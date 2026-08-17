"""Feature-local typed result for an exact operation-binding correction."""

from __future__ import annotations

from dataclasses import dataclass

from core.easycrypt.proof_state_compiler.contracts import EvidenceRef
from core.easycrypt.proof_state_compiler.syntax.attempted_operation import (
    operation_resource,
)


OPERATION_BINDING_REPAIR_ANALYSIS_PRODUCER_ID = (
    "operation_binding_repair.analysis"
)


@dataclass(frozen=True)
class OperationBindingRepair:
    attempt_id: str
    occurrence_identity: str
    recovery_key: str
    trigger_id: str
    failure_class: str
    operation: str
    resource: str
    rejected_tactic: str
    corrected_tactic: str
    evidence_refs: tuple[EvidenceRef, ...]

    def __post_init__(self) -> None:
        if self.failure_class not in {"B1", "B2", "B4"}:
            raise ValueError("operation binding repair supports only B1/B2/B4")
        if self.operation not in {"apply", "exact", "call", "conseq"}:
            raise ValueError("operation binding repair has unsupported operation")
        if not all((
            self.attempt_id,
            self.occurrence_identity,
            self.recovery_key,
            self.trigger_id,
            self.resource,
        )) or not self.evidence_refs:
            raise ValueError("operation binding repair requires identity/evidence")
        rejected = operation_resource(self.rejected_tactic)
        corrected = operation_resource(self.corrected_tactic)
        if rejected is None or corrected is None:
            raise ValueError("operation binding repair requires bounded tactics")
        if rejected[0] != self.operation or corrected[0] != self.operation:
            raise ValueError("repair must preserve the same semantic operation")
        if self.failure_class == "B1":
            same_resource = (
                rejected[1].rsplit(".", 1)[-1]
                == corrected[1].rsplit(".", 1)[-1]
                == self.resource.rsplit(".", 1)[-1]
            )
        else:
            same_resource = rejected[1] == corrected[1] == self.resource
        if not same_resource:
            raise ValueError("repair must preserve the same selected resource")
