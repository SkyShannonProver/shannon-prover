"""Deterministic same-goal no-progress guidance for a managed proof node."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from workflow.proof_management import ManagedTurn


@dataclass
class NoProgressGuidance:
    """Track repeated rejected commits without interpreting EasyCrypt text."""

    threshold: int = 3
    _goal_hash: str = ""
    _committed_count: int = 0
    _attempts: list[str] = field(default_factory=list)

    def seed(self, *, goal_hash: str, committed_count: int) -> None:
        self._goal_hash = str(goal_hash or "")
        self._committed_count = max(0, int(committed_count))
        self._attempts = []

    def observe(
        self,
        turn: ManagedTurn,
        handled_intent: dict[str, Any] | None,
    ) -> str:
        view = turn.workspace_view if isinstance(turn.workspace_view, dict) else {}
        status = view.get("proof_status")
        status = status if isinstance(status, dict) else {}
        goal_hash = str(status.get("goal_hash") or "")
        committed_count = len(tuple(turn.committed_tactics or ()))
        intent = handled_intent if isinstance(handled_intent, dict) else {}
        payload = intent.get("payload")
        payload = payload if isinstance(payload, dict) else {}
        tactic = str(payload.get("tactic") or "").strip()
        is_commit = intent.get("intent") == "commit_tactic" and bool(tactic)

        if not goal_hash:
            self._goal_hash = ""
            self._committed_count = committed_count
            self._attempts = []
            return ""
        made_progress = committed_count > self._committed_count
        if goal_hash != self._goal_hash or made_progress:
            self._goal_hash = goal_hash
            self._committed_count = committed_count
            self._attempts = []
            if made_progress:
                return ""
        self._committed_count = committed_count
        if not is_commit:
            return ""
        self._attempts.append(tactic[:500])
        if len(self._attempts) != self.threshold:
            return ""
        distinct = len(set(self._attempts))
        return (
            "## Manager no-progress nudge\n\n"
            f"The unchanged current goal has seen {len(self._attempts)} "
            f"commit attempts ({distinct} distinct tactic texts) without extending "
            "the accepted prefix. Stop cycling through guessed synonymous lemma "
            "names. Reuse any persistent handoff resource anchor or declaration "
            "already advertised by the manager; otherwise construct a local helper, "
            "amend the route, or restart. Do not call tools outside the current "
            "managed proof-tool contract."
        )
