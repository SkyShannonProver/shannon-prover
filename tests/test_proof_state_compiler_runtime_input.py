"""Authority and typed-conversion tests for the fresh V2 runtime input."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from core.easycrypt.ec_runtime_identity import EasyCryptRuntimeIdentity
from core.easycrypt.session_api import open_session
from core.easycrypt.session_compiler_input import (
    build_compiler_input,
    read_bound_compiler_input_event,
    record_compiler_input,
    validate_compiler_input,
)
from core.easycrypt.session_compiler_resources import (
    build_compiler_resource_load,
    read_bound_compiler_resource_load_event,
    record_compiler_resource_load,
    validate_compiler_resource_load,
)
from core.easycrypt.session_events import append_event, read_events
from tests.helpers.builders import start_event, tool_called, tool_result
from workflow.proof_management.backend_actions import (
    capture_authoritative_view_invocation,
    resolve_authoritative_view_invocation,
)
from workflow.proof_state_compiler.input_gateway import (
    attach_compiler_resources,
    attach_native_state,
    runtime_compiler_input,
)
from tests.proof_state_compiler_test_support import (
    native_state,
    native_state_manager_result,
)


GOAL = """Current goal (remaining: 1)

x : int
------------------------------------------------------------------------
x = x
[7|check]>
"""

TEST_RUNTIME = EasyCryptRuntimeIdentity(
    build_id="test-easycrypt-build",
    binary_sha256="a" * 64,
)


def _build_compiler_input(session: Path, **kwargs: object) -> dict:
    return build_compiler_input(
        session,
        runtime_identity=TEST_RUNTIME,
        **kwargs,
    )


def _session(tmp_path: Path) -> tuple[Path, Path]:
    session = tmp_path / ".ec_session_compiler_input"
    session.mkdir()
    source = tmp_path / "target.ec"
    source.write_text("lemma target : true.\nproof. admit. qed.\n")
    (session / "session_meta.json").write_text(json.dumps({
        "file": str(source.resolve()),
        "lemma": "target",
    }))
    (session / "current.out").write_text(GOAL)
    (session / "history.ec").write_text("move=> x.\n")
    start_event(session)
    return session, source


def _append_candidate_close(session: Path, tactic: str = "trivial.") -> None:
    tool_called(session, "next")
    append_event(session, "tactic.submitted", {
        "tactic": tactic,
        "history_lines_before": 0,
        "line_count": 1,
    })
    append_event(session, "goal.changed", {
        "tactic": tactic,
        "goals_before": 1,
        "goals_after": 0,
        "no_more_goals": True,
        "async_check_close": False,
        "no_progress": False,
        "candidate_closed": True,
    })
    append_event(session, "tactic.result", {
        "tactic": tactic,
        "status": "ok",
        "history_committed": True,
        "goals_before": 1,
        "goals_after": 0,
        "candidate_closed": True,
    })
    append_event(session, "proof.candidate_closed", {
        "tactic": tactic,
        "goals_before": 1,
        "goals_after": 0,
        "no_more_goals": True,
        "async_check_close": False,
    })
    tool_result(session, "next")


def _append_qed_saved(session: Path) -> None:
    tool_called(session, "next")
    append_event(session, "tactic.submitted", {
        "tactic": "qed.",
        "history_lines_before": 1,
        "line_count": 1,
    })
    append_event(session, "tactic.result", {
        "tactic": "qed.",
        "status": "ok",
        "history_committed": True,
        "goals_before": 0,
        "goals_after": -1,
        "candidate_closed": False,
    })
    tool_result(session, "next")


def test_runtime_snapshot_is_narrow_hashed_and_self_consistent(
    tmp_path: Path,
) -> None:
    session, source = _session(tmp_path)

    data = _build_compiler_input(session)

    assert validate_compiler_input(data).ok
    assert data["target"] == {
        "source_file": str(source.resolve()),
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "lemma": "target",
    }
    assert data["state"]["goal_lines"] == GOAL.splitlines()
    assert data["state"]["goal_identity_required"] is True
    assert len(data["state"]["committed_prefix_identity"]) == 64
    assert "workspace" not in data
    assert "panel" not in data
    assert "loaded_declarations" not in data
    assert "resource_load_report" not in data
    assert data["easycrypt_runtime"] == TEST_RUNTIME.to_payload()
    assert "verifier_scope" not in data
    assert "program_snapshot" not in data


@pytest.mark.parametrize("schema_version", [3.0, True])
def test_runtime_snapshot_rejects_noninteger_schema_aliases(
    tmp_path: Path,
    schema_version: object,
) -> None:
    session, _ = _session(tmp_path)
    data = _build_compiler_input(session)
    data["schema_version"] = schema_version

    validation = validate_compiler_input(data)

    assert not validation.ok
    assert "unsupported compiler input schema_version" in validation.errors


@pytest.mark.parametrize("legacy_field", ["verifier_scope", "program_snapshot"])
def test_runtime_snapshot_rejects_removed_legacy_semantic_fields(
    tmp_path: Path,
    legacy_field: str,
) -> None:
    session, _ = _session(tmp_path)
    data = _build_compiler_input(session)
    data[legacy_field] = {}

    validation = validate_compiler_input(data)

    assert not validation.ok
    assert any("unexpected fields" in error for error in validation.errors)


def test_runtime_snapshot_uses_current_candidate_close_event_before_qed(
    tmp_path: Path,
) -> None:
    session, _ = _session(tmp_path)
    (session / "current.out").write_text(
        "No more goals\n[8|check]>\n",
        encoding="utf-8",
    )
    (session / "history.ec").write_text("trivial.\n", encoding="utf-8")
    _append_candidate_close(session)

    data = _build_compiler_input(session)

    assert validate_compiler_input(data).ok
    assert data["state"]["closed"] is True
    assert data["state"]["goal_identity_required"] is False
    assert data["state"]["goal_identity"] == ""
    assert data["state"]["goal_lines"] == []


def test_runtime_snapshot_uses_qed_saved_event_when_daemon_output_is_bare(
    tmp_path: Path,
) -> None:
    session, _ = _session(tmp_path)
    (session / "current.out").write_text("[9|check]>\n", encoding="utf-8")
    (session / "history.ec").write_text(
        "trivial.\nqed.\n",
        encoding="utf-8",
    )
    _append_candidate_close(session)
    _append_qed_saved(session)

    data = _build_compiler_input(session)

    assert validate_compiler_input(data).ok
    assert data["state"]["closed"] is True
    assert data["state"]["goal_identity_required"] is False
    assert data["state"]["goal_identity"] == ""
    assert data["state"]["goal_lines"] == []


def test_runtime_snapshot_does_not_reuse_stale_candidate_close_event(
    tmp_path: Path,
) -> None:
    session, _ = _session(tmp_path)
    _append_candidate_close(session)
    tool_called(session, "next")
    append_event(session, "tactic.submitted", {
        "tactic": "move=> x.",
        "history_lines_before": 1,
        "line_count": 1,
    })
    append_event(session, "tactic.result", {
        "tactic": "move=> x.",
        "status": "ok",
        "history_committed": True,
        "goals_before": 1,
        "goals_after": 1,
        "candidate_closed": False,
    })
    tool_result(session, "next")

    data = _build_compiler_input(session)

    assert validate_compiler_input(data).ok
    assert data["state"]["closed"] is False
    assert data["state"]["goal_identity_required"] is True
    assert data["state"]["goal_identity"]


def test_compiler_input_is_read_only_through_one_current_call_event(
    tmp_path: Path,
) -> None:
    session, _ = _session(tmp_path)
    command = [
        "python3",
        "core/easycrypt/session_cli.py",
        "-d",
        str(session),
        "-compiler-input-v2",
    ]
    boundary = capture_authoritative_view_invocation(session, command)
    assert boundary is not None
    tool_called(session, "compiler-input-v2", mutates=False)
    record_compiler_input(open_session(session), _build_compiler_input(session))
    tool_result(session, "compiler-input-v2", mutates=False)

    resolution = resolve_authoritative_view_invocation(boundary, exit_code=0)

    assert resolution.error == ""
    assert resolution.payload is not None
    assert resolution.payload["kind"] == "proof_state_compiler_input"
    assert (session / "history.ec").read_text() == "move=> x.\n"


def test_event_binding_rejects_artifact_payload_drift(tmp_path: Path) -> None:
    session, _ = _session(tmp_path)
    record_compiler_input(open_session(session), _build_compiler_input(session))
    event = read_events(session)[-1]
    event["payload"]["goal_identity"] = "forged"

    binding = read_bound_compiler_input_event(session, event)

    assert not binding.ok
    assert any("goal_identity" in error for error in binding.errors)


def test_typed_boundary_rechecks_source_hash_before_compilation(
    tmp_path: Path,
) -> None:
    session, source = _session(tmp_path)
    record_compiler_input(open_session(session), _build_compiler_input(session))
    event = read_events(session)[-1]
    binding = read_bound_compiler_input_event(session, event)
    assert binding.ok and binding.data is not None
    manager_result = {
        "snapshot": binding.data,
        "authority": {
            "event_type": "compiler.input.produced",
            "event_id": event["event_id"],
            "event_sequence": 1,
            "artifact_ref": event["payload"]["artifact"],
            "artifact_sha256": event["payload"]["snapshot_sha256"],
        },
    }

    live = runtime_compiler_input(manager_result)
    assert live.snapshot.provenance.authoritative
    assert live.environment.source_units[0].text == source.read_text()
    assert live.environment.easycrypt_runtime == TEST_RUNTIME

    source.write_text("lemma target : false.\nproof. admit. qed.\n")
    with pytest.raises(ValueError, match="source changed"):
        runtime_compiler_input(manager_result)


def test_state_input_rejects_resource_payload_fields(
    tmp_path: Path,
) -> None:
    session, _ = _session(tmp_path)
    data = _build_compiler_input(session)
    data["loaded_declarations"] = []

    validation = validate_compiler_input(data)

    assert not validation.ok
    assert any("unexpected fields" in error for error in validation.errors)


def test_resource_occurrence_preserves_hash_bound_loaded_declarations(
    tmp_path: Path,
) -> None:
    session, _ = _session(tmp_path)
    base = _build_compiler_input(session)
    declaration = "lemma Loaded.L : forall &m, Pr[G.main() @ &m : res] <= 1%r."
    loaded = ({
        "symbol": "Loaded.L",
        "source_ref": "compiler.resources.loaded:resource-event#declaration",
        "declaration_sha256": hashlib.sha256(declaration.encode()).hexdigest(),
        "declaration": declaration,
    },)
    report = ({
        "request_id": "symbols:test",
        "producer_id": "test.symbols",
        "query_kind": "symbol_declarations",
        "status": "ok",
        "symbols": ["Loaded.L"],
        "requested_count": 1,
        "loaded_count": 1,
        "truncated": False,
        "elapsed_ms": 4,
    },)
    data = build_compiler_resource_load(
        base_compiler_input=base,
        request_id="resource-request",
        source_snapshot_id=base["snapshot_id"],
        source_event_id="compiler-input-event",
        loaded_declarations=loaded,
        resource_load_report=report,
    )
    record_compiler_resource_load(open_session(session), data)
    event = read_events(session)[-1]
    binding = read_bound_compiler_resource_load_event(session, event)
    assert binding.ok and binding.data is not None
    assert binding.data["source_snapshot_id"] == base["snapshot_id"]
    assert binding.data["loaded_declarations"][0]["symbol"] == "Loaded.L"


def test_resource_occurrence_attaches_without_replacing_state_provenance(
    tmp_path: Path,
) -> None:
    session, _ = _session(tmp_path)
    base = _build_compiler_input(session)
    record_compiler_input(open_session(session), base)
    input_event = read_events(session)[-1]
    input_binding = read_bound_compiler_input_event(session, input_event)
    assert input_binding.ok and input_binding.data is not None
    ordinary = runtime_compiler_input({
        "snapshot": input_binding.data,
        "authority": {
            "event_type": "compiler.input.produced",
            "event_id": input_event["event_id"],
            "event_sequence": 1,
            "artifact_ref": input_event["payload"]["artifact"],
            "artifact_sha256": input_event["payload"]["snapshot_sha256"],
        },
    })
    live = attach_native_state(
        ordinary,
        native_state_manager_result(
            native_state(ordinary.snapshot.state_ref),
            TEST_RUNTIME,
            goal_before=GOAL,
        ),
        native_state_request_id="native-test-request",
    )
    declaration = "lemma Loaded.L : true."
    resource = build_compiler_resource_load(
        base_compiler_input=base,
        request_id="resource-request",
        source_snapshot_id=base["snapshot_id"],
        source_event_id=input_event["event_id"],
        loaded_declarations=({
            "symbol": "Loaded.L",
            "source_ref": "compiler.resources.loaded:test#declaration",
            "declaration_sha256": hashlib.sha256(
                declaration.encode()
            ).hexdigest(),
            "declaration": declaration,
        },),
        resource_load_report=({
            "request_id": "symbols:test",
            "producer_id": "test.symbols",
            "query_kind": "symbol_declarations",
            "status": "ok",
            "symbols": ["Loaded.L"],
            "requested_count": 1,
            "loaded_count": 1,
            "truncated": False,
            "elapsed_ms": 1,
        },),
    )
    record_compiler_resource_load(open_session(session), resource)
    resource_event = read_events(session)[-1]
    resource_binding = read_bound_compiler_resource_load_event(
        session, resource_event
    )
    assert resource_binding.ok and resource_binding.data is not None
    enriched = attach_compiler_resources(
        live,
        {
            "result": resource_binding.data,
            "authority": {
                "event_type": "compiler.resources.loaded",
                "event_id": resource_event["event_id"],
                "event_sequence": 2,
                "artifact_ref": resource_event["payload"]["artifact"],
                "artifact_sha256": resource_event["payload"]["result_sha256"],
            },
            "history_unchanged": True,
            "state_version_before": ordinary.snapshot.state_ref.state_version,
            "state_version_after": ordinary.snapshot.state_ref.state_version,
        },
        expected_request_id="resource-request",
    )

    assert enriched.snapshot.provenance == live.snapshot.provenance
    assert enriched.source_snapshot_id == live.source_snapshot_id
    assert enriched.environment.loaded_declarations[0].symbol == "Loaded.L"


def test_resource_contract_accepts_bounded_exact_symbol_load_report(
    tmp_path: Path,
) -> None:
    session, _ = _session(tmp_path)
    base = _build_compiler_input(session)
    report = ({
        "request_id": "symbols:test",
        "producer_id": "test.symbols",
        "query_kind": "symbol_declarations",
        "status": "ok",
        "symbols": ["Wrong.dword_ll", "dword_ll"],
        "requested_count": 2,
        "loaded_count": 0,
        "truncated": False,
        "elapsed_ms": 4,
    },)
    data = build_compiler_resource_load(
        base_compiler_input=base,
        request_id="resource-request",
        source_snapshot_id=base["snapshot_id"],
        source_event_id="compiler-input-event",
        loaded_declarations=(),
        resource_load_report=report,
    )

    assert validate_compiler_resource_load(data).ok
