"""Codex JSONL normalization into the provider-neutral event lifecycle."""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from typing import Any, Iterable, Mapping

from workflow.proof_tool.proof_tool_contract import (
    ProofToolContractManifest,
    ToolIdentity,
    resolve_proof_tool_contract,
)
from workflow.provider.provider_event_lifecycle import (
    AgentCapabilityPolicy,
    AgentEventKind,
    AgentEventLifecycleGuard,
    CanonicalAgentEvent,
    EventNormalizationResult,
    HOST_METADATA_CAPABILITY,
    InvocationEventAudit,
    LifecycleRequirements,
    audit_normalized_invocation,
)


CODEX_HOST_IDENTITY = "codex"
CODEX_HOST_METADATA_TOOLS = frozenset({
    "list_mcp_resources",
    "list_mcp_resource_templates",
})
_CODEX_TOOL_ITEMS = frozenset({
    "command_execution",
    "file_change",
    "mcp_tool_call",
    "todo_list",
    "web_search",
})
CODEX_EXEC_JSONL_CONTRACT = "codex_exec_jsonl.v2"


def codex_event_text(value: Mapping[str, Any]) -> str:
    """Extract bounded provider diagnostic/assistant text from one raw event."""

    for key in (
        "text",
        "summary",
        "message",
        "aggregated_output",
        "output",
        "result",
        "error",
    ):
        item = value.get(key)
        if isinstance(item, str) and item.strip():
            return item.strip()
        if isinstance(item, list) and item and all(
            isinstance(part, str) for part in item
        ):
            joined = "\n".join(part for part in item if part.strip()).strip()
            if joined:
                return joined
        if isinstance(item, (dict, list)) and item:
            try:
                return json.dumps(item, ensure_ascii=False, sort_keys=True)
            except (TypeError, ValueError):
                return str(item)
    return ""


class CodexEventNormalizer:
    """Normalize one exact ``codex exec --json`` invocation."""

    provider = "codex"

    def __init__(
        self,
        *,
        invocation_id: str,
        manifest: ProofToolContractManifest,
    ) -> None:
        if not invocation_id:
            raise ValueError("Codex normalizer requires an invocation identity")
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
                violations=("Codex event type is missing",)
            )
        base = {
            "invocation_id": self.invocation_id,
            "provider": self.provider,
            "raw_event_type": event_type,
        }
        if event_type == "thread.started":
            thread_id = value.get("thread_id")
            return _one(CanonicalAgentEvent(
                **base,
                kind=AgentEventKind.INVOCATION_STARTED,
                session_id=thread_id if isinstance(thread_id, str) else "",
            ))
        if event_type == "turn.started":
            return _one(CanonicalAgentEvent(
                **base,
                kind=AgentEventKind.TURN_STARTED,
            ))
        if event_type == "turn.completed":
            return _one(CanonicalAgentEvent(
                **base,
                kind=AgentEventKind.TERMINAL_COMPLETED,
            ))
        if event_type == "turn.failed":
            return _one(CanonicalAgentEvent(
                **base,
                kind=AgentEventKind.TERMINAL_FAILED,
            ))
        if event_type == "error":
            return _one(CanonicalAgentEvent(
                **base,
                kind=AgentEventKind.PROVIDER_ERROR,
            ))
        if event_type not in {"item.started", "item.completed"}:
            return EventNormalizationResult(violations=(
                f"unknown Codex event type {event_type!r}",
            ))
        item = value.get("item")
        if not isinstance(item, Mapping):
            return EventNormalizationResult(violations=(
                "Codex item event is missing an object item",
            ))
        return self._normalize_item(event_type, item, base)

    def _normalize_item(
        self,
        event_type: str,
        item: Mapping[str, Any],
        base: Mapping[str, Any],
    ) -> EventNormalizationResult:
        item_type = item.get("type")
        if not isinstance(item_type, str) or not item_type:
            return EventNormalizationResult(violations=(
                "Codex item type is missing",
            ))
        item_id = item.get("id")
        item_id = item_id if isinstance(item_id, str) else ""
        if item_type == "error":
            return _one(CanonicalAgentEvent(
                **base,
                kind=AgentEventKind.PROVIDER_ERROR,
                item_id=item_id,
            ))
        if item_type == "agent_message":
            kind = (
                AgentEventKind.MESSAGE_COMPLETED
                if event_type == "item.completed"
                else AgentEventKind.PASSIVE
            )
            return _one(CanonicalAgentEvent(
                **base,
                kind=kind,
                item_id=item_id,
            ))
        if item_type == "reasoning":
            return _one(CanonicalAgentEvent(
                **base,
                kind=AgentEventKind.PASSIVE,
                item_id=item_id,
            ))
        if item_type not in _CODEX_TOOL_ITEMS:
            return EventNormalizationResult(violations=(
                f"unknown Codex item type {item_type!r}",
            ))

        tool, capability = self._tool_identity(item_type, item)
        common: dict[str, Any] = {
            **base,
            "item_id": item_id,
            "tool": tool,
            "capability": capability,
        }
        if event_type == "item.started":
            raw_arguments = _raw_arguments(item)
            common["raw_arguments"] = raw_arguments
            if capability == HOST_METADATA_CAPABILITY:
                common["host_metadata_arguments_valid"] = (
                    _valid_host_metadata_arguments(
                        raw_arguments,
                        private_server=self.manifest.identity.server,
                    )
                )
            return _one(CanonicalAgentEvent(
                **common,
                kind=AgentEventKind.TOOL_STARTED,
            ))

        result = item.get("result")
        if result is None:
            result = item.get("output")
        # A completion may omit server/tool; the generic lifecycle guard binds
        # it to the exact pending start by item identity.
        common["host_metadata_result_empty"] = _empty_host_metadata_result(result)
        return _one(CanonicalAgentEvent(
            **common,
            kind=AgentEventKind.TOOL_COMPLETED,
        ))

    def _tool_identity(
        self,
        item_type: str,
        item: Mapping[str, Any],
    ) -> tuple[ToolIdentity | None, str]:
        if item_type != "mcp_tool_call":
            return ToolIdentity("codex", item_type), f"provider_tool:{item_type}"
        server = item.get("server")
        tool = item.get("tool")
        if not isinstance(tool, str) or not tool:
            tool = item.get("name")
        identity = (
            ToolIdentity(server, tool)
            if isinstance(server, str) and server and isinstance(tool, str) and tool
            else None
        )
        if identity is None:
            # Codex completion records may retain only the item id/result.  The
            # lifecycle guard binds that completion to the exact pending start;
            # starts without identity still fail there.
            return None, ""
        if (
            identity.server == CODEX_HOST_IDENTITY
            and identity.tool in CODEX_HOST_METADATA_TOOLS
        ):
            return identity, HOST_METADATA_CAPABILITY
        return identity, "mcp_tool"


