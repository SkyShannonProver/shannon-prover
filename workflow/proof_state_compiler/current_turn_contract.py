"""Contracts and typed JSON primitives for current turn presentation."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from workflow.proof_state_compiler.surface_profiles import (
    require_current_workspace_view as _require_profile_workspace_view,
)


SURFACE_MODEL_SCHEMA_VERSION = 1
SURFACE_TURN_SCHEMA_VERSION = 1
_RUNTIME_ONLY_FIELDS = frozenset({"_l1_surface_notice", "surface_turn"})


def require_current_workspace_view(
    view: object,
    *,
    profile_id: str,
    label: str,
) -> dict[str, Any]:
    """Validate one lean current workspace view."""

    if not isinstance(view, dict):
        raise TypeError(f"{label} must be an object")
    data = {
        key: value
        for key, value in view.items()
        if key not in _RUNTIME_ONLY_FIELDS
    }
    _require_profile_workspace_view(
        data,
        profile_id=profile_id,
        label=label,
    )
    return json.loads(json.dumps(data))


def current_proof_surface(
    view: dict[str, Any],
    profile_id: str,
) -> dict[str, Any]:
    goal = goal_surface(view)
    proof_status = as_dict(view.get("proof_status"))
    status = drop_empty({
        "status": proof_status.get("status"),
        "remaining_goals": proof_status.get("remaining_goals"),
        "remaining_goals_known": proof_status.get("remaining_goals_known"),
        "surface_phase": "goal_only",
    })
    data = drop_empty({
        "schema_version": SURFACE_MODEL_SCHEMA_VERSION,
        "profile": profile_id,
        "phase": "goal_only",
        "goal": goal,
        "status": status,
        "metadata": {
            "contract": "CurrentGoalEnvelope -> CurrentProofSurface",
        },
    })
    data["surface_model_hash"] = content_hash(data, "surface_model_hash")
    return data


def current_proof_surface_from_turn(
    surface_turn: object,
) -> dict[str, Any]:
    if not isinstance(surface_turn, dict):
        return {}
    proof = surface_turn.get("proof_surface")
    return dict(proof) if isinstance(proof, dict) else {}


def goal_surface(view: dict[str, Any]) -> dict[str, Any]:
    goal = as_dict(view.get("current_goal"))
    if not goal:
        return {}
    lines = goal.get("lines")
    text = str(goal.get("text") or goal.get("lines_preview") or "")
    if not text and isinstance(lines, list):
        text = "\n".join(str(line) for line in lines)
    line_count = goal.get("line_count")
    if line_count is None and isinstance(lines, list):
        line_count = len(lines)
    return drop_empty({
        "title": "Current Goal",
        "text": text,
        "lines": list(lines) if isinstance(lines, list) else None,
        "truncated": goal.get("truncated"),
        "line_count": line_count,
    })


def content_hash(data: dict[str, Any], field: str) -> str:
    payload = dict(data)
    payload.pop(field, None)
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha1(encoded.encode("utf-8")).hexdigest()


def as_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def drop_empty(data: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in data.items()
        if value not in (None, "", [], {}, ())
    }
