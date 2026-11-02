"""Bracket-depth scanning shared by every lexical check in the compiler.

These scans only bound candidate discovery and fail closed; EasyCrypt alone
decides whether a text parses.  Two depth disciplines exist on purpose:

* ``top_level_indices`` and the helpers built on it read printed goals and
  declarations leniently: bracket kinds are not matched and a closer with no
  open bracket is ignored, so one stray character cannot hide every later
  separator.
* ``balanced`` is strict: every bracket closes in order with its own kind.
  It admits agent-written tactics and arguments before they are quoted back
  or recomposed.

``openers`` selects which brackets count toward depth.  The module-binder and
module-application scans count parentheses only.
"""

from __future__ import annotations

from collections.abc import Iterator


BRACKETS = "([{"
PARENTHESES = "("
_CLOSER = {"(": ")", "[": "]", "{": "}"}


def _closers(openers: str) -> str:
    return "".join(_CLOSER[opener] for opener in openers)


def top_level_indices(
    text: str,
    *,
    start: int = 0,
    openers: str = BRACKETS,
) -> Iterator[int]:
    """Yield every index from ``start`` that is outside all brackets.

    Bracket characters themselves are never yielded.
    """

    closers = _closers(openers)
    depth = 0
    for index in range(start, len(text)):
        char = text[index]
        if char in openers:
            depth += 1
        elif char in closers:
            depth = max(0, depth - 1)
        elif depth == 0:
            yield index


def find_top_level(
    text: str,
    token: str,
    *,
    start: int = 0,
    openers: str = BRACKETS,
) -> int:
    """Return the first top-level index where ``token`` starts, else -1."""

    for index in top_level_indices(text, start=start, openers=openers):
        if text.startswith(token, index):
            return index
    return -1


def split_top_level(text: str, token: str) -> tuple[str, ...]:
    """Split ``text`` at every top-level ``token``; parts are stripped."""

    parts: list[str] = []
    start = 0
    for index in top_level_indices(text):
        if index >= start and text.startswith(token, index):
            parts.append(text[start:index].strip())
            start = index + len(token)
    parts.append(text[start:].strip())
    return tuple(parts)


def matching_close(
    text: str,
    opening: int,
    *,
    openers: str = BRACKETS,
) -> int:
    """Return where the bracket at ``opening`` closes by depth, else -1."""

    closers = _closers(openers)
    depth = 0
    for index in range(opening, len(text)):
        char = text[index]
        if char in openers:
            depth += 1
        elif char in closers:
            depth -= 1
            if depth == 0:
                return index
    return -1


def parenthesized(text: str) -> bool:
    """Whether the ``(`` that starts ``text`` closes at its last character."""

    return bool(text) and text[0] == "(" and (
        matching_close(text, 0, openers=PARENTHESES) == len(text) - 1
    )


def balanced(text: str) -> bool:
    """Whether every bracket in ``text`` closes in order with its own kind."""

    expected: list[str] = []
    for char in text:
        if char in _CLOSER:
            expected.append(_CLOSER[char])
        elif char in _CLOSER.values() and (
            not expected or expected.pop() != char
        ):
            return False
    return not expected
