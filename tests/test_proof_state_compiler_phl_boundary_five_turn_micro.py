"""Contracts for the PHL transitivity-boundary five-turn micro."""

from __future__ import annotations

import json
from dataclasses import replace
from types import SimpleNamespace

from workflow.validation.proof_state_compiler_phl_boundary_five_turn_micro import (
    ARMS,
    CAMPAIGN_SHA256,
    CAMPAIGN_SPEC,
    FIXED_REJECTED_TACTIC,
    HISTORICAL_STATEMENT_GOAL_IDENTITY,
    MAX_LIVE_TURNS,
    PROFILE,
    REPEATS,
    REPLAY_PREFIX,
    TRAJECTORY_ORDER,
    ManagedStep,
    _compilation_for_arm,
    _panel,
    _provider_valid,
)
from workflow.validation.proof_state_compiler_phl_boundary_five_turn_micro_evaluator import (
    _evaluate_trajectory,
    evaluate_bundle,
)
from workflow.validation.proof_state_compiler_managed_action_model import (
    decode_managed_action_result,
)
from workflow.proof_state_compiler.profile_ids import (
    PHL_TRANSITIVITY_BOUNDARY_TREATMENT_PROFILE,
)


def test_preregistered_campaign_freezes_authentic_route_and_horizon() -> None:
    assert CAMPAIGN_SHA256 == (
        "9d22fd966aded16881361066b729e5a79de7aad621203394e27373f4597002f6"
    )
    assert PROFILE == PHL_TRANSITIVITY_BOUNDARY_TREATMENT_PROFILE
    assert ARMS == ("l1", "treatment")
    assert REPEATS == 3
    assert MAX_LIVE_TURNS == 5
    assert len(REPLAY_PREFIX) == 13
    assert REPLAY_PREFIX[-1] == "proc."
    assert CAMPAIGN_SPEC["fixed_trigger"] == FIXED_REJECTED_TACTIC
    assert CAMPAIGN_SPEC["historical_statement_goal_identity"] == (
        HISTORICAL_STATEMENT_GOAL_IDENTITY
    )
    assert CAMPAIGN_SPEC["accepted_rewind_stops_early"] is False
    assert CAMPAIGN_SPEC["sample_replacement"] is False
    assert tuple(tuple(item) for item in CAMPAIGN_SPEC["trajectory_order"]) == (
        TRAJECTORY_ORDER
    )


def _runtime(*, goal_identity: str = "goal", lines: tuple[str, ...] = ("goal",)):
    snapshot = SimpleNamespace(
        state_ref=SimpleNamespace(
            state_version=4,
            goal_identity=goal_identity,
        ),
        goal_count=1,
        goal_count_known=True,
        closed=False,
        goal_lines=lines,
    )
    return SimpleNamespace(snapshot=snapshot)


def _step(
    *,
    intent: str,
    tactic: str,
    before: tuple[str, ...],
    after: tuple[str, ...],
    outcome: str = "accepted",
    effect: str = "changed",
    evidence: object | None = None,
) -> ManagedStep:
    return ManagedStep(
        intent=intent,
        tactic=tactic,
        action={
            "outcome_kind": outcome,
            "proof_state_effect": effect,
            "execution_authority": {
                "structured_error": "expecting a goal of the form: equiv[F]"
            },
        },
        history_before=before,
        history_after=after,
        compiler_input_after=_runtime(),
        turn_evidence=evidence,
    )


def test_accepted_undo_changes_state_but_is_not_phl_success() -> None:
    step = _step(
        intent="undo_last_step",
        tactic="",
        before=("proc.",),
        after=(),
    )

    assert step.accepted_changed
    assert not step.accepted_phl_transitivity


def test_accepted_phl_tactic_is_the_primary_endpoint() -> None:
    tactic = "transitivity Middle.enc (true ==> true) (true ==> true)."
    step = _step(
        intent="commit_tactic",
        tactic=tactic,
        before=("proc.",),
        after=("proc.", tactic),
    )

    assert step.accepted_changed
    assert step.accepted_phl_transitivity


