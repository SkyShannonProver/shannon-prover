"""Tests for aggregate ProofContextView contract."""
from __future__ import annotations

import json
import tempfile
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]

import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from core.easycrypt import session_agent_view as session_agent_view_module  # type: ignore  # noqa: E402
from core.easycrypt.commands.session_commands import (  # type: ignore  # noqa: E402
    _build_start_agent_view,
    _stdout_structured_view,
    handle_agent_view,
)
from core.easycrypt.session_agent_view import (  # type: ignore  # noqa: E402
    PROOF_CONTEXT_VIEW_KIND,
    build_proof_context_view,
    validate_proof_context_view,
    write_proof_context_view_artifact,
)
from core.easycrypt.session_prover_workspace_view import (  # type: ignore  # noqa: E402
    PROVER_WORKSPACE_VIEW_KIND,
)
from core.easycrypt.session_api import open_session  # type: ignore  # noqa: E402
from core.easycrypt.session_events import append_event, read_events  # type: ignore  # noqa: E402
from core.easycrypt.session_projection import (  # type: ignore  # noqa: E402
    projection_to_goal_info,
    read_proof_state_projection,
)
from core.easycrypt.session_state import read_session_state  # type: ignore  # noqa: E402
from core.easycrypt.session_tool_view import make_tool_view, write_tool_view_artifact  # type: ignore  # noqa: E402
from tests.helpers.builders import (  # noqa: E402
    start_event,
    tool_called,
    tool_result,
    write_open_goal,
)

_start_event = start_event
_tool_called = tool_called
_tool_result = tool_result
_write_open_goal = write_open_goal


def _proof_state(d: Path) -> dict:
    return projection_to_goal_info(read_proof_state_projection(d))


def test_agent_view_promotes_current_tool_view_recommendation() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        _write_open_goal(d)
        _start_event(d)
        proof_state = _proof_state(d)
        tool_view = make_tool_view(
            tool="goal-info",
            proof_state=proof_state,
            recommendations=[{
                "id": "goal_info.tactic.0",
                "kind": "tactic_candidate",
                "producer": "goal-info",
                "action": "smt().",
                "why": "The parser saw an ambient equality.",
                "confidence": "medium",
                "preconditions": [],
                "source_refs": [],
                "evidence_refs": ["deterministic.goal_parser"],
                "metadata": {},
            }],
            evidence={
                "deterministic": [{
                    "id": "deterministic.goal_parser",
                    "producer": "ec_goal_parser",
                    "active_goal_hash": proof_state["goal"]["active_goal_hash"],
                }],
            },
        ).to_dict()
        payload = write_tool_view_artifact(d, tool_view)
        append_event(d, "tool.view.produced", payload)

        view = build_proof_context_view(d)
        validation = validate_proof_context_view(view)

        assert validation.ok is True
        assert view["kind"] == PROOF_CONTEXT_VIEW_KIND
        recs = view["guidance"]["recommendations"]
        assert len(recs) == 1
        assert recs[0]["action"] == "smt()."
        assert recs[0]["metadata"]["freshness"] == "active_goal_hash"
        assert recs[0]["metadata"]["source_goal_hash"] == (
            proof_state["goal"]["active_goal_hash"]
        )
        assert view["actions"][0]["category"] == "strategy"
        assert view["actions"][0]["command"] == "smt()."
        assert view["guidance"]["stale_recommendation_count"] == 0
        assert view["evidence"]["deterministic"][0]["id"].endswith(
            "deterministic.goal_parser"
        )


def test_agent_view_marks_placeholder_recommendation_as_strategy_hint() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        _write_open_goal(d)
        _start_event(d)
        proof_state = _proof_state(d)
        action = "apply (ExpPsample_Exp <instantiate args at arg_1>)."
        tool_view = make_tool_view(
            tool="goal-info",
            proof_state=proof_state,
            recommendations=[{
                "id": "pivot.placeholder",
                "kind": "pivot_tactic",
                "producer": "AUTO-PIVOT",
                "action": action,
                "why": "Needs module expression instantiation.",
                "confidence": "medium",
                "preconditions": [],
                "source_refs": [],
                "evidence_refs": ["kb.pivot"],
                "metadata": {},
            }],
            evidence={
                "kb": [{
                    "id": "kb.pivot",
                    "producer": "AUTO-PIVOT",
                    "active_goal_hash": proof_state["goal"]["active_goal_hash"],
                }],
            },
        ).to_dict()
        payload = write_tool_view_artifact(d, tool_view)
        append_event(d, "tool.view.produced", payload)

        view = build_proof_context_view(d)

        assert validate_proof_context_view(view).ok is True
        action0 = view["safe_next_actions"][0]
        assert action0["kind"] == "consider_strategy_hint"
        assert action0["requires_instantiation"] is True
        assert action0["action"] == action
        assert view["actions"][0]["category"] == "strategy"
        assert view["actions"][0]["requires_instantiation"] is True


