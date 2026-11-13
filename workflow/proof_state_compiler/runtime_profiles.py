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
from core.easycrypt.session.session_prover_workspace_schema import (
    PROVER_WORKSPACE_VIEW_KEYS,
)
from workflow.proof_state_compiler.profile_registry import PRODUCTION_TURN_PROFILES
from workflow.proof_state_compiler.surface_profiles import (
    ensure_current_surface_profile,
)


def allowed_runtime_intents(profile_id: str | None) -> frozenset[str]:
    return frozenset(ensure_current_surface_profile(profile_id).allowed_intents)


def current_surface_profile_names() -> list[str]:
    return sorted(PRODUCTION_TURN_PROFILES)


def effective_runtime_surface_manifest(profile_id: str | None) -> dict[str, Any]:
    current = ensure_current_surface_profile(profile_id)
    allowed = frozenset(current.allowed_intents)
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
        "workspace_keys": sorted(PROVER_WORKSPACE_VIEW_KEYS),
    }
