"""Declarative, all-stage feature activation contracts."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

from core.easycrypt.proof_state_compiler.features.registry import FeatureCatalog


OFF = "off"
AUDIT = "audit"
TREATMENT = "treatment"
FEATURE_MODES = frozenset({OFF, AUDIT, TREATMENT})


@dataclass(frozen=True)
class FeatureActivation:
    """The only per-feature choice exposed by an experiment profile."""

    feature_id: str
    mode: str

    def __post_init__(self) -> None:
        if not self.feature_id:
            raise ValueError("feature activation requires a feature ID")
        if self.mode not in FEATURE_MODES:
            raise ValueError(f"unsupported feature activation mode {self.mode!r}")


@dataclass(frozen=True)
class CompilerProfile:
    """Declarative experiment profile; absent catalog features are OFF."""

    profile_id: str
    activations: tuple[FeatureActivation, ...] = ()
    delivery_policy_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.profile_id:
            raise ValueError("compiler profile requires an ID")
        feature_ids = tuple(item.feature_id for item in self.activations)
        if len(feature_ids) != len(set(feature_ids)):
            raise ValueError("compiler profile contains duplicate feature activations")
        if len(self.delivery_policy_ids) != len(set(self.delivery_policy_ids)):
            raise ValueError("compiler profile contains duplicate delivery policies")
        has_treatment = any(item.mode == TREATMENT for item in self.activations)
        if has_treatment and not self.delivery_policy_ids:
            raise ValueError("treatment profile requires delivery policy IDs")
        if not has_treatment and self.delivery_policy_ids:
            raise ValueError(
                "a profile without treatment cannot select delivery policies"
            )


@dataclass(frozen=True)
class ActivationPlan:
    """Canonical pass/certification plan derived once per profile."""

    profile_id: str
    feature_modes: tuple[tuple[str, str], ...]
    pass_feature_ids: tuple[str, ...]
    certification_feature_ids: tuple[str, ...]
    plan_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        mode_by_feature = dict(self.feature_modes)
        if len(mode_by_feature) != len(self.feature_modes):
            raise ValueError("activation plan contains duplicate feature modes")
        if self.feature_modes != tuple(sorted(self.feature_modes)):
            raise ValueError("activation plan feature modes must be canonical")
        if any(mode not in FEATURE_MODES for mode in mode_by_feature.values()):
            raise ValueError("activation plan contains an unsupported feature mode")
        expected_pass = tuple(
            feature_id
            for feature_id, mode in self.feature_modes
            if mode in {AUDIT, TREATMENT}
        )
        if self.pass_feature_ids != expected_pass:
            raise ValueError("pass feature IDs do not match activation modes")
        if self.certification_feature_ids != expected_pass:
            raise ValueError(
                "certification feature IDs must equal the active pass set"
            )
        object.__setattr__(self, "plan_sha256", _plan_sha256(self.to_dict()))

    @property
    def compiler_enabled(self) -> bool:
        return bool(self.pass_feature_ids)

    def mode_for(self, feature_id: str) -> str:
        try:
            return dict(self.feature_modes)[feature_id]
        except KeyError as exc:
            message = f"feature {feature_id!r} is absent from activation plan"
            raise KeyError(message) from exc

    def to_dict(self) -> dict[str, object]:
        return {
            "profile_id": self.profile_id,
            "feature_modes": [
                {"feature_id": feature_id, "mode": mode}
                for feature_id, mode in self.feature_modes
            ],
            "pass_feature_ids": list(self.pass_feature_ids),
            "certification_feature_ids": list(self.certification_feature_ids),
        }


def build_activation_plan(
    profile: CompilerProfile,
    catalog: FeatureCatalog,
) -> ActivationPlan:
    """Resolve one profile atomically; no pass accepts a separate user switch."""

    declared = {item.feature_id: item.mode for item in profile.activations}
    unknown = sorted(set(declared) - set(catalog.feature_ids))
    if unknown:
        raise ValueError(
            "compiler profile selects unknown features: " + ", ".join(unknown)
        )
    feature_modes = tuple(
        (feature_id, declared.get(feature_id, OFF))
        for feature_id in catalog.feature_ids
    )
    pass_feature_ids = tuple(
        feature_id
        for feature_id, mode in feature_modes
        if mode in {AUDIT, TREATMENT}
    )
    return ActivationPlan(
        profile_id=profile.profile_id,
        feature_modes=feature_modes,
        pass_feature_ids=pass_feature_ids,
        certification_feature_ids=pass_feature_ids,
    )


def _plan_sha256(value: dict[str, object]) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
