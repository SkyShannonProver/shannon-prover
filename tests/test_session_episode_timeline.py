"""Tests for the episode timeline views: the live session view and the
prover replay-root projection (merged from test_prover_episode_timeline.py)."""
from __future__ import annotations

import json
import tempfile
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from core.easycrypt.commands.session_commands import handle_episode_view  # type: ignore  # noqa: E402
from core.easycrypt.session_api import open_session  # type: ignore  # noqa: E402
from core.easycrypt.session_episode_timeline import (  # type: ignore  # noqa: E402
    build_session_episode_timeline,
    validate_session_episode_timeline,
)
from core.easycrypt.session_events import append_event, read_events  # type: ignore  # noqa: E402
from core.easycrypt.session_tactic_execution_result import (  # type: ignore  # noqa: E402
    write_tactic_execution_result_artifact,
)
from tests.helpers.builders import (  # noqa: E402
    append_bound_workspace_event,
    bind_tactic_execution_workspace,
    write_unchecked_tactic_execution_artifact,
)
from workflow.validation.prover_episode_timeline import (  # noqa: E402
    build_replay_root_timelines,
)


def _replay_execution(
    *,
    tactic: str,
    proof_status: str = "open",
    goal_hash: str = "goal-a",
    num_remaining=1,
) -> dict:
    return _execution(
        tactic=tactic,
        proof_status=proof_status,
        goal_hash=goal_hash,
        num_remaining=num_remaining,
    )


def _write_root(results: list[dict]) -> Path:
    root = Path(tempfile.mkdtemp())
    proof_dir = root / "proof_A"
    proof_dir.mkdir()
    for result in results:
        _append_execution(proof_dir, result)
    replay_summary = {
        "proof_id": "proof_A",
        "file": "eval/examples/A.ec",
        "lemma": "A",
        "tactic_count": len(results),
        "replayed_tactic_count": len(results),
        "outcome": "PASS",
        "consistency_warnings": 0,
        "event_counts": {"tactic.execution.produced": len(results)},
        "artifact_dir": str(proof_dir),
        "session_dir": "/tmp/session-A",
        "runner": "inprocess",
        "full_hooks": False,
    }
    audit = {
        "warnings": [],
        "command_counts": {
            "next": len(results),
            "audit_tool": 0,
            "total": len(results),
        },
        "event_counts": {"tactic.execution.produced": len(results)},
        "proof_state": {"status": results[-1]["audit"]["proof_status"]},
    }
    (proof_dir / "summary.json").write_text(
        json.dumps(replay_summary), encoding="utf-8",
    )
    (proof_dir / "audit_report.json").write_text(
        json.dumps(audit), encoding="utf-8",
    )
    (proof_dir / "commands.json").write_text(
        json.dumps([{"kind": "commit"} for _ in results]), encoding="utf-8",
    )
    (root / "summary.json").write_text(
        json.dumps([replay_summary]), encoding="utf-8",
    )
    return root


