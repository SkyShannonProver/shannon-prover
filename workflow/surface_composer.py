"""Compose the canonical prover presentation surface.

The composer is the only normal-runtime selector between raw workspace facts and
the agent/human presentation.  Producers emit raw facts; renderers consume only
the typed ``SurfaceModel`` built here.
"""
from __future__ import annotations

import re
from typing import Any
from workflow.context_intents import (
    INTENT_CLASS_CONTEXT_TOPIC,
    INTENT_CLASS_PROBE_PREVIEW,
    INTENT_CLASS_SYMBOL_LOOKUP,
    direct_context_request,
    intent_class,
    intent_is_read_only,
    intent_is_retrieval,
    intent_payload_fields,
    intent_spec,
)
from workflow.surface_action_eligibility import (
    filter_surface_actions,
    has_current_call_surface_context,
)
from workflow.surface_action_choices import (
    bridge_probe_claim_choices_for_view,
    call_subgoal_invariant_choices_for_view,
    inv_from_lemma_choices_for_view,
    operator_queries_for_goal,
)
from workflow.surface_model import _drop_empty
from workflow.surface_model import (
    DisplayPolicy,
    PanelAction,
    PanelFact,
    PanelModel,
    SurfaceModel,
    last_action_needs_attention,
    surface_model_to_dict,
)
from workflow.surface_state_predicates import goal_has_program as _current_goal_has_program
from workflow.surface_tactic_forms import tactic_form_names_for_state
from core.easycrypt.analysis.ec_pr_terms import (
    extract_pr_terms as _extract_pr_terms,
    matching_bracket_from as _matching_bracket,
    parse_pr_inner as _parse_pr_inner,
    split_top_level as _split_top_level,
    top_level_colon as _top_level_colon,
    top_level_relation as _top_level_relation,
)
from workflow.surface_whole_program import (
    _PROC_CALL_RE,
    _SETUP_ANNOTATION_RE,
    _SETUP_SUMMARY_RE,
    _WHOLE_PROGRAM_OBSERVATION_LIMIT,
    _WHOLE_PROGRAM_PREFIX_REGION_KINDS,
    _WHOLE_PROGRAM_REGION_COUNT_DELTA_THRESHOLD,
    _WHOLE_PROGRAM_RENDER_REGION_LIMIT,
    _WHOLE_PROGRAM_REORDER_REGION_KIND_PRIORITY,
    _WHOLE_PROGRAM_SETUP_SIGNATURE_LIMIT,
    _WHOLE_PROGRAM_SETUP_SIGNATURE_PREVIEW_LIMIT,
    _WHOLE_PROGRAM_WRAPPER_REGION_KINDS,
    _call_label_positions,
    _call_name_from_statement,
    _current_region,
    _frontier_head_label,
    _has_after_region,
    _has_current_or_earlier_call,
    _has_intervening_guard_before_later_while,
    _has_noncall_prefix_before_later_call,
    _has_region_count_delta,
    _inline_preview,
    _is_current_only_same_shape,
    _is_prefix_block_vs_call_shape,
    _is_same_shape_with_lookahead,
    _is_wrapper_call_shape,
    _is_wrapper_call_side,
    _proc_module_method,
    _region_kind_sequence,
    _scope_entry_head,
    _setup_annotation_index,
    _setup_statement_count,
    _setup_statement_signature,
    _setup_statements,
    _shared_call_label_position_observation,
    _should_show_whole_program_structure,
    _side_has_guard_before_while,
    _statement_is_proc_call,
    _strip_setup_call_tag,
    _visible_call_labels,
    _visible_call_labels_differ,
    _whole_program_observations,
    _whole_program_region_from_entry,
    _whole_program_region_text,
    _whole_program_regions_for_side,
    _wrapper_call_observations,
    _wrapper_call_signature,
)
from workflow.surface_panels import (  # noqa: F401  (facade re-exports)
    PANEL_TITLES,
    _LIVE_VAR_FACT_KEYS,
    _LOAD_BEARING_CALL_TAIL,
    _LOAD_BEARING_RANK,
    _PLACEHOLDER_HANDLE_SYMBOLS,
    _SEQ_POSITION,
    _SUPPORTED_TACTIC_FORM_NAMES,
    _SWAP_OFFSET,
    _applicable_tactic_families,
    _automation_residual_failure,
    _automation_residual_families,
    _branch_sample_alignment,
    _branch_sample_alignment_details,
    _branch_sample_alignment_summary,
    _call_candidate_detail,
    _call_display_facts,
    _call_frontier_fact_items,
    _call_panel,
    _call_raw_audit_fact,
    _call_surface_has_callable_now,
    _callable_display_candidates,
    _compact_exposure_plan,
    _compact_unknown_head_fallback,
    _compact_value,
    _context_result_panel,
    _context_result_title,
    _current_head,
    _current_sample_frontiers,
    _current_scope_has_live_statement,
    _current_scope_setup_has_proc_call,
    _decision_context_panel_facts,
    _deep_actions,
    _deep_panel,
    _display_call_site,
    _display_matched_call_sites,
    _displayable_branch_focus,
    _event_union_skeleton,
    _extract_seq_positions,
    _extract_swap_offsets,
    _families_from_close_with,
    _focus_is_pure,
    _frontier_residual_staging,
    _goal_conclusion_region,
    _goal_is_large_for_surface,
    _goal_precondition_carries_bad_guard,
    _goal_surface,
    _head_label,
    _inline_text,
    _integer_arithmetic_panel_facts,
    _invariant_frame,
    _is_placeholder,
    _is_placeholder_handle,
    _iter_successor_panel_facts,
    _list_residual_shapes,
    _load_bearing_frontier_call,
    _local_patch_loop_fact,
    _lookahead_entries_pairable,
    _lookahead_entry_label,
    _lookahead_item_line,
    _memory_translation_panel_facts,
    _near_frontier_bridge_candidates,
    _near_frontier_bridge_detail,
    _near_frontier_bridge_fact,
    _non_applicable_reason,
    _normalise_program,
    _normalize_head,
    _normalized_inline_text,
    _obligation_shape_panel_facts,
    _opener_panel,
    _paired_lookahead_line,
    _paired_lookahead_lines,
    _parenthesize_event,
    _parse_head_from_text,
    _primary_panel,
    _probability_goal_shape,
    _probability_structure_analysis,
    _probability_structure_summary,
    _probability_tactic_affordances,
    _program_frontier_has_live_facts,
    _program_head_known,
    _programs_are_in_sync,
    _pure_actions,
    _pure_has_split_candidate,
    _pure_panel,
    _pure_tail_has_closing_lemma_route,
    _rcond_branch_callouts,
    _rcond_branch_items,
    _rcond_branch_line,
    _recover_actions,
    _recover_panel,
    _recover_title,
    _render_surgery_skeleton,
    _rewind_targets,
    _scope_frontier_head,
    _scope_frontier_line,
    _scope_frontier_pair_label,
    _scope_position_text,
    _scope_setup_connector,
    _scope_setup_has_proc_call,
    _scope_setup_subject,
    _scope_setup_summary,
    _short_procedure_list,
    _statement_has_program_syntax,
    _strip_label,
    _surgery_lookahead_after_frontier,
    _surgery_where,
    _surgery_where_from_current_scope,
    _swap_frame_items,
    _tactic_family,
    _tactic_mentions_automation,
    _unfoldable_goal_head_facts,
    _up_to_bad_call_compatibility_fact,
    _whole_program_structure_fact,
    _with_decision_context_facts,
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
    available_actions = () if goal_only else tuple(_surface_actions(view))
    primary = None if goal_only else _primary_panel(view, phase, available_actions)
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
    ps = view.get("proof_status") if isinstance(view.get("proof_status"), dict) else {}
    layer = str(ps.get("current_layer") or "").lower()
    focus = str(ps.get("view_focus") or "").lower()
    frontier = view.get("program_frontier") if isinstance(view.get("program_frontier"), dict) else {}
    frontier_focus = str(frontier.get("view_focus") or "").lower()
    call_site_surface = view.get("call_site_surface") if isinstance(view.get("call_site_surface"), dict) else {}
    seq_surface = view.get("seq_cut_surface") if isinstance(view.get("seq_cut_surface"), dict) else {}
    pure_tail_surface = view.get("pure_tail_surface") if isinstance(view.get("pure_tail_surface"), dict) else {}
    goal_type = str(ps.get("goal_type") or "").lower()
    single_sided = goal_type in {"hoare", "phoare", "bdhoare"}
    has_program_goal = _current_goal_has_program(view) or _program_frontier_has_live_facts(view)
    single_program_obligation = _goal_is_single_program_obligation(view)
    if _goal_is_probability_opener(view) and not has_program_goal and not single_program_obligation:
        return "opener"
    if single_program_obligation:
        return "plain"
    if (
        not has_program_goal
        and _goal_surface(view).get("text")
        and (layer in {"ambient_logic", "pure_logic"}
             or focus in {"ambient_logic", "pure_logic"}
             or frontier_focus in {"ambient_logic", "pure_logic"})
    ):
        return "pure_logic"
    if layer == "call_site" or focus == "call_site" or bool(call_site_surface):
        if _call_context_preflight_eligible(view):
            return "call_site"
        return "plain" if single_sided else "deep_surgery"
    if (
        bool(seq_surface)
        or (focus == "seq_cut" and layer not in {"pr", "probability"})
        or layer in {"procedure_body", "seq_cut", "deep_surgery"}
    ):
        return "plain" if single_sided else "deep_surgery"
    if (
        bool(pure_tail_surface)
        or (
            not has_program_goal
            and layer in {"pure_logic", "ambient_logic", "verification_residue"}
        )
    ):
        return "pure_logic"
    return str(ps.get("view_focus") or ps.get("current_layer") or "plain")


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


def _goal_is_single_program_obligation(view: dict[str, Any]) -> bool:
    text = str(_goal_surface(view).get("text") or "")
    if not text:
        return False
    if not re.search(r"(?m)^\s*pre\s*=", text):
        return False
    if not re.search(r"(?m)^\s*post\s*=", text):
        return False
    # Relational/pRHL goals carry explicit side memories; those should keep the
    # surgery surface, not collapse to a one-program bound/procedure obligation.
    if re.search(r"(?m)^\s*&[12]\b|\{[12]\}", text):
        return False
    return bool(
        "[=]" in text
        or "Bound" in text
        or _statement_has_program_syntax(text)
    )


def _call_context_preflight_eligible(view: dict[str, Any]) -> bool:
    current_call = has_current_call_surface_context(view)
    for intent in (
        "call_site_options",
        "call_subgoals",
        "call_invariant_skeleton",
        "inv_from_lemma",
    ):
        preflight = view.get("surface_action_preflight") if isinstance(view, dict) else {}
        results = preflight.get("results") if isinstance(preflight, dict) else []
        for item in results or []:
            if isinstance(item, dict) and item.get("intent") == intent and item.get("eligible"):
                if intent != "call_site_options" and not current_call:
                    continue
                return True
    return False


def _goal_is_probability_opener(view: dict[str, Any]) -> bool:
    ps = view.get("proof_status") if isinstance(view.get("proof_status"), dict) else {}
    if str(ps.get("goal_type") or "").lower() == "probability":
        return True
    if str(ps.get("view_focus") or "").lower() == "probability":
        return True
    if str(ps.get("current_layer") or "").lower() in {"pr", "probability"}:
        return True
    goal = _goal_surface(view)
    return "Pr[" in str(goal.get("text") or "")


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
    handles = view.get("inspect_lookup_handles") if isinstance(view.get("inspect_lookup_handles"), dict) else {}
    asks = handles.get("ask_manager_for") if isinstance(handles, dict) else None
    raw_actions: list[dict[str, Any]] = []
    for ask in asks or []:
        if not isinstance(ask, dict):
            continue
        action = direct_context_request(ask)
        if not _advertised_action(action):
            continue
        raw_actions.append(action)
    actions = [_panel_action_from_request(action) for action in _expand_state_derived_actions(view, raw_actions)]
    return _attach_choices(actions)


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
        if intent == "bridge_probe" and _is_placeholder(payload.get("claim")):
            for claim in bridge_probe_claim_choices_for_view(view):
                expanded = dict(action)
                expanded["payload"] = {**payload, "claim": claim}
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
    if intent_class(intent) == INTENT_CLASS_PROBE_PREVIEW:
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
        if phase == "plain":
            available = tuple(_plain_actions(view, available))
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


def _plain_actions(
    view: dict[str, Any],
    actions: tuple[PanelAction, ...],
) -> list[PanelAction]:
    out = list(actions)
    families = tactic_form_names_for_state(view, "plain", "plain") or frozenset()
    existing = {
        str(action.payload.get("name") or "").strip()
        for action in out
        if action.intent == "tactic_forms"
    }
    order = (
        "wp", "sp", "call", "rnd", "rcondt", "rcondf", "while",
        "rewrite", "apply", "case", "conseq",
    )
    for family in order:
        if family not in families or family not in _SUPPORTED_TACTIC_FORM_NAMES:
            continue
        if family in existing:
            continue
        out.append(PanelAction(
            intent="tactic_forms",
            payload={"name": family},
            label=f"tactic_forms: {family}",
            intent_class=INTENT_CLASS_CONTEXT_TOPIC,
            read_only=True,
            description="valid EasyCrypt forms for this single-sided proof obligation",
            source_refs=("surface_composer.plain", "current_goal"),
        ))
    return out


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
