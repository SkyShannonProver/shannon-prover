#!/usr/bin/env python3
"""Unit tests for the relational-invariant skeleton parsers.

Pure parsing — no EasyCrypt needed. Family-general: synthetic, arbitrary names
(no ChaChaPoly/MEE tokens) so the pass stays a mechanical structure extractor,
not a per-family hardcode. The key properties under test:
  * a named coupling predicate's parameters are typed and the {1}/{2} side
    pattern is recovered from the parameter names (x1/x2 = pair, lone x1 =
    single), exactly as a relational invariant like inv_cpa is shaped;
  * the state-field footprint (Module.field : type) and local-module aliases
    are recovered.

Run: python3 -m pytest tests/test_ec_relational_invariant.py -q
"""
from __future__ import annotations

import sys
from pathlib import Path

import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from core.easycrypt.analysis import ec_relational_invariant as ri  # type: ignore  # noqa: E402


def _fake_sources(*texts):
    return lambda _sd: [(t, Path("x.ec"), "source") for t in texts]


# A synthetic coupling predicate shaped like a real relational invariant:
# two single (left-side) map params, then three relational pairs.
_SRC = """
  op coupling (a1 : (k, v0) fmap)
          (b1 : (k, v1) fmap)
          (log1 log2 : (c, p) fmap)
          (lc1 lc2 : c list)
          (cnt1 cnt2 : int) =
      log1 = log2 /\\ lc1 = lc2 /\\ cnt1 = cnt2 /\\
      (forall n cc, (n, cc) \\in a1 => n \\in lc1).

  op plain (x : int) = x + 1.

  module StateM (O : Oracles) = {
    var lenc : n list
    var ndec : int
    proc enc() = {}
  }

  module Mem = {
    var log : (c, p) fmap
    var lc  : c list
  }

  local module Rin  = SplitC.I1.RO.
  local module Rout = SplitC.I2.RO.
"""


def test_relational_predicate_sides_recovered(monkeypatch):
    monkeypatch.setattr(ri, "_session_source_texts", _fake_sources(_SRC))
    preds = ri.relational_predicates(None)
    by_name = {p["name"]: p for p in preds}
    assert "coupling" in by_name
    assert "plain" not in by_name              # non-relational op excluded
    cp = by_name["coupling"]
    assert cp["arity"] == 8                     # 2 singles + 3 pairs = 8 params
    kinds = [(p["kind"], p["base"]) for p in cp["params"]]
    assert kinds == [
        ("single", "a1"), ("single", "b1"),
        ("pair", "log"), ("pair", "lc"), ("pair", "cnt"),
    ]
    # types are captured per param/pair
    types = [p["type"] for p in cp["params"]]
    assert types == ["(k, v0) fmap", "(k, v1) fmap", "(c, p) fmap",
                     "c list", "int"]


def test_state_field_pool_and_aliases(monkeypatch):
    monkeypatch.setattr(ri, "_session_source_texts", _fake_sources(_SRC))
    pool = ri.state_field_pool(None)
    fields = {f["qualified"]: f["type"] for f in pool["fields"]}
    assert fields["StateM.lenc"] == "n list"
    assert fields["StateM.ndec"] == "int"
    assert fields["Mem.log"] == "(c, p) fmap"
    assert fields["Mem.lc"] == "c list"
    assert pool["aliases"] == {"Rin": "SplitC.I1.RO", "Rout": "SplitC.I2.RO"}


def test_lone_op_with_no_pairs_and_nonrelational_body_excluded(monkeypatch):
    monkeypatch.setattr(ri, "_session_source_texts",
                        _fake_sources("op f (x : int) (y : int) = x + y."))
    assert ri.relational_predicates(None) == []


def test_instantiate_predicate_threads_sides_and_fields(monkeypatch):
    monkeypatch.setattr(ri, "_session_source_texts", _fake_sources(_SRC))
    pred = {p["name"]: p for p in ri.relational_predicates(None)}["coupling"]
    pool = ri.state_field_pool(None)
    cands = ri.instantiate_predicate(pred, pool)
    # singles -> {1}, pairs -> {1} {2}; the two fmap (RO-map) slots vary over the
    # RO aliases; Mem/StateM slots are unique exact-type matches.
    expected = ("call (_: coupling Rin.m{1} Rout.m{1} "
                "Mem.log{1} Mem.log{2} Mem.lc{1} Mem.lc{2} "
                "StateM.ndec{1} StateM.ndec{2}).")
    assert expected in cands
    assert len(cands) == 4          # 2 RO choices x 2 RO choices, rest unique
    assert all(c.startswith("call (_: coupling ") and c.endswith(").") for c in cands)


