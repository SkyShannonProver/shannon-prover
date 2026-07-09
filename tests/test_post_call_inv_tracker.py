"""Unit tests for the `[POST-CALL-INV-HINT]` state-machine — the tracker
that surfaces a hint after 3 consecutive failed close attempts post-
`call (_: Inv)` commit.

Pure-Python: no EC daemon, no session_cli wiring. Exercises the regex,
file-state transitions, and one-shot semantics.

The tracker logic lives in `core/easycrypt/session_hooks.py` (Phase 0
of the hook-registry refactor). Earlier draft of these tests imported
`Session._post_call_inv_tracker` from session_cli; that method has been
moved into `session_hooks.post_call_inv_trigger` and now takes a
`CommitHookContext` instead of positional args. Test cases unchanged.

Run: `python3 tests/test_post_call_inv_tracker.py`
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from core.easycrypt.session_hooks import (  # noqa: E402
    CommitHookContext,
    _POST_CALL_INV_RE,
    post_call_inv_trigger,
)

TRACKER_FILE = "post_call_inv_count.txt"


def _call(d, trimmed, has_new_error=False, no_progress=False,
          prev_count=0, curr_count=0):
    """Convenience: build a CommitHookContext and invoke the trigger."""
    return post_call_inv_trigger(CommitHookContext(
        session_dir=d, trimmed=trimmed,
        has_new_error=has_new_error, no_progress=no_progress,
        prev_count=prev_count, curr_count=curr_count,
    ))


def _read(d: Path) -> str | None:
    p = d / TRACKER_FILE
    return p.read_text() if p.exists() else None


def _write(d: Path, contents: str):
    (d / TRACKER_FILE).write_text(contents)


def _clear(d: Path):
    p = d / TRACKER_FILE
    if p.exists():
        p.unlink()


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

        # ── 1. Regex: matches and non-matches ──
        # The regex is the pre-condition for "did agent commit a call (_: Inv)?"
        # — it should match all syntactic variants of the bare `call (_: ...)`
        # form and skip everything else.
        def regex_matches():
            r = _POST_CALL_INV_RE
            assert r.match("call (_: ={glob A}).")
            assert r.match("call (_: StLSke.gs{1} = RO.m{2} /\\ ={Mem.lc}).")
            assert r.match("  call (_: Inv).")
            assert r.match("call (_:Inv).")
            assert r.match("CALL (_: Inv).")  # case-insensitive

        def regex_skips():
            r = _POST_CALL_INV_RE
            assert not r.match("call equ_cc.")
            assert not r.match("call UFCMA_genCC &m.")
            assert not r.match("byequiv (_: ={glob A}).")
            assert not r.match("apply foo.")
            assert not r.match("ecall (equ_cc n{1}).")
            assert not r.match("by call (_: Inv).")  # `by` prefix

        # ── 2. Successful call (_: Inv) commit creates file = "0" ──
        def commit_creates_file():
            _clear(d)
            ret = _call(
                d, "call (_: ={glob A}).",
                has_new_error=False, no_progress=False,
                prev_count=1, curr_count=4,
            )
            assert ret is None, f"unexpected hint: {ret!r}"
            assert _read(d) == "0", f"file content: {_read(d)!r}"

        # ── 3. Failed call (_: Inv) commit does NOT create file ──
        def failed_commit_no_file():
            _clear(d)
            # has_new_error=True
            ret = _call(
                d, "call (_: ={glob A}).",
                has_new_error=True, no_progress=False,
                prev_count=1, curr_count=1,
            )
            assert ret is None
            assert _read(d) is None, f"file should not exist; got {_read(d)!r}"

            # no_progress=True
            ret = _call(
                d, "call (_: ={glob A}).",
                has_new_error=False, no_progress=True,
                prev_count=1, curr_count=1,
            )
            assert ret is None
            assert _read(d) is None

        # ── 4. Failing tactic post-call increments count ──
        def fail_increments():
            _clear(d)
            _write(d, "0")
            ret = _call(
                d, "smt().",
                has_new_error=True, no_progress=False,
                prev_count=4, curr_count=4,
            )
            assert ret is None, f"unexpected hint: {ret!r}"
            assert _read(d) == "1"

            ret = _call(
                d, "auto.",
                has_new_error=False, no_progress=True,
                prev_count=4, curr_count=4,
            )
            assert ret is None
            assert _read(d) == "2"

        # ── 5. Threshold crossing fires hint AND deletes file (one-shot) ──
        def threshold_fires():
            _clear(d)
            _write(d, "2")
            ret = _call(
                d, "smt().",
                has_new_error=True, no_progress=False,
                prev_count=4, curr_count=4,
            )
            assert ret is not None, "hint should have fired"
            # v2: trigger now returns HookResult; older versions returned str
            text = ret.text if hasattr(ret, "text") else ret
            assert "[POST-CALL-INV-HINT]" in text
            assert "transitivity" in text  # check (2) advice
            assert _read(d) is None, "file should be deleted (one-shot)"

        # ── 6. Closing a subgoal resets count to "0" ──
        def close_resets():
            _clear(d)
            _write(d, "2")
            ret = _call(
                d, "smt().",
                has_new_error=False, no_progress=False,
                prev_count=4, curr_count=3,  # subgoal closed
            )
            assert ret is None
            assert _read(d) == "0", \
                f"file should reset to 0; got {_read(d)!r}"

        # ── 7. Neutral tactic (no error, no progress, no subgoal closed) ──
        # Leaves count unchanged. Example: agent runs `-status` or `-goal-info`
        # which doesn't appear here, but a tactic like `idtac.` would.
        def neutral_unchanged():
            _clear(d)
            _write(d, "1")
            ret = _call(
                d, "idtac.",
                has_new_error=False, no_progress=False,
                prev_count=4, curr_count=4,  # no change
            )
            assert ret is None
            assert _read(d) == "1", f"unchanged; got {_read(d)!r}"

        # ── 8. No file + non-call tactic → no-op ──
        def no_file_noop():
            _clear(d)
            ret = _call(
                d, "smt().",
                has_new_error=True, no_progress=False,
                prev_count=2, curr_count=2,
            )
            assert ret is None
            assert _read(d) is None

        # ── 9. New `call (_: Inv)` resets file even if previously tracking ──
        # If agent commits a fresh call (_: Inv) (e.g., on a new subgoal), we
        # reset to start tracking the new fan-out from scratch.
        def new_call_overwrites():
            _clear(d)
            _write(d, "2")
            ret = _call(
                d, "call (_: ={glob B}).",
                has_new_error=False, no_progress=False,
                prev_count=4, curr_count=7,
            )
            assert ret is None
            assert _read(d) == "0", f"should reset to 0; got {_read(d)!r}"

        # ── 10. Corrupted file content → treated as 0 ──
        def corrupted_resets():
            _clear(d)
            _write(d, "garbage_not_an_int")
            ret = _call(
                d, "smt().",
                has_new_error=True, no_progress=False,
                prev_count=4, curr_count=4,
            )
            # Corrupted = 0; +1 = 1; below threshold → no hint, file = "1"
            assert ret is None
            assert _read(d) == "1"

        all_cases = [
            ("regex matches all `call (_: ...)` variants", regex_matches),
            ("regex skips named-equiv / non-call tactics", regex_skips),
            ("successful call (_: Inv) commit creates file=\"0\"",
             commit_creates_file),
            ("failed call (_: Inv) commit (error or no_progress) does NOT create file",
             failed_commit_no_file),
            ("failing tactic post-call increments count",
             fail_increments),
            ("threshold (3) fires hint AND deletes file (one-shot)",
             threshold_fires),
            ("subgoal-closing tactic resets count to \"0\"",
             close_resets),
            ("neutral tactic leaves count unchanged",
             neutral_unchanged),
            ("no file + non-call tactic is a no-op",
             no_file_noop),
            ("new `call (_: Inv)` overwrites tracker to \"0\"",
             new_call_overwrites),
            ("corrupted file content treated as 0",
             corrupted_resets),
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
