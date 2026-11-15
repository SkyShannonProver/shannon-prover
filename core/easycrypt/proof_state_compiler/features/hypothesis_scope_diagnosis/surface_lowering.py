"""Lower one owned hypothesis-scope result to one bounded surface item."""

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
from .analysis import HYPOTHESIS_SCOPE_ANALYSIS_PRODUCER_ID
from .ids import (
    HYPOTHESIS_SCOPE_DIAGNOSIS_FEATURE_ID,
    HYPOTHESIS_SCOPE_FACT_STRATEGY_CONTRACT,
    HYPOTHESIS_SCOPE_SMT_HINT_STRATEGY_CONTRACT,
)


def lower_hypothesis_scope_diagnosis(
    state: AnalyzedProofState,
    _invocation: CompilerInvocationContext,
) -> SurfaceContribution:
    ownership = state.recovery_ownership
    if ownership.owner_feature_id != HYPOTHESIS_SCOPE_DIAGNOSIS_FEATURE_ID:
        return SurfaceContribution()
    attempted = state.attempted_operation
    diagnostics = attempt_diagnostics(
        state, HYPOTHESIS_SCOPE_ANALYSIS_PRODUCER_ID,
    )
    realizations = owned_realizations(
        state, HYPOTHESIS_SCOPE_DIAGNOSIS_FEATURE_ID,
    )
    # The analysis forms either the action or the explanation, never both.
    if not realizations and len(diagnostics) == 1 and attempted is not None:
        return SurfaceContribution(diagnostics=(attempt_diagnostic_candidate(
            attempted,
            diagnostics[0],
            id_prefix="hypothesis-scope-diagnostic",
            feature_id=HYPOTHESIS_SCOPE_DIAGNOSIS_FEATURE_ID,
            strategy_contract=HYPOTHESIS_SCOPE_FACT_STRATEGY_CONTRACT,
        ),))
    if len(realizations) != 1 or diagnostics:
        return SurfaceContribution()
    return SurfaceContribution(actions=(realization_action(
        realizations[0], HYPOTHESIS_SCOPE_SMT_HINT_STRATEGY_CONTRACT,
    ),))
