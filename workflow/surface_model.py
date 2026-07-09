"""Typed presentation contract for prover followups and playground cards.

Raw ``ProverWorkspaceView`` values are audit facts.  This module defines the
single typed surface that renderers consume: panels, facts, actions, and their
display policy.  Renderers should not select content from raw workspace panels.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any


SURFACE_MODEL_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class PanelFact:
    key: str
    label: str
    value: Any
    kind: str = "fact"
    role: str = "primary"
    summary: str = ""
    details: Any = None
    audit_payload: Any = None
    source_refs: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return _drop_empty({
            "key": self.key,
            "label": self.label,
            "kind": self.kind,
            "role": self.role,
            "summary": self.summary,
            "value": self.value,
            "details": self.details,
            "audit_payload": self.audit_payload,
            "source_refs": list(self.source_refs),
        })


@dataclass(frozen=True)
class PanelAction:
    intent: str
    payload: dict[str, Any] = field(default_factory=dict)
    label: str = ""
    intent_class: str = ""
    read_only: bool = True
    requires_input: tuple[str, ...] = ()
    choices: dict[str, list[Any]] = field(default_factory=dict)
    description: str = ""
    source_refs: tuple[str, ...] = ()
    eligibility_reason: str = ""
    state_scope: str = ""

    def to_dict(self) -> dict[str, Any]:
        return _drop_empty({
            "intent": self.intent,
            "payload": dict(self.payload),
            "label": self.label or self.intent,
            "intent_class": self.intent_class,
            "read_only": self.read_only,
            "requires_input": list(self.requires_input),
            "choices": self.choices,
            "description": self.description,
            "source_refs": list(self.source_refs),
            "eligibility_reason": self.eligibility_reason,
            "state_scope": self.state_scope,
        })


@dataclass(frozen=True)
class DisplayPolicy:
    lead_before_goal: bool = False
    verbosity: str = "normal"
    compact_goal: bool = False
    show_status: bool = True
    show_actions: bool = True

    def to_dict(self) -> dict[str, Any]:
        return _drop_empty({
            "lead_before_goal": self.lead_before_goal,
            "verbosity": self.verbosity,
            "compact_goal": self.compact_goal,
            "show_status": self.show_status,
            "show_actions": self.show_actions,
        })


@dataclass(frozen=True)
class PanelModel:
    panel_id: str
    phase: str
    title: str
    facts: tuple[PanelFact, ...] = ()
    actions: tuple[PanelAction, ...] = ()
    display_policy: DisplayPolicy = field(default_factory=DisplayPolicy)
    source_refs: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return _drop_empty({
            "panel_id": self.panel_id,
            "phase": self.phase,
            "title": self.title,
            "facts": [fact.to_dict() for fact in self.facts],
            "actions": [action.to_dict() for action in self.actions],
            "display_policy": self.display_policy.to_dict(),
            "source_refs": list(self.source_refs),
        })


@dataclass(frozen=True)
class SurfaceModel:
    profile: str
    phase: str
    goal: dict[str, Any] = field(default_factory=dict)
    status: dict[str, Any] = field(default_factory=dict)
    primary_panel: PanelModel | None = None
    panels: tuple[PanelModel, ...] = ()
    actions: tuple[PanelAction, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    schema_version: int = SURFACE_MODEL_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        data = _drop_empty({
            "schema_version": self.schema_version,
            "profile": self.profile,
            "phase": self.phase,
            "goal": self.goal,
            "status": self.status,
            "primary_panel": (
                self.primary_panel.to_dict() if self.primary_panel else None
            ),
            "panels": [panel.to_dict() for panel in self.panels],
            "actions": [action.to_dict() for action in self.actions],
            "metadata": dict(self.metadata),
        })
        return data


def surface_model_hash(model: SurfaceModel | dict[str, Any]) -> str:
    data = model.to_dict() if isinstance(model, SurfaceModel) else dict(model)
    data.pop("surface_model_hash", None)
    if isinstance(data.get("metadata"), dict):
        data["metadata"] = dict(data["metadata"])
        data["metadata"].pop("surface_model_hash", None)
    payload = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def surface_model_to_dict(model: SurfaceModel | dict[str, Any]) -> dict[str, Any]:
    data = model.to_dict() if isinstance(model, SurfaceModel) else dict(model)
    data["surface_model_hash"] = surface_model_hash(data)
    return data


def last_action_needs_attention(view: dict[str, Any]) -> bool:
    lr = view.get("last_result") if isinstance(view.get("last_result"), dict) else {}
    result = str(lr.get("result") or "").lower()
    proof_state = str(lr.get("proof_state") or "").lower()
    error_summary = str(lr.get("error_summary") or "").strip()
    text = " ".join((result, proof_state, error_summary.lower()))
    if "reject" in result or "error" in result:
        return True
    if error_summary and "accepted" not in result:
        return True
    return any(
        marker in text
        for marker in (
            "no progress",
            "no-progress",
            "no_progress",
            "no effect",
            "no_effect",
            "no-op",
            "noop",
            "did not change",
            "not changed",
            "auto-revert",
            "auto_revert",
            "reverted",
        )
    )


def _drop_empty(data: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value for key, value in data.items()
        if value not in (None, "", [], {}, ())
    }


def goal_text(view: dict[str, Any]) -> str:
    """The current goal's text from a workspace view (joined lines, else the
    preview/text fallbacks). Generic view accessor — lives with the typed
    leaves so predicates/tactic-forms need not import a policy module."""
    goal = view.get("current_goal") if isinstance(view.get("current_goal"), dict) else {}
    lines = goal.get("lines")
    if isinstance(lines, list):
        return "\n".join(str(line) for line in lines)
    return str(goal.get("lines_preview") or goal.get("text") or "")
