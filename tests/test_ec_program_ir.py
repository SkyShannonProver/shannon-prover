"""Tests for ProgramIR call-site/frontier analysis."""
from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from core.easycrypt.analysis.ec_program_ir import (  # noqa: E402
    annotate_callable_lemma_handles,
    build_program_ir,
)


def test_program_ir_marks_last_top_level_call_frontier() -> None:
    ir = build_program_ir(
        {
            "left_statements": [{
                "pos": 1,
                "pos_path": "1",
                "type": "CALL",
                "text": "x <@ M.f();",
                "procedure": "M.f",
            }, {
                "pos": 2,
                "pos_path": "2",
                "type": "CALL",
                "text": "y <@ M.g();",
                "procedure": "M.g",
            }],
            "right_statements": [{
                "pos": 1,
                "pos_path": "1",
                "type": "ASSIGN",
                "text": "z <- y;",
            }],
        },
        "pRHL",
    )

    by_proc = {
        site["procedure"]: site
        for site in ir["call_sites"]
    }
    assert by_proc["M.f"]["requires_cut_to_frontier"] is True
    assert by_proc["M.g"]["is_frontier_call"] is True
    assert ir["frontier"]["by_side"]["left"]["procedure"] == "M.g"
    assert ir["frontier"]["frontier_blockers"]["right"]["kind"] == "ASSIGN"
    assert ir["fact_source"] == "pretty_program_text"
    assert ir["authority"] == "pretty_text_fallback"
    assert ir["ec_ground_truth"] is False


def test_program_ir_preserves_ec_native_program_authority() -> None:
    ir = build_program_ir(
        {
            "program_fact_source": "ec_native_program_ast",
            "program_authority": "ec_native_ground_truth",
            "program_authority_rank": 100,
            "program_ec_ground_truth": True,
            "program_native_artifact": "/tmp/native-program.json",
            "left_statements": [{
                "pos": 1,
                "pos_path": "1",
                "type": "CALL",
                "text": "x <@ M.f();",
                "procedure": "M.f",
            }],
            "right_statements": [],
        },
        "pRHL",
    )

    assert ir["fact_source"] == "ec_native_program_ast"
    assert ir["authority"] == "ec_native_ground_truth"
    assert ir["authority_rank"] == 100
    assert ir["ec_ground_truth"] is True
    assert ir["native_artifact"] == "/tmp/native-program.json"


def test_program_ir_annotates_callable_handles_with_frontier_status() -> None:
    ir = build_program_ir(
        {
            "left_statements": [{
                "pos": 1,
                "pos_path": "1",
                "type": "CALL",
                "text": "x <@ M.f();",
                "procedure": "M.f",
            }, {
                "pos": 2,
                "pos_path": "2",
                "type": "ASSIGN",
                "text": "z <- x;",
            }],
            "right_statements": [],
        },
        "pRHL",
    )

    handles = annotate_callable_lemma_handles(
        ir,
        [{"lemma": "M_f_equiv", "procedure": "M.f"}],
    )

    assert handles[0]["callable_now"] is False
    assert handles[0]["requires_cut_to_frontier"] is True
    assert handles[0]["frontier_status"] == "requires_cut"
    assert "wp" in handles[0]["repair_hint"]


def test_program_ir_marks_named_handle_for_same_concrete_call_pair_as_lower_priority() -> None:
    ir = build_program_ir(
        {
            "left_statements": [{
                "pos": 1,
                "pos_path": "1",
                "type": "CALL",
                "text": "c <@ EncRnd.cc(n, p);",
                "procedure": "EncRnd.cc",
            }, {
                "pos": 2,
                "pos_path": "2",
                "type": "ASSIGN",
                "text": "t <- c;",
            }],
            "right_statements": [{
                "pos": 1,
                "pos_path": "1",
                "type": "CALL",
                "text": "c <@ EncRnd.cc(n, p);",
                "procedure": "EncRnd.cc",
            }, {
                "pos": 2,
                "pos_path": "2",
                "type": "ASSIGN",
                "text": "t <- c;",
            }],
        },
        "pRHL",
    )

    handles = annotate_callable_lemma_handles(
        ir,
        [{"lemma": "equ_cc", "procedure": "EncRnd.cc"}],
    )

    assert handles[0]["frontier_status"] == "requires_cut"
    assert handles[0]["same_concrete_call_pairs"]
    assert handles[0]["call_handle_relevance"] == (
        "off_frontier_named_equiv_for_same_concrete_call_pair"
    )
    assert "same-concrete-procedure pair" in handles[0]["frontier_status_detail"]


