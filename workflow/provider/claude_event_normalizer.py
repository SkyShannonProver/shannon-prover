"""Claude stream-json normalization into the provider-neutral lifecycle."""
from __future__ import annotations

import json
from typing import Any, Mapping

from workflow.proof_tool.proof_tool_contract import ProofToolContractManifest, ToolIdentity
from workflow.provider.provider_event_lifecycle import (
    AgentEventKind,
    CanonicalAgentEvent,
    EventNormalizationResult,
)


class ClaudeEventNormalizer:
    provider = "claude"

    def __init__(
        self,
        *,
        invocation_id: str,
        manifest: ProofToolContractManifest,
    ) -> None:
        if not invocation_id:
            raise ValueError("Claude normalizer requires an invocation identity")
        self.invocation_id = invocation_id
        self.manifest = manifest

    def normalize(
        self,
        raw: str | Mapping[str, Any],
    ) -> EventNormalizationResult:
        value, error = _parse_record(raw)
        if error:
            return EventNormalizationResult(violations=(error,))
        assert value is not None
        event_type = value.get("type")
        if not isinstance(event_type, str) or not event_type:
            return EventNormalizationResult(
                violations=("Claude event type is missing",)
            )
        base = {
            "invocation_id": self.invocation_id,
            "provider": self.provider,
            "raw_event_type": event_type,
        }
        if event_type == "system":
            if value.get("subtype") == "init":
                session_id = value.get("session_id")
                return _events(CanonicalAgentEvent(
                    **base,
                    kind=AgentEventKind.INVOCATION_STARTED,
                    session_id=session_id if isinstance(session_id, str) else "",
                ))
            # Newer Claude CLI versions emit further system subtypes (status/
            # progress chatter). They carry no tool/protocol semantics; killing
            # the node over vocabulary drift took the whole claude backend down
            # (observed live 2026-08-19: node died in 5s at the first such
            # event). Same policy as the Codex progress-message fix on main.
            return _events(CanonicalAgentEvent(
                **base,
                kind=AgentEventKind.PASSIVE,
            ))
        if event_type == "assistant":
            return self._assistant(value, base)
        if event_type == "user":
            return self._user(value, base)
        if event_type == "result":
            failed = bool(value.get("is_error")) or str(
                value.get("subtype") or ""
            ) in {"error", "failed"}
            events: list[CanonicalAgentEvent] = []
            if isinstance(value.get("result"), str):
                events.append(CanonicalAgentEvent(
                    **base,
                    kind=AgentEventKind.MESSAGE_COMPLETED,
                ))
            events.append(CanonicalAgentEvent(
                **base,
                kind=(
                    AgentEventKind.TERMINAL_FAILED
                    if failed
                    else AgentEventKind.TERMINAL_COMPLETED
                ),
            ))
            return EventNormalizationResult(events=tuple(events))
        # Unknown top-level types are provider chatter, not protocol: the CLI
        # freely grows informational events (`rate_limit_event` killed a live
        # node minutes after the system-subtype fix). The guard's authority is
        # call pairing, ordering, and terminal cardinality — all carried by the
        # known types above; malformed KNOWN types still fail closed.
        return _events(CanonicalAgentEvent(
            **base,
            kind=AgentEventKind.PASSIVE,
        ))

    def _assistant(
        self,
        value: Mapping[str, Any],
        base: Mapping[str, Any],
    ) -> EventNormalizationResult:
        blocks, error = _message_blocks(value)
        if error:
            return EventNormalizationResult(violations=(error,))
        events: list[CanonicalAgentEvent] = []
        for block in blocks:
            block_type = block.get("type")
            if block_type in {"text", "thinking"}:
                events.append(CanonicalAgentEvent(
                    **base,
                    kind=AgentEventKind.PASSIVE,
                ))
                continue
            if block_type != "tool_use":
                return EventNormalizationResult(violations=(
                    f"unknown Claude assistant block {block_type!r}",
                ))
            name = block.get("name")
            tool, capability = _claude_tool_identity(name)
            events.append(CanonicalAgentEvent(
                **base,
                kind=AgentEventKind.TOOL_STARTED,
                item_id=(
                    block.get("id") if isinstance(block.get("id"), str) else ""
                ),
                tool=tool,
                capability=capability,
                raw_arguments=block.get("input"),
            ))
        return EventNormalizationResult(events=tuple(events))

    def _user(
        self,
        value: Mapping[str, Any],
        base: Mapping[str, Any],
    ) -> EventNormalizationResult:
        blocks, error = _message_blocks(value)
        if error:
            return EventNormalizationResult(violations=(error,))
        events: list[CanonicalAgentEvent] = []
        for block in blocks:
            block_type = block.get("type")
            if block_type != "tool_result":
                return EventNormalizationResult(violations=(
                    f"unknown Claude user block {block_type!r}",
                ))
            events.append(CanonicalAgentEvent(
                **base,
                kind=AgentEventKind.TOOL_COMPLETED,
                item_id=(
                    block.get("tool_use_id")
                    if isinstance(block.get("tool_use_id"), str)
                    else ""
                ),
            ))
        return EventNormalizationResult(events=tuple(events))


def _parse_record(
    raw: str | Mapping[str, Any],
) -> tuple[Mapping[str, Any] | None, str]:
    if isinstance(raw, str):
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            return None, f"invalid Claude JSON event: {exc}"
    else:
        value = raw
    if not isinstance(value, Mapping):
        return None, "Claude JSON event is not an object"
    return value, ""


def _message_blocks(
    value: Mapping[str, Any],
) -> tuple[list[Mapping[str, Any]], str]:
    message = value.get("message")
    if not isinstance(message, Mapping):
        return [], "Claude message event is missing message object"
    content = message.get("content")
    if not isinstance(content, list):
        return [], "Claude message content is not a list"
    if not all(isinstance(block, Mapping) for block in content):
        return [], "Claude message content contains a non-object block"
    return list(content), ""


def _claude_tool_identity(value: Any) -> tuple[ToolIdentity | None, str]:
    if not isinstance(value, str) or not value:
        return None, ""
    if value.startswith("mcp__"):
        parts = value.split("__", 2)
        if len(parts) == 3 and parts[1] and parts[2]:
            return ToolIdentity(parts[1], parts[2]), "mcp_tool"
        return None, "mcp_tool"
    return ToolIdentity("claude", value), f"provider_tool:{value}"


def _events(*events: CanonicalAgentEvent) -> EventNormalizationResult:
    return EventNormalizationResult(events=events)
