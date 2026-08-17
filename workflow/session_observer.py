"""Workflow-facing observer for EasyCrypt session artifacts.

The core EasyCrypt layer emits the facts: events, proof-state projection,
current workspace artifacts, and CommitResponse artifacts. This module is the
workflow boundary over those facts. Progress tracking should consume this
snapshot instead of separately grepping stdout, counting submitted command
text, or opening session files ad hoc.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from core.easycrypt.session_artifact_io import (
    read_confined_hashed_json_object,
)
from core.easycrypt.session_commit_response import (
    COMMIT_RESPONSE_SCHEMA_VERSION,
    validate_commit_response_event_binding,
)
from core.easycrypt.session_prover_workspace_schema import (
    PROVER_WORKSPACE_VIEW_SCHEMA_VERSION,
    validate_prover_workspace_event_binding,
)
from core.easycrypt.session_tactic_execution_artifacts import (
    validate_linked_workspace_artifact,
    validate_linked_workspace_event,
)
from core.easycrypt.session_tactic_execution_result import (
    TACTIC_EXECUTION_RESULT_SCHEMA_VERSION,
    validate_tactic_execution_event_binding,
)
from core.easycrypt.session_events import (
    event_payload,
)
from core.easycrypt.session_projection import read_proof_state_projection


@dataclass(frozen=True)
class WorkflowSessionSnapshot:
    session_dir: str
    exists: bool
    ok: bool
    status: str = "unknown"
    goals_discharged: bool = False
    qed_committed: bool = False
    offline_verified: bool = False
    candidate_close_authority: dict[str, Any] = field(default_factory=dict)
    event_log_exists: bool = False
    event_count: int = 0
    tactic_count: int = 0
    history_exists: bool = False
    history_tactics: list[str] = field(default_factory=list)
    goal_type: str = "unknown"
    goal_hash: str = ""
    num_remaining: int | None = None
    latest_transition: dict[str, Any] = field(default_factory=dict)
    latest_commit_response: dict[str, Any] | None = None
    latest_commit_payload: dict[str, Any] | None = None
    latest_workspace_view: dict[str, Any] | None = None
    latest_workspace_payload: dict[str, Any] | None = None
    latest_tactic_execution_result: dict[str, Any] | None = None
    latest_tactic_execution_payload: dict[str, Any] | None = None
    commit_response_count: int = 0
    workspace_view_count: int = 0
    tactic_execution_count: int = 0
    errors_since_progress: int = 0
    last_progress_at: float = 0.0
    latest_tool_name: str = ""
    active_tool: str | None = None
    active_tool_mutates: bool | None = None
    last_readonly_tool_at: float = 0.0
    last_mutating_tool_at: float = 0.0
    contract_errors: list[str] = field(default_factory=list)
    contract_warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_dir": self.session_dir,
            "exists": self.exists,
            "ok": self.ok,
            "status": self.status,
            "goals_discharged": self.goals_discharged,
            "qed_committed": self.qed_committed,
            "offline_verified": self.offline_verified,
            "candidate_close_authority": dict(self.candidate_close_authority),
            "event_log_exists": self.event_log_exists,
            "event_count": self.event_count,
            "tactic_count": self.tactic_count,
            "history_exists": self.history_exists,
            "history_tactics": list(self.history_tactics),
            "goal_type": self.goal_type,
            "goal_hash": self.goal_hash,
            "num_remaining": self.num_remaining,
            "latest_transition": dict(self.latest_transition),
            "latest_commit_response": self.latest_commit_response,
            "latest_commit_payload": self.latest_commit_payload,
            "latest_workspace_view": self.latest_workspace_view,
            "latest_workspace_payload": self.latest_workspace_payload,
            "latest_tactic_execution_result": self.latest_tactic_execution_result,
            "latest_tactic_execution_payload": self.latest_tactic_execution_payload,
            "commit_response_count": self.commit_response_count,
            "workspace_view_count": self.workspace_view_count,
            "tactic_execution_count": self.tactic_execution_count,
            "errors_since_progress": self.errors_since_progress,
            "last_progress_at": self.last_progress_at,
            "latest_tool_name": self.latest_tool_name,
            "active_tool": self.active_tool,
            "active_tool_mutates": self.active_tool_mutates,
            "last_readonly_tool_at": self.last_readonly_tool_at,
            "last_mutating_tool_at": self.last_mutating_tool_at,
            "contract_errors": list(self.contract_errors),
            "contract_warnings": list(self.contract_warnings),
        }


def observe_session(
    session_dir: str | Path | None,
    *,
    cwd: str | Path | None = None,
) -> WorkflowSessionSnapshot:
    """Read one session directory into a workflow-level snapshot."""
    path = _resolve_session_dir(session_dir, cwd=cwd)
    if path is None:
        return WorkflowSessionSnapshot(
            session_dir="",
            exists=False,
            ok=False,
            contract_errors=["session directory is unknown"],
        )

    errors: list[str] = []
    warnings: list[str] = []
    events: list[dict[str, Any]] = []
    projection = None
    try:
        projection = read_proof_state_projection(
            path,
            infer_live_tool_name=True,
        )
        events = list(projection.source_events)
    except Exception as exc:
        errors.append(f"projection unreadable: {exc}")
    active_tool, active_mutates = _pending_tool(events)

    latest_commit, latest_commit_payload, commit_errors, commit_warnings = (
        _latest_commit_response(path, events)
    )
    latest_workspace, latest_workspace_payload, workspace_errors, workspace_warnings = (
        _latest_workspace_view(path, events)
    )
    (
        latest_execution,
        latest_execution_payload,
        execution_errors,
        execution_warnings,
    ) = _latest_tactic_execution_result(path, events)
    errors.extend(commit_errors)
    errors.extend(workspace_errors)
    errors.extend(execution_errors)
    warnings.extend(commit_warnings)
    warnings.extend(workspace_warnings)
    warnings.extend(execution_warnings)

    if projection is not None:
        errors.extend(projection.events.errors)
        errors.extend(projection.consistency.errors)
        warnings.extend(projection.events.warnings)
        warnings.extend(projection.consistency.warnings)
        status = projection.status
        goals_discharged = projection.goals_discharged
        qed_committed = projection.qed_committed
        offline_verified = projection.offline_verified
        candidate_close_authority = (
            projection.candidate_close_authority.to_dict()
        )
        tactic_count = projection.history.tactic_count
        history_exists = projection.history.exists
        history_tactics = list(projection.history.tactics)
        goal_type = projection.goal.goal_type
        goal_hash = projection.goal.active_goal_hash
        num_remaining = projection.goal.num_remaining
        latest_transition = projection.latest_transition.to_dict()
        event_log_exists = projection.events.exists
        event_count = projection.events.event_count
    else:
        status = "unknown"
        goals_discharged = False
        qed_committed = False
        offline_verified = False
        candidate_close_authority = {}
        tactic_count = 0
        history_exists = False
        history_tactics = []
        goal_type = "unknown"
        goal_hash = ""
        num_remaining = None
        latest_transition = {}
        event_log_exists = False
        event_count = len(events)

    progress = _progress_summary(events)
    latest_tool_name, last_readonly_at, last_mutating_at = _tool_summary(events)

    return WorkflowSessionSnapshot(
        session_dir=str(path.resolve()),
        exists=path.exists(),
        ok=not errors,
        status=status,
        goals_discharged=goals_discharged,
        qed_committed=qed_committed,
        offline_verified=offline_verified,
        candidate_close_authority=candidate_close_authority,
        event_log_exists=event_log_exists,
        event_count=event_count,
        tactic_count=tactic_count,
        history_exists=history_exists,
        history_tactics=history_tactics,
        goal_type=goal_type,
        goal_hash=goal_hash,
        num_remaining=num_remaining,
        latest_transition=latest_transition,
        latest_commit_response=latest_commit,
        latest_commit_payload=latest_commit_payload,
        latest_workspace_view=latest_workspace,
        latest_workspace_payload=latest_workspace_payload,
        latest_tactic_execution_result=latest_execution,
        latest_tactic_execution_payload=latest_execution_payload,
        commit_response_count=len(_events_of_type(events, "commit.response.produced")),
        workspace_view_count=len(_events_of_type(events, "prover.workspace_view.produced")),
        tactic_execution_count=len(_events_of_type(events, "tactic.execution.produced")),
        errors_since_progress=progress["errors_since_progress"],
        last_progress_at=progress["last_progress_at"],
        latest_tool_name=latest_tool_name,
        active_tool=active_tool,
        active_tool_mutates=active_mutates,
        last_readonly_tool_at=last_readonly_at,
        last_mutating_tool_at=last_mutating_at,
        contract_errors=errors,
        contract_warnings=warnings,
    )


def _resolve_session_dir(
    session_dir: str | Path | None,
    *,
    cwd: str | Path | None,
) -> Path | None:
    if not session_dir:
        return None
    path = Path(session_dir).expanduser()
    if not path.is_absolute() and cwd is not None:
        path = Path(cwd) / path
    return path


def _events_of_type(events: list[dict[str, Any]], typ: str) -> list[dict[str, Any]]:
    return [event for event in events if event.get("type") == typ]


def _pending_tool(events: list[dict[str, Any]]) -> tuple[str | None, bool | None]:
    pending: dict[str, Any] | None = None
    for event in events:
        typ = event.get("type")
        payload = event_payload(event)
        if typ == "tool.called":
            pending = payload
        elif typ == "tool.result":
            pending = None
    if pending is None:
        return None, None
    return (
        str(pending.get("name") or "") or None,
        bool(pending.get("mutates_proof_state")),
    )


def _tool_summary(events: list[dict[str, Any]]) -> tuple[str, float, float]:
    latest_name = ""
    last_readonly = 0.0
    last_mutating = 0.0
    for event in events:
        if event.get("type") not in {"tool.called", "tool.result"}:
            continue
        payload = event_payload(event)
        name = str(payload.get("name") or "")
        latest_name = name or latest_name
        ts = _event_ts(event)
        if bool(payload.get("mutates_proof_state")):
            last_mutating = max(last_mutating, ts)
        else:
            last_readonly = max(last_readonly, ts)
    return latest_name, last_readonly, last_mutating


def _latest_commit_response(
    session_dir: Path,
    events: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, list[str], list[str]]:
    produced = _events_of_type(events, "commit.response.produced")
    if not produced:
        return None, None, [], []
    event = produced[-1]
    payload = event_payload(event)
    session_errors = _event_session_binding_errors(
        session_dir,
        event,
        label="commit-response",
    )
    if session_errors:
        return None, payload, session_errors, []
    payload_errors = _event_schema_version_errors(
        payload,
        expected=COMMIT_RESPONSE_SCHEMA_VERSION,
        label="commit-response",
    )
    data, artifact_hash, errors, warnings = _read_hashed_artifact(
        session_dir,
        payload,
        artifact_subdir="commit_responses",
        hash_field="response_hash",
        label="commit-response",
    )
    errors[:0] = payload_errors
    if data is None:
        return None, payload, errors, warnings
    binding = validate_commit_response_event_binding(
        data,
        payload,
        artifact_hash=artifact_hash,
    )
    errors.extend(f"commit-response: {err}" for err in binding.errors)
    warnings.extend(f"commit-response: {warn}" for warn in binding.warnings)
    return data, payload, errors, warnings


def _latest_workspace_view(
    session_dir: Path,
    events: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, list[str], list[str]]:
    produced = _events_of_type(events, "prover.workspace_view.produced")
    if not produced:
        return None, None, [], []
    event = produced[-1]
    payload = event_payload(event)
    session_errors = _event_session_binding_errors(
        session_dir,
        event,
        label="prover-workspace-view",
    )
    if session_errors:
        return None, payload, session_errors, []
    payload_errors = _event_schema_version_errors(
        payload,
        expected=PROVER_WORKSPACE_VIEW_SCHEMA_VERSION,
        label="prover-workspace-view",
    )
    data, artifact_hash, errors, warnings = _read_hashed_artifact(
        session_dir,
        payload,
        artifact_subdir="prover_workspace_views",
        hash_field="view_hash",
        label="prover-workspace-view",
    )
    errors[:0] = payload_errors
    if data is None:
        return None, payload, errors, warnings
    binding = validate_prover_workspace_event_binding(
        data,
        payload,
        artifact_hash=artifact_hash,
    )
    errors.extend(
        f"prover-workspace-view: {err}"
        for err in binding.errors
    )
    warnings.extend(
        f"prover-workspace-view: {warn}"
        for warn in binding.warnings
    )
    return data, payload, errors, warnings


def _latest_tactic_execution_result(
    session_dir: Path,
    events: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, list[str], list[str]]:
    produced = _events_of_type(events, "tactic.execution.produced")
    if not produced:
        return None, None, [], []
    event = produced[-1]
    payload = event_payload(event)
    session_errors = _event_session_binding_errors(
        session_dir,
        event,
        label="tactic-execution-result",
    )
    if session_errors:
        return None, payload, session_errors, []
    payload_errors = _event_schema_version_errors(
        payload,
        expected=TACTIC_EXECUTION_RESULT_SCHEMA_VERSION,
        label="tactic-execution-result",
    )
    data, artifact_hash, errors, warnings = _read_hashed_artifact(
        session_dir,
        payload,
        artifact_subdir="tactic_execution_results",
        hash_field="result_hash",
        label="tactic-execution-result",
    )
    errors[:0] = payload_errors
    if data is None:
        return None, payload, errors, warnings
    binding = validate_tactic_execution_event_binding(
        data,
        payload,
        artifact_hash=artifact_hash,
    )
    errors.extend(f"tactic-execution-result: {err}" for err in binding.errors)
    warnings.extend(
        f"tactic-execution-result: {warn}" for warn in binding.warnings
    )
    linked = validate_linked_workspace_artifact(data, session_dir=session_dir)
    errors.extend(
        "tactic-execution-result.workspace: " + err
        for err in linked.errors
    )
    warnings.extend(
        "tactic-execution-result.workspace: " + warn
        for warn in linked.warnings
    )
    event_link = validate_linked_workspace_event(
        data,
        events=events,
        tactic_event=event,
    )
    errors.extend(
        "tactic-execution-result.workspace: " + err
        for err in event_link.errors
    )
    return data, payload, errors, warnings


def _event_schema_version_errors(
    payload: dict[str, Any],
    *,
    expected: int,
    label: str,
) -> list[str]:
    """Reject event metadata from any artifact generation but the current one."""

    actual = payload.get("schema_version")
    if actual == expected:
        return []
    return [
        f"{label}: event schema_version {actual!r} is unsupported; "
        f"expected {expected}"
    ]


def _event_session_binding_errors(
    session_dir: Path,
    event: dict[str, Any],
    *,
    label: str,
) -> list[str]:
    """Require an authoritative event to belong to the observed session."""

    expected = str(session_dir.resolve())
    return [
        f"{label}: event {field_name} does not match the current session: "
        f"expected {expected!r}, got {event.get(field_name)!r}"
        for field_name in ("session_dir", "session_id")
        if event.get(field_name) != expected
    ]


def _read_hashed_artifact(
    session_dir: Path,
    payload: dict[str, Any],
    *,
    artifact_subdir: str,
    hash_field: str,
    label: str,
) -> tuple[dict[str, Any] | None, str, list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    artifact_value = str(payload.get("artifact") or "")
    artifact_read = read_confined_hashed_json_object(
        session_dir,
        artifact_value,
        subdir=artifact_subdir,
    )
    if artifact_read is None:
        return None, "", [
            f"{label}: artifact missing or outside the current session's "
            f"{artifact_subdir} directory: {artifact_value}"
        ], warnings
    if not artifact_read.ok or artifact_read.data is None:
        return None, "", [f"{label}: artifact JSON unreadable"], warnings
    data = artifact_read.data
    digest = artifact_read.artifact_hash
    if payload.get(hash_field) != digest:
        errors.append(f"{label}: {hash_field} does not match artifact")
    if data.get("schema_version") != payload.get("schema_version"):
        errors.append(f"{label}: schema_version mismatch")
    if bool(payload.get("ok")) != bool(data.get("ok")):
        errors.append(f"{label}: ok flag mismatch")
    return data, digest, errors, warnings


def _progress_summary(events: list[dict[str, Any]]) -> dict[str, Any]:
    errors_since_progress = 0
    last_progress_at = 0.0
    commit_events = _events_of_type(events, "commit.response.produced")
    if commit_events:
        for event in commit_events:
            payload = event_payload(event)
            ts = _event_ts(event)
            status = str(payload.get("status") or "")
            accepted = payload.get("accepted_count")
            accepted = accepted if isinstance(accepted, int) else 0
            if accepted > 0 and status in {"ok", "partial_success"}:
                errors_since_progress = 0
                last_progress_at = max(last_progress_at, ts)
            elif status == "failed" or not bool(payload.get("ok", True)):
                errors_since_progress += 1
            elif status == "undone":
                errors_since_progress += 1
        return {
            "errors_since_progress": errors_since_progress,
            "last_progress_at": last_progress_at,
        }

    for event in events:
        typ = event.get("type")
        payload = event_payload(event)
        ts = _event_ts(event)
        if typ == "tactic.result":
            if payload.get("history_committed") and payload.get("status") == "ok":
                errors_since_progress = 0
                last_progress_at = max(last_progress_at, ts)
            elif payload.get("status") not in {"ok", ""}:
                errors_since_progress += 1
        elif typ == "tactic.undone":
            errors_since_progress += 1

    return {
        "errors_since_progress": errors_since_progress,
        "last_progress_at": last_progress_at,
    }


def _event_ts(event: dict[str, Any]) -> float:
    raw = str(event.get("timestamp") or "")
    if not raw:
        return 0.0
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).timestamp()
    except Exception:
        return 0.0
