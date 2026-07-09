"""Daemon-backed EC session continuity (worker-death attach, SHANNON_EC_DAEMON=1).

Covers the three layers of the feature:

1. ``SessionManager`` registry primitives in ``core/easycrypt/ec_daemon.py``
   (``adopt`` / ``info`` / ``touch`` / ``reap_idle``) — pure in-process, fake
   EC subprocess objects, no sockets.
2. The ``adopt_session`` / ``session_info`` RPCs over a real unix socket
   served by an in-process ``DaemonServer`` (fake EC sessions injected).
3. ``workflow.proof_management.daemon_attach`` — the verified attach client:
   every fallback reason, the success path against a live fake daemon,
   cleanup on partial failure, and ``release_daemon_session``.
4. Flag gating in ``ReplSessionManager.start`` and
   ``ProofNodeLifecycleManager.bootstrap``: with ``SHANNON_EC_DAEMON`` unset
   the legacy restart+replay path is byte-identical (the legacy ``_FakeRepl``
   whose ``start`` has NO ``daemon_attach`` kwarg must keep working).

The real-EasyCrypt worker-death integration test (kill nothing, adopt the
live EC process, verify the goal survives with zero replay) is
``test_worker_death_attach_real_ec`` at the bottom — skip-marked unless
``easycrypt`` is on PATH. Note macOS sandboxes that block unix sockets will
fail the socket-backed tests here; run them unsandboxed (same constraint as
``tests/test_rewind_wedge_fix.py``).
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.easycrypt.ec_daemon import DaemonServer, SessionManager  # noqa: E402
from core.easycrypt.ec_daemon_client import ECDaemonClient, ECDaemonError  # noqa: E402

from workflow.proof_management import daemon_attach as da  # noqa: E402
from workflow.proof_management.repl_session import ReplSessionManager  # noqa: E402
from workflow.proof_management.lifecycle import (  # noqa: E402
    _daemon_attach_request,
)


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _FakeProc:
    """Stands in for ``subprocess.Popen``: alive until ``close()``."""

    def __init__(self) -> None:
        self.returncode: int | None = None

    def poll(self) -> int | None:
        return self.returncode


class _FakeEC:
    """Duck-types the slice of ``ECSubprocess`` the registry + the
    ``session_info`` / ``get_goal`` handlers touch."""

    def __init__(
        self,
        file_path: str = "/tmp/fake.ec",
        lemma_name: str = "foo",
        committed_count: int = 0,
        goal_raw: bytes = b"Current goal\n\nx + 0 = x\n[1|check]>",
    ) -> None:
        self.proc = _FakeProc()
        self.file_path = Path(file_path)
        self.lemma_name = lemma_name
        self.committed_count = committed_count
        self.goal_raw = goal_raw
        self.closed = False
        self.sent: list[str] = []

    def close(self) -> None:
        self.closed = True
        self.proc.returncode = 0

    # get_goal handler protocol
    def _send(self, line: str) -> None:
        self.sent.append(line)

    def _read_until_prompt(self) -> bytes:
        return self.goal_raw


def _register(mgr: SessionManager, sid: str, ec: _FakeEC) -> None:
    """Inject a fake live session into the registry (bypasses ``open``,
    which would spawn a real EC process)."""
    with mgr._registry_lock:
        mgr._sessions[sid] = ec
        mgr._locks[sid] = threading.Lock()
        mgr._last_used[sid] = time.time()


# ---------------------------------------------------------------------------
# 1. SessionManager registry primitives
# ---------------------------------------------------------------------------


def test_adopt_renames_live_session() -> None:
    mgr = SessionManager()
    ec = _FakeEC(committed_count=7)
    _register(mgr, "scli_old", ec)

    assert mgr.adopt("scli_old", "scli_new") is True

    assert mgr.list() == ["scli_new"]
    info = mgr.info("scli_new")
    assert info["exists"] and info["committed_count"] == 7
    assert mgr.info("scli_old") == {"exists": False}
    assert not ec.closed  # rename only — the EC process is untouched
    # The adopted session is usable under the new id.
    with mgr.with_session("scli_new") as got:
        assert got is ec
    with pytest.raises(KeyError):
        with mgr.with_session("scli_old"):
            pass


def test_adopt_missing_donor_raises() -> None:
    mgr = SessionManager()
    with pytest.raises(KeyError):
        mgr.adopt("scli_ghost", "scli_new")
    with pytest.raises(KeyError):
        mgr.adopt("scli_ghost", "scli_ghost")  # same-id no-op still needs liveness


def test_adopt_taken_target_raises_and_preserves_both() -> None:
    mgr = SessionManager()
    donor, holder = _FakeEC(), _FakeEC()
    _register(mgr, "scli_a", donor)
    _register(mgr, "scli_b", holder)
    with pytest.raises(ValueError):
        mgr.adopt("scli_a", "scli_b")
    assert sorted(mgr.list()) == ["scli_a", "scli_b"]
    assert not donor.closed and not holder.closed


def test_adopt_same_id_is_noop() -> None:
    mgr = SessionManager()
    _register(mgr, "scli_x", _FakeEC())
    assert mgr.adopt("scli_x", "scli_x") is True
    assert mgr.list() == ["scli_x"]


def test_info_reports_dead_ec_process() -> None:
    mgr = SessionManager()
    ec = _FakeEC()
    ec.proc.returncode = 1  # EC died, registry entry still present
    _register(mgr, "scli_dead", ec)
    info = mgr.info("scli_dead")
    assert info["exists"] is True
    assert info["ec_alive"] is False


def test_info_missing_session() -> None:
    assert SessionManager().info("scli_nope") == {"exists": False}


def test_reap_idle_closes_only_stale_sessions() -> None:
    mgr = SessionManager()
    stale, fresh = _FakeEC(), _FakeEC()
    _register(mgr, "scli_stale", stale)
    _register(mgr, "scli_fresh", fresh)
    with mgr._registry_lock:
        mgr._last_used["scli_stale"] = time.time() - 3600.0

    reaped = mgr.reap_idle(ttl_seconds=60.0)

    assert reaped == ["scli_stale"]
    assert stale.closed and not fresh.closed
    assert mgr.list() == ["scli_fresh"]


def test_reap_idle_nonpositive_ttl_disables() -> None:
    mgr = SessionManager()
    ec = _FakeEC()
    _register(mgr, "scli_s", ec)
    with mgr._registry_lock:
        mgr._last_used["scli_s"] = 0.0  # epoch — maximally stale
    assert mgr.reap_idle(0) == []
    assert mgr.reap_idle(-5) == []
    assert not ec.closed


def test_with_session_touches_last_used() -> None:
    mgr = SessionManager()
    _register(mgr, "scli_t", _FakeEC())
    with mgr._registry_lock:
        mgr._last_used["scli_t"] = time.time() - 3600.0
    with mgr.with_session("scli_t"):
        pass
    # The touch must have refreshed it past any reasonable cutoff.
    assert mgr.info("scli_t")["idle_seconds"] < 60.0
    assert mgr.reap_idle(ttl_seconds=600.0) == []


# ---------------------------------------------------------------------------
# 2. Daemon RPC surface (in-process server, real unix socket, fake EC)
# ---------------------------------------------------------------------------


class _ServerHarness:
    """In-process DaemonServer on a short-lived unix socket."""

    def __init__(self) -> None:
        base = Path(tempfile.gettempdir())
        self.sock = str(base / f"ecdt_{uuid.uuid4().hex[:8]}.sock")
        self.mgr = SessionManager()
        self.srv = DaemonServer(self.sock, self.mgr)
        self._thread = threading.Thread(
            target=self.srv.serve_forever, daemon=True
        )

    def __enter__(self) -> "_ServerHarness":
        self._thread.start()
        deadline = time.time() + 5.0
        while not os.path.exists(self.sock):
            if time.time() > deadline:
                raise RuntimeError("daemon socket did not appear")
            time.sleep(0.02)
        return self

    def __exit__(self, *a: object) -> None:
        self.srv.shutdown()
        self._thread.join(timeout=5.0)

    def client(self) -> ECDaemonClient:
        return ECDaemonClient(self.sock)


def test_rpc_adopt_session_and_session_info() -> None:
    with _ServerHarness() as h:
        ec = _FakeEC(committed_count=3, lemma_name="lem")
        _register(h.mgr, "scli_donor", ec)
        cli = h.client()

        info = cli.session_info("scli_donor")
        assert info["exists"] and info["committed_count"] == 3
        assert info["lemma_name"] == "lem" and info["ec_alive"] is True

        assert cli.adopt_session("scli_donor", "scli_target") is True
        assert cli.list_sessions() == ["scli_target"]
        assert cli.session_info("scli_donor") == {"exists": False}

        # Adopted session answers get_goal (the attach liveness probe).
        goal = cli.get_goal("scli_target")
        assert "x + 0 = x" in goal["raw"]


def test_rpc_adopt_session_missing_donor_is_structured_error() -> None:
    with _ServerHarness() as h:
        cli = h.client()
        with pytest.raises(ECDaemonError):
            cli.adopt_session("scli_ghost", "scli_new")
        assert cli.list_sessions() == []


def test_rpc_session_info_missing() -> None:
    with _ServerHarness() as h:
        assert h.client().session_info("scli_none") == {"exists": False}


# ---------------------------------------------------------------------------
# 3. daemon_attach client (verification, fallback reasons, success, release)
# ---------------------------------------------------------------------------


_PREFIX = ["proof.", "rewrite addz0."]


def _donor_dir(
    tmp_path: Path,
    *,
    ec_file: Path,
    name: str = "donor_session",
    socket_path: str = "/tmp/ecdt_definitely_not_listening.sock",
    lemma: str = "foo",
    prefix: list[str] | None = None,
    state_count: int | None = None,
    session_id: str | None = None,
    current_out: str = "Current goal:\n\n  x + 0 = x\n",
) -> Path:
    """A donor session dir shaped like a dead worker left it."""
    prefix = _PREFIX if prefix is None else prefix
    donor = tmp_path / name
    donor.mkdir(exist_ok=True)
    (donor / "history.ec").write_text("\n".join(prefix) + "\n", encoding="utf-8")
    (donor / "session_meta.json").write_text(
        json.dumps({"file": str(ec_file), "lemma": lemma}), encoding="utf-8"
    )
    (donor / "daemon_state.json").write_text(
        json.dumps({
            "session_id": session_id or da.daemon_session_id_for_dir(donor),
            "committed_count": len(prefix) if state_count is None else state_count,
            "file_path": str(ec_file.resolve()),
            "lemma_name": lemma,
            "socket_path": socket_path,
        }),
        encoding="utf-8",
    )
    (donor / "current.out").write_text(current_out, encoding="utf-8")
    return donor


@pytest.fixture()
def ec_file(tmp_path: Path) -> Path:
    f = tmp_path / "target.ec"
    f.write_text("lemma foo (x:int): x + 0 = x.\n", encoding="utf-8")
    return f


def _attempt(tmp_path: Path, donor: Path, ec_file: Path, **kw: object) -> dict:
    args: dict = dict(
        project_root=tmp_path,
        donor_session_dir=donor,
        target_session_dir=tmp_path / "target_session",
        file_path=str(ec_file),
        lemma_name="foo",
        replay_prefix=list(_PREFIX),
    )
    args.update(kw)
    return da.attempt_daemon_attach(**args)


def test_flag_off_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SHANNON_EC_DAEMON", raising=False)
    assert da.daemon_session_attach_enabled() is False
    for off in ("", "0", "false", "no"):
        monkeypatch.setenv("SHANNON_EC_DAEMON", off)
        assert da.daemon_session_attach_enabled() is False
    for on in ("1", "true", "YES", "On"):
        monkeypatch.setenv("SHANNON_EC_DAEMON", on)
        assert da.daemon_session_attach_enabled() is True


def test_attach_disabled_without_flag(
    tmp_path: Path, ec_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("SHANNON_EC_DAEMON", raising=False)
    donor = _donor_dir(tmp_path, ec_file=ec_file)
    result = _attempt(tmp_path, donor, ec_file)
    assert result == {"ok": False, "reason": "disabled"}


@pytest.fixture()
def flag_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SHANNON_EC_DAEMON", "1")


def test_attach_donor_dir_missing(
    tmp_path: Path, ec_file: Path, flag_on: None
) -> None:
    result = _attempt(tmp_path, tmp_path / "nope", ec_file)
    assert not result["ok"] and result["reason"] == "donor_dir_missing"


def test_attach_donor_is_target(
    tmp_path: Path, ec_file: Path, flag_on: None
) -> None:
    donor = _donor_dir(tmp_path, ec_file=ec_file)
    result = _attempt(tmp_path, donor, ec_file, target_session_dir=donor)
    assert not result["ok"] and result["reason"] == "donor_is_target"


def test_attach_empty_prefix_rejected(
    tmp_path: Path, ec_file: Path, flag_on: None
) -> None:
    donor = _donor_dir(tmp_path, ec_file=ec_file)
    result = _attempt(tmp_path, donor, ec_file, replay_prefix=[])
    assert not result["ok"] and result["reason"] == "empty_replay_prefix"


def test_attach_history_mismatch(
    tmp_path: Path, ec_file: Path, flag_on: None
) -> None:
    donor = _donor_dir(tmp_path, ec_file=ec_file, prefix=["proof."])
    result = _attempt(tmp_path, donor, ec_file)  # requests _PREFIX (2 tactics)
    assert not result["ok"] and result["reason"] == "history_mismatch"
    assert result["donor_history_count"] == 1
    assert result["requested_count"] == 2


def test_attach_session_meta_mismatch(
    tmp_path: Path, ec_file: Path, flag_on: None
) -> None:
    donor = _donor_dir(tmp_path, ec_file=ec_file, lemma="other_lemma")
    # daemon_state lemma must also be "foo"-incompatible for this path;
    # the meta check fires first.
    result = _attempt(tmp_path, donor, ec_file)
    assert not result["ok"] and result["reason"] == "session_meta_mismatch"


def test_attach_daemon_state_out_of_sync(
    tmp_path: Path, ec_file: Path, flag_on: None
) -> None:
    donor = _donor_dir(tmp_path, ec_file=ec_file, state_count=1)
    result = _attempt(tmp_path, donor, ec_file)
    assert not result["ok"] and result["reason"] == "daemon_state_out_of_sync"
    assert result["daemon_state_count"] == 1


def test_attach_daemon_socket_dead(
    tmp_path: Path, ec_file: Path, flag_on: None
) -> None:
    donor = _donor_dir(tmp_path, ec_file=ec_file)  # default dead socket path
    result = _attempt(tmp_path, donor, ec_file)
    assert not result["ok"] and result["reason"] == "daemon_socket_dead"


def test_attach_daemon_session_gone(
    tmp_path: Path, ec_file: Path, flag_on: None
) -> None:
    with _ServerHarness() as h:  # live daemon, but no session registered
        donor = _donor_dir(tmp_path, ec_file=ec_file, socket_path=h.sock)
        result = _attempt(tmp_path, donor, ec_file)
    assert not result["ok"] and result["reason"] == "daemon_session_gone"


def test_attach_daemon_ec_dead(
    tmp_path: Path, ec_file: Path, flag_on: None
) -> None:
    with _ServerHarness() as h:
        donor = _donor_dir(tmp_path, ec_file=ec_file, socket_path=h.sock)
        ec = _FakeEC(file_path=str(ec_file), committed_count=2)
        ec.proc.returncode = 1  # registry entry alive, EC process dead
        _register(h.mgr, da.daemon_session_id_for_dir(donor), ec)
        result = _attempt(tmp_path, donor, ec_file)
    assert not result["ok"] and result["reason"] == "daemon_ec_dead"


def test_attach_daemon_commit_count_mismatch(
    tmp_path: Path, ec_file: Path, flag_on: None
) -> None:
    with _ServerHarness() as h:
        donor = _donor_dir(tmp_path, ec_file=ec_file, socket_path=h.sock)
        ec = _FakeEC(file_path=str(ec_file), committed_count=5)  # != 2
        _register(h.mgr, da.daemon_session_id_for_dir(donor), ec)
        result = _attempt(tmp_path, donor, ec_file)
    assert not result["ok"]
    assert result["reason"] == "daemon_commit_count_mismatch"


def test_attach_goal_hash_mismatch(
    tmp_path: Path, ec_file: Path, flag_on: None
) -> None:
    with _ServerHarness() as h:
        donor = _donor_dir(tmp_path, ec_file=ec_file, socket_path=h.sock)
        # Sanity: the helper derives a non-empty hash from current.out, so a
        # wrong expectation must be DETECTED, not silently skipped.
        assert da._goal_hash_from_session_dir(donor)
        ec = _FakeEC(file_path=str(ec_file), committed_count=2)
        _register(h.mgr, da.daemon_session_id_for_dir(donor), ec)
        result = _attempt(
            tmp_path, donor, ec_file, expected_goal_hash="deadbeef" * 8
        )
        # Verification failed BEFORE any mutation: donor session untouched.
        assert da.daemon_session_id_for_dir(donor) in h.mgr.list()
    assert not result["ok"] and result["reason"] == "goal_hash_mismatch"
    assert not (tmp_path / "target_session").exists()


def test_attach_success_adopts_without_replay(
    tmp_path: Path, ec_file: Path, flag_on: None
) -> None:
    with _ServerHarness() as h:
        donor = _donor_dir(tmp_path, ec_file=ec_file, socket_path=h.sock)
        donor_sid = da.daemon_session_id_for_dir(donor)
        ec = _FakeEC(file_path=str(ec_file), committed_count=2)
        _register(h.mgr, donor_sid, ec)
        expected_hash = da._goal_hash_from_session_dir(donor)
        assert expected_hash

        target = tmp_path / "target_session"
        result = _attempt(
            tmp_path, donor, ec_file, expected_goal_hash=expected_hash
        )

        assert result["ok"] is True, result
        assert result["replay_avoided"] == 2
        target_sid = da.daemon_session_id_for_dir(target)
        assert result["session_id"] == target_sid
        # Daemon side: session renamed, never replayed, EC untouched.
        assert h.mgr.list() == [target_sid]
        assert h.mgr.info(target_sid)["committed_count"] == 2
        assert not ec.closed
        # Disk side: full session dir copied; daemon_state rewritten to the
        # target id so the next commit's _sync_to is a no-op.
        assert (target / "history.ec").read_text() == \
            (donor / "history.ec").read_text()
        new_state = json.loads((target / "daemon_state.json").read_text())
        assert new_state["session_id"] == target_sid
        assert new_state["committed_count"] == 2
        assert new_state["socket_path"] == h.sock
        # Liveness probe really ran against the adopted session.
        assert ec.sent, "get_goal probe never reached the EC process"


def test_attach_adopt_conflict_cleans_up_target_dir(
    tmp_path: Path, ec_file: Path, flag_on: None
) -> None:
    """Target sid already taken in the daemon -> adopt RPC fails -> the
    half-copied target dir must be removed so the legacy fallback starts
    clean."""
    with _ServerHarness() as h:
        donor = _donor_dir(tmp_path, ec_file=ec_file, socket_path=h.sock)
        target = tmp_path / "target_session"
        _register(h.mgr, da.daemon_session_id_for_dir(donor),
                  _FakeEC(file_path=str(ec_file), committed_count=2))
        _register(h.mgr, da.daemon_session_id_for_dir(target), _FakeEC())

        result = _attempt(tmp_path, donor, ec_file)

    assert not result["ok"] and result["reason"] == "adopt_failed"
    assert not target.exists()


def test_attach_liveness_probe_failure_closes_adopted_session(
    tmp_path: Path, ec_file: Path, flag_on: None
) -> None:
    with _ServerHarness() as h:
        donor = _donor_dir(tmp_path, ec_file=ec_file, socket_path=h.sock)
        ec = _FakeEC(file_path=str(ec_file), committed_count=2, goal_raw=b"")
        _register(h.mgr, da.daemon_session_id_for_dir(donor), ec)

        target = tmp_path / "target_session"
        result = _attempt(tmp_path, donor, ec_file)

        assert not result["ok"]
        assert result["reason"] == "liveness_probe_empty"
        # Half-adopted session closed; nothing stale left for the fallback.
        assert h.mgr.list() == []
        assert ec.closed
    assert not target.exists()


def test_attach_never_raises(tmp_path: Path, ec_file: Path, flag_on: None,
                             monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        da, "_attempt_daemon_attach_inner",
        lambda **kw: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    donor = _donor_dir(tmp_path, ec_file=ec_file)
    result = _attempt(tmp_path, donor, ec_file)
    assert not result["ok"] and result["reason"] == "unexpected_error"
    assert "RuntimeError" in result["error"]


def test_release_daemon_session(
    tmp_path: Path, ec_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with _ServerHarness() as h:
        donor = _donor_dir(tmp_path, ec_file=ec_file, socket_path=h.sock)
        sid = da.daemon_session_id_for_dir(donor)
        _register(h.mgr, sid, _FakeEC())

        # Flag off: never touches the daemon.
        monkeypatch.delenv("SHANNON_EC_DAEMON", raising=False)
        assert da.release_daemon_session(donor, tmp_path) is False
        assert h.mgr.list() == [sid]

        # Replay/audit cleanup is lower-level than clean worker release: it must
        # close daemon fast-path sessions even when attach continuity is off.
        assert da.close_daemon_session(donor, tmp_path) is True
        assert h.mgr.list() == []

        # Flag on: clean-exit release closes the live session.
        donor = _donor_dir(tmp_path, name="donor2", ec_file=ec_file, socket_path=h.sock)
        sid = da.daemon_session_id_for_dir(donor)
        _register(h.mgr, sid, _FakeEC())
        monkeypatch.setenv("SHANNON_EC_DAEMON", "1")
        assert da.release_daemon_session(donor, tmp_path) is True
        assert h.mgr.list() == []


def test_release_without_daemon_state_is_false(
    tmp_path: Path, flag_on: None
) -> None:
    empty = tmp_path / "no_state"
    empty.mkdir()
    assert da.release_daemon_session(empty, tmp_path) is False


# ---------------------------------------------------------------------------
# 4. Flag gating in ReplSessionManager / lifecycle
# ---------------------------------------------------------------------------


def _repl(tmp_path: Path) -> ReplSessionManager:
    return ReplSessionManager(
        file_path="target.ec",
        lemma_name="foo",
        include_dir="easycrypt-src/theories",
        session_tag="continuity_unit",
        node_id="Tree-unit",
        project_root=tmp_path,
    )


def test_repl_start_flag_off_is_legacy_even_with_attach_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("SHANNON_EC_DAEMON", raising=False)
    # Flag off must never even attempt an attach.
    monkeypatch.setattr(
        da, "attempt_daemon_attach",
        lambda **kw: (_ for _ in ()).throw(AssertionError("attach attempted")),
    )
    repl = _repl(tmp_path)
    seen: dict = {}

    def fake_start_locked(replay_prefix=None, *, preamble_actions=None, **kw):
        seen["replay_prefix"] = list(replay_prefix or [])
        seen["preamble_actions"] = list(preamble_actions or [])
        return "SNAPSHOT", []

    repl._start_locked = fake_start_locked  # type: ignore[method-assign]

    out = repl.start(
        replay_prefix=["proof."],
        daemon_attach={"donor_session_dir": ".ec_session_dead"},
    )
    assert out == ("SNAPSHOT", [])
    assert seen["replay_prefix"] == ["proof."]
    assert seen["preamble_actions"] == []  # no fallback action: never tried


def test_repl_start_flag_on_attach_failure_records_fallback_action(
    tmp_path: Path, flag_on: None
) -> None:
    repl = _repl(tmp_path)
    seen: dict = {}

    def fake_start_locked(replay_prefix=None, *, preamble_actions=None, **kw):
        seen["preamble_actions"] = list(preamble_actions or [])
        return "SNAPSHOT", list(preamble_actions or [])

    repl._start_locked = fake_start_locked  # type: ignore[method-assign]

    snapshot, actions = repl.start(
        replay_prefix=["proof."],
        daemon_attach={"donor_session_dir": str(tmp_path / "no_such_donor")},
    )
    assert snapshot == "SNAPSHOT"
    assert len(seen["preamble_actions"]) == 1
    action = seen["preamble_actions"][0]
    assert action["label"] == "daemon_attach_fallback"
    assert action["mutates_proof_state"] is False
    assert action["daemon_attach"]["reason"] == "donor_dir_missing"


def test_repl_start_flag_on_attach_success_skips_start_locked(
    tmp_path: Path, flag_on: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    repl = _repl(tmp_path)
    monkeypatch.setattr(
        da, "attempt_daemon_attach",
        lambda **kw: {"ok": True, "replay_avoided": 167,
                      "donor": ".ec_session_dead", "target": repl.session_dir,
                      "session_id": "scli_t", "socket_path": "/tmp/x.sock"},
    )
    repl._snapshot_from_agent_view = (  # type: ignore[method-assign]
        lambda *, actions: "ATTACHED_SNAPSHOT"
    )
    repl._start_locked = (  # type: ignore[method-assign]
        lambda *a, **kw: (_ for _ in ()).throw(
            AssertionError("legacy start must not run on attach success")
        )
    )
    epoch_before = repl.session_epoch

    snapshot, actions = repl.start(
        replay_prefix=["t%d." % i for i in range(167)],
        daemon_attach={"donor_session_dir": ".ec_session_dead",
                       "expected_goal_hash": "abc"},
    )

    assert snapshot == "ATTACHED_SNAPSHOT"
    assert repl.session_epoch == epoch_before + 1
    assert len(actions) == 1
    assert actions[0]["label"] == "daemon_attach"
    assert actions[0]["mutates_proof_state"] is True
    assert actions[0]["replay_steps_avoided"] == 167


def test_daemon_attach_request_gating(monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = {"daemon_attach": {"donor_session_dir": ".ec_session_dead",
                             "expected_goal_hash": "h"}}
    monkeypatch.delenv("SHANNON_EC_DAEMON", raising=False)
    assert _daemon_attach_request(ctx) is None  # flag off -> legacy

    monkeypatch.setenv("SHANNON_EC_DAEMON", "1")
    assert _daemon_attach_request(ctx) == {
        "donor_session_dir": ".ec_session_dead",
        "expected_goal_hash": "h",
    }
    assert _daemon_attach_request({}) is None
    assert _daemon_attach_request({"daemon_attach": "junk"}) is None
    assert _daemon_attach_request(
        {"daemon_attach": {"donor_session_dir": "  "}}
    ) is None


def test_lifecycle_flag_off_uses_legacy_repl_start_signature(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The byte-identical guarantee: with the flag off, bootstrap must call
    ``repl.start(replay_prefix=...)`` exactly as before — the pre-existing
    ``_FakeRepl`` (whose ``start`` has NO ``daemon_attach`` kwarg) must work
    even when the resume context carries an attach request."""
    monkeypatch.delenv("SHANNON_EC_DAEMON", raising=False)
    from test_proof_node_lifecycle import _lifecycle

    lifecycle, repl, _, _, _ = _lifecycle(tmp_path)
    record = lifecycle.bootstrap(
        ["proof."],
        resume_context={
            "daemon_attach": {"donor_session_dir": ".ec_session_dead"},
        },
    )
    assert repl.started_with == ["proof."]
    assert "daemon_attach_requested" not in record
    assert "daemon_attach_result" not in record


