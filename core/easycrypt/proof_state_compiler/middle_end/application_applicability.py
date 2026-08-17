"""P3 current-state applicability over exact native request populations.

This analysis is feature-neutral and presentation-free.  It joins the exact
planned request identity set with EasyCrypt observations for one ``StateRef``.
Argument repair may consume the result only after applicability is established.
"""

from __future__ import annotations

from core.easycrypt.proof_state_compiler.contracts import (
    APPLICATION_APPLICABLE,
    APPLICATION_INAPPLICABLE,
    APPLICATION_INDETERMINATE,
    ApplicationApplicability,
    EvidenceRef,
    NativeProofTermDescriptor,
    NativeSemanticObservation,
    NativeSemanticPlanningReport,
    StateRef,
)
from core.easycrypt.proof_state_compiler.contracts.native_semantics import (
    NATIVE_PRODUCTION_ABSTAINED,
    NATIVE_PRODUCTION_READY,
)


def assess_current_state_application(
    *,
    state_ref: StateRef,
    operation: str,
    selected_resource: str,
    planning_report: NativeSemanticPlanningReport | None,
    native_observations: tuple[NativeSemanticObservation, ...],
    feature_id: str,
    native_producer_id: str,
    matched_request_ids: tuple[str, ...],
) -> ApplicationApplicability | None:
    """Establish applicability before any argument-repair presentation."""

    producer_observations = tuple(
        item
        for item in native_observations
        if item.producer_id == native_producer_id
    )
    if any(item.state_ref != state_ref for item in producer_observations):
        raise ValueError("application applicability crossed StateRef")
    if planning_report is not None and planning_report.state_ref != state_ref:
        raise ValueError("application planning report crossed StateRef")
    matched = tuple(dict.fromkeys(matched_request_ids))
    if len(matched) != len(matched_request_ids):
        raise ValueError("application applicability has duplicate matches")

    decisions = (
        ()
        if planning_report is None
        else planning_report.decisions_for(
            feature_id=feature_id,
            producer_id=native_producer_id,
        )
    )
    if not decisions:
        return None
    _stage, decision = decisions[-1]
    planned_ids = set(decision.proposed_request_ids)
    if any(request_id not in planned_ids for request_id in matched):
        raise ValueError("application match is outside the planned population")

    # A producer can participate in both planning stages.  Observations from a
    # previous stage remain authoritative facts, but they are not members of
    # the latest population and cannot count toward its completeness.
    observations = tuple(
        item
        for item in producer_observations
        if item.request_id in planned_ids
    )
    observation_by_id = {item.request_id: item for item in observations}
    if len(observation_by_id) != len(observations):
        raise ValueError("application applicability has duplicate observations")
    observed_ids = set(observation_by_id)
    if any(request_id not in observed_ids for request_id in matched):
        raise ValueError("application diagnostic match has no native observation")
    for request_id in matched:
        observation = observation_by_id[request_id]
        descriptor = observation.descriptor
        if (
            observation.status != "accepted"
            or not isinstance(descriptor, NativeProofTermDescriptor)
            or descriptor.result_convertible_to_current_goal is not True
        ):
            raise ValueError(
                "application applicability match lacks native goal relation"
            )

    planning_evidence = tuple(
        stage.evidence_ref for stage, _decision in decisions
    )
    observation_evidence = tuple(
        EvidenceRef(
            evidence_id="native-search:" + item.provenance.source_event_id,
            source_kind="native_application_search",
            source_ref=item.provenance.artifact_ref,
            source_sha256=item.provenance.source_sha256,
        )
        for item in observations
    )
    evidence_refs = tuple(dict.fromkeys(
        planning_evidence + observation_evidence
    ))
    nonmatching = tuple(
        item.request_id
        for item in observations
        if item.request_id not in matched
    )
    common = {
        "producer_id": native_producer_id,
        "state_ref": state_ref,
        "operation": operation,
        "selected_resource": selected_resource,
        "population_identity_sha256": decision.proposed_population_sha256,
        "evidence_refs": evidence_refs,
    }
    if decision.disposition == NATIVE_PRODUCTION_ABSTAINED:
        if matched:
            return ApplicationApplicability(
                **common,
                status=APPLICATION_APPLICABLE,
                population_complete=False,
                accepted_request_ids=matched,
                nonmatching_request_ids=nonmatching,
                reason=decision.reason,
            )
        return ApplicationApplicability(
            **common,
            status=APPLICATION_INDETERMINATE,
            population_complete=False,
            accepted_request_ids=(),
            nonmatching_request_ids=nonmatching,
            reason=decision.reason,
        )
    if decision.disposition != NATIVE_PRODUCTION_READY:
        return None

    population_complete = observed_ids == planned_ids
    unvalidated_convertible = tuple(
        item
        for item in observations
        if item.request_id not in matched
        and item.status == "accepted"
        and isinstance(item.descriptor, NativeProofTermDescriptor)
        and item.descriptor.result_convertible_to_current_goal is True
    )
    if unvalidated_convertible:
        return ApplicationApplicability(
            **common,
            status=APPLICATION_INDETERMINATE,
            population_complete=population_complete,
            accepted_request_ids=(),
            nonmatching_request_ids=nonmatching,
            reason="native_result_failed_feature_validation",
        )
    if not population_complete:
        if matched:
            return ApplicationApplicability(
                **common,
                status=APPLICATION_APPLICABLE,
                population_complete=False,
                accepted_request_ids=matched,
                nonmatching_request_ids=nonmatching,
                reason="native_population_incomplete",
            )
        return ApplicationApplicability(
            **common,
            status=APPLICATION_INDETERMINATE,
            population_complete=False,
            accepted_request_ids=(),
            nonmatching_request_ids=nonmatching,
            reason="native_population_incomplete",
        )
    return ApplicationApplicability(
        **common,
        status=(
            APPLICATION_APPLICABLE
            if matched
            else APPLICATION_INAPPLICABLE
        ),
        population_complete=True,
        accepted_request_ids=matched,
        nonmatching_request_ids=nonmatching,
        reason="" if matched else "complete_native_population_has_no_match",
    )
