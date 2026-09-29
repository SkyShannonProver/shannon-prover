#!/usr/bin/env python3
"""Integration tests for ec_daemon — requires `easycrypt` on PATH.

Run with: python3 tests/test_ec_daemon.py (no pytest needed)

The daemon is started as a subprocess on an ephemeral socket path.
Each test starts+stops its own daemon for isolation. Timing metrics
are printed for observability, not asserted as hard thresholds
(timing varies on developer machines).
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
EC_DIR = REPO_ROOT / "core" / "easycrypt"

import _pathsetup  # noqa: F401,E402  (repo root on sys.path)
from core.easycrypt.ec_daemon_client import ECDaemonClient, ECDaemonError  # noqa: E402


MINIMAL_EC = """require import AllCore.

lemma foo (x : int) : x = x.
proof.
admit.
qed.

lemma bar (x : int) : 0 = 0.
proof.
admit.
qed.
"""

SUB_UNFOLD_EC = """require import AllCore.

module type INNER = { proc f() : int }.
module Inner : INNER = { proc f() : int = { return 42; } }.
module Wrap (I : INNER) = { proc f() : int = { var r; r <@ I.f(); return r; } }.

equiv inner_eq : Inner.f ~ Inner.f : true ==> ={res}.
proof.
proc. auto.
qed.

equiv test_unfold : Wrap(Inner).f ~ Wrap(Inner).f : true ==> ={res}.
proof.
admit.
qed.
"""


def _write_ec(content: str) -> Path:
    """Write ``content`` to a temp .ec file, return the path."""
    fd, name = tempfile.mkstemp(suffix=".ec")
    os.close(fd)
    p = Path(name)
    p.write_text(content)
    return p


class DaemonHarness:
    """Start/stop a daemon on a per-test socket."""

    def __init__(self):
        self.sock = f"/tmp/ec_daemon_test_{uuid.uuid4().hex[:8]}.sock"
        self.proc: subprocess.Popen | None = None

    def start(self):
        # Make sure socket is clean
        try:
            os.unlink(self.sock)
        except FileNotFoundError:
            pass
        env = dict(os.environ)
        self.proc = subprocess.Popen(
            [sys.executable, str(EC_DIR / "ec_daemon.py"),
             "--socket", self.sock, "--log-level", "WARNING"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env,
        )
        # Wait for socket to appear
        for _ in range(60):
            if os.path.exists(self.sock):
                return
            time.sleep(0.1)
        raise RuntimeError("daemon did not create socket within 6s")

    def stop(self):
        cli = ECDaemonClient(self.sock)
        try:
            cli.shutdown()
        except Exception:
            pass
        if self.proc is not None:
            try:
                self.proc.wait(timeout=3.0)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait()
        try:
            os.unlink(self.sock)
        except FileNotFoundError:
            pass

    def client(self) -> ECDaemonClient:
        return ECDaemonClient(self.sock)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_basic_open_commit_close():
    h = DaemonHarness()
    h.start()
    try:
        ec_file = _write_ec(MINIMAL_EC)
        cli = h.client()
        res = cli.open_session("s1", str(ec_file),
                               ["easycrypt-src/theories"], "foo")
        assert res["remaining"] == 1, f"remaining={res['remaining']}"
        assert not res["is_closed"]

        c = cli.commit("s1", "trivial.")
        assert c["accepted"], f"trivial should succeed, got {c}"
        assert c["goal_after"]["is_closed"]

        q = cli.commit("s1", "qed.")
        assert q["accepted"]
        assert "+ added lemma" in q["raw_output"]

        cli.close_session("s1")
        assert cli.list_sessions() == []
        print("  ✓ basic_open_commit_close")
    finally:
        ec_file.unlink(missing_ok=True)
        h.stop()


def test_try_tactic_is_rollback():
    """After try_tactic the main session's state MUST be unchanged."""
    h = DaemonHarness()
    h.start()
    try:
        ec_file = _write_ec(MINIMAL_EC)
        cli = h.client()
        cli.open_session("s1", str(ec_file),
                         ["easycrypt-src/theories"], "foo")
        # Try trivial — would close the goal if committed
        t = cli.try_tactic("s1", "trivial.")
        assert t["accepted"]
        assert t["goal_after"]["is_closed"]
        # Session unchanged: commit trivial should ALSO work (goal
        # is still open because try was rolled back)
        c = cli.commit("s1", "trivial.")
        assert c["accepted"]
        assert c["goal_after"]["is_closed"]
        cli.commit("s1", "qed.")
        cli.close_session("s1")
        print("  ✓ try_tactic_is_rollback")
    finally:
        ec_file.unlink(missing_ok=True)
        h.stop()


def test_try_failed_tactic_clean_error():
    h = DaemonHarness()
    h.start()
    try:
        ec_file = _write_ec(MINIMAL_EC)
        cli = h.client()
        cli.open_session("s1", str(ec_file),
                         ["easycrypt-src/theories"], "foo")
        # Bogus lemma — should fail cleanly, session unaffected
        t = cli.try_tactic("s1", "apply nonexistent_lemma.")
        assert not t["accepted"]
        assert t["error"] is not None
        assert t["error"]["kind"] == "unknown_lemma"
        # Session still open — commit trivial works
        c = cli.commit("s1", "trivial.")
        assert c["accepted"]
        cli.close_session("s1")
        print("  ✓ try_failed_tactic_clean_error")
    finally:
        ec_file.unlink(missing_ok=True)
        h.stop()


