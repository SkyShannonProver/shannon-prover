"""One event-bound artifact for a bounded tagged native semantic batch."""

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
    NATIVE_SEMANTIC_PROTOCOL_VERSION,
    NativeCompanionIdentity,
    NativeSemanticBatchRequest,
    NativeSemanticQuery,
    run_native_semantic_batch,
    validate_attempt_descriptor,
    validate_native_query_payload,
    validate_proof_term_descriptor,
    validate_selected_application_binding_set_descriptor,
    validate_tactic_prefix_descriptor,
)
from core.easycrypt.session_artifact_io import (
    BoundJsonArtifactRead,
    read_bound_current_json_artifact_event,
    write_confined_text_artifact,
)
from core.easycrypt.session_events import record_authoritative_artifact_event
from core.easycrypt.session_projection import read_proof_state_projection


NATIVE_SEMANTIC_SCHEMA_VERSION = NATIVE_SEMANTIC_PROTOCOL_VERSION
NATIVE_SEMANTIC_KIND = "easycrypt_native_semantic_batch_result"
NATIVE_SEMANTIC_EVENT = "native.semantic.batch.produced"
NATIVE_SEMANTIC_SUBDIR = "native_semantic_batches"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class NativeSemanticValidation:
    errors: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.errors


def build_native_semantic_batch_result(
    session_dir: str | Path,
    *,
    manager_state_version: int,
    batch_id: str,
    requests: tuple[dict[str, object], ...],
    include_dirs: tuple[Path, ...],
    timeout: int = 30,
) -> dict[str, Any]:
    """Replay one exact state once and elaborate every ordered member."""

    path = Path(session_dir).resolve()
    if type(manager_state_version) is not int or manager_state_version < 0:
        raise ValueError("native semantic batch requires manager state version")
    if any(
        type(item) is not dict
        or set(item) != {
            "request_id", "evaluation_prefix", "query_kind", "payload"
        }
        for item in requests
    ):
        raise ValueError("native semantic request member schema is invalid")
    queries = tuple(NativeSemanticQuery(
        request_id=str(item.get("request_id") or ""),
        query_kind=str(item.get("query_kind") or ""),
        payload=(
            dict(item["payload"])
            if isinstance(item.get("payload"), dict)
            else {}
        ),
        evaluation_prefix=tuple(item["evaluation_prefix"]),
    ) for item in requests)
    projection = read_proof_state_projection(
        path,
        live_tool_name="native-semantic-batch",
    )
    if not projection.events.ok or not projection.consistency.ok:
        raise ValueError("native semantic batch requires consistent session state")
    if not projection.goal_identity_required:
        raise ValueError("native semantic batch requires an open proof goal")
    goal_identity = projection.goal.active_goal_hash
    if not goal_identity:
        raise ValueError("native semantic batch requires canonical goal identity")
    context = path / "context.ec"
    history = history_path(path)
    context_sha256 = _sha256_file(context)
    history_sha256 = _sha256_file(history)
    prefix_identity = committed_prefix_identity(
        tuple(read_committed_tactics(path))
    )
    runtime_identity = verified_session_runtime_identity(path)
    request = NativeSemanticBatchRequest(
        batch_id=batch_id,
        context_file=context,
        history_file=history,
        include_dirs=include_dirs,
        queries=queries,
        expected_goal_identity=goal_identity,
        expected_context_sha256=context_sha256,
        expected_history_sha256=history_sha256,
    )
    batch = run_native_semantic_batch(
        request,
        runtime_identity=runtime_identity,
        timeout=timeout,
    )
    data = {
        "schema_version": NATIVE_SEMANTIC_SCHEMA_VERSION,
        "kind": NATIVE_SEMANTIC_KIND,
        "ok": True,
        "query_id": str(uuid.uuid4()),
        "request": {
            "batch_id": request.batch_id,
            "members": [item.runtime_payload() for item in request.queries],
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
        "native_companion": batch.companion_identity.identity_payload(),
        "result": {
            "goal_before": batch.goal_before,
            "members": [{
                "request_id": item.request_id,
                "evaluation_prefix": list(item.evaluation_prefix),
                "query_kind": item.query_kind,
                "payload": item.payload,
                "status": item.status,
                "result_formula": item.result_formula,
                "descriptor": item.descriptor,
                "structured_error": item.structured_error,
                "elapsed_ms": item.elapsed_ms,
            } for item in batch.results],
            "cache_state": batch.cache_state,
            "build_elapsed_ms": batch.build_elapsed_ms,
            "execution_elapsed_ms": batch.execution_elapsed_ms,
            "elapsed_ms": batch.elapsed_ms,
        },
        "session_files_unchanged": True,
    }
    validation = validate_native_semantic_batch_result(data)
    if not validation.ok:
        raise ValueError(
            "native semantic batch contract: " + "; ".join(validation.errors)
        )
    return data


def validate_native_semantic_batch_result(
    data: dict[str, Any],
) -> NativeSemanticValidation:
    errors: list[str] = []
    if type(data) is not dict:
        return NativeSemanticValidation((
            "native semantic batch result must be an object",
        ))
    if type(data.get("schema_version")) is not int or data.get(
        "schema_version"
    ) != NATIVE_SEMANTIC_SCHEMA_VERSION:
        errors.append("unsupported native semantic batch schema_version")
    if data.get("kind") != NATIVE_SEMANTIC_KIND or data.get("ok") is not True:
        errors.append("native semantic batch kind/ok is invalid")
    if type(data.get("query_id")) is not str or not data.get("query_id"):
        errors.append("native semantic batch requires query_id")
    request = data.get("request")
    if type(request) is not dict:
        errors.append("native semantic batch request must be an object")
        request = {}
    if type(request.get("batch_id")) is not str or not request.get("batch_id"):
        errors.append("native semantic batch requires batch_id")
    requested_members = request.get("members")
    if (
        type(requested_members) is not list
        or not requested_members
        or len(requested_members) > 8
    ):
        errors.append("native semantic batch request size is invalid")
        requested_members = []
    request_ids: list[str] = []
    for item in requested_members:
        if type(item) is not dict or set(item) != {
            "request_id", "evaluation_prefix", "query_kind", "payload"
        }:
            errors.append("native semantic batch member request is invalid")
            continue
        request_id = item.get("request_id")
        request_ids.append(str(request_id or ""))
        if type(request_id) is not str or not request_id:
            errors.append("native semantic batch member requires request_id")
        evaluation_prefix = item.get("evaluation_prefix")
        if (
            type(evaluation_prefix) is not list
            or any(
                type(tactic) is not str
                or not tactic
                or tactic != tactic.strip()
                or not tactic.endswith(".")
                or "\n" in tactic
                or "\r" in tactic
                for tactic in evaluation_prefix
            )
        ):
            errors.append(
                "native semantic batch member evaluation prefix is invalid"
            )
        try:
            validate_native_query_payload(
                str(item.get("query_kind") or ""),
                item.get("payload"),
            )
        except ValueError as exc:
            errors.append(f"native semantic batch member query is invalid: {exc}")
    if len(request_ids) != len(set(request_ids)):
        errors.append("native semantic batch contains duplicate request IDs")
    state = data.get("state")
    if type(state) is not dict:
        errors.append("native semantic batch state must be an object")
        state = {}
    if type(state.get("session_id")) is not str or not state.get("session_id"):
        errors.append("native semantic batch state requires session_id")
    if type(state.get("state_version")) is not int or state.get(
        "state_version", -1
    ) < 0:
        errors.append("native semantic batch state_version is invalid")
    if state.get("goal_identity_required") is not True or not state.get(
        "goal_identity"
    ):
        errors.append("native semantic batch requires open goal identity")
    if not _SHA256_RE.fullmatch(
        str(state.get("committed_prefix_identity") or "")
    ):
        errors.append("native semantic batch committed prefix is invalid")
    inputs = data.get("inputs")
    if type(inputs) is not dict:
        errors.append("native semantic batch inputs must be an object")
        inputs = {}
    for field in ("context_sha256", "history_sha256"):
        if not _SHA256_RE.fullmatch(str(inputs.get(field) or "")):
            errors.append(f"native semantic batch {field} is invalid")
    try:
        runtime = EasyCryptRuntimeIdentity.from_payload(
            data.get("easycrypt_runtime")
        )
    except ValueError as exc:
        errors.append(f"native semantic batch runtime is invalid: {exc}")
        runtime = None
    try:
        companion = NativeCompanionIdentity.from_payload(
            data.get("native_companion")
        )
    except ValueError as exc:
        errors.append(f"native semantic batch companion is invalid: {exc}")
        companion = None
    if runtime is not None and companion is not None and (
        runtime.build_id != companion.easycrypt_toolchain_build_id
    ):
        errors.append("native semantic batch runtime/toolchain IDs differ")
    result = data.get("result")
    if type(result) is not dict:
        errors.append("native semantic batch payload result must be an object")
        result = {}
    if type(result.get("goal_before")) is not str or not result.get("goal_before"):
        errors.append("native semantic batch requires goal_before")
    result_members = result.get("members")
    if type(result_members) is not list or len(result_members) != len(
        requested_members
    ):
        errors.append("native semantic batch result cardinality is invalid")
        result_members = []
    for index, item in enumerate(result_members):
        request_item = requested_members[index]
        if type(item) is not dict or type(request_item) is not dict:
            errors.append("native semantic batch result member is invalid")
            continue
        for field in (
            "request_id", "evaluation_prefix", "query_kind", "payload"
        ):
            if item.get(field) != request_item.get(field):
                errors.append(
                    f"native semantic batch result {field} order drifted"
                )
        status = item.get("status")
        formula = item.get("result_formula")
        descriptor = item.get("descriptor")
        structured_error = item.get("structured_error")
        if status == "accepted":
            query_kind = request_item.get("query_kind")
            if (
                type(formula) is not str
                or (query_kind == "proof_term_elaboration" and not formula)
                or (query_kind != "proof_term_elaboration" and bool(formula))
                or type(descriptor) is not dict
                or not descriptor
                or structured_error != {}
            ):
                errors.append("accepted native semantic batch member is invalid")
            else:
                try:
                    if query_kind == "proof_term_elaboration":
                        validate_proof_term_descriptor(descriptor)
                    elif query_kind == "selected_application_binding_set":
                        validate_selected_application_binding_set_descriptor(
                            descriptor
                        )
                    elif query_kind == "attempt_diagnostic":
                        validate_attempt_descriptor(
                            descriptor,
                            query=NativeSemanticQuery(
                                request_id=str(request_item["request_id"]),
                                query_kind=str(query_kind),
                                payload=dict(request_item["payload"]),
                                evaluation_prefix=tuple(
                                    request_item["evaluation_prefix"]
                                ),
                            ),
                        )
                    else:
                        validate_tactic_prefix_descriptor(
                            descriptor,
                            query=NativeSemanticQuery(
                                request_id=str(request_item["request_id"]),
                                query_kind=str(query_kind),
                                payload=dict(request_item["payload"]),
                                evaluation_prefix=tuple(
                                    request_item["evaluation_prefix"]
                                ),
                            ),
                        )
                except RuntimeError as exc:
                    errors.append(f"native semantic descriptor is invalid: {exc}")
        elif status == "rejected":
            if (
                formula != ""
                or descriptor != {}
                or type(structured_error) is not dict
                or not structured_error
            ):
                errors.append("rejected native semantic batch member is invalid")
        else:
            errors.append("native semantic batch member status is invalid")
        if type(item.get("elapsed_ms")) is not int or item.get(
            "elapsed_ms", -1
        ) < 0:
            errors.append("native semantic batch member elapsed_ms is invalid")
    if result.get("cache_state") not in {"cold", "warm"}:
        errors.append("native semantic batch cache_state is invalid")
    phase_timings = []
    for field in ("build_elapsed_ms", "execution_elapsed_ms", "elapsed_ms"):
        value = result.get(field)
        if type(value) is not int or value < 0:
            errors.append(f"native semantic batch {field} is invalid")
        else:
            phase_timings.append(value)
    if len(phase_timings) == 3 and phase_timings[2] < sum(phase_timings[:2]):
        errors.append("native semantic batch phase timings are inconsistent")
    if data.get("session_files_unchanged") is not True:
        errors.append("native semantic batch did not preserve session files")
    return NativeSemanticValidation(tuple(errors))


def native_semantic_batch_event_payload_fields(
    data: dict[str, Any],
    *,
    artifact: str,
    artifact_hash: str,
    result_sha256: str,
) -> dict[str, Any]:
    validation = validate_native_semantic_batch_result(data)
    request = data.get("request") if isinstance(data.get("request"), dict) else {}
    state = data.get("state") if isinstance(data.get("state"), dict) else {}
    runtime = data.get("easycrypt_runtime") if isinstance(
        data.get("easycrypt_runtime"), dict
    ) else {}
    companion = data.get("native_companion") if isinstance(
        data.get("native_companion"), dict
    ) else {}
    result = data.get("result") if isinstance(data.get("result"), dict) else {}
    requested_members = request.get("members") if isinstance(
        request.get("members"), list
    ) else []
    result_members = result.get("members") if isinstance(
        result.get("members"), list
    ) else []
    typed_result_members = tuple(
        item for item in result_members if isinstance(item, dict)
    )
    return {
        "schema_version": int(data.get("schema_version") or 0),
        "ok": bool(data.get("ok")) and validation.ok,
        "query_id": str(data.get("query_id") or ""),
        "batch_id": str(request.get("batch_id") or ""),
        "request_count": len(requested_members),
        "accepted_count": sum(
            item.get("status") == "accepted" for item in typed_result_members
        ),
        "rejected_count": sum(
            item.get("status") == "rejected" for item in typed_result_members
        ),
        "cache_state": str(result.get("cache_state") or ""),
        "build_elapsed_ms": int(result.get("build_elapsed_ms") or 0),
        "execution_elapsed_ms": int(
            result.get("execution_elapsed_ms") or 0
        ),
        "elapsed_ms": int(result.get("elapsed_ms") or 0),
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
        "error_count": len(validation.errors),
    }


def write_native_semantic_batch_artifact(
    session_dir: str | Path,
    data: dict[str, Any],
) -> dict[str, Any]:
    validation = validate_native_semantic_batch_result(data)
    if not validation.ok:
        raise ValueError(
            "native semantic batch contract: " + "; ".join(validation.errors)
        )
    text = _canonical_text(data)
    artifact_hash = hashlib.sha1(text.encode("utf-8")).hexdigest()
    result_sha256 = hashlib.sha256(text.encode("utf-8")).hexdigest()
    artifact = write_confined_text_artifact(
        session_dir,
        subdir=NATIVE_SEMANTIC_SUBDIR,
        filename=f"native_semantic_batch_{artifact_hash[:16]}.json",
        text=text + "\n",
    )
    return native_semantic_batch_event_payload_fields(
        data,
        artifact=str(artifact),
        artifact_hash=artifact_hash,
        result_sha256=result_sha256,
    )


def record_native_semantic_batch_result(
    session: Any,
    data: dict[str, Any],
) -> dict[str, Any]:
    return record_authoritative_artifact_event(
        session,
        NATIVE_SEMANTIC_EVENT,
        lambda: write_native_semantic_batch_artifact(session.dir, data),
        source="session_cli",
    )


def read_bound_native_semantic_batch_event(
    session_dir: str | Path,
    event: dict[str, Any],
) -> BoundJsonArtifactRead:
    expected_session = str(Path(session_dir).resolve())

    def _validate(
        data: dict[str, Any],
        payload: dict[str, Any],
        artifact_hash: str,
    ) -> tuple[list[str], list[str]]:
        errors = list(validate_native_semantic_batch_result(data).errors)
        expected = native_semantic_batch_event_payload_fields(
            data,
            artifact=str(payload.get("artifact") or ""),
            artifact_hash=artifact_hash,
            result_sha256=hashlib.sha256(
                _canonical_text(data).encode("utf-8")
            ).hexdigest(),
        )
        for key, value in expected.items():
            if payload.get(key) != value:
                errors.append(
                    f"{NATIVE_SEMANTIC_EVENT} {key} does not match artifact"
                )
        state = data.get("state") if isinstance(data.get("state"), dict) else {}
        if state.get("session_id") != expected_session:
            errors.append("native semantic batch session is not current")
        return errors, []

    return read_bound_current_json_artifact_event(
        session_dir,
        event,
        event_type=NATIVE_SEMANTIC_EVENT,
        subdir=NATIVE_SEMANTIC_SUBDIR,
        validate_binding=_validate,
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise ValueError(
            f"native semantic batch input is unavailable: {path.name}"
        ) from exc
    return digest.hexdigest()


def _canonical_text(data: dict[str, Any]) -> str:
    return json.dumps(data, indent=2, sort_keys=True)
