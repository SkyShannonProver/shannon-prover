from __future__ import annotations

from dataclasses import dataclass

from workflow.proof_management import AgentIntent, ProofProbeAlternativeManager
from workflow.proof_management.probe_alternatives import (
    probe_alternative_entry,
    workspace_view_with_probe_alternatives,
)


@dataclass(frozen=True)
class _Snapshot:
    session_epoch: int = 1
    state_version: int = 2
    goal_hash: str = "abc"


def test_probe_alternative_entry_marks_tool_error_as_infrastructure() -> None:
    entry = probe_alternative_entry(
        "byequiv => //.",
        {
            "kind": "probe_tool_error",
            "result": "The read-only probe tool failed.",
            "error_summary": "daemon connection unavailable",
        },
    )

    assert entry["probe_result"] == "tool_error"
    assert entry["status"] == "probe_infrastructure_error"
    assert "Do not treat this as evidence" in entry["how_to_use"]


def test_probe_alternative_manager_records_current_state_portfolio() -> None:
    manager = ProofProbeAlternativeManager()
    snapshot = _Snapshot()

    manager.record(
        AgentIntent("probe_tactic", {"tactic": "wp."}),
        snapshot,
        _accepted_probe("wp."),
    )
    manager.record(
        AgentIntent("probe_tactic", {"tactic": "sim."}),
        snapshot,
        {"tactic": "sim.", "error_summary": "cannot infer"},
    )
    manager.record(
        AgentIntent("probe_tactic", {"tactic": "wp."}),
        snapshot,
        _accepted_probe("wp."),
    )

    alternatives = manager.alternatives_for_snapshot(snapshot)
    assert [item["tactic"] for item in alternatives] == ["wp.", "sim."]
    assert alternatives[0]["probe_result"] == "accepted"
    assert alternatives[1]["probe_result"] == "rejected"


def test_workspace_view_with_probe_alternatives_adds_candidate_panel() -> None:
    view = workspace_view_with_probe_alternatives(
        {"candidate_moves": {"moves": []}},
        [{"tactic": "wp.", "probe_result": "accepted"}],
    )

    assert "moves" not in view["candidate_moves"]
    assert view["candidate_moves"]["probe_alternatives"] == [
        {"tactic": "wp.", "probe_result": "accepted"}
    ]


def _accepted_probe(tactic: str) -> dict[str, object]:
    return {
        "tactic": tactic,
        "probe_preview": {
            "tactic": tactic,
            "goal_after_remaining": 1,
            "goal_after_probe": {
                "lines": ["Current goal", "after probe"],
                "char_count": 24,
                "truncated": False,
            },
        },
    }
