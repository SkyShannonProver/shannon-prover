"""Single declarative registry for current runtime/experiment profiles.

A profile has two orthogonal projections: compiler activation/delivery and the
manager turn envelope.  They are declared together here so adding or deleting
an experiment arm cannot update one projection while forgetting the other.
Feature semantics and delivery-policy definitions remain in their own catalogs.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from core.context_intents import persistent_control_names
from core.easycrypt.proof_state_compiler.features.accepted_contract_retention import (
    ACCEPTED_CONTRACT_RETENTION_FEATURE_ID,
)
from core.easycrypt.proof_state_compiler.features.intro_pattern_repair import (
    INTRO_PATTERN_REPAIR_FEATURE_ID,
)
from core.easycrypt.proof_state_compiler.features.compound_tactic_prefix_recovery import (
    COMPOUND_TACTIC_PREFIX_RECOVERY_FEATURE_ID,
)
from core.easycrypt.proof_state_compiler.features.operation_binding_repair import (
    OPERATION_BINDING_REPAIR_FEATURE_ID,
)
from core.easycrypt.proof_state_compiler.features.phl_transitivity_boundary_repair import (
    PHL_TRANSITIVITY_BOUNDARY_REPAIR_FEATURE_ID,
)
from core.easycrypt.proof_state_compiler.features.relation_bridge_realization import (
    RELATION_BRIDGE_REALIZATION_FEATURE_ID,
)
from core.easycrypt.proof_state_compiler.features.tactic_dialect_repair import (
    TACTIC_DIALECT_REPAIR_FEATURE_ID,
)
from core.easycrypt.proof_state_compiler.features.program_operation_readiness import (
    PROGRAM_OPERATION_READINESS_FEATURE_ID,
)
from core.easycrypt.proof_state_compiler.features.pure_tail_recovery import (
    PURE_TAIL_RECOVERY_FEATURE_ID,
)
from workflow.proof_state_compiler.activation import (
    AUDIT,
    TREATMENT,
    CompilerProfile,
    FeatureActivation,
)
from workflow.proof_state_compiler.delivery_policies import (
    COMPOUND_TACTIC_PREFIX_RECOVERY_ONCE_POLICY_ID,
    INTRO_PATTERN_REPAIR_ONCE_POLICY_ID,
    OPERATION_BINDING_REPAIR_ONCE_POLICY_ID,
    PHL_TRANSITIVITY_BOUNDARY_ONCE_POLICY_ID,
    RELATION_BRIDGE_ONCE_POLICY_ID,
    TACTIC_DIALECT_REPAIR_ONCE_POLICY_ID,
    PURE_TAIL_RECOVERY_ONCE_POLICY_ID,
)
from workflow.proof_state_compiler.profile_ids import (
    ALL_CANDIDATE_AUDIT_PROFILE,
    ALL_CANDIDATE_TREATMENT_PROFILE,
    COMPOUND_TACTIC_PREFIX_RECOVERY_AUDIT_PROFILE,
    COMPOUND_TACTIC_PREFIX_RECOVERY_TREATMENT_PROFILE,
    DEFAULT_CURRENT_SURFACE_PROFILE,
    L1_CONTROL_PROFILE,
    M04_AUDIT_PROFILE,
    M09_AUDIT_PROFILE,
    INTRO_PATTERN_REPAIR_AUDIT_PROFILE,
    INTRO_PATTERN_REPAIR_TREATMENT_PROFILE,
    OPERATION_BINDING_REPAIR_AUDIT_PROFILE,
    OPERATION_BINDING_REPAIR_TREATMENT_PROFILE,
    PHL_TRANSITIVITY_BOUNDARY_AUDIT_PROFILE,
    PHL_TRANSITIVITY_BOUNDARY_TREATMENT_PROFILE,
    RELATION_BRIDGE_REALIZATION_AUDIT_PROFILE,
    RELATION_BRIDGE_REALIZATION_TREATMENT_PROFILE,
    TACTIC_DIALECT_REPAIR_AUDIT_PROFILE,
    TACTIC_DIALECT_REPAIR_TREATMENT_PROFILE,
    PURE_TAIL_RECOVERY_AUDIT_PROFILE,
    PURE_TAIL_RECOVERY_TREATMENT_PROFILE,
)
from workflow.proof_state_compiler.surface_contract import SurfaceProfile


@dataclass(frozen=True)
class RuntimeProfileRegistration:
    """One complete experiment-arm registration at the runtime boundary."""

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


def _turn_profile(
    profile_id: str,
    *,
    stage: str,
    description: str,
    paper_level: str,
    paper_role: str = "paper",
) -> SurfaceProfile:
    return SurfaceProfile(
        name=profile_id,
        stage=stage,
        description=description,
        allowed_intents=_CONTROL_INTENTS,
        paper_level=paper_level,
        paper_role=paper_role,
        base_surface="goal_only",
    )


_REGISTRATIONS = tuple(sorted(
    (
        RuntimeProfileRegistration(
            profile_id=ALL_CANDIDATE_AUDIT_PROFILE,
            compiler_profile=CompilerProfile(
                profile_id=ALL_CANDIDATE_AUDIT_PROFILE,
                activations=(
                    FeatureActivation(
                        ACCEPTED_CONTRACT_RETENTION_FEATURE_ID, AUDIT
                    ),
                    FeatureActivation(
                        COMPOUND_TACTIC_PREFIX_RECOVERY_FEATURE_ID, AUDIT
                    ),
                    FeatureActivation(INTRO_PATTERN_REPAIR_FEATURE_ID, AUDIT),
                    FeatureActivation(OPERATION_BINDING_REPAIR_FEATURE_ID, AUDIT),
                    FeatureActivation(
                        PHL_TRANSITIVITY_BOUNDARY_REPAIR_FEATURE_ID, AUDIT
                    ),
                    FeatureActivation(
                        PROGRAM_OPERATION_READINESS_FEATURE_ID, AUDIT
                    ),
                    FeatureActivation(PURE_TAIL_RECOVERY_FEATURE_ID, AUDIT),
                    FeatureActivation(
                        RELATION_BRIDGE_REALIZATION_FEATURE_ID, AUDIT
                    ),
                    FeatureActivation(TACTIC_DIALECT_REPAIR_FEATURE_ID, AUDIT),
                ),
            ),
            turn_profile=_turn_profile(
                ALL_CANDIDATE_AUDIT_PROFILE,
                stage="l4_proof_state_compiler_v2",
                description=(
                    "Matched L1 envelope with every evidence-open recovery "
                    "candidate computed but hidden."
                ),
                paper_level="L4-audit",
                paper_role="ablation",
            ),
        ),
        RuntimeProfileRegistration(
            profile_id=ALL_CANDIDATE_TREATMENT_PROFILE,
            compiler_profile=CompilerProfile(
                profile_id=ALL_CANDIDATE_TREATMENT_PROFILE,
                activations=(
                    FeatureActivation(
                        ACCEPTED_CONTRACT_RETENTION_FEATURE_ID, AUDIT
                    ),
                    FeatureActivation(
                        COMPOUND_TACTIC_PREFIX_RECOVERY_FEATURE_ID, TREATMENT
                    ),
                    FeatureActivation(
                        INTRO_PATTERN_REPAIR_FEATURE_ID, TREATMENT
                    ),
                    FeatureActivation(
                        OPERATION_BINDING_REPAIR_FEATURE_ID, TREATMENT
                    ),
                    FeatureActivation(
                        PHL_TRANSITIVITY_BOUNDARY_REPAIR_FEATURE_ID, TREATMENT
                    ),
                    FeatureActivation(
                        PROGRAM_OPERATION_READINESS_FEATURE_ID, AUDIT
                    ),
                    FeatureActivation(PURE_TAIL_RECOVERY_FEATURE_ID, TREATMENT),
                    FeatureActivation(
                        RELATION_BRIDGE_REALIZATION_FEATURE_ID, TREATMENT
                    ),
                    FeatureActivation(
                        TACTIC_DIALECT_REPAIR_FEATURE_ID, TREATMENT
                    ),
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
            turn_profile=_turn_profile(
                ALL_CANDIDATE_TREATMENT_PROFILE,
                stage="l4_proof_state_compiler_v2",
                description=(
                    "Matched L1 envelope with all evidence-open recovery "
                    "treatments and hidden state-refresh computation."
                ),
                paper_level="L4",
            ),
        ),
        RuntimeProfileRegistration(
            profile_id=COMPOUND_TACTIC_PREFIX_RECOVERY_AUDIT_PROFILE,
            compiler_profile=CompilerProfile(
                profile_id=COMPOUND_TACTIC_PREFIX_RECOVERY_AUDIT_PROFILE,
                activations=(FeatureActivation(
                    COMPOUND_TACTIC_PREFIX_RECOVERY_FEATURE_ID, AUDIT
                ),),
            ),
            turn_profile=_turn_profile(
                COMPOUND_TACTIC_PREFIX_RECOVERY_AUDIT_PROFILE,
                stage="l4_proof_state_compiler_v2",
                description=(
                    "Matched L1 envelope with hidden compound accepted-prefix "
                    "diagnostic computation."
                ),
                paper_level="L4-audit",
                paper_role="ablation",
            ),
        ),
        RuntimeProfileRegistration(
            profile_id=COMPOUND_TACTIC_PREFIX_RECOVERY_TREATMENT_PROFILE,
            compiler_profile=CompilerProfile(
                profile_id=COMPOUND_TACTIC_PREFIX_RECOVERY_TREATMENT_PROFILE,
                activations=(FeatureActivation(
                    COMPOUND_TACTIC_PREFIX_RECOVERY_FEATURE_ID, TREATMENT
                ),),
                delivery_policy_ids=(
                    COMPOUND_TACTIC_PREFIX_RECOVERY_ONCE_POLICY_ID,
                ),
            ),
            turn_profile=_turn_profile(
                COMPOUND_TACTIC_PREFIX_RECOVERY_TREATMENT_PROFILE,
                stage="l4_proof_state_compiler_v2",
                description=(
                    "Matched L1 envelope plus one native-localized boundary "
                    "inside the agent's rolled-back compound tactic."
                ),
                paper_level="L4",
            ),
        ),
        RuntimeProfileRegistration(
            profile_id=L1_CONTROL_PROFILE,
            compiler_profile=CompilerProfile(profile_id=L1_CONTROL_PROFILE),
            turn_profile=_turn_profile(
                L1_CONTROL_PROFILE,
                stage="l1_goal_projection",
                description="Goal-only managed control with no compiler output.",
                paper_level="L1",
            ),
        ),
        RuntimeProfileRegistration(
            profile_id=M04_AUDIT_PROFILE,
            compiler_profile=CompilerProfile(
                profile_id=M04_AUDIT_PROFILE,
                activations=(FeatureActivation(
                    PROGRAM_OPERATION_READINESS_FEATURE_ID,
                    AUDIT,
                ),),
            ),
            turn_profile=_turn_profile(
                M04_AUDIT_PROFILE,
                stage="l4_proof_state_compiler_v2",
                description="Matched L1 envelope with hidden M04 audit computation.",
                paper_level="L4-audit",
                paper_role="ablation",
            ),
        ),
        RuntimeProfileRegistration(
            profile_id=M09_AUDIT_PROFILE,
            compiler_profile=CompilerProfile(
                profile_id=M09_AUDIT_PROFILE,
                activations=(FeatureActivation(
                    ACCEPTED_CONTRACT_RETENTION_FEATURE_ID,
                    AUDIT,
                ),),
            ),
            turn_profile=_turn_profile(
                M09_AUDIT_PROFILE,
                stage="l4_proof_state_compiler_v2",
                description="Matched L1 envelope with hidden M09 audit computation.",
                paper_level="L4-audit",
                paper_role="ablation",
            ),
        ),
        RuntimeProfileRegistration(
            profile_id=OPERATION_BINDING_REPAIR_AUDIT_PROFILE,
            compiler_profile=CompilerProfile(
                profile_id=OPERATION_BINDING_REPAIR_AUDIT_PROFILE,
                activations=(FeatureActivation(
                    OPERATION_BINDING_REPAIR_FEATURE_ID,
                    AUDIT,
                ),),
            ),
            turn_profile=_turn_profile(
                OPERATION_BINDING_REPAIR_AUDIT_PROFILE,
                stage="l4_proof_state_compiler_v2",
                description=(
                    "Matched L1 envelope with hidden operation-binding recovery "
                    "audit."
                ),
                paper_level="L4-audit",
                paper_role="ablation",
            ),
        ),
        RuntimeProfileRegistration(
            profile_id=OPERATION_BINDING_REPAIR_TREATMENT_PROFILE,
            compiler_profile=CompilerProfile(
                profile_id=OPERATION_BINDING_REPAIR_TREATMENT_PROFILE,
                activations=(FeatureActivation(
                    OPERATION_BINDING_REPAIR_FEATURE_ID,
                    TREATMENT,
                ),),
                delivery_policy_ids=(
                    OPERATION_BINDING_REPAIR_ONCE_POLICY_ID,
                ),
            ),
            turn_profile=_turn_profile(
                OPERATION_BINDING_REPAIR_TREATMENT_PROFILE,
                stage="l4_proof_state_compiler_v2",
                description=(
                    "Matched L1 envelope plus one failure-linked native-checked "
                    "repair."
                ),
                paper_level="L4",
            ),
        ),
        RuntimeProfileRegistration(
            profile_id=PURE_TAIL_RECOVERY_AUDIT_PROFILE,
            compiler_profile=CompilerProfile(
                profile_id=PURE_TAIL_RECOVERY_AUDIT_PROFILE,
                activations=(FeatureActivation(
                    PURE_TAIL_RECOVERY_FEATURE_ID, AUDIT
                ),),
            ),
            turn_profile=_turn_profile(
                PURE_TAIL_RECOVERY_AUDIT_PROFILE,
                stage="l4_proof_state_compiler_v2",
                description=(
                    "Matched L1 envelope with hidden commitment-relative "
                    "pure-tail recovery computation."
                ),
                paper_level="L4-audit",
                paper_role="ablation",
            ),
        ),
        RuntimeProfileRegistration(
            profile_id=INTRO_PATTERN_REPAIR_AUDIT_PROFILE,
            compiler_profile=CompilerProfile(
                profile_id=INTRO_PATTERN_REPAIR_AUDIT_PROFILE,
                activations=(FeatureActivation(
                    INTRO_PATTERN_REPAIR_FEATURE_ID, AUDIT
                ),),
            ),
            turn_profile=_turn_profile(
                INTRO_PATTERN_REPAIR_AUDIT_PROFILE,
                stage="l4_proof_state_compiler_v2",
                description=(
                    "Matched L1 envelope with hidden structured intro-pattern "
                    "recovery computation."
                ),
                paper_level="L4-audit",
                paper_role="ablation",
            ),
        ),
        RuntimeProfileRegistration(
            profile_id=INTRO_PATTERN_REPAIR_TREATMENT_PROFILE,
            compiler_profile=CompilerProfile(
                profile_id=INTRO_PATTERN_REPAIR_TREATMENT_PROFILE,
                activations=(FeatureActivation(
                    INTRO_PATTERN_REPAIR_FEATURE_ID, TREATMENT
                ),),
                delivery_policy_ids=(INTRO_PATTERN_REPAIR_ONCE_POLICY_ID,),
            ),
            turn_profile=_turn_profile(
                INTRO_PATTERN_REPAIR_TREATMENT_PROFILE,
                stage="l4_proof_state_compiler_v2",
                description=(
                    "Matched L1 envelope plus one native-unique canonical "
                    "realization of an already selected destruct pattern."
                ),
                paper_level="L4",
            ),
        ),
        RuntimeProfileRegistration(
            profile_id=PURE_TAIL_RECOVERY_TREATMENT_PROFILE,
            compiler_profile=CompilerProfile(
                profile_id=PURE_TAIL_RECOVERY_TREATMENT_PROFILE,
                activations=(FeatureActivation(
                    PURE_TAIL_RECOVERY_FEATURE_ID, TREATMENT
                ),),
                delivery_policy_ids=(PURE_TAIL_RECOVERY_ONCE_POLICY_ID,),
            ),
            turn_profile=_turn_profile(
                PURE_TAIL_RECOVERY_TREATMENT_PROFILE,
                stage="l4_proof_state_compiler_v2",
                description=(
                    "Matched L1 envelope plus one native-unique target repair "
                    "for an already selected pure-tail rewrite."
                ),
                paper_level="L4",
            ),
        ),
        RuntimeProfileRegistration(
            profile_id=RELATION_BRIDGE_REALIZATION_AUDIT_PROFILE,
            compiler_profile=CompilerProfile(
                profile_id=RELATION_BRIDGE_REALIZATION_AUDIT_PROFILE,
                activations=(
                    FeatureActivation(OPERATION_BINDING_REPAIR_FEATURE_ID, AUDIT),
                    FeatureActivation(RELATION_BRIDGE_REALIZATION_FEATURE_ID, AUDIT),
                ),
            ),
            turn_profile=_turn_profile(
                RELATION_BRIDGE_REALIZATION_AUDIT_PROFILE,
                stage="l4_proof_state_compiler_v2",
                description=(
                    "Matched L1 envelope with hidden operation-binding and "
                    "relation-realization recovery computation."
                ),
                paper_level="L4-audit",
                paper_role="ablation",
            ),
        ),
        RuntimeProfileRegistration(
            profile_id=RELATION_BRIDGE_REALIZATION_TREATMENT_PROFILE,
            compiler_profile=CompilerProfile(
                profile_id=RELATION_BRIDGE_REALIZATION_TREATMENT_PROFILE,
                activations=(
                    FeatureActivation(
                        OPERATION_BINDING_REPAIR_FEATURE_ID, TREATMENT
                    ),
                    FeatureActivation(
                        RELATION_BRIDGE_REALIZATION_FEATURE_ID, TREATMENT
                    ),
                ),
                delivery_policy_ids=(
                    OPERATION_BINDING_REPAIR_ONCE_POLICY_ID,
                    RELATION_BRIDGE_ONCE_POLICY_ID,
                ),
            ),
            turn_profile=_turn_profile(
                RELATION_BRIDGE_REALIZATION_TREATMENT_PROFILE,
                stage="l4_proof_state_compiler_v2",
                description=(
                    "Matched L1 envelope plus one uniquely owned current-failure "
                    "repair, including native relation realization."
                ),
                paper_level="L4",
            ),
        ),
        RuntimeProfileRegistration(
            profile_id=PHL_TRANSITIVITY_BOUNDARY_AUDIT_PROFILE,
            compiler_profile=CompilerProfile(
                profile_id=PHL_TRANSITIVITY_BOUNDARY_AUDIT_PROFILE,
                activations=(FeatureActivation(
                    PHL_TRANSITIVITY_BOUNDARY_REPAIR_FEATURE_ID, AUDIT
                ),),
            ),
            turn_profile=_turn_profile(
                PHL_TRANSITIVITY_BOUNDARY_AUDIT_PROFILE,
                stage="l4_proof_state_compiler_v2",
                description=(
                    "Matched L1 envelope with hidden PHL transitivity boundary "
                    "recovery computation."
                ),
                paper_level="L4-audit",
                paper_role="ablation",
            ),
        ),
        RuntimeProfileRegistration(
            profile_id=PHL_TRANSITIVITY_BOUNDARY_TREATMENT_PROFILE,
            compiler_profile=CompilerProfile(
                profile_id=PHL_TRANSITIVITY_BOUNDARY_TREATMENT_PROFILE,
                activations=(FeatureActivation(
                    PHL_TRANSITIVITY_BOUNDARY_REPAIR_FEATURE_ID, TREATMENT
                ),),
                delivery_policy_ids=(
                    PHL_TRANSITIVITY_BOUNDARY_ONCE_POLICY_ID,
                ),
            ),
            turn_profile=_turn_profile(
                PHL_TRANSITIVITY_BOUNDARY_TREATMENT_PROFILE,
                stage="l4_proof_state_compiler_v2",
                description=(
                    "Matched L1 envelope plus one native-established PHL "
                    "transitivity boundary diagnostic."
                ),
                paper_level="L4",
            ),
        ),
        RuntimeProfileRegistration(
            profile_id=TACTIC_DIALECT_REPAIR_AUDIT_PROFILE,
            compiler_profile=CompilerProfile(
                profile_id=TACTIC_DIALECT_REPAIR_AUDIT_PROFILE,
                activations=(FeatureActivation(
                    TACTIC_DIALECT_REPAIR_FEATURE_ID, AUDIT
                ),),
            ),
            turn_profile=_turn_profile(
                TACTIC_DIALECT_REPAIR_AUDIT_PROFILE,
                stage="l4_proof_state_compiler_v2",
                description=(
                    "Matched L1 envelope with hidden selected tactic-dialect "
                    "recovery computation."
                ),
                paper_level="L4-audit",
                paper_role="ablation",
            ),
        ),
        RuntimeProfileRegistration(
            profile_id=TACTIC_DIALECT_REPAIR_TREATMENT_PROFILE,
            compiler_profile=CompilerProfile(
                profile_id=TACTIC_DIALECT_REPAIR_TREATMENT_PROFILE,
                activations=(FeatureActivation(
                    TACTIC_DIALECT_REPAIR_FEATURE_ID, TREATMENT
                ),),
                delivery_policy_ids=(TACTIC_DIALECT_REPAIR_ONCE_POLICY_ID,),
            ),
            turn_profile=_turn_profile(
                TACTIC_DIALECT_REPAIR_TREATMENT_PROFILE,
                stage="l4_proof_state_compiler_v2",
                description=(
                    "Matched L1 envelope plus one native-established selected "
                    "tactic-dialect repair or blocker diagnostic."
                ),
                paper_level="L4",
            ),
        ),
    ),
    key=lambda item: item.profile_id,
))
_REGISTRATION_IDS = tuple(item.profile_id for item in _REGISTRATIONS)
if len(_REGISTRATION_IDS) != len(set(_REGISTRATION_IDS)):
    raise ValueError("runtime profile registry contains duplicate IDs")

CURRENT_PROFILE_REGISTRATIONS: Mapping[
    str, RuntimeProfileRegistration
] = MappingProxyType({item.profile_id: item for item in _REGISTRATIONS})
CURRENT_PROFILE_IDS = frozenset(CURRENT_PROFILE_REGISTRATIONS)
CURRENT_COMPILER_PROFILES: Mapping[str, CompilerProfile] = MappingProxyType({
    profile_id: registration.compiler_profile
    for profile_id, registration in CURRENT_PROFILE_REGISTRATIONS.items()
})
CURRENT_TURN_PROFILES: Mapping[str, SurfaceProfile] = MappingProxyType({
    profile_id: registration.turn_profile
    for profile_id, registration in CURRENT_PROFILE_REGISTRATIONS.items()
})


def normalize_current_surface_profile_id(profile_id: str | None) -> str:
    """Return one registered profile ID; omission selects the public compiler."""

    normalized = str(profile_id or "").strip() or DEFAULT_CURRENT_SURFACE_PROFILE
    if normalized not in CURRENT_PROFILE_IDS:
        known = ", ".join(sorted(CURRENT_PROFILE_IDS))
        raise ValueError(
            f"profile {profile_id!r} is not a current compiler-v2 "
            f"surface; current profiles: {known}"
        )
    return normalized
