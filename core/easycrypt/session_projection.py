"""Canonical proof-state projection for EasyCrypt sessions.

This module is the read-only boundary that joins the factual sources available
for an interactive proof session:

* ``current.out`` / ``prev.out`` via :mod:`session_state`
* append-only JSONL session events via :mod:`session_events`
The current managed L1/compiler-V2 path requests only exact goal text,
canonical goal identity, status, history, and event consistency. It has no
dependency on the removed Python proof-analysis or goal-parser pipeline.

Consumers should prefer this projection when they need a consistent view of
"where the proof is" instead of independently grepping EC text and event logs.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core.easycrypt.committed_history import (
    committed_tactics_have_qed,
    history_path,
    read_committed_tactics,
)
from core.easycrypt.proof_lifecycle import (
    CLOSED_UNTRUSTED,
    ERROR,
    GOALS_DISCHARGED_PENDING_QED,
    NO_CURRENT,
    OPEN,
    SESSION_CLOSED_PENDING_VERIFICATION,
    UNKNOWN,
    VERIFIED,
    is_session_completion_candidate,
)
from core.easycrypt.session_events import (
    EVENTS_FILENAME,
    event_payload,
    summarize_events,
    validate_event_stream,
)
from core.easycrypt.session_state import (
    REMAINING_UNKNOWN,
    SessionState,
    extract_active_goal_block,
    read_session_state,
)


_EC_PROMPT_LINE_RE = re.compile(r"(?m)^\[\d+\|[^\]\n]*\]>\s*$")


@dataclass(frozen=True)
class HistoryProjection:
    path: str
    exists: bool
    tactic_count: int
    has_qed: bool
    latest_tactic: str = ""
    # Exact content from the same read that produced tactic_count/has_qed.
    # Kept internal to typed consumers; generic status serialization remains
    # bounded and does not expose the proof spine.
    tactics: tuple[str, ...] = field(default=(), repr=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "exists": self.exists,
            "tactic_count": self.tactic_count,
            "has_qed": self.has_qed,
            "latest_tactic": self.latest_tactic,
        }


@dataclass(frozen=True)
class EventContractProjection:
    event_log: str
    exists: bool
    event_count: int
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    event_counts: dict[str, int] = field(default_factory=dict)
    tactic_status_counts: dict[str, int] = field(default_factory=dict)
    candidate_closed: bool = False
    verification_status: str | None = None
    latest_attempt: dict[str, Any] = field(default_factory=dict)
    recent_failed_attempts: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_log": self.event_log,
            "exists": self.exists,
            "event_count": self.event_count,
            "ok": self.ok,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "event_counts": dict(self.event_counts),
            "tactic_status_counts": dict(self.tactic_status_counts),
            "candidate_closed": self.candidate_closed,
            "verification_status": self.verification_status,
            "latest_attempt": dict(self.latest_attempt),
            "recent_failed_attempts": list(self.recent_failed_attempts),
        }


@dataclass(frozen=True)
class CandidateCloseAuthorityProjection:
    """Exact event occurrence authorizing the current closed candidate.

    Aggregate event history is useful telemetry, but it cannot say whether an
    old close still describes the current state.  This record binds either the
    latest tactic result directly to its adjacent ``proof.candidate_closed``
    event, or a saved ``qed.`` result to the immediately preceding certified
    close occurrence.
    """

    kind: str = "none"
    close_result_event_id: str = ""
    close_event_id: str = ""
    terminal_event_id: str = ""
    close_result_sequence: int = 0
    close_event_sequence: int = 0
    terminal_event_sequence: int = 0

    def __post_init__(self) -> None:
        if self.kind not in {
            "none",
            "direct_close",
            "post_qed_preserved_close",
            "undo_restored_close",
        }:
            raise ValueError("unsupported candidate-close authority kind")
        identities = (
            self.close_result_event_id,
            self.close_event_id,
            self.terminal_event_id,
        )
        sequences = (
            self.close_result_sequence,
            self.close_event_sequence,
            self.terminal_event_sequence,
        )
        if self.kind == "none":
            if any(identities) or any(sequences):
                raise ValueError(
                    "absent candidate-close authority carries an occurrence"
                )
            return
        if any(type(value) is not str or not value for value in identities):
            raise ValueError("candidate-close authority requires event identities")
        if any(type(value) is not int or value <= 0 for value in sequences):
            raise ValueError("candidate-close authority requires event sequences")
        if self.close_event_sequence != self.close_result_sequence + 1:
            raise ValueError("candidate-close result and close event must be adjacent")
        if self.kind == "direct_close" and (
            self.terminal_event_id != self.close_result_event_id
            or self.terminal_event_sequence != self.close_result_sequence
        ):
            raise ValueError("direct close authority has the wrong terminal event")
        if self.kind in {"post_qed_preserved_close", "undo_restored_close"} and (
            self.terminal_event_sequence <= self.close_event_sequence
        ):
            raise ValueError("preserved close authority has the wrong event order")

    @property
    def authoritative(self) -> bool:
        return self.kind in {
            "direct_close",
            "post_qed_preserved_close",
            "undo_restored_close",
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "authoritative": self.authoritative,
            "close_result_event_id": self.close_result_event_id,
            "close_event_id": self.close_event_id,
            "terminal_event_id": self.terminal_event_id,
            "close_result_sequence": self.close_result_sequence,
            "close_event_sequence": self.close_event_sequence,
            "terminal_event_sequence": self.terminal_event_sequence,
        }


@dataclass(frozen=True)
class GoalProjection:
    has_current: bool
    state_kind: str
    goal_type: str
    num_remaining: int | None
    num_remaining_determined: bool
    proof_candidate_closed: bool
    active_goal_hash: str
    active_goal_preview: str
    fact_source: str = "pretty_goal_text"
    authority: str = "display_only_text_projection"
    authority_rank: int = 10

    def __post_init__(self) -> None:
        if self.proof_candidate_closed and self.active_goal_hash:
            raise ValueError("closed GoalProjection cannot carry active_goal_hash")

    def to_dict(self, *, include_raw: bool = False, raw_text: str = "") -> dict[str, Any]:
        data = {
            "has_current": self.has_current,
            "state_kind": self.state_kind,
            "goal_type": self.goal_type,
            "num_remaining": self.num_remaining,
            "num_remaining_determined": self.num_remaining_determined,
            "proof_candidate_closed": self.proof_candidate_closed,
            "active_goal_hash": self.active_goal_hash,
            "active_goal_preview": self.active_goal_preview,
            "fact_source": self.fact_source,
            "authority": self.authority,
            "authority_rank": self.authority_rank,
        }
        if include_raw:
            data["active_goal_text"] = raw_text
        return data

    def to_display_dict(
        self,
        *,
        include_raw: bool = False,
        raw_text: str = "",
    ) -> dict[str, Any]:
        """Return goal presentation fields without duplicating identity.

        ``ProofStateProjection.goal.active_goal_hash`` is the identity owner.
        Display projections deliberately omit that field so a downstream
        consumer cannot accidentally promote a presentation alias into a
        second authority path.
        """

        data = self.to_dict(include_raw=include_raw, raw_text=raw_text)
        data.pop("active_goal_hash", None)
        return data


@dataclass(frozen=True)
class TransitionProjection:
    """Latest transition effect classification, not candidate-close authority."""

    kind: str
    tactic: str = ""
    status: str = ""
    goals_before: int | None = None
    goals_after: int | None = None
    candidate_closed: bool = False
    no_progress: bool = False
    no_progress_reason: str = ""
    history_committed: bool | None = None
    latest_error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "tactic": self.tactic,
            "status": self.status,
            "goals_before": self.goals_before,
            "goals_after": self.goals_after,
            "candidate_closed": self.candidate_closed,
            "no_progress": self.no_progress,
            "no_progress_reason": self.no_progress_reason,
            "history_committed": self.history_committed,
            "latest_error": self.latest_error,
        }


@dataclass(frozen=True)
class ConsistencyProjection:
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "notes": list(self.notes),
        }


@dataclass(frozen=True)
class ProofStateProjection:
    session_dir: str
    status: str
    goals_discharged: bool
    offline_verified: bool
    history: HistoryProjection
    events: EventContractProjection
    candidate_close_authority: CandidateCloseAuthorityProjection
    goal: GoalProjection
    latest_transition: TransitionProjection
    consistency: ConsistencyProjection
    active_goal_text: str
    # The exact parsed records used for `events`, retained for workflow
    # telemetry/artifact adapters so they do not reread a moving JSONL file.
    # Deliberately omitted from `to_dict()`.
    source_events: tuple[dict[str, Any], ...] = field(
        default=(),
        repr=False,
        compare=False,
    )

    @property
    def goal_identity_required(self) -> bool:
        """Whether this exact EC snapshot has an active goal to identify.

        Candidate readiness additionally requires a valid event occurrence.
        Goal identity does not: ``No more goals`` in this exact state means
        there is no active goal hash, even when the event contract is missing
        and the candidate therefore cannot cross a managed commit boundary.
        """

        return not self.goal.proof_candidate_closed

    @property
    def qed_committed(self) -> bool:
        """Whether this exact discharged state has committed close syntax."""

        return bool(self.goals_discharged and self.history.has_qed)

    @property
    def session_completion_candidate(self) -> bool:
        """Whether this session may cross the tree/finalization boundary."""

        return bool(
            self.qed_committed
            and is_session_completion_candidate(self.status)
        )

    def to_dict(
        self,
        *,
        include_raw: bool = False,
    ) -> dict[str, Any]:
        return {
            "session_dir": self.session_dir,
            "status": self.status,
            "goals_discharged": self.goals_discharged,
            "offline_verified": self.offline_verified,
            "history": self.history.to_dict(),
            "events": self.events.to_dict(),
            "candidate_close_authority": self.candidate_close_authority.to_dict(),
            "goal": self.goal.to_dict(
                include_raw=include_raw,
                raw_text=self.active_goal_text,
            ),
            "latest_transition": self.latest_transition.to_dict(),
            "consistency": self.consistency.to_dict(),
        }


def read_proof_state_projection(
    session_dir: str | Path,
    *,
    current_path: str | Path | None = None,
    previous_path: str | Path | None = None,
    live_tool_name: str | None = None,
    infer_live_tool_name: bool = False,
) -> ProofStateProjection:
    """Read a session directory into one canonical proof-state projection."""
    path = Path(session_dir)
    state = read_session_state(
        path,
        Path(current_path) if current_path is not None else None,
        Path(previous_path) if previous_path is not None else None,
    )
    events, event_json_errors = _read_events_strict(path / EVENTS_FILENAME)
    effective_live_tool_name = live_tool_name
    if effective_live_tool_name is None and infer_live_tool_name:
        effective_live_tool_name = _pending_tool_name(events)
    contract_events = _without_live_tool_called(
        events,
        effective_live_tool_name,
    )
    history = _read_history(path)
    event_projection = _build_event_projection(
        path / EVENTS_FILENAME,
        contract_events,
        event_json_errors,
    )
    transition = _build_latest_transition(contract_events)
    close_authority = _build_candidate_close_authority(
        contract_events,
        transition=transition,
        history=history,
    )
    goal_projection = _build_goal_projection(state)
    goal_projection = _normalize_post_qed_goal_projection(
        goal_projection,
        history=history,
        close_authority=close_authority,
        transition=transition,
        event_contract_ok=event_projection.ok,
    )
    consistency = _build_consistency(
        state=state,
        history=history,
        events=event_projection,
        close_authority=close_authority,
        goal=goal_projection,
        transition=transition,
    )
    goals_discharged = bool(
        event_projection.ok
        and close_authority.authoritative
        and consistency.ok
    )
    offline_verified = bool(
        goals_discharged
        and event_projection.verification_status == "pass"
    )
    status = _project_status(
        goal=goal_projection,
        events=event_projection,
        transition=transition,
        history=history,
        goals_discharged=goals_discharged,
        offline_verified=offline_verified,
    )
    return ProofStateProjection(
        session_dir=str(path.resolve()),
        status=status,
        goals_discharged=goals_discharged,
        offline_verified=offline_verified,
        history=history,
        events=event_projection,
        candidate_close_authority=close_authority,
        goal=goal_projection,
        latest_transition=transition,
        consistency=consistency,
        active_goal_text=state.raw_for_goal_tools,
        source_events=tuple(events),
    )


def projection_to_proof_status(projection: ProofStateProjection) -> dict[str, Any]:
    """Compact current proof/session status for typed artifacts."""
    return {
        "status": projection.status,
        "goals_discharged": projection.goals_discharged,
        "qed_committed": projection.qed_committed,
        "offline_verified": projection.offline_verified,
        "goal_identity_required": projection.goal_identity_required,
        "goal": {
            "state_kind": projection.goal.state_kind,
            "goal_type": projection.goal.goal_type,
            "num_remaining": projection.goal.num_remaining,
            "num_remaining_determined": (
                projection.goal.num_remaining_determined
            ),
            "proof_candidate_closed": (
                projection.goal.proof_candidate_closed
            ),
            "active_goal_hash": projection.goal.active_goal_hash,
            "fact_source": projection.goal.fact_source,
            "authority": projection.goal.authority,
            "authority_rank": projection.goal.authority_rank,
        },
        "history": {
            "tactic_count": projection.history.tactic_count,
            "has_qed": projection.history.has_qed,
            "latest_tactic": projection.history.latest_tactic,
        },
        "candidate_close_authority": (
            projection.candidate_close_authority.to_dict()
        ),
        "latest_transition": projection.latest_transition.to_dict(),
        "event_contract": {
            "ok": projection.events.ok,
            "exists": projection.events.exists,
            "event_count": projection.events.event_count,
            "candidate_closed": projection.events.candidate_closed,
            "verification_status": projection.events.verification_status,
            "error_count": len(projection.events.errors),
            "warning_count": len(projection.events.warnings),
            "latest_attempt": dict(projection.events.latest_attempt),
            "recent_failed_attempts": list(
                projection.events.recent_failed_attempts[:5]
            ),
            "errors": projection.events.errors[:3],
            "warnings": projection.events.warnings[:3],
        },
        "consistency": {
            "ok": projection.consistency.ok,
            "error_count": len(projection.consistency.errors),
            "warning_count": len(projection.consistency.warnings),
            "note_count": len(projection.consistency.notes),
            "errors": projection.consistency.errors[:3],
            "warnings": projection.consistency.warnings[:3],
            "notes": projection.consistency.notes[:3],
        },
    }


def _read_history(session_dir: Path) -> HistoryProjection:
    path = history_path(session_dir)
    if not path.exists():
        return HistoryProjection(
            path=str(path),
            exists=False,
            tactic_count=0,
            has_qed=False,
        )
    lines = read_committed_tactics(session_dir)
    return HistoryProjection(
        path=str(path),
        exists=True,
        tactic_count=len(lines),
        has_qed=committed_tactics_have_qed(lines),
        latest_tactic=lines[-1] if lines else "",
        tactics=tuple(lines),
    )


def _pending_tool_name(events: list[dict[str, Any]]) -> str | None:
    pending: dict[str, Any] | None = None
    for event in events:
        if event.get("type") == "tool.called":
            pending = event_payload(event)
        elif event.get("type") == "tool.result":
            pending = None
    if pending is None:
        return None
    return str(pending.get("name") or "") or None


def _read_events_strict(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    if not path.exists():
        return [], [f"event log missing: {path}"]
    events: list[dict[str, Any]] = []
    errors: list[str] = []
    for lineno, line in enumerate(
        path.read_text(encoding="utf-8", errors="replace").splitlines(),
        start=1,
    ):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            event = json.loads(stripped)
        except json.JSONDecodeError as exc:
            errors.append(f"event log line {lineno}: invalid JSON: {exc.msg}")
            continue
        if not isinstance(event, dict):
            errors.append(f"event log line {lineno}: event must be a JSON object")
            continue
        events.append(event)
    return events, errors


def _without_live_tool_called(
    events: list[dict[str, Any]],
    live_tool_name: str | None,
) -> list[dict[str, Any]]:
    """Drop unmatched ``tool.called`` events that are NOT proof-state corruption.

    ``session_cli._run_action`` logs ``tool.called`` before a handler and
    ``tool.result`` after it returns. Two cases leave an unmatched ``tool.called``
    that is harmless to the proof state and must not flip ``event_contract.ok``:

    1. the CURRENT live tool's own in-flight call (a projection built inside the
       handler, before its ``tool.result`` is emitted — mutating handlers can also
       build a post-commit view before their final ``tool.result``);
    2. a READ-ONLY action (for example an exact tactic preflight or native
       compiler projection)
       whose handler raised or was killed between the two emits (the exception path
       re-raises without emitting ``tool.result``), leaving a stale dangling call
       that poisons the NEXT commit's contract — the observed "probe accepted,
       commit rejected (event contract is not valid)" MISLABEL of a successful
       commit.

    A dangling MUTATING call is genuine and still
    fails closed (here and at the authoritative qed gate). We key on the
    ``mutates_proof_state`` flag the event already carries (not a name list), so new
    read-only actions heal automatically; a missing flag defaults to mutating
    (fail-closed). This neutralization applies ONLY to the live/inline view (a
    ``live_tool_name`` is set); strict reads (``live_tool_name=None``, e.g. audits
    and the qed acceptance gate, which also re-read the raw log) keep the full
    stream so a genuinely corrupt stream is still caught there.
    """
    if not live_tool_name or not events:
        return events
    open_calls: dict[str, list[tuple[int, bool]]] = {}
    for idx, event in enumerate(events):
        payload = event_payload(event)
        name = str(payload.get("name") or "")
        if event.get("type") == "tool.called":
            open_calls.setdefault(name, []).append(
                (idx, bool(payload.get("mutates_proof_state", True))))
        elif event.get("type") == "tool.result" and open_calls.get(name):
            open_calls[name].pop()
    drop: set[int] = set()
    for name, entries in open_calls.items():
        for idx, mutates in entries:
            # (a) this live tool's own in-flight call; (b) a stale dangling
            # READ-ONLY call from a crashed probe. A dangling MUTATING call that is
            # not the live one is genuine corruption and is kept (fails closed).
            if name == live_tool_name or not mutates:
                drop.add(idx)
    if not drop:
        return events
    return [event for i, event in enumerate(events) if i not in drop]


def _build_event_projection(
    path: Path,
    events: list[dict[str, Any]],
    json_errors: list[str],
) -> EventContractProjection:
    exists = path.exists()
    validation = validate_event_stream(events) if events else None
    summary = summarize_events(events)
    errors = list(json_errors)
    warnings: list[str] = []
    if validation is not None:
        errors.extend(issue.format() for issue in validation.errors)
        warnings.extend(issue.format() for issue in validation.warnings)
    elif exists:
        errors.append("event stream is empty")
    ok = exists and not errors
    return EventContractProjection(
        event_log=str(path),
        exists=exists,
        event_count=len(events),
        ok=ok,
        errors=errors,
        warnings=warnings,
        event_counts=summary.event_counts,
        tactic_status_counts=summary.tactic_status_counts,
        candidate_closed=summary.candidate_closed_count > 0,
        verification_status=summary.verification_status,
        latest_attempt=(
            summary.latest_attempt.to_dict()
            if summary.latest_attempt is not None else {}
        ),
        recent_failed_attempts=[
            attempt.to_dict()
            for attempt in summary.recent_failed_attempts[:5]
        ],
    )


def _build_goal_projection(
    state: SessionState,
) -> GoalProjection:
    if not state.has_current:
        return GoalProjection(
            has_current=False,
            state_kind="no_current",
            goal_type=UNKNOWN,
            num_remaining=None,
            num_remaining_determined=False,
            proof_candidate_closed=False,
            active_goal_hash="",
            active_goal_preview="",
        )

    raw = state.raw_for_goal_tools
    active_hash = active_goal_hash_from_raw(raw)
    _, raw_remaining = extract_active_goal_block(raw)

    if state.num_remaining == REMAINING_UNKNOWN:
        num_remaining = None
        determined = False
    else:
        num_remaining = state.num_remaining
        determined = True

    proof_closed = bool(state.proof_candidate_closed or raw_remaining == 0)
    if proof_closed:
        num_remaining = 0
        determined = True
    if proof_closed:
        state_kind = "candidate_closed"
        goal_type = "complete"
    elif not determined:
        state_kind = UNKNOWN
        goal_type = UNKNOWN
    else:
        state_kind = "open"
        goal_type = UNKNOWN
    return GoalProjection(
        has_current=True,
        state_kind=state_kind,
        goal_type=goal_type,
        num_remaining=num_remaining,
        num_remaining_determined=determined,
        proof_candidate_closed=proof_closed,
        active_goal_hash=active_hash,
        active_goal_preview=_preview(raw),
        fact_source="pretty_goal_text",
        authority="display_only_text_projection",
        authority_rank=10,
    )


def _canonical_goal_hash_text(raw: str) -> str:
    """Canonicalize volatile EasyCrypt prompt text before hashing a goal.

    EC may leave the final ``[N|check]>`` prompt in ``current.out`` depending
    on how the state was reached (plain replay vs. checkpoint rewind).  The
    prompt is transport state, not proof state, so resume capsules must not
    drift merely because one path captured the prompt line and another did not.
    """
    return _EC_PROMPT_LINE_RE.sub("", str(raw or "")).rstrip()


def active_goal_hash_from_raw(raw: str) -> str:
    """Return the canonical active-goal identity used by projections.

    Resume and daemon-continuity code occasionally has only the raw EasyCrypt
    goal response available.  Keeping that fallback on this public helper
    prevents those paths from silently inventing a second hash algorithm or
    hashing volatile prompt text.
    """
    raw_text = str(raw or "")
    active_goal, remaining = extract_active_goal_block(raw_text)
    if remaining == 0:
        return ""
    canonical = _canonical_goal_hash_text(active_goal or raw_text)
    if not canonical.strip():
        return ""
    return hashlib.sha1(
        canonical.encode("utf-8", errors="replace")
    ).hexdigest()


def _normalize_post_qed_goal_projection(
    goal: GoalProjection,
    *,
    history: HistoryProjection,
    close_authority: CandidateCloseAuthorityProjection,
    transition: TransitionProjection,
    event_contract_ok: bool,
) -> GoalProjection:
    """Treat a saved ``qed.`` prompt as a closed proof candidate.

    After EC accepts ``qed.`` the latest prompt may contain no ``No more goals``
    marker, only ``[n|check]>``. The raw EC state is therefore indeterminate,
    but the event stream plus history already prove the candidate was closed
    before ``qed.`` was saved. Expose that as the canonical state so agents do
    not see a misleading ambient/unknown goal after finishing a proof.
    """
    if not (
        event_contract_ok
        and history.has_qed
        and close_authority.authoritative
        and transition.kind in {"qed_saved", "closed", "undo"}
        and not goal.proof_candidate_closed
        and not goal.num_remaining_determined
    ):
        return goal

    return GoalProjection(
        has_current=goal.has_current,
        state_kind="candidate_closed",
        goal_type="complete",
        num_remaining=0,
        num_remaining_determined=True,
        proof_candidate_closed=True,
        active_goal_hash="",
        active_goal_preview=(
            "No active goal: proof candidate was closed and `qed.` was saved."
        ),
        fact_source="session_event_projection",
        authority="event_contract_projection",
        authority_rank=80,
    )


def _build_candidate_close_authority(
    events: list[dict[str, Any]],
    *,
    transition: TransitionProjection,
    history: HistoryProjection,
) -> CandidateCloseAuthorityProjection:
    """Bind candidate closure to the exact current terminal occurrence."""

    semantic_indices = [
        index
        for index, event in enumerate(events)
        if event.get("type") in {"tactic.result", "tactic.undone"}
    ]
    if not semantic_indices:
        return CandidateCloseAuthorityProjection()
    latest_index = semantic_indices[-1]
    latest_event = events[latest_index]
    if latest_event.get("type") == "tactic.undone":
        return _undo_restored_close_authority(
            events,
            semantic_indices=semantic_indices,
            undo_index=latest_index,
            history=history,
        )
    if latest_event.get("type") != "tactic.result":
        return CandidateCloseAuthorityProjection()

    direct_close = _paired_candidate_close(events, latest_index)
    if direct_close is not None and transition.kind == "closed":
        return _candidate_close_authority(
            events,
            result_index=latest_index,
            close_index=direct_close,
            terminal_index=latest_index,
            kind="direct_close",
        )

    if transition.kind != "qed_saved" or not history.has_qed:
        return CandidateCloseAuthorityProjection()
    prior_indices = [index for index in semantic_indices if index < latest_index]
    if not prior_indices:
        return CandidateCloseAuthorityProjection()
    prior_index = prior_indices[-1]
    if events[prior_index].get("type") != "tactic.result":
        return CandidateCloseAuthorityProjection()
    prior_close = _paired_candidate_close(events, prior_index)
    if prior_close is None:
        return CandidateCloseAuthorityProjection()
    return _candidate_close_authority(
        events,
        result_index=prior_index,
        close_index=prior_close,
        terminal_index=latest_index,
        kind="post_qed_preserved_close",
    )


def _undo_restored_close_authority(
    events: list[dict[str, Any]],
    *,
    semantic_indices: list[int],
    undo_index: int,
    history: HistoryProjection,
) -> CandidateCloseAuthorityProjection:
    """Recognize one failed extra closer that was exactly undone.

    A closed compound command can be followed by a rejected standalone
    ``qed.`` which is nevertheless appended to history, then by one manager
    undo restoring the prior history. The undo is authoritative only when it
    names that exact intervening failed command and the resulting history is
    again closed; broader rewind histories fail closed.
    """
    if not history.has_qed:
        return CandidateCloseAuthorityProjection()
    undo_payload = event_payload(events[undo_index])
    if str(undo_payload.get("status") or "") != "ok":
        return CandidateCloseAuthorityProjection()
    undone_tactic = str(undo_payload.get("undone_tactic") or "").strip()
    remaining_steps = _as_optional_int(undo_payload.get("remaining_steps"))
    if not undone_tactic or remaining_steps != history.tactic_count:
        return CandidateCloseAuthorityProjection()
    prior_semantics = [index for index in semantic_indices if index < undo_index]
    if len(prior_semantics) < 2:
        return CandidateCloseAuthorityProjection()
    rejected_index = prior_semantics[-1]
    rejected = event_payload(events[rejected_index])
    if (
        events[rejected_index].get("type") != "tactic.result"
        or str(rejected.get("status") or "") != "error"
        or str(rejected.get("tactic") or "").strip() != undone_tactic
    ):
        return CandidateCloseAuthorityProjection()
    close_result_index = prior_semantics[-2]
    close_index = _paired_candidate_close(events, close_result_index)
    if close_index is None:
        return CandidateCloseAuthorityProjection()
    return _candidate_close_authority(
        events,
        result_index=close_result_index,
        close_index=close_index,
        terminal_index=undo_index,
        kind="undo_restored_close",
    )


def _paired_candidate_close(
    events: list[dict[str, Any]],
    result_index: int,
) -> int | None:
    result_payload = event_payload(events[result_index])
    if (
        events[result_index].get("type") != "tactic.result"
        or result_payload.get("status") != "ok"
        or result_payload.get("candidate_closed") is not True
    ):
        return None
    close_index = result_index + 1
    if close_index >= len(events):
        return None
    close = events[close_index]
    if close.get("type") != "proof.candidate_closed":
        return None
    close_payload = event_payload(close)
    result_tactic = str(result_payload.get("tactic") or "").strip()
    close_tactic = str(close_payload.get("tactic") or "").strip()
    if not result_tactic or not close_tactic or result_tactic != close_tactic:
        return None
    return close_index


def _candidate_close_authority(
    events: list[dict[str, Any]],
    *,
    result_index: int,
    close_index: int,
    terminal_index: int,
    kind: str,
) -> CandidateCloseAuthorityProjection:
    result_id = str(events[result_index].get("event_id") or "")
    close_id = str(events[close_index].get("event_id") or "")
    terminal_id = str(events[terminal_index].get("event_id") or "")
    if not result_id or not close_id or not terminal_id:
        return CandidateCloseAuthorityProjection()
    return CandidateCloseAuthorityProjection(
        kind=kind,
        close_result_event_id=result_id,
        close_event_id=close_id,
        terminal_event_id=terminal_id,
        close_result_sequence=result_index + 1,
        close_event_sequence=close_index + 1,
        terminal_event_sequence=terminal_index + 1,
    )


def _build_latest_transition(events: list[dict[str, Any]]) -> TransitionProjection:
    latest_result: dict[str, Any] | None = None
    latest_undo: dict[str, Any] | None = None
    latest_result_idx = -1
    latest_undo_idx = -1

    for idx, event in enumerate(events):
        typ = event.get("type")
        if typ == "tactic.result":
            latest_result = event_payload(event)
            latest_result_idx = idx
        elif typ == "tactic.undone":
            latest_undo = event_payload(event)
            latest_undo_idx = idx

    if latest_undo is not None and latest_undo_idx > latest_result_idx:
        return TransitionProjection(
            kind="undo",
            tactic=str(latest_undo.get("undone_tactic") or ""),
            status=str(latest_undo.get("status") or ""),
            goals_after=_as_optional_int(latest_undo.get("remaining_steps")),
        )
    if latest_result is None:
        return TransitionProjection(kind="none")

    status = str(latest_result.get("status") or UNKNOWN)
    tactic = str(latest_result.get("tactic") or "")
    goals_before = _as_optional_int(latest_result.get("goals_before"))
    goals_after = _as_optional_int(latest_result.get("goals_after"))
    candidate_closed = bool(latest_result.get("candidate_closed"))
    no_progress = bool(latest_result.get("no_progress")) or status == "no_progress_reverted"
    history_committed = latest_result.get("history_committed")
    history_committed = history_committed if isinstance(history_committed, bool) else None
    kind = _classify_transition_kind(
        tactic=tactic,
        status=status,
        goals_before=goals_before,
        goals_after=goals_after,
        candidate_closed=candidate_closed,
        no_progress=no_progress,
        history_committed=history_committed,
    )
    return TransitionProjection(
        kind=kind,
        tactic=tactic,
        status=status,
        goals_before=goals_before,
        goals_after=goals_after,
        candidate_closed=candidate_closed,
        no_progress=no_progress,
        no_progress_reason=str(latest_result.get("no_progress_reason") or ""),
        history_committed=history_committed,
        latest_error=str(latest_result.get("latest_error") or ""),
    )


def _classify_transition_kind(
    *,
    tactic: str,
    status: str,
    goals_before: int | None,
    goals_after: int | None,
    candidate_closed: bool,
    no_progress: bool,
    history_committed: bool | None,
) -> str:
    if status == "refused":
        return "refused"
    if status == "error":
        return "error"
    if no_progress:
        return "no_progress"
    if candidate_closed or goals_after == 0:
        return "closed"
    if _is_qed_tactic(tactic) and status == "ok":
        return "qed_saved"
    if goals_before is not None and goals_after is not None:
        if goals_after > goals_before:
            return "decomposition"
        if goals_after < goals_before:
            return "progress"
        if history_committed:
            return "state_changed_same_goal_count"
        return "unchanged"
    if history_committed:
        return "committed_unknown_effect"
    return UNKNOWN


def _build_consistency(
    *,
    state: SessionState,
    history: HistoryProjection,
    events: EventContractProjection,
    close_authority: CandidateCloseAuthorityProjection,
    goal: GoalProjection,
    transition: TransitionProjection,
) -> ConsistencyProjection:
    errors: list[str] = []
    warnings: list[str] = []
    notes: list[str] = []

    state_is_determined_open = (
        state.has_current
        and goal.num_remaining_determined
        and not goal.proof_candidate_closed
    )
    state_is_indeterminate = (
        state.has_current
        and not goal.num_remaining_determined
        and not goal.proof_candidate_closed
    )
    if history.has_qed and state_is_determined_open:
        errors.append("history contains qed but current EC state is not closed")
    elif history.has_qed and state_is_indeterminate:
        notes.append(
            "history contains qed and current EC state is indeterminate",
        )
    current_event_closed = close_authority.authoritative
    if current_event_closed and state_is_determined_open:
        errors.append("event log says candidate_closed but current EC state is open")
    elif current_event_closed and state_is_indeterminate:
        notes.append(
            "event log says candidate_closed and current EC state is indeterminate",
        )
    if goal.proof_candidate_closed and events.exists and not current_event_closed:
        warnings.append("current EC state is closed but event log has no candidate close")
    if goal.proof_candidate_closed and not events.exists:
        warnings.append("current EC state is closed but event log is missing")

    if (
        transition.goals_after is not None
        and goal.num_remaining_determined
        and goal.num_remaining is not None
        and transition.kind != "undo"
        and transition.goals_after != goal.num_remaining
    ):
        warnings.append(
            "latest tactic event goals_after differs from current EC state "
            f"({transition.goals_after} != {goal.num_remaining})",
        )

    return ConsistencyProjection(
        ok=not errors,
        errors=errors,
        warnings=warnings,
        notes=notes,
    )


def _project_status(
    *,
    goal: GoalProjection,
    events: EventContractProjection,
    transition: TransitionProjection,
    history: HistoryProjection,
    goals_discharged: bool,
    offline_verified: bool,
) -> str:
    if offline_verified:
        return VERIFIED
    if goals_discharged:
        return (
            SESSION_CLOSED_PENDING_VERIFICATION
            if history.has_qed
            else GOALS_DISCHARGED_PENDING_QED
        )
    if goal.proof_candidate_closed:
        return CLOSED_UNTRUSTED
    if not goal.has_current:
        return NO_CURRENT
    if transition.latest_error and transition.kind == "error":
        return ERROR
    if goal.state_kind == UNKNOWN:
        return UNKNOWN
    return OPEN


def _preview(raw: str, limit: int = 1200) -> str:
    text = raw.strip()
    if len(text) <= limit:
        return text
    return text[:limit] + "\n..."


def _as_optional_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        if value == REMAINING_UNKNOWN:
            return None
        return value
    return None


def _is_qed_tactic(tactic: str) -> bool:
    return tactic.strip().lower().rstrip(".").strip() == "qed"
