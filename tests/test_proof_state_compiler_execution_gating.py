"""Trigger-first scheduling remains feature-owned and pre-P1."""

from __future__ import annotations

from core.easycrypt.proof_state_compiler.compiler import ProofStateCompiler
from core.easycrypt.proof_state_compiler.contracts import (
    CompilerTurnEvidence,
    StateRef,
    freeze_json_object,
)
from core.easycrypt.proof_state_compiler.features.operation_binding_repair import (
    OPERATION_BINDING_REPAIR_FEATURE_ID,
    operation_binding_repair_feature,
)
from core.easycrypt.proof_state_compiler.features.compound_tactic_prefix_recovery import (
    compound_tactic_prefix_recovery_feature,
)
from core.easycrypt.proof_state_compiler.features.intro_pattern_repair import (
    intro_pattern_repair_feature,
)
from core.easycrypt.proof_state_compiler.features.phl_transitivity_boundary_repair import (
    phl_transitivity_boundary_repair_feature,
)
from core.easycrypt.proof_state_compiler.features.pure_tail_recovery import (
    pure_tail_recovery_feature,
)
from core.easycrypt.proof_state_compiler.features.relation_bridge_realization import (
    relation_bridge_realization_feature,
)
from core.easycrypt.proof_state_compiler.features.tactic_dialect_repair import (
    tactic_dialect_repair_feature,
)
from core.easycrypt.proof_state_compiler.features.program_operation_readiness import (
    PROGRAM_OPERATION_READINESS_FEATURE_ID,
    program_operation_readiness_feature,
)
from workflow.proof_state_compiler.configuration import (
    compiler_assembly_for_profile,
)
from workflow.proof_state_compiler.profile_ids import (
    OPERATION_BINDING_REPAIR_AUDIT_PROFILE,
    OPERATION_BINDING_REPAIR_TREATMENT_PROFILE,
)
from workflow.proof_state_compiler.service import (
    CompilerServiceSkipped,
    ProofStateCompilerService,
)
from workflow.proof_state_compiler.execution_lifetime import (
    FeatureExecutionLifetimeLedger,
)


class _NoCompilerRuntime:
    """Record any access that should be unreachable after a negative gate."""

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.state_version = 4

    def committed_history(self):
        self.calls.append("committed_history")
        return []

    def read_compiler_input_v2(self, **kwargs):
        self.calls.append("read_compiler_input_v2")
        raise AssertionError("negative execution gate reached compiler input")

    def project_native_state(self, **kwargs):
        self.calls.append("project_native_state")
        raise AssertionError("negative execution gate reached native projection")

    def execute_native_semantic_batch(self, **kwargs):
        self.calls.append("execute_native_semantic_batch")
        raise AssertionError("negative execution gate reached native semantics")

    def certify_exact_tactic(self, tactic: str, **kwargs):
        self.calls.append("certify_exact_tactic")
        raise AssertionError("negative execution gate reached certification")


def _state_ref() -> StateRef:
    return StateRef(
        session_id="execution-gate-session",
        state_version=4,
        goal_identity="execution-gate-goal",
        goal_identity_required=True,
        committed_prefix_identity="a" * 64,
    )


def _turn(
    *,
    outcome: str,
    tactic: str,
    error: str = "",
) -> CompilerTurnEvidence:
    return CompilerTurnEvidence(
        source_event_id=f"turn-{outcome}",
        source_event_sequence=7,
        authority_kind="event_bound_tactic_execution_result",
        artifact_ref=f"tactic_execution_results/{outcome}.json",
        artifact_hash="b" * 64,
        hash_algorithm="sha256",
        post_state_ref=_state_ref(),
        intent="commit_tactic",
        payload=freeze_json_object({"tactic": tactic}),
        outcome_kind=outcome,
        proof_state_effect="changed" if outcome == "accepted" else "unchanged",
        structured_error=error,
    )


def _operation_service(runtime: _NoCompilerRuntime):
    assembly = compiler_assembly_for_profile(
        OPERATION_BINDING_REPAIR_TREATMENT_PROFILE
    )
    assert assembly is not None
    return ProofStateCompilerService.create(runtime=runtime, assembly=assembly)


