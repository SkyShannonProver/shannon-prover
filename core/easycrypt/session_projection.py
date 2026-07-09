"""Canonical proof-state projection for EasyCrypt sessions.

This module is the read-only boundary that joins the three factual sources
available for an interactive proof session:

* ``current.out`` / ``prev.out`` via :mod:`session_state`
* append-only JSONL session events via :mod:`session_events`
* active-goal structure via :mod:`ec_goal_parser`

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

from core.easycrypt.analysis.ec_goal_parser import (
    REMAINING_UNKNOWN as PARSER_REMAINING_UNKNOWN,
    goal_to_json,
    parse_goal,
)
from core.easycrypt.analysis.ec_native_state import (
    annotate_goal_fallback,
    annotate_program_fallback,
    goal_authority,
    has_program_fields,
    load_native_goal_fact,
    load_native_program_fact,
    merge_native_goal_fact,
    merge_native_program_fact,
    native_remaining,
)
from core.easycrypt.session_goal_context import (
    extract_module_keywords,
    scan_pr_bridge_lemmas,
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
    read_session_state,
)


UNKNOWN = "unknown"
_EC_PROMPT_LINE_RE = re.compile(r"(?m)^\[\d+\|[^\]\n]*\]>\s*$")


@dataclass(frozen=True)
class HistoryProjection:
    path: str
    exists: bool
    tactic_count: int
    has_qed: bool
    latest_tactic: str = ""

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
    latest_error: str = ""
    latest_error_tactic: str = ""
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
            "latest_error": self.latest_error,
            "latest_error_tactic": self.latest_error_tactic,
            "latest_attempt": dict(self.latest_attempt),
            "recent_failed_attempts": list(self.recent_failed_attempts),
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
    authority: str = "pretty_text_fallback"
    authority_rank: int = 10
    ec_ground_truth: bool = False
    native_artifact: str = ""
    parser_error: str = ""
    parsed_goal: dict[str, Any] = field(default_factory=dict)

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
            "ec_ground_truth": self.ec_ground_truth,
            "native_artifact": self.native_artifact,
            "parser_error": self.parser_error,
            "parsed_goal": dict(self.parsed_goal),
        }
        if include_raw:
            data["active_goal_text"] = raw_text
        return data


@dataclass(frozen=True)
class TransitionProjection:
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
    candidate_ready: bool
    final_ready: bool
    history: HistoryProjection
    events: EventContractProjection
    goal: GoalProjection
    latest_transition: TransitionProjection
    consistency: ConsistencyProjection

    def to_dict(
        self,
        *,
        include_raw: bool = False,
        active_goal_text: str = "",
    ) -> dict[str, Any]:
        return {
            "session_dir": self.session_dir,
            "status": self.status,
            "candidate_ready": self.candidate_ready,
            "final_ready": self.final_ready,
            "history": self.history.to_dict(),
            "events": self.events.to_dict(),
            "goal": self.goal.to_dict(
                include_raw=include_raw,
                raw_text=active_goal_text,
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
) -> ProofStateProjection:
    """Read a session directory into one canonical proof-state projection."""
    path = Path(session_dir)
    state = read_session_state(
        path,
        Path(current_path) if current_path is not None else None,
        Path(previous_path) if previous_path is not None else None,
    )
    events, event_json_errors = _read_events_strict(path / EVENTS_FILENAME)
    contract_events = _without_live_tool_called(events, live_tool_name)
    history = _read_history(path / "history.ec")
    event_projection = _build_event_projection(
        path / EVENTS_FILENAME,
        contract_events,
        event_json_errors,
    )
    transition = _build_latest_transition(contract_events)
    goal_projection = _build_goal_projection(state)
    goal_projection = _normalize_post_qed_goal_projection(
        goal_projection,
        history=history,
        events=event_projection,
        transition=transition,
    )
    consistency = _build_consistency(
        state=state,
        history=history,
        events=event_projection,
        goal=goal_projection,
        transition=transition,
    )
    candidate_ready = bool(
        event_projection.ok
        and event_projection.candidate_closed
        and (goal_projection.proof_candidate_closed or history.has_qed)
        and consistency.ok
    )
    final_ready = bool(
        candidate_ready
        and event_projection.verification_status == "pass"
    )
    status = _project_status(
        goal=goal_projection,
        events=event_projection,
        transition=transition,
        history=history,
        final_ready=final_ready,
    )
    return ProofStateProjection(
        session_dir=str(path.resolve()),
        status=status,
        candidate_ready=candidate_ready,
        final_ready=final_ready,
        history=history,
        events=event_projection,
        goal=goal_projection,
        latest_transition=transition,
        consistency=consistency,
    )


def projection_to_dict(
    session_dir: str | Path,
    *,
    include_raw: bool = False,
    live_tool_name: str | None = None,
) -> dict[str, Any]:
    """Convenience JSON-ready wrapper around :func:`read_proof_state_projection`."""
    projection = read_proof_state_projection(
        session_dir,
        live_tool_name=live_tool_name,
    )
    active_goal_text = ""
    if include_raw:
        state = read_session_state(Path(session_dir))
        active_goal_text = state.raw_for_goal_tools
    return projection.to_dict(
        include_raw=include_raw,
        active_goal_text=active_goal_text,
    )


def projection_to_goal_info(projection: ProofStateProjection) -> dict[str, Any]:
    """Compact projection payload safe to embed in ``-goal-info`` JSON."""
    # bd-hoare/phoare: surface the post + probability BOUND explicitly so a phoare
    # goal is never reported as a bound-less hoare `post = true` (PBound audit).
    _pg = projection.goal.parsed_goal if isinstance(projection.goal.parsed_goal, dict) else {}
    _phoare_extra: dict[str, Any] = {}
    if _pg.get("goal_type") == "phoare":
        if _pg.get("phoare_bound"):
            _phoare_extra["phoare_bound"] = _pg["phoare_bound"]
        if _pg.get("post"):
            _phoare_extra["post"] = _pg["post"]
    elif _pg.get("goal_type") == "hoare":
        # a literally-`true` postcondition is a REAL trivial obligation, distinct
        # from a parse failure that left the post empty — surface it so the agent
        # trusts it (and reaches for `auto`/`trivial`, not `smt`/`bypr`).
        if _pg.get("post"):
            _phoare_extra["post"] = _pg["post"]
        if _pg.get("trivial_postcondition"):
            _phoare_extra["trivial_postcondition"] = True
    return {
        "status": projection.status,
        "candidate_ready": projection.candidate_ready,
        "final_ready": projection.final_ready,
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
            "ec_ground_truth": projection.goal.ec_ground_truth,
            "native_artifact": projection.goal.native_artifact,
            **_phoare_extra,
        },
        "history": {
            "tactic_count": projection.history.tactic_count,
            "has_qed": projection.history.has_qed,
            "latest_tactic": projection.history.latest_tactic,
        },
        "latest_transition": projection.latest_transition.to_dict(),
        "event_contract": {
            "ok": projection.events.ok,
            "exists": projection.events.exists,
            "event_count": projection.events.event_count,
            "candidate_closed": projection.events.candidate_closed,
            "verification_status": projection.events.verification_status,
            "error_count": len(projection.events.errors),
            "warning_count": len(projection.events.warnings),
            "latest_error": projection.events.latest_error,
            "latest_error_tactic": projection.events.latest_error_tactic,
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


def _read_history(path: Path) -> HistoryProjection:
    if not path.exists():
        return HistoryProjection(
            path=str(path),
            exists=False,
            tactic_count=0,
            has_qed=False,
        )
    lines = [
        line.strip()
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
        if line.strip()
    ]
    has_qed = any(line.lower().rstrip(".").strip() == "qed" for line in lines)
    return HistoryProjection(
        path=str(path),
        exists=True,
        tactic_count=len(lines),
        has_qed=has_qed,
        latest_tactic=lines[-1] if lines else "",
    )


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
    2. a READ-ONLY action (e.g. a ``try`` probe, ``goal-info``, ``tactic-forms``)
       whose handler raised or was killed between the two emits (the exception path
       re-raises without emitting ``tool.result``), leaving a stale dangling call
       that poisons the NEXT commit's contract — the observed "probe accepted,
       commit rejected (event contract is not valid)" MISLABEL of a successful
       commit.

    A dangling MUTATING call (``next``/``chain``/``prev``) is genuine and still
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
        latest_error=summary.latest_error.error,
        latest_error_tactic=summary.latest_error.tactic,
        latest_attempt=(
            summary.latest_attempt.to_dict()
            if summary.latest_attempt is not None else {}
        ),
        recent_failed_attempts=[
            attempt.to_dict()
            for attempt in summary.recent_failed_attempts[:5]
        ],
    )


def _build_goal_projection(state: SessionState) -> GoalProjection:
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
    hash_text = _canonical_goal_hash_text(raw)
    active_hash = hashlib.sha1(hash_text.encode("utf-8", errors="replace")).hexdigest()
    parsed: dict[str, Any] = {}
    parser_error = ""
    parser_remaining = PARSER_REMAINING_UNKNOWN
    parser_goal_type = UNKNOWN
    try:
        info = parse_goal(raw)
        parsed = goal_to_json(
            info,
            pr_rewrite_candidates=(
                _projection_pr_rewrite_candidates(state, info, raw) or None
            ),
        )
        parser_remaining = info.num_remaining
        parser_goal_type = parsed.get("goal_type") or info.goal_type or UNKNOWN
    except Exception as exc:
        parser_error = f"{type(exc).__name__}: {exc}"

    parsed = annotate_goal_fallback(parsed)
    native_goal = load_native_goal_fact(state.session_dir, active_hash)
    if native_goal:
        parsed = merge_native_goal_fact(parsed, native_goal)
    native_program = load_native_program_fact(state.session_dir, active_hash)
    if not native_program and native_goal and has_program_fields(native_goal):
        native_program = native_goal
    if native_program:
        parsed = merge_native_program_fact(parsed, native_program)
    else:
        parsed = annotate_program_fallback(parsed)

    native_count, native_count_determined = native_remaining(parsed)
    if native_count_determined:
        num_remaining = native_count
        determined = True
    elif state.num_remaining == REMAINING_UNKNOWN:
        num_remaining = None
        determined = False
    else:
        num_remaining = state.num_remaining
        determined = True

    proof_closed = bool(state.proof_candidate_closed)
    if parsed.get("ec_ground_truth") and "proof_candidate_closed" in parsed:
        proof_closed = bool(parsed.get("proof_candidate_closed"))
    if proof_closed:
        state_kind = "candidate_closed"
        goal_type = "complete"
    elif not determined:
        state_kind = str(parsed.get("state_kind") or UNKNOWN)
        goal_type = str(parsed.get("goal_type") or parser_goal_type or UNKNOWN)
    else:
        state_kind = str(parsed.get("state_kind") or "open")
        goal_type = str(parsed.get("goal_type") or parser_goal_type or UNKNOWN)

    if parser_remaining != PARSER_REMAINING_UNKNOWN:
        parsed.setdefault("parser_num_remaining", parser_remaining)
    parsed.setdefault("state_num_remaining", num_remaining)
    if native_count_determined:
        parsed.setdefault("native_num_remaining", native_count)
        parsed["num_remaining"] = native_count
        parsed["num_remaining_determined"] = True

    authority = goal_authority(parsed)

    return GoalProjection(
        has_current=True,
        state_kind=state_kind,
        goal_type=goal_type,
        num_remaining=num_remaining,
        num_remaining_determined=determined,
        proof_candidate_closed=proof_closed,
        active_goal_hash=active_hash,
        active_goal_preview=_preview(raw),
        fact_source=authority["fact_source"],
        authority=authority["authority"],
        authority_rank=authority["authority_rank"],
        ec_ground_truth=authority["ec_ground_truth"],
        native_artifact=authority["native_artifact"],
        parser_error=parser_error,
        parsed_goal=parsed,
    )


def _canonical_goal_hash_text(raw: str) -> str:
    """Canonicalize volatile EasyCrypt prompt text before hashing a goal.

    EC may leave the final ``[N|check]>`` prompt in ``current.out`` depending
    on how the state was reached (plain replay vs. checkpoint rewind).  The
    prompt is transport state, not proof state, so resume capsules must not
    drift merely because one path captured the prompt line and another did not.
    """
    return _EC_PROMPT_LINE_RE.sub("", str(raw or "")).rstrip()


def _projection_pr_rewrite_candidates(
    state: SessionState,
    info: Any,
    raw_goal: str,
) -> list[dict[str, Any]]:
    if getattr(info, "goal_type", "") != "probability":
        return []
    if getattr(info, "prob_form", "") not in {
        "eq", "ineq", "diff_eq", "compound",
        "adv_eq", "adv_diff_ineq", "adv_ineq",
    }:
        return []
    keywords = extract_module_keywords(info)
    if not keywords:
        return []

    session_dir = Path(state.session_dir)
    search_dirs: list[Path] = []
    include_file = session_dir / "include_dirs.txt"
    try:
        for line in include_file.read_text(encoding="utf-8").splitlines():
            path = Path(line.strip())
            if path.is_dir() and path not in search_dirs:
                search_dirs.append(path)
    except Exception:
        pass

    active_lemma = ""
    source_file: Path | None = None
    meta_path = session_dir / "session_meta.json"
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
        active_lemma = str(meta.get("lemma") or "")
        raw_source = meta.get("file") or meta.get("source_file")
        if raw_source:
            source_file = Path(str(raw_source)).expanduser().resolve()
            if source_file.parent.is_dir() and source_file.parent not in search_dirs:
                search_dirs.append(source_file.parent)
    except Exception:
        source_file = None

    if not search_dirs:
        return []
    context_file = session_dir / "context.ec"
    search_files = [context_file] if context_file.exists() else []
    return scan_pr_bridge_lemmas(
        search_dirs,
        keywords,
        goal_text=raw_goal,
        search_files=search_files,
        allow_local_files=search_files,
        excluded_names={active_lemma} if active_lemma else set(),
        excluded_files={source_file} if source_file else set(),
    )


def _normalize_post_qed_goal_projection(
    goal: GoalProjection,
    *,
    history: HistoryProjection,
    events: EventContractProjection,
    transition: TransitionProjection,
) -> GoalProjection:
    """Treat a saved ``qed.`` prompt as a closed proof candidate.

    After EC accepts ``qed.`` the latest prompt may contain no ``No more goals``
    marker, only ``[n|check]>``. The raw EC state is therefore indeterminate,
    but the event stream plus history already prove the candidate was closed
    before ``qed.`` was saved. Expose that as the canonical state so agents do
    not see a misleading ambient/unknown goal after finishing a proof.
    """
    if not (
        history.has_qed
        and events.candidate_closed
        and transition.kind in {"qed_saved", "closed"}
        and not goal.proof_candidate_closed
        and not goal.num_remaining_determined
    ):
        return goal

    parsed = {
        "goal_type": "complete",
        "num_remaining": 0,
        "num_remaining_determined": True,
        "parser_num_remaining": 0,
        "state_num_remaining": 0,
        "post_qed_projection": True,
        "fact_source": "session_event_projection",
        "authority": "event_contract_projection",
        "authority_rank": 80,
        "ec_ground_truth": False,
        "native_artifact": "",
        "warnings": [],
    }
    return GoalProjection(
        has_current=goal.has_current,
        state_kind="candidate_closed",
        goal_type="complete",
        num_remaining=0,
        num_remaining_determined=True,
        proof_candidate_closed=True,
        active_goal_hash=goal.active_goal_hash,
        active_goal_preview=(
            "No active goal: proof candidate was closed and `qed.` was saved."
        ),
        fact_source="session_event_projection",
        authority="event_contract_projection",
        authority_rank=80,
        ec_ground_truth=False,
        native_artifact="",
        parser_error=goal.parser_error,
        parsed_goal=parsed,
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
    goal: GoalProjection,
    transition: TransitionProjection,
) -> ConsistencyProjection:
    errors: list[str] = []
    warnings: list[str] = []
    notes: list[str] = []

    if goal.parser_error:
        warnings.append(f"goal parser failed: {goal.parser_error}")
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
    if events.candidate_closed and state_is_determined_open:
        errors.append("event log says candidate_closed but current EC state is open")
    elif events.candidate_closed and state_is_indeterminate:
        notes.append(
            "event log says candidate_closed and current EC state is indeterminate",
        )
    if state.proof_candidate_closed and events.exists and not events.candidate_closed:
        warnings.append("current EC state is closed but event log has no candidate close")
    if state.proof_candidate_closed and not events.exists:
        warnings.append("current EC state is closed but event log is missing")

    parser_remaining = goal.parsed_goal.get("parser_num_remaining")
    if (
        isinstance(parser_remaining, int)
        and goal.num_remaining_determined
        and goal.num_remaining is not None
        and parser_remaining != goal.num_remaining
    ):
        errors.append(
            "session_state remaining count differs from goal parser "
            f"({goal.num_remaining} != {parser_remaining})",
        )

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
    final_ready: bool,
) -> str:
    if final_ready:
        return "verified"
    if events.candidate_closed and history.has_qed:
        return "candidate_closed"
    if goal.proof_candidate_closed:
        return "candidate_closed"
    if not goal.has_current:
        return "no_current"
    # ``events.latest_error`` is a historical audit field: it records the most
    # recent failed tactic anywhere in the stream.  A later accepted tactic must
    # return the proof to ``open`` while the old failure remains available via
    # ``latest_errors`` with temporal_scope=prior_attempt.
    if events.latest_error and transition.kind == "error":
        return "error"
    if goal.state_kind == UNKNOWN:
        return UNKNOWN
    return "open"


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
