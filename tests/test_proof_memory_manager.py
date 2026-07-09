from __future__ import annotations

import hashlib
import json
from pathlib import Path

from workflow.proof_management.memory_store import ProofMemoryManager
from workflow.proof_management.repair_notes import normalize_rewind_note


def _history_hash(tactics: list[str]) -> str:
    return hashlib.sha1("\n".join(tactics).encode("utf-8")).hexdigest()


def _confirmation_id(*parts: object) -> str:
    return hashlib.sha1("|".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:12]


def test_proof_memory_manager_records_checkpoint_rewind(tmp_path: Path) -> None:
    manager = ProofMemoryManager(
        node_id="Tree-unit",
        run_dir=tmp_path,
        history_hash=_history_hash,
        confirmation_id=_confirmation_id,
    )

    memory = manager.record_checkpoint_rewind(
        tactics=["proc.", "seq 1 1 : P.", "wp."],
        checkpoint_id="cp_2",
        tactic_index=2,
        state_version=7,
        rewind_note={
            "hypothesis": "boundary_too_weak",
            "intended_repair": "strengthen seq midpoint",
            "negative_memory": {
                "scope": "call_invariant",
                "avoid_pattern": "={glob A}",
                "reason": "abstract adversary call can write A",
                "applies_when": "inside abstract adversary call invariant",
            },
        },
    )

    assert memory["from_tactic_index"] == 2
    assert memory["kept_prefix_end"] == 1
    assert memory["discarded_suffix"] == ["seq 1 1 : P.", "wp."]
    assert memory["repair_episode_id"].startswith("repair_")
    assert memory["discarded_pieces"][0]["replay_class"] == "boundary_sensitive"
    assert memory["discarded_pieces"][1]["replay_class"] == "structural_replayable"
    assert memory["stale_piece_ids"] == [memory["discarded_pieces"][0]["piece_id"]]
    assert memory["negative_memory_ids"]
    assert memory["rewind_note"]["schema_version"] == 1
    assert memory["rewind_note"]["hypothesis"] == "boundary_too_weak"
    assert memory["rewind_note"]["negative_memories"][0]["avoid_pattern"] == (
        "={glob A}"
    )
    assert [item.to_dict() for item in manager.route_memories] == [memory]
    assert manager.route_memories[0].memory_id == memory["memory_id"]
    assert manager.route_memory_snapshot().route_memories[0].memory_id == memory["memory_id"]
    assert manager.negative_memories[0].avoid_pattern == "={glob A}"
    assert manager.repair_episodes[0].rewind_note["intended_repair"] == (
        "strengthen seq midpoint"
    )

    memory_file = tmp_path / "route_memory" / "Tree-unit_route_replay_memory.json"
    payload = json.loads(memory_file.read_text(encoding="utf-8"))
    assert payload["kind"] == "route_replay_memory"
    assert payload["schema_version"] == 2
    assert payload["route_memory_snapshot"]["kind"] == "route_memory_snapshot"
    assert payload["route_memories"][0]["memory_id"] == memory["memory_id"]
    assert payload["negative_memories"][0]["avoid_pattern"] == "={glob A}"
    assert payload["repair_episodes"][0]["episode_id"] == memory["repair_episode_id"]
    assert "memories" not in payload

    reloaded = ProofMemoryManager(
        node_id="Tree-unit",
        run_dir=tmp_path,
        history_hash=_history_hash,
        confirmation_id=_confirmation_id,
    )
    assert reloaded.route_memories[0].memory_id == memory["memory_id"]
    assert reloaded.repair_episodes[0].episode_id == memory["repair_episode_id"]
    assert reloaded.repair_episodes[0].discarded_pieces[0].tactic == (
        "seq 1 1 : P."
    )
    assert reloaded.negative_memories[0].reason == (
        "abstract adversary call can write A"
    )


def test_rewind_note_normalization_preserves_resume_signal() -> None:
    note = normalize_rewind_note({
        "hypothesis": ["call boundary", "lost frame"],
        "boundary_kind": "call_invariant",
        "missing_fact": "={glob RO}",
        "repair": "strengthen call invariant",
        "reuse_expectation": "structural suffix should replay",
        "avoid": {"pattern": "={glob A}", "reason": "adversary writes it"},
        "custom_probe_id": "probe_17",
    }).to_dict()

    assert note["hypothesis"] == "call boundary; lost frame"
    assert note["broken_boundary_kind"] == "call_invariant"
    assert note["missing_facts"] == ["={glob RO}"]
    assert note["intended_repair"] == "strengthen call invariant"
    assert note["negative_memories"][0]["avoid_pattern"] == "={glob A}"
    assert note["extra"] == {"custom_probe_id": "probe_17"}


