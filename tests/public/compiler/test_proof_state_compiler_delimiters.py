"""The compiler's one bracket-depth scanner and its two disciplines."""

from __future__ import annotations

import pytest

from core.easycrypt.proof_state_compiler.delimiters import (
    PARENTHESES,
    balanced,
    find_top_level,
    matching_close,
    parenthesized,
    split_top_level,
    top_level_indices,
)


def test_lenient_scan_ignores_bracket_kind_and_stray_closers() -> None:
    assert find_top_level("f (a : b) : c", ":") == 10
    assert find_top_level("[a : b) : c", ":") == 8
    # A stray closer clamps depth at zero instead of hiding the separator.
    assert find_top_level("a) : b", ":") == 3
    assert find_top_level("(a : b", ":") == -1
    assert find_top_level("a : b : c", ":", start=3) == 6


def test_openers_select_which_brackets_group() -> None:
    text = "M{x y} (a b) c"
    assert next(
        index for index in top_level_indices(text) if text[index] == " "
    ) == 6
    assert next(
        index
        for index in top_level_indices(text, openers=PARENTHESES)
        if text[index] == " "
    ) == 3


def test_split_top_level_strips_parts_and_keeps_empty_ones() -> None:
    assert split_top_level("A => (B => C) => D", "=>") == ("A", "(B => C)", "D")
    assert split_top_level("a /\\ /\\ b", "/\\") == ("a", "", "b")
    assert split_top_level("", "=>") == ("",)


@pytest.mark.parametrize(
    ("text", "opening", "openers", "expected"),
    [
        ("(a [b] c) d", 0, "([{", 8),
        ("(a [b) c] d)", 0, "([{", 8),
        ("(a [b) c] d)", 0, PARENTHESES, 5),
        ("(a (b) c", 0, "([{", -1),
        ("x (a) (b)", 6, PARENTHESES, 8),
    ],
)
def test_matching_close_counts_depth_only(
    text: str, opening: int, openers: str, expected: int,
) -> None:
    assert matching_close(text, opening, openers=openers) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("(a)", True),
        ("((a) (b))", True),
        ("(a) (b)", False),
        ("(a", False),
        ("(", False),
        ("", False),
        ("[a]", False),
    ],
)
def test_parenthesized_requires_one_enclosing_group(text: str, expected: bool) -> None:
    assert parenthesized(text) is expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("f (a [b] {c})", True),
        ("(a]", False),
        ("(a [b) c]", False),
        ("a)", False),
        ("(a", False),
        ("", True),
    ],
)
def test_balanced_is_strict_about_kind_and_order(text: str, expected: bool) -> None:
    assert balanced(text) is expected