def test_agent_view_keeps_old_goal_recommendation_stale() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        _write_open_goal(d)
        _start_event(d)
        proof_state = _proof_state(d)
        old_state = json.loads(json.dumps(proof_state))
        old_state["goal"]["active_goal_hash"] = "old-goal-hash"
        tool_view = make_tool_view(
            tool="goal-info",
            proof_state=old_state,
            recommendations=[{
                "id": "old.rec",
                "kind": "tactic_candidate",
                "producer": "goal-info",
                "action": "auto.",
                "why": "Old goal recommendation.",
                "confidence": "medium",
                "preconditions": [],
                "source_refs": [],
                "evidence_refs": ["deterministic.old"],
                "metadata": {},
            }],
            evidence={"deterministic": [{"id": "deterministic.old"}]},
            notes=["old source note"],
        ).to_dict()
        payload = write_tool_view_artifact(d, tool_view)
        append_event(d, "tool.view.produced", payload)

        view = build_proof_context_view(d)

        assert validate_proof_context_view(view).ok is True
        assert view["guidance"]["recommendations"] == []
        stale = view["guidance"]["stale_recommendations"]
        assert len(stale) == 1
        assert stale[0]["metadata"]["freshness"] == "stale_goal_hash"
        assert view["guidance"]["stale_recommendation_count"] == 1
        assert view["notes"] == []


def test_agent_view_keeps_tactic_candidate_as_strategy_context() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        _write_open_goal(d)
        _start_event(d)
        proof_state = _proof_state(d)
        tool_view = make_tool_view(
            tool="align",
            proof_state=proof_state,
            recommendations=[{
                "id": "align.swap.0",
                "kind": "swap_tactic",
                "producer": "align",
                "action": "swap{1} 7 -5.",
                "why": "Static alignment found a candidate.",
                "action_type": "tactic_candidate",
                "confidence": "medium",
                "preconditions": [],
                "source_refs": [],
                "evidence_refs": ["epistemic.align"],
                "metadata": {
                    "epistemic_status": "static_candidate_uncertified_by_ec",
                    "state_changed": False,
                    "validation_owner": "manager_commit",
                },
            }],
            evidence={
                "epistemic": [{
                    "id": "epistemic.align",
                    "producer": "align",
                    "active_goal_hash": proof_state["goal"]["active_goal_hash"],
                }],
            },
        ).to_dict()
        payload = write_tool_view_artifact(d, tool_view)
        append_event(d, "tool.view.produced", payload)

        view = build_proof_context_view(d)

        assert validate_proof_context_view(view).ok is True
        action = view["actions"][0]
        assert action["category"] == "strategy"
        assert action["state_changed"] is False
        assert action["epistemic_status"] == "static_candidate_uncertified_by_ec"
        assert view["safe_next_actions"][0]["kind"] == "consider_strategy_hint"
        assert "recommended_tool" not in view["safe_next_actions"][0]


