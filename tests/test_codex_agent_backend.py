from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import _pathsetup  # noqa: F401

import workflow.proof_node_runtime as runtime_module
from workflow.proof_node_runtime import (
    CodexAgentSession,
    NodeMemory,
    ProofNodeRuntime,
    agent_session_class,
)
from workflow.schemas.config import (
    DEFAULT_CLAUDE_MODEL,
    DEFAULT_CODEX_MODEL,
    ProverConfig,
)


class _FakeStdin:
    def __init__(self) -> None:
        self.text = ""
        self.closed = False

    def write(self, value: str) -> None:
        self.text += value

    def close(self) -> None:
        self.closed = True


class _FakeStderr:
    def read(self) -> str:
        return ""


class _FakeProc:
    def __init__(self, lines: list[str]) -> None:
        self.stdin = _FakeStdin()
        self.stdout = iter(lines)
        self.stderr = _FakeStderr()
        self.returncode = 0

    def wait(self, timeout: float | None = None) -> int:
        return self.returncode

    def poll(self) -> int:
        return self.returncode

    def terminate(self) -> None:
        self.returncode = -15

    def kill(self) -> None:
        self.returncode = -9


def _mcp_config(tmp_path: Path) -> Path:
    path = tmp_path / "mcp.json"
    path.write_text(
        json.dumps({
            "mcpServers": {
                "proof_node_manager": {
                    "type": "stdio",
                    "command": "/usr/bin/python3",
                    "args": ["-m", "workflow.proof_node_mcp_server", "--port", "1234"],
                    "env": {
                        "PYTHONPATH": str(tmp_path),
                        "SHANNON_SURFACE_PROFILE": "l4_proof_state_compiler_v2_operation_binding_repair",
                    },
                }
            }
        }),
        encoding="utf-8",
    )
    return path


def test_codex_backend_has_provider_specific_default_model() -> None:
    default = ProverConfig()
    assert default.agent_backend == "codex"
    assert default.model == DEFAULT_CODEX_MODEL
    codex = ProverConfig(agent_backend="codex")
    assert codex.agent_backend == "codex"
    assert codex.model == DEFAULT_CODEX_MODEL
    assert agent_session_class("codex") is CodexAgentSession
    claude = ProverConfig(agent_backend="claude")
    assert claude.model == DEFAULT_CLAUDE_MODEL


def test_codex_command_is_read_only_and_requires_private_mcp(tmp_path: Path) -> None:
    agent = CodexAgentSession(
        model="gpt-test",
        effort="high",
        source_file="target.ec",
        session_tag="tag",
        project_root=tmp_path,
    )
    command = agent._command(_mcp_config(tmp_path))

    assert command[1:3] == ["exec", "-"]
    assert command[command.index("--model") + 1] == "gpt-test"
    assert command[command.index("--sandbox") + 1] == "read-only"
    assert "--skip-git-repo-check" in command
    assert "--ignore-user-config" in command
    disabled = [
        command[index + 1]
        for index, value in enumerate(command)
        if value == "--disable"
    ]
    assert "standalone_web_search" in disabled
    assert "multi_agent" in disabled
    assert "plugins" in disabled
    overrides = [command[index + 1] for index, value in enumerate(command) if value == "-c"]
    assert "approval_policy=\"never\"" in overrides
    assert "web_search=\"disabled\"" in overrides
    assert "mcp_servers.proof_node_manager.required=true" in overrides
    assert (
        "mcp_servers.proof_node_manager.default_tools_approval_mode=\"approve\""
        in overrides
    )
    assert any(value.startswith("mcp_servers.proof_node_manager.command=") for value in overrides)
    assert any(value.startswith("mcp_servers.proof_node_manager.args=") for value in overrides)
    assert any(value.startswith("mcp_servers.proof_node_manager.tool_timeout_sec=") for value in overrides)

    resume = agent._command(
        _mcp_config(tmp_path), resume_session_id="thread-123"
    )
    assert resume[1:3] == ["exec", "resume"]
    assert resume[-2:] == ["thread-123", "-"]
    assert "--skip-git-repo-check" in resume
    assert "sandbox_mode=\"read-only\"" in resume


