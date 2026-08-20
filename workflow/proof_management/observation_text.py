"""Agent-facing observation prose for manager backend actions.

This module owns the pure text-rendering layer extracted from
``backend_actions.py``: the result/effect/proof-state sentences stitched into
agent observations, plus the error-summary extraction that turns raw backend
excerpts into one bounded human-readable line.  Nothing here touches the
event-binding/contract layer — these functions consume already-resolved
values and return strings byte-identical to the pre-extraction output.
"""
from __future__ import annotations

from typing import Any

from core.easycrypt.value_shapes import first_text as _first_text

from workflow.proof_management.common import (
    _dict,
    _list,
    _preview,
)
from workflow.proof_management.turn_view import intent_effect as _intent_effect


def _read_only_result_text(label: str, status: str) -> str:
    ok = str(status or "").strip() in {"", "ok", "available"}
    if label == "exact_tactic_preflight":
        return (
            "EasyCrypt checked the exact tactic without committing it."
            if ok
            else "EasyCrypt rejected the exact tactic without changing proof state."
        )
    if label == "managed_goal_view":
        return "The manager produced the authoritative current goal envelope."
    if label == "episode_view":
        return "The manager produced the authoritative session timeline."
    return "The manager completed the read-only backend operation."


def _manager_result_text(label: str, status: str, ok: bool) -> str:
    normalized = str(status or "").strip()
    if label == "commit_tactic":
        if normalized == "partial_success":
            return (
                "EasyCrypt committed the successful tactic prefix and rejected "
                "the remaining tactic."
            )
        if normalized == "no_progress_reverted":
            return (
                "EasyCrypt accepted the tactic but the manager reverted it "
                "as a no-op because it did not change the goal."
            )
        return (
            "EasyCrypt accepted the committed tactic."
            if ok
            else "EasyCrypt rejected the committed tactic."
        )
    if label == "fresh_restart":
        return (
            "EasyCrypt restarted this node from the target lemma."
            if ok
            else "The manager could not restart this node."
        )
    if label in {"undo_last_step", "undo_to_checkpoint"}:
        return (
            "The manager completed the requested rewind."
            if ok
            else "The manager could not complete the requested rewind."
        )
    if ok:
        return f"The manager completed {label}."
    return f"The manager could not complete {label} ({normalized or 'failed'})."


def _action_effect(label: str, execution: dict[str, Any]) -> str:
    if label == "exact_tactic_preflight":
        return (
            "This asks the manager for information only; it does not change "
            "the EasyCrypt proof state."
        )
    if bool(execution.get("state_changed") or execution.get("history_committed")):
        return (
            "EasyCrypt accepted a proof-state change; the refreshed view is "
            "based on the new committed state."
        )
    if label == "fresh_restart":
        return (
            "This explicitly restarts the current node's EasyCrypt session "
            "from the target lemma and discards this node's committed branch."
        )
    if label == "undo_to_checkpoint":
        return (
            "This rewinds the current node's committed branch to the selected "
            "checkpoint and returns the refreshed view."
        )
    if label == "commit_tactic":
        return (
            "The manager attempted to commit a tactic; use the result and "
            "latest goal to decide what changed."
        )
    return _intent_effect(label)


def _proof_state_observation(
    label: str,
    execution: dict[str, Any],
    status: str,
) -> str:
    normalized = str(status or "").strip()
    if normalized in {"no_progress", "no_progress_reverted"}:
        return "The committed EasyCrypt proof state was not changed."
    if bool(execution.get("state_changed") or execution.get("history_committed")):
        return "The committed EasyCrypt proof state changed."
    if normalized in {"failed", "error", "rejected"}:
        return "The committed EasyCrypt proof state was not changed."
    if label == "exact_tactic_preflight":
        return "The committed EasyCrypt proof state was not changed."
    if label == "fresh_restart":
        return "The EasyCrypt proof state was reset to the target lemma start."
    if label == "undo_to_checkpoint":
        return "The EasyCrypt proof state was rewound to the selected checkpoint."
    return ""


