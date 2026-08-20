"""Shared detection for prover-facing template placeholders."""
from __future__ import annotations

import re


_PLACEHOLDER_INSTANTIATION_RE = re.compile(
    r"<(?!:)[^>]+>|\bLEMMA\b|\boracle_name\b|\.\.\.|call\s*\(_:\s*Inv\s*\)"
)


def requires_placeholder_instantiation(action: str) -> bool:
    """Return whether a tactic/action still contains an agent-fillable placeholder."""
    return bool(_PLACEHOLDER_INSTANTIATION_RE.search(action))


__all__ = ["requires_placeholder_instantiation"]
