"""Normalize backend command results into manager actions."""
from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.easycrypt.session_tactic_execution_artifacts import (
    read_bound_tactic_execution_event,
)
from core.easycrypt.session_compiler_input import (
    read_bound_compiler_input_event,
)
from core.easycrypt.session_compiler_resources import (
    read_bound_compiler_resource_load_event,
)
from core.easycrypt.session_native_semantics import (
    read_bound_native_semantic_batch_event,
)
from core.easycrypt.session_native_state import read_bound_native_state_event
from core.easycrypt.session_episode_timeline import (
    read_bound_episode_timeline_event,
)
from core.easycrypt.session_workspace_artifact import (
    read_bound_prover_workspace_event,
)
from core.easycrypt.session_events import validate_event
from core.easycrypt.session_tactic_preflight import (
    TACTIC_PREFLIGHT_EVENT_TYPE,
    read_bound_tactic_preflight_event,
)
from core.easycrypt.value_shapes import first_text as _first_text

from workflow.proof_management.common import (
    _dict,
    _drop_empty,
    _list,
    _preview,
)
from workflow.proof_management.turn_view import intent_effect as _intent_effect
from workflow.managed_turn_outcome import classify_manager_action_outcome
from workflow.proof_management.backend_invocation import (
    BackendInvocationBoundary,
    capture_backend_invocation,
    resolve_backend_invocation,
)

def _iter_json_objects(text: str):
    """Yield every top-level decodable JSON object in ``text``, in order.

    Backend command stdout is multi-section: human/debug display lines,
    goal text (which contains brace-delimited fragments), candidate-option JSON
    previews, and daemon-verify emissions. Only commands without an artifact
    contract use stdout as their typed transport. Such callers select the
    expected envelope by shape rather than taking the first ``{``; this
    generator is the shared scan that makes that possible.
    """
    raw = text or ""
    decoder = json.JSONDecoder()
    i = 0
    n = len(raw)
    while i < n:
        if raw[i] != "{":
            i += 1
            continue
        try:
            obj, end = decoder.raw_decode(raw[i:])
        except json.JSONDecodeError:
            i += 1
            continue
        if isinstance(obj, dict):
            yield obj
        i += max(end, 1)


def extract_json_object(text: str) -> dict[str, Any]:
    """First decodable JSON object. Heuristic — prefer marker/shape selection.

    Retained for commands whose current transport is one unambiguous typed JSON
    envelope (notably start). Tactic execution, exact preflight, workspace, and episode
    content are read only through their event-bound artifacts.
    """
    for obj in _iter_json_objects(text):
        return obj
    return {}


def backend_action_record(
    label: str,
    cmd: list[str],
    result: subprocess.CompletedProcess[str],
    duration_ms: int = 0,
    *,
    tactic_preflight_boundary: TacticPreflightInvocationBoundary | None = None,
    tactic_execution_boundary: TacticExecutionInvocationBoundary | None = None,
    authoritative_view_boundary: AuthoritativeViewInvocationBoundary | None = None,
    authoritative_view_resolution: AuthoritativeViewResolution | None = None,
) -> dict[str, Any]:
    stdout = result.stdout or ""
    stderr = result.stderr or ""
    mutates = backend_args_mutate_proof_state(cmd)
    requires_preflight = _backend_args_require_tactic_preflight(cmd)
    preflight_resolution = _tactic_preflight_from_invocation(
        tactic_preflight_boundary,
        exit_code=result.returncode,
        required=requires_preflight,
    )
    tactic_execution_resolution = _tactic_execution_from_invocation(
        tactic_execution_boundary,
        exit_code=result.returncode,
    )
    aggregate_resolution = authoritative_view_resolution or (
        resolve_authoritative_view_invocation(
            authoritative_view_boundary,
            exit_code=result.returncode,
            required=_backend_args_require_authoritative_view(cmd),
        )
    )
    requires_execution_result = _backend_args_require_tactic_execution_result(cmd)
    outcome = _backend_action_outcome(
        label,
        stdout=stdout,
        exit_code=result.returncode,
        mutates_proof_state=mutates,
        requires_execution_result=requires_execution_result,
        tactic_execution_result=tactic_execution_resolution.result,
        authoritative_payload=aggregate_resolution.payload,
    )
    contract_error = (
        preflight_resolution.error
        or tactic_execution_resolution.error
        or aggregate_resolution.error
    )
    if contract_error:
        outcome = {
            **classify_manager_action_outcome(
                status="backend_contract_error",
                ok=False,
                read_only=not mutates,
                mutates_proof_state=mutates,
                state_changed=False,
            ).to_dict(),
            "contract_error": contract_error,
        }
    elif preflight_resolution.required and preflight_resolution.artifact is not None:
        view_ok = bool(preflight_resolution.artifact.get("ok"))
        outcome = classify_manager_action_outcome(
            status="ok" if view_ok else "error",
            ok=view_ok and result.returncode == 0,
            read_only=True,
            mutates_proof_state=False,
            state_changed=False,
        ).to_dict()
    execution_authority = _tactic_execution_authority(
        tactic_execution_resolution
    )
    return {
        "label": label,
        "argv": cmd,
        "exit_code": result.returncode,
        "duration_ms": int(duration_ms),
        "mutates_proof_state": mutates,
        **outcome,
        **(
            {"execution_authority": execution_authority}
            if execution_authority
            else {}
        ),
        "agent_observation": agent_observation_from_command(
            label,
            cmd,
            stdout=stdout,
            stderr=stderr,
            exit_code=result.returncode,
            tactic_preflight_resolution=preflight_resolution,
            tactic_execution_resolution=tactic_execution_resolution,
            authoritative_view_resolution=aggregate_resolution,
        ),
        "stdout_chars": len(stdout),
        "stdout_lines": len(stdout.splitlines()),
        "stderr_chars": len(stderr),
        "stderr_preview": stderr[-1200:],
        "stdout_has_workspace_view": (
            "current_goal" in stdout
            and "proof_status" in stdout
        ),
    }


