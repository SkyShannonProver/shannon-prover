"""Daemon attempts known to fail are skipped for a while, never judged.

Three failures repeat on every commit until something changes: the daemon
cannot be spawned (each attempt waits for its socket), EasyCrypt rejects or
runs out of time on a committed transaction while the journal is replayed,
and EasyCrypt rejects the lemma's context when the session is opened. The
backend remembers each in the session directory, keyed by what failed (the
socket, the committed prefix identity, the source content), and skips the
daemon while the key still matches and the entry is fresh. A skip is a batch
fallback like any other; it is never a verdict.

No EasyCrypt and no daemon: the client and the spawn are faked.
"""
from __future__ import annotations

import importlib
import json
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path

import pytest

import core.easycrypt.daemon_backend as daemon_backend
import core.easycrypt.ec_daemon as ecd
import core.easycrypt.ec_lifecycle as ecl
import core.easycrypt.lemma_extract as lemma_extract
from core.easycrypt.committed_history import committed_prefix_identity
from core.easycrypt.daemon_backend import (
    CONTENT_FAILURE_TTL_SECONDS,
    SPAWN_FAILURE_TTL_SECONDS,
    DaemonBackend,
)
from core.easycrypt.ec_backend import BatchBackend
from core.easycrypt.ec_daemon_client import ECDaemonError
from core.easycrypt.session.session_events import read_events, validate_event
from core.easycrypt.session.session_runtime import Session

_EC_OUT = "Current goal\n\nType variables: <none>\n\nremaining goals: 0\n\n[1|check]>\n"


class _Clock:
    def __init__(self) -> None:
        self.now = 1_000_000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock(monkeypatch) -> _Clock:
    clock = _Clock()
    monkeypatch.setattr(daemon_backend.time, "time", clock)
    return clock


class _Client:
    """A daemon whose replay rejects ``bad.`` and whose open may fail."""

    def __init__(self, open_error: Exception | None = None, timed_out: str = "") -> None:
        self.calls: list[str] = []
        self.open_error = open_error
        self.timed_out = timed_out

    def list_sessions(self):
        self.calls.append("list")
        return []

    def close_session(self, session_id):
        self.calls.append("close")

    def open_session(self, *args, **kwargs):
        self.calls.append("open")
        if self.open_error is not None:
            raise self.open_error
        return {}

    def commit(self, session_id, tactic, timeout=None):
        self.calls.append(tactic)
        if tactic == self.timed_out:
            return {"accepted": False, "timed_out": True, "raw_output": "",
                    "error": {"kind": "timeout", "raw": "EasyCrypt did not finish "
                              "this transaction within 170 s"}}
        if tactic == "bad.":
            return {"accepted": False, "error": {"raw": "nothing to introduce"}}
        return {"accepted": True, "raw_output": _EC_OUT}


def _backend(tmp_path: Path, client: _Client) -> tuple[DaemonBackend, Path]:
    session_dir = tmp_path / "session"
    session_dir.mkdir(exist_ok=True)
    source = tmp_path / "T.ec"
    if not source.exists():
        source.write_text("lemma L : true.\nproof. admit. qed.\n", encoding="utf-8")
    backend = DaemonBackend(session_dir, [], socket_path=str(tmp_path / "none.sock"))
    backend._ensure_daemon = lambda: client  # type: ignore[method-assign]
    return backend, source


# --- spawn failure ------------------------------------------------------------

def test_a_spawn_failure_is_tried_once_then_skipped_until_it_expires(
    tmp_path, clock, monkeypatch,
):
    session_dir = tmp_path / "session"
    session_dir.mkdir()
    socket_path = str(tmp_path / "missing" / "d.sock")
    spawns: list[str] = []

    def spawn(self):
        spawns.append(self.socket_path)
        return False

    monkeypatch.setattr(DaemonBackend, "_spawn_daemon", spawn)
    source = tmp_path / "T.ec"
    source.write_text("lemma L : true.\nproof. admit. qed.\n", encoding="utf-8")

    first = DaemonBackend(session_dir, [], socket_path=socket_path)
    assert first.commit_latest(source, "L", ["a."]) is None
    assert first.last_error == f"daemon spawn failed: {socket_path}"
    assert [n["kind"] for n in first.unavailable_notices] == ["spawn"]
    assert first.unavailable_notices[0]["ttl_seconds"] == SPAWN_FAILURE_TTL_SECONDS

    # A later session_cli process (a new backend) honours it.
    clock.now += SPAWN_FAILURE_TTL_SECONDS - 1
    second = DaemonBackend(session_dir, [], socket_path=socket_path)
    assert second.commit_latest(source, "L", ["a."]) is None
    assert second.last_error.startswith(
        f"negative cache: daemon spawn failed: {socket_path}"
    )
    assert second.unavailable_notices == []
    assert len(spawns) == 1

    clock.now += 2
    third = DaemonBackend(session_dir, [], socket_path=socket_path)
    assert third.commit_latest(source, "L", ["a."]) is None
    assert third.last_error == f"daemon spawn failed: {socket_path}"
    assert len(spawns) == 2
    assert len(third.unavailable_notices) == 1

    # Another socket is another daemon.
    other = DaemonBackend(session_dir, [], socket_path=str(tmp_path / "x" / "e.sock"))
    assert other.commit_latest(source, "L", ["a."]) is None
    assert len(spawns) == 3


