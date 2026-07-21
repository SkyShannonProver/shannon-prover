"""Contract tests for structured session event logging.

These tests are pure Python and do not start EasyCrypt. They validate the
append-only JSONL contract and one pre-EC session_cli path so the event
schema can be refactored safely before broader proof replay tests exist.
"""
from __future__ import annotations

import tempfile
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

import sys
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from core.easycrypt.session_api import open_session  # type: ignore  # noqa: E402
from core.easycrypt.session_events import (  # type: ignore  # noqa: E402
    append_event,
    event_payload,
    has_candidate_closed,
    latest_tactic_error,
    make_event,
    read_events,
    summarize_events,
    validate_event,
    validate_event_stream,
)
from core.easycrypt.session_tactic_precheck import _strip_shell_filter_artifact  # type: ignore  # noqa: E402
from core.easycrypt.session_projection import read_proof_state_projection  # type: ignore  # noqa: E402
from workflow.progress import (  # noqa: E402
    _event_log_has_candidate_closed,
    _session_goal_state_text,
    _session_state_has_candidate_closed,
)
from workflow.proof_acceptance import (  # noqa: E402
    emit_workflow_verification_event,
    validate_acceptance_event_contract,
    validate_candidate_event_contract,
)
from core.easycrypt.analysis.ec_goal_parser import goal_to_json, parse_goal  # type: ignore  # noqa: E402
from core.easycrypt.ec_suggest import suggest_close, suggest_from_session  # type: ignore  # noqa: E402
from core.easycrypt.session_state import (  # type: ignore  # noqa: E402
    REMAINING_UNKNOWN,
    infer_goal_count,
    read_session_state,
)
from core.easycrypt.commands.session_commands import handle_status  # type: ignore  # noqa: E402
from core.easycrypt.commands.speculative_commands import handle_align, handle_swap_search  # type: ignore  # noqa: E402
from core.easycrypt.ec_bridge_lemmas import analyze_bridge_lemmas_from_session  # type: ignore  # noqa: E402
from core.easycrypt.analysis.ec_call_subgoals import preview_from_session  # type: ignore  # noqa: E402
from core.easycrypt.ec_diagnose import diagnose_from_session  # type: ignore  # noqa: E402
from core.easycrypt.subgoal_gap import analyze_session  # type: ignore  # noqa: E402


def _chain_session_summary(session_dir: str | Path) -> dict[str, Any]:
    path = Path(session_dir)
    events = read_events(path)
    event_summary = summarize_events(events)
    accepted = 0
    failed = 0
    for event in events:
        if event.get("type") != "tactic.result":
            continue
        payload = event_payload(event)
        status = str(payload.get("status") or "")
        committed = payload.get("history_committed")
        if status == "ok" and committed is not False:
            accepted += 1
        elif status in {"error", "probe_error", "probe_rejected"} or payload.get(
            "has_new_error"
        ):
            failed += 1

    projection_status = "unknown"
    projection_candidate_ready = False
    projection_final_ready = False
    projection_consistency_errors: list[str] = []
    remaining_goals: int | None = None
    try:
        projection = read_proof_state_projection(path)
        projection_status = projection.status
        projection_candidate_ready = projection.candidate_ready
        projection_final_ready = projection.final_ready
        projection_consistency_errors = list(projection.consistency.errors)
        remaining_goals = projection.goal.num_remaining
    except Exception as exc:
        projection_consistency_errors = [f"projection unreadable: {exc}"]

    if remaining_goals is None or remaining_goals == REMAINING_UNKNOWN:
        state = read_session_state(path)
        remaining_goals = state.num_remaining
        if remaining_goals == REMAINING_UNKNOWN:
            raw = (
                (path / "current.out").read_text(encoding="utf-8", errors="replace")
                if (path / "current.out").exists()
                else ""
            )
            inferred, _ = infer_goal_count(raw)
            remaining_goals = None if inferred == REMAINING_UNKNOWN else inferred

    candidate_closed = bool(
        event_summary.candidate_closed_count
        or projection_status in {"candidate_closed", "verified"}
        or projection_candidate_ready
    )
    return {
        "accepted_tactics": accepted,
        "failed_tactics": failed,
        "candidate_closed": candidate_closed,
        "remaining_goals": remaining_goals,
        "event_counts": dict(event_summary.event_counts),
        "tactic_status_counts": dict(event_summary.tactic_status_counts),
        "verification_status": event_summary.verification_status,
        "projection_status": projection_status,
        "projection_candidate_ready": projection_candidate_ready,
        "projection_final_ready": projection_final_ready,
        "projection_consistency_errors": projection_consistency_errors,
    }


