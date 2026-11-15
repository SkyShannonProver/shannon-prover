"""Lower the uniquely owned smt-failure localization to one diagnostic."""

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
from .analysis import SMT_FAILURE_LOCALIZATION_PRODUCER_ID
from .ids import (
    SMT_FAILURE_LOCALIZATION_FEATURE_ID,
    SMT_FAILURE_LOCALIZATION_STRATEGY_CONTRACT,
)


def lower_smt_failure_localization(
    state: AnalyzedProofState,
    _invocation: CompilerInvocationContext,
) -> SurfaceContribution:
    attempted = state.attempted_operation
    if attempted is None or not state.recovery_ownership.owns(
        SMT_FAILURE_LOCALIZATION_FEATURE_ID,
        attempted.recovery_key,
    ):
        return SurfaceContribution()
    diagnostics = attempt_diagnostics(
        state, SMT_FAILURE_LOCALIZATION_PRODUCER_ID,
    )
    if len(diagnostics) != 1:
        return SurfaceContribution()
    return SurfaceContribution(diagnostics=(attempt_diagnostic_candidate(
        attempted,
        diagnostics[0],
        id_prefix="smt-failure-localization",
        feature_id=SMT_FAILURE_LOCALIZATION_FEATURE_ID,
        strategy_contract=SMT_FAILURE_LOCALIZATION_STRATEGY_CONTRACT,
    ),))
