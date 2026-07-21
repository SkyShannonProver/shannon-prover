"""Proof-node state/evidence/view projection pipeline."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from workflow.surface_profiles import apply_workspace_view_surface_profile


@dataclass(frozen=True)
class ProofProjectionResult:
    view: dict[str, Any]            # surface-profiled (lean) view — drives the agent markdown
    state: Any
    evidence: Any
    full_view: dict[str, Any] = field(default_factory=dict)  # complete view — for the audit JSON


class ProofProjectionPipeline:
    """Coordinates projection without owning proof state or proof strategy."""

    def __init__(
        self,
        *,
        workspace: Any,
        node_state: Any,
        checkpoints: Any,
        proof_memory: Any,
        events: Any,
        analyzers: Any,
        renderer: Any,
        file_path: str,
        project_root: str,
        surface_profile: str,
    ) -> None:
        self.workspace = workspace
        self.node_state = node_state
        self.checkpoints = checkpoints
        self.proof_memory = proof_memory
        self.events = events
        self.analyzers = analyzers
        self.renderer = renderer
        self.file_path = str(file_path or "")
        self.project_root = str(project_root or "")
        self.surface_profile = str(surface_profile or "")

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
        state = self.node_state.build(
            snapshot=snapshot,
            raw_workspace_view=raw_view,
            base_workspace_view=base_view,
            file_path=self.file_path if file_path is None else str(file_path or ""),
            project_root=(
                self.project_root
                if project_root is None else str(project_root or "")
            ),
            latest_observation=latest_observation,
            replay_prefix=list(replay_prefix or []),
            replay_prefix_count=replay_prefix_count,
            restore_anchor=self.checkpoints.pre_rewind_restore_anchor,
            route_memories=[
                memory.to_dict()
                for memory in self.proof_memory.route_memories
            ],
            route_event_facts=self.events.route_event_facts,
            typed_events=self.events.recent_events(),
        )
        route_evidence = self.analyzers.analyze_route(
            state=state,
            workspace_view=base_view,
        )
        route_health = route_evidence.route_health
        structural_transitions = route_evidence.structural_transitions
        checkpoint_index = self.checkpoints.build_index(
            structural_items=self.checkpoints.structural_surface(
                state.committed_tactics,
                route_health=route_health,
                replay_prefix_count=state.replay_prefix_count,
            ),
            restore_option=self.checkpoints.pre_rewind_restore_option(),
        )
        route_replay_surface = self.proof_memory.route_replay_memory_surface(
            state.committed_tactics,
        )
        lineage_briefing = self.proof_memory.lineage_briefing_surface(
            state.committed_tactics,
        )
        evidence = self.analyzers.run(
            state=state,
            checkpoint_index=checkpoint_index,
            workspace_view=base_view,
            route_health=route_health,
            structural_transitions=structural_transitions,
            route_replay_memory=route_replay_surface,
            lineage_briefing=lineage_briefing,
            repair_episodes=[
                episode.to_dict()
                for episode in self.proof_memory.repair_episodes
            ],
        )
        rendered = self.renderer.render(base_view, state=state, evidence=evidence)
        # full_view = the COMPLETE view (all panels) — for the audit JSON. The agent's
        # lean view is the surface-profiled one below. Single content authority: the
        # profile decides what the AGENT sees; the audit JSON keeps everything.
        full_view = dict(rendered)
        full_view.pop("view_hash", None)
        full_view["view_hash"] = self.workspace.view_hash(full_view)
        full_view = self.workspace.order_agent_view(full_view)
        view = apply_workspace_view_surface_profile(rendered, self.surface_profile)
        view.pop("view_hash", None)
        view["view_hash"] = self.workspace.view_hash(view)
        view = self.workspace.order_agent_view(view)
        return ProofProjectionResult(
            view=view, state=state, evidence=evidence, full_view=full_view)
