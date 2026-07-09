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
    latest_readonly_probe_event: dict[str, Any] | None = None,
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

    if intent.intent == "undo_last_step" and latest_readonly_probe_event:
        return IntentPreflightDecision(
            kind="menu",
            observation=probe_undo_boundary_observation(
                intent=intent,
                latest_probe=latest_readonly_probe_event,
            ),
            label="probe_undo_boundary",
            audit_kind="undo_last_step.probe_boundary_guard",
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


def probe_undo_boundary_observation(
    *,
    intent: AgentIntent,
    latest_probe: dict[str, Any],
) -> dict[str, Any]:
    tactic = str(latest_probe.get("tactic") or "").strip()
    accepted = bool(latest_probe.get("accepted"))
    options: list[dict[str, Any]] = [
        {
            "label": "Show rewind choices",
            "effect_if_selected": (
                "This shows committed tactics you can rewind before; "
                "it does not treat the read-only probe as an undo target."
            ),
            "submit": {"intent": "undo_to_checkpoint", "payload": {}},
        },
    ]
    if accepted and tactic:
        options.insert(0, {
            "label": "Commit accepted probe",
            "effect_if_selected": (
                "This commits the exact tactic that was accepted by the "
                "read-only probe and then returns the real post-commit view."
            ),
            "submit": {
                "intent": "commit_tactic",
                "payload": {"tactic": tactic},
            },
        })
    return _drop_empty({
        "intent": intent.intent,
        "kind": "probe_undo_boundary",
        "message": (
            "The previous action was a read-only probe, so there is no "
            "probe step to undo. `undo_last_step` would undo the most "
            "recent committed tactic, not that probe."
        ),
        "last_probe": _drop_empty({
            "tactic": tactic,
            "accepted": accepted,
            "status": latest_probe.get("status"),
            "turn_index": latest_probe.get("turn_index"),
        }),
        "options": options,
    })




