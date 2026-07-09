"""Tests for probability-budget middle-end analysis."""
from __future__ import annotations

from core.easycrypt.analysis.probability_budget import (
    analyze_probability_budget,
    probability_budget_route_risk,
)


PRODUCT_BOUND = "((PKE_.qD%r / order%r) ^ 2) * (PKE_.qD%r / order%r)"


def _symbols(analysis: dict) -> set[str]:
    return {
        str(item.get("symbol"))
        for item in analysis.get("useful_fact_handles", [])
        if isinstance(item, dict)
    }


def test_analyzer_classifies_top_level_probability_product_budget() -> None:
    goal = (
        "Pr[G4.main() @ &m : (G3.a, G3.b) \\in G3.cilog] <= "
        f"{PRODUCT_BOUND}"
    )

    analysis = analyze_probability_budget(goal)

    assert analysis["kind"] == "probability_budget"
    assert analysis["source"] == "single_program_probability_goal"
    assert analysis["budget_shape"] == "product_bound"
    assert analysis["event_shape"]["kind"] == "membership_event"
    assert {
        "PKE_.qD_pos",
        "gt1_q",
        "mulr_ge0",
        "divr_ge0",
        "mulr_gt0",
        "divr_gt0",
        "expr_gt0",
        "divrr",
    } <= _symbols(analysis)
    # Factual Pr-shape only — no heuristic route advice.
    assert "side_condition_recipe" not in analysis
    assert "likely_proof_family" not in analysis
    assert "anti_routes" not in analysis
    ledger = analysis["budget_ledger"]
    assert ledger["kind"] == "probability_budget_ledger"
    assert ledger["status"] == "partial"
    assert len(ledger["factor_slots"]) == 3
    assert [slot["source"] for slot in ledger["factor_slots"][:2]] == [
        "power_expansion",
        "power_expansion",
    ]
    assert ledger["factor_slots"][0]["role"] == "finite_domain_point_mass"




def test_analyzer_classifies_phoare_bound_product_budget() -> None:
    goal = f"""
Current goal
Bound   : [<=] {PRODUCT_BOUND}
pre = true
( 1)  c <@ A.main();
post = c \\in G3.cilog
"""

    analysis = analyze_probability_budget(goal)

    assert analysis["source"] == "phoare_bound"
    assert analysis["bound_relation"] == "[<=]"
    assert analysis["factors"]
    assert "PKE_.qD_pos" in _symbols(analysis)
    assert "gt1_q" in _symbols(analysis)
    assert analysis["budget_ledger"]["kind"] == "probability_budget_ledger"


def test_analyzer_classifies_top_level_scaled_probability_equality() -> None:
    goal = (
        "(1%r / bound%r) * Pr[G.main(x0) @ &m : phi (glob G) res] = "
        "Pr[Guess(G).main(x0) @ &m : "
        "phi (glob G) res.`2 /\\ res.`1 = psi (glob G) res.`2]"
    )

    analysis = analyze_probability_budget(goal)

    assert analysis["kind"] == "probability_budget"
    assert analysis["budget_shape"] == "scaled_probability"
    assert analysis["source"] == "top_level_probability_equality"
    assert analysis["scale"] == "1%r / bound%r"
    assert analysis["source_probability"] == "Pr[G.main(x0) @ &m : phi (glob G) res]"
    assert analysis["target_probability"].startswith("Pr[Guess(G).main")
    ledger = analysis["budget_ledger"]
    assert ledger["budget_shape"] == "scaled_probability"
    assert [slot["role"] for slot in ledger["factor_slots"][:2]] == [
        "source_probability",
        "scale_point_mass",
    ]
    assert ledger["event_obligations"][0]["expected_seq_shape"] == (
        "seq K : event (P) (scale) _ 0%r"
    )


def test_analyzer_classifies_phoare_scaled_probability_bound() -> None:
    goal = """
Current goal
Bound   : [=] (1%r / bound%r) * Pr[G.main(x0) @ &m : phi (glob G) res]
pre = (glob G) = (glob G){m} /\\ x0 = x
( 1)  o <@ G.main(x)
( 2)  i <$ [0..(bound - 1)]
post = phi (glob G) res.`2 /\\ res.`1 = psi (glob G) res.`2
"""

    analysis = analyze_probability_budget(goal)

    assert analysis["source"] == "phoare_bound"
    assert analysis["bound_relation"] == "[=]"
    assert analysis["budget_shape"] == "scaled_probability"
    assert analysis["budget_ledger"]["source_probability"] == (
        "Pr[G.main(x0) @ &m : phi (glob G) res]"
    )
    assert "source probability" in analysis["budget_ledger"]["read_as"]


