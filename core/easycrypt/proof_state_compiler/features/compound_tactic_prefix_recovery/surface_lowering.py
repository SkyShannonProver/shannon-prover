"""Lower one owned accepted-prefix result to a non-imperative diagnostic."""

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
from .analysis import COMPOUND_PREFIX_DIAGNOSTIC_PRODUCER_ID
from .ids import (
    COMPOUND_TACTIC_PREFIX_RECOVERY_FEATURE_ID,
    COMPOUND_TACTIC_PREFIX_RECOVERY_STRATEGY_CONTRACT,
)


def lower_compound_tactic_prefix_recovery(
    state: AnalyzedProofState,
    _invocation: CompilerInvocationContext,
) -> SurfaceContribution:
    attempted = state.attempted_operation
    if attempted is None or not state.recovery_ownership.owns(
        COMPOUND_TACTIC_PREFIX_RECOVERY_FEATURE_ID,
        attempted.recovery_key,
    ):
        return SurfaceContribution()
    diagnostics = attempt_diagnostics(
        state, COMPOUND_PREFIX_DIAGNOSTIC_PRODUCER_ID,
    )
    if len(diagnostics) != 1:
        return SurfaceContribution()
    return SurfaceContribution(diagnostics=(attempt_diagnostic_candidate(
        attempted,
        diagnostics[0],
        id_prefix="compound-prefix-diagnostic",
        feature_id=COMPOUND_TACTIC_PREFIX_RECOVERY_FEATURE_ID,
        strategy_contract=COMPOUND_TACTIC_PREFIX_RECOVERY_STRATEGY_CONTRACT,
    ),))
