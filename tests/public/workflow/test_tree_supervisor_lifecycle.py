"""Tree supervisor process lifecycle: spawn failures, kills, and finalization.

These tests drive the real ``NodeSupervisor`` methods (and, where the bug
lives in the monitor loop, the real ``run_tree_prover``) against fake workers
backed by real OS pipes. Session state is injected through crafted
``WorkflowSessionSnapshot`` values; no EasyCrypt, model, or network is used.
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

import workflow.tree.supervisor as sup
import workflow.tree.trackers as trk
from workflow.proc_lifecycle import WORKER_PGID_MANIFEST_ENV
from workflow.proof_management.lineage import LemmaLineageStore
from workflow.tree.payload_audit import PayloadAuditRecorder
from workflow.tree.result import TreeRunResult
from workflow.tree.session_observer import WorkflowSessionSnapshot


class _FakeWorker:
    """A ``Popen`` stand-in whose stdout is a real pipe.

    The tracker reads it exactly as it reads a worker. The process "exits"
    when ``exit`` closes the write end and fixes the return code; ``wait``
    on a live worker times out, as a real hung worker would.
    """

    def __init__(self, lines=(), *, alive=True, exit_code=0):
        read_fd, write_fd = os.pipe()
        self.stdout = os.fdopen(read_fd, "r")
        self.stderr = None
        self._writer = os.fdopen(write_fd, "w")
        self.pid = -1
        self.returncode = None
        self.write(*lines)
        if not alive:
            self.exit(exit_code)

    def write(self, *lines):
        for line in lines:
            self._writer.write(line + "\n")
        self._writer.flush()

    def exit(self, code=0):
        if self._writer is not None:
            self._writer.close()
            self._writer = None
        if self.returncode is None:
            self.returncode = code

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        if self.returncode is None:
            raise subprocess.TimeoutExpired("fake-worker", timeout)
        return self.returncode

    def terminate(self):
        self.exit(-15)

    def kill(self):
        self.exit(-9)


def _result_line(text="done"):
    return json.dumps({"type": "result", "result": text, "turns": 1})


def _snapshot(session_dir, tactics, **overrides):
    values = {
        "session_dir": str(session_dir),
        "exists": True,
        "ok": True,
        "status": "open",
        "history_exists": True,
        "history_tactics": list(tactics),
        "tactic_count": len(tactics),
    }
    values.update(overrides)
    return WorkflowSessionSnapshot(**values)


@pytest.fixture
def terminated(monkeypatch):
    """Record every process-tree termination instead of signalling."""
    calls = []

    def _terminate(proc, **_kwargs):
        calls.append(proc)
        proc.terminate()

    monkeypatch.setattr(sup, "_terminate_process_tree", _terminate)
    monkeypatch.delenv(WORKER_PGID_MANIFEST_ENV, raising=False)
    return calls


# --- Bare supervisor: the tick methods without the monitor loop -------------


def _bare_supervisor(tmp_path, **kwargs):
    supervisor = sup.NodeSupervisor(
        lambda *_args, **_kwargs: ["worker"],
        str(tmp_path),
        **kwargs,
    )
    supervisor.logger = logging.getLogger("test.tree_supervisor_lifecycle")
    supervisor.lineage = LemmaLineageStore(run_dir=None)
    supervisor.payload_audit = PayloadAuditRecorder(
        kwargs.get("payload_audit_path")
    )
    supervisor.nodes = {}
    supervisor.start_time = time.time()
    supervisor.exhausted_branches = {}
    supervisor._n_active = 0
    return supervisor


class _BareProc:
    def __init__(self, returncode=None):
        self.stdout = None
        self.stderr = None
        self.pid = -1
        self.returncode = returncode

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        if self.returncode is None:
            raise subprocess.TimeoutExpired("bare", timeout)
        return self.returncode

    def terminate(self):
        if self.returncode is None:
            self.returncode = -15


def _add_node(supervisor, node_id, *, committed, proc=None, depth=0):
    proc = proc or _BareProc()
    session_tag = supervisor._session_tag(node_id)
    tracker = trk._TreeProverTracker(
        proc,
        f"Tree-{node_id}",
        supervisor.cwd,
        session_tag=session_tag,
    )
    tactics = [f"tac{index}." for index in range(committed)]
    tracker.session_snapshot = _snapshot(f".ec_session_{session_tag}", tactics)
    tracker.accepted_tactic_texts = list(tactics)
    tracker.accepted_tactics = committed
    tracker.last_accept_time = time.time() - 10_000
    node = sup.ProofTreeNode(
        node_id=node_id,
        parent_id="root",
        tracker=tracker,
        replay_prefix=[],
        depth=depth,
        spawn_time=time.time() - 10_000,
    )
    supervisor.nodes[node_id] = node
    return node


def test_progress_gap_rebalance_does_not_kill_a_second_node(tmp_path, terminated):
    """At capacity, the progress-gap kill already frees the slot the
    rebalance child needs; no other healthy node may be killed for it."""
    supervisor = _bare_supervisor(tmp_path, max_concurrent=6)  # capped to 4
    leader = _add_node(supervisor, "0.0", committed=10)
    laggard = _add_node(supervisor, "0.1", committed=1)
    steady = [
        _add_node(supervisor, "0.2", committed=8),
        _add_node(supervisor, "0.3", committed=8),
    ]
    spawned = []

    def _spawn_node(node_id, parent_id, *_args, **_kwargs):
        spawned.append(node_id)
        return _add_node(supervisor, node_id, committed=10, depth=1)

    supervisor._spawn_node = _spawn_node
    active = supervisor._active_nodes()
    supervisor._n_active = len(active)

    supervisor._tick_progress_gap(active)

    assert spawned == ["0.0.0"]
    assert terminated == [laggard.tracker.proc]
    assert all(not node.tracker.finished for node in steady)
    assert not leader.tracker.finished
    assert len(supervisor._active_nodes()) == supervisor.max_concurrent


def test_kill_of_an_exited_unpolled_node_releases_its_slot(tmp_path, terminated):
    """A worker can exit between polls. Killing it must still take it out of
    the active set, or the capacity loop picks it forever."""
    supervisor = _bare_supervisor(tmp_path, max_concurrent=1)
    _add_node(supervisor, "0.0", committed=6)
    exited = _add_node(
        supervisor, "0.1", committed=0, proc=_BareProc(returncode=1),
    )

    for _ in range(5):
        if len(supervisor._active_nodes()) <= supervisor.max_concurrent:
            break
        supervisor._kill_least_productive()

    assert len(supervisor._active_nodes()) == 1
    assert exited.tracker.finished
    # It exited on its own: not a supervisor decision, nothing to signal.
    assert exited.tracker.supervisor_killed is False
    assert terminated == []


def _layer3_candidate(supervisor):
    node = _add_node(supervisor, "0.0", committed=3, proc=_BareProc(returncode=1))
    node.tracker.finished = True
    node.tracker.context_respawn_count = 1
    return node


def test_layer3_capsule_selection_failure_consumes_the_one_shot(
    tmp_path, monkeypatch,
):
    monkeypatch.delenv("SHANNON_DISABLE_CTX_RESPAWN", raising=False)
    supervisor = _bare_supervisor(
        tmp_path, payload_audit_path=str(tmp_path / "payload_audit.jsonl"),
    )
    node = _layer3_candidate(supervisor)
    selections = []

    def _select(**kwargs):
        selections.append(kwargs["session_tag"])
        return None

    monkeypatch.setattr(sup, "_layer3_select_capsule", _select)

    assert supervisor._maybe_layer3_crash_respawn(node) is False
    assert supervisor._maybe_layer3_crash_respawn(node) is False
    assert selections == ["prover_tree_0_0"]


def test_layer3_capsule_load_failure_consumes_the_one_shot(tmp_path, monkeypatch):
    monkeypatch.delenv("SHANNON_DISABLE_CTX_RESPAWN", raising=False)
    supervisor = _bare_supervisor(
        tmp_path, payload_audit_path=str(tmp_path / "payload_audit.jsonl"),
    )
    node = _layer3_candidate(supervisor)
    loads = []

    def _load(path):
        loads.append(path)
        raise ValueError("corrupt capsule")

    monkeypatch.setattr(
        sup,
        "_layer3_select_capsule",
        lambda **_kwargs: (tmp_path / "resume.json", "live"),
    )
    monkeypatch.setattr(sup, "_load_resume_capsule", _load)

    for _ in range(3):
        assert supervisor._maybe_layer3_crash_respawn(node) is False
    assert len(loads) == 1


def test_progress_gap_child_bootstrap_failure_is_isolated(tmp_path, terminated):
    """A rebalance child whose bootstrap fails must not escape the tick."""
    audit = tmp_path / "payload_audit.jsonl"
    supervisor = _bare_supervisor(tmp_path, payload_audit_path=str(audit))
    leader = _add_node(supervisor, "0.0", committed=10)
    _add_node(supervisor, "0.1", committed=1)

    def _failing_spawn(node_id, *_args, **_kwargs):
        raise TimeoutError(f"replay budget exhausted for {node_id}")

    supervisor._spawn_node = _failing_spawn
    active = supervisor._active_nodes()
    supervisor._n_active = len(active)

    supervisor._tick_progress_gap(active)

    assert not leader.tracker.finished
    assert supervisor._active_nodes() == [leader]
    records = [json.loads(line) for line in audit.read_text().splitlines()]
    failed = [r for r in records if r["event"] == "child_spawn_failed"]
    assert len(failed) == 1
    assert failed[0]["node"] == "Tree-0.0"
    assert failed[0]["child"] == "Tree-0.0.0"
    assert "TimeoutError" in failed[0]["error"]
    # The failed child's id (and session tag) is never reused.
    assert leader.children == ["0.0.0"]


# --- Real monitor loop -------------------------------------------------------


class _Spawns:
    """Per-node fake workers; ``fail`` maps node ids to the exception the
    managed-session bootstrap raises for them."""

    def __init__(self, *, fail=None, workers=None, on_failure=None):
        self.fail = dict(fail or {})
        self.workers = dict(workers or {})
        self.on_failure = on_failure
        self.built = []

    def build_cmd_fn(self, session_tag, node_id, replay_prefix, **_kwargs):
        self.built.append(node_id)
        if node_id in self.fail:
            if self.on_failure is not None:
                self.on_failure(node_id)
            raise self.fail[node_id]
        return ["fake-worker", "--node", node_id]

    def popen(self, cmd, *_args, **_kwargs):
        node_id = cmd[cmd.index("--node") + 1]
        worker = self.workers.get(node_id)
        if worker is None:
            worker = self.workers[node_id] = _FakeWorker()
        return worker


def _drive(monkeypatch, tmp_path, spawns, *, snapshots=None, **kwargs):
    cwd = tmp_path / "cwd"
    cwd.mkdir(exist_ok=True)
    run_dir = tmp_path / "run"
    run_dir.mkdir(exist_ok=True)
    monkeypatch.setattr(sup.subprocess, "Popen", spawns.popen)
    monkeypatch.setattr(sup.time, "sleep", lambda *_a, **_k: None)
    status_bar = []
    monkeypatch.setattr(sup, "_set_status_bar_active", status_bar.append)
    if snapshots is not None:
        def _session_snapshot(_cwd, session_dir):
            name = Path(str(session_dir or "")).name
            return snapshots.get(name)

        monkeypatch.setattr(trk, "_session_snapshot", _session_snapshot)
    options = {
        "timeout": 600,
        "max_concurrent": 4,
        "initial_provers": 1,
        "check_interval": 0,
        "min_alive_seconds": 0,
        "grace_seconds": 10_000,
        "stuck_idle_seconds": 10_000,
        "stuck_errors": 10_000,
        "source_file": "f.ec",
        "target_lemma": "L",
        "payload_audit_path": str(run_dir / "payload_audit.jsonl"),
    }
    options.update(kwargs)
    result = sup.run_tree_prover(spawns.build_cmd_fn, cwd=str(cwd), **options)
    return result, status_bar


def _audit_events(tmp_path):
    path = tmp_path / "run" / "payload_audit.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_structural_undo_child_bootstrap_failure_keeps_the_run(
    monkeypatch, tmp_path, terminated,
):
    """A structural-undo child whose replay bootstrap fails is one failed
    branch: the run must keep its parent, and the result its session."""
    session = ".ec_session_prover_tree_0_0"
    (tmp_path / "cwd" / session).mkdir(parents=True)
    parent = _FakeWorker()
    snapshots = {
        session: _snapshot(
            session,
            ["proc."],
            latest_transition={"kind": "undo", "tactic": "byequiv."},
        ),
    }

    def _parent_finishes(_node_id):
        parent.write(_result_line("parent report"))
        parent.exit(0)

    spawns = _Spawns(
        fail={"0.0.0": TimeoutError("replay_prefix_aggregate_budget")},
        workers={"0.0": parent},
        on_failure=_parent_finishes,
    )

    result, _ = _drive(
        monkeypatch, tmp_path, spawns,
        snapshots=snapshots,
        structural_undo_spawn_delay_seconds=0,
    )

    assert isinstance(result, TreeRunResult)
    assert result.selected_node_id == "0.0"
    assert result.output_text == "parent report"
    assert result.infrastructure_errors == ()
    assert [Path(path).name for path in result.managed_session_dirs] == [session]
    assert spawns.built == ["0.0", "0.0.0"]
    events = [record["event"] for record in _audit_events(tmp_path)]
    assert events.count("child_spawn_failed") == 1
    assert events[-1] == "run_end"
    assert terminated == []


@pytest.mark.parametrize(
    ("failure", "expected_error"),
    [
        (RuntimeError("bootstrap opened no proof"), "tree search failed"),
        (KeyboardInterrupt("received signal 15"), "tree search interrupted"),
    ],
)
def test_failed_startup_reaps_roots_that_already_started(
    monkeypatch, tmp_path, terminated, failure, expected_error,
):
    first_root = _FakeWorker()
    spawns = _Spawns(fail={"0.1": failure}, workers={"0.0": first_root})

    try:
        result, status_bar = _drive(
            monkeypatch, tmp_path, spawns, initial_provers=2,
        )
    except BaseException as exc:  # KeyboardInterrupt must not end pytest
        pytest.fail(f"startup failure escaped the supervisor: {exc!r}")

    assert terminated == [first_root]
    assert first_root.poll() is not None
    assert any(expected_error in item for item in result.infrastructure_errors)
    assert result.selected_node_id == "0.0"
    assert status_bar == [True, False]


def test_finished_but_alive_worker_is_reaped_and_result_survives(
    monkeypatch, tmp_path, terminated,
):
    """A worker can emit its final result and still be running. It must be
    terminated at the end of the run, and its exit status must not void the
    tree result."""
    lingering = _FakeWorker([_result_line("gave up")])
    spawns = _Spawns(workers={"0.0": lingering})

    result, _ = _drive(monkeypatch, tmp_path, spawns)

    assert terminated == [lingering]
    assert result.selected_node_id == "0.0"
    assert result.output_text == "gave up"
    assert result.returncode == -15


# --- Winner exit -------------------------------------------------------------


def test_winner_exit_keeps_draining_output_beyond_pipe_capacity(tmp_path):
    """A winner that writes more than the pipe holds after it was selected
    must be drained so it can exit on its own, with its final event read."""
    script = (
        "import json, sys\n"
        "for index in range(4000):\n"
        "    print(json.dumps({'type': 'system', 'pad': 'x' * 200, 'i': index}))\n"
        "print(json.dumps({'type': 'result', 'result': 'winner report', 'turns': 9}))\n"
        "sys.stdout.flush()\n"
    )
    proc = subprocess.Popen(
        [sys.executable, "-c", script],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        supervisor = _bare_supervisor(tmp_path)
        node = _add_node(supervisor, "0.0", committed=3, proc=proc)

        started = time.time()
        supervisor._await_winner_exit(node, timeout=60)

        assert time.time() - started < 30
        assert proc.returncode == 0
        assert node.tracker.result_text == "winner report"
        assert node.tracker.manager_turns == 9
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()


# --- Tracker stdout reads ----------------------------------------------------


def _turn_line(index):
    return json.dumps({
        "type": "system",
        "kind": "manager_turn.completed",
        "turn_index": index,
    })


def test_poll_processes_every_line_that_arrived_together(tmp_path):
    """Lines delivered in one write must all be handled by one poll, not
    left in a read buffer until the worker happens to write again."""
    worker = _FakeWorker()
    tracker = trk._TreeProverTracker(worker, "Tree-0.0", str(tmp_path))

    worker.write(_turn_line(1), _turn_line(2), _turn_line(3))
    tracker.poll_lines()

    assert tracker.manager_turns == 3
    assert tracker.finished is False


def test_poll_joins_a_line_split_across_reads(tmp_path):
    worker = _FakeWorker()
    tracker = trk._TreeProverTracker(worker, "Tree-0.0", str(tmp_path))
    line = _result_line("final report")

    worker._writer.write(line[:10])
    worker._writer.flush()
    tracker.poll_lines()
    assert tracker.result_text == ""

    worker._writer.write(line[10:])  # the exit flushes the unterminated tail
    worker.exit(0)
    tracker.poll_lines()

    assert tracker.result_text == "final report"
    assert tracker.finished is True
