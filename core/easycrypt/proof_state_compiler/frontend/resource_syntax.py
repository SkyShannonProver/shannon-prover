"""Feature-neutral scanning utilities for loaded EasyCrypt declarations."""

from __future__ import annotations

import re

from core.easycrypt.proof_state_compiler.delimiters import (
    PARENTHESES,
    find_top_level,
    matching_close,
)
from core.easycrypt.proof_text import easycrypt_code, sentence_ends


_DECLARATION_START = re.compile(
    r"^\s*(?:(?:local\s+)?lemma|(?:declare\s+)?axiom)\s+([A-Za-z_][\w']*)\b",
    re.MULTILINE,
)


def declarations(text: str) -> tuple[tuple[str, str], ...]:
    """Return ``(name, declaration)`` for each lemma or axiom of ``text``.

    A declaration runs from its keyword to the line whose last code character
    is a sentence-final dot. Comments and strings are read as EasyCrypt reads
    them (``proof_text``), so a declaration inside a comment is not one, and a
    comment inside a declaration stays in its text.
    """

    code = easycrypt_code(text)
    final_dots = set(sentence_ends(text, code))
    lines = []
    offset = 0
    for line in text.splitlines(keepends=True):
        lines.append((offset, line, code[offset:offset + len(line)]))
        offset += len(line)
    found = []
    index = 0
    while index < len(lines):
        match = _DECLARATION_START.match(lines[index][2])
        if not match:
            index += 1
            continue
        parts = []
        while True:
            start, line, line_code = lines[index]
            end = len(line_code.rstrip())
            if start + end in final_dots:
                # A comment after the final period is not declaration text,
                # and the next line already starts another sentence.
                parts.append(line[:end].strip())
                break
            parts.append(line.strip())
            if index + 1 >= len(lines):
                break
            index += 1
        found.append((match.group(1), " ".join(parts)))
        index += 1
    return tuple(found)


def normalized_declaration(text: str) -> str:
    """Strip verifier display headers while preserving declaration syntax."""

    match = _DECLARATION_START.search(text)
    return text[match.start():].strip() if match is not None else text.strip()


def module_parameter_specs(header: str) -> tuple[tuple[str, str], ...]:
    """Return ordered ``(name, restriction)`` module binders."""

    parameters = []
    index = 0
    while index < len(header):
        if header[index] != "(":
            index += 1
            continue
        end = matching_close(header, index, openers=PARENTHESES)
        if end < 0:
            break
        content = header[index + 1:end].strip()
        match = re.match(r"^([A-Za-z_][\w']*)\s*<:\s*(.+)$", content)
        if match:
            parameters.append((match.group(1), match.group(2).strip()))
        index = end + 1
    return tuple(parameters)


def consume_leading_forall_module_parameters(
    proposition: str,
) -> tuple[tuple[tuple[str, str], ...], str] | None:
    """Consume verifier-normalized leading module quantifiers.

    EasyCrypt may print a source declaration whose module parameters occur in
    the declaration header as ``forall`` binders after the colon.  This helper
    accepts only parenthesized module binders and returns ``None`` for every
    other quantified shape so callers cannot silently drop term binders.
    """

    remaining = proposition.strip()
    parameters: list[tuple[str, str]] = []
    while remaining.startswith("forall "):
        comma = find_top_level(remaining, ",")
        if comma < 0:
            return None
        binder_clause = remaining[len("forall "):comma].strip()
        clause_parameters = exact_module_parameter_specs(binder_clause)
        if not clause_parameters:
            return None
        parameters.extend(clause_parameters)
        remaining = remaining[comma + 1:].strip()
    return tuple(parameters), remaining


def exact_module_parameter_specs(text: str) -> tuple[tuple[str, str], ...]:
    """Parse a sequence consisting only of parenthesized module binders."""

    parameters = []
    index = 0
    while index < len(text):
        while index < len(text) and text[index].isspace():
            index += 1
        if index >= len(text):
            break
        if text[index] != "(":
            return ()
        end = matching_close(text, index, openers=PARENTHESES)
        if end < 0:
            return ()
        content = text[index + 1:end].strip()
        match = re.fullmatch(r"([A-Za-z_][\w']*)\s*<:\s*(.+)", content)
        if match is None:
            return ()
        parameters.append((match.group(1), match.group(2).strip()))
        index = end + 1
    return tuple(parameters)
