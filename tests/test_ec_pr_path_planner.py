"""Tests for Pr-level path planning."""
from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from core.easycrypt.analysis.ec_pr_path_planner import build_pr_path_plan  # noqa: E402


def test_pr_path_planner_finds_multihop_have_chain() -> None:
    plan = build_pr_path_plan({
        "goal_type": "probability",
        "prob_form": "adv_ineq",
        "lhs_game": "BR93_Game0",
        "rhs_game": "OW_Game",
        "have_chain_candidates": [{
            "name": "game0_game1_bound",
            "lhs_game": "BR93_Game0",
            "rhs_game": "BR93_Game1",
        }, {
            "name": "game1_ow_bound",
            "lhs_game": "BR93_Game1",
            "rhs_game": "OW_Game",
        }],
    })

    path = plan["recommended_path"]
    assert path["status"] == "complete"
    assert path["relation"] == "inequality"
    assert path["lemmas"] == ["game0_game1_bound", "game1_ow_bound"]
    assert [hop["edge_kind"] for hop in path["hops"]] == [
        "have_chain",
        "have_chain",
    ]


def test_pr_path_planner_prefers_full_pr_text_when_parser_keeps_only_roots() -> None:
    plan = build_pr_path_plan({
        "goal_type": "probability",
        "prob_form": "eq",
        "lhs_game": "Game",
        "rhs_game": "MainD",
        "goal_text": (
            "Pr[Game(A, O1).main() @ &m : res] = "
            "Pr[MainD(D(A), O2).distinguish() @ &m : res]"
        ),
        "pr_rewrite_candidates": [{
            "name": "bridge",
            "lhs_game": "Game(A, O1)",
            "rhs_game": "MainD(D(A), O2)",
        }],
    })

    assert plan["endpoints"][0]["source_key"] == "Game(A,O1)"
    assert plan["endpoints"][0]["target_key"] == "MainD(D(A),O2)"
    assert plan["recommended_path"]["status"] == "complete"


def test_pr_path_planner_uses_rewrite_before_bound_hop() -> None:
    plan = build_pr_path_plan({
        "goal_type": "probability",
        "prob_form": "ineq",
        "lhs_game": "Game0",
        "rhs_game": "Game2",
        "pr_rewrite_candidates": [{
            "name": "pr_Game0_Game1",
            "lhs_game": "Game0",
            "rhs_game": "Game1",
        }],
        "have_chain_candidates": [{
            "name": "game1_game2_bound",
            "lhs_game": "Game1",
            "rhs_game": "Game2",
        }],
    })

    hops = plan["recommended_path"]["hops"]
    assert [hop["lemma"] for hop in hops] == [
        "pr_Game0_Game1",
        "game1_game2_bound",
    ]
    assert hops[0]["action_hint"] == "rewrite pr_Game0_Game1."
    assert hops[1]["edge_kind"] == "have_chain"


def test_pr_path_planner_plans_diff_eq_subgoals() -> None:
    plan = build_pr_path_plan({
        "goal_type": "probability",
        "prob_form": "diff_eq",
        "lhs_pos_game": "Game0",
        "rhs_pos_game": "Game1",
        "lhs_neg_game": "Game2",
        "rhs_neg_game": "Game3",
        "pr_rewrite_candidates": [{
            "name": "pr_Game0_Game1",
            "lhs_game": "Game0",
            "rhs_game": "Game1",
        }, {
            "name": "pr_Game2_Game3",
            "lhs_game": "Game2",
            "rhs_game": "Game3",
        }],
    })

    assert plan["summary"]["complete_path_count"] == 2
    assert [path["endpoint_id"] for path in plan["paths"]] == [
        "diff_eq.pos",
        "diff_eq.neg",
    ]
    assert plan["recommended_path"]["lemmas"] == ["pr_Game0_Game1"]