def test_program_diff_records_aligned_call_pairs_in_statement_order() -> None:
    ir = build_program_ir(
        {
            "left_statements": [{
                "pos": 1,
                "pos_path": "1",
                "type": "CALL",
                "text": "t <@ Poly.mac(n, a, c);",
                "procedure": "Poly.mac",
            }, {
                "pos": 2,
                "pos_path": "2",
                "type": "CALL",
                "text": "c <@ ChaCha.enc(n, p);",
                "procedure": "ChaCha.enc",
            }],
            "right_statements": [{
                "pos": 1,
                "pos_path": "1",
                "type": "CALL",
                "text": "t <@ D(A, O).O.Poly.mac(n, a, c);",
                "procedure": "D.O.Poly.mac",
            }, {
                "pos": 2,
                "pos_path": "2",
                "type": "CALL",
                "text": "c <@ D(A, O).O.ChaCha.enc(n, p);",
                "procedure": "D.O.ChaCha.enc",
            }],
        },
        "pRHL",
    )

    script = ir["program_diff"]["edit_script"]
    call_pairs = [
        step for step in script if step["kind"] == "aligned_call_pair"
    ]
    assert [step["procedure_tail"] for step in call_pairs] == [
        "Poly.mac",
        "ChaCha.enc",
    ]
    assert ir["program_diff"]["summary"]["aligned_call_pair_count"] == 2
    assert ir["program_diff"]["next_action_plan"]["phase_order"][-1][
        "tactic_template"
    ] == "call <matching lemma>."


def test_program_ast_preserves_statement_parent_paths() -> None:
    ir = build_program_ir(
        {
            "left_statements": [{
                "pos": 1,
                "pos_path": "1",
                "type": "IF",
                "text": "if (b) {",
            }, {
                "pos": 2,
                "pos_path": "1.1",
                "type": "CALL",
                "text": "x <@ M.f();",
                "procedure": "M.f",
            }],
            "right_statements": [],
        },
        "pRHL",
    )

    blocks = {
        (block["side"], block["statement_path"]): block
        for block in ir["program_ast"]["blocks"]
    }
    assert blocks[("left", "1.1")]["parent_path"] == "1"
    assert blocks[("left", "1")]["child_paths"] == ["1.1"]
    assert ir["summary"]["program_ast_block_count"] == 2


def test_edit_script_v2_emits_wrapper_open_slice() -> None:
    ir = build_program_ir(
        {
            "left_statements": [{
                "pos": 1,
                "pos_path": "1",
                "type": "CALL",
                "text": "c <@ GenWrapper.enc(n, p);",
                "procedure": "GenWrapper.enc",
            }],
            "right_statements": [{
                "pos": 1,
                "pos_path": "1",
                "type": "CALL",
                "text": "c <@ D(A, O).O.ChaCha.enc(n, p);",
                "procedure": "D.O.ChaCha.enc",
            }],
        },
        "pRHL",
    )

    edit_v2 = ir["program_diff"]["edit_script_v2"]
    assert edit_v2["summary"]["wrapper_open_slice_count"] == 1
    wrapper = edit_v2["next_slice"]
    assert wrapper["kind"] == "wrapper_open_slice"
    assert wrapper["requires_targeted_inline"] is True
    assert wrapper["phase_order"][0]["kind"] == "open_one_wrapper"
    assert wrapper["phase_order"][0]["tactic_hint"] == "inline GenWrapper.enc."
    assert wrapper["expected_next"]["kind"] == "open_one_wrapper"


def test_handle_action_plan_specializes_frontier_exposure_then_call() -> None:
    ir = build_program_ir(
        {
            "left_statements": [{
                "pos": 1,
                "pos_path": "1",
                "type": "CALL",
                "text": "t <@ Poly.mac(n, a, c);",
                "procedure": "Poly.mac",
            }, {
                "pos": 2,
                "pos_path": "2",
                "type": "ASSIGN",
                "text": "z <- t;",
            }],
            "right_statements": [{
                "pos": 1,
                "pos_path": "1",
                "type": "CALL",
                "text": "t <@ D.O.Poly.mac(n, a, c);",
                "procedure": "D.O.Poly.mac",
            }, {
                "pos": 2,
                "pos_path": "2",
                "type": "ASSIGN",
                "text": "z <- t;",
            }],
        },
        "pRHL",
    )

    handles = annotate_callable_lemma_handles(
        ir,
        [{"lemma": "poly_mac1", "procedure": "Poly.mac"}],
    )

    plan = handles[0]["program_action_plans"][0]
    actions = plan["phase_order"]
    assert actions[0]["kind"] == "expose_call_pair_frontier"
    assert actions[0]["tactic_hint"].startswith("seq 1 1")
    assert actions[0]["left_suffix_statement_count"] == 1
    assert actions[0]["right_suffix_statement_count"] == 1
    assert actions[-1]["tactic_template"] == "call poly_mac1."
    assert handles[0]["program_edit_script_v2"][0]["phase_order"][-1][
        "tactic_template"
    ] == "call poly_mac1."
    assert "seq 1 1" in handles[0]["repair_hint"]


