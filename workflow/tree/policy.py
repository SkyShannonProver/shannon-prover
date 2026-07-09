"""Pure branch-policy helpers for tree-mode proof search.

This module owns scheduler keys and generic proof-layer actions.
It deliberately does not inspect live processes, mutate sessions, or decide
when to spawn. The supervisor in ``workflow.progress`` uses these helpers as
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


def failed_experiment_memory_key(failed_experiment_memory: dict | None) -> str:
    """Return a stable scheduler key for generic failed-experiment memory."""
    if not isinstance(failed_experiment_memory, dict):
        return ""
    kind = str(failed_experiment_memory.get("experiment_kind") or "").strip()
    shape = str(failed_experiment_memory.get("failure_shape") or "").strip()
    subject = str(failed_experiment_memory.get("subject") or "").strip()
    if not kind or not shape or not subject:
        return ""
    return f"memory:failed_branch_experiment_cluster:{kind}:{shape}:{subject}"


def layer_move_action_key(layer_move_action: dict | None) -> str:
    """Return a stable scheduler key for one layer-move action."""
    if not isinstance(layer_move_action, dict):
        return ""
    current = str(layer_move_action.get("current_layer") or "").strip()
    move = str(layer_move_action.get("move") or "").strip()
    if not current or move not in {"up", "same", "down"}:
        return ""
    return f"action:layer_move:{current}:{move}"


def proof_ir_frontier_key(proof_ir: dict | None) -> str:
    """Return a semantic frontier key for spawn dedupe.

    The tree scheduler should avoid cloning the same proof frontier just
    because the accepted prefix grew by a tactic or two.  This key uses the
    typed ProofIR surface when available and deliberately stays generic:
    current layer, goal kind, first scheduler role, and program frontier kind.
    """
    if not isinstance(proof_ir, dict):
        return ""
    layer = str(proof_ir.get("current_layer") or "").strip()
    goal_kind = str(proof_ir.get("goal_kind") or "").strip()
    role = ""
    for item in _as_list(proof_ir.get("candidate_menu")):
        if not isinstance(item, dict):
            continue
        action_type = str(item.get("action_type") or "")
        if action_type == "avoid_action":
            continue
        role = str(
            item.get("scheduler_role")
            or _as_dict(item.get("scheduler")).get("scheduler_role")
            or _as_dict(item.get("cost_factors")).get("scheduler_role")
            or ""
        ).strip()
        if role:
            break
    resources = _as_dict(proof_ir.get("resources"))
    program_ir = _as_dict(resources.get("program_ir"))
    frontier = _as_dict(program_ir.get("frontier"))
    frontier_kind = str(
        frontier.get("frontier_kind")
        or frontier.get("kind")
        or frontier.get("status")
        or ""
    ).strip()
    parts = [
        f"layer:{layer}" if layer else "",
        f"goal:{goal_kind}" if goal_kind else "",
        f"role:{role}" if role else "",
        f"frontier:{frontier_kind}" if frontier_kind else "",
    ]
    key = "|".join(part for part in parts if part)
    return key[:240]


def tree_spawn_branch_key(
    prefix_len: int,
    failed_first: str,
    failed_experiment_memory: dict | None = None,
    layer_move_action: dict | None = None,
    *,
    goal_hash: str = "",
    frontier_key: str = "",
) -> tuple[Any, str]:
    location = (
        f"goal:{goal_hash[:24]}"
        if goal_hash
        else f"prefix:{prefix_len}"
    )
    if frontier_key:
        location = f"{location}|{frontier_key}"
    action_key = layer_move_action_key(layer_move_action)
    if action_key:
        return (location, action_key)
    experiment_key = failed_experiment_memory_key(failed_experiment_memory)
    if experiment_key:
        return (location, experiment_key)
    return (location, (failed_first or "")[:40])


def tree_spawn_limit_for_branch_key(branch_key: tuple[Any, str]) -> int:
    if len(branch_key) >= 2:
        key = str(branch_key[1])
        if key.startswith((
            "memory:failed_branch_experiment_cluster:",
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


def infer_abstraction_layer_from_proof_ir(
    proof_ir: dict | None,
    *,
    fallback: str = "unknown",
) -> str:
    """Map ProofIR's typed layer names to tree policy layer names."""
    if not isinstance(proof_ir, dict):
        return fallback
    layer = str(proof_ir.get("current_layer") or "").strip()
    mapping = {
        "pr": "pr",
        "prhl_module": "prhl",
        "call_site": "call",
        "procedure_body": "procedure",
        "ambient_logic": "smt",
    }
    return mapping.get(layer, fallback)


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
    failed_experiment_memory: dict | None = None,
) -> dict:
    """Build one prompt/scheduler action for a layer-move experiment."""
    first_failed = failed_suffix[0] if failed_suffix else ""
    move_labels = {
        "up": "move to a higher abstraction layer",
        "same": "try a distinct strategy at the current abstraction layer",
        "down": "move to a lower abstraction layer",
    }
    focus_by_move = {
        "up": [
            "look for a Pr-level pivot, transitivity target, wrapper lemma, or missing intermediate assertion",
            "undo over-lowering if the parent expanded procedures before using call/bridge structure",
        ],
        "same": [
            "keep the same layer but choose a different opener family or intermediate",
            "use the parent failure only as a negative example, not as a syntax template",
        ],
        "down": [
            "commit to the next lower proof surface such as pRHL, call, or procedure steps",
            "prefer selective lowering and preserve call sites when oracle equivalences may apply",
        ],
    }
    hint = {
        "kind": "layer_move_action",
        "current_layer": current_layer,
        "move": move,
        "move_label": move_labels.get(move, move),
        "focus": focus_by_move.get(move, []),
        "first_failed_tactic": first_failed,
    }
    if failed_experiment_memory:
        hint["failed_experiment"] = dict(failed_experiment_memory)
    return hint


