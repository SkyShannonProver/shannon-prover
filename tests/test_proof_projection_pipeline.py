from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

from workflow.proof_management.projection import ProofProjectionPipeline


@dataclass(frozen=True)
class _Snapshot:
    raw_workspace_view: dict[str, Any]
    state_version: int = 7
    session_epoch: int = 2
    goal_hash: str = "goal"


class _Workspace:
    def project(self, raw, *, state_version, session_epoch, latest_observation):
        return {
            **dict(raw),
            "state_version": state_version,
            "session_epoch": session_epoch,
            "last_result": dict(latest_observation or {}),
        }

    def view_hash(self, view):
        return "hash-" + str(view.get("state_version"))

    def order_agent_view(self, view):
        return {**dict(view), "ordered": True}


class _NodeState:
    def build(self, **kwargs):
        payload = dict(kwargs)
        payload["committed_tactics"] = ["proc."]
        payload["replay_prefix_count"] = kwargs["replay_prefix_count"]
        return SimpleNamespace(
            **payload,
        )


class _Checkpoints:
    pre_rewind_restore_anchor = {"restore_id": "restore_1"}

    def structural_surface(self, tactics, *, route_health, replay_prefix_count):
        return [{"semantic_id": "before_seq_cut"}]

    def pre_rewind_restore_option(self):
        return {"restore_id": "restore_1"}

    def build_index(self, *, structural_items, restore_option):
        return SimpleNamespace(
            structural_items=structural_items,
            restore_option=restore_option,
        )


class _ProofMemory:
    repair_episodes: list[Any] = []

    route_memories: list[Any] = []

    def route_replay_memory_surface(self, tactics):
        return {}

    def lineage_briefing_surface(self, tactics):
        return {}


class _Events:
    route_event_facts: list[dict[str, Any]] = []

    def recent_events(self):
        return [{"kind": "typed"}]


class _Analyzers:
    def analyze_route(self, *, state, workspace_view):
        return SimpleNamespace(
            route_health=[{"signal": "ok"}],
            structural_transitions=[{"id": "wp"}],
        )

    def run(self, **kwargs):
        return SimpleNamespace(**kwargs)


class _Renderer:
    def render(self, view, *, state, evidence):
        return {
            **dict(view),
            "rendered_file_path": state.file_path,
            "route_health": evidence.route_health,
        }


def test_projection_pipeline_uses_dynamic_project_context() -> None:
    pipeline = ProofProjectionPipeline(
        workspace=_Workspace(),
        node_state=_NodeState(),
        checkpoints=_Checkpoints(),
        proof_memory=_ProofMemory(),
        events=_Events(),
        analyzers=_Analyzers(),
        renderer=_Renderer(),
        file_path="initial.ec",
        project_root="/initial",
        surface_profile="",
    )

    result = pipeline.project(
        _Snapshot({"kind": "prover_workspace_view"}),
        latest_observation={"result": "ok"},
        replay_prefix=["byequiv=>//."],
        replay_prefix_count=1,
        file_path="dynamic.ec",
        project_root="/dynamic",
    )

    assert result.state.file_path == "dynamic.ec"
    assert result.state.project_root == "/dynamic"
    assert result.view["rendered_file_path"] == "dynamic.ec"
    assert result.view["view_hash"] == "hash-7"
    assert result.view["ordered"] is True