def audit_codex_invocation(
    records: Iterable[str | Mapping[str, Any]],
    *,
    manifest: ProofToolContractManifest,
    invocation_id: str,
    process_exit: int | None,
    requirements: LifecycleRequirements | None = None,
) -> InvocationEventAudit:
    normalizer = CodexEventNormalizer(
        invocation_id=invocation_id,
        manifest=manifest,
    )
    guard = AgentEventLifecycleGuard(
        invocation_id=invocation_id,
        provider="codex",
        capability_policy=AgentCapabilityPolicy.proof_eval(manifest),
        requirements=(
            requirements
            if requirements is not None
            else LifecycleRequirements(require_turn_started=True)
        ),
    )
    return audit_normalized_invocation(
        records,
        normalizer=normalizer,
        guard=guard,
        process_exit=process_exit,
    )


def audit_codex_event_log(
    records: Iterable[str | Mapping[str, Any]],
    *,
    manifest: ProofToolContractManifest,
    requirements: LifecycleRequirements | None = None,
    process_exits: Iterable[int | None] | None = None,
) -> tuple[InvocationEventAudit, ...]:
    """Audit an append log as distinct invocation-bound Codex streams.

    ``codex exec resume`` appends another ``thread.started`` stream to the same
    diagnostic file.  Pending identities and terminal cardinality must never be
    shared across those process invocations.
    """

    segments: list[tuple[str, list[str | Mapping[str, Any]]]] = []
    current: list[str | Mapping[str, Any]] = []
    current_has_start = False
    current_declared_id = ""
    for raw in records:
        event_type = _raw_event_type(raw)
        declared_id = _raw_invocation_id(raw)
        identity_changed = bool(
            declared_id
            and current_declared_id
            and declared_id != current_declared_id
        )
        if current and (identity_changed or (
            event_type == "thread.started" and current_has_start
        )):
            segments.append((current_declared_id, current))
            current = []
            current_has_start = False
            current_declared_id = ""
        current.append(raw)
        if declared_id:
            if current_declared_id and declared_id != current_declared_id:
                raise ValueError("Codex event segment crossed invocation identity")
            current_declared_id = declared_id
        if event_type == "thread.started":
            current_has_start = True
    if current:
        segments.append((current_declared_id, current))
    exits = list(process_exits) if process_exits is not None else []
    if exits and len(exits) != len(segments):
        raise ValueError("Codex process-exit cardinality does not match invocations")
    return tuple(
        audit_codex_invocation(
            segment,
            manifest=manifest,
            invocation_id=(
                declared_id or f"offline-codex-invocation-{index + 1}"
            ),
            process_exit=(exits[index] if exits else None),
            requirements=requirements,
        )
        for index, (declared_id, segment) in enumerate(segments)
    )


