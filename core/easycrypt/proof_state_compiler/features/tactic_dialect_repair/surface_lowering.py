"""Lower one owned eager-dialect result to one bounded surface item."""

from __future__ import annotations

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
    owned_realizations,
    realization_action,
)
from .analysis import TACTIC_DIALECT_REPAIR_ANALYSIS_PRODUCER_ID
from .ids import (
    TACTIC_DIALECT_REPAIR_FEATURE_ID,
    TACTIC_DIALECT_REPAIR_STRATEGY_CONTRACT,
)


def lower_tactic_dialect_repair(
    state: AnalyzedProofState,
    _invocation: CompilerInvocationContext,
) -> SurfaceContribution:
    if state.recovery_ownership.owner_feature_id != TACTIC_DIALECT_REPAIR_FEATURE_ID:
        return SurfaceContribution()
    attempted = state.attempted_operation
    diagnostics = attempt_diagnostics(
        state, TACTIC_DIALECT_REPAIR_ANALYSIS_PRODUCER_ID,
    )
    realizations = owned_realizations(state, TACTIC_DIALECT_REPAIR_FEATURE_ID)
    if not realizations and len(diagnostics) == 1 and attempted is not None:
        return SurfaceContribution(diagnostics=(attempt_diagnostic_candidate(
            attempted,
            diagnostics[0],
            id_prefix="eager-dialect-diagnostic",
            feature_id=TACTIC_DIALECT_REPAIR_FEATURE_ID,
            strategy_contract=TACTIC_DIALECT_REPAIR_STRATEGY_CONTRACT,
        ),))
    if len(realizations) != 1 or diagnostics:
        return SurfaceContribution()
    return SurfaceContribution(actions=(realization_action(
        realizations[0], TACTIC_DIALECT_REPAIR_STRATEGY_CONTRACT,
    ),))
