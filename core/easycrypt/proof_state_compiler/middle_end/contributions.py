"""Typed contributions produced by independently registered P3 analyses."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from core.easycrypt.proof_state_compiler.contracts.analyzed_state import (
    ApplicationCandidate,
    BindingResolution,
    BoundaryContractAssessment,
    ProofCoordinate,
    ResourceAssessment,
    ScopeAssessment,
    TransformAssessment,
)
from core.easycrypt.proof_state_compiler.contracts.application_applicability import (
    ApplicationApplicability,
)
from core.easycrypt.proof_state_compiler.contracts.diagnostics import (
    StructuredDiagnostic,
)
from core.easycrypt.proof_state_compiler.contracts.proof_ir import ProofIR
from core.easycrypt.proof_state_compiler.contracts.delivery import CompilerInvocationContext
from core.easycrypt.proof_state_compiler.contracts.failure import (
    RecoveryActionRealization,
    RecoveryClaim,
)


@dataclass(frozen=True)
class AnalysisContribution:
    resources: tuple[ResourceAssessment, ...] = ()
    bindings: tuple[BindingResolution, ...] = ()
    applications: tuple[ApplicationCandidate, ...] = ()
    application_applicabilities: tuple[ApplicationApplicability, ...] = ()
    scope: tuple[ScopeAssessment, ...] = ()
    boundary_contracts: tuple[BoundaryContractAssessment, ...] = ()
    transforms: tuple[TransformAssessment, ...] = ()
    diagnostics: tuple[StructuredDiagnostic, ...] = ()
    recovery_action_realizations: tuple[RecoveryActionRealization, ...] = ()
    recovery_claims: tuple[RecoveryClaim, ...] = ()


class AnalysisProducer(Protocol):
    def __call__(
        self,
        proof_ir: ProofIR,
        coordinate: ProofCoordinate,
        invocation: CompilerInvocationContext,
    ) -> AnalysisContribution: ...
