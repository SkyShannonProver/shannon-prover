"""Coverage for proc_lifecycle.terminate_pgid_bounded — the single-PID bounded
pgid teardown shared by ec_services._hard_kill_ec_daemon (#3 step 4).

Drives real detached subprocesses (no EasyCrypt needed). A background reaper
thread waits on each Popen so that once the process dies the poll's
os.kill(pid, 0) starts raising and terminate_pgid_bounded returns promptly (the
production daemon is detached and reaped by init, so the same poll sees it gone).
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]

import workflow.proc_lifecycle as proc_lifecycle  # noqa: E402
from workflow.proc_lifecycle import (  # noqa: E402
    signal_group_ladder,
    terminate_pgid_bounded,
    terminate_subprocess_tree,
)


def _reaped(proc: subprocess.Popen, timeout: float = 3.0) -> bool:
    t = threading.Thread(target=lambda: proc.wait(), daemon=True)
    t.start()
    t.join(timeout)
    return proc.poll() is not None


@pytest.mark.skipif(not hasattr(subprocess, "Popen"), reason="needs subprocess")
def test_terminate_pgid_bounded_sigterm_path():
    """A normal process is stopped by the SIGTERM to its group."""
    proc = subprocess.Popen(["sleep", "30"], start_new_session=True)
    reaper = threading.Thread(target=lambda: proc.wait(), daemon=True)
    reaper.start()
    t0 = time.monotonic()
    terminate_pgid_bounded(proc.pid, grace_seconds=5.0)
    reaper.join(2.0)
    assert proc.poll() is not None            # exited
    assert time.monotonic() - t0 < 4.0        # well within the grace window
    assert proc.returncode < 0                # killed by a signal (SIGTERM)


def test_terminate_pgid_bounded_escalates_to_sigkill():
    """A process that IGNORES SIGTERM is escalated to SIGKILL after the bounded
    grace window (the wait must not be unbounded)."""
    code = "import signal, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(30)"
    proc = subprocess.Popen([sys.executable, "-c", code], start_new_session=True)
    reaper = threading.Thread(target=lambda: proc.wait(), daemon=True)
    reaper.start()
    time.sleep(0.2)  # let the handler install
    t0 = time.monotonic()
    terminate_pgid_bounded(proc.pid, grace_seconds=0.5)
    reaper.join(2.0)
    assert proc.poll() is not None
    assert proc.returncode == -9              # SIGKILL (SIGTERM was ignored)
    # bounded: SIGKILL fired after ~grace, not blocked indefinitely
    assert 0.4 < time.monotonic() - t0 < 3.0


def test_terminate_pgid_bounded_dead_pid_is_safe():
    """Signalling an already-exited process is a no-op, not a crash."""
    proc = subprocess.Popen(["sleep", "0.05"], start_new_session=True)
    assert _reaped(proc)
    terminate_pgid_bounded(proc.pid, grace_seconds=0.5)  # must not raise


def _record_group_signals(monkeypatch) -> list[tuple[int, int]]:
    """Record killpg calls instead of delivering them (a group signal to the
    test runner's own group would terminate pytest itself)."""
    calls: list[tuple[int, int]] = []
    monkeypatch.setattr(
        proc_lifecycle.os,
        "killpg",
        lambda pgid, sig: calls.append((pgid, sig)),
    )
    return calls


def test_terminate_subprocess_tree_never_signals_the_callers_group(monkeypatch):
    """A child that is not a session leader shares the caller's process group.
    Stopping it must signal only its PID, never the caller's own group."""
    proc = subprocess.Popen(["sleep", "30"])  # same group as this process
    group_calls = _record_group_signals(monkeypatch)
    try:
        terminate_subprocess_tree(proc, grace_seconds=3.0)
        assert os.getpgrp() not in {pgid for pgid, _sig in group_calls}
        assert proc.poll() is not None
        assert proc.returncode == -signal.SIGTERM
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()


def test_terminate_pgid_bounded_never_signals_the_callers_group(monkeypatch):
    proc = subprocess.Popen(["sleep", "30"])  # same group as this process
    reaper = threading.Thread(target=lambda: proc.wait(), daemon=True)
    reaper.start()
    group_calls = _record_group_signals(monkeypatch)
    try:
        terminate_pgid_bounded(proc.pid, grace_seconds=3.0)
        reaper.join(2.0)
        assert os.getpgrp() not in {pgid for pgid, _sig in group_calls}
        assert proc.poll() is not None
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()


def test_terminate_subprocess_tree_still_signals_a_session_leader_group(
    monkeypatch,
):
    proc = subprocess.Popen(["sleep", "30"], start_new_session=True)
    group_calls = _record_group_signals(monkeypatch)
    try:
        terminate_subprocess_tree(proc, grace_seconds=0.2)
        assert group_calls and group_calls[0] == (proc.pid, signal.SIGTERM)
    finally:
        proc.kill()
        proc.wait()


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def test_signal_group_ladder_stops_at_the_first_signal_the_child_honours():
    proc = subprocess.Popen(["sleep", "30"], start_new_session=True)
    try:
        t0 = time.monotonic()
        assert signal_group_ladder(
            proc, ((signal.SIGTERM, 5.0), (signal.SIGKILL, 5.0))
        ) == -signal.SIGTERM
        assert time.monotonic() - t0 < 3.0
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()


def test_signal_group_ladder_escalates_and_reaches_the_whole_group():
    """Child and grandchild ignore SIGINT and SIGTERM (an ignored disposition
    survives exec), so only the final SIGKILL to the group stops both."""
    code = (
        "import signal, subprocess, time\n"
        "signal.signal(signal.SIGINT, signal.SIG_IGN)\n"
        "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
        "grandchild = subprocess.Popen(['sleep', '30'])\n"
        "print(grandchild.pid, flush=True)\n"
        "time.sleep(30)\n"
    )
    proc = subprocess.Popen(
        [sys.executable, "-c", code],
        start_new_session=True,
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        grandchild = int(proc.stdout.readline())
        t0 = time.monotonic()
        status = signal_group_ladder(
            proc,
            ((signal.SIGINT, 0.3), (signal.SIGTERM, 0.3), (signal.SIGKILL, 5.0)),
        )
        elapsed = time.monotonic() - t0
        assert status == -signal.SIGKILL
        assert 0.5 < elapsed < 4.0
        deadline = time.monotonic() + 3.0
        while _alive(grandchild) and time.monotonic() < deadline:
            time.sleep(0.05)
        assert not _alive(grandchild)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
        proc.stdout.close()


def test_signal_group_ladder_does_not_signal_an_exited_child(monkeypatch):
    proc = subprocess.Popen(["true"], start_new_session=True)
    proc.wait()
    group_calls = _record_group_signals(monkeypatch)
    assert signal_group_ladder(proc, ((signal.SIGTERM, 1.0),)) == 0
    assert group_calls == []
