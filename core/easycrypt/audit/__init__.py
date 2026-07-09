"""core.easycrypt.audit — run-trace analysis for prover sessions.

Read-only analysis of Claude Code session traces (JSONL files under
~/.claude/projects/<project>/<session_id>.jsonl). Extracts the data we
keep needing to ad-hoc-grep:

- Per-step timeline (thinking blocks paired with tool calls)
- Hook fire counts (which `[MARKER]`s appeared, how often)
- Stuck windows (consecutive non-progress segments)
- Cross-run comparison (two traces side-by-side)

# Why this package exists

Architecture step #2 of the post-2026-04-30 cleanup: replace the one-off
Python scripts that have accumulated across audits with a coherent,
reusable, layer-clean module. Each future prover run dumps its trace
JSONL to a known location; this package consumes that JSONL and produces
structured data (no narrative). Audit reports are then assembled from
the structured data, not built from scratch each time.

Read-only by contract — never modifies traces, sessions, or project
state. Pure functions. Designed for unit testing without EC daemon.

# Public surface

```python
from core.easycrypt.audit import (
    Step, HookFire, StuckWindow, RunSummary,    # data classes
    extract_timeline,                            # → list[Step]
    count_hook_fires,                            # → dict[marker, int]
    list_hook_fires,                             # → list[HookFire]
    detect_stuck_windows,                        # → list[StuckWindow]
    summarize_run,                               # → RunSummary (fully composes)
    compare_runs,                                # → ComparisonReport
)
```

CLI entrypoint: `python3 -m core.easycrypt.audit <session.jsonl>`.

# Layout

- `types.py`     — dataclasses (Step, HookFire, StuckWindow, RunSummary, ComparisonReport)
- `timeline.py`  — JSONL → list[Step]
- `hook_stats.py` — JSONL → marker fire counts + locations
- `stuck.py`     — timeline → stuck windows (heuristic)
- `compare.py`   — two RunSummary → ComparisonReport
- `cli.py`       — `python3 -m core.easycrypt.audit ...` entry
"""
from __future__ import annotations

from .types import (
    Step,
    HookFire,
    StuckWindow,
    RunSummary,
    ComparisonReport,
)
from .timeline import extract_timeline
from .hook_stats import count_hook_fires, list_hook_fires
from .stuck import detect_stuck_windows
from .compare import compare_runs
from .summary import summarize_run

__all__ = [
    "Step",
    "HookFire",
    "StuckWindow",
    "RunSummary",
    "ComparisonReport",
    "extract_timeline",
    "count_hook_fires",
    "list_hook_fires",
    "detect_stuck_windows",
    "summarize_run",
    "compare_runs",
]
