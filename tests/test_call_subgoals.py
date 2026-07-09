"""Regression tests for ec_call_subgoals: speculative call subgoal preview.

Tests the formatter (`preview_subgoals`) against synthetic pre/post
goal text. The daemon-roundtrip path (`preview_from_session`) is
not unit-tested here — it requires a live EC session. Manual smoke
test that route by running:

    python3 core/easycrypt/session_cli.py -d <sess> \\
        -call-subgoals -c '<inv>'

against an actual session paused at a `call`-eligible state.

Run: `python3 tests/test_call_subgoals.py`
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

from core.easycrypt.analysis.ec_call_subgoals import (  # noqa: E402
    preview_subgoals,
    _find_module_type_procs,
    _extract_active_proc_calls,
    _identify_adv_type_in_call,
    _parse_remaining_count,
)


def _check(label: str, ok: bool, detail: str = "") -> None:
    if ok:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}")
        if detail:
            print(f"        {detail}")
        sys.exit(1)


def test_module_type_proc_extraction() -> None:
    """Given source with `module type ADV = { proc enc; proc dec; }`,
    extract the proc names."""
    print("[1] _find_module_type_procs: signature parsing")
    src = """\
module type CCA_CPA_Adv = {
  proc init() : unit
  proc distinguish() : bool
}.

module type OBO_OR = {
  proc enc(p : plain) : cipher
  proc dec(c : cipher) : plain option
  proc init() : unit
}.
"""
    procs = _find_module_type_procs(src, "CCA_CPA_Adv")
    _check("CCA_CPA_Adv has 2 procs", len(procs) == 2,
           f"got {procs}")
    _check("CCA_CPA_Adv procs: init, distinguish",
           set(procs) == {"init", "distinguish"},
           f"got {procs}")

    procs2 = _find_module_type_procs(src, "OBO_OR")
    _check("OBO_OR has 3 procs", len(procs2) == 3,
           f"got {procs2}")
    _check("OBO_OR procs include enc/dec/init",
           set(procs2) == {"enc", "dec", "init"},
           f"got {procs2}")

    procs3 = _find_module_type_procs(src, "DoesNotExist")
    _check("missing type returns empty list", procs3 == [])
    print()


def test_extract_proc_calls() -> None:
    """From a pRHL goal display, identify the trailing `<@` call on
    each side."""
    print("[2] _extract_active_proc_calls: pRHL trailing call extraction")
    pre = """\
Current goal (remaining: 1)

