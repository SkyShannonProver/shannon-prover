"""Legacy compact summary for historical session commands.

CommitResponse, ProofContextView, ProverWorkspaceView, and
TacticExecutionResult are the live manager contract.  CommandSummary remains as
a compatibility artifact for old traces, reports, and validators; it is not the
default agent-facing result.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from core.easycrypt.validation_result import ValidationResult

from core.easycrypt.session_prover_workspace_view import (  # type: ignore
    build_prover_workspace_view_from_context,
)
from core.easycrypt.session_prover_actions import (
    build_prover_actions,
    validate_prover_actions,
)
from core.easycrypt.value_shapes import as_dict as _dict, drop_empty as _drop_empty, as_list as _list


COMMAND_SUMMARY_SCHEMA_VERSION = 2
SUPPORTED_COMMAND_SUMMARY_SCHEMA_VERSIONS = {1, 2}
COMMAND_SUMMARY_KIND = "command_summary"


class CommandSummaryValidation(ValidationResult):
    """Canonical errors/warnings result under this view's public name."""


def build_command_workspace_view(
    session_dir: str | Path,
    *,
    commit_response: dict[str, Any],
    agent_view: dict[str, Any] | None = None,
    agent_view_payload: dict[str, Any] | None = None,
    max_recommendations: int = 3,
) -> tuple[dict[str, Any], str]:
    """Build a workspace view for legacy CommandSummary readers.

    Live tactic execution builds ProverWorkspaceView directly from
    ProofContextView. This helper remains for historical summaries that need to
    regenerate the old compact workspace slice.
    """
    path = Path(session_dir)
    agent_payload = agent_view_payload or {}
    if agent_view is None:
        agent_view = _load_json_object(agent_payload.get("artifact"))

    proof_state = _dict(commit_response.get("proof_state"))
    if not proof_state:
        proof_state = _dict((agent_view or {}).get("proof_state"))
    latest_errors = _compact_messages((agent_view or {}).get("latest_errors"))
    workspace_context_view, workspace_input_source = _context_view_for_workspace(
        path,
        agent_view or {},
        proof_state=proof_state,
        commit_response=commit_response,
        latest_errors=latest_errors,
        command_ok=bool(commit_response.get("ok")),
    )
    workspace_view = build_prover_workspace_view_from_context(
        workspace_context_view,
        proof_context_payload=agent_payload,
        max_alternatives=max_recommendations,
        max_evidence=5,
    )
    return workspace_view, workspace_input_source


def build_command_summary(
    session_dir: str | Path,
    *,
    commit_response: dict[str, Any],
    commit_response_payload: dict[str, Any] | None = None,
    agent_view: dict[str, Any] | None = None,
    agent_view_payload: dict[str, Any] | None = None,
    workspace_view: dict[str, Any] | None = None,
    workspace_payload: dict[str, Any] | None = None,
    workspace_input_source: str | None = None,
    max_recommendations: int = 3,
) -> dict[str, Any]:
    """Build one compact post-command summary."""
    path = Path(session_dir)
    commit_payload = commit_response_payload or {}
    agent_payload = agent_view_payload or {}
    if agent_view is None:
        agent_view = _load_json_object(agent_payload.get("artifact"))

    proof_state = _dict(commit_response.get("proof_state"))
    if not proof_state:
        proof_state = _dict((agent_view or {}).get("proof_state"))
    proof_goal = _dict(proof_state.get("goal"))
    proof_history = _dict(proof_state.get("history"))
    event_contract = _dict(proof_state.get("event_contract"))
    consistency = _dict(proof_state.get("consistency"))
    transition = _dict(
        commit_response.get("latest_transition")
        or proof_state.get("latest_transition")
        or (agent_view or {}).get("latest_transition")
    )
    mutation = _dict(commit_response.get("mutation"))
    current_goal = _dict((agent_view or {}).get("current_goal"))
    proof_ir = _dict((agent_view or {}).get("proof_ir"))
    command_ok = bool(commit_response.get("ok"))
    closed_status = str(proof_state.get("status") or "") in {
        "candidate_closed",
        "verified",
    }

    status = str(proof_state.get("status") or "")
    latest_errors = _compact_messages((agent_view or {}).get("latest_errors"))
    errors = _summary_errors(commit_response, proof_state, agent_view or {})
    warnings = _summary_warnings(proof_state, agent_view or {})
    active_recs_raw = _list(
        _dict((agent_view or {}).get("guidance")).get("recommendations")
    )
    workspace_artifact_payload = workspace_payload or {}
    if workspace_view is None:
        workspace_view, workspace_input_source = build_command_workspace_view(
            path,
            commit_response=commit_response,
            agent_view=agent_view,
            agent_view_payload=agent_payload,
            max_recommendations=max_recommendations,
        )
    if workspace_input_source is None:
        workspace_input_source = "unknown"
    workspace_slice = _command_workspace_slice(workspace_view)

    event_ok = bool(event_contract.get("ok", True))
    consistency_ok = bool(consistency.get("ok", True))
    summary = {
        "schema_version": COMMAND_SUMMARY_SCHEMA_VERSION,
        "kind": COMMAND_SUMMARY_KIND,
        "ok": bool(command_ok and event_ok and consistency_ok and not errors),
        "command": str(commit_response.get("command") or ""),
        "command_status": str(commit_response.get("status") or ""),
        "mutation": {
            "attempted_count": _int(mutation.get("attempted_count")),
            "accepted_count": _int(mutation.get("accepted_count")),
            "rollback_count": _int(mutation.get("rollback_count")),
            "history_committed": transition.get("history_committed"),
            "attempted_tactics": [
                str(item)
                for item in (mutation.get("attempted_tactics") or [])[:3]
                if isinstance(item, str) and item.strip()
            ],
            "failed_tactic": str(mutation.get("failed_tactic") or ""),
            "failure_reason": str(mutation.get("failure_reason") or ""),
        },
        "proof": {
            "status": status,
            "candidate_ready": bool(proof_state.get("candidate_ready")),
            "final_ready": bool(proof_state.get("final_ready")),
            "event_contract_ok": event_ok,
            "consistency_ok": consistency_ok,
            "goal_type": str(proof_goal.get("goal_type") or "unknown"),
            "num_remaining": proof_goal.get("num_remaining"),
            "num_remaining_determined": bool(
                proof_goal.get("num_remaining_determined")
            ),
            "goal_hash": str(proof_goal.get("active_goal_hash") or ""),
            "proof_ir_layer": str(proof_ir.get("current_layer") or ""),
            "proof_ir_goal_kind": str(proof_ir.get("goal_kind") or ""),
            "history_tactic_count": _int(proof_history.get("tactic_count")),
            "latest_tactic": str(proof_history.get("latest_tactic") or ""),
        },
        "transition": {
            "kind": str(transition.get("kind") or ""),
            "status": str(transition.get("status") or ""),
            "tactic": str(transition.get("tactic") or ""),
            "goals_before": transition.get("goals_before"),
            "goals_after": transition.get("goals_after"),
            "candidate_closed": bool(transition.get("candidate_closed")),
            "no_progress": bool(transition.get("no_progress")),
            "no_progress_reason": str(transition.get("no_progress_reason") or ""),
            "latest_error": str(transition.get("latest_error") or ""),
        },
        "current_goal": {
            "goal_type": (
                "complete"
                if closed_status
                else str(
                    current_goal.get("goal_type")
                    or proof_goal.get("goal_type")
                    or "unknown"
                )
            ),
            "state_kind": (
                "candidate_closed"
                if closed_status
                else str(
                    current_goal.get("state_kind")
                    or proof_goal.get("state_kind")
                    or ""
                )
            ),
            "num_remaining": (
                0
                if closed_status
                else current_goal.get(
                    "num_remaining",
                    proof_goal.get("num_remaining"),
                )
            ),
            "preview": _short_preview(str(current_goal.get("active_goal_preview") or "")),
        },
        "proof_ir": _compact_proof_ir(proof_ir),
        "workspace": workspace_slice,
        "latest_errors": latest_errors,
        "warnings": warnings,
        "errors": errors,
        "artifacts": {
            "agent_view": str(
                agent_payload.get("artifact")
                or _dict(commit_response.get("agent_view")).get("artifact")
                or ""
            ),
            "commit_response": str(commit_payload.get("artifact") or ""),
            "prover_workspace_view": str(
                workspace_artifact_payload.get("artifact") or ""
            ),
        },
        "debug": {
            "active_recommendation_count": len(active_recs_raw),
            "derived_recommendation_count": 0,
            "workspace_source": "prover_workspace_view",
            "workspace_input_source": workspace_input_source,
            "workspace_chars": _int(
                workspace_artifact_payload.get("workspace_chars")
            ),
            "workspace_current_goal_text_fully_shown": (
                workspace_artifact_payload.get("current_goal_text_fully_shown")
            ),
            "workspace_current_goal_truncated": workspace_artifact_payload.get(
                "current_goal_truncated"
            ),
            "stale_recommendation_count": _int(
                _dict((agent_view or {}).get("guidance")).get(
                    "stale_recommendation_count"
                )
            ),
            "session_dir": str(path.resolve()),
        },
    }
    validation = validate_command_summary(summary)
    if validation.errors:
        summary["errors"] = list(summary["errors"]) + [
            {"code": "command_summary.invalid", "message": err}
            for err in validation.errors
        ]
    if validation.warnings:
        summary["warnings"] = list(summary["warnings"]) + validation.warnings
    summary["ok"] = bool(
        summary["ok"]
        and not validation.errors
    )
    return summary


