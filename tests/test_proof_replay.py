"""Pure-Python tests for proof replay audit consistency checks."""
from __future__ import annotations

import sys
import tempfile
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from core.easycrypt.session_events import append_event, make_event  # noqa: E402
from core.easycrypt.session_agent_view import write_proof_context_view_artifact  # noqa: E402
from core.easycrypt.session_commit_response import write_commit_response_artifact  # noqa: E402
from core.easycrypt.session_episode_timeline import (  # noqa: E402
    write_session_episode_timeline_artifact,
)
from core.easycrypt.session_prover_workspace_view import (  # noqa: E402
    write_prover_workspace_view_artifact,
)
from core.easycrypt.session_tool_view import (  # noqa: E402
    make_tool_view,
    write_tool_view_artifact,
)
from workflow.validation.proof_replay import (  # noqa: E402
    _audit_agent_view_events,
    _audit_agent_views,
    _audit_commit_response_events,
    _audit_episode_timeline_events,
    _audit_episode_timelines,
    _audit_structured_diagnostics,
    _audit_tool_view_events,
    _audit_tool_views,
    _build_consistency_report,
)
from workflow.validation.replay_artifacts import (  # noqa: E402
    iter_replay_artifacts,
    load_replay_artifact,
    load_root_summaries,
)


def test_consistency_accepts_session_cli_bang_normalization() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        tactic_from_command = r"rewrite log_bij \!(loggK, logDr)."
        tactic_from_session = "rewrite log_bij !(loggK, logDr)."
        commands = [
            {
                "kind": "next",
                "step": 1,
                "rc": 0,
                "tactic": tactic_from_command,
                "stdout": "",
                "stderr": "",
            }
        ]
        events = [
            make_event(d, "session.started", {
                "file": str(d / "proof.ec"),
                "lemma": "L",
                "include_dirs": [],
                "discarded_tactic_count": 0,
                "restart_count": 1,
            }),
            make_event(d, "tool.called", {
                "name": "start",
                "mutates_proof_state": True,
                "session_dir": str(d.resolve()),
            }),
            make_event(d, "tool.result", {
                "name": "start",
                "mutates_proof_state": True,
                "session_dir": str(d.resolve()),
                "exit_code": 0,
                "status": "ok",
            }),
            make_event(d, "tool.called", {
                "name": "next",
                "mutates_proof_state": True,
                "session_dir": str(d.resolve()),
            }),
            make_event(d, "tactic.submitted", {
                "tactic": tactic_from_session,
                "history_lines_before": 0,
                "line_count": 1,
            }),
            make_event(d, "goal.changed", {
                "tactic": tactic_from_session,
                "goals_before": 1,
                "goals_after": 0,
                "no_more_goals": True,
                "async_check_close": False,
                "no_progress": False,
                "candidate_closed": True,
            }),
            make_event(d, "tactic.result", {
                "tactic": tactic_from_session,
                "status": "ok",
                "history_committed": True,
                "candidate_closed": True,
            }),
            make_event(d, "proof.candidate_closed", {
                "tactic": tactic_from_session,
                "goals_before": 1,
                "goals_after": 0,
                "no_more_goals": True,
                "async_check_close": False,
            }),
            make_event(d, "tool.result", {
                "name": "next",
                "mutates_proof_state": True,
                "session_dir": str(d.resolve()),
                "exit_code": 0,
                "status": "ok",
            }),
            make_event(d, "tool.called", {
                "name": "verify",
                "mutates_proof_state": False,
                "session_dir": str(d.resolve()),
            }),
            make_event(d, "verification.completed", {
                "lemma": "L",
                "status": "pass",
                "verifier": "easycrypt",
            }),
            make_event(d, "tool.result", {
                "name": "verify",
                "mutates_proof_state": False,
                "session_dir": str(d.resolve()),
                "exit_code": 0,
                "status": "ok",
            }),
        ]

        (d / "events.jsonl").write_text(
            "\n".join(json.dumps(event) for event in events) + "\n",
            encoding="utf-8",
        )
        (d / "current.out").write_text(
            "[1|check]>\nNo more goals\n[2|check]>\n",
            encoding="utf-8",
        )
        (d / "history.ec").write_text(
            tactic_from_session + "\n",
            encoding="utf-8",
        )

        report = _build_consistency_report(commands, events, "PASS", d)
        assert report["warnings"] == []
        assert report["event_contract_errors"] == 0
        assert report["proof_state"]["final_ready"] is True


