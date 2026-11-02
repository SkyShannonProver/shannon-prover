"""Proof-state-compiler RPC client extracted from ``ReplSessionManager``.

``CompilerSurface`` owns the five read-only compiler backend calls (exact
tactic certification, compiler input, resource loads, native semantic
batches, and native state projection).  It deliberately holds a reference to
its ``ReplSessionManager`` instead of copied dependencies: every call must
share the manager's live ``_lock`` (mutual exclusion with session lifecycle
operations), its thread-local turn deadline via ``_run_backend``, and its
live ``state_version``/``committed_history()`` counters.  The surface never
mutates the session; ``ReplSessionManager`` keeps one-line delegates so the
``CompilerRuntime`` protocol and existing call sites are unchanged.
"""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any

from core.easycrypt.session.session_events import event_payload
from workflow.proof_state_compiler.service import require_runtime_unchanged

from .backend_actions import AuthoritativeViewResolution
from .backend_request import BackendRequest
from .backend_invocation import (
    capture_backend_invocation,
    resolve_backend_invocation,
)
from .repl_session import (
    ReplBackendError,
    ReplBackendTimeout,
    session_dir_path,
)

if TYPE_CHECKING:
    from .repl_session import ReplSessionManager


class CompilerSurface:
    """Read-only compiler RPC surface bound to one ``ReplSessionManager``."""

    def __init__(self, session: "ReplSessionManager") -> None:
        self._session = session

    def certify_exact_tactic(
        self,
        tactic: str,
        *,
        timeout: int = 30,
    ) -> dict[str, Any]:
        """Return an authority-bound read-only check for one exact tactic.

        This is the backend boundary used by the proof-state compiler service.
        Unlike display-oriented action records, the result names the one
        ``tactic.preflight.produced`` occurrence inside this exact call and proves
        that committed history and the manager state version did not change.
        """

        session = self._session
        candidate = str(tactic or "").strip()
        if not candidate:
            return {}
        with session._lock:
            session_path = session_dir_path(
                session.session_dir, session.project_root
            )
            boundary = capture_backend_invocation(
                session_path,
                action_name="try",
                mutates_proof_state=False,
            )
            actions: list[dict[str, Any]] = []
            with _read_only_backend_call(
                session, "exact tactic certification"
            ) as state_version_before:
                try:
                    session._run_backend(
                        BackendRequest.try_tactic(candidate),
                        actions=actions,
                        timeout=timeout,
                    )
                except (ReplBackendTimeout, ReplBackendError):
                    pass
            action = dict(actions[-1]) if actions else {}
            window = resolve_backend_invocation(
                boundary,
                exit_code=action.get("exit_code"),
            )
            produced, produced_error = window.exactly_one_produced_event(
                "tactic.preflight.produced"
            ) if window.ok else (None, window.error)
            authority: dict[str, Any] = {}
            if produced is not None and not produced_error:
                payload = event_payload(produced)
                authority = {
                    "event_type": "tactic.preflight.produced",
                    "event_id": str(produced.get("event_id") or ""),
                    "artifact_ref": str(payload.get("artifact") or ""),
                    "artifact_hash": str(payload.get("artifact_hash") or ""),
                    "hash_algorithm": "sha1",
                }
            return {
                "tactic": candidate,
                "action": action,
                "authority": authority,
                "contract_error": produced_error,
                # Reported for callers outside the compiler; the guard above
                # has already raised if the call changed the session.
                "history_unchanged": True,
                "state_version_before": state_version_before,
            }

    def read_compiler_input_v2(
        self,
        *,
        timeout: int = 30,
    ) -> dict[str, Any]:
        """Return one current-call, event-bound compiler input occurrence.

        This method does not read or translate ``raw_workspace_view``.  The
        backend result is accepted only through ``compiler.input.produced``;
        the returned authority envelope names that exact event and artifact.
        """

        session = self._session
        with session._lock:
            actions: list[dict[str, Any]] = []
            authoritative_resolutions: list[AuthoritativeViewResolution] = []
            with _read_only_backend_call(session, "compiler input"):
                payload = session._run_backend(
                    BackendRequest.compiler_input(session.state_version),
                    actions=actions,
                    timeout=timeout,
                    authoritative_resolutions=authoritative_resolutions,
                )
            if not isinstance(payload, dict) or payload.get("ok") is not True:
                raise ReplBackendError(actions[-1] if actions else {
                    "label": "compiler_input_v2",
                    "exit_code": 1,
                    "agent_observation": {
                        "error_summary": "invalid compiler input payload",
                    },
                })
            target = payload.get("target")
            if not isinstance(target, dict):
                raise ValueError("compiler input target is missing")
            if target.get("lemma") != session.lemma_name:
                raise ValueError("compiler input target lemma drifted")
            # Relative paths are project-relative (the backend runs there),
            # never relative to this process's working directory.
            project_root = Path(session.project_root)
            reported_source = project_root / str(target.get("source_file") or "")
            if reported_source.resolve() != (
                project_root / session.file_path
            ).resolve():
                raise ValueError("compiler input target source drifted")
            state = payload.get("state")
            if (
                not isinstance(state, dict)
                or state.get("state_version") != session.state_version
            ):
                raise ValueError("compiler input manager state version drifted")
            snapshot_id = str(payload.get("snapshot_id") or "")
            if len(authoritative_resolutions) != 1:
                raise ValueError(
                    "compiler input occurrence is not uniquely event-bound"
                )
            resolution = authoritative_resolutions[0]
            produced = resolution.event_payload or {}
            if (
                resolution.error
                or produced.get("snapshot_id") != snapshot_id
                or not resolution.event_id
                or resolution.event_sequence <= 0
            ):
                raise ValueError(
                    "compiler input occurrence authority does not match its snapshot"
                )
            return {
                "snapshot": payload,
                "authority": {
                    "event_type": "compiler.input.produced",
                    "event_id": resolution.event_id,
                    "event_sequence": resolution.event_sequence,
                    "artifact_ref": str(produced.get("artifact") or ""),
                    "artifact_sha256": str(
                        produced.get("snapshot_sha256") or ""
                    ),
                },
            }

    def load_compiler_resources_v2(
        self,
        *,
        request_id: str,
        source_snapshot_id: str,
        source_event_id: str,
        expected_state: dict[str, Any],
        load_requests: tuple[Any, ...],
        timeout: int = 30,
    ) -> dict[str, Any]:
        """Load declarations for one exact prior compiler-input occurrence."""

        session = self._session
        if not request_id or not source_snapshot_id or not source_event_id:
            raise ValueError("compiler resource load identity is incomplete")
        if not load_requests:
            raise ValueError("compiler resource load requires requests")
        request = {
            "request_id": request_id,
            "source_snapshot_id": source_snapshot_id,
            "source_event_id": source_event_id,
            "expected_state": dict(expected_state),
            "requests": [item.runtime_payload() for item in load_requests],
        }
        with session._lock:
            actions: list[dict[str, Any]] = []
            resolutions: list[AuthoritativeViewResolution] = []
            with _read_only_backend_call(session, "compiler resource load"):
                payload = session._run_backend(
                    BackendRequest.compiler_resource_load(
                        session.state_version, request
                    ),
                    actions=actions,
                    timeout=timeout,
                    authoritative_resolutions=resolutions,
                )
            if not isinstance(payload, dict) or payload.get("ok") is not True:
                raise ReplBackendError(actions[-1] if actions else {
                    "label": "compiler_resource_load_v2",
                    "exit_code": 1,
                    "agent_observation": {
                        "error_summary": "invalid compiler resource payload",
                    },
                })
            if len(resolutions) != 1:
                raise ValueError("compiler resource occurrence is not uniquely bound")
            resolution = resolutions[0]
            produced = resolution.event_payload or {}
            if (
                resolution.error
                or payload.get("request_id") != request_id
                or payload.get("source_snapshot_id") != source_snapshot_id
                or payload.get("source_event_id") != source_event_id
                or produced.get("request_id") != request_id
                or not resolution.event_id
                or resolution.event_sequence <= 0
            ):
                raise ValueError("compiler resource occurrence identity drifted")
            return {
                "result": payload,
                "authority": {
                    "event_type": "compiler.resources.loaded",
                    "event_id": resolution.event_id,
                    "event_sequence": resolution.event_sequence,
                    "artifact_ref": str(produced.get("artifact") or ""),
                    "artifact_sha256": str(produced.get("result_sha256") or ""),
                },
            }

    def execute_native_semantic_batch(
        self,
        *,
        batch_id: str,
        requests: tuple[dict[str, object], ...],
        timeout: int = 30,
    ) -> dict[str, Any]:
        """Return one event-bound tagged native EasyCrypt semantic batch."""

        session = self._session
        if not batch_id or batch_id != batch_id.strip():
            raise ValueError("native semantic batch requires batch_id")
        if not requests or len(requests) > 8:
            raise ValueError("native semantic batch size is invalid")
        request = {
            "batch_id": batch_id,
            "members": [dict(item) for item in requests],
        }
        with session._lock:
            actions: list[dict[str, Any]] = []
            authoritative_resolutions: list[AuthoritativeViewResolution] = []
            with _read_only_backend_call(session, "native semantic batch"):
                payload = session._run_backend(
                    BackendRequest.native_semantic_batch(
                        session.state_version, request
                    ),
                    actions=actions,
                    timeout=timeout,
                    authoritative_resolutions=authoritative_resolutions,
                )
            if not isinstance(payload, dict) or payload.get("ok") is not True:
                raise ReplBackendError(actions[-1] if actions else {
                    "label": "native_semantic_batch",
                    "exit_code": 1,
                    "agent_observation": {
                        "error_summary": "invalid native semantic batch payload",
                    },
                })
            raw_request = payload.get("request")
            state = payload.get("state")
            if raw_request != request:
                raise ValueError("native semantic batch request identity drifted")
            if (
                not isinstance(state, dict)
                or state.get("session_id") != str(
                    session_dir_path(
                        session.session_dir, session.project_root
                    ).resolve()
                )
                or state.get("state_version") != session.state_version
            ):
                raise ValueError("native semantic batch state identity drifted")
            if len(authoritative_resolutions) != 1:
                raise ValueError(
                    "native semantic batch occurrence is not uniquely event-bound"
                )
            resolution = authoritative_resolutions[0]
            produced = resolution.event_payload or {}
            if (
                resolution.error
                or produced.get("query_id") != payload.get("query_id")
                or produced.get("batch_id") != batch_id
                or produced.get("request_count") != len(requests)
                or not resolution.event_id
                or resolution.event_sequence <= 0
            ):
                raise ValueError(
                    "native semantic batch event authority does not match result"
                )
            return {
                "result": payload,
                "authority": {
                    "event_type": "native.semantic.batch.produced",
                    "event_id": resolution.event_id,
                    "event_sequence": resolution.event_sequence,
                    "artifact_ref": str(produced.get("artifact") or ""),
                    "artifact_sha256": str(produced.get("result_sha256") or ""),
                },
            }

    def project_native_state(
        self,
        *,
        request_id: str,
        max_nodes: int = 4096,
        max_depth: int = 128,
        timeout: int = 30,
    ) -> dict[str, Any]:
        """Return one event-bound typed EasyCrypt proof-state occurrence."""

        session = self._session
        if not request_id or request_id != request_id.strip():
            raise ValueError("native state query requires request_id")
        request = {
            "request_id": request_id,
            "max_nodes": max_nodes,
            "max_depth": max_depth,
        }
        with session._lock:
            actions: list[dict[str, Any]] = []
            authoritative_resolutions: list[AuthoritativeViewResolution] = []
            with _read_only_backend_call(session, "native state query"):
                payload = session._run_backend(
                    BackendRequest.native_state_projection(
                        session.state_version, request
                    ),
                    actions=actions,
                    timeout=timeout,
                    authoritative_resolutions=authoritative_resolutions,
                )
            if not isinstance(payload, dict) or payload.get("ok") is not True:
                raise ReplBackendError(actions[-1] if actions else {
                    "label": "native_state_projection",
                    "exit_code": 1,
                    "agent_observation": {
                        "error_summary": "invalid native state payload",
                    },
                })
            raw_request = payload.get("request")
            state = payload.get("state")
            if raw_request != request:
                raise ValueError("native state request identity drifted")
            if (
                not isinstance(state, dict)
                or state.get("session_id") != str(
                    session_dir_path(
                        session.session_dir, session.project_root
                    ).resolve()
                )
                or state.get("state_version") != session.state_version
            ):
                raise ValueError("native state identity drifted")
            if len(authoritative_resolutions) != 1:
                raise ValueError("native state occurrence is not uniquely event-bound")
            resolution = authoritative_resolutions[0]
            produced = resolution.event_payload or {}
            if (
                resolution.error
                or produced.get("projection_id") != payload.get("projection_id")
                or produced.get("request_id") != request_id
                or not resolution.event_id
                or resolution.event_sequence <= 0
            ):
                raise ValueError("native state event authority does not match result")
            return {
                "result": payload,
                "authority": {
                    "event_type": "native.state.produced",
                    "event_id": resolution.event_id,
                    "event_sequence": resolution.event_sequence,
                    "artifact_ref": str(produced.get("artifact") or ""),
                    "artifact_sha256": str(produced.get("result_sha256") or ""),
                },
            }


@contextmanager
def _read_only_backend_call(
    session: "ReplSessionManager",
    label: str,
) -> Iterator[int]:
    """Fail closed when one read-only backend call changed the session.

    Every compiler backend call is read-only by contract.  The check runs
    when the call returns or raises, before any payload validation, so a
    mutation is never hidden behind an ordinary compiler failure.  Yields the
    manager state version the call was bound to.
    """

    history_before = tuple(session.committed_history())
    state_version_before = session.state_version
    try:
        yield state_version_before
    finally:
        require_runtime_unchanged(
            session,
            history_before=history_before,
            state_version_before=state_version_before,
            label=label,
        )
