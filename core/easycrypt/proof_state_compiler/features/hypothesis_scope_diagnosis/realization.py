"""Native out-of-scope hypothesis realization of one rejected operation.

Owned by this slice.  The companion's ``hypothesis_scope_diagnosis`` realizer
emits the payload; this module types it, and its codec checks that it
realizes the attempt it arrived with.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from core.easycrypt.proof_state_compiler.contracts import (
    CarriesRealization,
    AttemptRealization,
    NativeAttemptedOperationDescriptor,
    RealizationCodec,
    attempt_realization,
    realization_fields,
)

OUT_OF_SCOPE_HYPOTHESIS_KIND = "hypothesis_scope_diagnosis.out_of_scope_hypothesis"
SMT_HINT_FAILURE = "smt_hint_names_goal_hypothesis"
REWRITE_TARGET_FAILURE = "rewrite_name_declared_after_target"
# Mirrors max_references in the companion's realizer.
MAX_REFERENCES = 16

_FIELDS = frozenset({
    "source_operation",
    "written_name",
    "reference_position",
    "reference_count",
    "target_name",
    "lookup_scope",
    "goal_hypothesis",
    "declared_after_target",
    "candidate_tactic",
    "remaining_hints",
})
_LOCAL_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_']*$")
_HINT = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_']*(?:\.[A-Za-z_][A-Za-z0-9_']*)*$"
)
# source operation -> (failure kind, lookup scope, declared after target)
_SHAPES = {
    "smt": (SMT_HINT_FAILURE, "global_declarations", False),
    "rewrite": (REWRITE_TARGET_FAILURE, "context_before_target", True),
}


@dataclass(frozen=True)
class NativeOutOfScopeHypothesisDescriptor:
    """One written name EasyCrypt could not resolve where the operation looks.

    EasyCrypt established each field in the proof where the operation ran:
    which reference failed (the located smt hint, or the first rejected
    rewrite-item prefix), that the name does not resolve in the operation's
    own lookup scope, that it is a hypothesis of the goal, and, for
    ``rewrite ... in H``, that it is declared after ``H``.  An smt
    ``candidate_tactic`` is the agent's call without that one hint, parsed
    back by EasyCrypt and accepted with progress in the same proof.
    """

    source_operation: str
    written_name: str
    reference_position: int
    reference_count: int
    target_name: str
    lookup_scope: str
    goal_hypothesis: bool
    declared_after_target: bool
    candidate_tactic: str
    remaining_hints: tuple[str, ...]
    failure_kind: str

    def __post_init__(self) -> None:
        shape = _SHAPES.get(self.source_operation)
        if (
            shape is None
            or (self.failure_kind, self.lookup_scope,
                self.declared_after_target) != shape
            or type(self.written_name) is not str
            or not _LOCAL_NAME.fullmatch(self.written_name)
            or type(self.reference_count) is not int
            or not 1 <= self.reference_count <= MAX_REFERENCES
            or type(self.reference_position) is not int
            or not 1 <= self.reference_position <= self.reference_count
            or self.goal_hypothesis is not True
            or type(self.target_name) is not str
            or type(self.candidate_tactic) is not str
            or any(
                type(item) is not str or not _HINT.fullmatch(item)
                for item in self.remaining_hints
            )
        ):
            raise ValueError("native out-of-scope hypothesis descriptor is invalid")
        if self.source_operation == "rewrite" and (
            not _LOCAL_NAME.fullmatch(self.target_name)
            or self.target_name == self.written_name
            or self.candidate_tactic
            or self.remaining_hints
        ):
            raise ValueError("native rewrite scope descriptor is invalid")
        if self.source_operation == "smt" and (
            self.target_name
            or (
                self.candidate_tactic
                and (
                    not self.candidate_tactic.startswith("smt")
                    or self.candidate_tactic[3:4] not in {"(", " "}
                    or not self.candidate_tactic.endswith(".")
                    or "\n" in self.candidate_tactic
                    or "\r" in self.candidate_tactic
                    or len(self.remaining_hints) != self.reference_count - 1
                )
            )
            or (not self.candidate_tactic and self.remaining_hints)
        ):
            raise ValueError("native smt hint scope descriptor is invalid")

    @classmethod
    def from_realization(
        cls, realization: AttemptRealization
    ) -> "NativeOutOfScopeHypothesisDescriptor":
        payload = realization_fields(realization, _FIELDS)
        remaining = payload["remaining_hints"]
        if type(remaining) is not list:
            raise ValueError("native out-of-scope hypothesis hints are invalid")
        return cls(
            source_operation=payload["source_operation"],
            written_name=payload["written_name"],
            reference_position=payload["reference_position"],
            reference_count=payload["reference_count"],
            target_name=payload["target_name"],
            lookup_scope=payload["lookup_scope"],
            goal_hypothesis=payload["goal_hypothesis"],
            declared_after_target=payload["declared_after_target"],
            candidate_tactic=payload["candidate_tactic"],
            remaining_hints=tuple(remaining),
            failure_kind=realization.failure_kind,
        )


def _read(
    attempt: NativeAttemptedOperationDescriptor,
) -> NativeOutOfScopeHypothesisDescriptor:
    descriptor = NativeOutOfScopeHypothesisDescriptor.from_realization(
        attempt.realization
    )
    if (
        attempt.operation_family != descriptor.source_operation
        or attempt.exact_resource != descriptor.written_name
        or attempt.proof_term is not None
        or attempt.application_head is not None
        or attempt.side
        or attempt.positions
    ):
        raise ValueError(
            "native out-of-scope hypothesis does not realize its attempt"
        )
    return descriptor


OUT_OF_SCOPE_HYPOTHESIS_CODEC = RealizationCodec(
    OUT_OF_SCOPE_HYPOTHESIS_KIND, _read
)


def out_of_scope_hypothesis_of(
    attempt: CarriesRealization | None,
) -> NativeOutOfScopeHypothesisDescriptor | None:
    """The typed realization if ``attempt`` carries this slice's kind."""

    realization = attempt_realization(attempt, OUT_OF_SCOPE_HYPOTHESIS_KIND)
    if realization is None:
        return None
    return NativeOutOfScopeHypothesisDescriptor.from_realization(realization)
