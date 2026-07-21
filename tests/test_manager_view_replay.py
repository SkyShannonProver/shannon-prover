from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from workflow.validation import manager_view_replay as mvr


def test_step_parser_supports_plain_and_prefixed_steps() -> None:
    assert mvr._step_from_text("wp.", default_intent="commit_tactic").to_dict() == {
        "intent": "commit_tactic",
        "payload": {"tactic": "wp."},
    }
    assert mvr._step_from_text("inspect:goal_info", default_intent="commit_tactic").to_dict() == {
        "intent": "goal_info",
        "payload": {},
    }


def test_steps_from_tactics_file_accepts_json_steps(tmp_path: Path) -> None:
    path = tmp_path / "steps.json"
    path.write_text(
        json.dumps({
            "steps": [
                {"intent": "inspect_context", "payload": {"topic": "goal_info"}},
                "move=> H.",
            ]
        }),
        encoding="utf-8",
    )

    steps = mvr._steps_from_tactics_file(path, "commit_tactic")

    assert [step.to_dict() for step in steps] == [
        {"intent": "inspect_context", "payload": {"topic": "goal_info"}},
        {"intent": "commit_tactic", "payload": {"tactic": "move=> H."}},
    ]


def test_compare_ignores_volatile_fields_but_reports_view_diff(tmp_path: Path) -> None:
    left = tmp_path / "left" / "workspace_views"
    right = tmp_path / "right" / "workspace_views"
    left.mkdir(parents=True)
    right.mkdir(parents=True)
    # node_id is genuine cross-run noise still scrubbed by _VOLATILE_KEYS.
    # (agent-hidden metadata like view_hash is removed at SAVE time by
    # agent_display_view, so it no longer appears in saved artifacts.)
    base_view = {
        "kind": "prover_workspace_view",
        "node_id": "left",
        "inspect_lookup_handles": {
            "ask_manager_for": [
                {"intent": "inspect_context", "payload": {"topic": "goal_info"}},
            ]
        },
    }
    changed_volatile_only = dict(base_view)
    changed_volatile_only["node_id"] = "right"
    (left / "turn_000_bootstrap.json").write_text(json.dumps(base_view), encoding="utf-8")
    (right / "turn_000_bootstrap.json").write_text(
        json.dumps(changed_volatile_only),
        encoding="utf-8",
    )

    out_a = tmp_path / "diff_a"
    rc = mvr.compare(argparse.Namespace(
        left=str(left.parent),
        right=str(right.parent),
        out_dir=str(out_a),
        strict=False,
        fail_on_diff=False,
    ))

    assert rc == 0
    assert json.loads((out_a / "compare_report.json").read_text())["mismatches"] == 0

    changed_topic = dict(changed_volatile_only)
    changed_topic["inspect_lookup_handles"] = {
        "ask_manager_for": [
            {"intent": "inspect_context", "payload": {"topic": "bridge_lemmas"}},
        ]
    }
    (right / "turn_000_bootstrap.json").write_text(
        json.dumps(changed_topic),
        encoding="utf-8",
    )
    out_b = tmp_path / "diff_b"
    mvr.compare(argparse.Namespace(
        left=str(left.parent),
        right=str(right.parent),
        out_dir=str(out_b),
        strict=False,
        fail_on_diff=False,
    ))

    report = json.loads((out_b / "compare_report.json").read_text())
    assert report["mismatches"] == 1
    assert "bridge_lemmas" in (out_b / "turn_000_bootstrap.diff").read_text()


def _write_view(directory: Path, name: str, view: dict) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_text(json.dumps(view), encoding="utf-8")


