from __future__ import annotations

from core.easycrypt.session_tactic_execution_observation import (
    tactic_execution_failed,
    tactic_execution_no_progress,
    tactic_execution_workspace,
)


def test_tactic_execution_observation_reads_current_envelope() -> None:
    workspace = {"kind": "prover_workspace_view", "schema_version": 2}
    result = {
        "ok": True,
        "execution": {"steps": [{"status": "accepted"}]},
        "result": {"ok": True, "status": "ok"},
        "workspace": {"view": workspace},
    }

    assert tactic_execution_workspace(result) == workspace
    assert tactic_execution_failed(result) is False
    assert tactic_execution_no_progress(result) is False


def test_tactic_execution_observation_classifies_failure_and_no_progress() -> None:
    assert tactic_execution_failed({
        "ok": True,
        "execution": {"failed_tactic": "bad."},
        "result": {"ok": False, "status": "error"},
    }) is True
    assert tactic_execution_no_progress({
        "execution": {"steps": [{"status": "no_progress"}]},
        "result": {"status": "ok"},
    }) is True


def test_no_progress_runtime_shape_is_not_misclassified_as_failure() -> None:
    result = {
        "ok": False,
        "execution": {
            "failed_tactic": "simplify.",
            "steps": [{"status": "no_progress"}],
        },
        "result": {
            "ok": False,
            "status": "no_progress_reverted",
        },
    }

    assert tactic_execution_no_progress(result) is True
    assert tactic_execution_failed(result) is False
