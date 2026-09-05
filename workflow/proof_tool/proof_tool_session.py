"""Serialized serving session for the one managed proof tool.

This module sits above the authenticated loopback transport and below the
proof-node runtime.  It owns serving lifecycle only: idempotency, the manager
turn budget, durable turn presentation, and the stop/unhealthy latch.  It does
not parse proof intents, inspect manager actions, read committed history, or
decide whether a proof succeeded.
"""
from __future__ import annotations

import json
import math
import threading
import time
import traceback
from dataclasses import dataclass
from typing import Any, Callable, Protocol

from workflow.proof_management.types import ManagedTurn, TurnDirective
from workflow.proof_tool.proof_tool_contract import ProofToolContractManifest


class ManagedTurnHandler(Protocol):
    """The single semantic manager entry point consumed by this session."""

    def __call__(
        self,
        raw_arguments: Any,
        absolute_deadline: float,
    ) -> ManagedTurn: ...


class TurnMemory(Protocol):
    """Narrow NodeMemory surface used after a completed manager turn."""

    def record_turn(
        self,
        *,
        turn_index: int,
        raw_text: str,
        handled_intent: dict[str, Any] | None,
        turn: ManagedTurn,
    ) -> None: ...


TurnRenderer = Callable[
    [ManagedTurn, int, dict[str, Any] | None, TurnMemory],
    str,
]


@dataclass(frozen=True)
class ProofToolSessionResponse:
    """Exact cached result of one endpoint call."""

    exit_code: int
    text: str
    turn_index: int
    directive: TurnDirective
    manager_turn_completed: bool

    @property
    def is_error(self) -> bool:
        return self.exit_code != 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "exit_code": self.exit_code,
            "text": self.text,
            "turn_index": self.turn_index,
            "directive": self.directive.value,
            "manager_turn_completed": self.manager_turn_completed,
        }


@dataclass(frozen=True)
class ProofToolStopBoundary:
    """Snapshot taken after the current manager turn has drained.

    ``request_stop`` closes admission before waiting on the serving lock.  The
    returned spine is therefore the exact last manager-returned state: no later
    proof intent can slip between the stop request and checkpoint creation.
    """

    turn_index: int
    committed_tactics: tuple[str, ...]
    reason: str


