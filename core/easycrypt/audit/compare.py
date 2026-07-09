"""Cross-run comparison — diff two `RunSummary` instances."""
from __future__ import annotations

from .types import ComparisonReport, RunSummary


def compare_runs(this: RunSummary, baseline: RunSummary) -> ComparisonReport:
    """Build a diff between two run summaries.

    Convention: deltas are `this - baseline`. A negative wall_minutes_delta
    means `this` was faster. A positive hook count delta means a hook
    fired MORE in `this` than in `baseline`.

    `hooks_only_in_this` / `hooks_only_in_baseline` use the keys of each
    summary's `hook_counts` dict (which only includes markers with count
    ≥ 1). If a marker fired in both, it's not in either "only" list.
    """
    this_hooks = set(this.hook_counts.keys())
    base_hooks = set(baseline.hook_counts.keys())
    only_this = sorted(this_hooks - base_hooks)
    only_base = sorted(base_hooks - this_hooks)
    shared = this_hooks & base_hooks
    hook_count_deltas = {
        m: this.hook_counts[m] - baseline.hook_counts[m]
        for m in shared
    }

    stuck_this = sum(w.duration_min for w in this.stuck_windows)
    stuck_base = sum(w.duration_min for w in baseline.stuck_windows)

    tool_keys = set(this.tool_breakdown) | set(baseline.tool_breakdown)
    tool_deltas = {
        k: this.tool_breakdown.get(k, 0) - baseline.tool_breakdown.get(k, 0)
        for k in tool_keys
    }

    return ComparisonReport(
        this_session=this.session_id,
        baseline_session=baseline.session_id,
        wall_minutes_delta=this.wall_minutes - baseline.wall_minutes,
        thinking_blocks_delta=this.total_thinking_blocks - baseline.total_thinking_blocks,
        tool_calls_delta=this.total_tool_calls - baseline.total_tool_calls,
        hooks_only_in_this=only_this,
        hooks_only_in_baseline=only_base,
        hook_count_deltas=hook_count_deltas,
        stuck_minutes_this=stuck_this,
        stuck_minutes_baseline=stuck_base,
        stuck_minutes_delta=stuck_this - stuck_base,
        tool_count_deltas=tool_deltas,
    )
