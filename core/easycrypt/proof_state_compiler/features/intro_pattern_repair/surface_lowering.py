"""Lower one owned intro-pattern repair to one certifiable action."""

from core.easycrypt.proof_state_compiler.backend.surface_lowering import (
    SurfaceContribution,
)
from core.easycrypt.proof_state_compiler.contracts import (
    AnalyzedProofState,
    CompilerInvocationContext,
)
from core.easycrypt.proof_state_compiler.features.recovery_lowering import (
    owned_realizations,
    realization_action,
)
from .ids import (
    INTRO_PATTERN_REPAIR_FEATURE_ID,
    INTRO_PATTERN_REPAIR_STRATEGY_CONTRACT,
)


def lower_intro_pattern_repair(
    state: AnalyzedProofState,
    _invocation: CompilerInvocationContext,
) -> SurfaceContribution:
    # Only the resolved owner's realizations survive this filter.
    realizations = owned_realizations(state, INTRO_PATTERN_REPAIR_FEATURE_ID)
    if len(realizations) != 1:
        return SurfaceContribution()
    return SurfaceContribution(actions=(realization_action(
        realizations[0], INTRO_PATTERN_REPAIR_STRATEGY_CONTRACT,
    ),))
