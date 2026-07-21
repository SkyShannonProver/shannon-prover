"""Procedure/control-flow frontend for EasyCrypt program goals.

This module owns structural classification for exposed procedure bodies:
branches, loops, samples, straight-line prefixes, wrapper/init calls, swap
opportunities, and frontier plans.  It emits typed facts consumed by ProofIR;
it does not render the final tactic menu.
"""
from __future__ import annotations

import re
from typing import Any

from core.easycrypt.analysis.ec_utils import (
    as_dict as _dict,
    as_list as _list,
    contains_top_level_implication,
    dedupe_stripped_strings as _dedupe_strings,
    first_top_level_implication,
    is_live_safe_var as _is_live_safe_var,
    legacy_shape_tactic_templates as _legacy_shape_tactic_templates,
    looks_like_program_residual as _looks_like_program_residual,
)
from core.easycrypt.analysis.ec_procedure_ref import (
    looks_like_qualified_procedure_application as _looks_like_qualified_procedure_application,
    parse_procedure_application as _parse_procedure_application,
    procedure_exact_key as _procedure_exact_key,
    procedure_leaf_token as _procedure_leaf_token,
    shallow_call_procedure_from_statement as _shallow_call_procedure_from_statement,
    split_procedure_module_and_name as _split_procedure_module_and_name,
)
from core.easycrypt.analysis.ec_sampling_obligations import (
    build_sampling_obligation_frontend,
    sample_var,
)
from core.easycrypt.analysis.ec_sampling_statements import (
    is_sample_statement as _is_sample_statement,
    sample_statement_distribution as _sample_statement_distribution,
    sample_statement_var as _sample_statement_var,
)


PROCEDURE_FRONTEND_SCHEMA_VERSION = 1
PROCEDURE_FRONTEND_KIND = "easycrypt_procedure_frontend"


def build_procedure_body_frontend(
    parsed: dict[str, Any],
    goal_type: str,
    program_ir: dict[str, Any],
    goal_text: str,
) -> dict[str, Any]:
    """Return typed procedure/control-flow facts for the current goal."""
    parsed = _dict(parsed)
    program_ir_statement_count = len(_list(_dict(program_ir).get("statements")))
    statement_source = "program_ir" if program_ir_statement_count else "none"
    statements = [
        _dict(stmt)
        for stmt in _list(_dict(program_ir).get("statements"))
        if isinstance(stmt, dict)
    ]
    if not statements:
        statements = procedure_statements_from_pretty_goal(goal_text, goal_type)
        if statements:
            statement_source = "pretty_goal_fallback"
    structure_gap = _looks_like_program_residual(goal_text, goal_type) and not statements
    suggested = [
        str(item).strip()
        for item in _legacy_shape_tactic_templates(parsed)
        if str(item).strip()
    ]
    statement_types = {
        str(stmt.get("kind") or stmt.get("type") or "")
        for stmt in statements
    }
    branch_guards = procedure_branch_guards(statements)
    loops = procedure_loop_statements(statements)
    samples = procedure_sample_statements(statements)
    sampling_frontend = build_sampling_obligation_frontend(
        samples,
        parsed=parsed,
        goal_text=goal_text,
    )
    swap_candidates = procedure_swap_candidates(program_ir, statements)
    init_wrappers = procedure_like_statement_calls(statements)
    straight_prefix = procedure_straight_line_prefix(statements)
    control_frontiers = procedure_control_frontiers(program_ir, statements)
    structured_regions = procedure_structured_regions(statements)
    frontier_plan = procedure_frontier_plan(
        structured_regions=structured_regions,
        straight_prefix=straight_prefix,
        swap_candidates=swap_candidates,
        init_wrappers=init_wrappers,
    )
    obligation_stack = procedure_obligation_stack(
        program_ir,
        statements,
        structured_regions=structured_regions,
        parsed=parsed,
        goal_text=goal_text,
    )
    control_suffix = procedure_control_suffix_legality(
        statements,
        structured_regions=structured_regions,
        branch_guards=branch_guards,
        loops=loops,
        samples=samples,
    )
    side_condition_packs = procedure_residual_side_condition_packs(parsed, goal_text)
    live_state = procedure_live_state_summary(parsed, statements, goal_text)
    asymmetric_region = procedure_asymmetric_instrumentation_region(
        statements,
        parsed=parsed,
        goal_text=goal_text,
    )
    if asymmetric_region.get("available"):
        asymmetric_region = dict(asymmetric_region)
        asymmetric_region["live_fact_budget"] = procedure_live_fact_budget(
            live_state,
            asymmetric_region,
        )
    result_expression_map = procedure_result_expression_map(
        parsed,
        statements,
        goal_text,
    )
    bad_event_map = procedure_bad_event_candidate_map(
        parsed,
        statements,
        goal_text,
    )
    one_sided_call_summary = procedure_one_sided_call_site_summary(
        statements,
        parsed=parsed,
        goal_text=goal_text,
        result_expression_map=result_expression_map,
    )
    one_sided_sampling_residual = procedure_one_sided_sampling_residual_map(
        samples,
        parsed=parsed,
        goal_text=goal_text,
        live_state=live_state,
    )
    sample_coupling_budget = procedure_sample_coupling_budget(
        sampling_frontend,
        asymmetric_region,
        live_state,
        branch_guards=branch_guards,
        parsed=parsed,
        goal_text=goal_text,
    )
    current_region_summary = procedure_current_region_summary(
        statements,
        parsed=parsed,
        goal_text=goal_text,
        live_state=live_state,
        asymmetric_region=asymmetric_region,
        sample_coupling_budget=sample_coupling_budget,
    )
    loop_partition_summary = procedure_loop_partition_summary(
        statements,
        parsed=parsed,
        goal_text=goal_text,
    )
    post = str(parsed.get("post") or "")
    residual_close = bool(
        any(item.startswith("auto") or item.startswith("smt") for item in suggested)
        or ("post = true" in goal_text and "pre = true" in goal_text)
        or not statements
    )
    conseq_shape = bool(
        "&&" in post
        or "forall" in post
        or contains_top_level_implication(post)
    )
    return {
        "available": bool(statements or suggested or goal_text),
        "program_structure_status": {
            "statement_source": statement_source,
            "program_ir_statement_count": program_ir_statement_count,
            "recovered_statement_count": len(statements),
            "structure_unavailable": structure_gap,
            "inspection_actions": (
                ["-program-json", "-goal-info", "-agent-view"]
                if structure_gap else []
            ),
            "why": (
                "The goal text looks like an exposed program residual, but "
                "neither ProgramIR nor the pretty-goal fallback recovered a "
                "stable statement table."
                if structure_gap else
                "Program structure recovered from the current proof state."
            ),
        },
        "goal_type": goal_type,
        "statement_types": sorted(t for t in statement_types if t),
        "control_frontiers": control_frontiers,
        "structured_regions": structured_regions,
        "frontier_plan": frontier_plan,
        "proof_obligation_stack": obligation_stack,
        "control_suffix_legality": control_suffix,
        "live_state_summary": live_state,
        "current_region_summary": current_region_summary,
        "loop_partition_summary": loop_partition_summary,
        "asymmetric_instrumentation_region": asymmetric_region,
        "result_expression_map": result_expression_map,
        "bad_event_candidate_map": bad_event_map,
        "one_sided_call_site_summary": one_sided_call_summary,
        "one_sided_sampling_residual_map": one_sided_sampling_residual,
        "sample_coupling_budget": sample_coupling_budget,
        "branch_guards": branch_guards,
        "loop_frontiers": loops,
        "sample_frontiers": samples,
        "sampling_obligations": _list(sampling_frontend.get("obligations")),
        "sampling_candidate_families": _list(
            sampling_frontend.get("candidate_families")
        ),
        "residual_side_condition_packs": side_condition_packs,
        "swap_candidates": swap_candidates,
        "straight_line_prefix": straight_prefix,
        "init_like_wrappers": init_wrappers,
        "has_branch": bool(branch_guards),
        "has_loop": bool(loops),
        "has_sample": bool(samples),
        "has_sampling_obligation": bool(sampling_frontend.get("available")),
        "has_residual_side_condition_pack": bool(side_condition_packs),
        "has_live_state_summary": bool(live_state.get("available")),
        "has_current_region_summary": bool(current_region_summary.get("available")),
        "has_loop_partition_summary": bool(
            loop_partition_summary.get("available")
        ),
        "has_proof_obligation_stack": bool(obligation_stack.get("available")),
        "has_control_suffix_legality": bool(control_suffix.get("available")),
        "has_asymmetric_instrumentation_region": bool(
            asymmetric_region.get("available")
        ),
        "has_result_expression_map": bool(result_expression_map.get("available")),
        "has_bad_event_candidate_map": bool(bad_event_map.get("available")),
        "has_one_sided_call_site_summary": bool(
            one_sided_call_summary.get("available")
        ),
        "has_one_sided_sampling_residual_map": bool(
            one_sided_sampling_residual.get("available")
        ),
        "has_sample_coupling_budget": bool(
            sample_coupling_budget.get("available")
        ),
        "has_swap_candidate": bool(swap_candidates),
        "has_straight_line_prefix": bool(straight_prefix),
        "has_init_like_wrapper": bool(init_wrappers),
        "has_residual_close": residual_close,
        "residual_close_tactic_style": (
            "auto_simplify"
            if any("=>" in item for item in suggested) else
            "auto"
        ),
        "has_conseq_shape": conseq_shape,
        "has_sim": any(item.startswith("sim") for item in suggested),
        "has_wp": any(item.startswith("wp") for item in suggested),
    }


def procedure_live_state_summary(
    parsed: dict[str, Any],
    statements: list[dict[str, Any]],
    goal_text: str,
) -> dict[str, Any]:
    """Summarize proof-relevant variables without choosing a tactic.

    The summary is deliberately approximate.  Its job is to make accepted-but-
    weak sequence cuts and call invariants legible: which variables are visible
    in the post/pre, which are read or written by the current program slice, and
    therefore which facts a prover may need to carry explicitly.
    """
    parsed = _dict(parsed)
    pre_vars = _vars_from_logic_text(str(parsed.get("pre") or ""))
    post_vars = _vars_from_logic_text(str(parsed.get("post") or ""))
    if not pre_vars and not post_vars:
        body = re.sub(r"\s+", " ", str(goal_text or ""))
        post_vars = _vars_from_logic_text(body)
    writes_by_side = _vars_by_side(statements, "vars_written")
    reads_by_side = _vars_by_side(statements, "vars_read")
    program_vars = _dedupe_strings(
        writes_by_side["left"]
        + writes_by_side["right"]
        + reads_by_side["left"]
        + reads_by_side["right"]
    )
    live_post_program_vars = [
        var for var in post_vars
        if var in program_vars or _qualified_leaf(var) in {_qualified_leaf(p) for p in program_vars}
    ]
    live_pre_program_vars = [
        var for var in pre_vars
        if var in program_vars or _qualified_leaf(var) in {_qualified_leaf(p) for p in program_vars}
    ]
    return {
        "available": bool(program_vars or pre_vars or post_vars),
        "post_live_vars": live_post_program_vars[:16],
        "pre_live_vars": live_pre_program_vars[:16],
        "all_post_vars": post_vars[:24],
        "program_written_vars": program_vars[:24],
        "reads_by_side": reads_by_side,
        "writes_by_side": writes_by_side,
        "why": (
            "Visible pre/post and current statement reads/writes; use this to "
            "check whether a seq cut or call invariant carries enough live state."
        ),
        "epistemic_status": "shallow_dataflow_summary_not_typecheck",
    }


