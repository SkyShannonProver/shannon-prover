"""Typed authoritative failure and recovery-ownership contracts.

Failure delivery is horizontal policy.  The proof-domain feature that can
repair an attempted operation owns a ``RecoveryClaim``; shared P1/P2 contracts
own the rejected occurrence and parsed operation identity.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from core.easycrypt.proof_state_compiler.contracts.evidence import EvidenceRef
from core.easycrypt.proof_state_compiler.contracts.frozen_json import (
    FrozenJsonObject,
)
from core.easycrypt.proof_state_compiler.contracts.native_semantics import (
    NativeApplicationHeadDescriptor,
    NativeApplicationSyntaxRepairDescriptor,
    NativeEagerWhileDialectDescriptor,
    NativeIntroPatternRepairDescriptor,
    NativePhlTransitivityBoundaryDescriptor,
    NativePureTailRewriteDescriptor,
    NativeRelationBridgeChoiceDescriptor,
    NativeRelationBridgeDescriptor,
)
from core.easycrypt.proof_state_compiler.contracts.state_ref import StateRef


RECOVERY_NOT_APPLICABLE = "not_applicable"
RECOVERY_UNCLAIMED = "unclaimed"
RECOVERY_OWNED = "owned"
RECOVERY_CONFLICT = "conflict"
RECOVERY_INCONSISTENT = "inconsistent"
RECOVERY_OWNERSHIP_STATUSES = frozenset({
    RECOVERY_NOT_APPLICABLE,
    RECOVERY_UNCLAIMED,
    RECOVERY_OWNED,
    RECOVERY_CONFLICT,
    RECOVERY_INCONSISTENT,
})
RECOVERY_RESOURCE_MATCH_KINDS = frozenset({"none", "exact", "basename"})
RECOVERY_OUTPUT_KINDS = frozenset({"action", "diagnostic"})
EXACT_OPERATION_RESOURCE_WITNESS = "exact_operation_resource"
NATIVE_ARGUMENT_REALIZATION_WITNESS = "native_argument_realization"
NATIVE_TACTIC_PREFIX_WITNESS = "native_tactic_prefix"
RECOVERY_PRESERVATION_WITNESS_KINDS = frozenset({
    EXACT_OPERATION_RESOURCE_WITNESS,
    NATIVE_ARGUMENT_REALIZATION_WITNESS,
    NATIVE_TACTIC_PREFIX_WITNESS,
})


@dataclass(frozen=True)
class RecoveryHandoff:
    """One native-typed suffix at an exact compound boundary.

    The manager remains at the original ``StateRef`` because the rejected
    compound was rolled back.  ``accepted_prefix_effect`` records whether the
    scratch native prefix preserved that state or produced an intermediate
    proof state.  Any repaired state-changing suffix must therefore be
    recomposed with the exact prefix and certified from the original state.
    ``source_feature_id`` is the unique producer of this boundary fact and is
    also the factual fallback owner when no typed suffix consumer forms a P3
    recovery result.
    """

    handoff_kind: str
    source_feature_id: str
    source_rejected_tactic: str
    accepted_prefix_tactic: str
    accepted_prefix_effect: str
    accepted_prefix_stage_count: int
    derived_rejected_tactic: str
    native_failure_kind: str
    native_error_message: str

    def __post_init__(self) -> None:
        tactics = (
            self.source_rejected_tactic,
            self.accepted_prefix_tactic,
            self.derived_rejected_tactic,
        )
        prefix_body = self.accepted_prefix_tactic[:-1].rstrip()
        source_body = self.source_rejected_tactic[:-1].strip()
        if (
            self.handoff_kind != "native_compound_boundary"
            or not self.source_feature_id
            or self.accepted_prefix_effect not in {
                "accepted_no_progress", "accepted_changed"
            }
            or type(self.accepted_prefix_stage_count) is not int
            or self.accepted_prefix_stage_count < 1
            or any(
                not item
                or item != item.strip()
                or not item.endswith(".")
                for item in tactics
            )
            or self.source_rejected_tactic == self.derived_rejected_tactic
            or not prefix_body
            or not source_body.startswith(prefix_body + ";")
            or not self.native_failure_kind
            or not self.native_error_message
        ):
            raise ValueError("recovery handoff is invalid")

    def to_payload(self) -> dict[str, object]:
        return {
            "handoff_kind": self.handoff_kind,
            "source_feature_id": self.source_feature_id,
            "source_rejected_tactic": self.source_rejected_tactic,
            "accepted_prefix_tactic": self.accepted_prefix_tactic,
            "accepted_prefix_effect": self.accepted_prefix_effect,
            "accepted_prefix_stage_count": self.accepted_prefix_stage_count,
            "derived_rejected_tactic": self.derived_rejected_tactic,
            "native_failure_kind": self.native_failure_kind,
            "native_error_message": self.native_error_message,
        }

    @property
    def prefix_changes_state(self) -> bool:
        return self.accepted_prefix_effect == "accepted_changed"


@dataclass(frozen=True)
class RecoveryPreservationWitness:
    """Typed proof that one correction preserves an observed commitment.

    This is evidence carried through the existing recovery pipeline, not an
    execution mode.  The exact-operation witness freezes the historical
    operation/resource guard.  The native-argument witness permits one
    native-established realization to change tactic spelling while preserving
    the semantic argument supplied by the agent.
    """

    witness_kind: str
    witness_id: str
    source_operation_family: str
    target_operation_family: str
    selected_resource: str = ""
    committed_argument_sha256: str = ""
    native_family: str = ""
    realization_sha256: str = ""

    def __post_init__(self) -> None:
        if (
            self.witness_kind not in RECOVERY_PRESERVATION_WITNESS_KINDS
            or not self.witness_id
            or not self.source_operation_family
            or not self.target_operation_family
        ):
            raise ValueError("recovery preservation witness is incomplete")
        if self.witness_kind == EXACT_OPERATION_RESOURCE_WITNESS:
            if (
                self.source_operation_family != self.target_operation_family
                or self.committed_argument_sha256
                or self.native_family
                or self.realization_sha256
            ):
                raise ValueError("exact-operation witness changed its commitment")
        else:
            if (
                self.selected_resource
                or len(self.committed_argument_sha256) != 64
                or any(
                    char not in "0123456789abcdef"
                    for char in self.committed_argument_sha256
                )
                or not self.native_family
                or len(self.realization_sha256) != 64
                or any(
                    char not in "0123456789abcdef"
                    for char in self.realization_sha256
                )
            ):
                raise ValueError("native-argument witness lacks native identity")


@dataclass(frozen=True)
class RecoveryActionRealization:
    """One P3 cross-operation realization before P4 certification."""

    realization_id: str
    feature_id: str
    recovery_key: str
    trigger_id: str
    witness: RecoveryPreservationWitness
    exact_tactic: str
    reason_code: str
    reason: str
    evidence_refs: tuple[EvidenceRef, ...]

    def __post_init__(self) -> None:
        if not all((
            self.realization_id,
            self.feature_id,
            self.recovery_key,
            self.trigger_id,
            self.exact_tactic,
            self.reason_code,
            self.reason,
        )):
            raise ValueError("recovery action realization is incomplete")
        if not isinstance(self.witness, RecoveryPreservationWitness):
            raise TypeError("recovery realization requires a preservation witness")
        if not self.exact_tactic.endswith(".") or not self.evidence_refs:
            raise ValueError("recovery realization requires tactic and evidence")
        if self.witness.witness_kind != EXACT_OPERATION_RESOURCE_WITNESS and (
            hashlib.sha256(self.exact_tactic.encode("utf-8")).hexdigest()
            != self.witness.realization_sha256
        ):
            raise ValueError("recovery realization changed its witnessed tactic")


def exact_operation_resource_witness(
    operation_family: str,
    selected_resource: str,
) -> RecoveryPreservationWitness:
    """Build the historical same-operation/resource witness canonically."""

    payload = {
        "witness_kind": EXACT_OPERATION_RESOURCE_WITNESS,
        "operation_family": operation_family,
        "selected_resource": selected_resource,
    }
    identity = hashlib.sha256(json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
    return RecoveryPreservationWitness(
        witness_kind=EXACT_OPERATION_RESOURCE_WITNESS,
        witness_id=identity,
        source_operation_family=operation_family,
        target_operation_family=operation_family,
        selected_resource=selected_resource,
    )


def native_argument_realization_witness(
    *,
    source_operation_family: str,
    target_operation_family: str,
    committed_argument: str,
    native_family: str,
    exact_tactic: str,
) -> RecoveryPreservationWitness:
    """Bind one native-identified agent argument to one tactic realization."""

    argument_sha256 = hashlib.sha256(
        committed_argument.encode("utf-8")
    ).hexdigest()
    realization_sha256 = hashlib.sha256(exact_tactic.encode("utf-8")).hexdigest()
    payload = {
        "witness_kind": NATIVE_ARGUMENT_REALIZATION_WITNESS,
        "source_operation_family": source_operation_family,
        "target_operation_family": target_operation_family,
        "committed_argument_sha256": argument_sha256,
        "native_family": native_family,
        "realization_sha256": realization_sha256,
    }
    identity = hashlib.sha256(json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
    return RecoveryPreservationWitness(
        witness_kind=NATIVE_ARGUMENT_REALIZATION_WITNESS,
        witness_id=identity,
        source_operation_family=source_operation_family,
        target_operation_family=target_operation_family,
        committed_argument_sha256=argument_sha256,
        native_family=native_family,
        realization_sha256=realization_sha256,
    )


def native_tactic_prefix_witness(
    *,
    rejected_tactic: str,
    exact_prefix_tactic: str,
) -> RecoveryPreservationWitness:
    """Bind one exact failed compound tactic to a native-accepted prefix."""

    committed_sha256 = hashlib.sha256(
        rejected_tactic.encode("utf-8")
    ).hexdigest()
    realization_sha256 = hashlib.sha256(
        exact_prefix_tactic.encode("utf-8")
    ).hexdigest()
    payload = {
        "witness_kind": NATIVE_TACTIC_PREFIX_WITNESS,
        "source_operation_family": "compound_tactic",
        "target_operation_family": "tactic_prefix",
        "committed_argument_sha256": committed_sha256,
        "native_family": "accepted_proper_source_prefix",
        "realization_sha256": realization_sha256,
    }
    identity = hashlib.sha256(json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
    return RecoveryPreservationWitness(
        witness_kind=NATIVE_TACTIC_PREFIX_WITNESS,
        witness_id=identity,
        source_operation_family="compound_tactic",
        target_operation_family="tactic_prefix",
        committed_argument_sha256=committed_sha256,
        native_family="accepted_proper_source_prefix",
        realization_sha256=realization_sha256,
    )


@dataclass(frozen=True)
class FailureObservation:
    """One rejected/no-progress tactic result bound to its exact occurrence."""

    observation_id: str
    occurrence_identity: str
    source_event_id: str
    source_event_sequence: int
    state_ref: StateRef
    committed_prefix_identity: str
    intent: str
    payload: FrozenJsonObject
    outcome_kind: str
    structured_error: str
    evidence_ref: EvidenceRef

    def __post_init__(self) -> None:
        if not self.observation_id or not self.occurrence_identity:
            raise ValueError("failure observation requires stable identities")
        if (
            not self.source_event_id
            or type(self.source_event_sequence) is not int
            or self.source_event_sequence < 0
        ):
            raise ValueError("failure observation requires event identity")
        if not isinstance(self.state_ref, StateRef):
            raise TypeError("failure observation requires an exact StateRef")
        if (
            not self.committed_prefix_identity
            or self.committed_prefix_identity
            != self.state_ref.committed_prefix_identity
        ):
            raise ValueError("failure observation prefix is stale")
        if self.intent != "commit_tactic":
            raise ValueError("failure observation requires commit_tactic")
        if not isinstance(self.payload, FrozenJsonObject):
            raise TypeError("failure observation payload must be frozen JSON")
        tactic = self.payload.to_dict().get("tactic")
        if not isinstance(tactic, str) or not tactic.strip():
            raise ValueError("failure observation requires an exact tactic")
        if self.outcome_kind not in {"rejected", "no_progress"}:
            raise ValueError("failure observation requires a rejected outcome")
        if not isinstance(self.evidence_ref, EvidenceRef):
            raise TypeError("failure observation requires authoritative evidence")


@dataclass(frozen=True)
class AttemptedOperationIR:
    """Native-derived P2 descriptor of one exact rejected operation."""

    attempt_id: str
    failure_observation_id: str
    occurrence_identity: str
    trigger_id: str
    source_event_id: str
    state_ref: StateRef
    committed_prefix_identity: str
    operation_family: str
    exact_resource: str
    resource_basename: str
    rejected_tactic: str
    attempt_outcome_kind: str
    native_diagnostic_status: str
    native_failure_kind: str
    native_error_message: str
    parsed_arguments: tuple[str, ...]
    side: str
    positions: tuple[int, ...]
    application_head_descriptor: NativeApplicationHeadDescriptor | None
    relation_bridge_descriptor: NativeRelationBridgeDescriptor | None
    relation_bridge_choice_descriptor: NativeRelationBridgeChoiceDescriptor | None
    phl_transitivity_boundary_descriptor: (
        NativePhlTransitivityBoundaryDescriptor | None
    )
    eager_while_dialect_descriptor: NativeEagerWhileDialectDescriptor | None
    proof_term_descriptor: FrozenJsonObject
    evidence_refs: tuple[EvidenceRef, ...]
    pure_tail_rewrite_descriptor: NativePureTailRewriteDescriptor | None = None
    intro_pattern_repair_descriptor: NativeIntroPatternRepairDescriptor | None = None
    application_syntax_repair_descriptor: (
        NativeApplicationSyntaxRepairDescriptor | None
    ) = None
    recovery_handoff: RecoveryHandoff | None = None

    def __post_init__(self) -> None:
        if (
            not self.attempt_id
            or not self.failure_observation_id
            or not self.occurrence_identity
            or not self.trigger_id
            or not self.source_event_id
        ):
            raise ValueError("attempted operation requires complete identity")
        if not isinstance(self.state_ref, StateRef):
            raise TypeError("attempted operation requires an exact StateRef")
        if (
            self.committed_prefix_identity
            != self.state_ref.committed_prefix_identity
        ):
            raise ValueError("attempted operation prefix is stale")
        if self.operation_family not in {
            "apply", "exact", "call", "conseq", "transitivity", "change",
            "eager", "rewrite", "intro_pattern", "compound_tactic",
        }:
            raise ValueError("attempted operation has unsupported operation")
        if (
            self.resource_basename
            != (self.exact_resource.rsplit(".", 1)[-1] if self.exact_resource else "")
            or not self.rejected_tactic
            or not self.evidence_refs
        ):
            raise ValueError("attempted operation is incomplete")
        if self.attempt_outcome_kind not in {"rejected", "no_progress"}:
            raise ValueError("attempted operation outcome is invalid")
        if self.native_diagnostic_status not in {
            "blocker", "no_blocker", "indeterminate"
        }:
            raise ValueError("attempted operation diagnostic status is invalid")
        if (
            self.attempt_outcome_kind == "rejected"
            and self.native_diagnostic_status == "no_blocker"
        ):
            raise ValueError("rejected attempted operation requires native diagnostic")
        if self.native_diagnostic_status == "no_blocker" and (
            self.native_failure_kind or self.native_error_message
        ):
            raise ValueError("no-blocker attempted operation carried an error")
        if (
            self.native_diagnostic_status != "no_blocker"
            and not self.native_failure_kind
        ):
            raise ValueError("attempted operation diagnostic is empty")
        if (
            self.native_diagnostic_status == "indeterminate"
            and self.native_failure_kind != "native_assertion"
        ):
            raise ValueError("indeterminate attempted operation kind is invalid")
        if any(not item for item in self.parsed_arguments):
            raise ValueError("attempted operation arguments are invalid")
        if self.side not in {"", "left", "right"}:
            raise ValueError("attempted operation side is invalid")
        if any(type(item) is not int or item < 0 for item in self.positions):
            raise ValueError("attempted operation positions are invalid")
        if not isinstance(self.proof_term_descriptor, FrozenJsonObject):
            raise TypeError("attempted operation proof descriptor must be frozen")
        if (
            self.application_head_descriptor is not None
            and self.application_head_descriptor.resolved_head.identity.rsplit(
                ".", 1
            )[-1]
            != self.resource_basename
        ):
            raise ValueError("attempted operation head changed selected resource")
        if self.relation_bridge_descriptor is not None and (
            self.operation_family
            != self.relation_bridge_descriptor.source_operation
            or self.exact_resource
        ):
            raise ValueError("attempted relation bridge changed its identity")
        if self.relation_bridge_choice_descriptor is not None and (
            self.operation_family
            != self.relation_bridge_choice_descriptor.source_operation
            or self.exact_resource
            or self.relation_bridge_descriptor is not None
            or self.application_head_descriptor is not None
            or self.proof_term_descriptor.to_dict()
        ):
            raise ValueError("attempted relation choice changed its identity")
        if self.phl_transitivity_boundary_descriptor is not None and (
            self.operation_family
            != self.phl_transitivity_boundary_descriptor.source_operation
            or self.exact_resource
            or self.relation_bridge_descriptor is not None
            or self.relation_bridge_choice_descriptor is not None
            or self.application_head_descriptor is not None
            or self.proof_term_descriptor.to_dict()
            or self.side != self.phl_transitivity_boundary_descriptor.side
        ):
            raise ValueError("attempted PHL boundary changed its identity")
        if self.eager_while_dialect_descriptor is not None and (
            self.operation_family
            != self.eager_while_dialect_descriptor.source_operation
            or self.exact_resource
            or self.relation_bridge_descriptor is not None
            or self.relation_bridge_choice_descriptor is not None
            or self.phl_transitivity_boundary_descriptor is not None
            or self.application_head_descriptor is not None
            or self.proof_term_descriptor.to_dict()
            or self.side
            or self.positions
        ):
            raise ValueError("attempted eager dialect changed its identity")
        if self.pure_tail_rewrite_descriptor is not None and (
            self.operation_family
            != self.pure_tail_rewrite_descriptor.source_operation
            or self.operation_family != "rewrite"
            or self.exact_resource
            != self.pure_tail_rewrite_descriptor.selected_resource
            or self.relation_bridge_descriptor is not None
            or self.relation_bridge_choice_descriptor is not None
            or self.phl_transitivity_boundary_descriptor is not None
            or self.eager_while_dialect_descriptor is not None
            or self.application_head_descriptor is not None
            or self.proof_term_descriptor.to_dict()
            or self.side
            or self.positions
        ):
            raise ValueError("attempted pure-tail rewrite changed its identity")
        if self.intro_pattern_repair_descriptor is not None and (
            self.operation_family
            != self.intro_pattern_repair_descriptor.source_operation
            or self.operation_family != "intro_pattern"
            or self.exact_resource
            or self.relation_bridge_descriptor is not None
            or self.relation_bridge_choice_descriptor is not None
            or self.phl_transitivity_boundary_descriptor is not None
            or self.eager_while_dialect_descriptor is not None
            or self.pure_tail_rewrite_descriptor is not None
            or self.application_syntax_repair_descriptor is not None
            or self.application_head_descriptor is not None
            or self.proof_term_descriptor.to_dict()
            or self.side
            or self.positions
        ):
            raise ValueError("attempted intro-pattern repair changed its identity")
        syntax = self.application_syntax_repair_descriptor
        if syntax is not None and (
            self.operation_family != syntax.source_operation
            or self.exact_resource != syntax.selected_resource
            or self.native_failure_kind != syntax.failure_kind
            or self.application_head_descriptor is None
            or self.proof_term_descriptor.to_dict()
            or self.relation_bridge_descriptor is not None
            or self.relation_bridge_choice_descriptor is not None
            or self.phl_transitivity_boundary_descriptor is not None
            or self.eager_while_dialect_descriptor is not None
            or self.pure_tail_rewrite_descriptor is not None
            or self.intro_pattern_repair_descriptor is not None
            or self.parsed_arguments
            or self.side
            or self.positions
        ):
            raise ValueError(
                "attempted application syntax repair changed its identity"
            )
        if self.recovery_handoff is not None and (
            not isinstance(self.recovery_handoff, RecoveryHandoff)
            or self.recovery_handoff.derived_rejected_tactic
            != self.rejected_tactic
            or self.attempt_outcome_kind != "rejected"
            or self.recovery_handoff.native_error_message
            != self.native_error_message
        ):
            raise ValueError("attempted recovery handoff changed suffix identity")

    @property
    def operation(self) -> str:
        return self.operation_family

    @property
    def resource(self) -> str:
        return self.exact_resource

    @property
    def recovery_key(self) -> str:
        """Identity shared by every feature claiming this exact occurrence."""

        payload = {
            "attempt_id": self.attempt_id,
            "failure_observation_id": self.failure_observation_id,
            "occurrence_identity": self.occurrence_identity,
            "trigger_id": self.trigger_id,
            "source_event_id": self.source_event_id,
            "state_ref": self.state_ref.identity_payload(),
            "committed_prefix_identity": self.committed_prefix_identity,
            "operation_family": self.operation_family,
            "exact_resource": self.exact_resource,
            "attempt_outcome_kind": self.attempt_outcome_kind,
            "native_diagnostic_status": self.native_diagnostic_status,
            "native_failure_kind": self.native_failure_kind,
            "application_head_descriptor": (
                None
                if self.application_head_descriptor is None
                else self.application_head_descriptor.to_payload()
            ),
            "relation_bridge_descriptor": (
                None
                if self.relation_bridge_descriptor is None
                else self.relation_bridge_descriptor.to_payload()
            ),
            "relation_bridge_choice_descriptor": (
                None
                if self.relation_bridge_choice_descriptor is None
                else self.relation_bridge_choice_descriptor.to_payload()
            ),
            "phl_transitivity_boundary_descriptor": (
                None
                if self.phl_transitivity_boundary_descriptor is None
                else self.phl_transitivity_boundary_descriptor.to_payload()
            ),
            "eager_while_dialect_descriptor": (
                None
                if self.eager_while_dialect_descriptor is None
                else self.eager_while_dialect_descriptor.to_payload()
            ),
            "pure_tail_rewrite_descriptor": (
                None
                if self.pure_tail_rewrite_descriptor is None
                else self.pure_tail_rewrite_descriptor.to_payload()
            ),
            "intro_pattern_repair_descriptor": (
                None
                if self.intro_pattern_repair_descriptor is None
                else self.intro_pattern_repair_descriptor.to_payload()
            ),
            "application_syntax_repair_descriptor": (
                None
                if self.application_syntax_repair_descriptor is None
                else self.application_syntax_repair_descriptor.to_payload()
            ),
            "recovery_handoff": (
                None
                if self.recovery_handoff is None
                else self.recovery_handoff.to_payload()
            ),
            "proof_term_descriptor": self.proof_term_descriptor.to_dict(),
            "parsed_arguments": self.parsed_arguments,
            "side": self.side,
            "positions": self.positions,
        }
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class RecoveryClaim:
    """One semantic slice's ownership claim for an exact failed attempt."""

    feature_id: str
    recovery_key: str
    attempt_id: str
    occurrence_identity: str
    trigger_id: str
    operation_family: str
    selected_resource: str
    resource_match_kind: str
    allowed_output_kinds: tuple[str, ...]
    preservation_witness: RecoveryPreservationWitness
    evidence_refs: tuple[EvidenceRef, ...]

    def __post_init__(self) -> None:
        if not all((
            self.feature_id,
            self.recovery_key,
            self.attempt_id,
            self.occurrence_identity,
            self.trigger_id,
            self.operation_family,
        )):
            raise ValueError("recovery claim requires complete identity")
        if self.resource_match_kind not in RECOVERY_RESOURCE_MATCH_KINDS:
            raise ValueError("recovery claim resource match kind is invalid")
        if self.resource_match_kind == "none" and self.selected_resource:
            raise ValueError("resource-free recovery claim named a resource")
        if self.resource_match_kind != "none" and not self.selected_resource:
            raise ValueError("resource recovery claim requires selected resource")
        if (
            not self.allowed_output_kinds
            or self.allowed_output_kinds != tuple(sorted(set(
                self.allowed_output_kinds
            )))
            or any(
                item not in RECOVERY_OUTPUT_KINDS
                for item in self.allowed_output_kinds
            )
        ):
            raise ValueError("recovery claim output kinds are invalid")
        if not self.evidence_refs:
            raise ValueError("recovery claim requires evidence")
        if not isinstance(
            self.preservation_witness, RecoveryPreservationWitness
        ):
            raise TypeError("recovery claim requires a preservation witness")
        witness = self.preservation_witness
        if witness.source_operation_family != self.operation_family:
            raise ValueError("recovery witness source operation drifted")
        if witness.witness_kind == EXACT_OPERATION_RESOURCE_WITNESS:
            if witness.selected_resource != self.selected_resource:
                raise ValueError("recovery witness resource drifted")
        elif self.resource_match_kind != "none" or self.selected_resource:
            raise ValueError("cross-operation witness cannot claim a resource")


