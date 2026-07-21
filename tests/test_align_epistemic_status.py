from pathlib import Path


import sys

import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from core.easycrypt.analysis.swap_align import (  # type: ignore  # noqa: E402
    AlignResult,
    Match,
    Statement,
    compute_swap_plan,
    format_analysis,
)
from core.easycrypt.commands.speculative_commands import (  # type: ignore  # noqa: E402
    _align_epistemic_evidence,
    _align_guidance_from_output,
    _recommendations_from_tactic_lines,
)


def test_align_separates_static_blocked_from_suggested_swaps() -> None:
    left = [
        Statement(1, "(m0, m1) <@ A.choose(pk)", "CALL", "", "A.choose"),
        Statement(2, "y <$ dt", "SAMPLE", "dt", ""),
    ]
    right = [
        Statement(1, "y <$ dt", "SAMPLE", "dt", ""),
        Statement(2, "(m0, m1) <@ A.choose(gx)", "CALL", "", "A.choose"),
    ]
    matches = [Match(2, 1, "SAMPLE", "dt", "high")]

    swaps, blocked = compute_swap_plan(left, right, matches)

    assert swaps == []
    assert blocked
    assert blocked[0]["epistemic_status"] == "static_blocked_uncertified"
    assert "not an EasyCrypt rejection" in blocked[0]["not_meaning"]

    text = format_analysis(AlignResult(
        left=left,
        right=right,
        matches=matches,
        unmatched_left=[1],
        unmatched_right=[2],
        swaps=swaps,
        blocked_swaps=blocked,
    ))

    assert "NO STATICALLY CERTIFIED SWAPS" in text
    assert "STATICALLY BLOCKED / UNCERTIFIED CANDIDATES" in text
    assert "NOT an EasyCrypt rejection" in text
    assert "NO SWAPS NEEDED" not in text


def test_align_toolview_marks_candidates_as_route_dependent_frames() -> None:
    text = """
STATICALLY CERTIFIED SWAP FRAMES:
  epistemic_status: static_candidate_uncertified_by_ec
  swap{1} 7 -5.    (* move sample dt to row 2 *)

STATICALLY BLOCKED / UNCERTIFIED CANDIDATES:
  L7 <-> R2 dt:
    candidate: swap{1} 7 -5.   blocked_by: crosses CALL A.choose
"""
    recs = _recommendations_from_tactic_lines(
        "align",
        "alignment_tactic",
        text,
        producer="align",
        why="static candidate",
        action_type="tactic_candidate",
        metadata={"epistemic_status": "static_candidate_uncertified_by_ec"},
    )

    assert [r["action"] for r in recs] == ["swap{1} 7 <offset>."]
    assert recs[0]["action_type"] == "strategy_hint"
    assert recs[0]["metadata"]["epistemic_status"] == (
        "static_candidate_uncertified_by_ec"
    )
    assert recs[0]["metadata"]["concrete_static_candidate"] == "swap{1} 7 -5."
    assert recs[0]["metadata"]["offset_policy"] == "route_dependent"
    assert "requires_instantiation" not in recs[0]["metadata"]

    evidence = _align_epistemic_evidence(text)
    statuses = {e["status"] for e in evidence}
    assert "static_candidate_uncertified_by_ec" in statuses
    assert "static_blocked_uncertified" in statuses

    guidance = _align_guidance_from_output(text)
    assert guidance["primary_action"] == "choose_offset_then_commit"
    assert guidance["blocked_semantics"]["not_meaning"] == (
        "Swap is impossible or EC-rejected."
    )


def main() -> int:
    tests = [
        test_align_separates_static_blocked_from_suggested_swaps,
        test_align_toolview_marks_candidates_as_route_dependent_frames,
    ]
    for test in tests:
        test()
    print("PASS test_align_epistemic_status")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
