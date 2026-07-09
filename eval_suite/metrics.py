"""Extract paper-eval metrics from ShannonProver run directories."""
from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from workflow.validation.agent_thinking_trace import usage_dedup_key
from typing import Any


DESTRUCTIVE_LOWERING_RE = re.compile(
    r"(?i)(?:^|[;\s])(?:inline\s+\*|wp\.|smt\s*\(|proc\s*;\s*inline\s+\*)"
)
CLAUDE_PROJECTS_DIR = Path.home() / ".claude" / "projects"
THINKING_TOKEN_KEYS = (
    "thinking_tokens",
    "reasoning_tokens",
    "reasoning_output_tokens",
)
OUTPUT_DETAILS_TOKEN_KEYS = (
    "thinking_tokens",
    "reasoning_tokens",
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runs", nargs="+", type=Path)
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--markdown-output", type=Path)
    args = parser.parse_args(argv)

    rows = [collect_run_metrics(path) for path in args.runs]
    payload = {
        "schema_version": 1,
        "kind": "eval_suite_metrics",
        "runs": rows,
    }
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    if args.markdown_output:
        args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_output.write_text(render_markdown(rows), encoding="utf-8")
    if not args.json_output and not args.markdown_output:
        print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def collect_run_metrics(path: Path) -> dict[str, Any]:
    """Collect stable metrics for one orchestrator run or run container."""
    run_dir = _resolve_run_dir(path)
    summary = _read_json(run_dir / "summary.json")
    config = _read_json(run_dir / "config.json")
    iteration_dirs = sorted(run_dir.glob("iteration_*"))
    audit_paths = [
        audit
        for iteration in iteration_dirs
        for audit in iteration.glob("proof_node_manager_audit.jsonl")
    ]
    audit_records = [
        record
        for audit in audit_paths
        for record in _read_jsonl(audit)
    ]

    action_counts: Counter[str] = Counter()
    inspect_topics: Counter[str] = Counter()
    node_commits: Counter[str] = Counter()
    node_failed_turns: Counter[str] = Counter()
    accepted_probe_tactics: set[str] = set()
    committed_tactics_after_probe: set[str] = set()
    destructive_lowering = 0
    failed_commit_tactics = 0
    failed_probe_tactics = 0
    failed_tactic_attempts = 0
    accepted_commits = 0
    accepted_probes = 0
    probe_attempts = 0
    commit_attempts = 0
    undo_count = 0
    restart_count = 0
    blocked_by_profile = 0
    handled_turns = 0
    blind_retry_spikes: list[int] = []
    blind_run = 0

    for record in audit_records:
        kind = str(record.get("kind") or "")
        if kind == "agent_intent.blocked_by_surface_profile":
            blocked_by_profile += 1
            continue
        if kind != "agent_intent.handled":
            continue
        handled_turns += 1
        node = str(record.get("node") or "")
        intent = _intent_name(record.get("intent"))
        payload = _intent_payload(record.get("intent"))
        if intent == "inspect_context":
            inspect_topics[str(payload.get("topic") or "goal_info")] += 1
        actions = [
            action
            for action in record.get("manager_actions") or []
            if isinstance(action, dict)
        ]
        primary = _primary_action(actions)
        if primary:
            label = str(primary.get("label") or intent or "unknown")
            action_counts[label] += 1
        failed_tactic_turn = False
        if intent == "probe_tactic":
            probe_attempts += 1
            if _action_was_accepted(primary):
                accepted_probes += 1
                tactic = _action_tactic(primary) or str(payload.get("tactic") or "")
                if tactic:
                    accepted_probe_tactics.add(_normalize_tactic(tactic))
            else:
                failed_probe_tactics += 1
                failed_tactic_attempts += 1
                failed_tactic_turn = True
        elif intent == "commit_tactic":
            commit_attempts += 1
            tactic = str(payload.get("tactic") or _action_tactic(primary) or "")
            ok = _action_was_accepted(primary)
            if ok:
                accepted_commits += 1
                node_commits[node] += 1
                if _normalize_tactic(tactic) in accepted_probe_tactics:
                    committed_tactics_after_probe.add(_normalize_tactic(tactic))
                if DESTRUCTIVE_LOWERING_RE.search(tactic):
                    destructive_lowering += 1
            else:
                failed_commit_tactics += 1
                failed_tactic_attempts += 1
                failed_tactic_turn = True
        elif intent in {"undo_last_step", "undo_to_checkpoint"}:
            undo_count += 1
        elif intent == "fresh_restart":
            restart_count += 1

        if failed_tactic_turn:
            blind_run += 1
            node_failed_turns[node] += 1
        else:
            if blind_run >= 2:
                blind_retry_spikes.append(blind_run)
            blind_run = 0
    if blind_run >= 2:
        blind_retry_spikes.append(blind_run)

    profile = (
        config.get("surface_profile")
        or _first_profile_from_records(audit_records)
        or ""
    )
    best_prefix_depth = max(node_commits.values() or [0])
    final_proof_length = best_prefix_depth if summary.get("final_proved") else None
    agent_trace = _collect_agent_trace_metrics(iteration_dirs or [run_dir])
    return {
        "run_dir": str(run_dir),
        "profile": profile,
        "target": summary.get("target") or {
            "file": config.get("file"),
            "lemma": config.get("lemma"),
        },
        "outcome": {
            "proved": bool(summary.get("final_proved")),
            "regression_ok": bool(summary.get("final_regression_ok")),
            "elapsed_minutes": summary.get("total_elapsed_minutes"),
            "iterations": summary.get("iterations"),
        },
        "main": {
            "manager_turns": handled_turns,
            "commit_attempts": commit_attempts,
            "accepted_commits": accepted_commits,
            "failed_commit_tactics": failed_commit_tactics,
            "failed_probe_tactics": failed_probe_tactics,
            "failed_tactic_attempts": failed_tactic_attempts,
            "final_proof_length": final_proof_length,
        },
        "preview": {
            "probe_attempts": probe_attempts,
            "accepted_probes": accepted_probes,
            "failed_probes": failed_probe_tactics,
            "accepted_probe_rate": _ratio(accepted_probes, probe_attempts),
            "accepted_probe_to_commit_rate": _ratio(
                len(committed_tactics_after_probe),
                len(accepted_probe_tactics),
            ),
            "unique_accepted_probe_tactics": len(accepted_probe_tactics),
            "unique_committed_after_probe": len(committed_tactics_after_probe),
        },
        "navigator": {
            "destructive_lowering_count": destructive_lowering,
            "best_prefix_depth": best_prefix_depth,
        },
        "diagnostics": {
            "blind_retry_spike_count": len(blind_retry_spikes),
            "max_blind_retry_spike_length": max(blind_retry_spikes or [0]),
            "blind_retry_turns": sum(blind_retry_spikes),
            "blocked_by_surface_profile": blocked_by_profile,
        },
        "search": {
            "node_count": len({str(record.get("node") or "") for record in audit_records if record.get("node")}),
            "max_node_failed_turns": max(node_failed_turns.values() or [0]),
        },
        "mechanical_work": {
            "inspect_context_count": sum(inspect_topics.values()),
            "inspect_topics": dict(sorted(inspect_topics.items())),
            "lookup_symbol_count": action_counts.get("lookup_symbol", 0),
            "undo_count": undo_count,
            "fresh_restart_count": restart_count,
            "route_repair_count": undo_count + restart_count,
            "thinking_tokens_per_accepted_commit": _per(
                agent_trace.get("thinking_tokens"),
                accepted_commits,
            ),
            "thinking_chars_per_accepted_commit": _per(
                agent_trace.get("thinking_chars"),
                accepted_commits,
            ),
        },
        "agent_trace": agent_trace,
        "raw_action_counts": dict(sorted(action_counts.items())),
    }


def render_markdown(rows: list[dict[str, Any]]) -> str:
    lines = [
        "# Eval Suite Metrics",
        "",
        "| Profile | Target | Proved | Time (min) | Thinking tokens | Turns | Commits | Failed commits | Probes | Failed probes | Probe accept % | Undo | Restart | Route repairs | Destructive lowering | Blind spikes |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        target = row.get("target") or {}
        target_label = target.get("lemma") or row.get("run_dir")
        outcome = row.get("outcome") or {}
        main = row.get("main") or {}
        preview = row.get("preview") or {}
        navigator = row.get("navigator") or {}
        diagnostics = row.get("diagnostics") or {}
        mechanical = row.get("mechanical_work") or {}
        agent_trace = row.get("agent_trace") or {}
        lines.append(
            "| {profile} | {target} | {proved} | {time} | {thinking_tokens} | "
            "{turns} | {commits} | {failed_commits} | {probes} | "
            "{failed_probes} | {probe_rate} | {undo} | {restart} | "
            "{repairs} | {destructive} | {spikes} |".format(
                profile=row.get("profile") or "",
                target=target_label,
                proved="yes" if outcome.get("proved") else "no",
                time=_fmt(outcome.get("elapsed_minutes")),
                thinking_tokens=_fmt(agent_trace.get("thinking_tokens")),
                turns=_fmt(main.get("manager_turns")),
                commits=_fmt(main.get("accepted_commits")),
                failed_commits=_fmt(main.get("failed_commit_tactics")),
                probes=_fmt(preview.get("probe_attempts")),
                failed_probes=_fmt(preview.get("failed_probes")),
                probe_rate=_fmt_percent(preview.get("accepted_probe_rate")),
                undo=_fmt(mechanical.get("undo_count")),
                restart=_fmt(mechanical.get("fresh_restart_count")),
                repairs=_fmt(mechanical.get("route_repair_count")),
                destructive=_fmt(navigator.get("destructive_lowering_count")),
                spikes=_fmt(diagnostics.get("blind_retry_spike_count")),
            )
        )
    lines.append("")
    return "\n".join(lines)


def _resolve_run_dir(path: Path) -> Path:
    if (path / "summary.json").exists():
        return path
    summaries = sorted(path.glob("*/summary.json"))
    if len(summaries) == 1:
        return summaries[0].parent
    if not summaries:
        raise FileNotFoundError(f"no summary.json under {path}")
    raise ValueError(
        f"{path} contains multiple run summaries; pass one concrete run dir"
    )


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            rows.append(item)
    return rows


def _collect_agent_trace_metrics(iteration_dirs: list[Path]) -> dict[str, Any]:
    """Whole-run token/thinking accounting from ~/.claude transcripts.

    Host-specific: degrades to {"available": False} when transcripts are
    absent (CI, other machines). Related but deliberately separate from
    workflow/validation/agent_thinking_trace.py, which attributes thinking
    to individual turns for run bundles; the shared invariant (the usage
    dedup key) is imported from there."""
    records = _agent_session_records(iteration_dirs)
    totals = {
        "available": False,
        "session_count": len(records),
        "trace_count": 0,
        "missing_trace_count": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0,
        "effective_input_tokens": 0,
        "total_tokens": 0,
        "thinking_blocks": 0,
        "thinking_chars": 0,
        "thinking_tokens": 0,
        "thinking_tokens_exact": None,
        "thinking_token_estimate": 0,
        "thinking_token_source": "none",
        "summed_trace_duration_seconds": 0.0,
        "max_trace_duration_seconds": 0.0,
        "max_gap_before_thinking_seconds": 0.0,
        "sessions": [],
    }
    exact_thinking_tokens = 0
    saw_exact_thinking_tokens = False

    for record in records:
        session_id = str(record.get("session_id") or "").strip()
        if not session_id:
            continue
        trace_path = _find_session_trace(session_id)
        session_status = {
            key: value
            for key, value in record.items()
            if key != "trace_path"
        }
        session_status["trace_found"] = bool(trace_path)
        if trace_path:
            session_status["trace_path"] = str(trace_path)
        totals["sessions"].append(session_status)
        if trace_path is None:
            totals["missing_trace_count"] += 1
            continue
        stats = _parse_agent_trace(trace_path)
        totals["available"] = True
        totals["trace_count"] += 1
        totals["input_tokens"] += stats["input_tokens"]
        totals["output_tokens"] += stats["output_tokens"]
        totals["cache_creation_input_tokens"] += stats[
            "cache_creation_input_tokens"
        ]
        totals["cache_read_input_tokens"] += stats["cache_read_input_tokens"]
        totals["thinking_blocks"] += stats["thinking_blocks"]
        totals["thinking_chars"] += stats["thinking_chars"]
        totals["summed_trace_duration_seconds"] = round(
            totals["summed_trace_duration_seconds"] + stats["duration_seconds"],
            3,
        )
        totals["max_trace_duration_seconds"] = max(
            totals["max_trace_duration_seconds"],
            stats["duration_seconds"],
        )
        totals["max_gap_before_thinking_seconds"] = max(
            totals["max_gap_before_thinking_seconds"],
            stats["max_gap_before_thinking_seconds"],
        )
        if stats["thinking_tokens_exact"] is not None:
            saw_exact_thinking_tokens = True
            exact_thinking_tokens += stats["thinking_tokens_exact"]

    totals["effective_input_tokens"] = (
        totals["input_tokens"]
        + totals["cache_creation_input_tokens"]
        + totals["cache_read_input_tokens"]
    )
    totals["total_tokens"] = (
        totals["effective_input_tokens"]
        + totals["output_tokens"]
    )
    if saw_exact_thinking_tokens:
        totals["thinking_tokens_exact"] = exact_thinking_tokens
        totals["thinking_tokens"] = exact_thinking_tokens
        totals["thinking_token_estimate"] = exact_thinking_tokens
        totals["thinking_token_source"] = "usage_field"
    elif totals["thinking_chars"]:
        totals["thinking_token_estimate"] = int(
            math.ceil(totals["thinking_chars"] / 4.0)
        )
        totals["thinking_tokens"] = totals["thinking_token_estimate"]
        totals["thinking_token_source"] = "char_estimate"
    totals["summed_trace_duration_seconds"] = round(
        totals["summed_trace_duration_seconds"],
        3,
    )
    totals["max_trace_duration_seconds"] = round(
        totals["max_trace_duration_seconds"],
        3,
    )
    totals["max_gap_before_thinking_seconds"] = round(
        totals["max_gap_before_thinking_seconds"],
        3,
    )
    return totals


def _agent_session_records(iteration_dirs: list[Path]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for iteration_dir in iteration_dirs:
        manifest = _read_json(iteration_dir / "agent_session_ids.json")
        sessions = manifest.get("sessions") if manifest else None
        if isinstance(sessions, list):
            for item in sessions:
                if isinstance(item, dict) and item.get("session_id"):
                    record = dict(item)
                    record.setdefault("source", "agent_session_ids.json")
                    record.setdefault("iteration_dir", str(iteration_dir))
                    records.append(record)
        session_id_path = iteration_dir / "session_id.txt"
        if session_id_path.exists():
            session_id = session_id_path.read_text(encoding="utf-8").strip()
            if session_id:
                records.append({
                    "session_id": session_id,
                    "winner": True,
                    "source": "session_id.txt",
                    "iteration_dir": str(iteration_dir),
                })
    return _dedupe_session_records(records)


def _dedupe_session_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for record in records:
        session_id = str(record.get("session_id") or "").strip()
        if not session_id:
            continue
        if session_id not in merged:
            merged[session_id] = {"session_id": session_id}
            order.append(session_id)
        merged[session_id].update(record)
    return [merged[session_id] for session_id in order]


def _find_session_trace(session_id: str) -> Path | None:
    if not session_id or not CLAUDE_PROJECTS_DIR.exists():
        return None
    try:
        project_dirs = list(CLAUDE_PROJECTS_DIR.iterdir())
    except OSError:
        return None
    for project_dir in project_dirs:
        try:
            if not project_dir.is_dir():
                continue
            candidate = project_dir / f"{session_id}.jsonl"
            if candidate.exists():
                return candidate
        except OSError:
            continue
    return None


def _parse_agent_trace(path: Path) -> dict[str, Any]:
    stats = {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0,
        "thinking_blocks": 0,
        "thinking_chars": 0,
        "thinking_tokens_exact": None,
        "duration_seconds": 0.0,
        "max_gap_before_thinking_seconds": 0.0,
    }
    exact_thinking_tokens = 0
    saw_exact_thinking_tokens = False
    start_ts: datetime | None = None
    end_ts: datetime | None = None
    previous_ts: datetime | None = None
    seen_usage_keys: set[str] = set()

    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        ts = _parse_timestamp(str(event.get("timestamp") or ""))
        if ts is not None:
            start_ts = ts if start_ts is None or ts < start_ts else start_ts
            end_ts = ts if end_ts is None or ts > end_ts else end_ts
        message = event.get("message") if isinstance(event.get("message"), dict) else {}
        usage = message.get("usage")
        if not isinstance(usage, dict):
            usage = event.get("usage") if isinstance(event.get("usage"), dict) else {}
        usage_key = usage_dedup_key(event, message)
        count_usage = bool(usage) and (
            not usage_key or usage_key not in seen_usage_keys
        )
        if usage_key and count_usage:
            seen_usage_keys.add(usage_key)
        if usage and count_usage:
            stats["input_tokens"] += _int_value(usage.get("input_tokens"))
            stats["output_tokens"] += _int_value(usage.get("output_tokens"))
            stats["cache_creation_input_tokens"] += _int_value(
                usage.get("cache_creation_input_tokens")
            )
            stats["cache_read_input_tokens"] += _int_value(
                usage.get("cache_read_input_tokens")
            )
            thinking_tokens = _thinking_tokens_from_usage(usage)
            if thinking_tokens is not None:
                saw_exact_thinking_tokens = True
                exact_thinking_tokens += thinking_tokens

        content = message.get("content") if isinstance(message, dict) else []
        if not isinstance(content, list):
            content = []
        thinking_in_event = False
        for block in content:
            if not isinstance(block, dict) or block.get("type") != "thinking":
                continue
            text = str(block.get("thinking") or "")
            if not text:
                continue
            thinking_in_event = True
            stats["thinking_blocks"] += 1
            stats["thinking_chars"] += len(text)
        if thinking_in_event and ts is not None and previous_ts is not None:
            gap = max(0.0, (ts - previous_ts).total_seconds())
            stats["max_gap_before_thinking_seconds"] = max(
                stats["max_gap_before_thinking_seconds"],
                gap,
            )
        if ts is not None:
            previous_ts = ts

    if start_ts is not None and end_ts is not None:
        stats["duration_seconds"] = max(0.0, (end_ts - start_ts).total_seconds())
    if saw_exact_thinking_tokens:
        stats["thinking_tokens_exact"] = exact_thinking_tokens
    stats["duration_seconds"] = round(stats["duration_seconds"], 3)
    stats["max_gap_before_thinking_seconds"] = round(
        stats["max_gap_before_thinking_seconds"],
        3,
    )
    return stats


def _thinking_tokens_from_usage(usage: dict[str, Any]) -> int | None:
    for key in THINKING_TOKEN_KEYS:
        value = _optional_int_value(usage.get(key))
        if value is not None:
            return value
    details = usage.get("output_tokens_details")
    if isinstance(details, dict):
        for key in OUTPUT_DETAILS_TOKEN_KEYS:
            value = _optional_int_value(details.get(key))
            if value is not None:
                return value
    return None


def _parse_timestamp(raw: str) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def _int_value(value: Any) -> int:
    parsed = _optional_int_value(value)
    return parsed if parsed is not None else 0


def _optional_int_value(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def _intent_name(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("intent") or "")
    return ""


def _intent_payload(value: Any) -> dict[str, Any]:
    if isinstance(value, dict) and isinstance(value.get("payload"), dict):
        return dict(value["payload"])
    return {}


def _primary_action(actions: list[dict[str, Any]]) -> dict[str, Any] | None:
    for action in actions:
        if str(action.get("label") or "") != "agent_view":
            return action
    return actions[0] if actions else None


def _action_tactic(action: dict[str, Any] | None) -> str:
    if not action:
        return ""
    observation = action.get("agent_observation")
    if isinstance(observation, dict):
        return str(observation.get("tactic") or "")
    return ""


def _action_was_accepted(action: dict[str, Any] | None) -> bool:
    """Return whether the proof action succeeded at the EasyCrypt layer."""
    if not action:
        return False
    observation = action.get("agent_observation")
    if not isinstance(observation, dict):
        return _optional_int_value(action.get("exit_code")) == 0
    if observation.get("error_summary"):
        return False
    status_text = " ".join(
        str(observation.get(key) or "")
        for key in ("kind", "message", "result")
    ).lower()
    if "rejected" in status_text or "could not use" in status_text:
        return False
    if "accepted" in status_text or observation.get("accepted_tactic"):
        return True
    if (
        observation.get("manager_action") == "commit_tactic"
        and "not changed" in str(observation.get("proof_state") or "").lower()
    ):
        return False
    return _optional_int_value(action.get("exit_code")) == 0


def _normalize_tactic(tactic: str) -> str:
    return re.sub(r"\s+", " ", tactic).strip()


def _ratio(num: int, den: int) -> float | None:
    if den <= 0:
        return None
    return round(float(num) / float(den), 4)


def _per(num: Any, den: int) -> float | None:
    if den <= 0:
        return None
    value = _optional_int_value(num)
    if value is None:
        return None
    return round(float(value) / float(den), 2)


def _first_profile_from_records(records: list[dict[str, Any]]) -> str:
    for record in records:
        profile = record.get("surface_profile")
        if profile:
            return str(profile)
    return ""


def _fmt(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def _fmt_percent(value: Any) -> str:
    if value is None:
        return ""
    parsed = _optional_float_value(value)
    if parsed is None:
        return str(value)
    return f"{parsed * 100:.1f}%"


def _optional_float_value(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


if __name__ == "__main__":
    raise SystemExit(main())
