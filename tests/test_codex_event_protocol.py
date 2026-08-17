"""Authority and privacy tests for the Codex JSONL observation boundary."""

from __future__ import annotations

import json

from workflow.codex_event_protocol import (
    CODEX_EXEC_JSONL_CONTRACT,
    observe_codex_exec_jsonl,
)
from workflow.validation.proof_state_compiler_one_step_model import (
    decode_codex_result,
)


def _jsonl(*events: dict) -> str:
    return "\n".join(json.dumps(item) for item in events)


def _completed_stream(*items: dict) -> str:
    return _jsonl(
        {"type": "thread.started", "thread_id": "thread-1"},
        {"type": "turn.started"},
        *items,
        {
            "type": "turn.completed",
            "usage": {"input_tokens": 10, "output_tokens": 2},
        },
    )


def test_structural_audit_does_not_retain_reasoning_or_answer_text() -> None:
    secret_reasoning = "private chain of thought"
    secret_answer = '{"tactic":"proc."}'
    stdout = _completed_stream(
        {
            "type": "item.completed",
            "item": {"type": "reasoning", "text": secret_reasoning},
        },
        {
            "type": "item.completed",
            "item": {"type": "agent_message", "text": secret_answer},
        },
    )

    _events, audit = observe_codex_exec_jsonl(stdout, "")

    assert audit["contract"] == CODEX_EXEC_JSONL_CONTRACT
    assert audit["protocol_valid"]
    assert audit["provider_errors"] == []
    assert audit["protocol_unknowns"] == []
    assert audit["tool_item_types"] == []
    assert secret_reasoning not in repr(audit)
    assert secret_answer not in repr(audit)
    assert audit["reasoning_text_retained"] is False
    assert audit["assistant_text_retained"] is False


def test_error_item_is_provider_error_and_never_relabeled_as_tool() -> None:
    stdout = _completed_stream(
        {
            "type": "item.completed",
            "item": {
                "type": "error",
                "message": "nonfatal provider diagnostic",
                "status": "completed",
            },
        },
        {
            "type": "item.completed",
            "item": {
                "type": "agent_message",
                "text": '{"tactic":"proc."}',
            },
        },
    )

    result = decode_codex_result(
        stdout, "", returncode=0, duration_ms=5, prompt="goal"
    )

    assert result["tactic"] == "proc."
    assert result["tools_observed"] == []
    assert "codex provider error: nonfatal provider diagnostic" in result["error"]
    audit = result["provider_event_audit"]
    assert audit["protocol_valid"]
    assert audit["provider_errors"][0]["message"] == (
        "nonfatal provider diagnostic"
    )


def test_real_capability_item_is_reported_as_forbidden_tool() -> None:
    stdout = _completed_stream(
        {
            "type": "item.completed",
            "item": {
                "type": "mcp_tool_call",
                "server": "example",
                "tool": "lookup",
            },
        },
        {
            "type": "item.completed",
            "item": {
                "type": "agent_message",
                "text": '{"tactic":"proc."}',
            },
        },
    )

    result = decode_codex_result(
        stdout, "", returncode=0, duration_ms=5, prompt="goal"
    )

    assert result["tools_observed"] == ["mcp_tool_call"]
    assert "codex used forbidden tools: mcp_tool_call" in result["error"]
    assert result["provider_event_audit"]["protocol_valid"]


def test_unknown_item_fails_closed_as_protocol_drift_not_tool_use() -> None:
    stdout = _completed_stream(
        {
            "type": "item.completed",
            "item": {"type": "future_item_kind", "status": "completed"},
        },
        {
            "type": "item.completed",
            "item": {
                "type": "agent_message",
                "text": '{"tactic":"proc."}',
            },
        },
    )

    result = decode_codex_result(
        stdout, "", returncode=0, duration_ms=5, prompt="goal"
    )

    assert result["tools_observed"] == []
    assert "unknown codex protocol item" in result["error"]
    assert not result["provider_event_audit"]["protocol_valid"]
    assert result["provider_event_audit"]["protocol_unknowns"][0][
        "item_type"
    ] == "future_item_kind"


def test_invalid_json_and_missing_cardinality_remain_auditable() -> None:
    events, audit = observe_codex_exec_jsonl("not-json\n[]\n", "warning")

    assert events == []
    assert not audit["protocol_valid"]
    assert len(audit["invalid_jsonl_lines"]) == 2
    assert len(audit["cardinality_errors"]) == 3
    assert audit["stderr_bytes"] == len("warning")
    assert audit["stderr_nonempty"] is True
    assert "warning" not in repr(audit)
    assert audit["stderr_text_retained"] is False
