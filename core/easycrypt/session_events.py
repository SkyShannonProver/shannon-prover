"""Structured event logging for EasyCrypt proof sessions.

The interactive CLI still prints human-readable text for agents and
humans. This module records the same state transitions as append-only
JSONL events so workflow/progress/eval code can consume stable facts
instead of grepping display markers.
"""
from __future__ import annotations

import json
import traceback
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Union


SCHEMA_VERSION = 1
EVENTS_FILENAME = "events.jsonl"


@dataclass(frozen=True)
class LatestTacticError:
    error: str = ""
    tactic: str = ""


@dataclass(frozen=True)
class TacticAttempt:
    event_id: str = ""
    event_type: str = ""
    event_index: int = -1
    attempt_kind: str = ""
    tactic: str = ""
    status: str = ""
    accepted: bool | None = None
    mutates_proof_state: bool | None = None
    error: str = ""
    error_kind: str = ""

    @property
    def is_empty(self) -> bool:
        return not (self.event_id or self.event_type or self.tactic)

    @property
    def failed(self) -> bool:
        return bool(self.error) or self.accepted is False or self.status in {
            "error",
            "probe_rejected",
            "probe_error",
        }

    def to_dict(self) -> dict[str, Any]:
        if self.is_empty:
            return {}
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "event_index": self.event_index,
            "attempt_kind": self.attempt_kind,
            "tactic": self.tactic,
            "status": self.status,
            "accepted": self.accepted,
            "mutates_proof_state": self.mutates_proof_state,
            "error": self.error,
            "error_kind": self.error_kind,
        }


@dataclass(frozen=True)
class EventSummary:
    event_counts: dict[str, int]
    tactic_submitted_count: int
    tactic_result_count: int
    candidate_closed_count: int
    result_candidate_closed_count: int
    tactic_status_counts: dict[str, int]
    verification_status: str | None
    latest_error: LatestTacticError
    latest_attempt: TacticAttempt | None
    recent_failed_attempts: list[TacticAttempt]


@dataclass(frozen=True)
class EventValidationIssue:
    severity: str
    code: str
    message: str
    event_index: int | None = None
    event_type: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "event_index": self.event_index,
            "event_type": self.event_type,
        }

    def format(self) -> str:
        prefix = f"{self.severity.upper()} {self.code}"
        if self.event_index is not None:
            prefix += f" event#{self.event_index}"
        if self.event_type:
            prefix += f" {self.event_type}"
        return f"{prefix}: {self.message}"


@dataclass(frozen=True)
class EventStreamValidation:
    issues: list[EventValidationIssue]

    @property
    def errors(self) -> list[EventValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "error"]

    @property
    def warnings(self) -> list[EventValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "warning"]

    @property
    def error_count(self) -> int:
        return len(self.errors)

    @property
    def warning_count(self) -> int:
        return len(self.warnings)

    @property
    def ok(self) -> bool:
        return self.error_count == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "issues": [issue.to_dict() for issue in self.issues],
        }


_NONE_TYPE = type(None)
_FIELD_TYPE = Union[type, tuple[type, ...]]


