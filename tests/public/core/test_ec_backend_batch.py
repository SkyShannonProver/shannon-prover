"""Batch EasyCrypt runs are bounded and cannot write session files late.

The manager kills only the session CLI on its own timeout, so a batch EC child
outlives it. That child used to hold ``current.out`` open and overwrote it after
the next command had rewritten the file.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import core.easycrypt.ec_backend as ec_backend

ROOT = Path(__file__).resolve().parents[3]

SLOW_EC = r'''
import os, sys, time
open(sys.argv[1], "w").write(str(os.getpid()))
sys.stdin.read()
sys.stdout.write("partial output\n")
sys.stdout.flush()
time.sleep(float(sys.argv[2]))
sys.stdout.write("LATE REPLY\n")
sys.stdout.flush()
'''

CLI = r'''
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import core.easycrypt.ec_backend as eb
fake, pid_file, session = sys.argv[2], sys.argv[3], Path(sys.argv[4])
eb.emacs_command = lambda include_dirs, sock: [sys.executable, fake, pid_file, "1.0"]
eb.get_ec_env = lambda: None
eb.BatchBackend(session).run(session / "history.ec", session / "current.out", [])
'''


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def test_an_orphaned_batch_run_cannot_overwrite_current_out(tmp_path) -> None:
    fake = tmp_path / "slow_ec.py"
    fake.write_text(SLOW_EC, encoding="utf-8")
    cli = tmp_path / "cli.py"
    cli.write_text(CLI, encoding="utf-8")
    session = tmp_path / "session"
    session.mkdir()
    (session / "history.ec").write_text("trivial.\n", encoding="utf-8")
    pid_file = tmp_path / "ec.pid"

    try:
        subprocess.run(
            [sys.executable, str(cli), str(ROOT), str(fake), str(pid_file), str(session)],
            timeout=0.6,
        )
    except subprocess.TimeoutExpired:
        pass  # the manager gives up and kills the CLI, not its EC child
    (session / "current.out").write_text("NEXT COMMAND\n", encoding="utf-8")
    pid = int(pid_file.read_text(encoding="utf-8"))
    deadline = time.monotonic() + 5.0
    while _alive(pid) and time.monotonic() < deadline:
        time.sleep(0.05)

    assert (session / "current.out").read_text(encoding="utf-8") == "NEXT COMMAND\n"


def test_a_batch_run_past_its_timeout_is_killed_and_reported(tmp_path, monkeypatch) -> None:
    fake = tmp_path / "slow_ec.py"
    fake.write_text(SLOW_EC, encoding="utf-8")
    pid_file = tmp_path / "ec.pid"
    monkeypatch.setattr(
        ec_backend, "emacs_command",
        lambda include_dirs, sock: [sys.executable, str(fake), str(pid_file), "30"],
    )
    monkeypatch.setattr(ec_backend, "get_ec_env", lambda: None)
    (tmp_path / "history.ec").write_text("trivial.\n", encoding="utf-8")
    output = tmp_path / "current.out"

    started = time.monotonic()
    returncode = ec_backend.BatchBackend(tmp_path).run(
        tmp_path / "history.ec", output, [], timeout=0.5,
    )

    assert time.monotonic() - started < 5.0
    assert returncode != 0
    assert not _alive(int(pid_file.read_text(encoding="utf-8")))
    text = output.read_text(encoding="utf-8")
    assert text.startswith("partial output\n")
    assert "[error] EasyCrypt batch run timed out after 0.5s" in text
