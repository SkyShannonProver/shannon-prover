"""Heuristic stuck-window detection.

A "stuck window" is a span of the timeline where the agent isn't making
forward proof progress. We detect three kinds:

- **no-progress**: gap > N minutes between consecutive progress signals.
  A "progress signal" is an AFFIRMATIVE marker in the principal action's
  tool result: `verdict=PROGRESS`, `verdict=PROGRESS_DECOMPOSITION`,
  `[GOAL_CLOSED]`, or `[ALL_GOALS_CLOSED]`. The absence of a tactic-
  count metric is NOT itself stuck — many real progress events don't
  emit `(\\d+) tactics accepted` (only `-status` does).
- **regression-loop**: tactic count went backward (undo) and didn't
  recover within N steps.
- **search-storm**: ≥ K consecutive steps where the principal action
  was a `-search` / `-search-skeleton` call.

These are HEURISTICS — they may flag genuine progress (e.g. agent
correctly investigating before committing). The stuck-window report
is "ask, then verify"; combined with `count_hook_fires` it tells you
what to look at in the trace.

# Why "progress = affirmative signal"

An earlier draft used "absence of `tac=K+1`" as the no-progress check.
Since `tac=K` only appears in `-status` output (not the much more
common `-next` / `-chain` commit results), almost every step looked
like "no-progress" — total stuck time approximated wall time minus a
few `-status` calls. step2_2 and step4_bad2 both reported `72.8 min
stuck` (their wall times happened to be similar), erasing the very
real difference between their cliff classes (list-theory composition
vs phoare-seq syntax discovery).

Switching to affirmative `PROGRESS / DECOMP / CLOSED` markers — which
ARE emitted by every successful commit via `[STATE-DIFF]` — makes the
metric actually measure stuckness, not measurement-tool absence.
"""
from __future__ import annotations

import re
from typing import Optional

from .types import Step, StuckWindow


_TAC_RE = re.compile(r"tac=(\d+)")
_SEARCH_ACTION_RE = re.compile(
    r"(\bsession_cli\.py.*-search\b|\bsearch[-_]skeleton\b)"
)


def _step_tactic_count(step: Step) -> Optional[int]:
    """Pull `tac=K` from the principal_signal, if present."""
    m = _TAC_RE.search(step.principal_signal or "")
    return int(m.group(1)) if m else None


def _step_made_progress(step: Step) -> bool:
    """Return True iff this step produced an affirmative progress signal.

    Affirmative signals (in order of strength):
    - `ALL-CLOSED` — the proof is done
    - `CLOSED`     — a subgoal was closed
    - `PROGRESS`   — STATE-DIFF verdict=PROGRESS (tactic moved goal forward)
    - `DECOMP`     — STATE-DIFF verdict=PROGRESS_DECOMPOSITION (call/seq/
                     byequiv expanded subgoals; this is forward progress
                     even though subgoal count went up)

    `tac=K` alone is NOT counted — it's a metric-presence signal, not
    a progress claim. See module docstring for rationale.
    """
    sig = step.principal_signal or ""
    for marker in ("ALL-CLOSED", "CLOSED", "PROGRESS", "DECOMP"):
        if marker in sig:
            return True
    return False


def _step_is_search(step: Step) -> bool:
    return bool(_SEARCH_ACTION_RE.search(step.principal_action or ""))


