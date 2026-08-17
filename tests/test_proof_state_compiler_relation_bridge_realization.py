"""Contracts for native argument-preserving relation realization."""

from __future__ import annotations

import hashlib
from dataclasses import replace

import pytest

from core.easycrypt.proof_state_compiler import (
    AuthoritativeSnapshotInput,
    CompilationEnvironment,
    ProofStateCompiler,
    ProvenanceRef,
    StateRef,
)
from core.easycrypt.proof_state_compiler.backend import (
    action_surface_payload,
    admit_action_surface,
)
from core.easycrypt.proof_state_compiler.backend.recovery_handoff_lowering import (
    RECOVERY_HANDOFF_INTERNAL_PRESENTATION_BOUND_EXCEEDED,
)
from core.easycrypt.proof_state_compiler.contracts import (
    BASE_POLICY_REJECTION_REASONS,
    CERTIFICATION_MISSING_OR_REJECTED,
    CertificationResult,
    CompilerTurnEvidence,
    DeliveryPolicyDefinition,
    NativeAttemptedOperationDescriptor,
    NativeProofTermElaborationQuery,
    NativeRelationBridgeChoice,
    NativeRelationBridgeChoiceDescriptor,
    NativeRelationBridgeDescriptor,
    NativeSemanticObservation,
    NativeSemanticRequest,
    NativeSemanticRequestProduction,
    NativeTacticPrefixDiagnosticDescriptor,
    TargetRef,
    TransitionRef,
    compiler_invocation_context,
    freeze_json_object,
    failure_linked_repair_rule,
    frozen_json_sha256,
)
from core.easycrypt.proof_state_compiler.features.compound_tactic_prefix_recovery import (
    COMPOUND_TACTIC_PREFIX_RECOVERY_FEATURE_ID,
    compound_tactic_prefix_recovery_feature,
)
from core.easycrypt.proof_state_compiler.features.relation_bridge_realization import (
    RELATION_BRIDGE_REALIZATION_FEATURE_ID,
    relation_bridge_realization_feature,
)
from core.easycrypt.proof_state_compiler.features.relation_bridge_realization.surface_lowering import (
    lower_relation_bridge_realization,
)
from core.easycrypt.proof_state_compiler.features.registry import ExperimentGate
from core.easycrypt.proof_state_compiler.middle_end.native_dependencies import (
    NativeSemanticProducerBinding,
    plan_native_semantics,
)
from tests.proof_state_compiler_test_support import (
    attempted_operation_native_observation,
    native_state,
    typed_node,
)
from workflow.proof_state_compiler.configuration import (
    compiler_assembly_for_profile,
)
from workflow.proof_state_compiler.activation import AUDIT, TREATMENT
from workflow.proof_state_compiler.assembly import assemble_feature_set
from core.easycrypt.proof_state_compiler.backend.presentation import (
    PresentationContractError,
    render_action_surface_payload,
)
from workflow.proof_state_compiler.profile_ids import (
    RELATION_BRIDGE_REALIZATION_AUDIT_PROFILE,
    RELATION_BRIDGE_REALIZATION_TREATMENT_PROFILE,
)


def _state_ref() -> StateRef:
    return StateRef(
        session_id="relation-bridge-test",
        state_version=4,
        goal_identity="real-le-goal",
        goal_identity_required=True,
        committed_prefix_identity="a" * 64,
    )


def _snapshot(
    state_ref: StateRef,
    *,
    relation_operator: str = "<=",
    operand_type: str = "real",
) -> AuthoritativeSnapshotInput:
    left = typed_node("local", "x", type_text=operand_type)
    right = typed_node("local", "y", type_text=operand_type)
    formula = typed_node(
        "operator_application",
        f"x {relation_operator} y",
        children=(left, right),
        relation_operator=relation_operator,
    )
    return AuthoritativeSnapshotInput(
        state_ref=state_ref,
        provenance=ProvenanceRef(
            producer="relation-bridge.fixture",
            authority="compiler.input.produced",
            source_sha256="b" * 64,
            artifact_ref="compiler_inputs/relation-bridge.json",
            source_event_id="compiler-input-relation-bridge",
            source_event_sequence=4,
            authoritative=True,
        ),
        target=TargetRef("eval/relation_bridge.ec", "bridge"),
        transition=TransitionRef(
            "rejected", state_ref, "compiler_inputs/relation-bridge.json"
        ),
        goal_lines=("Current goal", "--------", f"x {relation_operator} y"),
        goal_count=1,
        goal_count_known=True,
        closed=False,
        native_state=native_state(state_ref, formula=formula),
    )


