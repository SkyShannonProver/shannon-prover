"""Pass-neutral Agent-facing account of a native compound-tactic boundary.

P3 can emit the standalone M18 diagnostic and P4 can compose the same boundary
with a consumer-owned recovery.  Both consume the same typed facts and use this
single wording owner; neither pass imports the other.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.easycrypt.proof_state_compiler.contracts.failure import (
        RecoveryHandoff,
    )


def compound_boundary_summary(
    *,
    accepted_prefix: str,
    accepted_effect: str,
    accepted_stage_count: int,
    rejected_extension: str,
    native_error: str,
    parse_error: bool = False,
    sentence: tuple[int, int] | None = None,
) -> str:
    """Describe rollback, the accepted prefix, and the first failed stage.

    The accepted prefix is quoted exactly once: the agent already holds the
    tactic it submitted, and repeating a long prefix is what pushed real
    boundaries past their delivery budget.  The account ends with EasyCrypt's
    report: it lists no continuations, which the agent already knows.

    When the tactic does not parse, EasyCrypt ran none of it: the prefix ran
    only on its own, and what follows it is the text that does not parse,
    possibly several stages, rather than one failing stage.

    ``sentence`` is ``(index, count)`` when the stages belong to the sentence
    EasyCrypt rejected in a multi-sentence commit: they ran after the
    sentences before it.
    """

    if accepted_stage_count == 1:
        accepted = "the first stage, which"
        verb = "changes" if accepted_effect == "accepted_changed" else "does not change"
    else:
        accepted = f"the first {accepted_stage_count} stages, which"
        verb = "change" if accepted_effect == "accepted_changed" else "do not change"
    if sentence is not None:
        index, count = sentence
        before = (
            "" if index == 1
            else " after the sentence before it" if index == 2
            else f" after the {index - 1} sentences before it"
        )
        subject = f"Sentence {index} of your {count}-sentence commit"
        where = f"In sentence {index},{before}, " if before else (
            f"In sentence {index}, "
        )
    else:
        subject = "Your compound tactic"
        where = ""
    if parse_error:
        opening = (
            f"{subject} does not parse, so EasyCrypt ran none of it; "
            "nothing was committed.\n\n"
            f"{where}on its own, EasyCrypt can execute {accepted} {verb} the "
            "goal:"
            if where else
            f"{subject} does not parse, so EasyCrypt ran none of it; "
            "nothing was committed.\n\n"
            f"On its own, EasyCrypt can execute {accepted} {verb} the goal:"
        )
        failing = "The rest does not parse:"
    else:
        opening = (
            f"{subject} failed and the commit was rolled back; nothing was "
            "committed.\n\n"
            f"{where}EasyCrypt can execute {accepted} {verb} the goal:"
            if sentence is not None else
            "Your compound tactic failed and was rolled back; nothing was "
            "committed.\n\n"
            f"EasyCrypt can execute {accepted} {verb} the goal:"
        )
        failing = "The next stage fails:"
    return (
        f"{opening}\n\n"
        f"{_indented_block(accepted_prefix)}\n\n"
        f"{failing}\n\n"
        f"{_indented_block(rejected_extension)}\n\n"
        "EasyCrypt reports:\n\n"
        f"{_indented_block(native_error)}"
    )


def checked_goal_reference(handoff: RecoveryHandoff | None) -> str:
    """Name the exact goal in which a failed operation was checked.

    A state-changing handoff is always presented after the boundary summary,
    which quotes the accepted prefix; refer back to it instead of quoting it
    again in every sentence.
    """

    if handoff is not None and handoff.prefix_changes_state:
        stages = (
            "that accepted stage" if handoff.accepted_prefix_stage_count == 1
            else "those accepted stages"
        )
        return f"the temporary goal produced by {stages}"
    return "the current goal"


def checked_entire_goal_reference(handoff: RecoveryHandoff | None) -> str:
    """Name the whole checked goal without losing its current/temporary scope."""

    goal = checked_goal_reference(handoff)
    return "the entire " + goal.removeprefix("the ")


def checked_state_reference(handoff: RecoveryHandoff | None) -> str:
    """Name the exact proof-state context used by a native check."""

    if handoff is not None and handoff.prefix_changes_state:
        return checked_goal_reference(handoff)
    return "the current proof state"


def _indented_block(value: str) -> str:
    lines = value.replace("\r\n", "\n").replace("\r", "\n")
    return "  " + lines.replace("\n", "\n  ")
