"""Proof-fact analysis boundary for EasyCrypt sessions.

Analyzers should produce structured facts here, not prompt text. Downstream
surfaces (ProofContextView, -diagnose, tree-spawn prompts, schedulers) can then
render or act on the same fact without each re-running analyzer-specific
logic or inventing its own wording.

Generic failed branch-experiment clusters provide scheduler memory without
carrying a lemma-specific repair.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional


PROOF_FACT_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class ProofFact:
    """A session-scoped analysis fact.

    ``payload`` is producer-owned, but must be JSON-serializable. ``goal_hash``
    ties the fact to the active state when available; analyzers based on recent
    session history may leave it empty if no goal is readable.
    """

    kind: str
    producer: str
    confidence: str
    payload: dict[str, Any] = field(default_factory=dict)
    goal_hash: str = ""
    source_event_ids: tuple[str, ...] = ()
    evidence: dict[str, Any] = field(default_factory=dict)
    expires_on: tuple[str, ...] = ("goal_change", "session_restart")
    schema_version: int = PROOF_FACT_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "kind": self.kind,
            "producer": self.producer,
            "confidence": self.confidence,
            "goal_hash": self.goal_hash,
            "source_event_ids": list(self.source_event_ids),
            "evidence": dict(self.evidence),
            "payload": dict(self.payload),
            "expires_on": list(self.expires_on),
        }


def collect_proof_facts(
    session_dir: str | Path,
    *,
    source_path: str | Path | None = None,
    include_kinds: Iterable[str] | None = None,
) -> list[ProofFact]:
    """Run known fact analyzers for a session.

    ``include_kinds`` is a cheap caller-side filter so high-frequency surfaces
    can request only the fact family they know how to render.
    """
    wanted = set(include_kinds or [])
    facts: list[ProofFact] = []
    if not wanted or "ec_scope_context" in wanted:
        fact = ec_scope_context_fact(session_dir, source_path=source_path)
        if fact is not None:
            facts.append(fact)
    if not wanted or "recent_failed_tactic_attempt_cluster" in wanted:
        facts.extend(recent_failed_attempt_cluster_facts(session_dir))
    if not wanted or "failed_branch_experiment_cluster" in wanted:
        facts.extend(failed_branch_experiment_cluster_facts(session_dir))
    return facts


def first_fact(
    facts: Iterable[ProofFact],
    kind: str,
) -> Optional[ProofFact]:
    for fact in facts:
        if fact.kind == kind:
            return fact
    return None


def ec_scope_context_fact(
    session_dir: str | Path,
    *,
    source_path: str | Path | None = None,
) -> Optional[ProofFact]:
    sdir = Path(session_dir)
    src = _resolve_source_path(sdir, source_path)
    if src is None or not src.exists():
        return None
    try:
        from core.easycrypt.ec_static_context import read_ec_scope_context  # type: ignore
    except Exception:
        try:
            from core.easycrypt.ec_static_context import (  # type: ignore
                read_ec_scope_context,
            )
        except Exception:
            return None
    try:
        scope_context = read_ec_scope_context(src)
    except Exception:
        return None
    if scope_context is None:
        return None
    return ProofFact(
        kind="ec_scope_context",
        producer="ec_static_context.analyze_ec_scope_context",
        confidence="high",
        payload=scope_context.to_dict(),
        evidence={
            "source_file": str(src),
            "source_hash": scope_context.source_hash,
        },
        expires_on=("source_change", "session_restart"),
    )


def recent_failed_attempt_cluster_facts(
    session_dir: str | Path,
) -> list[ProofFact]:
    sdir = Path(session_dir)
    try:
        from core.easycrypt.session_attempts import (  # type: ignore
            cluster_recent_failed_tactic_attempts,
            read_failed_tactic_attempts,
        )
    except Exception:
        try:
            from core.easycrypt.session_attempts import (  # type: ignore
                cluster_recent_failed_tactic_attempts,
                read_failed_tactic_attempts,
            )
        except Exception:
            return []
    try:
        attempts = read_failed_tactic_attempts(sdir)
        clusters = cluster_recent_failed_tactic_attempts(attempts)
    except Exception:
        return []
    return [
        ProofFact(
            kind="recent_failed_tactic_attempt_cluster",
            producer="session_attempts.cluster_recent_failed_tactic_attempts",
            confidence="medium",
            payload=cluster.to_dict(),
            goal_hash=_goal_hash(sdir),
            source_event_ids=cluster.source_event_ids,
            evidence={
                "events_file": str(sdir / "events.jsonl"),
                "lookback": 6,
                "min_consecutive": 3,
            },
            expires_on=("new_tactic_attempt", "goal_change", "session_restart"),
        )
        for cluster in clusters
    ]


def failed_branch_experiment_cluster_facts(
    session_dir: str | Path,
) -> list[ProofFact]:
    """Return generic repeated failed-branch experiment facts.

    These are scheduler/prompt memory facts: they say "this experiment shape
    already failed here" without claiming which tactic should replace it.
    """
    sdir = Path(session_dir)
    try:
        from core.easycrypt.session_attempts import (  # type: ignore
            cluster_failed_branch_experiments,
            read_failed_tactic_attempts,
        )
    except Exception:
        try:
            from core.easycrypt.session_attempts import (  # type: ignore
                cluster_failed_branch_experiments,
                read_failed_tactic_attempts,
            )
        except Exception:
            return []
    try:
        attempts = read_failed_tactic_attempts(sdir)
        clusters = cluster_failed_branch_experiments(attempts)
    except Exception:
        return []
    return [
        ProofFact(
            kind="failed_branch_experiment_cluster",
            producer="session_attempts.cluster_failed_branch_experiments",
            confidence="medium",
            payload=cluster.to_dict(),
            goal_hash=_goal_hash(sdir),
            source_event_ids=cluster.source_event_ids,
            evidence={
                "events_file": str(sdir / "events.jsonl"),
                "lookback": 8,
                "min_consecutive": 2,
                "policy_role": "dedupe_memory_only",
                "interpretation": (
                    "repeated failed branch-shape experiment; use as memory, "
                    "not as a repair directive"
                ),
            },
            expires_on=("new_tactic_attempt", "goal_change", "session_restart"),
        )
        for cluster in clusters
    ]


def _resolve_source_path(
    session_dir: Path,
    source_path: str | Path | None,
) -> Optional[Path]:
    raw: str | Path | None = source_path
    if raw is None:
        meta = _read_meta(session_dir)
        raw = meta.get("file") or meta.get("source_file")
    if not raw:
        return None
    p = Path(raw).expanduser()
    if p.is_absolute():
        return p
    for candidate in (
        Path.cwd() / p,
        session_dir / p,
        session_dir.parent / p,
    ):
        if candidate.exists():
            return candidate
    return p


def _read_meta(session_dir: Path) -> dict[str, Any]:
    meta_path = session_dir / "session_meta.json"
    if not meta_path.exists():
        return {}
    try:
        data = json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _goal_hash(session_dir: Path) -> str:
    try:
        from core.easycrypt.session_projection import read_proof_state_projection  # type: ignore
    except Exception:
        try:
            from core.easycrypt.session_projection import (  # type: ignore
                read_proof_state_projection,
            )
        except Exception:
            return _file_hash(session_dir / "current.out")
    try:
        projection = read_proof_state_projection(session_dir)
        return projection.goal.active_goal_hash
    except Exception:
        return _file_hash(session_dir / "current.out")


def _file_hash(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""
    return hashlib.sha1(text.encode("utf-8", errors="replace")).hexdigest()
