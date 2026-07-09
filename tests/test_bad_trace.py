"""Regression tests for ec_bad_trace: bad-event mutation scanner.

The tool is meant to surface every `<flag> <- true;` in a module's
procedures so the agent designing an up-to-bad invariant knows which
clauses must be tracked. Each test fixture is a synthetic EC
snippet — chosen for shape, not authenticity.

Run: `python3 tests/test_bad_trace.py`
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

from core.easycrypt.ec_bad_trace import trace_module  # noqa: E402


def _check(label: str, ok: bool, detail: str = "") -> None:
    if ok:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}")
        if detail:
            print(f"        {detail}")
        sys.exit(1)


def test_basic_two_flag_proc() -> None:
    """Module with one proc that flips two distinct flags under
    different if-guards — the canonical UFCMA shape."""
    print("[1] basic: two flags in one proc, different if-guards")
    src = """\
module UFCMA = {
  var bad1 : bool
  var bad2 : bool

  proc init() : unit = {
    bad1 <- false;
    bad2 <- false;
  }

  proc enc(n : nonce, p : plain) : cipher = {
    var c : cipher;
    c <- witness;
    if (n \\in lenc) {
      bad1 <- true;
    }
    if ((n,c) \\notin log) {
      bad2 <- true;
    }
    return c;
  }
}.
"""
    out = trace_module(src, "UFCMA")
    _check("report names module", "UFCMA" in out)
    _check("init proc listed", "proc init:" in out)
    _check("enc proc listed", "proc enc:" in out)
    _check("bad1 flip surfaced", "bad1 <- true" in out)
    _check("bad2 flip surfaced", "bad2 <- true" in out)
    _check("bad1 if-guard surfaced",
           "n \\in lenc" in out,
           f"out={out[:300]!r}")
    _check("bad2 if-guard surfaced",
           "(n,c) \\notin log" in out,
           f"out={out[:300]!r}")
    _check("init has 'no flag mutations' line "
           "(init only flips to FALSE, not TRUE)",
           "(no flag mutations)" in out.split("proc enc:")[0])
    print()


def test_counter_mutation_distinguished() -> None:
    """A `cbad <- cbad + 1;` line must be reported but tagged as
    counter, NOT as a bad flip."""
    print("[2] counter mutation tagged separately")
    src = """\
module M = {
  var bad : bool
  var cbad : int

  proc op() : unit = {
    cbad <- cbad + 1;
    bad <- true;
  }
}.
"""
    out = trace_module(src, "M")
    _check("counter line reported",
           "cbad <- cbad + 1" in out)
    _check("counter explicitly tagged as 'counter mutation'",
           "counter mutation" in out,
           f"out={out[:300]!r}")
    _check("flag flip distinct from counter",
           "bad <- true" in out)
    _check("flip count = 1 (counter not double-counted)",
           "1 flag flip(s)" in out,
           f"out={out[-200:]!r}")
    print()


def test_module_type_returns_hint() -> None:
    """`module type` has no procedure bodies — return a hint
    pointing at -members instead of an empty report."""
    print("[3] module type returns redirect hint")
    src = """\
module type ORACLE = {
  proc enc(p : plain) : cipher
}.
"""
    out = trace_module(src, "ORACLE")
    _check("hint mentions module type",
           "module type" in out)
    _check("hint redirects to -members",
           "-members" in out)
    _check("does NOT pretend to have scanned",
           "Bad-event mutations" not in out)
    print()


def test_declare_module_hint() -> None:
    """`declare module M : SIG` is adversary-supplied; its body
    isn't in this file. Return an explanatory hint."""
    print("[4] declare module returns explanatory hint")
    src = """\
declare module A : Adv.

lemma foo &m : Pr[Game(A).main() @ &m : res] = 1%r.
"""
    out = trace_module(src, "A")
    _check("hint mentions declare module",
           "declare module" in out)
    _check("hint explains adversary-supplied",
           "adversary" in out.lower(),
           f"out={out[:200]!r}")
    _check("does NOT pretend to have scanned",
           "Bad-event mutations" not in out)
    print()


def test_unknown_module_redirect() -> None:
    """Module name doesn't exist anywhere — redirect to -where."""
    print("[5] unknown module redirects to -where")
    src = """\
module M = { proc op() : unit = {} }.
"""
    out = trace_module(src, "DoesNotExist")
    _check("'not found' message",
           "not found" in out)
    _check("-where redirect",
           "-where" in out)
    print()


def test_alias_proc_skipped() -> None:
    """`proc enc = OtherMod.enc;` is an alias — has no body to
    scan, must NOT crash and must not falsely report mutations."""
    print("[6] alias proc skipped without crash")
    src = """\
module Wrapper = {
  proc init() : unit = {
    bad <- true;
  }

  proc enc = ChaChaPolyEnc.enc

  proc dec(c : cipher) : plain option = {
    var p : plain option;
    p <- witness;
    return p;
  }
}.
"""
    out = trace_module(src, "Wrapper")
    _check("init's bad flip reported",
           "bad <- true" in out)
    _check("dec listed (no flip)",
           "proc dec:" in out)
    # The alias `enc` should not appear as a proc with body.
    _check("alias enc NOT listed as scanable proc",
           "proc enc:" not in out,
           f"out={out!r}")
    print()


