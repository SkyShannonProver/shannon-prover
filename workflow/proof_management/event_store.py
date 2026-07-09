"""Proof-node event and audit storage.

This service keeps the node-local event spine deliberately small: typed events
are append-only, and analyzer route context is a bounded projection of those
events.  It does not interpret proof tactics.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from core.easycrypt.value_shapes import as_dict_copy as _dict
from core.easycrypt.value_shapes import drop_empty as _drop_empty
from workflow.proof_management.tactic_utils import tactic_head as _tactic_head

from .events import (
    ProofEvent,
    intent_event,
    malformed_intent_event,
    manager_audit_event,
    route_projection_event,
)


logger = logging.getLogger(__name__)


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
        self.events.append(stored)
        self._write_typed_event(stored)
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
        """Seed analyzer-visible route facts from a durable resume handoff."""
        for event in events:
            if not isinstance(event, dict):
                continue
            normalized = _resume_route_event(event, source=source)
            if not normalized:
                continue
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

    def latest_readonly_probe_event(self) -> dict[str, Any]:
        route_event_facts = self.route_event_facts
        if not route_event_facts:
            return {}
        latest = route_event_facts[-1]
        if latest.get("intent") != "probe_tactic":
            return {}
        if bool(latest.get("changed")):
            return {}
        return dict(latest)

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
            logger.warning("failed to write proof node manager audit: %s", exc)

    def _write_typed_event(self, event: ProofEvent) -> None:
        if self.run_dir is None:
            return
        try:
            self.run_dir.mkdir(parents=True, exist_ok=True)
            path = self.run_dir / "proof_node_events.jsonl"
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(event.to_dict(), sort_keys=True) + "\n")
        except Exception as exc:
            logger.warning("failed to write proof node event: %s", exc)

    def _load_typed_events(self) -> None:
        if self.run_dir is None:
            return
        path = self.run_dir / "proof_node_events.jsonl"
        if not path.exists():
            return
        loaded: list[ProofEvent] = []
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    event = ProofEvent.from_dict(json.loads(line))
                except (json.JSONDecodeError, TypeError, ValueError):
                    continue
                if event.node_id == self.node_id:
                    loaded.append(event)
        except Exception as exc:
            logger.warning("failed to load proof node events: %s", exc)
            return
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
            if isinstance(item, dict) and item.get("label") != "agent_view"
        ),
        {},
    )
    execution = _dict(observation.get("execution"))
    status = str(observation.get("status") or "").lower()
    error_summary = str(observation.get("error_summary") or "").strip()
    tactic = str(
        observation.get("tactic")
        or clean_payload.get("tactic")
        or ""
    ).strip()
    accepted = (
        status in {"accepted", "probe_accepted", "ok"}
        or bool(observation.get("probe_preview"))
        or bool(execution.get("state_changed") or execution.get("history_committed"))
        or "accepted" in str(action.get("agent_observation") or "").lower()
    )
    rejected = bool(error_summary) or status in {
        "rejected",
        "probe_rejected",
        "failed",
        "error",
    }
    changed = bool(execution.get("state_changed") or execution.get("history_committed"))
    return _drop_empty({
        "intent": intent,
        "tactic": tactic,
        "tactic_head": _tactic_head(tactic),
        "topic": clean_payload.get("topic"),
        "name": clean_payload.get("name"),
        "symbol": clean_payload.get("symbol"),
        "accepted": accepted,
        "rejected": rejected,
        "changed": changed,
        "error_summary": error_summary,
        "status": status,
    })


def _resume_route_event(
    event: dict[str, Any],
    *,
    source: str,
) -> dict[str, Any]:
    intent = str(event.get("intent") or "").strip()
    if not intent:
        intent_obj = _dict(event.get("intent_payload"))
        intent = str(intent_obj.get("intent") or "").strip()
    tactic = str(event.get("tactic") or "").strip()
    payload = _dict(event.get("payload"))
    if not tactic:
        tactic = str(payload.get("tactic") or "").strip()
    if not tactic:
        intent_obj = _dict(event.get("intent_payload"))
        intent_payload = _dict(intent_obj.get("payload"))
        tactic = str(intent_payload.get("tactic") or "").strip()
    error_summary = str(event.get("error_summary") or "").strip()
    accepted = bool(event.get("accepted"))
    rejected = bool(event.get("rejected"))
    changed = bool(event.get("changed"))
    status = str(event.get("status") or "").strip()
    if not intent:
        return {}
    return _drop_empty({
        "intent": intent,
        "tactic": tactic,
        "tactic_head": str(event.get("tactic_head") or _tactic_head(tactic)),
        "topic": event.get("topic"),
        "name": event.get("name"),
        "symbol": event.get("symbol"),
        "accepted": accepted,
        "rejected": rejected,
        "changed": changed,
        "error_summary": error_summary,
        "status": status,
        "resume_source": source,
    })


