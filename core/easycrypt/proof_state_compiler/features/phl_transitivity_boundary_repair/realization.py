"""Native PHL transitivity boundary realization of one selected failure.

Owned by this slice.  The companion's ``phl_transitivity_boundary_repair``
realizer emits the payload; this module types it, and its codec checks that
it realizes the attempt it arrived with.
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

PHL_TRANSITIVITY_BOUNDARY_KIND = "phl_transitivity_boundary_repair.boundary"
_FIELDS = frozenset({
    "source_operation",
    "attempted_form",
    "current_goal_form",
    "side",
})


@dataclass(frozen=True)
class NativePhlTransitivityBoundaryDescriptor:
    """Native PHL transitivity form/current-goal boundary mismatch."""

    source_operation: str
    attempted_form: str
    current_goal_form: str
    side: str
    failure_kind: str

    def __post_init__(self) -> None:
        if (
            self.source_operation != "transitivity"
            or self.attempted_form not in {"function", "statement"}
            or self.current_goal_form not in {"function", "statement"}
            or self.attempted_form == self.current_goal_form
            or self.side not in {"", "left", "right"}
            or (
                self.attempted_form == "function" and self.side
            )
            or (
                self.attempted_form == "statement" and not self.side
            )
            or self.failure_kind != "phl_transitivity_boundary_mismatch"
        ):
            raise ValueError("native PHL transitivity boundary is incomplete")

    @classmethod
    def from_realization(
        cls, realization: AttemptRealization
    ) -> "NativePhlTransitivityBoundaryDescriptor":
        payload = realization_fields(realization, _FIELDS)
        return cls(
            source_operation=payload["source_operation"],
            attempted_form=payload["attempted_form"],
            current_goal_form=payload["current_goal_form"],
            side=payload["side"],
            failure_kind=realization.failure_kind,
        )


def _read(
    attempt: NativeAttemptedOperationDescriptor,
) -> NativePhlTransitivityBoundaryDescriptor:
    descriptor = NativePhlTransitivityBoundaryDescriptor.from_realization(
        attempt.realization
    )
    if (
        attempt.operation_family != "transitivity"
        or attempt.exact_resource
        or attempt.proof_term is not None
        or attempt.application_head is not None
        or attempt.side != descriptor.side
    ):
        raise ValueError("native PHL boundary does not realize its attempt")
    return descriptor


PHL_TRANSITIVITY_BOUNDARY_CODEC = RealizationCodec(
    PHL_TRANSITIVITY_BOUNDARY_KIND, _read
)


def phl_transitivity_boundary_of(
    attempt: CarriesRealization | None,
) -> NativePhlTransitivityBoundaryDescriptor | None:
    """The typed realization if ``attempt`` carries this slice's kind."""

    realization = attempt_realization(attempt, PHL_TRANSITIVITY_BOUNDARY_KIND)
    if realization is None:
        return None
    return NativePhlTransitivityBoundaryDescriptor.from_realization(realization)
