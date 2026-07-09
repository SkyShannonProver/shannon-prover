"""Workflow-facing observer for EasyCrypt session artifacts.

The core EasyCrypt layer emits the facts: events, proof-state projection,
ProofContextView artifacts, and CommitResponse artifacts. This module is the
workflow boundary over those facts. Progress tracking should consume this
snapshot instead of separately grepping stdout, counting submitted command
text, or opening session files ad hoc.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from core.easycrypt.committed_history import read_committed_tactics
from core.easycrypt.session_agent_view import validate_proof_context_view
from core.easycrypt.session_commit_response import validate_commit_response
from core.easycrypt.session_tactic_execution_result import (
    validate_tactic_execution_result,
)
from core.easycrypt.session_events import (
    EVENTS_FILENAME,
    event_payload,
    read_event_file,
)
from core.easycrypt.session_projection import read_proof_state_projection


@dataclass(frozen=True)
class WorkflowSessionSnapshot:
    session_dir: str
    exists: bool
    ok: bool
    status: str = "unknown"
    candidate_ready: bool = False
    final_ready: bool = False
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
    latest_agent_view: dict[str, Any] | None = None
    latest_agent_payload: dict[str, Any] | None = None
    latest_workspace_view: dict[str, Any] | None = None
    latest_workspace_payload: dict[str, Any] | None = None
    latest_tactic_execution_result: dict[str, Any] | None = None
    latest_tactic_execution_payload: dict[str, Any] | None = None
    commit_response_count: int = 0
    agent_view_count: int = 0
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
            "candidate_ready": self.candidate_ready,
            "final_ready": self.final_ready,
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
            "latest_agent_view": self.latest_agent_view,
            "latest_agent_payload": self.latest_agent_payload,
            "latest_workspace_view": self.latest_workspace_view,
            "latest_workspace_payload": self.latest_workspace_payload,
            "latest_tactic_execution_result": self.latest_tactic_execution_result,
            "latest_tactic_execution_payload": self.latest_tactic_execution_payload,
            "commit_response_count": self.commit_response_count,
            "agent_view_count": self.agent_view_count,
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
    events = read_event_file(path / EVENTS_FILENAME)
    active_tool, active_mutates = _pending_tool(events)
    projection = None
    try:
        projection = read_proof_state_projection(
            path,
            live_tool_name=active_tool,
        )
    except Exception as exc:
        errors.append(f"projection unreadable: {exc}")

    latest_commit, latest_commit_payload, commit_errors, commit_warnings = (
        _latest_commit_response(path, events)
    )
    latest_agent, latest_agent_payload, agent_errors, agent_warnings = (
        _latest_agent_view(path, events)
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
    errors.extend(agent_errors)
    errors.extend(workspace_errors)
    errors.extend(execution_errors)
    warnings.extend(commit_warnings)
    warnings.extend(agent_warnings)
    warnings.extend(workspace_warnings)
    warnings.extend(execution_warnings)

    if projection is not None:
        errors.extend(projection.events.errors)
        errors.extend(projection.consistency.errors)
        warnings.extend(projection.events.warnings)
        warnings.extend(projection.consistency.warnings)
        status = projection.status
        candidate_ready = projection.candidate_ready
        final_ready = projection.final_ready
        tactic_count = projection.history.tactic_count
        history_exists = projection.history.exists
        goal_type = projection.goal.goal_type
        goal_hash = projection.goal.active_goal_hash
        num_remaining = projection.goal.num_remaining
        latest_transition = projection.latest_transition.to_dict()
        event_log_exists = projection.events.exists
        event_count = projection.events.event_count
    else:
        status = "unknown"
        candidate_ready = False
        final_ready = False
        tactic_count = 0
        history_exists = (path / "history.ec").exists()
        goal_type = "unknown"
        goal_hash = ""
        num_remaining = None
        latest_transition = {}
        event_log_exists = (path / EVENTS_FILENAME).exists()
        event_count = len(events)

    history_tactics = _read_history_tactics(path)
    if history_tactics:
        tactic_count = len(history_tactics)
        history_exists = True

    progress = _progress_summary(events)
    latest_tool_name, last_readonly_at, last_mutating_at = _tool_summary(events)

    return WorkflowSessionSnapshot(
        session_dir=str(path.resolve()),
        exists=path.exists(),
        ok=not errors,
        status=status,
        candidate_ready=candidate_ready,
        final_ready=final_ready,
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
        latest_agent_view=latest_agent,
        latest_agent_payload=latest_agent_payload,
        latest_workspace_view=latest_workspace,
        latest_workspace_payload=latest_workspace_payload,
        latest_tactic_execution_result=latest_execution,
        latest_tactic_execution_payload=latest_execution_payload,
        commit_response_count=len(_events_of_type(events, "commit.response.produced")),
        agent_view_count=len(_events_of_type(events, "agent.view.produced")),
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


def _read_history_tactics(path: Path) -> list[str]:
    return read_committed_tactics(path)


def _latest_commit_response(
    session_dir: Path,
    events: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, list[str], list[str]]:
    produced = _events_of_type(events, "commit.response.produced")
    if not produced:
        return None, None, [], []
    event = produced[-1]
    payload = event_payload(event)
    data, errors, warnings = _read_hashed_artifact(
        payload,
        hash_field="response_hash",
        label="commit-response",
    )
    if data is None:
        return None, payload, errors, warnings
    validation = validate_commit_response(data)
    errors.extend(f"commit-response: {err}" for err in validation.errors)
    warnings.extend(f"commit-response: {warn}" for warn in validation.warnings)
    mutation = data.get("mutation") if isinstance(data.get("mutation"), dict) else {}
    proof_state = data.get("proof_state") if isinstance(
        data.get("proof_state"), dict,
    ) else {}
    if data.get("command") != payload.get("command"):
        errors.append("commit-response: command mismatch")
    if data.get("status") != payload.get("status"):
        errors.append("commit-response: status mismatch")
    if payload.get("proof_status") != proof_state.get("status"):
        errors.append("commit-response: proof_status mismatch")
    if payload.get("attempted_count") != mutation.get("attempted_count"):
        errors.append("commit-response: attempted_count mismatch")
    if payload.get("accepted_count") != mutation.get("accepted_count"):
        errors.append("commit-response: accepted_count mismatch")
    return data, payload, errors, warnings


def _latest_agent_view(
    session_dir: Path,
    events: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, list[str], list[str]]:
    produced = _events_of_type(events, "agent.view.produced")
    if not produced:
        return None, None, [], []
    event = produced[-1]
    payload = event_payload(event)
    data, errors, warnings = _read_hashed_artifact(
        payload,
        hash_field="view_hash",
        label="agent-view",
    )
    if data is None:
        return None, payload, errors, warnings
    validation = validate_proof_context_view(data)
    errors.extend(f"agent-view: {err}" for err in validation.errors)
    warnings.extend(f"agent-view: {warn}" for warn in validation.warnings)
    proof_state = data.get("proof_state") if isinstance(
        data.get("proof_state"), dict,
    ) else {}
    goal = proof_state.get("goal") if isinstance(
        proof_state.get("goal"), dict,
    ) else {}
    if payload.get("proof_status") != proof_state.get("status"):
        errors.append("agent-view: proof_status mismatch")
    if payload.get("goal_hash") != goal.get("active_goal_hash"):
        errors.append("agent-view: goal_hash mismatch")
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
    data, errors, warnings = _read_hashed_artifact(
        payload,
        hash_field="view_hash",
        label="prover-workspace-view",
    )
    if data is None:
        return None, payload, errors, warnings
    if data.get("kind") != payload.get("view_kind"):
        errors.append("prover-workspace-view: view_kind mismatch")
    if bool(payload.get("ok")) != bool(data.get("ok")):
        errors.append("prover-workspace-view: ok flag mismatch")
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
    data, errors, warnings = _read_hashed_artifact(
        payload,
        hash_field="result_hash",
        label="tactic-execution-result",
    )
    if data is None:
        return None, payload, errors, warnings
    validation = validate_tactic_execution_result(data)
    errors.extend(f"tactic-execution-result: {err}" for err in validation.errors)
    warnings.extend(
        f"tactic-execution-result: {warn}" for warn in validation.warnings
    )
    execution = data.get("execution") if isinstance(
        data.get("execution"), dict,
    ) else {}
    if payload.get("mode") != execution.get("mode"):
        errors.append("tactic-execution-result: mode mismatch")
    if payload.get("command") != execution.get("command"):
        errors.append("tactic-execution-result: command mismatch")
    if bool(payload.get("ok")) != bool(data.get("ok")):
        errors.append("tactic-execution-result: ok flag mismatch")
    return data, payload, errors, warnings


def _read_hashed_artifact(
    payload: dict[str, Any],
    *,
    hash_field: str,
    label: str,
) -> tuple[dict[str, Any] | None, list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    artifact = Path(str(payload.get("artifact") or ""))
    if not artifact.exists():
        return None, [f"{label}: artifact missing: {artifact}"], warnings
    try:
        data = json.loads(artifact.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, [f"{label}: artifact JSON unreadable: {exc}"], warnings
    if not isinstance(data, dict):
        return None, [f"{label}: artifact root is not an object"], warnings
    canonical = json.dumps(data, indent=2, sort_keys=True)
    digest = hashlib.sha1(canonical.encode("utf-8")).hexdigest()
    if payload.get(hash_field) != digest:
        errors.append(f"{label}: {hash_field} does not match artifact")
    if data.get("schema_version") != payload.get("schema_version"):
        errors.append(f"{label}: schema_version mismatch")
    if bool(payload.get("ok")) != bool(data.get("ok")):
        errors.append(f"{label}: ok flag mismatch")
    return data, errors, warnings


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
