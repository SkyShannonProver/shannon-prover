"""Native unique-target realization of one selected rewrite.

Owned by this slice.  The companion's ``pure_tail_recovery`` realizer emits
the payload; this module types it, and its codec checks that it realizes the
attempt it arrived with.
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

PURE_TAIL_REWRITE_KIND = "pure_tail_recovery.rewrite_target"
_FIELDS = frozenset({
    "source_operation",
    "selected_resource",
    "target_kind",
    "target_name",
    "candidate_tactic",
    "accepted_target_count",
})


@dataclass(frozen=True)
class NativePureTailRewriteDescriptor:
    """Unique native realization of an agent-selected rewrite target.

    The descriptor does not choose a lemma, direction, occurrence, witness, or
    proof route.  It only records that the exact left-to-right rewrite already
    attempted by the agent fails at the conclusion and succeeds at exactly one
    named hypothesis in the unchanged current state.
    """

    source_operation: str
    selected_resource: str
    target_kind: str
    target_name: str
    candidate_tactic: str
    failure_kind: str
    accepted_target_count: int

    def __post_init__(self) -> None:
        if (
            self.source_operation != "rewrite"
            or type(self.selected_resource) is not str
            or not self.selected_resource
            or self.target_kind != "hypothesis"
            or type(self.target_name) is not str
            or not self.target_name
            or self.candidate_tactic
            != f"rewrite {self.selected_resource} in {self.target_name}."
            or self.failure_kind != "rewrite_target_mismatch"
            or self.accepted_target_count != 1
        ):
            raise ValueError("native pure-tail rewrite descriptor is incomplete")

    @classmethod
    def from_realization(
        cls, realization: AttemptRealization
    ) -> "NativePureTailRewriteDescriptor":
        payload = realization_fields(realization, _FIELDS)
        return cls(
            source_operation=payload["source_operation"],
            selected_resource=payload["selected_resource"],
            target_kind=payload["target_kind"],
            target_name=payload["target_name"],
            candidate_tactic=payload["candidate_tactic"],
            failure_kind=realization.failure_kind,
            accepted_target_count=payload["accepted_target_count"],
        )


def _read(
    attempt: NativeAttemptedOperationDescriptor,
) -> NativePureTailRewriteDescriptor:
    descriptor = NativePureTailRewriteDescriptor.from_realization(
        attempt.realization
    )
    if (
        attempt.operation_family != "rewrite"
        or attempt.exact_resource != descriptor.selected_resource
        or attempt.proof_term is not None
        or attempt.application_head is not None
        or attempt.side
        or attempt.positions
    ):
        raise ValueError("native pure-tail rewrite does not realize its attempt")
    return descriptor


PURE_TAIL_REWRITE_CODEC = RealizationCodec(PURE_TAIL_REWRITE_KIND, _read)


def pure_tail_rewrite_of(
    attempt: CarriesRealization | None,
) -> NativePureTailRewriteDescriptor | None:
    """The typed realization if ``attempt`` carries this slice's kind."""

    realization = attempt_realization(attempt, PURE_TAIL_REWRITE_KIND)
    if realization is None:
        return None
    return NativePureTailRewriteDescriptor.from_realization(realization)
