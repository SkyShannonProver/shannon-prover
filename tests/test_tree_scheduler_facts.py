"""Pure tests for tree scheduler policy keys."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from workflow.tree.policy import (  # noqa: E402
    TREE_MAX_ACTIVE_NODES,
    cap_tree_max_concurrent,
    effective_progress_count,
    layer_move_action_key,
    failed_experiment_memory_key,
    infer_abstraction_layer,
    infer_abstraction_layer_from_proof_ir,
    proof_ir_frontier_key,
    proof_ir_slice_for_layer_move,
    tree_spawn_branch_key,
    tree_spawn_limit_for_branch_key,
    undo_repair_mode,
)


def test_failed_experiment_memory_key_is_shape_based() -> None:
    hint = {
        "experiment_kind": "bridge_rewrite",
        "failure_shape": "wrong_number_of_arguments",
        "subject": "MainD",
    }
    key = failed_experiment_memory_key(hint)
    assert key == (
        "memory:failed_branch_experiment_cluster:"
        "bridge_rewrite:wrong_number_of_arguments:MainD"
    )
    spawn_key = tree_spawn_branch_key(
        35,
        "have := MainD(G2, FinRO).distinguish(()).",
        failed_experiment_memory=hint,
    )
    assert spawn_key == ("prefix:35", key)
    assert tree_spawn_limit_for_branch_key(spawn_key) == 1


def test_scheduler_limits_memory_guided_duplicate_children_to_one() -> None:
    memory_key = tree_spawn_branch_key(
        4,
        "have := MainD(G2, FinRO).distinguish(()).",
        failed_experiment_memory={
            "experiment_kind": "bridge_rewrite",
            "failure_shape": "wrong_number_of_arguments",
            "subject": "MainD",
        },
    )
    normal_key = tree_spawn_branch_key(4, "apply (local_helper &m).")
    assert tree_spawn_limit_for_branch_key(memory_key) == 1
    assert tree_spawn_limit_for_branch_key(normal_key) == 2


def test_tree_capacity_caps_active_nodes_at_four() -> None:
    assert TREE_MAX_ACTIVE_NODES == 4
    assert cap_tree_max_concurrent(9) == 4
    assert cap_tree_max_concurrent(4) == 4
    assert cap_tree_max_concurrent(0) == 1


def test_undo_repair_mode_uses_high_water_progress() -> None:
    assert undo_repair_mode(
        committed_count=8,
        max_committed_count_seen=18,
        last_undo_time=100.0,
        last_structural_undo_time=100.0,
        now=350.0,
        repair_window_seconds=300.0,
    )
    assert effective_progress_count(
        committed_count=8,
        max_committed_count_seen=18,
        in_undo_repair=True,
    ) == 18
    assert not undo_repair_mode(
        committed_count=8,
        max_committed_count_seen=18,
        last_undo_time=100.0,
        last_structural_undo_time=100.0,
        now=450.0,
        repair_window_seconds=300.0,
    )
    assert effective_progress_count(
        committed_count=8,
        max_committed_count_seen=18,
        in_undo_repair=False,
    ) == 8


def test_layer_move_action_key_distinguishes_layer_moves() -> None:
    down = {
        "kind": "layer_move_action",
        "current_layer": "pr",
        "move": "down",
    }
    up = {
        "kind": "layer_move_action",
        "current_layer": "pr",
        "move": "up",
    }
    down_key = layer_move_action_key(down)
    up_key = layer_move_action_key(up)
    assert down_key != up_key
    assert down_key == "action:layer_move:pr:down"
    assert tree_spawn_limit_for_branch_key(("prefix:4", down_key)) == 1


def test_layer_move_action_key_ignores_failure_memory_for_spawn_dedupe() -> None:
    base = {
        "kind": "layer_move_action",
        "current_layer": "prhl",
        "move": "up",
    }
    with_memory = {
        **base,
        "failed_experiment": {
            "experiment_kind": "procedure_lowering",
            "failure_shape": "goal_shape_mismatch",
            "subject": "proc",
        },
    }
    assert layer_move_action_key(base) == layer_move_action_key(with_memory)
    first = tree_spawn_branch_key(
        11,
        "proc.",
        layer_move_action=base,
        goal_hash="abcdef0123456789abcdef0123456789",
    )
    second = tree_spawn_branch_key(
        11,
        "proc.",
        layer_move_action=with_memory,
        goal_hash="abcdef0123456789abcdef0123456789",
    )
    assert first == second
    assert tree_spawn_limit_for_branch_key(first) == 1


def test_layer_classifier_uses_goal_surface_only() -> None:
    assert infer_abstraction_layer("Pr[G.main() @ &m : res] = x", []) == "pr"
    assert infer_abstraction_layer("equiv [A.f ~ B.g : true ==> ={res}]", []) == (
        "prhl"
    )


def test_layer_classifier_prefers_proof_ir_when_available() -> None:
    assert infer_abstraction_layer_from_proof_ir(
        {"current_layer": "call_site"},
        fallback="pr",
    ) == "call"
    assert infer_abstraction_layer_from_proof_ir(
        {"current_layer": "ambient_logic"},
        fallback="unknown",
    ) == "smt"
    assert infer_abstraction_layer_from_proof_ir(
        {"current_layer": "not-yet-known"},
        fallback="procedure",
    ) == "procedure"


def test_scheduler_falls_back_to_failed_tactic_without_fact() -> None:
    key = tree_spawn_branch_key(
        3,
        "byequiv (_: ={glob A} ==> ={res}).",
    )
    assert key == ("prefix:3", "byequiv (_: ={glob A} ==> ={res})."[:40])


def test_tree_spawn_key_can_use_semantic_frontier_instead_of_prefix_only() -> None:
    proof_ir = {
        "current_layer": "procedure_body",
        "goal_kind": "pRHL",
        "candidate_menu": [{
            "id": "program_frontier",
            "scheduler_role": "program_frontier_exposure",
            "action_type": "strategy_hint",
        }],
        "resources": {
            "program_ir": {
                "frontier": {"frontier_kind": "call_site_frontier"},
            },
        },
    }
    frontier_key = proof_ir_frontier_key(proof_ir)
    spawn_key = tree_spawn_branch_key(
        8,
        "wp.",
        layer_move_action={
            "kind": "layer_move_action",
            "current_layer": "procedure",
            "move": "up",
        },
        goal_hash="0123456789abcdef0123456789abcdef",
        frontier_key=frontier_key,
    )

    assert spawn_key[0].startswith("goal:0123456789abcdef01234567|")
    assert "role:program_frontier_exposure" in spawn_key[0]
    assert "frontier:call_site_frontier" in spawn_key[0]
    assert tree_spawn_limit_for_branch_key(spawn_key) == 1


def test_proof_ir_slice_for_down_move_keeps_program_plans() -> None:
    proof_ir = {
        "current_layer": "call_site",
        "goal_kind": "pRHL",
        "liveness": {
            "live_call_site_count": 2,
            "live_callable_lemma_count": 1,
        },
        "phase": {"prefer": ["call named equiv lemma"], "avoid": ["inline *"]},
        "resources": {
            "program_ir": {
                "frontier": {"has_frontier_pair": False},
                "program_diff": {
                    "action_plans": [{
                        "id": "plan.call_pair.1",
                        "kind": "call_site_exposure_plan",
                        "procedure_tail": "Poly.mac",
                        "phase_order": [{
                            "kind": "expose_last_call_frontier",
                            "tactic_family": "procedure_transform",
                            "tactic_hint": "wp.",
                            "reason": "not frontier",
                        }, {
                            "kind": "call_named_equiv",
                            "tactic_family": "call_named_equiv",
                            "tactic_template": "call poly_mac1.",
                            "reason": "consume handle",
                        }],
                    }],
                },
            },
            "handles": {
                "callable_lemmas": [{
                    "lemma": "poly_mac1",
                    "procedure": "Poly.mac",
                    "frontier_status": "requires_cut",
                }],
            },
            "name_resolution": {
                "items": [{
                    "name": "poly_mac1",
                    "resolution_status": "source_scope_check_required",
                }],
            },
        },
        "diagnostics": [],
    }

    proof_slice = proof_ir_slice_for_layer_move(proof_ir, move="down")

    assert proof_slice["move"] == "down"
    assert proof_slice["program_action_plans"][0]["procedure_tail"] == "Poly.mac"
    action = proof_slice["program_action_plans"][0]["phase_order"][1]
    assert action["tactic_shape"] == "call poly_mac1."
    assert "tactic_hint" not in action
    assert action["symbol_hint"] == "poly_mac1"
    assert proof_slice["callable_lemmas"] == []
    assert proof_slice["unresolved_lemma_hints"][0]["lemma"] == "poly_mac1"
    assert proof_slice["unresolved_lemma_hints"][0]["lookup_before_use"] == {
        "intent": "lookup_symbol",
        "payload": {"symbol": "poly_mac1"},
    }


def main() -> int:
    test_failed_experiment_memory_key_is_shape_based()
    test_scheduler_limits_memory_guided_duplicate_children_to_one()
    test_tree_capacity_caps_active_nodes_at_four()
    test_undo_repair_mode_uses_high_water_progress()
    test_layer_move_action_key_distinguishes_layer_moves()
    test_layer_move_action_key_ignores_failure_memory_for_spawn_dedupe()
    test_layer_classifier_uses_goal_surface_only()
    test_layer_classifier_prefers_proof_ir_when_available()
    test_scheduler_falls_back_to_failed_tactic_without_fact()
    test_tree_spawn_key_can_use_semantic_frontier_instead_of_prefix_only()
    test_proof_ir_slice_for_down_move_keeps_program_plans()
    print("PASS test_tree_scheduler_facts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
