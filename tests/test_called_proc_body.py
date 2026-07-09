#!/usr/bin/env python3
"""(C) Surface a CALLED procedure's body in-protocol, resolving functor aliases.

Found 2026-05-30 (live step4_badi): at a `call (_: <inv>)` over a compound game
procedure (`CPA_game(...).main()`), the agent needed the procedure's body to
choose the invariant; the view didn't surface it, so it read source (and got
killed by the IO policy). This extracts the body statically. Functor-alias aware:
`module CPA_game(A,O) = CCA_game(A,O).` resolves to `CCA_game.main`.

Family-agnostic (synthetic names). Run:
  python3 -m pytest tests/test_called_proc_body.py -q
"""
from __future__ import annotations

import sys
from pathlib import Path

import _pathsetup  # noqa: F401,E402  (repo root on sys.path)
from core.easycrypt.analysis.ec_called_proc_body import (  # noqa: E402
    called_module_proc, extract_called_proc_body)

_SRC = """
module Inner(A : Adv, O : Or) = {
  proc run () = {
    var x;
    O.init();
    x <@ A(O).go();
    return x;
  }
}.
module Outer(A : Adv, O : Or) = Inner(A, O).
"""


def test_parse_call_statement():
    assert called_module_proc("z <@ Outer(Adv1(B), G.O).run()") == ("Outer", "run")
    assert called_module_proc("b <@ Mod(X(Y(A)), U.O).main()") == ("Mod", "main")
    assert called_module_proc("no call here") is None


def test_resolves_functor_alias_to_body():
    res = extract_called_proc_body([(_SRC, "x.ec")], "Outer", "run")
    assert res is not None
    assert res["alias_chain"] == ["Outer", "Inner"]   # alias followed
    assert "O.init()" in res["body"] and "A(O).go()" in res["body"]
    assert res["source"] == "x.ec"


def test_direct_module_body():
    res = extract_called_proc_body([(_SRC, "x.ec")], "Inner", "run")
    assert res is not None and res["module"] == "Inner"
    assert "x <@ A(O).go()" in res["body"]


def test_missing_module_or_proc_returns_none():
    assert extract_called_proc_body([(_SRC, "x.ec")], "Nope", "run") is None
    assert extract_called_proc_body([(_SRC, "x.ec")], "Inner", "nope") is None
