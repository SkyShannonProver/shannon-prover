"""Contracts for selected eager-while dialect recovery."""

from __future__ import annotations

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
from core.easycrypt.proof_state_compiler.contracts import (
    CertificationResult,
    CompilerTurnEvidence,
    NativeEagerWhileCandidateDescriptor,
    NativeEagerWhileDialectDescriptor,
    TargetRef,
    TransitionRef,
    compiler_invocation_context,
    freeze_json_object,
    frozen_json_sha256,
)
from core.easycrypt.proof_state_compiler.features.tactic_dialect_repair import (
    TACTIC_DIALECT_REPAIR_FEATURE_ID,
    tactic_dialect_repair_feature,
)
from core.easycrypt.proof_state_compiler.features.tactic_dialect_repair.syntax import (
    is_candidate_eager_while,
)
from tests.proof_state_compiler_test_support import (
    attempted_operation_native_observation,
    native_state,
    typed_node,
)
from workflow.proof_state_compiler.configuration import (
    compiler_assembly_for_profile,
)
from core.easycrypt.proof_state_compiler.backend.presentation import (
    render_action_surface_payload,
)
from workflow.proof_state_compiler.profile_ids import (
    TACTIC_DIALECT_REPAIR_AUDIT_PROFILE,
    TACTIC_DIALECT_REPAIR_TREATMENT_PROFILE,
)


WRONG_EAGER = (
    "eager while (H : x <- 0; ~ x <- 0; : true ==> true)."
)


def _state_ref() -> StateRef:
    return StateRef(
        session_id="eager-dialect-test",
        state_version=4,
        goal_identity="eager-statement-goal",
        goal_identity_required=True,
        committed_prefix_identity="a" * 64,
    )


def _snapshot(state_ref: StateRef) -> AuthoritativeSnapshotInput:
    formula = typed_node("equivalence_statement", "equiv[statement]")
    return AuthoritativeSnapshotInput(
        state_ref=state_ref,
        provenance=ProvenanceRef(
            producer="eager-dialect.fixture",
            authority="compiler.input.produced",
            source_sha256="b" * 64,
            artifact_ref="compiler_inputs/eager-dialect.json",
            source_event_id="compiler-input-eager-dialect",
            source_event_sequence=4,
            authoritative=True,
        ),
        target=TargetRef("eval/eager_dialect.ec", "eager_boundary"),
        transition=TransitionRef(
            "rejected", state_ref, "compiler_inputs/eager-dialect.json"
        ),
        goal_lines=("Current goal", "--------", "equiv[statement]"),
        goal_count=1,
        goal_count_known=True,
        closed=False,
        native_state=native_state(state_ref, formula=formula),
    )


def _turn(state_ref: StateRef, tactic: str = WRONG_EAGER) -> CompilerTurnEvidence:
    return CompilerTurnEvidence(
        source_event_id="eager-dialect-failure",
        source_event_sequence=8,
        authority_kind="event_bound_tactic_execution_result",
        artifact_ref="tactic_execution_results/eager-dialect-failure.json",
        artifact_hash="c" * 64,
        hash_algorithm="sha256",
        post_state_ref=state_ref,
        intent="commit_tactic",
        payload=freeze_json_object({"tactic": tactic}),
        outcome_kind="rejected",
        proof_state_effect="unchanged",
        structured_error="native parse error",
    )


def _candidate(invariant: str) -> NativeEagerWhileCandidateDescriptor:
    return NativeEagerWhileCandidateDescriptor(
        invariant_text=invariant,
        candidate_tactic=f"eager while ({invariant}).",
    )


def _compile(
    *,
    candidates: tuple[NativeEagerWhileCandidateDescriptor, ...] = (),
    failure_kind: str = "eager_while_dialect_mismatch",
):
    state_ref = _state_ref()
    snapshot = _snapshot(state_ref)
    invocation = compiler_invocation_context(state_ref, _turn(state_ref))
    compiler = ProofStateCompiler(features=(tactic_dialect_repair_feature(),))
    environment = CompilationEnvironment("eager-dialect-environment", (), ())
    plan = compiler.plan_native_semantics(snapshot, environment, invocation)
    assert len(plan.requests) == 1
    descriptor = NativeEagerWhileDialectDescriptor(
        source_operation="eager",
        eager_subform="while",
        attempted_shape=(
            "invariant"
            if failure_kind == "eager_while_guard_mismatch"
            else "explicit_statement_contract"
        ),
        failure_kind=failure_kind,
        candidates=candidates,
    )
    observation = attempted_operation_native_observation(
        plan.requests[0],
        failure_kind=failure_kind,
        goal_kind="equiv_statement",
        argument_kinds=(
            "formula"
            if failure_kind == "eager_while_guard_mismatch"
            else "eager_while_contract",
        ),
        eager_while_dialect=descriptor,
    )
    environment = environment.with_native_semantic_observations((observation,))
    return invocation, compiler.compile(snapshot, environment, invocation)


