"""Contracts for the preregistered five-turn recovery comparison."""

from __future__ import annotations

from workflow.validation.proof_state_compiler_five_turn_recovery_micro import (
    ARMS,
    CAMPAIGN_SHA256,
    CAMPAIGN_SPEC,
    INITIAL_REJECTED_TACTIC,
    MAX_LIVE_TURNS,
    REPEATS,
    TRAJECTORY_ORDER,
    _compilation_for_arm,
)
from workflow.validation.proof_state_compiler_five_turn_recovery_micro_evaluator import (
    _evaluate_trajectory,
    evaluate_bundle,
)


def test_five_turn_preregistration_matches_historical_six_attempt_horizon() -> None:
    assert CAMPAIGN_SHA256
    assert ARMS == ("l1", "treatment")
    assert REPEATS == 3
    assert MAX_LIVE_TURNS == 5
    assert CAMPAIGN_SPEC["fixed_trigger_counts_as_attempt"] == 1
    assert CAMPAIGN_SPEC["maximum_executed_attempts"] == 6
    assert CAMPAIGN_SPEC["sample_replacement"] is False
    assert tuple(tuple(item) for item in CAMPAIGN_SPEC["trajectory_order"]) == (
        TRAJECTORY_ORDER
    )


def test_l1_compilation_boundary_constructs_no_service_work() -> None:
    record = _compilation_for_arm(
        arm="l1",
        service=None,
        executed=object(),  # L1 must not inspect or compile the occurrence.
    )

    assert record["compile_invoked"] is False
    assert record["kind"] == "none"
    assert record["item"] == {}
    assert record["timings_ms"]["total"] == 0
    assert record["native_semantics"]["planned_request_count"] == 0


def _compilation(*, arm: str, first: bool) -> dict:
    if arm == "l1":
        return {
            "compile_invoked": False,
            "kind": "none",
            "item": {},
            "timings_ms": {"total": 0, "certification": 0},
            "native_semantics": {"elapsed_ms": 0},
        }
    if first:
        return {
            "compile_invoked": True,
            "kind": "diagnostic",
            "item": {"code": "application_applicability_indeterminate"},
            "timings_ms": {"total": 4, "certification": 0},
            "native_semantics": {"elapsed_ms": 1},
        }
    return {
        "compile_invoked": True,
        "kind": "action",
        "item": {
            "correction": {"kind": "do_you_mean"},
            "payload": {"tactic": "apply (ler_trans B); first last."},
        },
        "timings_ms": {"total": 5, "certification": 2},
        "native_semantics": {"elapsed_ms": 1},
    }


def _turn(
    *, arm: str, index: int, accepted: bool, tokens: int
) -> dict:
    execution = (
        {
            "accepted_changed": True,
            "failed_unchanged": False,
            "goal_count_known": True,
            "goal_count": 2,
        }
        if accepted
        else {
            "accepted_changed": False,
            "failed_unchanged": True,
            "goal_count_known": True,
            "goal_count": 1,
        }
    )
    panel = {"current_goal": {"lines": ["goal"]}}
    if arm == "treatment":
        panel["compiler_assist"] = [_compilation(arm=arm, first=index == 1)["item"]]
    return {
        "provider_valid": True,
        "panel": panel,
        "compilation": _compilation(arm=arm, first=index == 1),
        "model_tactic": (
            "apply (ler_trans B); first last." if accepted else "transitivity B."
        ),
        "matches_compiler_action": bool(arm == "treatment" and accepted),
        "execution": execution,
        "duration_ms": 10,
        "usage": {
            "input_tokens": tokens - 10,
            "cached_input_tokens": 0,
            "output_tokens": 10,
            "reasoning_output_tokens": 8,
            "total_tokens": tokens,
        },
    }


def _trajectory(*, arm: str, repeat: int, passing_treatment: bool) -> dict:
    if arm == "treatment":
        turns = [
            _turn(arm=arm, index=1, accepted=False, tokens=60),
            _turn(
                arm=arm,
                index=2,
                accepted=passing_treatment,
                tokens=60,
            ),
        ]
        if not passing_treatment:
            turns.extend(
                _turn(arm=arm, index=index, accepted=False, tokens=600)
                for index in range(3, 6)
            )
    else:
        turns = [
            _turn(arm=arm, index=index, accepted=False, tokens=100)
            for index in range(1, 6)
        ]
    recovery = bool(arm == "treatment" and passing_treatment)
    return {
        "arm": arm,
        "repeat": repeat,
        "fixed_trigger": {
            "tactic": INITIAL_REJECTED_TACTIC,
            "failed_unchanged": True,
        },
        "turns": turns,
        "provider_valid": True,
        "trajectory_valid": True,
        "stop_reason": "accepted_progress" if recovery else "horizon_exhausted",
        "recovery_success": recovery,
        "bridge_success": recovery,
    }


def _bundle(*, mode: str, passing_treatment: bool = True) -> dict:
    trajectories = (
        [
            _trajectory(
                arm=arm,
                repeat=repeat,
                passing_treatment=passing_treatment,
            )
            for arm, repeat in TRAJECTORY_ORDER
        ]
        if mode == "model_micro"
        else []
    )
    return {
        "kind": "proof_state_compiler_five_turn_recovery_micro",
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


def test_independent_evaluator_passes_successful_lower_token_treatment() -> None:
    evaluation = evaluate_bundle(
        _bundle(mode="model_micro"),
        _bundle(mode="prepare_only"),
    )

    assert evaluation["decision"] == "FIVE_TURN_MICRO_PASS"
    assert evaluation["arm_summaries"]["l1"]["bridge_successes"] == 0
    assert evaluation["arm_summaries"]["treatment"]["bridge_successes"] == 3
    assert evaluation["treatment_reduction_percent"]["total_tokens"] > 0


def test_independent_evaluator_rejects_costly_unsuccessful_treatment() -> None:
    evaluation = evaluate_bundle(
        _bundle(mode="model_micro", passing_treatment=False),
        _bundle(mode="prepare_only"),
    )

    assert evaluation["decision"] == "NO_FIVE_TURN_MICRO_VALUE"
    assert not evaluation["pass_criteria"][
        "minimum_two_treatment_bridge_successes"
    ]


def test_alternative_accepted_progress_is_valid_but_not_a_bridge() -> None:
    trajectory = _trajectory(arm="treatment", repeat=1, passing_treatment=True)
    trajectory["turns"][-1]["execution"]["goal_count"] = 3
    trajectory["bridge_success"] = False
    report = _evaluate_trajectory(
        trajectory,
        expected_arm="treatment",
        expected_repeat=1,
    )

    assert report["trajectory_valid"]
    assert report["recovery_success"]
    assert not report["bridge_success"]
