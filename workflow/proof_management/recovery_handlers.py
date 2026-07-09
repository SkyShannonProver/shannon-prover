"""Checkpoint and replay recovery intent handling.

The facade owns turn rendering and audit.  This module owns the recovery
decision logic: checkpoint menus, checkpoint rewind/restore preparation, and
discarded-route replay probing/commit planning.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from workflow.proof_management.common import coerce_string_list as _string_list
from typing import Any, Literal

from .analyzers.route_health import current_route_health
from .checkpoint_surface import (
    checkpoint_id as make_checkpoint_id,
    semantic_checkpoint_overrides,
)
from .checkpoint_store import ProofCheckpointManager
from .lineage import LemmaLineageStore
from .memory_store import ProofMemoryManager, replay_chunk_public_surface
from .protocol_repair import AgentIntent
from .repl_session import history_hash
from .turn_view import intent_payload_surface
from core.easycrypt.value_shapes import as_dict as _dict, as_list as _list


RecoveryPlanKind = Literal["menu", "repl_call", "nonmutating"]


@dataclass(frozen=True)
class RecoveryTurnPlan:
    kind: RecoveryPlanKind
    observation: dict[str, Any] = field(default_factory=dict)
    label: str = ""
    audit_kind: str = ""
    call: Callable[[], tuple[Any, list[dict[str, Any]]]] | None = None
    actions: list[Any] = field(default_factory=list)
    audit_extra: dict[str, Any] = field(default_factory=dict)


class ProofRecoveryIntentHandler:
    """Owns checkpoint/replay recovery logic for one proof node."""

    def __init__(
        self,
        *,
        node_id: str,
        checkpoints: ProofCheckpointManager,
        proof_memory: ProofMemoryManager,
        lineage: LemmaLineageStore,
        repl: Any,
        committed_tactics: Callable[[], list[str]],
        latest_view: Callable[[], dict[str, Any]],
        replay_prefix_count: Callable[[], int],
        clear_replay_prefix: Callable[[], None],
        run_dir: Callable[[], Path | None],
        resumed_lineage: Callable[[], bool] | None = None,
    ) -> None:
        self.node_id = node_id
        self.checkpoints = checkpoints
        self.proof_memory = proof_memory
        self.lineage = lineage
        self.repl = repl
        self._committed_tactics = committed_tactics
        self._latest_view = latest_view
        self._replay_prefix_count = replay_prefix_count
        # Durable "node was resumed from an inherited prefix" predicate. The
        # transient ``replay_prefix_count`` is cleared by a rewind that crosses
        # the resume floor, so a guard that keys only off the count silently
        # lets a resumed node back into amend_and_replay after such a rewind.
        # Default keeps the historical count-only behavior for callers (tests)
        # that don't supply the durable flag.
        self._resumed_lineage = resumed_lineage
        self._clear_replay_prefix = clear_replay_prefix
        self._run_dir = run_dir

    def handle_fresh_restart(self, intent: AgentIntent) -> RecoveryTurnPlan:
        if not bool(intent.payload.get("confirm")):
            tactics = self._committed_tactics()
            if self.checkpoints.structural_recovery_available(tactics):
                return self._fresh_restart_structural_recovery_plan(
                    intent,
                    tactics=tactics,
                )
            return self._fresh_restart_confirmation_plan(intent)

        confirmation_id = str(intent.payload.get("confirmation_id") or "")
        if self._replay_prefix_count() > 0:
            return self._fresh_restart_confirmation_plan(
                intent,
                notice=(
                    "Fresh restart inside this node is disabled. To repair an "
                    "earlier step, choose a checkpoint from the rewind menu."
                ),
            )
        if (
            not confirmation_id
            or not self.checkpoints.is_fresh_restart_confirmed(intent.payload)
        ):
            return self._fresh_restart_confirmation_plan(intent)

        self.checkpoints.clear_fresh_restart_confirmation()

        def restart_and_clear_resume_prefix() -> tuple[Any, list[dict[str, Any]]]:
            snapshot, actions = self.repl.fresh_restart()
            self._clear_replay_prefix()
            return snapshot, actions

        return RecoveryTurnPlan(
            kind="repl_call",
            observation=self.checkpoints.fresh_restart_confirmed_observation(
                intent=intent.intent,
            ),
            call=restart_and_clear_resume_prefix,
            audit_extra={"proof_state_effect": "fresh_restart_confirmed"},
        )

    def handle_amend_and_replay(self, intent: AgentIntent) -> RecoveryTurnPlan:
        """Edit ONE committed step and replay the rest, stopping at the first step
        the edit invalidates.

        Lets the agent fix an early/root tactic (the opener, an early invariant)
        without re-deriving the ~90%-identical skeleton — the audited fresh_restart
        waste. The agent reads `proof_so_far`, picks the step index, and supplies the
        corrected tactic; the replay keeps every step that still holds and leaves the
        session at the divergence point. A pre-edit restore anchor is saved so the
        agent can back out via `undo_to_checkpoint` with the returned restore id.
        """
        tactics = self._committed_tactics()
        corrected = str(intent.payload.get("tactic") or "").strip()
        try:
            index = int(intent.payload.get("index"))
        except (TypeError, ValueError):
            index = 0

        if not corrected:
            return self.checkpoint_selection_plan(intent, notice=(
                "amend_and_replay needs the corrected tactic in payload `tactic`. "
                "No proof state changed."
            ))
        if index < 1 or index > len(tactics):
            return self.checkpoint_selection_plan(intent, notice=(
                f"amend_and_replay `index` must be a committed step in 1..{len(tactics)} "
                "(see the proof_so_far panel). No proof state changed."
            ))
        if self._is_resumed_node():
            return self.checkpoint_selection_plan(intent, notice=(
                "amend_and_replay is disabled inside a resumed node (its history "
                "already includes an internally replayed prefix). Use the rewind menu."
            ))

        edited = tactics[: index - 1] + [corrected] + tactics[index:]
        self.checkpoints.save_pre_rewind_restore_anchor(
            tactics=tactics,
            checkpoint_id=make_checkpoint_id(history_hash(tactics), index),
            tactic_index=index,
            state_version=self.repl.state_version,
        )

        def amend_call() -> tuple[Any, list[dict[str, Any]]]:
            return self.repl.restart_with_edited_prefix(edited)

        return RecoveryTurnPlan(
            kind="repl_call",
            observation={
                "intent": intent.intent,
                "kind": "amend_and_replay",
                "message": (
                    f"Replaced committed step {index} (`{tactics[index - 1]}`) with "
                    f"`{corrected}` and replayed the rest, stopping at the first step "
                    "the edit invalidated. Read the refreshed goal and continue from "
                    "where the replay stopped."
                ),
                "amended_step": index,
                "amended_tactic": corrected,
                "original_tactic": tactics[index - 1],
            },
            call=amend_call,
            audit_extra={"proof_state_effect": "amend_and_replay"},
        )

    def _is_resumed_node(self) -> bool:
        """True iff this node was resumed from an inherited prefix.

        Prefers the durable lineage marker (set once at bootstrap/adopt, never
        cleared by a rewind) and falls back to the transient resume-floor count
        for callers that don't supply it. The count alone is unsafe: a rewind
        that crosses the resume floor clears it, which would otherwise re-enable
        amend_and_replay on a resumed node (CBC_upto Tree-0.0.r2, 2026-06-25).
        """
        if self._resumed_lineage is not None and bool(self._resumed_lineage()):
            return True
        return self._replay_prefix_count() > 0

    def handle_undo_to_checkpoint(self, intent: AgentIntent) -> RecoveryTurnPlan:
        restore_id = str(intent.payload.get("restore_id") or "").strip()
        if restore_id:
            return self._restore_before_last_rewind_plan(intent, restore_id)
        checkpoint_id = str(intent.payload.get("checkpoint_id") or "").strip()
        if not checkpoint_id and intent.payload.get("index") is not None:
            # Index-addressed rewind off the `proof_so_far` panel (mirrors
            # amend_and_replay): build the checkpoint id from the CURRENT committed
            # history so a goal-only L1 agent — which has no checkpoint menu — can
            # still rewind to a numbered committed step. The id then validates against
            # the live digest below like any other.
            _tactics = self._committed_tactics()
            try:
                _idx = int(intent.payload.get("index"))
            except (TypeError, ValueError):
                _idx = 0
            if 1 <= _idx <= len(_tactics):
                checkpoint_id = make_checkpoint_id(history_hash(_tactics), _idx)
        if not checkpoint_id:
            return self.checkpoint_selection_plan(intent)

        tactics = self._committed_tactics()
        parsed = self.checkpoints.parse_checkpoint_id(checkpoint_id)
        digest = history_hash(tactics)
        if parsed is None or parsed[0] < 1 or parsed[0] > len(tactics):
            # The target step index itself is gone (unparseable id, or the
            # committed proof is now shorter than that index). This is genuinely
            # unreachable from the current scope — say so EXPLICITLY rather than
            # returning a silent identical re-prompt (panel-defect #2,
            # docs/reports/insights/l4_panel_defects_equiv_step4.md).
            return self.checkpoint_selection_plan(
                intent,
                notice=(
                    "TARGET NOT REACHABLE FROM THIS SCOPE: the requested rewind "
                    "target is not a committed tactic in this node's current "
                    "history (it may have been undone already, or never existed). "
                    "No proof state changed. Choose a target from the options "
                    "below, which are computed from the CURRENT committed proof."
                ),
            )
        if parsed[1] != digest[:16]:
            # The step index is still valid but the committed history advanced
            # since this id was issued (an intervening commit/undo re-hashed the
            # history), so the stale id no longer matches. This is NOT a no-op and
            # NOT "unreachable" — the same step is still rewindable under a fresh
            # id. Hand back the REFRESHED id for the same step so the agent can
            # re-submit immediately instead of perceiving a silent re-prompt
            # (panel-defect #2).
            fresh_id = make_checkpoint_id(digest, parsed[0])
            return self.checkpoint_selection_plan(
                intent,
                notice=(
                    "Your rewind target's id was issued against an earlier "
                    "committed history (a tactic was committed/undone since), so "
                    "the stale id was rejected and NOTHING was rewound. The same "
                    f"committed tactic #{parsed[0]} is still rewindable under the "
                    f"refreshed id `{fresh_id}` — re-submit `undo_to_checkpoint` "
                    "with that id (the options below already carry fresh ids)."
                ),
            )

        tactic_index = parsed[0]
        tactic = tactics[tactic_index - 1]
        confirmed = self.checkpoints.is_rewind_confirmed(
            intent.payload,
            checkpoint_id=checkpoint_id,
        )
        if (
            self.checkpoints.rewind_leaves_current_call_scope(tactics, tactic_index)
            and not confirmed
        ):
            return self._checkpoint_rewind_confirmation_plan(
                intent,
                tactics=tactics,
                checkpoint_id=checkpoint_id,
                tactic_index=tactic_index,
            )

        self.checkpoints.clear_rewind_confirmation()
        self.checkpoints.save_pre_rewind_restore_anchor(
            tactics=tactics,
            checkpoint_id=checkpoint_id,
            tactic_index=tactic_index,
            state_version=self.repl.state_version,
        )
        self.proof_memory.run_dir = self._run_dir()
        memory = self.proof_memory.record_checkpoint_rewind(
            tactics=tactics,
            checkpoint_id=checkpoint_id,
            tactic_index=tactic_index,
            state_version=self.repl.state_version,
            rewind_note=_dict(intent.payload.get("rewind_note")),
        )
        if memory:
            self.lineage.run_dir = self._run_dir()
            self.lineage.record_repair_episode(
                node_id=self.node_id,
                memory=memory,
            )
        observation = self.checkpoints.checkpoint_rewind_observation(
            intent=intent.intent,
            payload=intent_payload_surface(intent),
            tactic_index=tactic_index,
            committed_tactic=tactic,
            committed_tactics=tactics,
        )
        undone_count = int(observation.get("undone_tactic_count") or 0)
        # A rewind whose target sits inside the internally replayed prefix
        # partly discards that prefix, so the internal replay-prefix protection
        # must be lifted and the run continues correctly from the shorter
        # prefix. This is fully transparent to the agent: it perceives one
        # continuous proof it owns and just rewinds before a committed tactic.
        # We only keep an INTERNAL audit note (audit_extra is debug, never shown
        # to the agent). The rewind mechanism itself (rewind_before_tactic) was
        # never prefix-gated — it simply replays a shorter prefix.
        replay_count = self._replay_prefix_count()
        rewind_enters_replayed_prefix = bool(
            replay_count > 0 and tactic_index <= replay_count
        )
        checkpoint_audit: dict[str, Any] = {
            "tactic_index": tactic_index,
            "committed_tactic": tactic,
            "undone_tactic_count": undone_count,
        }
        if rewind_enters_replayed_prefix:
            checkpoint_audit["crosses_resume_floor"] = True
            checkpoint_audit["prior_replay_prefix_count"] = int(replay_count)

        def rewind_and_clear_prefix() -> tuple[Any, list[dict[str, Any]]]:
            result = self.repl.rewind_before_tactic(tactic_index)
            if rewind_enters_replayed_prefix:
                self._clear_replay_prefix()
            return result

        return RecoveryTurnPlan(
            kind="repl_call",
            observation=observation,
            call=rewind_and_clear_prefix,
            audit_extra={
                "proof_state_effect": "rewind_before_checkpoint",
                "checkpoint": checkpoint_audit,
            },
        )

    def handle_probe_replay_suffix_chunk(
        self,
        intent: AgentIntent,
    ) -> RecoveryTurnPlan:
        resolved = self.proof_memory.resolve_replay_suffix_chunk(
            self._committed_tactics(),
            str(intent.payload.get("chunk_id") or ""),
        )
        if not resolved:
            return self.replay_suffix_chunk_menu_plan(
                intent,
                notice=(
                    "That replay chunk is no longer available for the current "
                    "route memory. Choose from the current replay options."
                ),
            )

        current_tactics = self._committed_tactics()
        result = self.repl.verify_tactic_chunk_from_prefix(
            current_tactics,
            _string_list(resolved.get("tactics")),
        )
        if bool(result.get("ok")):
            self.proof_memory.remember_verified_replay_chunk(
                current_tactics=current_tactics,
                chunk=resolved,
            )
        observation = self.proof_memory.replay_suffix_probe_observation(
            intent=intent.intent,
            payload=intent_payload_surface(intent),
            chunk=resolved,
            result=result,
        )
        return RecoveryTurnPlan(
            kind="nonmutating",
            observation=observation,
            actions=_list(result.get("actions")),
            audit_kind="replay_suffix_chunk.probed",
        )

    def handle_commit_replay_suffix_chunk(
        self,
        intent: AgentIntent,
    ) -> RecoveryTurnPlan:
        resolved = self.proof_memory.resolve_replay_suffix_chunk(
            self._committed_tactics(),
            str(intent.payload.get("chunk_id") or ""),
        )
        if not resolved:
            return self.replay_suffix_chunk_menu_plan(
                intent,
                notice=(
                    "That replay chunk is no longer available for the current "
                    "route memory. Choose from the current replay options."
                ),
            )

        current_tactics = self._committed_tactics()
        chunk_tactics = _string_list(resolved.get("tactics"))
        if not self.proof_memory.replay_chunk_is_verified(
            current_tactics=current_tactics,
            chunk=resolved,
        ):
            result = self.repl.verify_tactic_chunk_from_prefix(
                current_tactics,
                chunk_tactics,
            )
            if not bool(result.get("ok")):
                observation = self.proof_memory.replay_suffix_commit_blocked_observation(
                    intent=intent.intent,
                    payload=intent_payload_surface(intent),
                    chunk=resolved,
                    result=result,
                )
                return RecoveryTurnPlan(
                    kind="nonmutating",
                    observation=observation,
                    actions=_list(result.get("actions")),
                    audit_kind="replay_suffix_chunk.commit_blocked",
                )

        observation = self.proof_memory.replay_suffix_commit_observation(
            intent=intent.intent,
            payload=intent_payload_surface(intent),
            chunk=resolved,
        )
        return RecoveryTurnPlan(
            kind="repl_call",
            observation=observation,
            call=lambda: self.repl.restore_committed_tactics(
                [*current_tactics, *chunk_tactics],
                label="commit_replay_suffix_chunk",
            ),
            audit_extra={
                "proof_state_effect": "commit_replay_suffix_chunk",
                "chunk": replay_chunk_public_surface(resolved),
            },
        )

    def checkpoint_selection_plan(
        self,
        intent: AgentIntent,
        *,
        notice: str = "",
    ) -> RecoveryTurnPlan:
        tactics = self._committed_tactics()
        checkpoint_options = self.checkpoints.menu_options(
            tactics,
            route_health=current_route_health(self._latest_view()),
            replay_prefix_count=self._replay_prefix_count(),
        )
        restore_option = self.checkpoints.pre_rewind_restore_option()
        checkpoint_index = self.checkpoints.build_index(
            menu_options=checkpoint_options,
            restore_option=restore_option,
        )
        observation = self.checkpoints.checkpoint_selection_observation(
            intent=intent.intent,
            notice=notice,
            checkpoint_index=checkpoint_index,
        )
        return RecoveryTurnPlan(
            kind="menu",
            observation=observation,
            label="checkpoint_selection",
            audit_kind="checkpoint_selection.requested",
        )

    def replay_suffix_chunk_menu_plan(
        self,
        intent: AgentIntent,
        *,
        notice: str = "",
    ) -> RecoveryTurnPlan:
        observation = self.proof_memory.replay_suffix_chunk_selection_observation(
            intent=intent.intent,
            payload=intent_payload_surface(intent),
            current_tactics=self._committed_tactics(),
            notice=notice,
        )
        return RecoveryTurnPlan(
            kind="menu",
            observation=observation,
            label="replay_suffix_chunk_selection",
            audit_kind="replay_suffix_chunk.selection_requested",
        )

    def _fresh_restart_structural_recovery_plan(
        self,
        intent: AgentIntent,
        *,
        tactics: list[str],
    ) -> RecoveryTurnPlan:
        observation = self.checkpoints.structural_recovery_observation(
            intent=intent.intent,
            tactics=tactics,
            state_version=self.repl.state_version,
            route_health=current_route_health(self._latest_view()),
            replay_prefix_count=self._replay_prefix_count(),
        )
        return RecoveryTurnPlan(
            kind="menu",
            observation=observation,
            label="structural_recovery_menu",
            audit_kind="fresh_restart.structural_recovery_menu",
        )

    def _fresh_restart_confirmation_plan(
        self,
        intent: AgentIntent,
        *,
        notice: str = "",
    ) -> RecoveryTurnPlan:
        observation = self.checkpoints.fresh_restart_confirmation_observation(
            intent=intent.intent,
            tactics=self._committed_tactics(),
            state_version=self.repl.state_version,
            replay_prefix_count=self._replay_prefix_count(),
            notice=notice,
        )
        return RecoveryTurnPlan(
            kind="menu",
            observation=observation,
            label="fresh_restart_confirmation",
            audit_kind="fresh_restart.confirmation_requested",
        )

    def _restore_before_last_rewind_plan(
        self,
        intent: AgentIntent,
        restore_id: str,
    ) -> RecoveryTurnPlan:
        anchor = self.checkpoints.restore_anchor(restore_id)
        if not anchor:
            return self.checkpoint_selection_plan(
                intent,
                notice=(
                    "That restore choice no longer matches the current "
                    "recovery state. Choose from the current options."
                ),
            )
        tactics = [
            str(tactic).strip()
            for tactic in _list(anchor.get("tactics"))
            if str(tactic).strip()
        ]
        if not tactics:
            return self.checkpoint_selection_plan(
                intent,
                notice=(
                    "That restore choice has no committed tactics to replay. "
                    "Choose from the current options."
                ),
            )
        observation = self.checkpoints.checkpoint_restore_observation(
            intent=intent.intent,
            payload=intent_payload_surface(intent),
            anchor=anchor,
        )

        def restore_and_clear() -> tuple[Any, list[dict[str, Any]]]:
            snapshot, actions = self.repl.restore_committed_tactics(tactics)
            self.checkpoints.clear_restore_anchor()
            return snapshot, actions

        return RecoveryTurnPlan(
            kind="repl_call",
            observation=observation,
            call=restore_and_clear,
            audit_extra={
                "proof_state_effect": "restore_before_last_rewind",
                "restore": {
                    "restore_id": restore_id,
                    "from_checkpoint_id": anchor.get("from_checkpoint_id"),
                    "from_tactic_index": anchor.get("from_tactic_index"),
                },
            },
        )

    def _checkpoint_rewind_confirmation_plan(
        self,
        intent: AgentIntent,
        *,
        tactics: list[str],
        checkpoint_id: str,
        tactic_index: int,
    ) -> RecoveryTurnPlan:
        confirmation_id = self.checkpoints.rewind_confirmation_token(
            tactics=tactics,
            state_version=self.repl.state_version,
            checkpoint_id=checkpoint_id,
        )
        option = self.checkpoints.checkpoint_option(
            tactics,
            tactic_index,
            override=semantic_checkpoint_overrides(
                tactics,
                route_health=current_route_health(self._latest_view()),
                replay_prefix_count=self._replay_prefix_count(),
            ).get(tactic_index),
        )
        option["submit"] = {
            "intent": "undo_to_checkpoint",
            "payload": {
                "checkpoint_id": checkpoint_id,
                "confirm": True,
                "confirmation_id": confirmation_id,
            },
        }
        option["effect_if_selected"] = (
            "This confirms a rewind that leaves the current call obligation "
            "scope and returns the refreshed view."
        )
        observation = self.checkpoints.checkpoint_rewind_confirmation_observation(
            intent=intent.intent,
            checkpoint=option,
        )
        return RecoveryTurnPlan(
            kind="menu",
            observation=observation,
            label="checkpoint_rewind_confirmation",
            audit_kind="checkpoint_rewind.confirmation_requested",
        )



