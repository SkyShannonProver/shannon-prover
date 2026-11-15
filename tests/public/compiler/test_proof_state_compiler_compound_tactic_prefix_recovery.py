"""Contracts for commitment-relative compound-tactic prefix recovery."""
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
    admit_action_surface,
    render_action_surface_payload,
)
from core.easycrypt.proof_state_compiler.backend.recovery_handoff_lowering import (
    recovery_handoff_message,
)
from core.easycrypt.proof_state_compiler.compound_boundary_text import (
    compound_boundary_summary,
)
from core.easycrypt.proof_state_compiler.contracts import (
    CompilerTurnEvidence,
    NativeApplicationHeadDescriptor,
    NativeApplicationSlotDescriptor,
    NativeAttemptedOperationDescriptor,
    NativeFormulaDescriptor,
    NativeInputArgument,
    NativeNamespaceSpellingSetQuery,
    NativeResolvedHead,
    NativeSemanticObservation,
    NativeTacticPrefixDiagnosticDescriptor,
    NativeTacticPrefixDiagnosticQuery,
    RecoveryHandoff,
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
from core.easycrypt.proof_state_compiler.features.operation_binding_repair import (
    OPERATION_BINDING_REPAIR_FEATURE_ID,
    operation_binding_repair_feature,
)
from core.easycrypt.proof_state_compiler.features.phl_transitivity_boundary_repair import (
    phl_transitivity_boundary_repair_feature,
)
from core.easycrypt.proof_state_compiler.features.pure_tail_recovery import (
    pure_tail_recovery_feature,
)
from core.easycrypt.proof_state_compiler.features.tactic_dialect_repair import (
    tactic_dialect_repair_feature,
)
from core.easycrypt.proof_state_compiler.contracts.failure import (
    compound_prefix_remainder,
)
from core.easycrypt.proof_state_compiler.frontend.attempted_operation import (
    MANAGER_ERROR_TEXT_LIMIT,
    manager_reports_same_error,
)
from tests.helpers.compiler_feature_assembly import feature_assembly
from tests.helpers.proof_state_compiler import (
    realization_of,
    namespace_spelling_set_observation,
    native_state,
    typed_node,
)
from workflow.proof_state_compiler.activation import (
    AUDIT,
    TREATMENT,
)
from workflow.proof_state_compiler.delivery_policies import (
    COMPOUND_TACTIC_PREFIX_RECOVERY_ONCE_POLICY_ID,
)
from core.easycrypt.proof_state_compiler.features.phl_transitivity_boundary_repair.realization import (
    NativePhlTransitivityBoundaryDescriptor,
)
from core.easycrypt.proof_state_compiler.features.pure_tail_recovery.realization import (
    NativePureTailRewriteDescriptor,
)
from core.easycrypt.proof_state_compiler.features.tactic_dialect_repair.realization import (
    NativeEagerWhileCandidateDescriptor,
    NativeEagerWhileDialectDescriptor,
)


REJECTED_TACTIC = "move=> &hr _; rewrite /eps; smt(sum_le_bound mu_bounded)."
PREFIXES = ("move=> &hr _.", "move=> &hr _; rewrite /eps.")
# EasyCrypt's own report for the whole commit; a native boundary must match it.
BOUNDARY_ERROR = "the first rejected extension failed"


def test_shared_compound_narration_safely_wraps_dynamic_text() -> None:
    summary = compound_boundary_summary(
        accepted_prefix="move=> `x`.",
        accepted_effect="accepted_changed",
        accepted_stage_count=1,
        rejected_extension="rewrite H.\nsmt().",
        native_error="first line\nsecond line",
    )

    assert summary.count("move=> `x`.") == 1
    assert "  move=> `x`.\n\nThe next stage fails:" in summary
    assert "  rewrite H.\n  smt()." in summary
    # The account ends with EasyCrypt's report; it offers no continuations.
    assert summary.endswith("EasyCrypt reports:\n\n  first line\n  second line")


def test_long_real_prefix_is_quoted_once_and_fits_the_owner_budget() -> None:
    """A recorded Opus 5.5 boundary that the old triple quote pushed to 721 B."""

    from workflow.proof_state_compiler.delivery_policies import (
        COMPOUND_TACTIC_PREFIX_RECOVERY_ONCE_POLICY_ID,
        default_delivery_policy_catalog,
    )

    prefix = (
        "move=> &2 Hnp Hp Hl Hb _ _ _ _ _ Hn r; do! split; "
        "[by rewrite mem_set | | | | ]."
    )
    args = {
        "accepted_effect": "accepted_changed",
        "accepted_stage_count": 3,
    }
    text = compound_boundary_summary(
        **args,
        accepted_prefix=prefix,
        rejected_extension="smt(get_setE mem_set domE).",
        native_error="cannot prove goal (strict)",
    )
    markdown = "## Compiler diagnostic\n\n" + text
    policy = next(
        item
        for item in default_delivery_policy_catalog().definitions
        if item.policy_id == COMPOUND_TACTIC_PREFIX_RECOVERY_ONCE_POLICY_ID
    )

    assert text.count(prefix) == 1
    assert len(markdown.encode("utf-8")) <= policy.max_markdown_bytes


def _state_ref() -> StateRef:
    return StateRef(
        session_id="compound-prefix-test",
        state_version=9,
        goal_identity="compound-prefix-goal",
        goal_identity_required=True,
        committed_prefix_identity="a" * 64,
    )


def _snapshot(state_ref: StateRef) -> AuthoritativeSnapshotInput:
    return AuthoritativeSnapshotInput(
        state_ref=state_ref,
        provenance=ProvenanceRef(
            producer="compound-prefix.fixture",
            authority="compiler.input.produced",
            source_sha256="b" * 64,
            artifact_ref="compiler_inputs/compound-prefix.json",
            source_event_id="compiler-input-compound-prefix",
            source_event_sequence=9,
            authoritative=True,
        ),
        target=TargetRef("eval/compound_prefix.ec", "compound_prefix_goal"),
        transition=TransitionRef(
            "rejected", state_ref, "compiler_inputs/compound-prefix.json"
        ),
        goal_lines=("Current goal", "--------", "true"),
        goal_count=1,
        goal_count_known=True,
        closed=False,
        native_state=native_state(
            state_ref,
            formula=typed_node("true", "true"),
        ),
    )


def _turn(
    state_ref: StateRef,
    tactic: str,
    *,
    outcome_kind: str = "rejected",
    source_event_id: str = "compound-prefix-failure",
    source_event_sequence: int = 10,
    structured_error: str = "[error] " + BOUNDARY_ERROR,
) -> CompilerTurnEvidence:
    return CompilerTurnEvidence(
        source_event_id=source_event_id,
        source_event_sequence=source_event_sequence,
        authority_kind="event_bound_tactic_execution_result",
        artifact_ref="tactic_execution_results/compound-prefix-failure.json",
        artifact_hash="c" * 64,
        hash_algorithm="sha256",
        post_state_ref=state_ref,
        intent="commit_tactic",
        payload=freeze_json_object({"tactic": tactic}),
        outcome_kind=outcome_kind,
        proof_state_effect="unchanged",
        structured_error=structured_error,
    )


def _compile(
    *,
    rejected_tactic: str = REJECTED_TACTIC,
    accepted_prefixes: tuple[str, ...] | None = None,
    outcome_kind: str = "rejected",
    accepted_effect: str = "accepted_changed",
    boundary_attempt: NativeAttemptedOperationDescriptor | None = None,
    source_event_id: str = "compound-prefix-failure",
    source_event_sequence: int = 10,
    features=None,
    native_candidates: tuple[str, ...] | None = None,
    native_boundary_failure_kind: str = "native_user_error",
    manager_error: str | None = None,
):
    if manager_error is None:
        manager_error = "[error] " + (
            BOUNDARY_ERROR
            if boundary_attempt is None
            else boundary_attempt.native_error_message
        )
    state_ref = _state_ref()
    snapshot = _snapshot(state_ref)
    lexical_candidates = compound_prefix_candidates(rejected_tactic)
    # EasyCrypt keeps the leading lexical cuts its parse delimits.
    candidates = (
        lexical_candidates if native_candidates is None else native_candidates
    )
    accepted_prefixes = (
        candidates if accepted_prefixes is None else accepted_prefixes
    )
    invocation = compiler_invocation_context(
        state_ref,
        _turn(
            state_ref,
            rejected_tactic,
            outcome_kind=outcome_kind,
            source_event_id=source_event_id,
            source_event_sequence=source_event_sequence,
            structured_error=manager_error,
        ),
    )
    compiler = ProofStateCompiler(
        features=(
            (compound_tactic_prefix_recovery_feature(),)
            if features is None else features
        )
    )
    environment = CompilationEnvironment("compound-prefix-environment", (), ())
    plan = compiler.plan_native_semantics(snapshot, environment, invocation)
    assert len(plan.requests) == 1
    request = plan.requests[0]
    assert isinstance(request.query, NativeTacticPrefixDiagnosticQuery)
    assert request.query.candidate_prefixes == lexical_candidates
    prefix_effects = tuple(
        accepted_effect if item in accepted_prefixes else "rejected"
        for item in candidates
    )
    contiguous = accepted_prefixes == candidates[:len(accepted_prefixes)]
    boundary_tactic = (
        compound_accepted_prefix_extension(
            rejected_tactic,
            accepted_prefix=accepted_prefixes[-1],
            candidate_prefixes=candidates,
        )
        if accepted_prefixes and contiguous
        else ""
    )
    descriptor = NativeTacticPrefixDiagnosticDescriptor(
        rejected_tactic=rejected_tactic,
        candidate_prefixes=candidates,
        prefix_effects=prefix_effects,
        accepted_prefixes=accepted_prefixes,
        boundary_tactic=boundary_tactic,
        native_failure_kind="native_user_error",
        native_error_message="the full compound failed later",
        boundary_failure_kind=(
            native_boundary_failure_kind
            if boundary_attempt is None
            else boundary_attempt.native_failure_kind
        ),
        boundary_error_message=(
            BOUNDARY_ERROR
            if boundary_attempt is None
            else boundary_attempt.native_error_message
        ),
        goal_kind="formula",
        boundary_attempt=boundary_attempt,
    )
    observation = NativeSemanticObservation.accepted(
        request=request,
        batch_id="compound-prefix-test-batch",
        batch_index=0,
        batch_size=1,
        batch_elapsed_ms=2,
        result_formula="",
        descriptor=descriptor,
        runtime_identity_sha256="d" * 64,
        companion_identity_sha256="e" * 64,
        elapsed_ms=2,
        provenance=ProvenanceRef(
            producer="test.native_prefix",
            authority="native.semantic.batch.produced",
            source_sha256="f" * 64,
            artifact_ref="native_semantic_batches/compound-prefix-test.json",
            source_event_id="native-semantic-compound-prefix-test",
            source_event_sequence=11,
            authoritative=True,
        ),
    )
    environment = environment.with_native_semantic_observations((observation,))
    # A B1 consumer of the boundary attempt asks EasyCrypt for same-basename
    # declarations after the accepted prefix; the fixture names have none.
    follow_up = compiler.plan_native_semantics(snapshot, environment, invocation)
    environment = environment.with_native_semantic_observations(tuple(
        namespace_spelling_set_observation(item)
        for item in follow_up.requests
        if isinstance(item.query, NativeNamespaceSpellingSetQuery)
    ))
    bundle = compiler.compile(snapshot, environment, invocation)
    return invocation, bundle


def _render_candidate_diagnostic(bundle) -> str:
    diagnostic = bundle.candidate_surface.diagnostics[0].diagnostic
    item = {"primary": diagnostic.primary}
    if diagnostic.notes:
        item["notes"] = list(diagnostic.notes)
    if diagnostic.placeholder_shape:
        item["placeholder_shape"] = diagnostic.placeholder_shape
    if diagnostic.help:
        item["help"] = diagnostic.help
    if diagnostic.terminal:
        item["terminal"] = diagnostic.terminal
    return render_action_surface_payload({
        "schema_version": 1,
        "resources": [],
        "bindings": [],
        "actions": [],
        "diagnostics": [item],
    }).text


def test_compound_prefix_population_is_complete_and_bounded() -> None:
    assert compound_tactic_prefix_recovery_feature().spec.gate.status == "candidate"
    assert compound_prefix_candidates(
        "rewrite mu_or; smt(ge0_mu)."
    ) == ("rewrite mu_or.",)
    assert compound_prefix_candidates(REJECTED_TACTIC) == PREFIXES
    assert compound_prefix_candidates(
        "case H => [x; smt() | y]; done."
    ) == ("case H => [x; smt() | y].",)
    assert compound_prefix_candidates("rewrite H; (* why *) done.") == ()
    assert compound_prefix_candidates('rewrite H; have X := "x".') == ()
    assert compound_prefix_candidates("rewrite H; (done.") == ()
    assert compound_prefix_candidates("rewrite H;; done.") == ()
    assert compound_prefix_candidates("rewrite H.") == ()
    assert compound_prefix_candidates("a;b;c;d;e;f;g;h;i;j.") == ()
    assert compound_accepted_prefix_extension(
        REJECTED_TACTIC,
        accepted_prefix=PREFIXES[-1],
        candidate_prefixes=PREFIXES,
    ) == "smt(sum_le_bound mu_bounded)."


def test_longest_contiguous_native_prefix_becomes_one_owned_diagnostic() -> None:
    _invocation, bundle = _compile()
    ownership = bundle.analyzed_state.recovery_ownership
    assert ownership.owner_feature_id == (
        COMPOUND_TACTIC_PREFIX_RECOVERY_FEATURE_ID
    )
    assert ownership.operation_family == "compound_tactic"
    assert ownership.selected_resource == ""
    assert ownership.preservation_witness is not None
    assert ownership.preservation_witness.witness_kind == "native_tactic_prefix"
    assert ownership.allowed_output_kinds == ("diagnostic",)
    assert not bundle.analyzed_state.recovery_action_realizations
    assert not bundle.candidate_surface.actions
    assert len(bundle.candidate_surface.diagnostics) == 1
    payload = (
        bundle.candidate_surface.diagnostics[0].diagnostic.identity_payload()
    )
    assert payload == {
        "code": "compound_prefix_diagnostic",
        "primary": (
            "Your compound tactic failed and was rolled back; nothing was "
            "committed.\n\n"
            "EasyCrypt can execute the first 2 stages, which change the "
            "goal:\n\n"
            "  move=> &hr _; rewrite /eps.\n\n"
            "The next stage fails:\n\n"
            "  smt(sum_le_bound mu_bounded).\n\n"
            "EasyCrypt reports:\n\n"
            "  the first rejected extension failed"
        ),
        "applicability": "explanation_only",
    }


def test_gate_accepts_unchanged_no_progress_compound_failure() -> None:
    state_ref = _state_ref()
    gate = compound_tactic_prefix_recovery_feature().execution_gate
    eligibility = gate.evaluate(
        _turn(state_ref, REJECTED_TACTIC, outcome_kind="no_progress")
    )

    assert eligibility.eligible is True


def test_no_progress_prefix_hands_any_native_typed_suffix_to_p2() -> None:
    rejected_tactic = "wp; transitivity y."
    boundary = NativeAttemptedOperationDescriptor(
        operation_family="transitivity",
        rejected_tactic="transitivity y.",
        exact_resource="",
        argument_kinds=("formula",),
        side="",
        positions=(),
        native_diagnostic_status="blocker",
        native_failure_kind="native_user_error",
        native_error_message="the first rejected extension failed",
        attempt_outcome="rejected",
        goal_kind="formula",
    )

    _invocation, bundle = _compile(
        rejected_tactic=rejected_tactic,
        accepted_effect="accepted_no_progress",
        boundary_attempt=boundary,
    )

    attempted = bundle.proof_ir.attempted_operation
    assert attempted is not None
    assert attempted.operation_family == "transitivity"
    assert attempted.rejected_tactic == boundary.rejected_tactic
    assert attempted.state_ref == bundle.state_ref
    assert attempted.recovery_handoff is not None
    assert attempted.recovery_handoff.accepted_prefix_effect == (
        "accepted_no_progress"
    )
    assert attempted.recovery_handoff.source_rejected_tactic == rejected_tactic
    assert attempted.recovery_handoff.derived_rejected_tactic == (
        boundary.rejected_tactic
    )


@pytest.mark.parametrize(
    "rejected_tactic",
    ("wp;transitivity y.", "wp ; transitivity y.", "wp ;transitivity y."),
)
def test_whitespace_before_separator_keeps_the_typed_suffix_handoff(
    rejected_tactic: str,
) -> None:
    boundary = NativeAttemptedOperationDescriptor(
        operation_family="transitivity",
        rejected_tactic="transitivity y.",
        exact_resource="",
        argument_kinds=("formula",),
        side="",
        positions=(),
        native_diagnostic_status="blocker",
        native_failure_kind="native_user_error",
        native_error_message="the first rejected extension failed",
        attempt_outcome="rejected",
        goal_kind="formula",
    )

    _invocation, bundle = _compile(
        rejected_tactic=rejected_tactic,
        accepted_effect="accepted_no_progress",
        boundary_attempt=boundary,
    )

    handoff = bundle.proof_ir.attempted_operation.recovery_handoff
    assert handoff is not None
    assert handoff.source_rejected_tactic == rejected_tactic
    assert handoff.accepted_prefix_tactic == "wp."
    assert handoff.derived_rejected_tactic == "transitivity y."


def test_compound_prefix_boundary_has_one_whitespace_tolerant_spelling() -> None:
    for source in (
        "move=> x; smt().",
        "move=> x;smt().",
        "move=> x ; smt().",
        "move=> x\n; smt().",
    ):
        assert compound_prefix_remainder(source, "move=> x.") == "smt()"
        assert compound_accepted_prefix_extension(
            source,
            accepted_prefix="move=> x.",
            candidate_prefixes=compound_prefix_candidates(source),
        ) == "smt()."
        RecoveryHandoff(
            handoff_kind="native_compound_boundary",
            source_feature_id=COMPOUND_TACTIC_PREFIX_RECOVERY_FEATURE_ID,
            source_rejected_tactic=source,
            accepted_prefix_tactic="move=> x.",
            accepted_prefix_effect="accepted_changed",
            accepted_prefix_stage_count=1,
            derived_rejected_tactic="smt().",
            native_failure_kind="native_user_error",
            native_error_message="failed",
        )
    assert compound_prefix_remainder(
        "wp; sp; auto.", "wp; sp."
    ) == "auto"
    for source, prefix in (
        ("move=> xs; smt().", "move=> x."),
        ("move=> x; .", "move=> x."),
        ("move=> x.", "move=> x."),
        ("case H => [x; smt() | y]; done.", "case H => [x."),
        (" wp; auto.", "wp."),
        ("wp; auto", "wp."),
    ):
        assert compound_prefix_remainder(source, prefix) is None
    with pytest.raises(ValueError, match="recovery handoff is invalid"):
        RecoveryHandoff(
            handoff_kind="native_compound_boundary",
            source_feature_id=COMPOUND_TACTIC_PREFIX_RECOVERY_FEATURE_ID,
            source_rejected_tactic="move=> xs; smt().",
            accepted_prefix_tactic="move=> x.",
            accepted_prefix_effect="accepted_changed",
            accepted_prefix_stage_count=1,
            derived_rejected_tactic="smt().",
            native_failure_kind="native_user_error",
            native_error_message="failed",
        )


def test_state_changing_prefix_hands_native_typed_suffix_to_p2() -> None:
    rejected_tactic = "move=> H; exact MissingFact."
    boundary = NativeAttemptedOperationDescriptor(
        operation_family="exact",
        rejected_tactic="exact MissingFact.",
        exact_resource="MissingFact",
        argument_kinds=(),
        side="",
        positions=(),
        native_diagnostic_status="blocker",
        native_failure_kind="lookup_failure",
        native_error_message="the first rejected extension failed",
        attempt_outcome="rejected",
        goal_kind="formula",
    )

    _invocation, bundle = _compile(
        rejected_tactic=rejected_tactic,
        accepted_effect="accepted_changed",
        boundary_attempt=boundary,
    )

    attempted = bundle.proof_ir.attempted_operation
    assert attempted is not None
    assert attempted.operation_family == "exact"
    assert attempted.rejected_tactic == boundary.rejected_tactic
    assert attempted.state_ref == bundle.state_ref
    assert attempted.recovery_handoff is not None
    assert attempted.recovery_handoff.accepted_prefix_tactic == "move=> H."
    assert attempted.recovery_handoff.accepted_prefix_effect == (
        "accepted_changed"
    )
    assert attempted.recovery_handoff.prefix_changes_state is True


def test_state_changing_eager_explanation_names_temporary_goal_and_ends_terminal() -> None:
    rejected_suffix = (
        "eager while (H : x <- 0; ~ x <- 0; : true ==> true)."
    )
    eager = NativeEagerWhileDialectDescriptor(
        source_operation="eager",
        eager_subform="while",
        attempted_shape="invariant",
        failure_kind="eager_while_guard_mismatch",
        candidates=(),
    )
    boundary = NativeAttemptedOperationDescriptor(
        operation_family="eager",
        rejected_tactic=rejected_suffix,
        exact_resource="",
        argument_kinds=("formula",),
        side="",
        positions=(),
        native_diagnostic_status="blocker",
        native_failure_kind="eager_while_guard_mismatch",
        native_error_message="the two guards are not equal",
        attempt_outcome="rejected",
        goal_kind="equiv_statement",
        realization=realization_of(eager),
    )

    _invocation, bundle = _compile(
        rejected_tactic="move=> H; " + rejected_suffix,
        accepted_effect="accepted_changed",
        boundary_attempt=boundary,
        features=(
            compound_tactic_prefix_recovery_feature(),
            tactic_dialect_repair_feature(),
        ),
    )

    diagnostic = bundle.candidate_surface.diagnostics[0].diagnostic
    assert "while guards in the temporary goal produced by that accepted stage" in (
        diagnostic.primary
    )
    assert "current while guards" not in diagnostic.primary
    # The compound boundary adds no continuation menu after the owner's help.
    assert diagnostic.terminal == ""
    markdown = _render_candidate_diagnostic(bundle)
    assert "does not choose between" not in markdown
    assert "submit it alone" not in markdown


def test_state_changing_pure_tail_action_names_temporary_goal() -> None:
    rejected_suffix = "rewrite FMap.get_setE."
    rewrite = NativePureTailRewriteDescriptor(
        source_operation="rewrite",
        selected_resource="FMap.get_setE",
        target_kind="hypothesis",
        target_name="Hupdate",
        candidate_tactic="rewrite FMap.get_setE in Hupdate.",
        failure_kind="rewrite_target_mismatch",
        accepted_target_count=1,
    )
    boundary = NativeAttemptedOperationDescriptor(
        operation_family="rewrite",
        rejected_tactic=rejected_suffix,
        exact_resource="FMap.get_setE",
        argument_kinds=("rewrite_lemma",),
        side="",
        positions=(),
        native_diagnostic_status="blocker",
        native_failure_kind="rewrite_target_mismatch",
        native_error_message="rewrite did not match the conclusion",
        attempt_outcome="rejected",
        goal_kind="formula",
        realization=realization_of(rewrite),
    )

    _invocation, bundle = _compile(
        rejected_tactic="move=> H; " + rejected_suffix,
        accepted_effect="accepted_changed",
        boundary_attempt=boundary,
        features=(
            compound_tactic_prefix_recovery_feature(),
            pure_tail_recovery_feature(),
        ),
    )

    action = bundle.candidate_surface.actions[0]
    assert action.payload.to_dict() == {
        "tactic": "move=> H; rewrite FMap.get_setE in Hupdate."
    }
    assert action.correction is not None
    assert action.correction.reason.count(
        "the temporary goal produced by that accepted stage"
    ) == 2
    assert "current conclusion" not in action.correction.reason


def test_state_changing_eager_action_names_temporary_goal() -> None:
    rejected_suffix = (
        "eager while (H : x <- 0; ~ x <- 0; : true ==> true)."
    )
    eager = NativeEagerWhileDialectDescriptor(
        source_operation="eager",
        eager_subform="while",
        attempted_shape="explicit_statement_contract",
        failure_kind="eager_while_dialect_mismatch",
        candidates=(NativeEagerWhileCandidateDescriptor(
            invariant_text="true",
            candidate_tactic="eager while (true).",
        ),),
    )
    boundary = NativeAttemptedOperationDescriptor(
        operation_family="eager",
        rejected_tactic=rejected_suffix,
        exact_resource="",
        argument_kinds=("eager_while_contract",),
        side="",
        positions=(),
        native_diagnostic_status="blocker",
        native_failure_kind="eager_while_dialect_mismatch",
        native_error_message="native parse error",
        attempt_outcome="rejected",
        goal_kind="equiv_statement",
        realization=realization_of(eager),
    )

    _invocation, bundle = _compile(
        rejected_tactic="move=> H; " + rejected_suffix,
        accepted_effect="accepted_changed",
        boundary_attempt=boundary,
        features=(
            compound_tactic_prefix_recovery_feature(),
            tactic_dialect_repair_feature(),
        ),
    )

    action = bundle.candidate_surface.actions[0]
    assert action.payload.to_dict() == {
        "tactic": "move=> H; eager while (true)."
    }
    assert action.correction is not None
    assert "invariant for the temporary goal produced by that accepted stage" in (
        action.correction.reason
    )
    assert "unchanged state" not in action.correction.reason


def test_state_changing_phl_boundary_is_explanation_without_undo() -> None:
    rejected_suffix = (
        "transitivity NativeStateCallee.bump "
        "(={arg} ==> ={res}) (={arg} ==> ={res})."
    )
    phl = NativePhlTransitivityBoundaryDescriptor(
        source_operation="transitivity",
        attempted_form="function",
        current_goal_form="statement",
        side="",
        failure_kind="phl_transitivity_boundary_mismatch",
    )
    boundary = NativeAttemptedOperationDescriptor(
        operation_family="transitivity",
        rejected_tactic=rejected_suffix,
        exact_resource="",
        argument_kinds=("phl_function",),
        side="",
        positions=(),
        native_diagnostic_status="blocker",
        native_failure_kind="phl_transitivity_boundary_mismatch",
        native_error_message="native rejected PHL transitivity boundary",
        attempt_outcome="rejected",
        goal_kind="equiv_statement",
        realization=realization_of(phl),
    )

    _invocation, bundle = _compile(
        rejected_tactic="proc; " + rejected_suffix,
        accepted_effect="accepted_changed",
        boundary_attempt=boundary,
        features=(
            compound_tactic_prefix_recovery_feature(),
            phl_transitivity_boundary_repair_feature(),
        ),
    )

    diagnostic = bundle.candidate_surface.diagnostics[0].diagnostic
    assert diagnostic.applicability == "explanation_only"
    assert "temporary goal produced by that accepted stage" in diagnostic.primary
    assert "undo" not in diagnostic.help.lower()
    assert "Both are proof-strategy choices" in diagnostic.help
    assert "The compiler selected neither" in diagnostic.help
    # The owner's help ends the panel; the boundary adds no continuation.
    assert diagnostic.terminal == ""
    markdown = _render_candidate_diagnostic(bundle)
    assert markdown.rstrip().endswith("The compiler selected neither.")


@pytest.mark.parametrize("consumer_layout", ("absent", "before", "after"))
def test_unhandled_typed_suffix_falls_back_to_compound_boundary_diagnostic(
    consumer_layout: str,
) -> None:
    boundary = NativeAttemptedOperationDescriptor(
        operation_family="exact",
        rejected_tactic="exact MissingFact.",
        exact_resource="MissingFact",
        argument_kinds=(),
        side="",
        positions=(),
        native_diagnostic_status="blocker",
        native_failure_kind="lookup_failure",
        native_error_message="unknown identifier MissingFact",
        attempt_outcome="rejected",
        goal_kind="formula",
    )
    compound = compound_tactic_prefix_recovery_feature()
    operation = operation_binding_repair_feature()
    features = {
        "absent": (compound,),
        "before": (operation, compound),
        "after": (compound, operation),
    }[consumer_layout]
    _invocation, bundle = _compile(
        rejected_tactic="move=> H; exact MissingFact.",
        accepted_effect="accepted_changed",
        boundary_attempt=boundary,
        features=features,
    )

    attempted = bundle.proof_ir.attempted_operation
    assert attempted is not None and attempted.recovery_handoff is not None
    assert attempted.recovery_handoff.source_feature_id == (
        COMPOUND_TACTIC_PREFIX_RECOVERY_FEATURE_ID
    )
    assert bundle.analyzed_state.recovery_ownership.owner_feature_id == (
        COMPOUND_TACTIC_PREFIX_RECOVERY_FEATURE_ID
    )
    assert len(bundle.candidate_surface.diagnostics) == 1
    diagnostic = bundle.candidate_surface.diagnostics[0].diagnostic
    assert diagnostic.code == "compound_prefix_diagnostic"
    # The fallback is the shared boundary account and nothing after it.
    assert diagnostic.primary == recovery_handoff_message(
        attempted.recovery_handoff
    )
    assert (
        "EasyCrypt can execute the first stage, which changes the goal:"
        "\n\n  move=> H."
    ) in diagnostic.primary
    assert "The next stage fails:\n\n  exact MissingFact." in (
        diagnostic.primary
    )


@pytest.mark.parametrize("consumer_first", (False, True))
def test_typed_suffix_argument_diagnostic_replaces_generic_fallback(
    consumer_first: bool,
) -> None:
    head = NativeApplicationHeadDescriptor(
        resolved_head=NativeResolvedHead("global", "Top.RO_FinRO_D"),
        input_mode="implicit",
        input_arguments=(
            NativeInputArgument(1, "formula", False, "G2", rejected=True),
            NativeInputArgument(2, "formula", False, "dout_ll"),
        ),
        slots=(
            NativeApplicationSlotDescriptor(
                position=1,
                kind="proof",
                formula=NativeFormulaDescriptor(
                    kind="quantifier",
                    text="forall x, is_lossless dblock",
                    type_text="bool",
                ),
            ),
            NativeApplicationSlotDescriptor(
                position=2,
                kind="module",
                name="D",
                type_text="FinRO_Distinguisher",
            ),
        ),
        result=NativeFormulaDescriptor(
            kind="formula",
            text="equiv[MainD(D, RO).distinguish ~ MainD(D, FinRO).distinguish]",
            type_text="bool",
        ),
    )
    boundary = NativeAttemptedOperationDescriptor(
        operation_family="conseq",
        rejected_tactic="conseq (RO_FinRO_D G2 dout_ll).",
        exact_resource="RO_FinRO_D",
        argument_kinds=("formula", "formula"),
        side="",
        positions=(),
        native_diagnostic_status="blocker",
        native_failure_kind="wrong_argument_kind",
        native_error_message="expecting a proof-term, not a formula",
        attempt_outcome="rejected",
        goal_kind="formula",
        application_head=head,
    )
    compound = compound_tactic_prefix_recovery_feature()
    operation = operation_binding_repair_feature()
    _invocation, bundle = _compile(
        rejected_tactic=(
            "symmetry; conseq (RO_FinRO_D G2 dout_ll)."
        ),
        accepted_effect="accepted_changed",
        boundary_attempt=boundary,
        features=(
            (operation, compound)
            if consumer_first else (compound, operation)
        ),
    )

    assert bundle.analyzed_state.recovery_ownership.owner_feature_id == (
        OPERATION_BINDING_REPAIR_FEATURE_ID
    )
    assert len(bundle.candidate_surface.diagnostics) == 1
    diagnostic = bundle.candidate_surface.diagnostics[0].diagnostic
    assert diagnostic.code == "selected_application_argument_layout"
    assert diagnostic.primary.startswith(
        "Your compound tactic failed and was rolled back; nothing was "
        "committed."
    )
    assert diagnostic.primary.count("symmetry.") == 1
    assert "1. a proof of `forall x, is_lossless dblock`" in (
        diagnostic.primary
    )
    assert "2. `dout_ll`" in diagnostic.primary
    assert "Argument 1 is a formula, but slot 1 requires a proof." in (
        diagnostic.primary
    )
    assert diagnostic.notes == ()
    assert "binding search" not in (
        diagnostic.primary + diagnostic.help + diagnostic.terminal
    ).lower()
    assert diagnostic.terminal == ""


def test_no_progress_failure_reaches_owned_diagnostic() -> None:
    _invocation, bundle = _compile(outcome_kind="no_progress")

    assert bundle.analyzed_state.recovery_ownership.owner_feature_id == (
        COMPOUND_TACTIC_PREFIX_RECOVERY_FEATURE_ID
    )
    assert len(bundle.candidate_surface.diagnostics) == 1
    assert not bundle.candidate_surface.actions


def test_same_boundary_diagnostic_is_once_per_material_recovery_scope() -> None:
    first_invocation, first_bundle = _compile(
        rejected_tactic="symmetry; apply A.",
        source_event_id="compound-prefix-failure-1",
        source_event_sequence=10,
    )
    second_invocation, second_bundle = _compile(
        rejected_tactic="symmetry; apply (A _).",
        source_event_id="compound-prefix-failure-2",
        source_event_sequence=11,
    )
    later_invocation, later_bundle = _compile(
        rejected_tactic="symmetry; idtac; apply A.",
        source_event_id="compound-prefix-failure-3",
        source_event_sequence=12,
    )
    first_candidate = first_bundle.candidate_surface.diagnostics[0]
    second_candidate = second_bundle.candidate_surface.diagnostics[0]
    later_candidate = later_bundle.candidate_surface.diagnostics[0]
    assert first_candidate.diagnostic.identity_payload() != (
        second_candidate.diagnostic.identity_payload()
    )
    assert first_candidate.recovery_lifetime_scope_id
    assert first_candidate.recovery_lifetime_scope_id == (
        second_candidate.recovery_lifetime_scope_id
    )
    assert later_candidate.recovery_lifetime_scope_id != (
        first_candidate.recovery_lifetime_scope_id
    )

    assembly = feature_assembly('compound_tactic_prefix_recovery', mode=TREATMENT)
    assert assembly is not None
    first = admit_action_surface(
        first_bundle.candidate_surface,
        (),
        assembly.manifest,
        triggers=first_invocation.triggers,
    )
    repeated = admit_action_surface(
        second_bundle.candidate_surface,
        (),
        assembly.manifest,
        triggers=second_invocation.triggers,
        previously_presented=frozenset(first.presented_delivery_ids),
    )
    advanced_boundary = admit_action_surface(
        later_bundle.candidate_surface,
        (),
        assembly.manifest,
        triggers=later_invocation.triggers,
        previously_presented=frozenset(first.presented_delivery_ids),
    )
    assert len(first.action_surface.diagnostics) == 1
    assert repeated.action_surface.empty
    assert repeated.decisions[0].reason == "delivery_lifetime_suppressed"
    assert len(advanced_boundary.action_surface.diagnostics) == 1


def test_no_accepted_prefix_leaves_recovery_unclaimed() -> None:
    _invocation, bundle = _compile(accepted_prefixes=())
    assert bundle.analyzed_state.recovery_ownership.status == "unclaimed"
    assert bundle.candidate_surface.empty


def test_noncontiguous_native_acceptance_leaves_recovery_unclaimed() -> None:
    _invocation, bundle = _compile(accepted_prefixes=(PREFIXES[-1],))

    assert bundle.analyzed_state.recovery_ownership.status == "unclaimed"
    assert bundle.candidate_surface.empty


def test_descriptor_rejects_noncanonical_accepted_prefix_order() -> None:
    with pytest.raises(ValueError, match="descriptor is invalid"):
        NativeTacticPrefixDiagnosticDescriptor(
            rejected_tactic=REJECTED_TACTIC,
            candidate_prefixes=PREFIXES,
            prefix_effects=("accepted_changed", "accepted_changed"),
            accepted_prefixes=tuple(reversed(PREFIXES)),
            boundary_tactic="smt(sum_le_bound mu_bounded).",
            native_failure_kind="native_user_error",
            native_error_message="failure",
            boundary_failure_kind="native_user_error",
            boundary_error_message="boundary failure",
            goal_kind="formula",
        )


# --- one sentence, EasyCrypt boundaries, EasyCrypt's own error -------------


@pytest.mark.parametrize(
    "tactic",
    (
        "proc; sp; if => //.\ninline A B.\nwp.",
        "move: H18; rewrite mem_set /=. case=> [[-> _] // | Hmem].",
        "move=> x; smt(). done.",
        "wp; sp.\tauto.",
    ),
)
def test_multi_sentence_commit_has_no_prefix_population(tactic: str) -> None:
    """The manager runs a multi-sentence commit sentence by sentence; the
    native check parses one global action, so no cut across sentences."""

    assert compound_prefix_candidates(tactic) == ()
    gate = compound_tactic_prefix_recovery_feature().execution_gate
    eligibility = gate.evaluate(_turn(_state_ref(), tactic))
    assert eligibility.eligible is False


@pytest.mark.parametrize(
    ("tactic", "prefixes"),
    (
        ("move=> x\n; smt().", ("move=> x.",)),
        ("rewrite p{2}.`1 M.f; smt().", ("rewrite p{2}.`1 M.f.",)),
        ("rewrite m.[x] get_setE; smt().", ("rewrite m.[x] get_setE.",)),
        ("swap{1} [1..2] 3; wp.", ("swap{1} [1..2] 3.",)),
        ("have := H x.`2; smt().", ("have := H x.`2.",)),
    ),
)
def test_dots_inside_one_sentence_keep_the_population(
    tactic: str, prefixes: tuple[str, ...]
) -> None:
    assert compound_prefix_candidates(tactic) == prefixes


def test_easycrypt_boundaries_narrow_cuts_inside_a_greedy_by() -> None:
    """``by`` takes every later ``;``: only ``split.`` is a real prefix."""

    tactic = "split; first by move=> t Ht; exact: poly_out_sub_add."
    assert compound_prefix_candidates(tactic) == (
        "split.", "split; first by move=> t Ht.",
    )
    _invocation, bundle = _compile(
        rejected_tactic=tactic,
        native_candidates=("split.",),
    )

    assert len(bundle.candidate_surface.diagnostics) == 1
    primary = bundle.candidate_surface.diagnostics[0].diagnostic.primary
    assert "EasyCrypt can execute the first stage" in primary
    assert (
        "The next stage fails:\n\n"
        "  first by move=> t Ht; exact: poly_out_sub_add.\n\n"
    ) in primary
    assert "  " + BOUNDARY_ERROR in primary


def test_native_candidates_must_lead_the_lexical_population() -> None:
    _invocation, bundle = _compile(
        native_candidates=(PREFIXES[1],),
    )

    assert not bundle.candidate_surface.diagnostics
    assert not bundle.analyzed_state.recovery_ownership.owner_feature_id


@pytest.mark.parametrize(
    "manager_error",
    (
        "[error] cannot find lemma `H4'",
        "[error] " + BOUNDARY_ERROR + " later",
        "",
        "[error] daemon rejection",
    ),
)
def test_boundary_error_must_be_easycrypt_report(manager_error: str) -> None:
    """A boundary whose error EasyCrypt did not report forms no compound IR."""

    _invocation, bundle = _compile(manager_error=manager_error)

    assert bundle.proof_ir.attempted_operation is None
    assert not bundle.candidate_surface.diagnostics
    assert not bundle.analyzed_state.recovery_ownership.owner_feature_id


def test_typed_handoff_also_requires_easycrypt_report() -> None:
    boundary = NativeAttemptedOperationDescriptor(
        operation_family="transitivity",
        rejected_tactic="transitivity y.",
        exact_resource="",
        argument_kinds=("formula",),
        side="",
        positions=(),
        native_diagnostic_status="blocker",
        native_failure_kind="native_user_error",
        native_error_message=BOUNDARY_ERROR,
        attempt_outcome="rejected",
        goal_kind="formula",
    )

    _invocation, bundle = _compile(
        rejected_tactic="wp; transitivity y.",
        accepted_effect="accepted_no_progress",
        boundary_attempt=boundary,
        manager_error="[error] some other failure",
    )

    assert bundle.proof_ir.attempted_operation is None


@pytest.mark.parametrize(
    "manager_error",
    (
        BOUNDARY_ERROR,
        "[error] " + BOUNDARY_ERROR,
        "[error-12-40] " + BOUNDARY_ERROR,
        "[critical] the first rejected\n  extension   failed",
        "[error] [Target.ec: line 3 (4-9)] " + BOUNDARY_ERROR,
    ),
)
def test_report_comparison_ignores_header_and_line_breaking(
    manager_error: str,
) -> None:
    _invocation, bundle = _compile(manager_error=manager_error)

    assert len(bundle.candidate_surface.diagnostics) == 1


def test_bracketed_easycrypt_message_matches_without_severity() -> None:
    assert manager_reports_same_error(
        "[by]: cannot close goals", "[by]: cannot close goals"
    )
    assert not manager_reports_same_error(
        "[by]: cannot close goals", "[error] cannot prove goal (strict)"
    )


def test_manager_text_at_its_limit_compares_as_prefix() -> None:
    native = "cannot unify " + "x" * 1400
    manager = ("[error] " + native)[:MANAGER_ERROR_TEXT_LIMIT]

    assert manager_reports_same_error(native, manager)
    assert not manager_reports_same_error(native, manager[:-200])
    assert not manager_reports_same_error(
        "cannot unify " + "y" * 1400, manager
    )


def test_native_contract_error_is_never_an_easycrypt_rejection() -> None:
    _invocation, bundle = _compile(
        native_boundary_failure_kind="contract_error",
    )

    assert bundle.proof_ir.attempted_operation is None
    assert not bundle.candidate_surface.diagnostics


@pytest.mark.parametrize(
    ("prefix", "effect", "expected"),
    (
        (
            "move=> H.",
            "accepted_changed",
            "move=> H; rewrite FMap.get_setE in Hupdate; done.",
        ),
        # A no-op prefix stays out of the action; the later stage does not.
        (
            "idtac.",
            "accepted_no_progress",
            "rewrite FMap.get_setE in Hupdate; done.",
        ),
        # The agent's line break in the prefix is kept.
        (
            "move=>\n  H.",
            "accepted_changed",
            "move=>\n  H; rewrite FMap.get_setE in Hupdate; done.",
        ),
    ),
)
def test_repair_keeps_the_stages_after_the_failing_one(
    prefix: str, effect: str, expected: str,
) -> None:
    """A repair replaces the failing stage only; it never drops ``; done``."""

    rejected_suffix = "rewrite FMap.get_setE."
    rewrite = NativePureTailRewriteDescriptor(
        source_operation="rewrite",
        selected_resource="FMap.get_setE",
        target_kind="hypothesis",
        target_name="Hupdate",
        candidate_tactic="rewrite FMap.get_setE in Hupdate.",
        failure_kind="rewrite_target_mismatch",
        accepted_target_count=1,
    )
    boundary = NativeAttemptedOperationDescriptor(
        operation_family="rewrite",
        rejected_tactic=rejected_suffix,
        exact_resource="FMap.get_setE",
        argument_kinds=("rewrite_lemma",),
        side="",
        positions=(),
        native_diagnostic_status="blocker",
        native_failure_kind="rewrite_target_mismatch",
        native_error_message="rewrite did not match the conclusion",
        attempt_outcome="rejected",
        goal_kind="formula",
        realization=realization_of(rewrite),
    )

    _invocation, bundle = _compile(
        rejected_tactic=prefix[:-1] + "; " + rejected_suffix[:-1] + "; done.",
        accepted_prefixes=(prefix,),
        accepted_effect=effect,
        boundary_attempt=boundary,
        features=(
            compound_tactic_prefix_recovery_feature(),
            pure_tail_recovery_feature(),
        ),
    )

    assert bundle.proof_ir.attempted_operation.recovery_handoff.later_stages == (
        "done"
    )
    action = bundle.candidate_surface.actions[0]
    assert action.payload.to_dict() == {"tactic": expected}


def test_unparsable_compound_says_nothing_ran() -> None:
    """A parse error runs nothing: the prefix ran only on its own, and the
    rest is the text that does not parse, not one failing stage."""

    summary = compound_boundary_summary(
        accepted_prefix="move=> x Hx.",
        accepted_effect="accepted_changed",
        accepted_stage_count=1,
        rejected_extension="spli t; smt().",
        native_error="parse error",
        parse_error=True,
    )

    assert summary.startswith(
        "Your compound tactic does not parse, so EasyCrypt ran none of it"
    )
    assert "On its own, EasyCrypt can execute the first stage" in summary
    assert "The rest does not parse:\n\n  spli t; smt()." in summary
    assert "The next stage fails" not in summary
    assert "rolled back" not in summary


# --- the rejected sentence of a multi-sentence commit -----------------------


def _failing_sentence_turn(state_ref, commit: str, index: int, sentence: str):
    from dataclasses import replace

    from core.easycrypt.ec_diagnostics import FailedSentence

    return replace(
        _turn(state_ref, commit),
        failed_sentence=FailedSentence(index=index, count=2, sentence=sentence),
    )


def test_failing_sentence_is_diagnosed_after_the_sentences_before_it() -> None:
    commit = "move=> x _.\nmove=> &hr _; rewrite /eps; smt(sum_le_bound mu_bounded)."
    sentence = REJECTED_TACTIC
    state_ref = _state_ref()
    snapshot = _snapshot(state_ref)
    invocation = compiler_invocation_context(
        state_ref, _failing_sentence_turn(state_ref, commit, 2, sentence),
    )
    compiler = ProofStateCompiler(features=(compound_tactic_prefix_recovery_feature(),))
    environment = CompilationEnvironment("compound-prefix-environment", (), ())

    plan = compiler.plan_native_semantics(snapshot, environment, invocation)

    # The native query names sentence 2 and runs after sentence 1.
    assert len(plan.requests) == 1
    request = plan.requests[0]
    assert request.query.rejected_tactic == sentence
    assert request.query.candidate_prefixes == PREFIXES
    assert request.evaluation_prefix == ("move=> x _.",)

    descriptor = NativeTacticPrefixDiagnosticDescriptor(
        rejected_tactic=sentence,
        candidate_prefixes=PREFIXES,
        prefix_effects=("accepted_changed", "accepted_changed"),
        accepted_prefixes=PREFIXES,
        boundary_tactic="smt(sum_le_bound mu_bounded).",
        native_failure_kind="native_user_error",
        native_error_message=BOUNDARY_ERROR,
        boundary_failure_kind="native_user_error",
        boundary_error_message=BOUNDARY_ERROR,
        goal_kind="formula",
    )
    observation = NativeSemanticObservation.accepted(
        request=request,
        batch_id="compound-sentence-batch",
        batch_index=0,
        batch_size=1,
        batch_elapsed_ms=2,
        result_formula="",
        descriptor=descriptor,
        runtime_identity_sha256="d" * 64,
        companion_identity_sha256="e" * 64,
        elapsed_ms=2,
        provenance=ProvenanceRef(
            producer="test.native_prefix",
            authority="native.semantic.batch.produced",
            source_sha256="f" * 64,
            artifact_ref="native_semantic_batches/compound-sentence.json",
            source_event_id="native-semantic-compound-sentence",
            source_event_sequence=11,
            authoritative=True,
        ),
    )
    environment = environment.with_native_semantic_observations((observation,))
    bundle = compiler.compile(snapshot, environment, invocation)

    assert bundle.proof_ir.attempted_operation.rejected_tactic == sentence
    assert bundle.proof_ir.attempted_operation.recovery_handoff is None
    primary = bundle.candidate_surface.diagnostics[0].diagnostic.primary
    assert primary.startswith(
        "Sentence 2 of your 2-sentence commit failed and the commit was "
        "rolled back; nothing was committed.\n\n"
        "In sentence 2, after the sentence before it, EasyCrypt can execute "
        "the first 2 stages"
    )


def test_a_failing_sentence_that_the_split_does_not_reproduce_abstains() -> None:
    state_ref = _state_ref()
    invocation = compiler_invocation_context(
        state_ref,
        _failing_sentence_turn(
            state_ref, "move=> x _.\nmove=> &hr _; smt().", 2, "smt().",
        ),
    )
    compiler = ProofStateCompiler(features=(compound_tactic_prefix_recovery_feature(),))
    environment = CompilationEnvironment("compound-prefix-environment", (), ())

    plan = compiler.plan_native_semantics(
        _snapshot(state_ref), environment, invocation,
    )

    assert plan.requests == ()


def test_only_an_opted_in_feature_runs_on_a_failing_sentence() -> None:
    state_ref = _state_ref()
    turn = _failing_sentence_turn(
        state_ref,
        "move=> x _.\nmove=> &hr _; rewrite /eps; smt(sum_le_bound mu_bounded).",
        2,
        REJECTED_TACTIC,
    )

    compound = compound_tactic_prefix_recovery_feature().execution_gate
    other = pure_tail_recovery_feature().execution_gate
    assert compound.evaluate(turn).eligible is True
    assert other.evaluate(turn).reason == "failing_sentence_not_accepted"
