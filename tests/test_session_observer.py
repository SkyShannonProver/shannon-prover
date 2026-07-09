"""Tests for workflow-level EasyCrypt session observation."""
from __future__ import annotations

import json
import tempfile
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]

import sys
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from core.easycrypt.session_commit_response import write_commit_response_artifact  # noqa: E402
from core.easycrypt.session_events import append_event  # noqa: E402
from core.easycrypt.session_tactic_execution_result import (  # noqa: E402
    write_tactic_execution_result_artifact,
)
from tests.helpers.builders import (  # noqa: E402
    start_event,
    tool_called,
    tool_result,
    write_open_goal,
)
from workflow.progress import _ProverTracker, _resume_replay_gate  # noqa: E402
from workflow.session_observer import WorkflowSessionSnapshot, observe_session  # noqa: E402

_start_event = start_event
_tool_called = tool_called
_tool_result = tool_result
_open_state = write_open_goal


def _commit_response(
    d: Path,
    *,
    command: str = "chain",
    status: str = "ok",
    attempted: list[str] | None = None,
    accepted_count: int = 0,
    failed_tactic: str = "",
    failure_reason: str = "",
) -> dict:
    attempted = attempted or []
    response = {
        "schema_version": 1,
        "kind": "commit_response",
        "ok": status in {"ok", "undone"},
        "command": command,
        "status": status,
        "proof_state": {"status": "open"},
        "latest_transition": {},
        "mutation": {
            "attempted_count": len(attempted),
            "accepted_count": accepted_count,
            "attempted_tactics": attempted,
            "failed_tactic": failed_tactic,
            "failure_reason": failure_reason,
            "keep_on_fail": False,
            "rollback_count": 0 if status == "ok" else 1,
        },
        "agent_view": {},
        "notes": [],
        "errors": [] if status == "ok" else [{
            "code": "commit.failed",
            "message": failure_reason,
        }],
        "debug": {},
    }
    payload = write_commit_response_artifact(d, response)
    append_event(d, "commit.response.produced", payload)
    return payload


def test_observer_reads_failed_commit_response() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        _open_state(d)
        (d / "history.ec").write_text("proc.\n", encoding="utf-8")
        _start_event(d)
        _tool_called(d, "next")
        append_event(d, "tactic.submitted", {
            "tactic": "proc.",
            "history_lines_before": 0,
            "line_count": 1,
        })
        append_event(d, "goal.changed", {
            "tactic": "proc.",
            "goals_before": 1,
            "goals_after": 1,
            "no_more_goals": False,
            "async_check_close": False,
            "no_progress": False,
            "candidate_closed": False,
        })
        append_event(d, "tactic.result", {
            "tactic": "proc.",
            "status": "ok",
            "history_committed": True,
            "goals_before": 1,
            "goals_after": 1,
            "candidate_closed": False,
        })
        _tool_result(d, "next")
        _commit_response(
            d,
            command="chain",
            status="failed",
            attempted=["bad."],
            accepted_count=0,
            failed_tactic="bad.",
            failure_reason="cannot prove goal",
        )

        snapshot = observe_session(d)
        assert snapshot.tactic_count == 1
        assert snapshot.history_tactics == ["proc."]
        assert snapshot.latest_commit_response is not None
        assert snapshot.latest_commit_response["status"] == "failed"
        assert snapshot.latest_commit_response["mutation"]["failed_tactic"] == "bad."
        assert snapshot.errors_since_progress >= 1


def test_resume_replay_gate_rejects_goal_hash_drift() -> None:
    snapshot = WorkflowSessionSnapshot(
        session_dir="/tmp/session",
        exists=True,
        ok=True,
        history_tactics=["proc.", "wp."],
        goal_hash="observed-hash",
        latest_transition={"tactic": "wp."},
    )

    checked, reason = _resume_replay_gate(
        snapshot,
        replay_prefix=["proc.", "wp."],
        expected_goal_hash="expected-hash",
    )

    assert checked is True
    assert "goal drift" in reason


def test_resume_replay_gate_accepts_matching_prefix_and_hash() -> None:
    snapshot = WorkflowSessionSnapshot(
        session_dir="/tmp/session",
        exists=True,
        ok=True,
        history_tactics=["proc.", "wp."],
        goal_hash="expected-hash",
        latest_transition={"tactic": "wp."},
    )

    checked, reason = _resume_replay_gate(
        snapshot,
        replay_prefix=["proc.", "wp."],
        expected_goal_hash="expected-hash",
    )

    assert checked is True
    assert reason == ""


