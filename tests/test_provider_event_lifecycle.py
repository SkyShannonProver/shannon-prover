from __future__ import annotations

from workflow.provider.claude_event_normalizer import ClaudeEventNormalizer
from workflow.provider.codex_event_normalizer import (
    audit_codex_event_log,
    audit_codex_invocation,
)
from workflow.proof_tool.proof_tool_contract import resolve_proof_tool_contract
from workflow.provider.provider_event_lifecycle import (
    AgentCapabilityPolicy,
    AgentEventLifecycleGuard,
    LifecycleRequirements,
    audit_normalized_invocation,
)
from workflow.provider.provider_sessions import _watermark_stop_ready


def _codex_event(event_type: str, **item) -> dict:
    value = {"type": event_type}
    if item:
        value["item"] = item
    return value


def _strict_codex_audit(*events: dict, process_exit: int = 0):
    manifest = resolve_proof_tool_contract("l1_goal_projection")
    return audit_codex_invocation(
        events,
        manifest=manifest,
        invocation_id="codex-invocation",
        process_exit=process_exit,
    )


def test_codex_proof_and_empty_metadata_calls_share_strict_lifecycle() -> None:
    audit = _strict_codex_audit(
        {"type": "thread.started", "thread_id": "thread-1"},
        {"type": "turn.started"},
        _codex_event(
            "item.started",
            id="metadata",
            type="mcp_tool_call",
            server="codex",
            tool="list_mcp_resources",
            arguments={"server": "proof_node_manager"},
        ),
        _codex_event(
            "item.completed",
            id="metadata",
            type="mcp_tool_call",
            result={"resources": []},
        ),
        _codex_event(
            "item.started",
            id="proof",
            type="mcp_tool_call",
            server="proof_node_manager",
            tool="submit_proof_intent",
            arguments={"intent": "finish"},
        ),
        _codex_event(
            "item.completed",
            id="proof",
            type="mcp_tool_call",
            result={"content": [{"type": "text", "text": "done"}]},
        ),
        _codex_event(
            "item.completed",
            id="message",
            type="agent_message",
            text="finished",
        ),
        {"type": "turn.completed"},
    )

    assert audit.valid
    assert audit.proof_tool_started == 1
    assert audit.proof_tool_completed == 1
    assert audit.host_metadata_calls == 1


def test_codex_source_navigation_and_proof_intent_share_one_manager_lifecycle() -> None:
    manifest = resolve_proof_tool_contract(
        "l1_goal_projection",
        source_navigation_enabled=True,
    )
    audit = audit_codex_invocation(
        [
            {"type": "thread.started", "thread_id": "thread-1"},
            {"type": "turn.started"},
            _codex_event(
                "item.started",
                id="search",
                type="mcp_tool_call",
                server="proof_node_manager",
                tool="search_easycrypt_source",
                arguments={"query": "target", "scope": "task"},
            ),
            _codex_event(
                "item.completed",
                id="search",
                type="mcp_tool_call",
                result={"content": [{"type": "text", "text": "Target.ec:1"}]},
            ),
            _codex_event(
                "item.started",
                id="resolve",
                type="mcp_tool_call",
                server="proof_node_manager",
                tool="resolve_easycrypt_declaration",
                arguments={"symbol": "target"},
            ),
            _codex_event(
                "item.completed",
                id="resolve",
                type="mcp_tool_call",
                result={"content": [{"type": "text", "text": "lemma target"}]},
            ),
            _codex_event(
                "item.started",
                id="source",
                type="mcp_tool_call",
                server="proof_node_manager",
                tool="read_easycrypt_source",
                arguments={"path": "task/Target.ec"},
            ),
            _codex_event(
                "item.completed",
                id="source",
                type="mcp_tool_call",
                result={"content": [{"type": "text", "text": "lemma target"}]},
            ),
            _codex_event(
                "item.started",
                id="proof",
                type="mcp_tool_call",
                server="proof_node_manager",
                tool="submit_proof_intent",
                arguments={"intent": "finish", "payload": {}},
            ),
            _codex_event(
                "item.completed",
                id="proof",
                type="mcp_tool_call",
                result={"content": [{"type": "text", "text": "done"}]},
            ),
            _codex_event(
                "item.completed",
                id="message",
                type="agent_message",
                text="finished",
            ),
            {"type": "turn.completed"},
        ],
        manifest=manifest,
        invocation_id="codex-source-read",
        process_exit=0,
    )

    assert audit.valid
    assert audit.source_reads == 1
    assert audit.source_searches == 1
    assert audit.declaration_resolutions == 1
    assert audit.proof_tool_completed == 1


