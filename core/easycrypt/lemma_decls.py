"""Where a lemma is declared and where its own proof is, as EasyCrypt reads it.

This is the one resolver for "the declaration of lemma X and its proof
block". The single-lemma precheck, proof write-back, extraction, evaluation
source preparation, verification and the startup duplicate guard all use it,
so they cannot disagree about which text belongs to the target.

Matching runs on ``proof_text.easycrypt_code``: comments and string literals
are blanked with every offset kept, so a commented-out copy is not a
declaration and every offset is valid in the original source.

A name declared more than once makes name-based lookup ambiguous, so runs
reject duplicate targets at startup; the helpers here still return every
declaration so callers can see the ambiguity.
"""

from __future__ import annotations

import re
from bisect import bisect_right
from dataclasses import dataclass

from core.easycrypt.proof_text import (
    easycrypt_code,
    sentence_ends,
    unchecked_proof_constructs,
)

# Keywords that declare a statement with a proof, after an optional `local`.
DECLARATION_KEYWORDS = r"lemma|theorem|equiv|hoare|ehoare|phoare"
_BY_RE = re.compile(r"(?<![\w'])by(?![\w'])")
_QED_SENTENCE_RE = re.compile(r"qed\s*\.")
_EMPTY_PROOF_MARKER_RE = re.compile(r"(?<![\w'])(?:proof|qed)\.")
_PROOF_OPENER_RE = re.compile(r"proof\s*\.(?=\s|$)")
# Sentences that start a new declaration. Inside a proof every sentence is a
# tactic, and none of these words starts one (`hoare`/`phoare` can, so they
# are left out).
_DECLARATION_SENTENCE_RE = re.compile(
    r"(?:(?:local|declare|global)\s+)?"
    r"(?:lemma|theorem|axiom|equiv|op|pred|type|module|clone|require|section"
    r"|theory|abstract|end|realize)(?![\w'])"
)


def lemma_decl_re(lemma_name: str) -> re.Pattern[str]:
    """Pattern matching a declaration of ``lemma_name`` (any decl keyword).

    A clone override such as ``lemma x <- y`` names a lemma of the cloned
    theory and declares nothing, so it does not match.
    """
    return re.compile(
        rf"(?<![\w'])\b(?:local\s+)?(?:{DECLARATION_KEYWORDS})\s+"
        + re.escape(lemma_name)
        + r"(?=[\s:(\[]|$)(?!\s*(?:=|<-|<=))",
    )


@dataclass(frozen=True)
class LemmaProof:
    """A declaration's own proof as a span of the source.

    ``kind`` is ``"by"`` for a ``by`` tactic that ends the declaration
    sentence (the span runs from ``by`` to its final dot), ``"qed"`` for the
    sentences after the declaration up to and including ``qed.``, and
    ``"open"`` for sentences that no ``qed.`` closes before the next
    declaration or the end of the source, such as a bare ``admit.`` shell or
    a proof cut off at the end of a file. EasyCrypt accepts a proof left
    open at the end of a file, so an open proof never counts as checked.
    """

    kind: str
    start: int
    end: int


@dataclass(frozen=True)
class LemmaDeclaration:
    """One declaration of a name, as offsets into the source."""

    start: int
    name_end: int
    # Just past the declaration sentence's final dot; None if it never ends.
    statement_end: int | None
    proof: LemmaProof | None


def lemma_declarations(content: str, lemma_name: str) -> list[LemmaDeclaration]:
    """Every declaration of ``lemma_name`` with its own proof, in source order."""
    code = easycrypt_code(content)
    ends = list(sentence_ends(content, code))
    return [
        _declaration(code, ends, match)
        for match in lemma_decl_re(lemma_name).finditer(code)
    ]


def _declaration(code: str, ends: list[int], match: re.Match[str]) -> LemmaDeclaration:
    index = bisect_right(ends, match.end())
    if index == len(ends):
        return LemmaDeclaration(match.start(), match.end(), None, None)
    statement_end = ends[index]
    by = _BY_RE.search(code, match.end(), statement_end - 1)
    if by is not None:
        proof = LemmaProof("by", by.start(), statement_end)
        return LemmaDeclaration(match.start(), match.end(), statement_end, proof)
    proof_start = None
    last_end = statement_end
    for end in ends[index + 1:]:
        start = end - len(code[last_end:end].lstrip())
        sentence = code[start:end]
        if _DECLARATION_SENTENCE_RE.match(sentence):
            break
        if proof_start is None:
            proof_start = start
        last_end = end
        if _QED_SENTENCE_RE.fullmatch(sentence):
            proof = LemmaProof("qed", proof_start, end)
            return LemmaDeclaration(match.start(), match.end(), statement_end, proof)
    proof = None if proof_start is None else LemmaProof("open", proof_start, last_end)
    return LemmaDeclaration(match.start(), match.end(), statement_end, proof)


def has_checked_proof(content: str, declaration: LemmaDeclaration) -> bool:
    """Whether the declaration's own proof is closed, non-empty and skips no goal.

    The scan for unchecked constructs starts at the declaration, so a
    ``by admit`` in its sentence counts too.
    """
    proof = declaration.proof
    if proof is None or proof.kind == "open":
        return False
    if unchecked_proof_constructs(content[declaration.start:proof.end]):
        return False
    body = easycrypt_code(content[proof.start:proof.end])
    return bool(_EMPTY_PROOF_MARKER_RE.sub("", body).strip())


def proof_tactics_span(
    content: str, declaration: LemmaDeclaration,
) -> tuple[int, int] | None:
    """Offsets of the tactics in a declaration's own proof, if it has one.

    A leading ``proof.`` with the blanks after it and the closing ``qed.``
    are left out; for a ``by`` proof the span is what follows ``by``.
    """
    proof = declaration.proof
    if proof is None:
        return None
    if proof.kind == "by":
        return proof.start + len("by"), proof.end
    code = easycrypt_code(content)
    start, end = proof.start, proof.end
    opener = _PROOF_OPENER_RE.match(code, start)
    if opener is not None:
        start = opener.end()
        while start < end and content[start].isspace():
            start += 1
    if proof.kind == "qed":
        end = max(start, code.rfind("qed", start, end))
    return start, end


def target_declaration(content: str, lemma_name: str) -> LemmaDeclaration | None:
    """The declaration a proof search for ``lemma_name`` works on.

    With several declarations, the first one still needing a proof wins.
    """
    declarations = lemma_declarations(content, lemma_name)
    for declaration in declarations:
        if not has_checked_proof(content, declaration):
            return declaration
    return declarations[0] if declarations else None


def lemma_decl_matches(content: str, lemma_name: str) -> list[re.Match[str]]:
    """All declaration matches of ``lemma_name``; offsets index ``content``."""
    return list(lemma_decl_re(lemma_name).finditer(easycrypt_code(content)))


def lemma_decl_lines(content: str, lemma_name: str) -> list[int]:
    """1-based line numbers of every declaration of ``lemma_name``."""
    return [
        content.count("\n", 0, match.start()) + 1
        for match in lemma_decl_matches(content, lemma_name)
    ]
