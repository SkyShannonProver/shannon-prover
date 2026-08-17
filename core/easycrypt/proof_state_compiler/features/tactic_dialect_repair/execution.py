"""Trigger-first gate for one exact selected eager-while failure."""

from core.easycrypt.proof_state_compiler.contracts import (
    CURRENT_STATE_FAILURE,
    CompilerTurnEvidence,
)
from core.easycrypt.proof_state_compiler.features.execution import (
    FeatureExecutionEligibility,
    FeatureExecutionGate,
    ONCE_PER_TURN_OCCURRENCE,
)
from .syntax import is_candidate_eager_while


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
    if not isinstance(tactic, str) or not is_candidate_eager_while(tactic):
        return FeatureExecutionEligibility(False, "eager_while_not_prefiltered")
    return FeatureExecutionEligibility(
        True,
        "candidate_selected_eager_while_failure",
        CURRENT_STATE_FAILURE,
    )


TACTIC_DIALECT_REPAIR_EXECUTION_GATE = FeatureExecutionGate(
    gate_id="owned_current_tactic_dialect_failure",
    predicate=_eligibility,
    lifetime=ONCE_PER_TURN_OCCURRENCE,
    accepts_recovery_handoff=True,
)
