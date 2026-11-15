"""Contracts for failure-linked localization of a failing smt call."""
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
    admit_action_surface,
    render_action_surface_payload,
)
from core.easycrypt.proof_state_compiler.backend.recovery_handoff_lowering import (
    recovery_handoff_message,
)
from core.easycrypt.proof_state_compiler.contracts import (
    AttemptRealization,
    CompilerTurnEvidence,
    NativeAttemptDiagnosticQuery,
    NativeAttemptedOperationDescriptor,
    NativeSemanticObservation,
    NativeSemanticRequest,
    NativeTacticPrefixDiagnosticDescriptor,
    NativeTacticPrefixDiagnosticQuery,
    TargetRef,
    TransitionRef,
    compiler_invocation_context,
    freeze_json_object,
)
from core.easycrypt.proof_state_compiler.features.compound_tactic_prefix_recovery import (
    COMPOUND_TACTIC_PREFIX_RECOVERY_FEATURE_ID,
    compound_tactic_prefix_recovery_feature,
)
from core.easycrypt.proof_state_compiler.features.compound_tactic_prefix_recovery.syntax import (
    compound_accepted_prefix_extension,
    compound_prefix_candidates,
)
from core.easycrypt.proof_state_compiler.features.smt_failure_localization import (
    SMT_FAILURE_LOCALIZATION_FEATURE_ID,
    smt_failure_localization_feature,
)
from core.easycrypt.proof_state_compiler.features.smt_failure_localization.realization import (
    SMT_FAILURE_LOCALIZATION_CODEC,
    SMT_FAILURE_LOCALIZATION_KIND,
    NativeSmtFailureLocalization,
)
from core.easycrypt.proof_state_compiler.features.smt_failure_localization.syntax import (
    is_direct_smt_failure_candidate,
)
from tests.helpers.compiler_feature_assembly import feature_assembly
from tests.helpers.proof_state_compiler import native_state, typed_node
from workflow.proof_state_compiler.activation import AUDIT, TREATMENT
from workflow.proof_state_compiler.delivery_policies import (
    SMT_FAILURE_LOCALIZATION_ONCE_POLICY_ID,
    default_delivery_policy_catalog,
)


STRICT_ERROR = "cannot prove goal (strict)"
MANAGER_ERROR = "[error-0-24] " + STRICT_ERROR


def _state_ref() -> StateRef:
    return StateRef(
        session_id="smt-failure-test",
        state_version=4,
        goal_identity="smt-failure-goal",
        goal_identity_required=True,
        committed_prefix_identity="a" * 64,
    )


def _snapshot(state_ref: StateRef) -> AuthoritativeSnapshotInput:
    return AuthoritativeSnapshotInput(
        state_ref=state_ref,
        provenance=ProvenanceRef(
            producer="smt-failure.fixture",
            authority="compiler.input.produced",
            source_sha256="b" * 64,
            artifact_ref="compiler_inputs/smt-failure.json",
            source_event_id="compiler-input-smt-failure",
            source_event_sequence=4,
            authoritative=True,
        ),
        target=TargetRef("eval/smt_failure.ec", "smt_failure_goal"),
        transition=TransitionRef(
            "rejected", state_ref, "compiler_inputs/smt-failure.json"
        ),
        goal_lines=("Current goal", "--------", "0 <= x => p x"),
        goal_count=1,
        goal_count_known=True,
        closed=False,
        native_state=native_state(
            state_ref,
            formula=typed_node("implication", "0 <= x => p x"),
        ),
    )


def _turn(
    state_ref: StateRef,
    tactic: str,
    *,
    structured_error: str = MANAGER_ERROR,
) -> CompilerTurnEvidence:
    return CompilerTurnEvidence(
        source_event_id="smt-failure-event",
        source_event_sequence=5,
        authority_kind="event_bound_tactic_execution_result",
        artifact_ref="tactic_execution_results/smt-failure.json",
        artifact_hash="c" * 64,
        hash_algorithm="sha256",
        post_state_ref=state_ref,
        intent="commit_tactic",
        payload=freeze_json_object({"tactic": tactic}),
        outcome_kind="rejected",
        proof_state_effect="unchanged",
        structured_error=structured_error,
    )


