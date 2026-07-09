from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from workflow.surface_profiles import (  # noqa: E402
    apply_workspace_view_surface_profile,
    resolve_surface_profile,
    surface_profile_allows_intent,
    surface_profile_names,
)
from workflow.surface_composer import (  # noqa: E402
    _load_bearing_frontier_call,
    _render_surgery_skeleton,
    _statement_is_proc_call,
    _surgery_lookahead_after_frontier,
    _surgery_where,
    compose_surface_model,
)
from workflow.surface_model import surface_model_to_dict  # noqa: E402
from workflow.surface_action_preflight import action_preflight_key  # noqa: E402


def _with_call_preflight(view: dict, *, eligible: bool = True) -> dict:
    out = dict(view)
    out["surface_action_preflight"] = {
        "schema_version": 1,
        "results": [{
            "intent": "call_site_options",
            "payload": {},
            "key": action_preflight_key("call_site_options", {}),
            "eligible": eligible,
            "reason": (
                "preflight found a runnable call-site option"
                if eligible else "preflight returned no displayable call-site option"
            ),
        }],
    }
    return out


def _model(view: dict) -> dict:
    return surface_model_to_dict(
        compose_surface_model(view, "l4_checked_action_surface")
    )


def _phase(view: dict) -> str:
    return _model(view)["phase"]


def _fact(panel: dict, key: str):
    for item in panel.get("facts", []):
        if item.get("key") == key:
            return item.get("value")
    raise AssertionError(f"missing fact {key!r} in {panel}")


def _panel(view: dict) -> dict:
    return _model(view)["primary_panel"]


def _panel_fact_dict(view: dict) -> dict:
    panel = _panel(view)
    return {item["key"]: item.get("value") for item in panel.get("facts", [])}


def _opener_fact_dict(view: dict) -> dict:
    v = dict(view)
    v["proof_status"] = {"current_layer": "pr", "goal_type": "probability"}
    return _panel_fact_dict(v)


def _call_fact_dict(view: dict) -> dict:
    v = _with_call_preflight(view)
    v.setdefault("proof_status", {"current_layer": "call_site"})
    v.setdefault("program_frontier", {"focus": {"frontier_call_sites": 1}})
    return _panel_fact_dict(v)


def _call_layer_view(frontier_call_sites: int) -> dict:
    return {
        "proof_status": {"status": "open", "view_focus": "relational_program",
                         "current_layer": "call_site"},
        "current_goal": {"lines": ["g" * 60]},
        "program_frontier": {"focus": {"frontier_call_sites": frontier_call_sites,
                                       "live_call_sites": 4}},
    }


def test_call_focus_gates_on_frontier_call_not_downstream_call() -> None:
    # Panel-audit root cause (2026-06-05): the call-invariant panel fired whenever the
    # goal CONTAINED a call (current_layer="call_site" / live_call_sites>0), even when
    # the call was downstream and the frontier needed a reorder/eager move. The phase
    # must no longer gate on frontier_call_sites alone.
    assert _phase(_call_layer_view(frontier_call_sites=0)) == "deep_surgery"
    assert _phase(_call_layer_view(frontier_call_sites=2)) == "deep_surgery"
    assert _phase(_with_call_preflight(_call_layer_view(frontier_call_sites=2))) == "call_site"


def test_call_skeleton_preflight_does_not_promote_noncallable_named_handle() -> None:
    # step4_1 calibration: after `byequiv ...; proc.`, the named handle
    # UFCMA_genCC is relevant context, but it is not callable/frontier-live yet.
    # A skeleton preflight alone must not make the surface read as "Call Frontier".
    view = {
        "proof_status": {"status": "open", "goal_type": "pRHL",
                         "view_focus": "relational_program", "current_layer": "call_site"},
        "current_goal": {"lines": ["L <@ G9.distinguish(x)     R <- false; if (b) { c <@ P.main(); }"]},
        "call_site_surface": {
            "named_handles": [{
                "symbol": "UFCMA_genCC",
                "callable_now": False,
                "frontier_live": False,
            }],
            "frontier_blockers": [{
                "kind": "named_call_subject_absent_at_frontier",
                "symbol": "UFCMA_genCC",
                "frontier_live_procedures": ["CPA_game.main", "G9.distinguish"],
            }],
            "named_call_templates": [{
                "symbol": "UFCMA_genCC",
                "status": "candidate_named_call",
                "tactic_shape": "call UFCMA_genCC.",
            }],
        },
        "surface_action_preflight": {
            "schema_version": 1,
            "results": [{
                "intent": "call_invariant_skeleton",
                "payload": {},
                "key": action_preflight_key("call_invariant_skeleton", {}),
                "eligible": True,
                "reason": "preflight generated a skeleton",
            }],
        },
        "inspect_lookup_handles": {"ask_manager_for": [
            {"intent": "call_invariant_skeleton", "payload": {}},
            {"intent": "tactic_forms", "payload": {"name": "call"}},
        ]},
    }

    model = _model(view)
    blob = json.dumps(model, ensure_ascii=False)
    assert model["primary_panel"]["panel_id"] == "deep_surgery"
    assert model["status"]["current_layer"] == "call_site"
    assert model["status"]["surface_phase"] == "deep_surgery"
    assert "call_invariant_skeleton" not in {a["intent"] for a in model.get("actions", [])}
    assert "call UFCMA_genCC." not in blob


def test_callable_named_handle_still_promotes_call_panel() -> None:
    view = {
        "proof_status": {"status": "open", "goal_type": "pRHL",
                         "view_focus": "relational_program", "current_layer": "call_site"},
        "current_goal": {"lines": ["x <@ M.f(); y <@ N.f();"]},
        "call_site_surface": {
            "named_handles": [{
                "symbol": "Bridge",
                "callable_now": True,
                "frontier_live": True,
            }],
            "callable_now": [{"symbol": "Bridge", "tactic_shape": "call Bridge."}],
            "named_call_templates": [{"symbol": "Bridge", "tactic_shape": "call Bridge."}],
        },
        "surface_action_preflight": {
            "schema_version": 1,
            "results": [{
                "intent": "call_invariant_skeleton",
                "payload": {},
                "key": action_preflight_key("call_invariant_skeleton", {}),
                "eligible": True,
                "reason": "preflight generated a skeleton",
            }],
        },
        "inspect_lookup_handles": {"ask_manager_for": [
            {"intent": "call_invariant_skeleton", "payload": {}},
        ]},
    }

    model = _model(view)
    blob = json.dumps(model, ensure_ascii=False)
    assert model["primary_panel"]["panel_id"] == "call_site"
    assert "call_invariant_skeleton" in {a["intent"] for a in model.get("actions", [])}
    assert "call Bridge." in blob


def test_near_frontier_bridge_surfaces_without_claiming_callable_now() -> None:
    view = {
        "proof_status": {"status": "open", "goal_type": "pRHL",
                         "view_focus": "relational_program", "current_layer": "call_site"},
        "current_goal": {"lines": ["c2 <@ ChaCha.enc(k,n,p); c1 <@ EncRnd.cc(n,p);"]},
        "program_frontier": {"focus": {"frontier_call_sites": 2}},
        "call_site_surface": {
            "state": "tail_blocked_named_call",
            "named_handles": [{
                "symbol": "equ_cc",
                "callable_now": False,
                "frontier_live": False,
                "requires_cut_to_frontier": True,
                "call_candidate_kind": "needs_frontier_exposure",
                "frontier_status": "requires_cut",
                "exact_signature_known": True,
                "name_resolution_status": "resolved_local_declaration",
                "instantiation_binding_status": "has_call_elaboration",
                "matched_call_sites": [
                    {"side": "left", "statement_path": "6", "procedure": "ChaCha.enc"},
                    {"side": "right", "statement_path": "4", "procedure": "EncRnd.cc"},
                ],
                "procedures": ["ChaCha.enc", "EncRnd.cc"],
            }],
            "exposure": {
                "symbol": "chacha_enc1",
                "action": {
                    "kind": "expose_last_call_frontier",
                    "tactic_shape": "seq 1 1 : <invariant preserving the call lemma postcondition>.",
                    "tactic_family": "procedure_transform",
                    "reason": "the matching call pair exists before the last-call frontier",
                },
            },
        },
    }

    facts = _call_fact_dict(view)
    blob = json.dumps(facts, ensure_ascii=False)
    assert "direct_current_call" not in facts
    assert "near_frontier_bridge" in facts
    assert "equ_cc" in blob
    assert "seq 1 1" in blob
    assert "needs frontier exposure before call" in blob


def test_deep_surgery_surfaces_near_frontier_bridge_context() -> None:
    view = {
        "proof_status": {"status": "open", "goal_type": "pRHL",
                         "view_focus": "relational_program", "current_layer": "call_site"},
        "current_goal": {"lines": [
            "c2 <@ ChaCha.enc(k,n,p)     c1 <@ EncRnd.cc(n,p)"
        ]},
        "program_frontier": {"focus": {"frontier_call_sites": 2, "live_call_sites": 2}},
        "call_site_surface": {
            "state": "tail_blocked_named_call",
            "named_handles": [{
                "symbol": "equ_cc",
                "callable_now": False,
                "frontier_live": False,
                "requires_cut_to_frontier": True,
                "call_candidate_kind": "needs_frontier_exposure",
                "exact_signature_known": True,
                "live_call_site_ids": ["left:6:ChaCha.enc", "right:4:EncRnd.cc"],
            }],
            "exposure": {
                "action": {
                    "kind": "expose_last_call_frontier",
                    "tactic_shape": "seq 6 0 : <invariant preserving the call lemma postcondition>.",
                },
            },
        },
    }

    panel = _panel(view)
    facts = {item["key"]: item for item in panel.get("facts", [])}
    blob = json.dumps(panel, ensure_ascii=False)
    assert panel["panel_id"] == "deep_surgery"
    assert "near_frontier_bridge" in facts
    assert "equ_cc" in blob
    assert "seq 6 0" in blob


def _body_view(goal_type: str, *, layer: str = "procedure_body",
               view_focus: str = "procedure_frontier", frontier_call_sites: int = 0) -> dict:
    return {
        "proof_status": {"status": "open", "goal_type": goal_type,
                         "view_focus": view_focus, "current_layer": layer},
        "current_goal": {"lines": ["g" * 60]},
        "program_frontier": {"focus": {"frontier_call_sites": frontier_call_sites,
                                       "live_call_sites": 1}},
    }


def test_single_sided_goal_never_routes_to_two_sided_surgery() -> None:
    # PBound L4 (2209 trip): a single-sided `hoare[... ==> true]` first leg of a
    # bd-hoare `seq` got the TWO-SIDED surgery panel (sim/swap/coupling/"both
    # sides"). The fresh agent distrusted the (correct) plain goal as "lossy" and
    # burned the run on bypr/smt. A single-sided goal has no two sides — it must
    # fall through to `plain` (bare goal), the exact form L1 proved PBound with.
    for gt in ("hoare", "phoare", "bdhoare"):
        assert _phase(_body_view(gt)) == "plain", gt
        # also the seq_cut view_focus path, and the call_site-with-no-frontier-call path
        assert _phase(_body_view(gt, view_focus="seq_cut")) == "plain", gt
        assert _phase(_body_view(gt, layer="call_site",
                                    frontier_call_sites=0)) == "plain", gt


def test_relational_goal_still_routes_to_surgery() -> None:
    # Control: a genuine two-sided equiv/pRHL goal MUST still get the surgery focus
    # (the single-sided gate must not over-fire and strip surgery from relational work).
    assert _phase(_body_view("equiv")) == "deep_surgery"
    assert _phase(_body_view("equiv", view_focus="seq_cut")) == "deep_surgery"
    # an unclassified goal_type keeps the prior (permissive) behaviour
    assert _phase(_body_view("")) == "deep_surgery"


def _opener_view(lines: "list[str]") -> dict:
    return {"current_goal": {"lines": lines}, "facts_and_diagnostics": {"facts": {}}}


def test_opener_has_no_single_route_prescription() -> None:
    f = _opener_fact_dict(_opener_view(["Pr[G.main(x) @ &m : res] <= 1%r / n%r"]))
    assert "yours" not in f
    assert "allowed_reductions" not in f
    assert "reduce_with" not in f
    assert "probability_structure" in f
    assert "tactic_affordances" in f


def test_opener_step41_rhs_sum_surfaces_plural_affordances() -> None:
    f = _opener_fact_dict(_opener_view([
        "Pr[Split1.IdealAll.MainD(G9(BNR_Adv(A)), SplitC2.RO_Pair(ROin, ROout)).distinguish",
        "   () @ &m : res] <=",
        "Pr[UFCMA(RO).distinguish() @ &m : res \\/ UFCMA.bad2] +",
        "Pr[UFCMA(RO).distinguish() @ &m : UFCMA.bad1]",
    ]))
    summary = f["probability_structure"]
    assert "RHS sum of 2 Pr terms" in summary
    assert "RHS Pr terms share program/memory" in summary
    assert "(res \\/ UFCMA.bad2) \\/ UFCMA.bad1" in summary
    forms = " ".join(f["tactic_affordances"])
    assert "top-level" in forms and "apply" in forms
    assert "supporting/order subgoal" in forms and "rewrite" in forms
    assert "downstream only" in forms and "byequiv" in forms
    assert "not directly to the original RHS-sum goal" in forms
    assert "ler_trans" not in forms


def test_opener_compound_pr_difference_lists_families_without_answer_lemmas() -> None:
    # Synthetic `|Pr - Pr| <= sum-of-bounds` goal (identifiers renamed from a
    # held-out MAC corpus run; goal shape preserved).
    f = _opener_fact_dict(_opener_view([
        "valid_init sigma q =>",
        "`|Pr[Dist_Mac(Adv, MacA(E1)).main(sigma, q) @ &m : res] -",
        "  Pr[Dist_Mac(Adv, MacB(E1, E2, E3)).main(sigma, q) @ &m : res]| <=",
        "eps_rng sigma q + eps_dom sigma q + eps_bad sigma q",
    ]))
    forms = " ".join(f["tactic_affordances"])
    assert "apply" in forms and "rewrite" in forms
    assert "MacA_MacB" not in forms and "Simul" not in forms


