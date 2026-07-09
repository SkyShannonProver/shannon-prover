"""Canonical workspace view printed to prover-facing stdout.

ProofContextView is the durable, full-fidelity aggregate artifact.
ProverWorkspaceView is the human-ordered IDE surface printed by ``-agent-view``:
brief turn result/status, exact committed goal, frontier context, selected
application requirements, neutral candidate moves, and semantic inspect handles.

The small navigator below is part of this projection layer: it interprets the
current completed snapshot into advisory, current-view-only navigation items.
It does not execute tactics, inspect EasyCrypt, or own proof truth.

Growth control: this module is a flat function bag that historically absorbed
every new panel concern. New self-contained clusters go in sibling modules and
get imported back (see session_frontier_scope for the pattern); do not add new
panel sections here directly.
"""
from __future__ import annotations

import hashlib
import json
import re
import shlex
from pathlib import Path
from typing import Any

from core.easycrypt.analysis.probability_budget import analyze_probability_budget  # type: ignore
from core.easycrypt.analysis.ec_obligation_gap import unconstrained_post_fields  # type: ignore
from core.easycrypt.analysis.ec_procedure_actions import procedure_navigation_map  # type: ignore
from core.easycrypt.analysis.ec_action_contracts import is_hardcoded_noise_move  # type: ignore
from core.easycrypt.value_shapes import (
    as_dict as _dict,
    as_dict_list as _as_dict_list,
    drop_empty as _drop_empty,
    first_text as _first_text,
)
from core.easycrypt.session_display import (
    leading_statement as _leading_statement,
    preview as _preview,
    statement_head as _statement_head,
    string_list as _string_list,
)
from core.easycrypt.session_frontier_scope import (
    _current_frontier_kind,
    _current_frontier_lookahead,
    _current_frontier_scope,
    _current_frontier_setup,
    _earliest_frontier_path_by_side,
    _first_scope_candidate,
    _frontier_row_path_key,
    _frontier_row_path_text,
    _frontier_row_side_text,
    _frontier_scope_entry,
    _frontier_scope_procedure,
    _frontier_setup_counts,
    _frontier_setup_side,
    _max_path_key,
    _path_key_from_text,
    _path_key_is_descendant,
    _trim_setup_to_earliest_frontier,
)
from core.easycrypt.session_candidate_status import (  # type: ignore
    goal_visibly_closed as _goal_visibly_closed,
    transition_can_mark_closed as _transition_can_mark_closed,
)
from core.easycrypt.session_workspace_view_manager import (  # type: ignore
    DECISION_CONTEXT_PANEL_KEYS,
    DEFAULT_GOAL_WINDOW_CHARS,
    DEFAULT_GOAL_WINDOW_LINES,
    WorkspaceViewManager,
    WorkspaceViewPlan,
    build_workspace_view_plan,
)


PROVER_WORKSPACE_VIEW_SCHEMA_VERSION = 2
PROVER_WORKSPACE_VIEW_KIND = "prover_workspace_view"
GOAL_WINDOW_MAX_LINES = DEFAULT_GOAL_WINDOW_LINES
GOAL_WINDOW_MAX_CHARS = DEFAULT_GOAL_WINDOW_CHARS

def write_prover_workspace_view_artifact(
    session_dir: str | Path,
    view: dict[str, Any],
) -> dict[str, Any]:
    """Persist the exact stdout-facing ProverWorkspaceView."""
    path = Path(session_dir)
    data = dict(view)
    text = json.dumps(data, indent=2, sort_keys=True)
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()
    out_dir = path / "prover_workspace_views"
    out_dir.mkdir(parents=True, exist_ok=True)
    artifact = out_dir / f"prover_workspace_view_{digest[:16]}.json"
    artifact.write_text(text + "\n", encoding="utf-8")

    current_goal = data.get("current_goal") if isinstance(
        data.get("current_goal"), dict,
    ) else {}
    proof_status = data.get("proof_status") if isinstance(
        data.get("proof_status"), dict,
    ) else {}
    if not isinstance(current_goal, dict):
        current_goal = {}
    text_fully_shown = bool(
        current_goal.get("text_fully_shown")
        if "text_fully_shown" in current_goal
        else current_goal.get("complete")
    )
    return {
        "schema_version": int(data.get("schema_version") or 0),
        "view_kind": str(data.get("kind") or ""),
        "ok": bool(data.get("ok")),
        "artifact": str(artifact),
        "view_hash": digest,
        "proof_status": str(proof_status.get("status") or ""),
        "current_goal_text_fully_shown": text_fully_shown,
        "current_goal_truncated": bool(current_goal.get("truncated")),
        "goal_chars": int(current_goal.get("char_count") or 0),
        "workspace_chars": len(json.dumps(data, sort_keys=True)),
    }


def record_prover_workspace_view(
    session_or_dir: Any,
    view: dict[str, Any],
    *,
    source: str = "session_cli",
) -> dict[str, Any]:
    """Write a ProverWorkspaceView artifact and emit an audit event."""
    session_dir = getattr(session_or_dir, "dir", session_or_dir)
    payload = write_prover_workspace_view_artifact(session_dir, view)
    emit = getattr(session_or_dir, "emit_event", None)
    if callable(emit):
        emit("prover.workspace_view.produced", payload, source=source)
    return payload


def build_prover_workspace_view_from_context(
    proof_context_view: dict[str, Any],
    *,
    proof_context_payload: dict[str, Any] | None = None,
    agent_view_payload: dict[str, Any] | None = None,
    max_alternatives: int = 3,
    max_evidence: int = 6,
) -> dict[str, Any]:
    """Return the compact stdout-facing workspace view."""
    view = _dict(proof_context_view)
    payload = _dict(proof_context_payload or agent_view_payload)
    proof_state = _dict(view.get("proof_state"))
    proof_goal = _dict(proof_state.get("goal"))
    current_goal = _dict(view.get("current_goal"))
    proof_ir = _dict(view.get("proof_ir"))
    guidance = _dict(view.get("guidance"))
    debug_refs = _dict(view.get("debug_refs"))
    plan = build_workspace_view_plan(
        view,
        max_alternatives=max_alternatives,
        max_evidence=max_evidence,
    )

    state = _state_panel(
        proof_state=proof_state,
        proof_goal=proof_goal,
        current_goal=current_goal,
        proof_ir=proof_ir,
        plan=plan,
    )
    phase = _phase_panel(proof_ir=proof_ir, state=state, plan=plan)
    frontier = _frontier_panel(
        phase=phase,
        proof_ir=proof_ir,
        state=state,
        plan=plan,
    )
    next_panel = _next_panel(
        view.get("actions"),
        view.get("safe_next_actions"),
        state=state,
        debug_refs=debug_refs,
        max_alternatives=max_alternatives,
    )
    errors = _compact_messages(view.get("errors"), limit=5)
    notes = _compact_messages(view.get("notes"), limit=5)
    workspace = _workspace_panel(
        state=state,
        phase=phase,
        frontier=frontier,
        next_panel=next_panel,
        proof_ir=proof_ir,
        evidence=_dict(view.get("evidence")),
        guidance=guidance,
        errors=errors,
        notes=notes,
        debug_refs=debug_refs,
        payload=payload,
        plan=plan,
        max_evidence=max_evidence,
    )

    out = {
        "schema_version": PROVER_WORKSPACE_VIEW_SCHEMA_VERSION,
        "kind": PROVER_WORKSPACE_VIEW_KIND,
        "ok": bool(view.get("ok")) and not errors,
        **workspace,
    }
    # Forward the committed-proof panel from the context view. It is built in
    # build_proof_context_view (session_agent_view), but this prover-workspace
    # projection is key-shaped (out = {**workspace}), so a panel that is not part
    # of `workspace` is silently dropped unless forwarded explicitly. Without
    # this the agent never sees its own numbered proof — which the index-based
    # amend_and_replay / undo_to_checkpoint intents depend on.
    proof_so_far = view.get("proof_so_far")
    if isinstance(proof_so_far, dict):
        out["proof_so_far"] = proof_so_far
    final = WorkspaceViewManager().sanitize_agent_view(out)
    _audit_panel_invariants(final)
    return final


def _audit_panel_invariants(view: dict[str, Any]) -> None:
    """Defense-in-depth: when SHANNON_PANEL_INVARIANTS is set, run the runtime
    panel-fidelity invariants over the final agent view and LOG any violation (never
    raise). Off by default so it cannot affect a normal run; enable it to catch a new
    goal shape that silently breaks an invariant. See tests/test_panel_properties.py
    for the exhaustive structural coverage."""
    import os
    if not os.environ.get("SHANNON_PANEL_INVARIANTS"):
        return
    try:
        from core.easycrypt.analysis.panel_invariants import check_panel_invariants
        violations = check_panel_invariants(view)
        if violations:
            import logging
            logging.getLogger("shannon.panel_invariants").warning(
                "panel invariant violations: %s", violations)
    except Exception:
        pass


def _state_panel(
    *,
    proof_state: dict[str, Any],
    proof_goal: dict[str, Any],
    current_goal: dict[str, Any],
    proof_ir: dict[str, Any],
    plan: WorkspaceViewPlan,
) -> dict[str, Any]:
    projection_status = _first_text(proof_state.get("status"), default="unknown")
    status = _display_status(
        projection_status=projection_status,
        proof_state=proof_state,
        current_goal=current_goal,
    )
    goal_type = _first_text(
        proof_goal.get("goal_type"),
        current_goal.get("goal_type"),
        proof_ir.get("goal_type"),
        default="unknown",
    )
    raw_goal = _first_text(
        current_goal.get("active_goal_text"),
        current_goal.get("active_goal_preview"),
        default="",
    )
    goal_window = _goal_window(
        raw_goal,
        current_goal=current_goal,
        max_lines=plan.budget.goal_window_lines,
        max_chars=plan.budget.goal_window_chars,
        inspect_order=plan.inspect_order,
    )
    out = {
        "status": status,
        "candidate_ready": bool(proof_state.get("candidate_ready")),
        "final_ready": bool(proof_state.get("final_ready")),
        "goal_type": goal_type,
        "goal_family": plan.goal_family,
        "goal_kind": _first_text(proof_ir.get("goal_kind"), default=""),
        "current_layer": _first_text(proof_ir.get("current_layer"), default=""),
        "remaining_goals": proof_goal.get("num_remaining"),
        "remaining_goals_known": bool(proof_goal.get("num_remaining_determined")),
        "goal_hash": _first_text(
            proof_goal.get("active_goal_hash"),
            current_goal.get("active_goal_hash"),
            default="",
        ),
        "source": _source_contract(proof_goal, current_goal),
        "preview": _preview(raw_goal),
        "goal_window": goal_window,
    }
    if projection_status != status:
        out["projection_status"] = projection_status
    return out


