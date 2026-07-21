"""PASS 3 — resource liveness + call-site routing (§3.3): over the built
handles, compute which resources are live/at the frontier and the per-call-site
route surface (the PASS2<->PASS3 writeback seam already isolated in
_pass3_liveness_and_route).

Carved out of ec_proof_ir.py (the funcs reachable ONLY from the liveness
entries). Imports only what these funcs use and NOTHING from ec_proof_ir, so
there is no cycle; ec_proof_ir re-exports this module's own defs so
build_proof_ir + consumers see them at the same path unchanged.
"""
from __future__ import annotations

import re
from typing import Any

# Pure leaf utilities live in ec_proof_ir_util now (carve step: break the
# import cycle for per-pass modules); the leaves this module's passes use are
# imported below.
from core.easycrypt.analysis.ec_proof_ir_util import (
    _instantiation_missing_slot_labels,
    _dict,
    _list,
    _candidate_lemma_name,
    _compact_pr_elaboration,
    _extract_tactic_from_action,
    _legality,
    _lemma_leaf,
)
from core.easycrypt.analysis.ec_utils import (
    dedupe_dicts as _dedupe_dicts,
    drop_empty_recursive as _drop_empty,
)

from core.easycrypt.analysis.ec_instantiation_binding import (
    binding_for_name,
)
from core.easycrypt.analysis.ec_name_resolution import (
    resolution_for_name,
)


_PLACEHOLDER_HANDLE_SYMBOLS = frozenset(
    {"lemma", "equiv", "Inv", "_", "axiom", "hoare", "phoare"}
)


def _pass3_liveness_and_route(handles, *, call_sites, destructive_moves,
                              program_ir, layer):
    """PASS 3 (§3.3 resource liveness / frontier): the one bidirectional seam.

    ``_handle_liveness`` READS the handles built in PASS 2; the resulting
    ``liveness`` then feeds ``_call_site_route_surface``, whose route is WRITTEN
    BACK into ``handles['call_site_route']``. This "liveness both consumes and
    produces handles" coupling is the single dependency that crosses the PASS 2 /
    PASS 3 boundary — isolated here (rather than inline in build_proof_ir) so a
    future carve of PASS 3 into its own module moves exactly this function and its
    callees, with the seam already explicit. Returns the liveness dict (consumed
    downstream by legality / phase / menu / diagnostics).
    """
    liveness = _handle_liveness(call_sites, handles, destructive_moves)
    handles["call_site_route"] = _call_site_route_surface(
        program_ir=program_ir,
        handles=handles,
        layer=layer,
        liveness=liveness,
    )
    return liveness


def _handle_liveness(
    call_sites: list[dict[str, Any]],
    handles: dict[str, Any],
    destructive_moves: list[dict[str, Any]],
) -> dict[str, Any]:
    callable_lemmas = _list(handles.get("callable_lemmas"))
    inline_all_taken = any(m.get("kind") == "inline_all" for m in destructive_moves)
    frontier_calls = [
        site for site in call_sites
        if isinstance(site, dict) and site.get("is_frontier_call")
    ]
    callable_now = [
        handle for handle in callable_lemmas
        if (
            isinstance(handle, dict)
            and handle.get("callable_now")
            and str(handle.get("call_candidate_kind") or "")
            == "direct_current_call"
        )
    ]
    requires_cut = [
        handle for handle in callable_lemmas
        if isinstance(handle, dict) and handle.get("requires_cut_to_frontier")
    ]
    oracle_obligations = [
        handle for handle in callable_lemmas
        if isinstance(handle, dict)
        and str(handle.get("handle_role") or "") == "oracle_obligation_handle"
    ]
    killed_by_inline_all = []
    for site in call_sites:
        proc = str(site.get("procedure") or "")
        linked = [
            str(handle.get("lemma") or "")
            for handle in callable_lemmas
            if isinstance(handle, dict)
            and (
                not str(handle.get("procedure") or "")
                or str(handle.get("procedure") or "") == proc
            )
        ]
        killed_by_inline_all.append({
            "resource": site.get("call_site_id") or site.get("id"),
            "procedure": proc,
            "is_frontier_call": bool(site.get("is_frontier_call")),
            "requires_cut_to_frontier": bool(site.get("requires_cut_to_frontier")),
            "linked_lemmas": [x for x in linked if x],
        })
    return {
        "live_call_site_count": len(call_sites),
        "frontier_call_site_count": len(frontier_calls),
        "live_callable_lemma_count": len(callable_lemmas),
        "callable_now_lemma_count": len(callable_now),
        "non_frontier_callable_lemma_count": len(requires_cut),
        "oracle_obligation_handle_count": len(oracle_obligations),
        "inline_all_taken": inline_all_taken,
        "inline_all_would_kill": killed_by_inline_all,
        "call_site_handles_consumed": bool(inline_all_taken and not call_sites),
    }


