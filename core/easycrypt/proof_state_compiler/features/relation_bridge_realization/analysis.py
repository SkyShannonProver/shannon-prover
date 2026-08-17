"""P3 ownership and realization of one native relation-bridge descriptor."""

from __future__ import annotations

import hashlib

from core.easycrypt.proof_state_compiler.contracts import (
    CHOICE_REQUIRED,
    CompilerInvocationContext,
    ProofCoordinate,
    ProofIR,
    RecoveryActionRealization,
    RecoveryClaim,
    StructuredDiagnostic,
    exact_operation_resource_witness,
    native_argument_realization_witness,
)
from core.easycrypt.proof_state_compiler.middle_end.contributions import (
    AnalysisContribution,
)
from core.easycrypt.proof_state_compiler.compound_boundary_text import (
    checked_goal_reference,
)
from .feature import RELATION_BRIDGE_REALIZATION_FEATURE_ID


_REASONS = {
    ("real_le", "formula_transitivity_surface_mismatch"): (
        "Formula-level transitivity applies to equality, not this real <= goal. "
        "The intermediate you supplied is preserved; ler_trans realizes the "
        "same inequality bridge."
    ),
    ("real_le", "change_target_not_convertible"): (
        "`change` can only replace {goal} with a definitionally "
        "convertible formula. This target is not convertible; the intermediate "
        "you supplied is preserved and ler_trans introduces it as a bridge."
    ),
    ("int_le", "formula_transitivity_surface_mismatch"): (
        "Formula-level transitivity applies to equality, not this int <= goal. "
        "The intermediate you supplied is preserved; Int.lez_trans realizes "
        "the same integer inequality bridge."
    ),
}

_CHOICE_PRODUCER_ID = "relation_bridge_realization.choice_analysis"


def _strict_relation_choice(
    attempted,
) -> AnalysisContribution:
    descriptor = attempted.relation_bridge_choice_descriptor
    if (
        descriptor is None
        or attempted.native_diagnostic_status != "blocker"
        or attempted.native_failure_kind != descriptor.failure_kind
        or descriptor.source_operation != attempted.operation_family
        or descriptor.relation_family != "real_lt"
    ):
        return AnalysisContribution()
    goal_context = checked_goal_reference(attempted.recovery_handoff)
    primary = (
        f"`transitivity {descriptor.intermediate_text}` is formula-level "
        f"equality transitivity, but {goal_context} is a real strict "
        f"inequality `{descriptor.goal_left_text} < "
        f"{descriptor.goal_right_text}`."
    )
    help_text = (
        "EasyCrypt checked these exact bridge alternatives for the failing "
        "stage. Which bridge do you mean?\n"
        + "\n".join(
            (
                f"- `{item.candidate_tactic}`: "
                f"`{descriptor.goal_left_text} {item.left_relation} "
                f"{descriptor.intermediate_text}`, "
                f"`{descriptor.intermediate_text} {item.right_relation} "
                f"{descriptor.goal_right_text}`"
            )
            for item in descriptor.choices
        )
        + "\nChoose one only if it fits the proof route you want; the compiler "
        "selected none."
    )
    try:
        diagnostic = StructuredDiagnostic(
            producer_id=_CHOICE_PRODUCER_ID,
            code="real_lt_choice",
            primary=primary,
            notes=(),
            help=help_text,
            applicability=CHOICE_REQUIRED,
            evidence_refs=attempted.evidence_refs,
            trigger_id=attempted.trigger_id,
        )
    except ValueError:
        # The bounded surface never truncates exact tactics or native terms.
        return AnalysisContribution()
    witness = exact_operation_resource_witness(
        attempted.operation_family,
        "",
    )
    claim = RecoveryClaim(
        feature_id=RELATION_BRIDGE_REALIZATION_FEATURE_ID,
        recovery_key=attempted.recovery_key,
        attempt_id=attempted.attempt_id,
        occurrence_identity=attempted.occurrence_identity,
        trigger_id=attempted.trigger_id,
        operation_family=attempted.operation_family,
        selected_resource="",
        resource_match_kind="none",
        allowed_output_kinds=("diagnostic",),
        preservation_witness=witness,
        evidence_refs=attempted.evidence_refs,
    )
    return AnalysisContribution(
        diagnostics=(diagnostic,),
        recovery_claims=(claim,),
    )


def analyze_relation_bridge_realization(
    proof_ir: ProofIR,
    _coordinate: ProofCoordinate,
    _invocation: CompilerInvocationContext,
) -> AnalysisContribution:
    attempted = proof_ir.attempted_operation
    if attempted is not None and (
        attempted.relation_bridge_choice_descriptor is not None
    ):
        return _strict_relation_choice(attempted)
    bridge = (
        None if attempted is None else attempted.relation_bridge_descriptor
    )
    if (
        attempted is None
        or bridge is None
        or attempted.native_diagnostic_status != "blocker"
        or attempted.native_failure_kind != bridge.failure_kind
        or bridge.relation_family not in {"real_le", "int_le"}
        or bridge.source_operation != attempted.operation_family
        or (bridge.relation_family, bridge.failure_kind) not in _REASONS
    ):
        return AnalysisContribution()
    certificate_family = {
        "real_le": "ler_trans",
        "int_le": "Int.lez_trans",
    }[bridge.relation_family]
    expected_tactic = (
        f"apply ({certificate_family} {bridge.intermediate_text}); first last."
    )
    if bridge.candidate_tactic != expected_tactic:
        return AnalysisContribution()
    witness = native_argument_realization_witness(
        source_operation_family=attempted.operation_family,
        target_operation_family="apply",
        committed_argument=bridge.intermediate_text,
        native_family=bridge.relation_family,
        exact_tactic=bridge.candidate_tactic,
    )
    realization_id = "relation-bridge-realization:" + hashlib.sha256(
        (attempted.recovery_key + "\0" + witness.witness_id).encode("utf-8")
    ).hexdigest()[:20]
    reason = _REASONS[(bridge.relation_family, bridge.failure_kind)]
    if "{goal}" in reason:
        reason = reason.format(
            goal=checked_goal_reference(attempted.recovery_handoff)
        )
    realization = RecoveryActionRealization(
        realization_id=realization_id,
        feature_id=RELATION_BRIDGE_REALIZATION_FEATURE_ID,
        recovery_key=attempted.recovery_key,
        trigger_id=attempted.trigger_id,
        witness=witness,
        exact_tactic=bridge.candidate_tactic,
        reason_code=bridge.failure_kind,
        reason=reason,
        evidence_refs=attempted.evidence_refs,
    )
    claim = RecoveryClaim(
        feature_id=RELATION_BRIDGE_REALIZATION_FEATURE_ID,
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
