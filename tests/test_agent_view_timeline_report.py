from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from workflow.validation.agent_view_timeline_report import (  # noqa: E402
    RunSpec,
    _result_summary,
    _state_summary,
    build_report,
    classify_compiler_action_usage,
    render_markdown,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )


def _workspace_view(*, remaining: int, goal_chars: int, goal_type: str = "pRHL") -> dict:
    return {
        "last_result": {},
        "proof_status": {
            "status": "open",
            "remaining_goals": remaining,
            "goal_type": goal_type,
            "current_layer": "call_site",
            "view_focus": "seq_cut",
        },
        "current_goal": {
            "lines": ["x = y"],
            "char_count": goal_chars,
            "goal_type": goal_type,
            "view_focus": "seq_cut",
        },
    }


def _compiler_action_view(tactic: str) -> dict:
    submit = json.dumps(
        {"intent": "commit_tactic", "payload": {"tactic": tactic}},
        separators=(",", ":"),
    )
    return {
        "surface_turn": {
            "compiler_markdown": (
                "## Optional checked fact available\n\n"
                "EasyCrypt checked this exact local action:\n"
                f"```json\n{submit}\n```"
            ),
        },
    }


def test_compiler_action_usage_is_exact_refined_or_ignored() -> None:
    view = _compiler_action_view("call (Alossless_F (<: D1(O).O) _).")

    exact = classify_compiler_action_usage(
        view,
        {
            "intent": "commit_tactic",
            "payload": {"tactic": "call (Alossless_F (<: D1(O).O) _)."},
        },
        accepted=True,
    )
    refined = classify_compiler_action_usage(
        view,
        {
            "intent": "commit_tactic",
            "payload": {"tactic": "call (Alossless_F (<: D1(O).O) hDO)."},
        },
        accepted=True,
    )
    rejected = classify_compiler_action_usage(
        view,
        {
            "intent": "commit_tactic",
            "payload": {
                "tactic": "call (Alossless_F (<: D1(O).O) (by islossless))."
            },
        },
        accepted=False,
    )
    ignored = classify_compiler_action_usage(
        view,
        {"intent": "commit_tactic", "payload": {"tactic": "wp."}},
        accepted=True,
    )

    assert exact["status"] == "exact_accepted"
    assert refined["status"] == "refined_accepted"
    assert rejected["status"] == "refined_rejected"
    assert ignored["status"] == "ignored"


def test_compiler_action_usage_recovers_archived_d1_r4_refinement() -> None:
    fixture = json.loads((
        ROOT
        / "tests"
        / "fixtures"
        / "agent_view_timeline"
        / "d1_r4_refinement.json"
    ).read_text())
    decision_view = fixture["decision_view"]
    result_view = fixture["result_view"]
    submitted = result_view["last_result"]

    usage = classify_compiler_action_usage(
        decision_view,
        {
            "intent": submitted["intent"],
            "payload": submitted["payload"],
        },
        accepted=(
            result_view["surface_turn"]["turn_outcome"]["outcome_kind"]
            == "accepted"
        ),
    )

    assert usage == {
        "offered_action_count": 1,
        "matched_action_index": 0,
        "status": "refined_accepted",
    }


def test_current_v3_status_and_accepted_finish_are_not_reported_as_unknown() -> None:
    view = {
        "proof_status": {
            "status": "session_closed_pending_verification",
            "remaining_goals": 0,
        },
        "current_goal": {},
    }

    assert _state_summary(view) == (
        "session_closed_pending_verification, 0 goals, goal 0 chars"
    )
    assert _result_summary(
        intent={"intent": "finish", "payload": {}},
        ok=True,
        manager_actions=[{
            "label": "finish",
            "agent_observation": {"kind": "finish_accepted"},
        }],
    ) == "finish accepted"


