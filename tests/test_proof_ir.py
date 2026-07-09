"""Tests for compiler-style EasyCrypt ProofIR analysis."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from core.easycrypt.analysis.ec_action_contracts import (  # noqa: E402
    normalize_action_candidate,
    validate_action_candidate,
)
from core.easycrypt.analysis.ec_proof_ir import (  # noqa: E402
    _candidate_menu,
    _pr_typed_bridge_chain_menu_items,
    _program_edit_script_menu_items,
    build_proof_ir,
    proof_ir_notes,
)


def test_proof_ir_candidate_menu_satisfies_action_contract() -> None:
    ir = build_proof_ir(current_goal={
        "goal_type": "pRHL",
        "parsed_goal": {
            "goal_type": "pRHL",
            "left_statements": [{
                "pos": 1,
                "type": "CALL",
                "text": "x <@ L.f();",
                "procedure": "L.f",
            }],
            "right_statements": [{
                "pos": 1,
                "type": "CALL",
                "text": "y <@ R.f();",
                "procedure": "R.f",
            }],
            "call_equiv_candidates": {"L.f": ["Lf_Rf_eq"]},
        },
    })

    errors = [
        f"candidate[{idx}]: {error}"
        for idx, candidate in enumerate(ir["candidate_menu"])
        for error in validate_action_candidate(candidate)
    ]
    assert errors == []
    assert all("readiness" in item for item in ir["candidate_menu"])
    assert all("effect" in item for item in ir["candidate_menu"])
    assert all("provenance" in item for item in ir["candidate_menu"])


def test_action_contract_blocks_fallback_resource_as_probeable() -> None:
    candidate = normalize_action_candidate({
        "id": "bad_source_scan_probe",
        "tactic": "rewrite maybe_later.",
        "tactic_family": "rewrite",
        "action_type": "probe_tactic",
        "cost": "cheap",
        "why": "source fallback only",
        "preconditions": [],
        "cost_factors": {
            "source": "source_scan_out_of_context",
            "authority": "source_scan_not_current_scope",
        },
    })

    assert (
        "fallback or unresolved resource cannot be probeable/runnable before inspection"
        in validate_action_candidate(candidate)
    )


def test_call_site_layer_tracks_live_callable_handles() -> None:
    current_goal = {
        "goal_type": "pRHL",
        "parsed_goal": {
            "goal_type": "pRHL",
            "left_statements": [{
                "pos": 1,
                "type": "CALL",
                "text": "c0 <@ GenChaChaPoly.enc(k, n, p);",
                "procedure": "GenChaChaPoly.enc",
            }],
            "right_statements": [{
                "pos": 1,
                "type": "CALL",
                "text": "c <@ IndBlock.enc(k, n, p);",
                "procedure": "IndBlock.enc",
            }],
            "call_equiv_candidates": {
                "GenChaChaPoly.enc": ["poly_mac1"],
                "IndBlock.enc": ["chacha_enc1"],
            },
        },
    }

    ir = build_proof_ir(current_goal=current_goal)

    assert ir["current_layer"] == "call_site"
    assert ir["liveness"]["live_call_site_count"] == 2
    assert ir["liveness"]["live_callable_lemma_count"] == 2
    assert ir["liveness"]["callable_now_lemma_count"] == 0
    assert {
        handle["lemma"]: handle["call_candidate_kind"]
        for handle in ir["resources"]["handles"]["callable_lemmas"]
    } == {
        "poly_mac1": "source_lookup_landmark",
        "chacha_enc1": "source_lookup_landmark",
    }
    call_candidates = [
        item for item in ir["candidate_menu"]
        if item["tactic_family"] == "call_named_equiv"
    ]
    assert call_candidates == []
    # `inline_all` (`inline *.`) is a bare hardcoded tactic — now dropped as
    # guidance, so it no longer appears in the menu. The live-handle-loss fact is
    # carried by the diagnostic below instead.
    assert [x for x in ir["candidate_menu"] if x["id"] == "inline_all"] == []
    assert ir["diagnostics"][0]["code"] == "proof_ir.live_call_handles"
    assert "direct_current_call" in ir["diagnostics"][0]["repairs"][0]


def test_proof_ir_prefers_ec_native_program_artifact() -> None:
    with tempfile.TemporaryDirectory() as td:
        session = Path(td)
        tool_views = session / "tool_views"
        tool_views.mkdir()
        (tool_views / "native_program.json").write_text(
            json.dumps({
                "tool": "ec-program-json",
                "program": {
                    "left_statements": [{
                        "pos": 1,
                        "pos_path": "1",
                        "type": "CALL",
                        "text": "x <@ Native.f();",
                        "procedure": "Native.f",
                    }],
                    "right_statements": [],
                    "call_equiv_candidates": {
                        "Native.f": ["Native_f_equiv"],
                    },
                },
            }),
            encoding="utf-8",
        )

        ir = build_proof_ir(
            session_dir=session,
            current_goal={
                "goal_type": "pRHL",
                "parsed_goal": {
                    "goal_type": "pRHL",
                    "left_statements": [],
                    "right_statements": [],
                },
            },
        )

    program_ir = ir["resources"]["program_ir"]
    assert program_ir["fact_source"] == "ec_native_program_ast"
    assert program_ir["authority"] == "ec_native_ground_truth"
    assert program_ir["ec_ground_truth"] is True
    assert program_ir["call_sites"][0]["procedure"] == "Native.f"
    assert "call Native_f_equiv." not in {
        item["tactic"] for item in ir["candidate_menu"]
    }
    assert "-where Native_f_equiv" in {
        item["tactic"] for item in ir["candidate_menu"]
    }


def test_proof_ir_recommendation_is_probe_only() -> None:
    ir = build_proof_ir(current_goal={
        "goal_type": "pRHL",
        "parsed_goal": {
            "goal_type": "pRHL",
            "left_statements": [{
                "pos": 1,
                "type": "CALL",
                "text": "x <@ M.f();",
                "procedure": "M.f",
            }],
            "right_statements": [],
            "call_equiv_candidates": {"M.f": ["M_f_equiv"]},
        },
    })

    menu = ir["candidate_menu"]
    by_tactic = {item["tactic"]: item for item in menu}
    assert "call M_f_equiv." not in by_tactic
    assert ir["resources"]["handles"]["callable_lemmas"][0][
        "call_candidate_kind"
    ] == "source_lookup_landmark"
    maps = [
        item for item in menu
        if item["tactic"].startswith("Inspect proof obligation stack")
    ]
    assert maps and maps[0]["action_type"] == "strategy_hint"


def test_call_handle_requires_frontier_before_probe() -> None:
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

    call_candidates = [
        item for item in ir["candidate_menu"]
        if item["id"] == "call_M_f_equiv"
    ]
    assert ir["liveness"]["non_frontier_callable_lemma_count"] == 1
    assert ir["liveness"]["callable_now_lemma_count"] == 0
    assert call_candidates == []
    assert ir["resources"]["handles"]["callable_lemmas"][0][
        "call_candidate_kind"
    ] == "source_lookup_landmark"
    # `expose_frontier_call` carried a bare `wp.`/placeholder frontier-exposure
    # move (guidance) and is now dropped; the structured route fact below stays.
    menu_ids = [item["id"] for item in ir["candidate_menu"]]
    assert "expose_frontier_call" not in menu_ids
    assert ir["diagnostics"][0]["code"] == "proof_ir.call_handles_not_frontier"
    assert "last-call frontier" in ir["diagnostics"][0]["repairs"][0]
    route = ir["resources"]["handles"]["call_site_route"]
    assert route["state"] == "tail_blocked_named_call"
    assert route.get("callable_now", []) == []
    assert route["named_handles"][0]["frontier_live"] is False
    assert route["named_handles"][0]["requires_cut_to_frontier"] is True
    assert any(
        blocker["kind"] == "named_call_not_at_frontier"
        for blocker in route["frontier_blockers"]
    )
    assert route["exposure"]["action"]["kind"] == "expose_last_call_frontier"
    assert "seq 1 0" in route["exposure"]["action"]["tactic_shape"]


def test_call_site_route_exposes_tail_blocked_call_pair() -> None:
    ir = build_proof_ir(current_goal={
        "goal_type": "pRHL",
        "parsed_goal": {
            "goal_type": "pRHL",
            "pre": "true",
            "post": "={res}",
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
            "right_statements": [{
                "pos": 1,
                "pos_path": "1",
                "type": "CALL",
                "text": "y <@ N.g();",
                "procedure": "N.g",
            }, {
                "pos": 2,
                "pos_path": "2",
                "type": "ASSIGN",
                "text": "w <- y;",
            }],
            "call_equiv_candidates": {
                "M.f": ["M_N_equiv"],
                "N.g": ["M_N_equiv"],
            },
        },
    })

    route = ir["resources"]["handles"]["call_site_route"]
    assert route["state"] == "tail_blocked_named_call"
    assert route["exposure"]["action"]["kind"] == "expose_call_pair_frontier"
    assert route["exposure"]["action"]["tactic_shape"].startswith("seq 1 1")
    assert {site["side"] for site in route["live_call_sites"]} == {
        "left",
        "right",
    }
    assert {
        blocker["side"]
        for blocker in route["frontier_blockers"]
        if blocker["kind"] == "ASSIGN"
    } == {"left", "right"}


def test_call_site_frontend_surfaces_swap_for_shifted_call_pair() -> None:
    ir = build_proof_ir(current_goal={
        "goal_type": "pRHL",
        "parsed_goal": {
            "goal_type": "pRHL",
            "left_statements": [{
                "pos": 1,
                "pos_path": "1",
                "type": "ASSIGN",
                "text": "z <- x;",
            }, {
                "pos": 2,
                "pos_path": "2",
                "type": "CALL",
                "text": "x <@ M.f();",
                "procedure": "M.f",
            }],
            "right_statements": [{
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
            "call_equiv_candidates": {"M.f": ["M_f_equiv"]},
        },
    })

    # `program_swap_alignment` surfaced an un-filled `swap <range> <offset>`
    # placeholder template — move GUIDANCE — so it is no longer a menu candidate.
    assert [
        item for item in ir["candidate_menu"]
        if item["id"] == "program_swap_alignment"
    ] == []


def test_external_realignment_swap_reaches_candidate_menu_as_offset_frame() -> None:
    """A daemon-accepted AUTO-SWAP-ALIGN swap is evidence for a source-position frame,
    not a unique route answer. The concrete accepted tactic stays in metadata; the
    agent-facing move blanks the route-dependent offset so it can flow to the
    deep-surgery `swap_offsets` panel without pushing a misleading location."""
    from core.easycrypt.analysis.ec_action_contracts import classify_info_kind  # type: ignore  # noqa: E402

    ir = build_proof_ir(
        current_goal={
            "goal_type": "pRHL",
            "parsed_goal": {
                "goal_type": "pRHL",
                "left_statements": [
                    {"pos": 1, "pos_path": "1", "type": "SAMPLE", "text": "r <$ d;"},
                    {"pos": 2, "pos_path": "2", "type": "CALL",
                     "text": "x <@ A.guess();", "procedure": "A.guess"},
                ],
                "right_statements": [
                    {"pos": 1, "pos_path": "1", "type": "CALL",
                     "text": "x <@ A.guess();", "procedure": "A.guess"},
                    {"pos": 2, "pos_path": "2", "type": "SAMPLE", "text": "r <$ d;"},
                ],
            },
        },
        external_recommendations=[{
            "id": "probe.auto_swap_align.0",
            "kind": "tactic_candidate",
            "producer": "AUTO-SWAP-ALIGN",
            "action": "swap{1} 11 -9.",
            "verified": True,
            "confidence": "verified",
            "metadata": {"epistemic_status": "daemon_probe_accepted"},
        }],
    )
    swap_items = [
        item for item in ir["candidate_menu"]
        if item.get("tactic_family") == "realignment_swap"
    ]
    assert swap_items, "daemon-accepted swap must reach candidate_menu (M1 regression)"
    assert swap_items[0]["tactic"] == "swap{1} 11 <offset>."
    assert swap_items[0]["action_type"] == "strategy_hint"
    assert not swap_items[0].get("verified")
    factors = swap_items[0]["cost_factors"]
    assert factors["ec_accepted_example"] == "swap{1} 11 -9."
    assert factors["offset_policy"] == "route_dependent"
    # The source-position frame is still a mechanical FACT, so the facts-only filter
    # keeps it for the agent without making the offset runnable.
    assert classify_info_kind(swap_items[0]) == "fact"


def test_call_site_frontend_surfaces_sp_for_symbolic_prefix() -> None:
    ir = build_proof_ir(current_goal={
        "goal_type": "pRHL",
        "parsed_goal": {
            "goal_type": "pRHL",
            "suggested_tactics": ["wp.", "auto => />."],
            "left_statements": [{
                "pos": 1,
                "pos_path": "1",
                "type": "ASSIGN",
                "text": "k <- Mem.k;",
                "vars_written": ["k"],
            }, {
                "pos": 2,
                "pos_path": "2",
                "type": "ASSIGN",
                "text": "(n, a, c, t) <- nact;",
                "vars_written": ["n", "a", "c", "t"],
            }, {
                "pos": 3,
                "pos_path": "3",
                "type": "CALL",
                "text": "t' <@ Poly.mac(k, n, a, c);",
                "procedure": "Poly.mac",
                "vars_written": ["t'"],
            }, {
                "pos": 4,
                "pos_path": "4",
                "type": "IF",
                "text": "if (t = t') {",
            }],
            "right_statements": [{
                "pos": 1,
                "pos_path": "1",
                "type": "ASSIGN",
                "text": "(n, a, c, t) <- nact;",
                "vars_written": ["n", "a", "c", "t"],
            }, {
                "pos": 2,
                "pos_path": "2",
                "type": "CALL",
                "text": "t' <@ D.O.Poly.mac(n, a, c);",
                "procedure": "D.O.Poly.mac",
                "vars_written": ["t'"],
            }, {
                "pos": 3,
                "pos_path": "3",
                "type": "IF",
                "text": "if (t = t') {",
            }],
        },
    })

    menu = ir["candidate_menu"]
    assert ir["current_layer"] == "call_site"
    # `program_sp_prefix` emitted a bare `sp.` (move GUIDANCE), so it is now
    # dropped; the symbolic-prefix STRUCTURE is surfaced as a fact elsewhere.
    assert [item for item in menu if item["id"] == "program_sp_prefix"] == []


def test_program_edit_script_seq_cut_is_agent_facing_candidate() -> None:
    ir = build_proof_ir(current_goal={
        "goal_type": "pRHL",
        "parsed_goal": {
            "goal_type": "pRHL",
            "pre": "pre = k{1} = Mem.k{1} /\\ Mem.k{1} = IndBlock.k{2}",
            "post": (
                "post = (n{1}, a{1}, c0{1}, t{1}) = "
                "(n{2}, a{2}, c{2}, t{2}) /\\ c0{1} = c{2}"
            ),
            "left_statements": [{
                "pos": 1,
                "pos_path": "1",
                "type": "ASSIGN",
                "text": "result <- true;",
                "vars_written": ["result"],
            }, {
                "pos": 2,
                "pos_path": "2",
                "type": "ASSIGN",
                "text": "n <- n;",
                "vars_written": ["n"],
            }, {
                "pos": 3,
                "pos_path": "3",
                "type": "ASSIGN",
                "text": "a <- a;",
                "vars_written": ["a"],
            }, {
                "pos": 4,
                "pos_path": "4",
                "type": "CALL",
                "text": "c0 <@ ChaCha.enc(n, p);",
                "procedure": "ChaCha.enc",
                "vars_written": ["c0"],
            }, {
                "pos": 5,
                "pos_path": "5",
                "type": "CALL",
                "text": "t' <@ Poly.mac(n, a, c0);",
                "procedure": "Poly.mac",
                "vars_written": ["t'"],
            }, {
                "pos": 6,
                "pos_path": "6",
                "type": "IF",
                "text": "if (t = t') { result <- true; }",
                "vars_written": ["result"],
            }],
            "right_statements": [{
                "pos": 1,
                "pos_path": "1",
                "type": "ASSIGN",
                "text": "result <- true;",
                "vars_written": ["result"],
            }, {
                "pos": 2,
                "pos_path": "2",
                "type": "CALL",
                "text": "c <@ D.O.ChaCha.enc(n, p);",
                "procedure": "D.O.ChaCha.enc",
                "vars_written": ["c"],
            }, {
                "pos": 3,
                "pos_path": "3",
                "type": "CALL",
                "text": "t <@ D.O.Poly.mac(n, a, c);",
                "procedure": "D.O.Poly.mac",
                "vars_written": ["t"],
            }, {
                "pos": 4,
                "pos_path": "4",
                "type": "IF",
                "text": "if (t = t') { result <- true; }",
                "vars_written": ["result"],
            }],
        },
    })

    # `program_seq_cut` emitted an un-filled `seq 5 3 : <invariant preserving…>`
    # template carrying `requires_instantiation: True` — strategy GUIDANCE, not a
    # state-derived fact — so it is now dropped from the menu.
    menu_ids = [item["id"] for item in ir["candidate_menu"]]
    assert "program_seq_cut" not in menu_ids


def test_full_prefix_seq_is_labeled_as_cleanup_skeleton() -> None:
    ir = build_proof_ir(current_goal={
        "goal_type": "pRHL",
        "parsed_goal": {
            "goal_type": "pRHL",
            "pre": "true",
            "post": "x{1} = x{2}",
            "left_statements": [{
                "pos": 1,
                "pos_path": "1",
                "type": "ASSIGN",
                "text": "x <- x;",
                "vars_written": ["x"],
            }, {
                "pos": 2,
                "pos_path": "2",
                "type": "ASSIGN",
                "text": "y <- y;",
                "vars_written": ["y"],
            }],
            "right_statements": [{
                "pos": 1,
                "pos_path": "1",
                "type": "ASSIGN",
                "text": "x <- x;",
                "vars_written": ["x"],
            }],
        },
    })

    # `program_full_prefix_split` emitted an un-filled
    # `seq 2 1 : <full-prefix invariant…>` template (requires_instantiation) —
    # cleanup GUIDANCE — so it is now dropped from the menu.
    assert [
        item for item in ir["candidate_menu"]
        if item["id"] == "program_full_prefix_split"
    ] == []


def test_program_edit_script_wrapper_open_uses_specific_procedure_hint() -> None:
    ir = build_proof_ir(current_goal={
        "goal_type": "pRHL",
        "parsed_goal": {
            "goal_type": "pRHL",
            "pre": "(glob A){1} = (glob A){m}",
            "post": "r{1} = b{2}",
            "left_statements": [{
                "pos": 1,
                "pos_path": "1",
                "type": "CALL",
                "text": "r <@ G8(BNR_Adv(A), RO).distinguish(x);",
                "procedure": "G8.distinguish",
                "vars_written": ["r"],
            }],
            "right_statements": [{
                "pos": 1,
                "pos_path": "1",
                "type": "CALL",
                "text": "b <@ CCA_CPA_Adv(BNR_Adv(A), EncRnd).main();",
                "procedure": "CCA_CPA_Adv.main",
                "vars_written": ["b"],
            }],
        },
    })

    # `program_wrapper_open` is a goal-FILLED `inline G8.distinguish.` (a fact),
    # so it is kept. Its old ordering peer `targeted_inline` was a bare/placeholder
    # guidance item that is now dropped, so the ordering assertion is removed.
    menu_ids = [item["id"] for item in ir["candidate_menu"]]
    assert "program_wrapper_open" in menu_ids
    wrapper = [
        item for item in ir["candidate_menu"]
        if item["id"] == "program_wrapper_open"
    ][0]
    assert wrapper["tactic"] == "inline G8.distinguish."
    assert wrapper["tactic_family"] == "targeted_inline"


def test_program_edit_script_ec_type_annotation_is_not_placeholder() -> None:
    items = _program_edit_script_menu_items(
        {},
        {
            "program_edit_script_action": {
                "kind": "expose_asymmetric_prefix",
                "tactic_hint": "seq 1 0 : witness<:ciphertext>.",
                "reason": "Expose the live prefix while keeping the EC type annotation intact.",
            },
        },
    )

    assert len(items) == 1
    item = items[0]
    assert item["cost_factors"]["has_placeholder"] is False
    assert item["cost"] == "cheap"
    assert all("placeholder" not in precondition for precondition in item["preconditions"])


def test_have_pr_bridge_obligation_surfaces_byequiv() -> None:
    ir = build_proof_ir(
        proof_state={
            "latest_transition": {
                "tactic": (
                    "have -> :\n"
                    "  Pr[G0.main() @ &m : res] = Pr[G1.main() @ &m : res]."
                ),
                "goals_before": 1,
                "goals_after": 2,
            },
        },
        current_goal={
            "goal_type": "probability",
            "parsed_goal": {
                "goal_type": "probability",
                "prob_form": "eq",
                "lhs_game": "G0",
                "rhs_game": "G1",
                "strategy_hint": "byequiv",
                "suggested_tactics": ["byequiv => //.", "rewrite ..."],
            },
        },
    )

    # `pr_direct_byequiv_bridge` surfaced a bare hardcoded `byequiv => //.`
    # (move GUIDANCE), so it is no longer pushed into the menu.
    assert [
        item for item in ir["candidate_menu"]
        if item["id"] == "pr_direct_byequiv_bridge"
    ] == []
    assert "byequiv => //." not in {
        item["tactic"] for item in ir["candidate_menu"]
    }


def test_ambient_lossless_goal_uses_loaded_ll_closer() -> None:
    with tempfile.TemporaryDirectory() as td:
        session = Path(td)
        (session / "context.ec").write_text(
            "axiom dblock_ll : is_lossless dblock.\n",
            encoding="utf-8",
        )
        ir = build_proof_ir(
            session_dir=session,
            current_goal={
                "goal_type": "ambient",
                "active_goal_preview": (
                    "Current goal\n\n"
                    "------------------------------------------------------------------------\n"
                    "is_lossless dblock\n"
                ),
                "parsed_goal": {
                    "goal_type": "ambient",
                    "ambient_shape": "logical",
                },
            },
        )

    exact = [
        item for item in ir["candidate_menu"]
        if item["id"] == "ambient_exact_dblock_ll"
    ][0]
    assert exact["tactic"] == "exact: dblock_ll."


def test_procedure_body_frontend_surfaces_branch_and_residual_passes() -> None:
    ir = build_proof_ir(current_goal={
        "goal_type": "pRHL",
        "parsed_goal": {
            "goal_type": "pRHL",
            "left_statements": [{
                "pos": 1,
                "pos_path": "1",
                "type": "ASSIGN",
                "text": "x <- a;",
            }, {
                "pos": 2,
                "pos_path": "2",
                "type": "IF",
                "text": "if (x \\in m) {",
            }],
            "right_statements": [{
                "pos": 1,
                "pos_path": "1",
                "type": "ASSIGN",
                "text": "x <- a;",
            }, {
                "pos": 4,
                "pos_path": "4",
                "type": "IF",
                "text": "if (x \\in m) {",
            }],
            "suggested_tactics": ["wp.", "auto => />."],
        },
    })

    actions = [item["tactic"] for item in ir["candidate_menu"]]
    # Goal-FILLED branch tactics (rcondt{N}/rcondf{N}/case:(real cond)) are facts
    # and stay. Bare shapes (`wp.`, `if => //=.`, `sp; if => //=.`, `auto => />.`)
    # were move GUIDANCE and are now dropped.
    assert "wp." not in actions
    assert any(action.startswith("rcondt{") for action in actions)
    assert any(action.startswith("rcondf{") for action in actions)
    assert any(action.startswith("case: (") for action in actions)
    assert "if => //=." not in actions
    assert "sp; if => //=." not in actions
    assert "auto => />." not in actions
    assert ir["phase"]["resource_summary"]["live_call_sites"] == 0


def test_procedure_body_frontend_surfaces_loop_sample_swap_passes() -> None:
    ir = build_proof_ir(current_goal={
        "goal_type": "pRHL",
        "parsed_goal": {
            "goal_type": "pRHL",
            "post": "post = ={x, i} /\\ 0 <= i{1}",
            "left_statements": [{
                "pos": 1,
                "pos_path": "1",
                "type": "ASSIGN",
                "text": "x <- a;",
                "vars_written": ["x"],
            }, {
                "pos": 2,
                "pos_path": "2",
                "type": "WHILE",
                "text": "while (i < n) {",
                "vars_read": ["i", "n"],
            }, {
                "pos": 3,
                "pos_path": "3",
                "type": "SAMPLE",
                "text": "r <$ d;",
                "vars_written": ["r"],
            }],
            "right_statements": [{
                "pos": 1,
                "pos_path": "1",
                "type": "ASSIGN",
                "text": "x <- a;",
                "vars_written": ["x"],
            }, {
                "pos": 2,
                "pos_path": "2",
                "type": "SAMPLE",
                "text": "r <$ d;",
                "vars_written": ["r"],
            }, {
                "pos": 3,
                "pos_path": "3",
                "type": "WHILE",
                "text": "while (i < n) {",
                "vars_read": ["i", "n"],
            }],
            "suggested_tactics": ["wp.", "auto => />."],
        },
    })

    actions = [item["tactic"] for item in ir["candidate_menu"]]
    frontend = ir["resources"]["handles"]["procedure_body_frontend"]
    # Frontend handle facts (the structural readout) stay; the bare/placeholder
    # tactic suggestions are now dropped as guidance.
    assert frontend["has_loop"] is True
    assert frontend["has_sample"] is True
    assert frontend["has_swap_candidate"] is True
    # The guard-bound `while (0 <= i < n).` (the loop guard restated AS the
    # invariant) is DROPPED — it overclaims; the guard/bound is part of, not the
    # whole, invariant. The dataflow-derived relational invariant
    # (`while (={…} /\ bad{1} = bad{2}).`) is a genuine state-derived fact and stays.
    assert any(action.startswith("while (") for action in actions)
    assert "while (0 <= i < n)." not in actions
    # Bare `sp.`/`skip.` and the un-filled `splitwhile{1} <…>`, `swap <range>
    # <offset>` and bare `rnd.` placeholder templates were guidance — now dropped.
    assert "sp." not in actions
    assert not any(action.startswith("splitwhile{") for action in actions)
    assert not any(action.startswith("swap ") for action in actions)
    assert "skip." not in actions
    assert not any(action == "rnd." for action in actions)
    assert [
        item for item in ir["candidate_menu"]
        if item["id"] == "procedure_splitwhile_frontier"
    ] == []


def test_structured_procedure_frontier_plan_orders_prefix_before_loop() -> None:
    ir = build_proof_ir(current_goal={
        "goal_type": "pRHL",
        "parsed_goal": {
            "goal_type": "pRHL",
            "post": "post = ={x, i} /\\ bad{1} = bad{2}",
            "left_statements": [{
                "pos": 1,
                "pos_path": "1",
                "type": "ASSIGN",
                "text": "x <- a;",
                "vars_written": ["x"],
            }, {
                "pos": 2,
                "pos_path": "2",
                "type": "WHILE",
                "text": "while (i < n) {",
                "vars_read": ["i", "n"],
            }, {
                "pos": 3,
                "pos_path": "3",
                "type": "SAMPLE",
                "text": "r <$ d;",
                "vars_written": ["r"],
            }],
            "right_statements": [{
                "pos": 1,
                "pos_path": "1",
                "type": "ASSIGN",
                "text": "x <- a;",
                "vars_written": ["x"],
            }, {
                "pos": 2,
                "pos_path": "2",
                "type": "SAMPLE",
                "text": "r <$ d;",
                "vars_written": ["r"],
            }, {
                "pos": 3,
                "pos_path": "3",
                "type": "WHILE",
                "text": "while (i < n) {",
                "vars_read": ["i", "n"],
            }],
            "suggested_tactics": ["wp.", "rnd.", "while (...)."],
        },
    })

    frontend = ir["resources"]["handles"]["procedure_body_frontend"]
    plan = frontend["frontier_plan"]
    assert plan["available"] is True
    assert plan["frontier_kind"] == "straight_line_prefix_before_loop_frontier"
    assert plan["next_structural_region"]["kind"] == "loop_frontier"
    assert any("loop invariant" in step for step in plan["primary_passes"])
    assert any("defer inner rnd" in step for step in plan["wait_for"])
    # The `frontier_plan` frontend handle facts above stay; the
    # `procedure_structured_frontier_plan` MENU item was route-PLAN prose
    # (guidance) and is now dropped, so the ordering assertion is removed.
    ids = [item["id"] for item in ir["candidate_menu"]]
    assert "procedure_structured_frontier_plan" not in ids


def test_procedure_frontend_recovers_hoare_pretty_loop_frontier() -> None:
    goal = (
        "Current goal\n\n"
        "------------------------------------------------------------------------\n"
        "pre = true\n\n"
        "(1-----)  s <$ dBlock\n"
        "(2-----)  c <- [s]\n"
        "(3-----)  i <- 0\n"
        "(4-----)  while (i < size p) {\n"
        "(4. 1--)    pi <- nth witness p i\n"
        "\npost = true\n"
    )
    ir = build_proof_ir(current_goal={
        "goal_type": "hoare",
        "active_goal_preview": goal,
        "parsed_goal": {
            "goal_type": "hoare",
            "suggested_tactics": ["auto."],
        },
    })

    frontend = ir["resources"]["handles"]["procedure_body_frontend"]
    assert frontend["has_loop"] is True
    assert frontend["loop_frontiers"][0]["condition"] == "i < size p"
    actions = [item["tactic"] for item in ir["candidate_menu"]]
    # The guard-bound invariant (`while (0 <= i < size p); by auto; smt (size_ge0).`)
    # is dropped — surfacing the guard AS the invariant overclaims. The loop frontier
    # condition above is still a fact; the invariant itself is the agent's to construct.
    assert "while (0 <= i < size p); by auto; smt (size_ge0)." not in actions
    assert not any("0 <= i < size p" in action for action in actions)


def test_structured_procedure_frontier_plan_keeps_sample_as_local_vc() -> None:
    ir = build_proof_ir(current_goal={
        "goal_type": "pRHL",
        "parsed_goal": {
            "goal_type": "pRHL",
            "post": "post = t{2} = s{1} + mask{2}",
            "left_statements": [{
                "pos": 1,
                "pos_path": "1",
                "type": "SAMPLE",
                "text": "s <$ dT;",
                "vars_written": ["s"],
            }],
            "right_statements": [{
                "pos": 1,
                "pos_path": "1",
                "type": "SAMPLE",
                "text": "t <$ dT;",
                "vars_written": ["t"],
            }],
            "suggested_tactics": ["rnd.", "wp."],
        },
    })

    frontend = ir["resources"]["handles"]["procedure_body_frontend"]
    plan = frontend["frontier_plan"]
    assert plan["frontier_kind"] == "sample_frontier"
    assert any("rnd coupling" in step for step in plan["primary_passes"])
    assert any("avoid plain rnd" in step for step in plan["wait_for"])
    assert any(
        item["tactic"].startswith("rnd (fun x => x + mask{2})")
        for item in ir["candidate_menu"]
    )


def test_asymmetric_instrumentation_map_ranks_before_sim_probe() -> None:
    ir = build_proof_ir(current_goal={
        "goal_type": "pRHL",
        "parsed_goal": {
            "goal_type": "pRHL",
            "pre": "pre = true",
            "post": "post = c1{1} = c1{2} /\\ badi{2}",
            "left_statements": [{
                "pos": 1,
                "pos_path": "1",
                "type": "ASSIGN",
                "text": "c1 <- c;",
                "vars_written": ["c1"],
                "vars_read": ["c"],
            }],
            "right_statements": [{
                "pos": 1,
                "pos_path": "1",
                "type": "ASSIGN",
                "text": "c1 <- c;",
                "vars_written": ["c1"],
                "vars_read": ["c"],
            }, {
                "pos": 2,
                "pos_path": "2",
                "type": "ASSIGN",
                "text": "badi <- badi || test;",
                "vars_written": ["badi"],
                "vars_read": ["badi", "test"],
            }],
            "suggested_tactics": ["sim.", "wp."],
        },
    })

    menu_by_id = {item["id"]: item for item in ir["candidate_menu"]}
    # The `Inspect asymmetric instrumentation region` surface-map is a fact and
    # stays. `procedure_sim_residual` was a bare `sim.` (guidance), now dropped.
    assert "procedure_asymmetric_instrumentation_map" in menu_by_id
    assert "procedure_sim_residual" not in menu_by_id
    assert "badi" in menu_by_id["procedure_asymmetric_instrumentation_map"]["tactic"]


def test_current_region_summary_explains_sync_call_and_bad_event_monitor() -> None:
    ir = build_proof_ir(current_goal={
        "goal_type": "pRHL",
        "parsed_goal": {
            "goal_type": "pRHL",
            "pre": "pre = true",
            "post": "post = c{1} = c{2} /\\ badi{2}",
            "left_statements": [{
                "pos": 1,
                "pos_path": "1",
                "type": "CALL",
                "text": "c <@ EncRnd.cc(n, p);",
                "procedure": "EncRnd.cc",
                "vars_written": ["c"],
                "vars_read": ["n", "p"],
            }, {
                "pos": 2,
                "pos_path": "2",
                "type": "ASSIGN",
                "text": "lt <- map f Mem.lc;",
                "vars_written": ["lt"],
                "vars_read": ["Mem.lc"],
            }, {
                "pos": 3,
                "pos_path": "3",
                "type": "SAMPLE",
                "text": "t0 <$ dpoly_out;",
                "vars_written": ["t0"],
            }, {
                "pos": 4,
                "pos_path": "4",
                "type": "IF",
                "text": "if (cbad < q /\\ size lt <= qdec) {",
                "vars_written": ["lbad1", "cbad"],
                "vars_read": ["cbad", "lt"],
            }],
            "right_statements": [{
                "pos": 1,
                "pos_path": "1",
                "type": "CALL",
                "text": "c <@ EncRnd.cc(n, p);",
                "procedure": "EncRnd.cc",
                "vars_written": ["c"],
                "vars_read": ["n", "p"],
            }, {
                "pos": 2,
                "pos_path": "2",
                "type": "ASSIGN",
                "text": "lt <- map f Mem.lc;",
                "vars_written": ["lt"],
                "vars_read": ["Mem.lc"],
            }, {
                "pos": 3,
                "pos_path": "3",
                "type": "SAMPLE",
                "text": "t0 <$ dpoly_out;",
                "vars_written": ["t0"],
            }, {
                "pos": 4,
                "pos_path": "4",
                "type": "IF",
                "text": "if (cbad < q /\\ size lt <= qdec) {",
                "vars_written": ["lbad1", "cbad", "badi", "cbadi"],
                "vars_read": ["cbad", "lt", "badi", "cbadi"],
            }],
            "call_equiv_candidates": {"EncRnd.cc": ["equ_cc"]},
            "suggested_tactics": ["wp.", "sim."],
        },
    })

    frontend = ir["resources"]["handles"]["procedure_body_frontend"]
    summary = frontend["current_region_summary"]
    assert summary["available"] is True
    assert summary["synchronized_call_prefix"][0]["left"]["procedure"] == "EncRnd.cc"
    assert summary["paired_samples"][0]["distribution"] == "dpoly_out"
    assert "badi" in summary["asymmetric_instrumentation"]["right_extra_written_vars"]

    handle = [
        item for item in ir["resources"]["handles"]["callable_lemmas"]
        if item["lemma"] == "equ_cc"
    ][0]
    assert handle["same_concrete_call_pairs"]
    assert handle["call_candidate_kind"] == "source_lookup_landmark"
    assert not [
        item for item in ir["candidate_menu"]
        if item["id"] == "call_equ_cc"
    ]
    menu = ir["candidate_menu"]
    menu_ids = [item["id"] for item in menu]
    assert "procedure_current_region_summary" in menu_ids
    assert any("sync call EncRnd.cc" in item["tactic"] for item in menu)


def test_one_sided_call_and_result_maps_surface_without_hiding_program_steps() -> None:
    ir = build_proof_ir(current_goal={
        "goal_type": "pRHL",
        "parsed_goal": {
            "goal_type": "pRHL",
            "pre": "pre = true",
            "post": "post = ={res}",
            "left_statements": [{
                "pos": 1,
                "pos_path": "1",
                "type": "CALL",
                "text": "p <@ E.dec(k, c);",
                "procedure": "E.dec",
                "vars_written": ["p"],
            }, {
                "pos": 2,
                "pos_path": "2",
                "type": "ASSIGN",
                "text": "res <- p <> None;",
                "vars_written": ["res"],
                "vars_read": ["p"],
            }],
            "right_statements": [{
                "pos": 1,
                "pos_path": "1",
                "type": "ASSIGN",
                "text": "res <- b;",
                "vars_written": ["res"],
                "vars_read": ["b"],
            }],
            "suggested_tactics": ["sim.", "wp."],
        },
    })

    frontend = ir["resources"]["handles"]["procedure_body_frontend"]
    assert frontend["result_expression_map"]["relation_shape"] == (
        "derived_result_mismatch"
    )
    assert frontend["one_sided_call_site_summary"]["available"] is True

    menu = ir["candidate_menu"]
    menu_by_id = {item["id"]: item for item in menu}
    assert "procedure_result_expression_map" in menu_by_id
    assert "procedure_one_sided_call_site_map" in menu_by_id
    assert "p <> None" in menu_by_id["procedure_result_expression_map"]["tactic"]
    assert "E.dec" in menu_by_id["procedure_one_sided_call_site_map"]["tactic"]


def test_bad_event_candidate_map_surfaces_event_fanout_without_recipe() -> None:
    ir = build_proof_ir(current_goal={
        "goal_type": "pRHL",
        "parsed_goal": {
            "goal_type": "pRHL",
            "pre": "!MACa.SUF_CMA.SUF_Wrap.win{2}",
            "post": "post = CTXT_Wrap.win{1} => MACa.SUF_CMA.SUF_Wrap.win{2}",
            "left_statements": [{
                "pos": 1,
                "pos_path": "1",
                "type": "CALL",
                "text": "b <@ A(O).forge();",
                "procedure": "A(O).forge",
                "vars_written": ["b"],
            }, {
                "pos": 2,
                "pos_path": "2",
                "type": "ASSIGN",
                "text": "CTXT_Wrap.win <- b;",
                "vars_written": ["CTXT_Wrap.win"],
                "vars_read": ["b"],
            }],
            "right_statements": [{
                "pos": 1,
                "pos_path": "1",
                "type": "ASSIGN",
                "text": "MACa.SUF_CMA.SUF_Wrap.win <- false;",
                "vars_written": ["MACa.SUF_CMA.SUF_Wrap.win"],
            }],
            "suggested_tactics": ["sim.", "wp."],
        },
    })

    frontend = ir["resources"]["handles"]["procedure_body_frontend"]
    event_map = frontend["bad_event_candidate_map"]
    assert event_map["available"] is True
    assert event_map["fanout_prediction"]["fanout_risk"] == (
        "high_if_used_before_oracle_obligations_are_mapped"
    )

    item = [
        item for item in ir["candidate_menu"]
        if item["id"] == "procedure_bad_event_candidate_map"
    ][0]
    assert "MACa.SUF_CMA.SUF_Wrap.win" in item["tactic"]
    assert "not a runnable tactic" in " ".join(item["preconditions"])


def test_bad_event_candidate_map_precedes_event_invariant_skeleton() -> None:
    ir = build_proof_ir(current_goal={
        "goal_type": "pRHL",
        "parsed_goal": {
            "goal_type": "pRHL",
            "pre": (
                "pre = UFCMA_li.badi{2} = false /\\ "
                "UFCMA_l.lbad1{1} = []"
            ),
            "post": (
                "post = (let tt = nth (w1,w2) UFCMA_l.lbad1{1} nth0 "
                "in tt.`1 = tt.`2) => UFCMA_li.badi{2}"
            ),
            "left_statements": [{
                "pos": 1,
                "pos_path": "1",
                "type": "CALL",
                "text": "b <@ CPA_game(Adv, UFCMA_l.O).main();",
                "procedure": "CPA_game.main",
                "vars_written": ["b"],
            }],
            "right_statements": [{
                "pos": 1,
                "pos_path": "1",
                "type": "CALL",
                "text": "b <@ CPA_game(Adv, UFCMA_li.O).main();",
                "procedure": "CPA_game.main",
                "vars_written": ["b"],
            }],
            "suggested_tactics": ["call (_: Inv).", "sim."],
        },
    })

    menu_ids = [item["id"] for item in ir["candidate_menu"]]
    assert "procedure_bad_event_candidate_map" in menu_ids
    assert "call_invariant_skeleton" in menu_ids


def test_sampling_obligation_frontend_classifies_translation_generically() -> None:
    ir = build_proof_ir(current_goal={
        "goal_type": "pRHL",
        "active_goal_preview": (
            "pre = true\n\n"
            "s <$ dT              (1)  t <$ dT\n\n"
            "post = t{2} = s{1} + mask{2}"
        ),
        "parsed_goal": {
            "goal_type": "pRHL",
            "post": "post = t{2} = s{1} + mask{2}",
            "left_statements": [{
                "pos": 1,
                "pos_path": "1",
                "type": "SAMPLE",
                "text": "s <$ dT;",
                "vars_written": ["s"],
            }],
            "right_statements": [{
                "pos": 1,
                "pos_path": "1",
                "type": "SAMPLE",
                "text": "t <$ dT;",
                "vars_written": ["t"],
            }],
            "suggested_tactics": ["wp.", "auto => />."],
        },
    })

    frontend = ir["resources"]["handles"]["procedure_body_frontend"]
    obligation = frontend["sampling_obligations"][0]
    assert obligation["relation_motif"]["motif"] == "translation_or_affine"
    assert obligation["same_distribution"] is True
    assert "dT_uffu" in obligation["required_evidence"]["candidate_distribution_facts"]
    assert any(
        family["family"] == "translation_or_affine"
        for family in obligation["candidate_families"]
    )
    rnd = [
        item for item in ir["candidate_menu"]
        if item["id"] == "procedure_rnd_coupling"
    ][0]
    assert rnd["action_type"] == "strategy_hint"
    assert rnd["tactic"] == "rnd (fun x => x + mask{2}) (fun x => x - mask{2})."
    assert "poly1305" not in json.dumps(rnd)


def test_sampling_obligation_frontend_pairs_same_distributions_before_fallback() -> None:
    ir = build_proof_ir(current_goal={
        "goal_type": "pRHL",
        "active_goal_preview": (
            "pre = true\n\n"
            "r <$ dR              (1)\n"
            "s <$ dS              (2)  t <$ dS\n\n"
            "post = t{2} = s{1} + offset{1}"
        ),
        "parsed_goal": {
            "goal_type": "pRHL",
            "post": "post = t{2} = s{1} + offset{1}",
            "left_statements": [{
                "pos": 1,
                "pos_path": "1",
                "type": "SAMPLE",
                "text": "r <$ dR;",
                "vars_written": ["r"],
            }, {
                "pos": 2,
                "pos_path": "2",
                "type": "SAMPLE",
                "text": "s <$ dS;",
                "vars_written": ["s"],
            }],
            "right_statements": [{
                "pos": 1,
                "pos_path": "1",
                "type": "SAMPLE",
                "text": "t <$ dS;",
                "vars_written": ["t"],
            }],
            "suggested_tactics": ["wp.", "auto => />."],
        },
    })

    obligations = ir["resources"]["handles"]["procedure_body_frontend"][
        "sampling_obligations"
    ]
    first = obligations[0]
    assert first["left_sample"]["var"] == "s"
    assert first["right_sample"]["var"] == "t"
    assert first["same_distribution"] is True
    assert first["relation_motif"]["motif"] == "translation_or_affine"
    second = obligations[1]
    assert second["left_sample"]["var"] == "r"
    assert second["right_sample"] == {}

    diag_codes = {diag["code"] for diag in ir["diagnostics"]}
    assert "proof_ir.sampling_pair_before_one_sided" in diag_codes
    rnd_item = [
        item for item in ir["candidate_menu"]
        if item["id"] == "procedure_rnd_coupling"
    ][0]
    assert any(
        "handle the paired coupling first" in precondition
        for precondition in rnd_item["preconditions"]
    )

    # The route-PLAN `procedure_structured_frontier_plan` menu item is dropped as
    # guidance; the goal-FILLED `rnd (fun…)` coupling below is a fact and stays.
    menu_ids = [item["id"] for item in ir["candidate_menu"]]
    assert "procedure_structured_frontier_plan" not in menu_ids
    assert rnd_item["tactic"].startswith("rnd (fun x => x + offset{1})")


def test_one_sided_sampling_residual_ranks_as_risk_map() -> None:
    ir = build_proof_ir(current_goal={
        "goal_type": "pRHL",
        "active_goal_preview": (
            "pre = true\n\n"
            "        (1)  t1 <$ dtag\n\n"
            "post = forall (t0_0 : tag), t0_0 \\in dtag => t0_0 = t1{2}"
        ),
        "parsed_goal": {
            "goal_type": "pRHL",
            "post": (
                "post = forall (t0_0 : tag), t0_0 \\in dtag => "
                "t0_0 = t1{2}"
            ),
            "right_statements": [{
                "pos": 1,
                "pos_path": "1",
                "type": "SAMPLE",
                "text": "t1 <$ dtag;",
                "vars_written": ["t1"],
                "distribution": "dtag",
            }],
            "suggested_tactics": ["rnd{2}.", "auto."],
        },
    })

    frontend = ir["resources"]["handles"]["procedure_body_frontend"]
    residual = frontend["one_sided_sampling_residual_map"]
    assert residual["available"] is True
    assert residual["universal_witnesses"] == ["t0_0"]

    diag_codes = {diag["code"] for diag in ir["diagnostics"]}
    assert "proof_ir.one_sided_sampling_residual" in diag_codes
    residual_item = [
        item for item in ir["candidate_menu"]
        if item["id"] == "procedure_one_sided_sampling_residual_map"
    ][0]
    assert "t1{2} <$ dtag" in residual_item["tactic"]


def test_sampling_obligation_frontend_handles_mlkems_seed_like_identity_shape() -> None:
    ir = build_proof_ir(current_goal={
        "goal_type": "pRHL",
        "active_goal_preview": (
            "pre = ={ek}\n\n"
            "m <$ dbytes32          (1)  m <$ dbytes32\n"
            "z <$ dbytes32          (2)  z <$ dbytes32\n\n"
            "post = ={m, z}"
        ),
        "parsed_goal": {
            "goal_type": "pRHL",
            "post": "post = ={m, z}",
            "left_statements": [{
                "pos": 1,
                "pos_path": "1",
                "type": "SAMPLE",
                "text": "m <$ dbytes32;",
                "vars_written": ["m"],
            }, {
                "pos": 2,
                "pos_path": "2",
                "type": "SAMPLE",
                "text": "z <$ dbytes32;",
                "vars_written": ["z"],
            }],
            "right_statements": [{
                "pos": 1,
                "pos_path": "1",
                "type": "SAMPLE",
                "text": "m <$ dbytes32;",
                "vars_written": ["m"],
            }, {
                "pos": 2,
                "pos_path": "2",
                "type": "SAMPLE",
                "text": "z <$ dbytes32;",
                "vars_written": ["z"],
            }],
            "suggested_tactics": ["wp.", "auto => />."],
        },
    })

    frontend = ir["resources"]["handles"]["procedure_body_frontend"]
    assert frontend["has_sampling_obligation"] is True
    assert all(
        obligation["same_distribution"]
        for obligation in frontend["sampling_obligations"]
    )
    families = {
        family["family"]
        for family in frontend["sampling_candidate_families"]
    }
    assert "identity" in families
    assert "translation_or_affine" not in families


def test_procedure_body_frontend_surfaces_visible_wrapper_inline() -> None:
    ir = build_proof_ir(current_goal={
        "goal_type": "pRHL",
        "parsed_goal": {
            "goal_type": "pRHL",
            "post": (
                "post = ((glob A){1} = (glob A){2}) && "
                "forall (result_L result_R : bool), result_L = result_R"
            ),
            "left_statements": [{
                "pos": 1,
                "pos_path": "1",
                "type": "ASSIGN",
                "text": "RealOrcls(GenChaChaPoly(OCC(IFinRO))).init()",
            }],
            "right_statements": [{
                "pos": 1,
                "pos_path": "1",
                "type": "ASSIGN",
                "text": "FinRO.init()",
            }],
            "suggested_tactics": ["sim.", "wp.", "auto => />."],
        },
    })

    actions = [item["tactic"] for item in ir["candidate_menu"]]
    # The goal-FILLED `inline RealOrcls…` is a fact and stays. The un-filled
    # `conseq (_: <weaker…>)` placeholder and bare `sim.` were guidance — dropped.
    assert any(action.startswith("inline RealOrcls") for action in actions)
    assert "conseq (_: <weaker postcondition preserving live state>) => />." not in actions
    assert "sim." not in actions


def test_probabilistic_vc_frontend_classifies_mee_loop_bad_bound() -> None:
    ir = build_proof_ir(current_goal={
        "goal_type": "pRHL",
        "active_goal_preview": (
            "pre = ={p, c}\n\n"
            "while (i < size p) { ... if (mem qs s) { bad <- true; } }\n\n"
            "post = Compute.bad{2} = "
            "(DoubleQuery.bad{1} \\/ mem DoubleQuery.qs (s + nth witness p i)){1}"
        ),
        "parsed_goal": {
            "goal_type": "pRHL",
            "post": (
                "post = Compute.bad{2} = "
                "(DoubleQuery.bad{1} \\/ mem DoubleQuery.qs (s + nth witness p i)){1}"
            ),
            "left_statements": [{
                "pos": 1,
                "pos_path": "1",
                "type": "WHILE",
                "text": "while (i < size p) {",
                "vars_read": ["i", "p"],
            }, {
                "pos": 2,
                "pos_path": "1.1",
                "type": "IF",
                "text": "if (mem qs s) {",
            }],
            "right_statements": [{
                "pos": 1,
                "pos_path": "1",
                "type": "WHILE",
                "text": "while (i < size p) {",
                "vars_read": ["i", "p"],
            }, {
                "pos": 2,
                "pos_path": "1.1",
                "type": "SAMPLE",
                "text": "s <$ dblock;",
                "vars_written": ["s"],
            }],
            "suggested_tactics": ["while (...).", "rcondt{1} 2.", "rnd."],
        },
    })

    frontend = ir["resources"]["handles"]["probabilistic_vc_frontend"]
    assert frontend["available"] is True
    kinds = {item["kind"] for item in frontend["obligations"]}
    assert "bad_event_reduction" in kinds
    assert "loop_bad_event_bound" in kinds
    assert "branch_event_split" in kinds
    assert "sampling_loss_or_coupling" in kinds
    assert "loop bad-event" in frontend["strategy"]
    # The `probabilistic_vc_plan` menu item rendered a `Probabilistic VC plan:`
    # route-PLAN (guidance); the VC frontend handle/obligation facts above stay,
    # but the plan menu item itself is now dropped.
    assert [
        item for item in ir["candidate_menu"]
        if item["id"] == "probabilistic_vc_plan"
    ] == []
    assert not any(
        item["tactic"].startswith("Probabilistic VC plan:")
        for item in ir["candidate_menu"]
    )


def test_probabilistic_vc_frontend_classifies_cramer_shoup_phoare_bound() -> None:
    ir = build_proof_ir(current_goal={
        "goal_type": "phoare",
        "active_goal_preview": (
            "phoare[ G4.main : true ==> "
            "(G3.a, G3.a_, G3.c, G3.d) \\in G3.cilog ] <= "
            "(PKE_.qD%r / order%r)"
        ),
        "parsed_goal": {
            "goal_type": "phoare",
            "post": (
                "post = (G3.a, G3.a_, G3.c, G3.d) \\in G3.cilog"
            ),
            "left_statements": [{
                "pos": 1,
                "pos_path": "1",
                "type": "SAMPLE",
                "text": "y <$ dt;",
                "vars_written": ["y"],
            }],
            "suggested_tactics": [
                "seq 23 : ((G3.a, G3.a_, G3.c, G3.d) \\in G3.cilog) 1%r 1%r 0%r _.",
                "rnd.",
            ],
        },
    })

    frontend = ir["resources"]["handles"]["probabilistic_vc_frontend"]
    assert frontend["available"] is True
    kinds = {item["kind"] for item in frontend["obligations"]}
    assert "phoare_seq_bound" in kinds
    assert "sampling_loss_or_coupling" in kinds
    assert frontend["strategy"] == "bounded phoare VC generation"
    # VC frontend facts above stay; the `Probabilistic VC plan:` route-PLAN menu
    # item is now dropped as guidance.
    actions = [item["tactic"] for item in ir["candidate_menu"]]
    assert not any(action.startswith("Probabilistic VC plan:") for action in actions)


def test_probabilistic_vc_frontend_classifies_pr_loss_accounting() -> None:
    ir = build_proof_ir(current_goal={
        "goal_type": "probability",
        "active_goal_preview": (
            "Current goal\n\n"
            "------------------------------------------------------------------------\n"
            "`| Pr[G0.main() @ &m : res] - Pr[G1.main() @ &m : res] | <=\n"
            "Pr[BadGame.main() @ &m : BadGame.bad] + eps"
        ),
        "parsed_goal": {
            "goal_type": "probability",
            "prob_form": "adv_diff_ineq",
        },
    })

    frontend = ir["resources"]["handles"]["probabilistic_vc_frontend"]
    assert frontend["available"] is True
    kinds = {item["kind"] for item in frontend["obligations"]}
    assert "pr_loss_accounting" in kinds
    assert "bad_event_reduction" in kinds
    assert "have-chain" in frontend["expected_rule_families"]
    # VC frontend facts above stay; the `Probabilistic VC plan:` route-PLAN menu
    # item is now dropped as guidance.
    assert not any(
        item["tactic"].startswith("Probabilistic VC plan:")
        for item in ir["candidate_menu"]
    )


def test_procedure_entry_with_body_transform_suggestion_is_body_layer() -> None:
    ir = build_proof_ir(current_goal={
        "goal_type": "phoare",
        "parsed_goal": {
            "goal_type": "phoare",
            "suggested_tactics": ["wp.", "auto."],
        },
    })

    actions = [item["tactic"] for item in ir["candidate_menu"]]
    # The layer classification is a fact and stays; the bare `wp.` suggestion was
    # move GUIDANCE and is now dropped.
    assert ir["current_layer"] == "procedure_body"
    assert "wp." not in actions


def test_phoare_lossless_without_statements_stays_procedure_entry() -> None:
    ir = build_proof_ir(current_goal={
        "goal_type": "phoare",
        "active_goal_preview": (
            "Current goal\n\n"
            "------------------------------------------------------------------------\n"
            "pre = true\n\nM.f [=] 1%r\n\npost = true\n"
        ),
        "parsed_goal": {
            "goal_type": "phoare",
            "suggested_tactics": ["proc.", "islossless."],
        },
    })

    assert ir["current_layer"] == "procedure_entry"
    assert ir["candidate_menu"][0]["id"] == "proc_open"
    assert ir["candidate_menu"][0]["tactic"] == "proc."


def test_procedure_entry_surfaces_body_fallback_menu_after_proc() -> None:
    ir = build_proof_ir(current_goal={
        "goal_type": "phoare",
        "parsed_goal": {
            "goal_type": "phoare",
            "suggested_tactics": ["proc."],
        },
    })

    actions = [item["tactic"] for item in ir["candidate_menu"]]
    # The state-derived opener `proc.` is a fact and stays. The hardcoded
    # body-fallback palette (bare `wp.`/`sp.`/`rnd.`/`if => //=.`/`rcondf 1;…`
    # and the `<loop invariant>`/`<loop-index>`/`<range> <offset>`/`<proof-relevant
    # condition>` placeholder templates) was move GUIDANCE and is now dropped.
    assert ir["current_layer"] == "procedure_entry"
    assert "proc." in actions
    assert "wp." not in actions
    assert "sp." not in actions
    assert "while (<loop invariant>)." not in actions
    assert "splitwhile{1} <loop-index>: (<split condition>)." not in actions
    assert "swap <range> <offset> => //=." not in actions
    assert "rnd." not in actions
    assert "if => //=." not in actions
    assert "rcondf 1; first auto." not in actions
    assert "case: (<proof-relevant condition>)." not in actions


def test_pr_byequiv_fallback_stays_below_rewrite_candidates() -> None:
    ir = build_proof_ir(current_goal={
        "goal_type": "probability",
        "parsed_goal": {
            "goal_type": "probability",
            "prob_form": "eq",
            "lhs_game": "G0",
            "rhs_game": "G1",
            "strategy_hint": "byequiv",
            "suggested_tactics": ["byequiv => //.", "rewrite ..."],
            "pr_rewrite_candidates": ["pr_G0_G1"],
        },
    })

    # The typed `rewrite pr_…` handle is a fact and stays. `pr_byequiv_fallback`
    # rendered a bare hardcoded `byequiv => //.` (move GUIDANCE) and is now dropped.
    menu_ids = [item["id"] for item in ir["candidate_menu"]]
    assert "rewrite_pr_handle" in menu_ids
    assert "pr_byequiv_fallback" not in menu_ids


def test_pr_byequiv_fallback_becomes_probe_when_pr_handles_need_lookup() -> None:
    ir = build_proof_ir(current_goal={
        "goal_type": "probability",
        "parsed_goal": {
            "goal_type": "probability",
            "prob_form": "eq",
            "lhs_game": "G0",
            "rhs_game": "G1",
            "strategy_hint": "byequiv",
            "suggested_tactics": ["byequiv => //."],
            "pr_rewrite_candidates": [{"lemma": "pr_RO_FinRO_D"}],
        },
    })

    # `pr_byequiv_fallback` was a bare hardcoded `byequiv => //.` (move GUIDANCE);
    # it is no longer surfaced regardless of whether the pr handles need a lookup.
    assert [
        item for item in ir["candidate_menu"]
        if item["id"] == "pr_byequiv_fallback"
    ] == []
    assert "byequiv => //." not in {
        item["tactic"] for item in ir["candidate_menu"]
    }


def test_pr_bound_clone_wrapper_surfaces_apply_candidate() -> None:
    ir = build_proof_ir(current_goal={
        "goal_type": "probability",
        "active_goal_preview": (
            "Current goal\n\n"
            "------------------------------------------------------------------------\n"
            "`|Pr[RP_RFc.PRFt.IND(PRPi, "
            "RP_RFc.DBounder(PRPF_Adv(QueryBounder(A)))).main() @ &m : res] - "
            "Pr[RP_RFc.PRFt.IND(RP_RFc.PRFi.PRFi, "
            "RP_RFc.DBounder(PRPF_Adv(QueryBounder(A)))).main() @ &m : res]| <= "
            "eps"
        ),
        "parsed_goal": {
            "goal_type": "probability",
            "prob_form": "adv_diff_ineq",
        },
    })

    apply_item = [
        item for item in ir["candidate_menu"]
        if item["id"] == "pr_clone_bound_apply_0"
    ][0]
    assert apply_item["tactic"] == (
        "apply/(RP_RFc.Conclusion_DBounder "
        "PRPF_Adv(QueryBounder(A)) _ &m)."
    )
    assert apply_item["action_type"] == "strategy_hint"


def test_while_frontier_exposure_does_not_suggest_plain_wp() -> None:
    ir = build_proof_ir(current_goal={
        "goal_type": "pRHL",
        "active_goal_preview": (
            "Current goal\n\n"
            "Hf: equiv[ P.f ~ P'.f : true ==> ={res}]\n"
            "------------------------------------------------------------------------\n"
            "&1 (left) : {i : int}\n&2 (right) : {i : int}\n"
        ),
        "parsed_goal": {
            "goal_type": "pRHL",
            "left_statements": [{
                "pos": 1,
                "pos_path": "1",
                "type": "WHILE",
                "text": "while (i < n) {",
            }, {
                "pos": 1,
                "pos_path": "1.1",
                "type": "CALL",
                "text": "x <@ P.f();",
                "procedure": "P.f",
            }],
            "right_statements": [{
                "pos": 1,
                "pos_path": "1",
                "type": "WHILE",
                "text": "while (i < n) {",
            }, {
                "pos": 1,
                "pos_path": "1.1",
                "type": "CALL",
                "text": "x <@ P'.f();",
                "procedure": "P'.f",
            }],
        },
    })

    exposure = [
        item for item in ir["candidate_menu"]
        if item["id"] == "expose_frontier_call"
    ][0]
    assert exposure["tactic"].startswith("while (")
    assert exposure["tactic"] != "wp."
    assert exposure["cost_factors"]["frontier_blocker_kinds"] == ["WHILE"]


def test_branch_frontier_defers_if_when_live_call_handle_needs_seq() -> None:
    ir = build_proof_ir(current_goal={
        "goal_type": "pRHL",
        "parsed_goal": {
            "goal_type": "pRHL",
            "pre": "pre = k{1} = Mem.k{1} /\\ Mem.k{1} = Block.k{2}",
            "post": "post = ={n, t, result} /\\ c0{1} = c{2}",
            "left_statements": [{
                "pos": 1,
                "pos_path": "1",
                "type": "CALL",
                "text": "t' <@ Poly.mac(n, c0);",
                "procedure": "Poly.mac",
                "vars_read": ["k", "n", "c0"],
                "vars_written": ["t'"],
            }, {
                "pos": 2,
                "pos_path": "2",
                "type": "IF",
                "text": "if (t' = t) {",
                "vars_read": ["t'", "t"],
            }],
            "right_statements": [{
                "pos": 1,
                "pos_path": "1",
                "type": "CALL",
                "text": "t <@ O.Poly.mac(n, c);",
                "procedure": "O.Poly.mac",
                "vars_read": ["Block.k", "n", "c"],
                "vars_written": ["t"],
            }, {
                "pos": 2,
                "pos_path": "2",
                "type": "IF",
                "text": "if (t' = t) {",
                "vars_read": ["t'", "t"],
            }],
            "call_equiv_candidates": {
                "Poly.mac": ["poly_mac1"],
            },
        },
    })

    # Both the `seq … : <invariant>` cut (`program_seq_cut`, placeholder +
    # requires_instantiation) and the `if_frontier` bare-`if` transform were move
    # GUIDANCE, so neither is surfaced in the menu now.
    menu_ids = [item["id"] for item in ir["candidate_menu"]]
    assert "program_seq_cut" not in menu_ids
    assert "if_frontier" not in menu_ids


def test_program_diff_orders_call_handles_by_statement_order() -> None:
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
                "text": "t <@ D.O.Poly.mac(n, a, c);",
                "procedure": "D.O.Poly.mac",
            }, {
                "pos": 2,
                "pos_path": "2",
                "type": "CALL",
                "text": "c <@ D.O.ChaCha.enc(n, p);",
                "procedure": "D.O.ChaCha.enc",
            }],
            "call_equiv_candidates": {
                "ChaCha.enc": ["chacha_enc1"],
                "Poly.mac": ["poly_mac1"],
            },
        },
    })

    handles = ir["resources"]["handles"]["callable_lemmas"]
    assert [handle["lemma"] for handle in handles] == [
        "poly_mac1",
        "chacha_enc1",
    ]
    assert handles[0]["program_diff_steps"][0]["kind"] == "aligned_call_pair"
    assert handles[0]["program_diff_steps"][0]["order"] == 1
    assert handles[1]["callable_now"] is True
    assert handles[1]["call_candidate_kind"] == "source_lookup_landmark"
    assert ir["resources"]["program_ir"]["program_diff"]["edit_script"][0][
        "procedure_tail"
    ] == "Poly.mac"
    # The program-diff edit-script fact (resources, above) stays. The
    # `seq 1 1 : <invariant…>` MENU item carried a `<placeholder>` and is now
    # dropped as guidance.
    assert not any(
        item["tactic"].startswith("seq 1 1")
        for item in ir["candidate_menu"]
    )


def test_external_recommendations_become_proof_ir_candidates() -> None:
    recs = [{
        "id": "auto_pivot_call_ready.0",
        "producer": "AUTO-PIVOT-CALL-READY",
        "action": "call poly_mac1.",
        "action_type": "runnable_tactic",
        "confidence": "verified",
        "metadata": {"epistemic_status": "daemon_probe_accepted"},
    }, {
        "id": "auto_bridge.single.0",
        "producer": "AUTO-BRIDGE-SUGGEST",
        "action": "-chain -c 'rewrite pr_RO_FinRO_D.'",
        "action_type": "inspection_action",
        "confidence": "verified",
        "metadata": {"bridge_kind": "single"},
    }, {
        "id": "try.inv.0",
        "producer": "try",
        "action": "call (_: I (glob P){1} (glob P'){2}).",
        "action_type": "runnable_tactic",
        "confidence": "verified",
        "metadata": {"epistemic_status": "daemon_probe_accepted"},
    }]
    ir = build_proof_ir(
        current_goal={
            "goal_type": "pRHL",
            "parsed_goal": {
                "goal_type": "pRHL",
                "left_statements": [],
                "right_statements": [],
            },
        },
        external_recommendations=recs,
    )

    candidates = ir["resources"]["external_candidates"]
    by_id = {candidate["id"]: candidate for candidate in candidates}
    assert by_id["auto_pivot_call_ready.0"]["tactic_family"] == "call_named_equiv"
    assert by_id["auto_pivot_call_ready.0"]["layer"] == "call_site"
    assert by_id["auto_pivot_call_ready.0"]["cost"] == "cheap"
    assert by_id["auto_pivot_call_ready.0"]["verified"] is True
    assert by_id["auto_bridge.single.0"]["tactic_family"] == "pr_bridge"
    assert by_id["auto_bridge.single.0"]["tactic"] == "rewrite pr_RO_FinRO_D."
    assert by_id["auto_bridge.single.0"]["cost"] == "cheap"
    assert by_id["try.inv.0"]["tactic_family"] == "call_invariant_skeleton"
    assert by_id["try.inv.0"]["layer"] == "call_site"
    assert by_id["try.inv.0"]["cost"] == "cheap"


def test_external_candidate_requires_scope_check_for_source_local_name() -> None:
    with tempfile.TemporaryDirectory() as td:
        session = Path(td)
        source = session / "Target.ec"
        source.write_text(
            "section Cleanup.\n"
            "  local equiv enc_eq: L.f ~ R.f : true ==> ={res}.\n"
            "  proof. by trivial. qed.\n"
            "end section Cleanup.\n"
            "lemma target: true. proof. trivial. qed.\n",
            encoding="utf-8",
        )
        (session / "context.ec").write_text("", encoding="utf-8")
        (session / "session_meta.json").write_text(
            json.dumps({"file": str(source), "lemma": "target"}),
            encoding="utf-8",
        )
        recs = [{
            "id": "auto_diff.enc_eq",
            "producer": "AUTO-DIFF",
            "action": "call enc_eq.",
            "action_type": "probe_tactic",
            "confidence": "medium",
        }]
        ir = build_proof_ir(
            session_dir=session,
            current_goal={
                "goal_type": "equiv",
                "parsed_goal": {"goal_type": "equiv"},
            },
            external_recommendations=recs,
        )

    candidate = ir["resources"]["external_candidates"][0]
    assert candidate["tactic_family"] == "call_named_equiv"
    assert candidate["action_type"] == "strategy_hint"
    assert candidate["name_resolution"]["resolution_status"] == (
        "source_local_scope_check_required"
    )
    menu_by_family = {
        item["tactic_family"]: item
        for item in ir["candidate_menu"]
        if item["id"].startswith("sig_external_call_")
        or item["id"].startswith("external_call_")
    }
    assert menu_by_family["signature_lookup"]["tactic"] == "-where enc_eq"
    assert menu_by_family["signature_lookup"]["action_type"] == "inspection_action"
    assert "call_named_equiv" not in menu_by_family


def test_no_progress_external_candidate_is_avoided() -> None:
    recs = [{
        "id": "auto_pivot.bound",
        "producer": "AUTO-PIVOT",
        "action": "apply Bound_by_PRP_PRF.",
        "action_type": "runnable_tactic",
        "confidence": "medium",
    }]
    ir = build_proof_ir(
        proof_state={
            "latest_transition": {
                "kind": "no_progress",
                "status": "no_progress_reverted",
                "tactic": "apply Bound_by_PRP_PRF.",
                "no_progress": True,
                "no_progress_reason": "text-equal",
            },
        },
        current_goal={
            "goal_type": "probability",
            "parsed_goal": {
                "goal_type": "probability",
                "prob_form": "adv_ineq",
                "lhs_game": "Game0",
                "rhs_game": "Game1",
            },
        },
        external_recommendations=recs,
    )

    candidate = ir["resources"]["external_candidates"][0]
    assert candidate["action_type"] == "avoid_action"
    assert candidate["legality"]["status"] == "avoid"
    assert candidate["cost_factors"]["negative_evidence"] == "latest_no_progress"


def test_unverified_external_pr_apply_is_probe_after_signature_resolution() -> None:
    recs = [{
        "id": "auto_pivot.bound",
        "producer": "AUTO-PIVOT",
        "action": "apply Bound_by_PRP_PRF.",
        "action_type": "runnable_tactic",
        "confidence": "medium",
    }]
    context = """\
