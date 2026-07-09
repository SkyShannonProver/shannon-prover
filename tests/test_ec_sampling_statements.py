"""Tests for leaf sampling-statement parsers."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from core.easycrypt.analysis.ec_sampling_statements import (  # noqa: E402
    is_sample_statement,
    sample_distribution_leaf,
    sample_statement_distribution,
    sample_statement_var,
)


def test_sampling_statement_var_preserves_simple_and_qualified_modes() -> None:
    assert sample_statement_var({"vars_written": ["s"]}, "ignored") == "s"
    assert sample_statement_var({}, "s <$ dT;") == "s"
    assert sample_statement_var({}, "M.s <$ dT;") == ""
    assert sample_statement_var({}, "M.s <$ dT;", qualified_lhs=True) == "M.s"


def test_sampling_statement_distribution_preserves_call_site_modes() -> None:
    assert sample_statement_distribution({"distribution": "dT.;"}, "s <$ other;") == "dT"
    assert (
        sample_statement_distribution(
            {"distribution": "dT.;"},
            "s <$ other;",
            strip_explicit=False,
        )
        == "dT.;"
    )
    assert sample_statement_distribution({}, "s <$ dT;") == "dT"
    assert sample_statement_distribution({}, "s <$ dT.", strip_fallback=False) == "dT."


def test_sampling_statement_shape_and_leaf_helpers() -> None:
    assert is_sample_statement({"kind": "sample"})
    assert is_sample_statement({"text": "x <$ d;"})
    assert not is_sample_statement({"kind": "assign", "text": "x <- y;"})
    assert sample_distribution_leaf("Distr.duniform xs") == "duniform"
