"""Resume drift-gate must not kill a branch the agent intentionally rewound.

The orchestrator runs a ONE-TIME post-resume integrity check
(`_resume_replay_gate`): it confirms the committed prefix replayed into the
session still matches the checkpoint we resumed from, to catch genuine backend
replay desync.

Under transparent resume the agent owns its whole proof and may
`undo_to_checkpoint` / `undo_last_step` INTO the replayed prefix to discharge an
admit or rebuild an upstream invariant — which legitimately rewrites the prefix.
Before this fix the gate could not tell that intentional rewrite from backend
desync and killed the branch ("resume capsule drift"), culling exactly the tree
doing the cross-prefix repair that Tasks #1/#2 enabled. The gate now skips once
the agent has rewound (`agent_has_rewound`); a genuine desync still surfaces
because it appears BEFORE any agent undo.
"""
from __future__ import annotations

import sys
import tempfile
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from workflow.progress import _resume_replay_gate, _TreeProverTracker  # noqa: E402
from workflow.session_observer import WorkflowSessionSnapshot  # noqa: E402


def _snap(history: list[str], goal_hash: str = "", latest_tactic: str = ""):
    return WorkflowSessionSnapshot(
        session_dir="/tmp/x",
        exists=True,
        ok=True,
        history_exists=True,
        history_tactics=list(history),
        goal_hash=goal_hash,
        latest_transition={"tactic": latest_tactic} if latest_tactic else {},
        active_tool_mutates=None,
    )


PREFIX = ["proc.", "sp.", "admit.", "wp.", "skip."]


def test_rewound_branch_is_not_drift_killed_despite_prefix_mismatch():
    """The fix: agent rewrote step 3 (admit. -> inline.) — must NOT be drift."""
    rewritten = ["proc.", "sp.", "inline.", "wp.", "skip.", "auto."]
    checked, drift = _resume_replay_gate(
        _snap(rewritten, goal_hash="deadbeef"),
        replay_prefix=PREFIX,
        expected_goal_hash="cafef00d",
        agent_has_rewound=True,
    )
    assert checked is True
    assert drift == ""  # no kill


def test_genuine_desync_still_detected_before_any_rewind():
    """Same mismatch but agent has NOT rewound -> genuine desync -> drift."""
    desynced = ["proc.", "XXX.", "admit.", "wp.", "skip."]
    checked, drift = _resume_replay_gate(
        _snap(desynced, goal_hash="deadbeef"),
        replay_prefix=PREFIX,
        expected_goal_hash="cafef00d",
        agent_has_rewound=False,
    )
    assert checked is True
    assert "prefix drift" in drift  # still killed — desync caught


def test_clean_replay_verifies_without_drift():
    """Prefix matches and goal hash matches -> verified, no drift."""
    checked, drift = _resume_replay_gate(
        _snap(PREFIX, goal_hash="cafef00d", latest_tactic="skip."),
        replay_prefix=PREFIX,
        expected_goal_hash="cafef00d",
        agent_has_rewound=False,
    )
    assert checked is True
    assert drift == ""


def test_rewound_flag_short_circuits_even_with_empty_snapshot():
    """Once rewound, the gate is moot regardless of snapshot state."""
    checked, drift = _resume_replay_gate(
        None,
        replay_prefix=PREFIX,
        expected_goal_hash="cafef00d",
        agent_has_rewound=True,
    )
    assert checked is True
    assert drift == ""


# --- signal DERIVATION (the gap the audit flagged: above tests pass the flag as
# a literal; these exercise how `agent_has_rewound` is actually produced from
# real snapshot application, which is where the original last_undo_time wiring
# was broken for undo_to_checkpoint). ---


def _tracker() -> _TreeProverTracker:
    proc = types.SimpleNamespace(pid=0, poll=lambda: None, returncode=None)
    return _TreeProverTracker(proc, "Tree-0.0", tempfile.mkdtemp(), session_tag="unit")


def _count_snap(n: int):
    return WorkflowSessionSnapshot(
        session_dir="/tmp/x", exists=True, ok=True,
        history_exists=True, history_tactics=["t."] * n, tactic_count=n,
    )


def test_history_truncation_latches_rewound_signal():
    """undo_to_checkpoint = force-restart + shorter replay -> committed count
    dips below the high-water mark. The signal must latch and stay latched even
    after the agent re-proves forward past the old length."""
    t = _tracker()
    for n in (50, 110):              # initial replay grows monotonically
        t._apply_session_snapshot(_count_snap(n))
    assert t.history_ever_shrank is False  # forward-only so far

    t._apply_session_snapshot(_count_snap(64))   # rewind into the prefix
    assert t.history_ever_shrank is True    # latched

    t._apply_session_snapshot(_count_snap(114))  # re-prove forward past old max
    assert t.history_ever_shrank is True    # sticky — never clears


def test_forward_only_proof_never_latches():
    """A normal forward-only proof (no rewind) must NOT trip the signal."""
    t = _tracker()
    for n in (1, 5, 40, 110, 111):
        t._apply_session_snapshot(_count_snap(n))
    assert t.history_ever_shrank is False


def test_missing_history_read_is_not_mistaken_for_a_rewind():
    """A transient snapshot with no on-disk history must not falsely latch."""
    t = _tracker()
    t._apply_session_snapshot(_count_snap(110))
    # history_exists=False (e.g. mid force-restart rmtree) with empty history:
    t._apply_session_snapshot(WorkflowSessionSnapshot(
        session_dir="/tmp/x", exists=True, ok=True,
        history_exists=False, history_tactics=[], tactic_count=0,
    ))
    assert t.history_ever_shrank is False


def test_derived_signal_skips_drift_gate_for_undo_to_checkpoint_case():
    """End to end: a node that rewound via history truncation derives
    agent_has_rewound=True (no tactic.undone needed), so the gate does NOT
    drift-kill despite the prefix now being rewritten."""
    t = _tracker()
    t._apply_session_snapshot(_count_snap(110))
    t._apply_session_snapshot(_count_snap(64))  # undo_to_checkpoint, no last_undo
    assert t.last_undo_time == 0.0          # the old signal stays silent...
    derived = (
        getattr(t, "history_ever_shrank", False)
        or getattr(t, "last_undo_time", 0.0) > 0
    )
    assert derived is True                  # ...but the new signal fires
    rewritten = ["proc.", "sp.", "inline.", "wp.", "skip.", "auto."]
    checked, drift = _resume_replay_gate(
        _snap_view(rewritten),
        replay_prefix=PREFIX,
        expected_goal_hash="cafef00d",
        agent_has_rewound=derived,
    )
    assert checked is True
    assert drift == ""  # not killed


def _snap_view(history: list[str]):
    return WorkflowSessionSnapshot(
        session_dir="/tmp/x", exists=True, ok=True, history_exists=True,
        history_tactics=list(history), goal_hash="deadbeef",
        active_tool_mutates=None,
    )
