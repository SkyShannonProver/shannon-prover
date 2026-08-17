"""Contracts for native PHL transitivity form/boundary recovery."""

from __future__ import annotations

import pytest

from core.easycrypt.proof_state_compiler import (
    AuthoritativeSnapshotInput,
    CompilationEnvironment,
    ProofStateCompiler,
    ProvenanceRef,
    StateRef,
)
from core.easycrypt.proof_state_compiler.backend import admit_action_surface
from core.easycrypt.proof_state_compiler.contracts import (
    CompilerTurnEvidence,
    NativePhlTransitivityBoundaryDescriptor,
    TargetRef,
    TransitionRef,
    compiler_invocation_context,
    freeze_json_object,
)
from core.easycrypt.proof_state_compiler.features.phl_transitivity_boundary_repair import (
    PHL_TRANSITIVITY_BOUNDARY_REPAIR_FEATURE_ID,
    phl_transitivity_boundary_repair_feature,
)
from core.easycrypt.proof_state_compiler.features.relation_bridge_realization import (
    RELATION_BRIDGE_REALIZATION_FEATURE_ID,
    relation_bridge_realization_feature,
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
    PHL_TRANSITIVITY_BOUNDARY_AUDIT_PROFILE,
    PHL_TRANSITIVITY_BOUNDARY_TREATMENT_PROFILE,
)


FUNCTION_TACTIC = (
    "transitivity NativeStateCallee.bump "
    "(={arg} ==> ={res}) (={arg} ==> ={res})."
)
STATEMENT_TACTIC = (
    "transitivity{1} { y <@ NativeStateCallee.bump(x); } "
    "(={arg} ==> ={res}) (={arg} ==> ={res})."
)


def _state_ref(goal_form: str) -> StateRef:
    return StateRef(
        session_id="phl-boundary-test",
        state_version=4,
        goal_identity=f"equiv-{goal_form}",
        goal_identity_required=True,
        committed_prefix_identity="a" * 64,
    )


def _snapshot(state_ref: StateRef, goal_form: str) -> AuthoritativeSnapshotInput:
    formula = typed_node(
        f"equivalence_{goal_form}",
        "equiv[...]" if goal_form == "statement" else "equiv[F]",
    )
    return AuthoritativeSnapshotInput(
        state_ref=state_ref,
        provenance=ProvenanceRef(
            producer="phl-boundary.fixture",
            authority="compiler.input.produced",
            source_sha256="b" * 64,
            artifact_ref="compiler_inputs/phl-boundary.json",
            source_event_id="compiler-input-phl-boundary",
            source_event_sequence=4,
            authoritative=True,
        ),
        target=TargetRef("eval/phl_boundary.ec", "boundary"),
        transition=TransitionRef(
            "rejected", state_ref, "compiler_inputs/phl-boundary.json"
        ),
        goal_lines=("Current goal", "--------", formula["text"]),
        goal_count=1,
        goal_count_known=True,
        closed=False,
        native_state=native_state(state_ref, formula=formula),
    )


def _turn(state_ref: StateRef, tactic: str) -> CompilerTurnEvidence:
    return CompilerTurnEvidence(
        source_event_id="phl-boundary-failure",
        source_event_sequence=8,
        authority_kind="event_bound_tactic_execution_result",
        artifact_ref="tactic_execution_results/phl-boundary-failure.json",
        artifact_hash="c" * 64,
        hash_algorithm="sha256",
        post_state_ref=state_ref,
        intent="commit_tactic",
        payload=freeze_json_object({"tactic": tactic}),
        outcome_kind="rejected",
        proof_state_effect="unchanged",
        structured_error="native rejected PHL transitivity boundary",
    )


def _compile(attempted_form: str):
    current_form = "statement" if attempted_form == "function" else "function"
    tactic = FUNCTION_TACTIC if attempted_form == "function" else STATEMENT_TACTIC
    side = "" if attempted_form == "function" else "left"
    state_ref = _state_ref(current_form)
    snapshot = _snapshot(state_ref, current_form)
    invocation = compiler_invocation_context(state_ref, _turn(state_ref, tactic))
    compiler = ProofStateCompiler(
        features=(phl_transitivity_boundary_repair_feature(),)
    )
    environment = CompilationEnvironment("phl-boundary-environment", (), ())
    plan = compiler.plan_native_semantics(snapshot, environment, invocation)
    assert len(plan.requests) == 1
    boundary = NativePhlTransitivityBoundaryDescriptor(
        source_operation="transitivity",
        attempted_form=attempted_form,
        current_goal_form=current_form,
        side=side,
        failure_kind="phl_transitivity_boundary_mismatch",
    )
    observation = attempted_operation_native_observation(
        plan.requests[0],
        failure_kind="phl_transitivity_boundary_mismatch",
        goal_kind=f"equiv_{current_form}",
        argument_kinds=(f"phl_{attempted_form}",),
        side=side,
        phl_transitivity_boundary=boundary,
    )
    environment = environment.with_native_semantic_observations((observation,))
    return invocation, compiler.compile(snapshot, environment, invocation)


