"""Structured prover-facing tool view contract.

The session event stream records state transitions. The proof-state projection
turns those events plus EC output into the current truth. ToolView is the next
boundary: it packages that truth with structured guidance and evidence so the
prover does not have to infer semantics from display text such as ``[AUTO-*]``
blocks.

Human-readable text is still useful as display/fallback, but it should live in
``debug`` or compatibility fields. New machine consumers should read:

* ``proof_state`` for authoritative proof/session state
* ``guidance.recommendations`` for suggested next actions
* ``evidence`` for why those suggestions were produced
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core.easycrypt.validation_result import ValidationResult


TOOL_VIEW_SCHEMA_VERSION = 1
EVIDENCE_BUCKETS = (
    "deterministic",
    "context",
    "epistemic",
    "kb",
    "retrieval",
    "probe",
    "event",
    "raw",
)
RECOMMENDATION_ACTION_TYPES = (
    "runnable_tactic",
    "probe_tactic",
    "inspection_action",
    "strategy_hint",
    "avoid_action",
    "warning",
)


_ACTION_REQUIRES_INSTANTIATION_RE = re.compile(
    r"<(?!:)[^>]+>|\bLEMMA\b|\boracle_name\b|\.\.\."
)


def action_requires_instantiation(action: str) -> bool:
    return bool(_ACTION_REQUIRES_INSTANTIATION_RE.search(action))


def legacy_display_mode(default: str = "full") -> str:
    return os.environ.get("SHANNON_LEGACY_DISPLAY", default).strip().lower()


def structured_tool_stdout(default_legacy_display: str = "full") -> bool:
    return legacy_display_mode(default_legacy_display) in {
        "off",
        "hide",
        "hidden",
        "none",
    }


def stdout_tool_view(
    view: dict,
    *,
    omit_raw_previews: bool = False,
) -> dict:
    data = json.loads(json.dumps(view))
    debug = data.get("debug")
    if isinstance(debug, dict):
        for key in list(debug):
            if key.startswith("legacy"):
                debug.pop(key, None)
    if omit_raw_previews:
        evidence = data.get("evidence")
        raw_items = evidence.get("raw") if isinstance(evidence, dict) else None
        if isinstance(raw_items, list):
            evidence["raw"] = [
                {
                    key: item[key]
                    for key in ("id", "format", "source_name", "source_event_id")
                    if isinstance(item, dict) and key in item
                } | {"preview_omitted": True}
                for item in raw_items
                if isinstance(item, dict)
            ]
    return data


def emit_tool_or_legacy(
    view: dict | None,
    legacy_text: str,
    *,
    omit_raw_previews: bool = False,
    default_legacy_display: str = "full",
) -> None:
    if structured_tool_stdout(default_legacy_display) and isinstance(view, dict):
        sys.stdout.write(
            json.dumps(
                stdout_tool_view(view, omit_raw_previews=omit_raw_previews),
                indent=2,
            ) + "\n"
        )
        return
    sys.stdout.write(legacy_text)


class ToolViewValidation(ValidationResult):
    """Canonical errors/warnings result under this view's public name."""


@dataclass(frozen=True)
class SourceRef:
    kind: str
    id: str = ""
    path: str = ""
    line: int | None = None
    title: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"kind": self.kind}
        if self.id:
            data["id"] = self.id
        if self.path:
            data["path"] = self.path
        if self.line is not None:
            data["line"] = self.line
        if self.title:
            data["title"] = self.title
        if self.details:
            data["details"] = dict(self.details)
        return data


@dataclass(frozen=True)
class Recommendation:
    id: str
    kind: str
    producer: str
    action: str
    why: str
    action_type: str = ""
    confidence: str = "medium"
    preconditions: list[str] = field(default_factory=list)
    source_refs: list[SourceRef | dict[str, Any]] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        refs: list[dict[str, Any]] = []
        for ref in self.source_refs:
            refs.append(ref.to_dict() if isinstance(ref, SourceRef) else dict(ref))
        data = {
            "id": self.id,
            "kind": self.kind,
            "producer": self.producer,
            "action": self.action,
            "why": self.why,
            "confidence": self.confidence,
            "preconditions": list(self.preconditions),
            "source_refs": refs,
            "evidence_refs": list(self.evidence_refs),
            "metadata": dict(self.metadata),
        }
        if self.action_type:
            data["action_type"] = self.action_type
        return data


@dataclass(frozen=True)
class ToolView:
    tool: str
    ok: bool = True
    proof_state: dict[str, Any] = field(default_factory=dict)
    guidance: dict[str, Any] = field(default_factory=dict)
    evidence: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    notes: list[dict[str, Any]] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)
    debug: dict[str, Any] = field(default_factory=dict)
    schema_version: int = TOOL_VIEW_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        data = {
            "schema_version": self.schema_version,
            "tool": self.tool,
            "ok": self.ok,
            "proof_state": dict(self.proof_state),
            "guidance": _normalize_guidance(self.guidance),
            "evidence": _normalize_evidence(self.evidence),
            "notes": _normalize_messages(self.notes),
            "errors": _normalize_messages(self.errors),
            "debug": dict(self.debug),
        }
        validation = validate_tool_view(data)
        if not validation.ok:
            data["ok"] = False
            data["errors"] = data["errors"] + [
                {
                    "code": "tool_view.invalid",
                    "message": msg,
                    "severity": "error",
                }
                for msg in validation.errors
            ]
        return data


