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
    """Describe rollback, the accepted prefix, and the first failed stage."""

    accepted_inline = markdown_inline_code(accepted_prefix)
    execute_label = (
        "EasyCrypt can execute the first stage:"
        if accepted_stage_count == 1
        else "EasyCrypt can execute through:"
    )
    changed = accepted_effect == "accepted_changed"
    effect = (
        "That stage changes the goal. The next stage fails:"
        if changed and accepted_stage_count == 1
        else (
            "That accepted prefix changes the goal. The next stage fails:"
            if changed
            else (
                "That stage does not change the goal. The next stage fails:"
                if accepted_stage_count == 1
                else (
                    "That accepted prefix does not change the goal. "
                    "The next stage fails:"
                )
            )
        )
    )
    return (
        "Your compound tactic failed and was rolled back. "
        f"{accepted_inline} was not committed.\n\n"
        f"{execute_label}\n\n"
        f"{_indented_block(accepted_prefix)}\n\n"
        f"{effect}\n\n"
        f"{_indented_block(rejected_extension)}\n\n"
        "EasyCrypt reports:\n\n"
        f"{_indented_block(native_error)}"
    )


def compound_boundary_continuation(
    *,
    accepted_prefix: str,
    accepted_effect: str,
    accepted_stage_count: int,
) -> str:
    """State strategy-preserving options after an explanation-only result."""

    accepted_inline = markdown_inline_code(accepted_prefix)
    if accepted_effect == "accepted_changed":
        unit = "step" if accepted_stage_count == 1 else "prefix"
        return (
            f"If you want to continue from the goal produced by that {unit}, "
            f"submit {accepted_inline} separately. You may instead replace "
            "the failing suffix and resubmit the compound. The compiler does "
            "not choose between these options."
        )
    return (
        f"Submitting {accepted_inline} separately would not change the goal. "
        "Repair the failing suffix or choose a different tactic; the compiler "
        "does not choose between these options."
    )


def checked_goal_reference(handoff: RecoveryHandoff | None) -> str:
    """Name the exact goal in which a failed operation was checked."""

    if handoff is not None and handoff.prefix_changes_state:
        return (
            "the temporary goal produced by "
            + markdown_inline_code(handoff.accepted_prefix_tactic)
        )
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


def markdown_inline_code(value: str) -> str:
    """Fence one exact dynamic value without assuming it contains no ticks."""

    fence = "`"
    while fence in value:
        fence += "`"
    return f"{fence}{value}{fence}"


def _indented_block(value: str) -> str:
    return "  " + value.replace("\n", "\n  ")
