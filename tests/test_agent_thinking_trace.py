from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from workflow.validation.agent_thinking_trace import (  # noqa: E402
    extract_turns,
    write_node_thinking,
)
from workflow.validation.agent_view_timeline_report import (  # noqa: E402
    RunSpec,
    build_report,
    render_markdown,
)


def _assistant(ts: str, *blocks: dict) -> dict:
    return {"type": "assistant", "timestamp": ts, "message": {"content": list(blocks)}}


def _thinking(text: str) -> dict:
    return {"type": "thinking", "thinking": text}


def _submit(intent: str, **payload) -> dict:
    return {
        "type": "tool_use",
        "name": "mcp__proof_node_manager__submit_proof_intent",
        "input": {"intent": intent, "payload": payload},
    }


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


def _transcript(path: Path) -> None:
    """Mix the two real shapes: thinking + tool_use in one event, and thinking in
    a separate streamed event before the tool_use."""
    _write_jsonl(path, [
        _assistant(
            "2026-05-30T23:07:00Z",
            _thinking("reason for checkpoint rewind"),
            _submit("undo_to_checkpoint", checkpoint_id="before_call"),
        ),
        _assistant("2026-05-30T23:07:30Z", _thinking("reason for commit")),
        _assistant(
            "2026-05-30T23:07:31Z",
            _submit("commit_tactic", tactic="byequiv => //."),
        ),
        _assistant(
            "2026-05-30T23:08:00Z",
            _thinking("reason for current goal request"),
            _submit("goal_info"),
        ),
    ])


def test_extract_turns_pairs_thinking_across_event_shapes(tmp_path: Path) -> None:
    tpath = tmp_path / "sess.jsonl"
    _transcript(tpath)
    turns = extract_turns(tpath)
    assert [t.intent for t in turns] == [
        "undo_to_checkpoint", "commit_tactic", "goal_info",
    ]
    assert [t.key for t in turns] == [
        '{"checkpoint_id": "before_call"}',
        "byequiv => //.",
        "",
    ]
    # thinking is paired even when it streamed in a separate event from the submit
    assert turns[1].thinking == "reason for commit"
    assert turns[2].thinking == "reason for current goal request"


def test_write_node_thinking_uses_recorded_session(tmp_path: Path) -> None:
    node_dir = tmp_path / "node_memory" / "Tree_0_0"
    node_dir.mkdir(parents=True)
    tpath = tmp_path / "sess.jsonl"
    _transcript(tpath)
    # the run-time correlation pointer (Part A)
    _write_jsonl(node_dir / "agent_sessions.jsonl", [
        {"kind": "agent_session", "session_id": "sess", "transcript_path": str(tpath)},
    ])

    result = write_node_thinking(node_dir)
    assert result.discovery == "recorded_session_id"
    assert result.turns_written == 3
    assert (node_dir / "thinking" / "turn_002.md").exists()
    # turn index aligns with submit order; md carries the intent/payload header
    body = (node_dir / "thinking" / "turn_002.md").read_text(encoding="utf-8")
    assert "reason for commit" in body
    assert "commit_tactic" in body
    index = json.loads((node_dir / "thinking" / "index.json").read_text(encoding="utf-8"))
    assert index["turns"][0]["payload_key"] == '{"checkpoint_id": "before_call"}'
    assert index["turns"][2]["intent"] == "goal_info"


