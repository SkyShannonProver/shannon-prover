"""EasyCrypt's -emacs prompt is recognised in one place (ec_prompt)."""
from __future__ import annotations

from core.easycrypt.ec_prompt import (
    PROMPT_BYTES_RE,
    PROMPT_LINE_RE,
    check_prompt_uid,
    is_prompt_line,
    last_prompt_uid,
)


def test_every_easycrypt_mode_is_a_prompt() -> None:
    for mode in ("check", "weakcheck", "report"):
        assert is_prompt_line(f"  [12|{mode}]>  ")
        assert PROMPT_BYTES_RE.search(f"out\n[12|{mode}]>\n".encode())
    assert not is_prompt_line("[12|check]> trailing")
    assert not is_prompt_line("[x|check]>")


def test_only_check_mode_prompts_carry_a_check_uid() -> None:
    assert check_prompt_uid("[7|check]>") == 7
    assert check_prompt_uid("[7|weakcheck]>") is None
    assert check_prompt_uid("[3|report]> [8|check]>") == 8


def test_last_prompt_uid_reads_the_final_prompt() -> None:
    raw = "[3|check]>\nCurrent goal\n------\ntrue\n[4|check]>\n"
    assert last_prompt_uid(raw) == 4
    assert last_prompt_uid("no prompt") is None


def test_prompt_lines_are_removed_with_their_blank_tail() -> None:
    raw = "Current goal\n\n------\ntrue\n[4|check]>\n"
    assert PROMPT_LINE_RE.sub("", raw).rstrip() == "Current goal\n\n------\ntrue"
