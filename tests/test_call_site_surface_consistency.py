"""call_site_surface: no self-contradiction, no dangled-landmark noise.

Found in the WB_ON run (turn_008/9/10): a `source_lookup_landmark` handle
(`UFCMA_genCC`) was surfaced with `callable_now:false` AND
`frontier_status:"callable_now"` (self-contradiction) plus a "tactic shape is
hidden" note (dangled noise) — the agent could not act on it.
"""
from __future__ import annotations

import sys
from pathlib import Path

import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from core.easycrypt.analysis import ec_proof_ir as IR  # noqa: E402
from core.easycrypt import session_prover_workspace_view as V  # noqa: E402
from workflow.surface_action_preflight import action_preflight_key  # noqa: E402


def _with_call_preflight(view: dict) -> dict:
    out = dict(view)
    out["surface_action_preflight"] = {
        "schema_version": 1,
        "results": [{
            "intent": "call_site_options",
            "payload": {},
            "key": action_preflight_key("call_site_options", {}),
            "eligible": True,
            "reason": "preflight found a runnable call-site option",
        }],
    }
    return out


def test_frontier_status_never_contradicts_callable_now() -> None:
    handles = {"callable_lemmas": [
        {"lemma": "UFCMA_genCC", "call_candidate_kind": "source_lookup_landmark",
         "callable_now": True, "frontier_status": "callable_now"},
        {"lemma": "direct", "call_candidate_kind": "direct_current_call",
         "callable_now": True, "frontier_status": "callable_now"},
    ]}
    items = {h["symbol"]: h for h in IR._call_route_named_handles(handles)}
    land = items["UFCMA_genCC"]
    # not a direct call -> callable_now False, and frontier_status must NOT claim
    # "callable_now" (the contradiction)
    assert land["callable_now"] is False
    assert land["frontier_status"] != "callable_now"
    # a genuine direct call stays consistent
    assert items["direct"]["callable_now"] is True
    assert items["direct"]["frontier_status"] == "callable_now"


def test_dangled_landmark_handles_are_dropped() -> None:
    ctx = {"handles": {"call_site_route": {"named_handles": [
        {"symbol": "UFCMA_genCC", "callable_now": False,
         "requires_cut_to_frontier": False, "call_candidate_kind": "source_lookup_landmark"},
        {"symbol": "good", "callable_now": True, "call_candidate_kind": "direct_current_call"},
        {"symbol": "cuttable", "callable_now": False,
         "requires_cut_to_frontier": True, "call_candidate_kind": "frontier_after_cut"},
    ]}}}
    out = V._workspace_call_site_surface(ctx)
    syms = [h["symbol"] for h in out.get("named_handles", [])]
    assert "UFCMA_genCC" not in syms          # dangled landmark: dropped
    assert {"good", "cuttable"} <= set(syms)  # callable / cut-able: kept


def test_symbol_hint_rejects_placeholder_words() -> None:
    # Origin guard: a *template* call shape carries a bare placeholder/kind word
    # (`call lemma.`) — it must NOT be extracted as a real symbol, otherwise it
    # leaks downstream into a phantom `lemma` named handle.
    assert V._symbol_hint_from_call_shape("call lemma.") == ""
    assert V._symbol_hint_from_call_shape("call equiv.") == ""
    assert V._symbol_hint_from_call_shape("call (_: Inv)") == ""
    # genuine names still resolve (incl. lowercase + qualified)
    assert V._symbol_hint_from_call_shape("ecall (equ_cc n{2} m).") == "equ_cc"
    assert V._symbol_hint_from_call_shape("call UFCMA_genCC.") == "UFCMA_genCC"
    assert V._symbol_hint_from_call_shape("call A.B.lem.") == "A.B.lem"


def test_placeholder_lemma_handle_is_dropped() -> None:
    # Chokepoint guard: a callable_lemma whose `lemma` name is the kind word
    # "lemma" (leaked from a template shape) must never be minted as a named
    # handle — that was the phantom `lemma` candidate seen in the call-frontier
    # panel (step3 L4 turn_024/048).
    handles = {"callable_lemmas": [
        {"lemma": "lemma", "source": "candidate_moves.moves",
         "call_candidate_kind": "direct_current_call", "callable_now": True},
        {"lemma": "equ_cc", "call_candidate_kind": "direct_current_call",
         "callable_now": True},
    ]}
    syms = [h["symbol"] for h in IR._call_route_named_handles(handles)]
    assert "lemma" not in syms     # phantom kind-word handle: dropped
    assert "equ_cc" in syms        # genuine lemma: kept


