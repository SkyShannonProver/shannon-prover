"""Read-only probe candidate portfolio management."""
from __future__ import annotations

from typing import Any

from .backend_actions import accepted_probe_preview_effects
from .common import _dict, _drop_empty, _list
from .protocol_repair import AgentIntent
from .transitions import structural_transition_surface


class ProofProbeAlternativeManager:
    """Owns current-state read-only probe alternatives."""

    def __init__(self) -> None:
        self._by_state: dict[tuple[int, int, str], list[dict[str, Any]]] = {}

    def record(
        self,
        intent: AgentIntent,
        snapshot: Any,
        observation: dict[str, Any],
    ) -> None:
        if intent.intent != "probe_tactic":
            return
        tactic = str(
            observation.get("tactic")
            or intent.payload.get("tactic")
            or ""
        ).strip()
        if not tactic:
            return
        key = snapshot_probe_key(snapshot)
        entry = probe_alternative_entry(tactic, observation)
        entries = list(self._by_state.get(key, []))
        entries = [
            item
            for item in entries
            if str(item.get("tactic") or "").strip() != tactic
        ]
        entries.append(entry)
        accepted = [
            item
            for item in entries
            if str(item.get("probe_result") or "") == "accepted"
        ]
        rejected = [
            item
            for item in entries
            if str(item.get("probe_result") or "") != "accepted"
        ]
        self._by_state = {
            **self._by_state,
            key: [*accepted[-4:], *rejected[-3:]][-6:],
        }

    def alternatives_for_snapshot(self, snapshot: Any) -> list[dict[str, Any]]:
        return [
            dict(item)
            for item in self._by_state.get(snapshot_probe_key(snapshot), [])
            if isinstance(item, dict)
        ]

    def seed_for_snapshot(
        self,
        snapshot: Any,
        alternatives: list[dict[str, Any]],
    ) -> None:
        entries = [
            dict(item)
            for item in alternatives
            if isinstance(item, dict)
        ][-6:]
        if entries:
            self._by_state[snapshot_probe_key(snapshot)] = entries

    def workspace_view_with_alternatives(
        self,
        workspace_view: dict[str, Any],
        snapshot: Any,
    ) -> dict[str, Any]:
        return workspace_view_with_probe_alternatives(
            workspace_view,
            self.alternatives_for_snapshot(snapshot),
        )


def snapshot_probe_key(snapshot: Any) -> tuple[int, int, str]:
    return (
        int(getattr(snapshot, "session_epoch", 0) or 0),
        int(getattr(snapshot, "state_version", 0) or 0),
        str(getattr(snapshot, "goal_hash", "") or ""),
    )


def workspace_view_with_probe_alternatives(
    workspace_view: dict[str, Any],
    alternatives: list[dict[str, Any]],
) -> dict[str, Any]:
    raw = dict(_dict(workspace_view))
    if not alternatives:
        return raw
    candidate_moves = dict(_dict(raw.get("candidate_moves")))
    candidate_moves["probe_alternatives"] = [
        dict(item)
        for item in alternatives
        if isinstance(item, dict)
    ][-6:]
    raw["candidate_moves"] = _drop_empty(candidate_moves)
    return raw


def probe_alternative_entry(
    tactic: str,
    observation: dict[str, Any],
) -> dict[str, Any]:
    preview = _dict(observation.get("probe_preview"))
    accepted = bool(preview)
    probe_tool_error = is_probe_tool_error(observation)
    goal_after = _dict(preview.get("goal_after_probe"))
    lines = [
        str(line)
        for line in _list(goal_after.get("lines"))
        if isinstance(line, str)
    ]
    goal_summary = _drop_empty({
        "remaining_goals": preview.get("goal_after_remaining"),
        "first_lines": lines[:4],
        "char_count": goal_after.get("char_count"),
        "truncated": goal_after.get("truncated"),
    })
    if accepted:
        transition = structural_transition_surface(
            tactic,
            status="accepted_checkpoint",
            submit_intent="commit_tactic",
        )
        preview_effects = accepted_probe_preview_effects(tactic, preview)
        if preview_effects and transition.get("kind") == "structural_transition":
            transition = dict(transition)
            commit_action = transition.pop("recommended_next", None)
            if commit_action:
                transition["available_commit"] = commit_action
            transition["observed_risk"] = preview_effects.get("observed_risk")
        if transition.get("kind") == "closing_or_checking":
            return _drop_empty({
                "tactic": tactic,
                "probe_result": "accepted",
                "status": "verified_on_current_state",
                "how_to_use": (
                    "This closing/checking tactic was accepted by a read-only "
                    "probe on the current proof state. Commit it only if you "
                    "want to try closing or checking this obligation."
                ),
                "closing_decision": transition,
                "goal_after_probe_summary": goal_summary,
            })
        return _drop_empty({
            "tactic": tactic,
            "probe_result": "accepted",
            "status": "verified_on_current_state",
            "how_to_use": (
                "This tactic was accepted by a read-only probe on the current "
                "proof state. The transition record describes the checked "
                "effect and any visible limitations."
            ),
            "structural_transition": transition,
            "preview_effects": preview_effects,
            "goal_after_probe_summary": goal_summary,
        })
    if probe_tool_error:
        return _drop_empty({
            "tactic": tactic,
            "probe_result": "tool_error",
            "status": "probe_infrastructure_error",
            "how_to_use": (
                "The read-only probe failed before EasyCrypt could validate "
                "this tactic. Do not treat this as evidence that the tactic "
                "is invalid; retry after the backend is healthy or choose a "
                "commit only if the proof route is otherwise clear."
            ),
            "error_summary": observation.get("error_summary"),
        })
    return _drop_empty({
        "tactic": tactic,
        "probe_result": "rejected",
        "status": "do_not_commit_unchanged",
        "how_to_use": (
            "This tactic was rejected by a read-only probe on the current "
            "proof state. Repair it before probing again."
        ),
        "error_summary": observation.get("error_summary"),
    })


def is_probe_tool_error(observation: dict[str, Any]) -> bool:
    if str(observation.get("kind") or "") == "probe_tool_error":
        return True
    text = " ".join(
        str(observation.get(key) or "")
        for key in ("result", "error_summary")
    ).lower()
    return any(
        marker in text
        for marker in (
            "probe tool failed",
            "could not sync daemon",
            "daemon connection",
            "session open",
            "backend health",
        )
    )