def test_single_side_frontier_exposure_gets_seq_order_hint() -> None:
    ir = build_program_ir(
        {
            "left_statements": [{
                "pos": 1,
                "pos_path": "1",
                "type": "CALL",
                "text": "t <@ Poly.mac(n, a, c);",
                "procedure": "Poly.mac",
            }, {
                "pos": 2,
                "pos_path": "2",
                "type": "ASSIGN",
                "text": "z <- t;",
            }],
            "right_statements": [],
        },
        "pRHL",
    )

    handles = annotate_callable_lemma_handles(
        ir,
        [{"lemma": "poly_mac1", "procedure": "Poly.mac"}],
    )

    action = handles[0]["program_action_plans"][0]["phase_order"][0]
    assert action["kind"] == "expose_last_call_frontier"
    assert action["tactic_hint"].startswith("seq 1 0")
    assert action["statement_order"] == 1
    assert action["suffix_statement_count"] == 1


def test_asymmetric_oracle_prefix_stays_secondary_to_call_site_split() -> None:
    ir = build_program_ir(
        {
            "pre": "pre = k{1} = Mem.k{1} /\\ Mem.k{1} = IndBlock.k{2}",
            "post": (
                "post = (n{1}, a{1}, c0{1}, t{1}) = "
                "(n{2}, a{2}, c{2}, t{2}) /\\ c0{1} = c{2}"
            ),
            "left_statements": [{
                "pos": 1,
                "pos_path": "1",
                "type": "CALL",
                "text": "t' <@ Poly.mac(n, a, c0);",
                "procedure": "Poly.mac",
                "vars_written": ["t'"],
            }, {
                "pos": 2,
                "pos_path": "2",
                "type": "ASSIGN",
                "text": "result <- true;",
                "vars_written": ["result"],
            }, {
                "pos": 3,
                "pos_path": "3",
                "type": "ASSIGN",
                "text": "n <- n;",
                "vars_written": ["n"],
            }, {
                "pos": 4,
                "pos_path": "4",
                "type": "ASSIGN",
                "text": "a <- a;",
                "vars_written": ["a"],
            }, {
                "pos": 5,
                "pos_path": "5",
                "type": "ASSIGN",
                "text": "c0 <- c0;",
                "vars_written": ["c0"],
            }],
            "right_statements": [{
                "pos": 1,
                "pos_path": "1",
                "type": "CALL",
                "text": "t <@ D.O.Poly.mac(n, a, c);",
                "procedure": "D.O.Poly.mac",
                "vars_written": ["t"],
            }, {
                "pos": 2,
                "pos_path": "2",
                "type": "ASSIGN",
                "text": "result <- true;",
                "vars_written": ["result"],
            }, {
                "pos": 3,
                "pos_path": "3",
                "type": "ASSIGN",
                "text": "n <- n;",
                "vars_written": ["n"],
            }],
        },
        "pRHL",
    )

    plan = ir["program_diff"]["action_plans"][0]
    assert plan["kind"] == "call_site_exposure_plan"
    action = plan["phase_order"][0]
    assert action["kind"] == "expose_call_pair_frontier"
    assert action["tactic_hint"].startswith("seq 1 1 : <invariant preserving")

    asym = [
        plan for plan in ir["program_diff"]["action_plans"]
        if plan["kind"] == "asymmetric_seq_exposure_plan"
    ][0]
    assert asym["proof_intent"] == "full_prefix_post_normalization"
    action = asym["phase_order"][1]
    assert action["kind"] == "expose_asymmetric_prefix"
    assert action["requires_instantiation"] is True
    assert action["tactic_hint"].startswith("seq 5 3 : <full-prefix invariant")
    assert (
        "(n{1}, a{1}, c0{1}, t{1}) = (n{2}, a{2}, c{2}, t{2})"
        in action["invariant_skeleton"]
    )
    assert "c0{1} = c{2}" in action["invariant_skeleton"]
    assert "k{1} = Mem.k{1}" in action["invariant_skeleton"]
    next_slice = ir["program_diff"]["edit_script_v2"]["next_slice"]
    assert next_slice["kind"] == "call_pair_slice"
    assert next_slice["expected_next"]["kind"] == "expose_call_pair_frontier"
    assert next_slice["expected_next"]["tactic"].startswith("seq 1 1 : <")

    handles = annotate_callable_lemma_handles(
        ir,
        [{"lemma": "poly_mac1", "procedure": "Poly.mac"}],
    )
    assert handles[0]["program_action_plans"][0]["kind"] == (
        "call_site_exposure_plan"
    )
    assert "seq 1 1" in handles[0]["repair_hint"]