def candidate_layer_move_actions(
    current_layer: str,
    *,
    failed_suffix: list[str],
    failed_experiment_memory: dict | None = None,
) -> list[dict]:
    return [
        build_layer_move_action(
            current_layer,
            move,
            failed_suffix=failed_suffix,
            failed_experiment_memory=failed_experiment_memory,
        )
        for move in layer_move_order(current_layer)
    ]


def proof_ir_slice_for_layer_move(
    proof_ir: dict | None,
    *,
    move: str,
    max_items: int = 4,
) -> dict:
    """Return a compact ProofIR view suitable for one child branch.

    The full ProofContextView can be large.  A child only needs the compiler
    resources relevant to its assigned layer move: high-level handles for
    moving up, cost-ranked candidates for staying put, and ProgramIR action
    plans for moving down.
    """
    if not isinstance(proof_ir, dict):
        return {}
    resources = _as_dict(proof_ir.get("resources"))
    handles = _as_dict(resources.get("handles"))
    name_resolution = _as_dict(resources.get("name_resolution"))
    program_ir = _as_dict(resources.get("program_ir"))
    program_diff = _as_dict(program_ir.get("program_diff"))
    slice_data: dict[str, Any] = {
        "kind": "proof_ir_layer_slice",
        "move": move if move in {"up", "same", "down"} else "same",
        "current_layer": str(proof_ir.get("current_layer") or ""),
        "goal_kind": str(proof_ir.get("goal_kind") or ""),
        "liveness": _compact_liveness(_as_dict(proof_ir.get("liveness"))),
        "phase": _compact_phase(_as_dict(proof_ir.get("phase"))),
        "diagnostics": _compact_diagnostics(proof_ir, max_items=max_items),
    }
    if slice_data["move"] == "up":
        slice_data["pr_path_plan"] = _compact_pr_path_plan(
            _as_dict(resources.get("pr_path_plan")),
        )
        slice_data["name_resolution"] = _compact_name_resolution(
            _as_dict(resources.get("name_resolution")),
            max_items=max_items,
        )
    elif slice_data["move"] == "down":
        slice_data["program_frontier"] = _as_dict(program_ir.get("frontier"))
        slice_data["program_action_plans"] = [
            _compact_program_action_plan(plan, name_resolution=name_resolution)
            for plan in _as_list(program_diff.get("action_plans"))[:max_items]
            if isinstance(plan, dict)
        ]
        compacted_lemmas = [
            _compact_callable_lemma(handle, name_resolution=name_resolution)
            for handle in _as_list(handles.get("callable_lemmas"))[:max_items]
            if isinstance(handle, dict)
        ]
        slice_data["callable_lemmas"] = [
            item for item in compacted_lemmas
            if item.get("resolution_status") not in _UNRESOLVED_NAME_STATUSES
        ]
        slice_data["unresolved_lemma_hints"] = [
            item for item in compacted_lemmas
            if item.get("resolution_status") in _UNRESOLVED_NAME_STATUSES
        ]
        slice_data["invariant_skeleton"] = _as_dict(
            handles.get("invariant_skeleton")
        )
    else:
        slice_data["candidate_menu"] = [
            _compact_candidate(item)
            for item in _as_list(proof_ir.get("candidate_menu"))[:max_items]
            if isinstance(item, dict)
        ]
        slice_data["phase_legality"] = _compact_phase_legality(
            _as_dict(_as_dict(proof_ir.get("phase")).get("legality")),
        )
    return slice_data


