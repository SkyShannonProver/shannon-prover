"""Immutable committed-proof transport bound to one exact manager turn."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .types import ProofStateSnapshot


class CommittedHistoryRuntime(Protocol):
    """The sole session-owned entry point needed to bind a turn spine."""

    node_id: str
    session_dir: str
    state_version: int
    session_epoch: int

    def committed_history(self) -> list[str]: ...


@dataclass(frozen=True)
class CommittedTurnSpine:
    """One post-state-bound copy of the session owner's committed history.

    The spine is transport, not a durable ledger or semantic authority.  It
    never reads ``history.ec`` itself and deliberately has no qed/closedness
    helpers.  Construction calls the supplied session owner exactly once.
    """

    snapshot: ProofStateSnapshot
    tactics: tuple[str, ...]

    @classmethod
    def capture(
        cls,
        runtime: CommittedHistoryRuntime,
        snapshot: ProofStateSnapshot,
    ) -> "CommittedTurnSpine":
        if not isinstance(snapshot, ProofStateSnapshot):
            raise TypeError("CommittedTurnSpine requires an exact post snapshot")
        expected_identity = (
            runtime.node_id,
            runtime.session_dir,
            runtime.session_epoch,
            runtime.state_version,
        )
        observed_identity = (
            snapshot.node_id,
            snapshot.session_dir,
            snapshot.session_epoch,
            snapshot.state_version,
        )
        if observed_identity != expected_identity:
            raise ValueError(
                "CommittedTurnSpine snapshot does not match the current REPL "
                "node/session occurrence"
            )
        history = runtime.committed_history()
        if type(history) is not list or any(type(item) is not str for item in history):
            raise TypeError("committed_history() must return list[str]")
        return cls(snapshot=snapshot, tactics=tuple(history))
