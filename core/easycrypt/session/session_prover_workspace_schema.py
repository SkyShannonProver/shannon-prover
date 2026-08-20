"""Strict schema contract for the current ProverWorkspaceView.

The runtime has one supported workspace-view generation: v3.  Historical
panel layouts are deliberately rejected here rather than inferred or migrated
inside the live manager, timeline, or artifact readers.
"""
from __future__ import annotations

import json
from typing import Any

from core.easycrypt.proof_lifecycle import GOAL_IDENTITY_FREE_STATUSES

from core.easycrypt.validation_result import ValidationResult


PROVER_WORKSPACE_VIEW_SCHEMA_VERSION = 3
PROVER_WORKSPACE_VIEW_KIND = "prover_workspace_view"

PROVER_WORKSPACE_VIEW_REQUIRED_FIELDS = (
    "last_result",
    "proof_status",
    "current_goal",
)

UNSUPPORTED_PROVER_WORKSPACE_KEYS = frozenset({
    "decision_context",
    "facts_and_gaps",
    "next_actions",
    "proof_frontier",
    "proof_position",
    "recent_diagnostics",
    "rewind_route_memory",
    "suggested_next_steps",
    "want_more_context",
    # Retired rich-view/panel carrier fields.  Current compiler output crosses
    # the manager boundary separately as a bounded ActionSurface.
    "program_frontier",
    "application_context",
    "facts_and_diagnostics",
    "candidate_moves",
    "inspect_lookup_handles",
    "call_site_surface",
    "seq_cut_surface",
    "pure_tail_surface",
    "frame_obligation_ledger",
    "recovery_diagnosis_surface",
    "structural_checkpoints",
    "route_replay_memory",
    "proof_ir",
})


class ProverWorkspaceViewValidation(ValidationResult):
    """Validation result for the one supported workspace-view schema."""


def validate_prover_workspace_view(
    data: dict[str, Any],
) -> ProverWorkspaceViewValidation:
    """Validate a complete current ProverWorkspaceView without adapting it."""

    errors: list[str] = []
    schema_version = data.get("schema_version")
    if (
        type(schema_version) is not int
        or schema_version != PROVER_WORKSPACE_VIEW_SCHEMA_VERSION
    ):
        errors.append(
            "unsupported ProverWorkspaceView schema_version "
            f"{schema_version!r}; expected {PROVER_WORKSPACE_VIEW_SCHEMA_VERSION}"
        )
    kind = data.get("kind")
    if kind != PROVER_WORKSPACE_VIEW_KIND:
        errors.append(
            f"unsupported ProverWorkspaceView kind {kind!r}; "
            f"expected {PROVER_WORKSPACE_VIEW_KIND!r}"
        )
    if not isinstance(data.get("ok"), bool):
        errors.append("ProverWorkspaceView field `ok` must be a bool")
    for field in PROVER_WORKSPACE_VIEW_REQUIRED_FIELDS:
        if not isinstance(data.get(field), dict):
            errors.append(
                f"ProverWorkspaceView required field `{field}` must be an object"
            )
    current_goal = data.get("current_goal")
    proof_status = data.get("proof_status")
    proof_status = proof_status if isinstance(proof_status, dict) else {}
    status = str(proof_status.get("status") or "")
    goal_identity_required = proof_status.get("goal_identity_required")
    if type(goal_identity_required) is not bool:
        errors.append(
            "ProverWorkspaceView proof_status.goal_identity_required must be a bool"
        )
    goal_is_open = bool(data.get("ok")) and status not in (
        GOAL_IDENTITY_FREE_STATUSES
    )
    if isinstance(current_goal, dict) and goal_is_open:
        lines = current_goal.get("lines")
        if not isinstance(lines, list):
            errors.append(
                "open ProverWorkspaceView current_goal.lines must be a list"
            )
        elif any(type(line) is not str for line in lines):
            errors.append(
                "open ProverWorkspaceView current_goal.lines entries must be strings"
            )
    if bool(data.get("ok")) and type(goal_identity_required) is bool:
        if goal_is_open != goal_identity_required:
            errors.append(
                "ProverWorkspaceView status and goal identity class disagree"
            )
        goal_hash = proof_status.get("goal_hash")
        if goal_identity_required and (
            type(goal_hash) is not str or not goal_hash
        ):
            errors.append("open ProverWorkspaceView requires proof_status.goal_hash")
        if not goal_identity_required and goal_hash:
            errors.append("closed ProverWorkspaceView cannot carry proof_status.goal_hash")
    forbidden = sorted(_all_keys(data) & UNSUPPORTED_PROVER_WORKSPACE_KEYS)
    if forbidden:
        errors.append(
            "ProverWorkspaceView contains unsupported key(s): "
            + ", ".join(forbidden)
        )
    return ProverWorkspaceViewValidation(errors=errors)


def require_prover_workspace_view(
    data: dict[str, Any],
    *,
    label: str = "ProverWorkspaceView",
) -> None:
    """Raise a clear error unless ``data`` is a complete current v3 view."""

    validation = validate_prover_workspace_view(data)
    if validation.errors:
        raise ValueError(f"{label}: {'; '.join(validation.errors)}")


def prover_workspace_event_payload_fields(
    data: dict[str, Any],
    *,
    artifact: str,
    view_hash: str,
) -> dict[str, Any]:
    """Return the one current produced-event projection for a workspace view."""

    current_goal = data.get("current_goal")
    current_goal = current_goal if isinstance(current_goal, dict) else {}
    proof_status = data.get("proof_status")
    proof_status = proof_status if isinstance(proof_status, dict) else {}
    return {
        "schema_version": int(data.get("schema_version") or 0),
        "view_kind": str(data.get("kind") or ""),
        "ok": bool(data.get("ok")),
        "artifact": artifact,
        "view_hash": view_hash,
        "proof_status": str(proof_status.get("status") or ""),
        "current_goal_text_fully_shown": bool(
            current_goal.get("text_fully_shown")
        ),
        "current_goal_truncated": bool(current_goal.get("truncated")),
        "goal_chars": int(current_goal.get("char_count") or 0),
        "workspace_chars": len(json.dumps(data, sort_keys=True)),
    }


def validate_prover_workspace_event_binding(
    data: dict[str, Any],
    payload: dict[str, Any],
    *,
    artifact_hash: str,
) -> ProverWorkspaceViewValidation:
    """Validate every writer-owned event mirror against its workspace artifact."""

    validation = validate_prover_workspace_view(data)
    errors = list(validation.errors)
    expected = prover_workspace_event_payload_fields(
        data,
        artifact=str(payload.get("artifact") or ""),
        view_hash=artifact_hash,
    )
    for key, expected_value in expected.items():
        if payload.get(key) != expected_value:
            errors.append(
                f"event payload `{key}` mismatch: "
                f"expected {expected_value!r}, got {payload.get(key)!r}"
            )
    return ProverWorkspaceViewValidation(
        errors=errors,
        warnings=list(validation.warnings),
    )


def _all_keys(value: Any) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        for key, nested in value.items():
            keys.add(str(key))
            keys.update(_all_keys(nested))
    elif isinstance(value, list):
        for item in value:
            keys.update(_all_keys(item))
    return keys
