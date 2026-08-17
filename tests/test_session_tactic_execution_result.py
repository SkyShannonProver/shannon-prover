"""Tests for the live TacticExecutionResult contract."""
from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

import sys
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from core.easycrypt.session_tactic_execution_result import (  # type: ignore  # noqa: E402
    TACTIC_EXECUTION_RESULT_KIND,
    build_tactic_execution_result as _build_tactic_execution_result,
    format_tactic_execution_result,
    record_tactic_execution_result,
    validate_tactic_execution_result,
    write_tactic_execution_result_artifact,
    write_tactic_raw_result_artifact,
)
from core.easycrypt.session_events import (  # type: ignore  # noqa: E402
    append_event,
    read_events,
)
from core.easycrypt.session_runtime import (  # type: ignore  # noqa: E402
    Session,
    UndoStepResult,
)
from core.easycrypt.session_workspace_artifact import (  # type: ignore  # noqa: E402
    write_prover_workspace_view_artifact,
)
from core.easycrypt.commands.commit_commands import (  # type: ignore  # noqa: E402
    _finalize_tactic_execution,
)
from core.easycrypt.commands import commit_commands  # type: ignore  # noqa: E402
from tests.helpers.builders import (  # noqa: E402
    append_bound_workspace_event,
    bind_tactic_execution_workspace,
)


def _commit_response(
    *,
    command: str = "commit",
    status: str = "ok",
    ok: bool = True,
    attempted: list[str] | None = None,
    accepted_count: int = 1,
    failed_tactic: str = "",
    failure_reason: str = "",
    rollback_count: int = 0,
) -> dict:
    tactics = attempted if attempted is not None else ["wp."]
    return {
        "schema_version": 2,
        "kind": "commit_response",
        "ok": ok,
        "command": command,
        "status": status,
        "proof_state": {
            "status": "open",
            "goal": {
                "goal_type": "pRHL",
                "active_goal_hash": "goal-hash",
                "num_remaining": 1,
            },
        },
        "latest_transition": {
            "history_committed": ok and command not in {"try", "try-chain"},
        },
        "mutation": {
            "attempted_count": len(tactics),
            "accepted_count": accepted_count,
            "attempted_tactics": tactics,
            "failed_tactic": failed_tactic,
            "failure_reason": failure_reason,
            "keep_on_fail": False,
            "rollback_count": rollback_count,
        },
        "notes": [],
        "errors": [] if ok else [{
            "code": "commit.failed",
            "message": failure_reason,
            "failed_tactic": failed_tactic,
        }],
        "debug": {},
    }


def _workspace_view() -> dict:
    return {
        "schema_version": 3,
        "kind": "prover_workspace_view",
        "ok": True,
        "last_result": {},
        "current_goal": {
            "lines": ["Current goal", "----", "x{1} = x{2}"],
            "text_fully_shown": True,
            "truncated": False,
        },
        "proof_status": {
            "status": "open",
            "goal_identity_required": True,
            "goal_hash": "goal-hash",
        },
    }


def _workspace_payload(
    workspace: dict,
    *,
    artifact: str = "/tmp/prover_workspace_view.json",
) -> dict:
    canonical = json.dumps(workspace, indent=2, sort_keys=True)
    goal = workspace.get("current_goal", {})
    return {
        "artifact": artifact,
        "view_hash": hashlib.sha1(canonical.encode("utf-8")).hexdigest(),
        "current_goal_text_fully_shown": bool(goal.get("text_fully_shown")),
        "current_goal_truncated": bool(goal.get("truncated")),
        "goal_chars": int(goal.get("char_count") or 0),
        "workspace_chars": len(json.dumps(workspace, sort_keys=True)),
    }


def build_tactic_execution_result(*args, **kwargs):
    workspace = kwargs.get("workspace_view")
    if isinstance(workspace, dict) and "workspace_payload" not in kwargs:
        kwargs["workspace_payload"] = _workspace_payload(workspace)
    return _build_tactic_execution_result(*args, **kwargs)


