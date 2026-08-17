"""Feature-neutral scanning utilities for loaded EasyCrypt declarations."""

from __future__ import annotations

import re


_DECLARATION_START = re.compile(
    r"^\s*(?:(?:local\s+)?lemma|(?:declare\s+)?axiom)\s+([A-Za-z_][\w']*)\b",
    re.MULTILINE,
)
_CLONE_INSTANCE_START = re.compile(
    r"^\s*clone\s+(?:import\s+|include\s+)?"
    r"([A-Za-z_][\w'.]*)\s+as\s+([A-Za-z_][\w']*)\b",
    re.MULTILINE,
)


def declarations(text: str) -> tuple[tuple[str, str], ...]:
    lines = text.splitlines()
    found = []
    index = 0
    while index < len(lines):
        match = _DECLARATION_START.match(lines[index])
        if not match:
            index += 1
            continue
        parts = [lines[index].strip()]
        while not parts[-1].rstrip().endswith(".") and index + 1 < len(lines):
            index += 1
            parts.append(lines[index].strip())
        found.append((match.group(1), " ".join(parts)))
        index += 1
    return tuple(found)


def normalized_declaration(text: str) -> str:
    """Strip verifier display headers while preserving declaration syntax."""

    match = _DECLARATION_START.search(text)
    return text[match.start():].strip() if match is not None else text.strip()


def clone_instances(text: str) -> tuple[tuple[str, str], ...]:
    """Return ordered ``(source_theory, local_alias)`` clone instances."""

    return tuple(
        (match.group(1), match.group(2))
        for match in _CLONE_INSTANCE_START.finditer(text)
    )


def top_level_colon(text: str) -> int:
    depth = 0
    for index, char in enumerate(text):
        if char in "({[":
            depth += 1
        elif char in ")}]":
            depth = max(0, depth - 1)
        elif char == ":" and depth == 0:
            return index
    return -1


def module_parameters(header: str) -> tuple[str, ...]:
    return tuple(name for name, _ in module_parameter_specs(header))


def module_parameter_specs(header: str) -> tuple[tuple[str, str], ...]:
    """Return ordered ``(name, restriction)`` module binders."""

    parameters = []
    index = 0
    while index < len(header):
        if header[index] != "(":
            index += 1
            continue
        end = matching_paren(header, index)
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
        comma = top_level_comma(remaining)
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
        end = matching_paren(text, index)
        if end < 0:
            return ()
        content = text[index + 1:end].strip()
        match = re.fullmatch(r"([A-Za-z_][\w']*)\s*<:\s*(.+)", content)
        if match is None:
            return ()
        parameters.append((match.group(1), match.group(2).strip()))
        index = end + 1
    return tuple(parameters)


def matching_paren(text: str, opening: int) -> int:
    depth = 0
    for index in range(opening, len(text)):
        if text[index] == "(":
            depth += 1
        elif text[index] == ")":
            depth -= 1
            if depth == 0:
                return index
    return -1


def top_level_comma(text: str) -> int:
    depth = 0
    for index, char in enumerate(text):
        if char in "({[":
            depth += 1
        elif char in ")}]":
            depth = max(0, depth - 1)
        elif char == "," and depth == 0:
            return index
    return -1


def split_top_level_implications(text: str) -> tuple[str, ...]:
    parts = []
    start = 0
    depth = 0
    index = 0
    while index < len(text) - 1:
        char = text[index]
        if char in "({[":
            depth += 1
        elif char in ")}]":
            depth = max(0, depth - 1)
        elif text[index:index + 2] == "=>" and depth == 0:
            parts.append(text[start:index].strip())
            start = index + 2
            index += 1
        index += 1
    parts.append(text[start:].strip())
    return tuple(parts)
