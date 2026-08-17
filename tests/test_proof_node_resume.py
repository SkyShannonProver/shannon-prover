import json
from pathlib import Path

import pytest

from workflow.proof_node_resume import (
    _checkpoint_payload_for_node,
    _manager_route_events_for_node,
    _resume_route_events_from_manager,
    create_resume_capsules,
    load_resume_capsule,
    load_resume_capsules,
)
from workflow.proof_management.event_store import (
    ProofEventManager,
    RESUME_ROUTE_EVENT_SCHEMA_VERSION,
)
from core.easycrypt.session_events import append_event
from core.easycrypt.session_projection import read_proof_state_projection


def _start_session_authority(
    session_dir: Path,
    *,
    file: str = "target.ec",
    lemma: str = "L",
) -> None:
    append_event(session_dir, "session.started", {
        "file": file,
        "lemma": lemma,
        "include_dirs": [],
        "discarded_tactic_count": 0,
        "restart_count": 1,
    })


def _checkpoint_sidecar(*, node_id: str = "Tree-0.0") -> dict:
    return {
        "schema_version": 1,
        "kind": "proof_checkpoint_state",
        "node_id": node_id,
        "pre_rewind_restore_anchor": {
            "restore_id": "restore_current",
            "tactics": ["proc."],
            "from_checkpoint_id": "cp_current",
            "from_tactic_index": 1,
        },
    }


def test_checkpoint_lookup_exact_binds_requested_canonical_node(tmp_path) -> None:
    checkpoint_dir = tmp_path / "checkpoint_state"
    checkpoint_dir.mkdir()
    (checkpoint_dir / "Tree-0.0_checkpoint_state.json").write_text(
        json.dumps(_checkpoint_sidecar(node_id="Tree-other")),
        encoding="utf-8",
    )

    assert _checkpoint_payload_for_node(tmp_path, "Tree-0.0") == {}


def test_checkpoint_lookup_does_not_fan_out_legacy_slug_aliases(tmp_path) -> None:
    checkpoint_dir = tmp_path / "checkpoint_state"
    checkpoint_dir.mkdir()
    (checkpoint_dir / "Tree_0_0_checkpoint_state.json").write_text(
        json.dumps(_checkpoint_sidecar()),
        encoding="utf-8",
    )

    assert _checkpoint_payload_for_node(tmp_path, "Tree-0.0") == {}


def test_resume_capsule_rejects_misbound_checkpoint_artifact(tmp_path) -> None:
    capsule_dir = tmp_path / "misbound_checkpoint"
    capsule_dir.mkdir()
    (capsule_dir / "history.ec").write_text("proc.\n", encoding="utf-8")
    (capsule_dir / "checkpoint_state.json").write_text(
        json.dumps(_checkpoint_sidecar(node_id="Tree-other")),
        encoding="utf-8",
    )
    (capsule_dir / "resume.json").write_text(
        json.dumps({
            "kind": "proof_node_resume_capsule",
            "capsule_version": 2,
            "target": {"file": "target.ec", "lemma": "target"},
            "source": {
                "node_id": "Tree-0.0",
                "session_name": ".ec_session_prover_tree_0_0",
            },
            "replay": {
                "history_file": "history.ec",
                "resume_prefix_count": 1,
            },
            "score": {"value": 1.0, "reasons": []},
            "handoff": {
                "notes": [],
                "recent_tactics": [],
                "route_event_facts": [],
            },
        }),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="misbound checkpoint_state"):
        load_resume_capsule(capsule_dir)


