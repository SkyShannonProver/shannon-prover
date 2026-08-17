"""Bounded, non-authoritative candidate planning for frozen M05."""

from __future__ import annotations

import hashlib

from core.easycrypt.proof_state_compiler.contracts import (
    CompilerInvocationContext,
    NativePlanningBudget,
    NativeProofTermElaborationQuery,
    NativeSemanticRequest,
    NativeSemanticRequestProduction,
    ProofCoordinate,
    ProofIR,
)
from core.easycrypt.proof_state_compiler.features.losslessness_certificate_application.contracts import (
    LOSSLESSNESS_CERTIFICATE_NATIVE_PRODUCER_ID,
    LosslessnessApplicationSketch,
)
from core.easycrypt.proof_state_compiler.middle_end.procedure_binding import (
    bind_procedure_resource,
)
from core.easycrypt.proof_state_compiler.syntax.module_terms import (
    lexical_procedure_views,
)


def plan_losslessness_native_application(
    proof_ir: ProofIR,
    coordinate: ProofCoordinate,
    invocation: CompilerInvocationContext,
    _budget: NativePlanningBudget,
) -> NativeSemanticRequestProduction:
    """Request one exact native elaboration only after unique bounded planning."""

    if invocation.state_ref != proof_ir.state_ref:
        raise ValueError("M05 native request planning crossed StateRef")
    sketch = discover_unique_losslessness_application(proof_ir, coordinate)
    if sketch is None:
        return NativeSemanticRequestProduction.not_applicable(
            LOSSLESSNESS_CERTIFICATE_NATIVE_PRODUCER_ID
        )
    digest = hashlib.sha256(
        (
            sketch.resource.resource_id
            + "\0"
            + sketch.target_procedure
            + "\0"
            + sketch.application_term
        ).encode()
    ).hexdigest()[:20]
    request = NativeSemanticRequest(
        state_ref=proof_ir.state_ref,
        request_id=f"m05.losslessness.{digest}",
        producer_id=LOSSLESSNESS_CERTIFICATE_NATIVE_PRODUCER_ID,
        query=NativeProofTermElaborationQuery(
            operation="call",
            application_term=sketch.application_term,
        ),
        evidence_refs=sketch.evidence_refs,
    )
    return NativeSemanticRequestProduction.ready(
        LOSSLESSNESS_CERTIFICATE_NATIVE_PRODUCER_ID, (request,)
    )


def discover_unique_losslessness_application(
    proof_ir: ProofIR,
    coordinate: ProofCoordinate,
) -> LosslessnessApplicationSketch | None:
    """Return one lexical application sketch, or abstain on any ambiguity.

    Declaration parsing and structural unification only bound the native query.
    They do not authorize the theorem head, slot kinds, module value, residual
    premise, or result procedure.
    """

    active = coordinate.tactic_active_boundary
    if (
        not _is_frozen_m05_goal(proof_ir)
        or coordinate.status != "known"
        or active is None
        or active.kind != "call"
    ):
        return None
    sketches: list[LosslessnessApplicationSketch] = []
    for resource in proof_ir.resources:
        if (
            resource.resource_kind != "procedure_certificate"
            or resource.conclusion.kind != "lossless"
            or len(resource.premises) != 1
            or resource.premises[0].kind != "lossless"
        ):
            continue
        module_slots = tuple(
            slot
            for slot in resource.application_signature.slots
            if slot.kind == "module"
        )
        proof_slots = tuple(
            slot
            for slot in resource.application_signature.slots
            if slot.kind == "proof"
        )
        if (
            len(module_slots) != 1
            or len(proof_slots) != 1
            or len(resource.application_signature.slots) != 2
        ):
            continue
        candidates = set()
        for target_view in lexical_procedure_views(active.procedure):
            bound = bind_procedure_resource(
                conclusion_procedure=resource.conclusion.procedure,
                target_procedure=target_view,
                module_parameters=(module_slots[0].name,),
                premise_procedures=(resource.premises[0].procedure,),
            )
            if bound is None or len(bound.resolved_modules) != 1:
                continue
            candidates.add(
                f"{resource.symbol} (<: {bound.resolved_modules[0][1]}) _"
            )
        if len(candidates) != 1:
            continue
        evidence = tuple(dict.fromkeys(
            resource.evidence_refs
            + proof_ir.goal.evidence_refs
            + active.evidence_refs
        ))
        sketches.append(LosslessnessApplicationSketch(
            resource=resource,
            target_procedure=active.procedure,
            application_term=next(iter(candidates)),
            evidence_refs=evidence,
        ))
    return sketches[0] if len(sketches) == 1 else None


def _is_frozen_m05_goal(proof_ir: ProofIR) -> bool:
    goal = proof_ir.goal
    return (
        goal.status == "known"
        and goal.kind == "phoare"
        and goal.bound_relation == "="
        and goal.bound_value == "1%r"
        and goal.precondition == "true"
        and goal.postcondition == "true"
    )
