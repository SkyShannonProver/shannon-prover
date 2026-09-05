"""Lossless, non-replaying finalization for interrupted proof jobs.

Terminal handback and cold resume are deliberately separate operations.  The
terminal owner preserves the exact manager-accepted prefix immediately and
reuses the newest compatible checkpoint already minted at a completed manager
turn.  It never starts a fresh EasyCrypt session merely to make an interrupted
run terminal.  A later resume operation owns the one cold replay and validates
the recorded residual-goal identity.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

from workflow.node.proof_node_resume import (
    ProofNodeResumeCapsule,
    load_resume_capsule,
)


SAFE_STOP_FINALIZATION_KIND = "proof_safe_stop_finalization"
SAFE_STOP_FINALIZATION_SCHEMA_VERSION = 2


@dataclass(frozen=True)
class SafeStopFinalization:
    """Result of the run owner's mandatory safe-stop checkpoint boundary."""

    completed: bool
    method: str
    tactic_count: int
    checkpoint_tactic_count: int = 0
    uncheckpointed_tactic_count: int = 0
    capsule_paths: tuple[str, ...] = ()
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _is_compatible_open_capsule(
    capsule: ProofNodeResumeCapsule,
    *,
    target_file: str,
    lemma: str,
    committed_prefix: tuple[str, ...],
) -> bool:
    return (
        capsule.target_file == target_file
        and capsule.lemma == lemma
        and bool(capsule.replay_prefix)
        and tuple(capsule.replay_prefix)
        == committed_prefix[: len(capsule.replay_prefix)]
        and capsule.goal_identity_required is True
        and bool(capsule.current_goal_hash)
    )


def _validated_confirmed_capsules(
    paths: Iterable[str],
    *,
    allowed_root: Path,
    target_file: str,
    lemma: str,
    committed_prefix: tuple[str, ...],
) -> tuple[str, ...]:
    allowed_root = allowed_root.resolve()
    compatible: list[tuple[int, str]] = []
    for raw_path in paths:
        path = Path(str(raw_path)).resolve()
        if not path.is_file() or not path.is_relative_to(allowed_root):
            continue
        try:
            capsule = load_resume_capsule(path)
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        if _is_compatible_open_capsule(
            capsule,
            target_file=target_file,
            lemma=lemma,
            committed_prefix=committed_prefix,
        ):
            compatible.append((capsule.tactic_count, str(path)))
    if not compatible:
        return ()
    best_count = max(count for count, _ in compatible)
    return tuple(path for count, path in compatible if count == best_count)


def _write_accepted_prefix(
    run_dir: Path,
    *,
    lemma: str,
    committed_prefix: tuple[str, ...],
) -> None:
    """Persist reporting progress without executing EasyCrypt again."""

    text = "\n".join(committed_prefix) + "\n"
    encoded = text.encode("utf-8")
    (run_dir / "partial_proof_prefix.ec").write_bytes(encoded)
    (run_dir / "partial_proof_prefix.json").write_text(
        json.dumps(
            {
                "kind": "partial_proof_prefix",
                "schema_version": 2,
                "lemma": lemma,
                "closed_by_qed": False,
                "tactic_count": len(committed_prefix),
                "byte_count": len(encoded),
                "sha256": hashlib.sha256(encoded).hexdigest(),
                "source": "manager_session_history_or_resume_capsule",
                "replay_required_before_use": True,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _write_finalization_audit(
    run_dir: Path,
    *,
    trigger: str,
    result: SafeStopFinalization,
) -> None:
    payload = {
        "schema_version": SAFE_STOP_FINALIZATION_SCHEMA_VERSION,
        "kind": SAFE_STOP_FINALIZATION_KIND,
        "created_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "trigger": str(trigger or "run_terminal"),
        **result.to_dict(),
        "capsule_paths": list(result.capsule_paths),
    }
    path = Path(run_dir) / "safe_stop_finalization.json"
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def finalize_safe_stop_checkpoint(
    *,
    project_root: Path,
    run_dir: Path,
    target_file: str,
    lemma: str,
    include_dir: str,
    committed_prefix: Iterable[str],
    committed_transactions: Iterable[str] | None = None,
    existing_capsules: Iterable[str] = (),
    surface_profile: str | None = None,
    agent_report: dict[str, Any] | None = None,
    trigger: str = "run_terminal",
) -> SafeStopFinalization:
    """Finalize one interrupted run without synchronously replaying its spine.

    A compatible capsule is a checkpoint minted at an earlier completed
    manager turn whose prefix is a prefix of the terminal accepted spine.  The
    terminal handback may therefore contain a small uncheckpointed tail, but no
    accepted tactic is lost.  If no checkpoint survived, the accepted prefix is
    still a valid reporting artifact and the run remains an ordinary incomplete
    result; a future warm handoff can replay it explicitly.
    """

    run_dir = Path(run_dir).resolve()
    prefix = tuple(
        str(tactic).strip()
        for tactic in committed_prefix
        if isinstance(tactic, str) and tactic.strip()
    )
    allowed_root = run_dir / "resume_capsules"
    # Retain the parameter for call-site/source compatibility.  Transaction
    # boundaries matter when a later resume replays a capsule; they are not a
    # reason to execute the proof again while sealing a terminal result.
    del project_root, include_dir, committed_transactions, surface_profile, agent_report

    if not prefix:
        result = SafeStopFinalization(
            completed=True,
            method="no_progress",
            tactic_count=0,
        )
        _write_finalization_audit(run_dir, trigger=trigger, result=result)
        return result

    _write_accepted_prefix(
        run_dir,
        lemma=lemma,
        committed_prefix=prefix,
    )

    confirmed = _validated_confirmed_capsules(
        existing_capsules,
        allowed_root=allowed_root,
        target_file=target_file,
        lemma=lemma,
        committed_prefix=prefix,
    )
    if confirmed:
        checkpoint_count = load_resume_capsule(confirmed[0]).tactic_count
        result = SafeStopFinalization(
            completed=True,
            method=(
                "drained_live_checkpoint"
                if checkpoint_count == len(prefix)
                else "last_confirmed_checkpoint"
            ),
            tactic_count=len(prefix),
            checkpoint_tactic_count=checkpoint_count,
            uncheckpointed_tactic_count=len(prefix) - checkpoint_count,
            capsule_paths=confirmed,
        )
        _write_finalization_audit(run_dir, trigger=trigger, result=result)
        return result

    result = SafeStopFinalization(
        completed=True,
        method="accepted_prefix_only",
        tactic_count=len(prefix),
        checkpoint_tactic_count=0,
        uncheckpointed_tactic_count=len(prefix),
    )

    _write_finalization_audit(run_dir, trigger=trigger, result=result)
    return result


__all__ = [
    "SAFE_STOP_FINALIZATION_KIND",
    "SAFE_STOP_FINALIZATION_SCHEMA_VERSION",
    "SafeStopFinalization",
    "finalize_safe_stop_checkpoint",
]