def test_prover_episode_timeline_uses_event_order_and_rolls_up_steps() -> None:
    root = _write_root([
        _replay_execution(
            tactic="wp.",
            goal_hash="goal-a",
        ),
        _replay_execution(
            tactic="sim.",
            proof_status="session_closed_pending_verification",
            goal_hash="goal-b",
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
    assert "session_closed_verify_next" in steps[1]["prover_observations"]
    assert timeline["rollup"]["session_completion_candidate_step"] == 2
    assert timeline["rollup"]["final_proof_status"] == "session_closed_pending_verification"


def _execution(
    *,
    tactic: str,
    proof_status: str = "open",
    goal_hash: str = "goal-a",
    num_remaining=1,
) -> dict:
    return {
        "schema_version": 1,
        "kind": "tactic_execution_result",
        "ok": True,
        "execution": {
            "mode": "commit",
            "command": "commit",
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
                "schema_version": 3,
                "kind": "prover_workspace_view",
                "ok": True,
                "last_result": {},
                "current_goal": {
                    "goal_type": "pRHL" if proof_status == "open" else "complete",
                    "lines": ["Current goal", "----", "x{1} = x{2}"],
                    "text_fully_shown": True,
                },
                "proof_status": {
                    "status": proof_status,
                    "remaining_goals": num_remaining,
                    "remaining_goals_known": True,
                    "goal_identity_required": proof_status == "open",
                    "goal_hash": goal_hash if proof_status == "open" else "",
                },
            },
            "goal_chars": 32,
            "workspace_chars": 256,
        },
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
    bind_tactic_execution_workspace(d, result)
    append_bound_workspace_event(d, result)
    payload = write_tactic_execution_result_artifact(d, result)
    append_event(d, "tactic.execution.produced", payload)


def _append_unchecked_execution(d: Path, result: dict) -> None:
    bind_tactic_execution_workspace(d, result)
    append_bound_workspace_event(d, result)
    payload = write_unchecked_tactic_execution_artifact(d, result)
    append_event(d, "tactic.execution.produced", payload)


def test_episode_timeline_rejects_superseded_v2_workspace_view() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        result = _execution(tactic="wp.")
        result["workspace"]["view"]["schema_version"] = 2
        _append_unchecked_execution(d, result)

        timeline = build_session_episode_timeline(d)

    assert timeline["ok"] is False
    assert timeline["steps"] == []
    assert any(
        "unsupported ProverWorkspaceView schema_version 2; expected 3"
        in error["message"]
        for error in timeline["errors"]
    )


def test_episode_timeline_rejects_unsupported_execution_envelope() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        result = _execution(tactic="wp.")
        result["schema_version"] = 0
        _append_unchecked_execution(d, result)

        timeline = build_session_episode_timeline(d)

    assert timeline["ok"] is False
    assert timeline["steps"] == []
    assert any(
        "schema_version must be 1, got 0" in error["message"]
        for error in timeline["errors"]
    )


def test_session_episode_timeline_builds_live_view() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        _append_execution(d, _execution(
            tactic="wp.",
            goal_hash="goal-a",
        ))
        _append_execution(d, _execution(
            tactic="sim.",
            proof_status="session_closed_pending_verification",
            goal_hash="goal-b",
            num_remaining=0,
        ))

        timeline = build_session_episode_timeline(d)

        assert validate_session_episode_timeline(timeline).ok is True
        assert timeline["source"] == "tactic_execution_result"
        assert timeline["step_count"] == 2
        assert [s["tactic"] for s in timeline["steps"]] == ["wp.", "sim."]
        assert timeline["rollup"]["session_completion_candidate_step"] == 2
        assert timeline["rollup"]["final_proof_status"] == "session_closed_pending_verification"


def test_episode_timeline_preserves_duplicate_artifact_event_occurrences() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        repeated = _execution(tactic="wp.")
        _append_execution(d, repeated)
        _append_execution(d, repeated)

        timeline = build_session_episode_timeline(d)

        assert timeline["step_count"] == 2
        assert [step["event_index"] for step in timeline["steps"]] == [2, 4]


def test_episode_timeline_treats_no_progress_as_guidance_not_failure() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        result = _execution(tactic="simplify.")
        result["ok"] = False
        result["execution"].update({
            "accepted_count": 0,
            "rollback_count": 1,
            "failed_tactic": "simplify.",
            "failure_reason": "no progress; state reverted",
            "state_changed": False,
            "history_committed": False,
            "steps": [{
                "index": 1,
                "tactic": "simplify.",
                "status": "no_progress",
            }],
        })
        result["result"] = {
            "ok": False,
            "status": "no_progress_reverted",
            "failure_reason": "no progress; state reverted",
        }
        _append_execution(d, result)

        timeline = build_session_episode_timeline(d)
        step = timeline["steps"][0]

        assert step["transition_kind"] == "no_progress"
        assert step["no_progress"] is True
        assert step["failed"] is False
        assert "failed_command_repair_next" not in step["prover_observations"]
        assert timeline["rollup"]["failed_command_count"] == 0


def test_episode_timeline_separates_discharged_goals_from_closed_candidate() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        _append_execution(d, _execution(
            tactic="sim.",
            proof_status="goals_discharged_pending_qed",
            num_remaining=0,
        ))

        timeline = build_session_episode_timeline(d)
        step = timeline["steps"][0]

        assert "goals_discharged_qed_next" in step["prover_observations"]
        assert step["goals_discharged"] is True
        assert step["session_completion_candidate"] is False
        assert timeline["rollup"]["goals_discharged_step"] == 1
        assert timeline["rollup"]["session_completion_candidate_step"] == 0
        assert any(
            note["code"]
            == "timeline.no_session_completion_candidate_step"
            for note in timeline["notes"]
        )


def test_episode_timeline_rejects_forged_execution_event_payload() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        _append_execution(d, _execution(tactic="wp."))
        events_path = d / "events.jsonl"
        events = read_events(d)
        event = next(
            item for item in events
            if item.get("type") == "tactic.execution.produced"
        )
        event["payload"]["result_hash"] = "0" * 40
        event["payload"]["status"] = "forged"
        events_path.write_text(
            "".join(json.dumps(item) + "\n" for item in events),
            encoding="utf-8",
        )

        timeline = build_session_episode_timeline(d)

        assert timeline["ok"] is False
        assert timeline["steps"] == []
        assert any(
            error["code"] == "session_episode_timeline.execution_event_binding"
            for error in timeline["errors"]
        )


def test_episode_timeline_does_not_use_orphan_for_unresolved_event() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        _append_execution(d, _execution(tactic="wp."))
        events_path = d / "events.jsonl"
        events = read_events(d)
        event = next(
            item for item in events
            if item.get("type") == "tactic.execution.produced"
        )
        event["payload"]["artifact"] = str(
            d / "tactic_execution_results" / "missing.json"
        )
        events_path.write_text(
            "".join(json.dumps(item) + "\n" for item in events),
            encoding="utf-8",
        )

        timeline = build_session_episode_timeline(d)

        assert timeline["ok"] is False
        assert timeline["steps"] == []
        assert {
            error["code"] for error in timeline["errors"]
        } >= {
            "session_episode_timeline.execution_event_artifact_mismatch",
            "session_episode_timeline.orphan_execution_artifact",
        }


def test_episode_view_handler_records_artifact_event() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        _append_execution(d, _execution(
            tactic="sim.",
            proof_status="session_closed_pending_verification",
            goal_hash="goal-b",
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


def test_episode_view_handler_fails_closed_when_recording_fails() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        session = open_session(d)
        with patch(
            "core.easycrypt.session_episode_timeline.record_session_episode_timeline",
            side_effect=RuntimeError("timeline write failed"),
        ):
            with pytest.raises(RuntimeError, match="timeline write failed"):
                handle_episode_view(session, SimpleNamespace())


def main() -> int:
    test_prover_episode_timeline_uses_event_order_and_rolls_up_steps()
    test_session_episode_timeline_builds_live_view()
    test_episode_view_handler_records_artifact_event()
    print("PASS test_session_episode_timeline")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