def test_compare_detects_top_level_panel_reorder(tmp_path: Path) -> None:
    # A1: same content, only top-level panel ORDER differs.  The diff must be
    # non-empty -- the tool exists to catch exactly this.
    left = tmp_path / "left" / "workspace_views"
    right = tmp_path / "right" / "workspace_views"
    view_a = {
        "current_goal": {"lines": ["G"]},
        "candidate_moves": {"moves": [{"tactic": "wp."}]},
    }
    view_b = {
        "candidate_moves": {"moves": [{"tactic": "wp."}]},
        "current_goal": {"lines": ["G"]},
    }
    _write_view(left, "turn_001_commit_tactic.json", view_a)
    _write_view(right, "turn_001_commit_tactic.json", view_b)

    out = tmp_path / "diff"
    mvr.compare(argparse.Namespace(
        left=str(left.parent),
        right=str(right.parent),
        out_dir=str(out),
        strict=False,
        fail_on_diff=False,
    ))

    report = json.loads((out / "compare_report.json").read_text())
    assert report["mismatches"] == 1
    diff_text = (out / "turn_001_commit_tactic.diff").read_text()
    assert diff_text.strip(), "panel reorder must produce a non-empty diff"


def test_compare_flags_proof_divergence_when_goal_lines_differ(tmp_path: Path) -> None:
    # C2: when current_goal.lines differ, the row is flagged proof_diverged so a
    # divergent proof is not misread as a rendering change.
    left = tmp_path / "left" / "workspace_views"
    right = tmp_path / "right" / "workspace_views"
    _write_view(
        left,
        "turn_001_commit_tactic.json",
        {"current_goal": {"lines": ["pre: a = b"]}, "candidate_moves": {"moves": []}},
    )
    _write_view(
        right,
        "turn_001_commit_tactic.json",
        {"current_goal": {"lines": ["pre: a = c"]}, "candidate_moves": {"moves": []}},
    )

    out = tmp_path / "diff"
    mvr.compare(argparse.Namespace(
        left=str(left.parent),
        right=str(right.parent),
        out_dir=str(out),
        strict=False,
        fail_on_diff=False,
    ))

    report = json.loads((out / "compare_report.json").read_text())
    row = next(r for r in report["views"] if r["view"] == "turn_001_commit_tactic.json")
    assert row["proof_diverged"] is True
    assert "proof_diverged" in (out / "turn_001_commit_tactic.diff").read_text()


def test_compare_does_not_flag_proof_divergence_when_goal_lines_match(tmp_path: Path) -> None:
    # C2 negative: identical goal lines (even with other panel diffs) must NOT
    # be flagged as proof divergence.
    left = tmp_path / "left" / "workspace_views"
    right = tmp_path / "right" / "workspace_views"
    _write_view(
        left,
        "turn_001_commit_tactic.json",
        {"current_goal": {"lines": ["pre: a = b"]}, "candidate_moves": {"moves": [{"tactic": "wp."}]}},
    )
    _write_view(
        right,
        "turn_001_commit_tactic.json",
        {"current_goal": {"lines": ["pre: a = b"]}, "candidate_moves": {"moves": [{"tactic": "sp."}]}},
    )

    out = tmp_path / "diff"
    mvr.compare(argparse.Namespace(
        left=str(left.parent),
        right=str(right.parent),
        out_dir=str(out),
        strict=False,
        fail_on_diff=False,
    ))

    report = json.loads((out / "compare_report.json").read_text())
    row = next(r for r in report["views"] if r["view"] == "turn_001_commit_tactic.json")
    assert row["proof_diverged"] is False
    assert row["different"] is True


def test_saved_artifact_applies_agent_display_view() -> None:
    # C1: the saved per-turn artifact is the REAL agent surface -- hidden
    # metadata (view_hash, schema_version, ...) is removed.  EC-free.
    from core.easycrypt.session_workspace_view_manager import (
        AGENT_HIDDEN_METADATA_FIELDS,
        WorkspaceViewManager,
    )

    raw = {
        "current_goal": {"lines": ["G"]},
        "candidate_moves": {"moves": [{"tactic": "wp."}]},
        "view_hash": "deadbeef",
        "schema_version": 2,
        "session_epoch": 7,
        "based_on_state_version": 3,
        "ok": True,
        "kind": "prover_workspace_view",
    }
    surface = WorkspaceViewManager().agent_display_view(raw)

    for hidden in AGENT_HIDDEN_METADATA_FIELDS:
        assert hidden not in surface, f"{hidden} should be hidden from the agent surface"
    # Proof content survives.
    assert surface["current_goal"]["lines"] == ["G"]
    assert "candidate_moves" in surface


