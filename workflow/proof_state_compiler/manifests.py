"""Evidence-gated admission manifests for control and treatment arms."""

from __future__ import annotations

from core.easycrypt.proof_state_compiler.backend import AdmissionManifest
from core.easycrypt.proof_state_compiler.contracts.delivery_policy import (
    ResolvedDeliveryPlan,
)
from core.easycrypt.proof_state_compiler.features.registry import FeatureDefinition


def build_admission_manifest(
    *,
    manifest_id: str,
    features: tuple[FeatureDefinition, ...],
    admitted_feature_ids: tuple[str, ...],
    certification_feature_ids: tuple[str, ...] | None = None,
    delivery_plan: ResolvedDeliveryPlan,
) -> AdmissionManifest:
    """Freeze an experiment arm only when every evidence gate is open."""

    definitions = {item.spec.feature_id: item for item in features}
    if len(definitions) != len(features):
        raise ValueError("manifest assembly received duplicate feature IDs")
    certification_ids = (
        admitted_feature_ids
        if certification_feature_ids is None
        else certification_feature_ids
    )
    for feature_id in tuple(dict.fromkeys(
        certification_ids + admitted_feature_ids
    )):
        definition = definitions.get(feature_id)
        if definition is None:
            raise ValueError(
                f"manifest selects unregistered feature {feature_id!r}"
            )
        if definition.spec.gate.status == "hold":
            raise ValueError(f"feature {feature_id!r} has a closed evidence gate")
    if delivery_plan.profile_id != manifest_id:
        raise ValueError("delivery plan identity diverges from manifest")
    if delivery_plan.admitted_feature_ids != tuple(sorted(admitted_feature_ids)):
        raise ValueError("delivery plan feature bindings diverge from admission")
    return AdmissionManifest(
        manifest_id=manifest_id,
        certification_feature_ids=certification_ids,
        admitted_feature_ids=admitted_feature_ids,
        delivery_plan=delivery_plan,
    )
