"""Tests for the live TacticExecutionResult contract."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

import sys
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from core.easycrypt.session_tactic_execution_result import (  # type: ignore  # noqa: E402
    TACTIC_EXECUTION_RESULT_KIND,
    build_tactic_execution_result,
    format_tactic_execution_result,
    record_tactic_execution_result,
    validate_tactic_execution_result,
    write_tactic_execution_result_artifact,
    write_tactic_raw_result_artifact,
)
from core.easycrypt.session_events import append_event  # type: ignore  # noqa: E402
from core.easycrypt.commands.commit_commands import (  # type: ignore  # noqa: E402
    _finalize_tactic_execution,
)


def _commit_response(
    *,
    command: str = "next",
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
        "schema_version": 1,
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
        "agent_view": {},
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
        "schema_version": 1,
        "kind": "prover_workspace_view",
        "ok": True,
        "current_goal": {
            "lines": ["Current goal", "----", "x{1} = x{2}"],
            "text_fully_shown": True,
            "truncated": False,
            "goal_type": "pRHL",
            "view_focus": "relational_program",
        },
        "proof_position": {"status": "open"},
        "proof_frontier": {"summary": "frontier"},
        "facts_and_gaps": {},
        "suggested_next_steps": {"primary": {"id": "inspect.goal_info"}},
        "recent_diagnostics": {},
        "want_more_context": {
            "full_context_artifact": "/tmp/proof_context.json",
            "current_session_fallback": ".ec_session/current.out",
        },
    }


def test_tactic_execution_result_commit_contract_and_artifact() -> None:
    with tempfile.TemporaryDirectory() as td:
        result = build_tactic_execution_result(
            Path(td),
            mode="commit",
            command="next",
            commit_response=_commit_response(),
            commit_response_payload={"artifact": str(Path(td) / "commit.json")},
            proof_context_payload={"artifact": str(Path(td) / "context.json")},
            workspace_view=_workspace_view(),
            workspace_payload={
                "artifact": str(Path(td) / "workspace.json"),
                "view_hash": "workspace-hash",
                "current_goal_text_fully_shown": True,
                "current_goal_truncated": False,
                "goal_chars": 32,
                "workspace_chars": 2048,
            },
            raw_result="OK\nCurrent goal",
        )
        payload = write_tactic_execution_result_artifact(Path(td), result)
        artifact = Path(payload["artifact"])

        assert result["kind"] == TACTIC_EXECUTION_RESULT_KIND
        assert result["execution"]["mode"] == "commit"
        assert result["execution"]["state_changed"] is True
        assert result["workspace"]["view"]["current_goal"]["lines"][0] == "Current goal"
        assert result["workspace"]["artifact"].endswith("workspace.json")
        assert not any(
            handle.get("id") == "current_session_goal_file"
            for handle in result["inspect_handles"]
        )
        assert payload["workspace_artifact"].endswith("workspace.json")
        assert artifact.exists()
        assert validate_tactic_execution_result(json.loads(artifact.read_text())).ok


def test_inspect_handles_expose_goal_file_only_when_goal_truncated() -> None:
    workspace = _workspace_view()
    workspace["current_goal"]["text_fully_shown"] = False
    workspace["current_goal"]["truncated"] = True
    result = build_tactic_execution_result(
        Path("."),
        mode="commit",
        command="next",
        commit_response=_commit_response(),
        workspace_view=workspace,
    )

    assert any(
        handle.get("id") == "current_session_goal_file"
        and handle.get("path") == ".ec_session/current.out"
        for handle in result["inspect_handles"]
    )


def test_tactic_execution_result_preflight_never_changes_state() -> None:
    raw = (
        "[TRY] tactic: inline *.\n"
        "[TRY] accepted: True\n"
        "[TRY] goal_after: 1 subgoal(s) remaining\n"
        "[TRY] goal_after_raw:\n"
        "Current goal\n"
        "\n"
        "&1 (left ) : {x : int}\n"
        "&2 (right) : {x : int}\n"
        "pre = true\n"
        "post = x{1} = x{2}\n"
        "[12|check]>\n"
        "[TRY] NOTE: session state unchanged.\n"
    )
    result = build_tactic_execution_result(
        Path("."),
        mode="preflight",
        command="try",
        commit_response=_commit_response(
            command="try",
            status="preflight_accepted",
            accepted_count=0,
        ),
        workspace_view=_workspace_view(),
        raw_result=raw,
        raw_result_payload={
            "artifact": ".ec_session/tactic_raw_results/try_after.txt",
        },
    )

    assert result["execution"]["mode"] == "preflight"
    assert result["execution"]["preflight_accepted"] is True
    assert result["execution"]["state_changed"] is False
    assert result["execution"]["history_committed"] is False
    assert result["candidate_after"]["kind"] == "preflight_candidate_after"
    assert result["candidate_after"]["state_changed"] is False
    assert result["candidate_after"]["current_goal"]["text_fully_shown"] is True
    assert result["candidate_after"]["current_goal"]["lines"][0] == "Current goal"
    assert result["candidate_after"]["raw_result_artifact"].endswith("try_after.txt")
    assert any(
        handle["id"] == "preflight_candidate_after"
        for handle in result["inspect_handles"]
    )
    compact = format_tactic_execution_result(result)
    assert '"candidate_after":' in compact
    stdout_payload = json.loads(compact.split("\n", 1)[1])
    assert "kind" not in stdout_payload["candidate_after"]
    assert "raw_result_artifact" not in compact


def test_tactic_execution_result_try_chain_surfaces_candidate_after() -> None:
    raw = (
        "[TRY-CHAIN] tactics: 2 step(s)\n"
        "  [1] inline{1} 1.\n"
        "  [2] inline{2} 1.\n"
        "\n"
        "[TRY-CHAIN] all_accepted: True\n"
        "[TRY-CHAIN] final_closed: False\n"
        "  step 1 (inline{1} 1.): -> 1 subgoal(s) remaining\n"
        "  step 2 (inline{2} 1.): -> 1 subgoal(s) remaining\n"
        "[TRY-CHAIN] goal_after: 1 subgoal(s) remaining\n"
        "[TRY-CHAIN] goal_after_raw:\n"
        "Current goal\n"
        "\n"
        "&1 (left ) : {x : int}\n"
        "&2 (right) : {x : int}\n"
        "pre = true\n"
        "post = x{1} = x{2}\n"
        "[12|check]>\n"
        "[TRY-CHAIN] NOTE: session state unchanged.\n"
    )
    result = build_tactic_execution_result(
        Path("."),
        mode="preflight",
        command="try-chain",
        commit_response=_commit_response(
            command="try-chain",
            status="preflight_accepted",
            accepted_count=0,
        ),
        workspace_view=_workspace_view(),
        raw_result=raw,
        raw_result_payload={
            "artifact": ".ec_session/tactic_raw_results/try_chain_after.txt",
        },
    )

    assert result["candidate_after"]["goal_after_remaining"] == 1
    assert result["candidate_after"]["current_goal"]["lines"][0] == "Current goal"
    assert (
        result["candidate_after"]["current_goal"]["source"]["label"]
        == "[TRY-CHAIN] goal_after_raw"
    )


def test_tactic_execution_result_chain_steps_and_undo() -> None:
    chain = build_tactic_execution_result(
        Path("."),
        mode="commit_chain",
        command="chain",
        commit_response=_commit_response(
            command="chain",
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
        Path("."),
        mode="undo",
        command="prev",
        commit_response=_commit_response(
            command="prev",
            status="undone",
            attempted=[],
            accepted_count=0,
        ),
        workspace_view=_workspace_view(),
    )

    assert chain["execution"]["mode"] == "commit_chain"
    assert chain["execution"]["steps"][1]["status"] == "failed"
    assert undo["execution"]["mode"] == "undo"
    assert undo["execution"]["state_changed"] is True


def test_tactic_execution_result_record_and_format() -> None:
    class Session:
        def __init__(self, path: Path) -> None:
            self.dir = path
            self.events: list[tuple[str, dict, str]] = []

        def emit_event(self, event_type: str, payload: dict, *, source: str = "") -> None:
            self.events.append((event_type, payload, source))

    with tempfile.TemporaryDirectory() as td:
        session = Session(Path(td))
        raw_payload = write_tactic_raw_result_artifact(
            session.dir,
            command="next",
            raw_result="raw easycrypt result",
        )
        result = build_tactic_execution_result(
            session.dir,
            mode="commit",
            command="next",
            commit_response=_commit_response(),
            workspace_view=_workspace_view(),
            raw_result="raw easycrypt result",
            raw_result_payload=raw_payload,
        )
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
        assert result["inspect_handles"][1]["kind"] == "manager_request"
        assert result["inspect_handles"][1]["request"] == "goal_info"
        assert "command" not in result["inspect_handles"][1]


def test_tactic_execution_result_stdout_is_workspace_first_under_cap() -> None:
    workspace = _workspace_view()
    workspace["current_goal"]["lines"] = [
        "Current goal (remaining: 4)",
        *[f"  statement {idx} : x{idx}{{1}} = x{idx}{{2}}" for idx in range(90)],
    ]
    workspace["current_goal"]["char_count"] = len(
        "\n".join(workspace["current_goal"]["lines"])
    )
    workspace["suggested_next_steps"] = {
        "primary": {
            "id": "inspect.latest_error",
            "category": "diagnose",
            "command": "python3 core/easycrypt/session_cli.py -d .ec_session -diagnose",
        },
        "alternatives": [
            {
                "id": f"proof_ir.strategy.{idx}",
                "category": "strategy",
                "why": "reason about this candidate before committing",
                "contract": {
                    "role": "strategy_context",
                    "meaning": "verbose internal explanation",
                    "guardrail": "not directly runnable",
                    "use": "choose an inspection or instantiate it",
                },
            }
            for idx in range(8)
        ],
    }
    result = build_tactic_execution_result(
        Path("."),
        mode="commit_chain",
        command="chain",
        commit_response=_commit_response(
            command="chain",
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

        def emit_event(self, event_type: str, payload: dict, *, source: str = "") -> None:
            self.events.append((event_type, payload, source))

    with tempfile.TemporaryDirectory() as td:
        session = Session(Path(td))
        (session.dir / "current.out").write_text(
            "[1|check]>\nCurrent goal\n----\nx = y\n[2|check]>\n",
            encoding="utf-8",
        )
        payload = _finalize_tactic_execution(
            session,
            command="next",
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
            "agent.view.produced",
            "prover.workspace_view.produced",
            "tactic.execution.produced",
        ]
        execution_event = [
            payload for event_type, payload, _ in session.events
            if event_type == "tactic.execution.produced"
        ][0]
        assert execution_event["candidate_after_available"] is False
        assert execution_event["candidate_after_text_fully_shown"] is False
        result = json.loads(Path(execution_event["artifact"]).read_text())
        assert result["execution"]["mode"] == "commit"
        assert result["workspace"]["view"]["kind"] == "prover_workspace_view"
        assert "command_summary_artifact" not in result["audit"]


def test_try_chain_finalizer_ignores_live_try_tool_call() -> None:
    class Session:
        def __init__(self, path: Path) -> None:
            self.dir = path
            self.events: list[tuple[str, dict, str]] = []

        def emit_event(self, event_type: str, payload: dict, *, source: str = "") -> None:
            self.events.append((event_type, payload, source))

    with tempfile.TemporaryDirectory() as td:
        session = Session(Path(td))
        (session.dir / "current.out").write_text(
            "[1|check]>\nCurrent goal\n----\nx = y\n[2|check]>\n",
            encoding="utf-8",
        )
        append_event(session.dir, "session.started", {
            "file": None,
            "lemma": "L",
            "include_dirs": [],
            "discarded_tactic_count": 0,
            "restart_count": 1,
        })
        append_event(session.dir, "tool.called", {
            "name": "try",
            "mutates_proof_state": False,
            "session_dir": str(session.dir.resolve()),
        })

        payload = _finalize_tactic_execution(
            session,
            command="try-chain",
            live_tool_name="try",
            execution_mode="probe",
            status="probe_accepted",
            attempted_tactics=["inline{1} 1. inline{2} 1."],
            accepted_count=0,
            raw_output=(
                "[TRY-CHAIN] all_accepted: True\n"
                "[TRY-CHAIN] final_closed: False\n"
            ),
            ok=True,
            emit_execution_stdout=False,
        )

        assert payload is not None
        response = json.loads(Path(payload["artifact"]).read_text())
        assert response["ok"] is True
        assert not any(
            err.get("code") == "proof_state.event_contract"
            for err in response["errors"]
        )
        execution_event = [
            payload for event_type, payload, _ in session.events
            if event_type == "tactic.execution.produced"
        ][0]
        result = json.loads(Path(execution_event["artifact"]).read_text())
        assert result["result"]["ok"] is True
        assert result["execution"]["command"] == "try-chain"