def test_replay_cleanup_closes_manager_repl_once(tmp_path: Path) -> None:
    class FakeRepl:
        def __init__(self) -> None:
            self.calls = 0

        def close(self) -> bool:
            self.calls += 1
            return True

    class FakeManager:
        def __init__(self) -> None:
            self.repl = FakeRepl()

    manager = FakeManager()
    cleanup = mvr._ReplayCleanup(manager, tmp_path)

    assert cleanup.close() is True
    assert cleanup.close() is False
    assert manager.repl.calls == 1
    report = json.loads((tmp_path / "cleanup_report.json").read_text())
    assert report["daemon_session_closed"] is True
    assert report["error"] == ""


def test_prefer_project_root_guard_raises_on_mismatched_workflow(monkeypatch, tmp_path: Path) -> None:
    # B3: if `workflow` is already imported from a different root than the
    # requested --project-root, refuse loudly instead of silently ignoring it.
    import workflow as workflow_pkg

    cwd_root = Path(__file__).resolve().parents[1]
    monkeypatch.setattr(
        workflow_pkg,
        "__path__",
        [str(cwd_root / "workflow")],
        raising=False,
    )

    other_root = tmp_path / "other_checkout"
    with pytest.raises(SystemExit) as excinfo:
        mvr._guard_workflow_already_imported(other_root)
    message = str(excinfo.value)
    assert "--project-root cannot override" in message
    assert "by file path" in message.lower()


def test_prefer_project_root_guard_allows_matching_workflow(monkeypatch, tmp_path: Path) -> None:
    # B3 negative: when `workflow` is imported from the SAME root as the
    # requested --project-root, the guard must not raise.
    import workflow as workflow_pkg

    root = tmp_path / "checkout"
    monkeypatch.setattr(
        workflow_pkg,
        "__path__",
        [str(root / "workflow")],
        raising=False,
    )

    mvr._guard_workflow_already_imported(root)  # must not raise


def _write_run_fixture(tmp_path: Path) -> Path:
    """Build a minimal real-shaped iteration dir for --from-run extraction."""
    iteration = tmp_path / "iteration_1"
    node = iteration / "node_memory" / "Tree_0_0"
    (node / "manager_results").mkdir(parents=True)
    (node / "workspace_views").mkdir(parents=True)
    timeline = [
        {"kind": "bootstrap", "node": "Tree-0.0", "replay_prefix_count": 0},
        {"kind": "manager_turn", "turn": 1,
         "intent": {"intent": "probe_tactic", "payload": {"tactic": "congr."}}},
        {"kind": "manager_turn", "turn": 2,
         "intent": {"intent": "commit_tactic", "payload": {"tactic": "congr."}}},
        {"kind": "manager_turn", "turn": 3,
         "intent": {"intent": "inspect_context", "payload": {"topic": "goal_info"}}},
    ]
    (node / "timeline.jsonl").write_text(
        "\n".join(json.dumps(e) for e in timeline), encoding="utf-8"
    )
    # manager_results carries the authoritative handled_intent for turn 2.
    (node / "manager_results" / "turn_002.json").write_text(
        json.dumps({"handled_intent": {"intent": "commit_tactic",
                                       "payload": {"tactic": "congr."}}}),
        encoding="utf-8",
    )
    (node / "workspace_views" / "turn_001.json").write_text(
        json.dumps({"surface_profile": {"surface_profile": "l4_checked_action_surface"}}),
        encoding="utf-8",
    )
    (iteration / "manager_bootstrap_0_0.json").write_text(
        json.dumps({
            "file": "/abs/ChaChaPoly/chacha_poly.ec",
            "lemma": "step1",
            "include_dirs": ["/abs/ChaChaPoly", "/abs/theories"],
            "workspace_view": {
                "surface_profile": {"surface_profile": "l4_checked_action_surface"}
            },
        }),
        encoding="utf-8",
    )
    return iteration