def _node_with_thinking(run_dir: Path) -> None:
    node_dir = run_dir / "node_memory" / "Tree_0_0"
    _write_jsonl(node_dir / "timeline.jsonl", [
        {"kind": "manager_turn", "node": "Tree-0.0", "turn": 1,
         "time": "2026-05-30T23:07:01Z",
         "intent": {"intent": "undo_to_checkpoint", "payload": {"checkpoint_id": "before_call"}},
         "manager_actions": [{"action": "checkpoint rewind", "timing": "1.5 s"}], "ok": True},
        {"kind": "manager_turn", "node": "Tree-0.0", "turn": 2,
         "time": "2026-05-30T23:07:31Z",
         "intent": {"intent": "commit_tactic", "payload": {"tactic": "byequiv => //."}},
         "manager_actions": [{"action": "tactic commit", "timing": "250 ms"}], "ok": True},
    ])
    for turn, intent, payload in [
        (1, "undo_to_checkpoint", {"checkpoint_id": "before_call"}),
        (2, "commit_tactic", {"tactic": "byequiv => //."}),
    ]:
        path = node_dir / "manager_results" / f"turn_{turn:03d}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({
            "turn": turn,
            "handled_intent": {"intent": intent, "payload": payload},
            "ok": True,
        }), encoding="utf-8")
    thinking = node_dir / "thinking"
    thinking.mkdir(parents=True, exist_ok=True)
    (thinking / "turn_001.md").write_text("# t1\nthought one\n", encoding="utf-8")
    (thinking / "turn_002.md").write_text("# t2\nthought two\n", encoding="utf-8")
    (thinking / "index.json").write_text(json.dumps({"node": "Tree-0.0", "turns": [
        {"turn": 1, "intent": "undo_to_checkpoint",
         "payload_key": '{"checkpoint_id": "before_call"}',
         "file": "thinking/turn_001.md"},
        # deliberate mismatch: wrong tactic recorded for turn 2 → must NOT link
        {"turn": 2, "intent": "commit_tactic", "payload_key": "WRONG.",
         "file": "thinking/turn_002.md"},
    ]}), encoding="utf-8")


def test_timeline_links_thinking_and_guards_intent_mismatch(tmp_path: Path) -> None:
    run_dir = tmp_path / "2026-05-30_step4" / "iteration_1"
    _node_with_thinking(run_dir)
    report = build_report([RunSpec(label="run", path=run_dir)])
    rows = report["runs"][0]["rows"]
    # turn 1 matches → path populated; turn 2 payload_key mismatches → no path
    assert rows[0]["agent_think_path"].endswith("thinking/turn_001.md")
    assert rows[1]["agent_think_path"] == ""

    markdown = render_markdown(report)
    assert "thinking/turn_001.md)" in markdown
    assert "thinking/turn_002.md" not in markdown


def test_session_chain_resolves_from_canonical_registry_without_scan(
    tmp_path: Path,
) -> None:
    """When the runtime registered EVERY session (registration-at-creation),
    chain assembly must resolve the full chain from agent_sessions.jsonl alone —
    the ~/.claude mtime-window sweep must not run."""
    import workflow.validation.agent_thinking_trace as att

    node_dir = tmp_path / "node_memory" / "Tree_0_0"
    tactics = [f"tac_{i}." for i in range(1, 7)]
    _write_jsonl(node_dir / "timeline.jsonl", [
        {"kind": "manager_turn", "node": "Tree-0.0", "turn": i,
         "time": f"2026-06-10T10:0{i}:00Z",
         "intent": {"intent": "commit_tactic", "payload": {"tactic": tac}},
         "ok": True}
        for i, tac in enumerate(tactics, start=1)
    ])
    sess1 = tmp_path / "sess1.jsonl"
    _write_jsonl(sess1, [
        _assistant(f"2026-06-10T10:0{i}:00Z",
                   _thinking(f"think {i}"),
                   _submit("commit_tactic", tactic=tac))
        for i, tac in enumerate(tactics[:3], start=1)
    ])
    sess2 = tmp_path / "sess2.jsonl"
    _write_jsonl(sess2, [
        _assistant(f"2026-06-10T10:0{i}:00Z",
                   _thinking(f"think {i}"),
                   _submit("commit_tactic", tactic=tac))
        for i, tac in enumerate(tactics[3:], start=4)
    ])
    # Canonical registry: BOTH links registered at creation time.
    _write_jsonl(node_dir / "agent_sessions.jsonl", [
        {"kind": "agent_session", "session_id": "sess1",
         "transcript_path": str(sess1)},
        {"kind": "agent_session", "session_id": "sess2",
         "transcript_path": str(sess2)},
    ])

    def _no_scan(*a, **k):
        raise AssertionError(
            "global ~/.claude scan must not run when the registry is complete"
        )

    real_pool = att._candidate_pool
    att._candidate_pool = _no_scan
    try:
        result = write_node_thinking(node_dir)
    finally:
        att._candidate_pool = real_pool

    assert result.discovery == "session_chain[2]"
    assert result.turns_total == 6
    index = json.loads(
        (node_dir / "thinking" / "index.json").read_text(encoding="utf-8")
    )
    assert index["turns"][0]["payload_key"] == "tac_1."
    assert index["turns"][3]["payload_key"] == "tac_4."
    assert index["turns"][3]["turn"] == 4


