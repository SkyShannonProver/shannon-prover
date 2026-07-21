"""Frame fact parsing shared by proof-management analyzers.

These helpers recognize EasyCrypt frame equalities such as `={glob A}` and
`(glob A){1} = (glob A){2}`. They are intentionally syntactic evidence
extractors; they do not decide whether a proof obligation is valid.
"""
from __future__ import annotations

import re
from typing import Any

from workflow.proof_management.common import (
    _dict,
    _drop_empty_precheck as _drop_empty,
)
from workflow.proof_management.tactic_utils import tactic_head as _tactic_head


def merge_frame_fact_sources(
    grouped: list[tuple[str, list[dict[str, str]]]],
) -> list[dict[str, Any]]:
    by_key: dict[str, dict[str, Any]] = {}
    for source, facts in grouped:
        for fact in facts:
            key = str(fact.get("canonical") or "")
            if not key:
                continue
            current = by_key.setdefault(
                key,
                {
                    "canonical": key,
                    "display": fact.get("display") or key,
                    "sources": [],
                },
            )
            if source not in current["sources"]:
                current["sources"].append(source)
    return list(by_key.values())


def frame_ledger_scope_start(tactics: list[str]) -> int:
    for idx in range(len(tactics), 0, -1):
        tactic = str(tactics[idx - 1] or "").strip()
        if _starts_new_frame_obligation_segment(tactic):
            return idx + 1
    return 1


def frame_boundary_facts(
    tactics: list[str],
    *,
    start_index: int = 1,
) -> list[dict[str, Any]]:
    boundaries: list[dict[str, Any]] = []
    for idx, tactic in enumerate(tactics, start=1):
        if idx < max(1, int(start_index)):
            continue
        head = _tactic_head(tactic)
        lower = tactic.strip().lower()
        if head not in {"seq", "call", "while", "conseq"} and "call (_:" not in lower:
            continue
        facts = extract_frame_facts(tactic)
        boundaries.append(_drop_empty({
            "tactic_index": idx,
            "kind": head or "structural",
            "tactic": tactic,
            "canonical_facts": [fact["canonical"] for fact in facts],
            "carried_facts": [fact["display"] for fact in facts],
        }))
    return boundaries


def frame_recent_manager_goal_text(view: dict[str, Any]) -> str:
    texts: list[str] = []
    for key in ("latest_observation", "last_result"):
        value = _dict(view.get(key))
        if value:
            _collect_frame_goal_text(value, texts, key_hint=key)
    return "\n".join(texts)


def extract_frame_facts(text: str) -> list[dict[str, str]]:
    clean = strip_easycrypt_comments(str(text or ""))
    facts: list[dict[str, str]] = []

    def add(term: str, *, require_frame_like: bool = False) -> None:
        normalized = _normalize_frame_term(term)
        if not normalized:
            return
        if require_frame_like and not _looks_like_frame_term(normalized):
            return
        display = f"={{ {normalized} }}".replace("{ ", "{").replace(" }", "}")
        item = {"canonical": normalized, "display": display}
        if item not in facts:
            facts.append(item)

    for match in re.finditer(r"=\{\s*([^{}]+?)\s*\}", clean):
        for term in _split_frame_terms(match.group(1)):
            add(term)
    for match in re.finditer(
        r"\(([^(){}]+)\)\{1\}\s*=\s*\(\1\)\{2\}",
        clean,
    ):
        add(match.group(1), require_frame_like=True)
    for match in re.finditer(
        r"\b([A-Za-z_][A-Za-z0-9_.']*)\{1\}\s*=\s*\1\{2\}",
        clean,
    ):
        add(match.group(1), require_frame_like=True)
    return facts[:16]


def pre_post_global_frame_gap(
    view: dict[str, Any],
    *,
    goal_text: str | None = None,
) -> list[str]:
    text = goal_text if goal_text is not None else view_goal_text(view)
    pre, post = pre_post_sections(text)
    if not pre or not post:
        return []
    pre_terms = global_frame_terms(pre)
    post_terms = global_frame_terms(post)
    return [
        term for term in post_terms
        if term not in pre_terms
    ][:4]


def pre_post_sections(goal_text: str) -> tuple[str, str]:
    match = re.search(
        r"\bpre\s*=\s*(?P<pre>.*?)(?:\n\s*)+\bpost\s*=\s*(?P<post>.*)",
        str(goal_text or ""),
        re.S,
    )
    if not match:
        return "", ""
    return match.group("pre"), match.group("post")


