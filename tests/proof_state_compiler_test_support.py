"""Explicit native typed-state fixtures for compiler unit tests."""

from __future__ import annotations

from typing import Any

from core.easycrypt.proof_state_compiler.contracts import (
    NativeApplicationHeadDescriptor,
    NativeApplicationSyntaxRepairDescriptor,
    NativeApplicationSlotDescriptor,
    NativeEagerWhileDialectDescriptor,
    NativeIntroPatternRepairDescriptor,
    NativeFormulaDescriptor,
    NativeAttemptedOperationDescriptor,
    NativeAttemptDiagnosticQuery,
    NativeInputArgument,
    NativePhlTransitivityBoundaryDescriptor,
    NativePureTailRewriteDescriptor,
    NativeProofTermArgument,
    NativeProofTermDescriptor,
    NativeRelationBridgeChoiceDescriptor,
    NativeRelationBridgeDescriptor,
    NativeProofStateSnapshot,
    NativeResidualProofPremise,
    NativeResolvedHead,
    NativeSemanticObservation,
    NativeSemanticRequest,
    ProvenanceRef,
    StateRef,
    freeze_json_object,
)
from core.easycrypt.proof_state_compiler.syntax.attempted_operation import (
    single_operation_identity,
)
from core.easycrypt.ec_runtime_identity import EasyCryptRuntimeIdentity
from core.easycrypt.native_semantics import NativeCompanionIdentity


def typed_node(
    kind: str,
    text: str,
    *,
    type_text: str = "bool",
    children: tuple[dict[str, Any], ...] = (),
    child_roles: tuple[str, ...] = (),
    **properties: object,
) -> dict[str, Any]:
    value: dict[str, Any] = {
        "kind": kind,
        "complete": True,
        "text": text,
        "type": type_text,
        "children": list(children),
        **properties,
    }
    if child_roles:
        value["child_roles"] = list(child_roles)
    return value


def module_path(
    term: str,
    *arguments: dict[str, Any],
    top_kind: str = "concrete",
    top_identity: str | None = None,
) -> dict[str, Any]:
    """Version-two native module-path fixture."""

    return {
        "term": term,
        "top_kind": top_kind,
        "top_identity": top_identity or term.split("(", 1)[0],
        "arguments": list(arguments),
    }


def instruction(
    kind: str,
    text: str,
    *,
    side: str,
    position: int,
    procedure: str = "",
) -> dict[str, Any]:
    value: dict[str, Any] = {
        "kind": kind,
        "complete": True,
        "structural_path": [side, str(position)],
        "top_level_position": position,
        "text": text,
    }
    if kind == "call":
        value.update({"procedure": procedure, "target": None, "arguments": []})
    elif kind == "assign":
        value.update({
            "target": {
                "kind": "variable",
                "variables": [{
                    "kind": "local",
                    "identity": "x",
                    "display": "x",
                    "type": "int",
                }],
            },
            "value": typed_node("integer", "0", type_text="int"),
        })
    elif kind == "sample":
        value.update({
            "target": {
                "kind": "variable",
                "variables": [{
                    "kind": "local",
                    "identity": "x",
                    "display": "x",
                    "type": "int",
                }],
            },
            "distribution": typed_node("local", "d", type_text="int distr"),
        })
    return value


def program(
    side: str,
    instructions: tuple[dict[str, Any], ...],
) -> dict[str, Any]:
    return {
        "side": side,
        "role": "body" if side == "single" else f"{side}_body",
        "memory": "&m" if side == "single" else f"&{1 if side == 'left' else 2}",
        "statement": {
            "kind": "statement",
            "complete": True,
            "structural_path": [side],
            "text": " ".join(str(item["text"]) for item in instructions),
            "instructions": list(instructions),
        },
    }


def native_state(
    state_ref: StateRef,
    *,
    judgment_kind: str = "pure",
    formula: dict[str, Any] | None = None,
    programs: tuple[dict[str, Any], ...] = (),
    locals_value: tuple[dict[str, Any], ...] = (),
    complete: bool = True,
    artifact_ref: str = "native_state_projections/test.json",
) -> NativeProofStateSnapshot:
    formula = formula or typed_node("true", "true")
    projection = {
        "complete": complete,
        "truncation_reasons": [] if complete else ["test_incomplete"],
        "node_count": 1,
        "open_goal_count": 1,
        "focused_goal": {
            "judgment_kind": judgment_kind,
            "formula": formula,
            "programs": list(programs),
            "procedures": [],
        },
        "local_declarations": list(locals_value),
    }
    return NativeProofStateSnapshot(
        state_ref=state_ref,
        request_id="native-test-request",
        projection=freeze_json_object(projection),
        runtime_identity_sha256="c" * 64,
        companion_identity_sha256="d" * 64,
        provenance=ProvenanceRef(
            producer="test.native_state",
            authority="native.state.produced",
            source_sha256="e" * 64,
            artifact_ref=artifact_ref,
            source_event_id="native-state-test-event",
            source_event_sequence=1,
            authoritative=True,
        ),
        elapsed_ms=1,
    )


