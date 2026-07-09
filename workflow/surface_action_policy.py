"""Panel-level action policy for the typed surface contract.

Protocol validity is owned by ``context_intents``.  Profile visibility is owned
by ``surface_profiles``.  State eligibility is owned by
``surface_action_eligibility``.  This module owns the stable panel policy:
which intent families a panel is allowed to expose before state filtering.
"""
from __future__ import annotations


PANEL_INTENTS: dict[str, frozenset[str]] = {
    "recovery": frozenset({
        "operator_lemmas",
        "rewrite_candidates",
        "pr_bridge_routes",
        "verified_pivot_options",
        "call_invariant_skeleton",
        "equiv_bridge_lemmas",
        "lemma_hints",
        "subgoal_gap",
        "inv_from_lemma",
        "bridge_probe",
        "tactic_forms",
        "call_site_options",
        "call_subgoals",
        "proof_frontier",
        "align",
    }),
    "call_site": frozenset({
        "call_site_options",
        "call_subgoals",
        "call_invariant_skeleton",
        "inv_from_lemma",
        "subgoal_gap",
        "tactic_forms",
    }),
    "pure_logic": frozenset({
        "operator_lemmas",
        "rewrite_candidates",
        "equiv_bridge_lemmas",
        "lemma_hints",
        "subgoal_gap",
        "inv_from_lemma",
        "tactic_forms",
    }),
    "opener": frozenset({
        "operator_lemmas",
        "pr_bridge_routes",
        "verified_pivot_options",
        "rewrite_candidates",
        "equiv_bridge_lemmas",
        "lemma_hints",
        "subgoal_gap",
        "bridge_probe",
        "tactic_forms",
    }),
    "deep_surgery": frozenset({
        "proof_frontier",
        "align",
        "rewrite_candidates",
        "call_invariant_skeleton",
        "equiv_bridge_lemmas",
        "lemma_hints",
        "subgoal_gap",
        "inv_from_lemma",
        "tactic_forms",
    }),
}


def panel_allowed_intents(panel_id: str) -> frozenset[str] | None:
    return PANEL_INTENTS.get(panel_id)
