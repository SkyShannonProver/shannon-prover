"""Checkpoint and explicit proof-control recovery intent handling.

The facade owns turn rendering and audit.  This module owns the recovery
decision logic: checkpoint menus and checkpoint rewind/restore preparation.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from core.easycrypt.session.session_placeholders import requires_placeholder_instantiation
from core.easycrypt.value_shapes import as_list as _list

from .checkpoint_surface import (
    checkpoint_id as make_checkpoint_id,
    semantic_checkpoint_overrides,
)
from .checkpoint_store import ProofCheckpointManager
from .protocol_repair import AgentIntent
from .checkpoint_surface import history_hash
from .turn_view import intent_payload_surface


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
        repl: Any,
        committed_tactics: Callable[[], list[str]],
        replay_prefix_count: Callable[[], int],
        clear_replay_prefix: Callable[[], None],
        resumed_lineage: Callable[[], bool],
    ) -> None:
        self.node_id = node_id
        self.checkpoints = checkpoints
        self.repl = repl
        self._committed_tactics = committed_tactics
        self._replay_prefix_count = replay_prefix_count
        # Durable "node was resumed from an inherited prefix" predicate. The
        # transient ``replay_prefix_count`` is cleared by a rewind that crosses
        # the resume floor, so a guard that keys only off the count silently
        # lets a resumed node back into amend_and_replay after such a rewind.
        self._resumed_lineage = resumed_lineage
        self._clear_replay_prefix = clear_replay_prefix

    def handle_fresh_restart(self, intent: AgentIntent) -> RecoveryTurnPlan:
        if intent.payload.get("confirm") is not True:
            tactics = self._committed_tactics()
            if self.checkpoints.structural_recovery_available(tactics):
                return self._fresh_restart_structural_recovery_plan(
                    intent,
                    tactics=tactics,
                )
            return self._fresh_restart_confirmation_plan(intent)

        confirmation_id = intent.payload.get("confirmation_id", "")
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
            audit_extra={"proof_state_operation": "fresh_restart_confirmed"},
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
        if self._is_resumed_node():
            return self.amend_selection_plan(
                intent,
                notice=(
                    "Amend & replay is disabled inside a resumed node because its "
                    "history already includes an inherited replayed prefix. Use "
                    "Rewind instead."
                ),
                include_items=False,
            )
        corrected = intent.payload.get("tactic", "").strip()
        index = intent.payload.get("index", 0)

        if not corrected or requires_placeholder_instantiation(corrected):
            return self.amend_selection_plan(
                intent,
                notice=(
                    "Choose a committed tactic and provide a concrete replacement. "
                    "No proof state changed."
                ),
            )
        if index < 1 or index > len(tactics):
            return self.amend_selection_plan(
                intent,
                notice=(
                    f"`index` must identify a committed step in 1..{len(tactics)}. "
                    "Choose one of the steps below."
                ),
            )
        if corrected == tactics[index - 1].strip():
            return self.amend_selection_plan(
                intent,
                notice=(
                    "The replacement must differ from the committed tactic. "
                    "No proof state changed."
                ),
            )

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
            audit_extra={"proof_state_operation": "amend_and_replay"},
        )

    def amend_selection_plan(
        self,
        intent: AgentIntent,
        *,
        notice: str = "",
        include_items: bool = True,
    ) -> RecoveryTurnPlan:
        """Return the typed step-selection menu for Amend & replay."""
        tactics = self._committed_tactics()
        items: list[dict[str, Any]] = []
        if include_items:
            for index, tactic in enumerate(tactics, start=1):
                items.append({
                    "label": f"Amend committed tactic #{index}",
                    "committed_tactic": tactic,
                    "description": (
                        "Replace this tactic, then replay each later committed "
                        "tactic until the edited route diverges."
                    ),
                    "requires_input": ["tactic"],
                    "submit": {
                        "intent": "amend_and_replay",
                        "payload": {"index": index},
                    },
                })
        if not items and not notice:
            notice = (
                "No committed tactics are available to amend yet. Commit a proof "
                "step first."
            )
        observation = {
            "intent": intent.intent,
            "kind": "amend_selection",
            "control_menu": {
                "title": "Amend & replay",
                "notice": notice or (
                    "Choose a committed tactic and provide its replacement."
                ),
                "items": items,
            },
        }
        return RecoveryTurnPlan(
            kind="menu",
            observation=observation,
            label="amend_selection",
            audit_kind="amend_and_replay.selection_requested",
        )

    def _is_resumed_node(self) -> bool:
        """True iff this node was resumed from an inherited prefix.

        The durable lineage marker is set once at bootstrap/adopt and never
        cleared by a rewind. The transient count alone is unsafe: a rewind that
        crosses the resume floor clears it, which would otherwise re-enable
        amend_and_replay on a resumed node (CBC_upto Tree-0.0.r2, 2026-06-25).
        """
        return bool(self._resumed_lineage())

    def handle_undo_to_checkpoint(self, intent: AgentIntent) -> RecoveryTurnPlan:
        restore_id = intent.payload.get("restore_id", "")
        if restore_id:
            return self._restore_before_last_rewind_plan(intent, restore_id)
        checkpoint_id = intent.payload.get("checkpoint_id", "")
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
                "proof_state_operation": "rewind_before_checkpoint",
                "checkpoint": checkpoint_audit,
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
                "proof_state_operation": "restore_before_last_rewind",
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
