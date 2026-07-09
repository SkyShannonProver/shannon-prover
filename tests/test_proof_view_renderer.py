from __future__ import annotations

from workflow.proof_management.checkpoints import CheckpointIndex, CheckpointOption
from workflow.proof_management.evidence import EvidenceBundle
from workflow.proof_management.node_state import ProofNodeState
from workflow.proof_management.renderer import ProofViewRenderer


def test_proof_view_renderer_applies_evidence_panels() -> None:
    renderer = ProofViewRenderer()
    state = ProofNodeState(node_id="Tree-unit")
    evidence = EvidenceBundle(
        route_health=[{"signal": "seq_cut_mismatch"}],
        structural_transitions=[{"kind": "probe_wp"}],
        l4_panels={"seq_cut_surface": {"state": "opened"}},
        view_overrides={
            "candidate_moves": {
                "route_health": [{"signal": "local_pure_surgery_available"}]
            }
        },
        removed_panels=["call_site_surface"],
        route_replay_memory={"kind": "route_replay_memory", "items": []},
        lineage_briefing={"kind": "lineage_briefing", "node_id": "Tree-unit"},
        repair_episodes=[{"episode_id": "repair_1"}],
        checkpoint_index=CheckpointIndex(
            structural_items=[
                CheckpointOption({
                    "checkpoint_id": "cp_1",
                    "semantic_id": "before_seq_cut",
                })
            ],
            restore_option=CheckpointOption({
                "restore_id": "restore_1",
                "semantic_id": "restore_before_last_rewind",
            })
        ),
    )

    view = renderer.render(
        {
            "candidate_moves": {},
            "call_site_surface": {"state": "stale"},
            "structural_checkpoints": {"items": []},
        },
        state=state,
        evidence=evidence,
    )

    assert view["candidate_moves"]["route_health"] == [
        {"signal": "local_pure_surgery_available"}
    ]
    assert "structural_transitions" not in view["candidate_moves"]
    assert "call_site_surface" not in view
    assert view["seq_cut_surface"] == {"state": "opened"}
    assert "rewind_route_memory" not in view
    assert view["route_replay_memory"]["kind"] == "route_replay_memory"
    assert "proof_piece_memory" not in view
    assert view["lineage_briefing"]["kind"] == "lineage_briefing"
    assert view["route_replay_memory"]["repair_episodes"] == [
        {"episode_id": "repair_1"}
    ]
    assert view["structural_checkpoints"]["items"][0]["restore_id"] == "restore_1"
    assert view["structural_checkpoints"]["items"][1]["checkpoint_id"] == "cp_1"

    assert view["structural_checkpoints"]["items"][0]["restore_id"] == "restore_1"
    assert view["structural_checkpoints"]["items"][1]["checkpoint_id"] == "cp_1"