# --- replay failure -----------------------------------------------------------

def test_a_replay_rejection_is_skipped_while_the_journal_keeps_its_prefix(
    tmp_path, clock,
):
    client = _Client()
    backend, source = _backend(tmp_path, client)

    assert backend.commit_latest(source, "L", ["a.", "bad.", "c.", "new."]) is None
    assert client.calls[-2:] == ["a.", "bad."]
    reason = backend.last_error
    assert reason.startswith("replay rejected committed tactic 'bad.'")
    notice = backend.unavailable_notices[0]
    assert notice["kind"] == "replay" and notice["prefix_count"] == 2
    assert notice["ttl_seconds"] == CONTENT_FAILURE_TTL_SECONDS

    # Same prefix through step 2, whatever follows: no reopen, no replay.
    for journal in (["a.", "bad.", "c.", "new2."], ["a.", "bad.", "x.", "y.", "z."]):
        client.calls.clear()
        assert backend.commit_latest(source, "L", journal) is None
        assert client.calls == []
        assert backend.last_error.startswith(f"negative cache: {reason} (skipping")
    assert len(backend.unavailable_notices) == 1

    # The journal changed at the failing step: the daemon is tried again.
    client.calls.clear()
    reply = backend.commit_latest(source, "L", ["a.", "b.", "c.", "new."])
    assert reply is not None and reply.accepted
    assert "open" in client.calls


def test_a_replay_rejection_is_retried_when_the_journal_no_longer_reaches_it(
    tmp_path, clock,
):
    client = _Client()
    backend, source = _backend(tmp_path, client)
    assert backend.commit_latest(source, "L", ["a.", "bad.", "new."]) is None

    # After an undo the journal ends before the failing step.
    client.calls.clear()
    reply = backend.commit_latest(source, "L", ["a.", "new."])
    assert reply is not None and reply.accepted
    assert client.calls[-2:] == ["a.", "new."]
    assert not (backend.dir / "daemon_unavailable.json").exists()


def test_a_replay_rejection_is_retried_after_it_expires(tmp_path, clock):
    client = _Client()
    backend, source = _backend(tmp_path, client)
    journal = ["a.", "bad.", "new."]
    assert backend.commit_latest(source, "L", journal) is None

    clock.now += CONTENT_FAILURE_TTL_SECONDS + 1
    client.calls.clear()
    assert backend.commit_latest(source, "L", journal) is None
    assert client.calls[-2:] == ["a.", "bad."]
    assert backend.last_error.startswith("replay rejected committed tactic")
    assert len(backend.unavailable_notices) == 2


def test_a_replay_that_runs_out_of_time_is_remembered(tmp_path, clock):
    client = _Client(timed_out="slow.")
    backend, source = _backend(tmp_path, client)
    assert backend.commit_latest(source, "L", ["a.", "slow.", "new."]) is None
    assert backend.last_error.startswith("replay timed out on committed tactic 'slow.'")

    client.calls.clear()
    assert backend.commit_latest(source, "L", ["a.", "slow.", "new2."]) is None
    assert client.calls == []
    assert backend.last_error.startswith("negative cache: replay timed out")


def test_a_lost_connection_during_replay_is_not_remembered(tmp_path, clock):
    class _Dropping(_Client):
        def commit(self, session_id, tactic, timeout=None):
            self.calls.append(tactic)
            raise ConnectionError("daemon went away")

    client = _Dropping()
    backend, source = _backend(tmp_path, client)
    assert backend.commit_latest(source, "L", ["a.", "new."]) is None
    assert backend.unavailable_notices == []
    client.calls.clear()
    assert backend.commit_latest(source, "L", ["a.", "new."]) is None
    assert client.calls  # tried again