def _goal_window(
    text: str,
    *,
    current_goal: dict[str, Any],
    max_lines: int = GOAL_WINDOW_MAX_LINES,
    max_chars: int = GOAL_WINDOW_MAX_CHARS,
    inspect_order: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    raw = str(text or "").strip("\n")
    lines = raw.splitlines() if raw else []
    char_count = len(raw)
    line_count = len(lines)
    window_lines = list(lines)
    truncated_by_lines = len(window_lines) > max_lines
    if truncated_by_lines:
        window_lines = window_lines[:max_lines]
    window = "\n".join(window_lines)
    truncated_by_chars = len(window) > max_chars
    if truncated_by_chars:
        window = window[: max(0, max_chars - 3)].rstrip() + "..."
        truncated_by_lines = len(window.splitlines()) < line_count
    text_fully_shown = bool(raw) and not truncated_by_lines and not truncated_by_chars
    shown_lines = window.splitlines() if window else []
    out = {
        "lines": shown_lines,
        "text_fully_shown": text_fully_shown,
        "truncated": bool(raw) and not text_fully_shown,
        "line_count": line_count,
        "shown_lines": len(shown_lines),
        "char_count": char_count,
        "shown_chars": len(window),
        "source_field": (
            "current_goal.active_goal_text"
            if current_goal.get("active_goal_text")
            else "current_goal.active_goal_preview"
        ),
        "inspect_order": list(inspect_order or (
            "Read current_goal.lines first; it preserves the current goal as ordered lines.",
            "If text_fully_shown=false, read only the current session's current.out.",
            "For tactic syntax, ask the manager for tactic_forms.",
            "For timeline/confusion, ask the manager for episode_view.",
        )),
    }
    if not text_fully_shown:
        out["current_session_fallback"] = "current.out"
    return _drop_empty(out)


def _workspace_panel(
    *,
    state: dict[str, Any],
    phase: dict[str, Any],
    frontier: dict[str, Any],
    next_panel: dict[str, Any],
    proof_ir: dict[str, Any],
    evidence: dict[str, Any],
    guidance: dict[str, Any],
    errors: list[dict[str, str]],
    notes: list[dict[str, str]],
    debug_refs: dict[str, Any],
    payload: dict[str, Any],
    plan: WorkspaceViewPlan,
    max_evidence: int,
) -> dict[str, Any]:
    """Human-ordered workspace surface for the proving agent."""
    current_goal_panel = _workspace_current_goal(state)
    decision_context = _workspace_decision_context(next_panel)
    _enrich_decision_context(
        decision_context,
        state=state,
        frontier=frontier,
        proof_ir=proof_ir,
        evidence=evidence,
        debug_refs=debug_refs,
    )
    facts = _workspace_facts_and_gaps(phase=phase, frontier=frontier)
    diagnostics = _workspace_diagnostics(
        errors=errors,
        notes=notes,
        limit=max_evidence,
    )
    goal_text = _navigation_goal_text(state)
    probability_budget = analyze_probability_budget(goal_text)
    obligation_gap = unconstrained_post_fields(goal_text)
    more_context = _workspace_want_more_context(
        debug_refs=debug_refs,
        payload=payload,
        plan=plan,
        current_goal_text_fully_shown=bool(
            current_goal_panel.get("text_fully_shown")
        ),
        goal_type=_first_text(state.get("goal_type"), default="").lower(),
        goal_text=goal_text,
    )
    navigation_context = _navigation_context(
        decision_context=decision_context,
        state=state,
        frontier=frontier,
        proof_ir=proof_ir,
        evidence=evidence,
        plan=plan,
    )
    panel = {
        "last_result": {},
        "proof_status": _workspace_proof_status(
            state=state,
            phase=phase,
            plan=plan,
        ),
        "current_goal": current_goal_panel,
        "program_frontier": _workspace_program_frontier(frontier),
        "call_site_surface": _workspace_call_site_surface(navigation_context),
        "application_context": _workspace_application_context(
            decision_context,
            state=state,
            frontier=frontier,
            proof_ir=proof_ir,
            evidence=evidence,
            plan=plan,
            probability_budget=probability_budget,
        ),
        "facts_and_diagnostics": _workspace_facts_and_diagnostics(
            facts=facts,
            diagnostics=diagnostics,
            probability_budget=probability_budget,
            obligation_gap=obligation_gap,
        ),
        "candidate_moves": _workspace_candidate_moves(
            decision_context,
            state=state,
            frontier=frontier,
            proof_ir=proof_ir,
            evidence=evidence,
            plan=plan,
        ),
        "inspect_lookup_handles": _workspace_inspect_lookup_handles(
            more_context=more_context,
            decision_context=decision_context,
            proof_ir=proof_ir,
            offer_call_frontier=_frontier_exposes_call(frontier, goal_text, proof_ir),
            offer_pr_bridge=_goal_is_pr_bridge_candidate(goal_text),
            offer_equiv_bridge=_goal_has_live_bridge_target(goal_text),
            offer_program_surgery=bool(_PROGRAM_BLOCK_RE.search(goal_text or "")),
        ),
    }
    # Delivery wiring (2026-06-09 panel audit): the flag-only mechanism signals
    # the enrichment wrote into the INTERNAL decision_context (CORRECT
    # `up_to_bad_call`; reserved `scaffold_debt`) were a dead-end write — the
    # panel dict never carried a `decision_context` key, so no banner could
    # reach the agent regardless of downstream rendering. Emit ONLY the
    # agent-deliverable panel keys (the internal proof_options/handles are
    # already projected into application_context / candidate_moves above);
    # an empty signal set emits NO key at all.
    decision_signals = {
        key: decision_context[key]
        for key in DECISION_CONTEXT_PANEL_KEYS
        if isinstance(decision_context, dict)
        and isinstance(decision_context.get(key), dict)
        and decision_context.get(key)
    }
    if decision_signals:
        panel["decision_context"] = decision_signals
    return panel


def _workspace_current_goal(state: dict[str, Any]) -> dict[str, Any]:
    goal_window = _dict(state.get("goal_window"))
    source = _dict(state.get("source"))
    text_fully_shown = bool(
        goal_window.get("text_fully_shown")
        if "text_fully_shown" in goal_window
        else goal_window.get("complete")
    )
    out = {
        "lines": _goal_line_list(goal_window.get("lines")),
        "text_fully_shown": text_fully_shown,
        "truncated": bool(goal_window.get("truncated")),
        "goal_type": _first_text(state.get("goal_type"), default="unknown"),
        "view_focus": _first_text(state.get("goal_family"), default=""),
        "line_count": goal_window.get("line_count"),
        "shown_lines": goal_window.get("shown_lines"),
        "char_count": goal_window.get("char_count"),
        "shown_chars": goal_window.get("shown_chars"),
        "source": _drop_empty({
            "label": _first_text(source.get("label"), default=""),
            "ground_truth": source.get("ground_truth"),
        }),
    }
    if not text_fully_shown:
        out["fallback"] = (
            "Read only this session's current.out because the inline goal "
            "was truncated."
        )
    return _drop_empty(out)


def _workspace_proof_status(
    *,
    state: dict[str, Any],
    phase: dict[str, Any],
    plan: WorkspaceViewPlan,
) -> dict[str, Any]:
    # proof_status describes the COMMITTED proof state, not the last action's
    # outcome. A failed/no-progress tactic (or a read-only turn after one) does
    # NOT change the committed state, so "error"/"no_progress" must not be
    # reported here as if the proof itself were in an error state while a goal is
    # still open — that contradicts remaining_goals>0 and the rendered Status
    # line. The action failure is surfaced via last_result / the recovery banner /
    # the diagnose handle, not here.
    status = state.get("status")
    remaining = state.get("remaining_goals")
    if (
        status in {"error", "no_progress", "no_progress_reverted", "refused"}
        and state.get("remaining_goals_known")
        and isinstance(remaining, int)
        and remaining > 0
    ):
        status = "open"
    return _drop_empty({
        "status": status,
        "remaining_goals": remaining,
        "remaining_goals_known": state.get("remaining_goals_known"),
        "goal_type": state.get("goal_type"),
        "view_focus": plan.goal_family,
        "current_layer": phase.get("name") or state.get("current_layer"),
    })


def _workspace_program_frontier(frontier: dict[str, Any]) -> dict[str, Any]:
    return _drop_empty({
        "authority": frontier.get("authority"),
        "view_focus": frontier.get("family"),
        "focus": frontier.get("resource_focus"),
        "local_goal_hints": frontier.get("local_goal_hints"),
        "call_sites": frontier.get("call_sites"),
        "frontier_alignment": frontier.get("frontier_alignment"),
        "current_frontier_scope": frontier.get("current_frontier_scope"),
        "procedure_navigation": frontier.get("procedure_navigation"),
        "checks": frontier.get("checks"),
    })


def _call_site_handle_is_actionable(handle: dict[str, Any]) -> bool:
    """A named call handle worth showing the agent: callable now, or reachable by
    a cut. A non-callable, non-cut *source-lookup landmark* (a lemma signature
    merely found in the source, with its tactic shape hidden) is dangled noise —
    it tells the agent nothing it can act on, so drop it."""
    h = _dict(handle)
    if h.get("callable_now") or h.get("requires_cut_to_frontier"):
        return True
    return str(h.get("call_candidate_kind") or "") not in {
        "source_lookup_landmark", "source_lookup", "landmark",
    }


def _workspace_call_site_surface(context: dict[str, Any]) -> dict[str, Any]:
    route = _dict(_dict(context.get("handles")).get("call_site_route"))
    if not route:
        return {}

    def _keep(items: Any) -> list[dict[str, Any]]:
        return [h for h in _as_dict_list(items) if _call_site_handle_is_actionable(h)]

    return _drop_empty({
        "state": route.get("state"),
        "live_call_sites": _as_dict_list(route.get("live_call_sites"))[:8],
        "named_handles": _keep(route.get("named_handles"))[:8],
        "callable_now": _as_dict_list(route.get("callable_now"))[:8],
        "frontier_live_named_handles": _keep(
            route.get("frontier_live_named_handles")
        )[:8],
        "frontier_blockers": _as_dict_list(route.get("frontier_blockers"))[:8],
        "wrapper_depth": route.get("wrapper_depth"),
        "exposure": _dict(route.get("exposure")),
        "named_call_templates": _as_dict_list(
            route.get("named_call_templates")
        )[:4],
    })


def _workspace_facts_and_gaps(
    *,
    phase: dict[str, Any],
    frontier: dict[str, Any],
) -> dict[str, Any]:
    resources = {}
    resources.update(_dict(phase.get("resources")))
    resources.update(_dict(frontier.get("resource_focus")))
    fact_keys = (
        "missing_live_facts",
        "seq_cut_coverage",
        "coverage",
        "preserved_vars",
        "live_post_vars",
        "prefix_read_vars",
        "has_invariant_skeleton",
        "name_resolution",
        "has_pr_normal_form",
        "has_pr_arithmetic_plan",
        "has_pr_obligation_plan",
        "pr_obligation_primary_strategy",
        "unfoldable_goal_heads",
        "unfoldable_goal_head_count",
        "asymmetric_instrumentation_map",
        "asymmetric_instrumentation_regions",
        "one_sided_instrumentation",
        "instrumentation_regions",
    )
    selected = {
        key: _compact_fact_value(key, resources.get(key))
        for key in fact_keys
        if resources.get(key) not in (None, "", [], {})
    }
    if not selected:
        return {}
    return _drop_empty({
        "surface": _limit_mapping(selected, max_chars=2200),
        "note": (
            "Only current-frontier facts are shown here; the full proof "
            "context artifact keeps the compiler/internal details."
        ),
    })


def _workspace_facts_and_diagnostics(
    *,
    facts: dict[str, Any],
    diagnostics: dict[str, Any],
    probability_budget: dict[str, Any] | None = None,
    obligation_gap: dict[str, Any] | None = None,
) -> dict[str, Any]:
    gap = _dict(obligation_gap)
    gap_signal = (
        {"unconstrained_state": gap.get("fields"), "note": gap.get("note")}
        if gap.get("available") else None
    )
    return _drop_empty({
        "facts": _dict(facts.get("surface")),
        "fact_note": facts.get("note"),
        "probability_budget": probability_budget,
        "gap_signal": gap_signal,
        "errors": diagnostics.get("errors"),
        "notes": diagnostics.get("notes"),
    })


def _workspace_application_context(
    decision_context: dict[str, Any],
    *,
    state: dict[str, Any],
    frontier: dict[str, Any],
    proof_ir: dict[str, Any],
    evidence: dict[str, Any],
    plan: WorkspaceViewPlan | None,
    probability_budget: dict[str, Any] | None = None,
) -> dict[str, Any]:
    invariant_inputs = _dict(decision_context.get("call_invariant_inputs"))
    if invariant_inputs:
        return _call_invariant_application_context(invariant_inputs)

    context = _navigation_context(
        decision_context=decision_context,
        state=state,
        frontier=frontier,
        proof_ir=proof_ir,
        evidence=evidence,
        plan=plan,
    )
    selected: list[dict[str, Any]] = []
    for option in _workspace_proof_options(decision_context, context)[:2]:
        category = _first_text(option.get("category"), default="")
        tactic = _first_text(option.get("tactic"), default="")
        tactic_field = (
            {"tactic": tactic}
            if category in {"commit", "probe"} and tactic else
            {"tactic_shape": tactic}
            if tactic else
            {}
        )
        selected.append(_drop_empty({
            "title": option.get("title"),
            **tactic_field,
            "why_relevant": _first_text(
                option.get("guidance"),
                _first_list_text(option.get("evidence")),
                default="",
            ),
            "runnable_status": option.get("runnable_status"),
            "missing_input": option.get("missing_input"),
            # Carry the option's structured provenance onto the thin twin so the
            # provenance stamper does not mislabel a daemon-probe-accepted handle
            # "unverified" right next to a "Daemon probe accepted…" why_relevant.
            "confidence": option.get("confidence"),
            "epistemic_status": option.get("epistemic_status"),
            "source": option.get("source"),
        }))
    return _drop_empty({"selected_handles": selected})


def _call_invariant_application_context(inputs: dict[str, Any]) -> dict[str, Any]:
    selected_handles: list[dict[str, Any]] = []
    for item in _as_dict_list(inputs.get("call_equiv_context")):
        selected_handles.append(_drop_empty({
            "name": item.get("lemma"),
            "kind": "call-equivalence handle",
            "why_relevant": item.get("why_relevant"),
            "lhs_proc": item.get("lhs_proc"),
            "rhs_proc": item.get("rhs_proc"),
            "tactic_family": "call / ecall",
        }))

    declaration_requirements: list[dict[str, Any]] = []
    for item in _as_dict_list(inputs.get("required_external_facts")):
        declaration_requirements.append(_drop_empty({
            "atom": item.get("fact_shape"),
            "category": "external state fact",
            "read": item.get("why_it_matters"),
            "source_lemma": item.get("source_lemma"),
        }))
    for item in _as_dict_list(inputs.get("base_relation_inputs")):
        for clause in _string_list(item.get("precondition_equalities")):
            declaration_requirements.append(_drop_empty({
                "atom": clause,
                "category": "base relation input",
                "read": item.get("proof_read"),
                "source_lemma": item.get("source_lemma"),
            }))

    residual_obligations = [
        item.get("fact_shape")
        for item in _as_dict_list(inputs.get("required_external_facts"))
        if item.get("fact_shape")
    ]

    return _drop_empty({
        "selected_handles": selected_handles,
        "visible_call_frontier": inputs.get("visible_call_frontier"),
        "declaration_requirements": declaration_requirements,
        "residual_obligations": residual_obligations,
        "visible_but_not_required": inputs.get("visible_but_not_currently_required"),
        "how_to_use": (
            "Use this section when constructing the concrete invariant inside "
            "`call (_: ...)`. "
            + str(inputs.get("runnable_status") or "")
        ).strip(),
        "inspect_if_unsure": inputs.get("inspect_if_unsure"),
    })


# The compiler pushes deterministic FACTS, not proof GUIDANCE. The PRODUCERS now
# drop hardcoded move advice at the source (see `classify_info_kind` in
# ec_action_contracts: `candidate_menu` never carries a bare tactic shape,
# placeholder template, or route-plan). The strategy-bucket filter below is kept as
# a thin BACKSTOP — it also covers the proof-state-driven fallback options that do
# not flow through `candidate_menu` — using the same shared `is_hardcoded_noise_move`
# predicate so the view and the producer can never disagree.


def _workspace_candidate_moves(
    decision_context: dict[str, Any],
    *,
    state: dict[str, Any] | None = None,
    frontier: dict[str, Any] | None = None,
    proof_ir: dict[str, Any] | None = None,
    evidence: dict[str, Any] | None = None,
    plan: WorkspaceViewPlan | None = None,
) -> dict[str, Any]:
    context = _navigation_context(
        decision_context=decision_context,
        state=_dict(state),
        frontier=_dict(frontier),
        proof_ir=_dict(proof_ir),
        evidence=_dict(evidence),
        plan=plan,
    )
    # The move list is the FACTUAL option space — sourced directly from the
    # typed ProofIR `candidate_menu`, not from the heuristic action ranker.
    # `avoid_action` items are a no-progress / liveness-loss demotion the ranker
    # stamps on a candidate; that is a guess about which move is bad, not a
    # static-legality fact, so they are not surfaced (view boundary: no
    # avoid/anti-route panel). Each menu item is run through the same factual
    # enrichment the manager applies (`_proof_option_from_action`: applicability /
    # template scaffolding / lookup hints), then rendered — no ranker order/cap.
    manager = WorkspaceViewManager()
    candidate_menu = _as_dict_list(_dict(proof_ir).get("candidate_menu"))
    moves: list[dict[str, Any]] = []
    for item in candidate_menu:
        if _first_text(_dict(item).get("action_type"), default="") == "avoid_action":
            continue
        option = manager._proof_option_from_action(_menu_item_to_action(item))
        if not option or _is_low_value_unfold_option(option, context):
            continue
        move = _compact_candidate_move(option)
        if move:
            moves.append(move)

    # When ProofIR produced no menu move (a closed candidate whose only move is
    # to finalize with `qed.`/verify, or a state with no typed candidate), fall
    # back to the proof-state-driven options the decision context already
    # carries. These are facts (the finalize move, the safe next step), not
    # ranked suggestions.
    if not moves:
        moves = [
            move
            for option in _workspace_proof_options(decision_context, context)
            if (move := _compact_candidate_move(option))
        ]

    # Backstop (the producers already drop these from `candidate_menu`): in the
    # strategy bucket, keep only state-derived facts. Drop a fill-in TEMPLATE (it
    # carries `missing_input` instantiation guidance — `call (_: Inv)`,
    # `rnd (… <offset>)`) and hardcoded noise (bare shapes / placeholder / plan).
    # Never touch a commit/probe/verified move (a fact, even when bare like `wp.`).
    moves = [
        m for m in moves
        if str(m.get("category") or "").lower() != "strategy"
        or (not m.get("missing_input")
            and not is_hardcoded_noise_move(str(m.get("tactic") or m.get("tactic_shape") or "")))
    ]
    return _drop_empty({"moves": _dedupe_dicts(moves)})


def _navigation_context(
    *,
    decision_context: dict[str, Any],
    state: dict[str, Any],
    frontier: dict[str, Any],
    proof_ir: dict[str, Any],
    evidence: dict[str, Any],
    plan: WorkspaceViewPlan | None,
) -> dict[str, Any]:
    phase = _dict(proof_ir.get("phase"))
    resources = _dict(proof_ir.get("resources"))
    handles = _dict(resources.get("handles"))
    goal_text = _navigation_goal_text(state)
    return {
        "decision_context": decision_context,
        "state": state,
        "frontier": frontier,
        "proof_ir": proof_ir,
        "evidence": evidence,
        "goal_text": goal_text,
        "goal_text_lower": goal_text.lower(),
        "goal_family": _first_text(
            getattr(plan, "goal_family", ""),
            state.get("goal_family"),
            default="",
        ),
        "goal_type": _first_text(state.get("goal_type"), default="").lower(),
        "phase_name": _first_text(
            phase.get("name"),
            state.get("current_layer"),
            proof_ir.get("current_layer"),
            default="",
        ).lower(),
        "phase_prefer": _string_list(phase.get("prefer")),
        "phase_avoid": _string_list(phase.get("avoid")),
        "phase_resources": _dict(phase.get("resource_summary")),
        "resources": resources,
        "handles": handles,
    }


def _navigation_goal_text(state: dict[str, Any]) -> str:
    goal_window = _dict(state.get("goal_window"))
    lines = _goal_line_list(goal_window.get("lines"))
    if lines:
        return "\n".join(lines)
    return _first_text(state.get("preview"), default="")


def _ambient_local_lemma_pack(goal_lower: str) -> list[dict[str, str]]:
    candidates = [
        (
            "Block.block_of_bytesdK",
            (("block_of_bytesd", "bytes_of_block", "block."),),
            "local block/byte conversion cancellation lemma",
        ),
        ("ge0_block_size", (("block_size",),), "local block-size non-negativity fact"),
        ("nth_cat", (("nth",), ("cat", "++")), "list nth over concatenation"),
        ("nth_take", (("nth",), ("take",)), "list nth over take"),
        ("nth_mkseq", (("nth",), ("mkseq",)), "list nth over mkseq"),
        ("size_cat", (("size",), ("cat", "++")), "list size over concatenation"),
        ("size_take", (("size",), ("take",)), "list size over take"),
        ("size_mkseq", (("size",), ("mkseq",)), "list size over mkseq"),
        ("nth_map", (("nth",), ("map",)), "list nth over map"),
        ("size_map", (("size",), ("map",)), "list size over map"),
        ("size_zip", (("size",), ("zip",)), "list size over zip"),
        ("mem_oflist", (("oflist",),), "finite-set membership for list conversion"),
        ("restrS", (("restr",),), "restriction successor/local set lemma"),
        ("is_restrS", (("is_restr",),), "restriction predicate successor/local set lemma"),
        ("is_restr_addS", (("is_restr",), ("fset1", "`|`", "\\|")), "restriction predicate union/local set lemma"),
    ]
    out: list[dict[str, str]] = []
    for symbol, trigger_groups, role in candidates:
        if all(any(trigger in goal_lower for trigger in group) for group in trigger_groups):
            out.append({"symbol": symbol, "role": role})
    return out[:8]


def _ambient_unfold_head(context: dict[str, Any]) -> str:
    heads = _ambient_unfold_heads(context)
    return heads[0] if heads else ""


def _ambient_unfold_heads(context: dict[str, Any]) -> list[str]:
    goal_text = _first_text(context.get("goal_text"), default="")
    out: list[str] = []
    for head in (
        "extend",
        "map2_xor",
        "take_xor",
        "os2bs",
        "bs2os",
        "unpad",
        "pad",
        "parse",
        "restr",
        "is_restr",
        "sxor2",
        "sxor",
        "block_of_bytesd",
        "bytes_of_block",
    ):
        if re.search(rf"\b{re.escape(head)}\b", goal_text):
            out.append(head)
    facts = _dict(context.get("evidence"))
    for item in _as_dict_list(facts.get("unfoldable_goal_heads")):
        name = _first_text(item.get("name"), default="")
        if name and not _is_low_priority_unfold_head(name):
            out.append(name)
    phase_resources = _dict(context.get("phase_resources"))
    for item in _as_dict_list(phase_resources.get("unfoldable_goal_heads")):
        name = _first_text(item.get("name"), default="")
        if name and not _is_low_priority_unfold_head(name):
            out.append(name)
    return _dedupe_strings(out)[:4]


_LOW_PRIORITY_UNFOLD_HEADS = frozenset({"block_size", "zero"})
def _is_low_priority_unfold_head(name: str) -> bool:
    return name.strip() in _LOW_PRIORITY_UNFOLD_HEADS


def _workspace_proof_options(
    decision_context: dict[str, Any],
    context: dict[str, Any],
) -> list[dict[str, Any]]:
    return [
        option
        for option in _as_dict_list(decision_context.get("proof_options"))
        if not _is_low_value_unfold_option(option, context)
    ]


def _is_low_value_unfold_option(option: dict[str, Any], context: dict[str, Any]) -> bool:
    tactic = _first_text(option.get("tactic"), default="")
    match = re.fullmatch(r"\s*rewrite\s+/([A-Za-z_][A-Za-z0-9_.'`]*)\s*\.\s*", tactic)
    if not match:
        return False
    name = match.group(1)
    if not _is_low_priority_unfold_head(name):
        return False
    goal_lower = _first_text(context.get("goal_text_lower"), default="")
    return bool(_ambient_local_lemma_pack(goal_lower) or _ambient_unfold_head(context))




































_MENU_ACTION_TYPE_TO_MOVE_CATEGORY = {
    "inspection_action": "inspect",
    "strategy_hint": "strategy",
    "probe_tactic": "probe",
}


def _menu_item_to_action(item: dict[str, Any]) -> dict[str, Any]:
    """Map a factual ec_proof_ir ``candidate_menu`` item to the action shape the
    factual move enrichment (`_proof_option_from_action`) consumes.

    The candidate move list is sourced from the typed ProofIR menu (the factual
    option space), not from the heuristic action ranker. A menu item carries no
    recommendation prose (no ``guidance``/``why_now``, no rank/confidence), so the
    enrichment produces a fact-only option: ``action_type`` -> a runnable / probe
    / inspect category, the parsed tactic shape, the daemon-``verified`` marker (a
    real provenance fact, kept per the view boundary §5), name-resolution status
    (so an unresolved lemma still gets a lookup hint), and the template-
    instantiation scaffolding. Order/cap/avoid (the ranker's contribution) are not
    translated.
    """
    item = _dict(item)
    action_type = _first_text(item.get("action_type"), default="")
    cost_factors = _dict(item.get("cost_factors"))
    tactic_family = _first_text(item.get("tactic_family"), default="")
    verified = bool(item.get("verified"))
    category = (
        "commit" if (action_type == "probe_tactic" and verified) else
        _MENU_ACTION_TYPE_TO_MOVE_CATEGORY.get(action_type, "strategy")
    )
    action: dict[str, Any] = {
        "category": category,
        "tactic": _first_text(item.get("tactic"), default=""),
        "tactic_family": tactic_family,
        "metadata": {"proof_ir_tactic_family": tactic_family},
        "source": _first_text(item.get("source"), default="ProofIR"),
        "requires_instantiation": bool(
            item.get("requires_instantiation")
            or cost_factors.get("requires_instantiation")
        ),
    }
    name_status = _first_text(cost_factors.get("name_resolution_status"), default="")
    if name_status:
        action["name_resolution_status"] = name_status
        action["cost_factors"] = {"name_resolution_status": name_status}
    if verified:
        # A daemon-checked candidate is ready to run; this is a verified fact,
        # not a confidence guess (see _readiness / view-boundary §5). The
        # epistemic marker drives ready-to-run readiness; the matching
        # confidence enum drives the "verified in a read-only probe" evidence.
        epistemic = _first_text(
            item.get("epistemic_status"), default="daemon_probe_accepted"
        )
        action["epistemic_status"] = epistemic
        action["confidence"] = (
            "verified_by_easycrypt"
            if epistemic in {"easycrypt_verified", "verified_by_easycrypt"}
            else "verified_by_probe"
        )
    action["readiness"] = _readiness(action)
    return action


def _compact_candidate_move(option: dict[str, Any]) -> dict[str, Any]:
    """Render one candidate move without repeating panel-level policy text."""

    category = _first_text(option.get("category"), default="")
    title = _first_text(option.get("title"), default="")
    tactic = _first_text(option.get("tactic"), default="")
    guidance = _preview(_first_text(option.get("guidance"), default=""), limit=220)
    is_mutating_candidate = category in {"commit", "probe"}
    name_status = _candidate_name_resolution_status(option)
    named_call_symbol = _symbol_hint_from_call_shape(tactic)
    unresolved_symbol = (
        named_call_symbol
        if name_status in _UNRESOLVED_NAME_STATUSES else
        ""
    )
    unresolved_or_unverified_call_symbol = unresolved_symbol or (
        named_call_symbol
        if category in {"strategy", "hint"} and named_call_symbol
        else ""
    )
    is_template = bool(
        option.get("missing_input")
        or option.get("runnable_status")
        or "template" in _first_text(option.get("applicability"), default="").lower()
        or "call (_:" in tactic
        and "Inv" in tactic
    )

    tactic_surface = {}
    if tactic:
        if is_mutating_candidate:
            tactic_surface["tactic"] = tactic
        else:
            tactic_surface["tactic_shape"] = tactic

    move = _drop_empty({
        "title": title,
        "category": category,
        **tactic_surface,
        "guidance": guidance,
        "applicability": option.get("applicability"),
        "runnable_status": option.get("runnable_status"),
        "missing_input": option.get("missing_input"),
    })
    # A `call (_: <inv>)` candidate with no `={...}` equality frame is the
    # postcondition shape only — mark it and point at the mechanical frame.
    _ts = tactic_surface.get("tactic_shape") or tactic_surface.get("tactic") or ""
    if "call (_:" in _ts and "={" not in _ts:
        move["needs_frame"] = (
            "Postcondition shape only — no `={...}` equality frame. Build the "
            "`={...}` part from `application_context.write_map` (per candidate "
            "field: who writes it — the read-only/preserved fields are safe to "
            "equate), then add your coupling before this is a usable invariant."
        )
    if unresolved_or_unverified_call_symbol:
        move["symbol_hint"] = unresolved_or_unverified_call_symbol
        move["lookup_before_use"] = {
            "intent": "lookup_symbol",
            "payload": {"symbol": unresolved_or_unverified_call_symbol},
        }
        if not move.get("runnable_status"):
            move["runnable_status"] = (
                "Not established as a live call tactic from this panel. "
                "The declaration is unresolved and the current call frontier is "
                "unchecked on the current goal."
            )
    if is_mutating_candidate:
        move["effect"] = option.get("effect")
        evidence = _preview_list(option.get("evidence"), limit=2, chars=220)
        if evidence:
            move["evidence"] = evidence
        source = _first_text(option.get("source"), default="")
        if source:
            move["source"] = source
    elif is_template:
        for key in ("how_to_complete", "inspect_if_unsure", "limitations"):
            value = option.get(key)
            if value not in (None, "", [], {}):
                move[key] = value
        if unresolved_symbol:
            _append_limitation(
                move,
                "Do not probe or commit the displayed tactic shape until "
                "the lookup_symbol intent confirms the lemma exists in the "
                "current scope.",
            )
        elif unresolved_or_unverified_call_symbol:
            _append_limitation(
                move,
                "Do not probe or commit the displayed call shape solely because "
                "the name is visible; the current frontier still determines "
                "whether it applies.",
            )
    else:
        evidence = _preview_list(option.get("evidence"), limit=1, chars=180)
        if evidence and not guidance:
            move["why_relevant"] = evidence[0]
        source = _first_text(option.get("source"), default="")
        if source:
            move["source"] = source
        if unresolved_symbol:
            _append_limitation(
                move,
                "Treat this as a route landmark, not an executable tactic; "
                "resolve the symbol first with the lookup_symbol intent.",
            )
        elif unresolved_or_unverified_call_symbol:
            _append_limitation(
                move,
                "Treat this as a route landmark, not an executable tactic; "
                "check the declaration and live call-site context before probing it.",
            )
    return _drop_empty(move)


_UNRESOLVED_NAME_STATUSES = frozenset({
    "needs_where_lookup",
    "in_scope_name_without_signature",
    "source_scope_check_required",
    "source_local_scope_check_required",
})


def _candidate_name_resolution_status(option: dict[str, Any]) -> str:
    factors = _dict(option.get("cost_factors"))
    metadata = _dict(option.get("metadata"))
    return _first_text(
        factors.get("name_resolution_status"),
        factors.get("resolution_status"),
        metadata.get("proof_ir_name_resolution_status"),
        default="",
    )


# Bare placeholder / kind words that appear inside *template* tactic shapes
# (e.g. `call lemma.`, `call (_: Inv)`). They are not real EasyCrypt symbol names
# and must never be promoted to a named-call handle symbol — otherwise the
# call-frontier panel renders a phantom `lemma` candidate (the kind word leaking
# into the symbol slot). See also _call_route_named_handles in ec_proof_ir.
_CALL_SHAPE_PLACEHOLDER_SYMBOLS = frozenset(
    {"_", "Inv", "lemma", "equiv", "axiom", "hoare", "phoare"}
)


def _symbol_hint_from_call_shape(text: str) -> str:
    match = re.search(
        r"\b(?:call|ecall)\s+\(?\s*([A-Za-z_][A-Za-z0-9_.'`]*"
        r"(?:\.[A-Za-z_][A-Za-z0-9_.'`]*)*)",
        text,
    )
    if not match:
        return ""
    symbol = match.group(1).strip().rstrip(".")
    if symbol in _CALL_SHAPE_PLACEHOLDER_SYMBOLS or symbol.startswith("<"):
        return ""
    return symbol


def _append_limitation(move: dict[str, Any], text: str) -> None:
    limitations = move.get("limitations")
    if not isinstance(limitations, list):
        limitations = []
    if text not in limitations:
        limitations.append(text)
    move["limitations"] = limitations


# Inspect topics that only mean something at a CALL frontier. On a goal with
# nothing to call they return an empty "no_route" / "no concrete call" result, so
# offering them there is pure noise — a handle the agent/human clicks into an
# empty panel. Gate them on the frontier actually exposing a call.
_CALL_FRONTIER_TOPICS = frozenset({
    "call_site_options",
    "call_invariant_skeleton",
    "call_subgoals",
})


def _frontier_exposes_call(
    frontier: dict[str, Any],
    goal_text: str,
    proof_ir: dict[str, Any] | None,
) -> bool:
    """True when there is a call to reason about — a visible call site, a `<@`
    call in the goal text, or a call tactic already in the proof-IR menu. Mirrors
    the availability test `_call_invariant_inputs` uses, so the call-frontier
    inspect handles are offered exactly when one of them could return content.

    Errs toward offering: a count-form summary (`resource_focus`, the no-raw-IR
    path) or a named callable lemma is enough — only a frontier with no call
    signal at all suppresses the handles."""
    frontier = _dict(frontier)
    if _as_dict_list(frontier.get("call_sites")):
        return True
    focus = _dict(frontier.get("resource_focus"))
    for key in ("frontier_call_sites", "live_callable_lemmas"):
        try:
            if int(focus.get(key) or 0) > 0:
                return True
        except (TypeError, ValueError):
            pass
    if " <@ " in (goal_text or ""):
        return True
    return _menu_offers_call_invariant(_dict(proof_ir))


# Pr-bridge inspect topics relate TWO probabilities (a game hop / Pr-equality).
# A single `Pr[P] = const`/bound is a direct byphoare-style computation with no
# bridge, so on it they return an empty "no matching context" — offered noise.
_PR_BRIDGE_TOPICS = frozenset({
    "pr_bridge_routes",
    "equiv_bridge_lemmas",
})


def _goal_is_pr_bridge_candidate(goal_text: str) -> bool:
    """True when the goal compares >= 2 `Pr[...]` terms over DISTINCT programs — the
    precondition for a Pr/equiv bridge (a game hop) to exist. A single Pr term (against
    a constant or a non-Pr bound) is a direct computation, not a bridge. Several Pr over
    the SAME program@memory (a union / big-sum / measure bound) is also not a bridge —
    no second program to relate. (FIX#3, deep audit Tier-C: step4_lbad1_sum
    `Pr[A:E] <= big(fun i => Pr[A:E_i])` over one program was offered pr_bridge_routes.)

    Errs toward offering: when the program signatures cannot be read (non-`@`-style Pr),
    a multi-Pr goal still gets the handles (their self-describing applicability tells the
    agent to skip)."""
    text = goal_text or ""
    if len(re.findall(r"Pr\s*\[", text)) < 2:
        return False
    progs = re.findall(r"Pr\s*\[\s*([^:\]]*?@[^:\]]*?):", text)
    # Drop ONLY when we can positively read >= 2 program signatures and they are all the
    # same program (a same-program union/measure bound, not a game-hop bridge).
    if len(progs) >= 2 and len({re.sub(r"\s+", "", p) for p in progs}) == 1:
        return False
    return True


def _goal_has_live_bridge_target(goal_text: str) -> bool:
    r"""True when the goal still has TWO distinct programs an equiv/bridge lemma could
    relate. A bridge lemma relates `L.proc ~ R.proc` (or two Pr-game endpoints); it is
    meaningless once EC has aligned the programs (`[programs are in sync]`) or the
    relation has been reduced to a pure pre/post residual with no remaining two-program
    structure. The live two-program signals are: a Pr-bridge candidate (>= 2 `Pr[` over
    distinct programs), an `L.proc ~ R.proc` equiv header, or a still-unaligned
    two-column program block. (FIX-EBL, panel re-audit cluster `EBL_RCD_EGR`:
    Plog_Psample i11 program-empty residual, i35 in-sync coupled branch, i61 in-sync
    post-only residual all got the equiv_bridge offer; the legit i0 `byequiv` Pr-bridge
    is protected by the `Pr[` arm.)"""
    text = goal_text or ""
    if _goal_is_pr_bridge_candidate(text):
        return True
    if "[programs are in sync]" in text:
        return False
    if " ~ " in text:
        return True
    return any(_PROGRAM_BLOCK_RE.search(line) for line in text.splitlines())


def _workspace_inspect_lookup_handles(
    *,
    more_context: dict[str, Any],
    decision_context: dict[str, Any],
    proof_ir: dict[str, Any] | None = None,
    offer_call_frontier: bool = True,
    offer_pr_bridge: bool = True,
    offer_equiv_bridge: bool = True,
    offer_program_surgery: bool = True,
) -> dict[str, Any]:
    ask_manager_for = _as_dict_list(more_context.get("ask_manager_for"))
    action_handles: list[dict[str, Any]] = []
    lookup_candidates: list[dict[str, Any]] = []
    for handle in ask_manager_for:
        lookup_candidates.extend(_lookup_candidates_from_handle_text(handle))
    # Re-source exact signature/declaration lookups (`-where <lemma>`) directly
    # from the FACTUAL candidate_menu, so they survive independent of the
    # recommendation pipeline. These exact-declaration lookups (e.g.
    # `-where pr_CCP_OCCP` for a clone-qualified bridge lemma) are the compiler
    # skeleton the lemma-lookup discipline needs — facts, not suggestions.
    for item in _as_dict_list(_dict(proof_ir).get("candidate_menu")):
        if _first_text(_dict(item).get("action_type"), default="") != (
            "inspection_action"
        ):
            continue
        lookup_candidates.extend(
            _lookup_candidates_from_handle_text({"command": item.get("tactic")})
        )
    for handle in _as_dict_list(decision_context.get("context_handles")):
        if handle.get("kind") == "lookup_symbol":
            lookup_candidates.append(_drop_empty({
                "symbol": handle.get("target"),
                "use_when": handle.get("use_when"),
            }))
            continue
        lookup_candidates.extend(_lookup_candidates_from_handle_text(handle))
        topic = _inspect_topic_from_context_handle(handle)
        if not topic:
            continue
        action_handles.append(_drop_empty({
            "intent": "inspect_context",
            "payload": {"topic": topic},
            "use_when": handle.get("use_when"),
            "returns": "manager-provided read-only context for this proof route",
        }))
    # Drop SPECULATIVE-menu handles that would return an empty result on this goal
    # — call-frontier handles with no call, Pr-bridge handles with no second
    # probability. Only the goal-class MENU (`ask_manager_for` from more_context)
    # is gated; a handle the manager's analysis surfaced (a context handle /
    # safe_next_action -> `action_handles`) is content-driven and always kept.
    suppressed: set[str] = set()
    if not offer_call_frontier:
        suppressed |= _CALL_FRONTIER_TOPICS
    if not offer_pr_bridge:
        suppressed |= _PR_BRIDGE_TOPICS
    if suppressed:
        ask_manager_for = [
            handle for handle in ask_manager_for
            if _first_text(_dict(handle.get("payload")).get("topic"), default="")
            not in suppressed
        ]
    # FIX-EBL (panel re-audit cluster `EBL_RCD_EGR`): `equiv_bridge_lemmas` on a goal
    # with NO live two-program bridge target (in-sync / pure pre-post residual). Unlike
    # the menu-side `_PR_BRIDGE_TOPICS` gate above (which only filters `ask_manager_for`),
    # this offer arrives through the `inspect.bridge_or_align` SAFE-NEXT-ACTION fallback
    # — a BLIND "sole manual entry point" emitted for ANY pRHL/equiv goal when the
    # recommendation queue is empty — so it lands in `action_handles`, which the
    # always-kept assumption above never filters. Suppress it from BOTH lists when the
    # goal has no bridgeable two-program structure (Plog_Psample i11/i35/i61, next move
    # `skip.`/`auto.`). A genuine `L.proc ~ R.proc` or Pr-bridge frontier keeps it
    # (`_goal_has_live_bridge_target`), so the "missed demand" bridge case is preserved.
    if not offer_equiv_bridge:
        ask_manager_for = [
            handle for handle in ask_manager_for
            if _first_text(_dict(handle.get("payload")).get("topic"), default="")
            != "equiv_bridge_lemmas"
        ]
        action_handles = [
            handle for handle in action_handles
            if _first_text(_dict(handle.get("payload")).get("topic"), default="")
            != "equiv_bridge_lemmas"
        ]
    # RTF residual (panel re-audit cluster RTF): the program-surgery `tactic_forms` menu
    # (call/sp/wp/swap/conseq/eager) fans out even on a goal with NO open program block —
    # a collapsed post-predicate (`skip.`), a pure-sample frontier (`rnd.`), or an aligned
    # residual (`auto.`). None of those forms can fire there, so offering them is an
    # off-route nudge (Plog_Psample i42/i43 got the whole surgery menu on a `skip`/`rnd`
    # leaf). `rnd`/`rcondt`/`rcondf` are gated separately by their own structure checks in
    # `_prhl_surgery_tactic_handles`. Gated on a real program block (`<@` call or `( N-- )`
    # two-column dump), so a genuine seq_cut/call surgery frontier keeps the full menu.
    if not offer_program_surgery:
        _surgery_forms = {"call", "sp", "wp", "swap", "conseq", "eager"}
        def _is_surgery_form(handle: Any) -> bool:
            payload = _dict(handle.get("payload"))
            return (
                _first_text(payload.get("topic"), default="") == "tactic_forms"
                and _first_text(payload.get("name"), default="") in _surgery_forms
            )
        ask_manager_for = [h for h in ask_manager_for if not _is_surgery_form(h)]
        action_handles = [h for h in action_handles if not _is_surgery_form(h)]
    ask_manager_for = _dedupe_manager_handles(action_handles + ask_manager_for)
    return _drop_empty({
        "effect": (
            "All handles here are read-only manager requests; the committed "
            "EasyCrypt proof state stays unchanged."
        ),
        "manager_note": (
            "Some requests may ask EasyCrypt or name resolution; wait for the "
            "manager result before choosing the next proof intent."
        ),
        "ask_manager_for": ask_manager_for,
        "lookup_candidates": _dedupe_dicts(lookup_candidates),
        "files": more_context.get("files"),
        "current_session_fallback": more_context.get("current_session_fallback"),
    })


def _inspect_topic_from_context_handle(handle: dict[str, Any]) -> str:
    return _normalize_inspect_topic(
        _first_text(handle.get("target"), handle.get("kind"), default="")
    )


# Bridge inspect topics were renamed to expose the goal layer (pr_ vs equiv_)
# and verified-route vs context-lemmas status. Canonicalize legacy names here so
# handles derived from safe_next_actions / context-handle `target` strings (e.g.
# the backend tool `bridge-lemmas`) surface the new agent-facing name too.
_INSPECT_TOPIC_ALIASES = {
    "bridge_options": "pr_bridge_routes",
    "bridge_lemmas": "equiv_bridge_lemmas",
}


def _normalize_inspect_topic(value: Any) -> str:
    topic = _first_text(value, default="").strip().lstrip("-").replace("-", "_")
    if topic in _LOW_LEVEL_INSPECT_TOPICS or topic in _DEMOTED_INSPECT_TOPICS:
        return ""
    return _INSPECT_TOPIC_ALIASES.get(topic, topic)


# Low-level session-CLI verbs — never agent-facing inspect topics.
_LOW_LEVEL_INSPECT_TOPICS = frozenset({
    "inspect_context",
    "try",
    "next",
    "prev",
    "chain",
    "tactic_exec",
    "commit_tactic",
    "probe_tactic",
})

# Topics DROPPED FROM THE OFFERED MENU by the opus-4-8 panel audit (tools/panel_audit)
# — kept FULLY REACHABLE by blind pull (dispatch is separate; _normalize is offer-side
# only, and the recommendation `category` field is untouched). Two reasons, both
# "do not occupy menu real-estate":
#   DEAD (offered a lot, ~0 pulls, hollow/declined): hint (1011/0, →-goal-info),
#     episode_view (124/0, the agent tracks its own history).
#   REDUNDANT (agent self-serves / goal-derivable; high offer, ~0 transfer): align
#     (the renderer already prints the side-by-side; build_on 0%), lemma_hints (one
#     hop before lookup_symbol; 1760/8).
# NOT here (deliberately kept offered): pr_bridge_routes — K0 re-score showed it USEFUL
# (40 pulls / 40% build_on), only its over-trigger is tightened; rewrite_candidates —
# its offer is the CONTENT-GATED native-search mapping (a verified producer) on thin data
# (1 pull), keep it.
_DEMOTED_INSPECT_TOPICS = frozenset({
    "hint",
    "episode_view",
    "align",
    "lemma_hints",
})


def _lookup_candidates_from_handle_text(handle: dict[str, Any]) -> list[dict[str, Any]]:
    text = " ".join(
        _first_text(handle.get(key), default="")
        for key in ("use_when", "guidance", "why", "returns", "command", "action")
    )
    out: list[dict[str, Any]] = []
    for match in re.finditer(r"(?:^|[`\s])-(?:where|sig)\s+([A-Za-z_][A-Za-z0-9_.'`]*)", text):
        symbol = match.group(1).strip("`'\"").rstrip("`'\".,;:")
        if not symbol:
            continue
        out.append({
            "symbol": symbol,
            "use_when": (
                f"Resolve exact signature for `{symbol}` only when this "
                "handle route is being tested."
            ),
        })
    return _dedupe_dicts(out)


def _compact_fact_value(key: str, value: Any) -> Any:
    if key == "unfoldable_goal_heads":
        compact: list[dict[str, Any]] = []
        for item in _as_dict_list(value)[:4]:
            compact.append(_drop_empty({
                "name": _first_text(item.get("name"), default=""),
                "unqualified_name": _first_text(
                    item.get("unqualified_name"),
                    default="",
                ),
                "declaration_kind": _first_text(
                    item.get("declaration_kind"),
                    default="",
                ),
                "unfold_tactic": _first_text(item.get("unfold_tactic"), default=""),
                "smt_argument_role": _first_text(
                    item.get("smt_argument_role"),
                    default="",
                ),
            }))
        return compact
    return value


def _workspace_decision_context(next_panel: dict[str, Any]) -> dict[str, Any]:
    projected = {
        "suggested_next_steps": _drop_empty({
            "primary": next_panel.get("primary"),
            "alternatives": next_panel.get("alternatives"),
            "context_hints": next_panel.get("background_hints"),
            "avoid": next_panel.get("blocked"),
        }),
    }
    WorkspaceViewManager().normalize_decision_context(projected)
    return _dict(projected.get("decision_context"))


def _enrich_decision_context(
    decision_context: dict[str, Any],
    *,
    state: dict[str, Any],
    frontier: dict[str, Any],
    proof_ir: dict[str, Any],
    evidence: dict[str, Any],
    debug_refs: dict[str, Any] | None = None,
) -> None:
    if decision_context is None:
        return
    # Gate the call-invariant write-map / inputs on whether a call FRONTIER is
    # actually present — use `_frontier_exposes_call`, the same availability mirror
    # `_call_invariant_inputs` uses (call_sites / resource_focus counts / `<@` / a
    # menu call item). Reading only the candidate_menu would suppress the write-map
    # in the placeholder-only adversary case: an un-filled `call (_: <adversary
    # invariant>)` skeleton is GUIDANCE, dropped at the producer, so the menu no
    # longer carries it even though a real call frontier exists. `_call_invariant_inputs`
    # still returns {} (nothing attached) when there is no real frontier.
    goal_text = "\n".join(_goal_line_list(_dict(state.get("goal_window")).get("lines")))
    if _has_call_invariant_option(decision_context) or _frontier_exposes_call(
        frontier, goal_text, proof_ir
    ):
        invariant_inputs = _call_invariant_inputs(
            state=state,
            frontier=frontier,
            proof_ir=proof_ir,
            evidence=evidence,
        )
        if invariant_inputs:
            decision_context["call_invariant_inputs"] = invariant_inputs

    # Mechanism CORRECT — up-to-bad call coherence (flag-only). When the current
    # goal head's POST admits a top-level `\/ bad` disjunct (the relation may break
    # on bad) AND a lockstep `call (_: inv)` move is on offer here, surface a neutral
    # `up_to_bad_call` observation. This is the pure-view path; the history-aware
    # sticky-fact path lives in session_hook_phases._up_to_bad_call_coherence. Both
    # write the SAME `up_to_bad_call` key + text for greppability. `debug_refs`
    # carries the session_dir used for the already-handled committed-call gate and
    # the per-session episode dedup (both best-effort, silently skipped if absent).
    _enrich_up_to_bad_call(decision_context, state=state, debug_refs=debug_refs)


# A rendered-goal line that begins the two-column PROGRAM block (the call statement
# `x <@ M.p(...)` or a column-marker row like `(1------)`), which TERMINATES a
# `pre =`/`post =` relation block. The up-to-bad disjunct lives in the relation
# (pre/post), never in the program columns; feeding the program text through the
# parser is what mis-split step4_1's post and dropped `bad1` (the program block sits
# between `pre =` and `post =` and swallowed the relation when parsed as one blob).
_PROGRAM_BLOCK_RE = re.compile(r"<@|\(\s*\d+(?:\.\d+)*\s*[-?]")

# The REPL prompt line the renderer appends AFTER the goal (e.g. ``[472|check]>``).
# It is NOT part of the relation — but it directly follows the ``post = ...`` block
# (no blank line between), so without stripping it the prompt glues onto the post's
# last disjunct (``... \/ UFCMA.bad1{2}[472|check]>``), making that disjunct a
# multi-token expression whose bad name `_looks_like_event_name` then rejects. We
# treat any line matching the prompt form as a block terminator AND drop it.
_REPL_PROMPT_RE = re.compile(r"^\s*\[\d+\|\w+\]>")


def _pre_post_relation_blocks(lines: list[str]) -> list[str]:
    r"""Pull the ``pre = ...`` and ``post = ...`` RELATION blocks out of a rendered
    EasyCrypt pRHL goal as flat strings.

    The agent-facing goal is the pretty-printed form, NOT `equiv[...]` tactic text:
    it has a ``pre =`` block, then a two-COLUMN program block, then a ``post =``
    block. A block starts at a ``pre =``/``post =`` line and runs over indented
    continuation lines until a blank line, the program block, or the next
    ``pre =``/``post =``. Returning the pre and post relation text SEPARATELY (and
    program-free) is what lets ``up_to_bad_names`` see step4_1's post disjunct
    ``forged{1} => forged{2} \/ bad2 \/ bad1`` AND its parenthesized pre-conjunct
    ``(UFCMA.bad1{2} \/ inv ...)`` without the program columns corrupting the split.
    """
    blocks: list[str] = []
    i = 0
    n = len(lines)
    while i < n:
        raw = str(lines[i])
        m = re.match(r"\s*(pre|post)\s*=(.*)$", raw)
        if not m:
            i += 1
            continue
        # The ``pre =``/``post =`` head text itself may already carry the prompt (a
        # one-line ``post = forged{1} => ... \/ UFCMA.bad1{2}`` rendered with the
        # ``[472|check]>`` appended on the SAME line); strip it off the head too.
        parts = [_REPL_PROMPT_RE.sub("", m.group(2)).strip()]
        i += 1
        while i < n:
            cont = str(lines[i])
            if not cont.strip():
                break  # blank line ends the block
            if _REPL_PROMPT_RE.match(cont):
                break  # REPL prompt line (`[NNN|check]>`) ends the goal — drop it
            if re.match(r"\s*(pre|post)\s*=", cont):
                break  # next relation block
            if _PROGRAM_BLOCK_RE.search(cont):
                break  # program block (two-column statements) ends the relation
            parts.append(cont.strip())
            i += 1
        block = " ".join(p for p in parts if p).strip()
        if block:
            blocks.append(block)
    return blocks


def _up_to_bad_names_in_goal(lines: list[str]) -> set[str]:
    r"""Union of ``up_to_bad_names`` over the pre/post relation blocks of a rendered
    goal. Falls back to the whole flat goal text when no ``pre =``/``post =`` block is
    found (e.g. a bare-disjunction or `equiv[...]`-shaped goal carried inline)."""
    try:
        from core.easycrypt.up_to_bad_coherence import up_to_bad_names
    except Exception:
        try:
            from core.easycrypt.up_to_bad_coherence import up_to_bad_names  # type: ignore
        except Exception:
            return set()
    names: set[str] = set()
    blocks = _pre_post_relation_blocks(lines)
    if blocks:
        for block in blocks:
            names |= up_to_bad_names(block)
    else:
        names |= up_to_bad_names("\n".join(lines))
    return names


# Episode dedup for the pure-view `up_to_bad_call` flag (audit 2026-06-09: the same
# banner repeated over 24 consecutive views in step4_1 scratch Tree_0_0 — 54
# fire-views carried ~4 facts). Keyed by the session_dir from debug_refs; when no
# session identity is available (unit tests, detached projections) dedup is OFF so
# the function stays a pure projection. Value = the last (bad-set, candidate) fact
# surfaced in the current episode; an episode ends when the goal stops carrying any
# harvested bad (frontier moved on), after which the same fact may fire again.
_UP_TO_BAD_EPISODE_LATCH: dict[str, tuple[tuple[str, ...], str] | None] = {}

# E3 re-arm ledger (audit 2026-06-09): the generic frontier re-arm (`_note_up_to_bad
# _episode(scope, None)` when the goal stops carrying a harvested bad) never triggers
# in step4_1 scratch Tree_0_0 — the goal carries `bad1, bad2` for its WHOLE lifetime,
# so the episode never ends and the fact, latched at t3/t4, can never re-surface at
# the decisive t29 (agent commits the WRONG one-segment `call (_: forged => ... \/
# bad)`, gets it accepted-but-undischargeable, then gives up at t30). E3 adds a
# SECOND, call-event re-arm: when a NEW relational `call (_: ...)` is committed that
# is STILL not the 2-clause up-to-bad form carrying the bad, the same latched fact may
# fire ONCE more (one re-fire per such call event). This ledger records, per scope,
# the set of call-signatures we have already consumed for re-arming, so a single
# committed non-uptobad call re-arms at most once (no return to 24-view spam).
_UP_TO_BAD_REARM_CONSUMED: dict[str, set[str]] = {}


def _note_up_to_bad_episode(
    scope: str, fact: tuple[tuple[str, ...], str] | None
) -> None:
    if not scope:
        return
    if len(_UP_TO_BAD_EPISODE_LATCH) > 512:  # bounded memory, never grows unbounded
        _UP_TO_BAD_EPISODE_LATCH.clear()
        _UP_TO_BAD_REARM_CONSUMED.clear()
    _UP_TO_BAD_EPISODE_LATCH[scope] = fact


def _latest_committed_call_sig(scope: str) -> str:
    r"""Signature of the most recent committed RELATIONAL ``call (_: ...)`` in this
    scope's history, whitespace-collapsed; ``""`` when none / unavailable.

    Reuses ``latest_relational_call`` (skips lemma-application + one-sided phoare
    calls), so the signature only changes when a NEW *relational* call is committed —
    the exact event E3's re-arm keys on. Best-effort: any read/parse failure yields
    ``""`` (no re-arm), preserving the never-raise / flag-only contract."""
    if not scope:
        return ""
    try:
        from core.easycrypt.up_to_bad_coherence import (  # type: ignore
            latest_relational_call,
        )
    except Exception:
        try:
            from core.easycrypt.up_to_bad_coherence import latest_relational_call  # type: ignore
        except Exception:
            return ""
    try:
        hist = Path(scope) / "history.ec"
        if not hist.exists():
            return ""
        tactics = [
            ln.strip()
            for ln in hist.read_text(encoding="utf-8", errors="replace").splitlines()
            if ln.strip()
        ]
        return latest_relational_call(tactics).replace(" ", "")
    except Exception:
        return ""


def _rearm_on_new_non_uptobad_call(scope: str, bad_names: set[str]) -> bool:
    r"""E3 re-arm decision: True when a NEW relational ``call (_: ...)`` has been
    committed in this scope that is STILL not the 2-clause up-to-bad form carrying an
    active bad — and we have NOT already consumed that exact call signature for a
    re-arm. Records the signature as consumed so the re-arm fires at most once per
    committed non-uptobad call (no return to the 24-view banner spam).

    Mirrors gate (c)'s history read but with INVERTED polarity: gate (c) SILENCES
    when the latest relational call IS the handled 2-clause form; this re-arms when
    the latest relational call is the WRONG (lockstep / non-bad) form — exactly the
    step4_1 scratch t29 ``call (_: forged{1} => forged{2} \/ bad2 \/ bad1).`` (a
    single-clause lockstep call, not ``call (_: bad, inv)``)."""
    if not scope:
        return False
    sig = _latest_committed_call_sig(scope)
    if not sig:
        return False
    # If this latest relational call ALREADY carries an active bad as a 2-clause
    # up-to-bad form, it is handled — gate (c) owns that case; never re-arm on it.
    try:
        from core.easycrypt.up_to_bad_coherence import (  # type: ignore
            is_lockstep_call,
        )
    except Exception:
        try:
            from core.easycrypt.up_to_bad_coherence import is_lockstep_call  # type: ignore
        except Exception:
            return False
    if not is_lockstep_call(sig):
        # A 2-clause call: re-arm only if it does NOT carry any active bad (i.e. it is
        # a 2-clause but for the wrong bad). If it carries the bad, gate (c) silences.
        if any(b.replace(" ", "") in sig for b in bad_names):
            return False
    consumed = _UP_TO_BAD_REARM_CONSUMED.setdefault(scope, set())
    if sig in consumed:
        return False  # already re-armed once on this committed call — no spam
    if len(consumed) > 256:  # bounded memory
        consumed.clear()
    consumed.add(sig)
    return True


def _offered_call_option_texts(decision_context: dict[str, Any]) -> list[str]:
    """The full text of every call-invariant move on offer (template included).

    Superset of `_has_call_invariant_option`'s fields: `tactic_shape` is included
    so the offered TEMPLATE text (where the rendered invariant lives) is visible
    to the already-handled gate below."""
    texts: list[str] = []
    for option in _as_dict_list(decision_context.get("proof_options")):
        text = " ".join(
            _first_text(option.get(key), default="")
            for key in ("title", "tactic", "tactic_shape", "guidance", "applicability")
        )
        if "call (_:" in text or "Invariant-call" in text:
            texts.append(text)
    return texts


def _extract_call_invariants_from_text(text: str) -> list[str]:
    r"""Every `call (_: <inv>)` invariant argument embedded in a free-form offer
    string, extracted by BALANCED-paren matching.

    The end-anchored `_call_invariant_arg` regex in `up_to_bad_coherence` does NOT
    apply here: an offer text carries trailing prose after the call template
    (`... call (_: UFCMA.bad1{2} /\ (...)).   Use this as route-selection ...`), so
    we must locate the `(` that opens the `(_: ...)` group and balance-match its
    close rather than anchor on end-of-string."""
    invs: list[str] = []
    for mt in re.finditer(r"call\s*\(\s*_\s*:", text):
        open_idx = text.rfind("(", mt.start(), mt.end())
        if open_idx < 0:
            continue
        depth = 0
        j = open_idx
        n = len(text)
        while j < n:
            c = text[j]
            if c in "({":
                depth += 1
            elif c in ")}":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        if depth != 0:
            continue
        inner = text[open_idx + 1 : j]  # `_: <inv>`
        colon = inner.find(":")
        if colon < 0:
            continue
        invs.append(inner[colon + 1 :].strip())
    return invs


def _invariant_top_conjunct_flags(inv: str) -> set[str]:
    r"""Bare bad-flag names that appear as a TOP-LEVEL CONJUNCT of an invariant
    expression — descending fully-parenthesized conjunct groups, splitting on both
    `/\` and `&&`. Positive twin of `_goal_negated_bad_conjuncts` (which collects
    the NEGATED `!bad` conjuncts); here a bare positive conjunct `UFCMA.bad1{2}`
    means the invariant ASSERTS/carries that bad as a maintained fact.

    A bad inside a disjunction or an implication consequent (`r{1} => ... \/ bad`)
    is NOT a top-level conjunct, so it is deliberately not collected."""
    try:
        from core.easycrypt.up_to_bad_coherence import (
            _looks_like_event_name,
            _peel_wrapping_group,
            _split_top_conjuncts,
            _strip_side_annot,
        )
    except Exception:
        try:
            from core.easycrypt.up_to_bad_coherence import (  # type: ignore
                _looks_like_event_name,
                _peel_wrapping_group,
                _split_top_conjuncts,
                _strip_side_annot,
            )
        except Exception:
            return set()
    found: set[str] = set()

    def _walk(seg: str, depth: int) -> None:
        if depth > 8:
            return
        seg = seg.strip()
        if not seg:
            return
        pieces = [p.strip() for p in _split_top_conjuncts(seg) if p.strip()]
        if len(pieces) != 1 or pieces[0] != seg:
            for p in pieces:
                _walk(p, depth + 1)
            return
        peeled = _peel_wrapping_group(seg)
        if peeled != seg:
            _walk(peeled, depth + 1)
            return
        cand = _strip_side_annot(seg)
        if _looks_like_event_name(cand):
            found.add(cand)

    _walk(inv, 0)
    return found


def _offer_already_handles_bad(offer_texts: list[str], bad_names: set[str]) -> bool:
    r"""Already-handled gate (a): the on-offer call template already carries/guards
    every active bad, so the frontier is INSIDE handled up-to-bad territory and
    re-offering the up-to-bad form here is wrong-domain. Two recognized shapes:

    (a1) NEGATED mention `!UFCMA.bad1{2}` anywhere in the offer text — the offered
        invariant guards that bad (typically obligation (1) of an earlier 2-clause
        call). Any-match over the active bads (audit 2026-06-09: silences the
        step4_1 resume t5/t42/t43 counterfactual FPs whose template literally
        contains `!UFCMA.bad1{2}`).

    (a2) E1 widening (audit 2026-06-09, step4_1 resume Tree_0_0 t34): an offered
        SINGLE-CLAUSE lockstep `call (_: inv)` whose invariant already carries
        EVERY active bad as a TOP-LEVEL CONJUNCT (`call (_: UFCMA.bad1{2} /\
        (UFCMA.bad1{2} \/ inv ...))`) — the agent is already tracking the bad inside
        the call invariant, so nothing to flag.

    A POSITIVE mention that is NOT a top-level conjunct is deliberately NOT enough:
    a one-clause call that merely RESTATES the up-to-bad post in a disjunction
    (`call (_: r{1} => forged{2} \/ ... \/ bad1{2}).`, step4_1 scratch t29) carries
    the bad only inside an implication-consequent disjunction, never as a top
    conjunct — exactly the wrong one-clause form this mechanism exists to flag, so
    it must keep firing."""
    joined = " ".join(offer_texts).replace(" ", "")
    for b in bad_names:
        if "!" + b.replace(" ", "") in joined:
            return True
    # (a2) offered single-clause lockstep call whose invariant carries every bad.
    if not bad_names:
        return False
    try:
        from core.easycrypt.up_to_bad_coherence import is_lockstep_call
    except Exception:
        try:
            from core.easycrypt.up_to_bad_coherence import is_lockstep_call  # type: ignore
        except Exception:
            return False
    norm_bads = {b.replace(" ", "") for b in bad_names}
    for text in offer_texts:
        for inv in _extract_call_invariants_from_text(text):
            if not is_lockstep_call(f"call (_: {inv})."):
                continue  # 2-clause / bare-flag phoare form — not the lockstep shape
            carried = {
                c.replace(" ", "") for c in _invariant_top_conjunct_flags(inv)
            }
            if norm_bads <= carried:
                return True
    return False


def _goal_negated_bad_conjuncts(lines: list[str]) -> set[str]:
    r"""Bad-flag names that appear as a TOP-LEVEL NEGATED CONJUNCT (`... /\
    !UFCMA.bad1{2} /\ ...`) in this goal's pre/post relation blocks — descending
    through fully-parenthesized conjunct groups.

    Already-handled gate (b): such a conjunct means the relation here is already
    stated under `!bad` — this goal lives INSIDE the obligations of some 2-clause
    up-to-bad call (audit 2026-06-09: the 14 wrong-domain views of step4_1 scratch
    carry `!UFCMA.bad1{2}` as a pre conjunct of the agent's own call obligation).
    A negated GUARD (`!bad => rel`) is NOT collected — that is the genuine
    unhandled up-to-bad shape and must keep firing."""
    try:
        from core.easycrypt.up_to_bad_coherence import (
            _looks_like_event_name,
            _peel_wrapping_group,
            _split_top_conjuncts,
            _strip_side_annot,
        )
    except Exception:
        try:
            from core.easycrypt.up_to_bad_coherence import (  # type: ignore
                _looks_like_event_name,
                _peel_wrapping_group,
                _split_top_conjuncts,
                _strip_side_annot,
            )
        except Exception:
            return set()
    found: set[str] = set()

    def _walk(seg: str, depth: int) -> None:
        # Split to FIXPOINT: `_split_top_conjuncts` peels a fully-parenthesized
        # piece while splitting on `&&`, so a returned piece can still carry
        # top-level `/\` structure (the wrong-domain pre's `(a /\ !bad /\ ...)`
        # group comes back as its interior). Recurse until each piece is atomic.
        if depth > 8:
            return
        seg = seg.strip()
        if not seg:
            return
        pieces = [p.strip() for p in _split_top_conjuncts(seg) if p.strip()]
        if len(pieces) != 1 or pieces[0] != seg:
            for p in pieces:
                _walk(p, depth + 1)
            return
        peeled = _peel_wrapping_group(seg)
        if peeled != seg:
            _walk(peeled, depth + 1)
            return
        if not seg.startswith("!"):
            return
        # The WHOLE operand must be a bare flag — `!bad => rel` (negated
        # guard, multi-token) is rejected by _looks_like_event_name.
        cand = _strip_side_annot(seg[1:].strip())
        if _looks_like_event_name(cand):
            found.add(cand)

    for block in _pre_post_relation_blocks(lines):
        _walk(block, 0)
    return found


def _committed_call_already_uptobad(scope: str, bad_names: set[str]) -> bool:
    """Already-handled gate (c): the committed history's most recent RELATIONAL
    `call (_: ...)` is already the 2-clause up-to-bad form carrying one of the
    active bads — the agent has handled the reduction; re-offering it here is the
    counterfactual-FP shape (step4_1 resume t7-t10: prefix L17 already committed
    `call (_: UFCMA.bad1, inv ...)`). Best-effort: reads `<session_dir>/history.ec`
    via debug_refs; any failure means the gate simply does not apply."""
    if not scope:
        return False
    try:
        from core.easycrypt.up_to_bad_coherence import (
            is_lockstep_call,
            latest_relational_call,
        )
    except Exception:
        try:
            from core.easycrypt.up_to_bad_coherence import (  # type: ignore
                is_lockstep_call,
                latest_relational_call,
            )
        except Exception:
            return False
    try:
        hist = Path(scope) / "history.ec"
        if not hist.exists():
            return False
        tactics = [
            ln.strip()
            for ln in hist.read_text(encoding="utf-8", errors="replace").splitlines()
            if ln.strip()
        ]
        latest = latest_relational_call(tactics)
        if not latest or is_lockstep_call(latest):
            return False
        flat = latest.replace(" ", "")
        return any(b.replace(" ", "") in flat for b in bad_names)
    except Exception:
        return False


def _committed_history_uptobad_names(scope: str) -> set[str]:
    r"""Up-to-bad event names harvested from the COMMITTED history (specG wiring).

    SPEC-G #1: the committed-history coherence fact (a `byequiv`/`equiv`/`conseq`/
    `byphoare` whose post admits a top-level `\/ bad` disjunct) was only reachable
    through `inspect_context topic=call_invariant_skeleton`, a topic queried 0 times
    on the six real sequences — so the agent never saw it. This harvests the SAME
    active-bad set the hook path computes (`session_hook_phases._up_to_bad_call_
    coherence`) directly off `<session_dir>/history.ec`, so the per-turn pure-view
    enrichment can union it into the goal-local harvest. We do NOT spin up a parallel
    history scanner: we reuse the manager-owned `history.ec` that gate (c) already
    reads, and the same `up_to_bad_names` parser the goal-local path uses.

    The decisive case (step4_1 resume Tree_0_1 lineage): the byequiv post
    `((res \/ UFCMA.bad2) \/ UFCMA.bad1){2}` is committed at the lineage root (L2),
    but the downstream logical subgoals no longer render the disjunction — so the
    goal-local harvest is ∅ and the pure-view path returned early. With this union
    the fact survives the whole lineage (until a gate silences it).

    Best-effort / never-raise: any missing scope, absent `history.ec`, or parse
    failure yields ∅ (no history contribution), preserving the flag-only contract."""
    if not scope:
        return set()
    try:
        from core.easycrypt.up_to_bad_coherence import up_to_bad_names  # type: ignore
    except Exception:
        try:
            from core.easycrypt.up_to_bad_coherence import up_to_bad_names  # type: ignore
        except Exception:
            return set()
    try:
        hist = Path(scope) / "history.ec"
        if not hist.exists():
            return set()
        names: set[str] = set()
        for raw in hist.read_text(encoding="utf-8", errors="replace").splitlines():
            t = raw.strip()
            if not t:
                continue
            head = t.lower().lstrip("+-* ").split("(")[0].split()
            head = head[0] if head else ""
            if head in ("byequiv", "equiv", "conseq", "byphoare"):
                names |= up_to_bad_names(t)
        return names
    except Exception:
        return set()


def _enrich_up_to_bad_call(
    decision_context: dict[str, Any],
    *,
    state: dict[str, Any],
    debug_refs: dict[str, Any] | None = None,
) -> None:
    """Pure-view CORRECT flag with the audit-2026-06-09 precision gates.

    Fires only when (1) the goal's pre/post harvests >=1 relation-break bad,
    (2) a call-invariant move is on offer, (3) none of the already-handled gates
    (a) offered-template negated mention / (b) goal-level negated-bad conjunct /
    (c) committed 2-clause call holds, and (4) the same (bad-set, candidate) fact
    was not already surfaced this episode (session-scoped dedup). Flag-only and
    never-raise: any internal failure silently degrades to no flag."""
    try:
        if "up_to_bad_call" in decision_context:
            return  # already surfaced upstream; do not clobber
        scope = ""
        if isinstance(debug_refs, dict):
            scope = _first_text(debug_refs.get("session_dir"), default="")
        lines = _goal_line_list(_dict(state.get("goal_window")).get("lines"))
        # SPEC-G #1: the data source for the `up_to_bad_call` fact is the goal-local
        # harvest UNION the committed-history coherence harvest (the byequiv/equiv/
        # conseq/byphoare posts in `history.ec`). The history union is what makes the
        # fact survive a lineage whose downstream subgoals no longer render the
        # up-to-bad disjunction (step4_1 resume Tree_0_1: byequiv post at L2, logical
        # subgoals below carry no `\/ bad`). Both sources feed the SAME three gates
        # and the SAME per-episode dedup ledger below — there is no second emit path,
        # so a fact present in both sources still fires exactly once (no double-fire).
        goal_bad_names = _up_to_bad_names_in_goal(lines)
        history_bad_names = _committed_history_uptobad_names(scope)
        bad_names = goal_bad_names | history_bad_names
        if not bad_names:
            # Episode over — neither the frontier NOR the committed history carries an
            # active bad; the next harvested fact (even an identical one) may fire
            # again. (When history alone carries the bad the episode stays open, which
            # is what keeps the fact alive across the Tree_0_1 logical subgoals.)
            _note_up_to_bad_episode(scope, None)
            return
        # Only fire when a lockstep call is the move actually on offer at this
        # frontier. (Offer-absent views leave the episode latch untouched.)
        offer_texts = _offered_call_option_texts(decision_context)
        if not offer_texts:
            return
        # Already-handled gates (a)/(b)/(c) — see each helper's docstring. Any
        # one of them means this frontier is INSIDE handled up-to-bad territory:
        # surfacing "re-issue your call in up-to-bad form" here is wrong-domain.
        if _offer_already_handles_bad(offer_texts, bad_names):
            return
        if bad_names & _goal_negated_bad_conjuncts(lines):
            return
        if _committed_call_already_uptobad(scope, bad_names):
            return
        sorted_bads = sorted(bad_names)
        bad_disp = ", ".join(f"`{b}`" for b in sorted_bads)
        # E2 (audit 2026-06-09): cover EVERY active relation-break bad. With >1 bad
        # the up-to-bad clause is their disjunction so the candidate/obligations
        # don't silently drop all but the sorted-first one; single-bad wording is
        # unchanged (regression red line). Mirrors `coherence_flag`'s E2 fix.
        if len(sorted_bads) == 1:
            bad_clause = sorted_bads[0]
            guard = f"!{bad_clause}"
        else:
            bad_clause = "(" + " \\/ ".join(sorted_bads) + ")"
            guard = f"!{bad_clause}"
        candidate = f"call (_: {bad_clause}, <inv>)."
        fact = (tuple(sorted_bads), candidate)
        if scope and _UP_TO_BAD_EPISODE_LATCH.get(scope) == fact:
            # Same fact already surfaced this episode. E3 (audit 2026-06-09): the
            # generic frontier re-arm never ends this episode (the goal carries the
            # bad for its whole lifetime), so without a second trigger the fact can
            # never re-surface at the decisive give-up turn. Re-arm ONCE when a NEW
            # relational `call (_: ...)` has been committed that is STILL not the
            # 2-clause up-to-bad form carrying the bad (step4_1 scratch t29's wrong
            # one-segment `call (_: forged => ... \/ bad)`). The three already-handled
            # gates above take priority — we only reach here past all of them.
            if not _rearm_on_new_non_uptobad_call(scope, bad_names):
                return  # no re-arm event — no repeats
        # NOTE the premise wording: the call is ON OFFER here — there may be no
        # committed lockstep call at all, so the text must not claim "your call
        # is lockstep" (audit 2026-06-09: false-premise banner). The history-aware
        # hook path keeps the committed-call phrasing; this is the offer phrasing.
        decision_context["up_to_bad_call"] = {
            "text": (
                f"Upstream postcondition admits `\\/ {bad_clause}`; the "
                f"`call (_: inv)` on offer here is lockstep (no bad clause). These "
                f"games diverge when {bad_disp} fires, so a lockstep call cannot be "
                f"discharged here. Consider the up-to-bad form "
                f"`call (_: {bad_clause}, <inv>)`. It generates these obligations: "
                f"(1) the oracle equiv under `{guard}`, (2) losslessness of both "
                f"oracles after `{bad_clause}`, (3) `{bad_clause}`-preservation."
            ),
            "active_bad_events": sorted(bad_names),
            "candidate": candidate,
            "certified": False,
            "guarantee": (
                "UNCERTIFIED suggestion — a structural coherence observation from "
                "the postcondition shape, NOT a verdict and NOT a gate."
            ),
        }
        _note_up_to_bad_episode(scope, fact)
    except Exception:
        # Flag-only contract: enrichment must never break view building; a
        # half-written entry from a failed enrichment is dropped, not surfaced.
        try:
            if isinstance(decision_context, dict):
                decision_context.pop("up_to_bad_call", None)
        except Exception:
            pass


def _menu_offers_call_invariant(proof_ir: dict[str, Any]) -> bool:
    for item in _as_dict_list(_dict(proof_ir).get("candidate_menu")):
        item = _dict(item)
        if item.get("tactic_family") == "call_invariant_skeleton":
            return True
        if "call (_:" in _first_text(item.get("tactic"), default=""):
            return True
    return False


def _has_call_invariant_option(decision_context: dict[str, Any]) -> bool:
    for option in _as_dict_list(decision_context.get("proof_options")):
        text = " ".join(
            _first_text(option.get(key), default="")
            for key in ("title", "tactic", "guidance", "applicability")
        )
        if "call (_:" in text or "Invariant-call" in text:
            return True
    return False


def _call_invariant_inputs(
    *,
    state: dict[str, Any],
    frontier: dict[str, Any],
    proof_ir: dict[str, Any],
    evidence: dict[str, Any],
) -> dict[str, Any]:
    goal_text = "\n".join(_goal_line_list(_dict(state.get("goal_window")).get("lines")))
    call_sites = _as_dict_list(frontier.get("call_sites"))
    if not call_sites and " <@ " not in goal_text:
        return {}

    left_call = next(
        (site for site in call_sites if _first_text(site.get("side"), default="") == "left"),
        {},
    )
    right_call = next(
        (site for site in call_sites if _first_text(site.get("side"), default="") == "right"),
        {},
    )
    inputs: dict[str, Any] = {
        "use_when": (
            "Use this section when filling the invariant expression inside "
            "`call (_: ...)` for the visible call frontier."
        ),
        "read_first": [
            (
                "The current goal's precondition and postcondition say what "
                "must be related before and after the adversary or oracle call."
            ),
            (
                "The left/right call-frontier rows show which procedure call "
                "the invariant must bridge."
            ),
            (
                "Setup statements before the frontier show initialized maps, "
                "logs, counters, and sampled values that may need to be carried."
            ),
        ],
        "visible_call_frontier": _drop_empty({
            "left": _frontier_site_read(left_call),
            "right": _frontier_site_read(right_call),
        }),
        "runnable_status": (
            "This section is not a tactic. It is a checklist for constructing "
            "the concrete invariant before using `probe_tactic` or "
            "`commit_tactic`."
        ),
        "inspect_if_unsure": {
            "topic": "call_subgoals",
            "why": (
                "After you draft a concrete invariant, this preview shows the "
                "obligations it creates and can reveal missing facts or extra "
                "conjuncts that make the proof harder."
            ),
        },
    }

    selected_handles = _selected_call_equiv_handles(
        proof_ir=proof_ir,
        evidence=evidence,
    )
    if selected_handles:
        inputs["call_equiv_context"] = _call_equiv_context_surface(selected_handles)[:2]
    required_facts = _required_external_facts(selected_handles)
    if required_facts:
        inputs["required_external_facts"] = required_facts
    relation_inputs = _relation_inputs_from_handles(selected_handles)
    if relation_inputs:
        inputs["base_relation_inputs"] = relation_inputs
    visible_unrequired = _visible_state_not_named_in_requirements(
        goal_text=goal_text,
        selected_handles=selected_handles,
        required_facts=required_facts,
    )
    if visible_unrequired:
        inputs["visible_but_not_currently_required"] = visible_unrequired
    return _drop_empty(inputs)


def _frontier_site_read(site: dict[str, Any]) -> dict[str, Any]:
    return _drop_empty({
        "procedure": _first_text(site.get("procedure"), default=""),
        "statement": _first_text(site.get("statement"), default=""),
        "statement_path": _first_text(site.get("statement_path"), default=""),
    })


def _selected_call_equiv_handles(
    *,
    proof_ir: dict[str, Any],
    evidence: dict[str, Any],
) -> list[dict[str, Any]]:
    by_name = _name_resolution_by_name(proof_ir)
    selected: list[dict[str, Any]] = []
    for item in _as_dict_list(evidence.get("context")):
        lemma = _first_text(item.get("lemma"), default="")
        if not lemma:
            continue
        resolution = by_name.get(lemma, {})
        if _first_text(resolution.get("handle_kind"), default="") != "call_equiv":
            continue
        selected.append(_drop_empty({
            "lemma": lemma,
            "call_template": _first_text(item.get("call_template"), default=""),
            "why_relevant": _first_text(item.get("semantic_delta"), default=""),
            "source": "manager call-site context",
            "declaration_source": _first_text(
                resolution.get("fact_source"),
                default="",
            ),
            "declaration": _first_text(resolution.get("declaration"), default=""),
            "lhs_proc": _first_text(resolution.get("lhs_proc"), default=""),
            "rhs_proc": _first_text(resolution.get("rhs_proc"), default=""),
        }))
    selected.sort(key=_call_equiv_relevance_key)
    return selected


def _call_equiv_relevance_key(item: dict[str, Any]) -> tuple[int, str]:
    call_template = _first_text(item.get("call_template"), default="").lower()
    declaration = _first_text(item.get("declaration"), default="")
    clauses = _precondition_clauses(declaration)
    has_external_fact = any(_looks_like_external_fact(clause) for clause in clauses)
    if has_external_fact:
        rank = 0
    elif call_template.startswith("ecall"):
        rank = 1
    else:
        rank = 2
    return rank, _first_text(item.get("lemma"), default="")


def _call_equiv_context_surface(handles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        _drop_empty({
            "lemma": _first_text(item.get("lemma"), default=""),
            "call_template": _first_text(item.get("call_template"), default=""),
            "why_relevant": _first_text(item.get("why_relevant"), default=""),
            "source": _first_text(item.get("source"), default=""),
            "declaration_source": _first_text(item.get("declaration_source"), default=""),
            "lhs_proc": _first_text(item.get("lhs_proc"), default=""),
            "rhs_proc": _first_text(item.get("rhs_proc"), default=""),
        })
        for item in handles
    ]


def _name_resolution_by_name(proof_ir: dict[str, Any]) -> dict[str, dict[str, Any]]:
    resources = _dict(proof_ir.get("resources"))
    handles = _dict(resources.get("handles"))
    candidates = (
        _items_list(resources.get("name_resolution"))
        + _items_list(handles.get("name_resolution"))
    )
    out: dict[str, dict[str, Any]] = {}
    for item in candidates:
        name = _first_text(item.get("name"), default="")
        if name and name not in out:
            out[name] = item
    return out


def _items_list(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict) and isinstance(value.get("items"), list):
        return _as_dict_list(value.get("items"))
    return _as_dict_list(value)


def _required_external_facts(handles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    for handle in handles:
        lemma = _first_text(handle.get("lemma"), default="")
        for clause in _precondition_clauses(_first_text(handle.get("declaration"), default="")):
            if not _looks_like_external_fact(clause):
                continue
            facts.append(_drop_empty({
                "fact_shape": clause,
                "source_lemma": lemma,
                "why_it_matters": (
                    "This fact appears in the selected call-equivalence "
                    "precondition, so the candidate invariant or current state "
                    "must provide it before that lemma can discharge the call."
                ),
            }))
    return _dedupe_dicts(facts)


def _relation_inputs_from_handles(handles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    inputs: list[dict[str, Any]] = []
    for handle in handles:
        lemma = _first_text(handle.get("lemma"), default="")
        clauses = _precondition_clauses(_first_text(handle.get("declaration"), default=""))
        equalities = [
            clause
            for clause in clauses
            if re.search(r"\b\w+\s*=\s*[A-Za-z0-9_.]+\.m(?:\{\d+\})?\b", clause)
        ]
        if equalities:
            inputs.append({
                "source_lemma": lemma,
                "precondition_equalities": equalities,
                "proof_read": (
                    "These equalities identify stable map parameters named by "
                    "the selected call-equivalence lemma. If the proof has a "
                    "file-local invariant over those maps, use that invariant "
                    "as the base relation instead of inventing unrelated map facts."
                ),
            })
    return inputs


def _precondition_clauses(declaration: str) -> list[str]:
    if "==>" not in declaration:
        return []
    before_post = declaration.split("==>", 1)[0]
    if ":" not in before_post:
        return []
    pre = before_post.rsplit(":", 1)[-1]
    clauses = re.split(r"\s*/\\\\\s*|\s*/\\\s*", pre)
    return [clause.strip().rstrip(".") for clause in clauses if clause.strip()]


def _looks_like_external_fact(clause: str) -> bool:
    if "forall" in clause and "\\in" in clause:
        return True
    if re.search(r"!\s*[^\s]+\s*\\in\b", clause):
        return True
    return False


def _visible_state_not_named_in_requirements(
    *,
    goal_text: str,
    selected_handles: list[dict[str, Any]],
    required_facts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    visible_maps = _visible_map_assignments(goal_text)
    if not visible_maps:
        return []
    required_text = " ".join(
        _first_text(item.get("fact_shape"), default="")
        for item in required_facts
    )
    literal_modules = {
        token
        for handle in selected_handles
        for token in re.findall(
            r"\b[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)*\.RO\b",
            _first_text(handle.get("lhs_proc"), default=""),
        )
    }
    out: list[dict[str, Any]] = []
    for item in visible_maps:
        module = item["state"].removesuffix(".m")
        if module not in literal_modules:
            continue
        if module in required_text or item["state"] in required_text:
            continue
        out.append({
            "state": item["state"],
            "why_visible": "It is initialized before the visible call frontier.",
            "why_not_added_by_default": (
                "The selected call-equivalence precondition facts do not name "
                "this state. Add it to an invariant only if a call-subgoal "
                "preview creates an obligation for it."
            ),
        })
    return _dedupe_dicts(out)


def _visible_map_assignments(goal_text: str) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for line in goal_text.splitlines():
        match = re.search(r"\b([A-Za-z][A-Za-z0-9_.]*\.m)\s*<-", line)
        if not match:
            continue
        out.append({
            "state": match.group(1),
            "statement": line.strip(),
        })
    return _dedupe_dicts(out)


def _dedupe_dicts(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for item in items:
        key = json.dumps(item, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def _dedupe_strings(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _workspace_diagnostics(
    *,
    errors: list[dict[str, str]],
    notes: list[dict[str, str]],
    limit: int,
) -> dict[str, Any]:
    return _drop_empty({
        "errors": errors[:limit],
        "notes": notes[:limit],
    })


def _workspace_want_more_context(
    *,
    debug_refs: dict[str, Any],
    payload: dict[str, Any],
    plan: WorkspaceViewPlan,
    current_goal_text_fully_shown: bool,
    goal_type: str = "",
    goal_text: str = "",
) -> dict[str, Any]:
    session_dir = _first_text(debug_refs.get("session_dir"), default="")
    current_out = f"{session_dir}/current.out" if session_dir else "current.out"
    raw_goal_fallback = (
        {}
        if current_goal_text_fully_shown
        else {
            "files": [
                {
                    "path": current_out,
                    "when": (
                        "Only because current_goal.text_fully_shown=false; "
                        "otherwise use current_goal.lines."
                    ),
                }
            ],
            "current_session_fallback": current_out,
        }
    )
    diagnose_handle = {
        "intent": "inspect_context",
        "payload": {"topic": "diagnose"},
        "use_when": "A tactic or probe failed and the latest error needs classification.",
        "returns": "latest-error classification",
    }
    episode_handle = {
        "intent": "inspect_context",
        "payload": {"topic": "episode_view"},
        "use_when": "Need the cross-step proof timeline or confusion history.",
        "returns": "event timeline and goal-count transitions",
    }
    operator_lemmas_handle = _manager_handle(
        "operator_lemmas",
        "Need the lemmas that apply to an OPERATOR in your goal — project-local "
        "lemmas included (not just stdlib) — instead of guessing a lemma name.",
        "lemmas mentioning that operator, found by live EC `search` over the loaded "
        "context (statements; you pick which to apply)",
        payload={"topic": "operator_lemmas", "operator": "OPERATOR"},
        runtime_note=(
            "Live EC search (~seconds). Replace OPERATOR with a symbol from your goal "
            "(e.g. big, sxor2, +^) — OR a tighter term skeleton to narrow a long list, "
            "e.g. (big _ _ (_ :: _)) when the goal applies it to a cons / (_ ++ _) for a cat."
        ),
    )
    base_handles = [
        operator_lemmas_handle,
    ]
    if plan.goal_family == "failure_diagnostic":
        base_handles = [
            diagnose_handle,
            operator_lemmas_handle,
            episode_handle,
        ]
    ask_manager_for = _dedupe_manager_handles(
        base_handles
        + _manager_context_handles(plan.goal_family, goal_type, goal_text=goal_text)
    )
    return _drop_empty({
        "ask_manager_for": ask_manager_for,
        **raw_goal_fallback,
        "full_context_artifact": _first_text(payload.get("artifact"), default=""),
        "full_context": "Additional manager context artifact, when present.",
    })

# Goal types with a single program (one memory). The pRHL "surgery" toolbox is
# the TWO-SIDED relational toolbox; `eager`/`lazy` transformations only relate an
# eager and a lazy program and cannot type-check on one program. (wp/swap/rcondt/
# rcondf/conseq/rnd remain valid single-sided, so only `eager` is gated.)
_SINGLE_SIDED_GOAL_TYPES = frozenset({"hoare", "phoare", "bdhoare"})


def _manager_context_handles(
    goal_family: str, goal_type: str = "", *, goal_text: str = ""
) -> list[dict[str, Any]]:
    # Unknown/empty goal_type -> treat as two-sided (keep the full toolbox); only
    # a DEFINITELY single-sided goal drops the two-sided-only handles.
    two_sided = goal_type.strip().lower() not in _SINGLE_SIDED_GOAL_TYPES
    common = {
        "probability": [
            _manager_handle(
                "pr_bridge_routes",
                (
                    # Self-describing applicability so the agent skips it on the
                    # wrong shape (panel audit: on a Pr-ARITHMETIC goal the agent
                    # click-first'd this, got empty, lost the opening turns).
                    "ONLY when the goal is a Pr-equality/inequality between two "
                    "DISTINCT procedures needing a game-hop or scheme/endpoint "
                    "normalization before byequiv/proc lowering. A Pr-arithmetic "
                    "goal (a sum or bound of Pr terms) lowers directly — skip this."
                ),
                # Honest return: drop the over-promise that lured the click-first.
                "any daemon-verified committable Pr bridge route for this goal — "
                "OFTEN EMPTY (returns none when the goal lowers directly without a hop)",
                runtime_note="May wait while EasyCrypt daemon checks candidate bridge chains.",
            ),
            _manager_handle(
                "equiv_bridge_lemmas",
                "Need pRHL/procedure-equivalence bridge lemma names or context after checking pr_bridge_routes.",
                "context-only equiv bridge lemma candidates (names to look up/apply); not a verified Pr route",
                runtime_note="May wait for EasyCrypt/name-resolution work before returning.",
            ),
            _manager_handle(
                "lemma_hints",
                "Need local lemma hints before choosing a Pr-level proof route.",
                "nearby lemma hints and proof-route context",
                runtime_note="May wait for EasyCrypt/name-resolution work before returning.",
            ),
            _manager_handle(
                "tactic_forms",
                "Need exact byphoare/phoare-loop tactic syntax before probing the probability route.",
                "valid `while` forms and common traps",
                payload={"topic": "tactic_forms", "name": "while"},
            ),
        ],
        "relational_program": [
            _manager_handle(
                "call_site_options",
                "The visible frontier contains call sites or named equiv handles may apply.",
                "call-ready/oracle-equiv context for the current frontier, "
                "plus the BODY of the procedure(s) called here (functor aliases "
                "resolved) so you can see which oracles/state your call invariant "
                "must preserve",
                runtime_note="May wait for EasyCrypt to check call-site candidates.",
            ),
            _manager_handle(
                "call_invariant_skeleton",
                (
                    "You are at an abstract-adversary `call (_: <inv>)` and want "
                    "the mechanical glob frame of the invariant before adding "
                    "your own semantic conjuncts."
                ),
                (
                    "the mechanical `={glob ...}` frame of the call invariant "
                    "(shared abstract oracle modules, daemon-confirmed to apply "
                    "and spawn the obligations). When a named coupling predicate "
                    "fits the in-scope state it ALSO surfaces a field-threaded "
                    "carrier (`inv … s1{1} s2{2}`), plus candidate inductive "
                    "side-conditions (`dom ⊆ used-set`) for any random oracle the "
                    "call queries. All revisable starting points — confirm the "
                    "coupling and add/adjust the semantic conjuncts (key/state "
                    "correspondences, set-membership)."
                ),
                runtime_note=(
                    "May wait while the EasyCrypt daemon probes which module "
                    "globs the call rule accepts."
                ),
            ),
            _manager_handle(
                "call_subgoals",
                (
                    "You are considering `call (_: Inv)` and already have a "
                    "concrete invariant expression you want to test first."
                ),
                (
                    "a read-only preview of the obligations caused by that "
                    "candidate invariant, including pre/init, call-preservation, "
                    "oracle-side, postcondition, missing-fact signals, and "
                    "extra conjuncts that may create avoidable obligations"
                ),
                payload={
                    "topic": "call_subgoals",
                    "invariant": "<the EasyCrypt invariant expression inside call (_: ...)>",
                },
                runtime_note=(
                    "May wait while EasyCrypt previews the obligations; the "
                    "committed proof state remains unchanged."
                ),
            ),
            _manager_handle(
                "tactic_forms",
                "A tactic has multiple EasyCrypt argument forms.",
                "valid tactic forms and common traps",
                payload={"topic": "tactic_forms", "name": "call"},
            ),
            _manager_handle(
                "tactic_forms",
                "The frontier may need indexed `sp i j` before branch or call tactics.",
                "valid `sp` forms and branch-frontier traps",
                payload={"topic": "tactic_forms", "name": "sp"},
            ),
            *_prhl_surgery_tactic_handles(two_sided, goal_text=goal_text),
            _manager_handle(
                "align",
                "LHS/RHS statement order may need swap/alignment context.",
                "swap/alignment context for the visible pRHL frontier",
            ),
        ],
        "procedure_frontier": [
            _manager_handle(
                "call_site_options",
                "The current procedure frontier exposes a call route.",
                "call-ready/oracle-equiv context for the current frontier, "
                "plus the BODY of the procedure(s) called here (functor aliases "
                "resolved) so you can see which oracles/state your call invariant "
                "must preserve",
                runtime_note="May wait for EasyCrypt to check call-site candidates.",
            ),
            _manager_handle(
                "call_subgoals",
                (
                    "You are considering `call (_: Inv)` and already have a "
                    "concrete invariant expression you want to test first."
                ),
                (
                    "a read-only preview of the obligations caused by that "
                    "candidate invariant, including pre/init, call-preservation, "
                    "oracle-side, postcondition, missing-fact signals, and "
                    "extra conjuncts that may create avoidable obligations"
                ),
                payload={
                    "topic": "call_subgoals",
                    "invariant": "<the EasyCrypt invariant expression inside call (_: ...)>",
                },
                runtime_note=(
                    "May wait while EasyCrypt previews the obligations; the "
                    "committed proof state remains unchanged."
                ),
            ),
            _manager_handle(
                "tactic_forms",
                "Need the valid form for call, while, seq, rnd, or rewrite.",
                "valid tactic forms and common traps",
                payload={"topic": "tactic_forms", "name": "call"},
            ),
            _manager_handle(
                "tactic_forms",
                "Need the valid indexed `sp i j` form before opening a branch frontier.",
                "valid `sp` forms and common traps",
                payload={"topic": "tactic_forms", "name": "sp"},
            ),
            _manager_handle(
                "tactic_forms",
                "Need the valid one-sided hoare/phoare loop form.",
                "valid `while` forms and common traps",
                payload={"topic": "tactic_forms", "name": "while"},
            ),
            *_prhl_surgery_tactic_handles(two_sided, goal_text=goal_text),
        ],
        "seq_cut": [
            _manager_handle(
                "call_site_options",
                "The current cut or frontier context may expose a call route.",
                "call-ready/oracle-equiv context for the current frontier, "
                "plus the BODY of the procedure(s) called here (functor aliases "
                "resolved) so you can see which oracles/state your call invariant "
                "must preserve",
                runtime_note="May wait for EasyCrypt to check call-site candidates.",
            ),
            _manager_handle(
                "call_subgoals",
                (
                    "You are considering `call (_: Inv)` and already have a "
                    "concrete invariant expression you want to test first."
                ),
                (
                    "a read-only preview of the obligations caused by that "
                    "candidate invariant, including pre/init, call-preservation, "
                    "oracle-side, postcondition, missing-fact signals, and "
                    "extra conjuncts that may create avoidable obligations"
                ),
                payload={
                    "topic": "call_subgoals",
                    "invariant": "<the EasyCrypt invariant expression inside call (_: ...)>",
                },
                runtime_note=(
                    "May wait while EasyCrypt previews the obligations; the "
                    "committed proof state remains unchanged."
                ),
            ),
            _manager_handle(
                "align",
                "The visible cut may depend on LHS/RHS statement alignment or missing live facts.",
                "swap/alignment context for the visible pRHL frontier",
            ),
            _manager_handle(
                "tactic_forms",
                "Need the valid form for call, seq, while, rnd, or rewrite.",
                "valid tactic forms and common traps",
                payload={"topic": "tactic_forms", "name": "call"},
            ),
            _manager_handle(
                "tactic_forms",
                "The visible cut/frontier may need indexed `sp i j` before branch tactics.",
                "valid `sp` forms and branch-frontier traps",
                payload={"topic": "tactic_forms", "name": "sp"},
            ),
            *_prhl_surgery_tactic_handles(two_sided, goal_text=goal_text),
        ],
        "failure_diagnostic": [
            _manager_handle(
                "diagnose",
                "The latest tactic/probe failed and the error needs classification.",
                "failure classification and repair context",
            ),
            _manager_handle(
                "episode_view",
                "Need to compare the current failure with recent transitions.",
                "proof timeline and recent tactic effects",
            ),
        ],
        "ambient_logic": [
            _manager_handle(
                "lemma_hints",
                "Need local or standard-library lemma names before rewriting a pure goal.",
                "nearby lemma hints and qualified-name lookup guidance",
                runtime_note="May wait for EasyCrypt/name-resolution work before returning.",
            ),
            _manager_handle(
                "tactic_forms",
                "Need the valid EasyCrypt form for rewrite, apply, conseq, while, or SMT setup.",
                "valid tactic forms and common traps",
                payload={"topic": "tactic_forms", "name": "rewrite"},
            ),
        ],
    }.get(goal_family, [])
    return _dedupe_manager_handles(common)


def _prhl_surgery_tactic_handles(
    two_sided: bool = True, *, goal_text: str = ""
) -> list[dict[str, Any]]:
    # wp/swap/rcondt/rcondf/conseq/rnd are all valid on a single program too; only
    # `eager`/`lazy` is two-sided-only. On a single-sided (hoare/phoare) goal we
    # drop `eager` AND replace the relational wording (`sim`, "smaller relation",
    # "one side", "pRHL") with single-program phrasing, so the menu never mis-frames
    # a one-program goal as a two-sided alignment problem.
    if two_sided:
        wp_when = "Mid-proof pRHL suffix surgery may need indexed `wp`."
        wp_ret = "valid indexed `wp` forms and suffix-alignment traps"
        swap_when = "Statement order may need a small `swap` before `sp`, `wp`, or `sim`."
        conseq_when = "A suffix proof may need `conseq` to weaken to a smaller relation before `sim`."
        conseq_ret = "valid `conseq` forms and pRHL memory-annotation traps"
        rnd_when = "One side may have an extra sample or need an explicit sample coupling."
    else:
        wp_when = "Mid-proof suffix may need indexed `wp` to absorb a tail before a cut."
        wp_ret = "valid indexed `wp` forms and suffix traps"
        swap_when = "Statement order may need a small `swap` before `sp` or `wp`."
        conseq_when = "A suffix proof may need `conseq` to weaken the pre/postcondition before closing."
        conseq_ret = "valid `conseq` forms and pre/post-weakening traps"
        rnd_when = "A sampling step may need `rnd` to reduce it to a distribution/probability fact."
    handles = [
        _manager_handle(
            "tactic_forms", wp_when, wp_ret,
            payload={"topic": "tactic_forms", "name": "wp"},
        ),
        _manager_handle(
            "tactic_forms", swap_when,
            "valid `swap` forms and statement-order traps",
            payload={"topic": "tactic_forms", "name": "swap"},
        ),
        _manager_handle(
            "tactic_forms",
            "A guarded branch may need `rcondt` after a case split or invariant fact.",
            "valid `rcondt` forms and guard-obligation traps",
            payload={"topic": "tactic_forms", "name": "rcondt"},
        ),
        _manager_handle(
            "tactic_forms",
            "A guarded branch may need `rcondf` after a case split or invariant fact.",
            "valid `rcondf` forms and guard-obligation traps",
            payload={"topic": "tactic_forms", "name": "rcondf"},
        ),
        _manager_handle(
            "tactic_forms", conseq_when, conseq_ret,
            payload={"topic": "tactic_forms", "name": "conseq"},
        ),
        _manager_handle(
            "tactic_forms", rnd_when,
            "valid `rnd` forms, including one-sided sampling",
            payload={"topic": "tactic_forms", "name": "rnd"},
        ),
        _manager_handle(
            "tactic_forms",
            "A known statement-order mismatch may need an eager/lazy transformation.",
            "valid `eager` forms and when to prefer smaller surgery",
            payload={"topic": "tactic_forms", "name": "eager"},
        ),
    ]
    if not two_sided:
        handles = [
            h for h in handles
            if (h.get("payload") or {}).get("name") != "eager"
        ]
    # FIX-5 (panel re-audit cluster ⑤): gate the STRUCTURE-specific forms on the goal
    # actually containing that structure at THIS frontier. `rnd`/`eager` need a `<$`
    # sample; `rcondt`/`rcondf` need a live `if (…)` program branch. Offering them on a
    # sample-free / branch-free goal is an off-route nudge toward a tactic that cannot
    # fire (observed on sample-free and branch-free benchmark frontiers that still
    # got the whole menu). Per-state correct: when the sample/branch is behind an inline it is not
    # the immediate move, and the hint returns once EC surfaces the `<$`/`if`. `wp`/
    # `swap`/`conseq` stay (generally applicable). Only when goal_text is known — an empty
    # goal_text keeps the full discoverability menu (the no-context fallback / test contract).
    if goal_text:
        drop: set[str] = set()
        if "<$" not in goal_text:
            drop |= {"rnd", "eager"}
        if not re.search(r"\bif\s*\(", goal_text):
            drop |= {"rcondt", "rcondf"}
        # FIX-EBL (panel re-audit cluster `EBL_RCD_EGR`): once EC prints
        # `[programs are in sync]` the two programs are aligned statement-by-
        # statement, so a guarded `if (…)` is RELATIONALLY COUPLED (the same
        # guard on both sides) — `auto`/`sim` discharges it directly, with no
        # case-split. The single-sided `rcondt{i}`/`rcondf{i}` (which force a
        # guard-truth obligation to collapse ONE side) is then an off-route
        # over-commitment, and `eager` cannot apply at all when the statement
        # order already matches (no eager/lazy mismatch). Plog_Psample i35 got
        # the whole branch/order menu on an in-sync coupled `if` whose move was
        # `auto.`. Two-sided `swap`/`wp`/`conseq`/`rnd` stay (still in play in
        # sync). Keyed on the printed marker, so a not-yet-aligned coupled
        # branch (no marker) still gets the case-split handles.
        if "[programs are in sync]" in goal_text:
            drop |= {"rcondt", "rcondf", "eager"}
        if drop:
            handles = [
                h for h in handles
                if (h.get("payload") or {}).get("name") not in drop
            ]
    return handles


def _manager_handle(
    topic: str,
    use_when: str,
    returns: str,
    *,
    payload: dict[str, Any] | None = None,
    runtime_note: str = "",
) -> dict[str, Any]:
    return _drop_empty({
        "intent": "inspect_context",
        "payload": payload or {"topic": topic},
        "use_when": use_when,
        "returns": returns,
        "note": runtime_note,
    })


def _dedupe_manager_handles(handles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for handle in handles:
        payload = (
            dict(handle.get("payload"))
            if isinstance(handle.get("payload"), dict)
            else {}
        )
        key = _normalize_inspect_topic(payload.get("topic") or handle.get("topic"))
        if key == "tactic_forms":
            name = _first_text(payload.get("name"), default="")
            if name:
                key = f"{key}:{name}"
        if not key or key in seen:
            continue
        handle = dict(handle)
        handle.pop("topic", None)
        payload["topic"] = key.split(":", 1)[0]
        handle["payload"] = payload
        seen.add(key)
        out.append(handle)
    return out


def _phase_panel(
    *,
    proof_ir: dict[str, Any],
    state: dict[str, Any],
    plan: WorkspaceViewPlan,
) -> dict[str, Any]:
    phase = _dict(proof_ir.get("phase"))
    if state.get("status") == "candidate_closed_pending_qed":
        return {
            "name": "closed_candidate",
            "summary": (
                "EasyCrypt reports no remaining goals; save the proof with "
                "`qed.` before final verification."
            ),
            "prefer": ["qed.", "verify the saved lemma after qed."],
            "avoid": ["opening new proof structure after the candidate closed"],
            "resources": {},
        }
    layer = _first_text(phase.get("name"), state.get("current_layer"), default="unknown")
    resources = _compact_resources(
        _dict(phase.get("resource_summary")),
        keys=plan.phase_resource_keys,
    )
    return {
        "name": layer,
        "summary": plan.phase_summary,
        "prefer": _string_list(phase.get("prefer"))[:3],
        "avoid": _string_list(phase.get("avoid"))[:3],
        "resources": resources,
    }


def _frontier_panel(
    *,
    phase: dict[str, Any],
    proof_ir: dict[str, Any],
    state: dict[str, Any],
    plan: WorkspaceViewPlan,
) -> dict[str, Any]:
    resources = _dict(phase.get("resources"))
    selected = _limit_mapping(
        {
            key: resources.get(key)
            for key in plan.frontier_resource_keys
            if resources.get(key) not in (None, "", [], {})
        },
        max_chars=plan.budget.frontier_chars,
    )
    regions = _structured_regions(proof_ir, plan=plan)
    call_sites = _frontier_call_sites(proof_ir, plan=plan, goal_text=_state_goal_text(state))
    procedure_frontend = _dict(
        _dict(_dict(proof_ir.get("resources")).get("handles")).get(
            "procedure_body_frontend"
        )
    )
    sync = _goal_programs_are_synchronized(state)
    alignment_rows = _frontier_alignment_rows(
        regions,
        call_sites=call_sites,
        plan=plan,
        synchronized=sync,
    )
    alignment = _frontier_alignment_from_rows(
        alignment_rows,
        plan=plan,
        single_sided=_goal_is_single_sided(state),
        symmetric=sync or _goal_programs_are_symmetric(state),
    )
    # The alignment correctly counts asymmetric two-column setup; feed it to the
    # navigation map so setup depth agrees with the alignment row (the parser's
    # straight_line_prefix under-counts right-only leading statements).
    return _drop_empty({
        "family": plan.goal_family,
        "authority": "ProofIR compiler surface",
        "resource_focus": selected,
        "local_goal_hints": _frontier_local_goal_hints(
            state=state,
            resources=resources,
        ),
        "call_sites": call_sites,
        "frontier_alignment": alignment,
        "current_frontier_scope": _current_frontier_scope(
            {"rows": alignment_rows},
            call_sites=call_sites,
        ),
        "procedure_navigation": procedure_navigation_map(
            procedure_frontend,
            setup_counts=_frontier_setup_counts({"rows": alignment_rows}),
        ),
        "checks": list(plan.frontier_checks),
    })


def _frontier_local_goal_hints(
    *,
    state: dict[str, Any],
    resources: dict[str, Any],
) -> dict[str, Any]:
    """Compact local definitions/facts that explain the visible frontier."""

    goal_text = _navigation_goal_text(state)
    if not goal_text:
        return {}
    unfoldables = _as_dict_list(resources.get("unfoldable_goal_heads"))
    branch_defs: list[dict[str, Any]] = []
    for symbol in _branch_guard_symbols(goal_text):
        match = _find_unfoldable_head(unfoldables, symbol)
        if not match:
            continue
        branch_defs.append(_drop_empty({
            "symbol": _first_text(match.get("name"), default=symbol),
            "kind": _first_text(match.get("declaration_kind"), default=""),
            "unfold_tactic": _first_text(
                match.get("unfold_tactic"),
                default=f"rewrite /{symbol}.",
            ),
            "use_when": (
                "This is the visible branch guard definition; unfold it when "
                "the branch condition becomes the local side condition."
            ),
            "lookup_before_use": {
                "intent": "lookup_symbol",
                "payload": {"symbol": _first_text(match.get("name"), default=symbol)},
            },
        }))

    subtype_facts = _frontier_subtype_fact_hints(
        goal_text=goal_text,
        branch_defs=branch_defs,
    )
    return _drop_empty({
        "branch_guard_definitions": _dedupe_dicts(branch_defs)[:3],
        "local_rewrite_facts": subtype_facts,
    })


def _branch_guard_symbols(goal_text: str) -> list[str]:
    out: list[str] = []
    for match in re.finditer(
        r"\bif\s*\(\s*([A-Za-z_][A-Za-z0-9_']*(?:\.[A-Za-z_][A-Za-z0-9_']*)+)\b",
        goal_text,
    ):
        out.append(match.group(1))
    return _dedupe_strings(out)


def _find_unfoldable_head(
    unfoldables: list[dict[str, Any]],
    symbol: str,
) -> dict[str, Any]:
    target = symbol.strip()
    target_tail = target.rsplit(".", 1)[-1] if "." in target else target
    for item in unfoldables:
        name = _first_text(item.get("name"), default="")
        if name == target:
            return item
    for item in unfoldables:
        name = _first_text(item.get("name"), default="")
        tail = name.rsplit(".", 1)[-1] if "." in name else name
        if tail == target_tail:
            out = dict(item)
            out["name"] = target
            out["unfold_tactic"] = f"rewrite /{target}."
            return out
    return {}


def _frontier_subtype_fact_hints(
    *,
    goal_text: str,
    branch_defs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not branch_defs:
        return []
    compact_goal = re.sub(r"\s+", " ", goal_text)
    candidates: list[tuple[str, str]] = []
    if "C.ofintd" in compact_goal:
        candidates.extend([
            (
                "C.ofintdK",
                "counter subtype well-formedness fact for side conditions opened by a branch guard",
            ),
            (
                "C.toint_ofintd",
                "counter conversion fact useful after unfolding a guard such as `SplitD.test`",
            ),
        ])
    out: list[dict[str, Any]] = []
    for symbol, role in candidates:
        out.append({
            "symbol": symbol,
            "role": role,
            "lookup_before_use": {
                "intent": "lookup_symbol",
                "payload": {"symbol": symbol},
            },
        })
    return _dedupe_dicts(out)[:4]


def _state_goal_text(state: dict[str, Any]) -> str:
    goal_window = _dict(state.get("goal_window"))
    text = "\n".join(_string_list(goal_window.get("lines")))
    if not text:
        text = _first_text(state.get("preview"), default="")
    return text


def _goal_programs_are_synchronized(state: dict[str, Any]) -> bool:
    return "[programs are in sync]" in _state_goal_text(state)


def _goal_is_single_sided(state: dict[str, Any]) -> bool:
    """A phoare/hoare/bdhoare SINGLE-program judgment (one memory, no `~` separator).

    The relational one-sided/symmetric framing does not apply here: there is no second
    program to align, and `sim`/`eager`/two-sided `call` cannot type-check. Calling such a
    goal "one-sided" and advising "a one-sided tactic before a symmetric tactic" misdirects
    the prover (deep audit Tier-B: mee_decrypt_correct phoare `[=]1%r`)."""
    text = _state_goal_text(state)
    if not text or " ~ " in text:
        return False
    low = text.lower()
    return (
        bool(re.search(r"\[\s*(?:=|<=|>=)\s*\]", text))
        or "phoare" in low
        or bool(re.search(r"\bhoare\b", low))
    )


def _goal_programs_are_symmetric(state: dict[str, Any]) -> bool:
    """The two related programs are TEXTUALLY IDENTICAL (`X ~ X`), so the frontier is
    symmetric even before EasyCrypt prints `[programs are in sync]`: a one-sided alignment
    step is unnecessary, the symmetric tactic applies directly (deep audit Tier-B:
    PIR_secure1 `PIR.main ~ PIR.main` mislabeled one-sided)."""
    text = _state_goal_text(state)
    return bool(
        re.search(r"([\w.]+(?:\([^()]*\))?[\w.]*)\s*~\s*\1(?![\w.(])", text)
    )


def _structured_regions(
    proof_ir: dict[str, Any],
    *,
    plan: WorkspaceViewPlan,
) -> list[dict[str, Any]]:
    if plan.goal_family not in {
        "relational_program",
        "procedure_frontier",
        "seq_cut",
        "failure_diagnostic",
    }:
        return []
    handles = _dict(_dict(proof_ir.get("resources")).get("handles"))
    frontend = _dict(handles.get("procedure_body_frontend"))
    regions = _as_dict_list(frontend.get("structured_regions"))
    if not regions:
        regions = _as_dict_list(_dict(frontend.get("frontier_plan")).get("region_summary"))
    return regions


def _frontier_call_sites(
    proof_ir: dict[str, Any],
    *,
    plan: WorkspaceViewPlan,
    goal_text: str = "",
) -> list[dict[str, Any]]:
    if plan.goal_family not in {
        "relational_program",
        "procedure_frontier",
        "seq_cut",
        "failure_diagnostic",
    }:
        return []
    handles = _dict(_dict(proof_ir.get("resources")).get("handles"))
    frontend = _dict(handles.get("procedure_body_frontend"))
    regions = _as_dict_list(frontend.get("structured_regions"))
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()

    def add(site: dict[str, Any]) -> None:
        item = _compact_call_site(site)
        if not item:
            return
        key = (
            str(item.get("side") or ""),
            str(item.get("statement_path") or item.get("path") or ""),
            str(item.get("procedure") or ""),
            str(item.get("statement") or ""),
        )
        if key in seen:
            return
        seen.add(key)
        out.append(item)

    for region in regions:
        if _looks_like_call_site(region):
            add(region)
        for side_key in ("left", "right", "statement"):
            side = _dict(region.get(side_key))
            if _looks_like_call_site(side):
                add(side)

    resources = _dict(proof_ir.get("resources"))
    for site in _as_dict_list(resources.get("call_sites")):
        add(site)
    return _live_frontier_call_sites(out, goal_text)[:8]


def _live_frontier_call_sites(
    sites: list[dict[str, Any]], goal_text: str
) -> list[dict[str, Any]]:
    """Keep only call sites that are at the CURRENT frontier of the rendered goal.

    The procedure-body frontend enumerates EVERY call in the program definition, so the raw
    list includes calls that are already CONSUMED (e.g. `a1`/`init` after `sp`) or live only
    in a HYPOTHESIS (a `hoare[...]` premise, not the active frontier). Surfacing those as live
    `call` frontiers is the deep audit's Tier-2 "stale-frontier model" (eq_Game1_Game2
    headlined consumed `a1` as live; step2_1 showed the pre-spawn `A.main()` for a spawned
    `init()`). A call at the ACTIVE frontier is rendered VERBATIM in the goal; a consumed or
    hypothesis-only call is not — so a call whose statement is absent from the goal text is
    not a live frontier and is dropped.

    Deliberately NOT filtered on statement-path depth: a dotted path (`2.1`) is ambiguous —
    it can be a live seq sub-position OR a call buried in a not-yet-entered loop/`if` body, and
    the path alone cannot tell them apart. Conservative: with no goal text, keep everything."""
    goal_norm = " ".join(str(goal_text or "").split())
    if not goal_norm:
        return sites
    kept: list[dict[str, Any]] = []
    for site in sites:
        statement = " ".join(str(site.get("statement") or "").split())
        if not statement:
            kept.append(site)  # no statement to locate — keep (conservative)
            continue
        if statement not in goal_norm and not _call_site_statement_matches_goal(site, goal_norm):
            continue  # consumed / pre-inline / hypothesis-only — not a live frontier call
        kept.append(site)
    return kept


def _call_site_statement_matches_goal(site: dict[str, Any], goal_norm: str) -> bool:
    """Fallback live-call check for EasyCrypt's multi-line program pretty-printer.

    The exact statement match above is the preferred guard against stale call sites.
    It fails, however, when EasyCrypt prints a functor endpoint over many aligned
    table lines (`c2 <@ ChaCha(...).enc(...)`) while ProofIR stores the statement in
    one compact line. In that case, require the assigned variable plus the method
    tail to occur in the same visible `<@ ... .method(` call span.
    """
    statement = " ".join(str(site.get("statement") or "").split())
    lhs_match = re.search(r"\b([A-Za-z_][A-Za-z0-9_']*)\s*<@", statement)
    if not lhs_match:
        return False
    lhs = lhs_match.group(1)
    proc = _first_text(site.get("procedure"), site.get("procedure_tail"), default="")
    method = _call_method_tail(proc)
    if not method:
        stmt_proc_match = re.search(r"\.([A-Za-z_][A-Za-z0-9_']*)\s*\(", statement)
        method = stmt_proc_match.group(1) if stmt_proc_match else ""
    if not method:
        return False
    pattern = (
        r"\b"
        + re.escape(lhs)
        + r"\s*<@\s*.{0,1600}\."
        + re.escape(method)
        + r"\s*\("
    )
    return re.search(pattern, goal_norm) is not None


def _frontier_alignment(
    regions: list[dict[str, Any]],
    *,
    call_sites: list[dict[str, Any]],
    plan: WorkspaceViewPlan,
    synchronized: bool = False,
    single_sided: bool = False,
    symmetric: bool = False,
) -> dict[str, Any]:
    rows = _frontier_alignment_rows(
        regions,
        call_sites=call_sites,
        plan=plan,
        synchronized=synchronized,
    )
    return _frontier_alignment_from_rows(
        rows,
        plan=plan,
        single_sided=single_sided,
        symmetric=symmetric,
    )


def _frontier_alignment_rows(
    regions: list[dict[str, Any]],
    *,
    call_sites: list[dict[str, Any]],
    plan: WorkspaceViewPlan,
    synchronized: bool = False,
) -> list[dict[str, Any]]:
    if plan.goal_family not in {
        "relational_program",
        "procedure_frontier",
        "seq_cut",
        "failure_diagnostic",
    }:
        return []
    rows = _alignment_rows(
        regions,
        call_sites=call_sites,
        synchronized=synchronized,
    )
    call_rows = _alignment_rows_from_call_sites(call_sites, synchronized=synchronized)
    if call_rows:
        kept: list[dict[str, Any]] = []
        seen_call_pairs: set[tuple[str, str]] = set()
        for row in rows:
            role = _first_text(row.get("role"), default="")
            if "call" not in role:
                kept.append(row)
                continue
            if _alignment_row_is_paired(row):
                kept.append(row)
                seen_call_pairs.add(_alignment_row_signature(row))
        for row in call_rows:
            sig = _alignment_row_signature(row)
            if sig in seen_call_pairs:
                continue
            kept.append(row)
            seen_call_pairs.add(sig)
        rows = kept
    return _prioritize_alignment_rows(rows)


def _frontier_alignment_from_rows(
    rows: list[dict[str, Any]],
    *,
    plan: WorkspaceViewPlan,
    single_sided: bool = False,
    symmetric: bool = False,
) -> dict[str, Any]:
    if not rows:
        return {}
    return _drop_empty({
        "summary": _alignment_summary(rows, plan=plan),
        "first_instruction_alignment": _first_instruction_alignment(
            rows, single_sided=single_sided, symmetric=symmetric
        ),
        "rows": rows[:8],
    })


def _alignment_rows(
    regions: list[dict[str, Any]],
    *,
    call_sites: list[dict[str, Any]] | None = None,
    synchronized: bool = False,
) -> list[dict[str, Any]]:
    setup_left: list[dict[str, Any]] = []
    setup_right: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    pending: dict[str, dict[str, list[dict[str, Any]]]] = {}

    for region in regions:
        left = _dict(region.get("left"))
        right = _dict(region.get("right"))
        if left or right:
            row = _alignment_row(
                kind=_first_text(region.get("kind"), default="frontier"),
                left=left,
                right=right,
                region=region,
                synchronized=synchronized,
            )
            if row:
                rows.append(row)
            continue

        side = _first_text(region.get("side"), default="")
        if side not in {"left", "right"}:
            continue
        kind = _first_text(region.get("kind"), default="frontier")
        if _is_setup_region(kind):
            if side == "left":
                setup_left.append(region)
            else:
                setup_right.append(region)
            continue

        key = _alignment_pair_key(region)
        bucket = pending.setdefault(key, {"left": [], "right": []})
        other_side = "right" if side == "left" else "left"
        if bucket[other_side]:
            other = bucket[other_side].pop(0)
            left_region = region if side == "left" else other
            right_region = other if side == "left" else region
            row = _alignment_row(
                kind=kind,
                left=left_region,
                right=right_region,
                region={"kind": kind},
                synchronized=synchronized,
            )
            if row:
                rows.append(row)
        else:
            bucket[side].append(region)

    prefix_left, residual_left = _split_regions_after_call(
        setup_left,
        call_sites or [],
        side="left",
    )
    prefix_right, residual_right = _split_regions_after_call(
        setup_right,
        call_sites or [],
        side="right",
    )
    # The setup row must show the same leading contiguous straight-line prefix as
    # the local setup contract — stop at the first gap in statement order. A gap
    # means a sample/call/loop/branch sat between assignments. A mid-program assign
    # (e.g. pr_G4's 5/8/10/12, sitting after intervening samples) is not part of
    # the leading prefix and must not inflate the "N setup statement(s)" row.
    # The residual-after-call part is split out above and unaffected.
    prefix_left = _leading_contiguous_prefix(prefix_left)
    prefix_right = _leading_contiguous_prefix(prefix_right)

    setup_row = _setup_alignment_row(
        prefix_left,
        prefix_right,
        synchronized=synchronized,
    )
    if setup_row:
        rows.insert(0, setup_row)
    residual_row = _residual_after_call_row(
        residual_left,
        residual_right,
        synchronized=synchronized,
    )
    if residual_row:
        rows.append(residual_row)

    for sides in pending.values():
        for side in ("left", "right"):
            for region in sides[side]:
                row = _alignment_row(
                    kind=_first_text(region.get("kind"), default="frontier"),
                    left=region if side == "left" else {},
                    right=region if side == "right" else {},
                    region=region,
                    synchronized=synchronized,
                )
                if row:
                    rows.append(row)
    return rows


def _leading_contiguous_prefix(
    regions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Keep only the LEADING contiguous run of straight-line statements: stop at the
    first gap in ``statement_order`` (a gap means a sample/call/loop/branch sat
    between the assigns). Matches the setup-prefix depth, so the setup row and
    navigation map never disagree."""
    out: list[dict[str, Any]] = []
    prev: int | None = None
    for region in sorted(
        _as_dict_list(regions),
        key=lambda r: int(_dict(r).get("statement_order") or 0),
    ):
        order = int(_dict(region).get("statement_order") or 0)
        if prev is not None and order != prev + 1:
            break
        out.append(region)
        prev = order
    return out


def _split_regions_after_call(
    regions: list[dict[str, Any]],
    call_sites: list[dict[str, Any]],
    *,
    side: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    call_keys = [
        key for key in (
            _statement_position_key(site)
            for site in call_sites
            if _first_text(site.get("side"), default="") == side
        )
        if key
    ]
    if not call_keys:
        return regions, []
    before: list[dict[str, Any]] = []
    after: list[dict[str, Any]] = []
    for region in regions:
        key = _statement_position_key(region)
        if key and any(key > call_key for call_key in call_keys):
            after.append(region)
        else:
            before.append(region)
    return before, after


def _statement_position_key(region: dict[str, Any]) -> tuple[int, ...]:
    path = _first_text(
        region.get("statement_path"),
        region.get("path"),
        region.get("pos_path"),
        default="",
    )
    if path:
        parts = [int(part) for part in re.findall(r"\d+", path)]
        if parts:
            return tuple(parts)
    for key in ("statement_order", "order", "position", "pos"):
        raw = region.get(key)
        if isinstance(raw, int):
            return (raw,)
        text = str(raw or "").strip()
        if text.isdigit():
            return (int(text),)
    return ()


def _alignment_rows_from_call_sites(
    call_sites: list[dict[str, Any]],
    *,
    synchronized: bool = False,
) -> list[dict[str, Any]]:
    pending: dict[str, dict[str, list[dict[str, Any]]]] = {}
    rows: list[dict[str, Any]] = []
    for site in call_sites:
        side = _first_text(site.get("side"), default="")
        if side not in {"left", "right"}:
            continue
        # Pair on the METHOD tail (not the full path) so the two module-instance wrappers of
        # a synchronized call match instead of each producing a "no matching call" row.
        key = _call_method_tail(_first_text(site.get("procedure"), default="")) or "call_site"
        bucket = pending.setdefault(key, {"left": [], "right": []})
        other_side = "right" if side == "left" else "left"
        if bucket[other_side]:
            other = bucket[other_side].pop(0)
            left = site if side == "left" else other
            right = other if side == "left" else site
            rows.append(_alignment_row(
                kind="call_site",
                left=left,
                right=right,
                region={"kind": "call_site"},
                synchronized=synchronized,
            ))
        else:
            bucket[side].append(site)
    for sides in pending.values():
        for side in ("left", "right"):
            for site in sides[side]:
                rows.append(_alignment_row(
                    kind="call_site",
                    left=site if side == "left" else {},
                    right=site if side == "right" else {},
                    region={"kind": "call_site"},
                    synchronized=synchronized,
                ))
    return [row for row in rows if row]


def _alignment_row_is_paired(row: dict[str, Any]) -> bool:
    left = _first_text(row.get("left"), default="")
    right = _first_text(row.get("right"), default="")
    return bool(
        left and right
        and not left.startswith("no matching")
        and not right.startswith("no matching")
    )


def _alignment_row_signature(row: dict[str, Any]) -> tuple[str, str]:
    return (
        _first_text(row.get("left"), default=""),
        _first_text(row.get("right"), default=""),
    )


def _is_setup_region(kind: str) -> bool:
    return kind in {"straight_line_prefix", "wrapper_or_init"}


def _call_method_tail(proc: str) -> str:
    """The bare METHOD name of a procedure call — the last dotted segment after the
    module-instance arguments are removed: `Poly(OpCCinit.OCC(I_stateless)).mac` and
    `D(A,IndBlock).O.Poly.mac` both reduce to `mac`.

    Two sides of a synchronized call differ only in the module INSTANCE that wraps the
    same method (the proof relates them with a `call <lemma>`). Keying the pairing on the
    full path left them UNPAIRED -> two "no matching left/right-side call" placeholder rows
    (live audit Tier-1: step1#call mis-said "no matching call" on a synchronized mac call)."""
    s = str(proc or "")
    for _ in range(8):
        s2 = re.sub(r"\([^()]*\)", "", s)
        if s2 == s:
            break
        s = s2
    return s.rstrip(".").split(".")[-1].strip()


def _alignment_pair_key(region: dict[str, Any]) -> str:
    kind = _first_text(region.get("kind"), default="frontier")
    if kind == "sample_frontier":
        return "|".join((
            kind,
            _first_text(region.get("distribution"), default=""),
            _first_text(region.get("sample_var"), default=""),
        ))
    if kind == "call_site":
        # Pair on the METHOD tail so two module-instance wrappers of the same call match.
        return "|".join((
            kind,
            _call_method_tail(
                _first_text(region.get("procedure_tail"), region.get("procedure"), default="")
            ),
        ))
    return kind


def _setup_alignment_row(
    left_regions: list[dict[str, Any]],
    right_regions: list[dict[str, Any]],
    *,
    synchronized: bool = False,
) -> dict[str, Any]:
    if not left_regions and not right_regions:
        return {}
    if synchronized and (left_regions or right_regions):
        role = "synchronized setup"
    else:
        role = (
            "setup / initialization"
            if left_regions and right_regions else
            "left-only setup"
            if left_regions else
            "right-only setup"
        )
    row = {
        "role": role,
        "left": _setup_side_text(
            left_regions,
            absent=_setup_absent_text("left", synchronized=synchronized),
        ),
        "right": _setup_side_text(
            right_regions,
            absent=_setup_absent_text("right", synchronized=synchronized),
        ),
        "proof_read": _setup_proof_read(
            left_regions,
            right_regions,
            synchronized=synchronized,
        ),
        "location": _drop_empty({
            "left_paths": _region_paths(left_regions),
            "right_paths": _region_paths(right_regions),
        }),
    }
    return _drop_empty(row)


def _residual_after_call_row(
    left_regions: list[dict[str, Any]],
    right_regions: list[dict[str, Any]],
    *,
    synchronized: bool = False,
) -> dict[str, Any]:
    if not left_regions and not right_regions:
        return {}
    role = (
        "residual after call"
        if left_regions and right_regions else
        "left residual after call"
        if left_regions else
        "right residual after call"
    )
    return _drop_empty({
        "role": role,
        "left": _setup_side_text(
            left_regions,
            absent=_residual_after_call_absent_text(
                "left",
                synchronized=synchronized,
            ),
        ),
        "right": _setup_side_text(
            right_regions,
            absent=_residual_after_call_absent_text(
                "right",
                synchronized=synchronized,
            ),
        ),
        "proof_read": _residual_after_call_proof_read(
            left_regions,
            right_regions,
            synchronized=synchronized,
        ),
        "location": _drop_empty({
            "left_paths": _region_paths(left_regions),
            "right_paths": _region_paths(right_regions),
        }),
    })


def _residual_after_call_absent_text(side: str, *, synchronized: bool) -> str:
    label = "left" if side == "left" else "right"
    if synchronized:
        return (
            f"EasyCrypt marks the programs as synchronized; the {label}-side "
            "post-call residual is represented by the shared program column."
        )
    return f"no {label}-side residual statement after this call frontier"


def _residual_after_call_proof_read(
    left_regions: list[dict[str, Any]],
    right_regions: list[dict[str, Any]],
    *,
    synchronized: bool = False,
) -> str:
    if synchronized and (left_regions or right_regions):
        return (
            "EasyCrypt prints this as shared residual program structure after "
            "the call frontier; it is not an unmatched opposite-side statement."
        )
    if left_regions and right_regions:
        return (
            "These statements remain after the live call frontier. Their "
            "effects are checked after the call returns; a bare call "
            "obligation is checked before these residual statements execute."
        )
    if left_regions:
        return (
            "The left side has residual statements after the live call "
            "frontier; their effects are not part of the callee obligation."
        )
    return (
        "The right side has residual statements after the live call frontier; "
        "their effects are not part of the callee obligation."
    )


def _setup_absent_text(side: str, *, synchronized: bool) -> str:
    if synchronized:
        label = "left" if side == "left" else "right"
        return (
            f"EasyCrypt marks the programs as synchronized; the {label}-side "
            "setup is represented by the single residual program column."
        )
    label = "left" if side == "left" else "right"
    return f"no {label}-side setup before this frontier"


# Panel-defect #1 (docs/reports/insights/l4_panel_defects_equiv_step4.md): a frontier
# statement that is actually a procedure call (`x <@ M.p(..)`, or a bare `M.p(..)` /
# `Iter(O).iter(..)` call) was being summarized as plain setup. Detect calls so the
# producer can flag the prefix as procedure-call structure. Re-implemented locally
# in core/ to stay consistent with workflow/surface_profiles._statement_is_proc_call
# WITHOUT importing workflow/ into core/ (layering).
_PROC_CALL_RE = re.compile(r"[A-Za-z_]\w*(?:\([^()]*\))?\.[A-Za-z_]\w*\s*\(")


def _statement_is_proc_call(text: Any) -> bool:
    """True iff a frontier statement is a procedure call.

    - `x <@ M.p(..)` — explicit call operator -> call.
    - `x <- e` — deterministic assignment -> NOT a call, even if its RHS mentions
      a dotted operator; a proc result would use `<@`, never `<-`.
    - bare `M.p(..)` / `Iter(O).iter(..)` (no `<-`/`<@`) -> call.
    Operator applications like `C.ofintd 0` (no `.proc(` parens) are NOT calls.
    """
    if not isinstance(text, str) or not text.strip():
        return False
    if "<@" in text:
        return True
    if "<-" in text:
        return False
    return bool(_PROC_CALL_RE.search(text))


def _setup_side_text(regions: list[dict[str, Any]], *, absent: str) -> str:
    if not regions:
        return absent
    statements = [
        _statement_text(region)
        for region in regions
        if _statement_text(region)
    ]
    if not statements:
        return f"{len(regions)} setup statement(s)"
    # Panel-defect #1: if any "setup" statement is actually a procedure call,
    # append a factual annotation. The literal `"N setup statement(s):"` prefix is
    # preserved verbatim so the _leading_statement parser and the surface_profiles
    # setup parser contract are not broken.
    call_stmts = [s for s in statements if _statement_is_proc_call(s)]
    call_annotation = (
        f" [procedure-call prefix: {'; '.join(call_stmts[:2])}]"
        if call_stmts else ""
    )
    if len(statements) == 1 and not call_annotation:
        return statements[0]
    if len(statements) == 1:
        # Single statement that is a call: keep the bare statement (no count
        # prefix to parse) but tag its structural kind.
        return f"{statements[0]}{call_annotation}"
    preview = "; ".join(statements[:3])
    if len(statements) > 3:
        preview += f"; ... ({len(statements) - 3} more)"
    return f"{len(statements)} setup statement(s): {preview}{call_annotation}"


def _setup_proof_read(
    left_regions: list[dict[str, Any]],
    right_regions: list[dict[str, Any]],
    *,
    synchronized: bool = False,
) -> str:
    if synchronized and (left_regions or right_regions):
        return (
            "EasyCrypt marks the programs as synchronized here; this setup is "
            "shared residual program structure printed in one column, not an "
            "unmatched opposite-side obligation."
        )
    if left_regions and right_regions:
        return (
            "These are setup statements before the current frontier; preserve "
            "the proof-relevant initialized state in later invariants, seq "
            "cuts, or calls."
        )
    if left_regions:
        return (
            "The left side has setup before the shared frontier; relate it to "
            "the precondition or carry the initialized state in the next "
            "invariant/cut."
        )
    return (
        "The right side has setup before the shared frontier; relate it to the "
        "precondition or carry the initialized state in the next invariant/cut."
    )


def _alignment_row(
    *,
    kind: str,
    left: dict[str, Any],
    right: dict[str, Any],
    region: dict[str, Any],
    synchronized: bool = False,
) -> dict[str, Any]:
    left_text = _statement_text(left)
    right_text = _statement_text(right)
    row = {
        "role": _alignment_role(
            kind,
            left=left,
            right=right,
            region=region,
            synchronized=synchronized,
        ),
        "left": left_text or _missing_side_text(
            "left",
            kind,
            synchronized=synchronized,
        ),
        "right": right_text or _missing_side_text(
            "right",
            kind,
            synchronized=synchronized,
        ),
        "proof_read": _alignment_proof_read(
            kind,
            left=left,
            right=right,
            region=region,
            synchronized=synchronized,
        ),
        "location": _drop_empty({
            "left_path": _first_text(left.get("statement_path"), left.get("path"), default=""),
            "right_path": _first_text(right.get("statement_path"), right.get("path"), default=""),
        }),
    }
    observations = _alignment_observations(kind, left=left, right=right, region=region)
    if observations:
        row["observations"] = observations
    return _drop_empty(row)


def _statement_text(region: dict[str, Any]) -> str:
    text = _first_text(region.get("statement"), region.get("text"), default="")
    if text:
        return _preview(text, limit=220)
    kind = _first_text(region.get("kind"), default="")
    if kind == "sample_frontier":
        sample_var = _first_text(region.get("sample_var"), default="sample")
        distribution = _first_text(region.get("distribution"), default="")
        if distribution:
            return f"{sample_var} <$ {distribution}"
    if kind == "loop_frontier":
        condition = _first_text(region.get("condition"), default="")
        if condition:
            return f"while ({condition}) {{ ... }}"
    return ""


def _missing_side_text(
    side: str,
    kind: str,
    *,
    synchronized: bool = False,
) -> str:
    label = "left" if side == "left" else "right"
    if synchronized:
        if kind == "sample_frontier":
            subject = "sample"
        elif kind == "loop_frontier":
            subject = "loop"
        elif kind == "call_site":
            subject = "call"
        else:
            subject = "statement"
        return (
            f"EasyCrypt marks the programs as synchronized; the {label}-side "
            f"{subject} is represented by the single residual program column."
        )
    if kind == "sample_frontier":
        return f"no matching {label}-side sample at this frontier"
    if kind == "loop_frontier":
        return f"no matching {label}-side loop at this frontier"
    if kind == "call_site":
        return f"no matching {label}-side call at this frontier"
    return f"no matching {label}-side statement at this frontier"


def _alignment_role(
    kind: str,
    *,
    left: dict[str, Any],
    right: dict[str, Any],
    region: dict[str, Any],
    synchronized: bool = False,
) -> str:
    if synchronized and bool(left) != bool(right):
        if kind == "loop_frontier":
            return "synchronized loop frontier"
        if kind == "sample_frontier":
            return "synchronized sample frontier"
        if kind == "call_site" or "call" in kind:
            return "synchronized call frontier"
        return "synchronized frontier"
    if kind == "loop_frontier":
        return "loop frontier"
    if kind == "sample_frontier":
        return "sample inside frontier"
    if kind == "aligned_call_frontier":
        return "aligned call frontier"
    if kind == "call_site" or "call" in kind:
        return "call frontier"
    if kind == "wrapper_or_init":
        return "wrapper/init frontier"
    if left and not right:
        return "left-only frontier"
    if right and not left:
        return "right-only frontier"
    return kind.replace("_", " ") or "frontier"


def _alignment_proof_read(
    kind: str,
    *,
    left: dict[str, Any],
    right: dict[str, Any],
    region: dict[str, Any],
    synchronized: bool = False,
) -> str:
    if synchronized and bool(left) != bool(right):
        return (
            "EasyCrypt marks the programs as synchronized here; this row is "
            "shared residual program structure printed in one column. Use it "
            "to choose the next local proof step, not as evidence of a missing "
            "opposite-side statement."
        )
    if kind == "loop_frontier":
        left_cond = _first_text(left.get("condition"), default="")
        right_cond = _first_text(right.get("condition"), default="")
        if left_cond and right_cond and left_cond != right_cond:
            return (
                "The loop guards differ syntactically; the while invariant "
                "should explain why the guards correspond and what state is "
                "preserved across iterations."
            )
        return (
            "This is the loop frontier; choose a while invariant that carries "
            "the state needed by the postcondition."
        )
    if kind == "sample_frontier":
        left_dist = _first_text(left.get("distribution"), default="")
        right_dist = _first_text(right.get("distribution"), default="")
        if left_dist and right_dist and left_dist == right_dist:
            return (
                "Both sides sample from the same distribution; once the state "
                "relation is right, the sampling step can usually be handled "
                "by a direct coupling or residual automation."
            )
        return (
            "This is a sampling frontier; choose a coupling or distribution "
            "argument that connects the sampled values."
        )
    if kind == "call_site" or "call" in kind:
        left_proc = _first_text(left.get("procedure_tail"), left.get("procedure"), default="")
        right_proc = _first_text(right.get("procedure_tail"), right.get("procedure"), default="")
        if left_proc and right_proc and left_proc == right_proc:
            return (
                "Both sides expose the same call procedure; a named equiv call "
                "or an invariant call may apply at this frontier."
            )
        return (
            "This is a call frontier; compare the procedures/oracle wrappers "
            "before choosing a named call or invariant call."
        )
    if left and not right:
        return (
            "Only the left side has this frontier statement; account for it "
            "with the precondition, a one-sided transform, or the next invariant."
        )
    if right and not left:
        return (
            "Only the right side has this frontier statement; account for it "
            "with the precondition, a one-sided transform, or the next invariant."
        )
    return (
        "Read this as a proof-shape alignment row, not as a tactic; choose the "
        "next tactic from the semantic difference it exposes."
    )


def _alignment_observations(
    kind: str,
    *,
    left: dict[str, Any],
    right: dict[str, Any],
    region: dict[str, Any],
) -> list[str]:
    observations: list[str] = []
    if kind == "loop_frontier":
        left_cond = _first_text(left.get("condition"), default="")
        right_cond = _first_text(right.get("condition"), default="")
        if left_cond and right_cond and left_cond != right_cond:
            observations.append(
                f"loop guards differ: left `{left_cond}`, right `{right_cond}`"
            )
    if kind == "sample_frontier":
        left_dist = _first_text(left.get("distribution"), default="")
        right_dist = _first_text(right.get("distribution"), default="")
        if left_dist and right_dist:
            if left_dist == right_dist:
                observations.append(f"same sampling distribution: `{left_dist}`")
            else:
                observations.append(
                    f"sampling distributions differ: left `{left_dist}`, right `{right_dist}`"
                )
    if kind == "call_site" or "call" in kind:
        left_proc = _first_text(left.get("procedure_tail"), left.get("procedure"), default="")
        right_proc = _first_text(right.get("procedure_tail"), right.get("procedure"), default="")
        if left_proc and right_proc:
            if left_proc == right_proc:
                observations.append(f"same procedure name: `{left_proc}`")
            else:
                observations.append(
                    f"call procedures differ: left `{left_proc}`, right `{right_proc}`"
                )
    shared = _string_list(region.get("shared_written_vars"))
    if shared:
        observations.append("shared written vars: " + ", ".join(shared[:6]))
    return observations[:3]


def _region_paths(regions: list[dict[str, Any]]) -> list[str]:
    # These paths are semantic coordinates, not display text.  Do not truncate
    # them here: the SurfaceModel composer derives setup ranges and current
    # frontier floors from this list, so dropping the 9th path can make the
    # panel say "positions 1-8" while the setup summary says 9 statements.
    return [
        _first_text(region.get("statement_path"), region.get("path"), default="")
        for region in regions
        if _first_text(region.get("statement_path"), region.get("path"), default="")
    ]


def _prioritize_alignment_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def key(row: dict[str, Any]) -> tuple[int, int]:
        role = _first_text(row.get("role"), default="")
        priority = (
            0 if "setup" in role else
            2 if "residual after call" in role else
            1 if "call" in role else
            3 if "loop" in role else
            4 if "sample" in role else
            5
        )
        return (priority, rows.index(row))

    return sorted(rows, key=key)




def _first_instruction_alignment(
    rows: list[dict[str, Any]],
    *,
    single_sided: bool = False,
    symmetric: bool = False,
) -> dict[str, Any]:
    for row in rows:
        left = _first_text(row.get("left"), default="")
        right = _first_text(row.get("right"), default="")
        if not left and not right:
            continue
        # The frontier head is the SYNTACTIC first statement of each side — even when
        # the first row is a "setup" summary. Skipping setup and reporting the first
        # row whose statement is a call made `left_head` read "call" (and
        # "both_sides_at_call") on while/assignment frontiers where the call was
        # buried in a loop body, steering the agent toward a call tactic that could
        # never fire (panel audit 2026-06-05). Read the real head from position 0.
        left_first = _leading_statement(left)
        right_first = _leading_statement(right)
        left_head = _statement_head(left_first)
        right_head = _statement_head(right_first)
        if not left_head and not right_head:
            continue
        return _drop_empty({
            "left_first": left_first,
            "right_first": right_first,
            "left_head": left_head,
            "right_head": right_head,
            "branch_alignment": _branch_alignment_read(
                left_head, right_head, single_sided=single_sided, symmetric=symmetric
            ),
            "proof_read": _first_instruction_proof_read(
                left_head, right_head, single_sided=single_sided, symmetric=symmetric
            ),
        })
    return {}




def _branch_alignment_read(
    left_head: str,
    right_head: str,
    *,
    single_sided: bool = False,
    symmetric: bool = False,
) -> str:
    if single_sided:
        return "single_program_frontier"
    if not left_head or not right_head:
        return "synchronized_frontier" if symmetric else "one-sided_frontier"
    if left_head == right_head == "if":
        return "both_sides_at_if"
    if left_head == right_head == "while":
        return "both_sides_at_while"
    if left_head == right_head == "call":
        return "both_sides_at_call"
    if left_head == right_head:
        return f"both_sides_at_{left_head}"
    if "if" in {left_head, right_head}:
        return "if_not_aligned"
    return "frontier_heads_differ"


def _first_instruction_proof_read(
    left_head: str,
    right_head: str,
    *,
    single_sided: bool = False,
    symmetric: bool = False,
) -> str:
    if single_sided:
        return (
            "Single-program (phoare/hoare) frontier; there is no second side to align."
        )
    if left_head == right_head == "if":
        return (
            "Both sides are at branch frontiers; `if` is a plausible next "
            "shape tactic once the branch guards are related."
        )
    if "if" in {left_head, right_head} and left_head != right_head:
        return (
            "Only one side is at a branch frontier; consume or align the "
            "other side with `sp`, `wp`, or a seq cut before using `if`."
        )
    if left_head == right_head == "call":
        return (
            "Both sides are at call frontiers; inspect call options or use a "
            "call tactic form before guessing an invariant."
        )
    if left_head == right_head == "while":
        return (
            "Both sides are at loop frontiers; choose a loop invariant and "
            "check the current proof mode before selecting the while form."
        )
    if not left_head or not right_head:
        if symmetric:
            return (
                "The two programs are identical (synchronized) — apply the symmetric "
                "tactic directly (`sim`, `while (={...})`, two-sided `call`); no one-sided "
                "alignment step is needed."
            )
        return (
            "The visible frontier is one-sided; use a one-sided tactic, "
            "alignment step, or seq cut before applying a symmetric tactic."
        )
    return (
        "The first visible statements have different heads; align or consume "
        "setup statements before using a symmetric branch/loop/call tactic."
    )


def _alignment_summary(rows: list[dict[str, Any]], *, plan: WorkspaceViewPlan) -> str:
    if not rows:
        return ""
    roles = [_first_text(row.get("role"), default="") for row in rows]
    has_setup = any("setup" in role for role in roles)
    has_loop = any("loop" in role for role in roles)
    has_sample = any("sample" in role for role in roles)
    has_call = any("call" in role for role in roles)
    has_post_call_residual = any("residual after call" in role for role in roles)
    parts: list[str] = []
    if has_setup:
        parts.append("setup statements appear before the current frontier")
    if has_loop:
        parts.append("loop guards are part of the current proof shape")
    if has_sample:
        parts.append("sampling steps are visible inside the frontier")
    if has_call:
        parts.append("call sites are visible at the frontier")
    if has_post_call_residual:
        parts.append("residual statements remain after a call frontier")
    if not parts:
        parts.append("the current frontier is shown as left/right proof-shape rows")
    return (
        "Frontier alignment: "
        + "; ".join(parts)
        + ". Use this as a proof-reader map before choosing while/rnd/seq/call tactics."
    )


def _looks_like_call_site(site: dict[str, Any]) -> bool:
    if not site:
        return False
    kind = _first_text(site.get("kind"), default="").lower()
    if kind == "call_site" or "call" in kind:
        return True
    if bool(site.get("is_call_site") or site.get("is_frontier_call")):
        return True
    return bool(site.get("procedure") or site.get("procedure_tail"))


def _compact_call_site(site: dict[str, Any]) -> dict[str, Any]:
    procedure = _first_text(site.get("procedure_tail"), site.get("procedure"), default="")
    statement = _preview(
        _first_text(site.get("statement") or site.get("text"), default=""),
        limit=220,
    )
    item: dict[str, Any] = _drop_empty({
        "side": _first_text(site.get("side"), default=""),
        "side_index": site.get("side_index"),
        "statement_order": site.get("statement_order") or site.get("order"),
        "statement_path": _first_text(site.get("statement_path"), default=""),
        "procedure": procedure,
        "statement": statement,
    })
    if (
        "is_frontier_call" in site
        or "is_frontier_statement" in site
        or "frontier" in site
    ):
        item["frontier"] = bool(
            site.get("is_frontier_call")
            or site.get("is_frontier_statement")
            or site.get("frontier")
        )
    return _drop_empty(item)


def _next_panel(
    actions_value: Any,
    safe_next_value: Any,
    *,
    state: dict[str, Any],
    debug_refs: dict[str, Any],
    max_alternatives: int,
) -> dict[str, Any]:
    raw_actions = _as_dict_list(actions_value)
    foreground_raw = [
        action for action in raw_actions
        if not _is_background_hint_action(action)
    ]
    background = [
        _compact_action(action, background_hint=True)
        for action in raw_actions
        if _is_background_hint_action(action)
    ][:max_alternatives]
    runnable = [
        _compact_action(action)
        for action in foreground_raw
        if _readiness(action) != "blocked"
    ]
    blocked = [
        _compact_action(action)
        for action in foreground_raw
        if _readiness(action) == "blocked"
    ][:3]

    if not runnable:
        runnable = [
            _compact_safe_action(action)
            for action in _as_dict_list(safe_next_value)
        ]
        runnable = [action for action in runnable if action]

    if state.get("status") == "candidate_closed_pending_qed":
        return {
            "primary": _qed_action(debug_refs),
            "alternatives": runnable[:max_alternatives],
            "background_hints": background,
            "blocked": blocked,
        }

    primary = runnable[0] if runnable else _empty_primary_action()
    return {
        "primary": primary,
        "alternatives": runnable[1:1 + max_alternatives],
        "background_hints": background,
        "blocked": blocked,
    }


def _is_background_hint_action(action: dict[str, Any]) -> bool:
    metadata = _dict(action.get("metadata"))
    source = _first_text(action.get("source"), default="")
    epistemic = _first_text(action.get("epistemic_status"), default="")
    if bool(metadata.get("unverified_pivot_hint")):
        return True
    if _first_text(metadata.get("source_kind"), default="") == "unverified_pivot_hint":
        return True
    if _first_text(metadata.get("scheduler_role"), default="") == "unverified_pivot_background":
        return True
    if epistemic == "unverified_pivot_not_frontier_verified":
        return True
    return source == "AUTO-PIVOT" and epistemic not in {
        "daemon_probe_accepted",
        "daemon_chain_accepted",
        "easycrypt_verified",
        "verified_by_easycrypt",
    }


def _compact_action(
    action: dict[str, Any],
    *,
    background_hint: bool = False,
) -> dict[str, Any]:
    category = _first_text(action.get("category"), default="strategy")
    action_text = _first_text(action.get("tactic"), action.get("command"), default="")
    surface_category = "hint" if background_hint else category
    readiness = "context_only" if background_hint else _readiness(action)
    compact: dict[str, Any] = {
        "category": surface_category,
        "readiness": readiness,
    }
    proof_state_effect = _proof_state_effect(surface_category, readiness)
    if proof_state_effect:
        compact["proof_state_effect"] = proof_state_effect
    if category in {"commit", "probe"}:
        compact["tactic"] = _first_text(
            action.get("tactic"),
            _tactic_from_command(action_text),
            default="",
        )
    elif category in {"inspect", "diagnose", "verify"}:
        compact.update(_inspect_action_surface(action, default_category=category))
    elif category in {"strategy", "avoid"}:
        if action.get("tactic") or _looks_tactic_shape(action_text):
            compact["tactic_shape"] = action_text
        elif action_text:
            compact["guidance"] = action_text
    elif action_text:
        compact["guidance"] = action_text
    if background_hint and not (
        compact.get("handle") or compact.get("target") or compact.get("guidance")
    ):
        compact.update(_inspect_action_surface(action, default_category=category))
    compact.update(_drop_empty({
        "why": _preview(_first_text(action.get("why"), default=""), limit=240),
        "source": _first_text(action.get("source"), default=""),
        "confidence": _agent_confidence(action, background_hint=background_hint),
    }))
    name_status = _first_text(
        _dict(action.get("cost_factors")).get("name_resolution_status"),
        _dict(action.get("metadata")).get("proof_ir_name_resolution_status"),
        default="",
    )
    if name_status:
        compact["name_resolution_status"] = name_status
    if bool(action.get("requires_instantiation")):
        compact["needs_instantiation"] = True
    return _drop_empty(compact)


def _compact_safe_action(action: dict[str, Any]) -> dict[str, Any]:
    kind = _first_text(action.get("kind"), default="")
    category = {
        "commit_recommendation": "commit",
        "probe_recommendation": "probe",
        "consider_strategy_hint": "strategy",
    }.get(kind, kind or "inspect")
    tool = _first_text(action.get("recommended_tool"), action.get("tool"), default="")
    if not tool:
        if category == "commit":
            tool = "next"
        elif category == "probe":
            tool = "try"
        elif category in {"inspect", "diagnose", "verify"}:
            tool = category
    action_text = _first_text(action.get("action"), action.get("tactic"), default="")
    readiness = (
        "needs_instantiation"
        if bool(action.get("requires_instantiation"))
        else "ready_to_run"
        if category in {"commit", "verify"}
        else "probe_first"
        if category == "probe"
        else "inspect_first"
        if category in {"inspect", "diagnose"}
        else "reasoning_required"
        if category == "strategy"
        else "inspect_first"
    )
    compact: dict[str, Any] = {
        "category": category,
        "readiness": readiness,
        "why": _preview(_first_text(action.get("why"), default=""), limit=240),
        "confidence": _agent_confidence(action),
    }
    proof_state_effect = _proof_state_effect(category, readiness)
    if proof_state_effect:
        compact["proof_state_effect"] = proof_state_effect
    if bool(action.get("requires_instantiation")):
        compact["needs_instantiation"] = True
    if category in {"commit", "probe"} and action_text:
        compact["tactic"] = action_text
    elif category in {"inspect", "diagnose", "verify"}:
        compact["handle"] = _handle_from_tool(tool or category)
    elif category == "strategy" and action_text:
        compact["guidance"] = action_text
    return _drop_empty(compact)


def _empty_primary_action() -> dict[str, Any]:
    return {
        "category": "none",
        "readiness": "no_action",
        "proof_state_effect": "no_proof_state_effect",
        "why": "No current safe action is available in the aggregate view.",
    }


def _qed_action(debug_refs: dict[str, Any]) -> dict[str, Any]:
    return {
        "category": "commit",
        "readiness": "ready_to_run",
        "proof_state_effect": "will_change_proof_state",
        "tactic": "qed.",
        "why": (
            "EasyCrypt reports no remaining goals after the latest tactic; "
            "commit `qed.` to save the lemma before final verification."
        ),
        "source": "EasyCrypt",
        "confidence": "closed_candidate",
    }


def _source_contract(
    proof_goal: dict[str, Any],
    current_goal: dict[str, Any],
) -> dict[str, Any]:
    fact_source = _first_text(
        proof_goal.get("fact_source"),
        current_goal.get("fact_source"),
        default="pretty_goal_text",
    )
    authority = _first_text(
        proof_goal.get("authority"),
        current_goal.get("authority"),
        default="pretty_text_fallback",
    )
    ground_truth = bool(
        proof_goal.get("ec_ground_truth")
        or current_goal.get("ec_ground_truth")
        or authority == "ec_native_ground_truth"
    )
    if ground_truth or fact_source.startswith("ec_native"):
        source_kind = "easycrypt_native"
        label = "EasyCrypt-native goal state"
    elif fact_source == "pretty_goal_text":
        source_kind = "easycrypt_stdout_fallback"
        label = "Parsed from EasyCrypt pretty goal text"
    elif fact_source:
        source_kind = fact_source
        label = f"Projected from {fact_source}"
    else:
        source_kind = "unknown"
        label = "Unknown goal-state source"
    return _drop_empty({
        "kind": source_kind,
        "label": label,
        "ground_truth": ground_truth,
        "fact_source": fact_source,
        "authority": authority,
        "authority_rank": proof_goal.get("authority_rank"),
        "native_artifact": _first_text(
            proof_goal.get("native_artifact"),
            current_goal.get("native_artifact"),
            default="",
        ),
    })


def _display_status(
    *,
    projection_status: str,
    proof_state: dict[str, Any],
    current_goal: dict[str, Any],
) -> str:
    transition = _dict(proof_state.get("latest_transition"))
    event_contract = _dict(proof_state.get("event_contract"))
    proof_goal = _dict(proof_state.get("goal"))
    goal_closed_visible = _goal_visibly_closed(current_goal, proof_goal)
    latest_closed = _transition_can_mark_closed(transition) and goal_closed_visible
    event_closed_visible = (
        bool(event_contract.get("candidate_closed"))
        and goal_closed_visible
    )
    if (
        projection_status in {"unknown", "open"}
        and (latest_closed or event_closed_visible)
        and not bool(proof_state.get("final_ready"))
    ):
        return "candidate_closed_pending_qed"
    return projection_status


def _compact_resources(
    resources: dict[str, Any],
    *,
    keys: tuple[str, ...],
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in keys:
        value = resources.get(key)
        if value in (None, "", [], {}):
            continue
        out[key] = value
    return out


def _compact_messages(value: Any, *, limit: int) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for item in _as_dict_list(value)[:limit]:
        code = _first_text(item.get("code"), default="message")
        message = _preview(_first_text(item.get("message"), default=""), limit=260)
        if code == "proof_ir.name_resolution_lookup_required":
            message = (
                "Some imported or cross-scope handles may need lookup if that "
                "route is being tested; use lookup_candidates for the concrete "
                "symbol instead of treating the whole list as a to-do queue."
            )
        if not message:
            continue
        out.append(_drop_empty({
            "code": code,
            "message": message,
            "severity": _first_text(item.get("severity"), default=""),
        }))
    return out


def _readiness(action: dict[str, Any]) -> str:
    category = _first_text(action.get("category"), default="")
    if bool(action.get("requires_instantiation")):
        return "needs_instantiation"
    if category == "strategy":
        return "reasoning_required"
    if category == "avoid":
        return "blocked"
    if category == "commit":
        confidence = _first_text(action.get("confidence"), default="")
        epistemic = _first_text(action.get("epistemic_status"), default="")
        if confidence == "verified" or epistemic in {
            "daemon_probe_accepted",
            "daemon_chain_accepted",
            "easycrypt_verified",
            "verified_by_easycrypt",
        }:
            return "ready_to_run"
        return "probe_first"
    if category == "probe":
        return "probe_first"
    if category in {"inspect", "diagnose"}:
        return "inspect_first"
    if category == "verify":
        return "ready_to_run"
    if category == "none":
        return "no_action"
    return "inspect_first"


def _proof_state_effect(category: str, readiness: str) -> str:
    if readiness in {"blocked", "no_action"}:
        return "no_proof_state_effect"
    if category == "commit":
        return "will_change_proof_state"
    if category == "probe":
        return "does_not_change_proof_state_probe_only"
    if category == "verify":
        return "does_not_change_proof_state_verification_check"
    if category in {"inspect", "diagnose", "verify"}:
        return "does_not_change_proof_state_read_only"
    if category in {"strategy", "hint"}:
        return ""
    if category == "avoid":
        return "no_proof_state_effect_guardrail"
    return "does_not_change_proof_state_read_only"


def _agent_confidence(
    action: dict[str, Any],
    *,
    background_hint: bool = False,
) -> str:
    confidence = _first_text(action.get("confidence"), default="")
    epistemic = _first_text(action.get("epistemic_status"), default="")
    metadata = _dict(action.get("metadata"))
    if background_hint or epistemic == "unverified_pivot_not_frontier_verified":
        return ""
    if confidence == "verified" or epistemic in {
        "daemon_probe_accepted",
        "daemon_chain_accepted",
    }:
        return "verified_by_probe"
    if epistemic in {"easycrypt_verified", "verified_by_easycrypt"}:
        return "verified_by_easycrypt"
    if bool(action.get("requires_instantiation")) or epistemic == (
        "template_requires_instantiation"
    ):
        return "needs_instantiation"
    if epistemic.startswith("diagnostic_"):
        return "diagnostic"
    if confidence:
        return confidence
    if epistemic:
        return "static"
    return ""


def _inspect_action_surface(
    action: dict[str, Any],
    *,
    default_category: str,
) -> dict[str, Any]:
    command = _first_text(
        action.get("command"),
        action.get("action"),
        action.get("tactic"),
        default="",
    )
    tool = _first_text(action.get("tool"), default="")
    if not tool:
        tool = _tool_from_command(command) or default_category
    out = {
        "handle": _handle_from_tool(tool),
        "target": _target_from_command(command),
    }
    return _drop_empty(out)


def _handle_from_tool(tool: str) -> str:
    normalized = str(tool or "").strip().lstrip("-").replace("-", "_")
    return {
        "goal_info": "goal_info",
        "diagnose": "diagnose",
        "episode_view": "episode_view",
        "where": "where",
        "members": "members",
        "sig": "signature",
        "search": "rewrite_candidates",
        "search_skeleton": "rewrite_candidates",
        "native_ast_search": "rewrite_candidates",
        "check_lemma": "check_lemma",
        "tactic_forms": "tactic_forms",
        "align": "align",
        "call_subgoals": "call_subgoals",
        "pivot_inspect": "pivot_context",
        "pivot_context": "pivot_context",
        "verified_pivot_options": "verified_pivot_options",
        "call_site_options": "call_site_options",
        "pr_bridge_routes": "pr_bridge_routes",
        "bridge_options": "pr_bridge_routes",  # back-compat alias
        "rewrite_candidates": "rewrite_candidates",
        "suggest_close": "suggest_close",
        "verify": "verify",
    }.get(normalized, normalized or "inspect")


def _tool_from_command(command: str) -> str:
    parts = _shell_parts(command)
    for part in parts:
        if part.startswith("-"):
            flag = part.lstrip("-")
            if flag in {
                "goal-info",
                "diagnose",
                "episode-view",
                "where",
                "members",
                "sig",
                "check-lemma",
                "tactic-forms",
                "align",
                "call-subgoals",
                "pivot-inspect",
                "suggest-close",
                "verify",
            }:
                return flag
    return ""


def _target_from_command(command: str) -> str:
    parts = _shell_parts(command)
    target_flags = {
        "-where",
        "-members",
        "-sig",
        "-check-lemma",
        "-tactic-forms",
        "-inv-from-lemma",
    }
    for idx, part in enumerate(parts):
        if part in target_flags and idx + 1 < len(parts):
            return parts[idx + 1]
    return ""


def _tactic_from_command(text: str) -> str:
    candidate = str(text or "").strip()
    if _looks_tactic_shape(candidate):
        return candidate
    parts = _shell_parts(candidate)
    for idx, part in enumerate(parts):
        if part == "-c" and idx + 1 < len(parts):
            return parts[idx + 1]
    return ""


def _shell_parts(command: str) -> list[str]:
    text = str(command or "").strip()
    if not text:
        return []
    try:
        return shlex.split(text)
    except ValueError:
        return text.split()


def _looks_tactic_shape(text: str) -> bool:
    stripped = str(text or "").strip()
    if not stripped:
        return False
    head = re.split(r"[\s{.]", stripped, maxsplit=1)[0]
    return head in {
        "auto",
        "byequiv",
        "call",
        "case",
        "congr",
        "conseq",
        "ecall",
        "exlim",
        "if",
        "inline",
        "move",
        "proc",
        "rcondf",
        "rcondt",
        "rewrite",
        "rnd",
        "seq",
        "sim",
        "skip",
        "smt",
        "sp",
        "swap",
        "transitivity",
        "while",
        "wp",
    }




def _preview_list(value: Any, *, limit: int, chars: int) -> list[str]:
    out: list[str] = []
    for item in _string_list(value):
        text = _preview(item, limit=chars)
        if text:
            out.append(text)
        if len(out) >= limit:
            break
    return out


def _limit_mapping(data: dict[str, Any], *, max_chars: int) -> dict[str, Any]:
    out: dict[str, Any] = {}
    remaining = max(0, max_chars)
    for key, value in data.items():
        if remaining <= 0:
            break
        limited_value, value_cost = _limit_structured_value(
            value,
            max_chars=max(80, remaining - len(key)),
        )
        cost = len(key) + value_cost
        if cost <= remaining and (
            value_cost <= 700 or isinstance(limited_value, (dict, list))
        ):
            out[key] = limited_value
            remaining -= cost
            continue
        limit = min(700, max(80, remaining - len(key)))
        out[key] = _preview(_value_preview_text(value), limit=limit)
        break
    return out


def _limit_structured_value(value: Any, *, max_chars: int) -> tuple[Any, int]:
    text = _value_preview_text(value)
    if len(text) <= max_chars and len(text) <= 700:
        return value, len(text)
    if isinstance(value, list):
        out: list[Any] = []
        used = 2
        for item in value:
            item_text = _value_preview_text(item)
            item_cost = len(item_text) + (2 if out else 0)
            if out and used + item_cost > max_chars:
                break
            if not out and item_cost > max_chars:
                break
            out.append(item)
            used += item_cost
        if out:
            return out, len(_value_preview_text(out))
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        used = 2
        for item_key, item_value in value.items():
            item_text = _value_preview_text(item_value)
            item_cost = len(str(item_key)) + len(item_text) + 4
            if out and used + item_cost > max_chars:
                break
            if not out and item_cost > max_chars:
                break
            out[str(item_key)] = item_value
            used += item_cost
        if out:
            return out, len(_value_preview_text(out))
    return _preview(text, limit=min(700, max(80, max_chars))), min(
        len(text),
        min(700, max(80, max_chars)),
    )


def _value_preview_text(value: Any) -> str:
    if isinstance(value, (dict, list)):
        try:
            return json.dumps(value, sort_keys=True, ensure_ascii=False)
        except Exception:
            return str(value)
    return str(value)






def _first_list_text(value: Any) -> str:
    for item in _string_list(value):
        return item
    return ""


def _goal_line_list(value: Any) -> list[str]:
    """Return EasyCrypt goal lines exactly as line records, including blanks."""
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