def procedure_asymmetric_instrumentation_region(
    statements: list[dict[str, Any]],
    *,
    parsed: dict[str, Any],
    goal_text: str,
) -> dict[str, Any]:
    """Detect one-sided monitor/log/counter style code regions generically."""
    left = [
        _dict(stmt) for stmt in statements
        if str(_dict(stmt).get("side") or "") == "left"
    ]
    right = [
        _dict(stmt) for stmt in statements
        if str(_dict(stmt).get("side") or "") == "right"
    ]
    if not left or not right:
        return {"available": False, "reason": "need_two_sided_program"}
    left_writes = _dedupe_strings([
        str(var) for stmt in left
        for var in _list(stmt.get("vars_written"))
        if _is_live_safe_var(str(var))
    ])
    right_writes = _dedupe_strings([
        str(var) for stmt in right
        for var in _list(stmt.get("vars_written"))
        if _is_live_safe_var(str(var))
    ])
    shared = sorted(set(left_writes) & set(right_writes))
    left_extra = sorted(set(left_writes) - set(right_writes))
    right_extra = sorted(set(right_writes) - set(left_writes))
    if not shared or not (left_extra or right_extra):
        return {"available": False, "reason": "no_shared_core_with_one_sided_state"}
    post_text = " ".join([
        str(_dict(parsed).get("pre") or ""),
        str(_dict(parsed).get("post") or ""),
        str(goal_text or ""),
    ])
    proof_relevant_extra = [
        var for var in [*left_extra, *right_extra]
        if _var_mentioned(post_text, var)
    ]
    return {
        "available": True,
        "kind": "asymmetric_instrumentation_region",
        "instrumented_side": (
            "left" if len(left_extra) > len(right_extra) else
            "right" if len(right_extra) > len(left_extra) else
            "both"
        ),
        "shared_written_vars": shared[:16],
        "left_extra_written_vars": left_extra[:16],
        "right_extra_written_vars": right_extra[:16],
        "proof_relevant_extra_vars": proof_relevant_extra[:16],
        "statement_counts": {"left": len(left), "right": len(right)},
        "kind_counts_by_side": {
            "left": _kind_counts(left),
            "right": _kind_counts(right),
        },
        "candidate_obligations": [
            "check whether the current seq/call invariant carries the one-sided extra state if the post mentions it",
            "when an extra update is guarded, expose the guard obligation with rcondt/rcondf or an explicit case split",
            "after monitor updates are exposed, consider local swap/conseq to realign the shared core",
        ],
        "why": (
            "Both sides share core written state, but one side has extra visible "
            "state updates. Treat sim/wp as unverified candidates; inspect live-state coverage "
            "before committing a cut or invariant."
        ),
        "epistemic_status": "structural_classification_not_recipe",
    }


def procedure_live_fact_budget(
    live_state: dict[str, Any],
    asymmetric_region: dict[str, Any],
) -> dict[str, Any]:
    """Describe the live facts a future cut/invariant should account for.

    This is not an invariant synthesizer.  It gives the prover a neutral
    accounting sheet: which visible post/program variables are proof-relevant,
    which one-sided monitor variables are mentioned by the goal, and therefore
    which facts a weak accepted ``seq``/``call`` invariant may fail to carry.
    """
    live = _dict(live_state)
    region = _dict(asymmetric_region)
    post_live = [
        str(item) for item in _list(live.get("post_live_vars"))
        if str(item)
    ]
    pre_live = [
        str(item) for item in _list(live.get("pre_live_vars"))
        if str(item)
    ]
    shared = [
        str(item) for item in _list(region.get("shared_written_vars"))
        if str(item)
    ]
    proof_relevant_extra = [
        str(item) for item in _list(region.get("proof_relevant_extra_vars"))
        if str(item)
    ]
    one_sided_extra = _dedupe_strings([
        str(item)
        for item in (
            _list(region.get("left_extra_written_vars"))
            + _list(region.get("right_extra_written_vars"))
        )
        if str(item)
    ])
    required = _dedupe_strings([
        *post_live,
        *proof_relevant_extra,
        *shared,
    ])
    return {
        "available": bool(required or pre_live or one_sided_extra),
        "kind": "procedure_live_fact_budget",
        "required_post_live_vars": post_live[:16],
        "required_pre_live_vars": pre_live[:16],
        "shared_core_vars": shared[:16],
        "one_sided_extra_vars": one_sided_extra[:16],
        "proof_relevant_extra_vars": proof_relevant_extra[:16],
        "required_visible_vars": required[:24],
        "coverage_question": (
            "Does the next seq/call/while invariant explicitly preserve these "
            "live facts, or intentionally discharge them as residual side "
            "conditions?"
        ),
        "strategy_boundary": (
            "This is an information budget, not a recipe. The prover still "
            "chooses whether to strengthen the cut, split a guard, or leave a "
            "pure residual for auto/smt."
        ),
    }


def procedure_obligation_stack(
    program_ir: dict[str, Any],
    statements: list[dict[str, Any]],
    *,
    structured_regions: list[dict[str, Any]],
    parsed: dict[str, Any],
    goal_text: str,
) -> dict[str, Any]:
    """Summarize wrapper/oracle/control layers currently visible.

    The stack is an orientation map.  It tells the prover whether the visible
    obligation is still at an abstract caller, an oracle/wrapper call, a local
    procedure body, an instrumentation block, or a control-flow residual.  It
    deliberately avoids naming a required next tactic.
    """
    call_sites = [
        _dict(site) for site in _list(_dict(program_ir).get("call_sites"))
        if isinstance(site, dict)
    ]
    if not call_sites:
        call_sites = [
            _dict(stmt) for stmt in statements
            if _statement_is_call(_dict(stmt))
        ]
    layers: list[dict[str, Any]] = []
    for call in sorted(
        call_sites,
        key=lambda item: (
            int(item.get("order") or item.get("position") or 0),
            str(item.get("side") or ""),
            str(item.get("statement_path") or ""),
        ),
    ):
        layer = _obligation_call_layer(call)
        if not layer:
            continue
        layers.append(layer)
    instrumentation = _instrumentation_layer(statements, parsed=parsed, goal_text=goal_text)
    if instrumentation:
        layers.append(instrumentation)
    for region in structured_regions:
        layer = _control_region_layer(_dict(region))
        if layer:
            layers.append(layer)
    layers = _dedupe_obligation_layers(layers)[:10]
    if not layers:
        return {"available": False, "reason": "no_visible_obligation_layers"}
    active = _active_obligation_layer(layers)
    bulk_risks = _bulk_lowering_risks(layers, statements)
    return {
        "available": True,
        "kind": "procedure_proof_obligation_stack",
        "active_layer": active,
        "layers": layers,
        "bulk_lowering_risks": bulk_risks,
        "layer_question": (
            "Are you trying to solve the current frontier layer, expose one "
            "wrapper, or descend into a generated oracle/control obligation?"
        ),
        "strategy_boundary": (
            "This stack is an orientation map. It does not force a tactic; it "
            "keeps wrapper/oracle/control layers distinct before lowering."
        ),
        "epistemic_status": "structural_frontier_map_not_verified_tactic",
    }


def procedure_control_suffix_legality(
    statements: list[dict[str, Any]],
    *,
    structured_regions: list[dict[str, Any]],
    branch_guards: list[dict[str, Any]],
    loops: list[dict[str, Any]],
    samples: list[dict[str, Any]],
) -> dict[str, Any]:
    """Expose which control tactics are structurally legal at the suffix.

    EasyCrypt tactics such as while/rnd/rcond are sensitive to the active
    statement position.  This pass reports blockers and obligations; it does
    not choose a branch direction or invariant.
    """
    per_side = {
        side: sorted(
            [
                _dict(stmt) for stmt in statements
                if str(_dict(stmt).get("side") or "") == side
                and bool(_dict(stmt).get("top_level", True))
            ],
            key=lambda item: int(item.get("order") or item.get("position") or 0),
        )
        for side in ("left", "right")
    }
    active_regions: list[dict[str, Any]] = []
    for region in structured_regions:
        item = _dict(region)
        kind = str(item.get("kind") or "")
        if kind not in {"loop_frontier", "branch_frontier", "sample_frontier", "call_site"}:
            continue
        side = "left" if str(item.get("side") or "") == "left" else "right"
        order = int(item.get("statement_order") or 0)
        suffix = _suffix_after_order(per_side.get(side, []), order)
        active_regions.append({
            "kind": kind,
            "side": side,
            "side_index": int(item.get("side_index") or (1 if side == "left" else 2)),
            "statement_order": order,
            "statement_path": str(item.get("statement_path") or ""),
            "condition": str(item.get("condition") or ""),
            "is_suffix_frontier": len(suffix) == 0,
            "suffix_blockers": [
                _compact_statement_for_legality(stmt) for stmt in suffix[:4]
            ],
        })
    tactic_legality = _control_tactic_legality(
        active_regions,
        branch_guards=branch_guards,
        loops=loops,
        samples=samples,
    )
    if not active_regions and not tactic_legality:
        return {"available": False, "reason": "no_control_or_suffix_frontier"}
    return {
        "available": True,
        "kind": "procedure_control_suffix_legality",
        "active_regions": active_regions[:8],
        "tactic_legality": tactic_legality,
        "branch_obligation_preview": _branch_obligation_preview(branch_guards),
        "loop_suffix_preview": _loop_suffix_preview(active_regions),
        "sample_suffix_preview": _sample_suffix_preview(active_regions),
        "why": (
            "Control tactics are phase-sensitive: while/rnd/rcond apply to a "
            "visible suffix/frontier, not to arbitrary inner statements."
        ),
        "strategy_boundary": (
            "Use this to decide whether to expose a suffix, split a guard, or "
            "choose a loop invariant. It does not decide the proof branch."
        ),
    }


def procedure_result_expression_map(
    parsed: dict[str, Any],
    statements: list[dict[str, Any]],
    goal_text: str,
) -> dict[str, Any]:
    """Expose result-producing expressions without claiming a proof bridge.

    A common procedure-body trap is treating ``={res}`` as if both programs
    literally return the same variable.  In many goals one side assigns
    ``res`` from a derived expression, while the other returns a boolean or an
    option test.  This pass only surfaces that map; the prover still has to
    prove the bridge.
    """
    by_side = {"left": [], "right": []}
    for stmt in statements:
        item = _dict(stmt)
        side = str(item.get("side") or "")
        if side not in by_side:
            continue
        extracted = _result_expression_from_statement(item)
        if not extracted:
            continue
        by_side[side].append(extracted)
    left = _last_result_expression(by_side["left"])
    right = _last_result_expression(by_side["right"])
    post_text = _proof_text(parsed, goal_text)
    post_mentions_result = _post_mentions_result(post_text)
    relation_shape = _result_relation_shape(left, right)
    direct_risky = bool(
        post_mentions_result
        and left
        and right
        and str(left.get("expression") or "") != str(right.get("expression") or "")
    )
    available = bool(left or right)
    return {
        "available": available,
        "kind": "procedure_result_expression_map",
        "left": left,
        "right": right,
        "relation_shape": relation_shape,
        "post_mentions_result": post_mentions_result,
        "direct_res_equality_risky": direct_risky,
        "source": "program_ir.result_statements",
        "why": (
            "Visible result-producing statements mapped to their expressions. "
            "Use this to check whether a postcondition over res/result needs a "
            "derived expression bridge before sim/skip/auto."
        ),
        "epistemic_status": "shallow_result_expression_map_not_typechecked",
    }