def test_analyzer_surfaces_list_membership_event_bound_bridge() -> None:
    goal = f"""
Current goal
Bound   : [<=] {PRODUCT_BOUND}
pre = size G3.cilog <= PKE_.qD
( 1)  u <$ dt
( 2)  u' <$ dt \\ pred1 u
post =
  let a = g ^ u in
  let a_ = g_ ^ u' in
  (a, a_) \\in G3.cilog
"""

    analysis = analyze_probability_budget(goal)

    bridge = analysis["event_bound_bridge"]
    assert bridge["kind"] == "list_membership_probability_bound"
    assert bridge["event_collection"] == "G3.cilog"
    assert bridge["size_bound"]["fact"] == "size G3.cilog <= PKE_.qD"
    assert bridge["candidate_lemma_handles"][0]["symbol"] == "mu_mem_le_mu1_size"
    assert "likely_proof_family" not in analysis
    obligation = analysis["budget_ledger"]["event_obligations"][0]
    assert obligation["bridge_family"] == "list_size_times_point_mass"
    assert obligation["candidate_lemma_handles"][0]["symbol"] == "mu_mem_le_mu1_size"


def test_analyzer_builds_list_membership_point_mass_route() -> None:
    goal = """
Current goal
Bound   : [<=] ((PKE_.qD%r / order%r) ^ 3) * (PKE_.qD%r / (order - 1)%r)
pre = size G3.cilog <= PKE_.qD
( 1)  G1.u <$ dt
( 2)  G1.u' <$ dt \\ pred1 G1.u
( 3)  r' <$ dt
( 4)  r <$ dt
( 5)  G3.a <- g ^ G1.u
( 6)  G3.a_ <- G1.g_ ^ G1.u'
( 7)  G3.c <- g ^ r'
( 8)  G3.d <- g ^ r
( 9)  b0 <@ A.guess(G3.a, G3.a_, G3.c, G3.d)
post = (G3.a, G3.a_, G3.c, G3.d) \\in G3.cilog
"""

    analysis = analyze_probability_budget(goal)

    route = analysis["event_bound_bridge"]["point_mass_route"]
    assert route["kind"] == "list_membership_point_mass_route"
    assert route["status"] == "complete"
    assert route["bridge_lemma"] == "mu_mem_le_mu1_size"
    assert "first apply list-size times point-mass bridge" in route["route_plan"][0]
    assignments = route["sample_factor_assignments"]
    assert [item["sample"] for item in assignments] == ["G1.u", "G1.u'", "r'", "r"]
    assert assignments[0]["expected_point_mass"] == "1%r / order%r"
    except_one = next(item for item in assignments if item["sample"] == "G1.u'")
    assert except_one["distribution_family"] == "finite_uniform_except_one"
    assert except_one["expected_point_mass"] == "1%r / (order - 1)%r"
    assert "order - 1" in except_one["candidate_factor_expr"]
    obligation = analysis["budget_ledger"]["event_obligations"][0]
    assert (
        obligation["event_bound_bridge"]["point_mass_route"]["kind"]
        == "list_membership_point_mass_route"
    )


def test_analyzer_ignores_non_product_probability_goal() -> None:
    goal = "Pr[G.main() @ &m : res] <= PKE_.qD%r / order%r"

    assert analyze_probability_budget(goal) == {}


def test_analyzer_ignores_probability_equality_even_with_product_shape() -> None:
    goal = f"Pr[G.main() @ &m : res] = {PRODUCT_BOUND}"

    assert analyze_probability_budget(goal) == {}


def test_analyzer_ignores_pure_probability_equality_for_chacha_step3_shape() -> None:
    goal = (
        "Pr[Split1.IdealAll.MainD(G8(BNR_Adv(A)), "
        "SplitC2.RO_Pair(ROin, ROout)).distinguish() @ &m : res] = "
        "Pr[CPA_game(CCA_CPA_Adv(BNR_Adv(A)), EncRnd).main() @ &m : res]"
    )

    assert analyze_probability_budget(goal) == {}