def test_agent_view_keeps_verified_byequiv_commit_with_only_partial_pr_handles() -> None:
    fake_ir = {
        "current_layer": "pr",
        "goal_kind": "Pr_eq",
        "resources": {
            "external_candidates": [{
                "id": "tool_view.try.commit_accepted_tactic",
                "producer": "try",
                "action": "byequiv => //.",
                "tactic": "byequiv => //.",
                "tactic_family": "probability_to_program",
                "action_type": "runnable_tactic",
                "confidence": "verified",
                "verified": True,
                "cost": "moderate",
                "layer": "pr",
                "cost_factors": {
                    "expansion": "medium",
                    "irreversibility": "medium",
                },
                "legality": {
                    "status": "preferred",
                    "reason": "Pr layer can lower after prerequisites.",
                },
            }],
        },
        "phase": {"name": "pr", "resource_summary": {}},
        "candidate_menu": [{
            "id": "sig_step2_3",
            "tactic": "-where step2_3",
            "tactic_family": "signature_lookup",
            "action_type": "inspection_action",
            "cost": "free",
            "why": "Resolve exact signature before guessing.",
            "confidence": "medium",
            "preconditions": [],
            "cost_factors": {},
        }, {
            "id": "rewrite_pr_handle",
            "tactic": "rewrite step2_3.",
            "tactic_family": "rewrite",
            "action_type": "strategy_hint",
            "cost": "cheap",
            "why": "Partial Pr rewrite context remains.",
            "confidence": "medium",
            "preconditions": [],
            "cost_factors": {},
        }, {
            "id": "pr_byequiv_fallback",
            "tactic": "byequiv => //.",
            "tactic_family": "probability_to_program",
            "action_type": "tactic_candidate",
            "cost": "moderate",
            "why": "pRHL lowering is probeable while partial handles remain.",
            "confidence": "medium",
            "preconditions": [],
            "cost_factors": {"fallback_after_pr_handles": True},
        }],
        "diagnostics": [],
    }
    original = session_agent_view_module._build_proof_ir_for_view
    session_agent_view_module._build_proof_ir_for_view = (
        lambda *args, **kwargs: fake_ir
    )
    try:
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            _write_open_goal(
                d,
                "Pr[G.main() @ &m : res] = Pr[H.main() @ &m : res]",
            )
            _start_event(d)
            proof_state = _proof_state(d)
            tool_view = make_tool_view(
                tool="try",
                proof_state=proof_state,
                recommendations=[{
                    "id": "try.commit_accepted_tactic",
                    "kind": "tactic_candidate",
                    "producer": "try",
                    "action": "byequiv => //.",
                    "why": "Private EasyCrypt preflight accepted this tactic.",
                    "action_type": "runnable_tactic",
                    "confidence": "verified",
                    "preconditions": [],
                    "source_refs": [],
                    "evidence_refs": ["preflight.try.result"],
                    "metadata": {
                        "epistemic_status": "easycrypt_preflight_accepted",
                    },
                }],
                evidence={
                    "probe": [{
                        "id": "preflight.try.result",
                        "active_goal_hash": proof_state["goal"]["active_goal_hash"],
                    }],
                },
            ).to_dict()
            payload = write_tool_view_artifact(d, tool_view)
            append_event(d, "tool.view.produced", payload)

            view = build_proof_context_view(d)
    finally:
        session_agent_view_module._build_proof_ir_for_view = original

    assert view["safe_next_actions"][0]["action"] == "byequiv => //."
    assert view["safe_next_actions"][0]["kind"] == "commit_recommendation"
    assert view["safe_next_actions"][0]["recommended_tool"] == "next"
    assert view["guidance"]["recommendations"][0]["action_type"] == "runnable_tactic"


def test_agent_view_suppresses_static_candidate_when_verified_commit_exists() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        _write_open_goal(d)
        _start_event(d)
        proof_state = _proof_state(d)
        parser_view = make_tool_view(
            tool="goal-info",
            proof_state=proof_state,
            recommendations=[{
                "id": "goal_info.tactic.0",
                "kind": "tactic_candidate",
                "producer": "goal-info",
                "action": "smt().",
                "why": "Static parser candidate.",
                "action_type": "tactic_candidate",
                "confidence": "medium",
                "preconditions": [],
                "source_refs": [],
                "evidence_refs": ["epistemic.parser"],
                "metadata": {
                    "epistemic_status": "static_parser_candidate_uncertified_by_ec",
                },
            }],
            evidence={"epistemic": [{"id": "epistemic.parser"}]},
        ).to_dict()
        payload = write_tool_view_artifact(d, parser_view)
        append_event(d, "tool.view.produced", payload)

        try_view = make_tool_view(
            tool="try",
            proof_state=proof_state,
            recommendations=[{
                "id": "try.commit_accepted_tactic",
                "kind": "tactic_candidate",
                "producer": "try",
                "action": "smt().",
                "why": "Private EasyCrypt preflight accepted this tactic.",
                "action_type": "runnable_tactic",
                "confidence": "verified",
                "preconditions": [],
                "source_refs": [],
                "evidence_refs": ["preflight.try.result"],
                "metadata": {
                    "epistemic_status": "easycrypt_preflight_accepted",
                },
            }],
            evidence={"preflight": [{"id": "preflight.try.result"}]},
            notes=[{
                "code": "try.state_unchanged",
                "message": "Private preflight did not mutate the committed proof state.",
            }],
        ).to_dict()
        payload = write_tool_view_artifact(d, try_view)
        append_event(d, "tool.view.produced", payload)

        view = build_proof_context_view(d)

        assert validate_proof_context_view(view).ok is True
        recs = view["guidance"]["recommendations"]
        assert len(recs) == 1
        assert recs[0]["action_type"] == "runnable_tactic"
        assert view["actions"][0]["category"] == "commit"
        assert view["safe_next_actions"][0]["kind"] == "commit_recommendation"
        assert view["safe_next_actions"][0]["recommended_tool"] == "next"
        assert view["debug_refs"]["suppressed_preflight_recommendation_count"] == 1
        assert view["notes"] == []


