"""Proof-node checkpoint and restore state.

This service owns checkpoint domain state for one proof node: structural
checkpoint indexing, pending rewind confirmations, and the pre-rewind restore
anchor.  It renders ProverWorkspaceView-compatible checkpoint options, but it
does not execute EasyCrypt commands.
"""
from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .checkpoints import CheckpointIndex, CheckpointOption, checkpoint_option
from .checkpoint_surface import (
    checkpoint_option as build_checkpoint_option,
    checkpoint_options,
    parse_checkpoint_id,
    rewind_leaves_current_call_scope,
    route_health_checkpoint,
    structural_recovery_available,
    structural_checkpoints_surface,
)
from core.easycrypt.value_shapes import as_dict_copy as _dict_or_empty
from core.easycrypt.value_shapes import drop_empty as _drop_empty


logger = logging.getLogger(__name__)

HistoryHashFn = Callable[[list[str]], str]
ConfirmationIdFn = Callable[..., str]


class ProofCheckpointManager:
    """Owns checkpoint indexing, confirmation, and restore anchors."""

    def __init__(
        self,
        *,
        node_id: str,
        run_dir: Path | None = None,
        history_hash: HistoryHashFn,
        confirmation_id: ConfirmationIdFn,
    ) -> None:
        self.node_id = node_id
        self.run_dir = Path(run_dir) if run_dir is not None else None
        self._history_hash = history_hash
        self._confirmation_id = confirmation_id
        self.rewind_confirmation_id = ""
        self.rewind_confirmation_checkpoint_id = ""
        self.fresh_restart_confirmation_id = ""
        self.pre_rewind_restore_anchor: dict[str, Any] = {}
        self.legacy_pre_rewind_restore_option: dict[str, Any] = {}
        self._load_checkpoint_state_file()

    def seed_resume_payload(self, payload: dict[str, Any] | None) -> None:
        """Restore durable checkpoint state from a resume capsule."""
        data = _dict_or_empty(payload)
        anchor = _dict_or_empty(data.get("pre_rewind_restore_anchor"))
        if anchor and _string_list(anchor.get("tactics")):
            self.pre_rewind_restore_anchor = anchor
            self.write_checkpoint_state_file()
        legacy_restore = _dict_or_empty(data.get("legacy_pre_rewind_restore_option"))
        if legacy_restore and not self.pre_rewind_restore_anchor:
            self.legacy_pre_rewind_restore_option = legacy_restore

    def fresh_restart_confirmation_token(
        self,
        *,
        tactics: list[str],
        state_version: int,
    ) -> str:
        confirmation_id = self._confirmation_id(
            self.node_id,
            state_version,
            self._history_hash(tactics),
        )
        self.fresh_restart_confirmation_id = confirmation_id
        return confirmation_id

    def is_fresh_restart_confirmed(self, payload: dict[str, Any]) -> bool:
        return (
            bool(payload.get("confirm"))
            and str(payload.get("confirmation_id") or "")
            == self.fresh_restart_confirmation_id
        )

    def clear_fresh_restart_confirmation(self) -> None:
        self.fresh_restart_confirmation_id = ""

    def fresh_restart_confirmed_observation(self, *, intent: str) -> dict[str, Any]:
        return {
            "intent": intent,
            "kind": "fresh_restart_confirmed",
            "message": (
                "Fresh restart confirmed. This branch was erased to the "
                "target lemma."
            ),
        }

    def structural_recovery_observation(
        self,
        *,
        intent: str,
        tactics: list[str],
        state_version: int,
        route_health: list[dict[str, Any]] | None = None,
        replay_prefix_count: int = 0,
    ) -> dict[str, Any]:
        confirmation_id = self.fresh_restart_confirmation_token(
            tactics=tactics,
            state_version=state_version,
        )
        checkpoint_options = [
            option
            for option in self.menu_options(
                tactics,
                route_health=route_health,
                replay_prefix_count=replay_prefix_count,
            )
            if str(option.get("undo_scope") or "") in {
                "seq_local",
                "branch_local",
                "call_local",
                "call_obligation_local",
            }
        ][:4]
        replay_count = min(int(replay_prefix_count), len(tactics))
        options = [
            {
                "label": "Show all rewind choices",
                "effect_if_selected": (
                    "This shows committed tactics you can rewind before."
                ),
                "submit": {"intent": "undo_to_checkpoint", "payload": {}},
            },
        ]
        if replay_count <= 0:
            options.append({
                "label": "Erase branch and restart",
                "effect_if_selected": (
                    "This confirms erasing committed tactics in this node "
                    "and restarting from the target lemma."
                ),
                "submit": {
                    "intent": "fresh_restart",
                    "payload": {
                        "confirm": True,
                        "confirmation_id": confirmation_id,
                    },
                },
            })
        return _drop_empty({
            "intent": intent,
            "kind": "structural_recovery_menu",
            "message": (
                "A structural recovery boundary is available for the current "
                "committed branch."
            ),
            "checkpoint_options": checkpoint_options,
            "options": options,
        })

    def fresh_restart_confirmation_observation(
        self,
        *,
        intent: str,
        tactics: list[str],
        state_version: int,
        replay_prefix_count: int = 0,
        notice: str = "",
    ) -> dict[str, Any]:
        confirmation_id = self.fresh_restart_confirmation_token(
            tactics=tactics,
            state_version=state_version,
        )
        replay_count = min(int(replay_prefix_count), len(tactics))
        options: list[dict[str, Any]] = [
            {
                "label": "Undo last committed tactic",
                "effect_if_selected": (
                    "This will undo the last committed tactic in this node."
                ),
                "submit": {"intent": "undo_last_step", "payload": {}},
            },
        ]
        options.extend([
            {
                "label": "Show rewind choices",
                "effect_if_selected": (
                    "This will show committed tactics you can rewind before."
                ),
                "submit": {"intent": "undo_to_checkpoint", "payload": {}},
            },
        ])
        destructive_payload: dict[str, Any] = {
            "confirm": True,
            "confirmation_id": confirmation_id,
        }
        destructive_effect = (
            "This will erase all committed tactics in this node and restart "
            "from the target lemma."
        )
        # Fresh restart inside a node whose history includes an internally
        # replayed prefix is disabled (the protection is internal/invisible to
        # the agent); only offer the destructive option otherwise.
        if replay_count <= 0:
            options.append({
                "label": "Erase branch and restart",
                "effect_if_selected": destructive_effect,
                "submit": {
                    "intent": "fresh_restart",
                    "payload": destructive_payload,
                },
            })
        return {
            "intent": intent,
            "kind": "fresh_restart_confirmation",
            "message": (
                # Panel-defect #2: do NOT blanket-steer toward checkpoint rewind.
                # A rewind to a SHALLOW target inside the current call/seq scope is
                # reliable; a rewind that leaves the current call-obligation scope
                # requires a confirm step and is the costly path. Recommend by
                # reachability, not unconditionally.
                "Fresh restart is destructive (it erases this whole node). For a "
                "LOCAL route repair, a checkpoint rewind to a target inside the "
                "current call/seq scope is the lighter option; a rewind that "
                "leaves the current call-obligation scope needs an explicit "
                "confirm and undoes more."
            ),
            "notice": notice,
            "options": options,
        }

    def rewind_confirmation_token(
        self,
        *,
        tactics: list[str],
        state_version: int,
        checkpoint_id: str,
    ) -> str:
        confirmation_id = self._confirmation_id(
            self.node_id,
            state_version,
            self._history_hash(tactics),
        )
        self.rewind_confirmation_id = confirmation_id
        self.rewind_confirmation_checkpoint_id = checkpoint_id
        return confirmation_id

    def is_rewind_confirmed(
        self,
        payload: dict[str, Any],
        *,
        checkpoint_id: str,
    ) -> bool:
        """A confirmed rewind for the checkpoint we asked the agent to confirm.

        Panel-defect #2 (P0; docs/reports/insights/l4_panel_defects_equiv_step4.md):
        the `confirmation_id` was bound to `repl.state_version`, so once ANY turn
        bumped the version the token the agent was shown went stale and the
        re-submitted `confirm:true` silently degraded to the menu re-prompt — a
        perceived no-op. We DO NOT compare the version-bound token here anymore.
        The genuine guard that the target is still valid is the `checkpoint_id`
        itself (it embeds the committed-history hash and is re-validated against
        the CURRENT history by the caller). So a confirm is honored when:
          - `confirm:true`, AND
          - the `checkpoint_id` is the same target we asked the agent to confirm.
        This keeps the "acknowledge you are leaving call scope" gate (the agent
        must have first been shown the confirmation for THIS checkpoint) while no
        longer rejecting a perfectly valid confirm just because a later turn moved
        the version forward. The caller still rejects a checkpoint_id that no
        longer matches the current committed history before calling us.
        """
        if not bool(payload.get("confirm")):
            return False
        if checkpoint_id and checkpoint_id == self.rewind_confirmation_checkpoint_id:
            return True
        # Back-compat: an exact (still-fresh) token also confirms, even if the
        # stored checkpoint binding was cleared by an unrelated path.
        return (
            bool(self.rewind_confirmation_id)
            and str(payload.get("confirmation_id") or "")
            == self.rewind_confirmation_id
            and checkpoint_id == self.rewind_confirmation_checkpoint_id
        )

    def clear_rewind_confirmation(self) -> None:
        self.rewind_confirmation_id = ""
        self.rewind_confirmation_checkpoint_id = ""

    def save_pre_rewind_restore_anchor(
        self,
        *,
        tactics: list[str],
        checkpoint_id: str,
        tactic_index: int,
        state_version: int,
    ) -> dict[str, Any]:
        restore_id = "restore_" + self._confirmation_id(
            self.node_id,
            state_version,
            self._history_hash(tactics),
        )
        self.pre_rewind_restore_anchor = {
            "restore_id": restore_id,
            "tactics": list(tactics),
            "from_checkpoint_id": checkpoint_id,
            "from_tactic_index": tactic_index,
        }
        self.write_checkpoint_state_file()
        return dict(self.pre_rewind_restore_anchor)

    def restore_anchor(self, restore_id: str) -> dict[str, Any]:
        anchor = dict(self.pre_rewind_restore_anchor)
        if not anchor or restore_id != str(anchor.get("restore_id") or ""):
            return {}
        return anchor

    def clear_restore_anchor(self) -> None:
        self.pre_rewind_restore_anchor = {}
        self.write_checkpoint_state_file()

    def write_checkpoint_state_file(self) -> None:
        if self.run_dir is None:
            return
        try:
            path = self._checkpoint_state_file_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "kind": "proof_checkpoint_state",
                        "node_id": self.node_id,
                        "pre_rewind_restore_anchor": self.pre_rewind_restore_anchor,
                        "legacy_pre_rewind_restore_option": (
                            self.legacy_pre_rewind_restore_option
                        ),
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.warning("failed to write checkpoint state: %s", exc)

    def _load_checkpoint_state_file(self) -> None:
        if self.run_dir is None:
            return
        path = self._checkpoint_state_file_path()
        if not path.exists():
            return
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("failed to load checkpoint state: %s", exc)
            return
        self.seed_resume_payload(payload)

    def _checkpoint_state_file_path(self) -> Path:
        node_slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", self.node_id)
        root = self.run_dir if self.run_dir is not None else Path(".")
        return root / "checkpoint_state" / f"{node_slug}_checkpoint_state.json"

    def build_index(
        self,
        *,
        menu_options: list[dict[str, Any]] | None = None,
        structural_items: list[dict[str, Any]] | None = None,
        restore_option: dict[str, Any] | None = None,
    ) -> CheckpointIndex:
        restore = checkpoint_option(restore_option)
        menu = [
            CheckpointOption(dict(item))
            for item in (menu_options or [])
            if isinstance(item, dict)
        ]
        if restore is not None:
            menu = [restore, *menu]
        structural = [
            CheckpointOption(dict(item))
            for item in (structural_items or [])
            if isinstance(item, dict)
        ]
        if restore is not None:
            structural = [restore, *structural]
        return CheckpointIndex(
            menu_options=menu,
            structural_items=structural,
            restore_option=restore,
        )

    def pre_rewind_restore_option(self) -> dict[str, Any]:
        option = pre_rewind_restore_option(self.pre_rewind_restore_anchor)
        if option:
            return option
        return dict(self.legacy_pre_rewind_restore_option)

    def parse_checkpoint_id(self, checkpoint_id: str) -> tuple[int, str] | None:
        return parse_checkpoint_id(checkpoint_id)

    def menu_options(
        self,
        tactics: list[str],
        *,
        route_health: list[dict[str, Any]] | None = None,
        replay_prefix_count: int = 0,
    ) -> list[dict[str, Any]]:
        return checkpoint_options(
            tactics,
            route_health=route_health,
            replay_prefix_count=replay_prefix_count,
        )

    def structural_surface(
        self,
        tactics: list[str],
        *,
        route_health: list[dict[str, Any]] | None = None,
        replay_prefix_count: int = 0,
    ) -> list[dict[str, Any]]:
        return structural_checkpoints_surface(
            tactics,
            route_health=route_health,
            replay_prefix_count=replay_prefix_count,
        )

    def checkpoint_option(
        self,
        tactics: list[str],
        tactic_index: int,
        *,
        override: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return build_checkpoint_option(
            tactics,
            self._history_hash(tactics),
            tactic_index,
            override=override,
        )

    def route_health_checkpoint(
        self,
        tactics: list[str],
        tactic_index: int,
        *,
        why_here: str,
    ) -> dict[str, Any]:
        return route_health_checkpoint(
            tactics,
            tactic_index,
            why_here=why_here,
        )

    def rewind_leaves_current_call_scope(
        self,
        tactics: list[str],
        tactic_index: int,
    ) -> bool:
        return rewind_leaves_current_call_scope(tactics, tactic_index)

    def structural_recovery_available(self, tactics: list[str]) -> bool:
        return structural_recovery_available(tactics)

    def checkpoint_selection_observation(
        self,
        *,
        intent: str,
        notice: str,
        checkpoint_index: CheckpointIndex,
    ) -> dict[str, Any]:
        options = checkpoint_index.menu_surface()
        if not options and not notice:
            notice = (
                "No committed tactics are available to rewind yet. Commit a proof "
                "step first; then Rewind will show targets."
            )
        return _drop_empty({
            "intent": intent,
            "kind": "checkpoint_selection",
            "message": (
                "Choose the committed tactic you want to rewind before."
                if options else "No rewind targets are available."
            ),
            "notice": notice,
            "checkpoint_options": options,
        })

    def checkpoint_rewind_observation(
        self,
        *,
        intent: str,
        payload: dict[str, Any],
        tactic_index: int,
        committed_tactic: str,
        committed_tactics: list[str],
    ) -> dict[str, Any]:
        undone_count = len(committed_tactics) - (int(tactic_index) - 1)
        return _drop_empty({
            "intent": intent,
            "payload": _dict_or_empty(payload),
            "kind": "checkpoint_rewind",
            "message": f"Rewound this branch to before committed tactic #{tactic_index}.",
            "tactic_index": int(tactic_index),
            "committed_tactic": committed_tactic,
            "undone_tactic_count": undone_count,
        })

    def checkpoint_restore_observation(
        self,
        *,
        intent: str,
        payload: dict[str, Any],
        anchor: dict[str, Any],
    ) -> dict[str, Any]:
        return _drop_empty({
            "intent": intent,
            "payload": _dict_or_empty(payload),
            "kind": "checkpoint_restore",
            "message": (
                "Restored this branch to the proof state saved before the "
                "last checkpoint rewind."
            ),
            "semantic_id": "restore_before_last_rewind",
            "restored_from": anchor.get("from_checkpoint_id"),
        })

    def checkpoint_rewind_confirmation_observation(
        self,
        *,
        intent: str,
        checkpoint: dict[str, Any],
    ) -> dict[str, Any]:
        return _drop_empty({
            "intent": intent,
            "kind": "checkpoint_rewind_confirmation",
            "message": (
                "This rewind leaves the current call obligation scope. "
                "Confirm it only if that broader recovery boundary is the "
                "state you want to restore."
            ),
            "checkpoint": checkpoint,
            "options": [
                {
                    "label": "Show current rewind choices",
                    "effect_if_selected": (
                        "This returns to the checkpoint menu without changing "
                        "the proof state."
                    ),
                    "submit": {"intent": "undo_to_checkpoint", "payload": {}},
                },
            ],
        })



def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def pre_rewind_restore_option(anchor: dict[str, Any]) -> dict[str, Any]:
    restore_id = str(_dict_or_empty(anchor).get("restore_id") or "").strip()
    if not restore_id:
        return {}
    return {
        "semantic_id": "restore_before_last_rewind",
        "semantic_ids": ["restore_before_last_rewind"],
        "label": "Restore before last checkpoint rewind",
        "restored_proof_layer": "pre_rewind_state",
        "undo_scope": "restore_pre_rewind",
        "why_checkpoint": (
            "state saved before the last checkpoint rewind; selecting it "
            "returns to that proof state"
        ),
        "effect_if_selected": (
            "This restores the branch to the proof state saved before the "
            "last checkpoint rewind."
        ),
        "submit": {
            "intent": "undo_to_checkpoint",
            "payload": {"restore_id": restore_id},
        },
    }


