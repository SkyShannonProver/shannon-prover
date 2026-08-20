"""Durable, event-bound tactic execution result contract.

TacticExecutionResult is the authoritative artifact recorded after proof
interaction commands. It answers two questions in one place:

* what happened to the submitted tactic(s)?
* what is the current managed workspace the prover should reason from now?

CommitResponse and the managed ProverWorkspaceView are the durable inputs to
this execution envelope. Human/backend CLI output may display a compact copy,
but live manager consumers bind through the produced event.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from core.easycrypt.session.session_artifact_io import write_confined_text_artifact
from core.easycrypt.validation_result import ValidationResult
from core.easycrypt.session.session_events import (
    read_events,
    record_authoritative_artifact_event,
)
from core.easycrypt.session.session_prover_workspace_schema import (
    validate_prover_workspace_view,
)
from core.easycrypt.session.session_tactic_execution_artifacts import (
    validate_linked_workspace_artifact,
    validate_linked_workspace_event,
)
from core.easycrypt.value_shapes import as_dict as _dict, drop_empty as _drop_empty, as_list as _list


TACTIC_EXECUTION_RESULT_SCHEMA_VERSION = 1
TACTIC_EXECUTION_RESULT_KIND = "tactic_execution_result"
TACTIC_EXECUTION_RESULT_STATUSES = frozenset({
    "ok",
    "error",
    "failed",
    "partial_success",
    "undone",
    "no_progress",
    "no_progress_reverted",
    "refused",
})


class TacticExecutionResultValidation(ValidationResult):
    """Canonical errors/warnings result under this view's public name."""


