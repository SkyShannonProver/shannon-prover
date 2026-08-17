"""P3 output: shared coordinate, resource, and candidate-binding analyses.

``BindingResolution`` is a structured transport contract. A resolution built
only from Python lexical analysis is not EasyCrypt-typechecked and cannot be
exposed as a checked fact. Native exact-tactic preflight is mandatory for every
visible action until bindings are populated by the native semantic adapter.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core.easycrypt.proof_state_compiler.contracts.evidence import EvidenceRef
from core.easycrypt.proof_state_compiler.contracts.application_applicability import (
    ApplicationApplicability,
)
from core.easycrypt.proof_state_compiler.contracts.diagnostics import (
    StructuredDiagnostic,
)
from core.easycrypt.proof_state_compiler.contracts.proof_ir import (
    ApplicationSignature,
    ProgramStatement,
)
from core.easycrypt.proof_state_compiler.contracts.state_ref import (
    ProvenanceRef,
    StateRef,
)
from core.easycrypt.proof_state_compiler.contracts.failure import (
    AttemptedOperationIR,
    RECOVERY_NOT_APPLICABLE,
    RecoveryActionRealization,
    RecoveryClaim,
    RecoveryOwnership,
)


@dataclass(frozen=True)
class ProofCoordinate:
    status: str
    forward_frontier: ProgramStatement | None
    tactic_active_boundary: ProgramStatement | None
    blocker: str = ""
    evidence_refs: tuple[EvidenceRef, ...] = ()

    def __post_init__(self) -> None:
        if self.status not in {"known", "unknown"}:
            raise ValueError(f"unsupported coordinate status {self.status!r}")
        if self.status == "unknown" and (
            self.forward_frontier is not None
            or self.tactic_active_boundary is not None
        ):
            raise ValueError("unknown coordinate cannot carry invented boundaries")
        if self.status == "known" and not self.evidence_refs:
            raise ValueError("known coordinate requires evidence")


@dataclass(frozen=True)
class ResourceAssessment:
    resource_id: str
    status: str
    missing_conditions: tuple[str, ...] = ()
    blocker: str = ""
    evidence_refs: tuple[EvidenceRef, ...] = ()

    def __post_init__(self) -> None:
        if not self.resource_id:
            raise ValueError("resource_id is required")
        if self.status not in {"live", "blocked", "stale", "unknown"}:
            raise ValueError(f"unsupported resource status {self.status!r}")
        if self.status != "unknown" and not self.evidence_refs:
            raise ValueError("non-unknown resource status requires evidence")


@dataclass(frozen=True)
class SlotResolution:
    slot_id: str
    kind: str
    status: str
    expected: str
    value: str = ""
    reason: str = ""
    evidence_refs: tuple[EvidenceRef, ...] = ()

    def __post_init__(self) -> None:
        if not self.slot_id or not self.kind or not self.expected:
            raise ValueError("slot resolution requires identity, kind, and expectation")
        if self.status not in {"resolved", "deferred", "blocked", "unknown"}:
            raise ValueError(f"unsupported slot resolution status {self.status!r}")
        if self.status == "resolved" and not self.value:
            raise ValueError("resolved slot requires a value")
        if self.status != "resolved" and self.value:
            raise ValueError("non-resolved slot cannot carry a value")
        if self.status in {"deferred", "blocked"} and not self.reason:
            raise ValueError(f"{self.status} slot requires a reason")
        if self.status != "unknown" and not self.evidence_refs:
            raise ValueError("non-unknown slot resolution requires evidence")


@dataclass(frozen=True)
class BindingResolution:
    """One ordered candidate binding, with authority supplied by its evidence.

    ``mechanically_complete`` means the declared structural slots have been
    filled or deliberately deferred. It does not assert native type/module/
    proof compatibility when the producer used lexical Python analysis.
    """

    binding_id: str
    producer_id: str
    resource_id: str
    target: str
    signature: ApplicationSignature
    slots: tuple[SlotResolution, ...]
    mechanically_complete: bool
    evidence_refs: tuple[EvidenceRef, ...] = ()

    def __post_init__(self) -> None:
        if not self.binding_id or not self.producer_id:
            raise ValueError("binding resolution requires binding and producer IDs")
        if not self.resource_id or not self.target:
            raise ValueError("binding resolution requires resource and target")
        if self.signature.resource_id != self.resource_id:
            raise ValueError("binding resolution signature targets another resource")
        expected = [(slot.slot_id, slot.kind) for slot in self.signature.slots]
        observed = [(slot.slot_id, slot.kind) for slot in self.slots]
        if observed != expected:
            raise ValueError("binding slot resolutions must match signature order and kind")
        complete = all(
            resolution.status == "resolved"
            if slot.binding_mode == "required"
            else resolution.status in {"resolved", "deferred"}
            for slot, resolution in zip(self.signature.slots, self.slots)
        )
        if self.mechanically_complete != complete:
            raise ValueError("mechanically_complete disagrees with slot states")
        if not self.evidence_refs:
            raise ValueError("binding resolution requires evidence")


@dataclass(frozen=True)
class ApplicationCandidate:
    """Structurally complete local candidate before native P4 certification."""

    candidate_id: str
    producer_id: str
    binding_id: str
    resource_id: str
    target: str
    operation: str
    application_term: str
    slot_resolutions: tuple[SlotResolution, ...]
    unresolved_premises: tuple[str, ...]
    evidence_refs: tuple[EvidenceRef, ...]
    trigger_id: str = ""

    def __post_init__(self) -> None:
        if not self.candidate_id or not self.producer_id or not self.binding_id:
            raise ValueError(
                "application candidate requires candidate, producer, and binding IDs"
            )
        if not self.resource_id or not self.target or not self.application_term:
            raise ValueError(
                "application candidate requires resource, target, and term"
            )
        if self.operation not in {"apply", "exact", "call", "conseq"}:
            raise ValueError(
                f"unsupported application operation {self.operation!r}"
            )
        slot_ids = [slot.slot_id for slot in self.slot_resolutions]
        if len(slot_ids) != len(set(slot_ids)):
            raise ValueError("application candidate has duplicate slot resolutions")
        if any(
            slot.status not in {"resolved", "deferred"}
            for slot in self.slot_resolutions
        ):
            raise ValueError(
                "application candidate cannot contain blocked or unknown slots"
            )
        deferred = tuple(
            slot.expected
            for slot in self.slot_resolutions
            if slot.status == "deferred"
        )
        if self.unresolved_premises != deferred:
            raise ValueError(
                "application candidate premises disagree with deferred slots"
            )
        if not self.evidence_refs:
            raise ValueError("application candidate requires evidence")


@dataclass(frozen=True)
class ScopeAssessment:
    name: str
    status: str
    evidence_refs: tuple[EvidenceRef, ...] = ()

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("scope name is required")
        if self.status not in {"live", "consumed", "unavailable", "unknown"}:
            raise ValueError(f"unsupported scope status {self.status!r}")
        if self.status != "unknown" and not self.evidence_refs:
            raise ValueError("non-unknown scope status requires evidence")


@dataclass(frozen=True)
class BoundaryContractAssessment:
    boundary_kind: str
    position: str
    required_slots: tuple[str, ...]
    unresolved_semantic_choices: tuple[str, ...] = ()
    evidence_refs: tuple[EvidenceRef, ...] = ()

    def __post_init__(self) -> None:
        if not self.boundary_kind or not self.position:
            raise ValueError("boundary contract requires kind and position")
        if not self.evidence_refs:
            raise ValueError("boundary contract requires evidence")


@dataclass(frozen=True)
class TransformAssessment:
    transform: str
    status: str
    missing_conditions: tuple[str, ...] = ()
    blocker: str = ""
    evidence_refs: tuple[EvidenceRef, ...] = ()

    def __post_init__(self) -> None:
        if not self.transform:
            raise ValueError("transform name is required")
        if self.status not in {
            "applicable", "blocked", "checked_no_progress", "unknown"
        }:
            raise ValueError(f"unsupported transform status {self.status!r}")
        if self.status != "unknown" and not self.evidence_refs:
            raise ValueError("non-unknown transform status requires evidence")


@dataclass(frozen=True)
class AnalyzedProofState:
    """State-local shared facts only; no feature-shaped result fields."""

    state_ref: StateRef
    provenance: ProvenanceRef
    coordinate: ProofCoordinate
    attempted_operation: AttemptedOperationIR | None = None
    resources: tuple[ResourceAssessment, ...] = ()
    bindings: tuple[BindingResolution, ...] = ()
    applications: tuple[ApplicationCandidate, ...] = ()
    application_applicabilities: tuple[ApplicationApplicability, ...] = ()
    scope: tuple[ScopeAssessment, ...] = ()
    boundary_contracts: tuple[BoundaryContractAssessment, ...] = ()
    transforms: tuple[TransformAssessment, ...] = ()
    diagnostics: tuple[StructuredDiagnostic, ...] = ()
    recovery_action_realizations: tuple[RecoveryActionRealization, ...] = ()
    recovery_claims: tuple[RecoveryClaim, ...] = ()
    recovery_ownership: RecoveryOwnership = field(
        default_factory=lambda: RecoveryOwnership(
            status=RECOVERY_NOT_APPLICABLE
        )
    )

    def __post_init__(self) -> None:
        if (
            self.attempted_operation is not None
            and self.attempted_operation.state_ref != self.state_ref
        ):
            raise ValueError("analyzed attempted operation is stale")
        if any(
            item.state_ref != self.state_ref
            for item in self.application_applicabilities
        ):
            raise ValueError("analyzed application applicability is stale")
        keys = tuple(
            (item.producer_id, item.operation, item.selected_resource)
            for item in self.application_applicabilities
        )
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate application applicability assessment")
        realization_ids = tuple(
            item.realization_id for item in self.recovery_action_realizations
        )
        if len(realization_ids) != len(set(realization_ids)):
            raise ValueError("duplicate recovery action realization")
