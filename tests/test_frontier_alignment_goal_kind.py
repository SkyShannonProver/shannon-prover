"""FIX#2 (deep audit Tier-B): the frontier-alignment read must not mislabel a
single-program (phoare/hoare) goal or a symmetric (identical-programs) equiv as a
relational "one-sided" frontier and push "a one-sided tactic before a symmetric tactic"."""
from __future__ import annotations

import core.easycrypt.session_prover_workspace_view as M
from core.easycrypt.session_workspace_view_manager import DisplayBudget


def _state(*lines: str) -> dict:
    return {"goal_window": {"lines": list(lines)}}


def _relational_plan() -> M.WorkspaceViewPlan:
    return M.WorkspaceViewPlan(
        goal_family="relational_program",
        goal_display_mode="window",
        phase_summary="relational",
        budget=DisplayBudget(
            goal_window_lines=80,
            goal_window_chars=8000,
            frontier_chars=4000,
            max_alternatives=3,
            max_evidence=6,
        ),
        panels=(),
        authority_order=(),
        inspect_order=(),
        focus=(),
        phase_resource_keys=(),
        frontier_resource_keys=(),
        frontier_checks=(),
    )


def test_goal_is_single_sided_detects_phoare() -> None:
    # mee_decrypt_correct shape: one program, `[=] 1%r`, no `~` separator.
    assert M._goal_is_single_sided(
        _state(
            "pre = key = (_ek, _mk) /\\ c = _c",
            "    MEE(PRPc.PseudoRP, MAC).dec",
            "    [=] 1%r",
            "post = res = mee_dec ...",
        )
    )


def test_goal_is_single_sided_false_for_two_program_equiv() -> None:
    assert not M._goal_is_single_sided(
        _state("pre = true", "    CPA(E, A).main ~ DDH(A).main", "post = ={res}")
    )


def test_goal_programs_are_symmetric_detects_identical_programs() -> None:
    # PIR_secure1 shape: identical programs both sides.
    assert M._goal_programs_are_symmetric(
        _state("pre = true", "    PIR.main ~ PIR.main", "post = PIR.s{1} = PIR.s{2}")
    )


def test_goal_programs_are_symmetric_false_for_different_programs() -> None:
    assert not M._goal_programs_are_symmetric(
        _state("pre = true", "    CPA(E, A).main ~ DDH(A).main", "post = ={res}")
    )


def test_branch_alignment_single_sided_not_one_sided() -> None:
    assert (
        M._branch_alignment_read("assignment", "", single_sided=True)
        == "single_program_frontier"
    )


def test_branch_alignment_symmetric_not_one_sided() -> None:
    assert (
        M._branch_alignment_read("call", "", symmetric=True) == "synchronized_frontier"
    )


def test_branch_alignment_default_empty_still_one_sided() -> None:
    # No flags: a genuinely one-sided relational frontier is unchanged.
    assert M._branch_alignment_read("call", "") == "one-sided_frontier"


def test_branch_alignment_both_heads_unchanged() -> None:
    assert M._branch_alignment_read("while", "while") == "both_sides_at_while"


def test_proof_read_single_sided_is_non_relational() -> None:
    read = M._first_instruction_proof_read("assignment", "", single_sided=True)
    assert "phoare" in read.lower()
    assert "no second side to align" in read.lower()
    assert "one-sided" not in read.lower()


def test_proof_read_symmetric_recommends_symmetric_tactic() -> None:
    read = M._first_instruction_proof_read("call", "", symmetric=True)
    assert "synchronized" in read.lower()
    assert "no one-sided" in read.lower()


def test_live_frontier_call_sites_drops_consumed_keeps_live() -> None:
    """FIX-B (deep audit Tier-2): a call site whose statement is absent from the rendered
    goal (consumed / pre-inline / hypothesis-only) is dropped; a call rendered verbatim at
    the active frontier is kept. Regression for eq_Game1_Game2 headlining consumed `a1`."""
    goal = (
        "equiv [ G1 ~ G2 : ={glob A} ==> ={res} ]\n"
        "b' <@ A(Log(LRO)).a2(c)\n~\nb' <@ A(Log(LRO)).a2(c)"
    )
    sites = [
        {"side": "left", "statement_path": "3", "statement": "(m0, m1) <@ A(Log(LRO)).a1(pk)"},
        {"side": "left", "statement_path": "8", "statement": "b' <@ A(Log(LRO)).a2(c)"},
    ]
    kept = M._live_frontier_call_sites(sites, goal)
    stmts = [s["statement"] for s in kept]
    assert "b' <@ A(Log(LRO)).a2(c)" in stmts
    assert not any("a1" in s for s in stmts)


