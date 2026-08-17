"""Feature definitions and the explicit compiler composition catalog."""

from __future__ import annotations

from dataclasses import dataclass

from core.easycrypt.proof_state_compiler.backend.surface_lowering import (
    SurfaceLowerer,
)
from core.easycrypt.proof_state_compiler.frontend.proof_ir_builder import (
    ResourceDiscoverer,
)
from core.easycrypt.proof_state_compiler.frontend.resource_loading import (
    ResourceLoadRequestProducer,
)
from core.easycrypt.proof_state_compiler.middle_end.contributions import (
    AnalysisProducer,
)
from core.easycrypt.proof_state_compiler.middle_end.native_dependencies import (
    NativeSemanticRequestProducer,
)
from core.easycrypt.proof_state_compiler.contracts.strategy import (
    StrategyContract,
)
from core.easycrypt.proof_state_compiler.features.execution import (
    FeatureExecutionGate,
    STATE_REFRESH_EXECUTION_GATE,
)


_GATE_STATUSES = {"hold", "candidate", "admitted"}
_PASSIVE_NATIVE_DEPENDENCIES = {"NativeProofStateSnapshot"}


@dataclass(frozen=True)
class ExperimentGate:
    status: str
    evidence_ledger_ids: tuple[str, ...]
    experiment_id: str = ""

    def __post_init__(self) -> None:
        if self.status not in _GATE_STATUSES:
            raise ValueError(f"unsupported experiment gate status {self.status!r}")
        if not self.evidence_ledger_ids:
            raise ValueError("experiment gate requires evidence ledger IDs")
        if self.status in {"candidate", "admitted"} and not self.experiment_id:
            raise ValueError(f"{self.status} feature requires an experiment_id")


@dataclass(frozen=True)
class FeatureSpec:
    feature_id: str
    gate: ExperimentGate
    correctness_contract: str
    provenance_contract: str
    native_semantic_dependencies: tuple[str, ...]
    shannon_delta_contract: str
    lexical_prefilter_contract: str
    required_ir_capabilities: tuple[str, ...]
    certification_policy: str
    strategy_contracts: tuple[StrategyContract, ...]

    def __post_init__(self) -> None:
        if not self.feature_id:
            raise ValueError("feature_id is required")
        if not self.correctness_contract or not self.provenance_contract:
            raise ValueError("feature requires correctness and provenance contracts")
        if (
            not self.shannon_delta_contract
            or not self.lexical_prefilter_contract
            or any(not item for item in self.native_semantic_dependencies)
            or len(self.native_semantic_dependencies)
            != len(set(self.native_semantic_dependencies))
        ):
            raise ValueError("feature requires explicit semantic ownership contracts")
        if not self.required_ir_capabilities:
            raise ValueError("feature requires explicit IR capabilities")
        if not self.certification_policy:
            raise ValueError("feature requires a certification policy")
        if not self.strategy_contracts:
            raise ValueError("feature requires explicit strategy contracts")
        if len(self.strategy_contracts) != len(set(self.strategy_contracts)):
            raise ValueError("feature contains duplicate strategy contracts")


@dataclass(frozen=True)
class FeatureDefinition:
    spec: FeatureSpec
    execution_gate: FeatureExecutionGate = STATE_REFRESH_EXECUTION_GATE
    resource_load_request_producers: tuple[ResourceLoadRequestProducer, ...] = ()
    resource_discoverers: tuple[ResourceDiscoverer, ...] = ()
    native_semantic_request_producers: tuple[
        NativeSemanticRequestProducer, ...
    ] = ()
    analysis_producers: tuple[AnalysisProducer, ...] = ()
    surface_lowerers: tuple[SurfaceLowerer, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.execution_gate, FeatureExecutionGate):
            raise TypeError("feature definition requires an execution gate")
        if not (
            self.resource_load_request_producers
            or self.resource_discoverers
            or self.native_semantic_request_producers
            or self.analysis_producers
            or self.surface_lowerers
        ):
            raise ValueError("feature definition requires at least one producer")
        request_bound_dependencies = tuple(
            dependency
            for dependency in self.spec.native_semantic_dependencies
            if dependency not in _PASSIVE_NATIVE_DEPENDENCIES
        )
        if (
            request_bound_dependencies
            and not self.native_semantic_request_producers
        ):
            raise ValueError(
                "request-bound native semantic dependencies require a native "
                "request producer"
            )


@dataclass(frozen=True)
class FeatureCatalog:
    """One auditable composition root; catalog membership never enables a pass."""

    definitions: tuple[FeatureDefinition, ...] = ()

    def __post_init__(self) -> None:
        feature_ids = tuple(item.spec.feature_id for item in self.definitions)
        if len(feature_ids) != len(set(feature_ids)):
            raise ValueError("feature catalog contains duplicate feature IDs")
        if feature_ids != tuple(sorted(feature_ids)):
            raise ValueError("feature catalog definitions must be sorted by feature ID")

    def get(self, feature_id: str) -> FeatureDefinition:
        match = next(
            (
                definition
                for definition in self.definitions
                if definition.spec.feature_id == feature_id
            ),
            None,
        )
        if match is None:
            raise KeyError(f"unknown feature_id {feature_id!r}")
        return match

    @property
    def feature_ids(self) -> tuple[str, ...]:
        return tuple(item.spec.feature_id for item in self.definitions)

    def select(self, feature_ids: tuple[str, ...]) -> tuple[FeatureDefinition, ...]:
        if len(feature_ids) != len(set(feature_ids)):
            raise ValueError("feature selection contains duplicate feature IDs")
        unknown = sorted(set(feature_ids) - set(self.feature_ids))
        if unknown:
            raise ValueError(
                "feature selection contains unknown IDs: " + ", ".join(unknown)
            )
        selected = set(feature_ids)
        return tuple(
            item for item in self.definitions if item.spec.feature_id in selected
        )
