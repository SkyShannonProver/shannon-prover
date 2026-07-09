#!/usr/bin/env python3
"""Regression: a successful commit must not be mislabeled "rejected".

Bug (2026-05-30, chachapoly step3 run): once a committed tactic decomposed the
goal into multiple subgoals (e.g. `call (_: inv ...)`), every following commit
was reported to the agent as "EasyCrypt rejected the committed tactic" even
though the proof state genuinely advanced. The agent_observation was internally
contradictory — `result` said rejected while `effect` said "accepted a
proof-state change".

Root cause: `_agent_observation_from_command` derived the commit verdict from
`_extract_json_object(stdout)` (the FIRST decodable JSON in the multi-section
`-next` stdout). On a multi-goal commit an earlier daemon-verify/AUTO-PIVOT
phase emission (carrying its own `ok: false`) decodes first, so the verdict read
that instead of the authoritative `[TACTIC-EXECUTION-RESULT]` block.

Fix: for `commit_tactic`, read the `[TACTIC-EXECUTION-RESULT]` payload by name.

Pure: no EasyCrypt needed.

Run: python3 -m pytest tests/test_commit_verdict_authoritative.py -q
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from workflow.proof_management.backend_actions import (  # noqa: E402
    agent_observation_from_command as _agent_observation_from_command,
)

_CMD = [
    "python3", "session_cli.py", "-d", ".ec_session_prover_tree_0_0",
    "-next", "-c", "call (_: inv ...).",
]


def _ter_block(*, result_ok: bool, status: str) -> str:
    """The authoritative TER stdout block emitted by the backend."""
    delivery = {
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
        "inspect_handles": {},
    }
    return "[TACTIC-EXECUTION-RESULT]\n" + json.dumps(
        delivery, separators=(",", ":")) + "\n"


# An earlier daemon-verify/AUTO-PIVOT-style emission that decodes first and used
# to hijack the verdict: it carries an execution block AND its own ok:false.
_EARLIER_VERIFY_EMISSION = json.dumps({
    "ok": False,
    "execution": {"state_changed": True, "history_committed": True},
    "result": {"ok": False, "status": "needs_intermediate"},
})


def _commit_stdout(*, result_ok: bool, status: str) -> str:
    return (
        "\n[AUTO-PIVOT] probability-route analysis\n"
        f"{_EARLIER_VERIFY_EMISSION}\n"
        "[LEGACY-OUTPUT]\n"
        "Current goal (remaining: 3)\n&m: {}\n----\n"
        + _ter_block(result_ok=result_ok, status=status)
    )


def test_successful_multigoal_commit_reads_as_accepted():
    stdout = _commit_stdout(result_ok=True, status="ok")
    obs = _agent_observation_from_command(
        "commit_tactic", _CMD, stdout=stdout, stderr="", exit_code=0,
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
    stdout = (
        "[LEGACY-OUTPUT]\nsome text {}\n"
        "[TACTIC-EXECUTION-RESULT]\n"
        + json.dumps(delivery, separators=(",", ":")) + "\n"
    )
    obs = _agent_observation_from_command(
        "commit_tactic",
        ["python3", "session_cli.py", "-d", "x", "-next", "-c", "bogus_tac."],
        stdout=stdout, stderr="", exit_code=0,
    )
    assert "rejected the committed tactic" in obs["result"], obs["result"]


def test_falls_back_when_marker_absent():
    # No TER marker (defensive): fall back to first-JSON heuristic. A bare ok
    # payload should still yield a sane verdict, not crash.
    stdout = json.dumps({
        "ok": True,
        "result": {"ok": True, "status": "ok"},
        "execution": {"state_changed": True, "history_committed": True},
    })
    obs = _agent_observation_from_command(
        "commit_tactic", _CMD, stdout=stdout, stderr="", exit_code=0,
    )
    assert "accepted the committed tactic" in obs["result"], obs["result"]
