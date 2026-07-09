"""Tests for the trace replay battery summary helper."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from workflow.validation.trace_replay_battery import (  # noqa: E402
    BatteryCase,
    parse_case,
    summarize_case,
    summarize_rows,
)


def _ts(t0: datetime, mins: float) -> str:
    return (t0 + timedelta(minutes=mins)).isoformat() + "+00:00"


def _write_trace(path: Path) -> None:
    t0 = datetime(2026, 1, 1, 0, 0, 0)
    lines = [
        json.dumps({
            "type": "assistant",
            "timestamp": _ts(t0, 0),
            "message": {
                "content": [
                    {"type": "thinking", "thinking": "Try current layer."},
                    {
                        "type": "tool_use",
                        "id": "tool_1",
                        "name": "Bash",
                        "input": {
                            "command": (
                                "python3 core/easycrypt/session_cli.py "
                                "-d s -next -c 'proc.'"
                            )
                        },
                    },
                ]
            },
        }),
        json.dumps({
            "type": "user",
            "timestamp": _ts(t0, 0),
            "message": {
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "tool_1",
                        "content": "[STATE-DIFF] verdict=PROGRESS\n1 tactics accepted",
                    }
                ]
            },
        }),
        json.dumps({
            "type": "assistant",
            "timestamp": _ts(t0, 2),
            "message": {
                "content": [
                    {"type": "thinking", "thinking": "Inspect before acting."},
                    {
                        "type": "tool_use",
                        "id": "tool_2",
                        "name": "Bash",
                        "input": {
                            "command": (
                                "python3 core/easycrypt/session_cli.py "
                                "-d s -search equ_cc"
                            )
                        },
                    },
                ]
            },
        }),
        json.dumps({
            "type": "user",
            "timestamp": _ts(t0, 2),
            "message": {
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "tool_2",
                        "content": "no matches",
                    }
                ]
            },
        }),
    ]
    path.write_text("\n".join(lines))


def test_parse_case() -> None:
    assert parse_case("step3|claude_jsonl|trace.jsonl|equ_cc") == BatteryCase(
        label="step3",
        kind="claude_jsonl",
        path="trace.jsonl",
        focus="equ_cc",
    )


def test_parse_case_rejects_incomplete_item() -> None:
    try:
        parse_case("step3|claude_jsonl")
    except argparse.ArgumentTypeError as err:
        assert "LABEL|KIND|PATH" in str(err)
    else:
        raise AssertionError("expected argparse.ArgumentTypeError")


def test_summarize_claude_jsonl_case(tmp_path: Path) -> None:
    trace = tmp_path / "trace.jsonl"
    _write_trace(trace)

    row = summarize_case(BatteryCase("trace", "claude_jsonl", str(trace)))

    assert row["status"] == "ok"
    assert row["thinking_blocks"] == 2
    assert row["tool_breakdown"]["-next"] == 1
    assert row["tool_breakdown"]["-search"] == 1
    assert "min" in row["short_summary"]


def test_summarize_replay_report_case(tmp_path: Path) -> None:
    report = tmp_path / "report.json"
    report.write_text(json.dumps({
        "summary": {
            "accepted_steps": 12,
            "missing_view_alignments": 3,
            "missing_absent": 1,
            "missing_bucket_only": 2,
            "missing_by_bucket": {"procedure_control": 2},
            "lint_errors": 0,
        }
    }))

    row = summarize_case(BatteryCase("route", "route_report", str(report)))

    assert row["accepted_steps"] == 12
    assert row["missing_view_alignments"] == 3
    assert row["missing_absent"] == 1
    assert row["attention_score"] == 5.5


def test_summarize_rows_orders_attention() -> None:
    rows = [
        {"label": "a", "kind": "route_report", "status": "ok", "attention_score": 1},
        {"label": "b", "kind": "claude_jsonl", "status": "ok", "attention_score": 7},
        {"label": "c", "kind": "route_report", "status": "missing", "attention_score": 1000},
    ]

    summary = summarize_rows(rows)

    assert summary["case_count"] == 3
    assert summary["present_cases"] == 2
    assert summary["missing_cases"] == 1
    assert summary["top_attention"][0]["label"] == "c"
