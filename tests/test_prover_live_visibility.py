"""Tests for live prover structured-output visibility safeguards."""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from workflow.agents.prover_prompt import _build_prover_prompt  # noqa: E402
from workflow.progress import (  # noqa: E402
    _TreeProverTracker,
    _find_branch_point,
    _summarize_tool,
    _terminate_process_tree,
)


def test_prover_prompt_omits_session_cli_as_agent_interface() -> None:
    prompt = _build_prover_prompt(
        "eval/examples/SchnorrPK.ec",
        "schnorr_proof_of_knowledge_completeness_ll",
        "easycrypt-src/theories",
        session_tag="test_visibility",
    )

    # The static prompt is a lean surface: target-file pointer + manager
    # handoff view. The MCP / interpret / play guidance lives in the runtime
    # wrapper, and the manager-resource menu is runtime-generated (the static
    # reference panels were removed in a97b0ce9f).
    assert "## Target Source" in prompt
    assert "Target file: `eval/examples/SchnorrPK.ec`" in prompt
    assert "Initial ProverWorkspaceView" in prompt
    assert "lemma_index" not in prompt
    # session_cli / legacy CLI must never be presented as the agent interface
    assert "session_cli.py" not in prompt
    assert "session_cli" not in prompt
    assert "Do **not** run" not in prompt
    assert "long-lived runtime's manager bridge" not in prompt
    assert "[TACTIC-EXECUTION-RESULT]" not in prompt
    assert "TacticExecutionResult" not in prompt
    assert "inspect_handles" not in prompt
    assert "[COMMAND-SUMMARY]" not in prompt
    assert "## Start the EasyCrypt session" not in prompt
    assert " -start -f " not in prompt
    assert "Run `-start` exactly once" not in prompt
    assert "| tail" not in prompt


def test_prover_static_carries_view_field_gold() -> None:
    # The interpret/play guidance lives in the runtime wrapper (covered by
    # test_long_lived_prompt_explains_runtime_and_memory), and the static
    # view-field gold / manager-resource panels were deliberately removed
    # (a97b0ce9f "Remove strategy-heavy prover prompt context"): the static
    # prompt is now ONLY a target-source pointer + the manager handoff view.
    # Guard against strategy-context creeping back into the static surface.
    prompt = _build_prover_prompt(
        "eval/examples/SchnorrPK.ec",
        "schnorr_proof_of_knowledge_completeness_ll",
        "easycrypt-src/theories",
        session_tag="test_navigation_prompt",
    )

    # Structural pin: with no managed session, the static prompt has exactly
    # the target-source section and the handoff-view section — no extra
    # strategy / reference / playbook sections.
    headings = [
        line.strip() for line in prompt.splitlines()
        if line.startswith("#")
    ]
    assert headings == [
        "## Target Source",
        "### Initial ProverWorkspaceView",
    ], f"unexpected static-prompt sections: {headings}"
    # the removed reference panels must stay gone
    assert "## A few specific things the view carries" not in prompt
    assert "Resources you can ask the manager for" not in prompt
    assert "application_context.write_map" not in prompt
    assert "proof_map" not in prompt
    assert "annotate_piece" not in prompt
    # the deleted legacy playbook must be gone
    assert "## Hypothesis-Driven Proving" not in prompt
    assert "fast_track_probe" not in prompt
    assert "## Information Source Policy" not in prompt
    assert "## Prove the lemma" not in prompt
    assert "\n## Rules" not in prompt
    # no target-answer leak
    for target_name in ("Pr_PIR_s", "nth_extend", "DDH1_G1_dec"):
        assert target_name not in prompt


def test_prover_prompt_embeds_manager_handoff_view() -> None:
    prompt = _build_prover_prompt(
        "eval/examples/SchnorrPK.ec",
        "schnorr_proof_of_knowledge_completeness_ll",
        "easycrypt-src/theories",
        session_tag="test_visibility",
        managed_session={
            "workspace_view": {
                "kind": "prover_workspace_view",
                "current_goal": {
                    "lines": ["Current goal", "----", "x = y"],
                    "text_fully_shown": True,
                },
                "suggested_next_steps": {"primary": {"category": "reason"}},
            },
        },
    )

    assert "The manager-produced agent-facing view at handoff" in prompt
    # The handoff view is the rendered agent-facing markdown surface (the same
    # one shown on every later turn) — not raw JSON. The goal text appears in
    # its Current Goal block; the full structured view lives separately in
    # LEGAL_LATEST_WORKSPACE_VIEW.
    initial_view = prompt.split("### Initial ProverWorkspaceView", 1)[1]
    assert "Current Goal" in initial_view
    assert "x = y" in initial_view
    assert '"schema_version"' not in initial_view
    assert "The expected manager handoff view is missing" not in prompt


