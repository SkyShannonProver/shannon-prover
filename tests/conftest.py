"""Pytest auto-loaded config for the tests/ tree.

Ensures the project root is on ``sys.path`` so pytest-style test
files can ``from workflow.agents import prover`` etc. without each
test file having to repeat the path-setup boilerplate.

Standalone test scripts (``python3 tests/test_foo.py``) typically do
their own ``sys.path.insert(0, ROOT)`` — this conftest only matters
when pytest is the runner.

It also owns the lifetime of every EasyCrypt daemon the suite starts; see
``_ec_daemon_hygiene``.
"""
from __future__ import annotations

import itertools
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# ---------------------------------------------------------------------------
# EasyCrypt daemon hygiene
# ---------------------------------------------------------------------------
#
# ``session_cli.py`` lazily spawns a detached ``ec_daemon.py``
# (``start_new_session=True``) at the default socket and, by design, leaves it
# running for later short-lived calls; only a prover run's cleanup
# (``ec_services._shutdown_ec_daemon``) stops it.  A test that drives
# ``session_cli`` has no prover run, so its daemon outlived pytest as a PID-1
# orphan, and the per-checkout default socket let a later run reuse a daemon
# still executing older code.  The suite therefore owns that lifecycle without
# changing it: every test module gets a fresh run-private default socket, its
# daemon is stopped through the production shutdown path when the module
# finishes, and a guard fails the module if any daemon it started survives.

_DAEMON_SCRIPT = ROOT / "core" / "easycrypt" / "ec_daemon.py"
_SOCKET_ROOT_PREFIX = "shannon-pytest-ec-"
_LEAK_GRACE_SECONDS = 3.0
_module_socket_index = itertools.count()


@dataclass(frozen=True)
class _Daemon:
    pid: int
    ppid: int
    socket: str
    command: str


def _live_ec_daemons() -> dict[int, _Daemon]:
    # Where the process table cannot be listed (no ps, a sandbox), the guard
    # sees no daemons and stays out of the way; it never fails a test itself.
    try:
        result = subprocess.run(
            ["ps", "-A", "-ww", "-o", "pid=,ppid=,command="],
            capture_output=True, text=True, check=False,
        )
    except OSError:
        return {}
    if result.returncode != 0:
        return {}
    listing = result.stdout
    daemons: dict[int, _Daemon] = {}
    for line in listing.splitlines():
        fields = line.split(None, 2)
        if len(fields) != 3 or "ec_daemon.py" not in fields[2]:
            continue
        argv = fields[2].split()
        if "python" not in Path(argv[0]).name or not any(
            arg.endswith("ec_daemon.py") for arg in argv[1:3]
        ):
            continue
        socket = ""
        if "--socket" in argv[:-1]:
            socket = argv[argv.index("--socket") + 1]
        pid = int(fields[0])
        daemons[pid] = _Daemon(pid, int(fields[1]), socket, fields[2])
    return daemons


def _started_by_this_run(daemon: _Daemon, socket_root: Path) -> bool:
    return (
        Path(daemon.socket).parent == socket_root
        or daemon.ppid == os.getpid()
    )


def _from_this_checkout_elsewhere(daemon: _Daemon, socket_root: Path) -> bool:
    """A daemon of this checkout's code outside every pytest socket root.

    Either a test bypassed ``EC_DAEMON_SOCKET`` or a prover run is active in
    this checkout.  The guard cannot tell which, so it reports the daemon
    and leaves it running: stopping it could kill a live run.
    """

    if Path(daemon.socket).parent.name.startswith(_SOCKET_ROOT_PREFIX):
        return False  # a pytest run in this checkout owns it
    return (
        not _started_by_this_run(daemon, socket_root)
        and str(_DAEMON_SCRIPT) in daemon.command
    )


def _reap(daemon: _Daemon) -> None:
    from workflow.proc_lifecycle import terminate_pgid_bounded

    try:
        session_leader = os.getpgid(daemon.pid) == daemon.pid
    except OSError:
        return
    if session_leader:
        # A detached daemon leads its own group of easycrypt/why3 children.
        terminate_pgid_bounded(daemon.pid, grace_seconds=3.0)
        return
    try:
        os.kill(daemon.pid, signal.SIGKILL)
    except OSError:
        pass


@pytest.fixture(scope="session")
def _ec_daemon_socket_root():
    # /tmp plus short per-module names keep sockets below the AF_UNIX limit.
    root = Path(tempfile.mkdtemp(prefix=_SOCKET_ROOT_PREFIX, dir="/tmp"))
    yield root
    shutil.rmtree(root, ignore_errors=True)


@pytest.fixture(scope="module", autouse=True)
def _ec_daemon_hygiene(request, _ec_daemon_socket_root):
    socket_root = _ec_daemon_socket_root
    preexisting = set(_live_ec_daemons())
    socket_path = str(socket_root / f"{next(_module_socket_index)}.sock")
    previous = os.environ.get("EC_DAEMON_SOCKET")
    os.environ["EC_DAEMON_SOCKET"] = socket_path

    yield

    if previous is None:
        os.environ.pop("EC_DAEMON_SOCKET", None)
    else:
        os.environ["EC_DAEMON_SOCKET"] = previous
    if os.path.exists(socket_path):
        from workflow.agents.ec_services import _shutdown_ec_daemon

        _shutdown_ec_daemon(
            reason=f"pytest module {request.module.__name__}",
            socket_path=socket_path,
        )

    deadline = time.monotonic() + _LEAK_GRACE_SECONDS
    while True:
        new = [
            daemon for pid, daemon in _live_ec_daemons().items()
            if pid not in preexisting
        ]
        leaked = [d for d in new if _started_by_this_run(d, socket_root)]
        foreign = [d for d in new if _from_this_checkout_elsewhere(d, socket_root)]
        if not (leaked or foreign) or time.monotonic() >= deadline:
            break
        time.sleep(0.2)
    for daemon in leaked:
        _reap(daemon)
    problems = []
    if leaked:
        problems.append(
            f"{request.module.__name__} left EasyCrypt daemon(s) running "
            f"(reaped now); stop every daemon a test starts:\n"
            + _describe(leaked)
        )
    if foreign:
        problems.append(
            "EasyCrypt daemon(s) of this checkout started outside this run's "
            "sockets during "
            f"{request.module.__name__} (left running: a test bypassed "
            "EC_DAEMON_SOCKET, or a prover run is active in this checkout):\n"
            + _describe(foreign)
        )
    if problems:
        pytest.fail("\n".join(problems), pytrace=False)


def _describe(daemons: list[_Daemon]) -> str:
    return "\n".join(
        f"  pid={d.pid} ppid={d.ppid} socket={d.socket or '?'}"
        for d in daemons
    )
