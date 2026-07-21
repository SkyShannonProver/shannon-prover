from __future__ import annotations

from workflow.proof_management.analyzers.pure_tail import PureTailAnalyzer
from workflow.proof_management.node_state import ProofNodeState


def _state(view: dict) -> ProofNodeState:
    return ProofNodeState(node_id="Tree-unit", base_workspace_view=view)


def _view(goal: str) -> dict:
    return {
        "proof_status": {
            "goal_type": "ambient",
            "current_layer": "ambient_logic",
            "view_focus": "pure_tail",
        },
        "current_goal": {"lines": goal.strip().splitlines()},
        "program_frontier": {"call_sites": []},
        "structural_checkpoints": {
            "items": [
                {
                    "checkpoint_id": "cp_branch",
                    "semantic_id": "before_branch_work",
                    "semantic_ids": ["before_branch_work", "after_seq_opened"],
                    "label": "Before branch work",
                    "undo_scope": "branch_local",
                    "submit": {
                        "intent": "undo_to_checkpoint",
                        "payload": {"checkpoint_id": "cp_branch"},
                    },
                }
            ]
        },
    }


def test_pure_tail_analyzer_reports_map_projection_gap() -> None:
    goal = r"""
Current goal
forall &1 &2,
  p{1} = p{2} =>
  (forall n0 c0,
     (n0, c0) \in ROF.m{1}.[(p{2}.`1, c1{2}) <- r{1}] =>
     n0 \in n{1} :: BNR.lenc{1})
"""
    surface = PureTailAnalyzer().analyze(state=_state(_view(goal)), view=_view(goal))

    families = {item["family"] for item in surface["obligation_families"]}
    assert "map_update_projection" in families
    assert "constructor_projection" in families
    assert "map_membership_preservation" in families
    assert surface["ambient_memory_translation"]["visible_decorations"]
    gap = surface["gap_analysis"][0]
    assert gap["signal"] == "map_key_membership_head_alignment"
    assert gap["reversible_to"][0]["undo_scope"] == "branch_local"


def test_pure_tail_analyzer_reports_membership_and_witness_sources() -> None:
    goal = r"""
Current goal
H16:
  (t1, t') \in
    UFCMA_l.lbad1{2} ++
    map (fun t'0 => (t0L, t'0))
      (map (fun c3 => c3.`4)
        (filter (fun c3 => c3.`1 = p{2}.`1) Mem.lc{2}))
exists (n1 : nonce),
  (n1 = p{2}.`1 \/ n1 \in BNR.lenc{2}) /\
  (oget UFCMA.log{2}.[p{2}.`1 <- (a{2}, c1{2}, t1)].[n1]).`3 = t1
"""
    surface = PureTailAnalyzer().analyze(state=_state(_view(goal)), view=_view(goal))

    membership = surface["membership_decomposition_surface"]
    witnesses = surface["existential_witness_surface"]
    lookup = surface["map_update_lookup_surface"]
    assert {
        "concat_membership",
        "map_membership",
        "filter_membership",
    } <= set(membership["source_shapes"])
    assert any(item.get("name") == "n1" for item in witnesses["binders"])
    sources = {item["source"] for item in witnesses["candidate_sources"]}
    assert "map_update_key" in sources
    assert "membership_member" in sources
    assert lookup["key_cases"]
    assert surface["gap_analysis"][0]["signal"] == (
        "local_membership_decomposition_available"
    )


def test_pure_tail_analyzer_ignores_live_call_frontier() -> None:
    goal = "Current goal\nforall x, x = x"
    view = _view(goal)
    view["program_frontier"] = {"call_sites": [{"procedure": "M.f"}]}
    view["proof_status"]["current_layer"] = "procedure_body"

    assert PureTailAnalyzer().analyze(state=_state(view), view=view) == {}


# --- NEW-2: real operators + visible hypotheses, not a fuzzy bucket (2026-06-05) ---
def test_goal_operators_lists_real_symbols_not_a_bucket() -> None:
    from workflow.proof_management.analyzers.pure_tail import (
        _goal_operators, _visible_hypotheses,
    )
    goal = (
        "m: word fset\ny: word\n"
        "------------------------------------------------------------\n"
        "mu dword (fun (x : word) => x ^ y \\in m) = (card m)%r * mu1 dword AWord.zeros"
    )
    ops = _goal_operators(goal)
    # the real operators the agent must look up are surfaced; bound vars (m,y,x) are not
    assert "mu" in ops and "card" in ops and "mu1" in ops and "dword" in ops
    assert "AWord.zeros" in ops
    assert "m" not in ops and "x" not in ops and "y" not in ops   # bound variables
    assert "fun" not in ops                                        # binder keyword
    assert _visible_hypotheses(goal) == []                        # only type bindings


