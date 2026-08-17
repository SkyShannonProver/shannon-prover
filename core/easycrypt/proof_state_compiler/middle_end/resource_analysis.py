"""Shared aggregation rules for resource-liveness assessments."""

from core.easycrypt.proof_state_compiler.contracts.analyzed_state import (
    ResourceAssessment,
)
from core.easycrypt.proof_state_compiler.middle_end.contributions import (
    AnalysisContribution,
)


def aggregate_resource_assessments(
    contributions: tuple[AnalysisContribution, ...],
) -> tuple[ResourceAssessment, ...]:
    assessments = tuple(
        item for contribution in contributions for item in contribution.resources
    )
    identities = [item.resource_id for item in assessments]
    if len(identities) != len(set(identities)):
        raise ValueError("P3 producers emitted duplicate resource assessments")
    return assessments
