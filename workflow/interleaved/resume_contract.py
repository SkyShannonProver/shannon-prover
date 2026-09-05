"""Bounded public projection and private binding for Shannon continuation.

The proof-node runtime already owns durable resume capsules.  Interleaved
Shannon must not expose their backend paths or invent a second proof-state
format.  This module validates those manager-owned capsules, projects the
small public checkpoint needed by the outer agent, and hashes the private
directory copied by the scheduler for a later continuation job.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from workflow.node.proof_node_resume import (
    ProofNodeResumeCapsule,
    load_resume_capsule,
)


CHECKPOINT_KIND = "interleaved_shannon_managed_checkpoint"
CHECKPOINT_SCHEMA_VERSION = 1
GOAL_PREVIEW_MAX_CHARS = 6000
CONTINUATION_NOTE_MAX_CHARS = 8000


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical_json_sha256(value: dict[str, object]) -> str:
    return _sha256_bytes(
        json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    )


def directory_content_sha256(root: Path) -> str:
    """Hash every regular file in a scheduler-owned capsule directory."""

    root = root.resolve()
    if not root.is_dir():
        raise ValueError("resume capsule root is not a directory")
    entries: list[dict[str, object]] = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError("resume capsule directory contains a symlink")
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        raw = path.read_bytes()
        entries.append({
            "path": relative,
            "byte_count": len(raw),
            "sha256": _sha256_bytes(raw),
        })
    if not entries or not (root / "resume.json").is_file():
        raise ValueError("resume capsule directory is incomplete")
    return _canonical_json_sha256({"files": entries})


def _prefix_text(capsule: ProofNodeResumeCapsule) -> str:
    if not capsule.replay_prefix:
        return ""
    return "\n".join(capsule.replay_prefix) + "\n"


def _boundary_rejection(capsule: ProofNodeResumeCapsule) -> dict[str, object]:
    for item in reversed(capsule.recent_tactics):
        status = str(item.get("status") or "")
        if status not in {"rejected", "no_progress"}:
            continue
        result: dict[str, object] = {
            "status": status,
            "intent": str(item.get("intent") or ""),
            "tactic": str(item.get("tactic") or "")[:2000],
        }
        outcome = str(item.get("outcome") or "").strip()
        if outcome:
            result["outcome"] = outcome[:2000]
        return result
    return {}


def checkpoint_projection(
    capsule: ProofNodeResumeCapsule,
) -> tuple[dict[str, object], str]:
    """Return a bounded public checkpoint and its exact accepted prefix."""

    prefix = _prefix_text(capsule)
    if not prefix or capsule.tactic_count <= 0:
        raise ValueError("resume capsule has no accepted prefix")
    if not capsule.goal_identity_required or not capsule.current_goal_hash:
        raise ValueError("resume capsule does not describe an open residual goal")

    checkpoint: dict[str, object] = {
        "schema_version": CHECKPOINT_SCHEMA_VERSION,
        "kind": CHECKPOINT_KIND,
        "authority": "manager_owned_resume_capsule",
        "tactic_count": capsule.tactic_count,
        "accepted_prefix_sha256": _sha256_bytes(prefix.encode("utf-8")),
        "goal": {
            "identity": capsule.current_goal_hash,
            "identity_required": True,
            "proof_status": capsule.proof_status,
            "preview": capsule.current_goal_preview[:GOAL_PREVIEW_MAX_CHARS],
        },
        "continuation_available": True,
    }
    rejection = _boundary_rejection(capsule)
    if rejection:
        checkpoint["boundary_rejection"] = rejection
    checkpoint["checkpoint_id"] = _canonical_json_sha256(checkpoint)
    return checkpoint, prefix


@dataclass(frozen=True)
class SelectedResumeCheckpoint:
    manifest_path: Path
    capsule: ProofNodeResumeCapsule
    public: dict[str, object]
    prefix_text: str


def select_resume_checkpoint(
    paths: Iterable[str],
    *,
    allowed_root: Path,
    lemma: str,
    accepted_prefix: Iterable[str] | None = None,
) -> SelectedResumeCheckpoint | None:
    """Choose the longest compatible open checkpoint within one result.

    When a terminal accepted spine is supplied, a checkpoint may lag it but
    must describe an exact prefix of that spine.  This prevents a same-length
    sibling branch from being paired with unrelated reporting progress.
    """

    allowed_root = allowed_root.resolve()
    accepted = (
        tuple(
            str(item).strip()
            for item in accepted_prefix
            if isinstance(item, str) and item.strip()
        )
        if accepted_prefix is not None
        else None
    )
    candidates: list[SelectedResumeCheckpoint] = []
    for raw in paths:
        path = Path(str(raw)).resolve()
        if not path.is_file() or not path.is_relative_to(allowed_root):
            continue
        try:
            capsule = load_resume_capsule(path)
            if capsule.lemma != lemma:
                continue
            if accepted is not None and (
                not capsule.replay_prefix
                or tuple(capsule.replay_prefix)
                != accepted[: len(capsule.replay_prefix)]
            ):
                continue
            public, prefix = checkpoint_projection(capsule)
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        candidates.append(SelectedResumeCheckpoint(
            manifest_path=path,
            capsule=capsule,
            public=public,
            prefix_text=prefix,
        ))
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda item: (item.capsule.tactic_count, item.capsule.score),
    )


def rebind_resume_capsule(
    manifest_path: Path,
    *,
    target_file: str,
    parent_job_id: str,
    checkpoint_id: str,
    continuation_note: str = "",
) -> None:
    """Rebind a copied capsule to the new isolated target before replay.

    The scheduler has already required an identical selected-lemma boundary;
    declarations after that lemma may differ.  The manager still replays the
    prefix against the new isolated source and verifies the recorded goal
    identity, so this rewrite cannot turn relevant source drift into accepted
    proof state.
    """

    capsule = load_resume_capsule(manifest_path)
    public, _ = checkpoint_projection(capsule)
    if public.get("checkpoint_id") != checkpoint_id:
        raise ValueError("resume checkpoint identity mismatch")
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("resume capsule manifest must be an object")
    target = data.get("target")
    if not isinstance(target, dict):
        raise ValueError("resume capsule target is missing")
    target["file"] = target_file
    data["target"] = target
    note = continuation_note.strip()
    if len(note) > CONTINUATION_NOTE_MAX_CHARS:
        raise ValueError("continuation note exceeds its character limit")
    if note:
        handoff = data.get("handoff")
        if not isinstance(handoff, dict):
            raise ValueError("resume capsule handoff is missing")
        notes = handoff.get("notes")
        if notes is None:
            notes = []
        if not isinstance(notes, list) or any(
            not isinstance(item, str) for item in notes
        ):
            raise ValueError("resume capsule handoff notes are invalid")
        notes.append(
            "Outer continuation briefing (untrusted strategy guidance; "
            "the manager-owned checkpoint remains authoritative):\n" + note
        )
        handoff["notes"] = notes
        data["handoff"] = handoff
    data["interleaved_continuation"] = {
        "schema_version": 1,
        "parent_job_id": parent_job_id,
        "checkpoint_id": checkpoint_id,
        "target_rebound_for_fresh_isolated_replay": True,
        "continuation_note_sha256": (
            _sha256_bytes(note.encode("utf-8")) if note else ""
        ),
    }
    manifest_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


__all__ = [
    "CHECKPOINT_KIND",
    "CHECKPOINT_SCHEMA_VERSION",
    "CONTINUATION_NOTE_MAX_CHARS",
    "SelectedResumeCheckpoint",
    "checkpoint_projection",
    "directory_content_sha256",
    "rebind_resume_capsule",
    "select_resume_checkpoint",
]
