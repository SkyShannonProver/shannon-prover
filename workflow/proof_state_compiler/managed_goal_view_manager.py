"""Projection policy for the minimal L1/compiler-V2 manager envelope."""
from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

from core.easycrypt.session_prover_workspace_schema import (
    require_prover_workspace_view,
)


_ORDER = (
    "last_result",
    "proof_status",
    "current_goal",
    "latest_observation",
    "schema_version",
    "kind",
    "based_on_state_version",
    "session_epoch",
    "view_hash",
)
_FORBIDDEN_FIELDS = frozenset({
    "debug_cli_fallback",
    "command",
    "code",
    "suggestions",
    "readiness",
    "predicted_proof_state",
})
_BACKEND_MARKERS = (
    "session_cli.py",
    "core/easycrypt/session_cli",
    " -managed-goal-view",
)


class ManagedGoalViewManager:
    """Hash, sanitize, and order only the neutral goal carrier."""

    def project(
        self,
        workspace_view: dict[str, Any],
        *,
        state_version: int | None = None,
        session_epoch: int | None = None,
        latest_observation: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        require_prover_workspace_view(
            workspace_view,
            label="managed goal workspace input",
        )
        clean = _scrub(copy.deepcopy(workspace_view))
        if latest_observation:
            clean["last_result"] = _scrub(copy.deepcopy(latest_observation))
        if state_version is not None:
            clean["based_on_state_version"] = int(state_version)
        if session_epoch is not None:
            clean["session_epoch"] = int(session_epoch)
        clean["view_hash"] = self.view_hash(clean)
        return self.order_workspace_view(clean)

    def order_workspace_view(self, view: dict[str, Any]) -> dict[str, Any]:
        data = dict(view)
        return {
            **{key: data[key] for key in _ORDER if key in data},
            **{key: value for key, value in data.items() if key not in _ORDER},
        }

    def view_hash(self, view: dict[str, Any]) -> str:
        payload = json.dumps(view, sort_keys=True, separators=(",", ":"))
        return hashlib.sha1(payload.encode("utf-8")).hexdigest()

    def lint_workspace_view(self, view: dict[str, Any]) -> list[str]:
        issues: list[str] = []
        text = json.dumps(view, sort_keys=True)
        for marker in _BACKEND_MARKERS:
            if marker in text:
                issues.append(f"backend marker leaked into workspace view: {marker}")
        for field in _FORBIDDEN_FIELDS:
            if _field_exists(view, field):
                issues.append(f"forbidden agent-facing field present: {field}")
        return issues


def _scrub(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _scrub(item)
            for key, item in value.items()
            if key not in _FORBIDDEN_FIELDS
            and not (key == "tool" and str(item).startswith("-"))
        }
    if isinstance(value, list):
        return [_scrub(item) for item in value]
    if isinstance(value, str):
        out = value
        for marker in _BACKEND_MARKERS:
            out = out.replace(marker, "manager")
        return out
    return value


def _field_exists(value: Any, field: str) -> bool:
    if isinstance(value, dict):
        return field in value or any(
            _field_exists(item, field) for item in value.values()
        )
    if isinstance(value, list):
        return any(_field_exists(item, field) for item in value)
    return False