def _classify_chain_outcome(
    exit_code: int,
    stdout: str,
    session_dir: str | Path,
) -> tuple[str, dict[str, Any]]:
    summary = _chain_session_summary(session_dir)
    accepted = int(summary.get("accepted_tactics") or 0)
    failed = int(summary.get("failed_tactics") or 0)
    closed = bool(summary.get("candidate_closed"))
    output = str(stdout or "").lower()
    if closed or (exit_code == 0 and failed == 0):
        return "ACCEPT", summary
    if accepted > 0:
        return "PARTIAL", summary
    if failed > 0 or exit_code != 0 or "failed" in output or "error" in output:
        return "REJECT", summary
    return "UNKNOWN", summary


def _append_minimal_closed_stream(d: Path, tactic: str = "qed.") -> None:
    append_event(d, "session.started", {
        "file": None,
        "lemma": "L",
        "include_dirs": [],
        "discarded_tactic_count": 0,
        "restart_count": 1,
    })
    append_event(d, "tool.called", {
        "name": "next",
        "mutates_proof_state": True,
        "session_dir": str(d.resolve()),
    })
    append_event(d, "tactic.submitted", {
        "tactic": tactic,
        "history_lines_before": 0,
        "line_count": 1,
    })
    append_event(d, "goal.changed", {
        "tactic": tactic,
        "goals_before": 1,
        "goals_after": 0,
        "no_more_goals": True,
        "async_check_close": False,
        "no_progress": False,
        "candidate_closed": True,
    })
    append_event(d, "tactic.result", {
        "tactic": tactic,
        "status": "ok",
        "history_committed": True,
        "candidate_closed": True,
    })
    append_event(d, "proof.candidate_closed", {
        "tactic": tactic,
        "goals_before": 1,
        "goals_after": 0,
        "no_more_goals": True,
        "async_check_close": False,
    })
    append_event(d, "tool.result", {
        "name": "next",
        "mutates_proof_state": True,
        "session_dir": str(d.resolve()),
        "exit_code": 0,
        "status": "ok",
    })


def test_append_event_jsonl_contract() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        assert append_event(d, "session.started", {"lemma": "L"})
        events = read_events(d)
        assert len(events) == 1
        event = events[0]
        assert event["schema_version"] == 1
        assert event["type"] == "session.started"
        assert event["source"] == "session_cli"
        assert event["payload"]["lemma"] == "L"
        assert event["session_dir"] == str(d.resolve())
        assert event["event_id"]
        assert event["timestamp"].endswith("Z")


def test_candidate_closed_reader() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        path = d / "events.jsonl"
        assert not _event_log_has_candidate_closed(path)
        append_event(d, "proof.candidate_closed", {"tactic": "qed."})
        assert not _event_log_has_candidate_closed(path)
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        path = d / "events.jsonl"
        _append_minimal_closed_stream(d)
        assert _event_log_has_candidate_closed(path)
        events = read_events(d)
        assert has_candidate_closed(events)


def test_event_summary_and_latest_error_helpers() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        append_event(d, "tactic.submitted", {"tactic": "bad."})
        append_event(d, "tactic.result", {
            "tactic": "bad.",
            "status": "error",
            "candidate_closed": False,
            "latest_error": "[error] bad tactic",
        })
        append_event(d, "tactic.submitted", {"tactic": "qed."})
        append_event(d, "tactic.result", {
            "tactic": "qed.",
            "status": "ok",
            "candidate_closed": True,
        })
        append_event(d, "proof.candidate_closed", {"tactic": "qed."})
        append_event(d, "verification.completed", {"status": "pass"})

        events = read_events(d)
        summary = summarize_events(events)
        assert summary.event_counts["tactic.result"] == 2
        assert summary.tactic_submitted_count == 2
        assert summary.tactic_result_count == 2
        assert summary.candidate_closed_count == 1
        assert summary.result_candidate_closed_count == 1
        assert summary.tactic_status_counts == {"error": 1, "ok": 1}
        assert summary.verification_status == "pass"
        latest = latest_tactic_error(events)
        assert latest.error == "[error] bad tactic"
        assert latest.tactic == "bad."