def test_operation_repair_skips_initial_and_success_pre_p1() -> None:
    cases = (
        None,
        _turn(outcome="accepted", tactic="smt()."),
    )
    expected_reasons = (
        "no_completed_turn",
        "turn_did_not_fail",
    )

    for turn_evidence, expected_reason in zip(cases, expected_reasons):
        runtime = _NoCompilerRuntime()
        result = _operation_service(runtime).compile_current_state(turn_evidence)

        assert isinstance(result, CompilerServiceSkipped)
        assert runtime.calls == []
        assert result.execution_plan.eligible_feature_ids == ()
        assert result.execution_plan.decisions[0].reason == expected_reason
        assert result.telemetry["timings_ms"]["input_initial"] == 0
        assert result.telemetry["timings_ms"]["manager_state_snapshot"] == 0
        assert result.telemetry["timings_ms"]["compiler_input_transport"] == 0
        assert result.telemetry["timings_ms"]["native_state_projection"] == 0
        assert result.telemetry["timings_ms"]["native_state_lowering"] == 0
        assert result.telemetry["timings_ms"]["resource_loading"] == 0
        assert result.telemetry["timings_ms"]["certification"] == 0


def test_operation_repair_defers_semantic_failure_ownership_to_native() -> None:
    evidence = _turn(
        outcome="rejected",
        tactic="apply Wrong.fact.",
        error="timeout while checking tactic",
    )

    plan = ProofStateCompiler(features=(
        operation_binding_repair_feature(),
    )).plan_execution(evidence)

    assert plan.eligible_feature_ids == (OPERATION_BINDING_REPAIR_FEATURE_ID,)
    assert plan.decisions[0].reason == "candidate_binding_operation_failure"


def test_owned_failure_enables_same_feature_in_audit_and_treatment() -> None:
    evidence = _turn(
        outcome="rejected",
        tactic="exact Wrong.dword_ll.",
        error="unknown identifier Wrong.dword_ll",
    )
    plans = []
    for profile_id in (
        OPERATION_BINDING_REPAIR_AUDIT_PROFILE,
        OPERATION_BINDING_REPAIR_TREATMENT_PROFILE,
    ):
        assembly = compiler_assembly_for_profile(profile_id)
        assert assembly is not None
        plans.append(assembly.compiler.plan_execution(evidence))

    assert plans[0] == plans[1]
    assert plans[0].eligible_feature_ids == (
        OPERATION_BINDING_REPAIR_FEATURE_ID,
    )
    assert plans[0].decisions[0].trigger_kind == "current_state_failure"


def test_completed_failure_occurrence_is_suppressed_before_p1() -> None:
    evidence = _turn(
        outcome="rejected",
        tactic="exact Wrong.dword_ll.",
        error="unknown identifier Wrong.dword_ll",
    )
    compiler = ProofStateCompiler(features=(operation_binding_repair_feature(),))
    first = compiler.plan_execution(evidence)
    ledger = FeatureExecutionLifetimeLedger()

    ledger.record_completed(first, evidence)
    repeated = ledger.suppress_completed(
        compiler.plan_execution(evidence),
        evidence,
    )

    assert repeated.eligible_feature_ids == ()
    assert repeated.decisions[0].reason == "turn_occurrence_already_compiled"
    assert ledger.size == 1


def test_combined_compiler_runs_only_each_feature_whose_gate_is_eligible() -> None:
    compiler = ProofStateCompiler(features=(
        operation_binding_repair_feature(),
        program_operation_readiness_feature(),
    ))
    accepted = _turn(outcome="accepted", tactic="smt().")
    plan = compiler.plan_execution(accepted)
    selected = compiler.select_execution_plan(plan)

    assert plan.configured_feature_ids == (
        OPERATION_BINDING_REPAIR_FEATURE_ID,
        PROGRAM_OPERATION_READINESS_FEATURE_ID,
    )
    assert plan.eligible_feature_ids == (PROGRAM_OPERATION_READINESS_FEATURE_ID,)
    assert tuple(item.spec.feature_id for item in selected.features) == (
        PROGRAM_OPERATION_READINESS_FEATURE_ID,
    )


def test_compound_failure_schedules_registered_recovery_consumers_generically() -> None:
    features = (
        compound_tactic_prefix_recovery_feature(),
        intro_pattern_repair_feature(),
        operation_binding_repair_feature(),
        phl_transitivity_boundary_repair_feature(),
        pure_tail_recovery_feature(),
        relation_bridge_realization_feature(),
        tactic_dialect_repair_feature(),
    )
    compiler = ProofStateCompiler(features=features)

    plan = compiler.plan_execution(_turn(
        outcome="rejected",
        tactic="wp; transitivity y.",
    ))

    assert plan.eligible_feature_ids == tuple(
        item.spec.feature_id for item in features
    )
    assert plan.decisions[0].reason == "candidate_compound_tactic_failure"
    assert {
        item.reason for item in plan.decisions[1:]
    } == {"candidate_typed_suffix_recovery_handoff"}
    assert features[0].execution_gate.produces_recovery_handoff is True
    assert all(
        item.execution_gate.accepts_recovery_handoff
        for item in features[1:]
    )