def test_goal_scope_symbols_reads_module_fields_off_goal_head():
    goal = (
        "SplitC.I1.RO.m <- empty    Mem.log <- empty\n"
        "SplitC.I2.RO.m <- empty    Mem.cnt <- 0\n"
        "Other.x <- 0\n")
    syms = ri.goal_scope_symbols(goal)
    assert "SplitC.I1.RO.m" in syms and "SplitC.I2.RO.m" in syms
    assert "Mem.log" in syms and "Mem.cnt" in syms and "Other.x" in syms
    assert "OutScope.y" not in syms          # not on the goal head -> out of scope


def test_typed_field_resolution_static_type_and_scope(monkeypatch):
    # STATIC resolution — no daemon probing. Types come from the source field
    # pool; scope comes from the goal head EC printed. A slot left with one
    # in-scope type-correct field is filled; several stay a MENU (the RO maps
    # cannot be type-disambiguated statically, so poly_in vs poly_out is the
    # agent's pick); an out-of-scope field (OutScope.y) is dropped without a probe.
    src = """
      op cpl (m1 : (k, va) fmap) (m2 : (k, vb) fmap)
             (log1 log2 : (c, p) fmap) (cnt1 cnt2 : int) =
          log1 = log2 /\\ cnt1 = cnt2.
      module Mem = {
        var log : (c, p) fmap
        var cnt : int
      }
      module Other = {
        var x : int
      }
      module OutScope = {
        var y : int
      }
      local module Rin  = SplitC.I1.RO.
      local module Rout = SplitC.I2.RO.
    """
    monkeypatch.setattr(ri, "_session_source_texts", _fake_sources(src))
    pred = {p["name"]: p for p in ri.relational_predicates(None)}["cpl"]
    pool = ri.state_field_pool(None)

    # goal head lists the live fields; OutScope.y is NOT here -> out of scope.
    goal = (
        "SplitC.I1.RO.m <- empty    Mem.log <- empty\n"
        "SplitC.I2.RO.m <- empty    Mem.cnt <- 0\n"
        "Other.x <- 0\n")

    res = ri.typed_field_resolution(pred, pool, goal)
    assert res is not None and res["name"] == "cpl"
    assert res["probed"] == 0                 # zero daemon probing
    menus = {m["param"]["base"]: (sorted(m["fields"]), m["filled"]) for m in res["menus"]}
    # RO maps: both in scope, both fmap -> a 2-menu (agent picks poly_in/out).
    assert menus["m1"] == (["Rin.m", "Rout.m"], False)
    assert menus["m2"] == (["Rin.m", "Rout.m"], False)
    assert menus["log"] == (["Mem.log"], True)            # source-unique, in scope
    # int menu: OutScope.y dropped by scope; Mem.cnt + Other.x remain.
    assert menus["cnt"] == (["Mem.cnt", "Other.x"], False)
    assert res["fully_determined"] is False
    tmpl = res["template"]
    assert tmpl.startswith("call (_: cpl ‹Rin.m | Rout.m›{1} ‹Rin.m | Rout.m›{1} "
                           "Mem.log{1} Mem.log{2} ")
    assert "OutScope.y" not in tmpl           # out-of-scope field never surfaces
    assert isinstance(res["witness"], str) and res["witness"].startswith("call (_: cpl ")


def test_typed_field_resolution_drops_predicate_when_slot_out_of_scope(monkeypatch):
    # If a required slot has NO in-scope field, the predicate does not apply at
    # this goal -> None (resolved by reading the goal, not by probing).
    src = """
      op cpl (log1 log2 : (c, p) fmap) = log1 = log2.
      module Mem = { var log : (c, p) fmap }
    """
    monkeypatch.setattr(ri, "_session_source_texts", _fake_sources(src))
    pred = {p["name"]: p for p in ri.relational_predicates(None)}["cpl"]
    pool = ri.state_field_pool(None)
    # Mem.log is not on this goal head -> the only candidate is out of scope.
    assert ri.typed_field_resolution(pred, pool, "Foo.bar <- empty\n") is None


def test_render_template_fills_unique_and_inlines_ambiguous_menus():
    menus = [
        {"param": {"kind": "single", "base": "m1", "type": "t"},
         "fields": ["Rin.m"], "filled": True},
        {"param": {"kind": "pair", "base": "log", "type": "t"},
         "fields": ["Mem.log"], "filled": True},
        {"param": {"kind": "pair", "base": "cnt", "type": "int"},
         "fields": ["BNR.ndec", "UFCMA.cbad1"], "filled": False},
    ]
    t = ri.render_template("inv", menus)
    assert t == ("call (_: inv Rin.m{1} Mem.log{1} Mem.log{2} "
                 "‹BNR.ndec | UFCMA.cbad1›{1} ‹BNR.ndec | UFCMA.cbad1›{2}).")
    # all-unique -> a complete, committable carrier (no ‹…› placeholders)
    filled_only = [m for m in menus if m["filled"]]
    assert "‹" not in ri.render_template("inv", filled_only)
