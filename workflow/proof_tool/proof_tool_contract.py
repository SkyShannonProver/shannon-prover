"""Provider-neutral contract for invocation-bound manager tools.

This module owns the stable MCP server/tool identity and the transport envelope
advertised to an agent provider. It deliberately does not decide whether a
proof intent is valid in the current proof state; that decision belongs to the
manager-owned admission path. Optional source-navigation tools are read-only
and never enter proof-state admission.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from workflow.proof_management.protocol_repair import ALLOWED_AGENT_INTENTS
from workflow.proof_state_compiler.runtime_profiles import allowed_runtime_intents


PROOF_TOOL_ENVELOPE_VERSION = "proof_tool_envelope.v3"


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
SOURCE_READ_TOOL_IDENTITY = ToolIdentity(
    server="proof_node_manager",
    tool="read_easycrypt_source",
)
SOURCE_SEARCH_TOOL_IDENTITY = ToolIdentity(
    server="proof_node_manager",
    tool="search_easycrypt_source",
)
DECLARATION_RESOLVE_TOOL_IDENTITY = ToolIdentity(
    server="proof_node_manager",
    tool="resolve_easycrypt_declaration",
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
    source_navigation_enabled: bool = False

    def __post_init__(self) -> None:
        if self.identity != PROOF_TOOL_IDENTITY:
            raise ValueError("proof-tool manifest used an unexpected identity")
        if self.envelope_version != PROOF_TOOL_ENVELOPE_VERSION:
            raise ValueError("proof-tool manifest used an unsupported envelope")
        if self.effective_profile_intents != tuple(
            sorted(set(self.effective_profile_intents))
        ):
            raise ValueError("effective profile intents must be sorted and unique")
        if not isinstance(self.source_navigation_enabled, bool):
            raise ValueError("source-navigation capability must be boolean")

    @property
    def tool_identities(self) -> tuple[ToolIdentity, ...]:
        return (
            (
                PROOF_TOOL_IDENTITY,
                SOURCE_READ_TOOL_IDENTITY,
                SOURCE_SEARCH_TOOL_IDENTITY,
                DECLARATION_RESOLVE_TOOL_IDENTITY,
            )
            if self.source_navigation_enabled
            else (PROOF_TOOL_IDENTITY,)
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "identity": self.identity.to_dict(),
            "envelope_version": self.envelope_version,
            "effective_profile_intents": list(self.effective_profile_intents),
            "source_navigation_enabled": self.source_navigation_enabled,
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
        source_navigation_enabled = value.get("source_navigation_enabled")
        if not isinstance(source_navigation_enabled, bool):
            raise ValueError(
                "proof-tool manifest source-navigation capability must be boolean"
            )
        return cls(
            identity=ToolIdentity(
                server=raw_identity.get("server"),
                tool=raw_identity.get("tool"),
            ),
            envelope_version=value.get("envelope_version"),
            effective_profile_intents=tuple(raw_intents),
            source_navigation_enabled=source_navigation_enabled,
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
    *,
    source_navigation_enabled: bool = False,
) -> ProofToolContractManifest:
    """Resolve one immutable contract manifest at node startup."""

    effective = tuple(sorted(
        allowed_runtime_intents(surface_profile) & ALLOWED_AGENT_INTENTS
    ))
    return ProofToolContractManifest(
        identity=PROOF_TOOL_IDENTITY,
        envelope_version=PROOF_TOOL_ENVELOPE_VERSION,
        effective_profile_intents=effective,
        source_navigation_enabled=bool(source_navigation_enabled),
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


def source_read_tool_definition() -> dict[str, Any]:
    """Render the bounded manager-owned EasyCrypt source-read tool."""

    return {
        "name": SOURCE_READ_TOOL_IDENTITY.tool,
        "description": (
            "Read a bounded line range from the proof-stripped EasyCrypt task "
            "or configured EasyCrypt theories through the manager-owned "
            "source boundary. Returns native-Read-style line-numbered text. "
            "This tool does not inspect or mutate proof state."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Repository-relative .ec or .eca path.",
                },
                "start_line": {"type": "integer", "minimum": 1},
                "end_line": {"type": "integer", "minimum": 1},
            },
            "required": ["path"],
            "additionalProperties": False,
        },
    }


def source_search_tool_definition() -> dict[str, Any]:
    """Render the bounded manager-owned EasyCrypt literal-search tool."""

    return {
        "name": SOURCE_SEARCH_TOOL_IDENTITY.tool,
        "description": (
            "Search literal text in the proof-stripped EasyCrypt task and "
            "configured EasyCrypt theories. Returns copy-ready file paths, "
            "line numbers, and optional bounded context. Matches are lexical "
            "candidates, not resolved EasyCrypt declarations. This tool does "
            "not inspect or mutate proof state."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 256,
                    "description": "One literal search string, not a regex.",
                },
                "scope": {
                    "type": "string",
                    "enum": ["all", "task", "libraries"],
                    "default": "all",
                },
                "path": {
                    "type": "string",
                    "description": (
                        "Optional exact repository-relative .ec/.eca file to search."
                    ),
                },
                "case_sensitive": {"type": "boolean", "default": True},
                "max_results": {
                    "type": "integer", "minimum": 1, "maximum": 50,
                    "default": 20,
                },
                "context_lines": {
                    "type": "integer", "minimum": 0, "maximum": 3,
                    "default": 0,
                },
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    }


def declaration_resolve_tool_definition() -> dict[str, Any]:
    """Render exact EasyCrypt-native declaration resolution."""

    return {
        "name": DECLARATION_RESOLVE_TOOL_IDENTITY.tool,
        "description": (
            "Ask EasyCrypt to resolve and print one exact candidate declaration "
            "in the prepared target environment. Use this after lexical source "
            "search when namespace identity matters. This is not fuzzy search "
            "and does not inspect or mutate the current proof state."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 256,
                    "description": (
                        "Exact EasyCrypt identifier, optionally theory-qualified."
                    ),
                },
            },
            "required": ["symbol"],
            "additionalProperties": False,
        },
    }


def proof_tool_definitions(
    manifest: ProofToolContractManifest,
) -> list[dict[str, Any]]:
    """Render exactly the tools enabled by one node manifest."""

    validate_proof_tool_contract(manifest)
    definitions = [proof_tool_definition(manifest)]
    if manifest.source_navigation_enabled:
        definitions.extend((
            source_read_tool_definition(),
            source_search_tool_definition(),
            declaration_resolve_tool_definition(),
        ))
    return definitions


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
