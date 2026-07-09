#!/usr/bin/env python3
"""Regression: a daemon connection dropped mid-probe must RECOVER, not surface
a raw socket error.

Bug (found 2026-05-30 auditing the step4 bad1_lbad1 resume runs): on a large
goal a heavy probe crashed the daemon's EC subprocess; the client raised a raw
`daemon closed connection mid-response; got b''` and `try_speculative` reported
`[TRY] error: daemon try_tactic failed: ...` with NO recovery — the agent saw a
scary low-level error.

Fix: the client raises a distinct `ECDaemonConnectionLost` (subclass of
`ECDaemonError`) on a mid-response EOF / dropped connection; `try_speculative`
catches it, respawns a fresh daemon, replays committed history, and retries the
probe ONCE (safe — `-try` never mutates committed state), bounded so a tactic
that genuinely crashes EC yields a clean, actionable message instead of a loop.

Pure: no EasyCrypt / no real daemon (sockets + backend are mocked).
Run: python3 -m pytest tests/test_daemon_connection_lost_recovery.py -q
"""
from __future__ import annotations

import sys
import tempfile
import types
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
from core.easycrypt.ec_daemon_client import (  # noqa: E402
    ECDaemonClient, ECDaemonConnectionLost, ECDaemonError)
from core.easycrypt.session_runtime import Session  # noqa: E402


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


# ── try_speculative: recover (respawn + replay + retry once) on a mid-probe drop

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


def _fake_session(cli_seq, *, sync_seq=None):
    # sync_seq: per-call results for _sync_to (1st = initial pre-probe sync,
    # 2nd = the recovery sync). Defaults to all-True.
    ec = Path(tempfile.mkstemp(suffix=".ec")[1])
    ec.write_text("require import AllCore.\nlemma l : true.\nproof.\ntrivial.\nqed.\n")
    hist = Path(tempfile.mkstemp(suffix=".history")[1]); hist.write_text("proc.\n")
    calls = {"force_fresh": 0, "sync": 0}
    sync_results = list(sync_seq or [])

    class FakeBackend:
        _session_id = "s"
        last_error = ""
        def __init__(self): self._clis = list(cli_seq)
        def _sync_to(self, fp, lname, tactics):
            calls["sync"] += 1
            return sync_results.pop(0) if sync_results else True
        def _ensure_daemon(self): return self._clis[0] if self._clis else None
        def _force_fresh_daemon(self):
            calls["force_fresh"] += 1
            if len(self._clis) > 1:
                self._clis.pop(0)
            return self._clis[0] if self._clis else None

    fake = types.SimpleNamespace(
        dir=Path("."), _include_dirs=[], _daemon_backend=FakeBackend(),
        history=hist,
        _get_daemon_meta=lambda: (str(ec), "l"),
        read_state=lambda: types.SimpleNamespace(raw_current=""),
        _session_file_path=lambda: str(ec),
        _format_try_single=lambda tactic, r, file_path, prev_raw: f"OK_SINGLE:{r}",
        _format_try_chain=lambda tactics, r, file_path, prev_raw: f"OK_CHAIN:{r}",
    )
    return fake, calls


def _run(fake, tactic="auto"):
    import os
    os.environ.pop("EC_DAEMON_DISABLE", None)
    return Session.try_speculative.__get__(fake, Session)(tactic)


def test_recovers_when_retry_succeeds():
    fake, calls = _fake_session([_CrashCli(), _OkCli()])
    out = _run(fake)
    assert out.startswith("OK_SINGLE:"), out          # recovered, formatted result
    assert "got b''" not in out                        # NOT the raw socket error
    assert calls["force_fresh"] == 1                   # exactly one respawn


def test_clean_message_when_retry_also_crashes():
    fake, calls = _fake_session([_CrashCli(), _CrashCli()])
    out = _run(fake)
    assert "repeatedly" in out and "too heavy" in out  # actionable, not raw
    assert "got b''" not in out
    assert "proof state is unchanged" in out
    assert calls["force_fresh"] == 1                   # bounded to one retry


def test_clean_message_when_resync_fails():
    # initial pre-probe sync succeeds; the RECOVERY sync fails.
    fake, calls = _fake_session([_CrashCli(), _OkCli()], sync_seq=[True, False])
    out = _run(fake)
    assert "could not be re-synced" in out
    assert "got b''" not in out
