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
