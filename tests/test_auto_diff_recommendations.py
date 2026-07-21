"""Tests for legacy AUTO-DIFF recommendation contracts."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

from core.easycrypt.session_hook_phases import AutoDiffPhase  # noqa: E402


def test_auto_diff_unverified_call_is_structural_hint_only() -> None:
    phase = AutoDiffPhase(session=object())

    recs = phase._diff_recommendations(
        "[AUTO-DIFF]\n  aligned call: `call equ_cc.`\n  suffix: `wp.`",
        call_ready=set(),
    )
    by_action = {item["action"]: item for item in recs}

    assert by_action["call equ_cc."]["action_type"] == "strategy_hint"
    assert by_action["call equ_cc."]["metadata"]["epistemic_status"] == (
        "static_call_alignment_not_frontier_verified"
    )
    assert by_action["wp."]["action_type"] == "tactic_candidate"


def test_auto_diff_daemon_ready_call_remains_runnable() -> None:
    phase = AutoDiffPhase(session=object())

    recs = phase._diff_recommendations(
        "[AUTO-DIFF]\n  aligned call: `call equ_cc.`",
        call_ready={"equ_cc"},
    )

    assert recs[0]["action"] == "call equ_cc."
    assert recs[0]["action_type"] == "runnable_tactic"
    assert recs[0]["confidence"] == "verified"
