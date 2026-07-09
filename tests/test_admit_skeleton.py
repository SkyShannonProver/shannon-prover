"""Tests for the admit-skeleton composability probe logic (P3.2).

The transaction (admit_skeleton_probe) is live-validated on elgamal/cpa_ddh0
(see the design doc §9 live findings); here we unit-test its decision logic with
a mocked ReplSessionManager so it runs without EasyCrypt.
"""
from __future__ import annotations

import contextlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from workflow.proof_management.residual_signals import classify_call_subgoal  # noqa: E402
from workflow.proof_management.repl_session import ReplSessionManager  # noqa: E402


def test_classify_call_subgoal():
    # live-validated: call(I) spawns equiv oracle subgoals + a pRHL continuation
    assert classify_call_subgoal("equiv") == "oracle"
    assert classify_call_subgoal("pRHL") == "continuation"
    assert classify_call_subgoal("ambient") == "continuation"
    assert classify_call_subgoal("") == "continuation"


def _mock_repl(post_call_states, closer_goal_after, precond=("pRHL", 1)):
    repl = ReplSessionManager(
        file_path="eval/examples/elgamal.ec", lemma_name="cpa_ddh0",
        include_dir="x", session_tag="mock", node_id="mock",
    )
    calls: list = []
    repl._lock = contextlib.nullcontext()  # type: ignore[assignment]
    repl._run_backend = lambda label, args, actions, timeout=0: (  # type: ignore[assignment]
        calls.append((label, list(args))) or ""
    )
    # precond is the goal seen by the call-point precondition; then the post-call
    # states drive the admit loop + continuation check.
    it = iter([precond] + list(post_call_states))
    repl._skeleton_state_locked = lambda: next(it)  # type: ignore[assignment]
    repl._probe_goal_after_locked = lambda c: closer_goal_after  # type: ignore[assignment]
    repl._committed_len_locked = lambda: 0  # constant -> no rollback drift  # type: ignore[assignment]
    repl._skeleton_continuation_text_locked = (  # type: ignore[assignment]
        lambda: ("pRHL", {"side_tokens": ["a{1}", "b{2}"]})
    )
    return repl, calls


def test_admit_skeleton_refuses_non_call_point():
    # safety precondition: refuse to apply on an oracle/ambient subgoal (where
    # call(I) does not belong) — found by review/e2e (it corrupted the history).
    repl, calls = _mock_repl(post_call_states=[], closer_goal_after=1, precond=("equiv", 2))
    res = repl.admit_skeleton_probe("call (_: I).")
    assert res["applied"] is False
    assert "not_at_call_point" in (res["error"] or "")
    # nothing was committed or undone
    assert not any(c[0].startswith("skel") for c in calls)


def test_admit_skeleton_composable_when_continuation_closes():
    # call -> equiv oracle (admit) -> pRHL continuation that a closer discharges
    repl, calls = _mock_repl(
        post_call_states=[("equiv", 2), ("pRHL", 1), ("pRHL", 1)],
        closer_goal_after=0,  # a closer reduces 1 -> 0
    )
    res = repl.admit_skeleton_probe("call (_: I).")
    assert res["applied"] is True
    assert res["n_admitted"] == 1
    assert res["continuation_type"] == "pRHL"
    assert res["continuation_closed"] is True
    assert res["composable"] is True
    assert res["verdict"] == "composable"
    assert res["vacuous"] is False
    # rollback undoes every commit (call + admit + close = 3)
    assert sum(1 for c in calls if c[0] == "skel_undo") == 3


def test_admit_skeleton_inconclusive_on_prhl_continuation():
    # closer fails on a still-relational (pRHL) continuation: NOT a hard
    # "not composable" -> inconclusive (#1 fix: avoid the false negative).
    repl, calls = _mock_repl(
        post_call_states=[("equiv", 2), ("pRHL", 1), ("pRHL", 1)],
        closer_goal_after=1,  # 1 not < 1 -> no closure
    )
    res = repl.admit_skeleton_probe("call (_: I).")
    assert res["n_admitted"] == 1
    assert res["continuation_closed"] is False
    assert res["composable"] is False
    assert res["verdict"] == "inconclusive"   # pRHL residue = more work, not weak I
    assert res["vacuous"] is True
    assert res["residual_signals"]["side_tokens"] == ["a{1}", "b{2}"]
    assert sum(1 for c in calls if c[0] == "skel_undo") == 2


