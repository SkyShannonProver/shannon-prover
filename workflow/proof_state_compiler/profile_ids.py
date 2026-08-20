"""Public runtime-profile identity vocabulary.

Only identities intended for an ordinary Shannon installation belong here.
Research controls, hidden-audit arms, and single-feature ablations live under
``workflow.proof_state_compiler.research.proof_state_compiler_research_profile_ids`` and are not
part of the public configuration surface.
"""
from __future__ import annotations


L1_CONTROL_PROFILE = "l1_goal_projection"
ALL_CANDIDATE_TREATMENT_PROFILE = "proof_state_compiler"
DEFAULT_CURRENT_SURFACE_PROFILE = ALL_CANDIDATE_TREATMENT_PROFILE


PRODUCTION_PROFILE_IDS = frozenset({
    L1_CONTROL_PROFILE,
    ALL_CANDIDATE_TREATMENT_PROFILE,
})