def procedure_one_sided_call_site_summary(
    statements: list[dict[str, Any]],
    *,
    parsed: dict[str, Any],
    goal_text: str,
    result_expression_map: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Summarize calls that are live on only one side of the current slice."""
    calls = [
        _call_site_summary(stmt)
        for stmt in statements
        if _statement_is_call(_dict(stmt))
    ]
    calls = [call for call in calls if call]
    if not calls:
        return {"available": False, "reason": "no_call_sites"}
    by_side = {
        "left": [call for call in calls if call.get("side") == "left"],
        "right": [call for call in calls if call.get("side") == "right"],
    }
    sites: list[dict[str, Any]] = []
    for side, side_calls in by_side.items():
        other = "right" if side == "left" else "left"
        other_calls = by_side[other]
        for call in side_calls:
            if _has_matching_call_site(call, other_calls):
                continue
            if other_calls:
                continue
            side_index = int(call.get("side_index") or 0)
            call = dict(call)
            call["one_sided_tactic_family"] = (
                f"call{{{side_index}}}/ecall{{{side_index}}}"
                if side_index else
                "side-specific call/ecall"
            )
            sites.append(call)
    if not sites:
        return {"available": False, "reason": "calls_have_matching_other_side"}
    result_map = _dict(result_expression_map)
    post_text = _proof_text(parsed, goal_text)
    return {
        "available": True,
        "kind": "procedure_one_sided_call_site_summary",
        "sites": sites[:6],
        "post_mentions_result": _post_mentions_result(post_text),
        "result_expression_map": result_map if result_map.get("available") else {},
        "candidate_obligations": [
            "do not treat a one-sided call as an aligned sim step",
            "use side-specific call/ecall only after the side condition and returned expression bridge are visible",
            "if the other side has already reduced to a pure expression, keep the derived result relation explicit",
        ],
        "why": (
            "A call site is visible on only one side of the current program "
            "slice. This is a frontier map for side-specific call/ecall or "
            "wp/conseq planning, not a tactic recipe."
        ),
        "epistemic_status": "structural_call_site_map_not_verified_tactic",
    }


def procedure_one_sided_sampling_residual_map(
    samples: list[dict[str, Any]],
    *,
    parsed: dict[str, Any],
    goal_text: str,
    live_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Surface one-sided sampling residues without prescribing a repair.

    A side-specific ``rnd{1}``/``rnd{2}`` can be legitimate losslessness work.
    It can also be a sign that a paired coupling was consumed too early, leaving
    a harder quantified postcondition.  This pass makes that debt visible from
    the current state only; it does not inspect traces or name any lemma.
    """
    visible = [
        _dict(sample) for sample in samples
        if isinstance(sample, dict) and str(_dict(sample).get("side") or "")
    ]
    if not visible:
        return {"available": False, "reason": "no_visible_sample_frontier"}
    sides = {
        str(sample.get("side") or "")
        for sample in visible
        if str(sample.get("side") or "") in {"left", "right"}
    }
    if len(sides) != 1:
        return {"available": False, "reason": "not_one_sided_sampling_frontier"}
    side = next(iter(sides))
    side_index = 1 if side == "left" else 2
    text = _proof_text(parsed, goal_text)
    post_text = " ".join([
        str(_dict(parsed).get("post") or ""),
        str(goal_text or ""),
    ])
    sample_records: list[dict[str, Any]] = []
    for sample in visible:
        var = _sample_written_var(sample)
        dist = str(sample.get("distribution") or "")
        if not dist:
            dist = _statement_distribution({
                "statement": str(sample.get("statement") or ""),
                "kind": "SAMPLE",
            })
        sample_records.append({
            "side": side,
            "side_index": side_index,
            "var": var,
            "distribution": dist,
            "statement_order": int(sample.get("statement_order") or 0),
            "statement_path": str(sample.get("statement_path") or ""),
            "statement": str(sample.get("statement") or "")[:160],
            "mentioned_in_post": _sample_var_mentioned(post_text, var, side_index),
        })
    universal_vars = _forall_bound_vars(post_text)
    mentions_sample = any(bool(item.get("mentioned_in_post")) for item in sample_records)
    quantifier_residual = bool(universal_vars and mentions_sample)
    live = _dict(live_state)
    post_live = [
        str(item) for item in _list(live.get("post_live_vars"))
        if str(item)
    ]
    risk_kind = (
        "quantified_coupling_residual_after_one_sided_sample"
        if quantifier_residual else
        "one_sided_lossless_or_distribution_side_condition"
    )
    if not (mentions_sample or quantifier_residual or "forall" in post_text):
        return {
            "available": False,
            "reason": "one_sided_sample_not_visible_in_postcondition",
        }
    return {
        "available": True,
        "kind": "procedure_one_sided_sampling_residual_map",
        "side": side,
        "side_index": side_index,
        "samples": sample_records[:4],
        "universal_witnesses": universal_vars[:6],
        "post_live_vars": post_live[:12],
        "risk_kind": risk_kind,
        "candidate_obligations": [
            "decide whether the sample is genuinely one-sided/lossless or a leftover coupling obligation",
            "if the post relates this sample to a universally quantified witness, account for the distribution/coupling bridge before treating the goal as pure logic",
            "if a paired sample was live before this residual, a cleaner continuation point may be before the side-specific rnd",
        ],
        "why": (
            "A random sample is visible on only one side, and the postcondition "
            "still mentions the sampled value or a quantified witness. This is "
            "a coupling-debt map, not a tactic recipe."
        ),
        "strategy_boundary": (
            "The prover still chooses between a side-specific losslessness step, "
            "a coupling/bijection argument, a postcondition weakening, or going "
            "back to a cleaner frontier."
        ),
        "epistemic_status": "structural_sampling_residual_map_not_typechecked",
    }


def procedure_sample_coupling_budget(
    sampling_frontend: dict[str, Any],
    asymmetric_region: dict[str, Any],
    live_state: dict[str, Any],
    *,
    branch_guards: list[dict[str, Any]],
    parsed: dict[str, Any],
    goal_text: str,
) -> dict[str, Any]:
    """Expose live paired-sample coupling pressure before it is consumed.

    This is the pre-damage counterpart to
    ``procedure_one_sided_sampling_residual_map``.  It does not say how to
    prove the coupling; it tells the prover that a paired sample is still a
    live resource and that nearby one-sided instrumentation/guards can make a
    blind ``wp`` or residual ``auto`` expensive.
    """
    frontend = _dict(sampling_frontend)
    obligations = [
        _dict(item) for item in _list(frontend.get("obligations"))
        if isinstance(item, dict)
    ]
    paired: list[dict[str, Any]] = []
    proof_text = _proof_text(parsed, goal_text)
    for obligation in obligations:
        left = _dict(obligation.get("left_sample"))
        right = _dict(obligation.get("right_sample"))
        if not left or not right or not bool(obligation.get("same_distribution")):
            continue
        lvar = str(left.get("var") or "")
        rvar = str(right.get("var") or "")
        relation = _dict(obligation.get("relation_motif"))
        paired.append({
            "left_sample": _compact_sample_budget_item(left, proof_text),
            "right_sample": _compact_sample_budget_item(right, proof_text),
            "same_distribution": True,
            "distribution": str(
                left.get("distribution") or right.get("distribution") or ""
            ),
            "distribution_leaf": str(
                left.get("distribution_leaf") or right.get("distribution_leaf") or ""
            ),
            "relation_motif": str(relation.get("motif") or "unknown"),
            "sample_vars": [var for var in (lvar, rvar) if var],
            "candidate_families": [
                str(item.get("family") or "")
                for item in _list(obligation.get("candidate_families"))
                if isinstance(item, dict) and str(item.get("family") or "")
            ][:4],
            "required_evidence": _dict(obligation.get("required_evidence")),
        })
    if not paired:
        return {"available": False, "reason": "no_live_paired_sample"}

    asym = _dict(asymmetric_region)
    guards = [
        _dict(item) for item in branch_guards
        if isinstance(item, dict) and str(_dict(item).get("condition") or "")
    ]
    if not asym.get("available") and not guards:
        return {
            "available": False,
            "reason": "paired_sample_without_nearby_instrumentation_or_guard",
        }

    live = _dict(live_state)
    post_live = [
        str(item) for item in _list(live.get("post_live_vars"))
        if str(item)
    ]
    paired_sample_vars = {
        str(item)
        for pair in paired
        for item in _list(pair.get("sample_vars"))
        if str(item)
    }
    proof_relevant_extra = [
        str(item) for item in _list(asym.get("proof_relevant_extra_vars"))
        if str(item) and str(item) not in paired_sample_vars
    ]
    required_visible = _dedupe_strings([
        *post_live,
        *[
            str(item)
            for pair in paired
            for item in _list(pair.get("sample_vars"))
            if str(item)
        ],
        *proof_relevant_extra,
    ])
    hazards = [
        "wp/auto before accounting for the paired sample can turn a coupling obligation into a quantified residual",
        "one-sided instrumentation or guard state should be budgeted in the cut/invariant before pure closing",
    ]
    if guards:
        hazards.append(
            "rcond/if direction still depends on guard entailment from the current path condition"
        )
    return {
        "available": True,
        "kind": "procedure_sample_coupling_budget",
        "paired_samples": paired[:4],
        "instrumentation_region": asym if asym.get("available") else {},
        "branch_guards": [
            {
                "side": str(item.get("side") or ""),
                "side_index": int(item.get("side_index") or 0),
                "statement_order": int(item.get("statement_order") or 0),
                "condition": str(item.get("condition") or ""),
            }
            for item in guards[:4]
        ],
        "required_visible_vars": required_visible[:24],
        "proof_relevant_extra_vars": proof_relevant_extra[:16],
        "wp_auto_hazard": True,
        "hazards": hazards,
        "candidate_obligations": [
            "choose whether the paired sample is coupled now, carried through a seq cut, or intentionally left as a residual",
            "if the next cut/invariant drops a sample or instrumentation variable, expect a harder residual side condition",
            "after any wp/seq/rcond/swap step, re-run agent-view because the live sample budget may change",
        ],
        "strategy_boundary": (
            "This is a liveness/coupling budget, not a proof recipe. The prover "
            "chooses the coupling family, cut, branch split, or rollback point."
        ),
        "epistemic_status": "structural_sample_liveness_not_typechecked",
    }


def procedure_bad_event_candidate_map(
    parsed: dict[str, Any],
    statements: list[dict[str, Any]],
    goal_text: str,
) -> dict[str, Any]:
    """Surface bad/win/event-style state visible in the current frontier.

    This is a semantic resource map, not a tactic recipe.  It only reports
    event-like identifiers that occur in the current goal or visible program
    slice, plus the generic obligation classes an up-to-bad split tends to
    create.  The prover still chooses whether to use a bad-event argument and
    verifies the exact call form with EasyCrypt.
    """
    parsed = _dict(parsed)
    pre = str(parsed.get("pre") or "")
    post = str(parsed.get("post") or "")
    text = " ".join([pre, post, str(goal_text or "")])
    logic_candidates = _bad_event_tokens_from_text(text)
    candidates: list[dict[str, Any]] = []
    for token in logic_candidates:
        candidates.append({
            "name": token,
            "leaf": _qualified_leaf(token),
            "source": (
                "postcondition" if _var_mentioned(post, token) else
                "precondition" if _var_mentioned(pre, token) else
                "goal_text"
            ),
            "side": _side_from_text_occurrence(text, token),
        })
    for stmt in statements:
        item = _dict(stmt)
        side = str(item.get("side") or "")
        statement = str(item.get("statement") or item.get("text") or "")
        proc = str(item.get("procedure") or "")
        order = int(item.get("order") or item.get("position") or 0)
        path = str(item.get("statement_path") or "")
        for key, source in (
            ("vars_written", "statement_write"),
            ("vars_read", "statement_read"),
        ):
            for var in _list(item.get(key)):
                name = str(var)
                if not _is_bad_event_name(name):
                    continue
                candidates.append({
                    "name": name,
                    "leaf": _qualified_leaf(name),
                    "source": source,
                    "side": side,
                    "side_index": 1 if side == "left" else 2 if side == "right" else 0,
                    "statement_order": order,
                    "statement_path": path,
                    "statement": statement,
                })
        for token in _bad_event_tokens_from_text(" ".join([statement, proc])):
            candidates.append({
                "name": token,
                "leaf": _qualified_leaf(token),
                "source": "statement_text" if _var_mentioned(statement, token) else "procedure_name",
                "side": side,
                "side_index": 1 if side == "left" else 2 if side == "right" else 0,
                "statement_order": order,
                "statement_path": path,
                "statement": statement,
                "procedure": proc,
            })
    candidates = _dedupe_event_candidates(candidates)
    if not candidates:
        return {"available": False, "reason": "no_bad_event_like_resource"}
    by_source: dict[str, int] = {}
    for candidate in candidates:
        source = str(candidate.get("source") or "unknown")
        by_source[source] = by_source.get(source, 0) + 1
    primary = _primary_bad_event_candidates(candidates)
    return {
        "available": True,
        "kind": "procedure_bad_event_candidate_map",
        "primary_candidates": primary[:8],
        "all_candidates": candidates[:16],
        "source_counts": by_source,
        "fanout_prediction": {
            "tactic_family": "call (_: <event>, <invariant>)",
            "expected_obligation_classes": [
                "adversary/procedure losslessness",
                "event preservation for generated oracle obligations",
                "initial or prefix event state",
                "postcondition implication under event/non-event cases",
            ],
            "fanout_risk": "high_if_used_before_oracle_obligations_are_mapped",
        },
        "candidate_obligations": [
            "check whether the event is a current proof target or a future oracle obligation",
            "if using an up-to-bad call, budget the generated losslessness and event-preservation subgoals",
            "do not treat event variables as ordinary equality state; they often need implication or case reasoning",
        ],
        "why": (
            "Bad/win/event-like state is visible in the current goal or program "
            "frontier. This map exposes semantic resources and likely fanout "
            "without choosing a proof tactic."
        ),
        "strategy_boundary": (
            "Use this when direct result equality or sim is semantically too "
            "strong; verify any concrete bad-event split with EC before committing."
        ),
        "epistemic_status": "structural_bad_event_map_not_typechecked",
    }


def procedure_current_region_summary(
    statements: list[dict[str, Any]],
    *,
    parsed: dict[str, Any],
    goal_text: str,
    live_state: dict[str, Any] | None = None,
    asymmetric_region: dict[str, Any] | None = None,
    sample_coupling_budget: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Summarize the visible procedure region without choosing a tactic.

    This is the passive compiler map for large procedure states.  It compresses
    a two-column program into semantic regions such as synchronized calls,
    paired samples, shared straight-line updates, and one-sided instrumentation
    so the prover does not have to rediscover the local shape from raw text.
    """
    left = _top_level_statements(statements, "left")
    right = _top_level_statements(statements, "right")
    if not left and not right:
        return {"available": False, "reason": "no_visible_top_level_statements"}

    aligned_regions = _aligned_region_summaries(left, right)
    sync_calls = [
        item for item in aligned_regions
        if str(item.get("kind") or "") == "synchronized_concrete_call"
    ]
    paired_samples = [
        item for item in aligned_regions
        if str(item.get("kind") or "") == "paired_same_distribution_sample"
    ]
    shared_updates = [
        item for item in aligned_regions
        if str(item.get("kind") or "") == "shared_straight_line_update"
    ]
    asym = _dict(asymmetric_region)
    sample_budget = _dict(sample_coupling_budget)
    guards = procedure_branch_guards(statements)
    region_outline = _dedupe_region_outline([
        *aligned_regions,
        *_sample_coupling_region_outline(sample_budget),
        *_asymmetric_region_outline(asym),
        *_guard_region_outline(guards),
    ])
    live = _dict(live_state)
    high_entropy = bool(
        len(left) + len(right) >= 6
        or sync_calls and (paired_samples or asym.get("available") or guards)
        or paired_samples and asym.get("available")
        or asym.get("available") and guards
    )
    available = bool(region_outline and high_entropy)
    if not available:
        return {
            "available": False,
            "reason": "visible_region_too_simple_for_summary",
            "statement_counts": {"left": len(left), "right": len(right)},
        }
    return {
        "available": True,
        "kind": "procedure_current_region_summary",
        "statement_counts": {"left": len(left), "right": len(right)},
        "region_outline": region_outline[:10],
        "synchronized_call_prefix": sync_calls[:4],
        "paired_samples": paired_samples[:4],
        "shared_straight_line_updates": shared_updates[:4],
        "asymmetric_instrumentation": asym if asym.get("available") else {},
        "sample_coupling_budget": (
            sample_budget if sample_budget.get("available") else {}
        ),
        "guard_candidates": [
            {
                "side": str(guard.get("side") or ""),
                "side_index": int(guard.get("side_index") or 0),
                "statement_order": int(guard.get("statement_order") or 0),
                "condition": str(guard.get("condition") or ""),
            }
            for guard in guards[:4]
        ],
        "live_fact_budget": (
            _dict(asym.get("live_fact_budget"))
            if asym.get("available") else
            {}
        ),
        "live_state_summary": live if live.get("available") else {},
        "orientation": (
            "Read this as a region map: close or account for synchronized "
            "prefixes and paired samples, then make one-sided "
            "instrumentation/guard obligations explicit before treating the "
            "residual as pure logic."
        ),
        "strategy_boundary": (
            "This is not a tactic recipe. It preserves the prover's choice of "
            "wp/sp/seq/call/rcond/swap while making the local program shape explicit."
        ),
        "epistemic_status": "shallow_program_region_summary_not_typechecked",
    }


def procedure_loop_partition_summary(
    statements: list[dict[str, Any]],
    *,
    parsed: dict[str, Any],
    goal_text: str,
) -> dict[str, Any]:
    """Summarize one-loop vs partitioned-loop structure without a recipe.

    Some large EasyCrypt proofs encode the same traversal on one side as a
    single loop and on the other side as filtered/concatenated sub-traversals.
    The compiler surface should expose that shape and the relevant operator
    families, while leaving the prover to choose loop invariants, cuts, or
    iterator lemmas.
    """
    left = _top_level_statements(statements, "left")
    right = _top_level_statements(statements, "right")
    left_loops = [
        _dict(stmt) for stmt in left
        if str(_dict(stmt).get("kind") or _dict(stmt).get("type") or "") == "WHILE"
    ]
    right_loops = [
        _dict(stmt) for stmt in right
        if str(_dict(stmt).get("kind") or _dict(stmt).get("type") or "") == "WHILE"
    ]
    if not left_loops and not right_loops:
        return {"available": False, "reason": "no_visible_top_level_loops"}

    parsed = _dict(parsed)
    text = " ".join([
        str(goal_text or ""),
        str(parsed.get("pre") or ""),
        str(parsed.get("post") or ""),
        *[
            str(_dict(stmt).get("statement") or _dict(stmt).get("text") or "")
            for stmt in left + right
        ],
    ])
    signals = _loop_partition_signals(text)
    one_vs_many = (
        (len(left_loops) == 1 and len(right_loops) >= 2)
        or (len(right_loops) == 1 and len(left_loops) >= 2)
    )
    iterator_partition_like = bool(
        "iterator" in signals
        and ({"cat", "filter", "map"} & set(signals))
    )
    if not one_vs_many and not iterator_partition_like:
        return {
            "available": False,
            "reason": "loop_shape_not_partition_like",
            "loop_counts_by_side": {
                "left": len(left_loops),
                "right": len(right_loops),
            },
        }

    if len(left_loops) == len(right_loops):
        shape = "iterator_partition_lemma_context"
        partitioned_side = ""
        single_loop_side = ""
    elif len(left_loops) > len(right_loops):
        shape = "right_single_loop_left_partitioned_loops"
        partitioned_side = "left"
        single_loop_side = "right"
    else:
        shape = "left_single_loop_right_partitioned_loops"
        partitioned_side = "right"
        single_loop_side = "left"
    queries = _loop_partition_search_queries(signals)
    return {
        "available": True,
        "kind": "procedure_loop_partition_summary",
        "shape": shape,
        "loop_counts_by_side": {"left": len(left_loops), "right": len(right_loops)},
        "single_loop_side": single_loop_side,
        "partitioned_side": partitioned_side,
        "partition_signals": signals,
        "left_loops": [_compact_statement_for_legality(stmt) for stmt in left_loops[:4]],
        "right_loops": [
            _compact_statement_for_legality(stmt) for stmt in right_loops[:4]
        ],
        "native_ast_queries": queries,
        "candidate_obligations": [
            "decide whether the loop relation is a single invariant, a split invariant, or an iterator decomposition lemma",
            "preserve the loop-carried state named in the current post/pre before closing residual logic",
            "use EC-native operator search for iterator/list partition facts before guessing lemma names",
        ],
        "orientation": (
            "Read this as a loop-partition map. It does not choose between "
            "while, splitwhile, seq, swap, or a named iterator lemma."
        ),
        "strategy_boundary": (
            "This is structural information only; use it to inspect the loop "
            "frontier and relevant iterator/list operators before lowering."
        ),
        "epistemic_status": "structural_loop_partition_map_not_verified_tactic",
    }


def _obligation_call_layer(call: dict[str, Any]) -> dict[str, Any]:
    proc = str(call.get("procedure") or "").strip()
    if not proc:
        proc = _procedure_from_call_text(str(call.get("statement") or call.get("text") or ""))
    if not proc:
        return {}
    role = str(call.get("frontier_role") or "")
    boundary = str(call.get("call_boundary_kind") or "")
    layer_kind = _call_layer_kind(proc, boundary=boundary, role=role)
    side = str(call.get("side") or "")
    order = int(call.get("order") or call.get("position") or call.get("statement_order") or 0)
    return {
        "layer_kind": layer_kind,
        "source": "call_site",
        "side": side,
        "side_index": 1 if side == "left" else 2 if side == "right" else 0,
        "statement_order": order,
        "statement_path": str(call.get("statement_path") or ""),
        "procedure": proc,
        "procedure_tail": _procedure_tail(proc),
        "frontier_role": role,
        "call_boundary_kind": boundary,
        "is_frontier": bool(call.get("is_frontier_call") or call.get("is_frontier_statement")),
        "orientation": _call_layer_orientation(layer_kind, role),
    }


def _call_layer_kind(procedure: str, *, boundary: str, role: str) -> str:
    proc = str(procedure or "")
    tail = _procedure_tail(proc)
    if boundary == "abstract_adversary_call":
        return "abstract_adversary_frontier"
    if (
        boundary == "oracle_call"
        or role == "oracle_obligation_source"
        or _procedure_mentions_oracle(proc)
    ):
        return "oracle_wrapper_or_boundary"
    if _procedure_mentions_instrumentation(proc):
        return "instrumentation_or_bad_event_call"
    if tail in {"init", "enc", "dec", "f", "g", "main", "distinguish"}:
        return "local_procedure_call"
    return "direct_procedure_call"


def _call_layer_orientation(layer_kind: str, role: str) -> str:
    if layer_kind == "abstract_adversary_frontier":
        return (
            "This call may generate oracle obligations; solve it with an "
            "adversary/call invariant before using oracle-local handles."
        )
    if layer_kind == "oracle_wrapper_or_boundary":
        return (
            "This layer is a wrapper/oracle boundary. Prefer exposing one "
            "wrapper or using a matching oracle handle before bulk inlining."
        )
    if layer_kind == "instrumentation_or_bad_event_call":
        return (
            "This call is instrumentation-like. Track one-sided state and "
            "guard obligations before treating it as a shared core step."
        )
    if role == "nested_non_frontier":
        return (
            "The call is live but not the EasyCrypt last-call frontier; expose "
            "it with wp/seq/targeted lowering before `call <lemma>`."
        )
    return "Direct procedure call layer; check frontier compatibility before call/ecall."


def _instrumentation_layer(
    statements: list[dict[str, Any]],
    *,
    parsed: dict[str, Any],
    goal_text: str,
) -> dict[str, Any]:
    text = _proof_text(parsed, goal_text)
    writes = _dedupe_strings([
        str(var) for stmt in statements
        for var in _list(_dict(stmt).get("vars_written"))
        if _is_instrumentation_name(str(var))
    ])
    calls = [
        _call_site_summary(_dict(stmt)) for stmt in statements
        if _statement_is_call(_dict(stmt))
        and _procedure_mentions_instrumentation(
            str(_dict(stmt).get("procedure") or _dict(stmt).get("statement") or "")
        )
    ]
    calls = [call for call in calls if call]
    proof_relevant = [
        var for var in writes
        if _var_mentioned(text, var) or _is_instrumentation_name(var)
    ]
    if not writes and not calls:
        return {}
    return {
        "layer_kind": "instrumentation_region",
        "source": "statement_writes_and_calls",
        "procedures": [str(call.get("procedure") or "") for call in calls[:4]],
        "written_vars": writes[:12],
        "proof_relevant_vars": proof_relevant[:12],
        "orientation": (
            "Instrumentation/bad-event state is visible. A weak accepted cut "
            "may still be too weak if it drops these variables or guards."
        ),
    }


def _control_region_layer(region: dict[str, Any]) -> dict[str, Any]:
    kind = str(region.get("kind") or "")
    if kind not in {"loop_frontier", "branch_frontier", "sample_frontier"}:
        return {}
    return {
        "layer_kind": kind,
        "source": "structured_region",
        "side": str(region.get("side") or ""),
        "side_index": int(region.get("side_index") or 0),
        "statement_order": int(region.get("statement_order") or 0),
        "statement_path": str(region.get("statement_path") or ""),
        "condition": str(region.get("condition") or ""),
        "orientation": {
            "loop_frontier": "Loop layer: choose/check invariant before loop-local branch/sample search.",
            "branch_frontier": "Branch layer: rcond requires an entailed guard; otherwise split/case.",
            "sample_frontier": "Sampling layer: choose a coupling/lossless family before residual auto/smt.",
        }.get(kind, "Control-flow layer."),
    }


def _dedupe_obligation_layers(layers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for layer in layers:
        item = _dict(layer)
        key = (
            str(item.get("layer_kind") or ""),
            str(item.get("side") or ""),
            str(item.get("statement_order") or ""),
            str(item.get("procedure") or item.get("condition") or item.get("written_vars") or ""),
        )
        if not key[0] or key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def _active_obligation_layer(layers: list[dict[str, Any]]) -> dict[str, Any]:
    for layer in reversed(layers):
        if bool(_dict(layer).get("is_frontier")):
            return dict(layer)
    return dict(layers[-1]) if layers else {}


def _bulk_lowering_risks(
    layers: list[dict[str, Any]],
    statements: list[dict[str, Any]],
) -> list[str]:
    kinds = {str(_dict(layer).get("layer_kind") or "") for layer in layers}
    statement_kinds = {
        str(_dict(stmt).get("kind") or _dict(stmt).get("type") or "").upper()
        for stmt in statements
    }
    risks: list[str] = []
    if "abstract_adversary_frontier" in kinds and (
        "oracle_wrapper_or_boundary" in kinds or "local_procedure_call" in kinds
    ):
        risks.append(
            "bulk inline may collapse adversary/oracle layers before generated obligations are explicit"
        )
    if "instrumentation_region" in kinds or "instrumentation_or_bad_event_call" in kinds:
        risks.append(
            "bulk inline may expose monitor/counter/log updates together with the shared core"
        )
    if len(statement_kinds & {"IF", "WHILE", "SAMPLE", "CALL"}) >= 2:
        risks.append(
            "bulk lowering exposes multiple control obligations at once; inspect the active frontier first"
        )
    return risks


def _procedure_mentions_oracle(procedure: str) -> bool:
    return bool(re.search(
        r"(?:Oracle|Oracles|Orcls|RO\b|ROIN|ROF|ROout|ROin)",
        str(procedure or ""),
    ))


def _procedure_mentions_instrumentation(procedure: str) -> bool:
    return bool(re.search(
        r"(?:bad|badi|cbad|lbad|log|monitor|event|flag)",
        str(procedure or ""),
        flags=re.IGNORECASE,
    ))


def _is_instrumentation_name(name: str) -> bool:
    return bool(re.search(
        r"(?:bad|badi|cbad|lbad|log|monitor|event|flag)",
        str(name or ""),
        flags=re.IGNORECASE,
    ))


def _is_bad_event_name(name: str) -> bool:
    leaf = _qualified_leaf(str(name or ""))
    return bool(re.search(
        r"(?:bad|badi|cbad|lbad|fail|failure|win|event|flag)",
        leaf,
        flags=re.IGNORECASE,
    ))


def _bad_event_tokens_from_text(text: str) -> list[str]:
    tokens = re.findall(
        r"\b[A-Za-z_][A-Za-z0-9_']*(?:\.[A-Za-z_][A-Za-z0-9_']*)*\b",
        str(text or ""),
    )
    skip = {
        "bad", "true", "false", "forall", "exists", "pre", "post", "if",
        "then", "else", "while", "event",
    }
    return _dedupe_strings([
        token for token in tokens
        if token not in skip and _is_bad_event_name(token)
    ])


def _side_from_text_occurrence(text: str, token: str) -> str:
    raw = str(text or "")
    name = re.escape(str(token or ""))
    if re.search(rf"{name}\s*\{{1\}}", raw):
        return "left"
    if re.search(rf"{name}\s*\{{2\}}", raw):
        return "right"
    return ""


def _dedupe_event_candidates(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, int, str]] = set()
    for item in items:
        candidate = _dict(item)
        name = str(candidate.get("name") or "")
        if not name:
            continue
        key = (
            name,
            str(candidate.get("source") or ""),
            str(candidate.get("side") or ""),
            int(candidate.get("statement_order") or 0),
            str(candidate.get("statement_path") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(candidate)
    return out


def _primary_bad_event_candidates(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    priority = {
        "postcondition": 0,
        "goal_text": 1,
        "statement_write": 2,
        "precondition": 3,
        "statement_read": 4,
        "statement_text": 5,
        "procedure_name": 6,
    }
    return sorted(
        [_dict(item) for item in items if isinstance(item, dict)],
        key=lambda item: (
            priority.get(str(item.get("source") or ""), 10),
            str(item.get("name") or ""),
            int(item.get("statement_order") or 0),
        ),
    )


def _loop_partition_signals(text: str) -> list[str]:
    source = str(text or "")
    signals: list[str] = []

    def add(signal: str) -> None:
        if signal and signal not in signals:
            signals.append(signal)

    if re.search(r"(?:^|[.\s])iters?\s*(?:\(|\b)", source):
        add("iterator")
    if "++" in source or re.search(r"\bcat\b", source):
        add("cat")
    if "List.filter" in source or re.search(r"\bfilter\b", source):
        add("filter")
    if "List.map" in source or re.search(r"\bmap\b", source):
        add("map")
    if re.search(r"\b(?:undup|uniq|perm_eq)\b", source):
        add("deduplicate")
    if re.search(r"\b(?:take|drop|iota|range)\b", source):
        add("slice")
    return signals


def _loop_partition_search_queries(signals: list[str]) -> list[dict[str, str]]:
    signal_set = {str(item) for item in signals if str(item)}
    queries: list[dict[str, str]] = []

    def add(query: str, reason: str) -> None:
        if not query or any(item["query"] == query for item in queries):
            return
        queries.append({
            "query": query,
            "action": f"-search-skeleton '{query}'",
            "reason": reason,
        })

    if "iterator" in signal_set and "cat" in signal_set:
        add(
            "iter cat",
            "Loop/iterator structure mentions concatenation; look for decomposition lemmas before hand-searching names.",
        )
    if "iterator" in signal_set and "filter" in signal_set:
        add(
            "iter filter",
            "Loop/iterator structure mentions filtered partitions; look for iterator/filter lemmas before lowering by trial.",
        )
    if "filter" in signal_set and "cat" in signal_set:
        add(
            "filter cat",
            "Partitioned loop state mentions filter and concatenation; look for list partition/reassembly facts.",
        )
    if "map" in signal_set and "filter" in signal_set:
        add(
            "map filter",
            "Residual loop state mentions map over filtered data; native operator search is more precise than regex lookup.",
        )
    return queries[:4]


def _suffix_after_order(
    statements: list[dict[str, Any]],
    order: int,
) -> list[dict[str, Any]]:
    if order <= 0:
        return []
    return [
        _dict(stmt) for stmt in statements
        if int(_dict(stmt).get("order") or _dict(stmt).get("position") or 0) > order
    ]


def _compact_statement_for_legality(stmt: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": str(stmt.get("kind") or stmt.get("type") or ""),
        "statement_order": int(stmt.get("order") or stmt.get("position") or 0),
        "statement_path": str(stmt.get("statement_path") or ""),
        "statement": str(stmt.get("statement") or stmt.get("text") or "")[:120],
        "procedure": str(stmt.get("procedure") or ""),
    }


def _control_tactic_legality(
    active_regions: list[dict[str, Any]],
    *,
    branch_guards: list[dict[str, Any]],
    loops: list[dict[str, Any]],
    samples: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for region in active_regions:
        kind = str(region.get("kind") or "")
        suffix = _list(region.get("suffix_blockers"))
        side_index = int(region.get("side_index") or 0)
        order = int(region.get("statement_order") or 0)
        if kind == "loop_frontier":
            out.append({
                "tactic_family": "while",
                "side_index": side_index,
                "statement_order": order,
                "status": "structurally_ready" if not suffix else "blocked_by_suffix",
                "reason": (
                    "loop is at the visible suffix frontier"
                    if not suffix else
                    "loop has trailing statements; EasyCrypt `while` may report invalid last instruction until suffix/prefix is handled"
                ),
                "blocked_by": suffix[:3],
                "suffix_blockers": suffix[:3],
            })
        elif kind == "branch_frontier":
            out.append({
                "tactic_family": "rcond/if/case",
                "side_index": side_index,
                "statement_order": order,
                "status": "guard_obligation_needed",
                "reason": "rcondt/rcondf needs the guard direction proved; use if/case when neither direction is known",
                "guard": str(region.get("condition") or ""),
            })
        elif kind == "sample_frontier":
            out.append({
                "tactic_family": "rnd",
                "side_index": side_index,
                "statement_order": order,
                "status": "structurally_ready" if not suffix else "blocked_by_suffix",
                "reason": (
                    "sample is at the suffix frontier"
                    if not suffix else
                    "sample has trailing statements; wp/seq may be needed before rnd"
                ),
                "blocked_by": suffix[:3],
                "suffix_blockers": suffix[:3],
            })
    if branch_guards and not any(item.get("tactic_family") == "rcond/if/case" for item in out):
        out.append({
            "tactic_family": "rcond/if/case",
            "status": "guard_obligation_needed",
            "reason": "visible branch guard requires either an entailment proof or an explicit split",
        })
    if loops and not any(item.get("tactic_family") == "while" for item in out):
        out.append({
            "tactic_family": "while",
            "status": "inspect_suffix_first",
            "reason": "loop exists but is not the active structured frontier",
        })
    if samples and not any(item.get("tactic_family") == "rnd" for item in out):
        out.append({
            "tactic_family": "rnd",
            "status": "inspect_suffix_first",
            "reason": "sample exists but is not the active structured frontier",
        })
    return out[:8]


def _branch_obligation_preview(branch_guards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for guard in branch_guards:
        item = _dict(guard)
        condition = str(item.get("condition") or "")
        if not condition:
            continue
        out.append({
            "condition": condition,
            "side_index": int(item.get("side_index") or 0),
            "true_obligation": f"prove `{condition}` from the current pre/path condition",
            "false_obligation": f"prove `!({condition})` from the current pre/path condition",
            "neutral_split": f"case: ({condition}).",
        })
    return out[:4]


def _loop_suffix_preview(active_regions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "side_index": int(region.get("side_index") or 0),
            "statement_order": int(region.get("statement_order") or 0),
            "is_suffix_frontier": bool(region.get("is_suffix_frontier")),
            "suffix_blockers": _list(region.get("suffix_blockers"))[:3],
        }
        for region in active_regions
        if str(region.get("kind") or "") == "loop_frontier"
    ][:4]


def _sample_suffix_preview(active_regions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "side_index": int(region.get("side_index") or 0),
            "statement_order": int(region.get("statement_order") or 0),
            "is_suffix_frontier": bool(region.get("is_suffix_frontier")),
            "suffix_blockers": _list(region.get("suffix_blockers"))[:3],
        }
        for region in active_regions
        if str(region.get("kind") or "") == "sample_frontier"
    ][:4]


def procedure_residual_side_condition_packs(
    parsed: dict[str, Any],
    goal_text: str,
) -> list[dict[str, Any]]:
    """Classify pure side-condition support lemmas from visible syntax.

    This is a standard-library lookup pack, not a project recipe.  The pass
    surfaces likely residual facts for domains/maps, finite counters, list
    indexing, and losslessness after wp/rcond/rnd; the prover still chooses the
    exact closer and verifies scope with EasyCrypt when needed.
    """
    text = " ".join([
        str(_dict(parsed).get("pre") or ""),
        str(_dict(parsed).get("post") or ""),
        str(goal_text or ""),
    ])
    text = re.sub(r"\s+", " ", text)
    packs: list[dict[str, Any]] = []
    map_lemmas: list[str] = []
    if any(token in text for token in ("\\in", "dom", ".m", "mem")):
        map_lemmas.extend(["domE", "get_setE", "mem_set", "mem_empty"])
    if map_lemmas:
        packs.append({
            "kind": "map_membership_residual",
            "evidence": [
                token for token in ["\\in", "dom", ".m", "mem"]
                if token in text
            ],
            "candidate_lemmas": _dedupe_strings(map_lemmas),
            "closer_template": "auto => />; smt(domE get_setE mem_set mem_empty).",
            "reason": (
                "visible residual mentions map/domain/membership syntax; "
                "standard map membership lemmas are likely closer resources"
            ),
        })

    counter_lemmas: list[str] = []
    for prefix in _counter_prefixes(text):
        counter_lemmas.extend([f"{prefix}.ofintdK", f"{prefix}.gt0_max_counter"])
    if "ofintd" in text and not counter_lemmas:
        counter_lemmas.extend(["ofintdK", "gt0_max_counter"])
    if counter_lemmas:
        packs.append({
            "kind": "finite_counter_residual",
            "evidence": [
                token for token in ["ofintd", "toint", "max_counter"]
                if token in text
            ],
            "candidate_lemmas": _dedupe_strings(counter_lemmas),
            "closer_template": (
                "auto => />; smt("
                + " ".join(_dedupe_strings(counter_lemmas)[:6])
                + ")."
            ),
            "reason": (
                "visible residual mentions finite counter conversion or bounds; "
                "use the corresponding counter theory lemmas if they are in scope"
            ),
        })

    list_lemmas: list[str] = []
    list_queries: list[dict[str, str]] = []
    mentions_nth = "nth" in text
    mentions_size = "size" in text
    mentions_cat = "++" in text or re.search(r"\bcat\b", text) is not None
    mentions_map = re.search(r"\bmap\b", text) is not None
    mentions_filter = re.search(r"\bfilter\b", text) is not None
    if any(token in text for token in ("nth", "size", "take", "drop")):
        list_lemmas.extend(["nth0", "nth_default", "size_ge0", "mem_take", "mem_drop"])
    if mentions_cat:
        list_lemmas.append("size_cat")
        if mentions_nth:
            list_lemmas.append("nth_cat")
        list_queries.append({
            "query": "nth cat" if mentions_nth else "size cat",
            "action": "-search-skeleton 'nth cat'" if mentions_nth else "-search-skeleton 'size cat'",
            "reason": "residual mentions list concatenation; inspect cat/list decomposition lemmas before hand-searching",
        })
    if mentions_map:
        list_lemmas.append("size_map")
        if mentions_nth:
            list_lemmas.append("nth_map")
        list_queries.append({
            "query": "nth map" if mentions_nth else "size map",
            "action": "-search-skeleton 'nth map'" if mentions_nth else "-search-skeleton 'size map'",
            "reason": "residual mentions map; inspect EC-native map/list lemmas before guessing names",
        })
    if mentions_filter:
        list_lemmas.append("size_filter")
        list_queries.append({
            "query": "size filter",
            "action": "-search-skeleton 'size filter'",
            "reason": "residual mentions filter; inspect EC-native filter/list lemmas before guessing names",
        })
    if list_lemmas:
        packs.append({
            "kind": "list_index_residual",
            "evidence": [
                token for token in ["nth", "size", "take", "drop", "cat", "map", "filter"]
                if token in text
            ],
            "candidate_lemmas": _dedupe_strings(list_lemmas),
            "native_ast_queries": list_queries[:4],
            "closer_template": (
                "auto => />; smt("
                + " ".join(_dedupe_strings(list_lemmas)[:6])
                + ")."
            ),
            "reason": (
                "visible residual mentions list indexing/size operations; "
                "inspect these generic list lemmas before hand-proving arithmetic"
            ),
        })
    return packs[:4]


def _counter_prefixes(text: str) -> list[str]:
    prefixes: list[str] = []
    for match in re.finditer(
        r"\b([A-Z][A-Za-z0-9_']*)\.(?:ofintd|toint|max_counter)\b",
        str(text or ""),
    ):
        prefixes.append(match.group(1))
    return _dedupe_strings(prefixes)


def procedure_structured_regions(statements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    regions: list[dict[str, Any]] = []
    for stmt in statements:
        side = str(_dict(stmt).get("side") or "")
        order = int(_dict(stmt).get("order") or _dict(stmt).get("position") or 0)
        if side not in {"left", "right"} or order <= 0:
            continue
        kind = str(_dict(stmt).get("kind") or _dict(stmt).get("type") or "").upper()
        text = str(_dict(stmt).get("statement") or _dict(stmt).get("text") or "").strip()
        region_kind = procedure_region_kind(kind, text)
        if not region_kind:
            continue
        # A statement NESTED inside a loop/branch body is not part of the
        # procedure's top-level straight-line prefix. Only the SETUP kinds are
        # gated on top-level: an in-loop assignment must not become a
        # `straight_line_prefix` region (it would inflate the setup count and the
        # sp/wp absorb depth, e.g. `sp 7` when only 6 top-level statements precede
        # the loop). Nested CALL / sample / loop / branch regions still surface —
        # they drive the call-frontier and control rows even when blocked behind a
        # loop — so only the two setup kinds are restricted here.
        statement_path = str(_dict(stmt).get("statement_path") or "")
        top_level = _dict(stmt).get("top_level")
        if top_level is None:
            top_level = ("." not in statement_path) if statement_path else True
        if not top_level and region_kind in {"straight_line_prefix", "wrapper_or_init"}:
            continue
        region: dict[str, Any] = {
            "kind": region_kind,
            "side": side,
            "side_index": 1 if side == "left" else 2,
            "statement_order": order,
            "statement_path": str(_dict(stmt).get("statement_path") or ""),
            "statement": text,
            "pass_families": procedure_region_pass_families(region_kind),
        }
        condition_keyword = (
            "while" if region_kind == "loop_frontier" else
            "if" if region_kind == "branch_frontier" else
            ""
        )
        if condition_keyword:
            region["condition"] = guard_condition(text, keyword=condition_keyword)
        if region_kind == "sample_frontier":
            region["sample_var"] = sample_var(stmt, text)
            region["distribution"] = _sample_statement_distribution(stmt, text)
        if region_kind == "call_site":
            region["procedure"] = str(_dict(stmt).get("procedure") or "")
        if region_kind == "straight_line_prefix":
            region["vars_written"] = _list(_dict(stmt).get("vars_written"))
            region["vars_read"] = _list(_dict(stmt).get("vars_read"))
        regions.append(region)
    return sorted(
        regions,
        key=lambda item: (
            int(_dict(item).get("statement_order") or 0),
            int(_dict(item).get("side_index") or 0),
            str(_dict(item).get("kind") or ""),
        ),
    )[:16]


def procedure_statements_from_pretty_goal(
    goal_text: str,
    goal_type: str,
) -> list[dict[str, Any]]:
    """Recover a shallow one-sided statement table from EC pretty goals.

    EasyCrypt sometimes prints hoare/procedure residuals with numbered program
    lines but the upstream parser does not expose them as ProgramIR statements.
    This fallback keeps the compiler story structural: we parse only statement
    frontiers and variable read/write approximations, not proof-specific names.
    """
    if str(goal_type or "") not in {"hoare", "phoare", "pRHL", "equiv"}:
        return []
    out: list[dict[str, Any]] = []
    for line in str(goal_text or "").splitlines():
        # `\(\s*` is REQUIRED: EasyCrypt right-pads single-digit line numbers for
        # alignment (`( 1)` … `( 9)`) while two-digit lines are flush (`(10)`).
        # Without the `\s*` the digit must sit immediately after `(`, so every
        # single-digit `( N)` line was silently dropped and the parsed program
        # started at statement 10 — making the leading straight-line prefix (and
        # thus every `sp`/`wp` absorb hint) wrong on long single-sided bodies.
        match = re.match(
            r"^\s*\(\s*(?P<path>[0-9][0-9.\s-]*)\)\s*(?P<stmt>.+?)\s*$",
            line,
        )
        if not match:
            continue
        path = re.sub(r"\s+", "", match.group("path")).strip("-")
        stmt = match.group("stmt").strip()
        if not path or not stmt or stmt == "...":
            continue
        order_match = re.match(r"([0-9]+)", path)
        order = int(order_match.group(1)) if order_match else len(out) + 1
        kind = _infer_statement_kind(stmt)
        top_level = "." not in path
        out.append({
            "side": "left",
            "side_index": 1,
            "order": order,
            "position": order,
            "pos": order,
            "statement_path": path,
            "pos_path": path,
            "kind": kind,
            "type": kind,
            "statement": stmt,
            "text": stmt,
            "top_level": top_level,
            "vars_read": _vars_from_statement_read(stmt),
            "vars_written": _vars_from_statement_write(stmt),
            "source": "pretty_goal_fallback",
        })
        if len(out) >= 24:
            break
    return out


def _infer_statement_kind(stmt: str) -> str:
    text = str(stmt or "").strip()
    if text.startswith("while "):
        return "WHILE"
    if text.startswith("if "):
        return "IF"
    if "<@" in text:
        return "CALL"
    if "<$" in text:
        return "SAMPLE"
    if "<-" in text:
        return "ASSIGN"
    if text.startswith("return"):
        return "RETURN"
    return "ABSTRACT"


def _vars_from_statement_read(stmt: str) -> list[str]:
    text = str(stmt or "")
    if "<-" in text:
        text = text.split("<-", 1)[1]
    elif "<$" in text:
        text = text.split("<$", 1)[1]
    elif "<@" in text:
        text = text.split("<@", 1)[1]
    return _dedupe_strings([
        token for token in re.findall(r"\b[A-Za-z_][A-Za-z0-9_'.]*\b", text)
        if token not in {"while", "if", "then", "else", "true", "false"}
    ])


def _vars_from_statement_write(stmt: str) -> list[str]:
    text = str(stmt or "")
    for marker in ("<@", "<$", "<-"):
        if marker in text:
            lhs = text.split(marker, 1)[0]
            return _dedupe_strings([
                token for token in re.findall(r"\b[A-Za-z_][A-Za-z0-9_'.]*\b", lhs)
                if token
            ])
    return []


def procedure_region_kind(kind: str, text: str) -> str:
    upper = str(kind or "").upper()
    raw = str(text or "")
    if upper == "WHILE" or re.search(r"\bwhile\b", raw):
        return "loop_frontier"
    if upper == "IF" or re.search(r"\bif\b", raw):
        return "branch_frontier"
    if upper in {"SAMPLE", "RND"} or "<$" in raw:
        return "sample_frontier"
    if upper == "CALL" or "<@" in raw:
        return "call_site"
    if looks_like_wrapper_call(raw):
        return "wrapper_or_init"
    if upper == "ASSIGN" or "<-" in raw:
        return "straight_line_prefix"
    return ""


def looks_like_wrapper_call(text: str) -> bool:
    raw = str(text or "").strip()
    return bool(raw and _looks_like_qualified_procedure_application(raw))


def procedure_region_pass_families(region_kind: str) -> list[str]:
    if region_kind == "loop_frontier":
        return [
            "while invariant",
            "splitwhile",
            "rcond/case inside loop after invariant",
        ]
    if region_kind == "branch_frontier":
        return ["rcondt/rcondf when entailed", "if/case split otherwise"]
    if region_kind == "sample_frontier":
        return ["rnd coupling", "lossless/distribution side condition"]
    if region_kind == "call_site":
        return ["call named equiv", "call invariant", "wp/seq to expose frontier"]
    if region_kind == "wrapper_or_init":
        return ["targeted inline", "sim/wp after wrapper exposure"]
    if region_kind == "straight_line_prefix":
        return ["sp when names are needed", "wp when working backward is enough"]
    return []


def procedure_frontier_plan(
    *,
    structured_regions: list[dict[str, Any]],
    straight_prefix: list[dict[str, Any]],
    swap_candidates: list[dict[str, Any]],
    init_wrappers: list[str],
) -> dict[str, Any]:
    if not structured_regions and not swap_candidates and not init_wrappers:
        return {"available": False, "reason": "no_structured_regions"}
    non_prefix = [
        _dict(item) for item in structured_regions
        if str(_dict(item).get("kind") or "") != "straight_line_prefix"
    ]
    first_region = _dict(structured_regions[0]) if structured_regions else {}
    next_region = non_prefix[0] if non_prefix else first_region
    next_kind = str(next_region.get("kind") or "")
    has_prefix_before_next = bool(
        straight_prefix
        and next_region
        and int(_dict(straight_prefix[0]).get("statement_order") or 0)
        < int(next_region.get("statement_order") or 0)
    )
    frontier_kind = next_kind or "unknown_frontier"
    if has_prefix_before_next:
        frontier_kind = f"straight_line_prefix_before_{next_kind or 'frontier'}"
    primary_passes: list[str] = []
    alternatives: list[str] = []
    wait_for: list[str] = []
    if has_prefix_before_next:
        primary_passes.append(
            "use sp if the next invariant/seq cut needs names from the straight-line prefix"
        )
        alternatives.append(
            "use wp when backward propagation exposes the same frontier without extra names"
        )
    if next_kind == "loop_frontier":
        primary_passes.append(
            "synthesize/check a loop invariant before entering loop-local branches or samples"
        )
        alternatives.extend([
            "splitwhile when one side has a prefix/suffix phase",
            "rcond/case only after the loop invariant obligation exposes the guard",
        ])
        wait_for.append(
            "defer inner rnd/case proof search until the loop frontier has been split or given an invariant"
        )
    elif next_kind == "branch_frontier":
        primary_passes.append(
            "prove the guard direction with rcondt/rcondf, or split it with if/case when neither direction is entailed"
        )
        alternatives.append("use sp first if symbolic assignments feed the guard")
        wait_for.append("avoid committing a branch direction before the precondition entails it")
    elif next_kind == "sample_frontier":
        primary_passes.append(
            "choose a rnd coupling/lossless family from sampled variables, distributions, and the post relation"
        )
        alternatives.append("use wp first only if the sample is still hidden behind suffix code")
        wait_for.append("avoid plain rnd until the coupling relation and distribution facts are explicit")
    elif next_kind == "call_site":
        primary_passes.append("try a matching named equiv/call invariant at the call frontier")
        alternatives.append("use wp/seq only if the call is not yet EasyCrypt's last-call frontier")
        wait_for.append("avoid inline * while callable handles are still live")
    elif next_kind == "wrapper_or_init":
        primary_passes.append("target-inline the visible wrapper/init procedure, then re-run the frontier pass")
        alternatives.append("sim/wp may close immediately if both sides expose equivalent wrappers")
    elif next_kind == "straight_line_prefix":
        primary_passes.append(
            "use sp or wp to consume the straight-line prefix before choosing a deeper control-flow pass"
        )
    if swap_candidates:
        alternatives.append(
            "use a local swap first when statement alignment evidence shows the same frontier in different order"
        )
    if init_wrappers and next_kind != "wrapper_or_init":
        alternatives.append(
            "target-inline visible init/wrapper calls only when they block the current frontier"
        )
    return {
        "available": True,
        "frontier_kind": frontier_kind,
        "next_structural_region": next_region,
        "primary_passes": _dedupe_strings(primary_passes),
        "alternatives": _dedupe_strings(alternatives),
        "wait_for": _dedupe_strings(wait_for),
        "region_summary": [
            {
                "kind": str(_dict(item).get("kind") or ""),
                "side": str(_dict(item).get("side") or ""),
                "statement_order": int(_dict(item).get("statement_order") or 0),
                "statement_path": str(_dict(item).get("statement_path") or ""),
            }
            for item in structured_regions[:8]
        ],
        "source": "program_ir.structured_regions",
        "epistemic_status": "classification_only_not_verified_tactic",
    }


def procedure_branch_guards(statements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for stmt in statements:
        if str(_dict(stmt).get("kind") or _dict(stmt).get("type") or "") != "IF":
            continue
        side = str(_dict(stmt).get("side") or "")
        order = int(_dict(stmt).get("order") or _dict(stmt).get("position") or 0)
        if side not in {"left", "right"} or order <= 0:
            continue
        out.append({
            "side": side,
            "side_index": 1 if side == "left" else 2,
            "statement_order": order,
            "statement_path": str(_dict(stmt).get("statement_path") or ""),
            "guard": str(_dict(stmt).get("statement") or _dict(stmt).get("text") or ""),
            "condition": guard_condition(
                str(_dict(stmt).get("statement") or _dict(stmt).get("text") or ""),
                keyword="if",
            ),
        })
    return out[:4]


def procedure_loop_statements(statements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for stmt in statements:
        if str(_dict(stmt).get("kind") or _dict(stmt).get("type") or "") != "WHILE":
            continue
        side = str(_dict(stmt).get("side") or "")
        order = int(_dict(stmt).get("order") or _dict(stmt).get("position") or 0)
        if side not in {"left", "right"} or order <= 0:
            continue
        text = str(_dict(stmt).get("statement") or _dict(stmt).get("text") or "")
        out.append({
            "side": side,
            "side_index": 1 if side == "left" else 2,
            "statement_order": order,
            "statement_path": str(_dict(stmt).get("statement_path") or ""),
            "guard": text,
            "condition": guard_condition(text, keyword="while"),
            "vars_read": _list(_dict(stmt).get("vars_read")),
            "vars_written": _list(_dict(stmt).get("vars_written")),
        })
    return out[:4]


def procedure_sample_statements(statements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for stmt in statements:
        kind = str(_dict(stmt).get("kind") or _dict(stmt).get("type") or "")
        text = str(_dict(stmt).get("statement") or _dict(stmt).get("text") or "")
        if kind not in {"SAMPLE", "RND"} and "<$" not in text:
            continue
        side = str(_dict(stmt).get("side") or "")
        order = int(_dict(stmt).get("order") or _dict(stmt).get("position") or 0)
        if side not in {"left", "right"} or order <= 0:
            continue
        out.append({
            "side": side,
            "side_index": 1 if side == "left" else 2,
            "statement_order": order,
            "statement_path": str(_dict(stmt).get("statement_path") or ""),
            "statement": text,
            "distribution": str(_dict(stmt).get("distribution") or ""),
            "vars_written": _list(_dict(stmt).get("vars_written")),
            "vars_read": _list(_dict(stmt).get("vars_read")),
        })
    return out[:4]


def procedure_straight_line_prefix(statements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for side in ("left", "right"):
        top_level = sorted(
            [
                stmt for stmt in statements
                if (
                    isinstance(stmt, dict)
                    and bool(stmt.get("top_level"))
                    and str(stmt.get("side") or "") == side
                )
            ],
            key=lambda item: int(item.get("order") or 0),
        )
        side_count = 0
        for stmt in top_level:
            kind = str(stmt.get("kind") or stmt.get("type") or "")
            if kind not in {"ASSIGN", "ABSTRACT", "ASSERT"}:
                break
            out.append({
                "side": str(stmt.get("side") or ""),
                "side_index": 1 if str(stmt.get("side") or "") == "left" else 2,
                "statement_order": int(stmt.get("order") or 0),
                "statement_path": str(stmt.get("statement_path") or ""),
                "kind": kind,
                "statement": str(stmt.get("statement") or stmt.get("text") or ""),
            })
            # PER-SIDE display bound. The old cap of 4 cut the prefix mid-way; a
            # COMBINED cap could starve the right side when the left has a long
            # prefix (so its leading count would read too low). 16 per side matches
            # procedure_structured_regions and keeps each side's count accurate.
            side_count += 1
            if side_count >= 16:
                break
    return out


def procedure_control_frontiers(
    program_ir: dict[str, Any],
    statements: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    frontier = _dict(_dict(program_ir).get("frontier"))
    by_side = _dict(frontier.get("by_side"))
    by_id = {
        str(stmt.get("statement_id") or ""): stmt
        for stmt in statements
        if isinstance(stmt, dict)
    }
    for side in ("left", "right"):
        item = _dict(by_side.get(side))
        stmt = _dict(by_id.get(str(item.get("statement_id") or "")))
        if not item and not stmt:
            continue
        kind = str(item.get("kind") or stmt.get("kind") or "")
        out.append({
            "side": side,
            "side_index": 1 if side == "left" else 2,
            "kind": kind,
            "statement_order": int(stmt.get("order") or 0),
            "statement_path": str(stmt.get("statement_path") or ""),
            "statement": str(stmt.get("statement") or stmt.get("text") or ""),
            "is_call": bool(item.get("is_call") or stmt.get("is_call_site")),
        })
    return out


def procedure_swap_candidates(
    program_ir: dict[str, Any],
    statements: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    diff = _dict(_dict(program_ir).get("program_diff"))
    for step in _list(diff.get("edit_script")):
        if not isinstance(step, dict):
            continue
        if str(step.get("kind") or "") != "shifted_call_pair":
            continue
        out.append({
            "reason": str(
                step.get("why")
                or "matching call shapes appear at different statement positions"
            ),
            "source": "program_diff.shifted_call_pair",
            "left_statement_order": int(step.get("left_order") or step.get("order") or 0),
            "right_statement_order": int(step.get("right_order") or step.get("order") or 0),
        })
    if out:
        return out[:3]
    for side in ("left", "right"):
        top = [
            stmt for stmt in statements
            if str(stmt.get("side") or "") == side and bool(stmt.get("top_level"))
        ]
        kinds = [str(stmt.get("kind") or "") for stmt in top]
        control_count = sum(1 for kind in kinds if kind in {"IF", "WHILE", "SAMPLE"})
        if len(top) >= 3 and control_count:
            out.append({
                "reason": (
                    "the side has multiple top-level statements around a "
                    "control-flow boundary; a local swap may expose the next wp/rnd/if slice"
                ),
                "source": "top_level_control_sequence",
                "side": side,
                "side_index": 1 if side == "left" else 2,
                "statement_count": len(top),
                "control_statement_count": control_count,
            })
    return out[:3]


def guard_condition(text: str, *, keyword: str) -> str:
    raw = re.sub(r"\s+", " ", str(text or "")).strip()
    match = re.match(rf"^{re.escape(keyword)}\s*\((.*)\)\s*\{{?\s*$", raw)
    if not match:
        return ""
    return match.group(1).strip()


def case_condition_for_tactic(guard: dict[str, Any]) -> str:
    condition = str(_dict(guard).get("condition") or "").strip()
    if not condition:
        text = str(_dict(guard).get("guard") or "")
        condition = guard_condition(text, keyword="if")
    if not condition:
        return ""
    if len(condition) > 120:
        return ""
    if "\n" in condition:
        return ""
    return condition


def procedure_like_statement_calls(statements: list[dict[str, Any]]) -> list[str]:
    out: list[str] = []
    for stmt in statements:
        if bool(_dict(stmt).get("is_call_site")):
            continue
        text = str(_dict(stmt).get("statement") or _dict(stmt).get("text") or "").strip()
        if not text.endswith("()") or "." not in text:
            continue
        call = _parse_procedure_application(text)
        proc = call.procedure.strip()
        module, name = _split_procedure_module_and_name(proc)
        if not module or not name or call.arguments:
            continue
        if not proc or proc.startswith("()"):
            continue
        if procedure_like_name_is_noisy(proc):
            continue
        out.append(proc)
    return _dedupe_strings(out)[:5]


def procedure_like_name_is_noisy(proc: str) -> bool:
    lowered = str(proc or "").lower()
    return lowered in {"true", "false"} or "<" in proc and ">" not in proc


def _result_expression_from_statement(stmt: dict[str, Any]) -> dict[str, Any] | None:
    text = str(stmt.get("statement") or stmt.get("text") or "").strip()
    kind = str(stmt.get("kind") or stmt.get("type") or "").upper()
    if not text:
        return None
    expression = ""
    source_kind = ""
    if kind == "RETURN" or re.match(r"^return\b", text):
        expression = re.sub(r"^return\b", "", text, count=1).strip()
        source_kind = "return"
    elif "<-" in text:
        lhs, rhs = text.split("<-", 1)
        lhs_tokens = re.findall(r"\b[A-Za-z_][A-Za-z0-9_'.]*\b", lhs)
        if not any(_is_result_variable(token) for token in lhs_tokens):
            return None
        expression = rhs.strip()
        source_kind = "result_assignment"
    else:
        return None
    expression = _clean_expression(expression)
    if not expression:
        return None
    side = str(stmt.get("side") or "")
    return {
        "side": side,
        "side_index": 1 if side == "left" else 2 if side == "right" else 0,
        "expression": expression,
        "source_kind": source_kind,
        "statement_order": int(stmt.get("order") or stmt.get("position") or 0),
        "statement_path": str(stmt.get("statement_path") or ""),
        "statement": text,
    }


def _last_result_expression(items: list[dict[str, Any]]) -> dict[str, Any]:
    if not items:
        return {}
    return dict(sorted(
        items,
        key=lambda item: (
            int(_dict(item).get("statement_order") or 0),
            str(_dict(item).get("statement_path") or ""),
        ),
    )[-1])


def _clean_expression(expression: str) -> str:
    text = re.sub(r"\s+", " ", str(expression or "")).strip()
    if ";" in text:
        text = text.split(";", 1)[0].strip()
    return text.strip()


def _is_result_variable(name: str) -> bool:
    leaf = _qualified_leaf(name)
    return leaf in {"res", "result"}


def _proof_text(parsed: dict[str, Any], goal_text: str) -> str:
    parsed = _dict(parsed)
    return " ".join([
        str(parsed.get("pre") or ""),
        str(parsed.get("post") or ""),
        str(goal_text or ""),
    ])


def _post_mentions_result(text: str) -> bool:
    raw = str(text or "")
    return bool(
        re.search(r"\b(?:res|result)\s*\{[12]\}", raw)
        or re.search(r"=\{\s*(?:res|result)\s*\}", raw)
        or re.search(r"\b(?:res|result)\b", raw)
    )


def _result_relation_shape(
    left: dict[str, Any],
    right: dict[str, Any],
) -> str:
    left_expr = str(_dict(left).get("expression") or "")
    right_expr = str(_dict(right).get("expression") or "")
    if left_expr and right_expr and left_expr == right_expr:
        return "same_result_expression"
    if left_expr and right_expr:
        return "derived_result_mismatch"
    if left_expr or right_expr:
        return "one_sided_result_expression"
    return "no_result_expression"


def _statement_is_call(stmt: dict[str, Any]) -> bool:
    kind = str(stmt.get("kind") or stmt.get("type") or "").upper()
    text = str(stmt.get("statement") or stmt.get("text") or "")
    return bool(kind == "CALL" or stmt.get("is_call_site") or "<@" in text)


def _call_site_summary(stmt: dict[str, Any]) -> dict[str, Any]:
    side = str(stmt.get("side") or "")
    if side not in {"left", "right"}:
        return {}
    text = str(stmt.get("statement") or stmt.get("text") or "").strip()
    proc = str(stmt.get("procedure") or "").strip()
    if not proc:
        proc = _procedure_from_call_text(text)
    return {
        "side": side,
        "side_index": 1 if side == "left" else 2,
        "statement_order": int(stmt.get("order") or stmt.get("position") or 0),
        "statement_path": str(stmt.get("statement_path") or ""),
        "statement": text,
        "procedure": proc,
        "procedure_tail": _procedure_tail(proc),
        "is_frontier_statement": bool(stmt.get("is_frontier_statement")),
        "is_frontier_call": bool(stmt.get("is_frontier_call")),
        "requires_cut_to_frontier": bool(stmt.get("requires_cut_to_frontier")),
        "vars_written": _list(stmt.get("vars_written")),
        "vars_read": _list(stmt.get("vars_read")),
    }


def _has_matching_call_site(
    call: dict[str, Any],
    other_calls: list[dict[str, Any]],
) -> bool:
    tail = str(call.get("procedure_tail") or "")
    procedure = str(call.get("procedure") or "")
    for other in other_calls:
        other_tail = str(_dict(other).get("procedure_tail") or "")
        other_procedure = str(_dict(other).get("procedure") or "")
        if tail and other_tail and tail == other_tail:
            return True
        if procedure and other_procedure and procedure == other_procedure:
            return True
    return False


def _top_level_statements(
    statements: list[dict[str, Any]],
    side: str,
) -> list[dict[str, Any]]:
    return sorted(
        [
            _dict(stmt) for stmt in statements
            if (
                isinstance(stmt, dict)
                and str(_dict(stmt).get("side") or "") == side
                and bool(_dict(stmt).get("top_level", True))
            )
        ],
        key=lambda item: int(item.get("order") or item.get("position") or 0),
    )


def _aligned_region_summaries(
    left: list[dict[str, Any]],
    right: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    max_len = max(len(left), len(right))
    for index in range(max_len):
        lstmt = left[index] if index < len(left) else {}
        rstmt = right[index] if index < len(right) else {}
        region = _aligned_region_summary(index + 1, lstmt, rstmt)
        if region:
            out.append(region)
    return out


def _aligned_region_summary(
    ordinal: int,
    left: dict[str, Any],
    right: dict[str, Any],
) -> dict[str, Any]:
    if not left and not right:
        return {}
    if left and right and _statement_is_call(left) and _statement_is_call(right):
        lcall = _call_site_summary(left)
        rcall = _call_site_summary(right)
        same_concrete = _same_procedure(
            str(lcall.get("procedure") or ""),
            str(rcall.get("procedure") or ""),
        )
        same_tail = (
            str(lcall.get("procedure_tail") or "")
            and str(lcall.get("procedure_tail") or "") == str(rcall.get("procedure_tail") or "")
        )
        return {
            "kind": (
                "synchronized_concrete_call"
                if same_concrete else
                "aligned_call_shape"
                if same_tail else
                "different_call_shape"
            ),
            "ordinal": ordinal,
            "left": lcall,
            "right": rcall,
            "same_concrete_procedure": same_concrete,
            "same_procedure_tail": bool(same_tail),
            "orientation": (
                "same concrete procedure call on both sides; this is local "
                "program structure, not by itself evidence that a cross-procedure "
                "named equiv lemma is the next action"
                if same_concrete else
                "aligned call-shaped region; check whether a named equiv or "
                "wrapper exposure is actually at the current frontier"
            ),
        }
    if left and right and _is_sample_statement(left) and _is_sample_statement(right):
        ldist = _statement_distribution(left)
        rdist = _statement_distribution(right)
        return {
            "kind": (
                "paired_same_distribution_sample"
                if ldist and ldist == rdist else
                "paired_sample"
            ),
            "ordinal": ordinal,
            "left": _compact_statement_region(left),
            "right": _compact_statement_region(right),
            "same_distribution": bool(ldist and ldist == rdist),
            "distribution": ldist if ldist == rdist else "",
            "orientation": (
                "paired samples are visible; choose a coupling family before "
                "one-sided sampling or pure residual closing"
            ),
        }
    if left and right and _is_straight_line_statement(left) and _is_straight_line_statement(right):
        shared = sorted(set(_vars(left, "vars_written")) & set(_vars(right, "vars_written")))
        if shared:
            return {
                "kind": "shared_straight_line_update",
                "ordinal": ordinal,
                "left": _compact_statement_region(left),
                "right": _compact_statement_region(right),
                "shared_written_vars": shared[:8],
                "orientation": "shared update prefix; a cut/invariant should preserve facts needed downstream",
            }
    if left and right:
        lkind = str(left.get("kind") or left.get("type") or "")
        rkind = str(right.get("kind") or right.get("type") or "")
        if lkind == rkind and lkind in {"IF", "WHILE"}:
            return {
                "kind": "aligned_control_region",
                "ordinal": ordinal,
                "left": _compact_statement_region(left),
                "right": _compact_statement_region(right),
                "control_kind": lkind,
                "orientation": "aligned control region; guard/invariant obligations still need proof",
            }
    side = "left" if left and not right else "right" if right and not left else ""
    stmt = left or right
    if side and stmt:
        return {
            "kind": "one_sided_region",
            "ordinal": ordinal,
            "side": side,
            "statement": _compact_statement_region(stmt),
            "orientation": "one-sided program region; account for side-specific result/state before sim/auto",
        }
    return {}


def _asymmetric_region_outline(region: dict[str, Any]) -> list[dict[str, Any]]:
    if not _dict(region).get("available"):
        return []
    return [{
        "kind": "asymmetric_instrumentation_region",
        "instrumented_side": str(region.get("instrumented_side") or ""),
        "shared_written_vars": _list(region.get("shared_written_vars"))[:8],
        "left_extra_written_vars": _list(region.get("left_extra_written_vars"))[:8],
        "right_extra_written_vars": _list(region.get("right_extra_written_vars"))[:8],
        "proof_relevant_extra_vars": _list(region.get("proof_relevant_extra_vars"))[:8],
    }]


def _sample_coupling_region_outline(budget: dict[str, Any]) -> list[dict[str, Any]]:
    if not _dict(budget).get("available"):
        return []
    pairs = [
        _dict(item) for item in _list(budget.get("paired_samples"))
        if isinstance(item, dict)
    ]
    if not pairs:
        return []
    return [{
        "kind": "paired_sample_coupling_budget",
        "paired_sample_count": len(pairs),
        "sample_vars": _dedupe_strings([
            str(var)
            for pair in pairs
            for var in _list(pair.get("sample_vars"))
            if str(var)
        ])[:8],
        "required_visible_vars": _list(budget.get("required_visible_vars"))[:8],
        "wp_auto_hazard": bool(budget.get("wp_auto_hazard")),
    }]


def _guard_region_outline(guards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "kind": "guard_obligation_region",
            "side": str(guard.get("side") or ""),
            "side_index": int(guard.get("side_index") or 0),
            "statement_order": int(guard.get("statement_order") or 0),
            "condition": str(guard.get("condition") or ""),
        }
        for guard in guards[:4]
        if str(guard.get("condition") or "")
    ]


def _dedupe_region_outline(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        key = (
            str(item.get("kind") or ""),
            str(item.get("ordinal") or item.get("statement_order") or ""),
            str(item.get("side") or item.get("instrumented_side") or ""),
        )
        if not key[0] or key in seen:
            continue
        seen.add(key)
        out.append(dict(item))
    return out


def _same_procedure(left: str, right: str) -> bool:
    return bool(left and right and _normalize_procedure(left) == _normalize_procedure(right))


def _normalize_procedure(proc: str) -> str:
    return _procedure_exact_key(proc, strip_outer=False)


def _is_straight_line_statement(stmt: dict[str, Any]) -> bool:
    kind = str(stmt.get("kind") or stmt.get("type") or "").upper()
    text = str(stmt.get("statement") or stmt.get("text") or "")
    return bool(kind in {"ASSIGN", "ABSTRACT", "ASSERT"} or "<-" in text)


def _statement_distribution(stmt: dict[str, Any]) -> str:
    item = _dict(stmt)
    return _sample_statement_distribution(
        item,
        str(item.get("statement") or item.get("text") or ""),
        strip_explicit=False,
        strip_fallback=False,
    )


def _compact_sample_budget_item(sample: dict[str, Any], proof_text: str) -> dict[str, Any]:
    item = _dict(sample)
    side_index = int(item.get("side_index") or 0)
    var = str(item.get("var") or "")
    return {
        "side": str(item.get("side") or ""),
        "side_index": side_index,
        "statement_order": int(item.get("statement_order") or 0),
        "statement_path": str(item.get("statement_path") or ""),
        "var": var,
        "distribution": str(item.get("distribution") or ""),
        "distribution_leaf": str(item.get("distribution_leaf") or ""),
        "mentioned_in_post_or_goal": _sample_var_mentioned(
            proof_text,
            var,
            side_index,
        ),
    }


def _sample_written_var(sample: dict[str, Any]) -> str:
    item = _dict(sample)
    return _sample_statement_var(
        item,
        str(item.get("statement") or ""),
        qualified_lhs=True,
    )


def _sample_var_mentioned(text: str, var: str, side_index: int) -> bool:
    raw = str(text or "")
    name = str(var or "")
    if not name:
        return False
    if side_index and re.search(
        rf"(?<![A-Za-z0-9_'.]){re.escape(name)}\s*\{{{side_index}\}}",
        raw,
    ):
        return True
    return _var_mentioned(raw, name)


def _forall_bound_vars(text: str) -> list[str]:
    out: list[str] = []
    for match in re.finditer(
        r"\bforall\s*(?:\(\s*)?([A-Za-z_][A-Za-z0-9_']*)",
        str(text or ""),
    ):
        out.append(match.group(1))
    return _dedupe_strings(out)


def _compact_statement_region(stmt: dict[str, Any]) -> dict[str, Any]:
    return {
        "side": str(stmt.get("side") or ""),
        "side_index": 1 if str(stmt.get("side") or "") == "left" else 2 if str(stmt.get("side") or "") == "right" else 0,
        "statement_order": int(stmt.get("order") or stmt.get("position") or 0),
        "statement_path": str(stmt.get("statement_path") or ""),
        "kind": str(stmt.get("kind") or stmt.get("type") or ""),
        "statement": str(stmt.get("statement") or stmt.get("text") or "")[:160],
        "procedure": str(stmt.get("procedure") or ""),
        "vars_written": _vars(stmt, "vars_written")[:8],
        "vars_read": _vars(stmt, "vars_read")[:8],
    }


def _vars(stmt: dict[str, Any], key: str) -> list[str]:
    return _dedupe_strings([
        str(item) for item in _list(_dict(stmt).get(key))
        if str(item)
    ])


def _procedure_from_call_text(text: str) -> str:
    return _shallow_call_procedure_from_statement(text)


def _procedure_tail(procedure: str) -> str:
    return _procedure_leaf_token(procedure)


def _vars_from_logic_text(text: str) -> list[str]:
    raw = str(text or "")
    tokens = re.findall(r"\b[A-Za-z_][A-Za-z0-9_'.]*\b", raw)
    skip = {
        "pre", "post", "true", "false", "forall", "exists", "fun", "let",
        "in", "res", "glob", "size", "nth", "map", "cat", "filter",
        "witness", "if", "then", "else", "while", "return",
    }
    return _dedupe_strings([
        token for token in tokens
        if token not in skip and _is_live_safe_var(token)
    ])


def _vars_by_side(
    statements: list[dict[str, Any]],
    key: str,
) -> dict[str, list[str]]:
    out = {"left": [], "right": []}
    for stmt in statements:
        item = _dict(stmt)
        side = str(item.get("side") or "")
        if side not in out:
            continue
        out[side].extend([
            str(var) for var in _list(item.get(key))
            if _is_live_safe_var(str(var))
        ])
    return {side: _dedupe_strings(values) for side, values in out.items()}


def _qualified_leaf(name: str) -> str:
    return str(name or "").split(".")[-1]


def _var_mentioned(text: str, var: str) -> bool:
    raw = str(text or "")
    name = str(var or "")
    if not name:
        return False
    if re.search(rf"(?<![A-Za-z0-9_'.]){re.escape(name)}(?![A-Za-z0-9_'.])", raw):
        return True
    leaf = _qualified_leaf(name)
    return bool(
        leaf and leaf != name
        and re.search(rf"(?<![A-Za-z0-9_'.]){re.escape(leaf)}(?![A-Za-z0-9_'.])", raw)
    )


def _kind_counts(statements: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for stmt in statements:
        kind = str(_dict(stmt).get("kind") or _dict(stmt).get("type") or "UNKNOWN")
        counts[kind] = counts.get(kind, 0) + 1
    return counts


__all__ = [
    "PROCEDURE_FRONTEND_KIND",
    "PROCEDURE_FRONTEND_SCHEMA_VERSION",
    "build_procedure_body_frontend",
    "case_condition_for_tactic",
    "contains_top_level_implication",
    "first_top_level_implication",
    "guard_condition",
    "looks_like_wrapper_call",
    "procedure_asymmetric_instrumentation_region",
    "procedure_bad_event_candidate_map",
    "procedure_branch_guards",
    "procedure_control_suffix_legality",
    "procedure_control_frontiers",
    "procedure_current_region_summary",
    "procedure_frontier_plan",
    "procedure_live_fact_budget",
    "procedure_live_state_summary",
    "procedure_like_name_is_noisy",
    "procedure_like_statement_calls",
    "procedure_loop_partition_summary",
    "procedure_loop_statements",
    "procedure_one_sided_call_site_summary",
    "procedure_one_sided_sampling_residual_map",
    "procedure_obligation_stack",
    "procedure_region_kind",
    "procedure_region_pass_families",
    "procedure_residual_side_condition_packs",
    "procedure_result_expression_map",
    "procedure_sample_coupling_budget",
    "procedure_sample_statements",
    "procedure_statements_from_pretty_goal",
    "procedure_straight_line_prefix",
    "procedure_structured_regions",
    "procedure_swap_candidates",
]
