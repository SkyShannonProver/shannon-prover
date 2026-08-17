from __future__ import annotations

import json
from pathlib import Path

import pytest

from workflow.proof_management.event_store import (
    ProofEventManager,
    ProofEventStoreError,
    RESUME_ROUTE_EVENT_SCHEMA_VERSION,
    require_resume_route_event,
    resume_route_event_from_manager_route_event,
)


def _route_event(intent: str, **updates: object) -> dict[str, object]:
    event: dict[str, object] = {
        "intent": intent,
        "outcome_kind": "unknown",
        "proof_state_effect": "unknown",
        "needs_attention": False,
        "accepted": False,
        "rejected": False,
        "changed": False,
    }
    event.update(updates)
    return event


def test_proof_event_manager_records_bounded_route_event_facts() -> None:
    manager = ProofEventManager(
        node_id="Tree-unit",
        route_event_limit=2,
    )

    manager.record_route_event(_route_event("finish"))
    manager.record_route_event(_route_event("commit_tactic"))
    manager.record_route_event(_route_event("undo_to_checkpoint"))

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
        manager.route_event_facts = [{"intent": "finish"}]  # type: ignore[misc]


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
        intent="undo_to_checkpoint",
        payload={},
        state_version=4,
    )
    manager.record_route_event(_route_event(
        "undo_to_checkpoint",
        outcome_kind="control_menu",
        proof_state_effect="unchanged",
    ))

    rows = [
        json.loads(line)
        for line in (tmp_path / "proof_node_events.jsonl").read_text(
            encoding="utf-8"
        ).splitlines()
    ]
    assert [row["kind"] for row in rows] == ["intent_received", "route_event"]
    assert [row["schema_version"] for row in rows] == [1, 1]
    assert [row["sequence"] for row in rows] == [1, 2]
    assert rows[1]["route_event"]["turn_index"] == 1


