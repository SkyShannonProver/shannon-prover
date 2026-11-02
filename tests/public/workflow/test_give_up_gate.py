"""Admission-owned anti-premature-give-up policy tests."""
from __future__ import annotations

import time

from tests.helpers.builders import make_manager
from workflow.proof_management import AgentIntent
from workflow.proof_management.intent_admission import (
    DEFAULT_GIVE_UP_ALLOW_AFTER,
    DEFAULT_GIVE_UP_WINDOW_S,
)


_OPEN = {"proof_status": {"status": "open", "remaining_goals": 1}}
_DONE = {"proof_status": {"status": "complete", "remaining_goals": 0}}


def _manager(view):
    manager = make_manager()
    manager.latest_view = dict(view)
    manager.repl.committed_history = lambda: []  # type: ignore[method-assign]
    return manager


def _admit(manager, intent: AgentIntent):
    return manager.admission.admit_intent(
        intent,
        latest_view=manager.latest_view,
        latest_snapshot=manager.latest_snapshot,
    )


def _finish() -> AgentIntent:
    return AgentIntent(intent="finish", payload={})


def test_non_finish_never_gated() -> None:
    manager = _manager(_OPEN)
    decision = _admit(
        manager,
        AgentIntent(intent="commit_tactic", payload={"tactic": "trivial."}),
    )
    assert decision.admitted


def test_success_finish_never_gated() -> None:
    manager = _manager(_DONE)
    for _ in range(5):
        assert _admit(manager, _finish()).admitted
    manager = _manager({"proof_status": {"status": "open", "remaining_goals": 0}})
    assert _admit(manager, _finish()).admitted


def test_candidate_closed_states_never_gated() -> None:
    for status in (
        "candidate_closed",
        "session_closed_pending_verification",
        "complete",
        "empty",
    ):
        manager = _manager({"proof_status": {"status": status}})
        assert _admit(manager, _finish()).admitted, status


def test_open_finish_deflected_once_then_allowed() -> None:
    assert DEFAULT_GIVE_UP_ALLOW_AFTER == 2
    manager = _manager(_OPEN)
    first = _admit(manager, _finish())
    assert first.preflight.kind == "menu"
    menu = first.preflight.observation["control_menu"]
    notice = menu["notice"]
    assert "That is your call" in notice
    assert "finishing is fine" in notice
    assert menu["items"][0]["submit"] == {"intent": "finish", "payload": {}}
    assert "give-up 1 of" not in notice.lower()
    assert "make a genuine attempt" not in notice.lower()
    assert _admit(manager, _finish()).admitted


def test_window_prunes_old_giveups() -> None:
    manager = _manager(_OPEN)
    old = time.time() - DEFAULT_GIVE_UP_WINDOW_S - 10
    manager.admission._give_up_times = [old]
    decision = _admit(manager, _finish())
    assert decision.preflight.kind == "menu"
    assert len(manager.admission._give_up_times) == 1
    assert manager.admission._give_up_times[0] > old
