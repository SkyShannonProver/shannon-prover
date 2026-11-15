"""Contracts for the failure-linked hypothesis-scope diagnosis slice."""
from __future__ import annotations

import dataclasses

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
from core.easycrypt.proof_state_compiler.backend.presentation import (
    render_action_surface_payload,
)
from core.easycrypt.proof_state_compiler.contracts import (
    AttemptRealization,
    CertificationResult,
    CompilerTurnEvidence,
    NativeAttemptedOperationDescriptor,
    NativeSemanticObservation,
    NativeTacticPrefixDiagnosticDescriptor,
    NativeTacticPrefixDiagnosticQuery,
    TargetRef,
    TransitionRef,
    compiler_invocation_context,
    freeze_json_object,
    frozen_json_sha256,
)
from core.easycrypt.proof_state_compiler.features.compound_tactic_prefix_recovery import (
    compound_tactic_prefix_recovery_feature,
)
from core.easycrypt.proof_state_compiler.features.compound_tactic_prefix_recovery.syntax import (
    compound_accepted_prefix_extension,
    compound_prefix_candidates,
)
from core.easycrypt.proof_state_compiler.features.hypothesis_scope_diagnosis import (
    HYPOTHESIS_SCOPE_DIAGNOSIS_FEATURE_ID,
    hypothesis_scope_diagnosis_feature,
)
from core.easycrypt.proof_state_compiler.features.hypothesis_scope_diagnosis.realization import (
    OUT_OF_SCOPE_HYPOTHESIS_CODEC,
    OUT_OF_SCOPE_HYPOTHESIS_KIND,
    NativeOutOfScopeHypothesisDescriptor,
)
from core.easycrypt.proof_state_compiler.features.hypothesis_scope_diagnosis.syntax import (
    is_hypothesis_scope_candidate,
)
from core.easycrypt.proof_state_compiler.features.operation_binding_repair import (
    operation_binding_repair_feature,
)
from tests.helpers.compiler_feature_assembly import feature_assembly
from tests.helpers.proof_state_compiler import (
    attempted_operation_native_observation,
    namespace_spelling_set_observation,
    native_state,
    typed_node,
)
from workflow.proof_state_compiler.activation import AUDIT, TREATMENT
from workflow.proof_state_compiler.delivery_policies import (
    HYPOTHESIS_SCOPE_DIAGNOSIS_ONCE_POLICY_ID,
    default_delivery_policy_catalog,
)
from workflow.proof_state_compiler.profile_ids import (
    ALL_CANDIDATE_TREATMENT_PROFILE,
)
from workflow.proof_state_compiler.profile_registry import (
    PRODUCTION_COMPILER_PROFILES,
)


SMT_ERROR = "cannot find lemma `H4'"
REWRITE_ERROR = "unknown lemma `Hbad'"


def _smt(
    *,
    position: int = 1,
    count: int = 1,
    candidate: str = "",
    remaining: tuple[str, ...] = (),
) -> NativeOutOfScopeHypothesisDescriptor:
    return NativeOutOfScopeHypothesisDescriptor(
        source_operation="smt",
        written_name="H4",
        reference_position=position,
        reference_count=count,
        target_name="",
        lookup_scope="global_declarations",
        goal_hypothesis=True,
        declared_after_target=False,
        candidate_tactic=candidate,
        remaining_hints=remaining,
        failure_kind="smt_hint_names_goal_hypothesis",
    )


def _rewrite(position: int = 1, count: int = 1) -> NativeOutOfScopeHypothesisDescriptor:
    return NativeOutOfScopeHypothesisDescriptor(
        source_operation="rewrite",
        written_name="Hbad",
        reference_position=position,
        reference_count=count,
        target_name="H18",
        lookup_scope="context_before_target",
        goal_hypothesis=True,
        declared_after_target=True,
        candidate_tactic="",
        remaining_hints=(),
        failure_kind="rewrite_name_declared_after_target",
    )


def _realization(
    descriptor: NativeOutOfScopeHypothesisDescriptor,
) -> AttemptRealization:
    payload = {
        field.name: getattr(descriptor, field.name)
        for field in dataclasses.fields(descriptor)
        if field.name != "failure_kind"
    }
    payload["remaining_hints"] = list(descriptor.remaining_hints)
    return AttemptRealization(
        kind=OUT_OF_SCOPE_HYPOTHESIS_KIND,
        failure_kind=descriptor.failure_kind,
        payload=freeze_json_object(payload),
    )