def test_lifecycle_flag_on_records_attach_audit(
    tmp_path: Path, flag_on: None
) -> None:
    from test_proof_node_lifecycle import _FakeRepl, _lifecycle

    class _AttachRepl(_FakeRepl):
        def __init__(self) -> None:
            super().__init__()
            self.attach_seen: dict | None = None

        def start(self, replay_prefix=None, *, daemon_attach=None):
            self.attach_seen = daemon_attach
            snapshot, actions = super().start(replay_prefix)
            actions = [{
                "label": "daemon_attach",
                "exit_code": 0,
                "mutates_proof_state": True,
                "daemon_attach": {"ok": True, "replay_avoided": 1},
            }] + actions
            return snapshot, actions

    lifecycle, _, projection, lineage, audits = _lifecycle(tmp_path)
    repl = _AttachRepl()
    lifecycle.repl = repl

    record = lifecycle.bootstrap(
        ["proof."],
        resume_context={
            "daemon_attach": {
                "donor_session_dir": ".ec_session_dead",
                "expected_goal_hash": "h",
            },
        },
    )

    assert repl.attach_seen == {
        "donor_session_dir": ".ec_session_dead",
        "expected_goal_hash": "h",
    }
    assert record["daemon_attach_requested"]["donor_session_dir"] == \
        ".ec_session_dead"
    assert record["daemon_attach_result"] == {"ok": True, "replay_avoided": 1}


