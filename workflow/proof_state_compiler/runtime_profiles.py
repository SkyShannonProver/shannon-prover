"""Runtime profile projection for ordinary user-facing configuration.

There is no unprofiled or historical fallback. An omitted public profile uses
the curated compiler treatment. Private research identities are resolved only
through the eval harness and are never returned by
``current_surface_profile_names``.
"""
from __future__ import annotations

from typing import Any

from core.context_intents import (
    INTENT_CLASS_PROOF_CONTROL,
    INTENT_CLASS_PROOF_MUTATION,
    intent_spec,
    persistent_control_names,
)
from workflow.proof_state_compiler.surface_profiles import (
    CURRENT_SURFACE_PROFILES,
    ensure_current_surface_profile,
)


def resolve_runtime_surface_profile(profile_id: str | None) -> Any:
    return ensure_current_surface_profile(profile_id)


def ensure_supported_runtime_surface_profile(profile_id: str | None) -> Any:
    return ensure_current_surface_profile(profile_id)


def allowed_runtime_intents(profile_id: str | None) -> frozenset[str]:
    return frozenset(ensure_current_surface_profile(profile_id).allowed_intents)


def runtime_surface_uses_goal_only(profile_id: str | None) -> bool:
    return ensure_current_surface_profile(profile_id).base_surface == "goal_only"


def current_surface_profile_names() -> list[str]:
    return sorted(CURRENT_SURFACE_PROFILES)


def effective_runtime_surface_manifest(profile_id: str | None) -> dict[str, Any]:
    current = ensure_current_surface_profile(profile_id)
    allowed = frozenset(current.allowed_intents)
    workspace_keys = {
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
    controls = persistent_control_names()
    return {
        "schema_version": 1,
        "profile": current.name,
        "stage": current.stage,
        "paper_level": current.paper_level,
        "allowed_intents": sorted(allowed),
        "proof_mutation_intents": sorted(
            intent
            for intent in allowed
            if intent_spec(intent) is not None
            and intent_spec(intent).intent_class == INTENT_CLASS_PROOF_MUTATION
        ),
        "proof_control_intents": sorted(
            intent
            for intent in allowed
            if intent_spec(intent) is not None
            and intent_spec(intent).intent_class == INTENT_CLASS_PROOF_CONTROL
        ),
        "persistent_controls": sorted(controls),
        "workspace_keys": sorted(workspace_keys),
        "first_ab_excluded_intents": [],
        "treatment_notes": {
            "replay_suffix_mutation_exposed": False,
            "finish_with_admit_nudge": False,
            "checkpoint_menu_overlay": False,
            "structural_checkpoint_facts": False,
        },
    }