def _attempt(
    tactic: str,
    descriptor: NativeOutOfScopeHypothesisDescriptor | None,
    *,
    family: str | None = None,
    resource: str | None = None,
    message: str | None = None,
) -> NativeAttemptedOperationDescriptor:
    source = "smt" if tactic.startswith("smt") else "rewrite"
    return NativeAttemptedOperationDescriptor(
        operation_family=family or source,
        rejected_tactic=tactic,
        exact_resource=(
            resource if resource is not None
            else "" if descriptor is None else descriptor.written_name
        ),
        argument_kinds=(
            ("smt_hint",) if source == "smt" else ("rewrite_lemma",)
        ),
        side="",
        positions=(),
        native_diagnostic_status="blocker",
        native_failure_kind=(
            "scope_error" if descriptor is None else descriptor.failure_kind
        ),
        native_error_message=message or (
            SMT_ERROR if source == "smt" else REWRITE_ERROR
        ),
        attempt_outcome="rejected",
        goal_kind="formula",
        realization=None if descriptor is None else _realization(descriptor),
    )


def _state_ref() -> StateRef:
    return StateRef(
        session_id="hypothesis-scope-test",
        state_version=3,
        goal_identity="hypothesis-scope-goal",
        goal_identity_required=True,
        committed_prefix_identity="a" * 64,
    )


def _snapshot(state_ref: StateRef) -> AuthoritativeSnapshotInput:
    return AuthoritativeSnapshotInput(
        state_ref=state_ref,
        provenance=ProvenanceRef(
            producer="hypothesis-scope.fixture",
            authority="compiler.input.produced",
            source_sha256="b" * 64,
            artifact_ref="compiler_inputs/hypothesis-scope.json",
            source_event_id="compiler-input-hypothesis-scope",
            source_event_sequence=3,
            authoritative=True,
        ),
        target=TargetRef("eval/hypothesis_scope.ec", "hypothesis_scope_goal"),
        transition=TransitionRef(
            "rejected", state_ref, "compiler_inputs/hypothesis-scope.json"
        ),
        goal_lines=("Current goal", "--------", "g x"),
        goal_count=1,
        goal_count_known=True,
        closed=False,
        native_state=native_state(
            state_ref, formula=typed_node("formula", "g x")
        ),
    )


def _turn(
    state_ref: StateRef,
    tactic: str,
    error: str,
    *,
    outcome_kind: str = "rejected",
    proof_state_effect: str = "unchanged",
) -> CompilerTurnEvidence:
    return CompilerTurnEvidence(
        source_event_id="hypothesis-scope-failure",
        source_event_sequence=4,
        authority_kind="event_bound_tactic_execution_result",
        artifact_ref="tactic_execution_results/hypothesis-scope.json",
        artifact_hash="c" * 64,
        hash_algorithm="sha256",
        post_state_ref=state_ref,
        intent="commit_tactic",
        payload=freeze_json_object({"tactic": tactic}),
        outcome_kind=outcome_kind,
        proof_state_effect=proof_state_effect,
        structured_error="[error] " + error if error else "",
    )


def _observation(request, descriptor) -> NativeSemanticObservation:
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
            artifact_ref="native_semantic_batches/hypothesis-scope.json",
            source_event_id="native-semantic-hypothesis-scope",
            source_event_sequence=5,
            authoritative=True,
        ),
    )


def _compile(attempt: NativeAttemptedOperationDescriptor, *, features=None):
    state_ref = _state_ref()
    snapshot = _snapshot(state_ref)
    invocation = compiler_invocation_context(
        state_ref,
        _turn(state_ref, attempt.rejected_tactic, attempt.native_error_message),
    )
    compiler = ProofStateCompiler(
        features=features or (hypothesis_scope_diagnosis_feature(),)
    )
    environment = CompilationEnvironment("hypothesis-scope-environment", (), ())
    plan = compiler.plan_native_semantics(snapshot, environment, invocation)
    assert len(plan.requests) == 1
    environment = environment.with_native_semantic_observations(
        (_observation(plan.requests[0], attempt),)
    )
    return invocation, compiler.compile(snapshot, environment, invocation)