def test_failed_unchanged_requires_current_turn_evidence() -> None:
    step = _step(
        intent="commit_tactic",
        tactic=FIXED_REJECTED_TACTIC,
        before=REPLAY_PREFIX,
        after=REPLAY_PREFIX,
        outcome="rejected",
        effect="unchanged",
        evidence=object(),
    )

    assert step.failed_unchanged
    assert not replace(step, turn_evidence=None).failed_unchanged


def test_l1_does_zero_compiler_work_even_on_owned_failure() -> None:
    record = _compilation_for_arm(
        arm="l1",
        service=None,
        executed=object(),
    )

    assert record["compile_invoked"] is False
    assert record["kind"] == "none"
    assert record["item"] == {}
    assert record["native_semantics"]["planned_request_count"] == 0


def test_panel_advertises_manager_undo_and_treatment_only_assist() -> None:
    step = _step(
        intent="commit_tactic",
        tactic=FIXED_REJECTED_TACTIC,
        before=REPLAY_PREFIX,
        after=REPLAY_PREFIX,
        outcome="rejected",
        effect="unchanged",
        evidence=object(),
    )
    diagnostic = {"code": "phl_boundary", "primary": "boundary mismatch"}

    treatment = _panel(
        step,
        arm="treatment",
        compiler_item=diagnostic,
    )
    l1 = _panel(step, arm="l1", compiler_item={})

    assert treatment["current_goal"]["lines"] == ["goal"]
    assert treatment["proof_controls"] == [
        {"intent": "undo_last_step", "payload": {}}
    ]
    assert treatment["compiler_assist"] == [diagnostic]
    assert "compiler_assist" not in l1


def _audit() -> dict:
    return {
        "protocol_valid": True,
        "provider_errors": [],
        "protocol_unknowns": [],
        "cardinality_errors": [],
        "reasoning_text_retained": False,
        "assistant_text_retained": False,
    }


def test_provider_accepts_only_advertised_well_formed_managed_action() -> None:
    panel = {
        "proof_controls": [{"intent": "undo_last_step", "payload": {}}]
    }
    result = {
        "returncode": 0,
        "error": "",
        "tools_observed": [],
        "provider_event_audit": _audit(),
    }

    assert _provider_valid(
        result,
        intent="undo_last_step",
        tactic="",
        panel=panel,
    )
    assert not _provider_valid(
        result,
        intent="undo_last_step",
        tactic="proc.",
        panel=panel,
    )
    assert not _provider_valid(
        result,
        intent="commit_tactic",
        tactic="proc",
        panel=panel,
    )


def test_managed_action_decoder_retains_action_not_private_reasoning() -> None:
    stdout = "\n".join(
        json.dumps(item)
        for item in (
            {"type": "thread.started", "thread_id": "thread-1"},
            {"type": "turn.started"},
            {
                "type": "item.completed",
                "item": {"type": "reasoning", "text": "private reasoning"},
            },
            {
                "type": "item.completed",
                "item": {
                    "type": "agent_message",
                    "text": '{"intent":"undo_last_step","tactic":""}',
                },
            },
            {
                "type": "turn.completed",
                "usage": {"input_tokens": 10, "output_tokens": 2},
            },
        )
    )

    result = decode_managed_action_result(
        stdout,
        "",
        returncode=0,
        duration_ms=5,
        prompt="goal",
    )

    assert result["intent"] == "undo_last_step"
    assert result["tactic"] == ""
    assert result["error"] == ""
    assert "private reasoning" not in repr(result["provider_event_audit"])