def timeout_backend_action_record(
    label: str,
    cmd: list[str],
    exc: subprocess.TimeoutExpired,
    timeout: int,
    duration_ms: int = 0,
) -> dict[str, Any]:
    stdout = _timeout_stream_text(exc.output)
    stderr = _timeout_stream_text(exc.stderr)
    mutates = backend_args_mutate_proof_state(cmd)
    outcome = classify_manager_action_outcome(
        status="timeout",
        ok=False,
        read_only=not mutates,
        mutates_proof_state=mutates,
        state_changed=False,
        timed_out=True,
    ).to_dict()
    return {
        "label": label,
        "argv": cmd,
        "exit_code": None,
        "timed_out": True,
        "timeout_seconds": timeout,
        "duration_ms": int(duration_ms),
        "mutates_proof_state": mutates,
        **outcome,
        "agent_observation": _timeout_observation(label, cmd, timeout),
        "stdout_chars": len(stdout),
        "stdout_lines": len(stdout.splitlines()),
        "stderr_chars": len(stderr),
        "stderr_preview": stderr[-1200:],
        "stdout_has_workspace_view": (
            "current_goal" in stdout
            and "proof_status" in stdout
        ),
    }


@dataclass(frozen=True)
class TacticPreflightInvocationBoundary:
    """Event-stream position captured before one exact ``-try`` call."""

    invocation: BackendInvocationBoundary
    expected_tactic: str


@dataclass(frozen=True)
class TacticExecutionInvocationBoundary:
    """Event-stream position captured before one mutating tactic action."""

    invocation: BackendInvocationBoundary
    expected_mode: str
    expected_command: str
    expected_tactics: tuple[str, ...] | None
    submitted_tactics_may_be_prefix: bool = False


@dataclass(frozen=True)
class _TacticPreflightResolution:
    required: bool = False
    artifact: dict[str, Any] | None = None
    event: dict[str, Any] | None = None
    artifact_hash: str = ""
    error: str = ""


@dataclass(frozen=True)
class _TacticExecutionResolution:
    required: bool = False
    result: dict[str, Any] | None = None
    error: str = ""
    event_id: str = ""
    event_sequence: int = 0
    artifact_ref: str = ""
    artifact_hash: str = ""
    hash_algorithm: str = ""


@dataclass(frozen=True)
class AuthoritativeViewInvocationBoundary:
    """Current-call boundary for an authoritative view invocation."""

    invocation: BackendInvocationBoundary
    event_type: str


@dataclass(frozen=True)
class AuthoritativeViewResolution:
    required: bool = False
    payload: dict[str, Any] | None = None
    artifact: Path | None = None
    error: str = ""
    event_id: str = ""
    event_sequence: int = 0
    event_payload: dict[str, Any] | None = None


def _backend_args_require_tactic_preflight(cmd: list[str]) -> bool:
    return not backend_args_mutate_proof_state(cmd) and "-try" in cmd


def capture_tactic_preflight_invocation(
    session_dir: Any,
    cmd: list[str],
) -> TacticPreflightInvocationBoundary | None:
    """Capture the lower event bound and exact tactic for one ``-try`` call.

    The artifact is trusted only when produced inside the matching backend-call
    event window. Capturing the byte offset avoids timestamp and mtime races.
    """
    if not _backend_args_require_tactic_preflight(cmd) or not session_dir:
        return None
    tactic = _command_arg_after(cmd, "-c") or _command_arg_after(
        cmd, "--command"
    )
    if not tactic.strip():
        return None
    return TacticPreflightInvocationBoundary(
        invocation=capture_backend_invocation(
            session_dir,
            action_name="try",
            mutates_proof_state=False,
        ),
        expected_tactic=tactic.strip(),
    )


def capture_tactic_execution_invocation(
    session_dir: Any,
    cmd: list[str],
) -> TacticExecutionInvocationBoundary | None:
    """Capture the only legal lower bound for a mutating TER occurrence."""

    if not _backend_args_require_tactic_execution_result(cmd):
        return None
    contract = _tactic_execution_request_contract(cmd)
    if contract is None or not session_dir:
        return None
    action_name, expected_mode, expected_command, expected_tactics, allow_prefix = contract
    return TacticExecutionInvocationBoundary(
        invocation=capture_backend_invocation(
            session_dir,
            action_name=action_name,
            mutates_proof_state=True,
        ),
        expected_mode=expected_mode,
        expected_command=expected_command,
        expected_tactics=expected_tactics,
        submitted_tactics_may_be_prefix=allow_prefix,
    )


