"""Deterministic candidate certification binding and exposure admission."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from core.easycrypt.proof_state_compiler.contracts.action_surface import (
    ActionSurface,
    BindingReference,
    NeutralDiagnostic,
    ResourceReference,
    VerifiedAction,
)
from core.easycrypt.proof_state_compiler.contracts.candidate_surface import (
    ActionCandidate,
    BindingReferenceCandidate,
    CandidateSurface,
    DiagnosticCandidate,
    ResourceReferenceCandidate,
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
from core.easycrypt.proof_state_compiler.contracts.state_ref import (
    ProvenanceRef,
    StateRef,
)
from core.easycrypt.proof_state_compiler.contracts.strategy import COMMITMENT_RELATIVE
from core.easycrypt.proof_state_compiler.contracts.digest import json_sha256
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


CandidateKind = Literal["action", "binding", "diagnostic", "resource"]
SurfaceCandidate = (
    ResourceReferenceCandidate
    | BindingReferenceCandidate
    | ActionCandidate
    | DiagnosticCandidate
)
SurfaceItem = ResourceReference | BindingReference | VerifiedAction | NeutralDiagnostic


@dataclass(frozen=True)
class _Admitted:
    """One admitted surface item and the policy whose budget it consumes."""

    item: SurfaceItem
    policy_id: str


def admit_action_surface(
    candidates: CandidateSurface,
    certifications: tuple[CertificationResult, ...],
    manifest: AdmissionManifest,
    *,
    triggers: tuple[CompilerTrigger, ...],
    previously_presented: frozenset[str] = frozenset(),
) -> AdmissionResult:
    """Admit candidates in a fixed order, each judged against those before it.

    A candidate is admitted only when the surface with it added renders
    within every budget; a rejected candidate leaves no trace on the surface.
    """

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
    plan = manifest.delivery_plan
    feature_order = {
        feature_id: index
        for index, feature_id in enumerate(manifest.admitted_feature_ids)
    }
    provenance = derived_provenance(
        "p4.action_surface", candidates.state_ref, candidates.provenance
    )
    decisions: list[AdmissionDecision] = []
    admitted: list[_Admitted] = []
    presented_delivery_ids: list[str] = []

    for candidate in sorted(_candidates(candidates), key=lambda item: (
        feature_order.get(item.feature_id, len(feature_order)),
        _kind_of(item),
        item.candidate_id,
    )):
        kind = _kind_of(candidate)
        dependencies = _delivery_dependencies(candidate)
        reason = _eligibility_rejection(
            candidate, dependencies, feature_order, manifest,
        )
        binding = None if reason else _delivery_binding_for(
            candidate,
            refresh=refreshes[0],
            trigger_by_id=trigger_by_id,
            plan=plan,
        )
        if binding is None:
            decisions.append(AdmissionDecision(
                candidate_id=candidate.candidate_id,
                feature_id=candidate.feature_id,
                admitted=False,
                reason=reason or "delivery_trigger_not_admitted",
            ))
            continue
        trigger, policy = binding
        certification = (
            certified.get(candidate.candidate_id)
            if isinstance(candidate, ActionCandidate) else None
        )
        delivery = _delivery_presentation(
            candidate, kind, certification, trigger, policy,
        )
        reason = _budget_rejection(
            delivery,
            policy,
            admitted,
            plan,
            presented=previously_presented.union(presented_delivery_ids),
        )
        item = None if reason else _surface_item(
            candidate, delivery, certification, candidates.state_ref,
        )
        if reason or item is None:
            decisions.append(_policy_rejection(
                candidate,
                policy,
                reason or CERTIFICATION_MISSING_OR_REJECTED,
                trigger_id=trigger.trigger_id,
            ))
            continue
        try:
            candidate_presentation = render_action_surface(
                _surface(candidates.state_ref, provenance, (item,))
            )
            surface_presentation = render_action_surface(_surface(
                candidates.state_ref,
                provenance,
                (*(entry.item for entry in admitted), item),
            ))
        except PresentationContractError:
            decisions.append(_policy_rejection(
                candidate,
                policy,
                PRESENTATION_CONTRACT_INVALID,
                trigger_id=trigger.trigger_id,
            ))
            continue
        byte_accounting = {
            "candidate_markdown_bytes": candidate_presentation.utf8_bytes,
            "effective_max_markdown_bytes": plan.candidate_max_markdown_bytes(
                candidate.feature_id,
                dependencies,
            ),
            "surface_markdown_bytes": surface_presentation.utf8_bytes,
            "surface_max_markdown_bytes": plan.aggregate_max_markdown_bytes,
        }
        reason = _markdown_rejection(**byte_accounting)
        if reason:
            decisions.append(_policy_rejection(
                candidate,
                policy,
                reason,
                trigger_id=trigger.trigger_id,
                **byte_accounting,
            ))
            continue
        admitted.append(_Admitted(item, policy.policy_id))
        presented_delivery_ids.append(delivery.presentation_id)
        decisions.append(AdmissionDecision(
            candidate_id=candidate.candidate_id,
            feature_id=candidate.feature_id,
            admitted=True,
            reason="admitted",
            trigger_id=trigger.trigger_id,
            delivery_id=delivery.presentation_id,
            policy_id=policy.policy_id,
            **byte_accounting,
        ))

    surface = _surface(
        candidates.state_ref,
        provenance,
        tuple(entry.item for entry in admitted),
    )
    presentation = render_action_surface(surface)
    return AdmissionResult(
        action_surface=surface,
        decisions=tuple(decisions),
        presentation=presentation,
        presented_delivery_ids=tuple(presented_delivery_ids),
    )


def _candidates(candidates: CandidateSurface) -> tuple[SurfaceCandidate, ...]:
    return (
        *candidates.resource_references,
        *candidates.binding_references,
        *candidates.actions,
        *candidates.diagnostics,
    )


def _kind_of(candidate: SurfaceCandidate) -> CandidateKind:
    if isinstance(candidate, ActionCandidate):
        return "action"
    if isinstance(candidate, DiagnosticCandidate):
        return "diagnostic"
    if isinstance(candidate, BindingReferenceCandidate):
        return "binding"
    return "resource"


def _delivery_dependencies(candidate: SurfaceCandidate) -> tuple[str, ...]:
    if isinstance(candidate, (ActionCandidate, DiagnosticCandidate)):
        return candidate.delivery_dependency_feature_ids
    return ()


def _eligibility_rejection(
    candidate: SurfaceCandidate,
    dependencies: tuple[str, ...],
    feature_order: dict[str, int],
    manifest: AdmissionManifest,
) -> str:
    """The manifest-level reason this candidate cannot be delivered, if any."""

    if candidate.feature_id not in feature_order:
        return "feature_not_admitted"
    if not set(dependencies).issubset(feature_order):
        return "delivery_dependency_not_admitted"
    if (
        candidate.strategy_contract.strategy_class
        not in manifest.admitted_strategy_classes
    ):
        return "strategy_class_not_admitted"
    return ""


def _delivery_binding_for(
    candidate: SurfaceCandidate,
    *,
    refresh: CompilerTrigger,
    trigger_by_id: dict[str, CompilerTrigger],
    plan: ResolvedDeliveryPlan,
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
    policy = plan.policy_for_feature(candidate.feature_id)
    if (
        policy is None
        or policy.rule.strategy_class
        != candidate.strategy_contract.strategy_class
        or policy.rule.trigger_kind != trigger.trigger_kind
    ):
        return None
    return trigger, policy


def _budget_rejection(
    delivery: DeliveryPresentation,
    policy: DeliveryPolicyDefinition,
    admitted: list[_Admitted],
    plan: ResolvedDeliveryPlan,
    *,
    presented: frozenset[str],
) -> str:
    """The lifetime or cardinality reason this delivery cannot be added."""

    if delivery.presentation_id in presented:
        return DELIVERY_LIFETIME_SUPPRESSED
    if sum(
        entry.policy_id == policy.policy_id for entry in admitted
    ) >= policy.max_items:
        return CARDINALITY_BUDGET_EXHAUSTED
    if len(admitted) >= plan.aggregate_max_items:
        return SURFACE_CARDINALITY_BUDGET_EXHAUSTED
    return ""


def _markdown_rejection(
    *,
    candidate_markdown_bytes: int,
    effective_max_markdown_bytes: int,
    surface_markdown_bytes: int,
    surface_max_markdown_bytes: int,
) -> str:
    if candidate_markdown_bytes > effective_max_markdown_bytes:
        return MARKDOWN_BYTE_BUDGET_EXCEEDED
    if surface_markdown_bytes > surface_max_markdown_bytes:
        return SURFACE_MARKDOWN_BYTE_BUDGET_EXCEEDED
    return ""


def _surface_item(
    candidate: SurfaceCandidate,
    delivery: DeliveryPresentation,
    certification: CertificationResult | None,
    state_ref: StateRef,
) -> SurfaceItem | None:
    """The admitted form of ``candidate``; ``None`` when an action is uncertified."""

    evidence_ids = tuple(item.evidence_id for item in candidate.evidence_refs)
    if isinstance(candidate, ActionCandidate):
        if certification is None or not _certification_matches(
            state_ref, candidate, certification,
        ):
            return None
        return VerifiedAction(
            feature_id=candidate.feature_id,
            intent=candidate.intent,
            payload=candidate.payload,
            unresolved_premises=candidate.unresolved_premises,
            verification_ref=certification.verification_ref,
            checked_effect=certification.checked_effect,
            strategy_contract=candidate.strategy_contract,
            delivery=delivery,
            evidence_ids=evidence_ids,
            recovery_witness_id=candidate.recovery_witness_id,
            correction=candidate.correction,
        )
    if isinstance(candidate, DiagnosticCandidate):
        return NeutralDiagnostic(
            feature_id=candidate.feature_id,
            diagnostic=candidate.diagnostic,
            strategy_contract=candidate.strategy_contract,
            delivery=delivery,
            evidence_ids=evidence_ids,
        )
    if isinstance(candidate, BindingReferenceCandidate):
        return BindingReference(
            feature_id=candidate.feature_id,
            resource_id=candidate.resource_id,
            resolved=candidate.resolved,
            unresolved=candidate.unresolved,
            strategy_contract=candidate.strategy_contract,
            delivery=delivery,
            evidence_ids=evidence_ids,
        )
    return ResourceReference(
        feature_id=candidate.feature_id,
        resource_id=candidate.resource_id,
        label=candidate.label,
        strategy_contract=candidate.strategy_contract,
        delivery=delivery,
        evidence_ids=evidence_ids,
    )


def _surface(
    state_ref: StateRef,
    provenance: ProvenanceRef,
    items: tuple[SurfaceItem, ...],
) -> ActionSurface:
    return ActionSurface(
        state_ref=state_ref,
        provenance=provenance,
        resource_references=tuple(
            item for item in items if isinstance(item, ResourceReference)
        ),
        binding_references=tuple(
            item for item in items if isinstance(item, BindingReference)
        ),
        actions=tuple(item for item in items if isinstance(item, VerifiedAction)),
        diagnostics=tuple(
            item for item in items if isinstance(item, NeutralDiagnostic)
        ),
    )


def _delivery_presentation(
    candidate: SurfaceCandidate,
    kind: CandidateKind,
    certification: CertificationResult | None,
    trigger: CompilerTrigger,
    policy: DeliveryPolicyDefinition,
) -> DeliveryPresentation:
    rule = policy.rule
    recovery_scope = (
        candidate.recovery_lifetime_scope_id
        if isinstance(candidate, DiagnosticCandidate)
        else ""
    )
    material_state = {
        "goal_identity": trigger.state_ref.goal_identity,
        "goal_identity_required": trigger.state_ref.goal_identity_required,
        "committed_prefix_identity": (
            trigger.state_ref.committed_prefix_identity
        ),
    }
    if recovery_scope:
        content: dict[str, object] = {
            "material_state": material_state,
            "kind": kind,
            "feature_id": candidate.feature_id,
            "strategy_class": candidate.strategy_contract.strategy_class,
            "presentation_kind": rule.presentation_kind,
            "policy_id": policy.policy_id,
            "recovery_lifetime_scope_id": recovery_scope,
        }
    else:
        content = {
            "material_state": material_state,
            "kind": kind,
            "candidate_id": candidate.candidate_id,
            "feature_id": candidate.feature_id,
            "delivery_dependency_feature_ids": list(
                _delivery_dependencies(candidate)
            ),
            "strategy_class": candidate.strategy_contract.strategy_class,
            "presentation_kind": rule.presentation_kind,
            "policy_id": policy.policy_id,
            "content": _candidate_content(candidate),
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
    return DeliveryPresentation(
        presentation_id=json_sha256(content),
        presentation_kind=rule.presentation_kind,
        lifetime=rule.lifetime,
        trigger_kind=trigger.trigger_kind,
        strategy_class=candidate.strategy_contract.strategy_class,
        policy_id=policy.policy_id,
        route_choice=candidate.strategy_contract.introduced_choice,
    )


def _candidate_content(candidate: SurfaceCandidate) -> dict[str, object]:
    if isinstance(candidate, ResourceReferenceCandidate):
        return {"resource_id": candidate.resource_id, "label": candidate.label}
    if isinstance(candidate, BindingReferenceCandidate):
        return {
            "resource_id": candidate.resource_id,
            "resolved": candidate.resolved.to_dict(),
            "unresolved": list(candidate.unresolved),
        }
    if isinstance(candidate, DiagnosticCandidate):
        return candidate.diagnostic.identity_payload()
    return {
        "intent": candidate.intent,
        "payload": candidate.payload.to_dict(),
        "unresolved_premises": list(candidate.unresolved_premises),
    }


def _certification_matches(
    state_ref: StateRef,
    candidate: ActionCandidate,
    result: CertificationResult,
) -> bool:
    return bool(
        result.candidate_id == candidate.candidate_id
        and result.state_ref == state_ref
        and result.policy == candidate.certification_policy
        and result.intent == candidate.intent
        and result.payload_sha256 == frozen_json_sha256(candidate.payload)
        and result.accepted
    )


def _policy_rejection(
    candidate: SurfaceCandidate,
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
