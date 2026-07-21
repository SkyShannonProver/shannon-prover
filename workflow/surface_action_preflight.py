"""Dynamic preflight facts for SurfaceModel actions.

Protocol/profile gating may expose a context action as a candidate.  Some
actions are useful only if a read-only backend check produces displayable
content for the *current* EasyCrypt state.  The manager owns that backend check;
this module owns the typed fact shape and result classifier.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from core.easycrypt.value_shapes import drop_empty as _drop_empty
from workflow.context_intents import intent_spec
from workflow.surface_action_choices import (
    call_invariants_from_text,
    call_subgoal_invariant_choices_for_view,
    inv_from_lemma_choices_for_view,
    is_placeholder,
)


PREFLIGHT_SCHEMA_VERSION = 2
PREFLIGHT_CANDIDATE_LIMIT = 4
DYNAMIC_PREFLIGHT_INTENTS = frozenset({
    "call_site_options",
    "pr_bridge_routes",
    "verified_pivot_options",
    "rewrite_candidates",
    "call_invariant_skeleton",
    "equiv_bridge_lemmas",
    "lemma_hints",
    "subgoal_gap",
    "inv_from_lemma",
    "call_subgoals",
})

_RUNNABLE_OR_VERIFIED_INTENTS = frozenset({
    "call_site_options",
    "pr_bridge_routes",
    "verified_pivot_options",
    "rewrite_candidates",
})

_SKELETON_INTENTS = frozenset({
    "call_invariant_skeleton",
})

_CONTEXT_CANDIDATE_INTENTS = frozenset({
    "equiv_bridge_lemmas",
    "lemma_hints",
    "inv_from_lemma",
})

_GAP_INTENTS = frozenset({
    "subgoal_gap",
})

_PREVIEW_INTENTS = frozenset({
    "call_subgoals",
})


def action_needs_dynamic_preflight(intent: str) -> bool:
    return str(intent or "").strip() in DYNAMIC_PREFLIGHT_INTENTS


def surface_preflight_candidates(view: dict[str, Any]) -> list[dict[str, Any]]:
    """Return protocol-visible actions that need manager-owned preflight."""
    handles = view.get("inspect_lookup_handles") if isinstance(view, dict) else {}
    asks = handles.get("ask_manager_for") if isinstance(handles, dict) else []
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for ask in asks or []:
        if not isinstance(ask, dict):
            continue
        action = dict(ask)
        intent = str(action.get("intent") or "").strip()
        spec = intent_spec(intent)
        if spec is None or not spec.advertised:
            continue
        if not action_needs_dynamic_preflight(intent):
            continue
        for candidate in _expanded_preflight_candidates(view, intent, _payload(action)):
            key = action_preflight_key(
                str(candidate.get("intent") or ""),
                _payload(candidate),
            )
            if key in seen:
                continue
            seen.add(key)
            out.append({
                "intent": str(candidate.get("intent") or ""),
                "payload": _payload(candidate),
            })
    return out


def action_preflight_key(intent: str, payload: dict[str, Any] | None = None) -> str:
    clean_payload = _stable_payload(payload or {})
    encoded = json.dumps(
        {"intent": str(intent or ""), "payload": clean_payload},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha1(encoded.encode("utf-8")).hexdigest()


def preflight_result_for_action(
    intent: str,
    payload: dict[str, Any] | None,
    action_summary: dict[str, Any] | None,
) -> dict[str, Any]:
    """Classify a hidden read-only manager action as surface-displayable or not."""
    payload = _stable_payload(payload or {})
    action = action_summary if isinstance(action_summary, dict) else {}
    observation = action.get("agent_observation")
    observation = observation if isinstance(observation, dict) else {}
    intent_name = str(intent or "")
    eligible, reason = _displayable_result(intent_name, observation, action)
    candidates = (
        _typed_candidate_evidence(_summary_content(action))
        if eligible
        else []
    )
    ready_count = sum(
        1 for candidate in candidates
        if isinstance(candidate.get("submit"), dict)
    )
    return _drop_empty({
        "intent": intent_name,
        "payload": payload,
        "key": action_preflight_key(intent_name, payload),
        "eligible": eligible,
        "reason": reason,
        "source": "manager_readonly_preflight",
        "backend_label": action.get("label"),
        "exit_code": action.get("exit_code"),
        "content_hash": _content_hash(observation.get("content")),
        "result_kind": (
            "ready_to_submit_candidates"
            if ready_count
            else "verified_candidates"
            if candidates
            else "displayable_context"
            if eligible
            else ""
        ),
        "candidate_count": len(candidates),
        "ready_submission_count": ready_count,
        "candidates": candidates,
    })


def attach_surface_action_preflight(
    view: dict[str, Any],
    results: list[dict[str, Any]],
) -> None:
    if not isinstance(view, dict):
        return
    view["surface_action_preflight"] = {
        "schema_version": PREFLIGHT_SCHEMA_VERSION,
        "results": [
            dict(item)
            for item in results
            if isinstance(item, dict) and item.get("intent")
        ],
    }


def preflight_result(
    view: dict[str, Any],
    intent: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    preflight = view.get("surface_action_preflight") if isinstance(view, dict) else {}
    results = preflight.get("results") if isinstance(preflight, dict) else []
    key = action_preflight_key(intent, payload or {})
    for item in results or []:
        if isinstance(item, dict) and item.get("key") == key:
            return dict(item)
    return {}


def preflight_candidate_evidence(
    view: dict[str, Any],
    intent: str,
    payload: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Return typed candidate evidence retained by current-state preflight.

    This is the canonical projection boundary for preflight output.  Surface
    composers must not recover executable candidates from legacy prose or raw
    ``candidate_moves`` values.
    """
    result = preflight_result(view, intent, payload or {})
    if not result.get("eligible"):
        return []
    return [
        dict(item)
        for item in result.get("candidates") or []
        if isinstance(item, dict) and str(item.get("candidate") or "").strip()
    ]