def _certification(bundle, candidate) -> CertificationResult:
    return CertificationResult(
        candidate_id=candidate.candidate_id,
        state_ref=bundle.state_ref,
        policy=candidate.certification_policy,
        intent=candidate.intent,
        payload_sha256=frozen_json_sha256(candidate.payload),
        accepted=True,
        verification_ref=(
            "tactic.preflight.produced:hypothesis-scope@sha256:" + "d" * 64
        ),
        checked_effect=freeze_json_object({
            "accepted": True,
            "outcome_known": True,
            "goal_after_closed": True,
            "goal_after_remaining": 0,
        }),
    )


def _rendered(invocation, bundle, *feature_ids, mode=TREATMENT, certify=True):
    assembly = feature_assembly(*feature_ids, mode=mode)
    certifications = tuple(
        _certification(bundle, item)
        for item in bundle.candidate_surface.actions
    ) if certify else ()
    admitted = admit_action_surface(
        bundle.candidate_surface,
        certifications,
        assembly.manifest,
        triggers=invocation.triggers,
    )
    if admitted.action_surface.empty:
        return admitted, ""
    return admitted, render_action_surface_payload(
        action_surface_payload(admitted.action_surface)
    ).text


# --------------------------------------------------------------- direct smt


def test_smt_hypothesis_hint_without_checked_candidate_is_facts_only() -> None:
    invocation, bundle = _compile(_attempt("smt(H4 nosuch).", _smt(count=2)))

    ownership = bundle.analyzed_state.recovery_ownership
    assert ownership.owner_feature_id == HYPOTHESIS_SCOPE_DIAGNOSIS_FEATURE_ID
    assert ownership.allowed_output_kinds == ("diagnostic",)
    assert bundle.candidate_surface.actions == ()
    diagnostic = bundle.candidate_surface.diagnostics[0].diagnostic
    assert diagnostic.applicability == "explanation_only"
    assert diagnostic.code == "smt_hint_names_goal_hypothesis"
    assert diagnostic.primary == (
        "`H4` is a hypothesis of the current goal, not a global lemma. "
        "`smt(...)` hints name global lemmas, axioms or theories; the goal's "
        "hypotheses are already given to smt."
    )
    assert diagnostic.help == "" and diagnostic.terminal == ""
    admitted, markdown = _rendered(
        invocation, bundle, HYPOTHESIS_SCOPE_DIAGNOSIS_FEATURE_ID
    )
    assert markdown == "## Compiler diagnostic\n\n" + diagnostic.primary
    assert len(markdown.encode("utf-8")) <= 700
    hidden, _ = _rendered(
        invocation, bundle, HYPOTHESIS_SCOPE_DIAGNOSIS_FEATURE_ID, mode=AUDIT
    )
    assert hidden.action_surface.empty


def test_smt_hint_dropped_candidate_is_one_certified_do_you_mean() -> None:
    descriptor = _smt(
        position=2, count=2, candidate="smt(f_all).", remaining=("f_all",)
    )
    invocation, bundle = _compile(_attempt("smt(f_all H4).", descriptor))

    ownership = bundle.analyzed_state.recovery_ownership
    assert ownership.allowed_output_kinds == ("action",)
    assert ownership.preservation_witness.witness_kind == (
        "native_argument_realization"
    )
    assert bundle.candidate_surface.diagnostics == ()
    (action,) = bundle.candidate_surface.actions
    assert action.payload.to_dict() == {"tactic": "smt(f_all)."}
    assert action.certification_policy == "exact_tactic_preflight"
    assert action.strategy_contract.required_commitment == (
        "agent_selected_smt_call_and_remaining_hints"
    )
    assert action.correction.reason == (
        "`H4` is a hypothesis of the current goal, not a global lemma. "
        "`smt(...)` hints name global lemmas, axioms or theories; the goal's "
        "hypotheses are already given to smt. EasyCrypt accepts the same "
        "`smt` call without the `H4` hint."
    )
    admitted, markdown = _rendered(
        invocation, bundle, HYPOTHESIS_SCOPE_DIAGNOSIS_FEATURE_ID
    )
    assert markdown.startswith("## Do you mean?\n\n`H4` is a hypothesis")
    assert '{"intent":"commit_tactic","payload":{"tactic":"smt(f_all)."}}' in (
        markdown
    )
    assert len(markdown.encode("utf-8")) <= 700
    # Without the manager's exact preflight nothing is shown: no uncertified
    # action, and the analysis formed no fallback explanation.
    uncertified, _ = _rendered(
        invocation, bundle, HYPOTHESIS_SCOPE_DIAGNOSIS_FEATURE_ID,
        certify=False,
    )
    assert uncertified.action_surface.empty


