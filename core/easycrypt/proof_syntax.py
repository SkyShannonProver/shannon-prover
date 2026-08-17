"""Shared lexical helpers for EasyCrypt proof blocks."""

from __future__ import annotations

import re
from dataclasses import dataclass

from core.easycrypt.lemma_decls import mask_comments


_PROOF_MARKER_RE = re.compile(r"(?<![A-Za-z0-9_'])proof\.")
_QED_MARKER_RE = re.compile(r"(?<![A-Za-z0-9_'])qed\.")


@dataclass(frozen=True)
class InlineProof:
    """A ``proof. ... qed.`` block contained on one physical line."""

    proof_start: int
    proof_end: int
    qed_start: int
    qed_end: int

    def open_line(self, source: str) -> str:
        """Return the declaration/proof prefix with the proof left open."""
        newline = "\n" if source.endswith("\n") else ""
        return source[:self.proof_end].rstrip() + newline


def inline_proof(
    source: str,
    *,
    masked_source: str | None = None,
) -> InlineProof | None:
    """Locate a single-line proof without matching markers inside comments."""
    masked = mask_comments(source) if masked_source is None else masked_source
    proof = _PROOF_MARKER_RE.search(masked)
    if proof is None:
        return None
    qed = _QED_MARKER_RE.search(masked, proof.end())
    if qed is None:
        return None
    return InlineProof(
        proof_start=proof.start(),
        proof_end=proof.end(),
        qed_start=qed.start(),
        qed_end=qed.end(),
    )
