"""Characterization tests for EasyCrypt procedure-reference parsing.

These helpers intentionally do not share one meaning yet.  The tests pin the
current distinctions before consolidating them behind clearer names.
"""
from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from core.easycrypt.analysis.ec_instantiation_binding import (  # noqa: E402
    _application_mentions as inst_application_mentions,
    _application_key as inst_application_key,
    _call_argument_candidates as inst_call_argument_candidates,
    _normalize_proc as inst_normalize_proc,
)
from core.easycrypt.analysis.ec_procedure_ref import (  # noqa: E402
    looks_like_qualified_procedure_application,
    procedure_leaf_token,
    shallow_call_procedure_from_statement,
    split_procedure_module_and_name,
)
from core.easycrypt.analysis.ec_procedure_frontend import (  # noqa: E402
    _normalize_procedure as frontend_normalize_procedure,
    _procedure_from_call_text as frontend_procedure_from_call_text,
    _procedure_tail as frontend_procedure_tail,
)
from core.easycrypt.analysis.ec_program_ir import (  # noqa: E402
    _fallback_proc_from_call_text as program_fallback_proc_from_call_text,
    _normalize_proc as program_normalize_proc,
)
from core.easycrypt.analysis.ec_proof_ir_state import (  # noqa: E402
    _fallback_proc_from_call_text as state_fallback_proc_from_call_text,
)
from core.easycrypt.ec_bridge_lemmas import (  # noqa: E402
    _normalize_proc as bridge_normalize_proc,
    _proc_tail as bridge_proc_tail,
)


def test_program_proc_normalization_is_a_spine_key() -> None:
    proc = "D(A, O).O.Poly.mac(n, a, c)"

    assert program_normalize_proc(proc) == "D.O.Poly.mac"
    assert inst_normalize_proc(proc) == "D(A,O).O.Poly.mac(n,a,c)"
    assert frontend_normalize_procedure(proc) == "D(A,O).O.Poly.mac(n,a,c)"
    assert bridge_normalize_proc(proc) == "D(A, O).O.Poly.mac(n, a, c)"


def test_unit_call_and_outer_paren_handling_differs_by_consumer() -> None:
    assert program_normalize_proc("D4_6.SampleE.sample()") == "D4_6.SampleE.sample"
    assert bridge_normalize_proc("D4_6.SampleE.sample()") == "D4_6.SampleE.sample"
    assert inst_normalize_proc("D4_6.SampleE.sample()") == "D4_6.SampleE.sample()"
    assert frontend_normalize_procedure("D4_6.SampleE.sample()") == (
        "D4_6.SampleE.sample()"
    )

    assert program_normalize_proc("(M.f)") == ""
    assert inst_normalize_proc("(M.f)") == "(M.f)"
    assert frontend_normalize_procedure("(M.f)") == "(M.f)"
    assert bridge_normalize_proc("(M.f)") == "(M.f)"


def test_call_statement_fallbacks_keep_different_procedure_shapes() -> None:
    call = "x <@ D(A, O).O.Poly.mac(n, a, c);"

    assert program_fallback_proc_from_call_text(call) == "D.O.Poly.mac"
    assert state_fallback_proc_from_call_text(call) == "D(A, O).O.Poly.mac"
    assert frontend_procedure_from_call_text(call) == "D"
    assert inst_call_argument_candidates(call) == {
        "procedure": "D(A, O).O.Poly.mac",
        "arguments": ["n", "a", "c"],
    }

    paren_call = "x <@ (M.f);"
    assert program_fallback_proc_from_call_text(paren_call) == ""
    assert state_fallback_proc_from_call_text(paren_call) == "(M.f)"
    assert inst_call_argument_candidates(paren_call) == {
        "procedure": "",
        "arguments": ["M.f"],
    }


def test_simple_call_statement_parsers_agree_on_non_functor_calls() -> None:
    call = "t <@ Poly.mac(n, a, c);"

    assert program_fallback_proc_from_call_text(call) == "Poly.mac"
    assert state_fallback_proc_from_call_text(call) == "Poly.mac"
    assert frontend_procedure_from_call_text(call) == "Poly.mac"
    assert inst_call_argument_candidates(call) == {
        "procedure": "Poly.mac",
        "arguments": ["n", "a", "c"],
    }


def test_call_argument_candidates_keep_legacy_filtering_edges() -> None:
    assert inst_call_argument_candidates("x <@ M.f(n{1}, a{2}, c);") == {
        "procedure": "M.f",
        "arguments": ["n", "a", "c"],
    }
    assert inst_call_argument_candidates("x <@ M.f(n + 1, a, m.[k]);") == {
        "procedure": "M.f",
        "arguments": ["a"],
    }
    assert inst_call_argument_candidates("x <@ M.f(n, a;") == {
        "procedure": "M.f",
        "arguments": [],
    }


def test_application_mentions_keep_legacy_scanner_edges() -> None:
    assert inst_application_mentions(
        "Pr[MainD(D, RO).distinguish(x) @ &m : p res]"
    ) == [
        {"callee": "MainD", "arguments": ["D", "RO"]},
        {"callee": "RO).distinguish", "arguments": ["x"]},
    ]
    assert inst_application_mentions("F(a,,b())") == [
        {"callee": "F", "arguments": ["a", "b()"]},
        {"callee": "b", "arguments": []},
    ]
    assert inst_application_mentions("M.f(a") == []


def test_tail_keys_are_not_yet_one_semantic() -> None:
    assert bridge_proc_tail("D4_6.SampleE.sample") == "SampleE.sample"
    assert bridge_proc_tail("ChaCha(CCRO(A.b)).enc") == "ChaCha(CCRO(A.b)).enc"

    assert frontend_procedure_tail("D4_6.SampleE.sample") == "sample"
    assert frontend_procedure_tail("ChaCha(CCRO(A.b)).enc") == "enc"
    assert inst_application_key("D(A, O).O.Poly.mac") == "Poly.mac"
    assert inst_application_key("(M.f)") == ""


def test_shared_procedure_endpoint_helpers_preserve_legacy_shapes() -> None:
    assert split_procedure_module_and_name("D(A, O).O.Poly.mac()") == (
        "D(A, O).O.Poly",
        "mac",
    )
    assert procedure_leaf_token("D(A, O).O.Poly.mac(n, a, c)") == "n, a, c"
    assert looks_like_qualified_procedure_application("RealOrcls(Gen(O)).init()")
    assert not looks_like_qualified_procedure_application("init()")

    call = "x <@ D(A, O).O.Poly.mac(n, a, c);"
    assert shallow_call_procedure_from_statement(call) == "D"
