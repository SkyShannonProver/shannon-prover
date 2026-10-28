"""Shared scaffolding for recovery slices triggered by one failed commit.

A recovery slice runs only after the agent's ``commit_tactic`` was rejected
or made no progress and left the proof state unchanged.  Most slices then
ask EasyCrypt to diagnose that exact rejected tactic.  Each slice supplies
only what is its own: a cheap lexical prefilter, its stable identities, and
its audit reasons.
"""

from __future__ import annotations

import hashlib
from typing import Callable

from core.easycrypt.proof_state_compiler.contracts import (
    CURRENT_STATE_FAILURE,
    CompilerInvocationContext,
    CompilerTurnEvidence,
    NativeAttemptDiagnosticQuery,
    NativePlanningBudget,
    NativeSemanticRequest,
    NativeSemanticRequestProduction,
    ProofCoordinate,
    ProofIR,
)
from core.easycrypt.proof_state_compiler.features.execution import (
    FeatureExecutionEligibility,
    FeatureExecutionGate,
    ONCE_PER_TURN_OCCURRENCE,
)


TacticPrefilter = Callable[[str], bool]


def failed_commit_gate(
    *,
    gate_id: str,
    prefilter: TacticPrefilter,
    not_prefiltered_reason: str,
    eligible_reason: str,
    missing_tactic_reason: str = "",
    produces_recovery_handoff: bool = False,
    accepts_recovery_handoff: bool = False,
) -> FeatureExecutionGate:
    """Run once per failed-commit occurrence whose tactic passes ``prefilter``.

    With ``missing_tactic_reason``, a missing or blank tactic is reported
    under that reason before the prefilter runs.
    """

    def eligibility(
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
        if missing_tactic_reason and (
            not isinstance(tactic, str) or not tactic.strip()
        ):
            return FeatureExecutionEligibility(False, missing_tactic_reason)
        if not isinstance(tactic, str) or not prefilter(tactic):
            return FeatureExecutionEligibility(False, not_prefiltered_reason)
        return FeatureExecutionEligibility(
            True, eligible_reason, CURRENT_STATE_FAILURE
        )

    return FeatureExecutionGate(
        gate_id=gate_id,
        predicate=eligibility,
        lifetime=ONCE_PER_TURN_OCCURRENCE,
        produces_recovery_handoff=produces_recovery_handoff,
        accepts_recovery_handoff=accepts_recovery_handoff,
    )


NativeAttemptProducer = Callable[
    [ProofIR, ProofCoordinate, CompilerInvocationContext, NativePlanningBudget],
    NativeSemanticRequestProduction,
]


def attempt_diagnostic_producer(
    *,
    producer_id: str,
    request_prefix: str,
    prefilter: TacticPrefilter,
) -> NativeAttemptProducer:
    """Ask EasyCrypt to diagnose the exact rejected tactic, nothing else."""

    def plan(
        proof_ir: ProofIR,
        _coordinate: ProofCoordinate,
        invocation: CompilerInvocationContext,
        _budget: NativePlanningBudget,
    ) -> NativeSemanticRequestProduction:
        failure = invocation.failure_observation
        if failure is None or invocation.state_ref != proof_ir.state_ref:
            return NativeSemanticRequestProduction.not_applicable(producer_id)
        tactic = str(failure.payload.to_dict().get("tactic") or "").strip()
        if not prefilter(tactic):
            return NativeSemanticRequestProduction.not_applicable(producer_id)
        digest = hashlib.sha256(
            (failure.occurrence_identity + "\0" + tactic).encode("utf-8")
        ).hexdigest()[:20]
        return NativeSemanticRequestProduction.ready(
            producer_id,
            (NativeSemanticRequest(
                state_ref=proof_ir.state_ref,
                request_id=f"{request_prefix}:{digest}",
                producer_id=producer_id,
                query=NativeAttemptDiagnosticQuery(
                    rejected_tactic=tactic,
                    observed_outcome_kind=failure.outcome_kind,
                ),
                evidence_refs=(failure.evidence_ref,),
            ),),
        )

    return plan
