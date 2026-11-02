"""Small shared helper for EasyCrypt session tooling.

Kept free of ``Session`` so both the runtime and the display helpers can
import it.
"""
from __future__ import annotations

from core.easycrypt.ec_prompt import is_prompt_line


def trim_after_last_prompt(text: str) -> str:
    """Keep content up to and including the last ``[N|...]>`` prompt line."""
    lines = text.splitlines(keepends=True)
    last_idx = -1
    for i, ln in enumerate(lines):
        if is_prompt_line(ln):
            last_idx = i
    if last_idx != -1:
        return "".join(lines[: last_idx + 1])
    return text

