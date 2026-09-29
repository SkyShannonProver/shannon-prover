"""Focused contracts for lossless Shannon reverse handback and continuation."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys

import pytest

from experiments.interleaved_shannon import shannon_jobs
from experiments.interleaved_shannon.agent_config import provider_identity_sha256
from experiments.interleaved_shannon.run_shannon import (
    _run_orchestrator_process,
    _wrapper_handback,
)
from experiments.interleaved_shannon.resume_contract import (
    checkpoint_projection,
    directory_content_sha256,
    rebind_resume_capsule,
    select_resume_checkpoint,
)
from workflow.node.proof_node_resume import load_resume_capsule
from workflow.node import safe_stop_finalizer
from workflow.schemas.prover_result import ProverResult


def _capsule(
    root: Path,
    *,
    lemma: str = "L",
    target: str = "old-target.ec",
    history: tuple[str, ...] = ("proc.", "wp."),
    continuation_brief: dict | None = None,
) -> Path:
    root.mkdir(parents=True)
    (root / "history.ec").write_text("\n".join(history) + "\n", encoding="utf-8")
    manifest = root / "resume.json"
    manifest.write_text(
        json.dumps({
            "kind": "proof_node_resume_capsule",
            "capsule_version": 2,
            "target": {
                "file": target,
                "lemma": lemma,
                "include_dir": "easycrypt-src/theories",
            },
            "source": {
                "commit": "abc123",
                "session_name": "Tree_0_0",
            },
            "replay": {
                "history_file": "history.ec",
                "resume_prefix_count": len(history),
                "tactic_count": len(history),
                "current_goal_hash": "a" * 40,
                "proof_status": "open",
                "goal_identity_required": True,
                "current_goal_preview": "Current goal\n----\nx = y",
            },
            "score": {"value": 8.0, "reasons": ["accepted prefix"]},
            "handoff": {
                "notes": [],
                "recent_tactics": [{
                    "turn": 3,
                    "intent": "commit_tactic",
                    "status": "rejected",
                    "tactic": "smt().",
                    "outcome": "remaining arithmetic goal",
                }],
                "route_event_facts": [],
                **(
                    {"continuation_brief": continuation_brief}
                    if continuation_brief is not None
                    else {}
                ),
            },
        }),
        encoding="utf-8",
    )
    return manifest


def _identity() -> dict[str, str]:
    return {
        "agent_backend": "codex",
        "model": "gpt-6-astra",
        "binary": "codex",
        "resolved_path": "/usr/local/bin/codex",
        "binary_sha256": "b" * 64,
        "version": "codex-cli 1",
    }


def test_safe_stop_finalizer_accepts_exact_live_drain_checkpoint(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "run"
    manifest = _capsule(
        run_dir / "resume_capsules" / "Tree_0_0",
        target="target.ec",
    )

    result = safe_stop_finalizer.finalize_safe_stop_checkpoint(
        project_root=tmp_path,
        run_dir=run_dir,
        target_file="target.ec",
        lemma="L",
        include_dir="easycrypt-src/theories",
        committed_prefix=("proc.", "wp."),
        existing_capsules=(str(manifest),),
        trigger="wall_clock_timeout",
    )

    assert result.completed is True
    assert result.method == "drained_live_checkpoint"
    assert result.capsule_paths == (str(manifest.resolve()),)
    audit = json.loads(
        (run_dir / "safe_stop_finalization.json").read_text(encoding="utf-8")
    )
    assert audit["completed"] is True
    assert audit["trigger"] == "wall_clock_timeout"


def test_safe_stop_finalizer_returns_accepted_prefix_without_replay(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    result = safe_stop_finalizer.finalize_safe_stop_checkpoint(
        project_root=tmp_path,
        run_dir=run_dir,
        target_file="target.ec",
        lemma="L",
        include_dir="easycrypt-src/theories",
        committed_prefix=("proc.", "wp."),
        trigger="outer_interrupt",
    )

    assert result.completed is True
    assert result.method == "accepted_prefix_only"
    assert result.tactic_count == 2
    assert result.checkpoint_tactic_count == 0
    assert result.uncheckpointed_tactic_count == 2
    assert result.capsule_paths == ()
    assert (run_dir / "partial_proof_prefix.ec").read_text(
        encoding="utf-8"
    ) == "proc.\nwp.\n"


def test_safe_stop_finalizer_reuses_compatible_earlier_checkpoint(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    manifest = _capsule(
        run_dir / "resume_capsules" / "Tree_0_0",
        target="target.ec",
        history=("proc.", "wp."),
    )

    result = safe_stop_finalizer.finalize_safe_stop_checkpoint(
        project_root=tmp_path,
        run_dir=run_dir,
        target_file="target.ec",
        lemma="L",
        include_dir="easycrypt-src/theories",
        committed_prefix=("proc.", "wp.", "skip."),
        existing_capsules=(str(manifest),),
        trigger="worker_process_exit",
    )

    assert result.completed is True
    assert result.method == "last_confirmed_checkpoint"
    assert result.tactic_count == 3
    assert result.checkpoint_tactic_count == 2
    assert result.uncheckpointed_tactic_count == 1
    assert result.capsule_paths == (str(manifest.resolve()),)
    audit = json.loads(
        (run_dir / "safe_stop_finalization.json").read_text(encoding="utf-8")
    )
    assert audit["completed"] is True
    assert audit["method"] == "last_confirmed_checkpoint"


def _canonical_result_tree(output_root: Path) -> tuple[Path, ProverResult]:
    iteration = output_root / "one" / "iteration_1"
    iteration.mkdir(parents=True)
    manifest = _capsule(iteration / "resume_capsules" / "Tree_0_0")
    result = ProverResult(
        status="incomplete",
        turns=7,
        elapsed_seconds=15.0,
        resume_capsules=[str(manifest)],
    )
    result.save(iteration / "prover_run_result.json")
    (iteration.parent / "summary.json").write_text(json.dumps({
        "final_proved": False,
        "final_prover_result_id": result.result_id,
        "final_prover_result_status": result.status,
    }), encoding="utf-8")
    (iteration / "provider_identity.json").write_text(json.dumps({
        "schema_version": 1,
        "kind": "provider_cli_identity",
        **_identity(),
    }), encoding="utf-8")
    source_manifest = iteration / "source_manifest.json"
    source_manifest.write_text(json.dumps({
        "schema_version": 1,
        "kind": "eval_source_prep",
        "source_contract": "proof_stripped_project",
        "strip_proofs": True,
        "target_lemma": "L",
    }), encoding="utf-8")
    return source_manifest, result


def test_reverse_checkpoint_projects_exact_residual_boundary(tmp_path: Path) -> None:
    manifest = _capsule(tmp_path / "resume_capsules" / "Tree_0_0")
    selected = select_resume_checkpoint(
        [str(manifest)],
        allowed_root=tmp_path / "resume_capsules",
        lemma="L",
    )

    assert selected is not None
    assert selected.prefix_text == "proc.\nwp.\n"
    assert selected.public["tactic_count"] == 2
    assert selected.public["goal"] == {
        "identity": "a" * 40,
        "identity_required": True,
        "proof_status": "open",
        "preview": "Current goal\n----\nx = y",
    }
    assert selected.public["boundary_rejection"]["tactic"] == "smt()."
    assert selected.public["continuation_available"] is True


def test_checkpoint_selection_requires_prefix_compatibility(tmp_path: Path) -> None:
    compatible = _capsule(
        tmp_path / "resume_capsules" / "compatible",
        history=("proc.",),
    )
    _capsule(
        tmp_path / "resume_capsules" / "sibling",
        history=("move=> x.", "wp."),
    )

    selected = select_resume_checkpoint(
        [
            str(tmp_path / "resume_capsules" / "sibling" / "resume.json"),
            str(compatible),
        ],
        allowed_root=tmp_path / "resume_capsules",
        lemma="L",
        accepted_prefix=("proc.", "wp."),
    )

    assert selected is not None
    assert selected.manifest_path == compatible.resolve()


def test_wrapper_preserves_full_prefix_when_checkpoint_lags(
    tmp_path: Path,
) -> None:
    output_root = tmp_path
    source_manifest, result = _canonical_result_tree(output_root)
    iteration = output_root / "one" / "iteration_1"
    full_prefix = "proc.\nwp.\nskip.\n"
    (iteration / "partial_proof_prefix.ec").write_text(
        full_prefix,
        encoding="utf-8",
    )
    (iteration / "partial_proof_prefix.json").write_text(
        json.dumps({
            "kind": "partial_proof_prefix",
            "schema_version": 2,
            "lemma": "L",
            "closed_by_qed": False,
            "tactic_count": 3,
            "byte_count": len(full_prefix.encode("utf-8")),
            "sha256": hashlib.sha256(full_prefix.encode("utf-8")).hexdigest(),
            "source": "manager_session_history_or_resume_capsule",
            "replay_required_before_use": True,
        }),
        encoding="utf-8",
    )

    handback = _wrapper_handback(
        output_root=output_root,
        invocation_id="12345678",
        lemma="L",
        process_exit_code=0,
        wrapper_error="",
        inner_provider="codex",
        inner_model="gpt-6-astra",
        inner_effort="high",
        expected_provider_identity=_identity(),
        invocation_receipt_sha256="b" * 64,
        expected_source_manifest=source_manifest,
    )

    progress = handback["progress"]
    assert progress["accepted_prefix"]["text"] == full_prefix
    assert progress["accepted_prefix"]["tactic_count"] == 3
    assert progress["checkpoint"]["tactic_count"] == 2
    assert progress["uncheckpointed_tail_tactics"] == 1
    assert shannon_jobs._validated_progress(
        progress,
        lemma="L",
        terminal_status="incomplete",
    )["uncheckpointed_tail_tactics"] == 1
    assert handback["status"] == "incomplete"
    assert result.status == "incomplete"


def test_incomplete_handback_recovers_guidance_and_source_breadcrumbs_from_checkpoint(
    tmp_path: Path,
) -> None:
    iteration = tmp_path / "one" / "iteration_1"
    brief = {
        "kind": "proof_continuation_brief",
        "version": 1,
        "origin": "source_navigation",
        "source_breadcrumbs": [{
            "tool": "search",
            "query": "Useful.useful",
            "scope": "libraries",
            "match_count": 1,
            "locations": ["easycrypt-src/theories/Useful.ec:10"],
        }],
        "blockers": ["The rewrite orientation is reversed."],
        "discoveries": ["Useful.useful resolves in the prepared environment."],
    }
    manifest = _capsule(
        iteration / "resume_capsules" / "Tree_0_0",
        continuation_brief=brief,
    )
    result = ProverResult(
        status="incomplete",
        turns=7,
        elapsed_seconds=15.0,
        ec_session_dir="/tmp/.ec_session_prover_tree_9_9",
        report={"blockers": ["wrong sibling-branch blocker"]},
        resume_capsules=[str(manifest)],
    )
    result.save(iteration / "prover_run_result.json")
    source_manifest = iteration / "source_manifest.json"
    source_manifest.write_text(json.dumps({
        "schema_version": 1,
        "kind": "eval_source_prep",
        "source_contract": "proof_stripped_project",
        "strip_proofs": True,
        "target_lemma": "L",
    }), encoding="utf-8")
    (iteration / "provider_identity.json").write_text(json.dumps({
        "schema_version": 1,
        "kind": "provider_cli_identity",
        **_identity(),
    }), encoding="utf-8")
    (iteration.parent / "summary.json").write_text(json.dumps({
        "final_proved": False,
        "final_prover_result_id": result.result_id,
        "final_prover_result_status": result.status,
    }), encoding="utf-8")

    handback = _wrapper_handback(
        output_root=tmp_path,
        invocation_id="12345678",
        lemma="L",
        process_exit_code=0,
        wrapper_error="",
        inner_provider="codex",
        inner_model="gpt-6-astra",
        inner_effort="high",
        expected_provider_identity=_identity(),
        invocation_receipt_sha256="b" * 64,
        expected_source_manifest=source_manifest,
    )
    progress = handback["progress"]
    assert progress["agent_guidance"]["blockers"] == [
        "The rewrite orientation is reversed."
    ]
    assert progress["source_breadcrumbs"]["authority"] == (
        "manager_observed_source_navigation"
    )
    assert progress["source_breadcrumbs"]["items"][0]["locations"] == [
        "easycrypt-src/theories/Useful.ec:10"
    ]


def test_wrapper_and_worker_preserve_checkpoint_without_exposing_private_path(
    tmp_path: Path,
) -> None:
    job_id = "3" * 16
    lane = tmp_path / "lane"
    lane_run = lane / "run"
    output_root = lane_run / "shannon" / "L" / job_id
    source_manifest, result = _canonical_result_tree(output_root)
    identity = _identity()
    handback = _wrapper_handback(
        output_root=output_root,
        invocation_id=job_id,
        lemma="L",
        process_exit_code=0,
        wrapper_error="",
        inner_provider="codex",
        inner_model="gpt-6-astra",
        inner_effort="high",
        expected_provider_identity=identity,
        invocation_receipt_sha256="c" * 64,
        expected_source_manifest=source_manifest,
    )
    (output_root / "wrapper_result.json").write_text(
        json.dumps(handback),
        encoding="utf-8",
    )

    assert handback["status"] == "incomplete"
    assert handback["progress"]["checkpoint"]["goal"]["identity"] == "a" * 40
    assert handback["progress"]["terminal"] == {
        "status": "incomplete",
        "cause": "proof_search_incomplete",
        "message": "",
    }
    assert "resume_capsules" in handback["resume_checkpoint_artifact"]

    record = {
        "schema_version": 1,
        "job_id": job_id,
        "lemma": "L",
        "inner_provider": "codex",
        "inner_model": "gpt-6-astra",
        "inner_effort": "high",
        "invocation_receipt_sha256": "c" * 64,
        "expected_provider_identity": identity,
        "expected_provider_identity_sha256": provider_identity_sha256(identity),
    }
    result_record = shannon_jobs._worker_result(
        record=record,
        run_dir=tmp_path / "outer-run",
        lane=lane,
        lane_run_dir=lane_run,
        wrapper_exit_code=10,
    )
    public = shannon_jobs._public_record(result_record)
    assert public["resume_checkpoint_id"] == (
        handback["progress"]["checkpoint"]["checkpoint_id"]
    )
    assert "resume_checkpoint_artifact" not in public
    assert result_record["resume_checkpoint_artifact"].endswith("resume.json")
    assert result_record["resume_checkpoint_directory_sha256"]
    assert result_record["prover_result_id"] == result.result_id


def test_resume_directory_hash_binds_every_file_and_rejects_symlink(
    tmp_path: Path,
) -> None:
    manifest = _capsule(tmp_path / "capsule")
    before = directory_content_sha256(manifest.parent)
    (manifest.parent / "history.ec").write_text("proc.\n", encoding="utf-8")
    assert directory_content_sha256(manifest.parent) != before

    link = manifest.parent / "bad-link"
    try:
        link.symlink_to(manifest.parent / "history.ec")
    except OSError:
        pytest.skip("symlinks unavailable")
    with pytest.raises(ValueError, match="symlink"):
        directory_content_sha256(manifest.parent)


def test_rebound_resume_still_requires_manager_replay_identity(tmp_path: Path) -> None:
    manifest = _capsule(tmp_path / "capsule")
    loaded = load_resume_capsule(manifest)
    projected, _ = checkpoint_projection(loaded)

    rebind_resume_capsule(
        manifest,
        target_file="new-isolated-target.ec",
        parent_job_id="0" * 16,
        checkpoint_id=str(projected["checkpoint_id"]),
    )

    rebound = load_resume_capsule(manifest)
    assert rebound.target_file == "new-isolated-target.ec"
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert payload["interleaved_continuation"] == {
        "schema_version": 1,
        "parent_job_id": "0" * 16,
        "checkpoint_id": projected["checkpoint_id"],
        "target_rebound_for_fresh_isolated_replay": True,
        "continuation_note_sha256": "",
    }
    assert rebound.current_goal_hash == "a" * 40


def test_resume_continuation_note_is_labelled_untrusted(tmp_path: Path) -> None:
    manifest = _capsule(tmp_path / "capsule")
    projected, _ = checkpoint_projection(load_resume_capsule(manifest))
    note = "The arithmetic branch is now known; try the local helper Hbound."

    rebind_resume_capsule(
        manifest,
        target_file="new-target.ec",
        parent_job_id="5" * 16,
        checkpoint_id=str(projected["checkpoint_id"]),
        continuation_note=note,
    )

    rebound = load_resume_capsule(manifest)
    assert rebound.current_goal_hash == "a" * 40
    assert rebound.replay_prefix == ["proc.", "wp."]
    assert rebound.handoff_notes[-1].endswith(note)
    assert "untrusted strategy guidance" in rebound.handoff_notes[-1]
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert payload["interleaved_continuation"][
        "continuation_note_sha256"
    ] == hashlib.sha256(note.encode("utf-8")).hexdigest()


def test_continuation_note_requires_a_managed_checkpoint() -> None:
    with pytest.raises(
        ValueError,
        match="continuation note requires a managed checkpoint resume",
    ):
        shannon_jobs.submit_job(
            lemma="L",
            timeout_minutes=30,
            handoff_current=False,
            strategy_note=None,
            continuation_note="notes/continue.md",
        )


def test_scheduler_parent_resume_allows_only_suffix_source_changes(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "run"
    job_id = "1" * 16
    job_dir = run_dir / "shannon_jobs" / job_id
    manifest = _capsule(job_dir / "lane_run_artifacts" / "resume")
    projected, _ = checkpoint_projection(load_resume_capsule(manifest))
    contract = {
        "target_sha256": "2" * 64,
        "lemma_prefix_sha256": "3" * 64,
        "proof_body_sha256": "4" * 64,
    }
    shannon_jobs._atomic_json(job_dir / "job.json", {
        "schema_version": 1,
        "job_id": job_id,
        "lemma": "L",
        "status": "incomplete",
        "source_contract": contract,
        "resume_checkpoint_id": projected["checkpoint_id"],
        "resume_checkpoint_artifact": (
            "lane_run_artifacts/resume/resume.json"
        ),
        "resume_checkpoint_directory_sha256": directory_content_sha256(
            manifest.parent
        ),
    })

    parent, selected, parent_run = shannon_jobs._resume_parent_checkpoint(
        run_dir=run_dir,
        parent_job_id=job_id,
        lemma="L",
        source_contract=contract,
    )
    assert parent["job_id"] == job_id
    assert selected == manifest.resolve()
    assert parent_run is None

    suffix_changed = dict(contract)
    suffix_changed["target_sha256"] = "6" * 64
    parent, selected, parent_run = shannon_jobs._resume_parent_checkpoint(
        run_dir=run_dir,
        parent_job_id=job_id,
        lemma="L",
        source_contract=suffix_changed,
    )
    assert parent["job_id"] == job_id
    assert selected == manifest.resolve()
    assert parent_run is None

    changed = dict(contract)
    changed["proof_body_sha256"] = "5" * 64
    with pytest.raises(ValueError, match="resume source changed"):
        shannon_jobs._resume_parent_checkpoint(
            run_dir=run_dir,
            parent_job_id=job_id,
            lemma="L",
            source_contract=changed,
        )

    changed = dict(contract)
    changed["lemma_prefix_sha256"] = "7" * 64
    with pytest.raises(ValueError, match="resume source changed"):
        shannon_jobs._resume_parent_checkpoint(
            run_dir=run_dir,
            parent_job_id=job_id,
            lemma="L",
            source_contract=changed,
        )


def test_continuation_resume_follows_runner_frozen_ancestor_chain(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prior_rel = Path("artifacts/interleaved_shannon/prior")
    middle_rel = Path("artifacts/interleaved_shannon/middle")
    current_rel = Path("artifacts/interleaved_shannon/current")
    prior = tmp_path / prior_rel
    middle = tmp_path / middle_rel
    current = tmp_path / current_rel
    current.mkdir(parents=True)
    source = (
        f"{shannon_jobs.SCRATCHPAD_BEGIN}\n"
        "lemma L : true.\nproof.\n  admit.\nqed.\n"
        f"{shannon_jobs.SCRATCHPAD_END}\n"
        "lemma conclusion : false.\nproof.\n  admit.\nqed.\n"
    )
    job_id = "9" * 16
    job_dir = prior / "shannon_jobs" / job_id
    wrapper_root = (
        job_dir / "lane_run_artifacts" / "shannon" / "L" / job_id
    )
    wrapper_artifact_rel = Path(
        "run/iteration_1/resume_capsules/node/resume.json"
    )
    capsule = _capsule(wrapper_root / wrapper_artifact_rel.parent)
    projected, _ = checkpoint_projection(load_resume_capsule(capsule))
    contract = shannon_jobs._source_contract(source, "L")
    (job_dir / "input").mkdir(parents=True)
    (job_dir / "input" / "target.ec").write_text(source, encoding="utf-8")
    receipt_record = {
        "job_id": job_id,
        "lemma": "L",
        "timeout_minutes": 8,
        "source_commit": "abc123",
        "source_contract": contract,
        "agent_profiles_sha256": "a" * 64,
        "inner_profile_sha256": "b" * 64,
        "inner_agent": {},
        "expected_provider_identity": {},
    }
    receipt = shannon_jobs._invocation_receipt(
        record=receipt_record,
        run_rel=prior_rel,
    )
    receipt_path = (
        job_dir / "lane_run_artifacts" / "job_input" / job_id
        / "invocation_receipt.json"
    )
    shannon_jobs._atomic_json(receipt_path, receipt)
    receipt_sha256 = hashlib.sha256(receipt_path.read_bytes()).hexdigest()
    shannon_jobs._atomic_json(wrapper_root / "wrapper_result.json", {
        "kind": "interleaved_shannon_wrapper_result",
        "invocation_id": job_id,
        "lemma": "L",
        "status": "incomplete",
        "invocation_receipt_sha256": receipt_sha256,
        "resume_checkpoint_artifact": wrapper_artifact_rel.as_posix(),
        "progress": {"checkpoint": {
            "checkpoint_id": projected["checkpoint_id"],
        }},
    })
    shannon_jobs._atomic_json(job_dir / "job.json", {
        "schema_version": 1,
        "job_id": job_id,
        "lemma": "L",
        "status": "incomplete",
        "source_contract": contract,
        "resume_checkpoint_id": projected["checkpoint_id"],
        "resume_checkpoint_artifact": (
            Path("lane_run_artifacts/shannon/L") / job_id
            / wrapper_artifact_rel
        ).as_posix(),
        "resume_checkpoint_directory_sha256": directory_content_sha256(
            capsule.parent
        ),
        "invocation_receipt": receipt,
        "invocation_receipt_sha256": receipt_sha256,
    })
    prior_manifest = prior / "manifest.json"
    prior_manifest.write_text(
        json.dumps({"schema_version": 4, "run_directory": prior_rel.as_posix()}),
        encoding="utf-8",
    )
    prior_events = prior / "outer_agent_events.jsonl"
    prior_events.write_text("{}\n", encoding="utf-8")
    middle.mkdir(parents=True)
    middle_manifest = middle / "manifest.json"
    middle_manifest.write_text(json.dumps({
        "schema_version": 4,
        "continuation": {
            "run_directory": prior_rel.as_posix(),
            "manifest_sha256": hashlib.sha256(
                prior_manifest.read_bytes()
            ).hexdigest(),
            "outer_events_sha256": hashlib.sha256(
                prior_events.read_bytes()
            ).hexdigest(),
        },
    }), encoding="utf-8")
    middle_events = middle / "outer_agent_events.jsonl"
    middle_events.write_text("{}\n", encoding="utf-8")
    current_manifest = current / "manifest.json"
    current_manifest.write_text(json.dumps({
        "schema_version": 4,
        "continuation": {
            "run_directory": middle_rel.as_posix(),
            "manifest_sha256": hashlib.sha256(
                middle_manifest.read_bytes()
            ).hexdigest(),
            "outer_events_sha256": hashlib.sha256(
                middle_events.read_bytes()
            ).hexdigest(),
        },
    }), encoding="utf-8")

    monkeypatch.setattr(shannon_jobs, "ROOT", tmp_path)
    current_source = source.replace("  admit.", "  trivial.", 1)
    current_contract = shannon_jobs._source_contract(current_source, "L")
    assert current_contract["proof_body_sha256"] != contract["proof_body_sha256"]
    options = shannon_jobs.continuation_resume_options(
        middle,
        source_text=current_source,
    )
    assert options == [{
        "job_id": job_id,
        "lemma": "L",
        "checkpoint_id": projected["checkpoint_id"],
        "tactic_count": 2,
    }]
    parent, selected, parent_run = shannon_jobs._resume_parent_checkpoint(
        run_dir=current,
        parent_job_id=job_id,
        lemma="L",
        source_contract=current_contract,
    )
    assert parent["job_id"] == job_id
    assert selected == capsule.resolve()
    assert parent_run == prior_rel

    prior_events.write_text('{"tampered":true}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="audit hash drifted"):
        shannon_jobs._resume_parent_checkpoint(
            run_dir=current,
            parent_job_id=job_id,
            lemma="L",
            source_contract=current_contract,
        )


def test_active_boundary_lease_allows_suffix_but_rejects_proof_edits() -> None:
    source = """op x = 0.
