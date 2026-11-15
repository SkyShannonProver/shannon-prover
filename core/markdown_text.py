"""Markdown spelling for text the agent reads."""

from __future__ import annotations

import re


def inline_code(text: str) -> str:
    """Markdown inline code that survives backticks in EasyCrypt text.

    EasyCrypt writes projections and absolute values with backticks
    (``p.`1``, ``|x|`` in some notations); a single-backtick span closed at the
    first of them. CommonMark allows a longer fence, padded when the text
    starts or ends with a backtick.
    """

    value = str(text)
    longest = max((len(run) for run in re.findall(r"`+", value)), default=0)
    fence = "`" * (longest + 1)
    if value.startswith("`") or value.endswith("`"):
        value = f" {value} "
    return f"{fence}{value}{fence}"
