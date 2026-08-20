"""Typed proof-node events.

These events are the manager-owned history spine.  EasyCrypt remains the
semantic authority; events only record what the manager observed and surfaced.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from core.easycrypt.value_shapes import as_dict_copy as _dict
from core.easycrypt.value_shapes import drop_empty as _drop_empty, as_list as _list
from workflow.proof_management.managed_turn_outcome import PROOF_STATE_EFFECTS


PROOF_EVENT_SCHEMA_VERSION = 1
RESUME_ROUTE_EVENT_SCHEMA_VERSION = 2

_PROOF_EVENT_REQUIRED_FIELDS = frozenset({
    "schema_version",
    "kind",
    "node_id",
    "sequence",
    "created_at",
    "state_version",
})
_PROOF_EVENT_OPTIONAL_FIELDS = frozenset({
    "intent",
    "payload",
    "status",
    "route_event",
    "observation",
    "actions",
    "snapshot",
    "metadata",
})
_PROOF_EVENT_FIELDS = _PROOF_EVENT_REQUIRED_FIELDS | _PROOF_EVENT_OPTIONAL_FIELDS

_ROUTE_EVENT_REQUIRED_FIELDS = frozenset({
    "intent",
    "turn_index",
    "outcome_kind",
    "proof_state_effect",
    "needs_attention",
    "accepted",
    "rejected",
    "changed",
})
_ROUTE_EVENT_STRING_FIELDS = frozenset({
    "kind",
    "tactic",
    "tactic_head",
    "error_summary",
    "outcome_kind",
    "proof_state_effect",
    "resume_source",
})
_ROUTE_EVENT_OPTIONAL_FIELDS = _ROUTE_EVENT_STRING_FIELDS | frozenset({
    "schema_version",
})

_ACCEPTED_ROUTE_OUTCOMES = frozenset({
    "accepted",
    "partial_success",
    "accepted_unconfirmed",
    "read_only",
})
_ROUTE_OUTCOME_EFFECTS: dict[str, frozenset[str]] = {
    "accepted": frozenset({"changed", "unchanged"}),
    "partial_success": frozenset({"changed"}),
    "accepted_unconfirmed": frozenset({"unknown"}),
    "read_only": frozenset({"read_only"}),
    "rejected": frozenset({"unchanged"}),
    "no_progress": frozenset({"unchanged"}),
    "backend_error": frozenset({"read_only", "unknown"}),
    "timeout": frozenset({"read_only", "unknown"}),
    "control_menu": frozenset({"unchanged"}),
    "repair": frozenset({"unchanged"}),
    "unknown": frozenset({"unknown"}),
}
_ROUTE_OUTCOME_ATTENTION: dict[str, frozenset[bool]] = {
    "accepted": frozenset({False}),
    "partial_success": frozenset({True}),
    "accepted_unconfirmed": frozenset({False}),
    "read_only": frozenset({False}),
    "rejected": frozenset({True}),
    "no_progress": frozenset({True}),
    "backend_error": frozenset({True}),
    "timeout": frozenset({True}),
    "control_menu": frozenset({False, True}),
    "repair": frozenset({True}),
    "unknown": frozenset({False}),
}


@dataclass(frozen=True)
class ProofEvent:
    """Append-only event for one proof node."""

    kind: str
    node_id: str
    schema_version: int = PROOF_EVENT_SCHEMA_VERSION
    sequence: int = 0
    created_at: str = ""
    state_version: int = 0
    intent: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    status: str = ""
    route_event: dict[str, Any] = field(default_factory=dict)
    observation: dict[str, Any] = field(default_factory=dict)
    actions: list[dict[str, Any]] = field(default_factory=list)
    snapshot: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def with_sequence(self, sequence: int) -> "ProofEvent":
        return ProofEvent(
            kind=self.kind,
            node_id=self.node_id,
            schema_version=self.schema_version,
            sequence=int(sequence),
            created_at=self.created_at or _now(),
            state_version=self.state_version,
            intent=self.intent,
            payload=dict(self.payload),
            status=self.status,
            route_event=dict(self.route_event),
            observation=dict(self.observation),
            actions=[dict(item) for item in self.actions],
            snapshot=dict(self.snapshot),
            metadata=dict(self.metadata),
        )

    def to_dict(self) -> dict[str, Any]:
        return _drop_empty({
            "schema_version": self.schema_version,
            "kind": self.kind,
            "node_id": self.node_id,
            "sequence": self.sequence,
            "created_at": self.created_at,
            "state_version": self.state_version,
            "intent": self.intent,
            "payload": self.payload,
            "status": self.status,
            "route_event": self.route_event,
            "observation": self.observation,
            "actions": self.actions,
            "snapshot": self.snapshot,
            "metadata": self.metadata,
        })

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ProofEvent":
        if type(value) is not dict:
            raise TypeError("ProofEvent must be an object")
        if "node" in value:
            raise ValueError("ProofEvent.node is retired; use node_id")
        missing = sorted(_PROOF_EVENT_REQUIRED_FIELDS - set(value))
        unexpected = sorted(set(value) - _PROOF_EVENT_FIELDS)
        if missing:
            raise ValueError(
                "ProofEvent is missing required field(s): " + ", ".join(missing)
            )
        if unexpected:
            raise ValueError(
                "ProofEvent contains unexpected field(s): "
                + ", ".join(unexpected)
            )
        if (
            type(value.get("schema_version")) is not int
            or value.get("schema_version") != PROOF_EVENT_SCHEMA_VERSION
        ):
            raise ValueError(
                "ProofEvent requires exact integer schema_version=1"
            )
        kind = value.get("kind")
        node_id = value.get("node_id")
        if type(kind) is not str or not kind.strip():
            raise ValueError("ProofEvent.kind must be a non-empty string")
        if type(node_id) is not str or not node_id.strip():
            raise ValueError("ProofEvent.node_id must be a non-empty string")
        sequence = _require_int_field(value, "sequence", minimum=1)
        state_version = _require_int_field(value, "state_version", minimum=0)
        created_at = _require_string_field(value, "created_at", required=True)
        intent = _require_string_field(value, "intent")
        status = _require_string_field(value, "status")
        payload = _require_dict_field(value, "payload")
        route_event = value.get("route_event")
        if kind == "route_event":
            _validate_persisted_route_event(route_event)
        elif "route_event" in value and type(route_event) is not dict:
            raise ValueError("ProofEvent.route_event must be an object")
        observation = _require_dict_field(value, "observation")
        snapshot = _require_dict_field(value, "snapshot")
        metadata = _require_dict_field(value, "metadata")
        actions = value.get("actions", [])
        if type(actions) is not list or any(type(item) is not dict for item in actions):
            raise ValueError("ProofEvent.actions must be a list of objects")
        return cls(
            kind=kind,
            node_id=node_id,
            schema_version=PROOF_EVENT_SCHEMA_VERSION,
            sequence=sequence,
            created_at=created_at,
            state_version=state_version,
            intent=intent,
            payload=payload,
            status=status,
            route_event=_dict(route_event),
            observation=observation,
            actions=[dict(item) for item in actions],
            snapshot=snapshot,
            metadata=metadata,
        )


def intent_event(
    *,
    node_id: str,
    intent: str,
    payload: dict[str, Any] | None = None,
    state_version: int = 0,
) -> ProofEvent:
    return ProofEvent(
        kind="intent_received",
        node_id=node_id,
        state_version=state_version,
        intent=intent,
        payload=dict(payload or {}),
        status="received",
    )


def malformed_intent_event(
    *,
    node_id: str,
    error: str,
    malformed_count: int,
    state_version: int = 0,
) -> ProofEvent:
    return ProofEvent(
        kind="malformed_intent",
        node_id=node_id,
        state_version=state_version,
        status="rejected",
        metadata={
            "error": error,
            "malformed_count": malformed_count,
        },
    )


def route_projection_event(
    *,
    node_id: str,
    route_event: dict[str, Any],
    state_version: int = 0,
) -> ProofEvent:
    return ProofEvent(
        kind="route_event",
        node_id=node_id,
        state_version=state_version,
        intent=str(route_event.get("intent") or ""),
        status=str(route_event.get("outcome_kind") or ""),
        route_event=dict(route_event),
    )


def manager_audit_event(
    *,
    node_id: str,
    record: dict[str, Any],
) -> ProofEvent:
    intent_obj = record.get("intent")
    intent = ""
    payload: dict[str, Any] = {}
    if isinstance(intent_obj, dict):
        intent = str(intent_obj.get("intent") or "")
        payload = _dict(intent_obj.get("payload"))
    return ProofEvent(
        kind=str(record.get("kind") or "manager_audit"),
        node_id=node_id,
        intent=intent,
        payload=payload,
        status=str(record.get("status") or ""),
        actions=[
            dict(item)
            for item in _list(record.get("manager_actions"))
            if isinstance(item, dict)
        ],
        snapshot=_dict(record.get("snapshot")),
        metadata={"audit_record": dict(record)},
    )


def _validate_persisted_route_event(value: Any) -> None:
    if type(value) is not dict:
        raise ValueError("route_event ProofEvent requires route_event object")
    missing = _ROUTE_EVENT_REQUIRED_FIELDS - set(value)
    unknown = set(value) - _ROUTE_EVENT_REQUIRED_FIELDS - _ROUTE_EVENT_OPTIONAL_FIELDS
    if missing:
        if len(missing) == 1:
            field_name = next(iter(missing))
            raise ValueError(f"route_event.{field_name} is required")
        raise ValueError(
            "route_event is missing required field(s): "
            + ", ".join(sorted(missing))
        )
    if unknown:
        raise ValueError(
            "route_event contains unexpected field(s): "
            + ", ".join(sorted(unknown))
        )
    intent = value.get("intent")
    turn_index = value.get("turn_index")
    if type(intent) is not str or not intent.strip():
        raise ValueError("route_event.intent must be a non-empty string")
    if type(turn_index) is not int or turn_index < 1:
        raise ValueError("route_event.turn_index must be a positive integer")
    for field_name in ("accepted", "rejected", "changed", "needs_attention"):
        if type(value[field_name]) is not bool:
            raise ValueError(f"route_event.{field_name} must be a boolean")
    if "schema_version" in value and (
        type(value["schema_version"]) is not int
        or value["schema_version"] != RESUME_ROUTE_EVENT_SCHEMA_VERSION
    ):
        raise ValueError(
            "route_event.schema_version must be integer "
            f"{RESUME_ROUTE_EVENT_SCHEMA_VERSION}"
        )
    for field_name in _ROUTE_EVENT_STRING_FIELDS:
        if field_name in value and type(value[field_name]) is not str:
            raise ValueError(f"route_event.{field_name} must be a string")
    require_route_event_verdict(value, label="route_event")


def require_route_event_verdict(
    value: dict[str, Any],
    *,
    label: str,
) -> dict[str, Any]:
    """Return the canonical route verdict after validating derived flags."""

    if "status" in value:
        raise ValueError(
            f"{label}.status is retired; use {label}.outcome_kind"
        )
    expected = route_event_verdict_from_outcome(
        outcome_kind=value.get("outcome_kind"),
        proof_state_effect=value.get("proof_state_effect"),
        needs_attention=value.get("needs_attention"),
        label=label,
    )
    for field_name in ("accepted", "rejected", "changed"):
        actual = value.get(field_name)
        if type(actual) is not bool:
            raise ValueError(f"{label}.{field_name} must be a boolean")
        if actual is not expected[field_name]:
            raise ValueError(
                f"{label}.{field_name}={str(actual).lower()} contradicts "
                f"{label}.outcome_kind={expected['outcome_kind']!r}, "
                f"proof_state_effect={expected['proof_state_effect']!r}"
            )
    return expected


def route_event_verdict_from_outcome(
    *,
    outcome_kind: Any,
    proof_state_effect: Any,
    needs_attention: Any,
    label: str = "route_event",
) -> dict[str, Any]:
    """Project canonical outcome fields into the redundant route flags."""

    if (
        type(outcome_kind) is not str
        or outcome_kind not in _ROUTE_OUTCOME_EFFECTS
    ):
        raise ValueError(
            f"{label}.outcome_kind is not canonical: {outcome_kind!r}"
        )
    if (
        type(proof_state_effect) is not str
        or proof_state_effect not in PROOF_STATE_EFFECTS
    ):
        raise ValueError(
            f"{label}.proof_state_effect is not canonical: "
            f"{proof_state_effect!r}"
        )
    if proof_state_effect not in _ROUTE_OUTCOME_EFFECTS[outcome_kind]:
        raise ValueError(
            f"{label}.proof_state_effect={proof_state_effect!r} contradicts "
            f"{outcome_kind!r}"
        )
    if type(needs_attention) is not bool:
        raise ValueError(f"{label}.needs_attention must be a boolean")
    if needs_attention not in _ROUTE_OUTCOME_ATTENTION[outcome_kind]:
        raise ValueError(
            f"{label}.needs_attention={str(needs_attention).lower()} "
            f"contradicts {outcome_kind!r}"
        )
    return {
        "outcome_kind": outcome_kind,
        "proof_state_effect": proof_state_effect,
        "needs_attention": needs_attention,
        "accepted": outcome_kind in _ACCEPTED_ROUTE_OUTCOMES,
        "rejected": outcome_kind == "rejected",
        "changed": proof_state_effect == "changed",
    }


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def _require_int_field(
    value: dict[str, Any],
    field_name: str,
    *,
    minimum: int,
) -> int:
    item = value.get(field_name)
    if type(item) is not int or item < minimum:
        raise ValueError(
            f"ProofEvent.{field_name} must be an integer >= {minimum}"
        )
    return item


def _require_string_field(
    value: dict[str, Any],
    field_name: str,
    *,
    required: bool = False,
) -> str:
    if field_name not in value:
        return ""
    item = value[field_name]
    if type(item) is not str or (required and not item.strip()):
        suffix = "a non-empty string" if required else "a string"
        raise ValueError(f"ProofEvent.{field_name} must be {suffix}")
    return item


def _require_dict_field(
    value: dict[str, Any],
    field_name: str,
) -> dict[str, Any]:
    if field_name not in value:
        return {}
    item = value[field_name]
    if type(item) is not dict:
        raise ValueError(f"ProofEvent.{field_name} must be an object")
    return dict(item)
