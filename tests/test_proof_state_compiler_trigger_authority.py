from __future__ import annotations

from dataclasses import replace

import pytest

from core.easycrypt.proof_state_compiler.contracts import (
    AGENT_SELECTED_OPERATION,
    CURRENT_STATE_FAILURE,
    STATE_REFRESH,
    CompilerTurnEvidence,
    StateRef,
    compiler_invocation_context,
    freeze_json_object,
)
from workflow.proof_management.protocol_repair import AgentIntent
from workflow.proof_management.types import ManagedTurn, ProofStateSnapshot
from workflow.proof_state_compiler.turn_evidence import (
    compiler_turn_evidence,
)


def _state_ref(
    *,
    session_id: str = "trigger-authority-session",
    version: int = 7,
    prefix: str = "f" * 64,
) -> StateRef:
    return StateRef(
        session_id=session_id,
        state_version=version,
        goal_identity="goal-after-turn",
        goal_identity_required=True,
        committed_prefix_identity=prefix,
    )


def _turn_evidence(
    *,
    outcome: str = "rejected",
    effect: str = "unchanged",
    tactic: str = "apply SelectedLemma.",
) -> CompilerTurnEvidence:
    return CompilerTurnEvidence(
        source_event_id="ter-event-7",
        source_event_sequence=23,
        authority_kind="event_bound_tactic_execution_result",
        artifact_ref="tactic_execution_results/result.json",
        artifact_hash="a" * 40,
        hash_algorithm="sha1",
        post_state_ref=_state_ref(),
        intent="commit_tactic",
        payload=freeze_json_object({"tactic": tactic}),
        outcome_kind=outcome,
        proof_state_effect=effect,
        structured_error=(
            "[error] cannot infer module arguments"
            if outcome == "rejected"
            else ""
        ),
    )


def test_rejected_turn_binds_one_current_failure_trigger_beside_refresh() -> None:
    context = compiler_invocation_context(_state_ref(), _turn_evidence())

    assert tuple(trigger.trigger_kind for trigger in context.triggers) == (
        STATE_REFRESH,
        CURRENT_STATE_FAILURE,
    )
    failure = context.event_trigger
    assert failure is not None
    assert failure.commitment_anchor is not None
    assert failure.commitment_anchor.anchor_kind == "rejected_proof_operation"
    assert failure.commitment_anchor.subject.to_dict() == {
        "intent": "commit_tactic",
        "payload": {"tactic": "apply SelectedLemma."},
        "structured_error": "[error] cannot infer module arguments",
    }
    assert failure.source_event_id == "ter-event-7"