def make_tool_view(
    *,
    tool: str,
    proof_state: dict[str, Any] | None = None,
    recommendations: list[Recommendation | dict[str, Any]] | None = None,
    guidance: dict[str, Any] | None = None,
    evidence: dict[str, Any] | None = None,
    notes: list[str | dict[str, Any]] | None = None,
    errors: list[str | dict[str, Any]] | None = None,
    debug: dict[str, Any] | None = None,
    ok: bool | None = None,
) -> ToolView:
    """Build a normalized ToolView.

    ``ok`` defaults to false when errors are present. Callers can override it
    when they intentionally return a partially useful view with non-fatal
    diagnostic messages.
    """
    guidance_data = dict(guidance or {})
    if recommendations is not None:
        guidance_data["recommendations"] = [
            r.to_dict() if isinstance(r, Recommendation) else dict(r)
            for r in recommendations
        ]
    err_items = _normalize_messages(errors or [])
    return ToolView(
        tool=tool,
        ok=(not err_items if ok is None else bool(ok)),
        proof_state=dict(proof_state or {}),
        guidance=guidance_data,
        evidence=_normalize_evidence(evidence or {}),
        notes=_normalize_messages(notes or []),
        errors=err_items,
        debug=dict(debug or {}),
    )


def tool_view_from_projection(
    *,
    tool: str,
    proof_state: dict[str, Any],
    recommendations: list[Recommendation | dict[str, Any]] | None = None,
    guidance: dict[str, Any] | None = None,
    evidence: dict[str, Any] | None = None,
    notes: list[str | dict[str, Any]] | None = None,
    errors: list[str | dict[str, Any]] | None = None,
    debug: dict[str, Any] | None = None,
    ok: bool | None = None,
) -> dict[str, Any]:
    """Convenience wrapper returning a JSON-ready dict."""
    return make_tool_view(
        tool=tool,
        proof_state=proof_state,
        recommendations=recommendations,
        guidance=guidance,
        evidence=evidence,
        notes=notes,
        errors=errors,
        debug=debug,
        ok=ok,
    ).to_dict()


def write_tool_view_artifact(
    session_dir: str | Path,
    view: ToolView | dict[str, Any],
) -> dict[str, Any]:
    """Persist a ToolView and return the matching event payload.

    The event stream should remain compact and indexable. Full ToolViews can be
    large because they include evidence and debug/fallback text, so the event
    carries a hash + artifact pointer while the JSON body lives under the
    session directory.
    """
    path = Path(session_dir)
    data = view.to_dict() if isinstance(view, ToolView) else dict(view)
    validation = validate_tool_view(data)
    text = json.dumps(data, indent=2, sort_keys=True)
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()
    tool_name = str(data.get("tool") or "tool")
    safe_tool = re.sub(r"[^A-Za-z0-9_.-]+", "_", tool_name).strip("_") or "tool"
    out_dir = path / "tool_views"
    out_dir.mkdir(parents=True, exist_ok=True)
    artifact = out_dir / f"{safe_tool}_{digest[:16]}.json"
    artifact.write_text(text + "\n", encoding="utf-8")

    guidance = data.get("guidance") if isinstance(data.get("guidance"), dict) else {}
    recs = guidance.get("recommendations") if isinstance(guidance, dict) else []
    proof_state = (
        data.get("proof_state") if isinstance(data.get("proof_state"), dict)
        else {}
    )
    return {
        "tool": tool_name,
        "schema_version": int(data.get("schema_version") or 0),
        "ok": bool(data.get("ok")) and validation.ok,
        "artifact": str(artifact),
        "view_hash": digest,
        "proof_status": str(proof_state.get("status") or ""),
        "recommendation_count": len(recs) if isinstance(recs, list) else 0,
        "error_count": len(data.get("errors") or []) + len(validation.errors),
        "warning_count": len(validation.warnings),
        "note_count": len(data.get("notes") or []),
    }


def record_tool_view(
    session_or_dir: Any,
    view: ToolView | dict[str, Any],
    *,
    source: str = "session_cli",
) -> dict[str, Any]:
    """Write a ToolView artifact and emit ``tool.view.produced`` if possible."""
    session_dir = getattr(session_or_dir, "dir", session_or_dir)
    payload = write_tool_view_artifact(session_dir, view)
    emit = getattr(session_or_dir, "emit_event", None)
    if callable(emit):
        emit("tool.view.produced", payload, source=source)
    return payload


