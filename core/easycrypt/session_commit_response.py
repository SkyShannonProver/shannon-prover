"""Structured response artifact for session tactic commands.

The event stream already records low-level tactic events. CommitResponse is the
per-command envelope: one `-next`, `-prev`, or `-chain` invocation gets one
machine-readable summary with the post-command proof state, mutation counts,
and failure details.  The live Proof Interaction Manager records the
ProofContextView, ProverWorkspaceView, and TacticExecutionResult immediately
after this normalized response.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from core.easycrypt.validation_result import ValidationResult

from core.easycrypt.session_projection import (
    projection_to_goal_info,
    read_proof_state_projection,
)


COMMIT_RESPONSE_SCHEMA_VERSION = 1
COMMIT_RESPONSE_KIND = "commit_response"


class CommitResponseValidation(ValidationResult):
    """Canonical errors/warnings result under this view's public name."""


def build_commit_response(
    session_dir: str | Path,
    *,
    command: str,
    status: str,
    attempted_tactics: list[str] | None = None,
    accepted_count: int = 0,
    failed_tactic: str = "",
    failure_reason: str = "",
    keep_on_fail: bool = False,
    rollback_count: int = 0,
    agent_view_payload: dict[str, Any] | None = None,
    live_tool_name: str | None = None,
    ok: bool | None = None,
) -> dict[str, Any]:
    path = Path(session_dir)
    projection = read_proof_state_projection(
        path,
        live_tool_name=live_tool_name or command,
    )
    proof_state = projection_to_goal_info(projection)
    tactics = [str(t).strip() for t in (attempted_tactics or []) if str(t).strip()]
    command_ok = ok if ok is not None else status in {"ok", "undone"}
    errors = []
    if not command_ok and failure_reason:
        errors.append({
            "code": "commit.failed",
            "message": failure_reason,
            "failed_tactic": failed_tactic,
        })
    event_contract = proof_state.get("event_contract")
    if isinstance(event_contract, dict) and not event_contract.get("ok", True):
        errors.append({
            "code": "proof_state.event_contract",
            "message": "event contract is not valid",
        })
    response = {
        "schema_version": COMMIT_RESPONSE_SCHEMA_VERSION,
        "kind": COMMIT_RESPONSE_KIND,
        "ok": bool(command_ok) and not errors,
        "command": command,
        "status": status,
        "proof_state": proof_state,
        "latest_transition": proof_state.get("latest_transition") or {},
        "mutation": {
            "attempted_count": len(tactics),
            "accepted_count": int(accepted_count),
            "attempted_tactics": tactics,
            "failed_tactic": failed_tactic,
            "failure_reason": failure_reason,
            "keep_on_fail": bool(keep_on_fail),
            "rollback_count": int(rollback_count),
        },
        "agent_view": _compact_agent_view_payload(agent_view_payload or {}),
        "notes": [],
        "errors": errors,
        "debug": {},
    }
    validation = validate_commit_response(response)
    if validation.errors:
        response["errors"] = list(response["errors"]) + [
            {"code": "commit_response.invalid", "message": err}
            for err in validation.errors
        ]
    if validation.warnings:
        response["notes"] = [
            {"code": "commit_response.warning", "message": warn}
            for warn in validation.warnings
        ]
    response["ok"] = not response["errors"] and bool(command_ok)
    return response


def write_commit_response_artifact(
    session_dir: str | Path,
    response: dict[str, Any],
) -> dict[str, Any]:
    path = Path(session_dir)
    data = dict(response)
    validation = validate_commit_response(data)
    text = json.dumps(data, indent=2, sort_keys=True)
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()
    command = str(data.get("command") or "commit")
    safe_command = re.sub(r"[^A-Za-z0-9_.-]+", "_", command).strip("_") or "commit"
    out_dir = path / "commit_responses"
    out_dir.mkdir(parents=True, exist_ok=True)
    artifact = out_dir / f"{safe_command}_{digest[:16]}.json"
    artifact.write_text(text + "\n", encoding="utf-8")

    proof_state = data.get("proof_state") if isinstance(
        data.get("proof_state"), dict,
    ) else {}
    mutation = data.get("mutation") if isinstance(data.get("mutation"), dict) else {}
    agent_view = data.get("agent_view") if isinstance(
        data.get("agent_view"), dict,
    ) else {}
    return {
        "schema_version": int(data.get("schema_version") or 0),
        "ok": bool(data.get("ok")) and validation.ok,
        "command": command,
        "status": str(data.get("status") or ""),
        "artifact": str(artifact),
        "response_hash": digest,
        "proof_status": str(proof_state.get("status") or ""),
        "attempted_count": int(mutation.get("attempted_count") or 0),
        "accepted_count": int(mutation.get("accepted_count") or 0),
        "failed_tactic": str(mutation.get("failed_tactic") or ""),
        "error_count": len(data.get("errors") or []) + len(validation.errors),
        "warning_count": len(validation.warnings),
        "agent_view_artifact": str(agent_view.get("artifact") or ""),
    }


