"""Tests for semantic EasyCrypt lemma indexing."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from core.easycrypt.analysis.ec_lemma_index import (  # noqa: E402
    build_semantic_lemma_index,
    high_precision_pr_bound_routes,
    mechanical_goal_candidates,
    semantic_distribution_certificates,
    semantic_one_sided_losslessness_candidates,
    semantic_pr_bound_candidates,
    semantic_pr_rewrite_candidates,
    source_declarations_by_name,
)
from core.easycrypt.analysis.ec_proof_ir import build_proof_ir  # noqa: E402


def _write_context(session: Path) -> None:
    (session / "context.ec").write_text(
        "local lemma OddlyNamedBridge &m :\n"
        "  Pr[Game(A, PLog).main() @ &m : res] =\n"
        "  Pr[Game(A, PLog2).main() @ &m : res].\n"
        "proof. by smt(). qed.\n\n"
        "lemma OddlyNamedBound &m :\n"
        "  Pr[Game(A, PLog).main() @ &m : Bad P.logP F.m] <= eps.\n"
        "proof. by smt(). qed.\n\n"
        "lemma OddlyNamedUnion &m :\n"
        "  Pr[Game(A, PLog).main() @ &m : E1 \\/ E2] <=\n"
        "  Pr[Game(A, PLog).main() @ &m : E1] +\n"
        "  Pr[Game(A, PLog).main() @ &m : E2].\n"
        "proof. by smt(). qed.\n",
        encoding="utf-8",
    )


def test_semantic_index_classifies_pr_rewrite_and_bound_without_name_rules() -> None:
    with tempfile.TemporaryDirectory() as td:
        session = Path(td)
        _write_context(session)
        index = build_semantic_lemma_index(session)

    by_name = {
        str(item.get("lemma") or ""): item
        for item in index["items"]
    }
    assert "pr_rewrite" in by_name["OddlyNamedBridge"]["semantic_tags"]
    assert "pr_bound" in by_name["OddlyNamedBound"]["semantic_tags"]
    assert "pr_additive_bound" in by_name["OddlyNamedUnion"]["semantic_tags"]
    assert "event_union" in by_name["OddlyNamedUnion"]["semantic_tags"]


def test_mechanical_goal_candidates_do_not_surface_symbol_overlap() -> None:
    with tempfile.TemporaryDirectory() as td:
        session = Path(td)
        (session / "context.ec").write_text(
            "lemma ArbitraryAlpha (d : 'a distr) (s : 'a fset) :\n"
            "  mu d (fun x => x \\in s) <= (card s)%r * mu1 d.\n"
            "proof. admit. qed.\n\n"
            "lemma UnrelatedBeta (xs : int list) : size xs <= size xs + 1.\n"
            "proof. admit. qed.\n",
            encoding="utf-8",
        )
        index = build_semantic_lemma_index(session)
        matches = mechanical_goal_candidates(
            index,
            goal_text=(
                "mu dD (fun k => k \\in cross s1 s2) <= "
                "(card (cross s1 s2))%r * eps"
            ),
        )

    assert matches == []


def test_mechanical_goal_candidates_reject_common_relation_only() -> None:
    index = {
        "items": [{
            "lemma": "Unrelated",
            "declaration_kind": "lemma",
            "declaration": "lemma Unrelated (x y : int) : x <= y.",
        }],
    }
    assert mechanical_goal_candidates(index, goal_text="a <= b") == []


def test_mechanical_goal_candidates_find_loaded_order_schema_from_exact_chain() -> None:
    index = {
        "items": [{
            "lemma": "UnexpectedChainName",
            "declaration_kind": "lemma",
            "declaration": (
                "lemma UnexpectedChainName (x y z : real) : "
                "x <= y => y <= z => x <= z."
            ),
            "authority": "source_scan_fallback",
        }],
    }
    goal = """Current goal