def global_frame_terms(text: str) -> list[str]:
    terms: list[str] = []
    for fact in extract_frame_facts(text):
        term = str(fact.get("canonical") or "")
        if term.startswith("glob ") and term not in terms:
            terms.append(term)
    return terms


def _field_top_module(canonical: str) -> str:
    """`OCC.gs` -> `OCC`; `ROIN.RO.m` -> `ROIN`; `glob OCC` / bare `m` -> '' (not a
    qualified field that a `glob` could subsume)."""
    c = str(canonical or "").strip()
    if not c or c.lower().startswith("glob ") or "." not in c:
        return ""
    return c.split(".", 1)[0]


def _is_clone_alias(a: str, b: str) -> bool:
    """True when two field canonicals are the SAME field up to clone-qualification, i.e.
    one dotted path is a `module.field`-granular suffix of the other: `RO.m` ≡ `ROIN.RO.m`
    ≡ `SplitC1.RO.m`. Requires >=2 shared trailing components (module.field), so unrelated
    fields that merely share a leaf name (`X.m` vs `Y.m`) do NOT alias-match. Globs never
    alias-match (handled by subsumption)."""
    a = str(a or "").strip()
    b = str(b or "").strip()
    if not a or not b or a == b:
        return False
    if a.lower().startswith("glob ") or b.lower().startswith("glob "):
        return False
    pa, pb = a.split("."), b.split(".")
    if len(pa) < 2 or len(pb) < 2:
        return False
    short, long = (pa, pb) if len(pa) <= len(pb) else (pb, pa)
    return long[-len(short):] == short


def frame_fact_carried(fact_canonical: str, carried: "set[str]") -> bool:
    """Is a required frame fact actually carried by a set of boundary frame facts?

    Lenient on purpose — the exact-string check made the frame-obligation ledger and
    route-health frame-gap over-report false drops, which steered the agent into rewinding
    SOUND proofs (the audit's worst 误导). A fact counts as carried by exact match, by
    `glob M` subsumption (a carried `={glob M}` covers every field `M.x...`), or by
    clone-alias (`RO.m` carried as `ROIN.RO.m`). The reverse direction is NOT inferred (a
    field does not cover its `glob`); transitivity / call-auto-frame stay out of scope (a
    deeper write-map fix). Leniency only causes false NEGATIVES (a missed drop), which are
    far safer than false positives here."""
    f = str(fact_canonical or "").strip()
    if not f:
        return False
    if f in carried:
        return True
    top = _field_top_module(f)
    if top and ("glob " + top) in carried:
        return True
    return any(_is_clone_alias(f, c) for c in carried)


def transitively_equal_terms(pre_text: str) -> "set[str]":
    """Frame terms X whose two-run equality `={X}` (X{1}=X{2}) is DERIVABLE from the
    PRECONDITION's memory-tagged equalities, including TRANSITIVELY through a middle
    memory: `(glob A){1}=(glob A){m} ∧ (glob A){2}=(glob A){m}` ⊢ `={glob A}`.

    Returns the canonical terms. Used to suppress a false "frame fact dropped" alarm when
    the fact is provable from the pre (so it is not dropped — just not re-asserted at a
    committed boundary). Scan ONLY the PRE / hypothesis context the caller passes — NEVER
    the postcondition (the goal to PROVE), so a required `={X}` appearing in the post does
    not self-certify as carried."""
    clean = strip_easycrypt_comments(str(pre_text or ""))
    adj: "dict[str, dict[str, set[str]]]" = {}

    def _edge(term: str, a: str, b: str) -> None:
        t = _normalize_frame_term(term)
        if not t or a == b:
            return
        g = adj.setdefault(t, {})
        g.setdefault(a, set()).add(b)
        g.setdefault(b, set()).add(a)

    for mt in re.finditer(r"\(([^(){}]+)\)\{(\w+)\}\s*=\s*\(\1\)\{(\w+)\}", clean):
        _edge(mt.group(1), mt.group(2), mt.group(3))
    for mt in re.finditer(r"\b([A-Za-z_][\w'.]*)\{(\w+)\}\s*=\s*\1\{(\w+)\}", clean):
        _edge(mt.group(1), mt.group(2), mt.group(3))

    out: "set[str]" = set()
    for term, g in adj.items():
        if "1" not in g or "2" not in g:
            continue
        seen = {"1"}
        stack = ["1"]
        while stack:
            n = stack.pop()
            for nb in g.get(n, ()):
                if nb not in seen:
                    seen.add(nb)
                    stack.append(nb)
        if "2" in seen:
            out.add(term)
    return out


