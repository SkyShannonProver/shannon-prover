"""Tests for the anti-premature-give-up gate (ProofNodeManager._give_up_gate).

A `finish` while the proof is still open is a give-up: deflect the first
ALLOW_AFTER-1 times within the window, honor the ALLOW_AFTER-th, and NEVER gate a
real completion.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

import workflow.proof_node_manager as pnm  # noqa: E402

ProofNodeManager = pnm.ProofNodeManager


def _mgr(view):
    """A ProofNodeManager stub with just what _give_up_gate touches."""
    m = ProofNodeManager.__new__(ProofNodeManager)
    m.node_id = "test-node"
    # latest_view / latest_snapshot are properties backed by self.lifecycle
    m.lifecycle = SimpleNamespace(latest_view=dict(view), latest_snapshot=None)
    m._audit = lambda *a, **k: None
    return m


def _finish():
    return SimpleNamespace(intent="finish", payload={})


_OPEN = {"proof_status": {"status": "open", "remaining_goals": 1}}
_DONE = {"proof_status": {"status": "complete", "remaining_goals": 0}}


def test_non_finish_never_gated() -> None:
    m = _mgr(_OPEN)
    assert m._give_up_gate(SimpleNamespace(intent="probe_tactic", payload={})) is None


def test_success_finish_never_gated() -> None:
    # status complete -> a real completion passes through, even repeatedly
    m = _mgr(_DONE)
    for _ in range(5):
        assert m._give_up_gate(_finish()) is None
    # remaining_goals == 0 with non-complete status is also a completion
    m2 = _mgr({"proof_status": {"status": "open", "remaining_goals": 0}})
    assert m2._give_up_gate(_finish()) is None


def test_candidate_closed_states_never_gated() -> None:
    # a closed candidate (needs qed/save, not a give-up nudge) must pass through
    for st in ("candidate_closed", "candidate_closed_pending_qed", "complete", "empty"):
        m = _mgr({"proof_status": {"status": st}})
        assert m._give_up_gate(_finish()) is None, st


def test_open_finish_deflected_once_then_allowed() -> None:
    # Default: ONE gentle, non-coercive nudge, then honor the finish.
    assert pnm._GIVE_UP_ALLOW_AFTER == 2
    m = _mgr(_OPEN)
    # 1st give-up -> deflected with a gentle "your call" message (ok False)
    g1 = m._give_up_gate(_finish())
    assert g1 is not None and g1.ok is False
    assert "That is your call" in g1.repair_prompt
    assert "finishing is fine" in g1.repair_prompt
    assert "submit `finish` again" in g1.repair_prompt
    # No coercive counter / "give-up N of M" pressure language.
    assert "give-up 1 of" not in g1.repair_prompt.lower()
    assert "make a genuine attempt" not in g1.repair_prompt.lower()
    # 2nd give-up within the window -> honored (None = proceed to finish)
    assert m._give_up_gate(_finish()) is None


def test_window_prunes_old_giveups() -> None:
    m = _mgr(_OPEN)
    # a stale give-up OLDER than the window must not count toward the threshold
    old = time.time() - pnm._GIVE_UP_WINDOW_S - 10
    m._give_up_times = [old]
    g = m._give_up_gate(_finish())
    # the stale one is pruned, so this is the first fresh give-up -> deflected
    assert g is not None and g.ok is False
    assert "That is your call" in g.repair_prompt
    assert m._give_up_times == [m._give_up_times[-1]]  # only the fresh one survives


if __name__ == "__main__":
    test_non_finish_never_gated()
    test_success_finish_never_gated()
    test_candidate_closed_states_never_gated()
    test_open_finish_deflected_once_then_allowed()
    test_window_prunes_old_giveups()
    print("PASS test_give_up_gate")
