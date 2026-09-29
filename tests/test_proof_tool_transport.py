from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Any, Mapping

import pytest

import _pathsetup  # noqa: F401
from core.easycrypt.eval_source_prep import prepare_eval_source
from workflow.proof_management.protocol_repair import AgentIntent
from workflow.proof_management.types import ManagedTurn, TurnDirective
from workflow.proof_tool.proof_node_mcp_server import (
    McpProtocolDecision,
    ProofToolMcpAdapter,
    _read_message,
)
from workflow.proof_tool.easycrypt_source_resource import (
    EasyCryptSourceResponse,
    EasyCryptSourceResource,
    SOURCE_RESOURCE_MANIFEST_ENV,
)
from workflow.proof_tool.proof_tool_contract import (
    DECLARATION_RESOLVE_TOOL_IDENTITY,
    PROOF_TOOL_IDENTITY,
    resolve_proof_tool_contract,
)
from workflow.proof_tool.proof_tool_endpoint import (
    ProofToolEndpointClient,
    ProofToolEndpointError,
    ProofToolEndpointServer,
)
from workflow.proof_tool.proof_tool_session import (
    ProofToolSession,
    ProofToolSessionResponse,
)


@dataclass
class _Memory:
    calls: list[dict[str, Any]] = field(default_factory=list)

    def record_turn(self, **kwargs: Any) -> None:
        self.calls.append(kwargs)


class _Handler:
    def __init__(self, *, directive: TurnDirective = TurnDirective.CONTINUE) -> None:
        self.calls: list[tuple[Any, float]] = []
        self.directive = directive

    def __call__(
        self,
        raw_arguments: Any,
        absolute_deadline: float,
    ) -> ManagedTurn:
        self.calls.append((raw_arguments, absolute_deadline))
        intent = (
            AgentIntent(
                intent=str(raw_arguments.get("intent")),
                payload=dict(raw_arguments.get("payload") or {}),
            )
            if isinstance(raw_arguments, Mapping)
            and isinstance(raw_arguments.get("payload"), dict)
            else None
        )
        return ManagedTurn(
            ok=True,
            workspace_view={},
            intent=intent,
            committed_tactics=("trivial.",),
            directive=self.directive,
        )


def _session(
    *,
    directive: TurnDirective = TurnDirective.CONTINUE,
    source_navigation_enabled: bool = False,
):
    manifest = resolve_proof_tool_contract(
        "l1_goal_projection",
        source_navigation_enabled=source_navigation_enabled,
    )
    handler = _Handler(directive=directive)
    memory = _Memory()
    rendered: list[int] = []
    emitted: list[dict[str, Any]] = []

    def render(
        _turn: ManagedTurn,
        turn_index: int,
        _intent: dict[str, Any] | None,
        _memory: _Memory,
    ) -> str:
        rendered.append(turn_index)
        return f"manager followup {turn_index}"

    session = ProofToolSession(
        node_id="Tree-unit",
        manifest=manifest,
        handle_turn=handler,
        memory=memory,
        response_renderer=render,
        max_turns=5,
        initial_committed_tactics=("bootstrap-1.", "bootstrap-2.", "bootstrap-3."),
        emit=emitted.append,
    )
    return manifest, handler, memory, rendered, emitted, session


def _source_resource(tmp_path: Path) -> tuple[EasyCryptSourceResource, Path]:
    project = tmp_path / "repo"
    task = project / "task"
    task.mkdir(parents=True)
    source = task / "Target.ec"
    source.write_text(
        "lemma target : true.\nproof.\n  trivial.\nqed.\n",
        encoding="utf-8",
    )
    theories = project / "easycrypt-src" / "theories"
    theories.mkdir(parents=True)
    prepared = prepare_eval_source(
        source_file=source,
        target_lemma="target",
        output_dir=project / "artifacts" / "eval_source",
        copy_root=task,
        strip_proofs=True,
    )
    manifest_path = project / "artifacts" / "eval_source" / "source_manifest.json"
    resource = EasyCryptSourceResource.from_environment(
        project_root=project,
        source_file=prepared.isolated_file.relative_to(project),
        target_lemma="target",
        include_dir=theories.relative_to(project),
        environ={
            SOURCE_RESOURCE_MANIFEST_ENV: str(manifest_path.relative_to(project))
        },
    )
    assert resource is not None
    return resource, prepared.isolated_file.relative_to(project)


