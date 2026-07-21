"""Tests for AbstractAdvCallHintPhase daemon-verified call recommendations."""
from __future__ import annotations

from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from core.easycrypt.session_hook_phases import (  # type: ignore  # noqa: E402
    HintDispatchPhase,
    _AbstractAdvCallGenerator,
)
from tests.helpers.fakes import (  # noqa: E402
    FakeCtx,
    FakeDaemonBackend,
    FakeDaemonHandle,
)


def AbstractAdvCallHintPhase(session):
    """The retired one-generator phase alias, rebuilt from public parts."""
    return HintDispatchPhase(session, generators=[_AbstractAdvCallGenerator(session)])


_GOAL_WITH_ABSTRACT_ADV = """\
Current goal
&m: {}
------------------------------------------------------------------------
&1 (left ) : {b, b' : bool}
&2 (right) : {b, b' : bool}

pre = (glob A){1} = (glob A){2}

(m0, m1) <@ A.choose(pk)    (1)  (m0, m1) <@ A.choose(gx)
b' <@ A.guess(c)            (2)  b' <@ A.guess(gy, gz)

post = ={res}
"""

_SOURCE_WITH_DECLARE = """\
section.
  declare module A <: Adversary.
  declare axiom Ac_ll: islossless A.choose.
end section.
"""


# ─── Test fakes ───────────────────────────────────────────────────────────

class _FakeDaemonCli:
    """Records every try_tactic call and returns scripted accept/reject.

    Kept local: this variant accepts a set of exact tactics, unlike the
    canonical substring-pattern ``tests.helpers.fakes.FakeDaemonCli``.
    """
    def __init__(self, accept: set[str]):
        self._accept = accept
        self.calls: list[tuple[str, str]] = []

    def try_tactic(self, session_id: str, tactic: str) -> dict:
        self.calls.append((session_id, tactic))
        return {"accepted": tactic in self._accept}


_FakeDaemonBackend = FakeDaemonBackend
_FakeDaemonHandle = FakeDaemonHandle
_FakeCtx = FakeCtx


class _FakeSession:
    def __init__(self, ctx_path: Path):
        self.context_file = ctx_path


def _phase_with_source(tmp_dir: Path, source: str) -> HintDispatchPhase:
    src_path = tmp_dir / "ctx.ec"
    src_path.write_text(source, encoding="utf-8")
    return AbstractAdvCallHintPhase(_FakeSession(src_path))


# ─── Tests ────────────────────────────────────────────────────────────────

def test_phase_emits_runnable_for_accepted_canonical_inv() -> None:
    accept = {
        "call (_: ={glob A} ==> ={res, glob A}).",
        "call (_: true).",
    }
    cli = _FakeDaemonCli(accept)
    with tempfile.TemporaryDirectory() as td:
        phase = _phase_with_source(Path(td), _SOURCE_WITH_DECLARE)
        ctx = _FakeCtx(
            active_goal=_GOAL_WITH_ABSTRACT_ADV,
            daemon_handle=_FakeDaemonHandle(cli),
        )
        results = phase.run(ctx)
    assert len(results) == 1
    res = results[0]
    actions = sorted(r["action"] for r in res.recommendations)
    assert actions == sorted(accept)
    for rec in res.recommendations:
        assert rec["action_type"] == "runnable_tactic"
        assert rec["confidence"] == "verified"
        assert rec["producer"] == "AUTO-ABSTRACT-ADV-CALL"
        assert (
            rec["metadata"]["epistemic_status"]
            == "easycrypt_preflight_accepted"
        )
        assert rec["metadata"]["abstract_modules"] == ["A"]
    # Daemon was probed for all 3 canonical shapes; 2 accepted, 1 rejected.
    probed_tactics = [t for _, t in cli.calls]
    assert len(probed_tactics) == 3
    assert "call (_: ={glob A}).\n".strip() in probed_tactics


def test_phase_no_emit_when_no_abstract_adv() -> None:
    src = "module Concrete = {}.\n"
    goal = "x <@ Concrete.foo(y);\n"
    cli = _FakeDaemonCli(accept={"call (_: ={glob Concrete}).\n".strip()})
    with tempfile.TemporaryDirectory() as td:
        phase = _phase_with_source(Path(td), src)
        ctx = _FakeCtx(
            active_goal=goal,
            daemon_handle=_FakeDaemonHandle(cli),
        )
        results = phase.run(ctx)
    assert results == []
    assert cli.calls == [], (
        "phase must not invoke daemon when no abstract adv call is in goal"
    )


def test_phase_no_emit_when_daemon_rejects_all() -> None:
    cli = _FakeDaemonCli(accept=set())
    with tempfile.TemporaryDirectory() as td:
        phase = _phase_with_source(Path(td), _SOURCE_WITH_DECLARE)
        ctx = _FakeCtx(
            active_goal=_GOAL_WITH_ABSTRACT_ADV,
            daemon_handle=_FakeDaemonHandle(cli),
        )
        results = phase.run(ctx)
    assert results == []
    assert len(cli.calls) == 3, "all 3 candidates must be probed once each"


def test_phase_dedup_skips_repeat_on_same_goal_shape() -> None:
    cli = _FakeDaemonCli(accept={"call (_: true)."})
    with tempfile.TemporaryDirectory() as td:
        phase = _phase_with_source(Path(td), _SOURCE_WITH_DECLARE)
        ctx = _FakeCtx(
            active_goal=_GOAL_WITH_ABSTRACT_ADV,
            daemon_handle=_FakeDaemonHandle(cli),
        )
        first = phase.run(ctx)
        second = phase.run(ctx)
    assert len(first) == 1
    assert second == [], "same goal shape must not re-probe"
    assert len(cli.calls) == 3, "daemon must only be probed once across runs"


def test_phase_no_emit_when_daemon_unavailable() -> None:
    with tempfile.TemporaryDirectory() as td:
        phase = _phase_with_source(Path(td), _SOURCE_WITH_DECLARE)
        ctx = _FakeCtx(
            active_goal=_GOAL_WITH_ABSTRACT_ADV,
            daemon_handle=None,
        )
        results = phase.run(ctx)
    assert results == []


def main() -> int:
    tests = [
        test_phase_emits_runnable_for_accepted_canonical_inv,
        test_phase_no_emit_when_no_abstract_adv,
        test_phase_no_emit_when_daemon_rejects_all,
        test_phase_dedup_skips_repeat_on_same_goal_shape,
        test_phase_no_emit_when_daemon_unavailable,
    ]
    for t in tests:
        t()
    print("PASS test_abstract_adv_call_phase")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
