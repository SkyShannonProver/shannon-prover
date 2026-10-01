"""Committed-admit completion safety is profile-independent admission."""
from __future__ import annotations

from tests.helpers.builders import (
    intent,
    make_manager,
)


_WITH_ADMITS = ["proc.", "sp.", "admit.", "wp.", "admit."]


def _manager(surface_profile: str, history: list[str] | None = None):
    manager = make_manager(
        lemma_name="step4_badi",
        surface_profile=surface_profile,
    )
    committed = list(_WITH_ADMITS if history is None else history)
    manager.repl.committed_history = (  # type: ignore[method-assign]
        lambda: list(committed)
    )
    return manager


def _admit(manager, current_intent):
    return manager.admission.admit_intent(
        current_intent,
        latest_view=manager.latest_view,
        latest_snapshot=manager.latest_snapshot,
    )


def _assert_flat_block(manager, current_intent) -> None:
    turn = _admit(manager, current_intent).turn
    assert turn is not None and turn.ok is False
    assert "(a)" not in turn.repair_prompt
    assert "checkpoints" not in turn.repair_prompt
    assert "un-discharged `admit.` tactic" in turn.repair_prompt


def test_l4_finish_with_admits_gets_flat_hard_block() -> None:
    _assert_flat_block(
        _manager("proof_state_compiler"),
        intent("finish"),
    )


def test_l4_finish_with_admits_never_escapes_on_repetition() -> None:
    manager = _manager("proof_state_compiler")
    for _ in range(3):
        _assert_flat_block(manager, intent("finish"))


def test_l4_qed_with_admits_stays_hard_blocked() -> None:
    _assert_flat_block(
        _manager("proof_state_compiler"),
        intent("commit_tactic", "qed."),
    )


def test_l1_finish_with_admits_keeps_flat_hard_block() -> None:
    _assert_flat_block(_manager("l1_goal_projection"), intent("finish"))


def test_l1_finish_with_admits_never_honored_via_counter() -> None:
    manager = _manager("l1_goal_projection")
    for _ in range(3):
        _assert_flat_block(manager, intent("finish"))


def test_admit_gate_precedes_open_proof_give_up_gate() -> None:
    manager = _manager("proof_state_compiler")
    manager.latest_view = {"proof_status": {"status": "open", "remaining_goals": 2}}
    for _ in range(3):
        _assert_flat_block(manager, intent("finish"))


def test_give_up_gate_unaffected_without_admits() -> None:
    manager = _manager(
        "proof_state_compiler",
        history=["proc.", "sp.", "wp."],
    )
    manager.latest_view = {"proof_status": {"status": "open", "remaining_goals": 1}}
    decision = _admit(manager, intent("finish"))
    assert decision.turn is None
    assert decision.preflight.kind == "menu"
