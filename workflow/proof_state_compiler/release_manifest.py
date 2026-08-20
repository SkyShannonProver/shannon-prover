"""Machine-checkable production boundary for a future public code release."""
from __future__ import annotations

from dataclasses import dataclass

from core.easycrypt.proof_state_compiler.features.catalog import (
    production_feature_catalog,
)
from workflow.proof_state_compiler.activation import TREATMENT
from workflow.proof_state_compiler.profile_ids import (
    ALL_CANDIDATE_TREATMENT_PROFILE,
)
from workflow.proof_state_compiler.profile_registry import (
    PRODUCTION_PROFILE_IDS,
    PRODUCTION_PROFILE_REGISTRATIONS,
)


@dataclass(frozen=True)
class ProductionReleaseManifest:
    """The profiles, feature packages, and policies allowed in production."""

    profile_ids: tuple[str, ...]
    feature_ids: tuple[str, ...]
    delivery_policy_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "kind": "proof_state_compiler_production_release_manifest",
            "profile_ids": list(self.profile_ids),
            "feature_ids": list(self.feature_ids),
            "delivery_policy_ids": list(self.delivery_policy_ids),
        }


def production_release_manifest() -> ProductionReleaseManifest:
    treatment = PRODUCTION_PROFILE_REGISTRATIONS[
        ALL_CANDIDATE_TREATMENT_PROFILE
    ].compiler_profile
    if any(item.mode != TREATMENT for item in treatment.activations):
        raise ValueError("production compiler profile may contain only treatment")
    treatment_feature_ids = tuple(sorted(
        item.feature_id for item in treatment.activations
    ))
    catalog_feature_ids = tuple(sorted(production_feature_catalog().feature_ids))
    if treatment_feature_ids != catalog_feature_ids:
        raise ValueError(
            "production feature catalog must equal the curated treatment set"
        )
    return ProductionReleaseManifest(
        profile_ids=tuple(sorted(PRODUCTION_PROFILE_IDS)),
        feature_ids=treatment_feature_ids,
        delivery_policy_ids=tuple(sorted(treatment.delivery_policy_ids)),
    )
