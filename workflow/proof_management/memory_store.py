"""Proof-node route and repair memory.

This service owns manager-level memory that should survive across local
repairs: discarded route suffixes, their replay chunks, and optional rewind
notes.  It deliberately does not execute EasyCrypt tactics; replay and commit
remain ReplSessionManager responsibilities.
"""
from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core.easycrypt.value_shapes import as_dict_copy as _dict_or_empty
from core.easycrypt.value_shapes import drop_empty as _drop_empty
from workflow.proof_management.repair_notes import (
    normalize_rewind_note,
    rewind_note_summary,
)
from workflow.proof_management.tactic_utils import tactic_head as _tactic_head
from workflow.proof_management.transitions import normalize_tactic_for_transition


logger = logging.getLogger(__name__)

HistoryHashFn = Callable[[list[str]], str]
ConfirmationIdFn = Callable[..., str]


@dataclass(frozen=True)
class RoutePiece:
    piece_id: str
    tactic: str
    offset: int
    replay_class: str = "unknown"
    intent: str = ""
    goal_tag: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _drop_empty({
            "piece_id": self.piece_id,
            "tactic": self.tactic,
            "offset": self.offset,
            "replay_class": self.replay_class,
            "intent": self.intent,
            "goal_tag": self.goal_tag,
            "metadata": self.metadata,
        })

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "RoutePiece":
        return cls(
            piece_id=str(value.get("piece_id") or ""),
            tactic=str(value.get("tactic") or ""),
            offset=_safe_int(value.get("offset")),
            replay_class=str(value.get("replay_class") or "unknown"),
            intent=str(value.get("intent") or ""),
            goal_tag=str(value.get("goal_tag") or ""),
            metadata=_dict_or_empty(value.get("metadata")),
        )


@dataclass(frozen=True)
class RepairEpisode:
    episode_id: str
    node_id: str
    created_at: str
    from_checkpoint_id: str
    from_tactic_index: int
    kept_prefix_end: int
    rewind_note: dict[str, Any] = field(default_factory=dict)
    discarded_pieces: list[RoutePiece] = field(default_factory=list)
    route_memory_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return _drop_empty({
            "episode_id": self.episode_id,
            "node_id": self.node_id,
            "created_at": self.created_at,
            "from_checkpoint_id": self.from_checkpoint_id,
            "from_tactic_index": self.from_tactic_index,
            "kept_prefix_end": self.kept_prefix_end,
            "rewind_note": self.rewind_note,
            "discarded_pieces": [
                piece.to_dict() for piece in self.discarded_pieces
            ],
            "route_memory_id": self.route_memory_id,
        })

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "RepairEpisode":
        return cls(
            episode_id=str(value.get("episode_id") or ""),
            node_id=str(value.get("node_id") or ""),
            created_at=str(value.get("created_at") or ""),
            from_checkpoint_id=str(value.get("from_checkpoint_id") or ""),
            from_tactic_index=_safe_int(value.get("from_tactic_index")),
            kept_prefix_end=_safe_int(value.get("kept_prefix_end")),
            rewind_note=_rewind_note_dict(value.get("rewind_note")),
            discarded_pieces=[
                RoutePiece.from_dict(item)
                for item in _dict_list(value.get("discarded_pieces"))
            ],
            route_memory_id=str(value.get("route_memory_id") or ""),
        )


@dataclass(frozen=True)
class NegativeMemory:
    memory_id: str
    created_at: str
    source_episode_id: str
    source_route_memory_id: str
    kind: str = "avoid_pattern"
    scope: str = ""
    avoid_pattern: str = ""
    reason: str = ""
    applies_when: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _drop_empty({
            "memory_id": self.memory_id,
            "created_at": self.created_at,
            "source_episode_id": self.source_episode_id,
            "source_route_memory_id": self.source_route_memory_id,
            "kind": self.kind,
            "scope": self.scope,
            "avoid_pattern": self.avoid_pattern,
            "reason": self.reason,
            "applies_when": self.applies_when,
            "evidence": self.evidence,
        })

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "NegativeMemory":
        return cls(
            memory_id=str(value.get("memory_id") or ""),
            created_at=str(value.get("created_at") or ""),
            source_episode_id=str(value.get("source_episode_id") or ""),
            source_route_memory_id=str(value.get("source_route_memory_id") or ""),
            kind=str(value.get("kind") or "avoid_pattern"),
            scope=str(value.get("scope") or ""),
            avoid_pattern=str(value.get("avoid_pattern") or ""),
            reason=str(value.get("reason") or ""),
            applies_when=str(value.get("applies_when") or ""),
            evidence=_dict_or_empty(value.get("evidence")),
        )


