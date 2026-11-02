"""P4 lowering shared by recovery slices that own one failed attempt.

A recovery slice that won ownership of the agent's failed tactic lowers
either its native realization to one certifiable ``Do you mean?`` action or
its diagnostic to one diagnostic candidate.  Each slice keeps its own
choice between the two and its own candidate-ID prefix; these helpers own
the ownership filters and candidate shapes so the slices cannot drift.
"""

from __future__ import annotations

from core.easycrypt.proof_state_compiler.contracts import (
    ActionCandidate,
    AnalyzedProofState,
    AttemptedOperationIR,
    CorrectionPresentation,
    DO_YOU_MEAN,
    DiagnosticCandidate,
    RecoveryActionRealization,
    StrategyContract,
    StructuredDiagnostic,
    freeze_json_object,
)
from core.easycrypt.proof_state_compiler.contracts.digest import (
    canonical_json,
    text_sha256,
)


EXACT_TACTIC_PREFLIGHT = "exact_tactic_preflight"


def owned_realizations(
    state: AnalyzedProofState,
    feature_id: str,
) -> tuple[RecoveryActionRealization, ...]:
    """The slice's realizations that ownership and its witness both admit."""

    ownership = state.recovery_ownership
    return tuple(
        item
        for item in state.recovery_action_realizations
        if item.feature_id == feature_id
        and ownership.owns(item.feature_id, item.recovery_key)
        and ownership.preservation_witness == item.witness
    )


def attempt_diagnostics(
    state: AnalyzedProofState,
    producer_id: str,
) -> tuple[StructuredDiagnostic, ...]:
    """The producer's diagnostics bound to the current failed attempt."""

    attempted = state.attempted_operation
    if attempted is None:
        return ()
    return tuple(
        item
        for item in state.diagnostics
        if item.producer_id == producer_id
        and item.trigger_id == attempted.trigger_id
    )


def realization_action(
    item: RecoveryActionRealization,
    strategy_contract: StrategyContract,
) -> ActionCandidate:
    """One exact-preflight ``Do you mean?`` action for an owned realization."""

    return ActionCandidate(
        candidate_id=item.realization_id,
        feature_id=item.feature_id,
        intent="commit_tactic",
        payload=freeze_json_object({"tactic": item.exact_tactic}),
        unresolved_premises=(),
        certification_policy=EXACT_TACTIC_PREFLIGHT,
        strategy_contract=strategy_contract,
        evidence_refs=item.evidence_refs,
        trigger_id=item.trigger_id,
        recovery_witness_id=item.witness.witness_id,
        correction=CorrectionPresentation(
            presentation_kind=DO_YOU_MEAN,
            reason_code=item.reason_code,
            reason=item.reason,
        ),
    )


def attempt_diagnostic_candidate(
    attempted: AttemptedOperationIR,
    diagnostic: StructuredDiagnostic,
    *,
    id_prefix: str,
    feature_id: str,
    strategy_contract: StrategyContract,
) -> DiagnosticCandidate:
    """One diagnostic candidate identified by the attempt and its content."""

    material = canonical_json(diagnostic.identity_payload())
    candidate_id = id_prefix + ":" + text_sha256(
        attempted.recovery_key
        + "\0"
        + material
    )[:20]
    return DiagnosticCandidate(
        candidate_id=candidate_id,
        feature_id=feature_id,
        diagnostic=diagnostic,
        strategy_contract=strategy_contract,
    )
