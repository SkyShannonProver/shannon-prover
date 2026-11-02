"""Locate a delegated lemma's proof in project source text."""

from __future__ import annotations

import re

from core.easycrypt.eval_source_prep import find_target_proof_block


def proof_body_span(content: str, lemma: str) -> tuple[str, tuple[int, int]]:
    """Return every byte between ``proof.`` and the final ``qed.``, and its span.

    Leading whitespace belongs to the body: a proof agent may indent its first
    tactic differently from the outer admit shell, and that must not count as
    a change outside the delegated body when the proof is merged back.
    """

    block = find_target_proof_block(content, lemma)
    if block is None:
        raise ValueError(f"could not find proof block for {lemma}")
    start, end = block
    block_text = content[start:end]
    proof = re.search(r"(?i)\bproof\s*\.", block_text)
    qed = list(re.finditer(r"(?i)\bqed\s*\.", block_text))
    if proof is None or not qed or qed[-1].start() < proof.end():
        raise ValueError(f"{lemma} has no proof./qed. block")
    body_start = start + proof.end()
    body_end = start + qed[-1].start()
    return content[body_start:body_end], (body_start, body_end)


def lemma_prefix_projection(content: str, lemma: str) -> str:
    """Normalize the delegated proof and ignore declarations after it.

    A continuation may replace later, not-yet-proved lemmas with admit shells
    solely to keep the current target loadable.  Those later declarations
    cannot participate in the proof of ``lemma``.  Binding the handoff through
    the end of the selected lemma therefore preserves every relevant source
    byte while allowing a loadable continuation seed to differ in its suffix.
    """

    block = find_target_proof_block(content, lemma)
    if block is None:
        raise ValueError(f"could not project proof block for {lemma}")
    start, _ = block
    return content[:start] + "proof.\n  admit.\nqed."
