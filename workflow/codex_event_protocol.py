"""Typed observation boundary for ``codex exec --json`` event streams.

The Codex CLI stream contains assistant content, lifecycle records, tool
activity, provider errors, and occasionally new protocol variants.  Consumers
must not infer one class from another: in particular an ``item`` whose type is
``error`` is provider evidence, not a tool call.

This module deliberately retains hashes and a redacted structural trace rather
than reasoning or assistant-message text.  Provider-error text is retained
because it is required to decide whether a model sample is valid.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from typing import Any, Mapping


CODEX_EXEC_JSONL_CONTRACT = "codex_exec_jsonl.v1"

_LIFECYCLE_EVENT_TYPES = frozenset({
    "thread.started",
    "turn.started",
    "turn.completed",
})
_TERMINAL_ERROR_EVENT_TYPES = frozenset({"error", "turn.failed"})
_ITEM_EVENT_TYPES = frozenset({"item.started", "item.completed"})
_CONTENT_ITEM_TYPES = frozenset({"agent_message", "reasoning"})
# These items represent an agent capability invocation rather than passive
# model output.  The one-step experiments disable all of them, so observing
# any one is a policy violation even when the provider protocol is well formed.
CODEX_TOOL_ITEM_TYPES = frozenset({
    "command_execution",
    "file_change",
    "mcp_tool_call",
    "todo_list",
    "web_search",
})
_PROVIDER_ERROR_ITEM_TYPES = frozenset({"error"})


def observe_codex_exec_jsonl(
    stdout: str,
    stderr: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Parse a one-shot Codex JSONL stream and return a redacted audit.

    ``protocol_valid`` means the stream was structurally understood and has
    the expected one-shot cardinality.  It does not mean the provider turn was
    successful or that the agent obeyed the no-tools experiment policy; those
    facts are reported separately.
    """

    events: list[dict[str, Any]] = []
    invalid_lines: list[dict[str, Any]] = []
    for line_number, line in enumerate(stdout.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            invalid_lines.append({
                "line": line_number,
                "error": str(exc),
                "line_sha256": _sha256(line),
            })
            continue
        if not isinstance(value, dict):
            invalid_lines.append({
                "line": line_number,
                "error": "JSONL event is not an object",
                "line_sha256": _sha256(line),
            })
            continue
        events.append(value)

    event_type_counts: Counter[str] = Counter()
    item_type_counts: Counter[str] = Counter()
    category_counts: Counter[str] = Counter()
    structural_trace: list[dict[str, Any]] = []
    provider_errors: list[dict[str, Any]] = []
    protocol_unknowns: list[dict[str, Any]] = []
    tool_item_types: set[str] = set()
    completed_agent_message_count = 0

    for index, event in enumerate(events):
        event_type = str(event.get("type") or "")
        item = event.get("item")
        item = item if isinstance(item, Mapping) else {}
        item_type = str(item.get("type") or "")
        status = str(item.get("status") or event.get("status") or "")
        category = codex_event_category(event_type, item_type)
        event_type_counts[event_type or "<missing>"] += 1
        if item_type:
            item_type_counts[item_type] += 1
        category_counts[category] += 1
        trace_item: dict[str, Any] = {
            "index": index,
            "event_type": event_type,
            "category": category,
        }
        if item_type:
            trace_item["item_type"] = item_type
        if status:
            trace_item["status"] = status
        structural_trace.append(trace_item)

        if category == "tool":
            tool_item_types.add(item_type)
        elif (
            category == "assistant_message"
            and event_type == "item.completed"
        ):
            completed_agent_message_count += 1
        elif category == "provider_error":
            message = codex_event_text(item or event)
            provider_errors.append({
                **trace_item,
                "message": message[:2000],
                "message_sha256": _sha256(message),
            })
        elif category in {"unknown_event", "unknown_item"}:
            protocol_unknowns.append(trace_item)

    terminal_count = (
        event_type_counts["turn.completed"]
        + event_type_counts["turn.failed"]
    )
    cardinality_errors: list[str] = []
    if event_type_counts["thread.started"] != 1:
        cardinality_errors.append("expected exactly one thread.started event")
    if terminal_count != 1:
        cardinality_errors.append("expected exactly one terminal turn event")
    if completed_agent_message_count != 1:
        cardinality_errors.append(
            "expected exactly one completed agent_message item"
        )

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


def codex_event_text(value: Mapping[str, Any]) -> str:
    """Extract bounded diagnostic text from a Codex event or item."""

    for key in (
        "text",
        "message",
        "aggregated_output",
        "output",
        "result",
        "error",
    ):
        item = value.get(key)
        if isinstance(item, str) and item.strip():
            return item.strip()
        if isinstance(item, (dict, list)) and item:
            try:
                return json.dumps(item, ensure_ascii=False, sort_keys=True)
            except (TypeError, ValueError):
                return str(item)
    return ""


def codex_event_category(event_type: str, item_type: str) -> str:
    """Classify one already-parsed event without inspecting its text."""

    if event_type in _TERMINAL_ERROR_EVENT_TYPES:
        return "provider_error"
    if event_type in _LIFECYCLE_EVENT_TYPES:
        return "lifecycle"
    if event_type not in _ITEM_EVENT_TYPES:
        return "unknown_event"
    if item_type == "agent_message":
        return "assistant_message"
    if item_type == "reasoning":
        return "reasoning"
    if item_type in CODEX_TOOL_ITEM_TYPES:
        return "tool"
    if item_type in _PROVIDER_ERROR_ITEM_TYPES:
        return "provider_error"
    return "unknown_item"


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
