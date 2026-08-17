"""Small tactic-string helpers used by the manager control boundary."""
from __future__ import annotations

import re


def strip_easycrypt_comments(text: str) -> str:
    """Remove nested EasyCrypt comments before classifying a submitted tactic."""

    out: list[str] = []
    index = 0
    depth = 0
    while index < len(text):
        if text.startswith("(*", index):
            depth += 1
            index += 2
            continue
        if depth and text.startswith("*)", index):
            depth -= 1
            index += 2
            continue
        if depth == 0:
            out.append(text[index])
        index += 1
    return "".join(out)


def tactic_head(tactic: str) -> str:
    text = str(tactic or "").strip()
    match = re.match(r"([A-Za-z_][A-Za-z0-9_]*)", text)
    return match.group(1).lower() if match else ""


def is_product_budget_seq(tactic: str) -> bool:
    text = str(tactic or "").strip().lower()
    if not re.match(r"seq\s+\d+\s*:", text):
        return False
    if "[<=" in text or "pr[" in text:
        return True
    has_budget_marker = "%r" in text or "order" in text or "q" in text
    has_event_marker = (
        "has " in text
        or " mu " in text
        or " size " in text
        or "bad" in text
        or "\\in" in text
    )
    return has_budget_marker and has_event_marker


def is_broad_inline_tactic(text: str) -> bool:
    """Whether a committed tactic uses EasyCrypt's broad ``inline *`` form."""

    return bool(re.search(r"\binline(?:\{[12]\})?\s+\*", str(text or "")))
