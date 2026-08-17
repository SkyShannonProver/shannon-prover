"""Trigger-first gate for a rejected bounded compound tactic."""

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
from .syntax import compound_prefix_candidates


def _compound_failure_eligibility(
    turn_evidence: CompilerTurnEvidence | None,
) -> FeatureExecutionEligibility:
    if turn_evidence is None:
        return FeatureExecutionEligibility(False, "no_completed_turn")
    if (
        turn_evidence.authority_kind
        != "event_bound_tactic_execution_result"
        or turn_evidence.intent != "commit_tactic"
    ):
        return FeatureExecutionEligibility(False, "unsupported_turn_authority")
    if (
        turn_evidence.outcome_kind not in {"rejected", "no_progress"}
        or turn_evidence.proof_state_effect != "unchanged"
    ):
        return FeatureExecutionEligibility(False, "turn_did_not_fail")
    tactic = turn_evidence.payload.to_dict().get("tactic")
    if not isinstance(tactic, str) or not compound_prefix_candidates(tactic):
        return FeatureExecutionEligibility(
            False, "compound_tactic_not_prefiltered"
        )
    return FeatureExecutionEligibility(
        True,
        "candidate_compound_tactic_failure",
        CURRENT_STATE_FAILURE,
    )


COMPOUND_TACTIC_PREFIX_RECOVERY_EXECUTION_GATE = FeatureExecutionGate(
    gate_id="owned_current_compound_tactic_failure",
    predicate=_compound_failure_eligibility,
    lifetime=ONCE_PER_TURN_OCCURRENCE,
    produces_recovery_handoff=True,
)
