from __future__ import annotations

from workflow.proof_management.backend_actions import _backend_action_outcome
from workflow.managed_turn_outcome import (
    PROOF_STATE_EFFECTS,
    PROOF_STATE_UNKNOWN,
    normalize_proof_state_effect,
)


def _summary(label: str, payload: dict, *, returncode: int = 0) -> dict:
    return _backend_action_outcome(
        label,
        stdout='{"result":{"status":"stdout-poison"}}',
        exit_code=returncode,
        mutates_proof_state=True,
        requires_execution_result=True,
        tactic_execution_result=payload,
    )


def test_backend_accepted_commit_is_the_only_source_of_changed_outcome() -> None:
    action = _summary(
        "commit_tactic",
        {
            "result": {"ok": True, "status": "ok"},
            "execution": {"state_changed": True, "history_committed": True},
        },
    )

    assert action["outcome_kind"] == "accepted"
    assert action["proof_state_effect"] == "changed"
    assert action["proof_state_changed"] is True
    assert action["needs_attention"] is False


def test_backend_no_progress_is_unchanged_attention_even_when_process_succeeds() -> None:
    action = _summary(
        "commit_tactic",
        {
            "result": {"ok": True, "status": "no_progress_reverted"},
            "execution": {"state_changed": False, "history_committed": False},
        },
    )

    assert action["outcome_kind"] == "no_progress"
    assert action["proof_state_effect"] == "unchanged"
    assert action["proof_state_changed"] is False
    assert action["needs_attention"] is True


def test_backend_partial_success_preserves_committed_prefix_and_attention() -> None:
    action = _summary(
        "commit_tactic",
        {
            "result": {"ok": False, "status": "partial_success"},
            "execution": {
                "state_changed": True,
                "history_committed": True,
                "accepted_count": 1,
            },
        },
        returncode=1,
    )

    assert action == {
        "outcome_kind": "partial_success",
        "proof_state_effect": "changed",
        "proof_state_changed": True,
        "needs_attention": True,
    }


def test_backend_partial_success_without_committed_change_fails_closed() -> None:
    action = _summary(
        "commit_tactic",
        {
            "result": {"ok": False, "status": "partial_success"},
            "execution": {
                "state_changed": False,
                "history_committed": False,
                "accepted_count": 1,
            },
        },
        returncode=1,
    )

    assert action == {
        "outcome_kind": "backend_error",
        "proof_state_effect": "unknown",
        "proof_state_changed": False,
        "needs_attention": True,
    }


def test_backend_rejection_is_not_inferred_from_human_result_text() -> None:
    action = _summary(
        "commit_tactic",
        {
            "result": {
                "ok": False,
                "status": "error",
                "message": "wording deliberately contains no verdict keyword",
            },
            "execution": {"state_changed": False, "history_committed": False},
        },
        returncode=1,
    )

    assert action["outcome_kind"] == "rejected"
    assert action["proof_state_effect"] == "unchanged"
    assert action["needs_attention"] is True


def test_executed_effect_contract_rejects_forecasts_and_audit_operations() -> None:
    for effect in PROOF_STATE_EFFECTS:
        assert normalize_proof_state_effect(effect) == effect

    for non_outcome in (
        "will_change_proof_state",
        "does_not_change_proof_state_read_only",
        "rewind_before_checkpoint",
        "scratch_replay_only",
    ):
        assert normalize_proof_state_effect(non_outcome) == PROOF_STATE_UNKNOWN
