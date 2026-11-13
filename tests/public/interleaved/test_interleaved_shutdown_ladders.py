"""Signal order and waits of the interleaved product's shutdown ladders.

Each ladder stops a child started with ``start_new_session=True`` by
signalling its process group. A fake process records every group signal and
every wait, so these tests pin the exact sequence, including the grace
periods, without sleeping.
"""
from __future__ import annotations

import os
import signal
import subprocess

import pytest

from workflow.interleaved import inner_runner, jobs, runner

INT, TERM, KILL = signal.SIGINT, signal.SIGTERM, signal.SIGKILL


class _Child:
    """Exits when it receives a signal in ``exits_on`` (SIGKILL always works
    unless ``unkillable``). ``group_gone`` models a child that already exited
    and whose process group no longer exists."""

    pid = 4321

    def __init__(self, exits_on=(), *, unkillable=False, group_gone=False, exited=False):
        self.exits_on = set(exits_on)
        self.unkillable = unkillable
        self.group_gone = group_gone
        self.returncode = 0 if exited else None
        self.trace: list[tuple[str, object]] = []

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        self.trace.append(("wait", timeout))
        if self.group_gone and self.returncode is None:
            self.returncode = 0
        if self.returncode is not None:
            return self.returncode
        raise subprocess.TimeoutExpired("child", timeout)

    def signal_group(self, pid, sig):
        assert pid == self.pid
        self.trace.append(("signal", sig))
        if self.group_gone:
            raise ProcessLookupError(pid)
        if sig in self.exits_on or (sig == KILL and not self.unkillable):
            self.returncode = -sig


@pytest.fixture
def child(monkeypatch):
    def make(*args, **kwargs):
        made = _Child(*args, **kwargs)
        monkeypatch.setattr(os, "killpg", made.signal_group)
        return made
    return make


def _sig(sig):
    return ("signal", sig)


def _wait(timeout):
    return ("wait", timeout)


# --- runner.terminate_group: the operator's Ctrl-C path for the outer agent

@pytest.mark.parametrize(
    ("exits_on", "expected"),
    [
        ({INT}, [_sig(INT), _wait(10)]),
        ({TERM}, [_sig(INT), _wait(10), _sig(TERM), _wait(10)]),
        ((), [_sig(INT), _wait(10), _sig(TERM), _wait(10), _sig(KILL)]),
    ],
)
def test_terminate_group_escalates_int_term_kill(child, exits_on, expected) -> None:
    process = child(exits_on)
    runner.terminate_group(process)
    assert process.trace == expected


def test_terminate_group_leaves_an_exited_child_alone(child) -> None:
    process = child(exited=True)
    runner.terminate_group(process)
    assert process.trace == []


def test_terminate_group_stops_when_the_group_is_gone(child) -> None:
    process = child(group_gone=True)
    runner.terminate_group(process)
    assert process.trace[0] == _sig(INT)
    assert _sig(TERM) not in process.trace and _sig(KILL) not in process.trace


# --- jobs._stop_inner_process: a lane worker stopping its inner orchestrator

@pytest.mark.parametrize(
    ("exits_on", "expected"),
    [
        ({TERM}, [_sig(TERM), _wait(8)]),
        ((), [_sig(TERM), _wait(8), _sig(KILL), _wait(2)]),
    ],
)
def test_stop_inner_process_escalates_term_kill(child, exits_on, expected) -> None:
    process = child(exits_on)
    jobs._stop_inner_process(process)
    assert process.trace == expected


def test_stop_inner_process_raises_when_even_sigkill_does_not_reap(child) -> None:
    process = child(unkillable=True)
    with pytest.raises(subprocess.TimeoutExpired):
        jobs._stop_inner_process(process)
    assert process.trace == [_sig(TERM), _wait(8), _sig(KILL), _wait(2)]


def test_stop_inner_process_reaps_a_child_whose_group_is_gone(child) -> None:
    process = child(group_gone=True)
    jobs._stop_inner_process(process)
    assert process.trace == [_sig(TERM), _wait(8)]
    assert process.returncode == 0


def test_stop_inner_process_leaves_an_exited_child_alone(child) -> None:
    process = child(exited=True)
    jobs._stop_inner_process(process)
    assert process.trace == []


def test_request_inner_process_stop_only_sends_sigterm(child) -> None:
    process = child()
    jobs._request_inner_process_stop(process)
    assert process.trace == [_sig(TERM)]


# --- inner_runner._wait_for_orchestrator: safe stop of the inner orchestrator

def _wait_after_interruption(process):
    return inner_runner._wait_for_orchestrator(
        process, interruption_requested=lambda: True, grace_seconds=0.0,
    )


def test_orchestrator_that_honours_sigint_finishes_cleanly(child) -> None:
    process = child({INT})
    assert _wait_after_interruption(process) == (-INT, "")
    assert process.trace == [_wait(0.25), _sig(INT), _wait(0.25)]


@pytest.mark.parametrize(
    ("exits_on", "tail", "status"),
    [
        ({TERM}, [_sig(TERM), _wait(4.0)], -TERM),
        ((), [_sig(TERM), _wait(4.0), _sig(KILL), _wait(None)], -KILL),
    ],
)
def test_orchestrator_past_its_grace_gets_term_then_kill(child, exits_on, tail, status) -> None:
    process = child(exits_on)
    exit_code, reason = _wait_after_interruption(process)
    assert exit_code == status
    assert reason.startswith("managed safe-stop handback exceeded")
    assert process.trace == [_wait(0.25), _sig(INT), _wait(0.25), *tail]
