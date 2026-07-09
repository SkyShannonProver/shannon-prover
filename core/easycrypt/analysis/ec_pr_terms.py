"""Textual scan of EasyCrypt probability-goal terms (``Pr[...]`` forms).

Moved verbatim (public names) from workflow/surface_composer.py — a
presentation module had grown its own Pr-goal text parser; this is
analysis-shaped code and lives with the other goal-text scanners.
``split_top_level`` here tracks each bracket family independently; the
single-depth variant in workflow analyzers' pure_tail is behaviorally
different on unbalanced input and deliberately NOT unified.
"""
from __future__ import annotations

import re


def top_level_relation(text: str) -> tuple[str, str, str] | None:
    s = str(text or "")
    depth_paren = depth_bracket = depth_brace = 0
    i = 0
    while i < len(s):
        ch = s[i]
        if ch == "(":
            depth_paren += 1
        elif ch == ")" and depth_paren:
            depth_paren -= 1
        elif ch == "[":
            depth_bracket += 1
        elif ch == "]" and depth_bracket:
            depth_bracket -= 1
        elif ch == "{":
            depth_brace += 1
        elif ch == "}" and depth_brace:
            depth_brace -= 1
        elif depth_paren == depth_bracket == depth_brace == 0:
            if s.startswith("<=", i):
                return s[:i], "<=", s[i + 2:]
            if ch == "<" and not s.startswith("<:", i):
                return s[:i], "<", s[i + 1:]
            if ch == "=" and not s.startswith("=>", i):
                return s[:i], "=", s[i + 1:]
        i += 1
    return None


def extract_pr_terms(text: str) -> list[dict[str, str]]:
    s = str(text or "")
    terms: list[dict[str, str]] = []
    for match in re.finditer(r"\bPr\s*\[", s):
        bracket = s.find("[", match.start())
        end = matching_bracket_from(s, bracket)
        if end is None:
            continue
        inner = s[bracket + 1:end]
        parsed = parse_pr_inner(inner)
        if parsed:
            terms.append(parsed)
    return terms


def matching_bracket_from(text: str, start: int) -> int | None:
    if start < 0 or start >= len(text) or text[start] != "[":
        return None
    depth = 0
    for idx in range(start, len(text)):
        ch = text[idx]
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                return idx
    return None


def parse_pr_inner(inner: str) -> dict[str, str] | None:
    split_at = top_level_colon(inner)
    if split_at is None:
        return None
    program_memory = " ".join(inner[:split_at].split())
    event = " ".join(inner[split_at + 1:].split())
    if not program_memory or not event:
        return None
    return {"program_memory": program_memory, "event": event}


def top_level_colon(text: str) -> int | None:
    depth_paren = depth_bracket = depth_brace = 0
    for idx, ch in enumerate(str(text or "")):
        if ch == "(":
            depth_paren += 1
        elif ch == ")" and depth_paren:
            depth_paren -= 1
        elif ch == "[":
            depth_bracket += 1
        elif ch == "]" and depth_bracket:
            depth_bracket -= 1
        elif ch == "{":
            depth_brace += 1
        elif ch == "}" and depth_brace:
            depth_brace -= 1
        elif ch == ":" and depth_paren == depth_bracket == depth_brace == 0:
            return idx
    return None


def split_top_level(text: str, sep: str) -> list[str]:
    s = str(text or "")
    if not sep:
        return [s]
    out: list[str] = []
    depth_paren = depth_bracket = depth_brace = 0
    start = 0
    i = 0
    while i < len(s):
        ch = s[i]
        if ch == "(":
            depth_paren += 1
        elif ch == ")" and depth_paren:
            depth_paren -= 1
        elif ch == "[":
            depth_bracket += 1
        elif ch == "]" and depth_bracket:
            depth_bracket -= 1
        elif ch == "{":
            depth_brace += 1
        elif ch == "}" and depth_brace:
            depth_brace -= 1
        elif depth_paren == depth_bracket == depth_brace == 0 and s.startswith(sep, i):
            out.append(s[start:i].strip())
            i += len(sep)
            start = i
            continue
        i += 1
    out.append(s[start:].strip())
    return [part for part in out if part]
