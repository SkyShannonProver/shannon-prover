"""Regression tests for proof-tool timing and bounded rewind replay."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from workflow.proof_management.repl_session import (  # noqa: E402
    ReplBackendTimeout,
    ReplSessionManager,
    replay_aggregate_budget_seconds,
)
from workflow.proof_tool.proof_tool_launch import ProofToolTimingBudget  # noqa: E402


def test_proof_tool_timing_budget_derives_ordered_transport_deadlines() -> None:
    budget = ProofToolTimingBudget.from_manager_budget(
        120.0,
        startup_seconds=15.0,
        transport_margin_seconds=7.5,
    )

    assert budget.startup_seconds == 15.0
    assert budget.manager_operation_seconds == 120.0
    assert budget.endpoint_read_seconds == 127.5
    assert budget.provider_tool_seconds == 135.0


@pytest.mark.parametrize(
    ("manager", "endpoint", "provider"),
    [
        (10.0, 10.0, 20.0),
        (10.0, 9.0, 20.0),
        (10.0, 20.0, 20.0),
    ],
)
def test_proof_tool_timing_budget_rejects_inverted_or_equal_deadlines(
    manager: float,
    endpoint: float,
    provider: float,
) -> None:
    with pytest.raises(ValueError, match="manager < endpoint < provider"):
        ProofToolTimingBudget(
            startup_seconds=5.0,
            manager_operation_seconds=manager,
            endpoint_read_seconds=endpoint,
            provider_tool_seconds=provider,
        )


# --------------------------------------------------------------------------
# Aggregate replay budget bounds the lock-held replay
# --------------------------------------------------------------------------


def test_replay_aggregate_budget_default_and_override(monkeypatch) -> None:
    monkeypatch.delenv("SHANNON_REPLAY_AGG_BUDGET", raising=False)
    monkeypatch.delenv("SHANNON_REPLAY_AGG_BUDGET_PER_TACTIC", raising=False)
    assert replay_aggregate_budget_seconds() == 600.0
    monkeypatch.setenv("SHANNON_REPLAY_AGG_BUDGET", "42.5")
    assert replay_aggregate_budget_seconds() == 42.5
    monkeypatch.setenv("SHANNON_REPLAY_AGG_BUDGET", "garbage")
    assert replay_aggregate_budget_seconds() == 600.0


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
    assert replay_aggregate_budget_seconds(10) == 600.0
    assert replay_aggregate_budget_seconds(40) == 600.0
    # The observed Layer-3 prefix: 123 tactics now budget 123 x 15s = 1845s.
    assert replay_aggregate_budget_seconds(123) == pytest.approx(1845.0)
    # Per-tactic rate is tunable without giving up scaling.
    monkeypatch.setenv("SHANNON_REPLAY_AGG_BUDGET_PER_TACTIC", "30")
    assert replay_aggregate_budget_seconds(123) == pytest.approx(3690.0)
    monkeypatch.setenv("SHANNON_REPLAY_AGG_BUDGET_PER_TACTIC", "garbage")
    assert replay_aggregate_budget_seconds(123) == pytest.approx(1845.0)
    # An explicit aggregate override wins VERBATIM — no scaling — so operators
    # can still pin (or disable, <= 0) the cap.
    monkeypatch.setenv("SHANNON_REPLAY_AGG_BUDGET", "42.5")
    assert replay_aggregate_budget_seconds(123) == 42.5
    monkeypatch.setenv("SHANNON_REPLAY_AGG_BUDGET", "0")
    assert replay_aggregate_budget_seconds(123) == 0.0


def test_replay_loop_deep_prefix_completes_under_scaled_budget(monkeypatch) -> None:
    """A deep replay that would blow the OLD flat 600s cap completes now.

    123 kept tactics at a faked ~8s each = ~984s total: over the old flat 600s
    budget (pre-fix this raised ReplBackendTimeout partway), under the scaled
    123 x 15s = 1845s budget. Reverting `_start_locked` to the un-scaled
    `replay_aggregate_budget_seconds()` call makes this test fail.
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
        repl, "_snapshot_from_managed_goal_view", lambda *, actions: object()
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
        repl, "_snapshot_from_managed_goal_view", lambda *, actions: object()
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
        repl, "_snapshot_from_managed_goal_view", lambda *, actions: object()
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
