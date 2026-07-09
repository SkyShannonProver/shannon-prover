"""Tests for EasyCrypt error classification (factual attribution only)."""
from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from core.easycrypt.analysis.ec_error_classifier import (  # noqa: E402
    classify,
    format_classification,
)


def test_classify_attributes_arity_error_as_syntax() -> None:
    cls = classify("invalid function application: wrong number of arguments")
    assert cls is not None
    assert cls["class"] == "syntax error"
    assert cls["subtype"] == "argument count mismatch"
    # Factual attribution only — no prescriptive "do not" / next-move fields.
    assert "do_not" not in cls
    assert set(cls) == {"class", "subtype", "what", "why"}


def test_format_renders_facts_without_directed_retry() -> None:
    cls = classify("invalid function application: wrong number of arguments")
    rendered = format_classification(
        cls,
        tactic_text="have := MainD(G2, FinRO).distinguish(()).",
        raw_error="invalid function application: wrong number of arguments",
    )
    # The factual class / what / why is surfaced.
    assert "[CLASS: syntax error — argument count mismatch]" in rendered
    assert "What this means:" in rendered
    assert "Why it's a syntax error:" in rendered
    # No heuristic directed-retry nudge or "do not abandon" guidance.
    assert "REQUIRED NEXT ACTION" not in rendered
    assert "Full-tactic replacements" not in rendered
    assert "DO NOT" not in rendered
    assert "do not abandon" not in rendered.lower()


def test_format_points_at_tactic_forms_reference_for_covered_head() -> None:
    cls = classify("invalid function application: wrong number of arguments")
    rendered = format_classification(cls, tactic_text="call foo bar.")
    # A factual pointer to the grammar-fact reference — the agent retrieves the
    # forms itself; the classifier does not pick the next move.
    assert "-tactic-forms call" in rendered


def main() -> int:
    test_classify_attributes_arity_error_as_syntax()
    test_format_renders_facts_without_directed_retry()
    test_format_points_at_tactic_forms_reference_for_covered_head()
    print("PASS test_ec_error_classifier")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