def record_commit_response(
    session_or_dir: Any,
    response: dict[str, Any],
    *,
    source: str = "session_cli",
) -> dict[str, Any]:
    session_dir = getattr(session_or_dir, "dir", session_or_dir)
    payload = write_commit_response_artifact(session_dir, response)
    emit = getattr(session_or_dir, "emit_event", None)
    if callable(emit):
        emit("commit.response.produced", payload, source=source)
    return payload


def validate_commit_response(data: dict[str, Any]) -> CommitResponseValidation:
    errors: list[str] = []
    warnings: list[str] = []
    required = {
        "schema_version": int,
        "kind": str,
        "ok": bool,
        "command": str,
        "status": str,
        "proof_state": dict,
        "latest_transition": dict,
        "mutation": dict,
        "agent_view": dict,
        "notes": list,
        "errors": list,
        "debug": dict,
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
    if data.get("schema_version") != COMMIT_RESPONSE_SCHEMA_VERSION:
        errors.append(
            f"schema_version must be {COMMIT_RESPONSE_SCHEMA_VERSION}, "
            f"got {data.get('schema_version')!r}"
        )
    if data.get("kind") != COMMIT_RESPONSE_KIND:
        errors.append(f"kind must be {COMMIT_RESPONSE_KIND!r}")
    if isinstance(data.get("command"), str) and not data["command"].strip():
        errors.append("command must be non-empty")
    if isinstance(data.get("status"), str) and not data["status"].strip():
        errors.append("status must be non-empty")

    mutation = data.get("mutation") if isinstance(data.get("mutation"), dict) else {}
    attempted = mutation.get("attempted_count")
    accepted = mutation.get("accepted_count")
    rollback = mutation.get("rollback_count")
    if not isinstance(attempted, int) or attempted < 0:
        errors.append("mutation.attempted_count must be a non-negative int")
        attempted = 0
    if not isinstance(accepted, int) or accepted < 0:
        errors.append("mutation.accepted_count must be a non-negative int")
        accepted = 0
    if not isinstance(rollback, int) or rollback < 0:
        errors.append("mutation.rollback_count must be a non-negative int")
        rollback = 0
    if isinstance(attempted, int) and isinstance(accepted, int) and accepted > attempted:
        errors.append("mutation.accepted_count cannot exceed attempted_count")
    tactics = mutation.get("attempted_tactics")
    if not isinstance(tactics, list):
        errors.append("mutation.attempted_tactics must be a list")
    elif isinstance(attempted, int) and len(tactics) != attempted:
        warnings.append("mutation.attempted_count differs from attempted_tactics length")
    elif isinstance(tactics, list):
        for idx, tactic in enumerate(tactics):
            if not isinstance(tactic, str):
                errors.append(f"mutation.attempted_tactics[{idx}] must be a string")
    for field_name in ("failed_tactic", "failure_reason"):
        if not isinstance(mutation.get(field_name), str):
            errors.append(f"mutation.{field_name} must be a string")
    if not isinstance(mutation.get("keep_on_fail"), bool):
        errors.append("mutation.keep_on_fail must be a bool")

    agent_view = data.get("agent_view")
    if isinstance(agent_view, dict):
        for field_name in ("artifact", "view_hash", "proof_status"):
            if field_name in agent_view and not isinstance(agent_view[field_name], str):
                errors.append(f"agent_view.{field_name} must be a string")
    for field_name in ("notes", "errors"):
        items = data.get(field_name)
        if isinstance(items, list):
            for idx, item in enumerate(items):
                if not isinstance(item, dict):
                    errors.append(f"{field_name}[{idx}] must be an object")
    return CommitResponseValidation(errors=errors, warnings=warnings)


def _compact_agent_view_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    out = {}
    for key in (
        "artifact",
        "view_hash",
        "proof_status",
        "goal_hash",
        "recommendation_count",
        "stale_recommendation_count",
        "error_count",
        "warning_count",
    ):
        if key in payload:
            out[key] = payload[key]
    return out
