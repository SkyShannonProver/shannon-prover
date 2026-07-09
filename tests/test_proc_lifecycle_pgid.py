"""Coverage for proc_lifecycle.terminate_pgid_bounded — the single-PID bounded
pgid teardown shared by prover._hard_kill_ec_daemon (#3 step 4).

Drives real detached subprocesses (no EasyCrypt needed). A background reaper
thread waits on each Popen so that once the process dies the poll's
os.kill(pid, 0) starts raising and terminate_pgid_bounded returns promptly (the
production daemon is detached and reaped by init, so the same poll sees it gone).
"""
from __future__ import annotations

import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from workflow.proc_lifecycle import terminate_pgid_bounded  # noqa: E402


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


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
