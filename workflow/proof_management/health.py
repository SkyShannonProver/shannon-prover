"""Proof-node health event construction."""
from __future__ import annotations

from .protocol_repair import AgentIntent
from .types import NodeHealthEvent


def timeout_health_event(
    *,
    node_id: str,
    intent: AgentIntent,
    action: dict,
    state_version: int,
) -> NodeHealthEvent:
    label = str(action.get("label") or intent.intent)
    timeout = action.get("timeout_seconds")
    mutating = bool(action.get("mutates_proof_state"))
    if mutating:
        detail = (
            "proof state may be uncertain; returning the last completed "
            "ProverWorkspaceView without refreshing"
        )
    else:
        detail = (
            "proof state should be unchanged; returning the last completed "
            "ProverWorkspaceView"
        )
    return NodeHealthEvent(
        node_id=node_id,
        status="manager_action_timeout",
        message=(
            f"manager backend action {label!r} timed out after "
            f"{timeout}s; {detail}"
        ),
        state_version=state_version,
    )


def backend_failure_health_event(
    *,
    node_id: str,
    intent: AgentIntent,
    action: dict,
    state_version: int,
) -> NodeHealthEvent | None:
    label = str(action.get("label") or intent.intent)
    mutating = bool(action.get("mutates_proof_state"))
    if not mutating and label != "agent_view":
        return None
    return NodeHealthEvent(
        node_id=node_id,
        status="manager_backend_failure",
        message=(
            f"manager backend action {label!r} exited with code "
            f"{action.get('exit_code')}; returning the last completed "
            "ProverWorkspaceView"
        ),
        state_version=state_version,
    )
