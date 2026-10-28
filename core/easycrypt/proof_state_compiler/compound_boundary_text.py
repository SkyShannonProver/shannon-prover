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
) -> str:
    """Describe rollback, the accepted prefix, and the first failed stage.

    The accepted prefix is quoted exactly once: the agent already holds the
    tactic it submitted, and repeating a long prefix is what pushed real
    boundaries past their delivery budget.
    """

    if accepted_stage_count == 1:
        accepted = "the first stage, which"
        verb = "changes" if accepted_effect == "accepted_changed" else "does not change"
    else:
        accepted = f"the first {accepted_stage_count} stages, which"
        verb = "change" if accepted_effect == "accepted_changed" else "do not change"
    return (
        "Your compound tactic failed and was rolled back; nothing was "
        "committed.\n\n"
        f"EasyCrypt can execute {accepted} {verb} the goal:\n\n"
        f"{_indented_block(accepted_prefix)}\n\n"
        "The next stage fails:\n\n"
        f"{_indented_block(rejected_extension)}\n\n"
        "EasyCrypt reports:\n\n"
        f"{_indented_block(native_error)}"
    )


def compound_boundary_continuation(
    *,
    accepted_effect: str,
    accepted_stage_count: int,
) -> str:
    """State strategy-preserving options after an explanation-only result.

    The boundary summary above always quotes the prefix, so this text refers
    to it rather than repeating it.
    """

    stages, it = (
        ("that stage", "it") if accepted_stage_count == 1
        else ("those stages", "them")
    )
    if accepted_effect == "accepted_changed":
        return (
            f"To continue from the goal after {stages}, submit {it} alone, "
            "or fix the failing suffix and resubmit the compound. The "
            "compiler does not choose between these options."
        )
    return (
        f"Submitting {stages} alone would not change the goal; fix the "
        "failing suffix or choose a different tactic. The compiler does not "
        "choose between these options."
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
    return "  " + value.replace("\n", "\n  ")
