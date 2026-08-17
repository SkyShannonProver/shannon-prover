"""Order-independent ownership resolution for exact failure recovery."""

from __future__ import annotations

from core.easycrypt.proof_state_compiler.contracts.delivery import (
    CompilerInvocationContext,
)
from core.easycrypt.proof_state_compiler.contracts.failure import (
    RECOVERY_CONFLICT,
    RECOVERY_INCONSISTENT,
    RECOVERY_NOT_APPLICABLE,
    RECOVERY_OWNED,
    RECOVERY_UNCLAIMED,
    RecoveryClaim,
    RecoveryOwnership,
    native_tactic_prefix_witness,
)
from core.easycrypt.proof_state_compiler.contracts.proof_ir import ProofIR


def complete_recovery_claims(
    proof_ir: ProofIR,
    claims: tuple[RecoveryClaim, ...],
) -> tuple[RecoveryClaim, ...]:
    """Install the compound-boundary fallback only when no slice handled it.

    A typed suffix feature earns ownership by forming an action or diagnostic.
    When no feature does so, the native compound-boundary producer remains the
    sole owner of its factual accepted-prefix diagnostic.  This is semantic
    fallback, not catalog priority, and is therefore order independent.
    """

    attempted = proof_ir.attempted_operation
    handoff = None if attempted is None else attempted.recovery_handoff
    if claims or attempted is None or handoff is None:
        return claims
    return (RecoveryClaim(
        feature_id=handoff.source_feature_id,
        recovery_key=attempted.recovery_key,
        attempt_id=attempted.attempt_id,
        occurrence_identity=attempted.occurrence_identity,
        trigger_id=attempted.trigger_id,
        operation_family="compound_tactic",
        selected_resource="",
        resource_match_kind="none",
        allowed_output_kinds=("diagnostic",),
        preservation_witness=native_tactic_prefix_witness(
            rejected_tactic=handoff.source_rejected_tactic,
            exact_prefix_tactic=handoff.accepted_prefix_tactic,
        ),
        evidence_refs=attempted.evidence_refs,
    ),)


def resolve_recovery_ownership(
    proof_ir: ProofIR,
    invocation: CompilerInvocationContext,
    claims: tuple[RecoveryClaim, ...],
) -> RecoveryOwnership:
    """Resolve claims without feature priority or catalog-order semantics."""

    if invocation.failure_observation is None:
        if claims:
            return RecoveryOwnership(
                status=RECOVERY_INCONSISTENT,
                claimant_feature_ids=_claimants(claims),
                audit_reason="recovery_claim_without_current_failure",
            )
        return RecoveryOwnership(status=RECOVERY_NOT_APPLICABLE)

    attempted = proof_ir.attempted_operation
    if attempted is None:
        if claims:
            return RecoveryOwnership(
                status=RECOVERY_INCONSISTENT,
                claimant_feature_ids=_claimants(claims),
                audit_reason="recovery_claim_without_attempted_operation_ir",
            )
        return RecoveryOwnership(status=RECOVERY_UNCLAIMED)
    if not claims:
        return RecoveryOwnership(
            status=RECOVERY_UNCLAIMED,
            recovery_key=attempted.recovery_key,
        )

    expected = (
        attempted.recovery_key,
        attempted.attempt_id,
        attempted.occurrence_identity,
        attempted.trigger_id,
    )
    observed = tuple(
        (
            claim.recovery_key,
            claim.attempt_id,
            claim.occurrence_identity,
            claim.trigger_id,
        )
        for claim in claims
    )
    claimants = _claimants(claims)
    if any(identity != expected for identity in observed):
        return RecoveryOwnership(
            status=RECOVERY_INCONSISTENT,
            recovery_key=attempted.recovery_key,
            claimant_feature_ids=claimants,
            audit_reason="recovery_claim_identity_mismatch",
        )
    # One semantic slice gets one ownership claim.  Differing evidence does
    # not turn duplicate claims from the same feature into independent votes.
    if len(claims) != len(claimants):
        return RecoveryOwnership(
            status=RECOVERY_INCONSISTENT,
            recovery_key=attempted.recovery_key,
            claimant_feature_ids=claimants,
            audit_reason="duplicate_recovery_claim",
        )
    if len(claimants) != 1:
        return RecoveryOwnership(
            status=RECOVERY_CONFLICT,
            recovery_key=attempted.recovery_key,
            claimant_feature_ids=claimants,
            audit_reason="multiple_recovery_owners",
        )
    return RecoveryOwnership(
        status=RECOVERY_OWNED,
        recovery_key=attempted.recovery_key,
        owner_feature_id=claimants[0],
        claimant_feature_ids=claimants,
        operation_family=claims[0].operation_family,
        selected_resource=claims[0].selected_resource,
        resource_match_kind=claims[0].resource_match_kind,
        allowed_output_kinds=claims[0].allowed_output_kinds,
        preservation_witness=claims[0].preservation_witness,
    )


def _claimants(claims: tuple[RecoveryClaim, ...]) -> tuple[str, ...]:
    return tuple(sorted({claim.feature_id for claim in claims}))
