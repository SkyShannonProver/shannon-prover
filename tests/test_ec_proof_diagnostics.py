"""Tests for ProofIR-backed compiler diagnostics."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path


import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from core.easycrypt.analysis.ec_proof_diagnostics import (  # noqa: E402
    format_failure_diagnostics,
    proof_ir_failure_diagnostics,
)
from core.easycrypt.analysis.ec_proof_ir import build_proof_ir  # noqa: E402
from core.easycrypt.ec_diagnose import diagnose  # type: ignore  # noqa: E402


def test_call_failure_reports_non_frontier_resource() -> None:
    ir = build_proof_ir(current_goal={
        "goal_type": "pRHL",
        "parsed_goal": {
            "goal_type": "pRHL",
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
            "call_equiv_candidates": {"M.f": ["M_f_equiv"]},
        },
    })

    diagnostics = proof_ir_failure_diagnostics(
        ir,
        latest_tactic="call M_f_equiv.",
        latest_error="cannot apply lemma",
    )

    assert diagnostics[0]["code"] == "proof_ir.failure.call_not_frontier"
    assert diagnostics[0]["evidence"]["lemma"] == "M_f_equiv"
    rendered = format_failure_diagnostics(diagnostics)
    assert "=== ProofIR Diagnostic ===" in rendered
    assert "last-call frontier" in rendered
    assert "Repair:" in rendered


def test_diagnose_includes_proof_ir_block_before_generic_advice() -> None:
    proof_ir = build_proof_ir(current_goal={
        "goal_type": "pRHL",
        "parsed_goal": {
            "goal_type": "pRHL",
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
            "call_equiv_candidates": {"M.f": ["M_f_equiv"]},
        },
    })

    text = diagnose(
        "the given proof-term proves a different judgment",
        "call M_f_equiv.",
        "",
        proof_ir=proof_ir,
    )

    assert "=== ProofIR Diagnostic ===" in text
    assert text.index("=== ProofIR Diagnostic ===") < text.index(
        "General suggestions:"
    )
    assert "matching procedure call still exists" in text


def test_ambient_goal_surfaces_unfoldable_ops_before_smt() -> None:
    with tempfile.TemporaryDirectory() as td:
        session_dir = Path(td)
        (session_dir / "context.ec").write_text(
            "op inv_cpa (x : int) = x = x.\n"
            "op check_plaintext (x : int) = x = x.\n",
            encoding="utf-8",
        )
        ir = build_proof_ir(
            session_dir=session_dir,
            current_goal={
                "goal_type": "ambient",
                "active_goal_text": (
                    "inv_cpa x = check_plaintext x"
                ),
                "parsed_goal": {"goal_type": "ambient"},
            },
        )

    unfoldables = ir["resources"]["handles"]["unfoldable_goal_heads"]
    names = [item["name"] for item in unfoldables]
    assert names[:2] == ["inv_cpa", "check_plaintext"]
    assert unfoldables[0]["smt_argument_role"] == "not_a_lemma_hint"
    assert any(
        item.get("tactic") == "rewrite /inv_cpa."
        for item in ir["candidate_menu"]
    )
    unfold = [
        item for item in ir["candidate_menu"]
        if item.get("tactic") == "rewrite /inv_cpa."
    ][0]
    assert unfold["tactic_family"] == "definition_unfold"
    assert any(
        diag.get("code") == "proof_ir.unfoldable_goal_heads"
        for diag in ir["diagnostics"]
    )


def test_smt_failure_reports_unfoldable_definition_argument() -> None:
    ir = {
        "resources": {
            "handles": {
                "unfoldable_goal_heads": [{
                    "name": "inv_cpa",
                    "declaration_kind": "op",
                    "unfold_tactic": "rewrite /inv_cpa.",
                }],
            },
        },
    }

    diagnostics = proof_ir_failure_diagnostics(
        ir,
        latest_tactic="smt(inv_cpa).",
        latest_error="[error] cannot find lemma `inv_cpa'",
    )

    assert diagnostics[0]["code"] == (
        "proof_ir.failure.smt_argument_is_unfoldable_definition"
    )
    rendered = format_failure_diagnostics(diagnostics)
    assert "rewrite /inv_cpa" in rendered
    assert "not a lemma" in rendered


def test_rewrite_failure_reports_typed_instantiation_needed() -> None:
    ir = {
        "current_layer": "pr",
        "resources": {
            "name_resolution": {
                "items": [{
                    "name": "pr_bridge",
                    "exact_signature_known": True,
                    "requires_instantiation": True,
                    "signature_lookup_action": "-sig pr_bridge",
                }],
            },
            "instantiation_bindings": {
                "items": [{
                    "name": "pr_bridge",
                    "instantiated_templates": [{
                        "tactic": "rewrite (pr_bridge A &m).",
                        "confidence": "high",
                    }],
                }],
            },
            "handles": {},
        },
    }

    diagnostics = proof_ir_failure_diagnostics(
        ir,
        latest_tactic="rewrite pr_bridge.",
        latest_error="wrong number of arguments",
    )

    assert diagnostics[0]["code"] == "proof_ir.failure.rewrite_needs_instantiation"
    assert "rewrite (pr_bridge A &m)." in diagnostics[0]["repairs"][0]


def test_call_failure_prefers_exlim_call_repair_for_value_slots() -> None:
    with tempfile.TemporaryDirectory() as td:
        session = Path(td)
        tool_views = session / "tool_views"
        tool_views.mkdir(exist_ok=True)
        (tool_views / "sig_equ_cc.json").write_text(
            """{
              "schema_version": 1,
              "tool": "sig",
              "kind": "tool_view",
              "ok": true,
              "evidence": {"context": [{"query": {"name": "equ_cc"}}], "raw": []},
              "debug": {"legacy_text": "=== Signature of 'equ_cc' (1 match) ===\\n\\n-- Local.ec:20 (equiv)\\nlocal equiv equ_cc n0 mr0 ms0:\\n  ChaCha.enc ~ EncRnd.cc :\\n    arg{2}.`1 = n0 /\\\\ mr0 = ROin.m{1} /\\\\ ms0 = ROout.m{1}\\n    ==> ={res} /\\\\ mr0 = ROin.m{1} /\\\\ ms0 = ROout.m{1}.\\n"}
            }""",
            encoding="utf-8",
        )
        ir = build_proof_ir(
            session_dir=session,
            current_goal={
                "goal_type": "pRHL",
                "parsed_goal": {
                    "goal_type": "pRHL",
                    "left_statements": [{
                        "pos": 1,
                        "type": "CALL",
                        "text": "c <@ ChaCha.enc(k, n, p);",
                        "procedure": "ChaCha.enc",
                    }],
                    "right_statements": [{
                        "pos": 1,
                        "type": "CALL",
                        "text": "c <@ EncRnd.cc(n, p);",
                        "procedure": "EncRnd.cc",
                    }],
                    "call_equiv_candidates": {"ChaCha.enc": ["equ_cc"]},
                },
            },
        )

    diagnostics = proof_ir_failure_diagnostics(
        ir,
        latest_tactic="call equ_cc.",
        latest_error="cannot infer all placeholders",
    )

    assert diagnostics[0]["code"] == "proof_ir.failure.call_needs_instantiation"
    assert "exlim n{2}, ROin.m{1}, ROout.m{1} => n0 mr0 ms0" in (
        diagnostics[0]["repairs"][0]
    )
    assert "syntax-sensitive" in diagnostics[0]["repairs"][0]


def test_seq_failure_reports_program_ir_planned_slice() -> None:
    ir = build_proof_ir(current_goal={
        "goal_type": "pRHL",
        "parsed_goal": {
            "goal_type": "pRHL",
            "pre": "pre = k{1} = Mem.k{1}",
            "post": "post = ={result}",
            "left_statements": [{
                "pos": 1,
                "pos_path": "1",
                "type": "CALL",
                "text": "t <@ Poly.mac(n, a, c);",
                "procedure": "Poly.mac",
                "vars_written": ["t"],
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
                "vars_written": ["t"],
            }, {
                "pos": 2,
                "pos_path": "2",
                "type": "ASSIGN",
                "text": "z <- t;",
            }],
            "call_equiv_candidates": {"Poly.mac": ["poly_mac1"]},
        },
    })

    diagnostics = proof_ir_failure_diagnostics(
        ir,
        latest_tactic="seq 2 1 : (={result}).",
        latest_error="invalid seq cut",
    )

    assert diagnostics[0]["code"] == "proof_ir.failure.seq_misaligned_with_program_ir"
    assert "seq 1 1" in diagnostics[0]["repairs"][0]
    assert diagnostics[0]["evidence"]["attempted_seq"] == {"left": 2, "right": 1}


def test_call_invariant_failure_prefers_frontier_named_handle() -> None:
    ir = build_proof_ir(current_goal={
        "goal_type": "pRHL",
        "parsed_goal": {
            "goal_type": "pRHL",
            "left_statements": [{
                "pos": 1,
                "pos_path": "1",
                "type": "CALL",
                "text": "t <@ Poly.mac(n, a, c);",
                "procedure": "Poly.mac",
            }],
            "right_statements": [{
                "pos": 1,
                "pos_path": "1",
                "type": "CALL",
                "text": "t <@ D.O.Poly.mac(n, a, c);",
                "procedure": "D.O.Poly.mac",
            }],
            "call_equiv_candidates": {"Poly.mac": ["poly_mac1"]},
        },
    })

    diagnostics = proof_ir_failure_diagnostics(
        ir,
        latest_tactic="call (_: ={res}).",
        latest_error="precondition is too weak",
    )

    assert diagnostics[0]["code"] == (
        "proof_ir.failure.call_invariant_when_named_handle_available"
    )
    assert "call poly_mac1." in diagnostics[0]["repairs"][0]


def test_rewrite_failure_reports_direction_mismatch() -> None:
    ir = build_proof_ir(current_goal={
        "goal_type": "probability",
        "parsed_goal": {
            "goal_type": "probability",
            "prob_form": "eq",
            "lhs_game": "Game1",
            "rhs_game": "Game0",
            "pr_rewrite_candidates": [{
                "name": "pr_Game0_Game1",
                "lhs_game": "Game0",
                "rhs_game": "Game1",
            }],
        },
    })

    diagnostics = proof_ir_failure_diagnostics(
        ir,
        latest_tactic="rewrite pr_Game0_Game1.",
        latest_error="left-hand side of rewrite rule does not match",
    )

    assert diagnostics[0]["code"] == "proof_ir.failure.rewrite_direction_mismatch"
    assert "rewrite -pr_Game0_Game1." in diagnostics[0]["repairs"][0]


def test_byequiv_failure_after_lowering_reports_layer_mismatch() -> None:
    diagnostics = proof_ir_failure_diagnostics(
        {
            "current_layer": "procedure_body",
            "resources": {"name_resolution": {}, "handles": {}},
        },
        latest_tactic="byequiv Game_equiv.",
        latest_error="not an equiv goal",
    )

    assert diagnostics[0]["code"] == "proof_ir.failure.byequiv_after_lowering"
    assert "procedure-body" in diagnostics[0]["cause"]


def test_proc_failure_reports_hidden_program_judgment_shape() -> None:
    diagnostics = proof_ir_failure_diagnostics(
        {
            "current_layer": "ambient_logic",
            "goal_type": "ambient",
            "resources": {
                "program_ir": {"call_sites": []},
                "handles": {},
            },
        },
        latest_tactic="proc.",
        latest_error=(
            "[error] expecting a goal of the form: hoare[S], ehoare[S], "
            "phoare[S], equiv[S]"
        ),
    )

    assert diagnostics[0]["code"] == (
        "proof_ir.failure.proc_needs_exposed_program_judgment"
    )
    assert "named predicate/invariant" in diagnostics[0]["repairs"][0]


def test_sim_failure_reports_asymmetric_instrumentation() -> None:
    diagnostics = proof_ir_failure_diagnostics(
        {
            "resources": {
                "handles": {
                    "procedure_body_frontend": {
                        "asymmetric_instrumentation_region": {
                            "available": True,
                            "instrumented_side": "right",
                            "shared_written_vars": ["c1"],
                            "right_extra_written_vars": ["badi"],
                            "proof_relevant_extra_vars": ["badi"],
                        }
                    }
                }
            }
        },
        latest_tactic="sim.",
        latest_error="cannot infer equalities",
    )

    assert diagnostics[0]["code"] == (
        "proof_ir.failure.sim_blocked_by_asymmetric_instrumentation"
    )
    assert "procedure_asymmetric_instrumentation_map" in diagnostics[0]["repairs"][0]


def test_sim_failure_reports_one_sided_call_site() -> None:
    diagnostics = proof_ir_failure_diagnostics(
        {
            "resources": {
                "handles": {
                    "procedure_body_frontend": {
                        "one_sided_call_site_summary": {
                            "available": True,
                            "sites": [{
                                "side": "left",
                                "side_index": 1,
                                "procedure": "E.dec",
                            }],
                            "post_mentions_result": True,
                            "result_expression_map": {
                                "available": True,
                                "relation_shape": "derived_result_mismatch",
                            },
                        }
                    }
                }
            }
        },
        latest_tactic="sim.",
        latest_error="programs are not synchronized",
    )

    assert diagnostics[0]["code"] == (
        "proof_ir.failure.sim_blocked_by_one_sided_call_site"
    )
    assert "procedure_one_sided_call_site_map" in diagnostics[0]["repairs"][0]


def test_sim_failure_reports_result_expression_bridge() -> None:
    diagnostics = proof_ir_failure_diagnostics(
        {
            "resources": {
                "handles": {
                    "procedure_body_frontend": {
                        "result_expression_map": {
                            "available": True,
                            "direct_res_equality_risky": True,
                            "relation_shape": "derived_result_mismatch",
                            "left": {"expression": "p <> None"},
                            "right": {"expression": "b"},
                        }
                    }
                }
            }
        },
        latest_tactic="sim.",
        latest_error="cannot close result equality",
    )

    assert diagnostics[0]["code"] == (
        "proof_ir.failure.sim_blocked_by_result_expression_bridge"
    )
    assert "procedure_result_expression_map" in diagnostics[0]["repairs"][0]


def test_while_failure_reports_suffix_frontier_issue() -> None:
    diagnostics = proof_ir_failure_diagnostics(
        {
            "resources": {
                "handles": {
                    "procedure_body_frontend": {
                        "frontier_plan": {
                            "frontier_kind": "straight_line_prefix_before_loop_frontier",
                            "region_summary": [{"kind": "loop_frontier"}],
                        },
                        "loop_frontiers": [{"side_index": 1, "statement_order": 9}],
                    }
                }
            }
        },
        latest_tactic="while (={i}).",
        latest_error="invalid last instruction",
    )

    assert diagnostics[0]["code"] == "proof_ir.failure.while_not_at_suffix_frontier"
    assert "wp" in diagnostics[0]["repairs"][0]


def main() -> int:
    test_call_failure_reports_non_frontier_resource()
    test_diagnose_includes_proof_ir_block_before_generic_advice()
    test_ambient_goal_surfaces_unfoldable_ops_before_smt()
    test_smt_failure_reports_unfoldable_definition_argument()
    test_rewrite_failure_reports_typed_instantiation_needed()
    test_call_failure_prefers_exlim_call_repair_for_value_slots()
    test_seq_failure_reports_program_ir_planned_slice()
    test_call_invariant_failure_prefers_frontier_named_handle()
    test_rewrite_failure_reports_direction_mismatch()
    test_byequiv_failure_after_lowering_reports_layer_mismatch()
    test_proc_failure_reports_hidden_program_judgment_shape()
    test_sim_failure_reports_asymmetric_instrumentation()
    test_sim_failure_reports_one_sided_call_site()
    test_sim_failure_reports_result_expression_bridge()
    test_while_failure_reports_suffix_frontier_issue()
    print("PASS test_ec_proof_diagnostics")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