def _localization(
    tactic: str,
    *,
    call: str = "smt()",
    occurrence: int = 0,
    count: int = 1,
    complete: bool = True,
    kind: str = "formula",
    report_call: int = 2,
    strict_call: int = 2,
) -> NativeSmtFailureLocalization:
    encoded = tactic.encode("utf-8")
    start = -1
    for _ in range(occurrence + 1):
        start = encoded.find(call.encode("utf-8"), start + 1)
    assert start >= 0
    return NativeSmtFailureLocalization(
        smt_call_text=call,
        smt_call_start=start,
        smt_call_end=start + len(call.encode("utf-8")),
        failed_goal_count=count,
        failed_goal_count_complete=complete,
        first_failed_goal_kind=kind,
        report_failure_call=report_call,
        strict_failure_call=strict_call,
        failure_kind="smt_call_failed",
    )


def _realization(descriptor: NativeSmtFailureLocalization) -> AttemptRealization:
    payload = dataclasses.asdict(descriptor)
    failure_kind = payload.pop("failure_kind")
    return AttemptRealization(
        kind=SMT_FAILURE_LOCALIZATION_KIND,
        failure_kind=failure_kind,
        payload=freeze_json_object(payload),
    )


def _attempt(
    tactic: str,
    descriptor: NativeSmtFailureLocalization | None,
    *,
    error: str = STRICT_ERROR,
    family: str = "smt_call",
) -> NativeAttemptedOperationDescriptor:
    return NativeAttemptedOperationDescriptor(
        operation_family=family,
        rejected_tactic=tactic,
        exact_resource="",
        argument_kinds=(),
        side="",
        positions=(),
        native_diagnostic_status="blocker",
        native_failure_kind=(
            "smt_call_failed" if descriptor is not None else "native_user_error"
        ),
        native_error_message=error,
        attempt_outcome="rejected",
        goal_kind="implication",
        realization=None if descriptor is None else _realization(descriptor),
    )


def _observation(
    request: NativeSemanticRequest,
    descriptor: NativeAttemptedOperationDescriptor
    | NativeTacticPrefixDiagnosticDescriptor,
) -> NativeSemanticObservation:
    return NativeSemanticObservation.accepted(
        request=request,
        batch_id=f"smt-failure-batch-{request.request_id}",
        batch_index=0,
        batch_size=1,
        batch_elapsed_ms=2,
        result_formula="",
        descriptor=descriptor,
        runtime_identity_sha256="d" * 64,
        companion_identity_sha256="e" * 64,
        elapsed_ms=2,
        provenance=ProvenanceRef(
            producer="test.native_smt_failure",
            authority="native.semantic.batch.produced",
            source_sha256="f" * 64,
            artifact_ref="native_semantic_batches/smt-failure-test.json",
            source_event_id="native-semantic-smt-failure-test",
            source_event_sequence=6,
            authoritative=True,
        ),
    )


def _compile_direct(
    tactic: str,
    descriptor: NativeSmtFailureLocalization | None,
    *,
    manager_error: str = MANAGER_ERROR,
    native_error: str = STRICT_ERROR,
):
    state_ref = _state_ref()
    snapshot = _snapshot(state_ref)
    invocation = compiler_invocation_context(
        state_ref, _turn(state_ref, tactic, structured_error=manager_error)
    )
    compiler = ProofStateCompiler(features=(smt_failure_localization_feature(),))
    environment = CompilationEnvironment("smt-failure-environment", (), ())
    plan = compiler.plan_native_semantics(snapshot, environment, invocation)
    assert len(plan.requests) == 1
    request = plan.requests[0]
    assert isinstance(request.query, NativeAttemptDiagnosticQuery)
    assert request.query.realizer_kinds == (SMT_FAILURE_LOCALIZATION_KIND,)
    environment = environment.with_native_semantic_observations((
        _observation(request, _attempt(tactic, descriptor, error=native_error)),
    ))
    return invocation, compiler.compile(snapshot, environment, invocation)


