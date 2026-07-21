"""Surface profiles for the paper proof-state compiler interface.

The profiles in this module are intentionally about the agent-facing surface,
not EasyCrypt semantics.  EasyCrypt remains the verifier in every managed
profile; the profile only controls which compiled proof-state resources are
visible and which manager intents are fair game for that surface.

Paper-facing profiles use the L1-L4 compiler-pass names.

Keep this axis separate from tree/search topology.  A surface profile says
what the agent can see and ask the manager to do; orchestrator/tree policy says
how many proof nodes exist and how they race.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
import re
from typing import Any

from workflow.view_neutrality import view_neutrality_strict
from workflow.context_intents import (
    CONTEXT_TOPIC_INTENTS,
    MANAGER_INTENTS,
    intent_spec,
    is_context_topic_intent,
    normalize_context_topic,
)


ALL_MANAGER_INTENTS = MANAGER_INTENTS

CONTROL_INTENTS = frozenset({
    "commit_tactic",
    "undo_last_step",
    "undo_to_checkpoint",
    "fresh_restart",
    "amend_and_replay",
    "finish",
})

# L1 now offers the SAME action capabilities as L4 (commit / undo_last_step /
# undo_to_checkpoint / fresh_restart / amend_and_replay / finish) so the L1<->L4
# comparison isolates the DERIVED panel content, not capabilities. The rewind intents
# both reference a committed step BY INDEX off the `proof_so_far` panel L1 now renders,
# so L1 needs no checkpoint menu (which would carry route-health content). L1 still
# lacks direct context-topic intents / `lookup_symbol` — the content-retrieval
# channels that ARE the panel's value under study.
GOAL_ONLY_CONTROL_INTENTS = CONTROL_INTENTS

BASIC_INSPECT_TOPICS = frozenset({
    "diagnose",
    "tactic_forms",
})

SIGNPOST_INSPECT_TOPICS = frozenset({
    "diagnose",
    "tactic_forms",
    "align",
    # On-demand structural rewind menu. Offered wherever `undo_to_checkpoint`
    # is an allowed intent (L2+), so an agent that diagnoses an upstream-cut
    # defect can DISCOVER the checkpoint targets to rewind to — not only in the
    # failure-recovery focus. Factual (the committed proof's own structure), so
    # it survives view_neutrality_strict (NOT in _HEURISTIC_INSPECT_TOPICS).
    "checkpoints",
})

PREVIEW_INSPECT_TOPICS = frozenset({
    "diagnose",
    "tactic_forms",
    "align",
    "call_subgoals",
    "checkpoints",  # on-demand structural rewind menu (see SIGNPOST note)
})

UPGRADED_NAVIGATOR_INSPECT_TOPICS = PREVIEW_INSPECT_TOPICS | frozenset({
    "pr_bridge_routes",
    "equiv_bridge_lemmas",
    "bridge_options",   # back-compat alias for pr_bridge_routes
    "bridge_lemmas",    # back-compat alias for equiv_bridge_lemmas
    "call_site_options",
    "call_invariant_skeleton",
    "inv_from_lemma",
    "lemma_hints",
    "operator_lemmas",  # live EC `search OP.` over the loaded ctx -> applicable lemmas (project-local incl.)
    "probability_budget_ledger",
    "proof_frontier",
    "rewrite_candidates",
    "subgoal_gap",
})


# Inspect topics that are heuristic guesses (relevance-ranked hints, the
# probability budget ledger, un-verified equiv
# bridge candidates). Removed from the offered set under view_neutrality_strict;
# the factual / daemon-verified topics (align, call_subgoals,
# pr_bridge_routes, inv_from_lemma,
# rewrite_candidates, subgoal_gap, proof_frontier, ...) stay. See
# docs/design/compiler_view_boundary.md.
_HEURISTIC_INSPECT_TOPICS = frozenset({
    "lemma_hints",
    "probability_budget_ledger",
    "call_invariant_skeleton",
    "equiv_bridge_lemmas",
    "bridge_lemmas",  # back-compat alias of equiv_bridge_lemmas
})



def effective_inspect_topics(
    profile: "SurfaceProfile | None",
) -> "frozenset[str] | None":
    """Inspect topics actually offered for a profile.

    Under view_neutrality_strict the heuristic topics (`_HEURISTIC_INSPECT_TOPICS`)
    are removed, so the agent is neither offered them nor allowed to request them;
    the factual / daemon-verified topics remain. Used by both the intent gate
    (`surface_profile_allows_intent`) and the rendered topic menu so the two agree.
    """
    topics = getattr(profile, "allowed_inspect_topics", None)
    if topics is None:
        return None
    if view_neutrality_strict():
        topics = frozenset(topics) - _HEURISTIC_INSPECT_TOPICS
    else:
        topics = frozenset(topics)
    return topics


@dataclass(frozen=True)
class SurfaceProfile:
    """One agent-facing proof-state surface profile."""

    name: str
    stage: str
    description: str
    allowed_intents: frozenset[str]
    allowed_inspect_topics: frozenset[str] | None = None
    supported: bool = True
    paper_level: str | None = None
    paper_role: str = "paper"
    # --- adaptive mode (default cheap surface, escalate to a richer one on stuck) ---
    # ``escalate_to`` names the profile this one upgrades to once the agent gets
    # stuck (reaches for a richer intent, or accumulates errors). ``schema_intents``
    # is the intent set advertised in the MCP tool schema (a SUPERSET of
    # ``allowed_intents``): the agent can SEE the richer levers from turn 1, but
    # the manager only ACCEPTS them once escalated. Both None for static profiles.
    escalate_to: str | None = None
    schema_intents: frozenset[str] | None = None


SURFACE_PROFILE_REGISTRY: dict[str, SurfaceProfile] = {
    "raw_cli": SurfaceProfile(
        name="raw_cli",
        stage="raw_cli",
        description=(
            "Planned direct EasyCrypt baseline: raw goal/error feedback and "
            "raw try/next/prev/start controls, without ProverWorkspaceView."
        ),
        allowed_intents=frozenset(),
        supported=False,
        paper_level="raw",
        paper_role="planned",
    ),
    "l1_goal_projection": SurfaceProfile(
        name="l1_goal_projection",
        stage="l1_goal_projection",
        description=(
            "L1 Goal-State Projection: manager transport of ONLY the current "
            "goal. No status, no manager-result section, no focus — the agent "
            "sees the raw goal and nothing else (the node-memory recovery anchor "
            "and the one-line submit-intent reminder are the only scaffolding)."
        ),
        allowed_intents=GOAL_ONLY_CONTROL_INTENTS,
        allowed_inspect_topics=frozenset(),
        paper_level="L1",
    ),
    "l2_semantic_ir": SurfaceProfile(
        name="l2_semantic_ir",
        stage="l2_semantic_ir",
        description=(
            "L2 Semantic Proof-State IR: goal plus proof layer, program "
            "frontier, live handles, diagnostics, and basic read-only "
            "inspections, but no flow-sensitive navigator."
        ),
        allowed_intents=CONTROL_INTENTS | SIGNPOST_INSPECT_TOPICS | frozenset({"lookup_symbol"}),
        allowed_inspect_topics=SIGNPOST_INSPECT_TOPICS,
        paper_level="L2",
    ),
    "l3_flow_navigation": SurfaceProfile(
        name="l3_flow_navigation",
        stage="l3_flow_navigation",
        description=(
            "L3 Flow-Sensitive Navigation: adds route hypotheses, phase-door "
            "recommendations, liveness/cost warnings, and structural "
            "transitions, but keeps non-mutating tactic previews disabled."
        ),
        allowed_intents=CONTROL_INTENTS | SIGNPOST_INSPECT_TOPICS | frozenset({"lookup_symbol"}),
        allowed_inspect_topics=SIGNPOST_INSPECT_TOPICS,
        paper_level="L3",
    ),
    "l4_preview_diagnostic": SurfaceProfile(
        name="l4_preview_diagnostic",
        stage="l4_preview_diagnostic",
        description=(
            "Diagnostic L4-minus-health profile: adds read-only context and "
            "call-subgoal previews, but omits the upgraded "
            "route-health and recovery surface."
        ),
        allowed_intents=ALL_MANAGER_INTENTS,
        allowed_inspect_topics=PREVIEW_INSPECT_TOPICS,
        paper_level="L4",
        paper_role="diagnostic",
    ),
    "l4_checked_action_surface": SurfaceProfile(
        name="l4_checked_action_surface",
        stage="l4_checked_action_surface",
        description=(
            "L4 Verifier-Checked Action Surface: exposes checked previews, "
            "route health, recovery diagnosis, recovery "
            "signals, and selected diagnostics while demoting accepted "
            "partial openers that only create residual surgery."
        ),
        allowed_intents=ALL_MANAGER_INTENTS,
        allowed_inspect_topics=UPGRADED_NAVIGATOR_INSPECT_TOPICS,
        paper_level="L4",
    ),
    "adaptive": SurfaceProfile(
        name="adaptive",
        stage="adaptive",
        description=(
            "Adaptive surface: starts as L1 goal-only (cheap fast path, no "
            "context-topic/lookup, no panels) and auto-escalates to the full L4 checked-"
            "action surface the moment the agent reaches for a richer intent "
            "(context-topic/lookup) or accumulates rejected commits. The MCP tool "
            "schema advertises all intents, but the manager only accepts the L4 "
            "ones after escalation. Once escalated it latches to L4."
        ),
        # Phase-1 (pre-escalation) EFFECTIVE intents = goal-only control set.
        allowed_intents=GOAL_ONLY_CONTROL_INTENTS,
        allowed_inspect_topics=frozenset(),
        # The agent SEES every lever in the tool schema (so reaching for one is the
        # escalation request), but they are gated until escalation.
        schema_intents=ALL_MANAGER_INTENTS,
        escalate_to="l4_checked_action_surface",
        paper_level="adaptive",
    ),
    "diagnostic_full_surface": SurfaceProfile(
        name="diagnostic_full_surface",
        stage="full",
        description=(
            "Diagnostic unfiltered compiled proof-state surface. Search "
            "topology remains orchestrator-owned and is not part of this "
            "surface profile."
        ),
        allowed_intents=ALL_MANAGER_INTENTS,
        allowed_inspect_topics=None,
        paper_role="diagnostic",
    ),
}


def surface_profile_names(*, include_unsupported: bool = True) -> list[str]:
    return sorted(
        name
        for name, profile in SURFACE_PROFILE_REGISTRY.items()
        if include_unsupported or profile.supported
    )


def resolve_surface_profile(name: str | None) -> SurfaceProfile | None:
    if not name:
        return None
    key = str(name).strip()
    if not key:
        return None
    try:
        return SURFACE_PROFILE_REGISTRY[key]
    except KeyError as exc:
        known = ", ".join(surface_profile_names())
        raise ValueError(f"unknown surface profile {key!r}; known profiles: {known}") from exc


def ensure_supported_surface_profile(name: str | None) -> SurfaceProfile | None:
    profile = resolve_surface_profile(name)
    if profile is not None and not profile.supported:
        raise ValueError(
            f"surface profile {profile.name!r} is registered for the eval "
            "story but does not have a managed runtime yet"
        )
    return profile


def _with_effective_context_intents(
    intents: frozenset[str],
    profile: "SurfaceProfile | None",
) -> frozenset[str]:
    """Mirror inspect-topic gating in the direct intent set."""
    topics = effective_inspect_topics(profile)
    if topics is None:
        return intents
    return (intents - CONTEXT_TOPIC_INTENTS) | (CONTEXT_TOPIC_INTENTS & topics)


def effective_allowed_intents(
    profile: "SurfaceProfile | None",
) -> "frozenset[str] | None":
    """Intents accepted for a profile after context-topic gating."""
    if profile is None:
        return None
    intents = frozenset(profile.allowed_intents)
    intents = _with_effective_context_intents(intents, profile)
    return intents


def allowed_intents_for_surface_profile(name: str | None) -> frozenset[str]:
    profile = resolve_surface_profile(name)
    if profile is None:
        return ALL_MANAGER_INTENTS
    return effective_allowed_intents(profile)


def schema_intents_for_surface_profile(name: str | None) -> frozenset[str]:
    """Intents advertised in the MCP tool schema. For an adaptive profile this is a
    SUPERSET of the currently-accepted intents (``allowed_intents``): the agent can
    see the richer levers from turn 1, but the manager only accepts the gated ones
    once it escalates. Reaching for a gated lever IS the escalation request."""
    profile = resolve_surface_profile(name)
    if profile is None:
        base = ALL_MANAGER_INTENTS
    else:
        base = profile.schema_intents if profile.schema_intents is not None else profile.allowed_intents
    base = frozenset(base)
    base = _with_effective_context_intents(base, profile)
    return base


def surface_profile_allows_intent(
    name: str | None,
    intent: str,
    payload: dict[str, Any] | None = None,
) -> tuple[bool, str]:
    profile = resolve_surface_profile(name)
    if profile is None:
        if intent == "inspect_context":
            return True, ""
        return True, ""
    if intent == "inspect_context":
        topics = effective_inspect_topics(profile)
        if topics is not None:
            topic = normalize_context_topic((payload or {}).get("topic") or "goal_info")
            if topic not in topics:
                allowed = ", ".join(sorted(topics)) or "<none>"
                return False, (
                    f"Surface profile `{profile.name}` hides context topic "
                    f"`{topic}`. Allowed topics: {allowed}."
                )
        return True, ""
    if is_context_topic_intent(intent):
        topic = normalize_context_topic(intent)
        topics = effective_inspect_topics(profile)
        if topics is not None and topic not in topics:
            allowed = ", ".join(sorted(topics)) or "<none>"
            return False, (
                f"Surface profile `{profile.name}` hides context topic "
                f"`{topic}`. Allowed topics: {allowed}."
            )
    if intent not in (effective_allowed_intents(profile) or frozenset()):
        return False, (
            f"Surface profile `{profile.name}` hides manager intent "
            f"`{intent}` for this run."
        )
    return True, ""


# --- view-neutrality strip (docs/design/compiler_view_boundary.md §5/§9) -----
#
# When `view_neutrality_strict()`, the agent view carries facts / daemon-verified
# content / guardrails ONLY. These keys are heuristic *guesses about which move is
# good or bad* (route recommendations, self-rated confidence, anti-routes, ranked
# suggestions, the probability budget ledger, invariant proposals) and are stripped
# wherever they appear. There is no "advisory" middle mode — excluded, not shown.
#
# NOT stripped (facts that merely READ like help): `preview_effects` (preflight-observed
# counts), `head_to_tactic` (reduction legality), `invariant_must_carry` /
# `frame_facts_at_risk` (frame), `rewind_targets` / `why_checkpoint` (real
# checkpoints), `unfoldable_heads`, `toolbox` / `options` / `close_with`
# (static form reference), `yours` / `limitations` (guardrails), daemon-verified
# bridge candidates.
_HEURISTIC_KEYS = frozenset({
    # route recommendation / self-rated confidence
    "navigation", "route_health", "route", "confidence", "confidence_reason",
    "why_now", "repair_if_fails", "why_relevant",
    # anti-route / avoid / forbidden lowerings
    "avoid", "anti_routes", "anti_route", "forbidden_routes",
    "unsafe_lowerings", "route_plan", "allowed_boundary_moves",
    # probability budget ledger + computed strategy
    "probability_budget", "budget_ledger", "probability_budget_ledger",
    "framework_strategy", "pr_obligation_primary_strategy", "pr_shape_facts",
    "likely_proof_family", "side_condition_recipe",
    # ranked actions / shape hints / invariant proposals / heuristic class labels
    "strategy_hint", "suggested_tactics", "suggested_invariant",
    "recommended_next", "recommended_tactic", "recovery_class", "diagnosis",
})


def enforce_view_neutrality(value: Any) -> Any:
    """Recursively drop heuristic keys (`_HEURISTIC_KEYS`) from an agent view.

    Facts, daemon-verified content, and guardrails are untouched. Applied at the
    single agent-view exit (`_with_profile_meta`) when `view_neutrality_strict()`.
    See docs/design/compiler_view_boundary.md.
    """
    if isinstance(value, dict):
        return {
            key: enforce_view_neutrality(item)
            for key, item in value.items()
            if key not in _HEURISTIC_KEYS
        }
    if isinstance(value, list):
        return [enforce_view_neutrality(item) for item in value]
    return value


# Top-level view keys every semantic surface (L2/L3/L4) keeps; the per-stage
# differences live in the _filter_* calls, not in this key set.
_SEMANTIC_SURFACE_KEYS: frozenset[str] = frozenset({
    "schema_version",
    "kind",
    "proof_status",
    "last_result",
    "current_goal",
    "program_frontier",
    "application_context",
    "facts_and_diagnostics",
    "inspect_lookup_handles",
    "candidate_moves",
    "surface_action_preflight",
    "latest_observation",
})


def apply_workspace_view_surface_profile(
    view: dict[str, Any],
    name: str | None,
) -> dict[str, Any]:
    """Return the profile-visible ProverWorkspaceView.

    The manager computes the full view first, then this function erases panels
    for the surface profile.  That keeps the verifier/session behavior
    comparable across profiles while changing only the interface shown to the
    agent.
    """
    profile = resolve_surface_profile(name)
    if profile is None or profile.stage == "full":
        return _with_profile_meta(dict(view), profile)

    raw = dict(view)
    if profile.stage == "l1_goal_projection":
        kept = _keep_top_level(
            raw,
            {
                "schema_version",
                "kind",
                "proof_status",
                "last_result",
                "current_goal",
                "latest_observation",
            },
        )
        return _with_profile_meta(kept, profile)

    if profile.stage == "l2_semantic_ir":
        kept = _keep_top_level(raw, set(_SEMANTIC_SURFACE_KEYS))
        kept["application_context"] = _filter_application_context(
            raw.get("application_context"),
            include_probability_budget=False,
        )
        kept["facts_and_diagnostics"] = _filter_facts_and_diagnostics(
            raw.get("facts_and_diagnostics"),
            include_probability_budget=False,
        )
        kept["inspect_lookup_handles"] = _filter_inspect_lookup_handles(
            raw.get("inspect_lookup_handles"),
            profile,
        )
        kept["candidate_moves"] = _filter_candidate_moves(
            raw.get("candidate_moves"),
            include_navigation=False,
            include_structural=False,
            include_upgrade_structural=False,
            include_route_health=False,
            allowed_inspect_topics=profile.allowed_inspect_topics,
        )
        return _with_profile_meta(kept, profile)

    if profile.stage == "l3_flow_navigation":
        kept = _keep_top_level(raw, set(_SEMANTIC_SURFACE_KEYS))
        kept["application_context"] = _filter_application_context(
            raw.get("application_context"),
            include_probability_budget=False,
        )
        kept["facts_and_diagnostics"] = _filter_facts_and_diagnostics(
            raw.get("facts_and_diagnostics"),
            include_probability_budget=False,
        )
        kept["inspect_lookup_handles"] = _filter_inspect_lookup_handles(
            raw.get("inspect_lookup_handles"),
            profile,
        )
        kept["candidate_moves"] = _filter_candidate_moves(
            raw.get("candidate_moves"),
            include_navigation=True,
            include_structural=True,
            include_upgrade_structural=False,
            include_route_health=False,
            allowed_inspect_topics=profile.allowed_inspect_topics,
        )
        return _with_profile_meta(kept, profile)

    if profile.stage in {
        "l4_preview_diagnostic",
        "l4_checked_action_surface",
    }:
        kept = _keep_top_level(raw, set(_SEMANTIC_SURFACE_KEYS))
        if profile.stage == "l4_checked_action_surface":
            for key in (
                "call_site_surface",
                "seq_cut_surface",
                "pure_tail_surface",
                "frame_obligation_ledger",
                "recovery_diagnosis_surface",
                "structural_checkpoints",
                "route_replay_memory",
            ):
                if raw.get(key) not in ({}, [], None, ""):
                    kept[key] = raw.get(key)
        kept["application_context"] = _filter_application_context(
            raw.get("application_context"),
            include_probability_budget=profile.stage == "l4_checked_action_surface",
        )
        kept["facts_and_diagnostics"] = _filter_facts_and_diagnostics(
            raw.get("facts_and_diagnostics"),
            include_probability_budget=profile.stage == "l4_checked_action_surface",
        )
        kept["inspect_lookup_handles"] = _filter_inspect_lookup_handles(
            raw.get("inspect_lookup_handles"),
            profile,
        )
        kept["candidate_moves"] = _filter_candidate_moves(
            raw.get("candidate_moves"),
            include_navigation=True,
            include_structural=True,
            include_upgrade_structural=profile.stage == "l4_checked_action_surface",
            include_route_health=profile.stage == "l4_checked_action_surface",
            demote_partial_commit_candidates=profile.stage == "l4_checked_action_surface",
            allowed_inspect_topics=profile.allowed_inspect_topics,
        )
        return _with_profile_meta(_assemble_profile_raw_view(kept), profile)

    return _with_profile_meta(raw, profile)



def _keep_top_level(raw: dict[str, Any], keys: set[str]) -> dict[str, Any]:
    return {key: value for key, value in raw.items() if key in keys}


# --- Profile-gated raw view --------------------------------------------------
#
# Measured (step4_badi L1 vs L4, 2026-06-01): at deep procedure_body / seq_cut
# with a giant goal, the full L4 surface (~51 KB, 13 sections) OVERWHELMS the
# agent — it disorients ("a fundamental issue I'm not seeing"), burns ~4.6x the
# tokens, and gives up. The lean L1 view (~11 KB, goal only) keeps the agent
# grinding. L4 therefore keeps profile-allowed raw facts/actions and drops only
# true noise/duplicates; visible panel choice is owned by workflow.surface_composer.
# This env var is now an A/B ON/OFF switch (the value is no longer a threshold):
# 0 restores the full surface for comparison; any positive value enables profile
# raw-view slimming.
_DEEP_GOAL_SHRINK_CHARS = int(os.environ.get("SHANNON_DEEP_GOAL_SHRINK_CHARS", "4000"))

# The shrink hides pre-computed ANALYSIS panels (noise at depth); it must NEVER
# hide the agent's available ACTIONS. `inspect_lookup_handles` is the agent's tool
# menu (which inspect topics it can ask for — call_subgoals,
# tactic_forms, …); keep it so the agent still knows what it can request.
_DEEP_SHRINK_KEEP = {
    "schema_version", "kind", "proof_status", "last_result",
    "current_goal", "latest_observation", "inspect_lookup_handles",
    "surface_action_preflight",
}


# Collapsed at every slim raw view: dup-of-core / navigation history only. The
# profile layer does not choose panels; it only removes empty or noisy raw facts.
_RAW_REFERENCE_COLLAPSE = {
    "route_replay_memory",
}


def _assemble_raw_slim_view(kept: dict[str, Any]) -> dict[str, Any]:
    """Profile-gated raw view assembly.

    Surface selection belongs to ``workflow.surface_composer``.  This function
    keeps profile-allowed raw facts, drops empty values, strips internal
    validation errors, and records only true raw-reference collapses.
    """
    lean: dict[str, Any] = {}
    collapsed: "list[str]" = []
    for key, val in kept.items():
        if val in ({}, [], None, ""):
            continue  # empty panel — never surface, never index
        if key in _RAW_REFERENCE_COLLAPSE:
            collapsed.append(key)
            continue
        if key == "facts_and_diagnostics" and isinstance(val, dict) and val.get("errors"):
            # internal schema-validation noise (e.g. `guidance.stale_recommendations[...]
            # must be non-empty`) — never an agent-facing fact. Strip it.
            val = {k: v for k, v in val.items() if k != "errors"}
            if not val:
                continue
        lean[key] = val  # analysis signal panel — kept (content-gated upstream)
    if collapsed:
        lean["reference"] = {
            "note": "Raw reference panels collapsed by profile slimming.",
            "collapsed": sorted(collapsed),
        }
    return lean


def _assemble_profile_raw_view(kept: dict[str, Any]) -> dict[str, Any]:
    """Profile-gated raw view assembly.

    The presentation contract lives in ``workflow.surface_composer``.  Surface
    profiles keep profile-allowed raw facts and hide disallowed material; they do
    not construct presentation panels or choose display order.
    """
    if _DEEP_GOAL_SHRINK_CHARS <= 0:
        return kept  # A/B escape hatch: restore the full surface for comparison
    return _assemble_raw_slim_view(kept)


def _filter_application_context(
    value: Any,
    *,
    include_probability_budget: bool,
) -> Any:
    if not isinstance(value, dict):
        return value
    out = dict(value)
    handles = out.get("selected_handles")
    if isinstance(handles, list):
        filtered: list[Any] = []
        for item in handles:
            if not isinstance(item, dict):
                filtered.append(item)
                continue
            if (
                not include_probability_budget
                and _is_probability_budget_handle(item)
            ):
                continue
            filtered.append(dict(item))
        out["selected_handles"] = filtered
    return out


def _filter_facts_and_diagnostics(
    value: Any,
    *,
    include_probability_budget: bool,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    out = dict(value)
    if not include_probability_budget:
        out.pop("probability_budget", None)
    return {
        key: item
        for key, item in out.items()
        if item not in ({}, [], None, "")
    }


def _is_probability_budget_handle(item: dict[str, Any]) -> bool:
    title = str(item.get("title") or "").lower()
    return (
        item.get("title") == "Probability-budget context"
        or item.get("title") == "Probability budget ledger"
        or item.get("budget_shape") == "product_bound"
        or item.get("kind") == "probability_budget_ledger"
        or item.get("kind") == "route-selection context"
        and ("probability-budget" in title or "probability budget" in title)
    )


def _filter_inspect_lookup_handles(
    value: Any,
    profile: SurfaceProfile,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    out = dict(value)
    requests = out.get("ask_manager_for")
    if isinstance(requests, list):
        allowed_requests = []
        for request in requests:
            if not isinstance(request, dict):
                continue
            if _manager_request_allowed(request, profile):
                spec = intent_spec(request.get("intent"))
                if spec is not None and not spec.advertised:
                    continue
                allowed_requests.append(dict(request))
        out["ask_manager_for"] = allowed_requests
    return {
        key: item
        for key, item in out.items()
        if item not in ({}, [], None, "")
    }


def _filter_candidate_moves(
    value: Any,
    *,
    include_navigation: bool,
    include_structural: bool,
    include_upgrade_structural: bool,
    include_route_health: bool,
    demote_partial_commit_candidates: bool = False,
    allowed_inspect_topics: frozenset[str] | None = None,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    allowed = {"moves", "limitations"}
    if include_navigation:
        allowed.add("navigation")
    if include_structural:
        allowed.add("structural_transitions")
    if include_route_health:
        allowed.add("route_health")
    out = {
        key: item
        for key, item in value.items()
        if key in allowed and item not in ({}, [], None, "")
    }
    if isinstance(out.get("moves"), list):
        moves = []
        for item in out["moves"]:
            if not isinstance(item, dict):
                continue
            move = dict(item)
            if demote_partial_commit_candidates:
                move = _demote_partial_commit_candidate(move)
            moves.append(move)
        out["moves"] = moves
    if isinstance(out.get("navigation"), list):
        out["navigation"] = [
            _filter_navigation_item(
                item,
                allowed_inspect_topics=allowed_inspect_topics,
            )
            for item in out["navigation"]
            if isinstance(item, dict)
            and (
                include_upgrade_structural
                or not _is_upgrade_profile_gate(item)
            )
        ]
    if isinstance(out.get("structural_transitions"), list):
        out["structural_transitions"] = [
            item
            for item in out["structural_transitions"]
            if not isinstance(item, dict)
            or include_upgrade_structural
            or not _is_upgrade_profile_gate(item)
        ]
    if isinstance(out.get("route_health"), list):
        out["route_health"] = [
            _filter_route_health_item(
                item,
                allowed_inspect_topics=allowed_inspect_topics,
            )
            for item in out["route_health"]
            if isinstance(item, dict)
        ]
    out = {
        key: item
        for key, item in out.items()
        if item not in ({}, [], None, "")
    }
    return out


def _is_upgrade_profile_gate(item: dict[str, Any]) -> bool:
    return str(item.get("profile_gate") or "") in {
        "l4_checked_action_surface",
        "navigator_upgrade",
    }


def _filter_navigation_item(
    item: dict[str, Any],
    *,
    allowed_inspect_topics: frozenset[str] | None,
) -> dict[str, Any]:
    out = dict(item)
    repairs = out.get("repair_if_fails")
    if isinstance(repairs, list):
        out["repair_if_fails"] = [
            repair
            for repair in repairs
            if isinstance(repair, dict)
            and not _mentions_hidden_inspect_topic(
                repair.get("next"),
                allowed_inspect_topics,
            )
        ]
    return {
        key: value
        for key, value in out.items()
        if value not in ({}, [], None, "")
    }


def _filter_route_health_item(
    item: dict[str, Any],
    *,
    allowed_inspect_topics: frozenset[str] | None,
) -> dict[str, Any]:
    out = dict(item)
    inspections = out.get("useful_inspections")
    if isinstance(inspections, list):
        out["useful_inspections"] = [
            dict(request) if isinstance(request, dict) else request
            for request in inspections
            if not isinstance(request, dict)
            or _manager_request_topic_allowed(request, allowed_inspect_topics)
        ]
    recommended = out.get("recommended_next")
    if (
        isinstance(recommended, dict)
        and not _manager_request_topic_allowed(recommended, allowed_inspect_topics)
    ):
        out.pop("recommended_next", None)
    elif isinstance(recommended, dict):
        out["recommended_next"] = dict(recommended)
    return {
        key: value
        for key, value in out.items()
        if value not in ({}, [], None, "")
    }


def _manager_request_allowed(request: dict[str, Any], profile: SurfaceProfile) -> bool:
    intent = str(request.get("intent") or "").strip()
    payload = request.get("payload")
    payload_dict = payload if isinstance(payload, dict) else {}
    allowed, _ = surface_profile_allows_intent(profile.name, intent, payload_dict)
    return allowed


def _inspect_topic_allowed(
    topic: str,
    allowed_inspect_topics: frozenset[str] | None,
) -> bool:
    return allowed_inspect_topics is None or normalize_context_topic(topic) in allowed_inspect_topics


def _manager_request_topic_allowed(
    request: dict[str, Any],
    allowed_inspect_topics: frozenset[str] | None,
) -> bool:
    intent = str(request.get("intent") or "").strip()
    if intent == "lookup_symbol":
        return True
    if intent == "inspect_context":
        payload = request.get("payload") if isinstance(request.get("payload"), dict) else {}
        return _inspect_topic_allowed(str(payload.get("topic") or ""), allowed_inspect_topics)
    if is_context_topic_intent(intent):
        return _inspect_topic_allowed(intent, allowed_inspect_topics)
    return True


def _mentions_hidden_inspect_topic(
    value: Any,
    allowed_inspect_topics: frozenset[str] | None,
) -> bool:
    if allowed_inspect_topics is None:
        return False
    text = str(value or "")
    known_topics = UPGRADED_NAVIGATOR_INSPECT_TOPICS | frozenset({
        "episode_view",
        "pivot_context",
        "verified_pivot_options",
        "call_site_options",
        "bridge_options",
        "rewrite_candidates",
        "probability_budget_ledger",
        "suggest_close",
    })
    return any(topic in text and topic not in allowed_inspect_topics for topic in known_topics)


def _demote_partial_commit_candidate(item: dict[str, Any]) -> dict[str, Any]:
    move = dict(item)
    if not _is_risky_partial_commit_candidate(move):
        return move
    lead = (
        "Accepted tactic leaves residual subgoals; treat this as a partial "
        "opener, not as a route recommendation."
    )
    evidence = [
        lead,
        *[
            str(piece)
            for piece in move.get("evidence", [])
            if str(piece).strip()
        ],
    ][:3]
    move.update({
        "title": "Accepted partial opener",
        "category": "commit",
        "effect": (
            "This tactic is known to be accepted, but it opens residual "
            "surgery. Commit it only if you intentionally want that local "
            "workbench and have a closure plan."
        ),
        "commit_risk": "leaves_residual_subgoals",
        "evidence": evidence,
    })
    return move


def _is_risky_partial_commit_candidate(item: dict[str, Any]) -> bool:
    if str(item.get("category") or "") != "commit":
        return False
    tactic = str(item.get("tactic") or "").strip()
    if not tactic:
        return False
    evidence_text = " ".join(str(piece) for piece in item.get("evidence", []))
    if not re.search(r"\bwould leave [1-9][0-9]* subgoal", evidence_text):
        return False
    lower = tactic.lower()
    if any(
        token in lower
        for token in (
            "wp",
            "rnd",
            "skip",
            "while",
            "call",
            "proc",
            "byequiv",
            "byphoare",
            "qed",
        )
    ):
        return False
    local_heads = ("move=>", "auto", "split", "rewrite")
    return lower.startswith(local_heads) or any(
        f"; {head}" in lower for head in local_heads
    )


def _with_profile_meta(
    view: dict[str, Any],
    profile: SurfaceProfile | None,
) -> dict[str, Any]:
    # Single agent-view exit: every apply_workspace_view_surface_profile branch
    # returns through here, so the neutrality strip is enforced in exactly one place.
    if view_neutrality_strict():
        view = enforce_view_neutrality(view)
    if profile is None:
        return view
    meta = dict(view.get("surface_profile") or {})
    meta.update({
        "name": profile.name,
        "surface_profile": profile.name,
        "stage": profile.stage,
        "description": profile.description,
        "paper_level": profile.paper_level,
        "paper_role": profile.paper_role,
    })
    view["surface_profile"] = meta
    return view
