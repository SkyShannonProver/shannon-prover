"""Native request that establishes the failed operation before B1/B2/B4."""

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
from core.easycrypt.proof_state_compiler.syntax.attempted_operation import (
    operation_resource,
)


OPERATION_BINDING_ATTEMPT_NATIVE_PRODUCER_ID = (
    "operation_binding_repair.attempt.native_diagnostic"
)


def plan_native_operation_binding_attempt(
    proof_ir: ProofIR,
    _coordinate: ProofCoordinate,
    invocation: CompilerInvocationContext,
    _budget: NativePlanningBudget,
) -> NativeSemanticRequestProduction:
    failure = invocation.failure_observation
    if failure is None or invocation.state_ref != proof_ir.state_ref:
        return NativeSemanticRequestProduction.not_applicable(
            OPERATION_BINDING_ATTEMPT_NATIVE_PRODUCER_ID
        )
    tactic = str(failure.payload.to_dict().get("tactic") or "").strip()
    # This is only a work-avoidance prefilter. Native EasyCrypt owns the parse
    # and semantic failure kind consumed by the B1/B2/B4 classifier.
    if operation_resource(tactic) is None:
        return NativeSemanticRequestProduction.not_applicable(
            OPERATION_BINDING_ATTEMPT_NATIVE_PRODUCER_ID
        )
    digest = hashlib.sha256(
        (failure.occurrence_identity + "\0" + tactic).encode("utf-8")
    ).hexdigest()[:20]
    request = NativeSemanticRequest(
        state_ref=proof_ir.state_ref,
        request_id=f"operation-binding-attempt:{digest}",
        producer_id=OPERATION_BINDING_ATTEMPT_NATIVE_PRODUCER_ID,
        query=NativeAttemptDiagnosticQuery(
            rejected_tactic=tactic,
            observed_outcome_kind=failure.outcome_kind,
        ),
        evidence_refs=(failure.evidence_ref,),
    )
    return NativeSemanticRequestProduction.ready(
        OPERATION_BINDING_ATTEMPT_NATIVE_PRODUCER_ID, (request,)
    )
