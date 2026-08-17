"""One native query over the complete bounded prefix population."""

from __future__ import annotations

import hashlib

from core.easycrypt.proof_state_compiler.contracts import (
    CompilerInvocationContext,
    NativePlanningBudget,
    NativeSemanticRequest,
    NativeSemanticRequestProduction,
    NativeTacticPrefixDiagnosticQuery,
    ProofCoordinate,
    ProofIR,
)
from .syntax import compound_prefix_candidates


COMPOUND_PREFIX_NATIVE_PRODUCER_ID = (
    "compound_tactic_prefix_recovery.native_diagnostic"
)


def plan_native_compound_prefix_attempt(
    proof_ir: ProofIR,
    _coordinate: ProofCoordinate,
    invocation: CompilerInvocationContext,
    _budget: NativePlanningBudget,
) -> NativeSemanticRequestProduction:
    failure = invocation.failure_observation
    if (
        failure is None
        or failure.outcome_kind not in {"rejected", "no_progress"}
        or invocation.state_ref != proof_ir.state_ref
    ):
        return NativeSemanticRequestProduction.not_applicable(
            COMPOUND_PREFIX_NATIVE_PRODUCER_ID
        )
    tactic = str(failure.payload.to_dict().get("tactic") or "").strip()
    candidates = compound_prefix_candidates(tactic)
    if not candidates:
        return NativeSemanticRequestProduction.not_applicable(
            COMPOUND_PREFIX_NATIVE_PRODUCER_ID
        )
    digest = hashlib.sha256(
        (failure.occurrence_identity + "\0" + tactic).encode("utf-8")
    ).hexdigest()[:20]
    return NativeSemanticRequestProduction.ready(
        COMPOUND_PREFIX_NATIVE_PRODUCER_ID,
        (NativeSemanticRequest(
            state_ref=proof_ir.state_ref,
            request_id=f"compound-prefix-attempt:{digest}",
            producer_id=COMPOUND_PREFIX_NATIVE_PRODUCER_ID,
            query=NativeTacticPrefixDiagnosticQuery(
                rejected_tactic=tactic,
                candidate_prefixes=candidates,
            ),
            evidence_refs=(failure.evidence_ref,),
        ),),
        considered_candidate_count=len(candidates),
    )
