"""Pure-Python tests for shared session helpers."""
from __future__ import annotations


from core.easycrypt.session.session_common import (  # type: ignore  # noqa: E402
    trim_after_last_prompt,
)


def test_trim_after_last_prompt() -> None:
    text = "intro\n[1|check]>\nnoise after prompt\n"
    assert trim_after_last_prompt(text) == "intro\n[1|check]>\n"
    assert trim_after_last_prompt("no prompt\n") == "no prompt\n"
