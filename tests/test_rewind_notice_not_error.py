#!/usr/bin/env python3
"""Regression: a SUCCESSFUL rewind/restart must not surface as a manager_error.

Bug (found 2026-05-30 auditing the step4 bad1_lbad1 resume runs): an
`undo_to_checkpoint` is implemented as restart+replay-prefix. The restart
(`-start --force-restart`) writes an INFORMATIONAL notice to stderr
("[session_cli] Restart #N: discarding K committed tactic(s) … Proceeding with
fresh session") and exits 0. `_error_summary` promoted ANY non-empty stderr to
`error_summary`, so a successful rewind handed the agent an `error_summary`
claiming its committed work was discarded — surfaced downstream as a
`manager_error` deterministic signal on an operation that in fact succeeded
exactly as asked. That is the framework misleading the agent.

Fix: the raw-stderr fallback fires ONLY when the action FAILED. Structured proof
errors (raw_excerpt / errors list) are still read regardless of status, so a
genuine probe rejection / failure keeps its detail.

Pure: no EasyCrypt needed.
Run: python3 -m pytest tests/test_rewind_notice_not_error.py -q
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from workflow.proof_management.backend_actions import (  # noqa: E402
    agent_observation_from_command,
)

_RESTART_NOTICE = (
    "[session_cli] Restart #2: discarding 101 committed tactic(s).\n"
    "  The 101 prior tactics are saved to a checkpoint file (see RESTART-NOTICE "
    "below) in case you decide to replay. Proceeding with fresh session.\n"
)
_REWIND_CMD = [
    "python3", "session_cli.py", "-d", "x",
    "-start", "--force-restart", "-f", "f.ec", "-lemma", "L",
]


def test_successful_rewind_restart_notice_is_not_an_error():
    # exit 0 + informational stderr -> NO error_summary surfaced to the agent.
    obs = agent_observation_from_command(
        "undo_to_checkpoint", _REWIND_CMD,
        stdout="", stderr=_RESTART_NOTICE, exit_code=0,
    )
    assert "error_summary" not in obs, obs.get("error_summary")


def test_failed_action_still_surfaces_stderr_error():
    # A genuine failure (nonzero exit) must STILL surface its stderr as an error.
    obs = agent_observation_from_command(
        "commit_tactic",
        ["python3", "session_cli.py", "-d", "x", "-next", "-c", "bogus."],
        stdout="", stderr="Fatal error: exception Invalid_argument\n",
        exit_code=1,
    )
    assert "error_summary" in obs
    assert "Fatal error" in obs["error_summary"]


def test_probe_rejection_detail_still_surfaces_from_raw_excerpt():
    # A probe rejection is ok=False but its detail lives in raw_excerpt, read
    # regardless of the stderr gate — so the agent still sees WHY it failed.
    import json
    delivery = {
        "execution": {"mode": "try", "submitted_tactics": ["smt()."]},
        "result": {"ok": False, "status": "probe_rejected",
                   "raw_excerpt": "[TRY] error: cannot prove goal (strict)"},
    }
    stdout = "[TACTIC-EXECUTION-RESULT]\n" + json.dumps(delivery) + "\n"
    obs = agent_observation_from_command(
        "probe_tactic",
        ["python3", "session_cli.py", "-d", "x", "-try", "-c", "smt()."],
        stdout=stdout, stderr="", exit_code=0,
    )
    assert "error_summary" in obs
    assert "cannot prove goal" in obs["error_summary"]