def test_goal_operators_drops_multivar_binders_and_types() -> None:
    # panel re-audit FIX-4c: the old extractor mislabeled (a) the 2nd+ variable of a
    # multi-name binder group `(result_L result_R : ptxt)` and (b) type symbols
    # (`ptxt`/`bool`/`rand`/`fmap`, incl. the nested-paren `(rand, ptxt) fmap`) as
    # "Goal operators" — confirmed 误导 on cpa_ddh0 / eq_Game1_Game2. Both are now
    # dropped; the real operators survive.
    from workflow.proof_management.analyzers.pure_tail import _goal_operators
    goal = (
        "&m: {}\n"
        "------------------------------------------------------------\n"
        "forall (result_L result_R : ptxt * ptxt) (A_L A_R : (glob A)) "
        "(m_L : (rand, ptxt) fmap) (b_L : bool),\n"
        "  result_L = result_R => big predT result_R \\in m_L"
    )
    ops = _goal_operators(goal)
    assert "big" in ops and "predT" in ops and "\\in" in ops   # real operators kept
    # trailing vars of a multi-name binder group are NOT operators
    for binder in ("result_L", "result_R", "A_L", "A_R", "m_L", "b_L"):
        assert binder not in ops, f"binder {binder} leaked as operator"
    # type symbols (including the nested-paren `(rand, ptxt) fmap`) are NOT operators
    for typ in ("ptxt", "rand", "fmap", "bool"):
        assert typ not in ops, f"type {typ} leaked as operator"


def test_goal_operators_drops_memory_labels_and_program_vars() -> None:
    # live PIR playground: `hr` (the `&hr` memory) and `PIR.s`/`PIR.s'` (program variables
    # carrying a `{hr}` memory annotation) were surfaced as "Goal operators" — they are NOT
    # operators. A real operator never has a `{mem}` suffix; searchable constants without one
    # (`Top.N`, `zerow`) survive.
    from workflow.proof_management.analyzers.pure_tail import _goal_operators
    goal = (
        "i0: int\n"
        "&hr: {b : bool, j : int, s, s' : int list}\n"
        "------------------------------------------------------------\n"
        "big predT a PIR.s{hr} +^ big predT a PIR.s'{hr} = sxor2 i0 zerow Top.N"
    )
    ops = _goal_operators(goal)
    assert "hr" not in ops                                  # memory label
    assert "PIR.s" not in ops and "PIR.s'" not in ops       # program vars (have {hr} suffix)
    assert "big" in ops and "sxor2" in ops                  # real operators kept
    # OVER-ROUTE GUARD (cc_step4_1): the `filter` promotion / list-op fix must NOT cause a PIR-style
    # `+^`/int-`+`/`-` goal to gain any raw `+`/`-`/`+^` operator route (the documented #1 risk — a
    # `(+^)`/group `+`/`-` route on every arithmetic goal mis-routed PIR's big-sum steps). A type-
    # carried group-op route was investigated and deliberately NOT shipped; this asserts no such
    # operator leaks. (The pre-existing curated `(+^)` route from `_LEMMA_OPS` lives on a different,
    # relational path — `_goal_operators` itself never surfaces a bare `+`/`-`/`+^`.)
    for routed in ("(+)", "(-)", "+", "-", "(+^)", "+^", "((+) (-))"):
        assert routed not in ops, f"over-routed arithmetic operator {routed!r} on a PIR-style goal"
    assert "Top.N" in ops and "zerow" in ops                # searchable constants (no {mem}) kept


def test_goal_operators_drops_let_bound_variables() -> None:
    # re-audit verification follow-up: a `let x = …` / `let (a, b) = …` binder is a VARIABLE
    # (accessed as x.`1 etc.), not an operator (CramerShoup `let sk2 = (…)` surfaced `sk2`).
    from workflow.proof_management.analyzers.pure_tail import _goal_operators
    goal = (
        "&m: {}\n----\n"
        "let sk2 = DH.G.g in let (a, b) = pair in "
        "big predT (sk2.`1) = a + DH.G.g"
    )
    ops = _goal_operators(goal)
    for binder in ("sk2", "a", "b"):   # `let x = …` and `let (a, b) = …` bind these
        assert binder not in ops, f"let-binder {binder} leaked as operator"
    assert "big" in ops and "predT" in ops and "DH.G.g" in ops   # real operators survive


def test_visible_hypotheses_extracts_propositions_only() -> None:
    from workflow.proof_management.analyzers.pure_tail import _visible_hypotheses
    goal = (
        "&m: {}\nsigma_: int\nge0_s: 0 <= sigma_\n"
        "----------------------------------\nPr[X] = Pr[Y]"
    )
    hyps = _visible_hypotheses(goal)
    assert "ge0_s: 0 <= sigma_" in hyps         # a proposition
    assert not any(h.startswith("sigma_:") for h in hyps)   # a bare type, not a hyp


def test_memory_translation_reports_named_memory_decorations() -> None:
    from workflow.proof_management.analyzers.pure_tail import pure_tail_surface

    goal = (
        "&m: {i : int, p : message}\n"
        "------------------------------------------------------------\n"
        "p{m} <> [] => size (drop block_size p{m}) < size p{m}"
    )
    surface = pure_tail_surface({
        "proof_status": {"current_layer": "ambient_logic", "goal_type": "ambient"},
        "current_goal": {"lines": goal.splitlines()},
    })
    memory = surface["ambient_memory_translation"]

    assert "{m}" in memory["visible_decorations"]
    assert "&m:" in memory["introduced_memory_bindings"]
    assert "p{m}" in memory["decorated_terms"]


