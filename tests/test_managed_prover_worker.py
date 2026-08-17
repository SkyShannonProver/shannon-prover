from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from core.easycrypt.committed_history import (  # noqa: E402
    closed_history_tactics as _closed_history_tactics,
)
from workflow.proof_node_runtime import render_manager_followup  # noqa: E402
from workflow.managed_prover_worker import _emit_final  # noqa: E402
from workflow.tree.trackers import _ProverTracker, _TreeProverTracker  # noqa: E402
from workflow.proof_management import ManagedTurn, NodeHealthEvent  # noqa: E402
from workflow.proof_state_compiler.managed_goal_view_manager import (  # noqa: E402
    ManagedGoalViewManager,
)
from workflow.proof_state_compiler.surface_profiles import (  # noqa: E402
    project_current_workspace_view,
)


def _current_workspace_view(**overrides: object) -> dict[str, object]:
    view: dict[str, object] = {
        "schema_version": 3,
        "kind": "prover_workspace_view",
        "ok": True,
        "last_result": {},
        "proof_status": {
            "status": "open",
            "remaining_goals_known": True,
            "goal_identity_required": True,
            "goal_hash": "goal",
        },
        "current_goal": {"lines": []},
        "view_hash": "fixture-view",
    }
    proof_status = dict(view["proof_status"])
    status_overrides = overrides.pop("proof_status", {})
    proof_status.update(status_overrides)
    if proof_status.get("status") in {
        "candidate_closed",
        "goals_discharged_pending_qed",
        "closed",
        "complete",
        "verified",
    } and "goal_identity_required" not in status_overrides:
        proof_status["goal_identity_required"] = False
        proof_status["goal_hash"] = ""
    view.update(overrides)
    view["proof_status"] = proof_status
    return view


def _profiled_workspace_view(
    profile_name: str,
    **overrides: object,
) -> dict[str, object]:
    """Build the fixture through the same projection/hash/order exit as runtime."""

    manager = ManagedGoalViewManager()
    view = project_current_workspace_view(
        _current_workspace_view(**overrides),
        profile_name,
    )
    view.pop("view_hash", None)
    view["view_hash"] = manager.view_hash(view)
    return manager.order_workspace_view(view)


def _current_bootstrap(*, workspace_view: dict[str, object]) -> dict[str, object]:
    return {
        "schema_version": 3,
        "kind": "proof_node_manager_bootstrap",
        "node_id": "Tree_0_0",
        "session_tag": "unit",
        "session_dir": ".ec_session_unit",
        "file": "target.ec",
        "lemma": "target",
        "include_dirs": ["."],
        "replay_prefix_count": 0,
        "replay_prefix": [],
        "replay_prefix_requested_count": 0,
        "manager_actions": [],
        "snapshot": {
            "node_id": "Tree_0_0",
            "session_tag": "unit",
            "session_dir": ".ec_session_unit",
            "session_epoch": 0,
            "state_version": 0,
            "goal_hash": "goal",
            "goal_identity_required": True,
            "workspace_view_artifact": "",
            "execution_refs": {},
        },
        "workspace_view": workspace_view,
    }


def _json_blocks(text: str) -> list[dict]:
    blocks: list[dict] = []
    parts = text.split("```json\n")[1:]
    for part in parts:
        raw = part.split("\n```", 1)[0]
        blocks.append(json.loads(raw))
    return blocks


def test_worker_final_event_carries_manager_turn_count(capsys) -> None:
    _emit_final("done", session_id="session-1", turns=8)

    event = json.loads(capsys.readouterr().out)
    assert event == {
        "result": "done",
        "session_id": "session-1",
        "turns": 8,
        "type": "result",
    }


def test_trackers_project_manager_turn_count_from_final_event(tmp_path: Path) -> None:
    event = json.dumps({"type": "result", "result": "done", "turns": 8})
    trackers = (
        _ProverTracker(object(), "Prover", str(tmp_path)),
        _TreeProverTracker(object(), "Tree-0.0", str(tmp_path)),
    )

    for tracker in trackers:
        tracker._process_line(event)
        assert tracker.manager_turns == 8


def test_tree_tracker_retains_live_manager_turn_count_without_final_event(
    tmp_path: Path,
) -> None:
    tracker = _TreeProverTracker(object(), "Tree-0.0", str(tmp_path))
    tracker._process_line(json.dumps({
        "type": "system",
        "kind": "manager_turn.completed",
        "node": "Tree-0.0",
        "turn_index": 1,
    }))
    assert tracker.manager_turns == 1

    # A stale/default final count must not erase turns observed before a hard
    # supervisor timeout. This is the exact failure mode of the audited run.
    tracker._process_line(json.dumps({
        "type": "result",
        "result": "timed out",
        "turns": 0,
    }))
    assert tracker.manager_turns == 1


