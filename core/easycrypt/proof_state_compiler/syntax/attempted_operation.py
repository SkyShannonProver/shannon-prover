"""Bounded syntax shared by the attempted-operation frontend and P4 guard."""

from __future__ import annotations

import re

from core.easycrypt.proof_state_compiler.delimiters import (
    balanced,
    matching_close,
    top_level_indices,
)


_OPERATION_HEAD = re.compile(
    r"^\s*(apply|exact|call|conseq)\s+\(*\s*"
    r"([A-Za-z_][A-Za-z0-9_']*(?:\.[A-Za-z_][A-Za-z0-9_']*)*)"
)
_REWRITE_OPERATION = re.compile(
    r"^\s*rewrite\s+"
    r"([A-Za-z_][A-Za-z0-9_']*(?:\.[A-Za-z_][A-Za-z0-9_']*)*)"
    r"(?:\s+in\s+[A-Za-z_][A-Za-z0-9_']*)?\s*\.\s*$"
)


def operation_resource(tactic: str) -> tuple[str, str] | None:
    """Parse the selected operation/resource from one bounded tactic only."""

    tactic = str(tactic or "").strip()
    if not _is_single_bounded_tactic(tactic):
        return None
    match = _OPERATION_HEAD.match(tactic)
    if match is None:
        return None
    return match.group(1), match.group(2)


def single_operation_identity(tactic: str) -> tuple[str, str] | None:
    """Return one active native-backed operation and selected resource."""

    parsed = operation_resource(tactic)
    if parsed is not None:
        return parsed
    tactic = str(tactic or "").strip()
    if not _is_single_bounded_tactic(tactic):
        return None
    match = _REWRITE_OPERATION.fullmatch(tactic)
    return None if match is None else ("rewrite", match.group(1))


def bare_operation_resource(tactic: str) -> tuple[str, str] | None:
    """Return the operation/resource only when the proof term is a bare head.

    This is the shared fail-closed boundary for repairs that may change only
    namespace spelling or fill arguments after an exact rejected commitment.
    It deliberately rejects partially applied terms so a recovery family
    cannot silently discard an argument supplied by the agent.
    """

    parsed = operation_head_arguments(tactic)
    if parsed is None or parsed[2]:
        return None
    return parsed[0], parsed[1]


def operation_head_arguments(tactic: str) -> tuple[str, str, str] | None:
    """Return operation, head resource, and the argument text after the head.

    Only a bare head or one parenthesized application spanning the whole
    proof term is accepted.  Replacing the head spelling in such a term keeps
    every argument written by the agent byte-identical.
    """

    parsed = operation_resource(tactic)
    if parsed is None:
        return None
    operation, resource = parsed
    body = tactic.strip()[:-1].strip()
    if not body.startswith(operation):
        return None
    term = body[len(operation):].strip()
    parenthesized = False
    while term.startswith("(") and matching_close(term, 0) == len(term) - 1:
        term = term[1:-1].strip()
        parenthesized = True
    if term == resource:
        return operation, resource, ""
    if (
        not parenthesized
        or not term.startswith(resource)
        or not term[len(resource)].isspace()
    ):
        return None
    return operation, resource, term[len(resource):].strip()


def _is_single_bounded_tactic(tactic: str) -> bool:
    """Accept one terminated tactic and fail closed on tactic sequencing.

    EasyCrypt uses ``.`` both as the command terminator and inside qualified
    names.  A prefix regex therefore cannot establish the one-operation
    recovery boundary.  This small scanner permits identifier qualification
    and balanced proof-term delimiters, but rejects any second top-level
    command, tactic combinator, comment, string, or malformed delimiter.
    """

    if (
        not tactic.endswith(".")
        or any(token in tactic for token in (";", "\n", "\r", "(*", "*)", '"'))
    ):
        return False
    body = tactic[:-1]
    if not body.strip() or not balanced(body):
        return False
    for index in top_level_indices(body):
        if body[index] != ".":
            continue
        previous = body[index - 1] if index else ""
        following = body[index + 1] if index + 1 < len(body) else ""
        if not (_identifier_char(previous) and _identifier_start(following)):
            return False
    return True


def _identifier_start(char: str) -> bool:
    return bool(char) and (char.isalpha() or char == "_")


def _identifier_char(char: str) -> bool:
    return bool(char) and (char.isalnum() or char in "_'")
