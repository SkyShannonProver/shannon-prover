"""Trigger, presentation, and lifetime contracts for compiler delivery.

Delivery is a backend policy over typed candidates.  It is deliberately
separate from feature discovery and strategy classification: a candidate can
be true and EasyCrypt-certified while still being silent for the current
trigger or suppressed because the same content was already presented.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass

from core.easycrypt.proof_state_compiler.contracts.frozen_json import (
    FrozenJsonObject,
    freeze_json_object,
)
from core.easycrypt.proof_state_compiler.contracts.failure import (
    FailureObservation,
)
from core.easycrypt.proof_state_compiler.contracts.evidence import EvidenceRef
from core.easycrypt.proof_state_compiler.contracts.state_ref import StateRef
from core.easycrypt.proof_state_compiler.contracts.strategy import (
    COMMITMENT_RELATIVE,
    INTRINSIC,
    ROUTE_SELECTING,
    STRATEGY_CLASSES,
)


STATE_REFRESH = "state_refresh"
EXPLICIT_CONTEXT_REQUEST = "explicit_context_request"
AGENT_SELECTED_OPERATION = "agent_selected_operation"
CURRENT_STATE_FAILURE = "current_state_failure"
TRIGGER_KINDS = frozenset({
    STATE_REFRESH,
    EXPLICIT_CONTEXT_REQUEST,
    AGENT_SELECTED_OPERATION,
    CURRENT_STATE_FAILURE,
})

CHANGED_FACT = "changed_fact"
COMMITMENT_RESULT = "commitment_result"
FAILURE_LINKED_REPAIR = "failure_linked_repair"
OPTIONAL_ADVISORY = "optional_advisory"
PRESENTATION_KINDS = frozenset({
    CHANGED_FACT,
    COMMITMENT_RESULT,
    FAILURE_LINKED_REPAIR,
    OPTIONAL_ADVISORY,
})

ONCE_PER_CONTENT = "once_per_content"
ONCE_PER_TRIGGER = "once_per_trigger"
LIFETIMES = frozenset({ONCE_PER_CONTENT, ONCE_PER_TRIGGER})


@dataclass(frozen=True)
class CommitmentAnchor:
    """One authoritative event recording a proof choice already made.

    The anchor is intentionally semantic and feature-neutral.  Its subject is
    a typed/frozen object such as a selected theorem and operation, or the
    accepted invariant at a structural boundary.  The committed-prefix
    identity prevents an anchor from being reused on an unrelated route.
    """

    anchor_id: str
    anchor_kind: str
    source_event_id: str
    committed_prefix_identity: str
    subject: FrozenJsonObject

    def __post_init__(self) -> None:
        if not self.anchor_id or not self.anchor_kind or not self.source_event_id:
            raise ValueError("commitment anchor requires identity, kind, and event")
        if not self.committed_prefix_identity:
            raise ValueError("commitment anchor requires committed-prefix identity")
        if not isinstance(self.subject, FrozenJsonObject):
            raise TypeError("commitment anchor subject must be frozen JSON")


@dataclass(frozen=True)
class CompilerTrigger:
    """One delivery request bound to the exact current proof state."""

    trigger_id: str
    trigger_kind: str
    state_ref: StateRef
    source_event_id: str
    commitment_anchor: CommitmentAnchor | None = None

    def __post_init__(self) -> None:
        if not self.trigger_id or not self.source_event_id:
            raise ValueError("compiler trigger requires identity and source event")
        if self.trigger_kind not in TRIGGER_KINDS:
            raise ValueError(f"unsupported compiler trigger {self.trigger_kind!r}")
        if not isinstance(self.state_ref, StateRef):
            raise TypeError("compiler trigger requires an exact StateRef")
        if self.trigger_kind in {STATE_REFRESH, EXPLICIT_CONTEXT_REQUEST}:
            if self.commitment_anchor is not None:
                raise ValueError(
                    "state/context triggers cannot claim a proof commitment"
                )
        elif self.commitment_anchor is None:
            raise ValueError(
                "selected-operation and failure triggers require a commitment anchor"
            )
        if (
            self.commitment_anchor is not None
            and self.commitment_anchor.committed_prefix_identity
            != self.state_ref.committed_prefix_identity
        ):
            raise ValueError("compiler trigger commitment is stale for this prefix")


@dataclass(frozen=True)
class DeliveryRule:
    """Manifest policy for one strategy class and one exact trigger kind."""

    strategy_class: str
    trigger_kind: str
    presentation_kind: str
    lifetime: str

    def __post_init__(self) -> None:
        if self.strategy_class not in STRATEGY_CLASSES:
            raise ValueError(f"unsupported strategy class {self.strategy_class!r}")
        if self.trigger_kind not in TRIGGER_KINDS:
            raise ValueError(f"unsupported delivery trigger {self.trigger_kind!r}")
        if self.presentation_kind not in PRESENTATION_KINDS:
            raise ValueError(
                f"unsupported presentation kind {self.presentation_kind!r}"
            )
        if self.lifetime not in LIFETIMES:
            raise ValueError(f"unsupported delivery lifetime {self.lifetime!r}")

        if self.presentation_kind == OPTIONAL_ADVISORY:
            if (
                self.strategy_class != ROUTE_SELECTING
                or self.trigger_kind != STATE_REFRESH
                or self.lifetime != ONCE_PER_CONTENT
            ):
                raise ValueError(
                    "optional advisory must be route-selecting, state-triggered, "
                    "and once per content"
                )
        elif self.presentation_kind == CHANGED_FACT:
            if (
                self.strategy_class != INTRINSIC
                or self.trigger_kind != STATE_REFRESH
                or self.lifetime != ONCE_PER_CONTENT
            ):
                raise ValueError(
                    "changed fact must be intrinsic, state-triggered, and delta-only"
                )
        elif self.presentation_kind == COMMITMENT_RESULT:
            if (
                self.strategy_class != COMMITMENT_RELATIVE
                or self.trigger_kind != AGENT_SELECTED_OPERATION
                or self.lifetime != ONCE_PER_TRIGGER
            ):
                raise ValueError(
                    "commitment result requires one agent-selected-operation trigger"
                )
        elif (
            self.strategy_class != COMMITMENT_RELATIVE
            or self.trigger_kind != CURRENT_STATE_FAILURE
            or self.lifetime != ONCE_PER_TRIGGER
        ):
            raise ValueError(
                "failure repair requires one commitment-relative failure trigger"
            )


@dataclass(frozen=True)
class DeliveryPresentation:
    """Audit-complete delivery metadata attached to one final surface item."""

    presentation_id: str
    presentation_kind: str
    lifetime: str
    trigger_kind: str
    strategy_class: str
    policy_id: str = ""
    route_choice: str = ""

    def __post_init__(self) -> None:
        if not self.presentation_id:
            raise ValueError("delivery presentation requires an ID")
        if not self.policy_id:
            raise ValueError("delivery presentation requires a policy ID")
        if self.presentation_kind not in PRESENTATION_KINDS:
            raise ValueError("delivery presentation has an invalid kind")
        if self.lifetime not in LIFETIMES:
            raise ValueError("delivery presentation has an invalid lifetime")
        if self.trigger_kind not in TRIGGER_KINDS:
            raise ValueError("delivery presentation has an invalid trigger")
        if self.strategy_class not in STRATEGY_CLASSES:
            raise ValueError("delivery presentation has an invalid strategy class")
        if self.strategy_class == ROUTE_SELECTING and not self.route_choice:
            raise ValueError("route-selecting presentation must name its choice")
        if self.strategy_class != ROUTE_SELECTING and self.route_choice:
            raise ValueError("only route-selecting presentation may name a choice")


def state_refresh_trigger(state_ref: StateRef, source_event_id: str) -> CompilerTrigger:
    """Bind the ordinary no-agent-intent refresh to a current input event."""

    return CompilerTrigger(
        trigger_id=f"state-refresh:{source_event_id}",
        trigger_kind=STATE_REFRESH,
        state_ref=state_ref,
        source_event_id=source_event_id,
    )


_TURN_AUTHORITY_KINDS = frozenset({
    "event_bound_tactic_execution_result",
})
_MUTATION_OUTCOMES = frozenset({"accepted", "rejected", "no_progress"})
_HEX_RE = re.compile(r"^[0-9a-f]+$")


@dataclass(frozen=True)
class CompilerTurnEvidence:
    """Feature-neutral evidence for the one manager turn just completed.

    A manager may construct this value only from a current-call authoritative
    backend result.  It deliberately contains the small validated subset a
    compiler consumer can bind; stdout, stderr, workspace mirrors, and old
    artifacts are not accepted transports.
    """

    source_event_id: str
    source_event_sequence: int
    authority_kind: str
    artifact_ref: str
    artifact_hash: str
    hash_algorithm: str
    post_state_ref: StateRef
    intent: str
    payload: FrozenJsonObject
    outcome_kind: str
    proof_state_effect: str
    structured_error: str = ""

    def __post_init__(self) -> None:
        if (
            not self.source_event_id
            or type(self.source_event_sequence) is not int
            or self.source_event_sequence < 0
        ):
            raise ValueError("turn evidence requires a source event identity")
        if self.authority_kind not in _TURN_AUTHORITY_KINDS:
            raise ValueError("turn evidence requires an event-bound authority")
        if (
            not self.artifact_ref
            or self.artifact_ref.startswith("/")
            or ".." in self.artifact_ref.split("/")
        ):
            raise ValueError("turn evidence artifact ref must be confined")
        expected_hash_length = {"sha1": 40, "sha256": 64}.get(
            self.hash_algorithm
        )
        if (
            expected_hash_length is None
            or len(self.artifact_hash) != expected_hash_length
            or not _HEX_RE.fullmatch(self.artifact_hash)
        ):
            raise ValueError("turn evidence artifact hash is invalid")
        if not isinstance(self.post_state_ref, StateRef):
            raise TypeError("turn evidence requires one complete post-StateRef")
        if not self.intent or not isinstance(self.payload, FrozenJsonObject):
            raise ValueError("turn evidence requires an exact intent and payload")
        if self.authority_kind == "event_bound_tactic_execution_result":
            expected_effects = {
                "accepted": "changed",
                "rejected": "unchanged",
                "no_progress": "unchanged",
            }
            if (
                self.outcome_kind not in _MUTATION_OUTCOMES
                or self.proof_state_effect
                != expected_effects.get(self.outcome_kind)
            ):
                raise ValueError(
                    "turn evidence has an inconsistent proof mutation outcome"
                )
            if self.outcome_kind == "accepted" and self.structured_error:
                raise ValueError("accepted turn evidence cannot carry an error")
        elif (
            self.outcome_kind != "read_only"
            or self.proof_state_effect != "read_only"
            or self.structured_error
        ):
            raise ValueError("read-only turn evidence has an invalid outcome")

    def identity_payload(self) -> dict[str, object]:
        return {
            "source_event_id": self.source_event_id,
            "source_event_sequence": self.source_event_sequence,
            "authority_kind": self.authority_kind,
            "artifact_ref": self.artifact_ref,
            "artifact_hash": self.artifact_hash,
            "hash_algorithm": self.hash_algorithm,
            "post_state_ref": self.post_state_ref.identity_payload(),
            "intent": self.intent,
            "payload": self.payload.to_dict(),
            "outcome_kind": self.outcome_kind,
            "proof_state_effect": self.proof_state_effect,
            "structured_error": self.structured_error,
        }


@dataclass(frozen=True)
class CompilerInvocationContext:
    """All exact-state triggers available to one fixed P1--P4 invocation."""

    state_ref: StateRef
    triggers: tuple[CompilerTrigger, ...]
    turn_evidence: CompilerTurnEvidence | None = None
    failure_observation: FailureObservation | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.state_ref, StateRef):
            raise TypeError("compiler invocation requires a StateRef")
        if not self.triggers or len(self.triggers) > 2:
            raise ValueError("compiler invocation requires one or two triggers")
        if any(trigger.state_ref != self.state_ref for trigger in self.triggers):
            raise ValueError("compiler invocation trigger is stale")
        if len({trigger.trigger_id for trigger in self.triggers}) != len(
            self.triggers
        ):
            raise ValueError("compiler invocation has duplicate triggers")
        refresh = tuple(
            trigger
            for trigger in self.triggers
            if trigger.trigger_kind == STATE_REFRESH
        )
        if len(refresh) != 1 or self.triggers[0] is not refresh[0]:
            raise ValueError("compiler invocation requires one leading refresh")
        event_triggers = tuple(
            trigger
            for trigger in self.triggers
            if trigger.trigger_kind != STATE_REFRESH
        )
        if bool(event_triggers) != bool(self.turn_evidence):
            raise ValueError("compiler invocation event trigger/evidence diverged")
        if event_triggers and (
            event_triggers[0].source_event_id
            != self.turn_evidence.source_event_id
        ):
            raise ValueError("compiler invocation crosses event authority")
        failure_triggers = tuple(
            trigger for trigger in event_triggers
            if trigger.trigger_kind == CURRENT_STATE_FAILURE
        )
        if bool(failure_triggers) != bool(self.failure_observation):
            raise ValueError(
                "compiler invocation failure trigger/observation diverged"
            )
        if self.failure_observation is not None:
            failure = self.failure_observation
            if (
                failure.state_ref != self.state_ref
                or failure.source_event_id != failure_triggers[0].source_event_id
                or failure.committed_prefix_identity
                != self.state_ref.committed_prefix_identity
            ):
                raise ValueError("compiler invocation failure is stale")

    @property
    def state_refresh(self) -> CompilerTrigger:
        return self.triggers[0]

    @property
    def event_trigger(self) -> CompilerTrigger | None:
        return self.triggers[1] if len(self.triggers) == 2 else None

    @property
    def identity_sha256(self) -> str:
        payload = {
            "state": self.state_ref.identity_payload(),
            # The ordinary refresh event is observation provenance, not a
            # semantic P1--P4 input. Exact-state cache identity already binds
            # the state; include only commitment/failure material here.
            "event_triggers": [
                {
                    "trigger_id": trigger.trigger_id,
                    "trigger_kind": trigger.trigger_kind,
                    "source_event_id": trigger.source_event_id,
                    "anchor": (
                        {
                            "anchor_id": trigger.commitment_anchor.anchor_id,
                            "anchor_kind": trigger.commitment_anchor.anchor_kind,
                            "source_event_id": (
                                trigger.commitment_anchor.source_event_id
                            ),
                            "committed_prefix_identity": (
                                trigger.commitment_anchor
                                .committed_prefix_identity
                            ),
                            "subject": (
                                trigger.commitment_anchor.subject.to_dict()
                            ),
                        }
                        if trigger.commitment_anchor is not None
                        else None
                    ),
                }
                for trigger in self.triggers
                if trigger.trigger_kind != STATE_REFRESH
            ],
        }
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


def compiler_invocation_context(
    state_ref: StateRef,
    turn_evidence: CompilerTurnEvidence | None = None,
    *,
    source_event_id: str = "",
) -> CompilerInvocationContext:
    """Bind one optional authoritative turn to the exact current StateRef."""

    refresh_source = source_event_id or (
        turn_evidence.source_event_id if turn_evidence is not None else ""
    )
    if not refresh_source:
        raise ValueError("compiler invocation requires a current source event")
    refresh = state_refresh_trigger(state_ref, refresh_source)
    if turn_evidence is None:
        return CompilerInvocationContext(state_ref, (refresh,))
    if turn_evidence.post_state_ref != state_ref:
        raise ValueError("compiler turn evidence is stale for current state")
    if (
        turn_evidence.authority_kind
        != "event_bound_tactic_execution_result"
        or turn_evidence.intent != "commit_tactic"
    ):
        return CompilerInvocationContext(state_ref, (refresh,))
    tactic = turn_evidence.payload.to_dict().get("tactic")
    if not isinstance(tactic, str) or not tactic.strip():
        return CompilerInvocationContext(state_ref, (refresh,))
    subject = freeze_json_object({
        "intent": turn_evidence.intent,
        "payload": turn_evidence.payload.to_dict(),
        "structured_error": turn_evidence.structured_error,
    })
    semantic_digest = hashlib.sha256(
        json.dumps(
            subject.to_dict(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    rejected = turn_evidence.outcome_kind in {"rejected", "no_progress"}
    occurrence_digest = hashlib.sha256(
        (
            turn_evidence.source_event_id
            + "\0"
            + str(turn_evidence.source_event_sequence)
            + "\0"
            + semantic_digest
        ).encode("utf-8")
    ).hexdigest()
    anchor = CommitmentAnchor(
        anchor_id=("rejected-operation:" if rejected else "accepted-operation:")
        + occurrence_digest[:24],
        anchor_kind=(
            "rejected_proof_operation"
            if rejected
            else "accepted_proof_operation"
        ),
        source_event_id=turn_evidence.source_event_id,
        committed_prefix_identity=state_ref.committed_prefix_identity,
        subject=subject,
    )
    event_trigger = CompilerTrigger(
        trigger_id=("current-failure:" if rejected else "selected-operation:")
        + occurrence_digest[:24],
        trigger_kind=(CURRENT_STATE_FAILURE if rejected else AGENT_SELECTED_OPERATION),
        state_ref=state_ref,
        source_event_id=turn_evidence.source_event_id,
        commitment_anchor=anchor,
    )
    failure_observation = None
    if rejected:
        evidence_digest = hashlib.sha256(
            json.dumps(
                turn_evidence.identity_payload(),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        failure_observation = FailureObservation(
            observation_id=f"failure-observation:{occurrence_digest[:24]}",
            occurrence_identity=occurrence_digest,
            source_event_id=turn_evidence.source_event_id,
            source_event_sequence=turn_evidence.source_event_sequence,
            state_ref=state_ref,
            committed_prefix_identity=state_ref.committed_prefix_identity,
            intent=turn_evidence.intent,
            payload=turn_evidence.payload,
            outcome_kind=turn_evidence.outcome_kind,
            structured_error=turn_evidence.structured_error,
            evidence_ref=EvidenceRef(
                evidence_id=f"rejected-turn.{evidence_digest[:16]}",
                source_kind=turn_evidence.authority_kind,
                source_ref=(
                    f"{turn_evidence.artifact_ref}#"
                    f"{turn_evidence.source_event_id}"
                ),
                source_sha256=evidence_digest,
            ),
        )
    return CompilerInvocationContext(
        state_ref=state_ref,
        triggers=(refresh, event_trigger),
        turn_evidence=turn_evidence,
        failure_observation=failure_observation,
    )


def optional_advisory_rule() -> DeliveryRule:
    """The only proactive SC2 policy: labelled and delta-suppressed."""

    return DeliveryRule(
        strategy_class=ROUTE_SELECTING,
        trigger_kind=STATE_REFRESH,
        presentation_kind=OPTIONAL_ADVISORY,
        lifetime=ONCE_PER_CONTENT,
    )


def intrinsic_changed_fact_rule() -> DeliveryRule:
    """Delta-only exposure for an intrinsic current-state fact."""

    return DeliveryRule(
        strategy_class=INTRINSIC,
        trigger_kind=STATE_REFRESH,
        presentation_kind=CHANGED_FACT,
        lifetime=ONCE_PER_CONTENT,
    )


def commitment_result_rule() -> DeliveryRule:
    """Once-only result of an already accepted agent commitment."""

    return DeliveryRule(
        strategy_class=COMMITMENT_RELATIVE,
        trigger_kind=AGENT_SELECTED_OPERATION,
        presentation_kind=COMMITMENT_RESULT,
        lifetime=ONCE_PER_TRIGGER,
    )


def failure_linked_repair_rule() -> DeliveryRule:
    """Once-only feedback for the exact rejected operation event."""

    return DeliveryRule(
        strategy_class=COMMITMENT_RELATIVE,
        trigger_kind=CURRENT_STATE_FAILURE,
        presentation_kind=FAILURE_LINKED_REPAIR,
        lifetime=ONCE_PER_TRIGGER,
    )