def test_tree_tracker_does_not_infer_manager_turns_from_tool_text(
    tmp_path: Path,
) -> None:
    tracker = _TreeProverTracker(object(), "Tree-0.0", str(tmp_path))
    tracker._process_line(json.dumps({
        "type": "assistant",
        "message": {"content": [{
            "type": "tool_use",
            "id": "intent-stop",
            "name": "mcp__proof_node_manager__submit_proof_intent",
            "input": {"intent": "finish", "payload": {}},
        }]},
    }))
    tracker._process_line(json.dumps({
        "type": "user",
        "message": {"content": [{
            "type": "tool_result",
            "tool_use_id": "intent-stop",
            "content": "Last action accepted. Current goal: x = x",
        }]},
    }))
    assert tracker.manager_turns == 0


def test_manager_followup_hides_backend_argv() -> None:
    turn = ManagedTurn(
        ok=True,
        workspace_view={
            "ok": True,
            "kind": "prover_workspace_view",
            "schema_version": 3,
            "last_result": {},
            "proof_status": {
                "status": "open",
                "remaining_goals_known": True,
                "goal_identity_required": True,
                "goal_hash": "goal",
            },
            "current_goal": {"lines": ["Current goal", "x = y"]},
            "based_on_state_version": 3,
            "session_epoch": 1,
            "view_hash": "abc",
        },
        manager_actions=[{
            "label": "tactic_commit",
            "argv": ["python3", "core/easycrypt/session_cli.py"],
            "exit_code": 0,
            "stdout_has_workspace_view": True,
            "agent_observation": {
                "status": "ok",
                "effect": "the submitted tactic was checked by EasyCrypt",
            },
        }],
    )

    text = render_manager_followup(
        turn,
        turn_index=1,
        handled_intent={"intent": "commit_tactic", "payload": {"tactic": "smt()."}},
    )

    assert "exactly one proof intent" in text
    # The current goal is rendered as markdown, not a JSON blob.
    assert "## 🎯 Current Goal" in text
    assert "Current goal" in text and "x = y" in text
    assert "session_cli.py" not in text
    assert '"argv"' not in text
    assert "latest_prover_workspace_view" not in text
    # The manager result is a readable summary, not a machine-readable blob.
    assert "```json" not in text
    assert len(_json_blocks(text)) == 0
    assert "Probe returned" not in text
    assert "### Manager result" not in text
    assert "you submitted" not in text
    # backend / freshness metadata never reaches the agent-facing markdown
    for hidden in ("schema_version", "based_on_state_version", "session_epoch", "view_hash"):
        assert hidden not in text


def test_manager_followup_includes_timeout_health_event() -> None:
    turn = ManagedTurn(
        ok=False,
        workspace_view=_current_workspace_view(
            current_goal={"lines": ["Current goal", "x = y"]},
        ),
        health_event=NodeHealthEvent(
            node_id="Tree-unit",
            status="manager_action_timeout",
            message="manager backend action timed out",
            state_version=3,
        ),
        manager_actions=[{
            "label": "commit_tactic",
            "timed_out": True,
            "timeout_seconds": 180,
            "mutates_proof_state": True,
        }],
    )

    text = render_manager_followup(
        turn,
        turn_index=2,
        handled_intent={
            "intent": "commit_tactic",
            "payload": {"tactic": "inline *."},
        },
    )
    # Timeout and health are surfaced as readable text.
    assert "```json" not in text
    assert len(_json_blocks(text)) == 0
    assert "manager_action_timeout" in text          # health line
    assert "TIMED OUT" in text                        # explicit timeout line
    # the goal is rendered into the markdown view
    assert "Current goal" in text and "x = y" in text


def _goal_status_turn(profile_name: str) -> ManagedTurn:
    return ManagedTurn(
        ok=True,
        workspace_view=_profiled_workspace_view(
            profile_name,
            current_goal={"lines": ["Current goal", "x = y"]},
            last_result={"tactic": "auto.",
                            "result": "EasyCrypt rejected the committed tactic.",
                            "proof_state": "The committed proof state was not changed.",
                            "outcome_kind": "rejected",
                            "proof_state_effect": "unchanged",
                            "proof_state_changed": False,
                            "needs_attention": True},
            proof_status={"status": "open", "remaining_goals": 1,
                             "view_focus": "relational_program", "current_layer": "call_site"},
        ),
        manager_actions=[{
            "label": "commit_tactic",
            "outcome_kind": "rejected",
            "proof_state_effect": "unchanged",
            "proof_state_changed": False,
            "needs_attention": True,
        }],
    )


