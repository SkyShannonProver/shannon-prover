"""Ordered, integrity-aware loading for current tactic execution artifacts.

Content-addressed result files are storage objects, while
``tactic.execution.produced`` entries are interaction occurrences.  This
loader preserves every event occurrence, returns only event-bound results,
and reports unresolved events and true orphan files.  Every read target is
confined to the prescribed subdirectory of the current session.  Historical
envelope identities and frozen copied basenames are accepted only by the bulk
loader after the complete event stream proves a valid ``session.adopted``
lineage to the current session.  The live single-event reader stays
strict-current by default.  Event payloads never authorize arbitrary direct
paths.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from core.easycrypt.session.session_artifact_io import (
    read_confined_hashed_json_object,
    read_confined_json_object_directory,
)
from core.easycrypt.session.session_events import (
    SessionAdoptionLineageError,
    event_payload,
    read_events,
    validated_session_lineage_aliases,
)
from core.easycrypt.session.session_prover_workspace_schema import (
    validate_prover_workspace_view,
)
from core.easycrypt.validation_result import ValidationResult


@dataclass(frozen=True)
class TacticExecutionArtifact:
    path: Path
    result: dict[str, Any]
    event: dict[str, Any] | None = None
    event_index: int = 0
    artifact_hash: str = ""


@dataclass(frozen=True)
class TacticExecutionArtifactBinding:
    """One TacticExecutionResult strictly bound to its produced event."""

    result: dict[str, Any] | None = None
    artifact: Path | None = None
    artifact_hash: str = ""
    event: dict[str, Any] | None = None
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return self.result is not None and not self.errors


@dataclass(frozen=True)
class TacticExecutionArtifactLoad:
    artifacts: list[TacticExecutionArtifact] = field(default_factory=list)
    event_count: int = 0
    resolved_event_count: int = 0
    unresolved_event_indexes: list[int] = field(default_factory=list)
    unresolved_event_errors: dict[int, tuple[str, ...]] = field(
        default_factory=dict
    )
    orphan_paths: list[Path] = field(default_factory=list)
    unreadable_orphan_paths: list[Path] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return (
            self.resolved_event_count == self.event_count
            and not self.orphan_paths
            and not self.unreadable_orphan_paths
        )


def load_tactic_execution_artifacts(
    session_dir: str | Path,
    *,
    events: Iterable[dict[str, Any]] | None = None,
) -> TacticExecutionArtifactLoad:
    """Load current artifacts without conflating files and event occurrences."""

    path = Path(session_dir)
    event_rows = list(events) if events is not None else read_events(path)
    expected_session = str(path.resolve())
    lineage_error = ""
    try:
        aliases = validated_session_lineage_aliases(event_rows, path)
    except SessionAdoptionLineageError as exc:
        aliases = frozenset()
        lineage_error = str(exc)
    effective_aliases = (
        None if aliases == frozenset({expected_session}) else aliases
    )
    artifacts: list[TacticExecutionArtifact] = []
    event_artifact_names: set[str] = set()
    unresolved: list[int] = []
    unresolved_errors: dict[int, tuple[str, ...]] = {}
    event_count = 0
    for event_index, event in enumerate(event_rows, start=1):
        if type(event) is not dict or event.get("type") != "tactic.execution.produced":
            continue
        event_count += 1
        if lineage_error:
            binding = TacticExecutionArtifactBinding(
                event=event,
                errors=("invalid session adoption lineage: " + lineage_error,),
            )
        else:
            binding = read_bound_tactic_execution_event(
                path,
                event,
                events=event_rows,
                allowed_session_dirs=effective_aliases,
                allow_frozen_copy=effective_aliases is not None,
            )
        if (
            not binding.ok
            or binding.result is None
            or binding.artifact is None
        ):
            unresolved.append(event_index)
            unresolved_errors[event_index] = binding.errors
            continue
        artifacts.append(TacticExecutionArtifact(
            path=binding.artifact,
            result=binding.result,
            event=event,
            event_index=event_index,
            artifact_hash=binding.artifact_hash,
        ))
        event_artifact_names.add(binding.artifact.name)

    orphan_paths: list[Path] = []
    unreadable_orphan_paths: list[Path] = []
    for artifact_read in read_confined_json_object_directory(
        path,
        subdir="tactic_execution_results",
    ):
        artifact_path = artifact_read.path
        if artifact_path.name in event_artifact_names:
            continue
        if not artifact_read.ok:
            unreadable_orphan_paths.append(artifact_path)
            continue
        orphan_paths.append(artifact_path)

    return TacticExecutionArtifactLoad(
        artifacts=artifacts,
        event_count=event_count,
        resolved_event_count=event_count - len(unresolved),
        unresolved_event_indexes=unresolved,
        unresolved_event_errors=unresolved_errors,
        orphan_paths=orphan_paths,
        unreadable_orphan_paths=unreadable_orphan_paths,
    )


def validate_linked_workspace_artifact(
    result: dict[str, Any],
    *,
    session_dir: str | Path,
    allow_frozen_copy: bool = False,
) -> ValidationResult:
    """Validate a TER's linked workspace file, hash, schema, and embedding."""

    errors: list[str] = []
    workspace = result.get("workspace")
    workspace = workspace if isinstance(workspace, dict) else {}
    embedded = workspace.get("view")
    embedded = embedded if isinstance(embedded, dict) else {}
    artifact_value = workspace.get("artifact")
    if not isinstance(artifact_value, str) or not artifact_value:
        return ValidationResult(errors=[
            "workspace.artifact must be a non-empty string",
        ])
    artifact_read = read_confined_hashed_json_object(
        session_dir,
        artifact_value,
        subdir="prover_workspace_views",
        allow_frozen_copy=allow_frozen_copy,
    )
    if artifact_read is None:
        return ValidationResult(errors=[
            "workspace artifact is missing or outside the current session's "
            f"prover_workspace_views directory: {artifact_value}",
        ])
    if not artifact_read.ok or artifact_read.data is None:
        return ValidationResult(errors=[
            "workspace artifact is not a readable JSON object: "
            f"{artifact_read.path}",
        ])
    linked = artifact_read.data
    linked_hash = artifact_read.artifact_hash
    expected_hash = workspace.get("view_hash")
    if linked_hash != expected_hash:
        errors.append("workspace.view_hash does not match linked artifact")
    validation = validate_prover_workspace_view(linked)
    errors.extend(
        "linked workspace: " + error
        for error in validation.errors
    )
    if linked != embedded:
        errors.append("linked workspace artifact differs from embedded workspace.view")
    return ValidationResult(errors=errors, warnings=list(validation.warnings))


