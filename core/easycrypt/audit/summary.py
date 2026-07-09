"""Compose a `RunSummary` from a JSONL trace path."""
from __future__ import annotations

from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Optional

from .io import read_jsonl
from .types import RunSummary
from .timeline import extract_timeline
from .hook_stats import count_hook_fires, list_hook_fires
from .stuck import detect_stuck_windows


_TOOL_FLAGS = (
    "-search-skeleton",      # listed first so the prefix-match below picks
    "-search",               # the longer name when both substrings would match
    "-sig",
    "-where",
    "-lemma-hints",
    "-tactic-forms",
    "-bridge-lemmas",
    "-goal-info",
    "-try",
    "-next",
    "-chain",
    "-prev",
    "-start",
    "-status",
    "-show-proof",
    "-diagnose",
    "-align",
    "-suggest-close",
    "-inv-from-lemma",
    "-members",
    "-clones",
    "-subgoal-gap",
    "-call-subgoals",
    "-bridge-probe",
)


def _count_tool_flags(jsonl_path: Path) -> tuple[int, int, dict[str, int]]:
    """Return (total_tool_calls, total_bash_calls, tool_breakdown).

    `tool_breakdown` counts session_cli flag occurrences. A bash command
    that contains `session_cli.py` and one of the listed flags is counted
    once per flag. Agents sometimes pack multiple flags in one command;
    in that case we count each (rare in practice).
    """
    recs = read_jsonl(jsonl_path)
    total_tool = 0
    total_bash = 0
    breakdown: Counter[str] = Counter()
    for r in recs:
        if r.get("type") != "assistant":
            continue
        msg = r.get("message") or {}
        for c in (msg.get("content") or []):
            if c.get("type") != "tool_use":
                continue
            total_tool += 1
            if c.get("name") != "Bash":
                continue
            total_bash += 1
            cmd = (c.get("input") or {}).get("command", "")
            for flag in _TOOL_FLAGS:
                if flag in cmd:
                    breakdown[flag] += 1
                    # Don't break — agent may use multiple flags. But avoid
                    # double-counting `-search` when `-search-skeleton`
                    # already matched (prefix discipline).
                    if flag == "-search-skeleton":
                        break
            else:
                continue
    return total_tool, total_bash, dict(breakdown)


def _wall_minutes(jsonl_path: Path) -> float:
    """First-to-last assistant timestamp delta, in minutes."""
    recs = read_jsonl(jsonl_path)
    first: Optional[datetime] = None
    last: Optional[datetime] = None
    for r in recs:
        if r.get("type") != "assistant":
            continue
        ts_raw = r.get("timestamp")
        if not ts_raw:
            continue
        try:
            ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
        except ValueError:
            continue
        if first is None:
            first = ts
        last = ts
    if first is None or last is None:
        return 0.0
    return (last - first).total_seconds() / 60


def _project_dir_name(jsonl_path: Path) -> str:
    """The project-folder component (e.g. '-private-tmp-cap-step2-2-r1')."""
    parent = jsonl_path.parent.name
    return parent


def _session_id(jsonl_path: Path) -> str:
    return jsonl_path.stem


def summarize_run(jsonl_path: Path) -> RunSummary:
    """Single entry-point: produce a complete `RunSummary` for a trace."""
    p = Path(jsonl_path)
    timeline = extract_timeline(p)
    counts = count_hook_fires(p)
    fires = list_hook_fires(p)
    windows = detect_stuck_windows(timeline)
    total_tool, total_bash, tool_break = _count_tool_flags(p)
    return RunSummary(
        session_id=_session_id(p),
        project_dir=_project_dir_name(p),
        total_thinking_blocks=len(timeline),
        total_tool_calls=total_tool,
        total_bash_calls=total_bash,
        wall_minutes=_wall_minutes(p),
        timeline=timeline,
        hook_fires=fires,
        hook_counts={k: v for k, v in counts.items() if v > 0},
        stuck_windows=windows,
        tool_breakdown={k: v for k, v in tool_break.items() if v > 0},
    )