def test_agent_view_safe_next_actions_skip_avoid_recommendations() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        _write_open_goal(d)
        _start_event(d)
        proof_state = _proof_state(d)
        tool_view = make_tool_view(
            tool="try",
            proof_state=proof_state,
            recommendations=[{
                "id": "try.avoid_rejected_tactic",
                "kind": "avoid_tactic",
                "producer": "try",
                "action": "simplify.",
                "why": "Private EasyCrypt preflight predicted no progress.",
                "action_type": "avoid_action",
                "confidence": "high",
                "preconditions": [],
                "source_refs": [],
                "evidence_refs": ["preflight.try.result"],
                "metadata": {
                    "epistemic_status": "easycrypt_preflight_no_progress",
                },
            }],
            evidence={"preflight": [{"id": "preflight.try.result"}]},
        ).to_dict()
        payload = write_tool_view_artifact(d, tool_view)
        append_event(d, "tool.view.produced", payload)

        view = build_proof_context_view(d)

        assert validate_proof_context_view(view).ok is True
        assert view["actions"][0]["category"] == "avoid"
        assert view["safe_next_actions"] == []


def test_agent_view_accepts_latest_transition_diagnostic_without_goal_hash() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        _write_open_goal(d)
        _start_event(d)
        _tool_called(d, "next")
        append_event(d, "tactic.submitted", {
            "tactic": "rewrite Foo.",
            "history_lines_before": 0,
            "line_count": 1,
        })
        append_event(d, "diagnostic.emitted", {
            "source": "proof_diagnostics",
            "layer": 4,
            "suppress_error": False,
            "request_rollback": False,
            "text": "[AUTO-LEMMA-HINTS]",
            "kind": "recommendation",
            "recommendations": [{
                "id": "proof_diagnostics.0",
                "kind": "strategy_hint",
                "producer": "proof-diagnostics",
                "action": "try a stronger invariant",
                "why": "The failed tactic needs stronger context.",
                "confidence": "medium",
                "preconditions": [],
                "source_refs": [],
                "evidence_refs": ["diagnostic.proof_diagnostics.0"],
                "metadata": {},
            }],
            "evidence": {
                "diagnostic": [
                    {"id": "diagnostic.proof_diagnostics.0", "producer": "diagnose"}
                ],
            },
        })
        append_event(d, "goal.changed", {
            "tactic": "rewrite Foo.",
            "goals_before": 1,
            "goals_after": 1,
            "no_more_goals": False,
            "async_check_close": False,
            "no_progress": False,
            "candidate_closed": False,
        })
        append_event(d, "tactic.result", {
            "tactic": "rewrite Foo.",
            "status": "ok",
            "history_committed": True,
            "goals_before": 1,
            "goals_after": 1,
            "candidate_closed": False,
        })
        _tool_result(d, "next")

        view = build_proof_context_view(d)

        assert validate_proof_context_view(view).ok is True
        recs = view["guidance"]["recommendations"]
        assert len(recs) == 1
        assert recs[0]["producer"] == "proof-diagnostics"
        assert recs[0]["metadata"]["freshness"] == "latest_transition"


