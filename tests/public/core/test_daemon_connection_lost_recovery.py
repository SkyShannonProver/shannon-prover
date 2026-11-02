#!/usr/bin/env python3
"""Regression: a daemon connection dropped mid-probe must RECOVER, not surface
a raw socket error.

Bug (found 2026-05-30 auditing the step4 bad1_lbad1 resume runs): on a large
goal a heavy probe crashed the daemon's EC subprocess; the client raised a raw
`daemon closed connection mid-response; got b''` and the -try probe reported
`[TRY] error: daemon try_tactic failed: ...` with NO recovery — the agent saw a
scary low-level error.

Fix: the client raises a distinct `ECDaemonConnectionLost` (subclass of
`ECDaemonError`) on a mid-response EOF / dropped connection;
`DaemonBackend.try_tactics` catches it, respawns a fresh daemon, replays
committed history, and retries the probe ONCE (safe — `-try` never mutates
committed state), bounded so a tactic that genuinely crashes EC yields a clean,
actionable message instead of a loop.

Pure: no EasyCrypt / no real daemon (sockets + backend are mocked).
Run: python3 -m pytest tests/public/core/test_daemon_connection_lost_recovery.py -q
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from unittest import mock

from core.easycrypt.daemon_backend import DaemonBackend  # noqa: E402
from core.easycrypt.ec_daemon_client import (  # noqa: E402
    ECDaemonClient, ECDaemonConnectionLost, ECDaemonError)


# ── client: the mid-response EOF / dropped connection is a recoverable class ──

def test_mid_response_eof_raises_connection_lost():
    cli = ECDaemonClient("/tmp/irrelevant.sock")
    fake = mock.MagicMock()
    fake.recv.return_value = b""        # EOF before any newline
    with mock.patch("socket.socket", return_value=fake):
        try:
            cli._call("try_tactic", "s", {"tactic": "x."})
            assert False, "expected ECDaemonConnectionLost"
        except ECDaemonConnectionLost as e:
            assert "mid-response" in str(e)
    # subclass of ECDaemonError so existing `except ECDaemonError` still catches.
    assert issubclass(ECDaemonConnectionLost, ECDaemonError)


def test_connection_refused_raises_connection_lost():
    cli = ECDaemonClient("/tmp/irrelevant.sock")
    fake = mock.MagicMock()
    fake.connect.side_effect = ConnectionRefusedError("nope")
    with mock.patch("socket.socket", return_value=fake):
        try:
            cli._call("list_sessions")
            assert False, "expected ECDaemonConnectionLost"
        except ECDaemonConnectionLost:
            pass


# ── try_tactics: recover (respawn + replay + retry once) on a mid-probe drop

class _CrashCli:
    def try_tactic(self, sid, t):
        raise ECDaemonConnectionLost("daemon closed connection mid-response; got b''")
    def try_chain(self, sid, ts):
        raise ECDaemonConnectionLost("daemon closed connection mid-response; got b''")


class _OkCli:
    def try_tactic(self, sid, t):
        return {"accepted": True, "goal_after": {}, "error": None}
    def try_chain(self, sid, ts):
        return {"accepted": True}


def _backend(cli_seq, *, sync_seq=None):
    # sync_seq: per-call results for _sync_to (1st = initial pre-probe sync,
    # 2nd = the recovery sync). Defaults to all-True.
    calls = {"force_fresh": 0, "sync": 0}
    sync_results = list(sync_seq or [])
    clis = list(cli_seq)
    backend = DaemonBackend(Path(tempfile.mkdtemp()), [], socket_path="/tmp/irrelevant.sock")

    def _sync_to(fp, lname, tactics):
        calls["sync"] += 1
        return sync_results.pop(0) if sync_results else True

    def _force_fresh_daemon():
        calls["force_fresh"] += 1
        if len(clis) > 1:
            clis.pop(0)
        return clis[0] if clis else None

    backend._sync_to = _sync_to
    backend._ensure_daemon = lambda: clis[0] if clis else None
    backend._force_fresh_daemon = _force_fresh_daemon
    return backend, calls


def _run(backend, tactic="auto"):
    return backend.try_tactics(Path("l.ec"), "l", ["proc."], tactic)


def test_recovers_when_retry_succeeds():
    backend, calls = _backend([_CrashCli(), _OkCli()])
    out = _run(backend)
    assert out.accepted is True and not out.tool_error   # recovered, real verdict
    assert "got b''" not in out.report                   # NOT the raw socket error
    assert calls["force_fresh"] == 1                     # exactly one respawn


def test_clean_message_when_retry_also_crashes():
    backend, calls = _backend([_CrashCli(), _CrashCli()])
    out = _run(backend)
    assert out.tool_error
    assert "repeatedly" in out.report and "too heavy" in out.report  # actionable
    assert "got b''" not in out.report
    assert "proof state is unchanged" in out.report
    assert calls["force_fresh"] == 1                     # bounded to one retry


def test_clean_message_when_resync_fails():
    # initial pre-probe sync succeeds; the RECOVERY sync fails.
    backend, calls = _backend([_CrashCli(), _OkCli()], sync_seq=[True, False])
    out = _run(backend)
    assert out.tool_error
    assert "could not be re-synced" in out.report
    assert "got b''" not in out.report