def test_session_step_up_reports_empty_and_changed_outcomes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    empty_session = Session(tmp_path / "empty")
    empty = empty_session.step_up()

    assert empty == UndoStepResult(
        output="No steps to undo.\n",
        status="empty",
        undone_tactic="",
        remaining_steps=0,
    )
    assert empty.state_changed is False
    assert read_events(empty_session.dir)[-1]["payload"]["status"] == "empty"

    changed_session = Session(tmp_path / "changed")
    changed_session.history.write_text("wp.\n", encoding="utf-8")
    changed_session.steps.write_text("1\n", encoding="utf-8")

    def fake_run_ec(_history: Path, output: Path) -> None:
        output.write_text(
            "[1|check]>\nCurrent goal\n----\nx = x\n[2|check]>\n",
            encoding="utf-8",
        )

    monkeypatch.setattr(changed_session, "_run_ec", fake_run_ec)
    changed = changed_session.step_up()

    assert changed.status == "ok"
    assert changed.undone_tactic == "wp."
    assert changed.remaining_steps == 0
    assert changed.state_changed is True
    assert changed_session.history.read_text() == ""
    assert read_events(changed_session.dir)[-1]["payload"]["status"] == "ok"


@pytest.mark.parametrize(
    ("undo_status", "expected_status", "expected_ok"),
    (("ok", "undone", True), ("empty", "no_progress", False)),
)
def test_handle_undo_preserves_the_explicit_undo_outcome(
    monkeypatch: pytest.MonkeyPatch,
    undo_status: str,
    expected_status: str,
    expected_ok: bool,
) -> None:
    captured: dict = {}

    class FakeSession:
        def step_up(self) -> UndoStepResult:
            return UndoStepResult(
                output=(
                    "Command (undone):\nwp.\n"
                    if undo_status == "ok" else "No steps to undo.\n"
                ),
                status=undo_status,
                undone_tactic="wp." if undo_status == "ok" else "",
                remaining_steps=0,
            )

    monkeypatch.setattr(
        commit_commands,
        "_finalize_tactic_execution",
        lambda _session, **kwargs: captured.update(kwargs),
    )

    assert commit_commands.handle_undo(FakeSession(), object()) == 0
    assert captured["status"] == expected_status
    assert captured["ok"] is expected_ok
    assert captured["failure_reason"] == (
        "" if expected_ok else "No steps to undo."
    )


def test_tactic_execution_result_commit_contract_and_artifact() -> None:
    with tempfile.TemporaryDirectory() as td:
        workspace = _workspace_view()
        result = build_tactic_execution_result(
            mode="commit",
            command="commit",
            commit_response=_commit_response(),
            commit_response_payload={"artifact": str(Path(td) / "commit.json")},
            workspace_view=workspace,
            workspace_payload=_workspace_payload(
                workspace,
                artifact=str(Path(td) / "workspace.json"),
            ),
            raw_result="OK\nCurrent goal",
        )
        bind_tactic_execution_workspace(Path(td), result)
        payload = write_tactic_execution_result_artifact(Path(td), result)
        artifact = Path(payload["artifact"])

        assert result["kind"] == TACTIC_EXECUTION_RESULT_KIND
        assert result["execution"]["mode"] == "commit"
        assert result["execution"]["state_changed"] is True
        assert result["workspace"]["view"]["current_goal"]["lines"][0] == "Current goal"
        assert "prover_workspace_view_" in result["workspace"]["artifact"]
        assert "inspect_handles" not in result
        assert "prover_workspace_view_" in payload["workspace_artifact"]
        assert artifact.exists()
        assert validate_tactic_execution_result(json.loads(artifact.read_text())).ok


def test_tactic_execution_result_rejects_superseded_v2_embedded_workspace() -> None:
    with tempfile.TemporaryDirectory() as td:
        workspace = _workspace_view()
        workspace["schema_version"] = 2
        result = build_tactic_execution_result(
            mode="commit",
            command="commit",
            commit_response=_commit_response(),
            workspace_view=workspace,
        )

    validation = validate_tactic_execution_result(result)
    assert validation.ok is False
    assert any(
        "unsupported ProverWorkspaceView schema_version 2; expected 3"
        in error
        for error in validation.errors
    )


def test_tactic_execution_result_rejects_retired_command_summary_artifact() -> None:
    result = build_tactic_execution_result(
        mode="commit",
        command="commit",
        commit_response=_commit_response(),
        workspace_view=_workspace_view(),
    )
    result["audit"]["command_summary_artifact"] = "/tmp/retired.json"

    validation = validate_tactic_execution_result(result)

    assert validation.ok is False
    assert any(
        "audit.command_summary_artifact is retired" in error
        for error in validation.errors
    )


def test_tactic_execution_result_rejects_workspace_hash_mismatch() -> None:
    result = build_tactic_execution_result(
        mode="commit",
        command="commit",
        commit_response=_commit_response(),
        workspace_view=_workspace_view(),
    )
    result["workspace"]["view_hash"] = "0" * 40

    validation = validate_tactic_execution_result(result)

    assert validation.ok is False
    assert (
        "workspace.view_hash does not match embedded workspace.view"
        in validation.errors
    )


