"""State-bound P3 assessment of one selected application's viability.

This is compiler-derived evidence over a declared bounded native population.
It is not a replacement for EasyCrypt observations and it does not claim that
the selected theorem is globally usable or unusable outside that population.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.easycrypt.proof_state_compiler.contracts.evidence import EvidenceRef
from core.easycrypt.proof_state_compiler.contracts.state_ref import StateRef


APPLICATION_APPLICABLE = "applicable"
APPLICATION_INAPPLICABLE = "inapplicable"
APPLICATION_INDETERMINATE = "indeterminate"
APPLICATION_APPLICABILITY_STATUSES = frozenset({
    APPLICATION_APPLICABLE,
    APPLICATION_INAPPLICABLE,
    APPLICATION_INDETERMINATE,
})
BOUNDED_NATIVE_POPULATION = "bounded_native_population"


@dataclass(frozen=True)
class ApplicationApplicability:
    """Applicability before argument repair for one exact ``StateRef``.

    ``accepted_request_ids`` and ``nonmatching_request_ids`` are audit-only.
    Presentation consumes only the typed status and completeness facts.
    An incomplete population can establish applicability after one accepted
    member, but it can never establish a unique completion.
    """

    producer_id: str
    state_ref: StateRef
    operation: str
    selected_resource: str
    status: str
    population_complete: bool
    population_identity_sha256: str
    accepted_request_ids: tuple[str, ...]
    nonmatching_request_ids: tuple[str, ...]
    reason: str
    evidence_refs: tuple[EvidenceRef, ...]
    scope: str = BOUNDED_NATIVE_POPULATION

    def __post_init__(self) -> None:
        if not self.producer_id or not self.selected_resource:
            raise ValueError("application applicability requires ownership")
        if self.operation not in {"apply", "exact", "call"}:
            raise ValueError("application applicability operation is invalid")
        if self.status not in APPLICATION_APPLICABILITY_STATUSES:
            raise ValueError("application applicability status is invalid")
        if self.scope != BOUNDED_NATIVE_POPULATION:
            raise ValueError("application applicability scope is invalid")
        if (
            len(self.population_identity_sha256) != 64
            or any(
                char not in "0123456789abcdef"
                for char in self.population_identity_sha256
            )
        ):
            raise ValueError("application population identity is invalid")
        accepted = self.accepted_request_ids
        nonmatching = self.nonmatching_request_ids
        if (
            len(accepted) != len(set(accepted))
            or len(nonmatching) != len(set(nonmatching))
            or set(accepted) & set(nonmatching)
        ):
            raise ValueError("application applicability request identity is invalid")
        if self.status == APPLICATION_APPLICABLE:
            if not accepted:
                raise ValueError("applicable assessment requires native acceptance")
            if (
                (self.population_complete and self.reason)
                or (not self.population_complete and not self.reason)
            ):
                raise ValueError(
                    "applicable assessment completeness/reason is inconsistent"
                )
        elif self.status == APPLICATION_INAPPLICABLE:
            if accepted or not self.population_complete or not self.reason:
                raise ValueError("inapplicable assessment requires complete zero match")
        elif accepted or not self.reason:
            raise ValueError("indeterminate assessment requires zero checked matches")
        if not self.evidence_refs:
            raise ValueError("application applicability requires evidence")

    @property
    def unique_checked_completion(self) -> bool:
        return self.population_complete and len(self.accepted_request_ids) == 1

    @property
    def unique_selection_unestablished(self) -> bool:
        return self.status == APPLICATION_APPLICABLE and (
            not self.population_complete or len(self.accepted_request_ids) > 1
        )
