import json
from pathlib import Path

import pytest

from workflow.proof_node_resume import (
    create_resume_capsules,
    load_resume_capsule,
    load_resume_capsules,
)
from core.easycrypt.session_projection import read_proof_state_projection


def test_load_resume_capsule_from_directory(tmp_path):
    capsule_dir = tmp_path / "Tree_0_1"
    capsule_dir.mkdir()
    (capsule_dir / "history.ec").write_text("proc.\nwp.\n", encoding="utf-8")
    (capsule_dir / "resume.json").write_text(
        json.dumps(
            {
                "kind": "proof_node_resume_capsule",
                "capsule_version": 1,
                "target": {
                    "file": "eval/examples/PIR.ec",
                    "lemma": "PIR_correct",
                    "include_dir": "easycrypt-src/theories",
                },
                "source": {
                    "commit": "abc123",
                    "session_name": "Tree_0_1",
                },
                "replay": {
                    "history_file": "history.ec",
                    "current_goal_hash": "goal-hash",
                    "current_goal_preview": "Current goal ...",
                },
                "score": {
                    "value": 7.5,
                    "reasons": ["deep accepted prefix"],
                },
                "handoff": {
                    "notes": ["resume from accepted structural transition"],
                    "recent_tactics": [],
                },
            }
        ),
        encoding="utf-8",
    )

    capsule = load_resume_capsule(capsule_dir)

    assert capsule.path == (capsule_dir / "resume.json").resolve()
    assert capsule.target_file == "eval/examples/PIR.ec"
    assert capsule.lemma == "PIR_correct"
    assert capsule.replay_prefix == ["proc.", "wp."]
    assert capsule.score == 7.5


def test_load_resume_capsule_surfaces_recorded_tactic_count_mismatch(tmp_path):
    # A capsule whose manifest claims more tactics than history.ec yields is
    # internally inconsistent (truncated/mismatched history); the loader must
    # expose the manifest's claim so the orchestrator can warn "restored 2/90"
    # instead of silently resuming from the shorter prefix.
    capsule_dir = tmp_path / "Tree_0_1"
    capsule_dir.mkdir()
    (capsule_dir / "history.ec").write_text("proc.\nwp.\n", encoding="utf-8")
    (capsule_dir / "resume.json").write_text(
        json.dumps(
            {
                "kind": "proof_node_resume_capsule",
                "capsule_version": 1,
                "target": {
                    "file": "eval/examples/PIR.ec",
                    "lemma": "PIR_correct",
                    "include_dir": "easycrypt-src/theories",
                },
                "source": {"commit": "abc123", "session_name": "Tree_0_1"},
                "replay": {
                    "history_file": "history.ec",
                    "tactic_count": 90,
                    "current_goal_hash": "goal-hash",
                },
                "score": {"value": 7.5, "reasons": []},
                "handoff": {"notes": [], "recent_tactics": []},
            }
        ),
        encoding="utf-8",
    )

    capsule = load_resume_capsule(capsule_dir)

    assert capsule.tactic_count == 2
    assert capsule.recorded_tactic_count == 90

    from workflow.proof_management.lifecycle import replay_prefix_shortfall

    shortfall = replay_prefix_shortfall(
        capsule.recorded_tactic_count, capsule.tactic_count,
    )
    assert shortfall is not None
    assert shortfall["lost"] == 88


