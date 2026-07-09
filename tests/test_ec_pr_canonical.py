"""Tests for canonical EasyCrypt probability-term parsing."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from core.easycrypt.analysis.ec_pr_canonical import (  # noqa: E402
    endpoint_templates_compatible,
    first_pr_equality_terms,
    format_module_expr,
    game_key,
    module_application_args,
    module_application_parts,
    parse_module_expr,
    parse_pr_terms,
    pr_game_keys_from_text,
    pr_terms_with_spans,
    procedure_endpoint,
)


def test_parse_pr_terms_records_endpoint_memory_event_and_key() -> None:
    terms = parse_pr_terms(
        "Pr[Exp(A, F, Plog).main() @ &m : res] <= "
        "Pr[Exp(A, F, PLog).main() @ &m : Bad P.logP F.m]"
    )

    assert len(terms) == 2
    assert terms[0]["game_expr"] == "Exp(A, F, Plog).main()"
    assert terms[0]["game_key"] == "Exp(A,F,Plog)"
    assert terms[0]["memory"] == "&m"
    assert terms[0]["event"] == "res"
    assert terms[0]["endpoint"] == {
        "module_expr": "Exp(A, F, Plog)",
        "procedure": "main",
        "procedure_args": [],
        "canonical": "Exp(A, F, Plog).main()",
        "module_root": "Exp",
    }
    assert terms[1]["event"] == "Bad P.logP F.m"
    assert terms[1]["game_key"] == "Exp(A,F,PLog)"


def test_parse_pr_terms_can_fill_default_memory_and_event() -> None:
    terms = parse_pr_terms(
        "Pr[G.main()]",
        default_memory="&m",
        default_event="res",
    )

    assert len(terms) == 1
    assert terms[0]["memory"] == "&m"
    assert terms[0]["event"] == "res"
    assert terms[0]["game_key"] == "G"


def test_game_key_preserves_functor_args_and_strips_final_proc_call() -> None:
    assert game_key("Indist.Distinguish(D(A), IndRO).game()") == (
        "Indist.Distinguish(D(A),IndRO)"
    )
    assert pr_game_keys_from_text(
        "Pr[Indist.Distinguish(D(A), IndRO).game() @ &m : res]"
    ) == ["Indist.Distinguish(D(A),IndRO)"]


def test_pr_terms_with_spans_records_balanced_pr_terms() -> None:
    text = (
        "have h: Pr[G(A).main() @ &m : res] = "
        "Pr[H(B(C)).main() @ &m : Bad] /\\ Pr[broken."
    )

    terms = pr_terms_with_spans(text)
    first_start = text.index("Pr[G")
    second_start = text.index("Pr[H")

    assert terms == [
        ("G(A)", first_start, first_start + len("Pr[G(A).main() @ &m : res]")),
        (
            "H(B(C))",
            second_start,
            second_start + len("Pr[H(B(C)).main() @ &m : Bad]"),
        ),
    ]


def test_first_pr_equality_terms_uses_balanced_terms() -> None:
    text = (
        "lemma bridge: "
        "Pr[MainD(D, RO).distinguish(x) @ &m : p (res.[k])] = "
        "Pr[MainD(D, FinRO).distinguish(x) @ &m : p res]."
    )

    terms = first_pr_equality_terms(text)

    assert terms is not None
    left, right = terms
    assert left["game_key"] == "MainD(D,RO)"
    assert right["game_key"] == "MainD(D,FinRO)"
    assert left["endpoint"]["module_expr"] == "MainD(D, RO)"
    assert right["endpoint"]["procedure"] == "distinguish"


def test_endpoint_template_compatibility_ignores_instantiation_args() -> None:
    lemma_endpoint = procedure_endpoint("MainD(D, FinRO).distinguish(x)")
    goal_endpoint = procedure_endpoint("MainD(G2, FinRO).distinguish()")

    assert endpoint_templates_compatible(lemma_endpoint, goal_endpoint)
    assert lemma_endpoint["procedure_args"] == ["x"]
    assert goal_endpoint["procedure_args"] == []


def test_module_application_parts_splits_nested_functor_args() -> None:
    parts = module_application_parts("Wrap.Box.MainD(D(A), RealOrcls(IFinRO)).main")

    assert parts == {
        "root": "Wrap.Box.MainD",
        "args": ["D(A)", "RealOrcls(IFinRO)"],
    }
    assert module_application_args("MainD(D(A), FinRO)") == ["D(A)", "FinRO"]
    assert module_application_parts("PlainModule") == {}
    assert module_application_args("PlainModule") == []


def test_parse_module_expr_round_trips_nested_tree() -> None:
    tree = parse_module_expr("CCA_game(A, RealOrcls(OChaChaPoly(IFinRO)))")

    assert tree == {
        "name": "CCA_game",
        "args": [
            {"name": "A", "args": []},
            {
                "name": "RealOrcls",
                "args": [
                    {
                        "name": "OChaChaPoly",
                        "args": [{"name": "IFinRO", "args": []}],
                    },
                ],
            },
        ],
    }
    assert format_module_expr(tree) == "CCA_game(A, RealOrcls(OChaChaPoly(IFinRO)))"


def test_parse_module_expr_keeps_path_diff_permissive_heads() -> None:
    tree = parse_module_expr("let x = Wrap(A, Inner(B))")

    assert tree == {
        "name": "let x = Wrap",
        "args": [
            {"name": "A", "args": []},
            {
                "name": "Inner",
                "args": [{"name": "B", "args": []}],
            },
        ],
    }
