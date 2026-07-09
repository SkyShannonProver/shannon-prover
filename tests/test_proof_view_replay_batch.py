"""Tests for proof-view replay batch validation helper."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from workflow.validation.proof_view_replay_batch import (  # noqa: E402
    ReplaySpec,
    _summary,
    specs_for_preset,
    summarize_rows,
    parse_spec_item,
    read_spec_file,
)


def test_parse_spec_item() -> None:
    spec = parse_spec_item("ChaChaPoly|examples/chacha.ec|step1")

    assert spec == ReplaySpec(
        project="ChaChaPoly",
        file="examples/chacha.ec",
        lemma="step1",
    )
    assert spec.label == "ChaChaPoly:step1"


def test_parse_spec_item_rejects_incomplete_spec() -> None:
    try:
        parse_spec_item("ChaChaPoly|examples/chacha.ec")
    except argparse.ArgumentTypeError as err:
        assert "PROJECT|FILE|LEMMA" in str(err)
    else:
        raise AssertionError("expected argparse.ArgumentTypeError")


def test_read_spec_file(tmp_path: Path) -> None:
    path = tmp_path / "specs.json"
    path.write_text(json.dumps([
        {
            "project": "MEE-CBC",
            "file": "examples/MEE-CBC/CBC.eca",
            "lemma": "Bound_by_Birthday",
        }
    ]))

    assert read_spec_file(path) == [
        ReplaySpec(
            project="MEE-CBC",
            file="examples/MEE-CBC/CBC.eca",
            lemma="Bound_by_Birthday",
        )
    ]


def test_summary_accepts_nested_batch_report_shape() -> None:
    assert _summary({
        "summary": {
            "accepted_steps": 3,
            "missing_view_alignments": 1,
            "lint_errors": 0,
        }
    }) == {
        "accepted_steps": 3,
        "missing_view_alignments": 1,
        "lint_errors": 0,
    }


def test_specs_for_preset_resolves_against_examples_root(tmp_path: Path) -> None:
    specs = specs_for_preset("chachapoly-hard", tmp_path)

    assert specs[0] == ReplaySpec(
        project="ChaChaPoly",
        file=str(tmp_path / "ChaChaPoly/chacha_poly.ec"),
        lemma="step1",
    )
    assert any(spec.lemma == "step4_badi" for spec in specs)


def test_summarize_rows_merges_bucket_counts() -> None:
    summary = summarize_rows([
        {
            "project": "ChaChaPoly",
            "lemma": "step2_2",
            "accepted_steps": 10,
            "missing_view_alignments": 3,
            "missing_bucket_only": 1,
            "missing_absent": 2,
            "text_lint_errors": 0,
            "steps_by_bucket": {"pr_bridge": 4, "procedure_control": 6},
            "missing_by_bucket": {"pr_bridge": 1, "procedure_control": 2},
            "report": "a/report.json",
        },
        {
            "project": "MEE-CBC",
            "lemma": "CBC_upto",
            "accepted_steps": 7,
            "missing_view_alignments": 1,
            "missing_bucket_only": 0,
            "missing_absent": 1,
            "text_lint_errors": 2,
            "steps_by_bucket": {"procedure_control": 7},
            "missing_by_bucket": {"procedure_control": 1},
            "report": "b/report.json",
        },
    ])

    assert summary["lemma_count"] == 2
    assert summary["accepted_steps"] == 17
    assert summary["missing_view_alignments"] == 4
    assert summary["text_lint_errors"] == 2
    assert summary["missing_bucket_only"] == 1
    assert summary["missing_absent"] == 3
    assert summary["steps_by_bucket"] == {
        "pr_bridge": 4,
        "procedure_control": 13,
    }
    assert summary["missing_by_bucket"] == {
        "pr_bridge": 1,
        "procedure_control": 3,
    }
    assert summary["top_missing"][0]["lemma"] == "step2_2"
