"""Feature-neutral, identical-state one-step compiler experiment boundary.

This module is validation infrastructure, not a compiler pass. ``TrialPacket``
is feature-neutral. The only bundle-to-packet admission helper is named for the
frozen M05 exception so another feature cannot accidentally inherit its
state-refresh/optional-advisory semantics. Other micros must copy an already
admitted production item into the generic packet.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Literal

from core.easycrypt.proof_state_compiler import CompilationBundle, StateRef
from core.easycrypt.proof_state_compiler.backend import (
    AdmissionManifest,
    admit_action_surface,
)
from core.easycrypt.proof_state_compiler.contracts import (
    BASE_POLICY_REJECTION_REASONS,
    CERTIFICATION_MISSING_OR_REJECTED,
    CertificationResult,
    DeliveryPolicyDefinition,
    ResolvedDeliveryPlan,
    empty_delivery_plan,
    optional_advisory_rule,
    state_refresh_trigger,
)
from core.easycrypt.proof_state_compiler.contracts.frozen_json import (
    freeze_json_object,
    frozen_json_sha256,
)
from core.easycrypt.proof_state_compiler.features import FeatureDefinition
from core.easycrypt.proof_state_compiler.backend.presentation import (
    OPTIONAL_CHECKED_FACT_NOTICE,
)


TrialArm = Literal["control", "l1", "audit", "treatment"]
TRIAL_PACKET_KIND = "proof_state_compiler_one_step_trial"
TRIAL_PACKET_SCHEMA_VERSION = 1
# The micro envelope includes generic presentation copy in addition to the
# byte-budgeted ActionSurface.  Keep the full mechanical premises and measure
# their actual incremental cost instead of deleting them to meet the production
# surface's separate 700-byte admission ceiling.
DEFAULT_MAX_ASSIST_BYTES = 900


@dataclass(frozen=True)
class OneStepTrialSpec:
    trial_id: str
    feature_id: str
    evidence_ledger_ids: tuple[str, ...]
    max_assist_bytes: int = DEFAULT_MAX_ASSIST_BYTES

    def __post_init__(self) -> None:
        if not self.trial_id or not self.feature_id:
            raise ValueError("one-step trial requires trial and feature identity")
        if not self.evidence_ledger_ids:
            raise ValueError("one-step trial requires evidence provenance")
        if not 1 <= self.max_assist_bytes <= 4096:
            raise ValueError("one-step trial assist budget must be 1..4096 bytes")

    @classmethod
    def from_feature(
        cls,
        feature: FeatureDefinition,
        *,
        max_assist_bytes: int = DEFAULT_MAX_ASSIST_BYTES,
    ) -> "OneStepTrialSpec":
        gate = feature.spec.gate
        return cls(
            trial_id=gate.experiment_id,
            feature_id=feature.spec.feature_id,
            evidence_ledger_ids=gate.evidence_ledger_ids,
            max_assist_bytes=max_assist_bytes,
        )


@dataclass(frozen=True)
class ExactTacticPreflight:
    """Runtime verdict for one tactic on one exact compiler input state."""

    state_ref: StateRef
    tactic: str
    accepted: bool
    verification_ref: str

    def __post_init__(self) -> None:
        if not self.tactic or not self.verification_ref:
            raise ValueError("preflight requires tactic and verification_ref")


@dataclass(frozen=True)
class TrialPacket:
    """The entire one-step prompt payload; audit data stays elsewhere."""

    spec: OneStepTrialSpec
    arm: TrialArm
    state_ref: StateRef
    current_goal_lines: tuple[str, ...]
    manager_observation: tuple[tuple[str, str], ...] = ()
    compiler_assist: tuple[dict[str, Any], ...] = ()

    def __post_init__(self) -> None:
        if self.arm not in {"control", "l1", "audit", "treatment"}:
            raise ValueError("unsupported trial arm")
        if not self.current_goal_lines:
            raise ValueError("trial packet requires an exact current goal")
        if self.arm != "treatment" and self.compiler_assist:
            raise ValueError("non-treatment arm cannot contain compiler assistance")
        if len(self.compiler_assist) > 1:
            raise ValueError("one-step trial exposes at most one compiler item")
        if _json_size(self.compiler_assist) > self.spec.max_assist_bytes:
            raise ValueError("compiler assistance exceeds the trial byte budget")

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "schema_version": TRIAL_PACKET_SCHEMA_VERSION,
            "kind": TRIAL_PACKET_KIND,
            "trial_id": self.spec.trial_id,
            "arm": self.arm,
            "state": {
                "session_id": self.state_ref.session_id,
                "state_version": self.state_ref.state_version,
                "goal_identity": self.state_ref.goal_identity,
                "committed_prefix_identity": (
                    self.state_ref.committed_prefix_identity
                ),
            },
            "current_goal": {"lines": list(self.current_goal_lines)},
            "compiler_assist": list(self.compiler_assist),
        }
        if self.manager_observation:
            payload["last_result"] = dict(self.manager_observation)
        return payload

    @property
    def payload_bytes(self) -> int:
        return _json_size(self.to_dict())


def build_frozen_m05_trial_packet(
    bundle: CompilationBundle,
    arm: TrialArm,
    *,
    spec: OneStepTrialSpec,
    preflight: ExactTacticPreflight | None = None,
) -> TrialPacket:
    """Admit the frozen M05 candidate after exact-state verification."""

    assist: tuple[dict[str, Any], ...] = ()
    actions = tuple(
        action for action in bundle.candidate_surface.actions
        if action.feature_id == spec.feature_id
    )
    foreign_actions = tuple(
        action for action in bundle.candidate_surface.actions
        if action.feature_id != spec.feature_id
    )
    if foreign_actions:
        raise ValueError("one-step trial bundle contains an unselected feature")
    if len(actions) > 1:
        raise ValueError("one-step trial feature emitted multiple actions")

    certifications: tuple[CertificationResult, ...] = ()
    if len(actions) == 1:
        action = actions[0]
        tactic = str(action.payload.to_dict().get("tactic") or "")
        if _accepted_on_exact_state(bundle.state_ref, tactic, preflight):
            assert preflight is not None
            certifications = (CertificationResult(
                candidate_id=action.candidate_id,
                state_ref=preflight.state_ref,
                policy=action.certification_policy,
                intent=action.intent,
                payload_sha256=frozen_json_sha256(action.payload),
                accepted=True,
                verification_ref=preflight.verification_ref,
                checked_effect=freeze_json_object({"accepted": True}),
            ),)

    manifest_id = f"{spec.trial_id}:{arm}"
    policy = DeliveryPolicyDefinition(
        policy_id="frozen-m05-one-step",
        rule=optional_advisory_rule(),
        max_items=1,
        max_markdown_bytes=spec.max_assist_bytes,
        compatible_feature_ids=(spec.feature_id,),
        compatibility_contract="frozen M05 one-step validation",
        rejection_audit_reasons=BASE_POLICY_REJECTION_REASONS + (
            CERTIFICATION_MISSING_OR_REJECTED,
        ),
        frozen_research_exception=True,
    )
    delivery_plan = (
        ResolvedDeliveryPlan(
            profile_id=manifest_id,
            policies=(policy,),
            feature_policy_bindings=((spec.feature_id, policy.policy_id),),
        )
        if arm == "treatment"
        else empty_delivery_plan(manifest_id)
    )
    manifest = AdmissionManifest(
        manifest_id=manifest_id,
        certification_feature_ids=(
            (spec.feature_id,) if arm == "treatment" else ()
        ),
        admitted_feature_ids=(
            (spec.feature_id,) if arm == "treatment" else ()
        ),
        delivery_plan=delivery_plan,
    )
    admitted = admit_action_surface(
        bundle.candidate_surface,
        certifications,
        manifest,
        triggers=(state_refresh_trigger(
            bundle.state_ref,
            bundle.projected_state.provenance.source_event_id,
        ),),
    ).action_surface
    if admitted.actions:
        action = admitted.actions[0]
        assist = ({
            "exact_action": {
                "intent": action.intent,
                "payload": action.payload.to_dict(),
            },
            "unresolved_premises": list(action.unresolved_premises),
            "verification": "easycrypt_preflight_accepted",
            "delivery": {
                "kind": action.delivery.presentation_kind,
                "route_choice": action.delivery.route_choice,
                "notice": OPTIONAL_CHECKED_FACT_NOTICE,
            },
        },)

    return TrialPacket(
        spec=spec,
        arm=arm,
        state_ref=bundle.state_ref,
        current_goal_lines=bundle.projected_state.goal_lines,
        compiler_assist=assist,
    )


def trial_telemetry(
    control: TrialPacket,
    treatment: TrialPacket,
) -> dict[str, Any]:
    if control.spec != treatment.spec:
        raise ValueError("trial arms must use the same specification")
    if control.state_ref != treatment.state_ref:
        raise ValueError("trial arms must use the same StateRef")
    return {
        "trial_id": control.spec.trial_id,
        "feature_id": control.spec.feature_id,
        "state_identity": {
            "session_id": control.state_ref.session_id,
            "state_version": control.state_ref.state_version,
            "goal_identity": control.state_ref.goal_identity,
            "committed_prefix_identity": (
                control.state_ref.committed_prefix_identity
            ),
        },
        "control_bytes": control.payload_bytes,
        "treatment_bytes": treatment.payload_bytes,
        "incremental_bytes": treatment.payload_bytes - control.payload_bytes,
        "treatment_item_count": len(treatment.compiler_assist),
    }


def _accepted_on_exact_state(
    state_ref: StateRef,
    tactic: str,
    preflight: ExactTacticPreflight | None,
) -> bool:
    return bool(
        preflight is not None
        and preflight.accepted
        and preflight.state_ref == state_ref
        and preflight.tactic == tactic
    )


def _json_size(value: object) -> int:
    return len(json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8"))
