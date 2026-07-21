"""Full event-native proof context artifact for prover agents.

ToolView is intentionally per-tool: it records what one inspection tool saw
and recommended. ProofContextView is the next layer up. It reads the canonical
proof-state projection, recent ToolView artifacts, structured diagnostics, and
compiler phase analysis, then persists the full current-state context envelope.

The important contract is freshness: active recommendations must either be tied
to the current active goal hash or to the latest proof-state transition. Older
recommendations remain visible as stale/debug context, but they are not mixed
into the active next-step list.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core.easycrypt.validation_result import ValidationResult

from core.easycrypt.session_events import (
    EVENTS_FILENAME,
    event_payload,
    read_events,
)
from core.easycrypt.session_placeholders import requires_placeholder_instantiation
from core.easycrypt.session_projection import (
    projection_to_goal_info,
    read_proof_state_projection,
)
from core.easycrypt.session_state import read_session_state
from core.easycrypt.session_tool_view import EVIDENCE_BUCKETS
from core.easycrypt.session_prover_actions import (
    build_prover_actions,
    prover_contract_for_recommendation,
    validate_prover_actions,
)
from core.easycrypt.analysis.ec_proof_ir import (
    build_proof_ir,
    proof_ir_notes,
)


PROOF_CONTEXT_VIEW_SCHEMA_VERSION = 1
PROOF_CONTEXT_VIEW_KIND = "proof_context_view"
LEGACY_AGENT_PROOF_VIEW_KIND = "agent_proof_view"
PROOF_CONTEXT_VIEW_KINDS = {
    PROOF_CONTEXT_VIEW_KIND,
    LEGACY_AGENT_PROOF_VIEW_KIND,
}
_CLOSED_STATUSES = {"candidate_closed", "verified"}


class ProofContextViewValidation(ValidationResult):
    """Canonical errors/warnings result under this view's public name."""



@dataclass
class _GuidanceSource:
    source_kind: str
    source_name: str
    event_id: str
    event_index: int
    recommendations: list[dict[str, Any]]
    evidence: dict[str, Any]
    proof_status: str = ""
    goal_hash: str = ""
    artifact: str = ""
    view_hash: str = ""
    errors: list[dict[str, Any]] = field(default_factory=list)
    notes: list[dict[str, Any]] = field(default_factory=list)


# proof_so_far is no longer inlined in the per-turn prompt — it is written to the
# LEGAL_PROOF_SO_FAR file and read on demand — so it need not be budget-truncated.
# Keep a generous cap (any real proof is far under this) so the file is complete.
_PROOF_SO_FAR_HEAD = 1000
_PROOF_SO_FAR_TAIL = 1000


def _committed_tactics_from_history(path: Path) -> list[str]:
    """The node's committed tactics (``history.ec`` lines). Read core-side so the
    agent view does not depend on the workflow layer's reader."""
    try:
        lines = (path / "history.ec").read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    return [ln.strip() for ln in lines if ln.strip()]


def _proof_so_far(path: Path) -> dict[str, Any]:
    """A persistent, step-numbered view of the agent's OWN committed proof.

    History was previously kept out of the view, so a context-respawned agent was
    blind to its own work and re-derived the skeleton from scratch (the audited
    fresh_restart waste). Surfacing it lets the agent orient and reference a
    specific step to revise. Long proofs elide the middle; the opener and the
    recent tail (the usual revision targets) are always shown.
    """
    tactics = _committed_tactics_from_history(path)
    n = len(tactics)
    if n == 0:
        return {
            "committed_count": 0,
            "steps": [],
            "elided_count": 0,
            "note": "You have not committed any tactics in this node yet.",
        }
    numbered: list[dict[str, Any]] = [
        {"step": i, "tactic": t} for i, t in enumerate(tactics, start=1)
    ]
    elided = 0
    if n > _PROOF_SO_FAR_HEAD + _PROOF_SO_FAR_TAIL + 1:
        elided = n - _PROOF_SO_FAR_HEAD - _PROOF_SO_FAR_TAIL
        numbered = (
            numbered[:_PROOF_SO_FAR_HEAD]
            + [{"step": None, "tactic": f"... ({elided} steps elided) ..."}]
            + numbered[-_PROOF_SO_FAR_TAIL:]
        )
    return {
        "committed_count": n,
        "steps": numbered,
        "elided_count": elided,
        "note": (
            "Your committed proof so far in THIS node, step-numbered — your own "
            "work. Use it to orient; do not re-derive steps already listed here."
        ),
    }


