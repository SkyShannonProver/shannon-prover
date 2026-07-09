"""Shared candidate-closed status checks for workspace view projection."""
from __future__ import annotations

from typing import Any

from core.easycrypt.value_shapes import first_text as _first_text


def goal_visibly_closed(
    current_goal: dict[str, Any],
    proof_goal: dict[str, Any] | None = None,
) -> bool:
    proof_goal = proof_goal or {}
    preview = _first_text(
        current_goal.get("active_goal_preview"),
        current_goal.get("active_goal_text"),
        default="",
    )
    return bool(
        current_goal.get("proof_candidate_closed")
        or proof_goal.get("proof_candidate_closed")
        or "No more goals" in preview
    )


def transition_can_mark_closed(transition: dict[str, Any]) -> bool:
    kind = _first_text(transition.get("kind"), default="")
    if kind in {"", "none", "undo", "error", "refused", "no_progress"}:
        return False
    return bool(
        transition.get("candidate_closed")
        or transition.get("goals_after") == 0
        or kind in {"closed", "qed_saved"}
    )

