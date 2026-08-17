from __future__ import annotations

import json
from pathlib import Path

from workflow.proof_management.lineage import (
    LemmaLineageStore,
    lineage_briefing_from_events,
)


def test_lemma_lineage_store_appends_jsonl(tmp_path: Path) -> None:
    store = LemmaLineageStore(run_dir=tmp_path)

    store.append({
        "kind": "node_spawned",
        "node": "Tree_0_0",
        "route_family": "seq_cut",
    })

    path = tmp_path / "lemma_lineage.jsonl"
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
    ]
    assert rows[0]["kind"] == "node_spawned"
    assert rows[0]["node"] == "Tree_0_0"
    assert rows[0]["route_family"] == "seq_cut"
    assert rows[0]["created_at"]


def test_lemma_lineage_store_records_typed_node_events(tmp_path: Path) -> None:
    store = LemmaLineageStore(run_dir=tmp_path)

    store.record_node_bootstrap(
        node_id="Tree_0",
        session_tag="unit",
        session_dir=".ec_session_unit",
        replay_prefix_count=3,
    )
    store.record_proof_turn(
        node_id="Tree_0",
        route_event={
            "intent": "commit_tactic",
            "turn_index": 4,
            "accepted": True,
            "changed": False,
            "tactic": "wp.",
        },
    )

    rows = [
        json.loads(line)
        for line in (tmp_path / "lemma_lineage.jsonl").read_text(
            encoding="utf-8"
        ).splitlines()
    ]

    assert [row["kind"] for row in rows] == [
        "node_bootstrapped",
        "proof_turn_recorded",
    ]
    assert rows[0]["replay_prefix_count"] == 3
    assert rows[1]["tactic"] == "wp."


def test_lemma_lineage_store_records_tree_shadow_events(tmp_path: Path) -> None:
    store = LemmaLineageStore(run_dir=tmp_path)

    store.record_tree_run_started(
        cwd="/repo",
        timeout=60,
        max_concurrent=4,
        initial_provers=2,
        resume_roots=1,
        resume_root_policy="diversity",
    )
    store.record_resume_root_chosen(
        node_id="Tree-0.0",
        capsule_path="resume.json",
        capsule_score=12.5,
        tactic_count=7,
        route_family={"family": "top_level_seq_route", "confidence": "medium"},
        resume_diversity={
            "mode": "shadow",
            "score_rank": 0,
            "diversity_rank": 1,
            "route_family": "top_level_seq_route",
        },
        resume_root_policy="diversity",
    )
    store.record_node_spawned(
        node_id="Tree-0.0",
        parent_id="root",
        depth=0,
        replay_prefix=["proc.", "seq 1 1 : P."],
        strategy_index=0,
        spawn_reason="resume_root",
        route_family={"family": "top_level_seq_route", "confidence": "medium"},
    )
    store.record_route_family_assigned(
        node_id="Tree-0.0",
        route_family={
            "family": "top_level_seq_route",
            "confidence": "medium",
            "evidence": ["early seq cut"],
        },
        tactic_count=2,
        reason="poll",
    )
    store.record_node_spawned(
        node_id="Tree-0.0.0",
        parent_id="Tree-0.0",
        depth=1,
        replay_prefix=["proc.", "seq 1 1 : P."],
        spawn_reason="Error stuck",
        failed_at_branch=["call (_: old_inv)."],
        layer_move_action={"move": "same"},
    )
    store.record_repair_branch_created(
        parent_id="Tree-0.0",
        child_id="Tree-0.0.0",
        reason="Error stuck",
        prefix_count=2,
        failed_suffix=["call (_: old_inv)."],
        layer_move_action={"move": "same"},
    )
    store.record_node_killed(
        node_id="Tree-0.0.0",
        reason="capacity",
        committed_count=2,
        max_committed_count_seen=3,
        route_family={"family": "top_level_seq_route"},
    )
    store.record_winner_selected(
        node_id="Tree-0.0",
        completion_candidate=False,
        returncode=0,
        committed_count=5,
        max_committed_count_seen=5,
        route_family={"family": "top_level_seq_route"},
        selection_reason="best_available_branch",
        shadow_selection={
            "kind": "winner_route_family_shadow",
            "mode": "shadow",
            "selected_node": "Tree-0.0",
            "best_by_family": [{
                "node": "Tree-0.0",
                "route_family": "top_level_seq_route",
            }],
        },
    )
    store.record_tree_run_finished(
        winner_node_id="Tree-0.0",
        total_spawned=2,
        max_depth=1,
        completion_candidate=False,
        returncode=0,
    )

    rows = [
        json.loads(line)
        for line in (tmp_path / "lemma_lineage.jsonl").read_text(
            encoding="utf-8"
        ).splitlines()
    ]
    kinds = [row["kind"] for row in rows]
    assert "tree_run_started" in kinds
    run_event = next(row for row in rows if row["kind"] == "tree_run_started")
    assert run_event["resume_root_policy"] == "diversity"
    assert "resume_root_chosen" in kinds
    resume_event = next(row for row in rows if row["kind"] == "resume_root_chosen")
    assert resume_event["resume_diversity"]["diversity_rank"] == 1
    assert resume_event["resume_root_policy"] == "diversity"
    assert "node_spawned" in kinds
    assert "route_family_assigned" in kinds
    assert "repair_branch_created" in kinds
    assert "node_killed" in kinds
    assert "winner_selected" in kinds
    assert "tree_run_finished" in kinds

    briefing = json.loads(
        (tmp_path / "lemma_lineage_briefing.json").read_text(encoding="utf-8")
    )
    assert briefing["kind"] == "lemma_lineage_briefing"
    assert briefing["route_family_counts"]["top_level_seq_route"] == 2
    assert briefing["winner"]["node"] == "Tree-0.0"
    assert briefing["winner"]["shadow_selection"]["mode"] == "shadow"
    assert (tmp_path / "lemma_lineage_briefing.md").exists()