def observe_codex_jsonl_invocation(
    stdout: str,
    stderr: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Return raw parsed events plus a redacted structural lifecycle audit."""

    manifest = resolve_proof_tool_contract(None)
    invocation_id = "offline-codex-structural"
    normalizer = CodexEventNormalizer(
        invocation_id=invocation_id,
        manifest=manifest,
    )
    guard = AgentEventLifecycleGuard(
        invocation_id=invocation_id,
        provider="codex",
        capability_policy=AgentCapabilityPolicy(allow_all_known_tools=True),
        requirements=LifecycleRequirements(
            require_turn_started=True,
            require_process_exit=False,
            fail_on_provider_error=False,
        ),
    )
    events: list[dict[str, Any]] = []
    invalid_lines: list[dict[str, Any]] = []
    normalization_errors: list[str] = []
    event_type_counts: Counter[str] = Counter()
    item_type_counts: Counter[str] = Counter()
    category_counts: Counter[str] = Counter()
    structural_trace: list[dict[str, Any]] = []
    provider_errors: list[dict[str, Any]] = []
    protocol_unknowns: list[dict[str, Any]] = []
    tool_item_types: set[str] = set()
    completed_agent_message_count = 0

    for line_number, line in enumerate(stdout.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            reason = f"invalid Codex JSON event: {exc}"
            invalid_lines.append({
                "line": line_number,
                "error": str(exc),
                "line_sha256": _sha256(line),
            })
            normalization_errors.append(reason)
            guard.record_violation(reason)
            continue
        if not isinstance(value, dict):
            reason = "Codex JSON event is not an object"
            invalid_lines.append({
                "line": line_number,
                "error": "JSONL event is not an object",
                "line_sha256": _sha256(line),
            })
            normalization_errors.append(reason)
            guard.record_violation(reason)
            continue
        events.append(value)
        index = len(events) - 1
        event_type = str(value.get("type") or "")
        item = value.get("item")
        item = item if isinstance(item, Mapping) else {}
        item_type = str(item.get("type") or "")
        status = str(item.get("status") or value.get("status") or "")
        event_type_counts[event_type or "<missing>"] += 1
        if item_type:
            item_type_counts[item_type] += 1

        normalized = normalizer.normalize(value)
        for reason in normalized.violations:
            normalization_errors.append(reason)
            guard.record_violation(reason)
            protocol_unknowns.append({
                "index": index,
                "event_type": event_type,
                "item_type": item_type,
                "reason": reason,
            })
        categories = {_canonical_category(event, item_type) for event in normalized.events}
        category = next(iter(categories)) if len(categories) == 1 else (
            "unknown_event" if not categories else "mixed"
        )
        category_counts[category] += 1
        trace: dict[str, Any] = {
            "index": index,
            "event_type": event_type,
            "category": category,
        }
        if item_type:
            trace["item_type"] = item_type
        if status:
            trace["status"] = status
        structural_trace.append(trace)
        for canonical in normalized.events:
            guard.observe(canonical)
            if canonical.kind in {
                AgentEventKind.TOOL_STARTED,
                AgentEventKind.TOOL_COMPLETED,
            }:
                if item_type:
                    tool_item_types.add(item_type)
            elif canonical.kind == AgentEventKind.MESSAGE_COMPLETED:
                completed_agent_message_count += 1
            elif canonical.kind == AgentEventKind.PROVIDER_ERROR:
                message = codex_event_text(item or value)
                provider_errors.append({
                    **trace,
                    "message": message[:2000],
                    "message_sha256": _sha256(message),
                })

    lifecycle = guard.finish(process_exit=None)
    cardinality_errors = list(lifecycle.violations)
    for reason in normalization_errors:
        try:
            cardinality_errors.remove(reason)
        except ValueError:
            pass
    audit = {
        "contract": CODEX_EXEC_JSONL_CONTRACT,
        "protocol_valid": not (
            invalid_lines or protocol_unknowns or cardinality_errors
        ),
        "stdout_sha256": _sha256(stdout),
        "stdout_bytes": len(stdout.encode("utf-8")),
        "stderr_sha256": _sha256(stderr),
        "stderr_bytes": len(stderr.encode("utf-8")),
        "stderr_nonempty": bool(stderr.strip()),
        "parsed_event_count": len(events),
        "completed_agent_message_count": completed_agent_message_count,
        "invalid_jsonl_lines": invalid_lines,
        "event_type_counts": dict(sorted(event_type_counts.items())),
        "item_type_counts": dict(sorted(item_type_counts.items())),
        "category_counts": dict(sorted(category_counts.items())),
        "structural_trace": structural_trace,
        "tool_item_types": sorted(tool_item_types),
        "provider_errors": provider_errors,
        "protocol_unknowns": protocol_unknowns,
        "cardinality_errors": cardinality_errors,
        "reasoning_text_retained": False,
        "assistant_text_retained": False,
        "stderr_text_retained": False,
    }
    return events, audit


def _parse_record(
    raw: str | Mapping[str, Any],
) -> tuple[Mapping[str, Any] | None, str]:
    if isinstance(raw, str):
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            return None, f"invalid Codex JSON event: {exc}"
    else:
        value = raw
    if not isinstance(value, Mapping):
        return None, "Codex JSON event is not an object"
    return value, ""


def _raw_event_type(raw: str | Mapping[str, Any]) -> str:
    value, error = _parse_record(raw)
    if error or value is None:
        return ""
    event_type = value.get("type")
    return event_type if isinstance(event_type, str) else ""


def _raw_invocation_id(raw: str | Mapping[str, Any]) -> str:
    value, error = _parse_record(raw)
    if error or value is None:
        return ""
    invocation_id = value.get("_shannon_invocation_id")
    return invocation_id if isinstance(invocation_id, str) else ""


def _canonical_category(event: CanonicalAgentEvent, item_type: str) -> str:
    if event.kind in {
        AgentEventKind.TOOL_STARTED,
        AgentEventKind.TOOL_COMPLETED,
    }:
        return "tool"
    if event.kind == AgentEventKind.MESSAGE_COMPLETED:
        return "assistant_message"
    if event.kind == AgentEventKind.PROVIDER_ERROR:
        return "provider_error"
    if event.kind == AgentEventKind.PASSIVE and item_type == "reasoning":
        return "reasoning"
    return "lifecycle"


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _one(event: CanonicalAgentEvent) -> EventNormalizationResult:
    return EventNormalizationResult(events=(event,))


def _raw_arguments(item: Mapping[str, Any]) -> Any:
    if "arguments" in item:
        return item.get("arguments")
    return item.get("input")


def _valid_host_metadata_arguments(
    raw: Any,
    *,
    private_server: str,
) -> bool:
    if raw in (None, ""):
        return True
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return False
    if not isinstance(raw, Mapping):
        return False
    if set(raw) - {"server", "cursor"}:
        return False
    server = raw.get("server")
    if server not in (None, "", private_server):
        return False
    cursor = raw.get("cursor")
    return cursor is None or isinstance(cursor, str)


_EXACT_EMPTY_METADATA_TEXT = frozenset({
    "method not found",
    "mcp method not found",
    "unknown mcp method",
    "no resources",
    "no resources found",
    "no mcp resources",
    "no resource templates",
    "no resource templates found",
    "no mcp resource templates",
    "does not support resources",
    "does not support resource templates",
})


def _empty_host_metadata_result(value: Any) -> bool:
    """Recognize only exact structured/textual empty discovery results."""

    if value in (None, "", [], {}):
        return True
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return True
        try:
            decoded = json.loads(text)
        except json.JSONDecodeError:
            return " ".join(text.lower().split()) in _EXACT_EMPTY_METADATA_TEXT
        return _empty_host_metadata_result(decoded)
    if isinstance(value, list):
        return all(_empty_host_metadata_result(member) for member in value)
    if not isinstance(value, Mapping):
        return False
    for key, member in value.items():
        normalized = str(key).replace("_", "").lower()
        if normalized in {"resources", "resourcetemplates"}:
            if member not in (None, [], {}):
                return False
            continue
        if normalized in {"uri", "resource", "resourcelink"}:
            return False
        if normalized in {
            "content",
            "structuredcontent",
            "result",
            "output",
            "error",
            "message",
            "text",
        }:
            if not _empty_host_metadata_result(member):
                return False
            continue
        if normalized == "type":
            if member != "text":
                return False
            continue
        if normalized == "iserror":
            if not isinstance(member, bool):
                return False
            continue
        if normalized == "code":
            if member != -32601:
                return False
            continue
        if normalized in {"nextcursor", "cursor"}:
            if member not in (None, ""):
                return False
            continue
        if normalized == "status":
            if member not in (None, "", "unsupported", "completed", "error"):
                return False
            continue
        return False
    return True