def test_pr_path_planner_uses_resolved_lemma_declarations() -> None:
    plan = build_pr_path_plan({
        "goal_type": "probability",
        "prob_form": "ineq",
        "lhs_game": "IND(PRPi, PRPF_Adv(A))",
        "rhs_game": "IND(PRFi, PRPF_Adv(A))",
        "resolved_name_items": [{
            "name": "Bound_by_PRP_PRF",
            "handle_kind": "have_chain",
            "declaration": (
                "lemma Bound_by_PRP_PRF: forall &m, "
                "`|Pr[IND(PRPi, PRPF_Adv(A)).main() @ &m : res] - "
                "Pr[IND(PRFi, PRPF_Adv(A)).main() @ &m : res]| <= eps."
            ),
        }],
    })

    path = plan["recommended_path"]
    assert path["status"] == "complete"
    assert path["lemmas"] == ["Bound_by_PRP_PRF"]
    assert path["source_key"] == "IND(PRPi,PRPF_Adv(A))"
    assert path["target_key"] == "IND(PRFi,PRPF_Adv(A))"


def test_pr_path_planner_does_not_turn_compound_lemma_into_rewrite_edge() -> None:
    plan = build_pr_path_plan({
        "goal_type": "probability",
        "prob_form": "eq",
        "lhs_game": "Game0",
        "rhs_game": "Game1",
        "resolved_name_items": [{
            "name": "step2_3",
            "handle_kind": "pr_rewrite",
            "declaration": (
                "lemma step2_3 &m : "
                "Pr[Game0.main() @ &m : res] + Pr[Bad0.main() @ &m : res] = "
                "Pr[Game1.main() @ &m : res] + Pr[Bad1.main() @ &m : res]."
            ),
        }],
    })

    assert plan["edges"] == []
    assert plan["summary"]["pr_rewrite_edge_count"] == 0
    assert plan["recommended_path"] is None


def test_pr_path_planner_extracts_multiple_clone_where_edges() -> None:
    plan = build_pr_path_plan({
        "goal_type": "probability",
        "prob_form": "eq",
        "lhs_game": "MainD(D, RO)",
        "rhs_game": "Split1.MainD(D2, Split1.RO_Pair(I1.RO, I2.RO))",
        "resolved_name_items": [{
            "name": "pr_RO_split",
            "handle_kind": "pr_rewrite",
            "source_kind": "where_lookup_tool",
            "declaration": (
                "(* Split0.pr_RO_split *)\n"
                "lemma pr_RO_split: forall &m, "
                "Pr[MainD(D, RO).distinguish() @ &m : res] = "
                "Pr[Split0.MainD(D, RO_DOM(ROT.RO, ROF.RO)).distinguish() @ &m : res].\n\n"
                "(* Split1.pr_RO_split *)\n"
                "lemma pr_RO_split: forall &m, "
                "Pr[Split0.MainD(D, RO_DOM(ROT.RO, ROF.RO)).distinguish() @ &m : res] = "
                "Pr[Split1.MainD(D2, Split1.RO_Pair(I1.RO, I2.RO)).distinguish() @ &m : res]."
            ),
        }],
    })

    path = plan["recommended_path"]
    assert path["status"] == "complete"
    assert path["lemmas"] == ["Split0.pr_RO_split", "Split1.pr_RO_split"]
    assert plan["summary"]["pr_rewrite_edge_count"] == 4


