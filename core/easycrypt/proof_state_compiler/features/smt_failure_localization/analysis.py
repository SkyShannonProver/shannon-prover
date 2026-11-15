"""Own one native-localized smt failure of a rejected tactic.

The diagnostic reports only what EasyCrypt established: which smt call of
the tactic it ran fails first, how many goals that call fails on, and the
kind of the first failed goal.  It says nothing about what to do next.
"""

from __future__ import annotations

from core.easycrypt.proof_state_compiler.compound_boundary_text import (
    checked_goal_reference,
)
from core.easycrypt.proof_state_compiler.contracts import (
    EXPLANATION_ONLY,
    AttemptedOperationIR,
    CompilerInvocationContext,
    ProofCoordinate,
    ProofIR,
    StructuredDiagnostic,
    exact_operation_resource_witness,
    recovery_claim_for,
)
from core.easycrypt.proof_state_compiler.frontend.attempted_operation import (
    manager_reports_same_error,
)
from core.easycrypt.proof_state_compiler.middle_end.contributions import (
    AnalysisContribution,
)
from .ids import SMT_FAILURE_LOCALIZATION_FEATURE_ID
from .realization import (
    FORMULA_GOAL,
    PROGRAM_JUDGMENT_KINDS,
    SMT_CALL_FAILED,
    SMT_CALL_FAMILY,
    NativeSmtFailureLocalization,
    smt_failure_of,
)


SMT_FAILURE_LOCALIZATION_PRODUCER_ID = "smt_failure_localization.analysis"
_JUDGMENT_NAMES = {
    "hoare": "a `hoare` judgment",
    "phoare": "a `phoare` judgment",
    "ehoare": "an `ehoare` judgment",
    "equiv": "an `equiv` judgment",
    "eager": "an `eager` judgment",
}


def analyze_smt_failure_localization(
    proof_ir: ProofIR,
    _coordinate: ProofCoordinate,
    invocation: CompilerInvocationContext,
) -> AnalysisContribution:
    attempted = proof_ir.attempted_operation
    descriptor = None if attempted is None else smt_failure_of(attempted)
    failure = invocation.failure_observation
    if (
        attempted is None
        or descriptor is None
        or failure is None
        or attempted.operation_family != SMT_CALL_FAMILY
        or attempted.exact_resource
        or attempted.native_diagnostic_status != "blocker"
        or attempted.native_failure_kind != SMT_CALL_FAILED
        or descriptor.report_failure_call != descriptor.strict_failure_call
        or not descriptor.located_in(attempted.rejected_tactic)
        # The strict native run must fail with the error EasyCrypt reported
        # for the commit; the text is a veto, never a classifier.
        or not manager_reports_same_error(
            attempted.native_error_message,
            failure.structured_error,
        )
    ):
        return AnalysisContribution()
    primary = smt_failure_explanation(attempted, descriptor)
    if primary is None:
        return AnalysisContribution()
    diagnostic = StructuredDiagnostic(
        producer_id=SMT_FAILURE_LOCALIZATION_PRODUCER_ID,
        code="smt_failure_localization",
        primary=primary,
        notes=(),
        help="",
        applicability=EXPLANATION_ONLY,
        evidence_refs=attempted.evidence_refs,
        trigger_id=attempted.trigger_id,
    )
    claim = recovery_claim_for(
        attempted,
        feature_id=SMT_FAILURE_LOCALIZATION_FEATURE_ID,
        allowed_output_kinds=("diagnostic",),
        preservation_witness=exact_operation_resource_witness(
            attempted.operation_family,
            attempted.exact_resource,
        ),
    )
    return AnalysisContribution(
        diagnostics=(diagnostic,),
        recovery_claims=(claim,),
    )


def smt_failure_explanation(
    attempted: AttemptedOperationIR,
    descriptor: NativeSmtFailureLocalization,
) -> str | None:
    """The agent-facing facts, or ``None`` when they add nothing or cannot
    be quoted exactly."""

    tactic = attempted.rejected_tactic
    call = descriptor.smt_call_text
    handoff = attempted.recovery_handoff
    if "`" in call:
        return None
    if handoff is None and _call_is_whole_tactic(tactic, descriptor):
        # Its only failed goal is the current goal, which the agent sees.
        return None
    occurrences = _byte_occurrences(tactic, call)
    if descriptor.smt_call_start not in occurrences:
        return None
    position = ""
    if len(occurrences) > 1:
        ordinal = _ordinal(occurrences.index(descriptor.smt_call_start) + 1)
        position = f" (the {ordinal} `{call}` from the left)"
    subject = "your tactic" if handoff is None else "the failing tactic"
    goal = checked_goal_reference(handoff)
    count = descriptor.failed_goal_count
    bound = "" if descriptor.failed_goal_count_complete else "at least "
    goals = "goal" if count == 1 else "goals"
    lines = [
        f"Running {subject} on {goal}, the first smt call EasyCrypt cannot "
        f"prove is `{call}`{position}.",
    ]
    detail = (
        "In EasyCrypt's report mode, which admits a failed smt goal and "
        f"continues, this call fails on {bound}{count} {goals}."
    )
    kind = descriptor.first_failed_goal_kind
    if kind:
        first = (
            "That goal is"
            if count == 1 and descriptor.failed_goal_count_complete
            else "The first of them is"
        )
        if kind == FORMULA_GOAL:
            detail += f" {first} a pure logical formula."
        elif kind in PROGRAM_JUDGMENT_KINDS:
            name = _JUDGMENT_NAMES[kind.split("_", 1)[0]]
            detail += (
                f" {first} {name}; smt does not reason about programs: it "
                "treats a program judgment as an opaque proposition."
            )
        else:
            return None
    lines.append(detail)
    return "\n\n".join(lines)


def _call_is_whole_tactic(
    tactic: str,
    descriptor: NativeSmtFailureLocalization,
) -> bool:
    encoded = tactic.encode("utf-8")
    before = encoded[:descriptor.smt_call_start].strip()
    after = encoded[descriptor.smt_call_end:].strip()
    return before in {b"", b"by", b"try"} and after == b"."


def _byte_occurrences(text: str, needle: str) -> list[int]:
    encoded = text.encode("utf-8")
    pattern = needle.encode("utf-8")
    found = []
    index = encoded.find(pattern)
    while index >= 0:
        found.append(index)
        index = encoded.find(pattern, index + len(pattern))
    return found


def _ordinal(value: int) -> str:
    if value % 100 in {11, 12, 13}:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(value % 10, "th")
    return f"{value}{suffix}"
