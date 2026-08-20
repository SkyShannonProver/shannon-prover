"""Typed result boundary between tree search and run-level proof acceptance.

Tree supervision owns search topology and may select a session-closed
candidate.  It never owns the final proof verdict.  The prover run coordinator
consumes these immutable records, performs offline EasyCrypt verification, and
is the only layer allowed to produce a verified run outcome.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core.easycrypt.committed_history import history_path
from workflow.tree.session_observer import WorkflowSessionSnapshot


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class SessionClosureCandidate:
    """Content-bound handoff for one exact manager-owned EasyCrypt session."""

    candidate_id: str
    node_id: str
    session_dir: str
    session_status: str
    target_file: str
    target_file_sha256: str
    target_lemma: str
    history_sha256: str
    tactic_count: int
    close_result_event_id: str
    close_event_id: str
    terminal_event_id: str

    @classmethod
    def from_snapshot(
        cls,
        *,
        node_id: str,
        snapshot: WorkflowSessionSnapshot,
        target_file: str,
        target_lemma: str,
    ) -> "SessionClosureCandidate":
        if not snapshot.ok:
            raise ValueError("completion candidate snapshot is not authoritative")
        if not snapshot.session_completion_candidate:
            raise ValueError("completion candidate requires committed qed authority")
        authority = dict(snapshot.candidate_close_authority or {})
        if authority.get("authoritative") is not True:
            raise ValueError("completion candidate has no close occurrence authority")
        identities = {
            key: str(authority.get(key) or "")
            for key in (
                "close_result_event_id",
                "close_event_id",
                "terminal_event_id",
            )
        }
        if not all(identities.values()):
            raise ValueError("completion candidate close identity is incomplete")
        session = Path(snapshot.session_dir).resolve()
        history = history_path(session)
        source = Path(target_file).resolve()
        if not history.is_file():
            raise ValueError("completion candidate history is unavailable")
        if not source.is_file():
            raise ValueError("completion candidate target source is unavailable")
        payload = {
            "node_id": str(node_id),
            "session_dir": str(session),
            "session_status": snapshot.status,
            "target_file": str(source),
            "target_file_sha256": _sha256_file(source),
            "target_lemma": str(target_lemma),
            "history_sha256": _sha256_file(history),
            "tactic_count": int(snapshot.tactic_count),
            **identities,
        }
        if not payload["node_id"] or not payload["target_lemma"]:
            raise ValueError("completion candidate target identity is incomplete")
        candidate_id = hashlib.sha256(
            json.dumps(
                payload,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
        return cls(candidate_id=candidate_id, **payload)

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "node_id": self.node_id,
            "session_dir": self.session_dir,
            "session_status": self.session_status,
            "target_file": self.target_file,
            "target_file_sha256": self.target_file_sha256,
            "target_lemma": self.target_lemma,
            "history_sha256": self.history_sha256,
            "tactic_count": self.tactic_count,
            "close_result_event_id": self.close_result_event_id,
            "close_event_id": self.close_event_id,
            "terminal_event_id": self.terminal_event_id,
        }


@dataclass(frozen=True)
class TreeRunResult:
    """Search result; never a proof-success verdict."""

    output_text: str = ""
    returncode: int = 0
    selected_node_id: str = "root"
    selected_session_id: str = ""
    selected_session_dir: str = ""
    turns: int = 0
    managed_session_dirs: tuple[str, ...] = field(default_factory=tuple)
    completion_candidate: SessionClosureCandidate | None = None
    session_records: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    information_source_audit: tuple[dict[str, str], ...] = field(
        default_factory=tuple
    )
    payload_audit_path: str = ""
    destructive_abort: bool = False
    destructive_reason: str = ""
    infrastructure_errors: tuple[str, ...] = field(default_factory=tuple)


__all__ = ["SessionClosureCandidate", "TreeRunResult"]
