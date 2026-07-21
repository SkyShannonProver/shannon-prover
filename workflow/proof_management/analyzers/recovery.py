"""Recovery diagnosis analyzer."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from workflow.proof_management.analyzers.common import (
    _dict,
    _drop_empty_precheck as _drop_empty,
    _list,
    _string_list,
)
from workflow.proof_management.frame_facts import pre_post_global_frame_gap
from workflow.proof_management.node_state import ProofNodeState
from workflow.proof_management.recovery import (
    BOUNDARY_RECOVERY_CLASSES,
    LOCAL_WORK_RECOVERY_CLASSES,
    checkpoint_policy_for_recovery_class,
    checkpoint_recovery_ref,
    recovery_class_for_route_health_item,
)


@dataclass(frozen=True)
class RecoveryDiagnosisResult:
    surface: dict[str, Any] = field(default_factory=dict)
    view_overrides: dict[str, Any] = field(default_factory=dict)


class RecoveryDiagnosisAnalyzer:
    """Builds recovery diagnosis evidence and related route-health cleanup."""

    def analyze(
        self,
        *,
        state: ProofNodeState,
        view: dict[str, Any],
        route_health: list[dict[str, Any]],
    ) -> RecoveryDiagnosisResult:
        del state
        surface = recovery_diagnosis_surface(view, route_health=route_health)
        if not surface:
            return RecoveryDiagnosisResult()
        consistent = workspace_view_with_recovery_consistent_route_health(
            view,
            surface,
        )
        overrides: dict[str, Any] = {}
        if consistent.get("candidate_moves") != view.get("candidate_moves"):
            candidate_moves = consistent.get("candidate_moves")
            if isinstance(candidate_moves, dict):
                overrides["candidate_moves"] = dict(candidate_moves)
            else:
                overrides["candidate_moves"] = candidate_moves
        return RecoveryDiagnosisResult(surface=surface, view_overrides=overrides)


def workspace_view_with_recovery_consistent_route_health(
    workspace_view: dict[str, Any],
    recovery: dict[str, Any],
) -> dict[str, Any]:
    raw = dict(_dict(workspace_view))
    recovery_class = str(_dict(recovery).get("recovery_class") or "")
    if recovery_class not in LOCAL_WORK_RECOVERY_CLASSES:
        return raw
    candidate_moves = dict(_dict(raw.get("candidate_moves")))
    route_health = _list(candidate_moves.get("route_health"))
    if not route_health:
        return raw
    consistent: list[dict[str, Any]] = []
    changed = False
    for item in route_health:
        if not isinstance(item, dict):
            continue
        out = dict(item)
        for action_key in ("recommended_next", "primary_next_action"):
            action = _dict(out.get(action_key))
            if str(action.get("intent") or "") == "undo_to_checkpoint":
                out.pop(action_key, None)
                changed = True
        checkpoint = _dict(out.get("repair_checkpoint"))
        if checkpoint:
            refs = [
                ref
                for ref in _list(out.get("related_checkpoints"))
                if isinstance(ref, dict) and ref
            ]
            ref = checkpoint_recovery_ref(checkpoint)
            if ref and ref not in refs:
                refs.insert(0, ref)
            out["related_checkpoints"] = refs[:4]
            out.pop("repair_checkpoint", None)
            changed = True
        consistent.append(_drop_empty(out))
    if not changed:
        return raw
    candidate_moves["route_health"] = consistent
    raw["candidate_moves"] = _drop_empty(candidate_moves)
    return raw


def recovery_diagnosis_surface(
    view: dict[str, Any],
    *,
    route_health: list[dict[str, Any]],
) -> dict[str, Any]:
    primary = _primary_recovery_health_item(route_health)
    recovery_class = recovery_class_for_route_health_item(primary) if primary else ""
    confidence = str(primary.get("confidence") or "") if primary else ""
    evidence = _string_list(primary.get("evidence")) if primary else []
    signal = str(primary.get("signal") or "")
    frame_gap = pre_post_global_frame_gap(view)
    if frame_gap and recovery_class in {
        "",
        "call_frontier_recovery_evidence",
        "local_pure_surgery_available",
        "residual_program_surgery_available",
    }:
        recovery_class = "boundary_repair_evidence"
        confidence = "high"
        evidence = [
            "current pRHL post requires global frame equality absent from the displayed precondition",
            "missing frame fact(s): " + ", ".join(f"={{{term}}}" for term in frame_gap),
        ]
    if _pure_tail_local_work_visible(view) and (
        recovery_class in BOUNDARY_RECOVERY_CLASSES
        or recovery_class == "residual_program_surgery_available"
    ) and signal != "seq_boundary_restored" and not frame_gap:
        recovery_class = "local_pure_surgery_available"
        confidence = confidence or "medium"
        evidence = [
            "pure_tail_surface exposes current-state local proof work",
            (
                "structural route-health signal remains available as evidence"
                + (f": {signal}" if signal else "")
            ),
            "no frame_obligation_ledger boundary drop is visible in this view",
        ]
    if not recovery_class:
        if _dict(view.get("frame_obligation_ledger")).get("possibly_dropped"):
            recovery_class = "boundary_repair_evidence"
            confidence = "medium"
            evidence = [
                "frame_obligation_ledger reports a frame fact visible in the current local goal evidence",
                "a committed structural boundary does not carry the same frame fact",
            ]
        elif _dict(view.get("pure_tail_surface")):
            recovery_class = "local_pure_surgery_available"
            confidence = "medium"
            evidence = [
                "pure_tail_surface is visible for the current goal",
                "current proof state has no program-frontier work before the logical residual",
            ]
        else:
            return {}
    related_checkpoints = _recovery_related_checkpoints(
        view,
        primary=primary,
        recovery_class=recovery_class,
    )
    return _drop_empty({
        "kind": "recovery_diagnosis_surface",
        "recovery_class": recovery_class,
        "confidence": confidence or "medium",
        "checkpoint_policy": checkpoint_policy_for_recovery_class(recovery_class),
        "evidence": evidence[:6],
        "available_local_work": _recovery_available_local_work(
            view,
            primary=primary,
            recovery_class=recovery_class,
        ),
        "related_checkpoints": related_checkpoints[:5],
        "related_surfaces": _recovery_related_surfaces(view, primary),
        "limitations": _recovery_diagnosis_limitations(recovery_class),
    })


def _pure_tail_local_work_visible(view: dict[str, Any]) -> bool:
    if _dict(view.get("frame_obligation_ledger")).get("possibly_dropped"):
        return False
    if pre_post_global_frame_gap(view):
        return False
    pure_tail = _dict(view.get("pure_tail_surface"))
    if not pure_tail:
        return False
    membership = _dict(pure_tail.get("membership_decomposition_surface"))
    if _string_list(membership.get("source_shapes")):
        return True
    witnesses = _dict(pure_tail.get("existential_witness_surface"))
    if _list(witnesses.get("candidate_sources")):
        return True
    lookup = _dict(pure_tail.get("map_update_lookup_surface"))
    if _string_list(lookup.get("key_cases")):
        return True
    return False


def _primary_recovery_health_item(
    route_health: list[dict[str, Any]],
) -> dict[str, Any]:
    ranked: list[tuple[int, int, dict[str, Any]]] = []
    priority = {
        "local_pure_surgery_available": 0,
        "residual_program_surgery_available": 1,
        "call_frontier_recovery_evidence": 2,
        "seq_midpoint_repair_evidence": 3,
        "boundary_repair_evidence": 4,
        "ambiguous_recovery": 9,
    }
    signal_priority = {
        "frame_boundary_gap": -1,
    }
    for index, item in enumerate(route_health):
        if not isinstance(item, dict):
            continue
        recovery_class = recovery_class_for_route_health_item(item)
        if not recovery_class:
            continue
        signal = str(item.get("signal") or "")
        ranked.append((
            signal_priority.get(signal, priority.get(recovery_class, 9)),
            index,
            item,
        ))
    if not ranked:
        return {}
    ranked.sort(key=lambda entry: (entry[0], entry[1]))
    return dict(ranked[0][2])


def _recovery_related_surfaces(
    view: dict[str, Any],
    primary: dict[str, Any],
) -> list[str]:
    surfaces: list[str] = []
    related = str(primary.get("related_surface") or "")
    if related:
        surfaces.append(related)
    for key in (
        "call_site_surface",
        "seq_cut_surface",
        "pure_tail_surface",
        "frame_obligation_ledger",
        "structural_checkpoints",
        "route_replay_memory",
    ):
        if view.get(key) not in ({}, [], None, "") and key not in surfaces:
            surfaces.append(key)
    for key in _string_list(primary.get("companion_surfaces")):
        if key and key not in surfaces:
            surfaces.append(key)
    return surfaces[:6]


def _recovery_related_checkpoints(
    view: dict[str, Any],
    *,
    primary: dict[str, Any],
    recovery_class: str,
) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []

    def add(checkpoint: dict[str, Any]) -> None:
        ref = checkpoint_recovery_ref(checkpoint)
        if not ref:
            return
        ident = (
            str(ref.get("checkpoint_id") or ""),
            str(ref.get("semantic_id") or ""),
            str(ref.get("committed_step_index") or ref.get("tactic_index") or ""),
        )
        for existing in refs:
            existing_ident = (
                str(existing.get("checkpoint_id") or ""),
                str(existing.get("semantic_id") or ""),
                str(existing.get("committed_step_index") or existing.get("tactic_index") or ""),
            )
            if ident == existing_ident:
                return
        refs.append(ref)

    checkpoint = _dict(primary.get("repair_checkpoint"))
    if checkpoint:
        add(checkpoint)
    for checkpoint in _list(primary.get("related_checkpoints")):
        if isinstance(checkpoint, dict):
            add(checkpoint)
    pure_tail = _dict(view.get("pure_tail_surface"))
    if recovery_class == "local_pure_surgery_available":
        for gap in _list(pure_tail.get("gap_analysis")):
            if not isinstance(gap, dict):
                continue
            for checkpoint in _list(gap.get("reversible_to")):
                if isinstance(checkpoint, dict):
                    add(checkpoint)
    ledger = _dict(view.get("frame_obligation_ledger"))
    if recovery_class in {
        "boundary_repair_evidence",
        "seq_midpoint_repair_evidence",
    }:
        for dropped in _list(ledger.get("possibly_dropped")):
            if isinstance(dropped, dict):
                add(_dict(dropped.get("related_checkpoint")))
    checkpoints = _list(_dict(view.get("structural_checkpoints")).get("items"))
    local_scopes = {
        "local_pure_surgery_available": {"branch_local", "seq_local"},
        "residual_program_surgery_available": {"branch_local", "call_obligation_local"},
        "call_frontier_recovery_evidence": {"call_site_boundary", "call_local"},
        "seq_midpoint_repair_evidence": {"seq_local", "branch_local"},
        "boundary_repair_evidence": {
            "seq_local",
            "call_local",
            "structural_boundary",
            "call_site_boundary",
        },
    }.get(recovery_class, set())
    for checkpoint in checkpoints:
        if not isinstance(checkpoint, dict):
            continue
        if local_scopes and str(checkpoint.get("undo_scope") or "") not in local_scopes:
            continue
        add(checkpoint)
        if len(refs) >= 5:
            break
    return refs


def _recovery_available_local_work(
    view: dict[str, Any],
    *,
    primary: dict[str, Any],
    recovery_class: str,
) -> list[dict[str, Any]]:
    work: list[dict[str, Any]] = []
    pure_tail = _dict(view.get("pure_tail_surface"))
    if pure_tail:
        families = [
            str(item.get("family") or "")
            for item in _list(pure_tail.get("obligation_families"))
            if isinstance(item, dict) and item.get("family")
        ]
        if families:
            work.append({
                "kind": "pure_tail_obligation_families",
                "items": families[:8],
            })
        membership = _dict(pure_tail.get("membership_decomposition_surface"))
        shapes = _string_list(membership.get("source_shapes"))
        if shapes:
            work.append({
                "kind": "membership_decomposition_sources",
                "items": shapes[:6],
            })
        witnesses = _dict(pure_tail.get("existential_witness_surface"))
        sources = [
            str(item.get("source") or "")
            for item in _list(witnesses.get("candidate_sources"))
            if isinstance(item, dict) and item.get("source")
        ]
        if sources:
            work.append({
                "kind": "existential_witness_sources",
                "items": sources[:6],
            })
        lookup = _dict(pure_tail.get("map_update_lookup_surface"))
        cases = _string_list(lookup.get("key_cases"))
        if cases:
            work.append({
                "kind": "map_update_lookup_cases",
                "items": cases[:6],
            })
    signal = str(primary.get("signal") or "")
    if recovery_class == "residual_program_surgery_available":
        work.append(_drop_empty({
            "kind": "residual_program_surgery",
            "source_signal": signal,
            "evidence": _string_list(primary.get("evidence"))[:4],
        }))
    if recovery_class in BOUNDARY_RECOVERY_CLASSES and not work:
        work.append({
            "kind": "local_work_status",
            "items": ["current evidence points at a structural recovery boundary"],
        })
    return [item for item in work if item]


def _recovery_diagnosis_limitations(recovery_class: str) -> list[str]:
    if recovery_class == "boundary_repair_evidence":
        return [
            "does not infer a replacement invariant, cut formula, or postcondition",
            "uses only current residual evidence and recent local repair failures",
        ]
    if recovery_class == "call_frontier_recovery_evidence":
        return [
            "does not select a named call handle or call tactic form",
            "reports only that the current state has no live call site",
        ]
    if recovery_class == "seq_midpoint_repair_evidence":
        return [
            "does not synthesize a replacement seq midpoint",
            "reports obligation shape and local recovery boundaries only",
        ]
    if recovery_class == "local_pure_surgery_available":
        return [
            "does not select a destructor, witness, rewrite, or SMT lemma",
            "reported checkpoints are recovery references, not a default route",
        ]
    if recovery_class == "residual_program_surgery_available":
        return [
            "does not prescribe a conseq, sim, wp, or skip script",
            "reports residual program evidence before pure-tail obligations",
        ]
    return ["classification is conservative and may need additional inspected evidence"]
