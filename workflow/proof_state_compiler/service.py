"""The only proof-state compiler entry point used by a node manager."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field, replace
from typing import Any, Protocol

from core.easycrypt.proof_state_compiler.backend import (
    AdmissionManifest,
    AdmissionResult,
    admit_action_surface,
)
from core.easycrypt.proof_state_compiler.compiler import ProofStateCompiler
from core.easycrypt.proof_state_compiler.contracts import (
    ActionSurface,
    ActionCandidate,
    CertificationReuse,
    CertificationResult,
    CompilationEnvironment,
    CompilationBundle,
    DeclarationLoadRequest,
    NativeSemanticObservation,
    NativeSemanticPlan,
    NativeSemanticPlanningReport,
    NativeSemanticPlanningStage,
    ResourceLoadPlan,
    ProvenanceRef,
    StateRef,
    CompilerInvocationContext,
    CompilerTurnEvidence,
    compiler_invocation_context,
    frozen_json_sha256,
)
from core.easycrypt.proof_state_compiler.features.execution import (
    FeatureExecutionPlan,
)
from workflow.proof_state_compiler.certification_gateway import (
    CertificationGateway,
)
from workflow.proof_state_compiler.assembly import CompilerAssembly
from workflow.proof_state_compiler.cache import (
    EXACT_OBSERVATION_CACHE_SCOPE,
    MATERIAL_CERTIFICATION_CACHE_SCOPE,
    RESOURCE_ENVIRONMENT_CACHE_SCOPE,
    ExactObservationCompilerCache,
    MaterialCertificationCacheEntry,
    MaterialStateCertificationCache,
    ResourceEnvironmentCache,
    ResourceEnvironmentCacheEntry,
    exact_observation_cache_key,
    material_certification_cache_key,
    material_proof_state_fingerprint,
    material_resource_environment_cache_key,
)
from workflow.proof_state_compiler.input_gateway import (
    LiveCompilerInput,
    attach_compiler_resources,
    attach_native_state,
    native_semantic_observations,
    runtime_compiler_input,
)
from workflow.proof_state_compiler.execution_lifetime import (
    FeatureExecutionLifetimeLedger,
)
from workflow.proof_state_compiler.lifetime import DeliveryLifetimeLedger
from workflow.proof_state_compiler.telemetry import compilation_telemetry


class CompilerRuntime(Protocol):
    state_version: int

    def committed_history(self) -> list[str]: ...
    def read_compiler_input_v2(
        self,
        *,
        timeout: int = 30,
    ) -> dict[str, Any]: ...
    def load_compiler_resources_v2(
        self,
        *,
        request_id: str,
        source_snapshot_id: str,
        source_event_id: str,
        expected_state: dict[str, object],
        load_requests: tuple[DeclarationLoadRequest, ...],
        timeout: int = 30,
    ) -> dict[str, Any]: ...
    def certify_exact_tactic(
        self, tactic: str, *, timeout: int = 30
    ) -> dict[str, Any]: ...
    def execute_native_semantic_batch(
        self,
        *,
        batch_id: str,
        requests: tuple[dict[str, object], ...],
        timeout: int = 30,
    ) -> dict[str, Any]: ...
    def project_native_state(
        self,
        *,
        request_id: str,
        max_nodes: int = 4096,
        max_depth: int = 128,
        timeout: int = 30,
    ) -> dict[str, Any]: ...


@dataclass(frozen=True)
class CompilerServiceResult:
    bundle: CompilationBundle
    certifications: tuple[CertificationResult, ...]
    admission: AdmissionResult
    telemetry: dict[str, Any]

    @property
    def action_surface(self) -> ActionSurface:
        return self.admission.action_surface


@dataclass(frozen=True)
class CompilerServiceSkipped:
    """A pre-P1 result proving that no configured feature was eligible."""

    execution_plan: FeatureExecutionPlan
    telemetry: dict[str, Any]

    def __post_init__(self) -> None:
        if self.execution_plan.eligible_feature_ids:
            raise ValueError("skipped compiler result contains eligible features")


@dataclass(frozen=True)
class _CompiledCore:
    """Cacheable P1-P4 and certification result, before stateful delivery."""

    bundle: CompilationBundle
    certifications: tuple[CertificationResult, ...]


@dataclass(frozen=True)
class ProofStateCompilerService:
    runtime: CompilerRuntime
    assembly: CompilerAssembly
    certification_gateway: CertificationGateway
    _observation_cache: ExactObservationCompilerCache[_CompiledCore] = field(
        default_factory=ExactObservationCompilerCache,
        init=False,
        repr=False,
    )
    _certification_cache: MaterialStateCertificationCache = field(
        default_factory=MaterialStateCertificationCache,
        init=False,
        repr=False,
    )
    _resource_cache: ResourceEnvironmentCache = field(
        default_factory=ResourceEnvironmentCache,
        init=False,
        repr=False,
    )
    _delivery_lifetime: DeliveryLifetimeLedger = field(
        default_factory=DeliveryLifetimeLedger,
        init=False,
        repr=False,
    )
    _execution_lifetime: FeatureExecutionLifetimeLedger = field(
        default_factory=FeatureExecutionLifetimeLedger,
        init=False,
        repr=False,
    )

    @classmethod
    def create(
        cls,
        *,
        runtime: CompilerRuntime,
        assembly: CompilerAssembly,
    ) -> "ProofStateCompilerService":
        return cls(
            runtime=runtime,
            assembly=assembly,
            certification_gateway=CertificationGateway.default(),
        )

    @property
    def compiler(self) -> ProofStateCompiler:
        return self.assembly.compiler

    @property
    def manifest(self) -> AdmissionManifest:
        return self.assembly.manifest

    def compile_current_state(
        self,
        turn_evidence: CompilerTurnEvidence | None = None,
    ) -> CompilerServiceResult | CompilerServiceSkipped:
        """Compile, certify, and deliver one unchanged authoritative state."""

        started = time.perf_counter_ns()
        execution_plan = self._execution_lifetime.suppress_completed(
            self.compiler.plan_execution(turn_evidence),
            turn_evidence,
        )
        execution_planning_done = time.perf_counter_ns()
        if not execution_plan.eligible_feature_ids:
            return CompilerServiceSkipped(
                execution_plan=execution_plan,
                telemetry={
                    "execution": {
                        "status": "skipped",
                        **execution_plan.to_dict(),
                        "lifetime_ledger_size": self._execution_lifetime.size,
                    },
                    "timings_ms": {
                        "execution_planning": _elapsed_ms(
                            started, execution_planning_done
                        ),
                        "input_initial": 0,
                        "manager_state_snapshot": 0,
                        "compiler_input_transport": 0,
                        "native_state_projection": 0,
                        "native_state_lowering": 0,
                        "dependency_planning": 0,
                        "resource_loading": 0,
                        "native_dependency_planning": 0,
                        "native_semantic_execution": 0,
                        "input_total": 0,
                        "p1_projection": 0,
                        "p2_frontend": 0,
                        "p3_dependency_check": 0,
                        "p3_analysis": 0,
                        "p4_lowering": 0,
                        "compile_p1_p4": 0,
                        "certification": 0,
                        "admission": 0,
                        "total": _elapsed_ms(started, execution_planning_done),
                    },
                },
            )
        compiler = self.compiler.select_execution_plan(execution_plan)
        manager_state_snapshot_started = time.perf_counter_ns()
        history_before = tuple(self.runtime.committed_history())
        state_version_before = self.runtime.state_version
        compiler_input_started = time.perf_counter_ns()
        initial_runtime = runtime_compiler_input(
            self.runtime.read_compiler_input_v2()
        )
        compiler_input_done = time.perf_counter_ns()
        native_state_request_id = (
            ""
            if initial_runtime.snapshot.closed
            else f"compiler-state-{uuid.uuid4()}"
        )
        native_state_result = (
            None
            if initial_runtime.snapshot.closed
            else self.runtime.project_native_state(
                request_id=native_state_request_id
            )
        )
        native_state_projection_done = time.perf_counter_ns()
        initial = attach_native_state(
            initial_runtime,
            native_state_result,
            native_state_request_id=native_state_request_id,
        )
        initial_input_done = time.perf_counter_ns()
        if initial.snapshot.state_ref.state_version != state_version_before:
            raise ValueError("compiler input state version drifted from manager")
        invocation_context = compiler_invocation_context(
            initial.snapshot.state_ref,
            turn_evidence,
            source_event_id=initial.snapshot.provenance.source_event_id,
        )
        cache_key = exact_observation_cache_key(
            initial,
            history=history_before,
            compiler=compiler,
            activation_plan=self.assembly.activation_plan,
            invocation_context=invocation_context,
        )
        cache_lookup_done = time.perf_counter_ns()
        has_native_dependencies = any(
            feature.native_semantic_request_producers
            for feature in compiler.features
        )
        # An open P1 input always owns a fresh native.state.produced occurrence.
        # Reusing an old bundle would retain the old occurrence as provenance.
        # Only closed states (which have no native projection) may reuse a
        # whole result; expensive certifications have their own material cache.
        cached = (
            None
            if has_native_dependencies or initial.snapshot.native_state is not None
            else self._observation_cache.get(cache_key)
        )
        if cached is not None:
            _require_runtime_unchanged(
                self.runtime,
                history_before=history_before,
                state_version_before=state_version_before,
            )
            core = cached.value
            admission_started = time.perf_counter_ns()
            admission = self._admit_delivery(
                core.bundle,
                core.certifications,
                invocation_context,
            )
            admission_done = time.perf_counter_ns()
            finished = admission_done
            result = CompilerServiceResult(
                bundle=core.bundle,
                certifications=core.certifications,
                admission=admission,
                telemetry=compilation_telemetry(
                    core.bundle,
                    core.certifications,
                    admission,
                    environment_id=initial.environment.environment_id,
                    activation_plan=self.assembly.activation_plan,
                    compiler_feature_ids=tuple(
                        item.spec.feature_id for item in compiler.features
                    ),
                    feature_execution_plan=execution_plan,
                    feature_execution_lifetime_size=(
                        self._execution_lifetime.size
                    ),
                    manifest_id=self.manifest.manifest_id,
                    certification_feature_ids=(
                        self.manifest.certification_feature_ids
                    ),
                    admitted_feature_ids=self.manifest.admitted_feature_ids,
                    admitted_strategy_classes=(
                        self.manifest.admitted_strategy_classes
                    ),
                    delivery_plan=self.assembly.delivery_plan,
                    planned_resource_loads=(),
                    resource_load_report=(),
                    loaded_declarations=(),
                    planned_native_semantics=(),
                    native_semantic_plans=(),
                    native_semantic_observations=(),
                    timings_ms={
                        "execution_planning": _elapsed_ms(
                            started, execution_planning_done
                        ),
                        "input_initial": _elapsed_ms(
                            started, initial_input_done
                        ),
                        "manager_state_snapshot": _elapsed_ms(
                            manager_state_snapshot_started,
                            compiler_input_started,
                        ),
                        "compiler_input_transport": _elapsed_ms(
                            compiler_input_started, compiler_input_done
                        ),
                        "native_state_projection": _elapsed_ms(
                            compiler_input_done, native_state_projection_done
                        ),
                        "native_state_lowering": _elapsed_ms(
                            native_state_projection_done, initial_input_done
                        ),
                        "cache_lookup": _elapsed_ms(
                            initial_input_done, cache_lookup_done
                        ),
                        "dependency_planning": 0,
                        "resource_loading": 0,
                        "native_dependency_planning": 0,
                        "native_semantic_execution": 0,
                        "input_total": _elapsed_ms(
                            started, initial_input_done
                        ),
                        "p1_projection": 0,
                        "p2_frontend": 0,
                        "p3_dependency_check": 0,
                        "p3_analysis": 0,
                        "p4_lowering": 0,
                        "compile_p1_p4": 0,
                        "certification": 0,
                        "admission": _elapsed_ms(
                            admission_started, admission_done
                        ),
                        "total": _elapsed_ms(started, finished),
                    },
                    exact_observation_cache={
                        "hit": True,
                        "stored": True,
                        "key": cache_key,
                        "scope": EXACT_OBSERVATION_CACHE_SCOPE,
                        "origin_environment_id": (
                            cached.origin_environment_id
                        ),
                        "reused_compilation": True,
                        "reused_certification_count": len(
                            core.certifications
                        ),
                    },
                    certification_cache={
                        "lookup_performed": False,
                        "hit": None,
                        "key": "",
                        "scope": MATERIAL_CERTIFICATION_CACHE_SCOPE,
                        "material_state_sha256": "",
                        "origin_state_version": None,
                        "current_state_version": state_version_before,
                        "reused_certification_count": len(
                            core.certifications
                        ),
                        "reuse_via": "exact_observation_result",
                    },
                    resource_cache={
                        "lookup_performed": False,
                        "hit": None,
                        "key": "",
                        "scope": RESOURCE_ENVIRONMENT_CACHE_SCOPE,
                        "origin_environment_id": "",
                        "reused_declaration_count": 0,
                    },
                    certification_work_performed=False,
                    state_refresh_trigger=invocation_context.state_refresh,
                    invocation_context=invocation_context,
                    delivery_lifetime_size=(
                        self._delivery_lifetime.projected_size(
                            admission.presented_delivery_ids
                        )
                    ),
                ),
            )
            self._delivery_lifetime.record(admission.presented_delivery_ids)
            self._execution_lifetime.record_completed(
                execution_plan,
                turn_evidence,
            )
            return result
        native_stage_one_planning_started = time.perf_counter_ns()
        native_budget = compiler.native_planning_budget
        native_stage_one = compiler.plan_native_semantics(
            initial.snapshot,
            initial.environment,
            invocation_context,
            native_budget,
        )
        native_stage_one_budget_after = native_budget.consume(native_stage_one)
        native_stage_one_record = NativeSemanticPlanningStage.from_plan(
            stage="pre_resource",
            plan=native_stage_one,
            budget_after=native_stage_one_budget_after,
        )
        native_budget = native_stage_one_budget_after
        native_stage_one_planning_done = time.perf_counter_ns()
        initial, native_stage_one_observations = _execute_native_semantic_plan(
            self.runtime,
            initial,
            native_stage_one,
        )
        native_stage_one_execution_done = time.perf_counter_ns()
        plan = compiler.plan_resource_loads(
            initial.snapshot,
            initial.environment,
            invocation_context,
        )
        planning_done = time.perf_counter_ns()
        resource_cache = {
            "lookup_performed": False,
            "hit": None,
            "key": "",
            "scope": RESOURCE_ENVIRONMENT_CACHE_SCOPE,
            "origin_environment_id": "",
            "reused_declaration_count": 0,
        }
        if plan.requests:
            resource_key = material_resource_environment_cache_key(
                initial,
                plan=plan,
                compiler=compiler,
                activation_plan=self.assembly.activation_plan,
            )
            cached_resources = self._resource_cache.get(resource_key)
            if cached_resources is not None:
                _validate_cached_resource_environment(
                    plan,
                    initial,
                    cached_resources,
                )
                live = LiveCompilerInput(
                    snapshot=initial.snapshot,
                    environment=CompilationEnvironment(
                        environment_id=(
                            initial.environment.environment_id
                            + ":resource-cache:"
                            + resource_key[:16]
                        ),
                        source_units=initial.environment.source_units,
                        loaded_declarations=(
                            cached_resources.loaded_declarations
                        ),
                        easycrypt_runtime=(
                            initial.environment.easycrypt_runtime
                        ),
                        native_semantic_observations=(
                            initial.environment.native_semantic_observations
                        ),
                    ),
                    source_snapshot_id=initial.source_snapshot_id,
                    # A cache hit is not a new runtime load occurrence.  The
                    # original report remains on the cache entry for audit.
                    resource_load_report=(),
                )
                resource_cache = {
                    "lookup_performed": True,
                    "hit": True,
                    "key": resource_key,
                    "scope": RESOURCE_ENVIRONMENT_CACHE_SCOPE,
                    "origin_environment_id": (
                        cached_resources.origin_environment_id
                    ),
                    "reused_declaration_count": len(
                        cached_resources.loaded_declarations
                    ),
                    "origin_reports": [
                        item.to_dict()
                        for item in cached_resources.load_report
                    ],
                }
            else:
                resource_request_id = f"compiler-resources-{uuid.uuid4()}"
                live = attach_compiler_resources(
                    initial,
                    self.runtime.load_compiler_resources_v2(
                        request_id=resource_request_id,
                        source_snapshot_id=initial.source_snapshot_id,
                        source_event_id=(
                            initial.snapshot.provenance.source_event_id
                        ),
                        expected_state=(
                            initial.snapshot.state_ref.identity_payload()
                        ),
                        load_requests=plan.requests,
                    ),
                    expected_request_id=resource_request_id,
                )
                _validate_resource_load_response(plan, initial, live)
                self._resource_cache.store(
                    key=resource_key,
                    loaded_declarations=live.environment.loaded_declarations,
                    load_report=live.resource_load_report,
                    origin_environment_id=live.environment.environment_id,
                )
                resource_cache = {
                    "lookup_performed": True,
                    "hit": False,
                    "key": resource_key,
                    "scope": RESOURCE_ENVIRONMENT_CACHE_SCOPE,
                    "origin_environment_id": live.environment.environment_id,
                    "reused_declaration_count": 0,
                }
        else:
            live = initial
        resource_loading_done = time.perf_counter_ns()
        if live.snapshot.state_ref.state_version != state_version_before:
            raise ValueError("compiler input state version drifted from manager")
        native_stage_two_planning_started = time.perf_counter_ns()
        native_stage_two = compiler.plan_native_semantics(
            live.snapshot,
            live.environment,
            invocation_context,
            native_budget,
        )
        native_stage_two_budget_after = native_budget.consume(native_stage_two)
        native_stage_two_record = NativeSemanticPlanningStage.from_plan(
            stage="post_resource",
            plan=native_stage_two,
            budget_after=native_stage_two_budget_after,
        )
        native_budget = native_stage_two_budget_after
        native_stage_two_planning_done = time.perf_counter_ns()
        live, native_stage_two_observations = _execute_native_semantic_plan(
            self.runtime,
            live,
            native_stage_two,
        )
        native_execution_done = time.perf_counter_ns()
        unresolved = compiler.plan_native_semantics(
            live.snapshot,
            live.environment,
            invocation_context,
            native_budget,
        )
        if unresolved.requests:
            raise ValueError(
                "native semantic producers exceeded the two-stage dependency bound"
            )
        native_observations = (
            native_stage_one_observations + native_stage_two_observations
        )
        planned_native_semantics = (
            native_stage_one.requests + native_stage_two.requests
        )
        bundle, compiler_pass_timings = compiler.compile_with_timings(
            live.snapshot,
            live.environment,
            invocation_context,
            native_budget=native_budget,
            planning_report=NativeSemanticPlanningReport(
                state_ref=live.snapshot.state_ref,
                stages=(native_stage_one_record, native_stage_two_record),
            ),
        )
        compile_done = time.perf_counter_ns()
        fingerprint = material_proof_state_fingerprint(
            live,
            history=history_before,
        )
        certification_candidates = _eligible_certification_candidates(
            bundle,
            self.manifest.certification_feature_ids,
        )
        certification_cache = {
            "lookup_performed": False,
            "hit": None,
            "key": "",
            "scope": MATERIAL_CERTIFICATION_CACHE_SCOPE,
            "material_state_sha256": fingerprint.sha256,
            "origin_state_version": None,
            "current_state_version": bundle.state_ref.state_version,
            "reused_certification_count": 0,
            "reuse_via": "",
        }
        certification_work_performed = False
        certification_complete = True
        if certification_candidates:
            certification_key = material_certification_cache_key(
                fingerprint,
                bundle.candidate_surface,
                eligible_feature_ids=(
                    self.manifest.certification_feature_ids
                ),
            )
            cached_certifications = self._certification_cache.get(
                certification_key
            )
            if cached_certifications is not None:
                certifications = _reuse_material_certifications(
                    cached_certifications,
                    bundle=bundle,
                    current_input_provenance=live.snapshot.provenance,
                    material_state_sha256=fingerprint.sha256,
                    eligible_feature_ids=(
                        self.manifest.certification_feature_ids
                    ),
                )
                certification_cache = {
                    **certification_cache,
                    "lookup_performed": True,
                    "hit": True,
                    "key": certification_key,
                    "origin_state_version": (
                        cached_certifications.origin_state_ref.state_version
                    ),
                    "reused_certification_count": len(certifications),
                    "reuse_via": "material_state_equivalence",
                }
            else:
                certification_work_performed = True
                certifications = self.certification_gateway.certify(
                    bundle.candidate_surface,
                    self.runtime,
                    eligible_feature_ids=(
                        self.manifest.certification_feature_ids
                    ),
                )
                cacheable = _certifications_cover_candidates(
                    certifications,
                    certification_candidates,
                    bundle.state_ref,
                )
                if cacheable:
                    self._certification_cache.store(
                        key=certification_key,
                        material_state_sha256=fingerprint.sha256,
                        certifications=certifications,
                        origin_state_ref=bundle.state_ref,
                        origin_input_provenance=live.snapshot.provenance,
                        origin_environment_id=live.environment.environment_id,
                    )
                certification_complete = cacheable
                certification_cache = {
                    **certification_cache,
                    "lookup_performed": True,
                    "hit": False,
                    "key": certification_key,
                    "cacheable_result": cacheable,
                }
        else:
            certifications = ()
        certification_done = time.perf_counter_ns()
        admission = admit_action_surface(
            bundle.candidate_surface,
            certifications,
            self.manifest,
            triggers=invocation_context.triggers,
            previously_presented=self._delivery_lifetime.snapshot(),
        )
        admission_done = time.perf_counter_ns()
        _require_runtime_unchanged(
            self.runtime,
            history_before=history_before,
            state_version_before=state_version_before,
        )
        result = CompilerServiceResult(
            bundle=bundle,
            certifications=certifications,
            admission=admission,
            telemetry=compilation_telemetry(
                bundle,
                certifications,
                admission,
                environment_id=live.environment.environment_id,
                activation_plan=self.assembly.activation_plan,
                compiler_feature_ids=tuple(
                    item.spec.feature_id for item in compiler.features
                ),
                feature_execution_plan=execution_plan,
                feature_execution_lifetime_size=(
                    self._execution_lifetime.size
                ),
                manifest_id=self.manifest.manifest_id,
                certification_feature_ids=(
                    self.manifest.certification_feature_ids
                ),
                admitted_feature_ids=self.manifest.admitted_feature_ids,
                admitted_strategy_classes=(
                    self.manifest.admitted_strategy_classes
                ),
                delivery_plan=self.assembly.delivery_plan,
                planned_resource_loads=plan.requests,
                resource_load_report=live.resource_load_report,
                loaded_declarations=live.environment.loaded_declarations,
                planned_native_semantics=planned_native_semantics,
                native_semantic_plans=(
                    native_stage_one,
                    native_stage_two,
                ),
                native_semantic_observations=native_observations,
                timings_ms={
                    "execution_planning": _elapsed_ms(
                        started, execution_planning_done
                    ),
                    "input_initial": _elapsed_ms(started, initial_input_done),
                    "manager_state_snapshot": _elapsed_ms(
                        manager_state_snapshot_started, compiler_input_started
                    ),
                    "compiler_input_transport": _elapsed_ms(
                        compiler_input_started, compiler_input_done
                    ),
                    "native_state_projection": _elapsed_ms(
                        compiler_input_done, native_state_projection_done
                    ),
                    "native_state_lowering": _elapsed_ms(
                        native_state_projection_done, initial_input_done
                    ),
                    "dependency_planning": _elapsed_ms(
                        native_stage_one_execution_done, planning_done
                    ),
                    "resource_loading": _elapsed_ms(
                        planning_done, resource_loading_done
                    ),
                    "native_dependency_planning": _elapsed_ms(
                        native_stage_one_planning_started,
                        native_stage_one_planning_done,
                    ) + _elapsed_ms(
                        native_stage_two_planning_started,
                        native_stage_two_planning_done,
                    ),
                    "native_semantic_execution": _elapsed_ms(
                        native_stage_one_planning_done,
                        native_stage_one_execution_done,
                    ) + _elapsed_ms(
                        native_stage_two_planning_done,
                        native_execution_done,
                    ),
                    "input_total": _elapsed_ms(
                        started, native_execution_done
                    ),
                    **compiler_pass_timings,
                    "certification": _elapsed_ms(
                        compile_done, certification_done
                    ),
                    "admission": _elapsed_ms(
                        certification_done, admission_done
                    ),
                    "total": _elapsed_ms(started, admission_done),
                },
                exact_observation_cache={
                    "hit": False,
                    "stored": (
                        certification_complete
                        and not has_native_dependencies
                        and live.snapshot.native_state is None
                    ),
                    "key": cache_key,
                    "scope": EXACT_OBSERVATION_CACHE_SCOPE,
                    "origin_environment_id": live.environment.environment_id,
                    "reused_compilation": False,
                    "reused_certification_count": 0,
                },
                certification_cache=certification_cache,
                resource_cache=resource_cache,
                certification_work_performed=certification_work_performed,
                state_refresh_trigger=invocation_context.state_refresh,
                invocation_context=invocation_context,
                delivery_lifetime_size=self._delivery_lifetime.projected_size(
                    admission.presented_delivery_ids
                ),
            ),
        )
        if (
            certification_complete
            and not has_native_dependencies
            and live.snapshot.native_state is None
        ):
            self._observation_cache.store(
                key=cache_key,
                value=_CompiledCore(
                    bundle=bundle,
                    certifications=certifications,
                ),
                origin_environment_id=live.environment.environment_id,
            )
        self._delivery_lifetime.record(admission.presented_delivery_ids)
        self._execution_lifetime.record_completed(
            execution_plan,
            turn_evidence,
        )
        return result

    def _admit_delivery(
        self,
        bundle: CompilationBundle,
        certifications: tuple[CertificationResult, ...],
        invocation_context: CompilerInvocationContext,
    ) -> AdmissionResult:
        admission = admit_action_surface(
            bundle.candidate_surface,
            certifications,
            self.manifest,
            triggers=invocation_context.triggers,
            previously_presented=self._delivery_lifetime.snapshot(),
        )
        return admission


def _eligible_certification_candidates(
    bundle: CompilationBundle,
    eligible_feature_ids: tuple[str, ...],
) -> tuple[ActionCandidate, ...]:
    eligible = set(eligible_feature_ids)
    return tuple(
        item
        for item in bundle.candidate_surface.actions
        if item.feature_id in eligible
    )


def _execute_native_semantic_plan(
    runtime: CompilerRuntime,
    live: LiveCompilerInput,
    plan: NativeSemanticPlan,
) -> tuple[LiveCompilerInput, tuple[NativeSemanticObservation, ...]]:
    """Execute one bounded stage and fan one native unit out to its consumers."""

    if plan.state_ref != live.snapshot.state_ref:
        raise ValueError("native semantic plan crossed the live StateRef")
    if not plan.execution_units:
        return live, ()
    runtime_identity = live.environment.easycrypt_runtime
    if runtime_identity is None:
        raise ValueError(
            "native semantic planning requires EasyCrypt runtime identity"
        )
    batch_id = f"compiler-native-batch-{uuid.uuid4()}"
    raw_result = runtime.execute_native_semantic_batch(
        batch_id=batch_id,
        requests=tuple(
            unit.runtime_payload() for unit in plan.execution_units
        ),
    )
    observations = native_semantic_observations(
        raw_result,
        execution_units=plan.execution_units,
        expected_batch_id=batch_id,
        expected_runtime=runtime_identity,
    )
    return LiveCompilerInput(
        snapshot=live.snapshot,
        environment=live.environment.with_native_semantic_observations(
            observations
        ),
        source_snapshot_id=live.source_snapshot_id,
        resource_load_report=live.resource_load_report,
    ), observations


def _certifications_cover_candidates(
    certifications: tuple[CertificationResult, ...],
    candidates: tuple[ActionCandidate, ...],
    state_ref: StateRef,
) -> bool:
    expected = {item.candidate_id: item for item in candidates}
    observed = {item.candidate_id: item for item in certifications}
    if len(expected) != len(candidates) or len(observed) != len(certifications):
        return False
    if set(expected) != set(observed):
        return False
    return all(
        result.state_ref == state_ref
        and result.policy == candidate.certification_policy
        and result.intent == candidate.intent
        and result.payload_sha256 == frozen_json_sha256(candidate.payload)
        and result.reuse is None
        for candidate_id, candidate in expected.items()
        for result in (observed[candidate_id],)
    )


def _reuse_material_certifications(
    entry: MaterialCertificationCacheEntry,
    *,
    bundle: CompilationBundle,
    current_input_provenance: ProvenanceRef,
    material_state_sha256: str,
    eligible_feature_ids: tuple[str, ...],
) -> tuple[CertificationResult, ...]:
    if entry.material_state_sha256 != material_state_sha256:
        raise ValueError("material certification cache fingerprint drifted")
    candidates = _eligible_certification_candidates(
        bundle,
        eligible_feature_ids,
    )
    if not _certifications_cover_origin_candidates(
        entry.certifications,
        candidates,
        entry.origin_state_ref,
    ):
        raise ValueError("material certification cache candidate drifted")
    reuse = CertificationReuse(
        material_state_sha256=material_state_sha256,
        origin_state_ref=entry.origin_state_ref,
        origin_input_provenance=entry.origin_input_provenance,
        current_input_provenance=current_input_provenance,
    )
    return tuple(
        replace(item, state_ref=bundle.state_ref, reuse=reuse)
        for item in entry.certifications
    )


def _certifications_cover_origin_candidates(
    certifications: tuple[CertificationResult, ...],
    candidates: tuple[ActionCandidate, ...],
    origin_state_ref: StateRef,
) -> bool:
    expected = {item.candidate_id: item for item in candidates}
    observed = {item.candidate_id: item for item in certifications}
    if len(expected) != len(candidates) or len(observed) != len(certifications):
        return False
    if set(expected) != set(observed):
        return False
    return all(
        result.state_ref == origin_state_ref
        and result.policy == candidate.certification_policy
        and result.intent == candidate.intent
        and result.payload_sha256 == frozen_json_sha256(candidate.payload)
        and result.reuse is None
        for candidate_id, candidate in expected.items()
        for result in (observed[candidate_id],)
    )


def _elapsed_ms(start: int, end: int) -> int:
    return max(0, int((end - start) / 1_000_000))


def _require_runtime_unchanged(
    runtime: CompilerRuntime,
    *,
    history_before: tuple[str, ...],
    state_version_before: int,
) -> None:
    if tuple(runtime.committed_history()) != history_before:
        raise RuntimeError("compiler service changed committed proof history")
    if runtime.state_version != state_version_before:
        raise RuntimeError("compiler service changed manager state version")


def _validate_resource_load_response(
    plan: ResourceLoadPlan,
    initial: LiveCompilerInput,
    loaded: LiveCompilerInput,
) -> None:
    if loaded.snapshot.state_ref != plan.state_ref:
        raise ValueError("compiler resource loading changed the proof state")
    if loaded.environment.source_units != initial.environment.source_units:
        raise ValueError("compiler resource loading changed the source environment")
    expected = {request.request_id: request for request in plan.requests}
    observed = {
        str(item.get("request_id") or ""): item
        for item in loaded.resource_load_report
    }
    if set(observed) != set(expected):
        raise ValueError("compiler resource load report does not match its plan")
    for request_id, request in expected.items():
        item = observed[request_id]
        if not _resource_report_matches_request(item, request):
            raise ValueError("compiler resource load report request drifted")
    loaded_count = sum(
        int(item.get("loaded_count") or 0)
        for item in loaded.resource_load_report
    )
    if loaded_count != len(loaded.environment.loaded_declarations):
        raise ValueError("compiler resource load report cardinality drifted")
    if any(
        not any(
            _request_authorizes_symbol(request, declaration.symbol)
            for request in plan.requests
        )
        for declaration in loaded.environment.loaded_declarations
    ):
        raise ValueError("compiler resource loader returned an unrequested symbol")


def _validate_cached_resource_environment(
    plan: ResourceLoadPlan,
    initial: LiveCompilerInput,
    entry: ResourceEnvironmentCacheEntry,
) -> None:
    """Recheck immutable cached declarations against the current load plan."""

    if not plan.requests:
        raise ValueError("resource cache entry cannot satisfy an empty plan")
    if initial.environment.loaded_declarations:
        raise ValueError(
            "resource cache reuse requires a declaration-free initial input"
        )
    if any(
        not any(
            _request_authorizes_symbol(request, declaration.symbol)
            for request in plan.requests
        )
        for declaration in entry.loaded_declarations
    ):
        raise ValueError("cached declaration is outside the current load plan")
    expected = {request.request_id: request for request in plan.requests}
    observed = {
        str(item.get("request_id") or ""): item
        for item in (report.to_dict() for report in entry.load_report)
    }
    if set(observed) != set(expected):
        raise ValueError("cached resource report does not match current plan")
    for request_id, request in expected.items():
        item = observed[request_id]
        if not _resource_report_matches_request(item, request):
            raise ValueError("cached resource request drifted from current plan")
    loaded_count = sum(
        int(item.get("loaded_count") or 0) for item in observed.values()
    )
    if loaded_count != len(entry.loaded_declarations):
        raise ValueError("cached resource report cardinality drifted")


def _resource_report_matches_request(
    item: dict[str, Any],
    request: DeclarationLoadRequest,
) -> bool:
    if (
        item.get("producer_id") != request.producer_id
        or item.get("query_kind") != request.query_kind
    ):
        return False
    if request.query_kind == "scope_member_declarations":
        return bool(
            item.get("scope") == request.scope
            and item.get("member_name_terms")
            == list(request.member_name_terms)
        )
    return item.get("symbols") == list(request.symbols)


def _request_authorizes_symbol(
    request: DeclarationLoadRequest,
    symbol: str,
) -> bool:
    if request.query_kind == "scope_member_declarations":
        return symbol.startswith(request.scope + ".")
    return symbol in request.symbols
