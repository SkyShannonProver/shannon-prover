"""Single composition boundary from catalog/profile to compiler service parts."""

from __future__ import annotations

from dataclasses import dataclass

from core.easycrypt.proof_state_compiler.backend import AdmissionManifest
from core.easycrypt.proof_state_compiler.compiler import ProofStateCompiler
from core.easycrypt.proof_state_compiler.contracts.delivery_policy import (
    DeliveryPolicyCatalog,
    DeliveryPolicyDefinition,
    ResolvedDeliveryPlan,
)
from core.easycrypt.proof_state_compiler.features.registry import (
    FeatureCatalog,
    FeatureDefinition,
)
from workflow.proof_state_compiler.activation import (
    ActivationPlan,
    CompilerProfile,
    FeatureActivation,
    build_activation_plan,
)
from workflow.proof_state_compiler.manifests import build_admission_manifest
from workflow.proof_state_compiler.delivery_policy import resolve_delivery_plan


@dataclass(frozen=True)
class CompilerAssembly:
    """The only valid bundle of pass, certification, and admission settings."""

    activation_plan: ActivationPlan
    delivery_plan: ResolvedDeliveryPlan
    compiler: ProofStateCompiler
    manifest: AdmissionManifest

    def __post_init__(self) -> None:
        compiler_ids = tuple(
            item.spec.feature_id for item in self.compiler.features
        )
        plan = self.activation_plan
        delivery = self.delivery_plan
        if delivery.profile_id != plan.profile_id:
            raise ValueError("delivery plan identity diverges from activation plan")
        if self.manifest.manifest_id != plan.profile_id:
            raise ValueError("manifest identity diverges from activation plan")
        if compiler_ids != plan.pass_feature_ids:
            raise ValueError("compiler features diverge from activation plan")
        if self.manifest.certification_feature_ids != (
            plan.certification_feature_ids
        ):
            raise ValueError("certification manifest diverges from activation plan")
        if self.manifest.admitted_feature_ids != delivery.admitted_feature_ids:
            raise ValueError("admission manifest diverges from delivery plan")
        if self.manifest.delivery_plan != delivery:
            raise ValueError("admission delivery plan diverges from assembly")


def assemble_compiler_profile(
    profile: CompilerProfile,
    catalog: FeatureCatalog,
    delivery_policy_catalog: DeliveryPolicyCatalog,
) -> CompilerAssembly:
    """Assemble every stage from the same immutable activation plan."""

    plan = build_activation_plan(profile, catalog)
    delivery_plan = resolve_delivery_plan(
        profile,
        plan,
        catalog,
        delivery_policy_catalog,
    )
    features = catalog.select(plan.pass_feature_ids)
    compiler = ProofStateCompiler(features=features)
    manifest = build_admission_manifest(
        manifest_id=profile.profile_id,
        features=features,
        certification_feature_ids=plan.certification_feature_ids,
        admitted_feature_ids=delivery_plan.admitted_feature_ids,
        delivery_plan=delivery_plan,
    )
    return CompilerAssembly(
        activation_plan=plan,
        delivery_plan=delivery_plan,
        compiler=compiler,
        manifest=manifest,
    )


def assemble_feature_set(
    *,
    profile_id: str,
    features: tuple[FeatureDefinition, ...],
    modes: dict[str, str],
    delivery_policies: tuple[DeliveryPolicyDefinition, ...] = (),
) -> CompilerAssembly:
    """Generic low-level assembly helper for tests and validation sentinels."""

    catalog = FeatureCatalog(definitions=tuple(sorted(
        features,
        key=lambda item: item.spec.feature_id,
    )))
    if set(modes) != set(catalog.feature_ids):
        raise ValueError("feature-set assembly requires one mode per definition")
    profile = CompilerProfile(
        profile_id=profile_id,
        activations=tuple(
            FeatureActivation(feature_id, modes[feature_id])
            for feature_id in catalog.feature_ids
        ),
        delivery_policy_ids=tuple(
            item.policy_id for item in delivery_policies
        ),
    )
    policy_catalog = DeliveryPolicyCatalog(definitions=tuple(sorted(
        delivery_policies,
        key=lambda item: item.policy_id,
    )))
    return assemble_compiler_profile(profile, catalog, policy_catalog)
