"""Shared lexical guards for candidate proof text, not proof acceptance."""

import re


ADMIT_TOKEN_RE = re.compile(r"(?<!\w)admit\.", re.IGNORECASE)


def strip_comments(text: str) -> str:
    """Remove nested comments for the candidate-admit guard."""
    out: list[str] = []
    depth = 0
    i = 0
    while i < len(text):
        if text[i:i + 2] == "(*":
            depth += 1
            i += 2
            continue
        if depth > 0 and text[i:i + 2] == "*)":
            depth -= 1
            i += 2
            continue
        if depth == 0:
            out.append(text[i])
        i += 1
    return "".join(out)


def tactics_contain_admit(tactics: list[str]) -> bool:
    """Preserve the finalizer's admit guard for all candidate consumers."""
    for tactic in tactics:
        scrubbed = strip_comments(tactic)
        if scrubbed.strip().lower().rstrip(".").strip() == "admit":
            return True
        if ADMIT_TOKEN_RE.search(scrubbed):
            return True
    return False