def _extract_daemon_rejected(raw_excerpt: str) -> str:
    """The EC daemon prints `[DAEMON_REJECTED] <reason>` (e.g. `[DAEMON_REJECTED]
    unknown procedure: PseudoRP.fi`) when it rejects a tactic. That reason carries no
    `error_excerpt:`/`errors` structure, so the other extractors miss it — recover it
    so a daemon rejection is not surfaced as an empty error summary."""
    for line in (raw_excerpt or "").splitlines():
        s = line.strip()
        if s.startswith("[DAEMON_REJECTED]"):
            reason = s[len("[DAEMON_REJECTED]"):].strip()
            if reason:
                return _preview(reason, limit=280)
    return ""


def _error_summary(payload: dict[str, Any], stderr: str, *, ok: bool = False) -> str:
    result = _dict(payload.get("result"))
    # Structured EC error fields FIRST: a daemon/tactic rejection carries the clean
    # reason directly in result.error / result.failure_reason (e.g. "[error] unknown
    # procedure: PseudoRP.fi"). These were never read, so a `[DAEMON_REJECTED]`
    # commit landed error_summary=None and the agent was told to "use the error
    # summary" with none present (root-caused by EC replay, MEE-CBC L1/L4 2026-06-06).
    structured = _first_text(result.get("error"), result.get("failure_reason"), default="")
    if structured.strip():
        return _preview(structured.strip(), limit=280)
    raw_excerpt = _first_text(result.get("raw_excerpt"), default="")
    extracted = _extract_error_excerpt(raw_excerpt)
    if extracted:
        return extracted
    extracted = _extract_try_error_summary(raw_excerpt)
    if extracted:
        return extracted
    extracted = _extract_daemon_rejected(raw_excerpt)
    if extracted:
        return extracted
    error_items = [
        *_list(payload.get("errors")),
    ]
    for item in error_items:
        if isinstance(item, dict):
            text = _first_text(
                item.get("message"),
                item.get("diagnostic"),
                item.get("error"),
                default="",
            )
            if text:
                return _preview(text, limit=280)
        elif str(item).strip():
            return _preview(str(item), limit=280)
    # Raw-stderr fallback — ONLY when the action FAILED. Structured proof errors
    # (raw_excerpt / errors above) are read regardless of status. But session_cli also writes purely
    # INFORMATIONAL notices to stderr on SUCCESS (exit 0) — notably the
    # "[session_cli] Restart #N: discarding K committed tactic(s) … Proceeding
    # with fresh session" line emitted when a checkpoint rewind restarts+replays.
    # Promoting that to error_summary surfaced a SUCCESSFUL undo_to_checkpoint to
    # the agent as a manager_error claiming its committed work was discarded — a
    # misleading signal. Only fall back to stderr when the command did not succeed.
    if not ok and stderr.strip():
        return _preview(stderr.strip(), limit=280)
    return ""


def _extract_try_error_summary(raw_excerpt: str) -> str:
    if not raw_excerpt:
        return ""
    lines = [line.strip() for line in raw_excerpt.splitlines() if line.strip()]
    selected: list[str] = []
    for line in lines:
        if line.startswith("[TRY] error:"):
            selected.append(line.removeprefix("[TRY] error:").strip())
            continue
        if line.startswith("[TRY] sync_detail:"):
            selected.append(
                "sync_detail: "
                + line.removeprefix("[TRY] sync_detail:").strip()
            )
    if not selected:
        return ""
    return _preview(" ".join(selected), limit=280)


def _extract_error_excerpt(raw_excerpt: str) -> str:
    if not raw_excerpt:
        return ""
    lines = [line.strip() for line in raw_excerpt.splitlines()]
    for idx, line in enumerate(lines):
        if "error_excerpt:" not in line:
            continue
        tail: list[str] = []
        for item in lines[idx + 1:]:
            if not item:
                continue
            if item.startswith("[") and tail:
                break
            if item.startswith("["):
                continue
            tail.append(item)
        if tail:
            return _preview(" ".join(tail), limit=280)
    return ""
