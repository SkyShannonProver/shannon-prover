"""Regression tests for the rewind false-wedge fix.

Two independent defects produced the observed "bridge wedged" symptom:

* Defect A: ``_bridge_roundtrip`` left the *connect* timeout installed on the
  socket, so a legitimately slow-but-finite manager reply (a rewind replay)
  inherited the short connect timeout and raised ``socket.timeout``, misreported
  to the agent as ``MANAGER BRIDGE ERROR``. Fix: decouple the read timeout from
  the connect timeout.

* Defect B: a confirmed rewind does restart + per-tactic replay of the whole
  kept prefix with no aggregate cap while holding the bridge lock. Fix: bound the
  replay loop with an aggregate budget that surfaces progress and aborts cleanly.

These tests use loopback sockets / fakes only - no real EC backend, no real
bridge.
"""
from __future__ import annotations

import json
import socket
import socketserver
import sys
import threading
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from workflow.proof_node_mcp_server import (  # noqa: E402
    _bridge_connect_timeout,
    _bridge_read_timeout,
    _bridge_roundtrip,
)
from workflow.proof_management.repl_session import (  # noqa: E402
    ReplBackendTimeout,
    ReplSessionManager,
    _replay_aggregate_budget_seconds,
)


# --------------------------------------------------------------------------
# Defect A: read timeout decoupled from connect timeout
# --------------------------------------------------------------------------


class _SlowBridge(socketserver.ThreadingTCPServer):
    allow_reuse_address = True


