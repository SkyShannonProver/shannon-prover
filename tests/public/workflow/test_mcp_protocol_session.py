from __future__ import annotations

from workflow.proof_tool.proof_node_mcp_server import (
    SUPPORTED_MCP_PROTOCOL_VERSIONS,
    McpProtocolSession,
    McpProtocolState,
)
from workflow.proof_tool.proof_tool_contract import (
    DECLARATION_RESOLVE_TOOL_IDENTITY,
    SOURCE_READ_TOOL_IDENTITY,
    SOURCE_SEARCH_TOOL_IDENTITY,
    resolve_proof_tool_contract,
)


def _request(method: str, msg_id: int, params=None) -> dict:
    message = {"jsonrpc": "2.0", "id": msg_id, "method": method}
    if params is not None:
        message["params"] = params
    return message


def _initialized_session() -> McpProtocolSession:
    session = McpProtocolSession(
        manifest=resolve_proof_tool_contract("l1_goal_projection"),
        launch_id="launch-1",
    )
    initialized = session.handle(_request(
        "initialize",
        1,
        {"protocolVersion": SUPPORTED_MCP_PROTOCOL_VERSIONS[0]},
    ))
    assert initialized.response is not None
    notification = session.handle({
        "jsonrpc": "2.0",
        "method": "notifications/initialized",
    })
    assert notification.response is None and not notification.fatal
    return session


def test_readiness_ack_gates_lossless_tool_dispatch() -> None:
    session = _initialized_session()
    listed = session.handle(_request("tools/list", 2))

    assert listed.readiness_claim is not None
    assert listed.readiness_claim.launch_id == "launch-1"
    assert session.state == McpProtocolState.AWAITING_READINESS_ACK
    assert listed.response["result"]["tools"][0]["inputSchema"] == {
        "type": "object",
        "properties": {
            "intent": {"type": "string"},
            "payload": {"type": "object", "additionalProperties": True},
        },
        "additionalProperties": True,
    }
    claim = listed.readiness_claim
    assert session.acknowledge_readiness(
        launch_id=claim.launch_id,
        negotiated_protocol=claim.negotiated_protocol,
    )
    raw_arguments = {"extra": [1, 2], "payload": "malformed"}
    called = session.handle(_request("tools/call", 3, {
        "name": session.manifest.identity.tool,
        "arguments": raw_arguments,
    }))

    assert called.dispatch_tool_call
    assert called.tool_call_id == 3
    assert called.raw_arguments is raw_arguments


def test_call_before_readiness_ack_fails_closed() -> None:
    session = _initialized_session()
    session.handle(_request("tools/list", 2))

    decision = session.handle(_request("tools/call", 3, {
        "name": session.manifest.identity.tool,
        "arguments": {},
    }))

    assert decision.fatal
    assert decision.response["error"]["code"] == -32002
    assert session.state == McpProtocolState.UNAVAILABLE


def test_source_resource_is_listed_and_dispatched_only_when_enabled() -> None:
    session = McpProtocolSession(
        manifest=resolve_proof_tool_contract(
            "l1_goal_projection",
            source_navigation_enabled=True,
        ),
        launch_id="launch-source",
    )
    session.handle(_request(
        "initialize",
        1,
        {"protocolVersion": SUPPORTED_MCP_PROTOCOL_VERSIONS[0]},
    ))
    session.handle({"jsonrpc": "2.0", "method": "notifications/initialized"})
    listed = session.handle(_request("tools/list", 2))
    assert [item["name"] for item in listed.response["result"]["tools"]] == [
        "submit_proof_intent",
        "read_easycrypt_source",
        "search_easycrypt_source",
        "resolve_easycrypt_declaration",
    ]
    claim = listed.readiness_claim
    assert claim is not None
    assert session.acknowledge_readiness(
        launch_id=claim.launch_id,
        negotiated_protocol=claim.negotiated_protocol,
    )

    arguments = {"path": "task/Target.ec", "start_line": 1, "end_line": 20}
    called = session.handle(_request("tools/call", 3, {
        "name": "read_easycrypt_source",
        "arguments": arguments,
    }))
    assert called.dispatch_tool_call
    assert called.tool_identity == SOURCE_READ_TOOL_IDENTITY
    assert called.raw_arguments is arguments

    for request_id, name, identity, arguments in (
        (4, "search_easycrypt_source", SOURCE_SEARCH_TOOL_IDENTITY,
         {"query": "helper", "scope": "task"}),
        (5, "resolve_easycrypt_declaration", DECLARATION_RESOLVE_TOOL_IDENTITY,
         {"symbol": "Distr.mu_mem"}),
    ):
        called = session.handle(_request("tools/call", request_id, {
            "name": name,
            "arguments": arguments,
        }))
        assert called.dispatch_tool_call
        assert called.tool_identity == identity
        assert called.raw_arguments is arguments


def test_readiness_ack_must_match_every_identity() -> None:
    session = _initialized_session()
    listed = session.handle(_request("tools/list", 2))
    claim = listed.readiness_claim
    assert claim is not None

    assert not session.acknowledge_readiness(
        launch_id="other-launch",
        negotiated_protocol=claim.negotiated_protocol,
    )
    assert session.state == McpProtocolState.UNAVAILABLE


def test_protocol_order_and_jsonrpc_shape_fail_closed() -> None:
    manifest = resolve_proof_tool_contract("l1_goal_projection")
    session = McpProtocolSession(manifest=manifest, launch_id="launch-order")
    out_of_order = session.handle(_request("tools/list", 1))

    assert out_of_order.fatal
    assert session.state == McpProtocolState.UNAVAILABLE

    malformed = McpProtocolSession(manifest=manifest, launch_id="launch-json")
    decision = malformed.handle({"id": 1, "method": "initialize", "params": {}})
    assert decision.fatal
    assert decision.response["error"]["code"] == -32600

    invalid_id = McpProtocolSession(manifest=manifest, launch_id="launch-id")
    decision = invalid_id.handle({
        "jsonrpc": "2.0",
        "id": {"not": "a JSON-RPC id"},
        "method": "initialize",
        "params": {"protocolVersion": SUPPORTED_MCP_PROTOCOL_VERSIONS[0]},
    })
    assert decision.fatal
    assert decision.response["error"]["code"] == -32600


def test_unsupported_client_version_negotiates_owned_server_version() -> None:
    session = McpProtocolSession(
        manifest=resolve_proof_tool_contract("l1_goal_projection"),
        launch_id="launch-version",
    )
    decision = session.handle(_request(
        "initialize",
        1,
        {"protocolVersion": "2099-01-01"},
    ))

    assert decision.response["result"]["protocolVersion"] == (
        SUPPORTED_MCP_PROTOCOL_VERSIONS[-1]
    )
    assert session.negotiated_protocol == SUPPORTED_MCP_PROTOCOL_VERSIONS[-1]
