"""F2: the session keeps and rewinds the daemon instead of replaying.

The daemon primitive is ``test_ec_daemon_undo.py`` and the end-to-end
equivalence with restart+replay is ``test_daemon_undo_differential.py``.
This module pins the pieces in between, without EasyCrypt:

* ``DaemonBackend`` choosing undo over reopen+replay, and never opening or
  committing in ``rewind_to`` (fake client);
* the session journal operations and their events (fake daemon);
* the CLI/manager contract of a refused rewind, and the manager fallback;
* consumers: the projection ignores a refused rewind, metrics skip the
  fallback note.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[3]

from core.easycrypt.committed_history import committed_prefix_identity  # noqa: E402
from core.easycrypt.daemon_backend import DaemonBackend, DaemonRewind  # noqa: E402
from core.easycrypt.session.session_events import append_event, read_events  # noqa: E402
from core.easycrypt.session.session_projection import (  # noqa: E402
    read_proof_state_projection,
)
from core.easycrypt.session.session_runtime import Session  # noqa: E402
from eval_suite.metrics import _primary_action  # noqa: E402
from tests.helpers.builders import start_event, write_open_goal  # noqa: E402
from workflow.proof_management.backend_actions import (  # noqa: E402
    backend_action_record,
    capture_tactic_execution_invocation,
)
from workflow.proof_management.backend_request import BackendRequest  # noqa: E402
from workflow.proof_management.repl_session import (  # noqa: E402
    ReplBackendError,
    ReplSessionManager,
)

# ---------------------------------------------------------------------------
# DaemonBackend (fake client)
# ---------------------------------------------------------------------------


class _FakeClient:
    def __init__(self, *, rewind_reply: dict[str, Any] | None = None) -> None:
        self.sessions = ["scli"]
        self.calls: list[tuple[str, Any]] = []
        self.rewind_reply = rewind_reply or {
            "rewound": True, "undone": 1, "raw_output": "Current goal\n\nx\n[3|check]>",
        }

    def list_sessions(self):
        return list(self.sessions)

    def rewind(self, session_id, keep, **kwargs):
        self.calls.append(("rewind", (keep, kwargs)))
        return self.rewind_reply

    def open_session(self, *args, **kwargs):
        self.calls.append(("open_session", args))
        return {}

    def close_session(self, session_id):
        self.calls.append(("close_session", session_id))
        return True

    def commit(self, session_id, tactic, timeout=None):
        self.calls.append(("commit", tactic))
        return {"accepted": True, "raw_output": ""}


def _backend(tmp_path: Path, client: _FakeClient, held: list[str]) -> DaemonBackend:
    source = tmp_path / "x.ec"
    source.write_text("", encoding="utf-8")
    backend = DaemonBackend(tmp_path, [], socket_path=str(tmp_path / "missing.sock"))
    backend._session_id = "scli"
    backend._client = client  # type: ignore[assignment]
    backend._ensure_daemon = lambda: client  # type: ignore[method-assign]
    backend._save_state({
        "session_id": "scli",
        "committed_count": len(held),
        "committed_prefix_sha256": committed_prefix_identity(held),
        "file_path": str(source.resolve()),
        "lemma_name": "L",
        "socket_path": backend.socket_path,
    })
    return backend


def test_sync_to_a_shorter_journal_undoes_instead_of_reopening(tmp_path: Path) -> None:
    held = ["a.", "b. c.", "d."]
    client = _FakeClient()
    backend = _backend(tmp_path, client, held)
    assert backend._sync_to(tmp_path / "x.ec", "L", held[:2])
    assert client.calls == [(
        "rewind",
        (2, {
            "keep_identity": committed_prefix_identity(held[:2]),
            "held_identity": committed_prefix_identity(held),
            "require_open_goal": False,
        }),
    )]
    state = backend._load_state()
    assert state["committed_count"] == 2
    assert state["committed_prefix_sha256"] == committed_prefix_identity(held[:2])


def test_sync_to_reopens_and_replays_when_the_daemon_refuses(tmp_path: Path) -> None:
    held = ["a.", "b.", "c."]
    client = _FakeClient(rewind_reply={"rewound": False, "reason": "transaction_3_not_undoable"})
    backend = _backend(tmp_path, client, held)
    assert backend._sync_to(tmp_path / "x.ec", "L", held[:2])
    kinds = [kind for kind, _ in client.calls]
    assert kinds == ["rewind", "close_session", "open_session", "commit", "commit"]


def test_rewind_to_only_ever_undoes(tmp_path: Path) -> None:
    held = ["a.", "b.", "c."]
    client = _FakeClient()
    backend = _backend(tmp_path, client, held)
    source = tmp_path / "x.ec"
    # Holding exactly the target: nothing to do, nothing sent.
    assert backend.rewind_to(source, "L", held) == DaemonRewind(post_raw="", undone=0)
    # Longer target than held: refuse (that needs commits).
    assert backend.rewind_to(source, "L", held + ["d."]) is None
    # A different history of the same length: refuse.
    assert backend.rewind_to(source, "L", ["a.", "b.", "x."]) is None
    assert client.calls == []
    # A proper prefix: one rewind RPC.
    reply = backend.rewind_to(source, "L", held[:1], require_open_goal=True)
    assert reply == DaemonRewind(post_raw=client.rewind_reply["raw_output"], undone=1)
    assert client.calls[0][1][1]["require_open_goal"] is True
    # A vanished session or a refusal: refuse, never reopen.
    client.sessions = []
    assert backend.rewind_to(source, "L", []) is None
    client.sessions = ["scli"]
    client.rewind_reply = {"rewound": False, "reason": "undo_levels_unknown"}
    assert backend.rewind_to(source, "L", []) is None
    assert "undo_levels_unknown" in backend.last_error
    assert {kind for kind, _ in client.calls} == {"rewind"}


# ---------------------------------------------------------------------------
# Session journal operations (fake daemon)
# ---------------------------------------------------------------------------


def _session(tmp_path: Path, transactions: list[str]) -> Session:
    session = Session(tmp_path / "s")
    session.history.write_text("".join(t + "\n" for t in transactions))
    session.steps.write_text("".join(f"{len(t.splitlines())}\n" for t in transactions))
    session.curr.write_text("Current goal\n\nlatest\n[9|check]>")
    session.prev.write_text("Current goal\n\nlatest\n[9|check]>")
    return session


def test_rewind_to_command_count_refuses_inside_a_transaction(tmp_path: Path) -> None:
    session = _session(tmp_path, ["a.", "b. c.", "d."])
    before = session.history.read_text()
    result = session.rewind_to_command_count(2)
    assert result.status == "unavailable"
    assert "does not end a committed transaction" in result.reason
    assert session.history.read_text() == before
    assert read_events(session.dir)[-1]["payload"]["status"] == "unavailable"


def test_rewind_to_command_count_refuses_a_journal_with_a_pragma(
    tmp_path: Path, monkeypatch,
) -> None:
    session = _session(tmp_path, ["a.", "pragma Proofs:weak. b.", "c."])
    monkeypatch.setattr(
        session, "_daemon_undo_to",
        lambda *a, **k: pytest.fail("the daemon must not be asked"),
    )
    result = session.rewind_to_command_count(3)
    assert result.status == "unavailable"
    assert "pragma Proofs:weak." in result.reason


def test_rewind_to_command_count_trims_the_journal_after_the_daemon_undo(
    tmp_path: Path, monkeypatch,
) -> None:
    session = _session(tmp_path, ["a.", "b.\nc.", "d."])
    asked: list[tuple[list[str], dict]] = []

    def fake_undo(transactions, **kwargs):
        asked.append((list(transactions), kwargs))
        return DaemonRewind(post_raw="Current goal\n\nafter a\n[4|check]>", undone=2), ""

    monkeypatch.setattr(session, "_daemon_undo_to", fake_undo)
    result = session.rewind_to_command_count(1)
    assert asked == [(["a."], {"require_open_goal": True})]
    assert result.status == "ok" and result.undone_count == 2
    assert session.history.read_text() == "a.\n"
    assert session.steps.read_text() == "1\n"
    assert "after a" in session.curr.read_text()
    assert session.prev.read_text() == session.curr.read_text()
    undone = read_events(session.dir)[-1]["payload"]
    assert undone == {
        "status": "ok",
        "undone_tactic": "b.\nc.\nd.",
        "remaining_steps": 1,
        "history_lines_after": 1,
        "undone_count": 2,
        "backend": "daemon_undo",
    }


def test_rewind_to_command_count_reports_a_daemon_refusal(tmp_path: Path, monkeypatch) -> None:
    session = _session(tmp_path, ["a.", "b."])
    monkeypatch.setattr(
        session, "_daemon_undo_to",
        lambda *a, **k: (None, "daemon rewind refused: target_state_has_no_open_goal"),
    )
    result = session.rewind_to_command_count(1)
    assert result.status == "unavailable"
    assert "no_open_goal" in result.reason
    assert session.history.read_text() == "a.\nb.\n"


@pytest.mark.parametrize("daemon_follows", [True, False])
def test_roll_back_keeps_the_daemon_only_when_it_follows_the_journal(
    tmp_path: Path, monkeypatch, daemon_follows: bool,
) -> None:
    session = _session(tmp_path, ["a."])
    session._rollback.snapshot_pre_commit(1)
    session.history.write_text("a.\nb.\n")
    session.steps.write_text("1\n1\n")
    invalidated: list[bool] = []
    monkeypatch.setattr(
        session, "_daemon_undo_to",
        lambda transactions, **k: (
            (DaemonRewind("", 1), "") if daemon_follows else (None, "refused")
        ),
    )
    monkeypatch.setattr(session, "_invalidate_daemon", lambda: invalidated.append(True))
    session._roll_back()
    assert session.history.read_text() == "a.\n"
    assert invalidated == ([] if daemon_follows else [True])


def test_step_up_falls_back_to_the_batch_replay_without_a_daemon(
    tmp_path: Path, monkeypatch,
) -> None:
    session = _session(tmp_path, ["a.", "b."])
    replays: list[bool] = []
    monkeypatch.setattr(session, "replay_current", lambda: replays.append(True))
    monkeypatch.setattr(session, "_invalidate_daemon", lambda: None)
    result = session.step_up()
    assert result.status == "ok" and result.backend == "batch_replay"
    assert replays == [True]
    assert read_events(session.dir)[-1]["payload"]["backend"] == "batch_replay"


# ---------------------------------------------------------------------------
# CLI / manager contract of a refused rewind
# ---------------------------------------------------------------------------


@pytest.mark.easycrypt
def test_refused_rewind_is_an_unchanged_event_bound_undo_result(tmp_path: Path) -> None:
    session_dir = tmp_path / ".ec_session_refused_rewind"
    session_dir.mkdir()
    start_event(session_dir)
    write_open_goal(session_dir)
    (session_dir / "history.ec").write_text("a.\nb.\n")
    (session_dir / "steps.log").write_text("1\n1\n")
    request = BackendRequest.undo("undo_to_checkpoint", keep_commands=1)
    assert request.args == ("-tactic-exec", "undo", "--keep-commands", "1")
    cmd = [sys.executable, "core/easycrypt/session_cli.py", "-d", str(session_dir), *request.args]
    boundary = capture_tactic_execution_invocation(session_dir, request)
    completed = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=False)
    assert completed.returncode == 0, completed.stderr
    action = backend_action_record(
        request, cmd, completed, tactic_execution_boundary=boundary,
    )
    assert "contract_error" not in action
    assert action["outcome_kind"] == "no_progress"
    assert action["proof_state_changed"] is False
    undone = [e["payload"] for e in read_events(session_dir) if e["type"] == "tactic.undone"]
    assert undone[-1]["status"] == "unavailable"
    assert (session_dir / "history.ec").read_text() == "a.\nb.\n"


def test_projection_ignores_a_refused_rewind(tmp_path: Path) -> None:
    session_dir = tmp_path / "s"
    session_dir.mkdir()
    start_event(session_dir)
    write_open_goal(session_dir)
    (session_dir / "history.ec").write_text("a.\n")
    append_event(session_dir, "tactic.result", {
        "tactic": "a.", "status": "ok", "history_committed": True,
    })
    before = read_proof_state_projection(session_dir).latest_transition
    append_event(session_dir, "tactic.undone", {
        "status": "unavailable", "undone_tactic": "", "remaining_steps": 1,
        "reason": "daemon unavailable",
    })
    assert read_proof_state_projection(session_dir).latest_transition == before
    append_event(session_dir, "tactic.undone", {
        "status": "ok", "undone_tactic": "a.", "remaining_steps": 0,
    })
    assert read_proof_state_projection(session_dir).latest_transition.kind == "undo"


def _manager(tmp_path: Path) -> tuple[ReplSessionManager, Path]:
    repl = ReplSessionManager(
        file_path="eval/examples/SchnorrPK.ec",
        lemma_name="dummy",
        include_dir="easycrypt-src/theories",
        session_tag="unit",
        node_id="Tree-unit",
        project_root=tmp_path,
    )
    repl.session_dir = "session"
    session_dir = tmp_path / "session"
    session_dir.mkdir()
    (session_dir / "history.ec").write_text("a.\nb.\nc.\n")
    repl._snapshot_from_managed_goal_view = (  # type: ignore[method-assign]
        lambda *, actions: object()
    )
    return repl, session_dir


def test_backend_error_on_the_rewind_attempt_falls_back_to_restart(tmp_path: Path) -> None:
    repl, _session_dir = _manager(tmp_path)
    calls: list[str] = []

    def fake_backend(request, *, actions, timeout):  # noqa: ANN001
        calls.append(request.kind)
        action = {"label": request.label, "exit_code": 1, "argv": ["x"]}
        actions.append(action)
        if request.kind == "undo":
            raise ReplBackendError({**action, "outcome_kind": "backend_error"})
        return ""

    repl._run_backend = fake_backend  # type: ignore[method-assign]
    _snapshot, actions = repl.rewind_before_tactic(2)
    assert calls == ["undo", "start", "commit"]
    assert actions[0]["label"] == "daemon_undo_fallback"
    assert actions[0]["daemon_undo"]["keep_commands"] == 1
    assert "exited with code 1" in actions[0]["daemon_undo"]["reason"]


def test_restore_extending_the_history_needs_no_undo(tmp_path: Path) -> None:
    repl, session_dir = _manager(tmp_path)
    calls: list[tuple[str, str]] = []

    def fake_backend(request, *, actions, timeout):  # noqa: ANN001
        calls.append((request.kind, request.label))
        actions.append({"label": request.label, "exit_code": 0})
        with (session_dir / "history.ec").open("a") as history:
            history.write(request.tactic + "\n")
        return ""

    repl._run_backend = fake_backend  # type: ignore[method-assign]
    epoch = repl.session_epoch
    _snapshot, actions = repl.restore_committed_tactics(["a.", "b.", "c.", "d.", "e."])
    assert calls == [
        ("commit", "replay_prefix_step_4"),
        ("commit", "replay_prefix_step_5"),
    ]
    assert actions[0]["label"] == "restore_pre_rewind"
    assert actions[0]["replay_steps_avoided"] == 3
    assert actions[0]["mutates_proof_state"] is False
    assert repl.session_epoch == epoch + 1
    assert not [a for a in actions if a["label"] == "replay_prefix_divergence"]


def test_amend_undoes_to_the_edit_and_stops_at_the_first_drop(tmp_path: Path) -> None:
    repl, session_dir = _manager(tmp_path)
    (session_dir / "history.ec").write_text("a.\nb.\nc.\nd.\n")
    calls: list[str] = []

    def fake_backend(request, *, actions, timeout):  # noqa: ANN001
        calls.append(request.label)
        action = {"label": request.label, "exit_code": 0}
        history = session_dir / "history.ec"
        if request.kind == "undo":
            keep = int(request.args[-1])
            lines = history.read_text().splitlines()[:keep]
            history.write_text("".join(f"{line}\n" for line in lines))
            action["proof_state_changed"] = True
        elif request.tactic != "c.":   # the edit invalidates c.
            with history.open("a") as stream:
                stream.write(request.tactic + "\n")
        actions.append(action)
        return ""

    repl._run_backend = fake_backend  # type: ignore[method-assign]
    _snapshot, actions = repl.restart_with_edited_prefix(["a.", "B.", "c.", "d."])
    assert calls == ["restart_replay_edit", "replay_prefix_step_2", "replay_prefix_step_3"]
    stopped = [a for a in actions if a["label"] == "replay_prefix_stopped_at_divergence"]
    assert stopped and stopped[0]["replay_stopped_at_step"] == 3
    assert stopped[0]["replay_kept_count"] == 2
    assert stopped[0]["replay_requested_count"] == 4
    assert repl.committed_history() == ["a.", "B."]


def test_metrics_primary_action_skips_recovery_fallback_notes() -> None:
    actions = [
        {"label": "daemon_undo_fallback"},
        {"label": "undo_to_checkpoint", "outcome_kind": "accepted"},
        {"label": "managed_goal_view"},
    ]
    assert _primary_action(actions)["label"] == "undo_to_checkpoint"
    assert json.dumps(_primary_action([{"label": "managed_goal_view"}]))
