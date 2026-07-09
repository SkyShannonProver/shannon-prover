"""Unit tests for fresh-context continuation (auto context-respawn).

Covers the pure decision logic in ``workflow.ctx_respawn`` (watermark debounce,
env knobs, kill switch, proof-open classifier, handoff rendering), the runtime
respawn-guard methods (progress gate, cap,
premature-give-up classification) with lightweight fakes, and the supervisor's
``context_respawn`` marker observability reset. No real EasyCrypt or claude.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from workflow import ctx_respawn as cr


# --- Layer 1 detection: usage extraction -------------------------------------

def _assistant(input_t=0, cache_read=0, cache_create=0):
    return {
        "type": "assistant",
        "message": {
            "usage": {
                "input_tokens": input_t,
                "cache_read_input_tokens": cache_read,
                "cache_creation_input_tokens": cache_create,
                "output_tokens": 123,
            }
        },
    }


def test_context_tokens_sums_input_and_cache():
    ev = _assistant(input_t=10, cache_read=14540, cache_create=41447)
    assert cr.context_tokens_from_assistant_event(ev) == 10 + 14540 + 41447


def test_context_tokens_none_for_non_assistant():
    assert cr.context_tokens_from_assistant_event({"type": "user"}) is None
    assert cr.context_tokens_from_assistant_event({"type": "assistant"}) is None
    assert cr.context_tokens_from_assistant_event(
        {"type": "assistant", "message": {}}
    ) is None


def test_context_tokens_handles_garbage_values():
    ev = {"type": "assistant", "message": {"usage": {"input_tokens": "x"}}}
    assert cr.context_tokens_from_assistant_event(ev) is None  # 0 total -> None


# --- Layer 1 detection: debounced watermark ----------------------------------

def test_watermark_trips_after_consecutive_hot_turns():
    det = cr.CtxWatermarkDetector(tokens=150_000, turns=2, enabled=True)
    # First hot turn: arm, no trip yet (debounce).
    assert det.observe(_assistant(cache_read=160_000)) is False
    assert det.ctx_pressure is False
    assert det.hot_turns == 1
    # Second consecutive hot turn: trip (rising edge True).
    assert det.observe(_assistant(cache_read=160_000)) is True
    assert det.ctx_pressure is True


def test_watermark_resets_on_cold_turn():
    det = cr.CtxWatermarkDetector(tokens=150_000, turns=2, enabled=True)
    det.observe(_assistant(cache_read=160_000))   # hot (1)
    det.observe(_assistant(cache_read=10_000))    # cold -> reset to 0
    assert det.hot_turns == 0
    assert det.observe(_assistant(cache_read=160_000)) is False  # only 1 again
    assert det.ctx_pressure is False


def test_watermark_below_threshold_never_trips():
    det = cr.CtxWatermarkDetector(tokens=150_000, turns=1, enabled=True)
    assert det.observe(_assistant(cache_read=149_999)) is False
    assert det.ctx_pressure is False


def test_watermark_trip_is_rising_edge_only():
    det = cr.CtxWatermarkDetector(tokens=100, turns=1, enabled=True)
    assert det.observe(_assistant(input_t=200)) is True
    # Already tripped: subsequent hot turns return False (no re-fire).
    assert det.observe(_assistant(input_t=200)) is False


def test_watermark_disabled_never_trips():
    det = cr.CtxWatermarkDetector(tokens=100, turns=1, enabled=False)
    assert det.observe(_assistant(input_t=10_000)) is False
    assert det.ctx_pressure is False


def test_watermark_reset_clears_state():
    det = cr.CtxWatermarkDetector(tokens=100, turns=1, enabled=True)
    det.observe(_assistant(input_t=200))
    assert det.ctx_pressure is True
    det.reset()
    assert det.ctx_pressure is False
    assert det.hot_turns == 0


# --- env knobs ---------------------------------------------------------------

def test_env_defaults(monkeypatch):
    for k in (
        "SHANNON_CTX_WATERMARK_TOKENS",
        "SHANNON_CTX_WATERMARK_TURNS",
        "SHANNON_CTX_RESPAWN_MAX",
        "SHANNON_DISABLE_CTX_RESPAWN",
    ):
        monkeypatch.delenv(k, raising=False)
    # Default tightened to 140k (Change 5): fires before the observed ~145k
    # process death and below the ~159-169k SDK compaction band.
    assert cr.watermark_tokens() == 140_000
    assert cr.DEFAULT_WATERMARK_TOKENS == 140_000
    assert cr.watermark_turns() == 2
    assert cr.respawn_max() == 2
    assert cr.respawn_disabled() is False


def test_env_overrides(monkeypatch):
    monkeypatch.setenv("SHANNON_CTX_WATERMARK_TOKENS", "90000")
    monkeypatch.setenv("SHANNON_CTX_WATERMARK_TURNS", "3")
    monkeypatch.setenv("SHANNON_CTX_RESPAWN_MAX", "5")
    assert cr.watermark_tokens() == 90_000
    assert cr.watermark_turns() == 3
    assert cr.respawn_max() == 5


def test_env_override_takes_effect_in_detector(monkeypatch):
    monkeypatch.setenv("SHANNON_CTX_WATERMARK_TOKENS", "5000")
    monkeypatch.setenv("SHANNON_CTX_WATERMARK_TURNS", "1")
    monkeypatch.delenv("SHANNON_DISABLE_CTX_RESPAWN", raising=False)
    det = cr.CtxWatermarkDetector()  # picks up env
    assert det.tokens == 5000 and det.turns == 1
    assert det.observe(_assistant(input_t=6000)) is True


def test_kill_switch_truthy_values(monkeypatch):
    for val in ("1", "true", "TRUE", "yes", "on"):
        monkeypatch.setenv("SHANNON_DISABLE_CTX_RESPAWN", val)
        assert cr.respawn_disabled() is True
    for val in ("0", "false", "", "no"):
        monkeypatch.setenv("SHANNON_DISABLE_CTX_RESPAWN", val)
        assert cr.respawn_disabled() is False


def test_kill_switch_disables_detector(monkeypatch):
    monkeypatch.setenv("SHANNON_DISABLE_CTX_RESPAWN", "1")
    det = cr.CtxWatermarkDetector()
    assert det.enabled is False
    assert det.observe(_assistant(input_t=10_000_000)) is False


def test_bad_env_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("SHANNON_CTX_WATERMARK_TOKENS", "not-a-number")
    assert cr.watermark_tokens() == 140_000


# --- Layer 2 classifier: proof-open ------------------------------------------

def test_proof_is_open_true_when_open_with_goals():
    view = {"proof_status": {"status": "open", "remaining_goals": 4}}
    assert cr.proof_is_open(view) is True


def test_proof_is_open_false_when_no_goals():
    view = {"proof_status": {"status": "open", "remaining_goals": 0}}
    assert cr.proof_is_open(view) is False


def test_proof_is_open_false_for_candidate_and_complete():
    assert cr.proof_is_open(
        {"proof_status": {"status": "candidate_closed_pending_qed", "remaining_goals": 0}}
    ) is False
    assert cr.proof_is_open(
        {"proof_status": {"status": "complete", "remaining_goals": 0}}
    ) is False


def test_proof_is_open_false_for_missing_or_thin_view():
    assert cr.proof_is_open(None) is False
    assert cr.proof_is_open({}) is False
    assert cr.proof_is_open({"proof_status": "x"}) is False


# --- handoff: dead-end ledger dedup + cap ------------------------------------

# --- handoff: frontier brief + render ----------------------------------------

def test_frontier_brief_mentions_remaining_and_goal():
    view = {
        "proof_status": {"status": "open", "remaining_goals": 3},
        "current_goal": {"lines": ["a = b", "c <= d"]},
    }
    brief = cr.build_frontier_brief(view)
    assert "3 goal(s) remaining" in brief
    assert "a = b" in brief


def test_render_handoff_is_neutral_evidence_and_includes_sections():
    out = cr.render_handoff_section(
        frontier_brief="Frontier: 2 goal(s) remaining.",
        accepted_spine=["proc", "inline *"],
    )
    assert "neutral evidence" in out.lower()
    assert "`proc.`" in out
    assert "already tried" not in out.lower()
    assert "rejected" not in out.lower()
    # Frames as evidence, not a prohibition.
    assert "forbidden" not in out.lower()
    assert "do not use" not in out.lower()


def test_accepted_spine_tail_cap():
    spine = cr.build_accepted_spine([f"t{i}" for i in range(100)], cap=10)
    assert spine == [f"t{i}" for i in range(90, 100)]


# --- Change 4: verdict-strip (anti-anchoring) --------------------------------

def test_strip_closed_verdicts_removes_dispositions():
    text = (
        "I rewrote with foo and the goal reduced nicely.\n"
        "This lemma is UNPROVABLE as stated; it seems impossible as posed.\n"
        "There is no route here and it cannot be proved. I give up — stuck."
    )
    out = cr.strip_closed_verdicts(text)
    low = out.lower()
    # Working insight survives.
    assert "rewrote with foo" in out
    assert "goal reduced nicely" in out
    # Every closed-verdict phrasing is neutralized (case-insensitive).
    for verdict in (
        "unprovable", "impossible", "no route", "cannot be proved",
        "give up", "give-up",
    ):
        assert verdict not in low
    # Bare "stuck" (not a provability verdict) is intentionally KEPT — see the
    # over-strip fix; here it survives the "I give up — stuck" line.
    assert "stuck" in low


def test_strip_closed_verdicts_handles_giveup_spacing_variants():
    for v in ("give up", "giveup", "GIVE UP", "Give-up"):
        assert "give" not in cr.strip_closed_verdicts(v).lower()


def test_strip_closed_verdicts_best_effort_on_non_string():
    # Never raises; returns the input unchanged on a bad type.
    assert cr.strip_closed_verdicts("") == ""
    assert cr.strip_closed_verdicts(None) is None


def test_strip_closed_verdicts_catches_giving_up():
    # The present-participle / past forms (the most common give-up phrasings that
    # plain `give up` missed) are caught.
    assert "giving up" not in cr.strip_closed_verdicts("I am giving up on this leg").lower()
    assert "gave up" not in cr.strip_closed_verdicts("the predecessor gave up here").lower()


def test_strip_closed_verdicts_keeps_legit_technical_uses():
    # Bare "impossible"/"stuck" in a NON-provability sense must survive (no over-strip).
    for t in (
        "impossible to apply byequiv here",
        "the rewrite got stuck on the conditional",
        "this case is impossible to inline directly",
    ):
        assert cr.strip_closed_verdicts(t) == t


def test_strip_closed_verdicts_neutralizes_unprovable_as_posed():
    out = cr.strip_closed_verdicts("This node is UNPROVABLE AS POSED.").lower()
    assert "unprovable" not in out


# --- runtime respawn-guard methods (fakes, no EC/claude) ---------------------

class _FakeManager:
    def __init__(self, committed, view):
        self._committed = list(committed)
        self.latest_full_view = view

    def _current_committed_tactics(self):
        return list(self._committed)


class _FakeBridge:
    def __init__(self, terminal_health=None):
        self.terminal_health = terminal_health


class _FakeAgent:
    def __init__(self, ctx_pressure=False):
        self.ctx_pressure = ctx_pressure


class _FakeResult:
    def __init__(self, returncode=0):
        self.returncode = returncode


def _runtime_with(manager, bridge, agent):
    """Build a ProofNodeRuntime shell without running __init__ (no EC/bridge)."""
    from workflow.proof_node_runtime import ProofNodeRuntime

    rt = ProofNodeRuntime.__new__(ProofNodeRuntime)
    rt.manager = manager
    rt.bridge = bridge
    rt.agent = agent
    return rt


_OPEN_VIEW = {"proof_status": {"status": "open", "remaining_goals": 2}}
_CLOSED_VIEW = {"proof_status": {"status": "complete", "remaining_goals": 0}}


def test_should_respawn_on_ctx_pressure_with_progress(monkeypatch):
    monkeypatch.delenv("SHANNON_DISABLE_CTX_RESPAWN", raising=False)
    rt = _runtime_with(
        _FakeManager(["proc", "inline", "auto"], _OPEN_VIEW),
        _FakeBridge(terminal_health=None),
        _FakeAgent(ctx_pressure=True),
    )
    assert rt._should_respawn(_FakeResult(0), baseline=1) is True


def test_no_respawn_without_progress(monkeypatch):
    monkeypatch.delenv("SHANNON_DISABLE_CTX_RESPAWN", raising=False)
    rt = _runtime_with(
        _FakeManager(["proc", "inline"], _OPEN_VIEW),
        _FakeBridge(terminal_health=None),
        _FakeAgent(ctx_pressure=True),
    )
    # baseline == current committed count -> zero progress -> structural block.
    assert rt._should_respawn(_FakeResult(0), baseline=2) is False


def test_no_respawn_when_terminal_health_set(monkeypatch):
    monkeypatch.delenv("SHANNON_DISABLE_CTX_RESPAWN", raising=False)
    rt = _runtime_with(
        _FakeManager(["proc", "inline", "auto"], _OPEN_VIEW),
        _FakeBridge(terminal_health=object()),  # not None -> terminal
        _FakeAgent(ctx_pressure=True),
    )
    assert rt._should_respawn(_FakeResult(0), baseline=1) is False


def test_give_up_ends_run_no_respawn(monkeypatch):
    # CORE of the tightening: a clean give-up while the proof is still OPEN, with
    # NO ctx_pressure, must NOT respawn (it ends the run = measurable give-up).
    # REVERT-SENSITIVE: re-adding the premature-give-up branch (returncode==0 +
    # terminal_health is None + proof_is_open) flips this to True and fails.
    monkeypatch.delenv("SHANNON_DISABLE_CTX_RESPAWN", raising=False)
    rt = _runtime_with(
        _FakeManager(["proc", "inline", "auto"], _OPEN_VIEW),
        _FakeBridge(terminal_health=None),
        _FakeAgent(ctx_pressure=False),  # no token pressure, but proof open
    )
    assert rt._should_respawn(_FakeResult(0), baseline=1) is False


def test_no_respawn_on_real_finish_closed_proof(monkeypatch):
    monkeypatch.delenv("SHANNON_DISABLE_CTX_RESPAWN", raising=False)
    rt = _runtime_with(
        _FakeManager(["proc", "inline", "auto"], _CLOSED_VIEW),
        _FakeBridge(terminal_health=None),
        _FakeAgent(ctx_pressure=False),
    )
    # No pressure + proof not open -> not premature -> no respawn.
    assert rt._should_respawn(_FakeResult(0), baseline=1) is False


def test_no_respawn_on_nonzero_returncode_give_up(monkeypatch):
    monkeypatch.delenv("SHANNON_DISABLE_CTX_RESPAWN", raising=False)
    rt = _runtime_with(
        _FakeManager(["proc", "inline", "auto"], _OPEN_VIEW),
        _FakeBridge(terminal_health=None),
        _FakeAgent(ctx_pressure=False),
    )
    # returncode != 0 means the worker errored, not a clean premature give-up.
    assert rt._should_respawn(_FakeResult(2), baseline=1) is False


def test_kill_switch_blocks_runtime_respawn(monkeypatch):
    monkeypatch.setenv("SHANNON_DISABLE_CTX_RESPAWN", "1")
    rt = _runtime_with(
        _FakeManager(["proc", "inline", "auto"], _OPEN_VIEW),
        _FakeBridge(terminal_health=None),
        _FakeAgent(ctx_pressure=True),
    )
    assert rt._should_respawn(_FakeResult(0), baseline=1) is False


def test_made_progress_helper():
    rt = _runtime_with(
        _FakeManager(["a", "b", "c"], _OPEN_VIEW), _FakeBridge(), _FakeAgent()
    )
    assert rt._committed_count() == 3
    assert rt._made_progress(2) is True
    assert rt._made_progress(3) is False


# --- supervisor observability: context_respawn marker reset ------------------

def test_tracker_marker_resets_idle_timers():
    from workflow.progress import _TreeProverTracker

    class _Proc:
        def poll(self):
            return None

    t = _TreeProverTracker.__new__(_TreeProverTracker)
    # Minimal state the marker branch touches.
    t.name = "Tree-0.0"
    t.session_id = ""
    t.result_text = ""
    t.finished = False
    t.proved = False
    t.last_activity_time = 0.0
    t.last_progress_time = 0.0
    t.last_accept_time = 0.0
    t.errors_since_last_accept = 7
    t.context_respawn_count = 0
    # Stub the two end-of-line hooks so we exercise ONLY the marker branch
    # without needing a real session snapshot / display pipeline.
    t._refresh_structured_success = lambda: None
    # Avoid the assistant/user/tool branches; feed only the system marker.
    line = json.dumps({"type": "system", "context_respawn": 1, "node": "0.0"})
    # _process_line calls _handle_stream_event at the end; guard by stubbing.
    import workflow.progress as P
    orig = P._handle_stream_event
    P._handle_stream_event = lambda *a, **k: None
    try:
        t._process_line(line)
    finally:
        P._handle_stream_event = orig
    assert t.errors_since_last_accept == 0
    assert t.context_respawn_count == 1
    assert t.last_activity_time > 0.0
    assert t.last_progress_time > 0.0


# --- FIX #3: turn-limit exhaustion must NOT be treated as a premature give-up --

class _FakeBridgeTurns:
    """Bridge fake exposing the turn-budget fields _should_respawn now reads."""

    def __init__(self, *, turn_index, max_turns, terminal_health=None):
        self._turn_index = turn_index
        self.max_turns = max_turns
        self.terminal_health = terminal_health


def test_turn_limit_exhaustion_blocks_respawn_even_with_pressure(monkeypatch):
    monkeypatch.delenv("SHANNON_DISABLE_CTX_RESPAWN", raising=False)
    # Turn-limit STOP guard runs BEFORE the pressure check: even WITH ctx_pressure
    # set, an exhausted cumulative turn budget must block the respawn (a fresh
    # context would immediately re-STOP).
    rt = _runtime_with(
        _FakeManager(["proc", "inline", "auto"], _OPEN_VIEW),
        _FakeBridgeTurns(turn_index=1000, max_turns=1000, terminal_health=None),
        _FakeAgent(ctx_pressure=True),
    )
    assert rt._turn_limit_exhausted() is True
    assert rt._should_respawn(_FakeResult(0), baseline=1) is False


def test_ctx_pressure_respawns_when_budget_remains(monkeypatch):
    monkeypatch.delenv("SHANNON_DISABLE_CTX_RESPAWN", raising=False)
    # Budget remains + ctx_pressure + progress -> genuine watermark respawn.
    rt = _runtime_with(
        _FakeManager(["proc", "inline", "auto"], _OPEN_VIEW),
        _FakeBridgeTurns(turn_index=153, max_turns=1000, terminal_health=None),
        _FakeAgent(ctx_pressure=True),
    )
    assert rt._turn_limit_exhausted() is False
    assert rt._should_respawn(_FakeResult(0), baseline=1) is True


# --- FIX #2: the fresh-context reopening is materially smaller than turn-0 -----

def test_compact_prompt_drops_heavy_bootstrap():
    from workflow.agent_prompt_render import render_long_lived_agent_prompt

    # A bulky turn-0 bootstrap stands in for the lemma source + siblings + KB.
    heavy = "FULL_BOOTSTRAP_MARKER\n" + ("require import AllCore. " * 2000)
    common = dict(
        host="127.0.0.1", port=0, token="t",
        node_memory_dir=Path("/tmp/nm"), max_turns=1000, surface_profile=None,
    )
    full = render_long_lived_agent_prompt(heavy, **common)
    compact = render_long_lived_agent_prompt(
        heavy, compact=True, compact_pointer="Target lemma `L` lives in `f.ec`",
        **common,
    )
    # The heavy bootstrap is present in the normal opening, absent in the compact
    # one (the fresh session re-reads source on demand instead).
    assert "FULL_BOOTSTRAP_MARKER" in full
    assert "FULL_BOOTSTRAP_MARKER" not in compact
    # Compact is materially smaller and keeps the runtime/tool-protocol block.
    assert len(compact) < len(full) / 2
    assert "submit_proof_intent" in compact
    assert "Target lemma `L` lives in `f.ec`" in compact


# --- Change 3: recent-reasoning ring buffer (in-memory) ----------------------

def _new_agent_session(monkeypatch, *, k=3):
    from workflow.proof_node_runtime import ClaudeAgentSession

    monkeypatch.setenv("SHANNON_RECENT_REASONING_K", str(k))
    # The cap is read from the module constant at __init__; set it directly too
    # so the test does not depend on import-time env evaluation.
    sess = ClaudeAgentSession(
        model="m", source_file="f.ec", session_tag="tag",
        project_root=Path("/tmp"),
    )
    sess._recent_reasoning_cap = k
    return sess


def _assistant_text(text):
    return {"type": "assistant", "message": {"content": [{"type": "text", "text": text}]}}


def test_ring_buffer_keeps_only_last_k(monkeypatch):
    sess = _new_agent_session(monkeypatch, k=3)
    for i in range(6):
        sess._capture_reasoning(_assistant_text(f"thought {i}"))
    assert sess._recent_reasoning == ["thought 3", "thought 4", "thought 5"]


def test_ring_buffer_ignores_non_assistant_and_empty(monkeypatch):
    sess = _new_agent_session(monkeypatch, k=3)
    sess._capture_reasoning({"type": "user", "message": {"content": []}})
    sess._capture_reasoning({"type": "system", "context_respawn": 1})
    sess._capture_reasoning(_assistant_text("   "))  # whitespace only
    sess._capture_reasoning(  # only a tool_use block -> no text
        {"type": "assistant", "message": {"content": [{"type": "tool_use"}]}}
    )
    assert sess._recent_reasoning == []
    sess._capture_reasoning(_assistant_text("real thought"))
    assert sess._recent_reasoning == ["real thought"]


def test_ring_buffer_joins_multiple_text_blocks(monkeypatch):
    sess = _new_agent_session(monkeypatch, k=3)
    sess._capture_reasoning({
        "type": "assistant",
        "message": {"content": [
            {"type": "text", "text": "first"},
            {"type": "tool_use", "name": "x"},
            {"type": "text", "text": "second"},
        ]},
    })
    assert sess._recent_reasoning == ["first\nsecond"]


def test_ring_buffer_capture_does_no_disk_write(monkeypatch):
    # _capture_reasoning must keep reasoning in-memory only (CLAUDE.md: artifacts
    # never store thinking). Prove it by making ANY write-mode open() fail during
    # capture — a non-vacuous assertion: if capture ever persists, this fails.
    import builtins

    sess = _new_agent_session(monkeypatch, k=3)
    real_open = builtins.open

    def _no_write_open(file, mode="r", *a, **k):
        if any(c in str(mode) for c in ("w", "a", "x", "+")):
            raise AssertionError(f"_capture_reasoning wrote to disk: {file!r} ({mode})")
        return real_open(file, mode, *a, **k)

    monkeypatch.setattr(builtins, "open", _no_write_open)
    for i in range(5):
        sess._capture_reasoning(_assistant_text(f"thought {i}"))
    # in-memory ring buffer holds only the last K=3, on the session object
    assert sess._recent_reasoning == ["thought 2", "thought 3", "thought 4"]


# --- Change 3+4: forwarded reasoning on a fresh prompt (verdict-stripped) -----

def _fresh_prompt_runtime(monkeypatch, tmp_path, *, view=None):
    import workflow.proof_node_runtime as M
    from workflow.proof_node_runtime import ProofNodeRuntime

    monkeypatch.setattr(
        M, "render_long_lived_agent_prompt",
        lambda *a, **k: "RUNTIME_PROMPT_BLOCK submit_proof_intent", raising=True,
    )
    rt = ProofNodeRuntime.__new__(ProofNodeRuntime)
    rt.manager = _FakeManager(["proc", "inline"], view or _OPEN_VIEW)
    rt.bridge = _LoopBridge()
    rt.memory = _LoopMemory(tmp_path)
    rt.prompt = "ORIG"
    rt.file_path = "f.ec"
    rt.lemma_name = "L"
    rt.max_turns = 1000
    rt.surface_profile = None
    return rt


def test_fresh_prompt_forwards_recent_reasoning_verdict_stripped(monkeypatch, tmp_path):
    rt = _fresh_prompt_runtime(monkeypatch, tmp_path)
    reasoning = [
        "I set up the eager-sampling bridge and applied byequiv; promising.",
        "On reflection this looks UNPROVABLE and I should give up — stuck.",
    ]
    out = rt._build_fresh_prompt(recent_reasoning=reasoning)
    # The continuation framing + the working insight are present.
    assert "your own recent reasoning before the context swap" in out.lower()
    assert "eager-sampling bridge" in out
    assert "applied byequiv" in out
    # The closed verdict is NOT forwarded as an established conclusion.
    low = out.lower()
    assert "unprovable" not in low
    assert "give up" not in low and "give-up" not in low
    # bare "stuck" is NOT a provability verdict on its own -> intentionally kept
    # (the over-strip fix): it survives the "give up -- stuck" line.
    assert "stuck" in low
    # The state-only handoff still sits underneath it.
    assert "neutral evidence" in low


def test_fresh_prompt_without_reasoning_is_state_only(monkeypatch, tmp_path):
    # Fallback path: no reasoning -> no continuation block, just today's handoff.
    rt = _fresh_prompt_runtime(monkeypatch, tmp_path)
    out = rt._build_fresh_prompt(recent_reasoning=[])
    assert "your own recent reasoning before the context swap" not in out.lower()
    assert "neutral evidence" in out.lower()


def test_fresh_prompt_reasoning_failure_falls_back(monkeypatch, tmp_path):
    # If verdict-stripping blows up, the swap must still proceed with state-only.
    rt = _fresh_prompt_runtime(monkeypatch, tmp_path)
    import workflow.proof_node_runtime as M

    def _boom(_text):
        raise RuntimeError("strip exploded")

    monkeypatch.setattr(M, "strip_closed_verdicts", _boom, raising=True)
    out = rt._build_fresh_prompt(recent_reasoning=["some working insight here"])
    # _render_recent_reasoning swallowed the error -> no continuation block, but
    # the state-only handoff is intact and the prompt was produced.
    assert "your own recent reasoning before the context swap" not in out.lower()
    assert "neutral evidence" in out.lower()
    assert "submit_proof_intent" in out


# --- generation-loop integration (drives ProofNodeRuntime.run, fakes only) ----

class _LoopAgent:
    """Scripted agent: each run() pops the next (returncode, ctx_pressure)."""

    def __init__(self, script):
        self._script = list(script)
        self.run_calls = 0
        self.close_calls = 0
        self.ctx_pressure = False
        self.mcp_failed_to_start = False
        self.session_id = "sess-fixed"

    def run(self, prompt, *, system_prompt="", mcp_config_path=None, mcp_debug_log=None):
        from workflow.proof_node_runtime import ClaudeRunResult

        self.run_calls += 1
        rc, pressure = self._script.pop(0) if self._script else (0, False)
        self.ctx_pressure = pressure
        return ClaudeRunResult(text="", session_id=self.session_id, returncode=rc)

    def close(self, reason):
        self.close_calls += 1


class _LoopBridge:
    def __init__(self, *, turn_index=0, max_turns=1000):
        self._turn_index = turn_index
        self.max_turns = max_turns
        self.terminal_health = None
        self.host = "127.0.0.1"
        self.port = 0
        self.token = "t"
        self.start_calls = 0
        self.close_calls = 0

    def start(self):
        self.start_calls += 1

    def close(self):
        self.close_calls += 1


class _LoopManager:
    """Manager whose committed count grows by one each run() (progress)."""

    def __init__(self, view):
        self.latest_full_view = view
        self._committed = ["t0"]

    def _current_committed_tactics(self):
        # Each call advances progress so _made_progress sees >0 since gen start.
        self._committed = self._committed + [f"t{len(self._committed)}"]
        return list(self._committed)


class _LoopMemory:
    def __init__(self, tmp):
        self.dir = tmp
        # Mirror NodeMemory's durable file handles — the system-prompt anchor
        # (_prover_system_anchor) reads these on each run().
        self.latest_view = tmp / "latest_workspace_view.json"
        self.latest_result = tmp / "latest_manager_result.json"
        self.latest_followup = tmp / "latest_followup.md"
        self.latest_proof = tmp / "proof_so_far.md"

    def record_agent_session(self, *a, **k):
        pass


def _loop_runtime(monkeypatch, tmp_path, *, agent, bridge, manager, env=None):
    """A ProofNodeRuntime shell wired with loop fakes; side effects stubbed."""
    import workflow.proof_node_runtime as M
    from workflow.proof_node_runtime import ProofNodeRuntime

    # Stub the heavy prompt renderer and the EC-history reader the loop calls.
    monkeypatch.setattr(
        M, "render_long_lived_agent_prompt",
        lambda *a, **k: "RUNTIME_PROMPT", raising=True,
    )
    monkeypatch.setattr(M, "closed_history_tactics", lambda *a, **k: [], raising=True)

    rt = ProofNodeRuntime.__new__(ProofNodeRuntime)
    rt.manager = manager
    rt.bridge = bridge
    rt.agent = agent
    rt.memory = _LoopMemory(tmp_path)
    rt.prompt = "ORIG"
    rt.file_path = "f.ec"
    rt.lemma_name = "L"
    rt.include_dir = "."
    rt.session_tag = "tag"
    rt.node_id = "0.0"
    rt.run_dir = tmp_path
    rt.project_root = tmp_path
    rt.max_turns = bridge.max_turns
    rt.surface_profile = None
    rt.emit = lambda event: None
    rt._mcp_config_path = tmp_path / "mcp.json"
    rt._private_dir = tmp_path
    rt.checkpoints = []
    rt._write_mcp_config = lambda **k: None
    rt._checkpoint_resume_capsules = lambda: rt.checkpoints.append(1)
    rt._build_fresh_prompt = lambda *a, **k: "FRESH_PROMPT"
    return rt


def test_loop_respawn_cap_honored(monkeypatch, tmp_path):
    monkeypatch.delenv("SHANNON_DISABLE_CTX_RESPAWN", raising=False)
    monkeypatch.setenv("SHANNON_CTX_RESPAWN_MAX", "2")
    monkeypatch.delenv("SHANNON_NODE_DEADLINE_EPOCH", raising=False)
    # Every generation trips ctx_pressure -> cap is the only thing that stops it.
    agent = _LoopAgent(script=[(0, True)] * 10)
    bridge = _LoopBridge()
    manager = _LoopManager(_OPEN_VIEW)
    rt = _loop_runtime(monkeypatch, tmp_path, agent=agent, bridge=bridge, manager=manager)
    rt.run()
    # 2 respawns => 3 generations total, then the cap breaks the loop.
    assert agent.run_calls == 3
    assert len(rt.checkpoints) == 2
    # No-teardown invariant: bridge/manager started/closed exactly once each.
    assert bridge.start_calls == 1
    assert bridge.close_calls == 1


def test_loop_turn_limit_restop_no_second_respawn(monkeypatch, tmp_path):
    monkeypatch.delenv("SHANNON_DISABLE_CTX_RESPAWN", raising=False)
    monkeypatch.setenv("SHANNON_CTX_RESPAWN_MAX", "2")
    monkeypatch.delenv("SHANNON_NODE_DEADLINE_EPOCH", raising=False)
    # Gen 1: ctx_pressure (watermark) with progress -> respawn once.
    # Gen 2: turn-limit re-STOP (budget exhausted) -> must NOT respawn again, even
    # though ctx_pressure is still set, because the turn-limit guard precedes it.
    agent = _LoopAgent(script=[(0, True), (0, True)])
    bridge = _LoopBridge(turn_index=0, max_turns=1000)
    manager = _LoopManager(_OPEN_VIEW)
    rt = _loop_runtime(monkeypatch, tmp_path, agent=agent, bridge=bridge, manager=manager)

    # After the first run, exhaust the cumulative turn budget so generation 2's
    # exit is a turn-limit STOP.
    orig_run = agent.run

    def _run(*a, **k):
        res = orig_run(*a, **k)
        if agent.run_calls >= 2:
            bridge._turn_index = bridge.max_turns  # budget exhausted on gen 2
        return res

    agent.run = _run
    rt.run()
    # Gen 1 respawns (watermark). Gen 2 is turn-limit-exhausted => no 2nd respawn.
    assert agent.run_calls == 2
    assert len(rt.checkpoints) == 1


def test_loop_runway_guard_blocks_respawn(monkeypatch, tmp_path):
    monkeypatch.delenv("SHANNON_DISABLE_CTX_RESPAWN", raising=False)
    monkeypatch.setenv("SHANNON_CTX_RESPAWN_MAX", "2")
    # Deadline is ~now: the runway guard (#5) must break before any respawn even
    # though ctx_pressure + progress would otherwise trigger one.
    import time as _t
    monkeypatch.setenv("SHANNON_NODE_DEADLINE_EPOCH", repr(_t.time() + 1.0))
    agent = _LoopAgent(script=[(0, True)] * 5)
    bridge = _LoopBridge()
    manager = _LoopManager(_OPEN_VIEW)
    rt = _loop_runtime(monkeypatch, tmp_path, agent=agent, bridge=bridge, manager=manager)
    rt.run()
    assert agent.run_calls == 1           # one generation, no respawn
    assert len(rt.checkpoints) == 0


def test_loop_no_respawn_on_clean_finish(monkeypatch, tmp_path):
    monkeypatch.delenv("SHANNON_DISABLE_CTX_RESPAWN", raising=False)
    monkeypatch.setenv("SHANNON_CTX_RESPAWN_MAX", "2")
    monkeypatch.delenv("SHANNON_NODE_DEADLINE_EPOCH", raising=False)
    # Closed proof + no pressure -> common path: exactly one generation, no swap.
    agent = _LoopAgent(script=[(0, False)])
    bridge = _LoopBridge()
    manager = _LoopManager(_CLOSED_VIEW)
    rt = _loop_runtime(monkeypatch, tmp_path, agent=agent, bridge=bridge, manager=manager)
    rt.run()
    assert agent.run_calls == 1
    assert len(rt.checkpoints) == 0
    assert bridge.start_calls == 1 and bridge.close_calls == 1


# --- Layer-3 crash/exit respawn (supervisor) ---------------------------------
#
# These cover the supervisor-side fallback: `_find_node_resume_capsule`,
# `_mint_fresh_resume_capsule_from_live`, `_layer3_select_capsule`, and the pure
# admission gate `_layer3_gates_pass`. No real EC / claude / sockets — capsules
# are minted from on-disk `history.ec` only (which is exactly how Layer-3 must
# work at crash time, when the worker process is already dead).

import workflow.progress as prog
import workflow.tree.supervisor as sup
import workflow.tree.trackers as trk


def _write_live_session(cwd: Path, session_tag: str, tactics: list[str]) -> Path:
    """A dead worker's still-on-disk live EC session dir."""
    sess = Path(cwd) / f".ec_session_{session_tag}"
    sess.mkdir(parents=True, exist_ok=True)
    (sess / "history.ec").write_text(
        "".join(t + "\n" for t in tactics), encoding="utf-8"
    )
    (sess / "current.out").write_text(
        "Current goal\n  goal after " + str(len(tactics)) + " tactics\n",
        encoding="utf-8",
    )
    return sess


