"""Unit tests for `core.easycrypt.audit` — run-trace analysis.

Tests:
- Timeline extraction on synthetic JSONL
- Hook-fire counting (single + repeated markers, prefix-match for `[CLASS:`)
- Stuck-window detection (no-commit / regression-loop / search-storm)
- Cross-run comparison
- Summarize-run end-to-end smoke test

Pure-Python: no EC daemon, no network. Synthesizes minimal JSONL fixtures
in memory.

Run: `python3 tests/test_audit.py`
"""
from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from core.easycrypt.audit.timeline import extract_timeline  # noqa: E402
from core.easycrypt.audit.hook_stats import (  # noqa: E402
    KNOWN_MARKERS,
    count_hook_fires,
    list_hook_fires,
)
from core.easycrypt.audit.stuck import detect_stuck_windows  # noqa: E402
from core.easycrypt.audit.compare import compare_runs  # noqa: E402
from core.easycrypt.audit.summary import summarize_run  # noqa: E402
from core.easycrypt.audit.types import Step  # noqa: E402


def case(name: str, fn) -> bool:
    try:
        fn()
        print(f"  ✓ {name}")
        return True
    except AssertionError as e:
        print(f"  ✗ {name}\n      {e}")
        return False
    except Exception as e:
        print(f"  ✗ {name}\n      {type(e).__name__}: {e}")
        return False


def _ts(t0: datetime, mins: float) -> str:
    return (t0 + timedelta(minutes=mins)).isoformat() + "+00:00"


def _build_synthetic_jsonl(path: Path, *,
                           steps: list[dict]) -> None:
    """Write a minimal JSONL trace with the given steps.

    Each step dict supports:
      - `t_min`: float, minutes from t0
      - `think`: str
      - `actions`: list of {kind, cmd, result}
        kind = "bash" | "Read" | etc.
    """
    t0 = datetime(2026, 1, 1, 0, 0, 0)
    lines: list[str] = []
    counter = 0
    for st in steps:
        counter += 1
        ts = _ts(t0, st.get("t_min", 0.0))
        # Assistant message: thinking + tool_uses
        content = [{"type": "thinking", "thinking": st.get("think", "")}]
        for a in st.get("actions", []):
            tid = f"tool_{counter}_{a.get('idx', 0)}"
            content.append({
                "type": "tool_use",
                "id": tid,
                "name": a.get("kind", "Bash"),
                "input": {"command": a.get("cmd", "")} if a.get("kind", "Bash") == "Bash" else {},
            })
        lines.append(json.dumps({
            "type": "assistant",
            "timestamp": ts,
            "message": {"content": content},
        }))
        # User message: tool_result for each action
        result_content = []
        for a in st.get("actions", []):
            tid = f"tool_{counter}_{a.get('idx', 0)}"
            result_content.append({
                "type": "tool_result",
                "tool_use_id": tid,
                "content": a.get("result", ""),
            })
        if result_content:
            lines.append(json.dumps({
                "type": "user",
                "timestamp": ts,
                "message": {"content": result_content},
            }))
    path.write_text("\n".join(lines))