# ----------------------------------------------------------- direct rewrite


def test_rewrite_name_declared_after_target_is_explanation_only() -> None:
    invocation, bundle = _compile(
        _attempt("rewrite mem_set Hbad in H18.", _rewrite(position=2, count=2))
    )

    assert bundle.candidate_surface.actions == ()
    diagnostic = bundle.candidate_surface.diagnostics[0].diagnostic
    assert diagnostic.code == "rewrite_name_declared_after_target"
    assert diagnostic.primary == (
        "`Hbad` is a hypothesis of the current goal, declared after `H18`; "
        "`rewrite … in H18` resolves names in the context before `H18`."
    )
    _admitted, markdown = _rendered(
        invocation, bundle, HYPOTHESIS_SCOPE_DIAGNOSIS_FEATURE_ID
    )
    assert markdown == "## Compiler diagnostic\n\n" + diagnostic.primary


@pytest.mark.parametrize(
    "attempt",
    (
        # The native realizer abstained: the name is not a goal hypothesis,
        # it resolves where the operation looks, or no failing reference
        # was established.
        _attempt("smt(nosuch).", None, resource=""),
        _attempt("rewrite Hbad in H18.", None, resource="Hbad"),
    ),
)
def test_no_native_realization_means_no_claim_and_silence(attempt) -> None:
    _invocation, bundle = _compile(attempt)

    assert bundle.analyzed_state.recovery_ownership.owner_feature_id == ""
    assert bundle.candidate_surface.actions == ()
    assert bundle.candidate_surface.diagnostics == ()


def test_codec_rejects_a_realization_of_another_attempt() -> None:
    descriptor = _rewrite()
    with pytest.raises(ValueError, match="does not realize its attempt"):
        OUT_OF_SCOPE_HYPOTHESIS_CODEC.read(
            _attempt("rewrite Hbad in H18.", descriptor, resource="H18")
        )
    with pytest.raises(ValueError, match="does not realize its attempt"):
        OUT_OF_SCOPE_HYPOTHESIS_CODEC.read(
            _attempt("rewrite Hbad in H18.", descriptor, family="smt")
        )


@pytest.mark.parametrize(
    "changes",
    (
        {"declared_after_target": True},
        {"target_name": "H18"},
        {"reference_position": 3, "reference_count": 2},
        {"reference_count": 17, "reference_position": 1},
        {"goal_hypothesis": False},
        # The candidate must be the agent's own smt call.
        {"candidate_tactic": "smtx(f_all).", "remaining_hints": ("f_all",),
         "reference_count": 2},
        {"candidate_tactic": "smt().", "remaining_hints": ("f_all",)},
        {"written_name": "Top.H4"},
        {"failure_kind": "rewrite_name_declared_after_target"},
    ),
)
def test_smt_descriptor_rejects_inconsistent_native_facts(changes) -> None:
    with pytest.raises(ValueError, match="descriptor is invalid"):
        dataclasses.replace(_smt(), **changes)


@pytest.mark.parametrize(
    "changes",
    (
        {"declared_after_target": False},
        {"target_name": ""},
        {"target_name": "Hbad"},
        {"candidate_tactic": "rewrite Hbad in H19."},
        {"lookup_scope": "global_declarations"},
    ),
)
def test_rewrite_descriptor_rejects_inconsistent_native_facts(changes) -> None:
    with pytest.raises(ValueError, match="descriptor is invalid"):
        dataclasses.replace(_rewrite(), **changes)


# ------------------------------------------------------------- gate/prefilter


@pytest.mark.parametrize(
    "tactic",
    (
        "smt(H4).",
        "smt(f_all H4).",
        "smt(H4) .",
        "rewrite Hbad in H18.",
        "rewrite mem_set -Hbad /= in H18.",
        "by rewrite Hbad in H18.",
        "by smt(H4).",
    ),
)
def test_lexical_gate_schedules_bounded_smt_and_rewrite_in(tactic) -> None:
    assert is_hypothesis_scope_candidate(tactic)


