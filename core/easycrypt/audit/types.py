"""Audit data classes — pure data, no behavior."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Step:
    """One thinking-block + its associated tool calls.

    A `Step` represents the agent's chain of (think → act) at a single
    decision point in the proof. `step_n` is the 1-indexed thinking-
    block number. `principal_action` is the most-significant tool call
    (typically the one that commits a tactic, e.g. -next/-chain/-try);
    other calls (info-gathering bash, file reads) are in `aux_actions`.
    """
    step_n: int
    t_min: float                      # minutes from session t0
    think_text: str                   # full thinking block content
    think_first_line: str             # one-line summary
    principal_action: str             # short tactic / tool description
    principal_signal: str             # detected outcome (PROGRESS / DAEMON-REJ / etc.)
    aux_action_count: int = 0         # number of auxiliary actions in this step


@dataclass
class HookFire:
    """One occurrence of a `[MARKER]` block in a tool result."""
    marker: str                       # e.g. "[POST-CALL-INV-HINT]"
    step_n: int                       # which thinking-step it appeared in
    t_min: float                      # minutes from session t0
    excerpt: str                      # ~80-char snippet around the marker


@dataclass
class StuckWindow:
    """A continuous span where no tactic-progress occurred.

    `kind` classifies the symptom (heuristic):
    - "no-commit"       : no tactic committed for the whole window
    - "regression-loop" : tactic count went backward (undo > commit)
    - "search-storm"    : ≥ 5 consecutive `-search` / `-search-skeleton` calls
    - "thinking-stall"  : single thinking block > 90s with no tool call after
    """
    start_step: int
    end_step: int
    start_t_min: float
    end_t_min: float
    duration_min: float
    kind: str
    evidence: list[str] = field(default_factory=list)  # bullet descriptions


@dataclass
class RunSummary:
    """Composed summary of a full session trace."""
    session_id: str                   # the JSONL filename without extension
    project_dir: str                  # path component, e.g. "-private-tmp-cap-step2-2-r1"
    total_thinking_blocks: int
    total_tool_calls: int
    total_bash_calls: int
    wall_minutes: float
    timeline: list[Step]
    hook_fires: list[HookFire]
    hook_counts: dict[str, int]       # marker → count
    stuck_windows: list[StuckWindow]
    tool_breakdown: dict[str, int]    # session_cli flag → count (-search, -try, ...)


@dataclass
class ComparisonReport:
    """Diff between two `RunSummary` instances."""
    this_session: str
    baseline_session: str

    # Wall-time / progress deltas
    wall_minutes_delta: float          # this - baseline (negative = faster)
    thinking_blocks_delta: int
    tool_calls_delta: int

    # Hook deltas
    hooks_only_in_this: list[str]      # markers fired here but not in baseline
    hooks_only_in_baseline: list[str]
    hook_count_deltas: dict[str, int]  # marker → (this - baseline) for shared

    # Stuck windows
    stuck_minutes_this: float
    stuck_minutes_baseline: float
    stuck_minutes_delta: float

    # Tool usage deltas (top entries)
    tool_count_deltas: dict[str, int]
