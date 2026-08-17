"""Work-avoidance syntax gate; EasyCrypt retains semantic authority."""

from __future__ import annotations


def relation_bridge_intent_family(tactic: str) -> str | None:
    value = str(tactic or "").strip()
    if (
        not value.endswith(".")
        or any(token in value for token in (";", "\n", "\r", "(*", "*)", '"'))
    ):
        return None
    for family in ("transitivity", "change"):
        prefix = family + " "
        if value.startswith(prefix) and value[len(prefix):-1].strip():
            return family
    return None