def _write_stale_checkpoint_capsule(
    run_dir: Path, session_tag: str, tactics: list[str]
) -> Path:
    """A pre-written in-worker checkpoint capsule (the STALE artifact).

    Mirrors what `_checkpoint_resume_capsules` leaves on disk: a capsule dir under
    `run_dir/resume_capsules/<slug>_<.ec_session_tag>/` with its own history.ec and
    a `resume.json` manifest. We make it deliberately SHORTER than the live
    session to model the post-last-swap progress that the checkpoint omits.
    """
    cap_dir = (
        Path(run_dir)
        / "resume_capsules"
        / f"Tree_0_.ec_session_{session_tag}"
    )
    cap_dir.mkdir(parents=True, exist_ok=True)
    (cap_dir / "history.ec").write_text(
        "".join(t + "\n" for t in tactics), encoding="utf-8"
    )
    manifest = {
        "kind": "proof_node_resume_capsule",
        "capsule_version": 1,
        "target": {"file": "f.ec", "lemma": "L", "include_dir": ""},
        "source": {},
        "replay": {
            "history_file": "history.ec",
            "tactic_count": len(tactics),
            "current_goal_hash": "stalehash000",
            "current_goal_preview": "stale goal",
        },
        "score": {"value": 1.0, "reasons": [], "route_family": {}},
        "lineage": {"route_family": {}},
        "handoff": {"notes": []},
    }
    (cap_dir / "resume.json").write_text(json.dumps(manifest), encoding="utf-8")
    return cap_dir / "resume.json"