def matching_preflight_submission(
    view: dict[str, Any],
    intent: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Return the retained candidate whose submit payload matches exactly."""
    clean_payload = _stable_payload(payload)
    for result in _preflight_results(view):
        if not result.get("eligible"):
            continue
        source_intent = str(result.get("intent") or "")
        for candidate in result.get("candidates") or []:
            if not isinstance(candidate, dict):
                continue
            submit = candidate.get("submit")
            if not isinstance(submit, dict):
                continue
            if (
                str(submit.get("intent") or "") == intent
                and _stable_payload(_payload(submit)) == clean_payload
            ):
                return {
                    "source_intent": source_intent,
                    "candidate": dict(candidate),
                }
    return {}


def _displayable_result(
    intent: str,
    observation: dict[str, Any],
    action: dict[str, Any],
) -> tuple[bool, str]:
    if action.get("exit_code") not in (0, None):
        return False, "read-only preflight failed"
    content = observation.get("content")
    content = content if isinstance(content, dict) else {}
    if intent in _RUNNABLE_OR_VERIFIED_INTENTS:
        return _displayable_runnable_or_verified(intent, content)
    if intent in _SKELETON_INTENTS:
        return _displayable_skeleton(intent, content)
    if intent in _CONTEXT_CANDIDATE_INTENTS:
        return _displayable_context_candidates(intent, content)
    if intent in _GAP_INTENTS:
        return _displayable_gap(intent, content)
    if intent in _PREVIEW_INTENTS:
        return _displayable_preview(intent, content)
    if content:
        return True, "read-only preflight returned displayable content"
    return False, "preflight returned no displayable content"


def _typed_candidate_evidence(content: dict[str, Any]) -> list[dict[str, Any]]:
    items = content.get("items")
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        submit = _sanitized_submit(item.get("submit"))
        verification = str(item.get("verification") or "").strip()
        verified = (
            "daemon-verified" in verification.lower()
            and "not daemon-verified" not in verification.lower()
        )
        if not submit and not verified:
            continue
        candidate = str(item.get("candidate") or "").strip()
        if not candidate and submit.get("intent") == "commit_tactic":
            candidate = str(_payload(submit).get("tactic") or "").strip()
        if not candidate:
            continue
        clean = _drop_empty({
            "candidate": candidate,
            "why": _bounded_text(item.get("why")),
            "effect": _bounded_text(item.get("effect")),
            "verification": _bounded_text(verification),
            "submit": submit,
        })
        identity = json.dumps(
            submit or {"candidate": candidate},
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )
        if identity in seen:
            continue
        seen.add(identity)
        out.append(clean)
        if len(out) >= PREFLIGHT_CANDIDATE_LIMIT:
            break
    return out


def _sanitized_submit(value: Any) -> dict[str, Any]:
    submit = value if isinstance(value, dict) else {}
    intent = str(submit.get("intent") or "").strip()
    spec = intent_spec(intent)
    if spec is None or not spec.advertised:
        return {}
    payload = _payload(submit)
    allowed_fields = set(spec.payload_fields)
    if any(key not in allowed_fields for key in payload):
        return {}
    if spec.payload_fields and not payload:
        return {}
    if any(is_placeholder(value) for value in payload.values()):
        return {}
    return {"intent": intent, "payload": payload}


def _bounded_text(value: Any, limit: int = 800) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _preflight_results(view: dict[str, Any]) -> list[dict[str, Any]]:
    preflight = view.get("surface_action_preflight") if isinstance(view, dict) else {}
    results = preflight.get("results") if isinstance(preflight, dict) else []
    return [dict(item) for item in results or [] if isinstance(item, dict)]


def _expanded_preflight_candidates(
    view: dict[str, Any],
    intent: str,
    payload: dict[str, Any],
) -> list[dict[str, Any]]:
    if intent == "inv_from_lemma":
        lemma = str(payload.get("lemma") or "").strip()
        lemmas = (
            inv_from_lemma_choices_for_view(view)
            if is_placeholder(lemma)
            else [lemma] if _valid_choice_text(lemma) else []
        )
        return [
            {"intent": intent, "payload": {**payload, "lemma": lemma_name}}
            for lemma_name in lemmas
        ]
    if intent == "call_subgoals":
        invariant = str(payload.get("invariant") or "").strip()
        invariants = (
            call_subgoal_invariant_choices_for_view(view)
            if is_placeholder(invariant)
            else [invariant] if _valid_choice_text(invariant) else []
        )
        return [
            {"intent": intent, "payload": {**payload, "invariant": inv}}
            for inv in invariants
        ]
    return [{"intent": intent, "payload": payload}]


def derived_preflight_candidates(
    view: dict[str, Any],
    records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return second-pass candidates derived from first-pass preflight output."""
    if not _surface_requests_intent(view, "call_subgoals"):
        return []
    invariants: list[str] = []
    for record in records or []:
        intent = str(record.get("intent") or "")
        if intent not in {"call_invariant_skeleton", "inv_from_lemma"}:
            continue
        result = record.get("preflight_result")
        if not isinstance(result, dict) or not result.get("eligible"):
            continue
        summary = record.get("summary")
        content = _summary_content(summary if isinstance(summary, dict) else {})
        for inv in _invariants_from_content(content):
            if inv not in invariants:
                invariants.append(inv)
    return [
        {"intent": "call_subgoals", "payload": {"invariant": inv}}
        for inv in invariants[:4]
    ]


def _displayable_runnable_or_verified(
    intent: str,
    content: dict[str, Any],
) -> tuple[bool, str]:
    items = content.get("items")
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        if isinstance(item.get("submit"), dict):
            return True, f"preflight found a runnable {intent} option"
        verification = str(item.get("verification") or "").lower()
        if "not daemon-verified" in verification:
            continue
        if item.get("candidate") and "daemon-verified" in verification:
            return True, f"preflight found a daemon-verified {intent} option"
    notes = content.get("notes")
    note_codes = {
        str(note.get("code") or "")
        for note in notes if isinstance(note, dict)
    } if isinstance(notes, list) else set()
    if note_codes:
        return False, f"preflight returned non-actionable {intent} context"
    if content:
        return False, f"preflight returned context but no runnable/verified {intent} option"
    return False, f"preflight returned no displayable {intent} option"


def _displayable_skeleton(
    intent: str,
    content: dict[str, Any],
) -> tuple[bool, str]:
    items = content.get("items")
    saw_incomplete = False
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        if isinstance(item.get("submit"), dict):
            return True, f"preflight found a runnable {intent} skeleton"
        candidate = str(item.get("candidate") or "").strip()
        if candidate and not _candidate_needs_instantiation(candidate):
            return True, f"preflight found a readable {intent} skeleton"
        if candidate:
            saw_incomplete = True
    preview = str(content.get("preview") or content.get("result") or "").strip()
    if preview and "no matching context" not in preview.lower():
        return True, f"preflight found readable {intent} content"
    if saw_incomplete:
        return False, f"preflight returned only incomplete {intent} menus"
    if content:
        return False, f"preflight returned non-actionable {intent} context"
    return False, f"preflight returned no displayable {intent} skeleton"


def _displayable_context_candidates(
    intent: str,
    content: dict[str, Any],
) -> tuple[bool, str]:
    items = content.get("items")
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        candidate = str(item.get("candidate") or "").strip()
        if candidate and not _candidate_needs_instantiation(candidate):
            return True, f"preflight found concrete {intent} context"
    notes = content.get("notes")
    if isinstance(notes, list) and notes:
        return False, f"preflight returned no concrete {intent} candidates"
    preview = str(content.get("preview") or content.get("result") or "").strip()
    if preview and not _negative_preview(preview):
        return True, f"preflight found readable {intent} context"
    if content:
        return False, f"preflight returned non-actionable {intent} context"
    return False, f"preflight returned no displayable {intent} context"


def _displayable_gap(
    intent: str,
    content: dict[str, Any],
) -> tuple[bool, str]:
    items = content.get("items")
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        if str(item.get("candidate") or item.get("why") or "").strip():
            return True, f"preflight found a concrete {intent} gap"
    preview = str(content.get("preview") or content.get("result") or "").strip()
    if re.search(r"\bMISSING\b", preview):
        return True, f"preflight found a concrete {intent} gap"
    notes = content.get("notes")
    note_codes = {
        str(note.get("code") or "")
        for note in notes if isinstance(note, dict)
    } if isinstance(notes, list) else set()
    if note_codes:
        return False, f"preflight returned no concrete {intent} gap"
    if content:
        return False, f"preflight returned non-actionable {intent} context"
    return False, f"preflight returned no displayable {intent} gap"


def _displayable_preview(
    intent: str,
    content: dict[str, Any],
) -> tuple[bool, str]:
    preview = str(content.get("preview") or content.get("result") or "").strip()
    lowered = preview.lower()
    if not preview:
        return False, f"preflight returned no {intent} preview"
    if "rejected by daemon" in lowered or "was rejected" in lowered:
        return False, f"{intent} preview rejected the candidate"
    if "usage:" in lowered or "requires the daemon" in lowered or "could not sync" in lowered:
        return False, f"{intent} preview did not produce obligations"
    if "accepted by daemon" in lowered and "subgoal" in lowered:
        return True, f"preflight found a concrete {intent} obligation preview"
    if "active subgoal preview" in lowered:
        return True, f"preflight found a concrete {intent} obligation preview"
    return False, f"preflight returned no concrete {intent} obligations"


def _payload(action: dict[str, Any]) -> dict[str, Any]:
    payload = action.get("payload")
    return _stable_payload(payload if isinstance(payload, dict) else {})


def _stable_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        str(key): value
        for key, value in sorted(payload.items())
        if value not in (None, "", [], {})
    }