def _turn(state_ref: StateRef, tactic: str) -> CompilerTurnEvidence:
    return CompilerTurnEvidence(
        source_event_id="relation-bridge-failure",
        source_event_sequence=8,
        authority_kind="event_bound_tactic_execution_result",
        artifact_ref="tactic_execution_results/relation-bridge-failure.json",
        artifact_hash="c" * 64,
        hash_algorithm="sha256",
        post_state_ref=state_ref,
        intent="commit_tactic",
        payload=freeze_json_object({"tactic": tactic}),
        outcome_kind="rejected",
        proof_state_effect="unchanged",
        structured_error="native rejected relation realization",
    )


def _compile(tactic: str):
    state_ref = _state_ref()
    snapshot = _snapshot(state_ref)
    invocation = compiler_invocation_context(state_ref, _turn(state_ref, tactic))
    compiler = ProofStateCompiler(features=(relation_bridge_realization_feature(),))
    environment = CompilationEnvironment("relation-bridge-environment", (), ())
    plan = compiler.plan_native_semantics(snapshot, environment, invocation)
    assert len(plan.requests) == 1
    operation = "transitivity" if tactic.startswith("transitivity ") else "change"
    failure_kind = (
        "formula_transitivity_surface_mismatch"
        if operation == "transitivity"
        else "change_target_not_convertible"
    )
    bridge = NativeRelationBridgeDescriptor(
        source_operation=operation,
        relation_family="real_le",
        intermediate_text="0%r",
        intermediate_type_text="real",
        candidate_tactic="apply (ler_trans 0%r); first last.",
        failure_kind=failure_kind,
        source_target_present=operation == "change",
        source_target_convertible_to_current_goal=False,
        source_target_right_convertible_to_current_right=operation == "change",
    )
    observation = attempted_operation_native_observation(
        plan.requests[0],
        failure_kind=failure_kind,
        relation_bridge=bridge,
    )
    environment = environment.with_native_semantic_observations((observation,))
    return invocation, compiler.compile(snapshot, environment, invocation)


def _compile_strict_choice():
    tactic = "transitivity 0%r."
    state_ref = _state_ref()
    snapshot = _snapshot(state_ref, relation_operator="<")
    invocation = compiler_invocation_context(state_ref, _turn(state_ref, tactic))
    compiler = ProofStateCompiler(features=(relation_bridge_realization_feature(),))
    environment = CompilationEnvironment("relation-bridge-environment", (), ())
    plan = compiler.plan_native_semantics(snapshot, environment, invocation)
    assert len(plan.requests) == 1
    descriptor = NativeRelationBridgeChoiceDescriptor(
        source_operation="transitivity",
        relation_family="real_lt",
        goal_left_text="x",
        intermediate_text="0%r",
        goal_right_text="y",
        intermediate_type_text="real",
        failure_kind="formula_transitivity_surface_mismatch",
        choices=tuple(
            NativeRelationBridgeChoice(
                certificate_family=family,
                left_relation=left_relation,
                right_relation=right_relation,
                candidate_tactic=(
                    f"apply ({family} 0%r); first last."
                ),
            )
            for family, left_relation, right_relation in (
                ("ler_lt_trans", "<=", "<"),
                ("ltr_le_trans", "<", "<="),
                ("ltr_trans", "<", "<"),
            )
        ),
    )
    observation = attempted_operation_native_observation(
        plan.requests[0],
        failure_kind="formula_transitivity_surface_mismatch",
        relation_bridge_choice=descriptor,
    )
    environment = environment.with_native_semantic_observations((observation,))
    return invocation, compiler.compile(snapshot, environment, invocation)


def _compile_int_bridge():
    tactic = "transitivity 0."
    state_ref = _state_ref()
    snapshot = _snapshot(state_ref, operand_type="int")
    invocation = compiler_invocation_context(state_ref, _turn(state_ref, tactic))
    compiler = ProofStateCompiler(features=(relation_bridge_realization_feature(),))
    environment = CompilationEnvironment("relation-bridge-environment", (), ())
    plan = compiler.plan_native_semantics(snapshot, environment, invocation)
    assert len(plan.requests) == 1
    bridge = NativeRelationBridgeDescriptor(
        source_operation="transitivity",
        relation_family="int_le",
        intermediate_text="0",
        intermediate_type_text="int",
        candidate_tactic="apply (Int.lez_trans 0); first last.",
        failure_kind="formula_transitivity_surface_mismatch",
        source_target_present=False,
        source_target_convertible_to_current_goal=False,
        source_target_right_convertible_to_current_right=False,
    )
    observation = attempted_operation_native_observation(
        plan.requests[0],
        failure_kind="formula_transitivity_surface_mismatch",
        relation_bridge=bridge,
    )
    environment = environment.with_native_semantic_observations((observation,))
    return invocation, compiler.compile(snapshot, environment, invocation)


