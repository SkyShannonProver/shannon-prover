"""Compiler-layer smoke matrix for benchmark proof styles.

These tests stop short of EasyCrypt proof search.  They pin the compiler facts
that should exist before any prover agent chooses tactics: semantic lemma
recall, Pr obligations, and Pr-layer menu actions.
"""
from __future__ import annotations

import json
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from core.easycrypt.analysis.ec_proof_ir import build_proof_ir  # noqa: E402


@dataclass(frozen=True)
class CompilerSmokeCase:
    label: str
    goal: str
    expected_lemma: str
    source_file: Path | None = None
    context_text: str = ""
    min_score: int = 3
    expected_menu_ids: tuple[str, ...] = ()
    expected_obligation_kinds: tuple[str, ...] = ("pr_semantic_bound_lookup",)


PROJECT_SOURCE_CASES = (
    CompilerSmokeCase(
        label="PRG additive bad-event bound",
        source_file=ROOT / "eval" / "examples" / "PRG.ec",
        expected_lemma="Plog_Psample",
        min_score=15,
        # The `probabilistic_vc_plan` route-PLAN is GUIDANCE (no longer surfaced);
        # the bound-lemma FACTS are asserted via semantic_pr_bound_candidates /
        # pr_obligation_plan above.
        expected_menu_ids=(),
        expected_obligation_kinds=(
            "pr_union_bound_plan",
            "pr_semantic_bound_lookup",
        ),
        goal=(
            "Pr[Exp(A,F,Plog).main() @ &m: res] <= "
            "Pr[Exp(A,F,Psample).main() @ &m: res] + "
            "Pr[Exp(A,F,Psample).main() @ &m: Bad P.logP F.m]"
        ),
    ),
    CompilerSmokeCase(
        label="BR93 union-bound game hop",
        source_file=ROOT / "eval" / "examples" / "br93.ec",
        expected_lemma="pr_Game0_Game1",
        min_score=15,
        # The `probabilistic_vc_plan` route-PLAN is GUIDANCE (no longer surfaced);
        # the bound-lemma FACTS are asserted via semantic_pr_bound_candidates /
        # pr_obligation_plan above.
        expected_menu_ids=(),
        expected_obligation_kinds=(
            "pr_union_bound_plan",
            "pr_semantic_bound_lookup",
        ),
        goal=(
            "Pr[BR93_CPA(A).main() @ &m : res] <= "
            "Pr[Game1.main() @ &m : res] + "
            "Pr[Game1.main() @ &m : Game1.r \\in Log.qs]"
        ),
    ),
    CompilerSmokeCase(
        label="ChaChaPoly numbered step bound",
        source_file=ROOT / "eval" / "examples" / "ChaChaPoly" / "chacha_poly.ec",
        expected_lemma="step2_1",
        min_score=15,
        # The `probabilistic_vc_plan` route-PLAN is GUIDANCE (no longer surfaced);
        # the bound-lemma FACTS are asserted via semantic_pr_bound_candidates /
        # pr_obligation_plan above.
        expected_menu_ids=(),
        expected_obligation_kinds=(
            "pr_union_bound_plan",
            "pr_semantic_bound_lookup",
        ),
        goal=(
            "Pr[CCA_game(A,RealOrcls(OChaChaPoly(IFinRO))).main() @ &m : res] <= "
            "Pr[CPA_game(CCA_CPA_Adv(A), RealOrcls(StLSke(St))).main() @ &m : res] + "
            "Pr[UFCMA(A, St).main() @ &m : "
            "(exists c, c \\in Mem.lc /\\ dec StLSke.gs Mem.k c <> None)]"
        ),
    ),
    CompilerSmokeCase(
        label="MEE-CBC named birthday bound",
        source_file=ROOT / "eval" / "examples" / "MEE-CBC" / "CBC.eca",
        expected_lemma="Bound_by_Birthday",
        min_score=12,
        expected_menu_ids=("semantic_pr_bound_Bound_by_Birthday",),
        goal=(
            "Pr[INDR_CPA_direct(Compute,QueryBounder(A)).main() @ &m: Compute.bad] "
            "<= ((q * ell)^2)%r * mu dBlock (pred1 witness)"
        ),
    ),
)