# --- _find_node_resume_capsule -----------------------------------------------

def test_find_node_resume_capsule_picks_freshest(tmp_path):
    run_dir = tmp_path / "run"
    tag = "prover_tree_0"
    _write_stale_checkpoint_capsule(run_dir, tag, ["proc.", "wp."])
    # A second, NEWER capsule dir for the same session (also endswith the tag).
    newer = run_dir / "resume_capsules" / f"Tree_0_alt_.ec_session_{tag}"
    newer.mkdir(parents=True)
    (newer / "resume.json").write_text("{}", encoding="utf-8")
    import os as _os, time as _t
    _os.utime(newer / "resume.json", (_t.time() + 100, _t.time() + 100))

    found = prog._find_node_resume_capsule(run_dir, tag)
    assert found == newer / "resume.json"


def test_find_node_resume_capsule_none_when_absent(tmp_path):
    assert prog._find_node_resume_capsule(tmp_path / "run", "prover_tree_9") is None
    # capsules dir exists but holds only a non-matching tag.
    other = tmp_path / "run" / "resume_capsules" / "Tree_5_.ec_session_prover_tree_5"
    other.mkdir(parents=True)
    (other / "resume.json").write_text("{}", encoding="utf-8")
    assert prog._find_node_resume_capsule(tmp_path / "run", "prover_tree_0") is None


