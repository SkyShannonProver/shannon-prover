"""Feature-neutral transport from native proof terms to application IR.

Feature slices own eligibility, candidate enumeration, and any frozen policy
over a native descriptor.  Once a descriptor is accepted by that policy, this
module performs the mechanical lowering into shared signature, slot, binding,
resource-assessment, and application contracts.  It makes no route decision
and imports no feature package.
"""

from __future__ import annotations

import hashlib
import json

from core.easycrypt.proof_state_compiler.contracts import (
    ApplicationCandidate,
    ApplicationSignature,
    ArgumentSlot,
    BindingResolution,
    EvidenceRef,
    NativeProofTermArgument,
    NativeProofTermDescriptor,
    NativeSemanticObservation,
    ProofResource,
    ResourceAssessment,
    SlotResolution,
)
from core.easycrypt.proof_state_compiler.middle_end.contributions import (
    AnalysisContribution,
)
from core.easycrypt.proof_state_compiler.syntax.module_terms import (
    lexical_procedure_views,
)


def native_application_contribution(
    *,
    resource: ProofResource,
    observation: NativeSemanticObservation,
    producer_id: str,
    identity_namespace: str,
    evidence_refs: tuple[EvidenceRef, ...],
    trigger_id: str = "",
) -> AnalysisContribution:
    """Lower one already-policy-accepted native descriptor into shared IR."""

    descriptor = observation.descriptor
    if observation.status != "accepted" or descriptor is None:
        raise ValueError("native application transport requires acceptance")
    native_evidence = EvidenceRef(
        evidence_id=(
            "native-proof-term:"
            + observation.provenance.source_event_id
        ),
        source_kind="native_proof_term_descriptor",
        source_ref=observation.provenance.artifact_ref,
        source_sha256=observation.provenance.source_sha256,
    )
    evidence = tuple(dict.fromkeys(evidence_refs + (native_evidence,)))
    return native_application_descriptor_contribution(
        resource=resource,
        descriptor=descriptor,
        operation=observation.query.operation,
        application_term=observation.query.application_term,
        producer_id=producer_id,
        identity_namespace=identity_namespace,
        evidence_refs=evidence,
        trigger_id=trigger_id,
    )


