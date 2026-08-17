"""One fixed P1 -> P2 -> P3 -> P4 compiler orchestration."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from core.easycrypt.proof_state_compiler.backend.surface_lowering import (
    build_candidate_surface,
)
from core.easycrypt.proof_state_compiler.contracts import (
    AnalyzedProofState,
    CandidateSurface,
    CompilationBundle,
    CompilationEnvironment,
    CompilerInvocationContext,
    CompilerTurnEvidence,
    CURRENT_STATE_FAILURE,
    NativePlanningBudget,
    ProjectedProofState,
    ProofIR,
    NativeSemanticPlan,
    NativeSemanticPlanningReport,
    ResourceLoadPlan,
    StateRef,
    compiler_invocation_context,
)
from core.easycrypt.proof_state_compiler.features.registry import (
    FeatureDefinition,
)
from core.easycrypt.proof_state_compiler.features.execution import (
    FeatureExecutionDecision,
    FeatureExecutionEligibility,
    FeatureExecutionPlan,
)
from core.easycrypt.proof_state_compiler.frontend import (
    AuthoritativeSnapshotInput,
    build_proof_ir,
    plan_resource_loads,
    project_authoritative_state,
)
from core.easycrypt.proof_state_compiler.middle_end import (
    NativeSemanticProducerBinding,
    analyze_proof_ir,
    plan_native_semantics,
)


IR_CAPABILITIES = frozenset({
    "CompilerInvocationContext",
    "FailureObservation",
    "AttemptedOperationIR",
    "RecoveryHandoff",
    "RecoveryClaim",
    "RecoveryActionRealization",
    "RecoveryPreservationWitness",
    "GoalIR",
    "GoalIR.formula",
    "TypedTermIR",
    "FormulaRelation",
    "ProofFact",
    "ProgramStatement",
    "ProgramStatement.procedure",
    "ProgramStatement.structural_path",
    "ProofResource",
    "ModuleSpellingInventory",
    "ProofJudgment.probability",
    "ProofResource.procedure_certificate",
    "ApplicationSignature",
    "DeclarationLoadRequest.scope_member_declarations",
    "DeclarationLoadRequest.symbol_declarations",
    "ArgumentSlot.module",
    "SlotResolution",
    "ProofCoordinate",
    "ResourceAssessment",
    "BindingResolution",
    "ApplicationCandidate",
    "ScopeAssessment",
    "BoundaryContractAssessment",
    "TransformAssessment",
    "AnalyzedProofState",
    "NativeSemanticObservation",
    "NativeProofTermDescriptor",
    "NativeApplicationSyntaxRepairDescriptor",
    "NativeRelationBridgeDescriptor",
    "NativeRelationBridgeChoiceDescriptor",
    "NativePhlTransitivityBoundaryDescriptor",
    "NativePureTailRewriteDescriptor",
    "NativeEagerWhileDialectDescriptor",
    "NativeIntroPatternRepairDescriptor",
    "NativeTacticPrefixDiagnosticDescriptor",
    "NativeSemanticRequest.proof_term_elaboration",
})


@dataclass(frozen=True)
class ProofStateCompiler:
    """The pipeline is fixed; registered features contribute typed producers."""

    features: tuple[FeatureDefinition, ...] = ()
    native_planning_budget: NativePlanningBudget = field(
        default_factory=NativePlanningBudget
    )

    def __post_init__(self) -> None:
        feature_ids = [feature.spec.feature_id for feature in self.features]
        if len(feature_ids) != len(set(feature_ids)):
            raise ValueError("compiler contains duplicate feature IDs")
        for feature in self.features:
            missing = sorted(
                set(feature.spec.required_ir_capabilities) - IR_CAPABILITIES
            )
            if missing:
                raise ValueError(
                    f"feature {feature.spec.feature_id!r} requires unsupported "
                    f"IR capabilities: {', '.join(missing)}"
                )

    def plan_execution(
        self,
        turn_evidence: CompilerTurnEvidence | None,
    ) -> FeatureExecutionPlan:
        """Resolve the feature subset before any P1 or runtime I/O occurs."""

        evaluated = tuple(
            (feature, feature.execution_gate.evaluate(turn_evidence))
            for feature in self.features
        )
        handoff_scheduled = any(
            eligibility.eligible
            and feature.execution_gate.produces_recovery_handoff
            for feature, eligibility in evaluated
        )
        decisions = []
        for feature, eligibility in evaluated:
            if (
                handoff_scheduled
                and not eligibility.eligible
                and feature.execution_gate.accepts_recovery_handoff
            ):
                # This only schedules a removable recovery slice.  The native
                # handoff produced later in P2 carries the exact operation
                # family plus its native compound-boundary evidence; the
                # feature still has to establish ordinary applicability and
                # ownership.  State-changing repairs are recomposed and
                # certified from the original manager StateRef in P4.
                eligibility = FeatureExecutionEligibility(
                    eligible=True,
                    reason="candidate_typed_suffix_recovery_handoff",
                    trigger_kind=CURRENT_STATE_FAILURE,
                )
            decisions.append(FeatureExecutionDecision(
                feature_id=feature.spec.feature_id,
                gate_id=feature.execution_gate.gate_id,
                eligible=eligibility.eligible,
                reason=eligibility.reason,
                trigger_kind=eligibility.trigger_kind,
                lifetime=feature.execution_gate.lifetime,
            ))
        return FeatureExecutionPlan(tuple(decisions))

    def select_execution_plan(
        self,
        plan: FeatureExecutionPlan,
    ) -> "ProofStateCompiler":
        """Return the exact registered feature subset admitted by ``plan``."""

        configured = tuple(item.spec.feature_id for item in self.features)
        if plan.configured_feature_ids != configured:
            raise ValueError("feature execution plan diverges from compiler")
        selected = set(plan.eligible_feature_ids)
        return ProofStateCompiler(
            features=tuple(
                item for item in self.features
                if item.spec.feature_id in selected
            ),
            native_planning_budget=self.native_planning_budget,
        )

    def compile(
        self,
        snapshot: AuthoritativeSnapshotInput,
        environment: CompilationEnvironment,
        invocation: CompilerInvocationContext | None = None,
        *,
        native_budget: NativePlanningBudget | None = None,
        planning_report: NativeSemanticPlanningReport | None = None,
    ) -> CompilationBundle:
        bundle, _ = self.compile_with_timings(
            snapshot,
            environment,
            invocation,
            native_budget=native_budget,
            planning_report=planning_report,
        )
        return bundle

    def compile_with_timings(
        self,
        snapshot: AuthoritativeSnapshotInput,
        environment: CompilationEnvironment,
        invocation: CompilerInvocationContext | None = None,
        *,
        native_budget: NativePlanningBudget | None = None,
        planning_report: NativeSemanticPlanningReport | None = None,
    ) -> tuple[CompilationBundle, dict[str, int]]:
        """Compile once and expose feature-neutral pass latency attribution."""

        started = time.perf_counter_ns()
        invocation = _resolve_invocation(snapshot, invocation)
        projected = project_authoritative_state(snapshot)
        p1_done = time.perf_counter_ns()
        _require_stage("P1", projected, ProjectedProofState, snapshot.state_ref)
        if projected.provenance != snapshot.provenance:
            raise ValueError("P1 must preserve authoritative input provenance")
        source_event = _source_event(projected)

        proof_ir = build_proof_ir(
            projected,
            environment,
            tuple(
                producer
                for feature in self.features
                for producer in feature.resource_discoverers
            ),
            invocation,
            planning_report,
            include_module_spelling_inventory=_requires_ir_capability(
                self.features, "ModuleSpellingInventory"
            ),
        )
        p2_done = time.perf_counter_ns()
        _require_stage("P2", proof_ir, ProofIR, projected.state_ref, source_event)
        unresolved_native = plan_native_semantics(
            proof_ir,
            _native_producer_bindings(self.features),
            invocation,
            native_budget or self.native_planning_budget,
        )
        dependency_check_done = time.perf_counter_ns()
        if unresolved_native.requests:
            raise ValueError(
                "P3 cannot run with unresolved native semantic dependencies"
            )

        analyzed = analyze_proof_ir(
            proof_ir,
            tuple(
                producer
                for feature in self.features
                for producer in feature.analysis_producers
            ),
            invocation,
        )
        p3_done = time.perf_counter_ns()
        _require_stage(
            "P3", analyzed, AnalyzedProofState, projected.state_ref, source_event
        )

        candidates = build_candidate_surface(
            analyzed,
            tuple(
                lowerer
                for feature in self.features
                for lowerer in feature.surface_lowerers
            ),
            invocation,
        )
        p4_done = time.perf_counter_ns()
        _require_stage(
            "P4", candidates, CandidateSurface, projected.state_ref, source_event
        )
        registered = {feature.spec.feature_id for feature in self.features}
        produced = {
            item.feature_id
            for collection in (
                candidates.resource_references,
                candidates.binding_references,
                candidates.actions,
                candidates.diagnostics,
            )
            for item in collection
        }
        unknown = sorted(produced - registered)
        if unknown:
            raise ValueError(
                "P4 emitted candidates for unregistered features: "
                + ", ".join(unknown)
            )
        contracts_by_feature = {
            feature.spec.feature_id: set(feature.spec.strategy_contracts)
            for feature in self.features
        }
        undeclared = sorted(
            item.candidate_id
            for collection in (
                candidates.resource_references,
                candidates.binding_references,
                candidates.actions,
                candidates.diagnostics,
            )
            for item in collection
            if item.strategy_contract not in contracts_by_feature[item.feature_id]
        )
        if undeclared:
            raise ValueError(
                "P4 emitted candidates with undeclared strategy contracts: "
                + ", ".join(undeclared)
            )
        bundle = CompilationBundle(
            state_ref=projected.state_ref,
            projected_state=projected,
            proof_ir=proof_ir,
            analyzed_state=analyzed,
            candidate_surface=candidates,
        )
        return bundle, {
            "p1_projection": _elapsed_ms(started, p1_done),
            "p2_frontend": _elapsed_ms(p1_done, p2_done),
            "p3_dependency_check": _elapsed_ms(
                p2_done, dependency_check_done
            ),
            "p3_analysis": _elapsed_ms(dependency_check_done, p3_done),
            "p4_lowering": _elapsed_ms(p3_done, p4_done),
            "compile_p1_p4": _elapsed_ms(started, p4_done),
        }

    def plan_resource_loads(
        self,
        snapshot: AuthoritativeSnapshotInput,
        environment: CompilationEnvironment,
        invocation: CompilerInvocationContext | None = None,
    ) -> ResourceLoadPlan:
        """Discover bounded P2 dependencies without performing runtime I/O.

        The compiler was already assembled from one atomic activation plan.
        Resource dependencies therefore use the exact same feature definitions
        as P2 discovery, P3 analysis, and P4 lowering.
        """

        invocation = _resolve_invocation(snapshot, invocation)
        projected = project_authoritative_state(snapshot)
        _require_stage("P1", projected, ProjectedProofState, snapshot.state_ref)
        base_ir = build_proof_ir(
            projected,
            environment,
            invocation=invocation,
            include_module_spelling_inventory=_requires_ir_capability(
                self.features, "ModuleSpellingInventory"
            ),
        )
        _require_stage(
            "P2-base",
            base_ir,
            ProofIR,
            projected.state_ref,
            _source_event(projected),
        )
        return plan_resource_loads(
            projected,
            environment,
            base_ir,
            tuple(
                producer
                for feature in self.features
                for producer in feature.resource_load_request_producers
            ),
            invocation,
        )

    def plan_native_semantics(
        self,
        snapshot: AuthoritativeSnapshotInput,
        environment: CompilationEnvironment,
        invocation: CompilerInvocationContext | None = None,
        budget: NativePlanningBudget | None = None,
    ) -> NativeSemanticPlan:
        """Plan bounded P3 semantic dependencies without runtime I/O.

        Resource discovery runs first so a feature can derive an exact native
        request from verifier-resolved declarations. Only registered active
        feature producers participate; the shared compiler has no feature-ID
        conditionals.
        """

        invocation = _resolve_invocation(snapshot, invocation)
        projected = project_authoritative_state(snapshot)
        _require_stage("P1", projected, ProjectedProofState, snapshot.state_ref)
        proof_ir = build_proof_ir(
            projected,
            environment,
            tuple(
                producer
                for feature in self.features
                for producer in feature.resource_discoverers
            ),
            invocation,
            include_module_spelling_inventory=_requires_ir_capability(
                self.features, "ModuleSpellingInventory"
            ),
        )
        _require_stage(
            "P2-native-dependencies",
            proof_ir,
            ProofIR,
            projected.state_ref,
            _source_event(projected),
        )
        return plan_native_semantics(
            proof_ir,
            _native_producer_bindings(self.features),
            invocation,
            budget or self.native_planning_budget,
        )


def _native_producer_bindings(
    features: tuple[FeatureDefinition, ...],
) -> tuple[NativeSemanticProducerBinding, ...]:
    return tuple(
        NativeSemanticProducerBinding(
            feature_id=feature.spec.feature_id,
            producer=producer,
        )
        for feature in features
        for producer in feature.native_semantic_request_producers
    )


def _requires_ir_capability(
    features: tuple[FeatureDefinition, ...],
    capability: str,
) -> bool:
    return any(
        capability in feature.spec.required_ir_capabilities
        for feature in features
    )


def _resolve_invocation(
    snapshot: AuthoritativeSnapshotInput,
    invocation: CompilerInvocationContext | None,
) -> CompilerInvocationContext:
    if invocation is None:
        return compiler_invocation_context(
            snapshot.state_ref,
            source_event_id=snapshot.provenance.source_event_id,
        )
    if invocation.state_ref != snapshot.state_ref:
        raise ValueError("compiler invocation context is stale")
    return invocation


def _source_event(value: object) -> tuple[str, int]:
    provenance = value.provenance
    return provenance.source_event_id, provenance.source_event_sequence


def _elapsed_ms(start_ns: int, end_ns: int) -> int:
    return max(0, (end_ns - start_ns) // 1_000_000)


def _require_stage(
    stage: str,
    value: object,
    expected_type: type,
    expected_state_ref: StateRef,
    source_event: tuple[str, int] | None = None,
) -> None:
    if not isinstance(value, expected_type):
        raise TypeError(
            f"{stage} returned {type(value).__name__}; expected {expected_type.__name__}"
        )
    if value.state_ref != expected_state_ref:
        raise ValueError(f"{stage} returned facts for a different StateRef")
    if source_event is not None:
        if value.provenance.authoritative:
            raise ValueError(f"{stage} must return derived provenance")
        if _source_event(value) != source_event:
            raise ValueError(f"{stage} returned facts from a different source event")
