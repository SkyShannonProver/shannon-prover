"""Invocation-bound MCP readiness registration tests.

Readiness is authenticated endpoint state, never an inference from a debug log
or child-process liveness.
"""
from __future__ import annotations

from typing import Any

import _pathsetup  # noqa: F401
from workflow.proof_management.types import ManagedTurn
from workflow.provider.provider_sessions import ClaudeAgentSession
from workflow.proof_tool.proof_tool_contract import resolve_proof_tool_contract
from workflow.proof_tool.proof_tool_endpoint import ProofToolEndpointServer
from workflow.proof_tool.proof_tool_session import ProofToolSession


class _Memory:
    def record_turn(self, **_kwargs: Any) -> None:
        return


def _endpoint() -> ProofToolEndpointServer:
    manifest = resolve_proof_tool_contract("l1_goal_projection")

    def handle_turn(_raw: Any, _deadline: float) -> ManagedTurn:
        return ManagedTurn(ok=True, workspace_view={})

    session = ProofToolSession(
        node_id="Tree-readiness",
        manifest=manifest,
        handle_turn=handle_turn,
        memory=_Memory(),
        response_renderer=lambda *_args: "ok",
        max_turns=1,
    )
    return ProofToolEndpointServer(
        session=session,
        manifest=manifest,
        token="token",
    )


def _ready(
    endpoint: ProofToolEndpointServer,
    launch_id: str,
    protocol: str,
) -> dict[str, Any]:
    return endpoint.handle_envelope({
        "envelope_version": endpoint.manifest.envelope_version,
        "kind": "ready",
        "token": endpoint.token,
        "launch_id": launch_id,
        "negotiated_protocol": protocol,
    })


def test_ready_requires_the_exact_armed_invocation() -> None:
    endpoint = _endpoint()

    rejected = _ready(endpoint, "unarmed", "2024-11-05")

    assert rejected["ok"] is False
    assert rejected["error"]["code"] == "unexpected_launch"
    assert endpoint.wait_ready("unarmed", 0) is None


def test_exact_ready_ack_registers_launch_and_protocol() -> None:
    endpoint = _endpoint()
    endpoint.expect_launch("launch-1")

    ack = _ready(endpoint, "launch-1", "2024-11-05")
    claim = endpoint.wait_ready("launch-1", 0)

    assert ack["kind"] == "ready_ack"
    assert ack["ok"] is True
    assert claim is not None
    assert claim.launch_id == "launch-1"
    assert claim.negotiated_protocol == "2024-11-05"


def test_arming_new_launch_revokes_stale_child() -> None:
    endpoint = _endpoint()
    endpoint.expect_launch("launch-1")
    assert _ready(endpoint, "launch-1", "2024-11-05")["ok"] is True

    endpoint.expect_launch("launch-2")

    assert endpoint.wait_ready("launch-1", 0) is None
    stale = _ready(endpoint, "launch-1", "2024-11-05")
    assert stale["error"]["code"] == "unexpected_launch"


def test_provider_exit_before_ready_is_classified_as_startup_failure() -> None:
    class ExitedProcess:
        def poll(self) -> int:
            return 7

    events: list[dict[str, Any]] = []
    agent = ClaudeAgentSession.__new__(ClaudeAgentSession)
    agent.readiness_waiter = lambda *_args: None
    agent.mcp_failed_to_start = False
    agent.emit = events.append
    agent.session_tag = "readiness-exit"

    agent._watch_mcp_readiness(
        ExitedProcess(),
        "launch-exited",
        0.01,
    )

    assert agent.mcp_failed_to_start is True
    assert events == [{
        "type": "system",
        "mcp_spawn_failed": True,
        "timeout_s": 0.01,
        "launch_id": "launch-exited",
        "session_tag": "readiness-exit",
        "detail": "child exited before READY",
        "child_returncode": 7,
    }]