def test_lifecycle_flag_on_records_fallback_audit(
    tmp_path: Path, flag_on: None
) -> None:
    from test_proof_node_lifecycle import _FakeRepl, _lifecycle

    class _FallbackRepl(_FakeRepl):
        def start(self, replay_prefix=None, *, daemon_attach=None):
            snapshot, actions = super().start(replay_prefix)
            actions = [{
                "label": "daemon_attach_fallback",
                "exit_code": 0,
                "mutates_proof_state": False,
                "daemon_attach": {"ok": False, "reason": "daemon_socket_dead"},
            }] + actions
            return snapshot, actions

    lifecycle, _, _, _, _ = _lifecycle(tmp_path)
    lifecycle.repl = _FallbackRepl()

    record = lifecycle.bootstrap(
        ["proof."],
        resume_context={
            "daemon_attach": {"donor_session_dir": ".ec_session_dead"},
        },
    )
    assert record["daemon_attach_result"] == {
        "ok": False, "reason": "daemon_socket_dead",
    }


# ---------------------------------------------------------------------------
# 5. Real-EasyCrypt integration: worker death -> attach, zero replay
# ---------------------------------------------------------------------------


def _goal_body(raw: str) -> str:
    """The goal text minus the EC prompt line (`[N|check]>`), which is the
    only part allowed to differ across an attach (the counter advances)."""
    return "\n".join(
        line.rstrip()
        for line in raw.splitlines()
        if line.strip() and not (
            line.lstrip().startswith("[") and line.rstrip().endswith(">")
        )
    )


