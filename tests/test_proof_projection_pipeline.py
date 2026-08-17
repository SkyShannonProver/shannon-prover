from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from workflow.proof_management.projection import ProofProjectionPipeline
from workflow.proof_state_compiler.managed_goal_view_manager import (
    ManagedGoalViewManager,
)


@dataclass(frozen=True)
class _Snapshot:
    raw_workspace_view: dict[str, Any]
    state_version: int = 7
    session_epoch: int = 2


def _raw_view() -> dict[str, Any]:
    return {
        "schema_version": 3,
        "kind": "prover_workspace_view",
        "ok": True,
        "last_result": {},
        "proof_status": {
            "status": "open",
            "goal_identity_required": True,
            "goal_hash": "goal-hash",
            "remaining_goals": 1,
            "remaining_goals_known": True,
        },
        "current_goal": {"lines": ["goal"]},
    }


def test_current_projection_builds_only_the_managed_goal_envelope() -> None:
    pipeline = ProofProjectionPipeline(
        workspace=ManagedGoalViewManager(),
        surface_profile="l1_goal_projection",
    )

    result = pipeline.project(
        _Snapshot(_raw_view()),
        latest_observation={"kind": "commit", "message": "accepted"},
    )

    assert result.state is None
    assert result.evidence is None
    assert result.view["ok"] is True
    assert result.view["based_on_state_version"] == 7
    assert result.view["session_epoch"] == 2
    assert result.view["last_result"]["kind"] == "commit"
    assert result.view["view_hash"]
    assert result.full_view == result.view


def test_current_projection_rejects_retired_panel_carriers() -> None:
    pipeline = ProofProjectionPipeline(
        workspace=ManagedGoalViewManager(),
        surface_profile="l1_goal_projection",
    )
    raw = _raw_view()
    raw["candidate_moves"] = {"moves": []}

    try:
        pipeline.project(_Snapshot(raw))
    except ValueError as exc:
        assert "candidate_moves" in str(exc)
    else:
        raise AssertionError("retired panel carrier was accepted")
