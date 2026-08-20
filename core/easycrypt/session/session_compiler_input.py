"""Authoritative runtime input artifact for proof-state compiler V2.

This is a runtime-owned snapshot, not a compiler pass and not a projection of
the previous workspace panel.  One read-only CLI call records exactly one
artifact and binds it to ``compiler.input.produced`` inside that call's event
window.  The compiler receives it only after the manager validates the binding.
"""

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
    read_committed_tactics,
)
from core.easycrypt.ec_runtime_identity import (
    EasyCryptRuntimeIdentity,
    verified_session_runtime_identity,
)
from core.easycrypt.session.session_artifact_io import (
    BoundJsonArtifactRead,
    read_bound_current_json_artifact_event,
    write_confined_text_artifact,
)
from core.easycrypt.session.session_events import record_authoritative_artifact_event
from core.easycrypt.session.session_projection import (
    active_goal_hash_from_raw,
    read_proof_state_projection,
)
from core.easycrypt.session.session_state import (
    read_target_lemma_metadata,
)


COMPILER_INPUT_SCHEMA_VERSION = 5
COMPILER_INPUT_KIND = "proof_state_compiler_input"
COMPILER_INPUT_EVENT = "compiler.input.produced"
COMPILER_INPUT_SUBDIR = "compiler_inputs"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class CompilerInputValidation:
    errors: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.errors


def build_compiler_input(
    session_dir: str | Path,
    *,
    manager_state_version: int | None = None,
    runtime_identity: EasyCryptRuntimeIdentity | None = None,
    live_tool_name: str = "compiler-input-v2",
) -> dict[str, Any]:
    """Read one exact current runtime state into the narrow V2 input schema."""

    path = Path(session_dir)
    runtime_identity = (
        verified_session_runtime_identity(path)
        if runtime_identity is None
        else runtime_identity
    )
    target = read_target_lemma_metadata(path)
    if target.status != "target_lemma":
        raise ValueError("compiler input requires exact managed target metadata")
    source_path = Path(target.source_file)
    if not source_path.is_absolute():
        source_path = source_path.resolve()
    source_text = source_path.read_text(encoding="utf-8")
    projection = read_proof_state_projection(
        path,
        live_tool_name=live_tool_name,
    )
    if not projection.events.ok:
        raise ValueError("compiler input requires a valid session event contract")
    if not projection.consistency.ok:
        raise ValueError("compiler input requires a consistent proof-state projection")
    closed = not projection.goal_identity_required
    goal_lines = (
        () if closed else tuple(projection.active_goal_text.splitlines())
    )
    if not closed and not goal_lines:
        raise ValueError("open compiler input requires an exact active goal")
    goal_identity = "" if closed else projection.goal.active_goal_hash
    if not closed and not goal_identity:
        raise ValueError("open compiler input requires a canonical goal identity")
    history = tuple(read_committed_tactics(path))
    history_identity = committed_prefix_identity(history)
    state_version = (
        _event_count(path)
        if manager_state_version is None
        else manager_state_version
    )
    if type(state_version) is not int or state_version < 0:
        raise ValueError("manager_state_version must be a non-negative integer")
    remaining_known = projection.goal.num_remaining_determined
    remaining = (
        projection.goal.num_remaining
        if remaining_known and projection.goal.num_remaining is not None
        else 0
    )
    data = {
        "schema_version": COMPILER_INPUT_SCHEMA_VERSION,
        "kind": COMPILER_INPUT_KIND,
        "ok": True,
        "snapshot_id": str(uuid.uuid4()),
        "target": {
            "source_file": str(source_path),
            "source_sha256": hashlib.sha256(
                source_text.encode("utf-8")
            ).hexdigest(),
            "lemma": target.lemma,
        },
        "state": {
            "session_id": str(path.resolve()),
            "state_version": state_version,
            "goal_identity": goal_identity,
            "goal_identity_required": not closed,
            "committed_prefix_identity": history_identity,
            "goal_lines": list(goal_lines),
            "goal_count": int(remaining),
            "goal_count_known": remaining_known,
            "closed": closed,
        },
        "transition": {"kind": "inspected"},
        "easycrypt_runtime": runtime_identity.to_payload(),
    }
    validation = validate_compiler_input(data)
    if not validation.ok:
        raise ValueError(
            "compiler input contract: " + "; ".join(validation.errors)
        )
    return data


