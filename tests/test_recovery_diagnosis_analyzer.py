from __future__ import annotations

from workflow.proof_management.analyzers.recovery import RecoveryDiagnosisAnalyzer
from workflow.proof_management.node_state import ProofNodeState
from workflow.proof_management.recovery import annotate_route_health_items


def _state(view: dict) -> ProofNodeState:
    return ProofNodeState(node_id="Tree-unit", base_workspace_view=view)


def test_recovery_analyzer_prioritizes_visible_pure_tail_work() -> None:
    view = {
        "current_goal": {"lines": ["Current goal", "forall x, x = x"]},
        "pure_tail_surface": {
            "obligation_families": [{"family": "map_update_projection"}],
            "membership_decomposition_surface": {
                "source_shapes": ["map_membership"],
            },
        },
        "candidate_moves": {
            "route_health": [
                {
                    "signal": "lost_call_abstraction_boundary",
                    "recovery_class": "call_frontier_recovery_evidence",
                    "recommended_next": {
                        "intent": "undo_to_checkpoint",
                        "payload": {"checkpoint_id": "cp_outer"},
                    },
                    "repair_checkpoint": {
                        "checkpoint_id": "cp_outer",
                        "semantic_id": "last_call_site_boundary",
                        "label": "Before broad inline #99",
                        "tactic_index": 99,
                        "submit": {
                            "intent": "undo_to_checkpoint",
                            "payload": {"checkpoint_id": "cp_outer"},
                        },
                    },
                }
            ],
        },
    }
    route_health = annotate_route_health_items(
        view["candidate_moves"]["route_health"]
    )
    result = RecoveryDiagnosisAnalyzer().analyze(
        state=_state(view),
        view=view,
        route_health=route_health,
    )

    assert result.surface["recovery_class"] == "local_pure_surgery_available"
    assert result.surface["checkpoint_policy"] == "current_state_local_work_visible"
    assert result.surface["available_local_work"][0]["kind"] == (
        "pure_tail_obligation_families"
    )
    cleaned = result.view_overrides["candidate_moves"]["route_health"][0]
    assert "recommended_next" not in cleaned
    assert "repair_checkpoint" not in cleaned


def test_recovery_analyzer_promotes_visible_frame_gap() -> None:
    view = {
        "current_goal": {
            "lines": [
                "Current goal",
                "pre =",
                "  Mem.lc{1} = Mem.lc{2}",
                "",
                "post =",
                "  (glob A){1} = (glob A){2}",
            ],
        },
        "pure_tail_surface": {
            "membership_decomposition_surface": {
                "source_shapes": ["map_membership"],
            },
        },
    }
    route_health = annotate_route_health_items([
        {"signal": "pure_tail_alignment_gap", "confidence": "medium"}
    ])
    result = RecoveryDiagnosisAnalyzer().analyze(
        state=_state(view),
        view=view,
        route_health=route_health,
    )

    assert result.surface["recovery_class"] == "boundary_repair_evidence"
    assert result.surface["confidence"] == "high"
    assert "={glob A}" in " ".join(result.surface["evidence"])


def test_recovery_analyzer_returns_empty_without_recovery_evidence() -> None:
    view = {
        "current_goal": {"lines": ["Current goal", "post = true"]},
    }

    result = RecoveryDiagnosisAnalyzer().analyze(
        state=_state(view),
        view=view,
        route_health=[],
    )

    assert result.surface == {}
    assert result.view_overrides == {}
