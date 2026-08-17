"""Artifact and event authority for native semantic results."""

from __future__ import annotations

from pathlib import Path

from core.easycrypt.ec_runtime_identity import EasyCryptRuntimeIdentity
from core.easycrypt.native_semantics import NativeCompanionIdentity
from core.easycrypt.session_api import open_session
from core.easycrypt.session_events import append_event, read_events
from core.easycrypt.session_native_semantics import (
    native_semantic_batch_event_payload_fields,
    read_bound_native_semantic_batch_event,
    record_native_semantic_batch_result,
    validate_native_semantic_batch_result,
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


def _data(session: Path) -> dict:
    return {
        "schema_version": 17,
        "kind": "easycrypt_native_semantic_batch_result",
        "ok": True,
        "query_id": "query-1",
        "request": {
            "batch_id": "batch-1",
            "members": [{
                "request_id": "request-1",
                "evaluation_prefix": [],
                "query_kind": "proof_term_elaboration",
                "payload": {
                    "operation": "apply",
                    "application_term": "trueI _",
                },
            }],
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
            "members": [{
                "request_id": "request-1",
                "evaluation_prefix": [],
                "query_kind": "proof_term_elaboration",
                "payload": {
                    "operation": "apply",
                    "application_term": "trueI _",
                },
                "status": "rejected",
                "result_formula": "",
                "descriptor": {},
                "structured_error": {
                    "code": "not_functional",
                    "message": "too many arguments",
                },
                "elapsed_ms": 3,
            }],
            "cache_state": "warm",
            "build_elapsed_ms": 1,
            "execution_elapsed_ms": 10,
            "elapsed_ms": 12,
        },
        "session_files_unchanged": True,
    }


def _accepted_data(session: Path) -> dict:
    data = _data(session)
    data["request"]["members"][0]["payload"]["application_term"] = "trueI"
    data["result"] = {
        "goal_before": "Current goal\n---\ntrue",
        "members": [{
            "request_id": "request-1",
            "evaluation_prefix": [],
            "query_kind": "proof_term_elaboration",
            "payload": {
                "operation": "apply",
                "application_term": "trueI",
            },
            "status": "accepted",
            "result_formula": "true",
            "descriptor": {
                "resolved_head": {
                    "kind": "global",
                    "identity": "Core.trueI",
                    "type_arguments": [],
                },
                "input_mode": "implicit",
                "input_arguments": [],
                "explicit_hole_count": 0,
                "implicit_argument_count": 0,
                "arguments": [],
                "can_concretize": True,
                "residual_proof_premises": [],
                "result": {"kind": "true", "text": "true", "type": "bool"},
                "result_convertible_to_current_goal": True,
            },
            "structured_error": {},
            "elapsed_ms": 3,
        }],
        "cache_state": "warm",
        "build_elapsed_ms": 1,
        "execution_elapsed_ms": 10,
        "elapsed_ms": 12,
    }
    return data


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


def test_native_semantic_artifact_is_current_event_bound(tmp_path: Path) -> None:
    session = _session(tmp_path)
    data = _data(session)
    assert validate_native_semantic_batch_result(data).ok

    record_native_semantic_batch_result(open_session(session), data)
    event = read_events(session)[-1]
    bound = read_bound_native_semantic_batch_event(session, event)

    assert bound.ok
    assert bound.data == data


def test_native_semantic_artifact_preserves_accepted_descriptor(
    tmp_path: Path,
) -> None:
    session = _session(tmp_path)
    data = _accepted_data(session)

    assert validate_native_semantic_batch_result(data).ok
    record_native_semantic_batch_result(open_session(session), data)
    event = read_events(session)[-1]
    bound = read_bound_native_semantic_batch_event(session, event)

    assert bound.ok
    assert bound.data["result"]["members"][0]["descriptor"]["resolved_head"] == {
        "kind": "global",
        "identity": "Core.trueI",
        "type_arguments": [],
    }


def test_native_semantic_artifact_preserves_typed_formula_boundary(
    tmp_path: Path,
) -> None:
    session = _session(tmp_path)
    data = _accepted_data(session)
    result = data["result"]["members"][0]["descriptor"]["result"]
    result["boundary"] = {
        "role": "relation_left_probability",
        "procedure_identity": "Game(Current).main",
        "module": {
            "term": "Game(Current)",
            "top_kind": "concrete",
            "top_identity": "Game",
            "arguments": [{
                "term": "Current",
                "top_kind": "local",
                "top_identity": "Current",
                "arguments": [],
            }],
        },
    }

    assert validate_native_semantic_batch_result(data).ok
    record_native_semantic_batch_result(open_session(session), data)
    event = read_events(session)[-1]
    bound = read_bound_native_semantic_batch_event(session, event)

    assert bound.ok
    assert (
        bound.data["result"]["members"][0]["descriptor"]["result"]
        ["boundary"]["module"]["arguments"][0]["term"]
        == "Current"
    )


def test_native_semantic_validation_rejects_invalid_formula_boundary(
    tmp_path: Path,
) -> None:
    data = _accepted_data(_session(tmp_path))
    data["result"]["members"][0]["descriptor"]["result"]["boundary"] = {
        "role": "relation_left_probability",
        "procedure_identity": "Game(Current).main",
        "module": {
            "term": "",
            "top_kind": "concrete",
            "top_identity": "Game",
            "arguments": [],
        },
    }

    validation = validate_native_semantic_batch_result(data)

    assert not validation.ok
    assert any("descriptor is invalid" in error for error in validation.errors)


def test_native_semantic_validation_rejects_descriptor_kind_drift(
    tmp_path: Path,
) -> None:
    data = _accepted_data(_session(tmp_path))
    data["result"]["members"][0]["descriptor"]["result"]["kind"] = 7

    validation = validate_native_semantic_batch_result(data)

    assert not validation.ok
    assert any("descriptor is invalid" in error for error in validation.errors)


def test_invalid_batch_member_is_reported_without_breaking_event_validation(
    tmp_path: Path,
) -> None:
    data = _data(_session(tmp_path))
    data["result"]["members"] = ["not-an-object"]

    fields = native_semantic_batch_event_payload_fields(
        data,
        artifact="native_semantic_batches/bad.json",
        artifact_hash="1" * 40,
        result_sha256="2" * 64,
    )

    assert fields["ok"] is False
    assert fields["request_count"] == 1
    assert fields["accepted_count"] == 0
    assert fields["rejected_count"] == 0
    assert fields["error_count"] > 0


def test_native_semantic_backend_call_requires_one_produced_occurrence(
    tmp_path: Path,
) -> None:
    session = _session(tmp_path)
    command = [
        "python3",
        "core/easycrypt/session_cli.py",
        "-d",
        str(session),
        "-native-semantic-batch-json",
    ]
    boundary = capture_authoritative_view_invocation(session, command)
    assert boundary is not None
    tool_called(session, "native-semantic-batch", mutates=False)
    record_native_semantic_batch_result(open_session(session), _data(session))
    tool_result(session, "native-semantic-batch", mutates=False)

    resolution = resolve_authoritative_view_invocation(boundary, exit_code=0)

    assert resolution.error == ""
    assert resolution.payload is not None
    assert resolution.payload["kind"] == "easycrypt_native_semantic_batch_result"


def test_native_semantic_event_rejects_runtime_identity_drift(
    tmp_path: Path,
) -> None:
    session = _session(tmp_path)
    data = _data(session)
    record_native_semantic_batch_result(open_session(session), data)
    event = read_events(session)[-1]
    event["payload"]["easycrypt_runtime_identity_sha256"] = "0" * 64

    bound = read_bound_native_semantic_batch_event(session, event)

    assert not bound.ok
    assert any("runtime_identity" in error for error in bound.errors)


def test_repl_native_semantic_gateway_uses_project_root_session_identity(
    tmp_path: Path,
    monkeypatch,
) -> None:
    manager = ReplSessionManager(
        file_path="target.ec",
        lemma_name="target",
        include_dir="",
        session_tag="native-semantic-gateway",
        node_id="Tree-native-semantic",
        project_root=tmp_path,
    )
    payload = _data(tmp_path / ".ec_session_native-semantic-gateway")
    payload["state"]["state_version"] = 0
    payload["request"] = {
        "batch_id": "gateway-batch",
        "members": [{
            "request_id": "gateway-request",
            "evaluation_prefix": [],
            "query_kind": "proof_term_elaboration",
            "payload": {
                "operation": "apply",
                "application_term": "trueI _",
            },
        }],
    }
    payload["result"]["members"][0]["request_id"] = "gateway-request"

    def run_backend(label, args, *, actions, timeout, authoritative_resolutions):
        assert label == "native_semantic_batch"
        actions.append({"label": label, "exit_code": 0})
        authoritative_resolutions.append(AuthoritativeViewResolution(
            required=True,
            payload=payload,
            artifact=Path("native-semantic.json"),
            event_id="event-1",
            event_sequence=1,
            event_payload={
                "query_id": payload["query_id"],
                "batch_id": "gateway-batch",
                "request_count": 1,
                "artifact": "native-semantic.json",
                "result_sha256": "1" * 64,
            },
        ))
        return payload

    monkeypatch.setattr(manager, "_run_backend", run_backend)

    result = manager.execute_native_semantic_batch(
        batch_id="gateway-batch",
        requests=({
            "request_id": "gateway-request",
            "evaluation_prefix": [],
            "query_kind": "proof_term_elaboration",
            "payload": {
                "operation": "apply",
                "application_term": "trueI _",
            },
        },),
    )

    assert result["authority"]["event_type"] == "native.semantic.batch.produced"
    assert result["history_unchanged"] is True
    assert result["state_version_before"] == result["state_version_after"] == 0
