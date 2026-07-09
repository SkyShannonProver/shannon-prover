"""Shared state predicates for surface action policy and eligibility."""
from __future__ import annotations

import re
from typing import Any

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


def goal_has_program(view: dict[str, Any]) -> bool:
    text = goal_text(view)
    if _PROGRAM_TOKEN_RE.search(text):
        return True
    if _HOARE_PROGRAM_ASSIGNMENT_RE.search(text):
        return True
    return bool(_PROGRAM_TABLE_ASSIGNMENT_RE.search(text))


def is_relational_goal(view: dict[str, Any]) -> bool:
    ps = _dict(view.get("proof_status"))
    goal_type = str(ps.get("goal_type") or "").lower()
    if goal_type in {"equiv", "prhl", "relational"}:
        return True
    if goal_type in {"hoare", "phoare", "bdhoare", "probability", "pr"}:
        return False
    text = goal_text(view)
    return bool(re.search(r"\[=", text) or re.search(r"\{1\}|\{2\}", text))


