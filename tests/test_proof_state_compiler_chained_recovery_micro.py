"""Contracts for the two-failure treatment composition micro."""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

from workflow.proof_state_compiler.configuration import (
    compiler_assembly_for_profile,
)
from workflow.validation.proof_state_compiler_chained_recovery_micro import (
    CAMPAIGN_SHA256,
    CAMPAIGN_SPEC,
    INITIAL_REJECTED_TACTIC,
    MAX_LIVE_TURNS,
    PREPARED_SECOND_INTENTS,
    PROFILE,
    REPEATS,
    ExecutedIntent,
    _route_checks,
)
from workflow.validation.proof_state_compiler_chained_recovery_micro_evaluator import (
    evaluate_bundle,
)


def _executed(*, rejected: bool) -> ExecutedIntent:
    tactic = INITIAL_REJECTED_TACTIC
    if rejected:
        action = {
            "outcome_kind": "rejected",
            "proof_state_effect": "unchanged",
        }
        before = after = ()
        evidence = object()
    else:
        action = {
            "outcome_kind": "accepted",
            "proof_state_effect": "changed",
        }
        before, after = (), (tactic,)
        evidence = None
    compiler_input = SimpleNamespace(
        snapshot=SimpleNamespace(
            state_ref=SimpleNamespace(state_version=2, goal_identity="g"),
            goal_count=1,
            goal_count_known=True,
            closed=False,
        )
    )
    return ExecutedIntent(
        tactic=tactic,
        action=action,
        history_before=before,
        history_after=after,
        compiler_input_after=compiler_input,
        turn_evidence=evidence,
    )


def test_chain_preregistration_fixes_scope_without_a_new_profile() -> None:
    assert CAMPAIGN_SHA256
    assert CAMPAIGN_SPEC["fixed_initial_trigger"] == INITIAL_REJECTED_TACTIC
    assert CAMPAIGN_SPEC["scope"] == "treatment_composition_micro"
    assert CAMPAIGN_SPEC["live_turns"] == MAX_LIVE_TURNS == 2
    assert CAMPAIGN_SPEC["repeats"] == REPEATS == 3
    assert {name for name, _ in PREPARED_SECOND_INTENTS} == {
        "transitivity",
        "change",
    }

    assembly = compiler_assembly_for_profile(PROFILE)
    assert assembly is not None
    assert set(assembly.activation_plan.pass_feature_ids) == {
        "operation_binding_repair",
        "relation_bridge_realization",
    }


def test_chain_route_gate_requires_both_real_failures_and_exact_final_action() -> None:
    fixed = _executed(rejected=True)
    expected = "apply (ler_trans midpoint); first last."
    first_compilation = {
        "kind": "diagnostic",
        "item": {
            "code": "application_applicability_indeterminate",
            "primary": "X is not applicable at this proof-state phase.",
        },
    }
    second_compilation = {
        "kind": "action",
        "eligible_feature_ids": ["relation_bridge_realization"],
        "item": {
            "payload": {"tactic": expected},
            "correction": {"kind": "do_you_mean"},
        },
    }
    turns = [
        {
            "provider_valid": True,
            "relation_intent_family": "transitivity",
            "execution": {"failed_unchanged": True},
        },
        {
            "provider_valid": True,
            "model_tactic": expected,
            "execution": {
                "accepted_changed": True,
                "goal_count_known": True,
                "goal_count": 2,
            },
        },
    ]

    checks = _route_checks(
        fixed=fixed,
        first_compilation=first_compilation,
        turns=turns,
        second_compilation=second_compilation,
    )

    assert all(checks.values())


def test_chain_failure_contract_includes_manager_reverted_no_progress() -> None:
    rejected = _executed(rejected=True)
    no_progress = replace(
        rejected,
        action={
            "outcome_kind": "no_progress",
            "proof_state_effect": "unchanged",
        },
    )

    assert rejected.failed_unchanged
    assert no_progress.failed_unchanged


def test_chain_route_gate_does_not_count_a_one_turn_shortcut() -> None:
    checks = _route_checks(
        fixed=_executed(rejected=True),
        first_compilation={
            "kind": "diagnostic",
            "item": {
                "code": "application_applicability_indeterminate",
                "primary": "X is not applicable at this proof-state phase.",
            },
        },
        turns=[{
            "provider_valid": True,
            "relation_intent_family": None,
            "execution": {"accepted_changed": True},
        }],
        second_compilation={},
    )

    assert not all(checks.values())
    assert not checks["agent_selected_relation_intent"]
    assert not checks["do_you_mean_action_presented"]
    assert not checks["agent_copied_exact_action"]


def _evaluation_bundle(*, mode: str, complete: bool) -> dict:
    trajectories = []
    if mode == "model_micro":
        for repeat in range(1, REPEATS + 1):
            checks = {"all": complete}
            trajectories.append({
                "repeat": repeat,
                "provider_valid": True,
                "route_complete": complete,
                "fixed_trigger": {
                    "tactic": INITIAL_REJECTED_TACTIC,
                    "failed_unchanged": True,
                },
                "route_checks": checks,
                "turns": [
                    {
                        "provider_valid": True,
                        "relation_intent_family": "transitivity",
                        "model_tactic": "transitivity midpoint.",
                        "execution": {"failed_unchanged": True},
                        "usage": {},
                    },
                    {
                        "provider_valid": True,
                        "matches_compiler_action": complete,
                        "model_tactic": "apply (ler_trans midpoint); first last.",
                        "execution": {
                            "accepted_changed": complete,
                            "goal_count_known": True,
                            "goal_count": 2,
                        },
                        "usage": {},
                    },
                ],
            })
    return {
        "kind": "proof_state_compiler_chained_recovery_micro",
        "campaign_sha256": CAMPAIGN_SHA256,
        "mode": mode,
        "git": {"commit": "a" * 40, "dirty": False},
        "preparation_valid": True,
        "preparation_routes": [
            {"preparation_valid": True},
            {"preparation_valid": True},
        ],
        "trajectories": trajectories,
        "experiment_valid": mode == "model_micro",
    }


def test_independent_chain_evaluator_requires_all_three_complete_routes() -> None:
    passing = evaluate_bundle(
        _evaluation_bundle(mode="model_micro", complete=True),
        _evaluation_bundle(mode="prepare_only", complete=True),
    )
    failing = evaluate_bundle(
        _evaluation_bundle(mode="model_micro", complete=False),
        _evaluation_bundle(mode="prepare_only", complete=True),
    )

    assert passing["decision"] == "CHAIN_PASS"
    assert passing["complete_routes"] == 3
    assert failing["decision"] == "NO_CHAIN_VALUE"
    assert failing["complete_routes"] == 0
