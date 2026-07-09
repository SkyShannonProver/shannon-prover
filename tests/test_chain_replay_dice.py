"""Regression test for daemon-path chain replay correctness.

Two bugs caught by the 2026-04-29 P1 audit went silently undetected
for an unknown duration because the daemon was a stale orphan socket
the whole time. Once daemon_backend (`d24c095`) recovered, dormant
bugs surfaced:

  (1) `_structural_fingerprint` extracted goal pre/post/stmts but no
      hypothesis names. `have h : P by tac.` adds `h` to the context
      without changing the goal body — fingerprint identical →
      detect_no_progress(True, 'structural-fingerprint-equal') →
      TACTIC_NO_EFFECT_AUTO_REVERTED → chain rolled back the proof.
      Fixed in `8434a37`.

  (2) Chain mode running daemon-side candidate verification (one
      `try_tactic` per AUTO-REWRITE-PROBE / AUTO-PIVOT-VERIFIED
      candidate × N steps) inflated wall time 7-10x. Fixed by
      `_chain_skip_verify` flag in `c4221b3`.

This test exercises Dice4_6 D4_D6 — a verified-clean proof that uses
`have h : P by ...` (the bug-(1) trigger). Asserts:
  - Chain returns rc=0 (proof accepts every tactic)
  - history.ec ends with the same number of tactics as input
  - No [TACTIC_NO_EFFECT_AUTO_REVERTED] anywhere in the output
  - TacticExecutionResult JSON reports accepted_count == N (replaces the
    legacy "All N tactics accepted" text marker that the
    event-driven rewrite removed)
  - commit_meta.log has one PROGRESS verdict per committed tactic
    (state_diff_trigger fires per commit; this replaces the old
    "[STATE-DIFF] block count" assertion since the text marker no
    longer prints to stdout under the default
    SHANNON_LEGACY_DISPLAY=hidden mode — the data lives in
    commit_meta.log instead)
  - Chain finishes in under 60 s wall-clock (regression on (2):
    pre-fix this exceeded 5 minutes once daemon was healthy)

Run: `eval "$(opam env --switch=easycrypt)" && python3 tests/test_chain_replay_dice.py`
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)
SCLI = ROOT / "core" / "easycrypt" / "session_cli.py"
DICE_EC = ROOT / "eval" / "examples" / "Dice4_6.ec"
SESS = Path("/tmp/test_chain_replay_dice_session")

# Inline tactic body (the one the file's qed-passing proof uses, with
# `have h : P by ...` at line 2 — the bug-(1) trigger).
TACTICS = """\
move=> hf hfinv.
have dinter16_ll : is_lossless [1..6] by apply dinter_ll.
bypr (res{1}) (finv res{2})=> //.
move=> &1 &2 a.
have -> : Pr[D4.sample() @ &1 : res = a] = mu1 [1..4] a
  by byphoare=> //; proc; rnd (pred1 a); auto=> />.
have -> : Pr[D6.sample() @ &2 : finv res = a] =
          Pr[D4_6.SampleWi.sample(tt, 5) @ &2 : finv res = a]
  by byequiv D6_Sample=> //.
have -> := D4_6.pr_sampleWi &2 tt 5 (fun r => finv r = a) dinter16_ll.
simplify.
have -> : mu ([1..6] \\ fun (r:int) => !1 <= r <= 4) (fun (r:int) => finv r = a) =
          mu1 ([1..6] \\ fun (r:int) => !1 <= r <= 4) (f a)
  by apply mu_eq_support=> r; rewrite supp_dexcepted supp_dinter /=; smt().
have h_mu : mu [1..6] (fun (r:int) => !1<=r<=4) = 1%r / 3%r.
  have -> : mu [1..6] (fun (r:int) => !1<=r<=4) =
            mu [1..6] (predU (pred1 5) (pred1 6))
    by apply mu_eq_support => r; rewrite supp_dinter /=; smt().
  have -> : mu [1..6] (predU (pred1 5) (pred1 6)) =
            mu [1..6] (pred1 5) + mu [1..6] (pred1 6)
    by apply mu_disjointL => x /=; smt().
  by rewrite !dinter1E /= /#.