def test_integer_arithmetic_surface_extracts_drop_div_mod_boundary() -> None:
    from workflow.proof_management.analyzers.pure_tail import pure_tail_surface

    goal = (
        "p: message\n"
        "hp: p <> []\n"
        "hd: block_size <> 0\n"
        "------------------------------------------------------------\n"
        "size p %/ block_size + b2i (size p %% block_size <> 0) =\n"
        "size (drop block_size p) %/ block_size +\n"
        "b2i (size (drop block_size p) %% block_size <> 0) + 1"
    )
    surface = pure_tail_surface({
        "proof_status": {"current_layer": "ambient_logic", "goal_type": "ambient"},
        "current_goal": {"lines": goal.splitlines()},
    })
    arithmetic = surface["integer_arithmetic_surface"]

    assert "integer division `%/`" in arithmetic["visible_shapes"]
    assert "integer modulo `%%`" in arithmetic["visible_shapes"]
    assert arithmetic["size_drop_terms"][0]["drop_amount"] == "block_size"
    assert arithmetic["size_drop_terms"][0]["list_term"] == "p"
    assert arithmetic["split_candidates"][0]["condition"] == "block_size <= size p"
    families = {
        lemma
        for item in arithmetic["lemma_families"]
        for lemma in item.get("lemma_names", [])
    }
    assert {"size_drop", "drop_oversize", "divzMDl", "modzMDl", "divz_small", "modz_small"} <= families
    assert any("size p %% block_size <> 0" in guard for guard in arithmetic["b2i_guards"])


def test_integer_arithmetic_surface_ignores_premise_only_modulo() -> None:
    from workflow.proof_management.analyzers.pure_tail import pure_tail_surface

    goal = (
        "------------------------------------------------------------\n"
        "forall x, x %% n = 0 =>\n"
        "left x \\in log <=> right x \\in log"
    )
    surface = pure_tail_surface({
        "proof_status": {"current_layer": "ambient_logic", "goal_type": "ambient"},
        "current_goal": {"lines": goal.splitlines()},
    })

    assert "integer_arithmetic_surface" not in surface


def test_pure_tail_reports_premise_conjunction_and_iter_successor_shapes() -> None:
    from workflow.proof_management.analyzers.pure_tail import pure_tail_surface

    goal = (
        "&m: {i : int, c : byte list, p : message}\n"
        "------------------------------------------------------------\n"
        "r = iter (size p{m} %/ block_size + b2i (size p{m} %% block_size <> 0)) f x =>\n"
        "p{m} <> [] =>\n"
        "r = iter (size (drop block_size p{m}) %/ block_size +\n"
        "          b2i (size (drop block_size p{m}) %% block_size <> 0) + 1) f y /\\\n"
        "size (drop block_size p{m}) < size p{m}"
    )
    surface = pure_tail_surface({
        "proof_status": {"current_layer": "ambient_logic", "goal_type": "ambient"},
        "current_goal": {"lines": goal.splitlines()},
    })

    shape = surface["obligation_shape_surface"]
    premise_shapes = [item["shape"] for item in shape["implication_premises"]]
    obligation_shapes = [item["shape"] for item in shape["conclusion_obligations"]]
    assert premise_shapes == ["iter equality premise", "nonempty-list premise"]
    assert "iter equality obligation" in obligation_shapes
    assert "size/drop inequality obligation" in obligation_shapes
    successor = surface["iter_successor_surface"]["successor_calls"][0]
    assert successor["successor_offset"] == "+ 1"
    assert "size (drop block_size p{m})" in successor["count_shape"]


def test_sampling_bijection_no_longer_false_fires_on_any_d_word() -> None:
    # NEW-4(b): the old " d" token matched any space-d word. A pure membership goal
    # with `dom`/no distribution must NOT be tagged sampling_bijection.
    from workflow.proof_management.analyzers.pure_tail import _sampling_bijection_family
    fam = _sampling_bijection_family("(x \\in dom m) = exists a, a \\in m /\\ a = x")
    assert fam == {} or fam.get("family") != "sampling_bijection"


