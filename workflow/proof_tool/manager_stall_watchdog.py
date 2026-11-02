"""Out-of-band stall watchdog for one proof-node manager.

Every manager backend call already has its own timeout, but nothing bounds the
manager's own Python code: a deadlock, a blocked lock or a stuck thread inside a
turn holds the serving lock forever.  The node is never marked unhealthy, and
the worker later blocks on the same lock in its post-run reads until the
supervisor escalates to SIGKILL.

This watchdog runs on its own daemon thread and reads only two sources of
timing facts, both on one monotonic clock:

* the backend-call boundary marks recorded by ``_run_backend``
  (:mod:`workflow.proof_management.backend_call_boundary`); and
* the serving turn window, which :class:`ProofToolSession` opens only after it
  has acquired its serving lock (waiting for that lock is not a stall).

A stall is one of:

* ``backend_call_overrun``: a backend call is still in flight after its own
  timeout plus a grace period (default 30 s);
* ``manager_idle``: a turn is being served, no backend call is in flight, and
  no call boundary or turn start happened for the idle cap (default 300 s);
* ``endpoint_thread_dead``: the endpoint's accept loop died while serving.

``SHANNON_MANAGER_STALL_WATCHDOG`` selects the mode (default ``report``):

* ``off``: no watchdog thread;
* ``report``: emit one ``manager_turn.stalled`` audit record per stall episode
  and change nothing else;
* ``enforce``: close the agent, emit the record best-effort with a short
  timeout, then ``os._exit(MANAGER_STALL_EXIT_CODE)``.  The supervisor treats
  that exit as a crash and Layer-3 respawns the node from its checkpoint.

The watchdog never touches the proof-tool session lock or the REPL session
lock.  Every callback it makes (agent close, emit) runs on a helper thread with
a timeout, because the stalled thread may hold a lock the callback needs.
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
import traceback
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from workflow.proof_management import backend_call_boundary
from workflow.proof_management.backend_call_boundary import (
    BackendCall,
    BackendCallBoundaries,
)


MANAGER_STALL_WATCHDOG_ENV = "SHANNON_MANAGER_STALL_WATCHDOG"
MANAGER_STALL_WATCHDOG_MODES = ("off", "report", "enforce")
DEFAULT_MANAGER_STALL_WATCHDOG_MODE = "report"
MANAGER_STALL_EVENT_KIND = "manager_turn.stalled"
# EX_TEMPFAIL: a temporary failure the caller should retry.  The tree
# supervisor maps this exact code (with no final result event) to the Layer-3
# crash-respawn path; see ``workflow.tree.supervisor._layer3_gates_pass``.
MANAGER_STALL_EXIT_CODE = 75

DEFAULT_IDLE_CAP_SECONDS = 300.0
DEFAULT_CALL_GRACE_SECONDS = 30.0
DEFAULT_POLL_SECONDS = 5.0
DEFAULT_EMIT_TIMEOUT_SECONDS = 5.0
DEFAULT_CLOSE_TIMEOUT_SECONDS = 25.0

_MAX_FRAMES_PER_THREAD = 40
_PROJECT_ROOT = str(Path(__file__).resolve().parents[2]) + os.sep


def manager_stall_watchdog_mode(
    environ: Mapping[str, str] | None = None,
) -> str:
    """Return the configured mode; an unknown value observes, never enforces."""

    raw = (os.environ if environ is None else environ).get(
        MANAGER_STALL_WATCHDOG_ENV, ""
    )
    mode = str(raw or "").strip().lower()
    if mode in MANAGER_STALL_WATCHDOG_MODES:
        return mode
    return DEFAULT_MANAGER_STALL_WATCHDOG_MODE


@dataclass(frozen=True)
class _ServingTurn:
    serial: int
    turn_index: int
    started: float
    thread_ident: int
    thread_name: str


class ManagerStallWatchdog:
    """Detect a manager that stopped making progress inside a served turn.

    ``turn_started``/``turn_finished`` form the proof-tool session's turn
    monitor.  ``check`` is one evaluation; the background thread calls it every
    ``poll_seconds``.  Tests drive ``check`` directly with an injected clock
    (the clock of ``boundaries``) and an injected ``exit_fn``.
    """

    def __init__(
        self,
        *,
        node_id: str,
        mode: str,
        emit: Callable[[dict[str, Any]], None],
        close_agent: Callable[[str], None] | None = None,
        endpoint_alive: Callable[[], bool | None] | None = None,
        boundaries: BackendCallBoundaries | None = None,
        idle_cap_seconds: float = DEFAULT_IDLE_CAP_SECONDS,
        call_grace_seconds: float = DEFAULT_CALL_GRACE_SECONDS,
        poll_seconds: float = DEFAULT_POLL_SECONDS,
        emit_timeout_seconds: float = DEFAULT_EMIT_TIMEOUT_SECONDS,
        close_timeout_seconds: float = DEFAULT_CLOSE_TIMEOUT_SECONDS,
        exit_code: int = MANAGER_STALL_EXIT_CODE,
        exit_fn: Callable[[int], Any] = os._exit,
    ) -> None:
        if mode not in MANAGER_STALL_WATCHDOG_MODES:
            raise ValueError(f"unknown manager stall watchdog mode {mode!r}")
        self.node_id = str(node_id or "")
        self.mode = mode
        self._emit = emit
        self._close_agent = close_agent
        self._endpoint_alive = endpoint_alive
        self._boundaries = (
            boundaries
            if boundaries is not None
            else backend_call_boundary.BACKEND_CALLS
        )
        self._clock = self._boundaries.clock
        self.idle_cap_seconds = float(idle_cap_seconds)
        self.call_grace_seconds = float(call_grace_seconds)
        self.poll_seconds = max(0.001, float(poll_seconds))
        self.emit_timeout_seconds = max(0.0, float(emit_timeout_seconds))
        self.close_timeout_seconds = max(0.0, float(close_timeout_seconds))
        self.exit_code = int(exit_code)
        self._exit_fn = exit_fn
        # Private to the watchdog and held only for O(1) updates.
        self._state_lock = threading.Lock()
        self._turn: _ServingTurn | None = None
        self._turn_serial = 0
        self._reported: set[tuple[Any, ...]] = set()
        self._stopped = False
        self._stop_event = threading.Event()
        self._exit_pending = threading.Event()
        self._exit_ready = threading.Event()
        self._thread: threading.Thread | None = None

    # -- turn monitor (called by ProofToolSession with its lock held) --------

    def turn_started(self, turn_index: int) -> None:
        thread = threading.current_thread()
        now = self._clock()
        with self._state_lock:
            self._turn_serial += 1
            self._turn = _ServingTurn(
                serial=self._turn_serial,
                turn_index=int(turn_index),
                started=now,
                thread_ident=int(thread.ident or 0),
                thread_name=thread.name,
            )

    def turn_finished(self) -> None:
        with self._state_lock:
            self._turn = None

    # -- lifecycle -----------------------------------------------------------

    @property
    def exit_pending(self) -> bool:
        return self._exit_pending.is_set()

    def start(self) -> None:
        if self.mode == "off" or self._thread is not None:
            return
        self._thread = threading.Thread(
            target=self._poll_forever,
            name=f"manager-stall-watchdog-{self.node_id}",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        """Stop detecting.  An enforced exit already under way still completes."""

        with self._state_lock:
            self._stopped = True
        self._stop_event.set()
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=1.0)

    def hand_off_exit(self) -> None:
        """Let an enforced stall exit finish instead of returning a result.

        The runtime calls this on its way out.  If ``check`` has decided to
        exit, the caller must not go on to publish a final result (that would
        turn the stall into a clean give-up), so it waits for the bounded
        close/emit sequence and exits with the stall code itself.
        """

        if not self._exit_pending.is_set():
            return
        self._exit_ready.wait(
            self.close_timeout_seconds + self.emit_timeout_seconds + 5.0
        )
        self._exit_fn(self.exit_code)

    def _poll_forever(self) -> None:
        while not self._stop_event.wait(self.poll_seconds):
            try:
                self.check()
            except Exception:
                traceback.print_exc()

    # -- detection -----------------------------------------------------------

    def check(self) -> dict[str, Any] | None:
        """Evaluate once; return the record of a newly detected stall."""

        if self.mode == "off" or self._exit_pending.is_set():
            return None
        now = self._clock()
        stall = self._detect(now)
        if stall is None:
            return None
        episode = stall.pop("episode")
        with self._state_lock:
            if self._stopped or episode in self._reported:
                return None
            self._reported.add(episode)
            if self.mode == "enforce":
                self._exit_pending.set()
        record = self._record(stall)
        if self.mode == "report":
            _run_bounded(lambda: self._emit(record), self.emit_timeout_seconds)
            return record
        self._enforce_exit(record)
        return record

    def _detect(self, now: float) -> dict[str, Any] | None:
        if self._endpoint_alive is not None:
            try:
                alive = self._endpoint_alive()
            except Exception:
                alive = None
            if alive is False:
                return {
                    "episode": ("endpoint",),
                    "stall_kind": "endpoint_thread_dead",
                    "where": {"component": "proof_tool_endpoint"},
                    "elapsed_seconds": None,
                    "cap_seconds": None,
                    "turn": self._current_turn(),
                    "in_flight": (),
                    "now": now,
                }
        snapshot = self._boundaries.snapshot()
        overdue = [
            call
            for call in snapshot.in_flight
            if now - call.started > call.timeout_seconds + self.call_grace_seconds
        ]
        if overdue:
            call = max(
                overdue,
                key=lambda item: now - item.started - item.timeout_seconds,
            )
            return {
                "episode": ("call", call.token),
                "stall_kind": "backend_call_overrun",
                "where": {
                    "phase": "inside_backend_call",
                    "backend_call": call.label,
                    "timeout_seconds": call.timeout_seconds,
                    "thread": call.thread_name,
                    "frame": _top_frame(call.thread_ident),
                },
                "elapsed_seconds": now - call.started,
                "cap_seconds": call.timeout_seconds + self.call_grace_seconds,
                "turn": self._current_turn(),
                "in_flight": snapshot.in_flight,
                "now": now,
            }
        turn = self._current_turn()
        if turn is None or snapshot.in_flight:
            return None
        idle_since = turn.started
        last_call = ""
        if (
            snapshot.last_transition is not None
            and snapshot.last_transition >= turn.started
        ):
            idle_since = snapshot.last_transition
            last_call = snapshot.last_label
        elapsed = now - idle_since
        if elapsed <= self.idle_cap_seconds:
            return None
        return {
            "episode": ("idle", turn.serial, idle_since),
            "stall_kind": "manager_idle",
            "where": {
                "phase": "outside_backend_call",
                "last_backend_call": last_call,
                "thread": turn.thread_name,
                "frame": _top_frame(turn.thread_ident),
            },
            "elapsed_seconds": elapsed,
            "cap_seconds": self.idle_cap_seconds,
            "turn": turn,
            "in_flight": (),
            "now": now,
        }

    def _current_turn(self) -> _ServingTurn | None:
        with self._state_lock:
            return self._turn

    def _record(self, stall: dict[str, Any]) -> dict[str, Any]:
        now = float(stall["now"])
        turn = stall["turn"]
        elapsed = stall["elapsed_seconds"]
        cap = stall["cap_seconds"]
        record: dict[str, Any] = {
            "kind": MANAGER_STALL_EVENT_KIND,
            "node": self.node_id,
            "mode": self.mode,
            "action": "exit" if self.mode == "enforce" else "report",
            "stall_kind": stall["stall_kind"],
            "where": stall["where"],
            "elapsed_seconds": None if elapsed is None else round(elapsed, 3),
            "cap_seconds": None if cap is None else round(cap, 3),
            "turn_index": None if turn is None else turn.turn_index,
            "turn_elapsed_seconds": (
                None if turn is None else round(now - turn.started, 3)
            ),
            "in_flight_backend_calls": [
                _call_summary(call, now) for call in stall["in_flight"]
            ],
            "pid": os.getpid(),
            "detected_at_epoch": time.time(),
            "thread_stacks": _thread_stacks(),
        }
        if self.mode == "enforce":
            record["exit_code"] = self.exit_code
        return record

    def _enforce_exit(self, record: dict[str, Any]) -> None:
        reason = (
            f"manager stall watchdog: {record['stall_kind']} "
            f"(elapsed {record['elapsed_seconds']}s)"
        )
        if self._close_agent is not None:
            close_agent = self._close_agent
            _run_bounded(lambda: close_agent(reason), self.close_timeout_seconds)
        _run_bounded(lambda: self._emit(record), self.emit_timeout_seconds)
        self._exit_ready.set()
        self._exit_fn(self.exit_code)


def _run_bounded(action: Callable[[], Any], timeout: float) -> bool:
    """Run ``action`` on a daemon thread; give up waiting after ``timeout``."""

    def target() -> None:
        try:
            action()
        except Exception:
            traceback.print_exc()

    worker = threading.Thread(
        target=target,
        name="manager-stall-watchdog-callback",
        daemon=True,
    )
    worker.start()
    worker.join(timeout)
    return not worker.is_alive()


def _call_summary(call: BackendCall, now: float) -> dict[str, Any]:
    return {
        "label": call.label,
        "timeout_seconds": call.timeout_seconds,
        "elapsed_seconds": round(now - call.started, 3),
        "thread": call.thread_name,
    }


def _short_path(path: str) -> str:
    return path[len(_PROJECT_ROOT):] if path.startswith(_PROJECT_ROOT) else path


def _top_frame(thread_ident: int) -> str:
    frame = sys._current_frames().get(thread_ident)
    if frame is None:
        return ""
    code = frame.f_code
    return f"{_short_path(code.co_filename)}:{frame.f_lineno} in {code.co_name}"


def _thread_stacks() -> list[dict[str, Any]]:
    names = {thread.ident: thread for thread in threading.enumerate()}
    own = threading.get_ident()
    stacks: list[dict[str, Any]] = []
    for ident, frame in sorted(sys._current_frames().items()):
        if ident == own:
            continue
        thread = names.get(ident)
        summary = traceback.extract_stack(frame)[-_MAX_FRAMES_PER_THREAD:]
        stacks.append({
            "thread": thread.name if thread is not None else f"thread-{ident}",
            "daemon": bool(thread.daemon) if thread is not None else None,
            "stack": [
                f"{_short_path(item.filename)}:{item.lineno} in {item.name}"
                + (f": {item.line}" if item.line else "")
                for item in summary
            ],
        })
    return stacks


def append_audit_record(path: Path, record: Mapping[str, Any]) -> None:
    """Append one JSON line with a single ``O_APPEND`` write.

    The manager audit file is shared by every node of a run.  One raw write
    keeps the line whole without taking any Python-level lock the stalled
    thread might hold.
    """

    data = (json.dumps(dict(record), sort_keys=True, default=str) + "\n").encode(
        "utf-8"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(path), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
    try:
        os.write(fd, data)
    finally:
        os.close(fd)


def stall_headline(record: Mapping[str, Any]) -> str:
    """One stderr line; the supervisor's crash hint shows the last one."""

    where = record.get("where") if isinstance(record.get("where"), Mapping) else {}
    location = (
        where.get("backend_call")
        or where.get("frame")
        or where.get("component")
        or "unknown"
    )
    action = (
        f"exiting with code {record.get('exit_code')}"
        if record.get("action") == "exit"
        else "report only"
    )
    return (
        f"managed worker: manager stall watchdog ({action}): "
        f"{record.get('stall_kind')} in turn {record.get('turn_index')} "
        f"after {record.get('elapsed_seconds')}s (cap {record.get('cap_seconds')}s) "
        f"at {location}"
    )