def test_replay_artifact_typed_reader() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        proof_dir = root / "proof_A"
        proof_dir.mkdir()
        summary = {
            "proof_id": "proof_A",
            "file": "eval/examples/A.ec",
            "lemma": "A",
            "tactic_count": 1,
            "replayed_tactic_count": 1,
            "outcome": "PASS",
            "consistency_warnings": 0,
            "event_counts": {
                "proof.candidate_closed": 1,
                "verification.completed": 1,
            },
            "artifact_dir": str(proof_dir),
            "session_dir": "/tmp/session-A",
            "runner": "inprocess",
            "full_hooks": False,
        }
        audit = {
            "warnings": [],
            "tool_view_checked": 2,
            "tool_view_errors": 0,
            "tool_view_warnings": 0,
            "event_counts": summary["event_counts"],
            "command_counts": {"next": 1, "audit_tool": 2, "total": 3},
            "tactic_status_counts": {"ok": 1},
            "closed_text_steps": [1],
            "candidate_closed_events": 1,
            "verification_status": "pass",
            "failed_next": [],
            "proof_state": {"status": "verified", "final_ready": True},
        }
        (proof_dir / "summary.json").write_text(
            json.dumps(summary), encoding="utf-8",
        )
        (proof_dir / "audit_report.json").write_text(
            json.dumps(audit), encoding="utf-8",
        )
        (proof_dir / "commands.json").write_text(
            json.dumps([{"kind": "next"}]), encoding="utf-8",
        )
        append_event(proof_dir, "proof.candidate_closed", {"tactic": "qed."})
        (root / "summary.json").write_text(
            json.dumps([summary]), encoding="utf-8",
        )

        artifact = load_replay_artifact(proof_dir)
        assert artifact.ok
        assert artifact.summary.lemma == "A"
        assert artifact.audit_report.audit_tool_calls == 2
        assert artifact.audit_report.tool_view_checked == 2
        assert artifact.audit_report.tool_view_errors == 0
        assert artifact.audit_report.proof_state["status"] == "verified"
        assert len(artifact.commands) == 1
        assert len(artifact.events) == 1

        summaries = load_root_summaries(root)
        assert summaries[0].proof_id == "proof_A"
        assert list(iter_replay_artifacts(root))[0].proof_dir == proof_dir


def test_tool_view_audit_validates_goal_info_envelope() -> None:
    valid_view = make_tool_view(
        tool="goal-info",
        proof_state={"status": "open"},
    ).to_dict()
    valid = _audit_tool_views([{
        "kind": "audit_tool",
        "step": 1,
        "tool": "goal-info",
        "stdout": (
            "[AUTO-LEMMA-HINTS] text with EasyCrypt memory refs ={glob A}\n"
            + json.dumps({"tool_view": valid_view}) + "\n"
        ),
    }])
    assert valid["checked"] == 1
    assert valid["errors"] == []

    closed_bad = make_tool_view(
        tool="goal-info",
        proof_state={"status": "candidate_closed"},
        recommendations=[{
            "id": "bad",
            "kind": "tactic",
            "producer": "test",
            "action": "smt().",
            "why": "bad",
            "confidence": "low",
        }],
    ).to_dict()
    invalid = _audit_tool_views([{
        "kind": "audit_tool",
        "step": 2,
        "tool": "goal-info",
        "stdout": json.dumps({"tool_view": closed_bad}),
    }])
    assert invalid["checked"] == 1
    assert any("closed proof_state" in err for err in invalid["errors"])


