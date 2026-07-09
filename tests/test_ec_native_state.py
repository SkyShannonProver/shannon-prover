"""Tests for EC-native vs Shannon-adapter state provenance."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from core.easycrypt.analysis.ec_native_state import (  # noqa: E402
    load_native_goal_fact,
    load_native_program_fact,
)


def test_goal_json_adapter_is_not_treated_as_ec_native() -> None:
    with tempfile.TemporaryDirectory() as td:
        session = Path(td)
        tool_views = session / "tool_views"
        tool_views.mkdir()
        (tool_views / "goal_adapter.json").write_text(
            json.dumps({
                "tool": "goal-json",
                "goal_state": {
                    "goal_type": "phoare",
                    "fact_source": "pretty_goal_text",
                    "authority": "pretty_text_fallback",
                    "ec_ground_truth": False,
                },
            }),
            encoding="utf-8",
        )

        assert load_native_goal_fact(session) == {}


def test_program_json_adapter_is_not_treated_as_ec_native() -> None:
    with tempfile.TemporaryDirectory() as td:
        session = Path(td)
        tool_views = session / "tool_views"
        tool_views.mkdir()
        (tool_views / "program_adapter.json").write_text(
            json.dumps({
                "tool": "program-json",
                "program": {
                    "left_statements": [{
                        "type": "CALL",
                        "procedure": "M.f",
                    }],
                    "program_fact_source": "pretty_program_text",
                    "program_authority": "pretty_text_fallback",
                    "program_ec_ground_truth": False,
                },
            }),
            encoding="utf-8",
        )

        assert load_native_program_fact(session) == {}


def test_ec_goal_json_artifact_is_ground_truth() -> None:
    with tempfile.TemporaryDirectory() as td:
        session = Path(td)
        tool_views = session / "tool_views"
        tool_views.mkdir()
        (tool_views / "native_goal.json").write_text(
            json.dumps({
                "tool": "ec-goal-json",
                "goal_state": {
                    "goal_type": "phoare",
                    "num_remaining": 2,
                    "active_goal_hash": "abc",
                },
            }),
            encoding="utf-8",
        )

        fact = load_native_goal_fact(session, active_goal_hash="abc")

    assert fact["goal_type"] == "phoare"
    assert fact["num_remaining"] == 2
    assert fact["fact_source"] == "ec_native_goal_state"
    assert fact["authority"] == "ec_native_ground_truth"
    assert fact["ec_ground_truth"] is True


def test_ec_program_json_artifact_is_ground_truth() -> None:
    with tempfile.TemporaryDirectory() as td:
        session = Path(td)
        tool_views = session / "tool_views"
        tool_views.mkdir()
        (tool_views / "native_program.json").write_text(
            json.dumps({
                "tool": "ec-program-json",
                "program": {
                    "active_goal_hash": "abc",
                    "left_statements": [{
                        "type": "CALL",
                        "procedure": "Native.f",
                    }],
                    "right_statements": [],
                },
            }),
            encoding="utf-8",
        )

        fact = load_native_program_fact(session, active_goal_hash="abc")

    assert fact["left_statements"][0]["procedure"] == "Native.f"
    assert fact["fact_source"] == "ec_native_program_ast"
    assert fact["authority"] == "ec_native_ground_truth"
    assert fact["ec_ground_truth"] is True


def test_native_artifact_with_stale_goal_hash_is_ignored() -> None:
    with tempfile.TemporaryDirectory() as td:
        session = Path(td)
        tool_views = session / "tool_views"
        tool_views.mkdir()
        (tool_views / "stale_native_goal.json").write_text(
            json.dumps({
                "tool": "ec-goal-json",
                "goal_state": {
                    "goal_type": "phoare",
                    "active_goal_hash": "old",
                },
            }),
            encoding="utf-8",
        )

        assert load_native_goal_fact(session, active_goal_hash="new") == {}
