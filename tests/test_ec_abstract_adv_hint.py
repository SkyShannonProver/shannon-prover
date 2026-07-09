"""Tests for abstract-adversary call-site hint generator."""
from __future__ import annotations

from pathlib import Path
import sys

import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from core.easycrypt.analysis.ec_abstract_adv_hint import (  # type: ignore  # noqa: E402
    AbstractAdvCall,
    candidate_call_tactics,
    canonical_inv_shapes,
    detect_and_propose,
    extract_call_sites,
    filter_abstract,
    is_declared_abstract,
)


_CPA_DDH0_POST_INLINE_GOAL = """\
&m: {}
------------------------------------------------------------------------
&1 (left ) : {b, b' : bool, sk0, y : ZModE.exp, pk, pk0 : pkey, sk : skey,
             m0, m1, m : ptxt, c : ctxt}
&2 (right) : {b, b0, b' : bool, gy, gz : group, x, y : ZModE.exp, gx : pkey,
             m0, m1 : ptxt}

pre = (glob A){2} = (glob A){m} /\\ (glob A){1} = (glob A){m}

sk0 <$ dt                   (1)  x <$ dt
(pk, sk) <- (g ^ sk0, sk0)  (2)  y <$ dt
(m0, m1) <@ A.choose(pk)    (3)  gx <- g ^ x
b <$ {0,1}                  (4)  gy <- g ^ y
pk0 <- pk                   (5)  gz <- g ^ (x * y)
m <- if b then m1 else m0   (6)  (m0, m1) <@ A.choose(gx)
y <$ dt                     (7)  b0 <$ {0,1}
c <- (g ^ y, pk0 ^ y * m)   (8)  b' <@
                            ( )    A.guess(gy,
                            ( )      gz * if b0 then m1 else m0)
b' <@ A.guess(c)            (9)  b <- b' = b0

post = (b'{1} = b{1}) = b{2}
"""


_ELGAMAL_SECTION = """\
section.
  declare module A <: Adversary.
  declare axiom Ac_ll: islossless A.choose.
"""


def test_extract_call_sites_finds_both_adversary_calls() -> None:
    calls = extract_call_sites(_CPA_DDH0_POST_INLINE_GOAL)
    keys = sorted({(c.module, c.proc) for c in calls})
    assert keys == [("A", "choose"), ("A", "guess")]


def test_extract_call_sites_handles_functored_module() -> None:
    goal = "x <@ DDHAdv(A).guess(y);\nz <@ B.choose();"
    calls = extract_call_sites(goal)
    keys = {(c.module, c.proc) for c in calls}
    assert ("DDHAdv", "guess") in keys
    assert ("B", "choose") in keys


def test_is_declared_abstract_detects_section_declare() -> None:
    assert is_declared_abstract(_ELGAMAL_SECTION, "A") is True
    assert is_declared_abstract(_ELGAMAL_SECTION, "Ac_ll") is False
    assert is_declared_abstract(_ELGAMAL_SECTION, "A2") is False


def test_filter_abstract_drops_concrete_modules() -> None:
    source = "declare module A <: Adversary.\nmodule ElGamal = {}.\n"
    calls = [
        AbstractAdvCall("A", "choose"),
        AbstractAdvCall("ElGamal", "kg"),
    ]
    filtered = filter_abstract(calls, source)
    assert filtered == [AbstractAdvCall("A", "choose")]


def test_canonical_inv_shapes_single_module() -> None:
    shapes = canonical_inv_shapes(["A"])
    assert shapes == [
        "={glob A} ==> ={res, glob A}",
        "={glob A}",
        "true",
    ]


def test_canonical_inv_shapes_multi_module_dedup() -> None:
    shapes = canonical_inv_shapes(["A", "B", "A"])
    assert shapes[0] == "={glob A, glob B} ==> ={res, glob A, glob B}"
    assert shapes[1] == "={glob A, glob B}"
    assert shapes[2] == "true"


def test_canonical_inv_shapes_empty() -> None:
    assert canonical_inv_shapes([]) == []


def test_candidate_call_tactics_format() -> None:
    tactics = candidate_call_tactics(["A"])
    assert tactics == [
        "call (_: ={glob A} ==> ={res, glob A}).",
        "call (_: ={glob A}).",
        "call (_: true).",
    ]


def test_detect_and_propose_cpa_ddh0_shape() -> None:
    calls, tactics = detect_and_propose(
        _CPA_DDH0_POST_INLINE_GOAL, _ELGAMAL_SECTION,
    )
    assert {(c.module, c.proc) for c in calls} == {
        ("A", "choose"), ("A", "guess"),
    }
    assert tactics == [
        "call (_: ={glob A} ==> ={res, glob A}).",
        "call (_: ={glob A}).",
        "call (_: true).",
    ]


def test_detect_and_propose_no_abstract_adv_returns_empty() -> None:
    goal = "x <@ Concrete.foo(y);"
    source = "module Concrete = {}.\n"
    calls, tactics = detect_and_propose(goal, source)
    assert calls == []
    assert tactics == []


def main() -> int:
    tests = [
        test_extract_call_sites_finds_both_adversary_calls,
        test_extract_call_sites_handles_functored_module,
        test_is_declared_abstract_detects_section_declare,
        test_filter_abstract_drops_concrete_modules,
        test_canonical_inv_shapes_single_module,
        test_canonical_inv_shapes_multi_module_dedup,
        test_canonical_inv_shapes_empty,
        test_candidate_call_tactics_format,
        test_detect_and_propose_cpa_ddh0_shape,
        test_detect_and_propose_no_abstract_adv_returns_empty,
    ]
    for t in tests:
        t()
    print("PASS test_ec_abstract_adv_hint")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