def write_command_summary_artifact(
    session_dir: str | Path,
    summary: dict[str, Any],
) -> dict[str, Any]:
    path = Path(session_dir)
    data = dict(summary)
    validation = validate_command_summary(data)
    text = json.dumps(data, indent=2, sort_keys=True)
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()
    command = str(data.get("command") or "command")
    safe_command = re.sub(r"[^A-Za-z0-9_.-]+", "_", command).strip("_") or "command"
    out_dir = path / "command_summaries"
    out_dir.mkdir(parents=True, exist_ok=True)
    artifact = out_dir / f"{safe_command}_{digest[:16]}.json"
    artifact.write_text(text + "\n", encoding="utf-8")

    proof = _dict(data.get("proof"))
    metrics = command_summary_workspace_metrics(data)
    artifacts = _dict(data.get("artifacts"))
    errors = data.get("errors")
    warnings = data.get("warnings")
    return {
        "schema_version": int(data.get("schema_version") or 0),
        "ok": bool(data.get("ok")) and validation.ok,
        "command": command,
        "command_status": str(data.get("command_status") or ""),
        "artifact": str(artifact),
        "summary_hash": digest,
        "proof_status": str(proof.get("status") or ""),
        "goal_hash": str(proof.get("goal_hash") or ""),
        "goal_type": str(proof.get("goal_type") or ""),
        "num_remaining": proof.get("num_remaining"),
        "history_tactic_count": _int(proof.get("history_tactic_count")),
        "transition_kind": str(_dict(data.get("transition")).get("kind") or ""),
        "primary_action": str(metrics.get("primary_action") or ""),
        "recommendation_count": _int(metrics.get("recommendation_count")),
        "error_count": (
            (len(errors) if isinstance(errors, list) else 0)
            + len(validation.errors)
        ),
        "warning_count": len(warnings) if isinstance(warnings, list) else 0,
        "commit_response_artifact": str(artifacts.get("commit_response") or ""),
        "agent_view_artifact": str(artifacts.get("agent_view") or ""),
        "prover_workspace_artifact": str(
            artifacts.get("prover_workspace_view") or ""
        ),
        "workspace_chars": _int(_dict(data.get("debug")).get("workspace_chars")),
    }


def record_command_summary(
    session_or_dir: Any,
    summary: dict[str, Any],
    *,
    source: str = "session_cli",
) -> dict[str, Any]:
    session_dir = getattr(session_or_dir, "dir", session_or_dir)
    payload = write_command_summary_artifact(session_dir, summary)
    emit = getattr(session_or_dir, "emit_event", None)
    if callable(emit):
        emit("command.summary.produced", payload, source=source)
    return payload


def format_command_summary(summary: dict[str, Any]) -> str:
    proof = _dict(summary.get("proof"))
    transition = _dict(summary.get("transition"))
    workspace_next = command_summary_workspace_suggested_next_steps(summary)
    metrics = command_summary_workspace_metrics(summary)
    primary = _dict(workspace_next.get("primary"))
    mutation = _dict(summary.get("mutation"))
    command_status = str(summary.get("command_status") or "")
    compact = {
        "ok": bool(summary.get("ok")),
        "command": str(summary.get("command") or ""),
        "command_status": command_status,
        "probe_accepted": command_status == "probe_accepted",
        "proof_status": str(proof.get("status") or ""),
        "goal_type": str(proof.get("goal_type") or ""),
        "num_remaining": proof.get("num_remaining"),
        "transition_kind": str(transition.get("kind") or ""),
        "accepted_count": _int(mutation.get("accepted_count")),
        "attempted_tactics": [
            str(item)
            for item in (mutation.get("attempted_tactics") or [])[:2]
            if isinstance(item, str) and item.strip()
        ],
        "failed_tactic": str(mutation.get("failed_tactic") or ""),
        "failure_reason": str(mutation.get("failure_reason") or ""),
        "primary": _drop_empty({
            "id": str(primary.get("id") or metrics.get("primary_action_id") or ""),
            "category": str(primary.get("category") or ""),
            "readiness": str(primary.get("readiness") or ""),
            "proof_state_effect": str(primary.get("proof_state_effect") or ""),
            "tool": str(primary.get("tool") or ""),
            "tactic": str(primary.get("tactic") or ""),
        }),
        "action_count": _int(metrics.get("action_count")),
        "error_count": len(summary.get("errors") or []),
    }
    return (
        "[COMMAND-SUMMARY]\n"
        + json.dumps(summary, indent=2, sort_keys=True)
        + "\n"
        + "[COMMAND-SUMMARY] compact-tail-safe "
        + json.dumps(compact, sort_keys=True)
        + "\n"
    )


