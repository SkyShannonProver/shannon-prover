"""Managed prover node facade.

This module implements the internal split behind the single manager the prover
agent sees:

* ``ProofNodeManager`` is the node-level facade.
* ``ReplSessionManager`` owns EasyCrypt/session lifecycle and backend calls.
* every run uses ``ManagedGoalViewManager`` for the neutral goal envelope;
* the compiler contributes one already-admitted Markdown block.

The low-level session CLI remains a backend implementation detail here; it is
not part of the agent-facing protocol.  Importing and constructing a current
manager must not load the historical compiler/view modules.
"""
from __future__ import annotations

import hashlib
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

from workflow.proof_management import (
    CommittedTurnSpine,
    IntentAdmission,
    IntentAdmissionController,
    LemmaLineageStore,
    ManagedTurn,
    NodeHealthEvent,
    ProofCheckpointManager,
    ProofEventManager,
    ProofNodeLifecycleManager,
    ProofStateSnapshot,
    ProofProjectionPipeline,
    ProofRecoveryIntentHandler,
    ProofTurnExecutor,
    ReplSessionManager,
    TurnDirective,
)
from workflow.proof_management.compiler_turn_adapter import (
    CompilerTurnAdapter,
    CompilerTurnDeadlineExceeded,
)
from workflow.proof_management.checkpoint_surface import (
    history_hash as _history_hash,
)
from workflow.proof_management.repl_session import (
    session_dir_path as _session_dir_path,
)
from workflow.proof_tool.proof_tool_contract import (
    ProofToolContractManifest,
    resolve_proof_tool_contract,
    validate_proof_tool_contract,
)
from workflow.proof_state_compiler.configuration import (
    compiler_service_for_profile,
)
from workflow.proof_state_compiler.profile_registry import (
    normalize_runtime_surface_profile_id,
)
from workflow.proof_state_compiler.managed_goal_view_manager import (
    ManagedGoalViewManager,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class ProofNodeManager:
    """Single node manager facade visible to orchestration and the agent."""

    def __init__(
        self,
        *,
        file_path: str,
        lemma_name: str,
        include_dir: str,
        session_tag: str,
        node_id: str = "",
        run_dir: Path | None = None,
        project_root: Path = PROJECT_ROOT,
        surface_profile: str | None = None,
        proof_tool_manifest: ProofToolContractManifest | None = None,
    ) -> None:
        self.node_id = node_id or session_tag
        self.session_tag = session_tag
        self.run_dir = Path(run_dir) if run_dir is not None else None
        self.surface_profile = normalize_runtime_surface_profile_id(
            surface_profile
        )
        self.proof_tool_manifest = validate_proof_tool_contract(
            proof_tool_manifest
            if proof_tool_manifest is not None
            else resolve_proof_tool_contract(self.surface_profile)
        )
        self.repl = ReplSessionManager(
            file_path=file_path,
            lemma_name=lemma_name,
            include_dir=include_dir,
            session_tag=session_tag,
            node_id=self.node_id,
            project_root=project_root,
        )
        self.compiler_service = compiler_service_for_profile(
            self.surface_profile,
            self.repl,
        )
        self.workspace = ManagedGoalViewManager()
        self.lineage = LemmaLineageStore(run_dir=self.run_dir)
        self.events = ProofEventManager(
            node_id=self.node_id,
            run_dir=self.run_dir,
        )
        self.checkpoints = ProofCheckpointManager(
            node_id=self.node_id,
            run_dir=self.run_dir,
            history_hash=_history_hash,
            confirmation_id=_confirmation_id,
        )
        self.admission = IntentAdmissionController(
            node_id=self.node_id,
            surface_profile=self.surface_profile,
            effective_profile_intents=(
                self.proof_tool_manifest.effective_profile_intents
            ),
            events=self.events,
            state_version=lambda: self.repl.state_version,
            committed_history=lambda: self.repl.committed_history(),
            audit=self._audit,
        )
        self.compiler = CompilerTurnAdapter(
            node_id=self.node_id,
            service=self.compiler_service,
            session_id=lambda: str(self.session_path),
            audit=self._audit,
        )
        self.projection = ProofProjectionPipeline(
            workspace=self.workspace,
            surface_profile=self.surface_profile,
        )
        self.lifecycle = ProofNodeLifecycleManager(
            node_id=self.node_id,
            session_tag=self.session_tag,
            repl=self.repl,
            projection=self.projection,
            lineage=self.lineage,
            workspace=self.workspace,
            run_dir=lambda: self.run_dir,
            audit=self._audit,
            surface_profile=self.surface_profile,
        )
        self.recovery = ProofRecoveryIntentHandler(
            node_id=self.node_id,
            checkpoints=self.checkpoints,
            repl=self.repl,
            committed_tactics=lambda: self.repl.committed_history(),
            replay_prefix_count=lambda: self._replay_prefix_count,
            resumed_lineage=lambda: self._resumed_from_prefix,
            clear_replay_prefix=self._clear_replay_prefix,
        )
        self.turns = ProofTurnExecutor(
            node_id=self.node_id,
            repl=self.repl,
            events=self.events,
            lineage=self.lineage,
            latest_snapshot=lambda: self.latest_snapshot,
            latest_view=lambda: self.latest_view,
            set_latest_view=self._set_latest_view,
            project=lambda snapshot, latest: self._project(
                snapshot,
                latest_observation=latest,
            ),
            audit=self._audit,
            run_dir=lambda: self.run_dir,
            surface_profile=self.surface_profile,
        )

    @property
    def latest_snapshot(self) -> ProofStateSnapshot | None:
        return self.lifecycle.latest_snapshot

    @latest_snapshot.setter
    def latest_snapshot(self, value: ProofStateSnapshot | None) -> None:
        self.lifecycle.latest_snapshot = value

    @property
    def latest_view(self) -> dict[str, Any]:
        return self.lifecycle.latest_view

    @latest_view.setter
    def latest_view(self, value: dict[str, Any]) -> None:
        self.lifecycle.latest_view = dict(value) if isinstance(value, dict) else {}

    @property
    def latest_full_view(self) -> dict[str, Any]:
        """The complete unprofiled view, or empty until one was projected here."""

        return self.lifecycle.latest_full_view

    @property
    def state_version(self) -> int:
        """The committed EC state version. A manager-facade accessor so callers
        don't reach through to ``manager.repl`` (the one prior facade bypass)."""
        return self.repl.state_version

    @property
    def session_path(self) -> Path:
        """Resolved backend session identity exposed without leaking REPL access."""

        return _session_dir_path(
            self.repl.session_dir,
            self.repl.project_root,
        ).resolve()

    def close_session(self) -> bool:
        """Close this manager's backend session through the public lifecycle facade."""

        return self.repl.close()

    @property
    def malformed_count(self) -> int:
        """Current recoverable protocol-error streak, owned by admission."""

        return self.admission.malformed_count

    @property
    def _resumed_from_prefix(self) -> bool:
        """Durable resumed-lineage marker (survives a rewind-below-floor clear)."""
        return bool(getattr(self.lifecycle, "resumed_from_prefix", False))

    @property
    def _replay_prefix_count(self) -> int:
        return self.lifecycle.replay_prefix_count

    @_replay_prefix_count.setter
    def _replay_prefix_count(self, value: int) -> None:
        try:
            count = int(value or 0)
        except (TypeError, ValueError):
            count = 0
        self.lifecycle.replay_prefix_count = max(0, count)

    def adopt_bootstrap(self, bootstrap: dict[str, Any]) -> None:
        """Adopt a session that was already bootstrapped by this manager layer.

        Tree workers run as their own process after the orchestrator prepares
        the node session.  They need to continue the same manager-owned
        session without restarting EasyCrypt.  The donor's serialized
        preflight results are not live authority for this new manager
        incarnation, so adoption clears the private cache and re-runs the
        current-state preflight before the first worker handoff.
        """
        self.admission.clear_goal_rejections()
        self.lifecycle.adopt_bootstrap(bootstrap)
        bootstrap["compiler_markdown"] = self._compile_bootstrap_markdown()

    def bootstrap(
        self,
        replay_prefix: list[str] | None = None,
        *,
        resume_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.admission.clear_goal_rejections()
        record = self.lifecycle.bootstrap(
            replay_prefix=replay_prefix,
            resume_context=resume_context,
        )
        record["compiler_markdown"] = self._compile_bootstrap_markdown()
        return record

    def handle_tool_arguments(
        self,
        raw_arguments: Any,
        *,
        deadline: float | None = None,
    ) -> ManagedTurn:
        """Handle one raw MCP arguments value through canonical admission.

        The MCP transport deliberately performs no proof-intent validation.
        This entry point therefore preserves malformed requests for manager-owned
        repair instead of creating a second transport parser.
        """

        with self.repl.turn_deadline(deadline):
            admission = self.admission.admit_tool_arguments(
                raw_arguments,
                latest_view=self.latest_view,
                latest_snapshot=self.latest_snapshot,
                deadline=deadline,
            )
            return self._handle_admission(admission, deadline=deadline)

    def handle_agent_message(
        self,
        text: str,
        *,
        deadline: float | None = None,
    ) -> ManagedTurn:
        """Handle one JSON-text intent through the same admission controller."""

        with self.repl.turn_deadline(deadline):
            admission = self.admission.admit_text(
                text,
                latest_view=self.latest_view,
                latest_snapshot=self.latest_snapshot,
                deadline=deadline,
            )
            return self._handle_admission(admission, deadline=deadline)

    def _handle_admission(
        self,
        admission: IntentAdmission,
        *,
        deadline: float | None,
    ) -> ManagedTurn:
        if admission.turn is not None:
            turn = admission.turn
        else:
            intent = admission.intent
            if intent is None:
                raise RuntimeError("intent admission returned no decision")
            if admission.preflight.should_handle:
                turn = self.turns.handle_preflight_decision(
                    intent,
                    admission.preflight,
                )
            elif intent.intent == "fresh_restart":
                turn = self.turns.execute_recovery_plan(
                    intent,
                    self.recovery.handle_fresh_restart(intent),
                )
            elif intent.intent == "amend_and_replay":
                turn = self.turns.execute_recovery_plan(
                    intent,
                    self.recovery.handle_amend_and_replay(intent),
                )
            elif intent.intent == "undo_to_checkpoint":
                turn = self.turns.execute_recovery_plan(
                    intent,
                    self.recovery.handle_undo_to_checkpoint(intent),
                )
            elif intent.intent == "finish":
                turn = self.turns.finish_turn(intent)
            else:
                turn = self.turns.repl_call(
                    intent,
                    lambda: self.repl.handle_intent(intent),
                )
        return self._finalize_turn(turn, deadline=deadline)

    def _finalize_turn(
        self,
        turn: ManagedTurn,
        *,
        deadline: float | None,
    ) -> ManagedTurn:
        if turn.directive is TurnDirective.NODE_UNHEALTHY:
            return turn
        if self.admission.deadline_expired(deadline):
            return self._deadline_failure(turn)
        snapshot = turn.snapshot or self.latest_snapshot
        if snapshot is None:
            # Pre-bootstrap protocol repair has no exact post-state to bind.
            return turn
        try:
            spine = CommittedTurnSpine.capture(self.repl, snapshot)
        except Exception as exc:
            return self._spine_failure(turn, exc)
        if self.admission.deadline_expired(deadline):
            return self._deadline_failure(
                replace(turn, committed_tactics=spine.tactics)
            )
        try:
            return self.compiler.enrich(
                turn,
                spine,
                deadline=deadline,
            )
        except CompilerTurnDeadlineExceeded:
            return self._deadline_failure(
                replace(turn, committed_tactics=spine.tactics)
            )

    def _compile_bootstrap_markdown(self) -> str:
        snapshot = self.latest_snapshot
        if snapshot is None:
            return ""
        spine = CommittedTurnSpine.capture(self.repl, snapshot)
        return self.compiler.compile_current(spine=spine)

    def _deadline_failure(self, completed: ManagedTurn) -> ManagedTurn:
        failed = self.admission.deadline_exceeded_turn(
            latest_view=completed.workspace_view,
            latest_snapshot=completed.snapshot or self.latest_snapshot,
        )
        return replace(
            failed,
            intent=completed.intent,
            manager_actions=list(completed.manager_actions),
            manager_observations=dict(completed.manager_observations),
            committed_tactics=tuple(completed.committed_tactics),
        )

    def _spine_failure(
        self,
        completed: ManagedTurn,
        exc: Exception,
    ) -> ManagedTurn:
        health = NodeHealthEvent(
            node_id=self.node_id,
            status="committed_turn_spine_failed",
            message=(
                "failed to bind the exact post-turn committed proof spine; "
                "the node is fail-closed"
            ),
            state_version=self.repl.state_version,
        )
        self._audit({
            "kind": "committed_turn_spine.failed",
            "node": self.node_id,
            "error_type": type(exc).__name__,
            "error": str(exc)[:600],
            "health": health.to_dict(),
        })
        return replace(
            completed,
            ok=False,
            health_event=health,
            directive=TurnDirective.NODE_UNHEALTHY,
        )

    def _clear_replay_prefix(self) -> None:
        self.lifecycle.clear_replay_prefix()

    def _set_latest_view(self, view: dict[str, Any]) -> None:
        self.lifecycle.set_latest_view(view)

    def _project(
        self,
        snapshot: ProofStateSnapshot,
        *,
        latest_observation: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.admission.observe_projection(snapshot, latest_observation)
        return self.lifecycle.project(
            snapshot,
            latest_observation=latest_observation,
        )

    def _audit(self, record: dict[str, Any]) -> None:
        self.events.run_dir = self.run_dir
        self.events.audit(record)


def _confirmation_id(node_id: str, state_version: int, history_hash: str) -> str:
    seed = f"{node_id}:{state_version}:{history_hash}:{time.time_ns()}"
    return hashlib.sha1(seed.encode("utf-8")).hexdigest()[:16]
