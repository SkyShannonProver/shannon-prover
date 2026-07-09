"""Analyzer evidence bundle for prover workspace rendering."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .checkpoints import CheckpointIndex


@dataclass(frozen=True)
class EvidenceBundle:
    route_health: list[dict[str, Any]] = field(default_factory=list)
    structural_transitions: list[dict[str, Any]] = field(default_factory=list)
    l4_panels: dict[str, dict[str, Any]] = field(default_factory=dict)
    view_overrides: dict[str, Any] = field(default_factory=dict)
    removed_panels: list[str] = field(default_factory=list)
    route_replay_memory: dict[str, Any] = field(default_factory=dict)
    lineage_briefing: dict[str, Any] = field(default_factory=dict)
    repair_episodes: list[dict[str, Any]] = field(default_factory=list)
    checkpoint_index: CheckpointIndex = field(default_factory=CheckpointIndex)

    def to_dict(self) -> dict[str, Any]:
        return {
            "route_health": [dict(item) for item in self.route_health],
            "structural_transitions": [
                dict(item) for item in self.structural_transitions
            ],
            "l4_panels": {
                key: dict(value)
                for key, value in self.l4_panels.items()
                if isinstance(value, dict)
            },
            "view_overrides": dict(self.view_overrides),
            "removed_panels": list(self.removed_panels),
            "route_replay_memory": dict(self.route_replay_memory),
            "lineage_briefing": dict(self.lineage_briefing),
            "repair_episodes": [
                dict(item)
                for item in self.repair_episodes
                if isinstance(item, dict)
            ],
            "checkpoint_index": self.checkpoint_index.to_dict(),
        }
