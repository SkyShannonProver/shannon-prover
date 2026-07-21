from __future__ import annotations

from workflow.proof_management.node_state import ProofNodeStateManager


def test_proof_node_state_manager_builds_aggregate_state() -> None:
    manager = ProofNodeStateManager(
        node_id="Tree-unit",
        committed_tactic_reader=lambda: ["proc.", "wp."],
    )

    state = manager.build(
        snapshot=None,
        raw_workspace_view={"current_goal": {"lines": ["g"]}},
        base_workspace_view={"proof_status": {"status": "open"}},
        latest_observation={"kind": "context_result"},
        replay_prefix=["proc."],
        replay_prefix_count=1,
        restore_anchor={"restore_id": "restore_1"},
        route_memories=[{"memory_id": "route_1"}],
        route_event_facts=[{"intent": "tactic_forms"}],
        typed_events=[{"kind": "intent_received"}],
    )

    assert state.committed_tactics == ["proc.", "wp."]
    assert state.replay_prefix == ["proc."]
    assert state.restore_anchor["restore_id"] == "restore_1"
    assert state.route_memories[0]["memory_id"] == "route_1"
    assert state.route_event_facts[0]["intent"] == "tactic_forms"
    assert state.typed_events[0]["kind"] == "intent_received"
