"""Live session episode timeline for prover agents.

TacticExecutionResult is the live post-command envelope. This module projects
current artifacts into an ordered episode timeline so an agent can review how
it got to the current proof state during an interactive run.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core.easycrypt.proof_lifecycle import (
    GOALS_DISCHARGED_PENDING_QED,
    SESSION_CLOSED_PENDING_VERIFICATION,
    VERIFIED,
    allows_qed,
    has_discharged_goals,
    is_session_completion_candidate,
)

from core.easycrypt.session_artifact_io import (
    BoundJsonArtifactRead,
    read_bound_current_json_artifact_event,
    write_confined_text_artifact,
)
from core.easycrypt.session_events import (
    event_payload,
    record_authoritative_artifact_event,
)
from core.easycrypt.session_prover_workspace_schema import (
    validate_prover_workspace_view,
)
from core.easycrypt.session_tactic_execution_result import (
    validate_tactic_execution_event_binding,
    validate_tactic_execution_result,
)
from core.easycrypt.session_tactic_execution_artifacts import (
    load_tactic_execution_artifacts,
)
from core.easycrypt.session_tactic_execution_observation import (
    tactic_execution_failed,
    tactic_execution_no_progress,
)
from core.easycrypt.value_shapes import as_dict as _dict, as_list as _list


SESSION_EPISODE_TIMELINE_SCHEMA_VERSION = 3
SESSION_EPISODE_TIMELINE_KIND = "session_episode_timeline"


@dataclass(frozen=True)
class SessionEpisodeTimelineValidation:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def build_session_episode_timeline(session_dir: str | Path) -> dict[str, Any]:
    path = Path(session_dir)
    loaded = load_tactic_execution_artifacts(path)
    items = [item for item in loaded.artifacts if item.event_index > 0]
    source = "tactic_execution_result"
    steps: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    if loaded.resolved_event_count != loaded.event_count:
        errors.append({
            "code": "session_episode_timeline.execution_event_artifact_mismatch",
            "message": (
                f"{loaded.event_count} tactic execution event(s), but only "
                f"{loaded.resolved_event_count} resolved to readable artifacts"
            ),
        })
        for event_index, event_errors in sorted(
            loaded.unresolved_event_errors.items()
        ):
            errors.extend({
                "code": "session_episode_timeline.execution_event_binding",
                "message": f"event#{event_index}: {error}",
            } for error in event_errors)
    if loaded.orphan_paths or loaded.unreadable_orphan_paths:
        errors.append({
            "code": "session_episode_timeline.orphan_execution_artifact",
            "message": (
                f"{len(loaded.orphan_paths)} readable and "
                f"{len(loaded.unreadable_orphan_paths)} unreadable tactic "
                "execution artifact(s) have no producing event"
            ),
        })
    previous_goal_hash = ""
    for item in items:
        result = _dict(item.result)
        result_validation = validate_tactic_execution_result(result)
        if result_validation.errors:
            artifact = str(item.path)
            errors.extend({
                "code": "session_episode_timeline.unsupported_execution_result",
                "message": f"{artifact or 'tactic execution result'}: {error}",
            } for error in result_validation.errors)
            continue
        binding_validation = validate_tactic_execution_event_binding(
            result,
            event_payload(item.event or {}),
            artifact_hash=item.artifact_hash,
            include_contract=False,
        )
        if binding_validation.errors:
            errors.extend({
                "code": "session_episode_timeline.execution_event_binding",
                "message": f"{item.path}: {error}",
            } for error in binding_validation.errors)
            continue
        workspace = _dict(_dict(result.get("workspace")).get("view"))
        validation = validate_prover_workspace_view(workspace)
        if validation.errors:
            artifact = str(item.path)
            errors.extend({
                "code": "session_episode_timeline.unsupported_workspace_view",
                "message": f"{artifact or 'tactic execution result'}: {error}",
            } for error in validation.errors)
            continue
        step = step_from_tactic_execution(
            idx=len(steps) + 1,
            item={
                "path": item.path,
                "result": item.result,
                "event_index": item.event_index,
            },
            previous_goal_hash=previous_goal_hash,
        )
        steps.append(step)
        goal_hash = str(step.get("goal_hash") or "")
        if goal_hash:
            previous_goal_hash = goal_hash

    return {
        "schema_version": SESSION_EPISODE_TIMELINE_SCHEMA_VERSION,
        "kind": SESSION_EPISODE_TIMELINE_KIND,
        "ok": not errors,
        "session_dir": str(path.resolve()),
        "source": source,
        "step_count": len(steps),
        "rollup": _rollup(steps),
        "steps": steps,
        "notes": _episode_notes(steps),
        "errors": errors,
    }


def step_from_tactic_execution(
    *,
    idx: int,
    item: dict[str, Any],
    previous_goal_hash: str,
) -> dict[str, Any]:
    result = _dict(item.get("result"))
    execution = _dict(result.get("execution"))
    result_panel = _dict(result.get("result"))
    workspace = _dict(_dict(result.get("workspace")).get("view"))
    proof_status_panel = _dict(workspace.get("proof_status"))
    current_goal = _dict(workspace.get("current_goal"))
    audit = _dict(result.get("audit"))
    failed = tactic_execution_failed(result)
    goal_hash = str(audit.get("goal_hash") or "")
    proof_status = str(
        proof_status_panel.get("status")
        or audit.get("proof_status")
        or "",
    )
    num_remaining = proof_status_panel.get("remaining_goals")
    if num_remaining is None:
        num_remaining = audit.get("num_remaining")
    submitted = [
        str(tactic)
        for tactic in _list(execution.get("submitted_tactics"))
        if isinstance(tactic, str) and tactic.strip()
    ]
    tactic = str(execution.get("failed_tactic") or "")
    if not tactic and submitted:
        tactic = submitted[-1]
    state_changed = bool(execution.get("state_changed"))
    no_progress = tactic_execution_no_progress(result)
    goals_discharged = allows_qed(proof_status)
    session_completion_candidate = is_session_completion_candidate(
        proof_status
    )
    transition_kind = (
        "session_completion_candidate" if session_completion_candidate else
        "goals_discharged" if goals_discharged else
        "no_progress" if no_progress else
        "state_changed" if state_changed else
        "preflight" if str(execution.get("mode") or "") == "preflight" else
        "no_state_change"
    )
    step = {
        "step": idx,
        "event_index": _int(item.get("event_index")),
        "command": str(execution.get("command") or ""),
        "command_status": str(result_panel.get("status") or ""),
        "ok": bool(result.get("ok")),
        "failed": failed,
        "tactic": tactic,
        "accepted_count": _int(execution.get("accepted_count")),
        "attempted_count": _int(execution.get("attempted_count")),
        "rollback_count": _int(execution.get("rollback_count")),
        "proof_status": proof_status,
        "goal_type": str(
            current_goal.get("goal_type")
            or audit.get("goal_type")
            or "unknown"
        ),
        "num_remaining": num_remaining,
        "num_remaining_determined": num_remaining is not None,
        "goal_hash": goal_hash,
        "goal_hash_changed": bool(
            previous_goal_hash and goal_hash and goal_hash != previous_goal_hash
        ),
        "transition_kind": transition_kind,
        "transition_status": str(result_panel.get("status") or ""),
        "goals_before": None,
        "goals_after": num_remaining,
        "goals_discharged": goals_discharged,
        "session_completion_candidate": session_completion_candidate,
        "no_progress": no_progress,
        "no_progress_reason": str(result_panel.get("failure_reason") or ""),
        "error_count": len(_list(result.get("errors"))),
        "warning_count": len(_list(result.get("notes"))),
        "artifact": str(item.get("path") or ""),
        "source": "tactic_execution_result",
    }
    step["prover_observations"] = _step_observations(step)
    return step


def write_session_episode_timeline_artifact(
    session_dir: str | Path,
    timeline: dict[str, Any],
) -> dict[str, Any]:
    path = Path(session_dir)
    data = dict(timeline)
    validation = validate_session_episode_timeline(data)
    data["ok"] = bool(data.get("ok")) and validation.ok
    if validation.errors:
        data["errors"] = list(data.get("errors") or []) + [
            {"code": "session_episode_timeline.invalid", "message": err}
            for err in validation.errors
        ]
    text = json.dumps(data, indent=2, sort_keys=True)
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()
    artifact = write_confined_text_artifact(
        path,
        subdir="episode_timelines",
        filename=f"episode_timeline_{digest[:16]}.json",
        text=text + "\n",
    )
    return episode_timeline_event_payload_fields(
        data,
        artifact=str(artifact),
        timeline_hash=digest,
    )


def episode_timeline_event_payload_fields(
    data: dict[str, Any],
    *,
    artifact: str,
    timeline_hash: str,
) -> dict[str, Any]:
    """Return the sole current produced-event mirror for one timeline."""

    rollup = _dict(data.get("rollup"))
    return {
        "schema_version": int(data.get("schema_version") or 0),
        "ok": bool(data.get("ok")),
        "artifact": artifact,
        "timeline_hash": timeline_hash,
        "step_count": _int(data.get("step_count")),
        "final_proof_status": str(rollup.get("final_proof_status") or ""),
        "note_count": len(_list(data.get("notes"))),
        "error_count": len(_list(data.get("errors"))),
    }


def validate_episode_timeline_event_binding(
    data: dict[str, Any],
    payload: dict[str, Any],
    *,
    artifact_hash: str,
    expected_session_dir: str,
) -> SessionEpisodeTimelineValidation:
    """Validate a produced-event mirror against its exact timeline bytes."""

    validation = validate_session_episode_timeline(data)
    errors = list(validation.errors)
    expected = episode_timeline_event_payload_fields(
        data,
        artifact=str(payload.get("artifact") or ""),
        timeline_hash=artifact_hash,
    )
    for key, expected_value in expected.items():
        if payload.get(key) != expected_value:
            errors.append(
                f"episode.timeline.produced {key} does not match its artifact: "
                f"expected {expected_value!r}, got {payload.get(key)!r}"
            )
    if data.get("session_dir") != expected_session_dir:
        errors.append(
            "episode timeline session_dir does not match the current session"
        )
    return SessionEpisodeTimelineValidation(
        errors=errors,
        warnings=list(validation.warnings),
    )


def read_bound_episode_timeline_event(
    session_dir: str | Path,
    event: dict[str, Any],
) -> BoundJsonArtifactRead:
    """Read one live episode timeline only through its produced event."""

    expected_session = str(Path(session_dir).resolve())

    def _validate(
        data: dict[str, Any],
        payload: dict[str, Any],
        artifact_hash: str,
    ) -> tuple[list[str], list[str]]:
        validation = validate_episode_timeline_event_binding(
            data,
            payload,
            artifact_hash=artifact_hash,
            expected_session_dir=expected_session,
        )
        return list(validation.errors), list(validation.warnings)

    return read_bound_current_json_artifact_event(
        session_dir,
        event,
        event_type="episode.timeline.produced",
        subdir="episode_timelines",
        validate_binding=_validate,
    )


def record_session_episode_timeline(
    session_or_dir: Any,
    timeline: dict[str, Any],
    *,
    source: str = "session_cli",
) -> dict[str, Any]:
    session_dir = getattr(session_or_dir, "dir", session_or_dir)
    return record_authoritative_artifact_event(
        session_or_dir,
        "episode.timeline.produced",
        lambda: write_session_episode_timeline_artifact(session_dir, timeline),
        source=source,
    )


def validate_session_episode_timeline(
    data: dict[str, Any],
) -> SessionEpisodeTimelineValidation:
    errors: list[str] = []
    warnings: list[str] = []
    required = {
        "schema_version": int,
        "kind": str,
        "ok": bool,
        "session_dir": str,
        "step_count": int,
        "rollup": dict,
        "steps": list,
        "notes": list,
        "errors": list,
    }
    for key, typ in required.items():
        if key not in data:
            errors.append(f"missing field `{key}`")
            continue
        if not isinstance(data[key], typ):
            errors.append(
                f"field `{key}` expected {typ.__name__}, "
                f"got {type(data[key]).__name__}"
            )
    if data.get("schema_version") != SESSION_EPISODE_TIMELINE_SCHEMA_VERSION:
        errors.append(
            "schema_version must be "
            f"{SESSION_EPISODE_TIMELINE_SCHEMA_VERSION}"
        )
    if data.get("kind") != SESSION_EPISODE_TIMELINE_KIND:
        errors.append(f"kind must be {SESSION_EPISODE_TIMELINE_KIND!r}")
    steps = _list(data.get("steps"))
    if isinstance(data.get("step_count"), int) and data.get("step_count") != len(steps):
        errors.append("step_count must equal len(steps)")
    for idx, step in enumerate(steps):
        if not isinstance(step, dict):
            errors.append(f"steps[{idx}] must be an object")
            continue
        if step.get("step") != idx + 1:
            errors.append(f"steps[{idx}].step must be {idx + 1}")
    return SessionEpisodeTimelineValidation(errors=errors, warnings=warnings)


def _rollup(steps: list[dict[str, Any]]) -> dict[str, Any]:
    transition_counts = Counter(str(s.get("transition_kind") or "") for s in steps)
    proof_status_counts = Counter(str(s.get("proof_status") or "") for s in steps)
    return {
        "transition_counts": dict(sorted(transition_counts.items())),
        "proof_status_counts": dict(sorted(proof_status_counts.items())),
        "failed_command_count": sum(1 for s in steps if s.get("failed")),
        "no_progress_count": sum(1 for s in steps if s.get("no_progress")),
        "goal_hash_change_count": sum(1 for s in steps if s.get("goal_hash_changed")),
        "goals_discharged_step": next(
            (
                s["step"]
                for s in steps
                if has_discharged_goals(str(s.get("proof_status") or ""))
            ),
            0,
        ),
        "session_completion_candidate_step": next(
            (
                s["step"]
                for s in steps
                if is_session_completion_candidate(
                    str(s.get("proof_status") or "")
                )
            ),
            0,
        ),
        "final_proof_status": str(steps[-1].get("proof_status") or "") if steps else "",
    }


def _step_observations(step: dict[str, Any]) -> list[str]:
    out: list[str] = []
    if step.get("proof_status") == GOALS_DISCHARGED_PENDING_QED:
        out.append("goals_discharged_qed_next")
    if step.get("proof_status") == SESSION_CLOSED_PENDING_VERIFICATION:
        out.append("session_closed_verify_next")
    if step.get("proof_status") == VERIFIED:
        out.append("verified_stop")
    if step.get("failed"):
        out.append("failed_command_repair_next")
    if step.get("goal_hash_changed"):
        out.append("active_goal_changed")
    if step.get("transition_kind") == "state_changed_same_goal_count":
        out.append("same_goal_count_state_changed")
    if step.get("transition_kind") == "committed_unknown_effect":
        out.append("effect_unknown_from_goal_count")
    if step.get("no_progress"):
        out.append("no_progress_recorded")
    return out


def _episode_notes(
    steps: list[dict[str, Any]],
) -> list[dict[str, str]]:
    notes: list[dict[str, str]] = []
    if not steps:
        return [{
            "code": "timeline.empty",
            "message": "No TacticExecutionResult steps are available yet.",
        }]
    unknown = [s for s in steps if s.get("transition_kind") == "committed_unknown_effect"]
    if unknown:
        notes.append({
            "code": "timeline.has_unknown_effect_steps",
            "message": (
                f"{len(unknown)} step(s) were committed but their goal-count "
                "effect was indeterminate; inspect the linked execution result "
                "if this matters for strategy."
            ),
        })
    if not any(
        is_session_completion_candidate(str(s.get("proof_status") or ""))
        for s in steps
    ):
        notes.append({
            "code": "timeline.no_session_completion_candidate_step",
            "message": (
                "No step committed an authoritative session completion "
                "candidate yet."
            ),
        })
    return notes


def _int(value: Any) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0
