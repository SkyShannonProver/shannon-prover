"""Native localization of the first failing smt call of a rejected tactic.

Owned by this slice.  The companion's ``smt_failure_localization`` realizer
emits the payload; this module types it, and its codec checks that it
describes the attempt it arrived with.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.easycrypt.proof_state_compiler.contracts import (
    AttemptRealization,
    CarriesRealization,
    NativeAttemptedOperationDescriptor,
    RealizationCodec,
    attempt_realization,
    realization_fields,
)


SMT_FAILURE_LOCALIZATION_KIND = "smt_failure_localization.first_failed_call"
SMT_CALL_FAILED = "smt_call_failed"
SMT_CALL_FAMILY = "smt_call"
# The kind of the first failed goal: a program judgment by EasyCrypt's own
# constructor, any other formula, or "" when EasyCrypt's run could not
# re-derive that goal.
FORMULA_GOAL = "formula"
PROGRAM_JUDGMENT_KINDS = frozenset({
    "hoare_function",
    "hoare_statement",
    "phoare_function",
    "phoare_statement",
    "ehoare_function",
    "ehoare_statement",
    "equiv_function",
    "equiv_statement",
    "eager_function",
})
_GOAL_KINDS = PROGRAM_JUDGMENT_KINDS | {FORMULA_GOAL, ""}
_FIELDS = frozenset({
    "smt_call_text",
    "smt_call_start",
    "smt_call_end",
    "failed_goal_count",
    "failed_goal_count_complete",
    "first_failed_goal_kind",
    "report_failure_call",
    "strict_failure_call",
})


def _count(value: object) -> bool:
    return type(value) is int and value >= 1


@dataclass(frozen=True)
class NativeSmtFailureLocalization:
    """EasyCrypt's first failing smt call in one rejected tactic.

    ``smt_call_start``/``smt_call_end`` are UTF-8 byte offsets of the call
    EasyCrypt located, in the exact tactic that was run.  The two call
    numbers count smt calls in execution order in report and strict mode;
    the companion claims only when they agree.  ``failed_goal_count``
    counts report-mode failures of that same call and is a lower bound when
    the report run did not finish.
    """

    smt_call_text: str
    smt_call_start: int
    smt_call_end: int
    failed_goal_count: int
    failed_goal_count_complete: bool
    first_failed_goal_kind: str
    report_failure_call: int
    strict_failure_call: int
    failure_kind: str

    def __post_init__(self) -> None:
        if (
            type(self.smt_call_text) is not str
            or not self.smt_call_text.strip()
            or "\n" in self.smt_call_text
            or "\r" in self.smt_call_text
            or type(self.smt_call_start) is not int
            or type(self.smt_call_end) is not int
            or self.smt_call_start < 0
            or self.smt_call_end
            != self.smt_call_start + len(self.smt_call_text.encode("utf-8"))
            or not _count(self.failed_goal_count)
            or type(self.failed_goal_count_complete) is not bool
            or self.first_failed_goal_kind not in _GOAL_KINDS
            or not _count(self.report_failure_call)
            or self.strict_failure_call != self.report_failure_call
            or self.failure_kind != SMT_CALL_FAILED
        ):
            raise ValueError("native smt-failure localization is incomplete")

    @classmethod
    def from_realization(
        cls, realization: AttemptRealization
    ) -> "NativeSmtFailureLocalization":
        payload = realization_fields(realization, _FIELDS)
        return cls(
            smt_call_text=payload["smt_call_text"],
            smt_call_start=payload["smt_call_start"],
            smt_call_end=payload["smt_call_end"],
            failed_goal_count=payload["failed_goal_count"],
            failed_goal_count_complete=payload["failed_goal_count_complete"],
            first_failed_goal_kind=payload["first_failed_goal_kind"],
            report_failure_call=payload["report_failure_call"],
            strict_failure_call=payload["strict_failure_call"],
            failure_kind=realization.failure_kind,
        )

    def located_in(self, tactic: str) -> bool:
        """Whether the call's byte span in ``tactic`` spells the call."""

        encoded = tactic.encode("utf-8")
        try:
            spelled = encoded[self.smt_call_start:self.smt_call_end].decode(
                "utf-8"
            )
        except UnicodeDecodeError:
            return False
        return (
            self.smt_call_end <= len(encoded)
            and spelled == self.smt_call_text
        )


def _read(
    attempt: NativeAttemptedOperationDescriptor,
) -> NativeSmtFailureLocalization:
    descriptor = NativeSmtFailureLocalization.from_realization(
        attempt.realization
    )
    if (
        attempt.operation_family != SMT_CALL_FAMILY
        or attempt.exact_resource
        or attempt.argument_kinds
        or attempt.proof_term is not None
        or attempt.application_head is not None
        or attempt.side
        or attempt.positions
        or not descriptor.located_in(attempt.rejected_tactic)
    ):
        raise ValueError(
            "native smt-failure localization does not realize its attempt"
        )
    return descriptor


SMT_FAILURE_LOCALIZATION_CODEC = RealizationCodec(
    SMT_FAILURE_LOCALIZATION_KIND, _read
)


def smt_failure_of(
    attempt: CarriesRealization | None,
) -> NativeSmtFailureLocalization | None:
    """The typed localization if ``attempt`` carries this slice's kind."""

    realization = attempt_realization(attempt, SMT_FAILURE_LOCALIZATION_KIND)
    if realization is None:
        return None
    return NativeSmtFailureLocalization.from_realization(realization)
