"""Request one native diagnosis for a selected eager-while failure."""

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
from .syntax import is_candidate_eager_while


TACTIC_DIALECT_REPAIR_NATIVE_PRODUCER_ID = (
    "tactic_dialect_repair.eager_while.native_diagnostic"
)


def plan_native_eager_while_attempt(
    proof_ir: ProofIR,
    _coordinate: ProofCoordinate,
    invocation: CompilerInvocationContext,
    _budget: NativePlanningBudget,
) -> NativeSemanticRequestProduction:
    failure = invocation.failure_observation
    if failure is None or invocation.state_ref != proof_ir.state_ref:
        return NativeSemanticRequestProduction.not_applicable(
            TACTIC_DIALECT_REPAIR_NATIVE_PRODUCER_ID
        )
    tactic = str(failure.payload.to_dict().get("tactic") or "").strip()
    if not is_candidate_eager_while(tactic):
        return NativeSemanticRequestProduction.not_applicable(
            TACTIC_DIALECT_REPAIR_NATIVE_PRODUCER_ID
        )
    digest = hashlib.sha256(
        (failure.occurrence_identity + "\0" + tactic).encode("utf-8")
    ).hexdigest()[:20]
    return NativeSemanticRequestProduction.ready(
        TACTIC_DIALECT_REPAIR_NATIVE_PRODUCER_ID,
        (NativeSemanticRequest(
            state_ref=proof_ir.state_ref,
            request_id=f"eager-while-dialect:{digest}",
            producer_id=TACTIC_DIALECT_REPAIR_NATIVE_PRODUCER_ID,
            query=NativeAttemptDiagnosticQuery(
                rejected_tactic=tactic,
                observed_outcome_kind=failure.outcome_kind,
            ),
            evidence_refs=(failure.evidence_ref,),
        ),),
    )