lemma Bound_by_PRP_PRF &m:
  Pr[Game0.main() @ &m : res] <= Pr[Game1.main() @ &m : res].
proof. by trivial. qed.
"""
    with tempfile.TemporaryDirectory() as td:
        session = Path(td)
        (session / "context.ec").write_text(context, encoding="utf-8")
        ir = build_proof_ir(
            session_dir=session,
            current_goal={
                "goal_type": "probability",
                "parsed_goal": {
                    "goal_type": "probability",
                    "prob_form": "adv_ineq",
                    "lhs_game": "Game0",
                    "rhs_game": "Game1",
                },
            },
            external_recommendations=recs,
        )

    candidate = ir["resources"]["external_candidates"][0]
    assert candidate["name_resolution"]["resolution_status"] == (
        "resolved_local_declaration"
    )
    assert candidate["action_type"] == "probe_tactic"
    assert candidate["cost_factors"]["external_pr_path_requires_probe"] is True


def test_ambient_implication_gets_intro_candidate() -> None:
    ir = build_proof_ir(current_goal={
        "goal_type": "ambient",
        "active_goal_preview": (
            "Current goal\n"
            "------------------------------------------------------------------------\n"
            "equiv[ P.f ~ P'.f : true ==> ={res}] =>\n"
            "equiv[ O(P).enc ~ O(P').enc : true ==> ={res}]"
        ),
        "parsed_goal": {
            "goal_type": "ambient",
            "ambient_shape": "logical",
        },
    })

    assert ir["candidate_menu"][0]["id"] == "intro"
    assert ir["candidate_menu"][0]["tactic"] == "move=> H."
    assert ir["candidate_menu"][0]["tactic_family"] == "intro"


def test_intro_candidate_uses_fresh_hypothesis_name() -> None:
    ir = build_proof_ir(current_goal={
        "goal_type": "probability",
        "active_goal_preview": (
            "Current goal\n\n"
            "H: equiv[ P.init ~ P'.init : true ==> ={glob P}]\n"
            "------------------------------------------------------------------------\n"
            "equiv[ P.f ~ P'.f : true ==> ={res}] =>\n"
            "Pr[G.main() @ &m : res] = Pr[G'.main() @ &m : res]"
        ),
        "parsed_goal": {
            "goal_type": "probability",
            "prob_form": "eq",
            "intro_required": True,
        },
    })

    assert ir["candidate_menu"][0]["tactic"] == "move=> H0."


def test_intro_candidate_names_memory_and_module_binders() -> None:
    ir = build_proof_ir(current_goal={
        "goal_type": "probability",
        "active_goal_preview": (
            "Current goal\n\n"
            "H: equiv[ P.f ~ P'.f : true ==> ={res}]\n"
            "H0: equiv[ P.g ~ P'.g : true ==> ={res}]\n"
            "------------------------------------------------------------------------\n"
            "forall &m (A(O : RCPA_Oracles) <: RCPA_Adversary{-P}),\n"
            "  Pr[G(A).main() @ &m : res] = Pr[G'(A).main() @ &m : res]"
        ),
        "parsed_goal": {
            "goal_type": "probability",
            "prob_form": "eq",
            "intro_required": True,
        },
    })

    assert ir["candidate_menu"][0]["tactic"] == "move=> &m A."


def test_ambient_forall_memory_intro_names_all_binders_and_premise() -> None:
    ir = build_proof_ir(current_goal={
        "goal_type": "ambient",
        "active_goal_preview": (
            "Current goal\n"
            "------------------------------------------------------------------------\n"
            "forall &1 &2,\n"
            "  p{1} = p{2} /\\ I (glob P){1} (glob P'){2} =>\n"
            "  c{1} = c{2}"
        ),
        "parsed_goal": {
            "goal_type": "ambient",
            "ambient_shape": "logical",
        },
    })

    assert ir["candidate_menu"][0]["id"] == "intro"
    assert ir["candidate_menu"][0]["tactic"] == "move=> &1 &2 H."
    frontend = ir["resources"]["handles"]["ambient_frontend"]
    assert frontend["intro_required"] is True
    assert frontend["intro_tactic"] == "move=> &1 &2 H."


def test_ambient_forall_typed_binder_intro_keeps_premise() -> None:
    ir = build_proof_ir(current_goal={
        "goal_type": "ambient",
        "active_goal_preview": (
            "Current goal\n"
            "------------------------------------------------------------------------\n"
            "forall (sR : block), sR \\in dBlock => sR = sR"
        ),
        "parsed_goal": {
            "goal_type": "ambient",
            "ambient_shape": "logical",
        },
    })

    assert ir["candidate_menu"][0]["tactic"] == "move=> sR H."


def test_ambient_logic_exports_close_recommendations() -> None:
    ir = build_proof_ir(current_goal={
        "goal_type": "ambient",
        "active_goal_preview": (
            "Current goal\n"
            "------------------------------------------------------------------------\n"
            "x = x"
        ),
        "parsed_goal": {
            "goal_type": "ambient",
            "ambient_shape": "logical",
        },
    })

    # The ambient close palette (`auto => />.`, `ambient_simplify`/`simplify`,
    # `ambient_smt`/`smt().`) was hardcoded bare-tactic GUIDANCE, so none of it is
    # surfaced in the menu now.
    menu_ids = [item["id"] for item in ir["candidate_menu"]]
    assert "ambient_simplify" not in menu_ids
    assert "ambient_smt" not in menu_ids
    assert "auto => />." not in {item["tactic"] for item in ir["candidate_menu"]}


def test_pr_eq_without_rewrite_handle_gets_byequiv_bridge() -> None:
    ir = build_proof_ir(current_goal={
        "goal_type": "probability",
        "parsed_goal": {
            "goal_type": "probability",
            "prob_form": "eq",
            "lhs_game": "G",
            "rhs_game": "G'",
        },
    })

    # The pr layer classification is a fact and stays; the `byequiv_bridge`
    # lowering rendered a bare hardcoded `byequiv => //.` (move GUIDANCE) and is
    # now dropped from the menu.
    assert ir["current_layer"] == "pr"
    assert [
        item for item in ir["candidate_menu"]
        if item["id"] == "byequiv_bridge"
    ] == []
    assert "byequiv => //." not in {
        item["tactic"] for item in ir["candidate_menu"]
    }


def test_prhl_module_gets_proc_candidate() -> None:
    ir = build_proof_ir(current_goal={
        "goal_type": "equiv",
        "parsed_goal": {
            "goal_type": "equiv",
            "lhs_proc": "O(P).enc",
            "rhs_proc": "O(P').enc",
        },
    })

    assert ir["current_layer"] == "prhl_module"
    assert ir["phase"]["legality"]["proc_open"]["status"] == "preferred"
    assert ir["candidate_menu"][0]["id"] == "proc_open"
    assert ir["candidate_menu"][0]["tactic"] == "proc."


def test_phoare_entry_gets_proc_before_wp() -> None:
    ir = build_proof_ir(current_goal={
        "goal_type": "phoare",
        "parsed_goal": {"goal_type": "phoare"},
    })

    assert ir["current_layer"] == "procedure_entry"
    assert ir["candidate_menu"][0]["id"] == "proc_open"
    assert ir["candidate_menu"][0]["tactic"] == "proc."
    assert all(item["id"] != "wp_sp_seq" for item in ir["candidate_menu"])


def test_synchronized_prhl_residue_gets_auto_not_proc() -> None:
    ir = build_proof_ir(current_goal={
        "goal_type": "pRHL",
        "active_goal_preview": (
            "Current goal\n\n"
            "&1 (left ) : {i : int} [programs are in sync]\n"
            "&2 (right) : {i : int}\n"
            "\npre = true\npost = i{1} = i{2}"
        ),
        "parsed_goal": {
            "goal_type": "pRHL",
            "left_statements": [],
            "right_statements": [],
        },
    })

    # The residue layer classification and the ambient-close/proc-open phase
    # legality are facts and stay. The `residual_prhl_close` menu item rendered a
    # bare hardcoded `auto.` (move GUIDANCE) and is now dropped.
    assert ir["current_layer"] == "verification_residue"
    assert ir["phase"]["legality"]["ambient_close"]["status"] == "preferred"
    assert ir["phase"]["legality"]["proc_open"]["status"] == "avoid"
    assert [
        item for item in ir["candidate_menu"]
        if item["id"] == "residual_prhl_close"
    ] == []
    assert "auto." not in {item["tactic"] for item in ir["candidate_menu"]}


def test_current_goal_equiv_hypothesis_is_callable_handle() -> None:
    ir = build_proof_ir(current_goal={
        "goal_type": "pRHL",
        "active_goal_preview": (
            "Current goal\n\n"
            "Hf: equiv[ P.f  ~ P'.f :\n"
            "            arg{1} = arg{2} ==> ={res}]\n"
            "------------------------------------------------------------------------\n"
            "&1 (left) : {s : block}\n"
            "&2 (right) : {s : block}\n"
        ),
        "parsed_goal": {
            "goal_type": "pRHL",
            "left_statements": [{
                "pos": 1,
                "pos_path": "1",
                "type": "CALL",
                "text": "s <@ P.f(x);",
                "procedure": "P.f",
            }],
            "right_statements": [{
                "pos": 1,
                "pos_path": "1",
                "type": "CALL",
                "text": "s <@ P'.f(x);",
                "procedure": "P'.f",
            }],
        },
    })

    handles = ir["resources"]["handles"]["callable_lemmas"]
    assert handles[0]["lemma"] == "Hf"
    assert handles[0]["source"] == "current_goal_hypothesis"
    assert handles[0]["callable_now"] is True
    assert handles[0]["call_candidate_kind"] == "direct_current_call"
    resolved = ir["resources"]["name_resolution"]["items"][0]
    assert resolved["resolution_status"] == "resolved_goal_hypothesis"
    assert resolved["exact_signature_known"] is True
    call_candidate = [
        item for item in ir["candidate_menu"]
        if item["id"] == "call_Hf"
    ][0]
    assert call_candidate["tactic"] == "call Hf."
    assert call_candidate["action_type"] == "probe_tactic"


def test_phase_legality_marks_inline_all_avoid_with_live_handles() -> None:
    recs = [{
        "id": "try.inline_all",
        "producer": "try",
        "action": "inline *.",
        "action_type": "runnable_tactic",
        "confidence": "verified",
        "metadata": {"epistemic_status": "daemon_probe_accepted"},
    }]
    ir = build_proof_ir(
        current_goal={
            "goal_type": "pRHL",
            "parsed_goal": {
                "goal_type": "pRHL",
                "left_statements": [{
                    "pos": 1,
                    "type": "CALL",
                    "text": "x <@ M.f();",
                    "procedure": "M.f",
                }],
                "right_statements": [],
                "call_equiv_candidates": {"M.f": ["M_f_equiv"]},
            },
        },
        external_recommendations=recs,
    )

    assert ir["phase"]["legality"]["inline_all"]["status"] == "avoid"
    candidate = ir["resources"]["external_candidates"][0]
    assert candidate["tactic_family"] == "inline_all"
    assert candidate["action_type"] == "avoid_action"
    assert candidate["legality"]["status"] == "avoid"
    assert candidate["cost"] == "expensive"
    assert candidate["cost_factors"]["lost_handles"] == 1
    assert candidate["cost_factors"]["lost_callable_lemmas"] == 1


def test_proof_ir_resolves_local_call_handle_signature() -> None:
    context = """\