def capture_authoritative_view_invocation(
    session_dir: Any,
    cmd: list[str],
) -> AuthoritativeViewInvocationBoundary | None:
    """Capture one artifact-backed, read-only authoritative occurrence."""

    contract = _authoritative_view_contract(cmd)
    if contract is None or not session_dir or backend_args_mutate_proof_state(cmd):
        return None
    _, action_name, event_type = contract
    return AuthoritativeViewInvocationBoundary(
        invocation=capture_backend_invocation(
            session_dir,
            action_name=action_name,
            mutates_proof_state=False,
        ),
        event_type=event_type,
    )


def _authoritative_view_contract(
    cmd: list[str],
) -> tuple[str, str, str] | None:
    parts = [str(part) for part in cmd]
    return next((item for item in (
        (
            "-managed-goal-view",
            "managed-goal-view",
            "prover.workspace_view.produced",
        ),
        ("-episode-view", "episode-view", "episode.timeline.produced"),
        (
            "-compiler-input-v2",
            "compiler-input-v2",
            "compiler.input.produced",
        ),
        (
            "-compiler-resource-load-v2",
            "compiler-resource-load-v2",
            "compiler.resources.loaded",
        ),
        (
            "-native-semantic-batch-json",
            "native-semantic-batch",
            "native.semantic.batch.produced",
        ),
        (
            "-native-state-projection-json",
            "native-state-projection",
            "native.state.produced",
        ),
    ) if item[0] in parts), None)


def _backend_args_require_authoritative_view(cmd: list[str]) -> bool:
    return (
        not backend_args_mutate_proof_state(cmd)
        and _authoritative_view_contract(cmd) is not None
    )


def _tactic_execution_action_name(cmd: list[str]) -> str:
    parts = [str(part) for part in cmd]
    if "-tactic-exec" not in parts:
        return ""
    index = parts.index("-tactic-exec")
    mode = parts[index + 1] if index + 1 < len(parts) else ""
    return {
        "commit": "commit",
        "commit_chain": "commit_chain",
        "undo": "undo",
    }.get(mode, "")


def _tactic_execution_request_contract(
    cmd: list[str],
) -> tuple[str, str, str, tuple[str, ...] | None, bool] | None:
    """Return the exact manager request a TER must describe.

    ``None`` tactics means the invocation did not carry an inspectable tactic
    source (for example, an unsupported stdin-only caller). Manager-owned live
    commits always use ``-c`` and therefore bind the submitted text exactly.
    Chain failures report only the attempted prefix, so that one mode permits
    a prefix of the requested chain while successful chains must still match
    the whole request.
    """

    action_name = _tactic_execution_action_name(cmd)
    if not action_name:
        return None
    mode, command = {
        "commit": ("commit", "commit"),
        "commit_chain": ("commit_chain", "commit_chain"),
        "undo": ("undo", "undo"),
    }[action_name]
    if action_name == "undo":
        return action_name, mode, command, (), False
    raw = _command_arg_after(cmd, "-c") or _command_arg_after(cmd, "--command")
    if not raw:
        return action_name, mode, command, None, action_name == "commit_chain"
    if action_name == "commit_chain":
        tactics = _split_chain_tactics(raw)
        return action_name, mode, command, tuple(tactics), True
    return action_name, mode, command, (raw.strip(),), False


def _split_chain_tactics(text: str) -> list[str]:
    """Mirror the backend chain parser for request/result binding."""

    tactics: list[str] = []
    for part in re.split(r"\.\s", str(text or "").strip()):
        normalized = part.strip().rstrip(".")
        if normalized:
            tactics.append(normalized + ".")
    return tactics


def _event_payload(event: dict[str, Any]) -> dict[str, Any]:
    payload = event.get("payload")
    return payload if isinstance(payload, dict) else {}


def _read_bound_tactic_preflight(
    boundary: TacticPreflightInvocationBoundary,
    event: dict[str, Any],
) -> tuple[dict[str, Any] | None, str, str]:
    binding = read_bound_tactic_preflight_event(
        boundary.invocation.session_dir,
        event,
        expected_tactic=boundary.expected_tactic,
    )
    if not binding.ok:
        return None, "; ".join(binding.errors), binding.artifact_hash
    return binding.data, "", binding.artifact_hash


def _invocation_event_window(
    boundary: (
        TacticPreflightInvocationBoundary
        | TacticExecutionInvocationBoundary
        | AuthoritativeViewInvocationBoundary
    ),
    *,
    exit_code: int | None,
) -> tuple[list[dict[str, Any]], int, int, str]:
    window = resolve_backend_invocation(
        boundary.invocation,
        exit_code=exit_code,
    )
    return (
        list(window.events),
        window.call_index,
        window.result_index,
        window.error,
    )


