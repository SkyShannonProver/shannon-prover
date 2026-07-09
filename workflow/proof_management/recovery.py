"""Shared recovery-evidence vocabulary and helpers."""
from __future__ import annotations

from typing import Any

from workflow.proof_management.common import (
    _dict,
    _drop_empty_precheck as _drop_empty,
    _list,
)


RECOVERY_CLASS_BY_ROUTE_SIGNAL = {
    "frame_boundary_gap": "boundary_repair_evidence",
    "lost_call_abstraction_boundary": "call_frontier_recovery_evidence",
    "possible_boundary_gap": "boundary_repair_evidence",
    "probability_budget_route_risk": "boundary_repair_evidence",
    "seq_boundary_restored": "seq_midpoint_repair_evidence",
    "seq_cut_mismatch": "seq_midpoint_repair_evidence",
    "local_membership_decomposition_available": "local_pure_surgery_available",
    "pure_tail_alignment_gap": "local_pure_surgery_available",
    "frontier_placement": "residual_program_surgery_available",
    "local_tool_not_ready": "residual_program_surgery_available",
    "prhl_surgery_sequence_needed": "residual_program_surgery_available",
}

CHECKPOINT_POLICY_BY_RECOVERY_CLASS = {
    "boundary_repair_evidence": "boundary_checkpoint_visible",
    "call_frontier_recovery_evidence": "call_site_boundary_visible",
    "seq_midpoint_repair_evidence": "seq_local_checkpoint_visible",
    "local_pure_surgery_available": "current_state_local_work_visible",
    "residual_program_surgery_available": "current_state_residual_work_visible",
    "ambiguous_recovery": "neutral_recovery_options_visible",
}

BOUNDARY_RECOVERY_CLASSES = {
    "boundary_repair_evidence",
    "call_frontier_recovery_evidence",
    "seq_midpoint_repair_evidence",
}

LOCAL_WORK_RECOVERY_CLASSES = {
    "local_pure_surgery_available",
    "residual_program_surgery_available",
}


def recovery_class_for_route_health_item(item: dict[str, Any]) -> str:
    explicit = str(item.get("recovery_class") or "")
    if explicit:
        return explicit
    signal = str(item.get("signal") or "")
    return RECOVERY_CLASS_BY_ROUTE_SIGNAL.get(signal, "")


def checkpoint_policy_for_recovery_class(recovery_class: str) -> str:
    return CHECKPOINT_POLICY_BY_RECOVERY_CLASS.get(
        recovery_class,
        CHECKPOINT_POLICY_BY_RECOVERY_CLASS["ambiguous_recovery"],
    )


def annotate_route_health_items(
    items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    annotated: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        out = dict(item)
        recovery_class = recovery_class_for_route_health_item(out)
        if recovery_class:
            out["recovery_class"] = recovery_class
            out["checkpoint_policy"] = checkpoint_policy_for_recovery_class(
                recovery_class
            )
        if recovery_class not in BOUNDARY_RECOVERY_CLASSES:
            recommended = _dict(out.get("recommended_next"))
            primary = _dict(out.get("primary_next_action"))
            if str(recommended.get("intent") or "") == "undo_to_checkpoint":
                out.pop("recommended_next", None)
            if str(primary.get("intent") or "") == "undo_to_checkpoint":
                out.pop("primary_next_action", None)
            checkpoint = _dict(out.get("repair_checkpoint"))
            if checkpoint:
                refs = _list(out.get("related_checkpoints"))
                refs.append(checkpoint_recovery_ref(checkpoint))
                out["related_checkpoints"] = [
                    ref for ref in refs if isinstance(ref, dict) and ref
                ][:4]
                out.pop("repair_checkpoint", None)
        annotated.append(_drop_empty(out))
    return annotated


def checkpoint_recovery_ref(checkpoint: dict[str, Any]) -> dict[str, Any]:
    if not checkpoint:
        return {}
    return _drop_empty({
        "checkpoint_id": checkpoint.get("checkpoint_id"),
        "semantic_id": checkpoint.get("semantic_id"),
        "semantic_ids": checkpoint.get("semantic_ids"),
        "label": checkpoint.get("label"),
        "tactic_index": checkpoint.get("tactic_index"),
        "committed_step_index": checkpoint.get("committed_step_index")
        or checkpoint.get("tactic_index"),
        "undo_scope": checkpoint.get("undo_scope"),
        "restored_proof_layer": checkpoint.get("restored_proof_layer"),
        "restored_affordances": checkpoint.get("restored_affordances"),
        "why_checkpoint": checkpoint.get("why_checkpoint")
        or checkpoint.get("why_here"),
    })

