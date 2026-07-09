"""Small tactic-string classifiers shared by proof-management surfaces."""
from __future__ import annotations

import re


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