def test_no_flips_summary() -> None:
    """Module with procs but no flag flips — summary line warns
    about indirect flips via called modules."""
    print("[7] no flips: summary mentions indirect flips")
    src = """\
module Pure = {
  proc init() : unit = {
    x <- 0;
  }
  proc op(y : int) : int = {
    var r : int;
    r <- y + 1;
    return r;
  }
}.
"""
    out = trace_module(src, "Pure")
    _check("no-flip summary present",
           "No `<x> <- true` flips" in out)
    _check("hints at indirect flips",
           "called modules" in out)
    print()


def test_functor_module() -> None:
    """`module BNR(O : OBO_OR) = { ... }` (functor with parameter)
    must still parse and scan the body."""
    print("[8] functor-form module body scanned")
    src = """\
module BNR(O : OBO_OR) = {
  proc enc(p : plain) : cipher = {
    var c : cipher;
    c <- witness;
    if (size c > max_cipher_size) {
      bad <- true;
    }
    return c;
  }
}.
"""
    out = trace_module(src, "BNR")
    _check("functor body parsed",
           "proc enc:" in out)
    _check("bad flip in functor body found",
           "bad <- true" in out)
    _check("functor param's if-guard surfaced",
           "size c > max_cipher_size" in out)
    print()


def test_disjunctive_accumulation() -> None:
    """Real EC code (chacha_poly UFCMA) uses `bad <- bad || cond;`
    instead of `if (cond) { bad <- true; }`. Both must be caught.
    Audit 2026-04-30: original regex missed this form on the actual
    chacha_poly file, reporting 'no flag mutations' when bad1/bad2
    were clearly being set."""
    print("[10] disjunctive accumulation form (bad <- bad || cond)")
    src = """\
module UFCMA = {
  var bad1 : bool
  var bad2 : bool
  var cbad1 : int

  proc set_bad1(lt : tag list) : poly_out = {
    var t;
    t <$ dpoly_out;
    if (cbad1 < qenc /\\ size lt <= qdec) {
      bad1 <- bad1 || t \\in lt;
      cbad1 <- cbad1 + 1;
    }
    return t;
  }

  proc set_bad2(lt : tag list) : poly_out = {
    var t;
    t <$ dpoly_out;
    bad2 <- bad2 || t \\in lt;
    return t;
  }
}.
"""
    out = trace_module(src, "UFCMA")
    _check("bad1 disjunctive flip surfaced",
           "bad1 <- bad1 ||" in out,
           f"out={out[:500]!r}")
    _check("bad2 disjunctive flip surfaced",
           "bad2 <- bad2 ||" in out,
           f"out={out[:500]!r}")
    _check("counter mutation cbad1 still distinguished",
           "cbad1 <- cbad1 + 1" in out and "counter mutation" in out)
    _check("flip count = 2 (bad1, bad2 — counter not over-counted)",
           "2 flag flip(s)" in out,
           f"out={out[-300:]!r}")
    print()


def test_disjunctive_backslash_or() -> None:
    """EC also accepts `\\/` (Coq-style logical OR) in statements,
    not just `||`. cramer-shoup proofs use this form. Audit
    2026-04-30 caught it on eval/examples/cramer-shoup/cramer_shoup.ec
    where `bad <- bad \\/ (...)` reported as 'no flag mutations'."""
    print("[11] disjunctive form with `\\/` (cramer-shoup style)")
    src = """\
module G1 = {
  var bad : bool

  proc dec(c : ciphertext) : message option = {
    var p : message option;
    p <- witness;
    bad <- bad \\/ (cond1 /\\ cond2);
    return p;
  }
}.
"""
    out = trace_module(src, "G1")
    _check("backslash-or flip surfaced",
           "bad <- bad" in out and "\\/" in out,
           f"out={out[:400]!r}")
    _check("flip count = 1",
           "1 flag flip(s)" in out)
    print()


def test_local_module() -> None:
    """`local module M = { ... }` should be scanned identically."""
    print("[9] local module recognized")
    src = """\
local module L = {
  proc op() : unit = {
    bad <- true;
  }
}.
"""
    out = trace_module(src, "L")
    _check("local module body parsed",
           "proc op:" in out)
    _check("bad flip found",
           "bad <- true" in out)
    print()


if __name__ == "__main__":
    print("=== ec_bad_trace tests ===\n")
    test_basic_two_flag_proc()
    test_counter_mutation_distinguished()
    test_module_type_returns_hint()
    test_declare_module_hint()
    test_unknown_module_redirect()
    test_alias_proc_skipped()
    test_no_flips_summary()
    test_functor_module()
    test_disjunctive_accumulation()
    test_disjunctive_backslash_or()
    test_local_module()
    print("All tests passed.")
