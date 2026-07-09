"""Generate agent decision-view timeline tables from node memory.

The report is intentionally offline and deterministic: it reads per-node
``timeline.jsonl``, ``manager_results/turn_NNN.json``, and
``workspace_views/turn_NNN.json`` artifacts that a long-lived prover run has
already written. Human view-quality review is kept as a separate column so the
table can be regenerated after every run without baking subjective judgments
into the script.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from workflow.validation.replay_artifacts import node_id_from_dir as _node_id_from_dir
from workflow.proof_management.common import read_jsonl as _read_jsonl
from typing import Any


REPORT_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class RunSpec:
    label: str
    path: Path


def build_report(
    runs: list[RunSpec],
    *,
    chronological: bool = False,
) -> dict[str, Any]:
    """Build a machine-readable report for one or more iteration run dirs."""

    run_reports = [
        build_run_report(spec, chronological=chronological)
        for spec in runs
    ]
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "kind": "agent_view_timeline_report",
        "run_count": len(run_reports),
        "runs": run_reports,
    }


def build_run_report(
    spec: RunSpec,
    *,
    chronological: bool = False,
) -> dict[str, Any]:
    run_dir = spec.path.resolve()
    node_dirs = _node_memory_dirs(run_dir)
    rows_by_node: dict[str, list[dict[str, Any]]] = {}
    all_rows: list[dict[str, Any]] = []
    first_action_at = _first_manager_turn_submit_time(node_dirs)

    for node_dir in node_dirs:
        node_rows = _build_node_rows(
            run_dir=run_dir,
            node_dir=node_dir,
            first_action_at=first_action_at,
        )
        if not node_rows:
            continue
        node_id = str(node_rows[0].get("node") or node_dir.name)
        rows_by_node[node_id] = node_rows
        all_rows.extend(node_rows)

    if chronological:
        all_rows.sort(key=lambda row: (
            row.get("action_submitted_at") or "",
            row.get("node") or "",
            row.get("turn") or 0,
        ))
    else:
        all_rows.sort(key=lambda row: (
            _node_sort_key(str(row.get("node") or "")),
            row.get("turn") or 0,
        ))

    return {
        "label": spec.label,
        "run_dir": str(run_dir),
        "first_action_at": first_action_at.isoformat() if first_action_at else "",
        "node_count": len(rows_by_node),
        "turn_count": len(all_rows),
        "chronological": chronological,
        "rows": all_rows,
    }


_TABLE_HEADER = (
    "| View | Action time | Agent think | Manager time | Decision View (full · inline read) | "
    "Intent | State Seen | Result | 质量判断 |\n"
    "|---|---:|---:|---:|---|---|---|---|---|"
)


def _row_node_key(row: dict[str, Any]) -> str:
    """The proof-tree a row belongs to (for per-tree grouping)."""
    node = row.get("node")
    if node:
        return str(node)
    vid = str(row.get("view_id") or "")
    return vid.rsplit("-", 1)[0] if "-" in vid else (vid or "node")


def _render_rows_table(
    rows: list[dict[str, Any]], *, label: str,
    quality_notes: dict[str, str], quality_placeholder: str,
) -> list[str]:
    out = [_TABLE_HEADER]
    for row in rows:
        quality = _quality_for_row(
            quality_notes=quality_notes, run_label=label, row=row,
            placeholder=quality_placeholder,
        )
        out.append(
            "| " + " | ".join([
                _md_cell(str(row.get("view_id") or "")),
                _md_cell(str(row.get("action_time") or "")),
                _md_cell(_agent_think_cell(row)),
                _md_cell(str(row.get("manager_time") or "")),
                _md_cell(_decision_view_link(row)),
                _md_cell(str(row.get("intent_summary") or "")),
                _md_cell(str(row.get("decision_state_summary") or "")),
                _md_cell(str(row.get("result_summary") or "")),
                _md_cell(quality),
            ]) + " |"
        )
    return out


def render_markdown(
    report: dict[str, Any],
    *,
    quality_notes: dict[str, str] | None = None,
    quality_placeholder: str = "",
) -> str:
    """Render the report as a Markdown table suitable for review."""

    quality_notes = quality_notes or {}
    lines = [
        "# Agent View Timeline Report",
        "",
        "每行表示：agent 看到 Decision View -> 提交 Intent -> manager 返回 Result。",
        "",
        (
            "**Decision View 列有两个链接**：`turn_NNN.json` 是框架算出的**完整 view**"
            "（存档用，含所有面板）；`inline read` 是 agent **当轮真正读到的 inline 文本**"
            "（followups/turn_NNN.md，是该 view 的过滤 preview）。两者会**不一致**——preview "
            "会丢面板，所以判断「agent 实际看到了什么」要点 `inline read`，不是完整 view。"
        ),
        "",
        (
            "`Action time` 从每个 run 第一条 agent `submit_proof_intent` "
            "的估算提交时间开始计时；`Agent think` 是同一个 node 上从上一轮 "
            "manager result 到这次提交的间隔；`Manager time` 是本 intent 的 "
            "manager/EasyCrypt 处理时间。"
        ),
        "",
        (
            "`质量判断` 默认留空，供人工或后续 LLM 复盘填写；可用 "
            "`--quality-file` 传入 JSON 覆盖。"
        ),
    ]

    for run in _list(report.get("runs")):
        label = str(run.get("label") or "run")
        lines.extend([
            "",
            f"## {label}",
            "",
            f"Run dir: `{run.get('run_dir') or ''}`",
            "",
        ])
        first_action = str(run.get("first_action_at") or "")
        if first_action:
            lines.extend([f"t=0: `{first_action}`", ""])
        rows = _list(run.get("rows"))
        if run.get("chronological"):
            # explicit cross-tree chronological view → one combined table
            lines.extend(_render_rows_table(
                rows, label=label, quality_notes=quality_notes,
                quality_placeholder=quality_placeholder))
        else:
            # one table per proof tree, so a multi-tree run is not interleaved
            groups: dict[str, list[dict[str, Any]]] = {}
            order: list[str] = []
            for row in rows:
                key = _row_node_key(row)
                if key not in groups:
                    groups[key] = []
                    order.append(key)
                groups[key].append(row)
            multi = len(order) > 1
            for key in order:
                if multi:
                    lines.extend(["", f"### {key}", ""])
                lines.extend(_render_rows_table(
                    groups[key], label=label, quality_notes=quality_notes,
                    quality_placeholder=quality_placeholder))
    lines.append("")
    return "\n".join(lines)


def load_quality_notes(path: Path | None) -> dict[str, str]:
    if path is None:
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("--quality-file must contain a JSON object")
    out: dict[str, str] = {}
    for key, value in raw.items():
        if isinstance(value, str):
            out[str(key)] = value
    return out


def write_outputs(
    report: dict[str, Any],
    *,
    markdown_output: Path | None,
    json_output: Path | None,
    markdown: str,
) -> None:
    if markdown_output is not None:
        markdown_output.parent.mkdir(parents=True, exist_ok=True)
        markdown_output.write_text(markdown, encoding="utf-8")
    if json_output is not None:
        json_output.parent.mkdir(parents=True, exist_ok=True)
        json_output.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def parse_run_specs(values: list[str]) -> list[RunSpec]:
    specs: list[RunSpec] = []
    for value in values:
        label, path_text = _split_label_path(value)
        path = Path(path_text)
        if not label:
            label = path.name
            if label == "iteration_1":
                label = path.parent.name
        specs.append(RunSpec(label=label, path=path))
    return specs


def _build_node_rows(
    *,
    run_dir: Path,
    node_dir: Path,
    first_action_at: datetime | None,
) -> list[dict[str, Any]]:
    entries = [
        item for item in _read_jsonl(node_dir / "timeline.jsonl")
        if item.get("kind") == "manager_turn"
    ]
    entries.sort(key=lambda item: _int(item.get("turn")))
    node_id = _node_id_from_dir(node_dir)
    audit_records = _handled_audit_records_for_node(run_dir, node_id)
    thinking_index = _thinking_index(node_dir)
    usage_index = _usage_index(node_dir)
    audit_index = 0
    rows: list[dict[str, Any]] = []
    previous_result_at: datetime | None = None

    for entry in entries:
        turn = _int(entry.get("turn"))
        if turn <= 0:
            continue
        result_at = _parse_time(str(entry.get("time") or ""))
        result_path = node_dir / "manager_results" / f"turn_{turn:03d}.json"
        result_view_path = node_dir / "workspace_views" / f"turn_{turn:03d}.json"
        result_followup_path = node_dir / "followups" / f"turn_{turn:03d}.md"
        manager_result = _read_json(result_path)
        result_workspace_view = _read_json(result_view_path)
        node_id = str(entry.get("node") or _node_id_from_dir(node_dir))
        intent = _dict(manager_result.get("handled_intent") or entry.get("intent"))
        audit_record, audit_index = _next_matching_audit_record(
            audit_records,
            audit_index,
            intent,
        )
        manager_actions = _list(
            manager_result.get("manager_actions") or entry.get("manager_actions")
        )
        audit_manager_actions = _list(audit_record.get("manager_actions"))
        timing_seconds = _manager_action_seconds(manager_actions)
        submitted_at = _estimate_submit_time(result_at, timing_seconds)
        decision_view_path, decision_followup_path, decision_workspace_view = (
            _decision_artifacts(
                run_dir=run_dir,
                node_dir=node_dir,
                node_id=node_id,
                turn=turn,
            )
        )

        row = {
            "node": node_id,
            "node_dir": str(node_dir.resolve()),
            "turn": turn,
            "view_id": f"{_node_display(node_id)}-{turn}",
            "action_submitted_at": submitted_at.isoformat() if submitted_at else "",
            "manager_result_at": result_at.isoformat() if result_at else "",
            "action_time": _format_delta(first_action_at, submitted_at),
            "agent_think_seconds": _seconds_between(previous_result_at, submitted_at),
            "agent_think": _format_optional_seconds(
                _seconds_between(previous_result_at, submitted_at)
            ),
            "agent_think_path": _thinking_path_for_turn(
                node_dir, thinking_index, turn=turn, intent=intent,
            ),
            "usage": _usage_for_turn(usage_index, turn=turn, intent=intent),
            "manager_seconds": timing_seconds,
            "manager_time": _format_seconds(timing_seconds),
            "intent": intent,
            "intent_summary": _intent_summary(intent),
            "ok": _bool(manager_result.get("ok"), default=_bool(entry.get("ok"))),
            "manager_action_summary": _manager_action_summary(manager_actions),
            "result_summary": _result_summary(
                intent=intent,
                ok=_bool(manager_result.get("ok"), default=_bool(entry.get("ok"))),
                manager_actions=manager_actions,
                audit_manager_actions=audit_manager_actions,
            ),
            "decision_state_summary": (
                _state_summary(decision_workspace_view)
                if decision_workspace_view
                else "initial handoff (not persisted)"
            ),
            "result_state_summary": _state_summary(result_workspace_view),
            "decision_view_path": (
                str(decision_view_path.resolve()) if decision_view_path.exists() else ""
            ),
            "decision_followup_path": (
                str(decision_followup_path.resolve())
                if decision_followup_path.exists()
                else ""
            ),
            "result_view_path": (
                str(result_view_path.resolve()) if result_view_path.exists() else ""
            ),
            "workspace_view_path": (
                str(decision_view_path.resolve()) if decision_view_path.exists() else ""
            ),
            "manager_result_path": str(result_path.resolve()) if result_path.exists() else "",
            "result_followup_path": (
                str(result_followup_path.resolve())
                if result_followup_path.exists()
                else ""
            ),
            "view_chars": (
                _json_chars(decision_workspace_view) if decision_workspace_view else 0
            ),
            "goal_chars": _goal_chars(decision_workspace_view),
            "inspect_topics": _inspect_topics(decision_workspace_view),
            "deterministic_signals": _deterministic_signals(
                intent=intent,
                manager_actions=manager_actions,
                audit_manager_actions=audit_manager_actions,
                workspace_view=decision_workspace_view,
            ),
        }
        rows.append(row)
        if result_at is not None:
            previous_result_at = result_at

    return rows


def _node_memory_dirs(run_dir: Path) -> list[Path]:
    root = run_dir / "node_memory"
    if not root.is_dir():
        return []
    dirs = [
        path for path in root.iterdir()
        if path.is_dir() and (path / "timeline.jsonl").exists()
    ]
    return sorted(dirs, key=lambda path: _node_sort_key(_node_id_from_dir(path)))


def _first_manager_turn_submit_time(node_dirs: list[Path]) -> datetime | None:
    first: datetime | None = None
    for node_dir in node_dirs:
        for entry in _read_jsonl(node_dir / "timeline.jsonl"):
            if entry.get("kind") != "manager_turn":
                continue
            result_at = _parse_time(str(entry.get("time") or ""))
            manager_seconds = _manager_action_seconds(_list(entry.get("manager_actions")))
            submitted_at = _estimate_submit_time(result_at, manager_seconds)
            if submitted_at is not None and (first is None or submitted_at < first):
                first = submitted_at
    return first


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def _decision_artifacts(
    *,
    run_dir: Path,
    node_dir: Path,
    node_id: str,
    turn: int,
) -> tuple[Path, Path, dict[str, Any]]:
    if turn <= 1:
        initial_view_path = node_dir / "initial_workspace_view.json"
        initial_followup_path = node_dir / "initial_followup.md"
        initial_view = _read_json(initial_view_path)
        if initial_view:
            return initial_view_path, initial_followup_path, initial_view
        bootstrap_view, bootstrap_path = _bootstrap_workspace_view(run_dir, node_id)
        return bootstrap_path, initial_followup_path, bootstrap_view
    previous_stem = f"turn_{turn - 1:03d}"
    view_path = node_dir / "workspace_views" / f"{previous_stem}.json"
    return view_path, node_dir / "followups" / f"{previous_stem}.md", _read_json(view_path)


def _thinking_index(node_dir: Path) -> dict[int, dict[str, Any]]:
    """Map turn -> recorded thinking metadata from ``thinking/index.json`` (written
    by ``agent_thinking_trace``). Empty when no reasoning was extracted."""
    raw = _read_json(node_dir / "thinking" / "index.json")
    out: dict[int, dict[str, Any]] = {}
    for item in _list(raw.get("turns")):
        record = _dict(item)
        turn = _int(record.get("turn"))
        if turn > 0 and record.get("file"):
            out[turn] = record
    return out


def _thinking_path_for_turn(
    node_dir: Path,
    thinking_index: dict[int, dict[str, Any]],
    *,
    turn: int,
    intent: dict[str, Any],
) -> str:
    """Absolute path to this turn's thinking md, only when it both exists and the
    recorded intent matches the row's intent (guards against turn-index drift if a
    submit never became a manager turn)."""
    record = thinking_index.get(turn)
    if not record:
        return ""
    rel = str(record.get("file") or "")
    if not rel:
        return ""
    path = node_dir / rel
    if not path.exists():
        return ""
    recorded = (str(record.get("intent") or ""), str(record.get("payload_key") or ""))
    if recorded != _intent_signature(intent):
        return ""
    return str(path.resolve())


def _usage_index(node_dir: Path) -> dict[int, dict[str, Any]]:
    """Map turn -> full index record (incl. real token usage) from thinking/index.json,
    for ALL turns (unlike _thinking_index, which keeps only turns with a thinking file)."""
    raw = _read_json(node_dir / "thinking" / "index.json")
    out: dict[int, dict[str, Any]] = {}
    for item in _list(raw.get("turns")):
        record = _dict(item)
        turn = _int(record.get("turn"))
        if turn > 0:
            out[turn] = record
    return out


def _usage_for_turn(
    usage_index: dict[int, dict[str, Any]], *, turn: int, intent: dict[str, Any],
) -> dict[str, int]:
    """Real per-turn token usage, only when the recorded intent matches the row's
    intent (same drift guard as thinking). {} when unknown/mismatched."""
    record = usage_index.get(turn)
    if not record:
        return {}
    recorded = (str(record.get("intent") or ""), str(record.get("payload_key") or ""))
    if recorded != _intent_signature(intent):
        return {}
    tokens = record.get("tokens")
    if not isinstance(tokens, dict):
        return {}
    return {str(k): _int(v) for k, v in tokens.items()}


def _bootstrap_workspace_view(run_dir: Path, node_id: str) -> tuple[dict[str, Any], Path]:
    bootstrap_path = _bootstrap_file_for_node(run_dir, node_id)
    if bootstrap_path.exists():
        record = _read_json(bootstrap_path)
        view = _dict(record.get("workspace_view"))
        if view:
            return view, bootstrap_path
    jsonl_path = run_dir / "manager_session_bootstrap.jsonl"
    for record in _read_jsonl(jsonl_path):
        if str(record.get("node") or "") == node_id:
            view = _dict(record.get("workspace_view"))
            if view:
                return view, jsonl_path
    return {}, bootstrap_path


def _bootstrap_file_for_node(run_dir: Path, node_id: str) -> Path:
    suffix = node_id
    if suffix.startswith("Tree-"):
        suffix = suffix[len("Tree-"):]
    suffix = suffix.replace(".", "_").replace("-", "_")
    return run_dir / f"manager_bootstrap_{suffix}.json"


def _intent_summary(intent: dict[str, Any]) -> str:
    name = str(intent.get("intent") or "")
    payload = _dict(intent.get("payload"))
    if name in {"probe_tactic", "commit_tactic"}:
        prefix = "probe" if name == "probe_tactic" else "commit"
        return f"{prefix} {_short_tactic(str(payload.get('tactic') or ''))}"
    if name == "inspect_context":
        return f"inspect {payload.get('topic') or ''}".strip()
    if name == "lookup_symbol":
        return f"lookup {payload.get('symbol') or ''}".strip()
    if name:
        return name
    return "unknown"


def _short_tactic(tactic: str) -> str:
    text = " ".join(tactic.strip().split())
    text = text[:-1] if text.endswith(".") else text
    if not text:
        return "<empty>"
    # Keep compound tactics visible. The report is an audit/debugging surface,
    # so reducing "proc; inline ...; sp ..." to just "proc" hides the agent's
    # actual choice and can mislead view-quality review.
    if ";" in text:
        if len(text) > 96:
            return text[:93].rstrip() + "..."
        return text
    compact_patterns = [
        (r"^byequiv\s*=>\s*//$", "byequiv=>//"),
        (r"^proc$", "proc"),
        (r"^inline \*$", "inline *"),
        (r"^wp$", "wp"),
        (r"^sp;\s*if\b.*", "sp; if"),
        (r"^sp\s+1;\s*if\b.*", "sp 1; if"),
        (r"^call\s+\(_:\s*([A-Za-z0-9_'.]+).*", r"call \1"),
        (r"^smt\s*\(([^)]*)\).*", r"smt(\1)"),
    ]
    for pattern, replacement in compact_patterns:
        if re.match(pattern, text):
            return re.sub(pattern, replacement, text)
    if len(text) > 72:
        return text[:69].rstrip() + "..."
    return text


def _result_summary(
    *,
    intent: dict[str, Any],
    ok: bool,
    manager_actions: list[Any],
    audit_manager_actions: list[Any] | None = None,
) -> str:
    if not ok:
        return "repair / unhealthy"
    error = _manager_failure_hint(
        [*manager_actions, *_list(audit_manager_actions)]
    )
    name = str(intent.get("intent") or "")
    if name == "probe_tactic":
        return f"rejected probe: {error}" if error else "accepted probe"
    if name == "commit_tactic":
        return f"rejected commit: {error}" if error else "accepted commit"
    if name == "inspect_context":
        return "read-only inspect"
    if name == "lookup_symbol":
        return "lookup result"
    if name == "undo_last_step":
        return "undo result"
    if name == "undo_to_checkpoint":
        payload = _dict(intent.get("payload"))
        if payload.get("checkpoint_id"):
            return "checkpoint rewind selected"
        return "checkpoint choices requested"
    if name == "fresh_restart":
        payload = _dict(intent.get("payload"))
        if payload.get("confirm"):
            return "fresh restart confirmed"
        return "fresh restart confirmation requested"
    if name == "request_restart":
        return "legacy restart menu requested"
    if name == "finish":
        return "finish requested"
    return "manager result"


def _manager_failure_hint(manager_actions: list[Any]) -> str:
    """Return a compact failure hint from manager action text.

    Manager turn envelopes use ``ok=True`` for handled requests, including
    rejected probes.  The timeline must therefore inspect the action payload
    rather than treating the wrapper as proof success.
    """
    for action in manager_actions:
        item = _dict(action)
        if item.get("error_summary"):
            return str(item.get("error_summary"))
        observation = _dict(item.get("agent_observation"))
        if observation.get("error_summary"):
            return str(observation.get("error_summary"))
        if (
            observation.get("manager_action") == "commit_tactic"
            and "not changed" in str(observation.get("proof_state") or "").lower()
        ):
            return "proof state unchanged"
    text_parts: list[str] = []
    for action in manager_actions:
        item = _dict(action)
        for key in ("outcome", "result", "status"):
            value = item.get(key)
            if isinstance(value, str):
                text_parts.append(value)
        content = _dict(item.get("content"))
        for key in ("outcome", "result", "status"):
            value = content.get(key)
            if isinstance(value, str):
                text_parts.append(value)
    text = " ".join(text_parts).lower()
    if any(marker in text for marker in (
        "rejected",
        "could not use",
        "probe_error",
        "commit_error",
        "failed",
    )):
        return "manager reported rejection"
    return ""


def _state_summary(view: dict[str, Any]) -> str:
    proof_status = _dict(view.get("proof_status"))
    current_goal = _dict(view.get("current_goal"))
    goal_type = str(
        proof_status.get("goal_type")
        or current_goal.get("goal_type")
        or "unknown"
    )
    layer = str(proof_status.get("current_layer") or "").strip()
    focus = str(proof_status.get("view_focus") or current_goal.get("view_focus") or "").strip()
    remaining = proof_status.get("remaining_goals")
    pieces = [goal_type]
    if layer:
        pieces.append(layer)
    if focus and focus != layer:
        pieces.append(focus)
    goal_label = "goals" if remaining != 1 else "goal"
    if isinstance(remaining, int) and not isinstance(remaining, bool):
        return (
            f"{' / '.join(pieces)}, {remaining} {goal_label}, "
            f"goal {_goal_chars(view)} chars"
        )
    return f"{' / '.join(pieces)}, goal {_goal_chars(view)} chars"


def _goal_chars(view: dict[str, Any]) -> int:
    current_goal = _dict(view.get("current_goal"))
    value = current_goal.get("char_count")
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    lines = current_goal.get("lines")
    if isinstance(lines, list):
        return len("\n".join(str(line) for line in lines))
    return 0


def _inspect_topics(view: dict[str, Any]) -> list[str]:
    handles = _dict(view.get("inspect_lookup_handles"))
    out: list[str] = []
    for item in _list(handles.get("ask_manager_for")):
        payload = _dict(_dict(item).get("payload"))
        topic = payload.get("topic")
        if topic:
            out.append(str(topic))
    return out


def _deterministic_signals(
    *,
    intent: dict[str, Any],
    manager_actions: list[Any],
    audit_manager_actions: list[Any] | None = None,
    workspace_view: dict[str, Any],
) -> list[str]:
    signals: list[str] = []
    name = str(intent.get("intent") or "")
    if name == "commit_tactic":
        signals.append("commit_without_probe_check_not_inferred")
    for action in [*manager_actions, *_list(audit_manager_actions)]:
        item = _dict(action)
        if item.get("error_summary"):
            signals.append(f"manager_error:{item.get('error_summary')}")
        observation = _dict(item.get("agent_observation"))
        if observation.get("error_summary"):
            signals.append(f"manager_error:{observation.get('error_summary')}")
        if (
            observation.get("manager_action") == "commit_tactic"
            and "not changed" in str(observation.get("proof_state") or "").lower()
        ):
            signals.append("commit_no_state_change")
    topics = set(_inspect_topics(workspace_view))
    legacy = sorted(topics & {"pivot_context", "bridge_options"})
    if legacy:
        signals.append(f"legacy_topics:{','.join(legacy)}")
    if _goal_chars(workspace_view) >= 3000:
        signals.append("large_goal")
    # Dedupe, preserving first-seen order. The SAME handled error reaches this
    # function from both the live `manager_actions` and the `audit_manager_actions`
    # union (and via both the action-level and the agent_observation-level
    # `error_summary`), which otherwise emits one error as two identical
    # `manager_error:` signals — double-counting that misreads as two failures.
    seen: set[str] = set()
    deduped: list[str] = []
    for sig in signals:
        if sig not in seen:
            seen.add(sig)
            deduped.append(sig)
    return deduped


def _handled_audit_records_for_node(
    run_dir: Path,
    node_id: str,
) -> list[dict[str, Any]]:
    records = []
    audit_path = run_dir / "proof_node_manager_audit.jsonl"
    for item in _read_jsonl(audit_path):
        if item.get("kind") != "agent_intent.handled":
            continue
        if str(item.get("node") or "") != node_id:
            continue
        records.append(item)
    return records


def _next_matching_audit_record(
    records: list[dict[str, Any]],
    start: int,
    intent: dict[str, Any],
) -> tuple[dict[str, Any], int]:
    expected = _intent_signature(intent)
    for index in range(start, len(records)):
        record = records[index]
        if _intent_signature(_dict(record.get("intent"))) == expected:
            return record, index + 1
    return {}, start


def _intent_signature(intent: dict[str, Any]) -> tuple[str, str]:
    name = str(intent.get("intent") or "")
    payload = _dict(intent.get("payload"))
    if name in {"probe_tactic", "commit_tactic"}:
        return name, " ".join(str(payload.get("tactic") or "").split())
    if name == "inspect_context":
        return name, str(payload.get("topic") or "")
    if name == "lookup_symbol":
        return name, str(payload.get("symbol") or "")
    return name, json.dumps(payload, sort_keys=True)


def _manager_action_summary(actions: list[Any]) -> list[str]:
    out: list[str] = []
    for item in actions:
        action = _dict(item)
        label = str(action.get("action") or action.get("label") or "")
        timing = str(action.get("timing") or "")
        if label and timing:
            out.append(f"{label} ({timing})")
        elif label:
            out.append(label)
    return out


def _manager_action_seconds(actions: list[Any]) -> float:
    return sum(
        _parse_timing_seconds(str(_dict(action).get("timing") or ""))
        for action in actions
    )


def _parse_timing_seconds(text: str) -> float:
    match = re.match(r"^\s*([0-9]+(?:\.[0-9]+)?)\s*(ms|s)\s*$", text)
    if not match:
        return 0.0
    value = float(match.group(1))
    return value / 1000.0 if match.group(2) == "ms" else value


def _estimate_submit_time(result_at: datetime | None, manager_seconds: float) -> datetime | None:
    if result_at is None:
        return None
    if manager_seconds <= 0:
        return result_at
    return result_at - timedelta(seconds=manager_seconds)


def _seconds_between(start: datetime | None, end: datetime | None) -> float | None:
    if start is None or end is None:
        return None
    return max(0.0, (end - start).total_seconds())


def _format_delta(start: datetime | None, end: datetime | None) -> str:
    if start is None or end is None:
        return ""
    seconds = max(0, int(round((end - start).total_seconds())))
    hours, remainder = divmod(seconds, 3600)
    minutes, sec = divmod(remainder, 60)
    if hours:
        return f"+{hours}:{minutes:02d}:{sec:02d}"
    return f"+{minutes:02d}:{sec:02d}"


def _format_seconds(value: float) -> str:
    if value <= 0:
        return ""
    if value < 1:
        return f"{round(value * 1000):.0f} ms"
    if value.is_integer():
        return f"{int(value)} s"
    return f"{value:.1f} s"


def _format_optional_seconds(value: float | None) -> str:
    if value is None:
        return ""
    return _format_seconds(value)


def _parse_time(text: str) -> datetime | None:
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _decision_view_link(row: dict[str, Any]) -> str:
    # Two distinct artifacts, both linked: the FULL projected view (workspace_views/
    # turn_NNN.json — what the framework computed) and the INLINE followup the agent
    # actually read (followups/turn_NNN.md — a filtered preview of that view). They
    # diverge (the preview drops panels), so an audit must show what was CONSUMED,
    # not just what was OFFERED.
    path = str(row.get("decision_view_path") or "")
    follow = str(row.get("decision_followup_path") or "")
    view = "initial handoff" if not path else f"[{Path(path).name}]({path})"
    if follow:
        view += f" · [inline read]({follow})"
    return view


def _agent_think_cell(row: dict[str, Any]) -> str:
    """Inter-turn duration, made clickable when the agent's reasoning for this
    turn was extracted into a per-step thinking view."""
    duration = str(row.get("agent_think") or "")
    path = str(row.get("agent_think_path") or "")
    if not path:
        return duration
    return f"[{duration or 'think'}]({path})"


def _quality_for_row(
    *,
    quality_notes: dict[str, str],
    run_label: str,
    row: dict[str, Any],
    placeholder: str,
) -> str:
    node = str(row.get("node") or "")
    turn = str(row.get("turn") or "")
    view_id = str(row.get("view_id") or "")
    candidates = [
        f"{run_label}:{view_id}",
        view_id,
        f"{run_label}:{node}:{turn}",
        f"{node}:{turn}",
    ]
    for key in candidates:
        if key in quality_notes:
            return quality_notes[key]
    return placeholder


def _split_label_path(value: str) -> tuple[str, str]:
    if "=" not in value:
        return "", value
    label, path = value.split("=", 1)
    return label.strip(), path.strip()


def _node_display(node_id: str) -> str:
    if node_id.startswith("Tree-"):
        return "T" + node_id[len("Tree-"):]
    if node_id.startswith("Tree_"):
        return "T" + node_id[len("Tree_"):].replace("_", ".")
    return node_id


def _node_sort_key(node_id: str) -> tuple[Any, ...]:
    text = node_id.replace("Tree-", "").replace("Tree_", "").replace("_", ".")
    parts: list[Any] = []
    for part in re.split(r"([0-9]+)", text):
        if not part:
            continue
        parts.append(int(part) if part.isdigit() else part)
    return tuple(parts)


def _json_chars(value: Any) -> int:
    return len(json.dumps(value, ensure_ascii=False, sort_keys=True))


def _md_cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ").strip()


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _int(value: Any) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _bool(value: Any, *, default: bool = False) -> bool:
    return value if isinstance(value, bool) else default


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "runs",
        nargs="*",
        help="Iteration run dirs, optionally LABEL=PATH.",
    )
    parser.add_argument(
        "--run",
        dest="named_runs",
        action="append",
        default=[],
        help="Iteration run dir, optionally LABEL=PATH. Can be repeated.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Markdown output path. Defaults to stdout.",
    )
    parser.add_argument(
        "--json-output",
        type=Path,
        help="Optional machine-readable JSON report path.",
    )
    parser.add_argument(
        "--quality-file",
        type=Path,
        help=(
            "Optional JSON object mapping row ids such as T0.0-1 or "
            "'LABEL:T0.0-1' to quality notes."
        ),
    )
    parser.add_argument(
        "--quality-placeholder",
        default="",
        help="Text used when no quality note is supplied.",
    )
    parser.add_argument(
        "--chronological",
        action="store_true",
        help="Sort all node turns chronologically instead of grouping by node.",
    )
    args = parser.parse_args(argv)

    run_values = [*args.named_runs, *args.runs]
    if not run_values:
        parser.error("provide at least one run dir")
    specs = parse_run_specs(run_values)
    report = build_report(specs, chronological=args.chronological)
    quality_notes = load_quality_notes(args.quality_file)
    markdown = render_markdown(
        report,
        quality_notes=quality_notes,
        quality_placeholder=args.quality_placeholder,
    )
    write_outputs(
        report,
        markdown_output=args.output,
        json_output=args.json_output,
        markdown=markdown,
    )
    if args.output is None:
        print(markdown, end="")
    else:
        print(f"AGENT-VIEW-TIMELINE: wrote {args.output}")
    if args.json_output is not None:
        print(f"AGENT-VIEW-TIMELINE: wrote {args.json_output}")
    if not os.environ.get("SHANNON_BUNDLE_INTERNAL"):
        print(
            "NOTE: this is the bare timeline table only — no committed proof, no "
            "env header, no per-step thinking links, and view links use absolute "
            "machine paths. For the canonical, committable, GitHub-portable run "
            "report (the bundle that wraps this table), use:\n"
            "  python3 -m workflow.validation.run_report_bundle <run_iteration_dir> "
            "--timestamp <TS> [--lemma L --model M --profile P ...]",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
