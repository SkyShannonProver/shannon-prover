"""Task #5: MCP stdio-spawn readiness watchdog + auto-relaunch.

Claude Code intermittently fails to spawn the per-node `proof_node_manager`
stdio MCP server. When it does, no `mcp_debug.jsonl` is ever written, the agent
fails open with only generic harness tools, and the run dies at turn 0 with
`TOOL_BOUNDARY_MISSING` — a wasted slot. The readiness watchdog detects the
flake (no `server_start` event within the window while the process is alive),
kills the doomed subprocess, and flags `mcp_failed_to_start` so the runtime can
relaunch a fresh Claude process against the still-running manager bridge.
"""
from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from workflow.proof_node_runtime import (  # noqa: E402
    ClaudeAgentSession,
    _mcp_server_started,
)


# --------------------------------------------------------- readiness signal ---

def test_server_started_missing_file_is_false(tmp_path):
    assert _mcp_server_started(tmp_path / "absent.jsonl") is False


def test_server_started_without_event_is_false(tmp_path):
    p = tmp_path / "mcp_debug.jsonl"
    p.write_text('{"event": "message_in", "method": "initialize"}\n')
    assert _mcp_server_started(p) is False


def test_server_started_with_event_is_true(tmp_path):
    p = tmp_path / "mcp_debug.jsonl"
    p.write_text(
        '{"event": "server_start", "host": "127.0.0.1", "port": 0}\n'
        '{"event": "message_in", "method": "initialize"}\n'
    )
    assert _mcp_server_started(p) is True


# ------------------------------------------------------------- the watchdog ---

class _FakeProc:
    """Stands in for a Popen: alive until terminate()/kill()."""

    def __init__(self, *, exited: bool = False) -> None:
        self._rc: int | None = 0 if exited else None
        self.terminated = False
        self.killed = False

    def poll(self):
        return self._rc

    def terminate(self):
        self.terminated = True
        self._rc = -15

    def kill(self):
        self.killed = True
        self._rc = -9

    def wait(self, timeout=None):
        return self._rc


def _session() -> tuple[ClaudeAgentSession, list]:
    events: list = []
    s = ClaudeAgentSession(
        model="m", source_file="f.ec", session_tag="unit",
        project_root=ROOT, emit=events.append,
    )
    return s, events


def test_watchdog_kills_when_server_never_starts(tmp_path):
    s, events = _session()
    s.proc = _FakeProc()  # alive, never writes server_start
    s.mcp_failed_to_start = False
    s._watch_mcp_readiness(tmp_path / "never.jsonl", timeout_s=0.1)
    assert s.mcp_failed_to_start is True
    assert s.proc.terminated is True
    assert any(e.get("mcp_spawn_failed") for e in events)


def test_watchdog_leaves_healthy_server_alone(tmp_path):
    s, events = _session()
    s.proc = _FakeProc()
    p = tmp_path / "mcp_debug.jsonl"
    p.write_text('{"event": "server_start"}\n')  # server is up
    s._watch_mcp_readiness(p, timeout_s=0.1)
    assert s.mcp_failed_to_start is False
    assert s.proc.terminated is False
    assert not any(e.get("mcp_spawn_failed") for e in events)


def test_watchdog_server_starts_midway_is_not_killed(tmp_path):
    s, _ = _session()
    s.proc = _FakeProc()
    p = tmp_path / "mcp_debug.jsonl"

    def _late_start():
        time.sleep(0.15)
        p.write_text('{"event": "server_start"}\n')

    t = threading.Thread(target=_late_start, daemon=True)
    t.start()
    s._watch_mcp_readiness(p, timeout_s=1.0)
    t.join(timeout=2)
    assert s.mcp_failed_to_start is False
    assert s.proc.terminated is False


def test_watchdog_ignores_already_exited_proc(tmp_path):
    s, _ = _session()
    s.proc = _FakeProc(exited=True)  # exited on its own
    s._watch_mcp_readiness(tmp_path / "never.jsonl", timeout_s=0.1)
    assert s.mcp_failed_to_start is False
    assert s.proc.terminated is False
