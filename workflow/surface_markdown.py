"""Shared markdown rendering helpers for prover surfaces."""
from __future__ import annotations


def markdown_code_span(text: str) -> str:
    raw = str(text)
    longest = 0
    run = 0
    for ch in raw:
        if ch == "`":
            run += 1
            longest = max(longest, run)
        else:
            run = 0
    ticks = "`" * (longest + 1)
    pad = " " if raw.startswith("`") or raw.endswith("`") else ""
    return f"{ticks}{pad}{raw}{pad}{ticks}"