def build_tactic_execution_result(
    *,
    mode: str,
    command: str,
    commit_response: dict[str, Any],
    commit_response_payload: dict[str, Any] | None = None,
    workspace_view: dict[str, Any] | None = None,
    workspace_payload: dict[str, Any] | None = None,
    raw_result: str = "",
    raw_result_payload: dict[str, Any] | None = None,
    chain_steps: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build the authoritative result for one backend proof interaction."""
    response = _dict(commit_response)
    mutation = _dict(response.get("mutation"))
    transition = _dict(response.get("latest_transition"))
    proof_state = _dict(response.get("proof_state"))
    proof_goal = _dict(proof_state.get("goal"))
    commit_payload = _dict(commit_response_payload)
    workspace_data = _dict(workspace_view)
    workspace_artifact_payload = _dict(workspace_payload)
    workspace_goal = _dict(workspace_data.get("current_goal"))
    raw_payload = _dict(raw_result_payload)
    status = str(response.get("status") or "")
    normalized_mode = str(mode or "").strip()
    attempted_tactics = [
        str(item)
        for item in _list(mutation.get("attempted_tactics"))
        if isinstance(item, str) and item.strip()
    ]
    accepted_count = _int(mutation.get("accepted_count"))
    rollback_count = _int(mutation.get("rollback_count"))
    history_committed = _history_committed(
        mode=normalized_mode,
        status=status,
        accepted_count=accepted_count,
        transition=transition,
    )
    state_changed = _state_changed(
        mode=normalized_mode,
        status=status,
        accepted_count=accepted_count,
        rollback_count=rollback_count,
        history_committed=history_committed,
    )
    execution_data = _drop_empty({
        "mode": normalized_mode,
        "command": str(command or response.get("command") or ""),
        "backend_command": str(response.get("command") or command or ""),
        "submitted_tactics": attempted_tactics,
        "attempted_count": _int(mutation.get("attempted_count")),
        "accepted_count": accepted_count,
        "rollback_count": rollback_count,
        "failed_tactic": str(mutation.get("failed_tactic") or ""),
        "failure_reason": str(mutation.get("failure_reason") or ""),
        "keep_on_fail": bool(mutation.get("keep_on_fail")),
        "state_changed": state_changed,
        "history_committed": history_committed,
        "steps": chain_steps or _steps_from_mutation(
            normalized_mode,
            attempted_tactics,
            accepted_count=accepted_count,
            failed_tactic=str(mutation.get("failed_tactic") or ""),
            status=status,
        ),
    })
    # Empty is the canonical undo submission set, not an absent field.
    execution_data["submitted_tactics"] = attempted_tactics
    result = {
        "schema_version": TACTIC_EXECUTION_RESULT_SCHEMA_VERSION,
        "kind": TACTIC_EXECUTION_RESULT_KIND,
        "ok": bool(response.get("ok")) and not _list(response.get("errors")),
        "execution": execution_data,
        "result": _drop_empty({
            "ok": bool(response.get("ok")),
            "status": status,
            "failed_tactic": str(mutation.get("failed_tactic") or ""),
            "failure_reason": str(mutation.get("failure_reason") or ""),
            "error": _first_error(response),
            "raw_excerpt": _excerpt(raw_result),
            "raw_result_artifact": str(raw_payload.get("artifact") or ""),
        }),
        "workspace": _drop_empty({
            "view": workspace_data,
            "artifact": str(workspace_artifact_payload.get("artifact") or ""),
            "view_hash": str(workspace_artifact_payload.get("view_hash") or ""),
            "current_goal_text_fully_shown": _first_present(
                workspace_artifact_payload.get("current_goal_text_fully_shown"),
                workspace_goal.get("text_fully_shown"),
            ),
            "current_goal_truncated": _first_present(
                workspace_artifact_payload.get("current_goal_truncated"),
                workspace_goal.get("truncated"),
            ),
            "goal_chars": workspace_artifact_payload.get("goal_chars"),
            "workspace_chars": (
                workspace_artifact_payload.get("workspace_chars")
                if workspace_artifact_payload
                else _json_size(workspace_data)
            ),
        }),
        "audit": _drop_empty({
            "commit_response_artifact": str(commit_payload.get("artifact") or ""),
            "prover_workspace_artifact": str(
                workspace_artifact_payload.get("artifact") or ""
            ),
            "raw_result_artifact": str(raw_payload.get("artifact") or ""),
            "proof_status": str(proof_state.get("status") or ""),
            "goal_hash": str(proof_goal.get("active_goal_hash") or ""),
            "goal_type": str(proof_goal.get("goal_type") or ""),
            "num_remaining": proof_goal.get("num_remaining"),
        }),
        "notes": [],
        "errors": _list(response.get("errors")),
    }
    validation = validate_tactic_execution_result(result)
    if validation.errors:
        result["errors"] = list(result["errors"]) + [
            {"code": "tactic_execution_result.invalid", "message": err}
            for err in validation.errors
        ]
    if validation.warnings:
        result["notes"] = list(result["notes"]) + [
            {"code": "tactic_execution_result.warning", "message": warn}
            for warn in validation.warnings
        ]
    result["ok"] = bool(result["ok"]) and not validation.errors
    return result


def write_tactic_raw_result_artifact(
    session_dir: str | Path,
    *,
    command: str,
    raw_result: str,
) -> dict[str, Any]:
    """Persist the raw EasyCrypt/session text used to build the result."""
    path = Path(session_dir)
    text = str(raw_result or "")
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()
    safe_command = _safe_filename(command or "tactic")
    artifact = write_confined_text_artifact(
        path,
        subdir="tactic_raw_results",
        filename=f"{safe_command}_{digest[:16]}.txt",
        text=text,
    )
    return {
        "artifact": str(artifact),
        "raw_result_hash": digest,
        "raw_result_chars": len(text),
    }


def write_tactic_execution_result_artifact(
    session_dir: str | Path,
    result: dict[str, Any],
) -> dict[str, Any]:
    path = Path(session_dir)
    data = dict(result)
    validation = validate_tactic_execution_result(data)
    if validation.errors:
        raise ValueError(
            "TacticExecutionResult contract: " + "; ".join(validation.errors)
        )
    linked_validation = validate_linked_workspace_artifact(
        data,
        session_dir=path,
    )
    if linked_validation.errors:
        raise ValueError(
            "TacticExecutionResult workspace artifact: "
            + "; ".join(linked_validation.errors)
        )
    text = json.dumps(data, indent=2, sort_keys=True)
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()
    execution = _dict(data.get("execution"))
    safe_command = _safe_filename(str(execution.get("command") or "tactic"))
    artifact = write_confined_text_artifact(
        path,
        subdir="tactic_execution_results",
        filename=f"{safe_command}_{digest[:16]}.json",
        text=text + "\n",
    )
    return tactic_execution_event_payload_fields(
        data,
        artifact=str(artifact),
        result_hash=digest,
        validation=validation,
    )


def tactic_execution_event_payload_fields(
    data: dict[str, Any],
    *,
    artifact: str,
    result_hash: str,
    validation: TacticExecutionResultValidation | None = None,
) -> dict[str, Any]:
    """Return the sole current ``tactic.execution.produced`` projection."""

    checked = validation or validate_tactic_execution_result(data)
    execution = _dict(data.get("execution"))
    workspace = _dict(data.get("workspace"))
    audit = _dict(data.get("audit"))
    return {
        "schema_version": int(data.get("schema_version") or 0),
        "ok": bool(data.get("ok")) and checked.ok,
        "mode": str(execution.get("mode") or ""),
        "command": str(execution.get("command") or ""),
        "status": str(_dict(data.get("result")).get("status") or ""),
        "artifact": str(artifact),
        "result_hash": result_hash,
        "accepted_count": _int(execution.get("accepted_count")),
        "rollback_count": _int(execution.get("rollback_count")),
        "failed_tactic": str(execution.get("failed_tactic") or ""),
        "state_changed": bool(execution.get("state_changed")),
        "history_committed": bool(execution.get("history_committed")),
        "workspace_artifact": str(workspace.get("artifact") or ""),
        "workspace_chars": _int(workspace.get("workspace_chars")),
        "current_goal_text_fully_shown": workspace.get(
            "current_goal_text_fully_shown"
        ),
        "current_goal_truncated": workspace.get("current_goal_truncated"),
        "commit_response_artifact": str(audit.get("commit_response_artifact") or ""),
        "raw_result_artifact": str(audit.get("raw_result_artifact") or ""),
        "error_count": len(_list(data.get("errors"))) + len(checked.errors),
        "warning_count": len(checked.warnings),
    }


def record_tactic_execution_result(
    session_or_dir: Any,
    result: dict[str, Any],
    *,
    source: str = "session_cli",
) -> dict[str, Any]:
    validation = validate_tactic_execution_result(result)
    if validation.errors:
        raise ValueError(
            "TacticExecutionResult contract: " + "; ".join(validation.errors)
        )
    session_dir = getattr(session_or_dir, "dir", session_or_dir)
    workspace_event_validation = validate_linked_workspace_event(
        result,
        events=read_events(Path(session_dir)),
    )
    if workspace_event_validation.errors:
        raise ValueError(
            "TacticExecutionResult workspace event contract: "
            + "; ".join(workspace_event_validation.errors)
        )
    return record_authoritative_artifact_event(
        session_or_dir,
        "tactic.execution.produced",
        lambda: write_tactic_execution_result_artifact(session_dir, result),
        source=source,
    )


def format_tactic_execution_result(result: dict[str, Any]) -> str:
    delivery = _stdout_delivery_result(result)
    return "[TACTIC-EXECUTION-RESULT]\n" + json.dumps(
        delivery,
        separators=(",", ":"),
        sort_keys=False,
    ) + "\n"


def _stdout_delivery_result(result: dict[str, Any]) -> dict[str, Any]:
    """Return the compact human/backend CLI display shape.

    The durable artifact keeps the full authoritative envelope. Stdout remains
    workspace-first for debugging and avoids repeated explanatory fields that
    would push the current goal past common tool-output caps.
    """
    workspace = _dict(result.get("workspace"))
    delivery = {
        "execution": _dict(result.get("execution")),
        "result": _stdout_result_block(result.get("result")),
        "workspace": _stdout_workspace(workspace),
    }
    return _drop_empty(delivery)


def _stdout_result_block(value: Any) -> dict[str, Any]:
    block = dict(_dict(value))
    block.pop("raw_result_artifact", None)
    return _drop_empty(block)


def _stdout_workspace(workspace: dict[str, Any]) -> dict[str, Any]:
    view = dict(_dict(workspace.get("view")))
    for key in ("schema_version", "kind", "ok"):
        view.pop(key, None)
    return _drop_empty({
        "view": view,
        "current_goal_text_fully_shown": workspace.get(
            "current_goal_text_fully_shown"
        ),
        "current_goal_truncated": workspace.get("current_goal_truncated"),
    })


def validate_tactic_execution_result(
    data: dict[str, Any],
) -> TacticExecutionResultValidation:
    errors: list[str] = []
    warnings: list[str] = []
    required = {
        "schema_version": int,
        "kind": str,
        "ok": bool,
        "execution": dict,
        "result": dict,
        "workspace": dict,
        "audit": dict,
        "notes": list,
        "errors": list,
    }
    for key, typ in required.items():
        if key not in data:
            errors.append(f"missing field `{key}`")
            continue
        if not isinstance(data[key], typ):
            errors.append(
                f"field `{key}` expected {typ.__name__}, "
                f"got {type(data[key]).__name__}"
            )
    if (
        type(data.get("schema_version")) is not int
        or data.get("schema_version") != TACTIC_EXECUTION_RESULT_SCHEMA_VERSION
    ):
        errors.append(
            "schema_version must be "
            f"{TACTIC_EXECUTION_RESULT_SCHEMA_VERSION}, "
            f"got {data.get('schema_version')!r}"
        )
    if data.get("kind") != TACTIC_EXECUTION_RESULT_KIND:
        errors.append(f"kind must be {TACTIC_EXECUTION_RESULT_KIND!r}")
    if "inspect_handles" in data:
        errors.append(
            "inspect_handles is not part of TacticExecutionResult"
        )
    execution = _dict(data.get("execution"))
    mode = str(execution.get("mode") or "")
    if mode not in {"commit", "commit_chain", "undo"}:
        errors.append(f"execution.mode is invalid: {mode!r}")
    command = execution.get("command")
    if not isinstance(command, str) or not command:
        errors.append("execution.command must be a non-empty string")
    if "probe_accepted" in execution or "preflight_accepted" in execution:
        errors.append("preflight fields do not belong to tactic execution")
    for key in ("attempted_count", "accepted_count", "rollback_count"):
        value = execution.get(key)
        if type(value) is not int or value < 0:
            errors.append(f"execution.{key} must be a non-negative int")
    for key in ("state_changed", "history_committed"):
        if not isinstance(execution.get(key), bool):
            errors.append(f"execution.{key} must be a bool")
    attempted = _int(execution.get("attempted_count"))
    accepted = _int(execution.get("accepted_count"))
    submitted = execution.get("submitted_tactics")
    if type(submitted) is not list:
        errors.append("execution.submitted_tactics must be a list")
        submitted_tactics: list[str] = []
    else:
        submitted_tactics = submitted
        if any(type(tactic) is not str or not tactic.strip() for tactic in submitted):
            errors.append(
                "execution.submitted_tactics entries must be non-empty strings"
            )
    if attempted != len(submitted_tactics):
        errors.append(
            "execution.attempted_count must equal len(submitted_tactics)"
        )
    if accepted > attempted and mode != "undo":
        errors.append("execution.accepted_count cannot exceed attempted_count")
    result = _dict(data.get("result"))
    status = result.get("status")
    if status not in TACTIC_EXECUTION_RESULT_STATUSES:
        errors.append(f"result.status is invalid: {status!r}")
    if not isinstance(result.get("ok"), bool):
        errors.append("result.ok must be a bool")
    root_ok = data.get("ok")
    result_ok = result.get("ok")
    top_errors = data.get("errors")
    top_errors = top_errors if isinstance(top_errors, list) else []
    if type(root_ok) is bool and type(result_ok) is bool:
        expected_root_ok = result_ok and not top_errors
        if root_ok != expected_root_ok:
            errors.append(
                "root ok must equal result.ok with no top-level errors"
            )
    status_requires_ok = status in {
        "ok",
        "undone",
    }
    if type(result_ok) is bool and result_ok != status_requires_ok:
        errors.append("result.ok does not match result.status")
    if isinstance(status, str) and status.startswith("preflight_"):
        errors.append("non-preflight execution cannot use a preflight_* result.status")
    state_changed = execution.get("state_changed") is True
    history_committed = execution.get("history_committed") is True
    if history_committed and not state_changed:
        errors.append(
            "execution.history_committed requires state_changed=true"
        )
    if mode == "undo":
        if attempted or accepted or submitted_tactics:
            errors.append("undo execution cannot submit or accept tactics")
        if status not in {"undone", "no_progress", "refused"}:
            errors.append(
                "undo execution requires undone, no_progress, or refused status"
            )
        if status == "undone" and not (state_changed and history_committed):
            errors.append(
                "undone execution requires committed proof-state change"
            )
        if status != "undone" and (state_changed or history_committed):
            errors.append(
                "non-undone execution cannot change or commit proof history"
            )
    if mode in {"commit", "commit_chain"}:
        if accepted > 0 and not (state_changed and history_committed):
            errors.append(
                "accepted tactics require committed proof-state change"
            )
        if status == "ok" and (
            attempted < 1 or accepted != attempted
        ):
            errors.append(
                "successful commit must accept every submitted tactic"
            )
        if status == "partial_success" and accepted < 1:
            errors.append(
                "partial_success requires at least one accepted tactic"
            )
    workspace = _dict(data.get("workspace"))
    view = _dict(workspace.get("view"))
    view_validation = validate_prover_workspace_view(view)
    errors.extend(
        f"workspace.view: {error}"
        for error in view_validation.errors
    )
    workspace_artifact = workspace.get("artifact")
    workspace_hash = workspace.get("view_hash")
    if not isinstance(workspace_artifact, str) or not workspace_artifact:
        errors.append("workspace.artifact must be a non-empty string")
    if not isinstance(workspace_hash, str) or not workspace_hash:
        errors.append("workspace.view_hash must be a non-empty string")
    elif view:
        canonical_view = json.dumps(view, indent=2, sort_keys=True)
        embedded_hash = hashlib.sha1(canonical_view.encode("utf-8")).hexdigest()
        if workspace_hash != embedded_hash:
            errors.append(
                "workspace.view_hash does not match embedded workspace.view"
            )
    for key in ("current_goal_text_fully_shown", "current_goal_truncated"):
        if not isinstance(workspace.get(key), bool):
            errors.append(f"workspace.{key} must be a bool")
    for key in ("goal_chars", "workspace_chars"):
        value = workspace.get(key)
        if type(value) is not int or value < 0:
            errors.append(f"workspace.{key} must be a non-negative int")
    audit = _dict(data.get("audit"))
    if audit.get("prover_workspace_artifact") != workspace_artifact:
        errors.append(
            "audit.prover_workspace_artifact must equal workspace.artifact"
        )
    if "command_summary_artifact" in audit:
        errors.append(
            "audit.command_summary_artifact is retired; "
            "TacticExecutionResult is the sole execution-result carrier"
        )
    if "candidate_after" in data:
        errors.append("candidate_after is retired; use exact tactic preflight")
    return TacticExecutionResultValidation(errors=errors, warnings=warnings)


def validate_tactic_execution_event_binding(
    data: dict[str, Any],
    payload: dict[str, Any],
    *,
    artifact_hash: str,
    include_contract: bool = True,
) -> TacticExecutionResultValidation:
    """Validate one produced-event payload against its current TER artifact."""

    validation = validate_tactic_execution_result(data)
    errors = list(validation.errors) if include_contract else []
    warnings = list(validation.warnings) if include_contract else []
    expected = tactic_execution_event_payload_fields(
        data,
        artifact=str(payload.get("artifact") or ""),
        result_hash=artifact_hash,
        validation=validation,
    )
    for key, expected_value in expected.items():
        if payload.get(key) != expected_value:
            errors.append(
                f"event payload `{key}` mismatch: "
                f"expected {expected_value!r}, got {payload.get(key)!r}"
            )
    return TacticExecutionResultValidation(errors=errors, warnings=warnings)


def _history_committed(
    *,
    mode: str,
    status: str,
    accepted_count: int,
    transition: dict[str, Any],
) -> bool:
    if mode == "undo":
        return status == "undone"
    if mode == "commit_chain" and status == "partial_success":
        # ``latest_transition`` describes the final (failed/reverted) tactic,
        # not the aggregate chain mutation.  With --keep-on-fail, a positive
        # accepted_count means the successful prefix remains in history even
        # though that last transition correctly says it was not committed.
        return accepted_count > 0
    if transition.get("history_committed") is not None:
        return bool(transition.get("history_committed"))
    return accepted_count > 0 and status in {"ok", "partial_success"}


def _state_changed(
    *,
    mode: str,
    status: str,
    accepted_count: int,
    rollback_count: int,
    history_committed: bool,
) -> bool:
    if mode == "undo":
        return status == "undone"
    if rollback_count and accepted_count == 0:
        return False
    return bool(history_committed or accepted_count > 0)


def _steps_from_mutation(
    mode: str,
    attempted_tactics: list[str],
    *,
    accepted_count: int,
    failed_tactic: str,
    status: str,
) -> list[dict[str, Any]]:
    if mode != "commit_chain":
        return []
    steps: list[dict[str, Any]] = []
    for idx, tactic in enumerate(attempted_tactics):
        if idx < accepted_count:
            step_status = "accepted"
        elif failed_tactic and tactic == failed_tactic:
            step_status = "failed"
        elif status == "ok":
            step_status = "accepted"
        else:
            step_status = "not_run"
        steps.append({
            "index": idx + 1,
            "tactic": tactic,
            "status": step_status,
        })
    return steps


def _first_error(response: dict[str, Any]) -> str:
    errors = _list(response.get("errors"))
    if not errors:
        mutation = _dict(response.get("mutation"))
        return str(mutation.get("failure_reason") or "")
    item = errors[0]
    if isinstance(item, dict):
        return str(item.get("message") or item.get("error") or "")
    return str(item)


def _excerpt(text: str, *, limit: int = 1200) -> str:
    text = str(text or "")
    if len(text) <= limit:
        return text
    half = max(1, (limit - 80) // 2)
    return text[:half].rstrip() + "\n...[snip]...\n" + text[-half:].lstrip()


def _safe_filename(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_") or "tactic"


def _json_size(value: Any) -> int:
    try:
        return len(json.dumps(value, sort_keys=True))
    except Exception:
        return 0




def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except Exception:
        return 0


def _first_present(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None
