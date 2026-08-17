from __future__ import annotations

from workflow.proof_management.protocol_repair import (
    backend_failure_repair_prompt,
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


def test_parse_agent_intent_canonicalizes_semantic_string_payloads_once() -> None:
    parsed = parse_agent_intent(
        '{"intent": " commit_tactic ", "payload": {"tactic": "  wp.  "}}'
    )

    assert parsed.ok is True
    assert parsed.intent is not None
    assert parsed.intent.to_dict() == {
        "intent": "commit_tactic",
        "payload": {"tactic": "wp."},
    }


def test_parse_agent_intent_rejects_missing_or_bad_payload() -> None:
    assert (
        parse_agent_intent("no json here").error
        == "expected_exactly_one_json_object"
    )
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
    assert parse_agent_intent(
        '{"intent": "retired_preview_intent", "payload": {}}'
    ).error == "unknown_or_missing_intent"
    for retired in (
        '{"intent": "inspect_context", "payload": {"topic": "goal_info"}}',
        '{"intent": "bridge_options", "payload": {}}',
        '{"intent": "bridge_lemmas", "payload": {}}',
    ):
        assert parse_agent_intent(retired).error == "unknown_or_missing_intent"


def test_parse_agent_intent_rejects_any_wrapper_or_trailing_value() -> None:
    canonical = '{"intent": "finish", "payload": {}}'
    malformed = (
        "Please do this: " + canonical,
        "```json\n" + canonical + "\n```",
        canonical + " trailing prose",
        canonical + "\n" + canonical,
    )

    for text in malformed:
        parsed = parse_agent_intent(text)
        assert parsed.ok is False
        assert parsed.error == "expected_exactly_one_json_object"


def test_parse_agent_intent_requires_the_exact_outer_shape() -> None:
    for text in (
        '{"intent": "finish"}',
        '{"intent": "finish", "payload": null}',
        '{"intent": "finish", "payload": [], "reason": "done"}',
    ):
        assert parse_agent_intent(text).ok is False

    for extra in ("node_id", "view_hash", "goal_hash", "reason"):
        parsed = parse_agent_intent(
            '{"intent":"finish","payload":{},"' + extra + '":"private"}'
        )
        assert parsed.error == "unexpected_top_level_fields"


def test_parse_agent_intent_rejects_aliases_and_extra_payload_fields() -> None:
    malformed = (
        '{"intent":"commit_tactic","payload":{"tactic":"wp.","command":"wp."}}',
        '{"intent":"undo_to_checkpoint","payload":{"index":2}}',
        '{"intent":"undo_to_checkpoint","payload":{"checkpoint_id":"cp_1_x","rewind_note":{}}}',
    )
    for text in malformed:
        assert parse_agent_intent(text).error == "unexpected_payload_fields"

    for retired in (
        '{"intent":"call_subgoals","payload":{"command":"={x}"}}',
        '{"intent":"tactic_forms","payload":{"tactic":"call"}}',
        '{"intent":"operator_lemmas","payload":{"symbol":"big"}}',
        '{"intent":"inv_from_lemma","payload":{"symbol":"H"}}',
    ):
        assert parse_agent_intent(retired).error == "unknown_or_missing_intent"


def test_parse_agent_intent_enforces_exact_scalar_types() -> None:
    for value in ('"false"', '"true"', "0", "1", "null"):
        parsed = parse_agent_intent(
            '{"intent":"fresh_restart","payload":{"confirm":'
            + value
            + ',"confirmation_id":"token"}}'
        )
        assert parsed.error == "payload_field_confirm_must_be_bool"

    for value in ("true", "false", "0", "-1", '"2"', "1.0"):
        parsed = parse_agent_intent(
            '{"intent":"amend_and_replay","payload":{"index":'
            + value
            + ',"tactic":"wp."}}'
        )
        assert parsed.error == "payload_field_index_must_be_positive_int"


def test_parse_agent_intent_requires_nonempty_canonical_strings() -> None:
    cases = (
        ("commit_tactic", "tactic"),
    )
    for intent, field in cases:
        missing = parse_agent_intent(
            '{"intent":"' + intent + '","payload":{}}'
        )
        assert missing.error == "missing_required_payload_fields"
        for value in ('""', '"   "', "null", "1", "true"):
            malformed = parse_agent_intent(
                '{"intent":"' + intent + '","payload":{"' + field + '":'
                + value
                + "}}"
            )
            assert malformed.error == (
                f"payload_field_{field}_must_be_nonempty_string"
            )


def test_parse_agent_intent_accepts_only_canonical_control_variants() -> None:
    valid = (
        '{"intent":"undo_last_step","payload":{}}',
        '{"intent":"finish","payload":{}}',
        '{"intent":"undo_to_checkpoint","payload":{}}',
        '{"intent":"undo_to_checkpoint","payload":{"checkpoint_id":"cp_1_x"}}',
        '{"intent":"undo_to_checkpoint","payload":{"checkpoint_id":"cp_1_x","confirm":true,"confirmation_id":"token"}}',
        '{"intent":"undo_to_checkpoint","payload":{"restore_id":"restore_x"}}',
        '{"intent":"fresh_restart","payload":{}}',
        '{"intent":"fresh_restart","payload":{"confirm":true,"confirmation_id":"token"}}',
        '{"intent":"amend_and_replay","payload":{}}',
        '{"intent":"amend_and_replay","payload":{"index":1,"tactic":"wp."}}',
    )
    assert all(parse_agent_intent(text).ok for text in valid)

    invalid = (
        '{"intent":"undo_to_checkpoint","payload":{"restore_id":"restore_x","checkpoint_id":"cp_1_x"}}',
        '{"intent":"undo_to_checkpoint","payload":{"checkpoint_id":"cp_1_x","confirm":true}}',
        '{"intent":"undo_to_checkpoint","payload":{"checkpoint_id":"cp_1_x","confirmation_id":"token"}}',
        '{"intent":"undo_to_checkpoint","payload":{"checkpoint_id":"cp_1_x","confirm":false,"confirmation_id":"token"}}',
        '{"intent":"fresh_restart","payload":{"confirm":true}}',
        '{"intent":"fresh_restart","payload":{"confirmation_id":"token"}}',
        '{"intent":"fresh_restart","payload":{"confirm":false,"confirmation_id":"token"}}',
        '{"intent":"amend_and_replay","payload":{"index":1}}',
        '{"intent":"amend_and_replay","payload":{"tactic":"wp."}}',
    )
    assert all(not parse_agent_intent(text).ok for text in invalid)



def test_qed_detector_requires_standalone_commit_qed() -> None:
    assert intent_is_standalone_qed("commit_tactic", {"tactic": "qed."})
    assert intent_is_standalone_qed("commit_tactic", {"tactic": "(* done *) qed"})
    assert not intent_is_standalone_qed("tactic_forms", {"name": "qed"})
    assert not intent_is_standalone_qed("commit_tactic", {"tactic": "by qed."})


def test_qed_view_predicates_track_closed_candidate_states() -> None:
    closed_view = {"proof_status": {"status": "goals_discharged_pending_qed"}}
    open_view = {"proof_status": {"status": "open"}}
    no_more_goals_view = {"current_goal": {"lines": ["No more goals"]}}

    assert view_allows_qed(closed_view)
    assert not view_allows_qed(open_view)
    assert not view_allows_qed(no_more_goals_view)
    assert view_requires_qed_before_finish(closed_view)
    assert not view_requires_qed_before_finish(no_more_goals_view)
    assert not view_requires_qed_before_finish({
        "proof_status": {"status": "verified"},
    })


def test_protocol_repair_actions_are_non_mutating() -> None:
    actions = [qed_clarification_action({"tactic": "qed."})]

    assert [action["label"] for action in actions] == ["qed_clarification"]
    assert all(action["mutates_proof_state"] is False for action in actions)
    assert all(action["stdout_has_workspace_view"] is False for action in actions)
    assert actions[0]["outcome_kind"] == "repair"
    assert actions[0]["proof_state_effect"] == "unchanged"
    assert actions[0]["needs_attention"] is True


def test_backend_failure_repair_prompt_preserves_error_summary() -> None:
    prompt = backend_failure_repair_prompt({
        "label": "tactic_preflight",
        "mutates_proof_state": False,
        "agent_observation": {"error_summary": "unknown symbol"},
    })

    assert "could not complete `tactic_preflight`" in prompt
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