def command_summary_workspace_suggested_next_steps(
    summary: dict[str, Any],
) -> dict[str, Any]:
    """Return a compatibility action panel from the workspace decision context.

    Current CommandSummary artifacts store ``workspace.decision_context``.
    Historical artifacts stored ``workspace.suggested_next_steps``.
    Historical v2 artifacts stored ``workspace.next_actions`` and v1 artifacts
    stored ``next`` as a command-summary-specific surface; this adapter keeps
    validators and offline audits compatible without writing those legacy
    surfaces into new artifacts.
    """
    workspace = _dict(summary.get("workspace"))
    candidate_moves = _dict(workspace.get("candidate_moves"))
    if candidate_moves or _dict(workspace.get("inspect_lookup_handles")):
        return _suggested_panel_from_candidate_moves(candidate_moves, workspace)
    decision_context = _dict(workspace.get("decision_context"))
    if decision_context:
        return _suggested_panel_from_decision_context(decision_context)
    workspace_next = _dict(workspace.get("suggested_next_steps"))
    if workspace_next:
        return workspace_next
    workspace_next = _dict(workspace.get("next_actions"))
    if workspace_next:
        return workspace_next
    legacy_next = _dict(summary.get("next"))
    if not legacy_next:
        return {}
    actions = [
        dict(action) for action in _list(legacy_next.get("actions"))
        if isinstance(action, dict)
    ]
    primary = actions[0] if actions else _action_from_legacy_primary(legacy_next)
    alternatives = actions[1:4] if actions else []
    return _drop_empty({
        "primary": primary,
        "alternatives": alternatives,
        "avoid": [],
    })


def _suggested_panel_from_decision_context(
    decision_context: dict[str, Any],
) -> dict[str, Any]:
    options = [
        _workspace_action_from_proof_option(item)
        for item in _list(decision_context.get("proof_options"))
        if isinstance(item, dict)
    ]
    options = [item for item in options if item]
    handles = [
        _workspace_action_from_context_handle(item)
        for item in _list(decision_context.get("context_handles"))
        if isinstance(item, dict)
    ]
    handles = [item for item in handles if item]
    limitations = [
        _workspace_action_from_limitation(item)
        for item in _list(decision_context.get("limitations"))
        if isinstance(item, dict)
    ]
    limitations = [item for item in limitations if item]
    primary = options[0] if options else (handles[0] if handles else {})
    alternatives = options[1:4] if options else []
    context_hints = handles if options else handles[1:]
    return _drop_empty({
        "primary": primary,
        "alternatives": alternatives,
        "context_hints": context_hints,
        "avoid": limitations,
    })


def _suggested_panel_from_candidate_moves(
    candidate_moves: dict[str, Any],
    workspace: dict[str, Any],
) -> dict[str, Any]:
    moves = [
        _workspace_action_from_proof_option(item)
        for item in _list(candidate_moves.get("moves"))
        if isinstance(item, dict)
    ]
    moves = [item for item in moves if item]
    inspect_lookup = _dict(workspace.get("inspect_lookup_handles"))
    handles = [
        _workspace_action_from_context_handle(item)
        for item in _list(inspect_lookup.get("ask_manager_for"))
        if isinstance(item, dict)
    ]
    handles += [
        _workspace_action_from_context_handle(item)
        for item in _list(inspect_lookup.get("lookup_candidates"))
        if isinstance(item, dict)
    ]
    handles = [item for item in handles if item]
    limitations = [
        _workspace_action_from_limitation(item)
        for item in _list(candidate_moves.get("limitations"))
        if isinstance(item, dict)
    ]
    primary = moves[0] if moves else (handles[0] if handles else {})
    return _drop_empty({
        "primary": primary,
        "alternatives": moves[1:4] if moves else [],
        "context_hints": handles if moves else handles[1:],
        "avoid": limitations,
    })



def command_summary_action_menu(summary: dict[str, Any]) -> list[dict[str, Any]]:
    """Return a validator/audit action list from workspace suggestions or v1 next."""
    legacy_next = _dict(summary.get("next"))
    if legacy_next and _list(legacy_next.get("actions")):
        return [
            dict(action) for action in _list(legacy_next.get("actions"))
            if isinstance(action, dict)
        ]
    return _actions_from_workspace_next(
        command_summary_workspace_suggested_next_steps(summary)
    )


def command_summary_action_partitions(summary: dict[str, Any]) -> dict[str, Any]:
    """Return workspace-native action partitions for validators and audits.

    The names here describe the ProverWorkspaceView action model rather than the
    historical CommandSummary bucket schema.  Historical v1 summaries are still
    adapted, but callers do not need to know whether the source artifact carried
    old ``next`` buckets or current ``workspace.suggested_next_steps`` actions.
    """
    legacy_next = _dict(summary.get("next"))
    if legacy_next:
        return {
            "source": "historical_next_buckets",
            "primary_action": str(legacy_next.get("primary_action") or ""),
            "primary_action_id": str(legacy_next.get("primary_action_id") or ""),
            "actions": _list(legacy_next.get("actions")),
            "safe_actions": _list(legacy_next.get("safe_next_actions")),
            "commit_actions": _list(legacy_next.get("runnable_tactics")),
            "probe_actions": _list(legacy_next.get("probe_tactics")),
            "inspect_actions": _list(legacy_next.get("inspection_actions")),
            "strategy_actions": _list(legacy_next.get("strategy_hints")),
            "avoid_actions": _list(legacy_next.get("warnings")),
            "recommendations": _list(legacy_next.get("recommendations")),
        }

    actions = command_summary_action_menu(summary)
    workspace_next = command_summary_workspace_suggested_next_steps(summary)
    primary = _dict(workspace_next.get("primary")) or (actions[0] if actions else {})
    if (
        not bool(summary.get("ok"))
        and str(summary.get("command_status") or "") != "no_progress_reverted"
    ):
        diagnose = next(
            (
                action for action in actions
                if str(action.get("category") or "") == "diagnose"
                or str(action.get("target") or "") == "diagnose"
            ),
            {},
        )
        if not diagnose:
            diagnose = _diagnose_action_from_summary(summary)
        if diagnose:
            primary = diagnose
            actions = [diagnose] + [action for action in actions if action is not diagnose]
    proof_status = str(_dict(summary.get("proof")).get("status") or "")
    return {
        "source": "workspace.decision_context",
        "primary_action": _primary_action_from_workspace_action(primary),
        "primary_action_id": str(primary.get("id") or ""),
        "actions": actions,
        "safe_actions": _safe_next_from_workspace_actions(actions),
        "commit_actions": _bucket_workspace_actions(actions, "commit"),
        "probe_actions": _bucket_workspace_actions(actions, "probe"),
        "inspect_actions": _inspection_actions_from_workspace(actions),
        "strategy_actions": _strategy_hints_from_workspace(actions),
        "avoid_actions": _warnings_from_workspace(actions),
        "recommendations": _recommendations_from_workspace_actions(
            actions,
            proof_status=proof_status,
        ),
    }