def test_tactic_execution_result_rejects_workspace_audit_link_mismatch() -> None:
    result = build_tactic_execution_result(
        mode="commit",
        command="commit",
        commit_response=_commit_response(),
        workspace_view=_workspace_view(),
    )
    result["audit"]["prover_workspace_artifact"] = "/tmp/other-view.json"

    validation = validate_tactic_execution_result(result)

    assert validation.ok is False
    assert (
        "audit.prover_workspace_artifact must equal workspace.artifact"
        in validation.errors
    )


@pytest.mark.parametrize(
    ("mutate", "expected_error"),
    [
        (
            lambda result: result.update({"ok": False}),
            "root ok must equal result.ok",
        ),
        (
            lambda result: result["result"].update({"status": "error"}),
            "result.ok does not match result.status",
        ),
        (
            lambda result: result["execution"].update({"attempted_count": 2}),
            "attempted_count must equal len(submitted_tactics)",
        ),
        (
            lambda result: result["execution"].update({
                "history_committed": True,
                "state_changed": False,
            }),
            "history_committed requires state_changed=true",
        ),
        (
            lambda result: result["execution"].update({
                "history_committed": False,
            }),
            "accepted tactics require committed proof-state change",
        ),
    ],
)
def test_tactic_execution_result_rejects_cross_field_contradictions(
    mutate,
    expected_error: str,
) -> None:
    result = build_tactic_execution_result(
        mode="commit",
        command="commit",
        commit_response=_commit_response(),
        workspace_view=_workspace_view(),
    )
    mutate(result)

    validation = validate_tactic_execution_result(result)

    assert validation.ok is False
    assert any(expected_error in error for error in validation.errors)


def test_tactic_execution_result_rejects_bool_as_schema_or_count() -> None:
    result = build_tactic_execution_result(
        mode="commit",
        command="commit",
        commit_response=_commit_response(),
        workspace_view=_workspace_view(),
    )
    result["schema_version"] = True
    result["execution"]["attempted_count"] = True

    validation = validate_tactic_execution_result(result)

    assert validation.ok is False
    assert "schema_version must be 1, got True" in validation.errors
    assert "execution.attempted_count must be a non-negative int" in validation.errors


def test_tactic_execution_result_rejects_retired_probe_contract() -> None:
    result = build_tactic_execution_result(
        mode="preflight",
        command="try",
        commit_response=_commit_response(
            command="try",
            status="preflight_accepted",
            accepted_count=0,
        ),
        workspace_view=_workspace_view(),
    )
    result["execution"]["probe_accepted"] = True
    result["result"]["status"] = "probe_accepted"

    validation = validate_tactic_execution_result(result)

    assert validation.ok is False
    assert any(
        "preflight fields do not belong" in error
        for error in validation.errors
    )
    assert "result.status is invalid: 'probe_accepted'" in validation.errors


def test_tactic_execution_writer_rejects_missing_linked_workspace() -> None:
    result = build_tactic_execution_result(
        mode="commit",
        command="commit",
        commit_response=_commit_response(),
        workspace_view=_workspace_view(),
    )

    with pytest.raises(ValueError, match="workspace artifact is missing"):
        write_tactic_execution_result_artifact(Path("."), result)


@pytest.mark.parametrize("retired_mode", ["next", "try", "try-chain", "chain", "prev"])
def test_tactic_execution_result_rejects_retired_mode_aliases(
    retired_mode: str,
) -> None:
    result = build_tactic_execution_result(
        mode="commit",
        command="commit",
        commit_response=_commit_response(),
        workspace_view=_workspace_view(),
    )
    result["execution"]["mode"] = retired_mode

    validation = validate_tactic_execution_result(result)

    assert validation.ok is False
    assert f"execution.mode is invalid: {retired_mode!r}" in validation.errors


def test_tactic_execution_result_rejects_retired_inspect_handles() -> None:
    workspace = _workspace_view()
    workspace["current_goal"]["text_fully_shown"] = False
    workspace["current_goal"]["truncated"] = True
    result = build_tactic_execution_result(
        mode="commit",
        command="commit",
        commit_response=_commit_response(),
        workspace_view=workspace,
    )

    assert "inspect_handles" not in result
    result["inspect_handles"] = [{"id": "goal_info"}]
    validation = validate_tactic_execution_result(result)

    assert validation.ok is False
    assert (
        "inspect_handles is not part of TacticExecutionResult"
        in validation.errors
    )


