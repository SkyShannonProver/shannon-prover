"""Unit tests for the read-only panel-policy predicates.

These cover the predicates the philosophy audit relies on:
``framing_size``, ``imperative_findings`` and ``provenance_flags``. They are
pure / read-only — none of them mutate the view.
"""
from __future__ import annotations

import copy

from core.easycrypt.panel_policy import (
    SIZE_TARGET,
    attach_provenance,
    enforce,
    framing_size,
    imperative_findings,
    panel_order_for,
    provenance_flags,
    strip_machine_metadata,
)


# ── framing_size ─────────────────────────────────────────────────────────────

def test_framing_size_counts_only_framing_panels():
    # truth layers (current_goal) are exempt; only framing panels are summed.
    view = {
        "current_goal": {"lines": ["x" * 10000]},  # exempt, must not count
        "candidate_moves": {"moves": []},
    }
    size = framing_size(view)
    # the only framing panel is a tiny candidate_moves -> well under target.
    assert size < SIZE_TARGET
    # the huge goal did not leak into the framing size.
    assert size < 200


def test_framing_size_over_budget_panel_exceeds_target():
    bloated = {
        "candidate_moves": {
            "moves": [{"tactic": "rewrite x.", "blurb": "z" * (SIZE_TARGET + 1000)}]
        }
    }
    assert framing_size(bloated) > SIZE_TARGET


def test_framing_size_does_not_mutate_view():
    view = {"candidate_moves": {"moves": [{"tactic": "rewrite x."}]}}
    before = copy.deepcopy(view)
    framing_size(view)
    assert view == before


# ── imperative_findings ──────────────────────────────────────────────────────

def test_imperative_findings_flags_you_must_wording():
    view = {"application_context": {"note": "you must do X before Y"}}
    found = imperative_findings(view)
    assert found, "expected the imperative 'you must' wording to be flagged"
    paths = [jp for jp, _ in found]
    assert ".application_context.note" in paths


def test_imperative_findings_flags_ordering_wording():
    view = {"candidate_moves": {"hint": "do this first, then close the goal"}}
    found = imperative_findings(view)
    assert found
    # the matched string is returned alongside the path.
    assert any("do this first" in s for _, s in found)


def test_imperative_findings_clean_view_has_none():
    view = {
        "current_goal": {"lines": ["pr[A] = pr[B]"]},
        "candidate_moves": {"moves": [{"tactic": "byequiv."}]},
    }
    assert imperative_findings(view) == []


# ── provenance_flags ─────────────────────────────────────────────────────────

def test_provenance_flags_missing_markers_on_option_tactic():
    view = {"candidate_moves": {"moves": [{"tactic": "rewrite foo."}]}}
    flags = provenance_flags(view)
    assert flags, "a committable tactic without markers should be flagged"
    jpath, missing = flags[0]
    assert jpath == ".candidate_moves.moves[0]"
    assert set(missing) == {"derivation", "verified", "guarantee"}


def test_provenance_flags_complete_markers_not_flagged():
    view = {
        "candidate_moves": {
            "moves": [{
                "tactic": "rewrite foo.",
                "derivation": "from current-state analysis",
                "verified": "unverified_suggestion",
                "guarantee": "probe before committing; reversible",
            }]
        }
    }
    assert provenance_flags(view) == []


def test_provenance_flags_ignores_non_option_paths():
    # a tactic sitting under last_result (an echo, not an offered option) must
    # not be treated as a committable option needing provenance.
    view = {"last_result": {"tactic": "rewrite foo."}}
    assert provenance_flags(view) == []


# ── enforce: HARD framing strip ──────────────────────────────────────────────

def test_enforce_strips_standing_route_and_risk_framing():
    view = {
        "application_context": {
            "proof_story": {"active_route_objective": "G0 -> G1"},
            "panel_keep": "ok",
        },
        "risk_map": {"premature_wp": "risky"},
        "current_goal": {"lines": ["pr[A] = pr[B]"]},
    }
    report = enforce(view)
    assert "proof_story" not in view["application_context"]
    assert "risk_map" not in view
    assert view["application_context"]["panel_keep"] == "ok"   # non-framing kept
    assert view["current_goal"]["lines"]                       # truth untouched
    assert "application_context.proof_story" in report["stripped"]
    assert "risk_map" in report["stripped"]


# ── enforce: imperative wording is actually DELETED, not just reported ────────

def test_enforce_deletes_imperative_leaf_in_framing_panel():
    view = {"application_context":
            {"note": "you must resolve the bridge before opening the goal"}}
    report = enforce(view)
    # the imperative field is GONE (the bug was: reported but not deleted)
    assert "note" not in view.get("application_context", {})
    assert ".application_context.note" in report["imperative_stripped"]
    # and no imperative wording survives the gate
    assert imperative_findings(view) == []


