"""State-dependent eligibility for SurfaceModel actions.

Intent taxonomy lives in ``context_intents``.  Profile gating lives in
``surface_profiles``.  This module owns the last content contract before
rendering: an action may be protocol-valid and profile-visible, but it is shown
only when the current proof state makes it useful now.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Any

from workflow.context_intents import (
    INTENT_CLASS_CONTEXT_TOPIC,
    INTENT_CLASS_PROOF_MUTATION,
    INTENT_CLASS_PROOF_CONTROL,
    INTENT_CLASS_SYMBOL_LOOKUP,
    intent_class,
    intent_spec,
)
from workflow.surface_model import PanelAction
from workflow.surface_action_preflight import (
    action_needs_dynamic_preflight,
    matching_preflight_submission,
    preflight_result,
)
from workflow.surface_action_choices import (
    is_placeholder as _choice_is_placeholder,
)
from workflow.surface_action_policy import panel_allowed_intents
from workflow.surface_state_predicates import (
    derive_surface_state,
    goal_has_program,
    is_relational_goal,
    preferred_procedure_entry_transition,
)
from workflow.surface_tactic_forms import eligible_tactic_form_names
from core.easycrypt.value_shapes import as_dict as _dict, as_list as _list


@dataclass(frozen=True)
class ActionEligibilityResult:
    eligible: bool
    reason: str = ""
    source_refs: tuple[str, ...] = ()
    state_scope: str = ""


_CALL_CONTEXT_REQUIRES_CURRENT_FRONTIER = frozenset({
    "call_invariant_skeleton",
    "call_subgoals",
    "inv_from_lemma",
})

def has_current_call_surface_context(view: dict[str, Any]) -> bool:
    """True when call-context affordances are live at the current frontier.

    A future/downstream call or a non-callable named handle is useful audit context,
    but it must not make the agent-facing surface look like `call ...` applies now.
    """
    cs = _dict(view.get("call_site_surface"))
    if _list(cs.get("callable_now")) or _list(cs.get("frontier_live_named_handles")):
        return True
    for handle in _list(cs.get("named_handles")):
        if not isinstance(handle, dict):
            continue
        if handle.get("callable_now") or handle.get("frontier_live"):
            return True
    for site in _list(cs.get("live_call_sites")):
        if not isinstance(site, dict):
            continue
        if site.get("is_frontier_call") and not site.get("requires_cut_to_frontier"):
            return True
    return False


def has_displayable_call_surface(view: dict[str, Any]) -> bool:
    """Return whether the canonical surface should enter the call-site phase."""
    current_call = has_current_call_surface_context(view)
    preflight = _dict(view.get("surface_action_preflight"))
    results = _list(preflight.get("results"))
    for item in results:
        if not isinstance(item, dict) or not item.get("eligible"):
            continue
        intent = str(item.get("intent") or "")
        if intent not in {
            "call_site_options",
            "call_subgoals",
            "call_invariant_skeleton",
            "inv_from_lemma",
        }:
            continue
        if intent != "call_site_options" and not current_call:
            continue
        return True
    return False


def filter_surface_actions(
    view: dict[str, Any],
    panel_id: str,
    phase: str,
    actions: tuple[PanelAction, ...] | list[PanelAction],
) -> list[PanelAction]:
    """Return only actions eligible for this panel and proof state."""
    allowed = panel_allowed_intents(panel_id)
    out: list[PanelAction] = []
    for action in actions or ():
        if allowed is not None and action.intent not in allowed:
            continue
        candidate = action
        result = action_eligibility(view, panel_id, phase, candidate)
        if not result.eligible:
            continue
        out.append(_with_eligibility(candidate, result))
    return out


def preflight_candidate_state_eligibility(
    view: dict[str, Any],
    intent: str,
    payload: dict[str, Any] | None = None,
) -> ActionEligibilityResult:
    """Cheap state gate applied before a manager-owned read-only preflight.

    Dynamic preflight remains the authority on whether backend output is
    displayable.  This gate only rejects candidates whose required proof-state
    shape is already known to be absent, avoiding backend calls for the stable
    protocol/profile roster emitted by the workspace producer.
    """
    del payload  # Payload expansion is owned by surface_action_preflight.
    state = derive_surface_state(view)

    if intent == "call_site_options":
        if has_current_call_surface_context(view) or state.frontier_kind == "call":
            return _yes(
                "current proof state exposes a call frontier worth preflighting",
                "call_frontier",
                ("call_site_surface", "program_frontier.current_frontier_scope"),
            )
        return _no(
            "no current call frontier; future or static calls do not justify preflight",
            "call_frontier",
            ("call_site_surface", "program_frontier.current_frontier_scope"),
        )

    if intent in _CALL_CONTEXT_REQUIRES_CURRENT_FRONTIER:
        if has_current_call_surface_context(view):
            return _yes(
                "current frontier has concrete call context for this preflight",
                "call_site_surface",
                ("call_site_surface",),
            )
        return _no(
            "call-context preflight requires a current callable/frontier-live handle",
            "call_site_surface",
            ("call_site_surface",),
        )

    if intent in {"pr_bridge_routes", "verified_pivot_options"}:
        if state.goal_mode == "probability" and not state.has_program:
            return _yes(
                "current goal is a probability residual",
                "probability_goal",
                state.source_refs,
            )
        return _no(
            "Pr bridge preflight requires a current probability residual",
            "probability_goal",
            state.source_refs,
        )

    if intent == "equiv_bridge_lemmas":
        if not state.has_program and state.goal_mode in {"probability", "relational"}:
            return _yes(
                "current non-program goal can use an equivalence bridge lookup",
                "bridge_goal",
                state.source_refs,
            )
        return _no(
            "equivalence bridge preflight is not current program-frontier work",
            "bridge_goal",
            state.source_refs,
        )

    if intent in {"rewrite_candidates", "lemma_hints"}:
        if not state.has_program:
            return _yes(
                "current residual is non-program proof work",
                "logical_residual",
                state.source_refs,
            )
        return _no(
            "lemma/rewrite preflight waits until program-frontier work is absent",
            "logical_residual",
            state.source_refs,
        )

    # Some dynamic analyzers, notably subgoal_gap, perform their own precise
    # shape classification.  When no cheap exclusion is authoritative, let the
    # read-only classifier decide instead of duplicating its semantics here.
    return _yes(
        "no authoritative cheap state exclusion; use dynamic preflight result",
        "current_state",
        state.source_refs,
    )


def action_eligibility(
    view: dict[str, Any],
    panel_id: str,
    phase: str,
    action: PanelAction,
) -> ActionEligibilityResult:
    spec = intent_spec(action.intent)
    if spec is None or not spec.advertised:
        return _no("intent is not advertised", "context_intents")
    if intent_class(action.intent) == INTENT_CLASS_PROOF_CONTROL:
        return _no("proof control belongs to SurfaceTurnModel.control_menu", "surface_turn")

    intent = action.intent
    if intent_class(intent) == INTENT_CLASS_PROOF_MUTATION:
        transition = preferred_procedure_entry_transition(view)
        if (
            intent == "commit_tactic"
            and transition
            and action.payload == {"tactic": transition["tactic"]}
        ):
            return _yes(
                "exact preferred procedure-entry transition from ProofIR",
                "current_procedure_entry",
                ("program_frontier.procedure_entry_transition",),
            )
        preflight_match = matching_preflight_submission(view, intent, action.payload)
        if preflight_match:
            source_intent = str(preflight_match.get("source_intent") or "preflight")
            return _yes(
                f"exact manager-preflighted submission from {source_intent}",
                "surface_action_preflight",
                ("surface_action_preflight.results",),
            )
        return _no(
            "proof mutations require an exact typed current-state transition",
            "program_frontier",
        )
    if intent_class(intent) == INTENT_CLASS_SYMBOL_LOOKUP:
        return _yes("general symbol lookup", "global_lookup", action.source_refs)
    if intent in _CALL_CONTEXT_REQUIRES_CURRENT_FRONTIER and not has_current_call_surface_context(view):
        return _no(
            "call-context action needs a current callable/frontier-live call context",
            "call_site_surface",
            ("call_site_surface", "program_frontier"),
        )
    if action_needs_dynamic_preflight(intent):
        dynamic = preflight_result(view, intent, action.payload)
        if not dynamic:
            return _no(
                "no manager read-only preflight result for this action",
                "surface_action_preflight",
                ("surface_action_preflight",),
            )
        if not bool(dynamic.get("eligible")):
            return _no(
                str(dynamic.get("reason") or "preflight found no displayable result"),
                "surface_action_preflight",
                ("surface_action_preflight",),
            )
        return _yes(
            str(dynamic.get("reason") or "read-only preflight found displayable context"),
            "surface_action_preflight",
            ("surface_action_preflight",),
        )
    if intent == "operator_lemmas":
        return _no(
            "broad operator search is not a persistent surface action",
            "current_goal",
        )
    if intent == "tactic_forms":
        return _tactic_forms_eligibility(view, panel_id, phase, action)
    if intent == "proof_frontier":
        return (
            _yes("program frontier facts are present", "program_frontier", ("program_frontier",))
            if goal_has_program(view) or bool(_dict(view.get("program_frontier")))
            else _no("no program frontier is visible", "program_frontier")
        )
    if intent == "align":
        return (
            _yes("relational alignment facts are meaningful", "program_frontier", ("program_frontier",))
            if is_relational_goal(view)
            else _no("alignment is not meaningful for this single-sided goal", "program_frontier")
        )
    if intent_class(intent) == INTENT_CLASS_CONTEXT_TOPIC:
        if _has_unfilled_placeholder(action) and not _has_concrete_choice(action):
            return _no("context topic has no concrete state-derived choice", "current_goal")
        return _yes("profile-visible context topic", "current_goal", action.source_refs)
    return _no("unknown action class", "context_intents")


def _tactic_forms_eligibility(
    view: dict[str, Any],
    panel_id: str,
    phase: str,
    action: PanelAction,
) -> ActionEligibilityResult:
    names = [
        str(value).strip()
        for value in _action_values(action, "name")
        if str(value).strip() and not _is_placeholder(value)
    ]
    if not names:
        return _no("tactic form needs a concrete state-derived tactic name", "current_goal")
    allowed = eligible_tactic_form_names(view, panel_id, phase)
    if allowed is not None and not set(names).issubset(allowed):
        return _no("tactic reference is not visible in this current proof phase", "program_frontier")
    return _yes("tactic reference matches the canonical current-phase set", "current_phase", ("proof_status", "program_frontier"))


def _action_values(action: PanelAction, field: str) -> list[Any]:
    values: list[Any] = []
    value = action.payload.get(field)
    if value is not None and not _is_placeholder(value):
        values.append(value)
    for choice in action.choices.get(field, []):
        if choice is not None and not _is_placeholder(choice) and choice not in values:
            values.append(choice)
    return values


def _has_unfilled_placeholder(action: PanelAction) -> bool:
    if not action.requires_input:
        return False
    return any(_is_placeholder(action.payload.get(field)) for field in action.requires_input)


def _has_concrete_choice(action: PanelAction) -> bool:
    for values in action.choices.values():
        if any(not _is_placeholder(value) for value in values):
            return True
    return False


def _is_placeholder(value: Any) -> bool:
    return _choice_is_placeholder(value)


def _with_eligibility(
    action: PanelAction,
    result: ActionEligibilityResult,
) -> PanelAction:
    refs = tuple(dict.fromkeys((*action.source_refs, *result.source_refs)))
    return replace(
        action,
        source_refs=refs,
        eligibility_reason=result.reason,
        state_scope=result.state_scope,
    )


def _yes(
    reason: str,
    state_scope: str,
    source_refs: tuple[str, ...] = (),
) -> ActionEligibilityResult:
    return ActionEligibilityResult(True, reason, source_refs, state_scope)


def _no(
    reason: str,
    state_scope: str,
    source_refs: tuple[str, ...] = (),
) -> ActionEligibilityResult:
    return ActionEligibilityResult(False, reason, source_refs, state_scope)
