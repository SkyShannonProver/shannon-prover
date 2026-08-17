"""Native-backed B2/B4 probability-theorem multi-slot repair.

The printed declaration and current facts are used only to enumerate one
bounded spelling for the exact theorem the agent already attempted.  EasyCrypt
then owns theorem lookup, argument kinds, module restrictions, formula/proof
matching, holes, residual premises, and the resulting proposition.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from itertools import product

from core.easycrypt.proof_state_compiler.contracts import (
    CompilerInvocationContext,
    EvidenceRef,
    NativePlanningBudget,
    NativeProofTermDescriptor,
    NativeProofTermElaborationQuery,
    NativeSemanticObservation,
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
from core.easycrypt.proof_state_compiler.middle_end.goal_binding_terms import (
    bounded_goal_binding_terms,
)
from core.easycrypt.proof_state_compiler.middle_end.native_application import (
    native_application_contribution,
    resolved_head_matches_resource,
)
from core.easycrypt.proof_state_compiler.middle_end.proof_slot_binding import (
    bind_available_proof_slots,
)
from core.easycrypt.proof_state_compiler.syntax.attempted_operation import (
    bare_operation_resource,
)


PROBABILITY_MULTISLOT_REPAIR_NATIVE_PRODUCER_ID = (
    "operation_binding_repair.probability_multislot.native_elaboration"
)
_MAX_GOAL_MODULE_TERMS = 8
_MAX_GOAL_MEMORY_TERMS = 4


@dataclass(frozen=True)
class ProbabilityMultiSlotRepairSketch:
    """One non-authoritative exact spelling awaiting native elaboration."""

    resource: ProofResource
    application_term: str
    evidence_refs: tuple[EvidenceRef, ...]

    def __post_init__(self) -> None:
        if not self.application_term or not self.evidence_refs:
            raise ValueError("probability multi-slot repair sketch is incomplete")


@dataclass(frozen=True)
class _SketchDiscovery:
    sketches: tuple[ProbabilityMultiSlotRepairSketch, ...]
    considered_candidate_count: int
    exceeded_materialization_budget: bool = False


def plan_native_probability_multislot_repair(
    proof_ir: ProofIR,
    _coordinate: ProofCoordinate,
    invocation: CompilerInvocationContext,
    budget: NativePlanningBudget,
) -> NativeSemanticRequestProduction:
    """Ask EasyCrypt to decide every member of one bounded spelling pool."""

    if invocation.state_ref != proof_ir.state_ref:
        raise ValueError("probability multi-slot planning crossed StateRef")
    discovery = _discover_probability_multislot_repair_sketches(
        proof_ir,
        max_candidates=budget.remaining_consumer_requests,
    )
    if discovery.exceeded_materialization_budget:
        return NativeSemanticRequestProduction.abstained(
            PROBABILITY_MULTISLOT_REPAIR_NATIVE_PRODUCER_ID,
            reason="complete_candidate_pool_exceeds_materialization_budget",
            considered_candidate_count=discovery.considered_candidate_count,
        )
    if not discovery.sketches:
        return NativeSemanticRequestProduction.not_applicable(
            PROBABILITY_MULTISLOT_REPAIR_NATIVE_PRODUCER_ID
        )
    requests = _requests_for_sketches(proof_ir, discovery.sketches)
    return NativeSemanticRequestProduction.ready(
        PROBABILITY_MULTISLOT_REPAIR_NATIVE_PRODUCER_ID,
        requests,
        considered_candidate_count=discovery.considered_candidate_count,
    )


def _discover_probability_multislot_repair_sketches(
    proof_ir: ProofIR,
    *,
    max_candidates: int,
) -> _SketchDiscovery:
    """Enumerate all spellings or report overflow without taking a prefix."""

    attempted = proof_ir.attempted_operation
    goal = proof_ir.goal
    if (
        attempted is None
        or classify_operation_binding_failure(attempted) not in {"B2", "B4"}
        or attempted.operation != "apply"
        or bare_operation_resource(attempted.rejected_tactic)
        != ("apply", attempted.resource)
        or goal.status != "known"
        or goal.kind != "probability"
        or not goal.formula
        or goal.formula_ir is None
    ):
        return _SketchDiscovery((), 0)

    term_pool = bounded_goal_binding_terms(
        goal,
        max_module_terms=_MAX_GOAL_MODULE_TERMS,
        max_memory_terms=_MAX_GOAL_MEMORY_TERMS,
    )
    if term_pool is None:
        return _SketchDiscovery((), 0)

    sketches: list[ProbabilityMultiSlotRepairSketch] = []
    considered_candidate_count = 0
    for resource in proof_ir.resources:
        if (
            resource.symbol != attempted.resource
            or resource.resource_kind != "theorem"
            or resource.conclusion.kind != "probability"
        ):
            continue
        required_value_slots = tuple(
            slot
            for slot in resource.application_signature.slots
            if slot.binding_mode == "required" and slot.kind != "proof"
        )
        if not required_value_slots or any(
            slot.kind not in {"module", "memory"}
            for slot in required_value_slots
        ) or any(
            slot.kind != "proof" and slot not in required_value_slots
            for slot in resource.application_signature.slots
        ):
            continue
        value_pools = tuple(
            term_pool.module_terms
            if slot.kind == "module"
            else term_pool.memory_terms
            for slot in required_value_slots
        )
        combination_count = 1
        for values in value_pools:
            combination_count *= len(values)
        considered_candidate_count += combination_count
        if considered_candidate_count > max_candidates:
            return _SketchDiscovery(
                (),
                considered_candidate_count,
                exceeded_materialization_budget=True,
            )
        for values in product(*value_pools):
            resolved = {
                slot.name: value
                for slot, value in zip(required_value_slots, values)
            }
            expectations = {
                slot.slot_id: _lexical_instantiate(slot.expected, resolved)
                for slot in resource.application_signature.slots
            }
            proof_matches = bind_available_proof_slots(
                resource.application_signature,
                instantiated_expectations=expectations,
                facts=proof_ir.facts,
            )
            proof_values = proof_matches.as_dict()
            arguments = tuple(
                proof_values.get(slot.slot_id, "_")
                if slot.kind == "proof"
                else resolved[slot.name]
                for slot in resource.application_signature.slots
            )
            evidence = tuple(dict.fromkeys(
                attempted.evidence_refs
                + resource.evidence_refs
                + goal.evidence_refs
                + proof_matches.evidence_refs
            ))
            sketches.append(ProbabilityMultiSlotRepairSketch(
                resource=resource,
                application_term=f"{resource.symbol} {' '.join(arguments)}",
                evidence_refs=evidence,
            ))
    unique = {
        (sketch.resource.resource_id, sketch.application_term): sketch
        for sketch in sketches
    }
    return _SketchDiscovery(
        tuple(unique.values()),
        considered_candidate_count,
    )


def analyze_native_probability_multislot_repair(
    proof_ir: ProofIR,
    coordinate: ProofCoordinate,
    invocation: CompilerInvocationContext,
) -> AnalysisContribution:
    """Admit the sketch only from its exact accepted native descriptor."""

    accepted = matched_native_probability_multislot_observations(proof_ir)
    if len(accepted) != 1:
        return AnalysisContribution()
    sketch, observation = accepted[0]
    return native_application_contribution(
        resource=sketch.resource,
        observation=observation,
        producer_id=OPERATION_BINDING_REPAIR_ANALYSIS_PRODUCER_ID,
        identity_namespace="native-b24-probability",
        evidence_refs=sketch.evidence_refs,
        trigger_id=proof_ir.attempted_operation.trigger_id,
    )


def matched_native_probability_multislot_observations(
    proof_ir: ProofIR,
) -> tuple[tuple[
    ProbabilityMultiSlotRepairSketch, NativeSemanticObservation
], ...]:
    """Return only feature-validated accepted native search members."""

    existing = tuple(
        item
        for item in proof_ir.native_semantic_observations
        if item.producer_id
        == PROBABILITY_MULTISLOT_REPAIR_NATIVE_PRODUCER_ID
    )
    if not existing:
        return ()
    discovery = _discover_probability_multislot_repair_sketches(
        proof_ir,
        max_candidates=len(existing),
    )
    sketches = discovery.sketches
    requests = _requests_for_sketches(proof_ir, sketches)
    if (
        not sketches
        or len(requests) != len(sketches)
    ):
        return ()
    accepted: list[tuple[
        ProbabilityMultiSlotRepairSketch, NativeSemanticObservation
    ]] = []
    for sketch, request in zip(sketches, requests):
        observations = tuple(
            item
            for item in proof_ir.native_semantic_observations
            if item.producer_id
            == PROBABILITY_MULTISLOT_REPAIR_NATIVE_PRODUCER_ID
            and item.request_id == request.request_id
        )
        if (
            len(observations) == 1
            and observations[0].status == "accepted"
            and observations[0].descriptor is not None
            and probability_multislot_descriptor_matches(
                observations[0].descriptor,
                resource=sketch.resource,
            )
        ):
            accepted.append((sketch, observations[0]))
    return tuple(accepted)


def _requests_for_sketches(
    proof_ir: ProofIR,
    sketches: tuple[ProbabilityMultiSlotRepairSketch, ...],
) -> tuple[NativeSemanticRequest, ...]:
    return tuple(
        NativeSemanticRequest(
            state_ref=proof_ir.state_ref,
            request_id=_request_id(sketch),
            producer_id=PROBABILITY_MULTISLOT_REPAIR_NATIVE_PRODUCER_ID,
            query=NativeProofTermElaborationQuery(
                operation="apply",
                application_term=sketch.application_term,
            ),
            evidence_refs=sketch.evidence_refs,
        )
        for sketch in sketches
    )


def probability_multislot_descriptor_matches(
    descriptor: NativeProofTermDescriptor,
    *,
    resource: ProofResource,
) -> bool:
    """Freeze the native shape accepted by the probability recovery family."""

    slots = resource.application_signature.slots
    if (
        descriptor.resolved_head.kind != "global"
        or not resolved_head_matches_resource(
            descriptor.resolved_head.identity,
            resource.symbol,
        )
        or descriptor.input_mode != "implicit"
        or descriptor.implicit_argument_count != 0
        or len(descriptor.input_arguments) != len(slots)
        or len(descriptor.arguments) != len(slots)
        or descriptor.result.type_text != "bool"
        or descriptor.result_convertible_to_current_goal is not True
    ):
        return False
    expected_kinds = {
        "module": "module",
        "memory": "memory",
        "term": "formula",
        "formula": "formula",
        "proof": "proof",
    }
    for slot, input_argument, argument in zip(
        slots,
        descriptor.input_arguments,
        descriptor.arguments,
    ):
        if expected_kinds.get(slot.kind) != argument.kind:
            return False
        if input_argument.explicit_hole != (
            argument.kind == "proof" and argument.hole
        ):
            return False
    return True


def _request_id(sketch: ProbabilityMultiSlotRepairSketch) -> str:
    digest = hashlib.sha256(
        (
            sketch.resource.resource_id
            + "\0apply\0"
            + sketch.application_term
        ).encode("utf-8")
    ).hexdigest()[:20]
    return f"operation-binding-b24-probability:{digest}"


def _lexical_instantiate(value: str, resolved: dict[str, str]) -> str:
    result = value
    for name in sorted(resolved, key=len, reverse=True):
        result = re.sub(
            rf"(?<![A-Za-z0-9_']){re.escape(name)}(?![A-Za-z0-9_'])",
            resolved[name],
            result,
        )
    return result
