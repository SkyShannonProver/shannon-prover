"""Proof analyzer pipeline boundary."""
from __future__ import annotations

from typing import Any

from workflow.proof_management.checkpoints import CheckpointIndex
from workflow.proof_management.evidence import EvidenceBundle
from workflow.proof_management.node_state import ProofNodeState
from workflow.proof_management.analyzers.call_site import CallSiteAnalyzer
from workflow.proof_management.analyzers.frame_obligation import (
    FrameObligationAnalyzer,
)
from workflow.proof_management.analyzers.pure_tail import PureTailAnalyzer
from workflow.proof_management.analyzers.recovery import RecoveryDiagnosisAnalyzer
from workflow.proof_management.analyzers.route_health import (
    RouteHealthAnalysis,
    RouteHealthAnalyzer,
)
from workflow.proof_management.analyzers.seq_cut import SeqCutAnalyzer


class AnalyzerPipeline:
    """Combines analyzer outputs into one evidence bundle.

    The pipeline is pure with respect to EasyCrypt state: it consumes the
    current node state, checkpoint index, and base workspace view, then returns
    evidence for the renderer.
    """

    def __init__(self) -> None:
        self.call_site = CallSiteAnalyzer()
        self.frame_obligation = FrameObligationAnalyzer()
        self.pure_tail = PureTailAnalyzer()
        self.recovery = RecoveryDiagnosisAnalyzer()
        self.route_health = RouteHealthAnalyzer()
        self.seq_cut = SeqCutAnalyzer()

    def analyze_route(
        self,
        *,
        state: ProofNodeState,
        workspace_view: dict[str, Any] | None = None,
    ) -> RouteHealthAnalysis:
        return self.route_health.analyze(
            state=state,
            view=workspace_view,
        )

    def run(
        self,
        *,
        state: ProofNodeState,
        checkpoint_index: CheckpointIndex,
        workspace_view: dict[str, Any] | None = None,
        route_health: list[dict[str, Any]] | None = None,
        structural_transitions: list[dict[str, Any]] | None = None,
        l4_panels: dict[str, dict[str, Any]] | None = None,
        view_overrides: dict[str, Any] | None = None,
        removed_panels: list[str] | None = None,
        route_replay_memory: dict[str, Any] | None = None,
        lineage_briefing: dict[str, Any] | None = None,
        repair_episodes: list[dict[str, Any]] | None = None,
    ) -> EvidenceBundle:
        view_overrides_out = dict(view_overrides or {})
        removed_panels_out = [
            str(item)
            for item in (removed_panels or [])
            if str(item).strip()
        ]
        l4 = {
            key: dict(value)
            for key, value in (l4_panels or {}).items()
            if isinstance(value, dict)
        }
        base_view = dict(workspace_view or state.base_workspace_view)
        call_site = self.call_site.analyze(state=state, view=base_view)
        if call_site.surface and "call_site_surface" not in l4:
            l4["call_site_surface"] = call_site.surface
        for panel in call_site.removed_panels:
            if panel not in removed_panels_out and panel not in l4:
                removed_panels_out.append(panel)
        view_overrides_out.update(call_site.view_overrides)
        seq_cut = self.seq_cut.analyze(state=state, view=base_view)
        if seq_cut and "seq_cut_surface" not in l4:
            l4["seq_cut_surface"] = seq_cut
        frame_obligation = self.frame_obligation.analyze(state=state, view=base_view)
        if frame_obligation and "frame_obligation_ledger" not in l4:
            l4["frame_obligation_ledger"] = frame_obligation
        analysis_view = _analysis_view(
            base_view,
            l4_panels=l4,
            view_overrides=view_overrides_out,
            removed_panels=removed_panels_out,
            checkpoint_index=checkpoint_index,
            route_health=route_health,
            structural_transitions=structural_transitions,
            route_replay_memory=route_replay_memory,
        )
        pure_tail = self.pure_tail.analyze(state=state, view=analysis_view)
        if pure_tail and "pure_tail_surface" not in l4:
            l4["pure_tail_surface"] = pure_tail
            analysis_view = _analysis_view(
                base_view,
                l4_panels=l4,
                view_overrides=view_overrides_out,
                removed_panels=removed_panels_out,
                checkpoint_index=checkpoint_index,
                route_health=route_health,
                structural_transitions=structural_transitions,
                route_replay_memory=route_replay_memory,
            )
        recovery = self.recovery.analyze(
            state=state,
            view=analysis_view,
            route_health=[
                dict(item)
                for item in (route_health or [])
                if isinstance(item, dict)
            ],
        )
        if recovery.surface and "recovery_diagnosis_surface" not in l4:
            l4["recovery_diagnosis_surface"] = recovery.surface
        view_overrides_out.update(recovery.view_overrides)
        view_overrides_out = _view_overrides_with_candidate_evidence(
            view_overrides_out,
            route_health=route_health,
            structural_transitions=structural_transitions,
        )
        return EvidenceBundle(
            route_health=[
                dict(item)
                for item in (route_health or [])
                if isinstance(item, dict)
            ],
            structural_transitions=[
                dict(item)
                for item in (structural_transitions or [])
                if isinstance(item, dict)
            ],
            l4_panels=l4,
            view_overrides=view_overrides_out,
            removed_panels=removed_panels_out,
            route_replay_memory=dict(route_replay_memory or {}),
            lineage_briefing=dict(lineage_briefing or {}),
            repair_episodes=[
                dict(item)
                for item in (repair_episodes or [])
                if isinstance(item, dict)
            ],
            checkpoint_index=checkpoint_index,
        )