def test_probability_opener_stops_after_byphoare_enters_single_program_obligation() -> None:
    opener = {
        "proof_status": {
            "status": "open",
            "remaining_goals": 1,
            "current_layer": "pr",
            "goal_type": "probability",
        },
        "current_goal": {"lines": [
            "Pr[Guess(G).main(x0) @ &m :",
            "   phi (glob G) res.`2 /\\",
            "   let k = psi (glob G) res.`2 in res.`1 = if 0 <= k < bound then k else 0] =",
            "1%r / bound%r * Pr[G.main(x0) @ &m : phi (glob G) res]",
        ]},
    }
    byphoare_shell = {
        "proof_status": {
            "status": "open",
            "remaining_goals": 1,
            "current_layer": "pr",
            "goal_type": "probability",
        },
        "current_goal": {"lines": [
            "pre = (glob G) = (glob G){m} /\\ x0 = arg",
            "",
            "    Guess(G).main",
            "    [=] 1%r / bound%r * Pr[G.main(x0) @ &m : phi (glob G) res]",
            "",
            "post =",
            "  phi (glob G) res.`2 /\\",
            "  let k = psi (glob G) res.`2 in res.`1 = if 0 <= k < bound then k else 0",
        ]},
    }
    proc_body = {
        "proof_status": {
            "status": "open",
            "remaining_goals": 1,
            "current_layer": "pr",
            "goal_type": "probability",
        },
        "current_goal": {"lines": [
            "Context : hr: {i : int, x : tin, o : tres}",
            "Bound   : [=] 1%r / bound%r * p",
            "",
            "pre = (glob G) = (glob G){m} /\\ x0 = x",
            "",
            "(1)  o <@ G.main(x)",
            "(2)  i <$ [0..bound - 1]",
            "",
            "post =",
            "  phi (glob G) (i, o).`2 /\\",
            "  let k = psi (glob G) (i, o).`2 in",
            "  (i, o).`1 = if 0 <= k < bound then k else 0",
        ]},
        "program_frontier": {
            "current_frontier_scope": {
                "frontier": {
                    "left": {
                        "head": "call",
                        "path": "1",
                        "statement": "o <@ G.main(x)",
                        "procedure": "G.main",
                    },
                },
                "lookahead_after_frontier": [
                    {
                        "side": "left",
                        "path": "2",
                        "head": "sample",
                        "statement": "i <$ [0..bound - 1]",
                    }
                ],
            },
        },
    }

    assert _model(opener)["phase"] == "opener"
    assert _model(byphoare_shell)["phase"] == "plain"
    assert "primary_panel" not in _model(byphoare_shell)
    assert _model(proc_body)["phase"] == "plain"
    assert "primary_panel" not in _model(proc_body)


def test_opener_single_pr_keeps_multiple_possible_families() -> None:
    f = _opener_fact_dict(_opener_view(["Pr[G.main(x) @ &m : res] = 1%r / n%r"]))
    forms = " ".join(f["tactic_affordances"])
    assert "byphoare" in forms
    assert "rewrite" in forms
    assert "byequiv" in forms


def test_opener_two_program_relation_is_not_marked_as_rhs_sum() -> None:
    for goal in (
        "Pr[G0.main(x) @ &m : res] <= Pr[G1.main(x) @ &m : res \\/ bad]",
        "Pr[A.main(x) @ &m : res] = Pr[B.main(x) @ &m : res]",
    ):
        f = _opener_fact_dict(_opener_view([goal]))
        assert "RHS sum" not in f["probability_structure"]
        forms = " ".join(f["tactic_affordances"])
        assert "byequiv" in forms and "rewrite" in forms


def test_opener_same_rhs_program_sum_does_not_collapse_to_one_family() -> None:
    f = _opener_fact_dict(_opener_view([
        "Pr[Exp(A, F, Plog).main() @ &m : res] <=",
        "Pr[Exp(A, F, Psample).main() @ &m : res] +",
        "Pr[Exp(A, F, Psample).main() @ &m : Bad P.logP F.m]",
    ]))
    summary = f["probability_structure"]
    forms = " ".join(f["tactic_affordances"])
    assert "RHS Pr terms share program/memory" in summary
    assert "top-level" in forms and "apply" in forms
    assert "supporting/order subgoal" in forms and "rewrite" in forms
    assert "downstream only" in forms and "byequiv" in forms


def test_opener_status_marker_pipe_does_not_trigger_route_contract() -> None:
    f = _opener_fact_dict(_opener_view([
        "- Pr[A.main() @ &m : res] = - Pr[B.game() @ &m : res] [315|check]"
    ]))
    blob = json.dumps(f, ensure_ascii=False)
    assert "allowed_reductions" not in f
    assert "ler_trans" not in blob


def test_surgery_where_does_not_claim_both_sides_on_one_sided_frontier() -> None:
    # The frontier line hardcoded "both sides" even when branch_alignment said
    # `one-sided_frontier` and the right column was a placeholder. That mis-framed a
    # one-sided frontier as a two-sided alignment problem.
    one_sided = {"program_frontier": {"frontier_alignment": {
        "first_instruction_alignment": {"branch_alignment": "one-sided_frontier",
                                         "left_head": "call"},
        "rows": [{"role": "call frontier", "left": "o <@ G.main(x)",
                  "right": "no matching right-side call at this frontier"}]}}}
    where = " ".join(_surgery_where(one_sided))
    assert "both sides" not in where
    assert "left side only" in where and "o <@ G.main(x)" in where
    # a genuinely aligned two-sided frontier still reads "both sides"
    two_sided = {"program_frontier": {"frontier_alignment": {
        "first_instruction_alignment": {"branch_alignment": "aligned_frontier",
                                         "left_head": "call", "right_head": "call"},
        "rows": [{"role": "call frontier", "left": "x <@ A.f()", "right": "y <@ A.f()"}]}}}
    assert "both sides" in " ".join(_surgery_where(two_sided))


def test_surgery_where_fix_b2_samples_dedup_placeholders() -> None:
    # FIX-B2 (re-audit ①, grounded in captured raw frontiers br93 i35 / step2_1 i61):
    #  (a) a `<$` sample (analyzer role "sample inside frontier") is surfaced as a SAMPLE,
    #      never as a call frontier (the old `"frontier" in role` matched the substring);
    #  (b) a both-sides call whose two columns DIFFER shows both wrappers, and a redundant
    #      unpaired re-emission of an already-paired call is deduped;
    #  (c) a placeholder ("no matching …") is never shown as the frontier content.
    # (a)
    v = {"program_frontier": {"frontier_alignment": {"rows": [
        {"role": "sample inside frontier", "left": "k <$ dkey", "right": "k <$ dkey"},
    ]}}}
    out = _surgery_where(v)
    assert any(l.startswith("sample:") and "k <$ dkey" in l for l in out)
    assert not any(l.startswith("frontier:") for l in out)
    # (b)
    v = {"program_frontier": {"frontier_alignment": {"rows": [
        {"role": "call frontier", "left": "b <@ A(P).main()", "right": "b <@ A(Q).main()"},
        {"role": "call frontier",
         "left": "no matching left-side call at this frontier", "right": "b <@ A(Q).main()"},
    ]}}}
    out = _surgery_where(v)
    frontier_lines = [l for l in out if l.startswith("frontier:")]
    assert len(frontier_lines) == 1                                  # duplicate deduped
    assert "A(P).main()" in frontier_lines[0] and "A(Q).main()" in frontier_lines[0]  # both wrappers
    # (c)
    v = {"program_frontier": {"frontier_alignment": {
        "first_instruction_alignment": {"branch_alignment": "one-sided_frontier"},
        "rows": [{"role": "call frontier",
                  "left": "no matching left-side call at this frontier",
                  "right": "o <@ G.main(x)"}]}}}
    out = _surgery_where(v)
    assert any("right side only" in l and "o <@ G.main(x)" in l for l in out)
    assert not any("no matching" in l for l in out)


def test_surgery_where_uses_current_frontier_scope_for_call_pair() -> None:
    view = {"program_frontier": {"current_frontier_scope": {
        "frontier": {
            "kind": "call_pair",
            "left": {"statement": "c2 <@ ChaCha(CCRO(...)).enc(k, n, p2)", "procedure": "ChaCha.enc"},
            "right": {"statement": "c1 <@ EncRnd.cc(n, p1)", "procedure": "EncRnd.cc"},
        },
    }}}
    out = _surgery_where(view)
    assert len([line for line in out if "frontier:" in line]) == 1
    line = out[0]
    assert line.startswith("current frontier:")
    assert "both sides" in line
    assert "ChaCha" in line and "EncRnd.cc" in line
    assert "right side only" not in line


def test_surgery_where_keeps_future_calls_in_lookahead_not_current_where() -> None:
    view = {"program_frontier": {"current_frontier_scope": {
        "setup": {
            "left": {"paths": ["1", "2", "3", "4", "5"], "summary": "5 setup statement(s): p0 <- p; p1 <- p0; k <- Mem.k; ... (2 more)"},
            "right": {"paths": ["1", "2", "3"], "summary": "3 setup statement(s): p0 <- p; nap <- p0; (n, a, p1) <- nap"},
        },
        "frontier": {
            "kind": "call_pair",
            "left": {"path": "6", "statement": "c2 <@ ChaCha(CCRO(SplitD.RO_DOM(...))).enc(k, n, p2)", "procedure": "ChaCha.enc"},
            "right": {"path": "4", "statement": "c1 <@ EncRnd.cc(n, p1)", "procedure": "EncRnd.cc"},
        },
        "lookahead_after_frontier": [
            {"side": "left", "path": "11", "statement": "b <@ CCRO(SplitD.RO_DOM(...)).cc(k0, n0, C.ofintd 0)", "procedure": "CCRO.cc"},
            {"side": "right", "path": "5", "statement": "t <@ UFCMA(RO).set_bad1(map ...)", "procedure": "UFCMA.set_bad1"},
        ],
    }}}
    out = _surgery_where(view)
    frontier_lines = [line for line in out if "frontier:" in line]
    assert len(frontier_lines) == 1
    line = frontier_lines[0]
    assert "ChaCha" in line and "EncRnd.cc" in line
    assert "b <@" not in line and "set_bad1" not in line
    lookahead = " ".join(_surgery_lookahead_after_frontier(view))
    assert "b <@ CCRO" in lookahead and "set_bad1" in lookahead


def test_surgery_where_current_scope_is_side_aware_and_not_overmatched() -> None:
    view = {"program_frontier": {"current_frontier_scope": {
        "setup": {
            "left": {
                "paths": [str(i) for i in range(1, 10)],
                "summary": "9 setup statement(s): k0 <- k; n0 <- n; a0 <- a; ... (6 more)",
            },
        },
        "frontier": {
            "kind": "call_vs_call",
            "left": {
                "head": "call",
                "path": "10",
                "statement": "r1 <@ SplitC2.RO_Pair(SplitC2.I1.RO, SplitC2.I2.RO).get(x0)",
                "procedure": "SplitC2.RO_Pair.get",
            },
            "right": {
                "head": "call",
                "path": "1",
                "statement": "t <@ UFCMA(RO).set_bad1(map (fun (c5 : ciphertext) => c5.`4) Mem.lc)",
                "procedure": "UFCMA.set_bad1",
            },
        },
    }}}

    out = _surgery_where(view)
    assert out[0].startswith("left setup before current frontier")
    assert "left positions 1-9" in out[0]
    assert "(positions 1-9)" not in out[0]
    assert "live calls on both sides, not a matched call offer" in out[1]
    assert "ciphertex [" not in out[1]
    assert "ciphertext" in out[1]


def test_surgery_where_setup_summary_uses_safe_code_spans_for_ec_backticks() -> None:
    view = {"program_frontier": {"current_frontier_scope": {
        "setup": {
            "left": {
                "paths": [str(i) for i in range(1, 10)],
                "summary": "9 setup statement(s): k0 <- k; n0 <- n; a0 <- a; ... (6 more)",
            },
            "right": {
                "paths": ["1"],
                "summary": "lt <- map (fun (c5 : ciphertext) => c5.`4) (filter (fun (c5 : ciphertext) => c5.`1 = n) Mem.lc)",
            },
        },
        "frontier": {
            "kind": "right_sample",
            "right": {
                "head": "sample",
                "path": "2",
                "statement": "t0 <$ dpoly_out",
            },
        },
    }}}

    setup_line = _surgery_where(view)[0]
    assert "asymmetric setup before current frontier" in setup_line
    assert "right positions 1" in setup_line
    assert "c5.`4" in setup_line
    assert "``" in setup_line
    assert "ciphertext`" not in setup_line


def test_surgery_where_current_scope_setup_call_is_not_sp_wp() -> None:
    view = {
        "proof_status": {
            "status": "open",
            "current_layer": "deep_surgery",
            "view_focus": "seq_cut",
            "goal_type": "pRHL",
        },
        "current_goal": {"goal_type": "pRHL", "lines": ["x <@ A.main()"]},
        "program_frontier": {
            "current_frontier_scope": {
                "setup": {
                    "left": {
                        "paths": ["1"],
                        "summary": (
                            "SplitC2.RO_Pair(SplitC2.I1.RO, SplitC2.I2.RO).init() "
                            "[call: SplitC2.RO_Pair(SplitC2.I1.RO, SplitC2.I2.RO).init() "
                            "-- use inline/call, not sp/wp]"
                        ),
                    },
                    "right": {
                        "paths": ["1", "2", "3", "4"],
                        "summary": (
                            "4 setup statement(s): UFCMA.bad1 <- false; "
                            "UFCMA.cbad1 <- 0; UFCMA.bad2 <- false; ... (1 more)"
                        ),
                    },
                },
                "frontier": {
                    "kind": "call_pair",
                    "left": {
                        "head": "call",
                        "path": "2",
                        "statement": "r <@ G9(BNR_Adv(A), RO).distinguish(x)",
                        "procedure": "G9.distinguish",
                    },
                    "right": {
                        "head": "call",
                        "path": "5",
                        "statement": "b <@ CPA_game(CCA_CPA_Adv(BNR_Adv(A)), UFCMA(RO).O).main()",
                        "procedure": "CPA_game.main",
                    },
                },
            },
        },
    }

    setup_line = _surgery_where(view)[0]
    assert "procedure-call prefix" in setup_line
    assert "sp" not in setup_line and "wp" not in setup_line
    assert "inline" not in setup_line and "call `" not in setup_line
    assert "[call:" not in setup_line
    assert "SplitC2.RO_Pair" in setup_line
    choices = {
        name
        for action in _model(view).get("actions", [])
        if action["intent"] == "tactic_forms"
        for name in action["choices"]["name"]
    }
    assert "inline" in choices


def test_surgery_where_labels_mismatched_if_vs_call_frontier() -> None:
    view = {"program_frontier": {"current_frontier_scope": {
        "frontier": {
            "kind": "if_vs_call",
            "left": {
                "path": "9",
                "statement": "if (SplitD.test x) {",
            },
            "right": {
                "path": "1",
                "statement": "t <@ UFCMA(RO).set_bad1(map (fun (c5 : ciphertext) => c5.`4) Mem.lc)",
                "procedure": "UFCMA.set_bad1",
            },
        },
    }}}

    line = _surgery_where(view)[0]
    assert "left guarded if vs right call" in line
    assert "current frontier: both sides" not in line
    assert "c5.`4" in line


def test_surgery_where_setup_before_guard_does_not_prescribe_sp_wp() -> None:
    view = {"program_frontier": {"current_frontier_scope": {
        "setup": {
            "left": {
                "paths": [str(i) for i in range(1, 9)],
                "summary": "8 setup statement(s): k0 <- k; n0 <- n; a0 <- a; ... (5 more)",
            },
            "right": {
                "paths": ["2"],
                "summary": "c0 <- (n, a, c1, t)",
            },
        },
        "frontier": {
            "kind": "left_if",
            "left": {
                "head": "if",
                "path": "9",
                "statement": "if (SplitD.test x) {",
            },
        },
    }}}

    setup_line = _surgery_where(view)[0]
    assert "asymmetric setup before visible guard" in setup_line
    assert "prefix statements" in setup_line
    assert "absorb with" not in setup_line


