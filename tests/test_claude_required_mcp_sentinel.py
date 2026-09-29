"""Contract tests for Claude's eager managed-MCP preflight gate."""

from workflow.validation.claude_required_mcp_sentinel import validate_claude_init


EXPECTED = {
    "mcp__proof_node_manager__submit_proof_intent",
    "mcp__proof_node_manager__search_easycrypt_source",
}


def _init(*, status: str = "connected", tools: set[str] = EXPECTED) -> dict:
    return {
        "type": "system",
        "subtype": "init",
        "mcp_servers": [{"name": "proof_node_manager", "status": status}],
        "tools": sorted(tools),
    }


def test_accepts_connected_server_with_all_eager_tools() -> None:
    passed, error = validate_claude_init(
        _init(),
        server_name="proof_node_manager",
        expected_tools=EXPECTED,
    )
    assert passed is True
    assert error == ""


def test_rejects_connected_server_when_required_tool_is_deferred() -> None:
    passed, error = validate_claude_init(
        _init(tools={"mcp__proof_node_manager__submit_proof_intent"}),
        server_name="proof_node_manager",
        expected_tools=EXPECTED,
    )
    assert passed is False
    assert "required eager Claude MCP tools are missing" in error


def test_rejects_nonconnected_server() -> None:
    passed, error = validate_claude_init(
        _init(status="pending"),
        server_name="proof_node_manager",
        expected_tools=EXPECTED,
    )
    assert passed is False
    assert "was not connected" in error