def m05_native_state(
    state_ref: StateRef,
    *,
    locals_value: tuple[dict[str, Any], ...] = (),
    canonical_paths: bool = False,
) -> NativeProofStateSnapshot:
    """Typed equivalent of the ledger-pinned M05 post-``proc`` state."""

    truth = typed_node("true", "true")
    bound = typed_node("operator_application", "1%r", type_text="real")
    formula = typed_node(
        "bounded_hoare_statement",
        "phoare[statement : true ==> true] = 1%r",
        children=(truth, truth, bound),
        child_roles=("precondition", "postcondition", "bound"),
        comparison="=",
        memory="&m",
    )
    initializer = (
        "Top.D2(O).O./init" if canonical_paths else "D2(O).O.init"
    )
    active = (
        "Top.Adv_MAC_to_F(A, Top.D2(O).O)./guess"
        if canonical_paths
        else "Adv_MAC_to_F(A, D2(O).O).guess"
    )
    calls = (
        instruction(
            "call",
            f"_ <@ {initializer}()",
            side="single",
            position=1,
            procedure=initializer,
        ),
        instruction(
            "call",
            f"_ <@ {active}()",
            side="single",
            position=2,
            procedure=active,
        ),
    )
    return native_state(
        state_ref,
        judgment_kind="bounded_hoare_statement",
        formula=formula,
        programs=(program("single", calls),),
        locals_value=locals_value,
    )


def m05_native_observation(
    request: NativeSemanticRequest,
    *,
    target_procedure: str = "Adv_MAC_to_F(A, D2(O).O).guess",
    module_identity: str = "D2(O).O",
    premise_procedure: str = "D2(O).O.f",
) -> NativeSemanticObservation:
    """Typed equivalent of the accepted N1e descriptor for M05 unit tests."""

    descriptor = m05_native_descriptor(
        target_procedure=target_procedure,
        module_identity=module_identity,
        premise_procedure=premise_procedure,
    )
    return NativeSemanticObservation.accepted(
        request=request,
        batch_id=f"test-batch-{request.request_id}",
        batch_index=0,
        batch_size=1,
        batch_elapsed_ms=2,
        result_formula=descriptor.result.text,
        descriptor=descriptor,
        runtime_identity_sha256="a" * 64,
        companion_identity_sha256="b" * 64,
        elapsed_ms=2,
        provenance=ProvenanceRef(
            producer="test.native_proof_term",
            authority="native.semantic.batch.produced",
            source_sha256="f" * 64,
            artifact_ref="native_semantic_batches/m05-test.json",
            source_event_id="native-semantic-m05-test",
            source_event_sequence=2,
            authoritative=True,
        ),
    )


def bare_native_observation(
    request: NativeSemanticRequest,
    *,
    resolved_head: str,
    result_formula: NativeFormulaDescriptor | None = None,
) -> NativeSemanticObservation:
    """Accepted native descriptor for one bare global proof-term head."""

    result = result_formula or NativeFormulaDescriptor(
        kind="true",
        text="true",
        type_text="bool",
    )
    descriptor = NativeProofTermDescriptor(
        resolved_head=NativeResolvedHead(
            kind="global",
            identity=resolved_head,
        ),
        input_mode="implicit",
        input_arguments=(),
        explicit_hole_count=0,
        implicit_argument_count=0,
        arguments=(),
        can_concretize=True,
        residual_proof_premises=(),
        result=result,
        result_convertible_to_current_goal=True,
    )
    return NativeSemanticObservation.accepted(
        request=request,
        batch_id=f"test-batch-{request.request_id}",
        batch_index=0,
        batch_size=1,
        batch_elapsed_ms=2,
        result_formula=result.text,
        descriptor=descriptor,
        runtime_identity_sha256="a" * 64,
        companion_identity_sha256="b" * 64,
        elapsed_ms=2,
        provenance=ProvenanceRef(
            producer="test.native_proof_term",
            authority="native.semantic.batch.produced",
            source_sha256="f" * 64,
            artifact_ref="native_semantic_batches/bare-test.json",
            source_event_id="native-semantic-bare-test",
            source_event_sequence=2,
            authoritative=True,
        ),
    )


