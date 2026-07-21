"""Audit replay artifacts from the prover's point of view.

This audit historically treated each persisted CommandSummary as the UI a
prover agent saw after a mutating session command. Live runs now use
TacticExecutionResult; CommandSummary checks remain as a legacy audit path for
old traces and should not cause a new run to fail merely because no
CommandSummary sidecar was produced.
"""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from core.easycrypt.session_command_summary import (
    command_summary_action_partitions,
    validate_command_summary,
)
from core.easycrypt.session_events import events_of_type
from workflow.validation.replay_artifacts import (
    _read_json_object,
    _resolve_artifact_path,
)
from workflow.validation.replay_artifacts import (
    ReplayArtifact,
    iter_replay_artifacts,
    load_command_summary_artifacts,
)
from core.easycrypt.value_shapes import as_dict as _dict, as_list as _list


PLACEHOLDER_RE = re.compile(r"<(?!:)[^>\n]+>|\bLEMMA\b|\boracle_name\b")
CLI_COMMAND_RE = re.compile(
    r"(^\s*-|session_cli\.py|\bpython3\b|^Run `-|^run `-)",
    re.IGNORECASE,
)
PHOARE_BOUND_FALSE_POSITIVE_RE = re.compile(
    r"phoare[_ -]?bound|failure[- ]event|\bfel\b",
    re.IGNORECASE,
)


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
    summaries_checked = 0
    proofs_with_summaries = 0
    for artifact in artifacts:
        proof_summaries = [
            (item.path, item.summary)
            for item in load_command_summary_artifacts(artifact)
        ]
        if proof_summaries:
            proofs_with_summaries += 1
        summaries_checked += len(proof_summaries)
        issues.extend(_audit_artifact_level(artifact, proof_summaries))
        for idx, (path, summary) in enumerate(proof_summaries, start=1):
            issues.extend(_audit_command_summary(
                summary,
                artifact=artifact,
                artifact_path=path,
                step=idx,
            ))
    return _report(
        root=root,
        proof_count=len(artifacts),
        proofs_with_summaries=proofs_with_summaries,
        summaries_checked=summaries_checked,
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
    proof_summaries: list[tuple[Path, dict[str, Any]]],
) -> list[ProverUxIssue]:
    issues: list[ProverUxIssue] = []
    expected = artifact.audit_report.command_counts.get("next", 0)
    produced = len(proof_summaries)
    summary_events = len(events_of_type(artifact.events, "command.summary.produced"))
    tactic_execution_events = len(events_of_type(
        artifact.events,
        "tactic.execution.produced",
    ))
    commit_events = len(events_of_type(artifact.events, "commit.response.produced"))
    if expected and produced == 0 and tactic_execution_events == 0:
        issues.append(_issue(
            "error",
            "missing_command_summaries",
            (
                f"{expected} mutating replay commands but neither legacy "
                "CommandSummary nor live TacticExecutionResult artifacts"
            ),
            artifact,
        ))
    if summary_events and produced != summary_events:
        issues.append(_issue(
            "error",
            "command_summary_event_artifact_mismatch",
            f"{summary_events} summary events but {produced} readable artifacts",
            artifact,
        ))
    if commit_events and summary_events and commit_events != summary_events:
        issues.append(_issue(
            "error",
            "commit_summary_count_mismatch",
            f"{commit_events} CommitResponse events but {summary_events} CommandSummary events",
            artifact,
        ))
    return issues


