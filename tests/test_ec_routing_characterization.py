"""Characterization of the EC daemon-vs-batch routing decision in
Session.append_block, locked BEFORE the #3 Step-5 routing lift
(docs/refactor_ec_routing_lift_blueprint.md §2).

Drives a real Session.append_block in a tmpdir with NO real EasyCrypt and NO real
daemon: _run_ec is spied (and writes its output so downstream parsing survives),
DaemonBackend is faked. Freezes the 8-row decision matrix — in particular the
load-bearing invariant that a daemon REJECT is NOT a batch fallback (row 2).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

import importlib  # noqa: E402

from core.easycrypt.session_api import open_session  # noqa: E402

# NOTE: open_session yields an instance of the *bare-import* `session_runtime.Session`
# (the dual-import shim), NOT core.easycrypt.session_runtime.Session — so patches
# must target `type(sess)` and the bare `daemon_backend` module that
# `_try_daemon_path` imports lazily, never the core.easycrypt.* aliases.

# A minimal EC -emacs transcript the batch path can parse without crashing.
_EC_OUT = "Current goal\n\nType variables: <none>\n\nremaining goals: 0\n\n[1|check]>\n"

ACCEPT = {"post_raw": _EC_OUT, "accepted": True, "goal_after": {}, "error": None, "no_progress": False}
REJECT = {"post_raw": _EC_OUT, "accepted": False, "goal_after": {}, "error": {"raw": "[error] nope"}, "no_progress": False}


class _FakeBackend:
    """Stand-in for daemon_backend.DaemonBackend. Behaviour is set per-test via
    class attributes so _try_daemon_path's `DaemonBackend(...)` picks them up."""
    construct_raises = False
    commit_result = ACCEPT      # dict | None
    commit_raises = False

    def __init__(self, session_dir, include_dirs, socket_path=None):
        if type(self).construct_raises:
            raise RuntimeError("daemon construct failed")

    def try_commit_latest(self, fp, lname, tactics):
        if type(self).commit_raises:
            raise RuntimeError("commit RPC failed")
        return type(self).commit_result

    def get_goal_raw(self):
        return _EC_OUT

    def invalidate(self):
        pass


def _make_session(tmp_path, *, with_meta=True):
    sess = open_session(tmp_path / "sess")
    if with_meta:
        real_ec = tmp_path / "real.ec"
        real_ec.write_text("lemma foo : true. proof. trivial. qed.\n", encoding="utf-8")
        (Path(sess.dir) / "session_meta.json").write_text(
            json.dumps({"file": str(real_ec), "lemma": "foo"}), encoding="utf-8"
        )
    return sess


def _drive(monkeypatch, sess, *, disabled=False,
           construct_raises=False, commit_result=ACCEPT, commit_raises=False,
           write_compressed_raises=False, write_compressed=None):
    """Run append_block once with the daemon + EC stubbed; return observations."""
    obs = {"run_ec": 0, "commit": 0, "compress": 0}

    _FakeBackend.construct_raises = construct_raises
    _FakeBackend.commit_result = commit_result
    _FakeBackend.commit_raises = commit_raises

    SessionCls = type(sess)                          # the class actually in use
    db = importlib.import_module("core.easycrypt.daemon_backend")  # the module _try_daemon_path imports
    monkeypatch.setattr(db, "DaemonBackend", _FakeBackend, raising=True)
    monkeypatch.setattr(db, "is_disabled", lambda: disabled, raising=True)

    orig_commit = _FakeBackend.try_commit_latest

    def _commit_spy(self, *a, **k):
        obs["commit"] += 1
        return orig_commit(self, *a, **k)
    monkeypatch.setattr(_FakeBackend, "try_commit_latest", _commit_spy, raising=True)

    def _run_ec_spy(self, input_path, output_path, include_dirs=None):
        obs["run_ec"] += 1
        Path(output_path).write_text(_EC_OUT, encoding="utf-8")
    monkeypatch.setattr(SessionCls, "_run_ec", _run_ec_spy, raising=True)

    def _compress_spy(self):
        obs["compress"] += 1
    monkeypatch.setattr(SessionCls, "_compress_curr_inplace", _compress_spy, raising=True)
    if write_compressed_raises:
        def _wcc(self, raw):
            raise RuntimeError("curr-compressed write failed")
        monkeypatch.setattr(SessionCls, "_write_curr_compressed", _wcc, raising=True)
    else:
        monkeypatch.setattr(
            SessionCls, "_write_curr_compressed",
            write_compressed or (lambda self, raw: None), raising=True,
        )

    emitted: list = []
    orig_emit = SessionCls.emit_event

    def _emit_spy(self, event_type, payload=None, *, source="session_cli"):
        emitted.append((event_type, payload))
        return orig_emit(self, event_type, payload, source=source)
    monkeypatch.setattr(SessionCls, "emit_event", _emit_spy, raising=True)

    sess.append_block("trivial.")
    obs["via_daemon"] = bool(getattr(sess, "_last_commit_via_daemon", False))
    obs["reason"] = getattr(sess, "_last_routing_reason", "")
    obs["events"] = emitted
    return obs


