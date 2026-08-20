"""Turn-level agent observation rendering helpers."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from core.context_intents import (
    intent_is_read_only,
    intent_may_mutate_proof_state,
)
from workflow.proof_management.managed_turn_outcome import (
    classify_manager_action_outcome,
    observation_with_action_outcome,
)

from .protocol_repair import AgentIntent
from core.easycrypt.value_shapes import drop_empty as _drop_empty


def selection_menu_action(
    label: str,
    observation: dict[str, Any],
    *,
    ok: bool = True,
) -> dict[str, Any]:
    outcome = classify_manager_action_outcome(
        status="control_menu",
        ok=ok,
        read_only=False,
        mutates_proof_state=False,
        state_changed=False,
        control_menu=True,
    ).to_dict()
    return {
        "label": label,
        "exit_code": 0,
        "duration_ms": 0,
        "mutates_proof_state": False,
        **outcome,
        "agent_observation": observation,
        "stdout_has_workspace_view": False,
    }


def latest_observation_for_view(
    intent: AgentIntent,
    actions: list[dict[str, Any]],
) -> dict[str, Any]:
    for action in actions:
        if not isinstance(action, dict):
            continue
        observation = action.get("agent_observation")
        if isinstance(observation, dict) and observation:
            surfaced = dict(observation)
            surfaced = observation_with_action_outcome(surfaced, [action])
            result = _drop_empty({
                "intent": intent.intent,
                "payload": intent_payload_surface(intent),
                **surfaced,
            })
            return result
    result = _drop_empty({
        "intent": intent.intent,
        "payload": intent_payload_surface(intent),
        "result": (
            "The manager recorded the intent and returned the latest completed "
            "workspace view."
        ),
        "effect": intent_effect(intent.intent),
    })
    return result


def view_with_latest_observation(
    view: dict[str, Any],
    observation: dict[str, Any],
) -> dict[str, Any]:
    clean = dict(view) if isinstance(view, dict) else {}
    clean.pop("last_result", None)
    return {"last_result": observation, **clean} if clean else {"last_result": observation}


def render_observation_view(
    *,
    latest_view: dict[str, Any],
    latest_snapshot: Any,
    observation: dict[str, Any],
    project: Callable[[Any, dict[str, Any]], dict[str, Any]],
    overlay_after_project: bool = False,
) -> dict[str, Any]:
    if latest_snapshot is not None:
        view = project(latest_snapshot, observation)
        if overlay_after_project:
            view = view_with_latest_observation(view, observation)
        return view
    return view_with_latest_observation(latest_view, observation)


def snapshot_surface(snapshot: Any) -> dict[str, Any]:
    if snapshot is None:
        return {}
    to_dict = getattr(snapshot, "to_dict", None)
    if callable(to_dict):
        payload = to_dict()
        return dict(payload) if isinstance(payload, dict) else {}
    return {}


def clean_manager_actions(actions: list[Any]) -> list[dict[str, Any]]:
    return [action for action in actions if isinstance(action, dict)]


def intent_payload_surface(intent: AgentIntent) -> dict[str, Any]:
    payload = dict(intent.payload)
    allowed = {
        "tactic",
        "checkpoint_id",
        "restore_id",
        "confirm",
        "confirmation_id",
        "index",
    }
    return {
        key: value
        for key, value in payload.items()
        if key in allowed and value not in (None, "", [], {})
    }


def intent_effect(intent_name: str) -> str:
    if intent_is_read_only(intent_name):
        return (
            "This manager intent is read-only; it does not change the "
            "EasyCrypt proof state."
        )
    if intent_may_mutate_proof_state(intent_name):
        return (
            "This manager intent may change the EasyCrypt proof state, and "
            "the manager will return a refreshed workspace view afterward."
        )
    return "This manager intent does not change the EasyCrypt proof state."