def _tactic_preflight_from_invocation(
    boundary: TacticPreflightInvocationBoundary | None,
    *,
    exit_code: int | None,
    required: bool = False,
) -> _TacticPreflightResolution:
    if boundary is None:
        if required:
            return _TacticPreflightResolution(
                required=True,
                error="missing pre-call tactic-preflight event boundary",
            )
        return _TacticPreflightResolution()
    events, call_index, result_index, error = _invocation_event_window(
        boundary,
        exit_code=exit_code,
    )
    if error:
        return _TacticPreflightResolution(required=True, error=error)
    preflight_events = [
        event for event in events[call_index + 1:result_index]
        if event.get("type") == TACTIC_PREFLIGHT_EVENT_TYPE
    ]
    if len(preflight_events) != 1:
        return _TacticPreflightResolution(
            required=True,
            error=(
                "expected exactly one tactic.preflight.produced event for this "
                "backend call"
            ),
        )
    artifact, error, artifact_hash = _read_bound_tactic_preflight(
        boundary, preflight_events[0]
    )
    if (
        not error
        and artifact is not None
        and artifact.get("ok") is True
        and exit_code not in (None, 0)
    ):
        return _TacticPreflightResolution(
            required=True,
            error=(
                "successful tactic preflight contradicts the non-zero backend "
                "process exit code"
            ),
        )
    return _TacticPreflightResolution(
        required=True,
        artifact=artifact,
        event=preflight_events[0],
        artifact_hash=artifact_hash,
        error=error,
    )


def resolve_authoritative_view_invocation(
    boundary: AuthoritativeViewInvocationBoundary | None,
    *,
    exit_code: int | None,
    required: bool = False,
) -> AuthoritativeViewResolution:
    if boundary is None:
        if required:
            return AuthoritativeViewResolution(
                required=True,
                error="missing pre-call authoritative view event boundary",
            )
        return AuthoritativeViewResolution()
    window = resolve_backend_invocation(
        boundary.invocation,
        exit_code=exit_code,
    )
    if not window.ok:
        return AuthoritativeViewResolution(required=True, error=window.error)
    produced_event, error = window.exactly_one_produced_event(
        boundary.event_type,
    )
    if error or produced_event is None:
        return AuthoritativeViewResolution(required=True, error=error)
    if boundary.event_type == "prover.workspace_view.produced":
        binding = read_bound_prover_workspace_event(
            boundary.invocation.session_dir,
            produced_event,
        )
    elif boundary.event_type == "episode.timeline.produced":
        binding = read_bound_episode_timeline_event(
            boundary.invocation.session_dir,
            produced_event,
        )
    elif boundary.event_type == "compiler.input.produced":
        binding = read_bound_compiler_input_event(
            boundary.invocation.session_dir,
            produced_event,
        )
    elif boundary.event_type == "compiler.resources.loaded":
        binding = read_bound_compiler_resource_load_event(
            boundary.invocation.session_dir,
            produced_event,
        )
    elif boundary.event_type == "native.semantic.batch.produced":
        binding = read_bound_native_semantic_batch_event(
            boundary.invocation.session_dir,
            produced_event,
        )
    elif boundary.event_type == "native.state.produced":
        binding = read_bound_native_state_event(
            boundary.invocation.session_dir,
            produced_event,
        )
    else:
        return AuthoritativeViewResolution(
            required=True,
            error=f"unsupported authoritative view event: {boundary.event_type}",
        )
    if not binding.ok or binding.data is None:
        return AuthoritativeViewResolution(
            required=True,
            artifact=binding.path,
            error="; ".join(binding.errors),
        )
    if binding.data.get("ok") is True and exit_code not in (None, 0):
        return AuthoritativeViewResolution(
            required=True,
            artifact=binding.path,
            error=(
                "successful authoritative view contradicts the non-zero "
                "backend process exit code"
            ),
        )
    return AuthoritativeViewResolution(
        required=True,
        payload=binding.data,
        artifact=binding.path,
        event_id=str(produced_event.get("event_id") or ""),
        event_sequence=window.events.index(produced_event) + 1,
        event_payload=dict(_event_payload(produced_event)),
    )


