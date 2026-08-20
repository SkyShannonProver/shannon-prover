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
            "EasyCrypt rejected the selected function-level transitivity "
            f"because {goal_context} is statement-level `equiv[...]`."
        )
        help_text = (
            "You may remain at this statement boundary and continue the "
            "statement proof, using `transitivity{1}` or `{2}` if that fits "
            "your intended route.\n\n"
            "Alternatively, if you intended function-level transitivity, you "
            "may return to an `equiv[F]` boundary before applying it.\n\n"
            "Both are proof-strategy choices. The compiler selected neither."
        )
    else:
        primary = (
            "EasyCrypt rejected the selected statement-level transitivity "
            f"because {goal_context} is function-level `equiv[F]`."
        )
        help_text = (
            "You may remain at this function boundary and continue the "
            "function proof, using `transitivity F ...` if that fits your "
            "intended route.\n\n"
            "Alternatively, if you intended statement-level transitivity, you "
            "may enter a statement-level `equiv[...]` boundary before using "
            "`transitivity{1}` or `{2}`.\n\n"
            "Both are proof-strategy choices. The compiler selected neither."
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
