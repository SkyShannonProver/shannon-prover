"""Tests for the EasyCrypt static scope-context pass."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from core.easycrypt.ec_static_context import (  # noqa: E402
    analyze_ec_scope_context,
    is_cloned_theory_lemma,
)


_SOURCE = """\
abstract theory OpCCRO.
end OpCCRO.

clone import OpCC as OpCCinit with type globS <- unit.
clone import Ske.SKE_RND with type key <- key.
clone include MFinite with type t <- block.

section.
  declare module A <: CCA_Adv.

  local module G2(RO:RO) = {
    proc distinguish() = { return witness; }
  }.

  local equiv poly_mac1 :
    G2(O1).distinguish ~ G2(O2).distinguish : true ==> ={res}.
  proof. by trivial. qed.
end section.
"""


def test_scope_context_extracts_symbol_table_inputs() -> None:
    ctx = analyze_ec_scope_context(_SOURCE)
    assert ctx.local_modules == ("G2",)
    assert ctx.declared_modules == ("A",)
    assert ctx.section_bound_modules == ("G2", "A")
    assert "OpCC" in ctx.cloned_theories
    assert "OpCCinit" in ctx.cloned_theories
    assert "Ske" in ctx.cloned_theories
    assert "SKE_RND" in ctx.cloned_theories
    assert "MFinite" in ctx.cloned_theories
    assert "OpCCRO" in ctx.cloned_theories
    assert ctx.named_equivs == ("poly_mac1",)
    assert ctx.source_hash


def test_cloned_theory_lemma_uses_scope_context() -> None:
    ctx = analyze_ec_scope_context(_SOURCE)
    ok, hint = is_cloned_theory_lemma("OpCCRO.pr_CCP_OCCP", ctx)
    assert ok
    assert hint == "OpCCRO"
    local_ok, _ = is_cloned_theory_lemma("poly_mac1", ctx)
    assert not local_ok


def main() -> int:
    test_scope_context_extracts_symbol_table_inputs()
    test_cloned_theory_lemma_uses_scope_context()
    print("PASS test_ec_static_context")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
