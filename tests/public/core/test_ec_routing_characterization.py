"""Characterization of the EC daemon-vs-batch routing decision in
Session.append_block.

Drives a real Session.append_block in a tmpdir with NO real EasyCrypt and NO real
daemon: the batch backend's process spawn is replaced (it writes a fixed
transcript) and DaemonBackend is faked. Freezes the 9-row decision matrix — in
particular the load-bearing invariant that a daemon REJECT is NOT a batch
fallback (row 2), also when EasyCrypt ran out of time (row 9).
"""
from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest


from core.easycrypt.daemon_backend import DaemonCommit  # noqa: E402
from core.easycrypt.ec_backend import BatchBackend  # noqa: E402
from core.easycrypt.session.session_events import read_events  # noqa: E402
from core.easycrypt.session.session_runtime import Session  # noqa: E402

# A minimal EC -emacs transcript the batch path can parse without crashing.
_EC_OUT = "Current goal\n\nType variables: <none>\n\nremaining goals: 0\n\n[1|check]>\n"

ACCEPT = DaemonCommit(_EC_OUT)
REJECT = DaemonCommit(_EC_OUT, "[error] nope")
TIMED_OUT = DaemonCommit(
    "", "[error] EasyCrypt did not finish this transaction within 170 s",
)


class _FakeBackend:
    """Stand-in for daemon_backend.DaemonBackend. Behaviour is set per-test via
    class attributes so the session's `DaemonBackend(...)` picks them up."""
    construct_raises = False
    commit_result = ACCEPT      # DaemonCommit | None
    commit_raises = False
    commits = 0

    def __init__(self, session_dir, include_dirs, socket_path=None):
        if type(self).construct_raises:
            raise RuntimeError("daemon construct failed")

    def commit_latest(self, fp, lname, tactics):
        type(self).commits += 1
        if type(self).commit_raises:
            raise RuntimeError("commit RPC failed")
        return type(self).commit_result

    def get_goal_raw(self):
        return _EC_OUT

    def invalidate(self):
        pass


class _FakeBatch(BatchBackend):
    """The real batch backend with EasyCrypt replaced by a fixed transcript."""

    def __init__(self, session_dir):
        super().__init__(session_dir)
        self.runs = 0

    def run(self, input_path, output_path, include_dirs, timeout=None):
        self.runs += 1
        Path(output_path).write_text(_EC_OUT, encoding="utf-8")
        return 0


def _make_session(tmp_path, *, with_meta=True):
    session_dir = tmp_path / "sess"
    sess = Session(session_dir, batch=_FakeBatch(session_dir))
    if with_meta:
        real_ec = tmp_path / "real.ec"
        real_ec.write_text("lemma foo : true. proof. trivial. qed.\n", encoding="utf-8")
        (Path(sess.dir) / "session_meta.json").write_text(
            json.dumps({"file": str(real_ec), "lemma": "foo"}), encoding="utf-8"
        )
    return sess


def _drive(monkeypatch, sess, *, disabled=False,
           construct_raises=False, commit_result=ACCEPT, commit_raises=False,
           write_compressed_raises=False):
    """Run append_block once with the daemon + EC stubbed; return observations."""
    _FakeBackend.construct_raises = construct_raises
    _FakeBackend.commit_result = commit_result
    _FakeBackend.commit_raises = commit_raises
    _FakeBackend.commits = 0

    db = importlib.import_module("core.easycrypt.daemon_backend")
    monkeypatch.setattr(db, "DaemonBackend", _FakeBackend, raising=True)
    monkeypatch.setattr(db, "is_disabled", lambda: disabled, raising=True)
    if write_compressed_raises:
        def _wcc(self, raw):
            raise RuntimeError("curr-compressed write failed")
        monkeypatch.setattr(type(sess), "_write_curr_compressed", _wcc, raising=True)

    sess.append_block("trivial.")
    events = read_events(Path(sess.dir))
    routing = [e["payload"] for e in events if e["type"] == "ec.routing"]
    result = [e["payload"] for e in events if e["type"] == "tactic.result"][-1]
    return {
        "runs": sess._batch.runs,
        "commit": _FakeBackend.commits,
        "via_daemon": result["daemon_used"],
        "reason": routing[-1]["reason"] if routing else "",
        "routing": routing,
    }


