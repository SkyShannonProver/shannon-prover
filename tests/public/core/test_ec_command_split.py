"""Sentence splitting and comment masking follow EasyCrypt's lexer.

``(*)`` is an operator section and a ``(*`` inside a string opens no comment;
treating either as a comment opener merged every later sentence into one
command for the persistent EC process. ``..`` is one token, so the dot after
it is not final.
"""
from __future__ import annotations

import pytest

from core.easycrypt.lemma_decls import lemma_decl_lines
from core.easycrypt.proof_text import split_ec_commands, split_tactic_chain, strip_comments


@pytest.mark.parametrize("text, expected", [
    (
        "have h : (*) 1 1 = 1 by trivial.\ntrivial.\n",
        ["have h : (*) 1 1 = 1 by trivial.\n", "trivial.\n"],
    ),
    (
        "have h : (* ) 2 2 = 4 by trivial. trivial.",
        ["have h : (* ) 2 2 = 4 by trivial. ", "trivial."],
    ),
    ('idtac "(*". trivial.\n', ['idtac "(*". ', "trivial.\n"]),
    ("(* a. b. *) wp.\nskip.\n", ["(* a. b. *) wp.\n", "skip.\n"]),
    ("require (*--*) Foo.\nwp.(* c *)\n", ["require (*--*) Foo.\n", "wp.(* c *)"]),
    ("move=> x.\n  apply H. (* tail *)", ["move=> x.\n", "  apply H. ", "(* tail *)"]),
    # `..` is one token, so `[1 .. 2]` does not end the sentence.
    ("outline {1} [1 .. 2] b.\nskip.\n", ["outline {1} [1 .. 2] b.\n", "skip.\n"]),
    ("p <$ [lo .. hi]; r <- p... \nwp.", ["p <$ [lo .. hi]; r <- p... \n", "wp."]),
])
def test_split_ec_commands_follows_the_easycrypt_lexer(text, expected) -> None:
    assert split_ec_commands(text) == expected


def test_strip_comments_keeps_operator_sections_as_code() -> None:
    content = "op (*) (x y : int) = x * y.\nlemma foo : true.\n"

    assert strip_comments(content) == content
    assert lemma_decl_lines(content, "foo") == [2]


def test_strip_comments_ignores_comment_openers_in_strings() -> None:
    content = 'op s = "(*".\nlemma foo : true.\n'

    assert lemma_decl_lines(content, "foo") == [2]


def test_strip_comments_blanks_comments_and_discarded_sections() -> None:
    content = "(* lemma foo : true. *)\n(*--*) lemma bar : true.\n"
    masked = strip_comments(content)

    assert len(masked) == len(content)
    assert lemma_decl_lines(content, "foo") == []
    assert lemma_decl_lines(content, "bar") == [2]
    assert masked.splitlines()[1].strip() == "lemma bar : true."


@pytest.mark.parametrize("text, expected", [
    ("a. b", ["a.", "b."]),
    ("  move=> h.  smt().\n", ["move=> h.", "smt()."]),
    ("rewrite /f (* a. b *) /g. auto.", ["rewrite /f (* a. b *) /g.", "auto."]),
    ("outline {1} [1 .. 2] b. auto.", ["outline {1} [1 .. 2] b.", "auto."]),
    ("case: x => [->|h] . by [].", ["case: x => [->|h] .", "by []."]),
    ("(* only *)", ["(* only *)."]),
])
def test_a_chain_request_splits_at_sentence_ends(text, expected) -> None:
    # The backend commits these tactics and the manager binds its request to
    # them, so both sides read the chain through split_tactic_chain.
    assert split_tactic_chain(text) == expected
