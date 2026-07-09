from __future__ import annotations

from workflow.proof_management import AgentIntent
from workflow.proof_management.health import (
    backend_failure_health_event,
    timeout_health_event,
)


def test_timeout_health_event_marks_mutating_uncertainty() -> None:
    health = timeout_health_event(
        node_id="Tree_0",
        intent=AgentIntent(intent="commit_tactic", payload={"tactic": "wp."}),
        action={
            "label": "commit_tactic",
            "timeout_seconds": 180,
            "mutates_proof_state": True,
        },
        state_version=7,
    )

    assert health.status == "manager_action_timeout"
    assert health.state_version == 7
    assert "proof state may be uncertain" in health.message


def test_backend_failure_health_event_ignores_readonly_non_view_failure() -> None:
    intent = AgentIntent(intent="inspect_context", payload={"topic": "goal_info"})

    assert backend_failure_health_event(
        node_id="Tree_0",
        intent=intent,
        action={"label": "inspect_goal_info", "exit_code": 1},
        state_version=3,
    ) is None

    health = backend_failure_health_event(
        node_id="Tree_0",
        intent=intent,
        action={"label": "agent_view", "exit_code": 1},
        state_version=3,
    )

    assert health is not None
    assert health.status == "manager_backend_failure"
    assert "agent_view" in health.message
