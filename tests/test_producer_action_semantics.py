"""Producer-level checks for prover action semantics."""
from __future__ import annotations

from pathlib import Path


import sys
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from core.easycrypt.commands.commit_commands import (  # noqa: E402
    _parse_try_report,
    _try_recommendations,
)
from core.easycrypt.commands.inspect_commands import (  # noqa: E402
    _diagnose_epistemic_evidence,
    _diagnose_recommendation,
    _goal_info_epistemic_evidence,
)
from core.easycrypt.commands.speculative_commands import (  # noqa: E402
    _inv_from_lemma_epistemic_evidence,
    _inv_from_lemma_recommendations,
    _recommendations_from_tactic_lines,
    _suggest_close_epistemic_evidence,
)
from core.easycrypt.session_hook_phases import AutoDiffPhase  # noqa: E402
from core.easycrypt.search.handlers import (  # noqa: E402
    _bridge_lemma_recommendations,
    _bridge_lemmas_epistemic_evidence,
    _lemma_hint_recommendations,
    _lemma_hints_epistemic_evidence,
)


def test_suggest_close_marks_concrete_tactics_as_candidates_and_templates_as_strategy() -> None:
    text = """
Suggested tactics:
  1. byphoare => //.   (* single-game probability bound *)
  2. bypr ... .
"""
    recs = _recommendations_from_tactic_lines(
        "suggest_close",
        "closing_tactic",
        text,
        producer="suggest-close",
        why="static suggestion",
        action_type="tactic_candidate",
        metadata={
            "epistemic_status": "static_candidate_uncertified_by_ec",
        },
    )

    assert recs[0]["action"] == "byphoare => //."
    assert recs[0]["action_type"] == "tactic_candidate"
    assert recs[1]["action"] == "bypr ... ."
    assert recs[1]["action_type"] == "strategy_hint"
    assert recs[1]["metadata"]["requires_instantiation"] is True
    evidence = _suggest_close_epistemic_evidence(text)
    assert evidence[0]["status"] == "static_candidate_uncertified_by_ec"


def test_bridge_lemmas_marks_templates_as_strategy_and_concrete_as_candidates() -> None:
    recs = _bridge_lemma_recommendations(
        "  transitivity M ...\n"
        "  apply Foo.\n"
    )

    assert recs[0]["action"] == "transitivity M ..."
    assert recs[0]["action_type"] == "strategy_hint"
    assert recs[0]["metadata"]["requires_instantiation"] is True
    assert recs[1]["action"] == "apply Foo."
    assert recs[1]["action_type"] == "tactic_candidate"
    assert recs[1]["metadata"]["epistemic_status"] == (
        "static_candidate_uncertified_by_ec"
    )
    statuses = {
        item["status"] for item in _bridge_lemmas_epistemic_evidence(recs)
    }
    assert "template_requires_instantiation" in statuses
    assert "static_candidate_uncertified_by_ec" in statuses


def test_diagnose_recommendation_is_strategy_with_epistemic_status() -> None:
    text = """
=== Error Diagnosis ===

Level:      EXECUTION - the tactic is right, but the form is wrong.

Diagnosis:  rewrite direction is wrong

Suggestion: Try `rewrite -Foo.`

(Source: kb.error_patterns)
"""
    rec = _diagnose_recommendation(text, {"status": "open"})

    assert rec is not None
    data = rec.to_dict()
    assert data["action_type"] == "strategy_hint"
    assert data["metadata"]["epistemic_status"] == "diagnostic_pattern_match"
    assert data["metadata"]["recommended_next"] == "try_alternate_form"
    evidence = _diagnose_epistemic_evidence(text)
    assert evidence[0]["status"] == "diagnostic_execution_match"


def test_try_report_promotes_accepted_preflight_to_runnable_tactic() -> None:
    report = """
[TRY] tactic: smt().
[TRY] accepted: True
[TRY] goal_after: all goals closed.
[TRY] NOTE: session state unchanged. If accepted, commit with `-next -c '<tactic>'` to make it stick.
"""
    result = _parse_try_report(report, "smt().")
    recs = _try_recommendations(result, _DictRecommendation)
    data = recs[0].to_dict()

    assert result["accepted"] is True
    assert result["goal_after_closed"] is True
    assert data["action"] == "smt()."
    assert data["action_type"] == "runnable_tactic"
    assert data["confidence"] == "verified"
    assert data["metadata"]["epistemic_status"] == "easycrypt_preflight_accepted"