def _tactic_execution_from_invocation(
    boundary: TacticExecutionInvocationBoundary | None,
    *,
    exit_code: int | None,
) -> _TacticExecutionResolution:
    if boundary is None:
        return _TacticExecutionResolution()
    if boundary.expected_mode != "undo" and boundary.expected_tactics is None:
        return _TacticExecutionResolution(
            required=True,
            error=(
                "could not bind the mutating backend call to an explicit "
                "submitted tactic request"
            ),
        )
    events, call_index, result_index, error = _invocation_event_window(
        boundary,
        exit_code=exit_code,
    )
    if error:
        return _TacticExecutionResolution(required=True, error=error)
    result_events = [
        event for event in events[call_index + 1:result_index]
        if event.get("type") == "tactic.execution.produced"
    ]
    if len(result_events) != 1:
        return _TacticExecutionResolution(
            required=True,
            error=(
                "expected exactly one tactic.execution.produced event for "
                "this backend call"
            ),
        )
    result_event = result_events[0]
    binding = read_bound_tactic_execution_event(
        boundary.invocation.session_dir,
        result_event,
        events=events,
        expected_mode=boundary.expected_mode,
        expected_command=boundary.expected_command,
        expected_submitted_tactics=boundary.expected_tactics,
        submitted_tactics_may_be_prefix=(
            boundary.submitted_tactics_may_be_prefix
        ),
    )
    if not binding.ok:
        return _TacticExecutionResolution(
            required=True,
            error="; ".join(binding.errors),
        )
    if boundary.expected_mode == "undo":
        undo_events = [
            event for event in events[call_index + 1:result_index]
            if event.get("type") == "tactic.undone"
        ]
        if len(undo_events) != 1:
            return _TacticExecutionResolution(
                required=True,
                error=(
                    "expected exactly one tactic.undone event for this "
                    "undo backend call"
                ),
            )
        undo_event = undo_events[0]
        undo_issues = [
            issue for issue in validate_event(undo_event)
            if issue.severity == "error"
        ]
        if undo_issues:
            return _TacticExecutionResolution(
                required=True,
                error=(
                    "tactic.undone event contract is invalid: "
                    + "; ".join(issue.format() for issue in undo_issues)
                ),
            )
        resolved_session = str(boundary.invocation.session_dir.resolve())
        if any(
            undo_event.get(field_name) != resolved_session
            for field_name in ("session_dir", "session_id")
        ):
            return _TacticExecutionResolution(
                required=True,
                error="tactic.undone event does not belong to the current session",
            )
        undo_status = str(_event_payload(undo_event).get("status") or "")
        result_block = _event_payload(result_events[0])
        expected_status = "undone" if undo_status == "ok" else "no_progress"
        if undo_status not in {"ok", "empty"}:
            return _TacticExecutionResolution(
                required=True,
                error=f"unsupported tactic.undone status: {undo_status!r}",
            )
        if result_block.get("status") != expected_status:
            return _TacticExecutionResolution(
                required=True,
                error=(
                    "TacticExecutionResult status does not match the "
                    "tactic.undone outcome"
                ),
            )
        expected_changed = undo_status == "ok"
        if (
            result_block.get("state_changed") is not expected_changed
            or result_block.get("history_committed") is not expected_changed
        ):
            return _TacticExecutionResolution(
                required=True,
                error=(
                    "TacticExecutionResult mutation flags do not match the "
                    "tactic.undone outcome"
                ),
            )
    if exit_code not in (None, 0) and binding.result.get("ok") is True:
        return _TacticExecutionResolution(
            required=True,
            error=(
                "successful TacticExecutionResult contradicts the non-zero "
                "backend process exit code"
            ),
        )
    return _TacticExecutionResolution(
        required=True,
        result=binding.result,
        event_id=str(result_event.get("event_id") or ""),
        event_sequence=events.index(result_event) + 1,
        artifact_ref=(
            "tactic_execution_results/" + binding.artifact.name
            if binding.artifact is not None
            else ""
        ),
        artifact_hash=binding.artifact_hash,
        hash_algorithm="sha1",
    )


def _tactic_execution_authority(
    resolution: _TacticExecutionResolution,
) -> dict[str, Any]:
    """Project only validated TER fields needed by later manager consumers."""

    payload = resolution.result
    if (
        not resolution.required
        or resolution.error
        or not isinstance(payload, dict)
        or not resolution.event_id
        or resolution.event_sequence <= 0
        or not resolution.artifact_ref
        or not resolution.artifact_hash
        or resolution.hash_algorithm not in {"sha1", "sha256"}
    ):
        return {}
    execution = _dict(payload.get("execution"))
    result = _dict(payload.get("result"))
    submitted = execution.get("submitted_tactics")
    if not (
        isinstance(submitted, list)
        and all(type(item) is str for item in submitted)
    ):
        return {}
    return {
        "authority_kind": "event_bound_tactic_execution_result",
        "event_type": "tactic.execution.produced",
        "event_id": resolution.event_id,
        "event_sequence": resolution.event_sequence,
        "artifact_ref": resolution.artifact_ref,
        "artifact_hash": resolution.artifact_hash,
        "hash_algorithm": resolution.hash_algorithm,
        "submitted_tactics": list(submitted),
        "status": str(result.get("status") or ""),
        "state_changed": bool(execution.get("state_changed")),
        "history_committed": bool(execution.get("history_committed")),
        "structured_error": _first_text(
            result.get("error"),
            result.get("failure_reason"),
            default="",
        )[:1200],
    }


