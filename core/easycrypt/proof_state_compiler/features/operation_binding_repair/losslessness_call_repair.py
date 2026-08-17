"""Native-backed B2 repair for one bounded losslessness ``call``.

This is a semantic family of ``operation_binding_repair``, not a second
recovery feature.  Shared P2 owns the rejected operation, the feature-specific
``operation_binding_repair_once`` policy owns delivery, and EasyCrypt owns the
native attempt diagnosis and proof-term elaboration.  Python only bounds one
exact same-resource spelling with one module and one or two deferred proof
premises.
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
from core.easycrypt.proof_state_compiler.features.operation_binding_repair.classification import (
    classify_operation_binding_failure,
)
from core.easycrypt.proof_state_compiler.features.operation_binding_repair.contracts import (
    OPERATION_BINDING_REPAIR_ANALYSIS_PRODUCER_ID,
)
from core.easycrypt.proof_state_compiler.middle_end.contributions import (
    AnalysisContribution,
)
from core.easycrypt.proof_state_compiler.middle_end.native_application import (
    module_losslessness_certificate_matches,
    native_application_contribution,
)
from core.easycrypt.proof_state_compiler.middle_end.procedure_binding import (
    bind_procedure_resource,
)
from core.easycrypt.proof_state_compiler.syntax.module_terms import (
    lexical_procedure_views,
)


LOSSLESSNESS_CALL_REPAIR_NATIVE_PRODUCER_ID = (
    "operation_binding_repair.losslessness_call.native_elaboration"
)


@dataclass(frozen=True)
class LosslessnessCallRepairSketch:
    """One bounded same-resource spelling awaiting EasyCrypt authority."""

    resource: ProofResource
    target_procedure: str
    module_term: str
    application_term: str
    proof_premise_count: int
    premise_procedures: tuple[str, ...]
    evidence_refs: tuple[EvidenceRef, ...]

    def __post_init__(self) -> None:
        if not all((
            self.target_procedure,
            self.module_term,
            self.application_term,
            self.proof_premise_count,
            self.premise_procedures,
            self.evidence_refs,
        )):
            raise ValueError("losslessness call repair sketch is incomplete")
        if self.proof_premise_count not in {1, 2}:
            raise ValueError("losslessness call premise count is out of bounds")


def plan_native_losslessness_call_repair(
    proof_ir: ProofIR,
    coordinate: ProofCoordinate,
    invocation: CompilerInvocationContext,
    _budget: NativePlanningBudget,
) -> NativeSemanticRequestProduction:
    """Request one native descriptor after one exact B2 call remains."""

    if invocation.state_ref != proof_ir.state_ref:
        raise ValueError("losslessness call repair planning crossed StateRef")
    sketch = discover_unique_losslessness_call_repair(proof_ir, coordinate)
    if sketch is None:
        return NativeSemanticRequestProduction.not_applicable(
            LOSSLESSNESS_CALL_REPAIR_NATIVE_PRODUCER_ID
        )
    digest = hashlib.sha256(
        (
            sketch.resource.resource_id
            + "\0"
            + sketch.target_procedure
            + "\0"
            + sketch.application_term
        ).encode("utf-8")
    ).hexdigest()[:20]
    request = NativeSemanticRequest(
        state_ref=proof_ir.state_ref,
        request_id=f"operation-binding-losslessness-call:{digest}",
        producer_id=LOSSLESSNESS_CALL_REPAIR_NATIVE_PRODUCER_ID,
        query=NativeProofTermElaborationQuery(
            operation="call",
            application_term=sketch.application_term,
        ),
        evidence_refs=sketch.evidence_refs,
    )
    return NativeSemanticRequestProduction.ready(
        LOSSLESSNESS_CALL_REPAIR_NATIVE_PRODUCER_ID,
        (request,),
    )


def discover_unique_losslessness_call_repair(
    proof_ir: ProofIR,
    coordinate: ProofCoordinate,
) -> LosslessnessCallRepairSketch | None:
    """Enumerate one bounded placeholder-only call without semantic authority."""

    attempted = proof_ir.attempted_operation
    active = coordinate.tactic_active_boundary
    if (
        attempted is None
        or classify_operation_binding_failure(attempted) != "B2"
        or attempted.operation != "call"
        or attempted.application_syntax_repair_descriptor is not None
        or any(item != "hole" for item in attempted.parsed_arguments)
        or bool(attempted.side)
        or bool(attempted.positions)
        or not _is_losslessness_goal(proof_ir)
        or coordinate.status != "known"
        or active is None
        or active.kind != "call"
    ):
        return None
    sketches: list[LosslessnessCallRepairSketch] = []
    for resource in proof_ir.resources:
        if not _is_selected_bounded_module_certificate(
            resource,
            attempted.exact_resource,
        ):
            continue
        module_slot = next(
            slot
            for slot in resource.application_signature.slots
            if slot.kind == "module"
        )
        candidates: set[tuple[str, str, tuple[str, ...]]] = set()
        proof_premise_count = len(resource.premises)
        if len(attempted.parsed_arguments) > proof_premise_count + 1:
            continue
        for target_view in lexical_procedure_views(active.procedure):
            bound = bind_procedure_resource(
                conclusion_procedure=resource.conclusion.procedure,
                target_procedure=target_view,
                module_parameters=(module_slot.name,),
                premise_procedures=tuple(
                    premise.procedure for premise in resource.premises
                ),
            )
            if bound is None or len(bound.resolved_modules) != 1:
                continue
            module_term = bound.resolved_modules[0][1]
            candidates.add((
                module_term,
                " ".join((
                    resource.symbol,
                    f"(<: {module_term})",
                    *("_" for _item in resource.premises),
                )),
                bound.instantiated_premises,
            ))
        if len(candidates) != 1:
            continue
        module_term, application_term, premise_procedures = next(
            iter(candidates)
        )
        evidence = tuple(dict.fromkeys(
            attempted.evidence_refs
            + resource.evidence_refs
            + proof_ir.goal.evidence_refs
            + active.evidence_refs
        ))
        sketches.append(LosslessnessCallRepairSketch(
            resource=resource,
            target_procedure=active.procedure,
            module_term=module_term,
            application_term=application_term,
            proof_premise_count=proof_premise_count,
            premise_procedures=premise_procedures,
            evidence_refs=evidence,
        ))
    return sketches[0] if len(sketches) == 1 else None


def analyze_native_losslessness_call_repair(
    proof_ir: ProofIR,
    coordinate: ProofCoordinate,
    invocation: CompilerInvocationContext,
) -> AnalysisContribution:
    """Admit one call repair only from its exact native descriptor."""

    sketch = discover_unique_losslessness_call_repair(proof_ir, coordinate)
    requests = plan_native_losslessness_call_repair(
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
        if item.producer_id == LOSSLESSNESS_CALL_REPAIR_NATIVE_PRODUCER_ID
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
    if not module_losslessness_certificate_matches(
        descriptor,
        resource_symbol=sketch.resource.symbol,
        target_procedure=sketch.target_procedure,
        proof_premise_count=sketch.proof_premise_count,
        expected_premise_procedures=sketch.premise_procedures,
    ):
        return AnalysisContribution()
    return native_application_contribution(
        resource=sketch.resource,
        observation=observation,
        producer_id=OPERATION_BINDING_REPAIR_ANALYSIS_PRODUCER_ID,
        identity_namespace="native-b2-losslessness-call",
        evidence_refs=sketch.evidence_refs,
        trigger_id=proof_ir.attempted_operation.trigger_id,
    )


def _is_losslessness_goal(proof_ir: ProofIR) -> bool:
    goal = proof_ir.goal
    return (
        goal.status == "known"
        and goal.kind == "phoare"
        and goal.bound_relation == "="
        and goal.bound_value == "1%r"
        and goal.precondition == "true"
        and goal.postcondition == "true"
    )


def _is_selected_bounded_module_certificate(
    resource: ProofResource,
    selected: str,
) -> bool:
    slots = resource.application_signature.slots
    proof_premise_count = len(resource.premises)
    return (
        resource.symbol == selected
        and resource.resource_kind == "procedure_certificate"
        and resource.conclusion.kind == "lossless"
        and proof_premise_count in {1, 2}
        and all(item.kind == "lossless" for item in resource.premises)
        and len(slots) == proof_premise_count + 1
        and slots[0].kind == "module"
        and all(slot.kind == "proof" for slot in slots[1:])
    )