def build_proof_context_view(
    session_dir: str | Path,
    *,
    live_tool_name: str | None = "agent-view",
    include_goal_text: bool = False,
    max_recommendations: int = 12,
    max_stale_recommendations: int = 12,
) -> dict[str, Any]:
    """Build one JSON-ready full context view for the current proof state."""
    path = Path(session_dir)
    projection = read_proof_state_projection(
        path,
        live_tool_name=live_tool_name,
    )
    proof_state = projection_to_goal_info(projection)
    state = read_session_state(path)
    current_goal = projection.goal.to_dict(
        include_raw=include_goal_text,
        raw_text=_bounded(state.raw_for_goal_tools, 24000),
    )
    events = _events_without_live_call(read_events(path), live_tool_name)
    latest_window = _latest_tactic_window(events)
    current_hash = str(
        proof_state.get("goal", {}).get("active_goal_hash") or ""
        if isinstance(proof_state.get("goal"), dict) else ""
    )
    status = str(proof_state.get("status") or "")

    evidence = _empty_evidence()
    evidence["event"].append({
        "id": "event.proof_state_projection",
        "producer": "session_projection",
        "status": status,
        "goal_hash": current_hash,
        "event_contract": proof_state.get("event_contract"),
        "latest_transition": proof_state.get("latest_transition"),
    })

    errors = _projection_errors(proof_state)
    notes = _projection_notes(proof_state)
    latest_errors = _latest_errors(proof_state)
    diagnostic_history = _diagnostic_history(proof_state, latest_errors)
    proof_ir: dict[str, Any] = {}
    active_recs: list[dict[str, Any]] = []
    stale_recs: list[dict[str, Any]] = []
    debug_refs = {
        "session_dir": str(path.resolve()),
        "event_log": str((path / EVENTS_FILENAME).resolve()),
        "source_event_ids": [],
        "tool_view_artifacts": [],
        "diagnostic_event_ids": [],
        "stale_recommendation_count": 0,
        "ignored_recommendation_count": 0,
    }

    seen_active: set[tuple[str, str, str]] = set()
    seen_stale: set[tuple[str, str, str]] = set()
    for source in _iter_guidance_sources(path, events):
        if source.source_kind == "tool_view" and source.artifact:
            debug_refs["tool_view_artifacts"].append(source.artifact)
        if source.source_kind == "diagnostic":
            debug_refs["diagnostic_event_ids"].append(source.event_id)
        if source.event_id:
            debug_refs["source_event_ids"].append(source.event_id)
        freshness = _classify_freshness(
            source=source,
            current_goal_hash=current_hash,
            proof_status=status,
            latest_window=latest_window,
        )
        active = freshness in {
            "active_goal_hash",
            "latest_transition",
            "post_latest_transition",
        }
        if active:
            for item in source.errors[:3]:
                errors.append(_message(
                    code=f"source.{source.source_kind}.error",
                    message=str(item.get("message") or item),
                    source_event_id=source.event_id,
                ))
            for item in source.notes[:3]:
                if _is_aggregate_suppressed_note(item):
                    continue
                notes.append(_message(
                    code=f"source.{source.source_kind}.note",
                    message=str(item.get("message") or item),
                    source_event_id=source.event_id,
                ))
        for rec in source.recommendations:
            normalized = _normalize_recommendation(
                rec,
                source=source,
                freshness=freshness,
                current_goal_hash=current_hash,
            )
            key = (
                normalized.get("producer", ""),
                normalized.get("kind", ""),
                normalized.get("action", ""),
            )
            if active:
                if key in seen_active:
                    continue
                seen_active.add(key)
                _merge_evidence(evidence, source, active_only=True)
                if len(active_recs) < max_recommendations:
                    active_recs.append(normalized)
                else:
                    debug_refs["ignored_recommendation_count"] += 1
            else:
                debug_refs["stale_recommendation_count"] += 1
                if key in seen_stale:
                    continue
                seen_stale.add(key)
                if len(stale_recs) < max_stale_recommendations:
                    stale_recs.append(normalized)

    active_recs, suppressed_preflight_count = _suppress_verified_duplicate_preflights(
        active_recs,
    )
    proof_ir = _build_proof_ir_for_view(
        path,
        proof_state=proof_state,
        current_goal=current_goal,
        external_recommendations=active_recs,
    )
    if proof_ir:
        # ProofIR no longer injects ranked recommendations into the agent view:
        # the candidate moves, signature/declaration lookups, and call-invariant
        # inputs are sourced from the factual `candidate_menu` directly downstream
        # (ranker removal, step 2b). Only ProofIR's diagnostic notes are folded in.
        for note in proof_ir_notes(proof_ir):
            notes.append(_message(
                code=str(note.get("code") or "proof_ir.note"),
                message=str(note.get("message") or ""),
                severity=str(note.get("severity") or "info"),
            ))
    if proof_ir:
        evidence["deterministic"].append({
            "id": "proof_ir.handle_liveness",
            "producer": "ec_proof_ir.build_proof_ir",
            "goal_hash": current_hash,
            "current_layer": proof_ir.get("current_layer"),
            "goal_kind": proof_ir.get("goal_kind"),
            "resource_summary": (
                proof_ir.get("phase", {}).get("resource_summary")
                if isinstance(proof_ir.get("phase"), dict) else {}
            ),
        })
    debug_refs["suppressed_preflight_recommendation_count"] = suppressed_preflight_count

    if status in _CLOSED_STATUSES and active_recs:
        errors.append(_message(
            code="agent_view.closed_has_recommendations",
            message="closed proof_state cannot expose active recommendations",
        ))
        stale_recs = active_recs + stale_recs
        debug_refs["stale_recommendation_count"] += len(active_recs)
        active_recs = []

    active_recs = _attach_prover_contracts(active_recs)

    safe_next_actions = _safe_next_actions(
        proof_state=proof_state,
        recommendations=active_recs,
        latest_errors=latest_errors,
    )
    actions = build_prover_actions(
        session_dir=path,
        proof_state=proof_state,
        recommendations=active_recs,
        safe_next_actions=safe_next_actions,
        latest_errors=latest_errors,
        command_ok=True,
    )

    view: dict[str, Any] = {
        "schema_version": PROOF_CONTEXT_VIEW_SCHEMA_VERSION,
        "kind": PROOF_CONTEXT_VIEW_KIND,
        "ok": True,
        "proof_state": proof_state,
        "current_goal": current_goal,
        "proof_so_far": _proof_so_far(path),
        "proof_ir": proof_ir,
        "latest_transition": proof_state.get("latest_transition") or {},
        "guidance": {
            "recommendations": active_recs,
            "stale_recommendations": stale_recs,
            "stale_recommendation_count": int(
                debug_refs["stale_recommendation_count"]
            ),
        },
        "evidence": evidence,
        "diagnostic_history": diagnostic_history,
        "latest_errors": latest_errors,
        "safe_next_actions": safe_next_actions,
        "actions": actions,
        "notes": notes,
        "errors": errors,
        "debug_refs": debug_refs,
    }
    validation = validate_proof_context_view(view)
    if validation.errors:
        view["errors"] = list(view["errors"]) + [
            _message(code="agent_view.invalid", message=err)
            for err in validation.errors
        ]
    if validation.warnings:
        view["notes"] = list(view["notes"]) + [
            _message(code="agent_view.warning", message=warn)
            for warn in validation.warnings
        ]
    view["ok"] = not view["errors"]
    return view