def test_program_ir_classifies_abstract_adversary_frontier() -> None:
    ir = build_program_ir(
        {
            "left_statements": [{
                "pos": 1,
                "pos_path": "1",
                "type": "CALL",
                "text": "b <@ A(CBC_Oracle(P)).distinguish();",
                "procedure": "A(CBC_Oracle(P)).distinguish",
            }],
            "right_statements": [{
                "pos": 1,
                "pos_path": "1",
                "type": "CALL",
                "text": "b <@ A(CBC_Oracle(P')).distinguish();",
                "procedure": "A(CBC_Oracle(P')).distinguish",
            }],
        },
        "pRHL",
        goal_text=(
            "Current goal\n\n"
            "A(O : RCPA_Oracles) : RCPA_Adversary{-P, -P'}\n"
            "------------------------------------------------------------------------\n"
            "pre = true"
        ),
    )

    left = ir["frontier"]["by_side"]["left"]
    assert left["call_boundary_kind"] == "abstract_adversary_call"
    assert left["frontier_role"] == "oracle_obligation_source"
    assert ir["call_sites"][0]["frontier_role"] == "oracle_obligation_source"


def test_program_ir_uses_abstract_binder_when_parser_drops_functor_args() -> None:
    ir = build_program_ir(
        {
            "left_statements": [{
                "pos": 2,
                "pos_path": "2",
                "type": "CALL",
                "text": "b <@ A(CBC_Oracle(P)).distinguish()",
                "procedure": "A.distinguish",
            }],
            "right_statements": [{
                "pos": 2,
                "pos_path": "2",
                "type": "CALL",
                "text": "b <@ A(CBC_Oracle(P')).distinguish()",
                "procedure": "A.distinguish",
            }],
        },
        "pRHL",
        goal_text=(
            "Current goal\n\n"
            "A(O : RCPA_Oracles) : RCPA_Adversary{-P, -P'}\n"
            "------------------------------------------------------------------------\n"
            "pre = true"
        ),
    )

    left = ir["frontier"]["by_side"]["left"]
    assert left["procedure"] == "A.distinguish"
    assert left["call_boundary_kind"] == "abstract_adversary_call"
    assert left["frontier_role"] == "oracle_obligation_source"


def test_handles_under_adversary_frontier_become_oracle_obligations() -> None:
    ir = build_program_ir(
        {
            "left_statements": [{
                "pos": 1,
                "pos_path": "1",
                "type": "CALL",
                "text": "b <@ A(CBC_Oracle(P)).distinguish();",
                "procedure": "A(CBC_Oracle(P)).distinguish",
            }],
            "right_statements": [{
                "pos": 1,
                "pos_path": "1",
                "type": "CALL",
                "text": "b <@ A(CBC_Oracle(P')).distinguish();",
                "procedure": "A(CBC_Oracle(P')).distinguish",
            }],
        },
        "pRHL",
        goal_text=(
            "Current goal\n\n"
            "A(O : RCPA_Oracles) : RCPA_Adversary{-P, -P'}\n"
            "------------------------------------------------------------------------\n"
            "pre = true"
        ),
    )

    handles = annotate_callable_lemma_handles(
        ir,
        [{
            "lemma": "H0",
            "procedure": "P.f",
            "procedures": ["P.f", "P'.f"],
            "source": "current_goal_hypothesis",
        }],
    )

    assert handles[0]["handle_role"] == "oracle_obligation_handle"
    assert handles[0]["frontier_status"] == "oracle_obligation"
    assert handles[0]["callable_now"] is False
    assert handles[0]["oracle_obligation_source_call_site_ids"]


def main() -> int:
    test_program_ir_marks_last_top_level_call_frontier()
    test_program_ir_annotates_callable_handles_with_frontier_status()
    test_program_ir_marks_named_handle_for_same_concrete_call_pair_as_lower_priority()
    test_program_diff_records_aligned_call_pairs_in_statement_order()
    test_program_ast_preserves_statement_parent_paths()
    test_edit_script_v2_emits_wrapper_open_slice()
    test_handle_action_plan_specializes_frontier_exposure_then_call()
    test_single_side_frontier_exposure_gets_seq_order_hint()
    test_asymmetric_oracle_prefix_stays_secondary_to_call_site_split()
    test_program_ir_classifies_abstract_adversary_frontier()
    test_program_ir_uses_abstract_binder_when_parser_drops_functor_args()
    test_handles_under_adversary_frontier_become_oracle_obligations()
    print("PASS test_ec_program_ir")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
