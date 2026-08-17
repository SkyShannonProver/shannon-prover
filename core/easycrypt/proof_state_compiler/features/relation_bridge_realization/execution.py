"""Trigger-first execution gate for relation-bridge realization."""

from __future__ import annotations

from core.easycrypt.proof_state_compiler.contracts import (
    CURRENT_STATE_FAILURE,
    CompilerTurnEvidence,
)
from core.easycrypt.proof_state_compiler.features.execution import (
    FeatureExecutionEligibility,
    FeatureExecutionGate,
    ONCE_PER_TURN_OCCURRENCE,
)
from .syntax import relation_bridge_intent_family


def _relation_bridge_failure_eligibility(
    turn_evidence: CompilerTurnEvidence | None,
) -> FeatureExecutionEligibility:
    if turn_evidence is None:
        return FeatureExecutionEligibility(False, "no_completed_turn")
    if (
        turn_evidence.authority_kind != "event_bound_tactic_execution_result"
        or turn_evidence.intent != "commit_tactic"
    ):
        return FeatureExecutionEligibility(False, "unsupported_turn_authority")
    if (
        turn_evidence.outcome_kind not in {"rejected", "no_progress"}
        or turn_evidence.proof_state_effect != "unchanged"
    ):
        return FeatureExecutionEligibility(False, "turn_did_not_fail")
    tactic = turn_evidence.payload.to_dict().get("tactic")
    if not isinstance(tactic, str) or relation_bridge_intent_family(tactic) is None:
        return FeatureExecutionEligibility(False, "relation_intent_not_prefiltered")
    return FeatureExecutionEligibility(
        True,
        "candidate_relation_bridge_failure",
        CURRENT_STATE_FAILURE,
    )


RELATION_BRIDGE_FAILURE_EXECUTION_GATE = FeatureExecutionGate(
    gate_id="owned_current_relation_failure",
    predicate=_relation_bridge_failure_eligibility,
    lifetime=ONCE_PER_TURN_OCCURRENCE,
    accepts_recovery_handoff=True,
)