def _compact_liveness(liveness: dict) -> dict:
    keys = [
        "live_call_site_count",
        "frontier_call_site_count",
        "live_callable_lemma_count",
        "callable_now_lemma_count",
        "non_frontier_callable_lemma_count",
        "inline_all_taken",
    ]
    return {key: liveness.get(key) for key in keys if key in liveness}


def _compact_phase(phase: dict) -> dict:
    return {
        "prefer": [str(item) for item in _as_list(phase.get("prefer"))[:4]],
        "avoid": [str(item) for item in _as_list(phase.get("avoid"))[:4]],
        "resource_summary": _as_dict(phase.get("resource_summary")),
    }


def _compact_diagnostics(proof_ir: dict, *, max_items: int) -> list[dict]:
    return [
        {
            "code": str(item.get("code") or ""),
            "severity": str(item.get("severity") or ""),
            "message": str(item.get("message") or ""),
        }
        for item in _as_list(proof_ir.get("diagnostics"))[:max_items]
        if isinstance(item, dict)
    ]


def _compact_pr_path_plan(plan: dict) -> dict:
    recommended = _as_dict(plan.get("recommended_path"))
    return {
        "summary": _as_dict(plan.get("summary")),
        "recommended_path": {
            "relation": str(recommended.get("relation") or ""),
            "hop_count": int(recommended.get("hop_count") or 0),
            "lemmas": [
                str(item) for item in _as_list(recommended.get("lemmas"))[:5]
            ],
        } if recommended else {},
    }


def _compact_name_resolution(name_resolution: dict, *, max_items: int) -> dict:
    return {
        "summary": _as_dict(name_resolution.get("summary")),
        "lookup_actions": [
            str(action)
            for action in _as_list(name_resolution.get("lookup_actions"))[:max_items]
        ],
    }


def _compact_program_action_plan(
    plan: dict,
    *,
    name_resolution: dict | None = None,
) -> dict:
    return {
        "id": str(plan.get("id") or ""),
        "kind": str(plan.get("kind") or ""),
        "procedure_tail": str(plan.get("procedure_tail") or ""),
        "phase_order": [
            _compact_program_phase_action(action, name_resolution=name_resolution)
            for action in _as_list(plan.get("phase_order"))[:4]
            if isinstance(action, dict)
        ],
    }


def _compact_program_phase_action(
    action: dict,
    *,
    name_resolution: dict | None = None,
) -> dict:
    tactic = str(
        action.get("tactic_hint")
        or action.get("tactic_template")
        or ""
    )
    symbol = _call_symbol_from_tactic(tactic)
    status = _resolution_status(name_resolution, symbol)
    base = {
        "kind": str(action.get("kind") or ""),
        "tactic_family": str(action.get("tactic_family") or ""),
        "reason": str(action.get("reason") or ""),
    }
    if status in _UNRESOLVED_NAME_STATUSES and symbol:
        base.update({
            "tactic_shape": tactic,
            "symbol_hint": symbol,
            "resolution_status": status,
            "lookup_before_use": {
                "intent": "lookup_symbol",
                "payload": {"symbol": symbol},
            },
            "read": (
                "Route landmark only; submit this lookup intent through "
                "submit_proof_intent before turning the symbol into a "
                "call/apply/rewrite tactic."
            ),
        })
    elif tactic:
        base["tactic_hint"] = tactic
    return base