EVENT_PAYLOAD_SCHEMAS: dict[str, dict[str, dict[str, _FIELD_TYPE]]] = {
    "session.started": {
        "required": {
            "file": (str, _NONE_TYPE),
            "lemma": (str, _NONE_TYPE),
            "include_dirs": list,
            "discarded_tactic_count": int,
            "restart_count": int,
        },
        "optional": {
            "pre_restart_checkpoint_path": (str, _NONE_TYPE),
        },
    },
    "session.loaded_context": {
        "required": {
            "file": str,
            "context_file": str,
            "bytes": int,
            "lines": int,
        },
        "optional": {},
    },
    # Daemon-routing visibility events (#3 Step 5). MUST stay registered: an
    # emit_event of an unregistered type trips event.unknown_type, which the
    # fail-closed acceptance gate treats as fatal and SILENTLY REVERTS a fully
    # EC-verified proof (every daemon-path commit emits `ec.routing`). See the
    # ec_routing acceptance-gate regression. validate_event now also downgrades
    # unknown_type to a warning so a future miss degrades instead of reverting.
    "ec.routing": {
        "required": {
            "backend": str,
            "reason": (str, _NONE_TYPE),
        },
        "optional": {},
    },
    "session.daemon_context_opened": {
        "required": {
            "file": str,
            "lemma": (str, _NONE_TYPE),
            "include_dirs": list,
            "extracted_artifact": str,
            "mode": str,
        },
        "optional": {},
    },
    "session.daemon_context_open_failed": {
        "required": {
            "file": str,
            "lemma": (str, _NONE_TYPE),
            "include_dirs": list,
            "extracted_artifact": str,
            "error": str,
            "fallback": str,
        },
        "optional": {},
    },
    "tool.called": {
        "required": {
            "name": str,
            "mutates_proof_state": bool,
            "session_dir": str,
        },
        "optional": {
            "file": (str, _NONE_TYPE),
            "lemma": (str, _NONE_TYPE),
            "from_file": (str, _NONE_TYPE),
            "has_command": bool,
            "as_json": bool,
            "logged_after": bool,
            "verify_lemma": str,
        },
    },
    "tool.result": {
        "required": {
            "name": str,
            "mutates_proof_state": bool,
            "session_dir": str,
            "exit_code": int,
            "status": str,
        },
        "optional": {
            "file": (str, _NONE_TYPE),
            "lemma": (str, _NONE_TYPE),
            "from_file": (str, _NONE_TYPE),
            "has_command": bool,
            "as_json": bool,
            "verify_lemma": str,
        },
    },
    "tool.view.produced": {
        "required": {
            "tool": str,
            "schema_version": int,
            "ok": bool,
            "artifact": str,
            "view_hash": str,
        },
        "optional": {
            "proof_status": str,
            "recommendation_count": int,
            "error_count": int,
            "warning_count": int,
            "note_count": int,
        },
    },
    "agent.view.produced": {
        "required": {
            "schema_version": int,
            "ok": bool,
            "artifact": str,
            "view_hash": str,
        },
        "optional": {
            "proof_status": str,
            "goal_hash": str,
            "recommendation_count": int,
            "stale_recommendation_count": int,
            "error_count": int,
            "warning_count": int,
            "source_event_count": int,
        },
    },
    "prover.workspace_view.produced": {
        "required": {
            "schema_version": int,
            "view_kind": str,
            "ok": bool,
            "artifact": str,
            "view_hash": str,
        },
        "optional": {
            "proof_status": str,
            "current_goal_text_fully_shown": bool,
            "current_goal_truncated": bool,
            "goal_complete": bool,
            "goal_chars": int,
            "workspace_chars": int,
        },
    },
    "commit.response.produced": {
        "required": {
            "schema_version": int,
            "ok": bool,
            "command": str,
            "status": str,
            "artifact": str,
            "response_hash": str,
        },
        "optional": {
            "proof_status": str,
            "attempted_count": int,
            "accepted_count": int,
            "failed_tactic": str,
            "error_count": int,
            "warning_count": int,
            "agent_view_artifact": str,
        },
    },
    "tactic.execution.produced": {
        "required": {
            "schema_version": int,
            "ok": bool,
            "mode": str,
            "command": str,
            "status": str,
            "artifact": str,
            "result_hash": str,
        },
        "optional": {
            "accepted_count": int,
            "rollback_count": int,
            "failed_tactic": str,
            "state_changed": bool,
            "history_committed": bool,
            "probe_accepted": bool,
            "workspace_artifact": str,
            "workspace_chars": int,
            "current_goal_text_fully_shown": bool,
            "current_goal_truncated": bool,
            "candidate_after_available": bool,
            "candidate_after_goal_chars": int,
            "candidate_after_text_fully_shown": bool,
            "proof_context_artifact": str,
            "commit_response_artifact": str,
            "raw_result_artifact": str,
            "error_count": int,
            "warning_count": int,
        },
    },
    "command.summary.produced": {
        "required": {
            "schema_version": int,
            "ok": bool,
            "command": str,
            "command_status": str,
            "artifact": str,
            "summary_hash": str,
        },
        "optional": {
            "proof_status": str,
            "goal_hash": str,
            "goal_type": str,
            "num_remaining": (int, _NONE_TYPE),
            "history_tactic_count": int,
            "transition_kind": str,
            "primary_action": str,
            "recommendation_count": int,
            "error_count": int,
            "warning_count": int,
            "commit_response_artifact": str,
            "agent_view_artifact": str,
        },
    },
    "episode.timeline.produced": {
        "required": {
            "schema_version": int,
            "ok": bool,
            "artifact": str,
            "timeline_hash": str,
            "step_count": int,
        },
        "optional": {
            "final_proof_status": str,
            "final_primary_action": str,
            "note_count": int,
            "error_count": int,
        },
    },
    "tactic.submitted": {
        "required": {
            "tactic": str,
            "history_lines_before": int,
            "line_count": int,
        },
        "optional": {
            "deltas_only": bool,
        },
    },
    "diagnostic.emitted": {
        "required": {
            "source": str,
            "layer": int,
            "suppress_error": bool,
            "request_rollback": bool,
            "text": str,
        },
        "optional": {
            "schema_version": int,
            "kind": str,
            "recommendations": list,
            "evidence": dict,
            "notes": list,
            "errors": list,
            "debug": dict,
        },
    },
    "goal.changed": {
        "required": {
            "tactic": str,
            "goals_before": int,
            "goals_after": int,
            "no_more_goals": bool,
            "async_check_close": bool,
            "no_progress": bool,
            "candidate_closed": bool,
        },
        "optional": {
            "no_progress_reason": str,
        },
    },
    "tactic.result": {
        "required": {
            "tactic": str,
            "status": str,
            "history_committed": bool,
        },
        "optional": {
            "goals_before": int,
            "goals_after": int,
            "has_new_error": bool,
            "no_progress": bool,
            "no_progress_reason": str,
            "rollback_requested": bool,
            "history_lines_before": int,
            "history_lines_after": int,
            "candidate_closed": bool,
            "daemon_used": bool,
            "daemon_rejection": bool,
            "error_lines": list,
            "latest_error": str,
            "reason": str,
        },
    },
    "proof.candidate_closed": {
        "required": {
            "tactic": str,
            "goals_before": int,
            "goals_after": int,
            "no_more_goals": bool,
            "async_check_close": bool,
        },
        "optional": {},
    },
    "verification.completed": {
        "required": {
            "lemma": (str, _NONE_TYPE),
            "status": str,
            "verifier": str,
        },
        "optional": {
            "file": str,
            "full_file_status": str,
            "full_file_error_excerpt": str,
            "extracted_status": str,
            "verify_tmp": str,
            "verify_out": str,
            "use_session_proof": bool,
            "error_count": int,
            "errors": list,
            "reason": str,
            "error": str,
        },
    },
    "error.raised": {
        "required": {
            "phase": str,
        },
        "optional": {
            "kind": str,
            "action": str,
            "tactic": str,
            "exception_type": str,
            "exception": str,
            "traceback": str,
            "meta_command": str,
            "argument": str,
        },
    },
    "tactic.undone": {
        "required": {
            "status": str,
            "undone_tactic": str,
            "remaining_steps": int,
        },
        "optional": {
            "history_lines_after": int,
        },
    },
    "tactic.try_result": {
        "required": {
            "name": str,
            "kind": str,
            "mutates_proof_state": bool,
            "tactic": str,
            "status": str,
            "report": str,
        },
        "optional": {
            "accepted": (bool, _NONE_TYPE),
        },
    },
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def events_path(session_dir: Path) -> Path:
    return session_dir / EVENTS_FILENAME


def _json_safe(value: Any) -> Any:
    """Best-effort conversion to JSON-safe values.

    Event logging must never break a proof command. Unknown objects are
    rendered with ``repr`` so the event remains useful for debugging.
    """
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    return repr(value)


def make_event(
    session_dir: Path,
    event_type: str,
    payload: dict[str, Any] | None = None,
    *,
    source: str = "session_cli",
) -> dict[str, Any]:
    resolved_dir = str(session_dir.resolve()) if session_dir else ""
    return {
        "schema_version": SCHEMA_VERSION,
        "event_id": str(uuid.uuid4()),
        "timestamp": utc_now(),
        "session_id": resolved_dir,
        "session_dir": resolved_dir,
        "source": source,
        "type": event_type,
        "payload": _json_safe(payload or {}),
    }


def append_event(
    session_dir: Path,
    event_type: str,
    payload: dict[str, Any] | None = None,
    *,
    source: str = "session_cli",
) -> bool:
    """Append one JSONL event. Returns False on logging failure."""
    try:
        session_dir.mkdir(parents=True, exist_ok=True)
        path = events_path(session_dir)
        event = make_event(
            session_dir, event_type, payload, source=source,
        )
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, sort_keys=True) + "\n")
        return True
    except Exception:
        return False