def attempted_operation_native_observation(
    request: NativeSemanticRequest,
    *,
    failure_kind: str = "proof_term_lookup_failure",
    goal_kind: str = "formula",
    diagnostic_status: str | None = None,
    argument_kinds: tuple[str, ...] = (),
    side: str = "",
    application_head: NativeApplicationHeadDescriptor | None = None,
    relation_bridge: NativeRelationBridgeDescriptor | None = None,
    relation_bridge_choice: NativeRelationBridgeChoiceDescriptor | None = None,
    phl_transitivity_boundary: (
        NativePhlTransitivityBoundaryDescriptor | None
    ) = None,
    eager_while_dialect: NativeEagerWhileDialectDescriptor | None = None,
    pure_tail_rewrite: NativePureTailRewriteDescriptor | None = None,
    intro_pattern_repair: NativeIntroPatternRepairDescriptor | None = None,
    application_syntax_repair: (
        NativeApplicationSyntaxRepairDescriptor | None
    ) = None,
) -> NativeSemanticObservation:
    """Accepted native parse/applicability descriptor for a rejected tactic."""

    if not isinstance(request.query, NativeAttemptDiagnosticQuery):
        raise ValueError("attempt fixture requires a diagnostic query")
    parsed = single_operation_identity(request.query.rejected_tactic)
    relation_descriptor = (
        relation_bridge
        or relation_bridge_choice
        or phl_transitivity_boundary
        or eager_while_dialect
        or pure_tail_rewrite
        or intro_pattern_repair
        or application_syntax_repair
    )
    if parsed is None and pure_tail_rewrite is not None:
        parsed = (
            pure_tail_rewrite.source_operation,
            pure_tail_rewrite.selected_resource,
        )
    elif parsed is None and relation_descriptor is not None:
        parsed = (relation_descriptor.source_operation, "")
    if parsed is None:
        raise ValueError("attempt fixture requires one bounded operation")
    operation, resource = parsed
    status = diagnostic_status or (
        "blocker" if failure_kind else "no_blocker"
    )
    descriptor = NativeAttemptedOperationDescriptor(
        operation_family=operation,
        rejected_tactic=request.query.rejected_tactic,
        exact_resource=resource,
        argument_kinds=argument_kinds,
        side=side,
        positions=(),
        native_diagnostic_status=status,
        native_failure_kind=failure_kind,
        native_error_message=(
            "synthetic native rejected attempt" if failure_kind else ""
        ),
        attempt_outcome=request.query.observed_outcome_kind,
        goal_kind=goal_kind,
        application_head=application_head,
        relation_bridge=relation_bridge,
        relation_bridge_choice=relation_bridge_choice,
        phl_transitivity_boundary=phl_transitivity_boundary,
        eager_while_dialect=eager_while_dialect,
        pure_tail_rewrite=pure_tail_rewrite,
        intro_pattern_realization=intro_pattern_repair,
        application_syntax_repair=application_syntax_repair,
    )
    return NativeSemanticObservation.accepted(
        request=request,
        batch_id=f"test-batch-{request.request_id}",
        batch_index=0,
        batch_size=1,
        batch_elapsed_ms=2,
        result_formula="",
        descriptor=descriptor,
        runtime_identity_sha256="a" * 64,
        companion_identity_sha256="b" * 64,
        elapsed_ms=2,
        provenance=ProvenanceRef(
            producer="test.native_attempt",
            authority="native.semantic.batch.produced",
            source_sha256="f" * 64,
            artifact_ref="native_semantic_batches/attempt-test.json",
            source_event_id="native-semantic-attempt-test",
            source_event_sequence=2,
            authoritative=True,
        ),
    )


def b2_losslessness_native_observation(
    request: NativeSemanticRequest,
    *,
    target_procedure: str,
    module_identity: str = "",
) -> NativeSemanticObservation:
    """Accepted native descriptor for the frozen B2 losslessness family."""

    if not module_identity:
        marker = "(<: "
        if marker not in request.query.application_term or not (
            request.query.application_term.endswith(") _")
        ):
            raise ValueError("B2 fixture request has unexpected application")
        module_identity = request.query.application_term.split(marker, 1)[1][:-3]
    descriptor = m05_native_descriptor(
        target_procedure=target_procedure,
        module_identity=module_identity,
        premise_procedure=f"{module_identity}.mac",
        resolved_head="Top.Alossless",
        module_expected_type="OMac",
    )
    return NativeSemanticObservation.accepted(
        request=request,
        batch_id=f"test-batch-{request.request_id}",
        batch_index=0,
        batch_size=1,
        batch_elapsed_ms=2,
        result_formula=descriptor.result.text,
        descriptor=descriptor,
        runtime_identity_sha256="a" * 64,
        companion_identity_sha256="b" * 64,
        elapsed_ms=2,
        provenance=ProvenanceRef(
            producer="test.native_proof_term",
            authority="native.semantic.batch.produced",
            source_sha256="f" * 64,
            artifact_ref="native_semantic_batches/b2-losslessness-test.json",
            source_event_id="native-semantic-b2-losslessness-test",
            source_event_sequence=2,
            authoritative=True,
        ),
    )


