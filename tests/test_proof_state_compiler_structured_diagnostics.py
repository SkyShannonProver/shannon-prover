"""Feature-neutral outcome matrix for the structured diagnostic framework."""

from __future__ import annotations

import hashlib
from dataclasses import replace

from core.easycrypt.proof_state_compiler.contracts import (
    APPLICATION_APPLICABLE,
    APPLICATION_INAPPLICABLE,
    APPLICATION_INDETERMINATE,
    CHOICE_REQUIRED,
    EXPLANATION_ONLY,
    EvidenceRef,
    MAX_INTERNAL_PRESENTATION_BYTES,
    NativePlanningBudget,
    NativeApplicationSlotDescriptor,
    NativeFormulaDescriptor,
    NativeInputArgument,
    NativeSemanticPlanningDecision,
    NativeSemanticPlanningReport,
    NativeSemanticPlanningStage,
    NativeSemanticRequest,
    NativeProofTermElaborationQuery,
    StateRef,
)
from core.easycrypt.proof_state_compiler.middle_end.application_applicability import (
    assess_current_state_application,
)
from core.easycrypt.proof_state_compiler.middle_end.diagnostics import (
    application_arguments_misaligned,
    structured_application_diagnostic,
)
from tests.proof_state_compiler_test_support import bare_native_observation


FEATURE_ID = "synthetic_application_consumer"
PRODUCER_ID = "synthetic_application_consumer.native"


def test_argument_alignment_gate_distinguishes_mismatch_from_inference() -> None:
    slots = (
        NativeApplicationSlotDescriptor(
            position=1,
            kind="proof",
            formula=NativeFormulaDescriptor(
                kind="true", text="true", type_text="bool"
            ),
        ),
        NativeApplicationSlotDescriptor(
            position=2,
            kind="module",
            name="O",
            type_text="Oracle",
        ),
    )

    assert application_arguments_misaligned(
        slots, (NativeInputArgument(1, "formula", False, "G2"),)
    )
    assert application_arguments_misaligned(
        slots,
        (
            NativeInputArgument(1, "proof", False),
            NativeInputArgument(2, "formula", False, "G2"),
        ),
    )
    assert not application_arguments_misaligned(
        slots, (NativeInputArgument(1, "proof", False),)
    )
    assert not application_arguments_misaligned(
        slots, (NativeInputArgument(1, "hole", True),)
    )


def _state_ref() -> StateRef:
    return StateRef(
        session_id="structured-diagnostic-session",
        state_version=3,
        committed_prefix_identity="prefix-structured-diagnostic",
        goal_identity_required=True,
        goal_identity="goal-structured-diagnostic",
    )


def _evidence(label: str = "base") -> EvidenceRef:
    return EvidenceRef(
        evidence_id=f"structured-diagnostic:{label}",
        source_kind="test_native_evidence",
        source_ref=f"test://structured-diagnostic/{label}",
        source_sha256=hashlib.sha256(label.encode()).hexdigest(),
    )


def _decision(
    disposition: str,
    *,
    proposed: int,
    reason: str = "",
) -> NativeSemanticPlanningDecision:
    return NativeSemanticPlanningDecision(
        feature_id=FEATURE_ID,
        producer_id=PRODUCER_ID,
        disposition=disposition,
        reason=reason,
        considered_candidate_count=max(proposed, 7),
        proposed_request_ids=tuple(
            f"application-request:{index}"
            for index in range(1, proposed + 1)
        ),
        unresolved_request_count=proposed,
        unresolved_execution_unit_count=proposed,
    )


def _report(decision: NativeSemanticPlanningDecision) -> NativeSemanticPlanningReport:
    budget = NativePlanningBudget()
    return NativeSemanticPlanningReport(
        state_ref=_state_ref(),
        stages=(NativeSemanticPlanningStage(
            state_ref=_state_ref(),
            stage="post_resource",
            budget_before=budget,
            budget_after=budget,
            decisions=(decision,),
            evidence_ref=_evidence("planning"),
        ),),
    )


def _request(index: int) -> NativeSemanticRequest:
    return NativeSemanticRequest(
        state_ref=_state_ref(),
        request_id=f"application-request:{index}",
        producer_id=PRODUCER_ID,
        query=NativeProofTermElaborationQuery(
            operation="apply",
            application_term=f"Selected.theorem Candidate{index}",
        ),
        evidence_refs=(_evidence("request"),),
    )


def _assessment(
    *,
    decision: NativeSemanticPlanningDecision | None,
    observations=(),
    matched=(),
    state_ref: StateRef | None = None,
):
    return assess_current_state_application(
        state_ref=state_ref or _state_ref(),
        operation="apply",
        selected_resource="Selected.theorem",
        planning_report=None if decision is None else _report(decision),
        native_observations=tuple(observations),
        feature_id=FEATURE_ID,
        native_producer_id=PRODUCER_ID,
        matched_request_ids=tuple(matched),
    )


def _diagnostic(
    applicability,
    *,
    phase_boundary_mismatch=("CurrentBoundary", "ResultBoundary"),
):
    return structured_application_diagnostic(
        producer_id="synthetic.analysis",
        trigger_id="trigger-1",
        operation="apply",
        selected_resource="Selected.theorem",
        native_failure_kind="cannot_infer_module",
        applicability=applicability,
        phase_boundary_mismatch=phase_boundary_mismatch,
        evidence_refs=(_evidence(),),
    )