def test_pr_path_planner_searches_long_typed_bridge_chain() -> None:
    plan = build_pr_path_plan({
        "goal_type": "probability",
        "prob_form": "eq",
        "lhs_game": "Experiment(D, Oracle0)",
        "rhs_game": "Split3.MainD(D3, Oracle4)",
        "synthetic_pr_bridge_candidates": [{
            "name": "bridge_experiment_to_main",
            "lhs_game": "Experiment(D, Oracle0)",
            "rhs_game": "MainD(D0, Oracle0)",
        }, {
            "name": "bridge_main0_to_split1",
            "lhs_game": "MainD(D0, Oracle1)",
            "rhs_game": "Split1.MainD(D1, Oracle1)",
        }, {
            "name": "bridge_split1_to_split2",
            "lhs_game": "Split1.MainD(D1, Oracle2)",
            "rhs_game": "Split2.MainD(D2, Oracle2)",
        }, {
            "name": "bridge_split2_to_split3",
            "lhs_game": "Split2.MainD(D2, Oracle3)",
            "rhs_game": "Split3.MainD(D3, Oracle3)",
        }],
        "resolved_name_items": [{
            "name": "oracle_bridge",
            "handle_kind": "pr_rewrite",
            "declaration": (
                "(* Bridge0.pr_oracle *)\n"
                "lemma pr_oracle: forall &m, "
                "Pr[MainD(D0, Oracle0).run() @ &m : res] = "
                "Pr[MainD(D0, Oracle1).run() @ &m : res].\n\n"
                "(* Bridge1.pr_oracle *)\n"
                "lemma pr_oracle: forall &m, "
                "Pr[Split1.MainD(D1, Oracle1).run() @ &m : res] = "
                "Pr[Split1.MainD(D1, Oracle2).run() @ &m : res].\n\n"
                "(* Bridge2.pr_oracle *)\n"
                "lemma pr_oracle: forall &m, "
                "Pr[Split2.MainD(D2, Oracle2).run() @ &m : res] = "
                "Pr[Split2.MainD(D2, Oracle3).run() @ &m : res].\n\n"
                "(* Bridge3.pr_oracle *)\n"
                "lemma pr_oracle: forall &m, "
                "Pr[Split3.MainD(D3, Oracle3).run() @ &m : res] = "
                "Pr[Split3.MainD(D3, Oracle4).run() @ &m : res]."
            ),
        }],
    })

    path = plan["recommended_path"]
    assert path["status"] == "complete"
    assert path["hop_count"] == 8
    assert path["lemmas"] == [
        "bridge_experiment_to_main",
        "Bridge0.pr_oracle",
        "bridge_main0_to_split1",
        "Bridge1.pr_oracle",
        "bridge_split1_to_split2",
        "Bridge2.pr_oracle",
        "bridge_split2_to_split3",
        "Bridge3.pr_oracle",
    ]


def test_pr_path_planner_preserves_qualified_functor_application_keys() -> None:
    plan = build_pr_path_plan({
        "goal_type": "probability",
        "prob_form": "eq",
        "goal_text": (
            "Pr[Indist.Distinguish(D(A), IndRO).game() @ &m : res] = "
            "Pr[MainD(G2, RO).distinguish() @ &m : res]"
        ),
        "pr_rewrite_candidates": [{
            "name": "pr_wrapper_main",
            "lhs_game": "Indist.Distinguish(D(A), IndRO)",
            "rhs_game": "MainD(G2, RO)",
        }],
    })

    endpoint = plan["endpoints"][0]
    assert endpoint["source_key"] == "Indist.Distinguish(D(A),IndRO)"
    assert endpoint["target_key"] == "MainD(G2,RO)"
    assert plan["recommended_path"]["lemmas"] == ["pr_wrapper_main"]


def test_pr_path_planner_plans_compound_addend_pairs() -> None:
    plan = build_pr_path_plan({
        "goal_type": "probability",
        "prob_form": "compound",
        "lhs_addends": [
            {"game": "G0"},
            {"game": "G2"},
        ],
        "rhs_addends": [
            {"game": "G1"},
            {"game": "G3"},
        ],
        "pr_rewrite_candidates": [{
            "name": "pr_G0_G1",
            "lhs_game": "G0",
            "rhs_game": "G1",
        }, {
            "name": "pr_G2_G3",
            "lhs_game": "G2",
            "rhs_game": "G3",
        }],
    })

    assert [endpoint["id"] for endpoint in plan["endpoints"]] == [
        "compound.addend.1",
        "compound.addend.2",
    ]
    assert plan["summary"]["complete_path_count"] == 2
    assert [path["lemmas"] for path in plan["paths"]] == [
        ["pr_G0_G1"],
        ["pr_G2_G3"],
    ]


