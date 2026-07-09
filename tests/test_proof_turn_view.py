from __future__ import annotations

from workflow.proof_management import AgentIntent
from workflow.proof_management.turn_view import (
    clean_manager_actions,
    intent_effect,
    intent_payload_surface,
    latest_observation_for_view,
    render_observation_view,
    selection_menu_action,
    snapshot_surface,
    view_with_latest_observation,
)


def test_latest_observation_uses_first_agent_observation() -> None:
    intent = AgentIntent("probe_tactic", {"tactic": "wp.", "node_id": "hidden"})
    observation = latest_observation_for_view(
        intent,
        [
            {"label": "agent_view", "agent_observation": {"result": "skip"}},
            {"label": "probe_tactic", "agent_observation": {"result": "accepted"}},
        ],
    )

    assert observation == {
        "intent": "probe_tactic",
        "payload": {"tactic": "wp."},
        "result": "accepted",
    }


def test_latest_observation_has_readonly_fallback_effect() -> None:
    intent = AgentIntent("inspect_context", {"topic": "goal_info"})
    observation = latest_observation_for_view(intent, [])

    assert observation["intent"] == "inspect_context"
    assert observation["payload"] == {"topic": "goal_info"}
    assert "read-only" in observation["effect"]


def test_view_with_latest_observation_replaces_stale_last_result() -> None:
    view = view_with_latest_observation(
        {"last_result": {"result": "old"}, "current_goal": {"lines": ["G"]}},
        {"result": "new"},
    )

    assert view["last_result"] == {"result": "new"}
    assert view["current_goal"]["lines"] == ["G"]


def test_selection_menu_action_is_non_backend_observation() -> None:
    action = selection_menu_action("checkpoint_selection", {"kind": "menu"})

    assert action["label"] == "checkpoint_selection"
    assert action["proof_state_effect"] == "selection_menu_only"
    assert action["stdout_has_workspace_view"] is False


def test_intent_payload_surface_filters_protocol_metadata() -> None:
    payload = intent_payload_surface(
        AgentIntent("probe_tactic", {"tactic": "wp.", "node_id": "hidden"})
    )

    assert payload == {"tactic": "wp."}
    assert "may change" in intent_effect("commit_tactic")


def test_render_observation_view_projects_snapshot_and_can_overlay() -> None:
    calls: list[dict] = []

    def project(snapshot: object, observation: dict) -> dict:
        calls.append({"snapshot": snapshot, "observation": observation})
        return {"last_result": {"result": "projected"}, "proof_status": {"status": "open"}}

    view = render_observation_view(
        latest_view={"last_result": {"result": "old"}},
        latest_snapshot={"state_version": 1},
        observation={"result": "new"},
        project=project,
        overlay_after_project=True,
    )

    assert calls[0]["observation"] == {"result": "new"}
    assert view["last_result"] == {"result": "new"}
    assert view["proof_status"]["status"] == "open"


def test_snapshot_surface_and_clean_manager_actions_are_defensive() -> None:
    class Snapshot:
        def to_dict(self) -> dict:
            return {"state_version": 2}

    assert snapshot_surface(Snapshot()) == {"state_version": 2}
    assert snapshot_surface(None) == {}
    assert clean_manager_actions([{"label": "ok"}, "not-an-action"]) == [
        {"label": "ok"}
    ]