@dataclass(frozen=True)
class RouteMemory:
    memory_id: str
    created_at: str
    node_id: str
    repair_episode_id: str
    from_checkpoint_id: str
    from_tactic_index: int
    kept_prefix_end: int
    kept_prefix_hash: str
    discarded_suffix: list[str] = field(default_factory=list)
    discarded_pieces: list[RoutePiece] = field(default_factory=list)
    rewind_note: dict[str, Any] = field(default_factory=dict)
    structural_chunks: list[dict[str, Any]] = field(default_factory=list)
    stale_piece_ids: list[str] = field(default_factory=list)
    negative_memory_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return _drop_empty({
            "memory_id": self.memory_id,
            "created_at": self.created_at,
            "node_id": self.node_id,
            "repair_episode_id": self.repair_episode_id,
            "from_checkpoint_id": self.from_checkpoint_id,
            "from_tactic_index": self.from_tactic_index,
            "kept_prefix_end": self.kept_prefix_end,
            "kept_prefix_hash": self.kept_prefix_hash,
            "discarded_suffix": list(self.discarded_suffix),
            "discarded_pieces": [
                piece.to_dict() for piece in self.discarded_pieces
            ],
            "rewind_note": self.rewind_note,
            "structural_chunks": [
                dict(item) for item in self.structural_chunks
            ],
            "stale_piece_ids": list(self.stale_piece_ids),
            "negative_memory_ids": list(self.negative_memory_ids),
        })

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "RouteMemory":
        memory_id = str(value.get("memory_id") or "")
        kept_prefix_end = _safe_int(value.get("kept_prefix_end"))
        discarded_suffix = _string_list(value.get("discarded_suffix"))
        pieces = [
            RoutePiece.from_dict(item)
            for item in _dict_list(value.get("discarded_pieces"))
        ]
        if not pieces:
            pieces = _route_pieces(
                discarded_suffix,
                memory_id=memory_id or "route_loaded",
                base_offset=kept_prefix_end,
            )
        chunks = [
            dict(item)
            for item in _dict_list(value.get("structural_chunks"))
        ]
        if not chunks:
            chunks = _route_memory_structural_chunks(
                discarded_suffix,
                memory_id=memory_id or "route_loaded",
            )
        return cls(
            memory_id=memory_id,
            created_at=str(value.get("created_at") or ""),
            node_id=str(value.get("node_id") or ""),
            repair_episode_id=str(value.get("repair_episode_id") or ""),
            from_checkpoint_id=str(value.get("from_checkpoint_id") or ""),
            from_tactic_index=_safe_int(value.get("from_tactic_index")),
            kept_prefix_end=kept_prefix_end,
            kept_prefix_hash=str(value.get("kept_prefix_hash") or ""),
            discarded_suffix=discarded_suffix,
            discarded_pieces=pieces,
            rewind_note=_rewind_note_dict(value.get("rewind_note")),
            structural_chunks=chunks,
            stale_piece_ids=_string_list(value.get("stale_piece_ids")),
            negative_memory_ids=_string_list(value.get("negative_memory_ids")),
        )


@dataclass(frozen=True)
class RouteMemorySnapshot:
    node_id: str
    route_memories: list[RouteMemory] = field(default_factory=list)
    repair_episodes: list[RepairEpisode] = field(default_factory=list)
    negative_memories: list[NegativeMemory] = field(default_factory=list)
    verified_route_options: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        open_episode = self.repair_episodes[0].episode_id if self.repair_episodes else ""
        return _drop_empty({
            "kind": "route_memory_snapshot",
            "node_id": self.node_id,
            "open_repair_episode": open_episode,
            "route_memory_count": len(self.route_memories),
            "repair_episode_count": len(self.repair_episodes),
            "negative_memory_count": len(self.negative_memories),
            "verified_route_option_count": len(self.verified_route_options),
            "route_memories": [
                memory.to_dict() for memory in self.route_memories
            ],
            "repair_episodes": [
                episode.to_dict() for episode in self.repair_episodes
            ],
            "negative_memories": [
                memory.to_dict() for memory in self.negative_memories
            ],
            "verified_route_options": [
                dict(item) for item in self.verified_route_options
            ],
        })