def test_steps_from_run_extracts_full_intent_stream(tmp_path: Path) -> None:
    iteration = _write_run_fixture(tmp_path)

    steps, meta = mvr._steps_from_run(str(iteration), "", project_root=mvr.SCRIPT_PROJECT_ROOT)

    # Probe/inspect intents are recovered, not just committed tactics.
    assert [s.to_dict() for s in steps] == [
        {"intent": "probe_tactic", "payload": {"tactic": "congr."}},
        {"intent": "commit_tactic", "payload": {"tactic": "congr."}},
        {"intent": "inspect_context", "payload": {"topic": "goal_info"}},
    ]
    assert meta["file"] == "/abs/ChaChaPoly/chacha_poly.ec"
    assert meta["lemma"] == "step1"
    assert meta["surface_profile"] == "l4_checked_action_surface"
    assert meta["node"] == "Tree-0.0"
    assert meta["node_views_dir"].endswith("Tree_0_0/workspace_views")
    # The non-file include dir is preferred for the single manager include slot.
    assert meta["include_dir"] == "/abs/theories"
    assert meta["intent_count"] == 3


def test_steps_from_run_accepts_node_dir_directly(tmp_path: Path) -> None:
    iteration = _write_run_fixture(tmp_path)
    node_dir = iteration / "node_memory" / "Tree_0_0"

    steps, meta = mvr._steps_from_run(str(node_dir), "", project_root=mvr.SCRIPT_PROJECT_ROOT)

    assert [s.intent for s in steps] == [
        "probe_tactic", "commit_tactic", "inspect_context",
    ]
    assert meta["node"] == "Tree-0.0"


def test_reconcile_views_flags_match_and_divergence(tmp_path: Path) -> None:
    out = tmp_path / "out"
    (out / "workspace_views").mkdir(parents=True)
    live = tmp_path / "live_views"
    live.mkdir()

    view = {"current_goal": {"lines": ["G"]}, "candidate_moves": {"moves": []}}
    # turn 1: identical
    (out / "workspace_views" / "turn_001_probe_tactic.json").write_text(json.dumps(view))
    (live / "turn_001.json").write_text(json.dumps(view))
    # turn 2: different goal (proof divergence) and content
    (out / "workspace_views" / "turn_002_commit_tactic.json").write_text(
        json.dumps({"current_goal": {"lines": ["H"]}})
    )
    (live / "turn_002.json").write_text(json.dumps({"current_goal": {"lines": ["G2"]}}))
    # turn 3 exists only in the live run (replay stopped early / capped): it must
    # NOT read as a silent pass.
    (live / "turn_003.json").write_text(json.dumps(view))
    # a bootstrap view must be ignored by reconcile
    (out / "workspace_views" / "turn_000_bootstrap.json").write_text(json.dumps(view))

    rec = mvr._reconcile_views(out, live, strict=False)
    by_turn = {row["turn"]: row for row in rec["views"]}

    assert by_turn[1]["identical"] is True
    assert by_turn[2]["identical"] is False
    assert by_turn[2]["goal_diverged"] is True
    assert by_turn[3]["identical"] is False  # missing on the replay side
    assert rec["identical"] == 1
    assert rec["turns_compared"] == 2     # only turns present on both sides
    assert rec["turns_total"] == 3
    assert rec["missing"] == 1            # turn 3 never reproduced
    assert rec["mismatched"] == 2         # turn 2 differs + turn 3 missing
    assert 0 not in by_turn  # bootstrap skipped
    # a per-turn diff file was written for the mismatch
    assert Path(by_turn[2]["diff"]).exists()
