"""Lower one owned accepted-prefix result to a non-imperative diagnostic."""

import hashlib
import json

from core.easycrypt.proof_state_compiler.backend.surface_lowering import (
    SurfaceContribution,
)
from core.easycrypt.proof_state_compiler.contracts import (
    AnalyzedProofState,
    CompilerInvocationContext,
    DiagnosticCandidate,
)
from .analysis import COMPOUND_PREFIX_DIAGNOSTIC_PRODUCER_ID
from .feature import (
    COMPOUND_TACTIC_PREFIX_RECOVERY_FEATURE_ID,
    COMPOUND_TACTIC_PREFIX_RECOVERY_STRATEGY_CONTRACT,
)


def lower_compound_tactic_prefix_recovery(
    state: AnalyzedProofState,
    _invocation: CompilerInvocationContext,
) -> SurfaceContribution:
    ownership = state.recovery_ownership
    if ownership.owner_feature_id != COMPOUND_TACTIC_PREFIX_RECOVERY_FEATURE_ID:
        return SurfaceContribution()
    attempted = state.attempted_operation
    if attempted is None or not ownership.owns(
        COMPOUND_TACTIC_PREFIX_RECOVERY_FEATURE_ID,
        attempted.recovery_key,
    ):
        return SurfaceContribution()
    diagnostics = tuple(
        item
        for item in state.diagnostics
        if item.producer_id == COMPOUND_PREFIX_DIAGNOSTIC_PRODUCER_ID
        and item.trigger_id == attempted.trigger_id
    )
    if len(diagnostics) != 1:
        return SurfaceContribution()
    diagnostic = diagnostics[0]
    material = json.dumps(
        diagnostic.identity_payload(),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    candidate_id = "compound-prefix-diagnostic:" + hashlib.sha256(
        (attempted.recovery_key + "\0" + material).encode("utf-8")
    ).hexdigest()[:20]
    return SurfaceContribution(diagnostics=(DiagnosticCandidate(
        candidate_id=candidate_id,
        feature_id=COMPOUND_TACTIC_PREFIX_RECOVERY_FEATURE_ID,
        diagnostic=diagnostic,
        strategy_contract=COMPOUND_TACTIC_PREFIX_RECOVERY_STRATEGY_CONTRACT,
    ),))
