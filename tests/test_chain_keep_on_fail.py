"""Verify that ``-tactic-exec commit_chain`` leaves ``history.ec`` in a
state matching the current structured result's ``accepted_count``.

Two failure modes the fix addresses:
  (A) Daemon-side rejection rolls back history without emitting the
      `[TACTIC_NO_EFFECT_AUTO_REVERTED]` marker. The chain handler used
      to call `step_up` blindly (because the marker is its only signal),
      over-rolling-back a real prefix tactic.
  (B) `detect_no_progress` correctly auto-reverts but chain's coarser
      `_extract_goal` disagrees, so the OK branch falsely increments
      `accepted` for a tactic that no longer exists in history.

The fix: chain uses `history.ec` line count as ground truth for
"tactic was committed". This file exercises a range of scenarios and
asserts that the line count of history.ec matches the chain's reported
`accepted` count after the chain returns.

Run: `python3 tools/bootstrap_easycrypt.py --verify-only` followed by this file.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)
from core.easycrypt.ec_env import get_ec_env  # noqa: E402
SCLI = ROOT / "core" / "easycrypt" / "session_cli.py"
SAMPLE_EC = ROOT / "eval" / "examples" / "WhileSample.ec"
DICE_EC = ROOT / "eval" / "examples" / "Dice4_6.ec"
TRIVIAL_EC = (
    ROOT / "tests" / "fixtures" / "native_semantics"
    / "proof_term_implicit_goal.ec"
)
SESS = ROOT / ".ec_session_chain_test"


def run(args: list[str], env_extra: dict | None = None) -> tuple[int, str]:
    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)
    p = subprocess.run(
        ["python3", str(SCLI), *args],
        cwd=ROOT, env=env, capture_output=True, text=True,
    )
    return p.returncode, p.stdout + p.stderr


def history_line_count() -> int:
    h = SESS / "history.ec"
    if not h.exists():
        return 0
    return sum(1 for ln in h.read_text(encoding="utf-8").splitlines()
               if ln.strip())


def fresh_session(file_path: Path = SAMPLE_EC, lemma: str | None = None):
    if SESS.exists():
        shutil.rmtree(SESS)
    args = [
        "-d", str(SESS), "-start",
        "-f", str(file_path),
        "-I", str(file_path.parent),
    ]
    if lemma is not None:
        args.extend(["-lemma", lemma])
    rc, out = run(args)
    if rc != 0:
        return f"-start failed: {out[-300:]}"
    return None  # success


def parse_accepted_count(stdout: str) -> int:
    """Read one current structured CLI delivery and return its count.

    This direct-CLI consistency test deliberately has no text-marker or
    historical-output fallback.  The manager's semantic authority remains the
    event-bound durable artifact; here we test only the current developer CLI
    display contract emitted from that artifact.
    """

    marker = "[TACTIC-EXECUTION-RESULT]\n"
    if stdout.count(marker) != 1:
        raise AssertionError("expected exactly one structured execution result")
    encoded = stdout.split(marker, 1)[1].lstrip()
    try:
        result, end = json.JSONDecoder().raw_decode(encoded)
    except json.JSONDecodeError as exc:
        raise AssertionError("structured execution result is invalid JSON") from exc
    if encoded[end:].strip():
        raise AssertionError("unexpected output after structured execution result")
    if not isinstance(result, dict) or set(result) != {
        "execution", "result", "workspace",
    }:
        raise AssertionError("unexpected structured execution result shape")
    if not isinstance(result["result"], dict) or not isinstance(
        result["workspace"], dict
    ):
        raise AssertionError("structured result blocks must be objects")
    execution = result.get("execution")
    if not isinstance(execution, dict) or execution.get("mode") != "commit_chain":
        raise AssertionError("execution result is not for commit_chain")
    accepted = execution.get("accepted_count")
    if type(accepted) is not int or accepted < 0:
        raise AssertionError("execution.accepted_count must be a non-negative int")
    return accepted


# ─────────────────────────────────────────────────────────────────────
# Scenarios
# ─────────────────────────────────────────────────────────────────────

def case_full_success():
    """Chain where every tactic succeeds. accepted == len(tactics) ==
    history_added."""
    err = fresh_session(SAMPLE_EC, lemma="Sample_lossless2")
    if err:
        return f"skipped ({err})"
    baseline = history_line_count()
    rc, out = run([
        "-d", str(SESS), "-tactic-exec", "commit_chain", "-c",
        "proc. seq 1 2 : (={ret}). auto.",
    ])
    accepted = parse_accepted_count(out)
    h = history_line_count() - baseline
    if accepted < 0:
        return f"FAILED: no accepted count\n{out[-300:]}"
    if h != accepted:
        return (f"FAILED: accepted={accepted} but history_added={h}\n"
                f"{out[-400:]}")
    return f"passed (accepted={accepted}, history_added={h})"


def case_first_tactic_fails_keep():
    """Chain where the FIRST tactic fails. With --keep-on-fail and
    accepted=0, the chain falls through to the default rollback branch
    (`accepted > 0` is false). Verify nothing gets stuck."""
    err = fresh_session(SAMPLE_EC, lemma="Sample_lossless2")
    if err:
        return f"skipped ({err})"
    baseline = history_line_count()
    rc, out = run([
        "-d", str(SESS), "-tactic-exec", "commit_chain", "--keep-on-fail", "-c",
        "intentionally_malformed_xyz. proc. auto.",
    ])
    accepted = parse_accepted_count(out)
    h = history_line_count() - baseline
    if accepted != 0:
        return f"FAILED: expected accepted=0, got {accepted}\n{out[-400:]}"
    if h != 0:
        return f"FAILED: history grew by {h} but accepted=0\n{out[-400:]}"
    return f"passed (accepted=0, history_added=0)"


def case_last_tactic_fails_keep():
    """Chain where the LAST tactic fails parse. accepted = N-1, and
    history.ec must have exactly N-1 lines added."""
    err = fresh_session(SAMPLE_EC, lemma="Sample_lossless2")
    if err:
        return f"skipped ({err})"
    baseline = history_line_count()
    rc, out = run([
        "-d", str(SESS), "-tactic-exec", "commit_chain", "--keep-on-fail", "-c",
        "proc. seq 1 2 : (={ret}). intentionally_malformed_xyz.",
    ])
    accepted = parse_accepted_count(out)
    h = history_line_count() - baseline
    if accepted != 2:
        return f"FAILED: expected accepted=2, got {accepted}\n{out[-400:]}"
    if h != accepted:
        return f"FAILED: accepted={accepted} but history_added={h}\n{out[-400:]}"
    return f"passed (accepted={accepted}, history_added={h})"


def case_middle_fails_no_keep():
    """Chain WITHOUT --keep-on-fail. Default behavior: rollback all
    accepted tactics + the failing one. After: history_added == 0."""
    err = fresh_session(SAMPLE_EC, lemma="Sample_lossless2")
    if err:
        return f"skipped ({err})"
    baseline = history_line_count()
    rc, out = run([
        "-d", str(SESS), "-tactic-exec", "commit_chain", "-c",
        "proc. seq 1 2 : (={ret}). intentionally_malformed_xyz.",
    ])
    accepted = parse_accepted_count(out)
    h = history_line_count() - baseline
    if h != 0:
        return (f"FAILED: default rollback should leave history "
                f"unchanged, but got {h} new lines\n{out[-400:]}")
    return f"passed (accepted={accepted} pre-rollback, history_added=0)"


def case_middle_no_progress_keep():
    """Chain with a no-op tactic in the middle. The no-op auto-reverts
    in append_block. With --keep-on-fail, the prefix is preserved."""
    err = fresh_session(SAMPLE_EC, lemma="Sample_lossless2")
    if err:
        return f"skipped ({err})"
    baseline = history_line_count()
    rc, out = run([
        "-d", str(SESS), "-tactic-exec", "commit_chain", "--keep-on-fail", "-c",
        # `proc.` again is a no-op once we're already inside proc
        "proc. seq 1 2 : (={ret}). proc.",
    ])
    accepted = parse_accepted_count(out)
    h = history_line_count() - baseline
    if accepted != 2 or h != 2:
        return (f"FAILED: expected accepted=2 history_added=2, "
                f"got accepted={accepted} history_added={h}\n{out[-400:]}")
    return f"passed (accepted={accepted}, history_added={h})"


def case_first_no_progress():
    """Chain where the FIRST tactic is a no-op. accepted=0, history
    should not grow."""
    err = fresh_session(SAMPLE_EC, lemma="Sample_lossless2")
    if err:
        return f"skipped ({err})"
    # Force the goal into pRHL state already-past-proc
    rc, out = run([
        "-d", str(SESS), "-tactic-exec", "commit", "-c", "proc.",
    ])
    if rc != 0:
        return f"skipped (proc setup failed: {out[-200:]})"
    baseline = history_line_count()
    # `proc.` again is a no-op; the chain should fail on iter 1.
    rc, out = run([
        "-d", str(SESS), "-tactic-exec", "commit_chain", "--keep-on-fail", "-c",
        "proc. seq 1 2 : (={ret}).",
    ])
    accepted = parse_accepted_count(out)
    h = history_line_count() - baseline
    if accepted != 0:
        return f"FAILED: expected accepted=0, got {accepted}\n{out[-400:]}"
    if h != 0:
        return f"FAILED: history grew by {h}\n{out[-400:]}"
    return f"passed (accepted=0, history_added=0)"


def case_ambient_goal_chain():
    """Chain in an ambient (non-pRHL) goal. Different goal-type code
    path through `_extract_goal` and `detect_no_progress`. Open the
    Dice4_6 prD4 lemma — its body is `forall k &m, Pr[...] = ...`,
    an ambient goal."""
    err = fresh_session(DICE_EC, lemma="prD4")
    if err:
        return f"skipped ({err})"
    baseline = history_line_count()
    # `move=> k &m.` introduces both binders. `trivial.` won't close
    # the Pr equality; force a parse error after a real step.
    rc, out = run([
        "-d", str(SESS), "-tactic-exec", "commit_chain", "--keep-on-fail", "-c",
        "move=> k &m. intentionally_malformed_xyz.",
    ])
    accepted = parse_accepted_count(out)
    h = history_line_count() - baseline
    if accepted != 1:
        return f"FAILED: expected accepted=1, got {accepted}\n{out[-400:]}"
    if h != accepted:
        return (f"FAILED: accepted={accepted} history_added={h}\n"
                f"{out[-400:]}")
    return f"passed (accepted={accepted}, history_added={h})"


def case_chain_two_sequential_no_progress():
    """Chain with TWO sequential no-ops. The first auto-reverts and
    the chain stops there. accepted=N-1 doesn't apply because the
    first no-op fires. Verify the line-count consistency."""
    err = fresh_session(SAMPLE_EC, lemma="Sample_lossless2")
    if err:
        return f"skipped ({err})"
    rc, out = run([
        "-d", str(SESS), "-tactic-exec", "commit", "-c", "proc.",
    ])
    if rc != 0:
        return f"skipped (proc setup failed: {out[-200:]})"
    baseline = history_line_count()
    rc, out = run([
        "-d", str(SESS), "-tactic-exec", "commit_chain", "--keep-on-fail", "-c",
        "proc. proc.",   # both no-ops
    ])
    accepted = parse_accepted_count(out)
    h = history_line_count() - baseline
    if h != accepted:
        return (f"FAILED: accepted={accepted} history_added={h}\n"
                f"{out[-400:]}")
    return f"passed (accepted={accepted}, history_added={h})"


def case_qed_at_end():
    """Chain that closes the goal with qed. accepted should equal
    chain length and history should grow accordingly."""
    err = fresh_session(TRIVIAL_EC, lemma="native_implicit_goal")
    if err:
        return f"skipped ({err})"
    baseline = history_line_count()
    rc, out = run([
        "-d", str(SESS), "-tactic-exec", "commit_chain", "-c",
        "move=> _. trivial. qed.",
    ])
    accepted = parse_accepted_count(out)
    h = history_line_count() - baseline
    if accepted < 0:
        return f"FAILED: no accepted count parsed\n{out[-400:]}"
    if accepted != 3:
        return (f"FAILED: expected accepted=3 (full chain), got {accepted}\n"
                f"{out[-400:]}")
    if h != accepted:
        return (f"FAILED: accepted={accepted} history_added={h}\n"
                f"{out[-400:]}")
    return f"passed (accepted={accepted}, history_added={h})"


def case_long_chain_mixed():
    """A 5-tactic chain mixing successes and a final failure. Mirrors
    the empirical step3 case (chain of structural tactics)."""
    err = fresh_session(SAMPLE_EC, lemma="Sample_lossless2")
    if err:
        return f"skipped ({err})"
    baseline = history_line_count()
    rc, out = run([
        "-d", str(SESS), "-tactic-exec", "commit_chain", "--keep-on-fail", "-c",
        "proc. seq 1 2 : (={ret}). auto. split. intentionally_malformed_xyz.",
    ])
    accepted = parse_accepted_count(out)
    h = history_line_count() - baseline
    if accepted < 0:
        return f"FAILED: no accepted count parsed\n{out[-400:]}"
    if h != accepted:
        return (f"FAILED: accepted={accepted} history_added={h}\n"
                f"{out[-400:]}")
    return f"passed (accepted={accepted}, history_added={h})"


def case_daemon_rejection_arity():
    """Trigger a daemon-side rejection (accepted=False with [critical]
    error) by calling a lemma with wrong arity. This is the silent
    rollback path that the prior `auto_reverted` marker missed —
    history is rolled back BUT no marker is emitted. The chain must
    notice via the line-count signal."""
    err = fresh_session(SAMPLE_EC, lemma="Sample_lossless2")
    if err:
        return f"skipped ({err})"
    baseline = history_line_count()
    # `apply (sample_ll _ _).` references a real lemma but with the
    # wrong number of arguments. The daemon should respond with
    # accepted=False + a [critical]/[error] reason and roll back the
    # speculative history append.
    rc, out = run([
        "-d", str(SESS), "-tactic-exec", "commit_chain", "--keep-on-fail", "-c",
        "proc. seq 1 2 : (={ret}). apply (sample_ll _ _ _ _).",
    ])
    accepted = parse_accepted_count(out)
    h = history_line_count() - baseline
    if accepted != 2:
        return f"FAILED: expected accepted=2, got {accepted}\n{out[-500:]}"
    if h != accepted:
        return (f"FAILED: accepted={accepted} history_added={h}\n"
                f"{out[-500:]}")
    return f"passed (accepted={accepted}, history_added={h})"


def case_back_to_back_chains():
    """Run two chains in sequence. Verify state consistency: the second
    chain's baseline equals the first chain's accepted count."""
    err = fresh_session(SAMPLE_EC, lemma="Sample_lossless2")
    if err:
        return f"skipped ({err})"
    baseline_0 = history_line_count()
    rc, out = run([
        "-d", str(SESS), "-tactic-exec", "commit_chain", "-c",
        "proc. seq 1 2 : (={ret}).",
    ])
    accepted_1 = parse_accepted_count(out)
    h_1 = history_line_count() - baseline_0
    if accepted_1 != 2 or h_1 != 2:
        return f"FAILED on first chain: accepted={accepted_1} h={h_1}\n{out[-300:]}"

    baseline_1 = history_line_count()
    rc, out = run([
        "-d", str(SESS), "-tactic-exec", "commit_chain", "--keep-on-fail", "-c",
        "auto. intentionally_malformed_xyz.",
    ])
    accepted_2 = parse_accepted_count(out)
    h_2 = history_line_count() - baseline_1
    if accepted_2 != 1 or h_2 != accepted_2:
        return (f"FAILED on second chain: accepted={accepted_2} h={h_2}\n"
                f"{out[-300:]}")
    return f"passed (chain1 accepted={accepted_1}, chain2 accepted={accepted_2})"


def case_different_lemma():
    """Chain on a different lemma in the same file (Dice4_6 prD6,
    structurally distinct from prD4) to exercise the per-lemma
    extraction + chain interaction."""
    err = fresh_session(DICE_EC, lemma="prD6")
    if err:
        return f"skipped ({err})"
    baseline = history_line_count()
    rc, out = run([
        "-d", str(SESS), "-tactic-exec", "commit_chain", "--keep-on-fail", "-c",
        "move=> k &m. byphoare=> //. intentionally_malformed_xyz.",
    ])
    accepted = parse_accepted_count(out)
    h = history_line_count() - baseline
    if accepted < 1:
        return f"FAILED: expected accepted>=1, got {accepted}\n{out[-400:]}"
    if h != accepted:
        return f"FAILED: accepted={accepted} history_added={h}\n{out[-400:]}"
    return f"passed (accepted={accepted}, history_added={h})"


def case_daemon_disabled():
    """Re-run the keep-on-fail middle-error scenario with the daemon
    disabled (subprocess fallback). The fix should be valid in BOTH
    code paths: subprocess never auto-rolls-back on rejection, so
    tactic_committed=True for parse errors → step_up correctly fires."""
    err = fresh_session(SAMPLE_EC, lemma="Sample_lossless2")
    if err:
        return f"skipped ({err})"
    baseline = history_line_count()
    rc, out = run([
        "-d", str(SESS), "-tactic-exec", "commit_chain", "--keep-on-fail", "-c",
        "proc. seq 1 2 : (={ret}). intentionally_malformed_xyz.",
    ], env_extra={"EC_DAEMON_DISABLE": "1"})
    accepted = parse_accepted_count(out)
    h = history_line_count() - baseline
    if accepted != 2:
        return f"FAILED: expected accepted=2, got {accepted}\n{out[-400:]}"
    if h != accepted:
        return f"FAILED: accepted={accepted} history_added={h}\n{out[-400:]}"
    return f"passed (accepted={accepted}, history_added={h})"


def main():
    print(f"Running chain consistency tests...")
    print(f"  ROOT = {ROOT}")
    print()

    cases = [
        ("full-success",               case_full_success),
        ("first-fails-keep",           case_first_tactic_fails_keep),
        ("last-fails-keep",            case_last_tactic_fails_keep),
        ("middle-fails-no-keep",       case_middle_fails_no_keep),
        ("middle-no-progress-keep",    case_middle_no_progress_keep),
        ("first-no-progress",          case_first_no_progress),
        ("ambient-goal-chain",         case_ambient_goal_chain),
        ("two-sequential-no-progress", case_chain_two_sequential_no_progress),
        ("qed-at-end",                 case_qed_at_end),
        ("long-chain-mixed",           case_long_chain_mixed),
        ("daemon-rejection-arity",     case_daemon_rejection_arity),
        ("back-to-back-chains",        case_back_to_back_chains),
        ("different-lemma",            case_different_lemma),
        ("daemon-disabled",            case_daemon_disabled),
    ]

    results = {}
    for name, fn in cases:
        print(f"Case: {name}")
        try:
            res = fn()
        except Exception as e:
            res = f"FAILED (exception): {e}"
        print(f"  → {res}")
        results[name] = res
        print()

    # Cleanup
    if SESS.exists():
        shutil.rmtree(SESS)

    print("=== Summary ===")
    failed = []
    skipped = []
    for name, res in results.items():
        if "FAILED" in res:
            failed.append(name)
        elif "skipped" in res:
            skipped.append(name)
    total = len(results)
    print(f"  total:   {total}")
    print(f"  passed:  {total - len(failed) - len(skipped)}")
    print(f"  skipped: {len(skipped)}{' ' + str(skipped) if skipped else ''}")
    print(f"  failed:  {len(failed)}{' ' + str(failed) if failed else ''}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())


import pytest as _pytest


def test_accepted_count_parser_accepts_only_current_structured_delivery() -> None:
    current = {
        "execution": {"mode": "commit_chain", "accepted_count": 2},
        "result": {"status": "partial_success"},
        "workspace": {"view": {"current_goal": {"lines": ["goal"]}}},
    }
    rendered = "[TACTIC-EXECUTION-RESULT]\n" + json.dumps(current) + "\n"
    assert parse_accepted_count(rendered) == 2

    historical_markers = (
        "state after 2 accepted tactics",
        "All 2 tactics accepted",
        "[chain] Stopped after 2/3 tactics",
    )
    for marker in historical_markers:
        with _pytest.raises(AssertionError):
            parse_accepted_count(marker)


try:
    _MANAGED_EC_AVAILABLE = shutil.which(
        "easycrypt", path=get_ec_env().get("PATH")
    ) is not None
except RuntimeError:
    _MANAGED_EC_AVAILABLE = False


@_pytest.mark.skipif(not _MANAGED_EC_AVAILABLE,
                     reason="repository-managed EasyCrypt is unavailable")
def test_all_cases() -> None:
    """pytest entry: the case() harness's failure count must be zero.

    This file predates the pytest convention (custom case()/main()); the
    wrapper makes its coverage visible to `pytest tests/` — it had been
    silently collected as zero tests.
    """
    assert main() == 0