def test_endpoint_start_failure_closes_unstarted_server_thread(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, _handler, _memory, _rendered, _emitted, session = _session()
    endpoint = ProofToolEndpointServer(manifest=manifest, session=session)

    def fail_start(_thread: threading.Thread) -> None:
        raise RuntimeError("thread launch failed")

    monkeypatch.setattr(threading.Thread, "start", fail_start)
    with pytest.raises(RuntimeError, match="thread launch failed"):
        endpoint.start()

    assert endpoint._httpd is None
    assert endpoint._thread is None


def test_session_replays_same_internal_call_exactly_once() -> None:
    manifest, handler, memory, rendered, emitted, session = _session()
    kwargs = {
        "call_id": "call-1",
        "raw_arguments": {
            "intent": "commit_tactic",
            "payload": {"tactic": "trivial."},
        },
        "absolute_deadline": time.time() + 10,
    }

    first = session.submit(**kwargs)
    second = session.submit(**kwargs)

    assert second is first
    assert len(handler.calls) == 1
    assert len(memory.calls) == 1
    assert rendered == [1]
    assert session.turn_index == 1
    assert session.last_committed_count == 1
    assert session.last_committed_tactics == ("trivial.",)
    assert emitted == [{
        "type": "system",
        "kind": "manager_turn.completed",
        "node": "Tree-unit",
        "turn_index": 1,
    }]


def test_concurrent_duplicate_waits_and_replays_exact_response() -> None:
    manifest = resolve_proof_tool_contract("l1_goal_projection")
    entered = threading.Event()
    release = threading.Event()
    manager_calls: list[Any] = []

    def handle(raw_arguments: Any, _deadline: float) -> ManagedTurn:
        manager_calls.append(raw_arguments)
        entered.set()
        assert release.wait(timeout=2)
        return ManagedTurn(ok=True, workspace_view={})

    session = ProofToolSession(
        node_id="Tree-concurrent-replay",
        manifest=manifest,
        handle_turn=handle,
        memory=_Memory(),
        response_renderer=lambda *_args: "one response",
        max_turns=5,
    )
    kwargs = {
        "call_id": "same-call",
        "raw_arguments": {"intent": "finish", "payload": {}},
        "absolute_deadline": time.time() + 10,
    }
    responses: list[Any] = []
    first = threading.Thread(target=lambda: responses.append(session.submit(**kwargs)))
    second = threading.Thread(target=lambda: responses.append(session.submit(**kwargs)))
    first.start()
    assert entered.wait(timeout=2)
    second.start()
    release.set()
    first.join(timeout=2)
    second.join(timeout=2)

    assert not first.is_alive() and not second.is_alive()
    assert len(manager_calls) == 1
    assert len(responses) == 2
    assert responses[0] is responses[1]


def test_safe_stop_drains_inflight_turn_and_closes_new_admission() -> None:
    manifest = resolve_proof_tool_contract("l1_goal_projection")
    entered = threading.Event()
    release = threading.Event()
    stop_finished = threading.Event()
    manager_calls: list[Any] = []

    def handle(raw_arguments: Any, _deadline: float) -> ManagedTurn:
        manager_calls.append(raw_arguments)
        entered.set()
        assert release.wait(timeout=2)
        return ManagedTurn(
            ok=True,
            workspace_view={},
            committed_tactics=("progress-1.", "progress-2."),
        )

    session = ProofToolSession(
        node_id="Tree-safe-stop",
        manifest=manifest,
        handle_turn=handle,
        memory=_Memory(),
        response_renderer=lambda *_args: "accepted",
        max_turns=5,
    )
    first_response: list[ProofToolSessionResponse] = []
    stop_boundary: list[Any] = []
    first = threading.Thread(
        target=lambda: first_response.append(session.submit(
            call_id="in-flight",
            raw_arguments={
                "intent": "commit_tactic",
                "payload": {"tactic": "progress-2."},
            },
            absolute_deadline=time.time() + 10,
        ))
    )
    first.start()
    assert entered.wait(timeout=2)

    def stop() -> None:
        stop_boundary.append(session.request_stop("outer cancellation requested"))
        stop_finished.set()

    stopper = threading.Thread(target=stop)
    stopper.start()
    # Admission closes immediately, but checkpointing cannot pass the drain
    # boundary until the already-admitted manager turn has completed.
    admission_deadline = time.monotonic() + 1.0
    while not session.stop_requested and time.monotonic() < admission_deadline:
        time.sleep(0.001)
    assert session.stop_requested is True
    assert not stop_finished.wait(timeout=0.05)
    release.set()
    first.join(timeout=2)
    stopper.join(timeout=2)

    assert not first.is_alive() and not stopper.is_alive()
    assert first_response[0].manager_turn_completed is True
    assert stop_boundary[0].turn_index == 1
    assert stop_boundary[0].committed_tactics == (
        "progress-1.",
        "progress-2.",
    )
    rejected = session.submit(
        call_id="after-stop",
        raw_arguments={"intent": "finish", "payload": {}},
        absolute_deadline=time.time() + 10,
    )
    assert rejected.directive is TurnDirective.STOP_REQUESTED
    assert rejected.manager_turn_completed is False
    assert "outer cancellation requested" in rejected.text
    assert len(manager_calls) == 1


def test_session_caches_expired_request_and_never_calls_manager() -> None:
    manifest, handler, _memory, _rendered, _emitted, session = _session()
    kwargs = {
        "call_id": "expired",
        "raw_arguments": {"intent": "finish", "payload": {}},
        "absolute_deadline": time.time() - 1,
    }

    first = session.submit(**kwargs)
    second = session.submit(**kwargs)

    assert first is second
    assert first.directive is TurnDirective.NODE_UNHEALTHY
    assert handler.calls == []


def test_later_unhealthy_latch_replaces_prior_success_with_exact_replay() -> None:
    manifest = resolve_proof_tool_contract("l1_goal_projection")
    calls: list[Any] = []

    def handle(raw_arguments: Any, _deadline: float) -> ManagedTurn:
        calls.append(raw_arguments)
        if len(calls) == 2:
            raise RuntimeError("manager boundary failed")
        return ManagedTurn(ok=True, workspace_view={})

    session = ProofToolSession(
        node_id="Tree-unhealthy-replay",
        manifest=manifest,
        handle_turn=handle,
        memory=_Memory(),
        response_renderer=lambda *_args: "first success",
        max_turns=5,
    )
    common = {
        "absolute_deadline": time.time() + 10,
    }
    first = session.submit(
        call_id="first",
        raw_arguments={"intent": "finish", "payload": {}},
        **common,
    )
    failed = session.submit(
        call_id="second",
        raw_arguments={"intent": "finish", "payload": {}},
        **common,
    )
    replay_one = session.submit(
        call_id="first",
        raw_arguments={"intent": "finish", "payload": {}},
        **common,
    )
    replay_two = session.submit(
        call_id="first",
        raw_arguments={"intent": "finish", "payload": {}},
        **common,
    )

    assert first.directive is TurnDirective.CONTINUE
    assert failed.directive is TurnDirective.NODE_UNHEALTHY
    assert replay_one is replay_two
    assert replay_one.directive is TurnDirective.NODE_UNHEALTHY
    assert len(calls) == 2


def test_stop_directive_prevents_another_manager_turn() -> None:
    manifest, handler, _memory, _rendered, _emitted, session = _session(
        directive=TurnDirective.STOP_REQUESTED
    )
    first = session.submit(
        call_id="finish",
        raw_arguments={"intent": "finish", "payload": {}},
        absolute_deadline=time.time() + 10,
    )
    second = session.submit(
        call_id="after-finish",
        raw_arguments={"intent": "finish", "payload": {}},
        absolute_deadline=time.time() + 10,
    )

    assert first.directive is TurnDirective.STOP_REQUESTED
    assert second.directive is TurnDirective.STOP_REQUESTED
    assert second.manager_turn_completed is False
    assert len(handler.calls) == 1


def test_endpoint_requires_exact_ready_registration() -> None:
    manifest, _handler, _memory, _rendered, _emitted, session = _session()
    endpoint = ProofToolEndpointServer(session=session, manifest=manifest)
    endpoint.start()
    endpoint.expect_launch("launch-1")
    client = ProofToolEndpointClient(
        host=endpoint.host,
        port=endpoint.port,
        token=endpoint.token,
        launch_id="launch-1",
        manifest=manifest,
        negotiated_protocol="2024-11-05",
        connect_timeout=1,
        endpoint_timeout=2,
    )
    try:
        with pytest.raises(ProofToolEndpointError, match="invocation_not_ready"):
            client.call(
                call_id="call-1",
                raw_arguments={"intent": "finish", "payload": {}},
                absolute_deadline=time.time() + 5,
            )
        ack = client.ready()
        claim = endpoint.wait_ready("launch-1", timeout=1)
        assert claim is not None
        assert ack.negotiated_protocol == claim.negotiated_protocol
    finally:
        endpoint.close()


def test_native_source_resolver_inherits_remaining_call_deadline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_resource, _source_path = _source_resource(tmp_path)
    manifest, _handler, _memory, _rendered, _emitted, session = _session(
        source_navigation_enabled=True
    )
    endpoint = ProofToolEndpointServer(
        session=session,
        manifest=manifest,
        source_resource=source_resource,
    )
    endpoint.start()
    endpoint.expect_launch("deadline-launch")
    client = ProofToolEndpointClient(
        host=endpoint.host,
        port=endpoint.port,
        token=endpoint.token,
        launch_id="deadline-launch",
        manifest=manifest,
        negotiated_protocol="2024-11-05",
        connect_timeout=1,
        endpoint_timeout=2,
    )
    observed: list[float] = []

    def resolve(self, raw_arguments, *, call_id="", timeout_seconds=60.0):
        observed.append(timeout_seconds)
        return EasyCryptSourceResponse(text="resolved")

    monkeypatch.setattr(EasyCryptSourceResource, "resolve_declaration", resolve)
    try:
        client.ready()
        response = client.source_resource(
            tool_identity=DECLARATION_RESOLVE_TOOL_IDENTITY,
            call_id="resolve-deadline",
            raw_arguments={"symbol": "target"},
            absolute_deadline=time.time() + 1.0,
        )
    finally:
        endpoint.close()

    assert response.text == "resolved"
    assert len(observed) == 1
    assert 0 < observed[0] <= 1.0


def test_transport_rejects_non_finite_json_before_session_admission() -> None:
    with pytest.raises(ValueError, match="non-finite JSON number"):
        _read_message(
            BytesIO(
                b'{"jsonrpc":"2.0","id":NaN,"method":"initialize"}\n'
            )
        )

    manifest, handler, _memory, _rendered, _emitted, session = _session()
    endpoint = ProofToolEndpointServer(session=session, manifest=manifest)
    response = endpoint.handle_bytes(
        b'{"envelope_version":"proof-tool-envelope-v1","raw_arguments":Infinity}'
    )
    assert response["error"]["code"] == "invalid_json"
    assert handler.calls == []


def test_stdio_adapter_caps_manager_call_at_node_deadline() -> None:
    manifest = resolve_proof_tool_contract("l1_goal_projection")
    deadlines: list[float] = []

    class Endpoint:
        negotiated_protocol = "2024-11-05"

        def call(self, **kwargs: Any) -> ProofToolSessionResponse:
            deadlines.append(kwargs["absolute_deadline"])
            return ProofToolSessionResponse(
                exit_code=0,
                text="ok",
                turn_index=1,
                directive=TurnDirective.CONTINUE,
                manager_turn_completed=True,
            )

    adapter = ProofToolMcpAdapter(
        host="127.0.0.1",
        port=43210,
        token="token",
        launch_id="launch-deadline",
        manifest=manifest,
        manager_timeout_seconds=600,
        endpoint_timeout_seconds=630,
        node_deadline_epoch=125.0,
        clock=lambda: 100.0,
    )
    adapter._endpoint = Endpoint()

    adapter._dispatch_tool_call(McpProtocolDecision(
        dispatch_tool_call=True,
        tool_identity=PROOF_TOOL_IDENTITY,
        tool_call_id=1,
        raw_arguments={"intent": "finish", "payload": {}},
    ))

    assert deadlines == [125.0]


def test_subprocess_stdio_mcp_reaches_endpoint_and_manager(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "core.easycrypt.compiler_namespace_adapter.load_exact_declarations",
        lambda symbols, _context, _includes, *, timeout=60.0: {
            symbol: {
                "requested": symbol,
                "status": "resolved",
                "resolved": symbol,
                "kind": "lemma",
                "body": f"lemma {symbol} : true.",
                "error": "",
            }
            for symbol in symbols
        },
    )
    source_resource, source_path = _source_resource(tmp_path)
    manifest, handler, memory, rendered, _emitted, session = _session(
        source_navigation_enabled=True
    )
    endpoint = ProofToolEndpointServer(
        session=session,
        manifest=manifest,
        source_resource=source_resource,
        token="-leading-dash-token",
    )
    endpoint.start()
    endpoint.expect_launch("black-box-launch")
    command = [
        sys.executable,
        "-m",
        "workflow.proof_tool.proof_node_mcp_server",
        "--host",
        endpoint.host,
        "--port",
        str(endpoint.port),
        f"--token={endpoint.token}",
        "--launch-id",
        "black-box-launch",
        "--manifest-json",
        json.dumps(manifest.to_dict(), separators=(",", ":"), sort_keys=True),
        "--manager-timeout-seconds",
        "5",
        "--endpoint-timeout-seconds",
        "8",
    ]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
    proc = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=Path(__file__).resolve().parents[1],
        env=env,
    )
    assert proc.stdin is not None
    assert proc.stdout is not None

    def exchange(message: dict[str, Any]) -> dict[str, Any]:
        proc.stdin.write(
            json.dumps(message, separators=(",", ":")).encode("utf-8") + b"\n"
        )
        proc.stdin.flush()
        line = proc.stdout.readline()
        assert line, proc.stderr.read().decode("utf-8", errors="replace")
        return json.loads(line)

    try:
        initialized = exchange({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "2024-11-05"},
        })
        assert initialized["result"]["protocolVersion"] == "2024-11-05"
        proc.stdin.write(
            b'{"jsonrpc":"2.0","method":"notifications/initialized"}\n'
        )
        proc.stdin.flush()
        tools = exchange({
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        })
        definition = tools["result"]["tools"][0]
        assert definition["name"] == manifest.identity.tool
        assert definition["inputSchema"] == {
            "type": "object",
            "properties": {
                "intent": {"type": "string"},
                "payload": {"type": "object", "additionalProperties": True},
            },
            "additionalProperties": True,
        }
        assert tools["result"]["tools"][1]["name"] == "read_easycrypt_source"
        assert tools["result"]["tools"][2]["name"] == "search_easycrypt_source"
        assert tools["result"]["tools"][3]["name"] == "resolve_easycrypt_declaration"
        assert endpoint.wait_ready("black-box-launch", timeout=2) is not None

        source_read = exchange({
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "read_easycrypt_source",
                "arguments": {"path": source_path.as_posix()},
            },
        })
        assert source_read["result"]["isError"] is False
        source_text = source_read["result"]["content"][0]["text"]
        assert "Target.ec — lines 1-" in source_text
        assert "admit." in source_text
        assert handler.calls == []
        assert session.turn_index == 0

        source_search = exchange({
            "jsonrpc": "2.0",
            "id": 31,
            "method": "tools/call",
            "params": {
                "name": "search_easycrypt_source",
                "arguments": {"query": "lemma target", "scope": "task"},
            },
        })
        assert source_search["result"]["isError"] is False
        assert f"{source_path.as_posix()}:1:" in (
            source_search["result"]["content"][0]["text"]
        )

        resolved = exchange({
            "jsonrpc": "2.0",
            "id": 32,
            "method": "tools/call",
            "params": {
                "name": "resolve_easycrypt_declaration",
                "arguments": {"symbol": "target"},
            },
        })
        assert resolved["result"]["isError"] is False
        assert "EasyCrypt-native declaration resolved" in (
            resolved["result"]["content"][0]["text"]
        )
        assert handler.calls == []
        assert session.turn_index == 0

        raw_arguments = {
            "intent": "commit_tactic",
            "payload": {"tactic": "seq 1 1 : (x{1} = x{2})."},
            "unknown_for_manager_repair": {"preserved": True},
        }
        called = exchange({
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": manifest.identity.tool,
                "arguments": raw_arguments,
            },
        })
        assert called["result"] == {
            "content": [{"type": "text", "text": "manager followup 1"}],
            "isError": False,
        }
        assert handler.calls[0][0] == raw_arguments
        assert handler.calls[0][1] > time.time()
        assert len(memory.calls) == 1
        assert rendered == [1]

        malformed = ["not", "an", "object"]
        repaired = exchange({
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {
                "name": manifest.identity.tool,
                "arguments": malformed,
            },
        })
        assert repaired["result"] == {
            "content": [{"type": "text", "text": "manager followup 2"}],
            "isError": False,
        }
        assert handler.calls[1][0] == malformed
    finally:
        proc.stdin.close()
        proc.wait(timeout=5)
        endpoint.close()

    assert proc.returncode == 0


def test_mcp_child_pythonpath_is_the_repo_root(tmp_path):
    """The child env must put the REPO ROOT on PYTHONPATH — when this module
    moved into workflow/proof_tool/, parent.parent silently became workflow/
    and every MCP child died on import (live, 2026-08-19). Anchor on a file
    that only exists at the root."""
    from pathlib import Path

    from workflow.proof_tool.proof_tool_launch import (
        ProofMcpLaunchSpec,
        proof_tool_timing_for_prefix,
    )

    spec = ProofMcpLaunchSpec(
        manifest=resolve_proof_tool_contract("l1_goal_projection"),
        endpoint_host="127.0.0.1",
        endpoint_port=1,
        endpoint_token="t",
        private_dir=tmp_path,
        timing=proof_tool_timing_for_prefix(0),
    )
    env = spec.child_command("a" * 12)[2]
    root = Path(env["PYTHONPATH"])
    assert (root / "pyproject.toml").exists()
    assert (root / "workflow" / "proof_tool").is_dir()
