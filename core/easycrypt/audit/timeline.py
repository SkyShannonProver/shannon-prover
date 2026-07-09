"""Extract per-step timeline from a Claude Code session JSONL.

A "step" pairs one extended-thinking block with the tool calls that
followed before the next thinking block. The principal action is the
first commit-style tool call (`-next` / `-chain`), or the first probe
(`-try`), or the first action of any kind if none of those.
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from .io import read_jsonl, stringify_content
from .types import Step

_TACTIC_CMD_RE = re.compile(r"-(next|chain|try|prev)\b")
_TACTIC_TEXT_RE = re.compile(r"-c\s+['\"]([^'\"]{0,200})")
_REMAINING_GOALS_RE = re.compile(r"(\d+) subgoal\(s\) remaining|remaining: (\d+)")
_TAC_COUNT_RE = re.compile(r"(\d+) tactics accepted")


def _detect_signal(result_text: str) -> str:
    """Extract a short signal label from a tool result. Multi-label (space-
    separated) when several apply.
    """
    if not result_text:
        return ""
    sigs: list[str] = []
    if "verdict=PROGRESS_DECOMPOSITION" in result_text:
        sigs.append("DECOMP")
    elif "verdict=PROGRESS" in result_text:
        sigs.append("PROGRESS")
    if "verdict=REGRESSION" in result_text:
        sigs.append("REGRESS")
    if "verdict=NEUTRAL" in result_text:
        sigs.append("NEUTRAL")
    if "AUTO-REVERTED" in result_text or "TACTIC_NO_EFFECT" in result_text:
        sigs.append("NO-OP-REV")
    if "DAEMON_REJECTED" in result_text:
        sigs.append("DAEMON-REJ")
    if "GOAL_CLOSED" in result_text and "ALL_GOALS_CLOSED" not in result_text:
        sigs.append("CLOSED")
    if "ALL_GOALS_CLOSED" in result_text:
        sigs.append("ALL-CLOSED")
    if "all_accepted: False" in result_text:
        sigs.append("CHAIN-FAIL")
    if "[TRY] accepted: False" in result_text:
        sigs.append("TRY-REJ")
    elif "[TRY] accepted: True" in result_text:
        sigs.append("TRY-OK")
    if "[AUTO-SIG]" in result_text:
        sigs.append("AUTO-SIG")
    m = _TAC_COUNT_RE.search(result_text)
    if m:
        sigs.append(f"tac={m.group(1)}")
    m2 = _REMAINING_GOALS_RE.search(result_text)
    if m2:
        n = m2.group(1) or m2.group(2)
        sigs.append(f"sg={n}")
    return " ".join(sigs)


def _extract_tactic(cmd: str) -> str:
    """Pull the tactic text out of a session_cli `-c '...'` argument."""
    m = _TACTIC_TEXT_RE.search(cmd)
    if m:
        return m.group(1)[:120]
    return cmd[:100]


def _is_tactic_cmd(cmd: str) -> bool:
    return bool(_TACTIC_CMD_RE.search(cmd))


def _principal_kind(cmd: str) -> int:
    """Lower number = more principal. Used to pick which tool call best
    represents the agent's intent in this step.
    """
    if "-next" in cmd or "-chain" in cmd:
        return 0
    if "-try" in cmd:
        return 1
    if "-prev" in cmd:
        return 2
    return 3


def extract_timeline(jsonl_path: Path) -> list[Step]:
    """Parse the trace and return per-step records.

    Robustness: assumes the JSONL has the standard Claude Code format
    (records with `type: assistant|user|...`, content arrays with
    `type: thinking|text|tool_use`). Skips records that don't fit.
    """
    recs = read_jsonl(jsonl_path)

    # First pass: build tool_use_id → result mapping
    tool_results: dict[str, str] = {}
    for r in recs:
        if r.get("type") != "user":
            continue
        msg = r.get("message") or {}
        content = msg.get("content")
        if not isinstance(content, list):
            continue
        for c in content:
            if isinstance(c, dict) and c.get("type") == "tool_result":
                tid = c.get("tool_use_id")
                if tid:
                    tool_results[tid] = stringify_content(c.get("content", ""))

    # Second pass: group by thinking blocks
    t0: Optional[datetime] = None
    step_n = 0
    groups: list[dict] = []
    cur: Optional[dict] = None

    def _ts_to_min(ts_raw: str) -> float:
        nonlocal t0
        try:
            ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return 0.0
        if t0 is None:
            t0 = ts
        return (ts - t0).total_seconds() / 60

    for r in recs:
        if r.get("type") != "assistant":
            continue
        ts_raw = r.get("timestamp") or ""
        if not ts_raw:
            continue
        rel_min = _ts_to_min(ts_raw)
        msg = r.get("message") or {}
        content = msg.get("content") or []
        for c in content:
            t = c.get("type")
            if t == "thinking":
                step_n += 1
                if cur is not None:
                    groups.append(cur)
                think_text = (c.get("thinking") or "").strip()
                cur = {
                    "step_n": step_n,
                    "t_min": rel_min,
                    "think_text": think_text,
                    "think_first_line": (
                        think_text.split("\n", 1)[0].strip()[:200]
                        if think_text else ""
                    ),
                    "actions": [],
                }
            elif t == "tool_use" and cur is not None:
                inp = c.get("input") or {}
                tid = c.get("id", "")
                if c.get("name") == "Bash":
                    cmd = inp.get("command", "")
                    cur["actions"].append({
                        "kind": "bash",
                        "cmd": cmd,
                        "result": tool_results.get(tid, ""),
                    })
                else:
                    cur["actions"].append({
                        "kind": c.get("name", "tool"),
                        "cmd": str(inp)[:200],
                        "result": tool_results.get(tid, ""),
                    })
            # `text` blocks are visible-to-user prose; we ignore them
            # for timeline purposes (think_first_line covers the gist).
    if cur is not None:
        groups.append(cur)

    # Third pass: build Step objects
    steps: list[Step] = []
    for g in groups:
        actions = g["actions"]
        principal: Optional[dict] = None
        if actions:
            tactic_actions = [
                a for a in actions
                if a["kind"] == "bash" and _is_tactic_cmd(a["cmd"])
            ]
            if tactic_actions:
                tactic_actions.sort(key=lambda a: _principal_kind(a["cmd"]))
                principal = tactic_actions[0]
            else:
                principal = actions[0]

        if principal:
            if principal["kind"] == "bash":
                action_text = _extract_tactic(principal["cmd"])
            else:
                action_text = f"[{principal['kind']}] " + principal["cmd"][:80]
            signal = _detect_signal(principal.get("result", ""))
        else:
            action_text = "(no action)"
            signal = ""

        steps.append(Step(
            step_n=g["step_n"],
            t_min=g["t_min"],
            think_text=g["think_text"],
            think_first_line=g["think_first_line"],
            principal_action=action_text,
            principal_signal=signal,
            aux_action_count=max(0, len(actions) - (1 if principal else 0)),
        ))

    return steps
