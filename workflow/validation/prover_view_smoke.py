"""Session-level smoke audit for prover-facing structured views.

This is lighter than proof replay: it audits one or more existing
``.ec_session_*`` directories and checks the artifacts a live prover would read:

* ToolView JSON under ``tool_views/``
* ProofContextView JSON under ``proof_context_views/`` (legacy
  ``agent_views/`` is still accepted)
* CommandSummary JSON under ``command_summaries/``

The goal is not to prove anything. The goal is to fail fast when a view regresses
back toward legacy stdout inference or exposes inconsistent action semantics.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from core.easycrypt.session_agent_view import validate_proof_context_view
from core.easycrypt.session_command_summary import (
    command_summary_workspace_metrics,
    validate_command_summary,
)
from core.easycrypt.session_tool_view import validate_tool_view
from workflow.validation.prover_view_text_lint import lint_prover_facing_payload
from core.easycrypt.value_shapes import as_dict as _dict


@dataclass(frozen=True)
class ProverSurfaceIssue:
    severity: str
    code: str
    message: str
    artifact: str = ""
    view_type: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "artifact": self.artifact,
            "view_type": self.view_type,
        }

    def format(self) -> str:
        loc = f"{self.view_type}:{self.artifact}" if self.artifact else self.view_type
        return f"[{self.severity.upper()}] {loc}: {self.code}: {self.message}"


def audit_session_dir(session_dir: str | Path) -> dict[str, Any]:
    path = Path(session_dir)
    issues: list[ProverSurfaceIssue] = []
    tool_views, tool_load_issues = _load_json_files(path / "tool_views", "tool_view")
    agent_views, agent_load_issues = _load_json_files(
        path / "proof_context_views",
        "proof_context_view",
    )
    legacy_agent_views, legacy_agent_load_issues = _load_json_files(
        path / "agent_views",
        "legacy_agent_view",
    )
    agent_views.extend(legacy_agent_views)
    command_summaries, summary_load_issues = _load_json_files(
        path / "command_summaries",
        "command_summary",
    )
    issues.extend(tool_load_issues)
    issues.extend(agent_load_issues)
    issues.extend(legacy_agent_load_issues)
    issues.extend(summary_load_issues)

    if not path.exists():
        issues.append(_issue(
            "error",
            "session_dir_missing",
            f"session directory does not exist: {path}",
            view_type="session",
        ))
    if path.exists() and not tool_views and not agent_views and not command_summaries:
        issues.append(_issue(
            "warning",
            "no_structured_artifacts",
            "no ToolView, ProofContextView, or CommandSummary artifacts found",
            view_type="session",
        ))

    for artifact, view in tool_views:
        issues.extend(_audit_tool_view(view, artifact=artifact))
    for artifact, view in agent_views:
        issues.extend(_audit_agent_view(view, artifact=artifact))
    for artifact, view in command_summaries:
        issues.extend(_audit_command_summary(view, artifact=artifact))

    return _report(
        session_dir=path,
        tool_view_count=len(tool_views),
        agent_view_count=len(agent_views),
        command_summary_count=len(command_summaries),
        issues=issues,
    )


def audit_many(session_dirs: Iterable[str | Path]) -> dict[str, Any]:
    reports = [audit_session_dir(path) for path in session_dirs]
    issues = [
        issue
        for report in reports
        for issue in report.get("issues", [])
    ]
    return {
        "ok": not any(issue.get("severity") == "error" for issue in issues),
        "session_count": len(reports),
        "error_count": sum(1 for issue in issues if issue.get("severity") == "error"),
        "warning_count": sum(1 for issue in issues if issue.get("severity") == "warning"),
        "reports": reports,
        "issues": issues,
    }


def _audit_tool_view(view: dict[str, Any], *, artifact: Path) -> list[ProverSurfaceIssue]:
    issues: list[ProverSurfaceIssue] = []
    validation = validate_tool_view(view)
    for err in validation.errors:
        issues.append(_artifact_issue(
            "error", "tool_view_contract", err, artifact, "tool_view",
        ))
    for warn in validation.warnings:
        issues.append(_artifact_issue(
            "warning", "tool_view_contract_warning", warn, artifact, "tool_view",
        ))

    if "tool_view" in view:
        issues.append(_artifact_issue(
            "error",
            "nested_legacy_tool_view",
            "ToolView artifact must not contain a nested `tool_view` envelope",
            artifact,
            "tool_view",
        ))

    proof_state = _dict(view.get("proof_state"))
    event_contract = _dict(proof_state.get("event_contract"))
    consistency = _dict(proof_state.get("consistency"))
    if event_contract and event_contract.get("ok") is False and view.get("ok") is True:
        issues.append(_artifact_issue(
            "error",
            "event_contract_error_not_fail_closed",
            "ToolView ok=true even though proof_state.event_contract.ok=false",
            artifact,
            "tool_view",
        ))
    if consistency and consistency.get("ok") is False and view.get("ok") is True:
        issues.append(_artifact_issue(
            "error",
            "consistency_error_not_fail_closed",
            "ToolView ok=true even though proof_state.consistency.ok=false",
            artifact,
            "tool_view",
        ))

    tool = str(view.get("tool") or "")
    if tool == "goal-info":
        issues.extend(_audit_goal_info_tool_view(view, artifact=artifact))
    if tool == "try":
        issues.extend(_audit_try_tool_view(view, artifact=artifact))
    issues.extend(_audit_text_hygiene(view, artifact=artifact, view_type="tool_view"))
    return issues


def _audit_goal_info_tool_view(
    view: dict[str, Any],
    *,
    artifact: Path,
) -> list[ProverSurfaceIssue]:
    issues: list[ProverSurfaceIssue] = []
    guidance = _dict(view.get("guidance"))
    if not isinstance(guidance.get("goal_info"), dict):
        issues.append(_artifact_issue(
            "error",
            "goal_info_payload_missing",
            "goal-info ToolView must expose legacy goal fields under guidance.goal_info",
            artifact,
            "tool_view",
        ))
    debug = _dict(view.get("debug"))
    if debug.get("legacy_top_level_fields") is True:
        issues.append(_artifact_issue(
            "error",
            "goal_info_legacy_envelope_flag",
            "goal-info ToolView still marks legacy_top_level_fields=true",
            artifact,
            "tool_view",
        ))
    for rec in _recommendations(view):
        if rec.get("action_type") == "runnable_tactic":
            issues.append(_artifact_issue(
                "error",
                "goal_info_unverified_runnable",
                "goal-info must emit static tactics as tactic_candidate or strategy_hint, not runnable_tactic",
                artifact,
                "tool_view",
            ))
    return issues


def _audit_try_tool_view(
    view: dict[str, Any],
    *,
    artifact: Path,
) -> list[ProverSurfaceIssue]:
    issues: list[ProverSurfaceIssue] = []
    recs = _recommendations(view)
    for result in _bucket(view, "preflight"):
        if result.get("producer") != "daemon.try_tactic":
            continue
        if result.get("mutates_proof_state") is not False:
            issues.append(_artifact_issue(
                "error",
                "preflight_mutates_state",
                "preflight evidence must set mutates_proof_state=false",
                artifact,
                "tool_view",
            ))
        accepted = result.get("accepted")
        no_progress = bool(result.get("no_progress_predicted"))
        tactic = str(result.get("tactic") or "")
        if accepted is True and not no_progress:
            if not _has_rec(
                recs,
                tactic=tactic,
                action_type="runnable_tactic",
                epistemic="easycrypt_preflight_accepted",
                confidence="verified",
            ):
                issues.append(_artifact_issue(
                    "error",
                    "accepted_try_missing_commit_recommendation",
                    "accepted preflight must produce verified runnable_tactic guidance",
                    artifact,
                    "tool_view",
                ))
        elif accepted is False:
            if not _has_rec(
                recs,
                tactic=tactic,
                action_type="avoid_action",
                epistemic="easycrypt_preflight_rejected",
            ):
                issues.append(_artifact_issue(
                    "error",
                    "rejected_try_missing_avoid",
                    "rejected preflight must produce avoid_action guidance",
                    artifact,
                    "tool_view",
                ))
        elif no_progress:
            if not _has_rec(
                recs,
                tactic=tactic,
                action_type="avoid_action",
                epistemic="easycrypt_preflight_no_progress",
            ):
                issues.append(_artifact_issue(
                    "error",
                    "no_progress_try_missing_avoid",
                    "no-progress preflight must produce avoid_action guidance",
                    artifact,
                    "tool_view",
                ))
    return issues


def _audit_agent_view(view: dict[str, Any], *, artifact: Path) -> list[ProverSurfaceIssue]:
    issues: list[ProverSurfaceIssue] = []
    validation = validate_proof_context_view(view)
    for err in validation.errors:
        issues.append(_artifact_issue(
            "error", "agent_view_contract", err, artifact, "agent_view",
        ))
    for warn in validation.warnings:
        issues.append(_artifact_issue(
            "warning", "agent_view_contract_warning", warn, artifact, "agent_view",
        ))

    proof_state = _dict(view.get("proof_state"))
    status = str(proof_state.get("status") or "")
    goal = _dict(proof_state.get("goal"))
    if status == "open":
        if goal.get("num_remaining_determined") is not True:
            issues.append(_artifact_issue(
                "error",
                "open_state_remaining_indeterminate",
                "open ProofContextView must expose a determined remaining-goal count",
                artifact,
                "agent_view",
            ))
        if not isinstance(goal.get("num_remaining"), int):
            issues.append(_artifact_issue(
                "error",
                "open_state_missing_remaining_count",
                "open ProofContextView must expose goal.num_remaining as an integer",
                artifact,
                "agent_view",
            ))

    guidance = _dict(view.get("guidance"))
    avoid_ids = {
        str(rec.get("id") or "")
        for rec in _list(guidance.get("recommendations"))
        if _action_type(rec) == "avoid_action"
    }
    for item in _list(view.get("safe_next_actions")):
        if str(item.get("recommendation_id") or "") in avoid_ids:
            issues.append(_artifact_issue(
                "error",
                "safe_next_action_points_to_avoid",
                "safe_next_actions must not ask the prover to consider avoid guidance as a next action",
                artifact,
                "agent_view",
            ))

    actions = _list(view.get("actions"))
    for action in actions:
        if action.get("category") == "commit" and not _commit_action_is_verified(action):
            issues.append(_artifact_issue(
                "error",
                "commit_action_not_verified",
                "commit actions must be EasyCrypt-verified; static candidates must remain strategy actions",
                artifact,
                "agent_view",
            ))
        if action.get("category") == "inspect":
            issues.extend(_audit_inspect_action(action, artifact=artifact, view_type="agent_view"))
        if action.get("category") == "probe":
            issues.append(_artifact_issue(
                "error",
                "public_probe_action",
                "ProofContextView must not expose a probe action",
                artifact,
                "agent_view",
            ))
    for item in _list(view.get("notes")):
        if str(item.get("code") or "") == "source.tool_view.note" and (
            "Speculative preflight did not mutate" in str(item.get("message") or "")
        ):
            issues.append(_artifact_issue(
                "warning",
                "aggregate_try_state_unchanged_note",
                "ProofContextView should not aggregate low-value try.state_unchanged notes",
                artifact,
                "agent_view",
            ))
    for rec in _list(guidance.get("recommendations")):
        if _action_type(rec) == "runnable_tactic" and not _recommendation_is_verified(rec):
            issues.append(_artifact_issue(
                "error",
                "active_runnable_recommendation_not_verified",
                "active runnable_tactic recommendations must be verified; static candidates should be tactic_candidate or strategy_hint",
                artifact,
                "agent_view",
            ))
    issues.extend(_audit_text_hygiene(view, artifact=artifact, view_type="agent_view"))
    return issues


def _audit_command_summary(
    view: dict[str, Any],
    *,
    artifact: Path,
) -> list[ProverSurfaceIssue]:
    issues: list[ProverSurfaceIssue] = []
    validation = validate_command_summary(view)
    for err in validation.errors:
        issues.append(_artifact_issue(
            "error", "command_summary_contract", err, artifact, "command_summary",
        ))
    for warn in validation.warnings:
        issues.append(_artifact_issue(
            "warning", "command_summary_contract_warning", warn, artifact, "command_summary",
        ))
    proof = _dict(view.get("proof"))
    next_block = _dict(view.get("next"))
    workspace_metrics = command_summary_workspace_metrics(view)
    if proof.get("status") == "candidate_closed":
        if workspace_metrics.get("primary_action") != "verify":
            issues.append(_artifact_issue(
                "error",
                "closed_summary_not_verify",
                "candidate_closed CommandSummary must direct prover to verify",
                artifact,
                "command_summary",
            ))
        if (
            _int(workspace_metrics.get("strategy_hint_count"))
            or _int(workspace_metrics.get("runnable_tactic_count"))
        ):
            issues.append(_artifact_issue(
                "error",
                "closed_summary_has_tactic_actions",
                "candidate_closed CommandSummary must not expose tactic actions",
                artifact,
                "command_summary",
            ))
    for action in _list(next_block.get("actions")):
        if action.get("category") == "commit" and not _commit_action_is_verified(action):
            issues.append(_artifact_issue(
                "error",
                "summary_commit_action_not_verified",
                "CommandSummary commit actions must be EasyCrypt-verified",
                artifact,
                "command_summary",
            ))
        if action.get("category") == "inspect":
            issues.extend(_audit_inspect_action(action, artifact=artifact, view_type="command_summary"))
    for rec in _list(next_block.get("recommendations")):
        if _action_type(rec) == "runnable_tactic" and not _recommendation_is_verified(rec):
            issues.append(_artifact_issue(
                "error",
                "summary_runnable_recommendation_not_verified",
                "CommandSummary runnable_tactic recommendations must be verified",
                artifact,
                "command_summary",
            ))
    issues.extend(_audit_text_hygiene(view, artifact=artifact, view_type="command_summary"))
    return issues


def _audit_text_hygiene(
    view: dict[str, Any],
    *,
    artifact: Path,
    view_type: str,
) -> list[ProverSurfaceIssue]:
    out: list[ProverSurfaceIssue] = []
    for issue in lint_prover_facing_payload(view, view_type=view_type):
        out.append(_artifact_issue(
            issue.severity,
            issue.code,
            f"{issue.message} (path: {issue.path})",
            artifact,
            view_type,
        ))
    return out


def _load_json_files(
    path: Path,
    view_type: str,
) -> tuple[list[tuple[Path, dict[str, Any]]], list[ProverSurfaceIssue]]:
    if not path.exists():
        return [], []
    out: list[tuple[Path, dict[str, Any]]] = []
    issues: list[ProverSurfaceIssue] = []
    for item in sorted(path.glob("*.json")):
        try:
            data = json.loads(item.read_text(encoding="utf-8"))
        except Exception as exc:
            issues.append(_artifact_issue(
                "error",
                "invalid_json_artifact",
                f"artifact is not valid JSON: {exc}",
                item,
                view_type,
            ))
            continue
        if isinstance(data, dict):
            out.append((item, data))
        else:
            issues.append(_artifact_issue(
                "error",
                "invalid_json_artifact_shape",
                "artifact JSON root must be an object",
                item,
                view_type,
            ))
    return out, issues


def _recommendations(view: dict[str, Any]) -> list[dict[str, Any]]:
    return _list(_dict(view.get("guidance")).get("recommendations"))


def _bucket(view: dict[str, Any], name: str) -> list[dict[str, Any]]:
    return _list(_dict(view.get("evidence")).get(name))


def _has_rec(
    recs: list[dict[str, Any]],
    *,
    tactic: str,
    action_type: str,
    epistemic: str,
    confidence: str = "",
) -> bool:
    for rec in recs:
        if str(rec.get("action") or "") != tactic:
            continue
        if _action_type(rec) != action_type:
            continue
        metadata = _dict(rec.get("metadata"))
        if str(metadata.get("epistemic_status") or "") != epistemic:
            continue
        if confidence and str(rec.get("confidence") or "") != confidence:
            continue
        return True
    return False


def _action_type(rec: dict[str, Any]) -> str:
    metadata = _dict(rec.get("metadata"))
    return str(rec.get("action_type") or metadata.get("action_type") or "")


def _commit_action_is_verified(action: dict[str, Any]) -> bool:
    metadata = _dict(action.get("metadata"))
    return (
        str(action.get("confidence") or "") == "verified"
        or str(action.get("epistemic_status") or "") == "easycrypt_preflight_accepted"
        or metadata.get("daemon_ready") is True
        or str(metadata.get("epistemic_status") or "") == "easycrypt_preflight_accepted"
    )


def _recommendation_is_verified(rec: dict[str, Any]) -> bool:
    metadata = _dict(rec.get("metadata"))
    return (
        str(rec.get("confidence") or "") == "verified"
        or metadata.get("daemon_ready") is True
        or str(metadata.get("epistemic_status") or "") == "easycrypt_preflight_accepted"
    )


def _audit_inspect_action(
    action: dict[str, Any],
    *,
    artifact: Path,
    view_type: str,
) -> list[ProverSurfaceIssue]:
    issues: list[ProverSurfaceIssue] = []
    if action.get("requires_instantiation") is True:
        issues.append(_artifact_issue(
            "error",
            "inspect_action_requires_instantiation",
            "inspect actions must be directly runnable tool calls; template guidance belongs in strategy",
            artifact,
            view_type,
        ))
    if str(action.get("tool") or "") == "inspection":
        issues.append(_artifact_issue(
            "error",
            "generic_inspection_action",
            "inspect actions must name a concrete tool; generic `inspection` usually means strategy text was misclassified",
            artifact,
            view_type,
        ))
    return issues



def _list(value: Any) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _artifact_issue(
    severity: str,
    code: str,
    message: str,
    artifact: Path,
    view_type: str,
) -> ProverSurfaceIssue:
    return _issue(
        severity,
        code,
        message,
        artifact=str(artifact),
        view_type=view_type,
    )


def _int(value: Any) -> int:
    return value if isinstance(value, int) else 0


def _issue(
    severity: str,
    code: str,
    message: str,
    *,
    artifact: str = "",
    view_type: str = "",
) -> ProverSurfaceIssue:
    return ProverSurfaceIssue(
        severity=severity,
        code=code,
        message=message,
        artifact=artifact,
        view_type=view_type,
    )


def _report(
    *,
    session_dir: Path,
    tool_view_count: int,
    agent_view_count: int,
    command_summary_count: int,
    issues: list[ProverSurfaceIssue],
) -> dict[str, Any]:
    return {
        "ok": not any(issue.severity == "error" for issue in issues),
        "session_dir": str(session_dir),
        "tool_view_count": tool_view_count,
        "agent_view_count": agent_view_count,
        "command_summary_count": command_summary_count,
        "error_count": sum(1 for issue in issues if issue.severity == "error"),
        "warning_count": sum(1 for issue in issues if issue.severity == "warning"),
        "issues": [issue.to_dict() for issue in issues],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Audit prover-facing structured views in session directories.",
    )
    parser.add_argument("session_dirs", nargs="+", help=".ec_session_* directories")
    parser.add_argument(
        "--write-report",
        action="store_true",
        help="Write prover_view_smoke_report.json into each audited session dir.",
    )
    args = parser.parse_args(argv)

    reports = []
    for raw in args.session_dirs:
        report = audit_session_dir(raw)
        reports.append(report)
        if args.write_report:
            out = Path(raw) / "prover_view_smoke_report.json"
            out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    combined = audit_many(args.session_dirs)
    combined["reports"] = reports
    print(json.dumps(combined, indent=2, sort_keys=True))
    return 0 if combined["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
