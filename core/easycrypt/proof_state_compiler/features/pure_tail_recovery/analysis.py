"""Own one unique native target repair for an agent-selected rewrite."""

from __future__ import annotations

import hashlib

from core.easycrypt.proof_state_compiler.contracts import (
    CompilerInvocationContext,
    ProofCoordinate,
    ProofIR,
    RecoveryActionRealization,
    RecoveryClaim,
    exact_operation_resource_witness,
)
from core.easycrypt.proof_state_compiler.middle_end.contributions import (
    AnalysisContribution,
)
from core.easycrypt.proof_state_compiler.compound_boundary_text import (
    checked_goal_reference,
)
from .feature import PURE_TAIL_RECOVERY_FEATURE_ID


def analyze_pure_tail_recovery(
    proof_ir: ProofIR,
    _coordinate: ProofCoordinate,
    _invocation: CompilerInvocationContext,
) -> AnalysisContribution:
    attempted = proof_ir.attempted_operation
    descriptor = (
        None if attempted is None else attempted.pure_tail_rewrite_descriptor
    )
    if (
        attempted is None
        or descriptor is None
        or attempted.operation_family != "rewrite"
        or attempted.exact_resource != descriptor.selected_resource
        or attempted.native_diagnostic_status != "blocker"
        or attempted.native_failure_kind != descriptor.failure_kind
        or descriptor.source_operation != attempted.operation_family
        or descriptor.target_kind != "hypothesis"
        or descriptor.accepted_target_count != 1
    ):
        return AnalysisContribution()
    expected_tactic = (
        f"rewrite {attempted.exact_resource} in {descriptor.target_name}."
    )
    if descriptor.candidate_tactic != expected_tactic:
        return AnalysisContribution()
    witness = exact_operation_resource_witness(
        attempted.operation_family,
        attempted.exact_resource,
    )
    realization_id = "pure-tail-rewrite-target:" + hashlib.sha256(
        (attempted.recovery_key + "\0" + descriptor.target_name).encode("utf-8")
    ).hexdigest()[:20]
    goal_context = checked_goal_reference(attempted.recovery_handoff)
    reason = (
        f"The selected rewrite `{attempted.exact_resource}` does not match the "
        f"conclusion of {goal_context}. EasyCrypt found exactly one hypothesis "
        f"in {goal_context} "
        f"where the same left-to-right rewrite applies: `{descriptor.target_name}`."
    )
    realization = RecoveryActionRealization(
        realization_id=realization_id,
        feature_id=PURE_TAIL_RECOVERY_FEATURE_ID,
        recovery_key=attempted.recovery_key,
        trigger_id=attempted.trigger_id,
        witness=witness,
        exact_tactic=descriptor.candidate_tactic,
        reason_code=descriptor.failure_kind,
        reason=reason,
        evidence_refs=attempted.evidence_refs,
    )
    claim = RecoveryClaim(
        feature_id=PURE_TAIL_RECOVERY_FEATURE_ID,
        recovery_key=attempted.recovery_key,
        attempt_id=attempted.attempt_id,
        occurrence_identity=attempted.occurrence_identity,
        trigger_id=attempted.trigger_id,
        operation_family=attempted.operation_family,
        selected_resource=attempted.exact_resource,
        resource_match_kind="exact",
        allowed_output_kinds=("action",),
        preservation_witness=witness,
        evidence_refs=attempted.evidence_refs,
    )
    return AnalysisContribution(
        recovery_action_realizations=(realization,),
        recovery_claims=(claim,),
    )
