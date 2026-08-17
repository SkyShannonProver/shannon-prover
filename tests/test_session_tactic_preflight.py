"""Tests for exact, event-bound tactic preflight artifacts."""
from __future__ import annotations

import json
from pathlib import Path

import _pathsetup  # noqa: F401,E402

from core.easycrypt.session_events import append_event, events_of_type, read_events
from core.easycrypt.session_tactic_preflight import (
    TACTIC_PREFLIGHT_EVENT_TYPE,
    build_tactic_preflight_artifact,
    canonical_tactic_preflight_text,
    read_bound_tactic_preflight_event,
    validate_tactic_preflight_artifact,
    write_tactic_preflight_artifact,
)


def _accepted(tactic: str = "move=> &m x.") -> dict:
    return build_tactic_preflight_artifact(
        proof_state={
            "status": "open",
            "goal_identity_required": True,
            "goal": {
                "state_kind": "open",
                "proof_candidate_closed": False,
                "active_goal_hash": "goal-identity",
            },
            "event_contract": {"ok": True},
            "consistency": {"ok": True},
        },
        result={
            "tactic": tactic,
            "accepted": True,
            "goal_after_closed": False,
            "goal_after_remaining": 2,
            "error_kind": "",
            "tool_error": False,
            "no_progress_predicted": False,
        },
        raw_report="accepted",
    )


def test_accepted_preflight_binds_exact_tactic() -> None:
    tactic = "move=> &m x."
    data = _accepted(tactic)

    assert validate_tactic_preflight_artifact(data).ok
    assert data["outcome_known"] is True
    assert data["runnable_evidence"]["exact_submit"] == {
        "intent": "commit_tactic",
        "payload": {"tactic": tactic},
    }


def test_rejected_transition_can_leave_authoritative_source_goal_open() -> None:
    data = _accepted()
    data["proof_state"]["status"] = "error"
    data["proof_state"]["latest_transition"] = {
        "kind": "error",
        "latest_error": "cannot infer module arguments",
    }

    assert validate_tactic_preflight_artifact(data).ok
    assert data["outcome_known"] is True


def test_runnable_preflight_fails_closed_without_each_goal_authority() -> None:
    mutations = (
        lambda state: state.update(goal_identity_required=False),
        lambda state: state["goal"].update(state_kind="unknown"),
        lambda state: state["goal"].update(proof_candidate_closed=True),
        lambda state: state["goal"].update(active_goal_hash=""),
        lambda state: state["event_contract"].update(ok=False),
        lambda state: state["consistency"].update(ok=False),
    )
    for mutate in mutations:
        data = _accepted()
        mutate(data["proof_state"])
        validation = validate_tactic_preflight_artifact(data)
        assert not validation.ok
        assert any("authoritatively open" in error for error in validation.errors)


def test_rejected_and_no_progress_preflights_are_not_runnable() -> None:
    for accepted, no_progress in ((False, False), (True, True)):
        data = build_tactic_preflight_artifact(
            proof_state={"status": "open"},
            result={
                "tactic": "skip.",
                "accepted": accepted,
                "goal_after_closed": False,
                "goal_after_remaining": 1,
                "tool_error": False,
                "no_progress_predicted": no_progress,
            },
        )
        assert validate_tactic_preflight_artifact(data).ok
        assert data["outcome_known"] is False
        assert data["runnable_evidence"] == {}


def test_preflight_schema_rejects_unknown_fields_and_unbound_evidence() -> None:
    data = _accepted()
    data["lookup_result"] = {"text": "retired"}
    data["tactic"] = "other."

    validation = validate_tactic_preflight_artifact(data)

    assert not validation.ok
    assert any("unknown field" in error for error in validation.errors)
    assert any("does not bind" in error for error in validation.errors)


def test_event_bound_reader_checks_hash_session_and_request(tmp_path: Path) -> None:
    session = tmp_path / "session"
    data = _accepted()
    payload = write_tactic_preflight_artifact(session, data)
    assert append_event(session, TACTIC_PREFLIGHT_EVENT_TYPE, payload)
    event = events_of_type(read_events(session), TACTIC_PREFLIGHT_EVENT_TYPE)[-1]

    matching = read_bound_tactic_preflight_event(
        session,
        event,
        expected_tactic=data["tactic"],
    )
    mismatching = read_bound_tactic_preflight_event(
        session,
        event,
        expected_tactic="other.",
    )

    assert matching.ok
    assert matching.data == data
    assert not mismatching.ok
    assert any("does not match" in error for error in mismatching.errors)


def test_event_bound_reader_rejects_tampered_artifact(tmp_path: Path) -> None:
    session = tmp_path / "session"
    data = _accepted()
    payload = write_tactic_preflight_artifact(session, data)
    assert append_event(session, TACTIC_PREFLIGHT_EVENT_TYPE, payload)
    event = events_of_type(read_events(session), TACTIC_PREFLIGHT_EVENT_TYPE)[-1]
    artifact = Path(payload["artifact"])
    tampered = dict(data)
    tampered["error_kind"] = "tampered"
    artifact.write_text(
        canonical_tactic_preflight_text(tampered) + "\n",
        encoding="utf-8",
    )

    bound = read_bound_tactic_preflight_event(session, event)

    assert not bound.ok
    assert any("artifact_hash mismatch" in error for error in bound.errors)


def test_artifact_body_contains_no_generic_view_or_recommendation_carrier(
    tmp_path: Path,
) -> None:
    data = _accepted()
    payload = write_tactic_preflight_artifact(tmp_path, data)
    body = json.loads(Path(payload["artifact"]).read_text(encoding="utf-8"))

    assert "guidance" not in body
    assert "recommendations" not in body
    assert "context_result" not in body
    assert "debug" not in body
