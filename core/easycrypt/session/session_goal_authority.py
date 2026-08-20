"""Shared current-goal authority predicates for managed session artifacts.

``ProofStateProjection.status`` is an aggregate diagnostic.  It may truthfully
be ``error`` after a rejected operation while the unchanged EasyCrypt goal is
still open.  Consumers that need source-state liveness must therefore use the
orthogonal goal, event, consistency, and identity facts below instead of
interpreting the aggregate status as a goal-state enum.
"""
from __future__ import annotations



def authoritative_open_goal_errors(proof_state: object) -> tuple[str, ...]:
    """Explain why a compact projected proof state is not authoritatively open."""

    if not isinstance(proof_state, dict):
        return ("proof state must be an object",)
    errors: list[str] = []
    goal = proof_state.get("goal")
    goal = goal if isinstance(goal, dict) else {}
    event_contract = proof_state.get("event_contract")
    event_contract = event_contract if isinstance(event_contract, dict) else {}
    consistency = proof_state.get("consistency")
    consistency = consistency if isinstance(consistency, dict) else {}

    if proof_state.get("goal_identity_required") is not True:
        errors.append("goal identity is not required")
    if goal.get("state_kind") != "open":
        errors.append("current goal state is not open")
    if goal.get("proof_candidate_closed") is not False:
        errors.append("current goal is closed or indeterminate")
    if not str(goal.get("active_goal_hash") or ""):
        errors.append("active goal identity is missing")
    if event_contract.get("ok") is not True:
        errors.append("event contract is not valid")
    if consistency.get("ok") is not True:
        errors.append("proof-state projection is inconsistent")
    return tuple(errors)


def has_authoritative_open_goal(proof_state: object) -> bool:
    """Whether the current source goal is open under all managed authorities."""

    return not authoritative_open_goal_errors(proof_state)
