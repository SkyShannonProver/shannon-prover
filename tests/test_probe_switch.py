"""Agent-facing probe visibility.

On the EasyCrypt backend a rejected commit is non-mutating and cheap to recover from,
so probe-before-every-commit was a net throughput drag (equiv_step4 / L1-vs-L4 audits).
The default agent-facing surface hides the `probe_tactic` lever; internal A/B runs can
opt back in with `SHANNON_ENABLE_PROBE=1`.
"""
import importlib

import pytest

import workflow.surface_profiles as sp


L4 = "l4_checked_action_surface"
PROBE = "probe_tactic"


@pytest.fixture
def probe_off(monkeypatch):
    monkeypatch.delenv("SHANNON_ENABLE_PROBE", raising=False)
    monkeypatch.delenv("SHANNON_DISABLE_PROBE", raising=False)
    yield


@pytest.fixture
def probe_on(monkeypatch):
    monkeypatch.setenv("SHANNON_ENABLE_PROBE", "1")
    monkeypatch.delenv("SHANNON_DISABLE_PROBE", raising=False)
    yield


def test_default_probe_is_off(probe_off):
    assert sp.probe_disabled() is True
    assert PROBE not in sp.allowed_intents_for_surface_profile(L4)
    assert PROBE not in sp.schema_intents_for_surface_profile(L4)
    ok, reason = sp.surface_profile_allows_intent(L4, PROBE)
    assert ok is False
    assert "unavailable" in reason.lower()
    assert PROBE not in (sp.effective_allowed_intents(sp.resolve_surface_profile(L4)) or set())


def test_explicit_enable_exposes_probe_for_internal_ab(probe_on):
    assert sp.probe_disabled() is False
    assert PROBE in sp.allowed_intents_for_surface_profile(L4)
    assert PROBE in sp.schema_intents_for_surface_profile(L4)
    ok, _ = sp.surface_profile_allows_intent(L4, PROBE)
    assert ok is True
    assert PROBE in (sp.effective_allowed_intents(sp.resolve_surface_profile(L4)) or set())


def test_disable_override_removes_probe_from_gate_and_schema(monkeypatch):
    monkeypatch.setenv("SHANNON_ENABLE_PROBE", "1")
    monkeypatch.setenv("SHANNON_DISABLE_PROBE", "1")
    assert sp.probe_disabled() is True
    # gate rejects probe with an explicit, helpful reason
    ok, reason = sp.surface_profile_allows_intent(L4, PROBE)
    assert ok is False
    assert "unavailable" in reason.lower()
    # not advertised in the MCP tool schema, not in allowed/effective intents
    assert PROBE not in sp.schema_intents_for_surface_profile(L4)
    assert PROBE not in sp.allowed_intents_for_surface_profile(L4)
    assert PROBE not in (sp.effective_allowed_intents(sp.resolve_surface_profile(L4)) or set())
    # replay-suffix probe is also removed
    assert "probe_replay_suffix_chunk" not in sp.allowed_intents_for_surface_profile(L4)


def test_switch_keeps_commit_and_inspect(probe_off):
    # control/inspect intents are untouched by the probe switch
    assert sp.surface_profile_allows_intent(L4, "commit_tactic")[0] is True
    assert sp.surface_profile_allows_intent(L4, "undo_last_step")[0] is True
    assert sp.surface_profile_allows_intent(L4, "lookup_symbol")[0] is True
    assert "commit_tactic" in sp.allowed_intents_for_surface_profile(L4)




def test_view_drops_probe_affordance_when_off(probe_off):
    # a view carrying a probe-bearing candidate move should have it stripped
    view = {
        "schema_version": 1,
        "kind": "prover_workspace_view",
        "current_goal": {"lines": ["g"]},
        "candidate_moves": {"moves": [{"intent": "probe_tactic", "tactic": "auto."}]},
    }
    out = sp.apply_workspace_view_surface_profile(view, L4)
    rendered = repr(out)
    # the probe intent should not survive as an offered affordance
    assert "probe_tactic" not in rendered or sp._profile_probe_enabled(
        sp.resolve_surface_profile(L4)
    ) is False


def test_l1_profile_unaffected(probe_off):
    # L1 never had probe; switch is a no-op there (still no probe, still has its controls)
    l1 = "l1_goal_projection"
    assert PROBE not in sp.allowed_intents_for_surface_profile(l1)
    assert "commit_tactic" in sp.allowed_intents_for_surface_profile(l1)


