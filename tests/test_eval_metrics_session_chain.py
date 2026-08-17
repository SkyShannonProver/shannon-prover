"""Regression tests: eval_suite.metrics consumes the canonical
``agent_session_ids.json`` manifest — every listed session's trace is summed
exactly once, and nothing outside the manifest is guessed at.
"""
from __future__ import annotations

import json
from pathlib import Path

import _pathsetup  # noqa: F401  (repo root on sys.path)

import eval_suite.metrics as metrics
from workflow.schemas.prover_result import (
    PROVER_RUN_INCOMPLETE,
    PROVER_RUN_VERIFIED,
    ProverResult,
)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


def _usage_event(request_id: str, message_id: str, **usage) -> dict:
    return {
        "type": "assistant",
        "timestamp": "2026-07-23T20:10:00Z",
        "requestId": request_id,
        "message": {"id": message_id, "usage": usage, "content": []},
    }


def _manifest(
    iteration_dir: Path,
    session_ids: list[str],
    *,
    agent_backend: str = "claude",
) -> None:
    iteration_dir.mkdir(parents=True, exist_ok=True)
    (iteration_dir / "agent_session_ids.json").write_text(
        json.dumps({
            "schema_version": 1,
            "kind": "agent_session_ids",
            "sessions": [
                {
                    "node": "Tree-0.0",
                    "session_id": sid,
                    "session_index": index,
                    "continuation": index > 0,
                    "winner": True,
                    "agent_backend": agent_backend,
                }
                for index, sid in enumerate(session_ids)
            ],
        }),
        encoding="utf-8",
    )


