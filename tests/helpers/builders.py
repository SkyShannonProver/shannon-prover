"""Canonical test-data builders shared across the tests/ tree.

Import-safe from both runners:

- pytest puts the project root on ``sys.path`` via ``tests/conftest.py``;
- standalone scripts (``python3 tests/test_foo.py``) insert the root
  themselves before importing ``tests.helpers.builders``.

Test files keep local helper names such as ``_start_event`` as thin
delegates/aliases so call sites stay untouched.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from core.easycrypt.session_events import append_event
from core.easycrypt.session_prover_workspace_schema import (
    prover_workspace_event_payload_fields,
)


# ─── Session-event seeders ────────────────────────────────────────

def start_event(d: Path) -> None:
    append_event(d, "session.started", {
        "file": None,
        "lemma": "L",
        "include_dirs": [],
        "discarded_tactic_count": 0,
        "restart_count": 1,
    })


def tool_called(d: Path, name: str, mutates: bool = True) -> None:
    append_event(d, "tool.called", {
        "name": name,
        "mutates_proof_state": mutates,
        "session_dir": str(d.resolve()),
    })


def tool_result(d: Path, name: str, mutates: bool = True, status: str = "ok") -> None:
    append_event(d, "tool.result", {
        "name": name,
        "mutates_proof_state": mutates,
        "session_dir": str(d.resolve()),
        "exit_code": 0 if status == "ok" else 1,
        "status": status,
    })


def write_open_goal(d: Path, body: str = "x = y") -> None:
    (d / "current.out").write_text(
        "[1|check]>\n"
        "Current goal\n"
        "----\n"
        f"{body}\n"
        "[2|check]>\n",
        encoding="utf-8",
    )


def managed_workspace_view(
    *,
    goal: str = "x = y",
    goal_hash: str = "goal-hash",
) -> dict:
    """One lean current workspace fixture with no retired carrier panels."""

    lines = ["Current goal", "----", goal]
    raw_goal = "\n".join(lines)
    return {
        "schema_version": 3,
        "kind": "prover_workspace_view",
        "ok": True,
        "last_result": {},
        "proof_status": {
            "status": "open",
            "goal_identity_required": True,
            "goal_hash": goal_hash,
            "remaining_goals": 1,
            "remaining_goals_known": True,
        },
        "current_goal": {
            "lines": lines,
            "text_fully_shown": True,
            "truncated": False,
            "line_count": len(lines),
            "shown_lines": len(lines),
            "char_count": len(raw_goal),
            "shown_chars": len(raw_goal),
            "source": "test_fixture",
        },
    }


def bind_tactic_execution_workspace(
    d: Path,
    result: dict,
) -> dict:
    """Persist and bind the embedded workspace in a TER test fixture."""
    workspace = result.get("workspace")
    if not isinstance(workspace, dict):
        return result
    view = workspace.get("view")
    if not isinstance(view, dict):
        return result
    canonical = json.dumps(view, indent=2, sort_keys=True)
    digest = hashlib.sha1(canonical.encode("utf-8")).hexdigest()
    out_dir = d / "prover_workspace_views"
    out_dir.mkdir(parents=True, exist_ok=True)
    artifact = out_dir / f"prover_workspace_view_{digest[:16]}.json"
    artifact.write_text(canonical + "\n", encoding="utf-8")
    current_goal = view.get("current_goal")
    current_goal = current_goal if isinstance(current_goal, dict) else {}
    workspace.update({
        "artifact": str(artifact),
        "view_hash": digest,
        "current_goal_text_fully_shown": bool(
            current_goal.get("text_fully_shown")
        ),
        "current_goal_truncated": bool(current_goal.get("truncated")),
        "goal_chars": int(current_goal.get("char_count") or 0),
        "workspace_chars": len(json.dumps(view, sort_keys=True)),
    })
    audit = result.get("audit")
    if not isinstance(audit, dict):
        audit = {}
        result["audit"] = audit
    audit["prover_workspace_artifact"] = str(artifact)
    return result


def append_bound_workspace_event(d: Path, result: dict) -> dict:
    """Emit the workspace occurrence already bound into a TER fixture."""

    workspace = result.get("workspace")
    workspace = workspace if isinstance(workspace, dict) else {}
    view = workspace.get("view")
    view = view if isinstance(view, dict) else {}
    payload = prover_workspace_event_payload_fields(
        view,
        artifact=str(workspace.get("artifact") or ""),
        view_hash=str(workspace.get("view_hash") or ""),
    )
    append_event(d, "prover.workspace_view.produced", payload)
    return payload


def write_unchecked_tactic_execution_artifact(d: Path, result: dict) -> dict:
    """Forge a malformed TER artifact for reader-side negative tests only."""

    text = json.dumps(result, indent=2, sort_keys=True)
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()
    out_dir = d / "tactic_execution_results"
    out_dir.mkdir(parents=True, exist_ok=True)
    artifact = out_dir / f"unchecked_{digest[:16]}.json"
    artifact.write_text(text + "\n", encoding="utf-8")
    execution = result.get("execution")
    execution = execution if isinstance(execution, dict) else {}
    outcome = result.get("result")
    outcome = outcome if isinstance(outcome, dict) else {}
    workspace = result.get("workspace")
    workspace = workspace if isinstance(workspace, dict) else {}
    audit = result.get("audit")
    audit = audit if isinstance(audit, dict) else {}

    def integer(value) -> int:
        return value if type(value) is int else 0

    return {
        "schema_version": result.get("schema_version"),
        "ok": bool(result.get("ok")),
        "mode": str(execution.get("mode") or ""),
        "command": str(execution.get("command") or ""),
        "status": str(outcome.get("status") or ""),
        "artifact": str(artifact),
        "result_hash": digest,
        "accepted_count": integer(execution.get("accepted_count")),
        "rollback_count": integer(execution.get("rollback_count")),
        "failed_tactic": str(execution.get("failed_tactic") or ""),
        "state_changed": bool(execution.get("state_changed")),
        "history_committed": bool(execution.get("history_committed")),
        "workspace_artifact": str(workspace.get("artifact") or ""),
        "workspace_chars": integer(workspace.get("workspace_chars")),
        "current_goal_text_fully_shown": bool(
            workspace.get("current_goal_text_fully_shown")
        ),
        "current_goal_truncated": bool(workspace.get("current_goal_truncated")),
        "commit_response_artifact": str(audit.get("commit_response_artifact") or ""),
        "raw_result_artifact": str(audit.get("raw_result_artifact") or ""),
        "error_count": len(result.get("errors") or []),
        "warning_count": 0,
    }


# ─── ProofNodeManager construction ────────────────────────────────

def make_manager(**overrides):
    """Build the standard unit-test ProofNodeManager (kwargs overridable)."""
    from workflow.proof_node_manager import ProofNodeManager

    kwargs: dict = {
        "file_path": "eval/examples/SchnorrPK.ec",
        "lemma_name": "dummy",
        "include_dir": "easycrypt-src/theories",
        "session_tag": "unit",
        "node_id": "Tree-unit",
    }
    kwargs.update(overrides)
    return ProofNodeManager(**kwargs)


def intent(name: str, tactic: str = ""):
    """Parse a minimal agent intent (optionally carrying a tactic payload)."""
    from workflow.proof_management.protocol_repair import parse_agent_intent

    payload = '{"tactic": "%s"}' % tactic if tactic else "{}"
    return parse_agent_intent(
        '{"intent": "%s", "payload": %s}' % (name, payload)
    ).intent