def test_off_scrubs_all_known_leak_markers(probe_off):
    """The audit (equiv_step4/pr_12/step3/CBC_upto) found these probe leaks in OFF views;
    assert each is gone after the global exit scrub."""
    view = {
        "schema_version": 1, "kind": "prover_workspace_view",
        "current_goal": {"lines": ["g"]},
        "candidate_moves": {"moves": [{
            "intent": "probe_tactic", "category": "probe", "tactic": "auto.",
            "verified": "read_only_probe_suggestion",
            "guarantee": "candidate tactic shape; proof state unchanged; probe then decide; reversible",
        }]},
        "application_context": {
            "how_to_use": "a checklist before using `probe_tactic` or `commit_tactic`.",
            "selected_handles": [{"why_relevant": "weak coverage. Probe this split point; extend it.",
                                  "verified": "read_only_probe_suggestion"}],
        },
        "last_result": {"checkpoint_options": [
            {"after_rewind_next": "Probe a smaller replacement step before recommitting."},
            {"after_rewind_next": "Inspect call_subgoals, then probe a revised call invariant."},
        ]},
    }
    off = sp.apply_workspace_view_surface_profile(view, L4)
    blob = __import__("json").dumps(off).lower()
    for marker in ("probe", "read_only_probe_suggestion", "probe then decide", "probe_tactic"):
        assert marker not in blob, (marker, blob)


def test_off_does_not_corrupt_non_probe_text(probe_off, probe_on):
    # a view with NO probe content must be byte-identical ON vs OFF (no collateral scrub)
    import json, os
    view = {
        "schema_version": 1, "kind": "prover_workspace_view",
        "current_goal": {"lines": ["equiv[A ~ B : ={x} ==> ={res}]"]},
        "facts_and_diagnostics": {"facts": {"note": "use rewrite then smt to close"}},
    }
    os.environ["SHANNON_ENABLE_PROBE"] = "1"
    os.environ.pop("SHANNON_DISABLE_PROBE", None)
    on = sp.apply_workspace_view_surface_profile(json.loads(json.dumps(view)), L4)
    os.environ.pop("SHANNON_ENABLE_PROBE", None)
    os.environ["SHANNON_DISABLE_PROBE"] = "1"
    off = sp.apply_workspace_view_surface_profile(json.loads(json.dumps(view)), L4)
    os.environ.pop("SHANNON_DISABLE_PROBE", None)
    # drop the surface_profile meta (description differs only by being scrubbed, no probe here)
    on.pop("surface_profile", None); off.pop("surface_profile", None)
    assert on == off


# --- helpers for the latent / synthetic latent-leak audit --------------------

import json as _json