def _attach_prover_contracts(
    recommendations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for rec in recommendations:
        if not isinstance(rec, dict):
            continue
        item = dict(rec)
        if not isinstance(item.get("prover_contract"), dict):
            item["prover_contract"] = prover_contract_for_recommendation(item)
        out.append(item)
    return out


def write_proof_context_view_artifact(
    session_dir: str | Path,
    view: dict[str, Any],
) -> dict[str, Any]:
    """Persist a ProofContextView and return the compact event payload."""
    path = Path(session_dir)
    data = dict(view)
    validation = validate_proof_context_view(data)
    text = json.dumps(data, indent=2, sort_keys=True)
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()
    out_dir = path / "proof_context_views"
    out_dir.mkdir(parents=True, exist_ok=True)
    artifact = out_dir / f"proof_context_view_{digest[:16]}.json"
    artifact.write_text(text + "\n", encoding="utf-8")

    proof_state = data.get("proof_state") if isinstance(
        data.get("proof_state"), dict,
    ) else {}
    goal = proof_state.get("goal") if isinstance(
        proof_state.get("goal"), dict,
    ) else {}
    guidance = data.get("guidance") if isinstance(data.get("guidance"), dict) else {}
    recs = guidance.get("recommendations") if isinstance(guidance, dict) else []
    stale = guidance.get("stale_recommendations") if isinstance(
        guidance, dict,
    ) else []
    debug_refs = data.get("debug_refs") if isinstance(
        data.get("debug_refs"), dict,
    ) else {}
    return {
        "schema_version": int(data.get("schema_version") or 0),
        "view_kind": str(data.get("kind") or ""),
        "ok": bool(data.get("ok")) and validation.ok,
        "artifact": str(artifact),
        "view_hash": digest,
        "proof_status": str(proof_state.get("status") or ""),
        "goal_hash": str(goal.get("active_goal_hash") or ""),
        "recommendation_count": len(recs) if isinstance(recs, list) else 0,
        "stale_recommendation_count": (
            len(stale) if isinstance(stale, list) else 0
        ),
        "error_count": len(data.get("errors") or []) + len(validation.errors),
        "warning_count": len(validation.warnings),
        "source_event_count": len(debug_refs.get("source_event_ids") or []),
    }



def record_proof_context_view(
    session_or_dir: Any,
    view: dict[str, Any],
    *,
    source: str = "session_cli",
) -> dict[str, Any]:
    """Write a ProofContextView artifact and emit the legacy event name."""
    session_dir = getattr(session_or_dir, "dir", session_or_dir)
    payload = write_proof_context_view_artifact(session_dir, view)
    emit = getattr(session_or_dir, "emit_event", None)
    if callable(emit):
        emit("agent.view.produced", payload, source=source)
    return payload



def validate_proof_context_view(
    data: dict[str, Any],
) -> ProofContextViewValidation:
    errors: list[str] = []
    warnings: list[str] = []
    required = {
        "schema_version": int,
        "kind": str,
        "ok": bool,
        "proof_state": dict,
        "current_goal": dict,
        "latest_transition": dict,
        "guidance": dict,
        "evidence": dict,
        "latest_errors": list,
        "safe_next_actions": list,
        "actions": list,
        "notes": list,
        "errors": list,
        "debug_refs": dict,
    }
    for key, typ in required.items():
        if key not in data:
            errors.append(f"missing field `{key}`")
            continue
        if not isinstance(data[key], typ):
            errors.append(
                f"field `{key}` expected {typ.__name__}, "
                f"got {type(data[key]).__name__}"
            )
    if data.get("schema_version") != PROOF_CONTEXT_VIEW_SCHEMA_VERSION:
        errors.append(
            f"schema_version must be {PROOF_CONTEXT_VIEW_SCHEMA_VERSION}, "
            f"got {data.get('schema_version')!r}"
        )
    if data.get("kind") not in PROOF_CONTEXT_VIEW_KINDS:
        errors.append(
            f"kind must be {PROOF_CONTEXT_VIEW_KIND!r} "
            f"(legacy {LEGACY_AGENT_PROOF_VIEW_KIND!r} is accepted)"
        )

    proof_state = data.get("proof_state") if isinstance(
        data.get("proof_state"), dict,
    ) else {}
    goal = proof_state.get("goal") if isinstance(
        proof_state.get("goal"), dict,
    ) else {}
    current_hash = str(goal.get("active_goal_hash") or "")
    status = str(proof_state.get("status") or "")
    guidance = data.get("guidance") if isinstance(data.get("guidance"), dict) else {}
    recs = guidance.get("recommendations") if isinstance(guidance, dict) else []
    stale = guidance.get("stale_recommendations") if isinstance(
        guidance, dict,
    ) else []
    if not isinstance(recs, list):
        errors.append("guidance.recommendations must be a list")
        recs = []
    if not isinstance(stale, list):
        errors.append("guidance.stale_recommendations must be a list")
        stale = []
    if status in _CLOSED_STATUSES and recs:
        errors.append("closed proof_state cannot have active recommendations")
    for idx, rec in enumerate(recs):
        _validate_recommendation(
            rec,
            f"guidance.recommendations[{idx}]",
            errors,
            warnings,
            current_goal_hash=current_hash,
            require_fresh=True,
        )
    for idx, rec in enumerate(stale):
        _validate_recommendation(
            rec,
            f"guidance.stale_recommendations[{idx}]",
            errors,
            warnings,
            current_goal_hash=current_hash,
            require_fresh=False,
        )

    evidence = data.get("evidence")
    if isinstance(evidence, dict):
        for bucket, items in evidence.items():
            if bucket not in EVIDENCE_BUCKETS:
                warnings.append(f"unknown evidence bucket `{bucket}`")
            if not isinstance(items, list):
                errors.append(f"evidence.{bucket} must be a list")
                continue
            for idx, item in enumerate(items):
                if not isinstance(item, dict):
                    errors.append(f"evidence.{bucket}[{idx}] must be an object")
                elif not item.get("id"):
                    warnings.append(f"evidence.{bucket}[{idx}] has no id")
    action_validation = validate_prover_actions(data.get("actions", []), label="actions")
    errors.extend(action_validation.errors)
    warnings.extend(action_validation.warnings)
    for field_name in ("latest_errors", "safe_next_actions", "actions", "notes", "errors"):
        items = data.get(field_name)
        if isinstance(items, list):
            for idx, item in enumerate(items):
                if not isinstance(item, dict):
                    errors.append(f"{field_name}[{idx}] must be an object")
    return ProofContextViewValidation(errors=errors, warnings=warnings)



def _iter_guidance_sources(
    session_dir: Path,
    events: list[dict[str, Any]],
) -> list[_GuidanceSource]:
    sources: list[_GuidanceSource] = []
    for idx, event in enumerate(events, start=1):
        typ = str(event.get("type") or "")
        payload = event_payload(event)
        event_id = str(event.get("event_id") or "")
        if typ == "tool.view.produced":
            source = _source_from_tool_view_event(
                session_dir, payload, event_id, idx,
            )
            if source is not None:
                sources.append(source)
        elif typ == "diagnostic.emitted":
            recs = payload.get("recommendations") or []
            if not isinstance(recs, list) or not recs:
                continue
            evidence = payload.get("evidence") if isinstance(
                payload.get("evidence"), dict,
            ) else {}
            sources.append(_GuidanceSource(
                source_kind="diagnostic",
                source_name=str(payload.get("source") or "diagnostic"),
                event_id=event_id,
                event_index=idx,
                recommendations=[dict(r) for r in recs if isinstance(r, dict)],
                evidence=dict(evidence),
                goal_hash=_extract_goal_hash(payload),
                errors=_coerce_messages(payload.get("errors") or []),
                notes=_coerce_messages(payload.get("notes") or []),
            ))
    sources.sort(key=lambda item: item.event_index, reverse=True)
    return sources


def _source_from_tool_view_event(
    session_dir: Path,
    payload: dict[str, Any],
    event_id: str,
    event_index: int,
) -> _GuidanceSource | None:
    artifact_raw = str(payload.get("artifact") or "")
    if not artifact_raw:
        return None
    artifact = Path(artifact_raw)
    if not artifact.exists() and not artifact.is_absolute():
        artifact = session_dir / artifact
    try:
        data = json.loads(artifact.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    guidance = data.get("guidance") if isinstance(data.get("guidance"), dict) else {}
    recs = guidance.get("recommendations") if isinstance(guidance, dict) else []
    if not isinstance(recs, list) or not recs:
        return None
    proof_state = data.get("proof_state") if isinstance(
        data.get("proof_state"), dict,
    ) else {}
    evidence = data.get("evidence") if isinstance(data.get("evidence"), dict) else {}
    return _GuidanceSource(
        source_kind="tool_view",
        source_name=str(data.get("tool") or payload.get("tool") or "tool"),
        event_id=event_id,
        event_index=event_index,
        recommendations=[dict(r) for r in recs if isinstance(r, dict)],
        evidence=dict(evidence),
        proof_status=str(proof_state.get("status") or ""),
        goal_hash=_extract_goal_hash(data),
        artifact=str(artifact),
        view_hash=str(payload.get("view_hash") or ""),
        errors=_coerce_messages(data.get("errors") or []),
        notes=_coerce_messages(data.get("notes") or []),
    )


def _normalize_recommendation(
    rec: dict[str, Any],
    *,
    source: _GuidanceSource,
    freshness: str,
    current_goal_hash: str,
) -> dict[str, Any]:
    source_key = _source_key(source)
    original_id = str(rec.get("id") or "recommendation")
    evidence_refs = [
        _prefixed_ref(source_key, ref)
        for ref in (rec.get("evidence_refs") or [])
        if isinstance(ref, str) and ref
    ]
    source_refs = [
        dict(ref) for ref in (rec.get("source_refs") or [])
        if isinstance(ref, dict)
    ]
    source_refs.append({
        "kind": source.source_kind,
        "id": source.event_id,
        "title": source.source_name,
        "details": {
            "artifact": source.artifact,
            "view_hash": source.view_hash,
            "event_index": source.event_index,
        },
    })
    metadata = dict(rec.get("metadata") or {})
    action_type = str(rec.get("action_type") or metadata.get("action_type") or "")
    metadata.update({
        "original_id": original_id,
        "source_kind": source.source_kind,
        "source_name": source.source_name,
        "source_event_id": source.event_id,
        "source_event_index": source.event_index,
        "source_goal_hash": source.goal_hash,
        "current_goal_hash": current_goal_hash,
        "freshness": freshness,
    })
    if action_type:
        metadata["action_type"] = action_type
    preconditions = [
        str(item) for item in (rec.get("preconditions") or [])
        if isinstance(item, str) and item
    ]
    if current_goal_hash and freshness == "active_goal_hash":
        preconditions.append(
            f"proof_state.goal.active_goal_hash == {current_goal_hash}"
        )
    item = {
        "id": f"{source_key}.{_safe_id(original_id)}",
        "kind": str(rec.get("kind") or "guidance"),
        "producer": str(rec.get("producer") or source.source_name),
        "action": str(rec.get("action") or ""),
        "why": str(rec.get("why") or "Structured guidance source matched."),
        "confidence": str(rec.get("confidence") or "medium"),
        "preconditions": preconditions,
        "source_refs": source_refs,
        "evidence_refs": evidence_refs,
        "metadata": metadata,
    }
    if action_type:
        item["action_type"] = action_type
    return item


def _merge_evidence(
    target: dict[str, list[dict[str, Any]]],
    source: _GuidanceSource,
    *,
    active_only: bool,
) -> None:
    if not active_only:
        return
    source_key = _source_key(source)
    for bucket, items in source.evidence.items():
        if not isinstance(items, list):
            continue
        out = target.setdefault(bucket, [])
        existing = {
            str(item.get("id") or "") for item in out if isinstance(item, dict)
        }
        for idx, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            copied = dict(item)
            old_id = str(copied.get("id") or f"{bucket}.{idx}")
            copied["id"] = _prefixed_ref(source_key, old_id)
            copied.setdefault("source_event_id", source.event_id)
            copied.setdefault("source_name", source.source_name)
            if copied["id"] in existing:
                continue
            existing.add(copied["id"])
            out.append(copied)


def _classify_freshness(
    *,
    source: _GuidanceSource,
    current_goal_hash: str,
    proof_status: str,
    latest_window: tuple[int, int],
) -> str:
    if proof_status in _CLOSED_STATUSES:
        return "closed_proof"
    if source.goal_hash and current_goal_hash:
        if source.goal_hash == current_goal_hash:
            return "active_goal_hash"
        return "stale_goal_hash"
    submit_idx, result_idx = latest_window
    if source.source_kind == "diagnostic" and submit_idx <= source.event_index <= result_idx:
        return "latest_transition"
    if result_idx >= 0 and source.event_index > result_idx:
        return "post_latest_transition"
    return "unknown_or_stale"


def _suppress_verified_duplicate_preflights(
    recommendations: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    verified_tactics = {
        str(rec.get("action") or "").strip()
        for rec in recommendations
        if _recommendation_action_type(rec) == "runnable_tactic"
        and (
            str(rec.get("confidence") or "") == "verified"
            or str(_recommendation_metadata(rec).get("epistemic_status") or "")
                == "easycrypt_preflight_accepted"
        )
    }
    if not verified_tactics:
        return recommendations, 0

    out: list[dict[str, Any]] = []
    suppressed = 0
    for rec in recommendations:
        action = str(rec.get("action") or "").strip()
        if (
            action in verified_tactics
            and _recommendation_action_type(rec) == "tactic_candidate"
        ):
            suppressed += 1
            continue
        out.append(rec)
    return out, suppressed


def _is_aggregate_suppressed_note(item: dict[str, Any]) -> bool:
    return str(item.get("code") or "") in {"try.state_unchanged"}


def _recommendation_action_type(rec: dict[str, Any]) -> str:
    metadata = _recommendation_metadata(rec)
    return str(rec.get("action_type") or metadata.get("action_type") or "")


def _recommendation_metadata(rec: dict[str, Any]) -> dict[str, Any]:
    metadata = rec.get("metadata")
    return dict(metadata) if isinstance(metadata, dict) else {}


def _latest_tactic_window(events: list[dict[str, Any]]) -> tuple[int, int]:
    result_idx = -1
    submit_idx = -1
    for idx in range(len(events), 0, -1):
        if events[idx - 1].get("type") == "tactic.result":
            result_idx = idx
            break
    if result_idx < 0:
        return (-1, -1)
    for idx in range(result_idx - 1, 0, -1):
        if events[idx - 1].get("type") == "tactic.submitted":
            submit_idx = idx
            break
    return (submit_idx, result_idx)


def _extract_goal_hash(data: dict[str, Any]) -> str:
    proof_state = data.get("proof_state") if isinstance(
        data.get("proof_state"), dict,
    ) else {}
    goal = proof_state.get("goal") if isinstance(
        proof_state.get("goal"), dict,
    ) else {}
    if goal.get("active_goal_hash"):
        return str(goal.get("active_goal_hash") or "")
    evidence = data.get("evidence") if isinstance(data.get("evidence"), dict) else {}
    for items in evidence.values():
        if not isinstance(items, list):
            continue
        for item in items:
            if isinstance(item, dict) and item.get("active_goal_hash"):
                return str(item.get("active_goal_hash") or "")
    debug = data.get("debug") if isinstance(data.get("debug"), dict) else {}
    if debug.get("active_goal_hash"):
        return str(debug.get("active_goal_hash") or "")
    return ""


def _safe_next_actions(
    *,
    proof_state: dict[str, Any],
    recommendations: list[dict[str, Any]],
    latest_errors: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    status = str(proof_state.get("status") or "")
    goal = proof_state.get("goal") if isinstance(
        proof_state.get("goal"), dict,
    ) else {}
    goal_type = str(goal.get("goal_type") or "unknown")
    event_contract = proof_state.get("event_contract") if isinstance(
        proof_state.get("event_contract"), dict,
    ) else {}
    if status == "verified":
        return [{
            "id": "proof.verified",
            "kind": "none",
            "why": "The proof-state projection is already verified.",
        }]
    if status == "candidate_closed":
        return [{
            "id": "proof.verify",
            "kind": "verify",
            "tool": "verify",
            "why": "The proof candidate is closed; run verification next.",
        }]
    if not event_contract.get("ok", True):
        return [{
            "id": "inspect.event_contract",
            "kind": "inspect",
            "tool": "status",
            "why": "The event contract has errors; inspect status before acting.",
        }]
    structural_errors = [
        e for e in latest_errors if e.get("origin") == "structural"
    ]
    if structural_errors:
        return [{
            "id": "inspect.structural_error",
            "kind": "diagnose",
            "tool": "diagnose",
            "why": (
                "Structural error in the event stream (origin="
                "structural); the session may be unhealthy."
            ),
        }]
    # Tactic-audit-only errors mean the last commit or private preflight
    # failed — that's normal proof iteration. We surface them via
    # ``latest_errors`` for transparency but do NOT preempt the
    # recommendation queue with a singleton ``diagnose`` action; if
    # the queue has no positive recommendations either, fall through
    # to the legacy behavior so the agent still has a deterministic
    # next step.
    current_or_unscoped_errors = [
        e for e in latest_errors
        if str(e.get("temporal_scope") or "current_attempt") != "prior_attempt"
    ]
    if current_or_unscoped_errors and not recommendations:
        return [{
            "id": "inspect.latest_error",
            "kind": "diagnose",
            "tool": "diagnose",
            "why": (
                "The latest tactic recorded an error and there are no "
                "verified recommendations to commit; consult diagnose."
            ),
        }]
    if recommendations:
        actions: list[dict[str, Any]] = []
        positive_recs = [
            rec for rec in recommendations
            if _recommendation_action_type(rec) != "avoid_action"
        ]
        for idx, rec in enumerate(positive_recs[:3]):
            action = str(rec.get("action") or "")
            action_type = _recommendation_action_type(rec)
            metadata = _recommendation_metadata(rec)
            epistemic_status = str(
                metadata.get("epistemic_status")
                or rec.get("epistemic_status")
                or ""
            )
            requires_instantiation = bool(
                rec.get("requires_instantiation")
                or metadata.get("requires_instantiation")
                or _requires_instantiation(action)
            )
            verified_commit = (
                action_type == "runnable_tactic"
                and (
                    str(rec.get("confidence") or "") == "verified"
                    or epistemic_status == "easycrypt_preflight_accepted"
                )
            )
            verified_chain = (
                action_type == "inspection_action"
                and action.strip().startswith("-chain")
                and (
                    str(rec.get("confidence") or "") == "verified"
                    or epistemic_status == "daemon_chain_accepted"
                )
            )
            if requires_instantiation:
                kind = "consider_strategy_hint"
                recommended_tool = ""
                state_changed = False
            elif verified_commit or verified_chain:
                kind = "commit_recommendation"
                recommended_tool = "chain" if verified_chain else "next"
                state_changed = True
            elif action_type in {"tactic_candidate", "runnable_tactic"}:
                kind = "consider_strategy_hint"
                recommended_tool = ""
                state_changed = False
            else:
                kind = "consider_recommendation"
                recommended_tool = ""
                state_changed = False
            contract = _dict_or_empty(
                rec.get("prover_contract")
            ) or prover_contract_for_recommendation(rec)
            item = {
                "id": f"use.recommendation.{idx}",
                "kind": kind,
                "recommendation_id": str(rec.get("id") or ""),
                "action": action,
                "confidence": str(rec.get("confidence") or ""),
                "why": _safe_action_why(kind),
                "action_type": action_type,
                "epistemic_status": epistemic_status,
                "state_changed": state_changed,
                "prover_contract": contract,
            }
            if recommended_tool:
                item["recommended_tool"] = recommended_tool
            if requires_instantiation:
                item["requires_instantiation"] = True
            actions.append(item)
        return actions
    # 鸡肋 blocks 2 & 6: this row is the SOLE manual entry point to the bridge / goal-info
    # producer when the recommendation queue is empty (the rich handle is deduped away on
    # these goals), so KEEP the row — but the old "No fresh recommendation is available …"
    # why-string was a dead label that added words and no information. Replace it with neutral
    # menu copy describing what the inspect returns (re-audit §6). A step that genuinely NEEDS
    # a named bridge lemma here (i67/i60) is missed demand served by a separate ADD, not this.
    if goal_type in {"pRHL", "equiv"}:
        return [{
            "id": "inspect.bridge_or_align",
            "kind": "inspect",
            "tool": "bridge-lemmas",
            "why": "Inspect bridge / alignment candidates for this equivalence goal.",
        }]
    if goal_type in {"ambient", "probability", "phoare", "hoare"}:
        return [{
            "id": "inspect.goal_info",
            "kind": "inspect",
            "tool": "goal-info",
            "why": "Parse the current goal — its shape, resolved names, and hypotheses.",
        }]
    return [{
        "id": "inspect.agent_view",
        "kind": "inspect",
        "tool": "agent-view",
        "why": "Refresh the aggregate view after the next proof-state change.",
    }]


def _safe_action_why(kind: str) -> str:
    if kind == "commit_recommendation":
        return (
            "A verified recommendation is available; committing will mutate "
            "the proof state."
        )
    if kind == "consider_strategy_hint":
        return (
            "Fresh structured context is available, but it needs reasoning or "
            "instantiation before execution."
        )
    return (
        "Fresh structured guidance is available; treat it as context unless "
        "its contract says it is a verified commit."
    )


def _requires_instantiation(action: str) -> bool:
    return requires_placeholder_instantiation(action)


def _validate_recommendation(
    rec: Any,
    label: str,
    errors: list[str],
    warnings: list[str],
    *,
    current_goal_hash: str,
    require_fresh: bool,
) -> None:
    if not isinstance(rec, dict):
        errors.append(f"{label} must be an object")
        return
    for key in ("id", "kind", "producer", "action", "why", "confidence"):
        if key not in rec:
            errors.append(f"{label} missing `{key}`")
        elif not isinstance(rec[key], str):
            errors.append(f"{label}.{key} must be a string")
        elif key in ("id", "kind", "producer", "action") and not rec[key].strip():
            errors.append(f"{label}.{key} must be non-empty")
    if rec.get("confidence") not in (
        None, "", "low", "medium", "high", "verified",
    ):
        warnings.append(f"{label}.confidence has unusual value {rec.get('confidence')!r}")
    for key in ("preconditions", "source_refs", "evidence_refs"):
        if key in rec and not isinstance(rec[key], list):
            errors.append(f"{label}.{key} must be a list")
    if not rec.get("source_refs") and not rec.get("evidence_refs"):
        errors.append(f"{label} must have source_refs or evidence_refs")
    metadata = rec.get("metadata")
    if not isinstance(metadata, dict):
        errors.append(f"{label}.metadata must be an object")
        metadata = {}
    freshness = str(metadata.get("freshness") or "")
    if require_fresh and freshness.startswith("stale"):
        errors.append(f"{label} is stale but appears in active recommendations")
    if require_fresh and freshness in {"unknown_or_stale", "closed_proof"}:
        errors.append(f"{label} has non-active freshness `{freshness}`")
    source_hash = str(metadata.get("source_goal_hash") or "")
    if (
        require_fresh
        and source_hash
        and current_goal_hash
        and source_hash != current_goal_hash
    ):
        errors.append(f"{label} source_goal_hash does not match current goal")


def _events_without_live_call(
    events: list[dict[str, Any]],
    live_tool_name: str | None,
) -> list[dict[str, Any]]:
    if not live_tool_name or not events:
        return events
    pending_idx: int | None = None
    for idx, event in enumerate(events):
        payload = event_payload(event)
        if event.get("type") == "tool.called" and payload.get("name") == live_tool_name:
            pending_idx = idx
        elif (
            event.get("type") == "tool.result"
            and payload.get("name") == live_tool_name
            and pending_idx is not None
        ):
            pending_idx = None
    if pending_idx is None:
        return events
    return events[:pending_idx] + events[pending_idx + 1:]


def _empty_evidence() -> dict[str, list[dict[str, Any]]]:
    return {bucket: [] for bucket in EVIDENCE_BUCKETS}


def _build_proof_ir_for_view(
    session_dir: Path,
    *,
    proof_state: dict[str, Any],
    current_goal: dict[str, Any],
    external_recommendations: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    try:
        return build_proof_ir(
            session_dir=session_dir,
            proof_state=proof_state,
            current_goal=current_goal,
            external_recommendations=external_recommendations or [],
        )
    except Exception as exc:
        return {
            "schema_version": 1,
            "kind": "easycrypt_proof_ir",
            "current_layer": "unknown",
            "goal_kind": "unknown",
            "goal_type": "unknown",
            "resources": {
                "program_ir": {},
                "pr_path_plan": {},
                "call_sites": [],
                "handles": {},
                "name_resolution": {},
                "instantiation_bindings": {},
            },
            "liveness": {},
            "destructive_moves": [],
            "phase": {},
            "candidate_menu": [],
            "diagnostics": [{
                "code": "proof_ir.build_failed",
                "severity": "info",
                "message": f"ProofIR analysis failed: {exc}",
            }],
        }


def _projection_errors(proof_state: dict[str, Any]) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    event_contract = proof_state.get("event_contract")
    if isinstance(event_contract, dict) and not event_contract.get("ok", True):
        for msg in event_contract.get("errors") or []:
            errors.append(_message(
                code="proof_state.event_contract",
                message=str(msg),
            ))
    consistency = proof_state.get("consistency")
    if isinstance(consistency, dict) and not consistency.get("ok", True):
        for msg in consistency.get("errors") or []:
            errors.append(_message(
                code="proof_state.consistency",
                message=str(msg),
            ))
    return errors


def _projection_notes(proof_state: dict[str, Any]) -> list[dict[str, Any]]:
    notes: list[dict[str, Any]] = []
    consistency = proof_state.get("consistency")
    if isinstance(consistency, dict):
        for msg in consistency.get("notes") or []:
            notes.append(_message(
                code="proof_state.consistency.note",
                message=str(msg),
            ))
        for msg in consistency.get("warnings") or []:
            notes.append(_message(
                code="proof_state.consistency.warning",
                message=str(msg),
            ))
    return notes


def _latest_errors(proof_state: dict[str, Any]) -> list[dict[str, Any]]:
    """Project the *latest tactic-level error* into a uniform list.

    Each entry is tagged with an ``origin`` field that classifies its
    source:

      * ``"tactic_audit"`` — the last committed or privately validated
        tactic produced an error message. This is NORMAL proof
        iteration: ``apply foo.`` may fail with ``unknown lemma`` and
        the agent simply tries something else. It is NOT a session-
        corruption signal.
      * ``"structural"`` — the underlying event stream itself is
        broken (JSON parsing failed, event_contract invariants
        violated, daemon crashed). This DOES mean the session is
        unhealthy and the agent should prefer ``diagnose`` /
        ``status`` over committing more tactics.

    Why the tag matters: prior to this distinction,
    ``_safe_next_actions`` would override the entire recommendation
    queue with ``inspect.latest_error`` whenever ANY latest_errors
    entry existed — so a single failed ``-try`` from the agent itself
    looked indistinguishable from "session is broken, restart". A
    Tree-mode worker on ChaChaPoly step1 (2026-05-03) misread that
    signal and tried to ``rm -rf`` its session dir. Tagging origin
    lets ``_safe_next_actions`` treat the two cases differently.
    """
    out: list[dict[str, Any]] = []
    event_contract = proof_state.get("event_contract")
    if isinstance(event_contract, dict):
        latest_attempt = _dict_or_empty(event_contract.get("latest_attempt"))
        current_attempt_id = str(latest_attempt.get("event_id") or "")
        current_attempt_status = str(latest_attempt.get("status") or "")
        current_attempt_tactic = str(latest_attempt.get("tactic") or "")
        current_attempt_error = str(latest_attempt.get("error") or "").strip()
        recent_failures = [
            _dict_or_empty(item)
            for item in event_contract.get("recent_failed_attempts") or []
            if isinstance(item, dict)
        ]
        if recent_failures:
            failure = recent_failures[0]
            failure_error = str(failure.get("error") or "").strip()
            failure_id = str(failure.get("event_id") or "")
            is_current = bool(
                failure_error
                and failure_id
                and current_attempt_id
                and failure_id == current_attempt_id
            )
            if failure_error:
                out.append({
                    "code": (
                        "current_tactic_error" if is_current
                        else "prior_tactic_error"
                    ),
                    "message": failure_error,
                    "tactic": str(failure.get("tactic") or ""),
                    "origin": "tactic_audit",
                    "severity": "noise",
                    "temporal_scope": (
                        "current_attempt" if is_current else "prior_attempt"
                    ),
                    "attempt_kind": str(failure.get("attempt_kind") or ""),
                    "attempt_status": str(failure.get("status") or ""),
                    "attempt_event_id": failure_id,
                    "current_attempt_status": current_attempt_status,
                    "current_attempt_tactic": current_attempt_tactic,
                    "relation_to_current_attempt": (
                        "this_error_belongs_to_current_attempt" if is_current
                        else "stale_unrelated_to_current_attempt"
                    ),
                })
        latest = str(event_contract.get("latest_error") or "").strip()
        if latest and not any(item.get("message") == latest for item in out):
            # Compatibility fallback for older event projections that
            # predate attempt provenance. Mark it as history, not as a
            # naked current error, unless the latest attempt itself
            # carries the same error.
            is_current = bool(current_attempt_error and latest == current_attempt_error)
            out.append({
                "code": (
                    "current_tactic_error" if is_current
                    else "prior_tactic_error"
                ),
                "message": latest,
                "tactic": str(event_contract.get("latest_error_tactic") or ""),
                "origin": "tactic_audit",
                "severity": "noise",
                "temporal_scope": (
                    "current_attempt" if is_current else "prior_attempt"
                ),
                "current_attempt_status": current_attempt_status,
                "current_attempt_tactic": current_attempt_tactic,
                "relation_to_current_attempt": (
                    "this_error_belongs_to_current_attempt" if is_current
                    else "stale_unrelated_to_current_attempt"
                ),
            })
    transition = proof_state.get("latest_transition")
    if isinstance(transition, dict):
        latest = str(transition.get("latest_error") or "").strip()
        if latest and not any(item.get("message") == latest for item in out):
            out.append({
                "code": "latest_transition_error",
                "message": latest,
                "tactic": str(transition.get("tactic") or ""),
                "origin": "tactic_audit",
                "severity": "noise",
                "temporal_scope": "prior_attempt",
                "relation_to_current_attempt": "no_attempt_provenance_available",
            })
    # Structural-corruption pass: when the event_contract itself flags
    # invariant violations (JSON parse failure, missing required event
    # types, empty stream when one was expected), promote those into
    # the same list with origin="structural" so callers can still
    # surface them, but distinguishably from tactic-audit noise.
    if isinstance(event_contract, dict) and not event_contract.get("ok", True):
        for msg in event_contract.get("errors") or []:
            text = str(msg).strip()
            if not text:
                continue
            if any(item.get("message") == text for item in out):
                continue
            out.append({
                "code": "event_contract_violation",
                "message": text,
                "tactic": "",
                "origin": "structural",
                "severity": "fatal",
            })
    return out


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _diagnostic_history(
    proof_state: dict[str, Any],
    latest_errors: list[dict[str, Any]],
) -> dict[str, Any]:
    event_contract = _dict_or_empty(proof_state.get("event_contract"))
    latest_attempt = _dict_or_empty(event_contract.get("latest_attempt"))
    recent_failures = [
        _dict_or_empty(item)
        for item in event_contract.get("recent_failed_attempts") or []
        if isinstance(item, dict)
    ][:5]
    current_error = str(latest_attempt.get("error") or "").strip()
    return {
        "current_attempt": latest_attempt,
        "current_error": current_error,
        "current_error_status": "present" if current_error else "none",
        "recent_failed_attempts": recent_failures,
        "latest_errors_temporal_scopes": [
            {
                "code": str(item.get("code") or ""),
                "temporal_scope": str(item.get("temporal_scope") or ""),
                "relation_to_current_attempt": str(
                    item.get("relation_to_current_attempt") or ""
                ),
                "tactic": str(item.get("tactic") or ""),
            }
            for item in latest_errors
        ],
        "policy": (
            "Errors without temporal_scope=current_attempt are historical "
            "diagnostics. They explain what failed before and must not be "
            "attributed to an accepted current command or private preflight."
        ),
    }


def is_audit_noise_only(latest_errors: list[dict[str, Any]]) -> bool:
    """Return True iff every entry in ``latest_errors`` is
    tactic-audit noise (the agent's own failed try/commit attempts).

    Callers use this to decide whether to escalate. Empty list is NOT
    audit-noise; it's "no errors at all", so this returns False (i.e.
    callers do not need to invoke their audit-noise branch on an
    empty list — they should fall through to the no-errors branch).
    """
    if not latest_errors:
        return False
    return all(
        (item.get("origin") or "tactic_audit") == "tactic_audit"
        for item in latest_errors
    )


def _coerce_messages(items: Any) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        return []
    out: list[dict[str, Any]] = []
    for idx, item in enumerate(items):
        if isinstance(item, dict):
            obj = dict(item)
            obj.setdefault("code", f"message.{idx}")
            obj.setdefault("message", "")
            out.append(obj)
        else:
            out.append(_message(code=f"message.{idx}", message=str(item)))
    return out


def _message(code: str, message: str, **extra: Any) -> dict[str, Any]:
    data = {"code": code, "message": message}
    for key, value in extra.items():
        if value not in (None, "", [], {}):
            data[key] = value
    return data


def _source_key(source: _GuidanceSource) -> str:
    event_part = source.event_id[:8] if source.event_id else str(source.event_index)
    return f"{source.source_kind}.{_safe_id(source.source_name)}.{event_part}"


def _prefixed_ref(prefix: str, ref: str) -> str:
    return f"{prefix}.{ref}"


def _safe_id(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", text).strip("_") or "item"


def _bounded(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "\n...[truncated]..."