local module L = { proc f() = { return witness; } }.
local module R = { proc f() = { return witness; } }.
local equiv M_f_equiv :
  L.f ~ R.f : true ==> ={res}.
proof. by trivial. qed.
"""
    with tempfile.TemporaryDirectory() as td:
        session = Path(td)
        (session / "context.ec").write_text(context, encoding="utf-8")
        ir = build_proof_ir(
            session_dir=session,
            current_goal={
                "goal_type": "pRHL",
                "parsed_goal": {
                    "goal_type": "pRHL",
                    "post": "post = ={res}",
                    "left_statements": [{
                        "pos": 1,
                        "type": "CALL",
                        "text": "x <@ L.f();",
                        "procedure": "L.f",
                    }],
                    "right_statements": [],
                    "call_equiv_candidates": {"L.f": ["M_f_equiv"]},
                },
            },
        )

    name_resolution = ir["resources"]["name_resolution"]
    assert name_resolution["summary"]["resolved"] == 1
    item = name_resolution["items"][0]
    assert item["resolution_status"] == "resolved_local_declaration"
    assert item["exact_signature_known"] is True
    assert item["procedure_match"] == "lhs"
    call_candidate = [
        x for x in ir["candidate_menu"]
        if x["id"] == "call_M_f_equiv"
    ][0]
    assert call_candidate["name_resolution"]["resolution_status"] == (
        "resolved_local_declaration"
    )
    assert "exact signature" in call_candidate["preconditions"][-1]


def test_source_generic_equiv_lemma_attaches_to_matching_call_site() -> None:
    source = """\
