"""Run-level proof lineage store.

This is the durable graph hook for orchestrator/node cooperation.  The current
implementation is intentionally small and append-only so resume can start
reading lineage before winner scoring is migrated.
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from workflow.proof_management.repair_notes import rewind_note_summary
from workflow.proof_management.route_family import (
    RouteFamilyEvidence,
    infer_route_family,
)
from core.easycrypt.value_shapes import as_dict_copy as _dict_or_empty
from core.easycrypt.value_shapes import drop_empty as _drop_empty


logger = logging.getLogger(__name__)


class LemmaLineageStore:
    """Append-only lineage events for one lemma/run directory."""

    def __init__(self, *, run_dir: Path | None = None) -> None:
        self.run_dir = Path(run_dir) if run_dir is not None else None

    def record_node_bootstrap(
        self,
        *,
        node_id: str,
        session_tag: str,
        session_dir: str,
        replay_prefix_count: int,
    ) -> None:
        self.append({
            "kind": "node_bootstrapped",
            "node": node_id,
            "session_tag": session_tag,
            "session_dir": session_dir,
            "replay_prefix_count": int(replay_prefix_count),
        })

    def record_tree_run_started(
        self,
        *,
        cwd: str,
        timeout: int,
        max_concurrent: int,
        initial_provers: int,
        resume_roots: int = 0,
        resume_root_policy: str = "score",
    ) -> None:
        self.append({
            "kind": "tree_run_started",
            "cwd": cwd,
            "timeout": int(timeout),
            "max_concurrent": int(max_concurrent),
            "initial_provers": int(initial_provers),
            "resume_roots": int(resume_roots),
            "resume_root_policy": resume_root_policy,
        })

    def record_node_spawned(
        self,
        *,
        node_id: str,
        parent_id: str | None,
        depth: int,
        replay_prefix: list[str] | None = None,
        strategy_index: int = 0,
        spawn_reason: str = "",
        route_family: dict[str, Any] | RouteFamilyEvidence | None = None,
        failed_at_branch: list[str] | None = None,
        layer_move_action: dict[str, Any] | None = None,
        expected_resume_goal_hash: str = "",
    ) -> None:
        tactics = [str(item) for item in list(replay_prefix or [])]
        family = _route_family_dict(route_family) or infer_route_family(
            tactics,
        ).to_dict()
        self.append({
            "kind": "node_spawned",
            "node": node_id,
            "parent": parent_id or "",
            "depth": int(depth),
            "replay_prefix_count": len(tactics),
            "strategy_index": int(strategy_index),
            "spawn_reason": spawn_reason,
            "route_family": family,
            "failed_at_branch": _string_list(failed_at_branch),
            "layer_move_action": _dict_or_empty(layer_move_action),
            "expected_resume_goal_hash": expected_resume_goal_hash,
        })

    def record_resume_root_chosen(
        self,
        *,
        node_id: str,
        capsule_path: str = "",
        capsule_score: float = 0.0,
        tactic_count: int = 0,
        route_family: dict[str, Any] | RouteFamilyEvidence | None = None,
        resume_diversity: dict[str, Any] | None = None,
        resume_root_policy: str = "score",
    ) -> None:
        self.append({
            "kind": "resume_root_chosen",
            "node": node_id,
            "capsule_path": capsule_path,
            "capsule_score": float(capsule_score or 0.0),
            "tactic_count": int(tactic_count or 0),
            "route_family": _route_family_dict(route_family),
            "resume_diversity": _dict_or_empty(resume_diversity),
            "resume_root_policy": resume_root_policy,
        })

    def record_route_family_assigned(
        self,
        *,
        node_id: str,
        route_family: dict[str, Any] | RouteFamilyEvidence,
        tactic_count: int,
        reason: str = "",
    ) -> None:
        family = _route_family_dict(route_family)
        if not family:
            return
        self.append({
            "kind": "route_family_assigned",
            "node": node_id,
            "route_family": family,
            "tactic_count": int(tactic_count),
            "reason": reason,
        })

    def record_repair_branch_created(
        self,
        *,
        parent_id: str,
        child_id: str,
        reason: str,
        prefix_count: int,
        failed_suffix: list[str] | None = None,
        layer_move_action: dict[str, Any] | None = None,
    ) -> None:
        self.append({
            "kind": "repair_branch_created",
            "parent": parent_id,
            "child": child_id,
            "reason": reason,
            "prefix_count": int(prefix_count),
            "failed_suffix": _string_list(failed_suffix),
            "layer_move_action": _dict_or_empty(layer_move_action),
        })

    def record_node_killed(
        self,
        *,
        node_id: str,
        reason: str,
        committed_count: int = 0,
        max_committed_count_seen: int = 0,
        route_family: dict[str, Any] | RouteFamilyEvidence | None = None,
    ) -> None:
        self.append({
            "kind": "node_killed",
            "node": node_id,
            "reason": reason,
            "committed_count": int(committed_count),
            "max_committed_count_seen": int(max_committed_count_seen),
            "route_family": _route_family_dict(route_family),
        })

    def record_winner_selected(
        self,
        *,
        node_id: str,
        proved: bool,
        returncode: int,
        committed_count: int = 0,
        max_committed_count_seen: int = 0,
        route_family: dict[str, Any] | RouteFamilyEvidence | None = None,
        selection_reason: str = "",
        shadow_selection: dict[str, Any] | None = None,
    ) -> None:
        self.append({
            "kind": "winner_selected",
            "node": node_id,
            "proved": bool(proved),
            "returncode": int(returncode),
            "committed_count": int(committed_count),
            "max_committed_count_seen": int(max_committed_count_seen),
            "route_family": _route_family_dict(route_family),
            "selection_reason": selection_reason,
            "shadow_selection": _dict_or_empty(shadow_selection),
        })

    def record_tree_run_finished(
        self,
        *,
        winner_node_id: str,
        total_spawned: int,
        max_depth: int,
        proved: bool,
        returncode: int,
    ) -> None:
        self.append({
            "kind": "tree_run_finished",
            "winner": winner_node_id,
            "total_spawned": int(total_spawned),
            "max_depth": int(max_depth),
            "proved": bool(proved),
            "returncode": int(returncode),
        })
        self.write_briefing()

    def record_repair_episode(
        self,
        *,
        node_id: str,
        memory: dict[str, Any],
    ) -> None:
        if not memory:
            return
        event = {
            "kind": "repair_episode_recorded",
            "node": node_id,
            "memory_id": memory.get("memory_id"),
            "repair_episode_id": memory.get("repair_episode_id"),
            "from_checkpoint_id": memory.get("from_checkpoint_id"),
            "from_tactic_index": memory.get("from_tactic_index"),
            **_repair_memory_summary(memory),
        }
        note_summary = rewind_note_summary(memory.get("rewind_note"))
        if note_summary:
            event["rewind_note"] = note_summary
        self.append(event)

    def record_proof_turn(
        self,
        *,
        node_id: str,
        route_event: dict[str, Any],
    ) -> None:
        if not route_event:
            return
        self.append({
            "kind": "proof_turn_recorded",
            "node": node_id,
            "intent": route_event.get("intent"),
            "turn_index": route_event.get("turn_index"),
            "accepted": route_event.get("accepted"),
            "changed": route_event.get("changed"),
            "tactic": route_event.get("tactic"),
        })

    def append(self, event: dict[str, Any]) -> None:
        if self.run_dir is None:
            return
        payload = {
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            **dict(event),
        }
        try:
            self.run_dir.mkdir(parents=True, exist_ok=True)
            path = self.run_dir / "lemma_lineage.jsonl"
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, sort_keys=True) + "\n")
        except Exception as exc:
            logger.warning("failed to write lemma lineage event: %s", exc)

    def read_events(self, *, limit: int | None = None) -> list[dict[str, Any]]:
        if self.run_dir is None:
            return []
        path = self.run_dir / "lemma_lineage.jsonl"
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except Exception:
            return []
        if limit is not None:
            lines = lines[-max(1, int(limit)) :]
        events: list[dict[str, Any]] = []
        for line in lines:
            try:
                item = json.loads(line)
            except Exception:
                continue
            if isinstance(item, dict):
                events.append(item)
        return events

    def lineage_briefing(self) -> dict[str, Any]:
        return lineage_briefing_from_events(self.read_events())

    def write_briefing(self) -> None:
        if self.run_dir is None:
            return
        briefing = self.lineage_briefing()
        try:
            self.run_dir.mkdir(parents=True, exist_ok=True)
            json_path = self.run_dir / "lemma_lineage_briefing.json"
            json_path.write_text(
                json.dumps(briefing, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            md_path = self.run_dir / "lemma_lineage_briefing.md"
            md_path.write_text(
                lineage_briefing_markdown(briefing),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.warning("failed to write lemma lineage briefing: %s", exc)


def lineage_briefing_from_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    node_ids: set[str] = set()
    family_counts: dict[str, int] = {}
    latest_family_by_node: dict[str, dict[str, Any]] = {}
    kills: list[dict[str, Any]] = []
    repairs: list[dict[str, Any]] = []
    spawned: list[dict[str, Any]] = []
    winner: dict[str, Any] = {}

    for event in events:
        kind = str(event.get("kind") or "")
        node = str(event.get("node") or "")
        if node:
            node_ids.add(node)
        if kind == "node_spawned":
            spawned.append(event)
            family = _route_family_dict(event.get("route_family"))
            if family:
                latest_family_by_node[node] = family
        elif kind == "route_family_assigned":
            family = _route_family_dict(event.get("route_family"))
            if node and family:
                latest_family_by_node[node] = family
        elif kind == "node_killed":
            kills.append(event)
        elif kind == "repair_episode_recorded":
            repairs.append(event)
        elif kind == "winner_selected":
            winner = event

    for family in latest_family_by_node.values():
        name = str(family.get("family") or "unknown")
        family_counts[name] = family_counts.get(name, 0) + 1

    return _drop_empty({
        "kind": "lemma_lineage_briefing",
        "node_count": len(node_ids),
        "spawned_count": len(spawned),
        "killed_count": len(kills),
        "repair_episode_count": len(repairs),
        "route_family_counts": family_counts,
        "winner": _winner_brief(winner),
        "recent_repairs": [_repair_event_brief(item) for item in repairs[-5:]],
        "recent_kills": [_kill_event_brief(item) for item in kills[-5:]],
        "nodes": [
            _drop_empty({
                "node": node,
                "route_family": latest_family_by_node.get(node, {}),
            })
            for node in sorted(node_ids)
        ],
        "interpretation": (
            "Shadow-mode proof lineage. This records route diversity and "
            "repair history without changing prover scheduling decisions."
        ),
    })


def lineage_briefing_markdown(briefing: dict[str, Any]) -> str:
    lines = ["# Lemma Lineage Briefing", ""]
    lines.append(f"- nodes: {briefing.get('node_count', 0)}")
    lines.append(f"- spawned: {briefing.get('spawned_count', 0)}")
    lines.append(f"- killed: {briefing.get('killed_count', 0)}")
    lines.append(f"- repairs: {briefing.get('repair_episode_count', 0)}")
    route_counts = _dict_or_empty(briefing.get("route_family_counts"))
    if route_counts:
        lines.append("- route families:")
        for name, count in sorted(route_counts.items()):
            lines.append(f"  - {name}: {count}")
    winner = _dict_or_empty(briefing.get("winner"))
    if winner:
        lines.append("")
        lines.append("## Winner")
        lines.append(f"- node: {winner.get('node', '')}")
        lines.append(f"- proved: {winner.get('proved', False)}")
        family = _dict_or_empty(winner.get("route_family"))
        if family:
            lines.append(f"- route_family: {family.get('family', 'unknown')}")
        shadow = _dict_or_empty(winner.get("shadow_selection"))
        if shadow:
            lines.append(
                "- shadow_selection: "
                + str(shadow.get("mode") or "shadow")
                + ", "
                + str(shadow.get("current_policy") or "current policy")
            )
    repairs = [
        item for item in list(briefing.get("recent_repairs") or [])
        if isinstance(item, dict)
    ]
    if repairs:
        lines.append("")
        lines.append("## Recent Repairs")
        for item in repairs:
            note = _dict_or_empty(item.get("rewind_note"))
            lines.append(
                "- "
                + str(item.get("node") or "")
                + (
                    f": {note.get('hypothesis')}"
                    if note.get("hypothesis") else ""
                )
            )
    lines.append("")
    lines.append(str(briefing.get("interpretation") or ""))
    lines.append("")
    return "\n".join(lines)


def _repair_memory_summary(memory: dict[str, Any]) -> dict[str, Any]:
    pieces = _dict_list(memory.get("discarded_pieces"))
    replay_class_counts: dict[str, int] = {}
    goal_tag_counts: dict[str, int] = {}
    for piece in pieces:
        replay_class = str(piece.get("replay_class") or "").strip()
        if replay_class:
            replay_class_counts[replay_class] = (
                replay_class_counts.get(replay_class, 0) + 1
            )
        goal_tag = str(piece.get("goal_tag") or "").strip()
        if goal_tag:
            goal_tag_counts[goal_tag] = goal_tag_counts.get(goal_tag, 0) + 1

    negative_ids = _string_list(memory.get("negative_memory_ids"))
    note_summary = rewind_note_summary(memory.get("rewind_note"))
    negative_count = max(
        len(negative_ids),
        int(note_summary.get("negative_memory_count") or 0),
    )
    return _drop_empty({
        "kept_prefix_end": memory.get("kept_prefix_end"),
        "discarded_tactic_count": len(_string_list(memory.get("discarded_suffix"))),
        "discarded_piece_count": len(pieces),
        "replay_class_counts": replay_class_counts,
        "goal_tag_counts": goal_tag_counts,
        "stale_piece_count": len(_string_list(memory.get("stale_piece_ids"))),
        "negative_memory_count": negative_count,
        "candidate_replay_chunk_count": len(
            _dict_list(memory.get("structural_chunks"))
        ),
    })


def _winner_brief(event: dict[str, Any]) -> dict[str, Any]:
    if not event:
        return {}
    return _drop_empty({
        "node": event.get("node"),
        "proved": event.get("proved"),
        "returncode": event.get("returncode"),
        "committed_count": event.get("committed_count"),
        "max_committed_count_seen": event.get("max_committed_count_seen"),
        "route_family": _route_family_dict(event.get("route_family")),
        "selection_reason": event.get("selection_reason"),
        "shadow_selection": _dict_or_empty(event.get("shadow_selection")),
    })


def _repair_event_brief(event: dict[str, Any]) -> dict[str, Any]:
    return _drop_empty({
        "node": event.get("node"),
        "memory_id": event.get("memory_id"),
        "repair_episode_id": event.get("repair_episode_id"),
        "from_checkpoint_id": event.get("from_checkpoint_id"),
        "from_tactic_index": event.get("from_tactic_index"),
        "discarded_piece_count": event.get("discarded_piece_count"),
        "rewind_note": rewind_note_summary(event.get("rewind_note")),
    })


def _kill_event_brief(event: dict[str, Any]) -> dict[str, Any]:
    return _drop_empty({
        "node": event.get("node"),
        "reason": event.get("reason"),
        "committed_count": event.get("committed_count"),
        "max_committed_count_seen": event.get("max_committed_count_seen"),
        "route_family": _route_family_dict(event.get("route_family")),
    })


def _route_family_dict(
    value: dict[str, Any] | RouteFamilyEvidence | Any,
) -> dict[str, Any]:
    if isinstance(value, RouteFamilyEvidence):
        return value.to_dict()
    if not isinstance(value, dict):
        return {}
    family = str(value.get("family") or "").strip()
    if not family:
        return {}
    return _drop_empty({
        "family": family,
        "confidence": str(value.get("confidence") or "").strip(),
        "evidence": _string_list(value.get("evidence")),
    })


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]



def _dict_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