def test_event_summary_tracks_latest_attempt_and_prior_preflight_failure() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        append_event(d, "tactic.try_result", {
            "name": "try",
            "kind": "speculative_tactic",
            "mutates_proof_state": False,
            "tactic": "have h: Pr[MainD(G2, RO).distinguish(()) @ &m : res] = 0%r.",
            "status": "ok",
            "accepted": False,
            "error_kind": "arity",
            "report": (
                "[TRY] tactic: have h: bad.\n"
                "[TRY] accepted: False\n"
                "[TRY] error_kind: arity\n"
                "[TRY] error_excerpt:\n"
                "  wrong number of arguments\n"
                "[TRY] NOTE: session state unchanged.\n"
            ),
        })
        append_event(d, "tactic.try_result", {
            "name": "try",
            "kind": "speculative_tactic",
            "mutates_proof_state": False,
            "tactic": "have h: 1 = 1 by done.",
            "status": "ok",
            "accepted": True,
            "report": (
                "[TRY] tactic: have h: 1 = 1 by done.\n"
                "[TRY] accepted: True\n"
            ),
        })

        summary = summarize_events(read_events(d))
        assert summary.latest_attempt is not None
        assert summary.latest_attempt.tactic == "have h: 1 = 1 by done."
        assert summary.latest_attempt.status == "preflight_accepted"
        assert summary.latest_attempt.error == ""
        assert len(summary.recent_failed_attempts) == 1
        failure = summary.recent_failed_attempts[0]
        assert failure.status == "preflight_rejected"
        assert failure.error == "wrong number of arguments"


def _event(d: Path, typ: str, payload: dict) -> dict:
    return make_event(d, typ, payload)


def test_validate_event_payload_schema() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        ok_event = _event(d, "tactic.submitted", {
            "tactic": "proc.",
            "history_lines_before": 0,
            "line_count": 1,
        })
        assert validate_event(ok_event) == []

        bad_event = _event(d, "tactic.submitted", {
            "tactic": "proc.",
            "line_count": "one",
        })
        issues = validate_event(bad_event)
        codes = [issue.code for issue in issues]
        assert "event.payload.missing" in codes
        assert "event.payload.type" in codes

        diag_event = _event(d, "diagnostic.emitted", {
            "source": "auto_bridge_suggest",
            "layer": 2,
            "suppress_error": False,
            "request_rollback": False,
            "text": "[AUTO-BRIDGE-SUGGEST] ...",
            "schema_version": 1,
            "kind": "recommendation",
            "recommendations": [{
                "id": "auto_bridge.0",
                "kind": "tactic_chain",
                "producer": "AUTO-BRIDGE-SUGGEST",
                "action": "-chain -c 'have -> : Pr[A] = Pr[B].'",
                "why": "daemon accepted the bridge tactic",
                "confidence": "verified",
            }],
            "evidence": {
                "probe": [{
                    "id": "probe.auto_bridge.0",
                    "accepted": True,
                }],
            },
            "notes": [],
            "errors": [],
            "debug": {},
        })
        assert validate_event(diag_event) == []

        view_event = _event(d, "tool.view.produced", {
            "tool": "goal-info",
            "schema_version": 1,
            "ok": True,
            "artifact": str(d / "tool_views" / "goal-info_deadbeef.json"),
            "view_hash": "a" * 40,
            "proof_status": "open",
            "recommendation_count": 2,
            "error_count": 0,
            "warning_count": 0,
            "note_count": 1,
        })
        assert validate_event(view_event) == []

        agent_view_event = _event(d, "agent.view.produced", {
            "schema_version": 1,
            "ok": True,
            "artifact": str(d / "proof_context_views" / "proof_context_view_deadbeef.json"),
            "view_hash": "b" * 40,
            "proof_status": "open",
            "goal_hash": "goal-hash",
            "recommendation_count": 1,
            "stale_recommendation_count": 0,
            "error_count": 0,
            "warning_count": 0,
            "source_event_count": 3,
        })
        assert validate_event(agent_view_event) == []

        workspace_event = _event(d, "prover.workspace_view.produced", {
            "schema_version": 1,
            "view_kind": "prover_workspace_view",
            "ok": True,
            "artifact": str(d / "prover_workspace_views" / "view.json"),
            "view_hash": "w" * 40,
            "proof_status": "open",
            "current_goal_text_fully_shown": True,
            "current_goal_truncated": False,
            "goal_chars": 42,
            "workspace_chars": 2048,
        })
        assert validate_event(workspace_event) == []

        commit_response_event = _event(d, "commit.response.produced", {
            "schema_version": 1,
            "ok": True,
            "command": "chain",
            "status": "ok",
            "artifact": str(d / "commit_responses" / "chain_deadbeef.json"),
            "response_hash": "c" * 40,
            "proof_status": "open",
            "attempted_count": 2,
            "accepted_count": 2,
            "failed_tactic": "",
            "error_count": 0,
            "warning_count": 0,
            "agent_view_artifact": str(d / "proof_context_views" / "agent.json"),
        })
        assert validate_event(commit_response_event) == []

        tactic_execution_event = _event(d, "tactic.execution.produced", {
            "schema_version": 1,
            "ok": True,
            "mode": "commit_chain",
            "command": "chain",
            "status": "ok",
            "artifact": str(d / "tactic_execution_results" / "chain.json"),
            "result_hash": "e" * 40,
            "accepted_count": 2,
            "rollback_count": 0,
            "failed_tactic": "",
            "state_changed": True,
            "history_committed": True,
            "probe_accepted": False,
            "workspace_artifact": str(d / "prover_workspace_views" / "view.json"),
            "workspace_chars": 2048,
            "proof_context_artifact": str(d / "proof_context_views" / "agent.json"),
            "commit_response_artifact": str(d / "commit_responses" / "chain.json"),
            "raw_result_artifact": str(d / "tactic_raw_results" / "chain.txt"),
            "error_count": 0,
            "warning_count": 0,
        })
        assert validate_event(tactic_execution_event) == []

        command_summary_event = _event(d, "command.summary.produced", {
            "schema_version": 1,
            "ok": True,
            "command": "chain",
            "command_status": "ok",
            "artifact": str(d / "command_summaries" / "chain_deadbeef.json"),
            "summary_hash": "d" * 40,
            "proof_status": "open",
            "goal_hash": "goal-hash",
            "goal_type": "pRHL",
            "num_remaining": 1,
            "history_tactic_count": 2,
            "transition_kind": "progress",
            "primary_action": "try_tactic",
            "recommendation_count": 1,
            "error_count": 0,
            "warning_count": 0,
            "commit_response_artifact": str(
                d / "commit_responses" / "chain.json"
            ),
            "agent_view_artifact": str(d / "proof_context_views" / "agent.json"),
        })
        assert validate_event(command_summary_event) == []

        episode_timeline_event = _event(d, "episode.timeline.produced", {
            "schema_version": 1,
            "ok": True,
            "artifact": str(d / "episode_timelines" / "timeline.json"),
            "timeline_hash": "e" * 40,
            "step_count": 2,
            "final_proof_status": "candidate_closed",
            "final_primary_action": "verify",
            "note_count": 0,
            "error_count": 0,
        })
        assert validate_event(episode_timeline_event) == []


