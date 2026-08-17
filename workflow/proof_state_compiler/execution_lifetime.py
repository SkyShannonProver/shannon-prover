"""Bounded service-local lifetime for event-triggered feature execution."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, replace

from core.easycrypt.proof_state_compiler.contracts import CompilerTurnEvidence
from core.easycrypt.proof_state_compiler.features.execution import (
    FeatureExecutionDecision,
    FeatureExecutionPlan,
    ONCE_PER_TURN_OCCURRENCE,
)


@dataclass
class FeatureExecutionLifetimeLedger:
    """Suppress re-running one terminal event occurrence, never proof content."""

    max_entries: int = 128
    _entries: dict[str, None] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.max_entries <= 0:
            raise ValueError("feature execution lifetime must be bounded")

    def suppress_completed(
        self,
        plan: FeatureExecutionPlan,
        turn_evidence: CompilerTurnEvidence | None,
    ) -> FeatureExecutionPlan:
        decisions = []
        for decision in plan.decisions:
            key = _occurrence_key(decision, turn_evidence)
            if decision.eligible and key and key in self._entries:
                decisions.append(replace(
                    decision,
                    eligible=False,
                    reason="turn_occurrence_already_compiled",
                    trigger_kind="",
                ))
            else:
                decisions.append(decision)
        return FeatureExecutionPlan(tuple(decisions))

    def record_completed(
        self,
        plan: FeatureExecutionPlan,
        turn_evidence: CompilerTurnEvidence | None,
    ) -> None:
        for decision in plan.decisions:
            if not decision.eligible:
                continue
            key = _occurrence_key(decision, turn_evidence)
            if not key:
                continue
            self._entries.pop(key, None)
            self._entries[key] = None
        while len(self._entries) > self.max_entries:
            oldest = next(iter(self._entries))
            del self._entries[oldest]

    @property
    def size(self) -> int:
        return len(self._entries)


def _occurrence_key(
    decision: FeatureExecutionDecision,
    turn_evidence: CompilerTurnEvidence | None,
) -> str:
    if decision.lifetime != ONCE_PER_TURN_OCCURRENCE:
        return ""
    if turn_evidence is None:
        if decision.eligible:
            raise ValueError(
                "once-per-turn execution requires authoritative turn evidence"
            )
        return ""
    payload = {
        "feature_id": decision.feature_id,
        "gate_id": decision.gate_id,
        "turn_evidence": turn_evidence.identity_payload(),
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