def test_admit_skeleton_likely_weak_invariant_on_ambient_residue():
    # ambient establish/derive residue that doesn't close, carrying a NON-frame
    # cross-side relation the invariant lacks -> likely_weak_invariant.
    repl, calls = _mock_repl(
        post_call_states=[("equiv", 2), ("ambient", 1), ("ambient", 1)],
        closer_goal_after=1,
    )
    repl._skeleton_continuation_text_locked = (  # type: ignore[assignment]
        lambda: ("ambient", {"side_tokens": ["badi{2}"]})  # non-frame
    )
    res = repl.admit_skeleton_probe("call (_: ={Mem.lc}).")  # frame = {Mem.lc}
    assert res["continuation_closed"] is False
    assert res["verdict"] == "likely_weak_invariant"


def test_admit_skeleton_feeds_hints():
    repl, calls = _mock_repl(
        post_call_states=[("equiv", 2), ("ambient", 1), ("ambient", 1)],
        closer_goal_after=0,  # a closer closes
    )
    res = repl.admit_skeleton_probe("call (_: I).", hints=("make_lbad1", "leq_make_lbad1"))
    assert res["hints_used"] == ["make_lbad1", "leq_make_lbad1"]
    assert res["verdict"] == "composable"


def _mock_unblock_repl(states, closer_goal_after):
    repl = ReplSessionManager(
        file_path="eval/examples/elgamal.ec", lemma_name="cpa_ddh0",
        include_dir="x", session_tag="mock", node_id="mock",
    )
    calls: list = []
    repl._lock = contextlib.nullcontext()  # type: ignore[assignment]
    repl._run_backend = lambda label, args, actions, timeout=0: (  # type: ignore[assignment]
        calls.append((label, list(args))) or ""
    )
    it = iter(states)
    repl._skeleton_state_locked = lambda: next(it)  # type: ignore[assignment]
    repl._probe_goal_after_locked = lambda c: closer_goal_after  # type: ignore[assignment]
    repl._committed_len_locked = lambda: 0  # type: ignore[assignment]
    repl._skeleton_continuation_text_locked = (  # type: ignore[assignment]
        lambda: ("equiv", {"side_tokens": ["x{1}"]})
    )
    return repl, calls


def test_unblock_probe_confirms_when_leaf_closes():
    # have conjunct -> admit -> a closer now discharges the leaf -> unblocks
    repl, calls = _mock_unblock_repl(
        states=[("equiv", 1), ("equiv", 1)], closer_goal_after=0,
    )
    res = repl.unblock_probe("inv_lbad1_i lbad1{1} ...")
    assert res["applied"] is True
    assert res["unblocks"] is True
    assert res["rollback_ok"] is True
    # the `have` and the `admit` are both undone
    assert sum(1 for c in calls if c[0] == "unblock_undo") == 2
    # the have introduced the conjunct as a hypothesis
    assert any("have _piece_h:" in " ".join(c[1]) for c in calls if c[0] == "unblock_have")


def test_unblock_probe_no_unblock_when_closer_fails():
    repl, calls = _mock_unblock_repl(
        states=[("equiv", 1), ("equiv", 1)], closer_goal_after=1,  # 1 not < 1
    )
    res = repl.unblock_probe("irrelevant {1}")
    assert res["applied"] is True
    assert res["unblocks"] is False
    assert res["residual_signals"]["side_tokens"] == ["x{1}"]


def test_unblock_probe_guards():
    assert ReplSessionManager(
        file_path="eval/examples/elgamal.ec", lemma_name="cpa_ddh0",
        include_dir="x", session_tag="mock", node_id="mock",
    ).unblock_probe("")["error"] == "empty_conjunct"
    repl, _ = _mock_unblock_repl(states=[("", 0)], closer_goal_after=0)
    assert repl.unblock_probe("x")["error"] == "no_open_goal"


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))
