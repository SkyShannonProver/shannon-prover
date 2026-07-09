#!/usr/bin/env python3
"""Unit tests for the mechanical call-glob invariant skeleton.

Pure parsing/rendering — no EasyCrypt needed. Family-general: uses synthetic,
arbitrary module names (no ChaChaPoly/MEE-specific tokens) so the pass stays a
mechanical structure synthesizer, not a per-family hardcode.

Run: python3 -m pytest tests/test_ec_call_glob_invariant.py -q
"""
from __future__ import annotations

import sys
from pathlib import Path

import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from core.easycrypt.analysis import ec_call_glob_invariant as cg  # type: ignore  # noqa: E402


def _fake_sources(*texts):
    return lambda _sd: [(t, Path("x.ec"), "source") for t in texts]


def test_declared_abstract_modules_basic(monkeypatch):
    src = """
      section S.
        declare module Sch <: Enc_Scheme.
        declare module Tag <: MAC_Scheme { -Wrap, -Sch }.
        declare module Adv <: Adversary { -Wrap, -Sch, -Tag }.
        lemma foo &m : Pr[X.main() @ &m : res] = Pr[Y.main() @ &m : res].
      end section S.
    """
    monkeypatch.setattr(cg, "_session_source_texts", _fake_sources(src))
    mods = cg.declared_abstract_modules(None)
    names = [m["name"] for m in mods]
    assert names == ["Sch", "Tag", "Adv"]  # textual order preserved
    assert mods[0]["bound"] == "Enc_Scheme"
    assert mods[1]["bound"] == "MAC_Scheme"


def test_declared_abstract_modules_dedup(monkeypatch):
    # nested re-declaration (tighter restriction) keeps one entry, order stable
    src = """
      declare module Sch <: T.
      section Inner.
        declare module Sch <: T { -W }.
        declare module Adv <: A.
      end section Inner.
    """
    monkeypatch.setattr(cg, "_session_source_texts", _fake_sources(src))
    names = [m["name"] for m in cg.declared_abstract_modules(None)]
    assert names == ["Sch", "Adv"]


def test_render_glob_invariant():
    assert cg.render_glob_invariant(["Sch", "Tag"]) == "={glob Sch, glob Tag}"
    assert cg.render_glob_invariant(["Sch"]) == "={glob Sch}"
    assert cg.render_glob_invariant([]) == ""
    # dedup preserves first-seen order
    assert cg.render_glob_invariant(["A", "B", "A"]) == "={glob A, glob B}"


def test_render_call_glob_tactic():
    assert cg.render_call_glob_tactic(["Sch", "Tag"]) == "call (_: ={glob Sch, glob Tag})."
    assert cg.render_call_glob_tactic([]) == ""


def test_maximal_accepted_glob_drops_adversary_at_singleton():
    # adversary singleton rejected (call rule "module Adv can write Adv");
    # oracle singletons accepted; union of oracles accepted.
    mods = [{"name": "Sch"}, {"name": "Tag"}, {"name": "Adv"}]

    def probe(tactic):
        if "glob Adv" in tactic:
            return {"accepted": False, "error": "module Adv can write Adv"}
        return {"accepted": True, "error": None}

    assert cg.maximal_accepted_glob(mods, probe) == ["Sch", "Tag"]


def test_maximal_accepted_glob_drops_adversary_at_union():
    # adversary singleton ACCEPTED but the union with it is rejected by name
    mods = [{"name": "Sch"}, {"name": "Tag"}, {"name": "Adv"}]

    def probe(tactic):
        # Adv alone is fine, but any union containing Adv is rejected by name.
        if "glob Adv" in tactic and tactic.count("glob ") > 1:
            return {"accepted": False, "error": "module Adv can write Adv"}
        return {"accepted": True, "error": None}

    assert cg.maximal_accepted_glob(mods, probe) == ["Sch", "Tag"]


def test_maximal_accepted_glob_all_rejected():
    mods = [{"name": "Adv"}]
    assert cg.maximal_accepted_glob(
        mods, lambda t: {"accepted": False, "error": "nope"}) == []


def test_no_modules_is_empty(monkeypatch):
    monkeypatch.setattr(cg, "_session_source_texts", _fake_sources("lemma g : true."))
    assert cg.declared_abstract_modules(None) == []
    assert cg.render_call_glob_tactic([]) == ""


# --- goal-derived glob candidates (panel audit: call_invariant_skeleton NO_GLOB) ---
# The shared oracle/state modules at a `call (_: ={glob ...})` frontier are the CONCRETE
# functor arguments threaded through the goal's module expressions (Log/LRO in Log(LRO)),
# never `declare module` abstracts — so declared_abstract_modules misses them and the
# producer emitted NO_GLOB. glob_modules_from_goal flattens them (daemon-filtered later).


def test_glob_modules_from_goal_flattens_functor_modules():
    names = [m["name"] for m in cg.glob_modules_from_goal(
        "Wrap(Mid(Leaf.Sub(P, Q), R)).run(a) ~ Other.run(a) : pre ==> post")]
    assert {"Wrap", "Mid", "Leaf.Sub", "P", "Q", "R"} <= set(names)


def test_glob_modules_from_goal_excludes_called_adversary():
    # the call rule forbids ={glob A}: the adversary root is excluded, its concrete
    # oracle arguments (Orc, St) are kept.
    names = [m["name"] for m in cg.glob_modules_from_goal(
        "r <@ A(Orc(St)).guess(); s <@ Orc(St).o(x); (glob A){1} = (glob A){2}",
        exclude={"A"})]
    assert "Orc" in names and "St" in names
    assert "A" not in names


def test_glob_modules_from_goal_empty_without_module_application():
    assert cg.glob_modules_from_goal("x + y = y + x") == []
