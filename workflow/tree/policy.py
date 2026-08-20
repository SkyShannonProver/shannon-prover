"""Pure branch-policy helpers for tree-mode proof search.

This module owns scheduler keys and generic proof-layer actions.
It deliberately does not inspect live processes, mutate sessions, or decide
when to spawn. The supervisor in ``workflow.tree.supervisor`` uses these helpers as
its policy vocabulary.

Boundary:
* layer-move actions are tree-search actions, not proof facts.
* failed experiment facts are only dedupe memory.
* diagnostics should be rendered by diagnostic surfaces before policy consumes
  typed proof-state resources.
"""

from __future__ import annotations

import re
from typing import Any


TREE_MAX_ACTIVE_NODES = 4
DEFAULT_TREE_INITIAL_PROVERS = 2
DEFAULT_STRUCTURAL_UNDO_SPAWN_DELAY_SECONDS = 300
DEFAULT_UNDO_REPAIR_PROTECTION_SECONDS = 900


def cap_tree_max_concurrent(max_concurrent: int) -> int:
    """Clamp tree-mode active-node capacity to the default hygiene cap."""
    try:
        requested = int(max_concurrent)
    except (TypeError, ValueError):
        requested = TREE_MAX_ACTIVE_NODES
    return max(1, min(requested, TREE_MAX_ACTIVE_NODES))


def undo_repair_mode(
    *,
    committed_count: int,
    max_committed_count_seen: int,
    last_undo_time: float,
    last_structural_undo_time: float,
    now: float,
    repair_window_seconds: float = DEFAULT_UNDO_REPAIR_PROTECTION_SECONDS,
) -> bool:
    """Return whether a node is rebuilding after a meaningful undo.

    The tree supervisor should not treat a shortened current history as lost
    progress while the same long-lived agent is repairing a route it diagnosed
    itself.  This predicate is deliberately generic: it only needs an undo
    timestamp plus evidence that the node previously reached a deeper prefix.
    """
    if max_committed_count_seen <= committed_count:
        return False
    recent_undo = max(
        float(last_undo_time or 0.0),
        float(last_structural_undo_time or 0.0),
    )
    if recent_undo <= 0:
        return False
    return float(now) - recent_undo < float(repair_window_seconds)


def effective_progress_count(
    *,
    committed_count: int,
    max_committed_count_seen: int,
    in_undo_repair: bool,
) -> int:
    """Progress count used for scheduling, not proof-state authority."""
    if in_undo_repair:
        return max(int(committed_count), int(max_committed_count_seen))
    return int(committed_count)


def layer_move_action_key(layer_move_action: dict | None) -> str:
    """Return a stable scheduler key for one layer-move action."""
    if not isinstance(layer_move_action, dict):
        return ""
    current = str(layer_move_action.get("current_layer") or "").strip()
    move = str(layer_move_action.get("move") or "").strip()
    if not current or move not in {"up", "same", "down"}:
        return ""
    return f"action:layer_move:{current}:{move}"


def tree_spawn_branch_key(
    prefix_len: int,
    failed_first: str,
    layer_move_action: dict | None = None,
    *,
    goal_hash: str = "",
) -> tuple[Any, str]:
    location = (
        f"goal:{goal_hash[:24]}"
        if goal_hash
        else f"prefix:{prefix_len}"
    )
    action_key = layer_move_action_key(layer_move_action)
    if action_key:
        return (location, action_key)
    return (location, (failed_first or "")[:40])


def tree_spawn_limit_for_branch_key(branch_key: tuple[Any, str]) -> int:
    if len(branch_key) >= 2:
        key = str(branch_key[1])
        if key.startswith((
            "action:layer_move:",
        )):
            return 1
    return 2


def infer_abstraction_layer(goal_state: str, failed_suffix: list[str]) -> str:
    """Classify the active proof surface for branch spawning.

    This is intentionally generic. It classifies the active proof surface,
    not the cryptographic meaning of a particular lemma.
    """
    text = f"{goal_state}\n{' '.join(failed_suffix)}"
    lowered = text.lower()
    if "pr[" in lowered or "pr [" in lowered:
        return "pr"
    if "equiv" in lowered or ("~" in text and "==>" in text):
        return "prhl"
    if "phoare" in lowered or "islossless" in lowered:
        return "hoare"
    if re.search(r"\bcall\b|\becall\b", lowered):
        return "call"
    if re.search(r"\b(proc|inline|wp|sp|rnd|seq|while|skip)\b", lowered):
        return "procedure"
    if "smt" in lowered:
        return "smt"
    return "unknown"


def layer_move_order(current_layer: str) -> list[str]:
    """Order layer-move actions for a stuck proof layer."""
    if current_layer == "pr":
        return ["down", "same", "up"]
    if current_layer in {"prhl", "hoare", "call"}:
        return ["up", "down", "same"]
    if current_layer in {"procedure", "smt"}:
        return ["up", "same", "down"]
    return ["down", "up", "same"]


def build_layer_move_action(
    current_layer: str,
    move: str,
    *,
    failed_suffix: list[str],
) -> dict:
    """Build one scheduler-owned branch-topology assignment.

    The assignment identifies which abstraction direction makes this child a
    distinct search branch. Proof facts and tactic suggestions remain owned by
    the child's manager-produced SurfaceModel.
    """
    _ = failed_suffix
    move_labels = {
        "up": "move to a higher abstraction layer",
        "same": "try a distinct strategy at the current abstraction layer",
        "down": "move to a lower abstraction layer",
    }
    hint = {
        "kind": "layer_move_action",
        "current_layer": current_layer,
        "move": move,
        "move_label": move_labels.get(move, move),
    }
    return hint


def candidate_layer_move_actions(
    current_layer: str,
    *,
    failed_suffix: list[str],
) -> list[dict]:
    return [
        build_layer_move_action(
            current_layer,
            move,
            failed_suffix=failed_suffix,
        )
        for move in layer_move_order(current_layer)
    ]


__all__ = [
    "DEFAULT_STRUCTURAL_UNDO_SPAWN_DELAY_SECONDS",
    "DEFAULT_UNDO_REPAIR_PROTECTION_SECONDS",
    "DEFAULT_TREE_INITIAL_PROVERS",
    "TREE_MAX_ACTIVE_NODES",
    "cap_tree_max_concurrent",
    "layer_move_action_key",
    "candidate_layer_move_actions",
    "effective_progress_count",
    "infer_abstraction_layer",
    "build_layer_move_action",
    "layer_move_order",
    "tree_spawn_branch_key",
    "tree_spawn_limit_for_branch_key",
    "undo_repair_mode",
]
