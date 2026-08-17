"""Complete bounded lexical population for top-level compound prefixes."""

from __future__ import annotations


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
    if not body.strip():
        return ()
    opening = {"(": ")", "[": "]", "{": "}"}
    closing = set(opening.values())
    stack: list[str] = []
    cut_offsets: list[int] = []
    for offset, char in enumerate(body):
        if char in opening:
            stack.append(opening[char])
        elif char in closing:
            if not stack or stack.pop() != char:
                return ()
        elif char == ";" and not stack:
            cut_offsets.append(offset)
            if len(cut_offsets) > MAX_COMPOUND_PREFIX_CANDIDATES:
                return ()
    if stack or not cut_offsets or not body[cut_offsets[-1] + 1 :].strip():
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
    prefix_body = accepted_prefix[:-1].rstrip()
    next_body = next_attempt[:-1]
    if not prefix_body or not next_body.startswith(prefix_body):
        return ""
    remainder = next_body[len(prefix_body):].lstrip()
    if not remainder.startswith(";"):
        return ""
    extension = remainder[1:].strip()
    if not extension:
        return ""
    return extension + "."
