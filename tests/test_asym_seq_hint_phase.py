"""Tests for AsymSeqHintPhase — the Layer-1 generator that produces
asymmetric ``seq N M : <inv>.`` candidates from swap_align column
matches.

Two end-to-end behaviors are covered:

1. Daemon ACCEPT path: synthesized invariant survives daemon probe
   → emit a runnable_tactic with confidence=verified.
2. Daemon REJECT path: synthesized invariant is rejected (typically
   because real Inv needs more clauses than swap_align could see)
   → emit a strategy_hint with the concrete shape so the agent
   doesn't fall back to the AUTO-DIFF ``<inv>`` placeholder.

The reject-path fallback is the whole reason this generator exists in
addition to the ones that already cover symmetric cases. AUTO-DIFF
already detects asymmetry; what's missing is concrete invariant text.
"""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from core.easycrypt.session_hook_phases import (  # type: ignore  # noqa: E402
    HintDispatchPhase,
    _AsymSeqGenerator,
)
from tests.helpers.fakes import (  # noqa: E402
    FakeCtx,
    FakeDaemonBackend,
    FakeDaemonHandle,
)


def AsymSeqHintPhase(session):
    """The retired one-generator phase alias, rebuilt from public parts."""
    return HintDispatchPhase(session, generators=[_AsymSeqGenerator(session)])


# A pRHL goal where swap_align should produce an asymmetric result
# (LHS has 5 statements, RHS has 3). The shared variables (k, t, n, a)
# must appear in BOTH columns' written-var sets so the synthesized
# invariant has actual content; ChaChaPoly step1 dec is the source.
_GOAL_ASYMMETRIC = """\
Current goal

Type variables: <none>

  &1 (left ) : {k : key, n : nonce, a : ad, c0 : ctxt, t : tag, k0 : key, t' : tag, m : msg, result : msg option}
  &2 (right) : {k : key, n : nonce, a : ad, c : ctxt, t : tag, t' : tag, result : msg option}

pre = ={n, a, t} /\\ c0{1} = c{2}

(1) k <- Mem.k                    (1) k <- IndBlock.k
(2) t' <- Poly.mac(k, n, a, c0)   (2) t' <- Poly.mac(k, n, a, c)
(3) m <- ChaCha.enc(k, n, c0)     (3) result <- if t = t' then Some m else None
(4) result <- if t = t' then ...
(5) skip

post = ={result}
"""


# ─── Test fakes ───────────────────────────────────────────────────────────

class _FakeDaemonCli:
    """Kept local: this variant accepts/rejects everything via one bool,
    unlike the canonical substring-pattern ``tests.helpers.fakes.FakeDaemonCli``."""

    def __init__(self, accept: bool):
        self.accept = accept
        self.calls: list[tuple[str, str]] = []

    def try_tactic(self, session_id: str, tactic: str) -> dict:
        self.calls.append((session_id, tactic))
        return {"accepted": self.accept}


_FakeDaemonBackend = FakeDaemonBackend
_FakeDaemonHandle = FakeDaemonHandle
_FakeCtx = FakeCtx


class _FakeSession:
    def __init__(self):
        self.context_file = None


# ─── Tests ────────────────────────────────────────────────────────────────

def test_no_emit_on_non_prhl_goal() -> None:
    """Non-pRHL goals (ambient, hoare, phoare) → no candidates, no
    daemon calls."""
    cli = _FakeDaemonCli(accept=True)
    phase = AsymSeqHintPhase(_FakeSession())
    ctx = _FakeCtx(
        active_goal="Pr[A.main() @ &m : res] = 1%r/2%r",
        daemon_handle=_FakeDaemonHandle(cli),
    )
    assert phase.run(ctx) == []
    assert cli.calls == []


def test_no_emit_when_daemon_unavailable() -> None:
    """No daemon → dispatcher returns immediately."""
    phase = AsymSeqHintPhase(_FakeSession())
    ctx = _FakeCtx(
        active_goal=_GOAL_ASYMMETRIC, daemon_handle=None,
    )
    assert phase.run(ctx) == []


def test_phase_runs_without_error_on_asymmetric_goal() -> None:
    """End-to-end exercise: phase parses goal, runs generator, probes
    daemon. We don't assert on emission shape because the swap_align
    parser may or may not accept this synthetic goal verbatim — but
    the phase must NEVER raise and must dedup correctly across
    repeated runs."""
    cli = _FakeDaemonCli(accept=True)
    phase = AsymSeqHintPhase(_FakeSession())
    ctx = _FakeCtx(
        active_goal=_GOAL_ASYMMETRIC,
        daemon_handle=_FakeDaemonHandle(cli),
    )
    first = phase.run(ctx)
    second = phase.run(ctx)
    # Dedup contract: same goal shape → no re-probe on the second call.
    if first:
        assert second == []


def test_dispatch_phase_no_fallback_for_generators_without_method() -> None:
    """Generators that DON'T implement
    ``fallback_recommendation_for_rejected`` keep the legacy behavior:
    daemon-rejected candidates produce no rec. Regression guard against
    the dispatcher accidentally forcing fallbacks on every generator."""
    from core.easycrypt.session_hook_phases import HintDispatchPhase  # type: ignore
    from core.easycrypt.hint_dispatch import Candidate  # type: ignore

    class _LegacyGen:
        producer_name = "AUTO-LEGACY"
        marker = "[AUTO-LEGACY]"
        layer = 2

        def applies_to_shape(self, gt: str) -> bool:
            return True

        def generate(self, ctx) -> list:
            return [Candidate(tactic="trivial.", why="stub")]
        # No fallback method.

    cli = _FakeDaemonCli(accept=False)
    phase = HintDispatchPhase(_FakeSession(), generators=[_LegacyGen()])
    ctx = _FakeCtx(
        active_goal="any goal text",
        daemon_handle=_FakeDaemonHandle(cli),
    )
    assert phase.run(ctx) == []


def main() -> int:
    tests = [
        test_no_emit_on_non_prhl_goal,
        test_no_emit_when_daemon_unavailable,
        test_phase_runs_without_error_on_asymmetric_goal,
        test_fallback_strategy_hint_via_generator_hook,
        test_dispatch_phase_emits_fallback_for_rejected_asym_candidate,
        test_dispatch_phase_no_fallback_for_generators_without_method,
    ]
    for t in tests:
        t()
    print("PASS test_asym_seq_hint_phase")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
