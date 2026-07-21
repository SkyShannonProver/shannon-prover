"""Tests for ProofIR action/menu rendering helpers."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from core.easycrypt.analysis.ec_menu_actions import (  # noqa: E402
    ambient_named_closer_menu_items,
    menu_item,
    native_ast_search_menu_items,
    safe_id,
    semantic_pr_bound_menu_items,
)


def test_menu_item_and_safe_id_keep_stable_shape() -> None:
    item = menu_item(
        "x",
        tactic="-where foo.",
        tactic_family="signature_lookup",
        action_type="inspection_action",
        cost="free",
        why="inspect foo",
        program_rank=3,
    )

    assert safe_id("A lemma/name") == "A_lemma_name"
    assert item["confidence"] == "medium"
    assert item["preconditions"] == []
    assert item["program_rank"] == 3
    assert item["scheduler_role"] == "typed_resource_lookup"
    assert item["scheduler"]["scheduler_role"] == "typed_resource_lookup"


def test_ambient_named_closer_menu_items_render_probe_action() -> None:
    items = ambient_named_closer_menu_items({
        "ambient_named_closers": [{
            "lemma": "dblock_ll",
            "tactic": "exact: dblock_ll.",
            "source_path": "Context.ec",
        }],
    })

    assert items[0]["id"] == "ambient_exact_dblock_ll"
    assert items[0]["tactic"] == "exact: dblock_ll."
    assert items[0]["action_type"] == "tactic_candidate"


def test_semantic_pr_bound_menu_items_render_where_lookup() -> None:
    items = semantic_pr_bound_menu_items({
        "semantic_pr_bound_candidates": [{
            "lemma": "OddlyNamedBound",
            "score": 9,
            "semantic_tags": ["pr_bound"],
            "pr_game_keys": ["Game(A,PLog)"],
        }],
    })

    assert items[0]["id"] == "semantic_pr_bound_OddlyNamedBound"
    assert items[0]["tactic"] == "-where OddlyNamedBound"
    assert items[0]["action_type"] == "inspection_action"
    assert items[0]["cost_factors"]["score"] == 9


def test_semantic_pr_bound_menu_items_skip_when_arithmetic_plan_exists() -> None:
    assert semantic_pr_bound_menu_items({
        "pr_path_plan": {
            "arithmetic_plan": {"available": True, "shape": "additive_pr_inequality"},
        },
        "semantic_pr_bound_candidates": [{"lemma": "Bound"}],
    }) == []


def test_native_ast_search_menu_items_prefer_hits_over_queries() -> None:
    items = native_ast_search_menu_items({
        "native_ast_search": {
            "available": True,
            "hits": [{
                "name": "mem_take",
                "query": "take mem",
                "kind": "lemma",
                "artifact": "tool_views/search.json",
            }],
            "suggested_queries": [{
                "query": "take mem",
                "action": "-search-skeleton 'take mem'",
            }],
        },
    })

    assert len(items) == 1
    assert items[0]["id"] == "native_ast_hit_mem_take"
    assert items[0]["tactic"] == "-where mem_take"


def test_native_ast_search_menu_items_render_pending_query() -> None:
    items = native_ast_search_menu_items({
        "native_ast_search": {
            "available": True,
            "suggested_queries": [{
                "query": "take mem",
                "action": "-search-skeleton 'take mem'",
                "reason": "look up take/mem facts",
            }],
        },
    })

    assert items[0]["id"] == "native_ast_search_0"
    assert items[0]["tactic"] == "-search-skeleton 'take mem'"
    assert items[0]["cost_factors"]["query"] == "take mem"


# ── fact vs guidance: the compiler pushes state-derived FACTS, not move GUIDANCE ──

import pytest  # noqa: E402

from core.easycrypt.analysis.ec_action_contracts import (  # noqa: E402
    classify_info_kind,
    is_hardcoded_noise_move,
)


# A GUIDANCE menu item is dropped from candidate_menu at the producer; a FACT is
# kept. This table is the keep/drop spec — keep it in sync with classify_info_kind.
_GUIDANCE_CASES = [
    # bare hardcoded tactic literals — dropped in ANY category (incl. probe_tactic)
    ("strategy_hint", "wp.", False, False),
    ("strategy_hint", "sp.", False, False),
    ("probe_tactic", "sim.", False, False),
    ("probe_tactic", "byequiv => //.", False, False),
    ("probe_tactic", "auto => />.", False, False),
    ("probe_tactic", "smt().", False, False),
    ("strategy_hint", "inline *.", False, False),
    # un-filled placeholder templates
    ("strategy_hint", "while (<loop invariant>).", False, False),
    ("strategy_hint", "splitwhile{1} 3: (<split of 5 <= r>).", False, False),
    ("strategy_hint", "conseq (_: <weaker postcondition>) => />.", False, False),
    ("strategy_hint", "swap <range> <offset>.", False, False),
    # route-plan prose
    ("strategy_hint", "Probabilistic VC plan: loss accounting via rnd", False, False),
    ("strategy_hint", "Structured procedure frontier: loop; primary: use sp", False, False),
    # fill-in template (requires instantiation), strategy bucket
    ("strategy_hint", "call (_: Inv)", True, False),
]

_FACT_CASES = [
    # state-derived openers
    ("probe_tactic", "move=> H.", False, False),
    ("probe_tactic", "proc.", False, False),
    ("probe_tactic", "rewrite /predT.", False, False),
    # goal-FILLED tactics (no placeholder)
    ("strategy_hint", "rcondt{1} 3; first auto.", False, False),
    ("strategy_hint", "case: (j = i).", False, False),
    ("strategy_hint", "while (0 <= j < Top.N).", False, False),
    ("strategy_hint", "call (_: inv_cpa /\\ ={glob A}).", False, False),
    ("strategy_hint", "inline G8.distinguish.", False, False),
    # source-position swap frames are mechanical facts; only the offset remains route-picked
    ("strategy_hint", "swap{2} 12 <offset>.", False, False),
    # Inspect-map readouts and resource lookups
    ("strategy_hint", "Inspect current procedure region summary: guard j = i.", False, False),
    ("inspection_action", "-program-json", False, False),
    ("inspection_action", "-where Foo", False, False),
    # a daemon-VERIFIED move is a fact even when bare
    ("probe_tactic", "wp.", False, True),
    # a requires_instantiation flag outside the strategy bucket is not a template
    ("inspection_action", "-where Bar", True, False),
]


@pytest.mark.parametrize("action_type, tactic, requires_instantiation, verified", _GUIDANCE_CASES)
def test_classify_info_kind_marks_guidance(action_type, tactic, requires_instantiation, verified) -> None:
    item = {
        "action_type": action_type,
        "tactic": tactic,
        "requires_instantiation": requires_instantiation,
        "verified": verified,
    }
    assert classify_info_kind(item) == "guidance"


@pytest.mark.parametrize("action_type, tactic, requires_instantiation, verified", _FACT_CASES)
def test_classify_info_kind_marks_fact(action_type, tactic, requires_instantiation, verified) -> None:
    item = {
        "action_type": action_type,
        "tactic": tactic,
        "requires_instantiation": requires_instantiation,
        "verified": verified,
    }
    assert classify_info_kind(item) == "fact"


def test_is_hardcoded_noise_move_does_not_match_filled_less_than() -> None:
    # A genuine `<` (less-than) in a goal-FILLED tactic must NOT read as a placeholder.
    assert is_hardcoded_noise_move("while (0 <= j < Top.N).") is False
    assert is_hardcoded_noise_move("while (<loop invariant>).") is True
    assert is_hardcoded_noise_move("swap <range> <offset>.") is True
    assert is_hardcoded_noise_move("swap{2} 12 <offset>.") is False


def test_menu_item_stamps_info_kind() -> None:
    # menu_item() runs through normalize_action_candidate, which stamps info_kind.
    guidance = menu_item(
        "g", tactic="wp.", tactic_family="procedure_transform",
        action_type="strategy_hint", cost="cheap", why="bare shape",
    )
    fact = menu_item(
        "f", tactic="case: (j = i).", tactic_family="procedure_transform",
        action_type="strategy_hint", cost="cheap", why="goal-filled",
    )
    assert guidance["info_kind"] == "guidance"
    assert fact["info_kind"] == "fact"
