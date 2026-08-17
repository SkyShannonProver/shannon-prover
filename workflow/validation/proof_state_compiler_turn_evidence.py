"""Validation-side binding of one rejected manager action to compiler evidence."""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any

from core.easycrypt.committed_history import committed_prefix_identity
from core.easycrypt.proof_state_compiler.contracts import (
    CompilerTurnEvidence,
    StateRef,
    freeze_json_object,
)
from workflow.proof_management.protocol_repair import AgentIntent


def rejected_turn_evidence(
    *,
    state_ref: StateRef,
    action: dict[str, Any],
    intent: AgentIntent,
    history: tuple[str, ...],
) -> CompilerTurnEvidence:
    """Bind one event-authoritative unchanged rejection, or fail closed."""

    if state_ref.committed_prefix_identity != committed_prefix_identity(history):
        raise RuntimeError("compiler StateRef prefix diverged from history authority")
    authority = action.get("execution_authority")
    if not isinstance(authority, dict):
        raise RuntimeError("manager action lacks execution authority")
    rejected_tactic = intent.payload.get("tactic")
    if (
        authority.get("authority_kind")
        != "event_bound_tactic_execution_result"
        or authority.get("event_type") != "tactic.execution.produced"
        or not isinstance(rejected_tactic, str)
        or authority.get("submitted_tactics") != [rejected_tactic]
        or authority.get("state_changed") is not False
        or authority.get("history_committed") is not False
    ):
        raise RuntimeError("manager failure authority contract diverged")
    artifact = PurePosixPath(str(authority.get("artifact_ref") or ""))
    try:
        index = artifact.parts.index("tactic_execution_results")
    except ValueError as exc:
        raise RuntimeError("failure artifact is not confined") from exc
    artifact_ref = str(PurePosixPath(*artifact.parts[index:]))
    return CompilerTurnEvidence(
        source_event_id=str(authority.get("event_id") or ""),
        source_event_sequence=int(authority.get("event_sequence")),
        authority_kind="event_bound_tactic_execution_result",
        artifact_ref=artifact_ref,
        artifact_hash=str(authority.get("artifact_hash") or ""),
        hash_algorithm=str(authority.get("hash_algorithm") or ""),
        post_state_ref=state_ref,
        intent=intent.intent,
        payload=freeze_json_object(intent.payload),
        outcome_kind=str(action.get("outcome_kind") or ""),
        proof_state_effect=str(action.get("proof_state_effect") or ""),
        structured_error=str(authority.get("structured_error") or "")[:1200],
    )