a b c : real
Hab : a <= b
Hbc : b <= c
----------------------------------------
a <= c
"""
    matches = mechanical_goal_candidates(index, goal_text=goal)

    assert [item["lemma"] for item in matches] == ["UnexpectedChainName"]
    assert matches[0]["match_kind"] == "order_transitivity_schema"
    assert "x <= y => y <= z => x <= z" in matches[0]["declaration"]


def test_mechanical_goal_candidates_match_complete_losslessness_obligation() -> None:
    index = {"items": [{
        "lemma": "AaL",
        "declaration_kind": "axiom",
        "declaration": (
            "declare axiom AaL (F <: ARF{-A}) (P <: APRG{-A}) : "
            "islossless P.prg => islossless F.f => islossless A(F,P).a."
        ),
        "module_parameters": ["A"],
    }]}
    goal = (
        "forall (F0 <: ARF{-A}) (P0 <: APRG{-A}), "
        "islossless P0.prg => islossless F0.f => islossless A(F0,P0).a"
    )

    matches = mechanical_goal_candidates(index, goal_text=goal)

    assert [item["lemma"] for item in matches] == ["AaL"]
    assert matches[0]["match_kind"] == "losslessness_obligation_match"
    assert matches[0]["parameter_bindings"] == {"F": "F0", "P": "P0"}
    assert matches[0]["required_premises"] == [
        "islossless P0.prg", "islossless F0.f",
    ]
    assert matches[0]["direct_application"] == "exact AaL."


def test_mechanical_goal_candidates_reject_losslessness_premise_mismatch() -> None:
    index = {"items": [{
        "lemma": "TooWeak",
        "declaration_kind": "lemma",
        "declaration": (
            "lemma TooWeak (F <: ARF{-A}) (P <: APRG{-A}) : "
            "islossless F.f => islossless A(F,P).a."
        ),
        "module_parameters": ["A"],
    }]}
    goal = (
        "forall (F0 <: ARF{-A}) (P0 <: APRG{-A}), "
        "islossless P0.prg => islossless F0.f => islossless A(F0,P0).a"
    )

    assert mechanical_goal_candidates(index, goal_text=goal) == []


def test_mechanical_goal_candidates_never_surface_target_lemma_itself() -> None:
    declaration = (
        "local lemma Alossless_D2 : forall (O <: Oracle{-D2}), "
        "islossless O.f => islossless D2(O).distinguish."
    )
    index = {"items": [{
        "lemma": "Alossless_D2",
        "declaration_kind": "local lemma",
        "declaration": declaration,
    }]}

    assert mechanical_goal_candidates(
        index,
        goal_text=(
            "forall (O <: Oracle{-D2}), "
            "islossless O.f => islossless D2(O).distinguish"
        ),
        target_lemma="Alossless_D2",
    ) == []


def test_mechanical_goal_candidates_find_finite_membership_measure_bridge() -> None:
    index = {
        "items": [
            {
                "lemma": "MeasureBridge",
                "declaration_kind": "lemma",
                "declaration": (
                    "lemma MeasureBridge ['a] (d : 'a distr) (s : 'a list) (r : real) : "
                    "(forall x, mu1 d x <= r) => mu d (mem s) <= (size s)%r * r."
                ),
            },
            {
                "lemma": "SizeNoise",
                "declaration_kind": "lemma",
                "declaration": "lemma SizeNoise (xs : int list) : size xs <= size xs + 1.",
            },
        ],
    }
    goal = "mu dt (mem (elems states)) <= (size (elems states))%r * epsilon"

    matches = mechanical_goal_candidates(index, goal_text=goal)

    assert [item["lemma"] for item in matches] == ["MeasureBridge"]
    assert matches[0]["match_kind"] == "loaded_structural_fingerprint"
    assert matches[0]["required_premises"] == ["(forall x, mu1 d x <= r)"]


def test_mechanical_goal_candidates_type_checks_add_sub_cancellation() -> None:
    index = {
        "items": [
            {
                "lemma": "PolyCancel",
                "declaration_kind": "lemma",
                "declaration": (
                    "lemma PolyCancel (x y : poly_out) : x = x - y + y."
                ),
            },
            {
                "lemma": "IntCancel",
                "declaration_kind": "lemma",
                "declaration": "lemma IntCancel (x y : int) : x = x - y + y.",
            },
        ],
    }
    goal = """Current goal
s t : poly_out
----------------------------------------
s - t + t = s
"""

    matches = mechanical_goal_candidates(index, goal_text=goal)

    assert [item["lemma"] for item in matches] == ["PolyCancel"]
    assert matches[0]["shared_types"] == ["poly_out"]


def test_mechanical_goal_candidates_do_not_leak_unrelated_context_type() -> None:
    index = {
        "items": [{
            "lemma": "PolyCancel",
            "declaration_kind": "lemma",
            "declaration": "lemma PolyCancel (x y : poly_out) : x = x - y + y.",
        }],
    }
    goal = """Current goal
nth0 : int
t0 : poly_out
----------------------------------------
nth0 - size xs < size ys /\\ t0 = nth witness ys nth0
"""

    assert mechanical_goal_candidates(index, goal_text=goal) == []


def test_mechanical_goal_candidates_match_nested_loaded_operators() -> None:
    index = {
        "items": [{
            "lemma": "PackingIdentity",
            "declaration_kind": "lemma",
            "declaration": (
                "local lemma PackingIdentity r s e : "
                "pack (Left.ofpair (Right.ofpair (r, s), e)) = (r, s)."
            ),
        }],
    }
    goal = "result = pack (Left.ofpair (Right.ofpair (a, b), extra))"

    matches = mechanical_goal_candidates(index, goal_text=goal)

    assert [item["lemma"] for item in matches] == ["PackingIdentity"]
    assert set(matches[0]["shared_symbols"]) == {"ofpair", "pack"}


def test_mechanical_goal_candidates_reject_bare_constant_overlap() -> None:
    index = {
        "items": [{
            "lemma": "LooseBound",
            "declaration_kind": "lemma",
            "declaration": "lemma LooseBound : eps <= q%r.",
        }],
    }

    assert mechanical_goal_candidates(index, goal_text="eps <= q%r ^ 2") == []


def test_mechanical_goal_candidates_find_zero_event_measure() -> None:
    index = {
        "items": [{
            "lemma": "ZeroMeasure",
            "declaration_kind": "lemma",
            "declaration": "lemma ZeroMeasure (d : 'a distr) : mu d pred0 = 0%r.",
        }],
    }

    matches = mechanical_goal_candidates(index, goal_text="mu sample pred0 = 0%r")

    assert [item["lemma"] for item in matches] == ["ZeroMeasure"]
    assert matches[0]["shared_structures"] == ["zero-event measure"]


def test_semantic_rewrite_candidates_match_goal_shape() -> None:
    with tempfile.TemporaryDirectory() as td:
        session = Path(td)
        _write_context(session)
        index = build_semantic_lemma_index(session)
        candidates = semantic_pr_rewrite_candidates(
            index,
            parsed={"goal_type": "probability"},
            goal_text=(
                "Pr[Game(A, PLog).main() @ &m : res] = "
                "Pr[Game(A, PLog2).main() @ &m : res]"
            ),
        )

    assert candidates
    assert candidates[0]["lemma"] == "OddlyNamedBridge"


def test_pr_rewrite_with_outer_premise_reports_exact_endpoint_and_premise() -> None:
    with tempfile.TemporaryDirectory() as td:
        session = Path(td)
        (session / "context.ec").write_text(
            "local lemma GuardedBridge &m (q : int) :\n"
            "  initialisation q =>\n"
            "  Pr[Game(A, G0).main(q) @ &m : res] =\n"
            "  Pr[Game(A, G1).main(q) @ &m : res].\n"
            "proof. admit. qed.\n",
            encoding="utf-8",
        )
        index = build_semantic_lemma_index(session)
        candidates = semantic_pr_rewrite_candidates(
            index,
            parsed={"goal_type": "probability"},
            goal_text="Pr[Game(A, G0).main(q) @ &m : res] <= eps",
        )

    by_name = {item["lemma"]: item for item in index["items"]}
    assert "pr_rewrite" in by_name["GuardedBridge"]["semantic_tags"]
    assert [item["lemma"] for item in candidates] == ["GuardedBridge"]
    assert candidates[0]["required_premises"] == ["initialisation q"]
    assert candidates[0]["exact_endpoint_match"] is True
    assert candidates[0]["exact_endpoint_matches"][0]["lemma_side"] == "lhs"
    assert candidates[0]["exact_endpoint_matches"][0]["rewrite_direction"] == "lhs_to_rhs"


def test_semantic_index_keeps_same_name_clone_pr_rewrites() -> None:
    with tempfile.TemporaryDirectory() as td:
        session = Path(td)
        tool_views = session / "tool_views"
        tool_views.mkdir()
        (tool_views / "where_split.json").write_text(
            json.dumps({
                "schema_version": 1,
                "tool": "where",
                "kind": "tool_view",
                "ok": True,
                "debug": {
                    "legacy_text": """\
