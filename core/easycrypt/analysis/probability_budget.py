"""Small static analyzer for probability-budget proof states.

The pass is intentionally conservative: it only emits guidance when the
current goal visibly contains a single-program probability/product-bound shape
or a one-sided phoare bound with a product-like budget.  It does not propose a
proof script; it surfaces route context for the workspace view and route-health
diagnostics.
"""
from __future__ import annotations

import re
from typing import Any

from core.easycrypt.analysis.ec_utils import (
    as_dict as _dict,
    as_list as _list,
    collapse_ws as _collapse_ws,
    dedupe_present_strings as _dedupe_strings,
    drop_empty as _drop_empty,
    matching_delimiter as _matching_delimiter,
    string_list as _string_list,
    strip_outer_parens as _strip_outer_parens,
    split_top_level_conjuncts as _split_top_level_conjuncts,
)
from core.easycrypt.analysis.ec_pr_canonical import parse_pr_terms
from core.context_intents import direct_context_request


def analyze_probability_budget(goal_text: str) -> dict[str, Any]:
    """Return advisory probability-budget context for a goal string.

    The returned shape is stable, JSON-serializable, and empty when the goal
    does not look like a product-budget probability proof.
    """

    text = str(goal_text or "")
    if not text.strip():
        return {}

    scaled_equality = _extract_scaled_probability_equality(text)
    if scaled_equality:
        return _scaled_probability_analysis(
            goal_text=text,
            bound_info=scaled_equality,
            scaled=scaled_equality,
        )

    bound_info = _extract_bound(text)
    if not bound_info:
        return {}

    scaled_bound = _extract_scaled_probability_product(str(bound_info.get("bound") or ""))
    if scaled_bound:
        return _scaled_probability_analysis(
            goal_text=text,
            bound_info=bound_info,
            scaled=scaled_bound,
        )

    if str(bound_info.get("relation") or "").strip() in {"=", "[=]"}:
        return {}
    bound = bound_info["bound"]
    if not _looks_like_product_budget(bound):
        return {}

    event = _extract_event(text)
    event_bound_bridge = _event_bound_bridge_for_goal(text, event)
    factors = _split_top_level_product_terms(bound)
    fact_handles = _fact_handles_for_bound(bound, event)
    budget_ledger = _build_budget_ledger(
        goal_text=text,
        bound_info=bound_info,
        event=event,
        event_bound_bridge=event_bound_bridge,
        factors=factors,
    )
    event_bound_bridge = (
        _event_bound_bridge_from_ledger(budget_ledger)
        or event_bound_bridge
    )

    return _drop_empty({
        "kind": "probability_budget",
        "budget_shape": "product_bound",
        "source": bound_info["source"],
        "bound_relation": bound_info["relation"],
        "bound": bound,
        "factors": factors,
        "event_shape": event,
        "event_bound_bridge": event_bound_bridge,
        "budget_ledger": budget_ledger,
        "useful_fact_handles": fact_handles,
        "read_as": (
            "Factual product-budget shape of the goal (bound, factors, event, "
            "event-bound bridge). Not a proof script, route ranking, or tactic "
            "order."
        ),
    })


def probability_budget_route_risk(
    *,
    goal_text: str,
    route_events: list[dict[str, Any]],
) -> dict[str, Any]:
    """Return route-health warning for product-budget trap patterns."""

    if not route_events:
        return {}

    events = route_events[-40:]
    recent = events[-8:]
    analysis = analyze_probability_budget(goal_text)
    split_bound = _recent_product_bound_from_phoare_split(recent)
    one_sided_call_residual = (
        _has_one_sided_le_one_bound(goal_text)
        and _has_visible_call_frontier(goal_text)
    )
    if not analysis and one_sided_call_residual and split_bound:
        analysis = _post_split_budget_context(split_bound)
    if not analysis:
        return {}

    latest = recent[-1]
    latest_head = str(latest.get("tactic_head") or "").lower()
    latest_tactic = str(latest.get("tactic") or "").lower()
    seq_ledger = _seq_budget_ledger(
        goal_text=goal_text,
        route_events=events,
        product_bound=str(analysis.get("bound") or ""),
        budget_shape=str(analysis.get("budget_shape") or ""),
        scale=str(analysis.get("scale") or ""),
        source_probability=str(analysis.get("source_probability") or ""),
    )
    budget_ledger = _risk_budget_ledger(analysis, seq_ledger)
    budget_shape = str(analysis.get("budget_shape") or "")
    budget_label = (
        "scaled probability budget"
        if budget_shape == "scaled_probability" else
        "product probability budget"
    )
    seq_budget_label = (
        "source/scale budget"
        if budget_shape == "scaled_probability" else
        "product budget"
    )
    bad_route_memory = _probability_budget_bad_route_memory(
        events,
        goal_text=goal_text,
        product_bound=str(analysis.get("bound") or ""),
        budget_shape=str(analysis.get("budget_shape") or ""),
        scale=str(analysis.get("scale") or ""),
        source_probability=str(analysis.get("source_probability") or ""),
    )

    local_sampling = any(
        _event_looks_like_sampling(event)
        and _event_accepted(event)
        for event in recent
    )
    seq_budget_cut = any(
        _seq_context_is_risky(item)
        for item in _list(seq_ledger.get("recent_seq_cuts"))
    )
    split_route = any(
        "phoare split" in str(event.get("tactic") or "").lower()
        and _event_accepted(event)
        for event in recent
    )
    bound_call_failure = (
        latest.get("rejected")
        and latest_head == "call"
        and "bound must" in str(latest.get("error_summary") or "").lower()
    )
    direct_true_call = (
        latest_head == "call"
        and "true" in latest_tactic
        and one_sided_call_residual
    )

    if not any((
        local_sampling,
        seq_budget_cut,
        split_route,
        bound_call_failure,
        one_sided_call_residual and split_bound,
        direct_true_call,
        bad_route_memory,
    )):
        return {}

    evidence: list[str] = []
    if local_sampling:
        evidence.append(f"recent accepted/preflighted local sampling under a {budget_label}")
    if seq_budget_cut:
        evidence.append(
            f"recent accepted/preflighted `seq` cut may allocate the {seq_budget_label} to the wrong branch"
        )
    if split_route:
        evidence.append("recent accepted/preflighted `phoare split !` under a product budget")
    if bound_call_failure:
        evidence.append(str(latest.get("error_summary") or "direct call rejected by bound shape"))
    if one_sided_call_residual and (split_bound or direct_true_call):
        evidence.append("visible one-sided `[<=] 1%r` procedure-call residual")
    if direct_true_call:
        evidence.append("recent direct `call (_: true).` under a one-sided bound")
    if bad_route_memory:
        evidence.append("route memory contains previously bad probability-budget tactic shapes")

    # The shape-based anti-routes are an ORCHESTRATOR route-health signal (this
    # function feeds `route_health`, kept per the orchestrator-search boundary),
    # not an agent-facing field — `analyze_probability_budget` no longer emits
    # them, so compute them here for the route-risk signal only.
    if budget_shape == "scaled_probability":
        anti_routes = list(_anti_routes_for_scaled_probability())
    else:
        anti_routes = list(_anti_routes_for_shape(goal_text, {
            "bound": str(analysis.get("bound") or ""),
            "relation": str(analysis.get("bound_relation") or ""),
            "source": str(analysis.get("source") or ""),
        }))
    if seq_budget_cut:
        anti_routes = _append_anti_route(
            anti_routes,
            {
                "route": "seq_cut_allocates_product_budget_to_prefix",
                "reason": (
                    "A plausible `seq K : side_fact` can put the whole product "
                    "budget on a prefix or side condition that should cost "
                    "about 1%r, leaving the real event budget unfunded."
                    if budget_shape != "scaled_probability" else
                    "A plausible `seq K : event scale` can omit the source "
                    "probability slot, leaving the real scaled-probability "
                    "decomposition unfunded."
                ),
            },
        )
    for route in bad_route_memory:
        anti_routes = _append_anti_route(anti_routes, route)

    return _drop_empty({
        "signal": "probability_budget_route_risk",
        "confidence": (
            "high"
            if bound_call_failure or one_sided_call_residual or seq_budget_cut or bad_route_memory
            else "medium"
        ),
        "message": (
            f"This route is under a {budget_label}. A locally accepted tactic "
            "may still charge the wrong proof obligation."
        ),
        "evidence": evidence,
        "budget": {
            "bound": analysis.get("bound"),
            "factors": analysis.get("factors"),
            "event_shape": analysis.get("event_shape"),
            "event_bound_bridge": analysis.get("event_bound_bridge"),
            "budget_ledger": analysis.get("budget_ledger"),
        },
        "budget_ledger": budget_ledger,
        "seq_budget_ledger": seq_ledger,
        "route_memory": bad_route_memory,
        "anti_routes": anti_routes,
        "recommended_next": direct_context_request({
            "intent": "probability_budget_ledger",
            "payload": {},
        }),
        "primary_next_action": direct_context_request({
            "intent": "probability_budget_ledger",
            "payload": {},
        }),
        "useful_inspections": _probability_budget_useful_inspections(
            source=str(analysis.get("source") or ""),
            budget_shape=budget_shape,
            one_sided_call_residual=one_sided_call_residual,
            event_bound_bridge=_dict(analysis.get("event_bound_bridge")),
        ),
    })


