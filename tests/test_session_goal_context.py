"""Pure-Python tests for session goal-context helpers."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace


import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from core.easycrypt.session_goal_context import (  # type: ignore  # noqa: E402
    extract_module_keywords,
    infer_remaining_goals,
    is_goal_too_large,
    match_equivs_to_calls,
    scan_local_equiv_details,
    scan_local_equiv_lemmas,
    scan_pr_bridge_lemmas,
    scan_prob_ineq_lemmas,
    too_large_warning_block,
)
from core.easycrypt import session_goal_context as package_goal_context  # noqa: E402


def test_package_import_boundary() -> None:
    assert package_goal_context.match_equivs_to_calls(["M.f"], []) == {}


def test_goal_size_warning() -> None:
    assert not is_goal_too_large("small")
    warning = too_large_warning_block("x" * 9000)
    assert "[GOAL-TOO-LARGE]" in warning
    assert "9000 bytes" in warning


def test_local_equiv_and_prob_ineq_scans() -> None:
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "context.ec"
        path.write_text(
            "\n".join([
                "local equiv equ_m : M.f ~ N.f : true ==> true.",
                "local equiv chacha_enc1 : ChaCha.enc ~ ChaCha.enc : true ==> true.",
                "proof. proc. skip. qed.",
                "lemma hop : Pr[G1.main() @ &m : res] <= Pr[G2.main() @ &m : res].",
                "proof. admit. qed.",
            ]),
            encoding="utf-8",
        )

        assert scan_local_equiv_lemmas(path) == ["equ_m", "chacha_enc1"]
        details = scan_local_equiv_details(path)
        assert details[:1] == [{
            "name": "equ_m",
            "lhs_proc": "M.f",
            "rhs_proc": "N.f",
        }]
        assert match_equivs_to_calls(["ChaCha.enc"], details) == {
            "ChaCha.enc": ["chacha_enc1"],
        }
        assert scan_prob_ineq_lemmas(path) == [{
            "name": "hop",
            "lhs_game": "G1",
            "rhs_game": "G2",
        }]
        assert scan_prob_ineq_lemmas(path, exclude_name="hop") == []


def test_extract_module_keywords_expands_wrapped_names() -> None:
    info = SimpleNamespace(
        prob_lhs_game="GenChaChaPoly(OCC(IFinRO))",
        prob_lhs_oracle="",
        prob_rhs_game="Indist.Distinguish",
        prob_rhs_oracle="IndRO",
        diff_eq_lhs_neg_game="",
        diff_eq_rhs_neg_game="",
        prob_compound_lhs=[],
        prob_compound_rhs=[],
    )
    keywords = extract_module_keywords(info)
    assert "GenChaChaPoly" in keywords
    assert "FinRO" in keywords
    assert "IndRO" in keywords


def test_scan_pr_bridge_lemmas() -> None:
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "PROM.ec"
        path.write_text(
            "\n".join([
                "lemma pr_RO_FinRO_D :",
                "  Pr[RO.main() @ &m : res] = Pr[FinRO.main() @ &m : res].",
                "proof. admit. qed.",
            ]),
            encoding="utf-8",
        )
        hits = scan_pr_bridge_lemmas([td], ["RO", "FinRO"])
        assert hits and hits[0]["name"] == "pr_RO_FinRO_D"
        assert hits[0]["matched_keywords"] == ["FinRO"]


def test_scan_pr_bridge_lemmas_uses_endpoint_structure_without_name_hit() -> None:
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "Bridge.eca"
        path.write_text(
            "\n".join([
                "lemma bridge0 &m x (p : bool -> bool):",
                "  Pr[MainD(D, RO).distinguish(x) @ &m : p res] =",
                "  Pr[MainD(D, FinRO).distinguish(x) @ &m : p res].",
                "proof. done. qed.",
            ]),
            encoding="utf-8",
        )
        goal = (
            "Pr[MainD(G2, FinRO).distinguish() @ &m : res] = "
            "Pr[Indist.Distinguish(D(A), IndRO).game() @ &m : res]"
        )

        hits = scan_pr_bridge_lemmas([td], ["IndRO"], goal_text=goal)

        assert hits and hits[0]["name"] == "bridge0"
        assert hits[0]["matched_keywords"] == []
        assert hits[0]["matched_by"] == "endpoint"
        assert hits[0]["structural_score"] > 0
        assert "FinRO" in hits[0]["matched_endpoint_atoms"]


def test_scan_pr_bridge_lemmas_respects_context_availability() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        context = root / "context.ec"
        context.write_text(
            "\n".join([
                "local lemma usable_bridge &m x:",
                "  Pr[MainD(D, RO).distinguish(x) @ &m : res] =",
                "  Pr[MainD(D, FinRO).distinguish(x) @ &m : res].",
                "proof. done. qed.",
            ]),
            encoding="utf-8",
        )
        source = root / "Target.ec"
        source.write_text(
            "\n".join([
                "local lemma step1 &m:",
                "  Pr[MainD(D, RO).distinguish() @ &m : res] =",
                "  Pr[MainD(D, FinRO).distinguish() @ &m : res].",
                "proof. done. qed.",
                "local lemma step2_3 &m:",
                "  Pr[UFCMA_poly(A, FinRO).main() @ &m : res] =",
                "  Pr[MainD(G8(A), RO).distinguish() @ &m : res].",
                "proof. done. qed.",
            ]),
            encoding="utf-8",
        )
        hidden = root / "Hidden.ec"
        hidden.write_text(
            "\n".join([
                "local lemma hidden_local &m x:",
                "  Pr[MainD(D, RO).distinguish(x) @ &m : res] =",
                "  Pr[MainD(D, FinRO).distinguish(x) @ &m : res].",
                "proof. done. qed.",
                "lemma exported_bridge &m x:",
                "  Pr[MainD(D, RO).distinguish(x) @ &m : res] =",
                "  Pr[MainD(D, FinRO).distinguish(x) @ &m : res].",
                "proof. done. qed.",
            ]),
            encoding="utf-8",
        )
        goal = (
            "Pr[MainD(G2, FinRO).distinguish() @ &m : res] = "
            "Pr[Indist.Distinguish(D(A), IndRO).game() @ &m : res]"
        )

        hits = scan_pr_bridge_lemmas(
            [root],
            ["IndRO"],
            goal_text=goal,
            search_files=[context],
            allow_local_files=[context],
            excluded_names={"step1"},
            excluded_files={source},
        )

        names = [hit["name"] for hit in hits]
        assert "usable_bridge" in names
        assert "exported_bridge" in names
        assert "hidden_local" not in names
        assert "step1" not in names
        assert "step2_3" not in names


def test_infer_remaining_goals_from_history() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        history = d / "history.ec"
        history.write_text("proc.\nseq 1 : true.\n", encoding="utf-8")
        session = SimpleNamespace(history=history)
        inferred = infer_remaining_goals(session, 2)
        assert [row["predicted_type"] for row in inferred] == [
            "(inherits prior goal type)",
            "(inherits prior goal type)",
        ]
        assert "Prefix" in inferred[0]["description"]


def test_infer_remaining_goals_have_rewrite_from_history() -> None:
    """Bare `have ->` is intentionally not inferred from history alone.

    EC exposes the equality claim as the current goal, and the continuation is
    too subtle to reconstruct without stepping the proof. This keeps
    remaining-goal diagnostics conservative.
    """
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        history = d / "history.ec"
        history.write_text("have -> : Pr[A] = Pr[B].\n", encoding="utf-8")
        session = SimpleNamespace(history=history)
        inferred = infer_remaining_goals(session, 2)
        assert inferred == []


if __name__ == "__main__":
    test_package_import_boundary()
    test_goal_size_warning()
    test_local_equiv_and_prob_ineq_scans()
    test_extract_module_keywords_expands_wrapped_names()
    test_scan_pr_bridge_lemmas()
    test_scan_pr_bridge_lemmas_uses_endpoint_structure_without_name_hit()
    test_scan_pr_bridge_lemmas_respects_context_availability()
    test_infer_remaining_goals_from_history()
    test_infer_remaining_goals_have_rewrite_from_history()
    print("PASS test_session_goal_context")
