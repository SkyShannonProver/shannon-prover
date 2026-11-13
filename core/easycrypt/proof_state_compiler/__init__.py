"""Proof-state compiler V2: a clean, evidence-gated compiler pipeline.

The package starts at an authoritative event-bound snapshot. Passes communicate
only through immutable contracts; presentation and proof execution stay out of
the compiler.
"""

from core.easycrypt.proof_state_compiler.contracts import (
    CompilationEnvironment,
    LoadedDeclaration,
    LoadedSourceUnit,
    ProvenanceRef,
    StateRef,
)
from core.easycrypt.proof_state_compiler.features import (
    ExperimentGate,
    FeatureCatalog,
    FeatureDefinition,
    FeatureSpec,
)
from core.easycrypt.proof_state_compiler.frontend import (
    AuthoritativeSnapshotInput,
    project_authoritative_state,
)
from core.easycrypt.proof_state_compiler.compiler import ProofStateCompiler

__all__ = [
    "AuthoritativeSnapshotInput",
    "CompilationEnvironment",
    "ExperimentGate",
    "FeatureCatalog",
    "FeatureDefinition",
    "FeatureSpec",
    "LoadedSourceUnit",
    "LoadedDeclaration",
    "ProofStateCompiler",
    "ProvenanceRef",
    "StateRef",
    "project_authoritative_state",
]
