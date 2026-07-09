"""Summarize fixed trace-replay evidence across prover runs.

This is a read-only calibration harness.  It does not run EasyCrypt and it is
not part of the prover/compiler path.  The goal is to keep old failure traces,
current route-replay reports, and human-proof replay reports in one small
battery so surface/frontend changes can be audited against the same evidence.
"""
from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from core.easycrypt.audit.summary import summarize_run


_PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class BatteryCase:
    label: str
    kind: str
    path: str
    focus: str = ""


_DEFAULT_CASES: tuple[BatteryCase, ...] = (
    BatteryCase(
        label="step3-drive-correct-a",
        kind="claude_jsonl",
        path=(
            "artifacts/drive_traces/correct_extracted/artifacts/"
            "correct_trace_upload_2026-05-03/step3/claude_project/"
            "5edc0985-0afc-4d27-982f-b2f2ac360479.jsonl"
        ),
        focus="early inline drift, equ_cc frontier search, raw-goal fallback",
    ),
    BatteryCase(
        label="step3-drive-correct-b",
        kind="claude_jsonl",
        path=(
            "artifacts/drive_traces/correct_extracted/artifacts/"
            "correct_trace_upload_2026-05-03/step3/claude_project/"
            "9b248992-2edf-4df8-a082-364dc62fde40.jsonl"
        ),
        focus="long step3 route through rcond/rnd residue after equ_cc",
    ),
    BatteryCase(
        label="step3-upload-trace",
        kind="claude_jsonl",
        path=(
            "artifacts/drive_traces/extracted/artifacts/"
            "trace_upload_2026-05-03/claude_traces/"
            "step3_0ddc66f1-1010-4627-8a54-a747db884d14.jsonl"
        ),
        focus="graded G8/G6/G4 route and premature inline descent",
    ),
    BatteryCase(
        label="step1-current-route",
        kind="route_report",
        path=(
            "artifacts/proof_route_replay_current_view/"
            "step1_old_route_current_20260509-120103/route_replay_report.json"
        ),
        focus="current view on old step1 route",
    ),
    BatteryCase(
        label="step3-current-route",
        kind="route_report",
        path=(
            "artifacts/proof_route_replay_current_view/"
            "overnight_routes_current_20260509-115951/"
            "step3_20260509_tree_0_0/route_replay_report.json"
        ),
        focus="current view at seq/equ_cc/rcond frontiers",
    ),
    BatteryCase(
        label="step4-badi-current-route",
        kind="route_report",
        path=(
            "artifacts/proof_route_replay_current_view/"
            "overnight_routes_current_20260509-115951/"
            "step4_badi_20260509_tree_0_0_1/route_replay_report.json"
        ),
        focus="bad-event procedure control-flow and weak cut hints",
    ),
    BatteryCase(
        label="mee-ctxt-current-view",
        kind="view_replay_report",
        path="artifacts/proof_view_replay/current_pr_bridge_batch/MEE-CBC_CTXT_security/report.json",
        focus="MEE CTXT wrapper oracle, one-sided call, bad-event map",
    ),
    BatteryCase(
        label="mee-bound-prp-prf-current-view",
        kind="view_replay_report",
        path="artifacts/proof_view_replay/current_pr_bridge_batch/MEE-CBC_Bound_by_PRP_PRF/report.json",
        focus="successful MEE clone/Pr bridge and query-bound invariant",
    ),
    BatteryCase(
        label="mee-cbc-security-current-view",
        kind="view_replay_report",
        path="artifacts/proof_view_replay/post_arch_replay_mee_preset_smoke/MEE-CBC_CBC_security/report.json",
        focus="MEE CBC control-flow, rcond, while, wrapper alignment",
    ),
    BatteryCase(
        label="mee-cbc-upto-current-view",
        kind="view_replay_report",
        path="artifacts/proof_view_replay/current_pr_bridge_batch/MEE-CBC_CBC_upto/report.json",
        focus="MEE CBC upto invariant/control-flow current-view replay",
    ),
)


