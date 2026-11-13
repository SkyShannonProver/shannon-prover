"""The daemon's per-transaction limit follows the manager's commit budget, and
a transaction EasyCrypt does not finish in time is a rejection.

Most tests drive a real daemon server with a fake EasyCrypt: a command
``nap_<seconds>.`` sleeps that long before it replies, every other command
replies at once, and each process logs the commands it received. One test
runs real EasyCrypt (skipped without the managed toolchain) with a slow
``unroll for`` and a low limit set through the environment.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

import core.easycrypt.daemon_backend as daemon_backend
import core.easycrypt.ec_daemon as ecd
import core.easycrypt.ec_lifecycle as ecl
import core.easycrypt.lemma_extract as lemma_extract
from core.easycrypt.daemon_backend import DaemonBackend
from core.easycrypt.ec_backend import BatchBackend
from core.easycrypt.ec_daemon_client import (
    DEFAULT_STEP_TIMEOUT_SECONDS,
    STEP_TIMEOUT_ENV,
    ECDaemonClient,
    step_timeout_seconds,
)
from core.easycrypt.ec_env import get_ec_env
from core.easycrypt.session.session_events import read_events
from core.easycrypt.session.session_runtime import Session
from workflow.proof_management import repl_session

ROOT = Path(__file__).resolve().parents[3]

FAKE_EC = r'''
import sys, time
log = open(sys.argv[1], "a", buffering=1)
log.write("--- spawn\n")
n = 0
sys.stdout.write("fake EasyCrypt\n[0|check]>")
sys.stdout.flush()
for line in sys.stdin:
    cmd = line.strip()
    log.write(cmd + "\n")
    if cmd.startswith("nap_"):
        time.sleep(float(cmd[4:].rstrip(".")))
    n += 1
    sys.stdout.write(f"\nCurrent goal\n\nRESPONSE-TO: {cmd}\n[{n}|check]>")
    sys.stdout.flush()
'''

SETUP = "require import AllCore.\nlemma L : true.\nproof.\n"
TIMEOUT_ERROR = "[error] EasyCrypt did not finish this transaction within {} s"


@pytest.fixture
def fake_ec(tmp_path, monkeypatch):
    script = tmp_path / "fake_ec.py"
    script.write_text(FAKE_EC, encoding="utf-8")
    log = tmp_path / "ec_commands.log"
    procs: list[subprocess.Popen] = []

    def spawn(include_dirs, why3_socket, env=None):
        proc = subprocess.Popen(
            [sys.executable, str(script), str(log)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, bufsize=0,
        )
        procs.append(proc)
        return proc

    monkeypatch.setattr(ecl, "spawn_emacs_pipe", spawn)
    monkeypatch.setattr(ecd.ECSubprocess, "_get_ec_env", staticmethod(lambda: {}))
    monkeypatch.setattr(lemma_extract, "extract_lemma", lambda *a, **k: SETUP)
    # A request without a limit (an older client) would wait this long.
    monkeypatch.setattr(ecd.ECSubprocess, "_RESPONSE_TIMEOUT_DEFAULT", 0.3)
    monkeypatch.delenv(STEP_TIMEOUT_ENV, raising=False)
    yield SimpleNamespace(log=log, procs=procs)
    for proc in procs:
        if proc.poll() is None:
            proc.kill()
            proc.wait()


def _commands_per_process(log: Path) -> list[list[str]]:
    processes: list[list[str]] = []
    for line in log.read_text(encoding="utf-8").splitlines():
        if line == "--- spawn":
            processes.append([])
        else:
            processes[-1].append(line)
    return processes


class _Server:
    def __init__(self) -> None:
        self.sock = str(Path(tempfile.gettempdir()) / f"ecst_{uuid.uuid4().hex[:8]}.sock")
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


def _source(tmp_path: Path) -> Path:
    source = tmp_path / "T.ec"
    source.write_text(SETUP + "qed.\n", encoding="utf-8")
    return source


# --- configuration ----------------------------------------------------------

@pytest.mark.parametrize(("raw", "expected"), [
    (None, DEFAULT_STEP_TIMEOUT_SECONDS),
    ("30", 30.0),
    (" 0.5 ", 0.5),
    ("", DEFAULT_STEP_TIMEOUT_SECONDS),
    ("soon", DEFAULT_STEP_TIMEOUT_SECONDS),
    ("0", DEFAULT_STEP_TIMEOUT_SECONDS),
    ("-5", DEFAULT_STEP_TIMEOUT_SECONDS),
    ("inf", DEFAULT_STEP_TIMEOUT_SECONDS),
    ("nan", DEFAULT_STEP_TIMEOUT_SECONDS),
])
def test_the_step_limit_takes_only_a_positive_finite_value(monkeypatch, raw, expected):
    if raw is None:
        monkeypatch.delenv(STEP_TIMEOUT_ENV, raising=False)
    else:
        monkeypatch.setenv(STEP_TIMEOUT_ENV, raw)
    assert step_timeout_seconds() == expected


def test_the_managers_commit_budget_is_the_core_step_limit_plus_a_margin():
    assert DEFAULT_STEP_TIMEOUT_SECONDS == 170.0
    assert repl_session.COMMIT_CALL_TIMEOUT_SECONDS == 180.0


@pytest.mark.easycrypt
def test_the_manager_hands_the_step_limit_to_session_cli(monkeypatch):
    monkeypatch.setenv(STEP_TIMEOUT_ENV, "soon")
    env = repl_session.ReplSessionManager._env(SimpleNamespace(session_dir="sess"))
    assert env[STEP_TIMEOUT_ENV] == "170"
    monkeypatch.setenv(STEP_TIMEOUT_ENV, env[STEP_TIMEOUT_ENV])
    assert step_timeout_seconds() == DEFAULT_STEP_TIMEOUT_SECONDS


def test_the_client_sends_the_limit_and_waits_a_little_longer(monkeypatch):
    calls = []

    def record(self, method, session_id="", params=None, timeout=300.0):
        calls.append((method, dict(params or {}), timeout))
        return {"accepted": True}

    monkeypatch.setattr(ECDaemonClient, "_call", record)
    monkeypatch.setenv(STEP_TIMEOUT_ENV, "42")
    client = ECDaemonClient("/nonexistent.sock")
    client.commit("s", "t.", timeout=5)
    client.commit("s", "t.")
    assert calls[0] == ("commit", {"tactic": "t.", "timeout": 5.0}, 20.0)
    assert calls[1] == ("commit", {"tactic": "t.", "timeout": 42.0}, 57.0)


@pytest.mark.parametrize(("value", "expected"), [
    (5, 5.0),
    (0.25, 0.25),
    (10_000, 600.0),
    (None, "default"),
    ("170", "default"),
    (True, "default"),
    (0, "default"),
    (-3, "default"),
    (float("nan"), "default"),
    (float("inf"), "default"),
])
def test_the_daemon_caps_the_limit_and_keeps_its_old_default_without_one(value, expected):
    if expected == "default":
        expected = ecd.ECSubprocess._RESPONSE_TIMEOUT_DEFAULT
    assert ecd._commit_timeout(value) == expected


# --- the daemon's verdict -----------------------------------------------------

def test_a_slow_transaction_is_a_timed_out_rejection_and_drops_the_session(
    fake_ec, tmp_path,
) -> None:
    mgr = ecd.SessionManager()
    mgr.open("scli_t", tmp_path / "T.ec", [], "L")
    srv = SimpleNamespace(mgr=mgr)

    started = time.monotonic()
    reply = ecd._h_commit(srv, "scli_t", {"tactic": "nap_5.", "timeout": 0.4})
    elapsed = time.monotonic() - started

    assert reply["status"] == "ok"
    result = reply["result"]
    assert result["accepted"] is False and result["timed_out"] is True
    assert result["error"]["raw"] == (
        "EasyCrypt did not finish this transaction within 0.4 s"
    )
    assert elapsed < 3.0
    assert mgr.list() == []
    assert fake_ec.procs[0].poll() is not None


def test_the_limit_bounds_the_whole_transaction_not_each_sentence(
    fake_ec, tmp_path,
) -> None:
    mgr = ecd.SessionManager()
    mgr.open("scli_t", tmp_path / "T.ec", [], "L")
    srv = SimpleNamespace(mgr=mgr)

    reply = ecd._h_commit(
        srv, "scli_t", {"tactic": "nap_0.4. nap_0.4. nap_0.4.", "timeout": 1.0},
    )

    assert reply["result"]["timed_out"] is True
    assert mgr.list() == []


def test_a_transaction_within_the_limit_is_committed(fake_ec, tmp_path) -> None:
    mgr = ecd.SessionManager()
    mgr.open("scli_t", tmp_path / "T.ec", [], "L")
    srv = SimpleNamespace(mgr=mgr)

    # Longer than the default a request without a limit gets (0.3 s here).
    reply = ecd._h_commit(srv, "scli_t", {"tactic": "nap_0.6.", "timeout": 5})

    assert reply["result"]["accepted"] is True
    assert "timed_out" not in reply["result"]
    assert mgr.list() == ["scli_t"]
    mgr.close("scli_t")


# --- the client's handling ----------------------------------------------------

def test_a_timed_out_commit_is_a_daemon_rejection(fake_ec, tmp_path, monkeypatch):
    monkeypatch.setenv(STEP_TIMEOUT_ENV, "0.5")
    session_dir = tmp_path / "session"
    session_dir.mkdir()
    with _Server() as server:
        backend = DaemonBackend(session_dir, [], socket_path=server.sock)
        assert backend.commit_latest(_source(tmp_path), "L", ["a."]).accepted

        reply = backend.commit_latest(_source(tmp_path), "L", ["a.", "nap_5."])

        assert reply is not None and not reply.accepted
        assert reply.error == TIMEOUT_ERROR.format("0.5")
        assert not (session_dir / "daemon_state.json").exists()
        assert ECDaemonClient(server.sock).list_sessions() == []


def test_a_replay_gets_the_step_limit(fake_ec, tmp_path, monkeypatch):
    # Committed once in 0.6 s, so it must replay although a request without
    # a limit gives up after 0.3 s here.
    monkeypatch.setenv(STEP_TIMEOUT_ENV, "5")
    session_dir = tmp_path / "session"
    session_dir.mkdir()
    with _Server() as server:
        backend = DaemonBackend(session_dir, [], socket_path=server.sock)
        reply = backend.commit_latest(_source(tmp_path), "L", ["nap_0.6.", "b."])

    assert reply is not None and reply.accepted, backend.last_error
    assert _commands_per_process(fake_ec.log)[0][-2:] == ["nap_0.6.", "b."]


def test_a_replay_beyond_the_step_limit_is_not_a_verdict(fake_ec, tmp_path, monkeypatch):
    monkeypatch.setenv(STEP_TIMEOUT_ENV, "0.4")
    session_dir = tmp_path / "session"
    session_dir.mkdir()
    with _Server() as server:
        backend = DaemonBackend(session_dir, [], socket_path=server.sock)
        reply = backend.commit_latest(_source(tmp_path), "L", ["nap_5.", "b."])

    assert reply is None
    assert backend.last_error == (
        "replay timed out on committed tactic 'nap_5.': "
        + TIMEOUT_ERROR.format("0.4")
    )
    assert not (session_dir / "daemon_state.json").exists()


def test_a_daemon_that_ignores_the_limit_degrades_to_the_batch_fallback(
    fake_ec, tmp_path, monkeypatch,
):
    def commit_without_limit(srv, sid, p):
        with srv.mgr.with_session(sid) as ec:
            outcome = ec.execute(p["tactic"])
        return ecd._ok_resp(ecd._outcome_to_dict(outcome))

    monkeypatch.setitem(ecd._METHOD_TABLE, "commit", commit_without_limit)
    monkeypatch.setenv(STEP_TIMEOUT_ENV, "5")
    session_dir = tmp_path / "session"
    session_dir.mkdir()
    with _Server() as server:
        backend = DaemonBackend(session_dir, [], socket_path=server.sock)
        reply = backend.commit_latest(_source(tmp_path), "L", ["nap_0.6."])

    # The old daemon gave up after its own 0.3 s: an RPC error, so the
    # session falls back to batch as before.
    assert reply is None
    assert backend.last_error.startswith(
        "daemon commit RPC failed: ECDaemonError: TimeoutError:"
    )


# --- the session --------------------------------------------------------------

class _NoBatch(BatchBackend):
    def run(self, *args, **kwargs):
        raise AssertionError("the batch backend must not run")


def test_a_timed_out_commit_is_rolled_back_and_the_next_commit_replays_without_it(
    fake_ec, tmp_path, monkeypatch,
):
    monkeypatch.setenv(STEP_TIMEOUT_ENV, "0.5")
    monkeypatch.setattr(daemon_backend, "is_disabled", lambda: False)
    with _Server() as server:
        monkeypatch.setenv("EC_DAEMON_SOCKET", server.sock)
        session = Session(tmp_path / "session", batch=_NoBatch(tmp_path / "session"))
        (session.dir / "session_meta.json").write_text(
            json.dumps({"file": str(_source(tmp_path)), "lemma": "L"}),
            encoding="utf-8",
        )

        first = session.append_block("a.")
        slow = session.append_block("nap_5.")
        after = session.append_block("b.")

    routing = [e["payload"] for e in read_events(session.dir) if e["type"] == "ec.routing"]
    assert [r["reason"] for r in routing] == [
        "daemon_accept", "daemon_reject", "daemon_accept",
    ]
    assert {r["backend"] for r in routing} == {"daemon"}
    assert first.status == "ok" and after.status == "ok"
    assert slow.status == "error"
    assert slow.latest_error == TIMEOUT_ERROR.format("0.5")
    assert session.history.read_text() == "a.\nb.\n"
    processes = _commands_per_process(fake_ec.log)
    assert len(processes) == 2
    assert "nap_5." not in processes[1]
    assert processes[1][-2:] == ["a.", "b."]


# --- real EasyCrypt -----------------------------------------------------------

try:
    _MANAGED_EC_AVAILABLE = shutil.which(
        "easycrypt", path=get_ec_env().get("PATH")
    ) is not None
except RuntimeError:
    _MANAGED_EC_AVAILABLE = False

# ``unroll for`` over this loop takes several seconds of EasyCrypt time.
SLOW_FIXTURE = """require import AllCore.
module M = {
  proc f() : int = {
    var i, s : int;
    s <- 0;
    i <- 0;
    while (i < 8000) { s <- s + 2; i <- i + 1; }
    return s;
  }
}.
lemma slow_unroll : hoare [M.f : true ==> true].
proof. admit. qed.
"""


@pytest.mark.easycrypt
@pytest.mark.skipif(
    not _MANAGED_EC_AVAILABLE, reason="repository-managed EasyCrypt is unavailable",
)
def test_real_easycrypt_rejects_a_slow_tactic_on_the_daemon(tmp_path):
    source = tmp_path / "Slow.ec"
    source.write_text(SLOW_FIXTURE, encoding="utf-8")
    session_dir = tmp_path / "session"
    env = dict(
        os.environ,
        **{
            STEP_TIMEOUT_ENV: "2",
            # A route nobody serves: EasyCrypt runs its provers itself.
            "WHY3EC_SOCKET": f"/tmp/stw_{uuid.uuid4().hex[:10]}.sock",
        },
    )
    env.pop("EC_DAEMON_DISABLE", None)

    def cli(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(ROOT / "core/easycrypt/session_cli.py"),
             "-d", str(session_dir), *args],
            cwd=ROOT, env=env, capture_output=True, text=True, timeout=300,
        )

    start = cli("-start", "--force-restart", "-f", str(source),
                "-lemma", "slow_unroll", "-I", str(ROOT / "easycrypt-src/theories"))
    assert start.returncode == 0, start.stderr
    timings = []
    for tactic in ("proc.", "unroll for 3.", "sp."):
        began = time.monotonic()
        cli("-tactic-exec", "commit", "-c", tactic)
        timings.append(time.monotonic() - began)

    events = read_events(session_dir)
    routing = [e["payload"] for e in events if e["type"] == "ec.routing"]
    results = [e["payload"] for e in events if e["type"] == "tactic.result"]
    assert [(r["backend"], r["reason"]) for r in routing] == [
        ("daemon", "daemon_accept"),
        ("daemon", "daemon_reject"),
        ("daemon", "daemon_accept"),
    ], routing
    assert [r["status"] for r in results] == ["ok", "error", "ok"]
    assert results[1]["latest_error"] == TIMEOUT_ERROR.format("2")
    assert timings[1] < 30, timings
    assert (session_dir / "history.ec").read_text() == "proc.\nsp.\n"