def main() -> int:
    fail = 0
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)

        # ── Timeline extraction ──
        def timeline_basic():
            p = d / "basic.jsonl"
            _build_synthetic_jsonl(p, steps=[
                {"t_min": 0.0, "think": "First thought.\nMore detail.",
                 "actions": [{"idx": 0, "kind": "Bash",
                              "cmd": "python3 session_cli.py -d s -next -c 'smt().'",
                              "result": "[STATE-DIFF] verdict=PROGRESS\n[1 tactics accepted]"}]},
                {"t_min": 1.5, "think": "Second thought.",
                 "actions": [{"idx": 0, "kind": "Bash",
                              "cmd": "python3 session_cli.py -d s -try -c 'apply foo.'",
                              "result": "[TRY] accepted: True\n[TRY] goal_after: 2 subgoal(s) remaining"}]},
            ])
            tl = extract_timeline(p)
            assert len(tl) == 2, f"expected 2 steps, got {len(tl)}"
            assert tl[0].step_n == 1
            assert abs(tl[0].t_min - 0.0) < 0.01
            assert "smt()" in tl[0].principal_action
            assert "PROGRESS" in tl[0].principal_signal
            assert tl[1].step_n == 2
            assert "apply foo" in tl[1].principal_action
            assert "TRY-OK" in tl[1].principal_signal
            assert "sg=2" in tl[1].principal_signal

        def timeline_principal_picks_next_over_try():
            p = d / "principal.jsonl"
            _build_synthetic_jsonl(p, steps=[
                {"t_min": 0.0, "think": "T",
                 "actions": [
                     {"idx": 0, "kind": "Bash",
                      "cmd": "python3 session_cli.py -d s -try -c 'foo.'",
                      "result": "[TRY] accepted: False"},
                     {"idx": 1, "kind": "Bash",
                      "cmd": "python3 session_cli.py -d s -next -c 'bar.'",
                      "result": "[STATE-DIFF] verdict=PROGRESS"},
                 ]},
            ])
            tl = extract_timeline(p)
            assert len(tl) == 1
            assert "bar" in tl[0].principal_action, \
                f"expected -next 'bar.' to be principal, got {tl[0].principal_action}"
            assert tl[0].aux_action_count == 1

        # ── Hook stats ──
        def hooks_basic_count():
            p = d / "hooks.jsonl"
            _build_synthetic_jsonl(p, steps=[
                {"t_min": 0.0, "think": "T",
                 "actions": [{"idx": 0, "kind": "Bash", "cmd": "x",
                              "result": "[STATE-DIFF] verdict=PROGRESS\n[STATE-DIFF] another"}]},
                {"t_min": 1.0, "think": "T",
                 "actions": [{"idx": 0, "kind": "Bash", "cmd": "x",
                              "result": "[POST-CALL-INV-HINT] hello\n[AUTO-SIG] details"}]},
            ])
            counts = count_hook_fires(p)
            assert counts["[STATE-DIFF]"] == 2, f"got {counts['[STATE-DIFF]']}"
            assert counts["[POST-CALL-INV-HINT]"] == 1
            assert counts["[AUTO-SIG]"] == 1
            assert counts["[DAEMON_REJECTED]"] == 0

        def hooks_prefix_class():
            # `[CLASS:` is a prefix-match marker — counts any `[CLASS: SYNTAX]`
            p = d / "class.jsonl"
            _build_synthetic_jsonl(p, steps=[
                {"t_min": 0.0, "think": "T",
                 "actions": [{"idx": 0, "kind": "Bash", "cmd": "x",
                              "result": "[CLASS: syntax error] details"}]},
            ])
            counts = count_hook_fires(p)
            assert counts["[CLASS:"] == 1

        def hook_fires_with_step_info():
            p = d / "fires.jsonl"
            _build_synthetic_jsonl(p, steps=[
                {"t_min": 0.0, "think": "T", "actions": []},
                {"t_min": 1.5, "think": "T",
                 "actions": [{"idx": 0, "kind": "Bash", "cmd": "x",
                              "result": "[POST-CALL-INV-HINT] foo\nbar"}]},
            ])
            fires = list_hook_fires(p)
            target = [f for f in fires if f.marker == "[POST-CALL-INV-HINT]"]
            assert len(target) == 1
            assert target[0].step_n == 2
            assert abs(target[0].t_min - 1.5) < 0.01
            assert "foo" in target[0].excerpt or "POST-CALL" in target[0].excerpt

        # ── Stuck windows ──
        def stuck_no_progress_long_gap():
            # 8 steps over 12 min, NO progress signal anywhere.
            # Whole run is one big stuck span (synthetic start → end gap).
            steps = [
                Step(step_n=i + 1, t_min=i * 1.5,
                     think_text="t", think_first_line="t",
                     principal_action="smt().",
                     principal_signal="",
                     aux_action_count=0)
                for i in range(8)
            ]
            ws = detect_stuck_windows(steps, no_progress_min_minutes=3.0)
            assert any(w.kind == "no-progress" for w in ws), \
                f"expected no-progress window, got {[w.kind for w in ws]}"

        def stuck_no_progress_split_by_progress_event():
            # Progress at min 0 and 10; gap of 10 min between is one window
            # (covering steps 1 through ... before the progress event at idx 5).
            steps = [
                Step(1, 0.0, "t", "t", "a", "PROGRESS tac=1", 0),  # progress
                Step(2, 2.0, "t", "t", "smt().", "", 0),
                Step(3, 4.0, "t", "t", "auto.", "", 0),
                Step(4, 6.0, "t", "t", "trivial.", "", 0),
                Step(5, 8.0, "t", "t", "done.", "", 0),
                Step(6, 10.0, "t", "t", "a", "PROGRESS tac=2", 0),  # progress
                Step(7, 11.0, "t", "t", "a", "", 0),
            ]
            ws = detect_stuck_windows(steps, no_progress_min_minutes=3.0)
            no_prog = [w for w in ws if w.kind == "no-progress"]
            assert len(no_prog) >= 1, \
                f"expected at least one no-progress window, got {ws}"
            # The gap from t=0 to t=10 should be flagged
            mid_window = next((w for w in no_prog
                               if w.start_t_min == 0.0
                               and abs(w.end_t_min - 10.0) < 0.01), None)
            assert mid_window is not None, \
                f"expected window 0–10 min between progress events, got {no_prog}"
            assert abs(mid_window.duration_min - 10.0) < 0.01

        def stuck_progress_decomp_counts_as_progress():
            # DECOMP (PROGRESS_DECOMPOSITION) should also reset the gap.
            steps = [
                Step(1, 0.0, "t", "t", "a", "DECOMP sg=4", 0),
                Step(2, 2.0, "t", "t", "a", "", 0),
                Step(3, 5.0, "t", "t", "a", "CLOSED PROGRESS", 0),
            ]
            ws = detect_stuck_windows(steps, no_progress_min_minutes=10.0)
            # Gap 0→5 = 5 min, below 10 min threshold → no window
            no_prog = [w for w in ws if w.kind == "no-progress"]
            assert len(no_prog) == 0, \
                f"expected no stuck window (DECOMP counted), got {no_prog}"

        def stuck_regression_loop():
            # tac goes 1→2→3→2→2 with no recovery within 3 steps
            steps = [
                Step(1, 0.0, "t", "t", "a", "tac=1", 0),
                Step(2, 1.0, "t", "t", "a", "tac=2", 0),
                Step(3, 2.0, "t", "t", "a", "tac=3", 0),
                Step(4, 3.0, "t", "t", "a", "tac=2", 0),  # regression
                Step(5, 4.0, "t", "t", "a", "tac=2", 0),
                Step(6, 5.0, "t", "t", "a", "tac=2", 0),
            ]
            ws = detect_stuck_windows(steps)
            assert any(w.kind == "regression-loop" for w in ws), \
                f"expected regression-loop, got {[w.kind for w in ws]}"

        def stuck_search_storm():
            steps = [
                Step(i + 1, i * 0.3, "t", "t",
                     "python3 session_cli.py -d s -search 'foo'",
                     "", 0)
                for i in range(7)
            ]
            ws = detect_stuck_windows(steps, search_storm_min_steps=5)
            assert any(w.kind == "search-storm" for w in ws), \
                f"expected search-storm, got {[w.kind for w in ws]}"

        def stuck_no_false_positive_when_progressing():
            # Healthy run: every step has PROGRESS signal, gap < threshold
            steps = [
                Step(i + 1, i * 0.5, "t", "t", "a",
                     f"PROGRESS tac={i + 1}", 0)
                for i in range(6)
            ]
            ws = detect_stuck_windows(steps, no_progress_min_minutes=3.0)
            assert all(w.kind != "no-progress" for w in ws), \
                f"unexpected no-progress window in healthy run: {[w.kind for w in ws]}"

        # ── Comparison ──
        def comparison_basic():
            p1 = d / "this.jsonl"
            p2 = d / "base.jsonl"
            _build_synthetic_jsonl(p1, steps=[
                {"t_min": 0.0, "think": "T",
                 "actions": [{"idx": 0, "kind": "Bash",
                              "cmd": "session_cli.py -search 'x'",
                              "result": "[POST-CALL-INV-HINT] new!"}]},
            ])
            _build_synthetic_jsonl(p2, steps=[
                {"t_min": 0.0, "think": "T",
                 "actions": [{"idx": 0, "kind": "Bash",
                              "cmd": "session_cli.py -search 'y'",
                              "result": "[STATE-DIFF] verdict=PROGRESS"}]},
            ])
            this_s = summarize_run(p1)
            base_s = summarize_run(p2)
            cmp = compare_runs(this_s, base_s)
            assert "[POST-CALL-INV-HINT]" in cmp.hooks_only_in_this
            assert "[STATE-DIFF]" in cmp.hooks_only_in_baseline

        # ── End-to-end summarize_run ──
        def summarize_e2e():
            p = d / "full.jsonl"
            _build_synthetic_jsonl(p, steps=[
                {"t_min": 0.0, "think": "Plan.",
                 "actions": [{"idx": 0, "kind": "Bash",
                              "cmd": "session_cli.py -d s -next -c 'smt().'",
                              "result": "[STATE-DIFF] verdict=PROGRESS\n1 tactics accepted"}]},
                {"t_min": 0.5, "think": "Probe.",
                 "actions": [{"idx": 0, "kind": "Bash",
                              "cmd": "session_cli.py -d s -try -c 'apply x.'",
                              "result": "[TRY] accepted: False"}]},
            ])
            s = summarize_run(p)
            assert s.total_thinking_blocks == 2
            assert s.total_bash_calls == 2
            assert s.tool_breakdown.get("-next", 0) == 1
            assert s.tool_breakdown.get("-try", 0) == 1
            assert s.hook_counts.get("[STATE-DIFF]", 0) == 1
            assert s.session_id == "full"
            assert s.wall_minutes >= 0.4

        cases = [
            ("timeline: basic 2-step extraction", timeline_basic),
            ("timeline: principal picks -next over -try",
             timeline_principal_picks_next_over_try),
            ("hooks: basic marker counts (incl. multi-fire)", hooks_basic_count),
            ("hooks: [CLASS: prefix-match counts", hooks_prefix_class),
            ("hooks: list_hook_fires links to step / t_min",
             hook_fires_with_step_info),
            ("stuck: no-progress window when no signals at all",
             stuck_no_progress_long_gap),
            ("stuck: gap between two progress events flagged correctly",
             stuck_no_progress_split_by_progress_event),
            ("stuck: DECOMP counts as progress (resets gap)",
             stuck_progress_decomp_counts_as_progress),
            ("stuck: regression-loop detected", stuck_regression_loop),
            ("stuck: search-storm detected", stuck_search_storm),
            ("stuck: healthy run has no no-progress windows",
             stuck_no_false_positive_when_progressing),
            ("compare: hooks_only_in_* lists are correct", comparison_basic),
            ("summarize_run: end-to-end fields populated", summarize_e2e),
        ]

        for name, fn in cases:
            if not case(name, fn):
                fail += 1

    n = len(cases)
    print()
    print(f"{n - fail}/{n} pass")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())


def test_all_cases() -> None:
    """pytest entry: the case() harness's failure count must be zero.

    This file predates the pytest convention (custom case()/main()); the
    wrapper makes its coverage visible to `pytest tests/` — it had been
    silently collected as zero tests.
    """
    assert main() == 0