_EC_LEMMA = """require import AllCore.

lemma continuity_foo (x : int) : x + 0 = x.
proof.
admit.
qed.
"""


@pytest.mark.skipif(
    shutil.which("easycrypt") is None,
    reason="easycrypt not on PATH (eval \"$(opam env --switch=easycrypt)\"); "
           "the worker-death attach integration test needs a real EC process",
)
def test_worker_death_attach_real_ec(
    tmp_path: Path, flag_on: None
) -> None:
    """End-to-end worker-death survival: commit real tactics into a daemon
    EC session, abandon it (the worker 'dies' — nothing is closed), then
    attach a new session dir. The goal state must be preserved and the
    daemon must perform ZERO replay (committed_count unchanged, no
    open/commit RPCs issued by the attach)."""
    ec_file = tmp_path / "continuity.ec"
    ec_file.write_text(_EC_LEMMA, encoding="utf-8")
    include_dirs = [str(REPO_ROOT / "easycrypt-src" / "theories")]

    with _ServerHarness() as h:
        cli = h.client()
        donor = tmp_path / "donor_session"
        donor.mkdir()
        donor_sid = da.daemon_session_id_for_dir(donor)

        opened = cli.open_session(
            donor_sid, str(ec_file), include_dirs, "continuity_foo",
        )
        assert opened["remaining"] >= 1
        commit = cli.commit(donor_sid, "move : (x + 0).")
        assert commit["accepted"], commit
        prefix = ["move : (x + 0)."]
        goal_before = cli.get_goal(donor_sid)["raw"]
        assert goal_before.strip()

        # Disk state as the dead worker left it.
        (donor / "history.ec").write_text(prefix[0] + "\n", encoding="utf-8")
        (donor / "session_meta.json").write_text(
            json.dumps({"file": str(ec_file), "lemma": "continuity_foo"}),
            encoding="utf-8",
        )
        (donor / "daemon_state.json").write_text(
            json.dumps({
                "session_id": donor_sid,
                "committed_count": 1,
                "file_path": str(ec_file.resolve()),
                "lemma_name": "continuity_foo",
                "socket_path": h.sock,
            }),
            encoding="utf-8",
        )
        (donor / "current.out").write_text(goal_before, encoding="utf-8")
        expected_hash = da._goal_hash_from_session_dir(donor)

        # --- worker dies here: no close_session, no cleanup ---

        target = tmp_path / "respawn_session"
        result = da.attempt_daemon_attach(
            project_root=tmp_path,
            donor_session_dir=donor,
            target_session_dir=target,
            file_path=str(ec_file),
            lemma_name="continuity_foo",
            replay_prefix=prefix,
            expected_goal_hash=expected_hash,
        )
        assert result["ok"] is True, result
        assert result["replay_avoided"] == 1

        target_sid = da.daemon_session_id_for_dir(target)
        info = cli.session_info(target_sid)
        assert info["exists"] and info["ec_alive"]
        # ZERO replay: the daemon never re-committed anything.
        assert info["committed_count"] == 1
        # Goal state preserved across the "death": the post-`move` goal
        # (EC abstracts `x + 0` to a fresh variable, so the conclusion is
        # `forall (x0 : int), x0 = x`, NOT the original statement) must
        # match what the donor saw, byte-for-byte modulo the prompt line.
        goal_after = cli.get_goal(target_sid)["raw"]
        assert _goal_body(goal_after) == _goal_body(goal_before)
        assert "forall" in _goal_body(goal_after)
        assert cli.list_sessions() == [target_sid]

        # Clean-exit release of the adopted session.
        assert da.release_daemon_session(target, tmp_path) is True
        assert cli.list_sessions() == []
