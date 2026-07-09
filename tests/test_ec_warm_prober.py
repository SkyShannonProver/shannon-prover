"""Integration tests for the warm EC prober (run-then-`undo N.`).

These spawn a real `easycrypt -emacs` (skipped if it is not on PATH), so they run
under the EC env: `eval "$(opam env --switch=easycrypt)"` and, for the smt case, a
why3server (the OS sandbox blocks `nice()`, so run unsandboxed).

The point of these tests is the *safety* of warm probing across tactic kinds: a
probe must never leave the warm process drifted (unable to return to the
committed base step) or corrupted — including a failing probe, a goal-closing
probe, an smt-calling probe, and a long run.
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

pytestmark = pytest.mark.skipif(
    shutil.which("easycrypt") is None,
    reason="easycrypt not on PATH (run inside the opam switch)")

from core.easycrypt.ec_warm_prober import WarmProber  # type: ignore  # noqa: E402

THEORIES = str(ROOT / "easycrypt-src" / "theories")

# Family-general synthetic source: a closing goal, a multi-conjunct goal, an
# arithmetic goal for smt. No crypto specifics.
_EC_SRC = """\
require import AllCore.

lemma warm_true : true.
proof.
trivial.
qed.

lemma warm_conj (a b c : int) : a = a /\\ b = b /\\ c = c.
proof.
smt().
qed.

lemma warm_arith (x : int) : x + 0 = x.
proof.
smt().
qed.
"""


def _why3():
    sock = "/tmp/why3ec.sock"
    return sock if os.path.exists(sock) else None


@pytest.fixture
def ec_file(tmp_path):
    f = tmp_path / "warm.ec"
    f.write_text(_EC_SRC, encoding="utf-8")
    return f


def test_open_warms_up_and_records_base_step(ec_file):
    wp = WarmProber([THEORIES], why3_socket=_why3())
    try:
        assert wp.open(ec_file, "warm_conj")
        assert wp.alive and wp.base_step is not None and wp.base_goal
    finally:
        wp.close()
    assert not wp.alive


def test_valid_probe_accepted_and_undo_restores(ec_file):
    wp = WarmProber([THEORIES], why3_socket=_why3())
    try:
        assert wp.open(ec_file, "warm_conj")
        base = wp.base_step
        r = wp.probe("split.")            # multi-subgoal: advances, applies
        assert r.accepted
        assert wp.alive and wp.base_step == base   # rolled back, no drift
    finally:
        wp.close()


def test_failing_probe_rejected_without_corruption(ec_file):
    wp = WarmProber([THEORIES], why3_socket=_why3())
    try:
        assert wp.open(ec_file, "warm_conj")
        base = wp.base_step
        bad = wp.probe("apply some_lemma_that_does_not_exist.")
        assert not bad.accepted and bad.error          # rejected, error reported
        assert wp.alive and wp.base_step == base        # not advanced, not dead
        good = wp.probe("split.")                        # still works afterwards
        assert good.accepted and wp.alive
    finally:
        wp.close()


def test_goal_closing_probe_then_undo_reenters(ec_file):
    wp = WarmProber([THEORIES], why3_socket=_why3())
    try:
        assert wp.open(ec_file, "warm_true")
        base = wp.base_step
        r = wp.probe("trivial.")          # closes `true`
        assert r.accepted
        assert wp.alive and wp.base_step == base    # undo re-entered the proof
        again = wp.probe("trivial.")       # still probeable after a closing probe
        assert again.accepted and wp.alive
    finally:
        wp.close()


def test_smt_probe_does_not_drift(ec_file):
    if _why3() is None:
        pytest.skip("why3server socket /tmp/why3ec.sock not present")
    wp = WarmProber([THEORIES], why3_socket=_why3())
    try:
        assert wp.open(ec_file, "warm_arith")
        base = wp.base_step
        r = wp.probe("smt().")            # spawns why3 work; must not drift/corrupt
        assert wp.alive and wp.base_step == base
        if r.accepted:                    # when why3 is healthy it closes x+0=x
            again = wp.probe("smt().")
            assert again.accepted and wp.alive
    finally:
        wp.close()


def test_100_consecutive_probes_no_drift(ec_file):
    wp = WarmProber([THEORIES], why3_socket=_why3())
    try:
        assert wp.open(ec_file, "warm_conj")
        base = wp.base_step
        probes = ["split.", "apply nope.", "trivial.", "rewrite nope.", "move=> h."]
        for i in range(100):
            wp.probe(probes[i % len(probes)])
            assert wp.alive, f"prober died at probe {i}"
            assert wp.base_step == base, f"drifted at probe {i}"
    finally:
        wp.close()