def test_codex_registry_never_falls_back_to_claude_transcript_scan(
    tmp_path: Path, monkeypatch
) -> None:
    import workflow.validation.agent_thinking_trace as att

    node_dir = tmp_path / "node_memory" / "Tree_0_0"
    _write_jsonl(node_dir / "timeline.jsonl", [
        {
            "kind": "manager_turn",
            "node": "Tree-0.0",
            "turn": turn,
            "time": f"2026-06-10T10:0{turn}:00Z",
            "intent": {"intent": intent, "payload": payload},
            "ok": True,
        }
        for turn, (intent, payload) in enumerate([
            ("commit_tactic", {"tactic": "trivial."}),
            ("commit_tactic", {"tactic": "qed."}),
            ("finish", {}),
        ], start=1)
    ])
    _write_jsonl(node_dir / "agent_sessions.jsonl", [{
        "kind": "agent_session",
        "session_id": "codex-thread",
        "agent_backend": "codex",
    }])
    codex_events = (
        tmp_path / "runtime_private" / "Tree_0_0" / "codex_events.jsonl"
    )
    _write_jsonl(codex_events, [
        {"type": "thread.started", "thread_id": "codex-thread"},
        {"type": "turn.started"},
        {
            "type": "item.completed",
            "item": {"id": "reason_1", "type": "reasoning", "text": "first"},
        },
        {
            "type": "item.started",
            "item": {
                "id": "item_1",
                "type": "mcp_tool_call",
                "tool": "submit_proof_intent",
                "arguments": {
                    "intent": "commit_tactic",
                    "payload": {"tactic": "trivial."},
                },
            },
        },
        # The completed event repeats the same call and must be deduplicated.
        {
            "type": "item.completed",
            "item": {
                "id": "item_1",
                "type": "mcp_tool_call",
                "tool": "submit_proof_intent",
                "arguments": {
                    "intent": "commit_tactic",
                    "payload": {"tactic": "trivial."},
                },
            },
        },
        {
            "type": "item.completed",
            "item": {
                "id": "item_2",
                "type": "mcp_tool_call",
                "tool": "submit_proof_intent",
                "arguments": {
                    "intent": "commit_tactic",
                    "payload": {"tactic": "qed."},
                },
            },
        },
        {
            "type": "turn.completed",
            "usage": {
                "input_tokens": 100,
                "cached_input_tokens": 60,
                "output_tokens": 5,
                "reasoning_output_tokens": 3,
            },
        },
        {"type": "turn.started"},
        # Item ids restart on a resumed CLI turn; this is a distinct call.
        {
            "type": "item.completed",
            "item": {
                "id": "item_1",
                "type": "mcp_tool_call",
                "tool": "submit_proof_intent",
                "arguments": {"intent": "finish", "payload": {}},
            },
        },
        {
            "type": "turn.completed",
            "usage": {
                "input_tokens": 200,
                "cached_input_tokens": 150,
                "output_tokens": 7,
                "reasoning_output_tokens": 4,
            },
        },
    ])

    def _no_claude_root() -> Path:
        raise AssertionError("Codex nodes must not scan ~/.claude")

    monkeypatch.setattr(att, "_claude_projects_root", _no_claude_root)
    result = write_node_thinking(node_dir)

    assert result.discovery == "recorded_session_id"
    assert result.transcripts == [codex_events]
    assert result.turns_total == 3
    index = json.loads(
        (node_dir / "thinking" / "index.json").read_text(encoding="utf-8")
    )
    turns = index["turns"]
    assert [turn["intent"] for turn in turns] == [
        "commit_tactic", "commit_tactic", "finish",
    ]
    # Codex exposes one usage aggregate per CLI turn, not per manager call.
    assert turns[0]["tokens"] == {}
    assert turns[1]["tokens"]["input_tokens"] == 40
    assert turns[1]["tokens"]["cache_read_input_tokens"] == 60
    assert turns[1]["token_usage_scope"] == "codex_cli_turn_aggregate"
    assert turns[2]["tokens"]["input_tokens"] == 50
    assert turns[2]["tokens"]["cache_read_input_tokens"] == 150
    assert turns[2]["token_usage_scope"] == "codex_cli_turn_aggregate"
    report = build_report([RunSpec(label="codex", path=tmp_path)])
    finish_row = report["runs"][0]["rows"][2]
    assert finish_row["usage"]["input_tokens"] == 50
    assert finish_row["usage_scope"] == "codex_cli_turn_aggregate"


