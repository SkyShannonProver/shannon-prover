"""Pure-Python tests for session diagnostics and display ordering."""
from __future__ import annotations

import sys
from pathlib import Path


import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from core.easycrypt.session_diagnostics import explain_no_progress  # type: ignore  # noqa: E402
from core.easycrypt.session_display import reorder_display  # type: ignore  # noqa: E402
from core.easycrypt import session_diagnostics as package_diagnostics  # noqa: E402
from core.easycrypt import session_display as package_display  # noqa: E402


def test_package_import_boundaries() -> None:
    assert package_diagnostics.explain_no_progress("move=> x.", "") == ""
    assert package_display.reorder_display(["plain"]) == ["plain"]


def test_inline_no_progress_names_visible_refs() -> None:
    hint = explain_no_progress(
        "inline Missing.proc.",
        "Current goal\nVisible.proc(x)\n[1|check]>\n",
    )
    assert "Missing.proc" in hint
    assert "Visible.proc" in hint


def test_rewrite_no_progress_hint() -> None:
    hint = explain_no_progress("rewrite Foo.", "Current goal\nx = y\n")
    assert "rewrite Foo" in hint
    assert "-sig Foo" in hint


def test_reorder_display_groups_layers() -> None:
    out = reorder_display([
        "[goal: pRHL]\n",
        "[AUTO-LEMMA-HINTS] hint\n",
        "[DAEMON_REJECTED] bad\n",
        "plain\n",
    ])
    joined = "".join(out)
    assert joined.index("L0 - action result") < joined.index("L1 - current")
    assert joined.index("L1 - current") < joined.index("L4 - strategy")
    assert joined.endswith("plain\n")


if __name__ == "__main__":
    test_package_import_boundaries()
    test_inline_no_progress_names_visible_refs()
    test_rewrite_no_progress_hint()
    test_reorder_display_groups_layers()
    print("PASS test_session_diagnostics")
