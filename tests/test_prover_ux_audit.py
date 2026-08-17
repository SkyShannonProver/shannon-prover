"""Tests for prover-facing replay UX audit rules."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from core.easycrypt.session_events import append_event  # noqa: E402
from core.easycrypt.session_commit_response import (  # noqa: E402
    write_commit_response_artifact,
)
from core.easycrypt.session_tactic_execution_result import (  # noqa: E402
    write_tactic_execution_result_artifact,
)
from tests.helpers.builders import (  # noqa: E402
    append_bound_workspace_event,
    bind_tactic_execution_workspace,
    write_unchecked_tactic_execution_artifact,
)
from workflow.validation.prover_ux_audit import audit_replay_root  # noqa: E402


def _tactic_execution(
    *,
    proof_status: str = "open",
    goal_lines: list[str] | None = None,
    ok: bool = True,
    failed_tactic: str = "",
    failure_reason: str = "",
    workspace_schema_version: int = 3,
) -> dict:
    if goal_lines is None:
        goal_lines = ["Current goal", "x = y"]
    remaining = 1 if proof_status == "open" else 0
    return {
        "schema_version": 1,
        "kind": "tactic_execution_result",
        "ok": ok,
        "execution": {
            "mode": "commit",
            "command": "commit",
            "submitted_tactics": [failed_tactic or "wp."],
            "attempted_count": 1,
            "accepted_count": 1 if ok else 0,
            "rollback_count": 0,
            "failed_tactic": failed_tactic,
            "failure_reason": failure_reason,
            "state_changed": ok,
            "history_committed": ok,
            "steps": [{
                "index": 1,
                "tactic": failed_tactic or "wp.",
                "status": "accepted" if ok else "rejected",
            }],
        },
        "result": {
            "ok": ok,
            "status": "ok" if ok else "error",
            "failure_reason": failure_reason,
        },
        "workspace": {"view": {
            "schema_version": workspace_schema_version,
            "kind": "prover_workspace_view",
            "ok": ok,
            "last_result": {},
            "proof_status": {
                "status": proof_status,
                "remaining_goals": remaining,
                "remaining_goals_known": True,
                "goal_type": "pRHL",
                "goal_identity_required": proof_status == "open",
                "goal_hash": "goal-hash" if proof_status == "open" else "",
            },
            "current_goal": {
                "goal_type": "pRHL",
                "lines": goal_lines,
            },
        }},
        "audit": {
            "commit_response_artifact": "commit_responses/current.json",
            "proof_status": proof_status,
            "goal_hash": "goal-hash",
            "goal_type": "pRHL",
            "num_remaining": remaining,
        },
        "notes": [],
        "errors": [],
    }


def _write_root(result: dict, *, unchecked: bool = False) -> Path:
    root = Path(tempfile.mkdtemp())
    proof_dir = root / "proof_A"
    proof_dir.mkdir()
    execution = result["execution"]
    result_panel = result["result"]
    proof_status = result["workspace"]["view"]["proof_status"]["status"]
    commit_response = {
        "schema_version": 2,
        "kind": "commit_response",
        "ok": bool(result_panel.get("ok")),
        "command": str(execution.get("command") or "next"),
        "status": str(result_panel.get("status") or ""),
        "proof_state": {"status": proof_status},
        "latest_transition": {},
        "mutation": {
            "attempted_count": execution["attempted_count"],
            "accepted_count": execution["accepted_count"],
            "attempted_tactics": execution["submitted_tactics"],
            "failed_tactic": execution.get("failed_tactic", ""),
            "failure_reason": execution.get("failure_reason", ""),
            "keep_on_fail": False,
            "rollback_count": execution["rollback_count"],
        },
        "notes": [],
        "errors": [],
        "debug": {},
    }
    commit_payload = write_commit_response_artifact(proof_dir, commit_response)
    append_event(proof_dir, "commit.response.produced", commit_payload)
    result["audit"]["commit_response_artifact"] = commit_payload["artifact"]
    bind_tactic_execution_workspace(proof_dir, result)
    append_bound_workspace_event(proof_dir, result)
    payload = (
        write_unchecked_tactic_execution_artifact(proof_dir, result)
        if unchecked
        else write_tactic_execution_result_artifact(proof_dir, result)
    )
    append_event(proof_dir, "tactic.execution.produced", payload)
    replay_summary = {
        "proof_id": "proof_A",
        "file": "eval/examples/A.ec",
        "lemma": "A",
        "tactic_count": 1,
        "replayed_tactic_count": 1,
        "outcome": "PASS",
        "consistency_warnings": 0,
        "event_counts": {
            "commit.response.produced": 1,
            "tactic.execution.produced": 1,
        },
        "artifact_dir": str(proof_dir),
        "session_dir": "/tmp/session-A",
        "runner": "inprocess",
        "full_hooks": False,
    }
    audit = {
        "warnings": [],
        "command_counts": {"commit": 1, "audit_tool": 0, "total": 1},
        "event_counts": replay_summary["event_counts"],
        "proof_state": {
            "status": result["workspace"]["view"]["proof_status"]["status"],
        },
    }
    (proof_dir / "summary.json").write_text(
        json.dumps(replay_summary), encoding="utf-8",
    )
    (proof_dir / "audit_report.json").write_text(
        json.dumps(audit), encoding="utf-8",
    )
    (proof_dir / "commands.json").write_text(
        json.dumps([{"kind": "commit"}]), encoding="utf-8",
    )
    (root / "summary.json").write_text(
        json.dumps([replay_summary]), encoding="utf-8",
    )
    return root


def test_prover_ux_audit_accepts_clean_open_tactic_execution() -> None:
    report = audit_replay_root(_write_root(_tactic_execution()))
    assert report["ok"] is True
    assert report["tactic_executions_checked"] == 1
    assert report["error_count"] == 0


def test_prover_ux_audit_accepts_pending_qed_commit_surface() -> None:
    result = _tactic_execution(
        proof_status="goals_discharged_pending_qed",
    )

    report = audit_replay_root(_write_root(result))
    assert report["ok"] is True
    assert report["error_count"] == 0


def test_prover_ux_audit_requires_failed_execution_details() -> None:
    result = _tactic_execution(ok=False, failed_tactic="", failure_reason="")
    codes = {issue["code"] for issue in audit_replay_root(_write_root(result))["issues"]}
    assert "failed_tactic_execution_missing_tactic" in codes
    assert "failed_tactic_execution_missing_reason" in codes


def test_prover_ux_audit_rejects_old_workspace_schema() -> None:
    result = _tactic_execution(workspace_schema_version=1)
    codes = {
        issue["code"]
        for issue in audit_replay_root(
            _write_root(result, unchecked=True)
        )["issues"]
    }
    assert "tactic_execution_workspace_schema_version" in codes


def test_prover_ux_audit_does_not_use_orphan_to_mask_unresolved_event() -> None:
    root = _write_root(_tactic_execution())
    events_path = root / "proof_A" / "events.jsonl"
    events = [
        json.loads(line)
        for line in events_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    execution_event = next(
        event for event in events
        if event["type"] == "tactic.execution.produced"
    )
    execution_event["payload"]["artifact"] = "missing_result.json"
    events_path.write_text(
        "\n".join(json.dumps(event) for event in events) + "\n",
        encoding="utf-8",
    )

    report = audit_replay_root(root)
    codes = {issue["code"] for issue in report["issues"]}

    assert report["ok"] is False
    assert "tactic_execution_event_artifact_mismatch" in codes
    assert "orphan_tactic_execution_artifact" in codes


def test_prover_ux_audit_preserves_duplicate_event_occurrences() -> None:
    root = _write_root(_tactic_execution())
    events_path = root / "proof_A" / "events.jsonl"
    event_lines = events_path.read_text(encoding="utf-8").splitlines()
    execution_line = next(
        line for line in event_lines
        if json.loads(line)["type"] == "tactic.execution.produced"
    )
    events_path.write_text(
        "\n".join([*event_lines, execution_line]) + "\n",
        encoding="utf-8",
    )

    report = audit_replay_root(root)

    assert report["tactic_executions_checked"] == 2
    assert "tactic_execution_event_artifact_mismatch" not in {
        issue["code"] for issue in report["issues"]
    }


def test_prover_ux_audit_rejects_forged_execution_event_payload() -> None:
    root = _write_root(_tactic_execution())
    events_path = root / "proof_A" / "events.jsonl"
    events = [json.loads(line) for line in events_path.read_text().splitlines()]
    execution_event = next(
        event for event in events
        if event["type"] == "tactic.execution.produced"
    )
    execution_event["payload"]["result_hash"] = "0" * 40
    execution_event["payload"]["status"] = "forged"
    events_path.write_text(
        "\n".join(json.dumps(event) for event in events) + "\n",
        encoding="utf-8",
    )

    report = audit_replay_root(root)

    assert report["ok"] is False
    assert "tactic_execution_event_binding" in {
        issue["code"] for issue in report["issues"]
    }