def parse_case(raw: str) -> BatteryCase:
    """Parse ``LABEL|KIND|PATH|FOCUS`` command-line case specs."""
    parts = [part.strip() for part in raw.split("|")]
    if len(parts) not in {3, 4} or not all(parts[:3]):
        raise argparse.ArgumentTypeError(
            "case must have form LABEL|KIND|PATH or LABEL|KIND|PATH|FOCUS"
        )
    return BatteryCase(
        label=parts[0],
        kind=parts[1],
        path=parts[2],
        focus=parts[3] if len(parts) == 4 else "",
    )


def default_cases() -> list[BatteryCase]:
    return list(_DEFAULT_CASES)


def summarize_cases(cases: Iterable[BatteryCase]) -> list[dict[str, Any]]:
    return [summarize_case(case) for case in cases]


def summarize_case(case: BatteryCase) -> dict[str, Any]:
    path = _resolve_path(case.path)
    row: dict[str, Any] = {
        "label": case.label,
        "kind": case.kind,
        "path": str(path),
        "focus": case.focus,
        "status": "ok" if path.exists() else "missing",
    }
    if not path.exists():
        row["attention_score"] = 1000
        row["notes"] = ["artifact missing"]
        return row

    if case.kind == "claude_jsonl":
        row.update(_summarize_claude_jsonl(path))
    elif case.kind in {"route_report", "view_replay_report"}:
        row.update(_summarize_replay_report(path))
    elif case.kind == "markdown_report":
        row.update(_summarize_markdown_report(path))
    else:
        row["status"] = "unknown_kind"
        row["attention_score"] = 1000
        row["notes"] = [f"unknown kind: {case.kind}"]
    return row


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    present = [row for row in rows if row.get("status") == "ok"]
    missing = [row for row in rows if row.get("status") == "missing"]
    return {
        "case_count": len(rows),
        "present_cases": len(present),
        "missing_cases": len(missing),
        "total_missing_view_alignments": sum(
            int(row.get("missing_view_alignments") or 0) for row in present
        ),
        "total_stuck_minutes": round(
            sum(float(row.get("stuck_minutes") or 0.0) for row in present),
            2,
        ),
        "top_attention": [
            {
                "label": row.get("label"),
                "kind": row.get("kind"),
                "attention_score": row.get("attention_score"),
                "focus": row.get("focus"),
                "summary": row.get("short_summary"),
            }
            for row in sorted(
                rows,
                key=lambda item: float(item.get("attention_score") or 0.0),
                reverse=True,
            )[:8]
        ],
    }


def write_outputs(rows: list[dict[str, Any]], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "summary": summarize_rows(rows),
        "cases": rows,
    }
    (out_dir / "trace_battery_summary.json").write_text(
        json.dumps(payload, indent=2),
        encoding="utf-8",
    )
    (out_dir / "trace_battery_summary.md").write_text(
        _format_markdown(payload),
        encoding="utf-8",
    )


def _summarize_claude_jsonl(path: Path) -> dict[str, Any]:
    summary = summarize_run(path)
    stuck_minutes = sum(window.duration_min for window in summary.stuck_windows)
    search_calls = (
        int(summary.tool_breakdown.get("-search") or 0)
        + int(summary.tool_breakdown.get("-search-skeleton") or 0)
    )
    try_calls = int(summary.tool_breakdown.get("-try") or 0)
    row = {
        "wall_minutes": round(summary.wall_minutes, 2),
        "thinking_blocks": summary.total_thinking_blocks,
        "tool_calls": summary.total_tool_calls,
        "bash_calls": summary.total_bash_calls,
        "stuck_minutes": round(stuck_minutes, 2),
        "stuck_windows": [
            {
                "kind": window.kind,
                "start_step": window.start_step,
                "end_step": window.end_step,
                "duration_min": round(window.duration_min, 2),
                "evidence": window.evidence[:2],
            }
            for window in summary.stuck_windows[:5]
        ],
        "tool_breakdown": dict(sorted(summary.tool_breakdown.items())),
        "hook_counts": dict(sorted(summary.hook_counts.items())),
        "attention_score": round(stuck_minutes + 0.1 * search_calls + 0.05 * try_calls, 2),
    }
    row["short_summary"] = (
        f"{summary.wall_minutes:.1f} min, {summary.total_thinking_blocks} thinking "
        f"blocks, {stuck_minutes:.1f} stuck min"
    )
    return row