def _backend_action_outcome(
    label: str,
    *,
    stdout: str,
    exit_code: int | None,
    mutates_proof_state: bool,
    requires_execution_result: bool,
    tactic_execution_result: dict[str, Any] | None = None,
    authoritative_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Normalize the backend verdict before any presentation prose is built."""
    if requires_execution_result:
        payload = dict(tactic_execution_result or {})
    elif authoritative_payload is not None:
        payload = dict(authoritative_payload)
    else:
        payload = extract_json_object(stdout)
    if requires_execution_result and not payload:
        outcome = classify_manager_action_outcome(
            status="backend_contract_error",
            ok=False,
            read_only=False,
            mutates_proof_state=True,
            state_changed=False,
        ).to_dict()
        return {
            **outcome,
            "contract_error": (
                "mutating backend call is missing its required event-bound "
                "TacticExecutionResult"
            ),
        }
    result = _dict(payload.get("result"))
    execution = _dict(payload.get("execution"))
    status = _first_text(
        result.get("status"),
        payload.get("command_status"),
        payload.get("status"),
        default="ok" if exit_code == 0 else "failed",
    )
    payload_ok = payload.get("ok")
    result_ok = result.get("ok")
    if isinstance(payload_ok, bool):
        ok = payload_ok
    elif isinstance(result_ok, bool):
        ok = result_ok
    else:
        ok = exit_code == 0
    state_changed = bool(
        execution.get("state_changed") or execution.get("history_committed")
    )
    return classify_manager_action_outcome(
        status=status,
        ok=ok,
        read_only=_is_read_only_backend_action(label),
        mutates_proof_state=mutates_proof_state,
        state_changed=state_changed,
    ).to_dict()


def agent_observation_from_command(
    label: str,
    cmd: list[str],
    *,
    stdout: str,
    stderr: str,
    exit_code: int | None,
    tactic_preflight_resolution: _TacticPreflightResolution | None = None,
    tactic_execution_resolution: _TacticExecutionResolution | None = None,
    authoritative_view_resolution: AuthoritativeViewResolution | None = None,
) -> dict[str, Any]:
    # Mutating proof actions consume the event-bound TER; exact compiler checks
    # consume their tactic-preflight artifact; aggregate workspace/timeline
    # actions consume their event-bound artifacts. Typed stdout is semantic
    # transport only for commands without an artifact contract (notably start).
    requires_execution_result = _backend_args_require_tactic_execution_result(cmd)
    tactic_resolution = (
        tactic_execution_resolution or _TacticExecutionResolution()
    )
    aggregate_resolution = authoritative_view_resolution or (
        AuthoritativeViewResolution(
            required=True,
            error="missing pre-call authoritative view event boundary",
        )
        if _backend_args_require_authoritative_view(cmd)
        else AuthoritativeViewResolution()
    )
    if requires_execution_result:
        payload = dict(tactic_resolution.result or {})
    elif aggregate_resolution.required:
        # Aggregate stdout is human/debug display only.  Even a byte-for-byte
        # valid object there is ignored unless the current-call produced event
        # binds the persisted artifact.
        payload = dict(aggregate_resolution.payload or {})
    else:
        payload = extract_json_object(stdout)
    missing_execution_result = (
        requires_execution_result and not tactic_resolution.result
    )
    execution_contract_error = tactic_resolution.error or (
        "Missing required event-bound TacticExecutionResult."
        if missing_execution_result else ""
    )
    resolution = tactic_preflight_resolution or (
        _TacticPreflightResolution(
            required=True,
            error="missing pre-call tactic-preflight event boundary",
        )
        if _backend_args_require_tactic_preflight(cmd)
        else _TacticPreflightResolution()
    )
    if resolution.required:
        # The event-bound artifact is the sole verdict/content authority.
        payload = {}
        if resolution.artifact is not None:
            payload["ok"] = bool(resolution.artifact.get("ok"))
            payload["tactic_preflight"] = resolution.artifact
    structured_contract_error = resolution.error or aggregate_resolution.error
    result = _dict(payload.get("result"))
    execution = _dict(payload.get("execution"))
    status = _first_text(
        result.get("status"),
        payload.get("command_status"),
        payload.get("status"),
        default="ok" if exit_code == 0 else "failed",
    )
    if structured_contract_error or missing_execution_result:
        status = "backend_contract_error"
    ok_value = payload.get("ok")
    result_ok = result.get("ok")
    if isinstance(ok_value, bool):
        ok = ok_value
    elif isinstance(result_ok, bool):
        ok = result_ok
    elif structured_contract_error or missing_execution_result:
        ok = False
    else:
        ok = exit_code == 0
    read_only_action = _is_read_only_backend_action(label)
    if structured_contract_error:
        observation = {
            "manager_action": label,
            "result": "The backend did not produce a trustworthy structured context view.",
            "effect": "The read-only request did not change the proof state.",
            "proof_state": "unchanged",
            "contract_error": structured_contract_error,
        }
    elif missing_execution_result:
        observation = {
            "manager_action": label,
            "result": "The mutating backend response violated the manager contract.",
            "effect": "The proof-state effect is unknown; do not infer acceptance.",
            "proof_state": "unknown",
            "contract_error": execution_contract_error,
        }
    elif read_only_action and ok:
        observation: dict[str, Any] = {
            "effect": _action_effect(label, execution),
            "result": _read_only_result_text(label, status),
        }
    else:
        observation = {
            "manager_action": label,
            "result": _manager_result_text(label, status, ok),
            "effect": _action_effect(label, execution),
            "proof_state": _proof_state_observation(label, execution, status),
        }
    # A missing or invalid current-call preflight artifact is a contract failure. Raw
    # stdout remains backend/human debug evidence and is not promoted into the
    # agent-visible context surface as a substitute.
    content = (
        {}
        if structured_contract_error
        else content_observation_from_payload(label, payload)
    )
    if content:
        observation["content"] = content
    tactic = _first_text(
        _first_list_text(execution.get("submitted_tactics")),
        _command_arg_after(cmd, "-c"),
        default="",
    )
    if tactic:
        observation["tactic"] = tactic
    error_summary = _error_summary(payload, stderr, ok=ok)
    if error_summary:
        observation["error_summary"] = error_summary
    return _compact_agent_observation(observation)


def content_observation_from_payload(
    label: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Expose only exact-preflight evidence needed by certification."""

    if label != "exact_tactic_preflight":
        return {}
    preflight = _dict(payload.get("tactic_preflight"))
    if not preflight:
        return {}
    return _drop_empty({
        "candidate": preflight.get("tactic"),
        "accepted": preflight.get("accepted"),
        "outcome_known": preflight.get("outcome_known"),
        "proof_state": preflight.get("proof_state"),
        "runnable_evidence": preflight.get("runnable_evidence"),
    })


def _is_read_only_backend_action(label: str) -> bool:
    return label in {
        "exact_tactic_preflight",
        "managed_goal_view",
        "episode_view",
        "compiler_input_v2",
        "native_semantic_batch",
        "native_state_projection",
        "verify",
    }


def _read_only_result_text(label: str, status: str) -> str:
    ok = str(status or "").strip() in {"", "ok", "available"}
    if label == "exact_tactic_preflight":
        return (
            "EasyCrypt checked the exact tactic without committing it."
            if ok
            else "EasyCrypt rejected the exact tactic without changing proof state."
        )
    if label == "managed_goal_view":
        return "The manager produced the authoritative current goal envelope."
    if label == "episode_view":
        return "The manager produced the authoritative session timeline."
    return "The manager completed the read-only backend operation."


def _manager_result_text(label: str, status: str, ok: bool) -> str:
    normalized = str(status or "").strip()
    if label == "commit_tactic":
        if normalized == "partial_success":
            return (
                "EasyCrypt committed the successful tactic prefix and rejected "
                "the remaining tactic."
            )
        if normalized == "no_progress_reverted":
            return (
                "EasyCrypt accepted the tactic but the manager reverted it "
                "as a no-op because it did not change the goal."
            )
        return (
            "EasyCrypt accepted the committed tactic."
            if ok
            else "EasyCrypt rejected the committed tactic."
        )
    if label == "fresh_restart":
        return (
            "EasyCrypt restarted this node from the target lemma."
            if ok
            else "The manager could not restart this node."
        )
    if label in {"undo_last_step", "undo_to_checkpoint"}:
        return (
            "The manager completed the requested rewind."
            if ok
            else "The manager could not complete the requested rewind."
        )
    if ok:
        return f"The manager completed {label}."
    return f"The manager could not complete {label} ({normalized or 'failed'})."


def _compact_context_content(content: dict[str, Any]) -> dict[str, Any]:
    return dict(content)


def _compact_agent_observation(observation: dict[str, Any]) -> dict[str, Any]:
    """Compact an observation without erasing nested schema-required fields."""

    content = observation.get("content")
    clean = _drop_empty({
        key: value
        for key, value in observation.items()
        if key != "content"
    })
    if isinstance(content, dict) and content:
        clean["content"] = _compact_context_content(content)
    return clean


def _timeout_observation(label: str, cmd: list[str], timeout: int) -> dict[str, Any]:
    return _drop_empty({
        "manager_action": label,
        "result": "The manager action timed out before producing a new completed view.",
        "effect": (
            "The attempted action may have touched the backend; the manager "
            "returned the last completed workspace view."
            if backend_args_mutate_proof_state(cmd)
            else (
                "This was a read-only manager request; it did not change the "
                "EasyCrypt proof state."
            )
        ),
        "proof_state": (
            "The manager could not confirm a new proof state before the timeout."
            if backend_args_mutate_proof_state(cmd)
            else "The committed EasyCrypt proof state was not changed."
        ),
        "tactic": _command_arg_after(cmd, "-c"),
        "timeout_seconds": timeout,
    })


def _action_effect(label: str, execution: dict[str, Any]) -> str:
    if label == "exact_tactic_preflight":
        return (
            "This asks the manager for information only; it does not change "
            "the EasyCrypt proof state."
        )
    if bool(execution.get("state_changed") or execution.get("history_committed")):
        return (
            "EasyCrypt accepted a proof-state change; the refreshed view is "
            "based on the new committed state."
        )
    if label == "fresh_restart":
        return (
            "This explicitly restarts the current node's EasyCrypt session "
            "from the target lemma and discards this node's committed branch."
        )
    if label == "undo_to_checkpoint":
        return (
            "This rewinds the current node's committed branch to the selected "
            "checkpoint and returns the refreshed view."
        )
    if label == "commit_tactic":
        return (
            "The manager attempted to commit a tactic; use the result and "
            "latest goal to decide what changed."
        )
    return _intent_effect(label)


def _proof_state_observation(
    label: str,
    execution: dict[str, Any],
    status: str,
) -> str:
    normalized = str(status or "").strip()
    if normalized in {"no_progress", "no_progress_reverted"}:
        return "The committed EasyCrypt proof state was not changed."
    if bool(execution.get("state_changed") or execution.get("history_committed")):
        return "The committed EasyCrypt proof state changed."
    if normalized in {"failed", "error", "rejected"}:
        return "The committed EasyCrypt proof state was not changed."
    if label == "exact_tactic_preflight":
        return "The committed EasyCrypt proof state was not changed."
    if label == "fresh_restart":
        return "The EasyCrypt proof state was reset to the target lemma start."
    if label == "undo_to_checkpoint":
        return "The EasyCrypt proof state was rewound to the selected checkpoint."
    return ""


def _extract_daemon_rejected(raw_excerpt: str) -> str:
    """The EC daemon prints `[DAEMON_REJECTED] <reason>` (e.g. `[DAEMON_REJECTED]
    unknown procedure: PseudoRP.fi`) when it rejects a tactic. That reason carries no
    `error_excerpt:`/`errors` structure, so the other extractors miss it — recover it
    so a daemon rejection is not surfaced as an empty error summary."""
    for line in (raw_excerpt or "").splitlines():
        s = line.strip()
        if s.startswith("[DAEMON_REJECTED]"):
            reason = s[len("[DAEMON_REJECTED]"):].strip()
            if reason:
                return _preview(reason, limit=280)
    return ""


def _error_summary(payload: dict[str, Any], stderr: str, *, ok: bool = False) -> str:
    result = _dict(payload.get("result"))
    # Structured EC error fields FIRST: a daemon/tactic rejection carries the clean
    # reason directly in result.error / result.failure_reason (e.g. "[error] unknown
    # procedure: PseudoRP.fi"). These were never read, so a `[DAEMON_REJECTED]`
    # commit landed error_summary=None and the agent was told to "use the error
    # summary" with none present (root-caused by EC replay, MEE-CBC L1/L4 2026-06-06).
    structured = _first_text(result.get("error"), result.get("failure_reason"), default="")
    if structured.strip():
        return _preview(structured.strip(), limit=280)
    raw_excerpt = _first_text(result.get("raw_excerpt"), default="")
    extracted = _extract_error_excerpt(raw_excerpt)
    if extracted:
        return extracted
    extracted = _extract_try_error_summary(raw_excerpt)
    if extracted:
        return extracted
    extracted = _extract_daemon_rejected(raw_excerpt)
    if extracted:
        return extracted
    error_items = [
        *_list(payload.get("errors")),
    ]
    for item in error_items:
        if isinstance(item, dict):
            text = _first_text(
                item.get("message"),
                item.get("diagnostic"),
                item.get("error"),
                default="",
            )
            if text:
                return _preview(text, limit=280)
        elif str(item).strip():
            return _preview(str(item), limit=280)
    # Raw-stderr fallback — ONLY when the action FAILED. Structured proof errors
    # (raw_excerpt / errors above) are read regardless of status. But session_cli also writes purely
    # INFORMATIONAL notices to stderr on SUCCESS (exit 0) — notably the
    # "[session_cli] Restart #N: discarding K committed tactic(s) … Proceeding
    # with fresh session" line emitted when a checkpoint rewind restarts+replays.
    # Promoting that to error_summary surfaced a SUCCESSFUL undo_to_checkpoint to
    # the agent as a manager_error claiming its committed work was discarded — a
    # misleading signal. Only fall back to stderr when the command did not succeed.
    if not ok and stderr.strip():
        return _preview(stderr.strip(), limit=280)
    return ""


def _extract_try_error_summary(raw_excerpt: str) -> str:
    if not raw_excerpt:
        return ""
    lines = [line.strip() for line in raw_excerpt.splitlines() if line.strip()]
    selected: list[str] = []
    for line in lines:
        if line.startswith("[TRY] error:"):
            selected.append(line.removeprefix("[TRY] error:").strip())
            continue
        if line.startswith("[TRY] sync_detail:"):
            selected.append(
                "sync_detail: "
                + line.removeprefix("[TRY] sync_detail:").strip()
            )
    if not selected:
        return ""
    return _preview(" ".join(selected), limit=280)


def _extract_error_excerpt(raw_excerpt: str) -> str:
    if not raw_excerpt:
        return ""
    lines = [line.strip() for line in raw_excerpt.splitlines()]
    for idx, line in enumerate(lines):
        if "error_excerpt:" not in line:
            continue
        tail: list[str] = []
        for item in lines[idx + 1:]:
            if not item:
                continue
            if item.startswith("[") and tail:
                break
            if item.startswith("["):
                continue
            tail.append(item)
        if tail:
            return _preview(" ".join(tail), limit=280)
    return ""


def _command_arg_after(cmd: list[str], flag: str) -> str:
    try:
        idx = cmd.index(flag)
    except ValueError:
        return ""
    try:
        return str(cmd[idx + 1]).strip()
    except IndexError:
        return ""


def _first_list_text(value: Any) -> str:
    if not isinstance(value, list):
        return ""
    for item in value:
        if isinstance(item, str) and item.strip():
            return item.strip()
    return ""



def _timeout_stream_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def backend_args_mutate_proof_state(cmd: list[str]) -> bool:
    flags = set(str(part) for part in cmd)
    if "-tactic-exec" in flags:
        return True
    return "-start" in flags


def _backend_args_require_tactic_execution_result(
    cmd: list[str],
) -> bool:
    """Whether this action uses the current per-tactic execution contract.

    Session start mutates lifecycle state but is not a tactic submission; it
    has its own response contract.
    """

    return "-tactic-exec" in {str(part) for part in cmd}