def test_live_frontier_call_sites_keeps_multiline_functor_call() -> None:
    """EasyCrypt can print a functor call over many program-table lines.

    The live-call filter must not require the compact ProofIR statement to be a
    literal substring of that pretty-printed table; the result variable plus
    method tail is enough current-goal evidence that this call is live.
    """
    goal = """
&1 (left ) : {c2 : bytes, k : key, n : nonce, p2 : message}
&2 (right) : {c1 : bytes, n : nonce, p1 : message}

c2 <@
  ChaCha(
    CCRO(
      SplitD.RO_DOM(
        SplitC1.RO_Pair(
          SplitC2.RO_Pair(SplitC2.I1.RO, SplitC2.I2.RO),
          SplitC1.I2.RO),
        SplitD.ROF.RO))).enc(k, n, p2)
                                      (  )  c1 <@ EncRnd.cc(n, p1)
"""
    sites = [
        {
            "side": "left",
            "statement_path": "6",
            "procedure": "ChaCha.enc",
            "statement": (
                "c2 <@ ChaCha(CCRO(SplitD.RO_DOM(SplitC1.RO_Pair("
                "SplitC2.RO_Pair(SplitC2.I1.RO, SplitC2.I2.RO), "
                "SplitC1.I2.RO), SplitD.ROF.RO))).enc(k, n, p2);"
            ),
        },
        {
            "side": "right",
            "statement_path": "4",
            "procedure": "EncRnd.cc",
            "statement": "c1 <@ EncRnd.cc(n, p1);",
        },
        {
            "side": "left",
            "statement_path": "2",
            "procedure": "A.a1",
            "statement": "b <@ A.a1(pk);",
        },
    ]
    kept = M._live_frontier_call_sites(sites, goal)
    kept_statements = " ".join(str(site["statement"]) for site in kept)
    assert "ChaCha" in kept_statements
    assert "EncRnd.cc" in kept_statements
    assert "A.a1" not in kept_statements


def test_current_frontier_scope_separates_current_pair_from_lookahead() -> None:
    alignment = {"rows": [
        {
            "role": "setup / initialization",
            "left": "5 setup statement(s): p0 <- p; p1 <- p0; k <- Mem.k; ... (2 more)",
            "right": "3 setup statement(s): p0 <- p; nap <- p0; (n, a, p1) <- nap",
            "location": {"left_paths": ["1", "2", "3", "4", "5"], "right_paths": ["1", "2", "3"]},
        },
        {
            "role": "call frontier",
            "left": "b <@ CCRO(SplitD.RO_DOM(...)).cc(k0, n0, C.ofintd 0)",
            "right": "no matching right-side call at this frontier",
            "location": {"left_path": "11"},
        },
        {
            "role": "call frontier",
            "left": "no matching left-side call at this frontier",
            "right": "c1 <@ EncRnd.cc(n, p1)",
            "location": {"right_path": "4"},
        },
        {
            "role": "call frontier",
            "left": "c2 <@ ChaCha(CCRO(SplitD.RO_DOM(...))).enc(k, n, p2)",
            "right": "no matching right-side call at this frontier",
            "location": {"left_path": "6"},
        },
        {
            "role": "call frontier",
            "left": "no matching left-side call at this frontier",
            "right": "t <@ UFCMA(RO).set_bad1(map ...)",
            "location": {"right_path": "5"},
        },
    ]}
    scope = M._current_frontier_scope(alignment, call_sites=[
        {"side": "left", "statement_path": "6", "procedure": "ChaCha.enc",
         "statement": "c2 <@ ChaCha(CCRO(SplitD.RO_DOM(...))).enc(k, n, p2)"},
        {"side": "right", "statement_path": "4", "procedure": "EncRnd.cc",
         "statement": "c1 <@ EncRnd.cc(n, p1)"},
        {"side": "left", "statement_path": "11", "procedure": "CCRO.cc",
         "statement": "b <@ CCRO(SplitD.RO_DOM(...)).cc(k0, n0, C.ofintd 0)"},
        {"side": "right", "statement_path": "5", "procedure": "UFCMA.set_bad1",
         "statement": "t <@ UFCMA(RO).set_bad1(map ...)"},
    ])

    frontier = scope["frontier"]
    assert frontier["kind"] == "call_pair"
    assert frontier["left"]["path"] == "6"
    assert frontier["left"]["procedure"] == "ChaCha.enc"
    assert frontier["right"]["path"] == "4"
    assert frontier["right"]["procedure"] == "EncRnd.cc"
    lookahead = " ".join(item["statement"] for item in scope["lookahead_after_frontier"])
    assert "b <@ CCRO" in lookahead and "set_bad1" in lookahead
    assert "b <@ CCRO" not in frontier["left"]["statement"]


