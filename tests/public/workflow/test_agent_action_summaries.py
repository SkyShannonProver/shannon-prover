"""Manager actions the agent sees in its turn summary."""
from __future__ import annotations

from workflow.node.agent_prompt_render import _agent_safe_action_summaries


def test_daemon_undo_fallback_is_not_shown_to_the_agent() -> None:
    actions = [
        {
            "label": "daemon_undo_fallback",
            "agent_observation": {
                "label": "daemon_undo_fallback",
                "result": "The session could not be rewound in place.",
            },
        },
        {
            "label": "undo_to_checkpoint",
            "agent_observation": {"result": "Rewound to checkpoint 3."},
        },
        {"label": "managed_goal_view", "agent_observation": {"result": "goal"}},
    ]

    summaries = _agent_safe_action_summaries(actions)

    assert [summary["action"] for summary in summaries] == ["checkpoint rewind"]