def test_l1_followup_is_goal_plus_repl_feedback() -> None:
    # L1 goal-state-projection baseline: goal + a REPL-style accept/reject/error line
    # for the last action (so the agent knows if its tactic landed). NOT the status,
    # NOT the manager-result section, NOT the raw result JSON. (Regression: those were
    # leaking, so the L1 baseline was not actually minimal — but pure goal-only with
    # zero feedback is too little, so the accept/reject line stays.)
    text = render_manager_followup(
        _goal_status_turn("l1_goal_projection"), turn_index=3,
        handled_intent={"intent": "commit_tactic", "payload": {"tactic": "auto."}},
        surface_profile="l1_goal_projection",
    )
    assert "## 🎯 Current Goal" in text and "x = y" in text     # goal stays
    assert "**Last action:**" in text and "rejected" in text    # REPL accept/reject feedback
    assert text.index("**Last action:**") < text.index("## 🎯 Current Goal")
    assert "## Status" not in text                              # no status
    assert "### Manager result" not in text                     # no manager-result section
    assert len(_json_blocks(text)) == 0                         # no raw result JSON blob
    assert "proof intent" in text                               # protocol reminder stays


def test_compiler_followup_uses_same_goal_envelope_as_l1() -> None:
    text = render_manager_followup(
        _goal_status_turn("l4_proof_state_compiler_v2_operation_binding_repair"), turn_index=3,
        handled_intent={"intent": "commit_tactic", "payload": {"tactic": "auto."}},
        surface_profile="l4_proof_state_compiler_v2_operation_binding_repair",
    )
    assert "## Status" not in text
    assert "**Last action:**" in text and "rejected" in text
    assert "### Manager result" not in text
    # (composition fix 2026-06-05) no raw result_payload JSON dump in the agent text.
    assert len(_json_blocks(text)) == 0


def test_l1_bootstrap_handoff_uses_only_current_envelope(tmp_path: Path) -> None:
    # the initial handoff (turn_000) must also be goal-only for L1 — not a raw view
    # JSON dump (which leaks all panels into the agent's very first view).
    from workflow.proof_node_runtime import NodeMemory
    mem = NodeMemory(tmp_path, "Tree_0_0", surface_profile="l1_goal_projection")
    mem.record_bootstrap(_current_bootstrap(
        workspace_view=_profiled_workspace_view(
            "l1_goal_projection",
            current_goal={"lines": ["Current goal", "Pr[A] <= Pr[B]"]},
            proof_status={"remaining_goals": 1, "view_focus": "probability"},
        ),
    ))
    text = (tmp_path / "node_memory" / "Tree_0_0" / "followups" / "turn_000.md").read_text()
    assert "## 🎯 Current Goal" in text and "Pr[A]" in text     # goal shown
    assert "```json" not in text                               # no raw view dump
    assert "candidate_moves" not in text and "call_site_surface" not in text  # no panel leak
    assert "Legal Node Memory Anchor" in text                  # recovery anchor kept


def test_compiler_bootstrap_handoff_uses_current_turn_not_raw_json(tmp_path: Path) -> None:
    from workflow.proof_node_runtime import NodeMemory
    profile = "l4_proof_state_compiler_v2_operation_binding_repair"
    mem = NodeMemory(tmp_path, "Tree_0_0", surface_profile=profile)
    mem.record_bootstrap(_current_bootstrap(
        workspace_view=_profiled_workspace_view(
            profile,
            current_goal={"lines": ["Current goal", "x = y"]},
        ),
    ))
    text = (tmp_path / "node_memory" / "Tree_0_0" / "followups" / "turn_000.md").read_text()
    assert "```json" not in text
    assert "## 🎯 Current Goal" in text and "x = y" in text
    latest = json.loads(mem.latest_view.read_text(encoding="utf-8"))
    assert "surface_turn" in latest
    assert "proof_surface" in latest["surface_turn"]
    assert "surface_model" not in latest


def test_closed_history_tactics_requires_qed(tmp_path: Path) -> None:
    session_dir = tmp_path / ".ec_session_unit"
    session_dir.mkdir()
    history = session_dir / "history.ec"

    history.write_text("byequiv=>//.\n", encoding="utf-8")
    assert _closed_history_tactics(session_dir) == []

    history.write_text("byequiv=>//.\nqed.\n", encoding="utf-8")
    assert _closed_history_tactics(session_dir) == ["byequiv=>//.", "qed."]

def test_worker_reports_runtime_initialization_failure_as_result_event(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    from workflow import managed_prover_worker

    prompt = tmp_path / "prompt.md"
    bootstrap = tmp_path / "bootstrap.json"
    prompt.write_text("prove it\n", encoding="utf-8")
    bootstrap.write_text("{}\n", encoding="utf-8")

    class BrokenRuntime:
        def __init__(self, **_kwargs) -> None:
            raise RuntimeError("confinement unavailable")

    monkeypatch.setattr(managed_prover_worker, "ProofNodeRuntime", BrokenRuntime)

    returncode = managed_prover_worker.main([
        "--prompt-file", str(prompt),
        "--bootstrap-file", str(bootstrap),
        "--file", "Target.ec",
        "--lemma", "target",
        "--include-dir", "theories",
        "--session-tag", "worker-test",
        "--node-id", "Tree-0.0",
        "--run-dir", str(tmp_path / "run"),
        "--model", "gpt-5.6-sol",
    ])

    assert returncode == 1
    event = json.loads(capsys.readouterr().out)
    assert event["type"] == "result"
    assert "confinement unavailable" in event["result"]
