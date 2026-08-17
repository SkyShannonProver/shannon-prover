"""Manager-internal EasyCrypt/compiler gateway commands.

These are the only read-only semantic commands owned by the proof-state
compiler runtime.  They emit event-bound artifacts and never build the
retired Python proof-analysis or rich panel pipeline.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def handle_compiler_input_v2(session, args) -> int:
    from core.easycrypt.session_compiler_input import (
        build_compiler_input,
        record_compiler_input,
    )

    data = build_compiler_input(
        session.dir,
        manager_state_version=args.manager_state_version,
    )
    record_compiler_input(session, data)
    sys.stdout.write(json.dumps({
        "schema_version": 1,
        "kind": "proof_state_compiler_input_recorded",
        "snapshot_id": data["snapshot_id"],
    }, sort_keys=True) + "\n")
    return 0


def handle_compiler_resource_load_v2(session, args) -> int:
    from core.easycrypt.compiler_resource_loader import (
        load_requested_declarations,
        parse_runtime_declaration_requests,
    )
    from core.easycrypt.session_compiler_input import build_compiler_input
    from core.easycrypt.session_compiler_resources import (
        build_compiler_resource_load,
        record_compiler_resource_load,
    )

    request = json.loads(args.compiler_resource_load_request_json or "{}")
    if type(request) is not dict:
        raise ValueError("compiler resource load request must be an object")
    request_id = str(request.get("request_id") or "")
    source_snapshot_id = str(request.get("source_snapshot_id") or "")
    source_event_id = str(request.get("source_event_id") or "")
    expected_state = request.get("expected_state")
    if type(expected_state) is not dict:
        raise ValueError("compiler resource load expected_state is missing")
    requests_value = request.get("requests")
    requests = parse_runtime_declaration_requests(requests_value)
    if not requests:
        raise ValueError("compiler resource load requires at least one request")

    base = build_compiler_input(
        session.dir,
        manager_state_version=args.manager_state_version,
        live_tool_name="compiler-resource-load-v2",
    )
    observed_state = {
        key: base["state"][key]
        for key in (
            "session_id",
            "state_version",
            "goal_identity",
            "goal_identity_required",
            "committed_prefix_identity",
        )
    }
    if observed_state != expected_state:
        raise ValueError("compiler resource load StateRef drifted")
    context_file = _active_context_file(session)
    if context_file is None:
        raise ValueError("compiler declaration loading requires an active context file")
    loaded = load_requested_declarations(
        requests,
        context_file=context_file,
        include_dirs=tuple(
            Path(value)
            for value in session._include_dirs
            if Path(value).is_dir()
        ),
    )
    data = build_compiler_resource_load(
        base_compiler_input=base,
        request_id=request_id,
        source_snapshot_id=source_snapshot_id,
        source_event_id=source_event_id,
        loaded_declarations=loaded.declarations,
        resource_load_report=loaded.report,
    )
    record_compiler_resource_load(session, data)
    sys.stdout.write(json.dumps({
        "schema_version": 1,
        "kind": "proof_state_compiler_resource_load_recorded",
        "request_id": request_id,
        "source_snapshot_id": source_snapshot_id,
        "loaded_declaration_count": len(loaded.declarations),
        "resource_load_request_count": len(loaded.report),
    }, sort_keys=True) + "\n")
    return 0


def handle_native_semantic_batch_json(session, args) -> int:
    from core.easycrypt.session_native_semantics import (
        build_native_semantic_batch_result,
        record_native_semantic_batch_result,
    )

    request = json.loads(args.native_semantic_batch_request_json or "{}")
    if type(request) is not dict:
        raise ValueError("native semantic batch request must be an object")
    members = request.get("members")
    if type(members) is not list or any(type(item) is not dict for item in members):
        raise ValueError("native semantic batch members must be objects")
    data = build_native_semantic_batch_result(
        session.dir,
        manager_state_version=args.manager_state_version,
        batch_id=str(request.get("batch_id") or ""),
        requests=tuple(dict(item) for item in members),
        include_dirs=tuple(Path(value) for value in session._include_dirs),
    )
    record_native_semantic_batch_result(session, data)
    sys.stdout.write(json.dumps({
        "schema_version": 1,
        "kind": "native_semantic_batch_recorded",
        "query_id": data["query_id"],
        "batch_id": data["request"]["batch_id"],
        "request_count": len(data["request"]["members"]),
    }, sort_keys=True) + "\n")
    return 0


def handle_native_state_projection_json(session, args) -> int:
    from core.easycrypt.session_native_state import (
        build_native_state_projection,
        record_native_state_projection,
    )

    request = json.loads(args.native_state_projection_request_json or "{}")
    if type(request) is not dict:
        raise ValueError("native state projection request must be an object")
    data = build_native_state_projection(
        session.dir,
        manager_state_version=args.manager_state_version,
        request_id=str(request.get("request_id") or ""),
        include_dirs=tuple(Path(value) for value in session._include_dirs),
        max_nodes=request.get("max_nodes", 4096),
        max_depth=request.get("max_depth", 128),
    )
    record_native_state_projection(session, data)
    projection = data["result"]["projection"]
    sys.stdout.write(json.dumps({
        "schema_version": 1,
        "kind": "native_proof_state_projection_recorded",
        "projection_id": data["projection_id"],
        "request_id": data["request"]["request_id"],
        "complete": projection["complete"],
        "node_count": projection["node_count"],
    }, sort_keys=True) + "\n")
    return 0


def _active_context_file(session) -> Path | None:
    extracted = sorted(session.dir.glob("extracted_*.ec"))
    if extracted:
        return extracted[0]
    context = session.dir / "context.ec"
    return context if context.exists() else None