def _render(bundle) -> str:
    diagnostic = bundle.candidate_surface.diagnostics[0].diagnostic
    return render_action_surface_payload({
        "schema_version": 1,
        "resources": [],
        "bindings": [],
        "actions": [],
        "diagnostics": [{"primary": diagnostic.primary}],
    }).text


# --------------------------------------------------------------------------
# Lexical gate


@pytest.mark.parametrize("tactic", [
    "by move=> H; split; smt().",
    "first by auto; rewrite /inv; smt(size_ge0).",
    "[smt() | split; [smt() | smt()]].",
    "do ! (split; try smt()).",
    "have Hd : x <> y by smt(neq_ltz).",
    "progress => /#.",
])
def test_direct_gate_accepts_one_tactic_that_mentions_smt(tactic: str) -> None:
    assert is_direct_smt_failure_candidate(tactic)


@pytest.mark.parametrize("tactic", [
    "move=> H; split; smt().",          # top-level sequence: handoff owns it
    "proc; auto; smt().",
    "move=> H; [smt() | smt()].",
    "do ! split; try smt().",
    "move=> H.\nsmt().",                # multi-sentence: handoff owns it
    "smt().",                           # one lone call on the current goal
    "smt(foo bar).",
    "by smt().",
    "try smt(ge0_mu).",
    "move=> H; split.",                 # no smt call
    "rewrite smt_lemma.",               # an identifier, not the tactic
    "by move=> H; (* smt *) split.",    # comment: abstain
    "smt",                              # unterminated
    "",
])
def test_direct_gate_rejects_sequences_lone_calls_and_non_smt(tactic: str) -> None:
    assert not is_direct_smt_failure_candidate(tactic)


def test_sequences_are_left_to_the_handoff_source() -> None:
    state_ref = _state_ref()
    tactic = "move=> H; split; smt()."
    invocation = compiler_invocation_context(state_ref, _turn(state_ref, tactic))
    compiler = ProofStateCompiler(features=(smt_failure_localization_feature(),))
    plan = compiler.plan_native_semantics(
        _snapshot(state_ref),
        CompilationEnvironment("smt-failure-environment", (), ()),
        invocation,
    )
    assert plan.requests == ()
    decision = smt_failure_localization_feature().execution_gate.evaluate(
        _turn(state_ref, tactic)
    )
    assert not decision.eligible
    assert decision.reason == "smt_failure_not_prefiltered"


# --------------------------------------------------------------------------
# Codec


def test_codec_reads_a_located_call_and_rejects_a_drifted_one() -> None:
    tactic = "by move=> H; split; smt()."
    good = _localization(tactic)
    assert SMT_FAILURE_LOCALIZATION_CODEC.read(_attempt(tactic, good)) == good
    shifted = dataclasses.replace(
        good,
        smt_call_start=good.smt_call_start - 1,
        smt_call_end=good.smt_call_end - 1,
    )
    with pytest.raises(ValueError):
        SMT_FAILURE_LOCALIZATION_CODEC.read(_attempt(tactic, shifted))
    with pytest.raises(ValueError):
        SMT_FAILURE_LOCALIZATION_CODEC.read(
            _attempt(tactic, good, family="compound_tactic")
        )


@pytest.mark.parametrize("change", [
    {"strict_failure_call": 3},
    {"failed_goal_count": 0},
    {"first_failed_goal_kind": "probability"},
    {"failure_kind": "native_user_error"},
    {"smt_call_end": 99},
])
def test_descriptor_rejects_disagreeing_or_incomplete_payloads(change) -> None:
    with pytest.raises(ValueError):
        dataclasses.replace(_localization("by split; smt()."), **change)


# --------------------------------------------------------------------------
# Direct analysis and wording


