"""Bounded lexical gate; EasyCrypt remains the parsing and scope authority."""

from __future__ import annotations

import re


# Optionally under a closing `by`, which runs its body first.
_SMT_HINTS = re.compile(r"^(?:by\s+)?smt\s*\(.*\)\s*\.$")
_REWRITE_IN = re.compile(
    r"^(?:by\s+)?rewrite\s.*\sin\s+[A-Za-z_][A-Za-z0-9_']*\s*\.$"
)


def is_hypothesis_scope_candidate(tactic: str) -> bool:
    """Schedule native diagnosis of ``smt(...)`` or ``rewrite ... in H``.

    The match claims nothing: EasyCrypt parses the tactic, locates the failing
    reference and decides every scope fact.  It only keeps unrelated failures
    from starting native work.
    """

    text = str(tactic or "")
    return bool(
        0 < len(text.encode("utf-8")) <= 4096
        and text == text.strip()
        and not any(
            token in text for token in (";", "\n", "\r", '"', "(*", "*)")
        )
        and (_SMT_HINTS.match(text) or _REWRITE_IN.match(text))
    )