def _compile_relation_handoff(
    *,
    native_error_message: str = (
        "formula-level transitivity does not match this inequality"
    ),
    strict_choice: bool = False,
    prefix_tactic: str = "wp.",
    prefix_effect: str = "accepted_no_progress",
):
    state_ref = _state_ref()
    snapshot = _snapshot(
        state_ref,
        relation_operator="<" if strict_choice else "<=",
    )
    rejected = (
        prefix_tactic[:-1].rstrip() + "; transitivity 0%r."
    )
    invocation = compiler_invocation_context(
        state_ref,
        _turn(state_ref, rejected),
    )
    compiler = ProofStateCompiler(features=(
        compound_tactic_prefix_recovery_feature(),
        relation_bridge_realization_feature(),
    ))
    environment = CompilationEnvironment("relation-handoff-environment", (), ())
    plan = compiler.plan_native_semantics(snapshot, environment, invocation)
    assert len(plan.requests) == 1
    assert plan.requests[0].feature_id == (
        COMPOUND_TACTIC_PREFIX_RECOVERY_FEATURE_ID
    )
    bridge = None
    bridge_choice = None
    if strict_choice:
        bridge_choice = NativeRelationBridgeChoiceDescriptor(
            source_operation="transitivity",
            relation_family="real_lt",
            goal_left_text="x",
            intermediate_text="0%r",
            goal_right_text="y",
            intermediate_type_text="real",
            failure_kind="formula_transitivity_surface_mismatch",
            choices=tuple(
                NativeRelationBridgeChoice(
                    certificate_family=family,
                    left_relation=left_relation,
                    right_relation=right_relation,
                    candidate_tactic=(
                        f"apply ({family} 0%r); first last."
                    ),
                )
                for family, left_relation, right_relation in (
                    ("ler_lt_trans", "<=", "<"),
                    ("ltr_le_trans", "<", "<="),
                    ("ltr_trans", "<", "<"),
                )
            ),
        )
    else:
        bridge = NativeRelationBridgeDescriptor(
            source_operation="transitivity",
            relation_family="real_le",
            intermediate_text="0%r",
            intermediate_type_text="real",
            candidate_tactic="apply (ler_trans 0%r); first last.",
            failure_kind="formula_transitivity_surface_mismatch",
            source_target_present=False,
            source_target_convertible_to_current_goal=False,
            source_target_right_convertible_to_current_right=False,
        )
    descriptor = NativeTacticPrefixDiagnosticDescriptor(
        rejected_tactic=rejected,
        candidate_prefixes=(prefix_tactic,),
        prefix_effects=(prefix_effect,),
        accepted_prefixes=(prefix_tactic,),
        boundary_tactic="transitivity 0%r.",
        native_failure_kind="native_user_error",
        native_error_message=native_error_message,
        boundary_failure_kind="formula_transitivity_surface_mismatch",
        boundary_error_message=native_error_message,
        goal_kind="formula",
        boundary_attempt=NativeAttemptedOperationDescriptor(
            operation_family="transitivity",
            rejected_tactic="transitivity 0%r.",
            exact_resource="",
            argument_kinds=("formula",),
            side="",
            positions=(),
            native_diagnostic_status="blocker",
            native_failure_kind="formula_transitivity_surface_mismatch",
            native_error_message=native_error_message,
            attempt_outcome="rejected",
            goal_kind="formula",
            relation_bridge=bridge,
            relation_bridge_choice=bridge_choice,
        ),
    )
    observation = NativeSemanticObservation.accepted(
        request=plan.requests[0],
        batch_id="relation-handoff-batch",
        batch_index=0,
        batch_size=1,
        batch_elapsed_ms=1,
        result_formula="",
        descriptor=descriptor,
        runtime_identity_sha256="d" * 64,
        companion_identity_sha256="e" * 64,
        elapsed_ms=1,
        provenance=ProvenanceRef(
            producer="test.relation_handoff",
            authority="native.semantic.batch.produced",
            source_sha256="f" * 64,
            artifact_ref="native_semantic_batches/relation-handoff.json",
            source_event_id="native-semantic-relation-handoff",
            source_event_sequence=9,
            authoritative=True,
        ),
    )
    bundle = compiler.compile(
        snapshot,
        environment.with_native_semantic_observations((observation,)),
        invocation,
    )
    return invocation, bundle


