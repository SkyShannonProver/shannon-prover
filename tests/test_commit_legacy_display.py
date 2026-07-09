"""Tests for mutating-command legacy stdout display modes."""
from __future__ import annotations

import os
import sys
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from core.easycrypt.commands.commit_commands import (  # type: ignore  # noqa: E402
    _legacy_stdout_write,
    _stdout_tool_view,
    _write_legacy_output,
)


class _Env:
    def __init__(self, value: str | None):
        self.value = value
        self.old: str | None = None

    def __enter__(self):
        self.old = os.environ.pop("SHANNON_LEGACY_DISPLAY", None)
        if self.value is not None:
            os.environ["SHANNON_LEGACY_DISPLAY"] = self.value

    def __exit__(self, *_args):
        os.environ.pop("SHANNON_LEGACY_DISPLAY", None)
        if self.old is not None:
            os.environ["SHANNON_LEGACY_DISPLAY"] = self.old


def _capture(fn, *args) -> str:
    buf = StringIO()
    with redirect_stdout(buf):
        fn(*args)
    return buf.getvalue()


def test_legacy_output_hidden_by_default() -> None:
    with _Env(None):
        assert _capture(_write_legacy_output, "Current goal\n----\nx = y\n") == ""
        assert _capture(_legacy_stdout_write, "[chain] 2 tactics\n") == ""


def test_legacy_output_full_opt_in() -> None:
    with _Env("full"):
        out = _capture(_write_legacy_output, "Current goal\n----\nx = y\n")
        direct = _capture(_legacy_stdout_write, "[chain] 2 tactics\n")

    assert "[LEGACY-OUTPUT]" in out
    assert "Current goal" in out
    assert direct == "[chain] 2 tactics\n"


def test_legacy_output_compact_opt_in() -> None:
    text = "noise\nCurrent goal\n----\npost = x = y\n"
    with _Env("compact"):
        out = _capture(_write_legacy_output, text)

    assert "[LEGACY-OUTPUT compact]" in out
    assert "Current goal" in out
    assert "post = x = y" in out


def test_stdout_tool_view_strips_legacy_report() -> None:
    view = {
        "tool": "try",
        "debug": {
            "legacy_report": "[TRY] accepted: False\nraw diagnostic",
            "parsed_result": {"accepted": False},
        },
    }

    out = _stdout_tool_view(view)

    assert "legacy_report" not in out["debug"]
    assert out["debug"]["parsed_result"]["accepted"] is False
    assert view["debug"]["legacy_report"].startswith("[TRY]")


def test_try_stdout_tool_view_surfaces_probe_verdict_first() -> None:
    view = {
        "schema_version": 1,
        "tool": "try",
        "ok": True,
        "proof_state": {"status": "error"},
        "guidance": {"recommendations": []},
        "debug": {
            "legacy_report": "[TRY] accepted: True\nraw diagnostic",
            "parsed_result": {
                "tactic": "byequiv => //.",
                "accepted": True,
                "goal_after_closed": False,
                "goal_after_remaining": 1,
                "error_kind": "",
                "no_progress_predicted": False,
            },
        },
    }

    out = _stdout_tool_view(view)

    assert list(out)[:4] == ["schema_version", "tool", "ok", "probe_result"]
    assert out["probe_result"]["status"] == "probe_accepted"
    assert out["probe_result"]["tactic"] == "byequiv => //."
    assert out["next"]["primary_action"] == "commit_probe_result"
    assert "legacy_report" not in out["debug"]


def main() -> int:
    tests = [
        test_legacy_output_hidden_by_default,
        test_legacy_output_full_opt_in,
        test_legacy_output_compact_opt_in,
        test_stdout_tool_view_strips_legacy_report,
        test_try_stdout_tool_view_surfaces_probe_verdict_first,
    ]
    for test in tests:
        test()
    print("PASS test_commit_legacy_display")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
