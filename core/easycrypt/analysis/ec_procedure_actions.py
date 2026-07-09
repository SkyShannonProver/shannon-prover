"""Procedure action rendering for EasyCrypt ProofIR facts.

This module turns typed procedure/frontend facts into stable menu-item JSON for
wp/sp/if/while/rnd/swap style actions.  It should not parse raw goals or derive
new semantic resources; those belong in frontend/middle-end passes.
"""
from __future__ import annotations

from typing import Any

from core.easycrypt.analysis.ec_utils import (
    as_dict as _dict,
    as_list as _list,
    dedupe_stripped_strings as _dedupe_strings,
)
from core.easycrypt.analysis.ec_menu_actions import menu_item
from core.easycrypt.analysis.ec_procedure_frontend import (
    case_condition_for_tactic,
)


PROCEDURE_ACTIONS_SCHEMA_VERSION = 1
PROCEDURE_ACTIONS_KIND = "easycrypt_procedure_actions"


def call_site_prefix_menu_items(handles: dict[str, Any]) -> list[dict[str, Any]]:
    """No menu items: this only ever emitted a hardcoded `sp.` move suggestion —
    GUIDANCE, not a state-derived fact. The compiler pushes facts, not move
    advice. The straight-line-prefix STRUCTURE is already surfaced as a fact by
    `procedure_surface_map_menu_items` (the region/control-suffix maps)."""
    return []


def procedure_entry_fallback_menu_items(
    handles: dict[str, Any],
) -> list[dict[str, Any]]:
    frontend = _dict(_dict(handles).get("procedure_body_frontend"))
    structure_status = _dict(frontend.get("program_structure_status"))
    items: list[dict[str, Any]] = []
    if structure_status.get("structure_unavailable"):
        items.append(menu_item(
            "program_structure_unavailable",
            tactic="-program-json",
            tactic_family="program_inspection",
            action_type="inspection_action",
            cost="free",
            why=(
                "The current goal looks like an exposed program residual, but "
                "the structural parser did not recover a stable statement "
                "table. Use structured inspection instead of reading session "
                "files such as current.out."
            ),
            preconditions=[
                "read-only inspection; it does not mutate the proof state",
                "if -program-json is still empty, run -goal-info to refresh EC-native goal facts",
                "after proc/wp/inline/seq, re-run agent-view because the printed program shape may change",
            ],
            preserves=["proof state"],
            cost_factors={
                "program_structure_status": structure_status,
                "inspection_actions": _list(
                    structure_status.get("inspection_actions")
                ),
            },
            program_rank=-10,
            scheduler_role="typed_resource_lookup",
        ))
    # Only the read-only `-program-json` inspection above is a fact. The former
    # 11-tactic fallback palette (wp/sp/while/splitwhile/swap/rnd/if/rcondf/case/
    # conseq/inline) was hardcoded GUIDANCE — bare shapes and placeholder
    # templates — so it is no longer emitted.
    return items


def procedure_frontier_plan_menu_items(
    handles: dict[str, Any],
) -> list[dict[str, Any]]:
    """No menu item: this only emitted the `Structured procedure frontier: …;
    primary: use X` route-PLAN — its own precondition said "this is not a runnable
    tactic", i.e. move GUIDANCE, not a fact. The underlying structural facts
    (region_summary, next structural region, live-state map) are already surfaced
    as facts by `procedure_surface_map_menu_items`, so dropping the plan loses no
    fact."""
    return []


