"""Lower the uniquely owned PHL boundary diagnosis to one surface item."""

from core.easycrypt.proof_state_compiler.backend.surface_lowering import (
    SurfaceContribution,
)
from core.easycrypt.proof_state_compiler.contracts import (
    AnalyzedProofState,
    CompilerInvocationContext,
)
from core.easycrypt.proof_state_compiler.features.recovery_lowering import (
    attempt_diagnostic_candidate,
    attempt_diagnostics,
)
from .analysis import PHL_TRANSITIVITY_BOUNDARY_ANALYSIS_PRODUCER_ID
from .ids import (
    PHL_TRANSITIVITY_BOUNDARY_REPAIR_FEATURE_ID,
    PHL_TRANSITIVITY_BOUNDARY_REPAIR_STRATEGY_CONTRACT,
)


def lower_phl_transitivity_boundary(
    state: AnalyzedProofState,
    _invocation: CompilerInvocationContext,
) -> SurfaceContribution:
    attempted = state.attempted_operation
    if attempted is None or not state.recovery_ownership.owns(
        PHL_TRANSITIVITY_BOUNDARY_REPAIR_FEATURE_ID,
        attempted.recovery_key,
    ):
        return SurfaceContribution()
    diagnostics = attempt_diagnostics(
        state, PHL_TRANSITIVITY_BOUNDARY_ANALYSIS_PRODUCER_ID,
    )
    if len(diagnostics) != 1:
        return SurfaceContribution()
    return SurfaceContribution(diagnostics=(attempt_diagnostic_candidate(
        attempted,
        diagnostics[0],
        id_prefix="phl-boundary-diagnostic",
        feature_id=PHL_TRANSITIVITY_BOUNDARY_REPAIR_FEATURE_ID,
        strategy_contract=PHL_TRANSITIVITY_BOUNDARY_REPAIR_STRATEGY_CONTRACT,
    ),))