def test_agent_view_artifact_and_handler_emit_event() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        _write_open_goal(d)
        _start_event(d)
        view = build_proof_context_view(d)
        payload = write_proof_context_view_artifact(d, view)
        assert Path(payload["artifact"]).exists()
        assert payload["schema_version"] == 1
        assert len(payload["view_hash"]) == 40
        assert payload["proof_status"] == "open"

        session = open_session(d)
        buf = StringIO()
        with redirect_stdout(buf):
            assert handle_agent_view(session, SimpleNamespace()) == 0
        out = json.loads(buf.getvalue())
        assert out["kind"] == PROVER_WORKSPACE_VIEW_KIND
        assert out["proof_status"]["status"] == "open"
        assert out["inspect_lookup_handles"]["ask_manager_for"][0]["intent"] == "operator_lemmas"
        assert any(e.get("type") == "agent.view.produced" for e in read_events(d))


def test_start_agent_view_exposes_next_action_without_raw_stdout() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        _write_open_goal(d)
        _start_event(d)
        session = open_session(d)

        view = _build_start_agent_view(
            session,
            SimpleNamespace(
                file=str(ROOT / "eval" / "examples" / "PIR.ec"),
                lemma="sxor2_cons",
                include_dirs=[],
            ),
            {"discarded_tactic_count": 0, "restart_count": 1},
        )

        assert validate_proof_context_view(view).ok is True
        assert view["kind"] == PROOF_CONTEXT_VIEW_KIND
        assert view["start"]["lemma"] == "sxor2_cons"
        assert view["proof_state"]["status"] == "open"
        assert view["actions"][0]["category"] == "inspect"
        assert view["actions"][0]["tool"] == "goal-info"


def test_agent_view_stdout_is_compact_prover_workspace_view() -> None:
    view = {
        "kind": PROOF_CONTEXT_VIEW_KIND,
        "ok": True,
        "proof_state": {
            "status": "open",
            "candidate_ready": False,
            "final_ready": False,
            "goal": {
                "state_kind": "open",
                "goal_type": "ambient",
                "num_remaining": 1,
                "num_remaining_determined": True,
                "active_goal_hash": "abc",
                "fact_source": "pretty_goal_text",
                "authority": "pretty_text_fallback",
                "authority_rank": 10,
                "ec_ground_truth": False,
            },
        },
        "guidance": {
            "recommendations": [{
                "id": "goal_info.tactic.0",
                "kind": "tactic_candidate",
                "producer": "goal-info",
                "action": "smt().",
                "why": "The parser saw an ambient equality.",
                "confidence": "medium",
                "metadata": {"epistemic_status": "static_parser_candidate"},
            }],
            "stale_recommendations": [
                {"action": "old tactic", "metadata": {"freshness": "stale_goal_hash"}},
                {"action": "older tactic", "metadata": {"freshness": "stale_goal_hash"}},
            ],
            "stale_recommendation_count": 2,
        },
        "current_goal": {
            "goal_type": "ambient",
            "active_goal_hash": "abc",
            "active_goal_preview": "x = y",
            "parsed_goal": {
                "suggested_tactics": ["smt()."],
                "tactic_details": [
                    {"tactic": "smt", "forms": [{"form": "very long"}]},
                ],
            },
        },
        "proof_ir": {
            "current_layer": "ambient_logic",
            "goal_kind": "ambient:simple_eq",
            "phase": {
                "name": "ambient_logic",
                "prefer": ["smt() for residual algebra/logic"],
                "avoid": ["undoing a correct call-level route"],
                "resource_summary": {
                    "native_ast_search_hits": 2,
                    "internal_noise": "hidden",
                },
            },
            "candidate_menu": [{
                "id": "ambient.smt.candidate",
                "action_type": "tactic_candidate",
                "tactic": "smt().",
                "tactic_family": "ambient_close",
                "why": "The parser saw an ambient equality.",
            }],
        },
        "actions": [],
        "safe_next_actions": [],
        "debug_refs": {
            "tool_view_artifacts": [f"tool_{idx}.json" for idx in range(7)],
            "session_dir": "/tmp/session",
            "event_log": "/tmp/session/events.jsonl",
        },
        "evidence": {"raw": [{"id": "raw.1", "preview": "long text"}]},
        "errors": [],
        "notes": [],
    }

    slim = _stdout_structured_view(
        view,
        proof_context_payload={
            "artifact": "/tmp/session/proof_context_views/agent.json",
            "view_hash": "1234",
        },
    )
    text = json.dumps(slim)

    assert slim["kind"] == PROVER_WORKSPACE_VIEW_KIND
    assert slim["current_goal"]["lines"] == ["x = y"]
    assert "text" not in slim["current_goal"]
    assert slim["current_goal"]["text_fully_shown"] is True
    assert slim["current_goal"]["goal_type"] == "ambient"
    assert slim["current_goal"]["source"]["ground_truth"] is False
    assert "shown_chars" not in slim["current_goal"]  # size count stripped
    assert slim["proof_status"]["status"] == "open"
    assert slim["proof_status"]["remaining_goals"] == 1
    assert "goal_lens" not in slim
    assert slim["proof_status"]["current_layer"] == "ambient_logic"
    assert slim["facts_and_diagnostics"] == {}
    assert slim["candidate_moves"] == {}
    assert "probe_tactic" not in text
    assert "full_context" not in slim["inspect_lookup_handles"]
    assert "effect" in slim["inspect_lookup_handles"]
    ask_manager_for = slim["inspect_lookup_handles"]["ask_manager_for"]
    assert ask_manager_for[0]["intent"] == "operator_lemmas"
    assert ask_manager_for[0]["payload"]["operator"]
    assert "command" not in ask_manager_for[0]
    assert "cost" not in ask_manager_for[0]
    assert "runtime_note" not in ask_manager_for[0]
    assert all("cost" not in handle for handle in ask_manager_for)
    assert "proof_ir" not in slim
    assert "guidance" not in slim
    assert "candidate_menu" not in text
    assert "old tactic" not in text
    assert "tactic_details" not in text