def test_validate_event_stream_accepts_realistic_replay_flow() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        events = [
            _event(d, "session.started", {
                "file": str(d / "proof.ec"),
                "lemma": "L",
                "include_dirs": [],
                "discarded_tactic_count": 0,
                "restart_count": 1,
            }),
            _event(d, "session.loaded_context", {
                "file": str(d / "proof.ec"),
                "context_file": str(d / "context.ec"),
                "bytes": 10,
                "lines": 1,
            }),
            _event(d, "tool.called", {
                "name": "start",
                "mutates_proof_state": True,
                "session_dir": str(d),
            }),
            _event(d, "tool.result", {
                "name": "start",
                "mutates_proof_state": True,
                "session_dir": str(d),
                "exit_code": 0,
                "status": "ok",
            }),
            _event(d, "tool.called", {
                "name": "next",
                "mutates_proof_state": True,
                "session_dir": str(d),
            }),
            _event(d, "tactic.submitted", {
                "tactic": "qed.",
                "history_lines_before": 0,
                "line_count": 1,
            }),
            _event(d, "goal.changed", {
                "tactic": "qed.",
                "goals_before": 1,
                "goals_after": 0,
                "no_more_goals": True,
                "async_check_close": False,
                "no_progress": False,
                "candidate_closed": True,
            }),
            _event(d, "tactic.result", {
                "tactic": "qed.",
                "status": "ok",
                "history_committed": True,
                "candidate_closed": True,
            }),
            _event(d, "proof.candidate_closed", {
                "tactic": "qed.",
                "goals_before": 1,
                "goals_after": 0,
                "no_more_goals": True,
                "async_check_close": False,
            }),
            _event(d, "tool.result", {
                "name": "next",
                "mutates_proof_state": True,
                "session_dir": str(d),
                "exit_code": 0,
                "status": "ok",
            }),
            _event(d, "tool.called", {
                "name": "verify",
                "mutates_proof_state": False,
                "session_dir": str(d),
            }),
            _event(d, "verification.completed", {
                "lemma": "L",
                "status": "pass",
                "verifier": "easycrypt",
            }),
            _event(d, "tool.result", {
                "name": "verify",
                "mutates_proof_state": False,
                "session_dir": str(d),
                "exit_code": 0,
                "status": "ok",
            }),
        ]
        result = validate_event_stream(events, expected_outcome="PASS")
        assert result.ok
        assert result.error_count == 0
        assert result.warning_count == 0