def _handoff_validation_assembly(
    producer_mode: str,
    consumer_mode: str,
    *,
    producer_allowance_markdown_bytes: int = 650,
    consumer_max_markdown_bytes: int = 1_400,
):
    compound = compound_tactic_prefix_recovery_feature()
    compound = replace(
        compound,
        spec=replace(
            compound.spec,
            gate=ExperimentGate(
                status="candidate",
                evidence_ledger_ids=compound.spec.gate.evidence_ledger_ids,
                experiment_id="compound-handoff-delivery-isolation-test",
            ),
        ),
    )
    modes = {
        COMPOUND_TACTIC_PREFIX_RECOVERY_FEATURE_ID: producer_mode,
        RELATION_BRIDGE_REALIZATION_FEATURE_ID: consumer_mode,
    }
    policies = []
    if producer_mode == TREATMENT:
        policies.append(DeliveryPolicyDefinition(
            policy_id="compound_handoff_dependency_test",
            rule=failure_linked_repair_rule(),
            max_items=1,
            max_markdown_bytes=1_100,
            dependency_allowance_markdown_bytes=(
                producer_allowance_markdown_bytes
            ),
            compatible_feature_ids=(
                COMPOUND_TACTIC_PREFIX_RECOVERY_FEATURE_ID,
            ),
            compatibility_contract=(
                "validation-only complete compound context and dependency "
                "allowance"
            ),
            rejection_audit_reasons=BASE_POLICY_REJECTION_REASONS + (
                CERTIFICATION_MISSING_OR_REJECTED,
            ),
        ))
    if consumer_mode == TREATMENT:
        policies.append(DeliveryPolicyDefinition(
            policy_id="relation_handoff_owner_test",
            rule=failure_linked_repair_rule(),
            max_items=1,
            max_markdown_bytes=consumer_max_markdown_bytes,
            compatible_feature_ids=(RELATION_BRIDGE_REALIZATION_FEATURE_ID,),
            compatibility_contract=(
                "validation-only complete relation owner presentation"
            ),
            rejection_audit_reasons=BASE_POLICY_REJECTION_REASONS + (
                CERTIFICATION_MISSING_OR_REJECTED,
            ),
        ))
    return assemble_feature_set(
        profile_id=f"handoff_isolation_{producer_mode}_{consumer_mode}",
        features=(compound, relation_bridge_realization_feature()),
        modes=modes,
        delivery_policies=tuple(policies),
    )


@pytest.mark.parametrize(
    "tactic",
    ("transitivity 0%r.", "change (0%r <= y)."),
)
def test_relation_bridge_is_one_owned_cross_operation_candidate(tactic: str) -> None:
    _invocation, bundle = _compile(tactic)

    ownership = bundle.analyzed_state.recovery_ownership
    assert ownership.owner_feature_id == RELATION_BRIDGE_REALIZATION_FEATURE_ID
    assert ownership.preservation_witness is not None
    assert ownership.preservation_witness.witness_kind == (
        "native_argument_realization"
    )
    assert ownership.preservation_witness.source_operation_family in {
        "transitivity", "change"
    }
    assert ownership.preservation_witness.target_operation_family == "apply"
    assert len(bundle.analyzed_state.recovery_action_realizations) == 1
    assert len(bundle.candidate_surface.actions) == 1
    candidate = bundle.candidate_surface.actions[0]
    assert candidate.payload.to_dict() == {
        "tactic": "apply (ler_trans 0%r); first last."
    }
    assert candidate.recovery_witness_id == (
        ownership.preservation_witness.witness_id
    )
    assert candidate.correction is not None
    assert candidate.correction.presentation_kind == "do_you_mean"


