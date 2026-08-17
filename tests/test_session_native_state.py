"""Artifact and current-call authority for native typed-state snapshots."""

from __future__ import annotations

from pathlib import Path

from core.easycrypt.ec_runtime_identity import EasyCryptRuntimeIdentity
from core.easycrypt.native_semantics import NativeCompanionIdentity
from core.easycrypt.session_api import open_session
from core.easycrypt.session_events import append_event, read_events
from core.easycrypt.session_native_state import (
    read_bound_native_state_event,
    record_native_state_projection,
    validate_native_state_artifact,
)
from tests.helpers.builders import tool_called, tool_result
from workflow.proof_management.backend_actions import (
    AuthoritativeViewResolution,
    capture_authoritative_view_invocation,
    resolve_authoritative_view_invocation,
)
from workflow.proof_management.repl_session import ReplSessionManager


RUNTIME = EasyCryptRuntimeIdentity("r-test", "a" * 64)
COMPANION = NativeCompanionIdentity(
    2, "r-test", "b" * 64, "c" * 64, "d" * 64
)


def _projection() -> dict:
    return {
        "complete": True,
        "truncation_reasons": [],
        "node_count": 1,
        "open_goal_count": 1,
        "focused_goal": {
            "judgment_kind": "pure",
            "formula": {
                "kind": "true",
                "complete": True,
                "text": "true",
                "type": "bool",
                "children": [],
            },
            "programs": [],
            "procedures": [],
        },
        "local_declarations": [],
    }


def _data(session: Path) -> dict:
    return {
        "schema_version": 2,
        "kind": "easycrypt_native_state_projection",
        "ok": True,
        "projection_id": "projection-1",
        "request": {
            "request_id": "request-1",
            "max_nodes": 4096,
            "max_depth": 128,
        },
        "state": {
            "session_id": str(session.resolve()),
            "state_version": 4,
            "goal_identity": "goal-identity",
            "goal_identity_required": True,
            "committed_prefix_identity": "d" * 64,
        },
        "inputs": {
            "context_sha256": "e" * 64,
            "history_sha256": "f" * 64,
        },
        "easycrypt_runtime": RUNTIME.to_payload(),
        "native_companion": COMPANION.identity_payload(),
        "result": {
            "goal_before": "Current goal\n---\ntrue",
            "projection": _projection(),
            "elapsed_ms": 12,
        },
        "session_files_unchanged": True,
    }


def _session(tmp_path: Path) -> Path:
    session = tmp_path / "session"
    session.mkdir()
    assert append_event(session, "session.started", {
        "file": "/tmp/target.ec",
        "lemma": "target",
        "include_dirs": [],
        "discarded_tactic_count": 0,
        "restart_count": 1,
    })
    return session


def test_native_state_artifact_is_current_event_bound(tmp_path: Path) -> None:
    session = _session(tmp_path)
    data = _data(session)
    assert validate_native_state_artifact(data).ok

    record_native_state_projection(open_session(session), data)
    event = read_events(session)[-1]
    bound = read_bound_native_state_event(session, event)

    assert bound.ok
    assert bound.data == data


def test_native_state_backend_call_requires_one_produced_occurrence(
    tmp_path: Path,
) -> None:
    session = _session(tmp_path)
    command = [
        "python3",
        "core/easycrypt/session_cli.py",
        "-d",
        str(session),
        "-native-state-projection-json",
    ]
    boundary = capture_authoritative_view_invocation(session, command)
    assert boundary is not None
    tool_called(session, "native-state-projection", mutates=False)
    record_native_state_projection(open_session(session), _data(session))
    tool_result(session, "native-state-projection", mutates=False)

    resolution = resolve_authoritative_view_invocation(boundary, exit_code=0)

    assert resolution.error == ""
    assert resolution.payload is not None
    assert resolution.payload["kind"] == "easycrypt_native_state_projection"


def test_native_state_event_rejects_projection_summary_drift(
    tmp_path: Path,
) -> None:
    session = _session(tmp_path)
    record_native_state_projection(open_session(session), _data(session))
    event = read_events(session)[-1]
    event["payload"]["node_count"] = 999

    bound = read_bound_native_state_event(session, event)

    assert not bound.ok
    assert any("node_count" in error for error in bound.errors)


def test_native_state_completeness_cannot_disagree_with_truncation() -> None:
    data = _data(Path("/tmp/session"))
    data["result"]["projection"]["truncation_reasons"] = ["max_nodes"]

    validation = validate_native_state_artifact(data)

    assert not validation.ok
    assert any("completeness" in error for error in validation.errors)


def test_native_state_artifact_rejects_malformed_nested_typed_fact() -> None:
    data = _data(Path("/tmp/session"))
    data["result"]["projection"]["local_declarations"] = [{
        "index": 0,
        "name": "H",
        "kind": "hypothesis",
        "formula": {"kind": "true", "complete": True, "children": "not-a-list"},
    }]

    validation = validate_native_state_artifact(data)

    assert not validation.ok
    assert any("formula.text" in error for error in validation.errors)


def test_repl_native_state_gateway_preserves_manager_state(
    tmp_path: Path,
    monkeypatch,
) -> None:
    manager = ReplSessionManager(
        file_path="target.ec",
        lemma_name="target",
        include_dir="",
        session_tag="native-state-gateway",
        node_id="Tree-native-state",
        project_root=tmp_path,
    )
    payload = _data(tmp_path / ".ec_session_native-state-gateway")
    payload["state"]["state_version"] = 0
    payload["request"] = {
        "request_id": "gateway-request",
        "max_nodes": 512,
        "max_depth": 64,
    }

    def run_backend(label, args, *, actions, timeout, authoritative_resolutions):
        assert label == "native_state_projection"
        assert "-native-state-projection-json" in args
        actions.append({"label": label, "exit_code": 0})
        authoritative_resolutions.append(AuthoritativeViewResolution(
            required=True,
            payload=payload,
            artifact=Path("native-state.json"),
            event_id="event-1",
            event_sequence=1,
            event_payload={
                "projection_id": payload["projection_id"],
                "request_id": "gateway-request",
                "artifact": "native-state.json",
                "result_sha256": "1" * 64,
            },
        ))
        return payload

    monkeypatch.setattr(manager, "_run_backend", run_backend)

    result = manager.project_native_state(
        request_id="gateway-request",
        max_nodes=512,
        max_depth=64,
    )

    assert result["authority"]["event_type"] == "native.state.produced"
    assert result["history_unchanged"] is True
    assert result["state_version_before"] == result["state_version_after"] == 0
