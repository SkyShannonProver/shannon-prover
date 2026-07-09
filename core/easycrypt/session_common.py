"""Small shared helpers for EasyCrypt session tooling.

This module is intentionally independent of ``Session``.  It holds utility
logic used by the CLI, command handlers, and hooks without making those
modules import ``session_cli.py`` as a public library.
"""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path


try:
    from core.easycrypt.analysis.ec_error_classifier import classify as _classify_ec_error
    from core.easycrypt.analysis.ec_error_classifier import (
        format_classification as _format_ec_classification,
    )
except Exception:
    _classify_ec_error = None
    _format_ec_classification = None


def classify_and_format(
    raw_error: str,
    tactic_text: str = "",
    file_path: str | None = None,
) -> str:
    """Try to classify raw EC error text; return formatted block or ''."""
    if not raw_error or _classify_ec_error is None:
        return ""
    try:
        cls = _classify_ec_error(raw_error)
        if cls and _format_ec_classification:
            try:
                return _format_ec_classification(
                    cls,
                    tactic_text=tactic_text,
                    file_path=file_path,
                    raw_error=raw_error,
                )
            except TypeError:
                pass
            try:
                return _format_ec_classification(cls, tactic_text=tactic_text)
            except TypeError:
                return _format_ec_classification(cls)
    except Exception:
        return ""
    return ""


def get_ec_env() -> dict:
    """Return the environment with EasyCrypt's opam switch on PATH.

    Delegates to ``ec_env.get_ec_env`` — the single source of the opam-switch
    environment (its module docstring owns the switch-name policy)."""
    from core.easycrypt.ec_env import get_ec_env as _get_ec_env
    return _get_ec_env()


def list_lemmas_in_file(file_path: Path) -> dict:
    """Scan a .ec file for lemma/equiv/hoare names by section scope."""
    try:
        text = file_path.read_text(encoding="utf-8")
    except Exception:
        return {"top_level": [], "in_sections": []}

    lines = text.split("\n")
    lemma_pat = re.compile(r"^\s*(local\s+)?(lemma|equiv|hoare|phoare)\s+([\w']+)")

    section_ranges: list[tuple[int, int]] = []
    stack: list[int] = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if re.match(r"^section\b", stripped):
            stack.append(i)
        elif re.match(r"^end\s+section\b", stripped):
            if stack:
                section_ranges.append((stack.pop(), i))

    def in_section(line_num: int) -> bool:
        return any(s < line_num < e for s, e in section_ranges)

    top_level: list[str] = []
    in_sections: list[str] = []
    for i, line in enumerate(lines):
        m = lemma_pat.match(line)
        if m:
            name = m.group(3)
            (in_sections if in_section(i) else top_level).append(name)

    return {"top_level": top_level, "in_sections": in_sections}


def trim_after_last_prompt(text: str) -> str:
    """Keep content up to and including the last ``[N|...]>`` prompt line."""
    lines = text.splitlines(keepends=True)
    last_idx = -1
    for i, ln in enumerate(lines):
        if re.match(r"^\[[0-9]+\|[^\]]+\]>\s*$", ln.strip()):
            last_idx = i
    if last_idx != -1:
        return "".join(lines[: last_idx + 1])
    return text


STRUCTURAL_TACTIC_RE = re.compile(
    r"^\s*(?:(?:sim|ecall|call|byequiv|byphoare|bypr|proc|inline|while|seq|"
    r"conseq|if|splitwhile|transitivity|apply|rewrite)\b|auto\s*=>)",
    re.IGNORECASE,
)


def is_structural_tactic(tactic_text: str) -> bool:
    """Return True if a tactic commits to a proof/program shape."""
    if not tactic_text:
        return False
    for part in re.split(r"[.;]\s*", tactic_text):
        if STRUCTURAL_TACTIC_RE.match(part.strip()):
            return True
    return False


def render_closer_hints(lem: dict) -> list[str]:
    """Render narrative last-mile closer hints when present."""
    ch = lem.get("closer_hints") or {}
    if not ch:
        return []
    lines = []
    smt_lems = ch.get("smt_lemmas") or []
    unfold = ch.get("unfold_ops") or []
    tail = (ch.get("typical_tail") or "").strip()
    if smt_lems:
        lines.append(f"     Closer smt hints: smt({' '.join(smt_lems)})")
    if unfold:
        lines.append(
            f"     Unfold first: "
            f"{' '.join('rewrite /' + op + '.' for op in unfold)}"
        )
    if tail:
        lines.append(f"     Typical tail: `{tail}`")
    return lines