def validate_tool_view(data: dict[str, Any]) -> ToolViewValidation:
    errors: list[str] = []
    warnings: list[str] = []

    required = {
        "schema_version": int,
        "tool": str,
        "ok": bool,
        "proof_state": dict,
        "guidance": dict,
        "evidence": dict,
        "notes": list,
        "errors": list,
        "debug": dict,
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

    if data.get("schema_version") != TOOL_VIEW_SCHEMA_VERSION:
        errors.append(
            f"schema_version must be {TOOL_VIEW_SCHEMA_VERSION}, "
            f"got {data.get('schema_version')!r}"
        )
    if isinstance(data.get("tool"), str) and not data.get("tool", "").strip():
        errors.append("field `tool` must be non-empty")

    guidance = data.get("guidance")
    if isinstance(guidance, dict):
        recs = guidance.get("recommendations", [])
        if not isinstance(recs, list):
            errors.append("guidance.recommendations must be a list")
        else:
            for idx, rec in enumerate(recs):
                _validate_recommendation(rec, idx, errors, warnings)

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
                    errors.append(
                        f"evidence.{bucket}[{idx}] must be an object"
                    )
                elif "id" not in item:
                    warnings.append(
                        f"evidence.{bucket}[{idx}] has no `id` field"
                    )

    for field_name in ("notes", "errors"):
        items = data.get(field_name)
        if isinstance(items, list):
            for idx, item in enumerate(items):
                if not isinstance(item, dict):
                    errors.append(f"{field_name}[{idx}] must be an object")
                elif not isinstance(item.get("message", ""), str):
                    errors.append(
                        f"{field_name}[{idx}].message must be a string"
                    )

    return ToolViewValidation(errors=errors, warnings=warnings)


def _validate_recommendation(
    rec: Any,
    idx: int,
    errors: list[str],
    warnings: list[str],
) -> None:
    if not isinstance(rec, dict):
        errors.append(f"guidance.recommendations[{idx}] must be an object")
        return
    for key in ("id", "kind", "producer", "action", "why", "confidence"):
        if key not in rec:
            errors.append(f"guidance.recommendations[{idx}] missing `{key}`")
        elif not isinstance(rec[key], str):
            errors.append(
                f"guidance.recommendations[{idx}].{key} must be a string"
            )
        elif key in ("id", "kind", "producer", "action") and not rec[key].strip():
            errors.append(
                f"guidance.recommendations[{idx}].{key} must be non-empty"
            )
    if rec.get("confidence") not in (
        None, "", "low", "medium", "high", "verified",
    ):
        warnings.append(
            f"guidance.recommendations[{idx}].confidence "
            f"has unusual value {rec.get('confidence')!r}"
        )
    for list_key in ("preconditions", "source_refs", "evidence_refs"):
        if list_key in rec and not isinstance(rec[list_key], list):
            errors.append(
                f"guidance.recommendations[{idx}].{list_key} must be a list"
            )
    if "metadata" in rec and not isinstance(rec["metadata"], dict):
        errors.append(
            f"guidance.recommendations[{idx}].metadata must be an object"
        )
    if "action_type" in rec:
        if not isinstance(rec["action_type"], str):
            errors.append(
                f"guidance.recommendations[{idx}].action_type must be a string"
            )
        elif rec["action_type"] not in RECOMMENDATION_ACTION_TYPES:
            errors.append(
                f"guidance.recommendations[{idx}].action_type must be one of "
                f"{', '.join(RECOMMENDATION_ACTION_TYPES)}"
            )


def _normalize_guidance(guidance: dict[str, Any]) -> dict[str, Any]:
    data = dict(guidance)
    recs = data.get("recommendations", [])
    normalized_recs: list[dict[str, Any]] = []
    if isinstance(recs, list):
        for rec in recs:
            if isinstance(rec, Recommendation):
                normalized_recs.append(rec.to_dict())
            elif isinstance(rec, dict):
                normalized_recs.append(dict(rec))
            else:
                normalized_recs.append({
                    "id": "invalid",
                    "kind": "invalid",
                    "producer": "tool_view",
                    "action": str(rec),
                    "why": "Non-object recommendation was coerced.",
                    "confidence": "low",
                    "preconditions": [],
                    "source_refs": [],
                    "evidence_refs": [],
                    "metadata": {},
                })
    data["recommendations"] = normalized_recs
    return data


def _normalize_evidence(evidence: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    data: dict[str, list[dict[str, Any]]] = {
        bucket: [] for bucket in EVIDENCE_BUCKETS
    }
    for bucket, items in dict(evidence).items():
        if isinstance(items, dict):
            normalized_items = [dict(items)]
        elif isinstance(items, list):
            normalized_items = [
                dict(item) if isinstance(item, dict)
                else {"id": f"{bucket}.{idx}", "value": item}
                for idx, item in enumerate(items)
            ]
        else:
            normalized_items = [{"id": bucket, "value": items}]
        data.setdefault(bucket, []).extend(normalized_items)
    return data


def _normalize_messages(
    items: list[str | dict[str, Any]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for idx, item in enumerate(items):
        if isinstance(item, dict):
            obj = dict(item)
            obj.setdefault("message", "")
            obj.setdefault("code", f"message.{idx}")
            out.append(obj)
        else:
            out.append({
                "code": f"message.{idx}",
                "message": str(item),
            })
    return out
