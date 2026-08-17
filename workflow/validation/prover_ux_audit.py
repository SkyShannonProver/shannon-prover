"""Audit replay artifacts from the prover's point of view.

Each persisted TacticExecutionResult records what happened to one proof action
and embeds the authoritative ProverWorkspaceView v3 shown after it.  The audit
checks that current contract directly; retired summary artifacts are outside
the supported input surface.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.easycrypt.session_artifact_io import read_hashed_json_object
from core.easycrypt.session_prover_workspace_schema import (
    PROVER_WORKSPACE_VIEW_SCHEMA_VERSION,
)
from core.easycrypt.session_commit_response import (
    validate_commit_response_event_binding,
)
from core.easycrypt.session_tactic_execution_artifacts import (
    TacticExecutionArtifactLoad,
    load_tactic_execution_artifacts as load_session_tactic_execution_artifacts,
)
from core.easycrypt.session_tactic_execution_result import (
    validate_tactic_execution_event_binding,
    validate_tactic_execution_result,
)
from core.easycrypt.session_tactic_execution_observation import (
    tactic_execution_failed,
    tactic_execution_no_progress,
    tactic_execution_workspace,
)
from core.easycrypt.session_events import event_payload, events_of_type
from workflow.validation.replay_artifacts import (
    ReplayArtifact,
    TacticExecutionArtifact,
    _resolve_artifact_path,
    iter_replay_artifacts,
)
from core.easycrypt.value_shapes import as_dict as _dict, as_list as _list


@dataclass(frozen=True)
class ProverUxIssue:
    severity: str
    code: str
    message: str
    proof_id: str = ""
    lemma: str = ""
    step: int = 0
    command: str = ""
    artifact: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "proof_id": self.proof_id,
            "lemma": self.lemma,
            "step": self.step,
            "command": self.command,
            "artifact": self.artifact,
        }

    def format(self) -> str:
        loc = self.lemma or self.proof_id or "<unknown-proof>"
        if self.step:
            loc += f" step {self.step}"
        if self.command:
            loc += f" {self.command}"
        return f"[{self.severity.upper()}] {loc}: {self.code}: {self.message}"


def audit_replay_root(root: Path) -> dict[str, Any]:
    artifacts = list(iter_replay_artifacts(root))
    issues: list[ProverUxIssue] = []
    executions_checked = 0
    proofs_with_executions = 0
    for artifact in artifacts:
        execution_load = load_session_tactic_execution_artifacts(
            artifact.proof_dir,
            events=artifact.events,
        )
        proof_executions = execution_load.artifacts
        if proof_executions:
            proofs_with_executions += 1
        executions_checked += len(proof_executions)
        issues.extend(_audit_artifact_level(
            artifact,
            proof_executions,
            execution_load=execution_load,
        ))
        for idx, item in enumerate(proof_executions, start=1):
            issues.extend(_audit_tactic_execution(
                item.result,
                artifact=artifact,
                artifact_path=item.path,
                step=idx,
            ))
    return _report(
        root=root,
        proof_count=len(artifacts),
        proofs_with_executions=proofs_with_executions,
        executions_checked=executions_checked,
        issues=issues,
    )


def write_report(root: Path, report: dict[str, Any]) -> Path:
    path = Path(root) / "prover_ux_report.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def _audit_artifact_level(
    artifact: ReplayArtifact,
    proof_executions: list[TacticExecutionArtifact],
    *,
    execution_load: TacticExecutionArtifactLoad,
) -> list[ProverUxIssue]:
    issues: list[ProverUxIssue] = []
    expected = artifact.audit_report.command_counts.get("commit", 0)
    produced = len(proof_executions)
    event_linked = sum(1 for item in proof_executions if item.event_index > 0)
    execution_events = len(events_of_type(
        artifact.events,
        "tactic.execution.produced",
    ))
    commit_event_rows = [
        (idx, event)
        for idx, event in enumerate(artifact.events, start=1)
        if event.get("type") == "commit.response.produced"
    ]
    commit_events = len(commit_event_rows)
    if expected and produced == 0:
        issues.append(_issue(
            "error",
            "missing_tactic_executions",
            f"{expected} mutating replay commands but no TacticExecutionResult artifacts",
            artifact,
        ))
    if event_linked != execution_events:
        issues.append(_issue(
            "error",
            "tactic_execution_event_artifact_mismatch",
            f"{execution_events} execution events but {event_linked} resolved event artifacts",
            artifact,
        ))
    for event_index, event_errors in sorted(
        execution_load.unresolved_event_errors.items()
    ):
        for error in event_errors:
            code = (
                "tactic_execution_workspace_schema_version"
                if "ProverWorkspaceView schema_version" in error
                else "tactic_execution_event_binding"
            )
            issues.append(_issue(
                "error",
                code,
                f"event#{event_index}: {error}",
                artifact,
            ))
    orphan_count = (
        len(execution_load.orphan_paths)
        + len(execution_load.unreadable_orphan_paths)
    )
    if orphan_count:
        issues.append(_issue(
            "error",
            "orphan_tactic_execution_artifact",
            f"{orphan_count} TacticExecutionResult artifact(s) have no producing event",
            artifact,
        ))
    for item in proof_executions:
        if item.event_index == 0:
            continue
        validation = validate_tactic_execution_event_binding(
            item.result,
            event_payload(item.event or {}),
            artifact_hash=item.artifact_hash,
            include_contract=False,
        )
        for error in validation.errors:
            issues.append(_issue(
                "error",
                "tactic_execution_event_binding",
                f"{item.path}: {error}",
                artifact,
            ))
    if commit_events != execution_events:
        issues.append(_issue(
            "error",
            "commit_execution_count_mismatch",
            f"{commit_events} CommitResponse events but {execution_events} tactic executions",
            artifact,
        ))
    issues.extend(_audit_commit_execution_chain(
        artifact,
        proof_executions,
        commit_event_rows,
    ))
    return issues


def _audit_commit_execution_chain(
    artifact: ReplayArtifact,
    proof_executions: list[TacticExecutionArtifact],
    commit_events: list[tuple[int, dict[str, Any]]],
) -> list[ProverUxIssue]:
    issues: list[ProverUxIssue] = []
    linked_executions = [
        item for item in proof_executions if item.event_index > 0
    ]
    for (commit_event_index, commit_event), execution_item in zip(
        commit_events,
        linked_executions,
    ):
        if commit_event_index >= execution_item.event_index:
            issues.append(_issue(
                "error",
                "commit_execution_event_order",
                "CommitResponse event must precede its TacticExecutionResult event",
                artifact,
            ))
        execution_audit = _dict(execution_item.result.get("audit"))
        linked_value = str(execution_audit.get("commit_response_artifact") or "")
        commit_payload = event_payload(commit_event)
        event_value = str(commit_payload.get("artifact") or "")
        if not linked_value:
            issues.append(_issue(
                "error",
                "tactic_execution_missing_commit_response_artifact",
                f"{execution_item.path} does not link its CommitResponse artifact",
                artifact,
            ))
            continue
        if Path(linked_value).name != Path(event_value).name:
            issues.append(_issue(
                "error",
                "commit_execution_artifact_link_mismatch",
                "TacticExecutionResult commit-response link does not match the "
                "paired CommitResponse event",
                artifact,
            ))
            continue
        commit_path = _resolve_artifact_path(
            artifact.proof_dir,
            linked_value,
            copied_subdir="commit_responses",
        )
        if commit_path is None:
            issues.append(_issue(
                "error",
                "commit_response_artifact_unreadable",
                f"linked CommitResponse artifact is unavailable: {linked_value}",
                artifact,
            ))
            continue
        loaded = read_hashed_json_object(commit_path)
        if loaded is None:
            issues.append(_issue(
                "error",
                "commit_response_artifact_unreadable",
                f"linked CommitResponse artifact is invalid: {commit_path}",
                artifact,
            ))
            continue
        response, response_hash = loaded
        validation = validate_commit_response_event_binding(
            response,
            commit_payload,
            artifact_hash=response_hash,
        )
        for error in validation.errors:
            issues.append(_issue(
                "error",
                "commit_response_event_binding",
                f"{commit_path}: {error}",
                artifact,
            ))
        for warning in validation.warnings:
            issues.append(_issue(
                "warning",
                "commit_response_contract_warning",
                f"{commit_path}: {warning}",
                artifact,
            ))
    return issues


def _audit_tactic_execution(
    tactic_execution: dict[str, Any],
    *,
    artifact: ReplayArtifact,
    artifact_path: Path,
    step: int,
) -> list[ProverUxIssue]:
    issues: list[ProverUxIssue] = []
    execution = _dict(tactic_execution.get("execution"))
    result_panel = _dict(tactic_execution.get("result"))
    workspace = tactic_execution_workspace(tactic_execution)
    command = str(execution.get("command") or "")
    validation = validate_tactic_execution_result(tactic_execution)
    for err in validation.errors:
        issues.append(_issue(
            "error",
            "tactic_execution_contract",
            err,
            artifact,
            step=step,
            command=command,
            path=artifact_path,
        ))
    for warn in validation.warnings:
        issues.append(_issue(
            "warning",
            "tactic_execution_contract_warning",
            warn,
            artifact,
            step=step,
            command=command,
            path=artifact_path,
        ))

    if workspace:
        if workspace.get("kind") != "prover_workspace_view":
            issues.append(_issue(
                "error",
                "tactic_execution_workspace_kind",
                "workspace.view must be a ProverWorkspaceView",
                artifact,
                step=step,
                command=command,
                path=artifact_path,
            ))
        if workspace.get("schema_version") != PROVER_WORKSPACE_VIEW_SCHEMA_VERSION:
            issues.append(_issue(
                "error",
                "tactic_execution_workspace_schema_version",
                "workspace.view must use ProverWorkspaceView schema version "
                f"{PROVER_WORKSPACE_VIEW_SCHEMA_VERSION}",
                artifact,
                step=step,
                command=command,
                path=artifact_path,
            ))

    proof = _dict(workspace.get("proof_status"))
    current_goal = _dict(workspace.get("current_goal"))
    failed = tactic_execution_failed(tactic_execution)
    errors = _list(tactic_execution.get("errors"))
    notes = _list(tactic_execution.get("notes"))

    proof_status = str(
        proof.get("status")
        or _dict(tactic_execution.get("audit")).get("proof_status")
        or ""
    )
    if tactic_execution.get("ok") is True and errors:
        issues.append(_issue(
            "error",
            "ok_execution_has_errors",
            "ok=true tactic execution exposes non-empty errors",
            artifact,
            step=step,
            command=command,
            path=artifact_path,
        ))

    if failed:
        if not execution.get("failed_tactic"):
            issues.append(_issue(
                "error",
                "failed_tactic_execution_missing_tactic",
                "failed tactic execution does not identify the failed tactic",
                artifact,
                step=step,
                command=command,
                path=artifact_path,
            ))
        if (
            not execution.get("failure_reason")
            and not result_panel.get("failure_reason")
            and not result_panel.get("error")
            and not errors
        ):
            issues.append(_issue(
                "error",
                "failed_tactic_execution_missing_reason",
                "failed execution does not expose a reason in execution/result/errors",
                artifact,
                step=step,
                command=command,
                path=artifact_path,
            ))

    if proof_status == "open" and tactic_execution.get("ok") is True:
        if not _list(current_goal.get("lines")):
            issues.append(_issue(
                "warning",
                "open_state_missing_goal",
                "open proof has no current goal lines in the workspace view",
                artifact,
                step=step,
                command=command,
                path=artifact_path,
            ))

    if tactic_execution_no_progress(tactic_execution):
        reason = str(
            execution.get("failure_reason")
            or result_panel.get("failure_reason")
            or result_panel.get("error")
            or ""
        )
        if not reason and not notes:
            issues.append(_issue(
                "warning",
                "no_progress_missing_reason",
                "execution reports no progress but no reason/note is exposed",
                artifact,
                step=step,
                command=command,
                path=artifact_path,
            ))
    return issues



def _report(
    *,
    root: Path,
    proof_count: int,
    proofs_with_executions: int,
    executions_checked: int,
    issues: list[ProverUxIssue],
) -> dict[str, Any]:
    errors = [issue for issue in issues if issue.severity == "error"]
    warnings = [issue for issue in issues if issue.severity == "warning"]
    notes = [issue for issue in issues if issue.severity == "note"]
    return {
        "schema_version": 2,
        "kind": "prover_ux_audit",
        "ok": not errors,
        "artifact_root": str(Path(root).resolve()),
        "proofs_checked": proof_count,
        "proofs_with_tactic_executions": proofs_with_executions,
        "tactic_executions_checked": executions_checked,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "note_count": len(notes),
        "issues": [issue.to_dict() for issue in issues],
    }


def _issue(
    severity: str,
    code: str,
    message: str,
    artifact: ReplayArtifact,
    *,
    step: int = 0,
    command: str = "",
    path: Path | None = None,
) -> ProverUxIssue:
    return ProverUxIssue(
        severity=severity,
        code=code,
        message=message,
        proof_id=artifact.summary.proof_id,
        lemma=artifact.summary.lemma,
        step=step,
        command=command,
        artifact=str(path or artifact.proof_dir),
    )




def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--artifact-root",
        required=True,
        help="Manager replay artifact root to audit.",
    )
    ap.add_argument(
        "--max-issues",
        type=int,
        default=80,
        help="Maximum issues to print in text mode.",
    )
    ap.add_argument(
        "--json",
        action="store_true",
        help="Print the full JSON report.",
    )
    ap.add_argument(
        "--no-write-report",
        action="store_true",
        help="Do not write prover_ux_report.json under the artifact root.",
    )
    args = ap.parse_args(argv)

    root = Path(args.artifact_root)
    report = audit_replay_root(root)
    if not args.no_write_report:
        write_report(root, report)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(
            "PROVER-UX-AUDIT: "
            f"proofs={report['proofs_checked']} "
            f"executions={report['tactic_executions_checked']} "
            f"errors={report['error_count']} "
            f"warnings={report['warning_count']}"
        )
        for item in report["issues"][: max(0, args.max_issues)]:
            issue = ProverUxIssue(**item)
            print(issue.format())
        remaining = len(report["issues"]) - max(0, args.max_issues)
        if remaining > 0:
            print(f"... {remaining} more issues omitted")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