def test_incomplete_search_is_indeterminate_and_hides_argument_shape() -> None:
    applicability = _assessment(
        decision=_decision(
            "abstained",
            proposed=9,
            reason="feature_complete_request_population_exceeds_native_budget",
        ),
    )
    diagnostic = _diagnostic(applicability)

    assert applicability.status == APPLICATION_INDETERMINATE
    assert not applicability.population_complete
    assert diagnostic is not None
    assert diagnostic.code == "application_applicability_indeterminate"
    assert diagnostic.applicability == EXPLANATION_ONLY
    assert diagnostic.placeholder_shape == ""
    assert diagnostic.identity_payload_bytes <= MAX_INTERNAL_PRESENTATION_BYTES
    assert diagnostic.primary == (
        "theorem is not applicable in the current proof state."
    )
    assert diagnostic.notes == (
        "EasyCrypt boundary mismatch: the checked goal uses CurrentBoundary; "
        "theorem uses ResultBoundary.",
    )
    payload_text = str(diagnostic.identity_payload())
    assert "Candidate" not in payload_text
    assert "9" not in payload_text
    assert "budget" not in payload_text
    assert "<module" not in payload_text


def test_indeterminate_diagnostic_abstains_without_native_boundaries() -> None:
    applicability = _assessment(
        decision=_decision(
            "abstained",
            proposed=9,
            reason="feature_complete_request_population_exceeds_native_budget",
        ),
    )

    assert _diagnostic(
        applicability, phase_boundary_mismatch=None
    ) is None


def test_complete_native_population_distinguishes_unique_ambiguous_and_zero() -> None:
    requests = (_request(1), _request(2))
    accepted_observations = tuple(
        bare_native_observation(request, resolved_head="Top.Selected.theorem")
        for request in requests
    )
    nonmatching_observations = tuple(
        replace(
            item,
            descriptor=replace(
                item.descriptor,
                result_convertible_to_current_goal=False,
            ),
        )
        for item in accepted_observations
    )
    decision = _decision("ready", proposed=2)

    unique = _assessment(
        decision=decision,
        observations=(accepted_observations[0], nonmatching_observations[1]),
        matched=(requests[0].request_id,),
    )
    ambiguous = _assessment(
        decision=decision,
        observations=accepted_observations,
        matched=tuple(item.request_id for item in requests),
    )
    zero = _assessment(
        decision=decision,
        observations=nonmatching_observations,
    )

    assert unique.status == APPLICATION_APPLICABLE
    assert unique.unique_checked_completion
    assert _diagnostic(unique) is None
    assert ambiguous.status == APPLICATION_APPLICABLE
    assert ambiguous.unique_selection_unestablished
    assert _diagnostic(ambiguous).applicability == CHOICE_REQUIRED
    assert zero.status == APPLICATION_INAPPLICABLE
    zero_diagnostic = _diagnostic(zero)
    assert zero_diagnostic.applicability == EXPLANATION_ONLY
    assert zero_diagnostic.placeholder_shape == ""


def test_no_planning_evidence_yields_no_assessment_or_diagnostic() -> None:
    applicability = _assessment(decision=None)

    assert applicability is None
    assert _diagnostic(applicability) is None


def test_partial_native_acceptance_proves_applicability_not_uniqueness() -> None:
    request = _request(1)
    observation = bare_native_observation(
        request, resolved_head="Top.Selected.theorem"
    )
    applicability = _assessment(
        decision=_decision("ready", proposed=2),
        observations=(observation,),
        matched=(request.request_id,),
    )

    assert applicability.status == APPLICATION_APPLICABLE
    assert not applicability.population_complete
    assert not applicability.unique_checked_completion
    diagnostic = _diagnostic(applicability)
    assert diagnostic.code == "application_completion_not_unique"
    assert diagnostic.placeholder_shape == ""


def test_population_completeness_requires_exact_planned_request_identity() -> None:
    planned = _request(1)
    unrelated_same_producer = _request(3)
    applicability = _assessment(
        decision=_decision("ready", proposed=2),
        observations=(
            bare_native_observation(
                planned, resolved_head="Top.Selected.theorem"
            ),
            bare_native_observation(
                unrelated_same_producer,
                resolved_head="Top.Selected.theorem",
            ),
        ),
        matched=(planned.request_id,),
    )

    assert applicability.status == APPLICATION_APPLICABLE
    assert not applicability.population_complete
    assert not applicability.unique_checked_completion
    assert applicability.accepted_request_ids == (planned.request_id,)
    assert unrelated_same_producer.request_id not in (
        applicability.nonmatching_request_ids
    )


def test_applicability_rejects_stale_state_ref() -> None:
    stale = StateRef(
        session_id="structured-diagnostic-session",
        state_version=4,
        committed_prefix_identity="prefix-structured-diagnostic",
        goal_identity_required=True,
        goal_identity="goal-stale",
    )

    try:
        _assessment(
            decision=_decision("ready", proposed=1),
            state_ref=stale,
        )
    except ValueError as exc:
        assert "StateRef" in str(exc)
    else:
        raise AssertionError("stale planning report was accepted")
