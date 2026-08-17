"""Event-bound live runtime input conversion for the compiler service."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.easycrypt.proof_state_compiler import (
    AuthoritativeSnapshotInput,
    CompilationEnvironment,
    LoadedDeclaration,
    LoadedSourceUnit,
    ProvenanceRef,
    StateRef,
)
from core.easycrypt.proof_state_compiler.frontend import RuntimeSnapshotInput
from core.easycrypt.ec_runtime_identity import EasyCryptRuntimeIdentity
from core.easycrypt.native_semantics import NativeCompanionIdentity
from core.easycrypt.session_native_semantics import (
    validate_native_semantic_batch_result,
)
from core.easycrypt.session_native_state import validate_native_state_artifact
from core.easycrypt.session_compiler_input import validate_compiler_input
from core.easycrypt.session_compiler_resources import (
    validate_compiler_resource_load,
)
from core.easycrypt.session_projection import active_goal_hash_from_raw
from core.easycrypt.proof_state_compiler.contracts import (
    NativeProofStateSnapshot,
    NativeFormulaBoundaryDescriptor,
    NativeFormulaDescriptor,
    NativeInputArgument,
    NativeIntroPatternRepairDescriptor,
    NativeModuleTermDescriptor,
    NativePhlTransitivityBoundaryDescriptor,
    NativePureTailRewriteDescriptor,
    NativeAttemptedOperationDescriptor,
    NativeCheckedApplication,
    NativeApplicationHeadDescriptor,
    NativeApplicationSyntaxRepairDescriptor,
    NativeApplicationSlotDescriptor,
    NativeEagerWhileCandidateDescriptor,
    NativeEagerWhileDialectDescriptor,
    NativeProofTermArgument,
    NativeProofTermDescriptor,
    NativeRelationBridgeChoice,
    NativeRelationBridgeChoiceDescriptor,
    NativeRelationBridgeDescriptor,
    NativeResidualProofPremise,
    NativeResolvedHead,
    NativeSelectedApplicationBindingSetDescriptor,
    NativeSemanticObservation,
    NativeSemanticExecutionUnit,
    NativeTacticPrefixDiagnosticDescriptor,
    TargetRef,
    TransitionRef,
    freeze_json_object,
)


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class RuntimeCompilerInput:
    """Validated ordinary runtime input before typed-state enrichment."""

    snapshot: RuntimeSnapshotInput
    environment: CompilationEnvironment
    source_snapshot_id: str
    resource_load_report: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True)
class LiveCompilerInput:
    """Compiler-ready input; every open state has native typed authority."""

    snapshot: AuthoritativeSnapshotInput
    environment: CompilationEnvironment
    source_snapshot_id: str
    resource_load_report: tuple[dict[str, Any], ...] = ()


def runtime_compiler_input(manager_result: dict[str, Any]) -> RuntimeCompilerInput:
    """Fail closed while converting one ordinary event-bound manager result."""

    if type(manager_result) is not dict:
        raise TypeError("manager compiler input result must be an object")
    raw = manager_result.get("snapshot")
    authority = manager_result.get("authority")
    if type(raw) is not dict or type(authority) is not dict:
        raise ValueError("manager compiler input result is incomplete")
    validation = validate_compiler_input(raw)
    if not validation.ok:
        raise ValueError(
            "manager compiler input snapshot is invalid: "
            + "; ".join(validation.errors)
        )
    if authority.get("event_type") != "compiler.input.produced":
        raise ValueError("compiler input has the wrong authority event")
    event_id = str(authority.get("event_id") or "")
    event_sequence = authority.get("event_sequence")
    artifact_ref = str(authority.get("artifact_ref") or "")
    artifact_sha256 = str(authority.get("artifact_sha256") or "")
    if not event_id or type(event_sequence) is not int or event_sequence < 0:
        raise ValueError("compiler input authority occurrence is incomplete")
    if not artifact_ref or not _SHA256_RE.fullmatch(artifact_sha256):
        raise ValueError("compiler input artifact authority is incomplete")

    state = raw.get("state")
    target = raw.get("target")
    transition = raw.get("transition")
    if type(state) is not dict or type(target) is not dict:
        raise ValueError("compiler input state or target is missing")
    if transition != {"kind": "inspected"}:
        raise ValueError("compiler input must describe an inspected state")
    state_ref = StateRef(
        session_id=str(state.get("session_id") or ""),
        state_version=_exact_int(state.get("state_version"), "state_version"),
        goal_identity=str(state.get("goal_identity") or ""),
        goal_identity_required=_exact_bool(
            state.get("goal_identity_required"), "goal_identity_required"
        ),
        committed_prefix_identity=str(
            state.get("committed_prefix_identity") or ""
        ),
    )
    source_file = str(target.get("source_file") or "")
    source_sha256 = str(target.get("source_sha256") or "")
    lemma = str(target.get("lemma") or "")
    source_text = Path(source_file).read_text(encoding="utf-8")
    observed_source_sha256 = hashlib.sha256(
        source_text.encode("utf-8")
    ).hexdigest()
    if source_sha256 != observed_source_sha256:
        raise ValueError("compiler source changed after runtime snapshot")

    provenance = ProvenanceRef(
        producer="runtime.compiler_input_v2",
        authority="compiler.input.produced",
        source_sha256=artifact_sha256,
        artifact_ref=artifact_ref,
        source_event_id=event_id,
        source_event_sequence=event_sequence,
        authoritative=True,
    )
    snapshot = RuntimeSnapshotInput(
        state_ref=state_ref,
        provenance=provenance,
        target=TargetRef(source_file=source_file, lemma=lemma),
        transition=TransitionRef(
            kind="inspected",
            previous_state_ref=state_ref,
            result_artifact_ref=artifact_ref,
        ),
        goal_lines=_exact_string_list(state.get("goal_lines")),
        goal_count=_exact_int(state.get("goal_count"), "goal_count"),
        goal_count_known=_exact_bool(
            state.get("goal_count_known"), "goal_count_known"
        ),
        closed=_exact_bool(state.get("closed"), "closed"),
    )
    environment = CompilationEnvironment(
        environment_id=f"compiler-input:{event_id}",
        source_units=(LoadedSourceUnit(
            source_ref=source_file,
            source_sha256=source_sha256,
            text=source_text,
        ),),
        easycrypt_runtime=EasyCryptRuntimeIdentity.from_payload(
            raw.get("easycrypt_runtime")
        ),
    )
    return RuntimeCompilerInput(
        snapshot=snapshot,
        environment=environment,
        source_snapshot_id=str(raw.get("snapshot_id") or ""),
        resource_load_report=(),
    )


def live_compiler_input(
    manager_result: dict[str, Any],
    native_state_result: dict[str, Any] | None,
    *,
    native_state_request_id: str = "",
) -> LiveCompilerInput:
    """Join ordinary state identity with native typed-state authority.

    Open states require exactly one native occurrence. Closed states require
    none. There is intentionally no pretty-text fallback.
    """

    return attach_native_state(
        runtime_compiler_input(manager_result),
        native_state_result,
        native_state_request_id=native_state_request_id,
    )


def attach_native_state(
    runtime_input: RuntimeCompilerInput,
    manager_result: dict[str, Any] | None,
    *,
    native_state_request_id: str = "",
) -> LiveCompilerInput:
    snapshot = runtime_input.snapshot
    native_state = None
    if snapshot.closed:
        if manager_result is not None:
            raise ValueError("closed compiler input cannot carry native open state")
        if native_state_request_id:
            raise ValueError("closed compiler input cannot carry native request")
    else:
        runtime = runtime_input.environment.easycrypt_runtime
        if runtime is None:
            raise ValueError("open compiler input requires EasyCrypt runtime identity")
        if manager_result is None:
            raise ValueError("open compiler input requires native typed state")
        if not native_state_request_id:
            raise ValueError("open compiler input requires native request identity")
        native_state = native_state_snapshot(
            manager_result,
            expected_state=snapshot.state_ref,
            expected_runtime=runtime,
            expected_request_id=native_state_request_id,
        )
        if snapshot.goal_count_known and (
            native_state.open_goal_count != snapshot.goal_count
        ):
            raise ValueError("native and runtime goal counts disagree")
    return LiveCompilerInput(
        snapshot=AuthoritativeSnapshotInput(
            state_ref=snapshot.state_ref,
            provenance=snapshot.provenance,
            target=snapshot.target,
            transition=snapshot.transition,
            goal_lines=snapshot.goal_lines,
            goal_count=snapshot.goal_count,
            goal_count_known=snapshot.goal_count_known,
            closed=snapshot.closed,
            native_state=native_state,
        ),
        environment=runtime_input.environment,
        source_snapshot_id=runtime_input.source_snapshot_id,
        resource_load_report=runtime_input.resource_load_report,
    )


def attach_compiler_resources(
    initial: LiveCompilerInput,
    manager_result: dict[str, Any],
    *,
    expected_request_id: str,
) -> LiveCompilerInput:
    """Attach one distinct resource-load occurrence to an unchanged state."""

    if type(manager_result) is not dict:
        raise TypeError("manager compiler resource result must be an object")
    raw = manager_result.get("result")
    authority = manager_result.get("authority")
    if type(raw) is not dict or type(authority) is not dict:
        raise ValueError("manager compiler resource result is incomplete")
    validation = validate_compiler_resource_load(raw)
    if not validation.ok:
        raise ValueError(
            "manager compiler resource result is invalid: "
            + "; ".join(validation.errors)
        )
    if manager_result.get("history_unchanged") is not True or (
        manager_result.get("state_version_before")
        != manager_result.get("state_version_after")
    ):
        raise ValueError("compiler resource loading changed manager proof state")
    if raw.get("request_id") != expected_request_id:
        raise ValueError("compiler resource result has another request identity")
    if raw.get("source_snapshot_id") != initial.source_snapshot_id:
        raise ValueError("compiler resource result has another source snapshot")
    if raw.get("source_event_id") != initial.snapshot.provenance.source_event_id:
        raise ValueError("compiler resource result has another source occurrence")
    if raw.get("state") != initial.snapshot.state_ref.identity_payload():
        raise ValueError("compiler resource result belongs to another StateRef")
    source_unit = initial.environment.source_units[0]
    target = raw.get("target")
    if type(target) is not dict or any((
        target.get("source_file") != source_unit.source_ref,
        target.get("source_sha256") != source_unit.source_sha256,
        target.get("lemma") != initial.snapshot.target.lemma,
    )):
        raise ValueError("compiler resource result target drifted")
    runtime = EasyCryptRuntimeIdentity.from_payload(raw.get("easycrypt_runtime"))
    if runtime != initial.environment.easycrypt_runtime:
        raise ValueError("compiler resource result used another EasyCrypt runtime")
    if authority.get("event_type") != "compiler.resources.loaded":
        raise ValueError("compiler resource result has the wrong authority event")
    event_id = str(authority.get("event_id") or "")
    event_sequence = authority.get("event_sequence")
    artifact_ref = str(authority.get("artifact_ref") or "")
    artifact_sha256 = str(authority.get("artifact_sha256") or "")
    if not event_id or type(event_sequence) is not int or event_sequence <= 0:
        raise ValueError("compiler resource event occurrence is incomplete")
    if not artifact_ref or not _SHA256_RE.fullmatch(artifact_sha256):
        raise ValueError("compiler resource artifact authority is incomplete")
    return LiveCompilerInput(
        snapshot=initial.snapshot,
        environment=CompilationEnvironment(
            environment_id=f"compiler-resources:{event_id}",
            source_units=initial.environment.source_units,
            loaded_declarations=_exact_loaded_declarations(
                raw.get("loaded_declarations")
            ),
            easycrypt_runtime=runtime,
            native_semantic_observations=(
                initial.environment.native_semantic_observations
            ),
        ),
        source_snapshot_id=initial.source_snapshot_id,
        resource_load_report=_exact_resource_load_report(
            raw.get("resource_load_report")
        ),
    )


def native_state_snapshot(
    manager_result: dict[str, Any],
    *,
    expected_state: StateRef,
    expected_runtime: EasyCryptRuntimeIdentity,
    expected_request_id: str,
) -> NativeProofStateSnapshot:
    """Convert exactly one manager/event-bound typed-state occurrence."""

    if type(manager_result) is not dict:
        raise TypeError("manager native state result must be an object")
    raw = manager_result.get("result")
    authority = manager_result.get("authority")
    if type(raw) is not dict or type(authority) is not dict:
        raise ValueError("manager native state result is incomplete")
    validation = validate_native_state_artifact(raw)
    if not validation.ok:
        raise ValueError(
            "manager native state result is invalid: "
            + "; ".join(validation.errors)
        )
    request = raw.get("request")
    if type(request) is not dict or request.get("request_id") != expected_request_id:
        raise ValueError("native state result does not match planned request")
    if manager_result.get("history_unchanged") is not True or (
        manager_result.get("state_version_before")
        != manager_result.get("state_version_after")
    ):
        raise ValueError("native state query changed manager proof state")
    state = raw.get("state")
    if type(state) is not dict or any((
        state.get("session_id") != expected_state.session_id,
        state.get("state_version") != expected_state.state_version,
        state.get("goal_identity") != expected_state.goal_identity,
        state.get("goal_identity_required")
        is not expected_state.goal_identity_required,
        state.get("committed_prefix_identity")
        != expected_state.committed_prefix_identity,
    )):
        raise ValueError("native state result belongs to another StateRef")
    goal_before = raw.get("result", {}).get("goal_before")
    if type(goal_before) is not str or (
        active_goal_hash_from_raw(goal_before) != expected_state.goal_identity
    ):
        raise ValueError("native state goal text disagrees with its StateRef")
    runtime = EasyCryptRuntimeIdentity.from_payload(raw.get("easycrypt_runtime"))
    if runtime != expected_runtime:
        raise ValueError("native state result used another EasyCrypt runtime")
    companion = NativeCompanionIdentity.from_payload(raw.get("native_companion"))
    if companion.easycrypt_toolchain_build_id != runtime.build_id:
        raise ValueError("native state runtime/toolchain build IDs differ")
    if authority.get("event_type") != "native.state.produced":
        raise ValueError("native state result has the wrong authority event")
    event_id = str(authority.get("event_id") or "")
    event_sequence = authority.get("event_sequence")
    artifact_ref = str(authority.get("artifact_ref") or "")
    artifact_sha256 = str(authority.get("artifact_sha256") or "")
    if not event_id or type(event_sequence) is not int or event_sequence <= 0:
        raise ValueError("native state event occurrence is incomplete")
    if not artifact_ref or not _SHA256_RE.fullmatch(artifact_sha256):
        raise ValueError("native state artifact authority is incomplete")
    result = raw["result"]
    return NativeProofStateSnapshot(
        state_ref=expected_state,
        request_id=request["request_id"],
        projection=freeze_json_object(result["projection"]),
        runtime_identity_sha256=runtime.semantic_identity_sha256,
        companion_identity_sha256=companion.semantic_identity_sha256,
        provenance=ProvenanceRef(
            producer="runtime.native_state",
            authority="native.state.produced",
            source_sha256=artifact_sha256,
            artifact_ref=artifact_ref,
            source_event_id=event_id,
            source_event_sequence=event_sequence,
            authoritative=True,
        ),
        elapsed_ms=result["elapsed_ms"],
    )


def native_semantic_observations(
    manager_result: dict[str, Any],
    *,
    execution_units: tuple[NativeSemanticExecutionUnit, ...],
    expected_batch_id: str,
    expected_runtime: EasyCryptRuntimeIdentity,
) -> tuple[NativeSemanticObservation, ...]:
    """Split one event-bound batch into ordered typed observations."""

    if type(manager_result) is not dict:
        raise TypeError("manager native semantic batch result must be an object")
    raw = manager_result.get("result")
    authority = manager_result.get("authority")
    if type(raw) is not dict or type(authority) is not dict:
        raise ValueError("manager native semantic batch result is incomplete")
    validation = validate_native_semantic_batch_result(raw)
    if not validation.ok:
        raise ValueError(
            "manager native semantic batch result is invalid: "
            + "; ".join(validation.errors)
        )
    if manager_result.get("history_unchanged") is not True or (
        manager_result.get("state_version_before")
        != manager_result.get("state_version_after")
    ):
        raise ValueError("native semantic batch changed manager proof state")

    raw_request = raw.get("request")
    state = raw.get("state")
    expected_request = {
        "batch_id": expected_batch_id,
        "members": [unit.runtime_payload() for unit in execution_units],
    }
    if raw_request != expected_request:
        raise ValueError("native semantic batch does not match its plan")
    if not execution_units:
        raise ValueError("native semantic batch plan is empty")
    expected_state = execution_units[0].state_ref
    if any(unit.state_ref != expected_state for unit in execution_units):
        raise ValueError("native semantic batch plan crosses StateRef")
    if type(state) is not dict or any((
        state.get("session_id") != expected_state.session_id,
        state.get("state_version") != expected_state.state_version,
        state.get("goal_identity") != expected_state.goal_identity,
        state.get("goal_identity_required")
        is not expected_state.goal_identity_required,
        state.get("committed_prefix_identity")
        != expected_state.committed_prefix_identity,
    )):
        raise ValueError("native semantic batch belongs to another StateRef")
    result = raw.get("result")
    goal_before = result.get("goal_before") if type(result) is dict else None
    if type(goal_before) is not str or (
        active_goal_hash_from_raw(goal_before) != expected_state.goal_identity
    ):
        raise ValueError("native semantic batch goal disagrees with its StateRef")

    runtime = EasyCryptRuntimeIdentity.from_payload(raw.get("easycrypt_runtime"))
    if runtime != expected_runtime:
        raise ValueError("native semantic batch used another EasyCrypt runtime")
    companion = NativeCompanionIdentity.from_payload(raw.get("native_companion"))
    if companion.easycrypt_toolchain_build_id != runtime.build_id:
        raise ValueError("native semantic batch runtime/toolchain build IDs differ")

    if authority.get("event_type") != "native.semantic.batch.produced":
        raise ValueError("native semantic batch has the wrong authority event")
    event_id = str(authority.get("event_id") or "")
    event_sequence = authority.get("event_sequence")
    artifact_ref = str(authority.get("artifact_ref") or "")
    artifact_sha256 = str(authority.get("artifact_sha256") or "")
    if not event_id or type(event_sequence) is not int or event_sequence <= 0:
        raise ValueError("native semantic batch event occurrence is incomplete")
    if not artifact_ref or not _SHA256_RE.fullmatch(artifact_sha256):
        raise ValueError("native semantic batch artifact authority is incomplete")
    provenance = ProvenanceRef(
        producer="runtime.native_semantic_batch",
        authority="native.semantic.batch.produced",
        source_sha256=artifact_sha256,
        artifact_ref=artifact_ref,
        source_event_id=event_id,
        source_event_sequence=event_sequence,
        authoritative=True,
    )
    result = raw["result"]
    members = result["members"]
    batch_size = len(execution_units)
    observations = []
    for batch_index, (unit, member) in enumerate(zip(execution_units, members)):
        descriptor = None
        if member["status"] == "accepted":
            if unit.query_kind == "proof_term_elaboration":
                descriptor = _native_proof_term_descriptor(member["descriptor"])
            elif unit.query_kind == "selected_application_binding_set":
                descriptor = _native_selected_application_binding_set_descriptor(
                    member["descriptor"]
                )
            elif unit.query_kind == "attempt_diagnostic":
                descriptor = _native_attempted_operation_descriptor(
                    member["descriptor"]
                )
            else:
                descriptor = _native_tactic_prefix_descriptor(
                    member["descriptor"]
                )
        for request in unit.requests:
            common = {
                "request": request,
                "batch_id": expected_batch_id,
                "batch_index": batch_index,
                "batch_size": batch_size,
                "batch_cache_state": result["cache_state"],
                "batch_build_elapsed_ms": result["build_elapsed_ms"],
                "batch_execution_elapsed_ms": result["execution_elapsed_ms"],
                "batch_elapsed_ms": result["elapsed_ms"],
                "runtime_identity_sha256": runtime.semantic_identity_sha256,
                "companion_identity_sha256": companion.semantic_identity_sha256,
                "elapsed_ms": member["elapsed_ms"],
                "provenance": provenance,
            }
            if member["status"] == "accepted":
                observations.append(NativeSemanticObservation.accepted(
                    result_formula=member["result_formula"],
                    descriptor=descriptor,
                    **common,
                ))
            else:
                observations.append(NativeSemanticObservation.rejected(
                    structured_error=dict(member["structured_error"]),
                    **common,
                ))
    return tuple(observations)


def _native_proof_term_descriptor(
    value: dict[str, Any],
) -> NativeProofTermDescriptor:
    head = _native_resolved_head(value["resolved_head"])
    input_arguments = tuple(
        NativeInputArgument(
            position=item["position"],
            syntax_kind=item["syntax_kind"],
            explicit_hole=item["explicit_hole"],
            source_spelling=str(item.get("source_spelling") or ""),
        )
        for item in value["input_arguments"]
    )
    arguments = []
    for item in value["arguments"]:
        actual = item["actual"]
        expected = item["expected"]
        arguments.append(NativeProofTermArgument(
            position=item["position"],
            kind=actual["kind"],
            hole=actual["hole"],
            expected_name=str(expected.get("name") or ""),
            expected_type=str(expected.get("type") or ""),
            expected_formula=(
                _native_formula_descriptor(expected["formula"])
                if isinstance(expected.get("formula"), dict)
                else None
            ),
            resolved_identity=str(actual.get("identity") or ""),
            resolved_formula=(
                _native_formula_descriptor(actual["formula"])
                if isinstance(actual.get("formula"), dict)
                else None
            ),
            resolved_proof_head=(
                _native_resolved_head(actual["head"])
                if isinstance(actual.get("head"), dict)
                else None
            ),
        ))
    residuals = tuple(
        NativeResidualProofPremise(
            argument_position=item["argument_position"],
            formula=_native_formula_descriptor(item["formula"]),
        )
        for item in value["residual_proof_premises"]
    )
    return NativeProofTermDescriptor(
        resolved_head=head,
        input_mode=value["input_mode"],
        input_arguments=input_arguments,
        explicit_hole_count=value["explicit_hole_count"],
        implicit_argument_count=value["implicit_argument_count"],
        arguments=tuple(arguments),
        can_concretize=value["can_concretize"],
        residual_proof_premises=residuals,
        result=_native_formula_descriptor(value["result"]),
        result_convertible_to_current_goal=(
            value["result_convertible_to_current_goal"]
        ),
    )


def _native_selected_application_binding_set_descriptor(
    value: dict[str, Any],
) -> NativeSelectedApplicationBindingSetDescriptor:
    return NativeSelectedApplicationBindingSetDescriptor(
        operation=value["operation"],
        selected_resource=value["selected_resource"],
        resolved_head=_native_resolved_head(value["resolved_head"]),
        module_slot_count=value["module_slot_count"],
        candidate_module_term_count=value["candidate_module_term_count"],
        candidate_check_count=value["candidate_check_count"],
        typed_binding_count=value["typed_binding_count"],
        checked_completion_count=value["checked_completion_count"],
        population_complete=value["population_complete"],
        checked_completions=tuple(
            NativeCheckedApplication(
                application_term=item["application_term"],
                candidate_tactic=item["candidate_tactic"],
                tactic_effect=item["tactic_effect"],
                descriptor=_native_proof_term_descriptor(item["descriptor"]),
            )
            for item in value["checked_completions"]
        ),
        reason=value["reason"],
    )


def _native_tactic_prefix_descriptor(
    value: dict[str, Any],
) -> NativeTacticPrefixDiagnosticDescriptor:
    boundary_attempt = value.get("boundary_attempt")
    return NativeTacticPrefixDiagnosticDescriptor(
        rejected_tactic=value["rejected_tactic"],
        candidate_prefixes=tuple(value["candidate_prefixes"]),
        prefix_effects=tuple(value["prefix_effects"]),
        accepted_prefixes=tuple(value["accepted_prefixes"]),
        boundary_tactic=value["boundary_tactic"],
        native_failure_kind=value["native_failure_kind"],
        native_error_message=value["native_error_message"],
        boundary_failure_kind=value["boundary_failure_kind"],
        boundary_error_message=value["boundary_error_message"],
        goal_kind=value["goal_kind"],
        boundary_attempt=(
            _native_attempted_operation_descriptor(boundary_attempt)
            if isinstance(boundary_attempt, dict)
            else None
        ),
    )


def _native_attempted_operation_descriptor(
    value: dict[str, Any],
) -> NativeAttemptedOperationDescriptor:
    proof_term = value.get("proof_term")
    application_head = value.get("application_head")
    relation_bridge = value.get("relation_bridge")
    relation_bridge_choice = value.get("relation_bridge_choice")
    phl_boundary = value.get("phl_transitivity_boundary")
    eager_while = value.get("eager_while_dialect")
    pure_tail_rewrite = value.get("pure_tail_rewrite")
    intro_pattern_realization = value.get("intro_pattern_realization")
    application_syntax = value.get("application_syntax_repair")
    return NativeAttemptedOperationDescriptor(
        operation_family=value["operation_family"],
        rejected_tactic=value["rejected_tactic"],
        exact_resource=value["exact_resource"],
        argument_kinds=tuple(value["argument_kinds"]),
        side=value["side"],
        positions=tuple(value["positions"]),
        native_diagnostic_status=value["native_diagnostic_status"],
        native_failure_kind=value["native_failure_kind"],
        native_error_message=value["native_error_message"],
        attempt_outcome=value["attempt_outcome"],
        goal_kind=value["goal_kind"],
        application_head=(
            _native_application_head_descriptor(application_head)
            if isinstance(application_head, dict)
            else None
        ),
        proof_term=(
            _native_proof_term_descriptor(proof_term)
            if isinstance(proof_term, dict)
            else None
        ),
        relation_bridge=(
            NativeRelationBridgeDescriptor(
                source_operation=relation_bridge["source_operation"],
                relation_family=relation_bridge["relation_family"],
                intermediate_text=relation_bridge["intermediate_text"],
                intermediate_type_text=relation_bridge["intermediate_type"],
                candidate_tactic=relation_bridge["candidate_tactic"],
                failure_kind=relation_bridge["failure_kind"],
                source_target_present=relation_bridge["source_target_present"],
                source_target_convertible_to_current_goal=(
                    relation_bridge["source_target_convertible_to_current_goal"]
                ),
                source_target_right_convertible_to_current_right=(
                    relation_bridge[
                        "source_target_right_convertible_to_current_right"
                    ]
                ),
            )
            if isinstance(relation_bridge, dict)
            else None
        ),
        relation_bridge_choice=(
            NativeRelationBridgeChoiceDescriptor(
                source_operation=relation_bridge_choice["source_operation"],
                relation_family=relation_bridge_choice["relation_family"],
                goal_left_text=relation_bridge_choice["goal_left_text"],
                intermediate_text=relation_bridge_choice["intermediate_text"],
                goal_right_text=relation_bridge_choice["goal_right_text"],
                intermediate_type_text=(
                    relation_bridge_choice["intermediate_type"]
                ),
                failure_kind=relation_bridge_choice["failure_kind"],
                choices=tuple(
                    NativeRelationBridgeChoice(
                        certificate_family=item["certificate_family"],
                        left_relation=item["left_relation"],
                        right_relation=item["right_relation"],
                        candidate_tactic=item["candidate_tactic"],
                    )
                    for item in relation_bridge_choice["choices"]
                ),
            )
            if isinstance(relation_bridge_choice, dict)
            else None
        ),
        phl_transitivity_boundary=(
            NativePhlTransitivityBoundaryDescriptor(
                source_operation=phl_boundary["source_operation"],
                attempted_form=phl_boundary["attempted_form"],
                current_goal_form=phl_boundary["current_goal_form"],
                side=phl_boundary["side"],
                failure_kind=phl_boundary["failure_kind"],
            )
            if isinstance(phl_boundary, dict)
            else None
        ),
        eager_while_dialect=(
            NativeEagerWhileDialectDescriptor(
                source_operation=eager_while["source_operation"],
                eager_subform=eager_while["eager_subform"],
                attempted_shape=eager_while["attempted_shape"],
                failure_kind=eager_while["failure_kind"],
                candidates=tuple(
                    NativeEagerWhileCandidateDescriptor(
                        invariant_text=item["invariant_text"],
                        candidate_tactic=item["candidate_tactic"],
                    )
                    for item in eager_while["candidates"]
                ),
            )
            if isinstance(eager_while, dict)
            else None
        ),
        pure_tail_rewrite=(
            NativePureTailRewriteDescriptor(
                source_operation=pure_tail_rewrite["source_operation"],
                selected_resource=pure_tail_rewrite["selected_resource"],
                target_kind=pure_tail_rewrite["target_kind"],
                target_name=pure_tail_rewrite["target_name"],
                candidate_tactic=pure_tail_rewrite["candidate_tactic"],
                failure_kind=pure_tail_rewrite["failure_kind"],
                accepted_target_count=(
                    pure_tail_rewrite["accepted_target_count"]
                ),
            )
            if isinstance(pure_tail_rewrite, dict)
            else None
        ),
        intro_pattern_realization=(
            NativeIntroPatternRepairDescriptor(
                source_operation=intro_pattern_realization["source_operation"],
                surface_operation=intro_pattern_realization["surface_operation"],
                attempted_pattern_kind=(
                    intro_pattern_realization["attempted_pattern_kind"]
                ),
                binder_names=tuple(intro_pattern_realization["binder_names"]),
                candidate_tactic=intro_pattern_realization["candidate_tactic"],
                failure_kind=intro_pattern_realization["failure_kind"],
                selected_pattern_count=(
                    intro_pattern_realization["selected_pattern_count"]
                ),
            )
            if isinstance(intro_pattern_realization, dict)
            else None
        ),
        application_syntax_repair=(
            NativeApplicationSyntaxRepairDescriptor(
                source_operation=application_syntax["source_operation"],
                selected_resource=application_syntax["selected_resource"],
                module_argument_position=(
                    application_syntax["module_argument_position"]
                ),
                module_term_text=application_syntax["module_term_text"],
                candidate_application_term=(
                    application_syntax["candidate_application_term"]
                ),
                candidate_tactic=application_syntax["candidate_tactic"],
                candidate_argument_kinds=tuple(
                    application_syntax["candidate_argument_kinds"]
                ),
                failure_kind=application_syntax["failure_kind"],
                resolved_candidate_count=(
                    application_syntax["resolved_candidate_count"]
                ),
            )
            if isinstance(application_syntax, dict)
            else None
        ),
    )


def _native_application_head_descriptor(
    value: dict[str, Any],
) -> NativeApplicationHeadDescriptor:
    return NativeApplicationHeadDescriptor(
        resolved_head=_native_resolved_head(value["resolved_head"]),
        input_mode=value["input_mode"],
        input_arguments=tuple(
            NativeInputArgument(
                position=item["position"],
                syntax_kind=item["syntax_kind"],
                explicit_hole=item["explicit_hole"],
                source_spelling=str(item.get("source_spelling") or ""),
            )
            for item in value["input_arguments"]
        ),
        slots=tuple(
            NativeApplicationSlotDescriptor(
                position=item["position"],
                kind=item["kind"],
                name=str(item.get("name") or ""),
                type_text=str(item.get("type") or ""),
                formula=(
                    _native_formula_descriptor(item["formula"])
                    if isinstance(item.get("formula"), dict)
                    else None
                ),
            )
            for item in value["slots"]
        ),
        result=_native_formula_descriptor(value["result"]),
    )


def _native_resolved_head(value: dict[str, Any]) -> NativeResolvedHead:
    return NativeResolvedHead(
        kind=value["kind"],
        identity=value["identity"],
        type_arguments=tuple(value["type_arguments"]),
    )


def _native_formula_descriptor(
    value: dict[str, Any],
) -> NativeFormulaDescriptor:
    boundary = value.get("boundary")
    return NativeFormulaDescriptor(
        kind=value["kind"],
        text=value["text"],
        type_text=value["type"],
        procedure=str(value.get("procedure") or ""),
        comparison=str(value.get("comparison") or ""),
        lossless=value.get("lossless"),
        boundary=(
            _native_formula_boundary_descriptor(boundary)
            if isinstance(boundary, dict)
            else None
        ),
    )


def _native_formula_boundary_descriptor(
    value: dict[str, Any],
) -> NativeFormulaBoundaryDescriptor:
    return NativeFormulaBoundaryDescriptor(
        role=value["role"],
        procedure_identity=value["procedure_identity"],
        module=_native_module_term_descriptor(value["module"]),
    )


def _native_module_term_descriptor(
    value: dict[str, Any],
) -> NativeModuleTermDescriptor:
    return NativeModuleTermDescriptor(
        term=value["term"],
        top_kind=value["top_kind"],
        top_identity=value["top_identity"],
        arguments=tuple(
            _native_module_term_descriptor(item)
            for item in value["arguments"]
        ),
    )


def _exact_int(value: object, field: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"compiler input {field} must be a non-negative integer")
    return value


def _exact_bool(value: object, field: str) -> bool:
    if type(value) is not bool:
        raise ValueError(f"compiler input {field} must be a boolean")
    return value


def _exact_string_list(value: object) -> tuple[str, ...]:
    if type(value) is not list or not all(type(item) is str for item in value):
        raise ValueError("compiler input goal_lines must be a string list")
    return tuple(value)


def _exact_loaded_declarations(value: object) -> tuple[LoadedDeclaration, ...]:
    if type(value) is not list:
        raise ValueError("compiler resource loaded_declarations must be a list")
    declarations = []
    for index, item in enumerate(value):
        if type(item) is not dict:
            raise ValueError(f"compiler loaded declaration {index} is not an object")
        declarations.append(LoadedDeclaration(
            symbol=str(item.get("symbol") or ""),
            source_ref=str(item.get("source_ref") or ""),
            declaration_sha256=str(item.get("declaration_sha256") or ""),
            declaration=str(item.get("declaration") or ""),
        ))
    return tuple(declarations)


def _exact_resource_load_report(value: object) -> tuple[dict[str, Any], ...]:
    if type(value) is not list:
        raise ValueError("compiler resource_load_report must be a list")
    reports = []
    seen: set[str] = set()
    for index, item in enumerate(value):
        if type(item) is not dict:
            raise ValueError(f"compiler resource report {index} is not an object")
        request_id = str(item.get("request_id") or "")
        if not request_id or request_id in seen:
            raise ValueError("compiler resource reports need unique request IDs")
        seen.add(request_id)
        reports.append(dict(item))
    return tuple(reports)