@dataclass(frozen=True)
class RecoveryOwnership:
    """Order-independent ownership result computed once after P3 producers."""

    status: str
    recovery_key: str = ""
    owner_feature_id: str = ""
    claimant_feature_ids: tuple[str, ...] = ()
    operation_family: str = ""
    selected_resource: str = ""
    resource_match_kind: str = "none"
    allowed_output_kinds: tuple[str, ...] = ()
    preservation_witness: RecoveryPreservationWitness | None = None
    audit_reason: str = ""

    def __post_init__(self) -> None:
        if self.status not in RECOVERY_OWNERSHIP_STATUSES:
            raise ValueError("unsupported recovery ownership status")
        if self.claimant_feature_ids != tuple(sorted(set(
            self.claimant_feature_ids
        ))):
            raise ValueError("recovery claimants must be canonical")
        if self.status == RECOVERY_OWNED:
            if (
                not self.recovery_key
                or not self.owner_feature_id
                or self.claimant_feature_ids != (self.owner_feature_id,)
                or self.audit_reason
                or not self.operation_family
                or self.resource_match_kind not in RECOVERY_RESOURCE_MATCH_KINDS
                or not self.allowed_output_kinds
                or self.preservation_witness is None
            ):
                raise ValueError("owned recovery requires exactly one owner")
            if self.resource_match_kind == "none" and self.selected_resource:
                raise ValueError("owned resource-free recovery named a resource")
            if self.resource_match_kind != "none" and not self.selected_resource:
                raise ValueError("owned resource recovery requires resource")
            if self.allowed_output_kinds != tuple(sorted(set(
                self.allowed_output_kinds
            ))) or any(
                item not in RECOVERY_OUTPUT_KINDS
                for item in self.allowed_output_kinds
            ):
                raise ValueError("owned recovery output kinds are invalid")
        else:
            if (
                self.owner_feature_id
                or self.operation_family
                or self.selected_resource
                or self.resource_match_kind != "none"
                or self.allowed_output_kinds
                or self.preservation_witness is not None
            ):
                raise ValueError("non-owned recovery cannot name an owner")
            if self.status in {RECOVERY_CONFLICT, RECOVERY_INCONSISTENT}:
                if not self.audit_reason:
                    raise ValueError("failed ownership requires an audit reason")

    def owns(self, feature_id: str, recovery_key: str) -> bool:
        return bool(
            self.status == RECOVERY_OWNED
            and self.owner_feature_id == feature_id
            and self.recovery_key == recovery_key
        )