def append_error_event(
    session_dir: Path,
    event_type: str,
    exc: BaseException,
    payload: dict[str, Any] | None = None,
    *,
    source: str = "session_cli",
) -> bool:
    data = dict(payload or {})
    data.update({
        "exception_type": type(exc).__name__,
        "exception": str(exc),
        "traceback": traceback.format_exc(limit=6),
    })
    return append_event(session_dir, event_type, data, source=source)


def read_event_file(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def read_events(session_dir: Path) -> list[dict[str, Any]]:
    return read_event_file(events_path(session_dir))


def event_payload(event: dict[str, Any]) -> dict[str, Any]:
    payload = event.get("payload") or {}
    return payload if isinstance(payload, dict) else {}


def events_of_type(
    events: list[dict[str, Any]],
    event_type: str,
) -> list[dict[str, Any]]:
    return [event for event in events if event.get("type") == event_type]


def validate_event(
    event: dict[str, Any],
    event_index: int | None = None,
) -> list[EventValidationIssue]:
    """Validate one event envelope and its known payload schema.

    The logger remains best-effort and permissive; this validator is the hard
    contract used by replay/audit code.
    """
    issues: list[EventValidationIssue] = []
    event_type = str(event.get("type") or "")

    def add(
        code: str,
        message: str,
        *,
        severity: str = "error",
    ) -> None:
        issues.append(EventValidationIssue(
            severity=severity,
            code=code,
            message=message,
            event_index=event_index,
            event_type=event_type,
        ))

    envelope_schema: dict[str, _FIELD_TYPE] = {
        "schema_version": int,
        "event_id": str,
        "timestamp": str,
        "session_id": str,
        "session_dir": str,
        "source": str,
        "type": str,
        "payload": dict,
    }
    for field, expected in envelope_schema.items():
        if field not in event:
            add("event.envelope.missing", f"missing envelope field `{field}`")
            continue
        if not _matches_type(event.get(field), expected):
            add(
                "event.envelope.type",
                f"envelope field `{field}` expected {_type_name(expected)}, "
                f"got {_value_type_name(event.get(field))}",
            )

    if "schema_version" in event and event.get("schema_version") != SCHEMA_VERSION:
        add(
            "event.schema_version",
            f"expected schema_version {SCHEMA_VERSION}, "
            f"got {event.get('schema_version')!r}",
        )
    if event.get("event_id") == "":
        add("event.envelope.empty", "`event_id` must be non-empty")
    if event.get("timestamp") == "":
        add("event.envelope.empty", "`timestamp` must be non-empty")
    if not event_type:
        add("event.envelope.empty", "`type` must be non-empty")
        return issues

    schema = EVENT_PAYLOAD_SCHEMAS.get(event_type)
    if schema is None:
        # Defense-in-depth: an unregistered type is a forward-compat gap, not a
        # proof-correctness problem (candidate-closed + verification PASS are gated
        # separately). Grade it a WARNING so a future unregistered emit degrades to
        # a non-fatal note instead of SILENTLY REVERTING an EC-verified proof at the
        # fail-closed acceptance gate (the ec_routing regression).
        add("event.unknown_type", f"unknown event type `{event_type}`",
            severity="warning")
        return issues

    payload = event_payload(event)
    for field, expected in schema.get("required", {}).items():
        if field not in payload:
            add("event.payload.missing", f"missing payload field `{field}`")
            continue
        if not _matches_type(payload.get(field), expected):
            add(
                "event.payload.type",
                f"payload field `{field}` expected {_type_name(expected)}, "
                f"got {_value_type_name(payload.get(field))}",
            )
    for field, expected in schema.get("optional", {}).items():
        if field in payload and not _matches_type(payload.get(field), expected):
            add(
                "event.payload.type",
                f"payload field `{field}` expected {_type_name(expected)}, "
                f"got {_value_type_name(payload.get(field))}",
            )
    return issues


def validate_event_stream(
    events: list[dict[str, Any]],
    *,
    expected_outcome: str | None = None,
) -> EventStreamValidation:
    """Validate event schema plus event-stream state transitions."""
    issues: list[EventValidationIssue] = []
    session_started = False
    pending_tool: dict[str, Any] | None = None
    pending_tactic: dict[str, Any] | None = None
    latest_tactic_result: dict[str, Any] | None = None
    candidate_close_count = 0
    result_candidate_close_count = 0
    latest_verification_status: str | None = None

    def add(
        code: str,
        message: str,
        *,
        idx: int | None = None,
        event_type: str = "",
        severity: str = "error",
    ) -> None:
        issues.append(EventValidationIssue(
            severity=severity,
            code=code,
            message=message,
            event_index=idx,
            event_type=event_type,
        ))

    if not events:
        add("stream.empty", "event stream is empty")
        return EventStreamValidation(issues)

    for idx, event in enumerate(events, start=1):
        event_type = str(event.get("type") or "")
        payload = event_payload(event)
        issues.extend(validate_event(event, idx))

        if event_type != "session.started" and not session_started:
            add(
                "stream.session.not_started",
                "event appeared before `session.started`",
                idx=idx,
                event_type=event_type,
            )
        if event_type == "session.started":
            if session_started:
                add(
                    "stream.session.duplicate_start",
                    "multiple `session.started` events in one stream",
                    idx=idx,
                    event_type=event_type,
                    severity="warning",
                )
            session_started = True

        if event_type == "tool.called":
            if pending_tool is not None:
                add(
                    "stream.tool.nested",
                    "tool.called occurred before previous tool.result",
                    idx=idx,
                    event_type=event_type,
                )
            pending_tool = payload
            continue

        if event_type == "tool.result":
            if pending_tool is None:
                add(
                    "stream.tool.result_without_call",
                    "tool.result has no matching tool.called",
                    idx=idx,
                    event_type=event_type,
                )
            else:
                called_name = str(pending_tool.get("name") or "")
                result_name = str(payload.get("name") or "")
                if called_name != result_name:
                    add(
                        "stream.tool.name_mismatch",
                        f"tool.result `{result_name}` does not match "
                        f"pending tool.called `{called_name}`",
                        idx=idx,
                        event_type=event_type,
                    )
                pending_tool = None
            continue

        if event_type == "tactic.submitted":
            if pending_tactic is not None:
                add(
                    "stream.tactic.nested",
                    "tactic.submitted occurred before previous tactic.result",
                    idx=idx,
                    event_type=event_type,
                )
            pending_tactic = payload
            continue

        if event_type == "goal.changed":
            if pending_tactic is None:
                add(
                    "stream.goal_changed_without_tactic",
                    "goal.changed has no pending tactic.submitted",
                    idx=idx,
                    event_type=event_type,
                )
            continue

        if event_type == "tactic.result":
            status = str(payload.get("status") or "")
            if pending_tactic is None and status != "refused":
                add(
                    "stream.tactic.result_without_submit",
                    "tactic.result has no matching tactic.submitted",
                    idx=idx,
                    event_type=event_type,
                )
            if pending_tactic is not None:
                submitted = _normalize_tactic_text(pending_tactic.get("tactic"))
                result = _normalize_tactic_text(payload.get("tactic"))
                if submitted != result:
                    add(
                        "stream.tactic.mismatch",
                        "tactic.result tactic does not match pending "
                        "tactic.submitted",
                        idx=idx,
                        event_type=event_type,
                    )
                pending_tactic = None
            if payload.get("candidate_closed"):
                result_candidate_close_count += 1
                if status != "ok":
                    add(
                        "stream.candidate_close.failed_tactic",
                        "non-ok tactic.result cannot be candidate_closed",
                        idx=idx,
                        event_type=event_type,
                    )
            latest_tactic_result = payload
            continue

        if event_type == "proof.candidate_closed":
            candidate_close_count += 1
            if latest_tactic_result is None:
                add(
                    "stream.candidate_close.no_tactic_result",
                    "proof.candidate_closed has no preceding tactic.result",
                    idx=idx,
                    event_type=event_type,
                )
            else:
                if latest_tactic_result.get("status") != "ok":
                    add(
                        "stream.candidate_close.failed_tactic",
                        "proof.candidate_closed follows a non-ok tactic.result",
                        idx=idx,
                        event_type=event_type,
                    )
                if not latest_tactic_result.get("candidate_closed"):
                    add(
                        "stream.candidate_close.result_not_marked",
                        "proof.candidate_closed follows a tactic.result whose "
                        "candidate_closed flag is false/missing",
                        idx=idx,
                        event_type=event_type,
                    )
            continue

        if event_type == "verification.completed":
            status = str(payload.get("status") or "")
            latest_verification_status = status
            if status == "pass" and candidate_close_count == 0:
                add(
                    "stream.verification.pass_without_candidate",
                    "verification.completed status=pass appeared before any "
                    "proof.candidate_closed event",
                    idx=idx,
                    event_type=event_type,
                )
            continue

    if pending_tool is not None:
        add(
            "stream.tool.missing_result",
            f"tool.called `{pending_tool.get('name')}` has no tool.result",
        )
    if pending_tactic is not None:
        add(
            "stream.tactic.missing_result",
            "tactic.submitted has no tactic.result",
        )
    if not session_started:
        add("stream.session.missing_start", "no `session.started` event found")
    if result_candidate_close_count != candidate_close_count:
        add(
            "stream.candidate_close.count_mismatch",
            "tactic.result candidate_closed count differs from "
            "proof.candidate_closed count",
        )
    if expected_outcome == "PASS" and latest_verification_status != "pass":
        add(
            "stream.verification.required_pass",
            "expected PASS outcome but latest verification.completed is not pass",
        )
    if expected_outcome and expected_outcome != "PASS" and latest_verification_status == "pass":
        add(
            "stream.verification.pass_on_nonpass",
            "latest verification.completed is pass but expected outcome is not PASS",
        )

    return EventStreamValidation(issues)


def count_event_types(events: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for event in events:
        typ = str(event.get("type") or "")
        if typ:
            counts[typ] = counts.get(typ, 0) + 1
    return counts


def candidate_closed_events(
    events: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        event for event in events
        if event.get("type") == "proof.candidate_closed"
        and event_payload(event).get("candidate_closed", True)
    ]


def has_candidate_closed(events: list[dict[str, Any]]) -> bool:
    return bool(candidate_closed_events(events))


def latest_tactic_error(
    events: list[dict[str, Any]],
) -> LatestTacticError:
    for event in reversed(events):
        if event.get("type") != "tactic.result":
            continue
        payload = event_payload(event)
        latest_error = str(payload.get("latest_error") or "").strip()
        if latest_error:
            return LatestTacticError(
                error=latest_error,
                tactic=str(payload.get("tactic") or ""),
            )
    return LatestTacticError()


def _report_error_excerpt(report: str) -> str:
    text = str(report or "")
    if not text.strip():
        return ""
    lines = [line.rstrip() for line in text.splitlines()]
    excerpt: list[str] = []
    capture = False
    for line in lines:
        stripped = line.strip()
        if stripped == "[TRY] error_excerpt:":
            capture = True
            continue
        if capture:
            if not line.startswith("  ") or stripped.startswith("[TRY]"):
                break
            if stripped:
                excerpt.append(stripped)
            if len(excerpt) >= 3:
                break
    if excerpt:
        return "\n".join(excerpt)

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[TRY] error:"):
            return stripped.removeprefix("[TRY] error:").strip()

    skip_prefixes = (
        "[TRY] tactic:",
        "[TRY] accepted:",
        "[TRY] goal_after:",
        "[TRY] NOTE:",
    )
    candidates: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith(skip_prefixes):
            continue
        lower = stripped.lower()
        if (
            "error" in lower
            or "wrong number" in lower
            or "cannot" in lower
            or "invalid" in lower
            or "failed" in lower
            or "mismatch" in lower
        ):
            candidates.append(stripped)
    if candidates:
        return "\n".join(candidates[:3])
    return ""


def _attempt_from_event(
    event: dict[str, Any],
    event_index: int,
) -> TacticAttempt | None:
    typ = str(event.get("type") or "")
    payload = event_payload(event)
    if typ == "tactic.result":
        status = str(payload.get("status") or "")
        error = str(payload.get("latest_error") or "").strip()
        return TacticAttempt(
            event_id=str(event.get("event_id") or ""),
            event_type=typ,
            event_index=event_index,
            attempt_kind="committed_tactic",
            tactic=str(payload.get("tactic") or ""),
            status=status,
            accepted=(False if status == "error" else True if status else None),
            mutates_proof_state=True,
            error=error,
            error_kind="easycrypt" if error else "",
        )
    if typ == "tactic.try_result":
        accepted = payload.get("accepted")
        accepted = accepted if isinstance(accepted, bool) else None
        tool_status = str(payload.get("status") or "")
        tool_error = tool_status == "error" or bool(payload.get("tool_error"))
        if tool_error:
            status = "probe_error"
        elif accepted is True:
            status = "probe_accepted"
        elif accepted is False:
            status = "probe_rejected"
        else:
            status = "probe_unknown"
        error = str(payload.get("latest_error") or "").strip()
        if not error and (tool_error or accepted is False):
            error = _report_error_excerpt(str(payload.get("report") or ""))
        return TacticAttempt(
            event_id=str(event.get("event_id") or ""),
            event_type=typ,
            event_index=event_index,
            attempt_kind="speculative_probe",
            tactic=str(payload.get("tactic") or ""),
            status=status,
            accepted=accepted,
            mutates_proof_state=False,
            error=error,
            error_kind=str(payload.get("error_kind") or ""),
        )
    return None


def latest_tactic_attempt(
    events: list[dict[str, Any]],
) -> TacticAttempt | None:
    for idx in range(len(events) - 1, -1, -1):
        attempt = _attempt_from_event(events[idx], idx)
        if attempt is not None:
            return attempt
    return None


def recent_failed_tactic_attempts(
    events: list[dict[str, Any]],
    *,
    limit: int = 5,
) -> list[TacticAttempt]:
    out: list[TacticAttempt] = []
    for idx in range(len(events) - 1, -1, -1):
        attempt = _attempt_from_event(events[idx], idx)
        if attempt is None or not attempt.failed:
            continue
        out.append(attempt)
        if len(out) >= limit:
            break
    return out


def summarize_events(events: list[dict[str, Any]]) -> EventSummary:
    tactic_result = events_of_type(events, "tactic.result")
    verification_events = events_of_type(events, "verification.completed")

    tactic_status_counts: dict[str, int] = {}
    result_candidate_closed_count = 0
    for event in tactic_result:
        payload = event_payload(event)
        status = str(payload.get("status", "unknown"))
        tactic_status_counts[status] = tactic_status_counts.get(status, 0) + 1
        if payload.get("candidate_closed"):
            result_candidate_closed_count += 1

    verification_status = None
    if verification_events:
        verification_status = event_payload(verification_events[-1]).get("status")

    return EventSummary(
        event_counts=count_event_types(events),
        tactic_submitted_count=len(events_of_type(events, "tactic.submitted")),
        tactic_result_count=len(tactic_result),
        candidate_closed_count=len(candidate_closed_events(events)),
        result_candidate_closed_count=result_candidate_closed_count,
        tactic_status_counts=tactic_status_counts,
        verification_status=verification_status,
        latest_error=latest_tactic_error(events),
        latest_attempt=latest_tactic_attempt(events),
        recent_failed_attempts=recent_failed_tactic_attempts(events),
    )


def _matches_type(value: Any, expected: _FIELD_TYPE) -> bool:
    expected_types = expected if isinstance(expected, tuple) else (expected,)
    if value is None:
        return _NONE_TYPE in expected_types
    for typ in expected_types:
        if typ is _NONE_TYPE:
            continue
        if typ is bool:
            if isinstance(value, bool):
                return True
            continue
        if typ is int:
            if isinstance(value, int) and not isinstance(value, bool):
                return True
            continue
        if isinstance(value, typ):
            return True
    return False


def _type_name(expected: _FIELD_TYPE) -> str:
    expected_types = expected if isinstance(expected, tuple) else (expected,)
    names = []
    for typ in expected_types:
        if typ is _NONE_TYPE:
            names.append("None")
        else:
            names.append(typ.__name__)
    return " | ".join(names)


def _value_type_name(value: Any) -> str:
    if value is None:
        return "None"
    return type(value).__name__


def _normalize_tactic_text(text: Any) -> str:
    tactic = str(text or "").strip().replace("\\!", "!")
    if tactic and not tactic.endswith("."):
        tactic += "."
    return tactic.rstrip()
