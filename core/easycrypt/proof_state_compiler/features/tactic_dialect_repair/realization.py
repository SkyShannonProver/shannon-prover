"""Native eager-while dialect realization of one selected failure.

Owned by this slice.  The companion's ``tactic_dialect_repair`` realizer
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

EAGER_WHILE_DIALECT_KIND = "tactic_dialect_repair.eager_while"
_FIELDS = frozenset({
    "source_operation",
    "eager_subform",
    "attempted_shape",
    "candidates",
})


@dataclass(frozen=True)
class NativeEagerWhileCandidateDescriptor:
    """One agent-supplied invariant accepted by native eager preflight."""

    invariant_text: str
    candidate_tactic: str

    def __post_init__(self) -> None:
        if (
            type(self.invariant_text) is not str
            or not self.invariant_text
            or self.candidate_tactic
            != f"eager while ({self.invariant_text})."
        ):
            raise ValueError("native eager-while candidate is not canonical")


@dataclass(frozen=True)
class NativeEagerWhileDialectDescriptor:
    """Native classification of one selected eager-while failure."""

    source_operation: str
    eager_subform: str
    attempted_shape: str
    failure_kind: str
    candidates: tuple[NativeEagerWhileCandidateDescriptor, ...]

    def __post_init__(self) -> None:
        if (
            self.source_operation != "eager"
            or self.eager_subform != "while"
            or self.attempted_shape not in {
                "explicit_statement_contract", "invariant"
            }
            or self.failure_kind not in {
                "eager_while_dialect_mismatch",
                "eager_while_guard_mismatch",
            }
            or len(self.candidates) > 2
            or len(self.candidates) != len(set(self.candidates))
        ):
            raise ValueError("native eager-while dialect descriptor is incomplete")
        if self.failure_kind == "eager_while_dialect_mismatch" and (
            self.attempted_shape != "explicit_statement_contract"
        ):
            raise ValueError("native eager dialect mismatch has the wrong shape")
        if self.failure_kind == "eager_while_guard_mismatch" and (
            self.attempted_shape != "invariant" or self.candidates
        ):
            raise ValueError("native eager guard mismatch carried candidates")

    @classmethod
    def from_realization(
        cls, realization: AttemptRealization
    ) -> "NativeEagerWhileDialectDescriptor":
        payload = realization_fields(realization, _FIELDS)
        candidates = payload["candidates"]
        if type(candidates) is not list or any(
            type(item) is not dict
            or set(item) != {"invariant_text", "candidate_tactic"}
            for item in candidates
        ):
            raise ValueError("native eager-while candidates are invalid")
        return cls(
            source_operation=payload["source_operation"],
            eager_subform=payload["eager_subform"],
            attempted_shape=payload["attempted_shape"],
            failure_kind=realization.failure_kind,
            candidates=tuple(
                NativeEagerWhileCandidateDescriptor(
                    invariant_text=item["invariant_text"],
                    candidate_tactic=item["candidate_tactic"],
                )
                for item in candidates
            ),
        )


def _read(
    attempt: NativeAttemptedOperationDescriptor,
) -> NativeEagerWhileDialectDescriptor:
    descriptor = NativeEagerWhileDialectDescriptor.from_realization(
        attempt.realization
    )
    if (
        attempt.operation_family != "eager"
        or attempt.exact_resource
        or attempt.proof_term is not None
        or attempt.application_head is not None
        or attempt.side
        or attempt.positions
    ):
        raise ValueError("native eager dialect does not realize its attempt")
    return descriptor


EAGER_WHILE_DIALECT_CODEC = RealizationCodec(EAGER_WHILE_DIALECT_KIND, _read)


def eager_while_dialect_of(
    attempt: CarriesRealization | None,
) -> NativeEagerWhileDialectDescriptor | None:
    """The typed realization if ``attempt`` carries this slice's kind."""

    realization = attempt_realization(attempt, EAGER_WHILE_DIALECT_KIND)
    if realization is None:
        return None
    return NativeEagerWhileDialectDescriptor.from_realization(realization)
