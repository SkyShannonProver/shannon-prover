"""Minimal backend text formatting for the current managed runtime.

Agent-visible presentation belongs to ``workflow.proof_state_compiler``.
This module only keeps the small, stable textual contract used internally by
the EasyCrypt daemon preflight adapter and the session transcript compressor.
"""
from __future__ import annotations

import re
from typing import Any

from core.easycrypt.session_common import trim_after_last_prompt
from core.easycrypt.session_no_progress import detect_no_progress


def reorder_display(chunks: list[str]) -> list[str]:
    """Preserve backend response order without legacy panel layering."""

    return list(chunks)


def format_try_single(
    tactic: str,
    result: dict[str, Any],
    file_path: str | None = None,
    prev_raw: str = "",
) -> str:
    """Render the private preflight fields consumed by the typed adapter."""

    del file_path
    accepted = bool(result.get("accepted"))
    lines = [
        f"[TRY] tactic: {tactic}",
        f"[TRY] accepted: {accepted}",
    ]
    goal = result.get("goal_after")
    if accepted and isinstance(goal, dict):
        if goal.get("is_closed"):
            lines.append("[TRY] goal_after: all goals closed.")
        else:
            lines.append(
                f"[TRY] goal_after: {goal.get('remaining', '?')} subgoal(s) remaining"
            )
        raw = str(goal.get("raw") or "")
        if prev_raw and raw:
            no_progress, _ = detect_no_progress(
                prev_raw, raw, has_new_error=False
            )
            if no_progress:
                lines.append("[TRY] PRODUCES NO PROGRESS")
    if not accepted:
        error = result.get("error")
        if isinstance(error, dict):
            lines.append(f"[TRY] error_kind: {error.get('kind', 'unknown')}")
    lines.append("[TRY] state_unchanged: true")
    return "\n".join(lines) + "\n"


def format_try_chain(
    tactics: list[str],
    chain: dict[str, Any],
    file_path: str | None = None,
    prev_raw: str = "",
) -> str:
    """Render a compact chain-preflight result for the typed parser."""

    del file_path, prev_raw
    accepted = bool(chain.get("accepted"))
    final_closed = bool(chain.get("final_closed"))
    lines = [
        f"[TRY-CHAIN] tactics: {len(tactics)} step(s)",
        f"[TRY-CHAIN] all_accepted: {accepted}",
        f"[TRY-CHAIN] final_closed: {final_closed}",
    ]
    if accepted:
        if final_closed:
            lines.append("[TRY-CHAIN] goal_after: all goals closed.")
        else:
            for step in reversed(list(chain.get("steps") or [])):
                if not isinstance(step, dict) or not step.get("accepted"):
                    continue
                goal = step.get("goal_after")
                if isinstance(goal, dict):
                    lines.append(
                        "[TRY-CHAIN] goal_after: "
                        f"{goal.get('remaining', '?')} subgoal(s) remaining"
                    )
                break
    elif chain.get("failed_at") is not None:
        error = chain.get("error")
        if isinstance(error, dict):
            lines.append(f"[TRY] error_kind: {error.get('kind', 'unknown')}")
    lines.append("[TRY-CHAIN] state_unchanged: true")
    return "\n".join(lines) + "\n"


def compress_current_state(text: str) -> str:
    """Keep only the latest EasyCrypt goal state from a replay transcript."""

    if not text:
        return text
    lines = text.splitlines(keepends=True)
    state_marker = re.compile(
        r"^(?:Current goal(?:\s*\(remaining:\s*\d+\))?|No more goals)\s*$"
    )
    prompt = re.compile(r"^\[[0-9]+\|[^\]]+\]>\s*$")
    marker_index = -1
    prompt_indices: list[int] = []
    for index, line in enumerate(lines):
        stripped = line.strip()
        if state_marker.match(stripped):
            marker_index = index
        if prompt.match(stripped):
            prompt_indices.append(index)
    if marker_index >= 0:
        start = marker_index
        for index in reversed(prompt_indices):
            if index < marker_index:
                start = index
                break
        return "".join(lines[start:])
    if prompt_indices:
        start = prompt_indices[-2] if len(prompt_indices) >= 2 else prompt_indices[-1]
        return trim_after_last_prompt("".join(lines[start:]))
    return text
