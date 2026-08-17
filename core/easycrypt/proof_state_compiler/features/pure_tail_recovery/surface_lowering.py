"""Lower one owned pure-tail repair to one certifiable action."""

from core.easycrypt.proof_state_compiler.backend.surface_lowering import (
    SurfaceContribution,
)
from core.easycrypt.proof_state_compiler.contracts import (
    ActionCandidate,
    AnalyzedProofState,
    CompilerInvocationContext,
    CorrectionPresentation,
    DO_YOU_MEAN,
    freeze_json_object,
)
from .feature import (
    PURE_TAIL_RECOVERY_FEATURE_ID,
    PURE_TAIL_RECOVERY_STRATEGY_CONTRACT,
)


def lower_pure_tail_recovery(
    state: AnalyzedProofState,
    _invocation: CompilerInvocationContext,
) -> SurfaceContribution:
    ownership = state.recovery_ownership
    if ownership.owner_feature_id != PURE_TAIL_RECOVERY_FEATURE_ID:
        return SurfaceContribution()
    realizations = tuple(
        item
        for item in state.recovery_action_realizations
        if item.feature_id == PURE_TAIL_RECOVERY_FEATURE_ID
        and ownership.owns(item.feature_id, item.recovery_key)
        and ownership.preservation_witness == item.witness
    )
    if len(realizations) != 1:
        return SurfaceContribution()
    item = realizations[0]
    return SurfaceContribution(actions=(ActionCandidate(
        candidate_id=item.realization_id,
        feature_id=item.feature_id,
        intent="commit_tactic",
        payload=freeze_json_object({"tactic": item.exact_tactic}),
        unresolved_premises=(),
        certification_policy="exact_tactic_preflight",
        strategy_contract=PURE_TAIL_RECOVERY_STRATEGY_CONTRACT,
        evidence_refs=item.evidence_refs,
        trigger_id=item.trigger_id,
        recovery_witness_id=item.witness.witness_id,
        correction=CorrectionPresentation(
            presentation_kind=DO_YOU_MEAN,
            reason_code=item.reason_code,
            reason=item.reason,
        ),
    ),))