[WHERE-HIT] pr_RO_split  (kind: lemma)
* In [lemmas or axioms]:

lemma pr_RO_split:
  Pr[Split1.IdealAll.MainD(D, Split1.IdealAll.RO).distinguish() @ &m : res] =
  Pr[Split1.IdealAll.MainD(D, RO_Pair(I1.RO, I2.RO)).distinguish() @ &m : res].
(* SplitC1.pr_RO_split *)
lemma pr_RO_split:
  Pr[Split0.IdealAll.MainD(D, Split0.IdealAll.RO).distinguish() @ &m : res] =
  Pr[Split0.IdealAll.MainD(D, SplitC1.RO_Pair(SplitC1.I1.RO, SplitC1.I2.RO)).distinguish() @ &m : res].
""",
                },
            }),
            encoding="utf-8",
        )

        index = build_semantic_lemma_index(session)

    rewrites = [
        item for item in index["items"]
        if item.get("lemma") in {"pr_RO_split", "SplitC1.pr_RO_split"}
    ]
    assert len(rewrites) == 2
    assert {
        tuple(item["pr_game_keys"]) for item in rewrites
    } == {
        (
            "Split1.IdealAll.MainD(D,Split1.IdealAll.RO)",
            "Split1.IdealAll.MainD(D,RO_Pair(I1.RO,I2.RO))",
        ),
        (
            "Split0.IdealAll.MainD(D,Split0.IdealAll.RO)",
            "Split0.IdealAll.MainD(D,SplitC1.RO_Pair(SplitC1.I1.RO,SplitC1.I2.RO))",
        ),
    }


def test_semantic_bound_candidates_match_bound_goal_without_bound_name() -> None:
    with tempfile.TemporaryDirectory() as td:
        session = Path(td)
        _write_context(session)
        index = build_semantic_lemma_index(session)
        candidates = semantic_pr_bound_candidates(
            index,
            parsed={"goal_type": "probability", "prob_form": "ineq"},
            goal_type="probability",
            goal_text=(
                "Pr[Game(A, PLog).main() @ &m : Bad P.logP F.m] <= eps"
            ),
        )

    assert candidates
    assert candidates[0]["lemma"] == "OddlyNamedBound"


def test_source_declarations_by_name_uses_semantic_index() -> None:
    with tempfile.TemporaryDirectory() as td:
        session = Path(td)
        _write_context(session)
        index = build_semantic_lemma_index(session)
        found = source_declarations_by_name(index, ["OddlyNamedBound"])

    assert "OddlyNamedBound" in found
    assert "Bad P.logP F.m" in found["OddlyNamedBound"]["declaration"]


def test_ec_native_where_artifact_overrides_source_scan_fallback() -> None:
    with tempfile.TemporaryDirectory() as td:
        session = Path(td)
        (session / "context.ec").write_text(
            "lemma ShadowBound &m :\n"
            "  Pr[Game(A, SourceOnly).main() @ &m : res] <= eps.\n"
            "proof. by smt(). qed.\n",
            encoding="utf-8",
        )
        tool_views = session / "tool_views"
        tool_views.mkdir()
        where_output = """\
[WHERE-HIT] ShadowBound  (kind: lemma)
* In [lemmas or axioms]:

lemma ShadowBound &m :
  Pr[Game(A, NativeTruth).main() @ &m : res] <= eps.
