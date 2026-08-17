"""Native diagnosis request for one exact failed intro-pattern attempt."""

from __future__ import annotations

import hashlib

from core.easycrypt.proof_state_compiler.contracts import (
    CompilerInvocationContext,
    NativeAttemptDiagnosticQuery,
    NativePlanningBudget,
    NativeSemanticRequest,
    NativeSemanticRequestProduction,
    ProofCoordinate,
    ProofIR,
)
from .syntax import is_nested_intro_pattern_candidate


INTRO_PATTERN_NATIVE_PRODUCER_ID = (
    "intro_pattern_repair.native_diagnostic"
)


def plan_native_intro_pattern_attempt(
    proof_ir: ProofIR,
    _coordinate: ProofCoordinate,
    invocation: CompilerInvocationContext,
    _budget: NativePlanningBudget,
) -> NativeSemanticRequestProduction:
    failure = invocation.failure_observation
    if failure is None or invocation.state_ref != proof_ir.state_ref:
        return NativeSemanticRequestProduction.not_applicable(
            INTRO_PATTERN_NATIVE_PRODUCER_ID
        )
    tactic = str(failure.payload.to_dict().get("tactic") or "").strip()
    if not is_nested_intro_pattern_candidate(tactic):
        return NativeSemanticRequestProduction.not_applicable(
            INTRO_PATTERN_NATIVE_PRODUCER_ID
        )
    digest = hashlib.sha256(
        (failure.occurrence_identity + "\0" + tactic).encode("utf-8")
    ).hexdigest()[:20]
    return NativeSemanticRequestProduction.ready(
        INTRO_PATTERN_NATIVE_PRODUCER_ID,
        (NativeSemanticRequest(
            state_ref=proof_ir.state_ref,
            request_id=f"intro-pattern-attempt:{digest}",
            producer_id=INTRO_PATTERN_NATIVE_PRODUCER_ID,
            query=NativeAttemptDiagnosticQuery(
                rejected_tactic=tactic,
                observed_outcome_kind=failure.outcome_kind,
            ),
            evidence_refs=(failure.evidence_ref,),
        ),),
    )
