"""Integration tests for ECSubprocess.batch_try backed by the warm prober.

Spawns a real `easycrypt -emacs` (skipped if not on PATH). The contract under
test: warm batch probing must agree EXACTLY with spawn-fresh `try_tactic`
(accepted / goal-closed / error), be reused across batches until a commit, and
fall back to spawn-fresh when disabled.
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

pytestmark = pytest.mark.skipif(
    shutil.which("easycrypt") is None,
    reason="easycrypt not on PATH (run inside the opam switch)")

from core.easycrypt.ec_daemon import ECSubprocess  # type: ignore  # noqa: E402

THEORIES = str(ROOT / "easycrypt-src" / "theories")

_SRC = """\
require import AllCore.

lemma warm_conj (a b c : int) : a = a /\\ b = b /\\ c = c.
proof.
smt().
qed.
"""

_TACTICS = ["split.", "apply does_not_exist.", "trivial.", "rewrite nope.", "done."]


@pytest.fixture
def opened_ec():
    f = Path(tempfile.mktemp(suffix=".ec"))
    f.write_text(_SRC, encoding="utf-8")
    ec = ECSubprocess([THEORIES])
    ec.spawn()
    ec.load_context_and_enter_proof(f, "warm_conj")
    try:
        yield ec
    finally:
        ec.close()


def _key(o):
    return (o.accepted, o.goal_after.is_closed, o.error is not None)


def test_batch_try_agrees_with_spawn_fresh(opened_ec):
    ec = opened_ec
    fresh = [ec._try_tactic_fresh(t) for t in _TACTICS]   # genuine spawn-fresh
    warm = ec.batch_try(_TACTICS)                         # warm run-then-undo
    assert ec._warm is not None and ec._warm.alive  # warm path was taken
    assert len(warm) == len(_TACTICS)
    for t, fr, wr in zip(_TACTICS, fresh, warm):
        assert _key(fr) == _key(wr), f"mismatch on {t!r}: {_key(fr)} vs {_key(wr)}"


def test_try_tactic_warm_agrees_with_fresh(opened_ec):
    # The single try_tactic path is warm-backed too; it must agree with the
    # spawn-fresh implementation tactic-for-tactic.
    ec = opened_ec
    for t in _TACTICS:
        fr = ec._try_tactic_fresh(t)
        wr = ec.try_tactic(t)
        assert _key(fr) == _key(wr), f"mismatch on {t!r}: {_key(fr)} vs {_key(wr)}"
    assert ec._warm is not None and ec._warm.alive   # warm built + reused


def test_warm_is_reused_then_invalidated_on_commit(opened_ec):
    ec = opened_ec
    ec.batch_try(_TACTICS)
    warm1 = ec._warm
    assert warm1 is not None and warm1.alive
    ec.batch_try(_TACTICS)
    assert ec._warm is warm1            # same warm process reused, not rebuilt
    ec.execute("split.")                # a commit moves the state
    assert ec._warm is None             # warm prober invalidated


def test_warm_disabled_falls_back_to_spawn_fresh(opened_ec):
    ec = opened_ec
    prev = os.environ.get("EC_WARM_PROBE")
    os.environ["EC_WARM_PROBE"] = "0"
    try:
        warm = ec.batch_try(_TACTICS)
        assert ec._warm is None         # disabled: no warm prober built
        # still correct via spawn-fresh
        fresh = [ec.try_tactic(t) for t in _TACTICS]
        for fr, wr in zip(fresh, warm):
            assert _key(fr) == _key(wr)
    finally:
        if prev is None:
            os.environ.pop("EC_WARM_PROBE", None)
        else:
            os.environ["EC_WARM_PROBE"] = prev


def test_try_chain_warm_agrees_with_fresh(opened_ec):
    # The chain path is warm-backed too (run the chain + one undo-to-base); it
    # must agree with spawn-fresh on accepted / final_closed / failed_at.
    ec = opened_ec
    chains = [
        ["split.", "trivial."],            # multi-step
        ["apply nope.", "trivial."],       # first step fails
        ["smt()."],                        # closes the goal
        ["trivial.", "split."],
    ]
    for ch in chains:
        fr = ec._try_chain_fresh(ch)
        wr = ec.try_chain(ch)
        got_fr = (fr.accepted, fr.final_closed, fr.failed_at)
        got_wr = (wr.accepted, wr.final_closed, wr.failed_at)
        assert got_fr == got_wr, f"chain {ch}: fresh={got_fr} warm={got_wr}"
    assert ec._warm is not None and ec._warm.alive


def test_goal_closing_tactic_in_batch(opened_ec):
    ec = opened_ec
    # `smt()` closes `a=a /\ b=b /\ c=c`; the batch must report it accepted+closed
    # and (critically) recover for the next probe.
    out = ec.batch_try(["smt().", "split."])
    assert out[0].accepted and out[0].goal_after.is_closed
    assert out[1].accepted                # state restored; split still applies
    assert ec._warm is not None and ec._warm.alive
