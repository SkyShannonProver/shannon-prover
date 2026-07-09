"""Tests for the episode timeline views: the live session view and the
prover replay-root projection (merged from test_prover_episode_timeline.py)."""
from __future__ import annotations

import json
import tempfile
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace

import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from core.easycrypt.commands.session_commands import handle_episode_view  # type: ignore  # noqa: E402
from core.easycrypt.session_api import open_session  # type: ignore  # noqa: E402
from core.easycrypt.session_command_summary import write_command_summary_artifact  # type: ignore  # noqa: E402
from core.easycrypt.session_episode_timeline import (  # type: ignore  # noqa: E402
    build_session_episode_timeline,
    validate_session_episode_timeline,
)
from core.easycrypt.session_events import append_event, read_events  # type: ignore  # noqa: E402
from core.easycrypt.session_tactic_execution_result import (  # type: ignore  # noqa: E402
    write_tactic_execution_result_artifact,
)
from tests.helpers.builders import command_summary  # noqa: E402
from workflow.validation.prover_episode_timeline import (  # noqa: E402
    build_replay_root_timelines,
)


def _summary(
    *,
    tactic: str,
    transition_kind: str,
    proof_status: str = "open",
    goal_hash: str = "goal-a",
    primary_action: str = "try_tactic",
    num_remaining=1,
) -> dict:
    runnable = [{
        "id": "r0",
        "tactic": "sim.",
        "producer": "goal-parser",
        "confidence": "medium",
        "why": "parser",
        "source": "deterministic",
        "goal_hash": goal_hash,
    }] if primary_action == "try_tactic" else []
    return command_summary(
        tactic=tactic,
        transition_kind=transition_kind,
        proof_status=proof_status,
        goal_hash=goal_hash,
        primary_action=primary_action,
        num_remaining=num_remaining,
        final_ready=False,
        state_kind="open",
        current_goal_type="pRHL",
        preview="Current goal\n----\nx{1} = x{2}",
        runnable=runnable,
        recommendations=[],
        agent_view="/tmp/agent.json",
        commit_response="/tmp/commit.json",
        with_action_fields=False,
    )


def _append_summary(d: Path, summary: dict) -> None:
    payload = write_command_summary_artifact(d, summary)
    append_event(d, "command.summary.produced", payload)


def _write_root(summaries: list[dict]) -> Path:
    root = Path(tempfile.mkdtemp())
    proof_dir = root / "proof_A"
    proof_dir.mkdir()
    for summary in summaries:
        _append_summary(proof_dir, summary)
    replay_summary = {
        "proof_id": "proof_A",
        "file": "eval/examples/A.ec",
        "lemma": "A",
        "tactic_count": len(summaries),
        "replayed_tactic_count": len(summaries),
        "outcome": "PASS",
        "consistency_warnings": 0,
        "event_counts": {"command.summary.produced": len(summaries)},
        "artifact_dir": str(proof_dir),
        "session_dir": "/tmp/session-A",
        "runner": "inprocess",
        "full_hooks": False,
    }
    audit = {
        "warnings": [],
        "command_counts": {
            "next": len(summaries),
            "audit_tool": 0,
            "total": len(summaries),
        },
        "event_counts": {"command.summary.produced": len(summaries)},
        "proof_state": {"status": summaries[-1]["proof"]["status"]},
    }
    (proof_dir / "summary.json").write_text(
        json.dumps(replay_summary), encoding="utf-8",
    )
    (proof_dir / "audit_report.json").write_text(
        json.dumps(audit), encoding="utf-8",
    )
    (proof_dir / "commands.json").write_text(
        json.dumps([{"kind": "next"} for _ in summaries]), encoding="utf-8",
    )
    (root / "summary.json").write_text(
        json.dumps([replay_summary]), encoding="utf-8",
    )
    return root