def test_validate_event_stream_detects_pairing_and_fake_close() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        events = [
            _event(d, "session.started", {
                "file": None,
                "lemma": "L",
                "include_dirs": [],
                "discarded_tactic_count": 0,
                "restart_count": 1,
            }),
            _event(d, "tool.called", {
                "name": "next",
                "mutates_proof_state": True,
                "session_dir": str(d),
            }),
            _event(d, "tactic.submitted", {
                "tactic": "bad.",
                "history_lines_before": 0,
                "line_count": 1,
            }),
            _event(d, "tactic.result", {
                "tactic": "bad.",
                "status": "error",
                "history_committed": False,
                "candidate_closed": True,
            }),
            _event(d, "proof.candidate_closed", {
                "tactic": "bad.",
                "goals_before": 1,
                "goals_after": 0,
                "no_more_goals": True,
                "async_check_close": False,
            }),
        ]
        result = validate_event_stream(events, expected_outcome="PASS")
        codes = [issue.code for issue in result.errors]
        assert "stream.candidate_close.failed_tactic" in codes
        assert "stream.tool.missing_result" in codes
        assert "stream.verification.required_pass" in codes


def test_validate_event_stream_detects_tool_name_mismatch() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        events = [
            _event(d, "session.started", {
                "file": None,
                "lemma": "L",
                "include_dirs": [],
                "discarded_tactic_count": 0,
                "restart_count": 1,
            }),
            _event(d, "tool.called", {
                "name": "status",
                "mutates_proof_state": False,
                "session_dir": str(d),
            }),
            _event(d, "tool.result", {
                "name": "goal-info",
                "mutates_proof_state": False,
                "session_dir": str(d),
                "exit_code": 0,
                "status": "ok",
            }),
        ]
        result = validate_event_stream(events)
        assert "stream.tool.name_mismatch" in [
            issue.code for issue in result.errors
        ]


def test_proof_acceptance_gate_requires_valid_candidate_contract() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        append_event(d, "proof.candidate_closed", {"tactic": "qed."})
        invalid = validate_candidate_event_contract(d)
        assert not invalid.ok
        assert any("session" in err for err in invalid.errors)

    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        _append_minimal_closed_stream(d)
        valid = validate_candidate_event_contract(d)
        assert valid.ok
        assert valid.candidate_closed


def test_proof_acceptance_gate_requires_verification_event() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        _append_minimal_closed_stream(d)
        before_verify = validate_acceptance_event_contract(d)
        assert not before_verify.ok
        assert before_verify.verification_status is None

        assert emit_workflow_verification_event(
            d, lemma="L", status="pass", verifier="easycrypt",
        )
        after_verify = validate_acceptance_event_contract(d)
        assert after_verify.ok
        assert after_verify.verification_status == "pass"


def test_progress_session_state_closed_fallback() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        session_dir = d / ".ec_session_prover"
        session_dir.mkdir()
        (session_dir / "current.out").write_text(
            "[35|check]>\n"
            "No more goals\n"
            "[36|check]>\n"
            "+ added lemma: `L'\n"
            "[37|check]>\n",
            encoding="utf-8",
        )
        assert _session_state_has_candidate_closed(str(d), ".ec_session_prover")
        goal = _session_goal_state_text(str(d), ".ec_session_prover")
        assert "No more goals" in goal

    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        session_dir = d / ".ec_session_prover"
        session_dir.mkdir()
        (session_dir / "current.out").write_text(
            "[31|check]>",
            encoding="utf-8",
        )
        (session_dir / "history.ec").write_text(
            "proc; islossless.\nqed.\n",
            encoding="utf-8",
        )
        _append_minimal_closed_stream(session_dir)
        assert _session_state_has_candidate_closed(str(d), ".ec_session_prover")
        goal = _session_goal_state_text(str(d), ".ec_session_prover")
        assert "Proof is already complete" in goal


