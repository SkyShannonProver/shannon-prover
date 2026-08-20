"""Minimal manager-owned goal envelope for L1 and compiler V2.

This module is deliberately smaller than the retired rich ``-agent-view``
pipeline.  It projects only transport/identity facts needed by the managed
turn boundary: current goal text, proof status, and canonical goal identity.
It never builds ProofIR, program panels, inspect menus, or legacy analyzers.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from core.easycrypt.session.session_projection import read_proof_state_projection
from core.easycrypt.session.session_prover_workspace_schema import (
    PROVER_WORKSPACE_VIEW_KIND,
    PROVER_WORKSPACE_VIEW_SCHEMA_VERSION,
    require_prover_workspace_view,
)


def build_managed_goal_view(
    session_dir: str | Path,
    *,
    live_tool_name: str,
) -> dict[str, Any]:
    """Build the exact neutral workspace carrier used by managed runs."""

    projection = read_proof_state_projection(
        session_dir,
        live_tool_name=live_tool_name,
    )
    open_goal = projection.goal_identity_required
    raw_goal = projection.active_goal_text if open_goal else ""
    lines = raw_goal.splitlines() if raw_goal else []
    remaining = projection.goal.num_remaining
    remaining_known = projection.goal.num_remaining_determined
    ok = bool(projection.events.ok and projection.consistency.ok)
    view = {
        "schema_version": PROVER_WORKSPACE_VIEW_SCHEMA_VERSION,
        "kind": PROVER_WORKSPACE_VIEW_KIND,
        "ok": ok,
        "last_result": {},
        "proof_status": {
            "status": projection.status,
            "goals_discharged": projection.goals_discharged,
            "qed_committed": projection.qed_committed,
            "offline_verified": projection.offline_verified,
            "goal_identity_required": open_goal,
            "remaining_goals": remaining if remaining_known else None,
            "remaining_goals_known": remaining_known,
            "goal_hash": (
                projection.goal.active_goal_hash if open_goal else ""
            ),
        },
        "current_goal": (
            {
                "lines": lines,
                "text_fully_shown": bool(lines),
                "truncated": False,
                "line_count": len(lines),
                "shown_lines": len(lines),
                "char_count": len(raw_goal),
                "shown_chars": len(raw_goal),
                "source": "easycrypt_current_goal_text",
            }
            if open_goal
            else {}
        ),
    }
    require_prover_workspace_view(view, label="managed goal view")
    return view


def record_managed_goal_view(session_or_dir: Any, view: dict[str, Any]) -> dict[str, Any]:
    """Bind one minimal view to the standard workspace produced event."""

    from core.easycrypt.session.session_workspace_artifact import (
        record_prover_workspace_view,
    )

    return record_prover_workspace_view(
        session_or_dir,
        view,
        source="managed_goal_view",
    )
