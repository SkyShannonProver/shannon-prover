#!/usr/bin/env python3
"""Trace analyzer (Phase 0 / M2): extract structured behavioral signals
from Claude Code subagent trace files produced by the prover runs.

Each trace is a newline-delimited JSONL file at
``~/.claude/projects/<proj-slug>/<session_id>.jsonl``. Events include
assistant messages (thinking blocks, text, tool_use) and user messages
(tool_result). The prover runs as one subagent per tree node, so each
tree node has its own trace file.

This analyzer produces, per trace:
  - basic volumetrics: # thinking blocks, # tool calls, # tactics
    committed, # undos, duration
  - AUTO-signal engagement: when did the prover first see each
    [AUTO-DIFF]/[AUTO-PIVOT] output? How many times total?
  - pivot engagement: when did prover first mention a file-local pivot
    in thinking? Did it ever submit an ``apply <pivot>`` / ``call
    <pivot>`` tool_use? Was it committed to history?
  - self-correction: how many ``-prev`` tool calls; what thinking
    immediately preceded them; did the prover narrate "let me back up"
    / "too complex" / "rethink" style intent?
  - pattern match examples: snippets of thinking that mention
    specific keywords of interest (pivot names, "apply", "inline *",
    "unfold", etc.)

Output formats:
  - ``--format summary`` (default): per-trace human-readable block
  - ``--format json``: per-trace structured JSON, one per line
  - ``--format csv``: flat CSV for aggregation across traces

Intended use: aggregate across many runs to build base-rate data on
LLM prover behavior (how often does it engage with AUTO-PIVOT? How
quickly does it self-correct? Under what conditions does it commit a
pivot apply?). Fed into the research-mode M1 benchmarking runner.

Usage:
    python3 -m workflow.tools.trace_analyzer <trace.jsonl> [trace.jsonl ...]
    python3 -m workflow.tools.trace_analyzer --format json <trace.jsonl>
    python3 -m workflow.tools.trace_analyzer --since 23:00 --format csv ~/.claude/projects/-p/*.jsonl
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

# Regexes for classifying tool calls + parsing tactics out of session_cli.
CHAIN_RE = re.compile(r"-chain\s+(?:--keep-on-fail\s+)?-c\s+['\"]?(.+?)['\"]?\s*(?:2>&1|\|)?$",
                      re.DOTALL)
NEXT_RE = re.compile(r"-next\s+-c\s+['\"]?(.+?)['\"]?\s*(?:2>&1|\|)?$", re.DOTALL)
PIVOT_NAME_RE = re.compile(
    r"\b(CCP_OCCP|pr_CCP_OCCP|chacha_enc1|chacha_enc2|poly_mac1|poly_mac2|"
    r"CCA_CPA_UFCMA|step1|step2|step2_1|step2_2|step2_3|step3|step4_\w+|"
    r"conclusion|UFCMA_genCC|pr_RO_FinRO_D|pr_TPI_ok)\b"
)
APPLY_PIVOT_RE = re.compile(
    r"\b(?:apply|rewrite|call)\s+\(?\s*(CCP_OCCP|pr_CCP_OCCP|chacha_enc1|chacha_enc2|"
    r"poly_mac1|poly_mac2|CCA_CPA_UFCMA|step\d\w*|conclusion|UFCMA_genCC|"
    r"pr_RO_FinRO_D|pr_TPI_ok)\b"
)
INLINE_ALL_RE = re.compile(r"\binline\s*\*\s*\.")
WHILE_INV_RE = re.compile(r"\bwhile\s*\{[12]\}\s*\(")
BACK_UP_INTENT_RE = re.compile(
    r"\b(let me (?:back up|undo|roll back|reconsider|rethink|try (?:a )?different)|"
    r"(?:too|quite) complex|overcomplicated|instead of|back up|abandon)\b",
    re.IGNORECASE,
)
AUTO_TAG_RE = re.compile(r"\[(AUTO-\w+)\]")


@dataclass
class EventRecord:
    """One notable event in the trace timeline. Compact summary."""
    t: float                   # seconds since trace start
    kind: str                  # "think" | "say" | "tool" | "result"
    detail: str                # short human-readable
    pivot_mentions: list[str] = field(default_factory=list)
    auto_tags: list[str] = field(default_factory=list)


@dataclass
class TraceStats:
    trace_id: str
    path: str
    start_iso: str = ""
    end_iso: str = ""
    duration_s: float = 0.0

    # Volumetrics
    thinking_blocks: int = 0
    thinking_chars_total: int = 0
    say_blocks: int = 0
    tool_calls_total: int = 0
    bash_calls: int = 0
    session_cli_calls: int = 0
    chain_calls: int = 0
    next_calls: int = 0
    prev_calls: int = 0
    start_calls: int = 0
    status_calls: int = 0
    goal_info_calls: int = 0
    agent_view_calls: int = 0
    episode_view_calls: int = 0
    diagnose_calls: int = 0
    try_calls: int = 0

    # EDA contract surfaces observed in tool results.
    tactic_execution_blocks: int = 0
    command_summary_blocks: int = 0
    commit_response_blocks: int = 0
    agent_view_json_blocks: int = 0
    episode_view_json_blocks: int = 0

    # Tactic volume (what prover actually submitted, not what EC accepted)
    tactics_submitted: int = 0
    inline_all_submissions: int = 0
    while_inv_submissions: int = 0

    # Pivot engagement
    pivot_mentions_in_thinking: int = 0
    first_pivot_mention_t: Optional[float] = None
    first_pivot_mention_name: Optional[str] = None
    apply_or_call_pivot_submissions: int = 0
    distinct_pivots_applied: list[str] = field(default_factory=list)

    # Self-correction
    back_up_intent_mentions: int = 0
    first_back_up_intent_t: Optional[float] = None

    # AUTO-* signal reception (counted in tool_result blocks)
    auto_tag_counts: dict[str, int] = field(default_factory=dict)
    first_auto_pivot_t: Optional[float] = None

    # Error pattern hits — from EC's output surfaced in tool_result
    error_messages_surfaced: int = 0

    # Timeline samples
    events: list[EventRecord] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


def _parse_iso(ts: str) -> Optional[datetime]:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None


def _extract_bash_command(tool_use_block: dict) -> str:
    inp = tool_use_block.get("input", {}) or {}
    return inp.get("command", "") or ""


def _classify_bash(cmd: str) -> dict[str, Any]:
    """Classify a Bash command string into categories used by stats."""
    is_cli = "session_cli" in cmd
    flags = {
        "is_session_cli": is_cli,
        "is_chain": is_cli and "-chain" in cmd,
        "is_next": is_cli and ("-next " in cmd or cmd.rstrip().endswith("-next")),
        "is_prev": is_cli and "-prev" in cmd,
        "is_start": is_cli and "-start" in cmd,
        "is_status": is_cli and "-status" in cmd,
        "is_goal_info": is_cli and "-goal-info" in cmd,
        "is_agent_view": is_cli and "-agent-view" in cmd,
        "is_episode_view": is_cli and "-episode-view" in cmd,
        "is_diagnose": is_cli and "-diagnose" in cmd,
        "is_try": is_cli and "-try" in cmd,
        "tactic_text": "",
    }
    # Extract tactic body from -c '<tactic>'
    m = re.search(r"-c\s+['\"]([^'\"]+)['\"]", cmd)
    if m:
        flags["tactic_text"] = m.group(1).strip()
    return flags


def _count_tactics_in_chain(body: str) -> int:
    """Count tactic statements in a -chain -c body. Tactics end with '.'
    followed by whitespace (or EOS). Module paths like A.main are not
    tactic terminators."""
    n = 0
    depth_p = 0
    depth_b = 0
    in_str = False
    for i, ch in enumerate(body):
        if ch == "'" or ch == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch == "(":
            depth_p += 1
        elif ch == ")" and depth_p > 0:
            depth_p -= 1
        elif ch == "[":
            depth_b += 1
        elif ch == "]" and depth_b > 0:
            depth_b -= 1
        elif ch == "." and depth_p == 0 and depth_b == 0:
            nxt = body[i + 1:i + 2]
            if not nxt or nxt.isspace():
                n += 1
    return n


def _extract_pivot_names_from_text(text: str) -> list[str]:
    return list(dict.fromkeys(PIVOT_NAME_RE.findall(text or "")))


def _extract_auto_tags(text: str) -> list[str]:
    if not text:
        return []
    return list(dict.fromkeys(AUTO_TAG_RE.findall(text)))


# ---------------------------------------------------------------------------
# Main analyzer
# ---------------------------------------------------------------------------


def analyze_trace(path: Path, sample_events_max: int = 40) -> TraceStats:
    stats = TraceStats(trace_id=path.stem[:12], path=str(path))
    start_dt: Optional[datetime] = None
    end_dt: Optional[datetime] = None
    tool_use_by_id: dict[str, dict] = {}

    with open(path) as f:
        for line in f:
            try:
                ev = json.loads(line)
            except Exception:
                continue
            ts = _parse_iso(ev.get("timestamp", ""))
            if ts:
                if start_dt is None or ts < start_dt:
                    start_dt = ts
                if end_dt is None or ts > end_dt:
                    end_dt = ts
            etype = ev.get("type")
            content = ev.get("message", {}).get("content", [])
            if not isinstance(content, list):
                continue
            rel_t = ((ts - start_dt).total_seconds()
                     if (ts and start_dt) else 0.0)
            for blk in content:
                if not isinstance(blk, dict):
                    continue
                btype = blk.get("type")
                if etype == "assistant" and btype == "thinking":
                    stats.thinking_blocks += 1
                    txt = blk.get("thinking", "") or ""
                    stats.thinking_chars_total += len(txt)
                    pivots = _extract_pivot_names_from_text(txt)
                    if pivots:
                        stats.pivot_mentions_in_thinking += len(pivots)
                        if stats.first_pivot_mention_t is None:
                            stats.first_pivot_mention_t = rel_t
                            stats.first_pivot_mention_name = pivots[0]
                    if BACK_UP_INTENT_RE.search(txt):
                        stats.back_up_intent_mentions += 1
                        if stats.first_back_up_intent_t is None:
                            stats.first_back_up_intent_t = rel_t
                    if len(stats.events) < sample_events_max:
                        stats.events.append(EventRecord(
                            t=rel_t, kind="think",
                            detail=txt[:200].replace("\n", " "),
                            pivot_mentions=pivots,
                        ))
                elif etype == "assistant" and btype == "text":
                    stats.say_blocks += 1
                    txt = blk.get("text", "") or ""
                    if len(stats.events) < sample_events_max:
                        stats.events.append(EventRecord(
                            t=rel_t, kind="say",
                            detail=txt[:180].replace("\n", " "),
                        ))
                elif etype == "assistant" and btype == "tool_use":
                    stats.tool_calls_total += 1
                    tool_name = blk.get("name", "")
                    tool_use_by_id[blk.get("id", "")] = {
                        "rel_t": rel_t, "name": tool_name, "input": blk.get("input", {})
                    }
                    if tool_name == "Bash":
                        stats.bash_calls += 1
                        cmd = _extract_bash_command(blk)
                        flags = _classify_bash(cmd)
                        if flags["is_session_cli"]:
                            stats.session_cli_calls += 1
                        if flags["is_chain"]:
                            stats.chain_calls += 1
                        if flags["is_next"]:
                            stats.next_calls += 1
                        if flags["is_prev"]:
                            stats.prev_calls += 1
                        if flags["is_start"]:
                            stats.start_calls += 1
                        if flags["is_status"]:
                            stats.status_calls += 1
                        if flags["is_goal_info"]:
                            stats.goal_info_calls += 1
                        if flags["is_agent_view"]:
                            stats.agent_view_calls += 1
                        if flags["is_episode_view"]:
                            stats.episode_view_calls += 1
                        if flags["is_diagnose"]:
                            stats.diagnose_calls += 1
                        if flags["is_try"]:
                            stats.try_calls += 1
                        tac = flags["tactic_text"]
                        if tac:
                            stats.tactics_submitted += _count_tactics_in_chain(tac)
                            if INLINE_ALL_RE.search(tac):
                                stats.inline_all_submissions += 1
                            if WHILE_INV_RE.search(tac):
                                stats.while_inv_submissions += 1
                            m = APPLY_PIVOT_RE.search(tac)
                            if m:
                                stats.apply_or_call_pivot_submissions += 1
                                name = m.group(1)
                                if name not in stats.distinct_pivots_applied:
                                    stats.distinct_pivots_applied.append(name)
                        if len(stats.events) < sample_events_max:
                            stats.events.append(EventRecord(
                                t=rel_t, kind="tool",
                                detail=(tac[:160] if tac else cmd[:160]),
                            ))
                elif etype == "user" and btype == "tool_result":
                    c = blk.get("content", "")
                    text = c if isinstance(c, str) else str(c)
                    tags = _extract_auto_tags(text)
                    for tag in tags:
                        stats.auto_tag_counts[tag] = (
                            stats.auto_tag_counts.get(tag, 0) + 1
                        )
                    if "[AUTO-PIVOT]" in text and stats.first_auto_pivot_t is None:
                        stats.first_auto_pivot_t = rel_t
                    if re.search(r"\[error[\w\-]*\]", text):
                        stats.error_messages_surfaced += 1
                    if "[TACTIC-EXECUTION-RESULT]" in text:
                        stats.tactic_execution_blocks += text.count(
                            "[TACTIC-EXECUTION-RESULT]",
                        )
                    if "[COMMAND-SUMMARY]" in text:
                        stats.command_summary_blocks += text.count("[COMMAND-SUMMARY]")
                    if "[COMMIT-RESPONSE]" in text:
                        stats.commit_response_blocks += text.count("[COMMIT-RESPONSE]")
                    if '"kind": "agent_proof_view"' in text or "'kind': 'agent_proof_view'" in text:
                        stats.agent_view_json_blocks += 1
                    if '"kind": "session_episode_timeline"' in text or "'kind': 'session_episode_timeline'" in text:
                        stats.episode_view_json_blocks += 1
                    if len(stats.events) < sample_events_max and tags:
                        stats.events.append(EventRecord(
                            t=rel_t, kind="result",
                            detail=f"tags={tags}; {text[:120].replace(chr(10), ' ')}",
                            auto_tags=tags,
                        ))

    if start_dt:
        stats.start_iso = start_dt.isoformat()
    if end_dt:
        stats.end_iso = end_dt.isoformat()
    if start_dt and end_dt:
        stats.duration_s = (end_dt - start_dt).total_seconds()
    return stats


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------


def format_summary(s: TraceStats) -> str:
    lines = [
        f"=== trace {s.trace_id} ({Path(s.path).name}) ===",
        f"  duration: {s.duration_s:.0f}s  start={s.start_iso[-15:-6] if s.start_iso else '-'}",
        f"  thinking blocks: {s.thinking_blocks}  (total chars: {s.thinking_chars_total})",
        f"  say blocks:      {s.say_blocks}",
        f"  tool calls:      {s.tool_calls_total}  (bash: {s.bash_calls})",
        f"  session_cli:     total={s.session_cli_calls}  chain={s.chain_calls}  next={s.next_calls}  prev={s.prev_calls}  start={s.start_calls}  status={s.status_calls}  goal-info={s.goal_info_calls}  agent-view={s.agent_view_calls}  episode-view={s.episode_view_calls}  diagnose={s.diagnose_calls}  try={s.try_calls}",
        f"  EDA surfaces:    tactic-execution={s.tactic_execution_blocks}  command-summary={s.command_summary_blocks}  commit-response={s.commit_response_blocks}  agent-view-json={s.agent_view_json_blocks}  episode-view-json={s.episode_view_json_blocks}",
        f"  tactics submitted: {s.tactics_submitted}  (inline*: {s.inline_all_submissions}, while{{N}}(inv): {s.while_inv_submissions})",
        f"  pivot-apply tool_uses: {s.apply_or_call_pivot_submissions}  (distinct: {s.distinct_pivots_applied})",
        f"  pivot mentions in thinking: {s.pivot_mentions_in_thinking}  "
        f"(first@{_fmt_t(s.first_pivot_mention_t)} name={s.first_pivot_mention_name})",
        f"  back-up intent mentions: {s.back_up_intent_mentions}  "
        f"(first@{_fmt_t(s.first_back_up_intent_t)})",
        f"  AUTO-* tags in tool_results: {s.auto_tag_counts}  "
        f"(first AUTO-PIVOT@{_fmt_t(s.first_auto_pivot_t)})",
        f"  error messages surfaced:    {s.error_messages_surfaced}",
    ]
    return "\n".join(lines)


def _fmt_t(t: Optional[float]) -> str:
    if t is None:
        return "-"
    m = int(t // 60)
    sec = int(t % 60)
    return f"{m:02d}:{sec:02d}"


CSV_FIELDS = [
    "trace_id", "duration_s", "thinking_blocks", "thinking_chars_total",
    "tool_calls_total", "bash_calls", "session_cli_calls", "chain_calls",
    "next_calls", "prev_calls", "start_calls", "status_calls",
    "goal_info_calls", "agent_view_calls", "episode_view_calls",
    "diagnose_calls", "try_calls", "command_summary_blocks",
    "commit_response_blocks", "agent_view_json_blocks",
    "episode_view_json_blocks",
    "tactics_submitted", "inline_all_submissions", "while_inv_submissions",
    "pivot_mentions_in_thinking", "first_pivot_mention_t",
    "apply_or_call_pivot_submissions", "distinct_pivots_applied",
    "back_up_intent_mentions", "first_back_up_intent_t",
    "first_auto_pivot_t", "error_messages_surfaced",
    "n_AUTO_PIVOT", "n_AUTO_DIFF", "n_AUTO_KB", "n_AUTO_SIG",
]


def row_for_csv(s: TraceStats) -> dict:
    row = {k: getattr(s, k, None) for k in CSV_FIELDS if hasattr(s, k)}
    row["trace_id"] = s.trace_id
    row["duration_s"] = f"{s.duration_s:.0f}"
    row["first_pivot_mention_t"] = (
        f"{s.first_pivot_mention_t:.0f}" if s.first_pivot_mention_t is not None else ""
    )
    row["first_back_up_intent_t"] = (
        f"{s.first_back_up_intent_t:.0f}" if s.first_back_up_intent_t is not None else ""
    )
    row["first_auto_pivot_t"] = (
        f"{s.first_auto_pivot_t:.0f}" if s.first_auto_pivot_t is not None else ""
    )
    row["distinct_pivots_applied"] = "|".join(s.distinct_pivots_applied)
    row["n_AUTO_PIVOT"] = s.auto_tag_counts.get("AUTO-PIVOT", 0)
    row["n_AUTO_DIFF"] = s.auto_tag_counts.get("AUTO-DIFF", 0)
    row["n_AUTO_SIG"] = s.auto_tag_counts.get("AUTO-SIG", 0)
    return row


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("traces", nargs="+", type=Path,
                    help="trace .jsonl files (or glob)")
    ap.add_argument("--format", choices=("summary", "json", "csv"),
                    default="summary")
    ap.add_argument("--min-duration", type=float, default=0.0,
                    help="skip traces shorter than N seconds")
    args = ap.parse_args()

    all_stats: list[TraceStats] = []
    for p in args.traces:
        if not p.exists():
            print(f"# skip {p}: not found", file=sys.stderr)
            continue
        try:
            stats = analyze_trace(p)
        except Exception as e:
            print(f"# error on {p}: {type(e).__name__}: {e}",
                  file=sys.stderr)
            continue
        if stats.duration_s < args.min_duration:
            continue
        all_stats.append(stats)

    if args.format == "summary":
        for s in all_stats:
            print(format_summary(s))
            print()
    elif args.format == "json":
        for s in all_stats:
            print(json.dumps(s.to_dict(), default=str))
    elif args.format == "csv":
        w = csv.DictWriter(sys.stdout, fieldnames=CSV_FIELDS)
        w.writeheader()
        for s in all_stats:
            w.writerow(row_for_csv(s))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