def test_resume_route_facts_come_from_typed_manager_events(tmp_path) -> None:
    manager = ProofEventManager(node_id="Tree-0.0", run_dir=tmp_path)
    manager.record_route_event({
        "intent": "undo_to_checkpoint",
        "outcome_kind": "control_menu",
        "proof_state_effect": "unchanged",
        "needs_attention": False,
        "accepted": False,
        "rejected": False,
        "changed": False,
    })
    manager.record_route_event({
        "intent": "commit_tactic",
        "tactic": "wp.",
        "tactic_head": "wp",
        "outcome_kind": "accepted",
        "proof_state_effect": "changed",
        "needs_attention": False,
        "accepted": True,
        "rejected": False,
        "changed": True,
    })

    current = _manager_route_events_for_node(tmp_path, "Tree-0.0")
    resume = _resume_route_events_from_manager(current)

    assert resume[0]["intent"] == "undo_to_checkpoint"
    assert resume[0]["outcome_kind"] == "control_menu"
    assert resume[1]["tactic"] == "wp."
    assert resume[1]["accepted"] is True
    assert resume[1]["changed"] is True


def test_create_resume_capsule_uses_typed_verdict_not_timeline_prose(
    tmp_path: Path,
) -> None:
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
    _start_session_authority(session_dir)
    # This retired prose says the opposite of the typed manager event and must
    # remain audit-only.
    (memory_dir / "timeline.jsonl").write_text(
        json.dumps({
            "turn": 1,
            "intent": {
                "intent": "commit_tactic",
                "payload": {"tactic": "wp."},
            },
            "manager_actions": [{"outcome": "accepted"}],
        }) + "\n",
        encoding="utf-8",
    )
    correct = ProofEventManager(node_id="Tree-0.0", run_dir=run_dir)
    correct.record_route_event({
        "intent": "commit_tactic",
        "tactic": "wp.",
        "tactic_head": "wp",
        "outcome_kind": "rejected",
        "proof_state_effect": "unchanged",
        "needs_attention": True,
        "accepted": False,
        "rejected": True,
        "changed": False,
        "error_summary": "typed rejection",
    })
    other = ProofEventManager(node_id="Tree-9.9", run_dir=run_dir)
    other.record_route_event({
        "intent": "commit_tactic",
        "tactic": "smt().",
        "tactic_head": "smt",
        "outcome_kind": "accepted",
        "proof_state_effect": "changed",
        "needs_attention": False,
        "accepted": True,
        "rejected": False,
        "changed": True,
    })

    paths = create_resume_capsules(
        project_root=tmp_path,
        run_dir=run_dir,
        session_dirs=[session_dir],
        target_file="target.ec",
        lemma="L",
    )
    manifest = json.loads(Path(paths[0]).read_text(encoding="utf-8"))

    assert manifest["handoff"]["route_event_facts"] == [{
        "kind": "resume_route_event",
        "schema_version": RESUME_ROUTE_EVENT_SCHEMA_VERSION,
        "intent": "commit_tactic",
        "tactic": "wp.",
        "tactic_head": "wp",
        "outcome_kind": "rejected",
        "proof_state_effect": "unchanged",
        "needs_attention": True,
        "accepted": False,
        "rejected": True,
        "changed": False,
        "error_summary": "typed rejection",
    }]
    assert manifest["handoff"]["recent_tactics"] == [{
        "turn": 1,
        "intent": "commit_tactic",
        "status": "rejected",
        "tactic": "wp.",
        "outcome": "typed rejection",
    }]


def test_create_resume_capsule_does_not_fallback_to_timeline_route_facts(
    tmp_path: Path,
) -> None:
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
    _start_session_authority(session_dir)
    (memory_dir / "timeline.jsonl").write_text(
        json.dumps({
            "turn": 1,
            "intent": {
                "intent": "commit_tactic",
                "payload": {"tactic": "wp."},
            },
            "manager_actions": [{"outcome": "accepted"}],
        }) + "\n",
        encoding="utf-8",
    )

    paths = create_resume_capsules(
        project_root=tmp_path,
        run_dir=run_dir,
        session_dirs=[session_dir],
        target_file="target.ec",
        lemma="L",
    )
    manifest = json.loads(Path(paths[0]).read_text(encoding="utf-8"))

    assert manifest["handoff"]["route_event_facts"] == []
    assert manifest["handoff"]["recent_tactics"] == []


