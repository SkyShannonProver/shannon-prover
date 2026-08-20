"""Turn composition for the current goal-only L1/compiler-V2 registry."""
from __future__ import annotations

from typing import Any

from core.context_intents import control_menu_intents
from workflow.proof_management.managed_turn_outcome import (
    action_outcome_from_action,
    normalize_proof_state_effect,
    proof_state_changed_for_turn,
    turn_needs_attention,
)
from workflow.proof_management.types import has_agent_observation_kind
from workflow.proof_state_compiler.current_turn_contract import (
    SURFACE_TURN_SCHEMA_VERSION,
    as_dict,
    content_hash,
    current_proof_surface,
    drop_empty,
)
from workflow.proof_state_compiler.surface_profiles import (
    ensure_current_surface_profile,
)


def compose_current_surface_turn(
    current_view: dict[str, Any],
    profile_id: str,
    *,
    base_surface: dict[str, Any] | None = None,
    handled_intent: dict[str, Any] | None = None,
    ok: bool = True,
    repair_prompt: str = "",
    manager_actions: list[dict[str, Any]] | None = None,
    health_event: dict[str, Any] | None = None,
    compiler_markdown: str | None = None,
) -> dict[str, Any]:
    """Compose the complete current turn without historical panel logic."""

    ensure_current_surface_profile(profile_id)
    view = dict(current_view) if isinstance(current_view, dict) else {}
    handled = handled_intent if isinstance(handled_intent, dict) else {}
    actions = list(manager_actions or [])
    intent = _intent_name(handled, view)
    payload = (
        handled.get("payload")
        if isinstance(handled.get("payload"), dict)
        else {}
    )
    current_surface = current_proof_surface(view, profile_id)
    changed = proof_state_changed_for_turn(actions, view)
    control_menu = _control_menu_from_view(view, intent, repair_prompt)
    menu_visible = (
        control_menu is not None
        and not _control_intent_executed(intent, payload, changed, view)
    )
    proof_surface = (
        dict(base_surface)
        if menu_visible
        and isinstance(base_surface, dict)
        and base_surface.get("schema_version")
        else current_surface
    )
    outcome = _turn_outcome(
        view,
        intent=intent,
        payload=payload,
        ok=ok,
        repair_prompt=repair_prompt,
        manager_actions=actions,
        health_event=health_event or {},
        proof_state_changed=changed,
    )
    presentation_kind = (
        "control_menu"
        if menu_visible
        else "bootstrap" if not handled else "proof_state"
    )
    compiler = compiler_markdown if isinstance(compiler_markdown, str) else ""
    data = drop_empty({
        "schema_version": SURFACE_TURN_SCHEMA_VERSION,
        "presentation_kind": presentation_kind,
        "proof_surface": proof_surface,
        "compiler_markdown": compiler,
        "control_menu": control_menu if menu_visible else None,
        "turn_outcome": outcome,
        "base_surface_updates": _base_surface_updates(
            intent,
            payload=payload,
            ok=ok,
            is_control_menu=menu_visible,
            proof_state_changed=changed,
        ),
        "proof_state_changed": changed,
        "metadata": {
            "contract": (
                "CurrentGoalEnvelope -> CurrentSurfaceTurn -> markdown"
            ),
            "current_surface_hash": current_surface.get("surface_model_hash"),
            "proof_surface_hash": proof_surface.get("surface_model_hash"),
        },
    })
    data["surface_turn_hash"] = content_hash(data, "surface_turn_hash")
    return data


def _intent_name(
    handled_intent: dict[str, Any],
    view: dict[str, Any],
) -> str:
    intent = str(handled_intent.get("intent") or "").strip()
    if intent:
        return intent
    return str(as_dict(view.get("last_result")).get("intent") or "").strip()


