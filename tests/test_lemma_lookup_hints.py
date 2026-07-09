"""Tests for contextual EasyCrypt lemma hints."""
from __future__ import annotations

import sys
from pathlib import Path


import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from core.easycrypt.search.ec_lemma_lookup import format_hints, lookup_for_goal  # type: ignore  # noqa: E402


def test_group_algebra_goal_surfaces_clone_qualified_lookup_guidance() -> None:
    hints = lookup_for_goal(
        "g ^ (x + y) = g ^ x * g ^ y /\\ DH.G.exp z = g ^ z",
        max_total=8,
    )
    names = [hint["name"] for hint in hints]
    rendered = format_hints(hints)

    assert names[:2] == ["expD", "expM"]
    assert "lookup_symbol" in rendered
    assert "DH.G.expD" in rendered


def test_block_and_list_goal_surfaces_local_and_stdlib_names() -> None:
    hints = lookup_for_goal(
        "nth witness (bytes_of_block (block_of_bytesd bs) ++ mkseq f n) i = x",
        max_total=10,
    )
    names = {hint["name"] for hint in hints}

    assert "block_of_bytesdK" in names
    assert "Block.block_of_bytesdK" in names
    assert "nth_cat" in names
    assert "nth_mkseq" in names
