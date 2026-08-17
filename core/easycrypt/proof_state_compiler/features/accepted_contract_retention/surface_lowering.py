"""Lower one exact accepted-contract loss to a commitment result."""

from __future__ import annotations

import hashlib

from core.easycrypt.proof_state_compiler.backend.surface_lowering import (
    SurfaceContribution,
)
from core.easycrypt.proof_state_compiler.contracts import (
    AnalyzedProofState,
    CompilerInvocationContext,
    DiagnosticCandidate,
)
from core.easycrypt.proof_state_compiler.features.accepted_contract_retention.analysis import (
    ACCEPTED_CONTRACT_RETENTION_PRODUCER_ID,
)
from core.easycrypt.proof_state_compiler.features.accepted_contract_retention.feature import (
    ACCEPTED_CONTRACT_RETENTION_FEATURE_ID,
    ACCEPTED_CONTRACT_RETENTION_STRATEGY_CONTRACT,
)


def lower_accepted_contract_retention(
    state: AnalyzedProofState,
    _invocation: CompilerInvocationContext,
) -> SurfaceContribution:
    matches = tuple(
        item for item in state.diagnostics
        if item.producer_id == ACCEPTED_CONTRACT_RETENTION_PRODUCER_ID
    )
    if len(matches) != 1 or not matches[0].trigger_id:
        return SurfaceContribution()
    item = matches[0]
    digest = hashlib.sha256(
        f"{item.trigger_id}\0{item.primary}".encode("utf-8")
    ).hexdigest()[:20]
    return SurfaceContribution(diagnostics=(DiagnosticCandidate(
        candidate_id=f"accepted-contract-retention:{digest}",
        feature_id=ACCEPTED_CONTRACT_RETENTION_FEATURE_ID,
        diagnostic=item,
        strategy_contract=ACCEPTED_CONTRACT_RETENTION_STRATEGY_CONTRACT,
    ),))
