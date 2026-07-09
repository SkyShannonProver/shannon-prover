from __future__ import annotations

from workflow.proof_management.analyzers.seq_cut import SeqCutAnalyzer
from workflow.proof_management.node_state import ProofNodeState


def _state(
    view: dict,
    *,
    tactics: list[str] | None = None,
    route_event_facts: list[dict] | None = None,
) -> ProofNodeState:
    return ProofNodeState(
        node_id="Tree-unit",
        base_workspace_view=view,
        committed_tactics=list(tactics or []),
        route_event_facts=list(route_event_facts or []),
    )


def _view(**extra) -> dict:
    view = {
        "proof_status": {
            "view_focus": "relational_program",
            "current_layer": "procedure_body",
            "remaining_goals": 3,
        },
        "current_goal": {
            "lines": [
                "Current goal",
                "&1: { x <@ M.f() }",
                "&2: { y <@ N.g() }",
                "post = ={x, y}",
            ],
        },
        "program_frontier": {
            "call_sites": [{"procedure": "M.f"}],
        },
    }
    view.update(extra)
    return view


def test_seq_cut_analyzer_reports_committed_seq_scope() -> None:
    analyzer = SeqCutAnalyzer()
    surface = analyzer.analyze(
        state=_state(
            _view(),
            tactics=["proc.", "seq 2 1 : (P).", "wp."],
            route_event_facts=[{"tactic_head": "wp", "status": "accepted"}],
        )
    )

    assert surface["state"] == "inside_seq_scope"
    assert surface["cut_position"]["left_count"] == 2
    assert surface["cut_position"]["right_count"] == 1
    assert surface["branch_focus"]["latest_event_head"] == "wp"
    assert surface["residual_frontier"]["latest_seq_tactic_index"] == 2
    assert surface["residual_frontier"]["tactics_after_latest_seq"] == 1
    assert "call_site" in surface["obligation_kinds"]
    assert "postcondition" in surface["obligation_kinds"]


def test_seq_cut_analyzer_reports_probe_preview() -> None:
    analyzer = SeqCutAnalyzer()
    surface = analyzer.analyze(
        state=_state(
            _view(
                last_result={
                    "accepted_tactic": "seq 1 1 : (P).",
                    "preview_summary": {"remaining_goals": 4},
                },
            )
        )
    )

    assert surface["state"] == "seq_probe_preview"
    assert surface["seq_candidate_id"].startswith("probe_")
    assert surface["obligation_count"] == 4
    assert surface["cut_position"]["left_count"] == 1
    assert surface["cut_position"]["right_count"] == 1


def test_seq_cut_analyzer_reports_rewound_seq_boundary() -> None:
    analyzer = SeqCutAnalyzer()
    surface = analyzer.analyze(
        state=_state(
            _view(
                last_result={
                    "kind": "checkpoint_rewind",
                    "committed_tactic": "seq 3 2 : (P).",
                    "tactic_index": 5,
                    "undone_tactic_count": 8,
                    "payload": {"checkpoint_id": "cp_saved"},
                },
            ),
            tactics=["proc."],
        )
    )

    assert surface["state"] == "before_rewound_seq_cut"
    assert surface["seq_candidate_id"] == "cp_saved"
    assert surface["restored_boundary"]["rewound_tactic_index"] == 5
    assert surface["restored_boundary"]["undone_tactic_count"] == 8
    assert surface["residual_frontier"]["rewound_seq_tactic_index"] == 5


def test_seq_cut_analyzer_ignores_non_seq_views() -> None:
    analyzer = SeqCutAnalyzer()

    assert analyzer.analyze(
        state=_state({
            "proof_status": {"view_focus": "ambient_logic"},
            "current_goal": {"lines": ["Current goal", "post = true"]},
        })
    ) == {}
