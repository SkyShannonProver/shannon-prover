"""Procedure-reference parsing and comparison keys for EasyCrypt analysis."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from core.easycrypt.analysis.ec_utils import (
    matching_delimiter,
    split_top_level_commas,
    strip_outer_parens,
)


@dataclass(frozen=True)
class ProcedureCall:
    """A parsed EasyCrypt procedure call expression."""

    procedure: str
    arguments: tuple[str, ...] = ()
    raw: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "procedure": self.procedure,
            "arguments": list(self.arguments),
            "raw": self.raw,
        }


def parse_call_statement(
    text: str,
    *,
    strip_outer: bool = True,
) -> Optional[ProcedureCall]:
    """Parse the call target after ``<@`` from a statement, if present."""
    source = str(text or "")
    marker = source.find("<@")
    if marker < 0:
        return None
    target = _take_until_top_level_semicolon(source[marker + 2 :].strip())
    if not target:
        return None
    return parse_procedure_application(target, strip_outer=strip_outer)


def extract_visible_call_procedures(text: str) -> list[str]:
    """Return complete procedure identities from visible ``<@`` calls.

    This is the pretty-goal fallback below ProgramIR.  It understands nested
    module applications such as ``Adv(A, D2(O).O).guess()`` and deliberately
    returns only the procedure identity, not value arguments or a tactic.
    ProgramIR remains authoritative when it has structured call sites; this
    helper prevents consumers from inventing separate regex identities when
    EasyCrypt exposes only its numbered pretty-printed program table.
    """
    source = str(text or "")
    procedures: list[str] = []
    seen: set[str] = set()
    offset = 0
    while True:
        marker = source.find("<@", offset)
        if marker < 0:
            break
        procedure = _procedure_after_call_marker(source, marker + 2)
        if procedure:
            key = procedure_exact_key(procedure)
            if key and key not in seen:
                seen.add(key)
                procedures.append(procedure)
        offset = marker + 2
    return procedures


def parse_call_argument_site(text: str) -> Optional[ProcedureCall]:
    """Parse a statement call target as legacy value-argument evidence."""
    source = str(text or "")
    marker = source.find("<@")
    if marker < 0:
        return None
    target = _take_until_top_level_semicolon(source[marker + 2 :].strip())
    if not target:
        return None
    open_idx = _final_argument_open_index(target, allow_leading=True)
    if open_idx < 0:
        return ProcedureCall(target.strip().rstrip("."), (), target)
    procedure = target[:open_idx].strip()
    close_idx = matching_delimiter(target, open_idx, "(", ")")
    if close_idx < 0:
        return ProcedureCall(procedure, (), target)
    arguments = tuple(
        arg for arg in split_top_level_commas(target[open_idx + 1 : close_idx])
        if arg
    )
    return ProcedureCall(procedure, arguments, target)


def parse_procedure_application(
    text: str,
    *,
    strip_outer: bool = True,
) -> ProcedureCall:
    """Parse ``Module.proc(args)`` while keeping module functor args intact."""
    raw = str(text or "").strip()
    source = (strip_outer_parens(raw) if strip_outer else raw).rstrip(".").strip()
    if not source:
        return ProcedureCall("", (), raw)
    open_idx = _final_argument_open_index(source)
    if open_idx < 0:
        return ProcedureCall(source, (), raw)
    close_idx = matching_delimiter(source, open_idx, "(", ")")
    if close_idx != len(source) - 1:
        return ProcedureCall(source, (), raw)
    procedure = source[:open_idx].strip()
    arguments = tuple(
        arg for arg in split_top_level_commas(source[open_idx + 1 : close_idx])
        if arg
    )
    return ProcedureCall(procedure, arguments, raw)


def procedure_exact_key(procedure: str, *, strip_outer: bool = True) -> str:
    """Whitespace-insensitive procedure key that preserves application shape."""
    call = parse_procedure_application(procedure, strip_outer=strip_outer)
    text = call.procedure
    if call.arguments:
        text = f"{text}({','.join(call.arguments)})"
    elif str(procedure or "").strip().endswith("()"):
        text = f"{text}()"
    return re.sub(r"\s+", "", text).rstrip(".")


def procedure_spine_key(procedure: str, *, strip_outer: bool = True) -> str:
    """Comparison key that drops functor/value arguments but keeps module path."""
    call = parse_procedure_application(procedure, strip_outer=strip_outer)
    return _drop_parenthesized_contents(
        call.procedure,
        strip_outer=strip_outer,
    ).rstrip(".")


def procedure_tail_key(
    procedure: str,
    *,
    components: int = 2,
    strip_outer: bool = True,
) -> str:
    """Return the last top-level dot-separated components of a procedure path."""
    parts = _top_level_dot_parts(
        procedure_exact_key(procedure, strip_outer=strip_outer)
    )
    if not parts:
        return ""
    count = max(1, components)
    return ".".join(parts[-count:])


def procedure_application_key(procedure: str, *, strip_outer: bool = True) -> str:
    """Spine tail key used to compare applications across wrapper modules."""
    return procedure_tail_key(
        procedure_spine_key(procedure, strip_outer=strip_outer),
        components=2,
        strip_outer=strip_outer,
    )


def split_procedure_module_and_name(proc_expr: str) -> tuple[str, str]:
    """Split ``M(args).proc`` or ``M(args).proc()`` into module and proc name."""
    source = str(proc_expr or "").strip()
    if source.endswith("()"):
        source = source[:-2].rstrip()
    depth = 0
    last_dot = -1
    for idx, ch in enumerate(source):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        elif ch == "." and depth == 0:
            rest = source[idx + 1 :].lstrip()
            if re.match(r"\w", rest):
                last_dot = idx
    if last_dot < 0:
        return source, ""
    return source[:last_dot], source[last_dot + 1 :].strip()


def procedure_leaf_token(procedure: str) -> str:
    """Return the final token from a dotted/parenthesized procedure shape."""
    tokens = [
        token for token in re.split(r"[.()]+", str(procedure or ""))
        if token
    ]
    return tokens[-1] if tokens else ""


def looks_like_qualified_procedure_application(text: str) -> bool:
    """Return true for a qualified ``Module.proc(...)`` expression."""
    call = parse_procedure_application(text)
    module, name = split_procedure_module_and_name(call.procedure)
    return bool(module and name)


def shallow_call_procedure_from_statement(text: str) -> str:
    """Return the legacy shallow call head after ``<@`` from a statement."""
    match = re.search(
        r"<@\s*([A-Za-z_][A-Za-z0-9_'.]*(?:\.[A-Za-z_][A-Za-z0-9_']*)*)\s*\(",
        str(text or ""),
    )
    return match.group(1) if match else ""


def _procedure_after_call_marker(text: str, start: int) -> str:
    """Parse one qualified procedure path after a visible ``<@`` marker."""
    source = str(text or "")
    idx = start
    while idx < len(source) and source[idx].isspace():
        idx += 1
    parts: list[str] = []
    while idx < len(source):
        match = re.match(r"[A-Za-z_][A-Za-z0-9_']*", source[idx:])
        if match is None:
            return ""
        name = match.group(0)
        idx += len(name)
        while idx < len(source) and source[idx].isspace():
            idx += 1

        application = ""
        if idx < len(source) and source[idx] == "(":
            close_idx = matching_delimiter(source, idx, "(", ")")
            if close_idx < 0:
                return ""
            application = source[idx : close_idx + 1]
            idx = close_idx + 1
            while idx < len(source) and source[idx].isspace():
                idx += 1
            if idx >= len(source) or source[idx] != ".":
                if not parts:
                    return ""
                return _compact_procedure_path(parts + [name])

        parts.append(name + application)
        if idx >= len(source) or source[idx] != ".":
            return ""
        idx += 1
        while idx < len(source) and source[idx].isspace():
            idx += 1
    return ""


def _compact_procedure_path(parts: list[str]) -> str:
    return re.sub(r"\s+", "", ".".join(parts)).strip(".")


def _take_until_top_level_semicolon(text: str) -> str:
    depth = 0
    source = str(text or "")
    for idx, ch in enumerate(source):
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth = max(0, depth - 1)
        elif ch == ";" and depth == 0:
            return source[:idx].strip()
    return source.strip()


def _final_argument_open_index(text: str, *, allow_leading: bool = False) -> int:
    depth = 0
    candidate = -1
    source = str(text or "")
    for idx, ch in enumerate(source):
        if ch == "(":
            if (
                depth == 0
                and (
                    _looks_like_application_open(source, idx)
                    or (allow_leading and idx == 0)
                )
            ):
                candidate = idx
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
    return candidate


def _looks_like_application_open(text: str, open_idx: int) -> bool:
    idx = open_idx - 1
    while idx >= 0 and text[idx].isspace():
        idx -= 1
    return idx >= 0 and bool(re.match(r"[A-Za-z0-9_'.)]", text[idx]))


def _drop_parenthesized_contents(text: str, *, strip_outer: bool = True) -> str:
    out: list[str] = []
    depth = 0
    source = strip_outer_parens(text) if strip_outer else str(text or "").strip()
    for char in source:
        if char == "(":
            depth += 1
        elif char == ")":
            depth = max(0, depth - 1)
        elif depth == 0:
            out.append(char)
    return re.sub(r"\s+", "", "".join(out).strip())


def _top_level_dot_parts(text: str) -> list[str]:
    source = str(text or "").strip()
    if not source:
        return []
    parts: list[str] = []
    depth = 0
    start = 0
    for idx, ch in enumerate(source):
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth = max(0, depth - 1)
        elif ch == "." and depth == 0:
            part = source[start:idx].strip()
            if part:
                parts.append(part)
            start = idx + 1
    tail = source[start:].strip()
    if tail:
        parts.append(tail)
    return parts


__all__ = [
    "ProcedureCall",
    "extract_visible_call_procedures",
    "looks_like_qualified_procedure_application",
    "parse_call_argument_site",
    "parse_call_statement",
    "parse_procedure_application",
    "procedure_application_key",
    "procedure_exact_key",
    "procedure_leaf_token",
    "procedure_spine_key",
    "procedure_tail_key",
    "shallow_call_procedure_from_statement",
    "split_procedure_module_and_name",
]
