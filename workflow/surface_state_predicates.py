"""Shared state predicates for surface action policy and eligibility."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from core.easycrypt.analysis.ec_obligation_ir import build_proof_obligation_ir
from workflow.surface_model import goal_text
from core.easycrypt.value_shapes import as_dict as _dict


_PROGRAM_TOKEN_RE = re.compile(r"<@|<\$|\bwhile\s*\(|\bwhile\b|\bif\s*\(")
_PROGRAM_TABLE_ASSIGNMENT_RE = re.compile(
    r"(?m)^.*<-\s*.*\(\s*\d+(?:[.?]\d+)?[-?]*\s*\)"
)
_HOARE_PROGRAM_ASSIGNMENT_RE = re.compile(
    r"\b(?:hoare|phoare|bdhoare)\s*\[[^\]]*<-",
    re.S,
)


@dataclass(frozen=True)
class SurfaceState:
    """Canonical proof-state dimensions consumed by presentation policy.

    These dimensions are intentionally orthogonal.  In particular,
    ``single_program`` is a goal mode, not a reason to erase its program
    frontier, and ``pure`` does not imply that every generic rewrite action is
    useful.
    """

    goal_mode: str
    frontier_kind: str
    obligation_kind: str
    current_layer: str
    has_program: bool
    authority: str
    source_refs: tuple[str, ...]


def derive_surface_state(view: dict[str, Any]) -> SurfaceState:
    ps = _dict(view.get("proof_status"))
    current_goal = _dict(view.get("current_goal"))
    goal_type = str(ps.get("goal_type") or current_goal.get("goal_type") or "").lower()
    focus = str(ps.get("view_focus") or "").lower()
    layer = str(ps.get("current_layer") or focus or "").lower()
    current_frontier = _frontier_has_current_statement(view)
    status_program = _layer_implies_program(layer, focus) and goal_type not in {
        "ambient", "probability", "pr",
    }
    has_program = (
        goal_has_program(view)
        or _frontier_has_program_facts(view)
        or status_program
        or _single_program_shell(view)
    )
    if (
        _dict(view.get("pure_tail_surface"))
        and layer in {"ambient_logic", "pure_logic", "verification_residue"}
        and not current_frontier
    ):
        has_program = False
    relational = goal_type in {"equiv", "prhl", "relational"} or is_relational_goal(view)
    if relational:
        goal_mode = "relational"
    elif goal_type in {"hoare", "phoare", "bdhoare"}:
        goal_mode = "single_program"
    elif goal_type in {"probability", "pr"} or layer in {"pr", "probability"}:
        goal_mode = "probability"
    elif has_program and not goal_type:
        alignment = _dict(_dict(view.get("program_frontier")).get("frontier_alignment"))
        first = _dict(alignment.get("first_instruction_alignment"))
        goal_mode = (
            "single_program"
            if str(first.get("branch_alignment") or "") == "single_program_frontier"
            else "relational"
        )
    elif has_program:
        goal_mode = "single_program"
    else:
        goal_mode = "pure"

    frontier_kind, frontier_authority = _frontier_kind(view, has_program=has_program)
    obligation_kind = _obligation_kind(view)
    refs = ["proof_status", "current_goal"]
    if frontier_kind != "none":
        refs.append("program_frontier.current_frontier_scope")
    return SurfaceState(
        goal_mode=goal_mode,
        frontier_kind=frontier_kind,
        obligation_kind=obligation_kind,
        current_layer=layer or "unknown",
        has_program=has_program,
        authority=frontier_authority,
        source_refs=tuple(refs),
    )


def goal_has_program(view: dict[str, Any]) -> bool:
    text = goal_text(view)
    if _PROGRAM_TOKEN_RE.search(text):
        return True
    if _HOARE_PROGRAM_ASSIGNMENT_RE.search(text):
        return True
    return bool(_PROGRAM_TABLE_ASSIGNMENT_RE.search(text))


def is_relational_goal(view: dict[str, Any]) -> bool:
    ps = _dict(view.get("proof_status"))
    current_goal = _dict(view.get("current_goal"))
    goal_type = str(ps.get("goal_type") or current_goal.get("goal_type") or "").lower()
    if goal_type:
        return goal_type in {"equiv", "prhl", "relational"}
    text = goal_text(view)
    return bool(re.search(r"\[=", text) or re.search(r"\{1\}|\{2\}", text))


def _frontier_has_program_facts(view: dict[str, Any]) -> bool:
    frontier = _dict(view.get("program_frontier"))
    scope = _dict(frontier.get("current_frontier_scope"))
    focus = _dict(frontier.get("focus"))
    alignment = _dict(frontier.get("frontier_alignment"))
    return bool(
        scope.get("setup")
        or scope.get("frontier")
        or scope.get("lookahead_after_frontier")
        or alignment.get("rows")
        or int(focus.get("frontier_call_sites") or 0)
        or int(focus.get("live_call_sites") or 0)
    )


def _frontier_has_current_statement(view: dict[str, Any]) -> bool:
    frontier = _dict(view.get("program_frontier"))
    scope = _dict(frontier.get("current_frontier_scope"))
    return bool(_dict(scope.get("frontier")))


def _layer_implies_program(layer: str, focus: str) -> bool:
    program_names = {
        "procedure_entry", "procedure_body", "procedure_frontier", "call_site",
        "seq_cut", "deep_surgery",
    }
    if layer and layer not in {"unknown", "plain"}:
        return layer in program_names
    return focus in program_names


def _single_program_shell(view: dict[str, Any]) -> bool:
    text = goal_text(view)
    return bool(
        re.search(r"(?m)^\s*pre\s*=", text)
        and re.search(r"(?m)^\s*post\s*=", text)
        and not re.search(r"(?m)^\s*&[12]\b|\{[12]\}", text)
        and ("[=]" in text or "Bound" in text)
    )


def _frontier_kind(view: dict[str, Any], *, has_program: bool) -> tuple[str, str]:
    frontier = _dict(view.get("program_frontier"))
    scope = _dict(frontier.get("current_frontier_scope"))
    current = _dict(scope.get("frontier"))
    kind = str(current.get("kind") or "").lower()
    heads = {
        str(_dict(current.get(side)).get("head") or "").lower()
        for side in ("left", "right")
    }
    joined = " ".join((kind, *sorted(heads)))
    if "call" in joined:
        return "call", "program_ir"
    if "sample" in joined:
        return "sample", "program_ir"
    if "while" in joined or "loop" in joined:
        return "loop", "program_ir"
    if "if" in joined or "branch" in joined:
        return "branch", "program_ir"
    if current:
        return "statement", "program_ir"
    if _dict(scope.get("setup")):
        return "setup", "program_ir"
    if has_program:
        return "program", "pretty_text_fallback"
    return "none", "proof_status"


def _obligation_kind(view: dict[str, Any]) -> str:
    pure_tail = _dict(view.get("pure_tail_surface"))
    existing = _dict(pure_tail.get("proof_obligation_ir"))
    if existing:
        conclusion = _dict(existing.get("conclusion"))
        kind = str(conclusion.get("kind") or "")
        if kind:
            return kind
    return build_proof_obligation_ir(goal_text(view)).conclusion.kind


def preferred_procedure_entry_transition(view: dict[str, Any]) -> dict[str, Any]:
    """Return the canonical current module-entry transition, if any."""
    frontier = view.get("program_frontier")
    if not isinstance(frontier, dict):
        return {}
    transition = frontier.get("procedure_entry_transition")
    if not isinstance(transition, dict):
        return {}
    if (
        transition.get("kind") != "module_procedure_entry"
        or transition.get("transition") != "proc_open"
        or transition.get("status") != "preferred"
        or transition.get("tactic") != "proc."
    ):
        return {}
    return transition
