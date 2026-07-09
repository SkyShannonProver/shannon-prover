"""Tests for shared EasyCrypt analysis utility helpers."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from core.easycrypt.analysis.ec_utils import (  # noqa: E402
    is_emit_safe_var,
    is_live_safe_var,
    split_flat_conjuncts,
    split_top_level_conjuncts,
    strip_outer_parens,
)


def test_safe_var_predicates_preserve_emit_and_live_rules() -> None:
    assert is_emit_safe_var("Mem.k")
    assert is_emit_safe_var("x_1")
    assert not is_emit_safe_var("1x")
    assert not is_emit_safe_var("x-1")

    assert is_live_safe_var("Mem.k")
    assert is_live_safe_var("x")
    assert not is_live_safe_var("Glob")


def test_split_flat_conjuncts_keeps_flat_regex_semantics() -> None:
    assert split_flat_conjuncts("a /\\ b && c") == ["a ", " b ", " c"]
    assert split_flat_conjuncts("a /\\\\ b") == ["a ", "\\ b"]
    assert split_flat_conjuncts("a /\\\\ b", include_double_escaped=False) == [
        "a ",
        "\\ b",
    ]


def test_split_top_level_conjuncts_respects_configured_nesting() -> None:
    assert split_top_level_conjuncts("a /\\ (b /\\ c) /\\ d") == [
        "a",
        "(b /\\ c)",
        "d",
    ]
    assert split_top_level_conjuncts(
        "  a\n /\\  [b /\\ c] /\\ d  ",
        collapse_whitespace=True,
    ) == ["a", "[b /\\ c]", "d"]


def test_strip_outer_parens_only_removes_enclosing_layers() -> None:
    assert strip_outer_parens("((a /\\ b))") == "a /\\ b"
    assert strip_outer_parens("(f(x) + g(y))") == "f(x) + g(y)"
    assert strip_outer_parens("(a)(b)") == "(a)(b)"
    assert strip_outer_parens("(a /\\ b") == "(a /\\ b"
