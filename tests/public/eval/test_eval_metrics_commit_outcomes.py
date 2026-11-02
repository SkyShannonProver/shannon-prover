"""Eval metrics count manager commit outcomes from the typed verdict.

Action records here are produced by the manager's own builders
(``_backend_action_outcome`` and ``agent_observation_for_request``) from
tactic-execution payloads, so they have the exact production shape and
prose, including the no-op reversion text that says EasyCrypt "accepted"
the tactic.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest


import eval_suite.metrics as metrics
from workflow.proof_management import backend_actions
from workflow.proof_management.backend_request import BackendRequest
from workflow.proof_management.protocol_repair import qed_clarification_action
from workflow.schemas.prover_result import (
    PROVER_RUN_INCOMPLETE,
    PROVER_RUN_VERIFIED,
    ProverResult,
)


def _commit_action(status: str, *, ok: bool, state_changed: bool) -> dict:
    tactic = "inline *."
    request = BackendRequest.commit("commit_tactic", tactic)
    payload = {
        "ok": ok,
        "result": {"status": status, "ok": ok},
        "execution": {
            "state_changed": state_changed,
            "history_committed": state_changed,
            "submitted_tactics": [tactic],
        },
    }
    outcome = backend_actions._backend_action_outcome(
        request,
        stdout="",
        exit_code=0,
        requires_execution_result=True,
        tactic_execution_result=payload,
    )
    observation = backend_actions.agent_observation_for_request(
        request,
        stdout="",
        stderr="",
        exit_code=0,
        tactic_execution_resolution=backend_actions._TacticExecutionResolution(
            required=True,
            result=payload,
        ),
    )
    return {
        "label": "commit_tactic",
        "exit_code": 0,
        "mutates_proof_state": True,
        **outcome,
        "agent_observation": observation,
    }


ACCEPTED = _commit_action("ok", ok=True, state_changed=True)
REJECTED = _commit_action("failed", ok=False, state_changed=False)
PARTIAL = _commit_action("partial_success", ok=True, state_changed=True)


@pytest.mark.parametrize("ok", [True, False])
def test_reverted_no_op_commit_is_not_an_accepted_commit(ok):
    action = _commit_action("no_progress_reverted", ok=ok, state_changed=False)
    # The trap: the manager's prose for this outcome says "accepted".
    assert "accepted" in action["agent_observation"]["result"]
    assert action["outcome_kind"] == "no_progress"

    assert metrics._action_was_accepted(action) is False


def test_commit_outcomes_follow_the_typed_verdict():
    assert metrics._action_was_accepted(ACCEPTED) is True
    assert metrics._action_was_accepted(REJECTED) is False
    assert metrics._action_was_accepted(PARTIAL) is False
    timeout = backend_actions.timeout_backend_action_record(
        BackendRequest.commit("commit_tactic", "smt()."),
        ["session_cli.py", "-tactic-exec", "commit", "-c", "smt()."],
        subprocess.TimeoutExpired("session_cli.py", 180),
        180,
    )
    assert metrics._action_was_accepted(timeout) is False


def test_commits_the_manager_never_ran_are_not_accepted():
    # A premature `qed.` the manager declined to execute (exit code 0).
    clarification = qed_clarification_action({"tactic": "qed."})
    assert clarification["outcome_kind"] == "repair"
    assert metrics._action_was_accepted(clarification) is False
    # A commit whose event-bound execution result is missing.
    contract_error = dict(ACCEPTED)
    contract_error.update(
        outcome_kind="backend_error",
        proof_state_effect="unknown",
        proof_state_changed=False,
    )
    assert metrics._action_was_accepted(contract_error) is False


def test_legacy_record_without_typed_outcome_still_excludes_reverted_no_op():
    legacy = {
        "label": "commit_tactic",
        "exit_code": 0,
        "agent_observation": {
            "manager_action": "commit_tactic",
            "result": (
                "NO PROGRESS — EasyCrypt ACCEPTED this commit but it did not "
                "change the goal, so nothing was committed (it auto-reverts)."
            ),
            "proof_state": "The committed EasyCrypt proof state was not changed.",
        },
    }
    assert metrics._action_was_accepted(legacy) is False
    legacy_accepted = {
        "label": "commit_tactic",
        "exit_code": 0,
        "agent_observation": {
            "manager_action": "commit_tactic",
            "result": "EasyCrypt accepted the committed tactic.",
            "proof_state": "The committed EasyCrypt proof state changed.",
        },
    }
    assert metrics._action_was_accepted(legacy_accepted) is True


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )


def _handled(node: str, action: dict, intent: str = "commit_tactic") -> dict:
    payload = {"tactic": "inline *."} if intent == "commit_tactic" else {}
    return {
        "kind": "agent_intent.handled",
        "node": node,
        "intent": {"intent": intent, "payload": payload},
        "manager_actions": [action],
    }


def _run(tmp_path: Path, records: list[dict], result: ProverResult) -> Path:
    run = tmp_path / "run"
    iteration = run / "iteration_1"
    _write_jsonl(iteration / "proof_node_manager_audit.jsonl", records)
    result.save(iteration / "prover_run_result.json")
    (run / "summary.json").write_text(json.dumps({
        "final_proved": result.is_verified,
        "final_prover_result_id": result.result_id,
        "final_prover_result_status": result.status,
    }), encoding="utf-8")
    (run / "config.json").write_text("{}", encoding="utf-8")
    return run


def test_run_metrics_count_commits_and_blind_runs_per_node(tmp_path):
    no_op = _commit_action("no_progress_reverted", ok=True, state_changed=False)
    undo = {"label": "undo_last_step", "exit_code": 0, "outcome_kind": "accepted"}
    records = [
        _handled("Tree-0.0", ACCEPTED),
        _handled("Tree-0.0", no_op),
        _handled("Tree-0.1", REJECTED),
        _handled("Tree-0.0", no_op),
        _handled("Tree-0.1", REJECTED),
        _handled("Tree-0.0", ACCEPTED),
        _handled("Tree-0.1", undo, intent="undo_last_step"),
    ]

    row = metrics.collect_run_metrics(
        _run(tmp_path, records, ProverResult(status=PROVER_RUN_INCOMPLETE))
    )

    assert row["main"]["commit_attempts"] == 6
    assert row["main"]["accepted_commits"] == 2
    assert row["main"]["failed_commit_tactics"] == 4
    assert row["navigator"]["best_prefix_depth"] == 2
    # Tree-0.0 failed twice in a row and Tree-0.1 failed twice in a row; the
    # interleaving must not splice them into one four-turn spike.
    assert row["diagnostics"]["blind_retry_spike_count"] == 2
    assert row["diagnostics"]["max_blind_retry_spike_length"] == 2
    assert row["diagnostics"]["blind_retry_turns"] == 4
    assert row["search"]["max_node_failed_turns"] == 2
    assert row["main"]["final_proof_length"] is None


def test_final_proof_length_is_the_verified_candidate_history(tmp_path):
    # Seven accepted commit turns, two of them later undone: the verified
    # proof has five tactics, not seven.
    records = [_handled("Tree-0.0", ACCEPTED) for _ in range(7)]
    verified = ProverResult(
        status=PROVER_RUN_VERIFIED,
        verification={"status": "pass", "method": "test_fixture"},
        completion_candidate={"candidate_id": "c", "tactic_count": 5},
    )

    row = metrics.collect_run_metrics(_run(tmp_path, records, verified))

    assert row["navigator"]["best_prefix_depth"] == 7
    assert row["main"]["final_proof_length"] == 5

    precheck_verified = ProverResult(
        status=PROVER_RUN_VERIFIED,
        verification={"status": "pass", "method": "precheck"},
    )
    assert metrics._verified_proof_length(precheck_verified) is None
