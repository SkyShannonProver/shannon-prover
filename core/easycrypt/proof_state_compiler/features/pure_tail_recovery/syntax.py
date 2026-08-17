"""Bounded lexical gate for one selected rewrite commitment."""

from __future__ import annotations

import re


_PLAIN_REWRITE = re.compile(
    r"^\s*rewrite\s+"
    r"([A-Za-z_][A-Za-z0-9_']*(?:\.[A-Za-z_][A-Za-z0-9_']*)*)"
    r"\s*\.\s*$"
)


def selected_plain_rewrite(tactic: str) -> str | None:
    """Return the selected lemma only for one plain left-to-right rewrite."""

    match = _PLAIN_REWRITE.fullmatch(str(tactic or ""))
    return None if match is None else match.group(1)
