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
    infer_abstraction_layer,
    tree_spawn_branch_key,
    tree_spawn_limit_for_branch_key,
    undo_repair_mode,
)


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


def test_scheduler_falls_back_to_failed_tactic_without_fact() -> None:
    key = tree_spawn_branch_key(
        3,
        "byequiv (_: ={glob A} ==> ={res}).",
    )
    assert key == ("prefix:3", "byequiv (_: ={glob A} ==> ={res})."[:40])


def main() -> int:
    test_tree_capacity_caps_active_nodes_at_four()
    test_undo_repair_mode_uses_high_water_progress()
    test_layer_move_action_key_distinguishes_layer_moves()
    test_layer_move_action_key_ignores_failure_memory_for_spawn_dedupe()
    test_layer_classifier_uses_goal_surface_only()
    test_scheduler_falls_back_to_failed_tactic_without_fact()
    print("PASS test_tree_scheduler_facts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
