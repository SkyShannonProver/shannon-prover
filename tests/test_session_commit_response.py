"""Tests for structured mutating-command CommitResponse contract."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

import sys
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from core.easycrypt.session_commit_response import (  # type: ignore  # noqa: E402
    COMMIT_RESPONSE_KIND,
    build_commit_response,
    validate_commit_response,
    write_commit_response_artifact,
)
from core.easycrypt.session_events import append_event  # type: ignore  # noqa: E402
from tests.helpers.builders import start_event  # noqa: E402

_start_event = start_event


def test_commit_response_builds_and_writes_artifact() -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        (d / "current.out").write_text(
            "[1|check]>\nCurrent goal\n----\nx = y\n[2|check]>\n",
            encoding="utf-8",
        )
        _start_event(d)
        response = build_commit_response(
            d,
            command="next",
            status="ok",
            attempted_tactics=["smt()."],
            accepted_count=1,
            agent_view_payload={
                "artifact": str(d / "proof_context_views" / "agent.json"),
                "view_hash": "a" * 40,
            },
            live_tool_name="next",
            ok=True,
        )

        assert response["kind"] == COMMIT_RESPONSE_KIND
        assert response["ok"] is True
        assert response["mutation"]["attempted_count"] == 1
        assert validate_commit_response(response).ok is True

        payload = write_commit_response_artifact(d, response)
        artifact = Path(payload["artifact"])
        assert artifact.exists()
        assert len(payload["response_hash"]) == 40
        assert payload["command"] == "next"
        assert payload["accepted_count"] == 1
        assert validate_commit_response(json.loads(artifact.read_text())).ok


def test_commit_response_validation_rejects_bad_counts() -> None:
    data = {
        "schema_version": 1,
        "kind": "commit_response",
        "ok": True,
        "command": "chain",
        "status": "ok",
        "proof_state": {},
        "latest_transition": {},
        "mutation": {
            "attempted_count": 1,
            "accepted_count": 2,
            "attempted_tactics": ["smt()."],
        },
        "agent_view": {},
        "notes": [],
        "errors": [],
        "debug": {},
    }
    validation = validate_commit_response(data)
    assert validation.ok is False
    assert any("cannot exceed" in err for err in validation.errors)


def _ok_current_out(d: Path) -> None:
    (d / "current.out").write_text(
        "[1|check]>\nCurrent goal\n----\nx = y\n[2|check]>\n", encoding="utf-8")


def test_crashed_probe_does_not_mislabel_next_commit() -> None:
    # A read-only probe whose handler raised left a dangling `tool.called(try)`
    # with no `tool.result`. In the live commit view that stale, harmless log entry
    # must NOT flip a SUCCESSFUL commit to ok=false ("event contract is not valid") —
    # the observed "probe accepted, commit rejected" mislabel.
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        _ok_current_out(d)
        _start_event(d)
        append_event(d, "tool.called", {"name": "try", "mutates_proof_state": False})
        append_event(d, "error.raised", {"phase": "cli_action", "action": "try"})
        # the live commit's own in-flight call (stripped as the live tool)
        append_event(d, "tool.called", {"name": "next", "mutates_proof_state": True})
        response = build_commit_response(
            d, command="next", status="ok", attempted_tactics=["trivial."],
            accepted_count=1, live_tool_name="next", ok=True)
        assert response["ok"] is True
        assert not any(e["code"] == "proof_state.event_contract"
                       for e in response["errors"])
        assert response["proof_state"]["event_contract"]["ok"] is True


def test_dangling_mutating_call_still_fails_closed() -> None:
    # A dangling MUTATING call (not the live tool) is genuine corruption and must
    # still fail closed — the fix only neutralizes read-only artifacts.
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        _ok_current_out(d)
        _start_event(d)
        append_event(d, "tool.called", {"name": "chain", "mutates_proof_state": True})
        append_event(d, "tool.called", {"name": "next", "mutates_proof_state": True})
        response = build_commit_response(
            d, command="next", status="ok", attempted_tactics=["x."],
            accepted_count=1, live_tool_name="next", ok=True)
        assert response["proof_state"]["event_contract"]["ok"] is False


def main() -> int:
    test_commit_response_builds_and_writes_artifact()
    test_commit_response_validation_rejects_bad_counts()
    print("PASS test_session_commit_response")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