def test_pure_focus_panel_drops_bucket_and_family_for_operators() -> None:
    from workflow.surface_composer import compose_surface_model
    pt = {
        "state": "ambient_pure_tail",
        "goal_operators": ["mu", "card", "mu1", "dword"],
        "visible_hypotheses": ["ge0_s: 0 <= sigma_"],
        "obligation_families": [{"family": "sampling_bijection", "evidence": ["x"]}],
    }
    model = compose_surface_model(
        {"proof_status": {"current_layer": "ambient_logic"}, "pure_tail_surface": pt},
        "l4_checked_action_surface",
    ).to_dict()
    focus = {
        item["key"]: item.get("value")
        for item in (model.get("primary_panel") or {}).get("facts", [])
    }
    assert model.get("primary_panel") is None
    # The producer may keep goal_operators as raw mechanical facts for action choices,
    # but the normal proof panel no longer re-lists broad operator tokens as content.
    assert "goal_operators" not in focus
    # 鸡肋 block 5A: the visible_hypotheses re-list is no longer rendered (already shown
    # verbatim in the goal block); the panel no longer carries it.
    assert "visible_hypotheses" not in focus
    assert "goal_shape" not in focus                 # no fuzzy bucket label
    assert "obligation_families" not in focus         # no fuzzy classifier in the panel
    assert "sampling_bijection" not in str(focus)
    # panel-audit 2026-06-26: `close_with` (smt/rewrite/case menu) and `yours` were DELETED
    # (鸡肋; close_with also 误导 by insisting on smt/rewrite/case).
    assert "yours" not in focus and "close_with" not in focus


def test_goal_operators_strips_ec_prompt_marker() -> None:
    # regression-audit MINOR (2026-06-05): the EC emacs prompt `[38|check]>` left in
    # a saved goal leaked a spurious `check` operator. _conclusion_text now strips it.
    from workflow.proof_management.analyzers.pure_tail import _goal_operators
    ops = _goal_operators("m: word fset\n----\n(x ^ y \\in m) = mem (image f m)\n[38|check]>")
    assert "check" not in ops
    assert "mem" in ops and "image" in ops


# --- panel audit PRG.ec::Plog_Psample: finite-map get/set is SYMBOLIC and was invisible ---
# Goals/tactics below are verbatim from the captured run
# (tmp/wt/oss-prep/.panel_audit_handoff/plog_psample/steps.json). The EC `search` skeletons
# `(_.[_ <- _].[_])` / `"_.[_<-_]"` and the `Bad` predicate name were ground-truthed against
# EC's native `search` over PRG.ec (returns get_set_sameE/get_setE/mem_set / negBadE).
_FMAP_GET = "(_.[_ <- _].[_])"
_FMAP_SET = '"_.[_<-_]"'


def test_goal_operators_routes_get_of_set_to_family_not_oget() -> None:
    # i13: `(oget m.[k<-v].[k]).`2 = …` closed by `smt(get_set_sameE)`. The get-of-set
    # skeleton must lead so operator_lemmas lands on get_set_sameE/get_setE — NOT bare `oget`.
    from workflow.proof_management.analyzers.pure_tail import _goal_operators
    goal = (
        "H: ! Bad P.logP{2} F.m{2}\n"
        "H5: ! Bad (P.seed{2} :: P.logP{2}) F.m{2}\n"
        "------------------------------------------------------------------------\n"
        "(oget F.m{1}.[P.seed{2} <- (r1L, r2L)].[P.seed{2}]).`2 = r2L\n"
        "[64|check]>"
    )
    ops = _goal_operators(goal)
    assert ops[0] == _FMAP_GET                      # focused get_set route is the lead
    assert ops.index(_FMAP_GET) < ops.index("oget")  # get_set family BEFORE bare oget
    # Over-correction fix (panel re-audit i45/69/78): the close is `smt(get_set_sameE)`, NOT
    # negBadE — `! Bad` here is just a standing hypothesis, so it must NOT be pulled onto a
    # get-of-set conclusion (the get_set route is the load-bearing one).
    assert "Bad" not in ops


def test_goal_operators_routes_set_membership_to_set_family() -> None:
    # i17: `r0 \in m.[k<-v] <=> …` closed by `smt(mem_set)`. The whole-set notation
    # `"_.[_<-_]"` (whose family contains mem_set) must lead, not bare `\in`.
    from workflow.proof_management.analyzers.pure_tail import _goal_operators
    goal = (
        "H: ! Bad P.logP{2} F.m{2}\n"
        "------------------------------------------------------------------------\n"
        "r0 \\in F.m{1}.[P.seed{2} <- (r1L, r2L)] <=>\n"
        "(r0 \\in F.m{2}) \\/ (r0 \\in P.seed{2} :: P.logP{2})\n"
        "[68|check]>"
    )
    ops = _goal_operators(goal)
    assert _FMAP_SET in ops                          # set/membership family present
    assert ops[0] == _FMAP_SET                       # and it is the lead route
    assert ops.index(_FMAP_SET) < ops.index("\\in")  # set family BEFORE bare `\in`


def test_goal_operators_does_not_route_to_dead_end_inv() -> None:
    # i25: conclusion is the local inductive `inv F.m{1} F.m{2} (…)`, closed by
    # `smt(negBadE)`. `inv` has ZERO rewrite lemmas (dead end) — it must NOT be a route;
    # the `Bad` characterization (negBadE) must be surfaced instead (!Bad in hypotheses).
    from workflow.proof_management.analyzers.pure_tail import _goal_operators
    goal = (
        "H: ! Bad P.logP{2} F.m{2}\n"
        "H5: ! Bad (P.seed{2} :: P.logP{2}) F.m{2}\n"
        "------------------------------------------------------------------------\n"
        "inv F.m{1} F.m{2} (P.seed{2} :: P.logP{2})\n"
        "[76|check]>"
    )
    ops = _goal_operators(goal, inductive_heads=frozenset({"inv"}))
    assert "inv" not in ops          # dead-end local predicate is dropped from the route
    assert ops == ["Bad"]            # only the reachable Bad characterization is offered


