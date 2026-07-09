"""Pure leaf utilities shared by every ec_proof_ir pass.

Extracted from ec_proof_ir.py (the 16 cross-pass leaf helpers + the one
constant they need) so the per-pass carving (e.g. ec_proof_action_surface)
can depend on them WITHOUT a circular import back into ec_proof_ir. These are
self-contained (no back-edges into pass logic). ec_proof_ir re-imports them, so
they remain importable from core.easycrypt.analysis.ec_proof_ir unchanged.
"""
from __future__ import annotations

import re
from typing import Any

from core.easycrypt.analysis.ec_utils import (
    as_dict as _dict,
    as_list as _list,
    candidate_names as _candidate_names,
    dedupe_strings as _dedupe_strings,
    lemma_leaf as _lemma_leaf,
    legacy_shape_tactic_templates as _legacy_shape_tactic_templates,
)

_CALL_NAME_LOOKUP_REQUIRED_STATUSES = {
    "needs_where_lookup",
    "in_scope_name_without_signature",
    "source_scope_check_required",
    "source_local_scope_check_required",
}


def _extract_tactic_from_action(action: str) -> str:
    text = action.strip()
    match = re.search(r"-chain\s+-c\s+(['\"])(.*?)\1", text)
    if match:
        return match.group(2).strip()
    return text


def _legality(status: str, reason: str) -> dict[str, Any]:
    return {"status": status, "reason": reason}


def _call_name_needs_lookup(
    resolved: dict[str, Any],
    *,
    resolution_status: str,
    exact_signature_known: bool,
    requires_instantiation: bool,
    instantiated_templates: list[Any],
) -> bool:
    if not resolved:
        return True
    if resolution_status in _CALL_NAME_LOOKUP_REQUIRED_STATUSES:
        return True
    if not exact_signature_known:
        return True
    if requires_instantiation and not instantiated_templates:
        return True
    return False


def _call_handle_candidate_kind(
    handle: dict[str, Any],
    *,
    resolved: dict[str, Any],
    resolution_status: str,
    exact_signature_known: bool,
    requires_instantiation: bool,
    instantiated_templates: list[Any],
) -> str:
    """Classify named-call handles by current-view executability.

    Procedure/name correlation is useful context, but it is not enough to make
    `call L.` a good current tactic.  A direct call candidate needs both a
    live last-call frontier and a resolved EasyCrypt declaration/signature.
    Other handles are route landmarks or future handles.
    """
    role = str(handle.get("handle_role") or "")
    callable_now = bool(handle.get("callable_now"))
    requires_cut = bool(handle.get("requires_cut_to_frontier"))
    needs_lookup = _call_name_needs_lookup(
        resolved,
        resolution_status=resolution_status,
        exact_signature_known=exact_signature_known,
        requires_instantiation=requires_instantiation,
        instantiated_templates=instantiated_templates,
    )
    if role == "oracle_obligation_handle":
        return "future_oracle_subgoal_handle"
    if needs_lookup:
        return "source_lookup_landmark"
    if callable_now and not requires_cut:
        return "direct_current_call"
    if requires_cut or not callable_now:
        return "needs_frontier_exposure"
    return "source_lookup_landmark"


def _program_edit_script_action(program_ir: dict[str, Any]) -> dict[str, Any]:
    diff = _dict(_dict(program_ir).get("program_diff"))
    if not diff:
        return {}
    preferred_kinds = {
        "expose_asymmetric_prefix",
        "expose_call_pair_frontier",
        "expose_last_call_frontier",
        "open_one_wrapper",
    }
    plans: list[dict[str, Any]] = []
    next_plan = _dict(diff.get("next_action_plan"))
    if next_plan:
        plans.append(next_plan)
    seen_plan_ids = {str(next_plan.get("id") or "")} if next_plan else set()
    for plan in _list(diff.get("action_plans")):
        if not isinstance(plan, dict):
            continue
        plan_id = str(plan.get("id") or "")
        if plan_id and plan_id in seen_plan_ids:
            continue
        plans.append(plan)
        if plan_id:
            seen_plan_ids.add(plan_id)
    for plan in plans:
        found = _action_from_program_plan(plan, preferred_kinds)
        if found:
            return found
    edit_v2 = _dict(diff.get("edit_script_v2"))
    next_slice = _dict(edit_v2.get("next_slice"))
    expected = _dict(next_slice.get("expected_next"))
    tactic = str(expected.get("tactic") or "").strip()
    kind = str(expected.get("kind") or "")
    if tactic and kind in preferred_kinds:
        return {
            "kind": kind,
            "tactic_hint": tactic,
            "reason": str(next_slice.get("why") or ""),
            "plan_id": str(next_slice.get("id") or ""),
            "plan_kind": str(next_slice.get("kind") or ""),
            "rank": int(next_slice.get("rank") or 9999),
            "left_statement_count": int(next_slice.get("left_statement_count") or 0),
            "right_statement_count": int(next_slice.get("right_statement_count") or 0),
            "target_call_site_ids": list(next_slice.get("target_call_site_ids") or []),
        }
    return {}


