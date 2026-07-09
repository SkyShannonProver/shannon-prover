"""Typed proof IR and phase analysis for EasyCrypt proof states.

This module is the compiler-style boundary above raw EC goal text.  It consumes
the existing goal parser output and session history, then exposes:

* the current abstraction layer
* the normalized goal kind
* live proof resources such as call sites and callable lemmas
* destructive moves already taken
* a small phase/cost menu and diagnostics

The analysis is intentionally structural.  It does not encode a particular
lemma's failure trace; it describes what resources are live in the current
proof state and what common tactic families would preserve or destroy.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

# Leaf utilities live in ec_proof_ir_util; build_proof_ir uses just these two
# (the per-pass modules import their own leaves directly).
from core.easycrypt.analysis.ec_proof_ir_util import (
    _lemma_leaf,
    _list,
)

from core.easycrypt.analysis.ec_proof_diagnostics import (
    proof_ir_failure_diagnostics,
)


PROOF_IR_SCHEMA_VERSION = 1
PROOF_IR_KIND = "easycrypt_proof_ir"


def build_proof_ir(
    *,
    session_dir: str | Path | None = None,
    proof_state: dict[str, Any] | None = None,
    current_goal: dict[str, Any] | None = None,
    external_recommendations: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a JSON-ready ProofIR summary for the current proof state."""
    st = project_state(
        session_dir=session_dir,
        proof_state=proof_state,
        current_goal=current_goal,
    )
    parsed = st["parsed"]
    goal_type = st["goal_type"]
    goal_text = st["goal_text"]
    destructive_moves = st["destructive_moves"]
    program_ir = st["program_ir"]
    pr_normal_form = st["pr_normal_form"]
    call_sites = st["call_sites"]
    latest_transition = st["latest_transition"]
    h = _build_proof_handles(
        parsed=parsed,
        goal_type=goal_type,
        goal_text=goal_text,
        program_ir=program_ir,
        pr_normal_form=pr_normal_form,
        session_dir=session_dir,
        latest_transition=latest_transition,
        external_recommendations=external_recommendations,
    )
    handles = h["handles"]
    external_candidates = h["external_candidates"]
    invariant_skeleton = h["invariant_skeleton"]
    name_resolution = h["name_resolution"]
    instantiation_bindings = h["instantiation_bindings"]
    pr_path_plan = h["pr_path_plan"]
    goal_kind = _goal_kind(goal_type, parsed)
    layer = _infer_layer(
        goal_type,
        parsed,
        call_sites=call_sites,
        destructive_moves=destructive_moves,
        goal_text=goal_text,
    )
    liveness = _pass3_liveness_and_route(
        handles,
        call_sites=call_sites,
        destructive_moves=destructive_moves,
        program_ir=program_ir,
        layer=layer,
    )
    legality = _phase_legality(layer, liveness, handles)
    external_candidates = _apply_candidate_pipeline(
        external_candidates,
        name_resolution=name_resolution,
        instantiation_bindings=instantiation_bindings,
        legality=legality,
        liveness=liveness,
        current_layer=layer,
        latest_transition=latest_transition,
    )
    handles["external_candidates"] = external_candidates
    recent_rewrite = _rewrite_leaf_from_tactic(
        str(latest_transition.get("tactic") or "")
    )
    if recent_rewrite:
        handles["recently_rewritten_pr_lemma"] = recent_rewrite
        handles["pr_rewrite_candidates"] = [
            lemma for lemma in _list(handles.get("pr_rewrite_candidates"))
            if _lemma_leaf(str(lemma)) != recent_rewrite
        ]
    # End of the PASS 2/3 mutation phase — every handles write happened above.
    # PASS 4 (phase / menu / diagnostics) only READS handles; enforce that.
    handles.freeze()
    surface = _build_action_surface(
        layer=layer,
        goal_kind=goal_kind,
        liveness=liveness,
        handles=handles,
        program_ir=program_ir,
        name_resolution=name_resolution,
        instantiation_bindings=instantiation_bindings,
        legality=legality,
        latest_transition=latest_transition,
        destructive_moves=destructive_moves,
    )
    phase = surface["phase"]
    menu = surface["menu"]
    diagnostics = surface["diagnostics"]
    latest_tactic = str(latest_transition.get("tactic") or "")
    latest_error = str(latest_transition.get("latest_error") or "")

    result = {
        "schema_version": PROOF_IR_SCHEMA_VERSION,
        "kind": PROOF_IR_KIND,
        "current_layer": layer,
        "goal_kind": goal_kind,
        "goal_type": goal_type,
        "resources": {
            "program_ir": program_ir,
            "pr_path_plan": pr_path_plan,
            "pr_normal_form": pr_normal_form,
            "call_sites": call_sites,
            "handles": handles,
            "invariant_skeleton": invariant_skeleton,
            "external_candidates": external_candidates,
            "name_resolution": name_resolution,
            "instantiation_bindings": instantiation_bindings,
        },
        "liveness": liveness,
        "destructive_moves": destructive_moves,
        "phase": phase,
        "candidate_menu": menu,
        "diagnostics": diagnostics,
    }
    failure_diags = proof_ir_failure_diagnostics(
        result,
        latest_tactic=latest_tactic,
        latest_error=latest_error,
    )
    if failure_diags:
        result["diagnostics"] = failure_diags + result["diagnostics"]
    # Scope the read-only guard to build_proof_ir: downstream consumers (e.g.
    # session_workspace_view_manager) still mutate the handles dict, so the
    # returned object must be writable — byte-identical to before.
    handles.thaw()
    return result