def _audit_command_summary(
    summary: dict[str, Any],
    *,
    artifact: ReplayArtifact,
    artifact_path: Path,
    step: int,
) -> list[ProverUxIssue]:
    issues: list[ProverUxIssue] = []
    command = str(summary.get("command") or "")
    validation = validate_command_summary(summary)
    for err in validation.errors:
        issues.append(_issue(
            "error",
            "command_summary_contract",
            err,
            artifact,
            step=step,
            command=command,
            path=artifact_path,
        ))
    for warn in validation.warnings:
        issues.append(_issue(
            "warning",
            "command_summary_contract_warning",
            warn,
            artifact,
            step=step,
            command=command,
            path=artifact_path,
        ))

    proof = _dict(summary.get("proof"))
    mutation = _dict(summary.get("mutation"))
    transition = _dict(summary.get("transition"))
    current_goal = _dict(summary.get("current_goal"))
    action_partitions = command_summary_action_partitions(summary)
    errors = _list(summary.get("errors"))
    latest_errors = _list(summary.get("latest_errors"))
    warnings = _list(summary.get("warnings"))

    proof_status = str(proof.get("status") or "")
    command_status = str(summary.get("command_status") or "")
    primary = str(action_partitions.get("primary_action") or "")
    commit_actions = _list(action_partitions.get("commit_actions"))
    inspections = _list(action_partitions.get("inspect_actions"))
    strategy_actions = _list(action_partitions.get("strategy_actions"))
    recs = _list(action_partitions.get("recommendations"))
    actions = _list(action_partitions.get("actions"))

    if proof.get("event_contract_ok") is False or proof.get("consistency_ok") is False:
        if summary.get("ok") is True:
            issues.append(_issue(
                "error",
                "contract_error_not_fail_closed",
                "summary ok=true even though event/consistency contract is false",
                artifact,
                step=step,
                command=command,
                path=artifact_path,
            ))
        if primary not in {"diagnose", "inspect", "status"}:
            issues.append(_issue(
                "error",
                "contract_error_wrong_primary_action",
                f"primary_action={primary!r} does not direct the prover to inspect/diagnose",
                artifact,
                step=step,
                command=command,
                path=artifact_path,
            ))

    if summary.get("ok") is True and errors:
        issues.append(_issue(
            "error",
            "ok_summary_has_errors",
            "ok=true summary exposes non-empty errors",
            artifact,
            step=step,
            command=command,
            path=artifact_path,
        ))

    failed = (
        summary.get("ok") is False
        or command_status == "error"
        or transition.get("status") == "error"
    )
    if failed:
        if primary != "diagnose":
            issues.append(_issue(
                "error",
                "failed_command_wrong_primary_action",
                f"failed command should point to diagnose, got {primary!r}",
                artifact,
                step=step,
                command=command,
                path=artifact_path,
            ))
        if not mutation.get("failed_tactic"):
            issues.append(_issue(
                "error",
                "failed_command_missing_tactic",
                "failed command does not identify the failed tactic",
                artifact,
                step=step,
                command=command,
                path=artifact_path,
            ))
        if not mutation.get("failure_reason") and not errors and not latest_errors:
            issues.append(_issue(
                "error",
                "failed_command_missing_reason",
                "failed command does not expose a reason in mutation/errors/latest_errors",
                artifact,
                step=step,
                command=command,
                path=artifact_path,
            ))

    if proof_status == "candidate_closed":
        if primary != "verify":
            issues.append(_issue(
                "error",
                "candidate_closed_wrong_primary_action",
                f"candidate_closed should point to verify, got {primary!r}",
                artifact,
                step=step,
                command=command,
                path=artifact_path,
            ))
        _closed_no_suggestions(
            issues,
            artifact,
            artifact_path,
            step,
            command,
            commit_actions=commit_actions,
            strategy_actions=strategy_actions,
            recs=recs,
            actions=actions,
            allow_verify=True,
        )
    elif proof_status == "verified":
        if primary != "none":
            issues.append(_issue(
                "error",
                "verified_wrong_primary_action",
                f"verified proof should have primary_action='none', got {primary!r}",
                artifact,
                step=step,
                command=command,
                path=artifact_path,
            ))
        _closed_no_suggestions(
            issues,
            artifact,
            artifact_path,
            step,
            command,
            commit_actions=commit_actions,
            strategy_actions=strategy_actions,
            recs=recs,
            actions=actions,
            allow_verify=False,
        )
    elif proof_status == "open" and summary.get("ok") is True:
        if not str(current_goal.get("preview") or "").strip():
            issues.append(_issue(
                "warning",
                "open_state_missing_goal_preview",
                "open proof has no active goal preview in the summary",
                artifact,
                step=step,
                command=command,
                path=artifact_path,
            ))
        if not (
            actions
            or commit_actions
            or inspections
            or strategy_actions
        ):
            issues.append(_issue(
                "warning",
                "open_state_has_no_next_action",
                "open proof exposes no action, commit tactic, inspection action, or strategy hint",
                artifact,
                step=step,
                command=command,
                path=artifact_path,
            ))

    issues.extend(_audit_primary_action(
        artifact,
        artifact_path,
        step,
        command,
        primary=primary,
        commit_actions=commit_actions,
        inspections=inspections,
        strategy_actions=strategy_actions,
        actions=actions,
    ))
    issues.extend(_audit_prover_actions(
        artifact,
        artifact_path,
        step,
        command,
        primary=primary,
        actions=actions,
    ))
    issues.extend(_audit_action_cleanliness(
        artifact,
        artifact_path,
        step,
        command,
        action_partitions=action_partitions,
    ))
    issues.extend(_audit_known_misleading_patterns(
        artifact,
        artifact_path,
        step,
        command,
        current_goal=current_goal,
        action_partitions=action_partitions,
    ))
    issues.extend(_audit_evidence_links(
        artifact,
        artifact_path,
        step,
        command,
        summary=summary,
    ))

    if transition.get("no_progress") is True:
        reason = str(transition.get("no_progress_reason") or "")
        if not reason and not warnings:
            issues.append(_issue(
                "warning",
                "no_progress_missing_reason",
                "transition.no_progress=true but no reason/warning is exposed",
                artifact,
                step=step,
                command=command,
                path=artifact_path,
            ))
    return issues