def test_direct_program_judgment_failure_is_one_owned_explanation() -> None:
    tactic = "by proc; auto; smt()."
    _invocation, bundle = _compile_direct(
        tactic,
        _localization(tactic, kind="phoare_statement", report_call=1, strict_call=1),
    )
    ownership = bundle.analyzed_state.recovery_ownership
    assert ownership.owner_feature_id == SMT_FAILURE_LOCALIZATION_FEATURE_ID
    assert bundle.candidate_surface.actions == ()
    (candidate,) = bundle.candidate_surface.diagnostics
    diagnostic = candidate.diagnostic
    assert diagnostic.applicability == "explanation_only"
    assert diagnostic.help == "" and diagnostic.notes == ()
    assert diagnostic.primary == (
        "Running your tactic on the current goal, the first smt call "
        "EasyCrypt cannot prove is `smt()`.\n\n"
        "In EasyCrypt's report mode, which admits a failed smt goal and "
        "continues, this call fails on 1 goal. That goal is a `phoare` "
        "judgment; smt does not reason about programs: it treats a program "
        "judgment as an opaque proposition."
    )


def test_second_identical_call_is_named_by_its_position() -> None:
    tactic = "by split; [smt() | smt()]."
    _invocation, bundle = _compile_direct(
        tactic, _localization(tactic, occurrence=1, count=1)
    )
    primary = bundle.candidate_surface.diagnostics[0].diagnostic.primary
    assert "`smt()` (the 2nd `smt()` from the left)." in primary
    assert "That goal is a pure logical formula." in primary


def test_count_and_unknown_kind_are_reported_without_guessing() -> None:
    tactic = "by move=> H; do ! split; smt(holds_all)."
    _invocation, bundle = _compile_direct(
        tactic,
        _localization(
            tactic, call="smt(holds_all)", count=3, complete=False, kind=""
        ),
    )
    primary = bundle.candidate_surface.diagnostics[0].diagnostic.primary
    assert "this call fails on at least 3 goals." in primary
    assert "judgment" not in primary and "formula" not in primary
    assert primary.endswith("fails on at least 3 goals.")


def test_several_failed_goals_describe_the_first_one() -> None:
    tactic = "by move=> H; progress; try smt()."
    _invocation, bundle = _compile_direct(
        tactic, _localization(tactic, count=2, kind="equiv_statement")
    )
    primary = bundle.candidate_surface.diagnostics[0].diagnostic.primary
    assert "fails on 2 goals. The first of them is an `equiv` judgment;" in primary


def test_treatment_shows_and_audit_hides_the_explanation() -> None:
    tactic = "by proc; auto; smt()."
    invocation, bundle = _compile_direct(
        tactic, _localization(tactic, kind="phoare_statement")
    )
    treatment = feature_assembly(SMT_FAILURE_LOCALIZATION_FEATURE_ID, mode=TREATMENT)
    audit = feature_assembly(SMT_FAILURE_LOCALIZATION_FEATURE_ID, mode=AUDIT)
    treated = admit_action_surface(
        bundle.candidate_surface, (), treatment.manifest,
        triggers=invocation.triggers,
    )
    hidden = admit_action_surface(
        bundle.candidate_surface, (), audit.manifest,
        triggers=invocation.triggers,
    )
    assert len(treated.action_surface.diagnostics) == 1
    assert hidden.action_surface.empty
    policy = next(
        item for item in default_delivery_policy_catalog().definitions
        if item.policy_id == SMT_FAILURE_LOCALIZATION_ONCE_POLICY_ID
    )
    assert len(_render(bundle).encode("utf-8")) <= policy.max_markdown_bytes


# --------------------------------------------------------------------------
# Abstention


def test_manager_error_must_be_the_strict_native_error() -> None:
    tactic = "by move=> H; split; smt()."
    _invocation, bundle = _compile_direct(
        tactic,
        _localization(tactic),
        manager_error="[error] unknown lemma `foo'",
    )
    assert bundle.candidate_surface.diagnostics == ()
    assert bundle.analyzed_state.recovery_ownership.owner_feature_id == ""


