"""Resolve delivery-policy references independently from feature activation."""

from __future__ import annotations

from core.easycrypt.proof_state_compiler.contracts.delivery_policy import (
    DeliveryPolicyCatalog,
    ResolvedDeliveryPlan,
    empty_delivery_plan,
)
from core.easycrypt.proof_state_compiler.features.registry import FeatureCatalog
from workflow.proof_state_compiler.activation import ActivationPlan, CompilerProfile


def resolve_delivery_plan(
    profile: CompilerProfile,
    activation_plan: ActivationPlan,
    feature_catalog: FeatureCatalog,
    policy_catalog: DeliveryPolicyCatalog,
) -> ResolvedDeliveryPlan:
    """Bind each treatment feature to exactly one compatible policy."""

    policies = policy_catalog.select(profile.delivery_policy_ids)
    admitted = tuple(
        feature_id
        for feature_id, mode in activation_plan.feature_modes
        if mode == "treatment"
    )
    if not admitted:
        if policies:
            raise ValueError("non-treatment profile cannot select delivery policies")
        return empty_delivery_plan(profile.profile_id)
    if not policies:
        raise ValueError("treatment profile requires a registered delivery policy")

    definitions = {
        definition.spec.feature_id: definition
        for definition in feature_catalog.select(admitted)
    }
    bindings: list[tuple[str, str]] = []
    used_policy_ids: set[str] = set()
    for feature_id in admitted:
        definition = definitions[feature_id]
        strategy_classes = {
            contract.strategy_class
            for contract in definition.spec.strategy_contracts
        }
        matches = tuple(
            policy for policy in policies
            if feature_id in policy.compatible_feature_ids
            and policy.rule.strategy_class in strategy_classes
        )
        if len(matches) != 1:
            reason = (
                "missing compatible delivery policy"
                if not matches
                else "duplicate delivery ownership"
            )
            raise ValueError(f"feature {feature_id!r} has {reason}")
        bindings.append((feature_id, matches[0].policy_id))
        used_policy_ids.add(matches[0].policy_id)
    unused = sorted(set(profile.delivery_policy_ids) - used_policy_ids)
    if unused:
        raise ValueError(
            "delivery profile selects incompatible/unused policies: "
            + ", ".join(unused)
        )
    return ResolvedDeliveryPlan(
        profile_id=profile.profile_id,
        policies=policies,
        feature_policy_bindings=tuple(sorted(bindings)),
    )
