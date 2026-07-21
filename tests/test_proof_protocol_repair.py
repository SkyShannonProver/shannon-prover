from __future__ import annotations

from workflow.proof_management.protocol_repair import (
    backend_failure_repair_prompt,
    finish_requires_qed_action,
    intent_is_standalone_qed,
    parse_agent_intent,
    qed_clarification_action,
    repair_prompt_text,
    repair_prompt_text_for_streak,
    view_allows_qed,
    view_requires_qed_before_finish,
)


def test_parse_agent_intent_accepts_proof_level_schema_only() -> None:
    parsed = parse_agent_intent(
        '{"intent": "commit_tactic", "payload": {"tactic": "byequiv=>//."}}'
    )

    assert parsed.ok is True
    assert parsed.intent is not None
    assert parsed.intent.to_dict() == {
        "intent": "commit_tactic",
        "payload": {"tactic": "byequiv=>//."},
    }


def test_parse_agent_intent_rejects_missing_or_bad_payload() -> None:
    assert parse_agent_intent("no json here").error == "unknown_or_missing_intent"
    assert (
        parse_agent_intent('{"intent": "debug_shell", "payload": {}}').error
        == "unknown_or_missing_intent"
    )
    assert (
        parse_agent_intent('{"intent": "request_restart", "payload": {}}').error
        == "unknown_or_missing_intent"
    )
    assert (
        parse_agent_intent('{"intent": "commit_tactic", "payload": "wp."}').error
        == "payload_must_be_object"
    )
    for retired in ("probe_tactic", "probe_replay_suffix_chunk", "bridge_probe"):
        assert parse_agent_intent(
            f'{{"intent": "{retired}", "payload": {{}}}}'
        ).error == "unknown_or_missing_intent"



def test_qed_detector_requires_standalone_commit_qed() -> None:
    assert intent_is_standalone_qed("commit_tactic", {"tactic": "qed."})
    assert intent_is_standalone_qed("commit_tactic", {"tactic": "(* done *) qed"})
    assert not intent_is_standalone_qed("probe_tactic", {"tactic": "qed."})
    assert not intent_is_standalone_qed("commit_tactic", {"tactic": "by qed."})


def test_qed_view_predicates_track_closed_candidate_states() -> None:
    closed_view = {"proof_status": {"status": "candidate_closed_pending_qed"}}
    open_view = {"proof_status": {"status": "open"}}
    no_more_goals_view = {"current_goal": {"lines": ["No more goals"]}}

    assert view_allows_qed(closed_view)
    assert not view_allows_qed(open_view)
    assert view_requires_qed_before_finish(closed_view)
    assert view_requires_qed_before_finish(no_more_goals_view)
    assert not view_requires_qed_before_finish({
        "proof_status": {"status": "verified"},
    })


def test_protocol_repair_actions_are_non_mutating() -> None:
    actions = [
        qed_clarification_action({"tactic": "qed."}),
        finish_requires_qed_action(),
    ]

    assert [action["label"] for action in actions] == [
        "qed_clarification",
        "finish_requires_qed",
    ]
    assert all(action["mutates_proof_state"] is False for action in actions)
    assert all(action["stdout_has_workspace_view"] is False for action in actions)


def test_backend_failure_repair_prompt_preserves_error_summary() -> None:
    prompt = backend_failure_repair_prompt({
        "label": "lookup_symbol",
        "mutates_proof_state": False,
        "agent_observation": {"error_summary": "unknown symbol"},
    })

    assert "could not complete `lookup_symbol`" in prompt
    assert "committed EasyCrypt proof state was not changed" in prompt
    assert "unknown symbol" in prompt


def test_parse_agent_intent_treats_empty_message_as_recoverable() -> None:
    # An empty or `{}`-only message is unreadable but recoverable: it parses to a
    # not-ok result carrying a repair prompt, never an exception.
    for text in ("", "{}", '{"payload": {}}'):
        parsed = parse_agent_intent(text)
        assert parsed.ok is False
        assert parsed.intent is None
        assert "JSON" in parsed.repair_prompt


def test_repair_prompt_text_for_streak_escalates_after_first() -> None:
    base = repair_prompt_text()
    # First strike: plain, canonical example only.
    assert repair_prompt_text_for_streak(1) == base
    assert "no valid proof intent" not in repair_prompt_text_for_streak(1)
    # Streak: explicit recoverable-no-op framing, names the count, keeps the
    # canonical example.
    streak = repair_prompt_text_for_streak(3)
    assert "3 replies" in streak
    assert "no valid proof intent" in streak
    assert "recoverable no-op" in streak
    assert base in streak
