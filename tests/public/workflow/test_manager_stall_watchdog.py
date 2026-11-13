"""Manager stall watchdog (F1): detection, modes, enforce exit, wiring.

No model, network or EasyCrypt: backend calls are faked at
``run_in_process_group``, time comes from an injected clock, and the enforce
exit runs in a subprocess.
"""
from __future__ import annotations

import json
import subprocess
import sys
import textwrap
import threading
import time
from pathlib import Path
from typing import Any

import pytest

from workflow.proof_management import backend_call_boundary
from workflow.proof_management.backend_call_boundary import BackendCallBoundaries
from workflow.proof_management.backend_request import BackendRequest
from workflow.proof_management.repl_session import (
    ReplBackendError,
    ReplBackendTimeout,
    ReplSessionManager,
)
from workflow.proof_management.types import ManagedTurn
from workflow.proof_tool.manager_stall_watchdog import (
    MANAGER_STALL_EVENT_KIND,
    MANAGER_STALL_EXIT_CODE,
    MANAGER_STALL_WATCHDOG_ENV,
    ManagerStallWatchdog,
    append_audit_record,
    manager_stall_watchdog_mode,
    stall_headline,
)
from workflow.proof_tool.proof_tool_contract import resolve_proof_tool_contract
from workflow.proof_tool.proof_tool_endpoint import ProofToolEndpointServer
from workflow.proof_tool.proof_tool_session import ProofToolSession


ROOT = Path(__file__).resolve().parents[3]