def _call_site_route_surface(
    *,
    program_ir: dict[str, Any],
    handles: dict[str, Any],
    layer: str,
    liveness: dict[str, Any],
) -> dict[str, Any]:
    if layer not in {"prhl_module", "procedure_entry", "call_site", "procedure_body"}:
        return {}
    call_sites = [
        _call_route_site(site)
        for site in _list(_dict(program_ir).get("call_sites"))
        if isinstance(site, dict)
    ]
    call_sites = [site for site in call_sites if site]
    named_handles = _call_route_named_handles(handles)
    if not call_sites and not named_handles:
        return {}
    direct = [
        handle for handle in named_handles
        if str(handle.get("call_candidate_kind") or "") == "direct_current_call"
    ]
    frontier_live = [
        handle for handle in named_handles
        if bool(handle.get("frontier_live"))
    ]
    tail_blocked = [
        handle for handle in named_handles
        if bool(handle.get("requires_cut_to_frontier"))
        or str(handle.get("call_candidate_kind") or "") == "needs_frontier_exposure"
    ]
    if direct:
        state = "callable_named_call"
    elif frontier_live:
        state = (
            "live_named_call_needs_binding"
            if any(_call_route_handle_needs_binding(handle) for handle in frontier_live)
            else "live_named_call_needs_resolution"
        )
    elif tail_blocked:
        state = "tail_blocked_named_call"
    elif call_sites and named_handles:
        state = "wrapper_layer_named_handle_not_live"
    elif call_sites:
        state = "wrapper_layer_no_named_handle"
    else:
        state = "named_handle_without_live_call_site"
    exposure = _call_route_exposure(handles, named_handles)
    templates = _call_route_templates(handles, named_handles)
    return _drop_empty({
        "id": f"call_site_route:{state}",
        "kind": "call_site_route",
        "state": state,
        "current_layer": layer,
        "live_call_sites": call_sites[:8],
        "named_handles": named_handles[:8],
        "callable_now": direct[:8],
        "frontier_live_named_handles": frontier_live[:8],
        "frontier_blockers": _call_route_frontier_blockers(
            program_ir=program_ir,
            named_handles=named_handles,
            live_call_sites=call_sites,
        ),
        "wrapper_depth": _call_route_wrapper_depth(call_sites, named_handles),
        "exposure": exposure,
        "named_call_templates": templates,
        "resource_summary": {
            "live_call_sites": int(liveness.get("live_call_site_count") or 0),
            "frontier_call_sites": int(
                liveness.get("frontier_call_site_count") or 0
            ),
            "live_callable_lemmas": int(
                liveness.get("live_callable_lemma_count") or 0
            ),
            "callable_now_lemmas": int(
                liveness.get("callable_now_lemma_count") or 0
            ),
            "non_frontier_callable_lemmas": int(
                liveness.get("non_frontier_callable_lemma_count") or 0
            ),
        },
        "evidence_style": "state_facts_only",
    })


def _call_route_site(site: dict[str, Any]) -> dict[str, Any]:
    return _drop_empty({
        "id": site.get("call_site_id") or site.get("id"),
        "side": site.get("side"),
        "position": site.get("order") or site.get("position") or site.get("pos"),
        "statement_path": site.get("statement_path") or site.get("pos_path"),
        "procedure": site.get("procedure"),
        "is_frontier_call": site.get("is_frontier_call"),
        "requires_cut_to_frontier": site.get("requires_cut_to_frontier"),
        "frontier_role": site.get("frontier_role"),
        "statement": _short_text(str(site.get("statement") or site.get("text") or ""), 180),
    })


