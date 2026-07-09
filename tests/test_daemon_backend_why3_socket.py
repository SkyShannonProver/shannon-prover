"""Tests for daemon_backend's why3 socket resolution.

Tree workers that route the first commit through the daemon path used
to silently spawn EC without ``-server``, breaking on SMT-dependent
clones (ChaChaPoly step1 reproducer 2026-05-03). The fix wires
``_resolve_why3_socket()`` into ``cli.open_session`` so the
daemon-spawned EC inherits the orchestrator's persistent why3 server.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]

from core.easycrypt.daemon_backend import _resolve_why3_socket  # type: ignore  # noqa: E402


def test_resolve_why3_socket_returns_path_when_file_exists() -> None:
    with tempfile.TemporaryDirectory() as td:
        fake_socket = Path(td) / "why3ec.sock"
        fake_socket.touch()
        with mock.patch("os.path.exists") as exists:
            exists.side_effect = lambda p: p == "/tmp/why3ec.sock"
            assert _resolve_why3_socket() == "/tmp/why3ec.sock"


def test_resolve_why3_socket_returns_none_when_missing() -> None:
    with mock.patch("os.path.exists", return_value=False):
        assert _resolve_why3_socket() is None


def main() -> int:
    test_resolve_why3_socket_returns_path_when_file_exists()
    test_resolve_why3_socket_returns_none_when_missing()
    print("PASS test_daemon_backend_why3_socket")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