def test_prover_workspace_view_goal_window_preserves_multiline_goal() -> None:
    raw_goal = "\n".join([
        "Current goal",
        "equiv [ M1.f ~ M2.f :",
        "  ={glob A} ==> ={res}",
        "]",
    ])
    view = {
        "kind": PROOF_CONTEXT_VIEW_KIND,
        "ok": True,
        "proof_state": {
            "status": "open",
            "candidate_ready": False,
            "final_ready": False,
            "goal": {
                "goal_type": "equiv",
                "num_remaining": 1,
                "num_remaining_determined": True,
                "active_goal_hash": "abc",
            },
        },
        "current_goal": {
            "goal_type": "equiv",
            "active_goal_hash": "abc",
            "active_goal_preview": "Current goal equiv [ M1.f ~ M2.f ...",
            "active_goal_text": raw_goal,
        },
        "actions": [],
        "safe_next_actions": [],
        "debug_refs": {"session_dir": "/tmp/session"},
        "guidance": {},
        "errors": [],
        "notes": [],
    }

    slim = _stdout_structured_view(view)

    assert slim["current_goal"]["lines"] == raw_goal.splitlines()
    assert "text" not in slim["current_goal"]
    assert slim["current_goal"]["text_fully_shown"] is True
    assert "line_count" not in slim["current_goal"]  # size count stripped
    assert "current_session_fallback" not in slim["inspect_lookup_handles"]
    assert "files" not in slim["inspect_lookup_handles"]
    assert any("M1.f ~ M2.f" in line for line in slim["current_goal"]["lines"])


def test_prover_workspace_view_goal_lines_preserve_blank_lines() -> None:
    raw_goal = "\n".join([
        "Current goal",
        "",
        "Type variables: <none>",
        "",
        "&m: {}",
        "------------------------------------------------------------------------",
        "pre = true",
        "",
        "post = res{1} = res{2}",
        "[1|check]>",
    ])
    view = {
        "kind": PROOF_CONTEXT_VIEW_KIND,
        "ok": True,
        "proof_state": {
            "status": "open",
            "candidate_ready": False,
            "final_ready": False,
            "goal": {
                "goal_type": "equiv",
                "num_remaining": 1,
                "num_remaining_determined": True,
                "active_goal_hash": "abc",
            },
        },
        "current_goal": {
            "goal_type": "equiv",
            "active_goal_hash": "abc",
            "active_goal_preview": "Current goal",
            "active_goal_text": raw_goal,
        },
        "actions": [],
        "safe_next_actions": [],
        "debug_refs": {"session_dir": "/tmp/session"},
        "guidance": {},
        "errors": [],
        "notes": [],
    }

    slim = _stdout_structured_view(view)

    assert slim["current_goal"]["lines"] == raw_goal.splitlines()
    assert "shown_lines" not in slim["current_goal"]  # size count stripped
    assert slim["current_goal"]["text_fully_shown"] is True
    assert "current_session_fallback" not in slim["inspect_lookup_handles"]