def test_replay_chain_uses_structured_session_summary() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        (d / "current.out").write_text(
            "[1|check]>\n"
            "Current goal\n"
            "----\n"
            "x = y\n"
            "[2|check]>\n",
            encoding="utf-8",
        )
        append_event(d, "tactic.submitted", {"tactic": "proc."})
        append_event(d, "tactic.result", {
            "tactic": "proc.",
            "status": "ok",
            "has_new_error": False,
            "history_committed": True,
        })

        outcome, summary = _classify_chain_outcome(0, "", d)
        assert outcome == "ACCEPT"
        assert summary["accepted_tactics"] == 1
        assert _chain_session_summary(d)["remaining_goals"] == 1

    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        (d / "current.out").write_text(
            "[1|check]>\nCurrent goal\n----\nx = y\n[2|check]>\n",
            encoding="utf-8",
        )
        append_event(d, "tactic.submitted", {"tactic": "proc."})
        append_event(d, "tactic.result", {
            "tactic": "proc.",
            "status": "ok",
            "has_new_error": False,
            "history_committed": True,
        })
        append_event(d, "tactic.submitted", {"tactic": "bad."})
        append_event(d, "tactic.result", {
            "tactic": "bad.",
            "status": "error",
            "has_new_error": True,
            "history_committed": False,
        })

        outcome, summary = _classify_chain_outcome(1, "failed", d)
        assert outcome == "PARTIAL"
        assert summary["accepted_tactics"] == 1
        assert summary["failed_tactics"] == 1

    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        (d / "current.out").write_text("[31|check]>", encoding="utf-8")
        (d / "history.ec").write_text(
            "proc; islossless.\nqed.\n",
            encoding="utf-8",
        )
        _append_minimal_closed_stream(d)

        summary = _chain_session_summary(d)
        assert summary["candidate_closed"] is True
        assert summary["projection_status"] == "candidate_closed"
        assert summary["projection_candidate_ready"] is True
        assert summary["remaining_goals"] == 0
        assert summary["projection_consistency_errors"] == []



def test_diagnose_prefers_structured_latest_error_event() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        (d / "current.out").write_text(
            "[1|check]>\n"
            "Current goal\n"
            "----\n"
            "x = y\n"
            "[2|check]>\n",
            encoding="utf-8",
        )
        append_event(d, "tactic.result", {
            "tactic": "apply MissingLemma.",
            "status": "error",
            "latest_error": "[error] unknown lemma: MissingLemma",
            "error_lines": ["[error] unknown lemma: MissingLemma"],
        })

        report = diagnose_from_session(d)
        assert "unknown lemma: MissingLemma" in report
        assert "Tactic:     apply MissingLemma." in report


def test_meta_command_refusal_emits_events_without_ec() -> None:
    with tempfile.TemporaryDirectory() as td:
        session = open_session(Path(td))
        out = session.append_block("search Foo.")
        assert "[META_COMMAND_REFUSED]" in out
        events = read_events(Path(td))
        event_types = [event["type"] for event in events]
        assert "error.raised" in event_types
        assert "tactic.result" in event_types
        result_events = [
            event for event in events if event["type"] == "tactic.result"
        ]
        assert result_events[-1]["payload"]["status"] == "refused"
        assert result_events[-1]["payload"]["history_committed"] is False


def test_raw_proof_control_refusal_emits_events_without_ec() -> None:
    with tempfile.TemporaryDirectory() as td:
        session = open_session(Path(td))
        out = session.append_block("undo 2.")
        assert "[PROOF_CONTROL_REFUSED]" in out
        assert "-tactic-exec undo" in out
        events = read_events(Path(td))
        result_events = [
            event for event in events if event["type"] == "tactic.result"
        ]
        assert result_events[-1]["payload"]["status"] == "refused"
        assert result_events[-1]["payload"]["reason"] == "proof_control_command"
        assert result_events[-1]["payload"]["history_committed"] is False


def test_shell_filter_artifact_stripper_handles_probe_tails() -> None:
    cleaned, changed = _strip_shell_filter_artifact(
        "wp.' 2>&1 | grep 'TACTIC-EXECUTION-RESULT.*workspace"
    )

    assert changed is True
    assert cleaned == "wp."


def test_closed_post_qed_prompt_is_goal_info_closed_state() -> None:
    with tempfile.TemporaryDirectory() as td:
        session = open_session(Path(td))
        session.curr.write_text(
            "[28|check]>\n"
            "No more goals\n"
            "[29|check]>\n"
            "+ added lemma: `L'\n"
            "[30|check]>\n",
            encoding="utf-8",
        )
        block, remaining = session.get_active_goal_block()
        assert remaining == 0
        assert "No more goals" in block
        state = read_session_state(Path(td))
        assert state.proof_candidate_closed is True
        assert state.num_remaining == 0
        assert "No more goals" in state.raw_for_goal_tools


def test_session_state_extracts_latest_current_goal() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        (d / "current.out").write_text(
            "[1|check]>\n"
            "No more goals\n"
            "[2|check]>\n"
            "Current goal (remaining: 3)\n"
            "----\n"
            "x = y\n"
            "[10|check]>\n",
            encoding="utf-8",
        )
        state = read_session_state(d)
        assert state.proof_candidate_closed is False
        assert state.num_remaining == 3
        assert "Current goal (remaining: 3)" in state.raw_for_goal_tools
        assert "x = y" in state.raw_for_goal_tools
        assert infer_goal_count(state.raw_current) == (3, False)


