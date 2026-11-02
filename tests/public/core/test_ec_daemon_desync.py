"""A timed-out or failed EC exchange must never pair a command with an older reply.

The fake EasyCrypt below answers every command with ``RESPONSE-TO: <command>``
and a prompt. A command containing ``slow`` sleeps first while the marker file
exists (once), so a short timeout leaves its reply late in the pipe. Before the
fix the daemon kept that session, and every later reply arrived one command
late.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path

import pytest

import core.easycrypt.ec_daemon as ecd
import core.easycrypt.ec_lifecycle as ecl
import core.easycrypt.lemma_extract as lemma_extract
from core.easycrypt.committed_history import committed_prefix_identity
from core.easycrypt.daemon_backend import DaemonBackend
from core.easycrypt.ec_daemon_client import ECDaemonClient
from core.easycrypt.ec_diagnostics import parse_error

FAKE_EC = r'''
import os, sys, time
marker = sys.argv[1]
n = 0
sys.stdout.write("fake EasyCrypt\n[0|check]>")
sys.stdout.flush()
for line in sys.stdin:
    cmd = line.strip()
    if "slow" in cmd and os.path.exists(marker):
        os.unlink(marker)
        time.sleep(1.5)
    n += 1
    reply = f"\nCurrent goal\n\nRESPONSE-TO: {cmd}\n[{n}|check]>"
    if "twice" in cmd:
        n += 1
        reply += f"\n[{n}|check]>"
    sys.stdout.write(reply)
    sys.stdout.flush()
'''

SETUP = "require import AllCore.\nlemma L : true.\nproof.\n"


@pytest.fixture
def fake_ec(tmp_path, monkeypatch):
    script = tmp_path / "fake_ec.py"
    script.write_text(FAKE_EC, encoding="utf-8")
    marker = tmp_path / "slow_once"
    procs: list[subprocess.Popen] = []

    def spawn(include_dirs, why3_socket, env=None):
        proc = subprocess.Popen(
            [sys.executable, str(script), str(marker)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, bufsize=0,
        )
        procs.append(proc)
        return proc

    monkeypatch.setattr(ecl, "spawn_emacs_pipe", spawn)
    monkeypatch.setattr(ecd.ECSubprocess, "_get_ec_env", staticmethod(lambda: {}))
    monkeypatch.setattr(lemma_extract, "extract_lemma", lambda *a, **k: SETUP)
    monkeypatch.setattr(ecd.ECSubprocess, "_RESPONSE_TIMEOUT_DEFAULT", 0.5)
    marker.write_text("", encoding="utf-8")
    yield marker, procs
    for proc in procs:
        if proc.poll() is None:
            proc.kill()
            proc.wait()


def _lifecycle(fake_ec) -> ecl.ECSessionLifecycle:
    ec = ecl.ECSessionLifecycle([], env={})
    ec.spawn()
    return ec


def test_a_timed_out_read_refuses_every_later_exchange(fake_ec) -> None:
    ec = _lifecycle(fake_ec)
    try:
        with pytest.raises(TimeoutError):
            ec.send_and_drain("slow_tactic.", timeout=0.3, is_error=parse_error)
        time.sleep(1.5)  # the late reply is now in the pipe

        assert ec.desynchronized
        with pytest.raises(ecl.ECProtocolDesync):
            ec.send_and_drain("next_tactic.", timeout=5, is_error=parse_error)
    finally:
        ec.teardown()


def test_an_extra_prompt_is_detected_before_the_next_send(fake_ec) -> None:
    ec = _lifecycle(fake_ec)
    try:
        raw = ec.send_and_drain("twice.", timeout=5, is_error=parse_error)
        assert "RESPONSE-TO: twice." in raw
        time.sleep(0.2)  # the second prompt has arrived but answers nothing

        with pytest.raises(ecl.ECProtocolDesync):
            ec.send_and_drain("next_tactic.", timeout=5, is_error=parse_error)
    finally:
        ec.teardown()


def test_respawn_clears_the_desynchronized_state(fake_ec) -> None:
    ec = _lifecycle(fake_ec)
    with pytest.raises(TimeoutError):
        ec.send_and_drain("slow_tactic.", timeout=0.3, is_error=parse_error)
    ec.teardown()
    ec.spawn()
    try:
        raw = ec.send_and_drain("next_tactic.", timeout=5, is_error=parse_error)
        assert "RESPONSE-TO: next_tactic." in raw
    finally:
        ec.teardown()


def test_the_daemon_drops_a_session_whose_request_timed_out(fake_ec, tmp_path) -> None:
    _, procs = fake_ec
    mgr = ecd.SessionManager()
    mgr.open("scli_t", tmp_path / "T.ec", [], "L")

    with pytest.raises(TimeoutError):
        with mgr.with_session("scli_t") as ec:
            ec.execute("slow_tactic.")

    assert mgr.list() == []
    assert procs[0].poll() is not None


class _Server:
    def __init__(self) -> None:
        self.sock = str(Path(tempfile.gettempdir()) / f"ecdz_{uuid.uuid4().hex[:8]}.sock")
        self.mgr = ecd.SessionManager()
        self.srv = ecd.DaemonServer(self.sock, self.mgr)
        self.thread = threading.Thread(target=self.srv.serve_forever, daemon=True)

    def __enter__(self) -> "_Server":
        self.thread.start()
        deadline = time.time() + 5.0
        while self.srv._listen_sock is None:
            assert time.time() < deadline, "daemon server did not start listening"
            time.sleep(0.02)
        return self

    def __exit__(self, *exc: object) -> None:
        self.srv.shutdown()
        self.thread.join(timeout=5.0)


def test_after_a_timeout_the_next_commit_gets_its_own_reply(
    fake_ec, tmp_path, monkeypatch,
) -> None:
    monkeypatch.setenv("SHANNON_EC_STEP_TIMEOUT", "0.5")
    source = tmp_path / "T.ec"
    source.write_text(SETUP + "qed.\n", encoding="utf-8")
    session_dir = tmp_path / "session"
    session_dir.mkdir()
    with _Server() as server:
        backend = DaemonBackend(session_dir, [], socket_path=server.sock)

        timed_out = backend.commit_latest(source, "L", ["slow_tactic."])
        assert timed_out is not None and not timed_out.accepted
        assert timed_out.error == (
            "[error] EasyCrypt did not finish this transaction within 0.5 s"
        )
        assert not (session_dir / "daemon_state.json").exists()
        assert ECDaemonClient(server.sock).list_sessions() == []
        time.sleep(1.5)  # the old process would now hold the late reply

        # The session rolled slow_tactic back, so the journal no longer has it.
        result = backend.commit_latest(source, "L", ["next_tactic."])

    assert result is not None and result.accepted
    assert "RESPONSE-TO: next_tactic." in result.post_raw
    state = json.loads((session_dir / "daemon_state.json").read_text())
    assert state["committed_count"] == 1


def test_a_failed_replay_forgets_the_cached_count(tmp_path) -> None:
    session_dir = tmp_path / "session"
    session_dir.mkdir()
    source = tmp_path / "T.ec"
    source.write_text(SETUP, encoding="utf-8")
    backend = DaemonBackend(session_dir, [], socket_path=str(tmp_path / "none.sock"))
    backend._save_state({
        "committed_count": 1,
        "committed_prefix_sha256": committed_prefix_identity(["a."]),
        "file_path": str(source.resolve()),
        "lemma_name": "L",
    })

    class _Client:
        def list_sessions(self):
            return [backend._session_id]

        def commit(self, session_id, tactic, timeout=None):
            return {"accepted": False, "error": {"raw": "boom"}}

    backend._ensure_daemon = lambda: _Client()  # type: ignore[method-assign]

    assert backend._sync_to(source, "L", ["a.", "b.", "c."]) is False
    assert not (session_dir / "daemon_state.json").exists()


@pytest.mark.parametrize(("held", "reopened"), [(["a."], False), (["x."], True)])
def test_sync_extends_only_the_prefix_the_daemon_holds(tmp_path, held, reopened) -> None:
    session_dir = tmp_path / "session"
    session_dir.mkdir()
    source = tmp_path / "T.ec"
    source.write_text(SETUP, encoding="utf-8")
    backend = DaemonBackend(session_dir, [], socket_path=str(tmp_path / "none.sock"))
    backend._save_state({
        "committed_count": 1,
        "committed_prefix_sha256": committed_prefix_identity(held),
        "file_path": str(source.resolve()),
        "lemma_name": "L",
    })
    calls: list[str] = []

    class _Client:
        def list_sessions(self):
            return [backend._session_id]

        def close_session(self, session_id):
            calls.append("close")

        def open_session(self, *args, **kwargs):
            calls.append("open")

        def commit(self, session_id, tactic, timeout=None):
            calls.append(tactic)
            return {"accepted": True}

    backend._ensure_daemon = lambda: _Client()  # type: ignore[method-assign]

    assert backend._sync_to(source, "L", ["a.", "b."]) is True
    assert calls == (["close", "open", "a.", "b."] if reopened else ["b."])
    state = json.loads((session_dir / "daemon_state.json").read_text())
    assert state["committed_prefix_sha256"] == committed_prefix_identity(["a.", "b."])


def test_a_failed_open_leaves_no_session_and_no_process(fake_ec, tmp_path, monkeypatch) -> None:
    _, procs = fake_ec

    def reject(*args, **kwargs):
        raise ValueError("lemma L not found")

    monkeypatch.setattr(lemma_extract, "extract_lemma", reject)
    mgr = ecd.SessionManager()

    with pytest.raises(ValueError, match="lemma L not found"):
        mgr.open("scli_t", tmp_path / "T.ec", [], "L")

    assert mgr.list() == []
    assert procs[0].poll() is not None
    with pytest.raises(KeyError):
        with mgr.with_session("scli_t"):
            pass
    # The id is free again for the client's retry.
    monkeypatch.setattr(lemma_extract, "extract_lemma", lambda *a, **k: SETUP)
    mgr.open("scli_t", tmp_path / "T.ec", [], "L")
    assert mgr.list() == ["scli_t"]
    mgr.close("scli_t")


def test_close_never_tears_down_under_a_running_request(fake_ec, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(ecd.ECSubprocess, "_RESPONSE_TIMEOUT_DEFAULT", 10.0)
    reading: set[int] = set()
    overlaps: list[str] = []
    read = ecl.ECSessionLifecycle._read_until_prompt
    teardown = ecl.ECSessionLifecycle.teardown

    def tracked_read(self, *args, **kwargs):
        reading.add(threading.get_ident())
        try:
            return read(self, *args, **kwargs)
        finally:
            reading.discard(threading.get_ident())

    def tracked_teardown(self, *args, **kwargs):
        if reading - {threading.get_ident()}:
            overlaps.append("teardown while another thread reads the pipe")
        return teardown(self, *args, **kwargs)

    monkeypatch.setattr(ecl.ECSessionLifecycle, "_read_until_prompt", tracked_read)
    monkeypatch.setattr(ecl.ECSessionLifecycle, "teardown", tracked_teardown)
    mgr = ecd.SessionManager()
    mgr.open("scli_t", tmp_path / "T.ec", [], "L")
    outcome: list[object] = []

    def request() -> None:
        try:
            with mgr.with_session("scli_t") as ec:
                outcome.append(ec.execute("slow_tactic."))
        except Exception as exc:  # the close must make the request fail
            outcome.append(exc)

    worker = threading.Thread(target=request)
    worker.start()
    time.sleep(0.3)
    started = time.monotonic()
    mgr.close("scli_t")
    elapsed = time.monotonic() - started
    worker.join(timeout=10)

    assert overlaps == []
    assert elapsed < 1.2, "close waited for the slow sentence instead of interrupting it"
    assert len(outcome) == 1 and isinstance(outcome[0], Exception)
    assert mgr.list() == []
