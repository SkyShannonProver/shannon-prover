"""Shared aggregation rules for bindings and exact applications."""

from core.easycrypt.proof_state_compiler.contracts.analyzed_state import (
    ApplicationCandidate,
    BindingResolution,
)
from core.easycrypt.proof_state_compiler.middle_end.contributions import (
    AnalysisContribution,
)


def aggregate_bindings(
    contributions: tuple[AnalysisContribution, ...],
) -> tuple[BindingResolution, ...]:
    bindings = tuple(
        item for contribution in contributions for item in contribution.bindings
    )
    identities = [item.binding_id for item in bindings]
    if len(identities) != len(set(identities)):
        raise ValueError("P3 producers emitted duplicate binding resolutions")
    return bindings


def aggregate_applications(
    contributions: tuple[AnalysisContribution, ...],
) -> tuple[ApplicationCandidate, ...]:
    applications = tuple(
        item for contribution in contributions for item in contribution.applications
    )
    candidate_ids = [item.candidate_id for item in applications]
    if len(candidate_ids) != len(set(candidate_ids)):
        raise ValueError("P3 producers emitted duplicate application candidate IDs")
    return applications