def test_route_health_warns_after_rnd_under_product_budget() -> None:
    goal = f"""
Current goal
Bound   : [<=] {PRODUCT_BOUND}
pre = true
( 1)  x <$ dunit;
post = x \\in G3.cilog
"""

    risk = probability_budget_route_risk(
        goal_text=goal,
        route_events=[{
            "intent": "probe_tactic",
            "tactic": "rnd.",
            "tactic_head": "rnd",
            "accepted": True,
            "status": "probe_accepted",
        }],
    )

    assert risk["signal"] == "probability_budget_route_risk"
    assert "single_rnd_for_whole_product_budget" in {
        item["route"] for item in risk["anti_routes"]
    }
    assert risk["recommended_next"] == {
        "intent": "inspect_context",
        "payload": {"topic": "probability_budget_ledger"},
    }
    assert risk["budget_ledger"]["kind"] == "probability_budget_ledger"
    assert risk["primary_next_action"] == risk["recommended_next"]


def test_route_health_warns_after_compact_rnd_under_product_budget() -> None:
    goal = f"""
Current goal
Bound   : [<=] {PRODUCT_BOUND}
pre = true
( 1)  u <$ dt
( 2)  v <$ dt
( 3)  w <$ dt
( 4)  z <$ dt
post = (u, v, w, z) \\in G3.cilog
"""

    risk = probability_budget_route_risk(
        goal_text=goal,
        route_events=[{
            "intent": "probe_tactic",
            "tactic": "do 4!rnd.",
            "tactic_head": "do",
            "accepted": True,
            "status": "probe_accepted",
        }],
    )

    assert risk["signal"] == "probability_budget_route_risk"
    assert "recent accepted/probed local sampling under a product probability budget" in risk["evidence"]


def test_route_health_suggests_event_bound_bridge_lookup() -> None:
    goal = f"""
Current goal
Bound   : [<=] {PRODUCT_BOUND}
pre = size G3.cilog <= PKE_.qD
( 1)  u <$ dt
( 2)  v <$ dt
post = (u, v) \\in G3.cilog
"""

    risk = probability_budget_route_risk(
        goal_text=goal,
        route_events=[{
            "intent": "probe_tactic",
            "tactic": "rnd; rnd; skip.",
            "tactic_head": "rnd",
            "accepted": True,
            "status": "probe_accepted",
        }],
    )

    assert risk["signal"] == "probability_budget_route_risk"
    assert (
        risk["budget"]["event_bound_bridge"]["candidate_lemma_handles"][0]["symbol"]
        == "mu_mem_le_mu1_size"
    )
    assert any(
        item.get("intent") == "lookup_symbol"
        and item.get("payload", {}).get("symbol") == "mu_mem_le_mu1_size"
        for item in risk["useful_inspections"]
    )


def test_route_health_warns_after_seq_puts_product_budget_on_side_fact() -> None:
    goal = f"""
Current goal
Bound   : [<=] {PRODUCT_BOUND}
pre = true
( 1)  c <@ A.choose();
post = size G3.cilog <= PKE_.qD
"""

    risk = probability_budget_route_risk(
        goal_text=goal,
        route_events=[{
            "intent": "commit_tactic",
            "tactic": "seq 13 : (size G3.cilog <= PKE_.qD).",
            "tactic_head": "seq",
            "accepted": True,
            "changed": True,
        }],
    )

    assert risk["signal"] == "probability_budget_route_risk"
    assert risk["confidence"] == "high"
    assert "recent accepted/probed `seq` cut may allocate the product budget to the wrong branch" in risk["evidence"]
    assert "seq_cut_allocates_product_budget_to_prefix" in {
        item["route"] for item in risk["anti_routes"]
    }


def test_route_health_warns_after_scale_only_seq_under_scaled_probability() -> None:
    goal = """
Current goal
Bound   : [=] (1%r / bound%r) * Pr[G.main(x0) @ &m : phi (glob G) res]
pre = (glob G) = (glob G){m} /\\ x0 = x
( 1)  o <@ G.main(x)
( 2)  i <$ [0..(bound - 1)]
post = phi (glob G) res.`2 /\\ res.`1 = psi (glob G) res.`2
"""

    risk = probability_budget_route_risk(
        goal_text=goal,
        route_events=[{
            "intent": "probe_tactic",
            "tactic": "seq 1 : (phi (glob G) o) (1%r / bound%r).",
            "tactic_head": "seq",
            "accepted": True,
            "status": "probe_accepted",
        }],
    )

    assert risk["signal"] == "probability_budget_route_risk"
    assert risk["budget_ledger"]["budget_shape"] == "scaled_probability"
    seq_cut = risk["budget_ledger"]["recent_seq_cuts"][0]
    assert seq_cut["classification"] == "scaled_probability_scale_only_likely_wrong_branch"
    assert "seq 1 : Q (P) (1%r / bound%r) _ 0%r." == seq_cut["preferred_shape"]