def _summarize_replay_report(path: Path) -> dict[str, Any]:
    report = _read_json(path)
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else report
    missing = int(summary.get("missing_view_alignments") or 0)
    missing_absent = int(summary.get("missing_absent") or 0)
    missing_bucket_only = int(summary.get("missing_bucket_only") or 0)
    accepted = int(summary.get("accepted_steps") or 0)
    missing_examples = list(summary.get("missing_examples") or [])[:6]
    row = {
        "accepted_steps": accepted,
        "total_steps": int(summary.get("total_steps") or accepted),
        "missing_view_alignments": missing,
        "missing_absent": missing_absent,
        "missing_bucket_only": missing_bucket_only,
        "missing_by_bucket": summary.get("missing_by_bucket") or {},
        "steps_by_bucket": summary.get("steps_by_bucket") or {},
        "missing_examples": missing_examples,
        "lint_errors": int(summary.get("lint_errors") or 0),
        "attention_score": missing + (2 * missing_absent) + (0.25 * missing_bucket_only),
    }
    row["short_summary"] = (
        f"{accepted} accepted steps, {missing} missing view alignments "
        f"({missing_absent} absent)"
    )
    return row


def _summarize_markdown_report(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    headings = [line.strip("# ").strip() for line in text.splitlines() if line.startswith("#")]
    return {
        "line_count": len(text.splitlines()),
        "heading_count": len(headings),
        "headings": headings[:12],
        "attention_score": 0,
        "short_summary": f"{len(text.splitlines())} report lines, {len(headings)} headings",
    }


def _read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _resolve_path(raw: str) -> Path:
    path = Path(os.path.expanduser(raw))
    if path.is_absolute():
        return path
    return _PROJECT_ROOT / path


def _format_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Trace Replay Battery",
        "",
        "Read-only summary of fixed trace and replay artifacts.",
        "",
        "## Summary",
        "",
        f"- cases: {summary['case_count']} ({summary['present_cases']} present, {summary['missing_cases']} missing)",
        f"- total stuck minutes in Claude traces: {summary['total_stuck_minutes']}",
        f"- total missing view alignments: {summary['total_missing_view_alignments']}",
        "",
        "## Top Attention",
        "",
    ]
    for item in summary["top_attention"]:
        lines.append(
            f"- `{item['label']}` [{item['kind']}]: score={item['attention_score']} - "
            f"{item.get('summary') or ''}"
        )
        if item.get("focus"):
            lines.append(f"  focus: {item['focus']}")
    lines.extend(["", "## Cases", ""])
    for row in payload["cases"]:
        lines.append(
            f"- `{row['label']}` [{row['kind']}] `{row['status']}`: "
            f"{row.get('short_summary') or ', '.join(row.get('notes') or [])}"
        )
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--case",
        action="append",
        type=parse_case,
        default=[],
        help="Case as LABEL|KIND|PATH or LABEL|KIND|PATH|FOCUS.",
    )
    parser.add_argument(
        "--default",
        action="store_true",
        help="Use the built-in step1/step3/step4/MEE battery.",
    )
    parser.add_argument("--out-dir", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true", help="Fail if any case is missing.")
    args = parser.parse_args(argv)

    cases = list(args.case)
    if args.default:
        cases.extend(default_cases())
    if not cases:
        parser.error("provide --default or at least one --case")

    rows = summarize_cases(cases)
    payload = {"summary": summarize_rows(rows), "cases": rows}
    if args.out_dir:
        write_outputs(rows, args.out_dir)
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(_format_markdown(payload))
    if args.strict and any(row.get("status") == "missing" for row in rows):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