class FakeClock:
    def __init__(self, start: float = 1000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class _Memory:
    def record_turn(self, **_kwargs: Any) -> None:
        return


def _watchdog(
    clock: FakeClock,
    *,
    mode: str = "report",
    events: list[dict[str, Any]] | None = None,
    **kwargs: Any,
) -> tuple[ManagerStallWatchdog, BackendCallBoundaries, list[dict[str, Any]]]:
    sink: list[dict[str, Any]] = [] if events is None else events
    boundaries = BackendCallBoundaries(clock=clock)
    watchdog = ManagerStallWatchdog(
        node_id="Tree-stall",
        mode=mode,
        emit=sink.append,
        boundaries=boundaries,
        **kwargs,
    )
    return watchdog, boundaries, sink


def _session(handle_turn, *, watchdog=None) -> ProofToolSession:
    return ProofToolSession(
        node_id="Tree-stall",
        manifest=resolve_proof_tool_contract("l1_goal_projection"),
        handle_turn=handle_turn,
        memory=_Memory(),
        response_renderer=lambda *_args: "rendered",
        max_turns=10,
        turn_monitor=watchdog,
    )


def _submit(session: ProofToolSession, call_id: str):
    return session.submit(
        call_id=call_id,
        raw_arguments={"intent": "commit_tactic"},
        absolute_deadline=time.time() + 3600,
    )


def _repl(tmp_path: Path, monkeypatch) -> ReplSessionManager:
    repl = ReplSessionManager(
        file_path="eval/examples/SchnorrPK.ec",
        lemma_name="dummy",
        include_dir="easycrypt-src/theories",
        session_tag="stall_watchdog_unit",
        node_id="Tree-stall",
        project_root=tmp_path,
    )
    monkeypatch.setattr(ReplSessionManager, "_env", lambda self: {})
    return repl


# -- configuration -----------------------------------------------------------


def test_mode_defaults_to_report_and_never_enforces_by_accident() -> None:
    assert manager_stall_watchdog_mode({}) == "report"
    assert manager_stall_watchdog_mode({MANAGER_STALL_WATCHDOG_ENV: ""}) == "report"
    assert manager_stall_watchdog_mode({MANAGER_STALL_WATCHDOG_ENV: " OFF "}) == "off"
    assert (
        manager_stall_watchdog_mode({MANAGER_STALL_WATCHDOG_ENV: "enforce"})
        == "enforce"
    )
    # The retired proposal spelling must not silently enable hard exits.
    assert manager_stall_watchdog_mode({MANAGER_STALL_WATCHDOG_ENV: "fail"}) == "report"
    with pytest.raises(ValueError):
        ManagerStallWatchdog(node_id="n", mode="fail", emit=lambda _r: None)


# -- backend calls through _run_backend ---------------------------------------


def test_backend_call_exceeding_its_cap_is_reported(
    tmp_path: Path, monkeypatch
) -> None:
    clock = FakeClock()
    watchdog, boundaries, events = _watchdog(clock)
    monkeypatch.setattr(backend_call_boundary, "BACKEND_CALLS", boundaries)
    repl = _repl(tmp_path, monkeypatch)
    entered = threading.Event()
    release = threading.Event()

    def hung_run(cmd, **kwargs):
        entered.set()
        release.wait(10)
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(
        "workflow.proof_management.repl_session.run_in_process_group", hung_run
    )

    def call() -> None:
        watchdog.turn_started(3)
        try:
            repl._run_backend(
                BackendRequest.commit("commit_tactic", "smt()."),
                actions=[],
                timeout=180,
            )
        except (ReplBackendError, ReplBackendTimeout):
            pass
        finally:
            watchdog.turn_finished()

    worker = threading.Thread(target=call, name="serving-turn")
    worker.start()
    try:
        assert entered.wait(5)
        clock.advance(180 + 30)  # exactly at the cap: still legitimate
        assert watchdog.check() is None
        clock.advance(0.5)
        record = watchdog.check()
        assert record is not None
        clock.advance(500)
        assert watchdog.check() is None  # one record per stall episode
    finally:
        release.set()
        worker.join(5)

    assert events == [record]
    assert record["kind"] == MANAGER_STALL_EVENT_KIND
    assert record["stall_kind"] == "backend_call_overrun"
    assert record["action"] == "report"
    assert record["where"]["backend_call"] == "commit_tactic"
    assert record["where"]["timeout_seconds"] == 180.0
    assert record["where"]["thread"] == "serving-turn"
    assert record["elapsed_seconds"] == 210.5
    assert record["cap_seconds"] == 210.0
    assert record["turn_index"] == 3
    assert "exit_code" not in record
    stacks = {item["thread"]: item["stack"] for item in record["thread_stacks"]}
    assert any("hung_run" in frame for frame in stacks["serving-turn"])


def test_long_legitimate_backend_calls_never_trigger(
    tmp_path: Path, monkeypatch
) -> None:
    clock = FakeClock()
    watchdog, boundaries, events = _watchdog(clock)
    monkeypatch.setattr(backend_call_boundary, "BACKEND_CALLS", boundaries)
    repl = _repl(tmp_path, monkeypatch)

    def slow_run(cmd, **kwargs):
        # Each call runs just under its own timeout; the watchdog looks in
        # several times while the call is in flight.
        for _ in range(6):
            clock.advance((kwargs["timeout"] - 1.0) / 6)
            assert watchdog.check() is None
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(
        "workflow.proof_management.repl_session.run_in_process_group", slow_run
    )
    watchdog.turn_started(1)
    # Thirty heavy calls in one turn: far beyond the 300 s idle cap in total,
    # but every gap between boundaries is short.
    for index in range(30):
        try:
            repl._run_backend(
                BackendRequest.commit(f"replay_prefix_step_{index}", "smt()."),
                actions=[],
                timeout=180,
            )
        except (ReplBackendError, ReplBackendTimeout):
            pass
        clock.advance(0.3)
        assert watchdog.check() is None
    watchdog.turn_finished()
    clock.advance(10_000)  # between turns the agent may think indefinitely
    assert watchdog.check() is None
    assert events == []


# -- manager idle outside any backend call -------------------------------------


def test_manager_step_sleeping_outside_any_call_is_reported_once() -> None:
    clock = FakeClock()
    watchdog, boundaries, events = _watchdog(clock)
    watchdog.turn_started(7)
    clock.advance(5)
    with boundaries.call("managed_goal_view", 60):
        clock.advance(20)
    clock.advance(300)  # exactly the idle cap since the last boundary
    assert watchdog.check() is None
    clock.advance(1)
    record = watchdog.check()
    assert record is not None
    for _ in range(5):
        clock.advance(120)
        assert watchdog.check() is None
    watchdog.turn_finished()

    assert events == [record]
    assert record["stall_kind"] == "manager_idle"
    assert record["where"]["phase"] == "outside_backend_call"
    assert record["where"]["last_backend_call"] == "managed_goal_view"
    assert record["elapsed_seconds"] == 301.0
    assert record["cap_seconds"] == 300.0
    assert record["turn_index"] == 7
    assert record["turn_elapsed_seconds"] == 326.0
    assert record["in_flight_backend_calls"] == []

    # Report mode changes nothing else: a later healthy turn is unaffected
    # and a later, separate stall is reported again.
    watchdog.turn_started(8)
    with boundaries.call("commit_tactic", 180):
        clock.advance(100)
    assert watchdog.check() is None
    clock.advance(301)
    assert watchdog.check() is not None
    assert len(events) == 2


def test_report_mode_thread_emits_one_event_and_the_turn_completes() -> None:
    events: list[dict[str, Any]] = []
    boundaries = BackendCallBoundaries()
    watchdog = ManagerStallWatchdog(
        node_id="Tree-stall",
        mode="report",
        emit=events.append,
        boundaries=boundaries,
        idle_cap_seconds=0.2,
        poll_seconds=0.01,
    )
    calls = {"n": 0}

    def handle_turn(_raw, _deadline) -> ManagedTurn:
        calls["n"] += 1
        if calls["n"] == 1:
            time.sleep(1.0)  # a manager step outside any backend call
        return ManagedTurn(ok=True, workspace_view={})

    session = _session(handle_turn, watchdog=watchdog)
    watchdog.start()
    try:
        first = _submit(session, "call-1")
        second = _submit(session, "call-2")
    finally:
        watchdog.stop()

    assert len(events) == 1
    assert events[0]["stall_kind"] == "manager_idle"
    assert events[0]["turn_index"] == 1
    # Report mode left the session healthy and serving.
    assert first.text == second.text == "rendered"
    assert session.unhealthy_reason == ""
    assert session.turn_index == 2
    assert watchdog.exit_pending is False


# -- waiting for the serving lock is not a stall --------------------------------


def test_waiting_for_the_session_lock_is_not_counted() -> None:
    clock = FakeClock()
    watchdog, boundaries, events = _watchdog(clock)
    in_turn = threading.Event()
    release_turn = threading.Event()

    def handle_turn(_raw, _deadline) -> ManagedTurn:
        in_turn.set()
        release_turn.wait(10)
        return ManagedTurn(ok=True, workspace_view={})

    session = _session(handle_turn, watchdog=watchdog)
    session._lock.acquire()  # e.g. a stop requester holding the serving lock
    waiter = threading.Thread(target=_submit, args=(session, "queued"))
    waiter.start()
    try:
        clock.advance(1000)  # a long wait for the lock, no turn served
        assert watchdog.check() is None
    finally:
        session._lock.release()
    assert in_turn.wait(5)
    # The serving window opened when the lock was acquired, not when the
    # caller began waiting 1000 s earlier.
    assert watchdog.check() is None
    clock.advance(299)
    assert watchdog.check() is None
    release_turn.set()
    waiter.join(5)
    assert events == []


# -- dead endpoint thread -------------------------------------------------------


def test_dead_endpoint_thread_is_reported_and_close_is_not() -> None:
    manifest = resolve_proof_tool_contract("l1_goal_projection")
    session = _session(lambda _raw, _deadline: ManagedTurn(ok=True, workspace_view={}))
    endpoint = ProofToolEndpointServer(
        session=session,
        manifest=manifest,
        token="token",
    )
    clock = FakeClock()
    watchdog, _boundaries, events = _watchdog(
        clock,
        endpoint_alive=endpoint.serving_thread_alive,
    )
    assert endpoint.serving_thread_alive() is None  # not started
    endpoint.start()
    try:
        assert endpoint.serving_thread_alive() is True
        assert watchdog.check() is None
        # Stop the accept loop behind the endpoint's back: the socket stays
        # bound but nothing serves it any more.
        endpoint._httpd.shutdown()
        endpoint._thread.join(5)
        assert endpoint.serving_thread_alive() is False
        record = watchdog.check()
        assert record is not None
        assert watchdog.check() is None
    finally:
        endpoint.close()
    assert endpoint.serving_thread_alive() is None
    assert events == [record]
    assert record["stall_kind"] == "endpoint_thread_dead"
    assert record["turn_index"] is None


def test_closed_endpoint_never_reads_as_dead() -> None:
    manifest = resolve_proof_tool_contract("l1_goal_projection")
    session = _session(lambda _raw, _deadline: ManagedTurn(ok=True, workspace_view={}))
    endpoint = ProofToolEndpointServer(session=session, manifest=manifest, token="t")
    clock = FakeClock()
    watchdog, _boundaries, events = _watchdog(
        clock,
        endpoint_alive=endpoint.serving_thread_alive,
    )
    endpoint.start()
    endpoint.close()
    assert watchdog.check() is None
    assert events == []


# -- enforce mode ---------------------------------------------------------------


def test_enforce_closes_agent_emits_then_exits_without_the_session_lock() -> None:
    clock = FakeClock()
    order: list[str] = []
    exits: list[int] = []
    events: list[dict[str, Any]] = []

    def emit(record: dict[str, Any]) -> None:
        order.append("emit")
        events.append(record)

    watchdog = ManagerStallWatchdog(
        node_id="Tree-stall",
        mode="enforce",
        emit=emit,
        close_agent=lambda reason: order.append(f"close:{reason}"),
        boundaries=BackendCallBoundaries(clock=clock),
        exit_fn=lambda code: (order.append("exit"), exits.append(code)),
    )
    in_turn = threading.Event()
    release = threading.Event()

    def handle_turn(_raw, _deadline) -> ManagedTurn:
        in_turn.set()
        release.wait(10)  # a deadlock: the serving lock stays held
        return ManagedTurn(ok=True, workspace_view={})

    session = _session(handle_turn, watchdog=watchdog)
    turn = threading.Thread(target=_submit, args=(session, "stuck"))
    turn.start()
    try:
        assert in_turn.wait(5)
        clock.advance(301)
        record = watchdog.check()  # must complete while the lock is held
        assert session._lock.locked()
        assert watchdog.check() is None  # exit already decided
    finally:
        release.set()
        turn.join(5)

    assert record is not None
    assert [entry.split(":")[0] for entry in order] == ["close", "emit", "exit"]
    assert "manager_idle" in order[0]
    assert exits == [MANAGER_STALL_EXIT_CODE]
    assert events == [record]
    assert record["action"] == "exit"
    assert record["exit_code"] == MANAGER_STALL_EXIT_CODE
    assert watchdog.exit_pending is True


def test_enforce_exit_is_bounded_when_callbacks_hang() -> None:
    clock = FakeClock()
    exits: list[int] = []
    never = threading.Event()
    watchdog = ManagerStallWatchdog(
        node_id="Tree-stall",
        mode="enforce",
        emit=lambda _record: never.wait(),
        close_agent=lambda _reason: never.wait(),
        boundaries=BackendCallBoundaries(clock=clock),
        close_timeout_seconds=0.05,
        emit_timeout_seconds=0.05,
        exit_fn=exits.append,
    )
    watchdog.turn_started(1)
    clock.advance(301)
    started = time.monotonic()
    assert watchdog.check() is not None
    assert time.monotonic() - started < 2.0
    assert exits == [MANAGER_STALL_EXIT_CODE]
    never.set()


_ENFORCE_SCRIPT = textwrap.dedent(
    """
    import json, sys, threading, time
    from pathlib import Path

    from workflow.proof_management.backend_call_boundary import (
        BackendCallBoundaries,
    )
    from workflow.proof_management.types import ManagedTurn
    from workflow.proof_tool.manager_stall_watchdog import ManagerStallWatchdog
    from workflow.proof_tool.proof_tool_contract import resolve_proof_tool_contract
    from workflow.proof_tool.proof_tool_session import ProofToolSession

    out = Path(sys.argv[1])

    def emit(record):
        with (out / "events.jsonl").open("a") as handle:
            handle.write(json.dumps(record) + "\\n")

    def close_agent(reason):
        (out / "closed.txt").write_text(reason)

    watchdog = ManagerStallWatchdog(
        node_id="Tree-enforce",
        mode="enforce",
        emit=emit,
        close_agent=close_agent,
        boundaries=BackendCallBoundaries(),
        idle_cap_seconds=0.2,
        poll_seconds=0.02,
    )

    class Memory:
        def record_turn(self, **kwargs):
            return

    def handle_turn(raw, deadline):
        threading.Event().wait()  # a manager deadlock outside any call

    session = ProofToolSession(
        node_id="Tree-enforce",
        manifest=resolve_proof_tool_contract("l1_goal_projection"),
        handle_turn=handle_turn,
        memory=Memory(),
        response_renderer=lambda *args: "rendered",
        max_turns=5,
        turn_monitor=watchdog,
    )
    watchdog.start()
    threading.Thread(
        target=session.submit,
        kwargs={
            "call_id": "stuck",
            "raw_arguments": {},
            "absolute_deadline": time.time() + 3600,
        },
        daemon=True,
    ).start()
    time.sleep(30)
    print("watchdog did not exit", flush=True)
    sys.exit(0)
    """
)


def test_enforce_mode_exits_the_process_with_the_dedicated_code(
    tmp_path: Path,
) -> None:
    completed = subprocess.run(
        [sys.executable, "-c", _ENFORCE_SCRIPT, str(tmp_path)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert completed.returncode == MANAGER_STALL_EXIT_CODE, completed.stderr
    assert "watchdog did not exit" not in completed.stdout
    records = [
        json.loads(line)
        for line in (tmp_path / "events.jsonl").read_text().splitlines()
    ]
    assert len(records) == 1
    assert records[0]["stall_kind"] == "manager_idle"
    assert records[0]["exit_code"] == MANAGER_STALL_EXIT_CODE
    assert "manager_idle" in (tmp_path / "closed.txt").read_text()


# -- runtime wiring ---------------------------------------------------------------


class _Exited(Exception):
    pass


def test_runtime_never_returns_a_result_after_an_enforced_stall(tmp_path) -> None:
    from workflow.node.proof_node_runtime import ProofNodeRuntime
    from workflow.provider.provider_sessions import AgentRunResult

    clock = FakeClock()
    exits: list[int] = []

    def exit_fn(code: int) -> None:
        exits.append(code)
        raise _Exited(code)

    watchdog = ManagerStallWatchdog(
        node_id="Tree-stall",
        mode="enforce",
        emit=lambda _record: None,
        boundaries=BackendCallBoundaries(clock=clock),
        poll_seconds=3600,
        exit_fn=exit_fn,
    )
    runtime = ProofNodeRuntime.__new__(ProofNodeRuntime)
    runtime._stall_watchdog = watchdog

    def serve() -> AgentRunResult:
        # The watchdog thread decides to exit while the main thread is still
        # serving; in production its os._exit would win this race.
        watchdog.turn_started(1)
        clock.advance(301)
        with pytest.raises(_Exited):
            watchdog.check()
        return AgentRunResult(text="give up", session_id="s", returncode=0)

    runtime._serve = serve
    with pytest.raises(_Exited):
        runtime.run()
    assert exits == [MANAGER_STALL_EXIT_CODE, MANAGER_STALL_EXIT_CODE]


_RUNTIME_POST_RUN_SCRIPT = textwrap.dedent(
    """
    import sys, threading, time
    from pathlib import Path

    from workflow.node.proof_node_runtime import ProofNodeRuntime
    from workflow.proof_management.backend_call_boundary import (
        BackendCallBoundaries,
    )
    from workflow.proof_tool.manager_stall_watchdog import ManagerStallWatchdog
    from workflow.proof_tool.proof_tool_contract import resolve_proof_tool_contract
    from workflow.proof_tool.proof_tool_session import ProofToolSession

    out = Path(sys.argv[1])
    runtime = ProofNodeRuntime.__new__(ProofNodeRuntime)
    runtime.run_dir = out
    watchdog = ManagerStallWatchdog(
        node_id="Tree-post-run",
        mode="enforce",
        emit=runtime._record_manager_stall,
        close_agent=lambda reason: (out / "closed.txt").write_text(reason),
        boundaries=BackendCallBoundaries(),
        idle_cap_seconds=0.3,
        poll_seconds=0.02,
    )

    class Memory:
        def record_turn(self, **kwargs):
            return

    def handle_turn(raw, deadline):
        threading.Event().wait()  # the stalled turn keeps the serving lock

    runtime.tool_session = ProofToolSession(
        node_id="Tree-post-run",
        manifest=resolve_proof_tool_contract("l1_goal_projection"),
        handle_turn=handle_turn,
        memory=Memory(),
        response_renderer=lambda *args: "rendered",
        max_turns=5,
        turn_monitor=watchdog,
    )
    runtime._stall_watchdog = watchdog

    def serve():
        threading.Thread(
            target=runtime.tool_session.submit,
            kwargs={
                "call_id": "stuck",
                "raw_arguments": {},
                "absolute_deadline": time.time() + 3600,
            },
            daemon=True,
        ).start()
        time.sleep(0.05)
        # The provider has returned; the runtime's post-run read waits on the
        # serving lock that the stalled turn still holds.
        return runtime.tool_session.unhealthy_reason

    runtime._serve = serve
    runtime.run()
    print("runtime returned", flush=True)
    sys.exit(0)
    """
)


def test_post_run_lock_read_behind_a_stalled_turn_exits_for_respawn(
    tmp_path: Path,
) -> None:
    completed = subprocess.run(
        [sys.executable, "-c", _RUNTIME_POST_RUN_SCRIPT, str(tmp_path)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert completed.returncode == MANAGER_STALL_EXIT_CODE, completed.stderr
    assert "runtime returned" not in completed.stdout
    audit = (tmp_path / "proof_node_manager_audit.jsonl").read_text().splitlines()
    assert [json.loads(line)["stall_kind"] for line in audit] == ["manager_idle"]
    assert "exiting with code 75" in completed.stderr.splitlines()[-1]
    assert (tmp_path / "closed.txt").exists()


def test_runtime_returns_normally_when_no_stall(tmp_path) -> None:
    from workflow.node.proof_node_runtime import ProofNodeRuntime
    from workflow.provider.provider_sessions import AgentRunResult

    watchdog = ManagerStallWatchdog(
        node_id="Tree-stall",
        mode="enforce",
        emit=lambda _record: None,
        boundaries=BackendCallBoundaries(clock=FakeClock()),
        poll_seconds=3600,
        exit_fn=lambda code: pytest.fail("no stall, no exit"),
    )
    runtime = ProofNodeRuntime.__new__(ProofNodeRuntime)
    runtime._stall_watchdog = watchdog
    expected = AgentRunResult(text="done", session_id="s", returncode=0)
    runtime._serve = lambda: expected
    assert runtime.run() is expected
    assert watchdog._thread is not None and not watchdog._thread.is_alive()


def test_runtime_stall_record_goes_to_the_manager_audit_and_stderr(
    tmp_path, capsys
) -> None:
    from workflow.node.proof_node_runtime import ProofNodeRuntime

    runtime = ProofNodeRuntime.__new__(ProofNodeRuntime)
    runtime.run_dir = tmp_path
    audit = tmp_path / "proof_node_manager_audit.jsonl"
    audit.write_text(json.dumps({"kind": "agent_intent.handled"}) + "\n")
    record = {
        "kind": MANAGER_STALL_EVENT_KIND,
        "node": "Tree-stall",
        "action": "exit",
        "exit_code": MANAGER_STALL_EXIT_CODE,
        "stall_kind": "manager_idle",
        "where": {"frame": "workflow/x.py:3 in f"},
        "turn_index": 4,
        "elapsed_seconds": 301.0,
        "cap_seconds": 300.0,
    }
    runtime._record_manager_stall(record)
    lines = audit.read_text().splitlines()
    assert [json.loads(line)["kind"] for line in lines] == [
        "agent_intent.handled",
        MANAGER_STALL_EVENT_KIND,
    ]
    err = capsys.readouterr().err
    assert err.strip() == stall_headline(record)
    assert "exiting with code 75" in err and "manager_idle in turn 4" in err


def test_append_audit_record_creates_the_file(tmp_path) -> None:
    path = tmp_path / "nested" / "audit.jsonl"
    append_audit_record(path, {"kind": "a"})
    append_audit_record(path, {"kind": "b"})
    assert [json.loads(x)["kind"] for x in path.read_text().splitlines()] == [
        "a",
        "b",
    ]


def test_stall_headline_names_the_action_and_location() -> None:
    report = stall_headline({
        "action": "report",
        "stall_kind": "backend_call_overrun",
        "turn_index": 2,
        "elapsed_seconds": 211.0,
        "cap_seconds": 210.0,
        "where": {"backend_call": "commit_tactic", "frame": "x.py:1 in f"},
    })
    assert report.startswith("managed worker: manager stall watchdog (report only)")
    assert "backend_call_overrun in turn 2 after 211.0s (cap 210.0s)" in report
    assert report.endswith("at commit_tactic")
    exiting = stall_headline({
        "action": "exit",
        "exit_code": MANAGER_STALL_EXIT_CODE,
        "stall_kind": "endpoint_thread_dead",
        "where": {"component": "proof_tool_endpoint"},
    })
    assert "(exiting with code 75)" in exiting
    assert exiting.endswith("at proof_tool_endpoint")
