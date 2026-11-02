"""A daemon rejection is rolled back, and one whose rollback fails fails the commit."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import core.easycrypt.daemon_backend as daemon_backend
from core.easycrypt.daemon_backend import DaemonCommit, _rejection
from core.easycrypt.session.session_runtime import Session
from core.easycrypt.session.session_events import read_events

_EC_OUT = "Current goal\n\n  true\n[1|check]>\n"


class _RejectingDaemon:
    calls: list[str] = []

    def __init__(self, session_dir, include_dirs, socket_path=None) -> None:
        pass

    def commit_latest(self, fp, lname, tactics):
        return DaemonCommit(_EC_OUT, "[error] nope")

    def invalidate(self) -> None:
        type(self).calls.append("invalidate")


def _session(tmp_path: Path, monkeypatch) -> Session:
    session = Session(tmp_path / "sess")
    source = tmp_path / "real.ec"
    source.write_text("lemma foo : true. proof. trivial. qed.\n", encoding="utf-8")
    (Path(session.dir) / "session_meta.json").write_text(
        json.dumps({"file": str(source), "lemma": "foo"}), encoding="utf-8",
    )
    session.history.write_text("split.\n", encoding="utf-8")
    session.steps.write_text("1\n", encoding="utf-8")
    _RejectingDaemon.calls = []
    monkeypatch.setattr(daemon_backend, "DaemonBackend", _RejectingDaemon)
    monkeypatch.setattr(daemon_backend, "is_disabled", lambda: False)
    return session


def test_a_rejection_is_rolled_back_and_reported(tmp_path, monkeypatch) -> None:
    session = _session(tmp_path, monkeypatch)

    result = session.append_block("bad_tactic.")

    assert result.status == "error"
    assert result.latest_error == "[error] nope"
    assert not result.history_committed
    assert session.history.read_text() == "split.\n"
    assert session.steps.read_text() == "1\n"
    assert _RejectingDaemon.calls == ["invalidate"]


def test_a_failed_rollback_fails_the_commit_after_invalidating(tmp_path, monkeypatch) -> None:
    session = _session(tmp_path, monkeypatch)

    def broken_restore() -> None:
        raise OSError("disk full")

    monkeypatch.setattr(session._rollback, "restore_pre_commit", broken_restore)

    with pytest.raises(OSError, match="disk full"):
        session.append_block("bad_tactic.")

    assert _RejectingDaemon.calls == ["invalidate"]
    results = [e for e in read_events(Path(session.dir)) if e.get("type") == "tactic.result"]
    assert results == []


@pytest.mark.parametrize(("error", "post_raw", "expected"), [
    ({"raw": "[error] nope"}, "", "[error] nope"),
    ({"kind": "other", "raw": "cannot infer all placeholders"}, "",
     "[error] cannot infer all placeholders"),
    ({"message": "boom"}, "", "[error] boom"),
    (None, "noise\n  [critical] nothing to rewrite\n[3|check]>\n",
     "[critical] nothing to rewrite"),
    ({}, "[2|check]>\n", "[error] daemon rejection"),
])
def test_the_rejection_names_the_daemon_error(error, post_raw, expected) -> None:
    assert _rejection(error, post_raw) == expected
