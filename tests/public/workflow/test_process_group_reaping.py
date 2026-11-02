"""A manager backend call stops the whole session_cli process group on timeout,
and the worker manifest lets a supervisor reap the run's EasyCrypt daemon.

Real processes, no EasyCrypt: Python children stand in for session_cli and the
``easycrypt`` it runs, and a script named ``ec_daemon.py`` for the daemon.
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


from workflow.proc_lifecycle import (  # noqa: E402
    reap_worker_pgid_manifest,
    record_daemon_socket,
    run_in_process_group,
)

pytestmark = pytest.mark.skipif(
    not hasattr(os, "killpg"), reason="needs POSIX process groups",
)

# session_cli stand-in: starts a grandchild, records its pid, prints, waits.
_PARENT = """
import subprocess, sys, time
grandchild = subprocess.Popen(
    [sys.executable, "-c", "import time; time.sleep(60)"],
    start_new_session=sys.argv[2] == "detached",
)
open(sys.argv[1], "w").write(str(grandchild.pid))
print("partial", flush=True)
time.sleep(60)
"""


def _gone(pid: int, within: float = 5.0) -> bool:
    deadline = time.monotonic() + within
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        time.sleep(0.05)
    return False


def _reaped(proc: subprocess.Popen, within: float = 5.0) -> bool:
    waiter = threading.Thread(target=proc.wait, daemon=True)
    waiter.start()
    waiter.join(within)
    return proc.poll() is not None


def _grandchild_pid(pid_file: Path) -> int:
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        if pid_file.exists() and pid_file.read_text().strip():
            return int(pid_file.read_text())
        time.sleep(0.05)
    raise AssertionError("the child never started its grandchild")


def test_a_finished_child_returns_like_subprocess_run() -> None:
    result = run_in_process_group(
        [sys.executable, "-c",
         "import sys; print('out'); print('err', file=sys.stderr); sys.exit(3)"],
        timeout=30, capture_output=True, text=True,
    )
    assert (result.returncode, result.stdout, result.stderr) == (3, "out\n", "err\n")


def test_a_timed_out_child_is_stopped_with_its_whole_group(tmp_path) -> None:
    pid_file = tmp_path / "grandchild.pid"
    with pytest.raises(subprocess.TimeoutExpired) as caught:
        run_in_process_group(
            [sys.executable, "-c", _PARENT, str(pid_file), "attached"],
            timeout=2.0, grace_seconds=1.0, capture_output=True, text=True,
        )
    assert "partial" in (caught.value.stdout or "")
    assert _gone(_grandchild_pid(pid_file))


def test_a_detached_grandchild_outlives_the_timeout(tmp_path) -> None:
    pid_file = tmp_path / "grandchild.pid"
    with pytest.raises(subprocess.TimeoutExpired):
        run_in_process_group(
            [sys.executable, "-c", _PARENT, str(pid_file), "detached"],
            timeout=2.0, grace_seconds=1.0, capture_output=True, text=True,
        )
    pid = _grandchild_pid(pid_file)
    try:
        assert not _gone(pid, within=0.5)
    finally:
        os.killpg(pid, signal.SIGKILL)


def _sleeper(script: Path) -> subprocess.Popen:
    script.write_text("import time\ntime.sleep(60)\n")
    return subprocess.Popen([sys.executable, str(script)], start_new_session=True)


def test_reaping_stops_the_recorded_daemon(tmp_path) -> None:
    socket_path = str(tmp_path / "d.sock")
    daemon = _sleeper(tmp_path / "ec_daemon.py")
    try:
        Path(socket_path + ".pid").write_text(str(daemon.pid))
        manifest = str(tmp_path / "process_groups")
        record_daemon_socket(manifest, socket_path)
        # Wait for the interpreter to show the script in its command line.
        time.sleep(0.3)
        assert reap_worker_pgid_manifest(manifest, grace_seconds=1.0) == 1
        assert _reaped(daemon)
        assert not os.path.exists(manifest)
    finally:
        if daemon.poll() is None:
            daemon.kill()


def test_reaping_leaves_a_recycled_daemon_pid_alone(tmp_path) -> None:
    socket_path = str(tmp_path / "d.sock")
    other = _sleeper(tmp_path / "unrelated.py")
    try:
        Path(socket_path + ".pid").write_text(str(other.pid))
        manifest = str(tmp_path / "process_groups")
        record_daemon_socket(manifest, socket_path)
        time.sleep(0.3)
        assert reap_worker_pgid_manifest(manifest, grace_seconds=1.0) == 0
        assert other.poll() is None
    finally:
        other.kill()
        other.wait()


def test_recording_without_a_manifest_is_a_no_op(tmp_path) -> None:
    record_daemon_socket(None, str(tmp_path / "d.sock"))
    record_daemon_socket("", str(tmp_path / "d.sock"))
    assert list(tmp_path.iterdir()) == []
