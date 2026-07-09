from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from workflow.managed_prover_worker import _render_manager_followup  # noqa: E402
from workflow.proof_node_runtime import (  # noqa: E402
    closed_history_tactics as _closed_history_tactics,
)
from workflow.proof_management import ManagedTurn, NodeHealthEvent  # noqa: E402


def _json_blocks(text: str) -> list[dict]:
    blocks: list[dict] = []
    parts = text.split("```json\n")[1:]
    for part in parts:
        raw = part.split("\n```", 1)[0]
        blocks.append(json.loads(raw))
    return blocks


def test_manager_followup_hides_backend_argv() -> None:
    turn = ManagedTurn(
        ok=True,
        workspace_view={
            "ok": True,
            "kind": "prover_workspace_view",
            "schema_version": 2,
            "last_result": {},
            "proof_status": {"status": "open"},
            "current_goal": {"lines": ["Current goal", "x = y"]},
            "program_frontier": {},
            "application_context": {},
            "facts_and_diagnostics": {},
            "candidate_moves": {},
            "inspect_lookup_handles": {},
            "based_on_state_version": 3,
            "session_epoch": 1,
            "view_hash": "abc",
        },
        manager_actions=[{
            "label": "probe_tactic",
            "argv": ["python3", "core/easycrypt/session_cli.py"],
            "exit_code": 0,
            "stdout_has_workspace_view": True,
            "agent_observation": {
                "status": "probe_accepted",
                "effect": "read-only probe; proof state unchanged",
            },
        }],
    )

    text = _render_manager_followup(
        turn,
        turn_index=1,
        handled_intent={"intent": "probe_tactic", "payload": {"tactic": "smt()."}},
    )

    assert "exactly one proof intent" in text
    # the view is now tiered markdown, not a JSON blob: goal rendered under a heading
    assert "## 🎯 Current Goal" in text
    assert "Current goal" in text and "x = y" in text
    assert "session_cli.py" not in text
    assert '"argv"' not in text
    assert "latest_prover_workspace_view" not in text
    # (composition fix 2026-06-05) the raw result_payload JSON dump is GONE — the
    # manager result is a readable summary, no machine-readable blob.
    assert "```json" not in text
    assert len(_json_blocks(text)) == 0
    assert "Probe returned" in text
    assert "### Manager result" not in text
    assert "you submitted" not in text
    # backend / freshness metadata never reaches the agent-facing markdown
    for hidden in ("schema_version", "based_on_state_version", "session_epoch", "view_hash"):
        assert hidden not in text


def test_manager_followup_includes_timeout_health_event() -> None:
    turn = ManagedTurn(
        ok=False,
        workspace_view={
            "kind": "prover_workspace_view",
            "current_goal": {"lines": ["Current goal", "x = y"]},
        },
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

    text = _render_manager_followup(
        turn,
        turn_index=2,
        handled_intent={
            "intent": "commit_tactic",
            "payload": {"tactic": "inline *."},
        },
    )
    # (composition fix 2026-06-05) no raw result_payload JSON dump — the timeout +
    # health are surfaced as readable text instead.
    assert "```json" not in text
    assert len(_json_blocks(text)) == 0
    assert "manager_action_timeout" in text          # health line
    assert "TIMED OUT" in text                        # explicit timeout line
    # the goal is rendered into the markdown view
    assert "Current goal" in text and "x = y" in text


def _goal_status_turn() -> ManagedTurn:
    return ManagedTurn(
        ok=True,
        workspace_view={
            "kind": "prover_workspace_view",
            "current_goal": {"lines": ["Current goal", "x = y"]},
            "last_result": {"tactic": "auto.",
                            "result": "EasyCrypt rejected the committed tactic.",
                            "proof_state": "The committed proof state was not changed."},
            "proof_status": {"status": "open", "remaining_goals": 1,
                             "view_focus": "relational_program", "current_layer": "call_site"},
        },
        manager_actions=[{"label": "commit_tactic",
                          "agent_observation": {"status": "accepted"}}],
    )


def test_l1_goal_only_followup_is_goal_plus_repl_feedback() -> None:
    # L1 goal-state-projection baseline: goal + a REPL-style accept/reject/error line
    # for the last action (so the agent knows if its tactic landed). NOT the status,
    # NOT the manager-result section, NOT the raw result JSON. (Regression: those were
    # leaking, so the L1 baseline was not actually minimal — but pure goal-only with
    # zero feedback is too little, so the accept/reject line stays.)
    text = _render_manager_followup(
        _goal_status_turn(), turn_index=3,
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


def test_non_l1_followup_keeps_status_and_turn_outcome() -> None:
    # the goal-only gate is L1-specific: richer profiles keep status + typed turn outcome.
    text = _render_manager_followup(
        _goal_status_turn(), turn_index=3,
        handled_intent={"intent": "commit_tactic", "payload": {"tactic": "auto."}},
        surface_profile="l4_checked_action_surface",
    )
    assert "## Status" in text
    assert "**Last action:**" in text and "rejected" in text
    assert "### Manager result" not in text
    # (composition fix 2026-06-05) no raw result_payload JSON dump in the agent text.
    assert len(_json_blocks(text)) == 0


def test_l1_bootstrap_handoff_is_goal_only(tmp_path: Path) -> None:
    # the initial handoff (turn_000) must also be goal-only for L1 — not a raw view
    # JSON dump (which leaks all panels into the agent's very first view).
    from workflow.proof_node_runtime import NodeMemory
    mem = NodeMemory(tmp_path, "Tree_0_0", surface_profile="l1_goal_projection")
    mem.record_bootstrap({"workspace_view": {
        "kind": "prover_workspace_view",
        "current_goal": {"lines": ["Current goal", "Pr[A] <= Pr[B]"]},
        "proof_status": {"remaining_goals": 1, "view_focus": "probability"},
        "candidate_moves": {"navigation": [1]}, "call_site_surface": {"x": 1}}})
    text = (tmp_path / "node_memory" / "Tree_0_0" / "followups" / "turn_000.md").read_text()
    assert "## 🎯 Current Goal" in text and "Pr[A]" in text     # goal shown
    assert "```json" not in text                               # no raw view dump
    assert "candidate_moves" not in text and "call_site_surface" not in text  # no panel leak
    assert "Legal Node Memory Anchor" in text                  # recovery anchor kept


def test_non_l1_bootstrap_handoff_uses_surface_turn_not_raw_json(tmp_path: Path) -> None:
    from workflow.proof_node_runtime import NodeMemory
    mem = NodeMemory(tmp_path, "Tree_0_0", surface_profile="l4_checked_action_surface")
    mem.record_bootstrap({"workspace_view": {
        "kind": "prover_workspace_view",
        "current_goal": {"lines": ["Current goal", "x = y"]}}})
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
