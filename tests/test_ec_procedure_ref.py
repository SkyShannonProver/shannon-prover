"""Tests for shared EasyCrypt procedure-reference helpers."""
from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from core.easycrypt.analysis.ec_procedure_ref import (  # noqa: E402
    parse_call_argument_site,
    parse_call_statement,
    parse_procedure_application,
    procedure_application_key,
    procedure_exact_key,
    procedure_spine_key,
    procedure_tail_key,
)


def test_parse_call_statement_keeps_functor_proc_and_value_args_separate() -> None:
    call = parse_call_statement("x <@ D(A, O).O.Poly.mac(n, a, c); y <- z;")

    assert call is not None
    assert call.procedure == "D(A, O).O.Poly.mac"
    assert call.arguments == ("n", "a", "c")


def test_parse_call_argument_site_preserves_legacy_value_arg_shape() -> None:
    call = parse_call_argument_site("x <@ D(A, O).O.Poly.mac(n, a, c);")

    assert call is not None
    assert call.procedure == "D(A, O).O.Poly.mac"
    assert call.arguments == ("n", "a", "c")

    paren_call = parse_call_argument_site("x <@ (M.f);")
    assert paren_call is not None
    assert paren_call.procedure == ""
    assert paren_call.arguments == ("M.f",)


def test_parse_call_argument_site_recovers_procedure_from_unclosed_args() -> None:
    call = parse_call_argument_site("x <@ M.f(n, a;")

    assert call is not None
    assert call.procedure == "M.f"
    assert call.arguments == ()


def test_parse_procedure_application_uses_final_top_level_argument_list() -> None:
    call = parse_procedure_application("Left(RO).enc(k, n, p)")

    assert call.procedure == "Left(RO).enc"
    assert call.arguments == ("k", "n", "p")
    assert parse_procedure_application("Left(RO).enc").procedure == "Left(RO).enc"


def test_procedure_keys_separate_exact_spine_and_application_matching() -> None:
    proc = "D(A, O).O.Poly.mac(n, a, c)"

    assert procedure_exact_key(proc) == "D(A,O).O.Poly.mac(n,a,c)"
    assert procedure_spine_key(proc) == "D.O.Poly.mac"
    assert procedure_application_key(proc) == "Poly.mac"


def test_tail_key_is_depth_aware_for_functor_arguments() -> None:
    proc = "ChaCha(CCRO(A.b)).enc"

    assert procedure_tail_key(proc) == "ChaCha(CCRO(A.b)).enc"
    assert procedure_tail_key(proc, components=1) == "enc"
    assert procedure_tail_key("D4_6.SampleE.sample") == "SampleE.sample"


def test_outer_parentheses_do_not_destroy_clean_spine_keys() -> None:
    assert procedure_exact_key("(M.f)") == "M.f"
    assert procedure_spine_key("(M.f)") == "M.f"
    assert procedure_tail_key("(M.f)") == "M.f"

    assert procedure_exact_key("(M.f)", strip_outer=False) == "(M.f)"
    assert procedure_spine_key("(M.f)", strip_outer=False) == ""
    assert procedure_tail_key("(M.f)", strip_outer=False) == "(M.f)"


def test_empty_unit_call_shape_is_preserved_only_by_exact_key() -> None:
    assert procedure_exact_key("D4_6.SampleE.sample()") == "D4_6.SampleE.sample()"
    assert procedure_spine_key("D4_6.SampleE.sample()") == "D4_6.SampleE.sample"


def test_legacy_call_statement_parse_can_preserve_outer_parens() -> None:
    call = parse_call_statement("x <@ (M.f);", strip_outer=False)

    assert call is not None
    assert call.procedure == "(M.f)"
    assert call.arguments == ()