def test_create_resume_capsule_skips_open_session_without_goal_identity(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "run"
    session_dir = tmp_path / ".ec_session_prover_tree_0_0"
    memory_dir = run_dir / "node_memory" / "Tree_0_0"
    session_dir.mkdir()
    memory_dir.mkdir(parents=True)
    (session_dir / "history.ec").write_text("proc.\n", encoding="utf-8")
    (memory_dir / "latest_workspace_view.json").write_text(
        json.dumps({"proof_status": {"status": "open"}}),
        encoding="utf-8",
    )
    # This is deliberately stale/unbound to the current history prefix.  It
    # must no longer repair a missing canonical session identity.
    (memory_dir / "timeline.jsonl").write_text(
        json.dumps({"goal_hash": "stale-memory-goal-hash"}) + "\n",
        encoding="utf-8",
    )

    paths = create_resume_capsules(
        project_root=tmp_path,
        run_dir=run_dir,
        session_dirs=[session_dir],
        target_file="target.ec",
        lemma="L",
    )

    assert paths == []


def test_closed_resume_capsule_may_omit_goal_identity(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    session_dir = tmp_path / ".ec_session_prover_tree_0_0"
    session_dir.mkdir()
    (session_dir / "history.ec").write_text("qed.\n", encoding="utf-8")
    append_event(session_dir, "session.started", {
        "file": None,
        "lemma": "L",
        "include_dirs": [],
        "discarded_tactic_count": 0,
        "restart_count": 1,
    })
    append_event(session_dir, "tool.called", {
        "name": "commit",
        "mutates_proof_state": True,
        "session_dir": str(session_dir.resolve()),
    })
    append_event(session_dir, "tactic.submitted", {
        "tactic": "qed.",
        "history_lines_before": 0,
        "line_count": 1,
    })
    append_event(session_dir, "goal.changed", {
        "tactic": "qed.",
        "goals_before": 1,
        "goals_after": 0,
        "no_more_goals": True,
        "async_check_close": False,
        "no_progress": False,
        "candidate_closed": True,
    })
    append_event(session_dir, "tactic.result", {
        "tactic": "qed.",
        "status": "ok",
        "history_committed": True,
        "candidate_closed": True,
    })
    append_event(session_dir, "proof.candidate_closed", {
        "tactic": "qed.",
        "goals_before": 1,
        "goals_after": 0,
        "no_more_goals": True,
        "async_check_close": False,
    })
    append_event(session_dir, "tool.result", {
        "name": "commit",
        "mutates_proof_state": True,
        "session_dir": str(session_dir.resolve()),
        "exit_code": 0,
        "status": "ok",
    })

    paths = create_resume_capsules(
        project_root=tmp_path,
        run_dir=run_dir,
        session_dirs=[session_dir],
        target_file="target.ec",
        lemma="L",
    )

    assert len(paths) == 1
    manifest = json.loads(Path(paths[0]).read_text(encoding="utf-8"))
    assert manifest["replay"]["current_goal_hash"] == ""
    assert manifest["replay"]["proof_status"] == "session_closed_pending_verification"
    assert manifest["replay"]["goal_identity_required"] is False
    loaded = load_resume_capsule(paths[0])
    assert loaded.current_goal_hash == ""
    assert loaded.proof_status == "session_closed_pending_verification"
    assert loaded.goal_identity_required is False


def test_load_resume_capsule_rejects_missing_goal_identity_classification(
    tmp_path: Path,
) -> None:
    capsule_dir = tmp_path / "unsafe_open"
    capsule_dir.mkdir()
    (capsule_dir / "history.ec").write_text("proc.\n", encoding="utf-8")
    (capsule_dir / "resume.json").write_text(
        json.dumps({
            "kind": "proof_node_resume_capsule",
            "capsule_version": 2,
            "target": {"file": "target.ec", "lemma": "L"},
            "source": {"session_name": "Tree_0"},
            "replay": {
                "history_file": "history.ec",
                "resume_prefix_count": 1,
                "current_goal_hash": "",
            },
            "score": {"value": 1.0},
            "lineage": {},
            "handoff": {"notes": [], "route_event_facts": []},
        }),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="replay.goal_identity_required"):
        load_resume_capsule(capsule_dir)


@pytest.mark.parametrize(
    ("identity_required", "goal_hash", "proof_status", "message"),
    [
        (True, "", "open", "non-empty field replay.current_goal_hash"),
        (False, "unexpected", "candidate_closed", "empty field replay.current_goal_hash"),
    ],
)
def test_load_resume_capsule_requires_goal_hash_iff_identity_is_required(
    tmp_path: Path,
    identity_required: bool,
    goal_hash: str,
    proof_status: str,
    message: str,
) -> None:
    capsule_dir = tmp_path / f"identity_{identity_required}"
    capsule_dir.mkdir()
    (capsule_dir / "history.ec").write_text("proc.\n", encoding="utf-8")
    (capsule_dir / "resume.json").write_text(
        json.dumps({
            "kind": "proof_node_resume_capsule",
            "capsule_version": 2,
            "target": {"file": "target.ec", "lemma": "L"},
            "source": {"session_name": "Tree_0"},
            "replay": {
                "history_file": "history.ec",
                "resume_prefix_count": 1,
                "current_goal_hash": goal_hash,
                "proof_status": proof_status,
                "goal_identity_required": identity_required,
            },
            "score": {"value": 1.0},
            "lineage": {},
            "handoff": {"notes": [], "route_event_facts": []},
        }),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=message):
        load_resume_capsule(capsule_dir)


def test_load_resume_capsule_from_directory(tmp_path):
    capsule_dir = tmp_path / "Tree_0_1"
    capsule_dir.mkdir()
    (capsule_dir / "history.ec").write_text("proc.\nwp.\n", encoding="utf-8")
    (capsule_dir / "resume.json").write_text(
        json.dumps(
            {
                "kind": "proof_node_resume_capsule",
                "capsule_version": 2,
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
                    "resume_prefix_count": 2,
                    "current_goal_hash": "goal-hash",
                    "goal_identity_required": True,
                    "current_goal_preview": "Current goal ...",
                },
                "score": {
                    "value": 7.5,
                    "reasons": ["deep accepted prefix"],
                },
                "handoff": {
                    "notes": ["resume from accepted structural transition"],
                    "recent_tactics": [],
                    "route_event_facts": [{
                        "kind": "resume_route_event",
                        "schema_version": RESUME_ROUTE_EVENT_SCHEMA_VERSION,
                        "intent": "commit_tactic",
                        "tactic": "wp.",
                        "outcome_kind": "accepted",
                        "proof_state_effect": "changed",
                        "needs_attention": False,
                        "accepted": True,
                        "rejected": False,
                        "changed": True,
                    }],
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
    assert (capsule.resume_context or {})["route_event_facts"] == [{
        "kind": "resume_route_event",
        "schema_version": RESUME_ROUTE_EVENT_SCHEMA_VERSION,
        "intent": "commit_tactic",
        "tactic": "wp.",
        "tactic_head": "wp",
        "outcome_kind": "accepted",
        "proof_state_effect": "changed",
        "needs_attention": False,
        "accepted": True,
        "rejected": False,
        "changed": True,
    }]


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
                "capsule_version": 2,
                "target": {
                    "file": "eval/examples/PIR.ec",
                    "lemma": "PIR_correct",
                    "include_dir": "easycrypt-src/theories",
                },
                "source": {"commit": "abc123", "session_name": "Tree_0_1"},
                "replay": {
                    "history_file": "history.ec",
                    "tactic_count": 90,
                    "resume_prefix_count": 2,
                    "current_goal_hash": "goal-hash",
                    "goal_identity_required": True,
                },
                "score": {"value": 7.5, "reasons": []},
                "handoff": {
                    "notes": [],
                    "recent_tactics": [],
                    "route_event_facts": [],
                },
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


def test_load_resume_capsule_does_not_recover_state_from_retired_view(tmp_path):
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
                "intent": "commit_tactic",
                "payload": {"tactic": "smt()."},
            },
            "manager_actions": [{
                "action": "tactic commit",
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
            "candidate_moves": {},
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
                "capsule_version": 2,
                "target": {"file": "x.ec", "lemma": "L", "include_dir": ""},
                "source": {"commit": "abc", "session_name": "Tree_0_1"},
                "replay": {
                    "history_file": "history.ec",
                "resume_prefix_count": 3,
                "current_goal_hash": "goal",
                "goal_identity_required": True,
                "current_goal_preview": "Current goal",
                },
                "score": {"value": 1, "reasons": []},
                "handoff": {
                    "notes": [],
                    "recent_tactics": [],
                    "route_event_facts": [],
                },
            }
        ),
        encoding="utf-8",
    )

    capsule = load_resume_capsule(capsule_dir)

    # Current-v2 data is authoritative. Retired view markers and timeline tails
    # are not used to reconstruct omitted route state.
    assert capsule.resume_prefix_count == 3
    context = capsule.resume_context or {}
    assert "route_memory_payload" not in context
    assert context["checkpoint_payload"] == {}
    assert "latest_workspace_view" not in context
    assert context["route_event_facts"] == []


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


def test_resume_capsule_v1_is_retired(tmp_path):
    manifest = tmp_path / "resume.json"
    manifest.write_text(
        json.dumps({
            "kind": "proof_node_resume_capsule",
            "capsule_version": 1,
        }),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unsupported resume capsule version"):
        load_resume_capsule(manifest)


@pytest.mark.parametrize(
    ("missing_owner", "missing_field", "error_field"),
    [
        ("replay", "resume_prefix_count", "replay.resume_prefix_count"),
        ("handoff", "route_event_facts", "handoff.route_event_facts"),
    ],
)
def test_resume_capsule_v2_requires_current_handoff_contract(
    tmp_path,
    missing_owner,
    missing_field,
    error_field,
):
    capsule_dir = tmp_path / missing_field
    capsule_dir.mkdir()
    (capsule_dir / "history.ec").write_text("proc.\n", encoding="utf-8")
    manifest = {
        "kind": "proof_node_resume_capsule",
        "capsule_version": 2,
        "target": {"file": "x.ec", "lemma": "L"},
        "source": {"session_name": "Tree_0"},
        "replay": {
            "history_file": "history.ec",
            "resume_prefix_count": 1,
        },
        "score": {"value": 1.0},
        "lineage": {},
        "handoff": {"notes": [], "route_event_facts": []},
    }
    manifest[missing_owner].pop(missing_field)
    (capsule_dir / "resume.json").write_text(
        json.dumps(manifest),
        encoding="utf-8",
    )
    # Historical tails must not repair an incomplete current-v2 manifest.
    (capsule_dir / "timeline_tail.jsonl").write_text(
        json.dumps({
            "kind": "bootstrap",
            "replay_prefix_count": 1,
            "intent": {
                "intent": "commit_tactic",
                "payload": {"tactic": "proc."},
            },
        })
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=error_field.replace(".", r"\.")):
        load_resume_capsule(capsule_dir)




def test_load_resume_capsule_reports_typed_route_event_schema_error(
    tmp_path,
) -> None:
    capsule_dir = tmp_path / "malformed_route_event"
    capsule_dir.mkdir()
    (capsule_dir / "history.ec").write_text("proc.\n", encoding="utf-8")
    (capsule_dir / "resume.json").write_text(
        json.dumps({
            "kind": "proof_node_resume_capsule",
            "capsule_version": 2,
            "target": {"file": "x.ec", "lemma": "L"},
            "source": {"session_name": "Tree_0"},
            "replay": {
                "history_file": "history.ec",
                "resume_prefix_count": 1,
            },
            "score": {"value": 1.0},
            "lineage": {},
            "handoff": {
                "notes": [],
                "route_event_facts": [{
                    "kind": "resume_route_event",
                    "schema_version": RESUME_ROUTE_EVENT_SCHEMA_VERSION,
                    "intent": 7,
                    "outcome_kind": "unknown",
                    "proof_state_effect": "unknown",
                    "needs_attention": False,
                    "accepted": "true",
                    "rejected": False,
                    "changed": False,
                }],
            },
        }),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match=r"handoff\.route_event_facts\[0\]\.intent must be",
    ):
        load_resume_capsule(capsule_dir)


def test_load_resume_capsule_rejects_legacy_v1_route_event(tmp_path) -> None:
    capsule_dir = tmp_path / "legacy_route_event"
    capsule_dir.mkdir()
    (capsule_dir / "history.ec").write_text("proc.\n", encoding="utf-8")
    (capsule_dir / "resume.json").write_text(
        json.dumps({
            "kind": "proof_node_resume_capsule",
            "capsule_version": 2,
            "target": {"file": "x.ec", "lemma": "L"},
            "source": {"session_name": "Tree_0"},
            "replay": {
                "history_file": "history.ec",
                "resume_prefix_count": 1,
                "current_goal_hash": "goal-hash",
                "proof_status": "open",
                "goal_identity_required": True,
            },
            "score": {"value": 1.0},
            "lineage": {},
            "handoff": {
                "notes": [],
                "route_event_facts": [{
                    "kind": "resume_route_event",
                    "schema_version": 1,
                    "intent": "commit_tactic",
                    "outcome_kind": "accepted",
                    "proof_state_effect": "changed",
                    "needs_attention": False,
                    "accepted": True,
                    "rejected": False,
                    "changed": True,
                }],
            },
        }),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=r"schema_version must be integer 2"):
        load_resume_capsule(capsule_dir)


def test_load_resume_capsule_reads_route_metadata_only_from_lineage(tmp_path):
    capsule_dir = tmp_path / "canonical_lineage"
    capsule_dir.mkdir()
    (capsule_dir / "history.ec").write_text("proc.\n", encoding="utf-8")
    (capsule_dir / "resume.json").write_text(
        json.dumps({
            "kind": "proof_node_resume_capsule",
            "capsule_version": 2,
            "target": {"file": "x.ec", "lemma": "L"},
            "source": {"session_name": "Tree_0"},
            "replay": {
                "history_file": "history.ec",
                "resume_prefix_count": 1,
                "current_goal_hash": "lineage-test-goal-hash",
                "goal_identity_required": True,
            },
            "score": {
                "value": 1.0,
                "route_family": {"family": "retired_score_owner"},
            },
            "lineage": {
                "route_family": {"family": "current_lineage_owner"},
                "resume_diversity": {"diversity_rank": 2},
            },
            "handoff": {
                "notes": [],
                "route_event_facts": [],
                "resume_diversity": {"diversity_rank": 99},
            },
        }),
        encoding="utf-8",
    )

    capsule = load_resume_capsule(capsule_dir)

    assert capsule.route_family == "current_lineage_owner"
    assert capsule.resume_diversity == {"diversity_rank": 2}


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
    _start_session_authority(
        session_a,
        file="eval/examples/ChaChaPoly/chacha_poly.ec",
        lemma="step4_bad1_lbad1",
    )
    _start_session_authority(
        session_b,
        file="eval/examples/ChaChaPoly/chacha_poly.ec",
        lemma="step4_bad1_lbad1",
    )
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
                "capsule_version": 2,
                "target": {
                    "file": "eval/examples/ChaChaPoly/chacha_poly.ec",
                    "lemma": "step4_bad1_lbad1",
                },
                "source": {"session_name": name},
                    "replay": {
                        "history_file": "history.ec",
                        "resume_prefix_count": len([
                            line for line in tactics.splitlines() if line.strip()
                        ]),
                        "current_goal_hash": f"{name}-goal-hash",
                        "goal_identity_required": True,
                    },
                "score": {"value": score},
                "lineage": {"route_family": {"family": family}},
                "handoff": {
                    "notes": [],
                    "recent_tactics": [],
                    "route_event_facts": [],
                },
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
    _start_session_authority(
        session_dir,
        file="eval/examples/PIR.ec",
        lemma="PIR_correct",
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
