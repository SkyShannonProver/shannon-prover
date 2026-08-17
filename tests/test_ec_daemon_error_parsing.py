"""Unit tests for EasyCrypt daemon error extraction."""
from __future__ import annotations

import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from core.easycrypt.ec_daemon import ECSubprocess


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
