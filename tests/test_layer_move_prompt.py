"""Contract tests for tree topology in child prover prompts."""
from __future__ import annotations

import inspect

from workflow.agents.prover_prompt import _build_child_prover_prompt


def _common_args() -> dict:
    return {
        "file_path": "artifacts/live_smoke/step1/chacha_poly.ec",
        "lemma_name": "step1",
        "include_dir": "easycrypt-src/theories",
        "session_tag": "prover_tree_0_0_0",
        "managed_session": {
            "workspace_view": {
                "schema_version": 3,
                "kind": "prover_workspace_view",
                "ok": True,
                "last_result": {},
                "proof_status": {
                    "status": "open",
                    "remaining_goals": 1,
                    "remaining_goals_known": True,
                    "goal_identity_required": True,
                    "goal_hash": "goal",
                },
                "current_goal": {"lines": ["authoritative_goal = true"]},
                "view_hash": "fixture-view",
            }
        },
    }


def test_child_prompt_has_no_second_proof_state_without_layer_move() -> None:
    prompt = _build_child_prover_prompt(**_common_args())

    assert "Tree branch assignment" not in prompt
    assert "authoritative_goal = true" in prompt
    for leaked in (
        "secret_parent_goal",
        "apply failed_lemma.",
        "call hidden_route.",
        "byequiv.",
        "Manager-replayed prefix",
        "`proc.`",
        "`wp.`",
    ):
        assert leaked not in prompt


def test_layer_move_renders_topology_only() -> None:
    action = {
        "kind": "layer_move_action",
        "current_layer": "call",
        "move": "down",
        "move_label": "move to a lower abstraction layer",
        "focus": ["call poly_mac1."],
        "first_failed_tactic": "apply failed_lemma.",
        "failed_experiment": {
            "experiment_kind": "bridge_rewrite",
            "failure_shape": "wrong_number_of_arguments",
            "subject": "MainD",
        },
        "proof_ir_slice": {
            "program_action_plans": [{"tactic_template": "call poly_mac1."}],
        },
    }
    prompt = _build_child_prover_prompt(
        **_common_args(),
        layer_move_action=action,
    )

    assert "Tree branch assignment" in prompt
    assert "move to a lower abstraction layer" in prompt
    assert "`call` abstraction layer" in prompt
    assert "topology only" in prompt
    assert "authoritative_goal = true" in prompt
    for leaked in (
        "call poly_mac1.",
        "apply failed_lemma.",
        "bridge_rewrite",
        "wrong_number_of_arguments",
        "MainD",
        "ProofIR Slice",
    ):
        assert leaked not in prompt


def test_old_parallel_presentation_inputs_are_not_in_child_prompt_api() -> None:
    parameters = inspect.signature(_build_child_prover_prompt).parameters

    for retired in (
        "replay_prefix",
        "negative_signal",
        "parent_goal_state",
        "discoveries",
        "blocked_openers",
    ):
        assert retired not in parameters
