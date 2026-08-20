"""Bind one completed managed turn to compiler trigger evidence."""

from __future__ import annotations

from pathlib import PurePosixPath

from core.easycrypt.committed_history import committed_prefix_identity
from core.easycrypt.proof_state_compiler.contracts import (
    CompilerTurnEvidence,
    StateRef,
    freeze_json_object,
)
from workflow.proof_management.types import AgentIntent, ManagedTurn


def compiler_turn_evidence(
    turn: ManagedTurn,
    *,
    session_id: str,
    committed_history: list[str] | tuple[str, ...],
) -> CompilerTurnEvidence | None:
    """Return exact TER-backed evidence, or abstain without a fallback."""

    intent = turn.intent
    snapshot = turn.snapshot
    if intent is None or snapshot is None or intent.intent != "commit_tactic":
        return None
    action = next(
        (
            item
            for item in turn.manager_actions
            if isinstance(item, dict)
            and item.get("label") != "managed_goal_view"
        ),
        None,
    )
    goal_identity = str(snapshot.goal_hash or "")
    if snapshot.goal_identity_required and not goal_identity:
        return None
    try:
        post_state_ref = StateRef(
            session_id=session_id,
            state_version=int(snapshot.state_version),
            goal_identity=goal_identity,
            goal_identity_required=snapshot.goal_identity_required,
            committed_prefix_identity=committed_prefix_identity(
                committed_history
            ),
        )
        return compiler_turn_evidence_from_action(
            action=action,
            intent=intent,
            post_state_ref=post_state_ref,
        )
    except (TypeError, ValueError):
        return None


def compiler_turn_evidence_from_action(
    *,
    action: object,
    intent: AgentIntent,
    post_state_ref: StateRef,
) -> CompilerTurnEvidence | None:
    """Bind one exact manager action without inventing another authority path.

    The live manager and deterministic validation fixtures share this function.
    Callers remain responsible only for obtaining the exact post-state identity;
    this function alone interprets the event-bound tactic result.
    """

    if (
        not isinstance(action, dict)
        or not isinstance(intent, AgentIntent)
        or not isinstance(post_state_ref, StateRef)
    ):
        return None
    intent_kind = intent.intent
    payload = intent.payload
    if intent_kind != "commit_tactic":
        return None
    authority = action.get("execution_authority")
    if not isinstance(authority, dict):
        return None
    if (
        authority.get("authority_kind")
        != "event_bound_tactic_execution_result"
        or authority.get("event_type") != "tactic.execution.produced"
    ):
        return None
    tactic = payload.get("tactic")
    if (
        not isinstance(tactic, str)
        or not tactic.strip()
        or authority.get("submitted_tactics") != [tactic]
    ):
        return None
    outcome_kind = str(action.get("outcome_kind") or "")
    proof_state_effect = str(action.get("proof_state_effect") or "")
    state_changed = authority.get("state_changed")
    history_committed = authority.get("history_committed")
    if outcome_kind == "accepted":
        if (
            proof_state_effect != "changed"
            or state_changed is not True
            or history_committed is not True
        ):
            return None
    elif outcome_kind in {"rejected", "no_progress"}:
        if (
            proof_state_effect != "unchanged"
            or state_changed is not False
            or history_committed is not False
        ):
            return None
    else:
        return None
    event_id = str(authority.get("event_id") or "")
    event_sequence = authority.get("event_sequence")
    artifact_ref = _confined_artifact_ref(authority.get("artifact_ref"))
    if (
        not event_id
        or type(event_sequence) is not int
        or event_sequence < 0
        or not artifact_ref
    ):
        return None
    try:
        return CompilerTurnEvidence(
            source_event_id=event_id,
            source_event_sequence=event_sequence,
            authority_kind="event_bound_tactic_execution_result",
            artifact_ref=artifact_ref,
            artifact_hash=str(authority.get("artifact_hash") or ""),
            hash_algorithm=str(authority.get("hash_algorithm") or ""),
            post_state_ref=post_state_ref,
            intent=intent_kind,
            payload=freeze_json_object(payload),
            outcome_kind=outcome_kind,
            proof_state_effect=proof_state_effect,
            structured_error=str(
                authority.get("structured_error") or ""
            )[:1200],
        )
    except (TypeError, ValueError):
        return None


def _confined_artifact_ref(value: object) -> str:
    raw = str(value or "").replace("\\", "/")
    if not raw:
        return ""
    path = PurePosixPath(raw)
    parts = path.parts
    try:
        index = parts.index("tactic_execution_results")
    except ValueError:
        return ""
    relative = PurePosixPath(*parts[index:])
    if ".." in relative.parts or len(relative.parts) != 2:
        return ""
    return str(relative)