def _closed_no_suggestions(
    issues: list[ProverUxIssue],
    artifact: ReplayArtifact,
    path: Path,
    step: int,
    command: str,
    *,
    commit_actions: list[Any],
    strategy_actions: list[Any],
    recs: list[Any],
    actions: list[Any],
    allow_verify: bool,
) -> None:
    if commit_actions:
        issues.append(_issue(
            "error",
            "closed_state_has_commit_actions",
            "closed proof exposes commit tactic suggestions",
            artifact,
            step=step,
            command=command,
            path=path,
        ))
    if strategy_actions:
        issues.append(_issue(
            "error",
            "closed_state_has_strategy_actions",
            "closed proof exposes strategy actions instead of stopping",
            artifact,
            step=step,
            command=command,
            path=path,
        ))
    if recs:
        issues.append(_issue(
            "error",
            "closed_state_has_legacy_recommendations",
            "closed proof exposes compatibility recommendations",
            artifact,
            step=step,
            command=command,
            path=path,
        ))
    if not allow_verify and (commit_actions or strategy_actions or recs):
        return
    bad_actions = [
        action for action in actions
        if _dict(action).get("category") in {"commit", "strategy"}
    ]
    if bad_actions:
        issues.append(_issue(
            "error",
            "closed_state_has_action_suggestions",
            "closed proof exposes commit/strategy actions",
            artifact,
            step=step,
            command=command,
            path=path,
        ))


def _audit_primary_action(
    artifact: ReplayArtifact,
    path: Path,
    step: int,
    command: str,
    *,
    primary: str,
    commit_actions: list[Any],
    inspections: list[Any],
    strategy_actions: list[Any],
    actions: list[Any],
) -> list[ProverUxIssue]:
    issues: list[ProverUxIssue] = []
    if primary and not actions:
        issues.append(_issue(
            "warning",
            "primary_action_without_unified_actions",
            "primary_action is set but the derived decision action menu is empty",
            artifact,
            step=step,
            command=command,
            path=path,
        ))
    if primary == "try_tactic" and not commit_actions:
        issues.append(_issue(
            "error",
            "primary_try_tactic_without_tactic",
            "primary_action=try_tactic but commit_actions is empty",
            artifact,
            step=step,
            command=command,
            path=path,
        ))
    if primary == "consider_strategy_hint" and not strategy_actions:
        issues.append(_issue(
            "error",
            "primary_strategy_without_hint",
            "primary_action=consider_strategy_hint but strategy_actions is empty",
            artifact,
            step=step,
            command=command,
            path=path,
        ))
    if primary == "inspect" and not inspections:
        issues.append(_issue(
            "warning",
            "primary_inspect_without_action",
            "primary_action=inspect but inspect_actions is empty",
            artifact,
            step=step,
            command=command,
            path=path,
        ))
    return issues


