"""Count and locate `[MARKER]` fires in a session trace.

Each tool result is scanned for known auto-fire markers (the canonical
list lives in HOOKS.md). Returns counts (for quick stats) and full
location records (for timeline annotation).

Markers ARE the contract — adding a new hook should add to HOOKS.md and
this list. We deliberately use the literal marker strings rather than
parsing structure so this module catches both registry-driven and
inline-emit hooks uniformly.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

from .io import read_jsonl, stringify_content
from .types import HookFire

# Canonical marker list. Keep in sync with HOOKS.md (#1-27 + lifecycle).
# Order doesn't matter for counting; for `list_hook_fires`, hooks are
# returned in trace-traversal order regardless of this list's order.
KNOWN_MARKERS = [
    # Action result / verdict (L0)
    "[DAEMON_REJECTED]",
    "[POST-CALL-INV-HINT]",
    "[STATE-DIFF]",
    "[GOAL_CLOSED]",
    "[ALL_GOALS_CLOSED]",
    "[TACTIC_NO_EFFECT_AUTO_REVERTED]",
    "[GOAL-TOO-LARGE]",
    "[AUTO-NOPROG-HINT]",
    "[AUTO-SIG]",
    "[CLASS:",                             # prefix-match: [CLASS: SYNTAX], etc.
    "[STRICT_WARNING]",
    # Goal text (L1)
    "[goal:",                              # prefix-match: [goal: pRHL] etc.
    # Daemon-verified ready-to-act (L2)
    "[AUTO-PIVOT-CALL-READY]",
    "[AUTO-PIVOT-VERIFIED]",
    "[AUTO-BRIDGE-SUGGEST",                # prefix-match: SUGGEST or SUGGEST/VERIFIED
    "[AUTO-REWRITE-PROBE]",
    # File helpers (L3)
    "[AUTO-DIFF]",
    "[AUTO-PIVOT]",
    "[AUTO-CALL-SUGGEST]",
    # Strategy (L4)
    "[AUTO-LEMMA-HINTS]",
    "[AUTO-SELF-HINTS]",
    # Lookups (L5)
    "[AUTO-RESOLVED-NAMES]",
    "[WHERE-HIT]",
    # Direct-emit (bypass _reorder_display)
    "[META_COMMAND_REFUSED]",
    "[TRY]",
    "[TRY-CHAIN]",
    "[BRIDGE-PROBE]",
    "[RESTART-NOTICE]",
    "[SEARCH-QUERY-AUTOFIX]",
    "[SEARCH-FALLBACK-HINT]",
    "[POST-QED]",
]


def _walk_tool_results(jsonl_path: Path):
    """Yield (timestamp_iso, tool_use_id, result_text) for every tool_result."""
    recs = read_jsonl(jsonl_path)
    for r in recs:
        if r.get("type") != "user":
            continue
        ts = r.get("timestamp", "")
        msg = r.get("message") or {}
        content = msg.get("content")
        if not isinstance(content, list):
            continue
        for c in content:
            if isinstance(c, dict) and c.get("type") == "tool_result":
                yield ts, c.get("tool_use_id", ""), stringify_content(c.get("content", ""))


def count_hook_fires(
    jsonl_path: Path,
    markers: Optional[list[str]] = None,
) -> dict[str, int]:
    """Return {marker → fire-count} across all tool results in the trace.

    A "fire" is one occurrence of the marker substring in one tool result.
    Multiple occurrences in a single result count separately (e.g. when
    chain mode emits multiple `[STATE-DIFF]` blocks per chain step).
    """
    if markers is None:
        markers = KNOWN_MARKERS
    counts = {m: 0 for m in markers}
    for _ts, _tid, result in _walk_tool_results(jsonl_path):
        for m in markers:
            counts[m] += result.count(m)
    return counts


def list_hook_fires(
    jsonl_path: Path,
    markers: Optional[list[str]] = None,
) -> list[HookFire]:
    """Return per-fire records ordered by trace position.

    Each `HookFire` includes a short excerpt around the marker so the
    audit reader can see what fired without re-loading the trace.
    """
    if markers is None:
        markers = KNOWN_MARKERS

    # Build assistant-msg → step_n mapping from the same trace
    recs = read_jsonl(jsonl_path)

    tool_to_step: dict[str, tuple[int, float]] = {}
    t0: Optional[datetime] = None
    step_n = 0
    pending_step: tuple[int, float] = (0, 0.0)
    for r in recs:
        if r.get("type") == "assistant":
            ts_raw = r.get("timestamp", "")
            try:
                ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                ts = None
            if ts is not None:
                if t0 is None:
                    t0 = ts
                rel_min = (ts - t0).total_seconds() / 60
            else:
                rel_min = pending_step[1]
            msg = r.get("message") or {}
            for c in (msg.get("content") or []):
                if c.get("type") == "thinking":
                    step_n += 1
                    pending_step = (step_n, rel_min)
                if c.get("type") == "tool_use":
                    tid = c.get("id")
                    if tid:
                        tool_to_step[tid] = pending_step

    fires: list[HookFire] = []
    for r in recs:
        if r.get("type") != "user":
            continue
        msg = r.get("message") or {}
        content = msg.get("content")
        if not isinstance(content, list):
            continue
        for c in content:
            if not (isinstance(c, dict) and c.get("type") == "tool_result"):
                continue
            tid = c.get("tool_use_id", "")
            text = stringify_content(c.get("content", ""))
            step_info = tool_to_step.get(tid, (0, 0.0))
            for m in markers:
                start = 0
                while True:
                    idx = text.find(m, start)
                    if idx < 0:
                        break
                    excerpt = text[max(0, idx - 30):idx + len(m) + 50]
                    excerpt = excerpt.replace("\n", " ")
                    fires.append(HookFire(
                        marker=m,
                        step_n=step_info[0],
                        t_min=step_info[1],
                        excerpt=excerpt[:120],
                    ))
                    start = idx + len(m)
    return fires