def test_goal_operators_set_plus_inv_routes_to_set_and_bad_not_inv() -> None:
    # i48: `inv m.[k<-v] m' logP` closed by `smt()` (needs mem_set/negBadE facts). The set
    # family + Bad must be surfaced; the dead-end `inv` head must not be a route.
    from workflow.proof_management.analyzers.pure_tail import _goal_operators
    goal = (
        "H: ! Bad P.logP{2} F.m{2}\n"
        "H6: ! Bad P.logP{2} F.m{2}\n"
        "------------------------------------------------------------------------\n"
        "inv F.m{1}.[x{2} <- (r1L, r2L)] F.m{2} P.logP{2}\n"
        "[99|check]>"
    )
    ops = _goal_operators(goal, inductive_heads=frozenset({"inv"}))
    assert "inv" not in ops
    # Over-correction fix (panel re-audit i80): the conclusion is an `inv`-after-SET proved by
    # its constructor + the set fact; `! Bad` is only a standing hypothesis, so the set route
    # leads and Bad is NOT pulled in (it was a decoy steering toward negBadE the close never uses).
    assert _FMAP_SET in ops and "Bad" not in ops


def test_goal_operators_keeps_inv_when_it_is_a_real_operator_not_inductive() -> None:
    # REGRESSION (cross-lemma): `inv` is ALSO the field/group inverse OPERATOR
    # (eval/examples/Pedersen.ec `inv (m' - m)`), a genuine lemma-bearing operator. When the
    # source does NOT declare `inv` inductive, it must be KEPT in the route — the dead-end
    # drop is gated on the SOURCE-confirmed inductive names, never a hardcoded name.
    from workflow.proof_management.analyzers.pure_tail import (
        _goal_operators, _local_inductive_predicate_names,
    )
    goal = (
        "d, d', m, m' : t\n"
        "------------------------------------------------------------------------\n"
        "x = Some ((d - d') * inv (m' - m))\n"
        "[12|check]>"
    )
    # Pedersen.ec declares no `inductive inv`, so the confirmed-inductive set excludes it.
    assert "inv" not in _local_inductive_predicate_names("op inv : t -> t.\nlemma foo : x = inv y.")
    ops = _goal_operators(goal, inductive_heads=frozenset())            # no source confirmation
    assert "inv" in ops                                                  # real operator preserved
    # and even with PRG's inductive set, a DIFFERENT inductive name does not drop `inv`
    assert "inv" in _goal_operators(goal, inductive_heads=frozenset({"Bad"}))


def test_local_inductive_predicate_names_parses_declarations() -> None:
    from workflow.proof_management.analyzers.pure_tail import _local_inductive_predicate_names
    src = "local inductive Bad logP (m : ('a,'b) fmap) =\n  | Cycle of (!uniq logP)\ninductive inv m1 m2 = | Invariant of x."
    names = _local_inductive_predicate_names(src)
    assert names == frozenset({"Bad", "inv"})


def test_goal_operators_bad_only_from_hypotheses() -> None:
    # i21: conclusion `(oget m.[k]).`2 = …` (no map SET, no Bad in conclusion) closed by
    # `smt(negBadE)` — the !Bad obligation lives ONLY in the hypotheses (H/H5). `_goal_operators`
    # must read the hypotheses and still surface `Bad`.
    from workflow.proof_management.analyzers.pure_tail import _goal_operators
    goal = (
        "H: ! Bad P.logP{2} F.m{2}\n"
        "H5: ! Bad (P.seed{2} :: P.logP{2}) F.m{2}\n"
        "------------------------------------------------------------------------\n"
        "(oget F.m{1}.[P.seed{2}]).`2 = r2L\n"
        "[72|check]>"
    )
    ops = _goal_operators(goal)
    assert "Bad" in ops              # surfaced from the hypotheses
    assert _FMAP_GET not in ops      # a bare get with NO set is not a get-of-set route
    assert _FMAP_SET not in ops      # and there is no set/update in this conclusion


def test_goal_operators_no_false_fmap_route_without_set() -> None:
    # Guard: a pure non-map goal must not gain a spurious map-skeleton route.
    from workflow.proof_management.analyzers.pure_tail import _goal_operators
    ops = _goal_operators(
        "m: word fset\ny: word\n----\nmu dword (fun x => x ^ y \\in m) = (card m)%r"
    )
    assert _FMAP_GET not in ops and _FMAP_SET not in ops
    assert "Bad" not in ops          # no Bad predicate anywhere
    assert "mu" in ops and "card" in ops
