"""Bounded syntax shared by the attempted-operation frontend and P4 guard."""

from __future__ import annotations

import re


_OPERATION_HEAD = re.compile(
    r"^\s*(apply|exact|call|conseq)\s+\(*\s*"
    r"([A-Za-z_][A-Za-z0-9_']*(?:\.[A-Za-z_][A-Za-z0-9_']*)*)"
)
_REWRITE_OPERATION = re.compile(
    r"^\s*rewrite\s+"
    r"([A-Za-z_][A-Za-z0-9_']*(?:\.[A-Za-z_][A-Za-z0-9_']*)*)"
    r"(?:\s+in\s+[A-Za-z_][A-Za-z0-9_']*)?\s*\.\s*$"
)
_OPEN_TO_CLOSE = {"(": ")", "[": "]", "{": "}"}
_CLOSE_TO_OPEN = {value: key for key, value in _OPEN_TO_CLOSE.items()}


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

    parsed = operation_resource(tactic)
    if parsed is None:
        return None
    operation, resource = parsed
    body = tactic.strip()[:-1].strip()
    if not body.startswith(operation):
        return None
    term = body[len(operation):].strip()
    while term.startswith("(") and term.endswith(")"):
        term = term[1:-1].strip()
    return parsed if term == resource else None


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
    if not body.strip():
        return False
    delimiters: list[str] = []
    for index, char in enumerate(body):
        if char in _OPEN_TO_CLOSE:
            delimiters.append(char)
            continue
        if char in _CLOSE_TO_OPEN:
            if not delimiters or delimiters.pop() != _CLOSE_TO_OPEN[char]:
                return False
            continue
        if char != "." or delimiters:
            continue
        previous = body[index - 1] if index else ""
        following = body[index + 1] if index + 1 < len(body) else ""
        if not (_identifier_char(previous) and _identifier_start(following)):
            return False
    return not delimiters


def _identifier_start(char: str) -> bool:
    return bool(char) and (char.isalpha() or char == "_")


def _identifier_char(char: str) -> bool:
    return bool(char) and (char.isalnum() or char in "_'")


OPERATION_HEAD_PATTERN = _OPERATION_HEAD.pattern