def test_route_health_allows_scaled_probability_seq_with_source_slot() -> None:
    goal = """
Current goal
Bound   : [=] (1%r / bound%r) * Pr[G.main(x0) @ &m : phi (glob G) res]
pre = (glob G) = (glob G){m} /\\ x0 = x
( 1)  o <@ G.main(x)
( 2)  i <$ [0..(bound - 1)]
post = phi (glob G) res.`2 /\\ res.`1 = psi (glob G) res.`2
"""

    assert probability_budget_route_risk(
        goal_text=goal,
        route_events=[{
            "intent": "probe_tactic",
            "tactic": (
                "seq 1 : (phi (glob G) o) "
                "(Pr[G.main(x0) @ &m : phi (glob G) res]) "
                "(1%r / bound%r) _ 0%r."
            ),
            "tactic_head": "seq",
            "accepted": True,
            "status": "probe_accepted",
        }],
    ) == {}


def test_route_health_warns_before_committing_bad_seq_probe() -> None:
    goal = f"""
Current goal
Bound   : [<=] {PRODUCT_BOUND}
pre = true
( 1)  c <@ A.choose();
post = (a, b, c, d) \\in G3.cilog
"""

    risk = probability_budget_route_risk(
        goal_text=goal,
        route_events=[{
            "intent": "probe_tactic",
            "tactic": "seq 13 : (size G3.cilog <= PKE_.qD).",
            "tactic_head": "seq",
            "accepted": True,
            "status": "probe_accepted",
        }],
    )

    assert risk["signal"] == "probability_budget_route_risk"
    assert "recent accepted/probed `seq` cut may allocate the product budget to the wrong branch" in risk["evidence"]


def test_route_health_warns_after_seq_unit_bound_under_product_budget() -> None:
    goal = f"""
Current goal
Bound   : [<=] {PRODUCT_BOUND}
pre = true
( 1)  c <@ A.choose();
post = (a, b, c, d) \\in G3.cilog
"""

    risk = probability_budget_route_risk(
        goal_text=goal,
        route_events=[{
            "intent": "probe_tactic",
            "tactic": "seq 13 : (size G3.cilog <= PKE_.qD) (1%r).",
            "tactic_head": "seq",
            "accepted": True,
            "status": "probe_accepted",
        }],
    )

    seq_cut = risk["budget_ledger"]["recent_seq_cuts"][0]
    assert risk["signal"] == "probability_budget_route_risk"
    assert seq_cut["classification"] == "unit_bound_likely_wrong_branch"
    assert "seq 13 : Q" in seq_cut["preferred_shape"]


def test_route_health_allows_event_preserving_membership_call_boundary() -> None:
    goal = """
Current goal
Bound   : [<=] ((PKE_.qD%r / order%r) ^ 3) * (PKE_.qD%r / (order - 1)%r)
pre = size G3.cilog <= PKE_.qD
( 1)  G1.u <$ dt
( 2)  G1.u' <$ dt \\ pred1 G1.u
( 3)  r' <$ dt
( 4)  r <$ dt
( 5)  G3.a <- g ^ G1.u
( 6)  G3.a_ <- G1.g_ ^ G1.u'
( 7)  G3.c <- g ^ r'
( 8)  G3.d <- g ^ r
( 9)  b0 <@ A.guess(G3.a, G3.a_, G3.c, G3.d)
post = (G3.a, G3.a_, G3.c, G3.d) \\in G3.cilog
"""

    risk = probability_budget_route_risk(
        goal_text=goal,
        route_events=[{
            "intent": "probe_tactic",
            "tactic": (
                "call (_: (G3.a, G3.a_, G3.c, G3.d) \\in G3.cilog ==> "
                "(G3.a, G3.a_, G3.c, G3.d) \\in G3.cilog)."
            ),
            "tactic_head": "call",
            "accepted": True,
            "status": "probe_accepted",
        }],
    )

    assert risk == {}


def test_route_health_warns_for_product_budget_on_side_fact_seq() -> None:
    goal = f"""
Current goal
Bound   : [<=] {PRODUCT_BOUND}
pre = true
( 1)  c <@ A.choose();
post = (a, b, c, d) \\in G3.cilog
"""

    risk = probability_budget_route_risk(
        goal_text=goal,
        route_events=[{
            "intent": "probe_tactic",
            "tactic": f"seq 13 : (size G3.cilog <= PKE_.qD) {PRODUCT_BOUND}.",
            "tactic_head": "seq",
            "accepted": True,
            "status": "probe_accepted",
        }],
    )

    assert risk["signal"] == "probability_budget_route_risk"
    seq_cut = risk["budget_ledger"]["recent_seq_cuts"][0]
    assert seq_cut["classification"] == "product_budget_side_fact_candidate"


