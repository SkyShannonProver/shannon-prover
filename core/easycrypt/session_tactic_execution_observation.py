"""Pure readers for the current TacticExecutionResult envelope.

These helpers keep timelines and validation tools from growing independent
interpretations of the same execution/result/workspace fields. They do not
adapt historical result shapes; callers validate the contract at ingress.
"""
from __future__ import annotations

from typing import Any

from core.easycrypt.value_shapes import as_dict, as_list


NO_PROGRESS_STATUSES = frozenset({
    "no_progress",
    "no_progress_reverted",
    "preflight_no_progress",
})
FAILED_STATUSES = frozenset({"error", "rejected", "failed"})


def tactic_execution_workspace(data: dict[str, Any]) -> dict[str, Any]:
    """Return the embedded current ProverWorkspaceView, or an empty object."""

    return as_dict(as_dict(data.get("workspace")).get("view"))


def tactic_execution_failed(data: dict[str, Any]) -> bool:
    """Return whether the current execution envelope records a failed action."""

    # A committed no-op is represented by the runtime with ``ok=False`` and a
    # ``failed_tactic`` so that the state rollback is explicit.  It is still a
    # distinct outcome, not an execution error: the current workspace should
    # keep offering fresh proof guidance rather than being forced to diagnose.
    if tactic_execution_no_progress(data):
        return False
    execution = as_dict(data.get("execution"))
    result = as_dict(data.get("result"))
    return bool(
        data.get("ok") is False
        or result.get("ok") is False
        or str(result.get("status") or "") in FAILED_STATUSES
        or execution.get("failed_tactic")
    )


def tactic_execution_no_progress(data: dict[str, Any]) -> bool:
    """Return whether the result or one execution step records no progress."""

    result = as_dict(data.get("result"))
    if str(result.get("status") or "") in NO_PROGRESS_STATUSES:
        return True
    execution = as_dict(data.get("execution"))
    return any(
        str(as_dict(step).get("status") or "") == "no_progress"
        for step in as_list(execution.get("steps"))
    )