def test_codex_uses_outer_eval_confinement_instead_of_nested_sandbox(
    tmp_path: Path,
) -> None:
    agent = CodexAgentSession(
        model="gpt-test",
        effort="high",
        source_file="target.ec",
        session_tag="tag",
        project_root=tmp_path,
        eval_confinement=SimpleNamespace(),
    )

    command = agent._command(_mcp_config(tmp_path))
    assert command[command.index("--sandbox") + 1] == "danger-full-access"
    overrides = [
        command[index + 1]
        for index, value in enumerate(command)
        if value == "-c"
    ]
    assert "approval_policy=\"never\"" in overrides

    resume = agent._command(
        _mcp_config(tmp_path), resume_session_id="thread-confined"
    )
    assert "sandbox_mode=\"danger-full-access\"" in resume
    assert "sandbox_mode=\"read-only\"" not in resume


def test_codex_failure_text_surfaces_jsonl_error(monkeypatch, tmp_path: Path) -> None:
    events = [
        {"type": "thread.started", "thread_id": "thread-err"},
        {
            "type": "error",
            "message": "selected model is not supported by this account",
        },
        {
            "type": "turn.failed",
            "error": {"message": "selected model is not supported by this account"},
        },
    ]
    proc = _FakeProc([json.dumps(event) + "\n" for event in events])
    proc.returncode = 1
    monkeypatch.setattr(runtime_module.subprocess, "Popen", lambda *args, **kwargs: proc)
    agent = CodexAgentSession(
        model="gpt-test",
        effort="low",
        source_file="target.ec",
        session_tag="tag",
        project_root=tmp_path,
    )

    result = agent.run("PROMPT", mcp_config_path=_mcp_config(tmp_path))

    assert result.returncode == 1
    assert "not supported by this account" in result.text


def test_codex_jsonl_is_normalized_for_existing_auditors(monkeypatch, tmp_path: Path) -> None:
    events = [
        {"type": "thread.started", "thread_id": "thread-123"},
        {
            "type": "item.started",
            "item": {
                "id": "cmd-1",
                "type": "command_execution",
                "command": "rg lemma target.ec",
                "status": "in_progress",
            },
        },
        {
            "type": "item.completed",
            "item": {
                "id": "cmd-1",
                "type": "command_execution",
                "command": "rg lemma target.ec",
                "aggregated_output": "lemma target",
                "status": "completed",
            },
        },
        {
            "type": "item.completed",
            "item": {
                "id": "msg-1",
                "type": "agent_message",
                "text": "proof node finished",
            },
        },
        {"type": "turn.completed", "usage": {"input_tokens": 10, "output_tokens": 3}},
    ]
    proc = _FakeProc([json.dumps(event) + "\n" for event in events])
    monkeypatch.setattr(runtime_module.subprocess, "Popen", lambda *args, **kwargs: proc)
    emitted: list[dict] = []
    session_ids: list[str] = []
    agent = CodexAgentSession(
        model="gpt-test",
        effort="high",
        source_file="target.ec",
        session_tag="tag",
        project_root=tmp_path,
        emit=emitted.append,
        on_session_id=session_ids.append,
    )

    result = agent.run(
        "MAIN PROMPT",
        system_prompt="SYSTEM ANCHOR",
        mcp_config_path=_mcp_config(tmp_path),
    )

    assert result.session_id == "thread-123"
    assert result.text == "proof node finished"
    assert session_ids == ["thread-123"]
    assert proc.stdin.text == "SYSTEM ANCHOR\n\nMAIN PROMPT"
    assert proc.stdin.closed is True
    tool_use = next(
        event for event in emitted
        if event.get("type") == "assistant"
        and event.get("message", {}).get("content", [{}])[0].get("type") == "tool_use"
    )
    block = tool_use["message"]["content"][0]
    assert block["name"] == "Bash"
    assert block["input"]["command"] == "rg lemma target.ec"
    assert any(event.get("type") == "user" for event in emitted)
    assert all(
        event.get("agent_backend") == "codex"
        for event in emitted
        if event.get("session_id")
    )


def test_codex_session_registry_does_not_invent_claude_transcript(tmp_path: Path) -> None:
    memory = NodeMemory(tmp_path, "Tree-0.0")
    memory.record_agent_session(
        "thread-123", cwd=tmp_path, agent_backend="codex"
    )
    record = json.loads(memory.agent_sessions.read_text(encoding="utf-8"))
    assert record["agent_backend"] == "codex"
    assert "transcript_path" not in record


def test_codex_continuation_waits_for_manager_finish() -> None:
    runtime = ProofNodeRuntime.__new__(ProofNodeRuntime)
    runtime.bridge = SimpleNamespace(finish_accepted=False)
    runtime.manager = SimpleNamespace(
        latest_view={"proof_status": {"status": "candidate_closed"}}
    )
    assert runtime._proof_is_closed() is False

    runtime.bridge.finish_accepted = True
    assert runtime._proof_is_closed() is True
