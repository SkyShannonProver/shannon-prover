"""Native-backed B2 losslessness module/proof-slot repair family.

Python declaration parsing and procedure unification only enumerate one
bounded source spelling.  EasyCrypt owns the resolved theorem head, argument
kinds, module identity, residual premise, and result procedure.  The explicit
``_`` in the requested proof term is intentional: it asks EasyCrypt to expose
the proof premise as a typed residual obligation instead of leaving an
implication for Shannon to decompose.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from core.easycrypt.proof_state_compiler.contracts import (
    CompilerInvocationContext,
    EvidenceRef,
    NativePlanningBudget,
    NativeProofTermElaborationQuery,
    NativeSemanticRequest,
    NativeSemanticRequestProduction,
    ProofCoordinate,
    ProofIR,
    ProofResource,
)
from core.easycrypt.proof_state_compiler.features.operation_binding_repair.contracts import (
    OPERATION_BINDING_REPAIR_ANALYSIS_PRODUCER_ID,
)
from core.easycrypt.proof_state_compiler.features.operation_binding_repair.classification import (
    classify_operation_binding_failure,
)
from core.easycrypt.proof_state_compiler.middle_end.contributions import (
    AnalysisContribution,
)
from core.easycrypt.proof_state_compiler.middle_end.native_application import (
    native_application_contribution,
    single_module_losslessness_direct_application_matches,
)
from core.easycrypt.proof_state_compiler.middle_end.procedure_binding import (
    bind_procedure_resource,
)
from core.easycrypt.proof_state_compiler.syntax.attempted_operation import (
    bare_operation_resource,
)
from core.easycrypt.proof_state_compiler.syntax.module_terms import (
    lexical_procedure_views,
)


LOSSLESSNESS_MODULE_REPAIR_NATIVE_PRODUCER_ID = (
    "operation_binding_repair.losslessness_module.native_elaboration"
)


@dataclass(frozen=True)
class LosslessnessModuleRepairSketch:
    """One non-authoritative source spelling awaiting native elaboration."""

    resource: ProofResource
    target_procedure: str
    application_term: str
    evidence_refs: tuple[EvidenceRef, ...]

    def __post_init__(self) -> None:
        if not self.target_procedure or not self.application_term:
            raise ValueError("B2 losslessness repair sketch is incomplete")
        if not self.evidence_refs:
            raise ValueError("B2 losslessness repair sketch requires evidence")


def plan_native_losslessness_module_repair(
    proof_ir: ProofIR,
    _coordinate: ProofCoordinate,
    invocation: CompilerInvocationContext,
    _budget: NativePlanningBudget,
) -> NativeSemanticRequestProduction:
    """Request one native descriptor after one exact B2 candidate remains."""

    if invocation.state_ref != proof_ir.state_ref:
        raise ValueError("B2 native request planning crossed StateRef")
    sketch = discover_unique_losslessness_module_repair(proof_ir)
    if sketch is None:
        return NativeSemanticRequestProduction.not_applicable(
            LOSSLESSNESS_MODULE_REPAIR_NATIVE_PRODUCER_ID
        )
    digest = hashlib.sha256(
        (
            sketch.resource.resource_id
            + "\0"
            + sketch.target_procedure
            + "\0apply\0"
            + sketch.application_term
        ).encode("utf-8")
    ).hexdigest()[:20]
    request = NativeSemanticRequest(
        state_ref=proof_ir.state_ref,
        request_id=f"operation-binding-b2-losslessness:{digest}",
        producer_id=LOSSLESSNESS_MODULE_REPAIR_NATIVE_PRODUCER_ID,
        query=NativeProofTermElaborationQuery(
            operation="apply",
            application_term=sketch.application_term,
        ),
        evidence_refs=sketch.evidence_refs,
    )
    return NativeSemanticRequestProduction.ready(
        LOSSLESSNESS_MODULE_REPAIR_NATIVE_PRODUCER_ID, (request,)
    )


def discover_unique_losslessness_module_repair(
    proof_ir: ProofIR,
) -> LosslessnessModuleRepairSketch | None:
    """Enumerate one same-resource B2 spelling without semantic authority."""

    attempted = proof_ir.attempted_operation
    target_procedure = _native_standalone_losslessness_target(proof_ir)
    if (
        attempted is None
        or classify_operation_binding_failure(attempted) != "B2"
        or attempted.operation != "apply"
        or bare_operation_resource(attempted.rejected_tactic)
        != ("apply", attempted.resource)
        or not target_procedure
    ):
        return None

    sketches: list[LosslessnessModuleRepairSketch] = []
    for resource in proof_ir.resources:
        if not _is_single_module_losslessness_resource(
            resource,
            attempted_resource=attempted.resource,
        ):
            continue
        module_slot = next(
            slot
            for slot in resource.application_signature.slots
            if slot.kind == "module"
        )
        candidates: set[str] = set()
        for target_view in lexical_procedure_views(target_procedure):
            bound = bind_procedure_resource(
                conclusion_procedure=resource.conclusion.procedure,
                target_procedure=target_view,
                module_parameters=(module_slot.name,),
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
            attempted.evidence_refs
            + resource.evidence_refs
            + proof_ir.goal.evidence_refs
        ))
        sketches.append(LosslessnessModuleRepairSketch(
            resource=resource,
            target_procedure=target_procedure,
            application_term=next(iter(candidates)),
            evidence_refs=evidence,
        ))
    return sketches[0] if len(sketches) == 1 else None


def analyze_native_losslessness_module_repair(
    proof_ir: ProofIR,
    coordinate: ProofCoordinate,
    invocation: CompilerInvocationContext,
) -> AnalysisContribution:
    """Admit one B2 binding only from its exact accepted native descriptor."""

    sketch = discover_unique_losslessness_module_repair(proof_ir)
    requests = plan_native_losslessness_module_repair(
        proof_ir,
        coordinate,
        invocation,
        NativePlanningBudget(),
    ).requests
    if sketch is None or len(requests) != 1:
        return AnalysisContribution()
    request = requests[0]
    observations = tuple(
        item
        for item in proof_ir.native_semantic_observations
        if item.producer_id == LOSSLESSNESS_MODULE_REPAIR_NATIVE_PRODUCER_ID
        and item.request_id == request.request_id
    )
    if (
        len(observations) != 1
        or observations[0].status != "accepted"
        or observations[0].descriptor is None
    ):
        return AnalysisContribution()
    observation = observations[0]
    descriptor = observation.descriptor
    if not single_module_losslessness_direct_application_matches(
        descriptor,
        resource_symbol=sketch.resource.symbol,
        target_procedure=sketch.target_procedure,
    ):
        return AnalysisContribution()
    return native_application_contribution(
        resource=sketch.resource,
        observation=observation,
        producer_id=OPERATION_BINDING_REPAIR_ANALYSIS_PRODUCER_ID,
        identity_namespace="native-b2-losslessness",
        evidence_refs=sketch.evidence_refs,
        trigger_id=proof_ir.attempted_operation.trigger_id,
    )


def _native_standalone_losslessness_target(proof_ir: ProofIR) -> str:
    """Read the target only from the native bounded-hoare function formula."""

    goal = proof_ir.goal
    formula = goal.formula_ir
    if (
        goal.status != "known"
        or goal.kind != "phoare"
        or goal.bound_relation != "="
        or goal.bound_value != "1%r"
        or goal.precondition != "true"
        or goal.postcondition != "true"
        or proof_ir.statements
        or formula is None
        or formula.kind != "bounded_hoare_function"
        or formula.properties.get("lossless") is not True
    ):
        return ""
    procedure = formula.properties.get("procedure")
    return procedure if type(procedure) is str and procedure else ""


def _is_single_module_losslessness_resource(
    resource: ProofResource,
    *,
    attempted_resource: str,
) -> bool:
    slots = resource.application_signature.slots
    return (
        resource.symbol == attempted_resource
        and resource.resource_kind == "procedure_certificate"
        and resource.conclusion.kind == "lossless"
        and len(resource.premises) == 1
        and resource.premises[0].kind == "lossless"
        and len(slots) == 2
        and sum(slot.kind == "module" for slot in slots) == 1
        and sum(slot.kind == "proof" for slot in slots) == 1
    )