def test_named_call_subject_absent_at_frontier_is_a_neutral_fact() -> None:
    # The eager-oracle trap (a held-out MAC corpus eager-while lemma): a named
    # equiv `h` is about procedure `HH(H).order_f`, but the frontier's live
    # calls are `H.f` (order_f
    # was inlined). The compiler already has both ingredients (handle.procedures,
    # live_call_sites[].procedure) but never compared them. This blocker surfaces
    # the FACT — subject vs frontier procedures — not a recommendation.
    blockers = IR._call_route_frontier_blockers(
        program_ir={"frontier": {}},
        named_handles=[{
            "symbol": "h", "procedure": "HH(H).order_f",
            "procedures": ["HH(H).order_f", "HH(H).order_f"],
            "frontier_live": False, "callable_now": False,
        }],
        live_call_sites=[{"side": "left", "procedure": "H.f"},
                         {"side": "right", "procedure": "H.f"}],
    )
    mism = [b for b in blockers if b.get("kind") == "named_call_subject_absent_at_frontier"]
    assert len(mism) == 1, blockers
    b = mism[0]
    assert b["symbol"] == "h"
    assert b["subject_procedures"] == ["HH(H).order_f"]
    assert b["frontier_live_procedures"] == ["H.f"]
    # resource-only: the blocker carries facts, never a prescription
    for prescriptive in ("recommendation", "advice", "suggested_tactic", "action",
                         "reformulate", "rewind", "should", "next_step"):
        assert prescriptive not in b


def test_subject_present_or_frontier_live_emits_no_mismatch() -> None:
    # (a) lemma subject IS among the frontier's live calls -> in scope, no fact
    in_scope = IR._call_route_frontier_blockers(
        program_ir={"frontier": {}},
        named_handles=[{"symbol": "h", "procedures": ["H.f"],
                        "frontier_live": False, "callable_now": False}],
        live_call_sites=[{"procedure": "H.f"}],
    )
    assert not any(b.get("kind") == "named_call_subject_absent_at_frontier" for b in in_scope)
    # (b) a handle that is live/callable at the frontier never gets a scope fact
    live = IR._call_route_frontier_blockers(
        program_ir={"frontier": {}},
        named_handles=[{"symbol": "h", "procedures": ["order_f"],
                        "frontier_live": True, "callable_now": False}],
        live_call_sites=[{"procedure": "H.f"}],
    )
    assert not any(b.get("kind") == "named_call_subject_absent_at_frontier" for b in live)
    # (c) no live call sites -> nothing to compare against, no fact
    no_sites = IR._call_route_frontier_blockers(
        program_ir={"frontier": {}},
        named_handles=[{"symbol": "h", "procedures": ["order_f"],
                        "frontier_live": False, "callable_now": False}],
        live_call_sites=[],
    )
    assert not any(b.get("kind") == "named_call_subject_absent_at_frontier" for b in no_sites)


def test_scope_fact_renders_as_neutral_text_not_guidance() -> None:
    # The rendered call-focus panel states the scope fact and gives NO instruction
    # (no "reformulate"/"rewind"/"inline"/"use" wording).
    from workflow.surface_composer import compose_surface_model
    view = {"call_site_surface": {
        "state": "tail_blocked_named_call",
        "named_handles": [{"symbol": "h"}],
        "frontier_blockers": [{
            "kind": "named_call_subject_absent_at_frontier", "symbol": "h",
            "subject_procedures": ["HH(H).order_f"],
            "frontier_live_procedures": ["H.f"],
        }],
    }}
    view["proof_status"] = {"current_layer": "call_site"}
    view["program_frontier"] = {"focus": {"frontier_call_sites": 1}}
    model = compose_surface_model(
        _with_call_preflight(view),
        "l4_checked_action_surface",
    ).to_dict()
    focus = {item["key"]: item.get("value") for item in model["primary_panel"].get("facts", [])}
    scope = focus.get("frontier_scope") or []
    assert scope and "HH(H).order_f" in scope[0] and "H.f" in scope[0]
    text = " ".join(scope).lower()
    for verb in ("reformulate", "rewind", "you should", "inline", "instead", "use "):
        assert verb not in text, f"guidance leaked: {verb!r}"


if __name__ == "__main__":
    test_frontier_status_never_contradicts_callable_now()
    test_dangled_landmark_handles_are_dropped()
    test_symbol_hint_rejects_placeholder_words()
    test_placeholder_lemma_handle_is_dropped()
    test_named_call_subject_absent_at_frontier_is_a_neutral_fact()
    test_subject_present_or_frontier_live_emits_no_mismatch()
    test_scope_fact_renders_as_neutral_text_not_guidance()
    print("PASS test_call_site_surface_consistency")
