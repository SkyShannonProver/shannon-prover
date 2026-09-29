from __future__ import annotations

import time
from multiprocessing import Process
from pathlib import Path

from core.easycrypt.session_cli import _session_action_lock


def _append_line(path: Path, line: str) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def _lock_worker(
    session_dir: str,
    log_path: str,
    release_path: str,
    label: str,
    wait_for_release: bool,
) -> None:
    with _session_action_lock(Path(session_dir)):
        _append_line(Path(log_path), f"{label}:enter")
        if wait_for_release:
            release = Path(release_path)
            deadline = time.time() + 5
            while not release.exists() and time.time() < deadline:
                time.sleep(0.02)
        _append_line(Path(log_path), f"{label}:exit")


def test_session_action_lock_serializes_processes(tmp_path: Path) -> None:
    session_dir = tmp_path / "session"
    log_path = tmp_path / "lock.log"
    release_path = tmp_path / "release"

    first = Process(
        target=_lock_worker,
        args=(str(session_dir), str(log_path), str(release_path), "first", True),
    )
    second = Process(
        target=_lock_worker,
        args=(str(session_dir), str(log_path), str(release_path), "second", False),
    )

    first.start()
    deadline = time.time() + 5
    while (not log_path.exists() or "first:enter" not in log_path.read_text()) and time.time() < deadline:
        time.sleep(0.02)

    second.start()
    time.sleep(0.2)
    assert log_path.read_text(encoding="utf-8").splitlines() == ["first:enter"]

    release_path.touch()
    first.join(timeout=5)
    second.join(timeout=5)

    assert first.exitcode == 0
    assert second.exitcode == 0
    assert log_path.read_text(encoding="utf-8").splitlines() == [
        "first:enter",
        "first:exit",
        "second:enter",
        "second:exit",
    ]