def test_current_frontier_scope_does_not_skip_earlier_right_sample() -> None:
    alignment = {"rows": [
        {
            "role": "setup / initialization",
            "left": "8 setup statement(s): k0 <- k; n0 <- n; a0 <- a; ... (5 more)",
            "right": "c0 <- (n, a, c1, t)",
            "location": {"left_paths": ["1", "2", "3", "4", "5", "6", "7", "8"],
                         "right_paths": ["2"]},
        },
        {
            "role": "sample inside frontier",
            "left": "no matching left-side sample at this frontier",
            "right": "t <$ dpoly_out",
            "location": {"right_path": "1"},
        },
        {
            "role": "call frontier",
            "left": "r0 <@ SplitC1.RO_Pair(SplitC2.RO_Pair(SplitC2.I1.RO, SplitC2.I2.RO), SplitC1.I2.RO).get(x)",
            "right": "no matching right-side call at this frontier",
            "location": {"left_path": "9"},
        },
    ]}

    scope = M._current_frontier_scope(alignment, call_sites=[
        {"side": "left", "statement_path": "9", "procedure": "SplitC1.RO_Pair.get",
         "statement": "r0 <@ SplitC1.RO_Pair(SplitC2.RO_Pair(SplitC2.I1.RO, SplitC2.I2.RO), SplitC1.I2.RO).get(x)"},
    ])

    assert "right" not in scope["setup"]
    frontier = scope["frontier"]
    assert frontier["kind"] == "call_vs_sample"
    assert frontier["left"]["path"] == "9"
    assert frontier["left"]["procedure"] == "SplitC1.RO_Pair.get"
    assert frontier["right"]["path"] == "1"
    assert frontier["right"]["head"] == "sample"


def test_current_frontier_scope_separates_program_head_from_tactic_active_tail() -> None:
    alignment = {"rows": [
        {
            "role": "sample inside frontier",
            "left": "r <$ sample",
            "right": "no matching right-side sample at this frontier",
            "location": {"left_path": "1"},
        },
        {
            "role": "loop frontier",
            "left": "while (test r) {",
            "right": "no matching right-side loop at this frontier",
            "location": {"left_path": "2"},
        },
        {
            "role": "sample inside frontier",
            "left": "r <$ sample",
            "right": "no matching right-side sample at this frontier",
            "location": {"left_path": "2.1"},
        },
    ]}

    scope = M._current_frontier_scope(alignment, call_sites=[])

    assert scope["frontier"]["left"]["path"] == "1"
    assert scope["frontier"]["left"]["head"] == "sample"
    assert scope["tactic_active_tail"]["left"]["path"] == "2"
    assert scope["tactic_active_tail"]["left"]["head"] == "while"
    assert scope["tactic_active_tail"]["left"]["authority"] == "top_level_program_ir"