def validate_compiler_input(data: dict[str, Any]) -> CompilerInputValidation:
    errors: list[str] = []
    if type(data) is not dict:
        return CompilerInputValidation(("compiler input must be an object",))
    expected_fields = {
        "schema_version",
        "kind",
        "ok",
        "snapshot_id",
        "target",
        "state",
        "transition",
        "easycrypt_runtime",
    }
    unexpected = sorted(set(data) - expected_fields)
    if unexpected:
        errors.append(
            "compiler input has unexpected fields: " + ", ".join(unexpected)
        )
    if (
        type(data.get("schema_version")) is not int
        or data.get("schema_version") != COMPILER_INPUT_SCHEMA_VERSION
    ):
        errors.append("unsupported compiler input schema_version")
    if data.get("kind") != COMPILER_INPUT_KIND:
        errors.append("unsupported compiler input kind")
    if data.get("ok") is not True:
        errors.append("compiler input must report ok=true")
    if type(data.get("snapshot_id")) is not str or not data.get("snapshot_id"):
        errors.append("compiler input requires snapshot_id")

    try:
        EasyCryptRuntimeIdentity.from_payload(data.get("easycrypt_runtime"))
    except ValueError as exc:
        errors.append(f"compiler input runtime identity is invalid: {exc}")

    target = data.get("target")
    if type(target) is not dict:
        errors.append("compiler input target must be an object")
        target = {}
    for field in ("source_file", "lemma"):
        if type(target.get(field)) is not str or not target.get(field):
            errors.append(f"compiler input target requires {field}")
    if not _SHA256_RE.fullmatch(str(target.get("source_sha256") or "")):
        errors.append("compiler input target source_sha256 is invalid")

    state = data.get("state")
    if type(state) is not dict:
        errors.append("compiler input state must be an object")
        state = {}
    if type(state.get("session_id")) is not str or not state.get("session_id"):
        errors.append("compiler input state requires session_id")
    if type(state.get("state_version")) is not int or state.get(
        "state_version", -1
    ) < 0:
        errors.append("compiler input state_version must be non-negative")
    if type(state.get("goal_identity_required")) is not bool:
        errors.append("compiler input requires explicit goal identity class")
    if type(state.get("committed_prefix_identity")) is not str or not (
        _SHA256_RE.fullmatch(state.get("committed_prefix_identity") or "")
    ):
        errors.append("compiler input committed_prefix_identity is invalid")
    goal_lines = state.get("goal_lines")
    if type(goal_lines) is not list or not all(
        type(line) is str for line in goal_lines
    ):
        errors.append("compiler input goal_lines must be a string list")
        goal_lines = []
    if type(state.get("goal_count")) is not int or state.get("goal_count", -1) < 0:
        errors.append("compiler input goal_count must be non-negative")
    for field in ("goal_count_known", "closed"):
        if type(state.get(field)) is not bool:
            errors.append(f"compiler input state requires boolean {field}")
    closed = state.get("closed") is True
    required = state.get("goal_identity_required") is True
    goal_identity = state.get("goal_identity")
    if type(goal_identity) is not str:
        errors.append("compiler input goal_identity must be a string")
        goal_identity = ""
    if closed and (required or goal_identity or goal_lines):
        errors.append("closed compiler input cannot carry an active goal")
    if not closed and (not required or not goal_identity or not goal_lines):
        errors.append("open compiler input requires goal identity and lines")
    if not closed and goal_lines:
        computed = active_goal_hash_from_raw("\n".join(goal_lines))
        if computed != goal_identity:
            errors.append("compiler input goal_identity does not match goal_lines")
    if data.get("transition") != {"kind": "inspected"}:
        errors.append("compiler input transition must be inspected")
    return CompilerInputValidation(tuple(errors))


