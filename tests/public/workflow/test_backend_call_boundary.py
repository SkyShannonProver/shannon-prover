"""Backend-call boundary marks recorded by ``ReplSessionManager._run_backend``.

The manager stall watchdog relies on these marks to tell a bounded backend
wait from a manager hang, so every call must be marked with the timeout that
``run_in_process_group`` actually enforces, and unmarked on every exit path.
"""
from __future__ import annotations

import subprocess
import threading
import time
from pathlib import Path

import pytest

from workflow.proof_management import backend_call_boundary
from workflow.proof_management.backend_call_boundary import BackendCallBoundaries
from workflow.proof_management.backend_request import BackendRequest
from workflow.proof_management.repl_session import (
    ReplBackendTimeout,
    ReplSessionManager,
)


class FakeClock:
    def __init__(self, start: float = 1000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def _repl(tmp_path: Path, monkeypatch) -> ReplSessionManager:
    repl = ReplSessionManager(
        file_path="eval/examples/SchnorrPK.ec",
        lemma_name="dummy",
        include_dir="easycrypt-src/theories",
        session_tag="backend_boundary_unit",
        node_id="Tree-boundary",
        project_root=tmp_path,
    )
    monkeypatch.setattr(ReplSessionManager, "_env", lambda self: {})
    return repl


def test_registry_tracks_in_flight_calls_per_thread_on_its_clock() -> None:
    clock = FakeClock()
    boundaries = BackendCallBoundaries(clock=clock)
    assert boundaries.snapshot().in_flight == ()
    assert boundaries.snapshot().last_transition is None
    outer = boundaries.enter("start", 180)
    clock.advance(2)
    seen: list[tuple[str, str]] = []

    def other() -> None:
        with boundaries.call("managed_goal_view", 60):
            seen.extend(
                (call.label, call.thread_name)
                for call in boundaries.snapshot().in_flight
            )

    worker = threading.Thread(target=other, name="other-thread")
    worker.start()
    worker.join(5)
    assert sorted(seen) == [
        ("managed_goal_view", "other-thread"),
        ("start", "MainThread"),
    ]
    snapshot = boundaries.snapshot()
    assert [(c.label, c.started, c.timeout_seconds) for c in snapshot.in_flight] == [
        ("start", 1000.0, 180.0)
    ]
    assert snapshot.last_label == "managed_goal_view"
    clock.advance(3)
    boundaries.exit(outer)
    boundaries.exit(outer)  # idempotent
    snapshot = boundaries.snapshot()
    assert snapshot.in_flight == ()
    assert snapshot.last_transition == 1005.0
    assert snapshot.last_label == "start"


def test_run_backend_marks_the_call_with_its_enforced_timeout(
    tmp_path: Path, monkeypatch
) -> None:
    clock = FakeClock()
    boundaries = BackendCallBoundaries(clock=clock)
    monkeypatch.setattr(backend_call_boundary, "BACKEND_CALLS", boundaries)
    repl = _repl(tmp_path, monkeypatch)
    seen: list[tuple[str, float]] = []

    def fake_run(cmd, **kwargs):
        seen.extend(
            (call.label, call.timeout_seconds)
            for call in boundaries.snapshot().in_flight
        )
        clock.advance(7.0)
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=kwargs["timeout"])

    monkeypatch.setattr(
        "workflow.proof_management.repl_session.run_in_process_group", fake_run
    )
    with pytest.raises(ReplBackendTimeout):
        repl._run_backend(
            BackendRequest.commit("commit_tactic", "auto."),
            actions=[],
            timeout=180,
        )
    # Turn-deadline clipping applies before the mark: the mark carries the
    # timeout run_in_process_group actually enforced.
    with repl.turn_deadline(time.time() + 42.0):
        with pytest.raises(ReplBackendTimeout):
            repl._run_backend(
                BackendRequest.undo("undo_last_step"),
                actions=[],
                timeout=120,
            )

    assert seen[0] == ("commit_tactic", 180.0)
    assert seen[1][0] == "undo_last_step"
    assert 40.0 < seen[1][1] <= 42.0
    after = boundaries.snapshot()
    assert after.in_flight == ()  # exit is marked even when the call raises
    assert after.last_label == "undo_last_step"
    assert after.last_transition == clock.now
