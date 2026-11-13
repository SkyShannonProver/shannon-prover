"""Manager-turn projection of the current runtime-profile registry.

No legacy panel stage or inspect roster belongs in this module.  Every current
arm uses the same goal-only manager envelope and persistent proof controls;
compiler configuration alone determines whether an ActionSurface is produced.
"""
from __future__ import annotations

from typing import Any

from core.easycrypt.session.session_prover_workspace_schema import (
    PROVER_WORKSPACE_VIEW_KEYS,
)
from workflow.proof_state_compiler.profile_registry import (
    runtime_profile_registration,
)
from workflow.proof_state_compiler.surface_contract import SurfaceProfile


def ensure_current_surface_profile(profile_id: str | None) -> SurfaceProfile:
    return runtime_profile_registration(profile_id).turn_profile


def project_current_workspace_view(
    view: dict[str, Any],
    profile_id: str,
) -> dict[str, Any]:
    """Erase durable carrier fields without invoking a legacy surface pass.

    ``view_hash`` is dropped too: it covers the unprojected view, so the
    caller recomputes it over the projected one.
    """

    ensure_current_surface_profile(profile_id)
    return {
        key: value
        for key, value in view.items()
        if key in PROVER_WORKSPACE_VIEW_KEYS and key != "view_hash"
    }


def require_current_workspace_view(
    view: object,
    *,
    profile_id: str,
    label: str,
) -> dict[str, Any]:
    ensure_current_surface_profile(profile_id)
    if not isinstance(view, dict):
        raise TypeError(f"{label} must be an object")
    unsupported = sorted(set(view) - PROVER_WORKSPACE_VIEW_KEYS)
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
