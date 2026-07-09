"""Call-frontier structure: module aliases + abstract-adversary glob boundary.

At a nested-functor call the agent reconstructs two mechanical facts by hand
(seen in step4_badi turn 3, ~70s):

  * module aliases — ``ROout`` resolves to ``SplitC2.I2.RO`` (so ``ROout.m`` is
    ``SplitC2.I2.RO.m``); the agent traces these by reading clones.
  * the glob boundary — ``declare module A <: CCA_Adv { -RO, -FRO, -Mem, ... }``
    says the abstract adversary ``A``'s glob is SEPARATE from those concrete
    state modules; so the ``={...}`` concrete frame covers the state, while
    ``glob A`` is preserved implicitly and must NOT go in the concrete frame.

Both are static (name resolution) — the compiler's job, not semantics. This
module extracts them so the call-frontier panel can show them.
"""
from __future__ import annotations

import re

from core.easycrypt.analysis.ec_utils import (
    collapse_ws as _norm,
    drop_empty as _drop_empty,
)

# ``declare module A <: CCA_Adv { -RO, -FRO, -Mem }`` — name, type, separation set.
_DECLARE_MODULE = re.compile(
    r"\bdeclare\s+module\s+([A-Z]\w*)\s*<:\s*"
    r"([A-Za-z_][\w'.]*(?:\s*\([^()]*\))?)\s*(?:\{([^{}]*)\})?"
)


def abstract_adversaries(source_texts: "Iterable[tuple]") -> "list[dict[str, Any]]":
    """``declare module`` adversaries with their glob-separation set.

    A name may be `declare`d in several abstract theories (inner, more abstract)
    plus the top-level lemma section; keep the RICHEST per name (the most
    glob-separation entries), which is the contextually-relevant one — e.g.
    `A <: CCA_Adv { -RO, -FRO, -Mem, ... }` over an inner `A <: Adv { -OCC }`.
    """
    best: "dict[str, dict[str, Any]]" = {}
    order: "list[str]" = []
    for item in source_texts:
        text = item[0] if isinstance(item, (list, tuple)) and item else str(item)
        for m in _DECLARE_MODULE.finditer(str(text)):
            name = m.group(1)
            sep = m.group(3) or ""
            sep_mods = [
                tok.strip().lstrip("-").strip()
                for tok in sep.split(",")
                if tok.strip().lstrip("-").strip()
            ]
            entry = {
                "name": name,
                "type": _norm(m.group(2)),
                "glob_separate_from": sep_mods,
            }
            if name not in best:
                best[name] = entry
                order.append(name)
            elif len(sep_mods) > len(best[name]["glob_separate_from"]):
                best[name] = entry
    return [best[n] for n in order]


def call_frontier_structure(
    source_texts: "Iterable[tuple]",
    *,
    aliases: "dict[str, str] | None" = None,
    goal_text: str = "",
) -> "dict[str, Any]":
    """Module-alias map + abstract-adversary glob boundary for the call frontier.

    ``aliases`` = ``state_field_pool``'s alias table. ``goal_text`` (optional)
    relevance-filters the adversaries to the ones actually named at the frontier.
    Returns ``{module_aliases, abstract_adversaries, note}`` or ``{}`` if neither
    is present. Mechanical facts only — it asserts no invariant content.
    """
    alias_rows = [
        {"alias": k, "resolves_to": _norm(v)}
        for k, v in (aliases or {}).items()
        if k and v
    ]
    adv = abstract_adversaries(source_texts)
    if goal_text:
        named = [a for a in adv if re.search(r"\b" + re.escape(a["name"]) + r"\b", goal_text)]
        adv = named or adv
    if not alias_rows and not adv:
        return {}
    return _drop_empty({
        "module_aliases": alias_rows,
        "abstract_adversaries": adv,
        "note": (
            "Mechanical name resolution. An alias `X -> Y` means `X.field` is "
            "`Y.field` (e.g. `ROout.m` = `SplitC2.I2.RO.m`). An abstract adversary "
            "with `glob_separate_from` has its glob preserved implicitly and "
            "SEPARATE from those concrete state modules — keep `glob A` OUT of the "
            "`={...}` concrete frame; the frame covers the state modules only."
        ),
    })


_MODULE_DEF = r"\b(?:local\s+)?module\s+{name}\b"
_CALL_MOD_TOKEN = re.compile(r"\b([A-Z][A-Za-z0-9_]*)\b")


def _module_is_defined(source_texts: "Iterable[tuple]", name: str) -> bool:
    pat = re.compile(_MODULE_DEF.format(name=re.escape(name)))
    for item in source_texts:
        text = item[0] if isinstance(item, (list, tuple)) and item else str(item)
        if pat.search(str(text)):
            return True
    return False


def inline_preview(
    source_texts: "Iterable[tuple]",
    call_statement: str,
    abstract_names: "Iterable[str]",
) -> "dict[str, Any]":
    """Which modules in a call ``inline*`` expands vs stops at.

    The agent mentally simulates this (step4_badi turn 13: "`inline*` would inline
    CCA_CPA_Adv and BNR_Adv but not A.main since A is abstract"). It is mechanical:
    a module is CONCRETE (has a body → inline expands it) or ABSTRACT (a declared
    adversary → inline stops, its oracle calls become the `call (_: Inv)`
    obligations). Returns ``{call, modules, inline_stops_at, note}`` or ``{}``.
    """
    abstract = {str(a) for a in (abstract_names or [])}
    rows: "list[dict[str, str]]" = []
    seen: "set[str]" = set()
    for m in _CALL_MOD_TOKEN.finditer(str(call_statement or "")):
        name = m.group(1)
        if name in seen:
            continue
        seen.add(name)
        if name in abstract:
            rows.append({"module": name, "kind": "abstract",
                         "inline": "stops (abstract adversary)"})
        elif _module_is_defined(source_texts, name):
            rows.append({"module": name, "kind": "concrete", "inline": "expands"})
        # bare types / unknown tokens are dropped (not module-like)
    if not rows:
        return {}
    stops = [r["module"] for r in rows if r["kind"] == "abstract"]
    concrete = [r["module"] for r in rows if r["kind"] == "concrete"]
    return _drop_empty({
        "call": _norm(call_statement)[:140],
        "modules": rows,
        "inline_stops_at": stops,
        # The nested-call mistake cost a backtrack live (step4_badi turn 8→15:
        # `call` stacked at the concrete game level, blew up, undone). Say the rule
        # loudly and structurally, not just in prose.
        "call_at": stops,
        "inline_first": concrete,
        "note": (
            "ONE call site, and it is the ABSTRACT adversary "
            + (f"({', '.join(stops)})" if stops else "")
            + ". Do NOT `call` at the concrete game/wrapper modules "
            + (f"({', '.join(concrete)})" if concrete else "")
            + " — that fails. `inline*` (or `inline` those by name) FIRST to unwrap "
            "them, which surfaces the single abstract-adversary call; THEN "
            "`call (_: Inv)` there. The concrete wrappers expand; the abstract "
            "adversary's oracle calls become your `call (_: Inv)` obligations."
        ),
    })