def test_tool_view_event_audit_validates_artifact_hash() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        view = make_tool_view(
            tool="status",
            proof_state={"status": "open"},
        ).to_dict()
        payload = write_tool_view_artifact(d, view)
        events = [make_event(d, "tool.view.produced", payload)]

        ok = _audit_tool_view_events(events)
        assert ok["checked"] == 1
        assert ok["errors"] == []

        bad_payload = dict(payload)
        bad_payload["view_hash"] = "b" * 40
        bad = _audit_tool_view_events([
            make_event(d, "tool.view.produced", bad_payload)
        ])
        assert any("view_hash" in err for err in bad["errors"])


def test_agent_view_audit_validates_artifact_hash_and_stdout() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        view = {
            "schema_version": 1,
            "kind": "proof_context_view",
            "ok": True,
            "proof_state": {
                "status": "open",
                "goal": {"active_goal_hash": "goal-hash"},
            },
            "current_goal": {"active_goal_hash": "goal-hash"},
            "latest_transition": {},
            "guidance": {
                "recommendations": [],
                "stale_recommendations": [],
                "stale_recommendation_count": 0,
            },
            "evidence": {},
            "latest_errors": [],
            "safe_next_actions": [],
            "actions": [],
            "notes": [],
            "errors": [],
            "debug_refs": {},
        }
        payload = write_proof_context_view_artifact(d, view)
        events = [make_event(d, "agent.view.produced", payload)]

        ok = _audit_agent_view_events(events)
        assert ok["checked"] == 1
        assert ok["errors"] == []

        bad_payload = dict(payload)
        bad_payload["view_hash"] = "c" * 40
        bad = _audit_agent_view_events([
            make_event(d, "agent.view.produced", bad_payload)
        ])
        assert any("view_hash" in err for err in bad["errors"])

        stdout = _audit_agent_views([{
            "kind": "audit_tool",
            "step": 1,
            "tool": "agent-view",
            "stdout": json.dumps({
                "schema_version": 2,
                "kind": "prover_workspace_view",
                "ok": True,
                "last_result": {},
                "proof_status": {},
                "current_goal": {},
                "program_frontier": {},
                "application_context": {},
                "facts_and_diagnostics": {},
                "candidate_moves": {},
                "inspect_lookup_handles": {},
            }),
        }])
        assert stdout["checked"] == 1
        assert stdout["errors"] == []


def test_prover_workspace_view_audit_rejects_backend_leaks() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        view = {
            "schema_version": 2,
            "kind": "prover_workspace_view",
            "ok": True,
            "last_result": {},
            "proof_status": {"status": "open"},
            "current_goal": {},
            "program_frontier": {},
            "application_context": {},
            "facts_and_diagnostics": {},
            "candidate_moves": {},
            "inspect_lookup_handles": {},
        }
        payload = write_prover_workspace_view_artifact(d, view)
        events = [make_event(d, "prover.workspace_view.produced", payload)]

        ok = _audit_agent_view_events(events)
        assert ok["checked"] == 1
        assert ok["errors"] == []

        leaked_stdout = _audit_agent_views([{
            "kind": "audit_tool",
            "step": 2,
            "tool": "agent-view",
            "stdout": json.dumps({
                **view,
                "debug_cli_fallback": {
                    "command": "python3 core/easycrypt/session_cli.py -agent-view",
                },
            }),
        }])
        assert leaked_stdout["checked"] == 1
        assert any("forbidden key" in err for err in leaked_stdout["errors"])


def test_commit_response_audit_validates_artifact_hash() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        response = {
            "schema_version": 1,
            "kind": "commit_response",
            "ok": True,
            "command": "chain",
            "status": "ok",
            "proof_state": {"status": "open"},
            "latest_transition": {},
            "mutation": {
                "attempted_count": 1,
                "accepted_count": 1,
                "attempted_tactics": ["smt()."],
                "failed_tactic": "",
                "failure_reason": "",
                "keep_on_fail": False,
                "rollback_count": 0,
            },
            "agent_view": {},
            "notes": [],
            "errors": [],
            "debug": {},
        }
        payload = write_commit_response_artifact(d, response)
        ok = _audit_commit_response_events([
            make_event(d, "commit.response.produced", payload)
        ])
        assert ok["checked"] == 1
        assert ok["errors"] == []

        bad_payload = dict(payload)
        bad_payload["response_hash"] = "d" * 40
        bad = _audit_commit_response_events([
            make_event(d, "commit.response.produced", bad_payload)
        ])
        assert any("response_hash" in err for err in bad["errors"])