def test_agent_view_timeline_report_renders_action_time_and_view_links(tmp_path: Path) -> None:
    run_dir = tmp_path / "2026-05-12_0000_step3" / "iteration_1"
    node_dir = run_dir / "node_memory" / "Tree_0_0"
    _write_jsonl(node_dir / "timeline.jsonl", [
        {
            "kind": "bootstrap",
            "node": "Tree-0.0",
            "time": "2026-05-12T00:00:01Z",
        },
        {
            "kind": "manager_turn",
            "node": "Tree-0.0",
            "turn": 1,
            "time": "2026-05-12T00:00:10Z",
                "intent": {
                    "intent": "undo_to_checkpoint",
                    "payload": {"checkpoint_id": "before_call"},
                },
                "manager_actions": [{"action": "checkpoint rewind", "timing": "1.5 s"}],
            "ok": True,
        },
        {
            "kind": "manager_turn",
            "node": "Tree-0.0",
            "turn": 2,
            "time": "2026-05-12T00:00:25Z",
            "intent": {
                "intent": "commit_tactic",
                "payload": {"tactic": "byequiv => //."},
            },
            "manager_actions": [{"action": "tactic commit", "timing": "250 ms"}],
            "ok": True,
        },
    ])
    _write_json(
        node_dir / "manager_results" / "turn_001.json",
        {
            "turn": 1,
            "handled_intent": {
                "intent": "undo_to_checkpoint",
                "payload": {"checkpoint_id": "before_call"},
            },
            "ok": True,
            "manager_actions": [{"action": "checkpoint rewind", "timing": "1.5 s"}],
        },
    )
    _write_json(
        node_dir / "manager_results" / "turn_002.json",
        {
            "turn": 2,
            "handled_intent": {
                "intent": "commit_tactic",
                "payload": {"tactic": "byequiv => //."},
            },
            "ok": True,
            "manager_actions": [{"action": "tactic commit", "timing": "250 ms"}],
        },
    )
    _write_json(node_dir / "workspace_views" / "turn_001.json", _workspace_view(remaining=1, goal_chars=284))
    _write_json(node_dir / "workspace_views" / "turn_002.json", _workspace_view(remaining=1, goal_chars=351))

    report = build_report([RunSpec(label="unit run", path=run_dir)])
    rows = report["runs"][0]["rows"]
    assert rows[0]["view_id"] == "T0.0-1"
    assert rows[0]["action_time"] == "+00:00"
    assert rows[1]["action_time"] == "+00:16"
    assert rows[1]["agent_think"] == "14.8 s"
    assert rows[0]["intent_summary"] == "undo_to_checkpoint"
    assert rows[0]["decision_state_summary"] == "initial handoff (not persisted)"
    assert rows[1]["decision_state_summary"] == "pRHL / call_site / seq_cut, 1 goal, goal 284 chars"
    assert rows[1]["result_state_summary"] == "pRHL / call_site / seq_cut, 1 goal, goal 351 chars"
    assert rows[0]["result_summary"] == "checkpoint rewind selected"
    assert rows[0]["manager_seconds"] == 1.5
    assert rows[1]["manager_seconds"] == 0.25
    assert rows[1]["manager_time"] == "250 ms"

    markdown = render_markdown(report, quality_notes={"unit run:T0.0-1": "清楚"})
    assert "| T0.0-1 | +00:00 |  | 1.5 s | initial handoff | undo_to_checkpoint |" in markdown
    assert "| T0.0-2 | +00:16 | 14.8 s | 250 ms | [turn_001.json](" in markdown
    assert "commit byequiv=>// | pRHL / call_site / seq_cut, 1 goal, goal 284 chars | accepted commit |" in markdown
    assert "[turn_001.json](" in markdown
    assert "清楚" in markdown
    assert "待人工评估" not in markdown


def test_agent_view_timeline_report_can_sort_chronologically_across_nodes(tmp_path: Path) -> None:
    run_dir = tmp_path / "run" / "iteration_1"
    for node_name, node_id, turn_time in (
        ("Tree_0_1", "Tree-0.1", "2026-05-12T00:00:20Z"),
        ("Tree_0_0", "Tree-0.0", "2026-05-12T00:00:10Z"),
    ):
        node_dir = run_dir / "node_memory" / node_name
        _write_jsonl(node_dir / "timeline.jsonl", [{
            "kind": "manager_turn",
            "node": node_id,
            "turn": 1,
            "time": turn_time,
            "intent": {"intent": "goal_info", "payload": {}},
            "manager_actions": [{"action": "goal info", "timing": "10 ms"}],
        }])
        _write_json(
            node_dir / "workspace_views" / "turn_001.json",
            _workspace_view(remaining=1, goal_chars=100, goal_type="probability"),
        )

    grouped = build_report([RunSpec(label="run", path=run_dir)])
    assert [row["view_id"] for row in grouped["runs"][0]["rows"]] == ["T0.0-1", "T0.1-1"]

    chronological = build_report([RunSpec(label="run", path=run_dir)], chronological=True)
    assert [row["view_id"] for row in chronological["runs"][0]["rows"]] == ["T0.0-1", "T0.1-1"]
    assert chronological["runs"][0]["rows"][1]["action_time"] == "+00:10"


def test_agent_view_timeline_report_marks_handled_commit_rejection(tmp_path: Path) -> None:
    run_dir = tmp_path / "run" / "iteration_1"
    node_dir = run_dir / "node_memory" / "Tree_0_0"
    _write_jsonl(node_dir / "timeline.jsonl", [{
        "kind": "manager_turn",
        "node": "Tree-0.0",
        "turn": 1,
        "time": "2026-05-12T00:00:10Z",
        "intent": {
            "intent": "commit_tactic",
            "payload": {"tactic": "move=> H."},
        },
        "manager_actions": [{
            "action": "tactic commit",
            "outcome": (
                "EasyCrypt rejected the committed tactic. "
                "The committed proof state was not changed."
            ),
            "timing": "2.4 s",
        }],
        "ok": True,
    }])
    _write_json(
        node_dir / "manager_results" / "turn_001.json",
        {
            "turn": 1,
            "handled_intent": {
                "intent": "commit_tactic",
                "payload": {"tactic": "move=> H."},
            },
            "ok": True,
            "manager_actions": [{
                "action": "tactic commit",
                "outcome": (
                    "EasyCrypt rejected the committed tactic. "
                    "The committed proof state was not changed."
                ),
                "timing": "2.4 s",
            }],
        },
    )
    _write_json(node_dir / "workspace_views" / "turn_001.json", _workspace_view(remaining=1, goal_chars=100))

    report = build_report([RunSpec(label="unit run", path=run_dir)])

    assert report["runs"][0]["rows"][0]["result_summary"] == (
        "rejected commit: manager reported rejection"
    )