def test_no_realization_means_no_claim() -> None:
    tactic = "by move=> H; rewrite nosuchlemma; smt()."
    _invocation, bundle = _compile_direct(
        tactic, None, native_error="unknown lemma `nosuchlemma'",
        manager_error="[error] unknown lemma `nosuchlemma'",
    )
    assert bundle.candidate_surface.diagnostics == ()


@pytest.mark.parametrize("tactic", ["by smt(foo).", "try smt()."])
def test_a_lone_call_on_the_current_goal_adds_nothing(tactic: str) -> None:
    # The gate keeps such commits away; the analysis abstains as well.
    state_ref = _state_ref()
    snapshot = _snapshot(state_ref)
    invocation = compiler_invocation_context(state_ref, _turn(state_ref, tactic))
    compiler = ProofStateCompiler(features=(smt_failure_localization_feature(),))
    environment = CompilationEnvironment("smt-failure-environment", (), ())
    request = NativeSemanticRequest(
        state_ref=state_ref,
        request_id="smt-failure-attempt:lone",
        producer_id="smt_failure_localization.native_diagnostic",
        query=NativeAttemptDiagnosticQuery(
            rejected_tactic=tactic,
            observed_outcome_kind="rejected",
            realizer_kinds=(SMT_FAILURE_LOCALIZATION_KIND,),
        ),
        evidence_refs=(invocation.failure_observation.evidence_ref,),
    )
    call = tactic.split(" ", 1)[1][:-1]
    environment = environment.with_native_semantic_observations((
        _observation(
            request,
            _attempt(tactic, _localization(tactic, call=call, report_call=1, strict_call=1)),
        ),
    ))
    bundle = compiler.compile(snapshot, environment, invocation)
    assert bundle.proof_ir.attempted_operation is not None
    assert bundle.proof_ir.attempted_operation.realization is not None
    assert bundle.candidate_surface.diagnostics == ()


# --------------------------------------------------------------------------
# Recovery handoff consumer


def _compile_handoff(
    rejected_tactic: str,
    suffix_attempt: NativeAttemptedOperationDescriptor | None,
    *,
    accepted_effect: str = "accepted_changed",
    native_candidates: tuple[str, ...] | None = None,
    features=None,
):
    state_ref = _state_ref()
    snapshot = _snapshot(state_ref)
    invocation = compiler_invocation_context(
        state_ref, _turn(state_ref, rejected_tactic)
    )
    compiler = ProofStateCompiler(features=features or (
        compound_tactic_prefix_recovery_feature(),
        smt_failure_localization_feature(),
    ))
    environment = CompilationEnvironment("smt-failure-environment", (), ())
    plan = compiler.plan_native_semantics(snapshot, environment, invocation)
    # Only the handoff source asks EasyCrypt about a top-level sequence.
    (request,) = plan.requests
    assert isinstance(request.query, NativeTacticPrefixDiagnosticQuery)
    # EasyCrypt keeps only the leading cuts its own grammar delimits.
    candidates = native_candidates or compound_prefix_candidates(
        rejected_tactic
    )
    descriptor = NativeTacticPrefixDiagnosticDescriptor(
        rejected_tactic=rejected_tactic,
        candidate_prefixes=candidates,
        prefix_effects=(accepted_effect,) * len(candidates),
        accepted_prefixes=candidates,
        boundary_tactic=compound_accepted_prefix_extension(
            rejected_tactic,
            accepted_prefix=candidates[-1],
            candidate_prefixes=candidates,
        ),
        native_failure_kind="native_user_error",
        native_error_message=STRICT_ERROR,
        boundary_failure_kind=(
            "native_user_error" if suffix_attempt is None
            else suffix_attempt.native_failure_kind
        ),
        boundary_error_message=STRICT_ERROR,
        goal_kind="formula",
        boundary_attempt=suffix_attempt,
    )
    environment = environment.with_native_semantic_observations((
        _observation(request, descriptor),
    ))
    return invocation, compiler.compile(snapshot, environment, invocation)


