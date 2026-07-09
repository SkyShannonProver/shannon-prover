"""The agent's step-numbered committed proof (`proof_so_far`).

Design (2026-06-25): it is NOT inlined in every prompt (that bloats context on
long proofs and contributed to a respawn cascade on CBC_upto). Instead it is
written every turn to a fixed node-memory file (`proof_so_far.md`, anchored as
LEGAL_PROOF_SO_FAR in the standing prompt) that the agent reads on demand — to
pick a step for amend_and_replay / undo_to_checkpoint, or to re-orient after a
context refresh / respawn. These tests lock: the file is written + complete, the
prompt does NOT inline it, and the standing anchor points at it.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from core.easycrypt.session_agent_view import _proof_so_far  # noqa: E402


def test_proof_so_far_forwarded_to_view_but_not_inlined_in_prompt(tmp_path):
    """proof_so_far must still be FORWARDED into the agent-facing view (so it lands
    in the saved snapshot + the file), but the rendered PROMPT must NOT inline it."""
    from core.easycrypt.session_agent_view import build_proof_context_view
    from core.easycrypt.session_prover_workspace_view import (
        build_prover_workspace_view_from_context,
    )
    from core.easycrypt.session_workspace_view_manager import WorkspaceViewManager
    from workflow.surface_turn_model import compose_surface_turn, render_surface_turn_markdown

    (tmp_path / "history.ec").write_text(
        "proc.\nseq 1 1 : (x=y).\nwp.\nskip.\n", encoding="utf-8")
    ctx = build_proof_context_view(str(tmp_path))
    view = build_prover_workspace_view_from_context(ctx)
    assert "proof_so_far" in view                       # still forwarded into the view
    assert view["proof_so_far"]["committed_count"] == 4
    disp = WorkspaceViewManager().agent_display_view(view)
    assert "proof_so_far" in disp                       # survives projection (for the file)
    md = render_surface_turn_markdown(
        compose_surface_turn(disp, "l4_checked_action_surface")
    )
    assert "Proof so far" not in md                     # but NOT inlined into the prompt
    assert "1. proc." not in md


def test_proof_so_far_numbers_committed_tactics(tmp_path):
    (tmp_path / "history.ec").write_text(
        "byequiv (_: ={glob A}).\nproc.\nauto.\n", encoding="utf-8")
    pf = _proof_so_far(tmp_path)
    assert pf["committed_count"] == 3
    assert pf["elided_count"] == 0
    assert pf["steps"] == [
        {"step": 1, "tactic": "byequiv (_: ={glob A})."},
        {"step": 2, "tactic": "proc."},
        {"step": 3, "tactic": "auto."},
    ]


def test_proof_so_far_empty_when_no_history(tmp_path):
    pf = _proof_so_far(tmp_path)  # no history.ec
    assert pf["committed_count"] == 0
    assert pf["steps"] == []


def test_proof_so_far_is_complete_for_normal_proofs(tmp_path):
    """The on-demand file is not budget-bound, so a normal-length proof is shown in
    FULL (no mid-proof elision) — unlike the old 25+25 prompt truncation."""
    lines = [f"tac{i}." for i in range(1, 201)]  # 200 committed tactics
    (tmp_path / "history.ec").write_text("\n".join(lines), encoding="utf-8")
    pf = _proof_so_far(tmp_path)
    assert pf["committed_count"] == 200
    assert pf["elided_count"] == 0                       # complete, no elision
    assert len(pf["steps"]) == 200
    assert pf["steps"][0] == {"step": 1, "tactic": "tac1."}
    assert pf["steps"][-1] == {"step": 200, "tactic": "tac200."}


def test_proof_so_far_written_to_file_and_anchored_not_inlined(tmp_path):
    """End-to-end: write_latest_followup persists the numbered proof to the fixed
    LEGAL_PROOF_SO_FAR file; the followup PROMPT does not inline it; and the
    standing node-memory anchor points the agent at the file."""
    from workflow.proof_management import ManagedTurn
    from workflow.proof_node_runtime import (
        NodeMemory, _legal_node_memory_anchor, _render_manager_followup,
    )
    memory = NodeMemory(tmp_path, "Tree_0_0")
    full_view = {
        "kind": "prover_workspace_view",
        "current_goal": {"lines": ["x = y"]},
        "proof_status": {"status": "open"},
        "proof_so_far": {"committed_count": 2,
                         "steps": [{"step": 1, "tactic": "proc."},
                                   {"step": 2, "tactic": "auto."}]},
    }
    # the file is written from the full workspace_view
    memory.write_latest_followup(
        turn_index=5, result_payload={}, workspace_view=full_view,
        followup_text="(prompt body)")
    assert memory.latest_proof.exists()
    proof_txt = memory.latest_proof.read_text(encoding="utf-8")
    assert "Proof so far" in proof_txt
    assert "1. proc." in proof_txt and "2. auto." in proof_txt

    # the prompt the agent reads does NOT inline the proof
    turn = ManagedTurn(
        ok=True,
        workspace_view={"kind": "prover_workspace_view",
                        "proof_status": {"status": "open"},
                        "current_goal": {"lines": ["x = y"]}},
        manager_actions=[],
    )
    md = _render_manager_followup(
        turn, 5, {"intent": "commit_tactic", "payload": {"tactic": "auto."}},
        memory, full_view=full_view, surface_profile="l4_checked_action_surface")
    assert "Proof so far" not in md
    assert "1. proc." not in md

    # the standing anchor points the agent at the file
    anchor = _legal_node_memory_anchor(memory)
    assert "LEGAL_PROOF_SO_FAR" in anchor
    assert "proof_so_far.md" in anchor