def _write_terminal_result(
    run: Path,
    *,
    verified: bool = False,
    final_regression_ok: bool = True,
    target: dict | None = None,
) -> ProverResult:
    result = ProverResult(
        status=PROVER_RUN_VERIFIED if verified else PROVER_RUN_INCOMPLETE,
        verification=(
            {"status": "pass", "method": "test_fixture"} if verified else {}
        ),
    )
    result.save(run / "iteration_1" / "prover_run_result.json")
    summary = {
        "final_proved": result.is_verified,
        "final_regression_ok": final_regression_ok,
        "final_prover_result_id": result.result_id,
        "final_prover_result_status": result.status,
    }
    if target is not None:
        summary["target"] = target
    (run / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    return result


def test_metrics_sums_both_session_traces_exactly(monkeypatch, tmp_path):
    projects = tmp_path / "projects" / "-proj-slug"
    # Initial session: two distinct requests plus a streamed duplicate chunk of
    # the second request (same requestId:message id) that must NOT double-count.
    _write_jsonl(projects / "sess-initial.jsonl", [
        _usage_event(
            "req1", "msg1",
            input_tokens=100, output_tokens=10,
            cache_creation_input_tokens=1000, cache_read_input_tokens=5000,
        ),
        _usage_event(
            "req2", "msg2",
            input_tokens=200, output_tokens=20,
            cache_creation_input_tokens=2000, cache_read_input_tokens=6000,
        ),
        _usage_event(
            "req2", "msg2",
            input_tokens=200, output_tokens=20,
            cache_creation_input_tokens=2000, cache_read_input_tokens=6000,
        ),
    ])
    # Continuation session.
    _write_jsonl(projects / "sess-continuation.jsonl", [
        _usage_event(
            "req3", "msg3",
            input_tokens=40, output_tokens=4,
            cache_creation_input_tokens=400, cache_read_input_tokens=900,
        ),
    ])
    monkeypatch.setattr(
        metrics, "CLAUDE_PROJECTS_DIR", tmp_path / "projects",
    )

    iteration = tmp_path / "run" / "iteration_1"
    _manifest(iteration, ["sess-initial", "sess-continuation"])

    totals = metrics._collect_agent_trace_metrics([iteration])
    assert totals["session_count"] == 2
    assert totals["trace_count"] == 2
    assert totals["missing_trace_count"] == 0
    assert totals["input_tokens"] == 100 + 200 + 40
    assert totals["output_tokens"] == 10 + 20 + 4
    assert totals["cache_creation_input_tokens"] == 1000 + 2000 + 400
    assert totals["cache_read_input_tokens"] == 5000 + 6000 + 900
    assert totals["effective_input_tokens"] == 340 + 3400 + 11900
    assert totals["total_tokens"] == 340 + 3400 + 11900 + 34


def test_metrics_does_not_double_count_duplicate_manifest_rows(
    monkeypatch, tmp_path,
):
    projects = tmp_path / "projects" / "-proj-slug"
    _write_jsonl(projects / "sess-a.jsonl", [
        _usage_event(
            "req1", "msg1",
            input_tokens=7, output_tokens=3,
            cache_creation_input_tokens=11, cache_read_input_tokens=13,
        ),
    ])
    monkeypatch.setattr(metrics, "CLAUDE_PROJECTS_DIR", tmp_path / "projects")

    iteration = tmp_path / "run" / "iteration_1"
    # The same session listed twice (e.g. manifest + session_id.txt) counts once.
    _manifest(iteration, ["sess-a", "sess-a"])
    (iteration / "session_id.txt").write_text("sess-a", encoding="utf-8")

    totals = metrics._collect_agent_trace_metrics([iteration])
    assert totals["session_count"] == 1
    assert totals["trace_count"] == 1
    assert totals["input_tokens"] == 7
    assert totals["output_tokens"] == 3
    assert totals["cache_creation_input_tokens"] == 11
    assert totals["cache_read_input_tokens"] == 13


def test_metrics_single_session_unchanged(monkeypatch, tmp_path):
    projects = tmp_path / "projects" / "-proj-slug"
    _write_jsonl(projects / "sess-only.jsonl", [
        _usage_event(
            "req1", "msg1",
            input_tokens=1, output_tokens=2,
            cache_creation_input_tokens=3, cache_read_input_tokens=4,
        ),
    ])
    monkeypatch.setattr(metrics, "CLAUDE_PROJECTS_DIR", tmp_path / "projects")

    iteration = tmp_path / "run" / "iteration_1"
    _manifest(iteration, ["sess-only"])

    totals = metrics._collect_agent_trace_metrics([iteration])
    assert totals["session_count"] == 1
    assert totals["effective_input_tokens"] == 1 + 3 + 4
    assert totals["total_tokens"] == 1 + 3 + 4 + 2


def test_metrics_prefers_run_confined_claude_transcript_registry(
    monkeypatch, tmp_path,
):
    iteration = tmp_path / "run" / "iteration_1"
    _manifest(iteration, ["sess-private"])
    transcript = (
        iteration
        / "runtime_private"
        / "Tree_0_0"
        / "agent_state"
        / "claude_home"
        / "projects"
        / "-private-project"
        / "sess-private.jsonl"
    )
    _write_jsonl(transcript, [
        _usage_event(
            "req-private", "msg-private",
            input_tokens=9, output_tokens=4,
            cache_creation_input_tokens=3, cache_read_input_tokens=7,
        ),
    ])
    _write_jsonl(
        iteration / "node_memory" / "Tree_0_0" / "agent_sessions.jsonl",
        [{
            "kind": "agent_session",
            "node": "Tree-0.0",
            "session_id": "sess-private",
            "agent_backend": "claude",
            "transcript_path": str(transcript),
        }],
    )
    monkeypatch.setattr(metrics, "CLAUDE_PROJECTS_DIR", tmp_path / "absent")

    totals = metrics._collect_agent_trace_metrics([iteration])

    assert totals["trace_count"] == 1
    assert totals["missing_trace_count"] == 0
    assert totals["input_tokens"] == 9
    assert totals["cache_creation_input_tokens"] == 3
    assert totals["cache_read_input_tokens"] == 7
    assert totals["output_tokens"] == 4


def test_metrics_missing_trace_is_reported_not_guessed(monkeypatch, tmp_path):
    monkeypatch.setattr(metrics, "CLAUDE_PROJECTS_DIR", tmp_path / "projects")
    iteration = tmp_path / "run" / "iteration_1"
    _manifest(iteration, ["sess-vanished"])
    totals = metrics._collect_agent_trace_metrics([iteration])
    assert totals["available"] is False
    assert totals["missing_trace_count"] == 1
    assert totals["total_tokens"] == 0


def test_codex_metrics_sum_cli_turn_usage_and_dedupe_shared_event_stream(
    tmp_path: Path,
) -> None:
    iteration = tmp_path / "run" / "iteration_1"
    # A resumed Codex thread can create multiple registry rows for one node,
    # while all of its CLI turns remain in the same canonical event stream.
    _manifest(
        iteration,
        ["codex-thread-initial", "codex-thread-resumed"],
        agent_backend="codex",
    )
    _write_jsonl(
        iteration / "runtime_private" / "Tree_0_0" / "codex_events.jsonl",
        [
            {
                "type": "turn.completed",
                "usage": {
                    "input_tokens": 100,
                    "cached_input_tokens": 60,
                    "cache_write_input_tokens": 10,
                    "output_tokens": 5,
                    "reasoning_output_tokens": 3,
                },
            },
            {
                "type": "turn.completed",
                "usage": {
                    "input_tokens": 200,
                    "cached_input_tokens": 150,
                    "cache_write_input_tokens": 20,
                    "output_tokens": 7,
                    "reasoning_output_tokens": 4,
                },
            },
        ],
    )

    totals = metrics._collect_agent_trace_metrics([iteration])

    assert totals["available"] is True
    assert totals["session_count"] == 2
    assert totals["trace_count"] == 1
    assert totals["missing_trace_count"] == 0
    assert totals["input_tokens"] == 60
    assert totals["cache_creation_input_tokens"] == 30
    assert totals["cache_read_input_tokens"] == 210
    assert totals["effective_input_tokens"] == 300
    assert totals["output_tokens"] == 12
    assert totals["thinking_tokens_exact"] == 7
    assert totals["total_tokens"] == 312
    assert sum(
        int(session.get("usage_event_count") or 0)
        for session in totals["sessions"]
    ) == 2
    assert totals["token_accounting_complete"] is True


def test_codex_metrics_recover_killed_turn_from_run_confined_session_ledger(
    tmp_path: Path,
) -> None:
    iteration = tmp_path / "run" / "iteration_1"
    session_id = "019fc581-24f4-79d1-bccf-5ceb493e4356"
    _manifest(iteration, [session_id], agent_backend="codex")
    private = iteration / "runtime_private" / "Tree_0_0"
    _write_jsonl(
        private / "codex_events.jsonl",
        [
            {"type": "thread.started", "thread_id": session_id},
            {"type": "turn.started"},
            {
                "type": "turn.completed",
                "usage": {
                    "input_tokens": 100,
                    "cached_input_tokens": 60,
                    "cache_write_input_tokens": 10,
                    "output_tokens": 5,
                    "reasoning_output_tokens": 3,
                },
            },
            {"type": "thread.started", "thread_id": session_id},
            {"type": "turn.started"},
            {"type": "item.completed", "item": {"type": "agent_message"}},
        ],
    )
    rollout = (
        private
        / "agent_state"
        / "codex_home"
        / "sessions"
        / "2026"
        / "08"
        / "03"
        / f"rollout-2026-08-03T02-43-22-{session_id}.jsonl"
    )
    _write_jsonl(
        rollout,
        [
            {
                "type": "event_msg",
                "payload": {
                    "type": "token_count",
                    "info": {
                        "total_token_usage": {
                            "input_tokens": 1000,
                            "cached_input_tokens": 700,
                            "cache_write_input_tokens": 0,
                            "output_tokens": 50,
                            "reasoning_output_tokens": 20,
                        }
                    },
                },
            }
        ],
    )

    totals = metrics._collect_agent_trace_metrics([iteration])

    assert totals["input_tokens"] == 300
    assert totals["cache_creation_input_tokens"] == 0
    assert totals["cache_read_input_tokens"] == 700
    assert totals["output_tokens"] == 50
    assert totals["thinking_tokens_exact"] == 20
    assert totals["total_tokens"] == 1050
    assert totals["token_accounting_complete"] is True
    assert totals["partial_turn_recovered_count"] == 1
    assert totals["usage_sources"] == {
        "run_confined_codex_session_ledger": 1,
    }
    assert totals["sessions"][0]["partial_turn_recovered"] is True


def test_codex_metrics_mark_open_turn_without_session_ledger_incomplete(
    tmp_path: Path,
) -> None:
    iteration = tmp_path / "run" / "iteration_1"
    _manifest(iteration, ["codex-open"], agent_backend="codex")
    _write_jsonl(
        iteration / "runtime_private" / "Tree_0_0" / "codex_events.jsonl",
        [
            {"type": "thread.started", "thread_id": "codex-open"},
            {"type": "turn.started"},
            {"type": "item.completed", "item": {"type": "agent_message"}},
        ],
    )

    totals = metrics._collect_agent_trace_metrics([iteration])

    assert totals["token_accounting_complete"] is False
    assert totals["incomplete_token_session_count"] == 1
    assert totals["sessions"][0]["token_accounting_complete"] is False


def test_codex_metrics_mark_terminal_turn_without_usage_incomplete(
    tmp_path: Path,
) -> None:
    iteration = tmp_path / "run" / "iteration_1"
    _manifest(iteration, ["codex-failed"], agent_backend="codex")
    _write_jsonl(
        iteration / "runtime_private" / "Tree_0_0" / "codex_events.jsonl",
        [
            {"type": "thread.started", "thread_id": "codex-failed"},
            {"type": "turn.started"},
            {"type": "turn.failed", "error": {"message": "disconnected"}},
        ],
    )

    totals = metrics._collect_agent_trace_metrics([iteration])

    assert totals["token_accounting_complete"] is False
    assert totals["incomplete_token_session_count"] == 1


def test_codex_metrics_sum_distinct_ledgers_for_sessions_sharing_cli_stream(
    tmp_path: Path,
) -> None:
    iteration = tmp_path / "run" / "iteration_1"
    session_ids = ["codex-initial", "codex-continuation"]
    _manifest(iteration, session_ids, agent_backend="codex")
    private = iteration / "runtime_private" / "Tree_0_0"
    _write_jsonl(
        private / "codex_events.jsonl",
        [{"type": "thread.started", "thread_id": session_ids[-1]}],
    )
    for index, session_id in enumerate(session_ids, start=1):
        _write_jsonl(
            private
            / "agent_state"
            / "codex_home"
            / "sessions"
            / "2026"
            / "08"
            / "03"
            / f"rollout-{index}-{session_id}.jsonl",
            [
                {
                    "type": "event_msg",
                    "payload": {
                        "type": "token_count",
                        "info": {
                            "total_token_usage": {
                                "input_tokens": 100 * index,
                                "cached_input_tokens": 10 * index,
                                "output_tokens": 5 * index,
                                "reasoning_output_tokens": 2 * index,
                            }
                        },
                    },
                }
            ],
        )

    totals = metrics._collect_agent_trace_metrics([iteration])

    assert totals["trace_count"] == 2
    assert totals["input_tokens"] == 270
    assert totals["cache_read_input_tokens"] == 30
    assert totals["output_tokens"] == 15
    assert totals["thinking_tokens_exact"] == 6
    assert totals["total_tokens"] == 315
    assert totals["token_accounting_complete"] is True


def test_eval_metrics_fail_countability_when_provider_usage_is_incomplete(
    tmp_path: Path,
) -> None:
    run = tmp_path / "run"
    iteration = run / "iteration_1"
    _manifest(iteration, ["codex-open"], agent_backend="codex")
    _write_jsonl(
        iteration / "runtime_private" / "Tree_0_0" / "codex_events.jsonl",
        [
            {"type": "thread.started", "thread_id": "codex-open"},
            {"type": "turn.started"},
        ],
    )
    _write_terminal_result(run)
    (run / "config.json").write_text(
        json.dumps({"surface_profile": "l1_goal_projection"}),
        encoding="utf-8",
    )

    row = metrics.collect_run_metrics(run)

    assert row["status"] == "invalid"
    assert row["outcome"]["countable"] is False
    assert row["agent_trace"]["token_accounting_complete"] is False
    assert row["validity"]["reasons"] == [
        "provider token accounting is incomplete for at least one agent session"
    ]


def test_eval_metrics_fail_countability_on_manager_bridge_exception(
    tmp_path: Path,
) -> None:
    run = tmp_path / "run"
    iteration = run / "iteration_1"
    iteration.mkdir(parents=True)
    _write_terminal_result(run)
    (run / "config.json").write_text(
        json.dumps({"surface_profile": "l4_proof_state_compiler_v2_operation_binding_repair"}),
        encoding="utf-8",
    )
    _write_jsonl(iteration / "proof_node_manager_audit.jsonl", [{
        "kind": "manager_bridge.exception",
        "node": "Tree-0.0",
        "error_type": "ValueError",
        "health": {"status": "manager_bridge_exception"},
    }])

    row = metrics.collect_run_metrics(run)

    assert row["status"] == "invalid"
    assert row["outcome"]["countable"] is False
    assert row["diagnostics"]["manager_bridge_exception_count"] == 1
    assert row["validity"]["reasons"] == [
        "manager bridge raised an internal exception during the agent run"
    ]


def test_metrics_fail_countability_on_recorded_target_proof_output(tmp_path):
    run = tmp_path / "run"
    iteration = run / "iteration_1"
    iteration.mkdir(parents=True)
    _write_terminal_result(
        run,
        verified=True,
        target={"lemma": "target", "file": "target.ec"},
    )
    (run / "config.json").write_text(
        json.dumps({"surface_profile": "l4_proof_state_compiler_v2_operation_binding_repair"}),
        encoding="utf-8",
    )
    _write_jsonl(iteration / "payload_audit.jsonl", [{
        "event": "tool_result",
        "target_proof_exposure": {
            "detected": True,
            "audit_code": "eval.target_proof_output_exposure",
            "path": "/repo/eval/target.ec",
            "line": 42,
        },
    }])

    row = metrics.collect_run_metrics(run)

    assert row["status"] == "invalid"
    assert row["validity"]["valid"] is False
    assert row["outcome"]["countable"] is False
    assert row["integrity"]["target_proof_output_exposure_count"] == 1


def test_eval_metrics_require_confinement_for_every_launched_node(tmp_path):
    run = tmp_path / "run"
    iteration = run / "iteration_1"
    private = iteration / "runtime_private" / "Tree_0_0"
    private.mkdir(parents=True)
    (private / "proof_node_mcp_config.json").write_text("{}", encoding="utf-8")
    _write_terminal_result(run)
    (run / "config.json").write_text(
        json.dumps({"eval_mode": True}), encoding="utf-8"
    )

    missing = metrics.collect_run_metrics(run)
    assert missing["status"] == "invalid"
    assert missing["outcome"]["countable"] is False
    assert missing["integrity"]["expected_confined_node_count"] == 1
    assert missing["integrity"]["confined_node_count"] == 0

    (private / "eval_agent_confinement.json").write_text(
        json.dumps({
            "schema_version": 2,
            "kind": "eval_agent_filesystem_confinement",
            "probe_status": "passed",
            "original_repository_visible": False,
            "sibling_worktrees_visible": False,
            "prior_agent_transcripts_visible": False,
            "host_tmp_visible": False,
        }),
        encoding="utf-8",
    )
    _manifest(iteration, ["codex-confined"], agent_backend="codex")
    _write_jsonl(private / "codex_events.jsonl", [
        {"type": "thread.started", "thread_id": "codex-confined"},
        {"type": "turn.started"},
        {
            "type": "turn.completed",
            "usage": {
                "input_tokens": 10,
                "cached_input_tokens": 0,
                "output_tokens": 2,
                "reasoning_output_tokens": 1,
            },
        },
    ])
    _write_jsonl(iteration / "proof_node_manager_audit.jsonl", [{
        "kind": "agent_intent.handled",
        "node": "Tree-0.0",
        "intent": {"intent": "finish", "payload": {}},
        "manager_actions": [],
    }])
    confined = metrics.collect_run_metrics(run)
    assert confined["status"] == "valid"
    assert confined["outcome"]["countable"] is True
    assert confined["integrity"]["filesystem_confinement_complete"] is True

    # Schema 1 asserted isolation without a negative namespace probe.  It must
    # not become countable merely because its booleans claimed success.
    stale = json.loads(
        (private / "eval_agent_confinement.json").read_text(encoding="utf-8")
    )
    stale["schema_version"] = 1
    stale.pop("probe_status")
    (private / "eval_agent_confinement.json").write_text(
        json.dumps(stale), encoding="utf-8"
    )
    unprobed = metrics.collect_run_metrics(run)
    assert unprobed["status"] == "invalid"
    assert unprobed["integrity"]["confined_node_count"] == 0


def test_eval_metrics_marks_missing_node_timeline_invalid(tmp_path):
    run = tmp_path / "run"
    iteration = run / "iteration_1"
    (iteration / "node_memory" / "Tree_0_0").mkdir(parents=True)
    _write_jsonl(iteration / "payload_audit.jsonl", [{
        "event": "run_end",
        "returncode": 1,
        "proved": False,
    }])
    _write_terminal_result(run, final_regression_ok=False)
    (run / "config.json").write_text("{}", encoding="utf-8")

    row = metrics.collect_run_metrics(run)

    assert row["status"] == "invalid"
    assert row["outcome"]["countable"] is False
    assert any(
        "no proof-node timeline" in reason
        for reason in row["validity"]["reasons"]
    )


def test_eval_metrics_rejects_launched_zero_session_zero_turn_run(tmp_path):
    run = tmp_path / "run"
    iteration = run / "iteration_1"
    private = iteration / "runtime_private" / "Tree_0_0"
    private.mkdir(parents=True)
    (private / "proof_node_mcp_config.json").write_text(
        "{}", encoding="utf-8"
    )
    (private / "eval_agent_confinement.json").write_text(
        json.dumps({
            "schema_version": 2,
            "kind": "eval_agent_filesystem_confinement",
            "probe_status": "passed",
            "original_repository_visible": False,
            "sibling_worktrees_visible": False,
            "prior_agent_transcripts_visible": False,
            "host_tmp_visible": False,
        }),
        encoding="utf-8",
    )
    node = iteration / "node_memory" / "Tree_0_0"
    node.mkdir(parents=True)
    _write_jsonl(node / "timeline.jsonl", [{"kind": "bootstrap"}])
    _write_terminal_result(run)
    (run / "config.json").write_text(
        json.dumps({
            "eval_mode": True,
            "surface_profile": "l4_proof_state_compiler_v2_m07",
            "prover": {
                "agent_backend": "codex",
                "model": "gpt-5.6-sol",
            },
        }),
        encoding="utf-8",
    )

    row = metrics.collect_run_metrics(run)

    assert row["status"] == "invalid"
    assert row["outcome"]["countable"] is False
    assert row["agent_trace"]["session_count"] == 0
    assert row["main"]["manager_turns"] == 0
    assert row["validity"]["reasons"] == [
        "no provider session was captured for any launched proof node",
        "no managed agent turn completed for any launched proof node",
    ]


def test_eval_metrics_decompose_compiler_cost_exposure_and_consumption() -> None:
    tactic = "call (Alossless_F (<: D1(O).O) _)."
    records = [
        {
            "kind": "proof_state_compiler.completed",
            "node": "Tree-0.0",
            "manifest_id": "l1-plus-m05-treatment",
            "resource_loading": {
                "planned_request_count": 1,
                "request_count": 1,
                "loaded_declaration_count": 1,
                "elapsed_ms": 2400,
            },
            "timings_ms": {
                "resource_loading": 2500,
                "compile_p1_p4": 4,
                "certification": 12,
                "total": 2520,
            },
            "candidate_counts": {"actions": 1},
            "certifications": {"total": 1, "accepted": 1},
            "admission": {
                "compiler_markdown_bytes": 310,
                "agent_surface": {
                    "resources": [],
                    "bindings": [],
                    "actions": [{
                        "feature_id": "losslessness_certificate_application",
                        "intent": "commit_tactic",
                        "payload": {"tactic": tactic},
                    }],
                    "diagnostics": [],
                },
                "presented_actions": [{
                    "feature_id": "losslessness_certificate_application",
                    "intent": "commit_tactic",
                    "payload": {"tactic": tactic},
                }],
            },
        },
        {
            "kind": "agent_intent.handled",
            "node": "Tree-0.0",
            "intent": {
                "intent": "commit_tactic",
                "payload": {"tactic": tactic},
            },
            "manager_actions": [{
                "label": "commit_tactic",
                "exit_code": 0,
            }],
        },
    ]

    result = metrics._collect_proof_state_compiler_economics(records)

    assert result["service_call_count"] == 1
    assert result["executed_call_count"] == 1
    assert result["skipped_call_count"] == 0
    assert result["planned_request_count"] == 1
    assert result["resource_load_round_count"] == 1
    assert result["completed_request_count"] == 1
    assert result["loader_internal_ms"] == 2400
    assert result["resource_loading_wall_ms"] == 2500
    assert result["service_total_ms"] == 2520
    assert result["certification_accepted_count"] == 1
    assert result["presented_item_count"] == 1
    assert result["presented_action_count"] == 1
    assert result["consumed_action_count"] == 1
    assert result["consumed_action_accepted_count"] == 1
    assert result["consumed_action_rejected_count"] == 0
    assert result["consumed_by_feature"] == {
        "losslessness_certificate_application": 1,
    }


def test_eval_metrics_retains_trigger_first_and_native_batch_economics() -> None:
    records = [
        {
            "kind": "proof_state_compiler.completed",
            "node": "Tree-0.0",
            "execution": {
                "status": "skipped",
                "eligible_feature_ids": [],
                "decisions": [{
                    "feature_id": "operation_binding_repair",
                    "eligible": False,
                    "reason": "no_completed_turn",
                }],
            },
            "timings_ms": {"total": 0},
        },
        {
            "kind": "proof_state_compiler.completed",
            "node": "Tree-0.0",
            "execution": {
                "status": "executed",
                "eligible_feature_ids": ["operation_binding_repair"],
                "decisions": [{
                    "feature_id": "operation_binding_repair",
                    "eligible": True,
                    "reason": "owned_failure_shape",
                }],
            },
            "native_state": {"present": True, "elapsed_ms": 1200},
            "native_semantics": {
                "planned_request_count": 4,
                "observation_count": 4,
                "batch_count": 1,
                "elapsed_ms": 991,
            },
            "timings_ms": {
                "input_initial": 2000,
                "manager_state_snapshot": 10,
                "compiler_input_transport": 600,
                "native_state_projection": 1300,
                "native_state_lowering": 20,
                "native_semantic_execution": 1000,
                "total": 6000,
            },
            "admission": {"compiler_markdown_bytes": 0, "presented_actions": []},
        },
    ]

    result = metrics._collect_proof_state_compiler_economics(records)

    assert result["service_call_count"] == 2
    assert result["executed_call_count"] == 1
    assert result["skipped_call_count"] == 1
    assert result["eligible_feature_occurrence_count"] == 1
    assert result["execution_skip_reasons"] == {"no_completed_turn": 1}
    assert result["input_initial_ms"] == 2000
    assert result["manager_state_snapshot_ms"] == 10
    assert result["compiler_input_transport_ms"] == 600
    assert result["native_state_projection_wall_ms"] == 1300
    assert result["native_state_lowering_ms"] == 20
    assert result["native_state_elapsed_ms"] == 1200
    assert result["native_semantic_execution_ms"] == 1000
    assert result["native_planned_request_count"] == 4
    assert result["native_observation_count"] == 4
    assert result["native_batch_count"] == 1
    assert result["native_batch_elapsed_ms"] == 991


def test_eval_metrics_counts_non_action_compiler_presentation() -> None:
    records = [{
        "kind": "proof_state_compiler.completed",
        "node": "Tree-0.0",
        "manifest_id": "operation-readiness-treatment",
        "resource_loading": {},
        "timings_ms": {"total": 2},
        "candidate_counts": {"diagnostics": 1},
        "certifications": {},
        "admission": {
            "admitted": 1,
            "compiler_markdown_bytes": 299,
            "agent_surface": {
                "resources": [],
                "bindings": [],
                "actions": [],
                "diagnostics": [{
                    "code": "program_operation_readiness",
                    "message": "call is structurally blocked",
                }],
            },
            "presented_actions": [],
            "decisions": [{
                "feature_id": "program_operation_readiness",
                "admitted": True,
            }],
        },
    }]

    result = metrics._collect_proof_state_compiler_economics(records)

    assert result["presentation_event_count"] == 1
    assert result["presented_item_count"] == 1
    assert result["presented_action_count"] == 0
    assert result["consumed_action_count"] == 0
    assert result["compiler_markdown_bytes"] == 299
    assert result["presented_by_feature"] == {
        "program_operation_readiness": 1,
    }


def test_eval_metrics_separates_compiler_cache_reuse_from_work() -> None:
    records = [
        {
            "kind": "proof_state_compiler.completed",
            "node": "Tree-0.0",
            "exact_observation_cache": {"hit": False},
            "certification_cache": {"hit": False},
            "resource_cache": {
                "hit": False,
                "reused_declaration_count": 0,
            },
            "timings_ms": {"total": 20, "certification": 12},
            "candidate_counts": {"actions": 1},
            "certifications": {
                "total": 1,
                "accepted": 1,
                "performed": 1,
                "performed_accepted": 1,
                "reused": 0,
            },
            "admission": {"compiler_markdown_bytes": 0, "presented_actions": []},
        },
        {
            "kind": "proof_state_compiler.completed",
            "node": "Tree-0.0",
            "exact_observation_cache": {"hit": False},
            "certification_cache": {"hit": True},
            "resource_cache": {
                "hit": True,
                "reused_declaration_count": 1,
            },
            "timings_ms": {"total": 2, "certification": 0},
            "candidate_counts": {"actions": 1},
            "certifications": {
                "total": 1,
                "accepted": 1,
                "performed": 0,
                "performed_accepted": 0,
                "reused": 1,
            },
            "admission": {"compiler_markdown_bytes": 0, "presented_actions": []},
        },
        {
            "kind": "proof_state_compiler.completed",
            "node": "Tree-0.0",
            "exact_observation_cache": {"hit": True},
            "certification_cache": {"hit": None},
            "resource_cache": {
                "hit": None,
                "reused_declaration_count": 0,
            },
            "timings_ms": {"total": 1, "certification": 0},
            "candidate_counts": {"actions": 1},
            "certifications": {
                "total": 1,
                "accepted": 1,
                "performed": 0,
                "performed_accepted": 0,
                "reused": 1,
            },
            "admission": {"compiler_markdown_bytes": 0, "presented_actions": []},
        },
    ]

    result = metrics._collect_proof_state_compiler_economics(records)

    assert result["service_call_count"] == 3
    assert result["exact_observation_cache_hit_count"] == 1
    assert result["exact_observation_cache_miss_count"] == 2
    assert result["material_certification_cache_hit_count"] == 1
    assert result["material_certification_cache_miss_count"] == 1
    assert result["resource_cache_hit_count"] == 1
    assert result["resource_cache_miss_count"] == 1
    assert result["reused_resource_declaration_count"] == 1
    assert result["certification_attempt_count"] == 1
    assert result["certification_accepted_count"] == 1
    assert result["reused_certification_count"] == 2
    assert result["candidate_action_count"] == 3
    assert result["service_total_ms"] == 23
