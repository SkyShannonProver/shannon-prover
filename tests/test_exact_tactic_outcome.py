"""Fast tests for the shared fail-closed exact-tactic verdict parser."""

from workflow.proof_state_compiler.certification_gateway import (
    exact_tactic_outcome,
)


TACTIC = "call (Alossless_F (<: D2(O).O) _)."


def _action(*, tactic=TACTIC, validation="daemon_accepted_on_exact_state"):
    return {
        "agent_observation": {
            "content": {
                "candidate": tactic,
                "runnable_evidence": {
                    "exact_submit": {
                        "intent": "commit_tactic",
                        "payload": {"tactic": tactic},
                    },
                    "validation_status": validation,
                    "no_progress_status": "progress",
                    "previewed_effect": {
                        "goal_after_closed": False,
                        "goal_after_remaining": 2,
                    },
                },
            },
        },
    }


def test_preflight_parser_accepts_only_exact_daemon_checked_tactic() -> None:
    assert exact_tactic_outcome(_action(), TACTIC)["accepted"]
    assert not exact_tactic_outcome(_action(tactic="skip."), TACTIC)["accepted"]
    assert not exact_tactic_outcome(
        _action(validation="not_preflighted"),
        TACTIC,
    )["accepted"]
    assert not exact_tactic_outcome({}, TACTIC)["accepted"]


def test_preflight_outcome_keeps_checked_residual_shape() -> None:
    assert exact_tactic_outcome(_action(), TACTIC) == {
        "accepted": True,
        "outcome_known": True,
        "goal_after_closed": False,
        "goal_after_remaining": 2,
    }

    missing_preview = _action()
    del missing_preview["agent_observation"]["content"][
        "runnable_evidence"
    ]["previewed_effect"]
    assert exact_tactic_outcome(missing_preview, TACTIC)[
        "outcome_known"
    ] is False