def _deep_probe_hits(obj, path=""):
    """Every place (key OR string value, case-insensitive) that 'probe' survives."""
    hits = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if "probe" in str(k).lower():
                hits.append((path + "/" + str(k), "KEY"))
            hits += _deep_probe_hits(v, path + "/" + str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            hits += _deep_probe_hits(v, f"{path}[{i}]")
    elif isinstance(obj, str):
        if "probe" in obj.lower():
            hits.append((path, "STR:" + obj[:80]))
    return hits


def _all_categories(obj):
    out = []
    if isinstance(obj, dict):
        if "category" in obj:
            out.append(obj["category"])
        for v in obj.values():
            out += _all_categories(v)
    elif isinstance(obj, list):
        for v in obj:
            out += _all_categories(v)
    return out


# valid `category` enum the renderer is allowed to emit. The fix must demote to
# exactly "commit"; it must never leave the literal "probe" and never mangle it to
# a stray word like "check" (the word-level scrub must not touch the enum value).
_VALID_CATEGORIES = {"commit", "navigation", "structural", "route_health",
                     "inspect", "lookup", "control", "static_candidate"}


# === SYNTHETIC LATENT-LEAK CASES (the L1 CBC_upto data carries no probe MOVES) ===

def test_latent_a_candidate_move_probe_stripped(probe_off):
    """(a) a candidate_moves move that is itself a probe affordance."""
    view = {
        "schema_version": 1, "kind": "prover_workspace_view",
        "current_goal": {"lines": ["g"]},
        "candidate_moves": {"moves": [{
            "intent": "probe_tactic", "category": "probe", "tactic": "auto.",
            "verified": "read_only_probe_suggestion",
            "guarantee": "candidate; proof state unchanged; probe then decide; reversible",
        }]},
    }
    off = sp.apply_workspace_view_surface_profile(view, L4)
    assert _deep_probe_hits(off) == [], _deep_probe_hits(off)
    cats = _all_categories(off)
    assert "probe" not in cats, cats
    for c in cats:
        assert c in _VALID_CATEGORIES, ("invalid category enum", c, cats)


def test_latent_b_demote_partial_commit_no_reprobe(probe_off):
    """(b) a risky partial-commit move `_demote_partial_commit_candidate` re-stamps.
    With probe OFF it must NOT be re-stamped category:'probe' nor regain probe text."""
    view = {
        "schema_version": 1, "kind": "prover_workspace_view",
        "current_goal": {"lines": ["g"]},
        "candidate_moves": {"moves": [{
            "category": "commit", "tactic": "move=> h; auto.",
            "evidence": ["accepted; would leave 2 subgoals of residual surgery"],
        }]},
    }
    off = sp.apply_workspace_view_surface_profile(view, L4)
    assert _deep_probe_hits(off) == [], _deep_probe_hits(off)
    cats = _all_categories(off)
    assert "probe" not in cats, cats
    for c in cats:
        assert c in _VALID_CATEGORIES, ("invalid category enum", c, cats)
    # the move is still present and demoted to a commit-side category
    moves = off.get("candidate_moves", {}).get("moves", [])
    demoted = [m for m in moves if str(m.get("tactic", "")).startswith("move=>")]
    assert demoted, off
    assert demoted[0].get("category") == "commit"


def test_latent_b_demote_directly_yields_commit(probe_off):
    """`_demote_partial_commit_candidate` directly returns category 'commit' (off),
    'probe' (on) — and never corrupts the enum to a word-scrubbed value."""
    risky = {
        "category": "commit", "tactic": "split; auto.",
        "evidence": ["would leave 3 subgoals"],
    }
    assert sp._is_risky_partial_commit_candidate(risky) is True
    out = sp._demote_partial_commit_candidate(dict(risky))
    assert out["category"] == "commit"
    assert "probe" not in _json.dumps(out).lower()


def test_latent_b_demote_on_uses_probe_category(probe_on):
    risky = {"category": "commit", "tactic": "split; auto.",
             "evidence": ["would leave 3 subgoals"]}
    out = sp._demote_partial_commit_candidate(dict(risky))
    assert out["category"] == "probe"  # unchanged behaviour when probe is ON


def test_latent_c_application_context_how_to_use(probe_off):
    """(c) application_context.how_to_use naming probe_tactic."""
    view = {
        "schema_version": 1, "kind": "prover_workspace_view",
        "current_goal": {"lines": ["g"]},
        "application_context": {
            "how_to_use": "a checklist before using `probe_tactic` or `commit_tactic`.",
            "selected_handles": [{
                "tactic": "rewrite foo.",
                "why_relevant": "weak coverage. Probe this split point; extend it.",
                "verified": "read_only_probe_suggestion",
            }],
        },
    }
    off = sp.apply_workspace_view_surface_profile(view, L4)
    assert _deep_probe_hits(off) == [], _deep_probe_hits(off)
    for c in _all_categories(off):
        assert c in _VALID_CATEGORIES, c


def test_latent_d_last_result_checkpoint_after_rewind_next(probe_off):
    """(d) last_result.checkpoint_options[].after_rewind_next probe recipe (the
    live turn_052 leak class)."""
    view = {
        "schema_version": 1, "kind": "prover_workspace_view",
        "current_goal": {"lines": ["g"]},
        "last_result": {"intent": "undo_to_checkpoint", "checkpoint_options": [
            {"after_rewind_next": "Probe a smaller replacement step before recommitting."},
            {"after_rewind_next": "Inspect call_subgoals, then probe a revised call invariant."},
        ]},
    }
    off = sp.apply_workspace_view_surface_profile(view, L4)
    assert _deep_probe_hits(off) == [], _deep_probe_hits(off)


def test_filter_probe_surface_direct_returns_commit(probe_off):
    """A bare probe move with a concrete tactic is rewritten to a 'commit' candidate."""
    out = sp._filter_probe_surface(
        {"intent": "probe_tactic", "category": "probe", "tactic": "auto."},
        allow_probe=False,
    )
    assert out is not None
    assert out["category"] == "commit"
    assert "probe" not in _json.dumps(out).lower()
    # a probe move with NO concrete tactic is dropped entirely
    assert sp._filter_probe_surface(
        {"intent": "probe_tactic", "category": "probe"}, allow_probe=False
    ) is None


# === MANAGER-REQUEST FILTER (3) ===

def test_manager_request_probe_dropped(probe_off):
    """inspect_lookup_handles.ask_manager_for carrying a probe request -> dropped OFF."""
    view = {
        "schema_version": 1, "kind": "prover_workspace_view",
        "current_goal": {"lines": ["g"]},
        "inspect_lookup_handles": {"ask_manager_for": [
            {"intent": "probe_tactic", "payload": {"tactic": "auto."}},
            {"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "wp"}},
        ]},
    }
    off = sp.apply_workspace_view_surface_profile(view, L4)
    reqs = off.get("inspect_lookup_handles", {}).get("ask_manager_for", [])
    intents = [r.get("intent") for r in reqs]
    assert "probe_tactic" not in intents, intents
    assert "tactic_forms" in intents  # the allowed request survives as a direct topic intent
    assert "goal_info" not in intents
    assert _deep_probe_hits(off) == [], _deep_probe_hits(off)


def test_manager_request_why_mentioning_probe_scrubbed(probe_off):
    """A surviving (allowed-intent) request whose `why` mentions probe is scrubbed."""
    view = {
        "schema_version": 1, "kind": "prover_workspace_view",
        "current_goal": {"lines": ["g"]},
        "inspect_lookup_handles": {"ask_manager_for": [
            {"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "wp"},
             "why": "Use this to probe the goal shape before you commit."},
        ]},
    }
    off = sp.apply_workspace_view_surface_profile(view, L4)
    assert _deep_probe_hits(off) == [], _deep_probe_hits(off)


# === REAL CBC_upto L1 DATA: all turns OFF carry ZERO probe (incl. live turn_052) ===

_CBC = (
    "agent_view_runs/CBC_upto/2026-06-05_0958_CBC_upto__6f50851-dirty/"
    "views/Tree_0_0"
)


def _cbc_turns():
    import glob
    import pathlib
    root = pathlib.Path(__file__).resolve().parents[1] / _CBC
    return sorted(glob.glob(str(root / "turn_*.json")))


@pytest.mark.skipif(not _cbc_turns(), reason="CBC_upto run artifacts not present")
def test_cbc_upto_all_turns_off_have_zero_probe(probe_off):
    turns = _cbc_turns()
    assert len(turns) >= 100, len(turns)
    leaks = []
    for t in turns:
        raw = _json.load(open(t))
        off = sp.apply_workspace_view_surface_profile(raw, L4)
        h = _deep_probe_hits(off)
        if h:
            leaks.append((t, h))
    assert leaks == [], leaks


@pytest.mark.skipif(not _cbc_turns(), reason="CBC_upto run artifacts not present")
def test_cbc_upto_turn_052_live_leak_closed(probe_off):
    import os
    t = [p for p in _cbc_turns() if p.endswith("turn_052.json")]
    assert t, "turn_052 missing"
    raw = _json.load(open(t[0]))
    # the raw saved view DOES carry the probe leak (sanity: non-vacuous test)
    assert "probe" in _json.dumps(raw).lower()
    off = sp.apply_workspace_view_surface_profile(raw, L4)
    assert _deep_probe_hits(off) == [], _deep_probe_hits(off)


def test_off_drops_last_result_probe_preview_and_probe_alternatives(probe_off):
    """L4-bundle audit: these keys (only present after a probe action, so invisible to L1
    audits) leaked through the value-only scrub. They must be dropped wholesale when OFF."""
    import json
    view = {
        "schema_version": 1, "kind": "prover_workspace_view",
        "current_goal": {"lines": ["g"]},
        "last_result": {
            "result": "EasyCrypt accepted this candidate tactic. goal_after_probe shows the goal.",
            "kind": "accepted_closing_probe",
            "probe_preview": {"goal_after_probe": ["x = 1"], "tactic": "auto."},
        },
        "candidate_moves": {"moves": [{"category": "commit", "tactic": "auto."}],
                            "probe_alternatives": [
                                {"probe_result": "ok", "goal_after_probe_summary": "1 goal",
                                 "status": "probe_infrastructure_error"}]},
    }
    off = sp.apply_workspace_view_surface_profile(view, L4)
    blob = json.dumps(off).lower()
    assert "probe" not in blob, blob
    assert "probe_preview" not in json.dumps(off)
    assert "probe_alternatives" not in json.dumps(off)
    assert "goal_after_probe" not in json.dumps(off)


def test_off_keeps_named_call_strategy_move(probe_off):
    """A 'Named-call context' strategy move (tactic_shape, no concrete `tactic`) that merely
    trips _contains_probe_intent must be KEPT (scrubbed), not dropped — it carries orientation."""
    view = {
        "schema_version": 1, "kind": "prover_workspace_view",
        "current_goal": {"lines": ["g"]},
        "candidate_moves": {"moves": [{
            "title": "Named-call context", "category": "strategy",
            "tactic_shape": "call UFCMA_genCC.", "symbol_hint": "UFCMA_genCC",
            "runnable_status": "Not established as runnable; probe before relying on it.",
        }]},
    }
    off = sp.apply_workspace_view_surface_profile(view, L4)
    moves = off.get("candidate_moves", {}).get("moves", [])
    kept = [m for m in moves if m.get("symbol_hint") == "UFCMA_genCC"]
    assert kept, ("named-call move dropped", off)
    assert kept[0].get("tactic_shape") == "call UFCMA_genCC."
    assert "probe" not in __import__("json").dumps(off).lower()


def test_off_keeps_commit_move_label_scrubbing_only_probe_words(probe_off):
    """A category:commit move that only MENTIONS probe in guarantee keeps its title (cpa_ddh0)."""
    view = {
        "schema_version": 1, "kind": "prover_workspace_view",
        "current_goal": {"lines": ["g"]},
        "candidate_moves": {"moves": [{
            "title": "Invariant-call route", "category": "commit",
            "tactic": "call (_: ={glob A} ==> ={res, glob A}).",
            "evidence": ["Daemon accepted this canonical-invariant call"],
            "guarantee": "not verified on the current goal; probe before committing.",
        }]},
    }
    off = sp.apply_workspace_view_surface_profile(view, L4)
    moves = off.get("candidate_moves", {}).get("moves", [])
    inv = [m for m in moves if m.get("title") == "Invariant-call route"]
    assert inv, ("commit move was genericized/dropped", [m.get("title") for m in moves])
    assert inv[0].get("tactic") == "call (_: ={glob A} ==> ={res, glob A})."
    assert "probe" not in __import__("json").dumps(off).lower()


# === RECOVERY / REMINDER / EXAMPLE TEXT (the schnorr 1713 bundle leak) ========
#
# The view/schema/gate strip probe when OFF, but the "could not read a proof
# intent" recovery message (and the give-up deflection nudge) still advertised a
# `probe_tactic` example — so the agent reached for a probe that the gate then
# bounced ("Probe is disabled for this run"), wasting a turn. The example/reminder
# text must be switch-aware too: no probe example when OFF, but still a COMMIT
# affordance so the agent knows it can act.

def test_repair_prompt_off_hides_probe_keeps_commit(probe_off):
    """The protocol-repair example must not advertise probe when OFF, but must
    still offer a commit affordance (the agent must still be told it can act)."""
    from workflow.proof_management.protocol_repair import (
        parse_agent_intent,
        repair_prompt_text,
    )
    # the standalone helper
    text = repair_prompt_text()
    assert "probe_tactic" not in text
    assert "commit_tactic" in text
    # and the parse result that the manager actually emits on an unreadable intent
    parsed = parse_agent_intent("this is not a proof intent")
    assert parsed.ok is False
    assert "probe_tactic" not in parsed.repair_prompt
    assert "commit_tactic" in parsed.repair_prompt


def test_repair_prompt_on_still_advertises_probe(probe_on):
    """Probe explicitly ON: the legacy probe example is shown."""
    from workflow.proof_management.protocol_repair import (
        parse_agent_intent,
        repair_prompt_text,
    )
    text = repair_prompt_text()
    assert "probe_tactic" in text
    parsed = parse_agent_intent("not a proof intent")
    assert parsed.ok is False
    assert "probe_tactic" in parsed.repair_prompt


def _give_up_deflection_prompt():
    """Drive the REAL manager give-up deflection path (`_give_up_gate`) and return
    the deflection `repair_prompt` it produces.

    `_give_up_gate` only reads `latest_view` (proof still open), the give-up window
    counters, and `_audit`; we build the minimal manager state by hand (via
    `__new__`, no EC session) so the test exercises production code, not a re-impl.
    A re-implementation in the test body would pass even if the production gate were
    reverted — this calls the gate itself, so reverting the gate flips the result.
    """
    from workflow.proof_node_manager import ProofNodeManager
    from workflow.proof_management.protocol_repair import AgentIntent

    class _Lifecycle:
        latest_snapshot = None
        latest_view = {"proof_status": {"status": "open", "remaining_goals": 2}}

    mgr = ProofNodeManager.__new__(ProofNodeManager)
    mgr.node_id = "n0"
    mgr._finish_with_admit_count = 0
    mgr._give_up_times = []
    mgr.lifecycle = _Lifecycle()
    mgr._audit = lambda rec: None

    turn = mgr._give_up_gate(AgentIntent(intent="finish", payload={}))
    assert turn is not None, "give-up gate should deflect on an open proof"
    return turn.repair_prompt


def test_give_up_deflection_text_off_hides_probe(probe_off):
    """The REAL manager give-up deflection nudge must not suggest `probe_tactic`
    when OFF, but must still point at the other still-available levers.

    Asserts on the actual `_give_up_gate` output: reverting the production gate (so
    the probe suggestion is always appended) makes this fail."""
    prompt = _give_up_deflection_prompt()
    assert "probe_tactic" not in prompt
    assert "`tactic_forms`" in prompt
    assert "`lookup_symbol`" in prompt


def test_give_up_deflection_text_on_keeps_probe(probe_on):
    """Probe explicitly ON: the REAL give-up deflection still advertises `probe_tactic`."""
    prompt = _give_up_deflection_prompt()
    assert "probe_tactic" in prompt
    assert "`tactic_forms`" in prompt
    assert "`lookup_symbol`" in prompt


# === TURN-0 LONG-LIVED PROMPT (the proof_node_runtime gates) ==================
#
# The long-lived bootstrap prompt is built once on turn 0 and still advertised
# `probe_tactic` to a probe-OFF agent in four spots (_INTERPRET_SIGNALS,
# _keep_going_actions_for_profile, _profile_safe_protocol, _adaptive_mode_section).
# Render the real prompt and assert no probe-lever mention survives when OFF, and
# that it reappears when ON (so an empty render can't pass the OFF test vacuously).

def _render_prompt(surface_profile: str) -> str:
    import tempfile
    from pathlib import Path
    from workflow.agent_prompt_render import render_long_lived_agent_prompt

    bootstrap = (
        "## What the Compiler Gives You\n"
        "Ask for its help with `inspect_context`: foo.\n"
        "- `call_invariant_skeleton` — live call invariant frames.\n"
        "Prove this lemma. If the first probe shows nothing, keep going.\n"
    )
    with tempfile.TemporaryDirectory() as d:
        return render_long_lived_agent_prompt(
            bootstrap,
            host="h", port=1, token="t",
            node_memory_dir=Path(d),
            max_turns=10,
            surface_profile=surface_profile,
        )


@pytest.mark.parametrize("profile", [L4, "adaptive"])
def test_long_lived_prompt_off_hides_probe_lever(probe_off, profile):
    """Probe OFF: the turn-0 prompt advertises no `probe_tactic` lever, and the
    adaptive escalation copy names no bare `probe` lever — while commit/inspect/
    lookup affordances stay."""
    text = _render_prompt(profile)
    assert PROBE not in text, (
        "probe_tactic leaked into the long-lived prompt with probe OFF"
    )
    assert "probe" not in text.lower()
    # bare `probe`/`inspect`/`lookup` unlock copy (adaptive) must not name probe
    assert "`probe`/`inspect`/`lookup`" not in text
    # keep-going "candidate" action must not say "probe a candidate" when off
    # (catches a revert of the _keep_going_actions_for_profile gate)
    assert "probe a candidate" not in text
    # commit/inspect/lookup levers are untouched
    assert "commit_tactic" in text


@pytest.mark.parametrize("profile", [L4, "adaptive"])
def test_long_lived_prompt_on_keeps_probe_lever(probe_on, profile):
    """Probe explicitly ON: the turn-0 prompt still advertises the `probe_tactic` lever
    (so the OFF assertion above is not vacuously satisfied by an empty render)."""
    text = _render_prompt(profile)
    assert PROBE in text
