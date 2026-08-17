"""Event-bound declaration resources for one compiler state occurrence.

The current proof-state snapshot and declaration loading are separate facts.
This artifact binds loaded declarations to an already-produced compiler input
occurrence without producing a second state snapshot.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.easycrypt.ec_runtime_identity import EasyCryptRuntimeIdentity
from core.easycrypt.proof_state_compiler.contracts import (
    LoadedDeclaration,
    StateRef,
)
from core.easycrypt.session_artifact_io import (
    BoundJsonArtifactRead,
    read_bound_current_json_artifact_event,
    write_confined_text_artifact,
)
from core.easycrypt.session_compiler_input import validate_compiler_input
from core.easycrypt.session_events import record_authoritative_artifact_event


COMPILER_RESOURCE_LOAD_SCHEMA_VERSION = 1
COMPILER_RESOURCE_LOAD_KIND = "proof_state_compiler_resource_load"
COMPILER_RESOURCE_LOAD_EVENT = "compiler.resources.loaded"
COMPILER_RESOURCE_LOAD_SUBDIR = "compiler_resource_loads"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class CompilerResourceLoadValidation:
    errors: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.errors


def build_compiler_resource_load(
    *,
    base_compiler_input: dict[str, Any],
    request_id: str,
    source_snapshot_id: str,
    source_event_id: str,
    loaded_declarations: tuple[dict[str, Any], ...],
    resource_load_report: tuple[dict[str, Any], ...],
) -> dict[str, Any]:
    """Build resources tied to one immutable compiler-input occurrence."""

    base_validation = validate_compiler_input(base_compiler_input)
    if not base_validation.ok:
        raise ValueError(
            "resource load base compiler input: "
            + "; ".join(base_validation.errors)
        )
    if not request_id or not source_snapshot_id or not source_event_id:
        raise ValueError("compiler resource load requires request/event identity")
    data = {
        "schema_version": COMPILER_RESOURCE_LOAD_SCHEMA_VERSION,
        "kind": COMPILER_RESOURCE_LOAD_KIND,
        "ok": True,
        "request_id": request_id,
        "source_snapshot_id": source_snapshot_id,
        "source_event_id": source_event_id,
        "target": dict(base_compiler_input["target"]),
        "state": {
            key: base_compiler_input["state"][key]
            for key in (
                "session_id",
                "state_version",
                "goal_identity",
                "goal_identity_required",
                "committed_prefix_identity",
            )
        },
        "easycrypt_runtime": dict(base_compiler_input["easycrypt_runtime"]),
        "loaded_declarations": [dict(item) for item in loaded_declarations],
        "resource_load_report": [dict(item) for item in resource_load_report],
    }
    validation = validate_compiler_resource_load(data)
    if not validation.ok:
        raise ValueError(
            "compiler resource load contract: " + "; ".join(validation.errors)
        )
    return data


def validate_compiler_resource_load(
    data: dict[str, Any],
) -> CompilerResourceLoadValidation:
    if type(data) is not dict:
        return CompilerResourceLoadValidation(("resource load must be an object",))
    errors: list[str] = []
    expected_fields = {
        "schema_version",
        "kind",
        "ok",
        "request_id",
        "source_snapshot_id",
        "source_event_id",
        "target",
        "state",
        "easycrypt_runtime",
        "loaded_declarations",
        "resource_load_report",
    }
    unexpected = sorted(set(data) - expected_fields)
    if unexpected:
        errors.append("resource load has unexpected fields: " + ", ".join(unexpected))
    if data.get("schema_version") != COMPILER_RESOURCE_LOAD_SCHEMA_VERSION:
        errors.append("unsupported resource load schema_version")
    if data.get("kind") != COMPILER_RESOURCE_LOAD_KIND:
        errors.append("unsupported resource load kind")
    if data.get("ok") is not True:
        errors.append("resource load must report ok=true")
    for field in ("request_id", "source_snapshot_id", "source_event_id"):
        if type(data.get(field)) is not str or not data.get(field):
            errors.append(f"resource load requires {field}")

    target = data.get("target")
    if type(target) is not dict:
        errors.append("resource load target must be an object")
        target = {}
    for field in ("source_file", "lemma"):
        if type(target.get(field)) is not str or not target.get(field):
            errors.append(f"resource load target requires {field}")
    if not _SHA256_RE.fullmatch(str(target.get("source_sha256") or "")):
        errors.append("resource load target source_sha256 is invalid")

    state = data.get("state")
    if type(state) is not dict:
        errors.append("resource load state must be an object")
        state = {}
    try:
        StateRef(
            session_id=state.get("session_id"),
            state_version=state.get("state_version"),
            goal_identity=state.get("goal_identity"),
            goal_identity_required=state.get("goal_identity_required"),
            committed_prefix_identity=state.get("committed_prefix_identity"),
        )
    except (TypeError, ValueError) as exc:
        errors.append(f"resource load StateRef is invalid: {exc}")
    try:
        EasyCryptRuntimeIdentity.from_payload(data.get("easycrypt_runtime"))
    except ValueError as exc:
        errors.append(f"resource load runtime identity is invalid: {exc}")

    declarations = data.get("loaded_declarations")
    if type(declarations) is not list:
        errors.append("loaded_declarations must be a list")
        declarations = []
    identities: list[tuple[object, object]] = []
    for index, item in enumerate(declarations):
        if type(item) is not dict:
            errors.append(f"loaded declaration {index} must be an object")
            continue
        try:
            LoadedDeclaration(
                symbol=item.get("symbol"),
                source_ref=item.get("source_ref"),
                declaration_sha256=item.get("declaration_sha256"),
                declaration=item.get("declaration"),
            )
        except (TypeError, ValueError) as exc:
            errors.append(f"loaded declaration {index} is invalid: {exc}")
        identities.append((item.get("symbol"), item.get("source_ref")))
    if len(identities) != len(set(identities)):
        errors.append("resource load has duplicate declarations")
    errors.extend(_resource_report_errors(data.get("resource_load_report")))
    return CompilerResourceLoadValidation(tuple(errors))


def _resource_report_errors(value: object) -> list[str]:
    if type(value) is not list:
        return ["resource_load_report must be a list"]
    errors: list[str] = []
    request_ids: list[object] = []
    for index, item in enumerate(value):
        if type(item) is not dict:
            errors.append(f"resource load report {index} must be an object")
            continue
        for field in ("request_id", "producer_id", "query_kind", "status"):
            if type(item.get(field)) is not str or not item.get(field):
                errors.append(f"resource load report {index} requires {field}")
        query_kind = item.get("query_kind")
        if query_kind not in {
            "scope_member_declarations",
            "symbol_declarations",
        }:
            errors.append(f"resource load report {index} has unsupported query")
        if item.get("status") not in {"ok", "miss", "error"}:
            errors.append(f"resource load report {index} has unsupported status")
        count_fields: tuple[str, ...] = ()
        if query_kind == "scope_member_declarations":
            if type(item.get("scope")) is not str or not item.get("scope"):
                errors.append(f"resource load report {index} requires scope")
            terms = item.get("member_name_terms")
            if type(terms) is not list or not terms or any(
                type(term) is not str or not term for term in terms
            ):
                errors.append(
                    f"resource load report {index} requires member_name_terms"
                )
            count_fields = ("member_count", "matched_name_count")
        elif query_kind == "symbol_declarations":
            symbols = item.get("symbols")
            if type(symbols) is not list or not symbols or len(symbols) > 8 or any(
                type(symbol) is not str or not symbol for symbol in symbols
            ):
                errors.append(f"resource load report {index} requires symbols")
        for field in (*count_fields, "requested_count", "loaded_count", "elapsed_ms"):
            if type(item.get(field)) is not int or item.get(field, -1) < 0:
                errors.append(
                    f"resource load report {index} requires non-negative {field}"
                )
        if type(item.get("truncated")) is not bool:
            errors.append(f"resource load report {index} requires boolean truncated")
        loaded = item.get("loaded_count")
        requested = item.get("requested_count")
        matched = item.get("matched_name_count")
        members = item.get("member_count")
        if type(loaded) is int and type(requested) is int and loaded > requested:
            errors.append(f"resource load report {index} loaded_count exceeds request")
        if type(matched) is int and type(members) is int and matched > members:
            errors.append(f"resource load report {index} matched count exceeds members")
        if type(requested) is int and type(matched) is int and requested > matched:
            errors.append(f"resource load report {index} requested count exceeds matches")
        truncated = item.get("truncated")
        if type(matched) is int and type(requested) is int and type(truncated) is bool:
            if truncated != (matched > requested):
                errors.append(f"resource load report {index} truncated flag is inconsistent")
        request_ids.append(item.get("request_id"))
    if len(request_ids) != len(set(request_ids)):
        errors.append("resource load report has duplicate request IDs")
    return errors


def _event_payload_fields(
    data: dict[str, Any],
    *,
    artifact: str,
    artifact_hash: str,
    result_sha256: str,
) -> dict[str, Any]:
    validation = validate_compiler_resource_load(data)
    state = data.get("state") if isinstance(data.get("state"), dict) else {}
    return {
        "schema_version": int(data.get("schema_version") or 0),
        "ok": bool(data.get("ok")) and validation.ok,
        "request_id": str(data.get("request_id") or ""),
        "source_snapshot_id": str(data.get("source_snapshot_id") or ""),
        "source_event_id": str(data.get("source_event_id") or ""),
        "artifact": artifact,
        "artifact_hash": artifact_hash,
        "result_sha256": result_sha256,
        "session_id": str(state.get("session_id") or ""),
        "goal_identity": str(state.get("goal_identity") or ""),
        "goal_identity_required": bool(state.get("goal_identity_required")),
        "committed_prefix_identity": str(
            state.get("committed_prefix_identity") or ""
        ),
        "error_count": len(validation.errors),
        "loaded_declaration_count": len(data.get("loaded_declarations") or []),
        "resource_load_request_count": len(data.get("resource_load_report") or []),
    }


def write_compiler_resource_load_artifact(
    session_dir: str | Path,
    data: dict[str, Any],
) -> dict[str, Any]:
    validation = validate_compiler_resource_load(data)
    if not validation.ok:
        raise ValueError(
            "compiler resource load contract: " + "; ".join(validation.errors)
        )
    text = json.dumps(data, indent=2, sort_keys=True)
    artifact_hash = hashlib.sha1(text.encode("utf-8")).hexdigest()
    result_sha256 = hashlib.sha256(text.encode("utf-8")).hexdigest()
    artifact = write_confined_text_artifact(
        session_dir,
        subdir=COMPILER_RESOURCE_LOAD_SUBDIR,
        filename=f"compiler_resources_{artifact_hash[:16]}.json",
        text=text + "\n",
    )
    return _event_payload_fields(
        data,
        artifact=str(artifact),
        artifact_hash=artifact_hash,
        result_sha256=result_sha256,
    )


def record_compiler_resource_load(session: Any, data: dict[str, Any]) -> dict[str, Any]:
    return record_authoritative_artifact_event(
        session,
        COMPILER_RESOURCE_LOAD_EVENT,
        lambda: write_compiler_resource_load_artifact(session.dir, data),
        source="session_cli",
    )


def read_bound_compiler_resource_load_event(
    session_dir: str | Path,
    event: dict[str, Any],
) -> BoundJsonArtifactRead:
    expected_session = str(Path(session_dir).resolve())

    def _validate(
        data: dict[str, Any],
        payload: dict[str, Any],
        artifact_hash: str,
    ) -> tuple[list[str], list[str]]:
        errors = list(validate_compiler_resource_load(data).errors)
        text = json.dumps(data, indent=2, sort_keys=True)
        expected = _event_payload_fields(
            data,
            artifact=str(payload.get("artifact") or ""),
            artifact_hash=artifact_hash,
            result_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        )
        for key, value in expected.items():
            if payload.get(key) != value:
                errors.append(
                    f"{COMPILER_RESOURCE_LOAD_EVENT} {key} does not match artifact"
                )
        state = data.get("state") if isinstance(data.get("state"), dict) else {}
        if state.get("session_id") != expected_session:
            errors.append("compiler resource load session_id is not current")
        return errors, []

    return read_bound_current_json_artifact_event(
        session_dir,
        event,
        event_type=COMPILER_RESOURCE_LOAD_EVENT,
        subdir=COMPILER_RESOURCE_LOAD_SUBDIR,
        validate_binding=_validate,
    )


__all__ = [
    "COMPILER_RESOURCE_LOAD_EVENT",
    "COMPILER_RESOURCE_LOAD_KIND",
    "COMPILER_RESOURCE_LOAD_SCHEMA_VERSION",
    "build_compiler_resource_load",
    "read_bound_compiler_resource_load_event",
    "record_compiler_resource_load",
    "validate_compiler_resource_load",
]