class ProofMemoryManager:
    """Owns route replay memory for one proof node."""

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
        self.route_memories: list[RouteMemory] = []
        self.repair_episodes: list[RepairEpisode] = []
        self.negative_memories: list[NegativeMemory] = []
        self.verified_route_options: list[dict[str, Any]] = []
        self.legacy_route_replay_memory: dict[str, Any] = {}
        self._verified_replay_chunks: dict[str, dict[str, Any]] = {}
        self._load_route_replay_memory_file()

    def seed_resume_payload(
        self,
        payload: dict[str, Any] | None,
        *,
        latest_workspace_view: dict[str, Any] | None = None,
    ) -> None:
        """Restore route/recovery memory supplied by a resume capsule."""
        payload = _dict_or_empty(payload)
        if payload:
            self._load_route_replay_memory_payload(payload)
            if self.route_memories:
                # Re-key the adopted memory under THIS node's slug. A Layer-3
                # respawn child (`Tree-0.0.r0`) inherits the dead node's
                # (`Tree-0.0`) route memory via the capsule payload; without
                # this write the file on disk stays keyed to the dead node and
                # the NEXT capsule mint / respawn for the child finds nothing.
                self.write_route_replay_memory_file()
        if not self.route_memories:
            legacy = _legacy_route_replay_surface_from_payload(payload)
            if not legacy:
                legacy = _legacy_route_replay_surface_from_view(
                    _dict_or_empty(latest_workspace_view)
                )
            if legacy:
                self.legacy_route_replay_memory = legacy

    def seed_verified_route_options(
        self,
        options: list[dict[str, Any]] | None,
    ) -> None:
        """Restore daemon-verified route options from a resume capsule."""
        clean_options = [
            item for item in (
                _verified_route_option_entry(option)
                for option in list(options or [])
                if isinstance(option, dict)
            )
            if item
        ]
        if not clean_options:
            return
        seen: set[str] = set()
        merged: list[dict[str, Any]] = []
        for item in [*clean_options, *self.verified_route_options]:
            key = str(item.get("option_id") or "")
            if not key:
                submit = _dict_or_empty(item.get("submit"))
                payload = _dict_or_empty(submit.get("payload"))
                key = str(payload.get("tactic") or item.get("semantic_objective") or "")
            if not key or key in seen:
                continue
            seen.add(key)
            merged.append(item)
        self.verified_route_options = merged[:10]

    def route_memory_snapshot(self) -> RouteMemorySnapshot:
        return RouteMemorySnapshot(
            node_id=self.node_id,
            route_memories=list(self.route_memories),
            repair_episodes=list(self.repair_episodes),
            negative_memories=list(self.negative_memories),
            verified_route_options=[
                dict(item) for item in self.verified_route_options
            ],
        )

    def record_checkpoint_rewind(
        self,
        *,
        tactics: list[str],
        checkpoint_id: str,
        tactic_index: int,
        state_version: int,
        rewind_note: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Save the discarded suffix before a checkpoint rewind."""
        normalized_rewind_note = _rewind_note_dict(rewind_note)
        kept_prefix_end = max(0, int(tactic_index) - 1)
        discarded_suffix = list(tactics[kept_prefix_end:])
        if self.route_memories:
            latest = self.route_memories[0].to_dict()
            if int(latest.get("kept_prefix_end") or -1) == len(tactics):
                discarded_suffix.extend(_string_list(latest.get("discarded_suffix")))
        if not discarded_suffix:
            return {}
        memory_id = "route_" + self._confirmation_id(
            self.node_id,
            state_version,
            self._history_hash(tactics),
        )
        created_at = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        discarded_pieces = _route_pieces(
            discarded_suffix,
            memory_id=memory_id,
            base_offset=kept_prefix_end,
        )
        episode = RepairEpisode(
            episode_id="repair_" + memory_id[-12:],
            node_id=self.node_id,
            created_at=created_at,
            from_checkpoint_id=checkpoint_id,
            from_tactic_index=int(tactic_index),
            kept_prefix_end=kept_prefix_end,
            rewind_note=normalized_rewind_note,
            discarded_pieces=discarded_pieces,
            route_memory_id=memory_id,
        )
        negative_memories = _negative_memories_from_rewind_note(
            normalized_rewind_note,
            memory_id=memory_id,
            episode_id=episode.episode_id,
            created_at=created_at,
        )
        stale_piece_ids = _stale_piece_ids(discarded_pieces)
        route_memory = RouteMemory(
            memory_id=memory_id,
            created_at=created_at,
            node_id=self.node_id,
            repair_episode_id=episode.episode_id,
            from_checkpoint_id=checkpoint_id,
            from_tactic_index=int(tactic_index),
            kept_prefix_end=kept_prefix_end,
            kept_prefix_hash=self._history_hash(tactics[:kept_prefix_end]),
            discarded_suffix=discarded_suffix,
            discarded_pieces=discarded_pieces,
            rewind_note=normalized_rewind_note,
            structural_chunks=_route_memory_structural_chunks(
                discarded_suffix,
                memory_id=memory_id,
            ),
            stale_piece_ids=stale_piece_ids,
            negative_memory_ids=[
                memory.memory_id for memory in negative_memories
            ],
        )
        self.repair_episodes = [episode, *self.repair_episodes[:9]]
        self.route_memories = [route_memory, *self.route_memories[:2]]
        self.negative_memories = [
            *negative_memories,
            *self.negative_memories[:9],
        ]
        self.write_route_replay_memory_file()
        return route_memory.to_dict()

    def lineage_briefing_surface(
        self,
        current_tactics: list[str],
    ) -> dict[str, Any]:
        if not (
            self.route_memories
            or self.repair_episodes
            or self.negative_memories
            or self.verified_route_options
        ):
            return {}
        route_items = [
            self._route_memory_lineage_brief(memory, current_tactics)
            for memory in self.route_memories[:3]
        ]
        route_items = [item for item in route_items if item]
        return _drop_empty({
            "kind": "lineage_briefing",
            "scope": "current_proof_node",
            "node_id": self.node_id,
            "current_tactic_count": len(current_tactics),
            "open_repair_episode": (
                _repair_episode_brief(self.repair_episodes[0])
                if self.repair_episodes else {}
            ),
            "recent_repairs": [
                _repair_episode_brief(episode)
                for episode in self.repair_episodes[:3]
            ],
            "route_memories": route_items,
            "negative_memories": [
                _negative_memory_brief(memory)
                for memory in self.negative_memories[:5]
            ],
            "verified_route_options": [
                _verified_route_option_brief(item)
                for item in self.verified_route_options[:5]
            ],
            "interpretation": (
                "Manager-owned continuity notes for this node. Use them as "
                "resume/navigation evidence; EasyCrypt replay still decides "
                "whether any old route piece is valid."
            ),
        })

    def route_replay_memory_surface(
        self,
        current_tactics: list[str],
    ) -> dict[str, Any]:
        items: list[dict[str, Any]] = []
        for route_memory in self.route_memories[:3]:
            memory = route_memory.to_dict()
            progress = self.route_memory_progress(memory, current_tactics)
            if not progress.get("prefix_matches"):
                continue
            chunks = self.eligible_replay_chunks(memory, current_tactics)
            if not chunks:
                continue
            items.append(_drop_empty({
                "memory_id": memory.get("memory_id"),
                "source": "discarded suffix saved before checkpoint rewind",
                "from_checkpoint_id": memory.get("from_checkpoint_id"),
                "kept_prefix_end": memory.get("kept_prefix_end"),
                "progress": progress,
                "available_chunks": [
                    replay_chunk_public_surface(chunk)
                    for chunk in chunks[:3]
                ],
                "interpretation": (
                    "These chunks are old committed tactics after a rewind. A "
                    "probe checks a chunk in a scratch verifier session before any "
                    "state-changing replay commit."
                ),
            }))
        if not items:
            return dict(self.legacy_route_replay_memory)
        return {
            "kind": "route_replay_memory",
            "state": "manager_owned_route_memory",
            "items": items,
            "repair_episodes": [
                _repair_episode_brief(episode)
                for episode in self.repair_episodes[:3]
            ],
        }

    def replay_suffix_chunk_selection_observation(
        self,
        *,
        intent: str,
        payload: dict[str, Any],
        current_tactics: list[str],
        notice: str = "",
    ) -> dict[str, Any]:
        return _drop_empty({
            "intent": intent,
            "payload": _dict_or_empty(payload),
            "kind": "replay_suffix_chunk_selection",
            "message": (
                "Choose a discarded route chunk to replay-check from the "
                "current proof state."
            ),
            "notice": notice,
            "route_replay_memory": self.route_replay_memory_surface(current_tactics),
        })

    def replay_suffix_probe_observation(
        self,
        *,
        intent: str,
        payload: dict[str, Any],
        chunk: dict[str, Any],
        result: dict[str, Any],
    ) -> dict[str, Any]:
        ok = bool(result.get("ok"))
        return _drop_empty({
            "intent": intent,
            "payload": _dict_or_empty(payload),
            "kind": "replay_suffix_probe",
            "message": (
                "The manager checked this discarded route chunk in a scratch "
                "EasyCrypt session. The committed proof state was not changed."
            ),
            "chunk": replay_chunk_public_surface(chunk),
            "status": "accepted" if ok else "stopped_at_first_failure",
            "accepted_tactic_count": _safe_int(result.get("accepted_count")),
            "failed_tactic": result.get("failed_tactic"),
            "failure_kind": result.get("failure_kind"),
            "error": result.get("error"),
        })

    def replay_suffix_commit_blocked_observation(
        self,
        *,
        intent: str,
        payload: dict[str, Any],
        chunk: dict[str, Any],
        result: dict[str, Any],
    ) -> dict[str, Any]:
        return _drop_empty({
            "intent": intent,
            "payload": _dict_or_empty(payload),
            "kind": "replay_suffix_commit_blocked",
            "message": (
                "The discarded route chunk did not replay cleanly from the "
                "current proof state. No committed proof state was changed."
            ),
            "chunk": replay_chunk_public_surface(chunk),
            "accepted_tactic_count": _safe_int(result.get("accepted_count")),
            "failed_tactic": result.get("failed_tactic"),
            "failure_kind": result.get("failure_kind"),
        })

    def replay_suffix_commit_observation(
        self,
        *,
        intent: str,
        payload: dict[str, Any],
        chunk: dict[str, Any],
    ) -> dict[str, Any]:
        return _drop_empty({
            "intent": intent,
            "payload": _dict_or_empty(payload),
            "kind": "replay_suffix_commit",
            "message": (
                "Committed the verifier-checked discarded route chunk and "
                "returned the refreshed proof state."
            ),
            "chunk": replay_chunk_public_surface(chunk),
            "committed_tactic_count": len(_string_list(chunk.get("tactics"))),
        })

    def route_memory_progress(
        self,
        memory: dict[str, Any],
        current_tactics: list[str],
    ) -> dict[str, Any]:
        kept_prefix_end = _safe_int(memory.get("kept_prefix_end"))
        if kept_prefix_end < 0:
            kept_prefix_end = 0
        kept_prefix = current_tactics[:kept_prefix_end]
        prefix_matches = (
            len(current_tactics) >= kept_prefix_end
            and self._history_hash(kept_prefix) == str(memory.get("kept_prefix_hash") or "")
        )
        if not prefix_matches:
            return {
                "prefix_matches": False,
                "state": "current_prefix_differs_from_saved_rewind_prefix",
            }
        old_suffix = _string_list(memory.get("discarded_suffix"))
        current_tail = current_tactics[kept_prefix_end:]
        old_cursor = 0
        current_cursor = 0
        rewrite_anchor: dict[str, Any] = {}
        if old_suffix and current_tail:
            if _same_tactic_for_replay(old_suffix[0], current_tail[0]):
                old_cursor = 1
                current_cursor = 1
            elif _same_replay_boundary_head(old_suffix[0], current_tail[0]):
                old_cursor = 1
                current_cursor = 1
                rewrite_anchor = {
                    "old_tactic": old_suffix[0],
                    "current_tactic": current_tail[0],
                    "relation": "same_structural_boundary_head_rewritten",
                }
        while (
            old_cursor < len(old_suffix)
            and current_cursor < len(current_tail)
            and _same_tactic_for_replay(old_suffix[old_cursor], current_tail[current_cursor])
        ):
            old_cursor += 1
            current_cursor += 1
        return _drop_empty({
            "prefix_matches": True,
            "covered_old_tactics": old_cursor,
            "covered_current_tail_tactics": current_cursor,
            "remaining_old_tactics": max(0, len(old_suffix) - old_cursor),
            "rewrite_anchor": rewrite_anchor,
        })

    def eligible_replay_chunks(
        self,
        memory: dict[str, Any],
        current_tactics: list[str],
    ) -> list[dict[str, Any]]:
        progress = self.route_memory_progress(memory, current_tactics)
        if not progress.get("prefix_matches"):
            return []
        start = _safe_int(progress.get("covered_old_tactics"))
        suffix = _string_list(memory.get("discarded_suffix"))
        if start >= len(suffix):
            return []
        return _route_memory_structural_chunks(
            suffix[start:],
            memory_id=str(memory.get("memory_id") or "route"),
            base_offset=start,
        )

    def resolve_replay_suffix_chunk(
        self,
        current_tactics: list[str],
        chunk_id: str,
    ) -> dict[str, Any]:
        wanted = str(chunk_id or "").strip()
        if not wanted:
            return {}
        for route_memory in self.route_memories:
            memory = route_memory.to_dict()
            for chunk in self.eligible_replay_chunks(memory, current_tactics):
                if str(chunk.get("chunk_id") or "") == wanted:
                    out = dict(chunk)
                    out["memory_id"] = memory.get("memory_id")
                    out["from_checkpoint_id"] = memory.get("from_checkpoint_id")
                    return out
        return {}

    def remember_verified_replay_chunk(
        self,
        *,
        current_tactics: list[str],
        chunk: dict[str, Any],
    ) -> None:
        """Remember that a replay chunk was scratch-verified at this prefix."""
        chunk_id = str(chunk.get("chunk_id") or "").strip()
        if not chunk_id:
            return
        self._verified_replay_chunks[chunk_id] = {
            "history_hash": self._history_hash(current_tactics),
            "tactics": _string_list(chunk.get("tactics")),
            "memory_id": chunk.get("memory_id"),
        }

    def replay_chunk_is_verified(
        self,
        *,
        current_tactics: list[str],
        chunk: dict[str, Any],
    ) -> bool:
        """Return whether a replay chunk was verified for this exact prefix."""
        chunk_id = str(chunk.get("chunk_id") or "").strip()
        if not chunk_id:
            return False
        verified = self._verified_replay_chunks.get(chunk_id)
        if not verified:
            return False
        return (
            verified.get("history_hash") == self._history_hash(current_tactics)
            and _string_list(verified.get("tactics")) == _string_list(chunk.get("tactics"))
        )

    def write_route_replay_memory_file(self) -> None:
        if self.run_dir is None or not self.route_memories:
            return
        try:
            path = self._route_replay_memory_file_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "schema_version": 2,
                "kind": "route_replay_memory",
                "node_id": self.node_id,
                "route_memory_snapshot": self.route_memory_snapshot().to_dict(),
                "repair_episodes": [
                    episode.to_dict() for episode in self.repair_episodes
                ],
                "route_memories": [
                    memory.to_dict() for memory in self.route_memories
                ],
                "negative_memories": [
                    memory.to_dict() for memory in self.negative_memories
                ],
                "verified_route_options": [
                    dict(item) for item in self.verified_route_options
                ],
            }
            path.write_text(
                json.dumps(payload, indent=2, sort_keys=True),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.warning("failed to write route replay memory: %s", exc)

    def _load_route_replay_memory_file(self) -> None:
        if self.run_dir is None:
            return
        path = self._route_replay_memory_file_path()
        if not path.exists():
            path = self._legacy_rewind_route_memory_file_path()
            if not path.exists():
                path = self._respawn_ancestor_route_memory_file_path()
            if path is None or not path.exists():
                return
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("failed to load route replay memory: %s", exc)
            return
        self._load_route_replay_memory_payload(payload)

    def _load_route_replay_memory_payload(self, payload: dict[str, Any]) -> None:
        payload = _dict_or_empty(payload)
        route_items = _dict_list(payload.get("route_memories"))
        if not route_items:
            route_items = _dict_list(payload.get("memories"))
        if route_items:
            self.route_memories = [
                RouteMemory.from_dict(item)
                for item in route_items
            ][:3]
        repair_items = _dict_list(payload.get("repair_episodes"))
        if repair_items:
            self.repair_episodes = [
                RepairEpisode.from_dict(item)
                for item in repair_items
            ][:10]
        negative_items = _dict_list(payload.get("negative_memories"))
        if not negative_items:
            tree = _dict_or_empty(payload.get("route_memory_snapshot"))
            negative_items = _dict_list(tree.get("negative_memories"))
        if negative_items:
            self.negative_memories = [
                NegativeMemory.from_dict(item)
                for item in negative_items
            ][:10]
        verified_options = [
            item for item in (
                _verified_route_option_entry(option)
                for option in _dict_list(payload.get("verified_route_options"))
            )
            if item
        ]
        if verified_options:
            self.seed_verified_route_options(verified_options)
        legacy = _legacy_route_replay_surface_from_payload(payload)
        if legacy and not self.route_memories:
            self.legacy_route_replay_memory = legacy

    def _route_replay_memory_file_path(self) -> Path:
        node_slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", self.node_id)
        root = self.run_dir if self.run_dir is not None else Path(".")
        return root / "route_memory" / f"{node_slug}_route_replay_memory.json"

    def _legacy_rewind_route_memory_file_path(self) -> Path:
        node_slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", self.node_id)
        root = self.run_dir if self.run_dir is not None else Path(".")
        return root / "route_memory" / f"{node_slug}_rewind_route_memory.json"

    def _respawn_ancestor_route_memory_file_path(self) -> Path | None:
        """The nearest respawn ancestor's route-memory file, or None.

        Layer-3 crash-respawn children are named ``<parent>.r<N>`` but the
        dead parent's route memory file stays keyed to the PARENT slug
        (e.g. ``Tree-0.0_route_replay_memory.json`` while the child is
        ``Tree-0.0.r0``). Resume-capsule seeding is the primary handoff path;
        this read-side fallback covers capsules minted without the payload so
        the child still sees the verifier-checked chunks instead of
        re-deriving them. Stale-prefix safety is unchanged: every surface is
        gated on ``kept_prefix_hash`` matching the current history.
        """
        if self.run_dir is None:
            return None
        node_id = str(self.node_id or "")
        while True:
            stripped = re.sub(r"\.r\d+$", "", node_id)
            if stripped == node_id or not stripped:
                return None
            node_id = stripped
            node_slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", node_id)
            for name in (
                f"{node_slug}_route_replay_memory.json",
                f"{node_slug}_rewind_route_memory.json",
            ):
                path = self.run_dir / "route_memory" / name
                if path.exists():
                    return path

    def _route_memory_lineage_brief(
        self,
        memory: RouteMemory,
        current_tactics: list[str],
    ) -> dict[str, Any]:
        memory_dict = memory.to_dict()
        progress = self.route_memory_progress(memory_dict, current_tactics)
        chunks = self.eligible_replay_chunks(memory_dict, current_tactics)
        return _drop_empty({
            "memory_id": memory.memory_id,
            "repair_episode_id": memory.repair_episode_id,
            "from_checkpoint_id": memory.from_checkpoint_id,
            "from_tactic_index": memory.from_tactic_index,
            "kept_prefix_end": memory.kept_prefix_end,
            "discarded_tactic_count": len(memory.discarded_suffix),
            "progress": {
                key: progress.get(key)
                for key in (
                    "prefix_matches",
                    "covered_old_tactics",
                    "remaining_old_tactics",
                    "rewrite_anchor",
                )
                if progress.get(key) not in (None, "", [], {})
            },
            "piece_counts": _piece_counts(memory.discarded_pieces),
            "stale_piece_count": len(memory.stale_piece_ids),
            "replayable_chunk_count": len(chunks),
            "rewind_note": rewind_note_summary(memory.rewind_note),
            "negative_memory_ids": list(memory.negative_memory_ids),
        })


def _legacy_route_replay_surface_from_payload(
    payload: dict[str, Any],
) -> dict[str, Any]:
    payload = _dict_or_empty(payload)
    surface = payload.get("legacy_route_replay_memory")
    if not isinstance(surface, dict):
        surface = payload.get("route_replay_memory")
    if not isinstance(surface, dict):
        surface = payload.get("rewind_route_memory")
    return _legacy_route_replay_surface(surface)


def _legacy_route_replay_surface_from_view(
    view: dict[str, Any],
) -> dict[str, Any]:
    view = _dict_or_empty(view)
    surface = view.get("route_replay_memory")
    if not isinstance(surface, dict):
        surface = view.get("rewind_route_memory")
    return _legacy_route_replay_surface(surface)


def _legacy_route_replay_surface(surface: Any) -> dict[str, Any]:
    if not isinstance(surface, dict):
        return {}
    items: list[dict[str, Any]] = []
    for item in _dict_list(surface.get("items"))[:3]:
        clean = dict(item)
        chunks: list[dict[str, Any]] = []
        for chunk in _dict_list(clean.get("available_chunks"))[:3]:
            chunk_out = dict(chunk)
            if not _string_list(chunk_out.get("tactics")):
                chunk_out.pop("submit_commit", None)
                chunk_out.pop("submit_probe", None)
                chunk_out["limitations"] = (
                    str(chunk_out.get("limitations") or "").strip()
                    + (
                        " Legacy resume capsule did not include the full "
                        "chunk tactic payload, so this item is navigation "
                        "evidence only."
                    )
                ).strip()
            chunks.append(_drop_empty(chunk_out))
        clean["available_chunks"] = chunks
        items.append(_drop_empty(clean))
    if not items:
        return {}
    return _drop_empty({
        "kind": "route_replay_memory",
        "state": "legacy_resume_route_memory",
        "items": items,
        "interpretation": (
            "This route memory was recovered from a legacy resume view. Use it "
            "as continuity evidence; chunks without tactic payload are not "
            "directly replayable until regenerated by a manager-owned rewind."
        ),
    })


def _verified_route_option_entry(value: dict[str, Any]) -> dict[str, Any]:
    value = _dict_or_empty(value)
    if (
        value.get("kind") != "verified_route_option"
        or value.get("confidence") != "verified"
    ):
        return {}
    submit = _dict_or_empty(value.get("submit"))
    payload = _dict_or_empty(submit.get("payload"))
    tactic = str(payload.get("tactic") or "").strip()
    if submit.get("intent") != "commit_tactic" or not tactic:
        return {}
    return _drop_empty({
        "kind": "verified_route_option",
        "schema_version": _safe_int(value.get("schema_version")) or 1,
        "option_id": str(value.get("option_id") or ""),
        "topic": str(value.get("topic") or ""),
        "mode": str(value.get("mode") or ""),
        "producer": str(value.get("producer") or ""),
        "semantic_objective": str(value.get("semantic_objective") or ""),
        "confidence": "verified",
        "submit": {
            "intent": "commit_tactic",
            "payload": {"tactic": tactic},
        },
        "tactic_chain": _string_list(value.get("tactic_chain")) or [tactic],
        "bindings": _dict_or_empty(value.get("bindings")),
        "preconditions": _string_list(value.get("preconditions")),
        "source_refs": _dict_list(value.get("source_refs"))[:5],
        "evidence_refs": _string_list(value.get("evidence_refs")),
        "verification_evidence": _dict_list(
            value.get("verification_evidence")
        )[:5],
        "context_evidence": _dict_list(value.get("context_evidence"))[:3],
        "metadata": _dict_or_empty(value.get("metadata")),
    })


def _verified_route_option_brief(value: dict[str, Any]) -> dict[str, Any]:
    value = _verified_route_option_entry(value)
    if not value:
        return {}
    submit = _dict_or_empty(value.get("submit"))
    payload = _dict_or_empty(submit.get("payload"))
    return _drop_empty({
        "option_id": value.get("option_id"),
        "topic": value.get("topic"),
        "producer": value.get("producer"),
        "semantic_objective": value.get("semantic_objective"),
        "tactic_head": _tactic_head(str(payload.get("tactic") or "")),
        "bindings": value.get("bindings"),
    })


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]



def _rewind_note_dict(value: Any) -> dict[str, Any]:
    return normalize_rewind_note(value).to_dict()


def _dict_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _route_pieces(
    tactics: list[str],
    *,
    memory_id: str,
    base_offset: int,
) -> list[RoutePiece]:
    pieces: list[RoutePiece] = []
    for idx, tactic in enumerate(tactics):
        clean = str(tactic).strip()
        if not clean:
            continue
        offset = int(base_offset) + idx
        pieces.append(RoutePiece(
            piece_id=f"piece_{memory_id[-8:]}_{offset}",
            tactic=clean,
            offset=offset,
            replay_class=_replay_class(clean),
            goal_tag=_goal_tag(clean),
        ))
    return pieces


def _stale_piece_ids(pieces: list[RoutePiece]) -> list[str]:
    if not pieces:
        return []
    first = pieces[0]
    if first.replay_class == "boundary_sensitive":
        return [first.piece_id]
    return []


def _negative_memories_from_rewind_note(
    rewind_note: dict[str, Any],
    *,
    memory_id: str,
    episode_id: str,
    created_at: str,
) -> list[NegativeMemory]:
    rewind_note = _rewind_note_dict(rewind_note)
    entries: list[Any] = []
    for key in (
        "negative_memory",
        "negative_memories",
        "avoid_patterns",
        "avoid",
        "do_not",
    ):
        value = rewind_note.get(key)
        if isinstance(value, list):
            entries.extend(value)
        elif value not in (None, "", {}, []):
            entries.append(value)
    memories: list[NegativeMemory] = []
    for idx, entry in enumerate(entries):
        surface = _negative_memory_entry(entry)
        avoid_pattern = str(surface.get("avoid_pattern") or "").strip()
        reason = str(surface.get("reason") or "").strip()
        if not avoid_pattern and not reason:
            continue
        memories.append(NegativeMemory(
            memory_id=f"neg_{memory_id[-8:]}_{idx}",
            created_at=created_at,
            source_episode_id=episode_id,
            source_route_memory_id=memory_id,
            kind=str(surface.get("kind") or "avoid_pattern"),
            scope=str(surface.get("scope") or ""),
            avoid_pattern=avoid_pattern,
            reason=reason,
            applies_when=str(surface.get("applies_when") or ""),
            evidence=_dict_or_empty(surface.get("evidence")),
        ))
    return memories


def _negative_memory_entry(entry: Any) -> dict[str, Any]:
    if isinstance(entry, dict):
        out = dict(entry)
        if "avoid_pattern" not in out:
            for key in ("pattern", "avoid", "do_not"):
                if key in out:
                    out["avoid_pattern"] = out.get(key)
                    break
        return out
    text = str(entry or "").strip()
    if not text:
        return {}
    return {
        "avoid_pattern": text,
        "reason": "recorded by rewind_note",
    }


def _piece_counts(pieces: list[RoutePiece]) -> dict[str, Any]:
    by_class: dict[str, int] = {}
    by_goal_tag: dict[str, int] = {}
    for piece in pieces:
        by_class[piece.replay_class] = by_class.get(piece.replay_class, 0) + 1
        if piece.goal_tag:
            by_goal_tag[piece.goal_tag] = by_goal_tag.get(piece.goal_tag, 0) + 1
    return _drop_empty({
        "total": len(pieces),
        "by_replay_class": by_class,
        "by_goal_tag": by_goal_tag,
    })


def _repair_episode_brief(episode: RepairEpisode) -> dict[str, Any]:
    return _drop_empty({
        "episode_id": episode.episode_id,
        "from_checkpoint_id": episode.from_checkpoint_id,
        "from_tactic_index": episode.from_tactic_index,
        "kept_prefix_end": episode.kept_prefix_end,
        "discarded_piece_count": len(episode.discarded_pieces),
        "piece_counts": _piece_counts(episode.discarded_pieces),
        "rewind_note": rewind_note_summary(episode.rewind_note),
        "route_memory_id": episode.route_memory_id,
    })


def _negative_memory_brief(memory: NegativeMemory) -> dict[str, Any]:
    return _drop_empty({
        "memory_id": memory.memory_id,
        "kind": memory.kind,
        "scope": memory.scope,
        "avoid_pattern": memory.avoid_pattern,
        "reason": memory.reason,
        "applies_when": memory.applies_when,
        "source_episode_id": memory.source_episode_id,
        "source_route_memory_id": memory.source_route_memory_id,
    })


def _replay_class(tactic: str) -> str:
    head = tactic.strip().split(None, 1)[0].rstrip(".:;") if tactic.strip() else ""
    if head in {"seq", "call", "while", "if", "conseq"}:
        return "boundary_sensitive"
    if head in {"inline", "sp", "wp", "swap", "rcondt", "rcondf", "rnd"}:
        return "structural_replayable"
    return "local_logic"


def _goal_tag(tactic: str) -> str:
    head = tactic.strip().split(None, 1)[0].rstrip(".:;") if tactic.strip() else ""
    if head in {"seq", "call", "while", "if"}:
        return f"{head}_boundary"
    if head in {"wp", "sp", "swap", "inline"}:
        return "program_frontier"
    if head in {"smt", "auto", "done", "trivial"}:
        return "closing_tail"
    return "proof_step"


def _route_memory_structural_chunks(
    discarded_suffix: list[str],
    *,
    memory_id: str,
    base_offset: int = 0,
) -> list[dict[str, Any]]:
    tactics = [str(tactic).strip() for tactic in discarded_suffix if str(tactic).strip()]
    chunks: list[dict[str, Any]] = []
    current: list[str] = []
    current_start = int(base_offset)
    max_chunk_size = 6

    def flush() -> None:
        nonlocal current, current_start
        if not current:
            return
        end_offset = current_start + len(current)
        digest = _chunk_digest(current)
        chunks.append(_drop_empty({
            "chunk_id": f"rch_{memory_id[-8:]}_{current_start}_{end_offset}_{digest}",
            "memory_id": memory_id,
            "start_offset": current_start,
            "end_offset": end_offset,
            "kind": _route_memory_chunk_kind(current),
            "tactic_count": len(current),
            "first_tactic": current[0],
            "last_tactic": current[-1],
            "tactics": list(current),
        }))
        current = []
        current_start = end_offset

    for offset, tactic in enumerate(tactics, start=int(base_offset)):
        if current and (
            len(current) >= max_chunk_size
            or _starts_route_memory_boundary(tactic)
        ):
            flush()
            current_start = offset
        if not current:
            current_start = offset
        current.append(tactic)
    flush()
    return chunks


def replay_chunk_public_surface(chunk: dict[str, Any]) -> dict[str, Any]:
    chunk_id = str(chunk.get("chunk_id") or "").strip()
    submit_payload = {"chunk_id": chunk_id} if chunk_id else {}
    return _drop_empty({
        "chunk_id": chunk_id,
        "memory_id": chunk.get("memory_id"),
        "kind": chunk.get("kind"),
        "tactic_count": chunk.get("tactic_count"),
        "first_tactic": chunk.get("first_tactic"),
        "last_tactic": chunk.get("last_tactic"),
        "effect": (
            "Scratch replay checks this old route chunk from the current "
            "committed proof state."
        ),
        "limitations": (
            "A changed invariant or branch shape can make only a prefix of the "
            "old chunk replayable."
        ),
        "submit_probe": {
            "intent": "probe_replay_suffix_chunk",
            "payload": submit_payload,
        },
        "submit_commit": {
            "intent": "commit_replay_suffix_chunk",
            "payload": submit_payload,
        },
    })


def _route_memory_chunk_kind(tactics: list[str]) -> str:
    heads = [_tactic_head(tactic) for tactic in tactics if _tactic_head(tactic)]
    if not heads:
        return "local_route_suffix"
    for head in heads:
        if head in {"seq", "call", "while", "if", "conseq"}:
            return f"{head}_route_suffix"
    if all(head in {"wp", "sp", "swap", "rcondt", "rcondf", "rnd"} for head in heads):
        return "frontier_surgery_suffix"
    return "local_route_suffix"


def _starts_route_memory_boundary(tactic: str) -> bool:
    head = _tactic_head(tactic)
    if head in {"seq", "call", "while", "if", "conseq"}:
        return True
    text = tactic.strip().lower()
    return "call (_:" in text or text.startswith("inline")


def _same_tactic_for_replay(left: str, right: str) -> bool:
    return normalize_tactic_for_transition(left) == normalize_tactic_for_transition(right)


def _same_replay_boundary_head(left: str, right: str) -> bool:
    left_head = _tactic_head(left)
    right_head = _tactic_head(right)
    if not left_head or left_head != right_head:
        return False
    return left_head in {"seq", "call", "while", "if", "conseq"}


def _chunk_digest(tactics: list[str]) -> str:
    import hashlib

    return hashlib.sha1("\n".join(tactics).encode("utf-8")).hexdigest()[:8]