def test_session_chain_skips_respawn_boundary_resubmit(tmp_path: Path) -> None:
    """A watermark respawn can kill a generation with a submit in flight; the
    continuation re-submits it, so its transcript STARTS with a duplicate of
    the previous link's last intent that has no timeline row of its own. Chain
    assembly must skip that leading resubmit instead of stalling (the CBC_upto
    L1 failure: 'recorded_session_id (partial 30/48)')."""
    import workflow.validation.agent_thinking_trace as att

    node_dir = tmp_path / "node_memory" / "Tree_0_0"
    tactics = [f"tac_{i}." for i in range(1, 9)]
    _write_jsonl(node_dir / "timeline.jsonl", [
        {"kind": "manager_turn", "node": "Tree-0.0", "turn": i,
         "time": f"2026-06-10T10:0{i}:00Z",
         "intent": {"intent": "commit_tactic", "payload": {"tactic": tac}},
         "ok": True}
        for i, tac in enumerate(tactics, start=1)
    ])
    # Session 1: timeline turns 1-4 PLUS the dangling in-flight submit of
    # turn 5's tactic (killed before the manager handled it).
    sess1 = tmp_path / "sess1.jsonl"
    _write_jsonl(sess1, [
        _assistant(f"2026-06-10T10:0{i}:00Z",
                   _thinking(f"think {i}"),
                   _submit("commit_tactic", tactic=tac))
        for i, tac in enumerate(tactics[:5], start=1)
    ])
    # Session 2 (continuation): re-submits turn 5's tactic, then turns 6-8.
    sess2 = tmp_path / "sess2.jsonl"
    _write_jsonl(sess2, [
        _assistant(f"2026-06-10T10:0{i}:00Z",
                   _thinking(f"retry think {i}"),
                   _submit("commit_tactic", tactic=tac))
        for i, tac in enumerate(tactics[4:], start=5)
    ])
    _write_jsonl(node_dir / "agent_sessions.jsonl", [
        {"kind": "agent_session", "session_id": "sess1",
         "transcript_path": str(sess1)},
        {"kind": "agent_session", "session_id": "sess2",
         "transcript_path": str(sess2)},
    ])

    def _no_scan(*a, **k):
        raise AssertionError("registry chain must resolve without the scan")

    real_pool = att._candidate_pool
    att._candidate_pool = _no_scan
    try:
        result = write_node_thinking(node_dir)
    finally:
        att._candidate_pool = real_pool

    assert result.discovery == "session_chain[2]"
    assert result.turns_total == 8
    index = json.loads(
        (node_dir / "thinking" / "index.json").read_text(encoding="utf-8")
    )
    # Session 1's greedy match consumes turns 1-5 (its dangling submit matches
    # the timeline row the continuation actually drove); the continuation's
    # duplicate leading resubmit is skipped and it covers turns 6-8.
    assert [t["payload_key"] for t in index["turns"]] == [f"tac_{i}." for i in range(1, 9)]


