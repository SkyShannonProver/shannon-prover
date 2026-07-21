"""Tests for unified prover-facing action projection."""
from __future__ import annotations

import tempfile
from pathlib import Path


import sys
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from core.easycrypt.session_events import append_event  # type: ignore  # noqa: E402
from core.easycrypt.session_prover_actions import (  # type: ignore  # noqa: E402
    build_prover_actions,
    primary_action_from_actions,
    validate_prover_actions,
)


def test_tactic_candidate_becomes_non_mutating_strategy_action() -> None:
    actions = build_prover_actions(
        session_dir=Path(".ec_session_test"),
        proof_state={
            "status": "open",
            "goal": {"active_goal_hash": "goal-hash"},
        },
        recommendations=[{
            "id": "align.swap.0",
            "kind": "swap_tactic",
            "producer": "align",
            "action": "swap{1} 7 -5.",
            "why": "Static candidate; EC has not tried it.",
            "action_type": "tactic_candidate",
            "confidence": "medium",
            "evidence_refs": ["epistemic.align"],
            "metadata": {
                "epistemic_status": "static_candidate_uncertified_by_ec",
            },
        }],
    )

    assert primary_action_from_actions(actions) == "consider_strategy_hint"
    assert actions[0]["category"] == "strategy"
    assert actions[0]["state_changed"] is False
    assert actions[0]["prover_contract"]["role"] == "tactic_candidate"
    assert "not a runnable action" in actions[0]["prover_contract"]["not_meaning"]
    assert validate_prover_actions(actions).ok is True


def test_candidate_closed_verify_action_uses_session_lemma_when_available() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        append_event(d, "session.started", {
            "file": "proof.ec",
            "lemma": "TargetLemma",
            "include_dirs": [],
            "discarded_tactic_count": 0,
            "restart_count": 1,
        })
        actions = build_prover_actions(
            session_dir=d,
            proof_state={
                "status": "candidate_closed",
                "goal": {"active_goal_hash": "goal-hash"},
            },
        )

    assert actions[0]["category"] == "verify"
    assert actions[0]["requires_instantiation"] is False
    assert "-verify TargetLemma" in actions[0]["command"]
    assert validate_prover_actions(actions).ok is True


def test_validate_actions_rejects_retired_probe_category() -> None:
    validation = validate_prover_actions([{
        "id": "bad.probe",
        "category": "probe",
        "title": "Probe tactic",
        "why": "bad state flag",
        "tool": "try",
        "command": "python3 core/easycrypt/session_cli.py -d .ec -try -c smt().",
        "tactic": "smt().",
        "state_changed": True,
    }])

    assert validation.ok is False
    assert any("category must be one of" in err for err in validation.errors)


def test_candidate_template_becomes_strategy_action() -> None:
    actions = build_prover_actions(
        session_dir=Path(".ec_session_test"),
        proof_state={
            "status": "open",
            "goal": {"active_goal_hash": "goal-hash"},
        },
        recommendations=[{
            "id": "bridge.template",
            "kind": "bridge_tactic",
            "producer": "bridge-lemmas",
            "action": "transitivity M ... .",
            "why": "Template needs an intermediate module.",
            "action_type": "tactic_candidate",
            "confidence": "medium",
            "metadata": {
                "epistemic_status": "template_requires_instantiation",
            },
        }],
    )

    assert actions[0]["category"] == "strategy"
    assert actions[0]["requires_instantiation"] is True
    assert validate_prover_actions(actions).ok is True


def test_call_inv_template_becomes_strategy() -> None:
    actions = build_prover_actions(
        session_dir=Path(".ec_session_test"),
        proof_state={
            "status": "open",
            "goal": {"active_goal_hash": "goal-hash"},
        },
        recommendations=[{
            "id": "auto_diff.template",
            "kind": "alignment_tactic",
            "producer": "AUTO-DIFF",
            "action": "call (_: Inv).",
            "why": "Template needs an explicit invariant.",
            "action_type": "tactic_candidate",
            "confidence": "medium",
            "metadata": {
                "epistemic_status": "template_requires_instantiation",
            },
        }],
    )

    assert actions[0]["category"] == "strategy"
    assert actions[0]["requires_instantiation"] is True
    assert validate_prover_actions(actions).ok is True


