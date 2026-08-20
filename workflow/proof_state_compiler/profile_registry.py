"""Production runtime-profile composition root.

Ordinary Shannon runs expose exactly the goal-only fallback and the curated
compiler treatment. Hidden audits and single-feature ablations are research
assets, resolved lazily from ``workflow.validation`` only when the evaluation
harness supplies their exact internal identity.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from core.context_intents import persistent_control_names
from core.easycrypt.proof_state_compiler.features.compound_tactic_prefix_recovery import (
    COMPOUND_TACTIC_PREFIX_RECOVERY_FEATURE_ID,
)
from core.easycrypt.proof_state_compiler.features.intro_pattern_repair import (
    INTRO_PATTERN_REPAIR_FEATURE_ID,
)
from core.easycrypt.proof_state_compiler.features.operation_binding_repair import (
    OPERATION_BINDING_REPAIR_FEATURE_ID,
)
from core.easycrypt.proof_state_compiler.features.phl_transitivity_boundary_repair import (
    PHL_TRANSITIVITY_BOUNDARY_REPAIR_FEATURE_ID,
)
from core.easycrypt.proof_state_compiler.features.pure_tail_recovery import (
    PURE_TAIL_RECOVERY_FEATURE_ID,
)
from core.easycrypt.proof_state_compiler.features.relation_bridge_realization import (
    RELATION_BRIDGE_REALIZATION_FEATURE_ID,
)
from core.easycrypt.proof_state_compiler.features.tactic_dialect_repair import (
    TACTIC_DIALECT_REPAIR_FEATURE_ID,
)
from workflow.proof_state_compiler.activation import (
    TREATMENT,
    CompilerProfile,
    FeatureActivation,
)
from workflow.proof_state_compiler.delivery_policies import (
    COMPOUND_TACTIC_PREFIX_RECOVERY_ONCE_POLICY_ID,
    INTRO_PATTERN_REPAIR_ONCE_POLICY_ID,
    OPERATION_BINDING_REPAIR_ONCE_POLICY_ID,
    PHL_TRANSITIVITY_BOUNDARY_ONCE_POLICY_ID,
    PURE_TAIL_RECOVERY_ONCE_POLICY_ID,
    RELATION_BRIDGE_ONCE_POLICY_ID,
    TACTIC_DIALECT_REPAIR_ONCE_POLICY_ID,
)
from workflow.proof_state_compiler.profile_ids import (
    ALL_CANDIDATE_TREATMENT_PROFILE,
    DEFAULT_CURRENT_SURFACE_PROFILE,
    L1_CONTROL_PROFILE,
)
from workflow.proof_state_compiler.surface_contract import SurfaceProfile


@dataclass(frozen=True)
class RuntimeProfileRegistration:
    """One compiler configuration and its matched manager-turn envelope."""

    profile_id: str
    compiler_profile: CompilerProfile
    turn_profile: SurfaceProfile

    def __post_init__(self) -> None:
        if not self.profile_id:
            raise ValueError("runtime profile registration requires an ID")
        if self.compiler_profile.profile_id != self.profile_id:
            raise ValueError("compiler profile identity diverges from registry")
        if self.turn_profile.name != self.profile_id:
            raise ValueError("turn profile identity diverges from registry")


_CONTROL_INTENTS = persistent_control_names()


def runtime_turn_profile(
    profile_id: str,
    *,
    stage: str,
    description: str,
    paper_level: str,
    paper_role: str = "paper",
) -> SurfaceProfile:
    """Build the common goal-only turn envelope for one registered arm."""

    return SurfaceProfile(
        name=profile_id,
        stage=stage,
        description=description,
        allowed_intents=_CONTROL_INTENTS,
        paper_level=paper_level,
        paper_role=paper_role,
        base_surface="goal_only",
    )


_PRODUCTION_REGISTRATIONS = (
    RuntimeProfileRegistration(
        profile_id=ALL_CANDIDATE_TREATMENT_PROFILE,
        compiler_profile=CompilerProfile(
            profile_id=ALL_CANDIDATE_TREATMENT_PROFILE,
            activations=(
                FeatureActivation(
                    COMPOUND_TACTIC_PREFIX_RECOVERY_FEATURE_ID, TREATMENT
                ),
                FeatureActivation(INTRO_PATTERN_REPAIR_FEATURE_ID, TREATMENT),
                FeatureActivation(OPERATION_BINDING_REPAIR_FEATURE_ID, TREATMENT),
                FeatureActivation(
                    PHL_TRANSITIVITY_BOUNDARY_REPAIR_FEATURE_ID, TREATMENT
                ),
                FeatureActivation(PURE_TAIL_RECOVERY_FEATURE_ID, TREATMENT),
                FeatureActivation(
                    RELATION_BRIDGE_REALIZATION_FEATURE_ID, TREATMENT
                ),
                FeatureActivation(TACTIC_DIALECT_REPAIR_FEATURE_ID, TREATMENT),
            ),
            delivery_policy_ids=(
                COMPOUND_TACTIC_PREFIX_RECOVERY_ONCE_POLICY_ID,
                INTRO_PATTERN_REPAIR_ONCE_POLICY_ID,
                OPERATION_BINDING_REPAIR_ONCE_POLICY_ID,
                PHL_TRANSITIVITY_BOUNDARY_ONCE_POLICY_ID,
                PURE_TAIL_RECOVERY_ONCE_POLICY_ID,
                RELATION_BRIDGE_ONCE_POLICY_ID,
                TACTIC_DIALECT_REPAIR_ONCE_POLICY_ID,
            ),
        ),
        turn_profile=runtime_turn_profile(
            ALL_CANDIDATE_TREATMENT_PROFILE,
            stage="l4_proof_state_compiler_v2",
            description=(
                "Curated compiler treatment. Every enabled feature may expose "
                "at most its admitted, bounded result."
            ),
            paper_level="L4",
        ),
    ),
    RuntimeProfileRegistration(
        profile_id=L1_CONTROL_PROFILE,
        compiler_profile=CompilerProfile(profile_id=L1_CONTROL_PROFILE),
        turn_profile=runtime_turn_profile(
            L1_CONTROL_PROFILE,
            stage="l1_goal_projection",
            description="Goal-only managed runtime with the compiler disabled.",
            paper_level="L1",
        ),
    ),
)


PRODUCTION_PROFILE_REGISTRATIONS: Mapping[
    str, RuntimeProfileRegistration
] = MappingProxyType({
    item.profile_id: item
    for item in sorted(_PRODUCTION_REGISTRATIONS, key=lambda item: item.profile_id)
})
PRODUCTION_PROFILE_IDS = frozenset(PRODUCTION_PROFILE_REGISTRATIONS)
PRODUCTION_COMPILER_PROFILES: Mapping[str, CompilerProfile] = MappingProxyType({
    profile_id: registration.compiler_profile
    for profile_id, registration in PRODUCTION_PROFILE_REGISTRATIONS.items()
})
PRODUCTION_TURN_PROFILES: Mapping[str, SurfaceProfile] = MappingProxyType({
    profile_id: registration.turn_profile
    for profile_id, registration in PRODUCTION_PROFILE_REGISTRATIONS.items()
})

# Existing runtime projection names now intentionally mean production only.
CURRENT_PROFILE_REGISTRATIONS = PRODUCTION_PROFILE_REGISTRATIONS
CURRENT_PROFILE_IDS = PRODUCTION_PROFILE_IDS
CURRENT_COMPILER_PROFILES = PRODUCTION_COMPILER_PROFILES
CURRENT_TURN_PROFILES = PRODUCTION_TURN_PROFILES


def _research_profile_registrations() -> Mapping[
    str, RuntimeProfileRegistration
]:
    try:
        from workflow.proof_state_compiler.research.proof_state_compiler_research_profile_registry import (
            RESEARCH_PROFILE_REGISTRATIONS,
        )
    except ModuleNotFoundError as exc:
        if exc.name != (
            "workflow.proof_state_compiler.research.proof_state_compiler_research_profile_registry"
        ):
            raise
        return MappingProxyType({})

    return RESEARCH_PROFILE_REGISTRATIONS


def runtime_profile_registration(profile_id: str | None) -> RuntimeProfileRegistration:
    """Resolve a production or exact research identity for internal runtime use."""

    normalized = str(profile_id or "").strip() or DEFAULT_CURRENT_SURFACE_PROFILE
    production = PRODUCTION_PROFILE_REGISTRATIONS.get(normalized)
    if production is not None:
        return production
    research = _research_profile_registrations().get(normalized)
    if research is not None:
        return research
    raise ValueError(
        f"profile {profile_id!r} is not a registered proof-state compiler runtime"
    )


def normalize_runtime_surface_profile_id(profile_id: str | None) -> str:
    return runtime_profile_registration(profile_id).profile_id


def normalize_public_surface_profile_id(profile_id: str | None) -> str:
    """Resolve only profiles supported by an ordinary user configuration."""

    normalized = str(profile_id or "").strip() or DEFAULT_CURRENT_SURFACE_PROFILE
    if normalized not in PRODUCTION_PROFILE_IDS:
        known = ", ".join(sorted(PRODUCTION_PROFILE_IDS))
        raise ValueError(
            f"profile {profile_id!r} is not a public runtime profile; "
            f"public profiles: {known}"
        )
    return normalized


def normalize_research_surface_profile_id(profile_id: str | None) -> str:
    """Resolve one exact private research arm; never default implicitly."""

    normalized = str(profile_id or "").strip()
    if not normalized or normalized not in _research_profile_registrations():
        raise ValueError(f"profile {profile_id!r} is not a research profile")
    return normalized


def all_internal_profile_ids() -> frozenset[str]:
    """Return the complete private research namespace for suite validation."""

    return frozenset(PRODUCTION_PROFILE_IDS | _research_profile_registrations().keys())