def _make_slow_bridge(reply: dict, delay_seconds: float):
    """A loopback TCP server that replies after ``delay_seconds``."""

    class Handler(socketserver.StreamRequestHandler):
        def handle(self) -> None:
            # Drain the request (client does SHUT_WR after sending).
            self.rfile.readline(2_000_000)
            time.sleep(delay_seconds)
            self.wfile.write((json.dumps(reply)).encode("utf-8"))

    server = _SlowBridge(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def test_bridge_roundtrip_succeeds_on_slow_but_finite_reply(monkeypatch) -> None:
    """A reply that arrives AFTER the connect timeout must NOT false-wedge.

    We set a tiny connect timeout (1s) and a generous read timeout (10s), and a
    bridge that takes 2s to answer. Pre-fix this raised socket.timeout (the 1s
    connect timeout governed recv); post-fix the slow-but-finite reply succeeds.
    """
    monkeypatch.setenv("SHANNON_BRIDGE_CONNECT_TIMEOUT", "1")
    monkeypatch.setenv("SHANNON_BRIDGE_READ_TIMEOUT", "10")

    expected = {"exit_code": 0, "text": "rewind replay finished"}
    server, _ = _make_slow_bridge(expected, delay_seconds=2.0)
    try:
        host, port = server.server_address
        data = _bridge_roundtrip(host, int(port), {"token": "t", "text": "x"})
    finally:
        server.shutdown()
        server.server_close()

    assert data == expected


def test_bridge_read_timeout_is_decoupled_from_connect_timeout(monkeypatch) -> None:
    """The read deadline is configured independently from the connect deadline."""
    monkeypatch.setenv("SHANNON_BRIDGE_CONNECT_TIMEOUT", "5")
    monkeypatch.setenv("SHANNON_BRIDGE_READ_TIMEOUT", "300")
    assert _bridge_connect_timeout() == 5.0
    assert _bridge_read_timeout() == 300.0


def test_bridge_read_timeout_default_is_generous() -> None:
    """Default read timeout comfortably covers a multi-minute rewind replay."""
    # No env override -> large finite default, far above the 30s connect default
    # and above the observed ~236-248s rewind replay.
    assert (_bridge_read_timeout() or 0) >= 300.0


def test_bridge_read_timeout_zero_means_blocking(monkeypatch) -> None:
    monkeypatch.setenv("SHANNON_BRIDGE_READ_TIMEOUT", "0")
    assert _bridge_read_timeout() is None


def test_bridge_roundtrip_sets_read_timeout_not_connect_timeout(monkeypatch) -> None:
    """Verify the socket carries the READ timeout after connect, not connect's."""
    monkeypatch.setenv("SHANNON_BRIDGE_CONNECT_TIMEOUT", "1")
    monkeypatch.setenv("SHANNON_BRIDGE_READ_TIMEOUT", "123")

    captured: dict[str, float | None] = {}

    real_create_connection = socket.create_connection

    class _SpySocket:
        def __init__(self, inner: socket.socket) -> None:
            self._inner = inner

        def settimeout(self, value):  # type: ignore[no-untyped-def]
            captured["read_timeout"] = value
            return self._inner.settimeout(value)

        def __getattr__(self, name):  # type: ignore[no-untyped-def]
            return getattr(self._inner, name)

        def __enter__(self):
            return self

        def __exit__(self, *exc):  # type: ignore[no-untyped-def]
            self._inner.close()
            return False

    def fake_create_connection(addr, timeout=None):  # type: ignore[no-untyped-def]
        captured["connect_timeout"] = timeout
        return _SpySocket(real_create_connection(addr, timeout=timeout))

    monkeypatch.setattr(socket, "create_connection", fake_create_connection)

    expected = {"exit_code": 0, "text": "ok"}
    server, _ = _make_slow_bridge(expected, delay_seconds=0.0)
    try:
        host, port = server.server_address
        _bridge_roundtrip(host, int(port), {"token": "t", "text": "x"})
    finally:
        server.shutdown()
        server.server_close()

    assert captured["connect_timeout"] == 1.0
    assert captured["read_timeout"] == 123.0


# --------------------------------------------------------------------------
# Defect B: aggregate replay budget bounds the lock-held replay
# --------------------------------------------------------------------------


def test_replay_aggregate_budget_default_and_override(monkeypatch) -> None:
    monkeypatch.delenv("SHANNON_REPLAY_AGG_BUDGET", raising=False)
    monkeypatch.delenv("SHANNON_REPLAY_AGG_BUDGET_PER_TACTIC", raising=False)
    assert _replay_aggregate_budget_seconds() == 600.0
    monkeypatch.setenv("SHANNON_REPLAY_AGG_BUDGET", "42.5")
    assert _replay_aggregate_budget_seconds() == 42.5
    monkeypatch.setenv("SHANNON_REPLAY_AGG_BUDGET", "garbage")
    assert _replay_aggregate_budget_seconds() == 600.0


def test_replay_aggregate_budget_scales_with_prefix_length(monkeypatch) -> None:
    """REGRESSION (2026-06-11): the budget must scale with the kept prefix.

    A flat 600s cap falsely aborted a legitimate, known-good 123-tactic replay
    (heavy smt calls, >4.9s/tactic average) during a Layer-3 crash respawn. The
    budget is now max(600s floor, 15s x kept tactics): short prefixes keep the
    600s wedge cap; deep prefixes get room proportional to their length.
    """
    monkeypatch.delenv("SHANNON_REPLAY_AGG_BUDGET", raising=False)
    monkeypatch.delenv("SHANNON_REPLAY_AGG_BUDGET_PER_TACTIC", raising=False)
    # Short prefix: the 600s floor still applies (the original wedge cap).
    assert _replay_aggregate_budget_seconds(10) == 600.0
    assert _replay_aggregate_budget_seconds(40) == 600.0
    # The observed Layer-3 prefix: 123 tactics now budget 123 x 15s = 1845s.
    assert _replay_aggregate_budget_seconds(123) == pytest.approx(1845.0)
    # Per-tactic rate is tunable without giving up scaling.
    monkeypatch.setenv("SHANNON_REPLAY_AGG_BUDGET_PER_TACTIC", "30")
    assert _replay_aggregate_budget_seconds(123) == pytest.approx(3690.0)
    monkeypatch.setenv("SHANNON_REPLAY_AGG_BUDGET_PER_TACTIC", "garbage")
    assert _replay_aggregate_budget_seconds(123) == pytest.approx(1845.0)
    # An explicit aggregate override wins VERBATIM — no scaling — so operators
    # can still pin (or disable, <= 0) the cap.
    monkeypatch.setenv("SHANNON_REPLAY_AGG_BUDGET", "42.5")
    assert _replay_aggregate_budget_seconds(123) == 42.5
    monkeypatch.setenv("SHANNON_REPLAY_AGG_BUDGET", "0")
    assert _replay_aggregate_budget_seconds(123) == 0.0


def test_replay_loop_deep_prefix_completes_under_scaled_budget(monkeypatch) -> None:
    """A deep replay that would blow the OLD flat 600s cap completes now.

    123 kept tactics at a faked ~8s each = ~984s total: over the old flat 600s
    budget (pre-fix this raised ReplBackendTimeout partway), under the scaled
    123 x 15s = 1845s budget. Reverting `_start_locked` to the un-scaled
    `_replay_aggregate_budget_seconds()` call makes this test fail.
    """
    repl = _make_repl()
    monkeypatch.delenv("SHANNON_REPLAY_AGG_BUDGET", raising=False)
    monkeypatch.delenv("SHANNON_REPLAY_AGG_BUDGET_PER_TACTIC", raising=False)

    clock = {"t": 0.0}
    monkeypatch.setattr(
        "workflow.proof_management.repl_session.time.perf_counter",
        lambda: clock["t"],
    )

    def fake_run_backend(label, args, *, actions, timeout):  # type: ignore[no-untyped-def]
        clock["t"] += 8.0
        actions.append({"label": label, "exit_code": 0})
        return ""

    monkeypatch.setattr(repl, "_run_backend", fake_run_backend)
    monkeypatch.setattr(
        repl, "_snapshot_from_agent_view", lambda *, actions: object()
    )

    tactics = [f"t{i}." for i in range(123)]
    snapshot, actions = repl._start_locked(
        replay_prefix=tactics,
        label="resume",
        force_restart=True,
    )
    assert snapshot is not None
    labels = [a["label"] for a in actions]
    assert sum(1 for l in labels if l.startswith("replay_prefix_step_")) == 123
    assert not any(l == "replay_prefix_aggregate_budget" for l in labels)


def _make_repl() -> ReplSessionManager:
    return ReplSessionManager(
        file_path="eval/examples/SchnorrPK.ec",
        lemma_name="dummy",
        include_dir="easycrypt-src/theories",
        session_tag="rewind_wedge_unit",
        node_id="Tree-unit",
        project_root=ROOT,
    )


def test_replay_loop_aborts_when_aggregate_budget_exceeded(monkeypatch) -> None:
    """A long replay must abort with a progress-bearing ReplBackendTimeout.

    We stub ``_run_backend`` so each replayed tactic 'takes' time (via a faked
    monotonic clock) and never touches a real EC backend. With a small aggregate
    budget the loop must stop partway and raise, recording how far it got - so
    the bridge lock is never held past the budget.
    """
    repl = _make_repl()
    monkeypatch.setenv("SHANNON_REPLAY_AGG_BUDGET", "5")

    # Fake monotonic clock: each call advances by 2s, so after 3 steps elapsed
    # is >= 5s and the 4th iteration trips the budget check.
    clock = {"t": 0.0}

    def fake_perf_counter() -> float:
        return clock["t"]

    calls: list[str] = []

    def fake_run_backend(label, args, *, actions, timeout):  # type: ignore[no-untyped-def]
        calls.append(label)
        clock["t"] += 2.0
        actions.append({"label": label, "exit_code": 0})
        return ""

    monkeypatch.setattr(
        "workflow.proof_management.repl_session.time.perf_counter",
        fake_perf_counter,
    )
    monkeypatch.setattr(repl, "_run_backend", fake_run_backend)

    tactics = [f"t{i}." for i in range(20)]

    with pytest.raises(ReplBackendTimeout) as excinfo:
        # Drive the locked replay path directly.
        repl._start_locked(
            replay_prefix=tactics,
            label="undo_to_checkpoint",
            force_restart=True,
        )

    action = excinfo.value.action
    assert action["label"] == "replay_prefix_aggregate_budget"
    assert action["timed_out"] is True
    assert action["timeout_seconds"] == 5.0
    # Progress is surfaced and we stopped well short of all 20 tactics.
    assert action["replay_steps_total"] == 20
    assert 0 < action["replay_steps_completed"] < 20
    assert action["mutates_proof_state"] is True
    # The error summary explains the abort to the manager/agent.
    summary = action["agent_observation"]["error_summary"]
    assert "aggregate" in summary
    # The -start call plus a bounded number of replay steps ran; not all 20.
    replay_calls = [c for c in calls if c.startswith("replay_prefix_step_")]
    assert len(replay_calls) < 20


def test_replay_loop_completes_within_budget(monkeypatch) -> None:
    """A replay that fits the budget completes normally (no false abort)."""
    repl = _make_repl()
    monkeypatch.setenv("SHANNON_REPLAY_AGG_BUDGET", "1000")

    def fake_run_backend(label, args, *, actions, timeout):  # type: ignore[no-untyped-def]
        actions.append({"label": label, "exit_code": 0})
        return ""

    monkeypatch.setattr(repl, "_run_backend", fake_run_backend)
    monkeypatch.setattr(
        repl, "_snapshot_from_agent_view", lambda *, actions: object()
    )

    tactics = [f"t{i}." for i in range(5)]
    snapshot, actions = repl._start_locked(
        replay_prefix=tactics,
        label="undo_to_checkpoint",
        force_restart=True,
    )
    assert snapshot is not None
    labels = [a["label"] for a in actions]
    assert sum(1 for l in labels if l.startswith("replay_prefix_step_")) == 5
    assert not any(l == "replay_prefix_aggregate_budget" for l in labels)


def test_replay_loop_unbounded_when_budget_disabled(monkeypatch) -> None:
    """Budget <= 0 restores the legacy unbounded behaviour (no abort)."""
    repl = _make_repl()
    monkeypatch.setenv("SHANNON_REPLAY_AGG_BUDGET", "0")

    clock = {"t": 0.0}
    monkeypatch.setattr(
        "workflow.proof_management.repl_session.time.perf_counter",
        lambda: clock["t"],
    )

    def fake_run_backend(label, args, *, actions, timeout):  # type: ignore[no-untyped-def]
        clock["t"] += 1000.0  # huge per-step elapsed; would trip any positive cap
        actions.append({"label": label, "exit_code": 0})
        return ""

    monkeypatch.setattr(repl, "_run_backend", fake_run_backend)
    monkeypatch.setattr(
        repl, "_snapshot_from_agent_view", lambda *, actions: object()
    )

    tactics = [f"t{i}." for i in range(4)]
    snapshot, actions = repl._start_locked(
        replay_prefix=tactics,
        label="undo_to_checkpoint",
        force_restart=True,
    )
    assert snapshot is not None
    labels = [a["label"] for a in actions]
    assert sum(1 for l in labels if l.startswith("replay_prefix_step_")) == 4
