"""P3 rendering for an already-established application assessment."""

from __future__ import annotations

from core.easycrypt.proof_state_compiler.contracts import (
    APPLICATION_INAPPLICABLE,
    APPLICATION_INDETERMINATE,
    CHOICE_REQUIRED,
    EXPLANATION_ONLY,
    ApplicationApplicability,
    EvidenceRef,
    RecoveryHandoff,
    StructuredDiagnostic,
)
from core.easycrypt.proof_state_compiler.compound_boundary_text import (
    checked_state_reference,
)


def structured_application_diagnostic(
    *,
    producer_id: str,
    trigger_id: str,
    operation: str,
    selected_resource: str,
    native_failure_kind: str,
    applicability: ApplicationApplicability | None,
    recovery_handoff: RecoveryHandoff | None = None,
    phase_boundary_mismatch: tuple[str, str] | None = None,
    evidence_refs: tuple[EvidenceRef, ...],
) -> StructuredDiagnostic | None:
    """Render only after the current-state applicability gate."""

    if applicability is None:
        return None
    combined_evidence = tuple(dict.fromkeys(
        evidence_refs + applicability.evidence_refs
    ))
    if not combined_evidence or applicability.unique_checked_completion:
        return None
    resource_label = selected_resource.rsplit(".", 1)[-1]
    operation_label = operation or "application"
    state_context = checked_state_reference(recovery_handoff)
    if applicability.status == APPLICATION_INDETERMINATE:
        if applicability.population_complete or phase_boundary_mismatch is None:
            return None
        current_boundary, result_boundary = phase_boundary_mismatch
        if not current_boundary or not result_boundary:
            return None
        return StructuredDiagnostic(
            producer_id=producer_id,
            code="application_applicability_indeterminate",
            primary=(
                f"{resource_label} is not applicable in {state_context}."
            ),
            notes=(
                "EasyCrypt boundary mismatch: the checked goal uses "
                f"{current_boundary}; theorem uses {result_boundary}.",
            ),
            help="",
            applicability=EXPLANATION_ONLY,
            evidence_refs=combined_evidence,
            trigger_id=trigger_id,
        )
    if applicability.unique_selection_unestablished:
        return StructuredDiagnostic(
            producer_id=producer_id,
            code="application_completion_not_unique",
            primary=(
                "EasyCrypt established applicability for selected "
                f"{resource_label}, but not one unique checked completion."
            ),
            notes=(),
            help="Choose the arguments that fit the proof route you want to pursue.",
            applicability=CHOICE_REQUIRED,
            evidence_refs=combined_evidence,
            trigger_id=trigger_id,
        )
    if applicability.status == APPLICATION_INAPPLICABLE:
        return StructuredDiagnostic(
            producer_id=producer_id,
            code="application_not_applicable_in_current_state",
            primary=(
                "The compiler did not establish a checked "
                f"{resource_label} {operation_label} from its complete bounded "
                f"candidate set in {state_context}."
            ),
            notes=((
                "The native blocker was "
                + native_failure_kind.replace("_", " ")
                + "."
            ),) if native_failure_kind else (),
            help="",
            applicability=EXPLANATION_ONLY,
            evidence_refs=combined_evidence,
            trigger_id=trigger_id,
        )
    return None