def _audit_prover_actions(
    artifact: ReplayArtifact,
    path: Path,
    step: int,
    command: str,
    *,
    primary: str,
    actions: list[Any],
) -> list[ProverUxIssue]:
    issues: list[ProverUxIssue] = []
    for idx, raw in enumerate(actions):
        action = _dict(raw)
        category = str(action.get("category") or "")
        cmd = str(action.get("command") or "")
        state_changed = action.get("state_changed")
        if category == "probe":
            issues.append(_issue(
                "error",
                "public_probe_action",
                f"derived action[{idx}] exposes the retired probe category",
                artifact,
                step=step,
                command=command,
                path=path,
            ))
        if category == "commit" and "-try" in cmd:
            issues.append(_issue(
                "warning",
                "commit_action_uses_try_command",
                f"derived action[{idx}] is a commit but command contains -try",
                artifact,
                step=step,
                command=command,
                path=path,
            ))
        if category in {"strategy", "avoid", "inspect", "diagnose", "verify"}:
            if state_changed is True:
                issues.append(_issue(
                    "error",
                    "non_commit_action_mutates_state",
                    f"derived action[{idx}] category={category!r} unexpectedly mutates state",
                    artifact,
                    step=step,
                    command=command,
                    path=path,
                ))
    return issues


def _audit_action_cleanliness(
    artifact: ReplayArtifact,
    path: Path,
    step: int,
    command: str,
    *,
    action_partitions: dict[str, Any],
) -> list[ProverUxIssue]:
    issues: list[ProverUxIssue] = []
    for idx, item in enumerate(_list(action_partitions.get("commit_actions"))):
        tactic = str(_dict(item).get("tactic") or "")
        if not tactic.strip():
            issues.append(_issue(
                "error",
                "empty_commit_action_tactic",
                f"commit_actions[{idx}] has no tactic",
                artifact,
                step=step,
                command=command,
                path=path,
            ))
            continue
        if PLACEHOLDER_RE.search(tactic) or CLI_COMMAND_RE.search(tactic):
            issues.append(_issue(
                "error",
                "non_runnable_item_in_commit_actions",
                f"commit_actions[{idx}] is not immediately runnable: {tactic!r}",
                artifact,
                step=step,
                command=command,
                path=path,
            ))
    for idx, item in enumerate(_list(action_partitions.get("inspect_actions"))):
        data = _dict(item)
        cmd = str(data.get("command") or data.get("action") or "")
        if cmd and PLACEHOLDER_RE.search(cmd) and not data.get("requires_instantiation"):
            issues.append(_issue(
                "error",
                "inspection_placeholder_not_marked",
                f"inspect_actions[{idx}] has placeholders but requires_instantiation=false",
                artifact,
                step=step,
                command=command,
                path=path,
            ))
        if not (cmd or data.get("tool") or data.get("kind")):
            issues.append(_issue(
                "warning",
                "inspection_action_missing_command",
                f"inspect_actions[{idx}] has no command, tool, or kind",
                artifact,
                step=step,
                command=command,
                path=path,
            ))
    for idx, item in enumerate(_list(action_partitions.get("strategy_actions"))):
        data = _dict(item)
        msg = str(data.get("message") or "")
        if not msg.strip():
            issues.append(_issue(
                "error",
                "empty_strategy_action",
                f"strategy_actions[{idx}] has no message",
                artifact,
                step=step,
                command=command,
                path=path,
            ))
        if PLACEHOLDER_RE.search(msg) and not data.get("requires_instantiation"):
            issues.append(_issue(
                "error",
                "strategy_placeholder_not_marked",
                f"strategy_actions[{idx}] has placeholders but requires_instantiation=false",
                artifact,
                step=step,
                command=command,
                path=path,
            ))
    for idx, item in enumerate(_list(action_partitions.get("recommendations"))):
        category = str(_dict(item).get("category") or "")
        if category not in {
            "runnable_tactic",
            "inspection_action",
            "strategy_hint",
            "warning",
        }:
            issues.append(_issue(
                "warning",
                "legacy_recommendation_missing_category",
                f"recommendations[{idx}] has unknown category {category!r}",
                artifact,
                step=step,
                command=command,
                path=path,
            ))
    for idx, item in enumerate(_list(action_partitions.get("safe_actions"))):
        data = _dict(item)
        action = str(data.get("action") or "")
        if not action or not PLACEHOLDER_RE.search(action):
            continue
        if not data.get("requires_instantiation"):
            issues.append(_issue(
                "error",
                "safe_action_placeholder_not_marked",
                f"safe_next_actions[{idx}] has placeholders but requires_instantiation=false",
                artifact,
                step=step,
                command=command,
                path=path,
            ))
        if str(data.get("kind") or "") == "consider_recommendation":
            issues.append(_issue(
                "error",
                "safe_action_placeholder_marked_runnable",
                f"safe_next_actions[{idx}] treats placeholder guidance as directly usable",
                artifact,
                step=step,
                command=command,
                path=path,
            ))
    return issues


