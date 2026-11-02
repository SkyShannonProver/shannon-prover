"""``-try`` reports a typed result; its text rendering is never parsed back."""
from __future__ import annotations

from core.easycrypt.session.session_display import (
    chain_try_result,
    single_try_result,
    try_tool_error,
)

GOAL = (
    "Current goal\n\nType variables: <none>\n\na: bool\n"
    "------------------------------------------------------------------------\n"
    "a /\\ a\n[4|check]>\n"
)


def test_an_accepted_tactic_reports_its_residual_goals() -> None:
    result = single_try_result("split.", {
        "accepted": True,
        "goal_after": {"raw": GOAL.replace("a /\\ a", "a"), "is_closed": False, "remaining": 2},
    }, prev_raw=GOAL)

    assert result.accepted is True
    assert (result.goal_after_closed, result.goal_after_remaining) == (False, 2)
    assert not result.no_progress_predicted
    assert result.report == (
        "[TRY] tactic: split.\n[TRY] accepted: True\n"
        "[TRY] goal_after: 2 subgoal(s) remaining\n[TRY] state_unchanged: true\n"
    )


def test_an_accepted_no_op_is_predicted_as_no_progress() -> None:
    result = single_try_result("idtac.", {
        "accepted": True,
        "goal_after": {"raw": GOAL, "is_closed": False, "remaining": 1},
    }, prev_raw=GOAL)

    assert result.no_progress_predicted
    assert "[TRY] PRODUCES NO PROGRESS\n" in result.report


def test_the_result_names_the_checked_tactic_exactly() -> None:
    # The text rendering used to be parsed back, which cut a tactic at its
    # first line and read report markers out of the tactic itself.
    tactic = "move=> ha\n  hb."
    result = single_try_result(tactic, {"accepted": True, "goal_after": {}})
    assert result.tactic == tactic

    marker = single_try_result("PRODUCES NO PROGRESS.", {"accepted": False})
    assert not marker.no_progress_predicted


def test_a_rejected_tactic_reports_its_error_kind() -> None:
    result = single_try_result("apply nope.", {
        "accepted": False, "error": {"kind": "unknown_lemma", "raw": "x"},
    })

    assert result.accepted is False
    assert result.error_kind == "unknown_lemma"
    assert not result.tool_error


def test_a_chain_reports_the_last_accepted_step() -> None:
    result = chain_try_result(" move=> h. split. ", ["move=> h.", "split."], {
        "accepted": True, "final_closed": False,
        "steps": [
            {"accepted": True, "goal_after": {"remaining": 1}},
            {"accepted": True, "goal_after": {"remaining": 3}},
        ],
    })

    assert result.tactic == "move=> h. split."
    assert (result.accepted, result.goal_after_remaining) == (True, 3)

    closed = chain_try_result("a. b.", ["a.", "b."], {"accepted": True, "final_closed": True})
    assert (closed.goal_after_closed, closed.goal_after_remaining) == (True, 0)


def test_a_check_that_could_not_run_is_a_tool_error() -> None:
    result = try_tool_error(" auto ", "[TRY] error: daemon connection lost.\n")

    assert result.tool_error and result.accepted is None
    assert result.tactic == "auto"
