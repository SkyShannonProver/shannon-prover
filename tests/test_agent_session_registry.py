"""Regression tests: every Claude session a prover node spawns (initial +
ctx-respawn continuations) must land in the canonical per-node registry
(``node_memory/<tree>/agent_sessions.jsonl``), flow into the run manifest
(``agent_session_ids.json``), and be counted exactly once by
``eval_suite.metrics``.

The bug these pin: ``ClaudeAgentSession.session_id`` was sticky across
generations, so a continuation session's id was only ever captured from a
``result`` event — a generation killed at the wall deadline (or by the
watermark terminate) vanished from every registry, manifest, and metric.
"""
from __future__ import annotations

import json
from pathlib import Path

import _pathsetup  # noqa: F401  (repo root on sys.path)

import workflow.proof_node_runtime as M
from workflow.proof_node_runtime import ClaudeAgentSession, NodeMemory
from workflow.tree.supervisor import _session_records_for_nodes


# --- fakes -------------------------------------------------------------------

class _FakeStderr:
    def read(self) -> str:
        return ""


class _FakeProc:
    """Just enough of Popen for ClaudeAgentSession.run()'s stream loop."""

    def __init__(self, lines: list[str]):
        self.stdout = iter(lines)
        self.stderr = _FakeStderr()
        self.returncode = 0

    def wait(self) -> int:
        return 0

    def poll(self) -> int:
        return 0

    def terminate(self) -> None:
        pass


def _stream(session_id: str, *, with_result: bool) -> list[str]:
    lines = [
        json.dumps({"type": "system", "subtype": "init", "session_id": session_id}),
        json.dumps({
            "type": "assistant",
            "session_id": session_id,
            "message": {"usage": {"input_tokens": 5}, "content": []},
        }),
    ]
    if with_result:
        lines.append(json.dumps({
            "type": "result", "result": "done", "session_id": session_id,
        }))
    return [line + "\n" for line in lines]


def _agent(tmp_path: Path, on_session_id) -> ClaudeAgentSession:
    return ClaudeAgentSession(
        model="test-model",
        source_file="target.ec",
        session_tag="test_tag",
        project_root=tmp_path,
        on_session_id=on_session_id,
    )


class _FakeTracker:
    def __init__(self, session_ids: list[str], *, committed: int = 3):
        self.session_ids = list(session_ids)
        self.session_id = session_ids[0] if session_ids else ""
        self.completion_candidate_ready = False
        self.committed_count = committed
        self.max_committed_count_seen = committed


class _FakeNode:
    def __init__(self, node_id: str, session_ids: list[str]):
        self.node_id = node_id
        self.tracker = _FakeTracker(session_ids)


# --- 1. initial session + one respawn: registry holds both ids --------------

def test_initial_and_respawn_sessions_both_registered(monkeypatch, tmp_path):
    memory = NodeMemory(tmp_path, "0.0")
    agent = _agent(
        tmp_path,
        lambda sid: memory.record_agent_session(sid, cwd=tmp_path),
    )

    # Generation 1 is terminated by the watermark: NO result event.
    monkeypatch.setattr(
        M.subprocess, "Popen",
        lambda *a, **k: _FakeProc(_stream("sess-initial", with_result=False)),
    )
    result1 = agent.run("prompt")
    assert result1.session_id == "sess-initial"

    # Generation 2 (the continuation) runs to a clean result.
    monkeypatch.setattr(
        M.subprocess, "Popen",
        lambda *a, **k: _FakeProc(_stream("sess-continuation", with_result=True)),
    )
    result2 = agent.run("prompt")
    # The stale generation-1 id must not mask the continuation's id.
    assert result2.session_id == "sess-continuation"

    rows = [
        json.loads(line)
        for line in memory.agent_sessions.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert [r["session_id"] for r in rows] == ["sess-initial", "sess-continuation"]


# --- 2. duplicate notification: registered once ------------------------------

def test_duplicate_registration_is_idempotent(tmp_path):
    memory = NodeMemory(tmp_path, "0.0")
    memory.record_agent_session("sess-cont", cwd=tmp_path)
    memory.record_agent_session("sess-cont", cwd=tmp_path)
    rows = [
        json.loads(line)
        for line in memory.agent_sessions.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert [r["session_id"] for r in rows] == ["sess-cont"]


def test_agent_notifies_each_session_id_once(monkeypatch, tmp_path):
    seen: list[str] = []
    agent = _agent(tmp_path, seen.append)
    # The same id arrives on the init event, an assistant event, AND the result
    # event — the hook must still fire once.
    monkeypatch.setattr(
        M.subprocess, "Popen",
        lambda *a, **k: _FakeProc(_stream("sess-a", with_result=True)),
    )
    agent.run("prompt")
    assert seen == ["sess-a"]


# --- 3. iteration manifest carries initial + continuation --------------------

def test_manifest_records_include_continuation():
    winner = _FakeNode("0.0", ["sess-initial", "sess-continuation"])
    records = _session_records_for_nodes([winner], winner=winner)
    assert [r["session_id"] for r in records] == [
        "sess-initial", "sess-continuation",
    ]
    assert [r["session_index"] for r in records] == [0, 1]
    assert [r["continuation"] for r in records] == [False, True]
    assert all(r["node"] == "Tree-0.0" for r in records)
    assert all(r["winner"] for r in records)
    # The exact shape prover.py serializes into agent_session_ids.json.
    manifest = {
        "schema_version": 1,
        "kind": "agent_session_ids",
        "sessions": records,
    }
    ids = {s["session_id"] for s in manifest["sessions"]}
    assert ids == {"sess-initial", "sess-continuation"}


def test_manifest_records_dedupe_repeated_ids():
    node = _FakeNode("0.0", ["sess-a", "sess-a", "sess-b"])
    records = _session_records_for_nodes([node], winner=node)
    assert [r["session_id"] for r in records] == ["sess-a", "sess-b"]


# --- 6. no-respawn: single-session behavior unchanged ------------------------

def test_manifest_records_single_session_unchanged():
    winner = _FakeNode("0.0", ["sess-only"])
    other = _FakeNode("0.1", ["sess-other"])
    records = _session_records_for_nodes([winner, other], winner=winner)
    assert [r["session_id"] for r in records] == ["sess-only", "sess-other"]
    assert [r["winner"] for r in records] == [True, False]
    assert all(r["session_index"] == 0 and r["continuation"] is False
               for r in records)
    # Legacy tracker without session_ids (e.g. a stub) still yields its
    # single session_id.
    legacy = _FakeNode("0.2", [])
    legacy.tracker.session_id = "sess-legacy"
    legacy.tracker.session_ids = []
    records = _session_records_for_nodes([legacy], winner=legacy)
    assert [r["session_id"] for r in records] == ["sess-legacy"]


def test_tracker_captures_full_session_chain(tmp_path):
    from workflow.tree.trackers import _ProverTracker

    tracker = _ProverTracker(proc=object(), name="Tree-0.0", cwd=str(tmp_path))
    for sid in ("sess-initial", "sess-initial", "sess-continuation"):
        tracker._process_line(json.dumps({
            "type": "system", "session_id": sid,
        }))
    assert tracker.session_id == "sess-initial"
    assert tracker.session_ids == ["sess-initial", "sess-continuation"]