"""
        (tool_views / "where_shadow.json").write_text(
            json.dumps({
                "tool": "where",
                "debug": {"legacy_text": where_output},
                "evidence": {
                    "context": [{"query": {"name": "ShadowBound"}}],
                    "raw": [],
                },
            }),
            encoding="utf-8",
        )

        index = build_semantic_lemma_index(session)
        by_name = {
            str(item.get("lemma") or ""): item
            for item in index["items"]
        }
        candidates = semantic_pr_bound_candidates(
            index,
            parsed={"goal_type": "probability", "prob_form": "ineq"},
            goal_type="probability",
            goal_text="Pr[Game(A, NativeTruth).main() @ &m : res] <= eps",
        )

    item = by_name["ShadowBound"]
    assert item["ec_ground_truth"] is True
    assert item["fact_source"] == "ec_native_print"
    assert "NativeTruth" in item["declaration"]
    assert "SourceOnly" not in item["declaration"]
    assert candidates[0]["lemma"] == "ShadowBound"
    assert candidates[0]["ec_ground_truth"] is True


def test_ec_native_where_artifact_splits_clone_rewrite_blocks() -> None:
    with tempfile.TemporaryDirectory() as td:
        session = Path(td)
        tool_views = session / "tool_views"
        tool_views.mkdir()
        where_output = """\
[WHERE-HIT-VIA-CLONE] pr_split -> Split0.pr_split  (kind: lemma)
* In [lemmas or axioms]:

(* Split0.pr_split *)
lemma pr_split &m :
  Pr[MainD(D, O0).run() @ &m : res] =
  Pr[MainD(D, O1).run() @ &m : res].

(* Split1.pr_split *)
lemma pr_split &m :
  Pr[MainD(D, O1).run() @ &m : res] =
  Pr[MainD(D, O2).run() @ &m : res].
"""
        (tool_views / "where_pr_split.json").write_text(
            json.dumps({
                "tool": "where",
                "debug": {"legacy_text": where_output},
                "evidence": {
                    "context": [{"query": {"name": "pr_split"}}],
                    "raw": [],
                },
            }),
            encoding="utf-8",
        )

        index = build_semantic_lemma_index(session)
        candidates = semantic_pr_rewrite_candidates(
            index,
            parsed={"goal_type": "probability"},
            goal_text=(
                "Pr[MainD(D, O0).run() @ &m : res] = "
                "Pr[MainD(D, O2).run() @ &m : res]"
            ),
            max_results=8,
        )

    by_name = {str(item.get("lemma") or ""): item for item in index["items"]}
    assert "Split0.pr_split" in by_name
    assert "Split1.pr_split" in by_name
    assert by_name["Split0.pr_split"]["ec_ground_truth"] is True
    assert "pr_rewrite" in by_name["Split0.pr_split"]["semantic_tags"]
    assert [item["lemma"] for item in candidates] == [
        "Split0.pr_split",
        "Split1.pr_split",
    ]


def test_ec_native_search_artifact_can_seed_semantic_index() -> None:
    with tempfile.TemporaryDirectory() as td:
        session = Path(td)
        tool_views = session / "tool_views"
        tool_views.mkdir()
        search_output = """\
[SKELETON-HITS] `search mu predU` -> 1 lemma(s)

lemma OddlyNamedNativeUnion &m :
  Pr[Game(A, NativeSearch).main() @ &m : E1 \\/ E2] <=
  Pr[Game(A, NativeSearch).main() @ &m : E1] +
  Pr[Game(A, NativeSearch).main() @ &m : E2].
