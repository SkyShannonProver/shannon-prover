"""Final compact compiler output admitted for agent presentation."""

from __future__ import annotations

from dataclasses import dataclass

from core.context_intents import intent_payload_contract_error
from core.easycrypt.proof_state_compiler.contracts.frozen_json import (
    FrozenJsonObject,
)
from core.easycrypt.proof_state_compiler.contracts.delivery import (
    DeliveryPresentation,
)
from core.easycrypt.proof_state_compiler.contracts.diagnostics import (
    StructuredDiagnostic,
)
from core.easycrypt.proof_state_compiler.contracts.state_ref import (
    ProvenanceRef,
    StateRef,
)
from core.easycrypt.proof_state_compiler.contracts.strategy import StrategyContract
from core.easycrypt.proof_state_compiler.contracts.correction import (
    CorrectionPresentation,
)


def validate_compiler_action(intent: object, payload: object) -> None:
    """Enforce the one manager-valid action shape the compiler may emit."""

    if intent != "commit_tactic":
        raise ValueError("compiler action intent must be commit_tactic")
    if isinstance(payload, FrozenJsonObject):
        data = payload.to_dict()
    elif isinstance(payload, dict):
        data = dict(payload)
    else:
        raise TypeError("compiler action payload must be an object")
    if set(data) != {"tactic"}:
        raise ValueError(
            "compiler action commit_tactic payload must contain only tactic"
        )
    error = intent_payload_contract_error("commit_tactic", data)
    if error:
        raise ValueError(f"compiler action payload is invalid: {error}")


@dataclass(frozen=True)
class ResourceReference:
    feature_id: str
    resource_id: str
    label: str
    strategy_contract: StrategyContract
    delivery: DeliveryPresentation
    evidence_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.feature_id or not self.resource_id or not self.label:
            raise ValueError("resource reference is incomplete")
        if not self.evidence_ids:
            raise ValueError("resource reference requires evidence IDs")
        if not isinstance(self.strategy_contract, StrategyContract):
            raise TypeError("resource reference requires a strategy contract")
        if not isinstance(self.delivery, DeliveryPresentation):
            raise TypeError("resource reference requires delivery metadata")


@dataclass(frozen=True)
class BindingReference:
    feature_id: str
    resource_id: str
    resolved: FrozenJsonObject
    unresolved: tuple[str, ...]
    strategy_contract: StrategyContract
    delivery: DeliveryPresentation
    evidence_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.feature_id or not self.resource_id:
            raise ValueError("binding reference is incomplete")
        if not self.evidence_ids:
            raise ValueError("binding reference requires evidence IDs")
        if not isinstance(self.strategy_contract, StrategyContract):
            raise TypeError("binding reference requires a strategy contract")
        if not isinstance(self.delivery, DeliveryPresentation):
            raise TypeError("binding reference requires delivery metadata")


@dataclass(frozen=True)
class VerifiedAction:
    feature_id: str
    intent: str
    payload: FrozenJsonObject
    unresolved_premises: tuple[str, ...]
    verification_ref: str
    checked_effect: FrozenJsonObject
    strategy_contract: StrategyContract
    delivery: DeliveryPresentation
    evidence_ids: tuple[str, ...]
    recovery_witness_id: str = ""
    correction: CorrectionPresentation | None = None

    def __post_init__(self) -> None:
        if not self.feature_id or not self.intent or not self.verification_ref:
            raise ValueError("verified action is incomplete")
        if not self.evidence_ids:
            raise ValueError("verified action requires evidence IDs")
        if not isinstance(self.strategy_contract, StrategyContract):
            raise TypeError("verified action requires a strategy contract")
        if not isinstance(self.delivery, DeliveryPresentation):
            raise TypeError("verified action requires delivery metadata")
        validate_compiler_action(self.intent, self.payload)
        if bool(self.recovery_witness_id) is not bool(self.correction):
            raise ValueError(
                "verified recovery correction requires witness and presentation"
            )


@dataclass(frozen=True)
class NeutralDiagnostic:
    feature_id: str
    diagnostic: StructuredDiagnostic
    strategy_contract: StrategyContract
    delivery: DeliveryPresentation
    evidence_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.feature_id:
            raise ValueError("diagnostic is incomplete")
        if not isinstance(self.diagnostic, StructuredDiagnostic):
            raise TypeError("diagnostic requires structured content")
        if not self.evidence_ids:
            raise ValueError("diagnostic requires evidence IDs")
        if self.evidence_ids != tuple(
            item.evidence_id for item in self.diagnostic.evidence_refs
        ):
            raise ValueError("diagnostic evidence IDs diverge from its content")
        if not isinstance(self.strategy_contract, StrategyContract):
            raise TypeError("diagnostic requires a strategy contract")
        if not isinstance(self.delivery, DeliveryPresentation):
            raise TypeError("diagnostic requires delivery metadata")

    @property
    def code(self) -> str:
        return self.diagnostic.code


@dataclass(frozen=True)
class ActionSurface:
    """Only admitted entries; this is safe for generic rendering."""

    state_ref: StateRef
    provenance: ProvenanceRef
    resource_references: tuple[ResourceReference, ...] = ()
    binding_references: tuple[BindingReference, ...] = ()
    actions: tuple[VerifiedAction, ...] = ()
    diagnostics: tuple[NeutralDiagnostic, ...] = ()

    @property
    def empty(self) -> bool:
        return not (
            self.resource_references
            or self.binding_references
            or self.actions
            or self.diagnostics
        )