def test_agent_view_workspace_goal_matches_raw_current_goal_block() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        (d / "current.out").write_text(
            "[41|check]>\n"
            "Current goal\n"
            "\n"
            "Type variables: <none>\n"
            "\n"
            "&m: {}\n"
            "------------------------------------------------------------------------\n"
            "&1 (left ) : {x : unit, k : key}\n"
            "&2 (right) : {b : bool}\n"
            "\n"
            "pre = (glob A){1} = (glob A){m}\n"
            "\n"
            "M1.f ~ M2.f\n"
            "\n"
            "post = res{1} = res{2}\n"
            "[42|check]>\n",
            encoding="utf-8",
        )
        _start_event(d)
        session = open_session(d)

        buf = StringIO()
        with redirect_stdout(buf):
            assert handle_agent_view(session, SimpleNamespace()) == 0
        workspace = json.loads(buf.getvalue())
        expected_lines = read_session_state(d).raw_for_goal_tools.strip("\n").splitlines()

        assert workspace["kind"] == PROVER_WORKSPACE_VIEW_KIND
        assert workspace["current_goal"]["text_fully_shown"] is True
        assert workspace["current_goal"]["truncated"] is False
        assert workspace["current_goal"]["lines"] == expected_lines
        assert "" in workspace["current_goal"]["lines"]


def test_prover_workspace_view_exposes_goal_file_only_when_truncated() -> None:
    raw_goal = "\n".join(["Current goal", *[f"line {idx}" for idx in range(900)]])
    view = {
        "kind": PROOF_CONTEXT_VIEW_KIND,
        "ok": True,
        "proof_state": {
            "status": "open",
            "candidate_ready": False,
            "final_ready": False,
            "goal": {
                "goal_type": "equiv",
                "num_remaining": 1,
                "num_remaining_determined": True,
                "active_goal_hash": "abc",
            },
        },
        "current_goal": {
            "goal_type": "equiv",
            "active_goal_hash": "abc",
            "active_goal_preview": "Current goal",
            "active_goal_text": raw_goal,
        },
        "actions": [],
        "safe_next_actions": [],
        "debug_refs": {"session_dir": "/tmp/session"},
        "guidance": {},
        "errors": [],
        "notes": [],
    }

    slim = _stdout_structured_view(view)

    assert slim["current_goal"]["text_fully_shown"] is False
    assert "current.out" in slim["inspect_lookup_handles"]["current_session_fallback"]
    assert slim["inspect_lookup_handles"]["files"][0]["path"].endswith("current.out")


def test_agent_view_stdout_turns_no_more_goals_into_qed_action() -> None:
    view = {
        "kind": PROOF_CONTEXT_VIEW_KIND,
        "ok": True,
        "proof_state": {
            "status": "unknown",
            "candidate_ready": False,
            "final_ready": False,
            "goal": {
                "state_kind": "unknown",
                "goal_type": "ambient",
                "num_remaining": None,
                "num_remaining_determined": False,
                "active_goal_hash": "closed",
                "fact_source": "pretty_goal_text",
                "authority": "pretty_text_fallback",
                "authority_rank": 10,
                "ec_ground_truth": False,
            },
            "latest_transition": {
                "kind": "closed",
                "candidate_closed": True,
                "goals_after": 0,
            },
            "event_contract": {"candidate_closed": True},
        },
        "current_goal": {
            "goal_type": "ambient",
            "active_goal_hash": "closed",
            "active_goal_preview": "No more goals\n[106|check]>",
        },
        "proof_ir": {
            "current_layer": "ambient_logic",
            "goal_kind": "ambient",
            "phase": {"name": "ambient_logic"},
        },
        "guidance": {
            "recommendations": [],
            "stale_recommendation_count": 3,
        },
        "actions": [{
            "id": "inspect.goal_info",
            "category": "inspect",
            "title": "Inspect proof state",
            "tool": "goal-info",
            "command": "python3 core/easycrypt/session_cli.py -d sess -goal-info",
            "state_changed": False,
            "confidence": "high",
            "why": "No fresh recommendation is available.",
            "requires_instantiation": False,
        }],
        "safe_next_actions": [],
        "debug_refs": {"session_dir": "/tmp/session"},
        "errors": [],
        "notes": [],
    }

    slim = _stdout_structured_view(view)

    assert slim["proof_status"]["status"] == "candidate_closed_pending_qed"
    assert slim["proof_status"]["current_layer"] == "closed_candidate"
    assert slim["candidate_moves"]["moves"][0]["category"] == "commit"
    assert slim["candidate_moves"]["moves"][0]["tactic"] == "qed."
    assert "command" not in slim["candidate_moves"]["moves"][0]


