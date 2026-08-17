"""Contracts for commitment-relative pure-tail rewrite recovery."""

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
    NativePureTailRewriteDescriptor,
    TargetRef,
    TransitionRef,
    compiler_invocation_context,
    freeze_json_object,
    frozen_json_sha256,
)
from core.easycrypt.proof_state_compiler.features.pure_tail_recovery import (
    PURE_TAIL_RECOVERY_FEATURE_ID,
    pure_tail_recovery_feature,
)
from core.easycrypt.proof_state_compiler.features.pure_tail_recovery.syntax import (
    selected_plain_rewrite,
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
    PURE_TAIL_RECOVERY_AUDIT_PROFILE,
    PURE_TAIL_RECOVERY_TREATMENT_PROFILE,
)


def _state_ref() -> StateRef:
    return StateRef(
        session_id="pure-tail-rewrite-test",
        state_version=7,
        goal_identity="pure-tail-goal",
        goal_identity_required=True,
        committed_prefix_identity="a" * 64,
    )


def _snapshot(state_ref: StateRef) -> AuthoritativeSnapshotInput:
    return AuthoritativeSnapshotInput(
        state_ref=state_ref,
        provenance=ProvenanceRef(
            producer="pure-tail.fixture",
            authority="compiler.input.produced",
            source_sha256="b" * 64,
            artifact_ref="compiler_inputs/pure-tail.json",
            source_event_id="compiler-input-pure-tail",
            source_event_sequence=7,
            authoritative=True,
        ),
        target=TargetRef("eval/pure_tail.ec", "rewrite_target"),
        transition=TransitionRef(
            "rejected", state_ref, "compiler_inputs/pure-tail.json"
        ),
        goal_lines=(
            "Current goal",
            "Hupdate: m.[x <- v].[x] = z",
            "--------",
            "z = v",
        ),
        goal_count=1,
        goal_count_known=True,
        closed=False,
        native_state=native_state(
            state_ref,
            formula=typed_node("operator_application", "z = v"),
        ),
    )


def _turn(state_ref: StateRef, tactic: str) -> CompilerTurnEvidence:
    return CompilerTurnEvidence(
        source_event_id="pure-tail-failure",
        source_event_sequence=8,
        authority_kind="event_bound_tactic_execution_result",
        artifact_ref="tactic_execution_results/pure-tail-failure.json",
        artifact_hash="c" * 64,
        hash_algorithm="sha256",
        post_state_ref=state_ref,
        intent="commit_tactic",
        payload=freeze_json_object({"tactic": tactic}),
        outcome_kind="rejected",
        proof_state_effect="unchanged",
        structured_error="rewrite did not match the conclusion",
    )


def _compile():
    tactic = "rewrite FMap.get_setE."
    state_ref = _state_ref()
    snapshot = _snapshot(state_ref)
    invocation = compiler_invocation_context(state_ref, _turn(state_ref, tactic))
    compiler = ProofStateCompiler(features=(pure_tail_recovery_feature(),))
    environment = CompilationEnvironment("pure-tail-environment", (), ())
    plan = compiler.plan_native_semantics(snapshot, environment, invocation)
    assert len(plan.requests) == 1
    descriptor = NativePureTailRewriteDescriptor(
        source_operation="rewrite",
        selected_resource="FMap.get_setE",
        target_kind="hypothesis",
        target_name="Hupdate",
        candidate_tactic="rewrite FMap.get_setE in Hupdate.",
        failure_kind="rewrite_target_mismatch",
        accepted_target_count=1,
    )
    observation = attempted_operation_native_observation(
        plan.requests[0],
        failure_kind="rewrite_target_mismatch",
        argument_kinds=("rewrite_lemma",),
        pure_tail_rewrite=descriptor,
    )
    environment = environment.with_native_semantic_observations((observation,))
    return invocation, compiler.compile(snapshot, environment, invocation)


def test_plain_rewrite_gate_is_bounded() -> None:
    assert selected_plain_rewrite("rewrite get_setE.") == "get_setE"
    assert selected_plain_rewrite("rewrite FMap.get_setE.") == "FMap.get_setE"
    assert selected_plain_rewrite("rewrite -get_setE.") is None
    assert selected_plain_rewrite("rewrite get_setE in H.") is None
    assert selected_plain_rewrite("rewrite get_setE mem_set.") is None
    assert selected_plain_rewrite("rewrite get_setE; smt().") is None


def test_unique_native_target_becomes_one_owned_do_you_mean_action() -> None:
    _invocation, bundle = _compile()
    ownership = bundle.analyzed_state.recovery_ownership
    assert ownership.owner_feature_id == PURE_TAIL_RECOVERY_FEATURE_ID
    assert ownership.operation_family == "rewrite"
    assert ownership.selected_resource == "FMap.get_setE"
    assert ownership.preservation_witness is not None
    assert ownership.preservation_witness.witness_kind == (
        "exact_operation_resource"
    )
    assert len(bundle.candidate_surface.actions) == 1
    candidate = bundle.candidate_surface.actions[0]
    assert candidate.payload.to_dict() == {
        "tactic": "rewrite FMap.get_setE in Hupdate."
    }
    assert candidate.correction is not None
    assert candidate.correction.presentation_kind == "do_you_mean"
    assert "exactly one hypothesis in the current goal" in (
        candidate.correction.reason
    )
    assert "Hupdate" in candidate.correction.reason


def test_treatment_exposes_and_audit_hides_the_certified_repair() -> None:
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
            "tactic.preflight.produced:pure-tail-test@sha256:" + "d" * 64
        ),
        checked_effect=freeze_json_object({
            "accepted": True,
            "outcome_known": True,
            "goal_after_closed": False,
            "goal_after_remaining": 1,
        }),
    )
    treatment = compiler_assembly_for_profile(
        PURE_TAIL_RECOVERY_TREATMENT_PROFILE
    )
    audit = compiler_assembly_for_profile(PURE_TAIL_RECOVERY_AUDIT_PROFILE)
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


def test_no_native_unique_target_leaves_recovery_unclaimed() -> None:
    tactic = "rewrite FMap.get_setE."
    state_ref = _state_ref()
    snapshot = _snapshot(state_ref)
    invocation = compiler_invocation_context(state_ref, _turn(state_ref, tactic))
    compiler = ProofStateCompiler(features=(pure_tail_recovery_feature(),))
    environment = CompilationEnvironment("pure-tail-environment", (), ())
    plan = compiler.plan_native_semantics(snapshot, environment, invocation)
    observation = attempted_operation_native_observation(
        plan.requests[0],
        failure_kind="rewrite_failure",
        argument_kinds=("rewrite_lemma",),
        pure_tail_rewrite=None,
    )
    bundle = compiler.compile(
        snapshot,
        environment.with_native_semantic_observations((observation,)),
        invocation,
    )
    assert bundle.analyzed_state.recovery_ownership.status == "unclaimed"
    assert bundle.candidate_surface.empty