def test_pr_path_planner_reports_partial_frontier_when_bridge_missing() -> None:
    plan = build_pr_path_plan({
        "goal_type": "probability",
        "prob_form": "eq",
        "lhs_game": "Game0",
        "rhs_game": "Game3",
        "pr_rewrite_candidates": [{
            "name": "pr_Game0_Game1",
            "lhs_game": "Game0",
            "rhs_game": "Game1",
        }, {
            "name": "pr_Game1_Game2",
            "lhs_game": "Game1",
            "rhs_game": "Game2",
        }],
    })

    assert plan["recommended_path"] is None
    assert plan["summary"]["partial_path_count"] >= 1
    partial = plan["partial_paths"][0]
    assert partial["status"] == "partial"
    assert partial["side"] == "source"
    assert partial["frontier_key"] == "Game2"
    assert partial["lemmas"] == ["pr_Game0_Game1", "pr_Game1_Game2"]
    assert "remaining frontier" in partial["strategy"]


def test_pr_path_planner_uses_synthetic_bridge_edges_in_target_frontier() -> None:
    plan = build_pr_path_plan({
        "goal_type": "probability",
        "prob_form": "eq",
        "goal_text": (
            "Pr[G1(Gen).main() @ &m : res] = "
            "Pr[Indist.Distinguish(D(A), IndRO).game() @ &m : res]"
        ),
        "pr_rewrite_candidates": [{
            "name": "pr_CCP_OCCP",
            "lhs_game": "G1(Gen)",
            "rhs_game": "G1(OCCP)",
        }],
        "synthetic_pr_bridge_candidates": [{
            "name": "bridge_indist_to_main",
            "lhs_game": "Indist.Distinguish(D(A), IndRO)",
            "rhs_game": "MainD(G2, RO)",
            "tactic": (
                "have -> : Pr[Indist.Distinguish(D(A), IndRO).game() @ &m : res] = "
                "Pr[MainD(G2, RO).distinguish() @ &m : res] "
                "by byequiv => //; proc; inline *; sim."
            ),
        }],
        "instantiated_pr_rewrite_candidates": [{
            "name": "pr_RO_FinRO_D",
            "lhs_game": "MainD(G2, RO)",
            "rhs_game": "MainD(G2, FinRO)",
            "action_hint": "rewrite (pr_RO_FinRO_D _ G2 &m () (fun x => x)) /=.",
        }],
    })

    partials = plan["partial_paths"]
    target_partial = [
        item for item in partials
        if item["side"] == "target"
    ][0]
    assert target_partial["root_key"] == "Indist.Distinguish(D(A),IndRO)"
    assert target_partial["frontier_key"] == "MainD(G2,FinRO)"
    assert [hop["edge_kind"] for hop in target_partial["hops"]] == [
        "synthetic_bridge",
        "pr_rewrite",
    ]
    assert "distinguish()" in target_partial["hops"][0]["action_hint"]
    assert "distinguish(())" not in target_partial["hops"][0]["action_hint"]
    assert target_partial["agenda"][0]["action_type"] == (
        "probe_tactic_if_current_endpoint_matches"
    )
    assert target_partial["agenda"][1]["readiness"] == (
        "typed_instantiation_candidate"
    )
    assert target_partial["missing_frontier"]["repair_class"] == (
        "add_or_prove_bridge_before_lowering"
    )


def test_pr_path_planner_emits_typed_agenda_for_complete_path() -> None:
    plan = build_pr_path_plan({
        "goal_type": "probability",
        "prob_form": "eq",
        "goal_text": (
            "Pr[Game0.main() @ &m : res] = "
            "Pr[Game2.main() @ &m : res]"
        ),
        "pr_rewrite_candidates": [{
            "name": "pr_Game0_Game1",
            "lhs_game": "Game0",
            "rhs_game": "Game1",
            "source_kind": "parsed_candidate",
        }],
        "instantiated_pr_rewrite_candidates": [{
            "name": "pr_Game1_Game2",
            "lhs_game": "Game1",
            "rhs_game": "Game2",
            "source_kind": "instantiated_binding",
            "action_hint": "rewrite (pr_Game1_Game2 _ M &m).",
        }],
    })

    path = plan["recommended_path"]
    assert path["status"] == "complete"
    assert path["saturation_condition"].startswith("Pr endpoint path is live")
    assert [item["lemma"] for item in path["agenda"]] == [
        "pr_Game0_Game1",
        "pr_Game1_Game2",
    ]
    assert path["agenda"][0]["readiness"] == "needs_signature_check"
    assert path["agenda"][1]["readiness"] == "typed_instantiation_candidate"
    assert "current Pr endpoint" in path["agenda"][0]["required_before_commit"][-1]
    assert path["next_action"]["lemma"] == "pr_Game0_Game1"


