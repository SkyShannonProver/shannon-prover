"""Native diagnosis request for one exact failed rewrite commitment."""

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
from .syntax import selected_plain_rewrite


PURE_TAIL_REWRITE_NATIVE_PRODUCER_ID = (
    "pure_tail_recovery.rewrite_target.native_diagnostic"
)


def plan_native_pure_tail_rewrite_attempt(
    proof_ir: ProofIR,
    _coordinate: ProofCoordinate,
    invocation: CompilerInvocationContext,
    _budget: NativePlanningBudget,
) -> NativeSemanticRequestProduction:
    failure = invocation.failure_observation
    if failure is None or invocation.state_ref != proof_ir.state_ref:
        return NativeSemanticRequestProduction.not_applicable(
            PURE_TAIL_REWRITE_NATIVE_PRODUCER_ID
        )
    tactic = str(failure.payload.to_dict().get("tactic") or "").strip()
    if selected_plain_rewrite(tactic) is None:
        return NativeSemanticRequestProduction.not_applicable(
            PURE_TAIL_REWRITE_NATIVE_PRODUCER_ID
        )
    digest = hashlib.sha256(
        (failure.occurrence_identity + "\0" + tactic).encode("utf-8")
    ).hexdigest()[:20]
    return NativeSemanticRequestProduction.ready(
        PURE_TAIL_REWRITE_NATIVE_PRODUCER_ID,
        (NativeSemanticRequest(
            state_ref=proof_ir.state_ref,
            request_id=f"pure-tail-rewrite-attempt:{digest}",
            producer_id=PURE_TAIL_REWRITE_NATIVE_PRODUCER_ID,
            query=NativeAttemptDiagnosticQuery(
                rejected_tactic=tactic,
                observed_outcome_kind=failure.outcome_kind,
            ),
            evidence_refs=(failure.evidence_ref,),
        ),),
    )
