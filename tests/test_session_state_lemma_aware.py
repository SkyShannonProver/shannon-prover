"""Tests for lemma-aware closed-proof detection in session_state.

These cover the bug Tree-0.1 hit on ChaChaPoly step1 (2026-05-03): the
extracted file contains helper lemmas with `admit. qed.` that close
BEFORE the target lemma's `proof.` opens. EC emits "No more goals" and
"+ added lemma: 'helper'" for each helper; the legacy parser scans
backwards from the last prompt and sees one of those "No more goals"
lines, falsely reporting the target as closed.

The fix: when we know the target lemma name (e.g., from
`session_meta.json` written by `-start -lemma <NAME>`), use EC's
authoritative "+ added lemma: `<target>'" signal instead.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

from core.easycrypt.session_state import (  # type: ignore  # noqa: E402
    REMAINING_UNKNOWN,
    read_session_state,
    read_target_lemma_from_meta,
    target_lemma_added,
)


_HELPER_CLOSED_TARGET_OPEN = """\
[157|check]>
+ added lemma: `helper_a'
[158|check]>
[159|check]>
No more goals
[160|check]>
+ added lemma: `sample_spec'
[161|check]>
[error-26-28]unknown type name: RO
[162|check]>
"""


_TARGET_CLOSED = """\
[157|check]>
+ added lemma: `helper_a'
[158|check]>
[159|check]>
No more goals
[160|check]>
+ added lemma: `sample_spec'
[161|check]>
[162|check]>
No more goals
[163|check]>
+ added lemma: `step1'
[164|check]>
"""


_LEGACY_NO_TARGET = """\
[5|check]>
No more goals
[6|check]>
"""


# ─── target_lemma_added unit tests ────────────────────────────────────────

def test_target_lemma_added_detects_exact_quoting() -> None:
    raw = "[7|check]>\n+ added lemma: `step1'\n[8|check]>\n"
    assert target_lemma_added(raw, "step1") is True


def test_target_lemma_added_distinguishes_targets() -> None:
    raw = "+ added lemma: `sample_spec'\n+ added lemma: `helper_a'\n"
    assert target_lemma_added(raw, "step1") is False
    assert target_lemma_added(raw, "sample_spec") is True
    assert target_lemma_added(raw, "helper_a") is True


def test_target_lemma_added_empty_target_returns_false() -> None:
    raw = "+ added lemma: `step1'\n"
    assert target_lemma_added(raw, "") is False


def test_target_lemma_added_handles_regex_special_chars_in_name() -> None:
    raw = "+ added lemma: `lemma.with.dots'\n"
    assert target_lemma_added(raw, "lemma.with.dots") is True
    # The dot regex should be escaped — not a wildcard match.
    assert target_lemma_added(raw, "lemmaXwithXdots") is False


# ─── read_target_lemma_from_meta unit tests ───────────────────────────────

def test_read_target_lemma_from_meta_present() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        (d / "session_meta.json").write_text(
            json.dumps({"lemma": "step1", "file": "x.ec"}),
            encoding="utf-8",
        )
        assert read_target_lemma_from_meta(d) == "step1"


def test_read_target_lemma_from_meta_missing_file() -> None:
    with tempfile.TemporaryDirectory() as td:
        assert read_target_lemma_from_meta(Path(td)) == ""


def test_read_target_lemma_from_meta_missing_field() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        (d / "session_meta.json").write_text(
            json.dumps({"file": "x.ec"}),
            encoding="utf-8",
        )
        assert read_target_lemma_from_meta(d) == ""


# ─── read_session_state integration tests ────────────────────────────────

def _write_session(td: Path, current: str, *, lemma: str | None = None) -> Path:
    (td / "current.out").write_text(current, encoding="utf-8")
    (td / "prev.out").write_text("", encoding="utf-8")
    if lemma is not None:
        (td / "session_meta.json").write_text(
            json.dumps({"lemma": lemma, "file": "x.ec"}),
            encoding="utf-8",
        )
    return td


def test_read_session_state_target_open_overrides_helper_no_more_goals() -> None:
    """Tree-0.1 reproducer: target's open ``proof.`` follows several
    closed helpers. Legacy heuristic falsely reports closed; new logic
    overrides because ``+ added lemma: `step1'`` is absent."""
    with tempfile.TemporaryDirectory() as td:
        _write_session(Path(td), _HELPER_CLOSED_TARGET_OPEN, lemma="step1")
        state = read_session_state(Path(td))
    assert state.proof_candidate_closed is False
    assert state.num_remaining == REMAINING_UNKNOWN


def test_read_session_state_target_closed_when_added_signal_present() -> None:
    """When EC has emitted ``+ added lemma: `step1'``, the proof IS
    closed — and the lemma-aware path agrees."""
    with tempfile.TemporaryDirectory() as td:
        _write_session(Path(td), _TARGET_CLOSED, lemma="step1")
        state = read_session_state(Path(td))
    assert state.proof_candidate_closed is True
    assert state.num_remaining == 0


def test_read_session_state_no_target_falls_back_to_legacy() -> None:
    """No session_meta.json (or no lemma field) → legacy heuristic
    still applies. ``No more goals`` on the latest prompt → closed."""
    with tempfile.TemporaryDirectory() as td:
        _write_session(Path(td), _LEGACY_NO_TARGET)
        state = read_session_state(Path(td))
    assert state.proof_candidate_closed is True
    assert state.num_remaining == 0


def test_read_session_state_explicit_target_overrides_meta() -> None:
    """Caller passes target_lemma; takes precedence over session_meta."""
    with tempfile.TemporaryDirectory() as td:
        _write_session(Path(td), _HELPER_CLOSED_TARGET_OPEN, lemma="not_step1")
        # Meta says target=not_step1 (which IS closed in helper text).
        # Explicit override forces the real target.
        state = read_session_state(Path(td), target_lemma="step1")
    assert state.proof_candidate_closed is False


def test_read_session_state_explicit_empty_target_disables_lemma_aware() -> None:
    """Passing ``target_lemma=""`` opts out of lemma-aware detection
    even when session_meta.json has a lemma."""
    with tempfile.TemporaryDirectory() as td:
        _write_session(Path(td), _HELPER_CLOSED_TARGET_OPEN, lemma="step1")
        state = read_session_state(Path(td), target_lemma="")
    # Legacy heuristic kicks in; the helper's "No more goals" wins.
    assert state.proof_candidate_closed is True


def main() -> int:
    tests = [
        test_target_lemma_added_detects_exact_quoting,
        test_target_lemma_added_distinguishes_targets,
        test_target_lemma_added_empty_target_returns_false,
        test_target_lemma_added_handles_regex_special_chars_in_name,
        test_read_target_lemma_from_meta_present,
        test_read_target_lemma_from_meta_missing_file,
        test_read_target_lemma_from_meta_missing_field,
        test_read_session_state_target_open_overrides_helper_no_more_goals,
        test_read_session_state_target_closed_when_added_signal_present,
        test_read_session_state_no_target_falls_back_to_legacy,
        test_read_session_state_explicit_target_overrides_meta,
        test_read_session_state_explicit_empty_target_disables_lemma_aware,
    ]
    for t in tests:
        t()
    print("PASS test_session_state_lemma_aware")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
