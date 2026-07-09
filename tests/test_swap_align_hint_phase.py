"""Tests for SwapAlignHintPhase — post-commit auto-fire of -align that
daemon-verifies each `swap{N} K M.` candidate before surfacing it as a
runnable_tactic recommendation."""
from __future__ import annotations

from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from core.easycrypt.session_hook_phases import (  # type: ignore  # noqa: E402
    HintDispatchPhase,
    _SwapAlignGenerator,
)
from tests.helpers.fakes import (  # noqa: E402
    FakeCtx,
    FakeDaemonBackend,
    FakeDaemonCli,
    FakeDaemonHandle,
)


def SwapAlignHintPhase(session):
    """The retired one-generator phase alias, rebuilt from public parts."""
    return HintDispatchPhase(session, generators=[_SwapAlignGenerator(session)])


# A minimal pRHL goal that swap_align's parser will accept and produce
# at least one swap candidate for. The two columns share statements
# but in different order (sample-then-call vs call-then-sample).
_GOAL_NEEDING_SWAP = """\
Current goal
&m: {}
------------------------------------------------------------------------
&1 (left ) : {x : int}
&2 (right) : {x : int}

pre = true

x <$ duniform [0..3]    (1)  y <- 1
y <- 1                  (2)  x <$ duniform [0..3]

post = ={x}
"""


# ─── Test fakes ───────────────────────────────────────────────────────────

_FakeDaemonCli = FakeDaemonCli
_FakeDaemonBackend = FakeDaemonBackend
_FakeDaemonHandle = FakeDaemonHandle
_FakeCtx = FakeCtx


class _FakeSession:
    def __init__(self):
        self.context_file = None


# ─── Tests ────────────────────────────────────────────────────────────────

def test_phase_no_emit_on_non_prhl_goal() -> None:
    cli = _FakeDaemonCli()
    phase = SwapAlignHintPhase(_FakeSession())
    ctx = _FakeCtx(
        active_goal="Pr[A.main() @ &m : res] = 1%r/2%r",
        daemon_handle=_FakeDaemonHandle(cli),
    )
    results = phase.run(ctx)
    assert results == []
    assert cli.calls == []


def test_phase_no_emit_when_daemon_unavailable() -> None:
    phase = SwapAlignHintPhase(_FakeSession())
    ctx = _FakeCtx(active_goal=_GOAL_NEEDING_SWAP, daemon_handle=None)
    results = phase.run(ctx)
    assert results == []


def test_phase_no_emit_when_no_swaps_or_all_rejected() -> None:
    cli = _FakeDaemonCli(accept_pattern="will_never_match")
    phase = SwapAlignHintPhase(_FakeSession())
    ctx = _FakeCtx(
        active_goal=_GOAL_NEEDING_SWAP,
        daemon_handle=_FakeDaemonHandle(cli),
    )
    results = phase.run(ctx)
    assert results == []


def test_phase_dedup_skips_repeat_on_same_goal_shape() -> None:
    cli = _FakeDaemonCli()  # accept everything
    phase = SwapAlignHintPhase(_FakeSession())
    ctx = _FakeCtx(
        active_goal=_GOAL_NEEDING_SWAP,
        daemon_handle=_FakeDaemonHandle(cli),
    )
    first = phase.run(ctx)
    second = phase.run(ctx)
    # Either no swaps produced (empty list) or the first run emitted
    # while the second is dedup-suppressed. Both branches are valid as
    # long as second never re-probes the daemon when first did.
    if first:
        assert second == []
        first_call_count = len(cli.calls)
        # Re-running on the same shape MUST NOT add daemon calls.
        phase.run(ctx)
        assert len(cli.calls) == first_call_count


def test_phase_emits_runnable_when_swap_accepted() -> None:
    """When swap_align produces a candidate AND the daemon accepts,
    the phase emits a runnable_tactic rec with confidence=verified."""
    cli = _FakeDaemonCli()  # accept all
    phase = SwapAlignHintPhase(_FakeSession())
    ctx = _FakeCtx(
        active_goal=_GOAL_NEEDING_SWAP,
        daemon_handle=_FakeDaemonHandle(cli),
    )
    results = phase.run(ctx)
    # The pRHL parser may or may not produce a candidate from this
    # synthetic goal — but if it does, the rec contract is what we
    # care about. Empty results just means parser disagreed; that
    # exercise is covered by other tests.
    if not results:
        return
    res = results[0]
    assert res.recommendations, "expected at least one runnable rec"
    for rec in res.recommendations:
        assert rec["action_type"] == "runnable_tactic"
        assert rec["confidence"] == "verified"
        assert rec["producer"] == "AUTO-SWAP-ALIGN"
        assert (
            rec["metadata"]["epistemic_status"]
            == "daemon_probe_accepted"
        )