def test_proof_event_manager_loads_node_events_from_existing_log(tmp_path: Path) -> None:
    path = tmp_path / "proof_node_events.jsonl"
    path.write_text(
        "\n".join([
            json.dumps({
                "schema_version": 1,
                "kind": "intent_received",
                "node_id": "Other",
                "sequence": 1,
                "created_at": "2026-01-01T00:00:00+0000",
                "state_version": 0,
                "intent": "finish",
            }),
            json.dumps({
                "schema_version": 1,
                "kind": "route_event",
                "node_id": "Tree-unit",
                "sequence": 1,
                "created_at": "2026-01-01T00:00:00+0000",
                "state_version": 0,
                "route_event": {
                    "intent": "commit_tactic",
                    "turn_index": 1,
                    "outcome_kind": "accepted",
                    "proof_state_effect": "changed",
                    "needs_attention": False,
                    "accepted": True,
                    "rejected": False,
                    "changed": True,
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
        {
            "intent": "commit_tactic",
            "turn_index": 1,
            "outcome_kind": "accepted",
            "proof_state_effect": "changed",
            "needs_attention": False,
            "accepted": True,
            "rejected": False,
            "changed": True,
        }
    ]
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
    ]
    assert rows[-1]["sequence"] == 2
    assert rows[-1]["node_id"] == "Tree-unit"


@pytest.mark.parametrize("missing_flag", ["accepted", "rejected", "changed"])
def test_persisted_route_event_requires_all_verdict_flags(
    tmp_path: Path,
    missing_flag: str,
) -> None:
    route_event = {
        "intent": "commit_tactic",
        "turn_index": 1,
        "outcome_kind": "accepted",
        "proof_state_effect": "changed",
        "needs_attention": False,
        "accepted": True,
        "rejected": False,
        "changed": True,
    }
    route_event.pop(missing_flag)
    (tmp_path / "proof_node_events.jsonl").write_text(
        json.dumps({
            "schema_version": 1,
            "kind": "route_event",
            "node_id": "Tree-unit",
            "sequence": 1,
            "created_at": "2026-01-01T00:00:00+0000",
            "state_version": 0,
            "route_event": route_event,
        }) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(
        ProofEventStoreError,
        match=rf"route_event\.{missing_flag} is required",
    ):
        ProofEventManager(node_id="Tree-unit", run_dir=tmp_path)


@pytest.mark.parametrize(
    "updates",
    [
        {"accepted": True, "rejected": True},
        {"accepted": False, "rejected": True, "changed": True},
        {"accepted": False, "rejected": False, "changed": True},
        {"status": "rejected"},
    ],
)
def test_persisted_route_event_rejects_contradictory_verdicts(
    tmp_path: Path,
    updates: dict[str, object],
) -> None:
    event = _route_event("commit_tactic", **updates)
    manager = ProofEventManager(node_id="Tree-unit", run_dir=tmp_path)

    with pytest.raises(ValueError):
        manager.record_route_event(event)

    assert manager.route_event_facts == []


@pytest.mark.parametrize(
    (
        "outcome_kind",
        "accepted",
        "rejected",
        "changed",
        "proof_state_effect",
        "needs_attention",
    ),
    [
        ("accepted", True, False, True, "changed", False),
        ("accepted", True, False, False, "unchanged", False),
        ("partial_success", True, False, True, "changed", True),
        ("accepted_unconfirmed", True, False, False, "unknown", False),
        ("read_only", True, False, False, "read_only", False),
        ("rejected", False, True, False, "unchanged", True),
        ("no_progress", False, False, False, "unchanged", True),
        ("backend_error", False, False, False, "unknown", True),
        ("backend_error", False, False, False, "read_only", True),
        ("timeout", False, False, False, "unknown", True),
        ("control_menu", False, False, False, "unchanged", False),
        ("repair", False, False, False, "unchanged", True),
        ("unknown", False, False, False, "unknown", False),
    ],
)
def test_persisted_route_event_accepts_canonical_verdict_shapes(
    outcome_kind: str,
    accepted: bool,
    rejected: bool,
    changed: bool,
    proof_state_effect: str,
    needs_attention: bool,
) -> None:
    manager = ProofEventManager(node_id="Tree-unit")

    recorded = manager.record_route_event(_route_event(
        "commit_tactic",
        accepted=accepted,
        rejected=rejected,
        changed=changed,
        outcome_kind=outcome_kind,
        proof_state_effect=proof_state_effect,
        needs_attention=needs_attention,
    ))

    assert recorded["outcome_kind"] == outcome_kind
    assert recorded["accepted"] is accepted
    assert recorded["rejected"] is rejected
    assert recorded["changed"] is changed


@pytest.mark.parametrize(
    "updates",
    [
        {
            "accepted": True,
            "outcome_kind": "rejected",
            "proof_state_effect": "unchanged",
            "needs_attention": True,
        },
        {
            "accepted": True,
            "outcome_kind": "partial_success",
            "proof_state_effect": "changed",
            "needs_attention": True,
        },
        {
            "accepted": True,
            "changed": True,
            "outcome_kind": "accepted_unconfirmed",
            "proof_state_effect": "changed",
        },
        {
            "accepted": True,
            "outcome_kind": "read_only",
            "proof_state_effect": "unknown",
        },
        {
            "rejected": True,
            "outcome_kind": "rejected",
            "proof_state_effect": "read_only",
            "needs_attention": True,
        },
        {
            "accepted": True,
            "outcome_kind": "no_progress",
            "proof_state_effect": "unchanged",
            "needs_attention": True,
        },
        {
            "outcome_kind": "backend_error",
            "proof_state_effect": "changed",
            "needs_attention": True,
        },
        {
            "outcome_kind": "control_menu",
            "proof_state_effect": "unknown",
        },
        {
            "outcome_kind": "repair",
            "proof_state_effect": "read_only",
            "needs_attention": True,
        },
        {
            "outcome_kind": "legacy_unknown",
            "proof_state_effect": "unknown",
        },
        {
            "outcome_kind": "accepted",
            "proof_state_effect": "unchanged",
            "accepted": True,
            "needs_attention": True,
        },
    ],
)
def test_persisted_route_event_rejects_cross_field_verdict_contradictions(
    updates: dict[str, object],
) -> None:
    manager = ProofEventManager(node_id="Tree-unit")

    with pytest.raises(ValueError):
        manager.record_route_event(_route_event("commit_tactic", **updates))

    assert manager.route_event_facts == []


@pytest.mark.parametrize(
    ("field_name", "bad_value"),
    [
        ("tactic", 7),
        ("status", "accepted"),
        ("needs_attention", "true"),
        ("unexpected", "legacy"),
    ],
)
def test_persisted_route_event_rejects_untyped_or_unknown_fields(
    tmp_path: Path,
    field_name: str,
    bad_value: object,
) -> None:
    event = _route_event("commit_tactic")
    event[field_name] = bad_value
    manager = ProofEventManager(node_id="Tree-unit", run_dir=tmp_path)

    with pytest.raises(ValueError):
        manager.record_route_event(event)

    assert manager.route_event_facts == []


@pytest.mark.parametrize(
    ("field_name", "bad_value"),
    [
        ("sequence", "1"),
        ("sequence", True),
        ("sequence", 0),
        ("state_version", "0"),
        ("state_version", True),
        ("state_version", -1),
    ],
)
def test_proof_event_manager_rejects_non_integer_event_coordinates(
    tmp_path: Path,
    field_name: str,
    bad_value: object,
) -> None:
    row = {
        "schema_version": 1,
        "kind": "intent_received",
        "node_id": "Tree-unit",
        "sequence": 1,
        "created_at": "2026-01-01T00:00:00+0000",
        "state_version": 0,
        "intent": "finish",
    }
    row[field_name] = bad_value
    (tmp_path / "proof_node_events.jsonl").write_text(
        json.dumps(row) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ProofEventStoreError, match="invalid current proof event"):
        ProofEventManager(node_id="Tree-unit", run_dir=tmp_path)


def test_proof_event_manager_rejects_sequence_gaps(tmp_path: Path) -> None:
    rows = [
        {
            "schema_version": 1,
            "kind": "intent_received",
            "node_id": "Tree-unit",
            "sequence": sequence,
            "created_at": f"2026-01-01T00:00:0{sequence}+0000",
            "state_version": 0,
            "intent": "finish",
        }
        for sequence in (1, 3)
    ]
    (tmp_path / "proof_node_events.jsonl").write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ProofEventStoreError, match="non-contiguous"):
        ProofEventManager(node_id="Tree-unit", run_dir=tmp_path)


def test_proof_event_manager_write_failure_does_not_advance_memory(
    tmp_path: Path,
) -> None:
    blocked_run_dir = tmp_path / "not-a-directory"
    blocked_run_dir.write_text("occupied", encoding="utf-8")
    manager = ProofEventManager(node_id="Tree-unit", run_dir=blocked_run_dir)

    with pytest.raises(ProofEventStoreError, match="failed to write current"):
        manager.record_intent_received(intent="finish")

    assert manager.events == []


def test_proof_event_manager_records_typed_intents() -> None:
    manager = ProofEventManager(node_id="Tree-unit")

    manager.record_intent_received(
        intent="undo_to_checkpoint",
        payload={},
        state_version=4,
    )
    manager.record_malformed_intent(
        error="not json",
        malformed_count=2,
        state_version=4,
    )

    rows = manager.recent_events()
    assert rows[0]["kind"] == "intent_received"
    assert rows[0]["intent"] == "undo_to_checkpoint"
    assert "payload" not in rows[0]
    assert rows[1]["kind"] == "malformed_intent"
    assert rows[1]["metadata"]["malformed_count"] == 2


def test_proof_event_manager_projects_control_and_commit_turns() -> None:
    manager = ProofEventManager(node_id="Tree-unit")

    control = manager.record_route_turn(
        intent="undo_to_checkpoint",
        payload={},
        actions=[{
            "label": "checkpoint_menu",
            "outcome_kind": "control_menu",
            "proof_state_effect": "unchanged",
            "proof_state_changed": False,
            "needs_attention": False,
        }],
        observation={},
    )

    assert control["intent"] == "undo_to_checkpoint"
    assert control["accepted"] is False
    assert control["rejected"] is False
    assert control["changed"] is False
    assert control["outcome_kind"] == "control_menu"
    assert control["proof_state_effect"] == "unchanged"

    commit = manager.record_route_turn(
        intent="commit_tactic",
        payload={"tactic": "wp."},
        actions=[{
            "label": "commit_tactic",
            "outcome_kind": "accepted",
            "proof_state_effect": "changed",
            "proof_state_changed": True,
            "needs_attention": False,
            "agent_observation": {"result": "prose says rejected"},
        }],
        observation={
            "status": "failed",
            "execution": {"state_changed": False},
        },
    )

    assert "topic" not in commit
    assert commit["accepted"] is True
    assert commit["rejected"] is False
    assert commit["changed"] is True


def test_route_turn_does_not_infer_outcome_from_nested_or_prose_fields() -> None:
    manager = ProofEventManager(node_id="Tree-unit")

    event = manager.record_route_turn(
        intent="commit_tactic",
        payload={"tactic": "smt()."},
        actions=[{
            "label": "commit_tactic",
            "agent_observation": {
                "result": "accepted and state changed",
                "execution": {"state_changed": True},
            },
        }],
        observation={
            "status": "accepted",
            "execution": {
                "state_changed": True,
                "history_committed": True,
            },
        },
    )

    assert event["outcome_kind"] == "unknown"
    assert event["proof_state_effect"] == "unknown"
    assert event["accepted"] is False
    assert event["rejected"] is False
    assert event["changed"] is False


def test_route_turn_rejection_comes_only_from_typed_action_outcome() -> None:
    manager = ProofEventManager(node_id="Tree-unit")

    event = manager.record_route_turn(
        intent="commit_tactic",
        payload={"tactic": "smt()."},
        actions=[{
            "label": "commit_tactic",
            "outcome_kind": "rejected",
            "proof_state_effect": "unchanged",
            "proof_state_changed": False,
            "needs_attention": True,
            "agent_observation": {"result": "accepted"},
        }],
        observation={
            "status": "ok",
            "execution": {"state_changed": True},
        },
    )

    assert event["accepted"] is False
    assert event["rejected"] is True
    assert event["changed"] is False
    assert event["outcome_kind"] == "rejected"


def test_route_turn_preserves_no_progress_as_distinct_typed_outcome() -> None:
    manager = ProofEventManager(node_id="Tree-unit")

    event = manager.record_route_turn(
        intent="commit_tactic",
        payload={"tactic": "smt()."},
        actions=[{
            "label": "commit_tactic",
            "outcome_kind": "no_progress",
            "proof_state_effect": "unchanged",
            "proof_state_changed": False,
            "needs_attention": True,
        }],
        observation={},
    )

    assert event["accepted"] is False
    assert event["rejected"] is False
    assert event["outcome_kind"] == "no_progress"
    assert event["needs_attention"] is True
    assert manager.events[-1].status == "no_progress"


def test_proof_event_manager_seeds_current_resume_route_event() -> None:
    manager = ProofEventManager(node_id="Tree-unit")

    manager.seed_resume_route_events([{
        "kind": "resume_route_event",
        "schema_version": RESUME_ROUTE_EVENT_SCHEMA_VERSION,
        "intent": "commit_tactic",
        "tactic": "wp.",
        "tactic_head": "wp",
        "outcome_kind": "accepted",
        "proof_state_effect": "changed",
        "needs_attention": False,
        "accepted": True,
        "rejected": False,
        "changed": True,
    }])

    assert manager.route_event_facts == [{
        "kind": "resume_route_event",
        "schema_version": RESUME_ROUTE_EVENT_SCHEMA_VERSION,
        "intent": "commit_tactic",
        "tactic": "wp.",
        "tactic_head": "wp",
        "outcome_kind": "accepted",
        "proof_state_effect": "changed",
        "needs_attention": False,
        "accepted": True,
        "rejected": False,
        "changed": True,
        "resume_source": "resume_capsule",
        "turn_index": 1,
    }]


def test_resume_route_event_rejects_retired_context_fields() -> None:
    event = {
        "kind": "resume_route_event",
        "schema_version": RESUME_ROUTE_EVENT_SCHEMA_VERSION,
        "intent": "undo_to_checkpoint",
        "topic": "tactic_forms",
        "outcome_kind": "control_menu",
        "proof_state_effect": "unchanged",
        "needs_attention": False,
        "accepted": False,
        "rejected": False,
        "changed": False,
        "error_summary": "",
    }

    with pytest.raises(ValueError, match="unknown topic"):
        require_resume_route_event(event)


def test_resume_projection_keeps_typed_verdict_and_drops_live_only_fields() -> None:
    event = {
        "intent": "commit_tactic",
        "tactic": "wp.",
        "tactic_head": "wp",
        "accepted": False,
        "rejected": True,
        "changed": False,
        "error_summary": "cannot prove goal",
        "turn_index": 7,
        "outcome_kind": "rejected",
        "proof_state_effect": "unchanged",
        "needs_attention": True,
    }

    projected = resume_route_event_from_manager_route_event(event)

    assert projected == {
        "kind": "resume_route_event",
        "schema_version": RESUME_ROUTE_EVENT_SCHEMA_VERSION,
        "outcome_kind": "rejected",
        "proof_state_effect": "unchanged",
        "needs_attention": True,
        "intent": "commit_tactic",
        "tactic": "wp.",
        "tactic_head": "wp",
        "accepted": False,
        "rejected": True,
        "changed": False,
        "error_summary": "cannot prove goal",
    }


def test_resume_projection_rejects_retired_status_alias() -> None:
    event = {
        "intent": "commit_tactic",
        "outcome_kind": "accepted",
        "proof_state_effect": "changed",
        "needs_attention": False,
        "accepted": True,
        "rejected": False,
        "changed": True,
        "status": "accepted",
    }

    with pytest.raises(ValueError, match=r"status is retired"):
        resume_route_event_from_manager_route_event(event)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda event: event.update({"intent": 7}),
        lambda event: event.update({"accepted": "true"}),
        lambda event: event.pop("outcome_kind"),
        lambda event: event.pop("proof_state_effect"),
        lambda event: event.pop("needs_attention"),
        lambda event: event.update({"legacy_payload": {}}),
        lambda event: event.update({"topic": "rewrite_candidates"}),
        lambda event: event.update({"rejected": True}),
        lambda event: event.update({"accepted": False, "changed": True}),
        lambda event: event.update({"outcome_kind": "legacy_unknown"}),
        lambda event: event.update({"proof_state_effect": "unchanged"}),
        lambda event: event.update({"needs_attention": True}),
        lambda event: event.update({"status": "rejected"}),
    ],
)
def test_resume_route_event_rejects_coercions_unknowns_and_contradictions(
    mutate,
) -> None:
    event = {
        "kind": "resume_route_event",
        "schema_version": RESUME_ROUTE_EVENT_SCHEMA_VERSION,
        "intent": "commit_tactic",
        "tactic": "wp.",
        "tactic_head": "wp",
        "outcome_kind": "accepted",
        "proof_state_effect": "changed",
        "needs_attention": False,
        "accepted": True,
        "rejected": False,
        "changed": True,
    }
    mutate(event)

    with pytest.raises(ValueError):
        require_resume_route_event(event)


def test_resume_route_event_seed_validates_the_batch_before_recording() -> None:
    manager = ProofEventManager(node_id="Tree-unit")
    valid = {
        "kind": "resume_route_event",
        "schema_version": RESUME_ROUTE_EVENT_SCHEMA_VERSION,
        "intent": "commit_tactic",
        "tactic": "wp.",
        "tactic_head": "wp",
        "outcome_kind": "accepted",
        "proof_state_effect": "changed",
        "needs_attention": False,
        "accepted": True,
        "rejected": False,
        "changed": True,
    }
    invalid = {**valid, "changed": "true"}

    with pytest.raises(ValueError, match=r"resume_route_events\[1\]\.changed"):
        manager.seed_resume_route_events([valid, invalid])

    assert manager.route_event_facts == []


@pytest.mark.parametrize(
    "field_name",
    ["outcome_kind", "proof_state_effect", "needs_attention"],
)
def test_resume_route_event_requires_canonical_outcome_fields(
    field_name: str,
) -> None:
    event = {
        "kind": "resume_route_event",
        "schema_version": RESUME_ROUTE_EVENT_SCHEMA_VERSION,
        "intent": "commit_tactic",
        "outcome_kind": "unknown",
        "proof_state_effect": "unknown",
        "needs_attention": False,
        "accepted": False,
        "rejected": False,
        "changed": False,
    }
    event.pop(field_name)

    with pytest.raises(ValueError, match=field_name):
        require_resume_route_event(event)


@pytest.mark.parametrize("schema_version", [None, "2", True, 0, 1, 3])
def test_proof_event_manager_rejects_non_v2_resume_route_events(
    schema_version,
) -> None:
    manager = ProofEventManager(node_id="Tree-unit")
    event = {
        "kind": "resume_route_event",
        "intent": "commit_tactic",
        "tactic": "wp.",
        "outcome_kind": "unknown",
        "proof_state_effect": "unknown",
        "needs_attention": False,
        "accepted": False,
        "rejected": False,
        "changed": False,
    }
    if schema_version is not None:
        event["schema_version"] = schema_version

    with pytest.raises(ValueError, match=r"resume_route_events\[0\]"):
        manager.seed_resume_route_events([event])

    assert manager.route_event_facts == []


@pytest.mark.parametrize(
    ("field_name", "bad_value"),
    [
        ("accepted", "false"),
        ("rejected", 0),
        ("changed", None),
        ("needs_attention", "false"),
    ],
)
def test_proof_event_manager_rejects_non_boolean_resume_route_flags(
    field_name: str,
    bad_value: object,
) -> None:
    manager = ProofEventManager(node_id="Tree-unit")
    event = {
        "kind": "resume_route_event",
        "schema_version": RESUME_ROUTE_EVENT_SCHEMA_VERSION,
        "intent": "commit_tactic",
        "tactic": "wp.",
        "outcome_kind": "unknown",
        "proof_state_effect": "unknown",
        "needs_attention": False,
        "accepted": False,
        "rejected": False,
        "changed": False,
    }
    event[field_name] = bad_value

    with pytest.raises(ValueError, match=field_name):
        manager.seed_resume_route_events([event])

    assert manager.route_event_facts == []


@pytest.mark.parametrize("missing_flag", ["accepted", "rejected", "changed"])
def test_proof_event_manager_requires_all_resume_route_flags(
    missing_flag: str,
) -> None:
    manager = ProofEventManager(node_id="Tree-unit")
    event = {
        "kind": "resume_route_event",
        "schema_version": RESUME_ROUTE_EVENT_SCHEMA_VERSION,
        "intent": "commit_tactic",
        "tactic": "wp.",
        "outcome_kind": "unknown",
        "proof_state_effect": "unknown",
        "needs_attention": False,
        "accepted": False,
        "rejected": False,
        "changed": False,
    }
    event.pop(missing_flag)

    with pytest.raises(ValueError, match=missing_flag):
        manager.seed_resume_route_events([event])

    assert manager.route_event_facts == []


@pytest.mark.parametrize("schema_version", [None, "1", True, 0, 2])
def test_proof_event_manager_rejects_non_current_typed_event_logs(
    tmp_path: Path,
    schema_version: object,
) -> None:
    row = {
        "kind": "route_event",
        "node_id": "Tree-unit",
        "sequence": 1,
        "created_at": "2026-01-01T00:00:00+0000",
        "state_version": 0,
        "route_event": {
            "intent": "commit_tactic",
            "turn_index": 1,
        },
    }
    if schema_version is not None:
        row["schema_version"] = schema_version
    (tmp_path / "proof_node_events.jsonl").write_text(
        json.dumps(row) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ProofEventStoreError, match="invalid current proof event"):
        ProofEventManager(node_id="Tree-unit", run_dir=tmp_path)


def test_proof_event_manager_does_not_load_legacy_node_alias(tmp_path: Path) -> None:
    (tmp_path / "proof_node_events.jsonl").write_text(
        json.dumps({
            "schema_version": 1,
            "kind": "route_event",
            "node": "Tree-unit",
            "sequence": 1,
            "created_at": "2026-01-01T00:00:00+0000",
            "state_version": 0,
            "route_event": {
                "intent": "commit_tactic",
                "turn_index": 1,
            },
        }) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ProofEventStoreError, match="ProofEvent.node is retired"):
        ProofEventManager(node_id="Tree-unit", run_dir=tmp_path)


@pytest.mark.parametrize("retired_key", ["payload", "intent_payload"])
def test_proof_event_manager_rejects_nested_resume_route_facts(
    retired_key,
) -> None:
    manager = ProofEventManager(node_id="Tree-unit")
    nested = {
        "kind": "resume_route_event",
        "schema_version": RESUME_ROUTE_EVENT_SCHEMA_VERSION,
        "intent": "commit_tactic",
        retired_key: {
            "intent": "commit_tactic",
            "payload": {"tactic": "wp."},
            "tactic": "wp.",
        },
    }

    with pytest.raises(ValueError, match=r"resume_route_events\[0\]"):
        manager.seed_resume_route_events([nested])

    assert manager.route_event_facts == []
