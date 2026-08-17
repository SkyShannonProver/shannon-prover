"""Own one native-established PHL transitivity boundary mismatch."""

from core.easycrypt.proof_state_compiler.contracts import (
    EXPLANATION_ONLY,
    CompilerInvocationContext,
    ProofCoordinate,
    ProofIR,
    RecoveryClaim,
    StructuredDiagnostic,
    exact_operation_resource_witness,
)
from core.easycrypt.proof_state_compiler.middle_end.contributions import (
    AnalysisContribution,
)
from core.easycrypt.proof_state_compiler.compound_boundary_text import (
    checked_goal_reference,
)
from .feature import PHL_TRANSITIVITY_BOUNDARY_REPAIR_FEATURE_ID


PHL_TRANSITIVITY_BOUNDARY_ANALYSIS_PRODUCER_ID = (
    "phl_transitivity_boundary_repair.analysis"
)


def analyze_phl_transitivity_boundary(
    proof_ir: ProofIR,
    _coordinate: ProofCoordinate,
    _invocation: CompilerInvocationContext,
) -> AnalysisContribution:
    attempted = proof_ir.attempted_operation
    descriptor = (
        None
        if attempted is None
        else attempted.phl_transitivity_boundary_descriptor
    )
    if (
        attempted is None
        or descriptor is None
        or attempted.native_diagnostic_status != "blocker"
        or attempted.native_failure_kind != descriptor.failure_kind
        or descriptor.source_operation != attempted.operation_family
    ):
        return AnalysisContribution()
    goal_context = checked_goal_reference(attempted.recovery_handoff)
    if descriptor.attempted_form == "function":
        primary = (
            "`transitivity F ...` is function-level and requires `equiv[F]`; "
            f"{goal_context} is statement-level `equiv[...]`."
        )
        help_text = (
            "Function-level transitivity belongs at an `equiv[F]` goal. At a "
            "statement goal, the corresponding forms are `transitivity{1} "
            "{ <statement> } ...` and `{2}`. Side and statement remain proof-"
            "strategy choices, so the compiler selected no correction."
        )
    else:
        primary = (
            "`transitivity{1/2} { ... }` is statement-level and requires "
            f"`equiv[statement]`; {goal_context} is `equiv[F]`."
        )
        help_text = (
            "Statement-level transitivity belongs after entering a procedure "
            "body. At an `equiv[F]` goal, the corresponding form is "
            "`transitivity F ...`. The intermediate function remains a proof-"
            "strategy choice, so the compiler selected no correction."
        )
    diagnostic = StructuredDiagnostic(
        producer_id=PHL_TRANSITIVITY_BOUNDARY_ANALYSIS_PRODUCER_ID,
        code="phl_boundary",
        primary=primary,
        notes=(),
        help=help_text,
        applicability=EXPLANATION_ONLY,
        evidence_refs=attempted.evidence_refs,
        trigger_id=attempted.trigger_id,
    )
    witness = exact_operation_resource_witness(
        attempted.operation_family,
        attempted.exact_resource,
    )
    claim = RecoveryClaim(
        feature_id=PHL_TRANSITIVITY_BOUNDARY_REPAIR_FEATURE_ID,
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