def _probability_budget_useful_inspections(
    *,
    source: str,
    one_sided_call_residual: bool,
    budget_shape: str = "",
    event_bound_bridge: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    ledger_label = (
        "scaled-probability ledger"
        if budget_shape == "scaled_probability" else
        "product-bound ledger"
    )
    inspections: list[dict[str, Any]] = [
            direct_context_request({
                "intent": "probability_budget_ledger",
                "payload": {},
                "why": (
                    f"Read the {ledger_label} before committing local "
                    "sampling, split, seq, or call steps."
                ),
            }),
            direct_context_request({
                "intent": "lemma_hints",
                "payload": {},
                "why": (
                    "Look for probability/event decomposition facts before "
                    "descending into local sampling or call tactics."
                ),
            }),
            direct_context_request({
                "intent": "tactic_forms",
                "payload": {"name": "seq"},
                "why": "Check one-sided `phoare [<=]` seq budget allocation before committing a cut.",
            }),
        ]
    bridge = _dict(event_bound_bridge)
    point_route = _dict(bridge.get("point_mass_route"))
    for lemma in _list(bridge.get("candidate_lemma_handles"))[:2]:
        symbol = str(_dict(lemma).get("symbol") or "").strip()
        if symbol:
            inspections.insert(0, {
                "intent": "lookup_symbol",
                "payload": {"symbol": symbol},
                "why": (
                    "The current goal is a list-membership event with a visible "
                    "size bound; inspect the measure bridge before more local sampling."
                ),
            })
    if point_route:
        inspections.insert(0, direct_context_request({
            "intent": "probability_budget_ledger",
            "payload": {},
            "why": (
                "The ledger has a list-membership point-mass route; read the "
                "sample-to-factor assignments before more `seq` or `call` attempts."
            ),
        }))
    if source == "single_program_probability_goal":
        inspections.append(
            direct_context_request({
                "intent": "tactic_forms",
                "payload": {"name": "fel"},
                "why": "Use only while the goal is still top-level `Pr[...] <= ...`.",
            })
        )
    if one_sided_call_residual:
        inspections.append(direct_context_request({
            "intent": "tactic_forms",
            "payload": {"name": "call"},
            "why": "A one-sided `[<=] 1%r` call may need `call (_: PRE ==> POST)`, not `call (_: true).`.",
        }))
    inspections.append(direct_context_request({
        "intent": "tactic_forms",
        "payload": {"name": "phoare_split"},
        "why": "Check split-bound direction before committing another split route.",
    }))
    return inspections


def _scaled_probability_analysis(
    *,
    goal_text: str,
    bound_info: dict[str, str],
    scaled: dict[str, Any],
) -> dict[str, Any]:
    source_probability = str(scaled.get("source_probability") or "").strip()
    scale = str(scaled.get("scale") or "").strip()
    target_probability = str(
        scaled.get("target_probability")
        or bound_info.get("target_probability")
        or ""
    ).strip()
    if not source_probability or not scale:
        return {}

    event = (
        _event_from_probability_term(target_probability)
        if target_probability else
        _extract_event(goal_text)
    )
    ledger = _build_scaled_probability_ledger(
        goal_text=goal_text,
        bound_info=bound_info,
        source_probability=source_probability,
        target_probability=target_probability,
        scale=scale,
        scale_factors=_string_list(scaled.get("scale_factors")),
        event=event,
    )
    return _drop_empty({
        "kind": "probability_budget",
        "budget_shape": "scaled_probability",
        "source": bound_info.get("source") or "top_level_probability_equality",
        "bound_relation": bound_info.get("relation"),
        "bound": scaled.get("bound_expression") or bound_info.get("bound"),
        "scale": scale,
        "factors": [scale],
        "scale_factors": scaled.get("scale_factors"),
        "source_probability": source_probability,
        "target_probability": target_probability,
        "event_shape": event,
        "budget_ledger": ledger,
        "useful_fact_handles": _fact_handles_for_scaled_probability(scale),
        "read_as": (
            "Factual scaled-probability shape (source/target probabilities, "
            "scale, factors, event). Not a proof script or route ranking."
        ),
    })


def _build_scaled_probability_ledger(
    *,
    goal_text: str,
    bound_info: dict[str, str],
    source_probability: str,
    target_probability: str,
    scale: str,
    scale_factors: list[str],
    event: dict[str, Any],
) -> dict[str, Any]:
    event_text = str(_dict(event).get("text") or "").strip()
    factor_slots: list[dict[str, Any]] = [
        {
            "id": "P",
            "expr": source_probability,
            "role": "source_probability",
        },
        {
            "id": "S1",
            "expr": scale,
            "role": "scale_point_mass",
        },
    ]
    if scale_factors and len(scale_factors) > 1:
        factor_slots.extend(
            {
                "id": f"S{idx}",
                "expr": factor,
                "role": _factor_role(factor),
                "source": "scale_factor",
            }
            for idx, factor in enumerate(scale_factors, start=2)
        )
    event_obligations = [_drop_empty({
        "id": "E1",
        "event": event_text,
        "event_kind": event.get("kind"),
        "source_probability_slot": "P",
        "scale_factor_slot": "S1",
        "expected_seq_shape": "seq K : event (P) (scale) _ 0%r",
        "source_probability": source_probability,
        "scale": scale,
    })] if event_text else []
    return _drop_empty({
        "schema_version": 1,
        "kind": "probability_budget_ledger",
        "status": "complete" if event_obligations else "partial",
        "source": bound_info.get("source"),
        "bound_relation": bound_info.get("relation"),
        "total_bound": str(bound_info.get("bound") or "").strip(),
        "budget_shape": "scaled_probability",
        "source_probability": source_probability,
        "target_probability": target_probability,
        "scale": scale,
        "scale_factors": scale_factors,
        "factor_slots": factor_slots,
        "event_obligations": event_obligations,
        "read_as": (
            "A factual scaled-probability ledger: P is the source probability "
            "resource, S1 is the scalar point-mass budget, and the factor slots "
            "/ event obligations describe the product structure. Structure only "
            "— no route plan or ranking."
        ),
    })


def _anti_routes_for_scaled_probability() -> list[dict[str, str]]:
    return [
        {
            "route": "scale_only_seq_for_scaled_probability",
            "reason": (
                "A `seq` cut that spends only the scalar factor can leave the "
                "source `Pr[...]` resource outside the event branch."
            ),
        },
        {
            "route": "accepted_seq_as_route_quality_without_source_probability",
            "reason": (
                "EasyCrypt may accept a seq cut even when the source probability "
                "slot is missing from the budget vector."
            ),
        },
        {
            "route": "local_sampling_before_source_probability_branch",
            "reason": (
                "Do not descend to the local sample before the source probability "
                "branch has been exposed by the event cut."
            ),
        },
        {
            "route": "direct_call_true_under_scaled_phoare_bound",
            "reason": (
                "`call (_: true).` does not explain either the source probability "
                "or the scalar point-mass budget."
            ),
        },
    ]


def _fact_handles_for_scaled_probability(scale: str) -> list[dict[str, str]]:
    handles: list[dict[str, str]] = []
    if "/" in scale:
        handles.extend([
            {
                "symbol": "divr_ge0",
                "why": "Ratio scale factors usually need non-negativity side conditions.",
            },
            {
                "symbol": "divr_gt0",
                "why": "Strict positivity is useful for scale nonzero side conditions.",
            },
        ])
    if "bound" in scale:
        handles.append({
            "symbol": "bound_pos",
            "why": "The visible scalar denominator is named `bound` in this goal family.",
        })
    return _dedupe_fact_handles(handles)[:4]


def _seq_budget_ledger(
    *,
    goal_text: str,
    route_events: list[dict[str, Any]],
    product_bound: str,
    budget_shape: str = "",
    scale: str = "",
    source_probability: str = "",
) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    for event in route_events:
        if not _event_looks_like_seq_cut(event) or not _event_accepted(event):
            continue
        parsed = _parse_one_sided_seq_cut(str(event.get("tactic") or ""))
        if not parsed:
            continue
        assertion = str(parsed.get("assertion") or "")
        budget_arg = str(parsed.get("budget_arg") or "")
        classification = _classify_seq_budget_arg(
            budget_arg,
            product_bound,
            assertion=assertion,
            goal_text=goal_text,
            budget_shape=budget_shape,
            scale=scale,
            source_probability=source_probability,
        )
        assertion_analysis = _seq_assertion_analysis(
            assertion=assertion,
            goal_text=goal_text,
        )
        entries.append(_drop_empty({
            "tactic": event.get("tactic"),
            "stmt_count": parsed.get("stmt_count"),
            "assertion_preview": assertion[:180],
            "budget_arg": budget_arg,
            "post_tactic_suffix": parsed.get("post_tactic_suffix"),
            "classification": classification,
            "assertion_analysis": assertion_analysis,
            "allowed_boundary_move": (
                "seq_event_unit_suffix_boundary"
                if classification == "unit_bound_event_preservation_candidate"
                else ""
            ),
            "assertion_is_side_condition": _looks_like_bound_side_text(assertion),
            "current_post_is_side_residual": _post_looks_like_bound_side_residual(goal_text),
            "preferred_shape": (
                f"seq {parsed.get('stmt_count')} : Q (P) ({scale}) _ 0%r."
                if budget_shape == "scaled_probability" and scale else
                f"seq {parsed.get('stmt_count')} : Q {product_bound}."
                if product_bound else ""
            ),
        }))
    return _drop_empty({
        "recent_seq_cuts": entries[-5:],
        "read_as": (
            "`seq K : Q B.` is a budget ledger entry: Q is the cut "
            "assertion and B is the budget assigned to the budget-carrying "
            "branch. For scaled-probability goals, the safe shape must also "
            "carry the source probability slot P. Missing B, missing P, or "
            "`1%r` can be accepted while charging the wrong branch."
        ) if entries else "",
    })


def _build_budget_ledger(
    *,
    goal_text: str,
    bound_info: dict[str, str],
    event: dict[str, Any],
    event_bound_bridge: dict[str, Any],
    factors: list[str],
) -> dict[str, Any]:
    factor_slots = _factor_slots_for_product(factors)
    if event_bound_bridge:
        point_mass_route = _list_membership_point_mass_route_for_goal(
            goal_text=goal_text,
            bridge=event_bound_bridge,
            factor_slots=factor_slots,
        )
        if point_mass_route:
            event_bound_bridge = {
                **event_bound_bridge,
                "point_mass_route": point_mass_route,
            }
    event_obligations = _event_obligations_for_goal(
        goal_text=goal_text,
        event=event,
        factor_slots=factor_slots,
    )
    if event_bound_bridge and event_obligations:
        event_obligations[0] = _merge_event_bridge(
            event_obligations[0],
            event_bound_bridge,
        )
    elif event_bound_bridge:
        event_obligations.append(_event_obligation_from_bridge(
            event_bound_bridge,
            factor_slots=factor_slots,
            index=1,
        ))

    status = _ledger_status(factor_slots, event_obligations)
    return _drop_empty({
        "schema_version": 1,
        "kind": "probability_budget_ledger",
        "status": status,
        "source": bound_info.get("source"),
        "bound_relation": bound_info.get("relation"),
        "total_bound": bound_info.get("bound"),
        "grouped_factors": factors,
        "factor_slots": factor_slots,
        "event_obligations": event_obligations,
        "read_as": (
            "A factual probability-budget ledger: factor slots are the "
            "resources in the product bound, and event obligations are the "
            "proof events tied to them. Structure only — no route plan or "
            "ranking."
        ),
    })


def _risk_budget_ledger(
    analysis: dict[str, Any],
    seq_ledger: dict[str, Any],
) -> dict[str, Any]:
    ledger = dict(_dict(analysis.get("budget_ledger")))
    if not ledger:
        ledger = {
            "schema_version": 1,
            "kind": "probability_budget_ledger",
            "status": "risk_only",
            "total_bound": analysis.get("bound"),
            "factor_slots": [
                {"id": f"B{idx + 1}", "expr": factor}
                for idx, factor in enumerate(_list(analysis.get("factors")))
            ],
        }
    if seq_ledger:
        ledger["recent_seq_cuts"] = seq_ledger.get("recent_seq_cuts")
        ledger["seq_cut_read_as"] = seq_ledger.get("read_as")
    return _drop_empty(ledger)


def _event_bound_bridge_from_ledger(
    ledger: dict[str, Any],
) -> dict[str, Any]:
    for obligation in _list(_dict(ledger).get("event_obligations")):
        bridge = _dict(_dict(obligation).get("event_bound_bridge"))
        if bridge:
            return bridge
    return {}


def _factor_slots_for_product(factors: list[str]) -> list[dict[str, Any]]:
    slots: list[dict[str, Any]] = []
    for grouped_index, factor in enumerate(factors, start=1):
        expanded = _expand_power_factor(factor)
        for repeat_index, expr in enumerate(expanded, start=1):
            slots.append(_drop_empty({
                "id": f"B{len(slots) + 1}",
                "expr": expr,
                "grouped_factor": factor,
                "grouped_factor_index": grouped_index,
                "source": (
                    "power_expansion"
                    if len(expanded) > 1 else
                    "top_level_product"
                ),
                "power_repeat_index": (
                    repeat_index if len(expanded) > 1 else None
                ),
                "role": _factor_role(expr),
            }))
    return slots


def _expand_power_factor(factor: str) -> list[str]:
    text = _strip_outer_parens(str(factor or "").strip())
    match = re.match(
        r"^(?P<base>.+?)\s*\^\s*(?P<power>\d+)$",
        text,
        flags=re.DOTALL,
    )
    if not match:
        return [text] if text else []
    try:
        power = int(match.group("power"))
    except ValueError:
        return [text] if text else []
    if power < 2 or power > 8:
        return [text] if text else []
    base = _strip_outer_parens(match.group("base").strip())
    return [base for _ in range(power)]


def _factor_role(expr: str) -> str:
    lower = str(expr or "").lower()
    if "/" in lower and any(token in lower for token in ("order", "card", "size")):
        return "finite_domain_point_mass"
    if "/" in lower:
        return "ratio_bound"
    if "q" in lower:
        return "query_bound"
    return "budget_factor"


def _event_obligations_for_goal(
    *,
    goal_text: str,
    event: dict[str, Any],
    factor_slots: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    event_texts = _event_texts_for_ledger(goal_text, event)
    obligations: list[dict[str, Any]] = []
    for text in event_texts:
        membership = _extract_membership_event(text)
        kind = _event_kind(text)
        bridge_family = _bridge_family_for_event(goal_text, kind, membership)
        size_bound = _extract_size_bound_for_collection(
            goal_text,
            str(membership.get("collection") or ""),
        )
        obligations.append(_drop_empty({
            "id": f"E{len(obligations) + 1}",
            "event": _collapse_ws(text)[:220],
            "event_kind": kind,
            "collection": membership.get("collection"),
            "bridge_family": bridge_family,
            "size_bound": size_bound,
            "candidate_factor_ids": _candidate_factor_ids(
                factor_slots,
                kind=kind,
                membership=membership,
            ),
        }))
    if obligations:
        return obligations
    if event:
        return [_drop_empty({
            "id": "E1",
            "event": event.get("text"),
            "event_kind": event.get("kind"),
            "bridge_family": _bridge_family_for_event(goal_text, str(event.get("kind") or ""), {}),
            "candidate_factor_ids": _candidate_factor_ids(
                factor_slots,
                kind=str(event.get("kind") or ""),
                membership=_dict(event.get("membership")),
            ),
        })]
    return []


def _event_texts_for_ledger(
    goal_text: str,
    event: dict[str, Any],
) -> list[str]:
    raw = str(_dict(event).get("text") or "")
    post = _extract_post_text(goal_text)
    source = post or raw
    parts = _split_top_level_conjunction(source)
    eventful = [
        part for part in parts
        if _event_kind(part) != "event" or _extract_membership_event(part)
    ]
    return eventful[:8] if eventful else ([raw] if raw else [])


def _split_top_level_conjunction(text: str) -> list[str]:
    return _split_top_level_conjuncts(text, nesting_open="(")


def _bridge_family_for_event(
    goal_text: str,
    kind: str,
    membership: dict[str, str],
) -> str:
    collection = str(membership.get("collection") or "")
    if collection and _extract_size_bound_for_collection(goal_text, collection):
        return "list_size_times_point_mass"
    if kind == "membership_event":
        return "membership_point_mass"
    if kind == "bad_or_win_event":
        return "bad_event_or_union_bound"
    if kind == "result_event":
        return "result_event_bound"
    return "event_bound"


def _candidate_factor_ids(
    factor_slots: list[dict[str, Any]],
    *,
    kind: str,
    membership: dict[str, str],
) -> list[str]:
    preferred_roles = {"finite_domain_point_mass", "ratio_bound"}
    ids = [
        str(slot.get("id") or "")
        for slot in factor_slots
        if str(slot.get("role") or "") in preferred_roles
    ]
    if kind == "membership_event" or membership:
        return [slot_id for slot_id in ids if slot_id][:4]
    return [
        str(slot.get("id") or "")
        for slot in factor_slots
        if str(slot.get("id") or "")
    ][:4]


def _merge_event_bridge(
    obligation: dict[str, Any],
    bridge: dict[str, Any],
) -> dict[str, Any]:
    out = dict(obligation)
    out["bridge_family"] = "list_size_times_point_mass"
    out["event_bound_bridge"] = bridge
    out["collection"] = out.get("collection") or bridge.get("event_collection")
    out["size_bound"] = out.get("size_bound") or bridge.get("size_bound")
    out["candidate_lemma_handles"] = bridge.get("candidate_lemma_handles")
    return _drop_empty(out)


def _event_obligation_from_bridge(
    bridge: dict[str, Any],
    *,
    factor_slots: list[dict[str, Any]],
    index: int,
) -> dict[str, Any]:
    return _drop_empty({
        "id": f"E{index}",
        "event": bridge.get("event_expression"),
        "event_kind": "membership_event",
        "collection": bridge.get("event_collection"),
        "bridge_family": "list_size_times_point_mass",
        "size_bound": bridge.get("size_bound"),
        "event_bound_bridge": bridge,
        "candidate_lemma_handles": bridge.get("candidate_lemma_handles"),
        "candidate_factor_ids": _candidate_factor_ids(
            factor_slots,
            kind="membership_event",
            membership={"collection": str(bridge.get("event_collection") or "")},
        ),
    })


def _ledger_status(
    factor_slots: list[dict[str, Any]],
    event_obligations: list[dict[str, Any]],
) -> str:
    if not factor_slots:
        return "risk_only"
    if not event_obligations:
        return "risk_only"
    bridged = [
        item for item in event_obligations
        if item.get("candidate_factor_ids") or item.get("event_bound_bridge")
    ]
    if (
        bridged
        and len(event_obligations) >= len(factor_slots)
        and all(item.get("candidate_factor_ids") for item in event_obligations)
    ):
        return "complete"
    return "partial"


def _list_membership_point_mass_route_for_goal(
    *,
    goal_text: str,
    bridge: dict[str, Any],
    factor_slots: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build a shape-gated route for Pr[tuple in L] product budgets."""

    size_bound = _dict(bridge.get("size_bound"))
    collection = str(bridge.get("event_collection") or "").strip()
    event_expression = str(bridge.get("event_expression") or "").strip()
    if not collection or not size_bound or not event_expression:
        return {}

    components = _tuple_components(event_expression)
    if not components:
        components = [event_expression]
    statements = _indexed_statements(goal_text)
    samples = _sample_assignments(statements)
    if not samples:
        return {}
    deterministic = _deterministic_assignments(statements)
    assignments = _sample_factor_assignments(
        components=components,
        samples=samples,
        deterministic=deterministic,
        factor_slots=factor_slots,
    )
    if not assignments:
        return {}

    expected_component_count = len(components)
    status = (
        "complete"
        if expected_component_count > 0 and len(assignments) >= expected_component_count
        else "partial"
    )
    upper = str(size_bound.get("upper_bound") or "").strip()
    return _drop_empty({
        "kind": "list_membership_point_mass_route",
        "schema_version": 1,
        "status": status,
        "event_collection": collection,
        "event_expression": _collapse_ws(event_expression),
        "event_components": components,
        "size_fact": size_bound.get("fact"),
        "bridge_lemma": "mu_mem_le_mu1_size",
        "route_plan": [
            "first apply list-size times point-mass bridge; do not start with local call/seq cleanup",
            (
                f"use `{size_bound.get('fact')}` as the list cardinality side fact"
                if size_bound.get("fact") else
                "use the visible `size L <= q` fact as the list cardinality side fact"
            ),
            "then prove a per-point mass bound for one fixed tuple/list element",
            "spend denominator factors by sampled variable and distribution family",
            "only descend to `rnd` after the per-point mass obligation is explicit",
        ],
        "sample_factor_assignments": assignments,
        "factor_assignment_summary": _factor_assignment_summary(assignments),
        "per_point_mass_read": (
            f"After the list-size bridge with `{upper}`, the remaining route is "
            "a per-point bound for the sampled tuple, paid by the listed "
            "sample/factor assignments."
            if upper else
            "After the list-size bridge, the remaining route is a per-point "
            "bound for the sampled tuple, paid by the listed sample/factor assignments."
        ),
        "anti_routes": [
            {
                "route": "seq_unit_bound_for_membership_event",
                "reason": (
                    "`seq K : membership 1%r` may be accepted while moving the "
                    "small product budget away from the list-membership bridge."
                ),
            },
            {
                "route": "event_preserving_call_as_product_bound_route",
                "reason": (
                    "A call invariant that merely preserves `tuple in L` does "
                    "not explain the size-times-point-mass budget."
                ),
            },
        ],
    })


def _tuple_components(expr: str) -> list[str]:
    text = _strip_outer_parens(str(expr or "").strip())
    if not text:
        return []
    parts: list[str] = []
    start = 0
    depth = 0
    for idx, ch in enumerate(text):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        elif ch == "," and depth == 0:
            parts.append(text[start:idx].strip())
            start = idx + 1
    parts.append(text[start:].strip())
    return [part for part in parts if part]


def _indexed_statements(goal_text: str) -> list[dict[str, Any]]:
    statements: list[dict[str, Any]] = []
    for match in re.finditer(r"^\s*\(\s*(\d+)\)\s*(.*?)\s*$", str(goal_text or ""), re.M):
        try:
            number = int(match.group(1))
        except ValueError:
            continue
        body = match.group(2).strip()
        if body:
            statements.append({"number": number, "body": body})
    return statements


def _sample_assignments(statements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    for statement in statements:
        body = str(statement.get("body") or "")
        if "<$" not in body:
            continue
        lhs, rhs = body.split("<$", 1)
        sample = lhs.strip().rstrip(";").split()[-1].strip()
        distribution = rhs.strip().rstrip(";").strip()
        if not sample or not distribution:
            continue
        samples.append(_drop_empty({
            "statement": statement.get("number"),
            "sample": sample,
            "distribution": distribution,
            "distribution_family": _sample_distribution_family(distribution),
            "expected_point_mass": _expected_point_mass_for_distribution(distribution),
        }))
    return samples


def _deterministic_assignments(statements: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    assignments: dict[str, dict[str, Any]] = {}
    for statement in statements:
        body = str(statement.get("body") or "")
        if "<-" not in body or "<$" in body or "<@" in body:
            continue
        lhs, rhs = body.split("<-", 1)
        target = lhs.strip().rstrip(";").split()[-1].strip()
        expr = rhs.strip().rstrip(";").strip()
        if target and expr:
            assignments[target] = {
                "statement": statement.get("number"),
                "target": target,
                "expr": expr,
            }
    return assignments


def _sample_factor_assignments(
    *,
    components: list[str],
    samples: list[dict[str, Any]],
    deterministic: dict[str, dict[str, Any]],
    factor_slots: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    assignments: list[dict[str, Any]] = []
    used_factors: set[str] = set()
    used_samples: set[str] = set()
    for component in components:
        expression = str(component or "").strip()
        defining = _dict(deterministic.get(expression))
        source_expr = str(defining.get("expr") or expression)
        for sample in samples:
            sample_name = str(sample.get("sample") or "")
            if not sample_name or sample_name in used_samples:
                continue
            if not _mentions_identifier(source_expr, sample_name):
                continue
            slot = _best_factor_slot_for_sample(
                sample=sample,
                factor_slots=factor_slots,
                used_factors=used_factors,
            )
            factor_id = str(slot.get("id") or "")
            if factor_id:
                used_factors.add(factor_id)
            used_samples.add(sample_name)
            assignments.append(_drop_empty({
                "component": component,
                "component_statement": defining.get("statement"),
                "component_definition": source_expr if defining else "",
                "sample": sample_name,
                "sample_statement": sample.get("statement"),
                "distribution": sample.get("distribution"),
                "distribution_family": sample.get("distribution_family"),
                "expected_point_mass": sample.get("expected_point_mass"),
                "candidate_factor_id": factor_id,
                "candidate_factor_expr": slot.get("expr"),
                "read_as": _sample_assignment_read_as(sample, slot),
            }))
    return assignments


def _mentions_identifier(text: str, name: str) -> bool:
    raw = str(text or "")
    token = re.escape(str(name or ""))
    return bool(re.search(rf"(?<![A-Za-z0-9_.'`]){token}(?![A-Za-z0-9_.'`])", raw))


def _sample_distribution_family(distribution: str) -> str:
    lower = str(distribution or "").lower()
    if "pred1" in lower:
        return "finite_uniform_except_one"
    if re.search(r"\bdt\b", lower):
        return "finite_uniform"
    return "sample_distribution"


def _expected_point_mass_for_distribution(distribution: str) -> str:
    family = _sample_distribution_family(distribution)
    if family == "finite_uniform_except_one":
        return "1%r / (order - 1)%r"
    if family == "finite_uniform":
        return "1%r / order%r"
    return ""


def _best_factor_slot_for_sample(
    *,
    sample: dict[str, Any],
    factor_slots: list[dict[str, Any]],
    used_factors: set[str],
) -> dict[str, Any]:
    family = str(sample.get("distribution_family") or "")
    def available(slot: dict[str, Any]) -> bool:
        return str(slot.get("id") or "") not in used_factors

    if family == "finite_uniform_except_one":
        for slot in factor_slots:
            expr = _normalize_expr(str(slot.get("expr") or ""))
            if available(slot) and ("order-1" in expr or "(order-1)" in expr):
                return slot
    if family == "finite_uniform":
        for slot in factor_slots:
            expr = _normalize_expr(str(slot.get("expr") or ""))
            if available(slot) and "order" in expr and "order-1" not in expr:
                return slot
    for slot in factor_slots:
        if available(slot) and str(slot.get("role") or "") == "finite_domain_point_mass":
            return slot
    return next((slot for slot in factor_slots if available(slot)), {})


def _sample_assignment_read_as(sample: dict[str, Any], slot: dict[str, Any]) -> str:
    family = str(sample.get("distribution_family") or "")
    factor = str(slot.get("expr") or "a point-mass factor")
    if family == "finite_uniform_except_one":
        return (
            f"`{sample.get('distribution')}` is a uniform-except-one sample; "
            f"it should pay an `1/(order-1)` point-mass obligation, matched to `{factor}`."
        )
    if family == "finite_uniform":
        return (
            f"`{sample.get('distribution')}` is a finite uniform sample; "
            f"it should pay an `1/order` point-mass obligation, matched to `{factor}`."
        )
    return f"Sample `{sample.get('sample')}` should be checked against `{factor}`."


def _factor_assignment_summary(assignments: list[dict[str, Any]]) -> str:
    if not assignments:
        return ""
    pieces = [
        f"{item.get('sample')} -> {item.get('candidate_factor_id') or '?'}"
        for item in assignments
        if item.get("sample")
    ]
    return "point-mass assignment: " + ", ".join(pieces)


def _parse_one_sided_seq_cut(tactic: str) -> dict[str, Any]:
    match = re.match(
        r"\s*seq\s+(?P<k>\d+)(?:\s+(?P<rhs>\d+))?\s*:\s*(?P<body>.+?)\.\s*$",
        str(tactic or ""),
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match or match.group("rhs"):
        return {}
    body, suffix = _split_tactic_suffix(match.group("body").strip())
    assertion, budget_arg = _split_seq_assertion_and_budget(body)
    return _drop_empty({
        "stmt_count": int(match.group("k")),
        "assertion": assertion,
        "budget_arg": budget_arg,
        "post_tactic_suffix": suffix,
    })


def _split_tactic_suffix(body: str) -> tuple[str, str]:
    payload = str(body or "").strip()
    depth = 0
    for idx, ch in enumerate(payload):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        elif ch == ";" and depth == 0:
            return payload[:idx].strip(), payload[idx:].strip()
    return payload, ""


def _split_seq_assertion_and_budget(body: str) -> tuple[str, str]:
    payload = str(body or "").strip()
    if not payload:
        return "", ""
    if payload.startswith("("):
        end = _matching_paren_index(payload, 0)
        if end >= 0:
            assertion = payload[: end + 1].strip()
            tail = payload[end + 1 :].strip()
            if tail.startswith(":"):
                tail = tail[1:].strip()
            return assertion, tail
    assertion, budget = _split_trailing_unit_budget(payload)
    if budget:
        return assertion, budget
    return payload, ""


def _split_trailing_unit_budget(payload: str) -> tuple[str, str]:
    raw = str(payload or "").strip()
    if not raw:
        return "", ""
    for suffix in ("(1%r)", "1%r"):
        if not raw.endswith(suffix):
            continue
        assertion = raw[: -len(suffix)].strip()
        if assertion:
            return assertion, suffix
    return raw, ""


def _matching_paren_index(text: str, start: int) -> int:
    return _matching_delimiter(text, start, "(", ")")


def _classify_seq_budget_arg(
    budget_arg: str,
    product_bound: str,
    *,
    assertion: str = "",
    goal_text: str = "",
    budget_shape: str = "",
    scale: str = "",
    source_probability: str = "",
) -> str:
    arg = _normalize_expr(budget_arg)
    bound = _normalize_expr(product_bound)
    side_fact = _looks_like_bound_side_text(assertion)
    matches_event = _seq_assertion_matches_current_event(
        assertion=assertion,
        goal_text=goal_text,
    )
    if budget_shape == "scaled_probability":
        scale_arg = _normalize_expr(scale)
        source_arg = _normalize_expr(source_probability)
        has_scale = bool(scale_arg and scale_arg in arg)
        has_source_probability = bool(source_arg and source_arg in arg)
        if not arg:
            return "missing_explicit_budget"
        if has_scale and has_source_probability:
            return "scaled_probability_seq_decomposition"
        if has_scale and not has_source_probability:
            return "scaled_probability_scale_only_likely_wrong_branch"
        if has_source_probability and not has_scale:
            return "scaled_probability_missing_scale"
        return "scaled_probability_missing_source_probability"
    if not arg:
        return "missing_explicit_budget"
    if arg == "1%r":
        if matches_event:
            return "unit_bound_event_preservation_candidate"
        if _extract_membership_event(assertion):
            return "bad_unit_seq_without_matching_event"
        return "unit_bound_likely_wrong_branch"
    if bound and arg == bound:
        if side_fact:
            return "product_budget_side_fact_candidate"
        return "product_budget_explicit_on_seq_suffix"
    if _looks_like_product_budget(budget_arg):
        if side_fact:
            return "product_budget_side_fact_candidate"
        return "explicit_product_budget_variant"
    return "non_product_explicit_budget"


def _seq_context_is_risky(item: Any) -> bool:
    if not isinstance(item, dict):
        return False
    classification = str(item.get("classification") or "")
    if classification in {
        "unit_bound_event_preservation_candidate",
        "scaled_probability_seq_decomposition",
    }:
        return False
    if classification in {
        "missing_explicit_budget",
        "unit_bound_likely_wrong_branch",
        "bad_unit_seq_without_matching_event",
        "product_budget_side_fact_candidate",
        "scaled_probability_scale_only_likely_wrong_branch",
        "scaled_probability_missing_source_probability",
    }:
        return True
    if (
        classification == "non_product_explicit_budget"
        and bool(item.get("assertion_is_side_condition"))
    ):
        return True
    if (
        classification == "non_product_explicit_budget"
        and _extract_membership_event(str(item.get("assertion_preview") or ""))
    ):
        return True
    return bool(
        item.get("assertion_is_side_condition")
        and item.get("current_post_is_side_residual")
        and classification != "product_budget_explicit_on_seq_suffix"
    )


def _seq_assertion_analysis(
    *,
    assertion: str,
    goal_text: str,
) -> dict[str, Any]:
    membership = _extract_membership_event(assertion)
    current = _current_membership_event(goal_text)
    kind = (
        "membership_event"
        if membership else
        "side_condition"
        if _looks_like_bound_side_text(assertion) else
        "unknown"
    )
    guard_text = _seq_assertion_guard_text(assertion)
    return _drop_empty({
        "assertion_kind": kind,
        "collection": membership.get("collection"),
        "matches_current_event": _membership_events_match(membership, current),
        "guard_facts": [guard_text] if guard_text else [],
    })


def _seq_assertion_matches_current_event(
    *,
    assertion: str,
    goal_text: str,
) -> bool:
    return _membership_events_match(
        _extract_membership_event(assertion),
        _current_membership_event(goal_text),
    )


def _current_membership_event(goal_text: str) -> dict[str, str]:
    event = _extract_event(goal_text)
    membership = _dict(event.get("membership"))
    if membership:
        return membership
    return _extract_membership_event(_extract_post_text(goal_text))


def _membership_events_match(
    candidate: dict[str, str],
    current: dict[str, str],
) -> bool:
    if not candidate or not current:
        return False
    candidate_collection = _normalize_collection_name(candidate.get("collection"))
    current_collection = _normalize_collection_name(current.get("collection"))
    if not candidate_collection or candidate_collection != current_collection:
        return False
    candidate_elem = _normalize_expr(candidate.get("element_preview"))
    current_elem = _normalize_expr(current.get("element_preview"))
    if not candidate_elem or not current_elem:
        return True
    return candidate_elem == current_elem or candidate_elem in current_elem or current_elem in candidate_elem


def _seq_assertion_guard_text(assertion: str) -> str:
    parts = _split_top_level_conjunction(assertion)
    event_parts = [part for part in parts if _extract_membership_event(part)]
    if not parts or len(event_parts) == len(parts):
        return ""
    guards = [part for part in parts if not _extract_membership_event(part)]
    return _collapse_ws(" /\\ ".join(guards))[:180]


def _probability_budget_bad_route_memory(
    route_events: list[dict[str, Any]],
    *,
    goal_text: str = "",
    product_bound: str = "",
    budget_shape: str = "",
    scale: str = "",
    source_probability: str = "",
) -> list[dict[str, str]]:
    routes: list[dict[str, str]] = []
    budget_label = (
        "scaled probability"
        if budget_shape == "scaled_probability" else
        "product"
    )
    for event in route_events:
        tactic = str(event.get("tactic") or "")
        lower = tactic.lower()
        accepted = _event_accepted(event)
        rejected = bool(event.get("rejected"))
        if accepted and _event_looks_like_sampling(event):
            routes = _append_anti_route(routes, {
                "route": f"remembered_local_sampling_under_{budget_label.replace(' ', '_')}_budget",
                "reason": (
                    f"This node already tried local sampling under the {budget_label} "
                    "budget; do not treat another accepted `rnd` as route "
                    "quality without a budget ledger."
                ),
            })
        if accepted and "phoare split" in lower:
            routes = _append_anti_route(routes, {
                "route": "remembered_phoare_split_under_product_budget",
                "reason": (
                    "This node already tried a `phoare split !` route; inspect "
                    "the residual bound direction before repeating that split."
                ),
            })
        if _event_looks_like_seq_cut(event) and accepted:
            parsed = _parse_one_sided_seq_cut(tactic)
            classification = _classify_seq_budget_arg(
                str(parsed.get("budget_arg") or ""),
                product_bound,
                assertion=str(parsed.get("assertion") or ""),
                goal_text=goal_text,
                budget_shape=budget_shape,
                scale=scale,
                source_probability=source_probability,
            )
            if classification in {
                "missing_explicit_budget",
                "unit_bound_likely_wrong_branch",
                "bad_unit_seq_without_matching_event",
                "product_budget_side_fact_candidate",
                "scaled_probability_scale_only_likely_wrong_branch",
                "scaled_probability_missing_source_probability",
            }:
                routes = _append_anti_route(routes, {
                    "route": f"remembered_{classification}",
                    "reason": (
                        "This node already saw an accepted `seq` shape whose "
                        "budget argument is likely the wrong ledger entry for "
                        "a product probability proof."
                    ),
                })
        if (accepted or rejected) and re.search(r"\bcall\s*\(\s*_:\s*true\s*\)\s*\.", lower):
            routes = _append_anti_route(routes, {
                "route": "remembered_direct_call_true_under_le_bound",
                "reason": (
                    "`call (_: true).` has already appeared on this node; under "
                    "`phoare [<=]` a hoare-style `call (_: PRE ==> POST).` is "
                    "often the compatible form."
                ),
            })
    return routes[:5]


def _extract_bound(text: str) -> dict[str, str]:
    normalized = _collapse_ws(text)

    phoare = re.search(
        r"Bound\s*:\s*(\[[^\]]+\])\s*(.+?)(?:\s+pre\s*=|\s+\(\s*1\s*\)|\s+post\s*=|$)",
        normalized,
        flags=re.IGNORECASE,
    )
    if phoare:
        return {
            "source": "phoare_bound",
            "relation": phoare.group(1).strip(),
            "bound": phoare.group(2).strip(),
        }

    pr = re.search(
        r"(?P<target>Pr\s*\[[^\]]+\])\s*(?P<relation><=|<|=)\s*(?P<bound>.+)$",
        normalized,
        flags=re.IGNORECASE,
    )
    if pr:
        return {
            "source": "single_program_probability_goal",
            "target_probability": pr.group("target").strip(),
            "relation": pr.group("relation").strip(),
            "bound": pr.group("bound").strip(),
        }
    return {}


def _extract_scaled_probability_equality(text: str) -> dict[str, Any]:
    """Detect top-level `Pr[...] = scale * Pr[...]` equalities.

    This intentionally ignores embedded phoare `Bound : [=] ...` goals; those
    are handled through `_extract_bound` so `pre`/`post` text stays available.
    """

    normalized = _collapse_ws(text)
    if not normalized or "Bound :" in normalized:
        return {}
    split = _split_top_level_equality(normalized)
    if not split:
        return {}
    lhs, rhs = split
    lhs_pr = _probability_terms(lhs)
    rhs_pr = _probability_terms(rhs)
    if len(lhs_pr) == 1 and _normalize_expr(lhs) == _normalize_expr(lhs_pr[0]):
        scaled = _extract_scaled_probability_product(rhs)
        if scaled:
            return _drop_empty({
                "source": "top_level_probability_equality",
                "relation": "=",
                "target_probability": lhs_pr[0],
                "bound": rhs,
                "bound_expression": rhs,
                **scaled,
            })
    if len(rhs_pr) == 1 and _normalize_expr(rhs) == _normalize_expr(rhs_pr[0]):
        scaled = _extract_scaled_probability_product(lhs)
        if scaled:
            return _drop_empty({
                "source": "top_level_probability_equality",
                "relation": "=",
                "target_probability": rhs_pr[0],
                "bound": lhs,
                "bound_expression": lhs,
                **scaled,
            })
    return {}


def _extract_scaled_probability_product(expr: str) -> dict[str, Any]:
    terms = _split_top_level_product_terms(expr)
    if len(terms) < 2:
        return {}
    probability_terms = [
        term for term in terms
        if _is_probability_term(term)
    ]
    if len(probability_terms) != 1:
        return {}
    source_probability = probability_terms[0]
    scale_factors = [
        term for term in terms
        if term != source_probability
    ]
    if not scale_factors:
        return {}
    scale = " * ".join(scale_factors)
    if not _looks_like_scale_budget(scale):
        return {}
    return _drop_empty({
        "source_probability": source_probability,
        "scale": scale,
        "scale_factors": scale_factors,
        "bound_expression": _collapse_ws(expr),
    })


def _split_top_level_equality(text: str) -> tuple[str, str] | None:
    paren_depth = 0
    bracket_depth = 0
    raw = str(text or "")
    for idx, ch in enumerate(raw):
        if ch == "(":
            paren_depth += 1
        elif ch == ")":
            paren_depth = max(0, paren_depth - 1)
        elif ch == "[":
            bracket_depth += 1
        elif ch == "]":
            bracket_depth = max(0, bracket_depth - 1)
        elif ch == "=" and paren_depth == 0 and bracket_depth == 0:
            prev_ch = raw[idx - 1] if idx > 0 else ""
            next_ch = raw[idx + 1] if idx + 1 < len(raw) else ""
            if prev_ch in "<>[" or next_ch in "=>":
                continue
            lhs = raw[:idx].strip()
            rhs = raw[idx + 1:].strip()
            if lhs and rhs:
                return lhs, rhs
    return None


def _split_top_level_product_terms(expr: str) -> list[str]:
    terms: list[str] = []
    raw = str(expr or "").strip()
    start = 0
    paren_depth = 0
    bracket_depth = 0
    for idx, ch in enumerate(raw):
        if ch == "(":
            paren_depth += 1
        elif ch == ")":
            paren_depth = max(0, paren_depth - 1)
        elif ch == "[":
            bracket_depth += 1
        elif ch == "]":
            bracket_depth = max(0, bracket_depth - 1)
        elif ch == "*" and paren_depth == 0 and bracket_depth == 0:
            terms.append(_strip_outer_parens(raw[start:idx].strip()))
            start = idx + 1
    terms.append(_strip_outer_parens(raw[start:].strip()))
    return [term for term in terms if term]


def _probability_terms(text: str) -> list[str]:
    return [
        str(item.get("pr_text") or "").strip()
        for item in parse_pr_terms(text, require_endpoint=False)
        if str(item.get("pr_text") or "").strip()
    ]


def _is_probability_term(text: str) -> bool:
    terms = _probability_terms(text)
    return len(terms) == 1 and _normalize_expr(text) == _normalize_expr(terms[0])


def _looks_like_scale_budget(scale: str) -> bool:
    normalized = _normalize_expr(scale)
    if normalized in {"", "1", "1%r"}:
        return False
    if "Pr[" in scale:
        return False
    return "/" in scale or "%r" in scale or "inv" in normalized


def _event_from_probability_term(term: str) -> dict[str, Any]:
    parsed = parse_pr_terms(term, require_endpoint=False)
    if parsed:
        event_text = _collapse_ws(parsed[0].get("event"))
        if event_text:
            membership = _extract_membership_event(event_text)
            return _drop_empty({
                "text": event_text[:240],
                "kind": _event_kind(event_text),
                "membership": membership,
                "mentions": _interesting_event_tokens(event_text),
            })
    match = re.match(r"Pr\s*\[[^:\]]+:\s*(?P<event>.+)\]\s*$", str(term or ""), re.DOTALL)
    if not match:
        return {}
    event_text = _collapse_ws(match.group("event"))
    if not event_text:
        return {}
    membership = _extract_membership_event(event_text)
    return _drop_empty({
        "text": event_text[:240],
        "kind": _event_kind(event_text),
        "membership": membership,
        "mentions": _interesting_event_tokens(event_text),
    })


def _extract_event(text: str) -> dict[str, Any]:
    normalized = _collapse_ws(text)
    pr_match = re.search(
        r"Pr\s*\[[^:\]]+:\s*(.+?)\]\s*(?:<=|<|=)",
        normalized,
        flags=re.IGNORECASE,
    )
    event_text = ""
    if pr_match:
        event_text = pr_match.group(1).strip()
    else:
        post_match = re.search(
            r"\bpost\s*=\s*(.+)$",
            normalized,
            flags=re.IGNORECASE,
        )
        if post_match:
            event_text = post_match.group(1).strip()

    if not event_text:
        return {}
    membership = _extract_membership_event(event_text)
    return _drop_empty({
        "text": event_text[:240],
        "kind": _event_kind(event_text),
        "membership": membership,
        "mentions": _interesting_event_tokens(event_text),
    })


def _event_bound_bridge_for_goal(
    goal_text: str,
    event: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(event, dict) or event.get("kind") != "membership_event":
        return {}
    membership = _dict(event.get("membership"))
    collection = str(membership.get("collection") or "").strip()
    if not collection:
        return {}
    size_bound = _extract_size_bound_for_collection(goal_text, collection)
    if not size_bound:
        return {}

    return _drop_empty({
        "kind": "list_membership_probability_bound",
        "event_collection": collection,
        "event_expression": membership.get("element_preview"),
        "size_bound": size_bound,
        "candidate_lemma_handles": [
            {
                "symbol": "mu_mem_le_mu1_size",
                "why": (
                    "`size L <= n` plus a per-point mass bound can turn "
                    "`mu dt (mem L)` into `n%r * r`."
                ),
            }
        ],
        "route_shape": [
            "Keep the product budget at the event level before committing local sampling cleanup.",
            "Use the visible list-size bound to reduce membership in the list to a size times point-mass bound.",
            "Prove the per-point mass bound from the sampled distributions and support exclusions.",
            "Only then descend into local sampling obligations if the per-point subgoal is explicit.",
        ],
        "per_point_budget_hint": _per_point_budget_hint(goal_text, size_bound),
        "anti_route": (
            "Do not treat a privately accepted multi-`rnd` preflight as proof-route quality "
            "unless it exposes the per-point membership bound required by the list-size lemma."
        ),
        "read_as": (
            "A bridge for membership events: the list-size fact caps how many "
            "targets can be hit, and the per-point mass bound pays for one target."
        ),
    })


def _extract_membership_event(event_text: str) -> dict[str, str]:
    raw = str(event_text or "")
    map_match = re.search(
        r"(?P<left>.+?)\\in\s+map\s+\(.+?\)\s+(?P<right>[A-Za-z_][A-Za-z0-9_.'`]*)",
        raw,
        flags=re.DOTALL,
    )
    if map_match:
        return _drop_empty({
            "collection": map_match.group("right").strip(),
            "mapped_collection": f"map (...) {map_match.group('right').strip()}",
            "element_preview": _collapse_ws(map_match.group("left"))[-180:],
        })
    matches = list(re.finditer(
        r"(?P<left>.+?)\\in\s+(?P<right>[A-Za-z_][A-Za-z0-9_.'`]*)",
        raw,
        flags=re.DOTALL,
    ))
    if not matches:
        matches = list(re.finditer(
            r"(?P<left>.+?)\bin\s+(?P<right>[A-Za-z_][A-Za-z0-9_.'`]*)",
            raw,
            flags=re.IGNORECASE | re.DOTALL,
        ))
    if not matches:
        return {}
    match = matches[-1]
    return _drop_empty({
        "collection": match.group("right").strip(),
        "element_preview": _collapse_ws(match.group("left"))[-180:],
    })


def _extract_size_bound_for_collection(goal_text: str, collection: str) -> dict[str, str]:
    target = _normalize_collection_name(collection)
    if not target:
        return {}
    normalized = _collapse_ws(goal_text)
    for match in re.finditer(
        r"\bsize\s+(?P<collection>[A-Za-z_][A-Za-z0-9_.'`]*(?:\{[^}]+\})?)\s*<=\s*(?P<bound>[A-Za-z_][A-Za-z0-9_.'`]*(?:\{[^}]+\})?|\d+)",
        normalized,
    ):
        seen = _normalize_collection_name(match.group("collection"))
        if seen != target:
            continue
        collection_text = match.group("collection").strip()
        bound_text = match.group("bound").strip()
        return {
            "collection": collection_text,
            "upper_bound": bound_text,
            "fact": f"size {collection_text} <= {bound_text}",
        }
    return {}


def _normalize_collection_name(text: str) -> str:
    return re.sub(r"\{[^}]+\}", "", str(text or "").strip())


def _per_point_budget_hint(goal_text: str, size_bound: dict[str, str]) -> str:
    bound_info = _extract_bound(goal_text)
    bound = str(bound_info.get("bound") or "")
    upper = str(size_bound.get("upper_bound") or "")
    if not bound or not upper:
        return ""
    return (
        f"After applying the list-size bridge with `{upper}`, prove a per-point "
        f"mass bound whose product with `{upper}%r` is no larger than `{bound}`."
    )


def _event_kind(event_text: str) -> str:
    lower = event_text.lower()
    if r"\in" in event_text or " in " in lower:
        return "membership_event"
    if any(token in lower for token in ("bad", "win", "forge", "collision")):
        return "bad_or_win_event"
    if "res" in lower:
        return "result_event"
    return "event"


def _interesting_event_tokens(event_text: str) -> list[str]:
    out: list[str] = []
    for token in re.findall(r"\b[A-Za-z_][A-Za-z0-9_.'`]*\b", event_text):
        if token in {"in", "true", "false", "res", "Some", "None"}:
            continue
        if "." in token or token[:1].isupper():
            out.append(token)
    return _dedupe_strings(out)[:8]


def _looks_like_product_budget(bound: str) -> bool:
    compact = _collapse_ws(bound)
    if "*" not in compact:
        return False
    ratio_count = compact.count("/")
    has_power = "^" in compact
    percent_reals = "%r" in compact
    return ratio_count >= 1 and (has_power or ratio_count >= 2 or percent_reals)


def _fact_handles_for_bound(bound: str, event: dict[str, Any]) -> list[dict[str, str]]:
    handles: list[dict[str, str]] = [
        {
            "symbol": "mulr_ge0",
            "why": "Product-bound side conditions often need non-negativity of factors.",
        },
        {
            "symbol": "divr_ge0",
            "why": "Ratio factors in the bound usually need numerator/denominator non-negativity.",
        },
        {
            "symbol": "expr_ge0",
            "why": "Powered ratio factors often need exponent non-negativity closure.",
        },
        {
            "symbol": "mulr_gt0",
            "why": "Strict positivity is useful when rewriting ratio-over-itself side conditions.",
        },
        {
            "symbol": "divr_gt0",
            "why": "Strictly positive denominator/numerator facts support positive ratio factors.",
        },
        {
            "symbol": "expr_gt0",
            "why": "Powered positive ratio factors stay positive.",
        },
        {
            "symbol": "divrr",
            "why": "B/B residuals often close by rewriting `divrr` after proving B is nonzero.",
        },
    ]
    if "PKE_.qD" in bound:
        handles.insert(0, {
            "symbol": "PKE_.qD_pos",
            "why": "The query-bound numerator appears in the probability budget.",
        })
    if "order" in bound:
        handles.insert(0, {
            "symbol": "gt1_q",
            "why": "The group order denominator appears in the probability budget.",
        })
    if event.get("kind") == "membership_event":
        handles.append({
            "symbol": "mu_mem_le_mu1_size",
            "why": (
                "Membership-event probability bounds often use list-size or "
                "union-bound style lemmas when available."
            ),
        })
    return _dedupe_fact_handles(handles)[:10]


def _anti_routes_for_shape(text: str, bound_info: dict[str, str]) -> list[dict[str, str]]:
    anti_routes = [
        {
            "route": "single_rnd_for_whole_product_budget",
            "reason": (
                "A single accepted `rnd` step, or a compact `do N!rnd`, may "
                "leave a subgoal that charges local samples against the entire "
                "product budget."
            ),
        },
        {
            "route": "accepted_phoare_split_as_route_quality",
            "reason": (
                "EasyCrypt may accept `phoare split !`, but the residual goals "
                "can still be a bad route under a product budget."
            ),
        },
        {
            "route": "seq_cut_allocates_product_budget_to_prefix",
            "reason": (
                "A plausible `seq K : side_fact` can move the small product "
                "budget onto a high-probability prefix or deterministic side "
                "condition."
            ),
        },
    ]
    lower = text.lower()
    if "bound   : [<=] 1%r" in lower or bound_info.get("relation") == "[<=]":
        anti_routes.append({
            "route": "direct_call_true_under_le_bound",
            "reason": (
                "Direct `call (_: true).` under a one-sided `[<=]` bound can "
                "fail because EasyCrypt expects a compatible bound direction."
            ),
        })
    return anti_routes


def _event_tactic_head(event: dict[str, Any]) -> str:
    head = str(event.get("tactic_head") or "").lower()
    if head:
        return head
    tactic = str(event.get("tactic") or "").strip().lower()
    return re.split(r"[\s{.]", tactic, maxsplit=1)[0] if tactic else ""


def _event_looks_like_sampling(event: dict[str, Any]) -> bool:
    head = _event_tactic_head(event)
    if head == "rnd":
        return True
    tactic = str(event.get("tactic") or "").lower()
    return bool(
        re.search(r"(?:^|[;.\s!])rnd(?:\b|\{|\s|\.|;)", tactic)
        or re.search(r"\bdo\s+\d+\s*!\s*rnd\b", tactic)
    )


def _event_looks_like_seq_cut(event: dict[str, Any]) -> bool:
    head = _event_tactic_head(event)
    if head == "seq":
        return True
    tactic = str(event.get("tactic") or "").lower()
    return bool(re.match(r"\s*seq\s+\d+\b", tactic))


def _event_accepted(event: dict[str, Any]) -> bool:
    status = str(event.get("status") or "").lower()
    return (
        bool(event.get("accepted"))
        or status in {"accepted", "preflight_accepted", "ok"}
    )


def _post_looks_like_bound_side_residual(text: str) -> bool:
    post = _extract_post_text(text).lower()
    if not post:
        return False
    return _looks_like_bound_side_text(post)


def _looks_like_bound_side_text(text: str) -> bool:
    lower = str(text or "").lower()
    eventful = any(
        token in lower
        for token in (r"\in", " bad", "win", "forge", "collision", "res")
    )
    side_conditionish = (
        "size " in lower
        or " <= " in lower
        or " < " in lower
        or "<=" in lower
        or "<>" in lower
        or "!=" in lower
        or "forall" in lower
        or bool(re.search(r"\b[A-Za-z_][A-Za-z0-9_.']*\s*=\s*", lower))
    )
    return side_conditionish and not eventful


def _extract_post_text(text: str) -> str:
    match = re.search(
        r"\bpost\s*=\s*(.+)$",
        _collapse_ws(text),
        flags=re.IGNORECASE,
    )
    return match.group(1).strip() if match else ""


def _has_one_sided_le_one_bound(text: str) -> bool:
    return bool(re.search(
        r"\bBound\s*:\s*\[<=\]\s*1%r\b",
        str(text or ""),
        flags=re.IGNORECASE,
    ))


def _has_visible_call_frontier(text: str) -> bool:
    raw = str(text or "")
    lower = raw.lower()
    return (
        "<@" in raw
        or "abstract call" in lower
        or "call frontier" in lower
        or bool(re.search(r"\b[A-Za-z_][A-Za-z0-9_.'`]*\.main\s*\(", raw))
    )


def _recent_product_bound_from_phoare_split(
    events: list[dict[str, Any]],
) -> str:
    for event in reversed(events):
        tactic = str(event.get("tactic") or "")
        if "phoare split" not in tactic.lower():
            continue
        tail = re.sub(
            r"^.*?\bphoare\s+split\s+!\s*",
            "",
            tactic,
            flags=re.IGNORECASE | re.DOTALL,
        ).strip().rstrip(".")
        if _looks_like_product_budget(tail):
            return tail
    return ""


def _post_split_budget_context(bound: str) -> dict[str, Any]:
    factors = _split_top_level_product_terms(bound)
    bound_info = {
        "source": "post_split_phoare_residual",
        "relation": "[<=]",
        "bound": bound,
    }
    event: dict[str, Any] = {}
    budget_ledger = _build_budget_ledger(
        goal_text="Bound : [<=] 1%r",
        bound_info=bound_info,
        event=event,
        event_bound_bridge={},
        factors=factors,
    )
    return _drop_empty({
        "kind": "probability_budget",
        "budget_shape": "product_bound",
        "source": "post_split_phoare_residual",
        "bound_relation": "[<=]",
        "bound": bound,
        "factors": factors,
        "budget_ledger": budget_ledger,
        "useful_fact_handles": _fact_handles_for_bound(bound, {}),
    })


def _normalize_expr(text: str) -> str:
    return re.sub(r"\s+", "", _strip_outer_parens(str(text or "").strip().rstrip(".")))


def _dedupe_fact_handles(items: list[dict[str, str]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in items:
        symbol = str(item.get("symbol") or "")
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        out.append(item)
    return out


def _append_anti_route(
    items: list[dict[str, str]],
    item: dict[str, str],
) -> list[dict[str, str]]:
    route = str(item.get("route") or "")
    if not route:
        return items
    if any(str(existing.get("route") or "") == route for existing in items):
        return items
    return [*items, item]
