"""Unit tests for EasyCrypt daemon error extraction."""
from __future__ import annotations

import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from core.easycrypt.ec_daemon import ECSubprocess
from core.easycrypt.ec_diagnostics import error_text, parse_error
from core.easycrypt.ec_warm_prober import _error_text


def test_parse_error_preserves_multiline_proof_term_evidence() -> None:
    parsed = ECSubprocess._parse_error(
        "[error-12-34]the given proof-term proves:\n"
        "  FMap.hasP (fun k v => P v) m\n"
        "instead of:\n"
        "  List.has P xs\n"
        "[130|check]>"
    )

    assert parsed is not None
    assert parsed["severity"] == "error"
    assert parsed["kind"] == "other"
    assert parsed["raw"] == (
        "the given proof-term proves:\n"
        "  FMap.hasP (fun k v => P v) m\n"
        "instead of:\n"
        "  List.has P xs"
    )
    assert "[130|check]>" not in parsed["raw"]


def test_parse_error_classifies_from_continuation_lines() -> None:
    parsed = ECSubprocess._parse_error(
        "[critical]the given proof-term proves:\n"
        "  expression with a type mismatch\n"
        "[9|check]>"
    )

    assert parsed is not None
    assert parsed["severity"] == "critical"
    assert parsed["kind"] == "type_error"


def test_transports_share_multiline_fatal_diagnostic():
    raw = "[fatal]the given proof-term proves:\n  EXPECTED\ninstead of:\n  ACTUAL\n[9|check]>"
    assert ECSubprocess._parse_error(raw) == parse_error(raw)
    assert _error_text(raw) == error_text(raw)
    assert "ACTUAL" in error_text(raw)
    assert "[9|check]>" not in error_text(raw)


def test_batch_keeps_first_error_without_appending_later_responses():
    raw = "[critical]first\n  DETAILS\n[error-2-0]second\n[9|check]>\nNo more goals"
    assert error_text(raw) == "[critical] first\n  DETAILS"
