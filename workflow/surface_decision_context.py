"""Helpers for presentation-eligible decision_context signals."""
from __future__ import annotations

from typing import Any

from core.easycrypt.session_workspace_view_manager import DECISION_CONTEXT_PANEL_KEYS


def decision_context_signals(*views: Any) -> dict[str, Any]:
    """Merge agent/human deliverable decision_context panel keys.

    Only the explicit panel keys survive here. Internal decision_context shapes
    such as proof_options or raw handles remain audit facts, not presentation
    facts.
    """
    signals: dict[str, Any] = {}
    for view in views:
        if not isinstance(view, dict):
            continue
        dc = view.get("decision_context")
        if not isinstance(dc, dict):
            continue
        for key in DECISION_CONTEXT_PANEL_KEYS:
            value = dc.get(key)
            if isinstance(value, dict) and value:
                signals[key] = value
    return signals


def merge_surface_decision_context(
    view: dict[str, Any],
    full_view: dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any] | None, dict[str, Any]]:
    """Merge presentation-eligible decision_context into profiled surface inputs.

    ``view`` is the current turn/profile view. ``full_view`` is the richer audit
    view that may carry producer-side mechanism signals stripped by profile
    projection. The current turn's core fields win so read-only/control turns do
    not accidentally render stale goal/result metadata from the audit view.
    """
    surface_view = dict(view) if isinstance(view, dict) else {}
    audit_view = dict(full_view) if isinstance(full_view, dict) and full_view else None
    if audit_view is not None:
        for core in ("last_result", "current_goal", "proof_status"):
            if core in surface_view:
                audit_view[core] = surface_view[core]
    signals = decision_context_signals(audit_view, surface_view)
    if signals:
        surface_view["decision_context"] = signals
        if audit_view is not None:
            audit_view["decision_context"] = dict(signals)
    return surface_view, audit_view, signals