def test_current_frontier_scope_lookahead_keeps_top_level_regions_not_nested_calls() -> None:
    alignment = {"rows": [
        {
            "role": "setup / initialization",
            "left": "k <- 0",
            "right": "2 setup statement(s): k <- 0; m <- nth witness l i",
            "location": {"left_paths": ["1"], "right_paths": ["1", "2"]},
        },
        {
            "role": "loop frontier",
            "left": "while (k < size l) {",
            "right": "no matching right-side loop at this frontier",
            "location": {"left_path": "2"},
        },
        {
            "role": "branch frontier",
            "left": "no matching left-side branch at this frontier",
            "right": "if (m \\notin M.log) {",
            "location": {"right_path": "3"},
        },
        {
            "role": "call frontier",
            "left": "y <@ H.f(m)",
            "right": "y <@ H.f(m)",
            "location": {"left_path": "2.2.1", "right_path": "3.1"},
        },
        {
            "role": "call frontier",
            "left": "no matching left-side call at this frontier",
            "right": "y <@ H.f(m)",
            "location": {"right_path": "4.2.1.1"},
        },
        {
            "role": "loop frontier",
            "left": "no matching left-side loop at this frontier",
            "right": "while (k < size l) {",
            "location": {"right_path": "4"},
        },
    ]}

    scope = M._current_frontier_scope(alignment, call_sites=[
        {"side": "left", "statement_path": "2.2.1", "procedure": "H.f",
         "statement": "y <@ H.f(m)"},
        {"side": "right", "statement_path": "3.1", "procedure": "H.f",
         "statement": "y <@ H.f(m)"},
        {"side": "right", "statement_path": "4.2.1.1", "procedure": "H.f",
         "statement": "y <@ H.f(m)"},
    ])

    assert scope["frontier"]["left"]["head"] == "while"
    assert scope["frontier"]["right"]["head"] == "if"
    lookahead = scope["lookahead_after_frontier"]
    assert [item["path"] for item in lookahead] == ["4"]
    assert lookahead[0]["head"] == "while"
    assert "H.f" not in " ".join(item["statement"] for item in lookahead)


def test_current_frontier_scope_lookahead_is_not_global_cap_biased() -> None:
    alignment = {"rows": [
        {
            "role": "setup / initialization",
            "left": "2 setup statement(s): Log.qs <- []; LRO.m <- empty",
            "right": "no right-side setup before this frontier",
            "location": {"left_paths": ["1", "2"]},
        },
        {
            "role": "sample inside frontier",
            "left": "(pk, sk) <$ dkeys",
            "right": "(pk, sk) <$ dkeys",
            "location": {"left_path": "3", "right_path": "1"},
        },
        {
            "role": "sample inside frontier",
            "left": "no matching left-side sample at this frontier",
            "right": "OWr.x <$ drand",
            "location": {"right_path": "2"},
        },
        {
            "role": "call frontier",
            "left": "(m0, m1) <@ A(Log(LRO)).a1(pk)",
            "right": "no matching right-side call at this frontier",
            "location": {"left_path": "4"},
        },
        {
            "role": "sample inside frontier",
            "left": "b <$ {0,1}",
            "right": "no matching right-side sample at this frontier",
            "location": {"left_path": "5"},
        },
        {
            "role": "sample inside frontier",
            "left": "Game2.r <$ drand",
            "right": "no matching right-side sample at this frontier",
            "location": {"left_path": "6"},
        },
        {
            "role": "call frontier",
            "left": "no matching left-side call at this frontier",
            "right": "(m0, m1) <@ A(Log(LRO)).a1(pk0)",
            "location": {"right_path": "7"},
        },
        {
            "role": "call frontier",
            "left": "b' <@ A(Log(LRO)).a2(c)",
            "right": "b <@ A(Log(LRO)).a2(y, h)",
            "location": {"left_path": "9", "right_path": "9"},
        },
    ]}
    scope = M._current_frontier_scope(alignment, call_sites=[
        {"side": "left", "statement_path": "4", "procedure": "A.a1",
         "statement": "(m0, m1) <@ A(Log(LRO)).a1(pk)"},
        {"side": "right", "statement_path": "7", "procedure": "A.a1",
         "statement": "(m0, m1) <@ A(Log(LRO)).a1(pk0)"},
        {"side": "left", "statement_path": "9", "procedure": "A.a2",
         "statement": "b' <@ A(Log(LRO)).a2(c)"},
        {"side": "right", "statement_path": "9", "procedure": "A.a2",
         "statement": "b <@ A(Log(LRO)).a2(y, h)"},
    ])

    lookahead = scope["lookahead_after_frontier"]
    right_statements = " ".join(item["statement"] for item in lookahead if item["side"] == "right")
    assert "A(Log(LRO)).a1" in right_statements
    assert "A(Log(LRO)).a2" in right_statements