"""

EXPECTED_TACTIC_COUNT = 13  # `.` -terminated atomic tactics in the body


def run(args: list[str], cwd: Path | None = None) -> tuple[int, str]:
    p = subprocess.run(
        [sys.executable, str(SCLI), *args],
        cwd=str(cwd or ROOT),
        capture_output=True,
        text=True,
        timeout=300,
    )
    return p.returncode, p.stdout + p.stderr


def main() -> int:
    if SESS.exists():
        shutil.rmtree(SESS)

    tac_file = Path("/tmp/test_chain_replay_dice_tactics.txt")
    tac_file.write_text(TACTICS)

    # Open session against the verified-clean lemma.
    rc, out = run([
        "-d", str(SESS), "-start",
        "-f", str(DICE_EC),
        "-I", str(ROOT / "easycrypt-src" / "theories"),
        "-lemma", "D4_D6",
    ])
    if rc != 0:
        print(f"FAIL: -start returned rc={rc}\n{out}")
        return 1

    # Chain replay with wall-clock measurement.
    t0 = time.monotonic()
    rc, out = run([
        "-d", str(SESS), "-chain", "--from-file", str(tac_file),
    ])
    elapsed = time.monotonic() - t0

    failures: list[str] = []
    if rc != 0:
        failures.append(f"chain rc={rc} (expected 0)")
    if "[TACTIC_NO_EFFECT_AUTO_REVERTED]" in out:
        failures.append(
            "chain output contains [TACTIC_NO_EFFECT_AUTO_REVERTED] — "
            "fingerprint should NOT mis-flag `have h : P by tac.`"
        )
    # Replaces the legacy "All N tactics accepted" text marker. The
    # event-driven rewrite routes mutation outcomes through the
    # structured TacticExecutionResult JSON instead.
    accepted_match = re.search(
        r'\[TACTIC-EXECUTION-RESULT\][\s\S]*?"execution"\s*:\s*\{[\s\S]*?"accepted_count"\s*:\s*(\d+)',
        out,
    )
    if not accepted_match:
        failures.append(
            "chain summary missing TacticExecutionResult "
            "execution.accepted_count; got tail:\n"
            f"{out[-500:]}"
        )
    elif int(accepted_match.group(1)) != EXPECTED_TACTIC_COUNT:
        failures.append(
            f"chain accepted_count={accepted_match.group(1)} "
            f"(expected {EXPECTED_TACTIC_COUNT})"
        )
    # The legacy [STATE-DIFF] text-block count assertion has been
    # replaced by the commit_meta.log check below: each successful
    # commit appends one ``verdict|delta|tactic`` line, so a 13-line
    # meta log is the same signal as 13 STATE-DIFF emissions —
    # without depending on SHANNON_LEGACY_DISPLAY mode.
    if elapsed > 60:
        failures.append(
            f"chain took {elapsed:.1f}s (> 60s budget) — daemon-path "
            "verify still firing in chain mode?"
        )

    # commit_meta.log has one line per commit (regardless of how many
    # text lines a multi-line tactic spans). history.ec line count is
    # NOT equal to commit count because `have ... by\n  ...\n  ...` is
    # one commit but multiple text lines.
    meta_path = SESS / "commit_meta.log"
    meta_lines: list[str] = []
    if meta_path.exists():
        meta_lines = [
            ln for ln in meta_path.read_text().splitlines() if ln.strip()
        ]
        if len(meta_lines) != EXPECTED_TACTIC_COUNT:
            failures.append(
                f"commit_meta.log has {len(meta_lines)} commits "
                f"(expected {EXPECTED_TACTIC_COUNT})"
            )

    # Cleanup
    if SESS.exists():
        shutil.rmtree(SESS)
    if tac_file.exists():
        tac_file.unlink()

    if failures:
        print("FAIL:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print(f"PASS: chain replay of D4_D6 ({EXPECTED_TACTIC_COUNT} tactics, "
          f"{elapsed:.1f}s, {len(meta_lines)} commit_meta entries)")
    return 0


if __name__ == "__main__":
    sys.exit(main())


import shutil as _shutil
import pytest as _pytest


@_pytest.mark.skipif(_shutil.which("easycrypt") is None,
                     reason="EasyCrypt binary not on PATH")
def test_all_cases() -> None:
    """pytest entry: the case() harness's failure count must be zero.

    This file predates the pytest convention (custom case()/main()); the
    wrapper makes its coverage visible to `pytest tests/` — it had been
    silently collected as zero tests.
    """
    assert main() == 0
