from __future__ import annotations

from pathlib import Path

import pytest

from core.easycrypt.session.session_managed_goal_view import build_managed_goal_view
from core.easycrypt.session.session_prover_workspace_schema import (
    PROVER_WORKSPACE_VIEW_KEYS,
    require_prover_workspace_view,
)
from tests.helpers.builders import start_event


GOAL = """Current goal (remaining: 1)

x : int
------------------------------------------------------------------------
x = x
[7|check]>
"""


def _managed_goal_view(tmp_path: Path) -> dict:
    session = tmp_path / ".ec_session_minimal"
    session.mkdir()
    (session / "current.out").write_text(GOAL, encoding="utf-8")
    (session / "history.ec").write_text("", encoding="utf-8")
    start_event(session)
    return build_managed_goal_view(
        session,
        live_tool_name="managed-goal-view",
    )


def test_managed_goal_view_contains_no_legacy_analysis_panels(
    tmp_path: Path,
) -> None:
    view = _managed_goal_view(tmp_path)

    require_prover_workspace_view(view, label="test managed goal view")
    assert view["current_goal"]["lines"] == GOAL.splitlines()
    assert view["proof_status"]["goal_identity_required"] is True
    assert view["proof_status"]["goal_hash"]
    assert "program_frontier" not in view
    assert "application_context" not in view
    assert "facts_and_diagnostics" not in view
    assert "candidate_moves" not in view
    assert "inspect_lookup_handles" not in view
    assert "proof_ir" not in view
    assert "diagnostic_history" not in view


def test_workspace_schema_accepts_only_the_current_top_level_keys(
    tmp_path: Path,
) -> None:
    view = _managed_goal_view(tmp_path)
    projected = {
        **view,
        "latest_observation": {},
        "based_on_state_version": 1,
        "session_epoch": 0,
        "view_hash": "hash",
    }
    assert set(projected) == PROVER_WORKSPACE_VIEW_KEYS
    require_prover_workspace_view(projected, label="projected view")

    for extra in ("next_actions", "unregistered_panel"):
        with pytest.raises(ValueError, match=f"unsupported key\\(s\\): {extra}"):
            require_prover_workspace_view({**view, extra: {}}, label="view")
