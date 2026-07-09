#!/usr/bin/env python3
"""Unit tests for the whole-file lemma index (statement extraction).

Family-general + synthetic source (no ChaChaPoly/MEE tokens). The key property
is eval-safety: the index carries lemma *statements* (signatures) only and never
a proof body / tactic, so it is admissible under eval mode.

Run: python3 -m pytest tests/test_lemma_index.py -q
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from core.easycrypt import ec_file_index as fi  # type: ignore  # noqa: E402

SYNTH = """require import AllCore.

lemma single_line (x : int) : x = x.
proof. trivial. qed.

lemma multi_line (f : 'a -> 'b) s t :
  size (foo f s t) = min (size s) (size t).
proof.
  byequiv => //.
  proc; inline *.
  admit.
qed.

section S.
  declare module E <: T.
  local lemma in_section &m :
    Pr[A.main() @ &m : res] = Pr[B.main() @ &m : res].
  proof.
    congr.
    admit.
  qed.
end section S.
"""

# proof-body tokens that must NEVER appear in the index
_PROOF_LEAK = ("trivial.", "byequiv", "inline *", "congr.", "admit.", "qed.")


def _index():
    fd, name = tempfile.mkstemp(suffix=".ec")
    import os
    os.close(fd)
    p = Path(name)
    p.write_text(SYNTH)
    try:
        return fi.index_ec_file(p)
    finally:
        p.unlink(missing_ok=True)


def test_all_lemmas_have_statements():
    idx = _index()
    by_name = {l["name"]: l for l in idx["all_lemmas"]}
    assert set(by_name) == {"single_line", "multi_line", "in_section"}
    # single-line statement captured, no proof
    assert by_name["single_line"]["statement"] == "lemma single_line (x : int) : x = x."
    # multi-line statement captured across both lines, stops before proof.
    stmt = by_name["multi_line"]["statement"]
    assert stmt.startswith("lemma multi_line")
    assert "size (foo f s t) = min (size s) (size t)." in stmt
    assert "proof" not in stmt and "admit" not in stmt and "byequiv" not in stmt
    # section lemma: statement only, location tagged
    assert by_name["in_section"]["location"] == "in_section"
    assert "Pr[A.main()" in by_name["in_section"]["statement"]
    assert "congr" not in by_name["in_section"]["statement"]


def test_extract_statement_stops_before_proof():
    lines = SYNTH.split("\n")
    # multi_line lemma declaration is the 6th line (index 5)
    start = next(i for i, l in enumerate(lines) if l.startswith("lemma multi_line"))
    stmt = fi._extract_statement(lines, start)
    assert "min (size s) (size t)." in stmt
    for leak in ("proof.", "byequiv", "inline *", "admit."):
        assert leak not in stmt


def test_format_lemma_index_leaks_no_proof():
    idx = _index()
    out = fi.format_lemma_index(idx)
    assert "3 lemma statement(s)" in out
    assert "single_line" in out and "multi_line" in out and "in_section" in out
    for leak in _PROOF_LEAK:
        assert leak not in out, f"proof token leaked into lemma index: {leak!r}"


def test_extract_statement_stops_at_inline_by_closed_lemma():
    # a `by`-closed lemma has no proof./qed.; the scan must stop at `by` and
    # neither leak the inline tactic nor swallow the following lemma.
    src = (
        "lemma by_closed : is_lossless dmap by exact/dmap_ll.\n"
        "\n"
        "lemma next_one (x : int) : x = x.\n"
        "proof. trivial. qed.\n"
    )
    lines = src.split("\n")
    stmt = fi._extract_statement(lines, 0)
    assert stmt == "lemma by_closed : is_lossless dmap"
    assert "exact" not in stmt and "dmap_ll" not in stmt
    assert "next_one" not in stmt        # did not run into the following lemma


def test_index_by_closed_lemmas_leak_no_proof():
    src = (
        "require import AllCore.\n\n"
        "lemma ll_a : is_lossless da by exact/da_ll.\n\n"
        "lemma ll_b : is_lossless db by exact/db_ll.\n"
    )
    import os
    fd, name = tempfile.mkstemp(suffix=".ec")
    os.close(fd)
    p = Path(name)
    p.write_text(src)
    try:
        idx = fi.index_ec_file(p)
    finally:
        p.unlink(missing_ok=True)
    out = fi.format_lemma_index(idx)
    # the inline proof (`by exact/da_ll.`) must not leak. ("exact" on its own
    # appears in the index boilerplate "the exact declaration", so assert on the
    # proof-specific tokens instead.)
    assert "exact/" not in out and "da_ll" not in out and "db_ll" not in out
    assert {"ll_a", "ll_b"} <= {l["name"] for l in idx["all_lemmas"]}


def test_format_lemma_index_empty():
    out = fi.format_lemma_index({"file": "x.ec", "all_lemmas": []})
    assert "no lemmas found" in out