def compiler_input_event_payload_fields(
    data: dict[str, Any],
    *,
    artifact: str,
    artifact_hash: str,
    snapshot_sha256: str,
) -> dict[str, Any]:
    validation = validate_compiler_input(data)
    state = data.get("state") if isinstance(data.get("state"), dict) else {}
    target = data.get("target") if isinstance(data.get("target"), dict) else {}
    return {
        "schema_version": int(data.get("schema_version") or 0),
        "ok": bool(data.get("ok")) and validation.ok,
        "snapshot_id": str(data.get("snapshot_id") or ""),
        "artifact": artifact,
        "artifact_hash": artifact_hash,
        "snapshot_sha256": snapshot_sha256,
        "session_id": str(state.get("session_id") or ""),
        "goal_identity": str(state.get("goal_identity") or ""),
        "goal_identity_required": bool(state.get("goal_identity_required")),
        "committed_prefix_identity": str(
            state.get("committed_prefix_identity") or ""
        ),
        "source_sha256": str(target.get("source_sha256") or ""),
        "lemma": str(target.get("lemma") or ""),
        "easycrypt_runtime_identity_sha256": str(
            (data.get("easycrypt_runtime") or {}).get(
                "semantic_identity_sha256"
            )
            if isinstance(data.get("easycrypt_runtime"), dict)
            else ""
        ),
        "error_count": len(validation.errors),
    }


def write_compiler_input_artifact(
    session_dir: str | Path,
    data: dict[str, Any],
) -> dict[str, Any]:
    validation = validate_compiler_input(data)
    if not validation.ok:
        raise ValueError(
            "compiler input contract: " + "; ".join(validation.errors)
        )
    text = _canonical_text(data)
    artifact_hash = hashlib.sha1(text.encode("utf-8")).hexdigest()
    snapshot_sha256 = hashlib.sha256(text.encode("utf-8")).hexdigest()
    artifact = write_confined_text_artifact(
        session_dir,
        subdir=COMPILER_INPUT_SUBDIR,
        filename=f"compiler_input_{artifact_hash[:16]}.json",
        text=text + "\n",
    )
    return compiler_input_event_payload_fields(
        data,
        artifact=str(artifact),
        artifact_hash=artifact_hash,
        snapshot_sha256=snapshot_sha256,
    )


def record_compiler_input(session: Any, data: dict[str, Any]) -> dict[str, Any]:
    return record_authoritative_artifact_event(
        session,
        COMPILER_INPUT_EVENT,
        lambda: write_compiler_input_artifact(session.dir, data),
        source="session_cli",
    )


def read_bound_compiler_input_event(
    session_dir: str | Path,
    event: dict[str, Any],
) -> BoundJsonArtifactRead:
    expected_session = str(Path(session_dir).resolve())

    def _validate(
        data: dict[str, Any],
        payload: dict[str, Any],
        artifact_hash: str,
    ) -> tuple[list[str], list[str]]:
        errors = list(validate_compiler_input(data).errors)
        text = _canonical_text(data)
        expected = compiler_input_event_payload_fields(
            data,
            artifact=str(payload.get("artifact") or ""),
            artifact_hash=artifact_hash,
            snapshot_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        )
        for key, value in expected.items():
            if payload.get(key) != value:
                errors.append(
                    f"{COMPILER_INPUT_EVENT} {key} does not match artifact"
                )
        state = data.get("state") if isinstance(data.get("state"), dict) else {}
        if state.get("session_id") != expected_session:
            errors.append("compiler input session_id is not the current session")
        return errors, []

    return read_bound_current_json_artifact_event(
        session_dir,
        event,
        event_type=COMPILER_INPUT_EVENT,
        subdir=COMPILER_INPUT_SUBDIR,
        validate_binding=_validate,
    )


def _canonical_text(data: dict[str, Any]) -> str:
    return json.dumps(data, indent=2, sort_keys=True)


def _event_count(session_dir: Path) -> int:
    path = session_dir / "events.jsonl"
    try:
        return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line)
    except OSError:
        return 0