@pytest.mark.parametrize("attempted_form", ("function", "statement"))
def test_phl_boundary_is_one_owned_explanation(attempted_form: str) -> None:
    _invocation, bundle = _compile(attempted_form)

    ownership = bundle.analyzed_state.recovery_ownership
    assert ownership.owner_feature_id == (
        PHL_TRANSITIVITY_BOUNDARY_REPAIR_FEATURE_ID
    )
    assert ownership.allowed_output_kinds == ("diagnostic",)
    assert bundle.candidate_surface.actions == ()
    assert len(bundle.candidate_surface.diagnostics) == 1
    diagnostic = bundle.candidate_surface.diagnostics[0].diagnostic
    assert diagnostic.applicability == "explanation_only"
    assert diagnostic.code == "phl_boundary"
    if attempted_form == "function":
        assert "requires `equiv[F]`" in diagnostic.primary
        assert "`transitivity{1}" in diagnostic.help
        assert diagnostic.help.startswith("Function-level transitivity")
        assert "Side and statement remain proof-strategy choices" in (
            diagnostic.help
        )
        assert "selected no correction" in diagnostic.help
    else:
        assert "requires `equiv[statement]`" in diagnostic.primary
        assert "after entering a procedure body" in diagnostic.help
        assert diagnostic.help.startswith("Statement-level transitivity")
        assert "intermediate function remains a proof-strategy choice" in (
            diagnostic.help
        )
        assert "selected no correction" in diagnostic.help


def test_phl_boundary_audit_is_hidden_and_treatment_is_visible() -> None:
    invocation, bundle = _compile("function")
    treatment = compiler_assembly_for_profile(
        PHL_TRANSITIVITY_BOUNDARY_TREATMENT_PROFILE
    )
    audit = compiler_assembly_for_profile(
        PHL_TRANSITIVITY_BOUNDARY_AUDIT_PROFILE
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


def test_phl_boundary_descriptor_rejects_same_form() -> None:
    with pytest.raises(ValueError, match="boundary"):
        NativePhlTransitivityBoundaryDescriptor(
            source_operation="transitivity",
            attempted_form="function",
            current_goal_form="function",
            side="",
            failure_kind="phl_transitivity_boundary_mismatch",
        )


def test_relation_and_phl_overlap_coalesces_once_and_only_phl_owns() -> None:
    state_ref = _state_ref("statement")
    snapshot = _snapshot(state_ref, "statement")
    invocation = compiler_invocation_context(
        state_ref,
        _turn(state_ref, FUNCTION_TACTIC),
    )
    compiler = ProofStateCompiler(
        features=(
            relation_bridge_realization_feature(),
            phl_transitivity_boundary_repair_feature(),
        )
    )
    environment = CompilationEnvironment("overlap-environment", (), ())

    plan = compiler.plan_native_semantics(snapshot, environment, invocation)

    assert len(plan.requests) == 2
    assert len(plan.execution_units) == 1
    assert len(plan.execution_units[0].requests) == 2
    assert {item.producer_id for item in plan.requests} == {
        "relation_bridge_realization.attempt.native_diagnostic",
        "phl_transitivity_boundary_repair.attempt.native_diagnostic",
    }
    boundary = NativePhlTransitivityBoundaryDescriptor(
        source_operation="transitivity",
        attempted_form="function",
        current_goal_form="statement",
        side="",
        failure_kind="phl_transitivity_boundary_mismatch",
    )
    observations = tuple(
        attempted_operation_native_observation(
            request,
            failure_kind="phl_transitivity_boundary_mismatch",
            goal_kind="equiv_statement",
            argument_kinds=("phl_function",),
            phl_transitivity_boundary=boundary,
        )
        for request in plan.requests
    )
    bundle = compiler.compile(
        snapshot,
        environment.with_native_semantic_observations(observations),
        invocation,
    )

    assert len(bundle.proof_ir.native_semantic_observations) == 2
    assert bundle.proof_ir.attempted_operation is not None
    assert bundle.proof_ir.attempted_operation.relation_bridge_descriptor is None
    assert (
        bundle.proof_ir.attempted_operation.phl_transitivity_boundary_descriptor
        == boundary
    )
    ownership = bundle.analyzed_state.recovery_ownership
    assert ownership.owner_feature_id == PHL_TRANSITIVITY_BOUNDARY_REPAIR_FEATURE_ID
    assert ownership.owner_feature_id != RELATION_BRIDGE_REALIZATION_FEATURE_ID
    assert len(bundle.candidate_surface.diagnostics) == 1
    assert bundle.candidate_surface.actions == ()