def test_compound_no_progress_handoff_routes_to_relation_recovery() -> None:
    _invocation, bundle = _compile_relation_handoff()

    attempted = bundle.proof_ir.attempted_operation
    assert attempted is not None
    assert attempted.operation_family == "transitivity"
    assert attempted.recovery_handoff is not None
    assert bundle.analyzed_state.recovery_ownership.owner_feature_id == (
        RELATION_BRIDGE_REALIZATION_FEATURE_ID
    )
    assert len(bundle.candidate_surface.actions) == 1
    action = bundle.candidate_surface.actions[0]
    assert action.delivery_dependency_feature_ids == (
        COMPOUND_TACTIC_PREFIX_RECOVERY_FEATURE_ID,
    )
    assert action.payload.to_dict() == {
        "tactic": "apply (ler_trans 0%r); first last."
    }
    assert action.correction is not None
    assert action.correction.reason.startswith(
        "Your compound tactic failed and was rolled back. `wp.` was not "
        "committed.\n\nEasyCrypt can execute the first stage:\n\n  wp."
    )
    assert "The next stage fails:\n\n  transitivity 0%r." in (
        action.correction.reason
    )


def test_state_changing_handoff_reconstructs_complete_certifiable_action() -> None:
    invocation, bundle = _compile_relation_handoff(
        prefix_tactic="move=> H.",
        prefix_effect="accepted_changed",
    )

    attempted = bundle.proof_ir.attempted_operation
    assert attempted is not None and attempted.recovery_handoff is not None
    assert attempted.recovery_handoff.prefix_changes_state is True
    assert bundle.analyzed_state.recovery_ownership.owner_feature_id == (
        RELATION_BRIDGE_REALIZATION_FEATURE_ID
    )
    assert len(bundle.candidate_surface.actions) == 1
    action = bundle.candidate_surface.actions[0]
    assert action.payload.to_dict() == {
        "tactic": "move=> H; apply (ler_trans 0%r); first last."
    }
    assert action.delivery_dependency_feature_ids == (
        COMPOUND_TACTIC_PREFIX_RECOVERY_FEATURE_ID,
    )
    assert action.correction is not None
    assert action.correction.reason.startswith(
        "Your compound tactic failed and was rolled back. `move=> H.` was "
        "not committed.\n\nEasyCrypt can execute the first stage:\n\n  move=> H."
    )
    certification = CertificationResult(
        candidate_id=action.candidate_id,
        state_ref=bundle.state_ref,
        policy=action.certification_policy,
        intent=action.intent,
        payload_sha256=frozen_json_sha256(action.payload),
        accepted=True,
        verification_ref=(
            "tactic.preflight.produced:state-changing-handoff@sha256:"
            + "d" * 64
        ),
        checked_effect=freeze_json_object({
            "accepted": True,
            "outcome_known": True,
            "goal_after_closed": False,
            "goal_after_remaining": 2,
        }),
    )
    admitted = admit_action_surface(
        bundle.candidate_surface,
        (certification,),
        _handoff_validation_assembly(TREATMENT, TREATMENT).manifest,
        triggers=invocation.triggers,
    )
    assert len(admitted.action_surface.actions) == 1
    assert admitted.action_surface.actions[0].payload.to_dict() == {
        "tactic": "move=> H; apply (ler_trans 0%r); first last."
    }


def test_state_changing_handoff_binds_consumer_native_work_to_prefix() -> None:
    invocation, bundle = _compile_relation_handoff(
        prefix_tactic="move=> H.",
        prefix_effect="accepted_changed",
    )
    attempted = bundle.proof_ir.attempted_operation
    assert attempted is not None

    def producer(proof_ir, _coordinate, _invocation, _budget):
        return NativeSemanticRequestProduction.ready(
            "synthetic.boundary.consumer",
            (NativeSemanticRequest(
                state_ref=proof_ir.state_ref,
                request_id="synthetic-boundary-consumer-request",
                producer_id="synthetic.boundary.consumer",
                query=NativeProofTermElaborationQuery(
                    operation="exact",
                    application_term="H true",
                ),
                evidence_refs=attempted.evidence_refs,
            ),),
        )

    plan = plan_native_semantics(
        bundle.proof_ir,
        (NativeSemanticProducerBinding(
            feature_id="synthetic_boundary_consumer",
            producer=producer,
        ),),
        invocation,
    )

    assert len(plan.requests) == 1
    assert plan.requests[0].evaluation_prefix == ("move=> H.",)
    assert plan.execution_units[0].runtime_payload()[
        "evaluation_prefix"
    ] == ["move=> H."]