def proof_ir_notes(proof_ir: dict[str, Any], *, max_notes: int = 3) -> list[dict[str, str]]:
    """Return compact note dictionaries for ProofContextView."""
    if not isinstance(proof_ir, dict):
        return []
    notes: list[dict[str, str]] = []
    for diag in proof_ir.get("diagnostics") or []:
        if not isinstance(diag, dict):
            continue
        msg = str(diag.get("message") or "")
        code = str(diag.get("code") or "proof_ir.diagnostic")
        if not msg:
            continue
        notes.append({
            "code": code,
            "message": msg,
            "severity": str(diag.get("severity") or "info"),
        })
        if len(notes) >= max_notes:
            break
    return notes


__all__ = [
    "PROOF_IR_KIND",
    "PROOF_IR_SCHEMA_VERSION",
    "build_proof_ir",
    "proof_ir_notes",
]


# PASS 4 (action surface) lives in ec_proof_action_surface now; re-exported here
# so build_proof_ir + the consumers import every name from this module unchanged.
# (action_surface imports only the sibling modules + util, so there is no cycle.)
from core.easycrypt.analysis.ec_proof_action_surface import (  # noqa: E402
    _ambient_named_closer_menu_items,
    _build_action_surface,
    _bound_template_family,
    _call_instantiation_hint,
    _call_site_control_menu_items,
    _call_site_prefix_menu_items,
    _candidate_menu,
    _coverage_notes,
    _coverage_preserved_vars,
    _coverage_safe_var,
    _coverage_strings,
    _coverage_var_is_preserved,
    _diagnostics,
    _double_quoted_tool_arg,
    _equiv_exact_closer_menu_items,
    _external_call_named_equiv_menu_items,
    _external_pr_bridge_frontier_candidates,
    _external_pr_bridge_frontier_items,
    _frontier_exposure_candidate,
    _has_live_pr_typed_bridge_path,
    _has_runnable_pr_frontend_action,
    _has_unfilled_angle_placeholder,
    _instantiated_template_menu_items,
    _instantiation_preconditions,
    _invariant_live_fact_coverage,
    _invariant_looks_noisy,
    _looks_like_pr_bridge_name,
    _menu_item,
    _native_ast_search_menu_items,
    _path_lemmas,
    _phase_guidance,
    _phase_legality,
    _planned_frontier_exposure,
    _pr_endpoint_relevance_cost_factors,
    _pr_path_signature_lookup_items,
    _pr_rewrite_candidate_index,
    _pr_typed_bridge_chain_menu_items,
    _pr_wrapper_bridge_menu_items,
    _probabilistic_vc_menu_items,
    _procedure_body_menu_items,
    _procedure_entry_fallback_menu_items,
    _procedure_frontier_plan_menu_items,
    _procedure_surface_map_menu_items,
    _program_edit_script_menu_items,
    _safe_id,
    _sampling_ordering_diagnostics,
    _semantic_pr_bound_menu_items,
    _template_args,
    _template_cost_factors,
    _while_invariant_tactic_hint,
)

