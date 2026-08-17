"""Shared proof-node facade types.

These are the small immutable records passed across the manager boundary.
Keeping them outside ``proof_node_manager`` lets backend/session services and
runtime code depend on the stable facade contract without importing the whole
manager implementation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .protocol_repair import AgentIntent


def has_agent_observation_kind(
    actions: list[dict[str, Any]],
    kind: str,
) -> bool:
    """Project an explicit manager/session observation without re-judging it."""

    return any(
        isinstance(action, dict)
        and isinstance(action.get("agent_observation"), dict)
        and action["agent_observation"].get("kind") == kind
        for action in actions
    )


@dataclass(frozen=True)
class ProofStateSnapshot:
    node_id: str
    session_tag: str
    session_dir: str
    session_epoch: int
    state_version: int
    goal_hash: str
    goal_identity_required: bool
    workspace_view_artifact: str = ""
    execution_refs: dict[str, Any] = field(default_factory=dict)
    raw_workspace_view: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("node_id", "session_tag", "session_dir"):
            value = getattr(self, field_name)
            if type(value) is not str or not value:
                raise ValueError(f"{field_name} must be a non-empty string")
        if type(self.session_epoch) is not int or self.session_epoch < 0:
            raise ValueError("session_epoch must be a non-negative integer")
        if type(self.state_version) is not int or self.state_version < 0:
            raise ValueError("state_version must be a non-negative integer")
        if type(self.goal_hash) is not str:
            raise TypeError("goal_hash must be a string")
        if type(self.goal_identity_required) is not bool:
            raise TypeError("goal_identity_required must be a bool")
        if self.goal_identity_required and not self.goal_hash:
            raise ValueError("open ProofStateSnapshot requires goal_hash")
        if not self.goal_identity_required and self.goal_hash:
            raise ValueError("closed ProofStateSnapshot cannot carry goal_hash")
        if type(self.execution_refs) is not dict:
            raise TypeError("execution_refs must be an object")
        if type(self.raw_workspace_view) is not dict:
            raise TypeError("raw_workspace_view must be an object")

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "session_tag": self.session_tag,
            "session_dir": self.session_dir,
            "session_epoch": self.session_epoch,
            "state_version": self.state_version,
            "goal_hash": self.goal_hash,
            "goal_identity_required": self.goal_identity_required,
            "workspace_view_artifact": self.workspace_view_artifact,
            "execution_refs": dict(self.execution_refs),
        }


@dataclass(frozen=True)
class NodeHealthEvent:
    node_id: str
    status: str
    message: str
    state_version: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "status": self.status,
            "message": self.message,
            "state_version": self.state_version,
        }


@dataclass(frozen=True)
class NodeProgressSummary:
    node_id: str
    session_tag: str
    state_version: int
    goal_hash: str
    proof_status: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "session_tag": self.session_tag,
            "state_version": self.state_version,
            "goal_hash": self.goal_hash,
            "proof_status": self.proof_status,
        }


@dataclass(frozen=True)
class ManagedTurn:
    ok: bool
    workspace_view: dict[str, Any]
    snapshot: ProofStateSnapshot | None = None
    repair_prompt: str = ""
    health_event: NodeHealthEvent | None = None
    intent: AgentIntent | None = None
    manager_actions: list[dict[str, Any]] = field(default_factory=list)
    manager_observations: dict[str, Any] = field(default_factory=dict)
    # Exact committed history observed by the manager after this turn.  This is
    # transport for turn-coherent presentation, not a second history authority.
    committed_tactics: tuple[str, ...] = field(default_factory=tuple)
    # Exact P4-admitted compiler Markdown. Workflow may only embed this block;
    # it must not parse, trim, reorder, or render it again.
    compiler_markdown: str = ""