@pytest.mark.parametrize(
    ("producer_mode", "consumer_mode", "visible", "rejection_reason"),
    (
        (AUDIT, AUDIT, False, "feature_not_admitted"),
        (AUDIT, TREATMENT, False, "delivery_dependency_not_admitted"),
        (TREATMENT, AUDIT, False, "feature_not_admitted"),
        (TREATMENT, TREATMENT, True, "admitted"),
    ),
)
def test_handoff_delivery_requires_treatment_for_producer_and_consumer(
    producer_mode: str,
    consumer_mode: str,
    visible: bool,
    rejection_reason: str,
) -> None:
    invocation, bundle = _compile_relation_handoff()
    candidate = bundle.candidate_surface.actions[0]
    certification = CertificationResult(
        candidate_id=candidate.candidate_id,
        state_ref=bundle.state_ref,
        policy=candidate.certification_policy,
        intent=candidate.intent,
        payload_sha256=frozen_json_sha256(candidate.payload),
        accepted=True,
        verification_ref=(
            "tactic.preflight.produced:handoff-isolation@sha256:" + "d" * 64
        ),
        checked_effect=freeze_json_object({
            "accepted": True,
            "outcome_known": True,
            "goal_after_closed": False,
            "goal_after_remaining": 2,
        }),
    )
    assembly = _handoff_validation_assembly(producer_mode, consumer_mode)
    admitted = admit_action_surface(
        bundle.candidate_surface,
        (certification,),
        assembly.manifest,
        triggers=invocation.triggers,
    )

    assert len(bundle.candidate_surface.actions) == 1
    assert len(admitted.action_surface.actions) == int(visible)
    assert (
        admitted.markdown_bytes > 0
        if visible
        else admitted.markdown_bytes == 0
    )
    assert admitted.decisions[0].reason == rejection_reason


def test_handoff_preserves_complete_action_owner_reason_past_420_bytes() -> None:
    _invocation, bundle = _compile_relation_handoff(
        native_error_message="native boundary detail " + "x" * 140,
    )

    assert bundle.analyzed_state.recovery_ownership.owner_feature_id == (
        RELATION_BRIDGE_REALIZATION_FEATURE_ID
    )
    assert len(bundle.candidate_surface.actions) == 1
    assert bundle.candidate_surface.diagnostics == ()
    correction = bundle.candidate_surface.actions[0].correction
    assert correction is not None
    assert len(correction.reason.encode("utf-8")) > 420
    assert "native boundary detail" in correction.reason
    assert "ler_trans realizes the same inequality bridge" in correction.reason
    assert bundle.candidate_surface.audit_reasons == ()


def test_handoff_preserves_complete_choice_semantics_past_420_bytes() -> None:
    _invocation, bundle = _compile_relation_handoff(strict_choice=True)

    assert bundle.analyzed_state.recovery_ownership.owner_feature_id == (
        RELATION_BRIDGE_REALIZATION_FEATURE_ID
    )
    assert bundle.candidate_surface.actions == ()
    assert len(bundle.candidate_surface.diagnostics) == 1
    diagnostic = bundle.candidate_surface.diagnostics[0].diagnostic
    assert diagnostic.identity_payload_bytes > 420
    assert diagnostic.applicability == "choice_required"
    assert "That stage does not change the goal" in (
        diagnostic.primary
    )
    assert "ler_lt_trans" in diagnostic.help
    assert "ltr_le_trans" in diagnostic.help
    assert "ltr_trans" in diagnostic.help
    assert bundle.candidate_surface.audit_reasons == ()


def test_state_changing_strict_choice_names_temporary_goal_and_selects_none() -> None:
    _invocation, bundle = _compile_relation_handoff(
        strict_choice=True,
        prefix_tactic="move=> H.",
        prefix_effect="accepted_changed",
    )

    diagnostic = bundle.candidate_surface.diagnostics[0].diagnostic
    assert "temporary goal produced by `move=> H.`" in diagnostic.primary
    assert "the current goal" not in diagnostic.primary
    assert "for the failing stage" in diagnostic.help
    assert diagnostic.help.endswith("the compiler selected none.")


