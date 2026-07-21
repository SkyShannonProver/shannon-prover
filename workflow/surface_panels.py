"""Typed candidate-panel builders for the prover surface.

Extracted verbatim from workflow/surface_composer.py: the seven panel
builders (primary/context-result/recover/call/pure/opener/deep) and their
helpers. Builders organize candidate facts; the composer applies the sole
fact/action eligibility contracts and renderers only render. Imports flow
composer -> panels -> whole-program -> core scanners, never backwards.
"""
from __future__ import annotations

import re
from typing import Any
from workflow.context_intents import (
    INTENT_CLASS_CONTEXT_TOPIC,
    INTENT_CLASS_SYMBOL_LOOKUP,
    intent_class,
    intent_is_read_only,
    intent_is_retrieval,
    intent_payload_fields,
    intent_spec,
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
from workflow.surface_action_preflight import preflight_candidate_evidence
from workflow.surface_markdown import markdown_code_span as _code_span
from workflow.surface_state_predicates import (
    goal_has_program as _current_goal_has_program,
    preferred_procedure_entry_transition,
)
from workflow.surface_structural_facts import (
    checked_seq_sources,
    checked_swap_sources,
    loaded_named_routes,
)
from workflow.surface_tactic_forms import (
    SUPPORTED_TACTIC_FORM_NAMES as _SUPPORTED_TACTIC_FORM_NAMES,
    compose_tactic_form_actions,
)

from core.easycrypt.analysis.ec_pr_terms import (
    extract_pr_terms as _extract_pr_terms,
    matching_bracket_from as _matching_bracket,
    parse_pr_inner as _parse_pr_inner,
    split_top_level as _split_top_level,
    top_level_colon as _top_level_colon,
    top_level_relation as _top_level_relation,
)
from core.easycrypt.analysis.ec_program_statements import (
    statement_is_procedure_call,
)
from workflow.surface_whole_program import (
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


PANEL_TITLES = {
    "deep_surgery": "Surgery -- align or decompose the two sides",
    "single_program": "Single-Program Frontier",
    "failure_recovery": "Recover -- last committed tactic was rejected",
    "call_site": "Call Frontier",
    "context_result": "Requested Context",
    "pure_logic": "Pure Logic Residual",
    "opener": "Probability Goal",
    "relational_program": "Relational Goal",
}


def _program_frontier_has_live_facts(view: dict[str, Any]) -> bool:
    frontier = view.get("program_frontier") if isinstance(view.get("program_frontier"), dict) else {}
    if not frontier:
        return False
    scope = frontier.get("current_frontier_scope") if isinstance(frontier.get("current_frontier_scope"), dict) else {}
    if _current_scope_has_live_statement(scope):
        return True
    alignment = frontier.get("frontier_alignment") if isinstance(frontier.get("frontier_alignment"), dict) else {}
    for row in alignment.get("rows") or []:
        if not isinstance(row, dict):
            continue
        for side in ("left", "right"):
            text = str(row.get(side) or "").strip()
            lowered = text.lower()
            if not text or lowered.startswith("no ") or "no matching" in lowered:
                continue
            if _statement_has_program_syntax(text):
                return True
    return False


def _current_scope_has_live_statement(scope: dict[str, Any]) -> bool:
    if not isinstance(scope, dict):
        return False
    setup = scope.get("setup") if isinstance(scope.get("setup"), dict) else {}
    for side in ("left", "right"):
        entry = setup.get(side) if isinstance(setup.get(side), dict) else {}
        if _statement_has_program_syntax(entry.get("summary")):
            return True
    frontier = scope.get("frontier") if isinstance(scope.get("frontier"), dict) else {}
    for side in ("left", "right"):
        entry = frontier.get(side) if isinstance(frontier.get(side), dict) else {}
        if _statement_has_program_syntax(entry.get("statement")):
            return True
    lookahead = scope.get("lookahead_after_frontier")
    if isinstance(lookahead, list):
        for item in lookahead:
            if isinstance(item, dict) and _statement_has_program_syntax(item.get("statement")):
                return True
    return False


def _statement_has_program_syntax(text: Any) -> bool:
    return bool(re.search(r"<@|<\$|<-|\bwhile\s*\(|\bwhile\b|\bif\s*\(", str(text or "")))


def _goal_surface(view: dict[str, Any]) -> dict[str, Any]:
    goal = view.get("current_goal") if isinstance(view.get("current_goal"), dict) else {}
    if not goal:
        return {}
    lines = goal.get("lines")
    text = str(goal.get("lines_preview") or goal.get("text") or "")
    if not text and isinstance(lines, list):
        text = "\n".join(str(line) for line in lines)
    line_count = goal.get("line_count")
    if line_count is None and isinstance(lines, list):
        line_count = len(lines)
    notice = ""
    if bool(goal.get("truncated")) and bool(goal.get("oversize_consider_undo")):
        notice = (
            "Goal is very large and was truncated here; a destructive lowering "
            "(for example `inline *`) may have exploded it. Consider "
            "`undo_last_step` rather than grinding the giant goal."
        )
    return _drop_empty({
        "title": "Current Goal",
        "text": text,
        "lines": list(lines) if isinstance(lines, list) else None,
        "goal_type": goal.get("goal_type"),
        "truncated": goal.get("truncated"),
        "line_count": line_count,
        "notice": notice,
    })


def _programs_are_in_sync(view: dict[str, Any]) -> bool:
    return "[programs are in sync]" in str(_goal_surface(view).get("text") or "")


def _goal_is_large_for_surface(view: dict[str, Any]) -> bool:
    goal = view.get("current_goal") if isinstance(view.get("current_goal"), dict) else {}
    if bool(goal.get("truncated")):
        return True
    line_count = goal.get("line_count")
    if isinstance(line_count, int):
        return line_count >= 40
    lines = goal.get("lines")
    return isinstance(lines, list) and len(lines) >= 40


def _primary_panel(
    view: dict[str, Any],
    phase: str,
    actions: tuple[PanelAction, ...],
) -> PanelModel | None:
    panel: PanelModel | None
    if phase == "context_result":
        panel = _context_result_panel(view)
    elif phase == "failure_recovery":
        panel = _recover_panel(view, actions)
    elif phase == "call_site":
        panel = _call_panel(view, actions)
    elif phase == "pure_logic":
        panel = _pure_panel(view, actions)
    elif phase == "opener":
        panel = _opener_panel(view, actions)
    elif phase == "deep_surgery":
        panel = _deep_panel(view, actions)
    elif phase == "single_program":
        panel = _single_program_panel(view, actions)
    elif phase == "relational_program":
        panel = _relational_program_panel(view, actions)
    else:
        panel = None
    return panel


def _single_program_panel(
    view: dict[str, Any],
    actions: tuple[PanelAction, ...],
) -> PanelModel:
    """Current one-sided ProgramIR facts, without relational surgery language."""
    frontier = view.get("program_frontier") if isinstance(view.get("program_frontier"), dict) else {}
    scope = frontier.get("current_frontier_scope") if isinstance(frontier.get("current_frontier_scope"), dict) else {}
    facts: list[PanelFact] = []
    setup = scope.get("setup") if isinstance(scope.get("setup"), dict) else {}
    setup_items = []
    for side in ("left", "right"):
        item = setup.get(side) if isinstance(setup.get(side), dict) else {}
        if not item:
            continue
        setup_items.append(_drop_empty({
            "side": side,
            "paths": item.get("paths"),
            "summary": item.get("summary"),
        }))
    if setup_items:
        facts.append(PanelFact(
            "setup_before_frontier",
            "Setup before current frontier",
            setup_items,
            kind="program_ir_fact",
            source_refs=("program_frontier.current_frontier_scope.setup",),
        ))
    current = scope.get("frontier") if isinstance(scope.get("frontier"), dict) else {}
    current_items = []
    for side in ("left", "right"):
        item = current.get(side) if isinstance(current.get(side), dict) else {}
        if item:
            current_items.append(_drop_empty({
                "side": side,
                "path": item.get("path"),
                "head": item.get("head"),
                "statement": item.get("statement"),
            }))
    if current_items:
        facts.append(PanelFact(
            "current_frontier",
            "Current frontier",
            current_items,
            kind="program_ir_fact",
            source_refs=("program_frontier.current_frontier_scope.frontier",),
        ))
    obligation = (
        frontier.get("program_obligation")
        if isinstance(frontier.get("program_obligation"), dict) else {}
    )
    if obligation.get("kind") == "procedure_losslessness":
        facts.append(PanelFact(
            "program_obligation",
            "Procedure losslessness obligation",
            _drop_empty({
                "goal_type": obligation.get("goal_type"),
                "bound": (
                    f"[{obligation.get('bound_relation')}] "
                    f"{obligation.get('bound_value')}"
                ),
                "precondition": obligation.get("precondition"),
                "postcondition": obligation.get("postcondition"),
                "limitations": obligation.get("limitations"),
            }),
            summary=(
                "The current single-program goal is the canonical "
                "`phoare [=] 1%r` encoding of procedure losslessness."
            ),
            details=obligation,
            audit_payload=obligation,
            kind="state_fact",
            role="primary",
            source_refs=("program_frontier.program_obligation",),
            authority=str(obligation.get("authority") or "pretty_text_fallback"),
        ))
    losslessness_fact = _one_sided_losslessness_fact(view)
    if losslessness_fact is not None:
        facts.append(losslessness_fact)
    lookahead = [
        _drop_empty({
            "side": item.get("side"),
            "path": item.get("path"),
            "head": item.get("head"),
            "statement": item.get("statement"),
        })
        for item in scope.get("lookahead_after_frontier") or []
        if isinstance(item, dict)
    ]
    if lookahead:
        facts.append(PanelFact(
            "bounded_lookahead",
            "Next structural statement",
            lookahead[:2],
            kind="program_ir_fact",
            role="supporting",
            source_refs=("program_frontier.current_frontier_scope.lookahead_after_frontier",),
        ))
    seq = view.get("seq_cut_surface") if isinstance(view.get("seq_cut_surface"), dict) else {}
    seq_scope = seq.get("seq_scope") if isinstance(seq.get("seq_scope"), dict) else {}
    if seq_scope:
        facts.append(PanelFact(
            "active_seq_scope",
            "Active seq scope",
            seq_scope,
            kind="program_ir_fact",
            role="supporting",
            source_refs=("seq_cut_surface.seq_scope",),
        ))
    named_routes = _loaded_named_routes_fact(view)
    if named_routes is not None:
        facts.append(named_routes)
    return PanelModel(
        panel_id="single_program",
        phase="single_program",
        title=PANEL_TITLES["single_program"],
        facts=tuple(facts),
        actions=actions,
        display_policy=DisplayPolicy(verbosity="focused"),
        source_refs=("program_frontier.current_frontier_scope", "seq_cut_surface"),
    )


def _relational_program_panel(
    view: dict[str, Any],
    actions: tuple[PanelAction, ...],
) -> PanelModel:
    facts: list[PanelFact] = []
    procedure_entry = _procedure_entry_fact(view)
    if procedure_entry is not None:
        facts.append(procedure_entry)
    named_routes = _loaded_named_routes_fact(view)
    if named_routes is not None:
        facts.append(named_routes)
    return PanelModel(
        panel_id="relational_program",
        phase="relational_program",
        title=PANEL_TITLES["relational_program"],
        facts=tuple(facts),
        actions=actions,
        display_policy=DisplayPolicy(verbosity="focused"),
        source_refs=(
            "program_frontier.procedure_entry_transition",
            "application_context.loaded_named_routes",
        ),
    )


def _procedure_entry_fact(view: dict[str, Any]) -> PanelFact | None:
    transition = preferred_procedure_entry_transition(view)
    if not transition:
        return None
    return PanelFact(
        "procedure_body_entry",
        "Procedure body entry",
        {
            "current_layer": transition["current_layer"],
            "transition": transition["transition"],
            "ready_to_submit": transition["tactic"],
            "effect": transition.get("effect"),
        },
        summary=(
            "ProofIR marks `proc.` as the preferred legal transition that opens "
            "this module-level procedure judgment."
        ),
        kind="program_ir_fact",
        source_refs=("program_frontier.procedure_entry_transition",),
    )


def _context_result_panel(view: dict[str, Any]) -> PanelModel:
    lr = view.get("last_result") if isinstance(view.get("last_result"), dict) else {}
    content = lr.get("content") if isinstance(lr.get("content"), dict) else {}
    facts: list[PanelFact] = []
    if isinstance(content, dict) and content:
        title = str(content.get("title") or "").strip()
        if title:
            facts.append(PanelFact(
                "content_title",
                "Content",
                title,
                kind="manager_result",
                source_refs=("last_result.content.title",),
            ))
        preview = str(content.get("preview") or "").strip()
        if preview:
            facts.append(PanelFact(
                "content_preview",
                "Returned text",
                preview,
                kind="manager_result",
                source_refs=("last_result.content.preview",),
            ))
        for key, label in (
            ("items", "Items"),
            ("notes", "Notes"),
            ("recommendations", "Recommendations"),
            ("goal_info", "Goal info"),
            ("goal_state", "Goal state"),
            ("history", "History"),
            ("latest_transition", "Latest transition"),
            ("result", "Result"),
            ("runtime_note", "Runtime note"),
            ("errors", "Errors"),
        ):
            value = content.get(key)
            if value not in ({}, [], None, ""):
                facts.append(PanelFact(
                    key,
                    label,
                    value,
                    kind="manager_result",
                    source_refs=(f"last_result.content.{key}",),
                ))
    if not facts:
        fallback = str(lr.get("result") or lr.get("message") or "").strip()
        facts.append(PanelFact(
            "result",
            "Result",
            fallback or "The manager returned no additional context for this state.",
            kind="manager_result",
            source_refs=("last_result",),
        ))
    return PanelModel(
        panel_id="context_result",
        phase="context_result",
        title=_context_result_title(lr, content),
        facts=tuple(facts),
        actions=(),
        display_policy=DisplayPolicy(
            lead_before_goal=True,
            compact_goal=True,
            verbosity="answer",
            show_actions=False,
        ),
        source_refs=("last_result",),
    )


def _context_result_title(
    last_result: dict[str, Any],
    content: dict[str, Any],
) -> str:
    intent = str(last_result.get("intent") or "context").strip()
    payload = last_result.get("payload") if isinstance(last_result.get("payload"), dict) else {}
    label = str(content.get("title") or "").strip()
    if not label:
        for key in ("topic", "symbol", "operator", "name", "lemma", "invariant", "command"):
            value = str(payload.get(key) or "").strip()
            if value:
                label = value
                break
    return f"Requested: `{intent}`" + (f" -- `{label}`" if label else "")


def _recover_panel(
    view: dict[str, Any],
    actions: tuple[PanelAction, ...],
) -> PanelModel:
    focus: dict[str, Any] = {}
    lr = view.get("last_result") if isinstance(view.get("last_result"), dict) else {}
    rejected_tactic = str(lr.get("tactic") or _strip_label(str(focus.get("rejected") or ""))).strip()
    rejected_family = _tactic_family(rejected_tactic)
    automation_residual = _automation_residual_failure(lr, rejected_tactic)
    procedure_entry = _procedure_entry_fact(view)
    head = _current_head(view, focus)
    applicable = (
        _automation_residual_families(view)
        if automation_residual else
        ["proc"] if procedure_entry is not None else
        _applicable_tactic_families(head, focus, view)
    )
    facts: list[PanelFact] = []
    if rejected_tactic or str(lr.get("result") or "").strip():
        facts.append(PanelFact(
            "rejected_tactic",
            "Rejected tactic",
            _drop_empty({
                "tactic": rejected_tactic,
                "family": rejected_family,
                "result": lr.get("result") or focus.get("rejected"),
                "error_summary": lr.get("error_summary"),
            }),
            kind="last_result",
            source_refs=("last_result",),
        ))
    if automation_residual:
        facts.append(PanelFact(
            "automation_residual_failure",
            "Automation residual failure",
            _drop_empty({
                "classification": "auto/SMT residual did not close",
                "evidence": lr.get("error_summary") or lr.get("result"),
                "meaning": (
                    "EasyCrypt could not discharge the residual obligation with "
                    "the supplied automation facts; this is not evidence that "
                    "the automation family is structurally inapplicable."
                ),
                "repair_surface": [
                    "same automation family may still fit with additional visible facts or lemmas",
                    "goal-derived operator lemmas, rewrites, or a local split may be relevant",
                ],
            }),
            kind="diagnostic",
            source_refs=("last_result", "current_goal"),
        ))
    if procedure_entry is not None:
        facts.append(procedure_entry)
    else:
        facts.append(PanelFact(
            "current_frontier_head",
            "Current frontier head",
            head["label"],
            kind="state_fact",
            source_refs=("program_frontier",),
        ))
    if applicable:
        facts.append(PanelFact(
            "applicable_tactic_families",
            "Residual repair families" if automation_residual else "Applicable tactic families",
            applicable,
            kind="route_options",
            source_refs=("last_result", "current_goal") if automation_residual else ("program_frontier",),
        ))
        if rejected_family and rejected_family not in applicable and not automation_residual:
            facts.append(PanelFact(
                "non_applicable_reason",
                "Why the rejected family does not fit this head",
                _non_applicable_reason(rejected_family, head, applicable),
                kind="diagnostic",
                source_refs=("last_result", "program_frontier"),
            ))
    else:
        fallback = _compact_unknown_head_fallback(focus)
        if fallback:
            facts.append(PanelFact(
                "compact_fallback",
                "Compact fallback",
                fallback,
                kind="fallback",
            source_refs=("program_frontier", "proof_status"),
            ))
    close_with = focus.get("close_with")
    if isinstance(close_with, list) and close_with and not _program_head_known(head):
        facts.append(PanelFact(
            "close_with",
            "Possible pure/probability closures",
            close_with[:6],
            kind="route_options",
            source_refs=("proof_status", "current_goal"),
        ))
    rewind_targets = _rewind_targets(view)
    if isinstance(rewind_targets, list) and rewind_targets:
        facts.append(PanelFact(
            "available_rewind_targets",
            "Available rewind targets",
            rewind_targets[:6],
            kind="control_options",
            source_refs=("structural_checkpoints", "recovery_diagnosis_surface"),
        ))
    recovery_actions = compose_tactic_form_actions(
        view,
        "recovery",
        "failure_recovery",
        actions,
        requested_names=applicable,
    )
    if automation_residual:
        recovery_actions.extend(
            action for action in actions
            if action.intent in {"operator_lemmas", "lookup_symbol"}
        )
    panel_actions = tuple(recovery_actions)
    return PanelModel(
        panel_id="recovery",
        phase="failure_recovery",
        title=_recover_title(lr),
        facts=tuple(facts),
        actions=panel_actions,
        display_policy=DisplayPolicy(
            lead_before_goal=True,
            verbosity="focused",
            show_actions=True,
        ),
        source_refs=("last_result", "program_frontier", "proof_status"),
    )


def _recover_title(last_result: dict[str, Any]) -> str:
    result = str(last_result.get("result") or "").lower()
    proof_state = str(last_result.get("proof_state") or "").lower()
    if "reject" in result or "error" in result:
        return PANEL_TITLES["failure_recovery"]
    if any(
        marker in (result + " " + proof_state)
        for marker in (
            "no progress",
            "no-progress",
            "no effect",
            "did not change",
            "auto-revert",
            "reverted",
        )
    ):
        return "Recover -- last action made no progress"
    return "Recover -- revise the previous step"


def _rewind_targets(view: dict[str, Any]) -> list[str]:
    out: list[str] = []
    recovery = view.get("recovery_diagnosis_surface")
    if isinstance(recovery, dict):
        for item in recovery.get("related_checkpoints") or []:
            if not isinstance(item, dict):
                continue
            label = str(item.get("label") or item.get("checkpoint_id") or "").strip()
            cid = str(item.get("checkpoint_id") or "").strip()
            why = str(item.get("why_checkpoint") or "").strip()
            text = label
            if cid and cid not in text:
                text += f" (`{cid}`)"
            if why:
                text += f" -- {why}"
            if text:
                out.append(text)
    checkpoints = view.get("structural_checkpoints")
    if isinstance(checkpoints, dict):
        for item in checkpoints.get("items") or checkpoints.get("checkpoints") or []:
            if not isinstance(item, dict):
                continue
            cid = str(item.get("checkpoint_id") or "").strip()
            why = str(item.get("why_checkpoint") or "").strip()
            step = item.get("committed_step_index")
            tactic = str(item.get("committed_tactic") or "").strip()
            parts = []
            if cid:
                parts.append(f"`{cid}`")
            if step is not None:
                parts.append(f"step {step}")
            if tactic:
                parts.append(tactic)
            text = " -- ".join(parts)
            if why:
                text += f" ({why})"
            if text:
                out.append(text)
    return out[:8]


def _call_panel(
    view: dict[str, Any],
    actions: tuple[PanelAction, ...],
) -> PanelModel:
    cs = view.get("call_site_surface") if isinstance(view.get("call_site_surface"), dict) else {}
    facts: list[PanelFact] = []
    facts.extend(_call_display_facts(view))
    losslessness_fact = _one_sided_losslessness_fact(view)
    if losslessness_fact is not None:
        facts.append(losslessness_fact)
    facts.extend(_call_frontier_fact_items(view))
    uptobad = _up_to_bad_call_compatibility_fact(view)
    if uptobad is not None:
        facts.append(uptobad)
    return PanelModel(
        panel_id="call_site",
        phase="call_site",
        title=PANEL_TITLES["call_site"],
        facts=tuple(facts),
        actions=actions,
        display_policy=DisplayPolicy(verbosity="normal"),
        source_refs=("call_site_surface",),
    )


def _call_display_facts(view: dict[str, Any]) -> list[PanelFact]:
    cs = view.get("call_site_surface") if isinstance(view.get("call_site_surface"), dict) else {}
    facts: list[PanelFact] = []
    candidates = _callable_display_candidates(cs)
    if candidates:
        summary = "; ".join(
            f"`{item['symbol']}` at " + " / ".join(item.get("frontier", []))
            for item in candidates
            if item.get("symbol")
        )
        details = [
            _call_candidate_detail(item)
            for item in candidates
            if _call_candidate_detail(item)
        ]
        facts.append(PanelFact(
            "direct_current_call",
            "Direct current call",
            {"candidates": candidates},
            kind="state_fact",
            role="primary",
            summary=summary,
            details=details,
            audit_payload=_drop_empty({
                "callable_now": cs.get("callable_now"),
                "frontier_live_named_handles": cs.get("frontier_live_named_handles"),
                "named_handles": cs.get("named_handles"),
            }),
            source_refs=(
                "call_site_surface.callable_now",
                "call_site_surface.frontier_live_named_handles",
                "call_site_surface.named_handles",
            ),
        ))

    blocked_handles = []
    for handle in cs.get("named_handles") or []:
        if not isinstance(handle, dict) or handle.get("callable_now"):
            continue
        if _is_placeholder_handle(handle):
            continue
        symbol = str(handle.get("symbol") or handle.get("name") or "").strip()
        if not symbol:
            continue
        blocked_handles.append(_drop_empty({
            "symbol": symbol,
            "status": "not callable in the current view",
            "frontier_live": handle.get("frontier_live"),
            "procedures": _short_procedure_list(handle.get("procedures")),
        }))
    if blocked_handles:
        facts.append(PanelFact(
            "blocked_named_handles",
            "Named handles not currently callable",
            blocked_handles[:6],
            kind="state_fact",
            role="diagnostic",
            source_refs=(
                "call_site_surface.named_handles",
                "call_site_surface.frontier_blockers",
            ),
        ))

    near_frontier_fact = _near_frontier_bridge_fact(cs)
    if near_frontier_fact is not None:
        facts.append(near_frontier_fact)

    blockers = cs.get("frontier_blockers")
    if blockers not in ({}, [], None, ""):
        facts.append(PanelFact(
            "frontier_blockers",
            "Frontier blockers",
            _compact_value(blockers),
            kind="state_fact",
            role="diagnostic",
            source_refs=("call_site_surface.frontier_blockers",),
        ))

    if _call_surface_has_callable_now(view):
        templates = cs.get("named_call_templates")
        if templates not in ({}, [], None, ""):
            facts.append(PanelFact(
                "named_call_templates",
                "Named call templates",
                _compact_value(templates),
                kind="state_fact",
                role="supporting",
                source_refs=("call_site_surface.named_call_templates",),
            ))
    return facts


def _one_sided_losslessness_fact(view: dict[str, Any]) -> PanelFact | None:
    cs = view.get("call_site_surface") if isinstance(view.get("call_site_surface"), dict) else {}
    one_sided = (
        cs.get("one_sided_call_surface")
        if isinstance(cs.get("one_sided_call_surface"), dict) else {}
    )
    handles = [
        item
        for item in one_sided.get("visible_lossless_handles") or []
        if isinstance(item, dict) and item.get("symbol") and item.get("procedure")
    ]
    if not handles:
        return None
    details = [
        _drop_empty({
            "lemma": item.get("symbol"),
            "live_procedure": item.get("procedure"),
            "declared_procedure": item.get("declared_procedure"),
            "module_bindings": item.get("parameter_bindings"),
            "module_arguments": item.get("module_argument_terms"),
            "instantiated_lemma_head": item.get("instantiated_lemma_head"),
            "call_template": item.get("call_template"),
            "required_premises": item.get("required_premises"),
            "match_kind": item.get("match_kind"),
            "verification_status": item.get("verification_status"),
            "authority": item.get("authority"),
        })
        for item in handles[:5]
    ]
    summary_parts = []
    for item in details:
        text = f"`{item['lemma']}` matches live `{item['live_procedure']}`"
        bindings = item.get("module_bindings")
        if isinstance(bindings, dict) and bindings:
            rendered = ", ".join(
                f"`{name}` -> `{value}`" for name, value in bindings.items()
            )
            text += f" with {rendered}"
        premises = item.get("required_premises")
        if isinstance(premises, list) and premises:
            text += "; required premise: " + ", ".join(
                f"`{premise}`" for premise in premises
            )
        if item.get("call_template"):
            text += f"; instantiated form: `{item['call_template']}`"
        summary_parts.append(text)
    return PanelFact(
        "one_sided_losslessness_certificates",
        "Loaded losslessness certificates",
        {"candidates": details},
        kind="state_fact",
        role="primary",
        summary="; ".join(summary_parts),
        details=details,
        audit_payload=handles[:5],
        source_refs=(
            "call_site_surface.one_sided_call_surface.visible_lossless_handles",
            "application_context.one_sided_losslessness_candidates",
        ),
        authority="loaded_declaration_shape_match",
    )


def _near_frontier_bridge_fact(cs: dict[str, Any]) -> PanelFact | None:
    near_frontier = _near_frontier_bridge_candidates(cs)
    if not near_frontier:
        return None
    summary = "; ".join(
        f"`{item['symbol']}` needs frontier exposure"
        for item in near_frontier
        if item.get("symbol")
    )
    details = [
        _near_frontier_bridge_detail(item)
        for item in near_frontier
        if _near_frontier_bridge_detail(item)
    ]
    return PanelFact(
        "near_frontier_bridge",
        "Near-frontier bridge",
        {"candidates": near_frontier},
        kind="state_fact",
        role="primary",
        summary=summary,
        details=details,
        audit_payload=_drop_empty({
            "named_handles": cs.get("named_handles"),
            "exposure": cs.get("exposure"),
            "frontier_blockers": cs.get("frontier_blockers"),
        }),
        source_refs=(
            "call_site_surface.named_handles",
            "call_site_surface.exposure",
        ),
    )


def _callable_display_candidates(cs: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen: set[tuple[str, tuple[str, ...]]] = set()
    pools = [
        item for item in cs.get("callable_now") or []
        if isinstance(item, dict)
    ]
    pools.extend(
        item for item in cs.get("frontier_live_named_handles") or []
        if isinstance(item, dict) and item.get("callable_now")
    )
    pools.extend(
        item for item in cs.get("named_handles") or []
        if isinstance(item, dict) and item.get("callable_now")
    )
    for handle in pools:
        if _is_placeholder_handle(handle):
            continue
        symbol = str(handle.get("symbol") or handle.get("name") or "").strip()
        if not symbol:
            continue
        sites = _display_matched_call_sites(handle)
        key = (symbol, tuple(sites))
        if key in seen:
            continue
        seen.add(key)
        candidate = _drop_empty({
            "symbol": symbol,
            "frontier": sites,
            "procedures": _short_procedure_list(handle.get("procedures")),
            "source": handle.get("source"),
            "call_candidate_kind": handle.get("call_candidate_kind"),
        })
        candidates.append(candidate)
    return candidates


def _near_frontier_bridge_candidates(cs: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen: set[tuple[str, tuple[str, ...]]] = set()
    for handle in cs.get("named_handles") or []:
        if not isinstance(handle, dict) or _is_placeholder_handle(handle):
            continue
        if handle.get("callable_now") or handle.get("frontier_live"):
            continue
        if not handle.get("requires_cut_to_frontier"):
            continue
        resolved = (
            handle.get("exact_signature_known")
            or handle.get("instantiation_binding_status") == "has_call_elaboration"
            or handle.get("name_resolution_status") == "resolved_local_declaration"
        )
        if not resolved:
            continue
        symbol = str(handle.get("symbol") or handle.get("name") or "").strip()
        if not symbol:
            continue
        sites = _display_matched_call_sites(handle)
        if not sites:
            continue
        key = (symbol, tuple(sites))
        if key in seen:
            continue
        seen.add(key)
        candidate = _drop_empty({
            "symbol": symbol,
            "status": "needs frontier exposure before call",
            "frontier": sites,
            "procedures": _short_procedure_list(handle.get("procedures")),
            "call_candidate_kind": handle.get("call_candidate_kind"),
            "frontier_status": handle.get("frontier_status"),
            "exposure": _compact_exposure_plan(cs.get("exposure")),
        })
        candidates.append(candidate)
    return candidates


def _compact_exposure_plan(exposure: Any) -> dict[str, Any]:
    if not isinstance(exposure, dict):
        return {}
    action = exposure.get("action") if isinstance(exposure.get("action"), dict) else {}
    return _drop_empty({
        "symbol": exposure.get("symbol"),
        "kind": action.get("kind"),
        "tactic_shape": action.get("tactic_shape"),
        "tactic_family": action.get("tactic_family"),
        "reason": action.get("reason"),
    })


def _near_frontier_bridge_detail(item: dict[str, Any]) -> str:
    symbol = str(item.get("symbol") or "").strip()
    frontier = item.get("frontier") if isinstance(item.get("frontier"), list) else []
    if not symbol or not frontier:
        return ""
    text = f"`{symbol}` matches " + " / ".join(str(x) for x in frontier)
    exposure = item.get("exposure") if isinstance(item.get("exposure"), dict) else {}
    shape = str(exposure.get("tactic_shape") or "").strip()
    if shape:
        text += f"; exposure shape: `{shape}`"
    return text


def _display_matched_call_sites(handle: dict[str, Any]) -> list[str]:
    out: list[str] = []
    matched = handle.get("matched_call_sites")
    if isinstance(matched, list):
        for site in matched:
            if isinstance(site, dict):
                line = _display_call_site(site)
                if line:
                    out.append(line)
    if out:
        return out
    site_ids = handle.get("frontier_call_site_ids") or handle.get("live_call_site_ids")
    if isinstance(site_ids, list):
        return [str(item) for item in site_ids if str(item).strip()]
    return []


def _display_call_site(site: dict[str, Any]) -> str:
    side = str(site.get("side") or "").strip()
    path = str(site.get("statement_path") or "").strip()
    proc = str(site.get("procedure") or "").strip()
    prefix = ":".join(part for part in (side, path) if part)
    if prefix and proc:
        return f"{prefix} `{proc}`"
    return prefix or (f"`{proc}`" if proc else "")


def _short_procedure_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        text = str(item or "").strip()
        if not text:
            continue
        out.append(text)
    return out[:4]


def _call_candidate_detail(item: dict[str, Any]) -> str:
    symbol = str(item.get("symbol") or "").strip()
    frontier = item.get("frontier") if isinstance(item.get("frontier"), list) else []
    if not symbol or not frontier:
        return ""
    return f"`{symbol}` matches " + " / ".join(str(x) for x in frontier)


_PLACEHOLDER_HANDLE_SYMBOLS = {
    "lemma", "pair", "goal", "inv", "invariant", "predicate", "tac", "tactic",
    "pre", "post", "operator", "symbol", "handle", "name",
}


def _is_placeholder_handle(handle: dict[str, Any]) -> bool:
    sym = str(handle.get("symbol") or handle.get("name") or "").strip()
    if not sym:
        return True
    low = sym.lower()
    if low in _PLACEHOLDER_HANDLE_SYMBOLS:
        return True
    text = " ".join(str(handle.get(k) or "") for k in ("why_visible", "tactic_shape", "template")).lower()
    return "placeholder" in text or "route-selection context" in text


def _call_surface_has_callable_now(view: dict[str, Any]) -> bool:
    cs = view.get("call_site_surface") if isinstance(view.get("call_site_surface"), dict) else {}
    if cs.get("callable_now"):
        return True
    for handle in cs.get("named_handles") or []:
        if isinstance(handle, dict) and handle.get("callable_now"):
            return True
    return False


def _call_frontier_fact_items(view: dict[str, Any]) -> list[PanelFact]:
    app = view.get("application_context") if isinstance(view.get("application_context"), dict) else {}
    out: list[PanelFact] = []
    cfs = app.get("call_frontier_structure") if isinstance(app.get("call_frontier_structure"), dict) else {}
    aliases = [
        f"`{item.get('alias')}` -> `{item.get('resolves_to')}`"
        for item in cfs.get("module_aliases") or []
        if isinstance(item, dict) and item.get("alias") and item.get("resolves_to")
    ]
    if aliases:
        out.append(PanelFact(
            "module_aliases",
            "Module aliases",
            aliases,
            role="supporting",
            source_refs=("application_context.call_frontier_structure.module_aliases",),
        ))
    adversaries = [
        str(item.get("name") or "").strip()
        for item in cfs.get("abstract_adversaries") or []
        if isinstance(item, dict) and str(item.get("name") or "").strip()
    ]
    if adversaries:
        out.append(PanelFact(
            "abstract_adversary_glob",
            "Abstract-adversary glob frame",
            "abstract adversary " + ", ".join(f"`{name}`" for name in adversaries) + " exposes a `={glob ...}` frame fact",
            role="supporting",
            source_refs=("application_context.call_frontier_structure.abstract_adversaries",),
        ))
    preview = app.get("inline_preview") if isinstance(app.get("inline_preview"), dict) else {}
    if preview:
        stops = preview.get("inline_stops_at") or preview.get("call_at") or []
        stop_text = ", ".join(f"`{x}`" for x in stops) if isinstance(stops, list) else str(stops)
        call = str(preview.get("call") or "").strip()
        text = ""
        if stop_text:
            text = (f"{call} -- " if call else "") + f"STOPS at {stop_text}"
        if text:
            out.append(PanelFact(
                "inline_preview",
                "Inline preview",
                text,
                role="supporting",
                source_refs=("application_context.inline_preview",),
            ))
    cs = view.get("call_site_surface") if isinstance(view.get("call_site_surface"), dict) else {}
    scope: list[str] = []
    for blocker in cs.get("frontier_blockers") or []:
        if not isinstance(blocker, dict):
            continue
        if blocker.get("kind") != "named_call_subject_absent_at_frontier":
            continue
        subject = ", ".join(str(x) for x in blocker.get("subject_procedures") or [] if x)
        live = ", ".join(str(x) for x in blocker.get("frontier_live_procedures") or [] if x)
        if subject or live:
            scope.append(f"subject procedures: {subject}; frontier-live procedures: {live}")
    if scope:
        out.append(PanelFact(
            "frontier_scope",
            "Frontier scope",
            scope,
            role="diagnostic",
            source_refs=("call_site_surface.frontier_blockers",),
        ))
    ledger = view.get("frame_obligation_ledger") if isinstance(view.get("frame_obligation_ledger"), dict) else {}
    required = ledger.get("required_later") if isinstance(ledger, dict) else None
    if isinstance(required, list) and required:
        out.append(PanelFact(
            "frame_required_later",
            "Frame facts required later",
            required[:6],
            role="supporting",
            source_refs=("frame_obligation_ledger.required_later",),
        ))
    return out


def _pure_panel(
    view: dict[str, Any],
    actions: tuple[PanelAction, ...],
) -> PanelModel:
    pt = view.get("pure_tail_surface") if isinstance(view.get("pure_tail_surface"), dict) else {}
    facts: list[PanelFact] = []
    intro_routes = [
        _drop_empty({"submit": item.get("submit"), "why": item.get("why"), "constructor": item.get("constructor")})
        for item in pt.get("inductive_intro_routes") or []
        if isinstance(item, dict) and item.get("submit")
    ]
    if intro_routes:
        facts.append(PanelFact(
            "inductive_intro_routes",
            "Inductive intro constructors",
            intro_routes,
            kind="state_fact",
            source_refs=("pure_tail_surface.inductive_intro_routes",),
        ))
    distribution_fact = _distribution_certificates_fact(view)
    if distribution_fact is not None:
        facts.append(distribution_fact)
    mechanical_fact = _mechanical_goal_matches_fact(
        view,
        source="pure_tail_surface",
    )
    if mechanical_fact is not None:
        facts.append(mechanical_fact)
    hypothesis_graph = pt.get("local_hypothesis_graph") if isinstance(pt.get("local_hypothesis_graph"), dict) else {}
    if hypothesis_graph.get("order_chains"):
        facts.append(PanelFact(
            "local_hypothesis_graph",
            "Local order chains",
            hypothesis_graph.get("order_chains"),
            kind="state_fact",
            source_refs=("pure_tail_surface.local_hypothesis_graph",),
        ))
    facts.extend(_iter_successor_panel_facts(pt))
    facts.extend(_integer_arithmetic_panel_facts(pt))
    facts.extend(_list_normalization_panel_facts(pt))
    facts.extend(_map_update_transport_panel_facts(pt))
    for key, label in (
        ("local_lemmas", "Matching local lemma routes"),
        ("alignment_gaps", "Alignment gaps"),
        ("gap_analysis", "Alignment gap facts"),
        ("membership_sources", "Membership decomposition sources"),
        ("map_update_lookup_cases", "Map-update lookup cases"),
        ("existential_witness_candidates", "Witness candidates"),
    ):
        value = pt.get(key)
        if value not in ({}, [], None, ""):
            facts.append(PanelFact(key, label, value, source_refs=(f"pure_tail_surface.{key}",)))
    return PanelModel(
        panel_id="pure_logic",
        phase="pure_logic",
        title=PANEL_TITLES["pure_logic"],
        facts=tuple(facts),
        actions=actions,
        display_policy=DisplayPolicy(verbosity="normal"),
        source_refs=("pure_tail_surface", "current_goal"),
    )


def _distribution_certificates_fact(view: dict[str, Any]) -> PanelFact | None:
    pure = view.get("pure_tail_surface") if isinstance(view.get("pure_tail_surface"), dict) else {}
    raw_items = [
        item for item in pure.get("distribution_certificates") or []
        if isinstance(item, dict)
        and item.get("lemma")
        and item.get("certificate_kind")
    ]
    if not raw_items:
        return None
    details: list[dict[str, Any]] = []
    cardinality = ""
    cardinality_facts: list[dict[str, Any]] = []
    for item in raw_items[:6]:
        kind = str(item.get("certificate_kind") or "")
        if kind == "distribution_losslessness":
            details.append(_drop_empty({
                "kind": "losslessness",
                "lemma": item.get("lemma"),
                "distribution": item.get("distribution"),
                "loaded_conclusion": item.get("declared_conclusion"),
                "current_goal_form": item.get("goal_form"),
                "remaining_premises": item.get("required_premises"),
            }))
        elif kind == "finite_interval_point_mass":
            cardinality = cardinality or str(item.get("interval_cardinality") or "")
            for support in item.get("loaded_supporting_facts") or []:
                if not isinstance(support, dict) or not support.get("lemma"):
                    continue
                compact = _drop_empty({
                    "lemma": support.get("lemma"),
                    "fact": support.get("fact"),
                    "remaining_premises": support.get("required_premises"),
                })
                if compact not in cardinality_facts:
                    cardinality_facts.append(compact)
            bindings = item.get("parameter_bindings") if isinstance(item.get("parameter_bindings"), dict) else {}
            details.append(_drop_empty({
                "kind": "finite-interval point mass",
                "lemma": item.get("lemma"),
                "distribution": item.get("distribution"),
                "loaded_identity": item.get("declared_conclusion"),
                "interval_bindings": _drop_empty({
                    "lower": bindings.get("i"),
                    "upper": bindings.get("j"),
                    "point": "current point-mass point",
                }),
                "remaining_premise_shapes": [
                    _distribution_premise_shape(premise)
                    for premise in item.get("required_premises") or []
                    if premise
                ],
            }))
    if not details:
        return None
    rendered_details = list(details)
    if cardinality or cardinality_facts:
        rendered_details.append(_drop_empty({
            "kind": "interval cardinality",
            "expression": cardinality,
            "loaded_facts": [
                f"{item.get('lemma')}: {item.get('fact')}"
                for item in cardinality_facts
                if item.get("lemma") and item.get("fact")
            ],
        }))
    return PanelFact(
        "distribution_certificates",
        "Loaded distribution facts",
        _drop_empty({
            "matches": details,
            "interval_cardinality": cardinality,
            "loaded_cardinality_facts": cardinality_facts,
        }),
        summary=(
            "Loaded declarations structurally bound to the current distribution "
            "obligation. They expose identities and premises; they do not select "
            "a proof command or discharge the remaining arithmetic."
        ),
        details=rendered_details,
        audit_payload=raw_items[:6],
        kind="state_fact",
        source_refs=("pure_tail_surface.distribution_certificates",),
    )


def _distribution_premise_shape(premise: str) -> str:
    text = str(premise or "").strip()
    if "\\in" in text and "dinter" in text:
        return "current point membership in the displayed interval"
    return text


def _group_mechanical_matches(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Compress structural siblings without hiding any loaded lemma names."""
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    order: list[tuple[Any, ...]] = []
    for item in items:
        kind = str(item.get("match_kind") or "")
        if kind == "loaded_structural_fingerprint":
            key = (
                kind,
                tuple(str(x) for x in item.get("shared_structures") or []),
                tuple(str(x) for x in item.get("shared_types") or []),
                tuple(str(x) for x in item.get("shared_symbols") or []),
                tuple(str(x) for x in item.get("shared_applied_symbols") or []),
            )
        else:
            key = (kind, str(item.get("lemma") or ""))
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(item)

    out: list[dict[str, Any]] = []
    for key in order:
        group = groups[key]
        first = group[0]
        lemmas = [str(item.get("lemma") or "") for item in group if item.get("lemma")]
        premises = {
            str(item.get("lemma") or ""): item.get("required_premises")
            for item in group
            if item.get("lemma") and item.get("required_premises")
        }
        out.append(_drop_empty({
            "lemmas": lemmas,
            "match": (
                first.get("match_kind")
                if first.get("match_kind") != "loaded_structural_fingerprint"
                else None
            ),
            "shared_symbols": first.get("shared_symbols"),
            "shared_structures": first.get("shared_structures"),
            "shared_types": first.get("shared_types"),
            "shared_applied_symbols": first.get("shared_applied_symbols"),
            "required_premises": premises,
            "parameter_bindings": first.get("parameter_bindings"),
            "declared_procedure": first.get("declared_procedure"),
            "instantiated_procedure": first.get("instantiated_procedure"),
            "direct_application": first.get("direct_application"),
        }))
    return out


def _mechanical_goal_matches_fact(
    view: dict[str, Any],
    *,
    source: str,
    excluded_lemmas: set[str] | None = None,
) -> PanelFact | None:
    container = view.get(source) if isinstance(view.get(source), dict) else {}
    raw_items = [
        item for item in container.get("mechanical_goal_candidates") or []
        if (
            isinstance(item, dict)
            and item.get("lemma")
            and item.get("match_kind") != "loaded_left_inverse_support"
            and str(item.get("lemma") or "") not in (excluded_lemmas or set())
        )
    ]
    grouped = _group_mechanical_matches(raw_items)
    if not grouped:
        return None
    return PanelFact(
        "mechanical_goal_candidates",
        "Loaded-context structural matches",
        grouped[:8],
        summary=(
            "Loaded declarations whose exact conclusion or structural fingerprint "
            "matches the current goal. Full declarations remain in audit JSON."
        ),
        details=grouped[:8],
        audit_payload=raw_items[:8],
        kind="state_fact",
        source_refs=(f"{source}.mechanical_goal_candidates",),
    )


def _loaded_named_routes_fact(view: dict[str, Any]) -> PanelFact | None:
    routes = list(loaded_named_routes(view))
    if not routes:
        return None
    return PanelFact(
        "loaded_named_routes",
        "Loaded named route matches",
        routes,
        summary=(
            "Typed ProofIR matched these loaded names to the current goal shape. "
            "They are route evidence, not EasyCrypt-preflighted submissions."
        ),
        details=routes,
        audit_payload=routes,
        kind="state_fact",
        source_refs=("application_context.loaded_named_routes",),
    )


def _opener_panel(
    view: dict[str, Any],
    actions: tuple[PanelAction, ...],
) -> PanelModel:
    goal = _goal_surface(view)
    text = str(goal.get("text") or "")
    pr_shape = _probability_structure_analysis(text)
    facts: list[PanelFact] = []
    verified_routes = _verified_pr_bridge_routes_fact(view)
    if verified_routes is not None:
        facts.append(verified_routes)
    endpoint_fact = _pr_endpoint_matches_fact(view)
    if endpoint_fact is not None:
        facts.append(endpoint_fact)
    bound_routes_fact = _pr_bound_routes_fact(view)
    if bound_routes_fact is not None:
        facts.append(bound_routes_fact)
    mechanical_fact = _mechanical_goal_matches_fact(
        view,
        source="application_context",
    )
    if mechanical_fact is not None:
        facts.append(mechanical_fact)
    named_routes = _loaded_named_routes_fact(view)
    if named_routes is not None:
        facts.append(named_routes)
    facts.append(
        PanelFact(
            "probability_structure",
            "Probability structure",
            _probability_structure_summary(pr_shape),
            kind="state_fact",
            source_refs=("current_goal", "proof_status"),
        )
    )
    affordances = _probability_tactic_affordances(pr_shape)
    if (
        affordances
        and endpoint_fact is None
        and bound_routes_fact is None
        and mechanical_fact is None
        and named_routes is None
        and verified_routes is None
    ):
        facts.append(PanelFact(
            "tactic_affordances",
            "Tactic applicability",
            affordances,
            kind="state_fact",
            source_refs=("current_goal", "tactic_forms"),
        ))
    if (
        endpoint_fact is None
        and bound_routes_fact is None
        and mechanical_fact is None
        and named_routes is None
        and verified_routes is None
    ):
        facts.extend(_unfoldable_goal_head_facts(view))
    return PanelModel(
        panel_id="opener",
        phase="opener",
        title=PANEL_TITLES["opener"],
        facts=tuple(facts),
        actions=actions,
        display_policy=DisplayPolicy(verbosity="normal"),
        source_refs=("current_goal", "facts_and_diagnostics"),
    )


def _verified_pr_bridge_routes_fact(view: dict[str, Any]) -> PanelFact | None:
    candidates = preflight_candidate_evidence(view, "pr_bridge_routes")
    if not candidates:
        return None
    ready_count = sum(
        1 for candidate in candidates
        if isinstance(candidate.get("submit"), dict)
    )
    details = [
        _drop_empty({
            "route": f"verified route {index}",
            "candidate": (
                candidate.get("candidate")
                if not isinstance(candidate.get("submit"), dict)
                else ""
            ),
            "verification": candidate.get("verification"),
            "why": candidate.get("why"),
            "effect": candidate.get("effect"),
        })
        for index, candidate in enumerate(candidates, start=1)
    ]
    count = len(candidates)
    return PanelFact(
        "verified_pr_bridge_routes",
        "Verifier-checked Pr bridge routes",
        details,
        summary=(
            f"Manager read-only preflight found {count} current-state route"
            f"{'s' if count != 1 else ''}; "
            + (
                "exact ready submissions appear below."
                if ready_count
                else "verified candidates are shown as evidence; no ready submit payload was returned."
            )
        ),
        details=details,
        audit_payload=candidates,
        kind="state_fact",
        source_refs=("surface_action_preflight.results",),
    )


def _pr_endpoint_matches_fact(view: dict[str, Any]) -> PanelFact | None:
    app = view.get("application_context") if isinstance(view.get("application_context"), dict) else {}
    raw_matches = [
        item for item in app.get("pr_endpoint_matches") or []
        if isinstance(item, dict) and item.get("lemma")
    ]
    details: list[dict[str, Any]] = []
    for item in raw_matches[:4]:
        matches = [
            match for match in item.get("exact_endpoint_matches") or []
            if isinstance(match, dict)
        ]
        if not matches:
            continue
        match = matches[0]
        details.append(_drop_empty({
            "lemma": item.get("lemma"),
            "matched_side": match.get("lemma_side"),
            "rewrite_direction": match.get("rewrite_direction"),
            "other_endpoint": match.get("other_endpoint"),
            "required_premises": item.get("required_premises"),
            "authority": item.get("authority"),
        }))
    if not details:
        return None
    count = len(details)
    return PanelFact(
        "pr_endpoint_matches",
        "Loaded Pr endpoint matches",
        details,
        summary=(
            f"{count} loaded lemma{'s' if count != 1 else ''} "
            f"{'have' if count != 1 else 'has'} a left-hand Pr program endpoint "
            "matching the current goal; the declared forward direction and outer "
            "premises are shown below."
        ),
        details=details,
        audit_payload=raw_matches,
        kind="state_fact",
        source_refs=("application_context.pr_endpoint_matches",),
    )


def _pr_bound_routes_fact(view: dict[str, Any]) -> PanelFact | None:
    app = view.get("application_context") if isinstance(view.get("application_context"), dict) else {}
    raw_routes = [
        item for item in app.get("pr_bound_routes") or []
        if isinstance(item, dict) and item.get("lemma")
    ]
    if not raw_routes:
        return None
    details = [
        _drop_empty({
            "lemma": item.get("lemma"),
            "route_role": item.get("route_role"),
            "exact_goal_endpoints": item.get("exact_goal_endpoints"),
            "parameterized_goal_endpoints": item.get("parameterized_goal_endpoints"),
            "parameter_bindings": item.get("parameter_bindings"),
            "required_premises": item.get("required_premises"),
            "authority": item.get("authority"),
        })
        for item in raw_routes[:6]
    ]
    return PanelFact(
        "pr_bound_routes",
        "Loaded Pr bound routes",
        details,
        summary=(
            "Loaded declarations with exact current-goal Pr endpoints, plus any "
            "strongly overlapping outer additive decomposition. This is the full "
            "mechanically eligible route set, not a selected architecture."
        ),
        details=details,
        audit_payload=raw_routes[:6],
        kind="state_fact",
        source_refs=("application_context.pr_bound_routes",),
    )


def _deep_panel(
    view: dict[str, Any],
    actions: tuple[PanelAction, ...],
) -> PanelModel:
    seq = view.get("seq_cut_surface") if isinstance(view.get("seq_cut_surface"), dict) else {}
    facts: list[PanelFact] = []
    for key, label in (
        ("seq_scope", "Seq scope"),
        ("obligation_shape", "Obligation shape"),
        ("residual_frontier_after_cut", "Residual frontier after checked cut"),
    ):
        value = seq.get(key)
        if value not in ({}, [], None, ""):
            facts.append(PanelFact(key, label, value, source_refs=(f"seq_cut_surface.{key}",)))
    branch_focus = _displayable_branch_focus(seq.get("branch_focus"))
    if branch_focus:
        facts.append(PanelFact(
            "branch_focus",
            "Branch focus",
            branch_focus,
            source_refs=("seq_cut_surface.branch_focus",),
        ))
    whole_program = _whole_program_structure_fact(view)
    if whole_program is not None:
        facts.append(whole_program)
    skeleton = _render_surgery_skeleton(view)
    if skeleton:
        for key, label in (
            ("where", "Where"),
            ("branch_sample_alignment", "Guarded branch / random alignment"),
            ("lookahead_after_frontier", "Lookahead after current frontier"),
            ("split_points", "Seq split points"),
            ("swap_offsets", "Swap offset frames"),
        ):
            value = skeleton.get(key)
            if value not in ({}, [], None, ""):
                if key == "branch_sample_alignment":
                    panel_label = label
                    if isinstance(value, dict):
                        panel_label = str(value.get("display_label") or label)
                    facts.append(PanelFact(
                        key,
                        panel_label,
                        value,
                        summary=_branch_sample_alignment_summary(value),
                        details=_branch_sample_alignment_details(value),
                        audit_payload=value,
                        source_refs=("program_frontier.current_frontier_scope",),
                    ))
                else:
                    source_refs = (
                        ("program_frontier.checked_structural_sources.seq_sources",)
                        if key == "split_points"
                        else ("program_frontier.checked_structural_sources.swap_sources",)
                        if key == "swap_offsets"
                        else ("program_frontier.current_frontier_scope",)
                    )
                    facts.append(PanelFact(
                        key,
                        label,
                        value,
                        source_refs=source_refs,
                    ))
    cs = view.get("call_site_surface") if isinstance(view.get("call_site_surface"), dict) else {}
    near_frontier_fact = _near_frontier_bridge_fact(cs)
    if near_frontier_fact is not None:
        facts.append(near_frontier_fact)
    losslessness_fact = _one_sided_losslessness_fact(view)
    if losslessness_fact is not None:
        facts.append(losslessness_fact)
    uptobad = _up_to_bad_call_compatibility_fact(view)
    if uptobad is not None:
        facts.append(uptobad)
    named_routes = _loaded_named_routes_fact(view)
    if named_routes is not None:
        facts.append(named_routes)
    if not facts:
        frontier = view.get("program_frontier")
        if frontier not in ({}, [], None, "") and (
            _current_goal_has_program(view) or _program_frontier_has_live_facts(view)
        ):
            facts.append(PanelFact(
                "program_frontier",
                "Program frontier",
                _compact_value(frontier),
                kind="state_fact",
                source_refs=("program_frontier",),
            ))
    return PanelModel(
        panel_id="deep_surgery",
        phase="deep_surgery",
        title=PANEL_TITLES["deep_surgery"],
        facts=tuple(facts),
        actions=actions,
        display_policy=DisplayPolicy(
            lead_before_goal=_goal_is_large_for_surface(view),
            verbosity="normal",
        ),
        source_refs=("seq_cut_surface", "program_frontier"),
    )


def _displayable_branch_focus(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    # remaining_goals/latest_event_head are already visible as status/last-action
    # facts.  Showing only those creates a fake "panel" with no proof-local
    # mechanical help, so keep branch_focus normal-display only when the analyzer
    # provides richer branch-local facts.
    noisy_keys = {"remaining_goals", "latest_event_head", "latest_event_status"}
    return {
        str(key): val
        for key, val in value.items()
        if key not in noisy_keys and val not in ({}, [], None, "")
    }


def _whole_program_structure_fact(view: dict[str, Any]) -> PanelFact | None:
    ps = view.get("proof_status") if isinstance(view.get("proof_status"), dict) else {}
    goal_type = str(ps.get("goal_type") or _goal_surface(view).get("goal_type") or "").lower()
    if goal_type in {"hoare", "phoare", "bdhoare", "probability"}:
        return None
    goal_text = str(_goal_surface(view).get("text") or "")
    if "[programs are in sync]" in goal_text:
        return None
    pf = view.get("program_frontier") if isinstance(view.get("program_frontier"), dict) else {}
    scope = pf.get("current_frontier_scope") if isinstance(pf.get("current_frontier_scope"), dict) else {}
    if not scope:
        return None
    setup = scope.get("setup") if isinstance(scope.get("setup"), dict) else {}
    frontier = scope.get("frontier") if isinstance(scope.get("frontier"), dict) else {}
    lookahead = scope.get("lookahead_after_frontier")

    left_regions = _whole_program_regions_for_side(setup, frontier, lookahead, "left")
    right_regions = _whole_program_regions_for_side(setup, frontier, lookahead, "right")
    if not _should_show_whole_program_structure(left_regions, right_regions):
        return None
    observations = _whole_program_observations(left_regions, right_regions)
    if not observations:
        return None
    return PanelFact(
        "whole_program_structure",
        "Whole-program structure",
        _drop_empty({
            "left_regions": _whole_program_region_text(left_regions),
            "right_regions": _whole_program_region_text(right_regions),
            "observations": observations,
        }),
        kind="state_fact",
        source_refs=("program_frontier.current_frontier_scope",),
    )


def _up_to_bad_call_compatibility_fact(view: dict[str, Any]) -> PanelFact | None:
    app = view.get("application_context") if isinstance(view.get("application_context"), dict) else {}
    entry = app.get("up_to_bad_call") if isinstance(app.get("up_to_bad_call"), dict) else {}
    if not entry:
        return None
    bads = [
        str(item).strip()
        for item in entry.get("active_bad_events") or []
        if str(item).strip()
    ]
    if not bads:
        return None
    bad_clause = bads[0] if len(bads) == 1 else "(" + " \\/ ".join(bads) + ")"
    guard = f"!{bad_clause}"
    if _goal_precondition_carries_bad_guard(view, bads):
        value = _drop_empty({
            "active_bad_events": bads,
            "visible_guard": guard,
            "obligation_context": (
                "current subgoal is already under the displayed bad-event guard"
            ),
            "verification_status": "mechanical guard-context fact; not a verdict or gate",
        })
        label = "Bad-event guarded obligation"
    else:
        value = _drop_empty({
            "active_bad_events": bads,
            "relation_break_guard": guard,
            "visible_call_offer_shape": "single-clause lockstep call invariant (no bad-event clause)",
            "relevant_call_form_family": f"call (_: {bad_clause}, <inv>).",
            "obligation_shapes": [
                f"oracle equivalence under {guard}",
                f"losslessness obligations after {bad_clause}",
                f"{bad_clause}-preservation",
            ],
            "verification_status": "mechanical compatibility fact; not a verdict or gate",
        })
        label = "Up-to-bad call compatibility"
    return PanelFact(
        "up_to_bad_call_compatibility",
        label,
        value,
        kind="state_fact",
        role="diagnostic",
        source_refs=("application_context.up_to_bad_call",),
    )


def _goal_precondition_carries_bad_guard(view: dict[str, Any], bads: list[str]) -> bool:
    goal = _goal_surface(view)
    text = str(goal.get("text") or "")
    if not text or "pre" not in text or "post" not in text:
        return False
    match = re.search(r"\bpre\s*=(.*?)(?:\n\s*post\s*=|\Z)", text, flags=re.DOTALL)
    if not match:
        return False
    pre_text = match.group(1)
    if "!" not in pre_text:
        return False
    return all(bad in pre_text for bad in bads)


_LOAD_BEARING_CALL_TAIL = re.compile(r"\.(distinguish|main|enc|dec|cc|mac|game)\b")


_LOAD_BEARING_RANK = ("distinguish", "enc", "dec", "cc", "mac", "main", "game")


def _rcond_branch_callouts(view: dict[str, Any]) -> list[str]:
    return [_rcond_branch_line(item) for item in _rcond_branch_items(view)]


def _rcond_branch_items(view: dict[str, Any]) -> list[dict[str, Any]]:
    pf = view.get("program_frontier")
    pn = (pf or {}).get("procedure_navigation") if isinstance(pf, dict) else None
    guards = (pn or {}).get("branch_guards") if isinstance(pn, dict) else None
    if not isinstance(guards, list):
        return []
    current_guards, lookahead_guards = _guard_scope_paths(view)
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for guard_info in guards:
        if not isinstance(guard_info, dict):
            continue
        side = str(guard_info.get("side_index") or "").strip()
        path = str(guard_info.get("at_path") or "").strip()
        if side not in {"1", "2"} or not path.isdigit():
            continue
        key = (side, path)
        if key in seen:
            continue
        seen.add(key)
        guard = str(guard_info.get("guard") or "").strip()
        is_current = key in current_guards
        indexed_forms = [f"rcondt{{{side}}} {path}", f"rcondf{{{side}}} {path}"]
        next_if_forms = (
            [f"rcondt{{{side}}} ^if{{{side}}}", f"rcondf{{{side}}} ^if{{{side}}}"]
            if is_current else []
        )
        if is_current:
            scope = "current frontier guard"
        elif key in lookahead_guards:
            scope = "lookahead after current frontier"
        else:
            scope = "later visible top-level guard"
        out.append(_drop_empty({
            "side": side,
            "position": path,
            "guard": guard,
            "indexed_forms": indexed_forms,
            "next_if_forms": next_if_forms,
            "scope": scope,
        }))
    return out


def _guard_scope_paths(
    view: dict[str, Any],
) -> tuple[set[tuple[str, str]], set[tuple[str, str]]]:
    frontier = view.get("program_frontier") if isinstance(view.get("program_frontier"), dict) else {}
    scope = frontier.get("current_frontier_scope") if isinstance(frontier.get("current_frontier_scope"), dict) else {}
    current = scope.get("frontier") if isinstance(scope.get("frontier"), dict) else {}
    current_paths: set[tuple[str, str]] = set()
    lookahead_paths: set[tuple[str, str]] = set()
    side_index = {"left": "1", "right": "2"}
    for side, index in side_index.items():
        entry = current.get(side) if isinstance(current.get(side), dict) else {}
        if str(entry.get("head") or "").strip() in {"if", "branch"}:
            path = str(entry.get("path") or "").strip()
            if path:
                current_paths.add((index, path))
    for entry in scope.get("lookahead_after_frontier") or []:
        if not isinstance(entry, dict):
            continue
        if str(entry.get("head") or "").strip() not in {"if", "branch"}:
            continue
        index = side_index.get(str(entry.get("side") or "").strip())
        path = str(entry.get("path") or "").strip()
        if index and path:
            lookahead_paths.add((index, path))
    return current_paths, lookahead_paths


def _rcond_branch_line(item: dict[str, Any]) -> str:
    side = str(item.get("side") or "").strip()
    path = str(item.get("position") or "").strip()
    guard = str(item.get("guard") or "").strip()
    guard_note = f" -- guard {_code_span(guard)}" if guard else ""
    return (
        f"guarded `if` at left/right side {side}, program position {path}: "
        f"{_code_span(f'rcondt{{{side}}} {path}')} or "
        f"{_code_span(f'rcondf{{{side}}} {path}')}{guard_note}"
    )


def _load_bearing_frontier_call(view: dict[str, Any]) -> str:
    cs = view.get("call_site_surface")
    if not isinstance(cs, dict):
        return ""
    candidates: list[str] = []
    for blocker in cs.get("frontier_blockers") or []:
        if not isinstance(blocker, dict):
            continue
        procs = blocker.get("frontier_live_procedures")
        if not isinstance(procs, list):
            continue
        subject_tails = {
            _proc_module_method(str(subject))
            for subject in blocker.get("subject_procedures") or []
            if str(subject or "").strip()
        }
        for proc in procs:
            name = str(proc or "").strip()
            if not name or not _LOAD_BEARING_CALL_TAIL.search(name):
                continue
            if _proc_module_method(name) in subject_tails:
                continue
            candidates.append(name)
    if not candidates:
        return ""

    def _rank(name: str) -> tuple[int, int]:
        match = _LOAD_BEARING_CALL_TAIL.search(name)
        method = match.group(1) if match else ""
        order = _LOAD_BEARING_RANK.index(method) if method in _LOAD_BEARING_RANK else len(_LOAD_BEARING_RANK)
        return (order, candidates.index(name))

    return sorted(dict.fromkeys(candidates), key=_rank)[0]


def _surgery_where(view: dict[str, Any], *, include_rcond: bool = True) -> list[str]:
    pf = view.get("program_frontier")
    scope = (pf or {}).get("current_frontier_scope") if isinstance(pf, dict) else None
    fa = (pf or {}).get("frontier_alignment") if isinstance(pf, dict) else None
    rcond_callouts = _rcond_branch_callouts(view) if include_rcond else []
    if isinstance(scope, dict) and scope:
        return (
            _surgery_where_from_current_scope(
                scope,
                synchronized=_programs_are_in_sync(view),
            )
            + rcond_callouts
        )
    if not isinstance(fa, dict):
        return rcond_callouts
    fia = fa.get("first_instruction_alignment") if isinstance(fa.get("first_instruction_alignment"), dict) else {}
    out: list[str] = []
    shown_frontier: set[str] = set()
    suppress_one_sided_frontier_rows = False

    def _norm(text: str) -> str:
        return " ".join(text.split())

    def _is_placeholder(text: str) -> bool:
        return text.startswith("no ") or "no matching" in text

    rows = [row for row in fa.get("rows") or [] if isinstance(row, dict)]

    def _row_side_status(row: dict[str, Any]) -> tuple[str, bool, bool, str, str]:
        role = str(row.get("role") or "")
        left = str(row.get("left") or "").strip()
        right = str(row.get("right") or "").strip()
        left_l = left.lower()
        right_l = right.lower()
        return role, bool(left) and not _is_placeholder(left_l), bool(right) and not _is_placeholder(right_l), left, right

    for row in rows:
        if not isinstance(row, dict):
            continue
        role, left_ok_current, right_ok_current, left, right = _row_side_status(row)
        left_l = left.lower()
        right_l = right.lower()

        loc = row.get("location") if isinstance(row.get("location"), dict) else {}
        if "setup" in role:
            def _path_range(paths: Any) -> str:
                if not isinstance(paths, list) or not paths:
                    return ""
                return f"{paths[0]}-{paths[-1]}" if len(paths) > 1 else str(paths[0])

            left_range = _path_range(loc.get("left_paths"))
            right_range = _path_range(loc.get("right_paths"))
            if left_range and right_range and left_range != right_range:
                pos = f" (left positions {left_range} / right positions {right_range})"
            elif left_range or right_range:
                pos = f" (positions {left_range or right_range})"
            else:
                pos = ""
            calls = [
                stmt for stmt in (_setup_statements(left) + _setup_statements(right))
                if statement_is_procedure_call(stmt)
            ]
            if calls:
                load_bearing = _load_bearing_frontier_call(view)
                if load_bearing and not _LOAD_BEARING_CALL_TAIL.search("; ".join(calls)):
                    out.append(
                        f"procedure-call prefix before the frontier{pos} -- "
                        f"load-bearing frontier call also visible `{load_bearing}`; "
                        f"setup calls: {'; '.join(calls[:2])}"
                    )
                    suppress_one_sided_frontier_rows = True
                else:
                    out.append(
                        f"procedure-call prefix before the frontier{pos} -- "
                        f"setup calls: {'; '.join(calls[:2])}"
                    )
            else:
                out.append(f"assignment/setup prefix before the frontier{pos}: {left[:80]}")
        elif "sample" in role:
            left_ok = bool(left) and not _is_placeholder(left_l)
            right_ok = bool(right) and not _is_placeholder(right_l)
            if left_ok and right_ok:
                where, content = "both sides", left[:60]
            elif left_ok:
                where, content = "left side only", left[:60]
            elif right_ok:
                where, content = "right side only", right[:60]
            else:
                continue
            out.append(f"sample: {where} at `{content}` -- random-sample frontier, not a call frontier")
        elif "frontier" in role or "loop" in role:
            left_ok = left_ok_current
            right_ok = right_ok_current
            if suppress_one_sided_frontier_rows and (left_ok != right_ok):
                continue
            if left_ok and right_ok:
                shown_frontier.add(_norm(left))
                shown_frontier.add(_norm(right))
                if _norm(left) == _norm(right):
                    out.append(f"frontier: both sides at `{left[:60]}`")
                else:
                    out.append(f"frontier: both sides -- left `{left[:48]}` / right `{right[:48]}`")
            elif left_ok and _norm(left) not in shown_frontier:
                shown_frontier.add(_norm(left))
                out.append(f"frontier: left side only at `{left[:60]}`")
            elif right_ok and _norm(right) not in shown_frontier:
                shown_frontier.add(_norm(right))
                out.append(f"frontier: right side only at `{right[:60]}`")
    out.extend(rcond_callouts)
    if not out and fia:
        out.append(f"frontier head `{fia.get('left_head')}` ({fia.get('branch_alignment')})")
    return out


def _surgery_where_from_current_scope(
    scope: dict[str, Any],
    *,
    synchronized: bool = False,
) -> list[str]:
    out: list[str] = []
    setup = scope.get("setup") if isinstance(scope.get("setup"), dict) else {}
    left_setup = setup.get("left") if isinstance(setup.get("left"), dict) else {}
    right_setup = setup.get("right") if isinstance(setup.get("right"), dict) else {}
    frontier = scope.get("frontier") if isinstance(scope.get("frontier"), dict) else {}
    left = frontier.get("left") if isinstance(frontier.get("left"), dict) else {}
    right = frontier.get("right") if isinstance(frontier.get("right"), dict) else {}
    frontier_head = _scope_frontier_head(left, right)
    if left_setup or right_setup:
        pos = _scope_position_text(
            left_setup.get("paths") if isinstance(left_setup, dict) else None,
            right_setup.get("paths") if isinstance(right_setup, dict) else None,
            synchronized=synchronized,
        )
        summary = _scope_setup_summary(left_setup, right_setup)
        subject = _scope_setup_subject(
            left_setup,
            right_setup,
            frontier_head=frontier_head,
            synchronized=synchronized,
        )
        connector = _scope_setup_connector(
            frontier_head,
            left_setup=left_setup,
            right_setup=right_setup,
        )
        out.append(f"{subject}{pos} -- {connector}: {summary}")
    if left or right:
        out.append(_scope_frontier_line(left, right, synchronized=synchronized))
    tail = (
        scope.get("tactic_active_tail")
        if isinstance(scope.get("tactic_active_tail"), dict)
        else {}
    )
    tail_left = tail.get("left") if isinstance(tail.get("left"), dict) else {}
    tail_right = tail.get("right") if isinstance(tail.get("right"), dict) else {}
    if (tail_left or tail_right) and not _same_scope_entries(
        left,
        right,
        tail_left,
        tail_right,
    ):
        out.append(
            _scope_frontier_line(
                tail_left,
                tail_right,
                synchronized=synchronized,
            ).replace("current frontier:", "suffix tactic boundary:", 1)
        )
    return [line for line in out if line]


def _same_scope_entries(
    left: dict[str, Any],
    right: dict[str, Any],
    other_left: dict[str, Any],
    other_right: dict[str, Any],
) -> bool:
    def key(entry: dict[str, Any]) -> tuple[str, str, str]:
        return (
            str(entry.get("path") or ""),
            str(entry.get("head") or ""),
            " ".join(str(entry.get("statement") or "").split()),
        )

    return key(left) == key(other_left) and key(right) == key(other_right)


def _scope_setup_subject(
    left: dict[str, Any],
    right: dict[str, Any],
    *,
    frontier_head: str = "",
    synchronized: bool = False,
) -> str:
    target = "visible guard" if frontier_head == "if" else "current frontier"
    if synchronized:
        return f"synchronized setup before {target}"
    if left and right:
        left_summary = str(left.get("summary") or "").strip()
        right_summary = str(right.get("summary") or "").strip()
        left_paths = left.get("paths")
        right_paths = right.get("paths")
        if left_summary != right_summary or left_paths != right_paths:
            return f"asymmetric setup before {target}"
        return f"setup before {target}"
    if left:
        return f"left setup before {target}"
    return f"right setup before {target}"


def _scope_setup_connector(
    frontier_head: str,
    *,
    left_setup: dict[str, Any],
    right_setup: dict[str, Any],
) -> str:
    if frontier_head == "if":
        return "prefix statements"
    if _scope_setup_has_proc_call(left_setup, right_setup):
        return "procedure-call prefix"
    return "assignment/setup prefix"


def _scope_setup_has_proc_call(*sides: dict[str, Any]) -> bool:
    for side in sides:
        summary = str(side.get("summary") or "").strip()
        if not summary:
            continue
        if _setup_annotation_index(summary) != -1:
            return True
        if any(statement_is_procedure_call(stmt) for stmt in _setup_statements(summary)):
            return True
    return False


def _scope_position_text(
    left_paths: Any,
    right_paths: Any,
    *,
    synchronized: bool = False,
) -> str:
    def _range(paths: Any) -> str:
        if not isinstance(paths, list) or not paths:
            return ""
        return f"{paths[0]}-{paths[-1]}" if len(paths) > 1 else str(paths[0])

    left_range = _range(left_paths)
    right_range = _range(right_paths)
    if synchronized and (left_range or right_range):
        return f" (positions {left_range or right_range})"
    if left_range and right_range and left_range != right_range:
        return f" (left positions {left_range} / right positions {right_range})"
    if left_range and not right_range:
        return f" (left positions {left_range})"
    if right_range and not left_range:
        return f" (right positions {right_range})"
    if left_range or right_range:
        return f" (positions {left_range or right_range})"
    return ""


def _scope_setup_summary(left: dict[str, Any], right: dict[str, Any]) -> str:
    left_summary = _strip_setup_call_tag(str(left.get("summary") or "").strip())
    right_summary = _strip_setup_call_tag(str(right.get("summary") or "").strip())
    if left_summary and right_summary and left_summary != right_summary:
        return (
            f"left {_code_span(_inline_preview(left_summary, limit=90))}; "
            f"right {_code_span(_inline_preview(right_summary, limit=90))}"
        )
    return _code_span(_inline_preview(left_summary or right_summary, limit=120))


def _scope_frontier_line(
    left: dict[str, Any],
    right: dict[str, Any],
    *,
    synchronized: bool = False,
) -> str:
    def _stmt(entry: dict[str, Any]) -> str:
        statement = str(entry.get("statement") or "").strip()
        procedure = str(entry.get("procedure") or "").strip()
        if procedure and procedure not in statement:
            return _code_span(f"{_inline_preview(statement, limit=64)} [{procedure}]")
        return _code_span(_inline_preview(statement, limit=72))

    if synchronized:
        entry = left or right
        if entry:
            return f"current frontier: synchronized at {_stmt(entry)}"
    if left and right:
        label = _scope_frontier_pair_label(left, right)
        return f"current frontier: {label} -- left {_stmt(left)} / right {_stmt(right)}"
    if left:
        return f"current frontier: left side only at {_stmt(left)}"
    return f"current frontier: right side only at {_stmt(right)}"


def _scope_frontier_pair_label(left: dict[str, Any], right: dict[str, Any]) -> str:
    left_head = _scope_entry_head(left)
    right_head = _scope_entry_head(right)
    if left_head == "call" and right_head == "call":
        left_proc = str(left.get("procedure") or "").strip()
        right_proc = str(right.get("procedure") or "").strip()
        left_tail = _proc_module_method(left_proc)
        right_tail = _proc_module_method(right_proc)
        if left_tail and right_tail and left_tail == right_tail:
            return "matched call-shape on both sides"
        return "live calls on both sides, not a matched call offer"
    if left_head and right_head and left_head != right_head:
        return f"left {_frontier_head_label(left_head)} vs right {_frontier_head_label(right_head)}"
    if left_head and right_head:
        return f"both sides at {_frontier_head_label(left_head)}"
    return "both sides"


def _scope_frontier_head(left: dict[str, Any], right: dict[str, Any]) -> str:
    left_head = _scope_entry_head(left) if left else ""
    right_head = _scope_entry_head(right) if right else ""
    if left_head == right_head:
        return left_head
    if "if" in {left_head, right_head}:
        return "if"
    if left_head:
        return left_head
    return right_head


def _surgery_lookahead_after_frontier(view: dict[str, Any]) -> list[str]:
    pf = view.get("program_frontier") if isinstance(view.get("program_frontier"), dict) else {}
    scope = pf.get("current_frontier_scope") if isinstance(pf.get("current_frontier_scope"), dict) else {}
    items = scope.get("lookahead_after_frontier")
    if not isinstance(items, list):
        return []
    tail = scope.get("tactic_active_tail") if isinstance(scope.get("tactic_active_tail"), dict) else {}
    tail_paths = {
        (side, str((tail.get(side) or {}).get("path") or "").strip())
        for side in ("left", "right")
        if isinstance(tail.get(side), dict)
        and str((tail.get(side) or {}).get("path") or "").strip()
    }
    valid_items = [
        item
        for item in items
        if isinstance(item, dict)
        and (
            str(item.get("side") or "").strip(),
            str(item.get("path") or "").strip(),
        ) not in tail_paths
    ]
    paired = _paired_lookahead_lines(valid_items)
    if paired:
        return paired
    return [_lookahead_item_line(item) for item in valid_items if _lookahead_item_line(item)]


def _paired_lookahead_lines(items: list[dict[str, Any]]) -> list[str]:
    if not items:
        return []
    by_path: dict[str, dict[str, dict[str, Any]]] = {}
    for item in items:
        path = str(item.get("path") or "").strip()
        side = str(item.get("side") or "").strip()
        if not path or side not in {"left", "right"}:
            return []
        side_map = by_path.setdefault(path, {})
        if side in side_map:
            return []
        side_map[side] = item
    if not by_path:
        return []
    lines: list[str] = ["paired future regions:"]
    for path, side_map in by_path.items():
        left = side_map.get("left")
        right = side_map.get("right")
        if not left or not right or not _lookahead_entries_pairable(left, right):
            return []
        line = _paired_lookahead_line(path, left, right)
        if not line:
            return []
        lines.append(line)
    return lines if len(lines) > 1 else []


def _lookahead_entries_pairable(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_label = _lookahead_entry_label(left)
    right_label = _lookahead_entry_label(right)
    return bool(left_label and left_label == right_label)


def _lookahead_entry_label(entry: dict[str, Any]) -> str:
    region = _whole_program_region_from_entry(entry)
    return str(region.get("label") or region.get("kind") or "").strip()


def _paired_lookahead_line(path: str, left: dict[str, Any], right: dict[str, Any]) -> str:
    label = _lookahead_entry_label(left)
    left_statement = str(left.get("statement") or "").strip()
    right_statement = str(right.get("statement") or "").strip()
    if not label:
        return ""
    if _normalized_inline_text(left_statement) == _normalized_inline_text(right_statement):
        if label.startswith("call "):
            return f"path {path}: {label}"
        return f"path {path}: {label} {_code_span(_inline_preview(left_statement, limit=72))}"
    return (
        f"path {path}: {label} -- left "
        f"{_code_span(_inline_preview(left_statement, limit=56))} / right "
        f"{_code_span(_inline_preview(right_statement, limit=56))}"
    )


def _lookahead_item_line(item: dict[str, Any]) -> str:
    side = str(item.get("side") or "").strip()
    path = str(item.get("path") or "").strip()
    statement = str(item.get("statement") or "").strip()
    procedure = str(item.get("procedure") or "").strip()
    if not side and not statement:
        return ""
    proc = f" [{procedure}]" if procedure and procedure not in statement else ""
    where = f"{side} path {path}" if path else side
    return f"{where}: {_code_span(_inline_preview(statement, limit=88) + proc)} -- after current frontier"


def _normalized_inline_text(text: str) -> str:
    return " ".join(str(text or "").split())


def _current_sample_frontiers(view: dict[str, Any]) -> list[dict[str, str]]:
    pf = view.get("program_frontier") if isinstance(view.get("program_frontier"), dict) else {}
    scope = pf.get("current_frontier_scope") if isinstance(pf.get("current_frontier_scope"), dict) else {}
    frontier = scope.get("frontier") if isinstance(scope.get("frontier"), dict) else {}
    out: list[dict[str, str]] = []
    for side in ("left", "right"):
        entry = frontier.get(side) if isinstance(frontier.get(side), dict) else {}
        statement = str(entry.get("statement") or "").strip()
        head = str(entry.get("head") or "").strip()
        if head != "sample" and "<$" not in statement:
            continue
        out.append(_drop_empty({
            "side": side,
            "path": str(entry.get("path") or "").strip(),
            "statement": _inline_preview(statement, limit=88),
        }))
    return out


def _branch_sample_alignment(view: dict[str, Any]) -> dict[str, Any]:
    guards = _rcond_branch_items(view)
    swaps = _swap_frame_items(view)
    samples = _current_sample_frontiers(view)
    # A bare sample frontier is just a frontier fact. It becomes random-alignment
    # evidence only when paired with swap/coupling scaffolding, or when current
    # visible guards need to be normalized before that alignment work.
    if not guards and not (samples and swaps):
        return {}
    has_current_guard = any(
        item.get("scope") == "current frontier guard" for item in guards
    )
    if guards and samples and swaps and has_current_guard:
        display_label = "Guarded branch / random alignment"
        stage = "guarded branch normalization before random coupling"
    elif guards and samples and swaps:
        display_label = "Random alignment with guarded lookahead"
        stage = "current random alignment with later guarded branches"
    elif guards and samples and has_current_guard:
        display_label = "Guarded branch with sample frontier"
        stage = "guarded branch normalization with sample frontier"
    elif guards and samples:
        display_label = "Sample frontier with guarded lookahead"
        stage = "current sample with later guarded branches"
    elif guards:
        display_label = "Guarded branch normalization"
        stage = "guarded branch normalization"
    else:
        display_label = "Random alignment"
        stage = "random alignment preparation"
    return _drop_empty({
        "display_label": display_label,
        "stage": stage,
        "current_sample_frontiers": samples,
        "visible_guarded_ifs": guards[:8],
        "swap_frames": [
            _drop_empty({
                "form": item.get("form"),
                "side": item.get("side"),
                "source_position": item.get("source_position"),
            })
            for item in swaps[:8]
        ],
    })


def _branch_sample_alignment_summary(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    samples = value.get("current_sample_frontiers") if isinstance(value.get("current_sample_frontiers"), list) else []
    guards = value.get("visible_guarded_ifs") if isinstance(value.get("visible_guarded_ifs"), list) else []
    swaps = value.get("swap_frames") if isinstance(value.get("swap_frames"), list) else []
    bits: list[str] = []
    if samples:
        sample_bits = []
        for item in samples[:2]:
            if not isinstance(item, dict):
                continue
            side = str(item.get("side") or "").strip()
            statement = str(item.get("statement") or "").strip()
            sample_bits.append(f"{side} {_code_span(statement)}")
        if sample_bits:
            bits.append("current sample " + "; ".join(sample_bits))
    if guards:
        bits.append(f"{len(guards)} visible guarded if(s)")
    if swaps:
        bits.append(f"{len(swaps)} swap frame(s)")
    return "; ".join(bits) if bits else str(value.get("stage") or "")


def _branch_sample_alignment_details(value: Any) -> list[str]:
    if not isinstance(value, dict):
        return []
    out: list[str] = []
    guards = value.get("visible_guarded_ifs") if isinstance(value.get("visible_guarded_ifs"), list) else []
    if guards:
        parts = []
        for item in guards[:6]:
            if not isinstance(item, dict):
                continue
            side = str(item.get("side") or "").strip()
            pos = str(item.get("position") or "").strip()
            guard = str(item.get("guard") or "").strip()
            next_forms = item.get("next_if_forms") if isinstance(item.get("next_if_forms"), list) else []
            forms = next_forms or item.get("indexed_forms") or []
            form_text = " / ".join(_code_span(str(form)) for form in forms[:2])
            guard_text = f" guard {_code_span(_inline_preview(guard, limit=96))}" if guard else ""
            scope = str(item.get("scope") or "visible guard")
            parts.append(f"{scope}, side {side} position {pos}: {form_text}{guard_text}")
        if parts:
            out.append("Visible guarded ifs: " + "; ".join(parts))
    swaps = value.get("swap_frames") if isinstance(value.get("swap_frames"), list) else []
    if swaps:
        forms = [
            _code_span(str(item.get("form")))
            for item in swaps[:6]
            if isinstance(item, dict) and item.get("form")
        ]
        if forms:
            out.append("Swap frames: " + "; ".join(forms))
    return out


def _extract_seq_positions(view: dict[str, Any]) -> list[str]:
    return [
        _code_span(item["form"] + " : (=?).")
        + " -- checked split positions; the cut formula is not selected."
        for item in checked_seq_sources(view)
    ]


def _extract_swap_offsets(view: dict[str, Any]) -> list[str]:
    return [item["display"] for item in _swap_frame_items(view)]


def _swap_frame_items(view: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in checked_swap_sources(view):
        form = item["form"]
        out.append(_drop_empty({
            **item,
            "display": (
                _code_span(form)
                + " -- checked static-realignment source; the offset is not selected."
            ),
        }))
    return out


def _render_surgery_skeleton(view: dict[str, Any]) -> dict[str, Any] | None:
    branch_sample = _branch_sample_alignment(view)
    where = _surgery_where(view, include_rcond=not bool(branch_sample))
    lookahead = _surgery_lookahead_after_frontier(view)
    positions = _extract_seq_positions(view)
    swaps = _extract_swap_offsets(view)
    if not where and not branch_sample and not lookahead and not positions and not swaps:
        return None
    skeleton: dict[str, Any] = {
        "where": where or ["deep procedure body -- read the goal's two sides."],
    }
    if branch_sample:
        skeleton["branch_sample_alignment"] = branch_sample
    if lookahead:
        skeleton["lookahead_after_frontier"] = lookahead
    if positions:
        skeleton["split_points"] = positions
    if swaps and not branch_sample:
        skeleton["swap_offsets"] = swaps
    return skeleton


def _probability_goal_shape(text: str) -> str:
    compact = " ".join(str(text or "").split())
    if not compact:
        return "probability goal"
    if "Pr[" not in compact:
        return compact[:240]
    if " = " in compact:
        relation = "equality"
    elif " <= " in compact or "<=" in compact:
        relation = "upper bound"
    elif " < " in compact:
        relation = "strict upper bound"
    else:
        relation = "probability expression"
    return f"Pr[...] {relation}"


def _probability_structure_analysis(text: str) -> dict[str, Any]:
    gtext = str(text or "")
    analysis: dict[str, Any] = {
        "base": _probability_goal_shape(gtext),
        "has_pr": "Pr[" in gtext,
    }
    if "Pr[" not in gtext:
        return analysis
    concl_region = _goal_conclusion_region(gtext)
    analysis["conclusion"] = " ".join(concl_region.split())
    relation = _top_level_relation(concl_region)
    if not relation:
        return analysis
    lhs, op, rhs = relation
    lhs_terms = _extract_pr_terms(lhs)
    rhs_terms = _extract_pr_terms(rhs)
    rhs_parts = _split_top_level(rhs, "+")
    all_terms = lhs_terms + rhs_terms
    rhs_programs = [_normalise_program(term.get("program_memory", "")) for term in rhs_terms]
    all_programs = [_normalise_program(term.get("program_memory", "")) for term in all_terms]
    analysis.update({
        "relation": op,
        "lhs_pr_terms": lhs_terms,
        "rhs_pr_terms": rhs_terms,
        "rhs_parts": rhs_parts,
        "rhs_sum_of_pr_terms": op in ("<=", "<") and len(rhs_parts) >= 2 and len(rhs_terms) == len(rhs_parts),
        "rhs_same_program": len(rhs_programs) >= 2 and len(set(rhs_programs)) == 1,
        "all_same_program": len(all_programs) >= 2 and len(set(all_programs)) == 1,
        "pr_term_count": len(all_terms),
        "rhs_program_count": len(set(rhs_programs)) if rhs_programs else 0,
        "all_program_count": len(set(all_programs)) if all_programs else 0,
        "has_abs_pr_difference": bool(re.search(r"\|[^|]*\bPr\s*\[[^|]*-[^|]*\bPr\s*\[[^|]*\|", concl_region)),
        "has_top_level_sum": len(_split_top_level(lhs, "+")) >= 2 or len(rhs_parts) >= 2,
    })
    return analysis


def _probability_structure_summary(shape: dict[str, Any]) -> str:
    pieces = [str(shape.get("base") or "probability goal")]
    if shape.get("rhs_sum_of_pr_terms"):
        rhs_terms = list(shape.get("rhs_pr_terms") or [])
        pieces.append(f"RHS sum of {len(rhs_terms)} Pr terms")
        if shape.get("rhs_same_program"):
            pieces.append("RHS Pr terms share program/memory")
            events = [str(term.get("event") or "") for term in rhs_terms]
            if len(events) == 2 and all(events):
                pieces.append(f"event-union skeleton visible: {_event_union_skeleton(events)}")
        elif rhs_terms:
            pieces.append(
                f"RHS Pr terms over {int(shape.get('rhs_program_count') or 0)} program/memory contexts"
            )
    elif int(shape.get("pr_term_count") or 0) >= 2:
        if shape.get("all_same_program"):
            pieces.append("visible Pr terms share program/memory")
        else:
            pieces.append(
                f"visible Pr terms over {int(shape.get('all_program_count') or 0)} program/memory contexts"
            )
    return "; ".join(piece for piece in pieces if piece)


def _probability_tactic_affordances(shape: dict[str, Any]) -> list[str]:
    if not shape.get("has_pr"):
        return []
    if shape.get("rhs_sum_of_pr_terms"):
        out = [
            "top-level: `apply` / Pr-order-transitivity family can introduce a single-Pr intermediate bound",
            "supporting/order subgoal: `rewrite` / Pr/order/union lemmas can relate the RHS event union to the displayed Pr sum",
        ]
        if shape.get("rhs_same_program"):
            out.append(
                "downstream only: `byequiv` / `byphoare` may apply after a single-Pr intermediate/subgoal exists; not directly to the original RHS-sum goal"
            )
        return out
    if shape.get("has_abs_pr_difference") or shape.get("has_top_level_sum"):
        return [
            "`apply` / order-arithmetic family for splitting the outer real inequality",
            "`rewrite` family for individual Pr equality/inequality lemmas",
        ]
    if int(shape.get("pr_term_count") or 0) <= 1:
        return [
            "`byphoare` family for a single Pr bound",
            "`rewrite` family for a matching Pr lemma",
            "`byequiv` family if introducing a comparison program",
        ]
    if shape.get("all_same_program"):
        return [
            "`rewrite` family for Pr/measure/event lemmas on the shared program",
            "`byphoare` family for a selected Pr term",
        ]
    return [
        "`byequiv` family for relating two Pr programs",
        "`rewrite` family for a matching Pr equality/inequality lemma",
    ]


def _goal_conclusion_region(text: str) -> str:
    gclean = re.sub(r"\[\s*\d+\s*\|\s*\w+\s*\]", "", str(text or ""))
    region = re.split(r"-{5,}", gclean)[-1] if "-----" in gclean else gclean
    return region.rsplit("=>", 1)[-1] if "=>" in region else region


def _normalise_program(text: str) -> str:
    return re.sub(r"\s+", "", str(text or ""))


def _event_union_skeleton(events: list[str]) -> str:
    return " \\/ ".join(_parenthesize_event(event) for event in events)


def _parenthesize_event(event: str) -> str:
    e = " ".join(str(event or "").split())
    if "\\/" in e or "/\\" in e:
        return f"({e})"
    return e


def _unfoldable_goal_head_facts(view: dict[str, Any]) -> list[PanelFact]:
    fd = view.get("facts_and_diagnostics") if isinstance(view.get("facts_and_diagnostics"), dict) else {}
    facts = fd.get("probability_budget") if isinstance(fd.get("probability_budget"), dict) else {}
    if not facts and isinstance(fd.get("facts"), dict):
        facts = fd["facts"]
    unfold = [
        _drop_empty({
            "name": item.get("name"),
            "unfold_tactic": item.get("unfold_tactic"),
        })
        for item in (facts.get("unfoldable_goal_heads") or [])
        if isinstance(item, dict) and item.get("unfold_tactic")
    ]
    if not unfold:
        return []
    return [PanelFact(
        "unfoldable_goal_heads",
        "Unfoldable goal heads",
        unfold,
        kind="state_fact",
        source_refs=("facts_and_diagnostics.probability_budget.unfoldable_goal_heads",),
    )]


def _compact_value(value: Any, *, limit: int = 2000) -> Any:
    text = str(value)
    if len(text) <= limit:
        return value
    return text[: limit - 1] + "..."


def _current_scope_setup_has_proc_call(view: dict[str, Any]) -> bool:
    pf = view.get("program_frontier") if isinstance(view.get("program_frontier"), dict) else {}
    scope = pf.get("current_frontier_scope") if isinstance(pf.get("current_frontier_scope"), dict) else {}
    setup = scope.get("setup") if isinstance(scope.get("setup"), dict) else {}
    left_setup = setup.get("left") if isinstance(setup.get("left"), dict) else {}
    right_setup = setup.get("right") if isinstance(setup.get("right"), dict) else {}
    return _scope_setup_has_proc_call(left_setup, right_setup)


def _iter_successor_panel_facts(pt: dict[str, Any]) -> list[PanelFact]:
    surface = (
        pt.get("iter_successor_surface")
        if isinstance(pt.get("iter_successor_surface"), dict) else {}
    )
    calls = surface.get("successor_calls") if isinstance(surface, dict) else []
    lines: list[str] = []
    for item in calls or []:
        if not isinstance(item, dict):
            continue
        count = _inline_text(item.get("count_shape"))
        offset = _inline_text(item.get("successor_offset"))
        family = _inline_text(item.get("lemma_family"))
        if not count:
            continue
        line = f"count has top-level {offset or '+ 1'}: {count}"
        if family:
            line += f" ({family})"
        lines.append(line)
    if not lines:
        return []
    return [PanelFact(
        "iter_successor_shape",
        "Iter successor shape",
        lines,
        kind="state_fact",
        source_refs=("pure_tail_surface.iter_successor_surface.successor_calls",),
    )]


def _integer_arithmetic_panel_facts(pt: dict[str, Any]) -> list[PanelFact]:
    arithmetic = (
        pt.get("integer_arithmetic_surface")
        if isinstance(pt.get("integer_arithmetic_surface"), dict) else {}
    )
    if not arithmetic:
        return []
    facts: list[PanelFact] = []

    split_lines: list[str] = []
    for item in arithmetic.get("split_candidates") or []:
        if not isinstance(item, dict):
            continue
        condition = _inline_text(item.get("condition"))
        if not condition:
            continue
        source = _inline_text(item.get("source_shape"))
        line = condition
        if source:
            line += f" from {source}"
        split_lines.append(line)
    if split_lines:
        facts.append(PanelFact(
            "integer_arithmetic_split_candidates",
            "Visible split candidates",
            split_lines,
            kind="state_fact",
            source_refs=("pure_tail_surface.integer_arithmetic_surface.split_candidates",),
        ))

    guards = [
        _inline_text(item)
        for item in arithmetic.get("b2i_guards") or []
        if _inline_text(item)
    ]
    if guards:
        facts.append(PanelFact(
            "integer_arithmetic_b2i_guards",
            "B2i modulo guards",
            f"{len(guards)} guard(s): " + "; ".join(guards[:4]),
            kind="state_fact",
            source_refs=("pure_tail_surface.integer_arithmetic_surface.b2i_guards",),
        ))

    family_lines: list[str] = []
    for item in arithmetic.get("lemma_families") or []:
        if not isinstance(item, dict):
            continue
        shape = _inline_text(item.get("shape"))
        lemmas = [
            _inline_text(lemma)
            for lemma in item.get("lemma_names") or []
            if _inline_text(lemma)
        ]
        if not shape and not lemmas:
            continue
        line = shape or "lemma family"
        if lemmas:
            line += ": " + ", ".join(lemmas)
        family_lines.append(line)
    if family_lines:
        facts.append(PanelFact(
            "integer_arithmetic_lemma_families",
            "Relevant lemma families",
            family_lines,
            kind="state_fact",
            source_refs=("pure_tail_surface.integer_arithmetic_surface.lemma_families",),
        ))
    return facts


def _list_normalization_panel_facts(pt: dict[str, Any]) -> list[PanelFact]:
    surface = (
        pt.get("list_normalization_surface")
        if isinstance(pt.get("list_normalization_surface"), dict) else {}
    )
    if not surface:
        return []

    details: list[dict[str, Any]] = []
    for item in surface.get("lemma_families") or []:
        if not isinstance(item, dict):
            continue
        shape = _inline_text(item.get("shape"))
        lemmas = [
            _inline_text(lemma)
            for lemma in item.get("lemma_names") or []
            if _inline_text(lemma)
        ]
        if not shape or not lemmas:
            continue
        details.append(_drop_empty({
            "shape": shape,
            "loaded_family": lemmas,
            "side_condition": _inline_text(item.get("side_condition")),
        }))

    for item in surface.get("nth_map_terms") or []:
        if not isinstance(item, dict):
            continue
        details.append(_drop_empty({
            "term": "nth over map",
            "source_list": _inline_text(item.get("source_list")),
            "index": _inline_text(item.get("index")),
            "side_condition": _inline_text(item.get("side_condition")),
            "side_condition_status": item.get("side_condition_status"),
            "supporting_hypotheses": item.get("supporting_hypotheses"),
        }))

    for item in surface.get("prefix_successor_chains") or []:
        if not isinstance(item, dict):
            continue
        details.append(_drop_empty({
            "shape": _inline_text(item.get("shape")),
            "term": (
                f"map {item.get('mapper')} (take {item.get('index')} "
                f"{item.get('source_list')})"
            ),
            "loaded_chain": [
                _inline_text(step.get("lemma"))
                for step in item.get("lemma_chain") or []
                if isinstance(step, dict) and _inline_text(step.get("lemma"))
            ],
            "side_condition": _inline_text(item.get("side_condition")),
            "side_condition_status": item.get("side_condition_status"),
            "supporting_premises": item.get("supporting_premises"),
        }))

    if not details:
        return []
    return [PanelFact(
        "list_normalization_routes",
        "List normalization routes",
        details,
        summary=(
            "Nested list terms in the current conclusion match these loaded stdlib "
            "families. Any side-condition status is derived only from named local "
            "hypotheses visible in this goal."
        ),
        details=details,
        audit_payload=surface,
        kind="state_fact",
        source_refs=("pure_tail_surface.list_normalization_surface",),
    )]


def _map_update_transport_panel_facts(pt: dict[str, Any]) -> list[PanelFact]:
    surface = (
        pt.get("map_update_transport_surface")
        if isinstance(pt.get("map_update_transport_surface"), dict) else {}
    )
    if not surface:
        return []
    lemmas = [
        _inline_text(surface.get("lookup_normalization_lemma")),
        _inline_text(surface.get("left_inverse_lemma")),
    ]
    value = _drop_empty({
        "shape": _inline_text(surface.get("shape")),
        "pointwise_relation": _inline_text(surface.get("pointwise_relation")),
        "key_transform": _inline_text(surface.get("key_transform")),
        "update_key_pair": surface.get("update_key_pair"),
        "loaded_support": [lemma for lemma in lemmas if lemma],
        "mechanical_effect": _inline_text(surface.get("effect")),
    })
    return [PanelFact(
        "map_update_transport",
        "Finite-map key transport",
        value,
        summary=(
            "A visible pointwise map relation and corresponding transformed update keys "
            "connect get/set normalization with loaded inverse evidence."
        ),
        details=value,
        audit_payload=surface,
        kind="state_fact",
        source_refs=("pure_tail_surface.map_update_transport_surface",),
    )]


def _inline_text(value: Any) -> str:
    return " ".join(str(value or "").replace("`", "").split())


def _current_head(view: dict[str, Any], focus: dict[str, Any]) -> dict[str, Any]:
    frontier = view.get("program_frontier") if isinstance(view.get("program_frontier"), dict) else {}
    alignment = frontier.get("frontier_alignment") if isinstance(frontier.get("frontier_alignment"), dict) else {}
    first = alignment.get("first_instruction_alignment") if isinstance(alignment.get("first_instruction_alignment"), dict) else {}
    left = _normalize_head(first.get("left_head"))
    right = _normalize_head(first.get("right_head"))
    branch = str(first.get("branch_alignment") or "").strip()
    text = str(focus.get("head_now") or "")
    if not (left or right):
        parsed = _parse_head_from_text(text)
        left = parsed.get("left", "")
        right = parsed.get("right", "")
        branch = branch or parsed.get("branch", "")
    pure = _focus_is_pure(focus, view)
    label = _head_label(left, right, branch, text, pure)
    return {
        "left": left,
        "right": right,
        "branch": branch,
        "label": label,
        "pure": pure,
        "raw": text,
    }


def _parse_head_from_text(text: str) -> dict[str, str]:
    lower = text.lower()
    left = ""
    right = ""
    m_left = re.search(r"left\s*=\s*([a-z_<>-]+)", lower)
    m_right = re.search(r"right\s*=\s*([a-z_<>-]+)", lower)
    if m_left:
        left = _normalize_head(m_left.group(1))
    if m_right:
        right = _normalize_head(m_right.group(1))
    if not left:
        for token in ("assignment", "while", "call", "sample", "if"):
            if token in lower:
                left = token
                break
    return {"left": left, "right": right, "branch": ""}


def _normalize_head(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text or text in {"none", "null", "<none>"}:
        return ""
    if "assignment" in text or "assign" in text or "<-" in text:
        return "assignment"
    if "while" in text:
        return "while"
    if "call" in text:
        return "call"
    if "sample" in text or "<$" in text or "rnd" in text:
        return "sample"
    if text == "if" or text.startswith("if"):
        return "if"
    return text


def _head_label(left: str, right: str, branch: str, raw: str, pure: bool) -> str:
    if pure:
        return raw or "pure/probability residual; no program frontier"
    parts = []
    parts.append(f"left={left or 'none'}")
    parts.append(f"right={right or 'none'}")
    if branch:
        parts.append(f"alignment={branch}")
    if left or right:
        return ", ".join(parts)
    return raw or "unknown program frontier"


def _focus_is_pure(focus: dict[str, Any], view: dict[str, Any]) -> bool:
    text = " ".join(str(focus.get(k) or "") for k in ("head_now", "read_this_first"))
    if "no program frontier" in text.lower() or "pure" in text.lower():
        return True
    ps = view.get("proof_status") if isinstance(view.get("proof_status"), dict) else {}
    layer = str(ps.get("current_layer") or ps.get("view_focus") or "").lower()
    return layer in {"pr", "probability", "ambient_logic", "pure_logic"}


def _applicable_tactic_families(
    head: dict[str, Any],
    focus: dict[str, Any],
    view: dict[str, Any] | None = None,
) -> list[str]:
    if head.get("pure"):
        explicit = _families_from_close_with(focus)
        if explicit:
            return explicit
        families = ["smt", "rewrite", "apply"]
        if _pure_has_split_candidate(view or {}):
            families.append("case")
        return families
    heads = {str(head.get("left") or ""), str(head.get("right") or "")} - {""}
    if "assignment" in heads:
        return ["sp", "wp"]
    if "while" in heads:
        return ["while"]
    if "call" in heads:
        return ["call", "inline", "proc"]
    if "sample" in heads:
        return ["rnd"]
    if "if" in heads:
        branch = str(head.get("branch") or "").lower()
        if "diverg" in branch:
            return ["case", "rcondt", "rcondf"]
        return ["if"]
    return []


def _automation_residual_failure(last_result: dict[str, Any], tactic: str) -> bool:
    """A failed automation close is not a structural frontier mismatch.

    EasyCrypt reports ``cannot prove goal (strict)`` when automation runs but the
    residual obligation needs more facts/lemmas.  Recovery should not translate
    that into "the tactic family does not fit this program head".
    """
    if not _tactic_mentions_automation(tactic):
        return False
    text = " ".join(
        str(last_result.get(key) or "").lower()
        for key in ("result", "error_summary", "proof_state")
    )
    return "cannot prove goal" in text


def _tactic_mentions_automation(tactic: str) -> bool:
    return bool(re.search(r"(?<![A-Za-z0-9_])(auto|smt)\b", str(tactic or "")))


def _automation_residual_families(view: dict[str, Any]) -> list[str]:
    families = ["smt", "rewrite", "apply"]
    if _pure_has_split_candidate(view):
        families.append("case")
    return families


def _pure_has_split_candidate(view: dict[str, Any]) -> bool:
    pt = view.get("pure_tail_surface") if isinstance(view.get("pure_tail_surface"), dict) else {}
    arithmetic = (
        pt.get("integer_arithmetic_surface")
        if isinstance(pt.get("integer_arithmetic_surface"), dict) else {}
    )
    return bool(arithmetic.get("split_candidates") if isinstance(arithmetic, dict) else False)


def _families_from_close_with(focus: dict[str, Any]) -> list[str]:
    out: list[str] = []
    values = focus.get("close_with")
    if not isinstance(values, list):
        return out
    for item in values:
        family = _tactic_family(str(item))
        if family and family not in out:
            out.append(family)
    return out[:4]


def _program_head_known(head: dict[str, Any]) -> bool:
    return bool((head.get("left") or head.get("right")) and not head.get("pure"))


def _non_applicable_reason(rejected: str, head: dict[str, Any], applicable: list[str]) -> str:
    return (
        f"`{rejected}` does not reduce the current frontier head "
        f"({head['label']}). Current-state families surfaced for this head: "
        + ", ".join(f"`{family}`" for family in applicable)
        + "."
    )


def _compact_unknown_head_fallback(focus: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for key in ("read_this_first", "head_now", "yours"):
        value = str(focus.get(key) or "").strip()
        if value:
            out.append(value)
    return out[:3]


def _tactic_family(tactic: str) -> str:
    text = str(tactic or "").strip()
    if not text:
        return ""
    text = _strip_label(text)
    match = re.match(r"([A-Za-z_][A-Za-z0-9_]*)", text)
    return match.group(1) if match else ""


def _strip_label(text: str) -> str:
    return re.sub(r"^[A-Za-z ]+:\s*", "", str(text or "")).strip()


def _is_placeholder(value: Any) -> bool:
    text = str(value or "").strip()
    return (
        not text
        or (text.startswith("<") and text.endswith(">"))
        or text.isupper()
        or "..." in text
        or "..." in text
        or "NAME" in text
        or "LEMMA" in text
        or "SYMBOL" in text
        or "QUERY" in text
    )
