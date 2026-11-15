"""Construct shared attempted-operation IR only from native EasyCrypt output."""

from __future__ import annotations

import re

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
from core.easycrypt.proof_state_compiler.contracts.digest import (
    canonical_json,
    text_sha256,
)


def parse_attempted_operation(
    observation: FailureObservation | None,
    native_observations: tuple[NativeSemanticObservation, ...],
    *,
    trigger_id: str,
) -> AttemptedOperationIR | None:
    """Join one exact failure to one native parse/applicability descriptor.

    Raw error text never classifies anything here. Its one use is a veto: a
    native compound boundary must report the same error EasyCrypt reported
    for the whole commit, or no compound IR is formed. Multiple feature
    consumers may receive fan-out observations for the same native semantic
    unit; byte-identical descriptors are deduplicated, while any
    disagreement fails closed.
    """

    if observation is None or not trigger_id:
        return None
    rejected_tactic = str(
        observation.payload.to_dict().get("tactic") or ""
    ).strip()
    # A multi-sentence commit that EasyCrypt rejected at one sentence: a
    # feature that opts in analysed that sentence after the earlier ones.
    sentence_scope = observation.sentence_scope
    if observation.failed_sentence is not None:
        if sentence_scope is None:
            return None
        rejected_tactic = sentence_scope.sentence
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
        material = canonical_json(descriptor.to_payload())
        candidates.setdefault(material, (descriptor, item))
    if len(candidates) != 1:
        return None
    descriptor, native_observation = next(iter(candidates.values()))
    prefix_population = isinstance(
        descriptor, NativeTacticPrefixDiagnosticDescriptor
    )
    # A native companion contract error is not an EasyCrypt rejection, and a
    # boundary must fail with the error EasyCrypt reported for the commit.
    if prefix_population and (
        "contract_error" in {
            descriptor.native_failure_kind,
            descriptor.boundary_failure_kind,
        }
        or not manager_reports_same_error(
            descriptor.boundary_error_message,
            observation.structured_error,
        )
    ):
        return None
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
    material = canonical_json(descriptor.to_payload())
    attempt_id = text_sha256(
        observation.occurrence_identity
        + "\0"
        + material
    )
    recovery_handoff = None
    # A failing sentence forms no typed handoff: its consumers would neither
    # run after nor recompose with the sentences before it.
    if (
        prefix_population
        and descriptor.boundary_attempt is not None
        and sentence_scope is None
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
    elif prefix_population:
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
        realization=descriptor.realization,
        proof_term_descriptor=freeze_json_object(
            descriptor.proof_term.to_payload()
            if descriptor.proof_term is not None
            else {}
        ),
        evidence_refs=evidence_refs,
        recovery_handoff=recovery_handoff,
    )


# The manager keeps at most this many characters of EasyCrypt's error
# (workflow/proof_management/backend_actions.py); a text that long may be cut.
MANAGER_ERROR_TEXT_LIMIT = 1200
_SEVERITY_HEADER = re.compile(r"^\[(?:error|critical|fatal)(?:-[0-9\-]+)?\]\s*")
_LOCATION_HEADER = re.compile(
    r"^\[[^\]\n]*: line \d+ \([^)\n]*\)(?: to line \d+ \([^)\n]*\))?\]:?\s*"
)


def _reported_error_text(value: str) -> str:
    text = _SEVERITY_HEADER.sub("", str(value or "").strip(), count=1)
    text = _LOCATION_HEADER.sub("", text, count=1)
    return " ".join(text.split())


def manager_reports_same_error(native_error: str, manager_error: str) -> bool:
    """Whether EasyCrypt's own report for the commit is the native error.

    Only the severity/location header and line breaking may differ: the
    native companion and the toplevel print the same EasyCrypt message with
    different margins. A manager text at its length limit is compared as a
    prefix. An empty side never matches.
    """

    native = _reported_error_text(native_error)
    manager = _reported_error_text(manager_error)
    if not native or not manager:
        return False
    if len(str(manager_error or "")) >= MANAGER_ERROR_TEXT_LIMIT:
        return native.startswith(manager)
    return native == manager