def command_summary_workspace_metrics(summary: dict[str, Any]) -> dict[str, Any]:
    """Return stable event/audit counts from the canonical workspace surface.

    Historical v1 artifacts may only contain old ``next`` buckets.  This
    adapter reads them for compatibility, but callers get workspace-oriented
    metric names instead of depending on the bucket schema directly.
    """
    legacy_next = _dict(summary.get("next"))
    if legacy_next and not _list(legacy_next.get("actions")):
        runnable = _list(legacy_next.get("runnable_tactics"))
        probe = _list(legacy_next.get("probe_tactics"))
        inspections = _list(legacy_next.get("inspection_actions"))
        strategy = _list(legacy_next.get("strategy_hints"))
        warnings = _list(legacy_next.get("warnings"))
        recs = _list(legacy_next.get("recommendations"))
        return {
            "source": "historical_next_buckets",
            "primary_action": str(legacy_next.get("primary_action") or ""),
            "primary_action_id": str(legacy_next.get("primary_action_id") or ""),
            "action_count": sum(
                len(items)
                for items in (runnable, probe, inspections, strategy)
            ),
            "runnable_tactic_count": len(runnable),
            "probe_tactic_count": len(probe),
            "inspection_action_count": len(inspections),
            "strategy_hint_count": len(strategy),
            "warning_count": len(warnings),
            "recommendation_count": len(recs),
        }

    actions = command_summary_action_menu(summary)
    workspace_next = command_summary_workspace_suggested_next_steps(summary)
    primary = _dict(workspace_next.get("primary")) or (actions[0] if actions else {})
    if (
        not bool(summary.get("ok"))
        and str(summary.get("command_status") or "") != "no_progress_reverted"
    ):
        diagnose = next(
            (
                action for action in actions
                if str(action.get("category") or "") == "diagnose"
                or str(action.get("target") or "") == "diagnose"
            ),
            {},
        ) or _diagnose_action_from_summary(summary)
        if diagnose:
            primary = diagnose
            actions = [diagnose] + [action for action in actions if action is not diagnose]
    proof_status = str(_dict(summary.get("proof")).get("status") or "")
    return {
        "source": "workspace.decision_context",
        "primary_action": _primary_action_from_workspace_action(primary),
        "primary_action_id": str(primary.get("id") or ""),
        "action_count": len(actions),
        "runnable_tactic_count": len(_bucket_workspace_actions(actions, "commit")),
        "probe_tactic_count": len(_bucket_workspace_actions(actions, "probe")),
        "inspection_action_count": len(_inspection_actions_from_workspace(actions)),
        "strategy_hint_count": len(_strategy_hints_from_workspace(actions)),
        "warning_count": len(_warnings_from_workspace(actions)),
        "recommendation_count": len(_recommendations_from_workspace_actions(
            actions,
            proof_status=proof_status,
        )),
    }



def _diagnose_action_from_summary(summary: dict[str, Any]) -> dict[str, Any]:
    mutation = _dict(summary.get("mutation"))
    failed = str(mutation.get("failed_tactic") or "")
    failure = str(mutation.get("failure_reason") or "")
    return _drop_empty({
        "id": "diagnose.latest_failure",
        "category": "diagnose",
        "title": _title_for_action({"category": "diagnose"}),
        "why": "Classify the latest tactic failure before trying another proof step.",
        "state_changed": False,
        "target": "diagnose",
        "tactic": failed,
        "error": failure,
        "proof_state_effect": "read-only; proof state unchanged",
    })


def _context_view_for_workspace(
    session_dir: Path,
    agent_view: dict[str, Any],
    *,
    proof_state: dict[str, Any],
    commit_response: dict[str, Any],
    latest_errors: list[dict[str, Any]],
    command_ok: bool,
) -> tuple[dict[str, Any], str]:
    """Return a ProofContextView-shaped input for the workspace manager.

    Normal live paths already pass a full ProofContextView with canonical
    ``actions``.  Tests and older artifacts may only contain guidance and
    safe_next_actions; for those, regenerate the same action list that
    ProofContextView would have carried, then let ProverWorkspaceView own the
    visible surface.
    """
    view = _json_clone(agent_view)
    if not view:
        view = {}
    view.setdefault("kind", "proof_context_view")
    view.setdefault("ok", True)
    if not _dict(view.get("proof_state")):
        view["proof_state"] = proof_state
    view.setdefault("latest_errors", latest_errors)
    view.setdefault("safe_next_actions", [])
    guidance = _dict(view.get("guidance"))
    recs = [
        dict(item) for item in _list(guidance.get("recommendations"))
        if isinstance(item, dict)
    ]
    input_source = (
        "proof_context_actions"
        if _list(view.get("actions"))
        else "compat_actions_regenerated"
    )

    probe_commit_rec = _probe_accepted_recommendation(
        commit_response,
        proof_state=proof_state,
        current_goal=_dict(view.get("current_goal")),
    )
    if probe_commit_rec and not _has_recommendation_id(
        recs,
        str(probe_commit_rec.get("id") or ""),
    ):
        recs = [probe_commit_rec, *recs]
        guidance = dict(guidance)
        guidance["recommendations"] = recs
        view["guidance"] = guidance
        input_source = "mutation_probe_result_plus_context"

    if not _list(view.get("actions")) or probe_commit_rec:
        actions = build_prover_actions(
            session_dir=session_dir,
            proof_state=_dict(view.get("proof_state")),
            recommendations=recs,
            safe_next_actions=_list(view.get("safe_next_actions")),
            latest_errors=latest_errors,
            command_ok=command_ok,
        )
        if probe_commit_rec:
            actions = _prioritize_action_id(
                actions,
                f"{_safe_summary_id(str(probe_commit_rec['id']))}.commit",
            )
        view["actions"] = actions
    return view, input_source


