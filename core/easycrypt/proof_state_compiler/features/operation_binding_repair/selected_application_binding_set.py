"""Generic native binding-set search for one already-selected theorem head."""

from __future__ import annotations

import hashlib
import json

from core.easycrypt.proof_state_compiler.contracts import (
    CompilerInvocationContext,
    NativePlanningBudget,
    NativeSelectedApplicationBindingSetDescriptor,
    NativeSelectedApplicationBindingSetQuery,
    NativeSemanticObservation,
    NativeSemanticRequest,
    NativeSemanticRequestProduction,
    ProofCoordinate,
    ProofIR,
)
from core.easycrypt.proof_state_compiler.features.operation_binding_repair.classification import (
    classify_operation_binding_failure,
)
from core.easycrypt.proof_state_compiler.syntax.attempted_operation import (
    bare_operation_resource,
)


SELECTED_APPLICATION_BINDING_SET_NATIVE_PRODUCER_ID = (
    "operation_binding_repair.selected_application_binding_set.native_search"
)


def plan_native_selected_application_binding_set(
    proof_ir: ProofIR,
    _coordinate: ProofCoordinate,
    _invocation: CompilerInvocationContext,
    _budget: NativePlanningBudget,
) -> NativeSemanticRequestProduction:
    """Search only an inference-seeking bare direct application.

    Concrete supplied arguments are never reinterpreted or reordered here.
    Their kind/position mismatches belong to the argument-alignment diagnostic.
    The native binding-set search is reserved for a bare ``apply``/``exact``
    whose selected theorem still requires module inference.
    """

    attempted = proof_ir.attempted_operation
    if attempted is None or attempted.native_diagnostic_status != "blocker":
        return NativeSemanticRequestProduction.not_applicable(
            SELECTED_APPLICATION_BINDING_SET_NATIVE_PRODUCER_ID
        )
    failure_class = classify_operation_binding_failure(attempted)
    head = attempted.application_head_descriptor
    candidate_evidence = attempted.evidence_refs
    if (
        failure_class == "B2"
        and attempted.operation in {"apply", "exact"}
        and head is not None
        and not head.input_arguments
        and any(slot.kind == "module" for slot in head.slots)
        and bare_operation_resource(attempted.rejected_tactic)
        == (attempted.operation, attempted.resource)
        and proof_ir.goal.kind not in {"probability", "losslessness"}
    ):
        inventory = proof_ir.module_spelling_inventory
        if inventory is None or not inventory.terms:
            return NativeSemanticRequestProduction.not_applicable(
                SELECTED_APPLICATION_BINDING_SET_NATIVE_PRODUCER_ID
            )
        if not inventory.complete:
            return NativeSemanticRequestProduction.abstained(
                SELECTED_APPLICATION_BINDING_SET_NATIVE_PRODUCER_ID,
                reason=inventory.reason,
                considered_candidate_count=0,
            )
        candidates = inventory.terms
        candidate_evidence = tuple(dict.fromkeys(
            candidate_evidence + inventory.evidence_refs
        ))
    else:
        return NativeSemanticRequestProduction.not_applicable(
            SELECTED_APPLICATION_BINDING_SET_NATIVE_PRODUCER_ID
        )
    query = NativeSelectedApplicationBindingSetQuery(
        operation=attempted.operation,
        selected_resource=attempted.resource,
        module_candidates=candidates,
    )
    digest = hashlib.sha256(
        (
            attempted.occurrence_identity
            + "\0"
            + attempted.recovery_key
            + "\0"
            + json.dumps(
                query.to_payload(),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        ).encode("utf-8")
    ).hexdigest()[:20]
    request = NativeSemanticRequest(
        state_ref=proof_ir.state_ref,
        request_id=f"selected-application-bindings:{digest}",
        producer_id=SELECTED_APPLICATION_BINDING_SET_NATIVE_PRODUCER_ID,
        query=query,
        evidence_refs=candidate_evidence,
    )
    return NativeSemanticRequestProduction.ready(
        SELECTED_APPLICATION_BINDING_SET_NATIVE_PRODUCER_ID,
        (request,),
        considered_candidate_count=len(candidates),
    )


def matched_native_selected_application_binding_set(
    proof_ir: ProofIR,
) -> tuple[
    NativeSemanticObservation,
    NativeSelectedApplicationBindingSetDescriptor,
] | None:
    attempted = proof_ir.attempted_operation
    if attempted is None:
        return None
    matches = tuple(
        observation
        for observation in proof_ir.native_semantic_observations
        if (
            observation.producer_id
            == SELECTED_APPLICATION_BINDING_SET_NATIVE_PRODUCER_ID
            and observation.status == "accepted"
            and isinstance(
                observation.descriptor,
                NativeSelectedApplicationBindingSetDescriptor,
            )
            and observation.descriptor.operation == attempted.operation
            and observation.descriptor.selected_resource == attempted.resource
            and observation.state_ref == proof_ir.state_ref
        )
    )
    if len(matches) != 1:
        return None
    observation = matches[0]
    assert isinstance(
        observation.descriptor,
        NativeSelectedApplicationBindingSetDescriptor,
    )
    return observation, observation.descriptor
