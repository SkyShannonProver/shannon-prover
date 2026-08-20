"""Canonical session goal identity for resume and daemon continuity."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from core.easycrypt.session.session_projection import read_proof_state_projection


@dataclass(frozen=True)
class SessionGoalIdentity:
    """Goal identity plus the canonical proof-state classification.

    An active/open proof must carry a non-empty goal hash across a resume or
    daemon-attach boundary.  A canonically closed proof has no active frontier
    to distinguish, so it may safely omit that hash.  Keeping both facts in one
    projection read prevents callers from classifying one snapshot and hashing
    another.
    """

    goal_hash: str
    proof_status: str
    goal_identity_required: bool


def read_session_goal_identity(session_dir: str | Path) -> SessionGoalIdentity:
    """Read the canonical goal identity and whether an identity is required.

    Both the identity class and hash come from one
    :class:`ProofStateProjection` occurrence.  A projection failure therefore
    returns an unusable open identity instead of reinterpreting ``current.out``
    through a second path.
    """

    path = Path(session_dir)
    goal_hash = ""
    proof_status = "unknown"
    try:
        projection = read_proof_state_projection(path)
        if not projection.events.ok or not projection.consistency.ok:
            raise ValueError("proof-state projection authority is invalid")
        proof_status = str(projection.status or "unknown")
        goal_identity_required = projection.goal_identity_required
        value = projection.goal.active_goal_hash
        if value:
            goal_hash = str(value)
    except Exception:
        goal_identity_required = True

    return SessionGoalIdentity(
        goal_hash=goal_hash if goal_identity_required else "",
        proof_status=proof_status,
        goal_identity_required=goal_identity_required,
    )
