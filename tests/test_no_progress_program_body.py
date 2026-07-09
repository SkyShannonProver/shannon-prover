"""Regression: the no-progress structural fingerprint must include the PROGRAM BODY.

Root-caused by EC replay (MEE-CBC `mee_decrypt_correct`, 2026-06-06): `inline` of an
in-loop call genuinely expanded the loop body (the call vanished; body renumbered
`(7.5)`->`(7.7)`), but for a phoare procedure-body goal `gi.left_stmts` is empty, so the
fingerprint `(goal_type, pre, post, left_stmts, right_stmts, event, hyp_names)` matched
and the effective inline was auto-reverted as "no progress" — blocking the whole
inline->loop proof path. Fix: add normalized `(N…)` program-statement lines to the
fingerprint.
"""
from __future__ import annotations

import sys
from pathlib import Path

import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from core.easycrypt.session_no_progress import detect_no_progress  # noqa: E402


def _phoare_goal(prog_lines: str, extra_hyp: str = "") -> str:
    hyp = f"{extra_hyp}\n" if extra_hyp else ""
    return (
        "Current goal\n\n"
        "Type variables: <none>\n\n"
        "_mk: mK\n_ek: block\n" + hyp +
        "------------------------------------------------------------------------\n"
        "Context : hr: {i : int, ek, ci, pi : block}\n"
        "Bound   : [=] 1%r\n\n"
        "pre = (key, c).`1 = (_ek, _mk)\n\n"
        + prog_lines + "\n\n"
        "post = p = mee_dec AESi _ek _mk\n"
    )


def test_inline_that_expands_program_body_is_not_no_progress() -> None:
    before = _phoare_goal("(7.2)    pi <@ PRPc.PseudoRP.fi(ek, ci)\n(7.5)    i <- i + 1")
    after = _phoare_goal("(7.4)    pi <- AESi ek ci\n(7.7)    i <- i + 1")
    is_np, reason = detect_no_progress(before, after, has_new_error=False)
    assert is_np is False, f"effective inline mislabeled no-progress ({reason!r})"


def test_true_noop_same_program_body_is_no_progress() -> None:
    g = _phoare_goal("(7.2)    pi <@ PRPc.PseudoRP.fi(ek, ci)\n(7.5)    i <- i + 1")
    is_np, _ = detect_no_progress(g, g, has_new_error=False)
    assert is_np is True


def test_cosmetic_whitespace_in_program_body_stays_no_progress() -> None:
    # The program lines are whitespace-normalized, so a pure-whitespace diff must NOT
    # count as progress.
    a = _phoare_goal("(7.2)    pi <@ PRPc.PseudoRP.fi(ek, ci)")
    b = _phoare_goal("(7.2)  pi <@   PRPc.PseudoRP.fi(ek, ci)")
    is_np, _ = detect_no_progress(a, b, has_new_error=False)
    assert is_np is True


def test_have_adds_hypothesis_is_still_progress() -> None:
    # Original fingerprint feature must keep working: a `have` adds a hypothesis
    # (program body unchanged) -> progress via hyp_names.
    before = _phoare_goal("(7.2)    pi <@ PRPc.PseudoRP.fi(ek, ci)")
    after = _phoare_goal("(7.2)    pi <@ PRPc.PseudoRP.fi(ek, ci)",
                         extra_hyp="ll_fi: islossless PRPc.PseudoRP.fi")
    is_np, _ = detect_no_progress(before, after, has_new_error=False)
    assert is_np is False