# --- _mint_fresh_resume_capsule_from_live ------------------------------------

def test_mint_fresh_capsule_reads_dead_session_history(tmp_path):
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    tag = "prover_tree_0"
    _write_live_session(cwd, tag, ["proc.", "inline *.", "wp.", "skip."])

    manifest = prog._mint_fresh_resume_capsule_from_live(
        cwd=str(cwd), run_dir=run_dir, session_tag=tag,
        target_file="f.ec", lemma="L",
    )
    assert manifest is not None and manifest.is_file()
    loaded = prog._load_resume_capsule(manifest)
    # The FRESH prefix reflects the full live history, including post-swap tactics.
    assert loaded.replay_prefix == ["proc.", "inline *.", "wp.", "skip."]
    # And it carries a real, consistent goal hash derived from the same state.
    assert loaded.current_goal_hash


def test_mint_fresh_capsule_none_when_live_dir_missing(tmp_path):
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    # No .ec_session dir at all.
    assert prog._mint_fresh_resume_capsule_from_live(
        cwd=str(cwd), run_dir=run_dir, session_tag="prover_tree_0",
        target_file="f.ec", lemma="L",
    ) is None


def test_mint_fresh_capsule_none_when_history_empty(tmp_path):
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    tag = "prover_tree_0"
    sess = cwd / f".ec_session_{tag}"
    sess.mkdir()
    (sess / "history.ec").write_text("   \n\n", encoding="utf-8")  # blank only
    assert prog._mint_fresh_resume_capsule_from_live(
        cwd=str(cwd), run_dir=run_dir, session_tag=tag,
        target_file="f.ec", lemma="L",
    ) is None


# --- _layer3_select_capsule: the load-bearing fresh-vs-stale decision --------

def test_layer3_prefers_fresh_live_over_stale_checkpoint(tmp_path):
    """The fix: when the live session has MORE tactics than the stale checkpoint,
    Layer-3 must replay the LIVE prefix, not the lagged checkpoint prefix.

    Reverting to a checkpoint-only path would return the 2-tactic stale prefix and
    fail this assertion.
    """
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    tag = "prover_tree_0"
    # Checkpoint was written at the last swap (2 tactics); the worker then
    # committed two MORE in the final generation before dying (4 tactics live).
    _write_stale_checkpoint_capsule(run_dir, tag, ["proc.", "wp."])
    _write_live_session(cwd, tag, ["proc.", "wp.", "inline *.", "skip."])

    selected = prog._layer3_select_capsule(
        cwd=str(cwd), run_dir=run_dir, session_tag=tag,
        source_file="f.ec", target_lemma="L",
    )
    assert selected is not None
    manifest, source = selected
    assert source == "live"
    loaded = prog._load_resume_capsule(manifest)
    # Post-swap progress preserved: full 4-tactic live prefix, NOT the stale 2.
    assert loaded.replay_prefix == ["proc.", "wp.", "inline *.", "skip."]
    # Drift-safety: the recorded goal hash is NOT the stale capsule's hash; it is
    # freshly derived from the same live state the prefix ends at.
    assert loaded.current_goal_hash != "stalehash000"
    assert loaded.current_goal_hash