def _call_route_named_handles(handles: dict[str, Any]) -> list[dict[str, Any]]:
    name_resolution = _dict(handles.get("name_resolution"))
    instantiation_bindings = _dict(handles.get("instantiation_bindings"))
    out: list[dict[str, Any]] = []
    for handle in _list(handles.get("callable_lemmas")):
        if not isinstance(handle, dict):
            continue
        lemma = str(handle.get("lemma") or "")
        if not lemma or lemma in _PLACEHOLDER_HANDLE_SYMBOLS:
            continue
        candidate_kind = str(handle.get("call_candidate_kind") or "")
        frontier_live = bool(handle.get("callable_now"))
        resolved = resolution_for_name(name_resolution, lemma)
        binding = binding_for_name(instantiation_bindings, lemma)
        exact_signature_known = bool(resolved.get("exact_signature_known"))
        requires_instantiation = exact_signature_known and bool(
            resolved.get("requires_instantiation")
        )
        missing_slots = _instantiation_missing_slot_labels(binding, resolved)
        item_callable = candidate_kind == "direct_current_call"
        # Reconcile frontier_status with the authoritative item callable_now: the
        # upstream status is derived from a different (broader) flag, so a
        # source-lookup landmark could carry `callable_now:false` AND
        # `frontier_status:"callable_now"` — a self-contradiction the agent (and
        # we) read as noise. Never report "callable_now" for a handle that is not.
        raw_status = str(handle.get("frontier_status") or "")
        frontier_status = (
            "callable_now" if item_callable
            else raw_status if (raw_status and raw_status != "callable_now")
            else (candidate_kind or "not_callable_at_frontier")
        )
        out.append(_drop_empty({
            "symbol": lemma,
            "source": handle.get("source"),
            "procedure": handle.get("procedure"),
            "procedures": handle.get("procedures"),
            "frontier_live": frontier_live,
            "callable_now": item_callable,
            "requires_cut_to_frontier": bool(handle.get("requires_cut_to_frontier")),
            "call_candidate_kind": candidate_kind,
            "frontier_status": frontier_status,
            "frontier_status_detail": handle.get("frontier_status_detail"),
            "live_call_site_ids": handle.get("live_call_site_ids"),
            "frontier_call_site_ids": handle.get("frontier_call_site_ids"),
            "matched_call_sites": handle.get("matched_call_sites"),
            "name_resolution_status": resolved.get("resolution_status"),
            "exact_signature_known": exact_signature_known,
            "requires_instantiation": requires_instantiation,
            "missing_slots": missing_slots,
            "instantiation_binding_status": (
                "has_call_elaboration"
                if _dict(binding.get("call_elaboration")).get("available") else
                "has_candidates"
                if _list(binding.get("instantiated_templates")) else
                "missing_candidates"
                if requires_instantiation else
                "not_required"
            ),
        }))
    return sorted(
        out,
        key=lambda item: (
            0 if item.get("callable_now") else 1,
            0 if item.get("requires_cut_to_frontier") else 1,
            str(item.get("symbol") or ""),
        ),
    )


def _call_route_handle_needs_binding(handle: dict[str, Any]) -> bool:
    return bool(handle.get("missing_slots")) or str(
        handle.get("instantiation_binding_status") or ""
    ) in {"missing_candidates", "has_call_elaboration", "has_candidates"}