def test_prover_episode_timeline_uses_event_order_and_rolls_up_steps() -> None:
    root = _write_root([
        _summary(
            tactic="wp.",
            transition_kind="state_changed_same_goal_count",
            goal_hash="goal-a",
            primary_action="try_tactic",
        ),
        _summary(
            tactic="sim.",
            transition_kind="closed",
            proof_status="candidate_closed",
            goal_hash="goal-b",
            primary_action="verify",
            num_remaining=0,
        ),
    ])

    report = build_replay_root_timelines(root)
    timeline = report["timelines"][0]
    steps = timeline["steps"]

    assert report["proof_count"] == 1
    assert report["step_count"] == 2
    assert [step["tactic"] for step in steps] == ["wp.", "sim."]
    assert steps[1]["goal_hash_changed"] is True
    assert "candidate_closed_verify_next" in steps[1]["prover_observations"]
    assert timeline["rollup"]["candidate_closed_step"] == 2
    assert timeline["rollup"]["final_primary_action"] == "verify"


def _execution(
    *,
    tactic: str,
    proof_status: str = "open",
    goal_hash: str = "goal-a",
    primary_category: str = "probe",
    num_remaining=1,
) -> dict:
    return {
        "schema_version": 1,
        "kind": "tactic_execution_result",
        "ok": True,
        "execution": {
            "mode": "commit",
            "command": "next",
            "submitted_tactics": [tactic],
            "attempted_count": 1,
            "accepted_count": 1,
            "rollback_count": 0,
            "state_changed": True,
            "history_committed": True,
            "steps": [{"index": 1, "tactic": tactic, "status": "accepted"}],
        },
        "result": {"ok": True, "status": "ok"},
        "workspace": {
            "view": {
                "current_goal": {
                    "goal_type": "pRHL" if proof_status == "open" else "complete",
                    "lines": ["Current goal", "----", "x{1} = x{2}"],
                    "text_fully_shown": True,
                },
                "proof_position": {
                    "status": proof_status,
                    "remaining_goals": num_remaining,
                    "remaining_goals_known": True,
                },
                "proof_frontier": {},
                "facts_and_gaps": {},
                "suggested_next_steps": {
                    "primary": {"category": primary_category},
                },
                "recent_diagnostics": {},
                "want_more_context": {},
            },
            "goal_chars": 32,
            "workspace_chars": 256,
        },
        "inspect_handles": [],
        "audit": {
            "proof_status": proof_status,
            "goal_hash": goal_hash,
            "goal_type": "pRHL" if proof_status == "open" else "complete",
            "num_remaining": num_remaining,
        },
        "notes": [],
        "errors": [],
    }


def _append_execution(d: Path, result: dict) -> None:
    payload = write_tactic_execution_result_artifact(d, result)
    append_event(d, "tactic.execution.produced", payload)


def test_session_episode_timeline_builds_live_view() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        _append_execution(d, _execution(
            tactic="wp.",
            goal_hash="goal-a",
            primary_category="probe",
        ))
        _append_execution(d, _execution(
            tactic="sim.",
            proof_status="candidate_closed",
            goal_hash="goal-b",
            primary_category="verify",
            num_remaining=0,
        ))

        timeline = build_session_episode_timeline(d)

        assert validate_session_episode_timeline(timeline).ok is True
        assert timeline["source"] == "tactic_execution_result"
        assert timeline["step_count"] == 2
        assert [s["tactic"] for s in timeline["steps"]] == ["wp.", "sim."]
        assert timeline["rollup"]["candidate_closed_step"] == 2
        assert timeline["rollup"]["final_primary_action"] == "verify"


def test_episode_view_handler_records_artifact_event() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        _append_execution(d, _execution(
            tactic="sim.",
            proof_status="candidate_closed",
            goal_hash="goal-b",
            primary_category="verify",
            num_remaining=0,
        ))
        session = open_session(d)
        buf = StringIO()
        with redirect_stdout(buf):
            assert handle_episode_view(session, SimpleNamespace()) == 0

        timeline = json.loads(buf.getvalue())
        assert timeline["kind"] == "session_episode_timeline"
        events = read_events(d)
        assert any(e.get("type") == "episode.timeline.produced" for e in events)
        assert list((d / "episode_timelines").glob("*.json"))


def main() -> int:
    test_prover_episode_timeline_uses_event_order_and_rolls_up_steps()
    test_session_episode_timeline_builds_live_view()
    test_episode_view_handler_records_artifact_event()
    print("PASS test_session_episode_timeline")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
