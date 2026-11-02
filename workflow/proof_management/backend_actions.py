"""Normalize backend command results into manager actions."""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.easycrypt.proof_text import split_tactic_chain
from core.easycrypt.session.session_tactic_execution_artifacts import (
    read_bound_tactic_execution_event,
)
from core.easycrypt.session.session_compiler_input import (
    read_bound_compiler_input_event,
)
from core.easycrypt.session.session_compiler_resources import (
    read_bound_compiler_resource_load_event,
)
from core.easycrypt.session.session_native_semantics import (
    read_bound_native_semantic_batch_event,
)
from core.easycrypt.session.session_native_state import read_bound_native_state_event
from core.easycrypt.session.session_workspace_artifact import (
    read_bound_prover_workspace_event,
)
from core.easycrypt.session.session_events import validate_event
from core.easycrypt.session.session_tactic_preflight import (
    TACTIC_PREFLIGHT_EVENT_TYPE,
    read_bound_tactic_preflight_event,
)
from core.easycrypt.value_shapes import first_text as _first_text

from workflow.proof_management.common import (
    _dict,
    _drop_empty,
)
# Agent-facing prose and error-summary extraction live in observation_text;
# they stay importable from this module for existing consumers.
from workflow.proof_management.observation_text import (
    _action_effect,
    _error_summary,
    _manager_result_text,
    _proof_state_observation,
    _read_only_result_text,
)
from workflow.proof_management.managed_turn_outcome import classify_manager_action_outcome
from workflow.proof_management.backend_invocation import (
    BackendInvocationBoundary,
    capture_backend_invocation,
    resolve_backend_invocation,
)
from workflow.proof_management.backend_request import BackendRequest
from workflow.proof_management.types import ExactTacticPreflight

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
    envelope (notably start). Tactic execution, exact preflight, workspace, and
    compiler content are read only through their event-bound artifacts.
    """
    for obj in _iter_json_objects(text):
        return obj
    return {}


def backend_action_record(
    request: BackendRequest,
    argv: list[str],
    result: subprocess.CompletedProcess[str],
    duration_ms: int = 0,
    *,
    tactic_preflight_boundary: TacticPreflightInvocationBoundary | None = None,
    tactic_execution_boundary: TacticExecutionInvocationBoundary | None = None,
    authoritative_view_boundary: AuthoritativeViewInvocationBoundary | None = None,
    authoritative_view_resolution: AuthoritativeViewResolution | None = None,
) -> dict[str, Any]:
    """Record one completed backend call; ``argv`` is kept for audit only."""

    stdout = result.stdout or ""
    stderr = result.stderr or ""
    label = request.label
    mutates = request.mutates_proof_state
    preflight_resolution = _tactic_preflight_from_invocation(
        tactic_preflight_boundary,
        exit_code=result.returncode,
        required=request.requires_tactic_preflight,
    )
    tactic_execution_resolution = _tactic_execution_from_invocation(
        tactic_execution_boundary,
        exit_code=result.returncode,
    )
    aggregate_resolution = authoritative_view_resolution or (
        resolve_authoritative_view_invocation(
            authoritative_view_boundary,
            exit_code=result.returncode,
            required=request.authoritative_view is not None,
        )
    )
    outcome = _backend_action_outcome(
        request,
        stdout=stdout,
        exit_code=result.returncode,
        requires_execution_result=request.requires_tactic_execution_result,
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
    observation = agent_observation_for_request(
        request,
        stdout=stdout,
        stderr=stderr,
        exit_code=result.returncode,
        tactic_preflight_resolution=preflight_resolution,
        tactic_execution_resolution=tactic_execution_resolution,
        authoritative_view_resolution=aggregate_resolution,
    )
    preflight_evidence = (
        _exact_tactic_preflight(
            preflight_resolution,
            # The one error summary this call produced, shared with the
            # observation rather than derived a second way.
            error_summary=str(observation.get("error_summary") or ""),
        )
        if request.requires_tactic_preflight
        else None
    )
    return {
        "label": label,
        "argv": argv,
        "exit_code": result.returncode,
        "duration_ms": int(duration_ms),
        "mutates_proof_state": mutates,
        **outcome,
        **(
            {"execution_authority": execution_authority}
            if execution_authority
            else {}
        ),
        **(
            {"preflight_evidence": preflight_evidence.to_payload()}
            if preflight_evidence is not None
            else {}
        ),
        "agent_observation": observation,
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
    request: BackendRequest,
    argv: list[str],
    exc: subprocess.TimeoutExpired,
    timeout: int,
    duration_ms: int = 0,
) -> dict[str, Any]:
    stdout = _timeout_stream_text(exc.output)
    stderr = _timeout_stream_text(exc.stderr)
    mutates = request.mutates_proof_state
    outcome = classify_manager_action_outcome(
        status="timeout",
        ok=False,
        read_only=not mutates,
        mutates_proof_state=mutates,
        state_changed=False,
        timed_out=True,
    ).to_dict()
    return {
        "label": request.label,
        "argv": argv,
        "exit_code": None,
        "timed_out": True,
        "timeout_seconds": timeout,
        "duration_ms": int(duration_ms),
        "mutates_proof_state": mutates,
        **outcome,
        "agent_observation": _timeout_observation(request, timeout),
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


def capture_tactic_preflight_invocation(
    session_dir: Any,
    request: BackendRequest,
) -> TacticPreflightInvocationBoundary | None:
    """Capture the lower event bound and exact tactic for one ``-try`` call.

    The artifact is trusted only when produced inside the matching backend-call
    event window. Capturing the byte offset avoids timestamp and mtime races.
    """
    if not request.requires_tactic_preflight or not session_dir:
        return None
    tactic = request.tactic.strip()
    if not tactic:
        return None
    return TacticPreflightInvocationBoundary(
        invocation=capture_backend_invocation(
            session_dir,
            action_name="try",
            mutates_proof_state=False,
        ),
        expected_tactic=tactic,
    )


def capture_tactic_execution_invocation(
    session_dir: Any,
    request: BackendRequest,
) -> TacticExecutionInvocationBoundary | None:
    """Capture the only legal lower bound for a mutating TER occurrence."""

    contract = _tactic_execution_request_contract(request)
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
    request: BackendRequest,
) -> AuthoritativeViewInvocationBoundary | None:
    """Capture one artifact-backed, read-only authoritative occurrence."""

    contract = request.authoritative_view
    if contract is None or not session_dir:
        return None
    action_name, event_type = contract
    return AuthoritativeViewInvocationBoundary(
        invocation=capture_backend_invocation(
            session_dir,
            action_name=action_name,
            mutates_proof_state=False,
        ),
        event_type=event_type,
    )


def _tactic_execution_request_contract(
    request: BackendRequest,
) -> tuple[str, str, str, tuple[str, ...] | None, bool] | None:
    """Return the exact manager request a TER must describe.

    ``None`` tactics means the request carried no tactic text, which the
    reader rejects. Manager-owned commits bind the submitted text exactly.
    Chain failures report only the attempted prefix, so that one mode permits
    a prefix of the requested chain while successful chains must still match
    the whole request.
    """

    if not request.requires_tactic_execution_result:
        return None
    # Backend action name, TER mode and TER command coincide for every kind.
    name = request.kind
    if name == "undo":
        return name, name, name, (), False
    raw = request.tactic.strip()
    if not raw:
        return name, name, name, None, name == "commit_chain"
    if name == "commit_chain":
        return name, name, name, tuple(split_tactic_chain(raw)), True
    return name, name, name, (raw,), False


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
        # ``unavailable``: a multi-step rewind that could not be done by
        # EasyCrypt's undo; nothing changed and the manager restarts instead.
        if undo_status not in {"ok", "empty", "unavailable"}:
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


def _exact_tactic_preflight(
    resolution: _TacticPreflightResolution,
    *,
    error_summary: str,
) -> ExactTacticPreflight:
    """Project the validated preflight artifact certification depends on."""

    return ExactTacticPreflight.from_artifact(
        None if resolution.error else resolution.artifact,
        error_summary=error_summary,
    )


def _backend_action_outcome(
    request: BackendRequest,
    *,
    stdout: str,
    exit_code: int | None,
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
        read_only=request.read_only,
        mutates_proof_state=request.mutates_proof_state,
        state_changed=state_changed,
    ).to_dict()


def agent_observation_for_request(
    request: BackendRequest,
    *,
    stdout: str,
    stderr: str,
    exit_code: int | None,
    tactic_preflight_resolution: _TacticPreflightResolution | None = None,
    tactic_execution_resolution: _TacticExecutionResolution | None = None,
    authoritative_view_resolution: AuthoritativeViewResolution | None = None,
) -> dict[str, Any]:
    # Mutating proof actions consume the event-bound TER; exact compiler checks
    # consume their tactic-preflight artifact; aggregate workspace and compiler
    # actions consume their event-bound artifacts. Typed stdout is semantic
    # transport only for commands without an artifact contract (notably start).
    label = request.label
    requires_execution_result = request.requires_tactic_execution_result
    tactic_resolution = (
        tactic_execution_resolution or _TacticExecutionResolution()
    )
    aggregate_resolution = authoritative_view_resolution or (
        AuthoritativeViewResolution(
            required=True,
            error="missing pre-call authoritative view event boundary",
        )
        if request.authoritative_view is not None
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
        if request.requires_tactic_preflight
        else _TacticPreflightResolution()
    )
    if resolution.required:
        # The event-bound artifact is the sole verdict authority; its evidence
        # travels as the action's preflight_evidence, not in this observation.
        payload = {}
        if resolution.artifact is not None:
            payload["ok"] = bool(resolution.artifact.get("ok"))
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
    read_only_action = request.read_only
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
    tactic = _first_text(
        _first_list_text(execution.get("submitted_tactics")),
        request.tactic.strip(),
        default="",
    )
    if tactic:
        observation["tactic"] = tactic
    error_summary = _error_summary(payload, stderr, ok=ok)
    if error_summary:
        observation["error_summary"] = error_summary
    return _drop_empty(observation)


def _timeout_observation(request: BackendRequest, timeout: int) -> dict[str, Any]:
    return _drop_empty({
        "manager_action": request.label,
        "result": "The manager action timed out before producing a new completed view.",
        "effect": (
            "The attempted action may have touched the backend; the manager "
            "returned the last completed workspace view."
            if request.mutates_proof_state
            else (
                "This was a read-only manager request; it did not change the "
                "EasyCrypt proof state."
            )
        ),
        "proof_state": (
            "The manager could not confirm a new proof state before the timeout."
            if request.mutates_proof_state
            else "The committed EasyCrypt proof state was not changed."
        ),
        "tactic": request.tactic.strip(),
        "timeout_seconds": timeout,
    })


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