class ProofToolSession:
    """One serialized, idempotent proof-tool serving session.

    The same lock covers the complete serving transaction: state/budget check,
    exactly one manager call, memory and rendering, directive latching, and the
    authoritative completed-turn index.  A duplicate call therefore waits for
    the first call to finish and receives the exact immutable cached response.
    """

    def __init__(
        self,
        *,
        node_id: str,
        manifest: ProofToolContractManifest,
        handle_turn: ManagedTurnHandler,
        memory: TurnMemory,
        response_renderer: TurnRenderer,
        max_turns: int,
        initial_committed_tactics: tuple[str, ...] = (),
        emit: Callable[[dict[str, Any]], None] | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.node_id = str(node_id or "").strip()
        if not self.node_id:
            raise ValueError("proof-tool session requires a non-empty node id")
        self.manifest = manifest
        self._handle_turn = handle_turn
        self._memory = memory
        self._response_renderer = response_renderer
        self.max_turns = max(1, int(max_turns))
        self._emit = emit or (lambda _event: None)
        self._clock = clock
        self._lock = threading.Lock()
        # This event is intentionally separate from the serving lock.  A stop
        # requester sets it immediately, then waits for the current manager
        # turn to leave the lock.  Any queued submitter observes the closed
        # admission gate after acquiring the lock and cannot start another
        # semantic call ahead of checkpoint finalization.
        self._stop_admission = threading.Event()
        self._turn_index = 0
        self._last_committed_tactics = tuple(initial_committed_tactics)
        self._stop_requested = False
        self._stop_reason = ""
        self._unhealthy_reason = ""
        self._entries: dict[str, ProofToolSessionResponse] = {}

    @property
    def turn_index(self) -> int:
        with self._lock:
            return self._turn_index

    @property
    def stop_requested(self) -> bool:
        return self._stop_admission.is_set()

    @property
    def last_committed_count(self) -> int:
        """Last exact post-turn committed-spine size exposed to the runtime."""

        with self._lock:
            return len(self._last_committed_tactics)

    @property
    def last_committed_tactics(self) -> tuple[str, ...]:
        """Last immutable manager-returned spine, cached for continuation only."""

        with self._lock:
            return self._last_committed_tactics

    @property
    def unhealthy_reason(self) -> str:
        with self._lock:
            return self._unhealthy_reason

    def request_stop(self, reason: str) -> ProofToolStopBoundary:
        """Close admission, drain one in-flight turn, and freeze its spine.

        This is the manager-owned safe-stop boundary used by timeout, outer
        cancellation, and worker process signals.  It may block only while the
        one already-admitted manager call completes; it never admits another
        proof intent after the request becomes visible.
        """

        stop_reason = str(reason or "external stop requested").strip()
        self._stop_admission.set()
        with self._lock:
            self._stop_requested = True
            if not self._stop_reason:
                self._stop_reason = stop_reason
            return ProofToolStopBoundary(
                turn_index=self._turn_index,
                committed_tactics=self._last_committed_tactics,
                reason=self._stop_reason,
            )

    def submit(
        self,
        *,
        call_id: str,
        raw_arguments: Any,
        absolute_deadline: float,
    ) -> ProofToolSessionResponse:
        """Execute or replay one proof-tool call.

        ``call_id`` is an internal transport identity, never an agent-supplied
        proof identity.  A repeated call id replays the exact cached response
        (envelope validation is the endpoint's job; the call id is minted by
        our own adapter from the launch id + JSON-RPC id).
        """

        call_key = str(call_id or "").strip()
        if not call_key:
            raise ValueError("proof-tool call requires a non-empty call id")
        deadline = _absolute_deadline(absolute_deadline)

        with self._lock:
            prior = self._entries.get(call_key)
            if prior is not None:
                if self._unhealthy_reason:
                    # Timeout/unhealthy results themselves replay byte-for-byte.
                    # A previously successful result must not survive a later
                    # failure that invalidated the whole session.
                    if prior.directive is TurnDirective.NODE_UNHEALTHY:
                        return prior
                    response = self._current_unhealthy_response()
                    self._entries[call_key] = response
                    return response
                return prior

            if self._unhealthy_reason:
                response = self._current_unhealthy_response()
                self._cache(call_key, response)
                return response
            if self._stop_admission.is_set() or self._stop_requested:
                response = ProofToolSessionResponse(
                    exit_code=0,
                    text=(
                        "MANAGER WORKER STOP: "
                        + (
                            "finish was already accepted"
                            if not self._stop_reason
                            else self._stop_reason
                        )
                        + ". Stop submitting proof intents and return your "
                        "concise PROVER REPORT."
                    ),
                    turn_index=self._turn_index,
                    directive=TurnDirective.STOP_REQUESTED,
                    manager_turn_completed=False,
                )
                self._cache(call_key, response)
                return response
            if self._turn_index >= self.max_turns:
                response = ProofToolSessionResponse(
                    exit_code=0,
                    text=(
                        "MANAGER WORKER STOP: turn limit reached before proof "
                        "completion. Produce a concise PROVER REPORT and stop."
                    ),
                    turn_index=self._turn_index,
                    directive=TurnDirective.STOP_REQUESTED,
                    manager_turn_completed=False,
                )
                self._stop_requested = True
                self._stop_admission.set()
                self._stop_reason = "turn limit reached"
                self._cache(call_key, response)
                return response
            if self._clock() >= deadline:
                response = self._unhealthy_response(
                    "proof-tool request deadline expired before the manager turn began"
                )
                self._cache(call_key, response)
                return response

            manager_completed = False
            next_turn_index = self._turn_index + 1
            try:
                turn = self._handle_turn(raw_arguments, deadline)
                manager_completed = True
                if not isinstance(turn, ManagedTurn):
                    raise TypeError("manager returned a non-ManagedTurn result")
                self._last_committed_tactics = tuple(turn.committed_tactics)
                if self._clock() > deadline:
                    self._turn_index = next_turn_index
                    response = self._unhealthy_response(
                        "proof-tool manager turn exceeded its absolute deadline",
                        manager_turn_completed=True,
                    )
                    self._cache(call_key, response)
                    self._emit_completed_turn(self._turn_index)
                    return response

                handled_intent = (
                    turn.intent.to_dict() if turn.intent is not None else None
                )
                self._memory.record_turn(
                    turn_index=next_turn_index,
                    raw_text=_canonical_arguments_text(raw_arguments),
                    handled_intent=handled_intent,
                    turn=turn,
                )
                rendered = self._response_renderer(
                    turn,
                    next_turn_index,
                    handled_intent,
                    self._memory,
                )
                if not isinstance(rendered, str):
                    raise TypeError("proof-tool response renderer returned non-text")

                self._apply_directive(turn.directive, turn)
                self._turn_index = next_turn_index
                exit_code = 2 if turn.directive is TurnDirective.NODE_UNHEALTHY else 0
                response = ProofToolSessionResponse(
                    exit_code=exit_code,
                    text=rendered,
                    turn_index=self._turn_index,
                    directive=turn.directive,
                    manager_turn_completed=True,
                )
                self._cache(call_key, response)
                self._emit_completed_turn(self._turn_index)
                return response
            except Exception as exc:
                # A returned ManagedTurn is a completed semantic turn even when
                # its memory/renderer projection fails.  Preserve that turn count
                # while refusing all further serving on the uncertain boundary.
                # This try covers three different subsystems (manager turn,
                # memory IO, renderer) — keep the full traceback on stderr so a
                # renderer KeyError is distinguishable from a manager KeyError.
                traceback.print_exc()
                if manager_completed:
                    self._turn_index = next_turn_index
                phase = "memory/renderer" if manager_completed else "manager turn"
                response = self._unhealthy_response(
                    f"proof-tool session failed in the {phase} "
                    f"({type(exc).__name__}: {str(exc)[:300]})",
                    manager_turn_completed=manager_completed,
                )
                self._cache(call_key, response)
                if manager_completed:
                    self._emit_completed_turn(self._turn_index)
                return response

    def _apply_directive(self, directive: TurnDirective, turn: ManagedTurn) -> None:
        if directive is TurnDirective.STOP_REQUESTED:
            self._stop_requested = True
            self._stop_admission.set()
        elif directive is TurnDirective.NODE_UNHEALTHY:
            health = turn.health_event
            detail = (
                f"{health.status}: {health.message}"
                if health is not None
                else "manager marked the node unhealthy"
            )
            self._unhealthy_reason = detail

    def _unhealthy_response(
        self,
        reason: str,
        *,
        manager_turn_completed: bool = False,
    ) -> ProofToolSessionResponse:
        self._unhealthy_reason = str(reason or "proof-tool session is unhealthy")
        return self._current_unhealthy_response(
            manager_turn_completed=manager_turn_completed
        )

    def _current_unhealthy_response(
        self,
        *,
        manager_turn_completed: bool = False,
    ) -> ProofToolSessionResponse:
        return ProofToolSessionResponse(
            exit_code=2,
            text=(
                "MANAGER WORKER STOP: proof node is unhealthy: "
                + (self._unhealthy_reason or "unknown proof-tool session failure")
            ),
            turn_index=self._turn_index,
            directive=TurnDirective.NODE_UNHEALTHY,
            manager_turn_completed=manager_turn_completed,
        )

    def _cache(self, call_id: str, response: ProofToolSessionResponse) -> None:
        self._entries[call_id] = response

    def _emit_completed_turn(self, turn_index: int) -> None:
        self._safe_emit({
            "type": "system",
            "kind": "manager_turn.completed",
            "node": self.node_id,
            "turn_index": turn_index,
        })

    def _safe_emit(self, event: dict[str, Any]) -> None:
        try:
            self._emit(event)
        except Exception:
            # Telemetry is a projection of an already-completed session action.
            return


def _absolute_deadline(value: float) -> float:
    try:
        deadline = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("proof-tool absolute deadline must be numeric") from exc
    if not math.isfinite(deadline) or deadline <= 0:
        raise ValueError("proof-tool absolute deadline must be finite and positive")
    return deadline


def _canonical_arguments_text(raw_arguments: Any) -> str:
    return json.dumps(
        raw_arguments,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
