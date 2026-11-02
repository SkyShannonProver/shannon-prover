"""Process-wide boundary marks around manager backend calls.

Every manager-owned EasyCrypt subprocess goes through
``ReplSessionManager._run_backend`` and carries its own timeout.  That function
marks the call's entry (with the timeout it will actually enforce) and its exit
here, so an out-of-band observer can tell "the manager is waiting on a bounded
backend call" from "the manager stopped making progress outside any call".

This module records timing facts only.  It never decides anything, never
blocks on proof state, and uses its own private lock, which is held for O(1)
dictionary updates and never across IO.  The stall policy that reads these
marks lives in ``workflow.proof_tool.manager_stall_watchdog``.
"""
from __future__ import annotations

import itertools
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass


@dataclass(frozen=True)
class BackendCall:
    """One in-flight backend call."""

    token: int
    label: str
    timeout_seconds: float
    started: float
    thread_ident: int
    thread_name: str


@dataclass(frozen=True)
class BackendCallSnapshot:
    """Immutable view of the registry at one instant."""

    in_flight: tuple[BackendCall, ...]
    last_transition: float | None
    last_label: str


class BackendCallBoundaries:
    """Thread-safe registry of in-flight backend calls on one clock.

    ``clock`` must be monotonic; a wall clock can jump (for example across a
    laptop sleep) and would turn into false stall reports.
    """

    def __init__(self, *, clock: Callable[[], float] = time.monotonic) -> None:
        self.clock = clock
        self._lock = threading.Lock()
        self._tokens = itertools.count(1)
        self._in_flight: dict[int, BackendCall] = {}
        self._last_transition: float | None = None
        self._last_label = ""

    def enter(self, label: str, timeout_seconds: float) -> int:
        thread = threading.current_thread()
        now = self.clock()
        with self._lock:
            token = next(self._tokens)
            self._in_flight[token] = BackendCall(
                token=token,
                label=str(label or "backend_call"),
                timeout_seconds=max(0.0, float(timeout_seconds)),
                started=now,
                thread_ident=int(thread.ident or 0),
                thread_name=thread.name,
            )
            self._last_transition = now
            self._last_label = str(label or "backend_call")
        return token

    def exit(self, token: int) -> None:
        now = self.clock()
        with self._lock:
            call = self._in_flight.pop(token, None)
            self._last_transition = now
            if call is not None:
                self._last_label = call.label

    @contextmanager
    def call(self, label: str, timeout_seconds: float) -> Iterator[None]:
        token = self.enter(label, timeout_seconds)
        try:
            yield
        finally:
            self.exit(token)

    def snapshot(self) -> BackendCallSnapshot:
        with self._lock:
            return BackendCallSnapshot(
                in_flight=tuple(self._in_flight.values()),
                last_transition=self._last_transition,
                last_label=self._last_label,
            )


# The worker process has one manager, so one registry is the whole state.
BACKEND_CALLS = BackendCallBoundaries()


@contextmanager
def backend_call(label: str, timeout_seconds: float) -> Iterator[None]:
    """Mark one backend call on the process registry (resolved per call)."""

    with BACKEND_CALLS.call(label, timeout_seconds):
        yield