# --- panel-audit 2026-06-13 (PRG.ec::Plog_Psample strands) ------------------------
# Two source-keyed routes that NAME the mechanical move keyed on the goal CONCLUSION,
# instead of dumping the conclusion head (`Plog.prg`/`P0`/`Bad`) as a searchable
# operator. Ground-truthed against the real captured goals.
import pathlib  # noqa: E402

_PRG_EC = str(
    pathlib.Path(__file__).resolve().parents[1] / "eval" / "examples" / "PRG.ec"
)


def _ambient_state(goal: str, *, file_path: str = "") -> ProofNodeState:
    return ProofNodeState(
        node_id="Tree-strands",
        file_path=file_path,
        base_workspace_view=_view(goal),
    )


def test_losslessness_route_is_projected_from_core_mechanical_candidates() -> None:
    goal = (
        "&m: {}\n"
        "------------------------------------------------------------\n"
        "forall (F0 <: ARF{-A}) (P0 <: APRG{-A}),\n"
        "  islossless P0.prg => islossless F0.f => islossless A(F0, P0).a"
    )
    view = _view(goal)
    view["application_context"] = {"mechanical_goal_candidates": [{
        "lemma": "AaL",
        "match_kind": "losslessness_obligation_match",
        "parameter_bindings": {"F": "F0", "P": "P0"},
        "direct_application": "exact AaL.",
        "required_premises": ["islossless P0.prg", "islossless F0.f"],
    }]}
    surface = PureTailAnalyzer().analyze(
        state=_ambient_state(goal, file_path=_PRG_EC), view=view
    )
    assert "conclusion_lemma_routes" not in surface
    candidate = surface["mechanical_goal_candidates"][0]
    assert candidate["lemma"] == "AaL"
    assert candidate["direct_application"] == "exact AaL."


def test_pure_tail_does_not_rescan_source_for_losslessness_routes() -> None:
    goal = "&m: {}\n----\nislossless F.f"
    surface = PureTailAnalyzer().analyze(
        state=_ambient_state(goal, file_path=_PRG_EC), view=_view(goal)
    )
    assert "conclusion_lemma_routes" not in surface
    assert "mechanical_goal_candidates" not in surface


def test_conclusion_keyed_lemma_route_silent_without_source() -> None:
    # No `file_path` (the unit `_state` path) ⇒ the source-keyed route cannot fire and
    # must collapse silently (never raise); the rest of the surface is unaffected.
    goal = (
        "&m: {}\n----\n"
        "forall &2, Bad P.logP{2} F.m{2} => islossless F.f"
    )
    surface = PureTailAnalyzer().analyze(state=_state(_view(goal)), view=_view(goal))
    assert "conclusion_lemma_routes" not in surface


def test_inductive_intro_route_names_Cycle_and_Collision() -> None:
    # i32 `apply Cycle; smt.` — the goal PROVES the file-local inductive predicate
    # `Bad`; the mechanical help is its introduction constructors (`apply Cycle` /
    # `apply Collision`), parsed from the multi-line `inductive Bad … = | … | …` decl.
    goal = (
        "&m: {}\n"
        "&2: {r1 : seed, r2 : output}\n"
        "v: seed\nv0: output\n"
        "h_nuniq: ! uniq P.logP{2}\n"
        "------------------------------------------------------------\n"
        "Bad (P.seed{2} :: P.logP{2}) F.m{2}"
    )
    surface = PureTailAnalyzer().analyze(
        state=_ambient_state(goal, file_path=_PRG_EC), view=_view(goal)
    )
    routes = surface["inductive_intro_routes"]
    assert [r["constructor"] for r in routes] == ["Cycle", "Collision"]
    assert [r["submit"] for r in routes] == ["apply Cycle.", "apply Collision."]
    # this goal is NOT a losslessness conclusion, so no lemma route is mixed in
    assert "conclusion_lemma_routes" not in surface


def test_inductive_intro_route_does_not_fire_on_lossless_goal() -> None:
    # The two routes are conclusion-shape disjoint: an `islossless X` head yields a
    # lemma route, never an inductive intro route, and vice-versa.
    goal = (
        "&m: {}\n----\n"
        "forall &2, Bad P.logP{2} F.m{2} => islossless F.f"
    )
    surface = PureTailAnalyzer().analyze(
        state=_ambient_state(goal, file_path=_PRG_EC), view=_view(goal)
    )
    assert "inductive_intro_routes" not in surface
    assert "conclusion_lemma_routes" not in surface


