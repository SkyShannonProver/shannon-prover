"""Pure regressions for conservative daemon Unix-socket probing."""

from __future__ import annotations

import errno
from pathlib import Path
from unittest import mock

import pytest

from core.easycrypt.daemon_backend import DaemonBackend


class _Probe:
    def __init__(self, result: int) -> None:
        self.result = result
        self.closed = False

    def settimeout(self, _timeout: float) -> None:
        pass

    def connect_ex(self, _path: str) -> int:
        return self.result

    def close(self) -> None:
        self.closed = True


@pytest.mark.parametrize("probe_errno", [errno.EPERM, errno.EACCES])
def test_access_denied_does_not_unlink_or_respawn(
    tmp_path: Path,
    probe_errno: int,
) -> None:
    socket_path = tmp_path / "live.sock"
    lock_path = tmp_path / "live.sock.spawn_lock"
    socket_path.touch()
    lock_path.touch()
    backend = DaemonBackend(
        tmp_path / "session",
        [],
        socket_path=str(socket_path),
    )
    probe = _Probe(probe_errno)

    with (
        mock.patch(
            "core.easycrypt.daemon_backend.socket.socket",
            return_value=probe,
        ),
        mock.patch.object(backend, "_spawn_daemon") as spawn,
    ):
        assert backend._ensure_daemon() is None

    assert probe.closed
    assert socket_path.exists()
    assert lock_path.exists()
    spawn.assert_not_called()
    assert "daemon socket access denied" in backend.last_error
    assert f"errno={probe_errno}" in backend.last_error


def test_confirmed_refusal_unlinks_and_attempts_respawn(tmp_path: Path) -> None:
    socket_path = tmp_path / "stale.sock"
    lock_path = tmp_path / "stale.sock.spawn_lock"
    socket_path.touch()
    lock_path.touch()
    backend = DaemonBackend(
        tmp_path / "session",
        [],
        socket_path=str(socket_path),
    )
    probe = _Probe(errno.ECONNREFUSED)

    with (
        mock.patch(
            "core.easycrypt.daemon_backend.socket.socket",
            return_value=probe,
        ),
        mock.patch.object(
            backend,
            "_spawn_daemon",
            return_value=False,
        ) as spawn,
    ):
        assert backend._ensure_daemon() is None

    assert probe.closed
    assert not socket_path.exists()
    assert not lock_path.exists()
    spawn.assert_called_once_with()


def test_sync_preserves_specific_connection_failure(tmp_path: Path) -> None:
    backend = DaemonBackend(
        tmp_path / "session",
        [],
        socket_path=str(tmp_path / "daemon.sock"),
    )
    detail = "daemon socket access denied: test (errno=1)"

    def unavailable():
        backend.last_error = detail
        return None

    with mock.patch.object(backend, "_ensure_daemon", side_effect=unavailable):
        assert not backend._sync_to(tmp_path / "proof.ec", "lemma", [])

    assert backend.last_error == detail
