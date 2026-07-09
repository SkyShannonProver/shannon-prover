"""Render analyzer evidence into a ProverWorkspaceView-compatible dict."""
from __future__ import annotations

from typing import Any

from .evidence import EvidenceBundle
from .node_state import ProofNodeState
from core.easycrypt.value_shapes import drop_empty as _drop_empty


class ProofViewRenderer:
    """Small rendering adapter for evidence-owned panels."""

    def render(
        self,
        base_view: dict[str, Any],
        *,
        state: ProofNodeState,
        evidence: EvidenceBundle,
    ) -> dict[str, Any]:
        view = dict(base_view)
        if evidence.route_health:
            candidate_moves = dict(
                view.get("candidate_moves")
                if isinstance(view.get("candidate_moves"), dict) else {}
            )
            candidate_moves["route_health"] = [
                dict(item) for item in evidence.route_health
            ][:2]
            view["candidate_moves"] = _drop_empty(candidate_moves)
        if evidence.structural_transitions:
            candidate_moves = dict(
                view.get("candidate_moves")
                if isinstance(view.get("candidate_moves"), dict) else {}
            )
            candidate_moves["structural_transitions"] = [
                dict(item) for item in evidence.structural_transitions[:3]
            ]
            view["candidate_moves"] = _drop_empty(candidate_moves)
        for panel, payload in evidence.l4_panels.items():
            if payload:
                view[panel] = dict(payload)
        for panel in evidence.removed_panels:
            view.pop(panel, None)
        for key, payload in evidence.view_overrides.items():
            if payload in (None, {}, []):
                view.pop(key, None)
            elif isinstance(payload, dict):
                view[key] = dict(payload)
            elif isinstance(payload, list):
                view[key] = list(payload)
            else:
                view[key] = payload
        if (
            evidence.checkpoint_index.structural_items
            or evidence.checkpoint_index.restore_option is not None
        ):
            view = _with_checkpoint_index(view, evidence)
        if evidence.route_replay_memory:
            view = _with_route_memory(view, evidence)
        if evidence.lineage_briefing:
            view["lineage_briefing"] = dict(evidence.lineage_briefing)
        return view


def _with_checkpoint_index(
    view: dict[str, Any],
    evidence: EvidenceBundle,
) -> dict[str, Any]:
    out = dict(view)
    structural = dict(
        out.get("structural_checkpoints")
        if isinstance(out.get("structural_checkpoints"), dict) else {}
    )
    existing = [
        item for item in structural.get("items", [])
        if isinstance(item, dict)
    ]
    authoritative = [
        item.to_dict()
        for item in evidence.checkpoint_index.structural_items
    ]
    if authoritative:
        existing = _non_duplicate_existing_checkpoints(existing, authoritative)
        items = [*authoritative, *existing]
    else:
        items = existing
    option = evidence.checkpoint_index.restore_option
    if option is not None:
        restore = option.to_dict()
        restore_id = _restore_id(restore)
        items = [
            restore,
            *[
                item for item in items
                if not _same_restore_option(item, restore_id)
            ],
        ]
    structural["items"] = items
    out["structural_checkpoints"] = structural
    return out


def _with_route_memory(
    view: dict[str, Any],
    evidence: EvidenceBundle,
) -> dict[str, Any]:
    out = dict(view)
    replay = _route_replay_memory(evidence)
    if replay:
        out["route_replay_memory"] = replay
    out.pop("rewind_route_memory", None)
    return out


def _route_replay_memory(evidence: EvidenceBundle) -> dict[str, Any]:
    if not evidence.route_replay_memory:
        return {}
    replay = dict(evidence.route_replay_memory)
    replay["kind"] = "route_replay_memory"
    replay.setdefault("state", "manager_owned_route_memory")
    if evidence.repair_episodes and "repair_episodes" not in replay:
        replay["repair_episodes"] = [
            dict(item)
            for item in evidence.repair_episodes
            if isinstance(item, dict)
        ]
    return _drop_empty(replay)


def _same_restore_option(item: dict[str, Any], restore_id: str) -> bool:
    if not restore_id:
        return False
    return _restore_id(item) == restore_id


def _non_duplicate_existing_checkpoints(
    existing: list[dict[str, Any]],
    authoritative: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    known = {
        _checkpoint_key(item)
        for item in authoritative
        if _checkpoint_key(item)
    }
    return [
        item for item in existing
        if not _checkpoint_key(item) or _checkpoint_key(item) not in known
    ]


def _checkpoint_key(item: dict[str, Any]) -> str:
    checkpoint_id = str(item.get("checkpoint_id") or "")
    if checkpoint_id:
        return "checkpoint:" + checkpoint_id
    semantic_id = str(item.get("semantic_id") or "")
    if semantic_id:
        return "semantic:" + semantic_id
    semantic_ids = item.get("semantic_ids")
    if isinstance(semantic_ids, list) and semantic_ids:
        return "semantic:" + str(semantic_ids[0])
    return ""


def _restore_id(item: dict[str, Any]) -> str:
    direct = str(item.get("restore_id") or "")
    if direct:
        return direct
    submit = item.get("submit") if isinstance(item.get("submit"), dict) else {}
    payload = submit.get("payload") if isinstance(submit.get("payload"), dict) else {}
    return str(payload.get("restore_id") or "")