def test_accepted_turn_binds_agent_selected_operation_without_error() -> None:
    evidence = _turn_evidence(
        outcome="accepted",
        effect="changed",
        tactic="while (={x}) (1:2).",
    )
    context = compiler_invocation_context(_state_ref(), evidence)

    assert context.event_trigger is not None
    assert context.event_trigger.trigger_kind == AGENT_SELECTED_OPERATION
    assert context.event_trigger.commitment_anchor is not None
    assert context.event_trigger.commitment_anchor.anchor_kind == (
        "accepted_proof_operation"
    )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("authority_kind", "manager_stdout", "event-bound"),
        ("artifact_hash", "not-a-hash", "artifact hash"),
        ("outcome_kind", "read_only", "proof mutation outcome"),
        ("proof_state_effect", "unknown", "proof mutation outcome"),
    ],
)
def test_turn_evidence_rejects_non_authoritative_or_inconsistent_values(
    field: str,
    value: object,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        replace(_turn_evidence(), **{field: value})


def test_turn_and_snapshot_occurrence_types_are_exact() -> None:
    with pytest.raises(ValueError, match="source event identity"):
        replace(_turn_evidence(), source_event_sequence=True)
    with pytest.raises(TypeError, match="goal_identity_required"):
        replace(_managed_turn(authority=_execution_authority()).snapshot,
                goal_identity_required=1)


@pytest.mark.parametrize(
    "state_ref",
    [
        _state_ref(session_id="sibling-session"),
        _state_ref(version=8),
        _state_ref(prefix="e" * 64),
        replace(_state_ref(), goal_identity="another-goal"),
    ],
)
def test_invocation_context_fails_closed_on_current_state_drift(
    state_ref: StateRef,
) -> None:
    with pytest.raises(ValueError, match="turn evidence is stale"):
        compiler_invocation_context(state_ref, _turn_evidence())


def test_trigger_identity_changes_with_exact_rejected_payload() -> None:
    first = compiler_invocation_context(_state_ref(), _turn_evidence())
    second = compiler_invocation_context(
        _state_ref(),
        _turn_evidence(tactic="apply (SelectedLemma M)."),
    )

    assert first.identity_sha256 != second.identity_sha256
    assert first.event_trigger is not None and second.event_trigger is not None
    assert first.event_trigger.trigger_id != second.event_trigger.trigger_id


def test_trigger_identity_changes_with_authoritative_event_occurrence() -> None:
    first_evidence = _turn_evidence()
    second_evidence = replace(
        first_evidence,
        source_event_id="ter-event-8",
        source_event_sequence=24,
    )

    first = compiler_invocation_context(_state_ref(), first_evidence)
    second = compiler_invocation_context(_state_ref(), second_evidence)

    assert first.event_trigger is not None and second.event_trigger is not None
    assert first.event_trigger.trigger_id != second.event_trigger.trigger_id
    assert first.event_trigger.commitment_anchor is not None
    assert second.event_trigger.commitment_anchor is not None
    assert (
        first.event_trigger.commitment_anchor.anchor_id
        != second.event_trigger.commitment_anchor.anchor_id
    )


def _managed_turn(*, authority: dict[str, object]) -> ManagedTurn:
    return ManagedTurn(
        ok=True,
        workspace_view={
            "proof_status": {"status": "open"},
            "last_result": {
                "outcome_kind": "rejected",
                "proof_state_effect": "unchanged",
            },
        },
        snapshot=ProofStateSnapshot(
            node_id="Tree_0_0",
            session_tag="trigger-authority",
            session_dir="/tmp/trigger-authority",
            session_epoch=1,
            state_version=7,
            goal_hash="goal-after-turn",
            goal_identity_required=True,
        ),
        intent=AgentIntent(
            intent="commit_tactic",
            payload={"tactic": "apply SelectedLemma."},
        ),
        manager_actions=[{
            "label": "commit_tactic",
            "outcome_kind": "rejected",
            "proof_state_effect": "unchanged",
            "execution_authority": authority,
        }],
    )


def _execution_authority() -> dict[str, object]:
    return {
        "authority_kind": "event_bound_tactic_execution_result",
        "event_type": "tactic.execution.produced",
        "event_id": "ter-event-7",
        "event_sequence": 23,
        "artifact_ref": "tactic_execution_results/result.json",
        "artifact_hash": "a" * 40,
        "hash_algorithm": "sha1",
        "submitted_tactics": ["apply SelectedLemma."],
        "status": "failed",
        "state_changed": False,
        "history_committed": False,
        "structured_error": "[error] cannot infer module arguments",
    }


def test_manager_turn_binding_uses_only_exact_execution_authority() -> None:
    history = ["proc."]
    evidence = compiler_turn_evidence(
        _managed_turn(authority=_execution_authority()),
        session_id="/tmp/trigger-authority",
        committed_history=history,
    )

    assert evidence is not None
    assert evidence.source_event_id == "ter-event-7"
    assert evidence.payload.to_dict() == {"tactic": "apply SelectedLemma."}
    assert evidence.structured_error == (
        "[error] cannot infer module arguments"
    )


def test_manager_turn_binding_uses_canonical_agent_tactic_identity() -> None:
    turn = replace(
        _managed_turn(authority=_execution_authority()),
        intent=AgentIntent(
            intent="commit_tactic",
            payload={"tactic": "  apply SelectedLemma.  "},
        ),
    )

    evidence = compiler_turn_evidence(
        turn,
        session_id="/tmp/trigger-authority",
        committed_history=["proc."],
    )

    assert evidence is not None
    assert evidence.payload.to_dict() == {"tactic": "apply SelectedLemma."}


@pytest.mark.parametrize(
    "change",
    [
        {"event_type": "tool.result"},
        {"submitted_tactics": ["apply AnotherLemma."]},
        {"artifact_hash": ""},
        {"state_changed": True},
    ],
)
def test_manager_turn_binding_abstains_on_authority_or_payload_drift(
    change: dict[str, object],
) -> None:
    authority = {**_execution_authority(), **change}
    assert compiler_turn_evidence(
        _managed_turn(authority=authority),
        session_id="/tmp/trigger-authority",
        committed_history=["proc."],
    ) is None