def procedure_surface_map_menu_items(handles: dict[str, Any]) -> list[dict[str, Any]]:
    """Render neutral procedure maps that should be visible across layers."""
    frontend = _dict(_dict(handles).get("procedure_body_frontend"))
    if not frontend.get("available"):
        return []
    items: list[dict[str, Any]] = []
    sample_budget = _dict(frontend.get("sample_coupling_budget"))
    if sample_budget.get("available"):
        label = _sample_coupling_budget_label(sample_budget)
        items.append(menu_item(
            "procedure_sample_coupling_budget_map",
            tactic=f"Inspect sample coupling budget: {label}.",
            tactic_family="procedure_transform",
            action_type="strategy_hint",
            cost="free",
            why=str(
                sample_budget.get("strategy_boundary")
                or (
                    "A paired sampling resource is still live near "
                    "instrumentation or branch state. This is a liveness map, "
                    "not a tactic recipe."
                )
            ),
            preconditions=[
                "not a runnable tactic; use it to audit whether wp/seq/rcond/auto preserves or discharges the displayed sample relation",
                "if wp/auto would consume a live paired sample before the coupling is explicit, expect quantified or one-sided residual debt",
                "compare required_visible_vars with any candidate cut/invariant before committing it",
                "after a mutating tactic, re-run agent-view because the sample budget may disappear or become a residual obligation",
            ],
            preserves=["sampling relation intent", "prover choice of local transform"],
            cost_factors={
                "sample_coupling_budget": sample_budget,
                "wp_auto_hazard": bool(sample_budget.get("wp_auto_hazard")),
                "required_visible_vars": _list(
                    sample_budget.get("required_visible_vars")
                )[:12],
            },
            program_rank=-10,
            scheduler_role="semantic_risk_map",
        ))
    region_summary = _dict(frontend.get("current_region_summary"))
    if region_summary.get("available"):
        label = _current_region_summary_label(region_summary)
        items.append(menu_item(
            "procedure_current_region_summary",
            tactic=f"Inspect current procedure region summary: {label}.",
            tactic_family="procedure_transform",
            action_type="strategy_hint",
            cost="free",
            why=str(
                region_summary.get("strategy_boundary")
                or (
                    "ProgramIR compressed the visible procedure body into "
                    "synchronized prefixes, paired samples, asymmetric "
                    "instrumentation, and guard obligations."
                )
            ),
            preconditions=[
                "not a runnable tactic; use it as a passive map before choosing wp/sp/seq/call/rcond/swap",
                "treat synchronized concrete calls as local program structure; they do not make an off-frontier named equiv automatically preferable",
                "compare live_fact_budget with any candidate cut or invariant before committing it",
                "after a mutating tactic, re-run agent-view because the active region may move",
            ],
            preserves=["current procedure region map", "proof strategy choice"],
            cost_factors={
                "region_summary": region_summary,
                "current_region_summary": region_summary,
                "sample_coupling_budget": sample_budget,
                "asymmetric_instrumentation_region": _dict(
                    frontend.get("asymmetric_instrumentation_region")
                ),
                "live_state_summary": _dict(frontend.get("live_state_summary")),
            },
            program_rank=3,
            scheduler_role="semantic_frontier_map",
        ))
    loop_partition = _dict(frontend.get("loop_partition_summary"))
    if loop_partition.get("available"):
        label = _loop_partition_label(loop_partition)
        queries = [
            _dict(item) for item in _list(loop_partition.get("native_ast_queries"))
            if isinstance(item, dict)
        ]
        preconditions = [
            "not a runnable tactic; use it as a passive map of one-loop vs partitioned-loop structure",
            "choose between loop invariant strengthening, split/swap alignment, or iterator/list lemmas from the displayed structure",
            "after any mutating tactic, re-run agent-view because the active loop region may move",
        ]
        if queries:
            preconditions.insert(
                2,
                "before guessing lemma names, inspect native AST queries: "
                + "; ".join(str(item.get("action") or "") for item in queries[:3]),
            )
        items.append(menu_item(
            "procedure_loop_partition_map",
            tactic=f"Inspect loop partition map: {label}.",
            tactic_family="procedure_transform",
            action_type="strategy_hint",
            cost="free",
            why=str(
                loop_partition.get("strategy_boundary")
                or (
                    "ProgramIR found loop/iterator partition structure. "
                    "This exposes obligations and EC-native search targets "
                    "without choosing a proof script."
                )
            ),
            preconditions=preconditions,
            preserves=[
                "loop partition structure",
                "prover choice of invariant or iterator lemma",
            ],
            cost_factors={
                "loop_partition_summary": loop_partition,
                "region_summary": [{"kind": "loop_partition_summary"}],
                "native_ast_queries": queries[:4],
            },
            program_rank=-6,
            scheduler_role="semantic_frontier_map",
        ))
    stack = _dict(frontend.get("proof_obligation_stack"))
    if stack.get("available"):
        active = _dict(stack.get("active_layer"))
        label = _obligation_layer_label(active)
        bulk_risks = [
            str(item) for item in _list(stack.get("bulk_lowering_risks"))
            if str(item)
        ]
        preconditions = [
            "not a runnable tactic; use it to orient the current wrapper/oracle/control layer",
            "choose whether to solve the current frontier, expose exactly one wrapper, or inspect a generated obligation",
            "after any targeted inline/wp/seq/call step, re-run agent-view because the active layer may move",
        ]
        if bulk_risks:
            preconditions.insert(
                2,
                "bulk lowering is expensive while the listed frontier resources are live",
            )
        items.append(menu_item(
            "procedure_proof_obligation_stack_map",
            tactic=f"Inspect proof obligation stack: {label}.",
            tactic_family="procedure_transform",
            action_type="strategy_hint",
            cost="free",
            why=str(
                stack.get("strategy_boundary")
                or (
                    "Visible wrapper, oracle, instrumentation, and control "
                    "layers are separated so lowering does not silently mix "
                    "current-frontier work with future obligations."
                )
            ),
            preconditions=preconditions,
            preserves=["proof obligation layer map", "call-site handles"],
            cost_factors={
                "proof_obligation_stack": stack,
                "active_layer": active,
                "bulk_lowering_risks": bulk_risks[:4],
            },
            program_rank=-8,
            scheduler_role="semantic_frontier_map",
        ))
    bad_event_map = _dict(frontend.get("bad_event_candidate_map"))
    if bad_event_map.get("available"):
        label = _bad_event_map_label(bad_event_map)
        fanout = _dict(bad_event_map.get("fanout_prediction"))
        expected = [
            str(item) for item in _list(fanout.get("expected_obligation_classes"))
            if str(item)
        ]
        preconditions = [
            "not a runnable tactic; use it to identify event resources and expected obligations",
            "only commit a concrete bad-event split after EC verifies the event expression and invariant shape",
            "do not treat event variables as ordinary equality state; preserve implication/case obligations explicitly",
        ]
        if expected:
            preconditions.append(
                "expected fanout classes: " + "; ".join(expected[:4])
            )
        items.append(menu_item(
            "procedure_bad_event_candidate_map",
            tactic=f"Inspect bad-event candidate map: {label}.",
            tactic_family="procedure_transform",
            action_type="strategy_hint",
            cost="free",
            why=str(
                bad_event_map.get("why")
                or (
                    "Bad/win/event-like state is visible. This is a semantic "
                    "resource map, not a proof recipe."
                )
            ),
            preconditions=preconditions,
            preserves=["bad-event semantic frontier", "prover proof-choice space"],
            cost_factors={
                "bad_event_candidate_map": bad_event_map,
                "fanout_prediction": fanout,
                "primary_candidates": [
                    _dict(item) for item in _list(
                        bad_event_map.get("primary_candidates")
                    ) if isinstance(item, dict)
                ][:8],
            },
            program_rank=-5,
            scheduler_role="semantic_frontier_map",
        ))
    sampling_residual = _dict(frontend.get("one_sided_sampling_residual_map"))
    if sampling_residual.get("available"):
        label = _one_sided_sampling_residual_label(sampling_residual)
        risk_kind = str(sampling_residual.get("risk_kind") or "")
        preconditions = [
            "not a runnable tactic; use it to audit whether this is true one-sided losslessness or remaining coupling debt",
            "if the sampled value is related to a quantified witness, do not treat the residual as pure auto/smt before accounting for that relation",
            "if this residual came from a side-specific rnd while a paired sample was still live, consider a cleaner checkpoint before that rnd",
        ]
        items.append(menu_item(
            "procedure_one_sided_sampling_residual_map",
            tactic=f"Inspect one-sided sampling residual: {label}.",
            tactic_family="procedure_transform",
            action_type="strategy_hint",
            cost="free",
            why=str(
                sampling_residual.get("why")
                or (
                    "A one-sided sample is visible and the postcondition still "
                    "mentions the sampled value or a quantified witness."
                )
            ),
            preconditions=preconditions,
            preserves=["sampling relation intent", "procedure residual shape"],
            cost_factors={
                "one_sided_sampling_residual_map": sampling_residual,
                "risk_kind": risk_kind,
            },
            program_rank=-9,
            scheduler_role=(
                "semantic_risk_map"
                if risk_kind == "quantified_coupling_residual_after_one_sided_sample"
                else "semantic_frontier_map"
            ),
        ))
    suffix = _dict(frontend.get("control_suffix_legality"))
    if suffix.get("available"):
        legality = [
            _dict(item) for item in _list(suffix.get("tactic_legality"))
            if isinstance(item, dict)
        ]
        label = _control_suffix_label(suffix)
        blocked = [
            _control_legality_label(item) for item in legality
            if str(item.get("status") or "") == "blocked_by_suffix"
        ]
        preconditions = [
            "not a runnable tactic; use it to check whether while/rnd/rcond/case is structurally at the frontier",
            "if a control tactic is blocked by suffix code, consume or expose that suffix before committing it",
            "rcond directions still require guard entailment from the current path condition and invariant",
        ]
        if blocked:
            preconditions.insert(1, "blocked control actions: " + "; ".join(blocked[:3]))
        items.append(menu_item(
            "procedure_control_suffix_legality",
            tactic=f"Inspect control/suffix legality: {label}.",
            tactic_family="procedure_transform",
            action_type="strategy_hint",
            cost="free",
            why=str(
                suffix.get("why")
                or (
                    "EasyCrypt control tactics are phase-sensitive; this map "
                    "separates legal frontiers from inner statements with suffix blockers."
                )
            ),
            preconditions=preconditions,
            preserves=["control frontier map", "procedure suffix structure"],
            cost_factors={
                "control_suffix_legality": suffix,
                "tactic_legality": legality[:6],
                "active_regions": [
                    _dict(item) for item in _list(suffix.get("active_regions"))
                    if isinstance(item, dict)
                ][:6],
            },
            program_rank=-7,
            scheduler_role="semantic_frontier_map",
        ))
    result_map = _dict(frontend.get("result_expression_map"))
    if result_map.get("available"):
        relation_shape = str(result_map.get("relation_shape") or "")
        if (
            not result_map.get("direct_res_equality_risky")
            and relation_shape != "one_sided_result_expression"
        ):
            result_map = {}
    if result_map.get("available"):
        left = _dict(result_map.get("left"))
        right = _dict(result_map.get("right"))
        tactic = "Inspect procedure result-expression map before using ={res}."
        left_label = _result_expression_label(left)
        right_label = _result_expression_label(right)
        if left_label or right_label:
            tactic = (
                "Inspect procedure result-expression map: "
                + (left_label or "left result not visible")
                + " vs "
                + (right_label or "right result not visible")
                + "."
            )
        items.append(menu_item(
            "procedure_result_expression_map",
            tactic=tactic,
            tactic_family="procedure_transform",
            action_type="strategy_hint",
            cost="free",
            why=str(
                result_map.get("why")
                or (
                    "Visible result-producing statements may define res/result "
                    "through derived expressions; treat this as a map before "
                    "closing a result equality."
                )
            ),
            preconditions=[
                "not a runnable tactic; use it to audit the postcondition bridge over res/result",
                "if left and right expressions differ, prove or preserve their derived relation before sim/skip/auto",
                "after any wp/call/seq step, re-run agent-view because the returned expression may move",
            ],
            preserves=["result relation intent", "procedure control-flow structure"],
            cost_factors={
                "result_expression_map": result_map,
                "direct_res_equality_risky": bool(
                    result_map.get("direct_res_equality_risky")
                ),
            },
            program_rank=-4,
            scheduler_role="semantic_risk_map",
        ))
    one_sided = _dict(frontend.get("one_sided_call_site_summary"))
    has_ready_named_call = any(
        isinstance(handle, dict)
        and bool(handle.get("callable_now"))
        and str(handle.get("handle_role") or "") != "oracle_obligation_handle"
        for handle in _list(_dict(handles).get("callable_lemmas"))
    )
    if one_sided.get("available") and not has_ready_named_call:
        sites = [
            _dict(site) for site in _list(one_sided.get("sites"))
            if isinstance(site, dict)
        ]
        label = _one_sided_call_label(sites[0]) if sites else "one-sided call"
        items.append(menu_item(
            "procedure_one_sided_call_site_map",
            tactic=f"Inspect one-sided call-site map: {label}.",
            tactic_family="procedure_transform",
            action_type="strategy_hint",
            cost="free",
            why=str(
                one_sided.get("why")
                or (
                    "One side has a live call while the other side is already "
                    "pure or at a different frontier."
                )
            ),
            preconditions=[
                "not a runnable tactic; use it to choose between side-specific call/ecall, wp, and conseq",
                "do not treat the one-sided call as an aligned sim step",
                "if the post mentions res/result, compare the result-expression map before closing the residual",
            ],
            preserves=["one-sided call frontier", "result relation intent"],
            cost_factors={
                "one_sided_call_site_summary": one_sided,
                "result_expression_map": _dict(one_sided.get("result_expression_map")),
            },
            program_rank=-3,
            scheduler_role="semantic_frontier_map",
        ))
    return items


