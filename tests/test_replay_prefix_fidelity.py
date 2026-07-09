"""Replay-prefix fidelity regressions (step4_1 r2 respawn, 2026-06-09).

A parent-committed hypothesis rewrite (`rewrite /inv /inv_cpa in H.`) was
silently dropped during bootstrap prefix replay: ``extract_goal_body`` treated
a "Current goal" header at line index 0 (the canonical compressed-display
shape) as NOT FOUND and degraded to a last-80-lines window, so
``detect_no_progress`` compared only the unchanged conclusion tails of the
pre/post displays and auto-reverted the step as a false "text-equal" no-op.
The bootstrap record then echoed the 73-step request while the session's
actual history held 72 steps, shifting every live step number in
replay/audit reconstructions by +1.

Covers:
- ``extract_goal_body`` treats a header at index 0 as found (full body).
- ``detect_no_progress`` sees a hypothesis-only change high in a long
  compressed display as progress.
- A true no-op is still flagged.
- ``replay_prefix_divergence`` reports dropped/added steps.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from core.easycrypt.session_no_progress import detect_no_progress  # noqa: E402
from core.easycrypt.session_state import extract_goal_body  # noqa: E402
from workflow.proof_management.repl_session import (  # noqa: E402
    replay_prefix_divergence,
)


def _compressed_display(hypothesis_line: str) -> str:
    """A compressed current.out-style display: header at line 0, a hypothesis
    block near the top, and a conclusion long enough (>80 lines) that the old
    tail-window comparison never saw the hypothesis."""
    conclusion = [f"   conclusion_line_{i} /\\" for i in range(110)]
    lines = [
        "Current goal (remaining: 10)",
        "",
        "Type variables: <none>",
        "",
        "&1: {x : int}",
        f"H: {hypothesis_line}",
        "r4L: forall (rR : poly_in), rR \\in dpoly_in => rR = rR",
        "-" * 72,
        *conclusion,
        "[431|check]>",
    ]
    return "\n".join(lines)


def test_extract_goal_body_header_at_line_zero_keeps_full_body() -> None:
    display = _compressed_display("inv A B C (folded)")
    assert display.splitlines()[0].startswith("Current goal")
    body = extract_goal_body(display)
    assert "H: inv A B C (folded)" in body
    assert "conclusion_line_0" in body


def test_extract_goal_body_header_later_still_works() -> None:
    display = "replay transcript noise\n" + _compressed_display("inv A B C")
    body = extract_goal_body(display)
    assert "H: inv A B C" in body
    assert "replay transcript noise" not in body


def test_hypothesis_only_rewrite_is_progress() -> None:
    # The phantom-step shape: the tactic unfolds a definition inside
    # hypothesis H; the conclusion (and the goal count) are unchanged.
    prev = _compressed_display("inv A B C (folded)")
    curr = _compressed_display("A = B /\\ unfolded_invariant_body C")
    is_noop, reason = detect_no_progress(prev, curr, has_new_error=False)
    assert not is_noop, (
        f"hypothesis-only rewrite flagged no-progress ({reason}): the goal-"
        "body extraction is windowing out the hypotheses again"
    )


def test_true_noop_still_detected() -> None:
    display = _compressed_display("inv A B C (folded)")
    is_noop, reason = detect_no_progress(
        display, display, has_new_error=False,
    )
    assert is_noop
    assert reason == "text-equal"


def test_replay_prefix_divergence_reports_dropped_step() -> None:
    requested = ["wp.", "rewrite /inv in H.", "skip."]
    committed = ["wp.", "skip."]
    divergence = replay_prefix_divergence(requested, committed)
    assert divergence["dropped"] == [
        {"index": 2, "tactic": "rewrite /inv in H."},
    ]
    assert divergence["added"] == []


def test_replay_prefix_divergence_reports_added_step() -> None:
    requested = ["wp.", "skip."]
    committed = ["wp.", "auto.", "skip."]
    divergence = replay_prefix_divergence(requested, committed)
    assert divergence["dropped"] == []
    assert divergence["added"] == [{"index": 2, "tactic": "auto."}]


def test_replay_prefix_divergence_equal_sequences_are_clean() -> None:
    steps = ["wp.", "skip."]
    divergence = replay_prefix_divergence(steps, list(steps))
    assert divergence == {"dropped": [], "added": []}
