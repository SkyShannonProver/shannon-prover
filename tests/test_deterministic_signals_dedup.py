#!/usr/bin/env python3
"""Regression: a single handled error must yield ONE `manager_error:` signal.

Bug (found 2026-05-30 auditing the step4 resume timelines): one error was
emitted as two identical `manager_error:` deterministic signals, because the
same handled action reaches `_deterministic_signals` from both `manager_actions`
and the `audit_manager_actions` union (and via both the action-level and the
agent_observation-level `error_summary`). The double-count misreads as two
distinct failures during audit. Fix: dedupe signals preserving order.

Pure. Run: python3 -m pytest tests/test_deterministic_signals_dedup.py -q
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from workflow.validation.agent_view_timeline_report import (  # noqa: E402
    _deterministic_signals,
)


def test_same_error_in_both_action_lists_is_one_signal():
    action = {"agent_observation": {"error_summary": "boom"}}
    sigs = _deterministic_signals(
        intent={"intent": "undo_to_checkpoint"},
        manager_actions=[action],
        audit_manager_actions=[action],   # same handled action in the audit union
        workspace_view={},
    )
    assert sigs.count("manager_error:boom") == 1, sigs


def test_action_level_and_observation_level_same_error_is_one_signal():
    action = {"error_summary": "x", "agent_observation": {"error_summary": "x"}}
    sigs = _deterministic_signals(
        intent={"intent": "probe_tactic"},
        manager_actions=[action],
        audit_manager_actions=None,
        workspace_view={},
    )
    assert sigs.count("manager_error:x") == 1, sigs


def test_distinct_errors_are_all_kept():
    sigs = _deterministic_signals(
        intent={"intent": "probe_tactic"},
        manager_actions=[{"agent_observation": {"error_summary": "e1"}},
                         {"agent_observation": {"error_summary": "e2"}}],
        audit_manager_actions=[],
        workspace_view={},
    )
    assert "manager_error:e1" in sigs and "manager_error:e2" in sigs
