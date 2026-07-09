"""Edit-and-replay stops at the FIRST replayed tactic that no longer applies.

When the agent fixes an early/root tactic and replays the rest, the replay must
stop at the first step the edit invalidated (leaving the session at the last kept
step), NOT skip it and keep trying later tactics into a now-wrong state. The
existing fork/respawn replay (restore_committed_tactics) must stay skip-and-continue.

Mocks the EC backend so it runs without EasyCrypt (same pattern as
test_admit_skeleton._mock_repl).
"""
from __future__ import annotations

import contextlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

import workflow.proof_management.repl_session as rs  # noqa: E402
from workflow.proof_management.repl_session import ReplSessionManager  # noqa: E402


def _mock_repl(monkeypatch, drop_step: int):
    """A ReplSessionManager whose mocked EC commits every replay step EXCEPT
    `drop_step` (which models a tactic the edit invalidated)."""
    repl = ReplSessionManager(
        file_path="x.ec", lemma_name="L", include_dir="x",
        session_tag="mock", node_id="mock",
    )
    repl._lock = contextlib.nullcontext()           # type: ignore[assignment]
    repl._session_epoch = 0                          # type: ignore[attr-defined]
    repl._include_dirs = lambda: []                  # type: ignore[assignment]
    repl._snapshot_from_agent_view = lambda **kw: None  # type: ignore[assignment]
    monkeypatch.setattr(rs, "_replay_aggregate_budget_seconds", lambda total: 0)
    monkeypatch.setattr(rs, "session_dir_path", lambda sd, pr: sd)

    state = {"committed": []}
    calls: list[str] = []

    def fake_backend(label, args, actions, timeout=0):
        calls.append(label)
        if label.startswith("replay_prefix_step_"):
            idx = int(label.rsplit("_", 1)[1])
            if idx != drop_step:                     # the dropped step does not commit
                state["committed"] = state["committed"] + [f"t{idx}"]
        return ""

    repl._run_backend = fake_backend                 # type: ignore[assignment]
    monkeypatch.setattr(rs, "read_committed_tactics", lambda sd: list(state["committed"]))
    return repl, calls


def _steps(calls):
    return [c for c in calls if c.startswith("replay_prefix_step_")]


def test_edited_prefix_stops_at_first_drop(monkeypatch):
    repl, calls = _mock_repl(monkeypatch, drop_step=3)
    _snap, actions = repl.restart_with_edited_prefix(
        ["t1.", "t2.", "BROKEN_AFTER_EDIT.", "t4."],
    )
    # steps 1,2,3 attempted; step 4 NOT (stopped at the first drop)
    assert _steps(calls) == [
        "replay_prefix_step_1", "replay_prefix_step_2", "replay_prefix_step_3",
    ]
    stopped = [a for a in actions if a.get("label") == "replay_prefix_stopped_at_divergence"]
    assert len(stopped) == 1
    assert stopped[0]["replay_stopped_at_step"] == 3
    assert stopped[0]["replay_kept_count"] == 2      # t1, t2 kept; t3 dropped, t4 untried


def test_restore_committed_tactics_keeps_skip_and_continue(monkeypatch):
    # the fork/respawn replay path must be UNCHANGED: a dropped step does NOT stop
    # the replay (it skips and continues, reporting divergence at the end).
    repl, calls = _mock_repl(monkeypatch, drop_step=2)
    _snap, actions = repl.restore_committed_tactics(["t1.", "t2.", "t3.", "t4."])
    assert _steps(calls) == [f"replay_prefix_step_{i}" for i in (1, 2, 3, 4)]
    assert not [a for a in actions if a.get("label") == "replay_prefix_stopped_at_divergence"]
