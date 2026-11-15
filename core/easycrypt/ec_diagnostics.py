"""Native EasyCrypt rejection diagnostics shared by batch and REPL transports.

This decodes native error envelopes; it does not infer proof state or acceptance
from a goal display. Callers retain process/transaction and rollback ownership.
"""

import re
from dataclasses import dataclass

from core.easycrypt.ec_prompt import PROMPT_RE


# EasyCrypt starts an error report at the beginning of a line. Output a
# tactic prints, such as ``idtac "[error] x"`` (shown as ``[W]+ [error] x``),
# is not a rejection.
ERROR_LINE_RE = re.compile(
    r"^\[(error|critical|fatal)(-[0-9\-]+)?\](.*)", re.MULTILINE
)


def parse_error(raw: str) -> dict | None:
    """Return the first rejection, including its bounded continuation lines."""
    match = ERROR_LINE_RE.search(raw)
    if match is None:
        return None
    continuation = raw[match.end():]
    boundary = re.search(
        PROMPT_RE.pattern + "|" + ERROR_LINE_RE.pattern,
        continuation,
        re.MULTILINE,
    )
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


@dataclass(frozen=True)
class FailedSentence:
    """The sentence of a multi-sentence transaction that EasyCrypt rejected.

    The REPL runs a transaction one sentence at a time and stops at the
    first rejection, so ``index`` (from 1) also says that sentences
    ``1 .. index - 1`` ran before it.  A one-sentence transaction has none.
    """

    index: int
    count: int
    sentence: str

    def __post_init__(self) -> None:
        if (
            type(self.index) is not int
            or type(self.count) is not int
            or not 1 <= self.index <= self.count
            or self.count < 2
            or type(self.sentence) is not str
            or not self.sentence.strip()
        ):
            raise ValueError("failed sentence is invalid")

    def to_payload(self) -> dict:
        return {
            "index": self.index,
            "count": self.count,
            "sentence": self.sentence,
        }

    @classmethod
    def from_payload(cls, value: object) -> "FailedSentence | None":
        """Read a payload; anything but one complete record is ``None``."""

        if not isinstance(value, dict) or set(value) != {
            "index", "count", "sentence",
        }:
            return None
        try:
            return cls(
                index=value["index"],
                count=value["count"],
                sentence=value["sentence"],
            )
        except ValueError:
            return None
