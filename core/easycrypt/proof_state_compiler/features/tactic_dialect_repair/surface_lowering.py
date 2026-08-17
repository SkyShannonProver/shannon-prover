"""Lower one owned eager-dialect result to one bounded surface item."""

from __future__ import annotations

import hashlib
import json

from core.easycrypt.proof_state_compiler.backend.surface_lowering import (
    SurfaceContribution,
)
from core.easycrypt.proof_state_compiler.contracts import (
    ActionCandidate,
    AnalyzedProofState,
    CompilerInvocationContext,
    CorrectionPresentation,
    DO_YOU_MEAN,
    DiagnosticCandidate,
    freeze_json_object,
)
from .analysis import TACTIC_DIALECT_REPAIR_ANALYSIS_PRODUCER_ID
from .feature import (
    TACTIC_DIALECT_REPAIR_FEATURE_ID,
    TACTIC_DIALECT_REPAIR_STRATEGY_CONTRACT,
)


def lower_tactic_dialect_repair(
    state: AnalyzedProofState,
    _invocation: CompilerInvocationContext,
) -> SurfaceContribution:
    ownership = state.recovery_ownership
    if ownership.owner_feature_id != TACTIC_DIALECT_REPAIR_FEATURE_ID:
        return SurfaceContribution()
    attempted = state.attempted_operation
    diagnostics = tuple(
        item
        for item in state.diagnostics
        if item.producer_id == TACTIC_DIALECT_REPAIR_ANALYSIS_PRODUCER_ID
        and attempted is not None
        and item.trigger_id == attempted.trigger_id
    )
    realizations = tuple(
        item
        for item in state.recovery_action_realizations
        if item.feature_id == TACTIC_DIALECT_REPAIR_FEATURE_ID
        and ownership.owns(item.feature_id, item.recovery_key)
        and ownership.preservation_witness == item.witness
    )
    if not realizations and len(diagnostics) == 1 and attempted is not None:
        diagnostic = diagnostics[0]
        material = json.dumps(
            diagnostic.identity_payload(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        candidate_id = "eager-dialect-diagnostic:" + hashlib.sha256(
            (attempted.recovery_key + "\0" + material).encode("utf-8")
        ).hexdigest()[:20]
        return SurfaceContribution(diagnostics=(DiagnosticCandidate(
            candidate_id=candidate_id,
            feature_id=TACTIC_DIALECT_REPAIR_FEATURE_ID,
            diagnostic=diagnostic,
            strategy_contract=TACTIC_DIALECT_REPAIR_STRATEGY_CONTRACT,
        ),))
    if len(realizations) != 1 or diagnostics:
        return SurfaceContribution()
    item = realizations[0]
    return SurfaceContribution(actions=(ActionCandidate(
        candidate_id=item.realization_id,
        feature_id=item.feature_id,
        intent="commit_tactic",
        payload=freeze_json_object({"tactic": item.exact_tactic}),
        unresolved_premises=(),
        certification_policy="exact_tactic_preflight",
        strategy_contract=TACTIC_DIALECT_REPAIR_STRATEGY_CONTRACT,
        evidence_refs=item.evidence_refs,
        trigger_id=item.trigger_id,
        recovery_witness_id=item.witness.witness_id,
        correction=CorrectionPresentation(
            presentation_kind=DO_YOU_MEAN,
            reason_code=item.reason_code,
            reason=item.reason,
        ),
    ),))
