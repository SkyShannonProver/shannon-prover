"""Structural diff of the two oracle modules at a relational call frontier.

step4_badi: `UFCMA_l` vs `UFCMA_li` — `set_bad1` differs (right resamples via
`set_bad1i`), `set_bad1i` is right-only. The agent rebuilt this by hand (~3 min).
"""
from __future__ import annotations

import sys
from pathlib import Path

import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from core.easycrypt.analysis.ec_oracle_diff import (  # noqa: E402
    differing_call_modules, oracle_module_diff, _module_procs,
)


_SRC = """
  local module UFCMA_l = {
    proc set_bad1 (lt) = { var t; t <$ d; if (g) { lbad1 <- lbad1 ++ m; } return t; }
    proc enc (p) = { var c; c <@ set_bad1(x); return c; }
  }.

  local module UFCMA_li = {
    proc set_bad1i (ti) = { var t; t <$ d; badi <- badi || t = ti; return t; }
    proc set_bad1 (lt) = { var t; t <$ d; if (g) { if (h) { t <@ set_bad1i(y); } lbad1 <- lbad1 ++ m; } return t; }
    proc enc (p) = { var c; c <@ set_bad1(x); return c; }
  }.
"""


def test_differing_call_modules() -> None:
    lm, rm = differing_call_modules(
        "b <@ CPA_game(CCA_CPA_Adv(BNR_Adv(A)), UFCMA_l.O).main()",
        "b <@ CPA_game(CCA_CPA_Adv(BNR_Adv(A)), UFCMA_li.O).main()")
    assert (lm, rm) == ("UFCMA_l", "UFCMA_li")


def test_oracle_diff_surfaces_only_the_divergence() -> None:
    diff = oracle_module_diff([(_SRC, "s")], "UFCMA_l", "UFCMA_li")
    differing = {d["proc"] for d in diff["differing_procs"]}
    assert "set_bad1" in differing        # differs (right resamples)
    assert "enc" not in differing         # identical -> suppressed
    assert diff["right_only_procs"] == ["set_bad1i"]   # the resample helper
    assert diff["left_only_procs"] == []
    # the surfaced set_bad1 right body shows the resample call
    sb = next(d for d in diff["differing_procs"] if d["proc"] == "set_bad1")
    assert "set_bad1i" in sb["right"] and "set_bad1i" not in sb["left"]


def test_module_procs_parses_each_proc() -> None:
    procs = _module_procs([(_SRC, "s")], "UFCMA_li")
    assert set(procs) == {"set_bad1i", "set_bad1", "enc"}


def test_empty_when_modules_absent_or_equal() -> None:
    assert oracle_module_diff([(_SRC, "s")], "UFCMA_l", "UFCMA_l") == {}
    assert oracle_module_diff([(_SRC, "s")], "Nope", "AlsoNope") == {}


if __name__ == "__main__":
    test_differing_call_modules()
    test_oracle_diff_surfaces_only_the_divergence()
    test_module_procs_parses_each_proc()
    test_empty_when_modules_absent_or_equal()
    print("PASS test_oracle_diff")
