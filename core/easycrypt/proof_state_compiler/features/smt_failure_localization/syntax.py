"""Bounded lexical gate for a direct smt-failure localization request.

The gate only avoids native work.  EasyCrypt alone parses the tactic, runs
it, and reports which smt call fails; nothing here is presented as a fact.

A direct request is made for one sentence that mentions an smt call and is
not a top-level ``;`` sequence.  The stage boundary of a top-level sequence,
like the sentence boundary of a multi-sentence commit, belongs to the
recovery-handoff source; this slice reaches such a commit only as the
consumer of that handoff, which runs the failing part in its temporary
state.  ``by``, ``first``, ``last`` and ``expect`` take every later ``;`` of
the sentence, so a ``;`` after one of them is part of its body and the
sentence is one tactic.  A tactic that is one smt call adds nothing: its
failed goal is the current goal, which the agent already sees.
"""

from __future__ import annotations

import re

from core.easycrypt.proof_state_compiler.delimiters import (
    balanced,
    matching_close,
    top_level_indices,
)
from core.easycrypt.proof_text import sentence_ends


MAX_SMT_LOCALIZATION_TACTIC_BYTES = 16_384
_SMT_CALL = re.compile(r"(?<![A-Za-z0-9_'.])smt(?![A-Za-z0-9_'])|/#")
_GREEDY_BODY = re.compile(
    r"(?<![A-Za-z0-9_'])(?:by|first|last|expect)(?![A-Za-z0-9_'])"
)
_LONE_SMT_HEAD = re.compile(r"(?:(?:by|try)\s+)?smt(?![A-Za-z0-9_'])")


def is_direct_smt_failure_candidate(tactic: str) -> bool:
    """Whether one failed commit may ask EasyCrypt to localize its smt call."""

    text = str(tactic or "")
    if (
        not text
        or text != text.strip()
        or len(text.encode("utf-8")) > MAX_SMT_LOCALIZATION_TACTIC_BYTES
        or not text.endswith(".")
        or any(token in text for token in ('"', "(*", "*)", "\x00"))
        or list(sentence_ends(text)) != [len(text)]
    ):
        return False
    body = text[:-1].strip()
    return bool(
        body
        and balanced(body)
        and _SMT_CALL.search(body) is not None
        and not _top_level_sequence(body)
        and not _lone_smt_call(body)
    )


def _top_level_sequence(body: str) -> bool:
    top_level = list(top_level_indices(body))
    separators = [index for index in top_level if body[index] == ";"]
    if not separators:
        return False
    outside = set(top_level)
    return not any(
        match.start() in outside
        for match in _GREEDY_BODY.finditer(body, 0, separators[0])
    )


def _lone_smt_call(body: str) -> bool:
    head = _LONE_SMT_HEAD.match(body)
    if head is None:
        return False
    rest = body[head.end():].lstrip()
    if rest.startswith("("):
        close = matching_close(rest, 0)
        if close < 0:
            return False
        rest = rest[close + 1:]
    return not rest.strip()
