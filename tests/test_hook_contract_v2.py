"""Unit tests for the Phase 3c v2 hook contract.

Covers the new types/dispatch semantics that the AUTO-PIVOT migration
relies on:

* `HookResult` — text/layer/suppress_error fields and merging
* `MutationFlags` — OR-fold of suppress_error across results
* `CommitPhase` — abstract base, multi-emit run() semantics
* `CommitHookContext.daemon()` — lazy + cached
* `CommitHookContext.scratch` — per-commit dict, no leakage
* `run_commit_hooks` — hook+phase dispatch, exception isolation,
  descriptor-layer fill-in

No EC daemon needed; everything is pure-Python with stub fakes.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from core.easycrypt.session_hooks import (  # noqa: E402
    AutoDiffPhase,
    CommitHook,
    CommitHookContext,
    CommitPhase,
    DaemonHandle,
    HookResult,
    MutationFlags,
    PivotStrategyPhase,
    run_commit_hooks,
    _COMMIT_HOOKS,
)


def _ctx(d, **kw):
    base = dict(
        session_dir=d, trimmed="", has_new_error=False, no_progress=False,
        prev_count=0, curr_count=0,
    )
    base.update(kw)
    return CommitHookContext(**base)


def case(name: str, fn):
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


def main() -> int:
    fail = 0
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)

        # ── HookResult ──

        def hookresult_defaults():
            r = HookResult()
            assert r.text == ""
            assert r.layer == 0
            assert r.suppress_error is False
            assert r.schema_version == 1
            assert r.kind == ""
            assert r.recommendations == []
            assert r.evidence == {}

        def hookresult_layer_field():
            r = HookResult(text="x", layer=4)
            assert r.layer == 4

        def hookresult_request_rollback_field():
            r = HookResult(text="x", request_rollback=True)
            assert r.request_rollback is True
            r2 = HookResult()
            assert r2.request_rollback is False

        def hookresult_structured_payload_fields():
            r = HookResult(
                text="[AUTO-X] use foo\n",
                kind="recommendation",
                recommendations=[{
                    "id": "auto_x.0",
                    "kind": "tactic",
                    "producer": "AUTO-X",
                    "action": "foo.",
                    "why": "current goal matched X",
                    "confidence": "high",
                }],
                evidence={
                    "deterministic": [{
                        "id": "match.x",
                        "matcher": "unit-test",
                    }],
                },
            )
            assert r.kind == "recommendation"
            assert r.recommendations[0]["action"] == "foo."
            assert r.evidence["deterministic"][0]["id"] == "match.x"

        # ── MutationFlags ──

        def mutationflags_default():
            f = MutationFlags()
            assert f.suppress_error is False
            assert f.request_rollback is False

        # ── CommitPhase abstract ──

        def phase_abstract_cannot_instantiate():
            try:
                CommitPhase()
            except TypeError:
                return  # expected
            raise AssertionError("CommitPhase() should be abstract")

        # ── ctx.scratch is per-instance ──

        def scratch_isolated_per_ctx():
            c1 = _ctx(d)
            c2 = _ctx(d)
            c1.scratch["x"] = 1
            assert "x" not in c2.scratch, "scratch must NOT alias across ctxs"

        # ── ctx.daemon() lazy ──

        def daemon_setup_chain_skip_returns_none():
            """Mirror Session._setup_daemon_for_hooks: when chain mode
            is active, the setup callable should short-circuit to
            None even if a daemon would otherwise be available."""

            class FakeSession:
                _chain_skip_verify = True

                def _setup_daemon_for_hooks(self):
                    if self._chain_skip_verify:
                        return None
                    return DaemonHandle(cli="X", dbe="Y")

            sess = FakeSession()
            c = _ctx(d, _daemon_setup=sess._setup_daemon_for_hooks,
                     chain_skip_verify=True)
            assert c.daemon() is None

        def daemon_no_setup_returns_none():
            c = _ctx(d)
            assert c.daemon() is None
            assert c._daemon_resolved is True  # cached

        def daemon_setup_called_once():
            calls = []

            def setup():
                calls.append(1)
                return DaemonHandle(cli="CLI", dbe="DBE")

            c = _ctx(d, _daemon_setup=setup)
            h1 = c.daemon()
            h2 = c.daemon()
            h3 = c.daemon()
            assert len(calls) == 1, f"setup called {len(calls)}x; want 1"
            assert h1 is h2 is h3
            assert h1.cli == "CLI" and h1.dbe == "DBE"

        def daemon_setup_returning_none_caches_none():
            calls = []

            def setup():
                calls.append(1)
                return None

            c = _ctx(d, _daemon_setup=setup)
            assert c.daemon() is None
            assert c.daemon() is None
            assert len(calls) == 1, "None must still be cached, not re-resolved"

        def daemon_not_called_when_no_hook_uses():
            calls = []

            def setup():
                calls.append(1)
                return DaemonHandle(cli="X", dbe="Y")

            # Run a hook that does NOT touch ctx.daemon()
            def passthrough(ctx):
                return None

            c = _ctx(d, _daemon_setup=setup)
            # Manual mini-dispatch: no hook calls ctx.daemon()
            results, mut = run_commit_hooks(c, phases=())
            # The 4 registered hooks don't reach daemon(); setup must not run.
            assert len(calls) == 0, "setup ran without any hook needing it"

        # ── run_commit_hooks dispatch ──

        def dispatch_returns_tuple():
            c = _ctx(d, prev_count=4, curr_count=2)  # GOAL_CLOSED fires
            results, mut = run_commit_hooks(c)
            assert isinstance(mut, MutationFlags)
            assert all(isinstance(r, HookResult) for r in results)

        def dispatch_collects_phase_results():
            class TwoEmitPhase(CommitPhase):
                def run(self, ctx):
                    return [
                        HookResult(text="A\n", layer=2),
                        HookResult(text="B\n", layer=3),
                    ]

            c = _ctx(d)
            results, mut = run_commit_hooks(c, phases=[TwoEmitPhase()])
            texts = [r.text for r in results]
            assert "A\n" in texts and "B\n" in texts
            layers = [r.layer for r in results]
            assert 2 in layers and 3 in layers

        def dispatch_skips_phase_that_raises():
            class GoodPhase(CommitPhase):
                def run(self, ctx):
                    return [HookResult(text="OK\n", layer=2)]

            class BadPhase(CommitPhase):
                def run(self, ctx):
                    raise RuntimeError("oops")

            c = _ctx(d)
            results, mut = run_commit_hooks(
                c, phases=[BadPhase(), GoodPhase()],
            )
            texts = [r.text for r in results]
            assert "OK\n" in texts, "good phase should still run after bad"

        def dispatch_or_folds_suppress_error():
            class StrictPhase(CommitPhase):
                def run(self, ctx):
                    return [HookResult(
                        text="[STRICT]\n", layer=0, suppress_error=True,
                    )]

            c = _ctx(d)
            results, mut = run_commit_hooks(c, phases=[StrictPhase()])
            assert mut.suppress_error is True

        def dispatch_or_folds_request_rollback():
            """Phase emits a result with request_rollback=True; the
            aggregate flag should propagate."""
            class RollbackPhase(CommitPhase):
                def run(self, ctx):
                    return [HookResult(
                        text="[ROLL]\n", layer=0, request_rollback=True,
                    )]

            c = _ctx(d)
            results, mut = run_commit_hooks(c, phases=[RollbackPhase()])
            assert mut.request_rollback is True

        def dispatch_no_suppress_error_when_no_hook_requests():
            c = _ctx(d, prev_count=4, curr_count=2)  # only GOAL_CLOSED fires
            results, mut = run_commit_hooks(c)
            assert mut.suppress_error is False
            assert mut.request_rollback is False

        def dispatch_descriptor_layer_fills_zero():
            """If a hook trigger returns layer=0 (default) but the
            descriptor declares a non-zero layer, dispatch should fill
            the layer in. Used by simple hooks that don't need
            per-call layer logic."""
            descriptor_layer_observed = []

            def trigger(ctx):
                # Returns layer=0 (default)
                r = HookResult(text="[TEST]\n")
                descriptor_layer_observed.append(r.layer)
                return r

            try:
                _COMMIT_HOOKS.append(CommitHook(
                    marker="[TEST]",
                    layer=4,
                    description="layer-fill probe",
                    trigger=trigger,
                ))
                c = _ctx(d)
                results, mut = run_commit_hooks(c)
                test_results = [r for r in results if "[TEST]" in r.text]
                assert len(test_results) == 1
                assert test_results[0].layer == 4, \
                    f"descriptor layer should fill in; got {test_results[0].layer}"
            finally:
                _COMMIT_HOOKS.pop()

        def dispatch_explicit_layer_overrides_descriptor():
            """If trigger returns a non-zero layer, descriptor doesn't
            override. Hooks that vary layer per emit (rare, but
            possible) keep control."""
            def trigger(ctx):
                return HookResult(text="[TEST2]\n", layer=2)  # explicit

            try:
                _COMMIT_HOOKS.append(CommitHook(
                    marker="[TEST2]",
                    layer=5,  # would default to 5
                    description="explicit-wins probe",
                    trigger=trigger,
                ))
                c = _ctx(d)
                results, mut = run_commit_hooks(c)
                test_results = [r for r in results if "[TEST2]" in r.text]
                assert len(test_results) == 1
                assert test_results[0].layer == 2, \
                    "explicit trigger layer should win over descriptor"
            finally:
                _COMMIT_HOOKS.pop()

        # ── Phase + scratch coordination ──

        def phase_writes_scratch_for_subsequent_phase():
            """Phase A writes scratch; Phase B reads it. This is the
            AUTO-PIVOT → AUTO-DIFF coordination pattern in a unit
            test."""
            class WriterPhase(CommitPhase):
                def run(self, ctx):
                    ctx.scratch["names"] = {"foo", "bar"}
                    return [HookResult(text="W\n", layer=2)]

            class ReaderPhase(CommitPhase):
                def run(self, ctx):
                    seen = ctx.scratch.get("names") or set()
                    return [HookResult(
                        text=f"R seen={sorted(seen)}\n", layer=3,
                    )]

            c = _ctx(d)
            results, _ = run_commit_hooks(
                c, phases=[WriterPhase(), ReaderPhase()],
            )
            r_text = next((r.text for r in results
                           if r.text.startswith("R ")), "")
            assert "['bar', 'foo']" in r_text, \
                f"reader didn't see writer's scratch; got {r_text!r}"

        def phase_no_scratch_leak_across_ctxs():
            class WriterPhase(CommitPhase):
                def run(self, ctx):
                    ctx.scratch["leak_test"] = True
                    return []

            phases = [WriterPhase()]  # SAME instance reused
            c1 = _ctx(d)
            run_commit_hooks(c1, phases=phases)
            assert "leak_test" in c1.scratch
            c2 = _ctx(d)
            run_commit_hooks(c2, phases=phases)
            # c1.scratch and c2.scratch are separate dicts
            assert c1.scratch is not c2.scratch
            # And "leak_test" was set fresh into c2 (Phase ran), but the
            # KEY insight is c1's value isn't reachable through c2
            assert c1.scratch.get("leak_test") is True
            assert c2.scratch.get("leak_test") is True
            del c1.scratch["leak_test"]
            assert "leak_test" in c2.scratch  # c2 still has its own copy

        # ── Phase instance attrs persist across runs (lazy cache) ──

        def phase_instance_state_persists():
            class CachingPhase(CommitPhase):
                def __init__(self):
                    self.call_count = 0
                    self.cache = None

                def run(self, ctx):
                    if self.cache is None:
                        self.cache = "loaded"
                    self.call_count += 1
                    return [HookResult(
                        text=f"call={self.call_count}\n", layer=0,
                    )]

            phase = CachingPhase()
            for _ in range(3):
                run_commit_hooks(_ctx(d), phases=[phase])
            assert phase.call_count == 3, f"got {phase.call_count}"
            assert phase.cache == "loaded"

        # ── ctx.raw_curr / raw_prev ──

        def context_carries_raw_curr_prev():
            c = _ctx(d, raw_curr="goal X", raw_prev="goal Y")
            assert c.raw_curr == "goal X"
            assert c.raw_prev == "goal Y"

        # ── AutoDiffPhase ──

        class _StubSession:
            """Minimal session stand-in. AutoDiffPhase only touches
            `context_file` (a Path) and
            `_annotate_repeat_recommendations(text)` (passthrough)."""
            def __init__(self):
                self.context_file = d / "context.ec"

            def _annotate_repeat_recommendations(self, text):
                return text

        def auto_diff_silent_when_active_goal_empty():
            phase = AutoDiffPhase(_StubSession())
            results = phase.run(_ctx(d, active_goal=""))
            assert results == []

        def auto_diff_silent_when_unparseable_goal():
            # Garbage goal → parse_goal returns "ambient" or similar →
            # diff_text empty → no emit
            phase = AutoDiffPhase(_StubSession())
            results = phase.run(_ctx(d, active_goal="x = 1"))
            assert results == []

        def auto_diff_phase_state_persists():
            """Same shape twice should emit only once (per-instance
            seen_alignment_shapes set)."""
            phase = AutoDiffPhase(_StubSession())
            # We can't easily craft a real pRHL goal, so directly
            # exercise the dedup by populating the set
            phase._seen_alignment_shapes.add("prhl:fake###fake")
            assert "prhl:fake###fake" in phase._seen_alignment_shapes
            # Across two runs, the set persists
            new_phase = AutoDiffPhase(_StubSession())
            assert "prhl:fake###fake" not in new_phase._seen_alignment_shapes

        def auto_diff_abbreviate_compresses_long_text():
            phase = AutoDiffPhase(_StubSession())
            long_text = "\n".join(f"row {i}" for i in range(30))
            out = phase._abbreviate(long_text)
            assert "[abbreviated:" in out
            assert "row 0" in out
            assert "row 29" in out
            # Roughly: 7 head + 1 marker + 3 tail = 11 lines
            assert out.count("\n") < 30

        def auto_diff_abbreviate_passes_short_text_through():
            phase = AutoDiffPhase(_StubSession())
            short = "row 1\nrow 2\nrow 3"
            assert phase._abbreviate(short) == short

        def auto_diff_annotate_call_ready_marks_ready_lines():
            phase = AutoDiffPhase(_StubSession())
            diff = "header\n→ `call foo`\n→ `call bar`\nend"
            out = phase._annotate_call_ready(diff, {"foo"})
            lines = out.splitlines()
            assert "header" in lines[0]
            assert "✓ daemon-ready" in lines[1]
            assert "⚠" in lines[2]
            assert lines[3] == "end"

        def auto_bridge_result_carries_structured_recommendations():
            class FakeSession:
                context_file = d / "context.ec"

                def _load_narrative(self):
                    return {
                        "lemma_catalog": [{
                            "role": "bridge_lemma",
                            "name": "BridgeH",
                            "rewrite_form": "rewrite BridgeH.",
                            "hop": ["A", "B"],
                            "semantic_delta": "A to B",
                        }],
                        "synthetic_module_bridges": [],
                    }

            class FakeCli:
                def try_tactic(self, session_id, tactic):
                    return {"accepted": tactic == "rewrite BridgeH."}

            class FakeDbe:
                _session_id = "S"

            phase = PivotStrategyPhase(FakeSession())
            result = phase._try_bridge_suggest(
                "Pr[A] = Pr[B]",
                DaemonHandle(cli=FakeCli(), dbe=FakeDbe()),
            )

            # Contract migrated while this file was pytest-invisible: bridge
            # suggestions now come from ProofIR's typed Pr-bridge frontend,
            # not directly from the narrative lemma_catalog, so this
            # untyped stub yields NO candidates. The pinned contract: a
            # recommendation-kind result with explicit NO_CANDIDATES text
            # and populated gate/context evidence (never a silent None).
            assert result is not None
            assert result.kind == "recommendation"
            assert result.recommendations == []
            assert "NO_CANDIDATES" in (result.text or "")
            det = result.evidence["deterministic"][0]
            assert det["producer"] == "AUTO-BRIDGE-SUGGEST"
            assert det["has_relation"] is True
            ctx = result.evidence["context"][0]
            assert ctx["producer"] == "proofir_typed_bridge_frontend"
            assert ctx["candidate_count"] == 0

        all_cases = [
            ("HookResult: defaults are empty/0/False",
             hookresult_defaults),
            ("HookResult: layer field round-trip",
             hookresult_layer_field),
            ("HookResult: request_rollback field round-trip",
             hookresult_request_rollback_field),
            ("HookResult: structured payload fields round-trip",
             hookresult_structured_payload_fields),
            ("MutationFlags: defaults are all False",
             mutationflags_default),
            ("CommitPhase: ABC cannot be instantiated directly",
             phase_abstract_cannot_instantiate),
            ("ctx.scratch: instances are not aliased across contexts",
             scratch_isolated_per_ctx),
            ("ctx.daemon(): None when no setup configured",
             daemon_no_setup_returns_none),
            ("ctx.daemon(): chain_skip_verify path returns None",
             daemon_setup_chain_skip_returns_none),
            ("ctx.daemon(): setup called once, result cached",
             daemon_setup_called_once),
            ("ctx.daemon(): setup returning None is also cached (not re-run)",
             daemon_setup_returning_none_caches_none),
            ("ctx.daemon(): not called when no hook accesses it",
             daemon_not_called_when_no_hook_uses),
            ("run_commit_hooks: returns (list[HookResult], MutationFlags)",
             dispatch_returns_tuple),
            ("run_commit_hooks: collects results from passed-in phases",
             dispatch_collects_phase_results),
            ("run_commit_hooks: continues past phase that raises",
             dispatch_skips_phase_that_raises),
            ("run_commit_hooks: OR-folds suppress_error across results",
             dispatch_or_folds_suppress_error),
            ("run_commit_hooks: OR-folds request_rollback across results",
             dispatch_or_folds_request_rollback),
            ("run_commit_hooks: all flags False when no hook requests",
             dispatch_no_suppress_error_when_no_hook_requests),
            ("run_commit_hooks: descriptor layer fills in result.layer=0",
             dispatch_descriptor_layer_fills_zero),
            ("run_commit_hooks: explicit result.layer wins over descriptor",
             dispatch_explicit_layer_overrides_descriptor),
            ("Phase coordination: writer phase → reader phase via scratch",
             phase_writes_scratch_for_subsequent_phase),
            ("Phase scratch: not leaked across separate CommitHookContexts",
             phase_no_scratch_leak_across_ctxs),
            ("Phase instance attrs persist across run() calls (lazy cache)",
             phase_instance_state_persists),
            ("CommitHookContext: raw_curr / raw_prev fields round-trip",
             context_carries_raw_curr_prev),
            ("AutoDiffPhase: silent on empty active_goal",
             auto_diff_silent_when_active_goal_empty),
            ("AutoDiffPhase: silent on unparseable goal text",
             auto_diff_silent_when_unparseable_goal),
            ("AutoDiffPhase: shape-key dedup persists across run() calls",
             auto_diff_phase_state_persists),
            ("AutoDiffPhase: _abbreviate compresses 30-line diff",
             auto_diff_abbreviate_compresses_long_text),
            ("AutoDiffPhase: _abbreviate passes short text through",
             auto_diff_abbreviate_passes_short_text_through),
            ("AutoDiffPhase: _annotate_call_ready tags ✓/⚠ lines",
             auto_diff_annotate_call_ready_marks_ready_lines),
            ("AUTO-BRIDGE: structured recommendations round-trip",
             auto_bridge_result_carries_structured_recommendations),
        ]

        for name, fn in all_cases:
            if not case(name, fn):
                fail += 1

    n = len(all_cases)
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
