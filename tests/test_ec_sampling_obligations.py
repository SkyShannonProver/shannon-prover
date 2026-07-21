"""Tests for sampling/coupling obligation frontend."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from core.easycrypt.analysis.ec_sampling_obligations import (  # noqa: E402
    build_sampling_obligation_frontend,
    sample_distribution,
    sample_var,
)


def test_sample_var_and_distribution_parse_statement_fallbacks() -> None:
    sample = {"text": "s <$ dT;", "vars_written": []}

    assert sample_var(sample, sample["text"]) == "s"
    assert sample_distribution(sample, sample["text"]) == "dT"


def test_sampling_frontend_classifies_translation_coupling() -> None:
    frontend = build_sampling_obligation_frontend(
        [
            {
                "side": "left",
                "side_index": 1,
                "statement_order": 1,
                "statement_path": "1",
                "statement": "s <$ dT;",
                "vars_written": ["s"],
            },
            {
                "side": "right",
                "side_index": 2,
                "statement_order": 1,
                "statement_path": "1",
                "statement": "t <$ dT;",
                "vars_written": ["t"],
            },
        ],
        parsed={"post": "post = t{2} = s{1} + mask{2}"},
        goal_text="",
    )

    obligation = frontend["obligations"][0]
    assert frontend["available"] is True
    assert obligation["same_distribution"] is True
    assert obligation["relation_motif"]["motif"] == "translation_or_affine"
    assert any(
        item["family"] == "translation_or_affine"
        for item in obligation["candidate_families"]
    )
    affine = [
        item for item in obligation["candidate_families"]
        if item["family"] == "translation_or_affine"
    ][0]
    assert affine["offset_candidates"][0]["offset"] == "mask{2}"
    assert affine["tactic_template"] == (
        "rnd (fun x => x + mask{2}) (fun x => x - mask{2})."
    )
    assert "candidate_distribution_facts" not in obligation["required_evidence"]


def test_sampling_frontend_pairs_same_distribution_before_one_sided() -> None:
    frontend = build_sampling_obligation_frontend(
        [
            {
                "side": "left",
                "side_index": 1,
                "statement_order": 1,
                "statement_path": "1",
                "statement": "r <$ dR;",
                "vars_written": ["r"],
            },
            {
                "side": "left",
                "side_index": 1,
                "statement_order": 2,
                "statement_path": "2",
                "statement": "s <$ dS;",
                "vars_written": ["s"],
            },
            {
                "side": "right",
                "side_index": 2,
                "statement_order": 1,
                "statement_path": "1",
                "statement": "t <$ dS;",
                "vars_written": ["t"],
            },
        ],
        parsed={"post": "post = t{2} = s{1} + offset{1}"},
        goal_text="",
    )

    assert frontend["obligations"][0]["left_sample"]["var"] == "s"
    assert frontend["obligations"][0]["right_sample"]["var"] == "t"
    assert frontend["obligations"][0]["same_distribution"] is True
    assert frontend["obligations"][1]["left_sample"]["var"] == "r"
    assert frontend["obligations"][1]["right_sample"] == {}


def test_sampling_frontend_classifies_identity_samples() -> None:
    frontend = build_sampling_obligation_frontend(
        [
            {
                "side": "left",
                "side_index": 1,
                "statement_order": 1,
                "statement_path": "1",
                "statement": "m <$ dbytes32;",
                "vars_written": ["m"],
            },
            {
                "side": "right",
                "side_index": 2,
                "statement_order": 1,
                "statement_path": "1",
                "statement": "m <$ dbytes32;",
                "vars_written": ["m"],
            },
        ],
        parsed={"post": "post = m{1} = m{2}"},
        goal_text="",
    )

    obligation = frontend["obligations"][0]
    assert obligation["same_distribution"] is True
    assert obligation["relation_motif"]["motif"] == "identity"
    assert any(
        item["family"] == "identity"
        for item in obligation["candidate_families"]
    )