def test_sample_only_frontier_does_not_surface_random_alignment_block() -> None:
    view = {
        "proof_status": {"status": "open", "remaining_goals": 1, "view_focus": "deep_surgery"},
        "current_goal": {"goal_type": "pRHL", "lines": ["k <$ dkey     (1) b1 <@ A.main()"]},
        "program_frontier": {"current_frontier_scope": {
            "setup": {
                "left": {
                    "paths": ["1", "2", "3", "4", "5"],
                    "summary": "5 setup statement(s): SplitC2.I1.RO.m <- empty; SplitC2.I2.RO.m <- empty; ...",
                },
                "right": {
                    "paths": ["1", "2", "3", "4"],
                    "summary": "4 setup statement(s): Mem.log <- empty; Mem.lc <- []; BNR.lenc <- []; BNR.ndec <- 0",
                },
            },
            "frontier": {
                "kind": "sample_vs_call",
                "left": {
                    "head": "sample",
                    "path": "6",
                    "statement": "k <$ dkey",
                },
                "right": {
                    "head": "call",
                    "path": "5",
                    "statement": "b1 <@ A(BNR(CPA_CCA_Orcls(EncRnd))).main()",
                    "procedure": "A.main",
                },
            },
        }},
    }

    skel = _render_surgery_skeleton(view)
    assert skel is not None
    assert "branch_sample_alignment" not in skel
    assert any("left sample vs right call" in line for line in skel["where"])
    panel_blob = json.dumps(_panel(view), ensure_ascii=False)
    assert "Guarded branch / random alignment" not in panel_blob
    assert "current sample" not in panel_blob


def test_sample_frontier_with_list_residual_surfaces_staging_boundary() -> None:
    view = {
        "proof_status": {"status": "open", "remaining_goals": 9, "view_focus": "deep_surgery"},
        "current_goal": {"goal_type": "pRHL", "lines": [
            "t <$ dpoly_out                          (1--)  t <$ dpoly_out",
            "post =",
            "  (nth (w1, w2) (UFCMA_l.lbad1 ++ map (fun t => (t0, t)) lt) nth0).`1 =",
            "  (nth (w1, w2) (UFCMA_l.lbad1 ++ map (fun t => (t0, t)) lt) nth0).`2",
        ]},
        "program_frontier": {"current_frontier_scope": {
            "frontier": {
                "kind": "sample",
                "left": {"head": "sample", "path": "1", "statement": "t <$ dpoly_out"},
                "right": {"head": "sample", "path": "1", "statement": "t <$ dpoly_out"},
            },
        }},
    }

    panel = _panel(view)
    staging = _fact(panel, "frontier_residual_staging")
    blob = json.dumps(staging, ensure_ascii=False)
    assert "live sample frontier remains" in blob
    assert "nth" in blob and "size" not in blob
    assert "SMT/rewrite lemmas apply to the exposed residual" in blob


def test_pure_residual_does_not_surface_program_staging_boundary() -> None:
    view = {
        "proof_status": {
            "status": "open",
            "remaining_goals": 1,
            "current_layer": "pure_logic",
            "view_focus": "ambient_logic",
            "goal_type": "ambient",
        },
        "current_goal": {
            "goal_type": "ambient",
            "lines": [
                "nth (w1, w2) (xs ++ map f ys) i = nth (w1, w2) xs i",
            ],
        },
        "program_frontier": {"current_frontier_scope": {
            "frontier": {
                "kind": "sample",
                "left": {"head": "sample", "path": "1", "statement": "t <$ dpoly_out"},
            },
        }},
    }

    model = _model(view)
    assert model["phase"] != "deep_surgery"
    assert "frontier_residual_staging" not in json.dumps(model, ensure_ascii=False)


def test_ambient_logic_residual_ignores_stale_program_frontier_metadata() -> None:
    view = {
        "proof_status": {
            "status": "open",
            "remaining_goals": 4,
            "current_layer": "deep_surgery",
            "view_focus": "ambient_logic",
            "goal_type": "ambient",
        },
        "current_goal": {
            "goal_type": "ambient",
            "lines": [
                "&m: {n : nonce}",
                "------------------------------------------------------------",
                "0 < C.max_counter + 1",
            ],
        },
        "program_frontier": {
            "authority": "proof-state analysis",
            "view_focus": "ambient_logic",
        },
        "inspect_lookup_handles": {"ask_manager_for": [
            {"intent": "tactic_forms", "payload": {"name": "rewrite"}},
        ]},
    }

    model = _model(view)
    assert model["phase"] == "pure_logic"
    assert model["primary_panel"]["panel_id"] == "pure_logic"
    blob = json.dumps(model, ensure_ascii=False)
    assert "Program frontier" not in blob
    assert "Surgery -- align or decompose the two sides" not in blob


def test_ambient_logic_map_update_does_not_trigger_surgery() -> None:
    view = {
        "proof_status": {
            "status": "open",
            "remaining_goals": 5,
            "current_layer": "ambient_logic",
            "view_focus": "ambient_logic",
            "goal_type": "ambient",
        },
        "current_goal": {
            "goal_type": "ambient",
            "lines": [
                "&m: {n : nonce, c0 : ciphertext}",
                "------------------------------------------------------------",
                "Mem.log{1}.[c0{1} <- p0{1}] = Mem.log{2}.[c0{2} <- p0{2}] /\\",
                "BNR.lenc{1} = BNR.lenc{2}",
            ],
        },
        "program_frontier": {
            "authority": "proof-state analysis",
            "view_focus": "ambient_logic",
        },
        "inspect_lookup_handles": {"ask_manager_for": [
            {"intent": "tactic_forms", "payload": {"name": "rewrite"}},
        ]},
    }

    model = _model(view)
    assert model["phase"] == "pure_logic"
    assert model["primary_panel"]["panel_id"] == "pure_logic"
    blob = json.dumps(model, ensure_ascii=False)
    assert "Program frontier" not in blob
    assert "Surgery -- align or decompose the two sides" not in blob


def test_closed_candidate_does_not_render_empty_surgery_panel() -> None:
    view = {
        "proof_status": {
            "status": "candidate_closed_pending_qed",
            "remaining_goals_known": False,
            "current_layer": "closed_candidate",
            "view_focus": "closed_candidate",
            "goal_type": "ambient",
        },
        "current_goal": {
            "goal_type": "ambient",
            "lines": ["No more goals", "[383|check]>"],
        },
        "program_frontier": {
            "authority": "proof-state analysis",
            "view_focus": "closed_candidate",
        },
    }

    model = _model(view)
    assert model["phase"] == "closed_candidate"
    assert "primary_panel" not in model
    assert model["status"]["remaining_goals"] == 0
    assert model["status"]["remaining_goals_known"] is True
    blob = json.dumps(model, ensure_ascii=False)
    assert "Program frontier" not in blob
    assert "Surgery -- align or decompose the two sides" not in blob


def test_plain_hoare_side_condition_filters_stale_while_tactic_form() -> None:
    view = {
        "proof_status": {
            "status": "open",
            "remaining_goals": 4,
            "current_layer": "procedure_body",
            "view_focus": "plain",
            "goal_type": "hoare",
        },
        "current_goal": {
            "goal_type": "hoare",
            "lines": [
                "forall &m,",
                "  hoare[ k0 <- k; n0 <- n; c4 <- C.ofintd 0; x <- (n1, c4); :",
                "          pre ==> SplitD.test x ]",
            ],
        },
        "inspect_lookup_handles": {"ask_manager_for": [
            {"intent": "tactic_forms", "payload": {"name": "while"}},
        ]},
    }

    model = _model(view)
    assert model["phase"] == "plain"
    actions = [
        action for action in model.get("actions", [])
        if action["intent"] == "tactic_forms"
    ]
    assert actions
    choices = {
        name
        for action in actions
        for name in action["choices"]["name"]
    }
    assert "while" not in choices
    assert {"wp", "rewrite", "apply"} <= choices


def test_plain_hoare_side_condition_keeps_while_only_when_loop_visible() -> None:
    view = {
        "proof_status": {
            "status": "open",
            "current_layer": "procedure_body",
            "view_focus": "plain",
            "goal_type": "hoare",
        },
        "current_goal": {
            "goal_type": "hoare",
            "lines": [
                "hoare[ while (i < n) { i <- i + 1 } : P ==> Q ]",
            ],
        },
        "inspect_lookup_handles": {"ask_manager_for": []},
    }

    choices = {
        name
        for action in _model(view).get("actions", [])
        if action["intent"] == "tactic_forms"
        for name in action["choices"]["name"]
    }
    assert "while" in choices


def test_deep_surgery_groups_guards_swaps_and_sample_frontier() -> None:
    view = {
        "proof_status": {"status": "open", "remaining_goals": 8, "view_focus": "seq_cut"},
        "current_goal": {"goal_type": "pRHL", "lines": ["g"]},
        "program_frontier": {
            "current_frontier_scope": {
                "setup": {
                    "left": {
                        "paths": [str(i) for i in range(1, 10)],
                        "summary": "9 setup statement(s): k0 <- k; n0 <- n; a0 <- a; ... (6 more)",
                    },
                    "right": {
                        "paths": ["1"],
                        "summary": "lt <- map (fun (c5 : ciphertext) => c5.`4) Mem.lc",
                    },
                },
                "frontier": {
                    "kind": "right_sample",
                    "right": {
                        "head": "sample",
                        "path": "2",
                        "statement": "t0 <$ dpoly_out",
                    },
                },
            },
            "procedure_navigation": {"branch_guards": [
                {"side_index": 1, "at_path": "13", "guard": "x2 \\notin SplitC2.I1.RO.m"},
                {"side_index": 1, "at_path": "17", "guard": "x3 \\notin SplitC2.I2.RO.m"},
                {"side_index": 2, "at_path": "3", "guard": "UFCMA.cbad1 < qenc /\\ size lt <= qdec"},
                {"side_index": 2, "at_path": "8", "guard": "x1 \\notin RO.m"},
            ]},
        },
        "candidate_moves": {"moves": [
            {"tactic": "swap{1} 16 -14."},
            {"tactic": "swap{2} 8 -7."},
        ]},
    }

    skel = _render_surgery_skeleton(view)
    assert skel is not None
    assert "branch_sample_alignment" in skel
    assert "swap_offsets" not in skel
    assert not any("rcondt" in line for line in skel["where"])
    alignment = skel["branch_sample_alignment"]
    assert alignment["stage"] == "guarded branch normalization before random coupling"
    assert alignment["current_sample_frontiers"][0]["statement"] == "t0 <$ dpoly_out"
    assert alignment["visible_guarded_ifs"][0]["next_if_forms"] == [
        "rcondt{1} ^if{1}",
        "rcondf{1} ^if{1}",
    ]
    assert alignment["visible_guarded_ifs"][1].get("next_if_forms") in (None, [])
    assert alignment["swap_frames"][0]["form"] == "swap{1} 16 <offset>."

    panel = _model(view)["primary_panel"]
    blob = json.dumps(panel, ensure_ascii=False)
    assert "Guarded branch / random alignment" in blob
    assert "swap{1} 16 -14" not in blob
    assert "rcondt{1} ^if{1}" in blob


def test_deep_surgery_surfaces_whole_program_structure_before_local_where() -> None:
    view = {
        "proof_status": {
            "status": "open",
            "remaining_goals": 1,
            "view_focus": "relational_program",
            "current_layer": "procedure_body",
            "goal_type": "pRHL",
        },
        "current_goal": {"goal_type": "pRHL", "lines": ["pre", "post"]},
        "program_frontier": {
            "current_frontier_scope": {
                "setup": {
                    "left": {
                        "paths": ["1", "2", "3", "4", "5"],
                        "summary": (
                            "5 setup statement(s): SplitC2.I1.RO.m <- empty; "
                            "SplitC2.I2.RO.m <- empty; () <- x; ... (2 more)"
                        ),
                    },
                    "right": {
                        "paths": ["1", "2", "3", "4"],
                        "summary": (
                            "4 setup statement(s): Mem.log <- empty; Mem.lc <- []; "
                            "BNR.lenc <- []; BNR.ndec <- 0"
                        ),
                    },
                },
                "frontier": {
                    "kind": "left_sample_vs_right_call",
                    "left": {
                        "head": "sample",
                        "path": "6",
                        "statement": "k <$ dkey",
                    },
                    "right": {
                        "head": "call",
                        "path": "5",
                        "statement": "b1 <@ A(BNR(CPA_CCA_Orcls(EncRnd))).main()",
                        "procedure": "A.main",
                    },
                },
                "lookahead_after_frontier": [
                    {
                        "side": "left",
                        "path": "12",
                        "statement": "b3 <@ A(BNR(CPA_CCA_Orcls(RealOrcls(...)))).main()",
                        "procedure": "A.main",
                    }
                ],
            },
        },
    }

    panel = _panel(view)
    keys = [fact["key"] for fact in panel["facts"]]
    assert keys.index("whole_program_structure") < keys.index("where")
    fact = _fact(panel, "whole_program_structure")
    assert fact["left_regions"] == "setup-block(5) | sample | call A.main"
    assert fact["right_regions"] == "setup-block(4) | call A.main"
    assert any("current frontier heads differ" in line for line in fact["observations"])
    assert "transitivity" not in json.dumps(fact, ensure_ascii=False).lower()


def test_deep_surgery_notes_guarded_region_before_shared_while() -> None:
    view = {
        "proof_status": {
            "status": "open",
            "remaining_goals": 1,
            "view_focus": "relational_program",
            "current_layer": "procedure_body",
            "goal_type": "pRHL",
        },
        "current_goal": {"goal_type": "pRHL", "lines": ["pre", "post"]},
        "program_frontier": {
            "current_frontier_scope": {
                "setup": {
                    "left": {"paths": ["1"], "summary": "k <- 0"},
                    "right": {
                        "paths": ["1", "2"],
                        "summary": "2 setup statement(s): k <- 0; m <- nth witness l i",
                    },
                },
                "frontier": {
                    "left": {
                        "head": "while",
                        "path": "2",
                        "statement": "while (k < size l) {",
                    },
                    "right": {
                        "head": "if",
                        "path": "3",
                        "statement": "if (m \\notin M.log) {",
                    },
                },
                "lookahead_after_frontier": [
                    {
                        "side": "right",
                        "path": "4",
                        "head": "while",
                        "statement": "while (k < size l) {",
                    },
                ],
            },
        },
    }

    fact = _fact(_panel(view), "whole_program_structure")
    assert fact["left_regions"] == "setup-block(1) | while"
    assert fact["right_regions"] == "setup-block(2) | guarded if | while"
    assert any(
        "intervening guarded region before a later top-level while" in line
        for line in fact["observations"]
    )
    assert "eager" not in json.dumps(fact, ensure_ascii=False).lower()


def test_deep_surgery_surfaces_wrapper_call_shape() -> None:
    view = {
        "proof_status": {
            "status": "open",
            "remaining_goals": 1,
            "view_focus": "relational_program",
            "current_layer": "procedure_body",
            "goal_type": "pRHL",
        },
        "current_goal": {"goal_type": "pRHL", "lines": ["pre", "post"]},
        "program_frontier": {
            "current_frontier_scope": {
                "setup": {
                    "left": {
                        "paths": ["1"],
                        "summary": "RealOrcls(GenChaChaPoly(OCC(I))).init()",
                    },
                    "right": {
                        "paths": ["1"],
                        "summary": "IndBlock.init()",
                    },
                },
                "frontier": {
                    "left": {
                        "head": "call",
                        "path": "2",
                        "statement": "b <@ A(RealOrcls(GenChaChaPoly(OCC(I)))).main()",
                        "procedure": "A.main",
                    },
                    "right": {
                        "head": "call",
                        "path": "2",
                        "statement": "b <@ D(A, IndBlock).guess()",
                        "procedure": "D.guess",
                    },
                },
            },
        },
    }

    fact = _fact(_panel(view), "whole_program_structure")
    assert fact["left_regions"] == "setup-block(1) | call A.main"
    assert fact["right_regions"] == "setup-block(1) | call D.guess"
    assert any("setup prefixes differ" in line for line in fact["observations"])
    assert any("top-level call labels differ" in line for line in fact["observations"])


