"""Tests for the proactive obligation-gap signal (lamp a).

Surface WHERE a stronger invariant is likely needed (module program state the
conclusion depends on that nothing constrains) without saying WHAT to add. Must
stay silent on healthy goals and on library constants.
"""
from __future__ import annotations

import sys
from pathlib import Path

import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from core.easycrypt.analysis.ec_obligation_gap import unconstrained_post_fields  # noqa: E402


def test_flags_state_the_invariant_does_not_constrain() -> None:
    res = unconstrained_post_fields(
        "pre = ={glob A} ==> "
        "(let tt = nth (w1,w2) UFCMA_l.lbad1{1} nth0 in tt.`1 = tt.`2) "
        "=> UFCMA_li.badi{2}"
    )
    assert res["available"] is True
    assert "UFCMA_l.lbad1" in res["fields"]
    assert "UFCMA_li.badi" in res["fields"]
    # WHERE, not WHAT: the note names fields, never a concrete conjunct
    assert "badi" not in res["note"].split("depends on")[0]
    assert "=>" not in res["note"]


def test_silent_when_post_state_is_constrained_by_pre() -> None:
    res = unconstrained_post_fields(
        "pre = ={Mem.log, RO.m} ==> ={Mem.log} /\\ RO.m{1} = RO.m{2}"
    )
    assert res["available"] is False


def test_library_constants_in_post_do_not_flag() -> None:
    # SmtMap.empty is not side-tagged program state; must not be flagged
    res = unconstrained_post_fields(
        "pre = ={RO.m} ==> RO.m{1} = SmtMap.empty /\\ RO.m{2} = SmtMap.empty"
    )
    assert res["available"] is False


def test_dims_field_by_field_as_invariant_strengthens() -> None:
    # lbad1 now coupled; only the still-unconstrained counter remains flagged
    res = unconstrained_post_fields(
        "pre = ={UFCMA_l.lbad1} ==> "
        "UFCMA_l.lbad1{1} = UFCMA_l.lbad1{2} /\\ UFCMA_li.cbadi{2} = 0"
    )
    assert res["available"] is True
    assert res["fields"] == ["UFCMA_li.cbadi"]


def test_no_post_no_signal() -> None:
    assert unconstrained_post_fields("")["available"] is False
    assert unconstrained_post_fields("just some text")["available"] is False


def main() -> int:
    test_flags_state_the_invariant_does_not_constrain()
    test_silent_when_post_state_is_constrained_by_pre()
    test_library_constants_in_post_do_not_flag()
    test_dims_field_by_field_as_invariant_strengthens()
    test_no_post_no_signal()
    print("PASS test_obligation_gap")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