def _command_workspace_slice(workspace_view: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": "prover_workspace_view",
        "current_goal": _dict(workspace_view.get("current_goal")),
        "proof_status": _dict(workspace_view.get("proof_status")),
        "program_frontier": _dict(workspace_view.get("program_frontier")),
        "application_context": _dict(workspace_view.get("application_context")),
        "facts_and_diagnostics": _dict(
            workspace_view.get("facts_and_diagnostics")
        ),
        "candidate_moves": _dict(workspace_view.get("candidate_moves")),
        "last_result": _dict(workspace_view.get("last_result")),
        "inspect_lookup_handles": _dict(
            workspace_view.get("inspect_lookup_handles")
            or workspace_view.get("want_more_context")
            or workspace_view.get("more_context")
            or workspace_view.get("inspect_more")
        ),
    }


def _actions_from_workspace_next(next_block: dict[str, Any]) -> list[dict[str, Any]]:
    ordered: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in [
        _dict(next_block.get("primary")),
        *_list(next_block.get("alternatives")),
        *_list(next_block.get("context_hints") or next_block.get("background_hints")),
        *_list(next_block.get("avoid") or next_block.get("blocked_or_avoid")),
    ]:
        if not isinstance(item, dict) or not item:
            continue
        action = dict(item)
        if str(action.get("category") or "") == "hint":
            action["category"] = "strategy"
            action.setdefault(
                "guidance",
                " ".join(
                    part for part in (
                        str(action.get("handle") or ""),
                        str(action.get("target") or ""),
                    )
                    if part
                ),
            )
        action.setdefault("title", _title_for_action(action))
        action.setdefault("why", "Projected from ProverWorkspaceView.")
        action.setdefault("state_changed", action.get("category") == "commit")
        if action.get("needs_instantiation") and not action.get(
            "requires_instantiation"
        ):
            action["requires_instantiation"] = True
        if not action.get("tool"):
            tool = _compat_tool_for_workspace_action(action)
            if tool:
                action["tool"] = tool
        action_id = str(action.get("id") or f"workspace.{len(ordered)}")
        if action_id in seen:
            continue
        action["id"] = action_id
        seen.add(action_id)
        ordered.append(action)
    return ordered


def _workspace_action_from_proof_option(option: dict[str, Any]) -> dict[str, Any]:
    category = str(option.get("category") or "strategy")
    requires_instantiation = bool(
        option.get("requires_instantiation")
        or option.get("needs_instantiation")
        or option.get("missing_input")
        or str(option.get("runnable_status") or "").startswith("Not yet;")
    )
    action: dict[str, Any] = {
        "id": str(option.get("id") or ""),
        "category": category,
        "title": _title_for_action({"category": category}),
        "why": " ".join(str(item) for item in _list(option.get("evidence"))[:1])
        or str(option.get("use_when") or ""),
        "state_changed": category == "commit",
        "tactic": str(option.get("tactic") or ""),
        "guidance": str(option.get("guidance") or ""),
        "proof_state_effect": str(option.get("effect") or ""),
        "confidence": str(option.get("confidence") or ""),
        "source": str(option.get("source") or ""),
        "requires_instantiation": requires_instantiation,
    }
    return _drop_empty(action)


def _workspace_action_from_context_handle(handle: dict[str, Any]) -> dict[str, Any]:
    payload = _dict(handle.get("payload"))
    topic = str(payload.get("topic") or "").strip()
    kind = str(handle.get("kind") or topic or "lookup_symbol")
    target = str(handle.get("target") or handle.get("symbol") or topic or "").strip()
    category = str(handle.get("category") or "")
    if category not in {"inspect", "diagnose", "verify"}:
        category = "diagnose" if target == "diagnose" else "inspect"
    action = {
        "id": str(handle.get("id") or ""),
        "category": category,
        "title": _title_for_action({"category": category}),
        "why": str(handle.get("use_when") or ""),
        "state_changed": False,
        "handle": kind,
        "target": target,
        "proof_state_effect": str(handle.get("effect") or "read-only; proof state unchanged"),
        "source": str(handle.get("source") or ""),
    }
    return _drop_empty(action)


def _workspace_action_from_limitation(item: dict[str, Any]) -> dict[str, Any]:
    return _drop_empty({
        "id": str(item.get("id") or ""),
        "category": "avoid",
        "title": _title_for_action({"category": "avoid"}),
        "why": str(item.get("detail") or ""),
        "state_changed": False,
        "source": str(item.get("source") or ""),
    })


def _action_from_legacy_primary(legacy_next: dict[str, Any]) -> dict[str, Any]:
    primary_action = str(legacy_next.get("primary_action") or "")
    primary_id = str(legacy_next.get("primary_action_id") or "legacy.primary")
    category = {
        "none": "none",
        "verify": "verify",
        "diagnose": "diagnose",
        "probe_tactic": "probe",
        "try_tactic": "commit",
        "consider_strategy_hint": "strategy",
        "inspect": "inspect",
        "avoid": "avoid",
    }.get(primary_action, "inspect")
    return {
        "id": primary_id,
        "category": category,
        "title": _title_for_action({"category": category}),
        "why": "Projected from a historical CommandSummary v1 next block.",
        "state_changed": category == "commit",
    }