def test_layer3_falls_back_to_stale_when_live_dir_missing(tmp_path):
    """No live session dir (e.g. cleaned/unreadable) -> use the stale checkpoint."""
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    tag = "prover_tree_0"
    stale = _write_stale_checkpoint_capsule(run_dir, tag, ["proc.", "wp."])
    # No .ec_session dir under cwd.

    selected = prog._layer3_select_capsule(
        cwd=str(cwd), run_dir=run_dir, session_tag=tag,
        source_file="f.ec", target_lemma="L",
    )
    assert selected is not None
    manifest, source = selected
    assert source == "checkpoint"
    assert manifest == stale


def test_layer3_none_when_neither_capsule_exists(tmp_path):
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    assert prog._layer3_select_capsule(
        cwd=str(cwd), run_dir=run_dir, session_tag="prover_tree_0",
        source_file="f.ec", target_lemma="L",
    ) is None


def test_layer3_mint_failure_falls_back_to_stale(tmp_path, monkeypatch):
    """Minting from live is best-effort: if create_resume_capsules raises, the
    selector must not crash and must fall back to the stale checkpoint."""
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    tag = "prover_tree_0"
    _write_live_session(cwd, tag, ["proc.", "wp.", "inline *.", "skip."])
    stale = _write_stale_checkpoint_capsule(run_dir, tag, ["proc.", "wp."])

    import workflow.proof_node_resume as pnr

    def _boom(*a, **k):
        raise RuntimeError("simulated mint failure")

    monkeypatch.setattr(pnr, "create_resume_capsules", _boom)
    selected = prog._layer3_select_capsule(
        cwd=str(cwd), run_dir=run_dir, session_tag=tag,
        source_file="f.ec", target_lemma="L",
    )
    assert selected is not None
    manifest, source = selected
    assert source == "checkpoint"
    assert manifest == stale


# --- _layer3_gates_pass: each gate independently -----------------------------

def _gate_kwargs(**over):
    base = dict(
        respawn_disabled=False,
        already_respawned=False,
        proved=False,
        supervisor_killed=False,
        worker_crashed=True,
        context_respawn_count=1,
        committed_count=5,
        depth=1,
        max_depth=4,
        has_run_dir=True,
        has_runway=True,
    )
    base.update(over)
    return base


def test_layer3_gates_pass_when_all_satisfied():
    assert prog._layer3_gates_pass(**_gate_kwargs()) is True


def test_layer3_gate_kill_switch():
    assert prog._layer3_gates_pass(**_gate_kwargs(respawn_disabled=True)) is False


def test_layer3_gate_one_shot_already_respawned():
    assert prog._layer3_gates_pass(**_gate_kwargs(already_respawned=True)) is False


def test_layer3_gate_proved():
    assert prog._layer3_gates_pass(**_gate_kwargs(proved=True)) is False


def test_layer3_gate_no_context_respawn():
    assert prog._layer3_gates_pass(**_gate_kwargs(context_respawn_count=0)) is False


def test_layer3_gate_no_context_respawn_but_has_replay_prefix():
    """Continuation nodes (Layer-3 children / resume roots) bypass the
    context_respawn_count gate — they are from degraded lineage by definition."""
    assert prog._layer3_gates_pass(
        **_gate_kwargs(context_respawn_count=0, has_replay_prefix=True)
    ) is True


def test_layer3_gate_no_committed_progress():
    assert prog._layer3_gates_pass(**_gate_kwargs(committed_count=0)) is False


def test_layer3_gate_depth_cap():
    assert prog._layer3_gates_pass(**_gate_kwargs(depth=4, max_depth=4)) is False


def test_layer3_gate_no_run_dir():
    assert prog._layer3_gates_pass(**_gate_kwargs(has_run_dir=False)) is False


def test_layer3_gate_no_runway():
    assert prog._layer3_gates_pass(**_gate_kwargs(has_runway=False)) is False


# --- Layer-3 is CRASH-ONLY: a clean give-up must NOT pass the gate -----------
#
# With Layer-2 removed, a clean give-up exits gracefully (returncode 0 + a final
# `result` event) and surfaces as `finished and not proved` — but it is a real,
# measurable agent decision and must end the run, never respawn. Only an abnormal
# worker death (crash) is an infra death we recover by replay. Revert-sensitive:
# deleting the `if not worker_crashed: return False` line flips the clean-give-up
# case to True and fails `test_layer3_gate_blocks_clean_give_up`.

def test_layer3_gate_blocks_clean_give_up():
    # Clean give-up = graceful exit, no crash. All other gates satisfied; the
    # crash gate alone must reject it.
    assert prog._layer3_gates_pass(**_gate_kwargs(worker_crashed=False)) is False


def test_layer3_gate_allows_crash():
    # Abnormal worker death (crash) with everything else satisfied: eligible.
    assert prog._layer3_gates_pass(**_gate_kwargs(worker_crashed=True)) is True


# --- FIX: Layer-3 must fire only on a worker SELF-exit, never a supervisor kill -
#
# `_kill_node` sets BOTH `finished` and `supervisor_killed`. Without the
# `supervisor_killed` gate a deliberately-killed DEGRADED node (drift / hygiene /
# destructive / capacity / progress-gap / grace) would pass every other gate and
# get resurrected by Layer-3 — defeating the drift gate and replaying a tainted
# prefix. These lock the gate to a worker self-exit only.

def test_layer3_gate_blocks_supervisor_killed_node():
    # All other conditions satisfied; only `supervisor_killed` differs. Removing
    # the `if supervisor_killed: return False` line in `_layer3_gates_pass` would
    # flip this to True and fail — so this is revert-sensitive to the fix.
    assert prog._layer3_gates_pass(**_gate_kwargs(supervisor_killed=True)) is False


def test_layer3_gate_allows_worker_self_exit():
    # Same inputs, supervisor_killed=False with a crash (worker_crashed=True per
    # the default): the node remains eligible. Pairs with the test above to prove
    # the gate toggles ON exactly the supervisor_killed flag and nothing else.
    assert prog._layer3_gates_pass(**_gate_kwargs(supervisor_killed=False)) is True


# --- monitor-loop wiring: finished-scan + gate ordering invariant ------------
#
# A faithful, minimal slice of `run_tree_prover`'s per-iteration tail (lines
# ~3819-3828): scan `nodes.values()` (NOT `_active_nodes()`) for finished &
# not-proved nodes and call `_maybe_layer3_crash_respawn`. We drive it with FAKE
# trackers/nodes — no subprocess / EC / claude — to assert (a) Layer-3 IS reached
# for a degraded self-exit and (b) is NOT reached for a supervisor kill.
#
# COVERED: the finished-scan iterating `nodes.values()` (so a just-finished node
#   is still seen), the `finished and not proved` predicate, and that the real
#   `_maybe_layer3_crash_respawn` gate decision flows from the real tracker flags
#   (we call the real `_layer3_gates_pass`, only stubbing the capsule/respawn I/O).
# NOT COVERED (would need real subprocess plumbing): `poll_lines` stdout draining,
#   `_active_nodes()` snapshot taken BEFORE poll, winner/drift kill branches, the
#   capsule-mint + `_spawn_node` machinery. Those are exercised by the dedicated
#   capsule tests above and the runtime-loop tests; here we lock the SCAN+GATE.

class _GateProc:
    def __init__(self, returncode=None):
        self.returncode = returncode


class _GateTracker:
    """Minimal tracker carrying exactly the fields the finished-scan + gate read.

    By default models a CRASH (no clean final-result emitted + killed exit) so the
    self-exit eligibility tests stay green; pass `final_result_emitted=True` /
    `returncode=0` to model a clean give-up.
    """

    def __init__(self, *, finished, proved, supervisor_killed,
                 context_respawn_count=1, committed_count=5,
                 final_result_emitted=False, returncode=137):
        self.finished = finished
        self.proved = proved
        self.supervisor_killed = supervisor_killed
        self.context_respawn_count = context_respawn_count
        self.committed_count = committed_count
        self.final_result_emitted = final_result_emitted
        self.proc = _GateProc(returncode=returncode)


class _GateNode:
    def __init__(self, node_id, tracker, *, depth=1):
        self.node_id = node_id
        self.tracker = tracker
        self.depth = depth
        self.layer3_respawned = False
        self.children = []


def _run_finished_scan(nodes, *, on_respawn_attempt):
    """Faithful copy of the loop tail at progress.py ~3819-3828.

    Iterates `nodes.values()` (the load-bearing choice: a finished/killed node is
    NOT in `_active_nodes()`, so scanning actives would skip it and Layer-3 would
    never fire). For each finished-&-not-proved node it runs the REAL Layer-3
    admission gate against the node's REAL tracker flags; `on_respawn_attempt`
    records which node ids passed the gate (would have been respawned).
    """
    for node in list(nodes.values()):
        if node.tracker.finished and not node.tracker.proved:
            t = node.tracker
            rc = t.proc.returncode if getattr(t, "proc", None) is not None else None
            worker_crashed = (
                (rc is not None and rc != 0)
                or not bool(getattr(t, "final_result_emitted", False))
            )
            if prog._layer3_gates_pass(
                respawn_disabled=False,
                already_respawned=bool(node.layer3_respawned),
                proved=bool(t.proved),
                supervisor_killed=bool(getattr(t, "supervisor_killed", False)),
                worker_crashed=worker_crashed,
                context_respawn_count=int(getattr(t, "context_respawn_count", 0) or 0),
                committed_count=int(getattr(t, "committed_count", 0) or 0),
                depth=int(node.depth),
                max_depth=4,
                has_run_dir=True,
                has_runway=True,
            ):
                on_respawn_attempt(node.node_id)


def test_loop_layer3_reached_for_degraded_self_exit():
    # Single/last degraded node that SELF-exited with the proof open: the
    # finished-scan must see it (it is no longer "active") and the gate admits it.
    seen = []
    nodes = {
        "0.0": _GateNode(
            "0.0",
            _GateTracker(finished=True, proved=False, supervisor_killed=False),
        )
    }
    _run_finished_scan(nodes, on_respawn_attempt=seen.append)
    assert seen == ["0.0"]


def test_loop_layer3_not_reached_for_supervisor_killed_node():
    # Same node, but the supervisor KILLED it (`_kill_node` set both flags):
    # the finished-scan still sees it, but the gate now rejects it.
    seen = []
    nodes = {
        "0.0": _GateNode(
            "0.0",
            _GateTracker(finished=True, proved=False, supervisor_killed=True),
        )
    }
    _run_finished_scan(nodes, on_respawn_attempt=seen.append)
    assert seen == []


