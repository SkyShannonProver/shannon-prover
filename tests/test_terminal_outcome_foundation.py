"""Permanent architecture gates for the single terminal-outcome owner."""

from __future__ import annotations

import inspect
from dataclasses import fields

import pytest

from workflow.schemas.prover_result import (
    PROVER_RUN_INFRASTRUCTURE_INVALID,
    PROVER_RUN_VERIFIED,
    ProverResult,
)
from workflow.tree.result import SessionClosureCandidate, TreeRunResult


def test_tree_handoff_has_no_final_proof_verdict() -> None:
    tree_fields = {field.name for field in fields(TreeRunResult)}
    candidate_fields = {field.name for field in fields(SessionClosureCandidate)}
    assert "proved" not in tree_fields
    assert "verified" not in tree_fields
    assert "proved" not in candidate_fields
    assert "verified" not in candidate_fields


def test_verified_prover_result_requires_passing_verification() -> None:
    with pytest.raises(ValueError, match="passing verification"):
        ProverResult(status=PROVER_RUN_VERIFIED)
    result = ProverResult(
        status=PROVER_RUN_VERIFIED,
        verification={"status": "pass", "method": "test"},
    )
    assert result.is_verified


def test_infrastructure_invalid_requires_explicit_error() -> None:
    with pytest.raises(ValueError, match="requires an error"):
        ProverResult(status=PROVER_RUN_INFRASTRUCTURE_INVALID)


def test_tree_runner_has_no_mutable_last_attribute_contract() -> None:
    from workflow.tree.supervisor import run_tree_prover

    source = inspect.getsource(run_tree_prover)
    assert "last_session" not in source
    assert "last_ec_session_dir" not in source
    assert "last_destructive" not in source


def test_current_terminal_consumers_do_not_parse_console_success() -> None:
    from workflow import project_driver
    from workflow.validation import run_report_bundle

    driver_source = inspect.getsource(project_driver.run_one_lemma)
    report_source = inspect.getsource(run_report_bundle._outcome)
    assert "Proved: True" not in driver_source
    assert "Verification PASSED" not in driver_source
    assert "summary.json" not in report_source
    assert "prover_run_result.json" not in report_source  # delegated reader
    assert "_terminal_result" in report_source