def test_pure_focus_panel_surfaces_core_lemma_match_and_intro_routes() -> None:
    # The renderer turns the route dicts into readable `submit — why` bullets, placed
    # ABOVE the operator tokens (they NAME the closing move).
    from workflow.surface_composer import compose_surface_model
    pt = {
        "mechanical_goal_candidates": [
            {
                "lemma": "AaL",
                "match_kind": "losslessness_obligation_match",
                "direct_application": "exact AaL.",
                "required_premises": ["islossless P.prg", "islossless F.f"],
            }
        ],
        "inductive_intro_routes": [
            {"constructor": "Cycle", "submit": "apply Cycle.", "why": "a constructor."}
        ],
        "goal_operators": ["Bad"],
    }
    model = compose_surface_model(
        {"proof_status": {"current_layer": "ambient_logic"}, "pure_tail_surface": pt},
        "l4_checked_action_surface",
    ).to_dict()
    focus = {item["key"]: item.get("value") for item in model["primary_panel"].get("facts", [])}
    assert any("exact AaL." in str(s) for s in focus["mechanical_goal_candidates"])
    assert any("apply Cycle." in str(s) for s in focus["inductive_intro_routes"])
    tactic_choices = {
        name
        for action in model.get("actions", [])
        if action["intent"] == "tactic_forms"
        for name in action["choices"]["name"]
    }
    # Exact loaded submit routes already carry the applicable form. Repeating a
    # generic apply reference page would add tokens without new state evidence.
    assert "apply" not in tactic_choices


# --- cc_step4_1 operator-route widening (panel audit 2026-06-28) -------------------------
def test_goal_operators_promotes_filter_past_the_cap() -> None:
    """Sub-cluster (a): `filter` is a named identifier literally in the goal, member of the
    `mem_filter`/`filter_*` family. On cc_step4_1 i94/i99 it was tokenised at index 9/11 and
    LOST to the `[:8]` operator cap (while `map`/`has` survived by token-position luck). It is
    now PROMOTED ahead of the cap. This only reorders already-extracted operators."""
    from workflow.proof_management.analyzers.pure_tail import _goal_operators
    # The real cc_step4_1 i94 conclusion shape: a `has (…) (map (…) (filter (…) Mem.lc{2}))`.
    goal = (
        "----------------------------------------------------------------\n"
        "valid_topol a m /\\\n"
        " has (fun (pt : polynomial * tag) => pt.`1 <> topol a m)\n"
        "   (map (fun (c : ciphertext) => (topol c.`2 c.`3, c.`4))\n"
        "      (filter (fun (c : ciphertext) => c.`1 = nth witness ns i) Mem.lc{2}))\n"
        "[460|check]>"
    )
    ops = _goal_operators(goal)
    assert "filter" in ops, "filter must survive the operator cap (sub-cluster a)"
    # it is promoted ahead of the lower-value `has`/`map` that previously crowded it out
    assert ops.index("filter") < 8


def test_goal_operators_filter_survives_even_when_deeply_buried() -> None:
    """A regression on the exact failure mode: enough operators precede `filter` to push it
    past index 8, yet it must still be offered."""
    from workflow.proof_management.analyzers.pure_tail import _goal_operators
    goal = (
        "----\n"
        "nth aa bb cc /\\ valid_topol a m /\\ has zz (mapX yy "
        "(poly1305_eval x (topol a m) (oget kk) (qqq rrr) (filter ff Mem.lc{2})))\n"
        "[1|check]>"
    )
    ops = _goal_operators(goal)
    assert "filter" in ops


def test_goal_operators_filter_promotion_does_not_invent_absent_operator() -> None:
    """The `filter` promotion is pure REORDERING: it must never surface a priority list-op that is
    NOT literally in the conclusion. A goal without `filter` does not gain one."""
    from workflow.proof_management.analyzers.pure_tail import _goal_operators
    goal = (
        "----\n"
        "has zz (map yy Mem.lc{2}) /\\ nth aa bb cc\n[1|check]>"
    )
    ops = _goal_operators(goal)
    assert "filter" not in ops
    assert "map" in ops and "has" in ops  # the operators that ARE present still surface


def test_pure_tail_hypothesis_graph_requires_an_exact_mechanical_chain() -> None:
    from workflow.proof_management.analyzers.pure_tail import pure_tail_surface

    view = {
        "proof_status": {"current_layer": "ambient_logic", "goal_type": "ambient"},
        "current_goal": {"lines": [
            "Hcard: (card (cross s1 s2))%r <= q%r ^ 2 / 4%r",
            "Hmu: mu d (fun k => k \\in cross s1 s2) <= (card (cross s1 s2))%r * eps",
            "------------------------------------------------------------",
            "mu d (fun k => k \\in cross s1 s2) <= q%r ^ 2 * eps / 4%r",
        ]},
    }
    graph = pure_tail_surface(view)["local_hypothesis_graph"]
    assert not graph.get("order_chains")


def test_pure_tail_hypothesis_graph_reports_exact_order_chain() -> None:
    from workflow.proof_management.analyzers.pure_tail import pure_tail_surface

    view = {
        "proof_status": {"current_layer": "ambient_logic", "goal_type": "ambient"},
        "current_goal": {"lines": [
            "Hxy: x <= y",
            "Hyz: y <= z",
            "------------------------------------------------------------",
            "x <= z",
        ]},
    }
    graph = pure_tail_surface(view)["local_hypothesis_graph"]

    assert graph["order_chains"][0]["premises"] == ["Hxy", "Hyz"]
    assert "submit" not in str(graph)
    assert "No tactic" in graph["limitations"][0]


