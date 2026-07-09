#!/usr/bin/env python3
"""`inspect_context diagnose` must be probe-aware.

The backend diagnose reads the COMMITTED session only; a read-only probe runs in
an ephemeral process and never touches it, so after a failed probe the committed
diagnosis is empty ("No errors found"). The manager must surface the last
read-only probe's own EasyCrypt error so the probe->diagnose loop is not blind.

Regression for an eager-while finding on a held-out MAC corpus run (probe
parse-errors invisible to diagnose), and for the de-KB'd diagnose (no
shell/apostrophe boilerplate).

Run: python3 -m pytest tests/test_diagnose_probe_aware.py -q
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from workflow.proof_node_manager import ProofNodeManager  # noqa: E402
from workflow.proof_management.protocol_repair import AgentIntent  # noqa: E402
from workflow.proof_management.types import ManagedTurn  # noqa: E402


class _FakeTurns:
    def repl_call(self, intent, fn):  # noqa: ANN001
        # The committed-session diagnose finds nothing (probe never touched it).
        return ManagedTurn(
            ok=True,
            workspace_view={},
            manager_actions=[{
                "label": "inspect_diagnose",
                "agent_observation": "No errors found in current session output.",
            }],
        )


class _FakeRepl:
    def handle_intent(self, intent):  # noqa: ANN001
        return None


class _FakeEvents:
    def __init__(self, probe):
        self._probe = probe

    def latest_readonly_probe_event(self):
        return self._probe


class _FakeMgr:
    """Minimal stand-in exposing only what _handle_inspect_diagnose touches."""

    def __init__(self, probe):
        self.turns = _FakeTurns()
        self.repl = _FakeRepl()
        self.events = _FakeEvents(probe)
        self.latest_view = {"current_goal": {"lines": ["pre = ...", "while c {..} ~ while c {..}"]}}


def _diagnose(probe):
    intent = AgentIntent(intent="inspect_context", payload={"topic": "diagnose"})
    turn = ProofNodeManager._handle_inspect_diagnose(_FakeMgr(probe), intent)
    return turn.manager_actions[0]["agent_observation"]


def test_diagnose_surfaces_last_probe_error() -> None:
    obs = _diagnose({
        "intent": "probe_tactic",
        "tactic": "eager while (h: S1 ~ S2 : pre ==> post).",
        "error_summary": "parse error",
        "changed": False,
    })
    # committed diagnosis is preserved
    assert "No errors found" in obs
    # the probe's own error is now surfaced (the blind spot is fixed)
    assert "Last read-only probe" in obs
    assert "parse error" in obs
    assert "eager while" in obs
    # and it is diagnosed with the hardcoded parse-error FACT (not KB shell boilerplate)
    assert ("did not parse" in obs) or ("fix the FORM" in obs)
    assert "session_cli strips" not in obs  # no MCP-irrelevant shell/apostrophe pseudo-cause
    assert "apostrophe in a primed" not in obs


def test_diagnose_unchanged_when_no_recent_probe() -> None:
    # No read-only probe failure pending -> diagnose result is untouched.
    obs = _diagnose({})
    assert obs == "No errors found in current session output."


def test_diagnose_unchanged_when_probe_had_no_error() -> None:
    # An accepted probe (no error_summary) must not trigger the augmentation.
    obs = _diagnose({"intent": "probe_tactic", "tactic": "auto.", "error_summary": "", "changed": False})
    assert obs == "No errors found in current session output."


def test_diagnose_tool_error_is_not_labelled_ec_rejection() -> None:
    # A probe that failed at the HARNESS/daemon layer must NOT be reported as an
    # EasyCrypt rejection — that would tell the agent its tactic is wrong when EC
    # never ruled on it (panel audit: diagnose harness-vs-EC).
    obs = _diagnose({
        "intent": "probe_tactic",
        "tactic": "probe while{2}.",
        "kind": "probe_tool_error",
        "error_summary": "probe tool failed: could not sync daemon",
        "changed": False,
    })
    assert "Last read-only probe" in obs
    assert "probe TOOL failed" in obs and "NOT an EasyCrypt rejection" in obs
    assert "EasyCrypt rejected the probe" not in obs   # must NOT mislabel as an EC rejection


if __name__ == "__main__":
    test_diagnose_surfaces_last_probe_error()
    test_diagnose_unchanged_when_no_recent_probe()
    test_diagnose_unchanged_when_probe_had_no_error()
    test_diagnose_tool_error_is_not_labelled_ec_rejection()
    print("PASS test_diagnose_probe_aware")