def test_load_resume_capsule_recovers_resume_context_from_legacy_view(tmp_path):
    capsule_dir = tmp_path / "Tree_0_1"
    capsule_dir.mkdir()
    (capsule_dir / "history.ec").write_text(
        "proc.\nseq 1 1 : P.\nwp.\n",
        encoding="utf-8",
    )
    (capsule_dir / "timeline_tail.jsonl").write_text(
        json.dumps({
            "kind": "manager_turn",
            "intent": {
                "intent": "probe_tactic",
                "payload": {"tactic": "smt()."},
            },
            "manager_actions": [{
                "action": "tactic probe",
                "error_summary": "cannot prove goal (strict)",
            }],
            "ok": True,
            "turn": 9,
        }) + "\n",
        encoding="utf-8",
    )
    (capsule_dir / "latest_workspace_view.json").write_text(
        json.dumps({
            "proof_status": {"status": "open", "remaining_goals": 1},
            "candidate_moves": {
                "probe_alternatives": [{
                    "tactic": "auto.",
                    "probe_result": "accepted",
                }],
            },
            "rewind_route_memory": {
                "kind": "rewind_route_memory",
                "items": [{
                    "memory_id": "route_old",
                    "available_chunks": [{
                        "chunk_id": "rch_old",
                        "first_tactic": "wp.",
                        "tactic_count": 1,
                    }],
                }],
            },
            "structural_checkpoints": {
                "items": [
                    {
                        "semantic_id": "before_branch_work",
                        "semantic_ids": ["before_branch_work", "resume_start"],
                        "committed_step_index": 3,
                    },
                    {
                        "semantic_id": "restore_before_last_rewind",
                        "semantic_ids": ["restore_before_last_rewind"],
                        "submit": {
                            "intent": "undo_to_checkpoint",
                            "payload": {"restore_id": "restore_old"},
                        },
                    },
                ],
            },
        }),
        encoding="utf-8",
    )
    (capsule_dir / "resume.json").write_text(
        json.dumps(
            {
                "kind": "proof_node_resume_capsule",
                "capsule_version": 1,
                "target": {"file": "x.ec", "lemma": "L", "include_dir": ""},
                "source": {"commit": "abc", "session_name": "Tree_0_1"},
                "replay": {
                    "history_file": "history.ec",
                    "current_goal_hash": "goal",
                    "current_goal_preview": "Current goal",
                },
                "score": {"value": 1, "reasons": []},
                "handoff": {"notes": [], "recent_tactics": []},
            }
        ),
        encoding="utf-8",
    )

    capsule = load_resume_capsule(capsule_dir)

    assert capsule.resume_prefix_count == 2
    context = capsule.resume_context or {}
    assert context["route_memory_payload"]["kind"] == "legacy_route_replay_memory"
    assert context["checkpoint_payload"]["kind"] == "legacy_checkpoint_state"
    assert context["checkpoint_payload"]["legacy_pre_rewind_restore_option"][
        "legacy_resume_surface"
    ]
    assert context["route_event_facts"][0]["rejected"] is True