def test_proof_memory_manager_surfaces_route_replay_memory() -> None:
    manager = ProofMemoryManager(
        node_id="Tree-unit",
        history_hash=_history_hash,
        confirmation_id=_confirmation_id,
    )
    manager.record_checkpoint_rewind(
        tactics=["proc.", "seq 1 1 : P.", "wp.", "auto."],
        checkpoint_id="cp_2",
        tactic_index=2,
        state_version=7,
        rewind_note={
            "hypothesis": "seq midpoint too weak",
            "avoid_patterns": ["old midpoint without frame equality"],
        },
    )

    surface = manager.route_replay_memory_surface(["proc."])

    assert surface["kind"] == "route_replay_memory"
    assert surface["repair_episodes"][0]["episode_id"].startswith("repair_")
    route = surface["items"][0]
    assert route["available_chunks"][0]["submit_probe"]["intent"] == (
        "probe_replay_suffix_chunk"
    )
    briefing = manager.lineage_briefing_surface(["proc."])
    assert briefing["negative_memories"][0]["avoid_pattern"] == (
        "old midpoint without frame equality"
    )


def test_proof_memory_manager_surfaces_verified_route_options() -> None:
    manager = ProofMemoryManager(
        node_id="Tree-unit",
        history_hash=_history_hash,
        confirmation_id=_confirmation_id,
    )
    manager.seed_verified_route_options([{
        "kind": "verified_route_option",
        "schema_version": 1,
        "option_id": "bridge_options.abc",
        "topic": "bridge_options",
        "producer": "deterministic_pr_bridge_compiler",
        "semantic_objective": "normalize then bridge",
        "confidence": "verified",
        "submit": {
            "intent": "commit_tactic",
            "payload": {"tactic": "rewrite -bridge."},
        },
        "tactic_chain": ["rewrite -bridge."],
        "bindings": {"namespace": "OpCCinit"},
        "evidence_refs": ["probe.bridge.0"],
        "verification_evidence": [{
            "id": "probe.bridge.0",
            "accepted": True,
        }],
    }])

    surface = manager.lineage_briefing_surface([])

    assert surface["kind"] == "lineage_briefing"
    option = surface["verified_route_options"][0]
    assert option["option_id"] == "bridge_options.abc"
    assert option["tactic_head"] == "rewrite"
    assert option["bindings"] == {"namespace": "OpCCinit"}


def test_proof_memory_manager_surfaces_lineage_briefing() -> None:
    manager = ProofMemoryManager(
        node_id="Tree-unit",
        history_hash=_history_hash,
        confirmation_id=_confirmation_id,
    )
    manager.record_checkpoint_rewind(
        tactics=["proc.", "call (_: old_inv).", "wp."],
        checkpoint_id="cp_call",
        tactic_index=2,
        state_version=7,
        rewind_note={
            "hypothesis": "call boundary too weak",
            "broken_boundary_kind": "call_invariant",
            "missing_facts": ["={glob RO}"],
            "reuse_expectation": "wp tail should replay",
            "avoid": "={glob A}",
        },
    )

    briefing = manager.lineage_briefing_surface(["proc."])

    assert briefing["kind"] == "lineage_briefing"
    assert briefing["node_id"] == "Tree-unit"
    assert briefing["open_repair_episode"]["from_checkpoint_id"] == "cp_call"
    assert briefing["open_repair_episode"]["rewind_note"]["hypothesis"] == (
        "call boundary too weak"
    )
    route = briefing["route_memories"][0]
    assert route["discarded_tactic_count"] == 2
    assert route["rewind_note"]["reuse_expectation"] == "wp tail should replay"
    assert briefing["negative_memories"][0]["avoid_pattern"] == "={glob A}"


def test_proof_memory_manager_extends_latest_discarded_suffix() -> None:
    manager = ProofMemoryManager(
        node_id="Tree-unit",
        history_hash=_history_hash,
        confirmation_id=_confirmation_id,
    )
    tactics = ["a.", "b.", "c."]
    first = manager.record_checkpoint_rewind(
        tactics=tactics,
        checkpoint_id="cp_3",
        tactic_index=3,
        state_version=1,
    )

    second = manager.record_checkpoint_rewind(
        tactics=tactics[:2],
        checkpoint_id="cp_2",
        tactic_index=2,
        state_version=2,
    )

    assert first["discarded_suffix"] == ["c."]
    assert second["discarded_suffix"] == ["b.", "c."]


