from __future__ import annotations

import os
from pathlib import Path

from core.easycrypt import ec_daemon
from core.easycrypt import ec_daemon_client
from workflow.agents import ec_services, prover


def test_ec_daemon_exposes_lifecycle_methods() -> None:
    assert ec_daemon._METHOD_TABLE["close_session"] is ec_daemon._h_close
    assert ec_daemon._METHOD_TABLE["list_sessions"] is ec_daemon._h_list
    assert ec_daemon._METHOD_TABLE["shutdown"] is ec_daemon._h_shutdown


def test_configure_run_ec_daemon_socket_prefers_repo_local_when_safe(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(ec_services, "_PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(ec_services, "_AF_UNIX_SOCKET_PATH_LIMIT", 10_000)
    monkeypatch.delenv("EC_DAEMON_SOCKET", raising=False)
    run_dir = tmp_path / "workflow" / "runs" / "run" / "iteration_1"
    run_dir.mkdir(parents=True)

    socket_path = prover._configure_run_ec_daemon_socket(run_dir)

    assert socket_path.startswith(str(tmp_path / "tmp" / "ec_daemons"))
    assert socket_path.endswith(".sock")
    assert len(Path(socket_path).name) < 32
    assert os.environ["EC_DAEMON_SOCKET"] == socket_path


def test_configure_run_ec_daemon_socket_prefers_git_common_root_for_worktree(
    tmp_path: Path,
    monkeypatch,
) -> None:
    main_root = tmp_path / "repo"
    worktree_root = main_root / ".worktrees" / "eval-short"
    run_dir = worktree_root / "artifacts" / "eval_suite" / "run"
    run_dir.mkdir(parents=True)

    monkeypatch.setattr(ec_services, "_PROJECT_ROOT", worktree_root)
    monkeypatch.setattr(ec_services, "_AF_UNIX_SOCKET_PATH_LIMIT", 10_000)
    monkeypatch.setattr(ec_services, "_git_common_project_root", lambda: main_root)
    monkeypatch.delenv("EC_DAEMON_SOCKET", raising=False)

    socket_path = prover._configure_run_ec_daemon_socket(run_dir)

    assert socket_path.startswith(str(main_root / "tmp" / "ec_daemons"))
    assert os.environ["EC_DAEMON_SOCKET"] == socket_path


def test_configure_run_ec_daemon_socket_uses_git_common_root_for_long_worktree(
    tmp_path: Path,
    monkeypatch,
) -> None:
    main_root = tmp_path / "repo"
    worktree_root = (
        main_root
        / "worktrees"
        / "eval-20260521-203628-b0b8e9eb-medium-nav-upgrade"
    )
    run_dir = worktree_root / "artifacts" / "eval_suite" / "run" / "iteration_1"
    socket_name = "ec_000000000000.sock"
    safe_socket = main_root / "tmp" / "ec_daemons" / socket_name
    unsafe_socket = worktree_root / "tmp" / "ec_daemons" / socket_name
    limit = len(os.fsencode(str(safe_socket))) + 5

    assert len(os.fsencode(str(unsafe_socket))) >= limit
    monkeypatch.setattr(ec_services, "_PROJECT_ROOT", worktree_root)
    monkeypatch.setattr(ec_services, "_AF_UNIX_SOCKET_PATH_LIMIT", limit)
    monkeypatch.setattr(ec_services, "_git_common_project_root", lambda: main_root)
    monkeypatch.delenv("EC_DAEMON_SOCKET", raising=False)

    socket_path = prover._configure_run_ec_daemon_socket(run_dir)

    assert socket_path.startswith(str(main_root / "tmp" / "ec_daemons"))
    assert len(os.fsencode(socket_path)) < limit
    assert os.environ["EC_DAEMON_SOCKET"] == socket_path


def test_shutdown_ec_daemon_removes_stale_socket(tmp_path: Path) -> None:
    sock = tmp_path / "ec_daemon.sock"
    lock = tmp_path / "ec_daemon.sock.spawn_lock"
    sock.write_text("not a unix socket", encoding="utf-8")
    lock.write_text("old lock", encoding="utf-8")

    stopped = prover._shutdown_ec_daemon(socket_path=str(sock), wait_seconds=0)

    assert stopped is False
    assert not sock.exists()
    assert not lock.exists()


def test_shutdown_repo_ec_daemons_scans_repo_socket_dir(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(ec_services, "_PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(ec_services, "_AF_UNIX_SOCKET_PATH_LIMIT", 10_000)
    socket_root = tmp_path / "tmp" / "ec_daemons"
    socket_root.mkdir(parents=True)
    for name in ("b.sock", "a.sock", "ignore.txt"):
        (socket_root / name).write_text("", encoding="utf-8")
    (socket_root / "orphan.sock.spawn_lock").write_text("", encoding="utf-8")
    calls: list[str] = []

    def fake_shutdown(
        *,
        reason: str = "",
        socket_path: str | None = None,
        wait_seconds: float = 3.0,
    ) -> bool:
        del reason, wait_seconds
        assert socket_path is not None
        calls.append(Path(socket_path).name)
        return Path(socket_path).name == "a.sock"

    monkeypatch.setattr(ec_services, "_shutdown_ec_daemon", fake_shutdown)

    stopped = prover._shutdown_repo_ec_daemons(reason="unit")

    assert stopped == 1
    assert calls == ["a.sock", "b.sock"]
    assert not (socket_root / "orphan.sock.spawn_lock").exists()


def test_shutdown_ec_daemon_uses_client_for_responsive_socket(
    tmp_path: Path,
    monkeypatch,
) -> None:
    sock = tmp_path / "ec_daemon.sock"
    sock.write_text("placeholder", encoding="utf-8")
    calls: list[tuple[str, str]] = []

    class DummyClient:
        def __init__(self, socket_path: str):
            calls.append(("init", socket_path))
            self.socket_path = Path(socket_path)

        def shutdown(self) -> bool:
            calls.append(("shutdown", ""))
            self.socket_path.unlink()
            return True

    monkeypatch.setattr(
        ec_services,
        "_ec_daemon_socket_responsive",
        lambda path: Path(path).exists(),
    )
    monkeypatch.setattr(ec_daemon_client, "ECDaemonClient", DummyClient)

    stopped = prover._shutdown_ec_daemon(socket_path=str(sock), wait_seconds=0)

    assert stopped is True
    assert not sock.exists()
    assert calls == [("init", str(sock)), ("shutdown", "")]


def test_shutdown_ec_daemon_treats_mid_response_close_as_stopped(
    tmp_path: Path,
    monkeypatch,
) -> None:
    sock = tmp_path / "ec_daemon.sock"
    lock = tmp_path / "ec_daemon.sock.spawn_lock"
    sock.write_text("placeholder", encoding="utf-8")
    lock.write_text("old lock", encoding="utf-8")

    class ClosingClient:
        def __init__(self, socket_path: str):
            self.socket_path = Path(socket_path)

        def shutdown(self) -> bool:
            self.socket_path.unlink()
            raise RuntimeError("daemon closed connection mid-response; got b''")

    monkeypatch.setattr(
        ec_services,
        "_ec_daemon_socket_responsive",
        lambda path: Path(path).exists(),
    )
    monkeypatch.setattr(ec_daemon_client, "ECDaemonClient", ClosingClient)

    stopped = prover._shutdown_ec_daemon(socket_path=str(sock), wait_seconds=0)

    assert stopped is True
    assert not sock.exists()
    assert not lock.exists()
