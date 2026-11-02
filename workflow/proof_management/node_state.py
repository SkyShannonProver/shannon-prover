"""The one mutable per-node state shared by the manager's services."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .types import ProofStateSnapshot


@dataclass
class NodeTurnState:
    """What the lifecycle, executor and recovery services read and write.

    ``ProofNodeManager`` creates one instance and passes the same object to
    every service, so a write by one (a projection, a rewind that lifts the
    resume floor) is what the next reader sees.
    """

    latest_snapshot: ProofStateSnapshot | None = None
    latest_view: dict[str, Any] = field(default_factory=dict)
    # The view as projected, kept apart from ``latest_view``, which an
    # observation overlay may replace after projection.
    latest_full_view: dict[str, Any] = field(default_factory=dict)
    replay_prefix: list[str] = field(default_factory=list)
    # Transient resume FLOOR: a rewind below it clears it so the shorter
    # history reads as fully agent-owned.
    replay_prefix_count: int = 0
    # Write-once LINEAGE fact: a respawn/resume child stays a resumed node for
    # its whole life.  The amend_and_replay guard keys off this so a
    # rewind-into-prefix cannot silently re-enable amend on a resumed node.
    resumed_from_prefix: bool = False

    def clear_replay_prefix(self) -> None:
        """Lift the resume floor; the lineage marker deliberately stays."""

        self.replay_prefix_count = 0
        self.replay_prefix = []
