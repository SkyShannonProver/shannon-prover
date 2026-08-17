"""Deterministic candidate certification binding and exposure admission."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from core.easycrypt.proof_state_compiler.contracts.action_surface import (
    ActionSurface,
    BindingReference,
    NeutralDiagnostic,
    ResourceReference,
    VerifiedAction,
)
from core.easycrypt.proof_state_compiler.contracts.candidate_surface import (
    CandidateSurface,
)
from core.easycrypt.proof_state_compiler.contracts.certification import (
    CertificationResult,
)
from core.easycrypt.proof_state_compiler.contracts.delivery import (
    ONCE_PER_CONTENT,
    STATE_REFRESH,
    CompilerTrigger,
    DeliveryPresentation,
)
from core.easycrypt.proof_state_compiler.contracts.delivery_policy import (
    CARDINALITY_BUDGET_EXHAUSTED,
    CERTIFICATION_MISSING_OR_REJECTED,
    DELIVERY_LIFETIME_SUPPRESSED,
    MARKDOWN_BYTE_BUDGET_EXCEEDED,
    PRESENTATION_CONTRACT_INVALID,
    DeliveryPolicyDefinition,
    ResolvedDeliveryPlan,
    SURFACE_CARDINALITY_BUDGET_EXHAUSTED,
    SURFACE_MARKDOWN_BYTE_BUDGET_EXCEEDED,
)
from core.easycrypt.proof_state_compiler.contracts.frozen_json import (
    frozen_json_sha256,
)
from core.easycrypt.proof_state_compiler.backend.presentation import (
    PresentationContractError,
    RenderedCompilerMarkdown,
    render_action_surface,
)
from core.easycrypt.proof_state_compiler.contracts.strategy import COMMITMENT_RELATIVE
from core.easycrypt.proof_state_compiler.derived_provenance import derived_provenance


@dataclass(frozen=True)
class AdmissionManifest:
    manifest_id: str
    certification_feature_ids: tuple[str, ...]
    admitted_feature_ids: tuple[str, ...]
    delivery_plan: ResolvedDeliveryPlan

    def __post_init__(self) -> None:
        if not self.manifest_id:
            raise ValueError("admission manifest requires an ID")
        if len(self.admitted_feature_ids) != len(set(self.admitted_feature_ids)):
            raise ValueError("admission manifest contains duplicate feature IDs")
        if len(self.certification_feature_ids) != len(
            set(self.certification_feature_ids)
        ):
            raise ValueError("manifest contains duplicate certification feature IDs")
        if any(
            not feature_id
            for feature_id in (
                self.certification_feature_ids + self.admitted_feature_ids
            )
        ):
            raise ValueError("admission manifest contains an empty feature ID")
        if not set(self.admitted_feature_ids).issubset(
            self.certification_feature_ids
        ):
            raise ValueError("admitted action features must be certification-eligible")
        if not isinstance(self.delivery_plan, ResolvedDeliveryPlan):
            raise TypeError("admission manifest requires a resolved delivery plan")
        if self.delivery_plan.profile_id != self.manifest_id:
            raise ValueError("delivery plan identity diverges from manifest")
        if self.delivery_plan.admitted_feature_ids != tuple(sorted(
            self.admitted_feature_ids
        )):
            raise ValueError("delivery plan feature bindings diverge from manifest")

    @property
    def admitted_strategy_classes(self) -> tuple[str, ...]:
        return self.delivery_plan.admitted_strategy_classes

@dataclass(frozen=True)
class AdmissionDecision:
    candidate_id: str
    feature_id: str
    admitted: bool
    reason: str
    trigger_id: str = ""
    delivery_id: str = ""
    policy_id: str = ""
    candidate_markdown_bytes: int = 0
    effective_max_markdown_bytes: int = 0
    surface_markdown_bytes: int = 0
    surface_max_markdown_bytes: int = 0

    def __post_init__(self) -> None:
        if not self.candidate_id or not self.feature_id or not self.reason:
            raise ValueError("admission decision is incomplete")
        if self.admitted and (not self.trigger_id or not self.delivery_id):
            raise ValueError(
                "admitted decision requires resolved trigger and delivery identity"
            )
        if not self.admitted and self.delivery_id:
            raise ValueError("rejected decision cannot claim a delivery identity")
        if any(
            type(value) is not int or value < 0
            for value in (
                self.candidate_markdown_bytes,
                self.effective_max_markdown_bytes,
                self.surface_markdown_bytes,
                self.surface_max_markdown_bytes,
            )
        ):
            raise ValueError("admission decision byte accounting is invalid")
        if self.admitted and not (
            0
            < self.candidate_markdown_bytes
            <= self.effective_max_markdown_bytes
            and 0
            < self.surface_markdown_bytes
            <= self.surface_max_markdown_bytes
        ):
            raise ValueError(
                "admitted decision requires complete bounded byte accounting"
            )


@dataclass(frozen=True)
class AdmissionResult:
    action_surface: ActionSurface
    decisions: tuple[AdmissionDecision, ...]
    presentation: RenderedCompilerMarkdown
    presented_delivery_ids: tuple[str, ...]

    @property
    def markdown_bytes(self) -> int:
        return self.presentation.utf8_bytes


def admit_action_surface(
    candidates: CandidateSurface,
    certifications: tuple[CertificationResult, ...],
    manifest: AdmissionManifest,
    *,
    triggers: tuple[CompilerTrigger, ...],
    previously_presented: frozenset[str] = frozenset(),
) -> AdmissionResult:
    if not triggers:
        raise ValueError("delivery requires at least one trigger")
    if any(trigger.state_ref != candidates.state_ref for trigger in triggers):
        raise ValueError("delivery trigger does not match candidate StateRef")
    trigger_by_id = {trigger.trigger_id: trigger for trigger in triggers}
    if len(trigger_by_id) != len(triggers):
        raise ValueError("delivery triggers contain duplicate IDs")
    refreshes = tuple(
        trigger for trigger in triggers if trigger.trigger_kind == STATE_REFRESH
    )
    if len(refreshes) != 1:
        raise ValueError("delivery requires exactly one state-refresh trigger")
    certified = {item.candidate_id: item for item in certifications}
    if len(certified) != len(certifications):
        raise ValueError("certification results contain duplicate candidate IDs")
    decisions: list[AdmissionDecision] = []
    resources: list[ResourceReference] = []
    bindings: list[BindingReference] = []
    actions: list[VerifiedAction] = []
    diagnostics: list[NeutralDiagnostic] = []
    presented_delivery_ids: list[str] = []
    resource_policy_ids: list[str] = []
    binding_policy_ids: list[str] = []
    action_policy_ids: list[str] = []
    diagnostic_policy_ids: list[str] = []

    ordered = [
        *(('resource', item) for item in candidates.resource_references),
        *(('binding', item) for item in candidates.binding_references),
        *(('action', item) for item in candidates.actions),
        *(('diagnostic', item) for item in candidates.diagnostics),
    ]
    feature_order = {
        feature_id: index
        for index, feature_id in enumerate(manifest.admitted_feature_ids)
    }
    ordered.sort(key=lambda pair: (
        feature_order.get(pair[1].feature_id, len(feature_order)),
        pair[0],
        pair[1].candidate_id,
    ))

    def current_surface() -> ActionSurface:
        return ActionSurface(
            state_ref=candidates.state_ref,
            provenance=derived_provenance(
                "p4.action_surface", candidates.state_ref, candidates.provenance
            ),
            resource_references=tuple(resources),
            binding_references=tuple(bindings),
            actions=tuple(actions),
            diagnostics=tuple(diagnostics),
        )

    for kind, candidate in ordered:
        if candidate.feature_id not in feature_order:
            decisions.append(AdmissionDecision(
                candidate_id=candidate.candidate_id,
                feature_id=candidate.feature_id,
                admitted=False,
                reason="feature_not_admitted",
            ))
            continue
        delivery_dependencies = getattr(
            candidate, "delivery_dependency_feature_ids", ()
        )
        if not set(delivery_dependencies).issubset(feature_order):
            decisions.append(AdmissionDecision(
                candidate_id=candidate.candidate_id,
                feature_id=candidate.feature_id,
                admitted=False,
                reason="delivery_dependency_not_admitted",
            ))
            continue
        if (
            candidate.strategy_contract.strategy_class
            not in manifest.admitted_strategy_classes
        ):
            decisions.append(AdmissionDecision(
                candidate_id=candidate.candidate_id,
                feature_id=candidate.feature_id,
                admitted=False,
                reason="strategy_class_not_admitted",
            ))
            continue
        binding = _delivery_binding_for(
            candidate,
            refresh=refreshes[0],
            trigger_by_id=trigger_by_id,
            manifest=manifest,
        )
        if binding is None:
            decisions.append(AdmissionDecision(
                candidate_id=candidate.candidate_id,
                feature_id=candidate.feature_id,
                admitted=False,
                reason="delivery_trigger_not_admitted",
            ))
            continue
        trigger, policy = binding
        rule = policy.rule
        certification = (
            certified.get(candidate.candidate_id) if kind == "action" else None
        )
        delivery = _delivery_presentation(
            kind,
            candidate,
            certification,
            trigger,
            policy,
        )
        if (
            delivery.presentation_id in previously_presented
            or delivery.presentation_id in presented_delivery_ids
        ):
            decisions.append(_policy_rejection(
                candidate,
                policy,
                DELIVERY_LIFETIME_SUPPRESSED,
                trigger_id=trigger.trigger_id,
            ))
            continue
        if _policy_item_count(
            policy.policy_id,
            resource_policy_ids,
            binding_policy_ids,
            action_policy_ids,
            diagnostic_policy_ids,
        ) >= policy.max_items:
            decisions.append(_policy_rejection(
                candidate,
                policy,
                CARDINALITY_BUDGET_EXHAUSTED,
                trigger_id=trigger.trigger_id,
            ))
            continue
        if _surface_item_count(resources, bindings, actions, diagnostics) >= (
            manifest.delivery_plan.aggregate_max_items
        ):
            decisions.append(_policy_rejection(
                candidate,
                policy,
                SURFACE_CARDINALITY_BUDGET_EXHAUSTED,
                trigger_id=trigger.trigger_id,
            ))
            continue

        if kind == "resource":
            value = ResourceReference(
                feature_id=candidate.feature_id,
                resource_id=candidate.resource_id,
                label=candidate.label,
                strategy_contract=candidate.strategy_contract,
                delivery=delivery,
                evidence_ids=_evidence_ids(candidate),
            )
            resources.append(value)
            resource_policy_ids.append(policy.policy_id)
        elif kind == "binding":
            value = BindingReference(
                feature_id=candidate.feature_id,
                resource_id=candidate.resource_id,
                resolved=candidate.resolved,
                unresolved=candidate.unresolved,
                strategy_contract=candidate.strategy_contract,
                delivery=delivery,
                evidence_ids=_evidence_ids(candidate),
            )
            bindings.append(value)
            binding_policy_ids.append(policy.policy_id)
        elif kind == "diagnostic":
            value = NeutralDiagnostic(
                feature_id=candidate.feature_id,
                diagnostic=candidate.diagnostic,
                strategy_contract=candidate.strategy_contract,
                delivery=delivery,
                evidence_ids=_evidence_ids(candidate),
            )
            diagnostics.append(value)
            diagnostic_policy_ids.append(policy.policy_id)
        else:
            if not _certification_matches(candidates, candidate, certification):
                decisions.append(_policy_rejection(
                    candidate,
                    policy,
                    CERTIFICATION_MISSING_OR_REJECTED,
                    trigger_id=trigger.trigger_id,
                ))
                continue
            actions.append(VerifiedAction(
                feature_id=candidate.feature_id,
                intent=candidate.intent,
                payload=candidate.payload,
                unresolved_premises=candidate.unresolved_premises,
                verification_ref=certification.verification_ref,
                checked_effect=certification.checked_effect,
                strategy_contract=candidate.strategy_contract,
                delivery=delivery,
                evidence_ids=_evidence_ids(candidate),
                recovery_witness_id=candidate.recovery_witness_id,
                correction=candidate.correction,
            ))
            action_policy_ids.append(policy.policy_id)

        try:
            candidate_presentation = render_action_surface(
                _last_item_surface(current_surface(), kind)
            )
            surface_presentation = render_action_surface(current_surface())
        except PresentationContractError:
            _pop_last(kind, resources, bindings, actions, diagnostics)
            _pop_last(
                kind,
                resource_policy_ids,
                binding_policy_ids,
                action_policy_ids,
                diagnostic_policy_ids,
            )
            decisions.append(_policy_rejection(
                candidate,
                policy,
                PRESENTATION_CONTRACT_INVALID,
                trigger_id=trigger.trigger_id,
            ))
            continue
        candidate_markdown_bytes = candidate_presentation.utf8_bytes
        surface_markdown_bytes = surface_presentation.utf8_bytes
        effective_max_markdown_bytes = (
            manifest.delivery_plan.candidate_max_markdown_bytes(
                candidate.feature_id,
                delivery_dependencies,
            )
        )
        if candidate_markdown_bytes > effective_max_markdown_bytes:
            _pop_last(kind, resources, bindings, actions, diagnostics)
            _pop_last(
                kind,
                resource_policy_ids,
                binding_policy_ids,
                action_policy_ids,
                diagnostic_policy_ids,
            )
            decisions.append(_policy_rejection(
                candidate,
                policy,
                MARKDOWN_BYTE_BUDGET_EXCEEDED,
                trigger_id=trigger.trigger_id,
                candidate_markdown_bytes=candidate_markdown_bytes,
                effective_max_markdown_bytes=effective_max_markdown_bytes,
                surface_markdown_bytes=surface_markdown_bytes,
                surface_max_markdown_bytes=(
                    manifest.delivery_plan.aggregate_max_markdown_bytes
                ),
            ))
            continue
        if surface_markdown_bytes > (
            manifest.delivery_plan.aggregate_max_markdown_bytes
        ):
            _pop_last(kind, resources, bindings, actions, diagnostics)
            _pop_last(
                kind,
                resource_policy_ids,
                binding_policy_ids,
                action_policy_ids,
                diagnostic_policy_ids,
            )
            decisions.append(_policy_rejection(
                candidate,
                policy,
                SURFACE_MARKDOWN_BYTE_BUDGET_EXCEEDED,
                trigger_id=trigger.trigger_id,
                candidate_markdown_bytes=candidate_markdown_bytes,
                effective_max_markdown_bytes=effective_max_markdown_bytes,
                surface_markdown_bytes=surface_markdown_bytes,
                surface_max_markdown_bytes=(
                    manifest.delivery_plan.aggregate_max_markdown_bytes
                ),
            ))
            continue
        presented_delivery_ids.append(delivery.presentation_id)
        decisions.append(AdmissionDecision(
            candidate_id=candidate.candidate_id,
            feature_id=candidate.feature_id,
            admitted=True,
            reason="admitted",
            trigger_id=trigger.trigger_id,
            delivery_id=delivery.presentation_id,
            policy_id=policy.policy_id,
            candidate_markdown_bytes=candidate_markdown_bytes,
            effective_max_markdown_bytes=effective_max_markdown_bytes,
            surface_markdown_bytes=surface_markdown_bytes,
            surface_max_markdown_bytes=(
                manifest.delivery_plan.aggregate_max_markdown_bytes
            ),
        ))

    surface = current_surface()
    presentation = render_action_surface(surface)
    return AdmissionResult(
        action_surface=surface,
        decisions=tuple(decisions),
        presentation=presentation,
        presented_delivery_ids=tuple(presented_delivery_ids),
    )


def _delivery_binding_for(
    candidate,
    *,
    refresh: CompilerTrigger,
    trigger_by_id: dict[str, CompilerTrigger],
    manifest: AdmissionManifest,
) -> tuple[CompilerTrigger, DeliveryPolicyDefinition] | None:
    if candidate.strategy_contract.strategy_class == COMMITMENT_RELATIVE:
        if not candidate.trigger_id:
            return None
        trigger = trigger_by_id.get(candidate.trigger_id)
        if trigger is None or trigger.trigger_kind == STATE_REFRESH:
            return None
    else:
        if candidate.trigger_id:
            return None
        trigger = refresh
    policy = manifest.delivery_plan.policy_for_feature(candidate.feature_id)
    if (
        policy is None
        or policy.rule.strategy_class
        != candidate.strategy_contract.strategy_class
        or policy.rule.trigger_kind != trigger.trigger_kind
    ):
        return None
    return trigger, policy


def _delivery_presentation(
    kind: str,
    candidate,
    certification,
    trigger: CompilerTrigger,
    policy: DeliveryPolicyDefinition,
) -> DeliveryPresentation:
    rule = policy.rule
    recovery_scope = (
        candidate.recovery_lifetime_scope_id
        if kind == "diagnostic"
        else ""
    )
    if recovery_scope:
        content = {
            "material_state": {
                "goal_identity": trigger.state_ref.goal_identity,
                "goal_identity_required": (
                    trigger.state_ref.goal_identity_required
                ),
                "committed_prefix_identity": (
                    trigger.state_ref.committed_prefix_identity
                ),
            },
            "kind": kind,
            "feature_id": candidate.feature_id,
            "strategy_class": candidate.strategy_contract.strategy_class,
            "presentation_kind": rule.presentation_kind,
            "policy_id": policy.policy_id,
            "recovery_lifetime_scope_id": recovery_scope,
        }
    else:
        content = {
            "material_state": {
                "goal_identity": trigger.state_ref.goal_identity,
                "goal_identity_required": trigger.state_ref.goal_identity_required,
                "committed_prefix_identity": (
                    trigger.state_ref.committed_prefix_identity
                ),
            },
            "kind": kind,
            "candidate_id": candidate.candidate_id,
            "feature_id": candidate.feature_id,
            "delivery_dependency_feature_ids": list(getattr(
                candidate, "delivery_dependency_feature_ids", ()
            )),
            "strategy_class": candidate.strategy_contract.strategy_class,
            "presentation_kind": rule.presentation_kind,
            "policy_id": policy.policy_id,
            "content": _candidate_content(kind, candidate),
            "checked_effect": (
                certification.checked_effect.to_dict()
                if certification is not None else {}
            ),
        }
    if rule.lifetime != ONCE_PER_CONTENT and not recovery_scope:
        content["trigger_id"] = trigger.trigger_id
        content["commitment_anchor_id"] = (
            trigger.commitment_anchor.anchor_id
            if trigger.commitment_anchor is not None else ""
        )
    encoded = json.dumps(
        content,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return DeliveryPresentation(
        presentation_id=hashlib.sha256(encoded).hexdigest(),
        presentation_kind=rule.presentation_kind,
        lifetime=rule.lifetime,
        trigger_kind=trigger.trigger_kind,
        strategy_class=candidate.strategy_contract.strategy_class,
        policy_id=policy.policy_id,
        route_choice=candidate.strategy_contract.introduced_choice,
    )


def _candidate_content(kind: str, candidate) -> dict[str, object]:
    if kind == "resource":
        return {"resource_id": candidate.resource_id, "label": candidate.label}
    if kind == "binding":
        return {
            "resource_id": candidate.resource_id,
            "resolved": candidate.resolved.to_dict(),
            "unresolved": list(candidate.unresolved),
        }
    if kind == "diagnostic":
        return candidate.diagnostic.identity_payload()
    return {
        "intent": candidate.intent,
        "payload": candidate.payload.to_dict(),
        "unresolved_premises": list(candidate.unresolved_premises),
    }


def _certification_matches(candidates, candidate, result) -> bool:
    return bool(
        result is not None
        and result.candidate_id == candidate.candidate_id
        and result.state_ref == candidates.state_ref
        and result.policy == candidate.certification_policy
        and result.intent == candidate.intent
        and result.payload_sha256 == frozen_json_sha256(candidate.payload)
        and result.accepted
    )


def _evidence_ids(candidate: object) -> tuple[str, ...]:
    return tuple(item.evidence_id for item in candidate.evidence_refs)


def _policy_item_count(policy_id: str, *collections: list[str]) -> int:
    return sum(item == policy_id for collection in collections for item in collection)


def _surface_item_count(*collections: list[object]) -> int:
    return sum(len(collection) for collection in collections)


def _policy_rejection(
    candidate,
    policy: DeliveryPolicyDefinition,
    reason: str,
    *,
    trigger_id: str,
    candidate_markdown_bytes: int = 0,
    effective_max_markdown_bytes: int = 0,
    surface_markdown_bytes: int = 0,
    surface_max_markdown_bytes: int = 0,
) -> AdmissionDecision:
    if not policy.permits_rejection(reason):
        raise ValueError(
            f"delivery policy {policy.policy_id!r} did not declare "
            f"rejection reason {reason!r}"
        )
    return AdmissionDecision(
        candidate_id=candidate.candidate_id,
        feature_id=candidate.feature_id,
        admitted=False,
        reason=reason,
        trigger_id=trigger_id,
        policy_id=policy.policy_id,
        candidate_markdown_bytes=candidate_markdown_bytes,
        effective_max_markdown_bytes=effective_max_markdown_bytes,
        surface_markdown_bytes=surface_markdown_bytes,
        surface_max_markdown_bytes=surface_max_markdown_bytes,
    )


def _last_item_surface(surface: ActionSurface, kind: str) -> ActionSurface:
    """Return the just-added candidate alone for standalone policy sizing."""

    return ActionSurface(
        state_ref=surface.state_ref,
        provenance=surface.provenance,
        resource_references=(
            (surface.resource_references[-1],) if kind == "resource" else ()
        ),
        binding_references=(
            (surface.binding_references[-1],) if kind == "binding" else ()
        ),
        actions=((surface.actions[-1],) if kind == "action" else ()),
        diagnostics=(
            (surface.diagnostics[-1],) if kind == "diagnostic" else ()
        ),
    )


def _pop_last(kind, resources, bindings, actions, diagnostics) -> None:
    {"resource": resources, "binding": bindings, "action": actions,
     "diagnostic": diagnostics}[kind].pop()