def test_codex_allows_progress_message_before_tool_and_final_message() -> None:
    audit = _strict_codex_audit(
        {"type": "thread.started", "thread_id": "thread-1"},
        {"type": "turn.started"},
        _codex_event(
            "item.completed",
            id="progress-message",
            type="agent_message",
            text="I will submit the next proof intent.",
        ),
        _codex_event(
            "item.started",
            id="proof",
            type="mcp_tool_call",
            server="proof_node_manager",
            tool="submit_proof_intent",
            arguments={"intent": "commit_tactic", "payload": {"tactic": "trivial."}},
        ),
        _codex_event(
            "item.completed",
            id="proof",
            type="mcp_tool_call",
            result={"content": [{"type": "text", "text": "accepted"}]},
        ),
        _codex_event(
            "item.completed",
            id="final-message",
            type="agent_message",
            text="The manager accepted the intent.",
        ),
        {"type": "turn.completed"},
    )

    assert audit.valid
    assert audit.proof_tool_started == 1
    assert audit.proof_tool_completed == 1


def test_codex_allows_commentary_message_while_tool_is_pending() -> None:
    audit = _strict_codex_audit(
        {"type": "thread.started", "thread_id": "thread-1"},
        {"type": "turn.started"},
        _codex_event(
            "item.started",
            id="proof",
            type="mcp_tool_call",
            server="proof_node_manager",
            tool="submit_proof_intent",
            arguments={"intent": "commit_tactic", "payload": {"tactic": "trivial."}},
        ),
        _codex_event(
            "item.completed",
            id="commentary",
            type="agent_message",
            text="The manager is checking the tactic.",
        ),
        _codex_event(
            "item.completed",
            id="proof",
            type="mcp_tool_call",
            result={"content": [{"type": "text", "text": "accepted"}]},
        ),
        {"type": "turn.completed"},
    )

    assert audit.valid
    assert audit.proof_tool_started == 1
    assert audit.proof_tool_completed == 1


def test_codex_terminal_still_rejects_pending_tool_after_commentary() -> None:
    audit = _strict_codex_audit(
        {"type": "thread.started", "thread_id": "thread-1"},
        {"type": "turn.started"},
        _codex_event(
            "item.started",
            id="proof",
            type="mcp_tool_call",
            server="proof_node_manager",
            tool="submit_proof_intent",
        ),
        _codex_event(
            "item.completed",
            id="commentary",
            type="agent_message",
            text="Still waiting.",
        ),
        {"type": "turn.completed"},
    )

    assert any("terminal arrived before tool calls completed" in item for item in audit.violations)
    assert any("tool calls did not complete" in item for item in audit.violations)


def test_codex_tool_completion_requires_bound_identity_and_start() -> None:
    missing_id = _strict_codex_audit(
        {"type": "thread.started", "thread_id": "thread-1"},
        _codex_event(
            "item.completed",
            type="mcp_tool_call",
            server="proof_node_manager",
            tool="submit_proof_intent",
        ),
        _codex_event("item.completed", id="message", type="agent_message"),
        {"type": "turn.completed"},
    )
    unmatched = _strict_codex_audit(
        {"type": "thread.started", "thread_id": "thread-1"},
        _codex_event(
            "item.completed",
            id="proof",
            type="mcp_tool_call",
            server="proof_node_manager",
            tool="submit_proof_intent",
        ),
        _codex_event("item.completed", id="message", type="agent_message"),
        {"type": "turn.completed"},
    )

    assert any("missing item identity" in error for error in missing_id.violations)
    assert any("without matching start" in error for error in unmatched.violations)


def test_codex_item_identity_cannot_be_reused() -> None:
    audit = _strict_codex_audit(
        {"type": "thread.started", "thread_id": "thread-1"},
        _codex_event(
            "item.started",
            id="same",
            type="mcp_tool_call",
            server="proof_node_manager",
            tool="submit_proof_intent",
        ),
        _codex_event(
            "item.started",
            id="same",
            type="mcp_tool_call",
            server="proof_node_manager",
            tool="submit_proof_intent",
        ),
        _codex_event(
            "item.completed",
            id="same",
            type="mcp_tool_call",
        ),
        _codex_event("item.completed", id="message", type="agent_message"),
        {"type": "turn.completed"},
    )

    assert any("identity was reused" in error for error in audit.violations)