def probability_multislot_native_observation(
    request: NativeSemanticRequest,
    *,
    result_formula: str,
    resolved_head: str = "Top.Step1_2.CCA_UFCMA.CCA_CPA_UFCMA",
) -> NativeSemanticObservation:
    """Accepted descriptor for the frozen B2/B4 probability family."""

    parts = request.query.application_term.split()
    if len(parts) != 7:
        raise ValueError("probability fixture request has unexpected application")
    values = parts[1:]
    proof_formulas = {
        2: NativeFormulaDescriptor(
            kind="formula",
            text=(
                "equiv[ St.init ~ St.init : true ==> "
                "RO.m{1} = RO.m{2} /\\ res{1} = res{2}]"
            ),
            type_text="bool",
        ),
        3: NativeFormulaDescriptor(
            kind="hoare_function",
            text="hoare[ St.kg : true ==> true]",
            type_text="bool",
            procedure="Top.Step1_2.St./kg",
        ),
        5: NativeFormulaDescriptor(
            kind="quantifier",
            text=(
                "forall (O <: CCA_Oracles{-A}), islossless O.enc => "
                "islossless O.dec => islossless A(O).main"
            ),
            type_text="bool",
        ),
    }
    arguments = []
    residuals = []
    for position, value in enumerate(values, start=1):
        if position in {1, 4}:
            arguments.append(NativeProofTermArgument(
                position=position,
                kind="module",
                hole=False,
                expected_name="St" if position == 1 else "A",
                expected_type="StLOrcls" if position == 1 else "CCA_Adv",
                resolved_identity=value,
            ))
        elif position == 6:
            arguments.append(NativeProofTermArgument(
                position=position,
                kind="memory",
                hole=False,
                expected_name="&m",
                expected_type="{}",
                resolved_identity=value,
            ))
        else:
            expected = proof_formulas[position]
            hole = value == "_"
            arguments.append(NativeProofTermArgument(
                position=position,
                kind="proof",
                hole=hole,
                expected_formula=expected,
                resolved_proof_head=(
                    None if hole else NativeResolvedHead("global", value)
                ),
            ))
            if hole:
                residuals.append(NativeResidualProofPremise(
                    argument_position=position,
                    formula=expected,
                ))
    descriptor = NativeProofTermDescriptor(
        resolved_head=NativeResolvedHead("global", resolved_head),
        input_mode="implicit",
        input_arguments=tuple(
            NativeInputArgument(
                position=index,
                syntax_kind="hole" if value == "_" else "formula",
                explicit_hole=value == "_",
            )
            for index, value in enumerate(values, start=1)
        ),
        explicit_hole_count=sum(value == "_" for value in values),
        implicit_argument_count=0,
        arguments=tuple(arguments),
        can_concretize=True,
        residual_proof_premises=tuple(residuals),
        result=NativeFormulaDescriptor(
            kind="formula",
            text=result_formula,
            type_text="bool",
        ),
        result_convertible_to_current_goal=(
            values[0] == "St"
            and values[3] == "A"
            and values[5] == "&m"
        ),
    )
    return NativeSemanticObservation.accepted(
        request=request,
        batch_id=f"test-batch-{request.request_id}",
        batch_index=0,
        batch_size=1,
        batch_elapsed_ms=2,
        result_formula=result_formula,
        descriptor=descriptor,
        runtime_identity_sha256="a" * 64,
        companion_identity_sha256="b" * 64,
        elapsed_ms=2,
        provenance=ProvenanceRef(
            producer="test.native_proof_term",
            authority="native.semantic.batch.produced",
            source_sha256="f" * 64,
            artifact_ref="native_semantic_batches/b24-probability-test.json",
            source_event_id="native-semantic-b24-probability-test",
            source_event_sequence=2,
            authoritative=True,
        ),
    )