def test_session_state_default_previous_path_is_prev_out() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        (d / "prev.out").write_text("old line\n", encoding="utf-8")
        (d / "current.out").write_text(
            "old line\nCurrent goal\n----\ny = z\n[2|check]>\n",
            encoding="utf-8",
        )
        state = read_session_state(d)
        assert state.previous_path.name == "prev.out"
        assert state.active_output.startswith("Current goal")
        assert "old line" not in state.active_output


def test_infer_goal_count_handles_post_qed_added_lemma_prompt() -> None:
    raw = (
        "[35|check]>\n"
        "No more goals\n"
        "[36|check]>\n"
        "+ added lemma: `L'\n"
        "[37|check]>\n"
    )
    assert infer_goal_count(raw) == (0, True)


def test_closed_goal_json_has_no_tactic_suggestions() -> None:
    info = parse_goal("No more goals\n[1|check]>\n")
    data = goal_to_json(info)
    assert data["num_remaining"] == 0
    assert data["proof_candidate_closed"] is True
    assert "suggested_tactics" not in data
    assert "parser_action_policy" not in data
    assert "next_action" in data


def test_probability_goal_behind_implication_is_not_ambient() -> None:
    raw = (
        "Current goal\n\n"
        "&m: {}\n"
        "i0: int\n"
        "------------------------------------------------------------------------\n"
        "0 <= i0 < Top.N => Pr[PIR.main(i0) @ &m : res = a i0] = 1%r\n"
        "[2|check]>\n"
    )
    info = parse_goal(raw)
    data = goal_to_json(info)

    assert data["goal_type"] == "probability"
    assert data["prob_form"] == "prob_eq_const"
    assert data["intro_required"] is True
    assert "suggested_tactics" not in data
    assert "parser_action_policy" not in data
    assert "legacy_shape_tactic_templates" not in data


def test_equiv_goal_parser_reports_root_relation_not_tactic_bridge_hint() -> None:
    raw = (
        "Current goal\n\n"
        "&m: {}\n"
        "------------------------------------------------------------------------\n"
        "pre = (glob A){2} = (glob A){m} /\\ (glob A){1} = (glob A){m}\n\n"
        "    G1(GenChaChaPoly(OCC(IFinRO))).main ~ MainD(G2, FinRO).distinguish\n\n"
        "post = res{1} <=> (fun (b : bool) => b) res{2}\n"
        "[2|check]>\n"
    )
    info = parse_goal(raw)
    data = goal_to_json(info)

    assert data["goal_type"] == "equiv"
    assert "bridge_hint" not in data
    relation = data["root_module_relation"]
    assert relation["lhs_root"] == "G1"
    assert relation["rhs_root"] == "MainD"
    assert relation["same_root_module"] is False
    assert "not a proof action recommendation" in relation["meaning"]


def test_suggest_close_closed_state_has_no_tactic_suggestions() -> None:
    out = suggest_close("No more goals\n[1|check]>\n", [])
    assert "Proof is already complete" in out
    assert "Suggested tactics" not in out


def test_suggest_from_session_handles_post_qed_added_lemma_prompt() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        (d / "current.out").write_text(
            "[35|check]>\n"
            "No more goals\n"
            "[36|check]>\n"
            "+ added lemma: `PIR_secure2'\n"
            "[37|check]>\n",
            encoding="utf-8",
        )
        out = suggest_from_session(d, [])
        assert "Proof is already complete" in out
        assert "Suggested tactics" not in out


def test_status_reports_closed_goal_as_complete_type() -> None:
    with tempfile.TemporaryDirectory() as td:
        session = open_session(Path(td))
        session.history.write_text("qed.\n", encoding="utf-8")
        session.curr.write_text(
            "[35|check]>\n"
            "No more goals\n"
            "[36|check]>\n"
            "+ added lemma: `L'\n"
            "[37|check]>\n",
            encoding="utf-8",
        )
        buf = StringIO()
        with redirect_stdout(buf):
            assert handle_status(session, SimpleNamespace()) == 0
        out = buf.getvalue()
        assert "[status] Goal type: complete" in out
        assert "[status] Proof COMPLETE" in out



def test_align_and_subgoal_gap_closed_goal_are_explicitly_closed() -> None:
    with tempfile.TemporaryDirectory() as td:
        session = open_session(Path(td))
        session.curr.write_text(
            "[35|check]>\n"
            "No more goals\n"
            "[36|check]>\n"
            "+ added lemma: `L'\n"
            "[37|check]>\n",
            encoding="utf-8",
        )
        buf = StringIO()
        with redirect_stdout(buf):
            assert handle_align(session, SimpleNamespace()) == 0
        out = buf.getvalue()
        assert "Proof is already complete" in out
        assert "NOT APPLICABLE" not in out

        gap = analyze_session(Path(td))
        assert "proof complete" in gap
        assert "Suggested tools" not in gap