def test_loop_layer3_not_reached_for_clean_give_up():
    # A degraded node that CLEANLY gave up (graceful exit: returncode 0 + a final
    # `result` event) self-exits with the proof open. The finished-scan sees it,
    # but the crash-only gate now rejects it -> the run ends on the give-up.
    seen = []
    nodes = {
        "0.0": _GateNode(
            "0.0",
            _GateTracker(
                finished=True, proved=False, supervisor_killed=False,
                final_result_emitted=True, returncode=0,
            ),
        )
    }
    _run_finished_scan(nodes, on_respawn_attempt=seen.append)
    assert seen == []


def test_loop_finished_scan_iterates_all_nodes_not_active():
    # Ordering invariant: the scan iterates nodes.values(), so even a node that
    # is finished (hence excluded from _active_nodes) is still considered for
    # Layer-3. A refactor that scanned only active nodes would drop it -> [].
    seen = []
    nodes = {
        "0.0": _GateNode(  # finished self-exit -> eligible
            "0.0",
            _GateTracker(finished=True, proved=False, supervisor_killed=False),
        ),
        "0.1": _GateNode(  # still running -> not finished -> skipped
            "0.1",
            _GateTracker(finished=False, proved=False, supervisor_killed=False),
        ),
    }
    _run_finished_scan(nodes, on_respawn_attempt=seen.append)
    assert seen == ["0.0"]


# NOTE: the former `test_kill_node_sets_supervisor_killed_flag` was a fragile
# `inspect.getsource(run_tree_prover)` STRING-MATCH guard — a workaround from when
# `_kill_node` / `_maybe_layer3_crash_respawn` were unreachable closures. Now that
# they live in NodeSupervisor, and the same contract is exercised end-to-end by
# `test_real_loop_layer3_skips_supervisor_killed` below (whose documented
# revert-sensitivity catches both "drop supervisor_killed=True in _kill_node" and
# "drop the gate's supervisor_killed= thread"), the string-match added nothing but
# refactor-brittleness, so it was removed (NodeSupervisor extraction, blueprint §4.3).


# --- REAL run_tree_prover drive: finished-scan -> _maybe_layer3_crash_respawn --
#
# WHY this exists (the gap these close):
#   The `_run_finished_scan` slice above is a hand-reimplemented COPY of the loop
#   tail; it does NOT execute the real `run_tree_prover` monitor loop, the real
#   finished-scan (`for node in list(nodes.values())` at progress.py:3842), or the
#   real nested closure `_maybe_layer3_crash_respawn` (progress.py:3330). So two
#   specific refactors the audit worried about would pass every existing test yet
#   silently break Layer-3:
#     (a) changing the finished-scan to iterate `_active_nodes()` instead of
#         `nodes.values()` — a finished node is excluded from `_active_nodes()`
#         (progress.py:3327-3328), so Layer-3 would never fire for it;
#     (b) dropping the `supervisor_killed=` argument threaded from the real
#         tracker into `_layer3_gates_pass` (progress.py:3376) — a supervisor-
#         killed degraded node would then be wrongly resurrected.
#
# These tests DRIVE THE REAL `run_tree_prover` end-to-end with fakes (an OS-pipe-
# backed fake worker process + a fake `build_cmd_fn`), exercising the real loop,
# real finished-scan, real `_maybe_layer3_crash_respawn`, and real
# `_layer3_gates_pass`. Only the capsule mint/load I/O at the *tail* of the
# closure is stubbed (those are covered by the dedicated capsule tests above), so
# we observe whether the closure REACHED the respawn (called `_load_resume_capsule`
# + `_spawn_node`, minting a `0.0.r*` child) without standing up real EC.
#
# Revert-sensitivity is proven in the module docstring of each test and verified
# out-of-band by mutating the two call-site lines and re-running (see the task
# report): scanning `_active_nodes()` makes test (1)/(3) fail; dropping the
# `supervisor_killed=` thread makes test (2) fail.

import os as _os
import subprocess as _subprocess


class _PipeProc:
    """A fake `subprocess.Popen` backed by a real OS pipe.

    A real pipe fd is used so `_ProverTracker.poll_lines` exercises its genuine
    code paths: `select.select([stdout], ...)` + `readline()` while alive, and the
    `for line in stdout` drain on exit. `script` is a list of stream-json lines
    written immediately; `exit_code` is returned by `poll()`/`wait()` so the
    process reads as a SELF-EXIT (no supervisor involvement). When `stay_alive`
    is False (default) the write end is closed right away so the first poll drains
    the script and marks the tracker finished.
    """

    def __init__(self, script, *, exit_code=0, stay_alive=False):
        r, w = _os.pipe()
        self.stdout = _os.fdopen(r, "r")
        self.stderr = None
        self._w = _os.fdopen(w, "w")
        for line in script:
            self._w.write(line.rstrip("\n") + "\n")
        self._w.flush()
        self._exit_code = exit_code
        self.returncode = exit_code
        if not stay_alive:
            self._w.close()
            self._w = None
        self.pid = -1
        self._stay_alive = stay_alive

    def poll(self):
        # `stay_alive` processes report running until explicitly finished; a
        # closed write end means the worker has exited.
        if self._stay_alive and self._w is not None:
            return None
        return self._exit_code

    def wait(self, timeout=None):
        return self._exit_code

    def terminate(self):
        if self._w is not None:
            self._w.close()
            self._w = None

    def kill(self):
        self.terminate()

    def send_signal(self, sig):
        pass


# The 7 function-object attributes run_tree_prover exposes as its caller contract
# (read via getattr by prover.py:3131/3163-3170 + two tests). The NodeSupervisor
# refactor moves the computation into the supervisor but MUST keep writing these
# back onto the run_tree_prover function object (blueprint §3.5 / risk #10).
_RUN_TREE_PROVER_LAST_ATTRS = (
    "last_session_id",
    "last_session_ids",
    "last_ec_session_dir",
    "last_information_source_audit",
    "last_payload_audit_path",
    "last_destructive_abort",
    "last_destructive_reason",
)


def _system_marker(n=1, node="0.0"):
    return json.dumps({"type": "system", "context_respawn": n, "node": node})


def _win_event(text="Proof complete [ALL_GOALS_CLOSED]"):
    """A `user`/tool_result block carrying the [ALL_GOALS_CLOSED] success marker
    (`_is_proof_success`, progress.py:828) — drives tracker.proved=True via the
    text-progress fallback, so the loop winner-detect (3486) fires."""
    return json.dumps({
        "type": "user",
        "message": {"content": [{"type": "tool_result", "content": text}]},
    })


def _result_event(text=""):
    # A clean `result` event finishes the worker with proved=False and, crucially,
    # context_respawn_count unchanged (so a non-degraded child won't re-respawn).
    return json.dumps({"type": "result", "result": text, "session_id": "s"})


class _ScriptedSpawns:
    """Per-node stdout scripts; `build_cmd_fn` encodes the node_id into the cmd
    so the patched `Popen` can pick the right script for each spawn."""

    def __init__(self, scripts):
        # scripts: dict[node_id_substring] -> (list_of_lines, dict(proc_kwargs))
        self.scripts = scripts
        self.spawned_node_ids: list[str] = []

    def build_cmd_fn(self, session_tag, node_id, replay_prefix, negative_signal,
                     **kwargs):
        self.spawned_node_ids.append(node_id)
        return ["fake-claude", "--node", node_id]

    def popen(self, cmd, *a, **k):
        node_id = cmd[cmd.index("--node") + 1] if "--node" in cmd else ""
        for key, (script, proc_kwargs) in self.scripts.items():
            if key in node_id:
                return _PipeProc(list(script), **proc_kwargs)
        # Default: an immediate clean finish (keeps the loop terminating).
        return _PipeProc([_result_event()])


def _seed_live_history(cwd: Path, node_id: str, tactics: list[str]) -> Path:
    """Create the dead worker's still-on-disk live EC session so the real
    `committed_count` (which reads history.ec, progress.py:2150) is > 0 and a
    fresh capsule could be minted from it."""
    tag = f"prover_tree_{node_id.replace('.', '_')}"
    sess = Path(cwd) / f".ec_session_{tag}"
    sess.mkdir(parents=True, exist_ok=True)
    (sess / "history.ec").write_text(
        "".join(t + "\n" for t in tactics), encoding="utf-8"
    )
    (sess / "current.out").write_text(
        "Current goal\n  open goal after " + str(len(tactics)) + " tactics\n",
        encoding="utf-8",
    )
    return sess


class _FakeLoaded:
    """Stand-in for a loaded ProofNodeResumeCapsule with a non-empty replay
    prefix, so the real `_maybe_layer3_crash_respawn` proceeds to `_spawn_node`."""

    def __init__(self, replay_prefix):
        self.replay_prefix = list(replay_prefix)
        self.current_goal_hash = "freshhash"
        self.current_goal_preview = "open goal"
        self.resume_context = {}


def _drive_real_tree_prover(monkeypatch, tmp_path, *, scripts, seed,
                            initial_branches=None, capture,
                            spawner_cls=_ScriptedSpawns):
    """Run the REAL `run_tree_prover` with fakes, recording respawn observations.

    `capture` is a dict mutated in place: 'select_calls' (session_tags the real
    closure asked to mint/select a capsule for -> proves the gate PASSED) and
    'load_calls'. We patch the capsule mint/load at the closure's tail so no real
    EC is touched, but the gate + finished-scan + `_spawn_node` are all REAL.
    `spawner_cls` lets a test substitute a `_ScriptedSpawns` subclass whose
    `build_cmd_fn` misbehaves (e.g. raises, modelling a bootstrap failure).
    """
    scr = spawner_cls(scripts)
    monkeypatch.setattr(sup.subprocess, "Popen", scr.popen, raising=True)
    # Keep the loop fast and non-blocking; status/teardown stubbed harmlessly.
    monkeypatch.setattr(prog.time, "sleep", lambda *_a, **_k: None, raising=True)
    monkeypatch.setattr(sup, "_terminate_process_tree",
                        lambda *a, **k: None, raising=True)

    def _spy_select_capsule(*, cwd, run_dir, session_tag, **kw):
        capture.setdefault("select_calls", []).append(session_tag)
        # Return a sentinel manifest path; the real closure then calls
        # `_load_resume_capsule` on it (patched below).
        return (Path(run_dir) / f"{session_tag}.json", "live")

    def _spy_load(path):
        capture.setdefault("load_calls", []).append(str(path))
        return _FakeLoaded(["proc.", "wp."])

    monkeypatch.setattr(sup, "_layer3_select_capsule", _spy_select_capsule,
                        raising=True)
    monkeypatch.setattr(sup, "_load_resume_capsule", _spy_load, raising=True)

    for nid, tactics in seed.items():
        _seed_live_history(Path(tmp_path / "cwd"), nid, tactics)
    (tmp_path / "cwd").mkdir(exist_ok=True)
    run_dir = tmp_path / "run"
    run_dir.mkdir(exist_ok=True)

    result = prog.run_tree_prover(
        scr.build_cmd_fn,
        cwd=str(tmp_path / "cwd"),
        # > 180s so the Layer-3 wall-clock runway guard (min_runway_seconds, default
        # 180) is satisfied at ~0s elapsed; `time.sleep` is stubbed so the loop still
        # returns in real-time ~0.
        timeout=600,
        max_concurrent=4,
        initial_provers=1,
        check_interval=0,
        min_alive_seconds=0,
        grace_seconds=10_000,           # never grace-kill in these short drives
        stuck_idle_seconds=10_000,
        stuck_errors=10_000,
        source_file="f.ec",
        target_lemma="L",
        initial_branches=initial_branches,
        payload_audit_path=str(run_dir / "payload_audit.jsonl"),
    )
    # Characterization: snapshot the caller-contract function attributes + return
    # tuple. These are the observable surface the NodeSupervisor refactor must keep
    # byte-identical (blueprint risk #10 + #11). Harmless for existing tests that
    # ignore these capture keys.
    capture["return_tuple"] = result
    capture["last_attrs"] = {
        k: getattr(prog.run_tree_prover, k, "__MISSING__")
        for k in _RUN_TREE_PROVER_LAST_ATTRS
    }
    return scr, result