def _audit_known_misleading_patterns(
    artifact: ReplayArtifact,
    path: Path,
    step: int,
    command: str,
    *,
    current_goal: dict[str, Any],
    action_partitions: dict[str, Any],
) -> list[ProverUxIssue]:
    issues: list[ProverUxIssue] = []
    preview = str(current_goal.get("preview") or "")
    if "[=]" in preview and "1%r" in preview and "<=" not in preview:
        combined = "\n".join(_walk_strings(action_partitions))
        if PHOARE_BOUND_FALSE_POSITIVE_RE.search(combined):
            issues.append(_issue(
                "error",
                "phoare_equality_bound_false_positive",
                "phoare equality goal is receiving failure-event/bound guidance",
                artifact,
                step=step,
                command=command,
                path=path,
            ))
    return issues


def _audit_evidence_links(
    artifact: ReplayArtifact,
    path: Path,
    step: int,
    command: str,
    *,
    summary: dict[str, Any],
) -> list[ProverUxIssue]:
    issues: list[ProverUxIssue] = []
    action_partitions = command_summary_action_partitions(summary)
    has_guidance = any(
        _list(action_partitions.get(key))
        for key in ("commit_actions", "strategy_actions", "inspect_actions")
    )
    artifacts = _dict(summary.get("artifacts"))
    if not artifacts.get("commit_response"):
        issues.append(_issue(
            "warning",
            "missing_commit_response_link",
            "CommandSummary does not link back to its CommitResponse artifact",
            artifact,
            step=step,
            command=command,
            path=path,
        ))
    if not has_guidance:
        return issues
    agent_view_path = _resolve_artifact_path(
        artifact.proof_dir,
        str(artifacts.get("agent_view") or ""),
        copied_subdir="proof_context_views",
    )
    if agent_view_path is None:
        agent_view_path = _resolve_artifact_path(
            artifact.proof_dir,
            str(artifacts.get("agent_view") or ""),
            copied_subdir="agent_views",
        )
    if agent_view_path is None:
        issues.append(_issue(
            "warning",
            "missing_agent_view_evidence_link",
            "guidance is present but the linked ProofContextView artifact is unavailable",
            artifact,
            step=step,
            command=command,
            path=path,
        ))
        return issues
    agent_view = _read_json_object(agent_view_path)
    debug = _dict(summary.get("debug"))
    active_count = int(debug.get("active_recommendation_count") or 0)
    if active_count and not _has_nonempty_evidence(_dict(agent_view.get("evidence"))):
        issues.append(_issue(
            "warning",
            "active_guidance_without_evidence",
            "active recommendations are present but ProofContextView evidence is empty",
            artifact,
            step=step,
            command=command,
            path=path,
        ))
    return issues


def _has_nonempty_evidence(evidence: dict[str, Any]) -> bool:
    for value in evidence.values():
        if isinstance(value, list) and value:
            return True
        if isinstance(value, dict) and value:
            return True
    return False


def _walk_strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _walk_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_strings(item)


def _report(
    *,
    root: Path,
    proof_count: int,
    proofs_with_summaries: int,
    summaries_checked: int,
    issues: list[ProverUxIssue],
) -> dict[str, Any]:
    errors = [issue for issue in issues if issue.severity == "error"]
    warnings = [issue for issue in issues if issue.severity == "warning"]
    notes = [issue for issue in issues if issue.severity == "note"]
    return {
        "schema_version": 1,
        "kind": "prover_ux_audit",
        "ok": not errors,
        "artifact_root": str(Path(root).resolve()),
        "proofs_checked": proof_count,
        "proofs_with_command_summaries": proofs_with_summaries,
        "command_summaries_checked": summaries_checked,
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
        help="Replay artifact root produced by workflow.validation.proof_replay.",
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
            f"summaries={report['command_summaries_checked']} "
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
