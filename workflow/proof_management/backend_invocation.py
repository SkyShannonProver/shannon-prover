"""Strict event windows for one manager-owned backend invocation."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.easycrypt.session_events import validate_event


@dataclass(frozen=True)
class BackendInvocationBoundary:
    """Immutable byte boundary captured immediately before one CLI process."""

    session_dir: Path
    event_offset: int
    event_device: int | None
    event_inode: int | None
    action_name: str
    mutates_proof_state: bool


@dataclass(frozen=True)
class BackendInvocationWindow:
    """The one validated ``tool.called``/``tool.result`` event window."""

    events: tuple[dict[str, Any], ...] = ()
    call_index: int = -1
    result_index: int = -1
    error: str = ""

    @property
    def ok(self) -> bool:
        return not self.error and self.call_index >= 0 and self.result_index >= 0

    def exactly_one_produced_event(
        self,
        event_type: str,
    ) -> tuple[dict[str, Any] | None, str]:
        """Select one produced event and require it to lie inside this call."""

        matches = [
            (index, event)
            for index, event in enumerate(self.events)
            if event.get("type") == event_type
        ]
        if len(matches) != 1:
            return None, f"expected exactly one {event_type} event for this backend call"
        index, event = matches[0]
        if not (self.call_index < index < self.result_index):
            return None, f"{event_type} must occur between tool.called and tool.result"
        return event, ""


def capture_backend_invocation(
    session_dir: str | Path,
    *,
    action_name: str,
    mutates_proof_state: bool,
) -> BackendInvocationBoundary:
    """Capture the only legal lower bound for a live CLI result artifact."""

    resolved_dir = Path(session_dir).resolve()
    events_path = resolved_dir / "events.jsonl"
    try:
        stat = events_path.stat()
        offset = int(stat.st_size)
        device = int(stat.st_dev)
        inode = int(stat.st_ino)
    except FileNotFoundError:
        offset, device, inode = 0, None, None
    except OSError:
        # Resolution fails closed for an unreadable pre-call stream.
        offset, device, inode = -1, None, None
    return BackendInvocationBoundary(
        session_dir=resolved_dir,
        event_offset=offset,
        event_device=device,
        event_inode=inode,
        action_name=action_name,
        mutates_proof_state=mutates_proof_state,
    )


def resolve_backend_invocation(
    boundary: BackendInvocationBoundary,
    *,
    exit_code: int | None,
) -> BackendInvocationWindow:
    """Read and validate exactly one current-call tool event pair."""

    events, error = _events_after_boundary(boundary)
    if error:
        return BackendInvocationWindow(error=error)
    call_indices = [
        index for index, event in enumerate(events)
        if event.get("type") == "tool.called"
    ]
    if len(call_indices) != 1:
        return BackendInvocationWindow(
            events=tuple(events),
            error="expected exactly one post-boundary tool.called event",
        )
    call_index = call_indices[0]
    result_indices = [
        index for index, event in enumerate(events)
        if event.get("type") == "tool.result"
    ]
    if len(result_indices) != 1:
        return BackendInvocationWindow(
            events=tuple(events),
            call_index=call_index,
            error="expected exactly one post-boundary tool.result event",
        )
    result_index = result_indices[0]
    if result_index <= call_index:
        return BackendInvocationWindow(
            events=tuple(events),
            call_index=call_index,
            result_index=result_index,
            error="tool.result must occur after tool.called",
        )

    resolved_session = str(boundary.session_dir.resolve())
    for index, event_type in (
        (call_index, "tool.called"),
        (result_index, "tool.result"),
    ):
        event = events[index]
        issues = [
            issue for issue in validate_event(event, index + 1)
            if issue.severity == "error"
        ]
        if issues:
            return BackendInvocationWindow(
                events=tuple(events),
                call_index=call_index,
                result_index=result_index,
                error=(
                    f"{event_type} event contract is invalid: "
                    + "; ".join(issue.format() for issue in issues)
                ),
            )
        for field_name in ("session_dir", "session_id"):
            if event.get(field_name) != resolved_session:
                return BackendInvocationWindow(
                    events=tuple(events),
                    call_index=call_index,
                    result_index=result_index,
                    error=(
                        f"{event_type} envelope {field_name} does not match "
                        "the current session"
                    ),
                )
        payload = _event_payload(event)
        if payload.get("name") != boundary.action_name:
            return BackendInvocationWindow(
                events=tuple(events),
                call_index=call_index,
                result_index=result_index,
                error=f"{event_type} action does not match the current backend call",
            )
        if payload.get("session_dir") != resolved_session:
            return BackendInvocationWindow(
                events=tuple(events),
                call_index=call_index,
                result_index=result_index,
                error=(
                    f"{event_type} payload session_dir does not match the current session"
                ),
            )
        if payload.get("mutates_proof_state") is not boundary.mutates_proof_state:
            return BackendInvocationWindow(
                events=tuple(events),
                call_index=call_index,
                result_index=result_index,
                error=(
                    f"{event_type} mutates_proof_state does not match the "
                    "invocation boundary"
                ),
            )
    if _event_payload(events[result_index]).get("exit_code") != exit_code:
        return BackendInvocationWindow(
            events=tuple(events),
            call_index=call_index,
            result_index=result_index,
            error="tool.result exit_code does not match the completed backend call",
        )
    return BackendInvocationWindow(
        events=tuple(events),
        call_index=call_index,
        result_index=result_index,
    )


def _events_after_boundary(
    boundary: BackendInvocationBoundary,
) -> tuple[list[dict[str, Any]], str]:
    if boundary.event_offset < 0:
        return [], "could not capture a readable pre-call event boundary"
    path = boundary.session_dir / "events.jsonl"
    try:
        stat = path.stat()
        if boundary.event_inode is not None and (
            int(stat.st_dev) != boundary.event_device
            or int(stat.st_ino) != boundary.event_inode
        ):
            return [], "event stream was replaced during the backend call"
        if int(stat.st_size) < boundary.event_offset:
            return [], "event stream was truncated during the backend call"
        with path.open("rb") as handle:
            handle.seek(boundary.event_offset)
            raw = handle.read()
    except (FileNotFoundError, OSError) as exc:
        return [], f"could not read post-call events: {exc}"
    if not raw:
        return [], "backend call appended no events"
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        return [], f"post-call event bytes are not UTF-8: {exc}"
    events: list[dict[str, Any]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            return [], f"post-call event line {line_number} is invalid JSON: {exc}"
        if not isinstance(event, dict):
            return [], f"post-call event line {line_number} is not an object"
        events.append(event)
    return events, ""


def _event_payload(event: dict[str, Any]) -> dict[str, Any]:
    payload = event.get("payload")
    return payload if isinstance(payload, dict) else {}
