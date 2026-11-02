"""Test-only assemblies of shipped features; no research registry is needed."""
from __future__ import annotations

from core.easycrypt.proof_state_compiler.features.catalog import (
    production_feature_catalog,
)
from workflow.proof_state_compiler.activation import TREATMENT
from workflow.proof_state_compiler.assembly import (
    CompilerAssembly,
    assemble_feature_set,
)
from workflow.proof_state_compiler.delivery_policies import (
    default_delivery_policy_catalog,
)


def feature_assembly(*feature_ids: str, mode: str) -> CompilerAssembly:
    """Keep feature selection explicit while using production policy definitions."""
    features = production_feature_catalog().select(tuple(sorted(feature_ids)))
    policies = tuple(
        policy
        for policy in default_delivery_policy_catalog().definitions
        if mode == TREATMENT
        and policy.compatible_feature_ids in tuple((item,) for item in feature_ids)
    )
    return assemble_feature_set(
        profile_id="test:" + "+".join(sorted(feature_ids)) + ":" + mode,
        features=features,
        modes={feature_id: mode for feature_id in feature_ids},
        delivery_policies=policies,
    )