def test_unverified_runnable_recommendation_becomes_strategy() -> None:
    actions = build_prover_actions(
        session_dir=Path(".ec_session_test"),
        proof_state={
            "status": "open",
            "goal": {"active_goal_hash": "goal-hash"},
        },
        recommendations=[{
            "id": "goal-parser.0",
            "kind": "tactic_candidate",
            "producer": "goal-parser",
            "action": "smt().",
            "why": "Parser suggestion; EC has not tried it.",
            "action_type": "runnable_tactic",
            "confidence": "medium",
        }],
    )

    assert primary_action_from_actions(actions) == "consider_strategy_hint"
    assert actions[0]["category"] == "strategy"
    assert actions[0]["state_changed"] is False
    assert actions[0]["epistemic_status"] == "strategy"
    assert validate_prover_actions(actions).ok is True


def test_verified_runnable_recommendation_becomes_commit() -> None:
    actions = build_prover_actions(
        session_dir=Path(".ec_session_test"),
        proof_state={
            "status": "open",
            "goal": {"active_goal_hash": "goal-hash"},
        },
        recommendations=[{
            "id": "try.accepted",
            "kind": "tactic_candidate",
            "producer": "try",
            "action": "smt().",
            "why": "Daemon accepted this tactic.",
            "action_type": "runnable_tactic",
            "confidence": "verified",
            "metadata": {
                "epistemic_status": "easycrypt_preflight_accepted",
            },
        }],
    )

    assert actions[0]["category"] == "commit"
    assert actions[0]["tool"] == "next"
    assert actions[0]["state_changed"] is True
    assert actions[0]["epistemic_status"] == "easycrypt_preflight_accepted"
    assert actions[0]["prover_contract"]["role"] == "verified_commit_candidate"
    assert validate_prover_actions(actions).ok is True


def test_verified_chain_recommendation_becomes_commit() -> None:
    actions = build_prover_actions(
        session_dir=Path(".ec_session_test"),
        proof_state={
            "status": "open",
            "goal": {"active_goal_hash": "goal-hash"},
        },
        recommendations=[{
            "id": "auto_bridge.chain.0",
            "kind": "tactic_chain",
            "producer": "AUTO-BRIDGE-SUGGEST",
            "action": "-chain -c 'have -> : Pr[A] = Pr[B] by byequiv=>//. rewrite -pr_AB.'",
            "why": "Daemon accepted the chain.",
            "action_type": "inspection_action",
            "confidence": "verified",
            "metadata": {
                "epistemic_status": "daemon_chain_accepted",
            },
        }],
    )

    assert actions[0]["category"] == "commit"
    assert actions[0]["tool"] == "chain"
    assert actions[0]["state_changed"] is True
    assert actions[0]["tactic"] == (
        "have -> : Pr[A] = Pr[B] by byequiv=>//. rewrite -pr_AB."
    )
    assert validate_prover_actions(actions).ok is True


def test_stale_prior_error_status_does_not_preempt_positive_action() -> None:
    actions = build_prover_actions(
        session_dir=Path(".ec_session_test"),
        proof_state={
            "status": "error",
            "goal": {"active_goal_hash": "goal-hash"},
        },
        recommendations=[{
            "id": "try.accepted",
            "kind": "tactic_candidate",
            "producer": "try",
            "action": "sp.",
            "why": "EasyCrypt accepted this tactic during private preflight.",
            "action_type": "runnable_tactic",
            "confidence": "verified",
            "metadata": {
                "epistemic_status": "easycrypt_preflight_accepted",
            },
        }],
        latest_errors=[{
            "origin": "tactic_audit",
            "severity": "noise",
            "message": "[error] invalid last instruction",
            "tactic": "rnd.",
            "temporal_scope": "prior_attempt",
            "relation_to_current_attempt": "stale_unrelated_to_current_attempt",
        }],
    )

    assert actions[0]["id"] != "inspect.latest_error"
    assert actions[0]["category"] == "commit"
    assert actions[0]["tactic"] == "sp."
    assert validate_prover_actions(actions).ok is True