def validate_linked_workspace_event(
    result: dict[str, Any],
    *,
    events: Iterable[dict[str, Any]],
    tactic_event: dict[str, Any] | None = None,
    allowed_session_dirs: frozenset[str] | None = None,
) -> ValidationResult:
    """Require the TER workspace link to name a prior produced-view event."""

    rows = list(events)
    tactic_index = len(rows)
    if tactic_event is not None:
        located_index = next(
            (index for index, event in enumerate(rows) if event is tactic_event),
            None,
        )
        if located_index is None:
            return ValidationResult(errors=[
                "tactic execution event is not present in the supplied event stream",
            ])
        tactic_index = located_index
    workspace = result.get("workspace")
    workspace = workspace if isinstance(workspace, dict) else {}
    artifact = workspace.get("artifact")
    view_hash = workspace.get("view_hash")
    matches = []
    invalid_matches: list[str] = []
    for event in rows[:tactic_index]:
        if event.get("type") != "prover.workspace_view.produced":
            continue
        payload = event_payload(event)
        if (
            payload.get("artifact") == artifact
            and payload.get("view_hash") == view_hash
        ):
            from core.easycrypt.session.session_events import validate_event

            event_errors = [
                f"{issue.code}: {issue.message}"
                for issue in validate_event(event)
                if issue.severity == "error"
            ]
            event_session_dir = event.get("session_dir")
            event_session_id = event.get("session_id")
            if event_session_dir != event_session_id:
                event_errors.append(
                    "workspace event session_dir and session_id do not match"
                )
            if (
                allowed_session_dirs is not None
                and event_session_dir not in allowed_session_dirs
            ):
                event_errors.append(
                    "workspace event is outside the validated session adoption lineage"
                )
            if event_errors:
                invalid_matches.extend(event_errors)
            else:
                matches.append(event)
    if not matches:
        errors = [
            "workspace artifact/hash has no matching prior "
            "prover.workspace_view.produced event",
        ]
        errors.extend(invalid_matches)
        return ValidationResult(errors=errors)
    return ValidationResult()


