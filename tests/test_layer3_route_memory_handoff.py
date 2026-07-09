"""Layer-3 crash respawn must hand the dead node's route memory to the child.

Regression for the 2026-06-11 upto_X1_X2 incident: Tree-0.0 rewound a
97-tactic proof, the manager saved the discarded suffix as verifier-checked
replay chunks, the worker crashed, and the respawned Tree-0.0.r0 re-derived
~90 tactics manually because:

1. the capsule builder derived the node slug from the SESSION DIR name
   (``Tree_0_0``) while the route-memory file is keyed by NODE ID
   (``Tree-0.0_route_replay_memory.json``), so the capsule shipped without
   the payload;
2. the child's ``ProofMemoryManager`` (node ``Tree-0.0.r0``) only ever looked
   for a file keyed to its OWN slug;
3. nothing in the respawn prompt told the agent the chunks existed.

Root-cause writeup: docs/reports/insights/resume_capsule_90_to_24_rootcause.md.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from workflow.proof_management.memory_store import ProofMemoryManager
from workflow.proof_node_resume import (
    _node_slug_aliases,
    _route_memory_payload_for_node,
    create_resume_capsules,
    load_resume_capsule,
)


def _history_hash(tactics: list[str]) -> str:
    return hashlib.sha1("\n".join(tactics).encode("utf-8")).hexdigest()


def _confirmation_id(*parts: object) -> str:
    return hashlib.sha1(
        "|".join(str(part) for part in parts).encode("utf-8")
    ).hexdigest()[:12]


_HISTORY = [
    "proc.",
    "seq 2 2 : (={glob X}).",
    "wp.",
    "call (_: true).",
    "auto.",
    "smt().",
]


def _memory_manager(run_dir: Path, node_id: str) -> ProofMemoryManager:
    return ProofMemoryManager(
        node_id=node_id,
        run_dir=run_dir,
        history_hash=_history_hash,
        confirmation_id=_confirmation_id,
    )


def _write_dead_node_route_memory(run_dir: Path, node_id: str = "Tree-0.0") -> dict:
    """Mint a REAL route-memory fixture the way the live manager writes it."""
    manager = _memory_manager(run_dir, node_id)
    memory = manager.record_checkpoint_rewind(
        tactics=_HISTORY,
        checkpoint_id="cp_root_byequiv",
        tactic_index=2,
        state_version=11,
        rewind_note={"hypothesis": "root byequiv post too weak"},
    )
    assert memory, "fixture rewind must produce a route memory"
    path = run_dir / "route_memory" / "Tree-0.0_route_replay_memory.json"
    assert path.is_file(), "fixture file must be keyed by the DEAD node id"
    return memory


# ---------------------------------------------------------------------------
# 1. Capsule-side discoverability: session-derived slug finds the node-id file
# ---------------------------------------------------------------------------


def test_node_slug_aliases_bridge_session_and_node_id_spellings() -> None:
    assert "Tree-0.0" in _node_slug_aliases("Tree_0_0")
    assert "Tree-0.0.r0" in _node_slug_aliases("Tree_0_0_r0")
    # The literal spelling always stays first.
    assert _node_slug_aliases("Tree-0.0")[0] == "Tree-0.0"
    assert _node_slug_aliases("") == []


def test_route_memory_payload_found_for_session_derived_slug(tmp_path: Path) -> None:
    _write_dead_node_route_memory(tmp_path)
    # `_node_slug_from_session_dir(.ec_session_prover_tree_0_0)` yields
    # "Tree_0_0"; the lookup must still find Tree-0.0_route_replay_memory.json.
    payload = _route_memory_payload_for_node(tmp_path, "Tree_0_0")
    assert payload.get("kind") == "route_replay_memory"
    assert payload.get("route_memories")


def test_resume_capsule_carries_dead_node_route_memory(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    _write_dead_node_route_memory(run_dir)
    session_dir = tmp_path / ".ec_session_prover_tree_0_0"
    session_dir.mkdir()
    (session_dir / "history.ec").write_text(
        "\n".join(_HISTORY[:1]) + "\n", encoding="utf-8"
    )

    created = create_resume_capsules(
        project_root=tmp_path,
        run_dir=run_dir,
        target_file="eval/X.ec",
        lemma="upto_X1_X2",
        session_dirs=[session_dir],
        output_dir=run_dir / "capsules",
    )
    assert created, "capsule must be minted from the fixture session dir"

    capsule = load_resume_capsule(created[0])
    payload = capsule.resume_context.get("route_memory_payload")
    assert isinstance(payload, dict) and payload.get("route_memories"), (
        "Layer-3 capsule lost the dead node's route memory: the respawned "
        "child would silently re-derive the saved suffix by hand"
    )


# ---------------------------------------------------------------------------
# 2. Child-side discoverability: Tree-0.0.r0 finds the Tree-0.0 file
# ---------------------------------------------------------------------------


def test_respawn_child_falls_back_to_dead_node_route_memory(tmp_path: Path) -> None:
    saved = _write_dead_node_route_memory(tmp_path)
    child = _memory_manager(tmp_path, "Tree-0.0.r0")
    assert child.route_memories, (
        "respawn child must inherit the dead parent's route memory file"
    )
    assert child.route_memories[0].memory_id == saved["memory_id"]
    # The inherited chunks are consumable from the kept prefix.
    kept_prefix = _HISTORY[:1]
    surface = child.route_replay_memory_surface(kept_prefix)
    chunks = surface["items"][0]["available_chunks"]
    assert chunks and chunks[0]["submit_commit"]["intent"] == (
        "commit_replay_suffix_chunk"
    )


def test_non_respawn_node_does_not_inherit_sibling_files(tmp_path: Path) -> None:
    _write_dead_node_route_memory(tmp_path)
    fresh = _memory_manager(tmp_path, "Tree-0.1")
    assert not fresh.route_memories


def test_seed_resume_payload_rekeys_route_memory_to_child(tmp_path: Path) -> None:
    dead_run = tmp_path / "dead"
    dead_run.mkdir()
    _write_dead_node_route_memory(dead_run)
    payload = json.loads(
        (dead_run / "route_memory" / "Tree-0.0_route_replay_memory.json")
        .read_text(encoding="utf-8")
    )

    child_run = tmp_path / "child"
    child_run.mkdir()
    child = _memory_manager(child_run, "Tree-0.0.r0")
    child.seed_resume_payload(payload)
    assert child.route_memories
    rekeyed = child_run / "route_memory" / "Tree-0.0.r0_route_replay_memory.json"
    assert rekeyed.is_file(), (
        "adopted route memory must be re-keyed to the live child so the NEXT "
        "capsule mint / respawn can find it"
    )


# ---------------------------------------------------------------------------
# 3. Prompt surfacing: the respawn prompt names the chunks and the intent
# ---------------------------------------------------------------------------


def _child_prompt_for_view(view: dict) -> str:
    from workflow.agents.prover_prompt import _build_child_prover_prompt

    return _build_child_prover_prompt(
        "eval/X.ec",
        "upto_X1_X2",
        "eval",
        "prover_tree_0_0_r0",
        replay_prefix=list(_HISTORY[:1]),
        negative_signal=[],
        managed_session={"workspace_view": view},
    )


def test_child_prompt_surfaces_unconsumed_route_chunks(tmp_path: Path) -> None:
    _write_dead_node_route_memory(tmp_path)
    child = _memory_manager(tmp_path, "Tree-0.0.r0")
    surface = child.route_replay_memory_surface(_HISTORY[:1])
    chunk = surface["items"][0]["available_chunks"][0]

    prompt = _child_prompt_for_view({"route_replay_memory": surface})
    assert "Saved route memory" in prompt
    assert "commit_replay_suffix_chunk" in prompt
    # Probe-free direction (2fd6ae726): the banner recommends commit-only
    # chunk consumption; the probe variant is no longer advertised here.
    assert "probe_replay_suffix_chunk" not in prompt
    assert str(chunk["chunk_id"]) in prompt
    # Frontier: the first unconsumed tactic is named so the agent can align.
    assert str(chunk["first_tactic"]) in prompt


def test_child_prompt_silent_without_replayable_chunks() -> None:
    prompt = _child_prompt_for_view({})
    assert "Saved route memory" not in prompt
    assert "commit_replay_suffix_chunk" not in prompt
    # Legacy navigation-only surfaces (no tactic payload -> no submit_commit)
    # must not trigger the banner either.
    legacy_view = {
        "route_replay_memory": {
            "kind": "route_replay_memory",
            "state": "legacy_resume_route_memory",
            "items": [{"available_chunks": [{"chunk_id": "rch_x", "kind": "k"}]}],
        }
    }
    prompt = _child_prompt_for_view(legacy_view)
    assert "Saved route memory" not in prompt
