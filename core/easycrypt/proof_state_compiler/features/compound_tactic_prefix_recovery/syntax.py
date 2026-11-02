"""Complete bounded lexical population for top-level compound prefixes."""

from __future__ import annotations

from core.easycrypt.proof_state_compiler.contracts.failure import (
    compound_prefix_remainder,
)
from core.easycrypt.proof_state_compiler.delimiters import (
    balanced,
    top_level_indices,
)


MAX_COMPOUND_TACTIC_BYTES = 16_384
MAX_COMPOUND_PREFIX_CANDIDATES = 8


def compound_prefix_candidates(tactic: str) -> tuple[str, ...]:
    """Return every proper top-level semicolon prefix, shortest first.

    This is only a lexical work bound.  EasyCrypt still parses the full tactic,
    diagnoses its rejection, and checks every returned candidate.  Ambiguous
    strings/comments and unbalanced delimiters abstain instead of guessing.
    """

    text = str(tactic or "")
    if (
        not text
        or text != text.strip()
        or len(text.encode("utf-8")) > MAX_COMPOUND_TACTIC_BYTES
        or not text.endswith(".")
        or '"' in text
        or "(*" in text
        or "*)" in text
        or "\x00" in text
    ):
        return ()
    body = text[:-1]
    if not body.strip() or not balanced(body):
        return ()
    cut_offsets = [
        offset for offset in top_level_indices(body) if body[offset] == ";"
    ]
    if (
        not cut_offsets
        or len(cut_offsets) > MAX_COMPOUND_PREFIX_CANDIDATES
        or not body[cut_offsets[-1] + 1 :].strip()
    ):
        return ()
    stage_boundaries = (-1, *cut_offsets, len(body))
    if any(
        not body[left + 1 : right].strip()
        for left, right in zip(stage_boundaries, stage_boundaries[1:])
    ):
        return ()
    candidates = tuple(
        body[:offset].rstrip() + "."
        for offset in cut_offsets
        if body[:offset].strip()
    )
    if (
        len(candidates) != len(cut_offsets)
        or len(candidates) != len(set(candidates))
    ):
        return ()
    return candidates


def compound_accepted_prefix_extension(
    tactic: str,
    *,
    accepted_prefix: str,
    candidate_prefixes: tuple[str, ...],
) -> str:
    """Return the exact first top-level stage after one accepted prefix.

    Candidate generation remains lexical and carries no semantic authority.
    The feature calls this only after EasyCrypt has rejected the full tactic
    and established one contiguous accepted prefix of the complete candidate
    population.
    """

    if (
        not accepted_prefix
        or accepted_prefix not in candidate_prefixes
        or not tactic.endswith(".")
        or not accepted_prefix.endswith(".")
    ):
        return ""
    index = candidate_prefixes.index(accepted_prefix)
    next_attempt = (
        candidate_prefixes[index + 1]
        if index + 1 < len(candidate_prefixes)
        else tactic
    )
    extension = compound_prefix_remainder(next_attempt, accepted_prefix)
    if extension is None:
        return ""
    return extension + "."
