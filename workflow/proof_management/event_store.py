"""Proof-node event and audit storage.

This service keeps the node-local event spine deliberately small: typed events
are append-only, and resume route context is a bounded projection of those
events. It does not interpret proof tactics.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.easycrypt.value_shapes import drop_empty as _drop_empty
from workflow.proof_management.managed_turn_outcome import action_outcome_from_action
from workflow.proof_management.tactic_utils import tactic_head as _tactic_head

from .events import (
    ProofEvent,
    RESUME_ROUTE_EVENT_SCHEMA_VERSION,
    intent_event,
    malformed_intent_event,
    manager_audit_event,
    require_route_event_verdict,
    route_event_verdict_from_outcome,
    route_projection_event,
)

RESUME_ROUTE_EVENT_KIND = "resume_route_event"
_RESUME_ROUTE_EVENT_REQUIRED_FIELDS = {
    "kind",
    "schema_version",
    "intent",
    "outcome_kind",
    "proof_state_effect",
    "needs_attention",
    "accepted",
    "rejected",
    "changed",
}
_RESUME_ROUTE_EVENT_OPTIONAL_FIELDS = {
    "tactic",
    "tactic_head",
    "error_summary",
}


class ProofEventStoreError(RuntimeError):
    """The current manager event spine could not be read or persisted safely."""


class ProofEventManager:
    """Owns node-local typed events and manager audit output."""

    def __init__(
        self,
        *,
        node_id: str,
        run_dir: Path | None = None,
        route_event_limit: int = 40,
    ) -> None:
        self.node_id = node_id
        self.run_dir = Path(run_dir) if run_dir is not None else None
        self.route_event_limit = max(1, int(route_event_limit))
        self.events: list[ProofEvent] = []
        self._load_typed_events()

    @property
    def route_event_facts(self) -> list[dict[str, Any]]:
        return [
            dict(event.route_event)
            for event in self.events
            if event.kind == "route_event" and event.route_event
        ][-self.route_event_limit :]

    def append_event(self, event: ProofEvent) -> ProofEvent:
        stored = event.with_sequence(len(self.events) + 1)
        # Current manager events have one exact persisted schema. Validate before
        # either durable or analyzer-visible state can advance.
        ProofEvent.from_dict(stored.to_dict())
        self._write_typed_event(stored)
        self.events.append(stored)
        return stored

    def record_intent_received(
        self,
        *,
        intent: str,
        payload: dict[str, Any] | None = None,
        state_version: int = 0,
    ) -> ProofEvent:
        return self.append_event(intent_event(
            node_id=self.node_id,
            intent=intent,
            payload=payload,
            state_version=state_version,
        ))

    def record_malformed_intent(
        self,
        *,
        error: str,
        malformed_count: int,
        state_version: int = 0,
    ) -> ProofEvent:
        return self.append_event(malformed_intent_event(
            node_id=self.node_id,
            error=error,
            malformed_count=malformed_count,
            state_version=state_version,
        ))

    def record_route_event(self, event: dict[str, Any]) -> dict[str, Any]:
        if not event:
            return {}
        out = dict(event)
        out["turn_index"] = self._route_event_count() + 1
        self.append_event(route_projection_event(
            node_id=self.node_id,
            route_event=out,
        ))
        return out

    def seed_resume_route_events(
        self,
        events: list[dict[str, Any]],
        *,
        source: str = "resume_capsule",
    ) -> None:
        """Seed route facts from a durable resume handoff."""
        normalized_events = [
            require_resume_route_event(
                event,
                source=source,
                label=f"resume_route_events[{index}]",
            )
            for index, event in enumerate(events)
        ]
        for normalized in normalized_events:
            self.record_route_event(normalized)

    def record_route_turn(
        self,
        *,
        intent: str,
        payload: dict[str, Any] | None,
        actions: list[dict[str, Any]],
        observation: dict[str, Any],
    ) -> dict[str, Any]:
        """Project a manager turn into the bounded route-event stream."""
        return self.record_route_event(_route_event_from_turn(
            intent=intent,
            payload=payload,
            actions=actions,
            observation=observation,
        ))

    def recent_events(self, limit: int = 40) -> list[dict[str, Any]]:
        return [event.to_dict() for event in self.events[-max(1, int(limit)):]]

    def _route_event_count(self) -> int:
        return sum(1 for event in self.events if event.kind == "route_event")

    def audit(self, record: dict[str, Any]) -> None:
        self.append_event(manager_audit_event(
            node_id=self.node_id,
            record=record,
        ))
        if self.run_dir is None:
            return
        try:
            self.run_dir.mkdir(parents=True, exist_ok=True)
            path = self.run_dir / "proof_node_manager_audit.jsonl"
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, sort_keys=True) + "\n")
        except Exception as exc:
            raise ProofEventStoreError(
                "failed to write current proof node manager audit"
            ) from exc

    def _write_typed_event(self, event: ProofEvent) -> None:
        if self.run_dir is None:
            return
        try:
            self.run_dir.mkdir(parents=True, exist_ok=True)
            path = self.run_dir / "proof_node_events.jsonl"
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(event.to_dict(), sort_keys=True) + "\n")
        except Exception as exc:
            raise ProofEventStoreError(
                "failed to write current proof node event"
            ) from exc

    def _load_typed_events(self) -> None:
        if self.run_dir is None:
            return
        path = self.run_dir / "proof_node_events.jsonl"
        if not path.exists():
            return
        loaded: list[ProofEvent] = []
        expected_sequence_by_node: dict[str, int] = {}
        try:
            for line_number, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(),
                start=1,
            ):
                if not line.strip():
                    continue
                try:
                    event = ProofEvent.from_dict(json.loads(line))
                except (json.JSONDecodeError, TypeError, ValueError) as exc:
                    raise ProofEventStoreError(
                        f"invalid current proof event at {path}:{line_number}: {exc}"
                    ) from exc
                expected = expected_sequence_by_node.get(event.node_id, 0) + 1
                if event.sequence != expected:
                    raise ProofEventStoreError(
                        "non-contiguous current proof event sequence at "
                        f"{path}:{line_number} for node {event.node_id!r}: "
                        f"expected {expected}, got {event.sequence}"
                    )
                expected_sequence_by_node[event.node_id] = expected
                if event.node_id == self.node_id:
                    loaded.append(event)
        except ProofEventStoreError:
            raise
        except Exception as exc:
            raise ProofEventStoreError(
                f"failed to load current proof node events from {path}"
            ) from exc
        if not loaded:
            return
        self.events = loaded


def _route_event_from_turn(
    *,
    intent: str,
    payload: dict[str, Any] | None,
    actions: list[dict[str, Any]],
    observation: dict[str, Any],
) -> dict[str, Any]:
    clean_payload = dict(payload) if isinstance(payload, dict) else {}
    action = next(
        (
            item
            for item in actions
            if isinstance(item, dict)
        ),
        {},
    )
    outcome = action_outcome_from_action(action)
    verdict = route_event_verdict_from_outcome(
        outcome_kind=outcome.outcome_kind,
        proof_state_effect=outcome.proof_state_effect,
        needs_attention=outcome.needs_attention,
    )
    error_summary = str(observation.get("error_summary") or "").strip()
    tactic = str(
        observation.get("tactic")
        or clean_payload.get("tactic")
        or ""
    ).strip()
    return _drop_empty({
        "intent": intent,
        "tactic": tactic,
        "tactic_head": _tactic_head(tactic),
        **verdict,
        "error_summary": error_summary,
    })


def require_resume_route_event(
    event: Any,
    *,
    source: str = "",
    label: str = "resume_route_event",
) -> dict[str, Any]:
    """Return an exact current resume-route fact or raise ``ValueError``.

    The current handoff contract is flat and typed.  Retired nested payloads,
    unknown fields, and string/integer stand-ins for booleans are rejected.
    Derived ``tactic_head`` values are checked when a producer supplies them
    rather than silently replacing contradictory evidence.
    """
    if type(event) is not dict:
        raise ValueError(f"{label} must be an object")
    fields = set(event)
    missing = _RESUME_ROUTE_EVENT_REQUIRED_FIELDS - fields
    unknown = fields - _RESUME_ROUTE_EVENT_REQUIRED_FIELDS - _RESUME_ROUTE_EVENT_OPTIONAL_FIELDS
    if missing or unknown:
        details: list[str] = []
        if missing:
            details.append("missing " + ", ".join(sorted(missing)))
        if unknown:
            details.append("unknown " + ", ".join(sorted(unknown)))
        raise ValueError(f"{label} has invalid fields: {'; '.join(details)}")
    if event["kind"] != RESUME_ROUTE_EVENT_KIND:
        raise ValueError(
            f"{label}.kind must be {RESUME_ROUTE_EVENT_KIND!r}"
        )
    if (
        type(event["schema_version"]) is not int
        or event["schema_version"] != RESUME_ROUTE_EVENT_SCHEMA_VERSION
    ):
        raise ValueError(
            f"{label}.schema_version must be integer "
            f"{RESUME_ROUTE_EVENT_SCHEMA_VERSION}"
        )
    intent = event["intent"]
    if type(intent) is not str or not intent.strip():
        raise ValueError(f"{label}.intent must be a non-empty string")
    for field_name in ("accepted", "rejected", "changed", "needs_attention"):
        if type(event[field_name]) is not bool:
            raise ValueError(f"{label}.{field_name} must be a boolean")
    verdict = require_route_event_verdict(event, label=label)
    for field_name in _RESUME_ROUTE_EVENT_OPTIONAL_FIELDS:
        if field_name in event and type(event[field_name]) is not str:
            raise ValueError(f"{label}.{field_name} must be a string")
    if type(source) is not str:
        raise ValueError(f"{label} source must be a string")

    tactic = event.get("tactic", "")
    tactic_head = _tactic_head(tactic)
    if "tactic_head" in event and event["tactic_head"] != tactic_head:
        raise ValueError(
            f"{label}.tactic_head does not match {label}.tactic"
        )

    out: dict[str, Any] = {
        "kind": RESUME_ROUTE_EVENT_KIND,
        "schema_version": RESUME_ROUTE_EVENT_SCHEMA_VERSION,
        "intent": intent,
        **verdict,
    }
    for field_name in ("tactic", "error_summary"):
        if field_name in event:
            out[field_name] = event[field_name]
    if tactic_head:
        out["tactic_head"] = tactic_head
    elif "tactic_head" in event:
        out["tactic_head"] = event["tactic_head"]
    if source:
        out["resume_source"] = source
    return out


def resume_route_event_from_manager_route_event(
    event: Any,
    *,
    label: str = "manager_route_event",
) -> dict[str, Any]:
    """Project one typed manager route event into the resume handoff schema.

    Manager events intentionally carry live-only fields such as ``turn_index``.
    A resume capsule preserves the complete canonical outcome contract and
    derives its typed booleans from that contract only.
    """
    if type(event) is not dict:
        raise ValueError(f"{label} must be an object")
    verdict = require_route_event_verdict(event, label=label)
    projected: dict[str, Any] = {
        "kind": RESUME_ROUTE_EVENT_KIND,
        "schema_version": RESUME_ROUTE_EVENT_SCHEMA_VERSION,
        **verdict,
    }
    for field_name in (
        "intent",
        "tactic",
        "tactic_head",
        "error_summary",
    ):
        if field_name in event:
            projected[field_name] = event[field_name]
    return require_resume_route_event(projected, label=label)
