"""Native repair of one selected nested intro pattern.

Owned by this slice.  The companion's ``intro_pattern_repair`` realizer
emits the payload; this module types it, and its codec checks that it
realizes the attempt it arrived with.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.easycrypt.proof_state_compiler.contracts import (
    CarriesRealization,
    AttemptRealization,
    NativeAttemptedOperationDescriptor,
    RealizationCodec,
    attempt_realization,
    realization_fields,
)

INTRO_PATTERN_REALIZATION_KIND = "intro_pattern_repair.nested_case"
_FIELDS = frozenset({
    "source_operation",
    "surface_operation",
    "attempted_pattern_kind",
    "binder_names",
    "candidate_tactic",
    "selected_pattern_count",
})


@dataclass(frozen=True)
class NativeIntroPatternRepairDescriptor:
    """Unique native repair of one agent-selected nested intro pattern.

    EasyCrypt has parsed both tactics and accepted the candidate in the exact
    unchanged state.  Shannon records only the already selected binder names
    and their order; it does not choose a hypothesis, decomposition, or proof
    route.
    """

    source_operation: str
    surface_operation: str
    attempted_pattern_kind: str
    binder_names: tuple[str, ...]
    candidate_tactic: str
    failure_kind: str
    selected_pattern_count: int

    def __post_init__(self) -> None:
        if (
            self.source_operation != "intro_pattern"
            or self.surface_operation != "move"
            or self.attempted_pattern_kind != "nested_case"
            or len(self.binder_names) < 2
            or len(self.binder_names) > 32
            or len(self.binder_names) != len(set(self.binder_names))
            or any(type(name) is not str or not name for name in self.binder_names)
            or type(self.candidate_tactic) is not str
            or not self.candidate_tactic.endswith(".")
            or self.failure_kind != "intro_pattern_structure_mismatch"
            or self.selected_pattern_count != 1
        ):
            raise ValueError("native intro-pattern repair descriptor is incomplete")

    @classmethod
    def from_realization(
        cls, realization: AttemptRealization
    ) -> "NativeIntroPatternRepairDescriptor":
        payload = realization_fields(realization, _FIELDS)
        binder_names = payload["binder_names"]
        if type(binder_names) is not list:
            raise ValueError("native intro-pattern binders are invalid")
        return cls(
            source_operation=payload["source_operation"],
            surface_operation=payload["surface_operation"],
            attempted_pattern_kind=payload["attempted_pattern_kind"],
            binder_names=tuple(binder_names),
            candidate_tactic=payload["candidate_tactic"],
            failure_kind=realization.failure_kind,
            selected_pattern_count=payload["selected_pattern_count"],
        )


def _read(
    attempt: NativeAttemptedOperationDescriptor,
) -> NativeIntroPatternRepairDescriptor:
    descriptor = NativeIntroPatternRepairDescriptor.from_realization(
        attempt.realization
    )
    if (
        attempt.operation_family != "intro_pattern"
        or attempt.exact_resource
        or attempt.proof_term is not None
        or attempt.application_head is not None
        or attempt.side
        or attempt.positions
    ):
        raise ValueError("native intro-pattern repair does not realize its attempt")
    return descriptor


INTRO_PATTERN_REALIZATION_CODEC = RealizationCodec(
    INTRO_PATTERN_REALIZATION_KIND, _read
)


def intro_pattern_realization_of(
    attempt: CarriesRealization | None,
) -> NativeIntroPatternRepairDescriptor | None:
    """The typed realization if ``attempt`` carries this slice's kind."""

    realization = attempt_realization(attempt, INTRO_PATTERN_REALIZATION_KIND)
    if realization is None:
        return None
    return NativeIntroPatternRepairDescriptor.from_realization(realization)
