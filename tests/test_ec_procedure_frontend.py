"""Tests for procedure/control-flow frontend classification."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from core.easycrypt.analysis.ec_procedure_frontend import (  # noqa: E402
    build_procedure_body_frontend,
    case_condition_for_tactic,
    guard_condition,
    looks_like_wrapper_call,
    procedure_residual_side_condition_packs,
)


def test_procedure_frontend_orders_prefix_before_loop() -> None:
    frontend = build_procedure_body_frontend(
        parsed={
            "goal_type": "pRHL",
            "post": "post = ={x, i} /\\ bad{1} = bad{2}",
            "suggested_tactics": ["wp.", "while (...)."],
        },
        goal_type="pRHL",
        program_ir={
            "statements": [
                {
                    "side": "left",
                    "order": 1,
                    "kind": "ASSIGN",
                    "statement": "x <- a;",
                    "statement_path": "1",
                    "top_level": True,
                    "vars_written": ["x"],
                },
                {
                    "side": "left",
                    "order": 2,
                    "kind": "WHILE",
                    "statement": "while (i < n) {",
                    "statement_path": "2",
                    "top_level": True,
                    "vars_read": ["i", "n"],
                },
                {
                    "side": "right",
                    "order": 1,
                    "kind": "ASSIGN",
                    "statement": "x <- a;",
                    "statement_path": "1",
                    "top_level": True,
                    "vars_written": ["x"],
                },
                {
                    "side": "right",
                    "order": 2,
                    "kind": "WHILE",
                    "statement": "while (i < n) {",
                    "statement_path": "2",
                    "top_level": True,
                    "vars_read": ["i", "n"],
                },
            ],
        },
        goal_text="",
    )

    assert frontend["has_loop"] is True
    assert frontend["has_straight_line_prefix"] is True
    plan = frontend["frontier_plan"]
    assert plan["frontier_kind"] == "straight_line_prefix_before_loop_frontier"
    assert plan["next_structural_region"]["kind"] == "loop_frontier"
    assert any("loop invariant" in item for item in plan["primary_passes"])


def test_procedure_frontend_surfaces_sampling_obligations() -> None:
    frontend = build_procedure_body_frontend(
        parsed={
            "goal_type": "pRHL",
            "post": "post = t{2} = s{1} + mask{2}",
            "suggested_tactics": ["rnd.", "wp."],
        },
        goal_type="pRHL",
        program_ir={
            "statements": [
                {
                    "side": "left",
                    "order": 1,
                    "kind": "SAMPLE",
                    "statement": "s <$ dT;",
                    "statement_path": "1",
                    "vars_written": ["s"],
                },
                {
                    "side": "right",
                    "order": 1,
                    "kind": "SAMPLE",
                    "statement": "t <$ dT;",
                    "statement_path": "1",
                    "vars_written": ["t"],
                },
            ],
        },
        goal_text="",
    )

    assert frontend["has_sample"] is True
    assert frontend["has_sampling_obligation"] is True
    obligation = frontend["sampling_obligations"][0]
    assert obligation["same_distribution"] is True
    assert obligation["relation_motif"]["motif"] == "translation_or_affine"
    assert frontend["frontier_plan"]["frontier_kind"] == "sample_frontier"


def test_procedure_frontend_surfaces_one_sided_sampling_residual() -> None:
    frontend = build_procedure_body_frontend(
        parsed={
            "goal_type": "pRHL",
            "post": (
                "post = forall (t0_0 : tag), t0_0 \\in dtag => "
                "t0_0 = t1{2} => badi{2}"
            ),
            "suggested_tactics": ["rnd{2}.", "auto."],
        },
        goal_type="pRHL",
        program_ir={
            "statements": [{
                "side": "right",
                "side_index": 2,
                "order": 1,
                "kind": "SAMPLE",
                "statement": "t1 <$ dtag;",
                "statement_path": "1",
                "top_level": True,
                "vars_written": ["t1"],
                "distribution": "dtag",
            }],
        },
        goal_text="",
    )

    residual = frontend["one_sided_sampling_residual_map"]
    assert residual["available"] is True
    assert residual["risk_kind"] == (
        "quantified_coupling_residual_after_one_sided_sample"
    )
    assert residual["samples"][0]["var"] == "t1"
    assert residual["samples"][0]["side_index"] == 2
    assert residual["universal_witnesses"] == ["t0_0"]
    assert frontend["has_one_sided_sampling_residual_map"] is True


def test_procedure_frontend_surfaces_sample_coupling_budget_before_wp() -> None:
    frontend = build_procedure_body_frontend(
        parsed={
            "goal_type": "pRHL",
            "post": "post = t0{1} = t1{2} /\\ badi{2}",
            "suggested_tactics": ["wp.", "auto."],
        },
        goal_type="pRHL",
        program_ir={
            "statements": [
                {
                    "side": "left",
                    "side_index": 1,
                    "order": 1,
                    "kind": "SAMPLE",
                    "statement": "t0 <$ dtag;",
                    "statement_path": "1",
                    "top_level": True,
                    "vars_written": ["t0"],
                    "distribution": "dtag",
                },
                {
                    "side": "right",
                    "side_index": 2,
                    "order": 1,
                    "kind": "SAMPLE",
                    "statement": "t1 <$ dtag;",
                    "statement_path": "1",
                    "top_level": True,
                    "vars_written": ["t1"],
                    "distribution": "dtag",
                },
                {
                    "side": "left",
                    "side_index": 1,
                    "order": 2,
                    "kind": "ASSIGN",
                    "statement": "c1 <- c;",
                    "statement_path": "2",
                    "top_level": True,
                    "vars_written": ["c1"],
                },
                {
                    "side": "right",
                    "side_index": 2,
                    "order": 2,
                    "kind": "ASSIGN",
                    "statement": "c1 <- c;",
                    "statement_path": "2",
                    "top_level": True,
                    "vars_written": ["c1"],
                },
                {
                    "side": "right",
                    "side_index": 2,
                    "order": 3,
                    "kind": "ASSIGN",
                    "statement": "badi <- badi || test;",
                    "statement_path": "3",
                    "top_level": True,
                    "vars_written": ["badi"],
                    "vars_read": ["badi", "test"],
                },
            ],
        },
        goal_text="",
    )

    budget = frontend["sample_coupling_budget"]
    assert budget["available"] is True
    assert budget["paired_samples"][0]["left_sample"]["var"] == "t0"
    assert budget["paired_samples"][0]["right_sample"]["var"] == "t1"
    assert budget["paired_samples"][0]["same_distribution"] is True
    assert budget["proof_relevant_extra_vars"] == ["badi"]
    assert budget["wp_auto_hazard"] is True
    assert frontend["current_region_summary"]["sample_coupling_budget"]["available"]
    assert frontend["has_sample_coupling_budget"] is True


def test_procedure_frontend_extracts_branch_guard_and_conseq_shape() -> None:
    frontend = build_procedure_body_frontend(
        parsed={
            "goal_type": "pRHL",
            "post": "post = x{1} = x{2} => y{1} = y{2}",
            "suggested_tactics": ["wp."],
        },
        goal_type="pRHL",
        program_ir={
            "statements": [
                {
                    "side": "left",
                    "order": 1,
                    "kind": "IF",
                    "statement": "if (x \\in xs) {",
                    "statement_path": "1",
                    "top_level": True,
                }
            ],
        },
        goal_text="",
    )

    assert frontend["has_branch"] is True
    assert frontend["has_conseq_shape"] is True
    assert frontend["branch_guards"][0]["condition"] == "x \\in xs"
    assert frontend["structured_regions"][0]["kind"] == "branch_frontier"


def test_procedure_frontend_summarizes_asymmetric_instrumentation() -> None:
    frontend = build_procedure_body_frontend(
        parsed={
            "goal_type": "pRHL",
            "pre": "pre = i{2} = nth0",
            "post": "post = c1{1} = c1{2} /\\ badi{2}",
            "suggested_tactics": ["sim.", "wp."],
        },
        goal_type="pRHL",
        program_ir={
            "statements": [
                {
                    "side": "left",
                    "order": 1,
                    "kind": "ASSIGN",
                    "statement": "c1 <- c;",
                    "statement_path": "1",
                    "top_level": True,
                    "vars_written": ["c1"],
                    "vars_read": ["c"],
                },
                {
                    "side": "right",
                    "order": 1,
                    "kind": "ASSIGN",
                    "statement": "c1 <- c;",
                    "statement_path": "1",
                    "top_level": True,
                    "vars_written": ["c1"],
                    "vars_read": ["c"],
                },
                {
                    "side": "right",
                    "order": 2,
                    "kind": "ASSIGN",
                    "statement": "badi <- badi || test;",
                    "statement_path": "2",
                    "top_level": True,
                    "vars_written": ["badi"],
                    "vars_read": ["badi", "test"],
                },
            ],
        },
        goal_text="",
    )

    region = frontend["asymmetric_instrumentation_region"]
    assert region["available"] is True
    assert region["instrumented_side"] == "right"
    assert region["shared_written_vars"] == ["c1"]
    assert region["right_extra_written_vars"] == ["badi"]
    assert region["proof_relevant_extra_vars"] == ["badi"]
    assert region["live_fact_budget"]["required_visible_vars"] == ["c1", "badi"]
    assert region["live_fact_budget"]["coverage_question"].startswith(
        "Does the next seq/call/while invariant"
    )
    assert frontend["live_state_summary"]["post_live_vars"] == ["c1", "badi"]


def test_procedure_frontend_summarizes_loop_partition_shape() -> None:
    frontend = build_procedure_body_frontend(
        parsed={
            "goal_type": "pRHL",
            "pre": "pre = ={xs}",
            "post": "post = iter (xs1 ++ xs2) = iter xs",
            "suggested_tactics": ["while (...)."],
        },
        goal_type="pRHL",
        program_ir={
            "statements": [
                {
                    "side": "left",
                    "order": 1,
                    "kind": "WHILE",
                    "statement": "while (0 < size xs) {",
                    "statement_path": "1",
                    "top_level": True,
                },
                {
                    "side": "right",
                    "order": 1,
                    "kind": "WHILE",
                    "statement": "while (0 < size (List.filter p xs)) {",
                    "statement_path": "1",
                    "top_level": True,
                },
                {
                    "side": "right",
                    "order": 2,
                    "kind": "WHILE",
                    "statement": "while (0 < size (List.filter q xs)) {",
                    "statement_path": "2",
                    "top_level": True,
                },
            ],
        },
        goal_text="post = iter (List.filter p xs ++ List.filter q xs) = iter xs",
    )

    summary = frontend["loop_partition_summary"]
    assert frontend["has_loop_partition_summary"] is True
    assert summary["shape"] == "left_single_loop_right_partitioned_loops"
    assert summary["loop_counts_by_side"] == {"left": 1, "right": 2}
    assert "filter" in summary["partition_signals"]
    assert "cat" in summary["partition_signals"]
    assert summary["native_ast_queries"][0]["query"] == "iter cat"


def test_procedure_frontend_surfaces_result_and_one_sided_call_maps() -> None:
    frontend = build_procedure_body_frontend(
        parsed={
            "goal_type": "pRHL",
            "post": "post = ={res}",
            "suggested_tactics": ["sim.", "wp."],
        },
        goal_type="pRHL",
        program_ir={
            "statements": [
                {
                    "side": "left",
                    "order": 1,
                    "kind": "CALL",
                    "statement": "p <@ E.dec(k, c);",
                    "procedure": "E.dec",
                    "statement_path": "1",
                    "top_level": True,
                    "vars_written": ["p"],
                },
                {
                    "side": "left",
                    "order": 2,
                    "kind": "ASSIGN",
                    "statement": "res <- p <> None;",
                    "statement_path": "2",
                    "top_level": True,
                    "vars_written": ["res"],
                    "vars_read": ["p"],
                },
                {
                    "side": "right",
                    "order": 1,
                    "kind": "ASSIGN",
                    "statement": "res <- b;",
                    "statement_path": "1",
                    "top_level": True,
                    "vars_written": ["res"],
                    "vars_read": ["b"],
                },
            ],
        },
        goal_text="",
    )

    result_map = frontend["result_expression_map"]
    assert result_map["available"] is True
    assert result_map["relation_shape"] == "derived_result_mismatch"
    assert result_map["direct_res_equality_risky"] is True
    assert result_map["left"]["expression"] == "p <> None"
    assert result_map["right"]["expression"] == "b"

    call_map = frontend["one_sided_call_site_summary"]
    assert call_map["available"] is True
    assert call_map["sites"][0]["procedure"] == "E.dec"
    assert call_map["sites"][0]["one_sided_tactic_family"] == "call{1}/ecall{1}"
    assert call_map["result_expression_map"]["relation_shape"] == (
        "derived_result_mismatch"
    )
    assert frontend["has_result_expression_map"] is True
    assert frontend["has_one_sided_call_site_summary"] is True


def test_procedure_frontend_maps_obligation_stack_without_recipe() -> None:
    frontend = build_procedure_body_frontend(
        parsed={
            "goal_type": "pRHL",
            "post": "post = UFCMA_li.badi{2}",
            "suggested_tactics": ["wp.", "call (_: ...)."],
        },
        goal_type="pRHL",
        program_ir={
            "statements": [
                {
                    "side": "left",
                    "order": 1,
                    "kind": "CALL",
                    "statement": "b <@ A(O).distinguish();",
                    "procedure": "A(O).distinguish",
                    "call_boundary_kind": "abstract_adversary_call",
                    "frontier_role": "current_frontier",
                    "is_frontier_call": True,
                    "top_level": True,
                },
                {
                    "side": "left",
                    "order": 2,
                    "kind": "CALL",
                    "statement": "c <@ CPA_CCA_Orcls(O).enc(n, a, m);",
                    "procedure": "CPA_CCA_Orcls(O).enc",
                    "call_boundary_kind": "oracle_call",
                    "frontier_role": "oracle_obligation_source",
                    "top_level": True,
                },
                {
                    "side": "right",
                    "order": 2,
                    "kind": "CALL",
                    "statement": "tt <@ UFCMA_li.set_bad1i(lt);",
                    "procedure": "UFCMA_li.set_bad1i",
                    "frontier_role": "nested_non_frontier",
                    "top_level": True,
                },
            ],
        },
        goal_text="",
    )

    stack = frontend["proof_obligation_stack"]
    assert stack["available"] is True
    layer_kinds = [layer["layer_kind"] for layer in stack["layers"]]
    assert "abstract_adversary_frontier" in layer_kinds
    assert "oracle_wrapper_or_boundary" in layer_kinds
    assert "instrumentation_or_bad_event_call" in layer_kinds
    assert stack["active_layer"]["frontier_role"] == "current_frontier"
    assert stack["epistemic_status"] == "structural_frontier_map_not_verified_tactic"
    assert frontend["has_proof_obligation_stack"] is True


def test_procedure_frontend_surfaces_bad_event_candidates_neutrally() -> None:
    frontend = build_procedure_body_frontend(
        parsed={
            "goal_type": "pRHL",
            "pre": (
                "pre = !MACa.SUF_CMA.SUF_Wrap.win{2} /\\ "
                "CTXT_Wrap.win{1} => MACa.SUF_CMA.SUF_Wrap.win{2}"
            ),
            "post": "post = CTXT_Wrap.win{1} => MACa.SUF_CMA.SUF_Wrap.win{2}",
            "suggested_tactics": ["sim.", "wp."],
        },
        goal_type="pRHL",
        program_ir={
            "statements": [
                {
                    "side": "left",
                    "side_index": 1,
                    "order": 1,
                    "kind": "ASSIGN",
                    "statement": "CTXT_Wrap.win <- p <> None;",
                    "vars_written": ["CTXT_Wrap.win"],
                    "vars_read": ["p"],
                    "top_level": True,
                },
                {
                    "side": "right",
                    "side_index": 2,
                    "order": 1,
                    "kind": "ASSIGN",
                    "statement": "MACa.SUF_CMA.SUF_Wrap.win <- true;",
                    "vars_written": ["MACa.SUF_CMA.SUF_Wrap.win"],
                    "top_level": True,
                },
            ],
        },
        goal_text="",
    )

    event_map = frontend["bad_event_candidate_map"]
    assert event_map["available"] is True
    names = [item["name"] for item in event_map["primary_candidates"]]
    assert "MACa.SUF_CMA.SUF_Wrap.win" in names
    assert "CTXT_Wrap.win" in names
    assert event_map["fanout_prediction"]["tactic_family"] == (
        "call (_: <event>, <invariant>)"
    )
    assert "event preservation for generated oracle obligations" in (
        event_map["fanout_prediction"]["expected_obligation_classes"]
    )
    assert frontend["has_bad_event_candidate_map"] is True


def test_procedure_frontend_reports_control_suffix_legality() -> None:
    frontend = build_procedure_body_frontend(
        parsed={
            "goal_type": "pRHL",
            "post": "post = ={x}",
            "suggested_tactics": ["while (...).", "wp."],
        },
        goal_type="pRHL",
        program_ir={
            "statements": [
                {
                    "side": "left",
                    "side_index": 1,
                    "order": 1,
                    "kind": "WHILE",
                    "statement": "while (i < n) {",
                    "condition": "i < n",
                    "top_level": True,
                },
                {
                    "side": "left",
                    "side_index": 1,
                    "order": 2,
                    "kind": "ASSIGN",
                    "statement": "x <- y;",
                    "top_level": True,
                },
                {
                    "side": "right",
                    "side_index": 2,
                    "order": 1,
                    "kind": "IF",
                    "statement": "if (bad) {",
                    "condition": "bad",
                    "top_level": True,
                },
            ],
        },
        goal_text="",
    )

    suffix = frontend["control_suffix_legality"]
    assert suffix["available"] is True
    by_family = {
        item["tactic_family"]: item
        for item in suffix["tactic_legality"]
    }
    assert by_family["while"]["status"] == "blocked_by_suffix"
    assert by_family["while"]["suffix_blockers"][0]["kind"] == "ASSIGN"
    assert by_family["rcond/if/case"]["status"] == "guard_obligation_needed"
    assert suffix["branch_obligation_preview"][0]["condition"] == "bad"
    assert frontend["has_control_suffix_legality"] is True


def test_procedure_frontend_classifies_residual_side_condition_packs() -> None:
    packs = procedure_residual_side_condition_packs(
        {
            "post": (
                "post = n \\in dom RO.m /\\ C.ofintd i = c /\\ "
                "nth witness (xs ++ ys) i = x /\\ "
                "size (map f xs) <= size (filter p ys)"
            )
        },
        "",
    )
    by_kind = {pack["kind"]: pack for pack in packs}

    assert "domE" in by_kind["map_membership_residual"]["candidate_lemmas"]
    assert "C.ofintdK" in by_kind["finite_counter_residual"]["candidate_lemmas"]
    assert "nth0" in by_kind["list_index_residual"]["candidate_lemmas"]
    assert "nth_cat" in by_kind["list_index_residual"]["candidate_lemmas"]
    assert "size_cat" in by_kind["list_index_residual"]["candidate_lemmas"]
    assert "nth_map" in by_kind["list_index_residual"]["candidate_lemmas"]
    assert "size_map" in by_kind["list_index_residual"]["candidate_lemmas"]
    assert "size_filter" in by_kind["list_index_residual"]["candidate_lemmas"]
    assert by_kind["list_index_residual"]["native_ast_queries"][0]["query"] == (
        "nth cat"
    )


def test_procedure_helpers_parse_conditions_and_wrapper_calls() -> None:
    guard = {"guard": "if (mem xs x) {"}

    assert guard_condition("while (i < n) {", keyword="while") == "i < n"
    assert case_condition_for_tactic(guard) == "mem xs x"
    assert looks_like_wrapper_call("RealOrcls(Gen(O)).init()")
