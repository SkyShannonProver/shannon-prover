"""Live session episode timeline for prover agents.

TacticExecutionResult is the live post-command envelope. This module projects
those artifacts into an ordered episode timeline so an agent can review how it
got to the current proof state during an interactive run. Legacy CommandSummary
artifacts remain a fallback for old traces.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core.easycrypt.session_events import event_payload, read_events
from core.easycrypt.session_command_summary import command_summary_workspace_metrics
from core.easycrypt.value_shapes import as_dict as _dict, as_list as _list
from core.easycrypt.value_shapes import as_dict_list as _as_dict_list


SESSION_EPISODE_TIMELINE_SCHEMA_VERSION = 1
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
    items = _load_tactic_execution_results(path)
    source = "tactic_execution_result"
    if not items:
        items = _load_command_summaries(path)
        source = "legacy_command_summary"
    steps: list[dict[str, Any]] = []
    previous_goal_hash = ""
    for idx, item in enumerate(items, start=1):
        if "result" in item:
            step = _step_from_tactic_execution(
                idx=idx,
                item=item,
                previous_goal_hash=previous_goal_hash,
            )
        else:
            step = _step_from_command_summary(
                idx=idx,
                item=item,
                previous_goal_hash=previous_goal_hash,
            )
        steps.append(step)
        goal_hash = str(step.get("goal_hash") or "")
        if goal_hash:
            previous_goal_hash = goal_hash

    return {
        "schema_version": SESSION_EPISODE_TIMELINE_SCHEMA_VERSION,
        "kind": SESSION_EPISODE_TIMELINE_KIND,
        "ok": True,
        "session_dir": str(path.resolve()),
        "source": source,
        "step_count": len(steps),
        "rollup": _rollup(steps),
        "steps": steps,
        "notes": _episode_notes(steps, source=source),
        "errors": [],
    }


def _step_from_tactic_execution(
    *,
    idx: int,
    item: dict[str, Any],
    previous_goal_hash: str,
) -> dict[str, Any]:
    result = _dict(item.get("result"))
    execution = _dict(result.get("execution"))
    result_panel = _dict(result.get("result"))
    workspace = _dict(_dict(result.get("workspace")).get("view"))
    proof_position = _dict(workspace.get("proof_status") or workspace.get("proof_position"))
    current_goal = _dict(workspace.get("current_goal"))
    audit = _dict(result.get("audit"))
    metrics = _workspace_action_metrics(
        _workspace_action_panel(workspace)
    )
    goal_hash = str(audit.get("goal_hash") or "")
    proof_status = str(
        proof_position.get("status")
        or audit.get("proof_status")
        or "",
    )
    num_remaining = proof_position.get("remaining_goals")
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
    candidate_closed = proof_status in {
        "candidate_closed",
        "candidate_closed_pending_qed",
        "verified",
    }
    transition_kind = (
        "closed" if candidate_closed else
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
        "history_tactic_count": 0,
        "transition_kind": transition_kind,
        "transition_status": str(result_panel.get("status") or ""),
        "goals_before": None,
        "goals_after": num_remaining,
        "candidate_closed": candidate_closed,
        "no_progress": str(result_panel.get("status") or "") == "preflight_no_progress",
        "no_progress_reason": str(result_panel.get("failure_reason") or ""),
        "primary_action": str(metrics.get("primary_action") or ""),
        "runnable_tactic_count": _int(metrics.get("runnable_tactic_count")),
        "inspection_action_count": _int(metrics.get("inspection_action_count")),
        "strategy_hint_count": _int(metrics.get("strategy_hint_count")),
        "error_count": len(_list(result.get("errors"))),
        "warning_count": len(_list(result.get("notes"))),
        "artifact": str(item.get("path") or ""),
        "source": "tactic_execution_result",
    }
    step["prover_observations"] = _step_observations(step)
    return step


def _step_from_command_summary(
    *,
    idx: int,
    item: dict[str, Any],
    previous_goal_hash: str,
) -> dict[str, Any]:
    summary = item["summary"]
    proof = _dict(summary.get("proof"))
    transition = _dict(summary.get("transition"))
    mutation = _dict(summary.get("mutation"))
    current_goal = _dict(summary.get("current_goal"))
    workspace_metrics = command_summary_workspace_metrics(summary)
    goal_hash = str(proof.get("goal_hash") or "")
    step = {
        "step": idx,
        "event_index": _int(item.get("event_index")),
        "command": str(summary.get("command") or ""),
        "command_status": str(summary.get("command_status") or ""),
        "ok": bool(summary.get("ok")),
        "tactic": str(transition.get("tactic") or proof.get("latest_tactic") or ""),
        "accepted_count": _int(mutation.get("accepted_count")),
        "attempted_count": _int(mutation.get("attempted_count")),
        "rollback_count": _int(mutation.get("rollback_count")),
        "proof_status": str(proof.get("status") or ""),
        "goal_type": str(proof.get("goal_type") or current_goal.get("goal_type") or "unknown"),
        "num_remaining": proof.get("num_remaining"),
        "num_remaining_determined": bool(
            proof.get("num_remaining_determined")
        ),
        "goal_hash": goal_hash,
        "goal_hash_changed": bool(
            previous_goal_hash and goal_hash and goal_hash != previous_goal_hash
        ),
        "history_tactic_count": _int(proof.get("history_tactic_count")),
        "transition_kind": str(transition.get("kind") or ""),
        "transition_status": str(transition.get("status") or ""),
        "goals_before": transition.get("goals_before"),
        "goals_after": transition.get("goals_after"),
        "candidate_closed": bool(transition.get("candidate_closed")),
        "no_progress": bool(transition.get("no_progress")),
        "no_progress_reason": str(transition.get("no_progress_reason") or ""),
        "primary_action": str(workspace_metrics.get("primary_action") or ""),
        "runnable_tactic_count": _int(
            workspace_metrics.get("runnable_tactic_count")
        ),
        "inspection_action_count": _int(
            workspace_metrics.get("inspection_action_count")
        ),
        "strategy_hint_count": _int(
            workspace_metrics.get("strategy_hint_count")
        ),
        "error_count": len(_list(summary.get("errors"))),
        "warning_count": len(_list(summary.get("warnings"))),
        "artifact": str(item.get("path") or ""),
        "source": "legacy_command_summary",
    }
    step["prover_observations"] = _step_observations(step)
    return step


def _workspace_action_metrics(next_actions: dict[str, Any]) -> dict[str, Any]:
    actions = [
        _dict(next_actions.get("primary")),
        *_as_dict_list(next_actions.get("alternatives")),
        *_as_dict_list(next_actions.get("context_hints") or next_actions.get("background_hints")),
        *_as_dict_list(next_actions.get("avoid") or next_actions.get("blocked_or_avoid")),
    ]
    primary = actions[0] if actions else {}
    categories = Counter(str(action.get("category") or "") for action in actions)
    return {
        "primary_action": _primary_action_from_workspace(primary),
        "runnable_tactic_count": categories.get("commit", 0),
        "inspection_action_count": (
            categories.get("inspect", 0)
            + categories.get("diagnose", 0)
            + categories.get("verify", 0)
        ),
        "strategy_hint_count": categories.get("strategy", 0) + categories.get("hint", 0),
    }


def _workspace_action_panel(workspace: dict[str, Any]) -> dict[str, Any]:
    candidate_moves = _dict(workspace.get("candidate_moves"))
    if candidate_moves:
        moves = _as_dict_list(candidate_moves.get("moves"))
        limitations = _as_dict_list(candidate_moves.get("limitations"))
        inspect_lookup = _dict(workspace.get("inspect_lookup_handles"))
        handles = _as_dict_list(inspect_lookup.get("ask_manager_for")) + _as_dict_list(
            inspect_lookup.get("lookup_candidates")
        )
        primary = moves[0] if moves else (handles[0] if handles else {})
        return {
            "primary": primary,
            "alternatives": moves[1:],
            "context_hints": handles if moves else handles[1:],
            "avoid": limitations,
        }
    decision_context = _dict(workspace.get("decision_context"))
    if decision_context:
        options = _as_dict_list(decision_context.get("proof_options"))
        handles = _as_dict_list(decision_context.get("context_handles"))
        limitations = _as_dict_list(decision_context.get("limitations"))
        primary = options[0] if options else (handles[0] if handles else {})
        return {
            "primary": primary,
            "alternatives": options[1:],
            "context_hints": handles if options else handles[1:],
            "avoid": limitations,
        }
    return _dict(
        workspace.get("suggested_next_steps")
        or workspace.get("next_actions")
    )


def _primary_action_from_workspace(action: dict[str, Any]) -> str:
    category = str(action.get("category") or "")
    if category == "none":
        return "none"
    if category == "verify":
        return "verify"
    if category == "diagnose":
        return "diagnose"
    if category == "commit":
        return "try_tactic"
    if category in {"strategy", "hint"}:
        return "consider_strategy_hint"
    if category == "inspect":
        return "inspect"
    if category == "avoid":
        return "avoid"
    return "inspect"


def _load_tactic_execution_results(session_dir: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[Path] = set()
    events = read_events(session_dir)
    for idx, event in enumerate(events, start=1):
        if event.get("type") != "tactic.execution.produced":
            continue
        payload = event_payload(event)
        path = _resolve_artifact_path(
            session_dir,
            str(payload.get("artifact") or ""),
            copied_subdir="tactic_execution_results",
        )
        if path is None or path in seen:
            continue
        data = _read_json_object(path)
        if data:
            out.append({"path": path, "result": data, "event_index": idx})
            seen.add(path)
    result_dir = session_dir / "tactic_execution_results"
    if result_dir.exists():
        for path in sorted(result_dir.glob("*.json")):
            if path in seen:
                continue
            data = _read_json_object(path)
            if data:
                out.append({"path": path, "result": data, "event_index": 0})
                seen.add(path)
    return out


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
    out_dir = path / "episode_timelines"
    out_dir.mkdir(parents=True, exist_ok=True)
    artifact = out_dir / f"episode_timeline_{digest[:16]}.json"
    artifact.write_text(text + "\n", encoding="utf-8")
    rollup = _dict(data.get("rollup"))
    return {
        "schema_version": int(data.get("schema_version") or 0),
        "ok": bool(data.get("ok")),
        "artifact": str(artifact),
        "timeline_hash": digest,
        "step_count": _int(data.get("step_count")),
        "final_proof_status": str(rollup.get("final_proof_status") or ""),
        "final_primary_action": str(rollup.get("final_primary_action") or ""),
        "note_count": len(_list(data.get("notes"))),
        "error_count": len(_list(data.get("errors"))),
    }


def record_session_episode_timeline(
    session_or_dir: Any,
    timeline: dict[str, Any],
    *,
    source: str = "session_cli",
) -> dict[str, Any]:
    session_dir = getattr(session_or_dir, "dir", session_or_dir)
    payload = write_session_episode_timeline_artifact(session_dir, timeline)
    emit = getattr(session_or_dir, "emit_event", None)
    if callable(emit):
        emit("episode.timeline.produced", payload, source=source)
    return payload


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


def _load_command_summaries(session_dir: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[Path] = set()
    events = read_events(session_dir)
    for idx, event in enumerate(events, start=1):
        if event.get("type") != "command.summary.produced":
            continue
        payload = event_payload(event)
        path = _resolve_artifact_path(
            session_dir,
            str(payload.get("artifact") or ""),
            copied_subdir="command_summaries",
        )
        if path is None or path in seen:
            continue
        data = _read_json_object(path)
        if data:
            out.append({"path": path, "summary": data, "event_index": idx})
            seen.add(path)
    summary_dir = session_dir / "command_summaries"
    if summary_dir.exists():
        for path in sorted(summary_dir.glob("*.json")):
            if path in seen:
                continue
            data = _read_json_object(path)
            if data:
                out.append({"path": path, "summary": data, "event_index": 0})
                seen.add(path)
    return out


def _rollup(steps: list[dict[str, Any]]) -> dict[str, Any]:
    transition_counts = Counter(str(s.get("transition_kind") or "") for s in steps)
    primary_counts = Counter(str(s.get("primary_action") or "") for s in steps)
    proof_status_counts = Counter(str(s.get("proof_status") or "") for s in steps)
    return {
        "transition_counts": dict(sorted(transition_counts.items())),
        "primary_action_counts": dict(sorted(primary_counts.items())),
        "proof_status_counts": dict(sorted(proof_status_counts.items())),
        "failed_command_count": sum(1 for s in steps if not s.get("ok")),
        "no_progress_count": sum(1 for s in steps if s.get("no_progress")),
        "goal_hash_change_count": sum(1 for s in steps if s.get("goal_hash_changed")),
        "candidate_closed_step": next(
            (s["step"] for s in steps if s.get("proof_status") == "candidate_closed"),
            0,
        ),
        "final_primary_action": str(steps[-1].get("primary_action") or "") if steps else "",
        "final_proof_status": str(steps[-1].get("proof_status") or "") if steps else "",
    }


def _step_observations(step: dict[str, Any]) -> list[str]:
    out: list[str] = []
    if step.get("proof_status") == "candidate_closed":
        out.append("candidate_closed_verify_next")
    if step.get("proof_status") == "verified":
        out.append("verified_stop")
    if not step.get("ok"):
        out.append("failed_command_diagnose_next")
    if step.get("goal_hash_changed"):
        out.append("active_goal_changed")
    if step.get("transition_kind") == "state_changed_same_goal_count":
        out.append("same_goal_count_state_changed")
    if step.get("transition_kind") == "committed_unknown_effect":
        out.append("effect_unknown_from_goal_count")
    if step.get("primary_action") == "consider_strategy_hint":
        out.append("strategy_hint_before_direct_tactic")
    if step.get("primary_action") == "try_tactic":
        out.append("direct_tactic_available")
    if step.get("no_progress"):
        out.append("no_progress_recorded")
    return out


def _episode_notes(
    steps: list[dict[str, Any]],
    *,
    source: str = "tactic_execution_result",
) -> list[dict[str, str]]:
    notes: list[dict[str, str]] = []
    if not steps:
        return [{
            "code": "timeline.empty",
            "message": (
                "No TacticExecutionResult steps are available yet."
                if source == "tactic_execution_result" else
                "No legacy CommandSummary steps are available yet."
            ),
        }]
    unknown = [s for s in steps if s.get("transition_kind") == "committed_unknown_effect"]
    if unknown:
        notes.append({
            "code": "timeline.has_unknown_effect_steps",
            "message": (
                f"{len(unknown)} step(s) were committed but their goal-count "
                "effect was indeterminate; inspect the linked summary if this "
                "matters for strategy."
            ),
        })
    if not any(s.get("proof_status") == "candidate_closed" for s in steps):
        notes.append({
            "code": "timeline.no_candidate_closed_step",
            "message": "No step reached candidate_closed yet.",
        })
    repeated_strategy = sum(
        1 for s in steps if s.get("primary_action") == "consider_strategy_hint"
    )
    if repeated_strategy >= 3:
        notes.append({
            "code": "timeline.strategy_hint_heavy",
            "message": (
                f"{repeated_strategy} step(s) asked the prover to consider "
                "strategy hints; direct tactic guidance was not always enough."
            ),
        })
    return notes


def _resolve_artifact_path(
    session_dir: Path,
    value: str,
    *,
    copied_subdir: str,
) -> Path | None:
    if value:
        direct = Path(value)
        if direct.exists():
            return direct
        copied = session_dir / copied_subdir / direct.name
        if copied.exists():
            return copied
        if not direct.is_absolute():
            relative = session_dir / direct
            if relative.exists():
                return relative
    return None


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}





def _int(value: Any) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0