def test_codex_host_metadata_text_must_be_an_exact_empty_result() -> None:
    audit = _strict_codex_audit(
        {"type": "thread.started", "thread_id": "thread-1"},
        _codex_event(
            "item.started",
            id="metadata",
            type="mcp_tool_call",
            server="codex",
            tool="list_mcp_resources",
            arguments={},
        ),
        _codex_event(
            "item.completed",
            id="metadata",
            type="mcp_tool_call",
            result="No resources; leaked resource URI file:///secret",
        ),
        _codex_event("item.completed", id="message", type="agent_message"),
        {"type": "turn.completed"},
    )

    assert any("non-empty or invalid" in error for error in audit.violations)


def test_bad_json_unknown_items_pending_eof_and_exit_mismatch_fail_closed() -> None:
    manifest = resolve_proof_tool_contract("l1_goal_projection")
    records = [
        "not-json",
        {"type": "thread.started", "thread_id": "thread-1"},
        _codex_event(
            "item.started",
            id="pending",
            type="mcp_tool_call",
            server="proof_node_manager",
            tool="submit_proof_intent",
        ),
        _codex_event("item.completed", id="future", type="future_tool"),
        _codex_event("item.completed", id="message", type="agent_message"),
        {"type": "turn.completed"},
    ]
    audit = audit_codex_invocation(
        records,
        manifest=manifest,
        invocation_id="codex-invocation",
        process_exit=7,
    )

    assert any("invalid Codex JSON" in error for error in audit.violations)
    assert any("unknown Codex item" in error for error in audit.violations)
    assert any("did not complete" in error for error in audit.violations)
    assert any("exited nonzero" in error for error in audit.violations)


def test_claude_normalizer_uses_the_same_invocation_guard() -> None:
    manifest = resolve_proof_tool_contract("l1_goal_projection")
    invocation_id = "claude-invocation"
    normalizer = ClaudeEventNormalizer(
        invocation_id=invocation_id,
        manifest=manifest,
    )
    guard = AgentEventLifecycleGuard(
        invocation_id=invocation_id,
        provider="claude",
        capability_policy=AgentCapabilityPolicy.proof_eval(
            manifest,
            allow_empty_host_metadata=False,
        ),
    )
    records = [
        {"type": "system", "subtype": "init", "session_id": "session-1"},
        {
            "type": "assistant",
            "message": {"content": [{
                "type": "tool_use",
                "id": "proof",
                "name": "mcp__proof_node_manager__submit_proof_intent",
                "input": {"intent": "finish"},
            }]},
        },
        {
            "type": "user",
            "message": {"content": [{
                "type": "tool_result",
                "tool_use_id": "proof",
                "content": "done",
            }]},
        },
        {"type": "result", "subtype": "success", "result": "finished"},
    ]

    audit = audit_normalized_invocation(
        records,
        normalizer=normalizer,
        guard=guard,
        process_exit=0,
    )

    assert audit.valid
    assert audit.proof_tool_started == 1
    assert audit.proof_tool_completed == 1


def test_claude_watermark_waits_for_tool_result_before_context_stop() -> None:
    manifest = resolve_proof_tool_contract("l1_goal_projection")
    invocation_id = "claude-watermark-tool-boundary"
    normalizer = ClaudeEventNormalizer(
        invocation_id=invocation_id,
        manifest=manifest,
    )
    guard = AgentEventLifecycleGuard(
        invocation_id=invocation_id,
        provider="claude",
        capability_policy=AgentCapabilityPolicy.proof_eval(
            manifest,
            allow_empty_host_metadata=False,
        ),
    )

    for raw in (
        {"type": "system", "subtype": "init", "session_id": "session-1"},
        {
            "type": "assistant",
            "message": {"content": [{
                "type": "tool_use",
                "id": "proof",
                "name": "mcp__proof_node_manager__submit_proof_intent",
                "input": {"intent": "commit_tactic", "payload": {"tactic": "skip."}},
            }]},
        },
    ):
        normalized = normalizer.normalize(raw)
        for event in normalized.events:
            assert guard.observe(event).allowed

    assert guard.has_pending_tool_calls
    assert not _watermark_stop_ready(ctx_pressure=True, event_guard=guard)

    completed = normalizer.normalize({
        "type": "user",
        "message": {"content": [{
            "type": "tool_result",
            "tool_use_id": "proof",
            "content": "accepted",
        }]},
    })
    for event in completed.events:
        assert guard.observe(event).allowed

    assert not guard.has_pending_tool_calls
    assert _watermark_stop_ready(ctx_pressure=True, event_guard=guard)
    assert guard.finish(process_exit=-15, cancelled=True).valid


