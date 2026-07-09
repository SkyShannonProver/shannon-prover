"""Tests for the Layer-1 hint dispatcher."""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)


from core.easycrypt.hint_dispatch import (  # type: ignore  # noqa: E402
    Candidate,
    candidates_to_recommendations,
    dispatch_hints,
)
from core.easycrypt.session_hook_phases import (  # type: ignore  # noqa: E402
    HintDispatchPhase,
    _AbstractAdvCallGenerator,
    _SwapAlignGenerator,
    make_default_hint_dispatch_phase,
)
from tests.helpers.fakes import (  # noqa: E402
    FakeCtx,
    FakeDaemonBackend,
    FakeDaemonCli,
    FakeDaemonHandle,
)


# ─── Test fakes ───────────────────────────────────────────────────────────

_FakeDaemonCli = FakeDaemonCli
_FakeDaemonBackend = FakeDaemonBackend
_FakeDaemonHandle = FakeDaemonHandle
_FakeCtx = FakeCtx


class _StubGenerator:
    """Minimal HintGenerator for dispatcher tests."""

    def __init__(
        self,
        producer_name: str,
        candidates: list[Candidate],
        applies_shapes: tuple[str, ...] = ("pRHL",),
    ):
        self.producer_name = producer_name
        self.marker = f"[{producer_name}]"
        self.layer = 2
        self._candidates = candidates
        self._applies_shapes = applies_shapes
        self.generate_calls = 0

    def applies_to_shape(self, goal_type: str) -> bool:
        return goal_type in self._applies_shapes

    def generate(self, ctx) -> list[Candidate]:
        self.generate_calls += 1
        return list(self._candidates)


# ─── Tests ────────────────────────────────────────────────────────────────

def test_dispatch_skips_when_daemon_unavailable() -> None:
    gen = _StubGenerator("STUB", [Candidate("wp.", "test")])
    ctx = _FakeCtx(active_goal="dummy", daemon_handle=None)
    results = dispatch_hints(ctx, [gen], goal_type="pRHL")
    assert results == []
    assert gen.generate_calls == 0


def test_dispatch_skips_generator_with_wrong_shape() -> None:
    gen = _StubGenerator("STUB", [Candidate("wp.", "test")], applies_shapes=("pRHL",))
    cli = _FakeDaemonCli()
    ctx = _FakeCtx(
        active_goal="dummy", daemon_handle=_FakeDaemonHandle(cli),
    )
    results = dispatch_hints(ctx, [gen], goal_type="ambient")
    assert results == []
    assert gen.generate_calls == 0
    assert cli.calls == []


def test_dispatch_partitions_accepted_and_rejected() -> None:
    gen = _StubGenerator("STUB", [
        Candidate("yes_match.", "ok"),
        Candidate("no_other.", "ok"),
        Candidate("yes_again.", "ok"),
    ])
    cli = _FakeDaemonCli(accept_pattern="yes_")
    ctx = _FakeCtx(
        active_goal="dummy", daemon_handle=_FakeDaemonHandle(cli),
    )
    results = dispatch_hints(ctx, [gen], goal_type="pRHL")
    assert len(results) == 1
    r = results[0]
    accepted_actions = [c.tactic for c in r.accepted]
    rejected_actions = [c.tactic for c in r.rejected]
    assert accepted_actions == ["yes_match.", "yes_again."]
    assert rejected_actions == ["no_other."]
    assert len(cli.calls) == 3


def test_dispatch_applies_probe_budget_per_generator() -> None:
    gen = _StubGenerator("STUB", [
        Candidate(f"t{i}.", "ok") for i in range(10)
    ])
    cli = _FakeDaemonCli()
    ctx = _FakeCtx(
        active_goal="dummy", daemon_handle=_FakeDaemonHandle(cli),
    )
    dispatch_hints(
        ctx, [gen], goal_type="pRHL", probe_budget_per_generator=4,
    )
    # Budget caps at 4 daemon calls, even though 10 candidates were
    # produced.
    assert len(cli.calls) == 4


def test_candidates_to_recommendations_canonical_shape() -> None:
    gen = _StubGenerator("AUTO-TEST", [Candidate(
        "swap{1} 7 -3.",
        why="Test rationale.",
        source_modules=("A",),
        metadata={"abstract_modules": ["A"]},
    )])
    cli = _FakeDaemonCli()
    ctx = _FakeCtx(
        active_goal="dummy", daemon_handle=_FakeDaemonHandle(cli),
    )
    results = dispatch_hints(ctx, [gen], goal_type="pRHL")
    recs = candidates_to_recommendations(results[0])
    assert len(recs) == 1
    rec = recs[0]
    assert rec["action"] == "swap{1} 7 -3."
    assert rec["action_type"] == "runnable_tactic"
    assert rec["confidence"] == "verified"
    assert rec["producer"] == "AUTO-TEST"
    assert rec["why"] == "Test rationale."
    assert rec["metadata"]["epistemic_status"] == "daemon_probe_accepted"
    assert rec["metadata"]["abstract_modules"] == ["A"]
    assert rec["source_refs"] == [{"kind": "module", "id": "A"}]


def test_hint_dispatch_phase_centralized_dedup() -> None:
    # Generator must apply to whatever shape `classify_goal` returns
    # for our minimal goal text; "ambient" is the safe default.
    gen = _StubGenerator(
        "STUB",
        [Candidate("wp.", "test")],
        applies_shapes=("pRHL", "ambient", "hoare"),
    )
    cli = _FakeDaemonCli()
    phase = HintDispatchPhase(session=None, generators=[gen])
    ctx = _FakeCtx(
        active_goal="dummy goal",
        daemon_handle=_FakeDaemonHandle(cli),
    )
    first = phase.run(ctx)
    second = phase.run(ctx)
    # Generator runs once; dedup suppresses second invocation at the
    # same goal shape.
    assert gen.generate_calls == 1
    assert len(first) == 1
    assert second == []


def test_hint_dispatch_phase_default_registry_lists_known_generators() -> None:
    """make_default_hint_dispatch_phase must include the known
    Layer-1 generators so commit_phases wires both shapes by default."""
    class _StubSession:
        context_file = None
    phase = make_default_hint_dispatch_phase(_StubSession())
    producer_names = sorted(g.producer_name for g in phase._generators)
    assert "AUTO-ABSTRACT-ADV-CALL" in producer_names
    assert "AUTO-SWAP-ALIGN" in producer_names
    assert "AUTO-ASYM-SEQ" in producer_names
    # All registered Layer-1 generators are typed correctly.
    types = sorted(type(g).__name__ for g in phase._generators)
    assert types == [
        "_AbstractAdvCallGenerator",
        "_AsymSeqGenerator",
        "_SwapAlignGenerator",
    ]


def main() -> int:
    tests = [
        test_dispatch_skips_when_daemon_unavailable,
        test_dispatch_skips_generator_with_wrong_shape,
        test_dispatch_partitions_accepted_and_rejected,
        test_dispatch_applies_probe_budget_per_generator,
        test_candidates_to_recommendations_canonical_shape,
        test_hint_dispatch_phase_centralized_dedup,
        test_hint_dispatch_phase_default_registry_lists_known_generators,
    ]
    for t in tests:
        t()
    print("PASS test_hint_dispatch")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
