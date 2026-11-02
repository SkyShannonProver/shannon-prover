"""Lower one owned relation realization to one certifiable action."""

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
from .analysis import RELATION_BRIDGE_CHOICE_PRODUCER_ID
from .ids import (
    RELATION_BRIDGE_REALIZATION_FEATURE_ID,
    RELATION_BRIDGE_REALIZATION_STRATEGY_CONTRACT,
)


def lower_relation_bridge_realization(
    state: AnalyzedProofState,
    _invocation: CompilerInvocationContext,
) -> SurfaceContribution:
    if (
        state.recovery_ownership.owner_feature_id
        != RELATION_BRIDGE_REALIZATION_FEATURE_ID
    ):
        return SurfaceContribution()
    attempted = state.attempted_operation
    diagnostics = attempt_diagnostics(state, RELATION_BRIDGE_CHOICE_PRODUCER_ID)
    realizations = owned_realizations(
        state, RELATION_BRIDGE_REALIZATION_FEATURE_ID,
    )
    if not realizations and len(diagnostics) == 1 and attempted is not None:
        return SurfaceContribution(diagnostics=(attempt_diagnostic_candidate(
            attempted,
            diagnostics[0],
            id_prefix="relation-bridge-choice",
            feature_id=RELATION_BRIDGE_REALIZATION_FEATURE_ID,
            strategy_contract=RELATION_BRIDGE_REALIZATION_STRATEGY_CONTRACT,
        ),))
    if len(realizations) != 1 or diagnostics:
        return SurfaceContribution()
    return SurfaceContribution(actions=(realization_action(
        realizations[0], RELATION_BRIDGE_REALIZATION_STRATEGY_CONTRACT,
    ),))