def test_legacy_continuation_checkpoint_is_retired(tmp_path):
    manifest = tmp_path / "checkpoint.json"
    manifest.write_text(
        json.dumps(
            {
                "kind": "proof_continuation_checkpoint",
                "checkpoint_version": 1,
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="not a proof-node resume capsule"):
        load_resume_capsule(manifest)


def test_resume_capsule_records_repair_lineage_and_route_memory(tmp_path):
    project_root = tmp_path
    run_dir = tmp_path / "run"
    session_dir = tmp_path / ".ec_session_prover_tree_0_2"
    memory_dir = run_dir / "node_memory" / "Tree_0_2"
    route_dir = run_dir / "route_memory"
    session_dir.mkdir()
    memory_dir.mkdir(parents=True)
    route_dir.mkdir(parents=True)
    (session_dir / "history.ec").write_text("proc.\n", encoding="utf-8")
    (session_dir / "current.out").write_text("Current goal\nx = y\n", encoding="utf-8")
    (memory_dir / "latest_workspace_view.json").write_text(
        json.dumps({"proof_status": {"status": "open", "remaining_goals": 2}}),
        encoding="utf-8",
    )
    (run_dir / "lemma_lineage.jsonl").write_text(
        json.dumps({
            "kind": "repair_episode_recorded",
            "node": "Tree_0_2",
            "memory_id": "route_abc",
            "repair_episode_id": "repair_abc",
            "from_checkpoint_id": "cp_call",
            "from_tactic_index": 5,
            "discarded_piece_count": 2,
            "replay_class_counts": {
                "boundary_sensitive": 1,
                "structural_replayable": 1,
            },
            "rewind_note": {
                "hypothesis": "call boundary lost frame fact",
                "broken_boundary_kind": "call_invariant",
                "missing_facts": ["={glob RO}"],
                "intended_repair": "strengthen call invariant",
            },
        }) + "\n",
        encoding="utf-8",
    )
    (run_dir / "lemma_lineage_briefing.json").write_text(
        json.dumps({
            "kind": "lemma_lineage_briefing",
            "node_count": 2,
            "repair_episode_count": 1,
            "route_family_counts": {
                "top_level_seq_route": 1,
                "call_boundary_route": 1,
            },
            "winner": {"node": "Tree_0_1", "proved": False},
        }),
        encoding="utf-8",
    )
    (run_dir / "lemma_lineage_briefing.md").write_text(
        "# Lemma Lineage Briefing\n",
        encoding="utf-8",
    )
    (route_dir / "Tree_0_2_rewind_route_memory.json").write_text(
        json.dumps({
            "kind": "rewind_route_memory",
            "schema_version": 2,
            "route_memories": [{
                "memory_id": "route_abc",
                "discarded_suffix": ["call (_: old_inv).", "wp."],
                "structural_chunks": [{"chunk_id": "rch_abc"}],
                "rewind_note": {
                    "reuse_expectation": "structural suffix should replay",
                },
            }],
            "negative_memories": [{
                "avoid_pattern": "={glob A}",
                "reason": "abstract adversary call writes A",
            }],
        }),
        encoding="utf-8",
    )

    paths = create_resume_capsules(
        project_root=project_root,
        run_dir=run_dir,
        session_dirs=[session_dir],
        target_file="eval/examples/ChaChaPoly/chacha_poly.ec",
        lemma="step4_bad1_lbad1",
        include_dir="easycrypt-src/theories",
    )

    capsule = load_resume_capsule(paths[0])
    joined = "\n".join(capsule.handoff_notes)
    assert "Repair memory before resume" in joined
    assert "Run lineage before resume" in joined
    assert "top_level_seq_route=1" in joined
    assert "call boundary lost frame fact" in joined
    assert "={glob RO}" in joined
    assert "Route replay memory available" in joined
    assert "The manager validates replay chunks before committing them" in joined
    assert "={glob A}" in joined

    manifest_path = (
        tmp_path
        / "run"
        / "resume_capsules"
        / "Tree_0_2_.ec_session_prover_tree_0_2"
        / "resume.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["handoff"]["artifacts"]["lemma_lineage_tail"] == (
        "lemma_lineage_tail.jsonl"
    )
    assert manifest["handoff"]["artifacts"]["lemma_lineage_briefing"] == (
        "lemma_lineage_briefing.json"
    )
    assert manifest["handoff"]["artifacts"]["lemma_lineage_briefing_md"] == (
        "lemma_lineage_briefing.md"
    )
    assert manifest["handoff"]["artifacts"]["route_memory"] == "route_memory.json"
    assert manifest["handoff"]["artifacts"]["resume_route_diversity"] == (
        "resume_route_diversity.json"
    )
    assert manifest["handoff"]["artifacts"]["resume_route_diversity_md"] == (
        "resume_route_diversity.md"
    )
    assert manifest["handoff"]["resume_diversity"]["route_family"] == (
        "linear_prefix_route"
    )
    assert manifest["lineage"]["resume_diversity"]["route_family"] == (
        "linear_prefix_route"
    )
    assert manifest["lineage"]["route_family"]["family"] == "linear_prefix_route"


def test_resume_capsule_carries_verified_route_options(tmp_path):
    project_root = tmp_path
    run_dir = tmp_path / "run"
    session_dir = tmp_path / ".ec_session_prover_tree_0_3"
    memory_dir = run_dir / "node_memory" / "Tree_0_3"
    route_options_dir = session_dir / "route_options"
    session_dir.mkdir()
    memory_dir.mkdir(parents=True)
    route_options_dir.mkdir()
    (session_dir / "history.ec").write_text("congr.\n", encoding="utf-8")
    (session_dir / "current.out").write_text("Current goal\nPr[A] = Pr[B]\n", encoding="utf-8")
    (memory_dir / "latest_workspace_view.json").write_text(
        json.dumps({"proof_status": {"status": "open", "remaining_goals": 1}}),
        encoding="utf-8",
    )
    route_option = {
        "kind": "verified_route_option",
        "schema_version": 1,
        "option_id": "bridge_options.abc",
        "topic": "bridge_options",
        "mode": "bridge",
        "producer": "deterministic_pr_bridge_compiler",
        "semantic_objective": "normalize then rewrite bridge",
        "confidence": "verified",
        "submit": {
            "intent": "commit_tactic",
            "payload": {"tactic": "rewrite -(OpCCinit.pr_CCP_OCCP I_stateless G1 &m)."},
        },
        "tactic_chain": [
            "rewrite -(OpCCinit.pr_CCP_OCCP I_stateless G1 &m).",
        ],
        "bindings": {"namespace": "OpCCinit"},
        "evidence_refs": ["probe.pr_bridge.0"],
        "verification_evidence": [{
            "id": "probe.pr_bridge.0",
            "accepted": True,
        }],
    }
    (route_options_dir / "verified_route_options.jsonl").write_text(
        json.dumps(route_option) + "\n",
        encoding="utf-8",
    )

    paths = create_resume_capsules(
        project_root=project_root,
        run_dir=run_dir,
        session_dirs=[session_dir],
        target_file="eval/examples/ChaChaPoly/chacha_poly.ec",
        lemma="step1",
        include_dir="easycrypt-src/theories",
    )

    manifest = json.loads(Path(paths[0]).read_text(encoding="utf-8"))
    assert manifest["handoff"]["artifacts"]["verified_route_options"] == (
        "verified_route_options.jsonl"
    )
    assert manifest["handoff"]["verified_route_options"][0]["option_id"] == (
        "bridge_options.abc"
    )
    capsule = load_resume_capsule(paths[0])
    context = capsule.resume_context or {}
    assert context["verified_route_options"][0]["submit"]["intent"] == "commit_tactic"
    assert context["verified_route_options"][0]["bindings"] == {
        "namespace": "OpCCinit"
    }
    assert "Verified route options before resume" in "\n".join(capsule.handoff_notes)


def test_resume_capsule_index_records_diversity_order(tmp_path):
    project_root = tmp_path
    run_dir = tmp_path / "run"
    session_a = tmp_path / ".ec_session_prover_tree_0_0"
    session_b = tmp_path / ".ec_session_prover_tree_0_1"
    memory_a = run_dir / "node_memory" / "Tree_0_0"
    memory_b = run_dir / "node_memory" / "Tree_0_1"
    session_a.mkdir()
    session_b.mkdir()
    memory_a.mkdir(parents=True)
    memory_b.mkdir(parents=True)
    (session_a / "history.ec").write_text(
        "proc.\nseq 1 1 : P.\nwp.\n",
        encoding="utf-8",
    )
    (session_b / "history.ec").write_text(
        "proc.\ncall (_: inv).\n",
        encoding="utf-8",
    )
    (session_a / "current.out").write_text("Current goal\nA\n", encoding="utf-8")
    (session_b / "current.out").write_text("Current goal\nB\n", encoding="utf-8")
    (memory_a / "latest_workspace_view.json").write_text(
        json.dumps({"proof_status": {"status": "open", "remaining_goals": 1}}),
        encoding="utf-8",
    )
    (memory_b / "latest_workspace_view.json").write_text(
        json.dumps({
            "proof_status": {
                "status": "open",
                "remaining_goals": 2,
                "current_layer": "call_site",
            },
        }),
        encoding="utf-8",
    )

    paths = create_resume_capsules(
        project_root=project_root,
        run_dir=run_dir,
        session_dirs=[session_a, session_b],
        target_file="eval/examples/ChaChaPoly/chacha_poly.ec",
        lemma="step4_bad1_lbad1",
        include_dir="easycrypt-src/theories",
    )

    index = json.loads(
        (run_dir / "resume_capsules" / "index.json").read_text(encoding="utf-8")
    )
    score_paths = [item["path"] for item in index["capsules"]]
    assert score_paths == paths
    groups = index["route_diversity"]["route_family_groups"]
    assert groups["top_level_seq_route"]["count"] == 1
    assert groups["call_boundary_route"]["count"] == 1
    diversity_families = [
        item["route_family"]["family"]
        for item in index["route_diversity"]["diversity_order"]
    ]
    assert set(diversity_families) == {
        "top_level_seq_route",
        "call_boundary_route",
    }
    assert (run_dir / "resume_capsules" / "resume_route_diversity.md").exists()
    for manifest_path in paths:
        manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
        joined = "\n".join(manifest["handoff"]["notes"])
        assert "Resume diversity shadow" in joined


def test_load_resume_capsules_can_order_by_diversity_policy(tmp_path):
    def write_capsule(name: str, *, score: float, history: str, family: str) -> Path:
        capsule_dir = tmp_path / name
        capsule_dir.mkdir()
        tactics = "\n".join(["proc."] * history.count("\n")) + "\n"
        (capsule_dir / "history.ec").write_text(tactics, encoding="utf-8")
        (capsule_dir / "resume.json").write_text(
            json.dumps({
                "kind": "proof_node_resume_capsule",
                "capsule_version": 1,
                "target": {
                    "file": "eval/examples/ChaChaPoly/chacha_poly.ec",
                    "lemma": "step4_bad1_lbad1",
                },
                "source": {"session_name": name},
                "replay": {"history_file": "history.ec"},
                "score": {
                    "value": score,
                    "route_family": {"family": family},
                },
                "handoff": {"notes": [], "recent_tactics": []},
            }),
            encoding="utf-8",
        )
        return capsule_dir / "resume.json"

    seq_a = write_capsule(
        "seq_a",
        score=10.0,
        history="a\nb\nc\n",
        family="top_level_seq_route",
    )
    seq_b = write_capsule(
        "seq_b",
        score=9.0,
        history="a\nb\n",
        family="top_level_seq_route",
    )
    call_a = write_capsule(
        "call_a",
        score=8.0,
        history="a\nb\nc\nd\n",
        family="call_boundary_route",
    )

    score_order = load_resume_capsules([seq_b, call_a, seq_a], policy="score")
    diversity_order = load_resume_capsules([seq_b, call_a, seq_a], policy="diversity")

    assert [capsule.session_name for capsule in score_order] == [
        "seq_a",
        "seq_b",
        "call_a",
    ]
    assert [capsule.session_name for capsule in diversity_order] == [
        "seq_a",
        "call_a",
        "seq_b",
    ]
    with pytest.raises(ValueError, match="unsupported resume root policy"):
        load_resume_capsules([seq_a], policy="unknown")


def test_resume_capsule_prefers_session_goal_hash_over_memory_timeline(tmp_path):
    project_root = tmp_path
    run_dir = tmp_path / "run"
    session_dir = tmp_path / ".ec_session_prover_tree_0_0"
    memory_dir = run_dir / "node_memory" / "Tree_0_0"
    session_dir.mkdir()
    memory_dir.mkdir(parents=True)
    (session_dir / "history.ec").write_text("proc.\n", encoding="utf-8")
    (session_dir / "current.out").write_text(
        "[1|check]>\nCurrent goal\n----\nx = y\n[2|check]>\n",
        encoding="utf-8",
    )
    (memory_dir / "timeline.jsonl").write_text(
        json.dumps({"goal_hash": "stale-memory-hash"}) + "\n",
        encoding="utf-8",
    )
    expected = read_proof_state_projection(session_dir).goal.active_goal_hash

    paths = create_resume_capsules(
        project_root=project_root,
        run_dir=run_dir,
        session_dirs=[session_dir],
        target_file="eval/examples/PIR.ec",
        lemma="PIR_correct",
        include_dir="easycrypt-src/theories",
    )

    capsule = load_resume_capsule(paths[0])
    assert capsule.current_goal_hash == expected
    assert capsule.current_goal_hash != "stale-memory-hash"