def test_tactic_execution_result_chain_steps_and_undo() -> None:
    chain = build_tactic_execution_result(
        mode="commit_chain",
        command="commit_chain",
        commit_response=_commit_response(
            command="commit_chain",
            attempted=["proc.", "bad."],
            accepted_count=1,
            ok=False,
            status="partial_success",
            failed_tactic="bad.",
            failure_reason="bad tactic",
        ),
        workspace_view=_workspace_view(),
        chain_steps=[
            {"index": 1, "tactic": "proc.", "status": "accepted"},
            {"index": 2, "tactic": "bad.", "status": "failed"},
        ],
    )
    undo = build_tactic_execution_result(
        mode="undo",
        command="undo",
        commit_response=_commit_response(
            command="undo",
            status="undone",
            attempted=[],
            accepted_count=0,
        ),
        workspace_view=_workspace_view(),
    )

    assert chain["execution"]["mode"] == "commit_chain"
    assert chain["execution"]["steps"][1]["status"] == "failed"
    assert chain["execution"]["history_committed"] is True
    assert chain["execution"]["state_changed"] is True
    assert validate_tactic_execution_result(chain).ok
    assert undo["execution"]["mode"] == "undo"
    assert undo["execution"]["state_changed"] is True


def test_tactic_execution_result_record_and_format() -> None:
    class Session:
        def __init__(self, path: Path) -> None:
            self.dir = path
            self.events: list[tuple[str, dict, str]] = []

        def emit_event(self, event_type: str, payload: dict, *, source: str = "") -> bool:
            self.events.append((event_type, payload, source))
            return append_event(self.dir, event_type, payload, source=source)

    with tempfile.TemporaryDirectory() as td:
        session = Session(Path(td))
        raw_payload = write_tactic_raw_result_artifact(
            session.dir,
            command="commit",
            raw_result="raw easycrypt result",
        )
        result = build_tactic_execution_result(
            mode="commit",
            command="commit",
            commit_response=_commit_response(),
            workspace_view=_workspace_view(),
            raw_result="raw easycrypt result",
            raw_result_payload=raw_payload,
        )
        bind_tactic_execution_workspace(session.dir, result)
        append_bound_workspace_event(session.dir, result)
        payload = record_tactic_execution_result(session, result)
        text = format_tactic_execution_result(result)

        assert Path(raw_payload["artifact"]).exists()
        assert Path(payload["artifact"]).exists()
        assert session.events[0][0] == "tactic.execution.produced"
        assert "[TACTIC-EXECUTION-RESULT]" in text
        assert "compact-head-safe" not in text
        assert "compact-tail-safe" not in text
        stdout_payload = json.loads(text.split("\n", 1)[1])
        assert "kind" not in stdout_payload
        assert "schema_version" not in stdout_payload
        assert "ok" not in stdout_payload
        assert "kind" not in stdout_payload["workspace"]["view"]
        assert "schema_version" not in stdout_payload["workspace"]["view"]
        assert "ok" not in stdout_payload["workspace"]["view"]
        assert '"workspace":' in text
        assert '"audit":' not in text
        assert "raw_result_artifact" not in text
        assert "inspect_handles" not in result
        assert "inspect_handles" not in stdout_payload


def test_tactic_execution_writer_requires_prior_workspace_event() -> None:
    class Session:
        def __init__(self, path: Path) -> None:
            self.dir = path

        def emit_event(self, event_type: str, payload: dict, *, source: str = "") -> bool:
            return append_event(self.dir, event_type, payload, source=source)

    with tempfile.TemporaryDirectory() as td:
        session = Session(Path(td))
        workspace = _workspace_view()
        workspace_payload = write_prover_workspace_view_artifact(
            session.dir,
            workspace,
        )
        result = build_tactic_execution_result(
            mode="commit",
            command="commit",
            commit_response=_commit_response(),
            workspace_view=workspace,
            workspace_payload=workspace_payload,
        )

        with pytest.raises(
            ValueError,
            match="workspace artifact/hash has no matching prior",
        ):
            record_tactic_execution_result(session, result)

        assert not (session.dir / "tactic_execution_results").exists()

