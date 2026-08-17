"""Construct shared attempted-operation IR only from native EasyCrypt output."""

from __future__ import annotations

import hashlib
import json

from core.easycrypt.proof_state_compiler.contracts.evidence import EvidenceRef
from core.easycrypt.proof_state_compiler.contracts.failure import (
    AttemptedOperationIR,
    FailureObservation,
    RecoveryHandoff,
)
from core.easycrypt.proof_state_compiler.contracts.native_semantics import (
    NativeAttemptedOperationDescriptor,
    NativeSemanticObservation,
    NativeTacticPrefixDiagnosticDescriptor,
)
from core.easycrypt.proof_state_compiler.contracts.frozen_json import (
    freeze_json_object,
)


def parse_attempted_operation(
    observation: FailureObservation | None,
    native_observations: tuple[NativeSemanticObservation, ...],
    *,
    trigger_id: str,
) -> AttemptedOperationIR | None:
    """Join one exact failure to one native parse/applicability descriptor.

    Raw error text is intentionally absent from this function. Multiple
    feature consumers may receive fan-out observations for the same native
    semantic unit; byte-identical descriptors are deduplicated, while any
    disagreement fails closed.
    """

    if observation is None or not trigger_id:
        return None
    rejected_tactic = str(
        observation.payload.to_dict().get("tactic") or ""
    ).strip()
    candidates: dict[
        str,
        tuple[
            NativeAttemptedOperationDescriptor
            | NativeTacticPrefixDiagnosticDescriptor,
            NativeSemanticObservation,
        ],
    ] = {}
    for item in native_observations:
        descriptor = item.descriptor
        if (
            item.state_ref != observation.state_ref
            or item.status != "accepted"
            or not isinstance(descriptor, (
                NativeAttemptedOperationDescriptor,
                NativeTacticPrefixDiagnosticDescriptor,
            ))
            or descriptor.rejected_tactic != rejected_tactic
            or (
                isinstance(descriptor, NativeAttemptedOperationDescriptor)
                and descriptor.attempt_outcome != observation.outcome_kind
            )
            or (
                isinstance(descriptor, NativeTacticPrefixDiagnosticDescriptor)
                and observation.outcome_kind
                not in {"rejected", "no_progress"}
            )
        ):
            continue
        material = json.dumps(
            descriptor.to_payload(),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        candidates.setdefault(material, (descriptor, item))
    if len(candidates) != 1:
        return None
    descriptor, native_observation = next(iter(candidates.values()))
    native_evidence = EvidenceRef(
        evidence_id=(
            "native-attempt:" + native_observation.provenance.source_event_id
        ),
        source_kind="native_attempt_descriptor",
        source_ref=native_observation.provenance.artifact_ref,
        source_sha256=native_observation.provenance.source_sha256,
    )
    evidence_refs = tuple(dict.fromkeys((
        observation.evidence_ref,
        native_evidence,
    )))
    material = json.dumps(
        descriptor.to_payload(),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    attempt_id = hashlib.sha256(
        (
            observation.occurrence_identity
            + "\0"
            + material
        ).encode("utf-8")
    ).hexdigest()
    recovery_handoff = None
    if (
        isinstance(descriptor, NativeTacticPrefixDiagnosticDescriptor)
        and descriptor.boundary_attempt is not None
    ):
        if not native_observation.feature_id:
            return None
        recovery_handoff = RecoveryHandoff(
            handoff_kind="native_compound_boundary",
            source_feature_id=native_observation.feature_id,
            source_rejected_tactic=descriptor.rejected_tactic,
            accepted_prefix_tactic=descriptor.accepted_prefixes[-1],
            accepted_prefix_effect=descriptor.prefix_effects[
                len(descriptor.accepted_prefixes) - 1
            ],
            accepted_prefix_stage_count=len(descriptor.accepted_prefixes),
            derived_rejected_tactic=descriptor.boundary_tactic,
            native_failure_kind=descriptor.boundary_failure_kind,
            native_error_message=descriptor.boundary_error_message,
        )
        descriptor = descriptor.boundary_attempt
    elif isinstance(descriptor, NativeTacticPrefixDiagnosticDescriptor):
        return AttemptedOperationIR(
            attempt_id=attempt_id,
            failure_observation_id=observation.observation_id,
            occurrence_identity=observation.occurrence_identity,
            trigger_id=trigger_id,
            source_event_id=observation.source_event_id,
            state_ref=observation.state_ref,
            committed_prefix_identity=observation.committed_prefix_identity,
            operation_family="compound_tactic",
            exact_resource="",
            resource_basename="",
            rejected_tactic=rejected_tactic,
            attempt_outcome_kind=observation.outcome_kind,
            native_diagnostic_status="blocker",
            native_failure_kind=descriptor.native_failure_kind,
            native_error_message=descriptor.native_error_message,
            parsed_arguments=(),
            side="",
            positions=(),
            application_head_descriptor=None,
            relation_bridge_descriptor=None,
            relation_bridge_choice_descriptor=None,
            phl_transitivity_boundary_descriptor=None,
            eager_while_dialect_descriptor=None,
            proof_term_descriptor=freeze_json_object({}),
            evidence_refs=evidence_refs,
        )
    return AttemptedOperationIR(
        attempt_id=attempt_id,
        failure_observation_id=observation.observation_id,
        occurrence_identity=observation.occurrence_identity,
        trigger_id=trigger_id,
        source_event_id=observation.source_event_id,
        state_ref=observation.state_ref,
        committed_prefix_identity=observation.committed_prefix_identity,
        operation_family=descriptor.operation_family,
        exact_resource=descriptor.exact_resource,
        resource_basename=(
            descriptor.exact_resource.rsplit(".", 1)[-1]
            if descriptor.exact_resource
            else ""
        ),
        rejected_tactic=descriptor.rejected_tactic,
        attempt_outcome_kind=descriptor.attempt_outcome,
        native_diagnostic_status=descriptor.native_diagnostic_status,
        native_failure_kind=descriptor.native_failure_kind,
        native_error_message=descriptor.native_error_message,
        parsed_arguments=descriptor.argument_kinds,
        side=descriptor.side,
        positions=descriptor.positions,
        application_head_descriptor=descriptor.application_head,
        relation_bridge_descriptor=descriptor.relation_bridge,
        relation_bridge_choice_descriptor=descriptor.relation_bridge_choice,
        phl_transitivity_boundary_descriptor=(
            descriptor.phl_transitivity_boundary
        ),
        eager_while_dialect_descriptor=descriptor.eager_while_dialect,
        pure_tail_rewrite_descriptor=descriptor.pure_tail_rewrite,
        intro_pattern_repair_descriptor=descriptor.intro_pattern_realization,
        application_syntax_repair_descriptor=(
            descriptor.application_syntax_repair
        ),
        proof_term_descriptor=freeze_json_object(
            descriptor.proof_term.to_payload()
            if descriptor.proof_term is not None
            else {}
        ),
        evidence_refs=evidence_refs,
        recovery_handoff=recovery_handoff,
    )