@pytest.mark.parametrize(
    "tactic",
    (
        "smt.",
        "smt().\nsmt().",
        "move=> H4; smt(H4).",
        "rewrite Hbad.",
        "rewrite Hbad in H18",
        "apply H4.",
        "rewrite Hbad in H18 => x.",
        'smt("H4").',
        "smt(H4 (* note *)).",
    ),
)
def test_lexical_gate_abstains_outside_its_bounded_shapes(tactic) -> None:
    assert not is_hypothesis_scope_candidate(tactic)


def test_gate_runs_only_on_an_unchanged_failed_commit() -> None:
    gate = hypothesis_scope_diagnosis_feature().execution_gate
    state_ref = _state_ref()
    assert gate.evaluate(_turn(state_ref, "smt(H4).", SMT_ERROR)).eligible
    assert not gate.evaluate(_turn(
        state_ref, "smt(H4).", "", outcome_kind="accepted",
        proof_state_effect="changed",
    )).eligible
    assert not gate.evaluate(_turn(state_ref, "apply H4.", SMT_ERROR)).eligible
    assert not gate.evaluate(None).eligible


# ---------------------------------------------------- operation binding (B1)


def test_operation_binding_and_hypothesis_scope_never_both_claim() -> None:
    features = (
        hypothesis_scope_diagnosis_feature(),
        operation_binding_repair_feature(),
    )
    _invocation, bundle = _compile(
        _attempt("smt(H4).", _smt()), features=features
    )
    ownership = bundle.analyzed_state.recovery_ownership
    assert ownership.claimant_feature_ids == (
        HYPOTHESIS_SCOPE_DIAGNOSIS_FEATURE_ID,
    )

    # A written name that resolves to nothing is B1's: the native realizer
    # leaves it unrealized, so this slice makes no claim.
    state_ref = _state_ref()
    snapshot = _snapshot(state_ref)
    invocation = compiler_invocation_context(
        state_ref, _turn(state_ref, "apply holds_al.", "unknown lemma"),
    )
    compiler = ProofStateCompiler(features=features)
    environment = CompilationEnvironment("hypothesis-scope-environment", (), ())
    plan = compiler.plan_native_semantics(snapshot, environment, invocation)
    environment = environment.with_native_semantic_observations(tuple(
        attempted_operation_native_observation(
            request, failure_kind="proof_term_lookup_failure"
        )
        for request in plan.requests
    ))
    follow_up = compiler.plan_native_semantics(snapshot, environment, invocation)
    environment = environment.with_native_semantic_observations(tuple(
        namespace_spelling_set_observation(item, spellings=())
        for item in follow_up.requests
    ))
    bundle = compiler.compile(snapshot, environment, invocation)
    assert HYPOTHESIS_SCOPE_DIAGNOSIS_FEATURE_ID not in (
        bundle.analyzed_state.recovery_ownership.claimant_feature_ids
    )


# ------------------------------------------------------------ compound suffix


def _compile_compound(
    rejected: str,
    boundary: NativeAttemptedOperationDescriptor,
    *,
    accepted_effect: str = "accepted_changed",
):
    state_ref = _state_ref()
    snapshot = _snapshot(state_ref)
    invocation = compiler_invocation_context(
        state_ref,
        _turn(state_ref, rejected, boundary.native_error_message),
    )
    compiler = ProofStateCompiler(features=(
        compound_tactic_prefix_recovery_feature(),
        hypothesis_scope_diagnosis_feature(),
    ))
    environment = CompilationEnvironment("hypothesis-scope-environment", (), ())
    plan = compiler.plan_native_semantics(snapshot, environment, invocation)
    (request,) = plan.requests
    assert isinstance(request.query, NativeTacticPrefixDiagnosticQuery)
    candidates = compound_prefix_candidates(rejected)
    accepted = candidates
    descriptor = NativeTacticPrefixDiagnosticDescriptor(
        rejected_tactic=rejected,
        candidate_prefixes=candidates,
        prefix_effects=tuple(accepted_effect for _ in candidates),
        accepted_prefixes=accepted,
        boundary_tactic=compound_accepted_prefix_extension(
            rejected,
            accepted_prefix=accepted[-1],
            candidate_prefixes=candidates,
        ),
        native_failure_kind=boundary.native_failure_kind,
        native_error_message=boundary.native_error_message,
        boundary_failure_kind=boundary.native_failure_kind,
        boundary_error_message=boundary.native_error_message,
        goal_kind="formula",
        boundary_attempt=boundary,
    )
    environment = environment.with_native_semantic_observations(
        (_observation(request, descriptor),)
    )
    return invocation, compiler.compile(snapshot, environment, invocation)


