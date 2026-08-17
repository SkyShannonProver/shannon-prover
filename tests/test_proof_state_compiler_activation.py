"""All-stage activation and removable-feature composition contracts."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from core.easycrypt.proof_state_compiler.backend import SurfaceContribution
from core.easycrypt.proof_state_compiler.contracts import (
    BASE_POLICY_REJECTION_REASONS,
    CHANGED_FACT,
    INTRINSIC,
    ONCE_PER_CONTENT,
    STATE_REFRESH,
    CompilationEnvironment,
    DeliveryPolicyCatalog,
    DeliveryPolicyDefinition,
    DeliveryRule,
    DiagnosticCandidate,
    EvidenceRef,
    EXPLANATION_ONLY,
    ProvenanceRef,
    StateRef,
    StrategyContract,
    StructuredDiagnostic,
    TargetRef,
    TransitionRef,
    compiler_invocation_context,
)
from core.easycrypt.proof_state_compiler.features import (
    ExperimentGate,
    FeatureCatalog,
    FeatureDefinition,
    FeatureSpec,
)
from core.easycrypt.proof_state_compiler.frontend import AuthoritativeSnapshotInput
from core.easycrypt.proof_state_compiler.middle_end import AnalysisContribution
from workflow.proof_state_compiler.activation import (
    AUDIT,
    OFF,
    TREATMENT,
    CompilerProfile,
    FeatureActivation,
    build_activation_plan,
)
from workflow.proof_state_compiler.assembly import (
    CompilerAssembly,
    assemble_compiler_profile,
)
from workflow.proof_state_compiler.configuration import (
    COMPILER_PROFILES,
    compiler_assembly_for_profile,
)
from workflow.proof_state_compiler.profile_ids import (
    M04_AUDIT_PROFILE,
    M09_AUDIT_PROFILE,
    OPERATION_BINDING_REPAIR_AUDIT_PROFILE,
    OPERATION_BINDING_REPAIR_TREATMENT_PROFILE,
)
from tests.proof_state_compiler_test_support import native_state
from workflow.proof_state_compiler.delivery_policies import (
    COMPOUND_TACTIC_PREFIX_RECOVERY_ONCE_POLICY_ID,
    INTRO_PATTERN_REPAIR_ONCE_POLICY_ID,
    OPERATION_BINDING_REPAIR_ONCE_POLICY_ID,
    PHL_TRANSITIVITY_BOUNDARY_ONCE_POLICY_ID,
    PURE_TAIL_RECOVERY_ONCE_POLICY_ID,
    RELATION_BRIDGE_ONCE_POLICY_ID,
    TACTIC_DIALECT_REPAIR_ONCE_POLICY_ID,
    default_delivery_policy_catalog,
)


ROOT = Path(__file__).resolve().parents[1]


def _strategy() -> StrategyContract:
    return StrategyContract(
        strategy_class=INTRINSIC,
        rationale="synthetic current-state fact",
    )


def _delivery_rule() -> DeliveryRule:
    return DeliveryRule(
        strategy_class=INTRINSIC,
        trigger_kind=STATE_REFRESH,
        presentation_kind=CHANGED_FACT,
        lifetime=ONCE_PER_CONTENT,
    )


def _delivery_policy(feature_id: str) -> DeliveryPolicyDefinition:
    return DeliveryPolicyDefinition(
        policy_id=f"{feature_id}.changed-fact",
        rule=_delivery_rule(),
        max_items=1,
        max_markdown_bytes=500,
        compatible_feature_ids=(feature_id,),
        compatibility_contract="synthetic exact feature binding",
        rejection_audit_reasons=BASE_POLICY_REJECTION_REASONS,
    )


def _policy_catalog(*feature_ids: str) -> DeliveryPolicyCatalog:
    return DeliveryPolicyCatalog(definitions=tuple(sorted(
        (_delivery_policy(feature_id) for feature_id in feature_ids),
        key=lambda item: item.policy_id,
    )))


def _definition(
    feature_id: str,
    *,
    calls: dict[str, int] | None = None,
) -> FeatureDefinition:
    counters = calls if calls is not None else {}

    def resource_loader(state, environment, proof_ir, invocation):
        counters["load"] = counters.get("load", 0) + 1
        return ()

    def discover(state, environment, proof_ir, invocation):
        counters["p2"] = counters.get("p2", 0) + 1
        return ()

    def analyze(proof_ir, coordinate, invocation):
        counters["p3"] = counters.get("p3", 0) + 1
        return AnalysisContribution()

    def lower(state, invocation):
        counters["p4"] = counters.get("p4", 0) + 1
        evidence = (EvidenceRef(
            evidence_id=f"{feature_id}:current-state",
            source_kind="synthetic_current_state",
            source_ref=state.provenance.artifact_ref,
            source_sha256=state.provenance.source_sha256,
        ),)
        return SurfaceContribution(diagnostics=(DiagnosticCandidate(
            candidate_id=f"{feature_id}:diagnostic",
            feature_id=feature_id,
            diagnostic=StructuredDiagnostic(
                producer_id=f"{feature_id}.synthetic",
                code="synthetic_fact",
                primary=f"{feature_id} is active",
                notes=(),
                help="",
                applicability=EXPLANATION_ONLY,
                evidence_refs=evidence,
            ),
            strategy_contract=_strategy(),
        ),))

    return FeatureDefinition(
        spec=FeatureSpec(
            feature_id=feature_id,
            gate=ExperimentGate(
                status="candidate",
                evidence_ledger_ids=("SYNTHETIC",),
                experiment_id=f"{feature_id}-activation-test",
            ),
            correctness_contract="emit one synthetic current-state diagnostic",
            provenance_contract="use only the current synthetic goal evidence",
            native_semantic_dependencies=(),
            shannon_delta_contract="synthetic activation sentinel",
            lexical_prefilter_contract="none",
            required_ir_capabilities=("AnalyzedProofState",),
            certification_policy="none",
            strategy_contracts=(_strategy(),),
        ),
        resource_load_request_producers=(resource_loader,),
        resource_discoverers=(discover,),
        analysis_producers=(analyze,),
        surface_lowerers=(lower,),
    )


def _snapshot() -> AuthoritativeSnapshotInput:
    state_ref = StateRef(
        session_id="activation-test",
        state_version=1,
        goal_identity="activation-goal",
        goal_identity_required=True,
        committed_prefix_identity="activation-prefix",
    )
    return AuthoritativeSnapshotInput(
        state_ref=state_ref,
        provenance=ProvenanceRef(
            producer="activation.fixture",
            authority="compiler.input.produced",
            source_sha256="a" * 64,
            artifact_ref="compiler_inputs/activation.json",
            source_event_id="activation-event",
            source_event_sequence=1,
            authoritative=True,
        ),
        target=TargetRef(source_file="eval/activation.ec", lemma="activation"),
        transition=TransitionRef(
            kind="initial",
            previous_state_ref=None,
            result_artifact_ref="compiler_inputs/activation.json",
        ),
        goal_lines=("Current goal", "x = x"),
        goal_count=1,
        goal_count_known=True,
        closed=False,
        native_state=native_state(state_ref),
    )


def _profile(feature_id: str, mode: str, profile_id: str) -> CompilerProfile:
    treatment = mode == TREATMENT
    return CompilerProfile(
        profile_id=profile_id,
        activations=(FeatureActivation(feature_id, mode),),
        delivery_policy_ids=(
            _delivery_policy(feature_id).policy_id,
        ) if treatment else (),
    )


def test_one_activation_atomically_controls_loading_p2_p3_and_p4() -> None:
    calls: dict[str, int] = {}
    definition = _definition("synthetic.vertical", calls=calls)
    catalog = FeatureCatalog(definitions=(definition,))
    snapshot = _snapshot()
    environment = CompilationEnvironment(
        environment_id="activation-test",
        source_units=(),
    )

    off = assemble_compiler_profile(
        _profile("synthetic.vertical", OFF, "synthetic-off"),
        catalog,
        _policy_catalog("synthetic.vertical"),
    )
    assert off.compiler.features == ()
    assert off.compiler.plan_resource_loads(snapshot, environment).requests == ()
    assert off.compiler.compile(snapshot, environment).candidate_surface.empty
    assert calls == {}

    audit = assemble_compiler_profile(
        _profile("synthetic.vertical", AUDIT, "synthetic-audit"),
        catalog,
        _policy_catalog("synthetic.vertical"),
    )
    audit.compiler.plan_resource_loads(snapshot, environment)
    audit_bundle = audit.compiler.compile(snapshot, environment)
    assert calls == {"load": 1, "p2": 1, "p3": 1, "p4": 1}
    assert len(audit_bundle.candidate_surface.diagnostics) == 1

    treatment = assemble_compiler_profile(
        _profile("synthetic.vertical", TREATMENT, "synthetic-treatment"),
        catalog,
        _policy_catalog("synthetic.vertical"),
    )
    treatment.compiler.plan_resource_loads(snapshot, environment)
    treatment_bundle = treatment.compiler.compile(snapshot, environment)
    assert calls == {"load": 2, "p2": 2, "p3": 2, "p4": 2}
    assert treatment_bundle == audit_bundle
    assert audit.activation_plan.pass_feature_ids == (
        "synthetic.vertical",
    )
    assert treatment.activation_plan.pass_feature_ids == (
        "synthetic.vertical",
    )
    assert audit.delivery_plan.admitted_feature_ids == ()
    assert treatment.delivery_plan.admitted_feature_ids == (
        "synthetic.vertical",
    )


def test_one_exact_invocation_context_reaches_loading_p2_p3_and_p4() -> None:
    seen = []

    def resource_loader(state, environment, proof_ir, invocation):
        seen.append(("load", invocation))
        return ()

    def discover(state, environment, proof_ir, invocation):
        seen.append(("p2", invocation))
        return ()

    def analyze(proof_ir, coordinate, invocation):
        seen.append(("p3", invocation))
        return AnalysisContribution()

    def lower(state, invocation):
        seen.append(("p4", invocation))
        return SurfaceContribution()

    base = _definition("synthetic.context")
    definition = replace(
        base,
        resource_load_request_producers=(resource_loader,),
        resource_discoverers=(discover,),
        analysis_producers=(analyze,),
        surface_lowerers=(lower,),
    )
    assembly = assemble_compiler_profile(
        _profile("synthetic.context", AUDIT, "synthetic-context"),
        FeatureCatalog(definitions=(definition,)),
        _policy_catalog("synthetic.context"),
    )
    snapshot = _snapshot()
    environment = CompilationEnvironment("activation-test", ())
    invocation = compiler_invocation_context(
        snapshot.state_ref,
        source_event_id=snapshot.provenance.source_event_id,
    )

    assembly.compiler.plan_resource_loads(snapshot, environment, invocation)
    assembly.compiler.compile(snapshot, environment, invocation)

    assert tuple(stage for stage, _context in seen) == (
        "load", "p2", "p3", "p4"
    )
    assert all(context is invocation for _stage, context in seen)


def test_disabling_one_line_does_not_change_another_lines_compiler_output() -> None:
    feature_a = _definition("synthetic.a")
    feature_b = _definition("synthetic.b")
    catalog = FeatureCatalog(definitions=(feature_a, feature_b))
    profile_with_a_off = CompilerProfile(
        profile_id="b-with-a-off",
        activations=(
            FeatureActivation("synthetic.a", OFF),
            FeatureActivation("synthetic.b", AUDIT),
        ),
    )
    b_only_catalog = FeatureCatalog(definitions=(feature_b,))
    b_only_profile = CompilerProfile(
        profile_id="b-only",
        activations=(FeatureActivation("synthetic.b", AUDIT),),
    )

    with_a_off = assemble_compiler_profile(
        profile_with_a_off, catalog, DeliveryPolicyCatalog()
    )
    b_only = assemble_compiler_profile(
        b_only_profile, b_only_catalog, DeliveryPolicyCatalog()
    )
    snapshot = _snapshot()
    environment = CompilationEnvironment(
        environment_id="activation-test",
        source_units=(),
    )

    assert tuple(
        item.spec.feature_id for item in with_a_off.compiler.features
    ) == ("synthetic.b",)
    assert with_a_off.compiler.compile(snapshot, environment) == (
        b_only.compiler.compile(snapshot, environment)
    )


def test_activation_plan_is_complete_deterministic_and_fail_closed() -> None:
    catalog = FeatureCatalog(definitions=(
        _definition("synthetic.a"),
        _definition("synthetic.b"),
    ))
    profile = CompilerProfile(
        profile_id="combined",
        activations=(
            FeatureActivation("synthetic.b", TREATMENT),
            FeatureActivation("synthetic.a", AUDIT),
        ),
        delivery_policy_ids=(_delivery_policy("synthetic.b").policy_id,),
    )
    first = build_activation_plan(profile, catalog)
    second = build_activation_plan(profile, catalog)

    assert first == second
    assert first.plan_sha256 == second.plan_sha256
    assert first.feature_modes == (
        ("synthetic.a", AUDIT),
        ("synthetic.b", TREATMENT),
    )
    assert first.pass_feature_ids == ("synthetic.a", "synthetic.b")
    assert not hasattr(first, "admitted_feature_ids")
    with pytest.raises(ValueError, match="unknown features"):
        build_activation_plan(
            CompilerProfile(
                profile_id="unknown",
                activations=(FeatureActivation("synthetic.missing", AUDIT),),
            ),
            catalog,
        )


def test_inconsistent_assembly_fails_closed() -> None:
    definition = _definition("synthetic.vertical")
    catalog = FeatureCatalog(definitions=(definition,))
    audit = assemble_compiler_profile(
        _profile("synthetic.vertical", AUDIT, "synthetic-audit"),
        catalog,
        _policy_catalog("synthetic.vertical"),
    )
    inconsistent_manifest = replace(
        audit.manifest,
        certification_feature_ids=(),
    )

    with pytest.raises(ValueError, match="certification manifest diverges"):
        CompilerAssembly(
            activation_plan=audit.activation_plan,
            delivery_plan=audit.delivery_plan,
            compiler=audit.compiler,
            manifest=inconsistent_manifest,
        )


def test_production_profiles_are_declarative_and_audit_treatment_share_passes(
) -> None:
    audit = compiler_assembly_for_profile(
        OPERATION_BINDING_REPAIR_AUDIT_PROFILE
    )
    treatment = compiler_assembly_for_profile(
        OPERATION_BINDING_REPAIR_TREATMENT_PROFILE
    )
    assert audit is not None and treatment is not None
    assert audit.activation_plan.pass_feature_ids == (
        treatment.activation_plan.pass_feature_ids
    )
    assert audit.activation_plan.certification_feature_ids == (
        treatment.activation_plan.certification_feature_ids
    )
    assert audit.delivery_plan.admitted_feature_ids == ()
    assert treatment.delivery_plan.admitted_feature_ids

    m09 = compiler_assembly_for_profile(M09_AUDIT_PROFILE)
    assert m09 is not None
    assert m09.activation_plan.pass_feature_ids == (
        "accepted_contract_retention",
    )
    assert m09.delivery_plan.admitted_feature_ids == ()

    m04 = compiler_assembly_for_profile(M04_AUDIT_PROFILE)
    assert m04 is not None
    assert m04.delivery_plan.admitted_feature_ids == ()
    assert compiler_assembly_for_profile(
        "l4_proof_state_compiler_v2_operation_readiness"
    ) is None
    assert compiler_assembly_for_profile(
        "l4_proof_state_compiler_v2_m07"
    ) is None

    assert compiler_assembly_for_profile(
        "l4_proof_state_compiler_v2_m05"
    ) is None
    assert not any(
        activation.feature_id == "losslessness_certificate_application"
        for profile in COMPILER_PROFILES.values()
        for activation in profile.activations
    )

    for profile in COMPILER_PROFILES.values():
        assert not hasattr(profile, "delivery_rules")
        assert not hasattr(profile, "max_items")
        assert not hasattr(profile, "max_markdown_bytes")

    configuration = (
        ROOT / "workflow" / "proof_state_compiler" / "configuration.py"
    ).read_text()
    assert "if profile ==" not in configuration
    assert not (
        ROOT
        / "core"
        / "easycrypt"
        / "proof_state_compiler"
        / "presets.py"
    ).exists()


def test_production_numerical_budgets_are_one_feature_per_policy() -> None:
    expected = {
        COMPOUND_TACTIC_PREFIX_RECOVERY_ONCE_POLICY_ID: (
            "compound_tactic_prefix_recovery", 700, 550
        ),
        OPERATION_BINDING_REPAIR_ONCE_POLICY_ID: (
            "operation_binding_repair", 700, 0
        ),
        INTRO_PATTERN_REPAIR_ONCE_POLICY_ID: (
            "intro_pattern_repair", 600, 0
        ),
        PURE_TAIL_RECOVERY_ONCE_POLICY_ID: (
            "pure_tail_recovery", 600, 0
        ),
        RELATION_BRIDGE_ONCE_POLICY_ID: (
            "relation_bridge_realization", 900, 0
        ),
        PHL_TRANSITIVITY_BOUNDARY_ONCE_POLICY_ID: (
            "phl_transitivity_boundary_repair", 600, 0
        ),
        TACTIC_DIALECT_REPAIR_ONCE_POLICY_ID: (
            "tactic_dialect_repair", 800, 0
        ),
    }
    policies = {
        item.policy_id: item
        for item in default_delivery_policy_catalog().definitions
        if item.compatible_feature_ids
    }

    assert set(policies) == set(expected)
    assert "current_failure_once" not in policies
    for policy_id, (feature_id, max_markdown_bytes, allowance) in expected.items():
        policy = policies[policy_id]
        assert policy.compatible_feature_ids == (feature_id,)
        assert policy.max_markdown_bytes == max_markdown_bytes
        assert policy.dependency_allowance_markdown_bytes == allowance
