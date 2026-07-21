"""Compose the canonical prover presentation surface.

The composer is the only normal-runtime selector between raw workspace facts and
the agent/human presentation.  Producers emit raw facts; renderers consume only
the typed ``SurfaceModel`` built here.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Any
from workflow.context_intents import (
    INTENT_CLASS_CONTEXT_TOPIC,
    INTENT_CLASS_PROOF_MUTATION,
    INTENT_CLASS_SYMBOL_LOOKUP,
    intent_class,
    intent_is_read_only,
    intent_is_retrieval,
    intent_payload_fields,
    intent_spec,
)
from workflow.surface_action_eligibility import (
    filter_surface_actions,
    has_displayable_call_surface,
)
from workflow.surface_action_preflight import preflight_candidate_evidence
from workflow.surface_fact_eligibility import (
    filter_surface_facts,
    validate_surface_fact_contract,
)
from workflow.surface_action_choices import (
    call_subgoal_invariant_choices_for_view,
    inv_from_lemma_choices_for_view,
    operator_queries_for_goal,
)
from workflow.surface_model import (
    PanelAction,
    PanelModel,
    SurfaceModel,
    _drop_empty,
    last_action_needs_attention,
    surface_model_to_dict,
)
from workflow.surface_state_predicates import derive_surface_state
from workflow.surface_state_predicates import preferred_procedure_entry_transition
from workflow.surface_tactic_forms import compose_tactic_form_actions
from workflow.surface_panels import (
    _SUPPORTED_TACTIC_FORM_NAMES,
    _goal_surface,
    _is_placeholder,
    _primary_panel,
)


def compose_surface_model_dict(
    view: dict[str, Any],
    profile: str | None,
    *,
    goal_only: bool = False,
) -> dict[str, Any]:
    if not isinstance(view, dict):
        return {}
    return surface_model_to_dict(
        compose_surface_model(view, profile, goal_only=goal_only)
    )


def compose_surface_model(
    view: dict[str, Any],
    profile: str | None = None,
    *,
    goal_only: bool = False,
) -> SurfaceModel:
    if not isinstance(view, dict):
        view = {}
    profile_name = str(profile or view.get("surface_profile") or "")
    phase = _phase_for_view(view, goal_only=goal_only, profile=profile_name)
    raw_actions = () if goal_only else tuple(_surface_actions(view))
    available_actions = () if goal_only else tuple(compose_tactic_form_actions(
        view, phase, phase, raw_actions
    ))
    primary = None if goal_only else _primary_panel(view, phase, available_actions)
    if primary is not None:
        primary = _finalize_primary_panel(view, primary)
    panel_actions = tuple(primary.actions) if primary else ()
    actions = () if goal_only else _visible_actions_for_surface(view, phase, primary, available_actions)
    status = _status_surface(view)
    if phase:
        status["surface_phase"] = phase
    return SurfaceModel(
        profile=profile_name,
        phase=phase,
        goal=_goal_surface(view),
        status=status,
        primary_panel=primary,
        panels=(),
        actions=actions,
        metadata={
            "contract": "raw_workspace_facts -> SurfaceModel -> markdown/card",
            "primary_panel_id": primary.panel_id if primary else "",
            "primary_action_count": len(panel_actions),
            "available_action_count": len(available_actions),
        },
    )


def _phase_for_view(view: dict[str, Any], *, goal_only: bool, profile: str) -> str:
    if goal_only or profile == "l1_goal_projection":
        return "goal_only"
    if _last_result_is_retrieval(view):
        return "context_result"
    if last_action_needs_attention(view):
        return "failure_recovery"
    if _view_is_closed_candidate(view):
        return "closed_candidate"
    state = derive_surface_state(view)
    if state.goal_mode == "probability" and not state.has_program:
        return "opener"
    if has_displayable_call_surface(view):
        return "call_site"
    if state.goal_mode == "single_program" and state.has_program:
        return "single_program"
    if state.goal_mode == "relational" and state.has_program:
        frontier = view.get("program_frontier") if isinstance(view.get("program_frontier"), dict) else {}
        scope = frontier.get("current_frontier_scope") if isinstance(frontier.get("current_frontier_scope"), dict) else {}
        if state.current_layer == "verification_residue" and not scope.get("frontier"):
            return "relational_program"
        return "deep_surgery"
    if state.goal_mode == "relational" and not state.has_program:
        if isinstance(view.get("pure_tail_surface"), dict) and view.get("pure_tail_surface"):
            return "pure_logic"
        if state.current_layer in {"prhl_module", "relational_program"}:
            return "relational_program"
        return "plain"
    if state.goal_mode == "pure" or not state.has_program:
        return "pure_logic"
    return "plain"


def _view_is_closed_candidate(view: dict[str, Any]) -> bool:
    ps = view.get("proof_status") if isinstance(view.get("proof_status"), dict) else {}
    status = str(ps.get("status") or "").lower()
    layer = str(ps.get("current_layer") or "").lower()
    focus = str(ps.get("view_focus") or "").lower()
    goal_text = str(_goal_surface(view).get("text") or "").strip().lower()
    return (
        "closed" in status
        or layer == "closed_candidate"
        or focus == "closed_candidate"
        or goal_text.startswith("no more goals")
    )


def _status_surface(view: dict[str, Any]) -> dict[str, Any]:
    ps = view.get("proof_status") if isinstance(view.get("proof_status"), dict) else {}
    remaining = ps.get("remaining_goals")
    remaining_known = ps.get("remaining_goals_known")
    if _view_is_closed_candidate(view):
        remaining = 0
        remaining_known = True
    return _drop_empty({
        "status": ps.get("status"),
        "remaining_goals": remaining,
        "remaining_goals_known": remaining_known,
        "view_focus": ps.get("view_focus"),
        "current_layer": ps.get("current_layer"),
        "goal_type": ps.get("goal_type"),
    })


def _last_result_is_retrieval(view: dict[str, Any]) -> bool:
    lr = view.get("last_result") if isinstance(view.get("last_result"), dict) else {}
    content = lr.get("content")
    return (
        intent_is_retrieval(str(lr.get("intent") or ""))
        and isinstance(content, dict)
        and bool(content)
    )


def _surface_actions(view: dict[str, Any]) -> list[PanelAction]:
    actions: list[PanelAction] = []
    procedure_entry = preferred_procedure_entry_transition(view)
    if procedure_entry:
        actions.append(PanelAction(
            intent="commit_tactic",
            payload={"tactic": procedure_entry["tactic"]},
            label="Open procedure body: proc.",
            intent_class=intent_class("commit_tactic"),
            read_only=False,
            description=str(procedure_entry.get("effect") or ""),
            source_refs=("program_frontier.procedure_entry_transition",),
            eligibility_reason="preferred procedure-entry transition from ProofIR",
            state_scope="current_procedure_entry",
        ))
    preflight_actions, replaced_context_intents = _preflight_proof_actions(view)
    actions.extend(preflight_actions)
    handles = view.get("inspect_lookup_handles") if isinstance(view.get("inspect_lookup_handles"), dict) else {}
    asks = handles.get("ask_manager_for") if isinstance(handles, dict) else None
    raw_actions: list[dict[str, Any]] = []
    for ask in asks or []:
        if not isinstance(ask, dict):
            continue
        action = dict(ask)
        if not _advertised_action(action):
            continue
        if str(action.get("intent") or "") in replaced_context_intents:
            continue
        raw_actions.append(action)
    actions.extend(
        _panel_action_from_request(action)
        for action in _expand_state_derived_actions(view, raw_actions)
    )
    return _attach_choices(actions)


def _preflight_proof_actions(
    view: dict[str, Any],
) -> tuple[list[PanelAction], set[str]]:
    """Project exact manager-preflighted routes into ready proof actions."""
    source_intent = "pr_bridge_routes"
    candidates = preflight_candidate_evidence(view, source_intent)
    actions: list[PanelAction] = []
    for index, candidate in enumerate(candidates, start=1):
        submit = candidate.get("submit")
        if not isinstance(submit, dict):
            continue
        intent = str(submit.get("intent") or "").strip()
        payload = submit.get("payload") if isinstance(submit.get("payload"), dict) else {}
        if intent_class(intent) != INTENT_CLASS_PROOF_MUTATION:
            continue
        candidate_text = str(candidate.get("candidate") or "").strip()
        why = str(candidate.get("why") or "").strip()
        actions.append(PanelAction(
            intent=intent,
            payload=dict(payload),
            label=f"Commit verified Pr bridge route {index}",
            intent_class=intent_class(intent),
            read_only=False,
            description="\n".join(part for part in (candidate_text, why) if part),
            source_refs=("surface_action_preflight.results",),
            eligibility_reason="manager-preflighted current-state route",
            state_scope="surface_action_preflight",
        ))
    return actions, ({source_intent} if candidates else set())


def _expand_state_derived_actions(
    view: dict[str, Any],
    actions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for action in actions:
        intent = str(action.get("intent") or "")
        payload = action.get("payload") if isinstance(action.get("payload"), dict) else {}
        if intent == "operator_lemmas" and _is_placeholder(payload.get("operator")):
            operators = operator_queries_for_goal(view)
            if not operators:
                out.append(action)
                continue
            for operator in operators:
                expanded = dict(action)
                expanded_payload = dict(payload)
                expanded_payload["operator"] = operator
                expanded["payload"] = expanded_payload
                out.append(expanded)
            continue
        if intent == "inv_from_lemma" and _is_placeholder(payload.get("lemma")):
            for lemma in inv_from_lemma_choices_for_view(view):
                expanded = dict(action)
                expanded["payload"] = {**payload, "lemma": lemma}
                out.append(expanded)
            continue
        if intent == "call_subgoals" and _is_placeholder(payload.get("invariant")):
            for invariant in call_subgoal_invariant_choices_for_view(view):
                expanded = dict(action)
                expanded["payload"] = {**payload, "invariant": invariant}
                out.append(expanded)
            continue
        out.append(action)
    return out


def _advertised_action(action: dict[str, Any]) -> bool:
    intent = str(action.get("intent") or "").strip()
    spec = intent_spec(intent)
    if spec is None or not spec.advertised:
        return False
    if intent == "tactic_forms":
        payload = action.get("payload") if isinstance(action.get("payload"), dict) else {}
        name = str(payload.get("name") or "").strip()
        if name and not _is_placeholder(name) and name not in _SUPPORTED_TACTIC_FORM_NAMES:
            return False
    return True


def _panel_action_from_request(action: dict[str, Any]) -> PanelAction:
    intent = str(action.get("intent") or "").strip()
    payload = dict(action.get("payload") or {}) if isinstance(action.get("payload"), dict) else {}
    spec = intent_spec(intent)
    payload_fields = intent_payload_fields(intent)
    requires = tuple(
        field for field in payload_fields
        if _is_placeholder(payload.get(field))
    )
    detail = _action_detail(intent, payload)
    return PanelAction(
        intent=intent,
        payload=payload,
        label=(f"{intent}: {detail}" if detail else intent),
        intent_class=intent_class(intent),
        read_only=intent_is_read_only(intent),
        requires_input=requires,
        choices={},
        description=str(
            action.get("use_when")
            or action.get("returns")
            or (spec.description if spec else "")
            or ""
        ),
        source_refs=("inspect_lookup_handles.ask_manager_for",),
    )


def _attach_choices(actions: list[PanelAction]) -> list[PanelAction]:
    choices: dict[tuple[str, str], list[Any]] = {}
    for action in actions:
        for field in intent_payload_fields(action.intent):
            value = action.payload.get(field)
            if value is None or _is_placeholder(value):
                continue
            key = (action.intent, field)
            if value not in choices.setdefault(key, []):
                choices[key].append(value)
    out: list[PanelAction] = []
    for action in actions:
        # A proof mutation is already a ready-to-submit command.  Choice
        # aggregation is a read-only context-menu concern; turning `proc.` into
        # `<tactic>` would destroy the exact transition certified by ProofIR.
        if not action.read_only:
            out.append(action)
            continue
        action_choices: dict[str, list[Any]] = {}
        for field in intent_payload_fields(action.intent):
            vals = choices.get((action.intent, field), [])
            if vals:
                action_choices[field] = vals
        out.append(PanelAction(
            intent=action.intent,
            payload=dict(action.payload),
            label=action.label,
            intent_class=action.intent_class,
            read_only=action.read_only,
            requires_input=action.requires_input,
            choices=action_choices,
            description=action.description,
            source_refs=action.source_refs,
            eligibility_reason=action.eligibility_reason,
            state_scope=action.state_scope,
        ))
    return out


def _visible_actions_for_surface(
    view: dict[str, Any],
    phase: str,
    primary: PanelModel | None,
    available: tuple[PanelAction, ...],
) -> tuple[PanelAction, ...]:
    if primary is None:
        filtered = filter_surface_actions(view, phase, phase, available)
        return tuple(_canonicalize_choice_actions(
            _attach_choices(_dedupe_actions(filtered))
        ))
    visible = list(primary.actions)
    for action in available:
        if action.intent_class == INTENT_CLASS_SYMBOL_LOOKUP:
            visible.extend(filter_surface_actions(
                view,
                "global_lookup",
                phase,
                (action,),
            ))
    return tuple(_canonicalize_choice_actions(_attach_choices(_dedupe_actions(visible))))


def _finalize_primary_panel(
    view: dict[str, Any],
    panel: PanelModel,
) -> PanelModel | None:
    """Apply the fact/action visibility contracts exactly once."""
    facts = panel.facts
    if panel.phase != "context_result":
        validate_surface_fact_contract(panel.panel_id, panel.facts)
        facts = tuple(filter_surface_facts(view, panel.panel_id, panel.facts))
    actions = tuple(filter_surface_actions(
        view, panel.panel_id, panel.phase, panel.actions
    ))
    if not facts:
        return None
    return replace(panel, facts=facts, actions=actions)


def _canonicalize_choice_actions(actions: list[PanelAction]) -> list[PanelAction]:
    """Collapse repeated concrete choices into one template action.

    The SurfaceModel action contract is a menu, not a bag of buttons.  If the
    same intent differs only by one payload field (`tactic_forms.name`,
    `operator_lemmas.operator`, ...), expose one action with a placeholder field
    and the concrete values in `choices`.  Renderers may expand that once.
    """
    grouped: dict[tuple[str, str, tuple[tuple[str, Any], ...]], list[PanelAction]] = {}
    order: list[tuple[str, str, tuple[tuple[str, Any], ...]]] = []
    passthrough: list[tuple[int, PanelAction]] = []
    for idx, action in enumerate(actions):
        variable_fields = [
            field for field in intent_payload_fields(action.intent)
            if _choice_values(action, field)
        ]
        if len(variable_fields) != 1:
            passthrough.append((idx, action))
            continue
        field = variable_fields[0]
        base_payload = {
            key: value for key, value in action.payload.items()
            if key != field
        }
        key = (action.intent, field, tuple(sorted(base_payload.items())))
        if key not in grouped:
            order.append(key)
        grouped.setdefault(key, []).append(action)

    collapsed_by_first_index: list[tuple[int, PanelAction]] = []
    for key in order:
        group = grouped[key]
        intent, field, base_items = key
        first = group[0]
        payload = dict(base_items)
        payload[field] = f"<{field}>"
        choices: dict[str, list[Any]] = {}
        for action in group:
            for choice_field, values in action.choices.items():
                target = choices.setdefault(choice_field, [])
                for value in values:
                    if value not in target:
                        target.append(value)
            value = action.payload.get(field)
            if value is not None and not _is_placeholder(value):
                target = choices.setdefault(field, [])
                if value not in target:
                    target.append(value)
        collapsed_by_first_index.append((
            actions.index(first),
            PanelAction(
                intent=intent,
                payload=payload,
                label=f"{intent}: <{field}>",
                intent_class=first.intent_class,
                read_only=first.read_only,
                requires_input=(field,),
                choices=choices,
                description=first.description,
                source_refs=first.source_refs,
                eligibility_reason=first.eligibility_reason,
                state_scope=first.state_scope,
            ),
        ))
    merged = passthrough + collapsed_by_first_index
    return [action for _, action in sorted(merged, key=lambda item: item[0])]


def _choice_values(action: PanelAction, field: str) -> list[Any]:
    values = action.choices.get(field, [])
    if action.intent == "tactic_forms" and field == "name":
        values = [
            value for value in values
            if str(value).strip() in _SUPPORTED_TACTIC_FORM_NAMES
        ]
    return [
        value for value in values
        if value is not None and not _is_placeholder(value)
    ]


def _dedupe_actions(actions: list[PanelAction]) -> list[PanelAction]:
    seen: set[str] = set()
    out: list[PanelAction] = []
    for action in actions:
        key = action.intent + "|" + repr(sorted(action.payload.items()))
        if key in seen:
            continue
        seen.add(key)
        out.append(action)
    return out


def _action_detail(intent: str, payload: dict[str, Any]) -> str:
    for key in ("operator", "name", "symbol", "lemma", "invariant", "claim", "path", "anchor"):
        value = str(payload.get(key) or "").strip()
        if value and not _is_placeholder(value):
            return value
    return ""