def test_frontier_panel_scope_uses_untruncated_alignment_rows(monkeypatch) -> None:
    rows = [
        {
            "role": "sample inside frontier",
            "left": "x0 <$ dt",
            "right": "x <$ dt",
            "location": {"left_path": "1", "right_path": "1"},
        },
        {
            "role": "call frontier",
            "left": "no matching left-side call at this frontier",
            "right": "(m0, m1) <@ U.choose(h)",
            "location": {"right_path": "3"},
        },
        {
            "role": "call frontier",
            "left": "(m0, m1) <@ U.choose(x)",
            "right": "no matching right-side call at this frontier",
            "location": {"left_path": "4"},
        },
        {
            "role": "sample inside frontier",
            "left": "no matching left-side sample at this frontier",
            "right": "b <$ {0,1}",
            "location": {"right_path": "4"},
        },
        {
            "role": "sample inside frontier",
            "left": "b <$ {0,1}",
            "right": "no matching right-side sample at this frontier",
            "location": {"left_path": "5"},
        },
        {
            "role": "sample inside frontier",
            "left": "no matching left-side sample at this frontier",
            "right": "d <$ dt",
            "location": {"right_path": "5"},
        },
        {
            "role": "assignment frontier",
            "left": "no matching left-side statement at this frontier",
            "right": "c <- g ^ d",
            "location": {"right_path": "6"},
        },
        {
            "role": "call frontier",
            "left": "no matching left-side call at this frontier",
            "right": "b' <@ U.guess(c)",
            "location": {"right_path": "7"},
        },
        {
            "role": "sample inside frontier",
            "left": "d0 <$ dt",
            "right": "no matching right-side sample at this frontier",
            "location": {"left_path": "8"},
        },
        {
            "role": "call frontier",
            "left": "b' <@ U.guess(c)",
            "right": "no matching right-side call at this frontier",
            "location": {"left_path": "11"},
        },
    ]
    monkeypatch.setattr(M, "_structured_regions", lambda proof_ir, *, plan: [])
    monkeypatch.setattr(
        M,
        "_frontier_call_sites",
        lambda proof_ir, *, plan, goal_text: [],
    )
    monkeypatch.setattr(
        M,
        "_frontier_alignment_rows",
        lambda regions, *, call_sites, plan, synchronized=False: rows,
    )

    panel = M._frontier_panel(
        phase={"resources": {}},
        proof_ir={},
        state=_state(
            "pre = (glob U){1} = (glob U){2}",
            "    HidingExperiment(Pedersen, U).main ~ FakeCommit(U).main",
            "post = res{1} = res{2}",
        ),
        plan=_relational_plan(),
    )

    displayed = " ".join(
        f"{row.get('left', '')} {row.get('right', '')}"
        for row in panel["frontier_alignment"]["rows"]
    )
    lookahead = " ".join(
        item["statement"]
        for item in panel["current_frontier_scope"]["lookahead_after_frontier"]
    )
    assert "d0 <$ dt" not in displayed
    assert "d0 <$ dt" in lookahead


def test_region_paths_are_not_truncated_for_setup_range_contract() -> None:
    regions = [
        {"statement_path": str(i), "statement": f"x{i} <- x{i - 1}"}
        for i in range(1, 10)
    ]

    assert M._region_paths(regions) == [str(i) for i in range(1, 10)]


def test_live_frontier_call_sites_no_goal_keeps_all() -> None:
    sites = [{"statement": "x <@ P.f()"}]
    assert M._live_frontier_call_sites(sites, "") == sites


def test_call_method_tail_strips_module_wrappers() -> None:
    # FIX-B (live audit Tier-1): the two module-instance wrappers of one synchronized call
    # must reduce to the SAME method tail so the call pairs instead of producing two
    # "no matching left/right-side call" placeholder rows.
    assert M._call_method_tail("Poly(OpCCinit.OCC(I_stateless)).mac") == "mac"
    assert M._call_method_tail("D(A, IndBlock).O.Poly.mac") == "mac"
    assert M._call_method_tail("A.choose") == "choose"
    assert M._call_method_tail("CCA_CPA_Adv(A, RealOrcls(StLSke(St))).main") == "main"


def test_call_sites_pair_synchronized_call_by_method_tail() -> None:
    # Two synchronized call sites (same method, different module wrappers) pair into ONE row.
    sites = [
        {"side": "left", "procedure": "Poly(OpCCinit.OCC(I_stateless)).mac",
         "statement": "t' <@ Poly(OpCCinit.OCC(I_stateless)).mac(k, n, a, c0)"},
        {"side": "right", "procedure": "D(A, IndBlock).O.Poly.mac",
         "statement": "t' <@ D(A, IndBlock).O.Poly.mac(n, a, c)"},
    ]
    rows = M._alignment_rows_from_call_sites(sites)
    assert len(rows) == 1
    assert M._alignment_row_is_paired(rows[0])