def test_unique_checked_invariant_becomes_one_owned_do_you_mean() -> None:
    _invocation, bundle = _compile(candidates=(_candidate("true"),))

    ownership = bundle.analyzed_state.recovery_ownership
    assert ownership.owner_feature_id == TACTIC_DIALECT_REPAIR_FEATURE_ID
    assert ownership.allowed_output_kinds == ("action",)
    assert ownership.preservation_witness is not None
    assert ownership.preservation_witness.witness_kind == (
        "native_argument_realization"
    )
    assert len(bundle.candidate_surface.actions) == 1
    candidate = bundle.candidate_surface.actions[0]
    assert candidate.payload.to_dict() == {"tactic": "eager while (true)."}
    assert candidate.correction is not None
    assert candidate.correction.presentation_kind == "do_you_mean"
    assert bundle.candidate_surface.diagnostics == ()


def test_multiple_checked_invariants_are_listed_without_ranking() -> None:
    _invocation, bundle = _compile(
        candidates=(_candidate("true"), _candidate("={x}")),
    )

    assert bundle.candidate_surface.actions == ()
    assert len(bundle.candidate_surface.diagnostics) == 1
    diagnostic = bundle.candidate_surface.diagnostics[0].diagnostic
    assert diagnostic.applicability == "choice_required"
    assert diagnostic.help == (
        "EasyCrypt checked these exact invariant alternatives for the failing "
        "stage. Which invariant do you mean?\n"
        "- `eager while (true).`\n"
        "- `eager while (={x}).`\n"
        "Choose one only if it fits the proof route you want; the compiler "
        "selected none."
    )


def test_no_checked_submitted_invariant_exposes_only_the_shape() -> None:
    _invocation, bundle = _compile()

    assert bundle.candidate_surface.actions == ()
    assert len(bundle.candidate_surface.diagnostics) == 1
    diagnostic = bundle.candidate_surface.diagnostics[0].diagnostic
    assert diagnostic.applicability == "has_placeholders"
    assert diagnostic.placeholder_shape == "eager while (<invariant>)."
    assert "supply the invariant you intended" in diagnostic.help


def test_valid_eager_form_with_unequal_guards_is_explanation_only() -> None:
    _invocation, bundle = _compile(
        failure_kind="eager_while_guard_mismatch",
    )

    assert bundle.candidate_surface.actions == ()
    diagnostic = bundle.candidate_surface.diagnostics[0].diagnostic
    assert diagnostic.applicability == "explanation_only"
    assert "both while guards in the current goal" in diagnostic.primary
    assert "only after those guards" in diagnostic.help


def test_treatment_admits_certified_action_and_audit_hides_it() -> None:
    invocation, bundle = _compile(candidates=(_candidate("true"),))
    candidate = bundle.candidate_surface.actions[0]
    certification = CertificationResult(
        candidate_id=candidate.candidate_id,
        state_ref=bundle.state_ref,
        policy=candidate.certification_policy,
        intent=candidate.intent,
        payload_sha256=frozen_json_sha256(candidate.payload),
        accepted=True,
        verification_ref=(
            "tactic.preflight.produced:eager-test@sha256:" + "d" * 64
        ),
        checked_effect=freeze_json_object({
            "accepted": True,
            "outcome_known": True,
            "goal_after_closed": False,
            "goal_after_remaining": 6,
        }),
    )
    treatment = compiler_assembly_for_profile(
        TACTIC_DIALECT_REPAIR_TREATMENT_PROFILE
    )
    audit = compiler_assembly_for_profile(
        TACTIC_DIALECT_REPAIR_AUDIT_PROFILE
    )
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
    markdown = render_action_surface_payload(
        action_surface_payload(treated.action_surface)
    ).text
    assert "## Do you mean?" in markdown
    assert "eager while (true)." in markdown


def test_eager_profiles_reuse_recovery_without_new_runtime_mode() -> None:
    treatment = compiler_assembly_for_profile(
        TACTIC_DIALECT_REPAIR_TREATMENT_PROFILE
    )
    audit = compiler_assembly_for_profile(
        TACTIC_DIALECT_REPAIR_AUDIT_PROFILE
    )
    assert treatment is not None and audit is not None
    assert treatment.activation_plan.pass_feature_ids == (
        TACTIC_DIALECT_REPAIR_FEATURE_ID,
    )
    assert audit.activation_plan.pass_feature_ids == (
        TACTIC_DIALECT_REPAIR_FEATURE_ID,
    )
    assert treatment.delivery_plan.aggregate_max_items == 1
    assert audit.delivery_plan.admitted_feature_ids == ()


def test_eager_descriptor_rejects_more_than_two_candidates() -> None:
    with pytest.raises(ValueError, match="incomplete"):
        NativeEagerWhileDialectDescriptor(
            source_operation="eager",
            eager_subform="while",
            attempted_shape="explicit_statement_contract",
            failure_kind="eager_while_dialect_mismatch",
            candidates=(
                _candidate("true"),
                _candidate("={x}"),
                _candidate("x{1} = x{2}"),
            ),
        )


@pytest.mark.parametrize(
    "tactic",
    (
        "eager if.",
        "eager while (true)",
        "eager while (true).\nundo.",
        'eager while ("true").',
    ),
)
def test_lexical_gate_abstains_outside_bounded_eager_while(tactic: str) -> None:
    assert not is_candidate_eager_while(tactic)