# --- the 9-row matrix --------------------------------------------------------

def test_row1_daemon_accept(monkeypatch, tmp_path):
    o = _drive(monkeypatch, _make_session(tmp_path), commit_result=ACCEPT)
    assert o["runs"] == 0 and o["commit"] == 1
    assert o["via_daemon"] is True
    assert o["reason"] == "daemon_accept"


def test_row2_daemon_reject_is_NOT_batch_fallback(monkeypatch, tmp_path):
    # The load-bearing invariant: a daemon REJECT still skips batch.
    o = _drive(monkeypatch, _make_session(tmp_path), commit_result=REJECT)
    assert o["runs"] == 0 and o["commit"] == 1
    assert o["via_daemon"] is False
    assert o["reason"] == "daemon_reject"


def test_row3_disabled_goes_batch(monkeypatch, tmp_path):
    o = _drive(monkeypatch, _make_session(tmp_path), disabled=True)
    assert o["runs"] == 1 and o["commit"] == 0
    assert o["reason"] == "disabled"


def test_row4_no_meta_goes_batch(monkeypatch, tmp_path):
    o = _drive(monkeypatch, _make_session(tmp_path, with_meta=False))
    assert o["runs"] == 1 and o["commit"] == 0
    assert o["reason"] == "no_meta"


def test_row5_commit_raises_falls_back_to_batch(monkeypatch, tmp_path):
    # daemon-FAIL -> batch fallback (the most sensitive distinction vs row 2).
    o = _drive(monkeypatch, _make_session(tmp_path), commit_raises=True)
    assert o["runs"] == 1 and o["commit"] == 1
    assert o["reason"] == "commit_exception"


def test_row6_commit_none_falls_back_to_batch(monkeypatch, tmp_path):
    o = _drive(monkeypatch, _make_session(tmp_path), commit_result=None)
    assert o["runs"] == 1 and o["commit"] == 1
    assert o["reason"] == "commit_none"


def test_row7_construct_raises_goes_batch(monkeypatch, tmp_path):
    o = _drive(monkeypatch, _make_session(tmp_path), construct_raises=True)
    assert o["runs"] == 1 and o["commit"] == 0
    assert o["reason"] == "construct_fail"


def test_row8_write_fail_falls_back_to_batch(monkeypatch, tmp_path):
    """A post-RPC prev/curr write that raises routes `write_fail`, a batch
    fallback."""
    o = _drive(monkeypatch, _make_session(tmp_path), commit_result=ACCEPT,
               write_compressed_raises=True)
    assert o["runs"] == 1 and o["commit"] == 1
    assert o["via_daemon"] is False
    assert o["reason"] == "write_fail"


def test_row9_daemon_timeout_is_a_daemon_reject(monkeypatch, tmp_path):
    # A batch run would spend the same time on the same tactic again.
    o = _drive(monkeypatch, _make_session(tmp_path), commit_result=TIMED_OUT)
    assert o["runs"] == 0 and o["commit"] == 1
    assert o["via_daemon"] is False
    assert o["reason"] == "daemon_reject"


def test_reject_does_not_write_error_into_curr(monkeypatch, tmp_path):
    """On a daemon REJECT the reply written to curr is rolled back (curr<-prev)
    and the rejection text is NEVER written into current.out; it rides home in
    the commit outcome instead."""
    sess = _make_session(tmp_path)
    _drive(monkeypatch, sess, commit_result=REJECT)
    curr = (Path(sess.dir) / "current.out").read_bytes()
    prev = (Path(sess.dir) / "prev.out").read_bytes()
    assert curr == prev               # the rollback ran; nothing wrote curr after
    assert b"[error]" not in curr     # the rejection text did not leak into curr


def test_ec_routing_event_is_emitted(monkeypatch, tmp_path):
    """append_block records the routing decision as an `ec.routing` audit event
    carrying the backend + reason."""
    o_batch = _drive(monkeypatch, _make_session(tmp_path / "b"), disabled=True)
    assert o_batch["routing"] == [{"backend": "batch", "reason": "disabled"}]

    o_daemon = _drive(monkeypatch, _make_session(tmp_path / "d"), commit_result=ACCEPT)
    assert o_daemon["routing"] == [{"backend": "daemon", "reason": "daemon_accept"}]


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