def test_deep_surgery_surfaces_wrapper_call_setup_difference() -> None:
    view = {
        "proof_status": {
            "status": "open",
            "remaining_goals": 2,
            "view_focus": "relational_program",
            "current_layer": "procedure_body",
            "goal_type": "pRHL",
        },
        "current_goal": {"goal_type": "pRHL", "lines": ["pre", "post"]},
        "program_frontier": {
            "current_frontier_scope": {
                "setup": {
                    "left": {
                        "paths": ["1", "2"],
                        "summary": "2 setup statement(s): F.init(); Plog.init()",
                    },
                    "right": {
                        "paths": ["1", "2"],
                        "summary": "2 setup statement(s): F.init(); Psample.init()",
                    },
                },
                "frontier": {
                    "left": {
                        "head": "call",
                        "path": "3",
                        "statement": "b <@ Exp(A, F, Plog).A.a()",
                        "procedure": "Exp.A.a",
                    },
                    "right": {
                        "head": "call",
                        "path": "3",
                        "statement": "b <@ Exp(A, F, Psample).A.a()",
                        "procedure": "Exp.A.a",
                    },
                },
            },
        },
    }

    fact = _fact(_panel(view), "whole_program_structure")
    assert fact["left_regions"] == "setup-block(2) | call A.a"
    assert fact["right_regions"] == "setup-block(2) | call A.a"
    assert fact["observations"] == [
        "setup prefixes differ before the top-level call region"
    ]


def test_deep_surgery_surfaces_matching_top_level_region_sequence_with_lookahead() -> None:
    view = {
        "proof_status": {
            "status": "open",
            "remaining_goals": 1,
            "view_focus": "relational_program",
            "current_layer": "procedure_body",
            "goal_type": "pRHL",
        },
        "current_goal": {"goal_type": "pRHL", "lines": ["pre", "post"]},
        "program_frontier": {
            "current_frontier_scope": {
                "setup": {
                    "left": {
                        "paths": ["1"],
                        "summary": "Log(LRO).init() [procedure-call prefix: Log(LRO).init()]",
                    },
                    "right": {
                        "paths": ["1"],
                        "summary": "Log(LRO).init() [procedure-call prefix: Log(LRO).init()]",
                    },
                },
                "frontier": {
                    "left": {
                        "head": "sample",
                        "path": "2",
                        "statement": "(pk, sk) <$ dkeys",
                    },
                    "right": {
                        "head": "sample",
                        "path": "2",
                        "statement": "(pk, sk) <$ dkeys",
                    },
                },
                "lookahead_after_frontier": [
                    {
                        "side": "left",
                        "path": "3",
                        "head": "call",
                        "statement": "(m0, m1) <@ A(Log(LRO)).a1(pk)",
                        "procedure": "A.a1",
                    },
                    {
                        "side": "right",
                        "path": "3",
                        "head": "call",
                        "statement": "(m0, m1) <@ A(Log(LRO)).a1(pk)",
                        "procedure": "A.a1",
                    },
                    {"side": "left", "path": "4", "head": "sample", "statement": "b <$ {0,1}"},
                    {"side": "right", "path": "4", "head": "sample", "statement": "b <$ {0,1}"},
                    {"side": "left", "path": "5", "head": "sample", "statement": "Game1.r <$ drand"},
                    {"side": "right", "path": "5", "head": "sample", "statement": "Game2.r <$ drand"},
                    {"side": "left", "path": "6", "head": "sample", "statement": "h <$ dptxt"},
                    {"side": "right", "path": "6", "head": "sample", "statement": "h <$ dptxt"},
                    {
                        "side": "left",
                        "path": "8",
                        "head": "call",
                        "statement": "b' <@ A(Log(LRO)).a2(c)",
                        "procedure": "A.a2",
                    },
                    {
                        "side": "right",
                        "path": "8",
                        "head": "call",
                        "statement": "b' <@ A(Log(LRO)).a2(c)",
                        "procedure": "A.a2",
                    },
                ],
            },
        },
    }

    fact = _fact(_panel(view), "whole_program_structure")
    assert fact["left_regions"] == (
        "setup-block(1) | sample | call A.a1 | sample | sample | sample | call A.a2"
    )
    assert fact["right_regions"] == fact["left_regions"]
    assert fact["observations"] == ["visible top-level region sequence matches across sides"]
    lookahead = _surgery_lookahead_after_frontier(view)
    assert lookahead == [
        "paired future regions:",
        "path 3: call A.a1",
        "path 4: sample `b <$ {0,1}`",
        "path 5: sample -- left `Game1.r <$ drand` / right `Game2.r <$ drand`",
        "path 6: sample `h <$ dptxt`",
        "path 8: call A.a2",
    ]


def test_deep_surgery_whole_program_keeps_later_top_level_calls_after_samples() -> None:
    view = {
        "proof_status": {
            "status": "open",
            "remaining_goals": 1,
            "view_focus": "relational_program",
            "current_layer": "procedure_body",
            "goal_type": "pRHL",
        },
        "current_goal": {"goal_type": "pRHL", "lines": ["pre", "post"]},
        "program_frontier": {
            "current_frontier_scope": {
                "setup": {
                    "left": {
                        "paths": ["1", "2"],
                        "summary": "2 setup statement(s): Log.qs <- []; LRO.m <- empty",
                    },
                },
                "frontier": {
                    "left": {
                        "head": "sample",
                        "path": "3",
                        "statement": "(pk, sk) <$ dkeys",
                    },
                    "right": {
                        "head": "sample",
                        "path": "1",
                        "statement": "(pk, sk) <$ dkeys",
                    },
                },
                "lookahead_after_frontier": [
                    {"side": "right", "path": "2", "head": "sample", "statement": "OWr.x <$ drand"},
                    {
                        "side": "left",
                        "path": "4",
                        "head": "call",
                        "statement": "(m0, m1) <@ A(Log(LRO)).a1(pk)",
                        "procedure": "A.a1",
                    },
                    {"side": "left", "path": "5", "head": "sample", "statement": "b <$ {0,1}"},
                    {"side": "left", "path": "6", "head": "sample", "statement": "Game2.r <$ drand"},
                    {"side": "left", "path": "7", "head": "sample", "statement": "h <$ dptxt"},
                    {
                        "side": "right",
                        "path": "7",
                        "head": "call",
                        "statement": "(m0, m1) <@ A(Log(LRO)).a1(pk0)",
                        "procedure": "A.a1",
                    },
                    {
                        "side": "left",
                        "path": "9",
                        "head": "call",
                        "statement": "b' <@ A(Log(LRO)).a2(c)",
                        "procedure": "A.a2",
                    },
                    {
                        "side": "right",
                        "path": "9",
                        "head": "call",
                        "statement": "b <@ A(Log(LRO)).a2(y, h)",
                        "procedure": "A.a2",
                    },
                ],
            },
        },
    }

    fact = _fact(_panel(view), "whole_program_structure")
    assert "call A.a2" in fact["left_regions"]
    assert "call A.a1" in fact["right_regions"]
    assert "call A.a2" in fact["right_regions"]
    lookahead = " ".join(_surgery_lookahead_after_frontier(view))
    assert "A(Log(LRO)).a2(c)" in lookahead
    assert "A(Log(LRO)).a2(y, h)" in lookahead


def test_deep_surgery_whole_program_notes_visible_call_label_difference() -> None:
    view = {
        "proof_status": {
            "status": "open",
            "remaining_goals": 1,
            "view_focus": "relational_program",
            "current_layer": "procedure_body",
            "goal_type": "pRHL",
        },
        "current_goal": {"goal_type": "pRHL", "lines": ["pre", "post"]},
        "program_frontier": {
            "current_frontier_scope": {
                "setup": {
                    "left": {
                        "paths": ["1"],
                        "summary": "Log(LRO).init() [procedure-call prefix: Log(LRO).init()]",
                    },
                },
                "frontier": {
                    "left": {
                        "head": "sample",
                        "path": "2",
                        "statement": "(pk, sk) <$ dkeys",
                    },
                    "right": {
                        "head": "sample",
                        "path": "1",
                        "statement": "(pk, sk) <$ dkeys",
                    },
                },
                "lookahead_after_frontier": [
                    {"side": "right", "path": "2", "head": "sample", "statement": "OWr.x <$ drand"},
                    {
                        "side": "left",
                        "path": "3",
                        "head": "call",
                        "statement": "(m0, m1) <@ A(Log(LRO)).a1(pk)",
                        "procedure": "A.a1",
                    },
                    {
                        "side": "right",
                        "path": "3",
                        "head": "call",
                        "statement": "x' <@ I(A).invert(pk, f pk OWr.x)",
                        "procedure": "I.invert",
                    },
                    {"side": "left", "path": "4", "head": "sample", "statement": "b <$ {0,1}"},
                    {"side": "left", "path": "5", "head": "sample", "statement": "Game2.r <$ drand"},
                    {
                        "side": "left",
                        "path": "8",
                        "head": "call",
                        "statement": "b' <@ A(Log(LRO)).a2(c)",
                        "procedure": "A.a2",
                    },
                ],
            },
        },
    }

    fact = _fact(_panel(view), "whole_program_structure")
    assert fact["left_regions"] == "setup-block(1) | sample | call A.a1 | sample | sample | call A.a2"
    assert fact["right_regions"] == "sample | sample | call I.invert"
    assert fact["observations"][0] == "visible top-level call labels differ across sides"


def test_deep_surgery_notes_shared_call_labels_at_different_positions() -> None:
    view = {
        "proof_status": {
            "status": "open",
            "remaining_goals": 1,
            "view_focus": "relational_program",
            "current_layer": "procedure_body",
            "goal_type": "pRHL",
        },
        "current_goal": {"goal_type": "pRHL", "lines": ["pre", "post"]},
        "program_frontier": {
            "current_frontier_scope": {
                "frontier": {
                    "left": {
                        "head": "call",
                        "path": "1",
                        "statement": "(x, w) <@ SchnorrPK.gen()",
                        "procedure": "SchnorrPK.gen",
                    },
                    "right": {
                        "head": "call",
                        "path": "1",
                        "statement": "(x, m, e, z) <@ Run(SchnorrPK).main()",
                        "procedure": "Run.main",
                    },
                },
                "lookahead_after_frontier": [
                    {
                        "side": "left",
                        "path": "2",
                        "head": "call",
                        "statement": "(m, s) <@ SchnorrPK.commit(x, w)",
                        "procedure": "SchnorrPK.commit",
                    },
                    {"side": "left", "path": "3", "head": "sample", "statement": "e <$ de"},
                    {
                        "side": "left",
                        "path": "4",
                        "head": "call",
                        "statement": "to <@ SpecialHVZKExperiment(SchnorrPK, SchnorrPKAlgorithms).main(x, e)",
                        "procedure": "SpecialHVZKExperiment.main",
                    },
                    {
                        "side": "left",
                        "path": "6",
                        "head": "while",
                        "statement": "while (to = None) {",
                    },
                    {
                        "side": "left",
                        "path": "8",
                        "head": "call",
                        "statement": "b <@ D.distinguish(x, t)",
                        "procedure": "D.distinguish",
                    },
                    {
                        "side": "right",
                        "path": "3",
                        "head": "call",
                        "statement": "b <@ D.distinguish(x, t)",
                        "procedure": "D.distinguish",
                    },
                ],
            },
        },
    }

    fact = _fact(_panel(view), "whole_program_structure")
    assert "call D.distinguish" in fact["left_regions"]
    assert "call D.distinguish" in fact["right_regions"]
    assert fact["observations"][0] == (
        "shared visible top-level call label(s) appear at different positions: call D.distinguish"
    )
    assert "eager" not in json.dumps(fact, ensure_ascii=False).lower()


def test_deep_surgery_specific_call_position_observation_suppresses_generic_call_reorder() -> None:
    view = {
        "proof_status": {
            "status": "open",
            "remaining_goals": 1,
            "view_focus": "relational_program",
            "current_layer": "procedure_body",
            "goal_type": "pRHL",
        },
        "current_goal": {"goal_type": "pRHL", "lines": ["pre", "post"]},
        "program_frontier": {
            "current_frontier_scope": {
                "frontier": {
                    "left": {"head": "sample", "path": "1", "statement": "sk0 <$ dt"},
                    "right": {"head": "sample", "path": "1", "statement": "x <$ dt"},
                },
                "lookahead_after_frontier": [
                    {"side": "right", "path": "2", "head": "sample", "statement": "y <$ dt"},
                    {
                        "side": "left",
                        "path": "3",
                        "head": "call",
                        "statement": "(m0, m1) <@ A.choose(pk)",
                        "procedure": "A.choose",
                    },
                    {"side": "left", "path": "4", "head": "sample", "statement": "b <$ {0,1}"},
                    {"side": "left", "path": "7", "head": "sample", "statement": "y <$ dt"},
                    {
                        "side": "right",
                        "path": "6",
                        "head": "call",
                        "statement": "(m0, m1) <@ A.choose(gx)",
                        "procedure": "A.choose",
                    },
                    {
                        "side": "right",
                        "path": "8",
                        "head": "call",
                        "statement": "b' <@ A.guess(gy, gz * if b0 then m1 else m0)",
                        "procedure": "A.guess",
                    },
                    {
                        "side": "left",
                        "path": "9",
                        "head": "call",
                        "statement": "b' <@ A.guess(c)",
                        "procedure": "A.guess",
                    },
                ],
            },
        },
    }

    fact = _fact(_panel(view), "whole_program_structure")
    observations = " ".join(fact["observations"])
    assert "call A.choose" in observations and "call A.guess" in observations
    assert "shared `call` regions appear at different top-level positions" not in observations


def test_deep_surgery_omits_whole_program_structure_for_synced_programs() -> None:
    view = {
        "proof_status": {
            "status": "open",
            "remaining_goals": 1,
            "view_focus": "relational_program",
            "current_layer": "procedure_body",
            "goal_type": "pRHL",
        },
        "current_goal": {
            "goal_type": "pRHL",
            "lines": [
                "&1 (left ) : {i : int} [programs are in sync]",
                "&2 (right) : {i : int}",
            ],
        },
        "program_frontier": {
            "current_frontier_scope": {
                "setup": {
                    "left": {"paths": ["1"], "summary": "j <- 0"},
                    "right": {"paths": ["1"], "summary": "j <- 0"},
                },
                "frontier": {
                    "left": {
                        "head": "while",
                        "path": "2",
                        "statement": "while (j < Top.N) {",
                    },
                    "right": {
                        "head": "while",
                        "path": "2",
                        "statement": "while (j < Top.N) {",
                    },
                },
                "lookahead_after_frontier": [
                    {"side": "left", "path": "4", "statement": "r <@ PIR.query(PIR.s)"},
                    {"side": "right", "path": "4", "statement": "r <@ PIR.query(PIR.s)"},
                ],
            },
        },
    }

    assert "whole_program_structure" not in _panel_fact_dict(view)