def test_real_loop_layer3_respawns_degraded_self_exit(monkeypatch, tmp_path):
    """INVARIANTS 1 + 3 via the REAL loop.

    A single/last node `0.0` SELF-EXITS (worker process ends, no `result` win)
    while degraded (`context_respawn` marker -> context_respawn_count>0) with the
    proof OPEN and >=1 committed tactic (seeded history.ec). The REAL finished-scan
    (which iterates `nodes.values()`, NOT `_active_nodes()`) must still see this
    now-finished node and the REAL `_maybe_layer3_crash_respawn` must REACH the
    respawn: it mints/selects a capsule, loads it, and `_spawn_node`s a `0.0.r*`
    child.

    REVERT-SENSITIVITY: if the finished-scan is changed to iterate
    `_active_nodes()`, node `0.0` (finished -> excluded from actives) is never
    scanned, `_maybe_layer3_crash_respawn` is never called, and
    `capture['select_calls']` stays empty -> this test FAILS. (Verified out-of-band
    by mutating progress.py:3842.)
    """
    monkeypatch.delenv("SHANNON_DISABLE_CTX_RESPAWN", raising=False)
    monkeypatch.delenv("SHANNON_NODE_DEADLINE_EPOCH", raising=False)
    capture: dict = {}
    # `0.0`: degraded self-exit (context_respawn marker, no `result`). The pipe
    # write end closes immediately so the first poll drains+finishes the node.
    # The `0.0.r0` respawn child finishes cleanly (a `result`, no marker) so the
    # gate's context_respawn_count==0 check stops a second respawn and the loop
    # terminates.
    scripts = {
        ".r": ([_result_event()], {}),               # any respawn child: clean
        "0.0": ([_system_marker(n=1)], {"exit_code": 0}),
    }
    scr, _ = _drive_real_tree_prover(
        monkeypatch, tmp_path,
        scripts=scripts, seed={"0.0": ["proc.", "wp.", "inline *."]},
        capture=capture,
    )
    # The real closure reached the respawn for node 0.0's session tag.
    assert capture.get("select_calls") == ["prover_tree_0_0"]
    assert capture.get("load_calls")  # capsule was loaded -> _spawn_node ran
    # A respawn child was actually minted (proves _spawn_node fired, not just the
    # gate). build_cmd_fn is called once per spawn; the second is the r-child.
    assert any(nid.startswith("0.0.r") for nid in scr.spawned_node_ids), (
        scr.spawned_node_ids
    )


def test_real_loop_layer3_skips_clean_give_up(monkeypatch, tmp_path):
    """CRASH-ONLY via the REAL loop: a degraded CLEAN GIVE-UP is NOT respawned.

    Node `0.0` is degraded (a `context_respawn` marker -> context_respawn_count>0)
    and committed (seeded history.ec), so every Layer-3 gate EXCEPT the new
    crash-only gate is satisfied. But it then emits a clean `result` event and
    exits 0 — a graceful give-up. The REAL `_maybe_layer3_crash_respawn` computes
    `worker_crashed=False` (returncode 0 + `final_result_emitted` set by the
    `result` event) and the REAL `_layer3_gates_pass` must REJECT it -> the run
    ends on the give-up, no capsule selected, no `0.0.r*` child.

    REVERT-SENSITIVITY: deleting the `if not worker_crashed: return False` line in
    `_layer3_gates_pass` flips this node back to eligible -> `select_calls`
    becomes non-empty and a `0.0.r*` child is minted -> this test FAILS.
    """
    monkeypatch.delenv("SHANNON_DISABLE_CTX_RESPAWN", raising=False)
    monkeypatch.delenv("SHANNON_NODE_DEADLINE_EPOCH", raising=False)
    capture: dict = {}
    # Degraded marker FIRST (sets context_respawn_count>0), then a clean `result`
    # (sets final_result_emitted) with exit_code 0 -> a graceful give-up, not a crash.
    scripts = {
        ".r": ([_result_event()], {}),
        "0.0": ([_system_marker(n=1), _result_event()], {"exit_code": 0}),
    }
    scr, _ = _drive_real_tree_prover(
        monkeypatch, tmp_path,
        scripts=scripts, seed={"0.0": ["proc.", "wp.", "inline *."]},
        capture=capture,
    )
    # Clean give-up -> crash gate rejects -> Layer-3 never selected a capsule.
    assert capture.get("select_calls", []) == []
    assert capture.get("load_calls", []) == []
    assert not any(nid.startswith("0.0.r") for nid in scr.spawned_node_ids), (
        scr.spawned_node_ids
    )


def test_real_loop_layer3_skips_supervisor_killed(monkeypatch, tmp_path):
    """INVARIANT 2 via the REAL loop: a SUPERVISOR-KILLED degraded node is NOT
    resurrected by Layer-3.

    We spawn `0.0` as a RESUME root with an `expected_goal_hash`, then make its
    observed session snapshot mismatch the replay prefix so the REAL resume-drift
    gate (progress.py:3783-3816) calls the REAL `_kill_node`, which sets BOTH
    `finished=True` and `supervisor_killed=True` (progress.py:3588-3593). In the
    SAME iteration the REAL finished-scan then calls the REAL
    `_maybe_layer3_crash_respawn`, whose gate reads the REAL tracker's
    `supervisor_killed` flag (threaded at progress.py:3376) and must REJECT it.

    REVERT-SENSITIVITY: if the `supervisor_killed=` argument is dropped from the
    `_layer3_gates_pass(...)` call in `_maybe_layer3_crash_respawn`
    (progress.py:3376), the killed-but-otherwise-eligible node passes the gate and
    `capture['select_calls']` becomes non-empty -> this test FAILS. (Verified
    out-of-band by mutating progress.py:3376.)
    """
    monkeypatch.delenv("SHANNON_DISABLE_CTX_RESPAWN", raising=False)
    monkeypatch.delenv("SHANNON_NODE_DEADLINE_EPOCH", raising=False)
    capture: dict = {}

    # Force a drift kill: the observed history must DIFFER from the replay prefix
    # so `_resume_replay_gate` returns a drift_reason. We patch `_session_snapshot`
    # for node 0.0's session dir to a crafted snapshot.
    from workflow.session_observer import WorkflowSessionSnapshot

    drift_snapshot = WorkflowSessionSnapshot(
        session_dir=".ec_session_prover_tree_0_0",
        exists=True,
        ok=True,
        status="open",
        history_exists=True,
        # Mismatch vs replay_prefix=["proc.","wp."] -> drift_reason fires.
        history_tactics=["WRONG.", "DIFFERENT."],
        active_tool_mutates=False,
        candidate_ready=False,
        final_ready=False,
    )
    real_snapshot = prog._session_snapshot

    def _snap(cwd, session_dir):
        if session_dir and "prover_tree_0_0" in str(session_dir):
            return drift_snapshot
        return real_snapshot(cwd, session_dir)

    monkeypatch.setattr(trk, "_session_snapshot", _snap, raising=True)

    # `0.0` is degraded (context_respawn marker) and committed (seeded history.ec)
    # so EVERY Layer-3 gate EXCEPT `supervisor_killed` is satisfied — isolating the
    # flag. It stays ALIVE long enough for the drift gate to kill it; once the
    # supervisor kills it (terminate -> closes pipe), the next poll finishes it.
    scripts = {
        ".r": ([_result_event()], {}),
        "0.0": ([_system_marker(n=1)], {"exit_code": 0, "stay_alive": True}),
    }
    branches = [{
        "replay_prefix": ["proc.", "wp."],
        "expected_goal_hash": "expected_hash_that_wont_match",
        "resume_root_policy": "score",
    }]
    scr, _ = _drive_real_tree_prover(
        monkeypatch, tmp_path,
        scripts=scripts, seed={"0.0": ["proc.", "wp.", "inline *."]},
        initial_branches=branches, capture=capture,
    )
    # The supervisor killed 0.0 (drift); Layer-3 must NOT have selected a capsule.
    assert capture.get("select_calls", []) == []
    assert capture.get("load_calls", []) == []
    # And no respawn child was minted.
    assert not any(nid.startswith("0.0.r") for nid in scr.spawned_node_ids), (
        scr.spawned_node_ids
    )


class _BootstrapTimeoutSpawns(_ScriptedSpawns):
    """`build_cmd_fn` raises ReplBackendTimeout for the Layer-3 respawn child.

    In production `build_cmd_fn` is `_build_tree_cmd` (workflow/agents/prover.py),
    which bootstraps the managed session BEFORE returning the worker cmd:
    `_prepare_managed_session` -> `manager.bootstrap` ->
    `repl.start(replay_prefix)`. A deep replay prefix can blow the aggregate
    replay budget there and raise `ReplBackendTimeout` out of the cmd build —
    this subclass models exactly that boundary for `.r*` respawn children.
    """

    def __init__(self, scripts):
        super().__init__(scripts)
        self.bootstrap_failures: list[str] = []

    def build_cmd_fn(self, session_tag, node_id, replay_prefix, negative_signal,
                     **kwargs):
        if ".r" in node_id:
            from workflow.proof_management.repl_session import ReplBackendTimeout
            self.bootstrap_failures.append(node_id)
            raise ReplBackendTimeout({
                "label": "replay_prefix_aggregate_budget",
                "timed_out": True,
                "timeout_seconds": 600.0,
                "replay_steps_completed": 57,
                "replay_steps_total": len(replay_prefix or []),
            })
        return super().build_cmd_fn(
            session_tag, node_id, replay_prefix, negative_signal, **kwargs
        )


