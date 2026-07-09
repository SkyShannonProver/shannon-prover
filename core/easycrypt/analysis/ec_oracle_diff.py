"""Structural diff of the two oracle modules at a relational call frontier.

At a `call (_: ...)` the two sides instantiate the same game with DIFFERENT oracle
modules (step4_badi: `UFCMA_l.O` vs `UFCMA_li.O`). The agent rebuilt the two
module bodies by hand (turns 2/7/13, ~3 min) just to see WHERE they diverge —
which is mechanical: the modules are concrete, so the diff is a structural
comparison of their procedures.

This surfaces only the divergence: procedures both modules have but with
DIFFERENT bodies (`set_bad1` — the right resamples), and procedures one side has
and the other does not (`set_bad1i`). Identical procedures are suppressed. The
coupling the proof needs lives exactly in the differing procedure(s) — but WHICH
coupling is the agent's (semantic) call; this only points at the divergence.
"""
from __future__ import annotations

import re

from core.easycrypt.analysis.ec_utils import (
    collapse_ws as _norm,
    delimited_region as _delimited_region,
)

_MOD_HEAD = (
    r"\b(?:local\s+)?module\s+{name}\b[^{{}}=]*=\s*\{{"
)
_PROC = re.compile(
    r"\bproc\s+([A-Za-z_]\w*)\s*(?:\([^()]*\))?\s*(?::[^={}]*)?=\s*[\{A-Za-z_]"
)
_MOD_TOKEN = re.compile(r"\b([A-Z][A-Za-z0-9_]*)\b")


def _module_procs(source_texts: "Iterable[tuple]", name: str) -> "dict[str, str]":
    """``{proc_name: normalized_body}`` for ``(local )?module <name> = {...}``."""
    head = re.compile(_MOD_HEAD.format(name=re.escape(name)))
    for item in source_texts:
        text = item[0] if isinstance(item, (list, tuple)) and item else str(item)
        m = head.search(str(text))
        if not m:
            continue
        body = _delimited_region(str(text), m.end() - 1, "{", "}")
        procs: "dict[str, str]" = {}
        for pm in _PROC.finditer(body):
            brace = body.find("{", pm.end() - 1)
            if brace < 0:
                # aliased proc (``proc set_bad1 = M.set_bad1``) — body is the alias
                tail = body[pm.end() - 1:].split("\n", 1)[0]
                procs[pm.group(1)] = _norm(tail)
                continue
            procs[pm.group(1)] = _norm(_delimited_region(body, brace, "{", "}"))
        if procs:
            return procs
    return {}


def differing_call_modules(left_call: str, right_call: str) -> "tuple":
    """The module token that differs between two call statements (``UFCMA_l`` vs
    ``UFCMA_li``), or ``(None, None)``."""
    L = _MOD_TOKEN.findall(str(left_call or ""))
    R = _MOD_TOKEN.findall(str(right_call or ""))
    for a, b in zip(L, R):
        if a != b:
            return (a, b)
    return (None, None)


def oracle_module_diff(
    source_texts: "Iterable[tuple]", left_mod: str, right_mod: str, *, body_cap: int = 600,
) -> "dict[str, Any]":
    """Structural diff of two concrete oracle modules' procedures."""
    if not left_mod or not right_mod or left_mod == right_mod:
        return {}
    left = _module_procs(source_texts, left_mod)
    right = _module_procs(source_texts, right_mod)
    if not left or not right:
        return {}
    differing: "list[dict[str, Any]]" = []
    left_only: "list[str]" = []
    right_only: "list[str]" = []
    for name in sorted(set(left) | set(right)):
        in_l, in_r = name in left, name in right
        if in_l and in_r:
            if left[name] != right[name]:
                differing.append({
                    "proc": name,
                    "left": left[name][:body_cap],
                    "right": right[name][:body_cap],
                })
        elif in_l:
            left_only.append(name)
        else:
            right_only.append(name)
    if not (differing or left_only or right_only):
        return {}
    return {
        "left_module": left_mod,
        "right_module": right_mod,
        "differing_procs": differing,
        "left_only_procs": left_only,
        "right_only_procs": right_only,
        "note": (
            "The two oracle modules diverge ONLY here (identical procedures are "
            "suppressed). The coupling the invariant needs lives in the differing "
            "procedure(s); which coupling is yours to decide."
        ),
    }
