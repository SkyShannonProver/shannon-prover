"""Tests for workflow-level EasyCrypt session observation."""
from __future__ import annotations

import hashlib
import json
import tempfile
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]

import sys
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from core.easycrypt.session_commit_response import write_commit_response_artifact  # noqa: E402
from core.easycrypt.session_events import append_event  # noqa: E402
from core.easycrypt.session_tactic_execution_result import (  # noqa: E402
    write_tactic_execution_result_artifact,
)
from core.easycrypt.session_workspace_artifact import (  # noqa: E402
    write_prover_workspace_view_artifact,
)
from tests.helpers.builders import (  # noqa: E402
    append_bound_workspace_event,
    bind_tactic_execution_workspace,
    start_event,
    tool_called,
    tool_result,
    write_open_goal,
)
from workflow.progress import _ProverTracker, _resume_replay_gate  # noqa: E402
from workflow.session_observer import WorkflowSessionSnapshot, observe_session  # noqa: E402
from workflow.tree.supervisor import _select_tree_run_result  # noqa: E402

_start_event = start_event
_tool_called = tool_called
_tool_result = tool_result
_open_state = write_open_goal


def _workspace_view(*, schema_version: int = 3) -> dict:
    return {
        "schema_version": schema_version,
        "kind": "prover_workspace_view",
        "ok": True,
        "last_result": {},
        "proof_status": {
            "status": "open",
            "goal_identity_required": True,
            "goal_hash": "goal-hash",
        },
        "current_goal": {"lines": ["x = y"]},
    }


def _tactic_execution_result(*, view: dict | None = None) -> dict:
    return {
        "schema_version": 1,
        "kind": "tactic_execution_result",
        "ok": True,
        "execution": {
            "mode": "commit",
            "command": "commit",
            "submitted_tactics": ["wp."],
            "attempted_count": 1,
            "accepted_count": 1,
            "rollback_count": 0,
            "state_changed": True,
            "history_committed": True,
        },
        "result": {"ok": True, "status": "ok"},
        "workspace": {
            "view": view or _workspace_view(),
            "workspace_chars": 100,
        },
        "audit": {},
        "notes": [],
        "errors": [],
    }


def _emit_workspace_view(
    d: Path,
    view: dict,
    *,
    event_schema_version: int | None = None,
) -> None:
    payload = write_prover_workspace_view_artifact(d, view)
    if event_schema_version is not None:
        payload = {**payload, "schema_version": event_schema_version}
    append_event(d, "prover.workspace_view.produced", payload)


def _emit_corrupt_workspace_view(d: Path, view: dict) -> None:
    """Bypass the fail-closed writer to exercise observer-side validation."""
    text = json.dumps(view, indent=2, sort_keys=True)
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()
    artifact_dir = d / "prover_workspace_views"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact = artifact_dir / f"corrupt_{digest[:16]}.json"
    artifact.write_text(text + "\n", encoding="utf-8")
    current_goal = view.get("current_goal", {})
    proof_status = view.get("proof_status", {})
    append_event(d, "prover.workspace_view.produced", {
        "schema_version": view.get("schema_version", 0),
        "view_kind": view.get("kind", ""),
        "ok": bool(view.get("ok")),
        "artifact": str(artifact),
        "view_hash": digest,
        "proof_status": proof_status.get("status", ""),
        "current_goal_text_fully_shown": bool(
            current_goal.get("text_fully_shown", False)
        ),
        "current_goal_truncated": bool(current_goal.get("truncated", False)),
        "goal_chars": int(current_goal.get("char_count", 0)),
        "workspace_chars": len(json.dumps(view, sort_keys=True)),
    })


def _commit_response(
    d: Path,
    *,
    command: str = "commit_chain",
    status: str = "ok",
    attempted: list[str] | None = None,
    accepted_count: int = 0,
    failed_tactic: str = "",
    failure_reason: str = "",
) -> dict:
    attempted = attempted or []
    response = {
        "schema_version": 2,
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
            command="commit_chain",
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
        expected_goal_identity_required=True,
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
        expected_goal_identity_required=True,
    )

    assert checked is True
    assert reason == ""