def _action_from_program_plan(
    plan: dict[str, Any],
    preferred_kinds: set[str],
) -> dict[str, Any]:
    plan = _dict(plan)
    if not plan:
        return {}
    fallback: dict[str, Any] = {}
    for action in _list(plan.get("phase_order")):
        if not isinstance(action, dict):
            continue
        tactic = str(action.get("tactic_hint") or action.get("tactic") or "").strip()
        if not tactic:
            continue
        family = str(action.get("tactic_family") or "")
        if family not in {"procedure_transform", "targeted_inline"}:
            continue
        kind = str(action.get("kind") or "")
        enriched = {
            **action,
            "tactic_hint": tactic,
            "plan_id": str(plan.get("id") or ""),
            "plan_kind": str(plan.get("kind") or ""),
            "rank": int(plan.get("rank") or 9999),
            "target_call_site_ids": list(plan.get("target_call_site_ids") or []),
            "why": str(plan.get("why") or ""),
        }
        if kind in preferred_kinds:
            return enriched
        if not fallback and kind != "weaken_or_normalize_post":
            fallback = enriched
    return fallback


def _instantiation_missing_slot_labels(
    binding: dict[str, Any],
    resolved: dict[str, Any],
) -> list[str]:
    labels: list[str] = []
    for slot_binding in _list(binding.get("slots")):
        if not isinstance(slot_binding, dict):
            continue
        slot = _dict(slot_binding.get("slot"))
        selected = _dict(slot_binding.get("selected_candidate"))
        kind = str(slot.get("kind") or "arg")
        name = str(slot.get("name") or slot.get("placeholder") or "")
        confidence = str(selected.get("confidence") or "")
        value = str(selected.get("value") or "")
        if kind == "type_arg" and value:
            continue
        if not value or value == "_" or confidence in {"", "low"}:
            labels.append(_slot_role_label(kind, name))
    if labels:
        return _dedupe_strings(labels)
    if binding and _list(binding.get("instantiated_templates")):
        return []
    for slot in _list(resolved.get("parameter_slots")):
        if not isinstance(slot, dict):
            continue
        kind = str(slot.get("kind") or "arg")
        if kind == "type_arg":
            continue
        labels.append(_slot_role_label(kind, str(slot.get("name") or "")))
    return _dedupe_strings(labels)


def _slot_role_label(kind: str, name: str) -> str:
    role = {
        "module_arg": "module arg",
        "memory_arg": "memory arg",
        "value_arg": "value arg",
        "proof_arg": "proof arg",
        "implicit_arg": "implicit arg",
        "type_arg": "type arg",
    }.get(str(kind or ""), "arg")
    return f"{role} `{name}`" if name else role


def _candidate_lemma_name(candidate: dict[str, Any]) -> str:
    action = str(candidate.get("action") or candidate.get("tactic") or "")
    tactic = _extract_tactic_from_action(action).strip()
    lemma_pat = r"([A-Za-z_][\w']*(?:\.[A-Za-z_][\w']*)*)"
    for pattern in (
        rf"^exlim\b.*;\s*e?call\s+\(\s*{lemma_pat}\b",
        rf"^e?call\s+\(\s*{lemma_pat}\b",
        rf"^e?call\s+{lemma_pat}\s*\.?$",
        rf"^byequiv\s+\(\s*{lemma_pat}\b",
        rf"^rewrite\s+-?\(\s*{lemma_pat}\b",
        rf"^rewrite\s+-?{lemma_pat}\s*\.?$",
        rf"^(?:apply|exact)\s+\(\s*{lemma_pat}\b",
        rf"^(?:apply|exact)\s+-?{lemma_pat}\s*\.?$",
        rf"^-sig\s+{lemma_pat}\s*$",
        rf"^-where\s+{lemma_pat}\s*$",
        rf"^have\s*:=\s*{lemma_pat}\b",
        rf"^have\s*:=\s*{lemma_pat}\s*\.?$",
    ):
        match = re.match(pattern, tactic)
        if match:
            name = match.group(1)
            return "" if _is_placeholder_lemma_name(name) else name
    return ""


def _is_placeholder_lemma_name(name: str) -> bool:
    return str(name or "") in {"_", "lemma_name", "Inv"}


def _compact_pr_elaboration(item: dict[str, Any]) -> dict[str, Any]:
    if not item:
        return {}
    return {
        "status": str(item.get("status") or ""),
        "lemma": str(item.get("lemma") or ""),
        "endpoint_argument_separation": [
            {
                "value_slot": str(sep.get("value_slot") or ""),
                "selected_value": str(sep.get("selected_value") or ""),
                "lemma_endpoint_template": str(
                    sep.get("lemma_endpoint_template") or ""
                ),
                "concrete_endpoint": str(sep.get("concrete_endpoint") or ""),
                "reason": str(sep.get("reason") or ""),
            }
            for sep in _list(item.get("endpoint_argument_separation"))[:4]
            if isinstance(sep, dict)
        ],
        "endpoint_matches": [
            {
                "lemma_endpoint": str(match.get("lemma_endpoint") or ""),
                "current_endpoint": str(match.get("current_endpoint") or ""),
            }
            for match in _list(item.get("endpoint_matches"))[:4]
            if isinstance(match, dict)
        ],
        "diagnostics": [
            {
                "code": str(diag.get("code") or ""),
                "message": str(diag.get("message") or ""),
                "avoid": str(diag.get("avoid") or ""),
            }
            for diag in _list(item.get("diagnostics"))[:4]
            if isinstance(diag, dict)
        ],
        "slots": [
            {
                "name": str(_dict(slot.get("slot")).get("name") or ""),
                "kind": str(_dict(slot.get("slot")).get("kind") or ""),
                "selected_value": str(slot.get("selected_value") or ""),
                "role": str(slot.get("role") or ""),
                "belongs_to": str(slot.get("belongs_to") or ""),
                "canonical_endpoint": str(slot.get("canonical_endpoint") or ""),
            }
            for slot in _list(item.get("slots"))[:8]
            if isinstance(slot, dict)
        ],
    }