def native_application_descriptor_contribution(
    *,
    resource: ProofResource,
    descriptor: NativeProofTermDescriptor,
    operation: str,
    application_term: str,
    producer_id: str,
    identity_namespace: str,
    evidence_refs: tuple[EvidenceRef, ...],
    trigger_id: str = "",
) -> AnalysisContribution:
    """Lower one native-checked member carried by a compound descriptor."""

    if operation not in {"apply", "exact", "call", "conseq"} or (
        not application_term
    ):
        raise ValueError("native application descriptor transport is invalid")
    evidence = tuple(dict.fromkeys(evidence_refs))
    if not evidence:
        raise ValueError("native application descriptor requires evidence")
    signature_slots = tuple(
        _argument_slot(
            argument,
            implicit_count=descriptor.implicit_argument_count,
            evidence_refs=evidence,
        )
        for argument in descriptor.arguments
    )
    resolutions = tuple(
        _slot_resolution(argument, evidence_refs=evidence)
        for argument in descriptor.arguments
    )
    signature = ApplicationSignature(
        resource_id=resource.resource_id,
        slots=signature_slots,
        evidence_refs=evidence,
    )
    target = descriptor.result.procedure or descriptor.result.text
    descriptor_material = json.dumps(
        descriptor.to_payload(),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    material = hashlib.sha256(
        (
            resource.resource_id
            + "\0"
            + target
            + "\0"
            + operation
            + "\0"
            + application_term
            + "\0"
            + descriptor_material
        ).encode("utf-8")
    ).hexdigest()[:20]
    binding = BindingResolution(
        binding_id=f"{identity_namespace}-binding:{material}",
        producer_id=producer_id,
        resource_id=resource.resource_id,
        target=target,
        signature=signature,
        slots=resolutions,
        mechanically_complete=True,
        evidence_refs=evidence,
    )
    application = ApplicationCandidate(
        candidate_id=f"{identity_namespace}-application:{material}",
        producer_id=producer_id,
        binding_id=binding.binding_id,
        resource_id=resource.resource_id,
        target=target,
        operation=operation,
        application_term=application_term,
        slot_resolutions=resolutions,
        unresolved_premises=tuple(
            item.expected
            for item in resolutions
            if item.status == "deferred"
        ),
        evidence_refs=evidence,
        trigger_id=trigger_id,
    )
    return AnalysisContribution(
        resources=(ResourceAssessment(
            resource_id=resource.resource_id,
            status="live",
            evidence_refs=evidence,
        ),),
        bindings=(binding,),
        applications=(application,),
    )


def single_module_losslessness_certificate_matches(
    descriptor: NativeProofTermDescriptor,
    *,
    resource_symbol: str,
    target_procedure: str,
) -> bool:
    """Recognize one exact native losslessness-certificate shape."""

    return module_losslessness_certificate_matches(
        descriptor,
        resource_symbol=resource_symbol,
        target_procedure=target_procedure,
        proof_premise_count=1,
    )


def module_losslessness_certificate_matches(
    descriptor: NativeProofTermDescriptor,
    *,
    resource_symbol: str,
    target_procedure: str,
    proof_premise_count: int,
    expected_premise_procedures: tuple[str, ...] = (),
) -> bool:
    """Match one module plus an exact native losslessness-premise list.

    This shared transport matcher is cardinality-generic.  Feature packages
    decide which positive premise counts they admit before calling it.
    """

    if proof_premise_count <= 0:
        return False
    if expected_premise_procedures and (
        len(expected_premise_procedures) != proof_premise_count
    ):
        return False
    expected_argument_count = proof_premise_count + 1

    if (
        descriptor.resolved_head.kind != "global"
        or not resolved_head_matches_resource(
            descriptor.resolved_head.identity,
            resource_symbol,
        )
        or descriptor.input_mode != "implicit"
        or descriptor.explicit_hole_count != proof_premise_count
        or descriptor.implicit_argument_count != 0
        or len(descriptor.input_arguments) != expected_argument_count
        or descriptor.input_arguments[0].syntax_kind != "module"
        or descriptor.input_arguments[0].explicit_hole
        or any(
            item.syntax_kind != "hole" or not item.explicit_hole
            for item in descriptor.input_arguments[1:]
        )
        or len(descriptor.arguments) != expected_argument_count
        or len(descriptor.residual_proof_premises) != proof_premise_count
    ):
        return False
    module = descriptor.arguments[0]
    proofs = descriptor.arguments[1:]
    return (
        module.kind == "module"
        and not module.hole
        and bool(module.expected_type)
        and bool(module.resolved_identity)
        and all(
            proof.kind == "proof"
            and proof.hole
            and residual.argument_position == proof.position
            and proof.expected_formula == residual.formula
            and (
                proof.resolved_formula is None
                or proof.resolved_formula == residual.formula
            )
            and residual.formula.kind == "bounded_hoare_function"
            and residual.formula.lossless is True
            and residual.formula.comparison == "="
            and bool(residual.formula.procedure)
            and (
                not expected_premise_procedures
                or _native_procedure_matches_lexical_candidate(
                    residual.formula.procedure,
                    expected_premise_procedures[index],
                )
            )
            for index, (proof, residual) in enumerate(zip(
                proofs,
                descriptor.residual_proof_premises,
            ))
        )
        and descriptor.result.kind == "bounded_hoare_function"
        and descriptor.result.lossless is True
        and descriptor.result.comparison == "="
        and descriptor.result.procedure == target_procedure
    )


def _native_procedure_matches_lexical_candidate(
    native_identity: str,
    lexical_candidate: str,
) -> bool:
    """Join a native xpath to the source spelling that formed its query.

    EasyCrypt prints authoritative procedure identities as ``Top.M./p``;
    declarations loaded for bounded planning spell the same procedure as
    ``M.p``.  The native descriptor remains the semantic authority.  This
    comparison only preserves the parsed declaration's premise order across
    that known printer boundary.
    """

    return (
        native_identity == lexical_candidate
        or lexical_candidate in lexical_procedure_views(native_identity)
    )


def single_module_losslessness_direct_application_matches(
    descriptor: NativeProofTermDescriptor,
    *,
    resource_symbol: str,
    target_procedure: str,
) -> bool:
    """Require a certificate whose result directly matches the current goal."""

    return (
        descriptor.result_convertible_to_current_goal is True
        and single_module_losslessness_certificate_matches(
            descriptor,
            resource_symbol=resource_symbol,
            target_procedure=target_procedure,
        )
    )


def resolved_head_matches_resource(identity: str, resource_symbol: str) -> bool:
    """Match an exact selected spelling under EasyCrypt's qualified root."""

    return identity == resource_symbol or identity.endswith("." + resource_symbol)


def _argument_slot(
    argument: NativeProofTermArgument,
    *,
    implicit_count: int,
    evidence_refs: tuple[EvidenceRef, ...],
) -> ArgumentSlot:
    expected = _argument_expectation(argument)
    return ArgumentSlot(
        slot_id=f"native:{argument.position}",
        name=argument.expected_name or f"{argument.kind}_{argument.position}",
        kind=argument.kind,
        binding_mode=(
            "deferred_obligation"
            if argument.kind == "proof" and argument.hole
            else "required"
        ),
        expected=expected,
        explicit=argument.position > implicit_count,
        evidence_refs=evidence_refs,
    )


def _slot_resolution(
    argument: NativeProofTermArgument,
    *,
    evidence_refs: tuple[EvidenceRef, ...],
) -> SlotResolution:
    expected = _argument_expectation(argument)
    if argument.kind == "proof" and argument.hole:
        return SlotResolution(
            slot_id=f"native:{argument.position}",
            kind=argument.kind,
            status="deferred",
            expected=expected,
            reason="native EasyCrypt returned a residual proof premise",
            evidence_refs=evidence_refs,
        )
    return SlotResolution(
        slot_id=f"native:{argument.position}",
        kind=argument.kind,
        status="resolved",
        expected=expected,
        value=_argument_value(argument),
        evidence_refs=evidence_refs,
    )


def _argument_expectation(argument: NativeProofTermArgument) -> str:
    if argument.kind == "proof":
        assert argument.expected_formula is not None
        return argument.expected_formula.text
    return argument.expected_type


def _argument_value(argument: NativeProofTermArgument) -> str:
    if argument.kind == "formula":
        assert argument.resolved_formula is not None
        return argument.resolved_formula.text
    if argument.kind in {"memory", "module"}:
        return argument.resolved_identity
    assert argument.resolved_proof_head is not None
    return argument.resolved_proof_head.identity