def test_progress_summary_uses_shell_tokenized_tactic_arg() -> None:
    cmd = (
        "python3 core/easycrypt/session_cli.py -d .ec_session "
        "-next -c 'wp.' 2>&1 | grep 'TACTIC-EXECUTION-RESULT'"
    )

    assert (
        _summarize_tool("Bash", {"command": cmd})
        == "Low-level EC session CLI call (debug signal)"
    )


def test_progress_summary_uses_shell_tokenized_chain_arg() -> None:
    cmd = (
        "python3 core/easycrypt/session_cli.py -d .ec_session "
        "-chain --keep-on-fail -c 'wp. skip. auto => />.' 2>&1 | head -80"
    )

    assert (
        _summarize_tool("Bash", {"command": cmd})
        == "Low-level EC session CLI call (debug signal)"
    )


def test_tree_tracker_exposes_session_tag_alias() -> None:
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(0.1)"],
    )
    try:
        tracker = _TreeProverTracker(
            proc,
            "Tree-test",
            str(ROOT),
            session_tag="prover_tree_test",
        )

        assert tracker.session_tag == "prover_tree_test"
    finally:
        proc.terminate()
        proc.wait(timeout=5)


def test_tree_tracker_activity_updates_on_mcp_tool_use_without_commit() -> None:
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(0.1)"],
    )
    try:
        tracker = _TreeProverTracker(
            proc,
            "Tree-test",
            str(ROOT),
            session_tag="prover_tree_test",
        )
        previous_activity = tracker.last_activity_time
        previous_progress = tracker.last_progress_time
        time.sleep(0.01)

        tracker._process_line(json.dumps({
            "type": "assistant",
            "message": {
                "content": [{
                    "type": "tool_use",
                    "name": "submit_proof_intent",
                    "input": {
                        "intent": "inspect_context",
                        "payload": {"topic": "call_subgoals"},
                    },
                }],
            },
        }))

        assert tracker.last_activity_time > previous_activity
        assert tracker.last_progress_time == previous_progress
        assert tracker.committed_count == 0
    finally:
        proc.terminate()
        proc.wait(timeout=5)



def test_terminate_process_tree_prefers_child_process_group(monkeypatch) -> None:
    calls: list[tuple[int, int]] = []

    class FakeProc:
        pid = 12345
        terminated = False
        killed = False

        def poll(self):
            return None

        def terminate(self):
            self.terminated = True

        def kill(self):
            self.killed = True

        def wait(self, timeout=None):  # noqa: ANN001
            return 0

    def fake_killpg(pgid: int, sig: int) -> None:
        calls.append((pgid, sig))

    monkeypatch.setattr("workflow.tree.supervisor.os.getpgid", lambda _pid: 456)
    monkeypatch.setattr("workflow.tree.supervisor.os.getpgrp", lambda: 999)
    monkeypatch.setattr("workflow.tree.supervisor.os.killpg", fake_killpg)

    proc = FakeProc()
    _terminate_process_tree(proc)  # type: ignore[arg-type]

    assert calls == [(456, signal.SIGTERM)]
    assert proc.terminated is False
    assert proc.killed is False


def test_tree_branching_replays_current_frontier_with_failed_tactic() -> None:
    tactics = [
        "congr.",
        "have -> : Pr[A.main() @ &m : res] = Pr[B.main() @ &m : res].",
        "byequiv => //.",
        "proc.",
        "inline{1} 1.",
        "wp.",
    ]

    branch = _find_branch_point(tactics, recent_failed_tactic="if => //.")

    assert branch == (tactics, ["if => //."])


def test_tree_branching_does_not_restart_at_first_strategy_tactic() -> None:
    tactics = [
        "congr.",
        "have -> : Pr[A.main() @ &m : res] = Pr[B.main() @ &m : res].",
        "byequiv => //.",
        "proc.",
        "inline{1} 1.",
    ]

    branch = _find_branch_point(tactics)

    assert branch == (tactics, [])


if __name__ == "__main__":
    test_prover_prompt_omits_session_cli_as_agent_interface()
    test_prover_prompt_embeds_manager_handoff_view()
    test_progress_summary_uses_shell_tokenized_tactic_arg()
    test_progress_summary_uses_shell_tokenized_chain_arg()
    test_tree_tracker_exposes_session_tag_alias()
    test_tree_tracker_activity_updates_on_mcp_tool_use_without_commit()
    test_node_new_commit_count_discounts_replay_prefix()
    test_tree_branching_replays_current_frontier_with_failed_tactic()
    test_tree_branching_does_not_restart_at_first_strategy_tactic()
    print("PASS test_prover_live_visibility")
