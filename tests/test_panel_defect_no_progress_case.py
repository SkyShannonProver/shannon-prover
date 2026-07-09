"""Panel-defect #3 root: the text-diff-only NO-PROGRESS heuristic false-positived on
hypothesis-adding / context-splitting tactics (`case (cond)`), which increase the open
goal count while leaving the printed first-goal body unchanged, and got auto-reverted.

See docs/reports/insights/l4_panel_defects_equiv_step4.md (Defect #3). The fix adds an
open-goal-count-increase guard to detect_no_progress: a strict increase in EC's
`(remaining: N)` count is genuine progress. A truly idempotent tactic (same body, same
count) is still flagged.
"""
from __future__ import annotations

from core.easycrypt.session_no_progress import detect_no_progress, _structural_fingerprint

# Goal body is byte-identical; only a hypothesis + a new subgoal were added (remaining 1->2).
_PREV = """Current goal

Type variables: <none>

a: bool
------------------------------------------------------------------------
foo => bar
[3|check]>"""

_CURR_CASE = """Current goal (remaining: 2)

Type variables: <none>

a: bool
hcond: cond
------------------------------------------------------------------------
foo => bar
[4|check]>"""

# A true no-op: identical body, identical (implicit) count of 1.
_CURR_NOOP = _PREV.replace("[3|check]", "[4|check]")


def test_case_that_adds_a_subgoal_is_progress() -> None:
    is_noop, reason = detect_no_progress(_PREV, _CURR_CASE, has_new_error=False)
    assert is_noop is False, (is_noop, reason)


def test_true_idempotent_tactic_is_still_no_progress() -> None:
    is_noop, reason = detect_no_progress(_PREV, _CURR_NOOP, has_new_error=False)
    assert is_noop is True
    assert reason == "text-equal"


def test_new_error_is_never_no_progress() -> None:
    is_noop, reason = detect_no_progress(_PREV, _CURR_NOOP, has_new_error=True)
    assert is_noop is False


# The harder, real path: a pRHL `case` whose split condition lands on the OTHER
# subgoal, so the FIRST subgoal's body, hypotheses, and structural fingerprint are
# byte-identical to the parent — only the open-goal count rises (1 -> 2). Pre-fix this
# took the `structural-fingerprint-equal` branch and was auto-reverted.
_PRHL_PREV = (
    "Current goal\n\nType variables: <none>\n\n"
    "&1 &2 : (glob M)\n"
    "------------------------------------------------------------------------\n"
    "equiv[ M.f ~ M.g : ={x} ==> ={res} ]\n[12|check]>"
)
_PRHL_CURR_CASE = (
    "Current goal (remaining: 2)\n\nType variables: <none>\n\n"
    "&1 &2 : (glob M)\n"
    "------------------------------------------------------------------------\n"
    "equiv[ M.f ~ M.g : ={x} ==> ={res} ]\n[13|check]>"
)


def test_fingerprint_identical_case_split_is_progress_via_count() -> None:
    # Sanity: the fingerprint really IS identical (so without the count guard this
    # would be flagged structural-fingerprint-equal).
    assert (
        _structural_fingerprint(_PRHL_PREV)
        == _structural_fingerprint(_PRHL_CURR_CASE)
    )
    is_noop, reason = detect_no_progress(
        _PRHL_PREV, _PRHL_CURR_CASE, has_new_error=False
    )
    assert is_noop is False, (is_noop, reason)
