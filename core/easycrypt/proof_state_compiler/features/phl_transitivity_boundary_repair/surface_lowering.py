"""Lower the uniquely owned PHL boundary diagnosis to one surface item."""

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
from .analysis import PHL_TRANSITIVITY_BOUNDARY_ANALYSIS_PRODUCER_ID
from .feature import (
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
    diagnostics = tuple(
        item
        for item in state.diagnostics
        if item.producer_id == PHL_TRANSITIVITY_BOUNDARY_ANALYSIS_PRODUCER_ID
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
    candidate_id = "phl-boundary-diagnostic:" + hashlib.sha256(
        (attempted.recovery_key + "\0" + material).encode("utf-8")
    ).hexdigest()[:20]
    return SurfaceContribution(diagnostics=(DiagnosticCandidate(
        candidate_id=candidate_id,
        feature_id=PHL_TRANSITIVITY_BOUNDARY_REPAIR_FEATURE_ID,
        diagnostic=diagnostic,
        strategy_contract=PHL_TRANSITIVITY_BOUNDARY_REPAIR_STRATEGY_CONTRACT,
    ),))