def test_session_chain_assembly_recovers_unregistered_swap(tmp_path: Path) -> None:
    """A context swap mid-run starts a new Claude session; historically only the
    final link was registered in agent_sessions.jsonl. Chain assembly must sweep
    the time window, stitch the unregistered prefix session back in, and number
    turns globally so they align with the timeline rows."""
    import os
    import workflow.validation.agent_thinking_trace as att

    node_dir = tmp_path / "node_memory" / "Tree_0_0"
    tactics = [f"tac_{i}." for i in range(1, 7)]
    _write_jsonl(node_dir / "timeline.jsonl", [
        {"kind": "manager_turn", "node": "Tree-0.0", "turn": i,
         "time": f"2026-06-10T10:0{i}:00Z",
         "intent": {"intent": "commit_tactic", "payload": {"tactic": tac}},
         "ok": True}
        for i, tac in enumerate(tactics, start=1)
    ])

    # Session 1 (turns 1-3): NOT registered — must be found by the window sweep.
    fake_projects = tmp_path / "projects" / "-fake-slug"
    sess1 = fake_projects / "sess1.jsonl"
    _write_jsonl(sess1, [
        _assistant(f"2026-06-10T10:0{i}:00Z",
                   _thinking(f"think {i}"),
                   _submit("commit_tactic", tactic=tac))
        for i, tac in enumerate(tactics[:3], start=1)
    ])
    # Put its mtime inside the node's timeline window.
    t = 1781431380.0  # ~2026-06-10T10:03Z; only relative window matters
    os.utime(sess1, (t, t))

    # Session 2 (turns 4-6): registered.
    sess2 = tmp_path / "sess2.jsonl"
    _write_jsonl(sess2, [
        _assistant(f"2026-06-10T10:0{i}:00Z",
                   _thinking(f"think {i}"),
                   _submit("commit_tactic", tactic=tac))
        for i, tac in enumerate(tactics[3:], start=4)
    ])
    _write_jsonl(node_dir / "agent_sessions.jsonl", [
        {"kind": "agent_session", "session_id": "sess2",
         "transcript_path": str(sess2)},
    ])

    real_root = att._claude_projects_root
    att._claude_projects_root = lambda: tmp_path / "projects"
    # The mtime window is computed from timeline times; make the sweep window
    # cover the synthetic mtime regardless of the host clock.
    real_pool = att._candidate_pool

    def pool(node_d, *, window_pad_s=1800.0):
        return real_pool(node_d, window_pad_s=1e12)

    att._candidate_pool = pool
    try:
        result = write_node_thinking(node_dir)
    finally:
        att._claude_projects_root = real_root
        att._candidate_pool = real_pool

    assert result.discovery == "session_chain[2]"
    assert result.turns_total == 6
    index = json.loads((node_dir / "thinking" / "index.json").read_text(encoding="utf-8"))
    # Global numbering: turn 4 is session 2's FIRST submit.
    assert index["turns"][3]["turn"] == 4
    assert index["turns"][3]["payload_key"] == "tac_4."
    assert index["turns"][0]["payload_key"] == "tac_1."
    body = (node_dir / "thinking" / "turn_004.md").read_text(encoding="utf-8")
    assert "think 4" in body
