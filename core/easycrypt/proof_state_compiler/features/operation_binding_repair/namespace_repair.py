"""Native-backed B1 namespace-only repair family.

The agent's written lemma name does not resolve. EasyCrypt enumerates every
lemma or axiom of the current environment with the same basename, spells each
with its shortest name that resolves back to it, and runs the agent's tactic
with only that head replaced at the current goal. The proof term must be a bare
head or one parenthesized application, and its argument text is copied
unchanged, so no argument is dropped, invented, or reordered.

This is type-directed resolution of the agent's own name, not a replacement
resource: declarations with a different basename are never considered. A
correction is formed only for a complete native population in which exactly
one declaration is accepted with progress; several accepted declarations are
never ranked.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from core.easycrypt.proof_state_compiler.contracts import (
    ApplicationCandidate,
    CompilerInvocationContext,
    EvidenceRef,
    NativeNamespaceSpellingSetDescriptor,
    NativeNamespaceSpellingSetQuery,
    NativePlanningBudget,
    NativeSemanticRequest,
    NativeSemanticRequestProduction,
    ProofCoordinate,
    ProofIR,
    valid_namespace_spelling_arguments,
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
from core.easycrypt.proof_state_compiler.syntax.attempted_operation import (
    operation_head_arguments,
)


NAMESPACE_REPAIR_NATIVE_PRODUCER_ID = (
    "operation_binding_repair.namespace.native_spelling_set"
)


@dataclass(frozen=True)
class NamespaceRepairSketch:
    operation: str
    written_name: str
    arguments: str
    evidence_refs: tuple[EvidenceRef, ...]


def plan_native_namespace_repair(
    proof_ir: ProofIR,
    _coordinate: ProofCoordinate,
    invocation: CompilerInvocationContext,
    _budget: NativePlanningBudget,
) -> NativeSemanticRequestProduction:
    """Plan one native population query for one unresolved written name."""

    if invocation.state_ref != proof_ir.state_ref:
        raise ValueError("B1 native request planning crossed StateRef")
    sketch = discover_namespace_repair(proof_ir)
    if sketch is None:
        return NativeSemanticRequestProduction.not_applicable(
            NAMESPACE_REPAIR_NATIVE_PRODUCER_ID
        )
    return NativeSemanticRequestProduction.ready(
        NAMESPACE_REPAIR_NATIVE_PRODUCER_ID,
        (_request_for_sketch(proof_ir, sketch),),
    )


def discover_namespace_repair(proof_ir: ProofIR) -> NamespaceRepairSketch | None:
    attempted = proof_ir.attempted_operation
    if (
        attempted is None
        or classify_operation_binding_failure(attempted) != "B1"
    ):
        return None
    parsed = operation_head_arguments(attempted.rejected_tactic)
    if (
        parsed is None
        or parsed[:2] != (attempted.operation, attempted.resource)
        or not valid_namespace_spelling_arguments(parsed[2])
    ):
        return None
    return NamespaceRepairSketch(
        operation=attempted.operation,
        written_name=attempted.resource,
        arguments=parsed[2],
        evidence_refs=attempted.evidence_refs,
    )


def _request_for_sketch(
    proof_ir: ProofIR,
    sketch: NamespaceRepairSketch,
) -> NativeSemanticRequest:
    query = NativeNamespaceSpellingSetQuery(
        operation=sketch.operation,
        arguments=sketch.arguments,
        written_name=sketch.written_name,
    )
    digest = hashlib.sha256(
        json.dumps(
            query.to_payload(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()[:20]
    return NativeSemanticRequest(
        state_ref=proof_ir.state_ref,
        request_id=f"operation-binding-b1:{digest}",
        producer_id=NAMESPACE_REPAIR_NATIVE_PRODUCER_ID,
        query=query,
        evidence_refs=sketch.evidence_refs,
    )


def analyze_native_namespace_repair(
    proof_ir: ProofIR,
    _coordinate: ProofCoordinate,
    _invocation: CompilerInvocationContext,
) -> AnalysisContribution:
    """Create a B1 application only when exactly one declaration is accepted."""

    sketch = discover_namespace_repair(proof_ir)
    # The application targets the goal the failed operation was run
    # against; without that goal there is nothing honest to report.
    if sketch is None or not proof_ir.goal.formula:
        return AnalysisContribution()
    request = _request_for_sketch(proof_ir, sketch)
    observations = tuple(
        item
        for item in proof_ir.native_semantic_observations
        if item.producer_id == NAMESPACE_REPAIR_NATIVE_PRODUCER_ID
        and item.request_id == request.request_id
    )
    if (
        len(observations) != 1
        or observations[0].status != "accepted"
        or not isinstance(
            observations[0].descriptor, NativeNamespaceSpellingSetDescriptor
        )
    ):
        return AnalysisContribution()
    observation = observations[0]
    descriptor = observation.descriptor
    if (
        descriptor.operation != sketch.operation
        or descriptor.arguments != sketch.arguments
        or descriptor.written_name != sketch.written_name
        or descriptor.written_name_resolves
        or not descriptor.population_complete
    ):
        return AnalysisContribution()
    accepted = tuple(
        item
        for item in descriptor.spellings
        if item.tactic_effect == "accepted_changed"
    )
    if len({item.resolved_identity for item in accepted}) != 1:
        return AnalysisContribution()
    spelling = accepted[0]

    native_evidence = EvidenceRef(
        evidence_id=(
            "native-namespace-spelling-set:"
            + observation.provenance.source_event_id
        ),
        source_kind="native_namespace_spelling_set",
        source_ref=observation.provenance.artifact_ref,
        source_sha256=observation.provenance.source_sha256,
    )
    evidence = tuple(dict.fromkeys(
        sketch.evidence_refs + (native_evidence,)
    ))
    material = hashlib.sha256(
        (
            request.request_id
            + "\0"
            + spelling.resolved_identity
            + "\0"
            + spelling.application_term
        ).encode("utf-8")
    ).hexdigest()[:20]
    return AnalysisContribution(applications=(ApplicationCandidate(
        candidate_id=f"operation-binding-repair:{material}",
        producer_id=OPERATION_BINDING_REPAIR_ANALYSIS_PRODUCER_ID,
        binding_id=f"native-namespace-binding:{material}",
        resource_id=f"native-global:{spelling.resolved_identity}",
        target=proof_ir.goal.formula,
        operation=sketch.operation,
        application_term=spelling.application_term,
        slot_resolutions=(),
        unresolved_premises=(),
        evidence_refs=evidence,
        trigger_id=proof_ir.attempted_operation.trigger_id,
    ),))
