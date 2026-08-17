"""Own one native-established selected eager-while dialect failure."""

from __future__ import annotations

import hashlib

from core.easycrypt.proof_state_compiler.contracts import (
    CHOICE_REQUIRED,
    EXPLANATION_ONLY,
    HAS_PLACEHOLDERS,
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
from .feature import TACTIC_DIALECT_REPAIR_FEATURE_ID


TACTIC_DIALECT_REPAIR_ANALYSIS_PRODUCER_ID = (
    "tactic_dialect_repair.eager_while.analysis"
)

_DIALECT_PRIMARY = (
    "`eager while` takes only an invariant formula here; the written "
    "`H : left ~ right : pre ==> post` contract is not this tactic's syntax."
)
_PLACEHOLDER = "eager while (<invariant>)."


def _claim(attempted, *, output_kind: str, witness) -> RecoveryClaim:
    return RecoveryClaim(
        feature_id=TACTIC_DIALECT_REPAIR_FEATURE_ID,
        recovery_key=attempted.recovery_key,
        attempt_id=attempted.attempt_id,
        occurrence_identity=attempted.occurrence_identity,
        trigger_id=attempted.trigger_id,
        operation_family=attempted.operation_family,
        selected_resource="",
        resource_match_kind="none",
        allowed_output_kinds=(output_kind,),
        preservation_witness=witness,
        evidence_refs=attempted.evidence_refs,
    )


def _placeholder_diagnostic(attempted) -> AnalysisContribution:
    goal_context = checked_goal_reference(attempted.recovery_handoff)
    help_text = (
        "Supply the invariant you intend for the failing stage in "
        f"{goal_context}; the compiler did not choose it."
        if attempted.recovery_handoff is not None
        else "Keep the eager route and supply the invariant you intended."
    )
    diagnostic = StructuredDiagnostic(
        producer_id=TACTIC_DIALECT_REPAIR_ANALYSIS_PRODUCER_ID,
        code="eager_while_dialect",
        primary=_DIALECT_PRIMARY,
        notes=(),
        help=help_text,
        applicability=HAS_PLACEHOLDERS,
        placeholder_shape=_PLACEHOLDER,
        evidence_refs=attempted.evidence_refs,
        trigger_id=attempted.trigger_id,
    )
    witness = exact_operation_resource_witness("eager", "")
    return AnalysisContribution(
        diagnostics=(diagnostic,),
        recovery_claims=(_claim(
            attempted, output_kind="diagnostic", witness=witness
        ),),
    )


def _choice_diagnostic(attempted, candidates) -> AnalysisContribution:
    help_text = (
        "EasyCrypt checked these exact invariant alternatives for the failing "
        "stage. Which invariant do you mean?\n"
        + "\n".join(f"- `{item.candidate_tactic}`" for item in candidates)
        + "\nChoose one only if it fits the proof route you want; the compiler "
        "selected none."
    )
    try:
        diagnostic = StructuredDiagnostic(
            producer_id=TACTIC_DIALECT_REPAIR_ANALYSIS_PRODUCER_ID,
            code="eager_while_invariant_choice",
            primary=_DIALECT_PRIMARY,
            notes=(),
            help=help_text,
            applicability=CHOICE_REQUIRED,
            evidence_refs=attempted.evidence_refs,
            trigger_id=attempted.trigger_id,
        )
    except ValueError:
        return _placeholder_diagnostic(attempted)
    witness = exact_operation_resource_witness("eager", "")
    return AnalysisContribution(
        diagnostics=(diagnostic,),
        recovery_claims=(_claim(
            attempted, output_kind="diagnostic", witness=witness
        ),),
    )


def analyze_eager_while_dialect(
    proof_ir: ProofIR,
    _coordinate: ProofCoordinate,
    _invocation: CompilerInvocationContext,
) -> AnalysisContribution:
    attempted = proof_ir.attempted_operation
    descriptor = (
        None if attempted is None else attempted.eager_while_dialect_descriptor
    )
    if (
        attempted is None
        or descriptor is None
        or attempted.operation_family != "eager"
        or descriptor.source_operation != attempted.operation_family
        or descriptor.eager_subform != "while"
        or attempted.native_diagnostic_status != "blocker"
        or attempted.native_failure_kind != descriptor.failure_kind
    ):
        return AnalysisContribution()
    if descriptor.failure_kind == "eager_while_guard_mismatch":
        goal_context = checked_goal_reference(attempted.recovery_handoff)
        diagnostic = StructuredDiagnostic(
            producer_id=TACTIC_DIALECT_REPAIR_ANALYSIS_PRODUCER_ID,
            code="eager_while_guard_mismatch",
            primary=(
                "The selected `eager while` form is valid syntax, but "
                f"EasyCrypt requires both while guards in {goal_context} to be "
                "syntactically equal."
            ),
            notes=(),
            help=(
                "The same eager operation can apply only after those guards "
                "are syntactically equal."
            ),
            applicability=EXPLANATION_ONLY,
            evidence_refs=attempted.evidence_refs,
            trigger_id=attempted.trigger_id,
        )
        witness = exact_operation_resource_witness("eager", "")
        return AnalysisContribution(
            diagnostics=(diagnostic,),
            recovery_claims=(_claim(
                attempted, output_kind="diagnostic", witness=witness
            ),),
        )
    candidates = descriptor.candidates
    if len(candidates) == 0:
        return _placeholder_diagnostic(attempted)
    if len(candidates) > 1:
        return _choice_diagnostic(attempted, candidates)
    candidate = candidates[0]
    witness = native_argument_realization_witness(
        source_operation_family="eager",
        target_operation_family="eager",
        committed_argument=candidate.invariant_text,
        native_family="eager_while_invariant",
        exact_tactic=candidate.candidate_tactic,
    )
    realization_id = "eager-while-dialect-realization:" + hashlib.sha256(
        (attempted.recovery_key + "\0" + witness.witness_id).encode("utf-8")
    ).hexdigest()[:20]
    realization = RecoveryActionRealization(
        realization_id=realization_id,
        feature_id=TACTIC_DIALECT_REPAIR_FEATURE_ID,
        recovery_key=attempted.recovery_key,
        trigger_id=attempted.trigger_id,
        witness=witness,
        exact_tactic=candidate.candidate_tactic,
        reason_code="eager_while_dialect_mismatch",
        reason=(
            "`eager while` takes only an invariant formula. This action "
            "preserves the one submitted invariant that EasyCrypt accepted "
            f"for {checked_goal_reference(attempted.recovery_handoff)}."
        ),
        evidence_refs=attempted.evidence_refs,
    )
    return AnalysisContribution(
        recovery_action_realizations=(realization,),
        recovery_claims=(_claim(
            attempted, output_kind="action", witness=witness
        ),),
    )