def _compact_callable_lemma(
    handle: dict,
    *,
    name_resolution: dict | None = None,
) -> dict:
    lemma = str(handle.get("lemma") or "")
    status = _resolution_status(name_resolution, lemma)
    item = {
        "lemma": str(handle.get("lemma") or ""),
        "procedure": str(handle.get("procedure") or ""),
        "frontier_status": str(handle.get("frontier_status") or ""),
        "callable_now": bool(handle.get("callable_now")),
        "repair_hint": str(handle.get("repair_hint") or ""),
    }
    if status:
        item["resolution_status"] = status
    if status in _UNRESOLVED_NAME_STATUSES and lemma:
        item["lookup_before_use"] = {
            "intent": "lookup_symbol",
            "payload": {"symbol": lemma},
        }
        item["read"] = (
            "Unresolved lemma hint; do not call it until a lookup intent "
            "submitted through submit_proof_intent confirms the declaration "
            "in the current scope."
        )
    return item


_UNRESOLVED_NAME_STATUSES = frozenset({
    "needs_where_lookup",
    "in_scope_name_without_signature",
    "source_scope_check_required",
    "source_local_scope_check_required",
})


def _resolution_status(name_resolution: dict | None, symbol: str) -> str:
    if not symbol:
        return ""
    for item in _as_list(_as_dict(name_resolution).get("items")):
        if not isinstance(item, dict):
            continue
        if str(item.get("name") or "") == symbol:
            return str(item.get("resolution_status") or "")
    return ""


def _call_symbol_from_tactic(tactic: str) -> str:
    match = re.search(
        r"\b(?:call|ecall)\s+\(?\s*([A-Za-z_][A-Za-z0-9_.'`]*"
        r"(?:\.[A-Za-z_][A-Za-z0-9_.'`]*)*)",
        tactic,
    )
    if not match:
        return ""
    return match.group(1).strip().rstrip(".")


def _compact_candidate(candidate: dict) -> dict:
    return {
        "id": str(candidate.get("id") or ""),
        "tactic_family": str(candidate.get("tactic_family") or ""),
        "tactic": str(candidate.get("tactic") or ""),
        "action_type": str(candidate.get("action_type") or ""),
        "cost": str(candidate.get("cost") or ""),
        "why": str(candidate.get("why") or ""),
    }


def _compact_phase_legality(legality: dict) -> dict:
    out: dict[str, dict[str, str]] = {}
    for name, rule in legality.items():
        if name not in {
            "rewrite",
            "pr_bridge",
            "call_named_equiv",
            "targeted_inline",
            "inline_all",
            "procedure_transform",
            "ambient_close",
        }:
            continue
        item = _as_dict(rule)
        out[str(name)] = {
            "status": str(item.get("status") or ""),
            "reason": str(item.get("reason") or ""),
        }
    return out


def _as_dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list:
    return value if isinstance(value, list) else []


__all__ = [
    "DEFAULT_STRUCTURAL_UNDO_SPAWN_DELAY_SECONDS",
    "DEFAULT_UNDO_REPAIR_PROTECTION_SECONDS",
    "DEFAULT_TREE_INITIAL_PROVERS",
    "TREE_MAX_ACTIVE_NODES",
    "cap_tree_max_concurrent",
    "layer_move_action_key",
    "candidate_layer_move_actions",
    "effective_progress_count",
    "failed_experiment_memory_key",
    "proof_ir_frontier_key",
    "infer_abstraction_layer",
    "infer_abstraction_layer_from_proof_ir",
    "proof_ir_slice_for_layer_move",
    "build_layer_move_action",
    "layer_move_order",
    "tree_spawn_branch_key",
    "tree_spawn_limit_for_branch_key",
    "undo_repair_mode",
]