def test_enforce_never_deletes_a_protected_tactic_field():
    # an imperative-looking string sitting in a protected `tactic` field must be
    # left in place (deleting a move would corrupt the view), not silently lost.
    view = {"candidate_moves": {"moves": [
        {"tactic": "you must rewrite foo.",
         "derivation": "d", "verified": "unverified_suggestion", "guarantee": "g"}]}}
    enforce(view)
    assert view["candidate_moves"]["moves"][0]["tactic"] == "you must rewrite foo."


# ── attach_provenance: honest markers, no fabricated "verified" ───────────────

def test_attach_provenance_stamps_unverified_on_bare_tactic():
    view = {"candidate_moves": {"moves": [{"tactic": "rewrite foo."}]}}
    n = attach_provenance(view)
    move = view["candidate_moves"]["moves"][0]
    assert n == 1
    assert move["verified"] == "unverified_suggestion"
    assert move["derivation"] and move["guarantee"]


def test_attach_provenance_does_not_fabricate_verified_from_title():
    # title/category are free-text display fields; a tactic merely *titled*
    # with the word "daemon" must NOT be stamped daemon-accepted.
    view = {"candidate_moves": {"moves": [
        {"tactic": "wp.", "title": "avoid daemon timeout", "category": "commit"}]}}
    attach_provenance(view)
    assert view["candidate_moves"]["moves"][0]["verified"] == "unverified_suggestion"


def test_attach_provenance_honors_producer_supplied_verified_marker():
    # a producer that supplies a real `verified` marker (or daemon source) is
    # classified as daemon-accepted.
    view = {"candidate_moves": {"moves": [
        {"tactic": "byequiv => //.", "source": "ProofIR daemon-probed bridge"}]}}
    attach_provenance(view)
    assert view["candidate_moves"]["moves"][0]["verified"] == \
        "daemon_accepted_on_current_goal"


# ── goal-dynamic panel ordering ──────────────────────────────────────────────

def _cluster_view(layer):
    return {
        "last_result": {}, "proof_status": {"current_layer": layer},
        "current_goal": {}, "program_frontier": {}, "call_site_surface": {},
        "seq_cut_surface": {}, "candidate_moves": {}, "application_context": {},
        "facts_and_diagnostics": {}, "inspect_lookup_handles": {},
        "structural_checkpoints": {}, "surface_profile": {},
    }


def test_panel_order_stable_header_footer_and_drops_config():
    order = panel_order_for(_cluster_view("call_site"))
    assert order[:3] == ["last_result", "current_goal", "proof_status"]  # stable header
    assert order[3] == "candidate_moves"                  # options lead the cluster
    assert order[-1] == "structural_checkpoints"          # undo demoted to footer
    assert "inspect_lookup_handles" in order[-3:]         # menu near the bottom
    assert "surface_profile" not in order                 # machine config hidden


def test_panel_order_is_goal_dynamic_call_vs_seq():
    call = panel_order_for(_cluster_view("call_site"))
    # at a call goal, the call surface leads the structural surfaces
    assert call.index("call_site_surface") < call.index("program_frontier")
    assert call.index("call_site_surface") < call.index("seq_cut_surface")
    seq = panel_order_for(_cluster_view("seq_cut"))
    # at a seq goal, the seq surface leads instead
    assert seq.index("seq_cut_surface") < seq.index("call_site_surface")
    assert seq.index("seq_cut_surface") < seq.index("program_frontier")


def test_panel_order_pins_metadata_last_and_keeps_unlisted():
    view = {"proof_status": {}, "current_goal": {}, "candidate_moves": {},
            "some_future_panel": {}, "view_hash": "x", "schema_version": 2}
    order = panel_order_for(view, pin_last=("view_hash", "schema_version"))
    assert order[-2:] == ["view_hash", "schema_version"]  # metadata pinned last
    assert "some_future_panel" in order                   # unlisted panel preserved


def test_strip_machine_metadata_removes_counts_keeps_status_flags():
    node = {
        "current_goal": {"lines": ["x"], "line_count": 5, "char_count": 99,
                         "shown_lines": 5, "shown_chars": 99,
                         "text_fully_shown": True, "truncated": False,
                         "goal_type": "pRHL"},
        "preview": {"truncated": True, "char_count": 3},
    }
    strip_machine_metadata(node)
    # the four size counts are gone; status flags (truncated/text_fully_shown) stay
    assert node["current_goal"] == {"lines": ["x"], "text_fully_shown": True,
                                    "truncated": False, "goal_type": "pRHL"}
    assert node["preview"] == {"truncated": True}