def test_tactic_execution_result_stdout_is_workspace_first_under_cap() -> None:
    workspace = _workspace_view()
    workspace["current_goal"]["lines"] = [
        "Current goal (remaining: 4)",
        *[f"  statement {idx} : x{idx}{{1}} = x{idx}{{2}}" for idx in range(90)],
    ]
    workspace["current_goal"]["char_count"] = len(
        "\n".join(workspace["current_goal"]["lines"])
    )
    result = build_tactic_execution_result(
        mode="commit_chain",
        command="commit_chain",
        commit_response=_commit_response(
            command="commit_chain",
            attempted=["move=> />.", "bad."],
            accepted_count=1,
            ok=False,
            status="partial_success",
            failed_tactic="bad.",
            failure_reason="cannot prove goal",
        ),
        workspace_view=workspace,
        workspace_payload={
            "artifact": ".ec_session/prover_workspace_views/w.json",
            "workspace_chars": 9000,
            "goal_chars": workspace["current_goal"]["char_count"],
            "current_goal_text_fully_shown": True,
            "current_goal_truncated": False,
        },
    )
    text = format_tactic_execution_result(result)
    first_transport_window = text[:10039]

    assert first_transport_window.startswith("[TACTIC-EXECUTION-RESULT]\n")
    assert '"status":"partial_success"' in first_transport_window
    assert '"workspace":' in first_transport_window
    assert "statement 89" in first_transport_window
    assert '"audit":' not in first_transport_window


def test_commit_response_finalizer_emits_tactic_execution_result() -> None:
    class Session:
        def __init__(self, path: Path) -> None:
            self.dir = path
            self.events: list[tuple[str, dict, str]] = []

        def emit_event(self, event_type: str, payload: dict, *, source: str = "") -> bool:
            self.events.append((event_type, payload, source))
            return append_event(self.dir, event_type, payload, source=source)

    with tempfile.TemporaryDirectory() as td:
        session = Session(Path(td))
        append_event(session.dir, "session.started", {
            "file": None,
            "lemma": "L",
            "include_dirs": [],
            "discarded_tactic_count": 0,
            "restart_count": 1,
        })
        append_event(session.dir, "tool.called", {
            "name": "commit",
            "mutates_proof_state": True,
            "session_dir": str(session.dir.resolve()),
        })
        (session.dir / "current.out").write_text(
            "[1|check]>\nCurrent goal\n----\nx = y\n[2|check]>\n",
            encoding="utf-8",
        )
        payload = _finalize_tactic_execution(
            session,
            command="commit",
            execution_mode="commit",
            status="ok",
            attempted_tactics=["wp."],
            accepted_count=1,
            raw_output="OK",
            ok=True,
            emit_execution_stdout=False,
        )

        assert payload is not None
        event_types = [event_type for event_type, _, _ in session.events]
        assert event_types == [
            "commit.response.produced",
            "prover.workspace_view.produced",
            "tactic.execution.produced",
        ]
        execution_event = [
            payload for event_type, payload, _ in session.events
            if event_type == "tactic.execution.produced"
        ][0]
        result = json.loads(Path(execution_event["artifact"]).read_text())
        assert result["execution"]["mode"] == "commit"
        assert result["workspace"]["view"]["kind"] == "prover_workspace_view"
        assert "command_summary_artifact" not in result["audit"]



def test_record_tactic_execution_result_rejects_invalid_workspace() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        result = build_tactic_execution_result(
            mode="commit",
            command="commit",
            commit_response=_commit_response(),
            workspace_view={},
        )

        with pytest.raises(ValueError, match="TacticExecutionResult contract"):
            record_tactic_execution_result(d, result)

        assert not (d / "tactic_execution_results").exists()


def test_finalizer_does_not_emit_invalid_ter_after_workspace_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Session:
        def __init__(self, path: Path) -> None:
            self.dir = path
            self.events: list[tuple[str, dict, str]] = []

        def emit_event(self, event_type: str, payload: dict, *, source: str = "") -> bool:
            self.events.append((event_type, payload, source))
            return append_event(self.dir, event_type, payload, source=source)

    with tempfile.TemporaryDirectory() as td:
        session = Session(Path(td))
        (session.dir / "current.out").write_text(
            "[1|check]>\nCurrent goal\n----\nx = y\n[2|check]>\n",
            encoding="utf-8",
        )

        def _fail_workspace(*args, **kwargs):
            raise ValueError("invalid current workspace")

        monkeypatch.setattr(
            commit_commands,
            "_record_prover_workspace_view",
            _fail_workspace,
        )

        with pytest.raises(ValueError, match="invalid current workspace"):
            _finalize_tactic_execution(
                session,
                command="commit",
                execution_mode="commit",
                status="ok",
                attempted_tactics=["wp."],
                accepted_count=1,
                raw_output="OK",
                ok=True,
                emit_execution_stdout=False,
            )

        event_types = [event_type for event_type, _, _ in session.events]
        assert "tactic.execution.produced" not in event_types
        assert not (session.dir / "tactic_execution_results").exists()