def procedure_body_menu_items(
    handles: dict[str, Any],
    *,
    invariant_hint: str = "<loop invariant from live variables>",
) -> list[dict[str, Any]]:
    frontend = _dict(_dict(handles).get("procedure_body_frontend"))
    if not frontend.get("available"):
        return []
    items: list[dict[str, Any]] = procedure_surface_map_menu_items(handles)
    init_wrappers = [
        str(item) for item in _list(frontend.get("init_like_wrappers"))
        if str(item)
    ]
    if init_wrappers:
        tactic = "inline " + " ".join(init_wrappers[:3]) + "."
        items.append(menu_item(
            "procedure_inline_visible_wrappers",
            tactic=tactic,
            tactic_family="targeted_inline",
            action_type="strategy_hint",
            cost="moderate",
            why=(
                "Procedure-body frontier contains visible wrapper/init calls "
                "printed as statements; targeted inline exposes their bodies "
                "without globally erasing unrelated structure."
            ),
            preconditions=[
                "inline only the visible wrappers needed for this residual subgoal",
                "follow with sim/auto/wp according to the exposed body",
            ],
            preserves=["unrelated procedure structure"],
            destroys=["selected wrapper body"],
            cost_factors={"wrapper_count": len(init_wrappers)},
        ))
    statement_types = {
        str(item) for item in _list(frontend.get("statement_types"))
        if str(item)
    }
    control_frontiers = [
        _dict(item) for item in _list(frontend.get("control_frontiers"))
        if isinstance(item, dict)
    ]
    if statement_types or bool(frontend.get("has_wp")):
        sample_budget = _dict(frontend.get("sample_coupling_budget"))
        wp_preconditions = [
            "use before call/rnd/if when the active statement is still hidden behind suffix code",
            "re-run agent-view after wp because the frontier and live handles change",
        ]
        wp_why = (
            "Procedure body statements are exposed; wp is the backward "
            "pass that consumes assign/call/sample suffixes and reveals "
            "the next control-flow obligation."
        )
        if sample_budget.get("wp_auto_hazard"):
            wp_why = (
                "Procedure body statements are exposed, but a live paired "
                "sample/coupling budget is visible near instrumentation or "
                "guard state. Treat wp as a local transform only after "
                "checking which sample/state facts it will carry or discharge."
            )
            wp_preconditions.insert(
                0,
                "audit procedure_sample_coupling_budget_map before using wp to consume a live sample or instrumentation suffix",
            )
        items.append(menu_item(
            "procedure_wp_frontier",
            tactic="wp.",
            tactic_family="procedure_transform",
            action_type="strategy_hint",
            cost="cheap",
            why=wp_why,
            preconditions=wp_preconditions,
            preserves=["current proof obligation shape"],
            cost_factors={
                "statement_types": sorted(statement_types),
                "control_frontiers": control_frontiers,
                "sample_coupling_budget": sample_budget,
                "wp_auto_hazard": bool(sample_budget.get("wp_auto_hazard")),
            },
        ))
    straight_prefix = [
        _dict(item) for item in _list(frontend.get("straight_line_prefix"))
        if isinstance(item, dict)
    ]
    if straight_prefix:
        items.append(menu_item(
            "procedure_sp_symbolic",
            tactic="sp.",
            tactic_family="procedure_transform",
            action_type="strategy_hint",
            cost="cheap",
            why=(
                "A straight-line symbolic prefix is visible before the next "
                "control boundary; sp names that prefix so if/while/rnd can "
                "be handled with explicit variables."
            ),
            preconditions=[
                "use when the next proof step needs names for assigned expressions",
            ],
            preserves=["control-flow frontier"],
            cost_factors={"prefix": straight_prefix[:3]},
        ))
    asymmetric_region = _dict(frontend.get("asymmetric_instrumentation_region"))
    if asymmetric_region.get("available"):
        budget = _dict(asymmetric_region.get("live_fact_budget"))
        extra = [
            str(item) for item in _list(budget.get("proof_relevant_extra_vars"))
            if str(item)
        ]
        tactic = "Inspect asymmetric instrumentation region before choosing seq/call/wp."
        if extra:
            tactic = (
                "Inspect asymmetric instrumentation region: one-sided live "
                "state " + ", ".join(extra[:4]) + " must be budgeted."
            )
        items.append(menu_item(
            "procedure_asymmetric_instrumentation_map",
            tactic=tactic,
            tactic_family="procedure_transform",
            action_type="strategy_hint",
            cost="free",
            why=str(
                asymmetric_region.get("why")
                or (
                    "One side has extra visible state updates around a shared "
                    "core. This is an information map, not a tactic recipe."
                )
            ),
            preconditions=[
                "not a runnable tactic; use it to audit whether a cut/invariant carries the displayed live state",
                "if the post mentions one-sided extra state, do not treat a weak accepted seq as automatically strong enough",
                "use branch/rcond/swap/conseq only after the corresponding guard/alignment obligation is visible",
                "compare live_fact_budget.required_visible_vars with the candidate cut/invariant before committing",
            ],
            preserves=["proof state", "procedure control-flow structure"],
            cost_factors={
                "region": asymmetric_region,
                "live_state_summary": _dict(frontend.get("live_state_summary")),
            },
            program_rank=-1,
            scheduler_role="semantic_risk_map",
        ))
    branch_guards = [
        _dict(item) for item in _list(frontend.get("branch_guards"))
        if isinstance(item, dict)
    ]
    items.extend(_branch_menu_items(branch_guards))
    loops = [
        _dict(item) for item in _list(frontend.get("loop_frontiers"))
        if isinstance(item, dict)
    ]
    items.extend(_loop_menu_items(loops, invariant_hint=invariant_hint))
    samples = [
        _dict(item) for item in _list(frontend.get("sample_frontiers"))
        if isinstance(item, dict)
    ]
    if samples:
        obligations = [
            _dict(item) for item in _list(frontend.get("sampling_obligations"))
            if isinstance(item, dict)
        ]
        families = [
            _dict(item) for item in _list(frontend.get("sampling_candidate_families"))
            if isinstance(item, dict)
        ]
        preferred_family = preferred_sampling_family(families)
        tactic = str(
            preferred_family.get("tactic_template")
            or "rnd (<coupling map>) (<inverse map>)."
        )
        items.append(menu_item(
            "procedure_rnd_coupling",
            tactic=tactic,
            tactic_family="procedure_transform",
            action_type="strategy_hint",
            cost="cheap",
            why=(
                "Sampling statements are visible. ProofIR classified this as "
                "a typed sampling/coupling obligation: use rnd only after "
                "choosing a coupling family from the sampled variables, "
                "distributions, and postcondition relation."
            ),
            preconditions=[
                "use plain wp first when the sampling statement is still behind assignments",
                *sampling_ordering_preconditions(obligations),
                "choose between identity, translation/affine, boolean flip, product/componentwise, or one-sided lossless forms from the relation evidence",
                "probe the filled tactic with EasyCrypt; this template is not a verified tactic",
            ],
            preserves=["sampling relation"],
            cost_factors={
                "samples": samples[:3],
                "sampling_obligations": obligations[:2],
                "candidate_families": families[:4],
            },
            program_rank=-1,
        ))
    swap_candidates = [
        _dict(item) for item in _list(frontend.get("swap_candidates"))
        if isinstance(item, dict)
    ]
    if swap_candidates:
        items.append(menu_item(
            "procedure_swap_alignment",
            tactic="swap <range> <offset>; wp.",
            tactic_family="procedure_transform",
            action_type="strategy_hint",
            cost="moderate",
            why=(
                "ProgramIR sees reorderable top-level structure around the "
                "current control frontier. A local swap can align statements "
                "before wp/rnd/call."
            ),
            preconditions=[
                "choose the concrete side/range from the displayed statement paths",
                "re-run agent-view after the swap because statement order changes",
            ],
            preserves=["statement semantics"],
            cost_factors={"swap_candidates": swap_candidates[:3]},
        ))
    if statement_types and not init_wrappers and "CALL" not in statement_types:
        items.append(menu_item(
            "procedure_inline_residual",
            tactic="inline <local wrapper>.",
            tactic_family="targeted_inline",
            action_type="strategy_hint",
            cost="moderate",
            why=(
                "No live call handle is attached at this procedure-body slice. "
                "If an opaque local wrapper still blocks wp/sim, inline only "
                "that wrapper rather than reopening unrelated structure."
            ),
            preconditions=[
                "replace the placeholder with a visible local procedure from the goal",
                "prefer wp/if/while/rnd first when the control frontier is already explicit",
            ],
            preserves=["unrelated procedure structure"],
        ))
    if bool(frontend.get("has_conseq_shape")) or loops or swap_candidates:
        items.append(menu_item(
            "procedure_conseq_post",
            tactic="conseq (_: <weaker postcondition preserving live state>) => />.",
            tactic_family="procedure_transform",
            action_type="strategy_hint",
            cost="moderate",
            why=(
                "The pRHL postcondition has a quantified or conjunctive shell; "
                "weaken/normalize it before finishing the residual program body."
            ),
            preconditions=[
                "replace the placeholder with the live relation needed by the remaining body",
                "after conseq, close pure side conditions with auto/smt",
            ],
            preserves=["needed postcondition relation"],
        ))
    side_packs = [
        _dict(item) for item in _list(frontend.get("residual_side_condition_packs"))
        if isinstance(item, dict)
    ]
    if side_packs:
        lemmas = _dedupe_strings([
            str(lemma)
            for pack in side_packs
            for lemma in _list(pack.get("candidate_lemmas"))
            if str(lemma)
        ])
        closer = (
            "auto => />; smt(" + " ".join(lemmas[:8]) + ")."
            if lemmas else
            "auto => />; smt()."
        )
        items.append(menu_item(
            "procedure_residual_side_condition_pack",
            tactic=closer,
            tactic_family="ambient_close",
            action_type="strategy_hint",
            cost="cheap",
            why=(
                "Procedure frontend classified the remaining syntax as a "
                "standard residual side condition pack. Use these as scope-"
                "checked closer resources after the program frontier has been "
                "handled, not as a reason to reopen structure."
            ),
            preconditions=[
                "only use after wp/rcond/rnd/call has reduced the active program slice to pure logic",
                "inspect or remove candidate lemmas that are not in scope for this theory",
                "if the residual still contains a live program frontier, handle that frontier first",
            ],
            preserves=["residual logical obligation"],
            cost_factors={
                "side_condition_packs": side_packs[:4],
                "candidate_lemmas": lemmas[:8],
                "authority_rank": 40,
            },
        ))
    if bool(frontend.get("has_sim")):
        sim_why = "The parser sees structurally aligned residual programs; try sim before heavier low-level passes."
        if asymmetric_region.get("available"):
            sim_why = (
                "The parser sees a sim-shaped residual, but ProcedureIR also "
                "sees one-sided extra state updates. Treat sim as a cheap probe, "
                "not evidence that the instrumentation state is irrelevant."
            )
        one_sided = _dict(frontend.get("one_sided_call_site_summary"))
        result_map = _dict(frontend.get("result_expression_map"))
        if one_sided.get("available"):
            sim_why = (
                "The parser sees a sim-shaped residual, but ProcedureIR also "
                "sees a one-sided call site. Treat sim as a cheap probe, not "
                "evidence that the side-specific call/result bridge is absent."
            )
        elif result_map.get("direct_res_equality_risky"):
            sim_why = (
                "The parser sees a sim-shaped residual, but ProcedureIR also "
                "sees different result-producing expressions. Treat sim as a "
                "cheap probe after auditing the result-expression bridge."
            )
        items.append(menu_item(
            "procedure_sim_residual",
            tactic="sim.",
            tactic_family="procedure_transform",
            action_type="probe_tactic",
            cost="cheap",
            why=sim_why,
            preserves=["synchronized residual structure"],
            cost_factors={
                "asymmetric_instrumentation_region": asymmetric_region,
                "one_sided_call_site_summary": one_sided,
                "result_expression_map": result_map,
            } if (
                asymmetric_region.get("available")
                or one_sided.get("available")
                or result_map.get("direct_res_equality_risky")
            ) else {},
        ))
    if bool(frontend.get("has_residual_close")):
        sample_budget = _dict(frontend.get("sample_coupling_budget"))
        close = (
            "auto => />."
            if str(frontend.get("residual_close_tactic_style") or "") == "auto_simplify" else
            "auto."
        )
        auto_preconditions = [
            "use after the current program statements have been consumed or simplified",
        ]
        auto_why = (
            "The remaining procedure-body obligation looks like a pure "
            "side condition or postcondition residue."
        )
        if sample_budget.get("wp_auto_hazard"):
            auto_why = (
                "The residual closer may be useful later, but ProcedureIR "
                "still sees a live paired sample/coupling budget near "
                "instrumentation or guard state."
            )
            auto_preconditions.insert(
                0,
                "do not treat auto as a pure closer until the sample coupling budget has been preserved, discharged, or intentionally left as a residual",
            )
        items.extend([
            menu_item(
                "procedure_skip_residual",
                tactic="skip.",
                tactic_family="procedure_transform",
                action_type="strategy_hint",
                cost="cheap",
                why=(
                    "The active procedure-body slice may already be reduced to "
                    "a skip-style residual; skip can expose the remaining pure "
                    "postcondition before auto/smt."
                ),
                preconditions=[
                    "use only after program statements have been consumed or are synchronized",
                ],
                preserves=["residual logical obligation"],
            ),
            menu_item(
                "procedure_auto_residual",
                tactic=close,
                tactic_family="ambient_close",
                action_type="probe_tactic",
                cost="cheap",
                why=auto_why,
                preconditions=auto_preconditions,
                preserves=["proof state if the side condition is not solved"],
                cost_factors={
                    "sample_coupling_budget": sample_budget,
                    "wp_auto_hazard": bool(sample_budget.get("wp_auto_hazard")),
                },
            ),
            menu_item(
                "procedure_smt_residual",
                tactic="smt().",
                tactic_family="ambient_close",
                action_type="strategy_hint",
                cost="moderate",
                why=(
                    "If auto leaves arithmetic/list bounds, use SMT with the "
                    "specific bound lemmas visible in context."
                ),
                preconditions=[
                    "try the cheaper auto residual closer first when available",
                ],
                preserves=["proof state until probed"],
            ),
        ])
    return items