def view_goal_text(
    view: dict[str, Any],
    *,
    legacy_goal_text_fallback: bool = False,
) -> str:
    current_goal = _dict(view.get("current_goal"))
    lines = current_goal.get("lines")
    if isinstance(lines, list):
        return "\n".join(str(line) for line in lines)
    if legacy_goal_text_fallback:
        text = current_goal.get("text") or view.get("goal_text")
        return str(text or "")
    return _first_text(
        current_goal.get("lines_preview"),
        current_goal.get("active_goal_text"),
        current_goal.get("active_goal_preview"),
        default="",
    )


def strip_easycrypt_comments(text: str) -> str:
    out: list[str] = []
    i = 0
    depth = 0
    while i < len(text):
        if text.startswith("(*", i):
            depth += 1
            i += 2
            continue
        if depth and text.startswith("*)", i):
            depth -= 1
            i += 2
            continue
        if depth == 0:
            out.append(text[i])
        i += 1
    return "".join(out)


def _starts_new_frame_obligation_segment(tactic: str) -> bool:
    text = strip_easycrypt_comments(str(tactic or "")).strip().lower()
    if not text:
        return False
    if text.startswith("have ") and ":" in text:
        return True
    if text.startswith("suff ") or text.startswith("suffices "):
        return True
    return False


def _collect_frame_goal_text(
    value: Any,
    texts: list[str],
    *,
    key_hint: str = "",
    depth: int = 0,
) -> None:
    if depth > 4:
        return
    if isinstance(value, str):
        if key_hint and _is_frame_goal_text_key(key_hint):
            texts.append(value)
        return
    if isinstance(value, list):
        if key_hint and _is_frame_goal_text_key(key_hint):
            texts.extend(str(item) for item in value if isinstance(item, str))
        else:
            for item in value:
                _collect_frame_goal_text(
                    item,
                    texts,
                    key_hint=key_hint,
                    depth=depth + 1,
                )
        return
    if not isinstance(value, dict):
        return
    for key, item in value.items():
        name = str(key or "")
        if _is_frame_goal_text_key(name):
            _collect_frame_goal_text(
                item,
                texts,
                key_hint=name,
                depth=depth + 1,
            )
        elif name in {"content", "result", "preview"}:
            _collect_frame_goal_text(
                item,
                texts,
                key_hint=key_hint,
                depth=depth + 1,
            )


def _is_frame_goal_text_key(key: str) -> bool:
    normalized = str(key or "").strip().lower()
    if normalized in {
        "current_goal",
        "goal_after",
        "goal_preview",
        "active_goal_text",
        "active_goal_preview",
        "lines",
        "lines_preview",
        "residual",
        "residual_goal",
        "residual_goals",
    }:
        return True
    return (
        "goal" in normalized
        and not any(
            marker in normalized
            for marker in ("payload", "intent", "tactic", "checkpoint")
        )
    )


def _split_frame_terms(text: str) -> list[str]:
    terms: list[str] = []
    for raw in str(text or "").split(","):
        term = raw.strip()
        if term:
            terms.append(term)
    return terms


def _normalize_frame_term(term: str) -> str:
    text = re.sub(r"\s+", " ", str(term or "").strip())
    while text.startswith("(") and text.endswith(")"):
        inner = text[1:-1].strip()
        if not inner:
            break
        text = inner
    if len(text) > 80:
        return ""
    if not re.search(r"[A-Za-z_]", text):
        return ""
    return text


def _looks_like_frame_term(term: str) -> bool:
    text = str(term or "").strip()
    if not text:
        return False
    lower = text.lower()
    if lower.startswith("glob "):
        return True
    if "." in text:
        return True
    if re.match(r"^[A-Z][A-Za-z0-9_']*(?:\b|$)", text):
        return True
    return False


def _first_text(*values: Any, default: str = "") -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value
        if isinstance(value, list):
            text = "\n".join(str(item) for item in value)
            if text.strip():
                return text
    return default
