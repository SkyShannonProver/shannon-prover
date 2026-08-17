"""Native-backed B1 namespace-only repair family.

The lexical phase identifies one same-basename spelling. EasyCrypt owns the
resolved head and elaborated result. This family deliberately accepts only a
bare proof-term head, so changing the namespace cannot silently drop or invent
arguments from the rejected tactic.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from core.easycrypt.proof_state_compiler.contracts import (
    ApplicationCandidate,
    CompilerInvocationContext,
    EvidenceRef,
    NativePlanningBudget,
    NativeProofTermDescriptor,
    NativeProofTermElaborationQuery,
    NativeSemanticRequest,
    NativeSemanticRequestProduction,
    ProofCoordinate,
    ProofIR,
    ProofResource,
    ResourceAssessment,
    SlotResolution,
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
    bare_operation_resource,
)


NAMESPACE_REPAIR_NATIVE_PRODUCER_ID = (
    "operation_binding_repair.namespace.native_elaboration"
)


@dataclass(frozen=True)
class NamespaceRepairSketch:
    resource: ProofResource
    operation: str
    attempted_resource: str
    application_term: str
    evidence_refs: tuple[EvidenceRef, ...]


def plan_native_namespace_repair(
    proof_ir: ProofIR,
    _coordinate: ProofCoordinate,
    invocation: CompilerInvocationContext,
    _budget: NativePlanningBudget,
) -> NativeSemanticRequestProduction:
    """Plan exactly one native elaboration for one namespace-only correction."""

    if invocation.state_ref != proof_ir.state_ref:
        raise ValueError("B1 native request planning crossed StateRef")
    sketch = discover_unique_namespace_repair(proof_ir)
    if sketch is None:
        return NativeSemanticRequestProduction.not_applicable(
            NAMESPACE_REPAIR_NATIVE_PRODUCER_ID
        )
    digest = hashlib.sha256(
        (
            sketch.operation
            + "\0"
            + sketch.attempted_resource
            + "\0"
            + sketch.resource.resource_id
            + "\0"
            + sketch.application_term
        ).encode("utf-8")
    ).hexdigest()[:20]
    request = NativeSemanticRequest(
        state_ref=proof_ir.state_ref,
        request_id=f"operation-binding-b1:{digest}",
        producer_id=NAMESPACE_REPAIR_NATIVE_PRODUCER_ID,
        query=NativeProofTermElaborationQuery(
            operation=sketch.operation,
            application_term=sketch.application_term,
        ),
        evidence_refs=sketch.evidence_refs,
    )
    return NativeSemanticRequestProduction.ready(
        NAMESPACE_REPAIR_NATIVE_PRODUCER_ID, (request,)
    )


def discover_unique_namespace_repair(
    proof_ir: ProofIR,
) -> NamespaceRepairSketch | None:
    attempted = proof_ir.attempted_operation
    if (
        attempted is None
        or classify_operation_binding_failure(attempted) != "B1"
        or "." not in attempted.resource
        or bare_operation_resource(attempted.rejected_tactic)
        != (attempted.operation, attempted.resource)
    ):
        return None
    resources = tuple(
        item
        for item in proof_ir.resources
        if item.symbol.rsplit(".", 1)[-1] == attempted.resource_basename
        and item.symbol != attempted.resource
    )
    if len(resources) != 1:
        return None
    resource = resources[0]
    evidence = tuple(dict.fromkeys(
        attempted.evidence_refs + resource.evidence_refs
    ))
    return NamespaceRepairSketch(
        resource=resource,
        operation=attempted.operation,
        attempted_resource=attempted.resource,
        application_term=resource.symbol,
        evidence_refs=evidence,
    )


def analyze_native_namespace_repair(
    proof_ir: ProofIR,
    coordinate: ProofCoordinate,
    invocation: CompilerInvocationContext,
) -> AnalysisContribution:
    """Create a B1 application only from one accepted native descriptor."""

    sketch = discover_unique_namespace_repair(proof_ir)
    requests = plan_native_namespace_repair(
        proof_ir, coordinate, invocation, NativePlanningBudget()
    ).requests
    if sketch is None or len(requests) != 1:
        return AnalysisContribution()
    request = requests[0]
    observations = tuple(
        item
        for item in proof_ir.native_semantic_observations
        if item.producer_id == NAMESPACE_REPAIR_NATIVE_PRODUCER_ID
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
    if not _descriptor_matches_namespace_repair(
        descriptor,
        resource_symbol=sketch.resource.symbol,
    ):
        return AnalysisContribution()

    native_evidence = EvidenceRef(
        evidence_id=(
            "native-proof-term:"
            + observation.provenance.source_event_id
        ),
        source_kind="native_proof_term_descriptor",
        source_ref=observation.provenance.artifact_ref,
        source_sha256=observation.provenance.source_sha256,
    )
    evidence = tuple(dict.fromkeys(
        sketch.evidence_refs + (native_evidence,)
    ))
    slots = tuple(
        SlotResolution(
            slot_id=f"native-proof:{item.argument_position}",
            kind="proof",
            status="deferred",
            expected=item.formula.text,
            reason="native EasyCrypt returned a residual proof premise",
            evidence_refs=evidence,
        )
        for item in descriptor.residual_proof_premises
    )
    descriptor_material = json.dumps(
        descriptor.to_payload(),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    material = hashlib.sha256(
        (
            sketch.operation
            + "\0"
            + sketch.attempted_resource
            + "\0"
            + sketch.resource.resource_id
            + "\0"
            + observation.query.application_term
            + "\0"
            + descriptor_material
        ).encode("utf-8")
    ).hexdigest()[:20]
    application = ApplicationCandidate(
        candidate_id=f"operation-binding-repair:{material}",
        producer_id=OPERATION_BINDING_REPAIR_ANALYSIS_PRODUCER_ID,
        binding_id=f"native-namespace-binding:{material}",
        resource_id=sketch.resource.resource_id,
        target=descriptor.result.text,
        operation=observation.query.operation,
        application_term=observation.query.application_term,
        slot_resolutions=slots,
        unresolved_premises=tuple(
            item.formula.text
            for item in descriptor.residual_proof_premises
        ),
        evidence_refs=evidence,
        trigger_id=proof_ir.attempted_operation.trigger_id,
    )
    return AnalysisContribution(
        resources=(ResourceAssessment(
            resource_id=sketch.resource.resource_id,
            status="live",
            evidence_refs=evidence,
        ),),
        applications=(application,),
    )


def _descriptor_matches_namespace_repair(
    descriptor: NativeProofTermDescriptor,
    *,
    resource_symbol: str,
) -> bool:
    return (
        descriptor.resolved_head.kind == "global"
        and descriptor.resolved_head.identity.rsplit(".", 1)[-1]
        == resource_symbol.rsplit(".", 1)[-1]
        and not descriptor.input_arguments
        and descriptor.explicit_hole_count == 0
    )
