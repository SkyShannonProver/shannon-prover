"""Tests for EasyCrypt native AST/operator search frontend."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from core.easycrypt.analysis.ec_native_ast_search import (  # noqa: E402
    build_native_ast_search_frontend,
    native_ast_operator_tokens,
    native_ast_search_queries,
    parse_search_skeleton_hits,
)


def test_operator_tokens_classify_membership_and_take_size() -> None:
    tokens = native_ast_operator_tokens(
        "x \\in take n xs => size (take n xs) <= size xs"
    )

    assert tokens[:3] == ["mem", "take", "size"]


def test_native_ast_search_queries_prefer_specific_operator_pairs() -> None:
    queries = native_ast_search_queries(
        parsed={"goal_type": "ambient"},
        goal_type="ambient",
        goal_text="x \\in take n xs => size (take n xs) <= size xs",
    )

    assert [item["query"] for item in queries] == ["take mem", "take size"]
    assert queries[0]["action"] == "-search-skeleton 'take mem'"


def test_probability_bound_queries_use_native_mu_search() -> None:
    queries = native_ast_search_queries(
        parsed={"goal_type": "probability", "prob_form": "adv_diff_ineq"},
        goal_type="probability",
        goal_text=(
            "`|Pr[G0.main() @ &m : res] - Pr[G1.main() @ &m : res]| <= "
            "Pr[Bad.main() @ &m : bad]"
        ),
    )

    assert [item["query"] for item in queries] == ["( <= ) mu"]


def test_iterator_partition_queries_use_native_operator_search() -> None:
    queries = native_ast_search_queries(
        parsed={"goal_type": "ambient"},
        goal_type="ambient",
        goal_text=(
            "IPNonce.iter (xs ++ ys) = "
            "IPNonce.iter (List.filter p xs ++ List.filter (fun x => ! p x) xs)"
        ),
    )

    names = [item["query"] for item in queries]
    assert names[:3] == ["iter cat", "iter filter", "filter cat"]
    assert queries[0]["action"] == "-search-skeleton 'iter cat'"


def test_parse_search_skeleton_hits_returns_declarations() -> None:
    hits = parse_search_skeleton_hits(
        "[SKELETON-HITS] `search take mem` -> 1 lemma(s)\n\n"
        "lemma mem_take (x : 'a) n xs:\n"
        "  x \\in take n xs => x \\in xs.\n"
    )

    assert hits == [{
        "name": "mem_take",
        "kind": "lemma",
        "declaration": (
            "lemma mem_take (x : 'a) n xs:\n"
            "  x \\in take n xs => x \\in xs."
        ),
        "source": "search_skeleton_tool_view",
    }]


def test_frontend_consumes_only_relevant_search_hits() -> None:
    with tempfile.TemporaryDirectory() as td:
        session = Path(td)
        tool_views = session / "tool_views"
        tool_views.mkdir()
        (tool_views / "search_skeleton_take_mem.json").write_text(
            json.dumps({
                "tool": "search-skeleton",
                "evidence": {
                    "context": [{"query": {"query": "take mem"}}],
                    "raw": [],
                },
                "debug": {
                    "legacy_text": (
                        "[SKELETON-HITS] `search take mem` -> 1 lemma(s)\n\n"
                        "lemma mem_take (x : 'a) n xs:\n"
                        "  x \\in take n xs => x \\in xs.\n"
                    ),
                },
            }),
            encoding="utf-8",
        )
        (tool_views / "search_skeleton_mu.json").write_text(
            json.dumps({
                "tool": "search-skeleton",
                "evidence": {
                    "context": [{"query": {"query": "mu"}}],
                    "raw": [],
                },
                "debug": {
                    "legacy_text": (
                        "[SKELETON-HITS] `search mu` -> 1 lemma(s)\n\n"
                        "lemma mu_mem_le: true.\n"
                    ),
                },
            }),
            encoding="utf-8",
        )
        frontend = build_native_ast_search_frontend(
            session_dir=session,
            parsed={"goal_type": "ambient"},
            goal_type="ambient",
            goal_text="x \\in take n xs => x \\in xs",
        )

    assert frontend["available"] is True
    assert frontend["observed_queries"][0]["query"] == "take mem"
    assert frontend["hits"][0]["name"] == "mem_take"
    assert frontend["suggested_queries"] == []