def read_bound_tactic_execution_event(
    session_dir: str | Path,
    event: dict[str, Any],
    *,
    events: Iterable[dict[str, Any]],
    expected_mode: str | None = None,
    expected_command: str | None = None,
    expected_submitted_tactics: tuple[str, ...] | None = None,
    submitted_tactics_may_be_prefix: bool = False,
    allowed_session_dirs: frozenset[str] | None = None,
    allow_frozen_copy: bool = False,
) -> TacticExecutionArtifactBinding:
    """Read one TER through a strict or validated historical commit point.

    Defaults are live-manager strict.  A bulk loader may supply aliases from a
    validated ``session.adopted`` chain and permit basename-only frozen reads;
    that permission is applied only when this event names an ancestor session.
    """

    from core.easycrypt.session.session_events import validate_event
    from core.easycrypt.session.session_tactic_execution_result import (
        validate_tactic_execution_event_binding,
        validate_tactic_execution_result,
    )

    errors: list[str] = []
    warnings: list[str] = []
    if type(event) is not dict:
        return TacticExecutionArtifactBinding(
            errors=("tactic-execution event is not an object",),
        )
    for issue in validate_event(event):
        rendered = f"{issue.code}: {issue.message}"
        if issue.severity == "error":
            errors.append(rendered)
        else:
            warnings.append(rendered)
    if event.get("type") != "tactic.execution.produced":
        errors.append("event type must be 'tactic.execution.produced'")

    resolved_session = Path(session_dir).resolve()
    expected_session = str(resolved_session)
    trusted_sessions = (
        frozenset({expected_session})
        if allowed_session_dirs is None
        else frozenset(allowed_session_dirs)
    )
    if expected_session not in trusted_sessions:
        errors.append("validated session aliases do not include the current session")
    event_session_dir = event.get("session_dir")
    event_session_id = event.get("session_id")
    if event_session_dir != event_session_id:
        errors.append("event session_dir and session_id do not match")
    if event_session_dir not in trusted_sessions:
        if allowed_session_dirs is None:
            errors.append(
                "event session_dir does not match the current session: "
                f"expected {expected_session!r}, got {event_session_dir!r}"
            )
        else:
            errors.append(
                "event session_dir is outside the validated session adoption "
                f"lineage: {event_session_dir!r}"
            )
    historical_event = (
        isinstance(event_session_dir, str)
        and event_session_dir != expected_session
        and event_session_dir in trusted_sessions
    )

    payload = event_payload(event)
    artifact_value = payload.get("artifact")
    if not isinstance(artifact_value, str) or not artifact_value:
        errors.append("tactic.execution.produced is missing artifact")
        return TacticExecutionArtifactBinding(
            event=event,
            errors=tuple(errors),
            warnings=tuple(warnings),
        )
    artifact_read = read_confined_hashed_json_object(
        resolved_session,
        artifact_value,
        subdir="tactic_execution_results",
        allow_frozen_copy=bool(allow_frozen_copy and historical_event),
    )
    if artifact_read is None:
        errors.append(
            "tactic.execution.produced artifact is missing or outside this session"
        )
        return TacticExecutionArtifactBinding(
            event=event,
            errors=tuple(errors),
            warnings=tuple(warnings),
        )
    artifact = artifact_read.path
    if not artifact_read.ok or artifact_read.data is None:
        errors.append("tactic-execution artifact is not a readable JSON object")
        return TacticExecutionArtifactBinding(
            artifact=artifact,
            event=event,
            errors=tuple(errors),
            warnings=tuple(warnings),
        )
    result = artifact_read.data
    artifact_hash = artifact_read.artifact_hash
    validation = validate_tactic_execution_result(result)
    errors.extend(validation.errors)
    warnings.extend(validation.warnings)
    execution = result.get("execution")
    execution = execution if isinstance(execution, dict) else {}
    if expected_mode is not None and execution.get("mode") != expected_mode:
        errors.append(
            "tactic-execution mode does not match the current backend action: "
            f"expected {expected_mode!r}, got {execution.get('mode')!r}"
        )
    if (
        expected_command is not None
        and execution.get("command") != expected_command
    ):
        errors.append(
            "tactic-execution command does not match the current backend action: "
            f"expected {expected_command!r}, got {execution.get('command')!r}"
        )
    if expected_submitted_tactics is not None:
        submitted = execution.get("submitted_tactics")
        submitted_tuple = (
            tuple(submitted)
            if isinstance(submitted, list)
            and all(type(item) is str for item in submitted)
            else None
        )
        expected_tuple = tuple(expected_submitted_tactics)
        result_block = result.get("result")
        result_block = result_block if isinstance(result_block, dict) else {}
        successful_chain = (
            submitted_tactics_may_be_prefix
            and result.get("ok") is True
            and result_block.get("status") == "ok"
        )
        matches = submitted_tuple == expected_tuple
        if submitted_tactics_may_be_prefix and not successful_chain:
            matches = (
                submitted_tuple is not None
                and bool(submitted_tuple)
                and submitted_tuple == expected_tuple[:len(submitted_tuple)]
            )
        if not matches:
            errors.append(
                "tactic-execution submitted tactics do not match the current "
                f"backend request: expected {list(expected_tuple)!r}, got "
                f"{list(submitted_tuple) if submitted_tuple is not None else submitted!r}"
            )
    binding_validation = validate_tactic_execution_event_binding(
        result,
        payload,
        artifact_hash=artifact_hash,
        include_contract=False,
    )
    errors.extend(binding_validation.errors)
    warnings.extend(binding_validation.warnings)
    workspace_artifact_validation = validate_linked_workspace_artifact(
        result,
        session_dir=resolved_session,
        allow_frozen_copy=bool(allow_frozen_copy and historical_event),
    )
    errors.extend(workspace_artifact_validation.errors)
    warnings.extend(workspace_artifact_validation.warnings)
    rows = list(events)
    workspace_event_validation = validate_linked_workspace_event(
        result,
        events=rows,
        tactic_event=event,
        allowed_session_dirs=trusted_sessions,
    )
    errors.extend(workspace_event_validation.errors)
    warnings.extend(workspace_event_validation.warnings)
    return TacticExecutionArtifactBinding(
        result=None if errors else result,
        artifact=artifact,
        artifact_hash=artifact_hash,
        event=event,
        errors=tuple(errors),
        warnings=tuple(warnings),
    )
