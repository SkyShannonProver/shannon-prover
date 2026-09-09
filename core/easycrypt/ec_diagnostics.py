"""Native EasyCrypt rejection diagnostics shared by batch and REPL transports.

This decodes native error envelopes; it does not infer proof state or acceptance
from a goal display. Callers retain process/transaction and rollback ownership.
"""

import re


ERROR_LINE_RE = re.compile(r"\[(error|critical|fatal)(-[0-9\-]+)?\](.*)")
_PROMPT_RE = re.compile(r"\[\d+\|[a-zA-Z]+\]>")


def parse_error(raw: str) -> dict | None:
    """Return the first rejection, including its bounded continuation lines."""
    match = ERROR_LINE_RE.search(raw)
    if match is None:
        return None
    continuation = raw[match.end():]
    boundary = re.search(_PROMPT_RE.pattern + "|" + ERROR_LINE_RE.pattern, continuation)
    if boundary:
        continuation = continuation[:boundary.start()]
    reason = (match.group(3) + continuation).strip()
    low = reason.lower()
    if "cannot unify" in low or "not convertible" in low:
        kind = "unification_fail"
    elif "no progress" in low:
        kind = "no_progress"
    elif any(word in low for word in (
        "unknown lemma", "cannot find lemma", "unknown procedure", "unknown module",
    )):
        kind = "unknown_lemma"
    elif any(word in low for word in ("type error", "unbound", "mismatch")):
        kind = "type_error"
    else:
        kind = "other"
    return {"kind": kind, "raw": reason[:2000], "severity": match.group(1)}


def error_text(raw: str) -> str:
    """Render the same native diagnostic for a string-valued result boundary."""
    error = parse_error(raw)
    return f"[{error['severity']}] {error['raw']}" if error else ""
