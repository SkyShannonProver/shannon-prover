"""Contract tests for structured session event logging.

These tests are pure Python and do not start EasyCrypt. They validate the
append-only JSONL contract and one pre-EC session_cli path so the event
schema can be refactored safely before broader proof replay tests exist.
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]

import sys
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from core.easycrypt.session_api import open_session  # type: ignore  # noqa: E402
from core.easycrypt.session_events import (  # type: ignore  # noqa: E402
    append_event,
    event_payload,
    has_candidate_closed,
    make_event,
    read_events,
    summarize_events,
    validate_event,
    validate_event_stream,
)
from core.easycrypt.session_tactic_precheck import _strip_shell_filter_artifact  # type: ignore  # noqa: E402
from core.easycrypt.session_projection import read_proof_state_projection  # type: ignore  # noqa: E402
from workflow.progress import (  # noqa: E402
    _session_goal_state_text,
)
from workflow.proof_acceptance import (  # noqa: E402
    emit_workflow_verification_event,
    validate_acceptance_event_contract,
    validate_goal_discharge_contract,
)
from core.easycrypt.session_state import (  # type: ignore  # noqa: E402
    REMAINING_UNKNOWN,
    infer_goal_count,
    read_session_state,
)
from core.easycrypt.session_cli import main as session_cli_main  # type: ignore  # noqa: E402


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
        projection_candidate_ready = projection.goals_discharged
        projection_final_ready = projection.offline_verified
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
        or projection_status in {
            "goals_discharged_pending_qed",
            "session_closed_pending_verification",
            "verified",
        }
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
    (d / "current.out").write_text(
        "[1|check]>\nNo more goals\n[2|check]>\n",
        encoding="utf-8",
    )
    (d / "history.ec").write_text(tactic + "\n", encoding="utf-8")
    append_event(d, "session.started", {
        "file": None,
        "lemma": "L",
        "include_dirs": [],
        "discarded_tactic_count": 0,
        "restart_count": 1,
    })
    append_event(d, "tool.called", {
        "name": "commit",
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
        "name": "commit",
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


def test_retired_command_summary_event_is_a_contract_error() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        event = _event(d, "command.summary.produced", {})

        issues = validate_event(event)

        assert any(
            issue.code == "event.retired_type" and issue.severity == "error"
            for issue in issues
        )


def test_retired_agent_view_event_is_a_contract_error() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        event = _event(d, "agent.view.produced", {})

        issues = validate_event(event)

        assert any(
            issue.code == "event.retired_type" and issue.severity == "error"
            for issue in issues
        )


def test_retired_proof_context_view_event_is_a_contract_error() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        event = _event(d, "proof.context_view.produced", {})

        issues = validate_event(event)

        assert any(
            issue.code == "event.retired_type" and issue.severity == "error"
            for issue in issues
        )


def test_retired_commit_response_agent_view_link_is_a_contract_error() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        event = _event(d, "commit.response.produced", {
            "schema_version": 2,
            "ok": True,
            "command": "commit",
            "status": "ok",
            "artifact": str(d / "commit_response.json"),
            "response_hash": "a" * 40,
            "agent_view_artifact": str(d / "proof_context_view.json"),
        })

        issues = validate_event(event)

        assert any(
            issue.code == "event.payload.retired"
            and "agent_view_artifact" in issue.message
            for issue in issues
        )


def test_goal_discharge_reader_requires_current_projection_authority() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        gate = validate_goal_discharge_contract(d)
        assert not gate.ok
        assert not gate.goals_discharged
        assert not gate.session_completion_candidate
        append_event(d, "proof.candidate_closed", {"tactic": "qed."})
        gate = validate_goal_discharge_contract(d)
        assert not gate.ok
        assert not gate.goals_discharged
        assert not gate.session_completion_candidate
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        _append_minimal_closed_stream(d)
        gate = validate_goal_discharge_contract(d)
        assert gate.ok
        assert gate.goals_discharged
        assert gate.session_completion_candidate
        events = read_events(d)
        assert has_candidate_closed(events)


def test_candidate_close_event_must_be_adjacent_to_its_marked_result() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        _append_minimal_closed_stream(d)
        events = read_events(d)
        close_index = next(
            index
            for index, event in enumerate(events)
            if event["type"] == "proof.candidate_closed"
        )
        close = events.pop(close_index)
        events.append(close)

        validation = validate_event_stream(events)

        codes = {issue.code for issue in validation.errors}
        assert "stream.candidate_close.missing_adjacent_event" in codes
        assert "stream.candidate_close.no_paired_tactic_result" in codes


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
        latest = summary.recent_failed_attempts[0]
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
        assert [issue.code for issue in validate_event(diag_event)] == [
            "event.retired_type"
        ]

        preflight_event = _event(d, "tactic.preflight.produced", {
            "schema_version": 1,
            "kind": "exact_tactic_preflight",
            "ok": True,
            "artifact": str(d / "tactic_preflights" / "preflight.json"),
            "artifact_hash": "a" * 40,
            "proof_status": "open",
            "tactic_sha256": "b" * 64,
            "accepted": True,
            "verdict_known": True,
            "outcome_known": True,
            "error_count": 0,
        })
        assert validate_event(preflight_event) == []

        retired_view_event = _event(d, "tool.view.produced", {})
        assert [issue.code for issue in validate_event(retired_view_event)] == [
            "event.retired_type"
        ]

        workspace_event = _event(d, "prover.workspace_view.produced", {
            "schema_version": 2,
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
            "schema_version": 2,
            "ok": True,
            "command": "commit_chain",
            "status": "ok",
            "artifact": str(d / "commit_responses" / "commit_chain_deadbeef.json"),
            "response_hash": "c" * 40,
            "proof_status": "open",
            "attempted_count": 2,
            "accepted_count": 2,
            "failed_tactic": "",
            "error_count": 0,
            "warning_count": 0,
        })
        assert validate_event(commit_response_event) == []

        tactic_execution_event = _event(d, "tactic.execution.produced", {
            "schema_version": 1,
            "ok": True,
            "mode": "commit_chain",
            "command": "commit_chain",
            "status": "ok",
            "artifact": str(d / "tactic_execution_results" / "commit_chain.json"),
            "result_hash": "e" * 40,
            "accepted_count": 2,
            "rollback_count": 0,
            "failed_tactic": "",
            "state_changed": True,
            "history_committed": True,
            "workspace_artifact": str(d / "prover_workspace_views" / "view.json"),
            "workspace_chars": 2048,
            "current_goal_text_fully_shown": True,
            "current_goal_truncated": False,
            "commit_response_artifact": str(d / "commit_responses" / "chain.json"),
            "raw_result_artifact": str(d / "tactic_raw_results" / "commit_chain.txt"),
            "error_count": 0,
            "warning_count": 0,
        })
        assert validate_event(tactic_execution_event) == []

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
                "name": "commit",
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
                "name": "commit",
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
                "name": "commit",
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


def test_validate_event_stream_rejects_empty_close_tactic_identity() -> None:
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
            _event(d, "tactic.submitted", {
                "tactic": "done.",
                "history_lines_before": 0,
                "line_count": 1,
            }),
            _event(d, "tactic.result", {
                "tactic": "done.",
                "status": "ok",
                "history_committed": True,
                "candidate_closed": True,
            }),
            _event(d, "proof.candidate_closed", {
                "tactic": "",
                "goals_before": 1,
                "goals_after": 0,
                "no_more_goals": True,
                "async_check_close": False,
            }),
        ]

        result = validate_event_stream(events)

        assert "stream.candidate_close.empty_tactic" in [
            issue.code for issue in result.errors
        ]


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
        invalid = validate_goal_discharge_contract(d)
        assert not invalid.ok
        assert any("session" in err for err in invalid.errors)

    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        _append_minimal_closed_stream(d)
        valid = validate_goal_discharge_contract(d)
        assert valid.ok
        assert valid.goals_discharged
        assert valid.session_completion_candidate


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


def test_progress_goal_state_text_is_diagnostic_only() -> None:
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
        goal = _session_goal_state_text(str(d), ".ec_session_prover")
        assert "No current goal remains" in goal


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
        assert summary["projection_status"] == (
            "session_closed_pending_verification"
        )
        assert summary["projection_candidate_ready"] is True
        assert summary["remaining_goals"] == 0
        assert summary["projection_consistency_errors"] == []



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
        assert "`undo_last_step`" in out
        assert "session_cli" not in out
        events = read_events(Path(td))
        result_events = [
            event for event in events if event["type"] == "tactic.result"
        ]
        assert result_events[-1]["payload"]["status"] == "refused"
        assert result_events[-1]["payload"]["reason"] == "proof_control_command"
        assert result_events[-1]["payload"]["history_committed"] is False


def test_tactic_exec_is_counted_as_a_cli_action() -> None:
    with tempfile.TemporaryDirectory() as td:
        with patch(
            "core.easycrypt.commands.commit_commands.handle_tactic_exec",
            return_value=0,
        ):
            assert session_cli_main([
                "-d", td, "-tactic-exec", "undo",
            ]) == 0

        events = read_events(Path(td))
        assert [event["type"] for event in events] == [
            "tool.called",
            "tool.result",
        ]
        assert event_payload(events[0])["name"] == "undo"


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
    test_goal_discharge_reader_requires_current_projection_authority()
    test_event_summary_and_latest_error_helpers()
    test_validate_event_payload_schema()
    test_validate_event_stream_accepts_realistic_replay_flow()
    test_validate_event_stream_detects_pairing_and_fake_close()
    test_validate_event_stream_detects_tool_name_mismatch()
    test_proof_acceptance_gate_requires_valid_candidate_contract()
    test_proof_acceptance_gate_requires_verification_event()
    test_progress_goal_state_text_is_diagnostic_only()
    test_meta_command_refusal_emits_events_without_ec()
    test_raw_proof_control_refusal_emits_events_without_ec()
    test_tactic_exec_is_counted_as_a_cli_action()
    test_closed_post_qed_prompt_is_goal_info_closed_state()
    test_session_state_extracts_latest_current_goal()
    test_session_state_default_previous_path_is_prev_out()
    test_infer_goal_count_handles_post_qed_added_lemma_prompt()
    print("PASS test_session_events")
