"""Event-bound artifact for one native EasyCrypt typed-state projection."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.easycrypt.committed_history import (
    committed_prefix_identity,
    history_path,
    read_committed_tactics,
)
from core.easycrypt.ec_runtime_identity import (
    EasyCryptRuntimeIdentity,
    verified_session_runtime_identity,
)
from core.easycrypt.native_semantics import (
    NativeCompanionIdentity,
    NativeStateProjectionRequest,
    run_native_state_projection,
    validate_native_projection,
)
from core.easycrypt.native_semantics.state_projection_adapter import (
    DEFAULT_MAX_DEPTH,
    DEFAULT_MAX_NODES,
)
from core.easycrypt.session.session_artifact_io import (
    BoundJsonArtifactRead,
    read_bound_current_json_artifact_event,
    write_confined_text_artifact,
)
from core.easycrypt.session.session_events import record_authoritative_artifact_event
from core.easycrypt.session.session_projection import read_proof_state_projection


NATIVE_STATE_SCHEMA_VERSION = 2
NATIVE_STATE_KIND = "easycrypt_native_state_projection"
NATIVE_STATE_EVENT = "native.state.produced"
NATIVE_STATE_SUBDIR = "native_state_projections"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class NativeStateValidation:
    errors: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.errors


def build_native_state_projection(
    session_dir: str | Path,
    *,
    manager_state_version: int,
    request_id: str,
    include_dirs: tuple[Path, ...],
    max_nodes: int = DEFAULT_MAX_NODES,
    max_depth: int = DEFAULT_MAX_DEPTH,
    timeout: int = 30,
) -> dict[str, Any]:
    """Replay and project typed state without mutating the live session."""

    path = Path(session_dir).resolve()
    if type(manager_state_version) is not int or manager_state_version < 0:
        raise ValueError("native state query requires manager state version")
    projection = read_proof_state_projection(
        path,
        live_tool_name="native-state-projection",
    )
    if not projection.events.ok or not projection.consistency.ok:
        raise ValueError("native state query requires consistent session state")
    if not projection.goal_identity_required:
        raise ValueError("native state query requires an open proof goal")
    goal_identity = projection.goal.active_goal_hash
    if not goal_identity:
        raise ValueError("native state query requires canonical goal identity")
    context = path / "context.ec"
    history = history_path(path)
    context_sha256 = _sha256_file(context)
    history_sha256 = _sha256_file(history)
    prefix_identity = committed_prefix_identity(
        tuple(read_committed_tactics(path))
    )
    runtime_identity = verified_session_runtime_identity(path)
    request = NativeStateProjectionRequest(
        request_id=request_id,
        context_file=context,
        history_file=history,
        include_dirs=include_dirs,
        expected_goal_identity=goal_identity,
        expected_context_sha256=context_sha256,
        expected_history_sha256=history_sha256,
        max_nodes=max_nodes,
        max_depth=max_depth,
    )
    result = run_native_state_projection(
        request,
        runtime_identity=runtime_identity,
        timeout=timeout,
    )
    data = {
        "schema_version": NATIVE_STATE_SCHEMA_VERSION,
        "kind": NATIVE_STATE_KIND,
        "ok": True,
        "projection_id": str(uuid.uuid4()),
        "request": {
            "request_id": request.request_id,
            "max_nodes": request.max_nodes,
            "max_depth": request.max_depth,
        },
        "state": {
            "session_id": str(path),
            "state_version": manager_state_version,
            "goal_identity": goal_identity,
            "goal_identity_required": True,
            "committed_prefix_identity": prefix_identity,
        },
        "inputs": {
            "context_sha256": context_sha256,
            "history_sha256": history_sha256,
        },
        "easycrypt_runtime": runtime_identity.to_payload(),
        "native_companion": result.companion_identity.identity_payload(),
        "result": {
            "goal_before": result.goal_before,
            "projection": result.projection,
            "elapsed_ms": result.elapsed_ms,
        },
        "session_files_unchanged": True,
    }
    validation = validate_native_state_artifact(data)
    if not validation.ok:
        raise ValueError("native state contract: " + "; ".join(validation.errors))
    return data


def validate_native_state_artifact(data: dict[str, Any]) -> NativeStateValidation:
    errors: list[str] = []
    if type(data) is not dict:
        return NativeStateValidation(("native state result must be an object",))
    if type(data.get("schema_version")) is not int or data.get(
        "schema_version"
    ) != NATIVE_STATE_SCHEMA_VERSION:
        errors.append("unsupported native state schema_version")
    if data.get("kind") != NATIVE_STATE_KIND or data.get("ok") is not True:
        errors.append("native state kind/ok is invalid")
    if type(data.get("projection_id")) is not str or not data.get("projection_id"):
        errors.append("native state result requires projection_id")
    request = data.get("request")
    if type(request) is not dict:
        errors.append("native state request must be an object")
        request = {}
    if type(request.get("request_id")) is not str or not request.get("request_id"):
        errors.append("native state request requires request_id")
    max_nodes = request.get("max_nodes")
    max_depth = request.get("max_depth")
    if type(max_nodes) is not int or not 64 <= max_nodes <= 100000:
        errors.append("native state max_nodes is invalid")
    if type(max_depth) is not int or not 8 <= max_depth <= 512:
        errors.append("native state max_depth is invalid")
    state = data.get("state")
    if type(state) is not dict:
        errors.append("native state state must be an object")
        state = {}
    if type(state.get("session_id")) is not str or not state.get("session_id"):
        errors.append("native state requires session_id")
    if type(state.get("state_version")) is not int or state.get(
        "state_version", -1
    ) < 0:
        errors.append("native state state_version is invalid")
    if state.get("goal_identity_required") is not True or not state.get(
        "goal_identity"
    ):
        errors.append("native state requires open goal identity")
    if not _SHA256_RE.fullmatch(
        str(state.get("committed_prefix_identity") or "")
    ):
        errors.append("native state committed prefix identity is invalid")
    inputs = data.get("inputs")
    if type(inputs) is not dict:
        errors.append("native state inputs must be an object")
        inputs = {}
    for field in ("context_sha256", "history_sha256"):
        if not _SHA256_RE.fullmatch(str(inputs.get(field) or "")):
            errors.append(f"native state {field} is invalid")
    try:
        runtime = EasyCryptRuntimeIdentity.from_payload(
            data.get("easycrypt_runtime")
        )
    except ValueError as exc:
        errors.append(f"native state runtime identity is invalid: {exc}")
        runtime = None
    try:
        companion = NativeCompanionIdentity.from_payload(
            data.get("native_companion")
        )
    except ValueError as exc:
        errors.append(f"native state companion identity is invalid: {exc}")
        companion = None
    if runtime is not None and companion is not None and (
        runtime.build_id != companion.easycrypt_toolchain_build_id
    ):
        errors.append("native state runtime/toolchain build IDs differ")
    result = data.get("result")
    if type(result) is not dict:
        errors.append("native state payload result must be an object")
        result = {}
    if type(result.get("goal_before")) is not str or not result.get("goal_before"):
        errors.append("native state result requires goal_before")
    if type(max_nodes) is int:
        try:
            validate_native_projection(
                result.get("projection"),
                max_nodes=max_nodes,
            )
        except RuntimeError as exc:
            errors.append(str(exc))
    if type(result.get("elapsed_ms")) is not int or result.get(
        "elapsed_ms", -1
    ) < 0:
        errors.append("native state elapsed_ms is invalid")
    if data.get("session_files_unchanged") is not True:
        errors.append("native state result did not preserve session files")
    return NativeStateValidation(tuple(errors))


def native_state_event_payload_fields(
    data: dict[str, Any],
    *,
    artifact: str,
    artifact_hash: str,
    result_sha256: str,
) -> dict[str, Any]:
    validation = validate_native_state_artifact(data)
    request = data.get("request") if isinstance(data.get("request"), dict) else {}
    state = data.get("state") if isinstance(data.get("state"), dict) else {}
    runtime = (
        data.get("easycrypt_runtime")
        if isinstance(data.get("easycrypt_runtime"), dict) else {}
    )
    companion = (
        data.get("native_companion")
        if isinstance(data.get("native_companion"), dict) else {}
    )
    result = data.get("result") if isinstance(data.get("result"), dict) else {}
    projection = (
        result.get("projection")
        if isinstance(result.get("projection"), dict) else {}
    )
    focused = (
        projection.get("focused_goal")
        if isinstance(projection.get("focused_goal"), dict) else {}
    )
    return {
        "schema_version": int(data.get("schema_version") or 0),
        "ok": bool(data.get("ok")) and validation.ok,
        "projection_id": str(data.get("projection_id") or ""),
        "request_id": str(request.get("request_id") or ""),
        "artifact": artifact,
        "artifact_hash": artifact_hash,
        "result_sha256": result_sha256,
        "session_id": str(state.get("session_id") or ""),
        "state_version": int(state.get("state_version") or 0),
        "goal_identity": str(state.get("goal_identity") or ""),
        "committed_prefix_identity": str(
            state.get("committed_prefix_identity") or ""
        ),
        "easycrypt_runtime_identity_sha256": str(
            runtime.get("semantic_identity_sha256") or ""
        ),
        "companion_binary_sha256": str(
            companion.get("companion_binary_sha256") or ""
        ),
        "why3_config_sha256": str(
            companion.get("why3_config_sha256") or ""
        ),
        "complete": bool(projection.get("complete")),
        "node_count": int(projection.get("node_count") or 0),
        "judgment_kind": str(focused.get("judgment_kind") or ""),
        "error_count": len(validation.errors),
    }


def write_native_state_artifact(
    session_dir: str | Path,
    data: dict[str, Any],
) -> dict[str, Any]:
    validation = validate_native_state_artifact(data)
    if not validation.ok:
        raise ValueError("native state contract: " + "; ".join(validation.errors))
    text = _canonical_text(data)
    artifact_hash = hashlib.sha1(text.encode("utf-8")).hexdigest()
    result_sha256 = hashlib.sha256(text.encode("utf-8")).hexdigest()
    artifact = write_confined_text_artifact(
        session_dir,
        subdir=NATIVE_STATE_SUBDIR,
        filename=f"native_state_{artifact_hash[:16]}.json",
        text=text + "\n",
    )
    return native_state_event_payload_fields(
        data,
        artifact=str(artifact),
        artifact_hash=artifact_hash,
        result_sha256=result_sha256,
    )


def record_native_state_projection(
    session: Any,
    data: dict[str, Any],
) -> dict[str, Any]:
    return record_authoritative_artifact_event(
        session,
        NATIVE_STATE_EVENT,
        lambda: write_native_state_artifact(session.dir, data),
        source="session_cli",
    )


def read_bound_native_state_event(
    session_dir: str | Path,
    event: dict[str, Any],
) -> BoundJsonArtifactRead:
    expected_session = str(Path(session_dir).resolve())

    def _validate(
        data: dict[str, Any],
        payload: dict[str, Any],
        artifact_hash: str,
    ) -> tuple[list[str], list[str]]:
        errors = list(validate_native_state_artifact(data).errors)
        expected = native_state_event_payload_fields(
            data,
            artifact=str(payload.get("artifact") or ""),
            artifact_hash=artifact_hash,
            result_sha256=hashlib.sha256(
                _canonical_text(data).encode("utf-8")
            ).hexdigest(),
        )
        for key, value in expected.items():
            if payload.get(key) != value:
                errors.append(f"{NATIVE_STATE_EVENT} {key} does not match artifact")
        state = data.get("state") if isinstance(data.get("state"), dict) else {}
        if state.get("session_id") != expected_session:
            errors.append("native state session_id is not the current session")
        return errors, []

    return read_bound_current_json_artifact_event(
        session_dir,
        event,
        event_type=NATIVE_STATE_EVENT,
        subdir=NATIVE_STATE_SUBDIR,
        validate_binding=_validate,
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise ValueError(f"native state input is unavailable: {path.name}") from exc
    return digest.hexdigest()


def _canonical_text(data: dict[str, Any]) -> str:
    return json.dumps(data, indent=2, sort_keys=True)
