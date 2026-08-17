"""Contracts for commitment-relative structured intro-pattern recovery."""

from __future__ import annotations

from core.easycrypt.proof_state_compiler import (
    AuthoritativeSnapshotInput,
    CompilationEnvironment,
    ProofStateCompiler,
    ProvenanceRef,
    StateRef,
)
from core.easycrypt.proof_state_compiler.backend import admit_action_surface
from core.easycrypt.proof_state_compiler.contracts import (
    CertificationResult,
    CompilerTurnEvidence,
    NativeIntroPatternRepairDescriptor,
    TargetRef,
    TransitionRef,
    compiler_invocation_context,
    freeze_json_object,
    frozen_json_sha256,
)
from core.easycrypt.proof_state_compiler.features.intro_pattern_repair import (
    INTRO_PATTERN_REPAIR_FEATURE_ID,
    intro_pattern_repair_feature,
)
from core.easycrypt.proof_state_compiler.features.intro_pattern_repair.syntax import (
    is_nested_intro_pattern_candidate,
)
from tests.proof_state_compiler_test_support import (
    attempted_operation_native_observation,
    native_state,
    typed_node,
)
from workflow.proof_state_compiler.configuration import (
    compiler_assembly_for_profile,
)
from workflow.proof_state_compiler.profile_ids import (
    INTRO_PATTERN_REPAIR_AUDIT_PROFILE,
    INTRO_PATTERN_REPAIR_TREATMENT_PROFILE,
)


REJECTED_TACTIC = "move => [ha hb [hc hd]]."
CANDIDATE_TACTIC = "move => [# ha hb hc hd]."


def _state_ref() -> StateRef:
    return StateRef(
        session_id="intro-pattern-test",
        state_version=4,
        goal_identity="intro-pattern-goal",
        goal_identity_required=True,
        committed_prefix_identity="a" * 64,
    )


def _snapshot(state_ref: StateRef) -> AuthoritativeSnapshotInput:
    return AuthoritativeSnapshotInput(
        state_ref=state_ref,
        provenance=ProvenanceRef(
            producer="intro-pattern.fixture",
            authority="compiler.input.produced",
            source_sha256="b" * 64,
            artifact_ref="compiler_inputs/intro-pattern.json",
            source_event_id="compiler-input-intro-pattern",
            source_event_sequence=4,
            authoritative=True,
        ),
        target=TargetRef("eval/intro_pattern.ec", "intro_pattern_goal"),
        transition=TransitionRef(
            "rejected", state_ref, "compiler_inputs/intro-pattern.json"
        ),
        goal_lines=(
            "Current goal",
            "a b c d: bool",
            "--------",
            "a /\\ b /\\ c /\\ d => true",
        ),
        goal_count=1,
        goal_count_known=True,
        closed=False,
        native_state=native_state(
            state_ref,
            formula=typed_node(
                "operator_application", "a /\\ b /\\ c /\\ d => true"
            ),
        ),
    )


def _turn(state_ref: StateRef, tactic: str) -> CompilerTurnEvidence:
    return CompilerTurnEvidence(
        source_event_id="intro-pattern-failure",
        source_event_sequence=5,
        authority_kind="event_bound_tactic_execution_result",
        artifact_ref="tactic_execution_results/intro-pattern-failure.json",
        artifact_hash="c" * 64,
        hash_algorithm="sha256",
        post_state_ref=state_ref,
        intent="commit_tactic",
        payload=freeze_json_object({"tactic": tactic}),
        outcome_kind="rejected",
        proof_state_effect="unchanged",
        structured_error="invalid intro-pattern: nothing to eliminate",
    )