def test_state_changing_handoff_suffix_is_localized_in_the_temporary_goal() -> None:
    rejected = "proc; auto; smt()."
    suffix = "smt()."
    invocation, bundle = _compile_handoff(
        rejected,
        _attempt(suffix, _localization(
            suffix, kind="phoare_statement", report_call=1, strict_call=1,
        )),
    )
    attempted = bundle.proof_ir.attempted_operation
    assert attempted is not None and attempted.recovery_handoff is not None
    ownership = bundle.analyzed_state.recovery_ownership
    assert ownership.owner_feature_id == SMT_FAILURE_LOCALIZATION_FEATURE_ID
    (candidate,) = bundle.candidate_surface.diagnostics
    assert candidate.delivery_dependency_feature_ids == (
        COMPOUND_TACTIC_PREFIX_RECOVERY_FEATURE_ID,
    )
    primary = candidate.diagnostic.primary
    boundary = recovery_handoff_message(attempted.recovery_handoff)
    assert primary.startswith(boundary + "\n\n")
    assert primary[len(boundary) + 2:] == (
        "Running the failing tactic on the temporary goal produced by those "
        "accepted stages, the first smt call EasyCrypt cannot prove is "
        "`smt()`.\n\n"
        "In EasyCrypt's report mode, which admits a failed smt goal and "
        "continues, this call fails on 1 goal. That goal is a `phoare` "
        "judgment; smt does not reason about programs: it treats a program "
        "judgment as an opaque proposition."
    )
    # Exposure needs both the handoff source and this owner in treatment.
    both = feature_assembly(
        COMPOUND_TACTIC_PREFIX_RECOVERY_FEATURE_ID,
        SMT_FAILURE_LOCALIZATION_FEATURE_ID,
        mode=TREATMENT,
    )
    owner_only = feature_assembly(
        SMT_FAILURE_LOCALIZATION_FEATURE_ID, mode=TREATMENT,
    )
    admitted = admit_action_surface(
        bundle.candidate_surface, (), both.manifest,
        triggers=invocation.triggers,
    )
    withheld = admit_action_surface(
        bundle.candidate_surface, (), owner_only.manifest,
        triggers=invocation.triggers,
    )
    assert len(admitted.action_surface.diagnostics) == 1
    assert withheld.action_surface.empty


def test_no_progress_handoff_refers_to_the_current_goal() -> None:
    rejected = "idtac; by split; smt()."
    suffix = "by split; smt()."
    _invocation, bundle = _compile_handoff(
        rejected,
        _attempt(suffix, _localization(suffix)),
        accepted_effect="accepted_no_progress",
        native_candidates=("idtac.",),
    )
    primary = bundle.candidate_surface.diagnostics[0].diagnostic.primary
    assert "Running the failing tactic on the current goal," in primary


def test_handoff_lone_suffix_call_is_still_reported() -> None:
    # The temporary goal is not visible to the agent, unlike the current one.
    rejected = "move=> H; rewrite /eps; smt()."
    suffix = "smt()."
    _invocation, bundle = _compile_handoff(
        rejected,
        _attempt(suffix, _localization(suffix, report_call=1, strict_call=1)),
    )
    (candidate,) = bundle.candidate_surface.diagnostics
    assert candidate.feature_id == SMT_FAILURE_LOCALIZATION_FEATURE_ID
    assert "That goal is a pure logical formula." in candidate.diagnostic.primary


def test_unlocalized_suffix_keeps_the_generic_boundary() -> None:
    rejected = "move=> H; rewrite /eps; smt()."
    _invocation, bundle = _compile_handoff(rejected, None)
    ownership = bundle.analyzed_state.recovery_ownership
    assert ownership.owner_feature_id == COMPOUND_TACTIC_PREFIX_RECOVERY_FEATURE_ID
    assert bundle.candidate_surface.diagnostics[0].diagnostic.code == (
        "compound_prefix_diagnostic"
    )
