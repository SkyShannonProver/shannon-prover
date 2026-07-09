"""Typed readers for proof replay artifacts.

The replay harness writes JSON files for humans and downstream tools. This
module is the single read boundary for those files so callers do not have to
know every key in ``summary.json`` / ``audit_report.json`` or reimplement
event-log parsing.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from core.easycrypt.session_events import (
    event_payload,
    read_event_file,
)


@dataclass(frozen=True)
class ReplaySummary:
    proof_id: str = ""
    file: str = ""
    lemma: str = ""
    tactic_count: int = 0
    replayed_tactic_count: int = 0
    outcome: str = ""
    consistency_warnings: int = 0
    event_counts: dict[str, int] = field(default_factory=dict)
    artifact_dir: str = ""
    session_dir: str = ""
    runner: str = ""
    full_hooks: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "ReplaySummary":
        data = data or {}
        return cls(
            proof_id=str(data.get("proof_id") or ""),
            file=str(data.get("file") or ""),
            lemma=str(data.get("lemma") or ""),
            tactic_count=_as_int(data.get("tactic_count")),
            replayed_tactic_count=_as_int(data.get("replayed_tactic_count")),
            outcome=str(data.get("outcome") or ""),
            consistency_warnings=_as_int(data.get("consistency_warnings")),
            event_counts=_int_dict(data.get("event_counts")),
            artifact_dir=str(data.get("artifact_dir") or ""),
            session_dir=str(data.get("session_dir") or ""),
            runner=str(data.get("runner") or ""),
            full_hooks=bool(data.get("full_hooks")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "proof_id": self.proof_id,
            "file": self.file,
            "lemma": self.lemma,
            "tactic_count": self.tactic_count,
            "replayed_tactic_count": self.replayed_tactic_count,
            "outcome": self.outcome,
            "consistency_warnings": self.consistency_warnings,
            "event_counts": dict(self.event_counts),
            "artifact_dir": self.artifact_dir,
            "session_dir": self.session_dir,
            "runner": self.runner,
            "full_hooks": self.full_hooks,
        }

    @property
    def passed(self) -> bool:
        return self.outcome == "PASS" and self.consistency_warnings == 0


@dataclass(frozen=True)
class AuditReport:
    warnings: list[str] = field(default_factory=list)
    event_contract_errors: int = 0
    event_contract_warnings: int = 0
    tool_view_checked: int = 0
    tool_view_errors: int = 0
    tool_view_warnings: int = 0
    agent_view_checked: int = 0
    agent_view_errors: int = 0
    agent_view_warnings: int = 0
    commit_response_checked: int = 0
    commit_response_errors: int = 0
    commit_response_warnings: int = 0
    command_summary_checked: int = 0
    command_summary_errors: int = 0
    command_summary_warnings: int = 0
    episode_timeline_checked: int = 0
    episode_timeline_errors: int = 0
    episode_timeline_warnings: int = 0
    structured_diagnostic_checked: int = 0
    structured_diagnostic_errors: int = 0
    structured_diagnostic_warnings: int = 0
    event_contract: dict[str, Any] = field(default_factory=dict)
    proof_state: dict[str, Any] = field(default_factory=dict)
    event_counts: dict[str, int] = field(default_factory=dict)
    command_counts: dict[str, int] = field(default_factory=dict)
    tactic_status_counts: dict[str, int] = field(default_factory=dict)
    closed_text_steps: list[Any] = field(default_factory=list)
    candidate_closed_events: int = 0
    verification_status: str | None = None
    failed_next: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "AuditReport":
        data = data or {}
        return cls(
            warnings=[str(x) for x in data.get("warnings") or []],
            event_contract_errors=_as_int(data.get("event_contract_errors")),
            event_contract_warnings=_as_int(data.get("event_contract_warnings")),
            tool_view_checked=_as_int(data.get("tool_view_checked")),
            tool_view_errors=_as_int(data.get("tool_view_errors")),
            tool_view_warnings=_as_int(data.get("tool_view_warnings")),
            agent_view_checked=_as_int(data.get("agent_view_checked")),
            agent_view_errors=_as_int(data.get("agent_view_errors")),
            agent_view_warnings=_as_int(data.get("agent_view_warnings")),
            commit_response_checked=_as_int(data.get("commit_response_checked")),
            commit_response_errors=_as_int(data.get("commit_response_errors")),
            commit_response_warnings=_as_int(data.get("commit_response_warnings")),
            command_summary_checked=_as_int(data.get("command_summary_checked")),
            command_summary_errors=_as_int(data.get("command_summary_errors")),
            command_summary_warnings=_as_int(data.get("command_summary_warnings")),
            episode_timeline_checked=_as_int(data.get("episode_timeline_checked")),
            episode_timeline_errors=_as_int(data.get("episode_timeline_errors")),
            episode_timeline_warnings=_as_int(
                data.get("episode_timeline_warnings")
            ),
            structured_diagnostic_checked=_as_int(
                data.get("structured_diagnostic_checked")
            ),
            structured_diagnostic_errors=_as_int(
                data.get("structured_diagnostic_errors")
            ),
            structured_diagnostic_warnings=_as_int(
                data.get("structured_diagnostic_warnings")
            ),
            event_contract=(
                dict(data.get("event_contract"))
                if isinstance(data.get("event_contract"), dict)
                else {}
            ),
            proof_state=(
                dict(data.get("proof_state"))
                if isinstance(data.get("proof_state"), dict)
                else {}
            ),
            event_counts=_int_dict(data.get("event_counts")),
            command_counts=_int_dict(data.get("command_counts")),
            tactic_status_counts=_int_dict(data.get("tactic_status_counts")),
            closed_text_steps=list(data.get("closed_text_steps") or []),
            candidate_closed_events=_as_int(data.get("candidate_closed_events")),
            verification_status=(
                None if data.get("verification_status") is None
                else str(data.get("verification_status"))
            ),
            failed_next=[
                dict(x) for x in data.get("failed_next") or []
                if isinstance(x, dict)
            ],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "warnings": list(self.warnings),
            "event_contract_errors": self.event_contract_errors,
            "event_contract_warnings": self.event_contract_warnings,
            "tool_view_checked": self.tool_view_checked,
            "tool_view_errors": self.tool_view_errors,
            "tool_view_warnings": self.tool_view_warnings,
            "agent_view_checked": self.agent_view_checked,
            "agent_view_errors": self.agent_view_errors,
            "agent_view_warnings": self.agent_view_warnings,
            "commit_response_checked": self.commit_response_checked,
            "commit_response_errors": self.commit_response_errors,
            "commit_response_warnings": self.commit_response_warnings,
            "command_summary_checked": self.command_summary_checked,
            "command_summary_errors": self.command_summary_errors,
            "command_summary_warnings": self.command_summary_warnings,
            "episode_timeline_checked": self.episode_timeline_checked,
            "episode_timeline_errors": self.episode_timeline_errors,
            "episode_timeline_warnings": self.episode_timeline_warnings,
            "structured_diagnostic_checked": self.structured_diagnostic_checked,
            "structured_diagnostic_errors": self.structured_diagnostic_errors,
            "structured_diagnostic_warnings": self.structured_diagnostic_warnings,
            "event_contract": dict(self.event_contract),
            "proof_state": dict(self.proof_state),
            "event_counts": dict(self.event_counts),
            "command_counts": dict(self.command_counts),
            "tactic_status_counts": dict(self.tactic_status_counts),
            "closed_text_steps": list(self.closed_text_steps),
            "candidate_closed_events": self.candidate_closed_events,
            "verification_status": self.verification_status,
            "failed_next": list(self.failed_next),
        }

    @property
    def audit_tool_calls(self) -> int:
        return self.command_counts.get("audit_tool", 0)


@dataclass(frozen=True)
class ReplayArtifact:
    proof_dir: Path
    summary: ReplaySummary
    audit_report: AuditReport
    commands: list[dict[str, Any]]
    events: list[dict[str, Any]]

    @property
    def ok(self) -> bool:
        return self.summary.passed and not self.audit_report.warnings


@dataclass(frozen=True)
class CommandSummaryArtifact:
    path: Path
    summary: dict[str, Any]
    event: dict[str, Any] | None = None
    event_index: int = 0


def load_replay_summary(path: Path) -> ReplaySummary:
    return ReplaySummary.from_dict(_read_json_object(path))


def load_audit_report(path: Path) -> AuditReport:
    return AuditReport.from_dict(_read_json_object(path))


def load_replay_artifact(proof_dir: Path) -> ReplayArtifact:
    proof_dir = Path(proof_dir)
    return ReplayArtifact(
        proof_dir=proof_dir,
        summary=load_replay_summary(proof_dir / "summary.json"),
        audit_report=load_audit_report(proof_dir / "audit_report.json"),
        commands=_read_json_list(proof_dir / "commands.json"),
        events=read_event_file(proof_dir / "events.jsonl"),
    )


def load_root_summaries(root: Path) -> list[ReplaySummary]:
    raw = _read_json(root / "summary.json", default=[])
    if isinstance(raw, list):
        return [
            ReplaySummary.from_dict(item)
            for item in raw
            if isinstance(item, dict)
        ]
    if isinstance(raw, dict):
        return [ReplaySummary.from_dict(raw)]
    return []


def iter_replay_artifacts(root: Path) -> Iterable[ReplayArtifact]:
    """Yield proof artifacts below a replay root.

    Prefer the root ``summary.json`` list when present because it records the
    intended proof directories. Fall back to scanning child directories.
    """
    root = Path(root)
    seen: set[Path] = set()
    for summary in load_root_summaries(root):
        if not summary.artifact_dir:
            continue
        proof_dir = Path(summary.artifact_dir)
        if proof_dir in seen or not (proof_dir / "summary.json").exists():
            continue
        seen.add(proof_dir)
        yield load_replay_artifact(proof_dir)

    for child in sorted(root.iterdir()) if root.exists() else []:
        if not child.is_dir() or child in seen:
            continue
        if (child / "summary.json").exists():
            seen.add(child)
            yield load_replay_artifact(child)


def load_command_summary_artifacts(
    artifact: ReplayArtifact,
) -> list[CommandSummaryArtifact]:
    """Load CommandSummary artifacts in event order.

    Summary filenames include hashes and are not a chronological ordering.
    Prefer ``command.summary.produced`` event order, then append any orphaned
    files as a compatibility fallback.
    """
    out: list[CommandSummaryArtifact] = []
    seen: set[Path] = set()
    for idx, event in enumerate(artifact.events, start=1):
        if event.get("type") != "command.summary.produced":
            continue
        payload = event_payload(event)
        path = _resolve_artifact_path(
            artifact.proof_dir,
            str(payload.get("artifact") or ""),
            copied_subdir="command_summaries",
        )
        if path is None or path in seen:
            continue
        data = _read_json_object(path)
        if data:
            out.append(CommandSummaryArtifact(
                path=path,
                summary=data,
                event=event,
                event_index=idx,
            ))
            seen.add(path)

    summary_dir = artifact.proof_dir / "command_summaries"
    if summary_dir.exists():
        for path in sorted(summary_dir.glob("*.json")):
            if path in seen:
                continue
            data = _read_json_object(path)
            if data:
                out.append(CommandSummaryArtifact(path=path, summary=data))
                seen.add(path)
    return out



def _read_json(path: Path, *, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _read_json_object(path: Path) -> dict[str, Any]:
    data = _read_json(path, default={})
    return data if isinstance(data, dict) else {}


def _read_json_list(path: Path) -> list[dict[str, Any]]:
    data = _read_json(path, default=[])
    if not isinstance(data, list):
        return []
    return [dict(item) for item in data if isinstance(item, dict)]


def _resolve_artifact_path(
    proof_dir: Path,
    value: str,
    *,
    copied_subdir: str,
) -> Path | None:
    if value:
        direct = Path(value)
        if direct.exists():
            return direct
        copied = proof_dir / copied_subdir / direct.name
        if copied.exists():
            return copied
        if not direct.is_absolute():
            relative = proof_dir / direct
            if relative.exists():
                return relative
    return None


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except Exception:
        return 0


def _int_dict(value: Any) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    return {str(k): _as_int(v) for k, v in value.items()}


def dig(value: Any, *keys: str) -> Any:
    """Walk nested dicts by key; None on any non-dict hop."""
    cur = value
    for key in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def node_id_from_dir(path: Path) -> str:
    """``Tree_0_1`` dir -> ``Tree-0.1`` node id (validation CLIs share this)."""
    name = path.name
    if name.startswith("Tree_"):
        return "Tree-" + name[len("Tree_"):].replace("_", ".")
    return name.replace("_", ".")