STYLE_VARIANT_CASES = (
    CompilerSmokeCase(
        label="project lemma has no Pr/bound name hint",
        expected_lemma="Theorem42",
        min_score=12,
        # The `probabilistic_vc_plan` route-PLAN is GUIDANCE (no longer surfaced);
        # the bound-lemma FACTS are asserted via semantic_pr_bound_candidates /
        # pr_obligation_plan above.
        expected_menu_ids=(),
        expected_obligation_kinds=(
            "pr_union_bound_plan",
            "pr_semantic_bound_lookup",
        ),
        context_text=(
            "local lemma Theorem42 &m:\n"
            "  Pr[BR93_CPA(A).main() @ &m : res] <=\n"
            "  Pr[Game1.main() @ &m : res] +\n"
            "  Pr[Game1.main() @ &m : Game1.r \\in Log.qs].\n"
            "proof. by smt(). qed.\n"
        ),
        goal=(
            "Pr[BR93_CPA(A).main() @ &m : res] <= "
            "Pr[Game1.main() @ &m : res] + "
            "Pr[Game1.main() @ &m : Game1.r \\in Log.qs]"
        ),
    ),
    CompilerSmokeCase(
        label="numbered ChaChaPoly-style lemma name",
        expected_lemma="step2_1",
        min_score=12,
        # The `probabilistic_vc_plan` route-PLAN is GUIDANCE (no longer surfaced);
        # the bound-lemma FACTS are asserted via semantic_pr_bound_candidates /
        # pr_obligation_plan above.
        expected_menu_ids=(),
        expected_obligation_kinds=(
            "pr_union_bound_plan",
            "pr_semantic_bound_lookup",
        ),
        context_text=(
            "local lemma step2_1 &m :\n"
            "  Pr[CCA_game(A,RealOrcls(OChaChaPoly(IFinRO))).main() @ &m : res] <=\n"
            "  Pr[CPA_game(CCA_CPA_Adv(A), RealOrcls(StLSke(St))).main() @ &m : res] +\n"
            "  Pr[UFCMA(A, St).main() @ &m : BadEvent].\n"
            "proof. by smt(). qed.\n"
        ),
        goal=(
            "Pr[CCA_game(A,RealOrcls(OChaChaPoly(IFinRO))).main() @ &m : res] <= "
            "Pr[CPA_game(CCA_CPA_Adv(A), RealOrcls(StLSke(St))).main() @ &m : res] + "
            "Pr[UFCMA(A, St).main() @ &m : BadEvent]"
        ),
    ),
    CompilerSmokeCase(
        label="bound lemma name says birthday, not Pr",
        expected_lemma="BirthdayFact",
        min_score=12,
        expected_menu_ids=("semantic_pr_bound_BirthdayFact",),
        context_text=(
            "lemma BirthdayFact &m:\n"
            "  Pr[INDR_CPA_direct(Compute,QueryBounder(A)).main() @ &m: Compute.bad]\n"
            "  <= ((q * ell)^2)%r * mu dBlock (pred1 witness).\n"
            "proof. by smt(). qed.\n"
        ),
        goal=(
            "Pr[INDR_CPA_direct(Compute,QueryBounder(A)).main() @ &m: Compute.bad] "
            "<= ((q * ell)^2)%r * mu dBlock (pred1 witness)"
        ),
    ),
)


def test_project_source_compiler_smoke_matrix_recalls_bound_lemmas() -> None:
    for case in PROJECT_SOURCE_CASES:
        ir = _build_smoke_ir(case)
        _assert_bound_case(case, ir)


def test_mee_cbc_pr_bridge_path_is_discovered_by_endpoint_shape() -> None:
    goal = (
        "Pr[INDR_CPA(IV_Wrap(CBC(PseudoRP)),A).main() @ &m: res] = "
        "Pr[INDR_CPA_direct(CBC_Oracle(PRP),A).main() @ &m: res]"
    )
    with tempfile.TemporaryDirectory(
        dir=ROOT,
        prefix=".tmp_compiler_smoke_",
    ) as td:
        session = Path(td)
        (session / "session_meta.json").write_text(
            json.dumps({
                "file": str(ROOT / "eval" / "examples" / "MEE-CBC" / "CBC.eca"),
            }),
            encoding="utf-8",
        )
        ir = build_proof_ir(
            session_dir=session,
            proof_state={},
            current_goal={
                "goal_type": "probability",
                "active_goal_preview": goal,
                "parsed_goal": {
                    "goal_type": "probability",
                    "prob_form": "eq",
                    "raw_text": goal,
                },
            },
        )

    handles = ir["resources"]["handles"]
    candidates = {
        str(item.get("lemma") or ""): item
        for item in handles.get("pr_rewrite_candidate_details", [])
    }
    assert "success_eq" in candidates
    path = handles["pr_path_plan"]["recommended_path"]
    assert path["status"] == "complete"
    assert path["lemmas"] == ["success_eq"]


def test_lemma_style_variant_matrix_is_not_name_prefix_dependent() -> None:
    for case in STYLE_VARIANT_CASES:
        ir = _build_smoke_ir(case)
        _assert_bound_case(case, ir)


def _build_smoke_ir(case: CompilerSmokeCase) -> dict:
    with tempfile.TemporaryDirectory(
        dir=ROOT,
        prefix=".tmp_compiler_smoke_",
    ) as td:
        session = Path(td)
        if case.context_text:
            (session / "context.ec").write_text(case.context_text, encoding="utf-8")
        if case.source_file is not None:
            (session / "session_meta.json").write_text(
                json.dumps({"file": str(case.source_file)}),
                encoding="utf-8",
            )
        return build_proof_ir(
            session_dir=session,
            proof_state={},
            current_goal={
                "goal_type": "probability",
                "active_goal_preview": case.goal,
                "parsed_goal": {
                    "goal_type": "probability",
                    "prob_form": "ineq",
                    "raw_text": case.goal,
                },
            },
        )
def _assert_bound_case(case: CompilerSmokeCase, ir: dict) -> None:
    assert ir["current_layer"] == "pr", case.label
    assert ir["goal_kind"] == "Pr_ineq", case.label

    handles = ir["resources"]["handles"]
    candidates = {
        str(item.get("lemma") or ""): item
        for item in handles.get("semantic_pr_bound_candidates", [])
    }
    assert case.expected_lemma in candidates, case.label
    candidate = candidates[case.expected_lemma]
    assert int(candidate.get("score") or 0) >= case.min_score, case.label
    tags = set(candidate.get("semantic_tags") or [])
    assert {"pr", "pr_bound", "pr_inequality"} <= tags, case.label

    obligation_plan = handles["pr_obligation_plan"]
    obligation_kinds = {
        str(item.get("kind") or "")
        for item in obligation_plan.get("obligations", [])
    }
    for expected in case.expected_obligation_kinds:
        assert expected in obligation_kinds, case.label

    menu_ids = {str(item.get("id") or "") for item in ir["candidate_menu"]}
    for expected in case.expected_menu_ids:
        assert expected in menu_ids, case.label
    assert "byequiv_bridge" not in menu_ids, case.label