"""
        (tool_views / "search_skeleton_mu.json").write_text(
            json.dumps({
                "tool": "search-skeleton",
                "debug": {"legacy_text": search_output},
                "evidence": {
                    "context": [{"query": {"query": "mu predU"}}],
                    "raw": [],
                },
            }),
            encoding="utf-8",
        )

        index = build_semantic_lemma_index(session)
        candidates = semantic_pr_bound_candidates(
            index,
            parsed={"goal_type": "probability", "prob_form": "ineq"},
            goal_type="probability",
            goal_text=(
                "Pr[Game(A, NativeSearch).main() @ &m : E1 \\/ E2] <= "
                "Pr[Game(A, NativeSearch).main() @ &m : E1] + "
                "Pr[Game(A, NativeSearch).main() @ &m : E2]"
            ),
        )

    assert candidates
    assert candidates[0]["lemma"] == "OddlyNamedNativeUnion"
    assert candidates[0]["fact_source"] == "ec_native_search"


def test_proof_ir_surfaces_semantic_bound_lookup_menu_item() -> None:
    with tempfile.TemporaryDirectory() as td:
        session = Path(td)
        _write_context(session)
        goal = "Pr[Game(A, PLog).main() @ &m : Bad P.logP F.m] <= eps"
        proof_ir = build_proof_ir(
            session_dir=session,
            proof_state={},
            current_goal={
                "goal_type": "probability",
                "active_goal_preview": goal,
                "parsed_goal": {
                    "goal_type": "probability",
                    "prob_form": "ineq",
                    "raw_text": goal,
                },
            },
        )

    handles = proof_ir["resources"]["handles"]
    assert handles["semantic_pr_bound_candidates"][0]["lemma"] == "OddlyNamedBound"
    assert any(
        item.get("tactic") == "-where OddlyNamedBound"
        for item in proof_ir["candidate_menu"]
    )


def test_prg_static_smoke_finds_project_bound_lemma_by_shape() -> None:
    with tempfile.TemporaryDirectory() as td:
        session = Path(td)
        source = ROOT / "eval" / "examples" / "PRG.ec"
        (session / "session_meta.json").write_text(
            f'{{"file": "{source}"}}',
            encoding="utf-8",
        )
        index = build_semantic_lemma_index(session, include_imported=False)
        candidates = semantic_pr_bound_candidates(
            index,
            parsed={"goal_type": "probability", "prob_form": "ineq"},
            goal_type="probability",
            goal_text=(
                "Pr[Exp(A,F,Plog).main() @ &m: res] <= "
                "Pr[Exp(A,F,Psample).main() @ &m: res] + "
                "Pr[Exp(A,F,Psample).main() @ &m: Bad P.logP F.m]"
            ),
        )

    assert any(item["lemma"] == "Plog_Psample" for item in candidates)


def test_br93_static_smoke_finds_project_bound_lemma_by_shape() -> None:
    with tempfile.TemporaryDirectory() as td:
        session = Path(td)
        source = ROOT / "eval" / "examples" / "br93.ec"
        (session / "session_meta.json").write_text(
            f'{{"file": "{source}"}}',
            encoding="utf-8",
        )
        index = build_semantic_lemma_index(session, include_imported=False)
        candidates = semantic_pr_bound_candidates(
            index,
            parsed={"goal_type": "probability", "prob_form": "ineq"},
            goal_type="probability",
            goal_text=(
                "Pr[BR93_CPA(A).main() @ &m : res] <= "
                "Pr[Game1.main() @ &m : res] + "
                "Pr[Game1.main() @ &m : Game1.r \\in Log.qs]"
            ),
        )

    assert any(item["lemma"] == "pr_Game0_Game1" for item in candidates)


def test_mechanical_goal_candidates_match_project_rewrite_head() -> None:
    index = {
        "items": [{
            "lemma": "gen_CTR_encrypt_bytes_cons",
            "declaration_kind": "lemma",
            "declaration": (
                "lemma gen_CTR_encrypt_bytes_cons f k n i (p : message) : "
                "gen_CTR_encrypt_bytes f k n i p = "
                "head p ++ gen_CTR_encrypt_bytes f k n (i + 1) (tail p)."
            ),
            "authority": "source_scan_fallback",
        }],
    }

    matches = mechanical_goal_candidates(
        index,
        goal_text=(
            "H: p <> []\n----\n"
            "r = gen_CTR_encrypt_bytes take_xor cc k n i p"
        ),
    )

    assert matches[0]["lemma"] == "gen_CTR_encrypt_bytes_cons"
    assert matches[0]["match_kind"] == "loaded_rewrite_head"
    assert matches[0]["rewrite_head"] == "gen_CTR_encrypt_bytes"


def test_mechanical_goal_candidates_drop_ambiguous_bound_only_head_family() -> None:
    index = {
        "items": [
            {
                "lemma": "cbc_step_a",
                "declaration_kind": "lemma",
                "declaration": "lemma cbc_step_a m p i : cbc m p i = Some witness.",
            },
            {
                "lemma": "cbc_step_b",
                "declaration_kind": "lemma",
                "declaration": "lemma cbc_step_b m p i : cbc m p i = p.[i].",
            },
        ],
    }

    matches = mechanical_goal_candidates(
        index,
        goal_text="----\ncbc message table n = table.[key]",
    )

    assert matches == []


def test_mechanical_goal_candidates_require_fixed_literal_near_rewrite_head() -> None:
    index = {
        "items": [{
            "lemma": "invr0",
            "declaration_kind": "lemma",
            "declaration": "lemma invr0 : inv 0%r = 0%r.",
        }],
    }

    assert mechanical_goal_candidates(
        index,
        goal_text="h: 0 <= k\n----\nvalue = inv bound%r",
    ) == []
    assert mechanical_goal_candidates(
        index,
        goal_text=(
            "----\nmu [1..4] (fun (x : int) => x = k) = "
            "if 1 <= k <= 4 then inv 4%r else 0%r"
        ),
    ) == []
    assert mechanical_goal_candidates(
        index,
        goal_text="----\ninv 0%r = 0%r",
    )[0]["lemma"] == "invr0"


def test_mechanical_goal_candidates_leave_broad_heads_to_structural_producer() -> None:
    index = {
        "items": [{
            "lemma": "nth_map",
            "declaration_kind": "lemma",
            "declaration": (
                "lemma nth_map ['a 'b] (d : 'a) (f : 'a -> 'b) (s : 'a list) i : "
                "nth (f d) (map f s) i = f (nth d s i)."
            ),
            "authority": "source_scan_fallback",
        }],
    }

    nested = mechanical_goal_candidates(
        index,
        goal_text="----\nnth z (map f xs) i = f (nth d xs i)",
    )
    bare = mechanical_goal_candidates(
        index,
        goal_text="----\nnth d xs i = x",
    )

    assert nested == []
    assert bare == []


def test_mechanical_goal_candidates_do_not_treat_bare_variable_as_rewrite_head() -> None:
    index = {
        "items": [{
            "lemma": "lez_anti",
            "declaration_kind": "lemma",
            "declaration": "lemma lez_anti x y : x <= y <= x => x = y by smt().",
            "authority": "source_scan_fallback",
        }],
    }

    matches = mechanical_goal_candidates(
        index,
        goal_text="----\ntt = tt /\\ m.[x <- y] = m.[x <- y]",
    )

    assert matches == []


def test_mechanical_goal_candidates_require_nested_lhs_shape() -> None:
    index = {
        "items": [{
            "lemma": "toofwords",
            "declaration_kind": "lemma",
            "declaration": (
                "lemma toofwords (x : words) : towords (ofwords x) = x."
            ),
            "authority": "source_scan_fallback",
        }],
    }

    bare = mechanical_goal_candidates(
        index,
        goal_text="----\ntowords padded \notin log",
    )
    nested = mechanical_goal_candidates(
        index,
        goal_text="----\ntowords (ofwords message) = message",
    )

    assert bare == []
    assert nested[0]["lemma"] == "toofwords"
    assert nested[0]["rewrite_shape"]["declaration_side"] == "lhs"


def test_mechanical_goal_candidates_do_not_match_result_constructor_rhs() -> None:
    index = {
        "items": [{
            "lemma": "ohead_cons",
            "declaration_kind": "lemma",
            "declaration": "lemma ohead_cons x xs : ohead (x :: xs) = Some x.",
            "authority": "source_scan_fallback",
        }],
    }

    matches = mechanical_goal_candidates(
        index,
        goal_text="----\nmap.[k] = Some value",
    )

    assert matches == []


def test_mechanical_goal_candidates_bind_loaded_left_inverse_to_map_transport() -> None:
    index = {
        "items": [{
            "lemma": "decode_encode",
            "declaration_kind": "lemma",
            "declaration": (
                "lemma decode_encode (x : source) : decode (encode x) = x."
            ),
            "authority": "source_scan_fallback",
        }],
    }
    goal = r"""
