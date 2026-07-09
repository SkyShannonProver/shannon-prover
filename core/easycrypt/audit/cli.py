"""CLI entry-point: `python3 -m core.easycrypt.audit <jsonl> [--baseline <jsonl>]`.

Prints a structured human-readable report. For programmatic consumption
use `from core.easycrypt.audit import summarize_run` directly.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .summary import summarize_run
from .compare import compare_runs


def _format_run_report(s, max_timeline_rows: int = 30) -> str:
    """Compact text report of a single RunSummary."""
    lines: list[str] = []
    lines.append(f"=== Run summary: {s.session_id} ===")
    lines.append(f"  project   : {s.project_dir}")
    lines.append(f"  wall time : {s.wall_minutes:.1f} min")
    lines.append(f"  thinking  : {s.total_thinking_blocks} blocks")
    lines.append(f"  tool calls: {s.total_tool_calls} (bash: {s.total_bash_calls})")
    # Quick stuck headline (sum of all stuck-window durations, may
    # double-count overlapping windows of different kinds).
    total_stuck = sum(w.duration_min for w in s.stuck_windows)
    if s.stuck_windows:
        kinds = sorted({w.kind for w in s.stuck_windows})
        lines.append(
            f"  stuck     : {total_stuck:.1f} min total in "
            f"{len(s.stuck_windows)} window(s) [{', '.join(kinds)}]"
        )
    else:
        lines.append(f"  stuck     : 0.0 min (no windows)")

    lines.append("")
    lines.append("Tool breakdown (top 12):")
    sorted_tools = sorted(
        s.tool_breakdown.items(), key=lambda x: -x[1],
    )[:12]
    for flag, n in sorted_tools:
        lines.append(f"  {flag:<22} {n}")

    lines.append("")
    lines.append("Hook fire counts:")
    if s.hook_counts:
        sorted_hooks = sorted(s.hook_counts.items(), key=lambda x: -x[1])
        for marker, n in sorted_hooks:
            lines.append(f"  {marker:<32} {n}")
    else:
        lines.append("  (none fired)")

    lines.append("")
    lines.append(f"Stuck windows ({len(s.stuck_windows)}):")
    for w in s.stuck_windows:
        lines.append(
            f"  [{w.kind:<16}] step {w.start_step}–{w.end_step} "
            f"({w.start_t_min:.1f}–{w.end_t_min:.1f} min, "
            f"{w.duration_min:.1f} min)"
        )
        for ev in w.evidence[:2]:
            lines.append(f"      • {ev}")

    lines.append("")
    n_show = min(max_timeline_rows, len(s.timeline))
    lines.append(f"Timeline (first {n_show} steps):")
    lines.append(
        f"  {'STEP':<5}{'TIME':<7}{'ACTION':<55}{'SIGNAL':<22}"
        f"THINK"
    )
    for st in s.timeline[:n_show]:
        action = st.principal_action[:50] + (
            f" (+{st.aux_action_count})" if st.aux_action_count > 0 else ""
        )
        signal = st.principal_signal[:21]
        first = st.think_first_line[:60]
        lines.append(
            f"  {st.step_n:<5}{st.t_min:6.1f} {action:<55}{signal:<22}"
            f"{first}"
        )
    if len(s.timeline) > n_show:
        lines.append(f"  … ({len(s.timeline) - n_show} more steps)")

    return "\n".join(lines)


def _format_comparison(cmp_report) -> str:
    lines: list[str] = []
    lines.append("")
    lines.append(f"=== Comparison: {cmp_report.this_session} vs {cmp_report.baseline_session} ===")
    lines.append(f"  wall delta     : {cmp_report.wall_minutes_delta:+.1f} min")
    lines.append(f"  thinking delta : {cmp_report.thinking_blocks_delta:+d} blocks")
    lines.append(f"  tool calls Δ   : {cmp_report.tool_calls_delta:+d}")
    lines.append(f"  stuck mins Δ   : {cmp_report.stuck_minutes_delta:+.1f} min "
                 f"(this: {cmp_report.stuck_minutes_this:.1f}, "
                 f"baseline: {cmp_report.stuck_minutes_baseline:.1f})")

    if cmp_report.hooks_only_in_this:
        lines.append("")
        lines.append("Hooks fired ONLY in this run (new behavior):")
        for m in cmp_report.hooks_only_in_this:
            lines.append(f"  + {m}")
    if cmp_report.hooks_only_in_baseline:
        lines.append("")
        lines.append("Hooks fired ONLY in baseline (regression risk):")
        for m in cmp_report.hooks_only_in_baseline:
            lines.append(f"  - {m}")

    nonzero_deltas = {k: v for k, v in cmp_report.hook_count_deltas.items() if v != 0}
    if nonzero_deltas:
        lines.append("")
        lines.append("Hook count deltas (this - baseline):")
        for marker, delta in sorted(nonzero_deltas.items(), key=lambda x: abs(x[1]), reverse=True):
            sign = "+" if delta > 0 else ""
            lines.append(f"  {marker:<32} {sign}{delta}")

    nonzero_tool_deltas = {k: v for k, v in cmp_report.tool_count_deltas.items() if v != 0}
    if nonzero_tool_deltas:
        lines.append("")
        lines.append("Tool count deltas (this - baseline):")
        for flag, delta in sorted(nonzero_tool_deltas.items(), key=lambda x: abs(x[1]), reverse=True)[:10]:
            sign = "+" if delta > 0 else ""
            lines.append(f"  {flag:<22} {sign}{delta}")

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="audit",
        description="Analyze a Claude Code prover-session JSONL trace.",
    )
    p.add_argument("jsonl", type=Path, help="Path to session JSONL file")
    p.add_argument(
        "--baseline", type=Path, default=None,
        help="Optional second JSONL to compare against (--baseline X "
             "compares jsonl - X).",
    )
    p.add_argument(
        "--json", action="store_true",
        help="Emit machine-readable JSON instead of human-readable report.",
    )
    p.add_argument(
        "--timeline-rows", type=int, default=30,
        help="Max timeline rows to print (default 30; use a large number "
             "for full timeline).",
    )
    args = p.parse_args(argv)

    if not args.jsonl.exists():
        sys.stderr.write(f"error: {args.jsonl} not found\n")
        return 1

    summary = summarize_run(args.jsonl)

    if args.json:
        # Convert dataclasses to dicts via dataclasses.asdict
        from dataclasses import asdict
        payload = {"summary": asdict(summary)}
        if args.baseline:
            base = summarize_run(args.baseline)
            cmp = compare_runs(summary, base)
            payload["comparison"] = asdict(cmp)
        sys.stdout.write(json.dumps(payload, indent=2, default=str))
        return 0

    sys.stdout.write(_format_run_report(summary, args.timeline_rows))
    sys.stdout.write("\n")

    if args.baseline:
        if not args.baseline.exists():
            sys.stderr.write(f"error: baseline {args.baseline} not found\n")
            return 1
        base = summarize_run(args.baseline)
        cmp = compare_runs(summary, base)
        sys.stdout.write(_format_comparison(cmp))
        sys.stdout.write("\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