from core.easycrypt.analysis.ec_pr_actions import (  # noqa: E402
    pr_byequiv_fallback_menu_items as _pr_byequiv_fallback_menu_items,
    pr_clone_bound_apply_menu_items as _pr_clone_bound_apply_menu_items,
    pr_decomposition_bridge_menu_items as _pr_decomposition_bridge_menu_items,
    pr_normalization_menu_items as _pr_normalization_menu_items,
    pr_rewrite_menu_items as _pr_rewrite_menu_items,
    resolution_preconditions as _resolution_preconditions,
    visible_pr_rewrites as _visible_pr_rewrites,
)


# This pass lives in ec_proof_ir_state now; re-exported here so build_proof_ir + the
# consumers import every name from this module unchanged.
# (ec_proof_ir_state imports only the sibling modules + util, so there is no cycle.)
from core.easycrypt.analysis.ec_proof_ir_state import (  # noqa: E402
    _destructive_moves,
    _fallback_proc_from_call_text,
    _goal_kind,
    _goal_text,
    _goal_text_looks_like_program_residual,
    _has_program_statements,
    _infer_layer,
    _is_synchronized_prhl_residue,
    _iter_program_statements,
    _pr_normal_form,
    _read_history_tactics,
    _suggested_body_transform_available,
    project_state,
)


# This pass lives in ec_proof_ir_liveness now; re-exported here so build_proof_ir + the
# consumers import every name from this module unchanged.
# (ec_proof_ir_liveness imports only the sibling modules + util, so there is no cycle.)
from core.easycrypt.analysis.ec_proof_ir_liveness import (  # noqa: E402
    _call_route_exposure,
    _call_route_first_exposure_action,
    _call_route_frontier_blockers,
    _call_route_handle_needs_binding,
    _call_route_named_handles,
    _call_route_site,
    _call_route_templates,
    _call_route_wrapper_depth,
    _call_site_route_surface,
    _dedupe_dicts,
    _drop_empty,
    _handle_liveness,
    _pass3_liveness_and_route,
    _short_text,
    _PLACEHOLDER_HANDLE_SYMBOLS,
    _apply_candidate_pipeline,
    _rewrite_leaf_from_tactic,
)


# This pass lives in ec_proof_ir_handles now; re-exported here so build_proof_ir + the
# consumers import every name from this module unchanged.
# (ec_proof_ir_handles imports only the sibling modules + util, so there is no cycle.)
from core.easycrypt.analysis.ec_proof_ir_handles import (  # noqa: E402
    _adversary_invariant_atom_worth_keeping,
    _adversary_invariant_atoms,
    _adversary_invariant_atoms_from_handles,
    _adversary_invariant_skeleton,
    _ambient_conventional_closer_names,
    _ambient_frontend,
    _ambient_named_closers,
    _ambient_top_connective,
    _callable_lemma_handles,
    _clean_proc,
    _clone_wrapper_terms,
    _compact_semantic_lemma_index,
    _contains_top_level_implication,
    _context_names,
    _equiv_exact_closers,
    _equiv_proc_pair,
    _first_memory_name,
    _first_top_level,
    _first_top_level_implication,
    _forall_binder_region,
    _forall_intro_binders,
    _fresh_intro_tactic,
    _fresh_name,
    _goal_body,
    _has_top_level_implication,
    _intro_candidate,
    _local_equiv_hypothesis_handles,
    _mapping_names,
    _matching_bracket,
    _matching_delimiter,
    _oracle_handle_atom_worth_keeping,
    _oracle_handle_invariant_atoms,
    _oracle_obligation_sources,
    _parse_equiv_hypothesis_body,
    _pr_byequiv_frontend,
    _pr_clone_bound_apply_candidates,
    _probabilistic_vc_frontend,
    _proc_signature_key,
    _procedure_body_frontend,
    _procedure_template_matches,
    _proof_handles,
    _quantifier_intro_tactic,
    _session_context_files,
    _session_target_lemma,
    _source_call_equiv_handles,
    _source_declarations_by_name,
    _source_equiv_declarations,
    _source_pr_rewrite_handles,
    _split_relational_atoms,
    _strip_memory_marker,
    _strip_outer_parens,
    _Handles,
    _build_proof_handles,
)