def _analysis_view(
    base_view: dict[str, Any],
    *,
    l4_panels: dict[str, dict[str, Any]],
    view_overrides: dict[str, Any],
    removed_panels: list[str] | None,
    checkpoint_index: CheckpointIndex,
    route_health: list[dict[str, Any]] | None,
    structural_transitions: list[dict[str, Any]] | None,
    route_replay_memory: dict[str, Any] | None,
) -> dict[str, Any]:
    raw = dict(base_view)
    for key in (removed_panels or []):
        raw.pop(str(key), None)
    for key, value in l4_panels.items():
        raw[key] = dict(value)
    for key, value in view_overrides.items():
        raw[key] = value
    structural_items = checkpoint_index.structural_surface()
    if structural_items and not isinstance(raw.get("structural_checkpoints"), dict):
        raw["structural_checkpoints"] = {"items": structural_items}
    if route_replay_memory:
        raw["route_replay_memory"] = dict(route_replay_memory)
    candidate_moves = dict(raw.get("candidate_moves") or {})
    if route_health and not candidate_moves.get("route_health"):
        candidate_moves["route_health"] = [
            dict(item)
            for item in route_health
            if isinstance(item, dict)
        ]
    if structural_transitions and not candidate_moves.get("structural_transitions"):
        candidate_moves["structural_transitions"] = [
            dict(item)
            for item in structural_transitions
            if isinstance(item, dict)
        ]
    if candidate_moves:
        raw["candidate_moves"] = candidate_moves
    return raw


def _view_overrides_with_candidate_evidence(
    view_overrides: dict[str, Any],
    *,
    route_health: list[dict[str, Any]] | None,
    structural_transitions: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    candidate_moves = view_overrides.get("candidate_moves")
    if not isinstance(candidate_moves, dict):
        return view_overrides
    merged = dict(candidate_moves)
    if route_health and "route_health" not in merged:
        merged["route_health"] = [
            dict(item)
            for item in route_health[:2]
            if isinstance(item, dict)
        ]
    if structural_transitions and "structural_transitions" not in merged:
        merged["structural_transitions"] = [
            dict(item)
            for item in structural_transitions[:3]
            if isinstance(item, dict)
        ]
    out = dict(view_overrides)
    out["candidate_moves"] = merged
    return out
