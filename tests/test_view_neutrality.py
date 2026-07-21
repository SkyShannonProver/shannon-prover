"""P2 — view-neutrality flag: heuristic content never gates a commit.

These lock the boundary invariant from docs/design/compiler_view_boundary.md §9:
under `view_neutrality_strict`, a daemon-accepted commit is NEVER converted to a
repair menu, and the accepted-probe view is never poisoned. With the flag OFF the
historic behavior (the probability-budget veto that stalled pr_G4) is preserved,
so the change is behavior-neutral until flipped.
"""
from __future__ import annotations

import pytest

from workflow.view_neutrality import view_neutrality_strict
from workflow.surface_profiles import (
    _HEURISTIC_INSPECT_TOPICS,
    _HEURISTIC_KEYS,
    apply_workspace_view_surface_profile,
    effective_inspect_topics,
    enforce_view_neutrality,
    resolve_surface_profile,
    surface_profile_allows_intent,
)
from workflow.surface_composer import compose_surface_model

_ENV = "SHANNON_VIEW_NEUTRALITY_STRICT"
_RISK = {
    "signal": "probability_budget_route_risk",
    "anti_route": "a single rnd may charge the whole product budget.",
}


def _risky_commit_view() -> dict:
    return {
        "proof_status": {"status": "open"},
        "current_goal": {"lines": ["Pr[G() @ &m : x] <= (q / order) ^ 3"]},
        "candidate_moves": {"route_health": [dict(_RISK)]},
    }


# --- the flag itself ---------------------------------------------------------

def test_flag_defaults_off(monkeypatch) -> None:
    monkeypatch.delenv(_ENV, raising=False)
    assert view_neutrality_strict() is False


@pytest.mark.parametrize(
    "val,expected",
    [("1", True), ("true", True), ("on", True), ("YES", True),
     ("0", False), ("", False), ("no", False)],
)
def test_flag_parsing(monkeypatch, val, expected) -> None:
    monkeypatch.setenv(_ENV, val)
    assert view_neutrality_strict() is expected


# --- §9 neutrality strip (the chokepoint filter) -----------------------------

def _all_keys(value) -> set:
    keys: set = set()
    if isinstance(value, dict):
        for k, v in value.items():
            keys.add(k)
            keys |= _all_keys(v)
    elif isinstance(value, list):
        for v in value:
            keys |= _all_keys(v)
    return keys


def test_enforce_view_neutrality_strips_heuristic_keeps_facts() -> None:
    view = {
        "current_goal": {"lines": ["g"]},                       # fact: keep
        "candidate_moves": {
            "navigation": [{"route": "x", "confidence": "medium"}],  # heuristic: drop
            "structural_transitions": [{"tactic": "sp."}],          # keep
        },
        "facts_and_diagnostics": {
            "probability_budget": {"unsafe_lowerings": ["..."]},     # heuristic: drop
            "facts": {"pr_obligation_primary_strategy": "x",         # heuristic: drop
                      "name_resolution": {"resolved": True}},        # fact: keep
        },
        "call_focus": {
            "invariant_must_carry": ["`={glob A}`"],                 # fact: keep
            "preview_effects": "inline* -> 47 goals",               # fact: keep
            "why_relevant": "looks relevant",                        # heuristic: drop
        },
        "yours": "your call",                                        # guardrail: keep
    }
    out = enforce_view_neutrality(view)
    present = _all_keys(out)
    assert present.isdisjoint(_HEURISTIC_KEYS)
    # facts / verified / guardrails survive
    assert out["current_goal"]["lines"] == ["g"]
    assert out["candidate_moves"]["structural_transitions"] == [{"tactic": "sp."}]
    assert out["facts_and_diagnostics"]["facts"]["name_resolution"] == {"resolved": True}
    assert out["call_focus"]["invariant_must_carry"] == ["`={glob A}`"]
    assert out["call_focus"]["preview_effects"] == "inline* -> 47 goals"
    assert out["yours"] == "your call"


def _heavy_l4_view() -> dict:
    return {
        "schema_version": 1, "kind": "prover_workspace_view",
        "proof_status": {"status": "open", "remaining_goals": 4,
                         "current_layer": "procedure_body", "view_focus": "seq_cut"},
        "last_result": {"intent": "commit_tactic", "tactic": "sp.", "result": "accepted"},
        "current_goal": {"goal_type": "pRHL", "lines": ["g" * 200]},
        "program_frontier": {"frontier_alignment": {"rows": []}},
        "candidate_moves": {
            "navigation": [{"id": "prhl_surgery_route", "route": "case_split_then_rcond",
                            "confidence": "medium", "why_now": "branch signals present",
                            "anti_routes": [{"route": "blind_conseq"}]}],
            "route_health": [{"signal": "probability_budget_route_risk",
                              "anti_route": "do not seq here"}],
        },
        "facts_and_diagnostics": {
            "probability_budget": {"budget_ledger": {"unsafe_lowerings": ["..."]}},
            "facts": {"pr_obligation_primary_strategy": "run_native_pr_search",
                      "name_resolution": {"resolved": True}},
        },
        "recovery_diagnosis_surface": {"recovery_class": "wrong_first_instruction",
                                       "evidence": ["a side still has code"]},
        "pure_tail_surface": {"p": 1},
        "inspect_lookup_handles": {"h": 1},
    }


