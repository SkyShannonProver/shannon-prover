"""Feature-owned gates for deciding whether one compiler slice should run.

Execution gates are scheduling hints, not semantic authorities.  A negative
decision may avoid all compiler/runtime work for a feature.  A positive
decision only permits the normal native-authoritative P1--P4, certification,
admission, and delivery pipeline to run; it never creates a proof fact.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from core.easycrypt.proof_state_compiler.contracts import (
    CompilerTurnEvidence,
    STATE_REFRESH,
    TRIGGER_KINDS,
)


REPEATABLE = "repeatable"
ONCE_PER_TURN_OCCURRENCE = "once_per_turn_occurrence"
EXECUTION_LIFETIMES = frozenset({REPEATABLE, ONCE_PER_TURN_OCCURRENCE})


@dataclass(frozen=True)
class FeatureExecutionEligibility:
    """One feature-local, pre-P1 scheduling decision."""

    eligible: bool
    reason: str
    trigger_kind: str = ""

    def __post_init__(self) -> None:
        if not self.reason:
            raise ValueError("feature execution eligibility requires a reason")
        if self.eligible:
            if self.trigger_kind not in TRIGGER_KINDS:
                raise ValueError(
                    "eligible feature execution requires a valid trigger kind"
                )
        elif self.trigger_kind:
            raise ValueError(
                "ineligible feature execution cannot claim a trigger kind"
            )


FeatureExecutionPredicate = Callable[
    [CompilerTurnEvidence | None],
    FeatureExecutionEligibility,
]


@dataclass(frozen=True)
class FeatureExecutionGate:
    """Stable gate identity plus one cheap feature-owned predicate."""

    gate_id: str
    predicate: FeatureExecutionPredicate
    lifetime: str = REPEATABLE
    produces_recovery_handoff: bool = False
    accepts_recovery_handoff: bool = False

    def __post_init__(self) -> None:
        if not self.gate_id:
            raise ValueError("feature execution gate requires an ID")
        if not callable(self.predicate):
            raise TypeError("feature execution gate requires a predicate")
        if self.lifetime not in EXECUTION_LIFETIMES:
            raise ValueError("feature execution gate has an invalid lifetime")
        if self.produces_recovery_handoff and self.accepts_recovery_handoff:
            raise ValueError(
                "one execution gate cannot both produce and consume a "
                "recovery handoff"
            )

    def evaluate(
        self,
        turn_evidence: CompilerTurnEvidence | None,
    ) -> FeatureExecutionEligibility:
        decision = self.predicate(turn_evidence)
        if not isinstance(decision, FeatureExecutionEligibility):
            raise TypeError(
                "feature execution predicate must return "
                "FeatureExecutionEligibility"
            )
        return decision


@dataclass(frozen=True)
class FeatureExecutionDecision:
    """Auditable execution decision after attaching feature identity."""

    feature_id: str
    gate_id: str
    eligible: bool
    reason: str
    trigger_kind: str = ""
    lifetime: str = REPEATABLE

    def __post_init__(self) -> None:
        if not self.feature_id or not self.gate_id or not self.reason:
            raise ValueError("feature execution decision requires identities")
        FeatureExecutionEligibility(
            eligible=self.eligible,
            reason=self.reason,
            trigger_kind=self.trigger_kind,
        )
        if self.lifetime not in EXECUTION_LIFETIMES:
            raise ValueError("feature execution decision has an invalid lifetime")

    def to_dict(self) -> dict[str, object]:
        return {
            "feature_id": self.feature_id,
            "gate_id": self.gate_id,
            "eligible": self.eligible,
            "reason": self.reason,
            "trigger_kind": self.trigger_kind,
            "lifetime": self.lifetime,
        }


@dataclass(frozen=True)
class FeatureExecutionPlan:
    """The feature subset permitted to enter the expensive compiler path."""

    decisions: tuple[FeatureExecutionDecision, ...]

    def __post_init__(self) -> None:
        feature_ids = tuple(item.feature_id for item in self.decisions)
        if len(feature_ids) != len(set(feature_ids)):
            raise ValueError("feature execution plan contains duplicate IDs")

    @property
    def configured_feature_ids(self) -> tuple[str, ...]:
        return tuple(item.feature_id for item in self.decisions)

    @property
    def eligible_feature_ids(self) -> tuple[str, ...]:
        return tuple(
            item.feature_id for item in self.decisions if item.eligible
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "configured_feature_ids": list(self.configured_feature_ids),
            "eligible_feature_ids": list(self.eligible_feature_ids),
            "decisions": [item.to_dict() for item in self.decisions],
        }


def _state_refresh_eligibility(
    turn_evidence: CompilerTurnEvidence | None,
) -> FeatureExecutionEligibility:
    del turn_evidence
    return FeatureExecutionEligibility(
        eligible=True,
        reason="state_refresh_consumer",
        trigger_kind=STATE_REFRESH,
    )


STATE_REFRESH_EXECUTION_GATE = FeatureExecutionGate(
    gate_id="state_refresh",
    predicate=_state_refresh_eligibility,
)