def test_dependency_allowance_admits_complete_composed_choice() -> None:
    invocation, bundle = _compile_relation_handoff(strict_choice=True)
    without_allowance = _handoff_validation_assembly(
        TREATMENT,
        TREATMENT,
        producer_allowance_markdown_bytes=0,
        consumer_max_markdown_bytes=500,
    )
    with_allowance = _handoff_validation_assembly(
        TREATMENT,
        TREATMENT,
        producer_allowance_markdown_bytes=400,
        consumer_max_markdown_bytes=500,
    )

    rejected = admit_action_surface(
        bundle.candidate_surface,
        (),
        without_allowance.manifest,
        triggers=invocation.triggers,
    )
    admitted = admit_action_surface(
        bundle.candidate_surface,
        (),
        with_allowance.manifest,
        triggers=invocation.triggers,
    )

    assert rejected.action_surface.empty
    assert rejected.decisions[0].reason == "markdown_byte_budget_exceeded"
    assert rejected.decisions[0].candidate_markdown_bytes > (
        rejected.decisions[0].effective_max_markdown_bytes
    )
    assert len(admitted.action_surface.diagnostics) == 1
    assert admitted.decisions[0].candidate_markdown_bytes <= (
        admitted.decisions[0].effective_max_markdown_bytes
    )
    assert admitted.decisions[0].candidate_markdown_bytes == admitted.markdown_bytes


def test_presentation_contract_failure_is_not_reported_as_budget_abstention(
    monkeypatch,
) -> None:
    from core.easycrypt.proof_state_compiler.backend import admission as admission_module

    invocation, bundle = _compile_relation_handoff(strict_choice=True)
    assembly = _handoff_validation_assembly(TREATMENT, TREATMENT)
    real_render = admission_module.render_action_surface

    def reject_nonempty(surface):
        if not surface.empty:
            raise PresentationContractError("fixture schema drift")
        return real_render(surface)

    monkeypatch.setattr(
        admission_module,
        "render_action_surface",
        reject_nonempty,
    )

    result = admit_action_surface(
        bundle.candidate_surface,
        (),
        assembly.manifest,
        triggers=invocation.triggers,
    )

    assert result.action_surface.empty
    assert result.decisions[0].reason == "presentation_contract_invalid"
    assert result.decisions[0].candidate_markdown_bytes == 0


def test_internal_safety_overflow_abstains_without_semantic_degradation() -> None:
    _invocation, bundle = _compile_relation_handoff(
        native_error_message="x" * 17_000,
    )

    assert bundle.candidate_surface.actions == ()
    assert bundle.candidate_surface.diagnostics == ()
    assert bundle.candidate_surface.audit_reasons == (
        RECOVERY_HANDOFF_INTERNAL_PRESENTATION_BOUND_EXCEEDED,
    )


def test_real_lt_choice_preserves_intermediate_without_ranking() -> None:
    _invocation, bundle = _compile_strict_choice()

    ownership = bundle.analyzed_state.recovery_ownership
    assert ownership.owner_feature_id == RELATION_BRIDGE_REALIZATION_FEATURE_ID
    assert ownership.allowed_output_kinds == ("diagnostic",)
    assert bundle.candidate_surface.actions == ()
    assert len(bundle.candidate_surface.diagnostics) == 1
    diagnostic = bundle.candidate_surface.diagnostics[0].diagnostic
    assert diagnostic.applicability == "choice_required"
    assert diagnostic.primary == (
        "`transitivity 0%r` is formula-level equality transitivity, but the "
        "current goal is a real strict inequality `x < y`."
    )
    assert diagnostic.help == (
        "EasyCrypt checked these exact bridge alternatives for the failing "
        "stage. Which bridge do you mean?\n"
        "- `apply (ler_lt_trans 0%r); first last.`: `x <= 0%r`, `0%r < y`\n"
        "- `apply (ltr_le_trans 0%r); first last.`: `x < 0%r`, `0%r <= y`\n"
        "- `apply (ltr_trans 0%r); first last.`: `x < 0%r`, `0%r < y`\n"
        "Choose one only if it fits the proof route you want; the compiler "
        "selected none."
    )


def test_real_lt_choice_is_hidden_in_audit_and_visible_in_treatment() -> None:
    invocation, bundle = _compile_strict_choice()
    treatment = compiler_assembly_for_profile(
        RELATION_BRIDGE_REALIZATION_TREATMENT_PROFILE
    )
    audit = compiler_assembly_for_profile(
        RELATION_BRIDGE_REALIZATION_AUDIT_PROFILE
    )
    assert treatment is not None and audit is not None

    treated = admit_action_surface(
        bundle.candidate_surface,
        (),
        treatment.manifest,
        triggers=invocation.triggers,
    )
    hidden = admit_action_surface(
        bundle.candidate_surface,
        (),
        audit.manifest,
        triggers=invocation.triggers,
    )
    assert len(treated.action_surface.diagnostics) == 1
    assert hidden.action_surface.empty