def test_try_report_turns_preflight_no_progress_into_avoid_action() -> None:
    report = """
[TRY] tactic: rewrite Foo.
[TRY] accepted: True
[TRY] goal_after: 1 subgoal(s) remaining
[TRY] WARNING: tactic accepted but PRODUCES NO PROGRESS (structural-fingerprint-equal).
"""
    result = _parse_try_report(report, "rewrite Foo.")
    recs = _try_recommendations(result, _DictRecommendation)
    data = recs[0].to_dict()

    assert result["accepted"] is True
    assert result["no_progress_predicted"] is True
    assert data["action_type"] == "avoid_action"
    assert data["metadata"]["epistemic_status"] == "easycrypt_preflight_no_progress"


def test_goal_info_marks_parser_tactics_as_legacy_templates() -> None:
    evidence = _goal_info_epistemic_evidence({
        "suggested_tactics": ["smt().", "rewrite ..."],
    })
    statuses = {item["status"] for item in evidence}
    assert "legacy_parser_templates_not_action_candidates" in statuses
    assert "template_requires_instantiation" in statuses


def test_lemma_hints_recommend_signature_lookup_not_direct_apply() -> None:
    hints = [{
        "name": "take_nth",
        "qualified": "List.take_nth",
        "kind": "lemma",
        "file": "easycrypt-src/theories/datatypes/List.ec",
        "matched_op": "take",
    }]
    recs = _lemma_hint_recommendations(hints)

    data = recs[0].to_dict()
    assert data["action"] == (
        '{"intent":"lookup_symbol","payload":{"symbol":"take_nth"}}'
    )
    assert data["action_type"] == "inspection_action"
    assert data["metadata"]["epistemic_status"] == "context_retrieval_unverified"
    evidence = _lemma_hints_epistemic_evidence(hints)
    assert evidence[0]["status"] == "context_retrieval_unverified"


def test_inv_from_lemma_concrete_template_is_candidate() -> None:
    output = """
Ready-to-use call template:
call (_: ={glob A} /\\ !bad{2}).
"""
    recs = _inv_from_lemma_recommendations("equiv_foo", output)

    assert recs[0]["action_type"] == "tactic_candidate"
    assert recs[0]["metadata"]["epistemic_status"] == (
        "context_extracted_candidate_uncertified_by_ec"
    )
    evidence = _inv_from_lemma_epistemic_evidence(output)
    assert evidence[0]["status"] == "context_extracted_candidate_uncertified_by_ec"


def test_inv_from_lemma_placeholder_template_is_strategy() -> None:
    output = """
Ready-to-use call template:
call (_: <instantiate invariant>).
"""
    recs = _inv_from_lemma_recommendations("equiv_foo", output)

    assert recs[0]["action_type"] == "strategy_hint"
    assert recs[0]["metadata"]["requires_instantiation"] is True


def test_auto_diff_call_inv_is_strategy_not_runnable() -> None:
    recs = AutoDiffPhase(None)._diff_recommendations(
        "Statements differ. Use `call (_: Inv)` with an explicit invariant.",
        set(),
    )

    assert recs[0]["action"] == "call (_: Inv)."
    assert recs[0]["action_type"] == "strategy_hint"
    assert recs[0]["metadata"]["epistemic_status"] == (
        "template_requires_instantiation"
    )
    assert recs[0]["metadata"]["requires_instantiation"] is True


def test_auto_diff_unverified_concrete_tactic_is_candidate() -> None:
    recs = AutoDiffPhase(None)._diff_recommendations(
        "Statements are misaligned. Try `swap{1} 2 -1`.",
        set(),
    )

    assert recs[0]["action"] == "swap{1} 2 -1."
    assert recs[0]["action_type"] == "tactic_candidate"
    assert recs[0]["metadata"]["epistemic_status"] == (
        "static_alignment_candidate_uncertified_by_ec"
    )


def test_auto_diff_preflight_ready_call_is_verified_runnable() -> None:
    recs = AutoDiffPhase(None)._diff_recommendations(
        "Pivot found: `call Foo`.",
        {"Foo"},
    )

    assert recs[0]["action"] == "call Foo."
    assert recs[0]["action_type"] == "runnable_tactic"
    assert recs[0]["confidence"] == "verified"
    assert recs[0]["metadata"]["epistemic_status"] == "easycrypt_preflight_accepted"


class _DictRecommendation:
    def __init__(self, **kwargs):
        self._data = dict(kwargs)

    def to_dict(self):
        return dict(self._data)
