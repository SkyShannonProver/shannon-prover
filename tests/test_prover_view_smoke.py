"""Tests for reusable prover-facing view smoke audit."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path


import sys
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from core.easycrypt.session_agent_view import build_proof_context_view, write_proof_context_view_artifact  # type: ignore  # noqa: E402
from core.easycrypt.session_events import append_event  # type: ignore  # noqa: E402
from core.easycrypt.session_projection import (  # type: ignore  # noqa: E402
    projection_to_goal_info,
    read_proof_state_projection,
)
from core.easycrypt.session_tool_view import make_tool_view, write_tool_view_artifact  # type: ignore  # noqa: E402
from tests.helpers.builders import start_event, write_open_goal  # noqa: E402
from workflow.validation.prover_view_smoke import audit_session_dir  # noqa: E402

_write_open_goal = write_open_goal
_start_event = start_event


def _proof_state(d: Path) -> dict:
    return projection_to_goal_info(read_proof_state_projection(d))


def _emit_tool_view(d: Path, view: dict) -> None:
    payload = write_tool_view_artifact(d, view)
    append_event(d, "tool.view.produced", payload)


def _issue_codes(report: dict) -> set[str]:
    return {str(issue.get("code") or "") for issue in report.get("issues", [])}


def _clean_goal_info_view(proof_state: dict) -> dict:
    return make_tool_view(
        tool="goal-info",
        proof_state=proof_state,
        guidance={"goal_info": {"goal_type": "ambient", "suggested_tactics": ["smt()."]}},
        recommendations=[{
            "id": "goal_info.tactic.0",
            "kind": "tactic_candidate",
            "producer": "goal-info",
            "action": "smt().",
            "why": "Static parser candidate; probe before committing.",
            "action_type": "probe_tactic",
            "confidence": "medium",
            "preconditions": [],
            "source_refs": [],
            "evidence_refs": ["epistemic.goal_info.tactic.0"],
            "metadata": {
                "epistemic_status": "static_parser_candidate_uncertified_by_ec",
            },
        }],
        evidence={
            "deterministic": [{
                "id": "deterministic.goal_parser",
                "producer": "ec_goal_parser",
            }],
            "epistemic": [{
                "id": "epistemic.goal_info.tactic.0",
                "producer": "goal-info",
            }],
        },
        debug={"legacy_top_level_fields": False},
    ).to_dict()


def _accepted_try_view(proof_state: dict, tactic: str = "smt().") -> dict:
    return make_tool_view(
        tool="try",
        proof_state=proof_state,
        recommendations=[{
            "id": "try.commit_accepted_tactic",
            "kind": "tactic_candidate",
            "producer": "try",
            "action": tactic,
            "why": "Daemon probe accepted this tactic.",
            "action_type": "runnable_tactic",
            "confidence": "verified",
            "preconditions": ["Commit with -next to mutate proof state."],
            "source_refs": [],
            "evidence_refs": ["probe.try.result"],
            "metadata": {
                "epistemic_status": "daemon_probe_accepted",
                "state_changed": False,
            },
        }],
        evidence={
            "probe": [{
                "id": "probe.try.result",
                "producer": "daemon.try_tactic",
                "tactic": tactic,
                "accepted": True,
                "no_progress_predicted": False,
                "mutates_proof_state": False,
            }],
        },
        notes=[{
            "code": "try.state_unchanged",
            "message": "Speculative probe did not mutate the committed proof state.",
        }],
    ).to_dict()


def _avoid_try_view(proof_state: dict, tactic: str = "simplify.") -> dict:
    return make_tool_view(
        tool="try",
        proof_state=proof_state,
        recommendations=[{
            "id": "try.avoid_no_progress_tactic",
            "kind": "avoid_tactic",
            "producer": "try",
            "action": tactic,
            "why": "Daemon probe predicted no progress.",
            "action_type": "avoid_action",
            "confidence": "high",
            "preconditions": [],
            "source_refs": [],
            "evidence_refs": ["probe.try.result"],
            "metadata": {
                "epistemic_status": "daemon_probe_no_progress",
                "state_changed": False,
            },
        }],
        evidence={
            "probe": [{
                "id": "probe.try.result",
                "producer": "daemon.try_tactic",
                "tactic": tactic,
                "accepted": True,
                "no_progress_predicted": True,
                "mutates_proof_state": False,
            }],
        },
    ).to_dict()


def test_prover_view_smoke_accepts_clean_session() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        _write_open_goal(d)
        _start_event(d)
        proof_state = _proof_state(d)
        _emit_tool_view(d, _clean_goal_info_view(proof_state))
        _emit_tool_view(d, _accepted_try_view(proof_state))
        view = build_proof_context_view(d)
        payload = write_proof_context_view_artifact(d, view)
        append_event(d, "agent.view.produced", payload)

        report = audit_session_dir(d)

        assert report["ok"] is True
        assert report["error_count"] == 0
        assert report["tool_view_count"] == 2
        assert report["agent_view_count"] == 1


def test_prover_view_smoke_rejects_legacy_goal_info_envelope() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        _write_open_goal(d)
        _start_event(d)
        proof_state = _proof_state(d)
        bad = _clean_goal_info_view(proof_state)
        bad["guidance"].pop("goal_info", None)
        bad["debug"]["legacy_top_level_fields"] = True
        bad["tool_view"] = {"legacy": True}
        _emit_tool_view(d, bad)

        report = audit_session_dir(d)
        codes = _issue_codes(report)

        assert report["ok"] is False
        assert "goal_info_payload_missing" in codes
        assert "goal_info_legacy_envelope_flag" in codes
        assert "nested_legacy_tool_view" in codes


def test_prover_view_smoke_rejects_try_without_action_semantics() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        _write_open_goal(d)
        _start_event(d)
        proof_state = _proof_state(d)
        bad = _accepted_try_view(proof_state)
        bad["guidance"]["recommendations"] = []
        _emit_tool_view(d, bad)

        report = audit_session_dir(d)

        assert report["ok"] is False
        assert "accepted_try_missing_commit_recommendation" in _issue_codes(report)


def test_prover_view_smoke_rejects_avoid_as_safe_next_action() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        _write_open_goal(d)
        _start_event(d)
        proof_state = _proof_state(d)
        _emit_tool_view(d, _avoid_try_view(proof_state))
        view = build_proof_context_view(d)
        avoid_id = view["guidance"]["recommendations"][0]["id"]
        view["safe_next_actions"].append({
            "kind": "commit_tactic",
            "action": "simplify.",
            "recommendation_id": avoid_id,
        })
        payload = write_proof_context_view_artifact(d, view)
        append_event(d, "agent.view.produced", payload)

        report = audit_session_dir(d)

        assert report["ok"] is False
        assert "safe_next_action_points_to_avoid" in _issue_codes(report)


def test_prover_view_smoke_rejects_unverified_commit_action() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        _write_open_goal(d)
        _start_event(d)
        proof_state = _proof_state(d)
        _emit_tool_view(d, _accepted_try_view(proof_state))
        view = build_proof_context_view(d)
        view["actions"][0]["confidence"] = "medium"
        view["actions"][0]["epistemic_status"] = "unverified_candidate"
        view["actions"][0]["metadata"]["daemon_ready"] = False
        view["actions"][0]["metadata"]["epistemic_status"] = "unverified_candidate"
        view["guidance"]["recommendations"][0]["confidence"] = "medium"
        view["guidance"]["recommendations"][0]["metadata"]["epistemic_status"] = (
            "unverified_candidate"
        )
        payload = write_proof_context_view_artifact(d, view)
        append_event(d, "agent.view.produced", payload)

        report = audit_session_dir(d)
        codes = _issue_codes(report)

        assert report["ok"] is False
        assert "commit_action_not_verified" in codes
        assert "active_runnable_recommendation_not_verified" in codes


def test_prover_view_smoke_rejects_corrupt_json_artifact() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        (d / "tool_views").mkdir()
        (d / "tool_views" / "bad.json").write_text("{not json", encoding="utf-8")

        report = audit_session_dir(d)

        assert report["ok"] is False
        assert "invalid_json_artifact" in _issue_codes(report)


def test_prover_view_smoke_rejects_unbalanced_negative_text() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        _write_open_goal(d)
        _start_event(d)
        proof_state = _proof_state(d)
        tool_view = make_tool_view(
            tool="goal-info",
            proof_state=proof_state,
            recommendations=[{
                "id": "bad.call",
                "kind": "call_tactic",
                "producer": "test",
                "action": "call H0.",
                "why": "H0 is not callable.",
                "action_type": "strategy_hint",
                "confidence": "medium",
                "preconditions": [],
                "source_refs": [],
                "evidence_refs": ["deterministic.test"],
                "metadata": {},
            }],
            evidence={
                "deterministic": [{
                    "id": "deterministic.test",
                    "active_goal_hash": proof_state["goal"]["active_goal_hash"],
                }],
            },
        ).to_dict()
        _emit_tool_view(d, tool_view)

        report = audit_session_dir(d)
        codes = _issue_codes(report)

        assert report["ok"] is False
        assert "not_callable_without_reason_or_repair" in codes
        assert "negative_guidance_without_repair" in codes


def test_prover_view_smoke_rejects_template_inspect_action() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        _write_open_goal(d)
        _start_event(d)
        view = build_proof_context_view(d)
        view["actions"] = [{
            "id": "bad.inspect",
            "category": "inspect",
            "title": "Inspect with tool",
            "why": "Misclassified strategy text.",
            "tool": "inspection",
            "command": "Run `-inv-from-lemma <oracle_name>` first.",
            "state_changed": False,
            "requires_instantiation": True,
        }]
        payload = write_proof_context_view_artifact(d, view)
        append_event(d, "agent.view.produced", payload)

        report = audit_session_dir(d)
        codes = _issue_codes(report)

        assert report["ok"] is False
        assert "inspect_action_requires_instantiation" in codes
        assert "generic_inspection_action" in codes


def main() -> int:
    tests = [
        test_prover_view_smoke_accepts_clean_session,
        test_prover_view_smoke_rejects_legacy_goal_info_envelope,
        test_prover_view_smoke_rejects_try_without_action_semantics,
        test_prover_view_smoke_rejects_avoid_as_safe_next_action,
        test_prover_view_smoke_rejects_unverified_commit_action,
        test_prover_view_smoke_rejects_corrupt_json_artifact,
        test_prover_view_smoke_rejects_unbalanced_negative_text,
        test_prover_view_smoke_rejects_template_inspect_action,
    ]
    for test in tests:
        test()
    print("PASS test_prover_view_smoke")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
