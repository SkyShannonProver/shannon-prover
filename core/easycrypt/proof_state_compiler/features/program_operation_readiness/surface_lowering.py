"""Lower one intrinsic readiness fact to the bounded diagnostic surface."""

from __future__ import annotations

import hashlib

from core.easycrypt.proof_state_compiler.backend.surface_lowering import (
    SurfaceContribution,
)
from core.easycrypt.proof_state_compiler.contracts import (
    AnalyzedProofState,
    CompilerInvocationContext,
    DiagnosticCandidate,
)
from core.easycrypt.proof_state_compiler.features.program_operation_readiness.analysis import (
    PROGRAM_OPERATION_READINESS_PRODUCER_ID,
)
from core.easycrypt.proof_state_compiler.features.program_operation_readiness.feature import (
    PROGRAM_OPERATION_READINESS_FEATURE_ID,
    PROGRAM_OPERATION_READINESS_STRATEGY_CONTRACT,
)


def lower_program_operation_readiness(
    state: AnalyzedProofState,
    _invocation: CompilerInvocationContext,
) -> SurfaceContribution:
    matches = tuple(
        item for item in state.diagnostics
        if item.producer_id == PROGRAM_OPERATION_READINESS_PRODUCER_ID
    )
    if len(matches) != 1:
        return SurfaceContribution()
    item = matches[0]
    digest = hashlib.sha256(
        f"{item.code}\0{item.primary}".encode("utf-8")
    ).hexdigest()[:20]
    return SurfaceContribution(diagnostics=(DiagnosticCandidate(
        candidate_id=f"program-operation-readiness:{digest}",
        feature_id=PROGRAM_OPERATION_READINESS_FEATURE_ID,
        diagnostic=item,
        strategy_contract=PROGRAM_OPERATION_READINESS_STRATEGY_CONTRACT,
    ),))