def test_pure_tail_reports_nth_map_route_with_visible_index_bounds() -> None:
    goal = r"""
Current goal
hlo: size prefix <= i
hhi: i < size prefix + size xs
------------------------------------------------------------
nth witness (map f xs) (i - size prefix) = rhs
"""
    surface = PureTailAnalyzer().analyze(state=_state(_view(goal)), view=_view(goal))

    normalization = surface["list_normalization_surface"]
    assert any(
        item["shape"] == "nth over map"
        and item["lemma_names"] == ["nth_map"]
        for item in normalization["lemma_families"]
    )
    term = normalization["nth_map_terms"][0]
    assert term["source_list"] == "xs"
    assert term["index"] == "i - size prefix"
    assert term["side_condition_status"] == "derivable_from_visible_linear_bounds"
    assert term["supporting_hypotheses"] == ["hlo", "hhi"]


def test_pure_tail_uses_nth_out_route_on_visible_negative_index_branch() -> None:
    goal = r"""
Current goal
h: ! 0 <= i < size l
------------------------------------------------------------
nth witness (map f l) i = f (nth witness l i)
"""
    surface = PureTailAnalyzer().analyze(state=_state(_view(goal)), view=_view(goal))

    normalization = surface["list_normalization_surface"]
    assert normalization["lemma_families"] == [{
        "shape": "nth outside map bounds",
        "lemma_names": ["nth_out", "size_map"],
        "side_condition": "! (0 <= index < size source_list)",
    }]
    term = normalization["nth_map_terms"][0]
    assert term["side_condition_status"] == "visible_false"
    assert term["supporting_hypotheses"] == ["h"]


def test_pure_tail_marks_nth_map_side_condition_visible_when_named_directly() -> None:
    goal = r"""
Current goal
h: 0 <= i < size l
------------------------------------------------------------
nth witness (map f l) i = f (nth witness l i)
"""
    surface = PureTailAnalyzer().analyze(state=_state(_view(goal)), view=_view(goal))

    term = surface["list_normalization_surface"]["nth_map_terms"][0]
    assert term["side_condition_status"] == "visible_true"
    assert term["supporting_hypotheses"] == ["h"]


def test_list_normalization_requires_real_size_map_nesting() -> None:
    goal = r"""
Current goal
------------------------------------------------------------
size xs = size ys /\ map f zs = map f zs
"""
    surface = PureTailAnalyzer().analyze(state=_state(_view(goal)), view=_view(goal))

    assert "list_normalization_surface" not in surface


def test_pure_tail_composes_prefix_successor_and_map_key_transport() -> None:
    goal = r"""
Current goal
------------------------------------------------------------
forall &1 &2,
  0 <= k{2} =>
  k{2} < size order{2} =>
  (forall x, left{2}.[x] = right{1}.[encode x]) =>
  forall result,
    map encode (take k{2} order{2}) ++
      [encode (nth witness order{2} k{2})] =
      map encode (take (k{2} + 1) order{2}) /\
    forall x,
      left{2}.[nth witness order{2} k{2} <- result].[x] =
      right{1}.[encode (nth witness order{2} k{2}) <- result].[encode x]
"""
    view = _view(goal)
    view["application_context"] = {
        "mechanical_goal_candidates": [{
            "lemma": "decode_encode",
            "match_kind": "loaded_left_inverse_support",
            "transform": "encode",
            "inverse": "decode",
            "support_role": "left_inverse_for_key_transport",
        }],
    }

    surface = PureTailAnalyzer().analyze(state=_state(view), view=view)

    prefix = surface["list_normalization_surface"]["prefix_successor_chains"][0]
    assert [item["lemma"] for item in prefix["lemma_chain"]] == [
        "take_nth", "map_rcons", "cats1",
    ]
    assert prefix["side_condition_status"] == "visible"
    transport = surface["map_update_transport_surface"]
    assert transport["key_transform"] == "encode"
    assert transport["lookup_normalization_lemma"] == "get_setE"
    assert transport["left_inverse_lemma"] == "decode_encode"


def test_pure_tail_preserves_projected_compiler_fact_extensions() -> None:
    goal = r"""
Current goal
------------------------------------------------------------
weight dword = 1%r
"""
    view = _view(goal)
    view["application_context"] = {
        "distribution_certificates": [{
            "lemma": "dword_ll",
            "certificate_kind": "distribution_losslessness",
            "distribution": "dword",
            "declared_conclusion": "is_lossless dword",
            "future_schema_field": {"producer_owned": True},
        }],
        "mechanical_goal_candidates": [{
            "lemma": "dword_ll",
            "match_kind": "exact_conclusion",
            "future_match_field": "preserved",
        }],
    }

    surface = PureTailAnalyzer().analyze(state=_state(view), view=view)

    assert surface["distribution_certificates"][0]["future_schema_field"] == {
        "producer_owned": True,
    }
    assert surface["mechanical_goal_candidates"][0]["future_match_field"] == "preserved"