lemma L : true.
proof.
  admit.
qed.
lemma Later : true.
proof. admit. qed.
"""
    job = {
        "job_id": "1" * 16,
        "lemma": "L",
        "status": "running",
        "source_contract": shannon_jobs._source_contract(source, "L"),
    }

    suffix_edit = source.replace("lemma Later : true.", "lemma Later : 0 = 0.")
    assert shannon_jobs._active_boundary_violations([job], suffix_edit) == []

    proof_edit = source.replace("  admit.", "  trivial.", 1)
    violations = shannon_jobs._active_boundary_violations([job], proof_edit)
    assert len(violations) == 1
    assert violations[0]["job_id"] == job["job_id"]
    assert violations[0]["changed"] == ["proof_body"]

    job["status"] = "incomplete"
    assert shannon_jobs._active_boundary_violations([job], proof_edit) == []


def test_scheduler_snapshots_optional_resume_briefing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_rel = Path("artifacts/interleaved_shannon/test")
    run_dir = tmp_path / run_rel
    run_dir.mkdir(parents=True)
    target = tmp_path / "target.ec"
    source = (
        f"{shannon_jobs.SCRATCHPAD_BEGIN}\n"
        "lemma L : true.\nproof.\n  admit.\nqed.\n"
        f"{shannon_jobs.SCRATCHPAD_END}\n"
        "lemma conclusion : false.\nproof.\n  admit.\nqed.\n"
    )
    target.write_text(source, encoding="utf-8")
    parent_id = "6" * 16
    parent_dir = run_dir / "shannon_jobs" / parent_id
    manifest = _capsule(parent_dir / "lane_run_artifacts" / "resume")
    projected, _ = checkpoint_projection(load_resume_capsule(manifest))
    contract = shannon_jobs._source_contract(source, "L")
    shannon_jobs._atomic_json(parent_dir / "job.json", {
        "schema_version": 1,
        "job_id": parent_id,
        "lemma": "L",
        "status": "incomplete",
        "source_contract": contract,
        "resume_checkpoint_id": projected["checkpoint_id"],
        "resume_checkpoint_artifact": "lane_run_artifacts/resume/resume.json",
        "resume_checkpoint_directory_sha256": directory_content_sha256(
            manifest.parent
        ),
    })
    note = run_dir / "continue_L.md"
    note.write_text("Try Hbound at the current residual goal.", encoding="utf-8")

    monkeypatch.setattr(shannon_jobs, "ROOT", tmp_path)
    monkeypatch.setattr(shannon_jobs, "TARGET", "target.ec")
    monkeypatch.setattr(
        shannon_jobs,
        "run_directory",
        lambda: (run_rel, run_dir),
    )
    monkeypatch.setattr(shannon_jobs, "_dispatch_locked", lambda **_kwargs: None)
    monkeypatch.setattr(
        shannon_jobs.subprocess,
        "check_output",
        lambda *_args, **_kwargs: "commit-id\n",
    )
    monkeypatch.setenv("INTERLEAVED_INNER_PROVIDER", "codex")
    monkeypatch.setenv(
        "INTERLEAVED_INNER_PROFILE_SHA256",
        shannon_jobs.agent_profile_sha256(
            shannon_jobs.profile_for("codex")
        ),
    )
    monkeypatch.setenv(
        "INTERLEAVED_INNER_PROVIDER_IDENTITY_JSON",
        json.dumps(_identity()),
    )

    public = shannon_jobs.submit_job(
        lemma="L",
        timeout_minutes=60,
        handoff_current=False,
        strategy_note=None,
        resume_job_id=parent_id,
        continuation_note=str(note.relative_to(tmp_path)),
    )

    assert public["resume_from_job_id"] == parent_id
    assert public["has_continuation_note"] is True
    assert "continuation_note_sha256" not in public
    records = shannon_jobs.private_job_records(run_dir)
    child = next(item for item in records if item["job_id"] != parent_id)
    note_copy = (
        run_dir / "shannon_jobs" / child["job_id"] / "input"
        / "continuation_note.md"
    )
    assert note_copy.read_text(encoding="utf-8") == note.read_text(encoding="utf-8")
    assert child["invocation_receipt"]["has_continuation_note"] is True
    assert child["invocation_receipt"]["continuation_note_sha256"] == (
        hashlib.sha256(note.read_bytes()).hexdigest()
    )


def test_terminal_event_cursor_reports_only_new_transitions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    job_id = "2" * 16
    record = {
        "schema_version": 1,
        "job_id": job_id,
        "lemma": "L",
        "status": "running",
    }
    shannon_jobs._save_job(run_dir, record)
    record["status"] = "incomplete"
    record["finished_at"] = "now"
    shannon_jobs._save_job(run_dir, record)

    monkeypatch.setattr(
        shannon_jobs,
        "run_directory",
        lambda: (Path("artifacts/interleaved_shannon/run"), run_dir),
    )
    monkeypatch.setattr(shannon_jobs, "_dispatch_locked", lambda **_: None)
    first = shannon_jobs.wait_for_terminal_events(
        after_sequence=0,
        timeout_seconds=1,
    )
    assert first["terminal_cursor"] == 1
    assert first["changed"][0]["job_id"] == job_id
    assert first["changed"][0]["terminal_event_sequence"] == 1

    second = shannon_jobs.wait_for_terminal_events(
        after_sequence=1,
        timeout_seconds=1,
    )
    assert second == {
        "schema_version": 1,
        "terminal_cursor": 1,
        "changed": [],
        "timed_out": True,
    }


def test_cancelling_does_not_publish_terminal_event_before_checkpoint(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    job_id = "4" * 16
    record = {
        "schema_version": 1,
        "job_id": job_id,
        "lemma": "L",
        "status": "running",
    }
    shannon_jobs._save_job(run_dir, record)
    record["status"] = "cancelling"
    shannon_jobs._save_job(run_dir, record)

    assert shannon_jobs._latest_terminal_sequence(run_dir) == 0

    record["status"] = "cancelled"
    record["progress"] = {
        "schema_version": 2,
        "kind": "interleaved_shannon_progress_capsule",
        "lemma": "L",
        "turns": 3,
        "elapsed_seconds": 4.0,
        "next_actions": ["redesign_boundary"],
        "terminal": {
            "status": "cancelled",
            "cause": "outer_cancelled",
            "message": "cancelled by outer job controller",
        },
    }
    shannon_jobs._save_job(run_dir, record)

    assert shannon_jobs._latest_terminal_sequence(run_dir) == 1
    public = shannon_jobs._public_record(record)
    assert public["status"] == "cancelled"
    assert public["progress"]["terminal"]["cause"] == "outer_cancelled"


def test_ordinary_incomplete_may_return_accepted_prefix_without_checkpoint() -> None:
    prefix = "move=> x.\n"
    progress = {
        "schema_version": 2,
        "kind": "interleaved_shannon_progress_capsule",
        "lemma": "L",
        "turns": 1,
        "elapsed_seconds": 1.0,
        "accepted_prefix": {
            "tactic_count": 1,
            "sha256": hashlib.sha256(prefix.encode("utf-8")).hexdigest(),
            "byte_count": len(prefix.encode("utf-8")),
            "authority": "manager_committed_history_reporting_artifact",
            "replay_required_before_use": True,
            "text": prefix,
        },
        "next_actions": ["replay_prefix_in_outer"],
        "terminal": {
            "status": "incomplete",
            "cause": "proof_search_incomplete",
            "message": "",
        },
    }

    assert shannon_jobs._validated_progress(
        progress,
        lemma="L",
        terminal_status="incomplete",
    )["accepted_prefix"]["tactic_count"] == 1


def test_uncheckpointed_tail_requires_a_checkpoint() -> None:
    prefix = "move=> x.\n"
    progress = {
        "schema_version": 2,
        "kind": "interleaved_shannon_progress_capsule",
        "lemma": "L",
        "turns": 1,
        "elapsed_seconds": 1.0,
        "accepted_prefix": {
            "tactic_count": 1,
            "sha256": hashlib.sha256(prefix.encode("utf-8")).hexdigest(),
            "byte_count": len(prefix.encode("utf-8")),
            "authority": "manager_committed_history_reporting_artifact",
            "replay_required_before_use": True,
            "text": prefix,
        },
        "uncheckpointed_tail_tactics": 1,
        "next_actions": ["replay_prefix_in_outer"],
        "terminal": {
            "status": "incomplete",
            "cause": "proof_search_incomplete",
            "message": "",
        },
    }

    with pytest.raises(
        ValueError,
        match="uncheckpointed tail requires a managed checkpoint",
    ):
        shannon_jobs._validated_progress(
            progress,
            lemma="L",
            terminal_status="incomplete",
        )


def test_cooperative_stop_reaches_child_checkpoint_boundary(tmp_path: Path) -> None:
    ready = tmp_path / "ready"
    checkpoint = tmp_path / "checkpoint"
    program = (
        "import pathlib,signal,time\n"
        f"ready=pathlib.Path({str(ready)!r})\n"
        f"checkpoint=pathlib.Path({str(checkpoint)!r})\n"
        "def stop(_signum, _frame):\n"
        "    checkpoint.write_text('preserved', encoding='utf-8')\n"
        "    raise SystemExit(17)\n"
        "signal.signal(signal.SIGINT, stop)\n"
        "ready.write_text('ready', encoding='utf-8')\n"
        "while True: time.sleep(0.05)\n"
    )
    exit_code, error = _run_orchestrator_process(
        [sys.executable, "-c", program],
        environment=dict(os.environ),
        interruption_requested=ready.exists,
        grace_seconds=2.0,
    )

    assert exit_code == 17
    assert error == ""
    assert checkpoint.read_text(encoding="utf-8") == "preserved"