def test_surgery_where_current_scope_uses_synchronized_language_for_synced_programs() -> None:
    view = {
        "proof_status": {
            "status": "open",
            "remaining_goals": 1,
            "view_focus": "relational_program",
            "current_layer": "procedure_body",
            "goal_type": "pRHL",
        },
        "current_goal": {
            "goal_type": "pRHL",
            "lines": [
                "&1 (left ) : {b : bool, i, j : int, r, r' : word} [programs are in sync]",
                "&2 (right) : {b : bool, i, j : int, r, r' : word}",
                "pre = true",
                "while (j < Top.N) {",
                "post = PIR.s'{1} = PIR.s'{2}",
            ],
        },
        "program_frontier": {
            "current_frontier_scope": {
                "setup": {
                    "left": {
                        "paths": ["1", "2"],
                        "summary": "2 setup statement(s): j <- 0; (PIR.s, PIR.s') <- ([], [])",
                    },
                },
                "frontier": {
                    "left": {
                        "head": "while",
                        "path": "3",
                        "statement": "while (j < Top.N) {",
                    },
                },
                "lookahead_after_frontier": [
                    {
                        "side": "left",
                        "path": "4",
                        "head": "call",
                        "statement": "r <@ PIR.query(PIR.s)",
                        "procedure": "PIR.query",
                    },
                    {
                        "side": "left",
                        "path": "5",
                        "head": "call",
                        "statement": "r' <@ PIR.query(PIR.s')",
                        "procedure": "PIR.query",
                    },
                ],
            },
        },
    }

    where = _surgery_where(view)
    assert where[0].startswith("synchronized setup before current frontier (positions 1-2)")
    assert where[1].startswith("current frontier: synchronized at")
    blob = " ".join(where)
    assert "left setup" not in blob
    assert "left side only" not in blob


def test_statement_is_proc_call_handles_nested_module_instantiation() -> None:
    # FIX-B2/④ (exposed by the step2_1 i61 raw-frontier capture): a nested-module call
    # `RealOrcls(OChaChaPoly(IFinRO)).init()` is a PROCEDURE CALL — the single-paren-level
    # regex missed it, so the setup row advertised it as `sp`/`wp`-absorbable.
    assert _statement_is_proc_call("RealOrcls(OChaChaPoly(IFinRO)).init()")
    assert _statement_is_proc_call("Log(LRO).init()")          # single level still works
    assert _statement_is_proc_call("Iter(O).iter(xs)")
    assert not _statement_is_proc_call("x <- f a")             # assignment is absorbable
    assert not _statement_is_proc_call("C.ofintd 0")           # operator application, not a call
    # the setup row for such a call is rendered as structure, not tactic advice
    v = {"program_frontier": {"frontier_alignment": {"rows": [{
        "role": "setup / initialization",
        "left": "RealOrcls(OChaChaPoly(IFinRO)).init()",
        "right": "RealOrcls(StLSke(St)).init()",
        "location": {"left_paths": ["1"], "right_paths": ["1"]},
    }]}}}
    line = _surgery_where(v)[0]
    # rendered via the proc-call branch, without prescribing inline/call vs sp/wp
    assert line.startswith("procedure-call prefix")
    assert "inline" not in line and "sp" not in line and "wp" not in line


def test_surgery_where_fix_b3_per_side_setup_positions() -> None:
    # FIX-B3 (re-audit ④): a setup row shows the per-side position range. A symmetric setup
    # reads as one range (pr_12 i45: 7/7); an asymmetric setup (step1 i58: right has an extra
    # init) shows BOTH columns instead of silently dropping the right side. No concrete
    # `sp i j` count is emitted (the underlying region count can be truncated).
    sym = {"program_frontier": {"frontier_alignment": {"rows": [{
        "role": "setup / initialization", "left": "a <- 0", "right": "a <- 0",
        "location": {"left_paths": ["1", "2", "3"], "right_paths": ["1", "2", "3"]},
    }]}}}
    assert "positions 1-3" in _surgery_where(sym)[0]
    assert "left positions" not in _surgery_where(sym)[0]            # symmetric -> single range
    asym = {"program_frontier": {"frontier_alignment": {"rows": [{
        "role": "setup / initialization", "left": "a <- 0", "right": "a <- 0; b <- 1",
        "location": {"left_paths": ["1"], "right_paths": ["1", "2"]},
    }]}}}
    line = _surgery_where(asym)[0]
    assert "left positions 1" in line and "right positions 1-2" in line  # both sides surfaced


def test_call_focus_drops_placeholder_candidate_handles() -> None:
    # `lemma` / `pair` are metavariable / route-selection labels the backend leaks
    # into named_handles; they must not render as "Candidate: `pair`".
    view = {
        "proof_status": {"current_layer": "call_site"},
        "current_goal": {"lines": ["g"]},
        "call_site_surface": {
            "state": "live_named_call_needs_resolution",
            "named_call_templates": [{"symbol": "CCP_OCCP", "tactic_shape": "call CCP_OCCP."}],
            "named_handles": [
                {"symbol": "pair", "callable_now": False,
                 "why_visible": "Use this as route-selection context; it is not a tactic to run as-is."},
                {"symbol": "lemma", "callable_now": False,
                 "why_visible": "This tactic shape still has placeholders; replace them..."},
                {"symbol": "CCP_OCCP", "callable_now": True},   # the real one survives
            ],
        },
    }
    cf = _call_fact_dict(view)
    blob = " ".join(str(v) for v in cf.values())
    assert "`pair`" not in blob and "`lemma`" not in blob
    assert "CCP_OCCP" in blob


def test_l4_profile_names_surface_level_not_tree_topology() -> None:
    profile = resolve_surface_profile("l4_checked_action_surface")

    assert profile is not None
    assert profile.name == "l4_checked_action_surface"
    assert profile.paper_level == "L4"
    assert profile.stage == "l4_checked_action_surface"


def test_diagnostic_full_surface_is_surface_not_tree_topology() -> None:
    profile = resolve_surface_profile("diagnostic_full_surface")

    assert profile is not None
    assert profile.name == "diagnostic_full_surface"
    assert profile.paper_level is None
    assert profile.paper_role == "diagnostic"


def test_surface_profile_names_are_canonical_only() -> None:
    names = set(surface_profile_names(include_unsupported=False))

    assert "l1_goal_projection" in names
    assert "l2_semantic_ir" in names
    assert "l3_flow_navigation" in names
    assert "l4_checked_action_surface" in names
    assert "diagnostic_full_surface" in names
    assert "full_tree" not in names
    assert "full_single_node" not in names


def test_old_combined_tree_names_are_not_surface_profiles() -> None:
    for name in ("full_tree", "full_single_node", "goal_only", "navigator_upgrade"):
        try:
            resolve_surface_profile(name)
        except ValueError as exc:
            assert "unknown surface profile" in str(exc)
        else:
            raise AssertionError(f"{name} unexpectedly resolved as a surface profile")


def test_view_metadata_exposes_only_surface_profile() -> None:
    view = apply_workspace_view_surface_profile(
        {"kind": "prover_workspace_view"},
        "diagnostic_full_surface",
    )

    assert view["surface_profile"]["name"] == "diagnostic_full_surface"
    assert view["surface_profile"]["surface_profile"] == "diagnostic_full_surface"
    assert "topology_effect" not in view["surface_profile"]
    assert "legacy_aliases" not in view["surface_profile"]




def test_l4_allows_manager_owned_bridge_and_rewrite_compilers() -> None:
    for topic in ("bridge_options", "rewrite_candidates"):
        allowed, reason = surface_profile_allows_intent(
            "l4_checked_action_surface",
            "inspect_context",
            {"topic": topic},
        )

        assert allowed, reason