def test_compound_suffix_rewrite_names_the_temporary_goal() -> None:
    invocation, bundle = _compile_compound(
        "move=> H18 Hbad; rewrite Hbad in H18.",
        _attempt("rewrite Hbad in H18.", _rewrite()),
    )

    ownership = bundle.analyzed_state.recovery_ownership
    assert ownership.owner_feature_id == HYPOTHESIS_SCOPE_DIAGNOSIS_FEATURE_ID
    diagnostic = bundle.candidate_surface.diagnostics[0].diagnostic
    assert diagnostic.primary.startswith(
        "Your compound tactic failed and was rolled back"
    )
    assert diagnostic.primary.endswith(
        "`Hbad` is a hypothesis of the temporary goal produced by that "
        "accepted stage, declared after `H18`; `rewrite … in H18` resolves "
        "names in the context before `H18`."
    )
    assert diagnostic.terminal == ""
    _admitted, markdown = _rendered(
        invocation, bundle,
        "compound_tactic_prefix_recovery",
        HYPOTHESIS_SCOPE_DIAGNOSIS_FEATURE_ID,
    )
    assert "  rewrite Hbad in H18." in markdown
    assert "  unknown lemma `Hbad'" in markdown
    hidden, _ = _rendered(
        invocation, bundle,
        "compound_tactic_prefix_recovery",
        HYPOTHESIS_SCOPE_DIAGNOSIS_FEATURE_ID,
        mode=AUDIT,
    )
    assert hidden.action_surface.empty


def test_compound_smt_candidate_is_recomposed_with_the_accepted_prefix() -> None:
    invocation, bundle = _compile_compound(
        "move=> H4; smt(H4).",
        _attempt("smt(H4).", _smt(candidate="smt().")),
    )

    (action,) = bundle.candidate_surface.actions
    assert action.payload.to_dict() == {"tactic": "move=> H4; smt()."}
    assert "the temporary goal produced by that accepted stage, not a " in (
        action.correction.reason
    )
    _admitted, markdown = _rendered(
        invocation, bundle,
        "compound_tactic_prefix_recovery",
        HYPOTHESIS_SCOPE_DIAGNOSIS_FEATURE_ID,
    )
    assert markdown.startswith("## Do you mean?\n\nYour compound tactic failed")
    assert "move=> H4; smt()." in markdown


def test_compound_no_progress_prefix_keeps_the_current_goal() -> None:
    _invocation, bundle = _compile_compound(
        "idtac; smt(H4).",
        _attempt("smt(H4).", _smt()),
        accepted_effect="accepted_no_progress",
    )

    diagnostic = bundle.candidate_surface.diagnostics[0].diagnostic
    assert diagnostic.primary.endswith(
        "`H4` is a hypothesis of the current goal, not a global lemma. "
        "`smt(...)` hints name global lemmas, axioms or theories; the goal's "
        "hypotheses are already given to smt."
    )


# --------------------------------------------------------------- registration


def test_registered_in_the_production_treatment_with_its_own_policy() -> None:
    profile = PRODUCTION_COMPILER_PROFILES[ALL_CANDIDATE_TREATMENT_PROFILE]
    assert (HYPOTHESIS_SCOPE_DIAGNOSIS_FEATURE_ID, TREATMENT) in {
        (item.feature_id, item.mode) for item in profile.activations
    }
    assert HYPOTHESIS_SCOPE_DIAGNOSIS_ONCE_POLICY_ID in profile.delivery_policy_ids
    (policy,) = (
        item for item in default_delivery_policy_catalog().definitions
        if item.policy_id == HYPOTHESIS_SCOPE_DIAGNOSIS_ONCE_POLICY_ID
    )
    assert policy.compatible_feature_ids == (
        HYPOTHESIS_SCOPE_DIAGNOSIS_FEATURE_ID,
    )
    assert policy.max_items == 1