def test_resume_replay_gate_rejects_open_state_without_expected_hash() -> None:
    snapshot = WorkflowSessionSnapshot(
        session_dir="/tmp/session",
        exists=True,
        ok=True,
        status="open",
        history_tactics=["proc.", "wp."],
        goal_hash="observed-but-unbound-hash",
        latest_transition={"tactic": "wp."},
    )

    checked, reason = _resume_replay_gate(
        snapshot,
        replay_prefix=["proc.", "wp."],
        expected_goal_hash="",
        expected_goal_identity_required=True,
    )

    assert checked is True
    assert "identity missing" in reason


def test_resume_replay_gate_allows_closed_state_without_expected_hash() -> None:
    snapshot = WorkflowSessionSnapshot(
        session_dir="/tmp/session",
        exists=True,
        ok=True,
        status="session_closed_pending_verification",
        goals_discharged=True,
        qed_committed=True,
        history_tactics=["proc.", "qed."],
        latest_transition={"tactic": "qed."},
    )

    checked, reason = _resume_replay_gate(
        snapshot,
        replay_prefix=["proc.", "qed."],
        expected_goal_hash="",
        expected_goal_identity_required=False,
    )

    assert checked is True
    assert reason == ""


def test_resume_replay_gate_checks_explicit_closed_identity_contract() -> None:
    snapshot = WorkflowSessionSnapshot(
        session_dir="/tmp/session",
        exists=True,
        ok=True,
        status="session_closed_pending_verification",
        goals_discharged=True,
        qed_committed=True,
        history_tactics=["proc.", "qed."],
        latest_transition={"tactic": "qed."},
    )

    checked, reason = _resume_replay_gate(
        snapshot,
        replay_prefix=["proc.", "qed."],
        expected_goal_hash="",
        expected_goal_identity_required=False,
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
        active_tool="commit_chain",
        active_tool_mutates=True,
    )

    checked, reason = _resume_replay_gate(
        snapshot,
        replay_prefix=["byequiv=> //."],
        expected_goal_hash="post-replay-goal-hash",
        expected_goal_identity_required=True,
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
        expected_goal_identity_required=True,
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
        assert snapshot.status == "session_closed_pending_verification"
        assert snapshot.qed_committed is True
        assert snapshot.goals_discharged is True
        assert snapshot.tactic_count == 1


def test_observer_flags_bad_commit_response_hash() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        _open_state(d)
        _start_event(d)
        payload = _commit_response(
            d,
            command="commit_chain",
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


@pytest.mark.parametrize(
    ("artifact_kind", "event_type", "artifact_subdir", "snapshot_field"),
    [
        (
            "commit",
            "commit.response.produced",
            "commit_responses",
            "latest_commit_response",
        ),
        (
            "workspace",
            "prover.workspace_view.produced",
            "prover_workspace_views",
            "latest_workspace_view",
        ),
        (
            "execution",
            "tactic.execution.produced",
            "tactic_execution_results",
            "latest_tactic_execution_result",
        ),
    ],
)
def test_observer_never_reads_authoritative_artifact_outside_session_subdir(
    tmp_path: Path,
    artifact_kind: str,
    event_type: str,
    artifact_subdir: str,
    snapshot_field: str,
) -> None:
    d = tmp_path / f"session-{artifact_kind}"
    d.mkdir()
    _open_state(d)
    _start_event(d)
    if artifact_kind == "commit":
        payload = _commit_response(d)
    elif artifact_kind == "workspace":
        payload = write_prover_workspace_view_artifact(d, _workspace_view())
        append_event(d, event_type, payload)
    else:
        result = _tactic_execution_result()
        bind_tactic_execution_workspace(d, result)
        append_bound_workspace_event(d, result)
        payload = write_tactic_execution_result_artifact(d, result)
        append_event(d, event_type, payload)

    original = Path(payload["artifact"])
    external_dir = tmp_path / "outside-session"
    external_dir.mkdir(exist_ok=True)
    external = external_dir / f"{artifact_kind}-{original.name}"
    external.write_bytes(original.read_bytes())
    events_path = d / "events.jsonl"
    events = [json.loads(line) for line in events_path.read_text().splitlines()]
    produced = [event for event in events if event.get("type") == event_type]
    assert len(produced) == 1
    produced[0]["payload"]["artifact"] = str(external)
    events_path.write_text(
        "\n".join(json.dumps(event) for event in events) + "\n",
        encoding="utf-8",
    )

    snapshot = observe_session(d)

    assert snapshot.ok is False
    assert getattr(snapshot, snapshot_field) is None
    assert any(
        f"outside the current session's {artifact_subdir} directory" in error
        for error in snapshot.contract_errors
    )


def test_observer_rejects_authoritative_event_from_another_session(
    tmp_path: Path,
) -> None:
    d = tmp_path / "session"
    d.mkdir()
    _open_state(d)
    _start_event(d)
    _commit_response(d)
    events_path = d / "events.jsonl"
    events = [json.loads(line) for line in events_path.read_text().splitlines()]
    commit_event = next(
        event for event in events
        if event.get("type") == "commit.response.produced"
    )
    other = str((tmp_path / "other-session").resolve())
    commit_event["session_dir"] = other
    commit_event["session_id"] = other
    events_path.write_text(
        "\n".join(json.dumps(event) for event in events) + "\n",
        encoding="utf-8",
    )

    snapshot = observe_session(d)

    assert snapshot.latest_commit_response is None
    assert any(
        "event session_dir does not match the current session" in error
        for error in snapshot.contract_errors
    )


def test_observer_rejects_stale_commit_response_event_schema() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        _open_state(d)
        _start_event(d)
        _commit_response(d)
        events_path = d / "events.jsonl"
        events = [json.loads(line) for line in events_path.read_text().splitlines()]
        commit_event = next(
            event for event in events if event.get("type") == "commit.response.produced"
        )
        commit_event["payload"]["schema_version"] = 1
        events_path.write_text(
            "\n".join(json.dumps(event) for event in events) + "\n",
            encoding="utf-8",
        )

        snapshot = observe_session(d)

        assert snapshot.ok is False
        assert any(
            "event schema_version 1 is unsupported; expected 2" in error
            for error in snapshot.contract_errors
        )


def test_observer_rejects_forged_commit_response_event_fields() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        _open_state(d)
        _start_event(d)
        _commit_response(
            d,
            attempted=["proc."],
            accepted_count=1,
        )
        events_path = d / "events.jsonl"
        events = [json.loads(line) for line in events_path.read_text().splitlines()]
        commit_event = next(
            event for event in events if event.get("type") == "commit.response.produced"
        )
        commit_event["payload"]["accepted_count"] = 0
        events_path.write_text(
            "\n".join(json.dumps(event) for event in events) + "\n",
            encoding="utf-8",
        )

        snapshot = observe_session(d)

        assert snapshot.ok is False
        assert any(
            "accepted_count" in error and "mismatch" in error
            for error in snapshot.contract_errors
        )


def test_observer_reads_tactic_execution_result() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        _open_state(d)
        _start_event(d)
        view = _workspace_view()
        view["current_goal"]["text_fully_shown"] = True
        result = _tactic_execution_result(view=view)
        bind_tactic_execution_workspace(d, result)
        append_bound_workspace_event(d, result)
        payload = write_tactic_execution_result_artifact(d, result)
        append_event(d, "tactic.execution.produced", payload)

        snapshot = observe_session(d)
        assert snapshot.tactic_execution_count == 1
        assert snapshot.latest_tactic_execution_result is not None
        assert (
            snapshot.latest_tactic_execution_result["execution"]["mode"]
            == "commit"
        )

        stale_payload = dict(payload)
        stale_payload["schema_version"] = 2
        append_event(d, "tactic.execution.produced", stale_payload)

        stale_snapshot = observe_session(d)
        assert stale_snapshot.ok is False
        assert any(
            "event schema_version 2 is unsupported; expected 1" in error
            for error in stale_snapshot.contract_errors
        )
        assert any(
            "tactic-execution-result: schema_version mismatch" in error
            for error in stale_snapshot.contract_errors
        )


def test_observer_rejects_tactic_execution_linked_workspace_tamper() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        _open_state(d)
        _start_event(d)
        result = _tactic_execution_result()
        bind_tactic_execution_workspace(d, result)
        append_bound_workspace_event(d, result)
        payload = write_tactic_execution_result_artifact(d, result)
        append_event(d, "tactic.execution.produced", payload)
        Path(result["workspace"]["artifact"]).write_text(
            json.dumps({**_workspace_view(), "ok": False}, indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )

        snapshot = observe_session(d)

        assert snapshot.ok is False
        assert any(
            "tactic-execution-result.workspace: "
            "workspace.view_hash does not match linked artifact"
            in error
            for error in snapshot.contract_errors
        )


def test_observer_rejects_tactic_execution_without_workspace_event() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        _open_state(d)
        _start_event(d)
        result = _tactic_execution_result()
        bind_tactic_execution_workspace(d, result)
        payload = write_tactic_execution_result_artifact(d, result)
        append_event(d, "tactic.execution.produced", payload)

        snapshot = observe_session(d)

        assert snapshot.ok is False
        assert any(
            "no matching prior prover.workspace_view.produced event" in error
            for error in snapshot.contract_errors
        )


def test_observer_rejects_v1_workspace_view() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        _open_state(d)
        _start_event(d)
        _emit_corrupt_workspace_view(d, _workspace_view(schema_version=2))

        snapshot = observe_session(d)

        assert snapshot.ok is False
        assert snapshot.latest_workspace_view is not None
        assert any(
            "unsupported ProverWorkspaceView schema_version 2" in error
            for error in snapshot.contract_errors
        )


def test_observer_rejects_stale_workspace_event_schema_version() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        _open_state(d)
        _start_event(d)
        _emit_workspace_view(
            d,
            _workspace_view(),
            event_schema_version=2,
        )

        snapshot = observe_session(d)

        assert snapshot.ok is False
        assert snapshot.latest_workspace_view is not None
        assert any(
            "event schema_version 2 is unsupported; expected 3" in error
            for error in snapshot.contract_errors
        )
        assert any(
            "prover-workspace-view: schema_version mismatch" in error
            for error in snapshot.contract_errors
        )


def test_observer_rejects_forged_workspace_event_mirror() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        _open_state(d)
        _start_event(d)
        _emit_workspace_view(d, _workspace_view())
        events_path = d / "events.jsonl"
        events = [json.loads(line) for line in events_path.read_text().splitlines()]
        events[-1]["payload"]["workspace_chars"] += 1
        events_path.write_text(
            "\n".join(json.dumps(event) for event in events) + "\n",
            encoding="utf-8",
        )

        snapshot = observe_session(d)

        assert snapshot.ok is False
        assert any(
            "event payload `workspace_chars` mismatch" in error
            for error in snapshot.contract_errors
        )


def test_observer_rejects_workspace_missing_required_field() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        _open_state(d)
        _start_event(d)
        view = _workspace_view()
        view.pop("last_result")
        _emit_corrupt_workspace_view(d, view)

        snapshot = observe_session(d)

        assert snapshot.ok is False
        assert any(
            "required field `last_result` must be an object" in error
            for error in snapshot.contract_errors
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
        tracker._refresh_completion_candidate()
        assert tracker.completion_candidate_ready is True
        assert tracker.accepted_tactics == 1
        assert tracker.session_snapshot is not None
        assert tracker.session_snapshot.goals_discharged is True


def test_progress_tracker_rejects_candidate_when_snapshot_contract_has_errors() -> None:
    snapshot = WorkflowSessionSnapshot(
        session_dir="session",
        exists=True,
        ok=False,
        status="session_closed_pending_verification",
        goals_discharged=True,
        qed_committed=True,
        event_log_exists=True,
        history_exists=True,
        history_tactics=["qed."],
        contract_errors=[
            "proof-context-view: stale recommendation action is empty"
        ],
    )

    tracker = _ProverTracker(_DummyProc(), "Prover-1", "/tmp", "session")
    with patch("workflow.tree.trackers._session_snapshot", return_value=snapshot):
        tracker._refresh_completion_candidate()

    assert tracker.completion_candidate_ready is False
    assert tracker.session_snapshot is snapshot


def test_progress_tracker_never_promotes_raw_or_history_text_to_success() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        _open_state(d)
        (d / "history.ec").write_text("proc.\nqed.\n", encoding="utf-8")

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

        assert tracker.completion_candidate_ready is False
        assert tracker.session_snapshot is not None
        assert tracker.session_snapshot.goals_discharged is False
        assert tracker.session_snapshot.offline_verified is False


def test_progress_tracker_ignores_bash_tactic_argv() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        _open_state(d)
        (d / "history.ec").write_text("proc.\n", encoding="utf-8")
        _start_event(d)

        tracker = _ProverTracker(_DummyProc(), "Prover-1", str(d.parent), d.name)
        commands = (
            "python3 core/easycrypt/session_cli.py "
            "-d .ec_session -chain -c 'proc. M.f. bad.'",
            "python3 core/easycrypt/session_cli.py "
            "-d .ec_session -tactic-exec commit_chain "
            "-c 'proc. M.f. bad.'",
        )
        with redirect_stdout(StringIO()):
            for command in commands:
                tracker._process_line(json.dumps({
                    "type": "assistant",
                    "message": {
                        "content": [{
                            "type": "tool_use",
                            "name": "Bash",
                            "input": {"command": command},
                        }],
                    },
                }))

        assert tracker.accepted_tactics == 1
        assert tracker.session_snapshot is not None
        assert tracker.session_snapshot.tactic_count == 1


def test_supervisor_winner_selection_requires_structured_success() -> None:
    raw_qed = SimpleNamespace(
        node_id="raw-qed",
        tracker=SimpleNamespace(
            committed_count=10,
            completion_candidate_ready=False,
            session_snapshot=WorkflowSessionSnapshot(
                session_dir="raw-qed",
                exists=True,
                ok=True,
                status="open",
                history_exists=True,
                history_tactics=["proc.", "qed."],
            ),
        ),
    )
    structured = SimpleNamespace(
        node_id="structured",
        tracker=SimpleNamespace(
            committed_count=2,
            completion_candidate_ready=False,
            session_snapshot=WorkflowSessionSnapshot(
                session_dir="structured",
                exists=True,
                ok=True,
                status="session_closed_pending_verification",
                goals_discharged=True,
                qed_committed=True,
            ),
        ),
    )

    winner, succeeded = _select_tree_run_result([raw_qed])
    assert winner is raw_qed
    assert succeeded is False
    assert raw_qed.tracker.completion_candidate_ready is False

    winner, succeeded = _select_tree_run_result([raw_qed, structured])
    assert winner is structured
    assert succeeded is True


def main() -> int:
    test_observer_reads_failed_commit_response()
    test_observer_reads_candidate_closed_projection()
    test_observer_flags_bad_commit_response_hash()
    test_observer_reads_tactic_execution_result()
    test_observer_rejects_v1_workspace_view()
    test_observer_rejects_stale_workspace_event_schema_version()
    test_observer_rejects_workspace_missing_required_field()
    test_observer_tolerates_live_readonly_tool_call()
    test_resume_replay_gate_rejects_goal_hash_drift()
    test_resume_replay_gate_accepts_matching_prefix_and_hash()
    test_resume_replay_gate_waits_for_active_mutating_tool()
    test_resume_replay_gate_waits_for_replay_transition()
    test_progress_tracker_refreshes_from_observer_snapshot()
    test_progress_tracker_never_promotes_raw_or_history_text_to_success()
    test_progress_tracker_ignores_bash_tactic_argv()
    test_supervisor_winner_selection_requires_structured_success()
    print("PASS test_session_observer")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