Current goal
------------------------------------------------------------
forall x,
  left.[x] = right.[encode x] =>
  left.[next <- value].[x] = right.[encode next <- value].[encode x]
"""

    matches = mechanical_goal_candidates(index, goal_text=goal)

    support = next(item for item in matches if item["lemma"] == "decode_encode")
    assert support["match_kind"] == "loaded_left_inverse_support"
    assert support["transform"] == "encode"
    assert support["inverse"] == "decode"


def test_loaded_left_inverse_is_not_surfaced_without_map_transport_shape() -> None:
    index = {
        "items": [{
            "lemma": "decode_encode",
            "declaration_kind": "lemma",
            "declaration": "lemma decode_encode (x : source) : decode (encode x) = x.",
            "authority": "source_scan_fallback",
        }],
    }

    assert mechanical_goal_candidates(
        index,
        goal_text="----\nencode message = encoded",
    ) == []


def test_mechanical_goal_candidates_do_not_match_map_update_shape_alone() -> None:
    index = {
        "items": [{
            "lemma": "size_set",
            "declaration_kind": "lemma",
            "declaration": (
                "lemma size_set (m : ('a, 'b) fmap) (a : 'a) (b : 'b) : "
                "size m.[a <- b] = if a \\in m then size m else size m + 1."
            ),
            "authority": "source_scan_fallback",
        }],
    }

    matches = mechanical_goal_candidates(
        index,
        goal_text=(
            "----\n"
            "oget log.[key <- value].[key] \\in allowed"
        ),
    )

    assert matches == []


def test_mechanical_goal_candidates_do_not_match_fixed_argument_at_wrong_depth() -> None:
    index = {
        "items": [{
            "lemma": "ofwords_witness",
            "declaration_kind": "lemma",
            "declaration": "lemma ofwords_witness : ofwords witness = witness.",
            "authority": "source_scan_fallback",
        }],
    }

    matches = mechanical_goal_candidates(
        index,
        goal_text="----\nofwords (nth witness xs i) = y",
    )

    assert matches == []


def test_high_precision_pr_bound_routes_keep_route_set_and_drop_noise() -> None:
    goal = (
        "Pr[G0.main() @ &m : res] <= "
        "Pr[G1.main() @ &m : res] + Pr[G2.main() @ &m : bad]"
    )
    candidates = [
        {
            "lemma": "reduction",
            "pr_game_keys": ["G0", "G1", "G2"],
            "semantic_tags": ["pr_bound", "pr_additive_bound"],
            "required_premises": ["0 <= eps"],
            "score": 18,
        },
        {
            "lemma": "Bound_G1",
            "pr_game_keys": ["G1", "H1"],
            "semantic_tags": ["pr_bound"],
            "score": 15,
        },
        {
            "lemma": "Bound_G2",
            "pr_game_keys": ["G2", "H2"],
            "semantic_tags": ["pr_bound"],
            "score": 13,
        },
        {
            "lemma": "Unrelated",
            "pr_game_keys": ["Other.main", "Other2.main", "Other3.main"],
            "semantic_tags": ["pr_bound", "pr_additive_bound"],
            "score": 10,
        },
    ]

    routes = high_precision_pr_bound_routes(candidates, goal_text=goal)

    assert [item["lemma"] for item in routes] == [
        "reduction", "Bound_G1", "Bound_G2",
    ]
    assert routes[0]["route_role"] == "outer_bound_decomposition"
    assert routes[0]["required_premises"] == ["0 <= eps"]
    assert {item["route_role"] for item in routes[1:]} == {
        "exact_visible_term_bound"
    }


def test_high_precision_pr_bound_routes_match_bound_module_instantiation() -> None:
    goal = (
        "Pr[Outer(QueryBounder(A)).main() @ &m : res] <= "
        "Pr[Inner(QueryBounder(A)).main() @ &m : res] + eps"
    )
    candidates = [
        {
            "lemma": "reduction",
            "declaration": (
                "lemma reduction (A <: Adv) &m : "
                "Pr[Outer(A).main() @ &m : res] <= "
                "Pr[Inner(A).main() @ &m : res] + Pr[Bad(A).main() @ &m : bad]."
            ),
            "pr_game_keys": ["Outer(A)", "Inner(A)", "Bad(A)"],
            "semantic_tags": ["pr_bound", "pr_additive_bound"],
            "score": 12,
        },
        {
            "lemma": "similar_but_different_game",
            "declaration": (
                "lemma similar_but_different_game (A <: Adv) &m : "
                "Pr[Other(A).main() @ &m : res] <= "
                "Pr[Inner(A).main() @ &m : res] + Pr[Bad(A).main() @ &m : bad]."
            ),
            "pr_game_keys": ["Other(A)", "Inner(A)", "Bad(A)"],
            "semantic_tags": ["pr_bound", "pr_additive_bound"],
            "score": 12,
        },
    ]

    routes = high_precision_pr_bound_routes(candidates, goal_text=goal)

    assert [item["lemma"] for item in routes] == ["reduction"]
    assert routes[0]["parameter_bindings"] == {"A": "QueryBounder(A)"}
    assert routes[0]["parameterized_goal_endpoints"] == [
        "Outer(QueryBounder(A))", "Inner(QueryBounder(A))",
    ]


def test_source_index_keeps_enclosing_section_module_parameter() -> None:
    with tempfile.TemporaryDirectory() as td:
        session = Path(td)
        (session / "context.ec").write_text(
            "section S.\n"
            "declare module Adv <: Distinguisher.\n"
            "lemma Bound &m : Pr[G(Adv).main() @ &m : res] <= "
            "Pr[H(Adv).main() @ &m : res] + eps.\n"
            "proof. admit. qed.\n"
            "end section S.\n",
            encoding="utf-8",
        )
        index = build_semantic_lemma_index(session)

    bound = next(item for item in index["items"] if item["lemma"] == "Bound")
    assert bound["module_parameters"] == ["Adv"]
    candidates = semantic_pr_bound_candidates(
        index,
        goal_type="probability",
        goal_text=(
            "Pr[G(B(Adv)).main() @ &m : res] <= "
            "Pr[H(B(Adv)).main() @ &m : res] + eps"
        ),
    )
    indexed_bound = next(item for item in candidates if item["lemma"] == "Bound")
    assert indexed_bound["module_parameters"] == ["Adv"]


def test_pr_bound_route_matches_enclosing_section_module_instantiation() -> None:
    goal = (
        "`|Pr[G(B(Adv)).main() @ &m : res] - "
        "Pr[H(B(Adv)).main() @ &m : res]| <= x + y"
    )
    routes = high_precision_pr_bound_routes([{
        "lemma": "Bound",
        "declaration": (
            "lemma Bound &m : `|Pr[G(Adv).main() @ &m : res] - "
            "Pr[H(Adv).main() @ &m : res]| <= x + y."
        ),
        "module_parameters": ["Adv"],
        "pr_game_keys": ["G(Adv)", "H(Adv)"],
        "semantic_tags": ["pr_bound", "pr_additive_bound"],
        "required_premises": ["initialisation sigma q"],
        "score": 11,
    }], goal_text=goal)

    assert [item["lemma"] for item in routes] == ["Bound"]
    assert routes[0]["parameter_bindings"] == {"Adv": "B(Adv)"}
    assert routes[0]["parameterized_goal_endpoints"] == [
        "G(B(Adv))", "H(B(Adv))",
    ]


def test_single_endpoint_bound_is_not_a_route_for_non_additive_pr_goal() -> None:
    routes = high_precision_pr_bound_routes(
        [{
            "lemma": "bound_left_only",
            "pr_game_keys": ["Left", "Other"],
            "semantic_tags": ["pr_bound"],
            "score": 12,
        }],
        goal_text="Pr[Left.main() @ &m : res] <= Pr[Right.main() @ &m : res]",
    )

    assert routes == []


def test_one_sided_losslessness_matches_module_binding_and_rejects_similar_routes() -> None:
    index = {
        "items": [
            {
                "lemma": "Alossless_F",
                "declaration": (
                    "lemma Alossless_F (O <: PRF_Oracles{-Adv_MAC_to_F(A)}) : "
                    "islossless O.f => islossless Adv_MAC_to_F(A, O).guess."
                ),
                "source": "session_context",
                "source_path": "/tmp/context.ec",
                "module_parameters": ["A"],
                "authority": "source_scan_fallback",
                "authority_rank": 10,
            },
            {
                "lemma": "Alossless",
                "declaration": (
                    "axiom Alossless (O <: OMac{-A}) : "
                    "islossless O.mac => islossless A(O).guess."
                ),
                "source": "session_context",
                "module_parameters": ["A"],
            },
            {
                "lemma": "Alossless_guess_main",
                "declaration": (
                    "lemma Alossless_guess_main (O <: OMac{-Guess_to_Main(A)}) : "
                    "islossless O.mac => islossless Guess_to_Main(A, O).main."
                ),
                "source": "session_context",
                "module_parameters": ["A"],
            },
        ]
    }

    candidates = semantic_one_sided_losslessness_candidates(
        index,
        procedures=["Adv_MAC_to_F(A, D2(O).O).guess"],
        target_lemma="Alossless_D2",
    )

    assert [item["lemma"] for item in candidates] == ["Alossless_F"]
    assert candidates[0]["parameter_bindings"] == {"O": "D2(O).O"}
    assert candidates[0]["required_premises"] == ["islossless D2(O).O.f"]
    assert candidates[0]["declared_procedure"] == "Adv_MAC_to_F(A, O).guess"
    assert candidates[0]["module_argument_terms"] == {"O": "<: D2(O).O"}
    assert candidates[0]["instantiated_lemma_head"] == (
        "Alossless_F (<: D2(O).O)"
    )
    assert candidates[0]["proof_argument_placeholders"] == ["_"]
    assert candidates[0]["call_template"] == (
        "call (Alossless_F (<: D2(O).O) _)."
    )


def test_one_sided_losslessness_requires_same_procedure_leaf() -> None:
    index = {"items": [{
        "lemma": "Alossless_F",
        "declaration": (
            "lemma Alossless_F (O <: PRF_Oracles{-Adv_MAC_to_F(A)}) : "
            "islossless O.f => islossless Adv_MAC_to_F(A, O).guess."
        ),
        "source": "session_context",
        "module_parameters": ["A"],
    }]}

    assert semantic_one_sided_losslessness_candidates(
        index,
        procedures=["Adv_MAC_to_F(A, D2(O).O).main"],
    ) == []


def test_one_sided_losslessness_does_not_rebind_ambient_section_module() -> None:
    index = {"items": [{
        "lemma": "losslessEPRPf",
        "declaration": "axiom losslessEPRPf : islossless EPRF.f.",
        "source": "source_file",
        "module_parameters": ["EPRF", "A"],
        "authority": "source_scan_fallback",
        "ec_ground_truth": False,
    }]}

    assert semantic_one_sided_losslessness_candidates(
        index,
        procedures=["D2(O).F0.f", "PRFpadded.f", "RP_RF1.PRPi.PRPi.f"],
    ) == []

    exact = semantic_one_sided_losslessness_candidates(
        index,
        procedures=["EPRF.f"],
    )
    assert [item["lemma"] for item in exact] == ["losslessEPRPf"]
    assert exact[0]["match_kind"] == "exact_procedure"


def test_distribution_losslessness_binds_loaded_certificate_to_weight_goal() -> None:
    index = {"items": [
        {
            "lemma": "dword_ll",
            "declaration_kind": "axiom",
            "declaration": "axiom dword_ll : is_lossless dword.",
            "source": "source_file",
        },
        {
            "lemma": "dblock_ll",
            "declaration_kind": "axiom",
            "declaration": "axiom dblock_ll : is_lossless dblock.",
            "source": "source_file",
        },
    ]}

    candidates = semantic_distribution_certificates(
        index,
        goal_text="Current goal\n----\nweight dword = 1%r",
    )

    assert [item["lemma"] for item in candidates] == ["dword_ll"]
    assert candidates[0]["certificate_kind"] == "distribution_losslessness"
    assert candidates[0]["distribution"] == "dword"
    assert candidates[0]["declared_conclusion"] == "is_lossless dword"


def test_distribution_losslessness_does_not_match_broad_weight_family() -> None:
    index = {"items": [{
        "lemma": "other_weight",
        "declaration_kind": "lemma",
        "declaration": "lemma other_weight : weight other = 1%r.",
    }]}

    assert semantic_distribution_certificates(
        index,
        goal_text="Current goal\n----\nweight dword = 1%r",
    ) == []


def test_interval_point_mass_binds_identity_and_loaded_cardinality_fact() -> None:
    index = {"items": [
        {
            "lemma": "dinter1E",
            "declaration_kind": "lemma",
            "declaration": (
                "lemma dinter1E (i j : int) x: "
                "mu1 (dinter i j) x = "
                "if (i <= x <= j) then 1%r/(j - i + 1)%r else 0%r."
            ),
            "source": "imported_theory",
        },
        {
            "lemma": "bound_pos",
            "declaration_kind": "axiom",
            "declaration": "axiom bound_pos : 0 < bound.",
            "source": "source_file",
        },
        {
            "lemma": "other_pos",
            "declaration_kind": "axiom",
            "declaration": "axiom other_pos : 0 < other.",
            "source": "source_file",
        },
    ]}

    candidates = semantic_distribution_certificates(
        index,
        goal_text=(
            "Current goal\n----\n"
            "mu1 [0..bound - 1] (if 0 <= k < bound then k else 0) = "
            "inv bound%r"
        ),
    )

    assert [item["lemma"] for item in candidates] == ["dinter1E"]
    candidate = candidates[0]
    assert candidate["certificate_kind"] == "finite_interval_point_mass"
    assert candidate["interval_cardinality"] == "bound"
    assert candidate["parameter_bindings"]["i"] == "0"
    assert candidate["parameter_bindings"]["j"] == "bound - 1"
    assert [item["lemma"] for item in candidate["loaded_supporting_facts"]] == [
        "bound_pos"
    ]


def test_interval_point_mass_canonicalises_mu_predicate_forms() -> None:
    index = {"items": [{
        "lemma": "dinter1E",
        "declaration_kind": "lemma",
        "declaration": (
            "lemma dinter1E (i j : int) x: "
            "mu1 (dinter i j) x = "
            "if (i <= x <= j) then 1%r/(j - i + 1)%r else 0%r."
        ),
    }]}

    for point_mass in (
        "mu [1..4] (fun (x : int) => x = k)",
        "mu [1..4] (fun x => k = x)",
        "mu [1..4] (pred1 k)",
    ):
        candidates = semantic_distribution_certificates(
            index,
            goal_text=(
                f"Current goal\n----\n{point_mass} = "
                "if 1 <= k <= 4 then inv 4%r else 0%r"
            ),
        )

        assert [item["lemma"] for item in candidates] == ["dinter1E"]
        assert candidates[0]["point"] == "k"
        assert candidates[0]["parameter_bindings"] == {
            "i": "1",
            "j": "4",
            "x": "k",
        }


def test_interval_point_mass_is_absent_without_visible_interval_mu1_term() -> None:
    index = {"items": [{
        "lemma": "dinter1E",
        "declaration_kind": "lemma",
        "declaration": (
            "lemma dinter1E (i j : int) x: "
            "mu1 (dinter i j) x = if (i <= x <= j) then 1%r else 0%r."
        ),
    }]}

    assert semantic_distribution_certificates(
        index,
        goal_text="Current goal\n----\nsize xs = n",
    ) == []