# --- the 8-row matrix --------------------------------------------------------

def test_row1_daemon_accept(monkeypatch, tmp_path):
    o = _drive(monkeypatch, _make_session(tmp_path), commit_result=ACCEPT)
    assert o["run_ec"] == 0 and o["commit"] == 1 and o["compress"] == 0
    assert o["via_daemon"] is True
    assert o["reason"] == "daemon_accept"


def test_row2_daemon_reject_is_NOT_batch_fallback(monkeypatch, tmp_path):
    # The load-bearing invariant: a daemon REJECT still skips batch.
    o = _drive(monkeypatch, _make_session(tmp_path), commit_result=REJECT)
    assert o["run_ec"] == 0 and o["commit"] == 1 and o["compress"] == 0
    assert o["via_daemon"] is False
    assert o["reason"] == "daemon_reject"


def test_row3_disabled_goes_batch(monkeypatch, tmp_path):
    o = _drive(monkeypatch, _make_session(tmp_path), disabled=True)
    assert o["run_ec"] == 2 and o["commit"] == 0 and o["compress"] == 1
    assert o["reason"] == "disabled"


def test_row4_no_meta_goes_batch(monkeypatch, tmp_path):
    o = _drive(monkeypatch, _make_session(tmp_path, with_meta=False))
    assert o["run_ec"] == 2 and o["commit"] == 0 and o["compress"] == 1
    assert o["reason"] == "no_meta"


def test_row5_commit_raises_falls_back_to_batch(monkeypatch, tmp_path):
    # daemon-FAIL -> batch fallback (the lift's most sensitive distinction vs row 2).
    o = _drive(monkeypatch, _make_session(tmp_path), commit_raises=True)
    assert o["run_ec"] == 2 and o["commit"] == 1 and o["compress"] == 1
    assert o["reason"] == "commit_exception"


def test_row6_commit_none_falls_back_to_batch(monkeypatch, tmp_path):
    o = _drive(monkeypatch, _make_session(tmp_path), commit_result=None)
    assert o["run_ec"] == 2 and o["commit"] == 1 and o["compress"] == 1
    assert o["reason"] == "commit_none"


def test_row7_construct_raises_goes_batch(monkeypatch, tmp_path):
    o = _drive(monkeypatch, _make_session(tmp_path), construct_raises=True)
    assert o["run_ec"] == 2 and o["commit"] == 0 and o["compress"] == 1
    assert o["reason"] == "construct_fail"


def test_row8_write_fail_falls_back_to_batch(monkeypatch, tmp_path):
    """A post-RPC prev/curr write that raises routes `write_fail`, which is
    took_daemon=False -> batch fallback. Previously UNcharacterized; the ECBackend
    lift converts this except-branch into a DaemonCommitOutcome.write_failed field,
    so this row guards that control-flow change."""
    o = _drive(monkeypatch, _make_session(tmp_path), commit_result=ACCEPT,
               write_compressed_raises=True)
    assert o["run_ec"] == 2 and o["commit"] == 1 and o["compress"] == 1
    assert o["via_daemon"] is False
    assert o["reason"] == "write_fail"


def test_reject_does_not_write_error_into_curr(monkeypatch, tmp_path):
    """Invariant C: on a daemon REJECT the speculative curr write is rolled back
    (curr<-prev) and the daemon's [error] text is NEVER written into current.out
    (it rides home in ECResult.rejection_error instead). The subtlest invariant
    the ECBackend lift must preserve — pinned with a real curr-writing stub so a
    stray error-into-curr would be caught."""
    sess = _make_session(tmp_path)
    _drive(monkeypatch, sess, commit_result=REJECT,
           write_compressed=lambda self, raw: (Path(self.dir) / "current.out").write_text(raw, encoding="utf-8"))
    curr = (Path(sess.dir) / "current.out").read_bytes()
    prev = (Path(sess.dir) / "prev.out").read_bytes()
    assert curr == prev               # restore_pre_commit ran; nothing wrote curr after
    assert b"[error]" not in curr     # the rejection text did not leak into curr


def test_ec_routing_event_is_emitted(monkeypatch, tmp_path):
    """The routing decision is no longer a silent boolean — append_block emits an
    `ec.routing` audit event carrying the backend + reason (#3 Step 5 visibility)."""
    o_batch = _drive(monkeypatch, _make_session(tmp_path), disabled=True)
    routing = [p for (n, p) in o_batch["events"] if n == "ec.routing"]
    assert routing == [{"backend": "batch", "reason": "disabled"}]

    o_daemon = _drive(monkeypatch, _make_session(tmp_path), commit_result=ACCEPT)
    routing = [p for (n, p) in o_daemon["events"] if n == "ec.routing"]
    assert routing == [{"backend": "daemon", "reason": "daemon_accept"}]


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
