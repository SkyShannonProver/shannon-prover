"""Tests for prover-facing replay UX audit rules."""
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
from workflow.validation.prover_ux_audit import audit_replay_root  # noqa: E402

# The canonical builder reproduces this file's original superset exactly.
_summary = command_summary


def _write_root(summary_payload: dict) -> Path:
    root = Path(tempfile.mkdtemp())
    proof_dir = root / "proof_A"
    proof_dir.mkdir()
    payload = write_command_summary_artifact(proof_dir, summary_payload)
    append_event(proof_dir, "command.summary.produced", payload)
    replay_summary = {
        "proof_id": "proof_A",
        "file": "eval/examples/A.ec",
        "lemma": "A",
        "tactic_count": 1,
        "replayed_tactic_count": 1,
        "outcome": "PASS",
        "consistency_warnings": 0,
        "event_counts": {"command.summary.produced": 1},
        "artifact_dir": str(proof_dir),
        "session_dir": "/tmp/session-A",
        "runner": "inprocess",
        "full_hooks": False,
    }
    audit = {
        "warnings": [],
        "command_counts": {"next": 1, "audit_tool": 0, "total": 1},
        "event_counts": {"command.summary.produced": 1},
        "proof_state": {"status": summary_payload["proof"]["status"]},
    }
    (proof_dir / "summary.json").write_text(
        json.dumps(replay_summary), encoding="utf-8",
    )
    (proof_dir / "audit_report.json").write_text(
        json.dumps(audit), encoding="utf-8",
    )
    (proof_dir / "commands.json").write_text(
        json.dumps([{"kind": "next"}]), encoding="utf-8",
    )
    (root / "summary.json").write_text(
        json.dumps([replay_summary]), encoding="utf-8",
    )
    return root


def test_prover_ux_audit_accepts_clean_open_summary() -> None:
    root = _write_root(_summary())
    report = audit_replay_root(root)
    assert report["ok"] is True
    assert report["command_summaries_checked"] == 1
    assert report["error_count"] == 0


def test_prover_ux_audit_rejects_placeholder_runnable_tactic() -> None:
    root = _write_root(_summary(
        runnable=[{
            "id": "bad",
            "tactic": "apply LEMMA.",
            "producer": "proof-diagnostics",
            "confidence": "low",
            "why": "placeholder",
            "source": "diagnostic",
            "goal_hash": "goal-hash",
        }],
        recommendations=[{
            "id": "bad",
            "kind": "tactic_candidate",
            "producer": "proof-diagnostics",
            "action": "apply LEMMA.",
            "why": "placeholder",
            "confidence": "low",
            "source": "diagnostic",
            "goal_hash": "goal-hash",
            "category": "runnable_tactic",
        }],
    ))
    codes = {issue["code"] for issue in audit_replay_root(root)["issues"]}
    assert "non_runnable_item_in_commit_actions" in codes


def test_prover_ux_audit_rejects_closed_state_suggestions() -> None:
    root = _write_root(_summary(
        proof_status="candidate_closed",
        primary_action="verify",
        runnable=[{
            "id": "bad",
            "tactic": "smt().",
            "producer": "goal-parser",
            "confidence": "medium",
            "why": "bad closed suggestion",
            "source": "deterministic",
            "goal_hash": "goal-hash",
        }],
    ))
    codes = {issue["code"] for issue in audit_replay_root(root)["issues"]}
    assert "closed_state_has_commit_actions" in codes


def test_prover_ux_audit_catches_phoare_bound_false_positive() -> None:
    root = _write_root(_summary(
        primary_action="consider_strategy_hint",
        runnable=[],
        recommendations=[{
            "id": "strategy",
            "kind": "strategy_hint",
            "producer": "proof-diagnostics",
            "action": "Use a failure-event bound with fel.",
            "why": "matched",
            "confidence": "medium",
            "source": "diagnostic",
            "goal_hash": "goal-hash",
            "category": "strategy_hint",
        }],
        strategy=[{
            "id": "strategy",
            "message": "Use a failure-event bound with fel.",
            "producer": "proof-diagnostics",
            "confidence": "medium",
            "why": "matched",
            "source": "diagnostic",
            "requires_instantiation": False,
        }],
        preview="Current goal\n----\nM.main [=] 1%r",
    ))
    codes = {issue["code"] for issue in audit_replay_root(root)["issues"]}
    assert "phoare_equality_bound_false_positive" in codes


def test_prover_ux_audit_requires_diagnose_for_failed_command() -> None:
    root = _write_root(_summary(
        ok=False,
        command_status="error",
        primary_action="try_tactic",
        failed_tactic="smt().",
        failure_reason="cannot prove",
    ))
    codes = {issue["code"] for issue in audit_replay_root(root)["issues"]}
    assert "failed_command_wrong_primary_action" in codes


if __name__ == "__main__":
    test_prover_ux_audit_accepts_clean_open_summary()
    test_prover_ux_audit_rejects_placeholder_runnable_tactic()
    test_prover_ux_audit_rejects_closed_state_suggestions()
    test_prover_ux_audit_catches_phoare_bound_false_positive()
    test_prover_ux_audit_requires_diagnose_for_failed_command()
    print("PASS test_prover_ux_audit")
