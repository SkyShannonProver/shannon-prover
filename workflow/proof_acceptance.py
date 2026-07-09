"""Fail-closed proof acceptance checks built on session events.

The session runtime emits append-only events, while upper workflow layers decide
whether a proof is safe to accept. This module is that boundary: it converts the
raw event stream into a small gate result that progress tracking and prover
acceptance can share.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core.easycrypt.session_events import (
    EVENTS_FILENAME,
    append_event,
    has_candidate_closed,
    read_event_file,
    summarize_events,
    validate_event_stream,
)


@dataclass(frozen=True)
class EventContractGate:
    ok: bool
    session_dir: str
    event_log: str
    event_log_exists: bool
    candidate_closed: bool = False
    verification_status: str | None = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "session_dir": self.session_dir,
            "event_log": self.event_log,
            "event_log_exists": self.event_log_exists,
            "candidate_closed": self.candidate_closed,
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


def validate_candidate_event_contract(
    session_dir: str | Path | None,
) -> EventContractGate:
    """Require a valid event stream with a real candidate-close event."""
    return _validate_event_contract(
        session_dir,
        require_candidate_closed=True,
        expected_outcome=None,
    )


def validate_acceptance_event_contract(
    session_dir: str | Path | None,
) -> EventContractGate:
    """Require a valid event stream for final proof acceptance.

    This is intentionally stricter than candidate tracking: final acceptance
    requires a closed candidate and a passing verification event in the same
    stream.
    """
    return _validate_event_contract(
        session_dir,
        require_candidate_closed=True,
        expected_outcome="PASS",
    )


def _validate_event_contract(
    session_dir: str | Path | None,
    *,
    require_candidate_closed: bool,
    expected_outcome: str | None,
) -> EventContractGate:
    path = _resolve_session_dir(session_dir)
    event_log = path / EVENTS_FILENAME if path is not None else Path("")
    if path is None:
        return EventContractGate(
            ok=False,
            session_dir="",
            event_log="",
            event_log_exists=False,
            errors=["session directory is unknown"],
        )
    if not event_log.exists():
        return EventContractGate(
            ok=False,
            session_dir=str(path.resolve()),
            event_log=str(event_log.resolve()),
            event_log_exists=False,
            errors=[f"event log missing: {event_log}"],
        )

    events = read_event_file(event_log)
    validation = validate_event_stream(
        events,
        expected_outcome=expected_outcome,
    )
    summary = summarize_events(events)
    candidate_closed = has_candidate_closed(events)
    errors = [issue.format() for issue in validation.errors]
    warnings = [issue.format() for issue in validation.warnings]

    if require_candidate_closed and not candidate_closed:
        errors.append("proof.candidate_closed event is required")

    return EventContractGate(
        ok=not errors,
        session_dir=str(path.resolve()),
        event_log=str(event_log.resolve()),
        event_log_exists=True,
        candidate_closed=candidate_closed,
        verification_status=summary.verification_status,
        errors=errors,
        warnings=warnings,
    )


def _resolve_session_dir(session_dir: str | Path | None) -> Path | None:
    if not session_dir:
        return None
    return Path(session_dir).expanduser()