def test_pr_path_planner_classifies_advantage_arithmetic_pipeline() -> None:
    plan = build_pr_path_plan({
        "goal_type": "probability",
        "prob_form": "adv_ineq",
        "raw_text": (
            "`|Pr[IND(PRPi, PRPF_Adv(A)).main() @ &m : res] - "
            "Pr[IND(PRFi, PRPF_Adv(A)).main() @ &m : res]| <= "
            "Pr[BAD.main() @ &m : bad] + mu q"
        ),
        "resolved_name_items": [{
            "name": "reduction",
            "handle_kind": "have_chain",
            "source_kind": "local_context",
            "declaration": (
                "lemma reduction (A <: Adv) &m : "
                "`|Pr[IND(PRPi, PRPF_Adv(A)).main() @ &m : res] - "
                "Pr[IND(PRFi, PRPF_Adv(A)).main() @ &m : res]| <= "
                "Pr[BAD.main() @ &m : bad] + eps."
            ),
            "parameter_slots": [
                {"kind": "module_arg", "name": "A"},
                {"kind": "memory_arg", "name": "&m"},
            ],
        }, {
            "name": "bad_bound",
            "handle_kind": "have_chain",
            "source_kind": "local_context",
            "declaration": (
                "lemma bad_bound (A <: Adv) &m : "
                "Pr[BAD.main() @ &m : bad] <= mu q."
            ),
        }, {
            "name": "pr_cleanup",
            "handle_kind": "pr_rewrite",
            "source_kind": "local_context",
            "declaration": (
                "lemma pr_cleanup &m : "
                "Pr[BAD.main() @ &m : bad] = Pr[BAD2.main() @ &m : bad]."
            ),
        }],
    })

    arithmetic = plan["arithmetic_plan"]
    assert arithmetic["available"] is True
    assert arithmetic["shape"] == "absolute_pr_difference_bound"
    assert arithmetic["recommended_chain"][:2] == ["reduction", "bad_bound"]
    assert arithmetic["candidate_lemmas"][0]["role"] == "advantage_bound"
    assert "module_arg" in arithmetic["candidate_lemmas"][0]["argument_risks"]
    assert "EasyCrypt" in arithmetic["native_ec_support"][0]
    assert "smt(mu_bounded)." in arithmetic["finish_tactics"]
    assert plan["summary"]["has_arithmetic_plan"] is True


def test_pr_path_planner_keeps_single_pr_bound_out_of_arithmetic_plan() -> None:
    plan = build_pr_path_plan({
        "goal_type": "probability",
        "prob_form": "ineq",
        "raw_text": "Pr[G.main() @ &m : bad] <= eps",
        "lhs_game": "G",
    })

    assert plan["arithmetic_plan"] == {
        "available": False,
        "reason": "not_pr_arithmetic_shape",
    }
    assert plan["summary"]["has_arithmetic_plan"] is False


def main() -> int:
    test_pr_path_planner_finds_multihop_have_chain()
    test_pr_path_planner_uses_rewrite_before_bound_hop()
    test_pr_path_planner_plans_diff_eq_subgoals()
    test_pr_path_planner_uses_resolved_lemma_declarations()
    test_pr_path_planner_does_not_turn_compound_lemma_into_rewrite_edge()
    test_pr_path_planner_preserves_qualified_functor_application_keys()
    test_pr_path_planner_plans_compound_addend_pairs()
    test_pr_path_planner_reports_partial_frontier_when_bridge_missing()
    test_pr_path_planner_uses_synthetic_bridge_edges_in_target_frontier()
    test_pr_path_planner_emits_typed_agenda_for_complete_path()
    test_pr_path_planner_extracts_multiple_clone_where_edges()
    test_pr_path_planner_searches_long_typed_bridge_chain()
    test_pr_path_planner_classifies_advantage_arithmetic_pipeline()
    test_pr_path_planner_keeps_single_pr_bound_out_of_arithmetic_plan()
    print("PASS test_ec_pr_path_planner")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
