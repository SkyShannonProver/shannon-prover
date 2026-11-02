"""EasyCrypt's ``-emacs`` prompt, ``[<uuid>|<mode>]>`` (ecTerminal.ml).

EasyCrypt prints the prompt on a line of its own after the output of every
command, so it marks where one command's reply ends. ``uuid`` numbers the
proof-engine state and ``mode`` is ``check``, ``weakcheck`` or ``report``.
Every reader of EasyCrypt output recognises prompts through this module.
"""
from __future__ import annotations

import re

PROMPT_RE = re.compile(r"\[([0-9]+)\|([A-Za-z]+)\]>")
PROMPT_BYTES_RE = re.compile(PROMPT_RE.pattern.encode("ascii"))
# Lines holding only a prompt. ``\s*$`` may also take the blank lines after
# it; goal identities hash text with these removed, so keep the pattern fixed.
PROMPT_LINE_RE = re.compile(rf"(?m)^{PROMPT_RE.pattern}\s*$")


def is_prompt_line(line: str) -> bool:
    """Whether ``line`` is a prompt and nothing else, ignoring blanks."""
    return PROMPT_RE.fullmatch(line.strip()) is not None


def check_prompt_uid(line: str) -> int | None:
    """The uuid of the first ``check``-mode prompt in ``line``, if any."""
    for match in PROMPT_RE.finditer(line):
        if match.group(2) == "check":
            return int(match.group(1))
    return None


def last_prompt_uid(text: str) -> int | None:
    """The uuid of the last prompt in ``text``, if any."""
    uid = None
    for match in PROMPT_RE.finditer(text):
        uid = int(match.group(1))
    return uid
