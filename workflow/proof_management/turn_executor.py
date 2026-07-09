"""Managed proof-turn execution.

``ProofNodeManager`` decides which service should handle an agent intent.  This
executor owns the common turn mechanics: render observations, record accepted
route events, surface backend failures, and shape the final ``ManagedTurn``.
"""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from .health import backend_failure_health_event, timeout_health_event
from .intent_preflight import IntentPreflightDecision
from .lineage import LemmaLineageStore
from .probe_alternatives import ProofProbeAlternativeManager
from .protocol_repair import (
    AgentIntent,
    backend_failure_repair_prompt,
)
from .recovery_handlers import RecoveryTurnPlan
from .repl_session import ReplBackendError, ReplBackendTimeout
from .turn_view import (
    clean_manager_actions,
    latest_observation_for_view,
    render_observation_view,
    selection_menu_action,
    snapshot_surface,
    view_with_latest_observation,
)
from .types import ManagedTurn, ProofStateSnapshot


class ProofTurnExecutor:
    """Executes manager-owned turns after intent routing has chosen a plan."""

    def __init__(
        self,
        *,
        node_id: str,
        repl: Any,
        events: Any,
        lineage: LemmaLineageStore,
        probe_alternatives: ProofProbeAlternativeManager,
        latest_snapshot: Callable[[], ProofStateSnapshot | None],
        latest_view: Callable[[], dict[str, Any]],
        set_latest_view: Callable[[dict[str, Any]], None],
        project: Callable[[ProofStateSnapshot, dict[str, Any] | None], dict[str, Any]],
        audit: Callable[[dict[str, Any]], None],
        run_dir: Callable[[], Path | None],
        surface_profile: str | None = None,
    ) -> None:
        self.node_id = node_id
        self.repl = repl
        self.events = events
        self.lineage = lineage
        self.probe_alternatives = probe_alternatives
        self._latest_snapshot = latest_snapshot
        self._latest_view = latest_view
        self._set_latest_view = set_latest_view
        self._project = project
        self._audit = audit
        self._run_dir = run_dir
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
            "snapshot": snapshot_surface(self._latest_snapshot()),
            **decision.audit_extra,
        })
        return ManagedTurn(
            ok=decision.ok,
            workspace_view=view,
            snapshot=self._latest_snapshot(),
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
        if plan.kind == "nonmutating":
            return self.nonmutating_backend_turn(
                intent,
                plan.observation,
                actions=plan.actions,
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

    def nonmutating_backend_turn(
        self,
        intent: AgentIntent,
        observation: dict[str, Any],
        *,
        actions: list[Any],
        audit_kind: str,
    ) -> ManagedTurn:
        clean_actions = clean_manager_actions(actions)
        view = self.view_for_observation(
            observation,
            overlay_after_project=True,
        )
        self._audit({
            "kind": audit_kind,
            "node": self.node_id,
            "intent": intent.to_dict(),
            "manager_actions": clean_actions,
            "proof_state_effect": "scratch_replay_only",
            "snapshot": snapshot_surface(self._latest_snapshot()),
        })
        return ManagedTurn(
            ok=True,
            workspace_view=view,
            snapshot=self._latest_snapshot(),
            intent=intent,
            manager_actions=clean_actions,
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
                "snapshot": snapshot_surface(self._latest_snapshot()),
                **(audit_extra or {}),
            })
            return ManagedTurn(
                ok=False,
                workspace_view=dict(self._latest_view()),
                snapshot=self._latest_snapshot(),
                health_event=health,
                intent=intent,
                manager_actions=[exc.action],
            )
        except ReplBackendError as exc:
            health = backend_failure_health_event(
                node_id=self.node_id,
                intent=intent,
                action=exc.action,
                state_version=self.repl.state_version,
            )
            observation = latest_observation_for_view(intent, [exc.action])
            view = view_with_latest_observation(self._latest_view(), observation)
            self._set_latest_view(view)
            self._audit({
                "kind": "manager_action.backend_failure",
                "node": self.node_id,
                "intent": intent.to_dict(),
                "manager_actions": [exc.action],
                "health": health.to_dict() if health else {},
                "snapshot": snapshot_surface(self._latest_snapshot()),
                **(audit_extra or {}),
            })
            return ManagedTurn(
                ok=False,
                workspace_view=view,
                snapshot=self._latest_snapshot(),
                repair_prompt=backend_failure_repair_prompt(exc.action),
                health_event=health,
                intent=intent,
                manager_actions=[exc.action],
            )
        observation = (
            latest_observation
            if latest_observation is not None
            else latest_observation_for_view(intent, actions)
        )
        self._record_route_event(intent, actions, observation)
        self.probe_alternatives.record(intent, snapshot, observation)
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

    def menu_turn(
        self,
        intent: AgentIntent,
        observation: dict[str, Any],
        *,
        label: str,
        audit_kind: str,
    ) -> ManagedTurn:
        action = selection_menu_action(label, observation)
        view = self.view_for_observation(
            observation,
            overlay_after_project=True,
        )
        self._audit({
            "kind": audit_kind,
            "node": self.node_id,
            "intent": intent.to_dict(),
            "manager_actions": [action],
            "proof_state_effect": "selection_menu_only",
            "snapshot": snapshot_surface(self._latest_snapshot()),
        })
        return ManagedTurn(
            ok=True,
            workspace_view=view,
            snapshot=self._latest_snapshot(),
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
            latest_view=self._latest_view(),
            latest_snapshot=self._latest_snapshot(),
            observation=observation,
            project=self._project,
            overlay_after_project=overlay_after_project,
        )
        self._set_latest_view(view)
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
        self.lineage.run_dir = self._run_dir()
        self.lineage.record_proof_turn(
            node_id=self.node_id,
            route_event=recorded,
        )
