"""Call-frontier structure: module aliases + abstract-adversary glob boundary.

The mechanical name-resolution facts the agent rebuilt by hand in step4_badi
turn 3 (~70s): `ROout -> SplitC2.I2.RO`, and `A`'s glob being separate from the
concrete state modules.
"""
from __future__ import annotations

import sys
from pathlib import Path

import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from core.easycrypt.analysis.ec_call_frontier_structure import (  # noqa: E402
    call_frontier_structure, abstract_adversaries, inline_preview,
)


_SRC = """
abstract theory OpCC.
  declare module I <: Init { -OCC }.
  declare module A <: Adv { -OCC, -I }.
end OpCC.

declare module A <: CCA_Adv { -RO, -FRO, -IndBlock, -Mem, -StLSke }.
"""
_ALIASES = {"ROin": "SplitC2.I1.RO", "ROout": "SplitC2.I2.RO", "ROF": "SplitD.ROF.RO"}


def test_picks_richest_adversary_declaration() -> None:
    # two `declare module A` — keep the one with the larger glob-separation set
    advs = {a["name"]: a for a in abstract_adversaries([(_SRC, "src")])}
    a = advs["A"]
    assert a["type"] == "CCA_Adv"
    assert {"RO", "FRO", "IndBlock", "Mem", "StLSke"} <= set(a["glob_separate_from"])
    assert "OCC" not in a["glob_separate_from"]  # not the inner Adv declaration


def test_surfaces_aliases_and_glob_boundary() -> None:
    out = call_frontier_structure(
        [(_SRC, "src")], aliases=_ALIASES,
        goal_text="b <@ CPA_game(CCA_CPA_Adv(BNR_Adv(A)), UFCMA_l.O).main()")
    amap = {r["alias"]: r["resolves_to"] for r in out["module_aliases"]}
    assert amap["ROout"] == "SplitC2.I2.RO"
    assert amap["ROF"] == "SplitD.ROF.RO"
    advs = [a["name"] for a in out["abstract_adversaries"]]
    assert "A" in advs
    # the note tells the agent to keep glob A OUT of the concrete frame
    assert "OUT of the" in out["note"] and "glob A" in out["note"]


def test_goal_relevance_filters_adversaries() -> None:
    # only A is named in the goal -> I is filtered out
    out = call_frontier_structure([(_SRC, "src")], aliases={}, goal_text="... A(O).main() ...")
    names = {a["name"] for a in out["abstract_adversaries"]}
    assert "A" in names and "I" not in names


def test_inline_preview_marks_concrete_vs_abstract() -> None:
    src = "module CPA_game = {}. module BNR_Adv = {}. declare module A <: Adv."
    out = inline_preview(
        [(src, "s")], "b <@ CPA_game(BNR_Adv(A), O).main()", abstract_names=["A"])
    by = {r["module"]: r["kind"] for r in out["modules"]}
    assert by["CPA_game"] == "concrete" and by["BNR_Adv"] == "concrete"
    assert by["A"] == "abstract"
    assert out["inline_stops_at"] == ["A"]


def test_empty_when_nothing() -> None:
    assert call_frontier_structure([("no declares here", "src")], aliases={}) == {}
    assert inline_preview([("x", "s")], "b <@ x", abstract_names=[]) == {}


if __name__ == "__main__":
    test_picks_richest_adversary_declaration()
    test_surfaces_aliases_and_glob_boundary()
    test_goal_relevance_filters_adversaries()
    test_empty_when_nothing()
    print("PASS test_call_frontier_structure")
