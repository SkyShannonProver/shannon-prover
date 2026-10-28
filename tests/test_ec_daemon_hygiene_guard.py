"""The suite-level EasyCrypt daemon guard in ``tests/conftest.py`` must hold.

``session_cli.py`` spawns ``ec_daemon.py`` detached and production leaves it
running, so a test that forgets it leaves a PID-1 orphan behind. An inner
pytest run loads the suite conftest and starts real detached daemons the same
way (through a parent that exits). A daemon at the module's default socket
must be stopped silently; a daemon of this checkout anywhere else must fail
its module but keep running, since it may belong to a live prover run. No EasyCrypt process is needed: the daemon only listens.
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import textwrap
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_INNER_CONFTEST = textwrap.dedent("""
    import importlib.util
    import sys

    _spec = importlib.util.spec_from_file_location(
        "shannon_suite_conftest", {conftest!r},
    )
    _suite = sys.modules[_spec.name] = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_suite)
    _ec_daemon_socket_root = _suite._ec_daemon_socket_root
    _ec_daemon_hygiene = _suite._ec_daemon_hygiene
""")

_INNER_TEST = textwrap.dedent("""
    import os
    import subprocess
    import sys
    import time

    _SPAWN = (
        "import subprocess, sys; print(subprocess.Popen("
        "[sys.executable, sys.argv[1], '--socket', sys.argv[2]], "
        "stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, "
        "start_new_session=True).pid)"
    )


    def test_spawn_detached_daemon():
        socket_path = {socket!r} or os.environ["EC_DAEMON_SOCKET"]
        spawned = subprocess.run(
            [sys.executable, "-c", _SPAWN, {daemon!r}, socket_path],
            capture_output=True, text=True, check=True,
        )
        with open({pid_file!r}, "w") as handle:
            handle.write(spawned.stdout.strip())
        deadline = time.monotonic() + 10
        while not os.path.exists(socket_path):
            assert time.monotonic() < deadline, "daemon never listened"
            time.sleep(0.05)
""")


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def _run_inner(
    tmp_path: Path,
    socket_path: str | None,
    *,
    expect_reaped: bool = True,
) -> tuple[str, int]:
    inner = tmp_path / "inner"
    inner.mkdir()
    pid_file = tmp_path / "daemon.pid"
    (inner / "conftest.py").write_text(_INNER_CONFTEST.format(
        conftest=str(ROOT / "tests" / "conftest.py"),
    ))
    (inner / "test_inner_daemon.py").write_text(_INNER_TEST.format(
        socket=socket_path,
        daemon=str(ROOT / "core" / "easycrypt" / "ec_daemon.py"),
        pid_file=str(pid_file),
    ))
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
         str(inner)],
        cwd=inner, capture_output=True, text=True, timeout=120,
    )
    pid = int(pid_file.read_text())
    try:
        assert _alive(pid) is not expect_reaped, (
            "guard left the inner daemon running" if expect_reaped
            else "guard stopped a daemon it does not own"
        )
    finally:
        if _alive(pid):
            os.killpg(pid, signal.SIGKILL)
    return result.stdout + result.stderr, result.returncode


def test_daemon_at_module_default_socket_is_stopped(tmp_path: Path) -> None:
    output, returncode = _run_inner(tmp_path, socket_path=None)
    assert returncode == 0, output
    assert "1 passed" in output


def test_daemon_of_this_checkout_elsewhere_fails_but_is_left_running(
    tmp_path: Path,
) -> None:
    # It may belong to a prover run in this checkout: report it, never kill it.
    socket_path = f"/tmp/shannon-guard-{uuid.uuid4().hex[:8]}.sock"
    try:
        output, returncode = _run_inner(
            tmp_path, socket_path=socket_path, expect_reaped=False,
        )
    finally:
        for leftover in (socket_path, socket_path + ".pid"):
            if os.path.exists(leftover):
                os.unlink(leftover)
    assert returncode != 0, output
    assert "1 passed, 1 error" in output
    assert "started outside this run's sockets" in output
    assert f"socket={socket_path}" in output
