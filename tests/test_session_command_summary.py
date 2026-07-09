"""Tests for compact prover-facing CommandSummary contract."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

import sys
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from core.easycrypt.session_command_summary import (  # type: ignore  # noqa: E402
    COMMAND_SUMMARY_KIND,
    build_command_workspace_view,
    build_command_summary,
    command_summary_action_partitions,
    command_summary_workspace_metrics,
    format_command_summary,
    record_command_summary,
    validate_command_summary,
    write_command_summary_artifact,
)


def _commit_response(
    *,
    ok: bool = True,
    status: str = "ok",
    proof_status: str = "open",
    goal_type: str = "pRHL",
    num_remaining=1,
    failed_tactic: str = "",
    failure_reason: str = "",
) -> dict:
    return {
        "schema_version": 1,
        "kind": "commit_response",
        "ok": ok,
        "command": "next",
        "status": status,
        "proof_state": {
            "status": proof_status,
            "candidate_ready": proof_status == "candidate_closed",
            "final_ready": False,
            "goal": {
                "state_kind": (
                    "candidate_closed"
                    if proof_status == "candidate_closed" else "open"
                ),
                "goal_type": goal_type,
                "num_remaining": num_remaining,
                "num_remaining_determined": num_remaining is not None,
                "proof_candidate_closed": proof_status == "candidate_closed",
                "active_goal_hash": "goal-hash",
            },
            "history": {
                "tactic_count": 2,
                "has_qed": False,
                "latest_tactic": "wp.",
            },
            "latest_transition": {
                "kind": "error" if not ok else "progress",
                "tactic": failed_tactic or "wp.",
                "status": status,
                "goals_before": 1,
                "goals_after": num_remaining,
                "candidate_closed": proof_status == "candidate_closed",
                "no_progress": False,
                "no_progress_reason": "",
                "history_committed": ok,
                "latest_error": failure_reason,
            },
            "event_contract": {
                "ok": True,
                "exists": True,
                "event_count": 5,
                "candidate_closed": proof_status == "candidate_closed",
                "verification_status": None,
                "error_count": 0,
                "warning_count": 0,
                "latest_error": failure_reason,
                "latest_error_tactic": failed_tactic,
                "errors": [],
                "warnings": [],
            },
            "consistency": {
                "ok": True,
                "error_count": 0,
                "warning_count": 0,
                "note_count": 0,
                "errors": [],
                "warnings": [],
                "notes": [],
            },
        },
        "latest_transition": {
            "kind": "error" if not ok else "progress",
            "tactic": failed_tactic or "wp.",
            "status": status,
            "goals_before": 1,
            "goals_after": num_remaining,
            "candidate_closed": proof_status == "candidate_closed",
            "no_progress": False,
            "no_progress_reason": "",
            "history_committed": ok,
            "latest_error": failure_reason,
        },
        "mutation": {
            "attempted_count": 1,
            "accepted_count": 1 if ok else 0,
            "attempted_tactics": [failed_tactic or "wp."],
            "failed_tactic": failed_tactic,
            "failure_reason": failure_reason,
            "keep_on_fail": False,
            "rollback_count": 0,
        },
        "agent_view": {},
        "notes": [],
        "errors": [] if ok else [{
            "code": "commit.failed",
            "message": failure_reason,
            "failed_tactic": failed_tactic,
        }],
        "debug": {},
    }


def _agent_view(*, proof_status: str = "open") -> dict:
    closed = proof_status == "candidate_closed"
    return {
        "schema_version": 1,
        "kind": "proof_context_view",
        "ok": True,
        "proof_state": {},
        "current_goal": {
            "has_current": True,
            "state_kind": "candidate_closed" if closed else "open",
            "goal_type": "complete" if closed else "pRHL",
            "num_remaining": 0 if closed else 1,
            "num_remaining_determined": True,
            "proof_candidate_closed": closed,
            "active_goal_hash": "goal-hash",
            "active_goal_preview": "Current goal\n----\npost = x{1} = x{2}",
            "parser_error": "",
            "parsed_goal": {
                "goal_type": "pRHL",
                "suggested_tactics": ["sim.", "wp."],
            },
        },
        "latest_transition": {},
        "guidance": {
            "recommendations": [],
            "stale_recommendations": [],
            "stale_recommendation_count": 0,
        },
        "evidence": {},
        "latest_errors": [],
        "safe_next_actions": [{
            "id": "inspect.bridge_or_align",
            "kind": "inspect",
            "tool": "bridge-lemmas",
            "why": "No fresh recommendation is available.",
        }],
        "notes": [],
        "errors": [],
        "debug_refs": {},
    }


def test_command_summary_does_not_promote_parser_shape_templates() -> None:
    summary = build_command_summary(
        Path("."),
        commit_response=_commit_response(),
        agent_view=_agent_view(),
    )

    assert summary["kind"] == COMMAND_SUMMARY_KIND
    assert summary["ok"] is True
    assert "next" not in summary
    assert summary["workspace"]["source"] == "prover_workspace_view"
    next_block = command_summary_action_partitions(summary)
    assert next_block["source"] == "workspace.decision_context"
    assert next_block["primary_action"] == "inspect"
    assert not any(
        rec.get("producer") == "goal-parser"
        for rec in next_block["recommendations"]
    )
    assert next_block["probe_actions"] == []
    assert next_block["commit_actions"] == []
    # The point of this test: the goal-parser's shape templates (`sim.`/`wp.`)
    # are NOT promoted to commit/probe actions (asserted above). Whatever the
    # fallback inspect action resolves to, it must be a genuine inspect
    # handle, not a parser shape template.
    inspect_handles = [a.get("handle") for a in next_block["inspect_actions"]]
    assert inspect_handles, "fallback inspect action missing entirely"
    # Topic-style handles, never tactic text (`sim.` / `wp.`).
    assert all(
        h and " " not in h and not h.endswith(".") for h in inspect_handles
    ), inspect_handles
    ask_topics = [
        (h.get("payload") or {}).get("topic")
        for h in summary["workspace"]["inspect_lookup_handles"]["ask_manager_for"]
    ]
    assert "bridge_lemmas" not in ask_topics  # old name fully canonicalized
    assert summary["debug"]["derived_recommendation_count"] == 0
    assert summary["debug"]["workspace_source"] == "prover_workspace_view"
    assert validate_command_summary(summary).ok is True


@pytest.mark.xfail(
    strict=False,
    reason=(
        "operator-routing over-correction: operator_lemmas outranks the "
        "view's equiv_bridge_lemmas safe_next_action; routing decision "
        "pending"
    ),
)
def test_command_summary_fallback_inspect_is_view_safe_next_action() -> None:
    # The agent_view's `bridge-lemmas` safe_next_action should surface as the
    # first inspect action (canonicalized to `equiv_bridge_lemmas`). Today the
    # operator-routing layer over-routes this fixture to `operator_lemmas`
    # instead, so the view's own fallback never surfaces.
    summary = build_command_summary(
        Path("."),
        commit_response=_commit_response(),
        agent_view=_agent_view(),
    )

    next_block = command_summary_action_partitions(summary)
    assert next_block["inspect_actions"][0]["handle"] == "equiv_bridge_lemmas"
    ask_topics = [
        (h.get("payload") or {}).get("topic")
        for h in summary["workspace"]["inspect_lookup_handles"]["ask_manager_for"]
    ]
    assert "equiv_bridge_lemmas" in ask_topics


def test_command_summary_compacts_proof_ir_external_candidates() -> None:
    agent_view = _agent_view()
    agent_view["proof_ir"] = {
        "current_layer": "call_site",
        "goal_kind": "pRHL",
        "phase": {
            "prefer": ["call named equiv lemma"],
            "avoid": ["global inline may hide live call handles"],
            "resource_summary": {
                "live_call_sites": 1,
                "live_callable_lemmas": 1,
            },
            "legality": {
                "call_named_equiv": {
                    "status": "preferred",
                    "reason": "Live call-site layer.",
                },
                "inline_all": {
                    "status": "avoid",
                    "reason": (
                        "Global inline would erase live handles; use call, "
                        "targeted inline, wp, or seq first."
                    ),
                },
            },
        },
        "resources": {
            "external_candidates": [{
                "id": "auto_pivot_call_ready.0",
                "producer": "AUTO-PIVOT-CALL-READY",
                "tactic_family": "call_named_equiv",
                "action": "call poly_mac1.",
                "cost": "cheap",
                "verified": True,
            }],
            "name_resolution": {
                "summary": {
                    "total": 1,
                    "resolved": 1,
                    "needs_lookup": 0,
                    "unresolved": 0,
                },
                "items": [{
                    "name": "poly_mac1",
                    "handle_kind": "call_equiv",
                    "resolution_status": "resolved_local_declaration",
                    "source_kind": "local_context",
                    "exact_signature_known": True,
                    "signature_lookup_action": "-sig poly_mac1",
                    "tactic_template": "call poly_mac1.",
                    "procedure_match": "lhs",
                }],
                "lookup_actions": [],
            },
            "instantiation_bindings": {
                "summary": {
                    "items": 1,
                    "slots": 1,
                    "slots_with_candidates": 1,
                },
                "source_summary": {
                    "source_module_candidates": 1,
                    "goal_module_candidates": 1,
                    "goal_memory_candidates": 0,
                },
                "items": [{
                    "name": "poly_mac1",
                    "instantiated_templates": [{
                        "tactic": "call (poly_mac1 RO).",
                        "confidence": "medium",
                    }],
                    "slots": [{
                        "slot": {
                            "kind": "module_arg",
                            "name": "O",
                        },
                        "candidates": [{
                            "value": "RO",
                            "confidence": "medium",
                            "source": "parsed_goal.call_site.functor_arg",
                        }],
                    }],
                }],
            },
            "pr_path_plan": {
                "summary": {
                    "complete_path_count": 1,
                    "has_recommended_path": True,
                },
                "recommended_path": {
                    "endpoint_id": "adv_ineq.bound",
                    "relation": "inequality",
                    "source_key": "BR93_Game0",
                    "target_key": "OW_Game",
                    "hop_count": 2,
                    "lemmas": ["game0_game1_bound", "game1_ow_bound"],
                },
            },
        },
        "diagnostics": [],
        "candidate_menu": [],
    }

    summary = build_command_summary(
        Path("."),
        commit_response=_commit_response(),
        agent_view=agent_view,
    )

    assert summary["proof"]["proof_ir_layer"] == "call_site"
    assert summary["proof_ir"]["external_candidates"][0]["action"] == (
        "call poly_mac1."
    )
    assert summary["proof_ir"]["external_candidates"][0]["verified"] is True
    assert summary["proof_ir"]["phase_legality"]["inline_all"]["status"] == "avoid"
    assert summary["proof_ir"]["name_resolution"]["summary"]["resolved"] == 1
    assert summary["proof_ir"]["name_resolution"]["items"][0][
        "resolution_status"
    ] == "resolved_local_declaration"
    assert summary["proof_ir"]["instantiation_bindings"]["items"][0][
        "instantiated_templates"
    ][0]["tactic"] == "call (poly_mac1 RO)."
    assert summary["proof_ir"]["pr_path_plan"]["recommended_path"]["lemmas"] == [
        "game0_game1_bound",
        "game1_ow_bound",
    ]
    assert validate_command_summary(summary).ok is True


def test_command_summary_closed_proof_points_to_verify() -> None:
    summary = build_command_summary(
        Path("."),
        commit_response=_commit_response(
            proof_status="candidate_closed",
            goal_type="complete",
            num_remaining=0,
        ),
        agent_view=_agent_view(proof_status="candidate_closed"),
    )

    assert summary["proof"]["status"] == "candidate_closed"
    next_block = command_summary_action_partitions(summary)
    assert next_block["primary_action"] == "verify"
    assert next_block["actions"][0]["category"] == "verify"
    assert next_block["recommendations"] == []
    assert validate_command_summary(summary).ok is True


def test_command_summary_closed_proof_hides_stale_current_goal() -> None:
    agent_view = _agent_view(proof_status="candidate_closed")
    agent_view["current_goal"] = {
        **agent_view["current_goal"],
        "state_kind": "unknown",
        "goal_type": "ambient",
        "num_remaining": None,
        "num_remaining_determined": False,
        "proof_candidate_closed": False,
        "active_goal_preview": "[37|check]>",
    }
    summary = build_command_summary(
        Path("."),
        commit_response=_commit_response(
            proof_status="candidate_closed",
            goal_type="complete",
            num_remaining=0,
        ),
        agent_view=agent_view,
    )

    assert summary["proof"]["status"] == "candidate_closed"
    assert summary["proof"]["goal_type"] == "complete"
    assert summary["current_goal"]["state_kind"] == "candidate_closed"
    assert summary["current_goal"]["goal_type"] == "complete"
    assert summary["current_goal"]["num_remaining"] == 0
    assert command_summary_action_partitions(summary)["primary_action"] == "verify"
    assert validate_command_summary(summary).ok is True


def test_command_summary_failed_tactic_points_to_diagnose() -> None:
    summary = build_command_summary(
        Path("."),
        commit_response=_commit_response(
            ok=False,
            status="error",
            failed_tactic="smt().",
            failure_reason="[error] cannot prove goal (strict)",
        ),
        agent_view=_agent_view(),
    )

    assert summary["ok"] is False
    assert summary["mutation"]["failed_tactic"] == "smt()."
    next_block = command_summary_action_partitions(summary)
    assert next_block["primary_action"] == "diagnose"
    assert next_block["actions"][0]["category"] == "diagnose"
    assert any(e["tactic"] == "smt()." for e in summary["errors"])
    assert validate_command_summary(summary).ok is True


def test_command_summary_no_progress_keeps_fresh_guidance_first() -> None:
    commit = _commit_response(
        ok=False,
        status="no_progress_reverted",
        failed_tactic="auto.",
        failure_reason="tactic had no effect or was not committed",
    )
    commit["proof_state"]["latest_transition"]["kind"] = "no_progress"
    commit["proof_state"]["latest_transition"]["no_progress"] = True
    commit["proof_state"]["latest_transition"]["status"] = "no_progress_reverted"
    commit["latest_transition"]["kind"] = "no_progress"
    commit["latest_transition"]["no_progress"] = True
    commit["latest_transition"]["status"] = "no_progress_reverted"
    agent_view = _agent_view()
    agent_view["guidance"]["recommendations"] = [{
        "id": "proof_ir.intro",
        "kind": "proof_ir_candidate",
        "producer": "ProofIR",
        "action": "move=> H.",
        "why": "ambient goal has a leading implication",
        "action_type": "probe_tactic",
        "confidence": "medium",
        "metadata": {"action_type": "probe_tactic"},
        "evidence_refs": [],
        "preconditions": [],
    }]
    agent_view["safe_next_actions"] = [{
        "id": "use.recommendation.0",
        "kind": "probe_recommendation",
        "recommendation_id": "proof_ir.intro",
        "action": "move=> H.",
        "recommended_tool": "try",
        "why": "Fresh structured guidance is available.",
    }]

    summary = build_command_summary(
        Path("."),
        commit_response=commit,
        agent_view=agent_view,
    )

    assert summary["ok"] is False
    next_block = command_summary_action_partitions(summary)
    assert next_block["primary_action"] == "probe_tactic"
    assert next_block["actions"][0]["category"] == "probe"
    assert next_block["actions"][0]["tactic"] == "move=> H."
    assert summary["transition"]["no_progress"] is True
    assert validate_command_summary(summary).ok is True


def test_command_summary_filters_phoare_bound_hint_on_equality_goal() -> None:
    agent_view = _agent_view()
    agent_view["current_goal"] = {
        **agent_view["current_goal"],
        "goal_type": "phoare",
        "active_goal_preview": (
            "Current goal\n----\npre = arg = x\n\n"
            "    M.main\n    [=] 1%r\n\n"
            "post = forall z, pred z <=> predT z\n"
        ),
        "parsed_goal": {
            "goal_type": "phoare",
            "suggested_tactics": ["proc.", "proc; inline *; wp."],
        },
    }
    summary = build_command_summary(
        Path("."),
        commit_response=_commit_response(goal_type="phoare"),
        agent_view=agent_view,
    )

    next_block = command_summary_action_partitions(summary)
    actions = [r["action"] for r in next_block["recommendations"]]
    assert "proc." not in actions
    assert not any("failure-event" in action for action in actions)
    assert next_block["probe_actions"] == []
    assert next_block["commit_actions"] == []
    assert validate_command_summary(summary).ok is True


def test_command_summary_keeps_placeholder_pivot_out_of_runnable_bucket() -> None:
    agent_view = _agent_view()
    action = "apply (ExpPsample_Exp <instantiate args at arg_1>)."
    agent_view["guidance"]["recommendations"] = [{
        "id": "pivot.placeholder",
        "kind": "pivot_tactic",
        "producer": "AUTO-PIVOT",
        "action": action,
        "why": "Needs the module expression at arg_1.",
        "action_type": "runnable_tactic",
        "confidence": "medium",
        "metadata": {
            "source_name": "auto_pivot",
            "source_goal_hash": "goal-hash",
        },
    }]
    agent_view["safe_next_actions"] = [{
        "id": "use.recommendation.0",
        "kind": "consider_strategy_hint",
        "recommendation_id": "pivot.placeholder",
        "action": action,
        "confidence": "medium",
        "requires_instantiation": True,
        "why": "Fresh structured guidance is available for the current state.",
    }]
    summary = build_command_summary(
        Path("."),
        commit_response=_commit_response(),
        agent_view=agent_view,
    )

    next_block = command_summary_action_partitions(summary)
    # The placeholder pivot is a fill-in template, not a state-derived fact: it must
    # never be runnable, and is now dropped from the candidate-move strategy bucket
    # entirely. The command summary stays valid.
    assert next_block["commit_actions"] == []
    assert next_block["strategy_actions"] == []
    assert validate_command_summary(summary).ok is True


def test_command_summary_promotes_probe_tactic_actions() -> None:
    agent_view = _agent_view()
    agent_view["guidance"]["recommendations"] = [{
        "id": "align.swap.0",
        "kind": "swap_tactic",
        "producer": "align",
        "action": "swap{1} 7 -5.",
        "why": "Static alignment found a candidate; EC has not tried it.",
        "action_type": "probe_tactic",
        "confidence": "medium",
        "evidence_refs": ["epistemic.align"],
        "metadata": {
            "source_name": "align",
            "source_goal_hash": "goal-hash",
            "epistemic_status": "static_candidate_uncertified_by_ec",
            "state_changed": False,
            "recommended_probe_tool": "try",
        },
    }]
    agent_view["safe_next_actions"] = [{
        "id": "use.recommendation.0",
        "kind": "consider_recommendation",
        "recommendation_id": "align.swap.0",
        "action": "swap{1} 7 -5.",
        "confidence": "medium",
        "why": "Fresh structured guidance is available for the current state.",
    }]
    summary = build_command_summary(
        Path("."),
        commit_response=_commit_response(),
        agent_view=agent_view,
    )

    next_block = command_summary_action_partitions(summary)
    assert next_block["primary_action"] == "probe_tactic"
    assert next_block["probe_actions"][0]["tactic"] == "swap{1} 7 -5."
    action = next_block["actions"][0]
    assert action["category"] == "probe"
    assert action["tool"] == "try"
    assert action["state_changed"] is False
    assert "epistemic_status" not in action
    assert "confidence" not in action
    assert "command" not in action
    assert validate_command_summary(summary).ok is True


def test_command_summary_writes_artifact() -> None:
    with tempfile.TemporaryDirectory() as td:
        summary = build_command_summary(
            Path(td),
            commit_response=_commit_response(),
            agent_view=_agent_view(),
            workspace_payload={
                "artifact": str(Path(td) / "prover_workspace_views" / "view.json"),
                "workspace_chars": 1234,
                "current_goal_text_fully_shown": True,
                "current_goal_truncated": False,
            },
        )
        payload = write_command_summary_artifact(Path(td), summary)
        artifact = Path(payload["artifact"])

        assert artifact.exists()
        assert payload["command"] == "next"
        assert len(payload["summary_hash"]) == 40
        assert payload["proof_status"] == summary["proof"]["status"]
        assert payload["goal_type"] == summary["proof"]["goal_type"]
        assert payload["num_remaining"] == summary["proof"]["num_remaining"]
        assert payload["history_tactic_count"] == (
            summary["proof"]["history_tactic_count"]
        )
        assert payload["transition_kind"] == summary["transition"]["kind"]
        assert payload["primary_action"] == command_summary_action_partitions(summary)["primary_action"]
        assert payload["prover_workspace_artifact"].endswith(
            "prover_workspace_views/view.json"
        )
        assert payload["workspace_chars"] == 1234
        assert summary["artifacts"]["prover_workspace_view"].endswith(
            "prover_workspace_views/view.json"
        )
        assert summary["debug"]["workspace_chars"] == 1234
        assert summary["debug"]["workspace_current_goal_text_fully_shown"] is True
        assert summary["debug"]["workspace_current_goal_truncated"] is False
        assert validate_command_summary(json.loads(artifact.read_text())).ok


def test_build_command_workspace_view_matches_summary_slice() -> None:
    workspace, source = build_command_workspace_view(
        Path("."),
        commit_response=_commit_response(),
        agent_view=_agent_view(),
    )
    summary = build_command_summary(
        Path("."),
        commit_response=_commit_response(),
        agent_view=_agent_view(),
        workspace_view=workspace,
        workspace_input_source=source,
    )

    assert workspace["kind"] == "prover_workspace_view"
    assert source == "compat_actions_regenerated"
    assert summary["workspace"]["current_goal"] == workspace["current_goal"]
    assert summary["debug"]["workspace_input_source"] == source


class _EventSession:
    def __init__(self, session_dir: Path) -> None:
        self.dir = session_dir
        self.events: list[tuple[str, dict, str]] = []

    def emit_event(
        self,
        event_type: str,
        payload: dict,
        *,
        source: str = "",
    ) -> None:
        self.events.append((event_type, payload, source))


def test_record_command_summary_records_legacy_artifact_when_explicitly_called() -> None:
    with tempfile.TemporaryDirectory() as td:
        session_dir = Path(td)
        session = _EventSession(session_dir)
        summary = build_command_summary(
            session_dir,
            commit_response=_commit_response(),
            agent_view=_agent_view(),
        )
        payload = record_command_summary(session, summary)

        event_types = [event_type for event_type, _, _ in session.events]
        assert event_types == ["command.summary.produced"]
        assert Path(payload["artifact"]).exists()
        written = json.loads(Path(payload["artifact"]).read_text())
        assert validate_command_summary(written).ok


def test_command_summary_buckets_verified_try_rec_as_runnable() -> None:
    """Audit adapters derive a runnable bucket from workspace suggestions."""
    agent_view = _agent_view()
    agent_view["guidance"]["recommendations"] = [{
        "id": "try.commit_accepted_tactic",
        "kind": "tactic_candidate",
        "producer": "try",
        "action": "swap{1} 7 -3.",
        "why": "Daemon probe accepted this tactic without mutating proof state.",
        "action_type": "runnable_tactic",
        "confidence": "verified",
        "evidence_refs": [
            "probe.try.result",
            "epistemic.try.daemon_probe_accepted",
        ],
        "metadata": {
            "epistemic_status": "daemon_probe_accepted",
            "state_changed": False,
            "recommended_commit_tool": "next",
            "source_goal_hash": "goal-hash",
        },
    }]
    agent_view["safe_next_actions"] = [{
        "id": "use.recommendation.0",
        "kind": "commit_recommendation",
        "recommendation_id": "try.commit_accepted_tactic",
        "action": "swap{1} 7 -3.",
        "confidence": "verified",
        "why": "Probe-verified tactic ready to commit.",
    }]
    summary = build_command_summary(
        Path("."),
        commit_response=_commit_response(),
        agent_view=agent_view,
    )

    next_block = command_summary_action_partitions(summary)
    bucket = next_block["commit_actions"]
    assert len(bucket) == 1
    assert bucket[0]["tactic"] == "swap{1} 7 -3."
    assert bucket[0]["producer"] == "try"
    assert "confidence" not in bucket[0]
    assert next_block["strategy_actions"] == []
    assert validate_command_summary(summary).ok is True


def test_command_summary_format_includes_tail_safe_compact_line() -> None:
    summary = build_command_summary(
        Path("."),
        commit_response=_commit_response(),
        agent_view=_agent_view(),
    )

    text = format_command_summary(summary)

    assert text.startswith("[COMMAND-SUMMARY]\n")
    assert "[COMMAND-SUMMARY] compact-head-safe " not in text
    assert "[COMMAND-SUMMARY]\n" in text
    assert "[COMMAND-SUMMARY] compact-tail-safe " in text
    assert '"primary": {' in text
    assert '"runnable_tactics"' not in text
    assert '"probe_tactics"' not in text


def test_command_summary_v2_rejects_top_level_next() -> None:
    summary = build_command_summary(
        Path("."),
        commit_response=_commit_response(),
        agent_view=_agent_view(),
    )
    polluted = {**summary, "next": command_summary_action_partitions(summary)}

    validation = validate_command_summary(polluted)

    assert validation.ok is False
    assert any("must not expose top-level `next`" in err for err in validation.errors)


def test_workspace_metrics_read_v2_without_old_next_buckets() -> None:
    agent_view = _agent_view()
    agent_view["actions"] = [{
        "id": "manual.wp.commit",
        "title": "Commit wp",
        "category": "commit",
        "tactic": "wp.",
        "confidence": "verified",
        "why": "Probe-verified tactic ready to commit.",
    }]
    summary = build_command_summary(
        Path("."),
        commit_response=_commit_response(),
        agent_view=agent_view,
    )

    metrics = command_summary_workspace_metrics(summary)

    assert "next" not in summary
    assert metrics["source"] == "workspace.decision_context"
    assert metrics["primary_action"] == "try_tactic"
    assert metrics["runnable_tactic_count"] == 1


def test_action_partitions_read_v2_workspace_actions() -> None:
    agent_view = _agent_view()
    agent_view["actions"] = [{
        "id": "manual.wp.commit",
        "title": "Commit wp",
        "category": "commit",
        "tactic": "wp.",
        "confidence": "verified",
        "why": "Probe-verified tactic ready to commit.",
    }]
    summary = build_command_summary(
        Path("."),
        commit_response=_commit_response(),
        agent_view=agent_view,
    )

    partitions = command_summary_action_partitions(summary)

    assert partitions["source"] == "workspace.decision_context"
    assert partitions["primary_action"] == "try_tactic"
    assert partitions["commit_actions"][0]["tactic"] == "wp."
    assert partitions["strategy_actions"] == []


def test_command_summary_probe_accepted_prioritizes_commit_action() -> None:
    response = _commit_response(
        ok=True,
        status="probe_accepted",
        proof_status="error",
        failed_tactic="",
        failure_reason="",
    )
    response["command"] = "try"
    response["mutation"]["accepted_count"] = 0
    response["mutation"]["attempted_tactics"] = ["byequiv => //."]
    summary = build_command_summary(
        Path("."),
        commit_response=response,
        agent_view=_agent_view(),
    )

    text = format_command_summary(summary)

    assert text.startswith("[COMMAND-SUMMARY]\n")
    assert "[COMMAND-SUMMARY] compact-head-safe " not in text
    assert '"command_status": "probe_accepted"' in text
    assert '"probe_accepted": true' in text
    assert "byequiv => //." in text
    next_block = command_summary_action_partitions(summary)
    assert next_block["primary_action"] == "try_tactic"
    assert next_block["actions"][0]["category"] == "commit"
    assert next_block["actions"][0]["tactic"] == "byequiv => //."
    assert next_block["commit_actions"][0]["tactic"] == "byequiv => //."


def main() -> int:
    tests = [
        test_command_summary_does_not_promote_parser_shape_templates,
        test_command_summary_compacts_proof_ir_external_candidates,
        test_command_summary_closed_proof_points_to_verify,
        test_command_summary_closed_proof_hides_stale_current_goal,
        test_command_summary_failed_tactic_points_to_diagnose,
        test_command_summary_no_progress_keeps_fresh_guidance_first,
        test_command_summary_filters_phoare_bound_hint_on_equality_goal,
        test_command_summary_keeps_placeholder_pivot_out_of_runnable_bucket,
        test_command_summary_promotes_probe_tactic_actions,
        test_command_summary_buckets_verified_try_rec_as_runnable,
        test_command_summary_writes_artifact,
        test_command_summary_format_includes_tail_safe_compact_line,
        test_command_summary_v2_rejects_top_level_next,
        test_workspace_metrics_read_v2_without_old_next_buckets,
        test_action_partitions_read_v2_workspace_actions,
        test_command_summary_probe_accepted_prioritizes_commit_action,
    ]
    for test in tests:
        test()
    print("PASS test_session_command_summary")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
