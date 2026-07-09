"""Tests for static EasyCrypt instantiation binding pass."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from core.easycrypt.analysis.ec_instantiation_binding import (  # noqa: E402
    binding_for_name,
    build_instantiation_bindings,
)


def test_binds_module_and_memory_slots_from_context_and_goal() -> None:
    with tempfile.TemporaryDirectory() as td:
        session = Path(td)
        (session / "context.ec").write_text(
            "declare module A <: Adv.\n"
            "local module RO : Oracle = { }.\n",
            encoding="utf-8",
        )
        bindings = build_instantiation_bindings(
            session_dir=session,
            parsed_goal={
                "goal_type": "probability",
                "lhs_game": "G1(A)",
                "rhs_game": "G2(A)",
                "event": "Pr[G1(A).main() @ &m : res]",
            },
            name_resolution={
                "items": [{
                    "name": "pr_CCP_OCCP",
                    "handle_kind": "pr_rewrite",
                    "tactic_template": "rewrite pr_CCP_OCCP.",
                    "parameter_slots": [{
                        "index": 1,
                        "kind": "module_arg",
                        "name": "A",
                        "type_or_bound": "Adv",
                        "placeholder": "<A_module>",
                    }, {
                        "index": 2,
                        "kind": "memory_arg",
                        "name": "&m",
                        "placeholder": "<m>",
                    }],
                }],
            },
        )

    item = binding_for_name(bindings, "pr_CCP_OCCP")
    assert bindings["summary"]["slots"] == 2
    assert bindings["summary"]["slots_with_candidates"] == 2
    module_slot = item["slots"][0]
    memory_slot = item["slots"][1]
    assert module_slot["candidates"][0]["value"] == "A"
    assert module_slot["candidates"][0]["confidence"] == "high"
    assert memory_slot["candidates"][0]["value"] == "&m"
    assert item["instantiated_templates"][0]["tactic"] == (
        "rewrite (pr_CCP_OCCP A &m)."
    )


def test_goal_functor_argument_is_module_candidate() -> None:
    bindings = build_instantiation_bindings(
        parsed_goal={
            "goal_type": "pRHL",
            "left_statements": [{
                "type": "CALL",
                "text": "c <@ Left(RO).enc(k);",
                "procedure": "Left(RO).enc",
            }],
        },
        name_resolution={
            "items": [{
                "name": "equ_cc",
                "handle_kind": "call_equiv",
                "tactic_template": "call equ_cc.",
                "parameter_slots": [{
                    "index": 1,
                    "kind": "module_arg",
                    "name": "O",
                    "type_or_bound": "Oracle",
                    "placeholder": "<O_module>",
                }],
            }],
        },
    )

    item = binding_for_name(bindings, "equ_cc")
    values = [candidate["value"] for candidate in item["slots"][0]["candidates"]]
    assert "RO" in values
    assert item["instantiated_templates"][0]["tactic"] == "call (equ_cc RO)."


def test_low_confidence_value_slots_do_not_emit_tactic() -> None:
    bindings = build_instantiation_bindings(
        parsed_goal={
            "goal_type": "pRHL",
            "left_statements": [{
                "type": "CALL",
                "text": "c2 <@ ChaCha.enc(k, n, p2);",
                "procedure": "ChaCha.enc",
            }],
            "call_equiv_candidates": {"ChaCha.enc": ["equ_cc"]},
        },
        name_resolution={
            "items": [{
                "name": "equ_cc",
                "handle_kind": "call_equiv",
                "tactic_template": "call equ_cc.",
                "parameter_slots": [{
                    "index": 1,
                    "kind": "value_arg",
                    "name": "n0",
                    "type_or_bound": "",
                    "placeholder": "<n0>",
                }, {
                    "index": 2,
                    "kind": "value_arg",
                    "name": "mr0",
                    "type_or_bound": "",
                    "placeholder": "<mr0>",
                }, {
                    "index": 3,
                    "kind": "value_arg",
                    "name": "ms0",
                    "type_or_bound": "",
                    "placeholder": "<ms0>",
                }],
            }],
        },
    )

    item = binding_for_name(bindings, "equ_cc")
    assert item["instantiated_templates"] == []
    assert all(
        candidate["confidence"] != "high"
        for slot in item["slots"]
        for candidate in slot["candidates"]
    )
    assert "equ_cc" not in [
        candidate["value"]
        for slot in item["slots"]
        for candidate in slot["candidates"]
    ]


def test_value_slots_bind_from_matching_call_arguments_by_stem() -> None:
    bindings = build_instantiation_bindings(
        parsed_goal={
            "goal_type": "pRHL",
            "left_statements": [{
                "type": "CALL",
                "text": "c2 <@ ChaCha.enc(n, mr, ms);",
                "procedure": "ChaCha.enc",
            }],
            "call_equiv_candidates": {"ChaCha.enc": ["equ_cc"]},
        },
        name_resolution={
            "items": [{
                "name": "equ_cc",
                "handle_kind": "call_equiv",
                "procedure": "ChaCha.enc",
                "tactic_template": "call equ_cc.",
                "parameter_slots": [{
                    "index": 1,
                    "kind": "value_arg",
                    "name": "n0",
                    "type_or_bound": "",
                    "placeholder": "<n0>",
                }, {
                    "index": 2,
                    "kind": "value_arg",
                    "name": "mr0",
                    "type_or_bound": "",
                    "placeholder": "<mr0>",
                }, {
                    "index": 3,
                    "kind": "value_arg",
                    "name": "ms0",
                    "type_or_bound": "",
                    "placeholder": "<ms0>",
                }],
            }],
        },
    )

    item = binding_for_name(bindings, "equ_cc")
    assert item["instantiated_templates"][0]["tactic"] == (
        "call (equ_cc n mr ms)."
    )
    assert [slot["selected_candidate"]["value"] for slot in item["slots"]] == [
        "n",
        "mr",
        "ms",
    ]
    assert item["call_elaboration"]["available"] is True
    assert item["call_elaboration"]["tactic_template"] == (
        "exlim n{1}, mr{1}, ms{1} => n0 mr0 ms0; "
        "call (equ_cc n0 mr0 ms0)."
    )
    assert item["call_elaboration"]["lifted_value_arguments"][0][
        "program_expression"
    ] == "n{1}"


def test_value_slots_ignore_functor_arguments_and_read_proc_arguments() -> None:
    bindings = build_instantiation_bindings(
        parsed_goal={
            "goal_type": "pRHL",
            "left_statements": [{
                "type": "CALL",
                "text": "c <@ Left(RO).enc(n0, mr0, ms0);",
                "procedure": "Left(RO).enc",
            }],
        },
        name_resolution={
            "items": [{
                "name": "equ_cc",
                "handle_kind": "call_equiv",
                "procedure": "Left(RO).enc",
                "tactic_template": "call equ_cc.",
                "parameter_slots": [{
                    "index": 1,
                    "kind": "value_arg",
                    "name": "n0",
                    "type_or_bound": "",
                    "placeholder": "<n0>",
                }, {
                    "index": 2,
                    "kind": "value_arg",
                    "name": "mr0",
                    "type_or_bound": "",
                    "placeholder": "<mr0>",
                }, {
                    "index": 3,
                    "kind": "value_arg",
                    "name": "ms0",
                    "type_or_bound": "",
                    "placeholder": "<ms0>",
                }],
            }],
        },
    )

    item = binding_for_name(bindings, "equ_cc")
    assert item["instantiated_templates"][0]["tactic"] == (
        "call (equ_cc n0 mr0 ms0)."
    )
    assert "RO" not in [
        candidate["value"]
        for slot in item["slots"]
        for candidate in slot["candidates"]
    ]


def test_call_elaboration_lifts_dotted_state_arguments_positionally() -> None:
    bindings = build_instantiation_bindings(
        parsed_goal={
            "goal_type": "pRHL",
            "left_statements": [{
                "type": "CALL",
                "text": "c <@ ChaCha.enc(n, ROin.m, ROout.m);",
                "procedure": "ChaCha.enc",
            }],
        },
        name_resolution={
            "items": [{
                "name": "equiv_bridge",
                "handle_kind": "call_equiv",
                "procedure": "ChaCha.enc",
                "tactic_template": "call equiv_bridge.",
                "parameter_slots": [{
                    "index": 1,
                    "kind": "value_arg",
                    "name": "n0",
                    "placeholder": "<n0>",
                }, {
                    "index": 2,
                    "kind": "value_arg",
                    "name": "mr0",
                    "placeholder": "<mr0>",
                }, {
                    "index": 3,
                    "kind": "value_arg",
                    "name": "ms0",
                    "placeholder": "<ms0>",
                }],
            }],
        },
    )

    item = binding_for_name(bindings, "equiv_bridge")
    assert [slot["selected_candidate"]["value"] for slot in item["slots"]] == [
        "n",
        "ROin.m",
        "ROout.m",
    ]
    assert item["call_elaboration"]["tactic_template"] == (
        "exlim n{1}, ROin.m{1}, ROout.m{1} => n0 mr0 ms0; "
        "call (equiv_bridge n0 mr0 ms0)."
    )


def test_call_elaboration_binds_state_snapshots_from_equiv_constraints() -> None:
    bindings = build_instantiation_bindings(
        parsed_goal={
            "goal_type": "pRHL",
            "left_statements": [{
                "type": "CALL",
                "text": "c <@ ChaCha.enc(k, n, p);",
                "procedure": "ChaCha.enc",
            }],
            "right_statements": [{
                "type": "CALL",
                "text": "c <@ EncRnd.cc(n, p);",
                "procedure": "EncRnd.cc",
            }],
        },
        name_resolution={
            "items": [{
                "name": "equ_cc",
                "handle_kind": "call_equiv",
                "procedure": "ChaCha.enc",
                "tactic_template": "call equ_cc.",
                "declaration": (
                    "local equiv equ_cc n0 mr0 ms0: "
                    "ChaCha.enc ~ EncRnd.cc : "
                    "arg{2}.`1 = n0 /\\ "
                    "mr0 = ROin.m{1} /\\ ms0 = ROout.m{1} "
                    "==> ={res} /\\ mr0 = ROin.m{1} /\\ ms0 = ROout.m{1}."
                ),
                "parameter_slots": [{
                    "index": 1,
                    "kind": "value_arg",
                    "name": "n0",
                    "placeholder": "<n0>",
                }, {
                    "index": 2,
                    "kind": "value_arg",
                    "name": "mr0",
                    "placeholder": "<mr0>",
                }, {
                    "index": 3,
                    "kind": "value_arg",
                    "name": "ms0",
                    "placeholder": "<ms0>",
                }],
            }],
        },
    )

    item = binding_for_name(bindings, "equ_cc")
    selected = [slot["selected_candidate"] for slot in item["slots"]]
    assert [candidate["value"] for candidate in selected] == [
        "n",
        "ROin.m",
        "ROout.m",
    ]
    assert selected[1]["source"] == "lemma_precondition.value_slot_equality"
    assert selected[1]["role"] == "state_snapshot_parameter"
    assert item["instantiated_templates"][0]["tactic"] == (
        "call (equ_cc n ROin.m ROout.m)."
    )
    assert item["call_elaboration"]["direct_ecall_template"] == (
        "ecall (equ_cc n{2} ROin.m{1} ROout.m{1})."
    )
    assert item["call_elaboration"]["tactic_template"] == (
        "exlim n{2}, ROin.m{1}, ROout.m{1} => n0 mr0 ms0; "
        "call (equ_cc n0 mr0 ms0)."
    )
    coverage = item["call_elaboration"]["lemma_precondition_coverage"]
    assert coverage["available"] is True
    assert coverage["covered_by_exlim_count"] == 3
    assert coverage["expected_residual_count"] == 0


def test_call_elaboration_precondition_coverage_is_lemma_name_agnostic() -> None:
    bindings = build_instantiation_bindings(
        parsed_goal={
            "goal_type": "pRHL",
            "left_statements": [{
                "type": "CALL",
                "text": "out <@ Stream.enc(k, nonce, msg);",
                "procedure": "Stream.enc",
            }],
            "right_statements": [{
                "type": "CALL",
                "text": "out <@ Random.cc(nonce, msg);",
                "procedure": "Random.cc",
            }],
        },
        name_resolution={
            "items": [{
                "name": "bridge_equiv",
                "handle_kind": "call_equiv",
                "procedure": "Stream.enc",
                "tactic_template": "call bridge_equiv.",
                "declaration": (
                    "local equiv bridge_equiv n0 st0: "
                    "Stream.enc ~ Random.cc : "
                    "arg{2}.`1 = n0 /\\ "
                    "st0 = State.m{1} /\\ "
                    "!n0 \\in Seen.nonces{1} /\\ "
                    "(forall x, x \\in State.m => ok x){1} "
                    "==> ={res} /\\ st0 = State.m{1}."
                ),
                "parameter_slots": [{
                    "index": 1,
                    "kind": "value_arg",
                    "name": "n0",
                    "placeholder": "<n0>",
                }, {
                    "index": 2,
                    "kind": "value_arg",
                    "name": "st0",
                    "placeholder": "<st0>",
                }],
            }],
        },
    )

    item = binding_for_name(bindings, "bridge_equiv")
    assert item["call_elaboration"]["tactic_template"] == (
        "exlim nonce{2}, State.m{1} => n0 st0; "
        "call (bridge_equiv n0 st0)."
    )
    coverage = item["call_elaboration"]["lemma_precondition_coverage"]
    assert coverage["available"] is True
    assert coverage["pre_atom_count"] == 4
    assert coverage["covered_by_exlim_count"] == 2
    assert coverage["expected_residual_count"] == 2
    residual_categories = {
        atom["category"] for atom in coverage["expected_residual_atoms"]
    }
    assert "lifted_value_side_condition" in residual_categories
    assert "state_invariant_requirement" in residual_categories


def test_dotted_goal_module_path_beats_tail_name_match() -> None:
    bindings = build_instantiation_bindings(
        parsed_goal={
            "goal_type": "probability",
            "event": (
                "Pr[RO(MainD).main() @ &m : res] = "
                "Pr[FiniteRO.MainD.main() @ &m : res]"
            ),
        },
        name_resolution={
            "items": [{
                "name": "pr_RO_FinRO_D",
                "handle_kind": "pr_rewrite",
                "tactic_template": "rewrite pr_RO_FinRO_D.",
                "parameter_slots": [{
                    "index": 1,
                    "kind": "module_arg",
                    "name": "MainD",
                    "type_or_bound": "Distinguisher",
                    "placeholder": "<D_module>",
                }, {
                    "index": 2,
                    "kind": "memory_arg",
                    "name": "&m",
                    "placeholder": "<m>",
                }],
            }],
        },
    )

    item = binding_for_name(bindings, "pr_RO_FinRO_D")
    module_candidates = item["slots"][0]["candidates"]
    assert module_candidates[0]["value"] == "FiniteRO.MainD"
    assert module_candidates[0]["confidence"] == "high"
    assert item["instantiated_templates"][0]["tactic"] == (
        "rewrite (pr_RO_FinRO_D FiniteRO.MainD &m)."
    )


def test_pr_rewrite_binds_section_proof_module_unit_and_identity_predicate() -> None:
    bindings = build_instantiation_bindings(
        parsed_goal={
            "goal_type": "probability",
            "raw_text": (
                "Pr[MainD(G2, RO).distinguish() @ &m : res] = "
                "Pr[MainD(G2, FinRO).distinguish() @ &m : res]"
            ),
        },
        name_resolution={
            "items": [{
                "name": "pr_RO_FinRO_D",
                "handle_kind": "pr_rewrite",
                "tactic_template": "rewrite pr_RO_FinRO_D.",
                "declaration": (
                    "lemma pr_RO_FinRO_D "
                    "(dout_ll : forall x, is_lossless (dout x)) "
                    "(D <: FinRO_Distinguisher{-RO, -FRO}) &m (x : unit) "
                    "(p : d_out_t -> bool) : "
                    "Pr[MainD(D,RO).distinguish(x) @ &m : p res] = "
                    "Pr[MainD(D,FinRO).distinguish(x) @ &m : p res]."
                ),
                "parameter_slots": [{
                    "index": 1,
                    "kind": "proof_arg",
                    "name": "dout_ll",
                    "type_or_bound": "forall x, is_lossless (dout x)",
                    "placeholder": "<dout_ll>",
                }, {
                    "index": 2,
                    "kind": "module_arg",
                    "name": "D",
                    "type_or_bound": "FinRO_Distinguisher{-RO, -FRO}",
                    "placeholder": "<D_module>",
                }, {
                    "index": 3,
                    "kind": "memory_arg",
                    "name": "&m",
                    "placeholder": "<m>",
                }, {
                    "index": 4,
                    "kind": "value_arg",
                    "name": "x",
                    "placeholder": "<x>",
                }, {
                    "index": 5,
                    "kind": "value_arg",
                    "name": "p",
                    "type_or_bound": "d_out_t -> bool",
                    "placeholder": "<p>",
                }],
            }],
        },
    )

    item = binding_for_name(bindings, "pr_RO_FinRO_D")
    assert [slot["selected_candidate"]["value"] for slot in item["slots"]] == [
        "_",
        "G2",
        "&m",
        "()",
        "(fun x => x)",
    ]
    assert item["instantiated_templates"][0]["tactic"] == (
        "rewrite (pr_RO_FinRO_D _ G2 &m () (fun x => x)) /=."
    )
    elaboration = item["pr_elaboration"]
    assert elaboration["status"] == "elaborated"
    x_slot = [
        slot for slot in elaboration["slots"]
        if slot["slot"]["name"] == "x"
    ][0]
    assert x_slot["selected_value"] == "()"
    assert x_slot["role"] == "lemma_endpoint_value_argument"
    assert x_slot["belongs_to"] == (
        "lemma_instantiation_not_concrete_procedure_call"
    )
    assert x_slot["canonical_endpoint"] == "MainD(G2, RO).distinguish()"
    separation = elaboration["endpoint_argument_separation"][0]
    assert separation["value_slot"] == "x"
    assert separation["selected_value"] == "()"
    assert separation["concrete_endpoint"] == "MainD(G2, RO).distinguish()"
    assert "distinguish(x)" in separation["lemma_endpoint_template"]
    diagnostic = elaboration["diagnostics"][0]
    assert diagnostic["avoid"] == "MainD(G2, RO).distinguish(())"


def test_pr_rewrite_binds_from_active_goal_text_when_parser_is_shallow() -> None:
    bindings = build_instantiation_bindings(
        parsed_goal={
            "goal_type": "probability",
            "prob_form": "eq",
            "lhs_game": "G1(GenChaChaPoly(OCC(IFinRO)))",
            "rhs_game": "MainD(G2, RO)",
        },
        goal_text=(
            "Current goal\n\n"
            "------------------------------------------------------------------------\n"
            "Pr[MainD(G2, RO).distinguish() @ &m : res] =\n"
            "Pr[MainD(G2, FinRO).distinguish() @ &m : res]"
        ),
        name_resolution={
            "items": [{
                "name": "pr_RO_FinRO_D",
                "handle_kind": "pr_rewrite",
                "tactic_template": "rewrite pr_RO_FinRO_D.",
                "declaration": (
                    "lemma pr_RO_FinRO_D:\n"
                    "  (forall (_ : nonce * C.counter), is_lossless dblock) =>\n"
                    "  forall (D0(G : RO) <: FinRO_Distinguisher{-RO, -FRO}) &m "
                    "(x : unit) (p : bool -> bool),\n"
                    "    Pr[MainD(D0, RO).distinguish(x) @ &m : p res] =\n"
                    "    Pr[MainD(D0, FinRO).distinguish(x) @ &m : p res]."
                ),
                "parameter_slots": [{
                    "index": 1,
                    "kind": "proof_arg",
                    "name": "proof1",
                    "placeholder": "<proof1>",
                }, {
                    "index": 2,
                    "kind": "module_arg",
                    "name": "D0",
                    "type_or_bound": "FinRO_Distinguisher{-RO, -FRO}",
                    "placeholder": "<D0_module>",
                }, {
                    "index": 3,
                    "kind": "memory_arg",
                    "name": "&m",
                    "placeholder": "<m>",
                }, {
                    "index": 4,
                    "kind": "value_arg",
                    "name": "x",
                    "type_or_bound": "unit",
                    "placeholder": "<x>",
                }, {
                    "index": 5,
                    "kind": "value_arg",
                    "name": "p",
                    "type_or_bound": "bool -> bool",
                    "placeholder": "<p>",
                }],
            }],
        },
    )

    item = binding_for_name(bindings, "pr_RO_FinRO_D")
    assert [slot["selected_candidate"]["value"] for slot in item["slots"]] == [
        "_",
        "G2",
        "&m",
        "()",
        "(fun x => x)",
    ]
    assert item["instantiated_templates"][0]["tactic"] == (
        "rewrite (pr_RO_FinRO_D _ G2 &m () (fun x => x)) /=."
    )
    elaboration = item["pr_elaboration"]
    assert elaboration["endpoint_argument_separation"][0]["concrete_endpoint"] == (
        "MainD(G2, RO).distinguish()"
    )
    assert elaboration["diagnostics"][0]["avoid"] == (
        "MainD(G2, RO).distinguish(())"
    )


def test_pr_rewrite_does_not_bind_unit_without_type_evidence() -> None:
    bindings = build_instantiation_bindings(
        parsed_goal={
            "goal_type": "probability",
            "raw_text": (
                "Pr[MainD(G2, RO).distinguish() @ &m : res] = "
                "Pr[MainD(G2, FinRO).distinguish() @ &m : res]"
            ),
        },
        name_resolution={
            "items": [{
                "name": "pr_RO_FinRO_D",
                "handle_kind": "pr_rewrite",
                "tactic_template": "rewrite pr_RO_FinRO_D.",
                "declaration": (
                    "lemma pr_RO_FinRO_D "
                    "(D <: FinRO_Distinguisher{-RO, -FRO}) &m x "
                    "(p : d_out_t -> bool) : "
                    "Pr[MainD(D,RO).distinguish(x) @ &m : p res] = "
                    "Pr[MainD(D,FinRO).distinguish(x) @ &m : p res]."
                ),
                "parameter_slots": [{
                    "index": 1,
                    "kind": "module_arg",
                    "name": "D",
                    "type_or_bound": "FinRO_Distinguisher{-RO, -FRO}",
                    "placeholder": "<D_module>",
                }, {
                    "index": 2,
                    "kind": "memory_arg",
                    "name": "&m",
                    "placeholder": "<m>",
                }, {
                    "index": 3,
                    "kind": "value_arg",
                    "name": "x",
                    "placeholder": "<x>",
                }, {
                    "index": 4,
                    "kind": "value_arg",
                    "name": "p",
                    "type_or_bound": "d_out_t -> bool",
                    "placeholder": "<p>",
                }],
            }],
        },
    )

    item = binding_for_name(bindings, "pr_RO_FinRO_D")
    assert item["instantiated_templates"] == []
    x_slot = [slot for slot in item["slots"] if slot["slot"]["name"] == "x"][0]
    assert all(
        candidate["value"] != "()"
        for candidate in x_slot["candidates"]
    )


def main() -> int:
    test_binds_module_and_memory_slots_from_context_and_goal()
    test_goal_functor_argument_is_module_candidate()
    test_low_confidence_value_slots_do_not_emit_tactic()
    test_value_slots_bind_from_matching_call_arguments_by_stem()
    test_value_slots_ignore_functor_arguments_and_read_proc_arguments()
    test_call_elaboration_lifts_dotted_state_arguments_positionally()
    test_call_elaboration_binds_state_snapshots_from_equiv_constraints()
    test_dotted_goal_module_path_beats_tail_name_match()
    test_pr_rewrite_binds_section_proof_module_unit_and_identity_predicate()
    test_pr_rewrite_binds_from_active_goal_text_when_parser_is_shallow()
    test_pr_rewrite_does_not_bind_unit_without_type_evidence()
    print("PASS test_ec_instantiation_binding")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
