"""Tests for procedure action/menu rendering."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from core.easycrypt.analysis.ec_procedure_actions import (  # noqa: E402
    call_site_prefix_menu_items,
    has_paired_and_one_sided_sampling,
    preferred_sampling_family,
    procedure_body_menu_items,
    procedure_entry_fallback_menu_items,
    procedure_frontier_plan_menu_items,
    procedure_surface_map_menu_items,
    sampling_ordering_diagnostics,
)
from core.easycrypt.analysis.ec_action_contracts import (  # noqa: E402
    normalize_action_candidates,
)


def test_call_site_prefix_menu_items_emits_no_guidance() -> None:
    # The hardcoded `sp.` prefix suggestion was move GUIDANCE, not a state-derived
    # fact, so the producer no longer emits it. The straight-line-prefix STRUCTURE
    # is surfaced as a fact by `procedure_surface_map_menu_items` instead.
    items = call_site_prefix_menu_items({
        "procedure_body_frontend": {
            "available": True,
            "has_loop": True,
            "straight_line_prefix": [{"side": "left", "statement_order": 1}],
            "control_frontiers": [{"kind": "WHILE"}],
        },
    })

    assert items == []


def test_procedure_entry_fallback_menu_items_drops_hardcoded_palette() -> None:
    # The 11-tactic fallback palette (wp/sp/while/splitwhile/swap/rnd/if/rcondf/
    # case/conseq/inline) was hardcoded GUIDANCE — bare shapes and placeholder
    # templates — so it is no longer emitted. Only the read-only `-program-json`
    # inspection (gated on `structure_unavailable`, asserted below) remains.
    assert procedure_entry_fallback_menu_items({}) == []


def test_procedure_entry_fallback_surfaces_structure_inspection_gap() -> None:
    items = procedure_entry_fallback_menu_items({
        "procedure_body_frontend": {
            "program_structure_status": {
                "structure_unavailable": True,
                "inspection_actions": ["-program-json", "-goal-info"],
            },
        },
    })

    assert items[0]["id"] == "program_structure_unavailable"
    assert items[0]["action_type"] == "inspection_action"
    assert items[0]["tactic"] == "-program-json"
    assert items[0]["scheduler_role"] == "typed_resource_lookup"
    assert "current.out" in items[0]["why"]
    assert not normalize_action_candidates(items)[0].get("contract_errors")


def test_procedure_frontier_plan_menu_items_emits_no_plan() -> None:
    # The "Structured procedure frontier: …; primary: use X" route-PLAN was move
    # GUIDANCE (its own precondition said "this is not a runnable tactic"); the
    # underlying region facts are surfaced by `procedure_surface_map_menu_items`.
    items = procedure_frontier_plan_menu_items({
        "procedure_body_frontend": {
            "frontier_plan": {
                "available": True,
                "frontier_kind": "sample_frontier",
                "primary_passes": ["choose a rnd coupling"],
                "wait_for": ["avoid plain rnd"],
                "region_summary": [{"kind": "sample_frontier"}],
            },
        },
    })

    assert items == []


def test_procedure_body_menu_items_render_branch_loop_and_sampling_actions() -> None:
    items = procedure_body_menu_items(
        {
            "procedure_body_frontend": {
                "available": True,
                "statement_types": ["IF", "WHILE", "SAMPLE"],
                "branch_guards": [{
                    "side_index": 1,
                    "statement_order": 2,
                    "guard": "if (x \\in xs) {",
                    "condition": "x \\in xs",
                }],
                "loop_frontiers": [{
                    "side_index": 1,
                    "statement_order": 3,
                    "condition": "i < n",
                }],
                "sample_frontiers": [{"side_index": 1, "statement_order": 4}],
                "sampling_obligations": [{
                    "left_sample": {"var": "s", "side_index": 1},
                    "right_sample": {"var": "t", "side_index": 2},
                    "same_distribution": True,
                }],
                "sampling_candidate_families": [{
                    "family": "translation_or_affine",
                    "tactic_template": "rnd (fun x => x + k) (fun x => x - k).",
                }],
            },
        },
        invariant_hint="={i}",
    )
    by_id = {item["id"]: item for item in items}

    assert by_id["procedure_rcondt_1_2"]["tactic"] == "rcondt{1} 2; first auto."
    assert by_id["procedure_case_guard_1_2"]["tactic"] == "case: (x \\in xs)."
    assert by_id["procedure_splitwhile_frontier"]["tactic"].startswith(
        "splitwhile{1} 3:"
    )
    assert by_id["procedure_while_live"]["tactic"] == "while (={i})."
    assert by_id["procedure_rnd_coupling"]["tactic"] == (
        "rnd (fun x => x + k) (fun x => x - k)."
    )


def test_procedure_body_menu_items_surface_asymmetric_region_neutrally() -> None:
    items = procedure_body_menu_items({
        "procedure_body_frontend": {
            "available": True,
            "statement_types": ["ASSIGN"],
            "has_sim": True,
            "live_state_summary": {"post_live_vars": ["c1", "badi"]},
            "asymmetric_instrumentation_region": {
                "available": True,
                "instrumented_side": "right",
                "shared_written_vars": ["c1"],
                "right_extra_written_vars": ["badi"],
                "proof_relevant_extra_vars": ["badi"],
                "live_fact_budget": {
                    "required_visible_vars": ["c1", "badi"],
                    "proof_relevant_extra_vars": ["badi"],
                },
                "why": "shared core plus one-sided extra state",
            },
        },
    })
    by_id = {item["id"]: item for item in items}

    info = by_id["procedure_asymmetric_instrumentation_map"]
    assert info["action_type"] == "strategy_hint"
    assert info["cost"] == "free"
    assert "badi" in info["tactic"]
    assert info["cost_factors"]["region"]["right_extra_written_vars"] == ["badi"]
    assert (
        "compare live_fact_budget.required_visible_vars"
        in info["preconditions"][-1]
    )
    assert "not a runnable tactic" in info["preconditions"][0]
    assert "one-sided extra state" in by_id["procedure_sim_residual"]["why"]


def test_procedure_body_menu_items_render_result_and_one_sided_maps() -> None:
    items = procedure_body_menu_items({
        "procedure_body_frontend": {
            "available": True,
            "statement_types": ["CALL", "ASSIGN"],
            "result_expression_map": {
                "available": True,
                "relation_shape": "derived_result_mismatch",
                "direct_res_equality_risky": True,
                "left": {"side_index": 1, "expression": "p <> None"},
                "right": {"side_index": 2, "expression": "b"},
            },
            "one_sided_call_site_summary": {
                "available": True,
                "sites": [{
                    "side_index": 1,
                    "statement_order": 1,
                    "procedure": "E.dec",
                }],
                "result_expression_map": {
                    "available": True,
                    "relation_shape": "derived_result_mismatch",
                },
            },
        },
    })
    by_id = {item["id"]: item for item in items}

    result = by_id["procedure_result_expression_map"]
    assert result["action_type"] == "strategy_hint"
    assert result["cost"] == "free"
    assert "p <> None" in result["tactic"]
    assert result["cost_factors"]["direct_res_equality_risky"] is True
    assert "not a runnable tactic" in result["preconditions"][0]

    call = by_id["procedure_one_sided_call_site_map"]
    assert call["action_type"] == "strategy_hint"
    assert call["cost"] == "free"
    assert "E.dec" in call["tactic"]
    assert "side-specific call/ecall" in call["preconditions"][0]


def test_procedure_body_menu_items_render_obligation_and_suffix_maps() -> None:
    items = procedure_body_menu_items({
        "procedure_body_frontend": {
            "available": True,
            "proof_obligation_stack": {
                "available": True,
                "active_layer": {
                    "layer_kind": "oracle_wrapper_or_boundary",
                    "frontier_role": "oracle_obligation_source",
                    "procedure": "CPA_CCA_Orcls(O).enc",
                    "statement_order": 5,
                },
                "layers": [{
                    "layer_kind": "abstract_adversary_frontier",
                    "procedure": "A(O).distinguish",
                    "statement_order": 1,
                }],
                "bulk_lowering_risks": [
                    "bulk inline may collapse adversary/oracle layers",
                ],
                "strategy_boundary": "orientation map only",
            },
            "control_suffix_legality": {
                "available": True,
                "active_regions": [{
                    "kind": "loop_frontier",
                    "side_index": 1,
                    "statement_order": 9,
                    "is_suffix_frontier": False,
                }],
                "tactic_legality": [{
                    "tactic_family": "while",
                    "side_index": 1,
                    "statement_order": 9,
                    "status": "blocked_by_suffix",
                    "suffix_blockers": [{"kind": "ASSIGN", "statement_order": 10}],
                }],
                "why": "control tactics are phase-sensitive",
            },
        },
    })
    by_id = {item["id"]: item for item in items}

    stack = by_id["procedure_proof_obligation_stack_map"]
    assert stack["action_type"] == "strategy_hint"
    assert stack["cost"] == "free"
    assert "CPA_CCA_Orcls(O).enc" in stack["tactic"]
    assert "not a runnable tactic" in stack["preconditions"][0]
    assert stack["cost_factors"]["active_layer"]["statement_order"] == 5

    suffix = by_id["procedure_control_suffix_legality"]
    assert suffix["action_type"] == "strategy_hint"
    assert suffix["cost"] == "free"
    assert "while@1:9=blocked_by_suffix" in suffix["tactic"]
    assert "blocked control actions" in suffix["preconditions"][1]
    assert suffix["cost_factors"]["tactic_legality"][0]["status"] == (
        "blocked_by_suffix"
    )


def test_procedure_body_menu_items_render_one_sided_sampling_residual_map() -> None:
    items = procedure_body_menu_items({
        "procedure_body_frontend": {
            "available": True,
            "statement_types": ["SAMPLE"],
            "one_sided_sampling_residual_map": {
                "available": True,
                "risk_kind": "quantified_coupling_residual_after_one_sided_sample",
                "samples": [{
                    "var": "t1",
                    "side_index": 2,
                    "distribution": "dtag",
                    "statement_order": 1,
                }],
                "universal_witnesses": ["t0_0"],
                "why": "one-sided sample with quantified residual",
            },
        },
    })

    by_id = {item["id"]: item for item in items}
    residual = by_id["procedure_one_sided_sampling_residual_map"]
    assert residual["action_type"] == "strategy_hint"
    assert residual["cost"] == "free"
    assert "t1{2} <$ dtag" in residual["tactic"]
    assert "not a runnable tactic" in residual["preconditions"][0]
    assert residual["cost_factors"]["risk_kind"] == (
        "quantified_coupling_residual_after_one_sided_sample"
    )


def test_procedure_body_menu_items_render_sample_coupling_budget_map() -> None:
    items = procedure_body_menu_items({
        "procedure_body_frontend": {
            "available": True,
            "statement_types": ["SAMPLE", "ASSIGN"],
            "has_wp": True,
            "has_residual_close": True,
            "sample_coupling_budget": {
                "available": True,
                "wp_auto_hazard": True,
                "paired_samples": [{
                    "left_sample": {"var": "t0", "side_index": 1},
                    "right_sample": {"var": "t1", "side_index": 2},
                    "same_distribution": True,
                    "distribution_leaf": "dtag",
                    "sample_vars": ["t0", "t1"],
                }],
                "required_visible_vars": ["t0", "t1", "badi"],
                "proof_relevant_extra_vars": ["badi"],
                "strategy_boundary": "sample budget only",
            },
        },
    })

    by_id = {item["id"]: item for item in items}
    budget = by_id["procedure_sample_coupling_budget_map"]
    assert budget["action_type"] == "strategy_hint"
    assert budget["cost"] == "free"
    assert "t0{1}/t1{2} <$ dtag" in budget["tactic"]
    assert "not a runnable tactic" in budget["preconditions"][0]
    assert budget["cost_factors"]["wp_auto_hazard"] is True

    wp = by_id["procedure_wp_frontier"]
    assert "sample/coupling budget" in wp["why"]
    assert "procedure_sample_coupling_budget_map" in wp["preconditions"][0]

    auto = by_id["procedure_auto_residual"]
    assert "sample coupling budget" in auto["preconditions"][0]


def test_procedure_surface_map_menu_items_render_loop_partition_map() -> None:
    items = procedure_surface_map_menu_items({
        "procedure_body_frontend": {
            "available": True,
            "loop_partition_summary": {
                "available": True,
                "shape": "left_single_loop_right_partitioned_loops",
                "loop_counts_by_side": {"left": 1, "right": 2},
                "partition_signals": ["iterator", "cat", "filter"],
                "native_ast_queries": [{
                    "query": "iter cat",
                    "action": "-search-skeleton 'iter cat'",
                }],
                "strategy_boundary": "loop partition map only",
            },
        },
    })

    by_id = {item["id"]: item for item in items}
    loop_map = by_id["procedure_loop_partition_map"]
    assert loop_map["action_type"] == "strategy_hint"
    assert loop_map["cost"] == "free"
    assert "left_single_loop_right_partitioned_loops" in loop_map["tactic"]
    assert "not a runnable tactic" in loop_map["preconditions"][0]
    assert "-search-skeleton 'iter cat'" in loop_map["preconditions"][2]
    assert loop_map["cost_factors"]["native_ast_queries"][0]["query"] == "iter cat"


def test_procedure_body_menu_items_render_residual_side_condition_pack() -> None:
    items = procedure_body_menu_items({
        "procedure_body_frontend": {
            "available": True,
            "residual_side_condition_packs": [{
                "kind": "finite_counter_residual",
                "candidate_lemmas": ["C.ofintdK", "C.gt0_max_counter"],
            }, {
                "kind": "map_membership_residual",
                "candidate_lemmas": ["domE", "mem_set"],
            }],
        },
    })
    by_id = {item["id"]: item for item in items}

    pack = by_id["procedure_residual_side_condition_pack"]
    assert pack["tactic"] == (
        "auto => />; smt(C.ofintdK C.gt0_max_counter domE mem_set)."
    )
    assert pack["action_type"] == "strategy_hint"


def test_sampling_ordering_helpers_and_diagnostics() -> None:
    obligations = [
        {
            "left_sample": {
                "var": "s",
                "side_index": 1,
                "distribution_leaf": "dS",
                "statement_order": 2,
            },
            "right_sample": {
                "var": "t",
                "side_index": 2,
                "distribution_leaf": "dS",
                "statement_order": 1,
            },
            "same_distribution": True,
        },
        {
            "left_sample": {
                "var": "r",
                "side_index": 1,
                "distribution_leaf": "dR",
                "statement_order": 1,
            },
            "right_sample": {},
            "same_distribution": False,
        },
    ]

    assert has_paired_and_one_sided_sampling(obligations) is True
    diagnostics = sampling_ordering_diagnostics({
        "procedure_body_frontend": {"sampling_obligations": obligations},
    })
    assert diagnostics[0]["code"] == "proof_ir.sampling_pair_before_one_sided"
    assert "paired same-distribution" in diagnostics[0]["message"]


def test_sampling_diagnostics_include_one_sided_residual_map() -> None:
    diagnostics = sampling_ordering_diagnostics({
        "procedure_body_frontend": {
            "one_sided_sampling_residual_map": {
                "available": True,
                "samples": [{
                    "var": "t1",
                    "side_index": 2,
                    "distribution": "dtag",
                }],
                "universal_witnesses": ["t0_0"],
            },
        },
    })

    assert diagnostics[0]["code"] == "proof_ir.one_sided_sampling_residual"
    assert "leftover coupling debt" in diagnostics[0]["message"]


def test_preferred_sampling_family_prioritizes_affine_over_identity() -> None:
    family = preferred_sampling_family([
        {"family": "identity", "tactic_template": "rnd."},
        {"family": "translation_or_affine", "tactic_template": "rnd affine."},
    ])

    assert family["family"] == "translation_or_affine"