def _content_hash(content: Any) -> str:
    if content in (None, "", [], {}):
        return ""
    encoded = json.dumps(content, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha1(encoded.encode("utf-8")).hexdigest()


def _candidate_needs_instantiation(candidate: str) -> bool:
    text = str(candidate or "")
    return (
        "..." in text
        or "<" in text and ">" in text
        or "‹" in text and "›" in text
    )


def _negative_preview(text: str) -> bool:
    lowered = str(text or "").lower()
    return any(marker in lowered for marker in (
        "no matching context",
        "no bridge lemma",
        "no bridge lemma chain",
        "no relevant stdlib lemmas",
        "no stdlib lemmas",
        "no match",
        "no missing marker",
    ))


def _valid_choice_text(text: str) -> bool:
    value = str(text or "").strip()
    return bool(value and not is_placeholder(value) and "..." not in value)


def _surface_requests_intent(view: dict[str, Any], intent: str) -> bool:
    handles = view.get("inspect_lookup_handles") if isinstance(view, dict) else {}
    asks = handles.get("ask_manager_for") if isinstance(handles, dict) else []
    for ask in asks or []:
        if not isinstance(ask, dict):
            continue
        action = dict(ask)
        if str(action.get("intent") or "").strip() == intent:
            return True
    return False


def _summary_content(summary: dict[str, Any]) -> dict[str, Any]:
    observation = summary.get("agent_observation")
    observation = observation if isinstance(observation, dict) else {}
    content = observation.get("content")
    return content if isinstance(content, dict) else {}


def _invariants_from_content(content: dict[str, Any]) -> list[str]:
    texts: list[str] = []
    items = content.get("items")
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        texts.extend(str(item.get(key) or "") for key in ("candidate", "preview", "result"))
        submit = item.get("submit")
        submit = submit if isinstance(submit, dict) else {}
        payload = submit.get("payload")
        payload = payload if isinstance(payload, dict) else {}
        texts.append(str(payload.get("tactic") or ""))
    texts.extend(str(content.get(key) or "") for key in ("preview", "result"))
    out: list[str] = []
    for text in texts:
        for inv in call_invariants_from_text(text):
            if _valid_choice_text(inv) and inv not in out:
                out.append(inv)
    return out