def test_int_le_bridge_preserves_integer_intermediate() -> None:
    _invocation, bundle = _compile_int_bridge()

    assert len(bundle.candidate_surface.actions) == 1
    candidate = bundle.candidate_surface.actions[0]
    assert candidate.payload.to_dict() == {
        "tactic": "apply (Int.lez_trans 0); first last."
    }
    assert candidate.correction is not None
    assert "int <=" in candidate.correction.reason
    assert "Int.lez_trans" in candidate.correction.reason


def test_relation_bridge_witness_mismatch_fails_closed_before_certification() -> None:
    invocation, bundle = _compile("transitivity 0%r.")
    realization = bundle.analyzed_state.recovery_action_realizations[0]
    changed = replace(
        realization,
        witness=replace(realization.witness, witness_id="f" * 64),
    )
    analyzed = replace(
        bundle.analyzed_state,
        recovery_action_realizations=(changed,),
    )
    feature = relation_bridge_realization_feature()
    from core.easycrypt.proof_state_compiler.backend.surface_lowering import (
        build_candidate_surface,
    )

    surface = build_candidate_surface(
        analyzed,
        feature.surface_lowerers,
        invocation,
    )
    assert surface.empty


def test_relation_bridge_payload_drift_fails_closed_before_certification() -> None:
    invocation, bundle = _compile("transitivity 0%r.")
    contribution = lower_relation_bridge_realization(
        bundle.analyzed_state,
        invocation,
    )
    changed = replace(
        contribution.actions[0],
        payload=freeze_json_object({"tactic": "apply unrelated_fact."}),
    )
    from core.easycrypt.proof_state_compiler.backend.surface_lowering import (
        SurfaceContribution,
        build_candidate_surface,
    )

    surface = build_candidate_surface(
        bundle.analyzed_state,
        (lambda _state, _invocation: SurfaceContribution(actions=(changed,)),),
        invocation,
    )
    assert surface.empty


def test_do_you_mean_is_metadata_on_the_one_verified_action() -> None:
    invocation, bundle = _compile("transitivity 0%r.")
    candidate = bundle.candidate_surface.actions[0]
    certification = CertificationResult(
        candidate_id=candidate.candidate_id,
        state_ref=bundle.state_ref,
        policy=candidate.certification_policy,
        intent=candidate.intent,
        payload_sha256=frozen_json_sha256(candidate.payload),
        accepted=True,
        verification_ref=(
            "tactic.preflight.produced:relation-test@sha256:" + "d" * 64
        ),
        checked_effect=freeze_json_object({
            "accepted": True,
            "outcome_known": True,
            "goal_after_closed": False,
            "goal_after_remaining": 2,
        }),
    )
    assembly = compiler_assembly_for_profile(
        RELATION_BRIDGE_REALIZATION_TREATMENT_PROFILE
    )
    assert assembly is not None
    admitted = admit_action_surface(
        bundle.candidate_surface,
        (certification,),
        assembly.manifest,
        triggers=invocation.triggers,
    )

    assert len(admitted.action_surface.actions) == 1
    assert admitted.action_surface.diagnostics == ()
    payload = action_surface_payload(admitted.action_surface)
    assert payload["actions"][0]["correction"]["kind"] == "do_you_mean"
    markdown = render_action_surface_payload(payload).text
    assert "## Do you mean?" in markdown
    assert "ler_trans" in markdown
    assert markdown.count("```json") == 1


def test_relation_profiles_share_recovery_without_adding_a_runtime_mode() -> None:
    treatment = compiler_assembly_for_profile(
        RELATION_BRIDGE_REALIZATION_TREATMENT_PROFILE
    )
    audit = compiler_assembly_for_profile(
        RELATION_BRIDGE_REALIZATION_AUDIT_PROFILE
    )
    assert treatment is not None and audit is not None
    assert treatment.activation_plan.pass_feature_ids == (
        "operation_binding_repair",
        "relation_bridge_realization",
    )
    assert audit.activation_plan.pass_feature_ids == (
        "operation_binding_repair",
        "relation_bridge_realization",
    )
    assert treatment.delivery_plan.aggregate_max_items == 1
    assert audit.delivery_plan.admitted_feature_ids == ()


def test_feature_has_no_scenario_or_theorem_constants() -> None:
    package = (
        __import__(
            "core.easycrypt.proof_state_compiler.features."
            "relation_bridge_realization.feature",
            fromlist=["__file__"],
        ).__file__
    )
    assert package is not None
    text = open(package, encoding="utf-8").read()
    assert "step2_1" not in text
    assert "CCA_CPA_UFCMA" not in text
    assert "StLSke" not in text
