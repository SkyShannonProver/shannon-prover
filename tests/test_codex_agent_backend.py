from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import _pathsetup  # noqa: F401

import workflow.provider.provider_sessions as runtime_module
from workflow.node.node_memory import NodeMemory
from workflow.provider.provider_sessions import (
    CodexAgentSession,
    agent_session_class,
)
from workflow.proof_tool.proof_tool_contract import resolve_proof_tool_contract
from workflow.proof_tool.proof_tool_launch import (
    CodexCapabilities,
    ProofMcpLaunchSpec,
    ProofToolTimingBudget,
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

    def poll(self) -> int | None:
        # Model a live child while the readiness watchdog races the stream
        # consumer. ``wait`` still supplies the final provider exit code.
        return None

    def terminate(self) -> None:
        self.returncode = -15

    def kill(self) -> None:
        self.returncode = -9


_REQUIRED_EXEC_OPTIONS = frozenset({
    "--config",
    "--disable",
    "--ignore-user-config",
    "--json",
    "--sandbox",
    "--strict-config",
})
_REQUIRED_RESUME_OPTIONS = frozenset({
    "--config",
    "--disable",
    "--ignore-user-config",
    "--json",
    "--strict-config",
})
_TEST_OPTIONAL_FEATURES = frozenset({
    "multi_agent",
    "plugins",
    "shell_tool",
    "standalone_web_search",
    "unified_exec",
    "view_image",
})


def _capabilities(
    *,
    version: str = "codex-cli arbitrary-test-build",
    features: frozenset[str] = _TEST_OPTIONAL_FEATURES,
) -> CodexCapabilities:
    return CodexCapabilities(
        binary="codex",
        version=version,
        features=features,
        exec_options=_REQUIRED_EXEC_OPTIONS,
        resume_options=_REQUIRED_RESUME_OPTIONS,
    )


def _launch_spec(tmp_path: Path) -> ProofMcpLaunchSpec:
    private_dir = tmp_path / "runtime-private"
    private_dir.mkdir(parents=True, exist_ok=True)
    return ProofMcpLaunchSpec(
        manifest=resolve_proof_tool_contract(None),
        endpoint_host="127.0.0.1",
        endpoint_port=43210,
        endpoint_token="private-token",
        private_dir=private_dir,
        timing=ProofToolTimingBudget.from_manager_budget(
            10,
            startup_seconds=1,
            transport_margin_seconds=2,
        ),
        python_executable="/managed/python",
    )


class _ReadinessFake:
    def __init__(self) -> None:
        self.issued: list[str] = []
        self.waited: list[str] = []

    def issue(self, launch_id: str) -> None:
        self.issued.append(launch_id)

    def wait(
        self,
        launch_id: str,
        _timeout: float,
    ) -> object | None:
        self.waited.append(launch_id)
        if self.issued and self.issued[-1] == launch_id:
            return SimpleNamespace(
                launch_id=launch_id,
                negotiated_protocol="2025-06-18",
            )
        return None


def _agent(
    tmp_path: Path,
    **kwargs,
) -> tuple[CodexAgentSession, ProofMcpLaunchSpec, _ReadinessFake]:
    spec = _launch_spec(tmp_path)
    readiness = _ReadinessFake()
    arguments = {
        "model": "gpt-test",
        "effort": "high",
        "source_file": "target.ec",
        "session_tag": "tag",
        "project_root": tmp_path,
        "proof_tool_manifest": spec.manifest,
        "readiness_issuer": readiness.issue,
        "readiness_waiter": readiness.wait,
    }
    arguments.update(kwargs)
    agent = CodexAgentSession(**arguments)
    agent.codex_capabilities = _capabilities()
    return agent, spec, readiness


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
    agent, spec, _readiness = _agent(tmp_path)
    command = agent._command(
        spec,
        launch_id="launch-command",
    )

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
    assert "shell_tool" in disabled
    assert "unified_exec" in disabled
    assert "code_mode_host" not in disabled
    assert "view_image" in disabled
    overrides = [command[index + 1] for index, value in enumerate(command) if value == "-c"]
    assert "approval_policy=\"never\"" in overrides
    assert "web_search=\"disabled\"" in overrides
    assert "mcp_servers.proof_node_manager.required=true" in overrides
    assert (
        'mcp_servers.proof_node_manager.enabled_tools=["submit_proof_intent"]'
        in overrides
    )
    assert (
        "mcp_servers.proof_node_manager.default_tools_approval_mode=\"approve\""
        in overrides
    )
    assert any(value.startswith("mcp_servers.proof_node_manager.command=") for value in overrides)
    assert any(value.startswith("mcp_servers.proof_node_manager.args=") for value in overrides)
    assert any(value.startswith("mcp_servers.proof_node_manager.tool_timeout_sec=") for value in overrides)
    assert any("launch-command" in value for value in overrides)

    resume = agent._command(
        spec,
        launch_id="launch-resume",
        resume_session_id="thread-123",
    )
    assert resume[1:3] == ["exec", "resume"]
    assert resume[-2:] == ["thread-123", "-"]
    assert "--skip-git-repo-check" in resume
    assert "sandbox_mode=\"read-only\"" in resume


def test_codex_optional_flags_are_capability_based_not_version_pinned(
    tmp_path: Path,
) -> None:
    spec = _launch_spec(tmp_path)
    commands: list[list[str]] = []
    for version in ("codex-cli 0.99-custom", "codex-cli future-nightly"):
        agent, _spec, _readiness = _agent(tmp_path)
        agent.codex_capabilities = _capabilities(
            version=version,
            features=frozenset({"plugins", "shell_tool"}),
        )
        commands.append(agent._command(spec, launch_id=f"launch-{len(commands)}"))

    disabled = [
        [
            command[index + 1]
            for index, value in enumerate(command)
            if value == "--disable"
        ]
        for command in commands
    ]
    assert disabled == [["plugins", "shell_tool"], ["plugins", "shell_tool"]]


def test_codex_uses_outer_eval_confinement_instead_of_nested_sandbox(
    tmp_path: Path,
) -> None:
    agent, spec, _readiness = _agent(
        tmp_path,
        eval_confinement=SimpleNamespace(),
    )

    command = agent._command(spec, launch_id="launch-confined")
    assert command[command.index("--sandbox") + 1] == "danger-full-access"
    overrides = [
        command[index + 1]
        for index, value in enumerate(command)
        if value == "-c"
    ]
    assert "approval_policy=\"never\"" in overrides

    resume = agent._command(
        spec,
        launch_id="launch-confined-resume",
        resume_session_id="thread-confined",
    )
    assert "sandbox_mode=\"danger-full-access\"" in resume
    assert "sandbox_mode=\"read-only\"" not in resume


def test_codex_failure_text_surfaces_jsonl_error(monkeypatch, tmp_path: Path) -> None:
    events = [
        {"type": "thread.started", "thread_id": "thread-err"},
        {"type": "turn.started"},
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
    agent, _spec, _readiness = _agent(
        tmp_path,
        effort="low",
    )

    # Provider startup/model errors can occur before the private MCP child is
    # requested. The stream diagnostic must remain visible in that path.
    result = agent.run("PROMPT")

    assert result.returncode == 1
    assert "not supported by this account" in result.text


def test_codex_jsonl_is_normalized_for_existing_auditors(monkeypatch, tmp_path: Path) -> None:
    events = [
        {"type": "thread.started", "thread_id": "thread-123"},
        {"type": "turn.started"},
        {
            "type": "item.started",
            "item": {
                "id": "mcp-1",
                "type": "mcp_tool_call",
                "server": "proof_node_manager",
                "tool": "submit_proof_intent",
                "arguments": {"intent": "finish", "payload": {}},
                "status": "in_progress",
            },
        },
        {
            "type": "item.completed",
            "item": {
                "id": "mcp-1",
                "type": "mcp_tool_call",
                "server": "proof_node_manager",
                "tool": "submit_proof_intent",
                "result": {"content": [{"type": "text", "text": "done"}]},
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
    agent, spec, readiness = _agent(
        tmp_path,
        emit=emitted.append,
        on_session_id=session_ids.append,
    )

    result = agent.run(
        "MAIN PROMPT",
        system_prompt="SYSTEM ANCHOR",
        mcp_launch_spec=spec,
    )

    assert result.session_id == "thread-123"
    assert result.text == "proof node finished"
    assert session_ids == ["thread-123"]
    assert len(readiness.issued) == 1
    assert readiness.waited
    assert readiness.issued[0] == readiness.waited[0]
    assert proc.stdin.text == "SYSTEM ANCHOR\n\nMAIN PROMPT"
    assert proc.stdin.closed is True
    tool_use = next(
        event for event in emitted
        if event.get("type") == "assistant"
        and event.get("message", {}).get("content", [{}])[0].get("type") == "tool_use"
    )
    block = tool_use["message"]["content"][0]
    assert block["name"] == "mcp__proof_node_manager__submit_proof_intent"
    assert block["input"] == {"intent": "finish", "payload": {}}
    assert any(event.get("type") == "user" for event in emitted)
    assert all(
        event.get("agent_backend") == "codex"
        for event in emitted
        if event.get("session_id")
    )


def test_codex_backend_keeps_running_when_commentary_completes_during_tool(
    monkeypatch,
    tmp_path: Path,
) -> None:
    events = [
        {"type": "thread.started", "thread_id": "thread-overlap"},
        {"type": "turn.started"},
        {
            "type": "item.started",
            "item": {
                "id": "mcp-overlap",
                "type": "mcp_tool_call",
                "server": "proof_node_manager",
                "tool": "submit_proof_intent",
                "arguments": {"intent": "commit_tactic"},
            },
        },
        {
            "type": "item.completed",
            "item": {
                "id": "msg-overlap",
                "type": "agent_message",
                "text": "The manager is checking this tactic.",
            },
        },
        {
            "type": "item.completed",
            "item": {
                "id": "mcp-overlap",
                "type": "mcp_tool_call",
                "result": {"content": [{"type": "text", "text": "accepted"}]},
            },
        },
        {"type": "turn.completed", "usage": {}},
    ]
    proc = _FakeProc([json.dumps(event) + "\n" for event in events])
    monkeypatch.setattr(runtime_module.subprocess, "Popen", lambda *args, **kwargs: proc)
    agent, spec, _readiness = _agent(tmp_path)

    result = agent.run("PROMPT", mcp_launch_spec=spec)

    assert result.returncode == 0
    assert result.text == "The manager is checking this tactic."


def test_eval_codex_fails_closed_on_non_manager_tool(monkeypatch, tmp_path: Path) -> None:
    events = [
        {"type": "thread.started", "thread_id": "thread-policy"},
        {"type": "turn.started"},
        {
            "type": "item.started",
            "item": {
                "id": "cmd-policy",
                "type": "command_execution",
                "command": "rg lemma target.ec",
                "status": "in_progress",
            },
        },
    ]
    proc = _FakeProc([json.dumps(event) + "\n" for event in events])
    monkeypatch.setattr(runtime_module.subprocess, "Popen", lambda *args, **kwargs: proc)
    emitted: list[dict] = []
    agent, spec, _readiness = _agent(
        tmp_path,
        emit=emitted.append,
        eval_mode=True,
    )

    result = agent.run("PROMPT", mcp_launch_spec=spec)

    assert result.returncode == 2
    assert result.text == (
        "provider attempted a disabled tool: codex:command_execution"
    )
    assert agent.mcp_failed_to_start is False
    assert any(
        item.get("codex_event_type") == "agent_event_policy.violation"
        for item in emitted
    )


def test_eval_codex_allows_only_manager_submit_intent_tool(
    monkeypatch,
    tmp_path: Path,
) -> None:
    events = [
        {"type": "thread.started", "thread_id": "thread-manager"},
        {"type": "turn.started"},
        {
            "type": "item.started",
            "item": {
                "id": "mcp-manager",
                "type": "mcp_tool_call",
                "server": "proof_node_manager",
                "tool": "submit_proof_intent",
                "arguments": {
                    "intent": "{\"intent\":\"finish\",\"payload\":{}}"
                },
                "status": "in_progress",
            },
        },
        {
            "type": "item.completed",
            "item": {
                "id": "mcp-manager",
                "type": "mcp_tool_call",
                "server": "proof_node_manager",
                "tool": "submit_proof_intent",
                "status": "completed",
                "result": {"content": [{"type": "text", "text": "done"}]},
            },
        },
        {
            "type": "item.completed",
            "item": {
                "id": "msg-manager",
                "type": "agent_message",
                "text": "finished",
            },
        },
        {"type": "turn.completed", "usage": {}},
    ]
    proc = _FakeProc([json.dumps(event) + "\n" for event in events])
    monkeypatch.setattr(runtime_module.subprocess, "Popen", lambda *args, **kwargs: proc)
    emitted: list[dict] = []
    confinement = SimpleNamespace(
        wrap_command=lambda command, *, agent_backend: command,
    )
    agent, spec, _readiness = _agent(
        tmp_path,
        emit=emitted.append,
        eval_confinement=confinement,
    )

    result = agent.run("PROMPT", mcp_launch_spec=spec)

    assert result.returncode == 0
    assert result.text == "finished"
    assert agent.last_turn_had_tool_call is True
    assert not any(
        item.get("codex_event_type") == "agent_event_policy.violation"
        for item in emitted
    )


def test_eval_codex_accepts_empty_host_metadata_without_manager_normalization(
    monkeypatch,
    tmp_path: Path,
) -> None:
    events = [
        {"type": "thread.started", "thread_id": "thread-metadata"},
        {"type": "turn.started"},
        {
            "type": "item.started",
            "item": {
                "id": "metadata-1",
                "type": "mcp_tool_call",
                "server": "codex",
                "tool": "list_mcp_resources",
                "arguments": {},
            },
        },
        {
            "type": "item.completed",
            "item": {
                "id": "metadata-1",
                "type": "mcp_tool_call",
                "server": "codex",
                "tool": "list_mcp_resources",
                "result": {"resources": [], "nextCursor": None},
            },
        },
        {
            "type": "item.completed",
            "item": {
                "id": "msg-metadata",
                "type": "agent_message",
                "text": "no proof action yet",
            },
        },
        {"type": "turn.completed", "usage": {}},
    ]
    proc = _FakeProc([json.dumps(event) + "\n" for event in events])
    monkeypatch.setattr(runtime_module.subprocess, "Popen", lambda *args, **kwargs: proc)
    emitted: list[dict] = []
    confinement = SimpleNamespace(
        wrap_command=lambda command, *, agent_backend: command,
    )
    agent, spec, _readiness = _agent(
        tmp_path,
        emit=emitted.append,
        eval_confinement=confinement,
    )

    result = agent.run("PROMPT", mcp_launch_spec=spec)

    assert result.returncode == 0
    assert result.text == "no proof action yet"
    assert agent.last_turn_had_tool_call is False
    assert not any(
        event.get("type") in {"assistant", "user"}
        and event.get("message", {}).get("content", [{}])[0].get("type")
        in {"tool_use", "tool_result"}
        for event in emitted
    )
    assert any(
        event.get("codex_event_type")
        == "agent_event_policy.host_metadata_empty"
        for event in emitted
    )


def test_eval_codex_rejects_nonempty_host_metadata(monkeypatch, tmp_path: Path) -> None:
    events = [
        {"type": "thread.started", "thread_id": "thread-resource"},
        {"type": "turn.started"},
        {
            "type": "item.started",
            "item": {
                "id": "metadata-resource",
                "type": "mcp_tool_call",
                "server": "codex",
                "tool": "list_mcp_resources",
                "arguments": {},
            },
        },
        {
            "type": "item.completed",
            "item": {
                "id": "metadata-resource",
                "type": "mcp_tool_call",
                "server": "codex",
                "tool": "list_mcp_resources",
                "arguments": {},
                "result": {
                    "resources": [
                        {"uri": "file:///forbidden", "name": "forbidden"}
                    ]
                },
            },
        },
    ]
    proc = _FakeProc([json.dumps(event) + "\n" for event in events])
    monkeypatch.setattr(runtime_module.subprocess, "Popen", lambda *args, **kwargs: proc)
    confinement = SimpleNamespace(
        wrap_command=lambda command, *, agent_backend: command,
    )
    agent, spec, _readiness = _agent(
        tmp_path,
        eval_confinement=confinement,
    )

    result = agent.run("PROMPT", mcp_launch_spec=spec)

    assert result.returncode == 2
    assert result.text == (
        "provider host metadata returned non-empty or invalid content"
    )


def test_codex_session_registry_does_not_invent_claude_transcript(tmp_path: Path) -> None:
    memory = NodeMemory(tmp_path, "Tree-0.0")
    memory.record_agent_session(
        "thread-123", cwd=tmp_path, agent_backend="codex"
    )
    record = json.loads(memory.agent_sessions.read_text(encoding="utf-8"))
    assert record["agent_backend"] == "codex"
    assert "transcript_path" not in record


def _minimal_turn_events(
    *,
    thread_id: str | None,
    input_tokens: int,
) -> list[dict]:
    events: list[dict] = []
    if thread_id is not None:
        events.append({"type": "thread.started", "thread_id": thread_id})
    events.extend([
        {"type": "turn.started"},
        {
            "type": "item.completed",
            "item": {"id": "msg-1", "type": "agent_message", "text": "working"},
        },
        {
            "type": "turn.completed",
            "usage": {"input_tokens": input_tokens, "output_tokens": 5},
        },
    ])
    return events


def test_codex_cumulative_usage_never_trips_context_watermark(
    tmp_path: Path, monkeypatch
) -> None:
    """Per-invocation token totals are not a current-context measurement."""
    from workflow.provider.ctx_respawn import CtxWatermarkDetector

    emitted: list[dict] = []
    agent, spec, _readiness = _agent(tmp_path, emit=emitted.append)
    agent._ctx_detector = CtxWatermarkDetector(tokens=100, turns=2, enabled=True)

    def _scripted(events: list[dict]) -> None:
        proc = _FakeProc([json.dumps(event) + "\n" for event in events])
        monkeypatch.setattr(
            runtime_module.subprocess, "Popen", lambda *args, **kwargs: proc
        )

    # Many requests can exceed the watermark without any one context doing so.
    _scripted(_minimal_turn_events(thread_id="thread-ctx", input_tokens=150))
    result = agent.run("PROMPT", mcp_launch_spec=spec)
    assert result.returncode == 0
    assert agent.ctx_pressure is False
    assert agent._ctx_detector.hot_turns == 0

    # A second large invocation is still not evidence of context pressure.
    _scripted(_minimal_turn_events(thread_id="thread-ctx", input_tokens=160))
    agent.run("CONTINUE", mcp_launch_spec=spec)
    assert agent.ctx_pressure is False
    trips = [e for e in emitted if e.get("ctx_watermark_tripped")]
    assert trips == []

    # A fresh thread (respawn cleared session_id) resets detector + pressure.
    agent.session_id = ""
    agent.ctx_pressure = True
    _scripted(_minimal_turn_events(thread_id="thread-new", input_tokens=10))
    agent.run("FRESH", mcp_launch_spec=spec)
    assert agent.ctx_pressure is False
    assert agent._ctx_detector.hot_turns == 0


def test_context_tokens_from_codex_event_shapes() -> None:
    from workflow.provider.ctx_respawn import context_tokens_from_codex_event

    assert context_tokens_from_codex_event(
        {"type": "turn.completed", "usage": {"input_tokens": 51069}}
    ) is None
    assert context_tokens_from_codex_event(
        {"type": "turn.completed", "usage": {}}
    ) is None
    assert context_tokens_from_codex_event(
        {"type": "turn.completed", "usage": {"input_tokens": "garbage"}}
    ) is None
    assert context_tokens_from_codex_event({"type": "turn.started"}) is None
    assert context_tokens_from_codex_event({}) is None
