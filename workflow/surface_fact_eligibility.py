"""Admission and generic safety rules for canonical panel facts.

Phase analyzers produce mechanical evidence and panel adapters select the facts
that constitute one panel.  This module is the single registry for the allowed
fact keys and their presentation metadata.  Its runtime filtering is deliberately
generic: audit-only, empty, unregistered, or uncertified-gap facts are rejected.
It must not re-implement phase semantics or choose proof strategy.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from workflow.surface_model import PanelFact


@dataclass(frozen=True)
class FactEligibilityResult:
    eligible: bool
    reason: str = ""
    authority: str = ""
    state_scope: str = ""
    novelty: str = ""
    actionability: str = ""
    semantic_boundary: str = "mechanical"


@dataclass(frozen=True)
class PanelFactContract:
    """Admission metadata for one fact key in one panel.

    Panel adapters choose facts and supply their provenance. This registry is
    the only owner of whether a produced key belongs on a particular panel and
    how actionable that class of fact is. Unknown keys fail validation before
    filtering, so a new producer fact cannot disappear silently.
    """

    actionability: str = "medium"
    semantic_boundary: str = "mechanical"


_SPECULATIVE_GAP_KEYS = frozenset({"alignment_gaps", "gap_analysis"})


def _contracts(
    keys: set[str],
    *,
    high: set[str] | None = None,
    low: set[str] | None = None,
) -> dict[str, PanelFactContract]:
    high = high or set()
    low = low or set()
    return {
        key: PanelFactContract(
            actionability=(
                "high" if key in high else "low" if key in low else "medium"
            ),
        )
        for key in keys
    }


PANEL_FACT_CONTRACTS: dict[str, dict[str, PanelFactContract]] = {
    "single_program": _contracts({
        "setup_before_frontier",
        "current_frontier",
        "program_obligation",
        "one_sided_losslessness_certificates",
        "bounded_lookahead",
        "active_seq_scope",
        "loaded_named_routes",
    }, high={
        "current_frontier",
        "program_obligation",
        "one_sided_losslessness_certificates",
        "bounded_lookahead",
        "loaded_named_routes",
    }),
    "relational_program": _contracts({
        "loaded_named_routes",
        "procedure_body_entry",
    }, high={"loaded_named_routes", "procedure_body_entry"}),
    "recovery": _contracts({
        "rejected_tactic",
        "automation_residual_failure",
        "current_frontier_head",
        "applicable_tactic_families",
        "non_applicable_reason",
        "compact_fallback",
        "close_with",
        "available_rewind_targets",
        "procedure_body_entry",
    }, high={"procedure_body_entry"}),
    "call_site": _contracts({
        "direct_current_call",
        "blocked_named_handles",
        "near_frontier_bridge",
        "frontier_blockers",
        "named_call_templates",
        "module_aliases",
        "abstract_adversary_glob",
        "inline_preview",
        "frontier_scope",
        "frame_required_later",
        "up_to_bad_call_compatibility",
        "one_sided_losslessness_certificates",
    }, high={
        "direct_current_call",
        "blocked_named_handles",
        "near_frontier_bridge",
        "named_call_templates",
        "module_aliases",
        "up_to_bad_call_compatibility",
        "one_sided_losslessness_certificates",
    }),
    "pure_logic": _contracts({
        "inductive_intro_routes",
        "distribution_certificates",
        "mechanical_goal_candidates",
        "local_hypothesis_graph",
        "iter_successor_shape",
        "integer_arithmetic_split_candidates",
        "integer_arithmetic_b2i_guards",
        "integer_arithmetic_lemma_families",
        "list_normalization_routes",
        "map_update_transport",
        "local_lemmas",
        "alignment_gaps",
        "gap_analysis",
        "membership_sources",
        "map_update_lookup_cases",
        "existential_witness_candidates",
    }, high={
        "inductive_intro_routes",
        "distribution_certificates",
        "mechanical_goal_candidates",
        "local_hypothesis_graph",
        "iter_successor_shape",
        "integer_arithmetic_split_candidates",
        "integer_arithmetic_lemma_families",
        "list_normalization_routes",
        "map_update_transport",
    }),
    "opener": _contracts({
        "verified_pr_bridge_routes",
        "pr_endpoint_matches",
        "pr_bound_routes",
        "mechanical_goal_candidates",
        "loaded_named_routes",
        "probability_structure",
        "tactic_affordances",
        "unfoldable_goal_heads",
    }, high={
        "verified_pr_bridge_routes",
        "pr_endpoint_matches",
        "pr_bound_routes",
        "mechanical_goal_candidates",
        "loaded_named_routes",
    }, low={"tactic_affordances"}),
    "deep_surgery": _contracts({
        "seq_scope",
        "obligation_shape",
        "residual_frontier_after_cut",
        "branch_focus",
        "whole_program_structure",
        "where",
        "branch_sample_alignment",
        "lookahead_after_frontier",
        "split_points",
        "swap_offsets",
        "near_frontier_bridge",
        "up_to_bad_call_compatibility",
        "program_frontier",
        "loaded_named_routes",
        "one_sided_losslessness_certificates",
    }, high={
        "whole_program_structure",
        "near_frontier_bridge",
        "up_to_bad_call_compatibility",
        "loaded_named_routes",
        "one_sided_losslessness_certificates",
    }),
}


def validate_surface_fact_contract(
    panel_id: str,
    facts: tuple[PanelFact, ...] | list[PanelFact],
) -> None:
    """Fail on producer/contract drift instead of silently hiding facts."""
    admitted = PANEL_FACT_CONTRACTS.get(panel_id, {})
    unknown = sorted({
        fact.key
        for fact in facts or ()
        if fact.role != "audit_only"
        and fact.kind != "audit_fact"
        and fact.key not in admitted
    })
    if unknown:
        raise ValueError(
            f"surface fact contract drift for {panel_id}: "
            + ", ".join(unknown)
        )


def filter_surface_facts(
    view: dict[str, Any],
    panel_id: str,
    facts: tuple[PanelFact, ...] | list[PanelFact],
) -> list[PanelFact]:
    out: list[PanelFact] = []
    for fact in facts or ():
        result = fact_eligibility(view, panel_id, fact)
        if not result.eligible:
            continue
        out.append(replace(
            fact,
            authority=fact.authority or result.authority,
            state_scope=fact.state_scope or result.state_scope,
            novelty=fact.novelty or result.novelty,
            actionability=fact.actionability or result.actionability,
            semantic_boundary=fact.semantic_boundary or result.semantic_boundary,
            eligibility_reason=fact.eligibility_reason or result.reason,
        ))
    return out


def fact_eligibility(
    view: dict[str, Any],
    panel_id: str,
    fact: PanelFact,
) -> FactEligibilityResult:
    if fact.role == "audit_only" or fact.kind == "audit_fact":
        return FactEligibilityResult(False, "audit evidence is not a normal surface fact")
    if fact.value in (None, "", [], {}, ()):
        return FactEligibilityResult(False, "fact has no displayable value")
    contract = PANEL_FACT_CONTRACTS.get(panel_id, {}).get(fact.key)
    if contract is None:
        return FactEligibilityResult(
            False,
            "fact key is not admitted by this panel's presentation contract",
        )
    if fact.key in _SPECULATIVE_GAP_KEYS and not _gap_is_verified(fact.value):
        return FactEligibilityResult(
            False,
            "uncertified gap inference stays in audit data",
        )

    authority = _authority(fact)
    novelty = _novelty(fact)
    return FactEligibilityResult(
        True,
        "non-empty mechanical fact is relevant to the current panel",
        authority=authority,
        state_scope=f"current_{panel_id}",
        novelty=novelty,
        actionability=contract.actionability,
        semantic_boundary=contract.semantic_boundary,
    )


def _authority(fact: PanelFact) -> str:
    refs = " ".join(fact.source_refs)
    if fact.kind in {"manager_result", "last_result"}:
        return "manager_result"
    if (
        "program_frontier" in refs
        or "call_site_surface" in refs
        or "candidate_moves.moves" in refs
    ):
        return "proof_state_analysis"
    if "application_context.up_to_bad_call" in refs:
        return "derived_mechanical_analysis"
    if "pure_tail_surface" in refs:
        return "goal_analysis"
    return "workspace_fact"


def _novelty(fact: PanelFact) -> str:
    refs = set(fact.source_refs)
    if refs and all(ref.startswith("current_goal") for ref in refs):
        return "goal_derived"
    if any(
        "call_site_surface" in ref
        or "program_frontier" in ref
        or "candidate_moves" in ref
        for ref in refs
    ):
        return "cross_context"
    return "derived"


def _gap_is_verified(value: Any) -> bool:
    items = value if isinstance(value, list) else [value]
    for item in items:
        if not isinstance(item, dict):
            continue
        authority = str(item.get("authority") or item.get("verification_status") or "").lower()
        if any(marker in authority for marker in ("verified", "proof-state", "compiler")):
            return True
    return False