def test_claude_source_navigation_and_proof_intent_share_one_manager_lifecycle() -> None:
    manifest = resolve_proof_tool_contract(
        "l1_goal_projection",
        source_navigation_enabled=True,
    )
    invocation_id = "claude-source-read"
    normalizer = ClaudeEventNormalizer(
        invocation_id=invocation_id,
        manifest=manifest,
    )
    guard = AgentEventLifecycleGuard(
        invocation_id=invocation_id,
        provider="claude",
        capability_policy=AgentCapabilityPolicy.proof_eval(
            manifest,
            allow_empty_host_metadata=False,
        ),
    )
    records = [
        {"type": "system", "subtype": "init", "session_id": "session-1"},
        {
            "type": "assistant",
            "message": {"content": [{
                "type": "tool_use",
                "id": "search",
                "name": "mcp__proof_node_manager__search_easycrypt_source",
                "input": {"query": "target", "scope": "task"},
            }]},
        },
        {
            "type": "user",
            "message": {"content": [{
                "type": "tool_result",
                "tool_use_id": "search",
                "content": "Target.ec:1",
            }]},
        },
        {
            "type": "assistant",
            "message": {"content": [{
                "type": "tool_use",
                "id": "resolve",
                "name": "mcp__proof_node_manager__resolve_easycrypt_declaration",
                "input": {"symbol": "target"},
            }]},
        },
        {
            "type": "user",
            "message": {"content": [{
                "type": "tool_result",
                "tool_use_id": "resolve",
                "content": "lemma target",
            }]},
        },
        {
            "type": "assistant",
            "message": {"content": [{
                "type": "tool_use",
                "id": "source",
                "name": "mcp__proof_node_manager__read_easycrypt_source",
                "input": {"path": "task/Target.ec"},
            }]},
        },
        {
            "type": "user",
            "message": {"content": [{
                "type": "tool_result",
                "tool_use_id": "source",
                "content": "lemma target",
            }]},
        },
        {
            "type": "assistant",
            "message": {"content": [{
                "type": "tool_use",
                "id": "proof",
                "name": "mcp__proof_node_manager__submit_proof_intent",
                "input": {"intent": "finish", "payload": {}},
            }]},
        },
        {
            "type": "user",
            "message": {"content": [{
                "type": "tool_result",
                "tool_use_id": "proof",
                "content": "done",
            }]},
        },
        {"type": "result", "subtype": "success", "result": "finished"},
    ]

    audit = audit_normalized_invocation(
        records,
        normalizer=normalizer,
        guard=guard,
        process_exit=0,
    )

    assert audit.valid
    assert audit.source_reads == 1
    assert audit.source_searches == 1
    assert audit.declaration_resolutions == 1
    assert audit.proof_tool_completed == 1


def test_tool_policy_only_is_still_invocation_bound() -> None:
    manifest = resolve_proof_tool_contract("l1_goal_projection")
    audit = audit_codex_invocation(
        [
            _codex_event(
                "item.started",
                id="shell",
                type="command_execution",
                command="cat target.ec",
            ),
            _codex_event(
                "item.completed",
                id="shell",
                type="command_execution",
            ),
        ],
        manifest=manifest,
        invocation_id="tool-only",
        process_exit=None,
        requirements=LifecycleRequirements.tool_policy_only(),
    )

    assert any("disabled tool" in error for error in audit.violations)


def test_appended_codex_log_resets_identity_state_per_invocation() -> None:
    manifest = resolve_proof_tool_contract("l1_goal_projection")
    records = []
    for thread in ("thread-1", "thread-1"):
        records.extend([
            {"type": "thread.started", "thread_id": thread},
            _codex_event(
                "item.started",
                id="provider-reused-id",
                type="mcp_tool_call",
                server="proof_node_manager",
                tool="submit_proof_intent",
            ),
            _codex_event(
                "item.completed",
                id="provider-reused-id",
                type="mcp_tool_call",
            ),
        ])

    audits = audit_codex_event_log(
        records,
        manifest=manifest,
        requirements=LifecycleRequirements.tool_policy_only(),
    )

    assert len(audits) == 2
    assert all(audit.valid for audit in audits)
    assert [audit.proof_tool_completed for audit in audits] == [1, 1]