def test_forgetting_the_daemon_state_keeps_the_known_failures(tmp_path, clock):
    client = _Client()
    backend, source = _backend(tmp_path, client)
    assert backend.commit_latest(source, "L", ["a.", "bad.", "new."]) is None
    backend._forget_state()
    backend.invalidate()
    client.calls.clear()

    fresh, _ = _backend(tmp_path, client)
    assert fresh.commit_latest(source, "L", ["a.", "bad.", "new."]) is None
    assert client.calls == []
    assert fresh.last_error.startswith("negative cache: replay rejected")


# --- open failure -------------------------------------------------------------

def _setup_rejected() -> ECDaemonError:
    return ECDaemonError(
        "SetupRejected: EC rejected setup command '\\nend section.' for lemma 'L': "
        "{'kind': 'other', 'raw': 'cannot process [section closing] inside a proof script'}",
        kind="setup_rejected",
    )


def test_a_rejected_context_is_skipped_until_the_source_changes(tmp_path, clock):
    client = _Client(open_error=_setup_rejected())
    backend, source = _backend(tmp_path, client)

    assert backend.commit_latest(source, "L", ["a."]) is None
    assert backend.last_error.startswith("open_session failed for T.ec:L:")
    assert [n["kind"] for n in backend.unavailable_notices] == ["open"]

    client.calls.clear()
    assert backend.commit_latest(source, "L", ["b."]) is None
    assert client.calls == []
    assert backend.last_error.startswith("negative cache: open_session failed")

    # The source changed: open it again (EasyCrypt still rejects it).
    source.write_text("lemma L : true.\nproof. trivial. qed.\n", encoding="utf-8")
    assert backend.commit_latest(source, "L", ["a."]) is None
    assert client.calls == ["close", "open"]
    assert len(backend.unavailable_notices) == 2

    # Another lemma of the same file is another context.
    client.calls.clear()
    client.open_error = None
    reply = backend.commit_latest(source, "M", ["a."])
    assert reply is not None and reply.accepted
    assert "open" in client.calls


FAKE_EC = r'''
import sys
n = 0
sys.stdout.write("fake EasyCrypt\n[0|check]>")
sys.stdout.flush()
for line in sys.stdin:
    cmd = line.strip()
    n += 1
    if cmd == "end section.":
        sys.stdout.write("\n[error-0-12]cannot process [section closing] inside a proof script")
    else:
        sys.stdout.write(f"\nRESPONSE-TO: {cmd}")
    sys.stdout.write(f"\n[{n}|check]>")
    sys.stdout.flush()
'''


def test_the_daemon_reports_a_rejected_context_as_a_class(tmp_path, clock, monkeypatch):
    script = tmp_path / "fake_ec.py"
    script.write_text(FAKE_EC, encoding="utf-8")
    procs: list[subprocess.Popen] = []

    def spawn(include_dirs, why3_socket, env=None):
        proc = subprocess.Popen(
            [sys.executable, str(script)], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=0,
        )
        procs.append(proc)
        return proc

    monkeypatch.setattr(ecl, "spawn_emacs_pipe", spawn)
    monkeypatch.setattr(ecd.ECSubprocess, "_get_ec_env", staticmethod(lambda: {}))
    monkeypatch.setattr(
        lemma_extract, "extract_lemma",
        lambda *a, **k: "section S.\nlemma L : true.\nproof.\nend section.\n",
    )
    sock = str(Path(tempfile.gettempdir()) / f"ecnc_{uuid.uuid4().hex[:8]}.sock")
    server = ecd.DaemonServer(sock, ecd.SessionManager())
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        deadline = time.time() + 5.0
        while server._listen_sock is None:
            assert time.time() < deadline
            time.sleep(0.02)
        session_dir = tmp_path / "session"
        session_dir.mkdir()
        source = tmp_path / "T.ec"
        source.write_text("lemma L : true.\nproof. admit. qed.\n", encoding="utf-8")
        backend = DaemonBackend(session_dir, [], socket_path=sock)

        assert backend.commit_latest(source, "L", ["trivial."]) is None
        assert "SetupRejected: EC rejected setup command 'end section." in backend.last_error
        assert [n["kind"] for n in backend.unavailable_notices] == ["open"]
        assert backend.commit_latest(source, "L", ["trivial."]) is None
        assert backend.last_error.startswith("negative cache: open_session failed")
        assert len(procs) == 1
    finally:
        server.shutdown()
        thread.join(timeout=5.0)
        for proc in procs:
            if proc.poll() is None:
                proc.kill()
                proc.wait()