def test_agent_view_does_not_treat_undo_zero_steps_as_pending_qed() -> None:
    view = {
        "kind": PROOF_CONTEXT_VIEW_KIND,
        "ok": True,
        "proof_state": {
            "status": "open",
            "candidate_ready": False,
            "final_ready": False,
            "goal": {
                "state_kind": "open",
                "goal_type": "probability",
                "num_remaining": 1,
                "num_remaining_determined": True,
                "active_goal_hash": "prob-goal",
                "proof_candidate_closed": False,
                "fact_source": "pretty_goal_text",
                "authority": "pretty_text_fallback",
                "authority_rank": 10,
                "ec_ground_truth": False,
            },
            "latest_transition": {
                "kind": "undo",
                "candidate_closed": False,
                "goals_after": 0,
                "status": "ok",
            },
            "event_contract": {"candidate_closed": False},
        },
        "current_goal": {
            "goal_type": "probability",
            "active_goal_hash": "prob-goal",
            "active_goal_preview": (
                "Current goal\n\n"
                "Type variables: <none>\n\n"
                "&m: {}\n"
                "------------------------------------------------------------------------\n"
                "Pr[A.main() @ &m : res] =\n"
                "Pr[B.main() @ &m : res]"
            ),
            "proof_candidate_closed": False,
        },
        "proof_ir": {
            "current_layer": "pr",
            "goal_kind": "Pr_eq",
            "goal_type": "probability",
            "phase": {"name": "pr"},
        },
        "guidance": {
            "recommendations": [{
                "action": "byequiv=>//.",
                "action_type": "runnable_tactic",
                "metadata": {
                    "epistemic_status": "easycrypt_preflight_accepted",
                    "goal_after_remaining": 1,
                    "goal_after_closed": False,
                },
            }],
        },
        "actions": [],
        "safe_next_actions": [],
        "debug_refs": {"session_dir": "/tmp/session"},
        "errors": [],
        "notes": [],
    }

    slim = _stdout_structured_view(view)

    assert slim["proof_status"]["status"] == "open"
    assert slim["proof_status"]["view_focus"] == "probability"
    assert slim["current_goal"]["view_focus"] == "probability"
    moves = slim.get("candidate_moves", {}).get("moves", [])
    assert all(move.get("tactic") != "qed." for move in moves)


def main() -> int:
    tests = [
        test_agent_view_promotes_current_tool_view_recommendation,
        test_agent_view_marks_placeholder_recommendation_as_strategy_hint,
        test_agent_view_keeps_old_goal_recommendation_stale,
        test_agent_view_keeps_tactic_candidate_as_strategy_context,
        test_agent_view_keeps_verified_byequiv_commit_with_only_partial_pr_handles,
        test_agent_view_suppresses_static_candidate_when_verified_commit_exists,
        test_agent_view_safe_next_actions_skip_avoid_recommendations,
        test_agent_view_accepts_latest_transition_diagnostic_without_goal_hash,
        test_agent_view_artifact_and_handler_emit_event,
        test_start_agent_view_exposes_next_action_without_raw_stdout,
        test_agent_view_stdout_is_compact_prover_workspace_view,
        test_prover_workspace_view_goal_window_preserves_multiline_goal,
        test_prover_workspace_view_goal_lines_preserve_blank_lines,
        test_prover_workspace_view_exposes_goal_file_only_when_truncated,
        test_agent_view_stdout_turns_no_more_goals_into_qed_action,
        test_agent_view_does_not_treat_undo_zero_steps_as_pending_qed,
    ]
    for test in tests:
        test()
    print("PASS test_session_agent_view")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
