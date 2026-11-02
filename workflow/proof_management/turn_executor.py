"""Managed proof-turn execution.

``ProofNodeManager`` decides which service should handle an agent intent.  This
executor owns the common turn mechanics: render observations, record accepted
route events, surface backend failures, and shape the final ``ManagedTurn``.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from .health import backend_failure_health_event, timeout_health_event
from workflow.proof_management.managed_turn_outcome import (
    classify_manager_action_outcome,
    observation_with_action_outcome,
    observation_with_recovery_outcome,
)
from .intent_admission import IntentPreflightDecision
from .lineage import LemmaLineageStore
from .node_state import NodeTurnState
from .protocol_repair import (
    AgentIntent,
    backend_failure_repair_prompt,
)
from .recovery_handlers import RecoveryTurnPlan
from .repl_session import ReplBackendError, ReplBackendTimeout
from .turn_view import (
    latest_observation_for_view,
    render_observation_view,
    selection_menu_action,
    snapshot_surface,
    view_with_latest_observation,
)
from .types import ManagedTurn, ProofStateSnapshot, TurnDirective

if TYPE_CHECKING:
    from .event_store import ProofEventManager
    from .repl_session import ReplSessionManager


class ProofTurnExecutor:
    """Executes manager-owned turns after intent routing has chosen a plan."""

    def __init__(
        self,
        *,
        node_id: str,
        state: NodeTurnState,
        repl: "ReplSessionManager",
        events: "ProofEventManager",
        lineage: LemmaLineageStore,
        project: Callable[[ProofStateSnapshot, dict[str, Any] | None], dict[str, Any]],
        audit: Callable[[dict[str, Any]], None],
        surface_profile: str | None = None,
    ) -> None:
        self.node_id = node_id
        self.state = state
        self.repl = repl
        self.events = events
        self.lineage = lineage
        # Projection is the manager's (admission bookkeeping + lifecycle
        # projection); it writes ``state``.
        self._project = project
        self._audit = audit
        self.surface_profile = surface_profile

    def handle_preflight_decision(
        self,
        intent: AgentIntent,
        decision: IntentPreflightDecision,
    ) -> ManagedTurn:
        if decision.kind == "menu":
            return self.menu_turn(
                intent,
                decision.observation,
                label=decision.label,
                audit_kind=decision.audit_kind,
                ok=decision.ok,
            )
        return self.action_repair_turn(intent, decision)

    def action_repair_turn(
        self,
        intent: AgentIntent,
        decision: IntentPreflightDecision,
    ) -> ManagedTurn:
        actions = list(decision.actions)
        observation = dict(decision.observation)
        view = self.view_for_observation(observation)
        self._audit({
            "kind": decision.audit_kind,
            "node": self.node_id,
            "surface_profile": self.surface_profile,
            "intent": intent.to_dict(),
            "manager_actions": actions,
            "snapshot": snapshot_surface(self.state.latest_snapshot),
            **decision.audit_extra,
        })
        return ManagedTurn(
            ok=decision.ok,
            workspace_view=view,
            snapshot=self.state.latest_snapshot,
            repair_prompt=decision.repair_prompt,
            intent=intent,
            manager_actions=actions,
        )

    def execute_recovery_plan(
        self,
        intent: AgentIntent,
        plan: RecoveryTurnPlan,
    ) -> ManagedTurn:
        if plan.kind == "menu":
            return self.menu_turn(
                intent,
                plan.observation,
                label=plan.label,
                audit_kind=plan.audit_kind,
            )
        if plan.kind != "repl_call":
            raise RuntimeError(f"unknown recovery plan kind: {plan.kind}")
        if plan.call is None:
            raise RuntimeError("recovery repl_call plan missing call")
        return self.repl_call(
            intent,
            plan.call,
            latest_observation=plan.observation,
            audit_extra=plan.audit_extra,
        )

    def repl_call(
        self,
        intent: AgentIntent,
        call: Callable[[], tuple[ProofStateSnapshot, list[dict[str, Any]]]],
        *,
        latest_observation: dict[str, Any] | None = None,
        audit_extra: dict[str, Any] | None = None,
    ) -> ManagedTurn:
        try:
            snapshot, actions = call()
        except ReplBackendTimeout as exc:
            health = timeout_health_event(
                node_id=self.node_id,
                intent=intent,
                action=exc.action,
                state_version=self.repl.state_version,
            )
            self._audit({
                "kind": "manager_action.timeout",
                "node": self.node_id,
                "intent": intent.to_dict(),
                "manager_actions": [exc.action],
                "health": health.to_dict(),
                "snapshot": snapshot_surface(self.state.latest_snapshot),
                **(audit_extra or {}),
            })
            return ManagedTurn(
                ok=False,
                workspace_view=dict(self.state.latest_view),
                snapshot=self.state.latest_snapshot,
                health_event=health,
                intent=intent,
                manager_actions=[exc.action],
                directive=TurnDirective.NODE_UNHEALTHY,
            )
        except ReplBackendError as exc:
            health = backend_failure_health_event(
                node_id=self.node_id,
                intent=intent,
                action=exc.action,
                state_version=self.repl.state_version,
            )
            observation = latest_observation_for_view(intent, [exc.action])
            view = view_with_latest_observation(self.state.latest_view, observation)
            self.state.latest_view = dict(view)
            self._audit({
                "kind": "manager_action.backend_failure",
                "node": self.node_id,
                "intent": intent.to_dict(),
                "manager_actions": [exc.action],
                "health": health.to_dict() if health else {},
                "snapshot": snapshot_surface(self.state.latest_snapshot),
                **(audit_extra or {}),
            })
            return ManagedTurn(
                ok=False,
                workspace_view=view,
                snapshot=self.state.latest_snapshot,
                repair_prompt=backend_failure_repair_prompt(exc.action),
                health_event=health,
                intent=intent,
                manager_actions=[exc.action],
                directive=(
                    TurnDirective.NODE_UNHEALTHY
                    if health is not None
                    else TurnDirective.CONTINUE
                ),
            )
        if latest_observation is not None:
            # Only restart-and-replay recovery plans supply an observation.
            observation = observation_with_recovery_outcome(
                latest_observation, actions
            )
        else:
            observation = observation_with_action_outcome(
                latest_observation_for_view(intent, actions), actions
            )
        self._record_route_event(intent, actions, observation)
        view = self._project(snapshot, observation)
        self._audit({
            "kind": "agent_intent.handled",
            "node": self.node_id,
            "intent": intent.to_dict(),
            "manager_actions": actions,
            "snapshot": snapshot.to_dict(),
            **(audit_extra or {}),
        })
        return ManagedTurn(
            ok=True,
            workspace_view=view,
            snapshot=snapshot,
            intent=intent,
            manager_actions=actions,
        )

    def finish_turn(self, intent: AgentIntent) -> ManagedTurn:
        """Accept a worker stop request without routing it through the REPL.

        ``finish`` controls serving only.  It does not mutate EasyCrypt and its
        directive must never be interpreted as proof closedness or success.
        """

        outcome = classify_manager_action_outcome(
            status="ok",
            ok=True,
            read_only=False,
            mutates_proof_state=False,
            state_changed=False,
        ).to_dict()
        action = {
            "label": "finish",
            "exit_code": 0,
            "duration_ms": 0,
            "mutates_proof_state": False,
            **outcome,
            "agent_observation": {
                "kind": "finish_accepted",
                "result": (
                    "Finish accepted; this proof node will stop after this "
                    "response."
                ),
                "effect": "The EasyCrypt proof state did not change.",
            },
        }
        observation = latest_observation_for_view(intent, [action])
        view = self.view_for_observation(
            observation,
            overlay_after_project=True,
        )
        self._audit({
            "kind": "agent_intent.finish_accepted",
            "node": self.node_id,
            "intent": intent.to_dict(),
            "manager_actions": [action],
            "proof_state_effect": "unchanged",
            "snapshot": snapshot_surface(self.state.latest_snapshot),
        })
        return ManagedTurn(
            ok=True,
            workspace_view=view,
            snapshot=self.state.latest_snapshot,
            intent=intent,
            manager_actions=[action],
            directive=TurnDirective.STOP_REQUESTED,
        )

    def menu_turn(
        self,
        intent: AgentIntent,
        observation: dict[str, Any],
        *,
        label: str,
        audit_kind: str,
        ok: bool = True,
        audit_extra: dict[str, Any] | None = None,
    ) -> ManagedTurn:
        action = selection_menu_action(label, observation, ok=ok)
        observation = observation_with_action_outcome(observation, [action])
        view = self.view_for_observation(
            observation,
            overlay_after_project=True,
        )
        self._audit({
            "kind": audit_kind,
            "node": self.node_id,
            "intent": intent.to_dict(),
            "manager_actions": [action],
            "proof_state_effect": action["proof_state_effect"],
            "snapshot": snapshot_surface(self.state.latest_snapshot),
            **(audit_extra or {}),
        })
        return ManagedTurn(
            ok=ok,
            workspace_view=view,
            snapshot=self.state.latest_snapshot,
            intent=intent,
            manager_actions=[action],
        )

    def view_for_observation(
        self,
        observation: dict[str, Any],
        *,
        overlay_after_project: bool = False,
    ) -> dict[str, Any]:
        view = render_observation_view(
            latest_view=self.state.latest_view,
            latest_snapshot=self.state.latest_snapshot,
            observation=observation,
            project=self._project,
            overlay_after_project=overlay_after_project,
        )
        self.state.latest_view = dict(view)
        return view

    def _record_route_event(
        self,
        intent: AgentIntent,
        actions: list[dict[str, Any]],
        observation: dict[str, Any],
    ) -> None:
        recorded = self.events.record_route_turn(
            intent=intent.intent,
            payload=intent.payload,
            actions=actions,
            observation=observation,
        )
        if not recorded:
            return
        self.lineage.record_proof_turn(
            node_id=self.node_id,
            route_event=recorded,
        )