def test_an_open_failure_without_a_rejection_is_not_remembered(tmp_path, clock):
    client = _Client(open_error=ECDaemonError("TimeoutError: EC did not emit prompt"))
    backend, source = _backend(tmp_path, client)
    assert backend.commit_latest(source, "L", ["a."]) is None
    assert backend.unavailable_notices == []
    client.calls.clear()
    assert backend.commit_latest(source, "L", ["a."]) is None
    assert "open" in client.calls


# --- the session --------------------------------------------------------------

class _CountingBatch(BatchBackend):
    def __init__(self, session_dir):
        super().__init__(session_dir)
        self.runs = 0

    def run(self, input_path, output_path, include_dirs, timeout=None):
        self.runs += 1
        Path(output_path).write_text(_EC_OUT, encoding="utf-8")
        return 0


def _session(tmp_path: Path) -> Session:
    session_dir = tmp_path / "sess"
    session = Session(session_dir, batch=_CountingBatch(session_dir))
    source = tmp_path / "real.ec"
    source.write_text("lemma foo : true. proof. admit. qed.\n", encoding="utf-8")
    (session.dir / "session_meta.json").write_text(
        json.dumps({"file": str(source), "lemma": "foo"}), encoding="utf-8",
    )
    return session


def test_a_skipped_daemon_routes_batch_and_says_why(tmp_path, clock, monkeypatch):
    socket_path = str(tmp_path / "missing" / "d.sock")
    monkeypatch.setenv("EC_DAEMON_SOCKET", socket_path)
    monkeypatch.delenv("EC_DAEMON_DISABLE", raising=False)
    spawns: list[str] = []

    def spawn(self):
        spawns.append(self.socket_path)
        return False

    monkeypatch.setattr(DaemonBackend, "_spawn_daemon", spawn)
    session = _session(tmp_path)
    session.append_block("trivial.")
    # A later session_cli process.
    session = Session(session.dir, batch=session._batch)
    session.append_block("trivial.")

    events = read_events(session.dir)
    routing = [e["payload"] for e in events if e["type"] == "ec.routing"]
    assert [(r["backend"], r["reason"]) for r in routing] == [
        ("batch", "commit_none"), ("batch", "commit_none"),
    ]
    assert routing[0]["detail"] == f"daemon spawn failed: {socket_path}"
    assert routing[1]["detail"].startswith(
        f"negative cache: daemon spawn failed: {socket_path}"
    )
    unavailable = [e for e in events if e["type"] == "ec.daemon_unavailable"]
    assert len(unavailable) == 1
    assert validate_event(unavailable[0]) == []
    payload = unavailable[0]["payload"]
    assert payload["kind"] == "spawn"
    assert payload["reason"] == f"daemon spawn failed: {socket_path}"
    assert payload["ttl_seconds"] == SPAWN_FAILURE_TTL_SECONDS
    assert payload["expires_at"].endswith("+00:00")
    assert len(spawns) == 1

    # -start clears the session directory and with it the known failures.
    session.start()
    (session.dir / "session_meta.json").write_text(
        json.dumps({"file": str(tmp_path / "real.ec"), "lemma": "foo"}),
        encoding="utf-8",
    )
    session.append_block("trivial.")
    assert len(spawns) == 2


def test_a_skipped_replay_never_becomes_a_verdict(tmp_path, clock, monkeypatch):
    monkeypatch.delenv("EC_DAEMON_DISABLE", raising=False)
    client = _Client()
    session = _session(tmp_path)
    session.history.write_text("a.\nbad.\n", encoding="utf-8")
    session.steps.write_text("1\n1\n", encoding="utf-8")
    db = importlib.import_module("core.easycrypt.daemon_backend")
    real = db.DaemonBackend

    class _Backend(real):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._ensure_daemon = lambda: client

    monkeypatch.setattr(db, "DaemonBackend", _Backend)
    first = session.append_block("trivial.")
    second = session.append_block("trivial.")

    routing = [e["payload"] for e in read_events(session.dir) if e["type"] == "ec.routing"]
    assert [r["reason"] for r in routing] == ["commit_none", "commit_none"]
    assert routing[1]["detail"].startswith("negative cache: replay rejected")
    # The batch backend judged both (its fixed transcript accepts them).
    assert first.status in {"ok", "no_progress_reverted"}
    assert second.status in {"ok", "no_progress_reverted"}
    assert session._batch.runs >= 2
    unavailable = [
        e["payload"] for e in read_events(session.dir)
        if e["type"] == "ec.daemon_unavailable"
    ]
    assert [u["kind"] for u in unavailable] == ["replay"]
    assert unavailable[0]["prefix_count"] == 2
    assert committed_prefix_identity(["a.", "bad."]) in (
        session.dir / "daemon_unavailable.json"
    ).read_text()
