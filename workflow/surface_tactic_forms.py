"""State-derived tactic-form families for the typed surface contract.

This module owns the question "which tactic form names are relevant to this
proof state?"  The composer may use these names to build actions, and the
eligibility layer may use the same names to gate actions, but neither layer
should maintain a separate tactic-family taxonomy.
"""
from __future__ import annotations

import re
from typing import Any

from workflow.surface_model import goal_text as _choice_goal_text
from workflow.surface_state_predicates import goal_has_program


PROGRAM_TACTIC_FORMS = frozenset({
    "sp", "wp", "swap", "rcondt", "rcondf", "conseq", "rnd", "eager",
    "call", "ecall", "inline", "proc", "seq", "while", "if",
})
PURE_TACTIC_FORMS = frozenset({"smt", "rewrite", "apply", "case", "have"})
CALL_TACTIC_FORMS = frozenset({"call", "ecall", "inline", "proc", "wp", "sp", "conseq"})
OPENER_TACTIC_FORMS = frozenset({
    "byequiv", "byphoare", "phoare", "bdhoare", "conseq", "rewrite", "apply", "smt",
})
PLAIN_BASE_TACTIC_FORMS = frozenset({"rewrite", "apply"})


def eligible_tactic_form_names(
    view: dict[str, Any],
    panel_id: str,
    phase: str,
) -> frozenset[str] | None:
    """Canonical tactic-form family set for a surface panel/state.

    ``None`` means the state has no extra family restriction beyond protocol and
    profile visibility.  This function is intentionally shared by composition
    and eligibility so the menu source and the gate cannot drift apart.
    """
    if panel_id == "plain" or phase == "plain":
        return tactic_form_names_for_state(view, panel_id, phase)
    if panel_id == "call_site" or phase == "call_site":
        return CALL_TACTIC_FORMS
    if panel_id == "pure_logic" or phase == "pure_logic":
        return PURE_TACTIC_FORMS
    if panel_id == "opener" or phase == "opener":
        return OPENER_TACTIC_FORMS | PURE_TACTIC_FORMS
    if panel_id == "deep_surgery" or phase == "deep_surgery":
        return PROGRAM_TACTIC_FORMS if goal_has_program(view) else PURE_TACTIC_FORMS
    if panel_id == "recovery" or phase == "failure_recovery":
        return None
    if not goal_has_program(view):
        return PURE_TACTIC_FORMS | OPENER_TACTIC_FORMS
    return None


def tactic_form_names_for_state(
    view: dict[str, Any],
    panel_id: str,
    phase: str,
) -> frozenset[str] | None:
    """Concrete tactic-form families eligible for this proof state.

    Plain single-sided side conditions need an explicit contract because their
    goal text may contain a Hoare program block; that block is not a relational
    surgery frontier and should not inherit stale program-roster entries.
    """
    if panel_id != "plain" and phase != "plain":
        return None
    text = goal_text(view)
    names = set(PLAIN_BASE_TACTIC_FORMS)
    program = plain_program_body(text)
    if not program:
        return frozenset(names)
    if re.search(r"<-|<@|<\$|\bif\b|\bwhile\b", program):
        names.add("wp")
    if "<@" in program:
        names.add("call")
    if "<$" in program:
        names.add("rnd")
    if re.search(r"\bif\b", program):
        names.update({"rcondt", "rcondf"})
    if re.search(r"\bwhile\b", program):
        names.add("while")
    return frozenset(names)


def plain_program_body(text: str) -> str:
    match = re.search(r"\b(?:hoare|phoare|bdhoare)\s*\[(.*?):", text, re.S)
    if match:
        return match.group(1)
    return text if goal_has_program({"current_goal": {"text": text}}) else ""


def goal_text(view: dict[str, Any]) -> str:
    return _choice_goal_text(view)

