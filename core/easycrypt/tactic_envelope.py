"""Canonical extraction of one leading EasyCrypt structural command.

This is deliberately not a parser for the full EasyCrypt tactical language.
It separates the leading command that owns a balanced structural payload from
the branch/closing tactical attached after it. Consumers keep ``raw_tactic``
for audit and use ``core`` only when ``exact`` is true.
"""
from __future__ import annotations

from dataclasses import dataclass
import re


_TRAILING_ARROW_HEADS = frozenset({"byequiv", "byphoare", "conseq", "call", "ecall"})
_RELATION_HEADS = frozenset({"byequiv", "byphoare", "conseq", "equiv"})
_MULTI_ARGUMENT_HEADS = frozenset({"conseq"})


@dataclass(frozen=True)
class StructuralTacticEnvelope:
    raw_tactic: str
    leading_control: str
    head: str
    core: str
    continuation: str
    exact: bool


def extract_structural_tactic_envelope(tactic: str) -> StructuralTacticEnvelope:
    """Separate a leading structural command from attached tactical control.

    Examples include ``byequiv (_: ...)=> //.`` and
    ``call (_: ...); 1: apply H.``. A malformed balanced payload or an unknown
    suffix is left unsplit with ``exact=False`` so semantic analyzers do not
    infer facts from a guessed command boundary.
    """
    raw = str(tactic or "").strip()
    if not raw:
        return StructuralTacticEnvelope("", "", "", "", "", False)

    leading_end = _leading_control_end(raw)
    leading = raw[:leading_end].strip()
    command = raw[leading_end:].strip()
    head_match = re.match(
        r"(?P<head>[A-Za-z_][A-Za-z0-9_]*)\b(?:\{[12]\})?",
        command,
    )
    if not head_match:
        return StructuralTacticEnvelope(raw, leading, "", command, "", False)
    head = head_match.group("head").lower()

    if head in _MULTI_ARGUMENT_HEADS:
        split_index = _top_level_continuation_index(command, head=head)
        core = command[:split_index].strip() if split_index >= 0 else command
        if not _balanced_delimiters(core):
            return StructuralTacticEnvelope(raw, leading, head, command, "", False)
        return StructuralTacticEnvelope(
            raw,
            leading,
            head,
            core,
            command[split_index:].strip() if split_index >= 0 else "",
            True,
        )

    payload_match = re.match(
        r"\(\s*(?:_\s*)?:",
        command[head_match.end():].lstrip(),
    )
    if payload_match:
        suffix_start = head_match.end()
        while suffix_start < len(command) and command[suffix_start].isspace():
            suffix_start += 1
        open_index = suffix_start + payload_match.start()
        close_index = _matching_group_end(command, open_index)
        if close_index < 0:
            return StructuralTacticEnvelope(raw, leading, head, command, "", False)
        tail = command[close_index + 1 :].strip()
        core = command[: close_index + 1].strip()
        if not tail:
            return StructuralTacticEnvelope(raw, leading, head, core, "", True)
        if tail.startswith("."):
            return StructuralTacticEnvelope(
                raw,
                leading,
                head,
                core + ".",
                tail[1:].strip(),
                True,
            )
        continuation_index = _top_level_continuation_index(tail, head=head)
        if continuation_index == 0:
            return StructuralTacticEnvelope(raw, leading, head, core, tail, True)
        if head in _RELATION_HEADS and tail.startswith(":"):
            if continuation_index < 0:
                return StructuralTacticEnvelope(
                    raw, leading, head, command, "", True
                )
            suffix = tail[:continuation_index].strip()
            return StructuralTacticEnvelope(
                raw,
                leading,
                head,
                f"{core} {suffix}",
                tail[continuation_index:].strip(),
                True,
            )
        return StructuralTacticEnvelope(raw, leading, head, command, "", False)

    split_index = _top_level_continuation_index(command, head=head)
    if split_index >= 0:
        return StructuralTacticEnvelope(
            raw,
            leading,
            head,
            command[:split_index].strip(),
            command[split_index:].strip(),
            True,
        )
    return StructuralTacticEnvelope(raw, leading, head, command, "", True)


def _leading_control_end(text: str) -> int:
    cursor = 0
    while cursor < len(text):
        start = cursor
        while cursor < len(text) and text[cursor].isspace():
            cursor += 1
        bullet = re.match(r"[+*~-]+\s*", text[cursor:])
        if bullet:
            cursor += bullet.end()
            continue
        selector = re.match(r"\d+\s*:\s*", text[cursor:])
        if selector:
            cursor += selector.end()
            continue
        by_prefix = re.match(r"by\b\s*", text[cursor:], flags=re.IGNORECASE)
        if by_prefix:
            cursor += by_prefix.end()
            continue
        return start
    return cursor


def _matching_group_end(text: str, open_index: int) -> int:
    pairs = {"(": ")", "[": "]", "{": "}"}
    if open_index < 0 or open_index >= len(text) or text[open_index] not in pairs:
        return -1
    stack: list[str] = []
    for index in range(open_index, len(text)):
        char = text[index]
        if char in pairs:
            stack.append(pairs[char])
        elif char in ")]}" and stack:
            if char != stack[-1]:
                return -1
            stack.pop()
            if not stack:
                return index
    return -1


def _top_level_continuation_index(text: str, *, head: str) -> int:
    pairs = {"(": ")", "[": "]", "{": "}"}
    stack: list[str] = []
    index = 0
    while index < len(text):
        char = text[index]
        if char in pairs:
            stack.append(pairs[char])
        elif char in ")]}" and stack:
            if char != stack[-1]:
                return -1
            stack.pop()
        elif not stack:
            if char == ";":
                return index
            if (
                head in _TRAILING_ARROW_HEADS
                and text[index : index + 2] == "=>"
                and (index == 0 or text[index - 1] != "=")
            ):
                return index
        index += 1
    return -1


def _balanced_delimiters(text: str) -> bool:
    pairs = {"(": ")", "[": "]", "{": "}"}
    stack: list[str] = []
    for char in text:
        if char in pairs:
            stack.append(pairs[char])
        elif char in ")]}":
            if not stack or char != stack[-1]:
                return False
            stack.pop()
    return not stack