def test_resume_replay_gate_waits_for_active_mutating_tool() -> None:
    snapshot = WorkflowSessionSnapshot(
        session_dir="/tmp/session",
        exists=True,
        ok=True,
        history_tactics=["byequiv=> //."],
        goal_hash="pre-replay-goal-hash",
        active_tool="chain",
        active_tool_mutates=True,
    )

    checked, reason = _resume_replay_gate(
        snapshot,
        replay_prefix=["byequiv=> //."],
        expected_goal_hash="post-replay-goal-hash",
    )

    assert checked is False
    assert reason == ""


def test_resume_replay_gate_waits_for_replay_transition() -> None:
    snapshot = WorkflowSessionSnapshot(
        session_dir="/tmp/session",
        exists=True,
        ok=True,
        history_tactics=["byequiv=> //."],
        goal_hash="pre-replay-goal-hash",
        latest_transition={},
    )

    checked, reason = _resume_replay_gate(
        snapshot,
        replay_prefix=["byequiv=> //."],
        expected_goal_hash="post-replay-goal-hash",
    )

    assert checked is False
    assert reason == ""


def test_observer_reads_candidate_closed_projection() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        (d / "current.out").write_text(
            "[1|check]>\nNo more goals\n[2|check]>\n",
            encoding="utf-8",
        )
        (d / "history.ec").write_text("qed.\n", encoding="utf-8")
        _start_event(d)
        _tool_called(d, "next")
        append_event(d, "tactic.submitted", {
            "tactic": "qed.",
            "history_lines_before": 0,
            "line_count": 1,
        })
        append_event(d, "goal.changed", {
            "tactic": "qed.",
            "goals_before": 1,
            "goals_after": 0,
            "no_more_goals": True,
            "async_check_close": False,
            "no_progress": False,
            "candidate_closed": True,
        })
        append_event(d, "tactic.result", {
            "tactic": "qed.",
            "status": "ok",
            "history_committed": True,
            "goals_before": 1,
            "goals_after": 0,
            "candidate_closed": True,
        })
        append_event(d, "proof.candidate_closed", {
            "tactic": "qed.",
            "goals_before": 1,
            "goals_after": 0,
            "no_more_goals": True,
            "async_check_close": False,
        })
        _tool_result(d, "next")

        snapshot = observe_session(d)
        assert snapshot.ok is True
        assert snapshot.status == "candidate_closed"
        assert snapshot.candidate_ready is True
        assert snapshot.tactic_count == 1


def test_observer_flags_bad_commit_response_hash() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        _open_state(d)
        _start_event(d)
        payload = _commit_response(
            d,
            command="chain",
            status="ok",
            attempted=["proc."],
            accepted_count=1,
        )
        events_path = d / "events.jsonl"
        text = events_path.read_text(encoding="utf-8")
        events_path.write_text(
            text.replace(payload["response_hash"], "0" * 40),
            encoding="utf-8",
        )

        snapshot = observe_session(d)
        assert snapshot.ok is False
        assert any("response_hash" in err for err in snapshot.contract_errors)


def test_observer_reads_tactic_execution_result() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        _open_state(d)
        _start_event(d)
        result = {
            "schema_version": 1,
            "kind": "tactic_execution_result",
            "ok": True,
            "execution": {
                "mode": "commit",
                "command": "next",
                "attempted_count": 1,
                "accepted_count": 1,
                "rollback_count": 0,
                "state_changed": True,
                "history_committed": True,
                "probe_accepted": False,
            },
            "result": {"ok": True, "status": "ok"},
            "workspace": {
                "view": {
                    "schema_version": 1,
                    "kind": "prover_workspace_view",
                    "ok": True,
                    "current_goal": {
                        "lines": ["x = y"],
                        "text_fully_shown": True,
                    },
                },
                "workspace_chars": 100,
            },
            "inspect_handles": [{"id": "goal_info"}],
            "audit": {},
            "notes": [],
            "errors": [],
        }
        payload = write_tactic_execution_result_artifact(d, result)
        append_event(d, "tactic.execution.produced", payload)

        snapshot = observe_session(d)
        assert snapshot.tactic_execution_count == 1
        assert snapshot.latest_tactic_execution_result is not None
        assert (
            snapshot.latest_tactic_execution_result["execution"]["mode"]
            == "commit"
        )


def test_observer_tolerates_live_readonly_tool_call() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        _open_state(d)
        _start_event(d)
        _tool_called(d, "goal-info", mutates=False)

        snapshot = observe_session(d)
        assert snapshot.active_tool == "goal-info"
        assert snapshot.active_tool_mutates is False
        assert snapshot.ok is True


