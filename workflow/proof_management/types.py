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


@dataclass(frozen=True)
class ProofStateSnapshot:
    node_id: str
    session_tag: str
    session_dir: str
    session_epoch: int
    state_version: int
    goal_hash: str
    proof_context_view_artifact: str = ""
    workspace_view_artifact: str = ""
    execution_refs: dict[str, Any] = field(default_factory=dict)
    raw_workspace_view: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "session_tag": self.session_tag,
            "session_dir": self.session_dir,
            "session_epoch": self.session_epoch,
            "state_version": self.state_version,
            "goal_hash": self.goal_hash,
            "proof_context_view_artifact": self.proof_context_view_artifact,
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