def _compile():
    state_ref = _state_ref()
    snapshot = _snapshot(state_ref)
    invocation = compiler_invocation_context(
        state_ref, _turn(state_ref, REJECTED_TACTIC)
    )
    compiler = ProofStateCompiler(features=(intro_pattern_repair_feature(),))
    environment = CompilationEnvironment("intro-pattern-environment", (), ())
    plan = compiler.plan_native_semantics(snapshot, environment, invocation)
    assert len(plan.requests) == 1
    descriptor = NativeIntroPatternRepairDescriptor(
        source_operation="intro_pattern",
        surface_operation="move",
        attempted_pattern_kind="nested_case",
        binder_names=("ha", "hb", "hc", "hd"),
        candidate_tactic=CANDIDATE_TACTIC,
        failure_kind="intro_pattern_structure_mismatch",
        selected_pattern_count=1,
    )
    observation = attempted_operation_native_observation(
        plan.requests[0],
        failure_kind="intro_pattern_structure_mismatch",
        argument_kinds=("ordered_named_binders",),
        intro_pattern_repair=descriptor,
    )
    environment = environment.with_native_semantic_observations((observation,))
    return invocation, compiler.compile(snapshot, environment, invocation)


def test_intro_pattern_lexical_gate_is_bounded() -> None:
    assert is_nested_intro_pattern_candidate(REJECTED_TACTIC)
    assert not is_nested_intro_pattern_candidate(
        "case: H => [ha [hb hc]]."
    )
    assert not is_nested_intro_pattern_candidate("move => [ha hb].")
    assert not is_nested_intro_pattern_candidate(
        "move => [# ha hb hc hd]."
    )
    assert not is_nested_intro_pattern_candidate(
        "move => [ha hb [hc hd]]; done."
    )
    assert not is_nested_intro_pattern_candidate(
        "move => [ha hb | hc hd]."
    )


def test_native_unique_intro_realization_becomes_owned_do_you_mean_action() -> None:
    _invocation, bundle = _compile()
    ownership = bundle.analyzed_state.recovery_ownership
    assert ownership.owner_feature_id == INTRO_PATTERN_REPAIR_FEATURE_ID
    assert ownership.operation_family == "intro_pattern"
    assert ownership.selected_resource == ""
    assert ownership.preservation_witness is not None
    assert ownership.preservation_witness.witness_kind == (
        "native_argument_realization"
    )
    assert len(bundle.candidate_surface.actions) == 1
    candidate = bundle.candidate_surface.actions[0]
    assert candidate.payload.to_dict() == {"tactic": CANDIDATE_TACTIC}
    assert candidate.correction is not None
    assert candidate.correction.presentation_kind == "do_you_mean"
    assert "same destruct and ordered binders" in candidate.correction.reason
    assert "no binder or proof step changes" in candidate.correction.reason


def test_treatment_exposes_and_audit_hides_certified_intro_repair() -> None:
    invocation, bundle = _compile()
    candidate = bundle.candidate_surface.actions[0]
    certification = CertificationResult(
        candidate_id=candidate.candidate_id,
        state_ref=bundle.state_ref,
        policy=candidate.certification_policy,
        intent=candidate.intent,
        payload_sha256=frozen_json_sha256(candidate.payload),
        accepted=True,
        verification_ref=(
            "tactic.preflight.produced:intro-pattern-test@sha256:" + "d" * 64
        ),
        checked_effect=freeze_json_object({
            "accepted": True,
            "outcome_known": True,
            "goal_after_closed": False,
            "goal_after_remaining": 1,
        }),
    )
    treatment = compiler_assembly_for_profile(
        INTRO_PATTERN_REPAIR_TREATMENT_PROFILE
    )
    audit = compiler_assembly_for_profile(INTRO_PATTERN_REPAIR_AUDIT_PROFILE)
    assert treatment is not None and audit is not None
    treated = admit_action_surface(
        bundle.candidate_surface,
        (certification,),
        treatment.manifest,
        triggers=invocation.triggers,
    )
    hidden = admit_action_surface(
        bundle.candidate_surface,
        (certification,),
        audit.manifest,
        triggers=invocation.triggers,
    )
    assert len(treated.action_surface.actions) == 1
    assert hidden.action_surface.empty
