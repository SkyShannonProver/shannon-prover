"""The one resolver for a lemma's declaration and its own proof.

Every consumer (precheck, write-back, extraction, eval source preparation,
verification, duplicate guard) reads the target through `lemma_decls`, so
these cases pin how EasyCrypt text is read: comments and strings are not
code, `(*)` is an operator, and a proof is only the target's own sentences.
"""
from __future__ import annotations

import pytest

from core.easycrypt.lemma_decls import (
    has_checked_proof,
    lemma_decl_lines,
    lemma_declarations,
    proof_tactics_span,
    target_declaration,
)


def _proof(source: str, name: str = "t", index: int = 0):
    declaration = lemma_declarations(source, name)[index]
    proof = declaration.proof
    return None if proof is None else (proof.kind, source[proof.start:proof.end])


@pytest.mark.parametrize("source, expected", [
    ("(* a (* lemma t : false. *) b *)\nlemma t : true.\nproof. trivial. qed.\n",
     ("qed", "proof. trivial. qed.")),
    ('op s = "(*".\nlemma t : true.\nproof.\n  trivial.\nqed.\n',
     ("qed", "proof.\n  trivial.\nqed.")),
    ("op (*) (x y : int) = x * y.\nlemma t : (*) 1 1 = 1.\nproof. by trivial. qed.\n",
     ("qed", "proof. by trivial. qed.")),
    ("lemma t : true.\nproof.\n  trivial. qed.\nlemma u : true.\nproof. admit. qed.\n",
     ("qed", "proof.\n  trivial. qed.")),
    ("lemma t (x : int) : x = x by smt().\nlemma u : true.\nproof. admit. qed.\n",
     ("by", "by smt().")),
    ("lemma t :\n  true\nby trivial.\n", ("by", "by trivial.")),
    ("section.\nlocal\nlemma t : true.\nproof.\n  admit.\nqed.\nend section.\n",
     ("qed", "proof.\n  admit.\nqed.")),
    ("lemma t : true.\nproof.\n  have := [0 .. 3].\n  trivial.\nqed.\n",
     ("qed", "proof.\n  have := [0 .. 3].\n  trivial.\nqed.")),
    ("lemma t : true.\nproof.\n  trivial.\nqed .\n",
     ("qed", "proof.\n  trivial.\nqed .")),
    # No `proof.`: the sentences up to `qed.` are still the target's own.
    ("lemma t : false.\n  admit.\nqed.\nlemma u : true.\nproof. trivial. qed.\n",
     ("qed", "admit.\nqed.")),
    # A bare `admit.` shell that nothing closes stops at the next declaration.
    ("lemma t : true.\nadmit.\nlemma u : true.\nproof. trivial. qed.\n",
     ("open", "admit.")),
    ("lemma t : true.\nproof.\n  trivial.\n", ("open", "proof.\n  trivial.")),
    ("lemma t : true.\nrealize foo. proof. trivial. qed.\n", None),
    ("ehoare t : M.f : 0%xr ==> 0%xr.\nproof. by proc. qed.\n",
     ("qed", "proof. by proc. qed.")),
])
def test_resolver_reads_the_target_as_easycrypt_does(source, expected) -> None:
    assert _proof(source) == expected


def test_abort_and_restate_are_two_declarations() -> None:
    source = (
        "lemma t : false.\nproof.\n  admit.\nabort.\n"
        "lemma t : true.\nproof.\n  trivial.\nqed.\n"
    )

    assert _proof(source, index=0) == ("open", "proof.\n  admit.\nabort.")
    assert _proof(source, index=1) == ("qed", "proof.\n  trivial.\nqed.")
    assert target_declaration(source, "t") == lemma_declarations(source, "t")[0]


def test_commented_and_quoted_copies_and_clone_overrides_are_not_declarations() -> None:
    source = (
        '(* lemma t : false. *)\nop s = "lemma t : false.".\n'
        "clone G as H with lemma t <- u.\n"
        "lemma t : true.\nproof. trivial. qed.\n"
    )

    assert lemma_decl_lines(source, "t") == [4]


@pytest.mark.parametrize("source, checked", [
    ("lemma t : true.\nproof. trivial. qed.\n", True),
    ("lemma t : true by trivial.\n", True),
    ("lemma t : true by admit.\n", False),
    ("lemma t : true.\nproof.\nqed.\n", False),
    ("lemma t : true.\nproof. (* nothing *) qed.\n", False),
    ("lemma t : true.\nproof.\n  admit.\nqed.\n", False),
    ("lemma t : true.\nproof.\n  trivial.\n", False),
])
def test_only_a_closed_nonempty_admit_free_proof_is_checked(source, checked) -> None:
    declaration = lemma_declarations(source, "t")[0]

    assert has_checked_proof(source, declaration) is checked


@pytest.mark.parametrize("source, tactics", [
    ("lemma t : true.\nproof.\n  move=> h.\n  trivial.\nqed.\n", "move=> h.\n  trivial.\n"),
    ("lemma t : true.\nproof. qed.\n", ""),
    ("lemma t : true by smt().\n", " smt()."),
    ("lemma t : true.\n  move=> h. trivial.\nqed.\n", "move=> h. trivial.\n"),
    ("lemma t : true.\nproof strict.\n  trivial.\nqed.\n", "proof strict.\n  trivial.\n"),
    ("lemma t : true.\nproof.\n  admit.\nlemma u : true.\n", "admit."),
])
def test_proof_tactics_leave_out_the_proof_markers(source, tactics) -> None:
    span = proof_tactics_span(source, lemma_declarations(source, "t")[0])
    assert source[span[0]:span[1]] == tactics


def test_a_declaration_without_proof_has_no_tactics() -> None:
    source = "lemma t : true.\nlemma u : true.\n"
    assert proof_tactics_span(source, lemma_declarations(source, "t")[0]) is None
