"""Speculative-check results and the session transcript compressor.

Agent-visible presentation belongs to ``workflow.proof_state_compiler``.
``TryResult`` is what one ``-try`` reports; its ``report`` text is the private
rendering printed by the backend command and kept in the audit event. Nothing
reads the text back: callers use the typed fields.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from core.easycrypt.ec_prompt import is_prompt_line
from core.easycrypt.session.session_common import trim_after_last_prompt
from core.easycrypt.session.session_no_progress import detect_no_progress


@dataclass(frozen=True)
class TryResult:
    """EasyCrypt's verdict on one speculative check, which commits nothing.

    ``accepted`` is ``None`` when no check ran; ``tool_error`` then says
    whether the check failed (a disabled daemon is reported without one).
    ``goal_after_remaining`` is the subgoal count after an accepted check,
    ``0`` once all goals are closed and ``None`` when unknown.
    """

    tactic: str
    report: str
    accepted: bool | None = None
    goal_after_closed: bool = False
    goal_after_remaining: int | None = None
    error_kind: str = ""
    tool_error: bool = False
    no_progress_predicted: bool = False


def try_tool_error(request: str, report: str) -> TryResult:
    """A check that could not run; ``report`` starts with ``[TRY] error:``."""

    return TryResult(tactic=request.strip(), report=report, tool_error=True)


def _remaining(goal: dict[str, Any]) -> tuple[str, int | None]:
    value = goal.get("remaining", "?")
    count = value if type(value) is int and value >= 0 else None
    return f"{value} subgoal(s) remaining", count


def _error_kind(error: dict[str, Any]) -> str:
    return str(error.get("kind", "unknown"))


def single_try_result(
    tactic: str,
    reply: dict[str, Any],
    prev_raw: str = "",
) -> TryResult:
    """The result of the daemon's ``try_tactic`` reply for one tactic.

    An accepted tactic is also checked for progress against ``prev_raw``,
    the current state, exactly as a commit would be.
    """

    accepted = bool(reply.get("accepted"))
    lines = [
        f"[TRY] tactic: {tactic}",
        f"[TRY] accepted: {accepted}",
    ]
    closed = False
    remaining = None
    no_progress = False
    error_kind = ""
    goal = reply.get("goal_after")
    if accepted and isinstance(goal, dict):
        if goal.get("is_closed"):
            lines.append("[TRY] goal_after: all goals closed.")
            closed, remaining = True, 0
        else:
            text, remaining = _remaining(goal)
            lines.append(f"[TRY] goal_after: {text}")
        raw = str(goal.get("raw") or "")
        if prev_raw and raw:
            no_progress, _ = detect_no_progress(
                prev_raw, raw, has_new_error=False
            )
            if no_progress:
                lines.append("[TRY] PRODUCES NO PROGRESS")
    if not accepted:
        error = reply.get("error")
        if isinstance(error, dict):
            error_kind = _error_kind(error)
            lines.append(f"[TRY] error_kind: {error_kind}")
    lines.append("[TRY] state_unchanged: true")
    return TryResult(
        tactic=tactic,
        report="\n".join(lines) + "\n",
        accepted=accepted,
        goal_after_closed=closed,
        goal_after_remaining=remaining,
        error_kind=error_kind.strip(),
        no_progress_predicted=no_progress,
    )


def chain_try_result(
    request: str,
    tactics: list[str],
    chain: dict[str, Any],
) -> TryResult:
    """The result of the daemon's ``try_chain`` reply for ``tactics``.

    The result names the whole ``request``; its goal count is the one after
    the last accepted step.
    """

    accepted = bool(chain.get("accepted"))
    final_closed = bool(chain.get("final_closed"))
    lines = [
        f"[TRY-CHAIN] tactics: {len(tactics)} step(s)",
        f"[TRY-CHAIN] all_accepted: {accepted}",
        f"[TRY-CHAIN] final_closed: {final_closed}",
    ]
    remaining = 0 if final_closed else None
    error_kind = ""
    if accepted:
        if final_closed:
            lines.append("[TRY-CHAIN] goal_after: all goals closed.")
        else:
            for step in reversed(list(chain.get("steps") or [])):
                if not isinstance(step, dict) or not step.get("accepted"):
                    continue
                goal = step.get("goal_after")
                if isinstance(goal, dict):
                    text, remaining = _remaining(goal)
                    lines.append(f"[TRY-CHAIN] goal_after: {text}")
                break
    elif chain.get("failed_at") is not None:
        error = chain.get("error")
        if isinstance(error, dict):
            error_kind = _error_kind(error)
            lines.append(f"[TRY] error_kind: {error_kind}")
    lines.append("[TRY-CHAIN] state_unchanged: true")
    return TryResult(
        tactic=request.strip(),
        report="\n".join(lines) + "\n",
        accepted=accepted,
        goal_after_closed=final_closed,
        goal_after_remaining=remaining,
        error_kind=error_kind.strip(),
    )


def compress_current_state(text: str) -> str:
    """Keep only the latest EasyCrypt goal state from a replay transcript."""

    if not text:
        return text
    lines = text.splitlines(keepends=True)
    state_marker = re.compile(
        r"^(?:Current goal(?:\s*\(remaining:\s*\d+\))?|No more goals)\s*$"
    )
    marker_index = -1
    prompt_indices: list[int] = []
    for index, line in enumerate(lines):
        stripped = line.strip()
        if state_marker.match(stripped):
            marker_index = index
        if is_prompt_line(stripped):
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