def test_real_loop_survives_layer3_respawn_bootstrap_timeout(monkeypatch, tmp_path):
    """REGRESSION (2026-06-11, .worktrees/mee-ctxt-l4np): a bootstrap failure
    while spawning the Layer-3 respawn child must DEGRADE, not kill the run.

    Observed: Tree-0.0 exited degraded at 123 tactics on equiv_step4;
    `_maybe_layer3_crash_respawn` -> `_spawn_node` -> `build_cmd_fn`
    (-> `_prepare_managed_session` -> `manager.bootstrap` ->
    `repl.start(replay_prefix)`) raised
    `ReplBackendTimeout('replay_prefix_aggregate_budget')` after 600s, and the
    exception propagated uncaught through `run_tree_prover`, killing the whole
    orchestrator — losing the remaining 60+ minutes of the prover window even
    though a healthy 123-tactic live capsule existed on disk.

    Here node `0.0` self-exits degraded (same setup as
    `test_real_loop_layer3_respawns_degraded_self_exit`) so the REAL
    `_maybe_layer3_crash_respawn` reaches `_spawn_node`, whose cmd build raises
    the same `ReplBackendTimeout`. The REAL loop must: swallow it, skip the
    respawn, finish winner selection normally, and write the `run_end` payload
    audit record — clean termination, so the caller's capsule/bundle hooks
    still run.

    REVERT-SENSITIVITY: removing the try/except around `_spawn_node` in
    `_maybe_layer3_crash_respawn` makes this test ERROR with ReplBackendTimeout
    escaping `run_tree_prover`.
    """
    monkeypatch.delenv("SHANNON_DISABLE_CTX_RESPAWN", raising=False)
    monkeypatch.delenv("SHANNON_NODE_DEADLINE_EPOCH", raising=False)
    capture: dict = {}
    scripts = {
        ".r": ([_result_event()], {}),               # never reached: spawn fails
        "0.0": ([_system_marker(n=1)], {"exit_code": 0}),
    }
    scr, result = _drive_real_tree_prover(
        monkeypatch, tmp_path,
        scripts=scripts, seed={"0.0": ["proc.", "wp.", "inline *."]},
        capture=capture, spawner_cls=_BootstrapTimeoutSpawns,
    )
    # The run SURVIVED and terminated normally on the best available branch.
    output_text, rc, winner_node, proved = result
    assert winner_node == "0.0"
    assert proved is False
    # The respawn was genuinely attempted (gate passed, capsule selected+loaded,
    # `_spawn_node` reached) and the bootstrap raised inside the cmd build.
    assert capture.get("select_calls") == ["prover_tree_0_0"]
    assert capture.get("load_calls")
    assert scr.bootstrap_failures and scr.bootstrap_failures[0].startswith("0.0.r")
    # But no respawn child was registered: the failure degraded to "no respawn".
    assert not any(".r" in nid for nid in scr.spawned_node_ids), (
        scr.spawned_node_ids
    )
    # Clean termination evidence: the failure is auditable AND the loop reached
    # its normal tail (run_end record) — the artifact-writing path the original
    # crash skipped.
    audit_lines = [
        json.loads(line)
        for line in (tmp_path / "run" / "payload_audit.jsonl")
        .read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    events = [rec.get("event") for rec in audit_lines]
    assert "layer3_respawn_bootstrap_failed" in events
    assert "run_end" in events
    failed = next(
        rec for rec in audit_lines
        if rec.get("event") == "layer3_respawn_bootstrap_failed"
    )
    assert "ReplBackendTimeout" in failed.get("error", "")
    assert failed.get("node") == "Tree-0.0"
    # CHARACTERIZATION: the bootstrap-fail degradation leaves a clean caller
    # contract — no destructive abort, empty session_ids (the respawn child was
    # never registered). Pins the observable surface across the refactor.
    assert _norm_last_attrs(capture["last_attrs"]) == {
        "last_session_id": "",
        "last_session_ids": [],
        "last_ec_session_dir": ".ec_session_prover_tree_0_0",
        "last_information_source_audit": [],
        "last_payload_audit_path": "payload_audit.jsonl",
        "last_destructive_abort": False,
        "last_destructive_reason": "",
    }


# ---------------------------------------------------------------------------
# CHARACTERIZATION baseline for the NodeSupervisor refactor
#
# The four real-drive tests above already lock the layer3 decision surface
# (select/load/spawn) + (test 4) the return tuple + payload events. These add the
# remaining observable the refactor must keep byte-identical: the 7 caller-contract
# `run_tree_prover.last_*` function attributes (blueprint risk #10) + a clean
# no-layer3 finish. Golden values were captured from the CURRENT (pre-refactor)
# run_tree_prover; after the NodeSupervisor extraction every assertion below must
# still pass unchanged.
# ---------------------------------------------------------------------------


def _payload_events(tmp_path):
    p = tmp_path / "run" / "payload_audit.jsonl"
    if not p.exists():
        return []
    return [
        json.loads(line).get("event")
        for line in p.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _norm_last_attrs(attrs: dict) -> dict:
    """Reduce the two absolute-path fields to basenames so golden comparisons are
    position-independent (pytest tmp dirs differ run-to-run); the rest is stable."""
    a = dict(attrs)
    for k in ("last_ec_session_dir", "last_payload_audit_path"):
        v = a.get(k)
        a[k] = _os.path.basename(str(v)) if v else v
    return a


def test_characterization_degraded_self_exit_last_attrs(monkeypatch, tmp_path):
    """GOLDEN: the layer3-respawn scenario's full caller-contract surface.

    Same drive as test_real_loop_layer3_respawns_degraded_self_exit, but pins the
    return tuple + all 7 `run_tree_prover.last_*` attrs. `last_session_ids` carries
    exactly the respawn child (Tree-0.0.r1) it minted from the 2-tactic live capsule.
    """
    monkeypatch.delenv("SHANNON_DISABLE_CTX_RESPAWN", raising=False)
    monkeypatch.delenv("SHANNON_NODE_DEADLINE_EPOCH", raising=False)
    capture: dict = {}
    scripts = {
        ".r": ([_result_event()], {}),
        "0.0": ([_system_marker(n=1)], {"exit_code": 0}),
    }
    _drive_real_tree_prover(
        monkeypatch, tmp_path,
        scripts=scripts, seed={"0.0": ["proc.", "wp.", "inline *."]},
        capture=capture,
    )
    assert capture["return_tuple"] == ("", 0, "0.0", False)
    assert _norm_last_attrs(capture["last_attrs"]) == {
        "last_session_id": "",
        "last_session_ids": [{
            "node": "Tree-0.0.r1", "session_id": "s", "winner": False,
            "proved": False, "committed_count": 2, "max_committed_count_seen": 2,
        }],
        "last_ec_session_dir": ".ec_session_prover_tree_0_0",
        "last_information_source_audit": [],
        "last_payload_audit_path": "payload_audit.jsonl",
        "last_destructive_abort": False,
        "last_destructive_reason": "",
    }


def test_characterization_clean_finish_no_layer3(monkeypatch, tmp_path):
    """GOLDEN: a non-degraded clean finish takes no layer3 path.

    Node 0.0 emits a single tool_result (the text-progress success fallback is
    gated off by the live session dir, so proved stays False) and exits 0. No
    context_respawn marker -> not degraded -> layer3 never selects a capsule;
    `last_session_ids` is empty (no `result`-event session_id captured). Pins the
    no-respawn branch of the observable surface.
    """
    monkeypatch.delenv("SHANNON_DISABLE_CTX_RESPAWN", raising=False)
    monkeypatch.delenv("SHANNON_NODE_DEADLINE_EPOCH", raising=False)
    capture: dict = {}
    scr, _ = _drive_real_tree_prover(
        monkeypatch, tmp_path,
        scripts={"0.0": ([_win_event()], {"exit_code": 0})},
        seed={"0.0": ["proc.", "wp.", "inline *."]},
        capture=capture,
    )
    assert capture["return_tuple"] == ("", 0, "0.0", False)
    assert capture.get("select_calls", []) == []
    assert capture.get("load_calls", []) == []
    assert scr.spawned_node_ids == ["0.0"]
    assert _payload_events(tmp_path) == ["run_start", "tool_result", "run_end"]
    assert _norm_last_attrs(capture["last_attrs"]) == {
        "last_session_id": "",
        "last_session_ids": [],
        "last_ec_session_dir": ".ec_session_prover_tree_0_0",
        "last_information_source_audit": [],
        "last_payload_audit_path": "payload_audit.jsonl",
        "last_destructive_abort": False,
        "last_destructive_reason": "",
    }


def test_node_supervisor_caps_max_concurrent_at_construction(tmp_path):
    """REGRESSION (NodeSupervisor-extraction adversarial audit, BUG-1): the
    instance's max_concurrent must be the CAPPED value, because _try_spawn_from's
    'make room if needed' gate reads self.max_concurrent. The original closure read
    the capped function-local; the extraction briefly promoted the RAW kwarg to
    self, so a caller passing max_concurrent>TREE_MAX_ACTIVE_NODES would let the
    tree spawn past the hygiene cap before backstop-killing back down. __init__ now
    caps, so self.max_concurrent is the single capped source of truth.
    """
    from workflow.tree.policy import TREE_MAX_ACTIVE_NODES

    over = prog.NodeSupervisor(lambda *a, **k: ["x"], str(tmp_path), max_concurrent=6)
    assert over.max_concurrent == TREE_MAX_ACTIVE_NODES  # 6 capped to 4
    under = prog.NodeSupervisor(lambda *a, **k: ["x"], str(tmp_path), max_concurrent=2)
    assert under.max_concurrent == 2  # below the cap → unchanged
    # And the make-room gate inside _try_spawn_from must read this capped value.
    import inspect
    src = inspect.getsource(prog.NodeSupervisor._try_spawn_from)
    assert "self._n_active >= self.max_concurrent" in src


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