def m05_native_descriptor(
    *,
    target_procedure: str = "Adv_MAC_to_F(A, D2(O).O).guess",
    module_identity: str = "D2(O).O",
    premise_procedure: str = "D2(O).O.f",
    resolved_head: str = "Top.Alossless_F",
    module_expected_type: str = (
        "MyECBC.MyMAC.PRF_Oracles{-Adv_MAC_to_F(A)}"
    ),
    result_convertible_to_current_goal: bool = True,
) -> NativeProofTermDescriptor:
    return module_losslessness_native_descriptor(
        target_procedure=target_procedure,
        module_identity=module_identity,
        premise_procedures=(premise_procedure,),
        resolved_head=resolved_head,
        module_expected_type=module_expected_type,
        result_convertible_to_current_goal=result_convertible_to_current_goal,
    )


def module_losslessness_native_descriptor(
    *,
    target_procedure: str,
    module_identity: str,
    premise_procedures: tuple[str, ...],
    resolved_head: str,
    module_expected_type: str,
    result_convertible_to_current_goal: bool = False,
) -> NativeProofTermDescriptor:
    """Native one-module certificate fixture with positive proof-hole count."""

    if not premise_procedures:
        raise ValueError("losslessness fixture requires a proof premise")
    premises = tuple(
        NativeFormulaDescriptor(
            kind="bounded_hoare_function",
            text=f"islossless {procedure}",
            type_text="bool",
            procedure=procedure,
            comparison="=",
            lossless=True,
        )
        for procedure in premise_procedures
    )
    result = NativeFormulaDescriptor(
        kind="bounded_hoare_function",
        text=f"islossless {target_procedure}",
        type_text="bool",
        procedure=target_procedure,
        comparison="=",
        lossless=True,
    )
    return NativeProofTermDescriptor(
        resolved_head=NativeResolvedHead(
            kind="global",
            identity=resolved_head,
        ),
        input_mode="implicit",
        input_arguments=(
            NativeInputArgument(1, "module", False),
            *(
                NativeInputArgument(position, "hole", True)
                for position in range(2, len(premises) + 2)
            ),
        ),
        explicit_hole_count=len(premises),
        implicit_argument_count=0,
        arguments=(
            NativeProofTermArgument(
                position=1,
                kind="module",
                hole=False,
                expected_name="O",
                expected_type=module_expected_type,
                resolved_identity=module_identity,
            ),
            *(
                NativeProofTermArgument(
                    position=position,
                    kind="proof",
                    hole=True,
                    expected_formula=premise,
                    resolved_formula=premise,
                )
                for position, premise in enumerate(premises, start=2)
            ),
        ),
        can_concretize=True,
        residual_proof_premises=tuple(
            NativeResidualProofPremise(
                argument_position=position,
                formula=premise,
            )
            for position, premise in enumerate(premises, start=2)
        ),
        result=result,
        result_convertible_to_current_goal=(
            result_convertible_to_current_goal
        ),
    )


def native_state_manager_result(
    native: NativeProofStateSnapshot,
    runtime: EasyCryptRuntimeIdentity,
    *,
    event_id: str = "native-state-test-event",
    event_sequence: int = 50,
    goal_before: str = "Current goal\n\ntrue",
) -> dict[str, Any]:
    companion = NativeCompanionIdentity(
        protocol_version=2,
        easycrypt_toolchain_build_id=runtime.build_id,
        easycrypt_library_sha256="f" * 64,
        companion_binary_sha256="d" * 64,
        why3_config_sha256="e" * 64,
    )
    state = native.state_ref
    raw = {
        "schema_version": 2,
        "kind": "easycrypt_native_state_projection",
        "ok": True,
        "projection_id": f"projection-{event_id}",
        "request": {
            "request_id": native.request_id,
            "max_nodes": 4096,
            "max_depth": 128,
        },
        "state": {
            "session_id": state.session_id,
            "state_version": state.state_version,
            "goal_identity": state.goal_identity,
            "goal_identity_required": state.goal_identity_required,
            "committed_prefix_identity": state.committed_prefix_identity,
        },
        "inputs": {
            "context_sha256": "1" * 64,
            "history_sha256": "2" * 64,
        },
        "easycrypt_runtime": runtime.to_payload(),
        "native_companion": companion.identity_payload(),
        "result": {
            "goal_before": goal_before,
            "projection": native.projection.to_dict(),
            "elapsed_ms": native.elapsed_ms,
        },
        "session_files_unchanged": True,
    }
    return {
        "result": raw,
        "authority": {
            "event_type": "native.state.produced",
            "event_id": event_id,
            "event_sequence": event_sequence,
            "artifact_ref": f"native_state_projections/{event_id}.json",
            "artifact_sha256": "3" * 64,
        },
        "history_unchanged": True,
        "state_version_before": state.state_version,
        "state_version_after": state.state_version,
    }