def test_episode_timeline_audit_validates_artifact_hash_and_stdout() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        timeline = {
            "schema_version": 1,
            "kind": "session_episode_timeline",
            "ok": True,
            "session_dir": str(d),
            "step_count": 1,
            "rollup": {
                "transition_counts": {"closed": 1},
                "primary_action_counts": {"verify": 1},
                "proof_status_counts": {"candidate_closed": 1},
                "failed_command_count": 0,
                "no_progress_count": 0,
                "goal_hash_change_count": 0,
                "candidate_closed_step": 1,
                "final_primary_action": "verify",
                "final_proof_status": "candidate_closed",
            },
            "steps": [{
                "step": 1,
                "command": "next",
                "command_status": "ok",
                "ok": True,
                "tactic": "sim.",
                "proof_status": "candidate_closed",
                "transition_kind": "closed",
                "primary_action": "verify",
                "prover_observations": ["candidate_closed_verify_next"],
            }],
            "notes": [],
            "errors": [],
        }
        payload = write_session_episode_timeline_artifact(d, timeline)
        ok = _audit_episode_timeline_events([
            make_event(d, "episode.timeline.produced", payload)
        ])
        assert ok["checked"] == 1
        assert ok["errors"] == []

        bad_payload = dict(payload)
        bad_payload["timeline_hash"] = "e" * 40
        bad = _audit_episode_timeline_events([
            make_event(d, "episode.timeline.produced", bad_payload)
        ])
        assert any("timeline_hash" in err for err in bad["errors"])

        stdout = _audit_episode_timelines([{
            "kind": "audit_tool",
            "step": 1,
            "tool": "episode-view",
            "stdout": json.dumps(timeline),
        }])
        assert stdout["checked"] == 1
        assert stdout["errors"] == []


def test_structured_diagnostic_audit_validates_recommendations() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        good = make_event(d, "diagnostic.emitted", {
            "source": "auto_pivot",
            "layer": 3,
            "suppress_error": False,
            "request_rollback": False,
            "text": "[AUTO-PIVOT]",
            "kind": "recommendation",
            "recommendations": [{
                "id": "auto_pivot.0",
                "kind": "pivot_tactic",
                "producer": "AUTO-PIVOT",
                "action": "apply prD4.",
                "why": "pivot matched",
                "confidence": "medium",
                "preconditions": [],
                "source_refs": [],
                "evidence_refs": ["deterministic.auto_pivot.0"],
                "metadata": {},
            }],
            "evidence": {
                "deterministic": [{
                    "id": "deterministic.auto_pivot.0",
                    "producer": "pivot_applicability",
                }],
            },
        })
        ok = _audit_structured_diagnostics([good])
        assert ok["checked"] == 1
        assert ok["errors"] == []

        bad = make_event(d, "diagnostic.emitted", {
            "source": "auto_pivot",
            "layer": 3,
            "suppress_error": False,
            "request_rollback": False,
            "text": "[AUTO-PIVOT]",
            "kind": "recommendation",
            "recommendations": [{"id": "bad"}],
            "evidence": [],
        })
        failed = _audit_structured_diagnostics([bad])
        assert failed["checked"] == 1
        assert any("missing action" in err for err in failed["errors"])
        assert any("evidence must be an object" in err for err in failed["errors"])


if __name__ == "__main__":
    test_consistency_accepts_session_cli_bang_normalization()
    test_replay_artifact_typed_reader()
    test_tool_view_audit_validates_goal_info_envelope()
    test_tool_view_event_audit_validates_artifact_hash()
    test_agent_view_audit_validates_artifact_hash_and_stdout()
    test_commit_response_audit_validates_artifact_hash()
    test_episode_timeline_audit_validates_artifact_hash_and_stdout()
    test_structured_diagnostic_audit_validates_recommendations()
    print("PASS test_proof_replay")
