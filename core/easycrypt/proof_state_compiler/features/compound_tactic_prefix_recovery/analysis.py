"""Own one native-localized accepted prefix of a failed compound tactic."""

from __future__ import annotations

from core.easycrypt.proof_state_compiler.contracts import (
    CompilerInvocationContext,
    EvidenceRef,
    EXPLANATION_ONLY,
    NativeTacticPrefixDiagnosticDescriptor,
    ProofCoordinate,
    ProofIR,
    RecoveryClaim,
    StructuredDiagnostic,
    native_tactic_prefix_witness,
)
from core.easycrypt.proof_state_compiler.middle_end.contributions import (
    AnalysisContribution,
)
from core.easycrypt.proof_state_compiler.compound_boundary_text import (
    compound_boundary_continuation,
    compound_boundary_summary,
)
from .feature import COMPOUND_TACTIC_PREFIX_RECOVERY_FEATURE_ID
from .native_attempt import COMPOUND_PREFIX_NATIVE_PRODUCER_ID
from .syntax import (
    compound_accepted_prefix_extension,
    compound_prefix_candidates,
)


COMPOUND_PREFIX_DIAGNOSTIC_PRODUCER_ID = (
    "compound_tactic_prefix_recovery.accepted_prefix_diagnostic"
)


def analyze_compound_tactic_prefix_recovery(
    proof_ir: ProofIR,
    _coordinate: ProofCoordinate,
    _invocation: CompilerInvocationContext,
) -> AnalysisContribution:
    attempted = proof_ir.attempted_operation
    handoff = None if attempted is None else attempted.recovery_handoff
    if handoff is not None:
        if handoff.source_feature_id != COMPOUND_TACTIC_PREFIX_RECOVERY_FEATURE_ID:
            return AnalysisContribution()
        diagnostic = _compound_boundary_diagnostic(
            accepted_prefix=handoff.accepted_prefix_tactic,
            accepted_effect=handoff.accepted_prefix_effect,
            accepted_stage_count=handoff.accepted_prefix_stage_count,
            rejected_extension=handoff.derived_rejected_tactic,
            native_error=handoff.native_error_message,
            trigger_id=attempted.trigger_id,
            evidence_refs=attempted.evidence_refs,
        )
        # The source feature supplies a fallback fact, not a competing claim.
        # Shared ownership installs its claim only when no typed suffix feature
        # formed a concrete P3 action or diagnostic.
        return AnalysisContribution(
            diagnostics=() if diagnostic is None else (diagnostic,),
        )
    if (
        attempted is None
        or attempted.operation_family != "compound_tactic"
        or attempted.attempt_outcome_kind not in {"rejected", "no_progress"}
        or attempted.native_diagnostic_status != "blocker"
        or attempted.exact_resource
        or attempted.parsed_arguments
        or attempted.side
        or attempted.positions
    ):
        return AnalysisContribution()
    candidates = compound_prefix_candidates(attempted.rejected_tactic)
    matches = tuple(
        item.descriptor
        for item in proof_ir.native_semantic_observations
        if item.producer_id == COMPOUND_PREFIX_NATIVE_PRODUCER_ID
        and item.state_ref == attempted.state_ref
        and item.status == "accepted"
        and isinstance(item.descriptor, NativeTacticPrefixDiagnosticDescriptor)
        and item.descriptor.rejected_tactic == attempted.rejected_tactic
        and item.descriptor.candidate_prefixes == candidates
    )
    if len(matches) != 1:
        return AnalysisContribution()
    descriptor = matches[0]
    accepted = descriptor.accepted_prefixes
    if (
        not accepted
        or descriptor.native_failure_kind != attempted.native_failure_kind
        or accepted != candidates[:len(accepted)]
    ):
        return AnalysisContribution()
    accepted_prefix = accepted[-1]
    extension = compound_accepted_prefix_extension(
        attempted.rejected_tactic,
        accepted_prefix=accepted_prefix,
        candidate_prefixes=candidates,
    )
    if not extension:
        return AnalysisContribution()
    if descriptor.boundary_tactic != extension:
        return AnalysisContribution()
    accepted_effect = descriptor.prefix_effects[len(accepted) - 1]
    witness = native_tactic_prefix_witness(
        rejected_tactic=attempted.rejected_tactic,
        exact_prefix_tactic=accepted_prefix,
    )
    diagnostic = _compound_boundary_diagnostic(
        accepted_prefix=accepted_prefix,
        accepted_effect=accepted_effect,
        accepted_stage_count=len(accepted),
        rejected_extension=extension,
        native_error=descriptor.boundary_error_message,
        trigger_id=attempted.trigger_id,
        evidence_refs=attempted.evidence_refs,
    )
    if diagnostic is None:
        return AnalysisContribution()
    claim = RecoveryClaim(
        feature_id=COMPOUND_TACTIC_PREFIX_RECOVERY_FEATURE_ID,
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


def _compound_boundary_diagnostic(
    *,
    accepted_prefix: str,
    accepted_effect: str,
    accepted_stage_count: int,
    rejected_extension: str,
    native_error: str,
    trigger_id: str,
    evidence_refs: tuple[EvidenceRef, ...],
) -> StructuredDiagnostic | None:
    try:
        primary = (
            compound_boundary_summary(
                accepted_prefix=accepted_prefix,
                accepted_effect=accepted_effect,
                accepted_stage_count=accepted_stage_count,
                rejected_extension=rejected_extension,
                native_error=native_error,
            )
            + "\n\n"
            + compound_boundary_continuation(
                accepted_prefix=accepted_prefix,
                accepted_effect=accepted_effect,
                accepted_stage_count=accepted_stage_count,
            )
        )
        return StructuredDiagnostic(
            producer_id=COMPOUND_PREFIX_DIAGNOSTIC_PRODUCER_ID,
            code="compound_prefix_diagnostic",
            primary=primary,
            help="",
            notes=(),
            applicability=EXPLANATION_ONLY,
            evidence_refs=evidence_refs,
            trigger_id=trigger_id,
        )
    except ValueError:
        # A long source prefix/error does not fit the bounded agent surface.
        return None
