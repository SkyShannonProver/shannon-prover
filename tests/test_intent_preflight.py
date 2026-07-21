from __future__ import annotations

from workflow.proof_management import AgentIntent
from workflow.proof_management.intent_preflight import preflight_intent


def test_preflight_does_not_intercept_admit() -> None:
    # `admit` is NOT blocked by preflight. The manager gates finish/qed while
    # committed admits remain; the orchestrator rejects a final admit.
    decision = preflight_intent(
        intent=AgentIntent(intent="commit_tactic", payload={"tactic": "admit."}),
        latest_view={"proof_status": {"status": "open"}},
        surface_profile=None,
    )

    assert decision.kind == "none"
    assert decision.should_handle is False
    assert decision.audit_kind != "agent_intent.admit_clarification"


def test_preflight_finish_requires_qed_when_candidate_pending() -> None:
    decision = preflight_intent(
        intent=AgentIntent(intent="finish", payload={}),
        latest_view={"proof_status": {"status": "candidate_closed_pending_qed"}},
        surface_profile=None,
    )

    assert decision.kind == "action_repair"
    assert decision.actions[0]["label"] == "finish_requires_qed"
    assert "qed" in decision.repair_prompt
