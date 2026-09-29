"""Committed-admit admission state survives resume-owned history."""
from __future__ import annotations

from tests.helpers.builders import intent, make_manager


def _manager(history: list[str]):
    manager = make_manager(lemma_name="step4_badi")
    manager.repl.committed_history = lambda: list(history)  # type: ignore[method-assign]
    return manager


def _admit(manager, current_intent):
    return manager.admission.admit_intent(
        current_intent,
        latest_view=manager.latest_view,
        latest_snapshot=manager.latest_snapshot,
    )


def test_resumed_node_is_gated_by_committed_admits() -> None:
    manager = _manager([
        "proc.", "sp.", "admit.", "wp.", "admit.", "skip.",
    ])
    for current in (intent("finish"), intent("commit_tactic", "qed.")):
        turn = _admit(manager, current).turn
        assert turn is not None, f"{current.intent} must be gated on resume"
        assert turn.ok is False
        assert "2 un-discharged `admit.` tactic" in turn.repair_prompt


def test_gate_clears_after_rewind_drops_admit_from_history() -> None:
    manager = _manager(["proc.", "sp.", "wp.", "skip."])
    assert _admit(manager, intent("finish")).turn is None
    decision = _admit(manager, intent("commit_tactic", "qed."))
    assert decision.turn is None


def test_non_finish_qed_intents_are_never_gated() -> None:
    manager = _manager(["admit.", "admit."])
    for current in (
        intent("commit_tactic", "sp."),
        intent("fresh_restart"),
        intent("undo_last_step"),
    ):
        decision = _admit(manager, current)
        assert decision.turn is None


def test_committed_admit_labels_carry_step_and_tactic() -> None:
    manager = _manager(["proc.", "admit.", "wp."])
    records = manager.admission.committed_admit_records()
    assert len(records) == 1
    assert "step 2" in records[0]["gate_label"]
    assert "admit." in records[0]["gate_label"]