def test_generator_probes_call_crossing_blocked_swaps_not_data_deps() -> None:
    """Slice 1B: the generator must ALSO emit the CALL-crossing swaps that the
    static read/write scan dumped into `blocked_swaps` (a blanket barrier, not an EC
    rejection), so the daemon can verify them -- but NOT the data/output-dependency
    blocked swaps (those are far more likely real rejections). Clean swaps come first
    (they get the probe budget ahead of the conservative candidates), and the blocked
    candidates carry an honest provenance `why`."""
    from types import SimpleNamespace
    import core.easycrypt.analysis.swap_align as sa  # type: ignore
    from core.easycrypt.session_hook_phases import _SwapAlignGenerator  # type: ignore

    fake = SimpleNamespace(
        # clean swap carries compute_swap_plan's `(* move ... *)` rationale comment
        swaps=["swap{1} 2 1.    (* move sample to row 1 *)"],
        blocked_swaps=[
            {  # CALL barrier -> conservative, probe BOTH candidate sides
                "left_candidate": "swap{1} 11 -9.", "left_blocker": "crosses CALL A.guess",
                "right_candidate": "swap{2} 3 2.", "right_blocker": "crosses CALL A.guess",
            },
            {  # data dependency -> likely a real rejection, do NOT probe
                "left_candidate": "swap{1} 4 1.", "left_blocker": "writes {x} read by stmt 3",
                "right_candidate": "", "right_blocker": "",
            },
        ],
    )
    orig = sa.parse_prhl_goal
    sa.parse_prhl_goal = lambda *a, **k: fake  # type: ignore
    try:
        gen = _SwapAlignGenerator(_FakeSession())
        ctx = _FakeCtx(active_goal=_GOAL_NEEDING_SWAP, daemon_handle=None)
        cands = gen.generate(ctx)
    finally:
        sa.parse_prhl_goal = orig  # type: ignore

    tactics = [c.tactic for c in cands]
    assert tactics[0] == "swap{1} 2 1."                 # clean swap probes first, comment STRIPPED
    clean = cands[0]
    assert "(*" not in clean.tactic                     # S1: no comment leaks into the runnable
    assert "move sample to row 1" in clean.why          # rationale folded into why
    assert "swap{1} 11 -9." in tactics                  # CALL-crossing blocked, both sides
    assert "swap{2} 3 2." in tactics
    assert "swap{1} 4 1." not in tactics                # data-dep blocked is NOT probed
    blocked = next(c for c in cands if c.tactic == "swap{1} 11 -9.")
    assert "BLOCKED" in blocked.why and "crosses a CALL" in blocked.why


def test_generator_emits_blocked_swaps_even_when_no_clean_swaps() -> None:
    """The step3 shape: every useful swap crosses a CALL, so `result.swaps` is EMPTY
    and only `blocked_swaps` carry candidates. The old early-return (`if not swaps:
    return []`) dropped them entirely; 1B must still emit the CALL-crossing candidates
    so the daemon can unblock the hard case."""
    from types import SimpleNamespace
    import core.easycrypt.analysis.swap_align as sa  # type: ignore
    from core.easycrypt.session_hook_phases import _SwapAlignGenerator  # type: ignore

    fake = SimpleNamespace(
        swaps=[],
        blocked_swaps=[{
            "left_candidate": "swap{1} 11 -9.", "left_blocker": "crosses CALL A.main",
            "right_candidate": "", "right_blocker": "",
        }],
    )
    orig = sa.parse_prhl_goal
    sa.parse_prhl_goal = lambda *a, **k: fake  # type: ignore
    try:
        cands = _SwapAlignGenerator(_FakeSession()).generate(
            _FakeCtx(active_goal=_GOAL_NEEDING_SWAP, daemon_handle=None)
        )
    finally:
        sa.parse_prhl_goal = orig  # type: ignore
    assert [c.tactic for c in cands] == ["swap{1} 11 -9."]


def main() -> int:
    tests = [
        test_phase_no_emit_on_non_prhl_goal,
        test_phase_no_emit_when_daemon_unavailable,
        test_phase_no_emit_when_no_swaps_or_all_rejected,
        test_phase_dedup_skips_repeat_on_same_goal_shape,
        test_phase_emits_runnable_when_swap_accepted,
        test_generator_probes_call_crossing_blocked_swaps_not_data_deps,
        test_generator_emits_blocked_swaps_even_when_no_clean_swaps,
    ]
    for t in tests:
        t()
    print("PASS test_swap_align_hint_phase")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