def _branch_menu_items(branch_guards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for idx, guard in enumerate(branch_guards[:2]):
        side_index = int(guard.get("side_index") or 0)
        order = int(guard.get("statement_order") or 0)
        if side_index <= 0 or order <= 0:
            continue
        items.extend([
            menu_item(
                f"procedure_rcondt_{side_index}_{order}",
                tactic=f"rcondt{{{side_index}}} {order}; first auto.",
                tactic_family="procedure_transform",
                action_type="strategy_hint",
                cost="moderate",
                why=(
                    "A branch guard is active inside the procedure body. If the "
                    "current precondition entails the guard on this side, reduce "
                    "the branch before continuing with sp/if/wp."
                ),
                preconditions=[
                    "use rcondt only when the side condition proves the guard true",
                    "if the guard is not known, split it with if or move symbolic assignments with sp first",
                ],
                preserves=["current program slice"],
                cost_factors={
                    "side": int(side_index),
                    "statement_order": int(order),
                    "guard": str(guard.get("guard") or ""),
                },
                program_rank=idx,
            ),
            menu_item(
                f"procedure_rcondf_{side_index}_{order}",
                tactic=f"rcondf{{{side_index}}} {order}; first auto.",
                tactic_family="procedure_transform",
                action_type="strategy_hint",
                cost="moderate",
                why=(
                    "The same branch guard can often be discharged as false in "
                    "bad-event or bounds subgoals. rcondf removes the false branch "
                    "while keeping the remaining program slice explicit."
                ),
                preconditions=[
                    "use rcondf only when the side condition proves the guard false",
                    "otherwise split the branch with if/case and keep both obligations",
                ],
                preserves=["current program slice"],
                cost_factors={
                    "side": int(side_index),
                    "statement_order": int(order),
                    "guard": str(guard.get("guard") or ""),
                },
                program_rank=idx,
            ),
        ])
        condition = case_condition_for_tactic(guard)
        if condition:
            items.append(menu_item(
                f"procedure_case_guard_{side_index}_{order}",
                tactic=f"case: ({condition}).",
                tactic_family="procedure_transform",
                action_type="strategy_hint",
                cost="cheap",
                why=(
                    "The guard is a proof-relevant boolean/decidable term. "
                    "A case split can expose the branch assumptions before "
                    "choosing rcond/wp/call in each branch."
                ),
                preconditions=[
                    "prefer rcondt/rcondf when the guard is already implied",
                ],
                preserves=["both branch obligations"],
                cost_factors={
                    "side": int(side_index),
                    "statement_order": int(order),
                    "condition": condition,
                },
                program_rank=idx,
            ))
    if branch_guards:
        items.extend([
            menu_item(
                "procedure_if_split",
                tactic="if => //=.",
                tactic_family="procedure_transform",
                action_type="strategy_hint",
                cost="cheap",
                why=(
                    "The active control frontier is a branch; split it when neither "
                    "rcondt nor rcondf is justified by the current precondition."
                ),
                preconditions=[
                    "use side-specific `if{1}.` or `if{2}.` when only one program side branches",
                ],
                preserves=["branch-local proof obligations"],
            ),
            menu_item(
                "procedure_sp_if",
                tactic="sp; if => //=.",
                tactic_family="procedure_transform",
                action_type="strategy_hint",
                cost="cheap",
                why=(
                    "The procedure body contains branch structure after straight-line "
                    "assignments; move symbolic assignments with sp, then split the guard."
                ),
                preconditions=[
                    "prefer rcondt/rcondf first when the guard is already implied by the precondition",
                ],
                preserves=["branch-local proof obligations"],
            ),
        ])
    return items


def _loop_menu_items(
    loops: list[dict[str, Any]],
    *,
    invariant_hint: str,
) -> list[dict[str, Any]]:
    if not loops:
        return []
    first_loop = loops[0]
    side_index = int(first_loop.get("side_index") or 0)
    order = int(first_loop.get("statement_order") or 0)
    items: list[dict[str, Any]] = []
    if side_index > 0 and order > 0:
        condition = str(first_loop.get("condition") or "").strip()
        split_hint = (
            f"splitwhile{{{side_index}}} {order}: (<split of {condition}>)."
            if condition else
            f"splitwhile{{{side_index}}} {order}: (<loop split condition>)."
        )
        items.append(menu_item(
            "procedure_splitwhile_frontier",
            tactic=split_hint,
            tactic_family="procedure_transform",
            action_type="strategy_hint",
            cost="cheap",
            why=(
                "A loop frontier is visible and may need phase splitting "
                "before the invariant or statement alignment is natural. "
                "splitwhile isolates the relevant loop phase before later "
                "wp/while/rnd steps."
            ),
            preconditions=[
                "use when one side has a loop prefix/suffix phase that should be isolated",
                "fill the split condition from the loop guard and the desired iteration boundary",
                "after splitwhile, re-run agent-view before choosing the invariant",
            ],
            preserves=["loop structure"],
            cost_factors={
                "loop": first_loop,
                "loop_count": len(loops),
            },
            program_rank=0,
        ))
    items.append(menu_item(
        "procedure_while_live",
        tactic=f"while ({invariant_hint}).",
        tactic_family="procedure_transform",
        action_type="strategy_hint",
        cost="moderate",
        why=(
            "A loop frontier is visible. Use a loop invariant synthesized "
            "from live pre/post variables before trying to expose calls "
            "inside the loop body."
        ),
        preconditions=[
            "check the live-variable invariant before committing",
            "after the while split, close initialization, preservation, and exit side conditions separately",
        ],
        preserves=["loop abstraction"],
        cost_factors={"loops": loops[:3]},
    ))
    return items


def preferred_sampling_family(families: list[dict[str, Any]]) -> dict[str, Any]:
    priority = {
        "translation_or_affine": 0,
        "boolean_or_conditional_flip": 1,
        "custom_bijection_or_distribution_bridge": 2,
        "identity": 3,
        "one_sided_lossless_or_predicate": 4,
        "inspect_sample_relation": 9,
    }
    if not families:
        return {}
    return sorted(
        families,
        key=lambda item: (
            priority.get(str(_dict(item).get("family") or ""), 8),
            str(_dict(item).get("family") or ""),
        ),
    )[0]


def sampling_ordering_preconditions(
    obligations: list[dict[str, Any]],
) -> list[str]:
    if not has_paired_and_one_sided_sampling(obligations):
        return []
    return [(
        "when a paired same-distribution sampling obligation and a one-sided "
        "sampling obligation are both visible, handle the paired coupling "
        "first; consume one-sided lossless samples afterwards"
    )]


def has_paired_and_one_sided_sampling(
    obligations: list[dict[str, Any]],
) -> bool:
    has_paired_same_distribution = False
    has_one_sided = False
    for obligation in obligations:
        item = _dict(obligation)
        left = _dict(item.get("left_sample"))
        right = _dict(item.get("right_sample"))
        has_left = bool(left.get("var"))
        has_right = bool(right.get("var"))
        if has_left and has_right and bool(item.get("same_distribution")):
            has_paired_same_distribution = True
        if has_left != has_right:
            has_one_sided = True
    return has_paired_same_distribution and has_one_sided


def procedure_navigation_map(
    frontend: dict[str, Any],
    *,
    setup_counts: "tuple[int, int] | None" = None,
) -> dict[str, Any]:
    """Positioned navigation map of the current obligation body (Q1 lamp / P).

    The procedure frontend already computes the body's straight-line prefix,
    branch guards, and loop/next-region frontiers WITH statement positions; the
    workspace view used to collapse them to bare tactic names. This projects the
    positions back so the agent can pick a POSITIONED tactic by reading
    structure instead of guessing offsets:

      * absorb depth  -> the ``L``/``R`` in ``sp L R`` / ``wp -L -R``
      * branch guards -> which ``if`` is at which order, and its condition
      * loop / next frontier -> where the next ``while`` / call / sample sits

    ``setup_counts`` is the authoritative ``(left, right)`` setup-statement count
    from the frontier alignment. The frontend's ``straight_line_prefix``
    under-counts an ASYMMETRIC two-column setup (right-only leading statements get
    dropped), which made absorb_depth disagree with the alignment row and the
    agent distrust the number. When given, the alignment count wins.

    Facts only. It never chooses a tactic or a branch direction (rcond direction
    still needs guard entailment — see lamp C); those stay the agent's.
    """
    fe = _dict(frontend)
    if not fe.get("available"):
        return {}
    prefix = [_dict(s) for s in _list(fe.get("straight_line_prefix"))]
    guards = [_dict(g) for g in _list(fe.get("branch_guards"))]
    loops = [_dict(loop) for loop in _list(fe.get("loop_frontiers"))]
    plan = _dict(fe.get("frontier_plan"))

    authoritative = {}
    if (isinstance(setup_counts, (list, tuple)) and len(setup_counts) == 2):
        if int(setup_counts[0] or 0) > 0:
            authoritative["left"] = int(setup_counts[0])
        if int(setup_counts[1] or 0) > 0:
            authoritative["right"] = int(setup_counts[1])

    absorb_depth: dict[str, Any] = {}
    for side in ("left", "right"):
        run = [s for s in prefix if str(s.get("side") or "") == side]
        sl_n = len(run)
        align_n = int(authoritative.get(side, 0) or 0)
        # `sp N`/`wp -N` absorbs the LEADING CONTIGUOUS top-level straight-line
        # prefix and STOPS at the first sample/call/loop/branch.
        #  * The body frontend (`procedure_straight_line_prefix`) computes exactly
        #    that leading run — PROVIDED it parsed from the program head (its first
        #    statement is order <= 1). Then prefer it: the alignment instead counts
        #    ALL straight-line assigns before the CALL frontier (pr_G4: 1,2,3,5,8,
        #    10,12 — 5/8/10/12 sit AFTER intervening samples, so `sp 7` would
        #    illegally cross them; the leading run is just 3).
        #  * When the frontend UNDER-parsed the head (an asymmetric two-column setup
        #    whose right leading statements the body parser dropped — so its run
        #    starts mid-program), the alignment count is the complete one.
        run_at_head = bool(run) and min(
            int(s.get("statement_order") or 0) for s in run
        ) <= 1
        if sl_n == 0:
            # The body parser found NO leading assign on this side — the first
            # statement is itself a frontier (sample/call/loop/branch), so there is
            # genuinely NO straight-line prefix to absorb. `sp` must be 0 here; the
            # old alignment fallback produced e.g. `sp 1` that crosses a leading
            # sample (the alignment counts a mid-program assign behind it). The body
            # parser parses the full program, so sl_n==0 reliably means "no head".
            n, used_alignment = 0, False
        elif run_at_head:
            # Frontend parsed the leading contiguous run from the head — authoritative.
            n, used_alignment = sl_n, False
        elif align_n > 0:
            # Frontend run starts mid-program (it under-parsed an asymmetric
            # two-column setup) — the alignment count is the complete one.
            n, used_alignment = align_n, True
        else:
            n, used_alignment = sl_n, False
        if n <= 0:
            continue
        entry: dict[str, Any] = {
            "side_index": 1 if side == "left" else 2,
            "absorbable_statements": n,
        }
        if not used_alignment and run:
            entry["through_order"] = max(int(s.get("statement_order") or 0) for s in run)
            entry["kinds"] = [str(s.get("kind") or "") for s in run]
        elif used_alignment and align_n != sl_n:
            kind = "right-only" if side == "right" else "asymmetric"
            entry["note"] = (
                "count from frontier alignment (" + str(n) + "); the straight-line "
                "body parser classified " + str(sl_n) + " " + kind
                + " setup statement(s) on this side"
            )
        absorb_depth[side] = entry

    if absorb_depth:
        left_n = _dict(absorb_depth.get("left")).get("absorbable_statements", 0) or 0
        right_n = _dict(absorb_depth.get("right")).get("absorbable_statements", 0) or 0
        # `sp` takes BOTH sides at once: `sp <left> <right>` (NOT per-side).
        absorb_depth["sp_hint"] = (
            "sp " + str(left_n) + " " + str(right_n)
            + " / wp -" + str(left_n) + " -" + str(right_n)
            + " absorbs the straight-line setup (" + str(left_n) + " left, "
            + str(right_n) + " right) before the next frontier"
        )

    branch_rows = []
    for g in guards[:4]:
        si = g.get("side_index")
        order = g.get("statement_order")
        branch_rows.append({
            "side_index": si,
            "at_order": order,
            "at_path": g.get("statement_path"),
            "guard": g.get("condition") or g.get("guard"),
            "rcond_forms": (
                "rcondt{" + str(si) + "} " + str(order) + " or rcondf{"
                + str(si) + "} " + str(order)
                + " (direction needs guard entailment — yours to decide)"
            ),
        })

    loop_rows = []
    for loop in loops[:4]:
        loop_rows.append({
            "side_index": loop.get("side_index"),
            "at_order": loop.get("statement_order") or loop.get("order"),
            "statement": loop.get("statement") or loop.get("text"),
        })

    next_frontier = {
        "kind": plan.get("frontier_kind"),
        "at_order": _dict(plan.get("next_structural_region")).get("statement_order"),
    }
    next_frontier = {k: v for k, v in next_frontier.items() if v not in (None, "", 0)}

    content = {
        "absorb_depth": absorb_depth,
        "branch_guards": branch_rows,
        "loop_frontiers": loop_rows,
        "next_frontier": next_frontier,
    }
    content = {k: v for k, v in content.items() if v}
    if not content:  # no positions to navigate -> stay silent
        return {}
    return {
        "how_to_use": (
            "Positions for choosing wp/sp depth, which `if` to rcond, and where "
            "the next loop/call frontier is. Facts only — pick the tactic and the "
            "branch direction yourself."
        ),
        **content,
    }


def sampling_sample_label(sample: dict[str, Any]) -> str:
    item = _dict(sample)
    var = str(item.get("var") or "?")
    side = str(item.get("side_index") or item.get("side") or "?")
    dist = str(item.get("distribution_leaf") or item.get("distribution") or "?")
    order = str(item.get("statement_order") or item.get("statement_path") or "?")
    return f"{var}{{{side}}} <$ {dist} at statement {order}"


def _result_expression_label(item: dict[str, Any]) -> str:
    if not item:
        return ""
    side_index = int(item.get("side_index") or 0)
    expr = str(item.get("expression") or "").strip()
    if not expr:
        return ""
    if len(expr) > 80:
        expr = expr[:77].rstrip() + "..."
    return f"res{{{side_index or '?'}}} := {expr}"


def _one_sided_call_label(item: dict[str, Any]) -> str:
    if not item:
        return "one-sided call"
    side_index = int(item.get("side_index") or 0)
    proc = str(item.get("procedure") or item.get("procedure_tail") or "call")
    order = str(item.get("statement_order") or item.get("statement_path") or "?")
    return f"{proc} on side {side_index or '?'} at statement {order}"


def _one_sided_sampling_residual_label(item: dict[str, Any]) -> str:
    samples = [
        _dict(sample) for sample in _list(_dict(item).get("samples"))
        if isinstance(sample, dict)
    ]
    if not samples:
        return "one-sided sample"
    sample = samples[0]
    var = str(sample.get("var") or "?")
    side = str(sample.get("side_index") or sample.get("side") or "?")
    dist = str(sample.get("distribution") or "?")
    witnesses = [
        str(w) for w in _list(_dict(item).get("universal_witnesses"))
        if str(w)
    ]
    label = f"{var}{{{side}}} <$ {dist}"
    if witnesses:
        label += "; quantified witness " + ", ".join(witnesses[:3])
    return label


def _sample_coupling_budget_label(item: dict[str, Any]) -> str:
    pairs = [
        _dict(pair) for pair in _list(_dict(item).get("paired_samples"))
        if isinstance(pair, dict)
    ]
    labels: list[str] = []
    for pair in pairs[:2]:
        left = _dict(pair.get("left_sample"))
        right = _dict(pair.get("right_sample"))
        lvar = str(left.get("var") or "?")
        rvar = str(right.get("var") or "?")
        dist = str(pair.get("distribution_leaf") or pair.get("distribution") or "?")
        labels.append(f"{lvar}{{1}}/{rvar}{{2}} <$ {dist}")
    extras = [
        str(extra)
        for extra in _list(_dict(item).get("proof_relevant_extra_vars"))
        if str(extra)
    ]
    if extras:
        labels.append("extra state " + ", ".join(extras[:3]))
    return "; ".join(labels) if labels else "paired sample near instrumentation"


def _bad_event_map_label(item: dict[str, Any]) -> str:
    candidates = [
        _dict(candidate) for candidate in _list(item.get("primary_candidates"))
        if isinstance(candidate, dict)
    ]
    names: list[str] = []
    for candidate in candidates:
        name = str(candidate.get("name") or "")
        source = str(candidate.get("source") or "")
        if not name:
            continue
        names.append(f"{name} ({source})" if source else name)
        if len(names) >= 4:
            break
    if names:
        return ", ".join(names)
    return "bad/win/event resource"


def _current_region_summary_label(item: dict[str, Any]) -> str:
    outline = [
        _dict(region) for region in _list(_dict(item).get("region_outline"))
        if isinstance(region, dict)
    ]
    labels: list[str] = []
    for region in outline:
        kind = str(region.get("kind") or "")
        if kind == "synchronized_concrete_call":
            left = _dict(region.get("left"))
            proc = str(left.get("procedure") or "")
            labels.append(f"sync call {proc}" if proc else "sync call")
        elif kind == "paired_same_distribution_sample":
            dist = str(region.get("distribution") or "")
            labels.append(f"paired sample {dist}" if dist else "paired sample")
        elif kind == "asymmetric_instrumentation_region":
            side = str(region.get("instrumented_side") or "")
            labels.append(f"asymmetric instrumentation {side}".strip())
        elif kind == "guard_obligation_region":
            cond = str(region.get("condition") or "")
            labels.append(f"guard {cond}" if cond and len(cond) <= 60 else "guard")
        elif kind == "shared_straight_line_update":
            shared = [
                str(var) for var in _list(region.get("shared_written_vars"))
                if str(var)
            ]
            labels.append(
                "shared update " + ", ".join(shared[:3])
                if shared else
                "shared update"
            )
        if len(labels) >= 3:
            break
    return "; ".join(labels) if labels else "visible procedure regions"


def _loop_partition_label(item: dict[str, Any]) -> str:
    counts = _dict(_dict(item).get("loop_counts_by_side"))
    left = int(counts.get("left") or 0)
    right = int(counts.get("right") or 0)
    signals = [
        str(signal) for signal in _list(_dict(item).get("partition_signals"))
        if str(signal)
    ]
    shape = str(_dict(item).get("shape") or "loop_partition")
    label = f"{shape} ({left} left loop(s), {right} right loop(s))"
    if signals:
        label += "; signals: " + ", ".join(signals[:4])
    return label


def _obligation_layer_label(item: dict[str, Any]) -> str:
    if not item:
        return "visible proof layer map"
    kind = str(item.get("layer_kind") or item.get("kind") or "layer")
    role = str(item.get("frontier_role") or item.get("role") or "")
    proc = str(item.get("procedure") or item.get("procedure_tail") or "")
    order = str(item.get("statement_order") or item.get("statement_path") or "")
    pieces = [kind]
    if role:
        pieces.append(role)
    if proc:
        pieces.append(proc)
    if order:
        pieces.append(f"statement {order}")
    return " / ".join(pieces)


def _control_suffix_label(item: dict[str, Any]) -> str:
    legality = [
        _dict(entry) for entry in _list(item.get("tactic_legality"))
        if isinstance(entry, dict)
    ]
    if not legality:
        regions = [
            _dict(entry) for entry in _list(item.get("active_regions"))
            if isinstance(entry, dict)
        ]
        if regions:
            return ", ".join(_control_region_label(region) for region in regions[:3])
        return "control frontier map"
    return ", ".join(_control_legality_label(entry) for entry in legality[:4])


def _control_legality_label(item: dict[str, Any]) -> str:
    tactic = str(item.get("tactic_family") or item.get("tactic") or "control")
    status = str(item.get("status") or "unknown")
    side = str(item.get("side_index") or item.get("side") or "?")
    order = str(item.get("statement_order") or item.get("statement_path") or "?")
    return f"{tactic}@{side}:{order}={status}"


def _control_region_label(item: dict[str, Any]) -> str:
    kind = str(item.get("kind") or "region")
    side = str(item.get("side_index") or item.get("side") or "?")
    order = str(item.get("statement_order") or item.get("statement_path") or "?")
    suffix = "suffix" if bool(item.get("is_suffix_frontier")) else "inner"
    return f"{kind}@{side}:{order}:{suffix}"


def sampling_ordering_diagnostics(
    handles: dict[str, Any],
) -> list[dict[str, Any]]:
    frontend = _dict(_dict(handles).get("procedure_body_frontend"))
    obligations = [
        _dict(item) for item in _list(frontend.get("sampling_obligations"))
        if isinstance(item, dict)
    ]
    diagnostics: list[dict[str, Any]] = []
    paired = []
    one_sided = []
    if has_paired_and_one_sided_sampling(obligations):
        for obligation in obligations:
            left = _dict(obligation.get("left_sample"))
            right = _dict(obligation.get("right_sample"))
            has_left = bool(left.get("var"))
            has_right = bool(right.get("var"))
            if has_left and has_right and bool(obligation.get("same_distribution")):
                paired.append(
                    f"{sampling_sample_label(left)} with "
                    f"{sampling_sample_label(right)}"
                )
            elif has_left != has_right:
                sample = left if has_left else right
                one_sided.append(sampling_sample_label(sample))
        diagnostics.append({
            "code": "proof_ir.sampling_pair_before_one_sided",
            "severity": "warning",
            "message": (
                "Sampling order note: a paired same-distribution sample is still "
                "live"
                + (f" ({'; '.join(paired[:2])})" if paired else "")
                + ", while one-sided sample(s) are also visible"
                + (f" ({'; '.join(one_sided[:2])})" if one_sided else "")
                + ". EasyCrypt may accept `rnd{1}.` or `rnd{2}.`, but consuming "
                "a one-sided sample first can turn the remaining coupling into a "
                "harder custom bridge."
            ),
            "repairs": [
                (
                    "Resolve the displayed same-distribution pair first with "
                    "the identity/translation/affine `rnd` family, then consume "
                    "one-sided lossless samples."
                ),
                (
                    "Treat a successful one-sided `rnd{1}.` or `rnd{2}.` as "
                    "potentially premature unless no paired sample obligation "
                    "is live."
                ),
            ],
        })
    residual = _dict(frontend.get("one_sided_sampling_residual_map"))
    if residual.get("available"):
        samples = [
            _one_sided_sampling_residual_label(residual)
        ]
        diagnostics.append({
            "code": "proof_ir.one_sided_sampling_residual",
            "severity": "info",
            "message": (
                "One-sided sampling residual: "
                + "; ".join(samples)
                + ". The postcondition still mentions the sampled value or a "
                "quantified witness, so this may be a true losslessness side "
                "condition or leftover coupling debt."
            ),
            "repairs": [
                (
                    "If this is intended to be one-sided, close the displayed "
                    "distribution/losslessness obligation explicitly."
                ),
                (
                    "If a paired sample was live before this residual, prefer "
                    "the paired coupling before side-specific rnd."
                ),
            ],
        })
    return diagnostics


__all__ = [
    "PROCEDURE_ACTIONS_KIND",
    "PROCEDURE_ACTIONS_SCHEMA_VERSION",
    "call_site_prefix_menu_items",
    "has_paired_and_one_sided_sampling",
    "preferred_sampling_family",
    "procedure_body_menu_items",
    "procedure_entry_fallback_menu_items",
    "procedure_frontier_plan_menu_items",
    "procedure_surface_map_menu_items",
    "sampling_ordering_diagnostics",
    "sampling_ordering_preconditions",
    "sampling_sample_label",
]