def test_swap_bridge_and_call_subgoals_closed_goal_are_explicit() -> None:
    with tempfile.TemporaryDirectory() as td:
        session = open_session(Path(td))
        session.curr.write_text(
            "[35|check]>\n"
            "No more goals\n"
            "[36|check]>\n"
            "+ added lemma: `L'\n"
            "[37|check]>\n",
            encoding="utf-8",
        )

        buf = StringIO()
        with redirect_stdout(buf):
            assert handle_swap_search(
                session, SimpleNamespace(max_swap_attempts=20),
            ) == 0
        swap_out = buf.getvalue()
        assert "Proof is already complete" in swap_out
        assert "Current goal" not in swap_out

        bridge_out = analyze_bridge_lemmas_from_session(Path(td))
        assert "Proof is already complete" in bridge_out

        call_out = preview_from_session(Path(td), "={glob A}")
        assert "Proof is already complete" in call_out
        assert "daemon" not in call_out.lower()


def test_all_emitted_event_types_are_registered() -> None:
    """Guard against the ec_routing regression: every emit_event /
    emit_error_event / append_event with a STRING-LITERAL type must be in
    EVENT_PAYLOAD_SCHEMAS. An unregistered type trips event.unknown_type, which
    the fail-closed acceptance gate treats as fatal and SILENTLY REVERTS an
    EC-verified proof (every daemon-path commit emits `ec.routing`). This catches a
    new emit that forgets to register, at test time instead of in a wasted run."""
    import re
    from core.easycrypt.session_events import EVENT_PAYLOAD_SCHEMAS  # noqa: E402
    pats = [
        re.compile(r"""emit_event\(\s*["']([a-z][\w.]+)["']"""),
        re.compile(r"""emit_error_event\(\s*["']([a-z][\w.]+)["']"""),
        re.compile(r"""append_event\([^,()]+,\s*["']([a-z][\w.]+)["']"""),
    ]
    emitted: dict[str, str] = {}
    for base in ("core/easycrypt", "workflow"):
        for path in (ROOT / base).rglob("*.py"):
            text = path.read_text(encoding="utf-8", errors="replace")
            for pat in pats:
                for m in pat.finditer(text):
                    emitted.setdefault(m.group(1), str(path.relative_to(ROOT)))
    missing = {t: loc for t, loc in emitted.items() if t not in EVENT_PAYLOAD_SCHEMAS}
    assert not missing, (
        "Emitted event types missing from EVENT_PAYLOAD_SCHEMAS (would trip "
        "event.unknown_type and silently revert verified proofs): " + repr(missing)
    )
    # The exact types whose absence caused the daemon-routing regression:
    for required in ("ec.routing", "session.daemon_context_opened",
                     "session.daemon_context_open_failed"):
        assert required in EVENT_PAYLOAD_SCHEMAS, required


if __name__ == "__main__":
    test_append_event_jsonl_contract()
    test_candidate_closed_reader()
    test_event_summary_and_latest_error_helpers()
    test_validate_event_payload_schema()
    test_validate_event_stream_accepts_realistic_replay_flow()
    test_validate_event_stream_detects_pairing_and_fake_close()
    test_validate_event_stream_detects_tool_name_mismatch()
    test_proof_acceptance_gate_requires_valid_candidate_contract()
    test_proof_acceptance_gate_requires_verification_event()
    test_progress_session_state_closed_fallback()
    test_meta_command_refusal_emits_events_without_ec()
    test_raw_proof_control_refusal_emits_events_without_ec()
    test_closed_post_qed_prompt_is_goal_info_closed_state()
    test_session_state_extracts_latest_current_goal()
    test_session_state_default_previous_path_is_prev_out()
    test_infer_goal_count_handles_post_qed_added_lemma_prompt()
    test_closed_goal_json_has_no_tactic_suggestions()
    test_probability_goal_behind_implication_is_not_ambient()
    test_suggest_close_closed_state_has_no_tactic_suggestions()
    test_suggest_from_session_handles_post_qed_added_lemma_prompt()
    test_status_reports_closed_goal_as_complete_type()
    test_align_and_subgoal_gap_closed_goal_are_explicitly_closed()
    test_swap_bridge_and_call_subgoals_closed_goal_are_explicit()
    print("PASS test_session_events")