def test_strategy_hint_text_that_mentions_tool_stays_strategy() -> None:
    actions = build_prover_actions(
        session_dir=Path(".ec_session_test"),
        proof_state={
            "status": "open",
            "goal": {"active_goal_hash": "goal-hash"},
        },
        recommendations=[{
            "id": "strategy.while_hint",
            "kind": "strategy_hint",
            "producer": "proof-diagnostics",
            "action": "Run `-inv-from-lemma <oracle_name>` to derive the call invariant.",
            "why": "Goal has a while loop.",
            "action_type": "strategy_hint",
            "confidence": "medium",
        }],
    )

    assert primary_action_from_actions(actions) == "consider_strategy_hint"
    assert actions[0]["category"] == "strategy"
    assert "tool" not in actions[0]
    assert actions[0]["requires_instantiation"] is True
    assert validate_prover_actions(actions).ok is True


def test_action_menu_preserves_call_routes_when_context_candidates_crowd_menu() -> None:
    recommendations = [
        {
            "id": "proof_ir.region",
            "producer": "ProofIR",
            "action": "Inspect current procedure region summary: visible procedure regions.",
            "why": "Keep the local program shape explicit.",
            "action_type": "strategy_hint",
            "confidence": "medium",
            "metadata": {
                "proof_ir_tactic_family": "procedure_transform",
                "scheduler_role": "semantic_frontier_map",
            },
        },
        *[
            {
                "id": f"auto_call.{idx}",
                "producer": "AUTO-CALL-SUGGEST",
                "action": f"call oracle_context_{idx}.",
                "why": "Oracle-equiv context only.",
                "action_type": "strategy_hint",
                "confidence": "low",
                "metadata": {
                    "source_name": "auto_call_suggest",
                    "proof_ir_tactic_family": "call_named_equiv",
                    "epistemic_status": "context_only_not_daemon_verified",
                },
            }
            for idx in range(4)
        ],
        {
            "id": "auto_diff.named",
            "producer": "AUTO-DIFF",
            "action": "call UFCMA_genCC.",
            "why": "Static named-call alignment route.",
            "action_type": "strategy_hint",
            "confidence": "medium",
            "metadata": {
                "source_name": "auto_diff",
                "proof_ir_tactic_family": "call_named_equiv",
            },
        },
        {
            "id": "auto_diff.inv",
            "producer": "AUTO-DIFF",
            "action": "call (_: Inv).",
            "why": "Invariant-call route needs an explicit invariant.",
            "action_type": "strategy_hint",
            "confidence": "medium",
            "metadata": {
                "source_name": "auto_diff",
                "proof_ir_tactic_family": "call_invariant_skeleton",
                "requires_instantiation": True,
            },
        },
    ]

    actions = build_prover_actions(
        session_dir=Path(".ec_session_test"),
        proof_state={"status": "open", "goal": {"active_goal_hash": "goal-hash"}},
        recommendations=recommendations,
        max_actions=6,
    )
    commands = [str(action.get("command") or "") for action in actions]

    assert any("call UFCMA_genCC." in command for command in commands[:4])
    assert any("call (_: Inv)." in command for command in commands[:4])
    assert sum("oracle_context_" in command for command in commands[:4]) <= 1
    assert validate_prover_actions(actions).ok is True


def main() -> int:
    tests = [
        test_tactic_candidate_becomes_non_mutating_strategy_action,
        test_candidate_closed_verify_action_uses_session_lemma_when_available,
        test_validate_actions_rejects_retired_probe_category,
        test_candidate_template_becomes_strategy_action,
        test_call_inv_template_becomes_strategy,
        test_unverified_runnable_recommendation_becomes_strategy,
        test_verified_runnable_recommendation_becomes_commit,
        test_verified_chain_recommendation_becomes_commit,
        test_stale_prior_error_status_does_not_preempt_positive_action,
        test_strategy_hint_text_that_mentions_tool_stays_strategy,
        test_action_menu_preserves_call_routes_when_context_candidates_crowd_menu,
    ]
    for test in tests:
        test()
    print("PASS test_session_prover_actions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
