"""Current proof-node goal-envelope projection pipeline."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from workflow.proof_state_compiler.surface_profiles import (
    ensure_current_surface_profile,
    project_current_workspace_view,
)


@dataclass(frozen=True)
class ProofProjectionResult:
    view: dict[str, Any]            # surface-profiled (lean) view — drives the agent markdown
    state: Any
    evidence: Any
    full_view: dict[str, Any]       # complete view — for the audit JSON


class ProofProjectionPipeline:
    """Project one authoritative snapshot into the current lean envelope."""

    def __init__(
        self,
        *,
        workspace: Any,
        surface_profile: str,
    ) -> None:
        self.workspace = workspace
        self.surface_profile = ensure_current_surface_profile(
            surface_profile
        ).name

    def project(
        self,
        snapshot: Any,
        *,
        latest_observation: dict[str, Any] | None = None,
        replay_prefix: list[str] | None = None,
        replay_prefix_count: int = 0,
        file_path: str | None = None,
        project_root: str | None = None,
    ) -> ProofProjectionResult:
        raw_view = snapshot.raw_workspace_view
        base_view = self.workspace.project(
            raw_view,
            state_version=snapshot.state_version,
            session_epoch=snapshot.session_epoch,
            latest_observation=latest_observation,
        )
        view = project_current_workspace_view(base_view, self.surface_profile)
        view.pop("view_hash", None)
        view["view_hash"] = self.workspace.view_hash(view)
        view = self.workspace.order_workspace_view(view)
        return ProofProjectionResult(
            view=view,
            state=None,
            evidence=None,
            full_view=dict(view),
        )
