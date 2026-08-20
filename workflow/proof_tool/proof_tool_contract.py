"""Provider-neutral contract for the single managed proof tool.

This module owns the stable MCP server/tool identity and the transport envelope
advertised to an agent provider.  It deliberately does not decide whether an
intent is valid in the current proof state; that decision belongs to the
manager-owned admission path.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from workflow.proof_management.protocol_repair import ALLOWED_AGENT_INTENTS
from workflow.proof_state_compiler.runtime_profiles import allowed_runtime_intents


PROOF_TOOL_ENVELOPE_VERSION = "proof_tool_envelope.v1"


@dataclass(frozen=True, order=True)
class ToolIdentity:
    """Canonical provider-neutral identity of one MCP tool."""

    server: str
    tool: str

    def __post_init__(self) -> None:
        if not isinstance(self.server, str) or not self.server.strip():
            raise ValueError("tool server identity must be a non-empty string")
        if not isinstance(self.tool, str) or not self.tool.strip():
            raise ValueError("tool name identity must be a non-empty string")
        object.__setattr__(self, "server", self.server.strip())
        object.__setattr__(self, "tool", self.tool.strip())

    def to_dict(self) -> dict[str, str]:
        return {"server": self.server, "tool": self.tool}


PROOF_TOOL_IDENTITY = ToolIdentity(
    server="proof_node_manager",
    tool="submit_proof_intent",
)


@dataclass(frozen=True)
class ProofToolContractManifest:
    """One node's resolved proof-tool contract.

    ``effective_profile_intents`` is presentation/admission configuration fixed
    at node startup.  It is not a statement that every listed control is valid
    in the current proof state.
    """

    identity: ToolIdentity
    envelope_version: str
    effective_profile_intents: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.identity != PROOF_TOOL_IDENTITY:
            raise ValueError("proof-tool manifest used an unexpected identity")
        if self.envelope_version != PROOF_TOOL_ENVELOPE_VERSION:
            raise ValueError("proof-tool manifest used an unsupported envelope")
        if self.effective_profile_intents != tuple(
            sorted(set(self.effective_profile_intents))
        ):
            raise ValueError("effective profile intents must be sorted and unique")

    def to_dict(self) -> dict[str, Any]:
        return {
            "identity": self.identity.to_dict(),
            "envelope_version": self.envelope_version,
            "effective_profile_intents": list(self.effective_profile_intents),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ProofToolContractManifest":
        """Parse a launch-provided manifest.

        The manifest travels parent -> child argv within one process tree on
        one machine; a frozen dataclass and ``==`` are its whole identity (the
        old sha256 self-authentication defended against nobody).
        """

        if not isinstance(value, Mapping):
            raise TypeError("proof-tool manifest must be an object")
        raw_identity = value.get("identity")
        if not isinstance(raw_identity, Mapping):
            raise ValueError("proof-tool manifest identity must be an object")
        raw_intents = value.get("effective_profile_intents")
        if not isinstance(raw_intents, list) or not all(
            isinstance(item, str) and item for item in raw_intents
        ):
            raise ValueError("proof-tool manifest intents must be a string list")
        return cls(
            identity=ToolIdentity(
                server=raw_identity.get("server"),
                tool=raw_identity.get("tool"),
            ),
            envelope_version=value.get("envelope_version"),
            effective_profile_intents=tuple(raw_intents),
        )


def proof_tool_input_schema() -> dict[str, Any]:
    """Return the intentionally permissive agent transport schema.

    The manager must receive malformed/missing intent fields unchanged so its
    protocol-repair path remains the only semantic decoder: no ``required``
    fields, no intent enum, no payload field enumeration.

    ``intent``/``payload`` DO declare their JSON types: with ``payload``
    undeclared, the Claude CLI serializes the nested object into a JSON string
    before the MCP call (verified live 2026-08-19 — every intent of a run
    arrived stringified). Type declarations keep the transport faithful while
    admission still owns all semantic validation.
    """

    return {
        "type": "object",
        "properties": {
            "intent": {"type": "string"},
            "payload": {"type": "object", "additionalProperties": True},
        },
        "additionalProperties": True,
    }


def resolve_proof_tool_contract(
    surface_profile: str | None,
) -> ProofToolContractManifest:
    """Resolve one immutable contract manifest at node startup."""

    effective = tuple(sorted(
        allowed_runtime_intents(surface_profile) & ALLOWED_AGENT_INTENTS
    ))
    return ProofToolContractManifest(
        identity=PROOF_TOOL_IDENTITY,
        envelope_version=PROOF_TOOL_ENVELOPE_VERSION,
        effective_profile_intents=effective,
    )


def proof_tool_definition(
    manifest: ProofToolContractManifest,
    *,
    description: str = "Submit exactly one proof intent to the managed proof node.",
) -> dict[str, Any]:
    """Render the provider-independent MCP tool definition."""

    validate_proof_tool_contract(manifest)
    return {
        "name": manifest.identity.tool,
        "description": str(description),
        "inputSchema": proof_tool_input_schema(),
    }


def validate_proof_tool_contract(
    manifest: ProofToolContractManifest,
) -> ProofToolContractManifest:
    """Fail closed unless the shared manifest carries the expected identity."""

    if not isinstance(manifest, ProofToolContractManifest):
        raise TypeError("proof-tool contract must be a resolved manifest")
    if manifest.identity != PROOF_TOOL_IDENTITY:
        raise ValueError("proof-tool manifest identity drifted")
    if manifest.envelope_version != PROOF_TOOL_ENVELOPE_VERSION:
        raise ValueError("proof-tool manifest envelope drifted")
    return manifest
