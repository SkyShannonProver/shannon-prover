"""Agent-facing tactic execution result contract.

TacticExecutionResult is the live IDE-style envelope printed after proof
interaction commands.  It answers two questions in one place:

* what happened to the submitted tactic(s)?
* what is the current workspace the prover should reason from now?

CommitResponse, ProofContextView, and ProverWorkspaceView are the durable
inputs.  Legacy CommandSummary artifacts are historical readers only and are
not part of the live execution envelope.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from core.easycrypt.validation_result import ValidationResult
from core.easycrypt.value_shapes import as_dict as _dict, drop_empty as _drop_empty, as_list as _list


TACTIC_EXECUTION_RESULT_SCHEMA_VERSION = 1
TACTIC_EXECUTION_RESULT_KIND = "tactic_execution_result"


class TacticExecutionResultValidation(ValidationResult):
    """Canonical errors/warnings result under this view's public name."""


def build_tactic_execution_result(
    session_dir: str | Path,
    *,
    mode: str,
    command: str,
    commit_response: dict[str, Any],
    commit_response_payload: dict[str, Any] | None = None,
    proof_context_payload: dict[str, Any] | None = None,
    workspace_view: dict[str, Any] | None = None,
    workspace_payload: dict[str, Any] | None = None,
    raw_result: str = "",
    raw_result_payload: dict[str, Any] | None = None,
    chain_steps: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build the live result shown to the proving agent."""
    path = Path(session_dir)
    response = _dict(commit_response)
    mutation = _dict(response.get("mutation"))
    transition = _dict(response.get("latest_transition"))
    proof_state = _dict(response.get("proof_state"))
    proof_goal = _dict(proof_state.get("goal"))
    commit_payload = _dict(commit_response_payload)
    context_payload = _dict(proof_context_payload)
    workspace_data = _dict(workspace_view)
    workspace_artifact_payload = _dict(workspace_payload)
    workspace_goal = _dict(workspace_data.get("current_goal"))
    raw_payload = _dict(raw_result_payload)
    status = str(response.get("status") or "")
    normalized_mode = _normalize_mode(mode or _mode_from_command(command))
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
    candidate_after = _preflight_candidate_after(
        mode=normalized_mode,
        status=status,
        tactic=(attempted_tactics[0] if attempted_tactics else ""),
        raw_result=raw_result,
        raw_payload=raw_payload,
    )
    inspect_handles = build_inspect_handles(
        workspace_data,
        session_dir=path,
        proof_context_payload=context_payload,
    )
    if candidate_after:
        inspect_handles.insert(1, {
            "id": "preflight_candidate_after",
            "kind": "execution_panel",
            "source": "candidate_after.current_goal.lines",
            "description": (
                "Speculative after-goal from accepted preflight validation; committed "
                "session state is unchanged."
            ),
        })
    result = {
        "schema_version": TACTIC_EXECUTION_RESULT_SCHEMA_VERSION,
        "kind": TACTIC_EXECUTION_RESULT_KIND,
        "ok": bool(response.get("ok")) and not _list(response.get("errors")),
        "execution": _drop_empty({
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
            "preflight_accepted": status == "preflight_accepted",
            "steps": chain_steps or _steps_from_mutation(
                normalized_mode,
                attempted_tactics,
                accepted_count=accepted_count,
                failed_tactic=str(mutation.get("failed_tactic") or ""),
                status=status,
            ),
        }),
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
                workspace_artifact_payload.get("goal_complete"),
                workspace_goal.get("complete"),
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
        "candidate_after": candidate_after,
        "inspect_handles": inspect_handles,
        "audit": _drop_empty({
            "commit_response_artifact": str(commit_payload.get("artifact") or ""),
            "proof_context_artifact": str(context_payload.get("artifact") or ""),
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
    if not candidate_after:
        result.pop("candidate_after", None)
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


def build_inspect_handles(
    workspace_view: dict[str, Any],
    *,
    session_dir: str | Path,
    proof_context_payload: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Return stable IDE-like inspection handles for the current workspace."""
    view = _dict(workspace_view)
    context_payload = _dict(proof_context_payload)
    more_context = _dict(
        view.get("inspect_lookup_handles")
        or view.get("want_more_context")
        or view.get("more_context")
        or view.get("inspect_more")
    )
    handles: list[dict[str, Any]] = [
        {
            "id": "current_goal",
            "kind": "workspace_panel",
            "source": "workspace.view.current_goal.lines",
            "description": "Current EasyCrypt goal lines already shown inline.",
        },
        {
            "id": "goal_info",
            "kind": "manager_request",
            "request": "goal_info",
            "tool": "-goal-info",
            "proof_state_effect": "does_not_change_proof_state_read_only",
            "description": "Parse the current goal and auto-resolve names.",
        },
        {
            "id": "diagnose",
            "kind": "manager_request",
            "request": "diagnose",
            "tool": "-diagnose",
            "proof_state_effect": "does_not_change_proof_state_read_only",
            "description": "Diagnose the latest tactic or preflight error.",
        },
        {
            "id": "episode_view",
            "kind": "manager_request",
            "request": "episode_view",
            "tool": "-episode-view",
            "proof_state_effect": "does_not_change_proof_state_read_only",
            "description": "Inspect the cross-step tactic timeline.",
        },
    ]
    if _dict(view.get("proof_frontier") or view.get("program_frontier")):
        handles.append({
            "id": "program_frontier",
            "kind": "workspace_panel",
            "source": "workspace.view.program_frontier",
            "description": "Current proof frontier, call sites, instrumentation, and coverage.",
        })
    full_context = (
        str(context_payload.get("artifact") or "")
        or str(more_context.get("full_context_artifact") or "")
    )
    if full_context:
        handles.append({
            "id": "proof_context_artifact",
            "kind": "artifact",
            "artifact": full_context,
            "description": "Full ProofContextView for compiler internals.",
        })
    current_goal = _dict(view.get("current_goal"))
    current_goal_text_fully_shown = bool(
        current_goal.get("text_fully_shown")
        if "text_fully_shown" in current_goal
        else False
    )
    fallback = str(more_context.get("current_session_fallback") or "")
    if fallback and not current_goal_text_fully_shown:
        handles.append({
            "id": "current_session_goal_file",
            "kind": "current_session_file",
            "path": fallback,
            "description": (
                "Only use because current_goal.text_fully_shown=false; "
                "otherwise use workspace.view.current_goal.lines."
            ),
        })
    return _dedupe_handles(handles)


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
    out_dir = path / "tactic_raw_results"
    out_dir.mkdir(parents=True, exist_ok=True)
    artifact = out_dir / f"{safe_command}_{digest[:16]}.txt"
    artifact.write_text(text, encoding="utf-8")
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
    text = json.dumps(data, indent=2, sort_keys=True)
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()
    execution = _dict(data.get("execution"))
    safe_command = _safe_filename(str(execution.get("command") or "tactic"))
    out_dir = path / "tactic_execution_results"
    out_dir.mkdir(parents=True, exist_ok=True)
    artifact = out_dir / f"{safe_command}_{digest[:16]}.json"
    artifact.write_text(text + "\n", encoding="utf-8")
    workspace = _dict(data.get("workspace"))
    audit = _dict(data.get("audit"))
    candidate_after = _dict(data.get("candidate_after"))
    candidate_goal = _dict(candidate_after.get("current_goal"))
    candidate_after_available = bool(candidate_after)
    return {
        "schema_version": int(data.get("schema_version") or 0),
        "ok": bool(data.get("ok")) and validation.ok,
        "mode": str(execution.get("mode") or ""),
        "command": str(execution.get("command") or ""),
        "status": str(_dict(data.get("result")).get("status") or ""),
        "artifact": str(artifact),
        "result_hash": digest,
        "accepted_count": _int(execution.get("accepted_count")),
        "rollback_count": _int(execution.get("rollback_count")),
        "failed_tactic": str(execution.get("failed_tactic") or ""),
        "state_changed": bool(execution.get("state_changed")),
        "history_committed": bool(execution.get("history_committed")),
        "preflight_accepted": bool(execution.get("preflight_accepted")),
        "workspace_artifact": str(workspace.get("artifact") or ""),
        "workspace_chars": _int(workspace.get("workspace_chars")),
        "current_goal_text_fully_shown": workspace.get(
            "current_goal_text_fully_shown"
        ),
        "current_goal_truncated": workspace.get("current_goal_truncated"),
        "candidate_after_available": candidate_after_available,
        "candidate_after_goal_chars": _int(candidate_goal.get("char_count")),
        "candidate_after_text_fully_shown": bool(
            candidate_goal.get("text_fully_shown")
            if candidate_after_available else False
        ),
        "proof_context_artifact": str(audit.get("proof_context_artifact") or ""),
        "commit_response_artifact": str(audit.get("commit_response_artifact") or ""),
        "raw_result_artifact": str(audit.get("raw_result_artifact") or ""),
        "error_count": len(_list(data.get("errors"))) + len(validation.errors),
        "warning_count": len(validation.warnings),
    }


def record_tactic_execution_result(
    session_or_dir: Any,
    result: dict[str, Any],
    *,
    source: str = "session_cli",
) -> dict[str, Any]:
    session_dir = getattr(session_or_dir, "dir", session_or_dir)
    payload = write_tactic_execution_result_artifact(session_dir, result)
    emit = getattr(session_or_dir, "emit_event", None)
    if callable(emit):
        emit("tactic.execution.produced", payload, source=source)
    return payload


def format_tactic_execution_result(result: dict[str, Any]) -> str:
    delivery = _stdout_delivery_result(result)
    return "[TACTIC-EXECUTION-RESULT]\n" + json.dumps(
        delivery,
        separators=(",", ":"),
        sort_keys=False,
    ) + "\n"


def _stdout_delivery_result(result: dict[str, Any]) -> dict[str, Any]:
    """Return the agent-facing TER shape, ordered for transport truncation.

    The durable artifact keeps the full internal envelope.  Stdout is the live
    IDE panel, so it is workspace-first and avoids repeated explanatory fields
    that would push the current goal past common tool-output caps.
    """
    workspace = _dict(result.get("workspace"))
    delivery = {
        "execution": _dict(result.get("execution")),
        "result": _stdout_result_block(result.get("result")),
        "workspace": _stdout_workspace(workspace),
        "inspect_handles": _minimal_inspect_handles(result.get("inspect_handles")),
    }
    if result.get("candidate_after"):
        delivery["candidate_after"] = _stdout_candidate_after(
            result.get("candidate_after"),
        )
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


def _stdout_candidate_after(value: Any) -> dict[str, Any]:
    candidate = dict(_dict(value))
    candidate.pop("kind", None)
    candidate.pop("raw_result_artifact", None)
    return _drop_empty(candidate)


def _minimal_inspect_handles(value: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in _list(value):
        handle = _dict(item)
        compact = _drop_empty({
            "id": str(handle.get("id") or ""),
            "kind": str(handle.get("kind") or ""),
            "source": str(handle.get("source") or ""),
            "request": str(handle.get("request") or ""),
            "tool": str(handle.get("tool") or ""),
            "proof_state_effect": str(handle.get("proof_state_effect") or ""),
            "command": str(handle.get("command") or ""),
            "artifact": str(handle.get("artifact") or ""),
            "path": str(handle.get("path") or ""),
        })
        if compact:
            out.append(compact)
    return out


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
        "inspect_handles": list,
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
    if data.get("schema_version") != TACTIC_EXECUTION_RESULT_SCHEMA_VERSION:
        errors.append(
            "schema_version must be "
            f"{TACTIC_EXECUTION_RESULT_SCHEMA_VERSION}, "
            f"got {data.get('schema_version')!r}"
        )
    if data.get("kind") != TACTIC_EXECUTION_RESULT_KIND:
        errors.append(f"kind must be {TACTIC_EXECUTION_RESULT_KIND!r}")
    execution = _dict(data.get("execution"))
    mode = str(execution.get("mode") or "")
    if mode not in {"preflight", "commit", "commit_chain", "undo"}:
        errors.append(f"execution.mode is invalid: {mode!r}")
    for key in ("attempted_count", "accepted_count", "rollback_count"):
        value = execution.get(key)
        if not isinstance(value, int) or value < 0:
            errors.append(f"execution.{key} must be a non-negative int")
    attempted = _int(execution.get("attempted_count"))
    accepted = _int(execution.get("accepted_count"))
    if accepted > attempted and mode != "undo":
        errors.append("execution.accepted_count cannot exceed attempted_count")
    workspace = _dict(data.get("workspace"))
    view = _dict(workspace.get("view"))
    if view and view.get("kind") != "prover_workspace_view":
        errors.append("workspace.view must be a ProverWorkspaceView")
    candidate_after = data.get("candidate_after")
    if candidate_after is not None:
        if not isinstance(candidate_after, dict):
            errors.append("candidate_after must be a dict when present")
        elif candidate_after:
            if candidate_after.get("kind") != "preflight_candidate_after":
                errors.append("candidate_after.kind must be 'preflight_candidate_after'")
            current_goal = _dict(candidate_after.get("current_goal"))
            if not _list(current_goal.get("lines")) and not bool(
                candidate_after.get("goal_after_closed")
            ):
                errors.append(
                    "candidate_after.current_goal.lines is required unless preflight closed the goal"
                )
    if not _list(data.get("inspect_handles")):
        warnings.append("inspect_handles is empty")
    return TacticExecutionResultValidation(errors=errors, warnings=warnings)


def _mode_from_command(command: str) -> str:
    command = str(command or "").strip()
    if command in {"try", "try-chain"}:
        return "preflight"
    if command == "chain":
        return "commit_chain"
    if command == "prev":
        return "undo"
    return "commit"


def _normalize_mode(mode: str) -> str:
    mode = str(mode or "").strip()
    aliases = {
        "next": "commit",
        "try": "preflight",
        "try-chain": "preflight",
        "chain": "commit_chain",
        "prev": "undo",
    }
    return aliases.get(mode, mode)


def _history_committed(
    *,
    mode: str,
    status: str,
    accepted_count: int,
    transition: dict[str, Any],
) -> bool:
    if mode == "preflight":
        return False
    if mode == "undo":
        return status == "undone"
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
    if mode == "preflight":
        return False
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


def _preflight_candidate_after(
    *,
    mode: str,
    status: str,
    tactic: str,
    raw_result: str,
    raw_payload: dict[str, Any],
) -> dict[str, Any]:
    """Extract the speculative after-goal from a preflight transcript.

    Preflight intentionally leaves ``workspace.view`` at the committed state.
    When EasyCrypt accepted the candidate, the after-goal is still essential
    reasoning context, so surface it as a separate candidate panel instead of
    forcing the prover to read the raw try artifact.
    """
    if mode != "preflight":
        return {}
    if status not in {"preflight_accepted", "preflight_no_progress"}:
        return {}
    text = str(raw_result or "")
    goal_after_closed = bool(re.search(
        r"^\[(?:TRY|TRY-CHAIN)\] goal_after:\s+all goals closed\.\s*$",
        text,
        re.MULTILINE,
    ))
    remaining: int | None = None
    m_remaining = re.search(
        r"^\[(?:TRY|TRY-CHAIN)\] goal_after:\s+(\d+) subgoal\(s\) remaining\s*$",
        text,
        re.MULTILINE,
    )
    if m_remaining:
        remaining = _int(m_remaining.group(1))
    elif goal_after_closed:
        remaining = 0
    goal_text = _extract_try_goal_after_raw(text)
    if not goal_text and not goal_after_closed:
        return {}
    lines = _goal_lines(goal_text)
    goal_panel = {
        "lines": lines,
        "line_count": len(lines),
        "char_count": len("\n".join(lines)),
        "shown_lines": len(lines),
        "shown_chars": len("\n".join(lines)),
        "text_fully_shown": True,
        "truncated": False,
        "source": {
            "label": (
                "[TRY-CHAIN] goal_after_raw"
                if "[TRY-CHAIN] goal_after_raw:" in text
                else "[TRY] goal_after_raw"
            ),
            "ground_truth": False,
        },
    }
    inferred = _infer_goal_type(goal_text)
    if inferred:
        goal_panel["goal_type"] = inferred
    return _drop_empty({
        "kind": "preflight_candidate_after",
        "tactic": tactic,
        "status": status,
        "state_changed": False,
        "history_committed": False,
        "goal_after_closed": goal_after_closed,
        "goal_after_remaining": remaining,
        "current_goal": goal_panel if lines else {},
        "raw_result_artifact": str(raw_payload.get("artifact") or ""),
        "note": (
            "This is the speculative state after preflight. The committed "
            "workspace remains workspace.view."
        ),
    })


def _extract_try_goal_after_raw(text: str) -> str:
    lines = str(text or "").splitlines()
    for idx, line in enumerate(lines):
        marker = line.strip()
        if marker not in {"[TRY] goal_after_raw:", "[TRY-CHAIN] goal_after_raw:"}:
            continue
        marker_prefix = "[TRY-CHAIN] " if marker.startswith("[TRY-CHAIN]") else "[TRY] "
        body: list[str] = []
        for item in lines[idx + 1:]:
            if item.startswith("[TRY] NOTE:") or item.startswith("[TRY-CHAIN] NOTE:"):
                break
            if item.startswith(marker_prefix) and body:
                break
            body.append(item.rstrip())
        while body and not body[0].strip():
            body.pop(0)
        while body and not body[-1].strip():
            body.pop()
        return "\n".join(body)
    return ""


def _goal_lines(text: str) -> list[str]:
    if not text:
        return []
    raw = [line.rstrip() for line in text.splitlines()]
    while raw and not raw[0].strip():
        raw.pop(0)
    while raw and not raw[-1].strip():
        raw.pop()
    return raw


def _infer_goal_type(text: str) -> str:
    low = str(text or "").lower()
    if "~" in text and "&1" in text and "&2" in text:
        return "pRHL"
    if "pr[" in low:
        return "probability"
    if "phoare" in low:
        return "phoare"
    if "hoare" in low:
        return "hoare"
    return ""


def _dedupe_handles(handles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for handle in handles:
        handle_id = str(handle.get("id") or "")
        if not handle_id or handle_id in seen:
            continue
        seen.add(handle_id)
        out.append(_drop_empty(handle))
    return out


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
