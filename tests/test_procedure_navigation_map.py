"""Tests for the positioned obligation navigation map (Q1 / P).

The procedure frontend already computes the body's straight-line prefix, branch
guards, and loop frontiers WITH positions; the view used to collapse them to bare
tactic names. This projection surfaces the positions so the agent picks a
POSITIONED tactic (wp -N / rcondt{i} k / where the next while is) by reading
structure instead of guessing offsets. It must stay facts-only (never pick a
tactic or a branch direction).
"""
from __future__ import annotations

import sys
from pathlib import Path

import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from core.easycrypt.analysis.ec_procedure_actions import procedure_navigation_map  # noqa: E402


def _frontend() -> dict:
    return {
        "available": True,
        "straight_line_prefix": [
            {"side": "left", "side_index": 1, "statement_order": i,
             "kind": "ASSIGN", "statement": f"x{i} <- e"}
            for i in range(1, 9)
        ],
        "branch_guards": [
            {"side": "left", "side_index": 1, "statement_order": 9,
             "statement_path": "9", "guard": "if (size lbad1 <= nth0)",
             "condition": "size lbad1 <= nth0"},
        ],
        "loop_frontiers": [
            {"side": "left", "side_index": 1, "statement_order": 12,
             "statement": "while (i < n)"},
        ],
        "frontier_plan": {
            "frontier_kind": "branch_frontier",
            "next_structural_region": {"statement_order": 9},
        },
    }


def test_absorb_depth_gives_the_wp_sp_offset() -> None:
    nav = procedure_navigation_map(_frontend())
    left = nav["absorb_depth"]["left"]
    assert left["absorbable_statements"] == 8
    assert left["through_order"] == 8
    # `sp` takes both sides at once — a combined `sp <L> <R>` hint, not per-side
    assert "sp 8 0" in nav["absorb_depth"]["sp_hint"]


def test_absorb_depth_uses_alignment_count_on_asymmetric_setup() -> None:
    """Regression: the body parser under-counts an asymmetric two-column setup
    (right-only leading statements dropped) — straight_line_prefix sees right=2
    while the alignment correctly sees 5. The alignment count must win, so
    absorb_depth no longer contradicts the alignment row (the bug that made the
    agent distrust the number and burn ~90s)."""
    frontend = {
        "available": True,
        "straight_line_prefix": [
            {"side": "left", "side_index": 1, "statement_order": 1, "kind": "ASSIGN"},
            {"side": "left", "side_index": 1, "statement_order": 2, "kind": "ASSIGN"},
            # parser only captured the aligned tail on the right (2 of 5)
            {"side": "right", "side_index": 2, "statement_order": 4, "kind": "ASSIGN"},
            {"side": "right", "side_index": 2, "statement_order": 5, "kind": "ASSIGN"},
        ],
        "branch_guards": [], "loop_frontiers": [], "frontier_plan": {},
    }
    nav = procedure_navigation_map(frontend, setup_counts=(2, 5))
    ad = nav["absorb_depth"]
    assert ad["left"]["absorbable_statements"] == 2
    assert ad["right"]["absorbable_statements"] == 5  # alignment count, not 2
    assert "alignment" in ad["right"]["note"]
    assert "sp 2 5" in ad["sp_hint"]
    # without the alignment count it would (wrongly) stay at the parsed 2
    nav0 = procedure_navigation_map(frontend)
    assert nav0["absorb_depth"]["right"]["absorbable_statements"] == 2


def test_branch_guard_is_positioned_but_direction_left_to_agent() -> None:
    nav = procedure_navigation_map(_frontend())
    g = nav["branch_guards"][0]
    assert g["at_order"] == 9
    assert g["guard"] == "size lbad1 <= nth0"
    # both rcond forms offered; direction explicitly deferred to the agent
    assert "rcondt{1} 9" in g["rcond_forms"] and "rcondf{1} 9" in g["rcond_forms"]
    assert "yours to decide" in g["rcond_forms"]


def test_loop_and_next_frontier_positions_surface() -> None:
    nav = procedure_navigation_map(_frontend())
    assert nav["loop_frontiers"][0]["at_order"] == 12
    assert nav["next_frontier"] == {"kind": "branch_frontier", "at_order": 9}


def test_facts_only_no_tactic_chosen() -> None:
    nav = procedure_navigation_map(_frontend())
    # the map states positions/forms; it never emits a single chosen runnable tactic
    assert "pick the tactic" in nav["how_to_use"]


def test_unavailable_or_empty_frontend_is_silent() -> None:
    assert procedure_navigation_map({"available": False}) == {}
    assert procedure_navigation_map({}) == {}
    # available but no body structure -> empty (self-gating)
    assert procedure_navigation_map({"available": True}) == {}


def main() -> int:
    test_absorb_depth_gives_the_wp_sp_offset()
    test_branch_guard_is_positioned_but_direction_left_to_agent()
    test_loop_and_next_frontier_positions_surface()
    test_facts_only_no_tactic_chosen()
    test_unavailable_or_empty_frontend_is_silent()
    print("PASS test_procedure_navigation_map")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
