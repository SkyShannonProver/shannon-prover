"""Bounded lexical sketch for a selected structured destruct attempt."""

from __future__ import annotations

import re


_INTRO_OPERATION = re.compile(r"^\s*move\b", re.IGNORECASE)


def is_nested_intro_pattern_candidate(tactic: str) -> bool:
    """Bound native work without claiming that the pattern is meaningful."""

    text = str(tactic or "")
    return bool(
        0 < len(text) <= 16_384
        and text == text.strip()
        and text.endswith(".")
        and _INTRO_OPERATION.match(text)
        and "=>" in text
        and text.count("[") >= 2
        and text.count("[") == text.count("]")
        and "#" not in text
        and "|" not in text
        and ";" not in text
        and "\n" not in text
        and "\r" not in text
        and '"' not in text
        and "(*" not in text
        and "*)" not in text
    )
