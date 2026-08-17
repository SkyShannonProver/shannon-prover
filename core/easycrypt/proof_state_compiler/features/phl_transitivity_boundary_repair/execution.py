"""Trigger-first gate for one exact failed PHL transitivity occurrence."""

from core.easycrypt.proof_state_compiler.contracts import (
    CURRENT_STATE_FAILURE,
    CompilerTurnEvidence,
)
from core.easycrypt.proof_state_compiler.features.execution import (
    FeatureExecutionEligibility,
    FeatureExecutionGate,
    ONCE_PER_TURN_OCCURRENCE,
)
from .syntax import is_candidate_phl_transitivity


def _eligibility(
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
    if not isinstance(tactic, str) or not is_candidate_phl_transitivity(tactic):
        return FeatureExecutionEligibility(False, "phl_transitivity_not_prefiltered")
    return FeatureExecutionEligibility(
        True,
        "candidate_phl_transitivity_boundary_failure",
        CURRENT_STATE_FAILURE,
    )


PHL_TRANSITIVITY_BOUNDARY_EXECUTION_GATE = FeatureExecutionGate(
    gate_id="owned_current_phl_transitivity_boundary_failure",
    predicate=_eligibility,
    lifetime=ONCE_PER_TURN_OCCURRENCE,
    accepts_recovery_handoff=True,
)
