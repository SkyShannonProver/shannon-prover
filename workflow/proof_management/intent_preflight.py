"""Agent-intent preflight guards.

This module owns protocol-level checks that should happen before an intent is
sent to the EasyCrypt backend.  It returns a small decision object; the facade
still owns turn rendering, audit, and any state-changing execution.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from workflow.surface_profiles import surface_profile_allows_intent

from .protocol_repair import (
    FINISH_REQUIRES_QED_PROMPT,
    QED_CLARIFICATION_PROMPT,
    AgentIntent,
    finish_requires_qed_action,
    intent_is_standalone_qed,
    qed_clarification_action,
    view_allows_qed,
    view_requires_qed_before_finish,
)
from .turn_view import (
    intent_payload_surface,
    latest_observation_for_view,
    selection_menu_action,
)
from core.easycrypt.value_shapes import drop_empty as _drop_empty


PreflightKind = Literal["none", "action_repair", "menu"]


@dataclass(frozen=True)
class IntentPreflightDecision:
    kind: PreflightKind = "none"
    ok: bool = True
    actions: list[dict[str, Any]] = field(default_factory=list)
    observation: dict[str, Any] = field(default_factory=dict)
    repair_prompt: str = ""
    label: str = ""
    audit_kind: str = ""
    audit_extra: dict[str, Any] = field(default_factory=dict)

    @property
    def should_handle(self) -> bool:
        return self.kind != "none"


def preflight_intent(
    *,
    intent: AgentIntent,
    latest_view: dict[str, Any],
    surface_profile: str | None,
) -> IntentPreflightDecision:
    # NOTE: `admit` is intentionally NOT blocked here. The manager gates
    # `qed`/`finish` while committed admits remain, and the orchestrator rejects
    # any final proof that still contains admit.

    if intent_is_standalone_qed(intent.intent, intent.payload) and not view_allows_qed(
        latest_view,
    ):
        actions = [qed_clarification_action(intent.payload)]
        return IntentPreflightDecision(
            kind="action_repair",
            ok=False,
            actions=actions,
            observation=latest_observation_for_view(intent, actions),
            repair_prompt=QED_CLARIFICATION_PROMPT,
            audit_kind="agent_intent.qed_clarification",
        )

    allowed, reason = surface_profile_allows_intent(
        surface_profile,
        intent.intent,
        intent.payload,
    )
    if not allowed:
        actions = [
            selection_menu_action(
                "surface_profile_hidden_intent",
                {
                    "intent": intent.intent,
                    "payload": intent_payload_surface(intent),
                    "message": reason,
                },
            )
        ]
        return IntentPreflightDecision(
            kind="action_repair",
            ok=False,
            actions=actions,
            observation=latest_observation_for_view(intent, actions),
            repair_prompt=reason,
            audit_kind="agent_intent.blocked_by_surface_profile",
            audit_extra={"reason": reason},
        )

    if intent.intent == "finish" and view_requires_qed_before_finish(latest_view):
        actions = [finish_requires_qed_action()]
        return IntentPreflightDecision(
            kind="action_repair",
            ok=False,
            actions=actions,
            observation=latest_observation_for_view(intent, actions),
            repair_prompt=FINISH_REQUIRES_QED_PROMPT,
            audit_kind="agent_intent.finish_requires_qed",
        )

    return IntentPreflightDecision()
