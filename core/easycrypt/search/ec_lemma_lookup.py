"""Online lookup over the offline-built EC stdlib lemma index.

The companion `build_lemma_index.py` script scans `easycrypt-src/
theories/` for lemma signatures and emits `lemma_index.json` (~1MB,
~4000 lemmas across 700+ ops). This module loads that JSON once at
import time (~10ms) and provides fast op-based lookup for runtime
hint-surfacing.

Public API:
    lookup_for_goal(goal_text, max_per_op=8, max_total=15)
        Scan ``goal_text`` for op tokens, return up to ``max_total``
        relevant lemma signatures. Used to populate `[AUTO-LEMMA-HINTS]`
        in `-goal-info` output.

Performance:
- Module load: ~5-20ms (JSON parse + dict build)
- Per query: <10ms typical (token scan + dict lookups)
- Total memory: ~5MB resident for the in-memory index

Design note: this is intentionally goal-text-driven, not file-driven.
The `.ec` file's `require import` lines tell us which theories are
formally in scope, but agents often want lemmas from theories they
have NOT imported yet (`require import List` is omnipresent; even when
not, the user can add it). So we surface ALL stdlib hits and let the
agent decide.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

_INDEX_PATH = Path(__file__).resolve().parent.parent / "lemma_index.json"

# Lazily loaded — first call to any public function triggers load.
_index: Optional[dict] = None


def _load_index() -> dict:
    global _index
    if _index is not None:
        return _index
    if not _INDEX_PATH.exists():
        # Index missing — return empty stub so callers degrade gracefully.
        # This happens on a fresh checkout before someone runs
        # `build_lemma_index.py`. Print a one-time warning to stderr.
        import sys
        sys.stderr.write(
            f"[ec_lemma_lookup] index not found at {_INDEX_PATH} — "
            f"hint surfacing disabled. Run "
            f"`python3 core/easycrypt/build_lemma_index.py` to build.\n"
        )
        _index = {"lemmas": [], "op_to_lemmas": {}, "version": 0}
        return _index
    _index = json.loads(_INDEX_PATH.read_text(encoding="utf-8"))
    return _index


# ── Identifier extraction (mirrors build script's NON_OP_TOKENS) ──
# We use the SAME filter so symmetry between index keys and lookup
# tokens is exact. Anything you exclude here, exclude in build too.
_NON_LOOKUP_TOKENS = frozenset({
    # EC keywords / connectives
    "forall", "exists", "fun", "let", "in", "if", "then", "else",
    "true", "false", "True", "False", "Some", "None",
    "and", "or", "not",
    # Built-in type names
    "int", "real", "bool", "unit", "list", "option", "distr",
    # Single-letter common variables
    "x", "y", "z", "n", "m", "k", "i", "j", "a", "b", "c", "d",
    "s", "t", "p", "q", "r", "f", "g", "h",
    "x0", "x1", "x2", "y0", "y1", "y2", "z0", "z1", "z2",
    # Common Pr/equiv tokens
    "Pr", "res", "main", "init", "pre", "post",
    "glob", "true_pr", "witness", "oget",
    # EC tactic names — when these appear in goal text it's because
    # the agent wrote them in nearby tactics (the `prev.out` may
    # include surrounding tactic context). They're not ops to lookup.
    "move", "case", "smt", "auto", "wp", "sp", "skip", "split",
    "last", "first", "by", "done", "trivial", "simplify", "congr",
    "rewrite", "apply", "exact", "have", "proc", "inline", "call",
    "seq", "if", "while", "rnd", "ecall", "byequiv", "byphoare",
    "bypr", "conseq", "transitivity", "elim", "left", "right",
    "do", "progress", "subst", "pose", "cut", "search", "trans",
    "transition", "transition", "eager", "swap", "qed", "lemma",
    "axiom", "abort", "admit", "abstract", "section", "end",
    "theory", "module", "type", "op", "pred", "var", "return",
    "import", "export", "require", "include", "clone", "as",
    # Common hypothesis names ("Hxxx") and counter names
    "Hi", "Hi1", "Hi2", "Hinv", "Hlt", "Hc", "Hdec", "Hceq", "Hneq",
    "hr", "ns",
})

# Match identifiers NOT preceded by `.` (which would make them field
# accessors like `Mem.lc`, `BNR.ndec`, `c.foo` — project-specific names
# that shouldn't trigger stdlib lookups). The negative lookbehind also
# allows `(`, ` `, start-of-string, etc. as predecessors.
_IDENT_RE = re.compile(r"(?<![.\w'])([A-Za-z_][\w']*)\b")


def _extract_query_tokens(goal_text: str) -> list[str]:
    """Pull op-like identifiers from goal text. Order is preserved
    (first occurrence wins) so the most prominent-near-top tokens come
    first. Deduplicated."""
    seen: set = set()
    out: list[str] = []
    for m in _IDENT_RE.finditer(goal_text):
        tok = m.group(1)
        if tok in seen:
            continue
        if tok in _NON_LOOKUP_TOKENS:
            continue
        # Drop wildcards and 1-char tokens regardless of case
        if len(tok) <= 1:
            continue
        if tok == "_" or tok.startswith("_"):
            continue
        if tok.isdigit():
            continue
        seen.add(tok)
        out.append(tok)
    return out


# ── Relevance scoring ──
# Heuristic: lemmas in "primary" theory files score higher than
# auxiliary ones. Hand-tuned: List/FSet/FMap/Logic are most-cited;
# BitEncoding/RealSeq/RealSeries are less likely to help unless the
# goal explicitly mentions bits or real series.
_PRIMARY_FILES = frozenset({
    "easycrypt-src/theories/datatypes/List.ec",
    "easycrypt-src/theories/datatypes/FSet.ec",
    "easycrypt-src/theories/datatypes/FMap.ec",
    "easycrypt-src/theories/datatypes/Int.ec",
    "easycrypt-src/theories/datatypes/IntMin.ec",
    "easycrypt-src/theories/prelude/Logic.ec",
    "easycrypt-src/theories/core/Core.ec",
    "easycrypt-src/theories/algebra/Ring.ec",
    "easycrypt-src/theories/distributions/Distr.ec",
})


def _score_lemma(lem: dict, query_token: str) -> float:
    """Heuristic relevance score (higher = more useful first).

    Components:
      - Primary file bonus: +5 if the lemma lives in a hot stdlib file
      - Name-relevance: +8 if the lemma's NAME literally starts with /
        contains the query token (e.g. `take_nth` for query `take`);
        these are usually direct rewriting / membership lemmas the
        agent wants. Higher than primary-file bonus so `take_nth` from
        List wins over `take_iota` even if the latter is more concise.
      - Brevity: small bonus, capped — we don't want to over-promote
        trivial facts like `take0` over substantive lemmas
      - Axiom penalty: lemmas > axioms (axioms often very specialized)
    """
    score = 0.0
    if lem["file"] in _PRIMARY_FILES:
        score += 5.0
    name_lower = lem["name"].lower()
    qt_lower = query_token.lower()
    if name_lower == qt_lower:
        score += 12.0  # exact-name match — definitely the right lemma
    elif name_lower.startswith(qt_lower + "_"):
        score += 8.0  # `take_nth` for `take`, `mem_rcons` for `mem`
    elif name_lower.startswith(qt_lower):
        # No underscore boundary, but query is a prefix. Catches EC's
        # `XP` / `XK` / `X0` / `Xid` shape lemmas — `mapP`, `mapK`,
        # `take0`, etc. These are often the most-used lemmas for an
        # op (membership decomposition, fixpoint, base case).
        score += 7.0
    elif name_lower.endswith("_" + qt_lower):
        score += 7.0  # `size_take` for `take`
    elif qt_lower in name_lower:
        score += 4.0  # `mem_filter` contains `filter` somewhere
    # Brevity: small capped bonus, doesn't dominate name-relevance
    stmt_len = len(lem["statement"])
    if stmt_len < 100:
        score += 1.0
    elif stmt_len > 300:
        score -= 1.0
    if lem["kind"] == "axiom":
        score -= 1.0
    return score


def _contextual_hints_for_goal(goal_text: str) -> list[dict]:
    """Small hand-curated hints for local/cloned-theory-heavy goals.

    The stdlib index is intentionally declaration-based, so it cannot see
    local clone qualifiers such as `DH.G.expD` or project-local lemmas such
    as `Block.block_of_bytesdK`. These hints do not claim the symbol is in
    scope; they tell the agent which bare names are worth resolving with
    lookup_symbol in the current file/clone context.
    """
    text = goal_text or ""
    lowered = text.lower()
    hints: list[dict] = []

    has_group_exp = bool(
        "^" in text
        or re.search(r"\bexp\b", lowered)
        or re.search(r"\b(g|x|y|z)\s*\^\s*", text)
        or "dh.g" in lowered
        or "group" in lowered
    )
    has_group_mul = "*" in text or "mul" in lowered
    if has_group_exp and has_group_mul:
        hints.extend([
            _contextual_hint(
                "expD",
                "group exponent addition rewrite, typically x^(a + b) = x^a * x^b",
                "group-algebra",
            ),
            _contextual_hint(
                "expM",
                "group exponent multiplication/nesting rewrite, typically (x^a)^b = x^(a*b)",
                "group-algebra",
            ),
            _contextual_hint(
                "expN",
                "group inverse/negative-exponent rewrite when inverses appear",
                "group-algebra",
            ),
            _contextual_hint(
                "mulrA",
                "associativity for group/ring multiplication when products need regrouping",
                "group-algebra",
            ),
            _contextual_hint(
                "mulrC",
                "commutativity for group/ring multiplication when product order differs",
                "group-algebra",
            ),
        ])

    if "block_of_bytesd" in text or "bytes_of_block" in text:
        hints.extend([
            _contextual_hint(
                "block_of_bytesdK",
                "project-local cancellation lemma between bytes_of_block and block_of_bytesd",
                "block-byte-local",
            ),
            _contextual_hint(
                "Block.block_of_bytesdK",
                "qualified form often needed when the lemma lives under the Block clone/module",
                "block-byte-local",
            ),
        ])

    list_tokens = {"nth", "take", "mkseq", "cat", "size", "++"}
    if any(tok in text for tok in list_tokens):
        hints.extend([
            _contextual_hint(
                "nth_cat",
                "case split for nth over concatenation",
                "list-shape",
            ),
            _contextual_hint(
                "nth_take",
                "rewrite nth of a take prefix",
                "list-shape",
            ),
            _contextual_hint(
                "nth_mkseq",
                "rewrite nth of a generated sequence",
                "list-shape",
            ),
            _contextual_hint(
                "size_cat",
                "rewrite size of concatenation",
                "list-shape",
            ),
            _contextual_hint(
                "size_take",
                "rewrite size of a take prefix",
                "list-shape",
            ),
            _contextual_hint(
                "size_mkseq",
                "rewrite size of a generated sequence",
                "list-shape",
            ),
        ])

    return _dedupe_contextual_hints(hints)


def _contextual_hint(name: str, statement: str, matched_op: str) -> dict:
    return {
        "name": name,
        "qualified": name,
        "kind": "contextual_hint",
        "statement": statement,
        "file": "current-file-or-cloned-theory",
        "ops": [matched_op],
        "matched_op": matched_op,
        "hint_note": (
            "Resolve the actual declaration first with lookup_symbol; cloned "
            "theories may require a qualified name such as `DH.G.expD`."
        ),
    }


def _dedupe_contextual_hints(hints: list[dict]) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for hint in hints:
        name = str(hint.get("name") or "")
        if not name or name in seen:
            continue
        seen.add(name)
        out.append(hint)
    return out


def lookup_for_goal(
    goal_text: str,
    max_per_op: int = 4,
    max_total: int = 18,
    skip_ops: Optional[set] = None,
) -> list[dict]:
    """Scan ``goal_text`` for op tokens, return up to ``max_total``
    most-relevant lemma signatures.

    Args:
        goal_text: the EC goal text (post `_compress_current_state`
            preferred, but works on raw too).
        max_per_op: at most this many lemmas per query token (avoids
            one prolific op like `=` flooding the result).
        max_total: total cap across all tokens.
        skip_ops: tokens to ignore (e.g. ones the agent has already
            looked up via `-sig` this session — caller provides).

    Returns:
        List of lemma dicts ordered by relevance (highest first). Each
        has keys: name, qualified, kind, statement, file, ops.
    """
    idx = _load_index()
    contextual_hints = _contextual_hints_for_goal(goal_text)
    if not idx.get("lemmas"):
        return contextual_hints[:max_total]
    skip_ops = skip_ops or set()

    # Build a quick name → lemma index on first call. This is the
    # "direct hit" lookup: when goal text contains a literal lemma
    # name (e.g. `mapP`, `take_nth` from a previous tactic context),
    # surface that lemma's full signature with high priority.
    name_to_lemma = getattr(_load_index, "_name_cache", None)
    if name_to_lemma is None:
        name_to_lemma = {lem["name"]: lem for lem in idx["lemmas"]}
        _load_index._name_cache = name_to_lemma  # type: ignore

    query_tokens = _extract_query_tokens(goal_text)
    seen_lemmas: set = {str(h.get("name") or "") for h in contextual_hints}
    results: list[tuple[float, dict, str]] = []  # (score, lemma, query_op)

    # Pass 1: Direct lemma-name hits. These are the strongest signal:
    # the agent literally referenced `mapP` somewhere in the goal /
    # tactic context, and we have its statement. Score them highest
    # so they appear at the top of the output.
    for tok in query_tokens:
        if tok in skip_ops:
            continue
        if tok in name_to_lemma:
            lem = name_to_lemma[tok]
            if lem["name"] not in seen_lemmas:
                seen_lemmas.add(lem["name"])
                # Direct hits get a +20 score bonus to dominate ranking
                results.append((100.0 + _score_lemma(lem, tok), lem, tok))

    # Pass 2: Op-based lookup. For each token, find lemmas whose
    # statements mention it; rank within-token by relevance, take top N.
    for tok in query_tokens:
        if tok in skip_ops or tok in name_to_lemma:
            # Already handled in pass 1
            continue
        lemma_ids = idx["op_to_lemmas"].get(tok, [])
        if not lemma_ids:
            continue
        per_tok_results: list[tuple[float, dict]] = []
        for lid in lemma_ids:
            lem = idx["lemmas"][lid]
            if lem["name"] in seen_lemmas:
                continue
            score = _score_lemma(lem, tok)
            per_tok_results.append((score, lem))
        per_tok_results.sort(key=lambda x: -x[0])
        for score, lem in per_tok_results[:max_per_op]:
            if lem["name"] not in seen_lemmas:
                seen_lemmas.add(lem["name"])
                results.append((score, lem, tok))
        if len(results) >= max_total * 2:
            break

    # Sort by combined score across tokens, take top N.
    results.sort(key=lambda x: -x[0])
    indexed_results = [
        {**lem, "matched_op": op}
        for score, lem, op in results[:max_total]
    ]
    return (contextual_hints + indexed_results)[:max_total]


def format_hints(hints: list[dict]) -> str:
    """Pretty-print lemma hints for stdout / delta output. Agent sees
    `[AUTO-LEMMA-HINTS]` block with one entry per lemma."""
    if not hints:
        return ""
    lines = [
        "[AUTO-LEMMA-HINTS] EC stdlib lemmas relevant to ops in your "
        "goal — paste-ready signatures (apply / rewrite / smt(...)):",
    ]
    for h in hints:
        loc = h["file"].split("/")[-1].rstrip(".ec")
        op = h.get("matched_op", "")
        # First line of statement (sometimes goes multi-line); trim
        # whitespace-only continuations to keep output dense.
        stmt = " ".join(h["statement"].split())
        if len(stmt) > 220:
            stmt = stmt[:217] + "..."
        lines.append(f"  [{loc} / op:`{op}`] `{h['name']}`: {stmt}")
        note = str(h.get("hint_note") or "").strip()
        if note:
            lines.append(f"      note: {note}")
    lines.append(
        "  -> Use `lookup_symbol` for the full declaration first; then "
        "`apply <name>` / `rewrite <name>` only after the statement matches."
    )
    return "\n".join(lines) + "\n"


# Smoke test on import (only when run directly)
if __name__ == "__main__":
    idx = _load_index()
    print(f"Loaded {idx.get('n_lemmas', 0)} lemmas, "
          f"{idx.get('n_ops', 0)} ops")
    # Test query: step2_2 stuck point's surrounding goal
    sample_goal = """
    move=> &hr Hi1 Hi2 Hinv Hlt; split; last by smt().
    split; [by smt() | move=> c Hc Hdec].
    case (c.`1 = nth witness ns{hr} i{hr}).
    move=> Hceq.
    smt(hasP mapP mem_filter).
    rewrite mapP; exists c1; rewrite mem_filter.
    rewrite (take_nth witness i{hr} ns{hr}); first by smt().
    rewrite mem_rcons in_cons.
    """
    hits = lookup_for_goal(sample_goal, max_total=10)
    print(f"\nQuery returned {len(hits)} lemmas:")
    print(format_hints(hits))