lemma CBC_Oracle_enc_eq (P <: PRF) (P' <: PRF) (I: (glob P) -> (glob P') -> bool):
  equiv [P.f ~ P'.f: true ==> true] =>
  equiv [CBC_Oracle(P).enc ~ CBC_Oracle(P').enc:
           ={p} /\\ I (glob P){1} (glob P'){2}
        ==> ={res} /\\ I (glob P){1} (glob P'){2}].
proof. by trivial. qed.
"""
    with tempfile.TemporaryDirectory() as td:
        session = Path(td)
        src = session / "SourceTarget.ec"
        src.write_text(source, encoding="utf-8")
        (session / "context.ec").write_text("", encoding="utf-8")
        (session / "session_meta.json").write_text(
            json.dumps({"file": str(src), "lemma": "target"}),
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
                        "text": "c <@ CBC_Oracle(F).enc(p);",
                        "procedure": "CBC_Oracle(F).enc",
                    }],
                    "right_statements": [{
                        "pos": 1,
                        "type": "CALL",
                        "text": "c <@ CBC_Oracle(DoubleQuery(F)).enc(p);",
                        "procedure": "CBC_Oracle(DoubleQuery(F)).enc",
                    }],
                },
            },
        )

    handles = ir["resources"]["handles"]["callable_lemmas"]
    assert any(handle["lemma"] == "CBC_Oracle_enc_eq" for handle in handles)
    handle = [h for h in handles if h["lemma"] == "CBC_Oracle_enc_eq"][0]
    assert handle["callable_now"] is True
    assert handle["call_candidate_kind"] == "source_lookup_landmark"
    assert [
        item for item in ir["candidate_menu"]
        if item["id"] == "sig_CBC_Oracle_enc_eq"
    ]
    assert not [
        item for item in ir["candidate_menu"]
        if item["id"] == "call_CBC_Oracle_enc_eq"
    ]


def test_matching_equiv_lemma_surfaces_exact_closer_before_proc() -> None:
    source = """\
lemma CBC_Oracle_enc_eq (P <: PRF) (P' <: PRF) (I: (glob P) -> (glob P') -> bool):
  equiv [P.f ~ P'.f: true ==> true] =>
  equiv [CBC_Oracle(P).enc ~ CBC_Oracle(P').enc:
           true ==> true].
proof. by trivial. qed.
"""
    goal = (
        "Current goal\n\n"
        "P_f_eq : equiv [P.f ~ P'.f: true ==> true]\n"
        "------------------------------------------------------------------------\n"
        "pre = true\n\n"
        "  CBC_Oracle(P).enc ~ CBC_Oracle(P').enc\n\n"
        "post = true\n"
    )
    with tempfile.TemporaryDirectory() as td:
        session = Path(td)
        src = session / "SourceTarget.ec"
        src.write_text(source, encoding="utf-8")
        (session / "session_meta.json").write_text(
            json.dumps({"file": str(src), "lemma": "target"}),
            encoding="utf-8",
        )
        ir = build_proof_ir(
            session_dir=session,
            current_goal={
                "goal_type": "pRHL",
                "active_goal_preview": goal,
                "parsed_goal": {
                    "goal_type": "pRHL",
                    "suggested_tactics": ["proc."],
                },
            },
        )

    exact = [
        item for item in ir["candidate_menu"]
        if item["id"].startswith("equiv_exact_CBC_Oracle_enc_eq")
    ][0]
    assert exact["tactic"] == "exact/(CBC_Oracle_enc_eq P P' I P_f_eq)."
    assert exact["action_type"] == "probe_tactic"


def test_ambient_lossless_closer_uses_module_proc_convention() -> None:
    with tempfile.TemporaryDirectory() as td:
        session = Path(td)
        (session / "context.ec").write_text(
            "axiom A_forge_ll (O <: Oracles): islossless A(O).forge.\n",
            encoding="utf-8",
        )
        ir = build_proof_ir(
            session_dir=session,
            current_goal={
                "goal_type": "ambient",
                "active_goal_preview": (
                    "Current goal\n\n"
                    "------------------------------------------------------------------------\n"
                    "forall (O <: Oracles), islossless A(O).forge\n"
                ),
                "parsed_goal": {
                    "goal_type": "ambient",
                    "ambient_shape": "logical",
                },
            },
        )

    assert any(
        item["tactic"] == "exact: A_forge_ll."
        for item in ir["candidate_menu"]
    )


def test_invariant_skeleton_from_prhl_postcondition() -> None:
    ir = build_proof_ir(current_goal={
        "goal_type": "pRHL",
        "parsed_goal": {
            "goal_type": "pRHL",
            "post": "={Mem.k, Mem.log, RO.m} /\\ StLSke.gs{1} = RO.m{2}",
            "left_statements": [{
                "pos": 1,
                "type": "CALL",
                "text": "c <@ L.enc(k);",
                "procedure": "L.enc",
                "vars_read": ["k", "p"],
            }],
            "right_statements": [{
                "pos": 1,
                "type": "CALL",
                "text": "c <@ R.enc(k);",
                "procedure": "R.enc",
                "vars_read": ["k"],
            }],
        },
    })

    skeleton = ir["resources"]["invariant_skeleton"]
    assert skeleton["available"] is True
    assert skeleton["shared_equalities"] == ["Mem.k", "Mem.log", "RO.m"]
    assert skeleton["dataflow_equalities"] == ["k"]
    assert skeleton["relational_atoms"] == ["StLSke.gs{1} = RO.m{2}"]
    assert skeleton["suggested_invariant"] == (
        "={Mem.k, Mem.log, RO.m, k} /\\ StLSke.gs{1} = RO.m{2}"
    )
    assert skeleton["live_reads"]["left"] == ["k", "p"]
    assert "call_invariant_skeleton" in [
        item["id"] for item in ir["candidate_menu"]
    ]


def test_call_invariant_skeleton_surfaces_live_fact_coverage() -> None:
    ir = build_proof_ir(current_goal={
        "goal_type": "pRHL",
        "parsed_goal": {
            "goal_type": "pRHL",
            "pre": (
                "pre = k{1} = Mem.k{1} /\\ "
                "Mem.k{1} = Block.k{2}"
            ),
            "post": "post = ={n, result} /\\ c0{1} = c{2}",
            "left_statements": [{
                "pos": 1,
                "type": "CALL",
                "text": "x <@ L.f(k, n, c0);",
                "procedure": "L.f",
                "vars_read": ["k", "n", "c0"],
            }],
            "right_statements": [{
                "pos": 1,
                "type": "CALL",
                "text": "x <@ R.f(Block.k, n, c);",
                "procedure": "R.f",
                "vars_read": ["Block.k", "n", "c"],
            }],
        },
    })

    skeleton = ir["resources"]["invariant_skeleton"]
    assert "k{1} = Mem.k{1}" in skeleton["carried_precondition_atoms"]
    item = [
        candidate for candidate in ir["candidate_menu"]
        if candidate["id"] == "call_invariant_skeleton"
    ][0]
    coverage = item["cost_factors"]["live_fact_coverage"]
    assert coverage["available"] is True
    assert coverage["coverage_label"] in {
        "covers_visible_live_facts",
        "partial_visible_live_coverage",
    }
    assert "n" in coverage["required_post_live_vars"]
    assert "strategy_boundary" in coverage
    preview = [
        candidate for candidate in ir["candidate_menu"]
        if candidate["id"] == "call_invariant_obligation_preview"
    ][0]
    assert preview["action_type"] == "inspection_action"
    assert preview["tactic"].startswith("-call-subgoals -c ")
    assert preview["cost_factors"]["live_fact_coverage"]["available"] is True
    menu_ids = [item["id"] for item in ir["candidate_menu"]]
    assert "call_invariant_obligation_preview" in menu_ids
    assert "call_invariant_skeleton" in menu_ids


def test_invariant_skeleton_filters_parser_tokens_from_code_reads() -> None:
    ir = build_proof_ir(current_goal={
        "goal_type": "pRHL",
        "parsed_goal": {
            "goal_type": "pRHL",
            "post": "post = c{1} = c{2} /\\ I (glob P){1} (glob P'){2}",
            "left_statements": [{
                "pos": 1,
                "type": "WHILE",
                "text": "while (i < size p) {",
                "vars_read": ["while", "i", "p"],
                "vars_written": [],
            }, {
                "pos": 1,
                "pos_path": "1.1",
                "type": "ASSIGN",
                "text": "pi <- nth witness<:block> p i",
                "vars_read": ["i", "witness", "p", "nth", "block"],
                "vars_written": ["pi"],
            }, {
                "pos": 1,
                "pos_path": "1.2",
                "type": "CALL",
                "text": "s <@ P.f(Block.(-) s pi)",
                "procedure": "P.f",
                "vars_read": ["Block.", "P.f", "pi"],
                "vars_written": ["s"],
            }],
            "right_statements": [{
                "pos": 1,
                "type": "WHILE",
                "text": "while (i < size p) {",
                "vars_read": ["while", "i", "p"],
                "vars_written": [],
            }, {
                "pos": 1,
                "pos_path": "1.1",
                "type": "ASSIGN",
                "text": "pi <- nth witness<:block> p i",
                "vars_read": ["i", "witness", "p", "nth", "block"],
                "vars_written": ["pi"],
            }, {
                "pos": 1,
                "pos_path": "1.2",
                "type": "CALL",
                "text": "s <@ P'.f(Block.(-) s pi)",
                "procedure": "P'.f",
                "vars_read": ["Block.", "P'.f", "pi"],
                "vars_written": ["s"],
            }],
        },
    })

    skeleton = ir["resources"]["invariant_skeleton"]
    assert skeleton["available"] is True
    assert skeleton["relational_atoms"] == [
        "c{1} = c{2}",
        "I (glob P){1} (glob P'){2}",
    ]
    suggested = skeleton["suggested_invariant"]
    for forbidden in ["post =", "while", "witness", "nth", "block", "Block.", "P.f"]:
        assert forbidden not in suggested
    assert "call_invariant_skeleton" not in [
        item["id"] for item in ir["candidate_menu"]
    ]


def test_inline_all_history_marks_call_handles_consumed() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        sess = Path(tmp)
        (sess / "history.ec").write_text(
            "proc.\ninline *.\nwp.\n",
            encoding="utf-8",
        )
        ir = build_proof_ir(
            session_dir=sess,
            current_goal={
                "goal_type": "pRHL",
                "parsed_goal": {
                    "goal_type": "pRHL",
                    "left_statements": [{
                        "pos": 1,
                        "type": "ASSIGN",
                        "text": "x <- y;",
                    }],
                    "right_statements": [{
                        "pos": 1,
                        "type": "ASSIGN",
                        "text": "x <- y;",
                    }],
                },
            },
        )

    assert ir["current_layer"] == "procedure_body"
    assert ir["liveness"]["inline_all_taken"] is True
    assert ir["liveness"]["call_site_handles_consumed"] is True
    assert proof_ir_notes(ir)[0]["code"] == "proof_ir.call_sites_already_lowered"


def test_prior_inline_all_diagnostic_is_suppressed_on_fresh_pr_frontier() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        sess = Path(tmp)
        (sess / "history.ec").write_text(
            "proc.\ninline *.\nwp.\n",
            encoding="utf-8",
        )
        ir = build_proof_ir(
            session_dir=sess,
            current_goal={
                "goal_type": "probability",
                "parsed_goal": {
                    "goal_type": "probability",
                    "prob_form": "eq",
                    "lhs_game": "G0.main()",
                    "rhs_game": "G1.main()",
                },
            },
        )

    assert ir["current_layer"] == "pr"
    assert ir["liveness"]["call_site_handles_consumed"] is True
    assert all(
        note["code"] != "proof_ir.call_sites_already_lowered"
        for note in proof_ir_notes(ir)
    )


def test_failed_call_after_inline_all_gets_resource_diagnostic() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        sess = Path(tmp)
        (sess / "history.ec").write_text(
            "proc.\ninline *.\nwp.\n",
            encoding="utf-8",
        )
        ir = build_proof_ir(
            session_dir=sess,
            proof_state={
                "latest_transition": {
                    "tactic": "call chacha_enc1.",
                    "latest_error": "cannot apply lemma",
                },
            },
            current_goal={
                "goal_type": "pRHL",
                "parsed_goal": {
                    "goal_type": "pRHL",
                    "left_statements": [{
                        "pos": 1,
                        "type": "ASSIGN",
                        "text": "x <- y;",
                    }],
                    "right_statements": [{
                        "pos": 1,
                        "type": "ASSIGN",
                        "text": "x <- y;",
                    }],
                },
            },
        )

    codes = [diag["code"] for diag in ir["diagnostics"]]
    assert "proof_ir.failure.call_site_erased_by_inline_all" in codes
    message = [
        diag["message"]
        for diag in ir["diagnostics"]
        if diag["code"] == "proof_ir.failure.call_site_erased_by_inline_all"
    ][0]
    assert "inline *" in message

    repair = [
        diag["repairs"][0]
        for diag in ir["diagnostics"]
        if diag["code"] == "proof_ir.failure.call_site_erased_by_inline_all"
    ][0]
    assert "Undo to before `inline *`" in repair


def test_failed_call_not_at_frontier_gets_resource_diagnostic() -> None:
    ir = build_proof_ir(
        proof_state={
            "latest_transition": {
                "tactic": "call M_f_equiv.",
                "latest_error": "the given proof-term proves a different judgment",
            },
        },
        current_goal={
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
        },
    )

    diag = ir["diagnostics"][0]
    assert diag["code"] == "proof_ir.failure.call_not_frontier"
    assert "current last-call frontier is a later statement" in diag["reason"]
    assert "wp" in diag["repairs"][0]
    assert diag["evidence"]["frontier_status"] == "requires_cut"


def test_probability_pr_rewrite_stays_at_pr_layer() -> None:
    ir = build_proof_ir(current_goal={
        "goal_type": "probability",
        "parsed_goal": {
            "goal_type": "probability",
            "prob_form": "eq",
            "pr_rewrite_candidates": [{"lemma": "pr_RO_FinRO_D"}],
        },
    })

    assert ir["current_layer"] == "pr"
    assert ir["goal_kind"] == "Pr_eq"
    # The signature lookup is present in the menu; its old rank-0 position was a
    # heuristic inspect-first ordering, removed with the ranker (the menu now
    # keeps structural build order, no preference ranking).
    assert "-where pr_RO_FinRO_D" in {
        item.get("tactic") for item in ir["candidate_menu"]
    }
    rewrite = [
        item for item in ir["candidate_menu"]
        if item["id"] == "rewrite_pr_handle"
    ][0]
    assert rewrite["tactic"] == "rewrite pr_RO_FinRO_D."
    assert rewrite["name_resolution"]["resolution_status"] == "needs_where_lookup"
    # phase carries only factual resource facts now — no prefer/avoid prose.
    assert "prefer" not in ir["phase"]
    assert "avoid" not in ir["phase"]


def test_probability_discovers_imported_pr_bridge_before_name_lookup() -> None:
    with tempfile.TemporaryDirectory() as td:
        session = Path(td)
        (session / "context.ec").write_text(
            "require import ToyBridge.\n",
            encoding="utf-8",
        )
        (session / "session_meta.json").write_text(
            json.dumps({"lemma": "target"}),
            encoding="utf-8",
        )
        (session / "ToyBridge.ec").write_text(
            "axiom pr_lazy_eager &m x (p : bool -> bool):\n"
            "  Pr[MainD(D, RO).distinguish(x) @ &m : p res] =\n"
            "  Pr[MainD(D, FinRO).distinguish(x) @ &m : p res].\n",
            encoding="utf-8",
        )

        ir = build_proof_ir(
            session_dir=session,
            current_goal={
                "goal_type": "probability",
                "active_goal_preview": (
                    "Current goal\n\n"
                    "------------------------------------------------------------------------\n"
                    "Pr[G1.main() @ &m : res] =\n"
                    "Pr[MainD(G2, RO).distinguish() @ &m : res]"
                ),
                "parsed_goal": {
                    "goal_type": "probability",
                    "prob_form": "eq",
                    "lhs_game": "G1",
                    "rhs_game": "MainD",
                },
            },
        )

    handles = ir["resources"]["handles"]
    assert "pr_lazy_eager" in handles["pr_rewrite_candidates"]
    detail = handles["pr_rewrite_candidate_details"][0]
    assert detail["source"] == "imported_theory.pr_rewrite_declaration"
    resolution = ir["resources"]["name_resolution"]
    item = resolution["items"][0]
    assert item["name"] == "pr_lazy_eager"
    assert item["resolution_status"] == "needs_where_lookup"
    assert item["signature_lookup_action"] == "-where pr_lazy_eager"
    assert resolution["lookup_actions"] == ["-where pr_lazy_eager"]
    assert any(
        edge["lemma"] == "pr_lazy_eager"
        for edge in ir["resources"]["pr_path_plan"]["edges"]
    )
    sig_item = [
        item for item in ir["candidate_menu"]
        if item["id"] == "sig_pr_lazy_eager"
    ][0]
    assert sig_item["tactic"] == "-where pr_lazy_eager"
    assert sig_item["action_type"] == "inspection_action"


def test_probability_pr_bridge_ranking_prefers_pair_endpoint_match() -> None:
    with tempfile.TemporaryDirectory() as td:
        session = Path(td)
        (session / "context.ec").write_text(
            "require import ToyBridge.\n",
            encoding="utf-8",
        )
        (session / "ToyBridge.ec").write_text(
            "\n".join([
                "axiom pr_FinRO_FunRO_D &m x (p : bool -> bool):",
                "  Pr[MainD(D, FinRO).distinguish(x) @ &m : p res] =",
                "  Pr[MainD(D, FunRO).distinguish(x) @ &m : p res].",
                "",
                "axiom pr_RO_FinRO_D &m x (p : bool -> bool):",
                "  Pr[MainD(D, RO).distinguish(x) @ &m : p res] =",
                "  Pr[MainD(D, FinRO).distinguish(x) @ &m : p res].",
            ]),
            encoding="utf-8",
        )
        ir = build_proof_ir(
            session_dir=session,
            current_goal={
                "goal_type": "probability",
                "active_goal_preview": (
                    "Current goal\n\n"
                    "------------------------------------------------------------------------\n"
                    "Pr[MainD(G2, RO).distinguish() @ &m : res] = "
                    "Pr[MainD(G2, FinRO).distinguish() @ &m : res]"
                ),
                "parsed_goal": {
                    "goal_type": "probability",
                    "prob_form": "eq",
                    "lhs_game": "MainD(G2, RO)",
                    "rhs_game": "MainD(G2, FinRO)",
                },
            },
        )

    details = ir["resources"]["handles"]["pr_rewrite_candidate_details"]
    assert [item["lemma"] for item in details[:2]] == [
        "pr_RO_FinRO_D",
        "pr_FinRO_FunRO_D",
    ]


def test_probability_wrapper_bridge_normalizes_experiment_endpoint() -> None:
    with tempfile.TemporaryDirectory() as td:
        session = Path(td)
        (session / "context.ec").write_text(
            "require import ToyBridge.\n",
            encoding="utf-8",
        )
        (session / "ToyBridge.ec").write_text(
            "\n".join([
                "axiom pr_RO_FinRO_D &m x (p : bool -> bool):",
                "  Pr[MainD(D, RO).distinguish(x) @ &m : p res] =",
                "  Pr[MainD(D, FinRO).distinguish(x) @ &m : p res].",
            ]),
            encoding="utf-8",
        )
        ir = build_proof_ir(
            session_dir=session,
            current_goal={
                "goal_type": "probability",
                "active_goal_preview": (
                    "Current goal\n\n"
                    "------------------------------------------------------------------------\n"
                    "Pr[MainD(G2, FinRO).distinguish() @ &m : res] =\n"
                    "Pr[Indist.Distinguish(D(A), IndRO).game() @ &m : res]"
                ),
                "parsed_goal": {
                    "goal_type": "probability",
                    "prob_form": "eq",
                    "lhs_game": "MainD(G2, FinRO)",
                    "rhs_game": "Indist.Distinguish(D(A), IndRO)",
                },
            },
        )

    candidates = ir["resources"]["handles"]["pr_wrapper_bridge_candidates"]
    assert candidates
    tactic = candidates[0]["tactic"]
    assert "Indist.Distinguish(D(A), IndRO).game()" in tactic
    assert "MainD(G2, RO).distinguish()" in tactic
    assert "distinguish(())" not in tactic
    assert "by byequiv => //; proc; inline *; sim." in tactic
    menu_item = [
        item for item in ir["candidate_menu"]
        if item["id"] == "pr_wrapper_bridge_0"
    ][0]
    assert menu_item["tactic_family"] == "pr_path_plan"
    assert menu_item["action_type"] == "probe_tactic"


def test_typed_bridge_menu_surfaces_live_wrapper_even_without_complete_path() -> None:
    tactic = (
        "have -> : Pr[Indist.Distinguish(D(A), IndRO).game() @ &m : res] = "
        "Pr[MainD(G2, RO).distinguish() @ &m : res] "
        "by byequiv => //; proc; inline *; sim."
    )
    items = _pr_typed_bridge_chain_menu_items({
        "pr_typed_bridge_frontend": {
            "wrapper_bridges": [{
                "tactic": tactic,
                "lhs_game": "Indist.Distinguish(D(A), IndRO)",
                "rhs_game": "MainD(G2, RO)",
                "adapter_module": "G2",
                "bridge_lemma": "pr_RO_FinRO_D",
                "reason": "Normalize wrapper endpoint before the typed Pr rewrite.",
            }],
        },
        "pr_path_plan": {
            "edges": [{
                "edge_kind": "synthetic_bridge",
                "action_hint": tactic,
            }],
        },
    })

    assert items
    assert items[0]["tactic"] == tactic
    assert items[0]["tactic_family"] == "pr_path_plan"
    assert items[0]["action_type"] == "strategy_hint"
    assert items[0]["obligation_completeness"] == "partial"
    assert (
        items[0]["cost_factors"]["path_status"]
        == "frontier_bridge_without_complete_path"
    )


def test_probability_external_pr_bridge_lookup_does_not_block_byequiv() -> None:
    ir = build_proof_ir(
        current_goal={
            "goal_type": "probability",
            "parsed_goal": {
                "goal_type": "probability",
                "prob_form": "eq",
                "lhs_game": "CCA_game(A, RealOrcls(ChaChaPoly))",
                "rhs_game": "Indist.Distinguish(D(A), IndBlock)",
            },
        },
        external_recommendations=[{
            "id": "auto_pivot.0",
            "producer": "AUTO-PIVOT",
            "action": "-where pr_CCP_OCCP",
            "action_type": "inspection_action",
            "confidence": "medium",
            "metadata": {"tag": "DISJOINT"},
        }],
    )

    menu = ir["candidate_menu"]
    assert menu[0]["id"] == "sig_external_pr_bridge_pr_CCP_OCCP"
    assert menu[0]["tactic"] == "-where pr_CCP_OCCP"
    assert menu[0]["action_type"] == "strategy_hint"
    assert not any(item["id"] == "pr_external_bridge_frontier" for item in menu)
    # `byequiv_bridge` rendered a bare hardcoded `byequiv => //.` (move GUIDANCE),
    # so it is now dropped — the external lookup no longer competes with it at all.
    assert not any(item["id"] == "byequiv_bridge" for item in menu)
    assert not any(item["tactic"] == "byequiv => //." for item in menu)


def test_recent_pr_rewrite_is_not_immediately_recommended_again() -> None:
    ir = build_proof_ir(
        current_goal={
            "goal_type": "probability",
            "parsed_goal": {
                "goal_type": "probability",
                "prob_form": "eq",
                "pr_rewrite_candidates": ["pr_CCP_OCCP"],
            },
        },
        proof_state={
            "latest_transition": {
                "tactic": "rewrite -(OpCCinit.pr_CCP_OCCP I_stateless G1 &m).",
            },
        },
    )

    actions = [item["tactic"] for item in ir["candidate_menu"]]
    assert "rewrite pr_CCP_OCCP." not in actions
    assert "-where pr_CCP_OCCP" not in actions
    # The byequiv lowering fallback was a bare hardcoded `byequiv => //.` (move
    # GUIDANCE) and is now dropped, so it is no longer offered here either.
    assert "byequiv => //." not in actions


def test_aligned_if_frontier_gets_if_transform_before_nested_call() -> None:
    menu = _candidate_menu(
        "call_site",
        "pRHL",
        {},
        {},
        program_ir={
            "frontier": {
                "by_side": {
                    "left": {"kind": "IF", "statement_id": "left:1"},
                    "right": {"kind": "IF", "statement_id": "right:1"},
                },
            },
        },
    )

    assert any(item["id"] == "if_frontier" for item in menu)


def test_compound_pr_lemma_is_not_simple_rewrite_candidate() -> None:
    with tempfile.TemporaryDirectory() as td:
        session = Path(td)
        (session / "context.ec").write_text(
            "\n".join([
                "local lemma step2_3 &m :",
                "  Pr[Game0.main() @ &m : res] + Pr[Bad0.main() @ &m : res] =",
                "  Pr[Game1.main() @ &m : res] + Pr[Bad1.main() @ &m : res].",
            ]),
            encoding="utf-8",
        )
        ir = build_proof_ir(
            session_dir=session,
            current_goal={
                "goal_type": "probability",
                "active_goal_preview": (
                    "Current goal\n\n"
                    "------------------------------------------------------------------------\n"
                    "Pr[Game0.main() @ &m : res] = Pr[Game1.main() @ &m : res]"
                ),
                "parsed_goal": {
                    "goal_type": "probability",
                    "prob_form": "eq",
                    "lhs_game": "Game0",
                    "rhs_game": "Game1",
                },
            },
        )

    assert "step2_3" not in ir["resources"].get("pr_rewrite_candidates", [])
    assert all(item["tactic"] != "rewrite step2_3." for item in ir["candidate_menu"])


def test_native_ast_search_query_is_proof_ir_frontend_action() -> None:
    ir = build_proof_ir(current_goal={
        "goal_type": "ambient",
        "active_goal_preview": (
            "Current goal\n\n"
            "------------------------------------------------------------------------\n"
            "x \\in take n xs => size (take n xs) <= size xs"
        ),
        "parsed_goal": {
            "goal_type": "ambient",
            "ambient_shape": "implication",
        },
    })

    native = ir["resources"]["handles"]["native_ast_search"]
    assert native["suggested_queries"][0]["query"] == "take mem"
    search_item = [
        item for item in ir["candidate_menu"]
        if item["id"] == "native_ast_search_0"
    ][0]
    assert search_item["tactic"] == "-search-skeleton 'take mem'"
    assert search_item["action_type"] == "inspection_action"
    assert search_item["tactic_family"] == "native_ast_search"


def test_pr_bound_goal_prefers_bound_search_over_unresolved_bridge_lookup() -> None:
    ir = build_proof_ir(current_goal={
        "goal_type": "probability",
        "active_goal_preview": (
            "Current goal\n\n"
            "------------------------------------------------------------------------\n"
            "Pr[Game(RO).main() @ &m : res \\/ Bad.flag] <= q%r * eps"
        ),
        "parsed_goal": {
            "goal_type": "probability",
            "prob_form": "ineq",
            "pr_rewrite_candidates": [{"lemma": "pr_RO_split"}],
        },
    })

    native = [
        item for item in ir["candidate_menu"]
        if item["id"] == "native_ast_search_0"
    ][0]
    lookup = [
        item for item in ir["candidate_menu"]
        if item["id"] == "sig_pr_RO_split"
    ][0]
    rewrite = [
        item for item in ir["candidate_menu"]
        if item["id"] == "rewrite_pr_handle"
    ][0]
    assert native["tactic"] == "-search-skeleton '( <= ) mu'"
    assert "upper-bound" in native["why"]
    assert lookup["cost"] == "expensive"
    assert rewrite["cost"] == "expensive"
    assert rewrite["action_type"] == "strategy_hint"


def test_native_ast_search_hits_become_where_candidates() -> None:
    with tempfile.TemporaryDirectory() as td:
        session = Path(td)
        tool_views = session / "tool_views"
        tool_views.mkdir()
        (tool_views / "search_skeleton_take_mem.json").write_text(
            json.dumps({
                "schema_version": 1,
                "tool": "search-skeleton",
                "kind": "tool_view",
                "ok": True,
                "evidence": {
                    "context": [{
                        "id": "context.search-skeleton.query",
                        "query": {"query": "take mem"},
                    }],
                    "raw": [],
                },
                "debug": {
                    "legacy_text": (
                        "[SKELETON-HITS] `search take mem` -> 1 lemma(s)\n\n"
                        "lemma mem_take (x : 'a) n xs:\n"
                        "  x \\in take n xs => x \\in xs.\n"
                    ),
                },
            }),
            encoding="utf-8",
        )
        ir = build_proof_ir(
            session_dir=session,
            current_goal={
                "goal_type": "ambient",
                "active_goal_preview": (
                    "Current goal\n\n"
                    "------------------------------------------------------------------------\n"
                    "x \\in take n xs => x \\in xs"
                ),
                "parsed_goal": {
                    "goal_type": "ambient",
                    "ambient_shape": "implication",
                },
            },
        )

    native = ir["resources"]["handles"]["native_ast_search"]
    assert native["observed_queries"][0]["query"] == "take mem"
    assert native["hits"][0]["name"] == "mem_take"
    assert native["suggested_queries"] == []
    where_item = [
        item for item in ir["candidate_menu"]
        if item["id"] == "native_ast_hit_mem_take"
    ][0]
    assert where_item["tactic"] == "-where mem_take"


def test_native_ast_search_ignores_hits_from_irrelevant_queries() -> None:
    with tempfile.TemporaryDirectory() as td:
        session = Path(td)
        tool_views = session / "tool_views"
        tool_views.mkdir()
        (tool_views / "search_skeleton_mu.json").write_text(
            json.dumps({
                "schema_version": 1,
                "tool": "search-skeleton",
                "kind": "tool_view",
                "ok": True,
                "evidence": {
                    "context": [{
                        "id": "context.search-skeleton.query",
                        "query": {"query": "mu"},
                    }],
                    "raw": [],
                },
                "debug": {
                    "legacy_text": (
                        "[SKELETON-HITS] `search mu` -> 1 lemma(s)\n\n"
                        "lemma mu_mem_le ['a]:\n"
                        "  forall (s : 'a fset) (d : 'a Distr.distr) (bd : real),\n"
                        "    mu d (mem s) <= (card s)%r * bd.\n"
                    ),
                },
            }),
            encoding="utf-8",
        )
        ir = build_proof_ir(
            session_dir=session,
            current_goal={
                "goal_type": "probability",
                "active_goal_preview": (
                    "Current goal\n\n"
                    "------------------------------------------------------------------------\n"
                    "`|Pr[G0.main() @ &m : res] - Pr[G1.main() @ &m : res]| <= "
                    "Pr[Bad.main() @ &m : bad]"
                ),
                "parsed_goal": {
                    "goal_type": "probability",
                    "prob_form": "adv_diff_ineq",
                },
            },
        )

    native = ir["resources"]["handles"]["native_ast_search"]
    assert native["hits"] == []
    assert [item["query"] for item in native["suggested_queries"]] == ["( <= ) mu"]


def test_proof_ir_consumes_sig_tool_view_for_pr_rewrite() -> None:
    sig_output = """\
=== Signature of 'pr_RO_FinRO_D' (1 match) ===

-- PROM.ec:10 (lemma)
lemma pr_RO_FinRO_D (A <: Adv) &m :
  Pr[RO(A).main() @ &m : res] = Pr[FinRO(A).main() @ &m : res].

Usage: apply (pr_RO_FinRO_D <module_arg1> <module_arg2> ... &m).
"""
    with tempfile.TemporaryDirectory() as td:
        session = Path(td)
        (session / "context.ec").write_text(
            "declare module A <: Adv.\n",
            encoding="utf-8",
        )
        tool_views = session / "tool_views"
        tool_views.mkdir()
        (tool_views / "sig_pr.json").write_text(
            json.dumps({
                "schema_version": 1,
                "tool": "sig",
                "kind": "tool_view",
                "ok": True,
                "proof_state": {"status": "open"},
                "guidance": {"recommendations": []},
                "evidence": {
                    "context": [{
                        "id": "context.sig.query",
                        "query": {"name": "pr_RO_FinRO_D"},
                    }],
                    "raw": [],
                },
                "notes": [],
                "errors": [],
                "debug": {"legacy_text": sig_output},
            }),
            encoding="utf-8",
        )
        ir = build_proof_ir(
            session_dir=session,
            current_goal={
                "goal_type": "probability",
                "parsed_goal": {
                    "goal_type": "probability",
                    "prob_form": "eq",
                    "event": "Pr[RO(A).main() @ &m : res]",
                    "pr_rewrite_candidates": [{"lemma": "pr_RO_FinRO_D"}],
                },
            },
        )

    assert ir["resources"]["name_resolution"]["summary"]["resolved"] == 1
    rewrite = [
        item for item in ir["candidate_menu"]
        if item["id"] == "rewrite_pr_handle"
    ][0]
    assert rewrite["name_resolution"]["resolution_status"] == (
        "resolved_signature_lookup"
    )
    assert rewrite["name_resolution"]["parameter_slots"] == [{
        "kind": "module_arg",
        "name": "A",
        "placeholder": "<A_module>",
    }, {
        "kind": "memory_arg",
        "name": "&m",
        "placeholder": "<m>",
    }]
    binding = rewrite["instantiation_binding"]
    assert binding["instantiated_templates"][0]["tactic"] == (
        "rewrite (pr_RO_FinRO_D A &m)."
    )
    assert binding["slots"][0]["candidates"][0]["value"] == "A"
    bound_candidates = [
        item for item in ir["candidate_menu"]
        if item["tactic_family"] == "instantiated_template"
    ]
    assert bound_candidates[0]["tactic"] == "rewrite (pr_RO_FinRO_D A &m)."
    assert bound_candidates[0]["action_type"] == "probe_tactic"
    assert bound_candidates[0]["cost_factors"]["bound_tactic_family"] == "rewrite"
    assert "exact signature" in rewrite["preconditions"][0]
    assert all(item["tactic_family"] != "signature_lookup" for item in ir["candidate_menu"])


def test_proof_ir_instantiates_section_exported_pr_rewrite_shape() -> None:
    where_output = """\
[WHERE-HIT] pr_RO_FinRO_D  (kind: lemma)
* In [lemmas or axioms]:

lemma pr_RO_FinRO_D:
  (forall (_ : nonce * C.counter), is_lossless dblock) =>
  forall (D0(G : RO) <: FinRO_Distinguisher{-RO, -FRO}) &m (x : unit)
    (p : bool -> bool),
    Pr[MainD(D0, RO).distinguish(x) @ &m : p res] =
    Pr[MainD(D0, FinRO).distinguish(x) @ &m : p res].
"""
    with tempfile.TemporaryDirectory() as td:
        session = Path(td)
        tool_views = session / "tool_views"
        tool_views.mkdir()
        (tool_views / "where_pr.json").write_text(
            json.dumps({
                "schema_version": 1,
                "tool": "where",
                "kind": "tool_view",
                "ok": True,
                "proof_state": {"status": "open"},
                "guidance": {"recommendations": []},
                "evidence": {
                    "context": [{
                        "id": "context.where.query",
                        "query": {"name": "pr_RO_FinRO_D"},
                    }],
                    "raw": [],
                },
                "notes": [],
                "errors": [],
                "debug": {"legacy_text": where_output},
            }),
            encoding="utf-8",
        )
        ir = build_proof_ir(
            session_dir=session,
            current_goal={
                "goal_type": "probability",
                "active_goal_preview": (
                    "Current goal\n\n"
                    "------------------------------------------------------------------------\n"
                    "Pr[MainD(G2, RO).distinguish() @ &m : res] = "
                    "Pr[MainD(G2, FinRO).distinguish() @ &m : res]"
                ),
                "parsed_goal": {
                    "goal_type": "probability",
                    "prob_form": "eq",
                    "lhs_game": "MainD(G2, RO)",
                    "rhs_game": "MainD(G2, FinRO)",
                    "pr_rewrite_candidates": [{"lemma": "pr_RO_FinRO_D"}],
                },
            },
        )

    bound = [
        item for item in ir["candidate_menu"]
        if item["id"].startswith("instantiated_pr_RO_FinRO_D")
    ][0]
    assert bound["tactic"] == (
        "rewrite (pr_RO_FinRO_D _ G2 &m () (fun x => x)) /=."
    )
    elaboration = bound["pr_elaboration"]
    assert elaboration["endpoint_argument_separation"][0]["selected_value"] == "()"
    assert elaboration["endpoint_argument_separation"][0]["concrete_endpoint"] == (
        "MainD(G2, RO).distinguish()"
    )
    assert elaboration["diagnostics"][0]["avoid"] == (
        "MainD(G2, RO).distinguish(())"
    )
    assert any(
        "lemma argument" in precondition
        for precondition in bound["preconditions"]
    )
    resolution = ir["resources"]["name_resolution"]["items"][0]
    assert resolution["parameter_slots"][0]["kind"] == "proof_arg"


def test_instantiated_pr_rewrite_ranking_preserves_endpoint_frontend_order() -> None:
    where_ro_finro = """\
[WHERE-HIT] pr_RO_FinRO_D  (kind: lemma)
* In [lemmas or axioms]:

lemma pr_RO_FinRO_D:
  (forall (_ : nonce * C.counter), is_lossless dblock) =>
  forall (D0(G : RO) <: FinRO_Distinguisher{-RO, -FRO}) &m (x : unit)
    (p : bool -> bool),
    Pr[MainD(D0, RO).distinguish(x) @ &m : p res] =
    Pr[MainD(D0, FinRO).distinguish(x) @ &m : p res].
"""
    where_finro_funro = """\
[WHERE-HIT] pr_FinRO_FunRO_D  (kind: lemma)
* In [lemmas or axioms]:

lemma pr_FinRO_FunRO_D:
  (forall (_ : nonce * C.counter), is_lossless dblock) =>
  forall (D0(G : RO) <: FinRO_Distinguisher{-RO, -FRO}) &m (x : unit)
    (p : bool -> bool),
    Pr[MainD(D0, FinRO).distinguish(x) @ &m : p res] =
    Pr[MainD(D0, FunRO).distinguish(x) @ &m : p res].
"""
    with tempfile.TemporaryDirectory() as td:
        session = Path(td)
        _write_where_tool_view(session, "pr_RO_FinRO_D", where_ro_finro)
        _write_where_tool_view(session, "pr_FinRO_FunRO_D", where_finro_funro)
        ir = build_proof_ir(
            session_dir=session,
            current_goal={
                "goal_type": "probability",
                "active_goal_preview": (
                    "Current goal\n\n"
                    "------------------------------------------------------------------------\n"
                    "Pr[Indist.Distinguish(D(A), IndRO).game() @ &m : res] = "
                    "Pr[MainD(G2, FinRO).distinguish() @ &m : "
                    "(fun (b : bool) => b) res]"
                ),
                "parsed_goal": {
                    "goal_type": "probability",
                    "prob_form": "eq",
                    "lhs_game": "Indist.Distinguish(D(A), IndRO)",
                    "rhs_game": "MainD(G2, FinRO)",
                    "pr_rewrite_candidates": [
                        {"lemma": "pr_RO_FinRO_D"},
                        {"lemma": "pr_FinRO_FunRO_D"},
                    ],
                },
            },
        )

    bound = [
        item for item in ir["candidate_menu"]
        if item["tactic_family"] == "instantiated_template"
        and item["tactic"].startswith("rewrite (pr_")
    ]
    assert [item["id"] for item in bound[:2]] == [
        "instantiated_pr_RO_FinRO_D_0",
        "instantiated_pr_FinRO_FunRO_D_0",
    ]
    assert bound[0]["cost_factors"]["pr_rewrite_candidate_index"] == 0
    assert bound[1]["cost_factors"]["pr_rewrite_candidate_index"] == 1
    assert bound[0]["cost_factors"]["pr_endpoint_relevance_rank"] == 0
    assert bound[1]["cost_factors"]["pr_endpoint_relevance_rank"] == 0


def test_pr_rewrite_instantiation_is_context_when_endpoint_does_not_match() -> None:
    where_output = """\
[WHERE-HIT] pr_RO_FinRO_D  (kind: lemma)
* In [lemmas or axioms]:

lemma pr_RO_FinRO_D:
  (forall (_ : nonce * C.counter), is_lossless dblock) =>
  forall (D0(G : RO) <: FinRO_Distinguisher{-RO, -FRO}) &m (x : unit)
    (p : bool -> bool),
    Pr[MainD(D0, RO).distinguish(x) @ &m : p res] =
    Pr[MainD(D0, FinRO).distinguish(x) @ &m : p res].
"""
    with tempfile.TemporaryDirectory() as td:
        session = Path(td)
        (session / "context.ec").write_text(
            "\n".join([
                "module G4 (A:Adv, RO:RO) = {",
                "  proc distinguish () = {",
                "    var b;",
                "    b <@ CPA_game(CCA_CPA_Adv(A), RealOrcls(GenChaChaPoly(CCRO(RO)))).main();",
                "    return b;",
                "  }",
                "}.",
            ]),
            encoding="utf-8",
        )
        tool_views = session / "tool_views"
        tool_views.mkdir()
        (tool_views / "where_pr.json").write_text(
            json.dumps({
                "schema_version": 1,
                "tool": "where",
                "kind": "tool_view",
                "ok": True,
                "proof_state": {"status": "open"},
                "guidance": {"recommendations": []},
                "evidence": {
                    "context": [{
                        "id": "context.where.query",
                        "query": {"name": "pr_RO_FinRO_D"},
                    }],
                    "raw": [],
                },
                "notes": [],
                "errors": [],
                "debug": {"legacy_text": where_output},
            }),
            encoding="utf-8",
        )
        ir = build_proof_ir(
            session_dir=session,
            current_goal={
                "goal_type": "probability",
                "active_goal_preview": (
                    "Current goal\n\n"
                    "------------------------------------------------------------------------\n"
                    "Pr[CPA_game(CCA_CPA_Adv(A), RealOrcls(GenChaChaPoly(CCRO(FinRO)))).main() @ &m : res] = "
                    "Pr[Split1.IdealAll.MainD(G8(A), RO_Pair(I1.RO, I2.RO)).distinguish() @ &m : res]"
                ),
                "parsed_goal": {
                    "goal_type": "probability",
                    "prob_form": "eq",
                    "lhs_game": "CPA_game(CCA_CPA_Adv(A), RealOrcls(GenChaChaPoly(CCRO(FinRO))))",
                    "rhs_game": "Split1.IdealAll.MainD(G8(A), RO_Pair(I1.RO, I2.RO))",
                    "pr_rewrite_candidates": [{"lemma": "pr_RO_FinRO_D"}],
                },
            },
        )

    bound = [
        item for item in ir["candidate_menu"]
        if item["id"].startswith("instantiated_pr_RO_FinRO_D")
    ][0]
    assert bound["action_type"] == "strategy_hint"
    assert bound["cost_factors"]["pr_endpoint_match"] == "missing"
    assert any(
        diag["code"] == "pr_elaboration.no_matching_pr_endpoint"
        for diag in bound["pr_elaboration"]["diagnostics"]
    )
    frontend = ir["resources"]["handles"]["pr_typed_bridge_frontend"]
    assert frontend["available"] is True
    bridge = frontend["wrapper_bridges"][0]
    assert bridge["adapter_module"] == "G4(A)"
    assert "CPA_game(CCA_CPA_Adv(A),RealOrcls" in bridge["lhs_game"]
    assert "MainD(G4(A),FinRO)" in bridge["rhs_game"]
    path = ir["resources"]["pr_path_plan"]["partial_paths"][0]
    assert [hop["edge_kind"] for hop in path["hops"][:2]] == [
        "synthetic_bridge",
        "pr_rewrite",
    ]
    assert all(item["id"] != "pr_byequiv_fallback" for item in ir["candidate_menu"])


def test_pr_typed_bridge_chain_connects_split_wrapper_adapters() -> None:
    where_finro = """\
[WHERE-HIT] pr_RO_FinRO_D  (kind: lemma)
* In [lemmas or axioms]:

lemma pr_RO_FinRO_D:
  forall (D0(G : RO) <: FinRO_Distinguisher) &m (x : unit)
    (p : bool -> bool),
    Pr[MainD(D0, RO).distinguish(x) @ &m : p res] =
    Pr[MainD(D0, FinRO).distinguish(x) @ &m : p res].
"""
    where_split = """\
[WHERE-HIT] pr_RO_split  (kind: lemma)
* In [lemmas or axioms]:

lemma pr_RO_split:
  Pr[Split1.IdealAll.MainD(D0, Split1.IdealAll.RO).distinguish() @ &m : res] =
  Pr[Split1.IdealAll.MainD(D0, RO_Pair(I1.RO, I2.RO)).distinguish() @ &m : res].
(* SplitC1.pr_RO_split *)
lemma pr_RO_split:
  Pr[Split0.IdealAll.MainD(D0, Split0.IdealAll.RO).distinguish() @ &m : res] =
  Pr[Split0.IdealAll.MainD(D0, SplitC1.RO_Pair(SplitC1.I1.RO, SplitC1.I2.RO)).distinguish() @ &m : res].
(* SplitD.pr_RO_split *)
lemma pr_RO_split:
  Pr[Split0.IdealAll.MainD(D0, Split0.IdealAll.RO).distinguish() @ &m : res] =
  Pr[Split0.IdealAll.MainD(D0, RO_DOM(ROT.RO, ROF.RO)).distinguish() @ &m : res].
"""
    with tempfile.TemporaryDirectory() as td:
        session = Path(td)
        (session / "context.ec").write_text(
            "\n".join([
                "lemma pr_RO_split:",
                "  Pr[MainD(D0, RO).distinguish() @ &m : res] =",
                "  Pr[MainD(D0, RO_DOM(ROT.RO, ROF.RO)).distinguish() @ &m : res].",
                "",
                "module G4 (A:Adv, RO:RO) = {",
                "  proc distinguish () = {",
                "    var b;",
                "    b <@ CCA_CPA_Adv(A, RealOrcls(GenChaChaPoly(CCRO(RO)))).main();",
                "    return b;",
                "  }",
                "}.",
                "module G6 (A:Adv, ROT:Split0.IdealAll.RO) = {",
                "  proc distinguish () = {",
                "    var b;",
                "    b <@ G4(A, RO_DOM(ROT, ROF.RO)).distinguish();",
                "    return b;",
                "  }",
                "}.",
                "module G8 (A:Adv, RO1:SplitC1.I1.RO) = {",
                "  proc distinguish () = {",
                "    var b;",
                "    b <@ G6(A, SplitC1.RO_Pair(RO1, SplitC1.I2.RO)).distinguish();",
                "    return b;",
                "  }",
                "}.",
            ]),
            encoding="utf-8",
        )
        tool_views = session / "tool_views"
        tool_views.mkdir()
        for name, text in {
            "where_finro.json": where_finro,
            "where_split.json": where_split,
        }.items():
            (tool_views / name).write_text(
                json.dumps({
                    "schema_version": 1,
                    "tool": "where",
                    "kind": "tool_view",
                    "ok": True,
                    "debug": {"legacy_text": text},
                }),
                encoding="utf-8",
            )
        ir = build_proof_ir(
            session_dir=session,
            current_goal={
                "goal_type": "probability",
                "active_goal_preview": (
                    "Current goal\n\n"
                    "------------------------------------------------------------------------\n"
                    "Pr[CPA_game(CCA_CPA_Adv(A), RealOrcls(GenChaChaPoly(CCRO(FinRO)))).main() @ &m : res] = "
                    "Pr[Split1.IdealAll.MainD(G8(A), RO_Pair(I1.RO, I2.RO)).distinguish() @ &m : res]"
                ),
                "parsed_goal": {
                    "goal_type": "probability",
                    "prob_form": "eq",
                    "lhs_game": "CPA_game",
                    "rhs_game": "Split1",
                    "pr_rewrite_candidates": [{"lemma": "pr_RO_FinRO_D"}],
                },
            },
        )

    path = ir["resources"]["pr_path_plan"]["recommended_path"]
    assert path["status"] == "complete"
    assert path["lemmas"] == [
        "bridge_CPA_game_CCA_CPA_Adv_A_RealOrcls_GenChaChaPoly_CCRO_FinRO_to_MainD_G4_A_FinRO",
        "pr_RO_FinRO_D",
        "bridge_MainD_G4_A_RO_to_Split0.IdealAll.MainD_G4_A_Split0.IdealAll.RO",
        "SplitD.pr_RO_split",
        "bridge_Split0.IdealAll.MainD_G4_A_RO_DOM_ROT.RO_ROF.RO_to_Split0.IdealAll.MainD_G6_A_Split0.IdealAll.RO",
        "SplitC1.pr_RO_split",
        "bridge_Split0.IdealAll.MainD_G6_A_SplitC1.RO_Pair_SplitC1.I1.RO_SplitC1.I2.RO_to_Split1.IdealAll.MainD_G8_A_Split1.IdealAll.RO",
        "pr_RO_split",
    ]
    assert all(item["id"] != "pr_byequiv_fallback" for item in ir["candidate_menu"])


def test_pr_inequality_does_not_surface_bare_byequiv_lowering() -> None:
    # `byequiv => //.` is a hardcoded bare tactic (move GUIDANCE), so the producer
    # no longer surfaces the `pr_byequiv_fallback` lowering even when EC's
    # `suggested_tactics` mention byequiv. The probability-goal classification is
    # the fact; the bare lowering tactic is not.
    ir = build_proof_ir(current_goal={
        "goal_type": "probability",
        "active_goal_preview": (
            "Current goal\n\n"
            "------------------------------------------------------------------------\n"
            "Pr[Left.main() @ &m : res] <= Pr[Right.main() @ &m : res]"
        ),
        "parsed_goal": {
            "goal_type": "probability",
            "prob_form": "ineq",
            "lhs_game": "Left",
            "rhs_game": "Right",
            "suggested_tactics": ["byequiv=> //=."],
            "strategy_hint": "byequiv",
        },
    })

    assert all(item["id"] != "pr_byequiv_fallback" for item in ir["candidate_menu"])
    assert all(item["tactic"] != "byequiv => //." for item in ir["candidate_menu"])


def _write_sig_tool_view(session: Path, name: str, legacy_text: str) -> None:
    tool_views = session / "tool_views"
    tool_views.mkdir(exist_ok=True)
    (tool_views / f"sig_{name}.json").write_text(
        json.dumps({
            "schema_version": 1,
            "tool": "sig",
            "kind": "tool_view",
            "ok": True,
            "evidence": {
                "context": [{
                    "id": "context.sig.query",
                    "query": {"name": name},
                }],
                "raw": [],
            },
            "debug": {"legacy_text": legacy_text},
        }),
        encoding="utf-8",
    )


def _write_where_tool_view(session: Path, name: str, legacy_text: str) -> None:
    tool_views = session / "tool_views"
    tool_views.mkdir(exist_ok=True)
    (tool_views / f"where_{name}.json").write_text(
        json.dumps({
            "schema_version": 1,
            "tool": "where",
            "kind": "tool_view",
            "ok": True,
            "proof_state": {"status": "open"},
            "guidance": {"recommendations": []},
            "evidence": {
                "context": [{
                    "id": "context.where.query",
                    "query": {"name": name},
                }],
                "raw": [],
            },
            "notes": [],
            "errors": [],
            "debug": {"legacy_text": legacy_text},
        }),
        encoding="utf-8",
    )


def test_proof_ir_bound_call_template_is_probe_candidate() -> None:
    with tempfile.TemporaryDirectory() as td:
        session = Path(td)
        _write_sig_tool_view(
            session,
            "equ_cc",
            (
                "=== Signature of 'equ_cc' (1 match) ===\n"
                "\n"
                "-- Local.ec:20 (equiv)\n"
                "local equiv equ_cc (O <: Oracle) :\n"
                "  Left(O).enc ~ Right(O).enc : true ==> ={res}.\n"
            ),
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
                        "text": "c <@ Left(RO).enc(k);",
                        "procedure": "Left(RO).enc",
                    }],
                    "right_statements": [],
                    "call_equiv_candidates": {
                        "Left(RO).enc": ["equ_cc"],
                    },
                },
            },
        )

    bound_candidates = [
        item for item in ir["candidate_menu"]
        if item["tactic_family"] == "instantiated_template"
    ]
    assert bound_candidates[0]["tactic"] == "call (equ_cc RO)."
    assert bound_candidates[0]["legality"]["status"] == "preferred"
    assert bound_candidates[0]["cost_factors"]["bound_tactic_family"] == (
        "call_named_equiv"
    )


def test_call_equiv_value_args_bind_from_multi_binder_signature() -> None:
    with tempfile.TemporaryDirectory() as td:
        session = Path(td)
        _write_sig_tool_view(
            session,
            "equ_cc",
            (
                "=== Signature of 'equ_cc' (1 match) ===\n"
                "\n"
                "-- Local.ec:20 (equiv)\n"
                "local equiv equ_cc (n0 : nonce) (mr0 ms0 : msg) :\n"
                "  ChaCha.enc ~ ChaCha.enc : true ==> ={res}.\n"
            ),
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
                        "text": "c <@ ChaCha.enc(n0, mr0, ms0);",
                        "procedure": "ChaCha.enc",
                    }],
                    "right_statements": [{
                        "pos": 1,
                        "type": "CALL",
                        "text": "c <@ ChaCha.enc(n0, mr0, ms0);",
                        "procedure": "ChaCha.enc",
                    }],
                    "call_equiv_candidates": {
                        "ChaCha.enc": ["equ_cc"],
                    },
                },
            },
        )

    slots = [
        slot["slot"]["name"]
        for item in ir["resources"]["handles"]["instantiation_bindings"]["items"]
        if item["name"] == "equ_cc"
        for slot in item["slots"]
    ]
    assert slots == ["n0", "mr0", "ms0"]
    templates = [
        item for item in ir["candidate_menu"]
        if item["tactic_family"] == "instantiated_template"
    ]
    assert templates[0]["tactic"] == "call (equ_cc n0 mr0 ms0)."
    assert all(
        item["tactic"] != "call equ_cc."
        for item in ir["candidate_menu"]
        if item["tactic_family"] == "call_named_equiv"
    )
    route = ir["resources"]["handles"]["call_site_route"]
    assert route["state"] == "callable_named_call"
    assert route["callable_now"][0]["symbol"] == "equ_cc"
    assert route["frontier_live_named_handles"][0]["symbol"] == "equ_cc"
    assert route["named_handles"][0]["call_candidate_kind"] == "direct_current_call"
    assert route["named_call_templates"][0]["status"] == "instantiated_template"
    assert route["named_call_templates"][0]["tactic_shape"] == (
        "call (equ_cc n0 mr0 ms0)."
    )


def test_call_equiv_state_snapshot_slots_surface_exlim_call_not_ecall() -> None:
    with tempfile.TemporaryDirectory() as td:
        session = Path(td)
        _write_sig_tool_view(
            session,
            "equ_cc",
            (
                "=== Signature of 'equ_cc' (1 match) ===\n"
                "\n"
                "-- Local.ec:20 (equiv)\n"
                "local equiv equ_cc n0 mr0 ms0:\n"
                "  ChaCha.enc ~ EncRnd.cc :\n"
                "    arg{2}.`1 = n0 /\\ mr0 = ROin.m{1} /\\ ms0 = ROout.m{1}\n"
                "    ==> ={res} /\\ mr0 = ROin.m{1} /\\ ms0 = ROout.m{1}.\n"
            ),
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
                    "call_equiv_candidates": {
                        "ChaCha.enc": ["equ_cc"],
                    },
                },
            },
        )

    binding = [
        item for item in ir["resources"]["handles"]["instantiation_bindings"]["items"]
        if item["name"] == "equ_cc"
    ][0]
    selected = [slot["selected_candidate"] for slot in binding["slots"]]
    assert [candidate["value"] for candidate in selected] == [
        "n",
        "ROin.m",
        "ROout.m",
    ]
    assert selected[1]["role"] == "state_snapshot_parameter"
    # The exlim/call elaboration is a fill-in TEMPLATE (it carries
    # requires_instantiation), so it is no longer surfaced in candidate_menu — the
    # exlim state-snapshot BINDING above (n / ROin.m / ROout.m as
    # state_snapshot_parameter) is the fact. Neither the ecall variant, the naked
    # instantiated form, nor any bare `call equ_cc.` is offered.
    assert all(
        item["id"] != "instantiated_ecall_elaboration_equ_cc"
        for item in ir["candidate_menu"]
    )
    assert all(
        item["id"] != "instantiated_call_elaboration_equ_cc"
        for item in ir["candidate_menu"]
    )
    assert all(
        item["tactic"] != "call (equ_cc n ROin.m ROout.m)."
        for item in ir["candidate_menu"]
    )
    assert all(
        item["tactic"] != "call equ_cc."
        for item in ir["candidate_menu"]
        if item["tactic_family"] == "call_named_equiv"
    )
    route = ir["resources"]["handles"]["call_site_route"]
    assert route["state"] == "callable_named_call"
    assert route["callable_now"][0]["symbol"] == "equ_cc"
    assert route["frontier_live_named_handles"][0]["symbol"] == "equ_cc"
    assert route["named_handles"][0]["call_candidate_kind"] == "direct_current_call"
    assert route["named_call_templates"][0]["preferred_call_form"] == (
        "exlim_then_call_fallback"
    )
    assert route["named_call_templates"][0]["tactic_shape"] == (
        "exlim n{2}, ROin.m{1}, ROout.m{1} => n0 mr0 ms0; "
        "call (equ_cc n0 mr0 ms0)."
    )


def test_pRHL_pretty_goal_fallback_classifies_body_without_raw_file() -> None:
    goal_text = (
        "pre = true\n"
        "(1) x <- a;\n"
        "(2) if (x \\in xs) {\n"
        "post = ={x}\n"
    )
    ir = build_proof_ir(current_goal={
        "goal_type": "pRHL",
        "active_goal_preview": goal_text,
        "parsed_goal": {
            "goal_type": "pRHL",
            "suggested_tactics": ["wp.", "if => //=."],
        },
    })

    assert ir["current_layer"] == "procedure_body"
    frontend = ir["resources"]["handles"]["procedure_body_frontend"]
    status = frontend["program_structure_status"]
    assert status["statement_source"] == "pretty_goal_fallback"
    assert status["recovered_statement_count"] == 2
    assert frontend["has_branch"] is True
    actions = [item["tactic"] for item in ir["candidate_menu"]]
    # `if => //=.` is a hardcoded bare tactic (move GUIDANCE), so it is no longer
    # surfaced; the branch is recognized via the goal-FILLED rcond/case facts.
    assert "if => //=." not in actions
    assert any(a.startswith("rcondt{1} ") for a in actions)
    assert any(a.startswith("case: (") for a in actions)


def test_program_structure_gap_points_to_structured_inspection() -> None:
    ir = build_proof_ir(current_goal={
        "goal_type": "pRHL",
        "active_goal_preview": (
            "pre = true\n"
            "left program contains c <@ EncRnd.cc(n, p)\n"
            "post = ={res}\n"
        ),
        "parsed_goal": {
            "goal_type": "pRHL",
            "suggested_tactics": ["wp."],
        },
    })

    assert ir["current_layer"] == "procedure_entry"
    by_id = {item["id"]: item for item in ir["candidate_menu"]}
    assert by_id["program_structure_unavailable"]["tactic"] == "-program-json"
    assert by_id["program_structure_unavailable"]["action_type"] == "inspection_action"


def test_unbound_call_equiv_value_args_do_not_surface_naked_call() -> None:
    with tempfile.TemporaryDirectory() as td:
        session = Path(td)
        _write_sig_tool_view(
            session,
            "equ_cc",
            (
                "=== Signature of 'equ_cc' (1 match) ===\n"
                "\n"
                "-- Local.ec:20 (equiv)\n"
                "local equiv equ_cc (n0 : nonce) (mr0 ms0 : msg) :\n"
                "  ChaCha.enc ~ ChaCha.enc : true ==> ={res}.\n"
            ),
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
                        "text": "c <@ ChaCha.enc(k, n, p2);",
                        "procedure": "ChaCha.enc",
                    }],
                    "right_statements": [{
                        "pos": 1,
                        "type": "CALL",
                        "text": "c <@ ChaCha.enc(k, n, p2);",
                        "procedure": "ChaCha.enc",
                    }],
                    "call_equiv_candidates": {
                        "ChaCha.enc": ["equ_cc"],
                    },
                },
            },
        )

    call_candidates = [
        item for item in ir["candidate_menu"]
        if item["tactic_family"] == "call_named_equiv"
    ]
    assert call_candidates == []
    lookup = [
        item for item in ir["candidate_menu"]
        if item["id"] == "sig_equ_cc"
    ][0]
    assert lookup["tactic"] == "-where equ_cc"
    assert lookup["cost_factors"]["requires_instantiation"] is True
    assert "value arg `mr0`" in lookup["missing_slots"]
    assert "value arg `ms0`" in lookup["missing_slots"]
    route = ir["resources"]["handles"]["call_site_route"]
    assert route["state"] == "live_named_call_needs_binding"
    assert route.get("callable_now", []) == []
    assert route["frontier_live_named_handles"][0]["symbol"] == "equ_cc"
    assert route["named_handles"][0]["frontier_live"] is True
    assert route["named_handles"][0]["callable_now"] is False
    assert route["named_call_templates"] == [{
        "symbol": "equ_cc",
        "status": "missing_instantiation",
        "missing_slots": ["value arg `mr0`", "value arg `ms0`"],
    }]


def test_adversary_frontier_marks_oracle_handles_and_skeleton() -> None:
    goal_text = (
        "Current goal\n\n"
        "H : equiv[ P.init ~ P'.init : true ==> ={glob P}]\n"
        "H0 : equiv[ P.f ~ P'.f : ={arg} ==> ={res}]\n"
        "A(O : RCPA_Oracles) : RCPA_Adversary{-P, -P'}\n"
        "------------------------------------------------------------------------\n"
        "pre = ={glob P}\n"
        "post = ={glob P} /\\ res{1} = res{2}"
    )
    ir = build_proof_ir(current_goal={
        "goal_type": "pRHL",
        "active_goal_preview": goal_text,
        "parsed_goal": {
            "goal_type": "pRHL",
            "pre": "={glob P}",
            "post": "={glob P} /\\ res{1} = res{2}",
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
    })

    handles = ir["resources"]["handles"]["callable_lemmas"]
    roles = {handle["lemma"]: handle["handle_role"] for handle in handles}
    assert roles["H"] == "oracle_obligation_handle"
    assert roles["H0"] == "oracle_obligation_handle"
    assert ir["liveness"]["oracle_obligation_handle_count"] == 2
    menu_ids = [item["id"] for item in ir["candidate_menu"]]
    assert "adversary_invariant_skeleton" in menu_ids
    assert "call_H0" not in menu_ids
    skeleton = [
        item for item in ir["candidate_menu"]
        if item["id"] == "adversary_invariant_skeleton"
    ][0]
    assert "H0" in skeleton["cost_factors"]["oracle_obligations"]
    # the oracle-handle fact is the resource-summary count, not prefer prose.
    assert ir["phase"]["resource_summary"]["oracle_obligation_handles"] >= 1
    assert ir["diagnostics"][0]["code"] == "proof_ir.oracle_obligation_handles"


def test_adversary_skeleton_prefers_oracle_hypothesis_invariant() -> None:
    goal_text = (
        "Current goal\n\n"
        "P_init_eq: equiv[ P.init ~ P'.init : true ==>\n"
        "                 I (glob P){1} (glob P'){2}]\n"
        "P_f_eq: equiv[ P.f ~ P'.f :\n"
        "                arg{1} = arg{2} /\\ I (glob P){1} (glob P'){2} ==>\n"
        "                res{1} = res{2} /\\ I (glob P){1} (glob P'){2}]\n"
        "A(O : RCPA_Oracles) : RCPA_Adversary{-P, -P'}\n"
        "------------------------------------------------------------------------\n"
        "pre = (glob A){1} = (glob A){m} /\\ (glob P){1} = (glob P){m}\n"
        "post = b{1} = b{2}"
    )
    ir = build_proof_ir(current_goal={
        "goal_type": "pRHL",
        "active_goal_preview": goal_text,
        "parsed_goal": {
            "goal_type": "pRHL",
            "pre": "pre = (glob A){1} = (glob A){m} /\\ (glob P){1} = (glob P){m}",
            "post": "post = b{1} = b{2}",
            "left_statements": [{
                "pos": 1,
                "type": "CALL",
                "text": "b <@ A(CBC_Oracle(P)).distinguish();",
                "procedure": "A(CBC_Oracle(P)).distinguish",
            }],
            "right_statements": [{
                "pos": 1,
                "type": "CALL",
                "text": "b <@ A(CBC_Oracle(P')).distinguish();",
                "procedure": "A(CBC_Oracle(P')).distinguish",
            }],
        },
    })

    skeleton = ir["resources"]["handles"]["adversary_invariant_skeleton"]
    assert skeleton["suggested_invariant"] == (
        "I (glob P){1} (glob P'){2}"
    )
    obligations = {
        item["lemma"]: item for item in skeleton["oracle_obligations"]
    }
    assert obligations["P_init_eq"] == {
        "lemma": "P_init_eq",
        "procedures": ["P.init", "P'.init"],
        "precondition": "true",
        "postcondition": "I (glob P){1} (glob P'){2}",
        "invariant_atoms": ["I (glob P){1} (glob P'){2}"],
        "expected_tactic": "call P_init_eq.",
        "source": "current_goal_hypothesis",
    }
    assert obligations["P_f_eq"] == {
        "lemma": "P_f_eq",
        "procedures": ["P.f", "P'.f"],
        "precondition": "arg{1} = arg{2} /\\ I (glob P){1} (glob P'){2}",
        "postcondition": "res{1} = res{2} /\\ I (glob P){1} (glob P'){2}",
        "invariant_atoms": ["I (glob P){1} (glob P'){2}"],
        "expected_tactic": "call P_f_eq.",
        "source": "current_goal_hypothesis",
    }
    menu_item = [
        item for item in ir["candidate_menu"]
        if item["id"] == "adversary_invariant_skeleton"
    ][0]
    assert menu_item["action_type"] == "strategy_hint"
    assert menu_item["tactic"] == (
        "call (_: I (glob P){1} (glob P'){2})."
    )


def test_pr_normalization_recommends_congr_before_byequiv() -> None:
    ir = build_proof_ir(current_goal={
        "goal_type": "probability",
        "active_goal_preview": (
            "Current goal\n\n"
            "------------------------------------------------------------------------\n"
            "- Pr[G.main() @ &m : res] = - Pr[G'.main() @ &m : res]"
        ),
        "parsed_goal": {
            "goal_type": "probability",
            "prob_form": "eq",
            "raw_text": "- Pr[G.main() @ &m : res] = - Pr[G'.main() @ &m : res]",
        },
    })

    assert ir["resources"]["pr_normal_form"]["normalization_kind"] == (
        "common_unary_minus"
    )
    assert ir["candidate_menu"][0]["id"] == "pr_normalize_congr"
    assert ir["candidate_menu"][0]["tactic"] == "congr."
    assert [
        item["id"] for item in ir["candidate_menu"]
        if item["id"] == "byequiv_bridge"
    ] == []


def test_instantiated_rewrite_in_additive_inequality_is_strategy_context() -> None:
    with tempfile.TemporaryDirectory() as td:
        session = Path(td)
        (session / "context.ec").write_text(
            "\n".join([
                "local lemma step3 &m :",
                "  Pr[Game0.main() @ &m : res] = Pr[Game1.main() @ &m : res].",
            ]),
            encoding="utf-8",
        )
        ir = build_proof_ir(
            session_dir=session,
            current_goal={
                "goal_type": "probability",
                "active_goal_preview": (
                    "Current goal\n\n"
                    "------------------------------------------------------------------------\n"
                    "Pr[Game0.main() @ &m : res] <=\n"
                    "Pr[Bound0.main() @ &m : bad0] + Pr[Bound1.main() @ &m : bad1]"
                ),
                "parsed_goal": {
                    "goal_type": "probability",
                    "prob_form": "compound",
                    "pr_rewrite_candidates": [{"lemma": "step3"}],
                    "lhs_addends": [{"game": "Game0", "event": "res"}],
                    "rhs_addends": [
                        {"game": "Bound0", "event": "bad0"},
                        {"game": "Bound1", "event": "bad1"},
                    ],
                },
            },
        )

    instantiated = [
        item for item in ir["candidate_menu"]
        if item["id"].startswith("instantiated_step3")
    ][0]
    assert instantiated["tactic"] == "rewrite (step3 &m)."
    assert instantiated["action_type"] == "strategy_hint"
    assert "additive/inequality shell" in instantiated["why"]


def test_future_source_lemma_is_not_instantiated_as_runnable_rewrite() -> None:
    with tempfile.TemporaryDirectory() as td:
        session = Path(td)
        source = session / "target.ec"
        (session / "context.ec").write_text(
            "\n".join([
                "local lemma step2_3 &m :",
                "  Pr[Game0.main() @ &m : res] = Pr[Game1.main() @ &m : res].",
                "proof.",
            ]),
            encoding="utf-8",
        )
        source.write_text(
            "\n".join([
                "local lemma step2_3 &m :",
                "  Pr[Game0.main() @ &m : res] = Pr[Game1.main() @ &m : res].",
                "proof. admit. qed.",
                "",
                "local lemma step3 &m :",
                "  Pr[Game0.main() @ &m : res] = Pr[Game1.main() @ &m : res].",
                "proof. admit. qed.",
            ]),
            encoding="utf-8",
        )
        (session / "session_meta.json").write_text(
            json.dumps({"file": str(source), "lemma": "step2_3"}),
            encoding="utf-8",
        )
        ir = build_proof_ir(
            session_dir=session,
            current_goal={
                "goal_type": "probability",
                "active_goal_preview": (
                    "Current goal\n\n"
                    "------------------------------------------------------------------------\n"
                    "Pr[Game0.main() @ &m : res] = Pr[Game1.main() @ &m : res]"
                ),
                "parsed_goal": {
                    "goal_type": "probability",
                    "prob_form": "Pr_eq",
                    "pr_rewrite_candidates": [{"lemma": "step3"}],
                },
            },
        )

    assert all(
        item["id"] != "instantiated_step3_0"
        for item in ir["candidate_menu"]
    )
    step3 = next(
        item for item in ir["resources"]["name_resolution"]["items"]
        if item["name"] == "step3"
    )
    assert step3["resolution_status"] == "source_local_scope_check_required"
    assert step3["exact_signature_known"] is False


def test_failed_call_oracle_handle_gets_boundary_diagnostic() -> None:
    goal_text = (
        "Current goal\n\n"
        "H0 : equiv[ P.f ~ P'.f : ={arg} ==> ={res}]\n"
        "A(O : RCPA_Oracles) : RCPA_Adversary{-P, -P'}\n"
        "------------------------------------------------------------------------\n"
        "pre = ={glob P}\n"
        "post = ={glob P}"
    )
    ir = build_proof_ir(
        proof_state={
            "latest_transition": {
                "tactic": "call H0.",
                "latest_error": "invalid tactic: no matching procedure call",
            },
        },
        current_goal={
            "goal_type": "pRHL",
            "active_goal_preview": goal_text,
            "parsed_goal": {
                "goal_type": "pRHL",
                "pre": "={glob P}",
                "post": "={glob P}",
                "left_statements": [{
                    "pos": 1,
                    "type": "CALL",
                    "text": "b <@ A(CBC_Oracle(P)).distinguish();",
                    "procedure": "A(CBC_Oracle(P)).distinguish",
                }],
                "right_statements": [{
                    "pos": 1,
                    "type": "CALL",
                    "text": "b <@ A(CBC_Oracle(P')).distinguish();",
                    "procedure": "A(CBC_Oracle(P')).distinguish",
                }],
            },
        },
    )

    diag = ir["diagnostics"][0]
    assert diag["code"] == "proof_ir.failure.call_is_oracle_obligation"
    assert diag["evidence"]["handle_role"] == "oracle_obligation_handle"
    assert "adversary invariant" in diag["repairs"][0]


def test_failed_byequiv_with_pr_frontend_actions_gets_diagnostic() -> None:
    ir = build_proof_ir(
        proof_state={
            "latest_transition": {
                "tactic": "byequiv => //.",
                "latest_error": "cannot apply byequiv",
            },
        },
        current_goal={
            "goal_type": "probability",
            "active_goal_preview": (
                "Current goal\n\n"
                "------------------------------------------------------------------------\n"
                "- Pr[G.main() @ &m : res] = - Pr[G'.main() @ &m : res]"
            ),
            "parsed_goal": {
                "goal_type": "probability",
                "prob_form": "eq",
                "pr_rewrite_candidates": [{"lemma": "pr_Game_Game'"}],
            },
        },
    )

    diag = ir["diagnostics"][0]
    assert diag["code"] == "proof_ir.failure.byequiv_before_pr_frontend"
    assert "congr" in " ".join(diag["repairs"])
    assert "pr_Game_Game'" in diag["evidence"]["pr_rewrite_candidates"]


def main() -> int:
    test_proof_ir_candidate_menu_satisfies_action_contract()
    test_action_contract_blocks_fallback_resource_as_probeable()
    test_call_site_layer_tracks_live_callable_handles()
    test_program_edit_script_seq_cut_is_agent_facing_candidate()
    test_full_prefix_seq_is_labeled_as_cleanup_skeleton()
    test_proof_ir_recommendation_is_probe_only()
    test_call_handle_requires_frontier_before_probe()
    test_while_frontier_exposure_does_not_suggest_plain_wp()
    test_program_diff_orders_call_handles_by_statement_order()
    test_external_recommendations_become_proof_ir_candidates()
    test_external_candidate_requires_scope_check_for_source_local_name()
    test_no_progress_external_candidate_is_avoided()
    test_unverified_external_pr_apply_is_probe_after_signature_resolution()
    test_annotation_ranks_intro_before_residual_closer()
    test_ambient_implication_gets_intro_candidate()
    test_prhl_module_gets_proc_candidate()
    test_phoare_entry_gets_proc_before_wp()
    test_current_goal_equiv_hypothesis_is_callable_handle()
    test_annotate_recommendations_adds_proof_ir_cost_metadata()
    test_phase_legality_marks_inline_all_avoid_with_live_handles()
    test_branch_frontier_defers_if_when_live_call_handle_needs_seq()
    test_proof_ir_resolves_local_call_handle_signature()
    test_source_generic_equiv_lemma_attaches_to_matching_call_site()
    test_annotate_recommendations_downgrades_inline_all_to_avoid()
    test_invariant_skeleton_from_prhl_postcondition()
    test_call_invariant_skeleton_surfaces_live_fact_coverage()
    test_inline_all_history_marks_call_handles_consumed()
    test_prior_inline_all_diagnostic_is_suppressed_on_fresh_pr_frontier()
    test_failed_call_after_inline_all_gets_resource_diagnostic()
    test_failed_call_not_at_frontier_gets_resource_diagnostic()
    test_probability_pr_rewrite_stays_at_pr_layer()
    test_probability_discovers_imported_pr_bridge_before_name_lookup()
    test_probability_pr_bridge_ranking_prefers_pair_endpoint_match()
    test_probability_typed_bridge_chain_exposes_wrapper_to_main_before_byequiv()
    test_typed_bridge_menu_surfaces_live_wrapper_even_without_complete_path()
    test_probability_have_chain_gets_pr_path_plan()
    test_probability_partial_pr_path_prioritizes_path_lookups()
    test_probability_advantage_bound_gets_arithmetic_plan()
    test_probability_bound_shape_without_candidates_still_gets_pr_plan()
    test_compound_pr_lemma_is_not_simple_rewrite_candidate()
    test_native_ast_search_query_is_proof_ir_frontend_action()
    test_pr_bound_goal_prefers_bound_search_over_unresolved_bridge_lookup()
    test_native_ast_search_hits_become_where_candidates()
    test_proof_ir_consumes_sig_tool_view_for_pr_rewrite()
    test_proof_ir_instantiates_section_exported_pr_rewrite_shape()
    test_proof_ir_bound_call_template_is_probe_candidate()
    test_call_equiv_value_args_bind_from_multi_binder_signature()
    test_call_equiv_state_snapshot_slots_surface_exlim_call_not_ecall()
    test_pRHL_pretty_goal_fallback_classifies_body_without_raw_file()
    test_program_structure_gap_points_to_structured_inspection()
    test_unbound_call_equiv_value_args_do_not_surface_naked_call()
    test_adversary_frontier_marks_oracle_handles_and_skeleton()
    test_adversary_skeleton_prefers_oracle_hypothesis_invariant()
    test_pr_normalization_recommends_congr_before_byequiv()
    test_structured_procedure_frontier_plan_orders_prefix_before_loop()
    test_structured_procedure_frontier_plan_keeps_sample_as_local_vc()
    test_current_region_summary_explains_sync_call_and_bad_event_monitor()
    test_probabilistic_vc_frontend_classifies_mee_loop_bad_bound()
    test_probabilistic_vc_frontend_classifies_cramer_shoup_phoare_bound()
    test_probabilistic_vc_frontend_classifies_pr_loss_accounting()
    test_failed_call_oracle_handle_gets_boundary_diagnostic()
    test_failed_byequiv_with_pr_frontend_actions_gets_diagnostic()
    print("PASS test_proof_ir")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
