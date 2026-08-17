"""Independent delivery-policy composition contracts.

Feature activation decides which P2/P3/P4 producers run.  Delivery policy
decides whether one treatment feature may expose a candidate, under which
trigger, lifetime, and per-policy budgets.  The two plans are resolved once by
the composition root and are immutable thereafter.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

from core.easycrypt.proof_state_compiler.contracts.delivery import (
    OPTIONAL_ADVISORY,
    DeliveryRule,
)
from core.easycrypt.proof_state_compiler.contracts.strategy import (
    ROUTE_SELECTING,
)


DELIVERY_LIFETIME_SUPPRESSED = "delivery_lifetime_suppressed"
CARDINALITY_BUDGET_EXHAUSTED = "cardinality_budget_exhausted"
MARKDOWN_BYTE_BUDGET_EXCEEDED = "markdown_byte_budget_exceeded"
PRESENTATION_CONTRACT_INVALID = "presentation_contract_invalid"
SURFACE_CARDINALITY_BUDGET_EXHAUSTED = (
    "surface_cardinality_budget_exhausted"
)
SURFACE_MARKDOWN_BYTE_BUDGET_EXCEEDED = (
    "surface_markdown_byte_budget_exceeded"
)
CERTIFICATION_MISSING_OR_REJECTED = "certification_missing_or_rejected"

# Absolute turn-surface safety ceiling. Feature policies remain smaller and
# evidence-specific; this constant is not their shared presentation budget.
MAX_COMPILER_MARKDOWN_BYTES = 4_096
BASE_POLICY_REJECTION_REASONS = (
    MARKDOWN_BYTE_BUDGET_EXCEEDED,
    PRESENTATION_CONTRACT_INVALID,
    CARDINALITY_BUDGET_EXHAUSTED,
    DELIVERY_LIFETIME_SUPPRESSED,
    SURFACE_MARKDOWN_BYTE_BUDGET_EXCEEDED,
    SURFACE_CARDINALITY_BUDGET_EXHAUSTED,
)


@dataclass(frozen=True)
class DeliveryPolicyDefinition:
    """One feature's complete final-Markdown envelope and delivery rule.

    ``max_markdown_bytes`` covers the complete standalone Markdown rendering
    of a candidate owned by the compatible feature.
    ``dependency_allowance_markdown_bytes`` is added only when that feature is
    named as an authorized upstream delivery dependency of another candidate.
    """

    policy_id: str
    rule: DeliveryRule
    max_items: int
    max_markdown_bytes: int
    compatible_feature_ids: tuple[str, ...]
    compatibility_contract: str
    rejection_audit_reasons: tuple[str, ...]
    dependency_allowance_markdown_bytes: int = 0
    frozen_research_exception: bool = False

    def __post_init__(self) -> None:
        if not self.policy_id or not isinstance(self.rule, DeliveryRule):
            raise ValueError("delivery policy requires identity and rule")
        if self.max_items <= 0 or self.max_markdown_bytes <= 0:
            raise ValueError("delivery policy requires positive budgets")
        if (
            type(self.dependency_allowance_markdown_bytes) is not int
            or self.dependency_allowance_markdown_bytes < 0
            or self.max_markdown_bytes > MAX_COMPILER_MARKDOWN_BYTES
            or self.dependency_allowance_markdown_bytes
            > MAX_COMPILER_MARKDOWN_BYTES
        ):
            raise ValueError("delivery policy byte budgets are invalid")
        if self.compatible_feature_ids != tuple(sorted(set(
            self.compatible_feature_ids
        ))):
            raise ValueError("delivery policy feature compatibility is not canonical")
        if len(self.compatible_feature_ids) > 1:
            raise ValueError(
                "one numerical delivery policy may budget only one feature"
            )
        if (
            self.dependency_allowance_markdown_bytes
            and not self.compatible_feature_ids
        ):
            raise ValueError(
                "dependency allowance requires one compatible feature"
            )
        if not self.compatibility_contract or not self.rejection_audit_reasons:
            raise ValueError("delivery policy requires compatibility/audit contracts")
        if len(self.rejection_audit_reasons) != len(set(
            self.rejection_audit_reasons
        )):
            raise ValueError("delivery policy has duplicate audit reasons")
        missing_rejections = sorted(
            set(BASE_POLICY_REJECTION_REASONS)
            - set(self.rejection_audit_reasons)
        )
        if missing_rejections:
            raise ValueError(
                "delivery policy omits generic rejection contracts: "
                + ", ".join(missing_rejections)
            )
        route_selecting = self.rule.strategy_class == ROUTE_SELECTING
        if route_selecting:
            if (
                not self.frozen_research_exception
                or self.rule.presentation_kind != OPTIONAL_ADVISORY
                or len(self.compatible_feature_ids) != 1
            ):
                raise ValueError(
                    "route-selecting delivery must be one frozen feature exception"
                )
        elif self.frozen_research_exception:
            raise ValueError(
                "only a route-selecting delivery may be a frozen exception"
            )

    def permits_rejection(self, reason: str) -> bool:
        """Whether admission may emit this policy-bound audit reason."""

        return reason in self.rejection_audit_reasons


@dataclass(frozen=True)
class DeliveryPolicyCatalog:
    definitions: tuple[DeliveryPolicyDefinition, ...] = ()

    def __post_init__(self) -> None:
        policy_ids = tuple(item.policy_id for item in self.definitions)
        if policy_ids != tuple(sorted(policy_ids)):
            raise ValueError("delivery policy catalog must be sorted")
        if len(policy_ids) != len(set(policy_ids)):
            raise ValueError("delivery policy catalog contains duplicate IDs")

    @property
    def policy_ids(self) -> tuple[str, ...]:
        return tuple(item.policy_id for item in self.definitions)

    def select(
        self,
        policy_ids: tuple[str, ...],
    ) -> tuple[DeliveryPolicyDefinition, ...]:
        if len(policy_ids) != len(set(policy_ids)):
            raise ValueError("delivery policy selection contains duplicates")
        unknown = sorted(set(policy_ids) - set(self.policy_ids))
        if unknown:
            raise ValueError(
                "delivery profile selects unknown policies: " + ", ".join(unknown)
            )
        selected = set(policy_ids)
        return tuple(
            definition for definition in self.definitions
            if definition.policy_id in selected
        )


@dataclass(frozen=True)
class ResolvedDeliveryPlan:
    profile_id: str
    policies: tuple[DeliveryPolicyDefinition, ...]
    feature_policy_bindings: tuple[tuple[str, str], ...]
    aggregate_max_items: int = field(init=False)
    aggregate_max_markdown_bytes: int = field(init=False)
    plan_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if not self.profile_id:
            raise ValueError("resolved delivery plan requires a profile ID")
        policy_ids = tuple(item.policy_id for item in self.policies)
        if policy_ids != tuple(sorted(policy_ids)):
            raise ValueError("resolved delivery policies must be canonical")
        if len(policy_ids) != len(set(policy_ids)):
            raise ValueError("resolved delivery plan has duplicate policies")
        if self.feature_policy_bindings != tuple(sorted(
            self.feature_policy_bindings
        )):
            raise ValueError("delivery feature bindings must be canonical")
        feature_ids = tuple(item[0] for item in self.feature_policy_bindings)
        if len(feature_ids) != len(set(feature_ids)):
            raise ValueError("a feature has duplicate delivery ownership")
        if any(policy_id not in policy_ids for _, policy_id in (
            self.feature_policy_bindings
        )):
            raise ValueError("delivery binding references an unresolved policy")
        # Independent candidates cannot add policy budgets together.  One
        # candidate may use only the explicit allowances of the upstream
        # delivery dependencies named on that candidate, and admission checks
        # that narrower bound separately.
        object.__setattr__(
            self,
            "aggregate_max_items",
            max((item.max_items for item in self.policies), default=0),
        )
        object.__setattr__(
            self,
            "aggregate_max_markdown_bytes",
            min(
                MAX_COMPILER_MARKDOWN_BYTES,
                max(
                    (item.max_markdown_bytes for item in self.policies),
                    default=0,
                )
                + sum(
                    item.dependency_allowance_markdown_bytes
                    for item in self.policies
                ),
            ),
        )
        object.__setattr__(self, "plan_sha256", _sha256(self.to_dict()))

    @property
    def policy_ids(self) -> tuple[str, ...]:
        return tuple(item.policy_id for item in self.policies)

    @property
    def admitted_feature_ids(self) -> tuple[str, ...]:
        return tuple(feature_id for feature_id, _ in self.feature_policy_bindings)

    @property
    def admitted_strategy_classes(self) -> tuple[str, ...]:
        return tuple(sorted({item.rule.strategy_class for item in self.policies}))

    @property
    def delivery_rules(self) -> tuple[DeliveryRule, ...]:
        return tuple(item.rule for item in self.policies)

    def policy_for_feature(self, feature_id: str) -> DeliveryPolicyDefinition | None:
        policy_by_id = {item.policy_id: item for item in self.policies}
        policy_id = dict(self.feature_policy_bindings).get(feature_id)
        return policy_by_id.get(policy_id) if policy_id is not None else None

    def candidate_max_markdown_bytes(
        self,
        feature_id: str,
        delivery_dependency_feature_ids: tuple[str, ...] = (),
    ) -> int:
        """Return the exact final-Markdown envelope for one composed candidate."""

        owner = self.policy_for_feature(feature_id)
        dependencies = tuple(delivery_dependency_feature_ids)
        if owner is None or dependencies != tuple(sorted(set(dependencies))):
            return 0
        dependency_policies = tuple(
            self.policy_for_feature(dependency_id)
            for dependency_id in dependencies
        )
        if any(policy is None for policy in dependency_policies):
            return 0
        return min(
            MAX_COMPILER_MARKDOWN_BYTES,
            owner.max_markdown_bytes + sum(
                policy.dependency_allowance_markdown_bytes
                for policy in dependency_policies
                if policy is not None
            ),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "profile_id": self.profile_id,
            "policies": [
                {
                    "policy_id": item.policy_id,
                    "strategy_class": item.rule.strategy_class,
                    "trigger_kind": item.rule.trigger_kind,
                    "presentation_kind": item.rule.presentation_kind,
                    "lifetime": item.rule.lifetime,
                    "max_items": item.max_items,
                    "max_markdown_bytes": item.max_markdown_bytes,
                    "dependency_allowance_markdown_bytes": (
                        item.dependency_allowance_markdown_bytes
                    ),
                    "compatible_feature_ids": list(item.compatible_feature_ids),
                    "compatibility_contract": item.compatibility_contract,
                    "rejection_audit_reasons": list(
                        item.rejection_audit_reasons
                    ),
                    "frozen_research_exception": item.frozen_research_exception,
                }
                for item in self.policies
            ],
            "feature_policy_bindings": [
                {"feature_id": feature_id, "policy_id": policy_id}
                for feature_id, policy_id in self.feature_policy_bindings
            ],
            "aggregate_budget": {
                "max_items": self.aggregate_max_items,
                "max_markdown_bytes": self.aggregate_max_markdown_bytes,
            },
        }


def empty_delivery_plan(profile_id: str) -> ResolvedDeliveryPlan:
    return ResolvedDeliveryPlan(
        profile_id=profile_id,
        policies=(),
        feature_policy_bindings=(),
    )


def _sha256(value: dict[str, object]) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
