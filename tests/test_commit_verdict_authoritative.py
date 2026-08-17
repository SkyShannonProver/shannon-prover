#!/usr/bin/env python3
"""Regression: a successful commit must not be mislabeled "rejected".

Bug (2026-05-30, chachapoly step3 run): once a committed tactic decomposed the
goal into multiple subgoals (e.g. `call (_: inv ...)`), every following commit
was reported to the agent as "EasyCrypt rejected the committed tactic" even
though the proof state genuinely advanced. The agent_observation was internally
contradictory — `result` said rejected while `effect` said "accepted a
proof-state change".

The current fix reads only the event-bound TacticExecutionResult artifact;
stdout emissions cannot participate in the verdict.

Pure: no EasyCrypt needed.

Run: python3 -m pytest tests/test_commit_verdict_authoritative.py -q
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from workflow.proof_management.backend_actions import (  # noqa: E402
    _TacticExecutionResolution,
    agent_observation_from_command,
)

_CMD = [
    "python3", "session_cli.py", "-d", ".ec_session_prover_tree_0_0",
    "-tactic-exec", "commit", "-c", "call (_: inv ...).",
]


def _ter_result(*, result_ok: bool, status: str) -> dict:
    return {
        "ok": result_ok,
        "execution": {
            "mode": "commit",
            "state_changed": True,
            "history_committed": True,
            "submitted_tactics": ["call (_: inv ...)."],
        },
        "result": {
            "ok": result_ok,
            "status": status,
            "raw_excerpt": "[STATE-DIFF] verdict=PROGRESS\n...goal...",
        },
        "workspace": {},
    }


def test_successful_multigoal_commit_reads_as_accepted():
    result = _ter_result(result_ok=True, status="ok")
    obs = agent_observation_from_command(
        "commit_tactic",
        _CMD,
        stdout='{"ok":false,"result":{"status":"error"}}',
        stderr="",
        exit_code=0,
        tactic_execution_resolution=_TacticExecutionResolution(
            required=True,
            result=result,
        ),
    )
    assert "accepted the committed tactic" in obs["result"], obs["result"]
    assert "rejected" not in obs["result"].lower()
    # effect/proof_state stay consistent with the verdict.
    assert "accepted a proof-state change" in obs["effect"]
    assert "changed" in obs["proof_state"]


def test_genuinely_failed_commit_still_reads_as_rejected():
    # If the authoritative TER reports failure, the verdict must be rejected.
    delivery = {
        "execution": {
            "mode": "commit",
            "state_changed": False,
            "history_committed": False,
            "submitted_tactics": ["bogus_tac."],
        },
        "result": {
            "ok": False,
            "status": "failed",
            "raw_excerpt": "[TRY] error: unknown tactic",
        },
    }
    obs = agent_observation_from_command(
        "commit_tactic",
        [
            "python3", "session_cli.py", "-d", "x",
            "-tactic-exec", "commit", "-c", "bogus_tac.",
        ],
        stdout='{"ok":true,"result":{"status":"ok"}}',
        stderr="",
        exit_code=0,
        tactic_execution_resolution=_TacticExecutionResolution(
            required=True,
            result=delivery,
        ),
    )
    assert "rejected the committed tactic" in obs["result"], obs["result"]


def test_missing_bound_result_is_a_backend_contract_error():
    stdout = '{"ok":true,"result":{"ok":true,"status":"ok"}}'
    obs = agent_observation_from_command(
        "commit_tactic", _CMD, stdout=stdout, stderr="", exit_code=0,
    )
    assert "violated the manager contract" in obs["result"]
    assert "Missing required event-bound TacticExecutionResult" in obs["contract_error"]
    assert "accepted" not in obs["result"].lower()
