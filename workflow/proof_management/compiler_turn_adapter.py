"""Manager-owned adapter for one compiler invocation and its telemetry."""
from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import replace
from typing import Any

from workflow.proof_state_compiler.service import CompilerServiceSkipped
from workflow.proof_state_compiler.turn_evidence import compiler_turn_evidence

from .turn_spine import CommittedTurnSpine
from .types import ManagedTurn


class CompilerTurnDeadlineExceeded(RuntimeError):
    """Raised when the shared absolute turn deadline has expired."""


class CompilerTurnAdapter:
    """The single manager boundary for compiler calls and telemetry.

    The adapter consumes the immutable post-turn spine; it does not read proof
    history or derive proof lifecycle facts.  Ordinary compiler failure remains
    an abstention, while an expired shared turn deadline is propagated so the
    manager can fail the node closed.
    """

    def __init__(
        self,
        *,
        node_id: str,
        service: Any | None,
        session_id: Callable[[], str],
        audit: Callable[[dict[str, Any]], None],
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.node_id = node_id
        self.service = service
        self._session_id = session_id
        self._audit = audit
        self._clock = clock

    def compile_current(
        self,
        *,
        turn: ManagedTurn | None = None,
        spine: CommittedTurnSpine | None = None,
        deadline: float | None = None,
    ) -> str:
        self._require_time(deadline)
        if self.service is None:
            return ""
        evidence = None
        if turn is not None and spine is not None:
            evidence = compiler_turn_evidence(
                turn,
                session_id=self._session_id(),
                committed_history=spine.tactics,
            )
        try:
            result = self.service.compile_current_state(turn_evidence=evidence)
        except Exception as exc:
            self._audit({
                "kind": "proof_state_compiler.failed",
                "node": self.node_id,
                "error_type": type(exc).__name__,
                "error": str(exc)[:600],
            })
            # A backend timeout at the shared absolute deadline is a serving
            # health failure, not an ordinary compiler abstention.  Check the
            # same deadline before taking the failure return path so Manager
            # always receives a typed unhealthy turn.
            self._require_time(deadline)
            return ""
        self._require_time(deadline)
        self._audit({
            "kind": "proof_state_compiler.completed",
            "node": self.node_id,
            **result.telemetry,
        })
        if isinstance(result, CompilerServiceSkipped):
            return ""
        return result.admission.presentation.text

    def enrich(
        self,
        turn: ManagedTurn,
        spine: CommittedTurnSpine,
        *,
        deadline: float | None = None,
    ) -> ManagedTurn:
        markdown = self.compile_current(
            turn=turn,
            spine=spine,
            deadline=deadline,
        )
        return replace(
            turn,
            committed_tactics=spine.tactics,
            compiler_markdown=markdown,
        )

    def _require_time(self, deadline: float | None) -> None:
        if deadline is not None and self._clock() >= float(deadline):
            raise CompilerTurnDeadlineExceeded(
                "shared proof-tool turn deadline expired during compiler phase"
            )