def _l4_view_with_panels(goal_chars: int, with_analysis: bool = False,
                         view_focus: str = "") -> dict:
    pf = {"x": 1}
    cm = {"navigation": [1, 2, 3]}
    if with_analysis:
        # the program-IR analysis the framework already computes at a deep seq_cut
        pf = {"frontier_alignment": {
            "rows": [
                {"role": "setup / initialization", "left": "nap <- p; n0 <- n;",
                 "location": {"left_paths": ["1", "2", "3"]}},
                {"role": "loop frontier", "left": "while (p1 <> []) {"},
            ],
            "first_instruction_alignment": {"left_head": "while", "branch_alignment": "both"},
        }}
        cm = {"navigation": [{"id": "prhl_mid_surgery",
                              "route": "case_split_then_rcond_swap_wp_conseq",
                              "fast_track_probe": {"tactic": "case: (<guard>)."}}]}
    return {
        "schema_version": 1, "kind": "prover_workspace_view",
        "proof_status": {"status": "open", "remaining_goals": 9, "view_focus": view_focus},
        "last_result": {"intent": {"intent": "commit_tactic"}},
        "current_goal": {"goal_type": "pRHL", "lines": ["g" * 100] * (goal_chars // 100)},
        "program_frontier": pf, "application_context": {"y": 1},
        "candidate_moves": cm,
        "facts_and_diagnostics": {"z": 1}, "seq_cut_surface": {"s": 1},
        "pure_tail_surface": {"p": 1}, "recovery_diagnosis_surface": {"r": 1},
        "structural_checkpoints": {"c": 1}, "inspect_lookup_handles": {"h": 1},
        "latest_observation": {"o": 1},
    }


def test_l4_deep_giant_goal_leads_with_focus_collapses_nav_bulk_keeps_signals() -> None:
    # Profile gating keeps raw signal panels; SurfaceModel owns the deep-surgery
    # primary panel. No profile-produced focus dict participates in the contract.
    out = apply_workspace_view_surface_profile(
        _l4_view_with_panels(6000, view_focus="seq_cut"), "l4_checked_action_surface")
    assert "deep_focus" not in out
    model = _model(out)
    assert model["primary_panel"]["panel_id"] == "deep_surgery"
    # analysis SIGNAL panels are NOT dropped — a deep view can still carry a gap
    assert "seq_cut_surface" in out
    assert "pure_tail_surface" in out
    assert "recovery_diagnosis_surface" in out
    for core in ("current_goal", "proof_status", "last_result"):
        assert core in out, core
    # the agent's tool menu must survive (it's an action, not noise)
    assert "inspect_lookup_handles" in out
    assert "inspect_lookup_handles" not in (out.get("reference", {}).get("collapsed") or [])


def test_l4_deep_focus_renders_existing_analysis_as_readable_skeleton(monkeypatch) -> None:
    # under neutrality, SurfaceModel's deep panel is mechanical facts only; heuristic
    # route/fast_track prescription stays out of the presentation contract.
    monkeypatch.setenv("SHANNON_VIEW_NEUTRALITY_STRICT", "1")
    out = apply_workspace_view_surface_profile(
        _l4_view_with_panels(6000, with_analysis=True, view_focus="seq_cut"),
        "l4_checked_action_surface")
    panel = _model(out)["primary_panel"]
    assert panel["panel_id"] == "deep_surgery"
    blob = json.dumps(panel, ensure_ascii=False)
    assert "route" not in blob and "fast_track_probe" not in blob
    assert "toolbox" not in blob and "yours" not in blob


def test_l4_deep_panel_does_not_surface_status_only_branch_focus() -> None:
    view = {
        "proof_status": {"status": "open", "remaining_goals": 8, "view_focus": "seq_cut"},
        "current_goal": {"goal_type": "pRHL", "lines": ["g"]},
        "program_frontier": {"current_frontier_scope": {
            "frontier": {
                "kind": "call_pair",
                "left": {"statement": "x <@ L.f()", "procedure": "L.f"},
                "right": {"statement": "y <@ R.f()", "procedure": "R.f"},
            },
        }},
        "seq_cut_surface": {
            "branch_focus": {"remaining_goals": 8, "latest_event_head": "inline"},
        },
    }

    panel = _model(view)["primary_panel"]
    blob = json.dumps(panel, ensure_ascii=False)
    assert "Branch focus" not in blob
    assert "latest_event_head" not in blob


def test_l4_small_goal_collapses_nav_bulk_no_full_dump() -> None:
    # consistency: even a small goal no longer gets a profile-produced focus dict;
    # raw signal panels stay available for the SurfaceModel composer.
    out = apply_workspace_view_surface_profile(
        _l4_view_with_panels(300), "l4_checked_action_surface")
    assert "deep_focus" not in out
    assert "seq_cut_surface" in out
    for core in ("current_goal", "proof_status", "last_result", "inspect_lookup_handles"):
        assert core in out, core


def test_l4_simple_goal_with_empty_signals_is_bare_core() -> None:
    # a genuinely simple goal (the analysis signal panels are empty / absent) lands
    # at goal-only-like bare core — the lean baseline the user wanted for small goals
    view = {
        "schema_version": 1, "kind": "prover_workspace_view",
        "proof_status": {"status": "open", "remaining_goals": 1},
        "last_result": {"intent": "commit_tactic", "tactic": "auto.", "result": "accepted"},
        "current_goal": {"lines": ["g" * 80]},
        "candidate_moves": {}, "inspect_lookup_handles": {"h": 1},
    }
    out = apply_workspace_view_surface_profile(view, "l4_checked_action_surface")
    assert "deep_focus" not in out and "recover_focus" not in out
    allowed = {"schema_version", "kind", "proof_status", "last_result",
               "current_goal", "inspect_lookup_handles", "surface_profile"}
    assert set(out) <= allowed, set(out) - allowed
    for core in ("current_goal", "proof_status", "last_result", "inspect_lookup_handles"):
        assert core in out, core


def test_l4_view_shape_is_phase_driven_not_size_driven() -> None:
    # the SAME phase (seq_cut surgery) gives the SAME SurfaceModel primary panel at
    # small and large goal sizes — profile no longer picks focus by size.
    small = _l4_view_with_panels(800, with_analysis=True)
    small["proof_status"]["view_focus"] = "seq_cut"
    large = _l4_view_with_panels(6000, with_analysis=True)
    large["proof_status"]["view_focus"] = "seq_cut"
    out_small = apply_workspace_view_surface_profile(small, "l4_checked_action_surface")
    out_large = apply_workspace_view_surface_profile(large, "l4_checked_action_surface")
    assert "deep_focus" not in out_small and "deep_focus" not in out_large
    assert _model(out_small)["primary_panel"]["panel_id"] == "deep_surgery"
    assert _model(out_large)["primary_panel"]["panel_id"] == "deep_surgery"


def _l4_failure_view(rejected: bool = True, view_focus: str = "failure_diagnostic") -> dict:
    return {
        "schema_version": 1, "kind": "prover_workspace_view",
        "proof_status": {"status": "open", "remaining_goals": 9,
                         "view_focus": view_focus, "current_layer": "procedure_body"},
        "last_result": {"intent": "commit_tactic", "tactic": "sim.",
                        "result": "EasyCrypt rejected the committed tactic." if rejected else "committed",
                        "proof_state": "not changed" if rejected else "changed"},
        "current_goal": {"goal_type": "pRHL", "lines": ["g" * 60]},
        "program_frontier": {"frontier_alignment": {"first_instruction_alignment": {
            "left_head": "while", "right_head": "while", "branch_alignment": "both_sides_at_while"}}},
        "recovery_diagnosis_surface": {"recovery_class": "wrong_first_instruction",
            "related_checkpoints": [{"label": "Before call invariant #8",
                "checkpoint_id": "cp_8_xyz", "why_checkpoint": "call invariant introduction point"}]},
        "structural_checkpoints": {"items": [
            {"checkpoint_id": "abc:3", "committed_step_index": 3,
             "committed_tactic": "sp.", "why_checkpoint": "clean seq boundary"}]},
        "candidate_moves": {"navigation": [1]}, "seq_cut_surface": {"s": 1},
        "pure_tail_surface": {"p": 1}, "inspect_lookup_handles": {"h": 1},
        "latest_observation": {"o": 1},
    }


def test_l4_failure_phase_surfaces_recover_model_without_head_table(monkeypatch) -> None:
    # Recovery presentation is composed in SurfaceModel, not in surface_profiles.
    # A while head surfaces only while-relevant facts/actions, never the generic
    # all-head table.
    monkeypatch.setenv("SHANNON_VIEW_NEUTRALITY_STRICT", "1")
    out = apply_workspace_view_surface_profile(
        _l4_failure_view(), "l4_checked_action_surface")
    assert "recover_focus" not in out and "deep_focus" not in out
    panel = _model(out)["primary_panel"]
    assert panel["panel_id"] == "recovery"
    blob = json.dumps(panel, ensure_ascii=False)
    assert "while" in blob and "sim." in blob
    assert "head if" not in blob and "invalid first instruction" not in blob
    assert "Before call invariant #8" in blob and "cp_8_xyz" in blob
    assert "structural_checkpoints" in out
    assert "inspect_lookup_handles" in out
    assert "pure_tail_surface" in out


def test_l4_failure_phase_fires_on_rejected_commit_without_failure_focus_flag() -> None:
    # even if view_focus wasn't set to failure_diagnostic, a rejected commit triggers it
    out = apply_workspace_view_surface_profile(
        _l4_failure_view(rejected=True, view_focus="seq_cut"), "l4_checked_action_surface")
    assert "recover_focus" not in out and "deep_focus" not in out
    assert _model(out)["primary_panel"]["panel_id"] == "recovery"


def test_l4_sticky_failure_flag_without_rejected_commit_does_not_fire_recover() -> None:
    # regression (2203 live): view_focus stays "failure_diagnostic" after the agent
    # moves on to an inspect at a call frontier; recover_focus must NOT fire on the
    # sticky flag alone — only a genuinely rejected COMMIT triggers it.
    view = _l4_failure_view(rejected=False, view_focus="failure_diagnostic")
    view["last_result"] = {"intent": "inspect_context",
                           "result": "The manager returned read-only context for the current goal."}
    view["proof_status"]["current_layer"] = "call_site"
    view["program_frontier"] = {"focus": {"frontier_call_sites": 1}}
    view["call_site_surface"] = {"named_call_templates": [{"symbol": "H", "tactic_shape": "call H."}]}
    view = _with_call_preflight(view)
    out = apply_workspace_view_surface_profile(view, "l4_checked_action_surface")
    assert "recover_focus" not in out
    assert _model(out)["primary_panel"]["panel_id"] == "call_site"


def _l4_pure_reject_view(goal_type: str = "probability", current_layer: str = "pr",
                         view_focus: str = "probability",
                         lines=None) -> dict:
    """A REJECTED commit on a PURE-LOGIC / probability goal: no program frontier,
    so recover_focus must NOT emit the program head menu."""
    return {
        "schema_version": 1, "kind": "prover_workspace_view",
        "proof_status": {"status": "open", "remaining_goals": 3,
                         "view_focus": view_focus, "current_layer": current_layer,
                         "goal_type": goal_type},
        "last_result": {"intent": "commit_tactic", "tactic": "sp.",
                        "result": "EasyCrypt rejected the committed tactic.",
                        "proof_state": "not changed"},
        "current_goal": {"goal_type": goal_type,
                         "lines": lines or ["Pr[A.main() @ &m : res] <= BRA.big i (0) n F"]},
        # explicit evidence the panel surfaces "no program-frontier work"
        "recovery_diagnosis_surface": {"recovery_class": "pure_residual",
            "evidence": ["no program-frontier work available at this goal"],
            "related_checkpoints": [{"label": "Before order split #2",
                "checkpoint_id": "cp_2_pq", "why_checkpoint": "order/transitivity entry point"}]},
        "structural_checkpoints": {"items": [
            {"checkpoint_id": "p:1", "committed_step_index": 1,
             "committed_tactic": "rewrite foo.", "why_checkpoint": "clean residual boundary"}]},
        "pure_tail_surface": {"goal_operators": ["BRA.big", "<="]},
        "inspect_lookup_handles": {"h": 1},
    }


def test_recover_model_pure_logic_reject_has_no_program_head_menu() -> None:
    # CONFIRMED BUG: a rejected PURE-LOGIC / probability goal (no program frontier)
    # must NOT get the PROGRAM head-table or the program head_now/yours; it gets a
    # pure/Pr recovery hint instead. rewind/rejected fields still present.
    out = apply_workspace_view_surface_profile(
        _l4_pure_reject_view(), "l4_checked_action_surface")
    panel = _model(out)["primary_panel"]
    blob = json.dumps(panel, ensure_ascii=False)
    # NO program head menu
    assert "head `if`" not in blob
    assert "first instruction (after `~`" not in blob
    assert "pick the condition / branch / invariant" not in blob
    assert "pure/probability residual" in blob
    assert "smt" in blob and "rewrite" in blob
    # goal-type-agnostic fields still present
    assert "sp." in blob
    assert "Before order split #2" in blob and "cp_2_pq" in blob


def test_recover_model_ambient_pure_reject_has_no_program_head_menu() -> None:
    # ambient_logic single-sided pure residual reject: same gating, generic pure hint.
    view = _l4_pure_reject_view(goal_type="hoare", current_layer="ambient_logic",
                                view_focus="ambient_logic",
                                lines=["x{1} = y{2} => P x"])
    out = apply_workspace_view_surface_profile(view, "l4_checked_action_surface")
    blob = json.dumps(_model(out)["primary_panel"], ensure_ascii=False)
    assert "head `if`" not in blob
    assert "pick the condition / branch / invariant" not in blob
    assert "smt" in blob
    assert "sp." in blob


def test_recover_model_program_reject_no_generic_head_table() -> None:
    # a rejected program / relational view surfaces only the current head family.
    out = apply_workspace_view_surface_profile(
        _l4_failure_view(), "l4_checked_action_surface")
    panel = _model(out)["primary_panel"]
    blob = json.dumps(panel, ensure_ascii=False)
    assert panel["panel_id"] == "recovery"
    assert "while" in blob
    assert "head if" not in blob and "head call" not in blob
    assert "pick the condition / branch / invariant" not in blob


def test_recover_model_auto_strict_failure_is_not_head_mismatch() -> None:
    # auto/smt can fail because the residual needs more facts while the family is
    # still a plausible close. Do not misclassify that as "auto does not reduce
    # the assignment frontier" and hide residual lookups behind sp/wp.
    view = _l4_failure_view()
    view["last_result"] = {
        "intent": "commit_tactic",
        "payload": {"tactic": "auto => />; smt(neq_w1_w2 size_ge0)."},
        "tactic": "auto => />; smt(neq_w1_w2 size_ge0).",
        "result": "EasyCrypt rejected the committed tactic.",
        "proof_state": "The committed EasyCrypt proof state was not changed.",
        "error_summary": "[error] cannot prove goal (strict)",
    }
    view["program_frontier"] = {"frontier_alignment": {"first_instruction_alignment": {
        "left_head": "assignment", "right_head": "assignment",
        "branch_alignment": "both_sides_at_assignment"}}}
    view["current_goal"] = {
        "goal_type": "pRHL",
        "lines": [
            "nth witness w1 i = nth witness w2 i",
            "0 <= i < size w1",
        ],
    }
    view["inspect_lookup_handles"] = {"ask_manager_for": [
        {"intent": "inspect_context",
         "payload": {"topic": "operator_lemmas", "operator": "OPERATOR"},
         "public_intent": "operator_lemmas",
         "payload_fields": ["operator"],
         "intent_class": "context_topic",
         "read_only": True},
    ]}
    panel = _model(apply_workspace_view_surface_profile(
        view, "l4_checked_action_surface"))["primary_panel"]
    blob = json.dumps(panel, ensure_ascii=False)
    assert "Automation residual failure" in blob
    assert "does not reduce the current frontier head" not in blob
    assert "Why the rejected family does not fit this head" not in blob
    names = [
        action.get("payload", {}).get("name")
        for action in panel.get("actions", [])
        if action.get("intent") == "tactic_forms"
    ]
    assert "rewrite" in names and "apply" in names
    assert "sp" not in names and "wp" not in names
    assert any(action.get("intent") == "operator_lemmas"
               for action in panel.get("actions", []))


def test_l4_deep_focus_blanks_seq_coupling_and_drops_route_prescription(monkeypatch) -> None:
    # under neutrality the concrete split point rides in deep_focus with the `={...}`
    # coupling BLANKED (mechanical), but the heuristic prescription (anti_route/avoid,
    # route confidence) is stripped. That route-steering content stalled pr_G4.
    monkeypatch.setenv("SHANNON_VIEW_NEUTRALITY_STRICT", "1")
    view = _l4_view_with_panels(6000, with_analysis=True, view_focus="seq_cut")
    view["candidate_moves"]["moves"] = [{"category": "commit", "title": "Seq-cut route",
                                         "tactic": "seq 29 36 : (={r, t0})."}]
    view["candidate_moves"]["route_health"] = [{"signal": "prhl_surgery_sequence_needed",
        "anti_route": "Do not use conseq as a blind replacement for a manual surgery."}]
    view["candidate_moves"]["navigation"] = [{"id": "prhl_surgery_route", "route": "case_split_then_rcond",
        "confidence": "medium", "confidence_reason": "branch signals present but the guard needs inspection."}]
    panel = _model(apply_workspace_view_surface_profile(
        view, "l4_checked_action_surface"))["primary_panel"]
    blob = json.dumps(panel, ensure_ascii=False)
    assert panel["panel_id"] == "deep_surgery"
    assert "={r, t0}" not in blob                     # semantics NOT filled
    assert "avoid" not in blob                        # anti_route prescription dropped
    assert "confidence" not in blob                   # route/confidence dropped


def test_call_focus_surfaces_specific_candidate_and_blocker_not_boilerplate() -> None:
    # the call focus must render the SPECIFIC computed analysis (the candidate named
    # call + its tactic + why it's blocked + the frame facts), NOT generic "how a call
    # works" advice — and NO "go probe/confirm first" hedging (that drove the
    # over-inspecting in the 0127 L4 run).
    view = {
        "schema_version": 1, "kind": "prover_workspace_view",
        "proof_status": {"status": "open", "remaining_goals": 1,
                         "view_focus": "relational_program", "current_layer": "call_site"},
        "last_result": {"intent": "commit_tactic", "tactic": "x.", "result": "ok"},
        "current_goal": {"lines": ["g" * 50]},
        # a genuine call AT the frontier (named handle present) -> frontier_call_sites>0,
        # so the call_focus panel correctly fires (vs a call merely downstream).
        "program_frontier": {"focus": {"frontier_call_sites": 1, "live_call_sites": 1}},
        "call_site_surface": {
            "state": "live_named_call_needs_resolution",
            "named_call_templates": [{"symbol": "UFCMA_genCC", "tactic_shape": "call UFCMA_genCC."}],
            "named_handles": [{"symbol": "UFCMA_genCC", "callable_now": False}],
            "frontier_blockers": [{"kind": "named_handle_not_callable_in_current_view"}],
        },
        "frame_obligation_ledger": {
            "required_later": [{"fact": "={glob A}"}],
            "possibly_dropped": [{
                "fact": "={RO.m}", "required_sources": ["current_goal"], "boundary": "call #5",
                "related_checkpoint": {"label": "Before call invariant #5",
                    "submit": {"intent": "undo_to_checkpoint",
                               "payload": {"checkpoint_id": "cp_5_abc"}}},
            }],
        },
        "inspect_lookup_handles": {"h": 1},
    }
    view = _with_call_preflight(view)
    panel = _model(apply_workspace_view_surface_profile(
        view, "l4_checked_action_surface"))["primary_panel"]
    # itemized named categories (situation / candidate / ...), not a crammed paragraph
    blob = json.dumps(panel, ensure_ascii=False)
    assert "UFCMA_genCC" in blob                                         # concrete named handle retained
    assert "call UFCMA_genCC." not in blob                                # non-callable tactic hidden
    assert "named_handle_not_callable" in blob
    assert "confirm via" not in blob.lower() and "probe first" not in blob.lower()  # no inspect-driving hedging


def test_phase_of_prefers_layer_goal_type_over_stale_view_focus() -> None:
    # regression (0846 run, turn 8): after `undo_last_step` back to the opener Pr
    # goal, view_focus stayed the stale "seq_cut", but current_layer/goal_type
    # correctly said pr/probability. The phase must follow the reliable signals.
    view = {
        "schema_version": 1, "kind": "prover_workspace_view",
        "proof_status": {"status": "open", "remaining_goals": 1,
                         "view_focus": "seq_cut",            # stale
                         "current_layer": "pr", "goal_type": "probability"},
        "last_result": {"intent": "undo_last_step"},
        "current_goal": {"lines": ["Pr[A() @ &m : x] <= Pr[B() @ &m : y]"]},
        "candidate_moves": {}, "inspect_lookup_handles": {"h": 1},
    }
    out = apply_workspace_view_surface_profile(view, "l4_checked_action_surface")
    assert "opener_focus" not in out and "deep_focus" not in out
    assert _model(out)["primary_panel"]["panel_id"] == "opener"


def test_probability_opener_ignores_empty_stale_call_site_surface() -> None:
    # Fable step4_badi baseline replay: some raw views carry an empty
    # call_site_surface key even while proof_status/current goal are a probability
    # opener. Empty stale channels must not claim the SurfaceModel contract.
    view = {
        "schema_version": 1, "kind": "prover_workspace_view",
        "proof_status": {
            "status": "open", "remaining_goals": 1,
            "view_focus": "probability", "current_layer": "pr",
            "goal_type": "probability",
        },
        "current_goal": {"goal_type": "probability", "lines": [
            "Pr[A.main() @ &m : res] <= Pr[B.main() @ &m : res \\/ bad]"
        ]},
        "call_site_surface": {},
        "program_frontier": {"authority": "proof-state analysis", "view_focus": "probability"},
        "inspect_lookup_handles": {"ask_manager_for": []},
    }

    model = _model(view)
    assert model["phase"] == "opener"
    assert model["primary_panel"]["panel_id"] == "opener"


def test_pure_tail_surface_beats_stale_program_frontier_residue() -> None:
    # Fable step4_badi baseline replay: after program work, the manager can still
    # retain stale/raw program_frontier scaffolding while current_layer and
    # pure_tail_surface identify a pure residual. The typed phase follows the
    # pure-tail evidence, not the stale raw channel.
    view = {
        "schema_version": 1, "kind": "prover_workspace_view",
        "proof_status": {
            "status": "open", "remaining_goals": 6,
            "view_focus": "relational_program",
            "current_layer": "verification_residue",
            "goal_type": "pRHL",
        },
        "current_goal": {"goal_type": "pRHL", "lines": [
            "forall &m, hoare[ x <- y; : true ==> size xs = size ys ]"
        ]},
        "program_frontier": {
            "authority": "proof-state analysis",
            "current_frontier_scope": {"setup": {"left": {"paths": ["1"]}}},
        },
        "call_site_surface": {},
        "pure_tail_surface": {
            "obligation_shape_surface": {
                "implication_premises": ["true"],
                "conclusion_obligations": ["size xs = size ys"],
            },
            "goal_operators": ["size"],
        },
        "inspect_lookup_handles": {"ask_manager_for": []},
    }

    model = _model(view)
    assert model["phase"] == "pure_logic"
    assert model["primary_panel"]["panel_id"] == "pure_logic"


def test_prhl_module_without_pure_tail_keeps_no_primary_panel() -> None:
    # Fable baseline replay: prhl_module goals may have no program frontier but also
    # no derived pure-tail facts. Do not invent a generic "no frontier" panel; keep
    # the old lean surface and only show eligible actions.
    view = {
        "schema_version": 1, "kind": "prover_workspace_view",
        "proof_status": {
            "status": "open", "remaining_goals": 1,
            "view_focus": "relational_program",
            "current_layer": "prhl_module",
            "goal_type": "equiv",
        },
        "current_goal": {"goal_type": "equiv", "lines": [
            "pre = arg{1} = arg{2}",
            "UFCMA_l.f ~ UFCMA_li.f",
            "post = res{1} = res{2}",
        ]},
        "program_frontier": {"authority": "proof-state analysis", "view_focus": "relational_program"},
        "inspect_lookup_handles": {"ask_manager_for": [
            {"intent": "operator_lemmas", "payload": {"operator": "nth"}},
        ]},
    }

    model = _model(view)
    assert model["phase"] == "relational_program"
    assert "primary_panel" not in model


def test_verification_residue_with_live_program_frontier_is_not_pure_fallback() -> None:
    # Fable baseline replay: verification_residue is only a pure residual when no
    # live program frontier remains. A synchronized residual program should not get
    # the generic pure-tail fallback panel.
    view = {
        "schema_version": 1, "kind": "prover_workspace_view",
        "proof_status": {
            "status": "open", "remaining_goals": 5,
            "view_focus": "relational_program",
            "current_layer": "verification_residue",
            "goal_type": "pRHL",
        },
        "current_goal": {"goal_type": "pRHL", "lines": [
            "&1 (left ) : {c, c0 : ciphertext, p : plaintext option} [programs are in sync]",
            "pre = p{1} = p{2}",
            "Mem.lc <- if c0 \\in Mem.log then Mem.lc else c0 :: Mem.lc",
            "post = Mem.lc{1} = Mem.lc{2}",
        ]},
        "program_frontier": {"frontier_alignment": {"rows": [
            {
                "role": "synchronized setup",
                "left": "c0 <- c",
                "right": "EasyCrypt marks the programs as synchronized",
            },
            {
                "role": "synchronized frontier",
                "left": "Mem.lc <- if c0 \\in Mem.log then Mem.lc else c0 :: Mem.lc",
                "right": "EasyCrypt marks the programs as synchronized",
            },
        ]}},
        "inspect_lookup_handles": {"ask_manager_for": [
            {"intent": "operator_lemmas", "payload": {"operator": "(\\in)"}},
        ]},
    }

    model = _model(view)
    assert model["phase"] == "relational_program"
    assert "primary_panel" not in model


def test_l4_opener_focus_is_mechanical_only_no_budget_prescription(monkeypatch) -> None:
    # regression (pr_G4 L4 stall): under neutrality the opener/probability focus
    # surfaces ONLY mechanical facts (unfoldable heads + reduction forms). It must NOT
    # re-surface the budget-ledger route / framework_strategy / confidence / fast_track
    # / avoid prescription that vetoed the correct seq/rnd descent and stalled the proof.
    monkeypatch.setenv("SHANNON_VIEW_NEUTRALITY_STRICT", "1")
    view = {
        "schema_version": 1, "kind": "prover_workspace_view",
        "proof_status": {"status": "open", "remaining_goals": 1,
                         "current_layer": "pr", "goal_type": "probability"},
        "last_result": {"intent": "commit_tactic", "tactic": "byphoare.", "result": "ok"},
        "current_goal": {"lines": ["Pr[G4.main() @ &m : x] <= (q / order) ^ 3"]},
        "facts_and_diagnostics": {"facts": {
            "pr_obligation_primary_strategy": "run_native_pr_search",
            "has_pr_obligation_plan": True,
            "unfoldable_goal_heads": [{"name": "G3.d", "unfold_tactic": "rewrite /G3.d."}],
        }},
        "candidate_moves": {"navigation": [{
            "id": "prob_phoare_loop", "route": "byphoare_probability_loop",
            "confidence": "medium", "why_now": "single Pr endpoint visible",
            "fast_track_probe": {"tactic": "byphoare (_: <pre> ==> <post>)."},
            "anti_routes": [{"route": "single_rnd_for_whole_product_budget",
                             "reason": "a single rnd may charge the whole product budget."}],
        }]},
        "inspect_lookup_handles": {"h": 1},
    }
    panel = _model(apply_workspace_view_surface_profile(
        view, "l4_checked_action_surface"))["primary_panel"]
    blob = json.dumps(panel, ensure_ascii=False)
    assert panel["panel_id"] == "opener"
    assert "rewrite /G3.d." in blob                                    # mechanical fact kept
    assert "tactic_affordances" in blob and "byphoare" in blob         # plural family facts kept
    # the heuristic prescription is GONE
    for key in ("framework_strategy", "confidence", "why_now", "fast_track_probe",
                "avoid", "pr_shape_facts"):
        assert key not in blob, key


def test_l1_goal_only_has_action_capabilities_no_content_channels() -> None:
    # L1 has the SAME action capabilities as L4 so the L1<->L4 comparison isolates the
    # DERIVED panel content, not capabilities. Both rewind intents (undo_to_checkpoint,
    # amend_and_replay) reference a committed step BY INDEX off the proof_so_far panel
    # L1 renders, so L1 needs no checkpoint menu. The content-RETRIEVAL channels
    # (probe / inspect / lookup) stay OFF — they ARE the panel value under study.
    def allows(name: str, intent: str) -> bool:
        return surface_profile_allows_intent(name, intent)[0]

    # L1: full ACTION set ON; content channels OFF
    assert allows("l1_goal_projection", "commit_tactic")
    assert allows("l1_goal_projection", "undo_last_step")
    assert allows("l1_goal_projection", "finish")
    assert allows("l1_goal_projection", "undo_to_checkpoint")
    assert allows("l1_goal_projection", "amend_and_replay")
    assert not allows("l1_goal_projection", "probe_tactic")
    assert not allows("l1_goal_projection", "inspect_context")
    assert not allows("l1_goal_projection", "lookup_symbol")

    # only L1 changed — L2/L3/L4 still offer checkpoint rewind
    assert allows("l2_semantic_ir", "undo_to_checkpoint")
    assert allows("l3_flow_navigation", "undo_to_checkpoint")
    assert allows("l4_checked_action_surface", "undo_to_checkpoint")


def test_public_readonly_handles_carry_intent_contract() -> None:
    import workflow.surface_profiles as M

    view = {
        "current_goal": {"lines": ["Current goal", "x = y"]},
        "proof_status": {"status": "open"},
        "inspect_lookup_handles": {"ask_manager_for": [
            {
                "intent": "inspect_context",
                "payload": {"topic": "tactic_forms", "name": "wp"},
                "use_when": "need valid tactic syntax",
            },
            {
                "intent": "lookup_symbol",
                "payload": {"symbol": "size_cat"},
                "use_when": "need declaration before applying it",
            },
        ]},
    }

    out = M.apply_workspace_view_surface_profile(
        view,
        "l4_checked_action_surface",
    )
    asks = out["inspect_lookup_handles"]["ask_manager_for"]
    by_intent = {ask["intent"]: ask for ask in asks}

    assert "inspect_context" not in by_intent
    assert by_intent["tactic_forms"]["intent_class"] == "context_topic"
    assert by_intent["tactic_forms"]["read_only"] is True
    assert by_intent["lookup_symbol"]["intent_class"] == "symbol_lookup"
    assert by_intent["lookup_symbol"]["read_only"] is True


def test_profile_filter_does_not_state_gate_inspect_roster() -> None:
    # State-dependent visibility belongs to SurfaceModel eligibility, not to
    # surface_profiles.  The profile filter only converts legacy wrappers to the
    # public direct intents and applies the profile allowlist/probe policy.
    import workflow.surface_profiles as M
    prof = M.ensure_supported_surface_profile("l4_checked_action_surface")

    def req(topic, name=None):
        p = {"topic": topic}
        if name:
            p["name"] = name
        return {"intent": "inspect_context", "payload": p, "use_when": "x", "returns": "y"}

    handles = {"ask_manager_for": [
        req("goal_info"), req("tactic_forms", "sp"), req("tactic_forms", "rcondt"),
        req("operator_lemmas"), req("tactic_forms", "eager"), req("call_site_options"),
    ]}
    out = M._filter_inspect_lookup_handles(handles, prof)
    names = [(r.get("payload") or {}).get("name") for r in out["ask_manager_for"]]
    intents = [r.get("intent") for r in out["ask_manager_for"]]
    assert "inspect_context" not in intents
    assert {"sp", "rcondt", "eager"} <= set(names)
    assert "goal_info" not in intents
    assert "operator_lemmas" in intents
    assert "call_site_options" in intents


def test_program_surgery_tactic_forms_are_state_eligible_only_with_program() -> None:
    from workflow.surface_composer import compose_surface_model
    from workflow.surface_model import surface_model_to_dict

    handles = {"ask_manager_for": [
        {"intent": "tactic_forms", "payload": {"name": name}}
        for name in ("sp", "rcondt", "eager")
    ]}
    no_program = {
        "proof_status": {"current_layer": "procedure_body", "goal_type": "pRHL"},
        "current_goal": {"lines": ["forall x, P x => Q x"]},
        "inspect_lookup_handles": handles,
    }
    model = surface_model_to_dict(compose_surface_model(no_program, "l4_checked_action_surface"))
    assert "tactic_forms" not in {action["intent"] for action in model.get("actions", [])}

    with_program = {
        **no_program,
        "current_goal": {"lines": ["x <- 0", "while (i < n) {"]},
    }
    model2 = surface_model_to_dict(compose_surface_model(with_program, "l4_checked_action_surface"))
    tf = [action for action in model2["actions"] if action["intent"] == "tactic_forms"]
    assert tf and set(tf[0]["choices"]["name"]) == {"sp", "rcondt", "eager"}


def test_operator_lemmas_prefilled_from_goal_operators() -> None:
    # FIX-4 (content lever): the dead `operator_lemmas operator=OPERATOR` placeholder is
    # pre-filled with the goal's actual load-bearing operators (`^`, `++`, nth, ...) so the
    # agent gets ready-to-submit lemma searches for ITS goal, plus one generic pointer.
    from workflow.surface_action_choices import operator_queries_for_goal
    from workflow.surface_composer import compose_surface_model
    from workflow.surface_model import surface_model_to_dict

    assert operator_queries_for_goal({"current_goal": {"lines": ["----", "a ^ b = c ^ d"]}}) == ["(^)"]
    # a list-operator applied to a cat gets a focused `search` skeleton offered before the bare op
    assert operator_queries_for_goal({"current_goal": {"lines": ["----", "nth w (l1 ++ l2) i"]}}) == [
        "(++)", "(nth _ (_ ++ _) _)", "nth"]
    # FIX-4c: the field/word XOR digraph `+^` is a DISTINCT operator from group `^` —
    # a `+^` goal must route to `(+^)` lemmas, NOT group-`(^)` lemmas (PIR/eq_Game1_Game2/
    # equ_cc/UFCMA_genCC all use `+^`); a real group `^` (CramerShoup/schnorr/cpa_ddh0,
    # incl. inverse `g^-1`) must still route to `(^)`.
    assert operator_queries_for_goal(
        {"current_goal": {"lines": ["----", "big predT a s +^ big predT a s' = a i0"]}}
    ) == ["(+^)"]
    assert "(^)" not in operator_queries_for_goal(
        {"current_goal": {"lines": ["----", "h +^ m = h' +^ m'"]}}
    )
    assert operator_queries_for_goal({"current_goal": {"lines": ["----", "g ^ x = g ^ -1"]}}) == ["(^)"]
    view = {
        "proof_status": {"current_layer": "ambient_logic", "goal_type": "ambient"},
        "current_goal": {"lines": ["----", "a ^ b = c ^ d"]},
        "inspect_lookup_handles": {"ask_manager_for": [
            {"intent": "operator_lemmas", "payload": {"operator": "OPERATOR"}, "use_when": "x", "returns": "y"},
        ]},
    }
    model = surface_model_to_dict(compose_surface_model(view, "l4_checked_action_surface"))
    ops = [
        op
        for action in model["actions"]
        if action["intent"] == "operator_lemmas"
        for op in action["choices"]["operator"]
    ]
    assert ops == ["(^)"]


def test_goal_head_operators_routes_named_ops_on_pure_goals() -> None:
    # PIR per-step measurement: on a PURE/ambient goal the route IS lemma-rewriting, so the
    # goal's NAMED operators (`big`, project-local fns) must be offered too — not just the
    # whitelist symbolic op. The old version pinned PIR's big-sum steps to `(+^)`; now `big`
    # is a candidate the agent can query directly. We do NOT pre-run the search.
    from workflow.surface_action_choices import operator_queries_for_goal
    pure = {
        "proof_status": {"current_layer": "ambient_logic", "view_focus": "ambient_logic"},
        "current_goal": {"lines": [
            "i0: int", "&hr: {b : bool, j : int, s, s' : int list}",
            "------------------------------------------------------------",
            "big predT a (i0 :: PIR.s{hr}) +^ big predT a PIR.s'{hr} = a i0",
        ]},
    }
    ho = operator_queries_for_goal(pure)
    assert "big" in ho and "(+^)" in ho        # both the named big-op AND the xor are offered
    assert "hr" not in ho                       # memory label `{hr}` dropped
    assert "bool" not in ho and "int" not in ho  # types not routed
    # a `big` over a cons in the goal gets the focused skeleton offered before the bare op
    # (so `search` returns big_consT on top, not the ~91-lemma bare-(+^) dump)
    assert "(big _ _ (_ :: _))" in ho
    assert ho.index("(big _ _ (_ :: _))") < ho.index("big")
    # gating: on a NON-pure goal (no ambient_logic), only the curated whitelist ops are offered
    relational = {
        "proof_status": {"current_layer": "procedure_frontier"},
        "current_goal": {"lines": ["----", "big predT a s +^ big predT a s' = a i0"]},
    }
    assert operator_queries_for_goal(relational) == ["(+^)"]   # no general-named routing off-phase


# --- DEFECT 1: rcondt/rcondf index callout (ChaChaPoly step4_1 per-step audit) -------
#
# A guarded `if (...)` at the frontier was named only as "frontier: left side only at
# `if (...)`" — side + guard, never the program INDEX or the rcondt/rcondf verb — even
# though the index is already computed in `procedure_navigation.branch_guards`. The
# fixtures below are the REAL captured branch_guards for the flagged steps.

def _surgery_with_guards(branch_guards: list) -> list:
    return _surgery_where({"program_frontier": {
        "procedure_navigation": {"branch_guards": branch_guards},
    }})


def test_surgery_rcondt_index_uses_at_path_not_at_order_off_by_one() -> None:
    # step4_1 i28: committed `rcondt{1} 17`. The guard's `at_path` is 17 but `at_order`
    # is 18 (a nested `if` body shifts the order count). The producer MUST emit the
    # at_path index 17 (the panel program-column position / real rcond index), NOT the
    # order-based 18 from the existing `rcond_forms` string — an off-by-one would be a
    # regression worse than no index.
    guards = [
        {"side_index": 1, "at_order": 13, "at_path": "13", "guard": "x4 \\notin SplitC2.I1.RO.m",
         "rcond_forms": "rcondt{1} 13 or rcondf{1} 13 (direction needs guard entailment — yours to decide)"},
        {"side_index": 1, "at_order": 18, "at_path": "17", "guard": "x5 \\notin SplitC2.I2.RO.m",
         "rcond_forms": "rcondt{1} 18 or rcondf{1} 18 (direction needs guard entailment — yours to decide)"},
        {"side_index": 2, "at_order": 4, "at_path": "4", "guard": "x1 \\notin RO.m",
         "rcond_forms": "rcondt{2} 4 or rcondf{2} 4 (direction needs guard entailment — yours to decide)"},
    ]
    out = " ".join(_surgery_with_guards(guards))
    assert "rcondt{1} 17" in out                 # the committed index (at_path), exact
    assert "rcondf{1} 17" in out                 # negated-guard sibling noted
    assert "rcondt{1} 18" not in out             # the at_order off-by-one is NOT emitted
    # the guard text travels with the callout
    assert "x5 \\notin SplitC2.I2.RO.m" in out


def test_surgery_rcondt_index_left_guard_at_top_level() -> None:
    # step4_1 i82: committed `rcondt{1} 2` (left guard `SplitD.test x0` at top-level pos 2).
    guards = [
        {"side_index": 1, "at_order": 2, "at_path": "2", "guard": "SplitD.test x0",
         "rcond_forms": "rcondt{1} 2 or rcondf{1} 2 (direction needs guard entailment — yours to decide)"},
        # nested (`at_path` 2.5) guards must be SKIPPED — not at the current frontier.
        {"side_index": 1, "at_order": 7, "at_path": "2.5", "guard": "x5 \\notin SplitC2.I1.RO.m",
         "rcond_forms": "rcondt{1} 7 or rcondf{1} 7 (direction needs guard entailment — yours to decide)"},
        {"side_index": 1, "at_order": 12, "at_path": "2.9", "guard": "x6 \\notin SplitC2.I2.RO.m",
         "rcond_forms": "rcondt{1} 12 or rcondf{1} 12 (direction needs guard entailment — yours to decide)"},
    ]
    out = _surgery_with_guards(guards)
    joined = " ".join(out)
    assert "rcondt{1} 2" in joined and "rcondf{1} 2" in joined
    # the dotted-path (un-entered body) guards are not rcond-able at the frontier -> skipped
    assert "rcondt{1} 7" not in joined and "rcondt{1} 12" not in joined
    rcond_lines = [l for l in out if "rcond" in l]
    assert len(rcond_lines) == 1


def test_surgery_rcondt_index_right_side_guard() -> None:
    # step4_1 i103: committed `rcondt{2} 3` (RIGHT-side guard `x \notin RO.m` at pos 3).
    # The producer must bind side 2 and index 3, and also expose the genuine left-side
    # alternatives (the relational frontier has guards on both sides).
    guards = [
        {"side_index": 1, "at_order": 6, "at_path": "6", "guard": "x5 \\notin SplitC2.I1.RO.m",
         "rcond_forms": "rcondt{1} 6 or rcondf{1} 6 (direction needs guard entailment — yours to decide)"},
        {"side_index": 1, "at_order": 11, "at_path": "10", "guard": "x6 \\notin SplitC2.I2.RO.m",
         "rcond_forms": "rcondt{1} 11 or rcondf{1} 11 (direction needs guard entailment — yours to decide)"},
        {"side_index": 1, "at_order": 17, "at_path": "15", "guard": "x4 \\notin SplitC1.I2.RO.m",
         "rcond_forms": "rcondt{1} 17 or rcondf{1} 17 (direction needs guard entailment — yours to decide)"},
        {"side_index": 2, "at_order": 3, "at_path": "3", "guard": "x \\notin RO.m",
         "rcond_forms": "rcondt{2} 3 or rcondf{2} 3 (direction needs guard entailment — yours to decide)"},
    ]
    out = " ".join(_surgery_with_guards(guards))
    assert "rcondt{2} 3" in out and "rcondf{2} 3" in out      # the committed right-side index
    # the left-side at_path indices (6/10/15) are the real alternatives, exact (no off-by-one)
    assert "rcondt{1} 6" in out and "rcondt{1} 10" in out and "rcondt{1} 15" in out


def test_surgery_rcond_callout_skips_dotted_and_bad_side() -> None:
    # robustness: only top-level integer at_path on side 1/2 is rcond-able now.
    guards = [
        {"side_index": 2, "at_order": 7, "at_path": "7.3.2", "guard": "g1"},   # nested -> skip
        {"side_index": 3, "at_order": 2, "at_path": "2", "guard": "g2"},        # bad side -> skip
        {"side_index": 1, "at_order": 5, "at_path": "5", "guard": "g3"},        # valid -> emit
    ]
    out = " ".join(_surgery_with_guards(guards))
    assert "rcondt{1} 5" in out
    assert "7.3.2" not in out and "rcondt{3}" not in out


# --- DEFECT 2: inline call-frontier load-bearing target (step4_1 i3/4/5/6) -----------
#
# The inline-call setup row foregrounded the trivial `.init()` SETUP call while the
# load-bearing call the agent actually inlined (`G9(...).distinguish`) was buried. The
# load-bearing frontier procedures sit in `call_site_surface.frontier_live_procedures`.

def test_surgery_inline_names_load_bearing_distinguish_not_init() -> None:
    # step4_1 i3: committed `inline {1} G9(BNR_Adv(A), ...).distinguish`. The setup row
    # only carries `SplitC2.RO_Pair(...).init()`; the load-bearing `G9.distinguish` is in
    # frontier_live_procedures. The Surgery callout must name `G9.distinguish`, NOT the
    # `.init()` setup call and NOT the named-equiv subject `CPA_game.main`.
    view = {
        "program_frontier": {"frontier_alignment": {"rows": [
            {
                "role": "setup / initialization",
                "left": "SplitC2.RO_Pair(SplitC2.I1.RO, SplitC2.I2.RO).init() "
                        "[call: SplitC2.RO_Pair(SplitC2.I1.RO, SplitC2.I2.RO).init() — use inline/call, not sp/wp]",
                "right": "4 setup statement(s): UFCMA.bad1 <- false; UFCMA.cbad1 <- 0; UFCMA.bad2 <- false; ... (1 more)",
                "location": {"left_paths": ["1"], "right_paths": ["1", "2", "3", "4"]},
            },
            {
                "role": "call frontier",
                "left": "no matching left-side call at this frontier",
                "right": "r <@ RO.get(n, C.ofintd 0)",
            },
            {
                "role": "loop frontier",
                "left": "no matching left-side loop at this frontier",
                "right": "while (i < size ns) {",
            },
            {
                "role": "branch frontier",
                "left": "no matching left-side branch at this frontier",
                "right": "if ((n, C.ofintd 0) \\in ROout.m) {",
            },
        ]}},
        "call_site_surface": {"frontier_blockers": [{
            "kind": "named_call_subject_absent_at_frontier",
            "symbol": "UFCMA_genCC",
            "subject_procedures": [
                "CPA_game(CCA_CPA_Adv(A), RealOrcls(GenChaChaPoly(CCRO(FinRO)))).main",
                "UFCMA(A, St).main",
            ],
            "frontier_live_procedures": ["CPA_game.main", "G9.distinguish", "RO.get", "UFCMA.set_bad2"],
        }]},
    }
    call_lines = [l for l in _surgery_where(view) if l.startswith("procedure-call prefix")]
    assert len(call_lines) == 1
    line = call_lines[0]
    assert "G9.distinguish" in line                       # the load-bearing frontier call
    assert "load-bearing frontier call" in line
    assert "inline" not in line and "sp" not in line and "wp" not in line
    # CPA_game.main is the named-equiv subject, NOT the frontier call named here
    assert "CPA_game.main" not in line
    where = " ".join(_surgery_where(view))
    assert "RO.get" not in where
    assert "while (i < size ns)" not in where
    assert "ROout.m" not in where


def test_up_to_bad_coherence_is_panel_fact_not_manager_signal() -> None:
    view = {
        "proof_status": {"status": "open", "goal_type": "pRHL",
                         "view_focus": "relational_program", "current_layer": "call_site"},
        "current_goal": {"lines": [
            "r <@ G9(BNR_Adv(A), RO).distinguish(x)",
            "post = ! (UFCMA.bad1{2} \\/ UFCMA.bad2{2}) => r{1} = forged{2}",
        ]},
        "program_frontier": {"frontier_alignment": {"rows": [{
            "role": "setup / initialization",
            "left": "SplitC2.RO_Pair(SplitC2.I1.RO, SplitC2.I2.RO).init() "
                    "[call: SplitC2.RO_Pair(SplitC2.I1.RO, SplitC2.I2.RO).init() — use inline/call, not sp/wp]",
            "right": "4 setup statement(s): UFCMA.bad1 <- false; UFCMA.cbad1 <- 0; UFCMA.bad2 <- false; ...",
            "location": {"left_paths": ["1"], "right_paths": ["1", "2", "3", "4"]},
        }]}},
        "call_site_surface": {"frontier_blockers": [{
            "kind": "named_call_subject_absent_at_frontier",
            "symbol": "UFCMA_genCC",
            "subject_procedures": ["CPA_game.main"],
            "frontier_live_procedures": ["CPA_game.main", "G9.distinguish"],
        }]},
        "decision_context": {"up_to_bad_call": {
            "text": "Consider the up-to-bad form call (_: (UFCMA.bad1 \\/ UFCMA.bad2), <inv>).",
            "active_bad_events": ["UFCMA.bad1", "UFCMA.bad2"],
            "candidate": "call (_: (UFCMA.bad1 \\/ UFCMA.bad2), <inv>).",
            "certified": False,
            "guarantee": "UNCERTIFIED suggestion",
        }},
        "inspect_lookup_handles": {"ask_manager_for": [
            {"intent": "tactic_forms", "payload": {"name": "call"}},
        ]},
    }

    model = _model(view)
    panel = model["primary_panel"]
    facts = {item["key"]: item for item in panel.get("facts", [])}
    assert "decision_signals" not in model.get("metadata", {})
    assert "up_to_bad_call_compatibility" in facts
    value = facts["up_to_bad_call_compatibility"]["value"]
    assert value["active_bad_events"] == ["UFCMA.bad1", "UFCMA.bad2"]
    assert value["relevant_call_form_family"] == (
        "call (_: (UFCMA.bad1 \\/ UFCMA.bad2), <inv>)."
    )
    blob = json.dumps(model, ensure_ascii=False)
    assert "Manager signal" not in blob
    assert "Consider the up-to-bad form" not in blob
    tactic_choices = {
        name
        for action in model.get("actions", [])
        if action["intent"] == "tactic_forms"
        for name in action["choices"]["name"]
    }
    assert {"call", "inline"} <= tactic_choices


def test_up_to_bad_context_after_call_is_guarded_obligation_not_call_offer() -> None:
    view = {
        "proof_status": {"status": "open", "goal_type": "pRHL",
                         "view_focus": "relational_program", "current_layer": "call_site"},
        "current_goal": {"lines": [
            "pre =",
            "  ! (UFCMA.bad1{2} \\/ UFCMA.bad2{2}) /\\ inv ...",
            "p0 <- p                                       (1)  p0 <- p",
            "c0 <@ RealOrcls(GenChaChaPoly(...)).enc(p0)   (2)  c0 <@ UFCMA(RO).O.enc(p0)",
            "post =",
            "  ! (UFCMA.bad1{2} \\/ UFCMA.bad2{2}) => c0{1} = c0{2}",
        ]},
        "program_frontier": {"frontier_alignment": {"rows": [{
            "role": "call frontier",
            "left": "c0 <@ RealOrcls(GenChaChaPoly(...)).enc(p0)",
            "right": "c0 <@ UFCMA(RO).O.enc(p0)",
        }]}},
        "decision_context": {"up_to_bad_call": {
            "active_bad_events": ["UFCMA.bad1", "UFCMA.bad2"],
            "candidate": "call (_: (UFCMA.bad1 \\/ UFCMA.bad2), <inv>).",
        }},
    }

    model = _model(view)
    facts = {item["key"]: item for item in model["primary_panel"].get("facts", [])}
    fact = facts["up_to_bad_call_compatibility"]
    assert fact["label"] == "Bad-event guarded obligation"
    value = fact["value"]
    assert value["visible_guard"] == "!(UFCMA.bad1 \\/ UFCMA.bad2)"
    assert "relevant_call_form_family" not in value
    assert "visible_call_offer_shape" not in value


def test_surgery_inline_load_bearing_prefers_distinguish_over_main() -> None:
    # step4_1 i6: frontier has both `G4.distinguish` and `G5_end.main`; the committed
    # tactic inlines the `.distinguish`. `.distinguish` outranks a bare `.main`.
    view = {"call_site_surface": {"frontier_blockers": [{
        "kind": "named_call_subject_absent_at_frontier",
        "symbol": "UFCMA_genCC",
        "subject_procedures": ["CPA_game(CCA_CPA_Adv(A), RealOrcls(GenChaChaPoly(CCRO(FinRO)))).main"],
        "frontier_live_procedures": ["CPA_game.main", "G4.distinguish", "G5_end.main", "RO.get"],
    }]}}
    assert _load_bearing_frontier_call(view) == "G4.distinguish"


def test_surgery_inline_no_load_bearing_call_falls_back_to_init_text() -> None:
    # When the structured frontier carries NO load-bearing call (only `.init()` and the
    # left game call is in the goal echo only — step4_1 i75), the callout keeps the old
    # `.init()`-named form rather than inventing a target.
    view = {
        "program_frontier": {"frontier_alignment": {"rows": [{
            "role": "setup / initialization",
            "left": "Log(LRO).init() [call: Log(LRO).init() — use inline/call, not sp/wp]",
            "right": "a <- 0",
            "location": {"left_paths": ["1"], "right_paths": ["1"]},
        }]}},
        "call_site_surface": {"frontier_blockers": [{"kind": "IF"}, {"kind": "ASSIGN"}]},
    }
    assert _load_bearing_frontier_call(view) == ""
    line = [l for l in _surgery_where(view) if l.startswith("procedure-call prefix")][0]
    assert "Log(LRO).init()" in line and "load-bearing" not in line
    assert "inline" not in line and "sp" not in line and "wp" not in line