def test_route_health_allows_matching_event_unit_seq_boundary() -> None:
    goal = f"""
Current goal
Bound   : [<=] {PRODUCT_BOUND}
pre = true
( 1)  c <@ A.choose();
post = (a, b, c, d) \\in G3.cilog
"""

    assert probability_budget_route_risk(
        goal_text=goal,
        route_events=[{
            "intent": "probe_tactic",
            "tactic": "seq 13 : ((a, b, c, d) \\in G3.cilog) 1%r; first by auto.",
            "tactic_head": "seq",
            "accepted": True,
            "status": "probe_accepted",
        }],
    ) == {}


def test_route_health_remembers_bad_probability_budget_route_shapes() -> None:
    goal = f"""
Current goal
Bound   : [<=] {PRODUCT_BOUND}
pre = true
( 1)  c <@ A.choose();
post = (a, b, c, d) \\in G3.cilog
"""

    events = [
        {
            "intent": "probe_tactic",
            "tactic": "rnd.",
            "tactic_head": "rnd",
            "accepted": True,
            "status": "probe_accepted",
        },
        *[
            {
                "intent": "inspect_context",
                "topic": "goal_info",
                "accepted": True,
            }
            for _ in range(10)
        ],
        {
            "intent": "probe_tactic",
            "tactic": "seq 13 : (size G3.cilog <= PKE_.qD).",
            "tactic_head": "seq",
            "accepted": True,
            "status": "probe_accepted",
        },
    ]

    risk = probability_budget_route_risk(goal_text=goal, route_events=events)

    assert risk["signal"] == "probability_budget_route_risk"
    assert "route memory contains previously bad probability-budget tactic shapes" in risk["evidence"]
    assert any(
        item["route"] == "remembered_local_sampling_under_product_budget"
        for item in risk["route_memory"]
    )


def test_route_health_warns_after_split_leaves_le_one_call_residual() -> None:
    goal = """
Current goal
Bound   : [<=] 1%r
pre = true
( 1)  b <@ A.main();
post = res
"""

    risk = probability_budget_route_risk(
        goal_text=goal,
        route_events=[{
            "intent": "commit_tactic",
            "tactic": f"phoare split ! 1%r (1%r - {PRODUCT_BOUND}).",
            "tactic_head": "phoare",
            "accepted": True,
            "changed": True,
        }],
    )

    assert risk["signal"] == "probability_budget_route_risk"
    assert "visible one-sided `[<=] 1%r` procedure-call residual" in risk["evidence"]
    assert any(
        item.get("payload", {}).get("name") == "phoare_split"
        for item in risk["useful_inspections"]
    )


def test_route_health_suggests_hoare_call_form_for_le_one_call_residual() -> None:
    goal = """
Current goal
Bound   : [<=] 1%r
pre = true
( 1)  b <@ A.main();
post = res
"""

    risk = probability_budget_route_risk(
        goal_text=goal,
        route_events=[
            {
                "intent": "commit_tactic",
                "tactic": f"phoare split ! 1%r (1%r - {PRODUCT_BOUND}).",
                "tactic_head": "phoare",
                "accepted": True,
                "changed": True,
            },
            {
                "intent": "probe_tactic",
                "tactic": "call (_: true).",
                "tactic_head": "call",
                "accepted": False,
                "rejected": True,
                "error_summary": "bound must be compatible with procedure call",
            },
        ],
    )

    assert "remembered_direct_call_true_under_le_bound" in {
        item["route"] for item in risk["route_memory"]
    }
    assert any(
        item.get("payload", {}).get("name") == "call"
        for item in risk["useful_inspections"]
    )


def test_route_health_ignores_unrelated_prhl_call_goal() -> None:
    goal = """
Current goal
pre = ={glob A}
( 1)  b <@ A.main();
( 2)  b <@ A.main();
post = ={res}
"""

    assert probability_budget_route_risk(
        goal_text=goal,
        route_events=[{
            "intent": "probe_tactic",
            "tactic": "call (_: true).",
            "tactic_head": "call",
            "accepted": True,
        }],
    ) == {}


def test_route_health_ignores_seq_without_product_budget() -> None:
    goal = """
Current goal
pre = true
( 1)  c <@ A.choose();
post = size log <= q
"""

    assert probability_budget_route_risk(
        goal_text=goal,
        route_events=[{
            "intent": "probe_tactic",
            "tactic": "seq 13 : (size log <= q).",
            "tactic_head": "seq",
            "accepted": True,
        }],
    ) == {}
