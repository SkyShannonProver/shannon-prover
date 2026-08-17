"""Whole-pipeline artifact binding all pass outputs to one proof state."""

from __future__ import annotations

from dataclasses import dataclass

from core.easycrypt.proof_state_compiler.contracts.candidate_surface import (
    CandidateSurface,
)
from core.easycrypt.proof_state_compiler.contracts.analyzed_state import (
    AnalyzedProofState,
)
from core.easycrypt.proof_state_compiler.contracts.projected_state import (
    ProjectedProofState,
)
from core.easycrypt.proof_state_compiler.contracts.proof_ir import ProofIR
from core.easycrypt.proof_state_compiler.contracts.state_ref import StateRef


COMPILER_SCHEMA_VERSION = 1
COMPILER_BUNDLE_KIND = "proof_state_compiler_v2_bundle"


@dataclass(frozen=True)
class CompilationBundle:
    state_ref: StateRef
    projected_state: ProjectedProofState
    proof_ir: ProofIR
    analyzed_state: AnalyzedProofState
    candidate_surface: CandidateSurface
    schema_version: int = COMPILER_SCHEMA_VERSION
    kind: str = COMPILER_BUNDLE_KIND

    def __post_init__(self) -> None:
        if self.schema_version != COMPILER_SCHEMA_VERSION:
            raise ValueError(f"unsupported compiler schema {self.schema_version}")
        if self.kind != COMPILER_BUNDLE_KIND:
            raise ValueError(f"unsupported compiler bundle kind {self.kind!r}")
        for name, value in (
            ("projected_state", self.projected_state),
            ("proof_ir", self.proof_ir),
            ("analyzed_state", self.analyzed_state),
            ("candidate_surface", self.candidate_surface),
        ):
            if value.state_ref != self.state_ref:
                raise ValueError(f"{name} belongs to a different StateRef")
        if not self.projected_state.provenance.authoritative:
            raise ValueError("P1 provenance must be authoritative")
        source_event = (
            self.projected_state.provenance.source_event_id,
            self.projected_state.provenance.source_event_sequence,
        )
        for name, value in (
            ("proof_ir", self.proof_ir),
            ("analyzed_state", self.analyzed_state),
            ("candidate_surface", self.candidate_surface),
        ):
            if value.provenance.authoritative:
                raise ValueError(f"{name} provenance must be derived")
            if (
                value.provenance.source_event_id,
                value.provenance.source_event_sequence,
            ) != source_event:
                raise ValueError(f"{name} provenance crosses event boundaries")
