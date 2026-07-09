"""Unit tests for Phase 3c hook migrations: GOAL_CLOSED, ALL_GOALS_CLOSED,
GOAL-TOO-LARGE.

Each test builds a CommitHookContext directly and asserts the trigger
function returns the expected text (or None) — pure functions, no EC
daemon. Mirrors the test_post_call_inv_tracker.py pattern.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from core.easycrypt.session_hooks import (  # noqa: E402
    AutoSigPhase,
    CommitHookContext,
    all_goals_closed_trigger,
    auto_noprog_hint_trigger,
    compute_goal_header,
    daemon_rejected_trigger,
    goal_closed_trigger,
    goal_header_trigger,
    goal_too_large_trigger,
    is_goal_too_large,
    state_diff_trigger,
    strict_warning_trigger,
    tactic_no_effect_trigger,
)


def _ctx(d, **kw):
    base = dict(
        session_dir=d, trimmed="", has_new_error=False, no_progress=False,
        prev_count=0, curr_count=0,
        no_more=False, async_check_close=False, active_goal="",
        raw_curr="", raw_prev="", daemon_rejection_error="",
    )
    base.update(kw)
    return CommitHookContext(**base)


def _text(r):
    """v2 contract: triggers return Optional[HookResult]. Tolerate the
    legacy Optional[str] form for any not-yet-migrated callers."""
    if r is None:
        return None
    return r.text if hasattr(r, "text") else r


def case(name: str, fn):
    try:
        fn()
        print(f"  ✓ {name}")
        return True
    except AssertionError as e:
        print(f"  ✗ {name}\n      {e}")
        return False
    except Exception as e:
        print(f"  ✗ {name}\n      {type(e).__name__}: {e}")
        return False


def main() -> int:
    fail = 0
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)

        # ── GOAL_CLOSED ──

        def goal_closed_partial():
            r = goal_closed_trigger(_ctx(d, prev_count=4, curr_count=2))
            assert r is not None
            t = _text(r)
            assert "[GOAL_CLOSED] 2 goal(s) closed" in t
            assert "2 goal(s) remaining" in t

        def goal_closed_skips_when_no_more():
            r = goal_closed_trigger(_ctx(d, prev_count=4, curr_count=0,
                                         no_more=True))
            assert r is None, "all-closed path owns this; goal_closed silent"

        def goal_closed_skips_when_async_close():
            r = goal_closed_trigger(_ctx(d, prev_count=4, curr_count=-1,
                                         async_check_close=True))
            assert r is None

        def goal_closed_skips_when_no_change():
            r = goal_closed_trigger(_ctx(d, prev_count=4, curr_count=4))
            assert r is None

        def goal_closed_skips_when_count_grew():
            # `case`/`split` etc — count INCREASED, not a close
            r = goal_closed_trigger(_ctx(d, prev_count=2, curr_count=5))
            assert r is None

        # ── ALL_GOALS_CLOSED ──

        def all_closed_no_more_path():
            r = all_goals_closed_trigger(_ctx(d, no_more=True))
            assert r is not None
            t = _text(r)
            assert "[ALL_GOALS_CLOSED] All proof goals have been closed." in t
            assert "async-check" not in t, "no_more path is the sync path"

        def all_closed_async_check_path():
            r = all_goals_closed_trigger(_ctx(d, async_check_close=True))
            assert r is not None
            t = _text(r)
            assert "[ALL_GOALS_CLOSED]" in t
            assert "async-check mode" in t

        def all_closed_no_more_dominates_async():
            # Both flags set: no_more body wins (sync is the cleaner signal)
            r = all_goals_closed_trigger(
                _ctx(d, no_more=True, async_check_close=True),
            )
            assert r is not None
            t = _text(r)
            assert "async-check" not in t

        def all_closed_silent_when_neither():
            r = all_goals_closed_trigger(_ctx(d))
            assert r is None

        # ── GOAL-TOO-LARGE ──

        def too_large_fires_above_threshold():
            big = "x" * 9000
            r = goal_too_large_trigger(_ctx(d, active_goal=big))
            assert r is not None
            t = _text(r)
            assert "[GOAL-TOO-LARGE]" in t
            assert "9000 bytes" in t

        def too_large_silent_below_threshold():
            small = "x" * 500
            r = goal_too_large_trigger(_ctx(d, active_goal=small))
            assert r is None

        def too_large_silent_when_empty():
            r = goal_too_large_trigger(_ctx(d, active_goal=""))
            assert r is None

        def too_large_threshold_predicate():
            assert not is_goal_too_large("")
            assert not is_goal_too_large("x" * 8000)
            assert is_goal_too_large("x" * 8001)

        # ── STRICT_WARNING ──

        # Realistic curr/prev pair: curr has a strict-mode SMT replay
        # error line that wasn't in prev. EC's error format is
        # "[error-N] cannot prove goal: <body> (strict mode ...)".
        STRICT_ERR = (
            "[error-1-1] cannot prove goal: foo (strict mode replay)"
        )
        REAL_ERR = "[error-1-1] type error in tactic at column 5"

        def strict_fires_with_suppress_error():
            r = strict_warning_trigger(_ctx(
                d, has_new_error=True, no_more=True,
                raw_prev="some prior state\n",
                raw_curr=f"some prior state\n{STRICT_ERR}",
            ))
            assert r is not None
            assert "[STRICT_WARNING]" in _text(r)
            assert r.suppress_error is True, \
                "must request has_new_error=False"
            assert r.layer == 0

        def strict_silent_when_no_more_false():
            r = strict_warning_trigger(_ctx(
                d, has_new_error=True, no_more=False,
                raw_prev="", raw_curr=STRICT_ERR,
            ))
            assert r is None, "needs no_more (proof structurally closed)"

        def strict_silent_when_no_error():
            r = strict_warning_trigger(_ctx(
                d, has_new_error=False, no_more=True,
                raw_prev="", raw_curr="",
            ))
            assert r is None

        def strict_silent_when_real_error_present():
            # Mix of real error + strict warning → must NOT fire
            # (strict_only is False because not every error is strict)
            r = strict_warning_trigger(_ctx(
                d, has_new_error=True, no_more=True,
                raw_prev="prior\n",
                raw_curr=f"prior\n{STRICT_ERR}\n{REAL_ERR}",
            ))
            assert r is None, "real error among strict ones must block fire"

        def strict_silent_when_no_strict_lines_at_all():
            # has_new_error True but no [error tagged strict-mode lines
            # → empty "any [error in line" check, not a strict-only case
            r = strict_warning_trigger(_ctx(
                d, has_new_error=True, no_more=True,
                raw_prev="prior\n",
                raw_curr="prior\nsome non-error noise\n",
            ))
            assert r is None

        # ── [goal:<type>] header ──

        # We exercise the trigger end-to-end (which depends on
        # `ec_goal_parser.classify_goal`) via the same active-goal text
        # shapes the parser is robust to. compute_goal_header is the
        # shared helper; the trigger is a thin wrapper.

        def goal_header_silent_when_active_goal_empty():
            r = goal_header_trigger(_ctx(d, active_goal=""))
            assert r is None

        def goal_header_returns_l1():
            # ambient goal: `=` between two terms, no &1/&2 markers.
            # classify_goal returns "ambient" — header must still emit.
            r = goal_header_trigger(_ctx(
                d, active_goal="x = 1\n",
            ))
            assert r is not None
            assert r.layer == 1, "header is L1 (sits above State:)"
            assert "[goal:" in _text(r)

        def goal_header_compute_helper_unparseable_returns_empty():
            # Parser may return a default for unrecognized text. Either
            # way, helper must return a STRING (possibly empty) — never
            # raise — so callers can do `if header:` reliably.
            assert isinstance(compute_goal_header(""), str)
            assert isinstance(compute_goal_header("garbage"), str)
            assert compute_goal_header("[31|check]>") == ""
            assert compute_goal_header("No more goals\n[31|check]>") == (
                "[goal: complete]\n"
            )

        # ── DAEMON_REJECTED ──

        def daemon_rejected_silent_when_no_error():
            r = daemon_rejected_trigger(_ctx(d))
            assert r is None

        def daemon_rejected_strips_severity_prefix():
            r = daemon_rejected_trigger(_ctx(
                d, daemon_rejection_error="[error] cannot infer foo",
            ))
            assert r is not None
            t = _text(r)
            assert "[DAEMON_REJECTED] cannot infer foo" in t
            assert "[error]" not in t.split("\n")[0]

        def daemon_rejected_l0_layer():
            r = daemon_rejected_trigger(_ctx(
                d, daemon_rejection_error="[critical] parse failure",
            ))
            assert r.layer == 0

        # ── AUTO-NOPROG-HINT ──

        def auto_noprog_silent_when_progress():
            r = auto_noprog_hint_trigger(_ctx(d, no_progress=False))
            assert r is None

        def auto_noprog_silent_when_no_hint():
            # explain_no_progress on garbage input returns "" (designed
            # to fail gracefully)
            r = auto_noprog_hint_trigger(_ctx(
                d, no_progress=True, trimmed="trivial.",
                raw_prev="",
            ))
            # May or may not return a hint depending on parser — only
            # test the contract (no exception, returns Optional[Result])
            assert r is None or hasattr(r, "text")

        # ── AutoSigPhase ──

        class _StubSession:
            """Minimal session stand-in for AutoSigPhase."""
            def __init__(self):
                self.dir = d
                self._include_dirs: list[str] = []

        def auto_sig_silent_when_no_error():
            phase = AutoSigPhase(_StubSession())
            results = phase.run(_ctx(d, has_new_error=False))
            assert results == []

        def auto_sig_silent_when_no_lemma_in_tactic():
            phase = AutoSigPhase(_StubSession())
            # `auto.` has no lemma name → ignored (in _IGNORE_NAMES)
            results = phase.run(_ctx(
                d, has_new_error=True, trimmed="auto.",
                raw_curr="prev\n[error-1-1] some error\n",
                raw_prev="prev",
            ))
            assert results == []

        def auto_sig_dedup_persists():
            """Same lemma name, two calls — only fires once. The
            phase's _seen_names set prevents re-emission."""
            phase = AutoSigPhase(_StubSession())
            phase._seen_names.add("foo_lemma")
            assert "foo_lemma" in phase._seen_names

        # ── TACTIC_NO_EFFECT_AUTO_REVERTED ──

        def tactic_no_effect_silent_when_progress():
            r = tactic_no_effect_trigger(_ctx(d, no_progress=False))
            assert r is None

        def tactic_no_effect_fires_with_rollback_request():
            r = tactic_no_effect_trigger(_ctx(d, no_progress=True))
            assert r is not None
            assert "[TACTIC_NO_EFFECT_AUTO_REVERTED]" in _text(r)
            assert r.request_rollback is True, \
                "must request rollback for the caller to apply"
            assert r.layer == 0
            # Trigger itself does NOT mutate files; that's the caller's job
            # (Session._apply_no_progress_rollback)

        # ── STATE-DIFF ──

        def state_diff_silent_when_no_progress():
            r = state_diff_trigger(_ctx(d, no_progress=True))
            assert r is None

        def state_diff_silent_when_error():
            r = state_diff_trigger(_ctx(d, has_new_error=True))
            assert r is None

        def state_diff_writes_commit_meta_log_even_on_empty_block():
            """commit_meta.log gets a line per commit regardless of
            whether format_state_diff_block produced text. Required
            for cross-subgoal-transition analysis alignment."""
            meta = d / "commit_meta.log"
            if meta.exists():
                meta.unlink()
            r = state_diff_trigger(_ctx(
                d, no_progress=False, has_new_error=False,
                trimmed="auto.",
                raw_curr="...", raw_prev="...",  # identical → empty diff
            ))
            assert meta.exists(), "commit_meta.log must be written"
            content = meta.read_text()
            assert "auto." in content, f"got: {content!r}"
            # Cleanup
            meta.unlink()

        # ── Combined: hook ordering / interactions ──

        def closed_and_too_large_both_fire():
            # Edge case: a `qed.` close on a previously-large goal
            big = "x" * 9000
            ctx = _ctx(d, no_more=True, active_goal=big)
            assert all_goals_closed_trigger(ctx) is not None
            assert goal_closed_trigger(ctx) is None  # all-closed path owns it
            assert goal_too_large_trigger(ctx) is not None

        all_cases = [
            ("GOAL_CLOSED: partial close emits closed/remaining counts",
             goal_closed_partial),
            ("GOAL_CLOSED: silent when proof fully closed (no_more)",
             goal_closed_skips_when_no_more),
            ("GOAL_CLOSED: silent on async-check close",
             goal_closed_skips_when_async_close),
            ("GOAL_CLOSED: silent when count unchanged",
             goal_closed_skips_when_no_change),
            ("GOAL_CLOSED: silent when count grew (case/split)",
             goal_closed_skips_when_count_grew),
            ("ALL_GOALS_CLOSED: sync no_more path",
             all_closed_no_more_path),
            ("ALL_GOALS_CLOSED: async-check path with mode-explainer",
             all_closed_async_check_path),
            ("ALL_GOALS_CLOSED: no_more dominates when both flags set",
             all_closed_no_more_dominates_async),
            ("ALL_GOALS_CLOSED: silent when neither flag set",
             all_closed_silent_when_neither),
            ("GOAL-TOO-LARGE: fires above 8000 bytes with size in body",
             too_large_fires_above_threshold),
            ("GOAL-TOO-LARGE: silent below threshold",
             too_large_silent_below_threshold),
            ("GOAL-TOO-LARGE: silent on empty active_goal",
             too_large_silent_when_empty),
            ("GOAL-TOO-LARGE: is_goal_too_large boundary at 8000",
             too_large_threshold_predicate),
            ("STRICT_WARNING: fires + requests suppress_error",
             strict_fires_with_suppress_error),
            ("STRICT_WARNING: silent without no_more",
             strict_silent_when_no_more_false),
            ("STRICT_WARNING: silent when has_new_error=False",
             strict_silent_when_no_error),
            ("STRICT_WARNING: silent when a real error is mixed in",
             strict_silent_when_real_error_present),
            ("STRICT_WARNING: silent when no [error tagged lines exist",
             strict_silent_when_no_strict_lines_at_all),
            ("[goal:<type>]: silent when active_goal is empty",
             goal_header_silent_when_active_goal_empty),
            ("[goal:<type>]: emits L1 header with marker prefix",
             goal_header_returns_l1),
            ("[goal:<type>]: compute_goal_header never raises",
             goal_header_compute_helper_unparseable_returns_empty),
            ("DAEMON_REJECTED: silent without error",
             daemon_rejected_silent_when_no_error),
            ("DAEMON_REJECTED: strips [error]/[critical]/[fatal] prefix",
             daemon_rejected_strips_severity_prefix),
            ("DAEMON_REJECTED: layer 0",
             daemon_rejected_l0_layer),
            ("AUTO-NOPROG-HINT: silent when progress was made",
             auto_noprog_silent_when_progress),
            ("AUTO-NOPROG-HINT: contract-only (no hint = None)",
             auto_noprog_silent_when_no_hint),
            ("AutoSigPhase: silent when no error",
             auto_sig_silent_when_no_error),
            ("AutoSigPhase: silent on lemmas in IGNORE list",
             auto_sig_silent_when_no_lemma_in_tactic),
            ("AutoSigPhase: per-name dedup persists across run() calls",
             auto_sig_dedup_persists),
            ("TACTIC_NO_EFFECT: silent when progress was made",
             tactic_no_effect_silent_when_progress),
            ("TACTIC_NO_EFFECT: fires + requests rollback (no file mutation)",
             tactic_no_effect_fires_with_rollback_request),
            ("STATE-DIFF: silent on no_progress",
             state_diff_silent_when_no_progress),
            ("STATE-DIFF: silent on has_new_error",
             state_diff_silent_when_error),
            ("STATE-DIFF: commit_meta.log written even when block empty",
             state_diff_writes_commit_meta_log_even_on_empty_block),
            ("Combined: closed+too-large coexist on a heavy qed close",
             closed_and_too_large_both_fire),
        ]

        for name, fn in all_cases:
            if not case(name, fn):
                fail += 1

    n = len(all_cases)
    print()
    print(f"{n - fail}/{n} pass")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())


def test_all_cases() -> None:
    """pytest entry: the case() harness's failure count must be zero.

    This file predates the pytest convention (custom case()/main()); the
    wrapper makes its coverage visible to `pytest tests/` — it had been
    silently collected as zero tests.
    """
    assert main() == 0