def test_l4_view_has_no_heuristic_keys_under_neutrality(monkeypatch) -> None:
    # §9 lint: the assembled L4 agent view carries NO heuristic key when strict.
    monkeypatch.setenv(_ENV, "1")
    out = apply_workspace_view_surface_profile(_heavy_l4_view(), "l4_checked_action_surface")
    leaked = _all_keys(out) & _HEURISTIC_KEYS
    assert not leaked, f"heuristic keys leaked into the neutral L4 view: {leaked}"
    assert "current_goal" in out  # facts survive


def test_l4_view_carries_heuristic_keys_when_not_strict() -> None:
    # non-vacuity: with the flag OFF the same L4 view DOES carry heuristic keys
    # (so the strip above is doing real work, not asserting on an empty view).
    out = apply_workspace_view_surface_profile(_heavy_l4_view(), "l4_checked_action_surface")
    assert _all_keys(out) & _HEURISTIC_KEYS


# --- P4: other agent-facing surfaces (inspect topics, prompt guidance) -------

def test_effective_inspect_topics_drops_heuristic_under_strict(monkeypatch) -> None:
    profile = resolve_surface_profile("l4_checked_action_surface")
    monkeypatch.delenv(_ENV, raising=False)
    off = effective_inspect_topics(profile)
    monkeypatch.setenv(_ENV, "1")
    on = effective_inspect_topics(profile)
    # the budget ledger (and the rest of the heuristic set) is removed under strict
    assert "probability_budget_ledger" in off and "probability_budget_ledger" not in on
    assert "lemma_hints" in off and "lemma_hints" not in on
    # factual / daemon-verified topics survive
    assert {"align", "call_subgoals", "pr_bridge_routes"} <= on
    assert "goal_info" not in on
    assert on == off - _HEURISTIC_INSPECT_TOPICS


def test_inspect_gate_blocks_heuristic_topic_under_strict(monkeypatch) -> None:
    monkeypatch.setenv(_ENV, "1")
    blocked, _ = surface_profile_allows_intent(
        "l4_checked_action_surface", "inspect_context",
        {"topic": "probability_budget_ledger"})
    assert blocked is False
    allowed, _ = surface_profile_allows_intent(
        "l4_checked_action_surface", "inspect_context", {"topic": "goal_info"})
    assert allowed is False


def test_inspect_gate_allows_heuristic_topic_when_not_strict(monkeypatch) -> None:
    monkeypatch.delenv(_ENV, raising=False)
    allowed, _ = surface_profile_allows_intent(
        "l4_checked_action_surface", "inspect_context",
        {"topic": "probability_budget_ledger"})
    assert allowed is True


def test_long_lived_prompt_does_not_duplicate_route_health_contract(tmp_path) -> None:
    from workflow.agent_prompt_render import render_long_lived_agent_prompt

    prompt = render_long_lived_agent_prompt(
        "ORIGINAL PROMPT",
        host="127.0.0.1",
        port=12345,
        token="tok",
        node_memory_dir=tmp_path,
        max_turns=7,
        surface_profile="l4_checked_action_surface",
    )
    assert "route_health" not in prompt
    assert "candidate_moves" not in prompt


# --- call-frontier focus panel: no generic family menu pushed (2026-06-26) -----
def test_call_focus_panel_drops_generic_family_menu_and_cross_prescription() -> None:
    # panel-audit 2026-06-26: the generic `options` family menu (call/inline*/swap/eager)
    # and the `yours` meta were DELETED (鸡肋 — a tactic-family checklist any prover knows;
    # 误导 when it pushed `call`/`inline*` at a one-sided/reorder frontier). With NO menu
    # at all, the panel cannot push a "cross the call" / "set up the call invariant"
    # move-verdict; the family choice stays the agent's. (The original FCBC-eager fix —
    # listing the reorder family so the agent was not steered to cross — is subsumed: no
    # family is steered toward now.)
    model = compose_surface_model(
        {
            "proof_status": {"current_layer": "call_site"},
            "program_frontier": {"focus": {"frontier_call_sites": 1}},
        },
        "l4_checked_action_surface",
    ).to_dict()
    primary = model.get("primary_panel") or {}
    focus = {item["key"]: item.get("value") for item in primary.get("facts", [])}
    assert "options" not in focus and "yours" not in focus
    blob = str(focus)
    assert "cross the call" not in blob
    assert "set up the call invariant" not in blob