def test_proof_memory_manager_surfaces_and_resolves_replay_chunks() -> None:
    manager = ProofMemoryManager(
        node_id="Tree-unit",
        history_hash=_history_hash,
        confirmation_id=_confirmation_id,
    )
    old_tactics = [
        "byequiv=>//.",
        "proc.",
        "seq 5 3 : (old_midpoint).",
        "sp 4 2.",
        "call (_: old_inv).",
        "wp.",
    ]
    manager.record_checkpoint_rewind(
        tactics=old_tactics,
        checkpoint_id="cp_old",
        tactic_index=3,
        state_version=1,
    )
    current_tactics = [
        "byequiv=>//.",
        "proc.",
        "seq 5 3 : (new_midpoint).",
        "sp 4 2.",
    ]

    surface = manager.route_replay_memory_surface(current_tactics)
    item = surface["items"][0]
    assert item["progress"]["rewrite_anchor"]["relation"] == (
        "same_structural_boundary_head_rewritten"
    )
    chunk = item["available_chunks"][0]
    assert chunk["first_tactic"] == "call (_: old_inv)."
    assert chunk["submit_probe"]["intent"] == "probe_replay_suffix_chunk"

    resolved = manager.resolve_replay_suffix_chunk(
        current_tactics,
        chunk["chunk_id"],
    )
    assert resolved["tactics"] == ["call (_: old_inv).", "wp."]


def test_proof_memory_manager_tracks_verified_replay_chunks_by_prefix() -> None:
    manager = ProofMemoryManager(
        node_id="Tree-unit",
        history_hash=_history_hash,
        confirmation_id=_confirmation_id,
    )
    current_tactics = ["proc.", "seq 1 1 : P."]
    chunk = {
        "chunk_id": "rch_unit_1_3",
        "memory_id": "route_unit",
        "tactics": ["wp.", "auto."],
    }

    assert not manager.replay_chunk_is_verified(
        current_tactics=current_tactics,
        chunk=chunk,
    )

    manager.remember_verified_replay_chunk(
        current_tactics=current_tactics,
        chunk=chunk,
    )

    assert manager.replay_chunk_is_verified(
        current_tactics=current_tactics,
        chunk=chunk,
    )
    assert not manager.replay_chunk_is_verified(
        current_tactics=[*current_tactics, "sp."],
        chunk=chunk,
    )
    assert not manager.replay_chunk_is_verified(
        current_tactics=current_tactics,
        chunk={**chunk, "tactics": ["wp."]},
    )


def test_proof_memory_manager_renders_replay_chunk_observations() -> None:
    manager = ProofMemoryManager(
        node_id="Tree-unit",
        history_hash=_history_hash,
        confirmation_id=_confirmation_id,
    )
    chunk = {
        "chunk_id": "rch_unit_1_3",
        "memory_id": "route_unit",
        "kind": "frontier_surgery_suffix",
        "first_tactic": "wp.",
        "last_tactic": "auto.",
        "tactic_count": 2,
        "tactics": ["wp.", "auto."],
    }

    probe = manager.replay_suffix_probe_observation(
        intent="probe_replay_suffix_chunk",
        payload={"chunk_id": chunk["chunk_id"]},
        chunk=chunk,
        result={"ok": True, "accepted_count": 2},
    )
    blocked = manager.replay_suffix_commit_blocked_observation(
        intent="commit_replay_suffix_chunk",
        payload={"chunk_id": chunk["chunk_id"]},
        chunk=chunk,
        result={
            "ok": False,
            "accepted_count": 1,
            "failed_tactic": "auto.",
            "failure_kind": "backend_error",
        },
    )
    committed = manager.replay_suffix_commit_observation(
        intent="commit_replay_suffix_chunk",
        payload={"chunk_id": chunk["chunk_id"]},
        chunk=chunk,
    )

    assert probe["kind"] == "replay_suffix_probe"
    assert probe["status"] == "accepted"
    assert probe["chunk"]["submit_commit"]["intent"] == "commit_replay_suffix_chunk"
    assert blocked["kind"] == "replay_suffix_commit_blocked"
    assert blocked["failed_tactic"] == "auto."
    assert committed["kind"] == "replay_suffix_commit"
    assert committed["committed_tactic_count"] == 2
