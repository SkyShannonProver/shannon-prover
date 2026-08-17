"""Request native parsing and boundary diagnosis for one failed occurrence."""

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
from .syntax import is_candidate_phl_transitivity


PHL_TRANSITIVITY_BOUNDARY_NATIVE_PRODUCER_ID = (
    "phl_transitivity_boundary_repair.attempt.native_diagnostic"
)


def plan_native_phl_transitivity_attempt(
    proof_ir: ProofIR,
    _coordinate: ProofCoordinate,
    invocation: CompilerInvocationContext,
    _budget: NativePlanningBudget,
) -> NativeSemanticRequestProduction:
    failure = invocation.failure_observation
    if failure is None or invocation.state_ref != proof_ir.state_ref:
        return NativeSemanticRequestProduction.not_applicable(
            PHL_TRANSITIVITY_BOUNDARY_NATIVE_PRODUCER_ID
        )
    tactic = str(failure.payload.to_dict().get("tactic") or "").strip()
    if not is_candidate_phl_transitivity(tactic):
        return NativeSemanticRequestProduction.not_applicable(
            PHL_TRANSITIVITY_BOUNDARY_NATIVE_PRODUCER_ID
        )
    digest = hashlib.sha256(
        (failure.occurrence_identity + "\0" + tactic).encode("utf-8")
    ).hexdigest()[:20]
    return NativeSemanticRequestProduction.ready(
        PHL_TRANSITIVITY_BOUNDARY_NATIVE_PRODUCER_ID,
        (NativeSemanticRequest(
            state_ref=proof_ir.state_ref,
            request_id=f"phl-transitivity-boundary:{digest}",
            producer_id=PHL_TRANSITIVITY_BOUNDARY_NATIVE_PRODUCER_ID,
            query=NativeAttemptDiagnosticQuery(
                rejected_tactic=tactic,
                observed_outcome_kind=failure.outcome_kind,
            ),
            evidence_refs=(failure.evidence_ref,),
        ),),
    )
