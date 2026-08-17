"""Internal P4 candidate surface.  These values are never rendered directly."""

from __future__ import annotations

import re
from dataclasses import dataclass

from core.easycrypt.proof_state_compiler.contracts.evidence import EvidenceRef
from core.easycrypt.proof_state_compiler.contracts.diagnostics import (
    StructuredDiagnostic,
)
from core.easycrypt.proof_state_compiler.contracts.frozen_json import FrozenJsonObject
from core.easycrypt.proof_state_compiler.contracts.state_ref import (
    ProvenanceRef,
    StateRef,
)
from core.easycrypt.proof_state_compiler.contracts.strategy import StrategyContract
from core.easycrypt.proof_state_compiler.contracts.correction import (
    CorrectionPresentation,
)
from core.easycrypt.proof_state_compiler.contracts.action_surface import (
    validate_compiler_action,
)


@dataclass(frozen=True)
class ResourceReferenceCandidate:
    candidate_id: str
    feature_id: str
    resource_id: str
    label: str
    strategy_contract: StrategyContract
    evidence_refs: tuple[EvidenceRef, ...]
    trigger_id: str = ""

    def __post_init__(self) -> None:
        if not self.candidate_id or not self.feature_id or not self.resource_id:
            raise ValueError("resource candidate requires identity and feature")
        if not self.label or not self.evidence_refs:
            raise ValueError("resource candidate requires label and evidence")
        if not isinstance(self.strategy_contract, StrategyContract):
            raise TypeError("resource candidate requires a strategy contract")


@dataclass(frozen=True)
class BindingReferenceCandidate:
    candidate_id: str
    feature_id: str
    resource_id: str
    resolved: FrozenJsonObject
    unresolved: tuple[str, ...]
    strategy_contract: StrategyContract
    evidence_refs: tuple[EvidenceRef, ...]
    trigger_id: str = ""

    def __post_init__(self) -> None:
        if not self.candidate_id or not self.feature_id or not self.resource_id:
            raise ValueError("binding candidate requires identity and feature")
        if not self.evidence_refs:
            raise ValueError("binding candidate requires evidence")
        if not isinstance(self.strategy_contract, StrategyContract):
            raise TypeError("binding candidate requires a strategy contract")


@dataclass(frozen=True)
class ActionCandidate:
    candidate_id: str
    feature_id: str
    intent: str
    payload: FrozenJsonObject
    unresolved_premises: tuple[str, ...]
    certification_policy: str
    strategy_contract: StrategyContract
    evidence_refs: tuple[EvidenceRef, ...]
    trigger_id: str = ""
    recovery_witness_id: str = ""
    correction: CorrectionPresentation | None = None
    delivery_dependency_feature_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.candidate_id or not self.feature_id or not self.intent:
            raise ValueError("action candidate requires identity, feature, and intent")
        if not self.certification_policy:
            raise ValueError("action candidate requires certification policy")
        if not self.evidence_refs:
            raise ValueError("action candidate requires evidence")
        if not isinstance(self.strategy_contract, StrategyContract):
            raise TypeError("action candidate requires a strategy contract")
        validate_compiler_action(self.intent, self.payload)
        if bool(self.recovery_witness_id) is not bool(self.correction):
            raise ValueError(
                "recovery correction requires both witness and presentation"
            )
        _validate_delivery_dependencies(
            self.feature_id,
            self.delivery_dependency_feature_ids,
        )


@dataclass(frozen=True)
class DiagnosticCandidate:
    candidate_id: str
    feature_id: str
    diagnostic: StructuredDiagnostic
    strategy_contract: StrategyContract
    delivery_dependency_feature_ids: tuple[str, ...] = ()
    recovery_lifetime_scope_id: str = ""

    def __post_init__(self) -> None:
        if not self.candidate_id or not self.feature_id:
            raise ValueError("diagnostic candidate requires identity and feature")
        if not isinstance(self.diagnostic, StructuredDiagnostic):
            raise TypeError("diagnostic candidate requires structured content")
        if not isinstance(self.strategy_contract, StrategyContract):
            raise TypeError("diagnostic candidate requires a strategy contract")
        if self.recovery_lifetime_scope_id and not re.fullmatch(
            r"[0-9a-f]{64}", self.recovery_lifetime_scope_id
        ):
            raise ValueError("diagnostic recovery lifetime scope is invalid")
        _validate_delivery_dependencies(
            self.feature_id,
            self.delivery_dependency_feature_ids,
        )

    @property
    def code(self) -> str:
        return self.diagnostic.code

    @property
    def evidence_refs(self) -> tuple[EvidenceRef, ...]:
        return self.diagnostic.evidence_refs

    @property
    def trigger_id(self) -> str:
        return self.diagnostic.trigger_id


@dataclass(frozen=True)
class CandidateSurface:
    state_ref: StateRef
    provenance: ProvenanceRef
    resource_references: tuple[ResourceReferenceCandidate, ...] = ()
    binding_references: tuple[BindingReferenceCandidate, ...] = ()
    actions: tuple[ActionCandidate, ...] = ()
    diagnostics: tuple[DiagnosticCandidate, ...] = ()
    audit_reasons: tuple[str, ...] = ()

    @property
    def empty(self) -> bool:
        return not (
            self.resource_references
            or self.binding_references
            or self.actions
            or self.diagnostics
        )


def _validate_delivery_dependencies(
    feature_id: str,
    dependencies: tuple[str, ...],
) -> None:
    if (
        type(dependencies) is not tuple
        or dependencies != tuple(sorted(set(dependencies)))
        or any(not item for item in dependencies)
        or feature_id in dependencies
    ):
        raise ValueError("candidate delivery dependencies are invalid")