def _turn_outcome(
    view: dict[str, Any],
    *,
    intent: str,
    payload: dict[str, Any],
    ok: bool,
    repair_prompt: str,
    manager_actions: list[dict[str, Any]],
    health_event: dict[str, Any],
    proof_state_changed: bool,
) -> dict[str, Any]:
    last_result = as_dict(view.get("last_result"))
    tactic = str(
        last_result.get("tactic") or payload.get("tactic") or ""
    ).strip()
    result = str(
        last_result.get("result")
        or last_result.get("message")
        or last_result.get("notice")
        or ""
    ).strip()
    error = str(last_result.get("error_summary") or "").strip()
    action_outcome = next(
        (
            action_outcome_from_action(action)
            for action in manager_actions
            if isinstance(action, dict)
            and action.get("label") != "managed_goal_view"
        ),
        None,
    )
    outcome_kind = str(
        last_result.get("outcome_kind")
        or (action_outcome.outcome_kind if action_outcome else "unknown")
    )
    if outcome_kind == "no_progress":
        result = (
            "EasyCrypt accepted the tactic, but it did not change the goal. "
            "The manager reverted the no-op commit."
        )
    if not ok and repair_prompt:
        result = repair_prompt
    elif tactic:
        result = (
            f"Last action: `{_short(tactic, 80)}` -- "
            f"{result or '(no result reported)'}"
        )
    if error and outcome_kind != "no_progress" and "EasyCrypt error:" not in result:
        result += ("\n" if result else "") + f"EasyCrypt error: {error}"
    if repair_prompt and not result:
        result = repair_prompt
    extras: list[str] = []
    if health_event.get("status"):
        extras.append(f"health: `{health_event['status']}`")
    if any(
        isinstance(action, dict) and action.get("timed_out")
        for action in manager_actions
    ):
        extras.append("manager backend action TIMED OUT")
    if extras:
        result = (result + "\n" if result else "") + "\n".join(extras)
    finish_accepted = has_agent_observation_kind(
        manager_actions,
        "finish_accepted",
    )
    proof_state_effect = normalize_proof_state_effect(
        last_result.get("proof_state_effect")
        or (
            action_outcome.proof_state_effect
            if action_outcome
            else "unknown"
        )
    )
    return drop_empty({
        "intent": intent,
        "payload": dict(payload),
        "ok": ok,
        "result_line": result,
        "error_summary": error,
        "lead_before_goal": bool(result or error),
        "needs_attention": turn_needs_attention(manager_actions, view),
        "finish_accepted": finish_accepted,
        "proof_state_changed": proof_state_changed,
        "outcome_kind": outcome_kind,
        "proof_state_effect": proof_state_effect,
        "source_refs": [
            "last_result",
            *(
                ["manager_actions.agent_observation"]
                if finish_accepted else []
            ),
        ],
    })


def _control_menu_from_view(
    view: dict[str, Any],
    intent: str,
    repair_prompt: str,
) -> dict[str, Any] | None:
    if intent not in control_menu_intents():
        return None
    raw_menu = as_dict(as_dict(view.get("last_result")).get("control_menu"))
    if not raw_menu:
        return None
    items: list[dict[str, Any]] = []
    for raw in raw_menu.get("items") or []:
        if not isinstance(raw, dict):
            continue
        submit = raw.get("submit")
        if not isinstance(submit, dict):
            raw_intent = raw.get("intent")
            if raw_intent or isinstance(raw.get("payload"), dict):
                submit = {
                    "intent": raw_intent,
                    "payload": raw.get("payload") or {},
                }
        if not isinstance(submit, dict) or not submit.get("intent"):
            continue
        if intent == "undo_to_checkpoint" and submit.get("intent") != intent:
            continue
        if intent == "amend_and_replay" and submit.get("intent") != intent:
            continue
        items.append(drop_empty({
            "label": str(
                raw.get("label")
                or raw.get("title")
                or raw.get("message")
                or submit.get("intent")
                or ""
            ).strip(),
            "description": str(
                raw.get("effect_if_selected")
                or raw.get("repair_use_when")
                or raw.get("why_checkpoint")
                or raw.get("notice")
                or raw.get("description")
                or ""
            ).strip(),
            "tactic": str(
                raw.get("committed_tactic") or raw.get("tactic") or ""
            ).strip(),
            "requires_input": [
                str(field).strip()
                for field in raw.get("requires_input") or []
                if str(field).strip()
            ],
            "submit": {
                "intent": submit.get("intent"),
                "payload": submit.get("payload") or {},
            },
            "source": "last_result.control_menu.items",
        }))
    notice = str(repair_prompt or raw_menu.get("notice") or "").strip()
    if not items and not notice:
        return None
    return drop_empty({
        "intent": intent,
        "title": str(raw_menu.get("title") or intent).strip(),
        "notice": notice,
        "items": items,
        "source_refs": ["last_result.control_menu"],
    })


def _control_intent_executed(
    intent: str,
    payload: dict[str, Any],
    changed: bool,
    view: dict[str, Any],
) -> bool:
    last_result = as_dict(view.get("last_result"))
    kind = str(last_result.get("kind") or "")
    if intent == "undo_to_checkpoint":
        return changed or kind in {"checkpoint_rewind", "checkpoint_restore"}
    if intent == "fresh_restart":
        return changed or kind == "fresh_restart_confirmed"
    return False


def _base_surface_updates(
    intent: str,
    *,
    payload: dict[str, Any],
    ok: bool,
    is_control_menu: bool,
    proof_state_changed: bool,
) -> bool:
    if not ok and not proof_state_changed:
        return False
    if is_control_menu:
        return False
    if intent == "finish":
        return False
    if intent == "fresh_restart":
        return bool(payload.get("confirm") and proof_state_changed)
    if intent == "undo_to_checkpoint":
        return bool(
            (
                payload.get("checkpoint_id")
                or payload.get("restore_id")
                or payload.get("confirm")
            )
            and proof_state_changed
        )
    return True


def _short(value: str, limit: int) -> str:
    normalized = " ".join(str(value or "").split())
    return (
        normalized
        if len(normalized) <= limit
        else normalized[: limit - 1] + "..."
    )
