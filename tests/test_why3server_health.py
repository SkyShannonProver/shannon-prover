"""Tests for why3server health probe + stale-socket detection.

The orchestrator pre-starts a single why3server that all EC subprocess
verifications share via ``-server /tmp/why3ec.sock``. The OS sandbox
blocks ``nice()`` so EC cannot spawn its own; if the shared socket goes
stale (file lingers but no listener), EC silently falls through to the
self-spawn path and dies. The fix is a Unix-socket connect probe — these
tests confirm the probe distinguishes the three cases that occur in
practice: missing path, stale orphan socket file, live listener.
"""
from __future__ import annotations

import os
import socket
import sys
import tempfile
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from workflow.agents.prover import _is_why3server_responsive  # noqa: E402


def test_responsive_probe_returns_false_for_missing_path() -> None:
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "no-such-socket"
        assert _is_why3server_responsive(str(path), timeout=0.5) is False


def test_responsive_probe_returns_false_for_stale_socket_file() -> None:
    """A regular file at the socket path (no listener) — exactly the
    state observed on the dev box on 2026-05-03 with /tmp/why3ec.sock
    left over from a prior session."""
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "stale.sock"
        path.write_bytes(b"")
        assert _is_why3server_responsive(str(path), timeout=0.5) is False


def test_responsive_probe_returns_false_for_orphan_socket_inode() -> None:
    """Socket file exists with SOCK_STREAM type but no process listens
    — the kernel will refuse the connect with ECONNREFUSED. This
    mirrors what happens when the why3server pid that bound the
    socket has died but the inode is still on disk.
    """
    with tempfile.TemporaryDirectory() as td:
        path = str(Path(td) / "orphan.sock")
        # Bind without listening, then close — leaves an orphan inode.
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            s.bind(path)
        finally:
            s.close()
        assert os.path.exists(path)
        assert _is_why3server_responsive(path, timeout=0.5) is False


def test_responsive_probe_returns_true_for_live_listener() -> None:
    """A real Unix-domain server bound and listening — connect should
    succeed and the probe must return True."""
    with tempfile.TemporaryDirectory() as td:
        path = str(Path(td) / "live.sock")
        srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        srv.bind(path)
        srv.listen(1)

        accepted = []

        def _accept_once():
            try:
                conn, _ = srv.accept()
                accepted.append(conn)
                conn.close()
            except Exception:
                pass

        t = threading.Thread(target=_accept_once, daemon=True)
        t.start()
        try:
            assert _is_why3server_responsive(path, timeout=2.0) is True
            t.join(timeout=2.0)
            assert accepted, (
                "live listener should have observed the probe's connect"
            )
        finally:
            srv.close()
            try:
                os.unlink(path)
            except Exception:
                pass


if __name__ == "__main__":
    test_responsive_probe_returns_false_for_missing_path()
    test_responsive_probe_returns_false_for_stale_socket_file()
    test_responsive_probe_returns_false_for_orphan_socket_inode()
    test_responsive_probe_returns_true_for_live_listener()
    print("PASS test_why3server_health")