def test_valid_cardinality_in_invalid_order_fails_closed() -> None:
    audit = _strict_codex_audit(
        {"type": "turn.started"},
        {"type": "thread.started", "thread_id": "thread-1"},
        _codex_event("item.completed", id="message", type="agent_message"),
        _codex_event(
            "item.started",
            id="late-tool",
            type="mcp_tool_call",
            server="proof_node_manager",
            tool="submit_proof_intent",
        ),
        _codex_event(
            "item.completed",
            id="late-tool",
            type="mcp_tool_call",
        ),
        {"type": "turn.completed"},
    )

    assert any("before invocation start" in error for error in audit.violations)
    assert any("start arrived after other events" in error for error in audit.violations)


def test_controlled_cancel_only_waives_end_of_invocation_cardinality() -> None:
    manifest = resolve_proof_tool_contract("l1_goal_projection")
    normalizer = ClaudeEventNormalizer(
        invocation_id="cancelled-claude",
        manifest=manifest,
    )
    guard = AgentEventLifecycleGuard(
        invocation_id="cancelled-claude",
        provider="claude",
        capability_policy=AgentCapabilityPolicy.proof_eval(
            manifest,
            allow_empty_host_metadata=False,
        ),
    )
    normalized = normalizer.normalize({
        "type": "system",
        "subtype": "init",
        "session_id": "session-1",
    })
    for event in normalized.events:
        guard.observe(event)

    audit = guard.finish(process_exit=-15, cancelled=True)

    assert audit.valid


def _claude_audit(records: list[dict]):
    manifest = resolve_proof_tool_contract("l1_goal_projection")
    invocation_id = "claude-notices"
    normalizer = ClaudeEventNormalizer(
        invocation_id=invocation_id,
        manifest=manifest,
    )
    guard = AgentEventLifecycleGuard(
        invocation_id=invocation_id,
        provider="claude",
        capability_policy=AgentCapabilityPolicy.proof_eval(
            manifest,
            allow_empty_host_metadata=False,
        ),
    )
    return audit_normalized_invocation(
        records,
        normalizer=normalizer,
        guard=guard,
        process_exit=0,
    )


_CLAUDE_PROOF_TURN = [
    {"type": "system", "subtype": "init", "session_id": "session-1"},
    {
        "type": "assistant",
        "message": {"content": [{
            "type": "tool_use",
            "id": "proof",
            "name": "mcp__proof_node_manager__submit_proof_intent",
            "input": {"intent": "finish"},
        }]},
    },
    {
        "type": "user",
        "message": {"content": [{
            "type": "tool_result",
            "tool_use_id": "proof",
            "content": "done",
        }]},
    },
    {"type": "result", "subtype": "success", "result": "finished"},
]


def test_claude_cli_notices_are_position_free() -> None:
    # Claude CLI 2.1.283 emits `commands_changed` before `init` and
    # `post_turn_summary` after the terminal `result`.
    audit = _claude_audit([
        {"type": "system", "subtype": "commands_changed"},
        *_CLAUDE_PROOF_TURN,
        {"type": "system", "subtype": "post_turn_summary"},
    ])

    assert audit.valid, audit.violations
    assert audit.proof_tool_started == 1
    assert audit.provider_notices == (
        "system/commands_changed",
        "system/post_turn_summary",
    )


def test_unknown_claude_record_types_stay_order_checked() -> None:
    # Unknown top-level records may carry content: accepted inside the
    # invocation, rejected after the terminal result.
    inside = _claude_audit([
        *_CLAUDE_PROOF_TURN[:1],
        {"type": "rate_limit_event"},
        *_CLAUDE_PROOF_TURN[1:],
    ])
    after = _claude_audit([
        *_CLAUDE_PROOF_TURN,
        {"type": "stream_event", "event": {"delta": "late"}},
    ])

    assert inside.valid, inside.violations
    assert not after.valid
    assert any("after terminal event" in error for error in after.violations)


def test_claude_content_after_result_still_fails_closed() -> None:
    audit = _claude_audit([
        *_CLAUDE_PROOF_TURN,
        {
            "type": "assistant",
            "message": {"content": [{"type": "text", "text": "late"}]},
        },
    ])

    assert not audit.valid
    assert any("after terminal event" in error for error in audit.violations)


def test_codex_reasoning_after_turn_completed_still_fails_closed() -> None:
    audit = _strict_codex_audit(
        {"type": "thread.started", "thread_id": "thread-1"},
        {"type": "turn.started"},
        _codex_event(
            "item.completed",
            id="message",
            type="agent_message",
            text="finished",
        ),
        {"type": "turn.completed"},
        _codex_event("item.started", id="late", type="reasoning"),
    )

    assert not audit.valid
    assert any("after terminal event" in error for error in audit.violations)
