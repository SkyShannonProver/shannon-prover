"""Fail-closed proof acceptance checks over the canonical session projection.

The core projection alone decides whether the current session has an exact
candidate-close occurrence and passing offline verification. This module only
checks that projection against candidate immutability and final-acceptance
requirements; it never re-summarizes event history into a second close fact.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from core.easycrypt.committed_history import history_path
from core.easycrypt.session_events import (
    EVENTS_FILENAME,
    append_event,
)
from core.easycrypt.session_projection import (
    ProofStateProjection,
    read_proof_state_projection,
)

if TYPE_CHECKING:
    from workflow.tree.result import SessionClosureCandidate


@dataclass(frozen=True)
class EventContractGate:
    ok: bool
    session_dir: str
    event_log: str
    event_log_exists: bool
    goals_discharged: bool = False
    session_completion_candidate: bool = False
    qed_committed: bool = False
    completion_candidate_bound: bool = False
    candidate_id: str = ""
    verification_status: str | None = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "session_dir": self.session_dir,
            "event_log": self.event_log,
            "event_log_exists": self.event_log_exists,
            "goals_discharged": self.goals_discharged,
            "session_completion_candidate": self.session_completion_candidate,
            "qed_committed": self.qed_committed,
            "completion_candidate_bound": self.completion_candidate_bound,
            "candidate_id": self.candidate_id,
            "verification_status": self.verification_status,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
        }

    def error_summary(self, limit: int = 5) -> str:
        if not self.errors:
            return ""
        shown = self.errors[:limit]
        suffix = "" if len(self.errors) <= limit else f" (+{len(self.errors) - limit} more)"
        return "; ".join(shown) + suffix


def emit_workflow_verification_event(
    session_dir: str | Path | None,
    *,
    lemma: str,
    status: str,
    verifier: str = "easycrypt",
    **payload: Any,
) -> bool:
    """Append a workflow-produced verification event to the session stream."""
    path = _resolve_session_dir(session_dir)
    if path is None:
        return False
    data = {
        "lemma": lemma,
        "status": status,
        "verifier": verifier,
    }
    data.update(payload)
    return append_event(path, "verification.completed", data, source="workflow.prover")


def validate_goal_discharge_contract(
    session_dir: str | Path | None,
) -> EventContractGate:
    """Require exact current authority that EasyCrypt discharged the goals."""
    gate, _projection = _read_projection_gate(
        session_dir,
        require_goals_discharged=True,
        require_session_completion_candidate=False,
        require_offline_verified=False,
    )
    return gate


def validate_acceptance_event_contract(
    session_dir: str | Path | None,
) -> EventContractGate:
    """Require a valid event stream for final proof acceptance.

    This is intentionally stricter than goal-discharge tracking: final
    acceptance requires committed ``qed.``, a session completion candidate,
    and a passing verification event in the same projection.
    """
    gate, _projection = _read_projection_gate(
        session_dir,
        require_goals_discharged=True,
        require_session_completion_candidate=True,
        require_offline_verified=True,
    )
    return gate


def validate_completion_candidate_contract(
    candidate: "SessionClosureCandidate",
) -> EventContractGate:
    """Bind a tree-selected candidate to its exact current session artifacts."""

    gate, projection = _read_projection_gate(
        candidate.session_dir,
        require_goals_discharged=True,
        require_session_completion_candidate=True,
        require_offline_verified=False,
    )
    errors = list(gate.errors)
    path = Path(candidate.session_dir).resolve()
    qed_committed = False
    completion_candidate_bound = False
    if projection is not None:
        authority = projection.candidate_close_authority
        qed_committed = projection.qed_committed
        expected_occurrence = (
            candidate.close_result_event_id,
            candidate.close_event_id,
            candidate.terminal_event_id,
        )
        actual_occurrence = (
            authority.close_result_event_id,
            authority.close_event_id,
            authority.terminal_event_id,
        )
        if expected_occurrence != actual_occurrence:
            errors.append("completion candidate close occurrence identity drifted")
        history = history_path(path)
        if not history.is_file() or _sha256_file(history) != candidate.history_sha256:
            errors.append("completion candidate history hash drifted")
        source = Path(candidate.target_file).resolve()
        if not source.is_file() or _sha256_file(source) != (
            candidate.target_file_sha256
        ):
            errors.append("completion candidate target source hash drifted")
        completion_candidate_bound = not errors
    return EventContractGate(
        ok=not errors,
        session_dir=gate.session_dir,
        event_log=gate.event_log,
        event_log_exists=gate.event_log_exists,
        goals_discharged=gate.goals_discharged,
        session_completion_candidate=gate.session_completion_candidate,
        qed_committed=qed_committed,
        completion_candidate_bound=completion_candidate_bound,
        candidate_id=candidate.candidate_id,
        verification_status=gate.verification_status,
        errors=errors,
        warnings=list(gate.warnings),
    )


def _read_projection_gate(
    session_dir: str | Path | None,
    *,
    require_goals_discharged: bool,
    require_session_completion_candidate: bool,
    require_offline_verified: bool,
) -> tuple[EventContractGate, ProofStateProjection | None]:
    path = _resolve_session_dir(session_dir)
    event_log = path / EVENTS_FILENAME if path is not None else Path("")
    if path is None:
        return (
            EventContractGate(
                ok=False,
                session_dir="",
                event_log="",
                event_log_exists=False,
                errors=["session directory is unknown"],
            ),
            None,
        )
    try:
        projection = read_proof_state_projection(path)
    except Exception as exc:
        return (
            EventContractGate(
                ok=False,
                session_dir=str(path.resolve()),
                event_log=str(event_log.resolve()),
                event_log_exists=event_log.exists(),
                errors=[f"canonical proof-state projection failed: {exc}"],
            ),
            None,
        )

    goals_discharged = bool(projection.goals_discharged)
    session_completion_candidate = bool(
        projection.session_completion_candidate
    )
    errors = [
        *projection.events.errors,
        *projection.consistency.errors,
    ]
    warnings = [
        *projection.events.warnings,
        *projection.consistency.warnings,
    ]
    if require_goals_discharged and not goals_discharged:
        errors.append(
            "authoritative current goal discharge is required"
        )
    if (
        require_session_completion_candidate
        and not session_completion_candidate
    ):
        errors.append(
            "committed session completion candidate authority is required"
        )
    if require_offline_verified and not projection.offline_verified:
        errors.append("passing offline verification authority is required")

    gate = EventContractGate(
        ok=not errors,
        session_dir=str(path.resolve()),
        event_log=projection.events.event_log,
        event_log_exists=projection.events.exists,
        goals_discharged=goals_discharged,
        session_completion_candidate=session_completion_candidate,
        qed_committed=projection.qed_committed,
        verification_status=projection.events.verification_status,
        errors=errors,
        warnings=warnings,
    )
    return gate, projection


def _resolve_session_dir(session_dir: str | Path | None) -> Path | None:
    if not session_dir:
        return None
    return Path(session_dir).expanduser()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
