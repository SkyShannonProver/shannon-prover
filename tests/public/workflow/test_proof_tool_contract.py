from __future__ import annotations

import pytest

from workflow.proof_tool.proof_tool_contract import (
    DECLARATION_RESOLVE_TOOL_IDENTITY,
    PROOF_TOOL_ENVELOPE_VERSION,
    PROOF_TOOL_IDENTITY,
    SOURCE_READ_TOOL_IDENTITY,
    SOURCE_SEARCH_TOOL_IDENTITY,
    ProofToolContractManifest,
    proof_tool_definition,
    proof_tool_definitions,
    proof_tool_input_schema,
    resolve_proof_tool_contract,
)


def test_resolved_contract_is_stable_and_transport_schema_is_permissive() -> None:
    first = resolve_proof_tool_contract("l1_goal_projection")
    second = resolve_proof_tool_contract("l1_goal_projection")

    assert first == second
    assert first.identity == PROOF_TOOL_IDENTITY
    assert first.envelope_version == PROOF_TOOL_ENVELOPE_VERSION
    assert first.effective_profile_intents == tuple(
        sorted(set(first.effective_profile_intents))
    )
    assert proof_tool_input_schema() == {
        "type": "object",
        "properties": {
            "intent": {"type": "string"},
            "payload": {"type": "object", "additionalProperties": True},
        },
        "additionalProperties": True,
    }
    tool = proof_tool_definition(first)
    assert tool["name"] == PROOF_TOOL_IDENTITY.tool
    assert tool["inputSchema"] == proof_tool_input_schema()
    # Transport-permissive: types are declared (an undeclared nested object
    # gets stringified by the Claude CLI), but nothing is required and the
    # intent is not an enum — malformed submissions must reach manager repair.
    assert "required" not in tool["inputSchema"]
    assert "enum" not in tool["inputSchema"]["properties"]["intent"]


def test_manifest_round_trips_and_equality_binds_intents() -> None:
    l1 = resolve_proof_tool_contract("l1_goal_projection")
    treatment = resolve_proof_tool_contract("proof_state_compiler")

    assert ProofToolContractManifest.from_dict(l1.to_dict()) == l1
    if l1.effective_profile_intents != treatment.effective_profile_intents:
        assert l1 != treatment

    with pytest.raises(ValueError, match="sorted and unique"):
        ProofToolContractManifest(
            identity=l1.identity,
            envelope_version=l1.envelope_version,
            effective_profile_intents=tuple(
                reversed(l1.effective_profile_intents)
            ),
        )
    with pytest.raises(ValueError, match="intents"):
        ProofToolContractManifest.from_dict({
            "identity": l1.identity.to_dict(),
            "envelope_version": l1.envelope_version,
            "effective_profile_intents": [1, 2],
        })


def test_source_navigation_is_an_explicit_manager_tool_set() -> None:
    manifest = resolve_proof_tool_contract(
        "l1_goal_projection",
        source_navigation_enabled=True,
    )

    assert manifest.tool_identities == (
        PROOF_TOOL_IDENTITY,
        SOURCE_READ_TOOL_IDENTITY,
        SOURCE_SEARCH_TOOL_IDENTITY,
        DECLARATION_RESOLVE_TOOL_IDENTITY,
    )
    assert ProofToolContractManifest.from_dict(manifest.to_dict()) == manifest
    definitions = proof_tool_definitions(manifest)
    assert [item["name"] for item in definitions] == [
        "submit_proof_intent",
        "read_easycrypt_source",
        "search_easycrypt_source",
        "resolve_easycrypt_declaration",
    ]
    source_schema = definitions[1]["inputSchema"]
    assert source_schema["required"] == ["path"]
    assert source_schema["additionalProperties"] is False
    search_schema = definitions[2]["inputSchema"]
    assert search_schema["required"] == ["query"]
    assert search_schema["properties"]["scope"]["enum"] == [
        "all", "task", "libraries"
    ]
    resolve_schema = definitions[3]["inputSchema"]
    assert resolve_schema["required"] == ["symbol"]
    assert resolve_schema["additionalProperties"] is False