def _call_route_frontier_blockers(
    *,
    program_ir: dict[str, Any],
    named_handles: list[dict[str, Any]],
    live_call_sites: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    frontier = _dict(_dict(program_ir).get("frontier"))
    blockers: list[dict[str, Any]] = []
    raw = frontier.get("frontier_blockers")
    if isinstance(raw, dict):
        for side, item in raw.items():
            if isinstance(item, dict):
                blockers.append(_drop_empty({
                    "side": side,
                    "kind": item.get("kind"),
                    "statement": _short_text(
                        str(item.get("statement") or item.get("text") or ""),
                        180,
                    ),
                }))
    for handle in named_handles:
        if handle.get("requires_cut_to_frontier"):
            blockers.append(_drop_empty({
                "kind": "named_call_not_at_frontier",
                "symbol": handle.get("symbol"),
                "live_call_site_ids": handle.get("live_call_site_ids"),
                "frontier_call_site_ids": handle.get("frontier_call_site_ids"),
            }))
    # Scope fact (neutral, resource-only): a named equiv operates on a subject
    # procedure (e.g. `HH(H).order_f`) that is NOT among the procedures the
    # frontier currently calls (e.g. `H.f`). This is a verifiable structural fact
    # the agent can read — it states *what* the lemma is about and *what* the
    # frontier calls, nothing more. It does NOT recommend reformulating, rewinding,
    # inlining, or abandoning the lemma; that decision stays the agent's. The
    # ingredients are already computed upstream: `handle.procedures` (the lemma's
    # subject) and `live_call_sites[].procedure` (the frontier's live calls).
    frontier_procs = sorted({
        str(site.get("procedure") or "").strip()
        for site in (live_call_sites or [])
        if isinstance(site, dict) and str(site.get("procedure") or "").strip()
    })
    if frontier_procs:
        for handle in named_handles:
            if handle.get("frontier_live") or handle.get("callable_now"):
                continue
            subjects = sorted({
                str(proc).strip()
                for proc in (
                    handle.get("procedures")
                    or ([handle.get("procedure")] if handle.get("procedure") else [])
                )
                if str(proc or "").strip()
            })
            if subjects and set(subjects).isdisjoint(frontier_procs):
                blockers.append(_drop_empty({
                    "kind": "named_call_subject_absent_at_frontier",
                    "symbol": handle.get("symbol"),
                    "subject_procedures": subjects,
                    "frontier_live_procedures": frontier_procs,
                }))
    return _dedupe_dicts(blockers)[:8]


def _call_route_wrapper_depth(
    call_sites: list[dict[str, Any]],
    named_handles: list[dict[str, Any]],
) -> int:
    if not call_sites:
        return 0
    if any(handle.get("frontier_live") for handle in named_handles):
        return 0
    procedures = [
        str(site.get("procedure") or "")
        for site in call_sites
        if str(site.get("procedure") or "")
    ]
    if not procedures:
        return 1
    return max(1, max(proc.count(".") for proc in procedures))


def _call_route_exposure(
    handles: dict[str, Any],
    named_handles: list[dict[str, Any]],
) -> dict[str, Any]:
    compact_by_symbol = {
        str(handle.get("symbol") or ""): handle
        for handle in named_handles
        if str(handle.get("symbol") or "")
    }
    for raw_handle in _list(handles.get("callable_lemmas")):
        if not isinstance(raw_handle, dict):
            continue
        symbol = str(raw_handle.get("lemma") or "")
        handle = compact_by_symbol.get(symbol, {})
        symbol = str(handle.get("symbol") or "")
        if not handle.get("requires_cut_to_frontier"):
            continue
        for plan in _list(_dict(raw_handle).get("program_action_plans")):
            if not isinstance(plan, dict):
                continue
            action = _call_route_first_exposure_action(plan)
            if action:
                return _drop_empty({
                    "symbol": symbol,
                    "plan_id": plan.get("id"),
                    "plan_kind": plan.get("kind"),
                    "action": action,
                })
    return {}


def _call_route_first_exposure_action(plan: dict[str, Any]) -> dict[str, Any]:
    for action in _list(plan.get("phase_order")):
        if not isinstance(action, dict):
            continue
        kind = str(action.get("kind") or "")
        if kind not in {
            "expose_asymmetric_prefix",
            "expose_call_pair_frontier",
            "expose_last_call_frontier",
            "open_one_wrapper",
        }:
            continue
        return _drop_empty({
            "kind": kind,
            "tactic_shape": action.get("tactic_hint") or action.get("tactic"),
            "tactic_family": action.get("tactic_family"),
            "left_statement_count": action.get("left_statement_count"),
            "right_statement_count": action.get("right_statement_count"),
            "target_call_site_ids": action.get("target_call_site_ids"),
            "requires_instantiation": action.get("requires_instantiation"),
            "invariant_skeleton": action.get("invariant_skeleton"),
            "reason": action.get("reason"),
        })
    return {}


def _call_route_templates(
    handles: dict[str, Any],
    named_handles: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    bindings = _dict(handles.get("instantiation_bindings"))
    out: list[dict[str, Any]] = []
    for handle in named_handles:
        symbol = str(handle.get("symbol") or "")
        if not symbol:
            continue
        binding = binding_for_name(bindings, symbol)
        call_elaboration = _dict(binding.get("call_elaboration"))
        if call_elaboration.get("available"):
            out.append(_drop_empty({
                "symbol": symbol,
                "status": call_elaboration.get("status"),
                "preferred_call_form": "exlim_then_call_fallback",
                "tactic_shape": call_elaboration.get("tactic_template"),
                "direct_ecall_template": call_elaboration.get("direct_ecall_template"),
                "lifted_value_arguments": call_elaboration.get("lifted_value_arguments"),
                "unresolved_non_value_slots": call_elaboration.get(
                    "unresolved_non_value_slots"
                ),
                "lemma_precondition_coverage": call_elaboration.get(
                    "lemma_precondition_coverage"
                ),
            }))
            continue
        templates = [
            _dict(item) for item in _list(binding.get("instantiated_templates"))
            if isinstance(item, dict)
        ]
        if templates:
            out.append(_drop_empty({
                "symbol": symbol,
                "status": "instantiated_template",
                "tactic_shape": templates[0].get("tactic"),
                "confidence": templates[0].get("confidence"),
            }))
            continue
        # A call-equiv lemma (LHS ~ RHS, no value args) is invoked by a bare
        # `call <name>.`; emit it as a daemon-probeable candidate even when the
        # frontier matcher did not mark it `callable_now`, so `call_site_options`
        # can verify and surface it (enumerate-and-verify, like bridge_options).
        is_equiv_call = len(_list(handle.get("procedures"))) >= 2 or "equiv" in str(
            handle.get("source") or ""
        )
        if (
            (handle.get("callable_now") or is_equiv_call)
            and not handle.get("requires_instantiation")
            and not _list(handle.get("missing_slots"))
        ):
            out.append({
                "symbol": symbol,
                "status": ("direct_named_call" if handle.get("callable_now")
                           else "candidate_named_call"),
                "tactic_shape": f"call {symbol}.",
            })
        elif _list(handle.get("missing_slots")):
            out.append(_drop_empty({
                "symbol": symbol,
                "status": "missing_instantiation",
                "missing_slots": handle.get("missing_slots"),
            }))
    return _dedupe_dicts(out)[:6]


def _short_text(text: str, limit: int) -> str:
    normalized = " ".join(str(text or "").split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: max(0, limit - 3)].rstrip() + "..."


def _apply_legality_to_candidates(
    candidates: list[dict[str, Any]],
    legality: dict[str, dict[str, Any]],
    liveness: dict[str, Any],
    *,
    current_layer: str = "",
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        item = dict(candidate)
        family = str(item.get("tactic_family") or "unknown")
        verdict = dict(legality.get(family) or legality.get("unknown") or {})
        scheduler_role = str(
            item.get("scheduler_role")
            or _dict(item.get("cost_factors")).get("scheduler_role")
            or ""
        )
        if (
            family == "procedure_transform"
            and str(item.get("action_type") or "") == "strategy_hint"
            and scheduler_role in {"semantic_frontier_map", "semantic_risk_map"}
            and _dict(_dict(item.get("cost_factors")).get(
                "bad_event_candidate_map"
            )).get("available")
            and current_layer in {"call_site", "procedure_body"}
        ):
            verdict = _legality(
                "preferred",
                (
                    "Read-only procedure semantic maps are in phase at the "
                    "current frontier; they describe resources and risks "
                    "without lowering the proof."
                ),
            )
        item["legality"] = verdict
        if verdict.get("status") == "avoid":
            item["cost"] = "expensive" if family == "inline_all" else str(item.get("cost") or "unknown")
            if family == "inline_all":
                factors = dict(item.get("cost_factors") or {})
                factors["lost_handles"] = int(liveness.get("live_call_site_count") or 0)
                factors["lost_callable_lemmas"] = int(
                    liveness.get("live_callable_lemma_count") or 0
                )
                item["cost_factors"] = factors
            if item.get("action_type") in {"tactic_candidate", "runnable_tactic"}:
                item["action_type"] = "avoid_action"
        out.append(item)
    # candidate_rank (heuristic preference) ordering removed (ranker removal,
    # step 2): the menu keeps its structural build order; the one factual
    # sequence it must respect (the Pr bridge chain) is applied downstream by
    # _order_instantiated_pr_bridges.
    return out


def _apply_name_resolution_to_candidates(
    candidates: list[dict[str, Any]],
    name_resolution: dict[str, Any],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        item = dict(candidate)
        lemma = _candidate_lemma_name(item)
        resolved = resolution_for_name(name_resolution, lemma) if lemma else {}
        if resolved:
            item["name_resolution"] = _compact_name_resolution_item(resolved)
            factors = dict(item.get("cost_factors") or {})
            status = str(resolved.get("resolution_status") or "")
            exact = bool(resolved.get("exact_signature_known"))
            factors["name_resolution_status"] = status
            factors["exact_signature_known"] = exact
            item["cost_factors"] = factors
            is_external = bool(item.get("producer"))
            is_verified = bool(item.get("verified"))
            if not exact:
                preconditions = list(item.get("preconditions") or [])
                action = str(resolved.get("signature_lookup_action") or "")
                if action:
                    preconditions.append(f"run `{action}` before guessing arguments")
                item["preconditions"] = preconditions
                if (
                    is_external
                    and not is_verified
                    and item.get("action_type") in {"tactic_candidate", "runnable_tactic"}
                ):
                    item["action_type"] = "strategy_hint"
                    item["confidence"] = "low"
                    item["why"] = (
                        str(item.get("why") or "")
                        + (
                            " ProofIR has not resolved this lemma signature; "
                            "inspect the name before treating the tactic as runnable."
                        )
                    ).strip()
            elif status == "source_local_scope_check_required":
                if (
                    is_external
                    and not is_verified
                    and item.get("action_type") in {"tactic_candidate", "runnable_tactic"}
                ):
                    item["action_type"] = "strategy_hint"
                    item["confidence"] = "low"
            elif (
                is_external
                and not is_verified
                and str(item.get("tactic_family") or "") == "pr_path_plan"
                and item.get("action_type") == "runnable_tactic"
            ):
                # A static AUTO-* `apply`/`have` suggestion is a useful edge
                # in the Pr graph, but it is not a checked compiler action.
                # Keep it probeable while letting ProofIR's typed, instantiated
                # templates rank first.
                item["action_type"] = "tactic_candidate"
                factors = dict(item.get("cost_factors") or {})
                factors["external_pr_path_requires_easycrypt_validation"] = True
                item["cost_factors"] = factors
        out.append(item)
    return out


def _apply_instantiation_bindings_to_candidates(
    candidates: list[dict[str, Any]],
    instantiation_bindings: dict[str, Any],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        item = dict(candidate)
        lemma = _candidate_lemma_name(item)
        binding = binding_for_name(instantiation_bindings, lemma) if lemma else {}
        if binding:
            compact = _compact_instantiation_binding_item(binding)
            item["instantiation_binding"] = compact
            templates = compact.get("instantiated_templates") or []
            if templates:
                factors = dict(item.get("cost_factors") or {})
                factors["instantiation_binding_status"] = "has_candidates"
                factors["instantiated_template_count"] = len(templates)
                item["cost_factors"] = factors
        out.append(item)
    return out


def _apply_negative_transition_to_candidates(
    candidates: list[dict[str, Any]],
    latest_transition: dict[str, Any],
    *,
    current_layer: str = "",
) -> list[dict[str, Any]]:
    """Downgrade candidates that just produced no visible progress."""
    if not _transition_is_no_progress(latest_transition):
        return candidates
    failed_tactic = _normalize_tactic_text(
        str(latest_transition.get("tactic") or "")
    )
    if not failed_tactic:
        return candidates
    out: list[dict[str, Any]] = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        item = dict(candidate)
        tactic = _normalize_tactic_text(
            str(item.get("tactic") or item.get("action") or "")
        )
        if tactic and tactic == failed_tactic:
            factors = dict(item.get("cost_factors") or {})
            factors["negative_evidence"] = "latest_no_progress"
            factors["no_progress_reason"] = str(
                latest_transition.get("no_progress_reason")
                or latest_transition.get("status")
                or "no_progress"
            )
            item["cost_factors"] = factors
            item["action_type"] = "avoid_action"
            item["cost"] = "expensive"
            item["confidence"] = "low"
            item["legality"] = {
                "status": "avoid",
                "reason": (
                    "The latest committed attempt of this tactic made no "
                    "visible proof-state progress and was rolled back."
                ),
            }
            item["why"] = (
                str(item.get("why") or "Candidate was suggested.")
                + " Negative evidence: the same tactic was just no-progress."
            )
        out.append(item)
    # candidate_rank (heuristic preference) ordering removed (ranker removal,
    # step 2): the menu keeps its structural build order; the one factual
    # sequence it must respect (the Pr bridge chain) is applied downstream by
    # _order_instantiated_pr_bridges.
    return out


def _apply_candidate_pipeline(
    candidates: list[dict[str, Any]],
    *,
    name_resolution: dict[str, Any],
    instantiation_bindings: dict[str, Any],
    legality: dict[str, Any],
    liveness: dict[str, Any],
    current_layer: str,
    latest_transition: dict[str, Any],
) -> list[dict[str, Any]]:
    """Shared candidate post-processing chain, applied identically to the
    external-candidate list and the action menu: name-resolution -> instantiation
    bindings -> legality -> negative-transition downgrade."""
    return _apply_negative_transition_to_candidates(
        _apply_legality_to_candidates(
            _apply_instantiation_bindings_to_candidates(
                _apply_name_resolution_to_candidates(
                    candidates,
                    name_resolution,
                ),
                instantiation_bindings,
            ),
            legality,
            liveness,
            current_layer=current_layer,
        ),
        latest_transition,
        current_layer=current_layer,
    )


def _transition_is_no_progress(transition: dict[str, Any]) -> bool:
    return (
        bool(transition.get("no_progress"))
        or str(transition.get("kind") or "") == "no_progress"
        or str(transition.get("status") or "") == "no_progress_reverted"
    )


def _normalize_tactic_text(tactic: str) -> str:
    text = _extract_tactic_from_action(str(tactic or "")).strip()
    text = re.sub(r"\s+", " ", text)
    return text


def _rewrite_leaf_from_tactic(tactic: str) -> str:
    text = str(tactic or "").strip()
    text = re.sub(r"^[+\-*]\s*", "", text)
    text = re.sub(r"^(?:by\s+)+", "", text)
    m = re.match(
        r"rewrite\s+-?\s*\(?\s*([A-Za-z_][A-Za-z0-9_'.]*)",
        text,
    )
    if not m:
        return ""
    return _lemma_leaf(m.group(1))


def _compact_name_resolution_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": str(item.get("name") or ""),
        "resolution_status": str(item.get("resolution_status") or ""),
        "source_kind": str(item.get("source_kind") or ""),
        "exact_signature_known": bool(item.get("exact_signature_known")),
        "requires_instantiation": bool(item.get("requires_instantiation")),
        "signature_lookup_action": str(item.get("signature_lookup_action") or ""),
        "procedure_match": str(item.get("procedure_match") or ""),
        "tactic_template": str(item.get("tactic_template") or ""),
        "parameter_slots": [
            {
                "kind": str(slot.get("kind") or ""),
                "name": str(slot.get("name") or ""),
                "placeholder": str(slot.get("placeholder") or ""),
            }
            for slot in (item.get("parameter_slots") or [])[:6]
            if isinstance(slot, dict)
        ],
    }


def _compact_instantiation_binding_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": str(item.get("name") or ""),
        "instantiated_templates": [
            {
                "status": str(template.get("status") or ""),
                "tactic": str(template.get("tactic") or ""),
                "confidence": str(template.get("confidence") or ""),
            }
            for template in (item.get("instantiated_templates") or [])[:3]
            if isinstance(template, dict)
        ],
        "slots": [
            {
                "slot": {
                    "kind": str(_dict(slot.get("slot")).get("kind") or ""),
                    "name": str(_dict(slot.get("slot")).get("name") or ""),
                    "placeholder": str(
                        _dict(slot.get("slot")).get("placeholder") or ""
                    ),
                },
                "candidates": [
                    {
                        "value": str(candidate.get("value") or ""),
                        "source": str(candidate.get("source") or ""),
                        "confidence": str(candidate.get("confidence") or ""),
                    }
                    for candidate in (slot.get("candidates") or [])[:4]
                    if isinstance(candidate, dict)
                ],
            }
            for slot in (item.get("slots") or [])[:6]
            if isinstance(slot, dict)
        ],
        "pr_elaboration": _compact_pr_elaboration(
            _dict(item.get("pr_elaboration"))
        ),
    }