pre = ={glob A}
post = ={res}

  r0 <@ A(O).distinguish()              (1)  r1 <@ A(O').distinguish()
"""
    lhs, rhs = _extract_active_proc_calls(pre)
    _check("LHS: A(O).distinguish",
           "A(O).distinguish" in lhs,
           f"got lhs={lhs!r}")
    _check("RHS: A(O').distinguish",
           "A(O" in rhs and ".distinguish" in rhs,
           f"got rhs={rhs!r}")

    pre2 = "no calls here just program text"
    lhs2, rhs2 = _extract_active_proc_calls(pre2)
    _check("no calls: empty strings", lhs2 == "" and rhs2 == "")

    # Real-world test against eval/examples/elgamal.ec at lemma
    # cpa_ddh0 found that when MULTIPLE `<@` calls appear in the
    # visible program, EC's `call` consumes the TRAILING one (the
    # last in source order), not the first. The extractor must
    # return the LAST `<@` per side, not the first. br93 / PRG had
    # only one visible call per side, so first == last masked this.
    pre_multi_call = """\
Current goal (remaining: 1)

  (m0,m1) <@ A.choose(g^x)              (1)  (m0,m1) <@ A.choose(g^x)
  z <$ dt                                ( )  z <$ dt
  b' <@ A.guess(g^y, g^z)               (3)  b' <@ A.guess(g^y, g^z)

post = ...
"""
    lhs3, rhs3 = _extract_active_proc_calls(pre_multi_call)
    _check("multi-call display: LHS = TRAILING (A.guess), not first",
           "guess" in lhs3,
           f"got lhs={lhs3!r}; should be A.guess (trailing call)")
    _check("multi-call display: RHS = TRAILING (A.guess)",
           "guess" in rhs3,
           f"got rhs={rhs3!r}")

    # Audit 2026-04-30 (chacha_poly step1 step 8 via replay harness):
    # When LHS `<@` is followed only by whitespace, then a column
    # marker `(N)`, then the RHS column's `<@`, the v1 split regex
    # required `\s+` before `(`. After the leading-whitespace skip
    # by the calling parser, the chunk STARTS with `(`, so split
    # didn't fire. Result: LHS got `(2)  b0 <@ A(D(A, IndBlock).O).main`
    # (column marker + RHS leak). Fix uses `(?:^|\s+)` to match
    # markers at chunk start too.
    pre_chacha_wrap = """\
b <@                                (2)  b0 <@ A(D(A, IndBlock).O).main()
  A(                                ( )
    RealOrcls(                      ( )
      GenChaChaPoly(OpCCinit.       ( )
        OCC(I_stateless)))).main()  ( )
"""
    lhs4, rhs4 = _extract_active_proc_calls(pre_chacha_wrap)
    _check("chacha_poly column-marker leak: no '(2)' in extracted call",
           "(2)" not in lhs4 and "(2)" not in rhs4,
           f"got lhs={lhs4!r} rhs={rhs4!r}; column marker leaked")
    _check("chacha_poly column-marker leak: no double-`<@` in either",
           "<@" not in lhs4 and "<@" not in rhs4,
           f"got lhs={lhs4!r} rhs={rhs4!r}; '<@' should already be stripped")
    print()

    # Documented limit: when EC wraps a long call across multiple
    # display lines (e.g., `b' <@\n  A.guess(gy,\n    gz * if ...)`),
    # this extractor gets the same-line empty chunk and gives up
    # on that side. Two-column positional reasoning makes
    # disambiguation hard. The "Active subgoal verifies" line in
    # the formatter (extracted from post_raw, not pre_raw) is the
    # authoritative source for which proc the call consumed. We
    # accept this limit rather than ship a column-position parser
    # that could mis-attribute wrapped lines.
    print()


def test_identify_adv_type() -> None:
    """Given a call expression and source declaring the module's
    adversary type, identify it."""
    print("[3] _identify_adv_type_in_call: type resolution")
    src = """\
module type CCA_CPA_Adv = { proc distinguish() : bool }.

module BNR(A : CCA_CPA_Adv) = {
  proc main() = {
    var b;
    b <@ A.distinguish();
    return b;
  }
}.

declare module Adv : CCA_CPA_Adv.
"""
    t = _identify_adv_type_in_call(src, "BNR(A).main")
    _check("functor module BNR's adv type = CCA_CPA_Adv",
           t == "CCA_CPA_Adv",
           f"got {t!r}")

    t2 = _identify_adv_type_in_call(src, "Adv.distinguish")
    _check("declare-module Adv's type = CCA_CPA_Adv",
           t2 == "CCA_CPA_Adv",
           f"got {t2!r}")

    t3 = _identify_adv_type_in_call(src, "Unknown.proc")
    _check("missing module returns None", t3 is None)

    # Real EC syntax for declare-module restrictions uses `<:`
    # (subtype) not `:` (ascription). step4_1 audit 2026-04-30 found
    # the v1 regex missed this on a live test fixture.
    src_subtype = """\
section S.

declare module I <: Init { -OCC }.
declare module B <: Adv { -OCC, -I }.

end section S.
"""
    _check("declare module B <: Adv (with restrictions)",
           _identify_adv_type_in_call(src_subtype, "B.distinguish") == "Adv",
           f"got {_identify_adv_type_in_call(src_subtype, 'B.distinguish')!r}")
    _check("declare module I <: Init",
           _identify_adv_type_in_call(src_subtype, "I.init") == "Init")

    src_functor_subtype = """\
module BNR(A <: Adv) = {
  proc main() = {}
}.
"""
    _check("functor with `<:` parameter binding",
           _identify_adv_type_in_call(src_functor_subtype, "BNR(X).main") == "Adv",
           f"got {_identify_adv_type_in_call(src_functor_subtype, 'BNR(X).main')!r}")
    print()


def test_parse_remaining_count() -> None:
    """Parse the (remaining: N) marker from EC goal text."""
    print("[4] _parse_remaining_count: subgoal counter")
    _check("(remaining: 5) → 5",
           _parse_remaining_count("Current goal (remaining: 5)\n...") == 5)
    _check("(remaining: 0) → 0",
           _parse_remaining_count("Current goal (remaining: 0)\n...") == 0)
    _check("Current goal without remaining → 1",
           _parse_remaining_count("Current goal\n...") == 1)
    _check("no goal → 0",
           _parse_remaining_count("just text") == 0)
    print()


def test_preview_full_path_with_source() -> None:
    """Happy path: speculative call accepted, source resolves the
    adversary type. Output should surface the count, active call,
    active subgoal's proc pair, and outermost module type — but
    NOT predict per-proc subgoals (EC's `call` produces one subgoal
    per oracle the adversary INVOKES, not one per proc of the
    adversary's type — predicting that requires reasoning about
    functor parameter types we don't fully resolve)."""
    print("[5] preview happy path: count + active proc pair, no over-claim")
    pre = """\
Current goal (remaining: 1)

pre = ={glob A}
post = ={res}

  b <@ BNR(A_inst).main()              (1)  b1 <@ BNR(A_inst).main()
"""
    post = """\
Current goal (remaining: 5)

pre = arg{1} = arg{2} /\\ ={glob A}

    Log(LRO).o ~ Log(LRO).o

post = res{1} = res{2}
"""
    src = """\
module type CCA_CPA_Adv = {
  proc init() : unit
  proc distinguish() : bool
}.

module BNR(A : CCA_CPA_Adv) = {
  proc main() = {
    var b;
    b <@ A.distinguish();
    return b;
  }
}.

declare module A_inst : CCA_CPA_Adv.
"""
    out = preview_subgoals(
        pre_raw=pre, post_raw=post, accepted=True, error_msg="",
        invariant="={glob A}", source_text=src,
    )
    _check("preview header present",
           "Call subgoal preview" in out)
    _check("subgoal count surfaced",
           "5 subgoal(s)" in out,
           f"out={out[:300]!r}")
    _check("active call (from pre) shown",
           "BNR(A_inst).main" in out)
    _check("active subgoal's proc pair extracted",
           "Log(LRO).o ~ Log(LRO).o" in out,
           f"out={out!r}")
    _check("outermost module type identified",
           "CCA_CPA_Adv" in out)
    _check("does NOT over-claim per-proc subgoal mapping",
           "Predicted subgoals" not in out and "predicted subgoal" not in out.lower(),
           f"out leaked optimistic prediction: {out[:400]!r}")
    _check("explicitly notes subgoals != adversary procs",
           "INVOKES" in out or "invokes" in out,
           f"out={out!r}")
    _check("recommended next step section present",
           "Recommended next step" in out)
    print()


def test_preview_rejection() -> None:
    """When daemon rejects the speculative call, surface the error
    and common-cause hints, no fake preview."""
    print("[6] preview rejection: error path")
    out = preview_subgoals(
        pre_raw="", post_raw="", accepted=False,
        error_msg="parse error: cannot infer all placeholders",
        invariant="(_: malformed_inv)", source_text="",
    )
    _check("rejection message verbatim",
           "cannot infer all placeholders" in out)
    _check("common causes hint present",
           "Common causes" in out)
    _check("does NOT pretend to have preview",
           "subgoal(s)" not in out and "Predicted subgoals" not in out,
           f"out leaked preview: {out!r}")
    print()


def test_preview_unresolved_type() -> None:
    """Call accepted but adversary type can't be resolved from
    source — output should still show count + active subgoal preview
    + recommended next step, just without the type-info section."""
    print("[7] preview without source: count + active preview")
    pre = """\
Current goal (remaining: 1)

  r <@ AbstractStuff.proc()              (1)  r1 <@ OtherStuff.proc()
"""
    post = """\
Current goal (remaining: 4)

(active subgoal body)
"""
    out = preview_subgoals(
        pre_raw=pre, post_raw=post, accepted=True, error_msg="",
        invariant="some_inv", source_text="",  # no source
    )
    _check("subgoal count still shown",
           "subgoal" in out)
    _check("falls back to active preview",
           "Active subgoal preview" in out)
    _check("does NOT over-claim a per-proc subgoal mapping",
           "Predicted subgoals" not in out,
           f"out leaked predict: {out[:400]!r}")
    _check("recommended next step still present",
           "Recommended next step" in out)
    print()


if __name__ == "__main__":
    print("=== ec_call_subgoals tests ===\n")
    test_module_type_proc_extraction()
    test_extract_proc_calls()
    test_identify_adv_type()
    test_parse_remaining_count()
    test_preview_full_path_with_source()
    test_preview_rejection()
    test_preview_unresolved_type()
    print("All tests passed.")