def detect_stuck_windows(
    timeline: list[Step],
    no_progress_min_minutes: float = 3.0,
    regression_min_steps: int = 3,
    search_storm_min_steps: int = 5,
) -> list[StuckWindow]:
    """Return the detected stuck windows in trace order. Windows may
    overlap (e.g. a search-storm can be inside a no-progress span); the
    caller should dedup if a flat list is desired.

    `no_progress_min_minutes`: gap threshold between progress events for
    a stuck window to be flagged. 3 min is the default — short enough to
    catch real flailing, long enough that brief investigation pauses
    don't spam the report.
    """
    windows: list[StuckWindow] = []
    if not timeline:
        return windows

    # ── 1. no-progress windows ──
    # Gap between consecutive PROGRESS / DECOMP / CLOSED signals > threshold.
    # The "before-first-progress" prefix and "after-last-progress" suffix
    # are also candidates if their durations exceed threshold.

    # Collect indices of progress events.
    progress_indices = [i for i, s in enumerate(timeline)
                        if _step_made_progress(s)]

    # Construct "boundary points" defining gaps to inspect:
    #   - synthetic start at t=0.0, before-step index = -1
    #   - each progress event
    #   - synthetic end at last step's t_min, after-step index = len(timeline)
    boundaries: list[tuple[int, float]] = [(-1, 0.0)]
    for i in progress_indices:
        boundaries.append((i, timeline[i].t_min))
    boundaries.append((len(timeline), timeline[-1].t_min))

    for k in range(len(boundaries) - 1):
        prev_idx, prev_t = boundaries[k]
        next_idx, next_t = boundaries[k + 1]
        duration = next_t - prev_t
        if duration < no_progress_min_minutes:
            continue
        # The "stuck" steps are those strictly after prev (which IS the
        # last progress event, or the synthetic start) and at-or-before
        # next (which IS the next progress event, or the synthetic end).
        first_stuck_idx = prev_idx + 1
        # `next_idx == len(timeline)` means trailing gap; clamp.
        last_stuck_idx = min(next_idx, len(timeline) - 1)
        # If `next` is a real progress event, the gap is the time UP TO
        # but not including that event (which is itself a PROGRESS).
        # Stuck steps are first_stuck_idx .. last_stuck_idx-1 in that case.
        if next_idx < len(timeline):
            last_stuck_idx = next_idx - 1
        if first_stuck_idx > last_stuck_idx:
            # No actual stuck steps in this gap (e.g. two progress events
            # back-to-back with a long wall-time gap). Skip.
            continue
        first_step = timeline[first_stuck_idx]
        last_step = timeline[last_stuck_idx]
        # Evidence: short summary of what dominated the gap.
        evidence = [
            f"gap from {prev_t:.1f} to {next_t:.1f} min "
            f"({duration:.1f} min, {last_stuck_idx - first_stuck_idx + 1} "
            f"steps without a PROGRESS / DECOMP / CLOSED signal)",
            f"first action: {first_step.principal_action[:60]}",
            f"last action:  {last_step.principal_action[:60]}",
        ]
        if prev_idx == -1:
            evidence.append("(window precedes first progress event)")
        if next_idx == len(timeline):
            evidence.append("(window extends to end of trace)")
        windows.append(StuckWindow(
            start_step=first_step.step_n,
            end_step=last_step.step_n,
            start_t_min=prev_t,
            end_t_min=next_t,
            duration_min=duration,
            kind="no-progress",
            evidence=evidence,
        ))

    # ── 2. regression-loop ──
    # Tactic count goes backward by ≥1 and doesn't recover within N steps.
    last_seen_tac: Optional[int] = None
    for i, s in enumerate(timeline):
        tac = _step_tactic_count(s)
        if tac is None:
            continue
        if last_seen_tac is not None and tac < last_seen_tac:
            # Regression detected at i; check if it's recovered within window
            recovered = False
            for j in range(i + 1, min(i + 1 + regression_min_steps, len(timeline))):
                jtac = _step_tactic_count(timeline[j])
                if jtac is not None and jtac >= last_seen_tac:
                    recovered = True
                    break
            if not recovered:
                end_idx = min(i + regression_min_steps, len(timeline) - 1)
                windows.append(StuckWindow(
                    start_step=s.step_n,
                    end_step=timeline[end_idx].step_n,
                    start_t_min=s.t_min,
                    end_t_min=timeline[end_idx].t_min,
                    duration_min=timeline[end_idx].t_min - s.t_min,
                    kind="regression-loop",
                    evidence=[
                        f"tactic count went {last_seen_tac} → {tac} at step "
                        f"{s.step_n}",
                        f"did not recover within {regression_min_steps} steps",
                    ],
                ))
        last_seen_tac = tac

    # ── 3. search-storm ──
    # ≥ K consecutive steps where principal action is a search.
    run_start: Optional[int] = None
    for i, s in enumerate(timeline):
        if _step_is_search(s):
            if run_start is None:
                run_start = i
        else:
            if run_start is not None:
                run_len = i - run_start
                if run_len >= search_storm_min_steps:
                    end_idx = i - 1
                    windows.append(StuckWindow(
                        start_step=timeline[run_start].step_n,
                        end_step=timeline[end_idx].step_n,
                        start_t_min=timeline[run_start].t_min,
                        end_t_min=timeline[end_idx].t_min,
                        duration_min=timeline[end_idx].t_min - timeline[run_start].t_min,
                        kind="search-storm",
                        evidence=[
                            f"{run_len} consecutive `-search` / "
                            f"`-search-skeleton` calls",
                        ],
                    ))
                run_start = None
    if run_start is not None:
        run_len = len(timeline) - run_start
        if run_len >= search_storm_min_steps:
            end_idx = len(timeline) - 1
            windows.append(StuckWindow(
                start_step=timeline[run_start].step_n,
                end_step=timeline[end_idx].step_n,
                start_t_min=timeline[run_start].t_min,
                end_t_min=timeline[end_idx].t_min,
                duration_min=timeline[end_idx].t_min - timeline[run_start].t_min,
                kind="search-storm",
                evidence=[
                    f"{run_len} consecutive search calls (through end of trace)",
                ],
            ))

    # Sort by start time for stable output
    windows.sort(key=lambda w: w.start_t_min)
    return windows