def test_unfold_case_try_call():
    """On the synthetic Wrap(Inner).f ~ Wrap(Inner).f goal, the UNFOLD
    plan from pivot_applicability is `proc. call inner_eq. auto.`.
    Verify each step is accepted as try_tactic (after previous commits)."""
    h = DaemonHarness()
    h.start()
    try:
        ec_file = _write_ec(SUB_UNFOLD_EC)
        cli = h.client()
        res = cli.open_session("u", str(ec_file),
                               ["easycrypt-src/theories"], "test_unfold")
        assert res["remaining"] == 1
        # Direct apply of inner_eq should FAIL here (wrapper mismatch
        # at the bare-equiv level — but structurally Inner is inside
        # Wrap(Inner); the right move is proc+call).
        t = cli.try_tactic("u", "apply inner_eq.")
        assert not t["accepted"], "apply at bare Wrap level should fail"
        # The UNFOLD plan:
        cli.commit("u", "proc.")
        c = cli.commit("u", "call inner_eq.")
        assert c["accepted"], f"call inner_eq should succeed post-proc: {c}"
        c = cli.commit("u", "auto.")
        assert c["accepted"]
        assert c["goal_after"]["is_closed"]
        cli.commit("u", "qed.")
        cli.close_session("u")
        print("  ✓ unfold_case_try_call")
    finally:
        ec_file.unlink(missing_ok=True)
        h.stop()


def test_concurrent_sessions():
    """Two sessions for different lemmas in the same file run in
    parallel. Commits on one don't affect the other."""
    h = DaemonHarness()
    h.start()
    try:
        ec_file = _write_ec(MINIMAL_EC)
        cli = h.client()
        # Open two sessions in parallel (different lemmas)
        res_a: dict = {}
        res_b: dict = {}
        def open_a():
            res_a["t0"] = time.time()
            res_a["out"] = cli.open_session(
                "a", str(ec_file), ["easycrypt-src/theories"], "foo",
            )
            res_a["t1"] = time.time()
        def open_b():
            res_b["t0"] = time.time()
            res_b["out"] = cli.open_session(
                "b", str(ec_file), ["easycrypt-src/theories"], "bar",
            )
            res_b["t1"] = time.time()
        ta = threading.Thread(target=open_a); tb = threading.Thread(target=open_b)
        ta.start(); tb.start(); ta.join(); tb.join()

        ids = set(cli.list_sessions())
        assert ids == {"a", "b"}, ids
        assert res_a["out"]["remaining"] == 1
        assert res_b["out"]["remaining"] == 1

        # Commits are independent
        cli.commit("a", "trivial.")
        cli.commit("a", "qed.")
        # Session b unchanged
        cli.commit("b", "trivial.")
        cli.commit("b", "qed.")

        cli.close_session("a")
        cli.close_session("b")
        print("  ✓ concurrent_sessions")
    finally:
        ec_file.unlink(missing_ok=True)
        h.stop()


def test_session_isolation_on_try():
    """A try on session A must not affect session B's state."""
    h = DaemonHarness()
    h.start()
    try:
        ec_file = _write_ec(MINIMAL_EC)
        cli = h.client()
        cli.open_session("a", str(ec_file),
                         ["easycrypt-src/theories"], "foo")
        cli.open_session("b", str(ec_file),
                         ["easycrypt-src/theories"], "bar")
        # Try trivial on a; should not affect b
        cli.try_tactic("a", "trivial.")
        # b still needs to go through its own commit
        c = cli.commit("b", "trivial.")
        assert c["accepted"]
        assert c["goal_after"]["is_closed"]
        cli.close_session("a")
        cli.close_session("b")
        print("  ✓ session_isolation_on_try")
    finally:
        ec_file.unlink(missing_ok=True)
        h.stop()


def test_batch_try():
    h = DaemonHarness()
    h.start()
    try:
        ec_file = _write_ec(MINIMAL_EC)
        cli = h.client()
        cli.open_session("s", str(ec_file),
                         ["easycrypt-src/theories"], "foo")
        results = cli.batch_try(
            "s",
            ["trivial.",
             "apply nonexistent_lemma.",
             "reflexivity."],
        )
        assert len(results) == 3
        assert results[0]["accepted"]
        assert not results[1]["accepted"]
        assert results[1]["error"]["kind"] == "unknown_lemma"
        # reflexivity. should succeed too
        assert results[2]["accepted"]
        # session still unchanged — commit trivial should work
        c = cli.commit("s", "trivial.")
        assert c["accepted"]
        cli.close_session("s")
        print("  ✓ batch_try")
    finally:
        ec_file.unlink(missing_ok=True)
        h.stop()


def test_double_open_rejected():
    h = DaemonHarness()
    h.start()
    try:
        ec_file = _write_ec(MINIMAL_EC)
        cli = h.client()
        cli.open_session("dup", str(ec_file),
                         ["easycrypt-src/theories"], "foo")
        ok_error = False
        try:
            cli.open_session("dup", str(ec_file),
                             ["easycrypt-src/theories"], "foo")
        except ECDaemonError:
            ok_error = True
        assert ok_error, "re-opening same session id should error"
        cli.close_session("dup")
        print("  ✓ double_open_rejected")
    finally:
        ec_file.unlink(missing_ok=True)
        h.stop()


# ---------------------------------------------------------------------------

TESTS = [
    test_basic_open_commit_close,
    test_try_tactic_is_rollback,
    test_try_failed_tactic_clean_error,
    test_unfold_case_try_call,
    test_concurrent_sessions,
    test_session_isolation_on_try,
    test_batch_try,
    test_double_open_rejected,
]


def main():
    print("Running ec_daemon integration tests")
    print("  (requires `easycrypt` on PATH via opam switch)")
    print()
    failed = 0
    for fn in TESTS:
        try:
            fn()
        except Exception as e:
            failed += 1
            print(f"  ✗ {fn.__name__}: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
    print()
    print(f"{len(TESTS) - failed}/{len(TESTS)} tests passed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
