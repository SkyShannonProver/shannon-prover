"""Own one native-unique realization of a selected destruct commitment."""

from __future__ import annotations

import hashlib

from core.easycrypt.proof_state_compiler.contracts import (
    CompilerInvocationContext,
    ProofCoordinate,
    ProofIR,
    RecoveryActionRealization,
    RecoveryClaim,
    native_argument_realization_witness,
)
from core.easycrypt.proof_state_compiler.middle_end.contributions import (
    AnalysisContribution,
)
from .feature import INTRO_PATTERN_REPAIR_FEATURE_ID


def analyze_intro_pattern_repair(
    proof_ir: ProofIR,
    _coordinate: ProofCoordinate,
    _invocation: CompilerInvocationContext,
) -> AnalysisContribution:
    attempted = proof_ir.attempted_operation
    descriptor = (
        None
        if attempted is None
        else attempted.intro_pattern_realization_descriptor
    )
    if (
        attempted is None
        or descriptor is None
        or attempted.operation_family != "intro_pattern"
        or attempted.exact_resource
        or attempted.native_diagnostic_status != "blocker"
        or attempted.native_failure_kind != descriptor.failure_kind
        or descriptor.source_operation != attempted.operation_family
        or descriptor.attempted_pattern_kind != "nested_case"
        or descriptor.selected_pattern_count != 1
    ):
        return AnalysisContribution()
    committed_binders = "\0".join(descriptor.binder_names)
    witness = native_argument_realization_witness(
        source_operation_family="intro_pattern",
        target_operation_family=descriptor.surface_operation,
        committed_argument=committed_binders,
        native_family="deep_flatten_intro_pattern",
        exact_tactic=descriptor.candidate_tactic,
    )
    realization_id = "intro-pattern-repair:" + hashlib.sha256(
        (attempted.recovery_key + "\0" + committed_binders).encode("utf-8")
    ).hexdigest()[:20]
    reason = (
        "EasyCrypt accepts the same destruct and ordered binders in "
        "deep-flatten form; no binder or proof step changes."
    )
    realization = RecoveryActionRealization(
        realization_id=realization_id,
        feature_id=INTRO_PATTERN_REPAIR_FEATURE_ID,
        recovery_key=attempted.recovery_key,
        trigger_id=attempted.trigger_id,
        witness=witness,
        exact_tactic=descriptor.candidate_tactic,
        reason_code=descriptor.failure_kind,
        reason=reason,
        evidence_refs=attempted.evidence_refs,
    )
    claim = RecoveryClaim(
        feature_id=INTRO_PATTERN_REPAIR_FEATURE_ID,
        recovery_key=attempted.recovery_key,
        attempt_id=attempted.attempt_id,
        occurrence_identity=attempted.occurrence_identity,
        trigger_id=attempted.trigger_id,
        operation_family=attempted.operation_family,
        selected_resource="",
        resource_match_kind="none",
        allowed_output_kinds=("action",),
        preservation_witness=witness,
        evidence_refs=attempted.evidence_refs,
    )
    return AnalysisContribution(
        recovery_action_realizations=(realization,),
        recovery_claims=(claim,),
    )
