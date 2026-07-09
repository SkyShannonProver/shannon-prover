"""Tests for the deambiguation of ``agent_view.latest_errors``.

Each entry in ``latest_errors`` now carries an ``origin`` field
classifying the error as either:

  * ``tactic_audit`` — the agent's last committed/probed tactic
    failed (a NORMAL part of proof iteration; not a session-
    corruption signal).
  * ``structural`` — the underlying event stream is broken
    (JSON parse failure, event_contract invariant violations).
    The session is genuinely unhealthy.

``_safe_next_actions`` previously preempted the entire recommendation
queue with a singleton ``inspect.latest_error`` action whenever ANY
``latest_errors`` entry existed — which conflated tactic-audit noise
with session corruption. ChaChaPoly step1 Tree-0.1 (2026-05-03)
misread that signal and tried to ``rm -rf`` its session dir. The
fixed behavior:

- structural errors → still escalate to ``diagnose``
- tactic-audit errors with NO recommendations → escalate (legacy)
- tactic-audit errors WITH recommendations → fall through; do not
  override the recommendation queue
"""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from core.easycrypt.session_agent_view import (  # noqa: E402
    _latest_errors,
    _safe_next_actions,
    is_audit_noise_only,
)


# ─── _latest_errors() origin tagging ──────────────────────────────────────

def test_latest_errors_tags_tactic_failure_with_tactic_audit_origin() -> None:
    """A tactic.result-derived error must carry origin=tactic_audit."""
    proof_state = {
        "event_contract": {
            "ok": True,
            "latest_error": "unknown lemma `foo'",
            "latest_error_tactic": "apply foo.",
            "latest_attempt": {
                "event_id": "e1",
                "attempt_kind": "committed_tactic",
                "status": "error",
                "tactic": "apply foo.",
                "error": "unknown lemma `foo'",
            },
            "recent_failed_attempts": [{
                "event_id": "e1",
                "attempt_kind": "committed_tactic",
                "status": "error",
                "tactic": "apply foo.",
                "error": "unknown lemma `foo'",
            }],
        },
    }
    out = _latest_errors(proof_state)
    assert len(out) == 1
    e = out[0]
    assert e["code"] == "current_tactic_error"
    assert e["origin"] == "tactic_audit"
    assert e["severity"] == "noise"
    assert e["tactic"] == "apply foo."
    assert e["temporal_scope"] == "current_attempt"


def test_latest_errors_tags_transition_error_with_tactic_audit() -> None:
    """``latest_transition.latest_error`` is also tactic-audit by
    construction (sourced from the same tactic.result events)."""
    proof_state = {
        "event_contract": {"ok": True},
        "latest_transition": {
            "latest_error": "could not unify",
            "tactic": "rewrite -E.",
        },
    }
    out = _latest_errors(proof_state)
    assert len(out) == 1
    assert out[0]["origin"] == "tactic_audit"
    assert out[0]["temporal_scope"] == "prior_attempt"


def test_latest_errors_marks_prior_probe_failure_as_stale_after_accepted_probe() -> None:
    proof_state = {
        "event_contract": {
            "ok": True,
            "latest_attempt": {
                "event_id": "try-ok",
                "attempt_kind": "speculative_probe",
                "status": "probe_accepted",
                "tactic": "have h: 1 = 1 by done.",
                "error": "",
            },
            "recent_failed_attempts": [{
                "event_id": "try-bad",
                "attempt_kind": "speculative_probe",
                "status": "probe_rejected",
                "tactic": "have h: Pr[MainD(G2, RO).distinguish(()) @ &m : res] = 0%r.",
                "error": "wrong number of arguments",
            }],
        },
    }
    out = _latest_errors(proof_state)
    assert len(out) == 1
    e = out[0]
    assert e["code"] == "prior_tactic_error"
    assert e["temporal_scope"] == "prior_attempt"
    assert e["relation_to_current_attempt"] == "stale_unrelated_to_current_attempt"
    assert e["current_attempt_status"] == "probe_accepted"
    assert e["message"] == "wrong number of arguments"


def test_latest_errors_promotes_event_contract_errors_as_structural() -> None:
    """When event_contract.ok=False, the bucket's structural errors
    are surfaced via latest_errors with origin=structural so the
    agent sees them in the same place as audit noise but
    distinguishably."""
    proof_state = {
        "event_contract": {
            "ok": False,
            "errors": [
                "event stream is empty",
                "tactic.submitted at index 5 has no matching tactic.result",
            ],
        },
    }
    out = _latest_errors(proof_state)
    assert all(e["origin"] == "structural" for e in out)
    assert all(e["severity"] == "fatal" for e in out)
    messages = {e["message"] for e in out}
    assert "event stream is empty" in messages
    assert any("matching tactic.result" in e["message"] for e in out)


def test_latest_errors_dedup_across_event_contract_and_transition() -> None:
    """Same error message must not appear twice (e.g. when both
    event_contract.latest_error and latest_transition.latest_error
    point at the same tactic.result event)."""
    msg = "unknown lemma `foo'"
    proof_state = {
        "event_contract": {
            "ok": True,
            "latest_error": msg,
            "latest_error_tactic": "apply foo.",
        },
        "latest_transition": {
            "latest_error": msg,
            "tactic": "apply foo.",
        },
    }
    out = _latest_errors(proof_state)
    assert len(out) == 1


