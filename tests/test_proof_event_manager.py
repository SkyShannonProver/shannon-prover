from __future__ import annotations

import json
from pathlib import Path

import pytest

from workflow.proof_management.event_store import ProofEventManager


def test_proof_event_manager_records_bounded_route_event_facts() -> None:
    manager = ProofEventManager(
        node_id="Tree-unit",
        route_event_limit=2,
    )

    manager.record_route_event({"intent": "probe_tactic"})
    manager.record_route_event({"intent": "commit_tactic"})
    manager.record_route_event({"intent": "undo_to_checkpoint"})

    assert [event["intent"] for event in manager.route_event_facts] == [
        "commit_tactic",
        "undo_to_checkpoint",
    ]
    assert [event["turn_index"] for event in manager.route_event_facts] == [2, 3]
    assert [event.kind for event in manager.events] == [
        "route_event",
        "route_event",
        "route_event",
    ]


def test_route_event_facts_projection_is_read_only() -> None:
    manager = ProofEventManager(node_id="Tree-unit")

    with pytest.raises(AttributeError):
        manager.route_event_facts = [{"intent": "probe_tactic"}]  # type: ignore[misc]


def test_proof_event_manager_writes_audit_jsonl(tmp_path: Path) -> None:
    manager = ProofEventManager(
        node_id="Tree-unit",
        run_dir=tmp_path,
    )

    manager.audit({"kind": "workspace_view.projected", "node": "Tree-unit"})

    audit_path = tmp_path / "proof_node_manager_audit.jsonl"
    rows = [
        json.loads(line)
        for line in audit_path.read_text(encoding="utf-8").splitlines()
    ]
    assert rows == [{"kind": "workspace_view.projected", "node": "Tree-unit"}]
    assert manager.events[-1].kind == "workspace_view.projected"
    typed_path = tmp_path / "proof_node_events.jsonl"
    typed_rows = [
        json.loads(line)
        for line in typed_path.read_text(encoding="utf-8").splitlines()
    ]
    assert typed_rows[-1]["kind"] == "workspace_view.projected"
    assert typed_rows[-1]["node_id"] == "Tree-unit"


def test_proof_event_manager_persists_typed_event_log(tmp_path: Path) -> None:
    manager = ProofEventManager(node_id="Tree-unit", run_dir=tmp_path)

    manager.record_intent_received(
        intent="probe_tactic",
        payload={"tactic": "wp."},
        state_version=4,
    )
    manager.record_route_event({"intent": "probe_tactic", "accepted": True})

    rows = [
        json.loads(line)
        for line in (tmp_path / "proof_node_events.jsonl").read_text(
            encoding="utf-8"
        ).splitlines()
    ]
    assert [row["kind"] for row in rows] == ["intent_received", "route_event"]
    assert [row["sequence"] for row in rows] == [1, 2]
    assert rows[1]["route_event"]["turn_index"] == 1


def test_proof_event_manager_loads_node_events_from_existing_log(tmp_path: Path) -> None:
    path = tmp_path / "proof_node_events.jsonl"
    path.write_text(
        "\n".join([
            json.dumps({
                "kind": "intent_received",
                "node_id": "Other",
                "sequence": 1,
                "intent": "probe_tactic",
            }),
            json.dumps({
                "kind": "route_event",
                "node_id": "Tree-unit",
                "sequence": 1,
                "route_event": {
                    "intent": "commit_tactic",
                    "turn_index": 1,
                },
            }),
        ]) + "\n",
        encoding="utf-8",
    )

    manager = ProofEventManager(node_id="Tree-unit", run_dir=tmp_path)
    manager.record_intent_received(intent="finish")

    assert [event["kind"] for event in manager.recent_events()] == [
        "route_event",
        "intent_received",
    ]
    assert manager.route_event_facts == [
        {"intent": "commit_tactic", "turn_index": 1}
    ]
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
    ]
    assert rows[-1]["sequence"] == 2
    assert rows[-1]["node_id"] == "Tree-unit"


def test_proof_event_manager_records_typed_intents() -> None:
    manager = ProofEventManager(node_id="Tree-unit")

    manager.record_intent_received(
        intent="probe_tactic",
        payload={"tactic": "wp."},
        state_version=4,
    )
    manager.record_malformed_intent(
        error="not json",
        malformed_count=2,
        state_version=4,
    )

    rows = manager.recent_events()
    assert rows[0]["kind"] == "intent_received"
    assert rows[0]["intent"] == "probe_tactic"
    assert rows[0]["payload"] == {"tactic": "wp."}
    assert rows[1]["kind"] == "malformed_intent"
    assert rows[1]["metadata"]["malformed_count"] == 2


def test_proof_event_manager_projects_read_only_and_commit_turns() -> None:
    manager = ProofEventManager(node_id="Tree-unit")

    context = manager.record_route_turn(
        intent="tactic_forms",
        payload={"name": "wp"},
        actions=[],
        observation={"status": "ok"},
    )

    assert context["intent"] == "tactic_forms"
    assert context["changed"] is False

    commit = manager.record_route_turn(
        intent="commit_tactic",
        payload={"tactic": "wp."},
        actions=[],
        observation={"execution": {"state_changed": True}},
    )

    assert commit["changed"] is True
