"""Audit prover behavior signals from EDA replay or live session artifacts.

This is not a proof checker. It answers a different question: given the
structured event stream and CommandSummary panels the prover saw, did the
interaction look healthy? The report is meant for regression experiments and
live Claude subagent runs:

* which tools were called, and how often
* whether structured next-action guidance was followed
* whether failures led to diagnosis
* whether candidate-closed states led to verification
* which proof/tactic failure categories appeared
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from core.easycrypt.session_command_summary import command_summary_action_partitions
from core.easycrypt.session_events import event_payload, read_event_file
from workflow.validation.replay_artifacts import (
    ReplayArtifact,
    iter_replay_artifacts,
    load_command_summary_artifacts,
)
from core.easycrypt.value_shapes import as_dict as _dict, as_list as _list


BEHAVIOR_AUDIT_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class BehaviorIssue:
    severity: str
    code: str
    message: str
    proof_id: str = ""
    lemma: str = ""
    step: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "proof_id": self.proof_id,
            "lemma": self.lemma,
            "step": self.step,
        }


@dataclass
class BehaviorSource:
    proof_id: str
    lemma: str
    path: Path
    outcome: str
    events: list[dict[str, Any]]
    command_summaries: list[tuple[Path, dict[str, Any], int]]


@dataclass
class BehaviorAccumulator:
    source_count: int = 0
    command_summary_count: int = 0
    proof_outcomes: Counter[str] = field(default_factory=Counter)
    tool_calls: Counter[str] = field(default_factory=Counter)
    read_only_tool_calls: Counter[str] = field(default_factory=Counter)
    mutating_tool_calls: Counter[str] = field(default_factory=Counter)
    tool_result_status: Counter[str] = field(default_factory=Counter)
    primary_actions: Counter[str] = field(default_factory=Counter)
    transition_kinds: Counter[str] = field(default_factory=Counter)
    goal_types: Counter[str] = field(default_factory=Counter)
    tactic_statuses: Counter[str] = field(default_factory=Counter)
    no_progress_count: int = 0
    runnable_steps: int = 0
    runnable_followed_exact: int = 0
    inspect_steps: int = 0
    inspect_followed_by_tool: int = 0
    failed_steps: int = 0
    failed_followed_by_diagnose: int = 0
    candidate_closed_steps: int = 0
    candidate_closed_followed_by_verify: int = 0
    repeated_read_only_tool_calls: list[dict[str, Any]] = field(default_factory=list)
    # Per-producer recommendation outcome tracking. ``recs_offered_by_producer``
    # is the denominator (every non-empty commit action adds 1 to its producer's
    # count). ``recs_adopted_by_producer`` is the
    # numerator (the next summary's mutation matched this producer's rec
    # text exactly). ``adoption_outcomes`` classifies the downstream
    # behavior so we can spot recs that are "verified by daemon but
    # strategy-poor" — see ``_classify_adoption_outcome``.
    # ``ignored_commit_recommendations``
    # records cases where a verified rec was on the panel but the agent
    # committed something else, which is the strongest signal that the
    # rec's ranking / why-rationale needs improvement.
    recs_offered_by_producer: Counter[str] = field(default_factory=Counter)
    recs_adopted_by_producer: Counter[str] = field(default_factory=Counter)
    adoption_outcomes: Counter[str] = field(default_factory=Counter)
    ignored_commit_recommendations: list[dict[str, Any]] = field(default_factory=list)
    issues: list[BehaviorIssue] = field(default_factory=list)
    per_source: list[dict[str, Any]] = field(default_factory=list)


def audit_path(path: Path) -> dict[str, Any]:
    path = Path(path)
    if _looks_like_session_dir(path):
        sources = [load_session_source(path)]
    else:
        sources = [
            _source_from_replay_artifact(artifact)
            for artifact in iter_replay_artifacts(path)
        ]
    return audit_sources(sources, root=path)


def audit_sources(
    sources: Iterable[BehaviorSource],
    *,
    root: Path,
) -> dict[str, Any]:
    acc = BehaviorAccumulator()
    for source in sources:
        acc.source_count += 1
        _audit_source(source, acc)
    return _report(acc, root=root)


def write_report(root: Path, report: dict[str, Any]) -> Path:
    path = Path(root) / "prover_behavior_report.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path



def load_session_source(session_dir: Path) -> BehaviorSource:
    session_dir = Path(session_dir)
    events = read_event_file(session_dir / "events.jsonl")
    lemma = ""
    for event in events:
        if event.get("type") == "session.started":
            lemma = str(event_payload(event).get("lemma") or "")
            break
    return BehaviorSource(
        proof_id=session_dir.name,
        lemma=lemma,
        path=session_dir,
        outcome="UNKNOWN",
        events=events,
        command_summaries=_load_command_summaries_from_session(session_dir, events),
    )


def _source_from_replay_artifact(artifact: ReplayArtifact) -> BehaviorSource:
    summaries = [
        (item.path, item.summary, item.event_index)
        for item in load_command_summary_artifacts(artifact)
    ]
    return BehaviorSource(
        proof_id=artifact.summary.proof_id or artifact.proof_dir.name,
        lemma=artifact.summary.lemma,
        path=artifact.proof_dir,
        outcome=artifact.summary.outcome,
        events=artifact.events,
        command_summaries=summaries,
    )


def _audit_source(source: BehaviorSource, acc: BehaviorAccumulator) -> None:
    acc.command_summary_count += len(source.command_summaries)
    acc.proof_outcomes[source.outcome or "UNKNOWN"] += 1
    per = {
        "proof_id": source.proof_id,
        "lemma": source.lemma,
        "path": str(source.path),
        "outcome": source.outcome,
        "command_summaries": len(source.command_summaries),
        "tool_calls": Counter(),
        "read_only_tool_calls": Counter(),
        "primary_actions": Counter(),
        "transition_kinds": Counter(),
        "issues": [],
    }

    summaries = source.command_summaries
    summary_event_indexes = [idx for _, _, idx in summaries]
    summaries_by_event = {
        idx: summary for _, summary, idx in summaries if idx
    }
    latest_summary_by_event = _latest_summary_lookup(
        summaries,
        event_count=len(source.events),
    )
    read_only_by_goal: dict[tuple[str, str], int] = defaultdict(int)

    for event_index, event in enumerate(source.events, start=1):
        typ = str(event.get("type") or "")
        payload = event_payload(event)
        if typ == "tool.called":
            name = str(payload.get("name") or "unknown")
            mutates = bool(payload.get("mutates_proof_state"))
            acc.tool_calls[name] += 1
            per["tool_calls"][name] += 1
            if mutates:
                acc.mutating_tool_calls[name] += 1
            else:
                acc.read_only_tool_calls[name] += 1
                per["read_only_tool_calls"][name] += 1
                goal_hash = _goal_hash_for_event(event_index, latest_summary_by_event)
                if goal_hash:
                    read_only_by_goal[(goal_hash, name)] += 1
        elif typ == "tool.result":
            name = str(payload.get("name") or "unknown")
            status = str(payload.get("status") or "")
            acc.tool_result_status[f"{name}:{status or 'unknown'}"] += 1
        elif typ == "tactic.result":
            status = str(payload.get("status") or "unknown")
            acc.tactic_statuses[status] += 1

    for (goal_hash, tool), count in sorted(read_only_by_goal.items()):
        if count <= 1:
            continue
        acc.repeated_read_only_tool_calls.append({
            "proof_id": source.proof_id,
            "lemma": source.lemma,
            "goal_hash": goal_hash,
            "tool": tool,
            "count": count,
        })

    for pos, (_path, summary, event_index) in enumerate(summaries):
        step = pos + 1
        proof = _dict(summary.get("proof"))
        transition = _dict(summary.get("transition"))
        action_partitions = command_summary_action_partitions(summary)
        mutation = _dict(summary.get("mutation"))
        status = str(proof.get("status") or "")
        primary = str(action_partitions.get("primary_action") or "")
        kind = str(transition.get("kind") or "")
        goal_type = str(proof.get("goal_type") or "")
        acc.primary_actions[primary or "unknown"] += 1
        acc.transition_kinds[kind or "unknown"] += 1
        acc.goal_types[goal_type or "unknown"] += 1
        per["primary_actions"][primary or "unknown"] += 1
        per["transition_kinds"][kind or "unknown"] += 1
        if transition.get("no_progress"):
            acc.no_progress_count += 1

        failed = (
            summary.get("ok") is False
            or str(summary.get("command_status") or "") == "error"
            or str(transition.get("status") or "") == "error"
            or bool(mutation.get("failed_tactic"))
        )
        if failed:
            acc.failed_steps += 1
            if _has_read_only_tool_between(
                source.events,
                "diagnose",
                start_event=event_index,
                end_event=_next_summary_event(summary_event_indexes, event_index),
            ):
                acc.failed_followed_by_diagnose += 1
            else:
                _add_issue(
                    acc, per, "warning", "failed_step_without_diagnose",
                    "failed command was not followed by -diagnose before the next summary",
                    source, step,
                )

        if status == "candidate_closed":
            acc.candidate_closed_steps += 1
            if _has_verify_after(source.events, event_index):
                acc.candidate_closed_followed_by_verify += 1
            else:
                _add_issue(
                    acc, per, "error", "candidate_closed_without_verify",
                    "candidate-closed summary was not followed by verification",
                    source, step,
                )

        commit_actions = _list(action_partitions.get("commit_actions"))
        commit_recs: list[dict[str, str]] = []
        for item in commit_actions:
            if not isinstance(item, dict):
                continue
            tac = _normalize_tactic(item.get("tactic"))
            if not tac:
                continue
            commit_recs.append({
                "id": str(item.get("id") or ""),
                "tactic": tac,
                "producer": str(item.get("producer") or ""),
                "confidence": str(item.get("confidence") or ""),
            })
        if commit_recs:
            acc.runnable_steps += 1
            for rec in commit_recs:
                if rec["producer"]:
                    acc.recs_offered_by_producer[rec["producer"]] += 1
            next_summary = summaries[pos + 1][1] if pos + 1 < len(summaries) else {}
            next_event_index = (
                summaries[pos + 1][2] if pos + 1 < len(summaries) else 0
            )
            next_tactic = _normalize_tactic(
                _dict(next_summary.get("transition")).get("tactic")
            )
            next_mutation = _dict(next_summary.get("mutation"))
            next_committed = bool(next_mutation.get("history_committed"))
            # Chain-aware adoption: tactic.submitted events in the window
            # between this summary and the next one give the FULL list of
            # tactics the agent attempted, not just the last one in
            # transition.tactic. Without this, a chain like
            # `chain byequiv=> //. proc.` records transition.tactic="proc."
            # only, so a rec for "byequiv=> //." would falsely look ignored.
            committed_tactics_window: list[str] = _committed_tactics_in_range(
                source.events, event_index, next_event_index,
            )
            matched_rec = None
            if committed_tactics_window:
                for rec in commit_recs:
                    if rec["tactic"] in committed_tactics_window:
                        matched_rec = rec
                        break
            elif next_committed:
                # Fallback: no event-window data (e.g., synthetic test
                # fixtures lacking tactic.submitted events). Use the
                # transition.tactic single-tactic match.
                matched_rec = next(
                    (r for r in commit_recs if r["tactic"] == next_tactic),
                    None,
                )
            if matched_rec is not None:
                acc.runnable_followed_exact += 1
                if matched_rec["producer"]:
                    acc.recs_adopted_by_producer[matched_rec["producer"]] += 1
                outcome = _classify_adoption_outcome(summaries, pos + 1)
                acc.adoption_outcomes[outcome] += 1
            elif (
                (committed_tactics_window or (next_committed and next_tactic))
                and commit_recs
            ):
                # Verified rec(s) were on the panel but the agent committed
                # something else. Record so we can study what
                # makes our recs unattractive (weaker than agent's choice?
                # poorly ranked? rationale unclear?).
                actual = (
                    "; ".join(committed_tactics_window)
                    if committed_tactics_window else next_tactic
                )
                acc.ignored_commit_recommendations.append({
                    "proof_id": source.proof_id,
                    "lemma": source.lemma,
                    "step": step,
                    "actual_commit": actual,
                    "ignored_recs": [
                        {
                            "producer": r["producer"],
                            "tactic": r["tactic"],
                            "confidence": r["confidence"],
                        }
                        for r in commit_recs
                    ],
                })

        if primary in {"inspect", "consider_strategy_hint"}:
            acc.inspect_steps += 1
            if _has_any_read_only_tool_between(
                source.events,
                start_event=event_index,
                end_event=_next_summary_event(summary_event_indexes, event_index),
            ):
                acc.inspect_followed_by_tool += 1

    per["tool_calls"] = dict(sorted(per["tool_calls"].items()))
    per["read_only_tool_calls"] = dict(sorted(per["read_only_tool_calls"].items()))
    per["primary_actions"] = dict(sorted(per["primary_actions"].items()))
    per["transition_kinds"] = dict(sorted(per["transition_kinds"].items()))
    acc.per_source.append(per)
    has_live_tactic_execution = any(
        event.get("type") == "tactic.execution.produced"
        for event in source.events
    )
    if not summaries and source.events and not has_live_tactic_execution:
        _add_issue(
            acc, per, "warning", "missing_command_summaries",
            (
                "events exist but neither legacy CommandSummary nor live "
                "TacticExecutionResult artifacts were readable"
            ),
            source, 0,
        )


def _report(acc: BehaviorAccumulator, *, root: Path) -> dict[str, Any]:
    errors = [issue for issue in acc.issues if issue.severity == "error"]
    warnings = [issue for issue in acc.issues if issue.severity == "warning"]
    return {
        "schema_version": BEHAVIOR_AUDIT_SCHEMA_VERSION,
        "kind": "prover_behavior_audit",
        "ok": not errors,
        "root": str(Path(root).resolve()),
        "proofs_checked": acc.source_count,
        "command_summaries_checked": acc.command_summary_count,
        "proof_outcomes": dict(sorted(acc.proof_outcomes.items())),
        "tool_usage": {
            "total_calls": sum(acc.tool_calls.values()),
            "read_only_calls": sum(acc.read_only_tool_calls.values()),
            "mutating_calls": sum(acc.mutating_tool_calls.values()),
            "by_name": dict(sorted(acc.tool_calls.items())),
            "read_only_by_name": dict(sorted(acc.read_only_tool_calls.items())),
            "mutating_by_name": dict(sorted(acc.mutating_tool_calls.items())),
            "result_status_by_name": dict(sorted(acc.tool_result_status.items())),
        },
        "command_summary_metrics": {
            "primary_actions": dict(sorted(acc.primary_actions.items())),
            "transition_kinds": dict(sorted(acc.transition_kinds.items())),
            "goal_types": dict(sorted(acc.goal_types.items())),
            "tactic_statuses": dict(sorted(acc.tactic_statuses.items())),
            "no_progress_count": acc.no_progress_count,
        },
        "guidance_follow_through": {
            "runnable_steps": acc.runnable_steps,
            "runnable_followed_exact": acc.runnable_followed_exact,
            "runnable_follow_rate": _rate(
                acc.runnable_followed_exact, acc.runnable_steps,
            ),
            "inspect_or_strategy_steps": acc.inspect_steps,
            "inspect_or_strategy_followed_by_read_only_tool": (
                acc.inspect_followed_by_tool
            ),
            "failed_steps": acc.failed_steps,
            "failed_followed_by_diagnose": acc.failed_followed_by_diagnose,
            "candidate_closed_steps": acc.candidate_closed_steps,
            "candidate_closed_followed_by_verify": (
                acc.candidate_closed_followed_by_verify
            ),
        },
        "recommendation_outcomes": {
            "recs_offered_total": sum(acc.recs_offered_by_producer.values()),
            "recs_offered_by_producer": dict(
                sorted(acc.recs_offered_by_producer.items())
            ),
            "recs_adopted_total": sum(acc.recs_adopted_by_producer.values()),
            "recs_adopted_by_producer": dict(
                sorted(acc.recs_adopted_by_producer.items())
            ),
            "adoption_rate_by_producer": {
                producer: _rate(
                    acc.recs_adopted_by_producer.get(producer, 0), offered,
                )
                for producer, offered in sorted(
                    acc.recs_offered_by_producer.items(),
                )
            },
            "adoption_outcomes": dict(sorted(acc.adoption_outcomes.items())),
            "ignored_commit_recommendations": (
                acc.ignored_commit_recommendations[:50]
            ),
        },
        "repeated_read_only_tool_calls": acc.repeated_read_only_tool_calls[:100],
        "error_count": len(errors),
        "warning_count": len(warnings),
        "issues": [issue.to_dict() for issue in acc.issues],
        "sources": acc.per_source,
    }


def _looks_like_session_dir(path: Path) -> bool:
    return (path / "events.jsonl").exists() and (
        (path / "command_summaries").exists()
        or not (path / "summary.json").exists()
    )


def _load_command_summaries_from_session(
    session_dir: Path,
    events: list[dict[str, Any]],
) -> list[tuple[Path, dict[str, Any], int]]:
    out: list[tuple[Path, dict[str, Any], int]] = []
    seen: set[Path] = set()
    for idx, event in enumerate(events, start=1):
        if event.get("type") != "command.summary.produced":
            continue
        path = _resolve_path(session_dir, str(event_payload(event).get("artifact") or ""))
        if path is None or path in seen:
            continue
        data = _read_json_object(path)
        if data:
            out.append((path, data, idx))
            seen.add(path)
    summary_dir = session_dir / "command_summaries"
    if summary_dir.exists():
        for path in sorted(summary_dir.glob("*.json")):
            if path in seen:
                continue
            data = _read_json_object(path)
            if data:
                out.append((path, data, 0))
                seen.add(path)
    return out


def _latest_summary_lookup(
    summaries: list[tuple[Path, dict[str, Any], int]],
    *,
    event_count: int,
) -> dict[int, dict[str, Any]]:
    by_event: dict[int, dict[str, Any]] = {}
    latest: dict[str, Any] = {}
    summary_iter = iter(sorted(
        [(idx, summary) for _path, summary, idx in summaries if idx],
        key=lambda item: item[0],
    ))
    try:
        current_idx, current_summary = next(summary_iter)
    except StopIteration:
        current_idx, current_summary = (0, {})
    max_idx = max(event_count, *[idx for _path, _summary, idx in summaries], 0)
    for idx in range(1, max_idx + 2):
        while current_idx and current_idx < idx:
            latest = current_summary
            try:
                current_idx, current_summary = next(summary_iter)
            except StopIteration:
                current_idx, current_summary = (0, {})
                break
        by_event[idx] = latest
    return by_event


def _goal_hash_for_event(
    event_index: int,
    latest_summary_by_event: dict[int, dict[str, Any]],
) -> str:
    summary = latest_summary_by_event.get(event_index) or {}
    return str(_dict(summary.get("proof")).get("goal_hash") or "")


def _next_summary_event(indexes: list[int], current: int) -> int:
    later = [idx for idx in indexes if idx and idx > current]
    return min(later) if later else 0


def _has_verify_after(events: list[dict[str, Any]], start_event: int) -> bool:
    for idx, event in enumerate(events, start=1):
        if idx <= start_event:
            continue
        typ = event.get("type")
        payload = event_payload(event)
        if typ == "verification.completed":
            return True
        if typ == "tool.called" and payload.get("name") == "verify":
            return True
    return False


def _has_read_only_tool_between(
    events: list[dict[str, Any]],
    tool_name: str,
    *,
    start_event: int,
    end_event: int,
) -> bool:
    for idx, event in enumerate(events, start=1):
        if idx <= start_event:
            continue
        if end_event and idx >= end_event:
            break
        if event.get("type") != "tool.called":
            continue
        payload = event_payload(event)
        if payload.get("name") == tool_name and not payload.get("mutates_proof_state"):
            return True
    return False


def _has_any_read_only_tool_between(
    events: list[dict[str, Any]],
    *,
    start_event: int,
    end_event: int,
) -> bool:
    for idx, event in enumerate(events, start=1):
        if idx <= start_event:
            continue
        if end_event and idx >= end_event:
            break
        if event.get("type") != "tool.called":
            continue
        payload = event_payload(event)
        if not payload.get("mutates_proof_state"):
            return True
    return False


def _add_issue(
    acc: BehaviorAccumulator,
    per: dict[str, Any],
    severity: str,
    code: str,
    message: str,
    source: BehaviorSource,
    step: int,
) -> None:
    issue = BehaviorIssue(
        severity=severity,
        code=code,
        message=message,
        proof_id=source.proof_id,
        lemma=source.lemma,
        step=step,
    )
    acc.issues.append(issue)
    per.setdefault("issues", []).append(issue.to_dict())


def _committed_tactics_in_range(
    events: list[dict[str, Any]],
    start_event_index: int,
    end_event_index: int,
) -> list[str]:
    """Collect normalized ``tactic.submitted`` payloads in the
    half-open event-index window ``(start_event_index, end_event_index]``.

    ``start_event_index`` is the index of the CommandSummary whose commit
    actions we are evaluating; ``end_event_index`` is the
    index of the NEXT CommandSummary. Tactics submitted strictly after
    the first and up to (and including) the second represent every
    tactic the agent attempted between the two panels — i.e., the full
    chain when a single ``-chain`` command spawned multiple
    ``tactic.submitted`` events. ``end_event_index == 0`` means "the
    next summary's event_index is unknown" and the function walks to
    the end of the event log.
    """
    if start_event_index <= 0:
        return []
    out: list[str] = []
    upper = end_event_index if end_event_index > 0 else len(events) + 1
    for idx, event in enumerate(events, start=1):
        if idx <= start_event_index:
            continue
        if idx > upper:
            break
        if str(event.get("type") or "") != "tactic.submitted":
            continue
        payload = event_payload(event)
        tac = _normalize_tactic(payload.get("tactic"))
        if tac:
            out.append(tac)
    return out


def _classify_adoption_outcome(
    summaries: list[tuple[Path, dict[str, Any], int]],
    start_pos: int,
    *,
    lookahead: int = 3,
) -> str:
    """Classify what happened in the proof after a verified rec was adopted.

    ``start_pos`` is the index of the summary that records the adoption
    (the post-mutation summary right after the agent committed the rec
    text). Outcome buckets:

    * ``adopted_then_error``: the adoption summary itself is an error or
      records a ``failed_tactic`` — the rec daemon-passed at probe time
      but EC rejected it on commit (a real bug in the rec or a stale
      verification).
    * ``adopted_no_progress``: the adoption summary's transition flagged
      ``no_progress`` — daemon let it through but it was a vacuous
      mutation.
    * ``adopted_then_detour``: the adoption commit was OK, but ≥2 of the
      next ``lookahead`` summaries are errors. Symptom of a rec that
      passed daemon verification at one goal but pushed the proof onto
      a brittle subsequent path.
    * ``adopted_ok``: clean — adoption committed and the next steps did
      not need to backtrack.
    """
    if start_pos >= len(summaries):
        return "adopted_ok"
    first_summary = summaries[start_pos][1]
    first_trans = _dict(first_summary.get("transition"))
    first_mut = _dict(first_summary.get("mutation"))
    first_status = str(first_trans.get("status") or "")
    first_failed = (
        first_status == "error"
        or bool(first_mut.get("failed_tactic"))
        or first_summary.get("ok") is False
        or str(first_summary.get("command_status") or "") == "error"
    )
    if first_failed:
        return "adopted_then_error"
    if first_trans.get("no_progress"):
        return "adopted_no_progress"
    error_count = 0
    end = min(start_pos + 1 + lookahead, len(summaries))
    for i in range(start_pos + 1, end):
        s = summaries[i][1]
        trans = _dict(s.get("transition"))
        mut = _dict(s.get("mutation"))
        if (
            str(trans.get("status") or "") == "error"
            or bool(mut.get("failed_tactic"))
            or s.get("ok") is False
            or str(s.get("command_status") or "") == "error"
        ):
            error_count += 1
    if error_count >= 2:
        return "adopted_then_detour"
    return "adopted_ok"


def _normalize_tactic(value: Any) -> str:
    text = str(value or "").strip().replace("\\!", "!")
    text = re.sub(r"\s+", " ", text)
    if text and not text.endswith("."):
        text += "."
    return text


def _rate(num: int, den: int) -> float:
    if den <= 0:
        return 0.0
    return round(num / den, 4)


def _resolve_path(base: Path, value: str) -> Path | None:
    if not value:
        return None
    path = Path(value)
    candidates = [path]
    if not path.is_absolute():
        candidates.append(base / path)
    candidates.append(base / path.name)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}




def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "path",
        help="Replay artifact root or a single live EasyCrypt session directory.",
    )
    ap.add_argument(
        "--write",
        action="store_true",
        help="Write prover_behavior_report.json next to the input path.",
    )
    ap.add_argument(
        "--fail-on-warnings",
        action="store_true",
        help="Return non-zero when warnings are present.",
    )
    args = ap.parse_args(argv)

    root = Path(args.path)
    report = audit_path(root)
    if args.write:
        write_report(root, report)
    print(json.dumps(report, indent=2, sort_keys=True))
    if report.get("error_count"):
        return 1
    if args.fail_on_warnings and report.get("warning_count"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