def test_is_audit_noise_only_helper_classifies_correctly() -> None:
    assert is_audit_noise_only([]) is False
    assert is_audit_noise_only([
        {"origin": "tactic_audit", "message": "x"},
    ]) is True
    assert is_audit_noise_only([
        {"origin": "tactic_audit", "message": "x"},
        {"origin": "tactic_audit", "message": "y"},
    ]) is True
    assert is_audit_noise_only([
        {"origin": "tactic_audit", "message": "x"},
        {"origin": "structural", "message": "z"},
    ]) is False
    # Missing origin (older callers) defaults to tactic_audit because
    # the historical default for ``latest_errors`` was always
    # tactic-failure-derived.
    assert is_audit_noise_only([
        {"message": "untagged"},
    ]) is True


# ─── _safe_next_actions() escalation policy ──────────────────────────────

def _make_state() -> dict:
    return {
        "status": "in_progress",
        "goal": {"goal_type": "pRHL"},
        "event_contract": {"ok": True},
    }


def test_safe_next_actions_escalates_on_structural_error() -> None:
    """Structural errors must still preempt the recommendation queue
    — the session is unhealthy and the agent should diagnose first."""
    actions = _safe_next_actions(
        proof_state=_make_state(),
        recommendations=[
            {
                "action": "trivial.",
                "action_type": "runnable_tactic",
                "confidence": "verified",
            },
        ],
        latest_errors=[
            {"origin": "structural", "severity": "fatal", "message": "boom"},
        ],
    )
    assert len(actions) == 1
    assert actions[0]["id"] == "inspect.structural_error"


def test_safe_next_actions_does_not_preempt_on_audit_noise_with_recs() -> None:
    """Tactic-audit noise + available recommendations → DO NOT preempt
    the recommendation queue. This is the core fix.

    The agent should see the recommendations (which is what the
    rec-builder generates AFTER the audit-noise branch) instead of
    only ``inspect.latest_error``."""
    state = _make_state()
    recs = [{
        "action": "trivial.",
        "action_type": "runnable_tactic",
        "confidence": "verified",
    }]
    actions = _safe_next_actions(
        proof_state=state,
        recommendations=recs,
        latest_errors=[
            {
                "origin": "tactic_audit",
                "severity": "noise",
                "message": "unknown lemma `foo'",
                "tactic": "apply foo.",
            },
        ],
    )
    # Must NOT be the singleton inspect.latest_error escalation.
    if actions:
        assert actions[0]["id"] != "inspect.latest_error"


def test_safe_next_actions_escalates_on_audit_noise_without_recs() -> None:
    """Tactic-audit noise WITHOUT any recommendations → still
    escalate to diagnose. The agent has nothing else to do, so a
    deterministic next step (``diagnose``) is better than silence."""
    actions = _safe_next_actions(
        proof_state=_make_state(),
        recommendations=[],
        latest_errors=[
            {
                "origin": "tactic_audit",
                "severity": "noise",
                "message": "unknown lemma `foo'",
                "tactic": "apply foo.",
            },
        ],
    )
    assert len(actions) == 1
    assert actions[0]["id"] == "inspect.latest_error"


def test_safe_next_actions_ignores_prior_only_audit_noise_without_recs() -> None:
    actions = _safe_next_actions(
        proof_state=_make_state(),
        recommendations=[],
        latest_errors=[
            {
                "origin": "tactic_audit",
                "severity": "noise",
                "message": "wrong number of arguments",
                "tactic": "have h: bad.",
                "temporal_scope": "prior_attempt",
                "relation_to_current_attempt": (
                    "stale_unrelated_to_current_attempt"
                ),
            },
        ],
    )
    assert actions
    assert actions[0]["id"] != "inspect.latest_error"


def test_safe_next_actions_escalates_on_event_contract_not_ok() -> None:
    """The pre-existing event_contract.ok=False branch keeps its
    behavior: that path catches the same structural cases earlier and
    routes to ``inspect.event_contract`` rather than
    ``inspect.structural_error``. Regression guard."""
    state = _make_state()
    state["event_contract"] = {"ok": False, "errors": ["broken"]}
    actions = _safe_next_actions(
        proof_state=state,
        recommendations=[],
        latest_errors=[],
    )
    assert len(actions) == 1
    assert actions[0]["id"] == "inspect.event_contract"


def main() -> int:
    tests = [
        test_latest_errors_tags_tactic_failure_with_tactic_audit_origin,
        test_latest_errors_tags_transition_error_with_tactic_audit,
        test_latest_errors_marks_prior_probe_failure_as_stale_after_accepted_probe,
        test_latest_errors_promotes_event_contract_errors_as_structural,
        test_latest_errors_dedup_across_event_contract_and_transition,
        test_is_audit_noise_only_helper_classifies_correctly,
        test_safe_next_actions_escalates_on_structural_error,
        test_safe_next_actions_does_not_preempt_on_audit_noise_with_recs,
        test_safe_next_actions_escalates_on_audit_noise_without_recs,
        test_safe_next_actions_ignores_prior_only_audit_noise_without_recs,
        test_safe_next_actions_escalates_on_event_contract_not_ok,
    ]
    for t in tests:
        t()
    print("PASS test_latest_errors_origin")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
