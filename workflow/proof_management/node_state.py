"""Proof-node aggregate state.

The state manager gathers the manager-readable proof state into one immutable
object before checkpoint analysis, evidence analysis, and view rendering.  It
does not execute tactics and does not decide proof strategy.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any
from core.easycrypt.value_shapes import drop_empty as _drop_empty


CommittedTacticReader = Callable[[], list[str]]


@dataclass(frozen=True)
class ProofNodeState:
    node_id: str
    snapshot: Any | None = None
    file_path: str = ""
    project_root: str = ""
    raw_workspace_view: dict[str, Any] = field(default_factory=dict)
    base_workspace_view: dict[str, Any] = field(default_factory=dict)
    latest_observation: dict[str, Any] = field(default_factory=dict)
    committed_tactics: list[str] = field(default_factory=list)
    replay_prefix: list[str] = field(default_factory=list)
    replay_prefix_count: int = 0
    restore_anchor: dict[str, Any] = field(default_factory=dict)
    route_memories: list[dict[str, Any]] = field(default_factory=list)
    route_event_facts: list[dict[str, Any]] = field(default_factory=list)
    typed_events: list[dict[str, Any]] = field(default_factory=list)

    @property
    def state_version(self) -> int:
        try:
            return int(getattr(self.snapshot, "state_version", 0) or 0)
        except (TypeError, ValueError):
            return 0

    @property
    def session_epoch(self) -> int:
        try:
            return int(getattr(self.snapshot, "session_epoch", 0) or 0)
        except (TypeError, ValueError):
            return 0

    def to_dict(self) -> dict[str, Any]:
        snapshot = (
            self.snapshot.to_dict()
            if hasattr(self.snapshot, "to_dict") else {}
        )
        return _drop_empty({
            "node_id": self.node_id,
            "file_path": self.file_path,
            "project_root": self.project_root,
            "snapshot": snapshot,
            "state_version": self.state_version,
            "session_epoch": self.session_epoch,
            "latest_observation": self.latest_observation,
            "committed_tactics": list(self.committed_tactics),
            "replay_prefix": list(self.replay_prefix),
            "replay_prefix_count": self.replay_prefix_count,
            "restore_anchor": self.restore_anchor,
            "route_memories": [dict(item) for item in self.route_memories],
            "route_event_facts": [dict(item) for item in self.route_event_facts],
            "typed_events": [dict(item) for item in self.typed_events],
        })


class ProofNodeStateManager:
    """Builds aggregate state snapshots for one proof node."""

    def __init__(
        self,
        *,
        node_id: str,
        committed_tactic_reader: CommittedTacticReader,
    ) -> None:
        self.node_id = node_id
        self._committed_tactic_reader = committed_tactic_reader

    def current_committed_tactics(self) -> list[str]:
        return list(self._committed_tactic_reader())

    def build(
        self,
        *,
        snapshot: Any | None,
        raw_workspace_view: dict[str, Any],
        base_workspace_view: dict[str, Any],
        file_path: str = "",
        project_root: str = "",
        latest_observation: dict[str, Any] | None = None,
        replay_prefix: list[str] | None = None,
        replay_prefix_count: int = 0,
        restore_anchor: dict[str, Any] | None = None,
        route_memories: list[dict[str, Any]] | None = None,
        route_event_facts: list[dict[str, Any]] | None = None,
        typed_events: list[dict[str, Any]] | None = None,
    ) -> ProofNodeState:
        return ProofNodeState(
            node_id=self.node_id,
            snapshot=snapshot,
            file_path=str(file_path or ""),
            project_root=str(project_root or ""),
            raw_workspace_view=dict(raw_workspace_view),
            base_workspace_view=dict(base_workspace_view),
            latest_observation=dict(latest_observation or {}),
            committed_tactics=self.current_committed_tactics(),
            replay_prefix=list(replay_prefix or []),
            replay_prefix_count=max(0, int(replay_prefix_count or 0)),
            restore_anchor=dict(restore_anchor or {}),
            route_memories=[
                dict(item)
                for item in (route_memories or [])
                if isinstance(item, dict)
            ],
            route_event_facts=[
                dict(item)
                for item in (route_event_facts or [])
                if isinstance(item, dict)
            ],
            typed_events=[
                dict(item)
                for item in (typed_events or [])
                if isinstance(item, dict)
            ],
        )