class _DummyProc:
    stdout = None

    def poll(self):
        return None


def test_progress_tracker_refreshes_from_observer_snapshot() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        (d / "current.out").write_text(
            "[1|check]>\nNo more goals\n[2|check]>\n",
            encoding="utf-8",
        )
        (d / "history.ec").write_text("qed.\n", encoding="utf-8")
        _start_event(d)
        _tool_called(d, "next")
        append_event(d, "tactic.submitted", {
            "tactic": "qed.",
            "history_lines_before": 0,
            "line_count": 1,
        })
        append_event(d, "goal.changed", {
            "tactic": "qed.",
            "goals_before": 1,
            "goals_after": 0,
            "no_more_goals": True,
            "async_check_close": False,
            "no_progress": False,
            "candidate_closed": True,
        })
        append_event(d, "tactic.result", {
            "tactic": "qed.",
            "status": "ok",
            "history_committed": True,
            "goals_before": 1,
            "goals_after": 0,
            "candidate_closed": True,
        })
        append_event(d, "proof.candidate_closed", {
            "tactic": "qed.",
            "goals_before": 1,
            "goals_after": 0,
            "no_more_goals": True,
            "async_check_close": False,
        })
        _tool_result(d, "next")

        tracker = _ProverTracker(_DummyProc(), "Prover-1", str(d.parent), d.name)
        tracker._refresh_structured_success()
        assert tracker.proved is True
        assert tracker.accepted_tactics == 1
        assert tracker.session_snapshot is not None
        assert tracker.session_snapshot.candidate_ready is True


def test_progress_tracker_accepts_candidate_ready_despite_view_errors() -> None:
    snapshot = WorkflowSessionSnapshot(
        session_dir="session",
        exists=True,
        ok=False,
        status="candidate_closed",
        candidate_ready=True,
        event_log_exists=True,
        history_exists=True,
        history_tactics=["qed."],
        contract_errors=["agent-view: stale recommendation action is empty"],
    )

    tracker = _ProverTracker(_DummyProc(), "Prover-1", "/tmp", "session")
    with patch("workflow.tree.trackers._session_snapshot", return_value=snapshot):
        tracker._refresh_structured_success()

    assert tracker.proved is True
    assert tracker.session_snapshot is snapshot


def test_progress_tracker_ignores_text_success_when_event_log_is_open() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        _open_state(d)
        _start_event(d)

        tracker = _ProverTracker(_DummyProc(), "Prover-1", str(d.parent), d.name)
        with redirect_stdout(StringIO()):
            tracker._process_line(json.dumps({
                "type": "user",
                "message": {
                    "content": [{
                        "type": "tool_result",
                        "content": "[ALL_GOALS_CLOSED]\nNo more goals\n",
                    }],
                },
            }))

        assert tracker.proved is False
        assert tracker.session_snapshot is not None
        assert tracker.session_snapshot.status == "open"


def test_progress_tracker_uses_snapshot_over_bash_chain_count() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        _open_state(d)
        (d / "history.ec").write_text("proc.\n", encoding="utf-8")
        _start_event(d)

        tracker = _ProverTracker(_DummyProc(), "Prover-1", str(d.parent), d.name)
        with redirect_stdout(StringIO()):
            tracker._process_line(json.dumps({
                "type": "assistant",
                "message": {
                    "content": [{
                        "type": "tool_use",
                        "name": "Bash",
                        "input": {
                            "command": (
                                "python3 core/easycrypt/session_cli.py "
                                "-d .ec_session -chain -c 'proc. M.f. bad.'"
                            ),
                        },
                    }],
                },
            }))

        assert tracker.accepted_tactics == 1
        assert tracker.session_snapshot is not None
        assert tracker.session_snapshot.tactic_count == 1


def main() -> int:
    test_observer_reads_failed_commit_response()
    test_observer_reads_candidate_closed_projection()
    test_observer_flags_bad_commit_response_hash()
    test_observer_reads_tactic_execution_result()
    test_observer_tolerates_live_readonly_tool_call()
    test_resume_replay_gate_rejects_goal_hash_drift()
    test_resume_replay_gate_accepts_matching_prefix_and_hash()
    test_resume_replay_gate_waits_for_active_mutating_tool()
    test_resume_replay_gate_waits_for_replay_transition()
    test_progress_tracker_refreshes_from_observer_snapshot()
    test_progress_tracker_ignores_text_success_when_event_log_is_open()
    test_progress_tracker_uses_snapshot_over_bash_chain_count()
    print("PASS test_session_observer")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
