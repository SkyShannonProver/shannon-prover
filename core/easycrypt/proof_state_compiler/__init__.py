"""Proof-state compiler V2: a clean, evidence-gated compiler pipeline.

The package starts at an authoritative event-bound snapshot. Passes communicate
only through immutable contracts; presentation and proof execution stay out of
the compiler.
"""

from core.easycrypt.proof_state_compiler.contracts import (
    ActionSurface,
    AnalyzedProofState,
    CandidateSurface,
    CompilationBundle,
    CompilationEnvironment,
    DeclarationLoadRequest,
    LoadedDeclaration,
    LoadedSourceUnit,
    NativeSemanticObservation,
    NativeProofTermDescriptor,
    NativeSemanticPlan,
    NativeSemanticRequest,
    NativeProofStateSnapshot,
    ProjectedProofState,
    ResourceLoadPlan,
    ProofIR,
    ProvenanceRef,
    StateRef,
    StrategyContract,
    TypedTermIR,
)
from core.easycrypt.proof_state_compiler.features import (
    ExperimentGate,
    FeatureCatalog,
    FeatureDefinition,
    FeatureSpec,
)
from core.easycrypt.proof_state_compiler.frontend import (
    AuthoritativeSnapshotInput,
    RuntimeSnapshotInput,
    project_authoritative_state,
)
from core.easycrypt.proof_state_compiler.compiler import ProofStateCompiler
from core.easycrypt.proof_state_compiler.serialization import (
    bundle_json,
    serialize_bundle,
)

__all__ = [
    "ActionSurface",
    "AnalyzedProofState",
    "AuthoritativeSnapshotInput",
    "RuntimeSnapshotInput",
    "CompilationBundle",
    "CompilationEnvironment",
    "DeclarationLoadRequest",
    "CandidateSurface",
    "ExperimentGate",
    "FeatureCatalog",
    "FeatureDefinition",
    "FeatureSpec",
    "ProjectedProofState",
    "ResourceLoadPlan",
    "LoadedSourceUnit",
    "LoadedDeclaration",
    "NativeSemanticObservation",
    "NativeProofTermDescriptor",
    "NativeSemanticPlan",
    "NativeSemanticRequest",
    "NativeProofStateSnapshot",
    "ProofIR",
    "ProofStateCompiler",
    "ProvenanceRef",
    "StateRef",
    "StrategyContract",
    "TypedTermIR",
    "project_authoritative_state",
    "bundle_json",
    "serialize_bundle",
]