def _compilation(arm: str, first: bool) -> dict:
    if arm == "l1":
        return {
            "compile_invoked": False,
            "kind": "none",
            "item": {},
            "timings_ms": {"total": 0, "certification": 0},
            "native_semantics": {"elapsed_ms": 0},
        }
    if first:
        item = {"code": "phl_boundary"}
        return {
            "compile_invoked": True,
            "kind": "diagnostic",
            "item": item,
            "timings_ms": {"total": 4, "certification": 0},
            "native_semantics": {"elapsed_ms": 2},
        }
    return {
        "compile_invoked": False,
        "kind": "none",
        "item": {},
        "timings_ms": {"total": 0, "certification": 0},
        "native_semantics": {"elapsed_ms": 0},
    }


def _turn(*, arm: str, index: int, success: bool, tokens: int) -> dict:
    compilation = _compilation(arm, first=index == 1)
    panel = {
        "current_goal": {"lines": ["goal"]},
        "proof_controls": [{"intent": "undo_last_step", "payload": {}}],
    }
    if arm == "treatment" and index == 1:
        panel["compiler_assist"] = [compilation["item"]]
    return {
        "provider_valid": True,
        "panel": panel,
        "compilation": compilation,
        "model_intent": "commit_tactic" if success else "undo_last_step",
        "model_tactic": "transitivity M.enc (true ==> true) (true ==> true)."
        if success
        else "",
        "duration_ms": 10,
        "usage": {
            "input_tokens": tokens - 10,
            "cached_input_tokens": 0,
            "output_tokens": 10,
            "reasoning_output_tokens": 5,
            "total_tokens": tokens,
        },
        "execution": {
            "accepted_changed": True,
            "accepted_phl_transitivity": success,
            "failed_unchanged": False,
        },
    }


def _trajectory(*, arm: str, repeat: int, success: bool) -> dict:
    turns = [_turn(arm=arm, index=1, success=False, tokens=40)]
    if success:
        turns.append(_turn(arm=arm, index=2, success=True, tokens=40))
    else:
        turns.extend(
            _turn(arm=arm, index=index, success=False, tokens=100)
            for index in range(2, 6)
        )
    return {
        "arm": arm,
        "repeat": repeat,
        "fixed_trigger": {
            "tactic": FIXED_REJECTED_TACTIC,
            "failed_unchanged": True,
        },
        "turns": turns,
        "trajectory_valid": True,
        "stop_reason": "accepted_phl_transitivity" if success else "horizon_exhausted",
        "phl_success": success,
        "function_boundary_reached": True,
        "repeated_boundary_mismatches": 0 if success else 1,
    }


def _bundle(*, mode: str) -> dict:
    trajectories = (
        [
            _trajectory(
                arm=arm,
                repeat=repeat,
                success=arm == "treatment",
            )
            for arm, repeat in TRAJECTORY_ORDER
        ]
        if mode == "model_micro"
        else []
    )
    return {
        "kind": "proof_state_compiler_phl_boundary_five_turn_micro",
        "campaign_sha256": CAMPAIGN_SHA256,
        "mode": mode,
        "git": {"commit": "a" * 40, "tracked_dirty": False},
        "preparation_valid": True,
        "trajectories": trajectories,
        "experiment_valid": mode == "model_micro",
    }


def test_evaluator_passes_successful_lower_token_treatment() -> None:
    evaluation = evaluate_bundle(
        _bundle(mode="model_micro"),
        _bundle(mode="prepare_only"),
    )

    assert evaluation["decision"] == "PHL_BOUNDARY_FIVE_TURN_MICRO_PASS"
    assert evaluation["arm_summaries"]["l1"]["phl_successes"] == 0
    assert evaluation["arm_summaries"]["treatment"]["phl_successes"] == 3
    assert evaluation["treatment_reduction_percent"]["total_tokens"] > 0


def test_evaluator_does_not_count_accepted_undo_as_primary_success() -> None:
    trajectory = _trajectory(arm="treatment", repeat=1, success=False)
    report = _evaluate_trajectory(
        trajectory,
        expected_arm="treatment",
        expected_repeat=1,
    )

    assert report["trajectory_valid"]
    assert not report["phl_success"]
