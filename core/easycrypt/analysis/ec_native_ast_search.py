"""EasyCrypt native AST/operator search frontend.

This pass derives conservative ``-search-skeleton`` queries from the current
goal and consumes previous search tool artifacts as typed lemma-inspection
candidates.  It does not run EasyCrypt itself.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from core.easycrypt.analysis.ec_utils import (
    as_dict as _dict,
    as_list as _list,
    dedupe_stripped_strings as _dedupe_strings,
)
from core.easycrypt.analysis.ec_pr_obligations import (
    native_ast_pr_arithmetic_shape,
)


NATIVE_AST_SEARCH_SCHEMA_VERSION = 1
NATIVE_AST_SEARCH_KIND = "easycrypt_native_ast_search"

NATIVE_AST_KNOWN_OPS = frozenset({
    "abs",
    "all",
    "card",
    "cat",
    "dom",
    "drop",
    "eq_except",
    "fdom",
    "filter",
    "foldl",
    "foldr",
    "get",
    "has",
    "iota",
    "is_lossless",
    "iter",
    "ler",
    "lossless",
    "map",
    "mem",
    "mu",
    "mu1",
    "mu_bounded",
    "nth",
    "oget",
    "perm_eq",
    "pred1",
    "predI",
    "predU",
    "range",
    "rcons",
    "set",
    "size",
    "support",
    "take",
    "uniq",
    "zip",
})

NATIVE_AST_STOP_TOKENS = frozenset({
    "Current",
    "Type",
    "variables",
    "none",
    "left",
    "right",
    "pre",
    "post",
    "true",
    "false",
    "forall",
    "exists",
    "fun",
    "let",
    "if",
    "then",
    "else",
    "with",
    "glob",
    "res",
    "main",
    "init",
    "game",
    "Pr",
    "int",
    "real",
    "bool",
    "unit",
    "list",
    "option",
    "module",
    "proc",
    "call",
    "inline",
    "wp",
    "sp",
    "smt",
    "auto",
})


def build_native_ast_search_frontend(
    *,
    session_dir: str | Path | None,
    parsed: dict[str, Any],
    goal_type: str,
    goal_text: str,
) -> dict[str, Any]:
    """Build EC-native AST search requests and consume prior search hits."""
    suggested = native_ast_search_queries(parsed, goal_type, goal_text)
    tool_data = scan_native_ast_search_tool_views(session_dir)
    suggested_queries = {
        str(item.get("query") or "")
        for item in suggested
        if isinstance(item, dict) and str(item.get("query") or "")
    }
    observed_queries = [
        item for item in _list(tool_data.get("queries"))
        if (
            isinstance(item, dict)
            and str(item.get("query") or "") in suggested_queries
        )
    ]
    hits = [
        item for item in _list(tool_data.get("hits"))
        if (
            isinstance(item, dict)
            and str(item.get("query") or "") in suggested_queries
        )
    ]
    seen_queries = {
        str(item.get("query") or "")
        for item in observed_queries
    }
    pending = [
        item for item in suggested
        if str(item.get("query") or "") not in seen_queries
    ]
    artifacts = _dedupe_strings(
        [
            str(item.get("artifact") or "")
            for item in observed_queries + hits
            if isinstance(item, dict) and str(item.get("artifact") or "")
        ],
    )
    return {
        "available": bool(pending or hits),
        "suggested_queries": pending,
        "observed_queries": observed_queries,
        "hits": hits,
        "tool_artifacts": artifacts,
        "source": "easycrypt_native_search",
    }


def native_ast_search_queries(
    parsed: dict[str, Any],
    goal_type: str,
    goal_text: str,
) -> list[dict[str, Any]]:
    if not str(goal_text or "").strip():
        return []
    if str(goal_type or "") not in {
        "ambient",
        "probability",
        "pRHL",
        "equiv",
        "hoare",
        "phoare",
        "eager",
    }:
        return []
    text = native_ast_goal_body(goal_text)
    tokens = native_ast_operator_tokens(text)
    queries: list[dict[str, Any]] = []

    def add(query: str, reason: str) -> None:
        clean = re.sub(r"\s+", " ", query).strip()
        if not clean or "'" in clean:
            return
        if clean in {str(item.get("query") or "") for item in queries}:
            return
        queries.append({
            "query": clean,
            "reason": reason,
            "action": f"-search-skeleton '{clean}'",
        })

    has = set(tokens)
    pr_shape = native_ast_pr_arithmetic_shape(parsed, goal_type, text)
    if pr_shape in {
        "absolute_pr_difference_bound",
        "additive_pr_inequality",
        "probability_inequality",
    }:
        if pr_shape == "additive_pr_inequality" or (
            pr_shape == "absolute_pr_difference_bound" and "+" in text
        ):
            add(
                "mu predU",
                "Goal is a Pr additive/union-style bound; EC native search can retrieve probability union/split lemmas such as mu_or.",
            )
        add(
            "( <= ) mu",
            "Goal is a Pr inequality; EC native search can retrieve probability upper-bound lemmas while staying at the Pr layer.",
        )

    if {"take", "mem"} <= has:
        add("take mem", "Goal mentions membership in/around `take`; EC native search can retrieve operator-level lemmas such as take/mem facts.")
    if {"take", "size"} <= has:
        add("take size", "Goal relates `take` and `size`; use native operator-AND search before guessing lemma names.")
    if {"drop", "size"} <= has:
        add("drop size", "Goal relates `drop` and `size`; use native operator-AND search before guessing lemma names.")
    if {"cat", "size"} <= has:
        add("cat size", "Goal relates list concatenation and size; use native operator-AND search.")
    if {"iter", "cat"} <= has:
        add("iter cat", "Goal relates iterator structure and concatenation; EC native search can retrieve iterator-concat decomposition lemmas before guessing names.")
    if {"iter", "filter"} <= has:
        add("iter filter", "Goal relates iterator structure and filtered partitions; use native operator-AND search before hand-searching lemma names.")
    if {"filter", "cat"} <= has:
        add("filter cat", "Goal relates filtering and concatenation; native search can surface partition/reassembly facts.")
    if {"map", "mem"} <= has:
        add("map mem", "Goal relates map and membership; native search should surface map/mem lemmas.")
    if {"filter", "mem"} <= has:
        add("filter mem", "Goal relates filter and membership; native search should surface filter/mem lemmas.")
    if {"get", "set"} <= has:
        add("get set", "Goal contains map lookup after update; native search should surface get/set rewrite lemmas.")
    if {"fdom", "set"} <= has:
        add("fdom set", "Goal contains finite-map domain/update facts; native search should surface domain/set lemmas.")
    if {"oget", "get"} <= has:
        add("oget get", "Goal contains option extraction from a map lookup; native search should surface oget/get lemmas.")
    if {"eq_except", "set"} <= has:
        add("eq_except set", "Goal contains map-update extensionality; native search should surface eq_except/set lemmas.")

    if not queries and len(tokens) >= 2:
        add(
            " ".join(tokens[:3]),
            "ProofIR extracted multiple EC operator tokens from the current goal; use native AST/operator search before regex search.",
        )
    elif not queries and tokens[:1] and tokens[0] in {
        "fdom",
        "oget",
        "eq_except",
        "mu_bounded",
        "support",
        "is_lossless",
    }:
        add(
            tokens[0],
            "ProofIR extracted a distinctive EC operator token from the current goal; native AST search is more precise than regex search.",
        )
    return queries[:4]


def native_ast_goal_body(goal_text: str) -> str:
    text = str(goal_text or "")
    text = re.sub(r"^\[\d+\|[^\]]+\]>.*$", " ", text, flags=re.MULTILINE)
    text = re.sub(r"-{5,}", " ", text)
    return text


def native_ast_operator_tokens(text: str) -> list[str]:
    out: list[str] = []

    def add(token: str) -> None:
        if token and token not in out:
            out.append(token)

    source = str(text or "")
    if r"\in" in source:
        add("mem")
    if ".[" in source:
        add("get")
    if "<-" in source and ".[" in source:
        add("set")
    if "++" in source:
        add("cat")
    if re.search(r"(?:^|[.\s])iters?\s*(?:\(|\b)", source):
        add("iter")
    if "List.filter" in source:
        add("filter")
    if re.search(r"\b(fdom|dom)\b", source):
        add("fdom")
    for match in re.finditer(r"(?<![.\w'])([A-Za-z_][A-Za-z0-9_']*)\b", source):
        token = match.group(1)
        if token in NATIVE_AST_STOP_TOKENS:
            continue
        if token not in NATIVE_AST_KNOWN_OPS:
            continue
        add(token)
    return out


def scan_native_ast_search_tool_views(
    session_dir: str | Path | None,
) -> dict[str, Any]:
    if session_dir is None:
        return {"queries": [], "hits": [], "artifacts": []}
    root = Path(session_dir) / "tool_views"
    if not root.exists():
        return {"queries": [], "hits": [], "artifacts": []}
    queries: list[dict[str, Any]] = []
    hits: list[dict[str, Any]] = []
    artifacts: list[str] = []
    seen_hits: set[tuple[str, str]] = set()
    for path in sorted(root.glob("*.json"), key=lambda p: p.stat().st_mtime):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(data, dict) or data.get("tool") != "search-skeleton":
            continue
        query = search_skeleton_query(data)
        artifacts.append(str(path))
        queries.append({"query": query, "artifact": str(path)})
        text = str(_dict(data.get("debug")).get("legacy_text") or "")
        if not text:
            for item in _list(_dict(data.get("evidence")).get("raw")):
                if isinstance(item, dict) and item.get("preview"):
                    text = str(item.get("preview") or "")
                    break
        for hit in parse_search_skeleton_hits(text):
            key = (str(hit.get("name") or ""), query)
            if not key[0] or key in seen_hits:
                continue
            seen_hits.add(key)
            enriched = dict(hit)
            enriched["query"] = query
            enriched["artifact"] = str(path)
            hits.append(enriched)
    return {"queries": queries, "hits": hits, "artifacts": artifacts}


def search_skeleton_query(data: dict[str, Any]) -> str:
    for item in _list(_dict(data.get("evidence")).get("context")):
        if not isinstance(item, dict):
            continue
        query = _dict(item.get("query"))
        value = str(query.get("query") or "")
        if value:
            return value
    return ""


def parse_search_skeleton_hits(text: str) -> list[dict[str, Any]]:
    source = str(text or "")
    if "[SKELETON-HITS]" not in source:
        return []
    start_re = re.compile(
        r"^(?:\(\*\s*[\w.]+\s*\*\)\s*\n)?(?P<kind>local\s+lemma|lemma|axiom)\s+"
        r"(?P<name>[A-Za-z_][A-Za-z0-9_']*)\b",
        re.MULTILINE,
    )
    matches = list(start_re.finditer(source))
    out: list[dict[str, Any]] = []
    for idx, match in enumerate(matches):
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(source)
        declaration = source[match.start():end].strip()
        declaration = re.sub(r"\n{3,}.*\Z", "", declaration, flags=re.DOTALL).strip()
        out.append({
            "name": match.group("name"),
            "kind": match.group("kind").replace("local ", ""),
            "declaration": declaration,
            "source": "search_skeleton_tool_view",
        })
    return out[:12]


__all__ = [
    "NATIVE_AST_KNOWN_OPS",
    "NATIVE_AST_SEARCH_KIND",
    "NATIVE_AST_SEARCH_SCHEMA_VERSION",
    "NATIVE_AST_STOP_TOKENS",
    "build_native_ast_search_frontend",
    "native_ast_goal_body",
    "native_ast_operator_tokens",
    "native_ast_search_queries",
    "parse_search_skeleton_hits",
    "scan_native_ast_search_tool_views",
    "search_skeleton_query",
]
