"""Manager-turn projection of the current runtime-profile registry.

No legacy panel stage or inspect roster belongs in this module.  Every current
arm uses the same goal-only manager envelope and persistent proof controls;
compiler configuration alone determines whether an ActionSurface is produced.
"""
from __future__ import annotations

from typing import Any

from core.context_intents import intent_spec
from workflow.proof_state_compiler.profile_registry import (
    CURRENT_TURN_PROFILES as CURRENT_SURFACE_PROFILES,
    normalize_current_surface_profile_id,
)
from workflow.proof_state_compiler.surface_contract import SurfaceProfile


def current_surface_profile(profile_id: str | None) -> SurfaceProfile:
    return CURRENT_SURFACE_PROFILES[
        normalize_current_surface_profile_id(profile_id)
    ]


def ensure_current_surface_profile(profile_id: str | None) -> SurfaceProfile:
    return CURRENT_SURFACE_PROFILES[
        normalize_current_surface_profile_id(profile_id)
    ]


def project_current_workspace_view(
    view: dict[str, Any],
    profile_id: str,
) -> dict[str, Any]:
    """Erase durable carrier fields without invoking a legacy surface pass."""

    ensure_current_surface_profile(profile_id)
    allowed = {
        "schema_version",
        "kind",
        "ok",
        "proof_status",
        "last_result",
        "current_goal",
        "latest_observation",
        "based_on_state_version",
        "session_epoch",
    }
    return {key: value for key, value in view.items() if key in allowed}


def require_current_workspace_view(
    view: object,
    *,
    profile_id: str,
    label: str,
) -> dict[str, Any]:
    ensure_current_surface_profile(profile_id)
    if not isinstance(view, dict):
        raise TypeError(f"{label} must be an object")
    allowed = {
        "schema_version",
        "kind",
        "ok",
        "proof_status",
        "last_result",
        "current_goal",
        "latest_observation",
        "view_hash",
        "based_on_state_version",
        "session_epoch",
    }
    unsupported = sorted(set(view) - allowed)
    if unsupported:
        raise ValueError(
            f"{label} contains unsupported current-envelope fields: "
            + ", ".join(unsupported)
        )
    proof_status = view.get("proof_status")
    if not isinstance(proof_status, dict) or not proof_status:
        raise ValueError(f"{label}.proof_status must be non-empty")
    if not isinstance(proof_status.get("remaining_goals_known"), bool):
        raise ValueError(f"{label}.proof_status.remaining_goals_known must be bool")
    if not isinstance(view.get("current_goal"), dict):
        raise ValueError(f"{label}.current_goal must be an object")
    if not isinstance(view.get("ok"), bool):
        raise ValueError(f"{label}.ok must be bool")
    if not isinstance(view.get("view_hash"), str) or not view.get("view_hash"):
        raise ValueError(f"{label}.view_hash must be non-empty")
    return view


def current_surface_profile_allows_intent(
    profile_id: str,
    intent: str,
) -> tuple[bool, str]:
    profile = ensure_current_surface_profile(profile_id)
    if intent_spec(intent) is None:
        return False, f"Unknown manager intent `{intent}`."
    if intent not in profile.allowed_intents:
        return False, (
            f"Surface profile `{profile.name}` exposes only the matched "
            f"proof-control protocol; intent `{intent}` is unavailable."
        )
    return True, ""