def _bucket_workspace_actions(
    actions: list[dict[str, Any]],
    category: str,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for action in actions:
        if str(action.get("category") or "") != category:
            continue
        out.append(_drop_empty({
            "id": str(action.get("recommendation_id") or action.get("id") or ""),
            "tactic": str(action.get("tactic") or ""),
            "producer": str(action.get("source") or ""),
            "confidence": str(action.get("confidence") or ""),
            "why": str(action.get("why") or ""),
            "source": str(action.get("source") or ""),
            "goal_hash": str(action.get("goal_hash") or ""),
        }))
    return out[:3]


def _inspection_actions_from_workspace(
    actions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for action in actions:
        if str(action.get("category") or "") not in {"inspect", "diagnose", "verify"}:
            continue
        out.append({
            "id": str(action.get("id") or ""),
            "tool": str(action.get("tool") or action.get("handle") or ""),
            "handle": str(action.get("handle") or action.get("tool") or ""),
            "target": str(action.get("target") or ""),
            "command": str(action.get("command") or ""),
            "kind": str(action.get("category") or ""),
            "why": str(action.get("why") or ""),
            "requires_instantiation": bool(
                action.get("requires_instantiation")
                or action.get("needs_instantiation")
            ),
        })
    return out[:3]


def _strategy_hints_from_workspace(
    actions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for action in actions:
        if str(action.get("category") or "") != "strategy":
            continue
        out.append({
            "id": str(action.get("recommendation_id") or action.get("id") or ""),
            "message": str(
                action.get("tactic_shape")
                or action.get("guidance")
                or action.get("tactic")
                or action.get("command")
                or action.get("why")
                or action.get("title")
                or ""
            ),
            "producer": str(action.get("source") or ""),
            "confidence": str(action.get("confidence") or ""),
            "why": str(action.get("why") or ""),
            "source": str(action.get("source") or ""),
            "requires_instantiation": bool(
                action.get("requires_instantiation")
                or action.get("needs_instantiation")
            ),
        })
    return out[:3]


def _warnings_from_workspace(actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for action in actions:
        if str(action.get("category") or "") != "avoid":
            continue
        out.append({
            "id": str(action.get("recommendation_id") or action.get("id") or ""),
            "message": str(action.get("why") or action.get("title") or ""),
            "producer": str(action.get("source") or ""),
            "confidence": str(action.get("confidence") or ""),
            "source": str(action.get("source") or ""),
        })
    return out[:3]


def _safe_next_from_workspace_actions(
    actions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    safe: list[dict[str, Any]] = []
    for action in actions:
        category = str(action.get("category") or "")
        if category == "commit":
            continue
        item = {
            "id": str(action.get("id") or ""),
            "kind": category,
            "why": str(action.get("why") or ""),
            "requires_instantiation": bool(
                action.get("requires_instantiation")
                or action.get("needs_instantiation")
            ),
        }
        for key in (
            "tool",
            "handle",
            "target",
            "command",
            "tactic",
            "confidence",
            "recommendation_id",
        ):
            if action.get(key) not in (None, "", [], {}):
                item[key] = str(action.get(key))
        for key in ("guidance", "tactic_shape"):
            if action.get(key) not in (None, "", [], {}):
                item[key] = str(action.get(key))
        safe.append(item)
    return safe[:3]


def _recommendations_from_workspace_actions(
    actions: list[dict[str, Any]],
    *,
    proof_status: str,
) -> list[dict[str, Any]]:
    if proof_status in {"candidate_closed", "verified", "candidate_closed_pending_qed"}:
        return []
    recs: list[dict[str, Any]] = []
    for action in actions:
        category = str(action.get("category") or "")
        action_text = str(
            action.get("tactic")
            or action.get("command")
            or action.get("tactic_shape")
            or action.get("guidance")
            or ""
        )
        if not action_text and category in {"strategy", "avoid"}:
            action_text = str(action.get("why") or action.get("title") or "")
        if not action_text:
            continue
        recs.append({
            "id": str(action.get("recommendation_id") or action.get("id") or ""),
            "kind": category,
            "producer": str(action.get("source") or "ProverWorkspaceView"),
            "action": action_text,
            "why": str(action.get("why") or ""),
            "confidence": str(action.get("confidence") or ""),
            "action_type": _action_type_from_category(category),
            "category": _action_type_from_category(category),
            "source": str(action.get("source") or "ProverWorkspaceView"),
            "goal_hash": str(action.get("goal_hash") or ""),
            "metadata": {
                "projection_source": "workspace.decision_context",
                "proof_state_effect": str(action.get("proof_state_effect") or ""),
            },
        })
    return recs[:3]


def _primary_action_from_workspace_action(action: dict[str, Any]) -> str:
    category = str(action.get("category") or "")
    if category == "none":
        return "none"
    if category == "verify":
        return "verify"
    if category == "diagnose":
        return "diagnose"
    if category == "probe":
        return "probe_tactic"
    if category == "commit":
        return "try_tactic"
    if category == "strategy":
        return "consider_strategy_hint"
    if category == "inspect":
        return "inspect"
    if category == "avoid":
        return "avoid"
    return "inspect"


def _compat_tool_for_workspace_action(action: dict[str, Any]) -> str:
    category = str(action.get("category") or "")
    if category == "commit":
        return "next"
    if category == "probe":
        return "try"
    if category in {"inspect", "diagnose", "verify", "hint"}:
        return str(action.get("handle") or category)
    return ""


def _action_type_from_category(category: str) -> str:
    return {
        "commit": "runnable_tactic",
        "probe": "probe_tactic",
        "inspect": "inspection_action",
        "diagnose": "inspection_action",
        "verify": "inspection_action",
        "strategy": "strategy_hint",
        "avoid": "warning",
    }.get(category, "strategy_hint")


def _title_for_action(action: dict[str, Any]) -> str:
    return {
        "commit": "Commit runnable tactic",
        "probe": "Probe tactic without changing proof state",
        "inspect": "Inspect proof state",
        "diagnose": "Diagnose latest error",
        "verify": "Verify closed proof",
        "strategy": "Reason about strategy hint",
        "avoid": "Avoid action",
        "none": "No action needed",
    }.get(str(action.get("category") or ""), "Inspect proof state")


def _has_recommendation_id(recs: list[dict[str, Any]], rec_id: str) -> bool:
    return bool(rec_id) and any(
        str(rec.get("id") or "") == rec_id for rec in recs
    )


def _json_clone(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    try:
        cloned = json.loads(json.dumps(value))
    except Exception:
        return dict(value)
    return cloned if isinstance(cloned, dict) else {}


def _probe_accepted_recommendation(
    commit_response: dict[str, Any],
    *,
    proof_state: dict[str, Any],
    current_goal: dict[str, Any],
) -> dict[str, Any]:
    if str(commit_response.get("status") or "") != "probe_accepted":
        return {}
    mutation = _dict(commit_response.get("mutation"))
    tactic = next(
        (
            str(item).strip()
            for item in (mutation.get("attempted_tactics") or [])
            if isinstance(item, str) and item.strip()
        ),
        "",
    )
    if not tactic:
        return {}
    proof_goal = _dict(proof_state.get("goal"))
    goal_hash = str(
        current_goal.get("active_goal_hash")
        or proof_goal.get("active_goal_hash")
        or ""
    )
    return {
        "id": "try.commit_accepted_tactic",
        "kind": "tactic_candidate",
        "producer": "try",
        "action": tactic,
        "why": "The last -try probe accepted this tactic without mutating proof state.",
        "action_type": "runnable_tactic",
        "confidence": "verified",
        "evidence_refs": [
            "probe.try.result",
            "epistemic.try.daemon_probe_accepted",
        ],
        "metadata": {
            "cost": "cheap",
            "epistemic_status": "daemon_probe_accepted",
            "recommended_commit_tool": "next",
            "source_goal_hash": goal_hash,
            "state_changed": False,
        },
    }


def _prioritize_action_id(
    actions: list[dict[str, Any]],
    action_id: str,
) -> list[dict[str, Any]]:
    if not action_id:
        return actions
    matching = [
        action for action in actions
        if isinstance(action, dict) and str(action.get("id") or "") == action_id
    ]
    if not matching:
        return actions
    return [
        *matching,
        *[
            action for action in actions
            if not (
                isinstance(action, dict)
                and str(action.get("id") or "") == action_id
            )
        ],
    ]


def validate_command_summary(data: dict[str, Any]) -> CommandSummaryValidation:
    errors: list[str] = []
    warnings: list[str] = []
    schema_version = data.get("schema_version")
    required = {
        "schema_version": int,
        "kind": str,
        "ok": bool,
        "command": str,
        "command_status": str,
        "mutation": dict,
        "proof": dict,
        "transition": dict,
        "current_goal": dict,
        "latest_errors": list,
        "warnings": list,
        "errors": list,
        "artifacts": dict,
        "debug": dict,
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
    if schema_version not in SUPPORTED_COMMAND_SUMMARY_SCHEMA_VERSIONS:
        errors.append(
            "schema_version must be one of "
            f"{sorted(SUPPORTED_COMMAND_SUMMARY_SCHEMA_VERSIONS)}, "
            f"got {schema_version!r}"
        )
    if schema_version == 1:
        if not isinstance(data.get("next"), dict):
            errors.append("schema v1 requires top-level `next`")
    if schema_version == COMMAND_SUMMARY_SCHEMA_VERSION:
        if not isinstance(data.get("workspace"), dict):
            errors.append("schema v2 requires `workspace`")
        if "next" in data:
            errors.append(
                "schema v2 must not expose top-level `next`; use "
                "workspace.decision_context"
            )
    if data.get("kind") != COMMAND_SUMMARY_KIND:
        errors.append(f"kind must be {COMMAND_SUMMARY_KIND!r}")
    mutation = _dict(data.get("mutation"))
    for key in ("attempted_count", "accepted_count", "rollback_count"):
        value = mutation.get(key)
        if not isinstance(value, int) or value < 0:
            errors.append(f"mutation.{key} must be a non-negative int")
    attempted = mutation.get("attempted_count")
    accepted = mutation.get("accepted_count")
    if isinstance(attempted, int) and isinstance(accepted, int) and accepted > attempted:
        errors.append("mutation.accepted_count cannot exceed attempted_count")
    proof = _dict(data.get("proof"))
    if proof.get("status") in ("candidate_closed", "verified"):
        metrics = command_summary_workspace_metrics(data)
        if _int(metrics.get("recommendation_count")):
            errors.append("closed proof cannot expose tactic recommendations")
    if data.get("ok") is True and data.get("errors"):
        errors.append("ok summary cannot contain errors")
    action_validation = validate_prover_actions(
        command_summary_action_menu(data),
        label="workspace.decision_context.actions",
    )
    errors.extend(action_validation.errors)
    warnings.extend(action_validation.warnings)
    if schema_version == 1:
        compat_next = _dict(data.get("next"))
        safe_actions = compat_next.get("safe_next_actions")
        if safe_actions is not None and not isinstance(safe_actions, list):
            errors.append("next.safe_next_actions must be a list")
        for key in (
            "runnable_tactics",
            "probe_tactics",
            "inspection_actions",
            "strategy_hints",
            "warnings",
        ):
            value = compat_next.get(key)
            if value is not None and not isinstance(value, list):
                errors.append(f"next.{key} must be a list")
    return CommandSummaryValidation(errors=errors, warnings=warnings)


def _compact_messages(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    out: list[dict[str, str]] = []
    for item in value[:5]:
        if isinstance(item, dict):
            compact = {
                "code": str(item.get("code") or ""),
                "message": str(item.get("message") or ""),
                "tactic": str(item.get("tactic") or ""),
            }
            for key in (
                "origin",
                "severity",
                "temporal_scope",
                "attempt_kind",
                "attempt_status",
                "current_attempt_status",
                "relation_to_current_attempt",
            ):
                if item.get(key) is not None:
                    compact[key] = str(item.get(key) or "")
            out.append(compact)
        else:
            out.append({"code": "message", "message": str(item), "tactic": ""})
    return out


def _summary_errors(
    commit_response: dict[str, Any],
    proof_state: dict[str, Any],
    agent_view: dict[str, Any],
) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    for item in commit_response.get("errors") or []:
        errors.append(_message(item, default_code="commit_response.error"))
    for item in agent_view.get("errors") or []:
        errors.append(_message(item, default_code="agent_view.error"))
    event_contract = _dict(proof_state.get("event_contract"))
    for item in event_contract.get("errors") or []:
        errors.append({"code": "event_contract.error", "message": str(item)})
    consistency = _dict(proof_state.get("consistency"))
    for item in consistency.get("errors") or []:
        errors.append({"code": "consistency.error", "message": str(item)})
    mutation = _dict(commit_response.get("mutation"))
    if not commit_response.get("ok"):
        reason = str(mutation.get("failure_reason") or "").strip()
        if reason:
            errors.append({
                "code": "command.failed",
                "message": reason,
                "tactic": str(mutation.get("failed_tactic") or ""),
            })
    deduped: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in errors:
        key = (item.get("message", ""), item.get("tactic", ""))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _summary_warnings(
    proof_state: dict[str, Any],
    agent_view: dict[str, Any],
) -> list[str]:
    warnings: list[str] = []
    for bucket in ("event_contract", "consistency"):
        for item in _dict(proof_state.get(bucket)).get("warnings") or []:
            warnings.append(str(item))
        for item in _dict(proof_state.get(bucket)).get("notes") or []:
            warnings.append(str(item))
    for item in agent_view.get("notes") or []:
        if isinstance(item, dict):
            msg = str(item.get("message") or "")
        else:
            msg = str(item)
        if msg:
            warnings.append(msg)
    return warnings[:8]


def _compact_proof_ir(proof_ir: dict[str, Any]) -> dict[str, Any]:
    if not proof_ir:
        return {}
    phase = _dict(proof_ir.get("phase"))
    return {
        "current_layer": str(proof_ir.get("current_layer") or ""),
        "goal_kind": str(proof_ir.get("goal_kind") or ""),
        "resource_summary": _dict(phase.get("resource_summary")),
        "phase_legality": {
            str(name): {
                "status": str(_dict(rule).get("status") or ""),
                "reason": str(_dict(rule).get("reason") or ""),
            }
            for name, rule in (_dict(phase.get("legality"))).items()
            if name in {
                "rewrite",
                "pr_bridge",
                "signature_lookup",
                "call_named_equiv",
                "targeted_inline",
                "inline_all",
                "procedure_transform",
                "ambient_close",
            }
        },
        "diagnostics": [
            {
                "code": str(item.get("code") or ""),
                "severity": str(item.get("severity") or ""),
                "message": str(item.get("message") or ""),
            }
            for item in (proof_ir.get("diagnostics") or [])[:3]
            if isinstance(item, dict)
        ],
        "external_candidates": [
            {
                "id": str(item.get("id") or ""),
                "producer": str(item.get("producer") or ""),
                "tactic_family": str(item.get("tactic_family") or ""),
                "action": str(item.get("action") or ""),
                "cost": str(item.get("cost") or ""),
                "verified": bool(item.get("verified")),
            }
            for item in (
                _dict(proof_ir.get("resources")).get("external_candidates")
                or []
            )[:4]
            if isinstance(item, dict)
        ],
        "name_resolution": _compact_name_resolution(
            _dict(_dict(proof_ir.get("resources")).get("name_resolution"))
        ),
        "instantiation_bindings": _compact_instantiation_bindings(
            _dict(_dict(proof_ir.get("resources")).get("instantiation_bindings"))
        ),
        "pr_path_plan": _compact_pr_path_plan(
            _dict(_dict(proof_ir.get("resources")).get("pr_path_plan"))
        ),
        "candidate_menu": [
            {
                "id": str(item.get("id") or ""),
                "tactic_family": str(item.get("tactic_family") or ""),
                "tactic": str(item.get("tactic") or ""),
                "action_type": str(item.get("action_type") or ""),
                "cost": str(item.get("cost") or ""),
                "why": str(item.get("why") or ""),
            }
            for item in (proof_ir.get("candidate_menu") or [])[:4]
            if isinstance(item, dict)
        ],
    }


def _compact_pr_path_plan(pr_path_plan: dict[str, Any]) -> dict[str, Any]:
    if not pr_path_plan:
        return {}
    recommended = _dict(pr_path_plan.get("recommended_path"))
    partials = [
        _dict(item)
        for item in (pr_path_plan.get("partial_paths") or [])[:3]
        if isinstance(item, dict)
    ]
    return {
        "summary": _dict(pr_path_plan.get("summary")),
        "recommended_path": (
            {
                "endpoint_id": str(recommended.get("endpoint_id") or ""),
                "relation": str(recommended.get("relation") or ""),
                "source_key": str(recommended.get("source_key") or ""),
                "target_key": str(recommended.get("target_key") or ""),
                "hop_count": int(recommended.get("hop_count") or 0),
                "lemmas": [
                    str(item) for item in (recommended.get("lemmas") or [])[:5]
                ],
                "hops": _compact_pr_path_hops(recommended),
            }
            if recommended else
            {}
        ),
        "partial_paths": [
            {
                "endpoint_id": str(partial.get("endpoint_id") or ""),
                "side": str(partial.get("side") or ""),
                "root_key": str(partial.get("root_key") or ""),
                "frontier_key": str(partial.get("frontier_key") or ""),
                "opposite_key": str(partial.get("opposite_key") or ""),
                "hop_count": int(partial.get("hop_count") or 0),
                "lemmas": [
                    str(item) for item in (partial.get("lemmas") or [])[:5]
                ],
                "hops": _compact_pr_path_hops(partial),
            }
            for partial in partials
        ],
    }


def _compact_pr_path_hops(path: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {
            "lemma": str(hop.get("lemma") or ""),
            "edge_kind": str(hop.get("edge_kind") or ""),
            "source": str(hop.get("source") or ""),
            "target": str(hop.get("target") or ""),
            "direction": str(hop.get("direction") or ""),
            "action_hint": str(hop.get("action_hint") or ""),
        }
        for hop in (path.get("hops") or [])[:4]
        if isinstance(hop, dict)
    ]


def _compact_name_resolution(name_resolution: dict[str, Any]) -> dict[str, Any]:
    if not name_resolution:
        return {}
    return {
        "summary": _dict(name_resolution.get("summary")),
        "signature_artifact_count": len(
            name_resolution.get("signature_artifacts") or []
        ),
        "lookup_actions": [
            str(action) for action in (name_resolution.get("lookup_actions") or [])[:4]
        ],
        "items": [
            {
                "name": str(item.get("name") or ""),
                "handle_kind": str(item.get("handle_kind") or ""),
                "resolution_status": str(item.get("resolution_status") or ""),
                "source_kind": str(item.get("source_kind") or ""),
                "exact_signature_known": bool(item.get("exact_signature_known")),
                "signature_lookup_action": str(
                    item.get("signature_lookup_action") or ""
                ),
                "tactic_template": str(item.get("tactic_template") or ""),
                "procedure_match": str(item.get("procedure_match") or ""),
                "parameter_slots": [
                    {
                        "kind": str(slot.get("kind") or ""),
                        "name": str(slot.get("name") or ""),
                        "placeholder": str(slot.get("placeholder") or ""),
                    }
                    for slot in (item.get("parameter_slots") or [])[:6]
                    if isinstance(slot, dict)
                ],
            }
            for item in (name_resolution.get("items") or [])[:4]
            if isinstance(item, dict)
        ],
    }


def _compact_instantiation_bindings(bindings: dict[str, Any]) -> dict[str, Any]:
    if not bindings:
        return {}
    return {
        "summary": _dict(bindings.get("summary")),
        "source_summary": _dict(bindings.get("source_summary")),
        "items": [
            {
                "name": str(item.get("name") or ""),
                "instantiated_templates": [
                    {
                        "tactic": str(template.get("tactic") or ""),
                        "confidence": str(template.get("confidence") or ""),
                    }
                    for template in (item.get("instantiated_templates") or [])[:2]
                    if isinstance(template, dict)
                ],
                "slots": [
                    {
                        "kind": str(_dict(slot.get("slot")).get("kind") or ""),
                        "name": str(_dict(slot.get("slot")).get("name") or ""),
                        "candidates": [
                            {
                                "value": str(candidate.get("value") or ""),
                                "confidence": str(candidate.get("confidence") or ""),
                                "source": str(candidate.get("source") or ""),
                            }
                            for candidate in (slot.get("candidates") or [])[:3]
                            if isinstance(candidate, dict)
                        ],
                    }
                    for slot in (item.get("slots") or [])[:4]
                    if isinstance(slot, dict)
                ],
            }
            for item in (bindings.get("items") or [])[:4]
            if isinstance(item, dict)
        ],
    }


def _message(item: Any, *, default_code: str) -> dict[str, str]:
    if isinstance(item, dict):
        return {
            "code": str(item.get("code") or default_code),
            "message": str(item.get("message") or item),
            "tactic": str(item.get("failed_tactic") or item.get("tactic") or ""),
        }
    return {"code": default_code, "message": str(item), "tactic": ""}


def _short_preview(text: str, limit: int = 500) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[:limit] + "\n..."


def _load_json_object(path_value: Any) -> dict[str, Any]:
    path = Path(str(path_value or ""))
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}





def _int(value: Any) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _safe_summary_id(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", text).strip("_") or "action"
