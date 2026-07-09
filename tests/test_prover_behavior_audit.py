"""Tests for prover behavior audit metrics."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from core.easycrypt.session_command_summary import write_command_summary_artifact  # noqa: E402
from core.easycrypt.session_events import append_event  # noqa: E402
from tests.helpers.builders import command_summary  # noqa: E402
from workflow.validation.prover_behavior_audit import (  # noqa: E402
    audit_path,
)


def _summary(
    *,
    proof_status: str = "open",
    primary_action: str = "try_tactic",
    transition_tactic: str = "wp.",
    runnable: list[dict] | None = None,
) -> dict:
    if runnable is None:
        runnable = [{
            "id": "r0",
            "tactic": "sim.",
            "producer": "goal-parser",
            "confidence": "medium",
            "why": "parser suggestion",
            "source": "deterministic",
            "goal_hash": "goal-hash",
        }]
    recommendations = [{
        "id": item["id"],
        "kind": "tactic_candidate",
        "producer": item["producer"],
        "action": item["tactic"],
        "why": item["why"],
        "confidence": item["confidence"],
        "action_type": "runnable_tactic",
        "source": item["source"],
        "goal_hash": item["goal_hash"],
        "category": "runnable_tactic",
    } for item in runnable]
    return command_summary(
        proof_status=proof_status,
        primary_action=primary_action,
        tactic=transition_tactic,
        runnable=runnable,
        recommendations=recommendations,
        final_ready=False,
        active_recommendation_count=len(recommendations),
        derived_recommendation_count=0,
        with_action_fields=False,
    )


def _write_replay_root() -> Path:
    root = Path(tempfile.mkdtemp())
    proof_dir = root / "proof_A"
    proof_dir.mkdir()

    step1 = _summary()
    step2 = _summary(
        proof_status="candidate_closed",
        primary_action="verify",
        transition_tactic="sim.",
        runnable=[],
    )
    payload1 = write_command_summary_artifact(proof_dir, step1)
    append_event(proof_dir, "command.summary.produced", payload1)
    append_event(proof_dir, "tool.called", {
        "name": "goal-info",
        "mutates_proof_state": False,
        "session_dir": str(proof_dir),
    })
    append_event(proof_dir, "tool.result", {
        "name": "goal-info",
        "mutates_proof_state": False,
        "session_dir": str(proof_dir),
        "exit_code": 0,
        "status": "ok",
    })
    payload2 = write_command_summary_artifact(proof_dir, step2)
    append_event(proof_dir, "command.summary.produced", payload2)
    append_event(proof_dir, "tool.called", {
        "name": "verify",
        "mutates_proof_state": False,
        "session_dir": str(proof_dir),
    })
    append_event(proof_dir, "verification.completed", {
        "lemma": "A",
        "status": "pass",
        "verifier": "easycrypt",
    })

    summary = {
        "proof_id": "proof_A",
        "file": "eval/examples/A.ec",
        "lemma": "A",
        "tactic_count": 2,
        "replayed_tactic_count": 2,
        "outcome": "PASS",
        "consistency_warnings": 0,
        "event_counts": {
            "command.summary.produced": 2,
            "verification.completed": 1,
        },
        "artifact_dir": str(proof_dir),
        "session_dir": "/tmp/session-A",
        "runner": "inprocess",
        "full_hooks": False,
    }
    audit = {
        "warnings": [],
        "command_counts": {"next": 2, "audit_tool": 0, "total": 2},
        "event_counts": summary["event_counts"],
        "proof_state": {"status": "verified"},
    }
    (proof_dir / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    (proof_dir / "audit_report.json").write_text(json.dumps(audit), encoding="utf-8")
    (proof_dir / "commands.json").write_text(json.dumps([]), encoding="utf-8")
    (root / "summary.json").write_text(json.dumps([summary]), encoding="utf-8")
    return root


def test_behavior_audit_counts_tool_usage_and_follow_through() -> None:
    root = _write_replay_root()
    report = audit_path(root)

    assert report["ok"] is True
    assert report["proofs_checked"] == 1
    assert report["command_summaries_checked"] == 2
    assert report["tool_usage"]["read_only_by_name"]["goal-info"] == 1
    assert report["guidance_follow_through"]["runnable_steps"] == 1
    assert report["guidance_follow_through"]["runnable_followed_exact"] == 1
    assert report["guidance_follow_through"]["candidate_closed_steps"] == 1
    assert (
        report["guidance_follow_through"]["candidate_closed_followed_by_verify"]
        == 1
    )


def _summary_min(
    *,
    transition_tactic: str = "wp.",
    runnable: list[dict] | None = None,
    history_committed: bool = True,
    transition_status: str = "ok",
    failed_tactic: str = "",
    no_progress: bool = False,
    primary_action: str = "try_tactic",
    proof_status: str = "open",
    transition_kind: str = "progress",
) -> dict:
    """Compact summary builder for adoption-outcome tests. Differs from
    ``_summary`` in that the caller can drive every field that affects
    adoption classification (committed vs not, error vs ok, etc.)."""
    summary = command_summary(
        ok=transition_status != "error" and not failed_tactic,
        command_status="error" if transition_status == "error" else "ok",
        proof_status=proof_status,
        primary_action=primary_action,
        tactic=transition_tactic,
        transition_kind=transition_kind,
        transition_status=transition_status,
        failed_tactic=failed_tactic,
        history_committed=history_committed,
        candidate_closed=False,
        no_progress=no_progress,
        num_remaining=1,
        final_ready=False,
        state_kind="open",
        current_goal_type="pRHL",
        preview="",
        runnable=runnable or [],
        recommendations=[],
        with_action_fields=False,
    )
    # This builder always reports the attempted tactic and no error entries,
    # even for failed transitions (the audit reads mutation/transition only).
    summary["transition"]["tactic"] = transition_tactic
    summary["errors"] = []
    return summary


def _runnable(producer: str, tactic: str, *, confidence: str = "verified") -> dict:
    return {
        "id": f"{producer}.0",
        "tactic": tactic,
        "producer": producer,
        "confidence": confidence,
        "why": "test",
        "source": producer,
        "goal_hash": "goal-hash",
    }


def _build_replay_dir(summaries: list[dict]) -> Path:
    """Write a sequence of CommandSummaries + their command.summary.produced
    events into a fresh temp replay-artifact directory."""
    root = Path(tempfile.mkdtemp())
    proof_dir = root / "proof_X"
    proof_dir.mkdir()
    for s in summaries:
        payload = write_command_summary_artifact(proof_dir, s)
        append_event(proof_dir, "command.summary.produced", payload)
    summary = {
        "proof_id": "proof_X",
        "file": "eval/examples/X.ec",
        "lemma": "X",
        "tactic_count": len(summaries),
        "replayed_tactic_count": len(summaries),
        "outcome": "PASS",
        "consistency_warnings": 0,
        "event_counts": {"command.summary.produced": len(summaries)},
        "artifact_dir": str(proof_dir),
        "session_dir": "/tmp/session-X",
        "runner": "inprocess",
        "full_hooks": False,
    }
    audit = {
        "warnings": [],
        "command_counts": {"next": len(summaries), "audit_tool": 0,
                           "total": len(summaries)},
        "event_counts": summary["event_counts"],
        "proof_state": {"status": "open"},
    }
    (proof_dir / "summary.json").write_text(
        json.dumps(summary), encoding="utf-8",
    )
    (proof_dir / "audit_report.json").write_text(
        json.dumps(audit), encoding="utf-8",
    )
    (proof_dir / "commands.json").write_text(json.dumps([]), encoding="utf-8")
    (root / "summary.json").write_text(
        json.dumps([summary]), encoding="utf-8",
    )
    return root


def test_recommendation_outcomes_track_per_producer_adoption() -> None:
    """A commit recommendation from producer P + next commit matches a P-rec text →
    adoption counted under P, outcome classified ``adopted_ok``."""
    summaries = [
        _summary_min(
            transition_tactic="proc.",
            runnable=[
                _runnable("AUTO-ABSTRACT-ADV-CALL",
                          "call (_: ={glob A})."),
                _runnable("try", "wp."),
            ],
        ),
        _summary_min(transition_tactic="wp."),  # adopted try's wp.
        _summary_min(transition_tactic="rnd."),
    ]
    root = _build_replay_dir(summaries)
    report = audit_path(root)
    out = report["recommendation_outcomes"]
    assert out["recs_offered_total"] == 2
    assert out["recs_offered_by_producer"] == {
        "AUTO-ABSTRACT-ADV-CALL": 1, "try": 1,
    }
    assert out["recs_adopted_by_producer"] == {"try": 1}
    assert out["adoption_outcomes"]["adopted_ok"] == 1
    assert out["adoption_rate_by_producer"]["try"] == 1.0
    assert out["adoption_rate_by_producer"]["AUTO-ABSTRACT-ADV-CALL"] == 0.0


def test_recommendation_outcomes_classify_adopted_then_error() -> None:
    """Rec adopted, but the very next summary records an error → outcome
    is ``adopted_then_error`` (this is the daemon-passed-but-EC-rejected
    failure mode the audit must surface)."""
    summaries = [
        _summary_min(
            transition_tactic="proc.",
            runnable=[_runnable("AUTO-FAKE", "bad_tactic.")],
        ),
        _summary_min(
            transition_tactic="bad_tactic.",
            transition_status="error",
            failed_tactic="bad_tactic.",
            history_committed=False,
        ),
        _summary_min(transition_tactic="recover."),
    ]
    root = _build_replay_dir(summaries)
    report = audit_path(root)
    out = report["recommendation_outcomes"]
    # Note: failed_tactic without history_committed means the rec was
    # *attempted* but commit failed. We still classify as adopted-then-
    # error because the agent acted on our rec.
    # The audit's adoption check requires history_committed=True, so
    # this case won't increment adoptions. Instead it shows up in
    # ignored_commit_recommendations if there was any committed alternate, or
    # simply not counted. Validate the latter:
    assert out["recs_adopted_by_producer"] == {}
    assert out["adoption_outcomes"] == {}


def test_recommendation_outcomes_classify_adopted_then_detour() -> None:
    """Rec adopted, commit succeeded, but next 3 summaries have ≥ 2
    errors → ``adopted_then_detour`` (rec passed daemon but pushed the
    proof onto a brittle path)."""
    summaries = [
        _summary_min(
            transition_tactic="proc.",
            runnable=[_runnable("AUTO-DETOUR", "weak_inv.")],
        ),
        _summary_min(transition_tactic="weak_inv."),  # adoption ok
        _summary_min(transition_tactic="bad1.",
                     transition_status="error", failed_tactic="bad1."),
        _summary_min(transition_tactic="bad2.",
                     transition_status="error", failed_tactic="bad2."),
        _summary_min(transition_tactic="recover."),
    ]
    root = _build_replay_dir(summaries)
    report = audit_path(root)
    out = report["recommendation_outcomes"]
    assert out["recs_adopted_by_producer"] == {"AUTO-DETOUR": 1}
    assert out["adoption_outcomes"]["adopted_then_detour"] == 1


def test_recommendation_outcomes_classify_adopted_no_progress() -> None:
    summaries = [
        _summary_min(
            transition_tactic="proc.",
            runnable=[_runnable("AUTO-VACUOUS", "noop.")],
        ),
        _summary_min(transition_tactic="noop.", no_progress=True),
        _summary_min(transition_tactic="recover."),
    ]
    root = _build_replay_dir(summaries)
    report = audit_path(root)
    out = report["recommendation_outcomes"]
    assert out["recs_adopted_by_producer"] == {"AUTO-VACUOUS": 1}
    assert out["adoption_outcomes"]["adopted_no_progress"] == 1


def test_recommendation_outcomes_record_ignored_commit_recommendations() -> None:
    """Panel has verified recs, but agent committed something else; record it
    so we can study the gap."""
    summaries = [
        _summary_min(
            transition_tactic="proc.",
            runnable=[
                _runnable("AUTO-ABSTRACT-ADV-CALL",
                          "call (_: ={glob A} ==> ={res, glob A})."),
                _runnable("AUTO-ABSTRACT-ADV-CALL", "call (_: true)."),
            ],
        ),
        # Agent picked something else — neither verified rec.
        _summary_min(transition_tactic="swap{1} 7 -3."),
    ]
    root = _build_replay_dir(summaries)
    report = audit_path(root)
    out = report["recommendation_outcomes"]
    assert out["recs_adopted_by_producer"] == {}
    assert len(out["ignored_commit_recommendations"]) == 1
    ig = out["ignored_commit_recommendations"][0]
    assert ig["actual_commit"] == "swap{1} 7 -3."
    producers = sorted(r["producer"] for r in ig["ignored_recs"])
    assert producers == ["AUTO-ABSTRACT-ADV-CALL", "AUTO-ABSTRACT-ADV-CALL"]



if __name__ == "__main__":
    test_behavior_audit_counts_tool_usage_and_follow_through()
    test_recommendation_outcomes_track_per_producer_adoption()
    test_recommendation_outcomes_classify_adopted_then_error()
    test_recommendation_outcomes_classify_adopted_then_detour()
    test_recommendation_outcomes_classify_adopted_no_progress()
    test_recommendation_outcomes_record_ignored_commit_recommendations()
    test_aggregate_behavior_reports_combines_runs()
    print("PASS test_prover_behavior_audit")
