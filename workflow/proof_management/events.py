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


@dataclass(frozen=True)
class ProofEvent:
    """Append-only event for one proof node."""

    kind: str
    node_id: str
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
        return cls(
            kind=str(value.get("kind") or ""),
            node_id=str(value.get("node_id") or value.get("node") or ""),
            sequence=_safe_int(value.get("sequence")),
            created_at=str(value.get("created_at") or ""),
            state_version=_safe_int(value.get("state_version")),
            intent=str(value.get("intent") or ""),
            payload=_dict(value.get("payload")),
            status=str(value.get("status") or ""),
            route_event=_dict(value.get("route_event")),
            observation=_dict(value.get("observation")),
            actions=[
                dict(item)
                for item in _list(value.get("actions"))
                if isinstance(item, dict)
            ],
            snapshot=_dict(value.get("snapshot")),
            metadata=_dict(value.get("metadata")),
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
        status=_route_status(route_event),
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


def _route_status(route_event: dict[str, Any]) -> str:
    if route_event.get("accepted") is True:
        return "accepted"
    if route_event.get("accepted") is False:
        return "rejected"
    if route_event.get("changed") is True:
        return "changed"
    return ""


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")





def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
