"""Typed per-turn presentation contract for agent followups and playground cards.

``SurfaceModel`` describes a proof state.  ``SurfaceTurnModel`` describes what a
single manager turn should present: the stable proof surface, an optional
read-only/control overlay, and the previous-turn outcome.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from workflow.context_intents import (
    INTENT_CLASS_PROBE_PREVIEW,
    intent_class,
    intent_is_retrieval,
)
from workflow.surface_composer import compose_surface_model_dict
from workflow.surface_markdown import markdown_code_span as _md_code
from workflow.surface_model import _drop_empty
from workflow.surface_model import last_action_needs_attention


SURFACE_TURN_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class TurnOutcome:
    intent: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    ok: bool = True
    result_line: str = ""
    error_summary: str = ""
    lead_before_goal: bool = False
    proof_state_changed: bool = False
    source_refs: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return _drop_empty({
            "intent": self.intent,
            "payload": dict(self.payload),
            "ok": self.ok,
            "result_line": self.result_line,
            "error_summary": self.error_summary,
            "lead_before_goal": self.lead_before_goal,
            "proof_state_changed": self.proof_state_changed,
            "source_refs": list(self.source_refs),
        })


@dataclass(frozen=True)
class ControlMenuItem:
    label: str
    submit: dict[str, Any]
    description: str = ""
    tactic: str = ""
    source: str = ""

    def to_dict(self) -> dict[str, Any]:
        return _drop_empty({
            "label": self.label,
            "description": self.description,
            "tactic": self.tactic,
            "submit": dict(self.submit),
            "source": self.source,
        })


@dataclass(frozen=True)
class ControlMenu:
    intent: str
    title: str
    notice: str = ""
    items: tuple[ControlMenuItem, ...] = ()
    source_refs: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return _drop_empty({
            "intent": self.intent,
            "title": self.title,
            "notice": self.notice,
            "items": [item.to_dict() for item in self.items],
            "source_refs": list(self.source_refs),
        })


@dataclass(frozen=True)
class SurfaceTurnModel:
    proof_surface: dict[str, Any]
    overlay_surface: dict[str, Any] | None = None
    control_menu: ControlMenu | None = None
    turn_outcome: TurnOutcome = field(default_factory=TurnOutcome)
    presentation_kind: str = "proof_state"
    base_surface_updates: bool = True
    proof_state_changed: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
    schema_version: int = SURFACE_TURN_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        data = _drop_empty({
            "schema_version": self.schema_version,
            "presentation_kind": self.presentation_kind,
            "proof_surface": dict(self.proof_surface),
            "overlay_surface": (
                dict(self.overlay_surface) if isinstance(self.overlay_surface, dict) else None
            ),
            "control_menu": self.control_menu.to_dict() if self.control_menu else None,
            "turn_outcome": self.turn_outcome.to_dict(),
            "base_surface_updates": self.base_surface_updates,
            "proof_state_changed": self.proof_state_changed,
            "metadata": dict(self.metadata),
        })
        data["surface_turn_hash"] = surface_turn_hash(data)
        return data


def surface_turn_hash(model: SurfaceTurnModel | dict[str, Any]) -> str:
    data = model.to_dict() if isinstance(model, SurfaceTurnModel) else dict(model)
    data.pop("surface_turn_hash", None)
    payload = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def compose_surface_turn(
    current_view: dict[str, Any],
    profile: str | None,
    *,
    base_view: dict[str, Any] | None = None,
    base_surface: dict[str, Any] | None = None,
    handled_intent: dict[str, Any] | None = None,
    ok: bool = True,
    repair_prompt: str = "",
    manager_actions: list[dict[str, Any]] | None = None,
    health_event: dict[str, Any] | None = None,
    goal_only: bool = False,
) -> dict[str, Any]:
    current_view = dict(current_view) if isinstance(current_view, dict) else {}
    handled_intent = handled_intent if isinstance(handled_intent, dict) else {}
    manager_actions = manager_actions or []
    intent = _intent_name(handled_intent, current_view)
    payload = handled_intent.get("payload") if isinstance(handled_intent.get("payload"), dict) else {}
    current_surface = _surface_from_view(current_view, profile, goal_only=goal_only)
    changed = _proof_state_changed(manager_actions, current_view)
    control_menu = _control_menu_from_view(current_view, intent, repair_prompt)

    is_probe = (
        intent_class(intent) == INTENT_CLASS_PROBE_PREVIEW
        and _has_probe_result(current_view)
    )
    is_retrieval = (
        intent_is_retrieval(intent)
        and _has_retrieval_result(current_view)
    )
    is_overlay = is_retrieval or is_probe
    is_control_menu = control_menu is not None and not _control_intent_executed(intent, payload, changed, current_view)

    if is_overlay or is_control_menu:
        proof_surface = _base_proof_surface(
            base_view=base_view,
            base_surface=base_surface,
            fallback_view=current_view,
            profile=profile,
            goal_only=goal_only,
        )
    else:
        proof_surface = current_surface

    overlay_surface = current_surface if is_retrieval else None
    outcome = _turn_outcome(
        current_view,
        intent=intent,
        payload=payload,
        ok=ok,
        repair_prompt=repair_prompt,
        manager_actions=manager_actions,
        health_event=health_event or {},
        proof_state_changed=changed,
    )
    kind = _presentation_kind(
        intent,
        is_retrieval=is_retrieval,
        is_probe=is_probe,
        is_control_menu=is_control_menu,
        handled_intent=handled_intent,
    )
    updates = _base_surface_updates(
        intent,
        payload=payload,
        ok=ok,
        is_retrieval=is_retrieval,
        is_probe=is_probe,
        is_control_menu=is_control_menu,
        proof_state_changed=changed,
    )
    turn = SurfaceTurnModel(
        proof_surface=proof_surface,
        overlay_surface=overlay_surface,
        control_menu=control_menu if is_control_menu else None,
        turn_outcome=outcome,
        presentation_kind=kind,
        base_surface_updates=updates,
        proof_state_changed=changed,
        metadata=_drop_empty({
            "contract": "SurfaceModel -> SurfaceTurnModel -> markdown/card",
            "current_surface_hash": current_surface.get("surface_model_hash"),
            "proof_surface_hash": proof_surface.get("surface_model_hash"),
            "overlay_surface_hash": (
                overlay_surface.get("surface_model_hash")
                if isinstance(overlay_surface, dict) else ""
            ),
        }),
    )
    return turn.to_dict()


def render_surface_turn_markdown(
    surface_turn: dict[str, Any],
    *,
    goal_only: bool = False,
    submit_line: str = "",
    anchor_block: str = "",
    banner_block: str = "",
) -> str:
    if not isinstance(surface_turn, dict):
        return ""
    kind = str(surface_turn.get("presentation_kind") or "")
    proof = surface_turn.get("proof_surface") if isinstance(surface_turn.get("proof_surface"), dict) else {}
    overlay = surface_turn.get("overlay_surface") if isinstance(surface_turn.get("overlay_surface"), dict) else None
    control = surface_turn.get("control_menu") if isinstance(surface_turn.get("control_menu"), dict) else None
    outcome = surface_turn.get("turn_outcome") if isinstance(surface_turn.get("turn_outcome"), dict) else {}

    if goal_only:
        body = _render_goal_only_surface(proof)
        outcome_md = _render_turn_outcome(outcome)
        if outcome_md and outcome.get("lead_before_goal"):
            body = _join_sections(outcome_md, body)
        elif outcome_md:
            body = _join_sections(body, outcome_md)
        return _join_sections(body, submit_line + anchor_block)

    if kind == "probe_preview":
        body = _render_turn_outcome(outcome)
        return _join_sections(body, submit_line + anchor_block)

    if overlay:
        overlay_md = _render_overlay_surface(overlay)
        proof_md = _render_proof_surface(proof)
        return _join_sections(
            proof_md,
            "## Read-only result\n" + overlay_md if overlay_md else "",
            submit_line + anchor_block,
        )

    if control:
        control_md = _render_control_menu(control)
        proof_md = _render_proof_surface(
            proof,
            compact_goal=True,
            heading="## Continue from unchanged proof state",
        )
        return _join_sections(control_md, proof_md, submit_line + anchor_block)

    proof_md = _render_proof_surface(proof)
    outcome_md = _render_turn_outcome(outcome)
    if outcome_md and outcome.get("lead_before_goal"):
        body = _join_sections(outcome_md, proof_md)
    elif outcome_md:
        body = _join_sections(proof_md, outcome_md)
    else:
        body = proof_md
    return _join_sections(banner_block, body, submit_line + anchor_block)


def proof_surface_from_turn(surface_turn: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(surface_turn, dict):
        return {}
    proof = surface_turn.get("proof_surface")
    return dict(proof) if isinstance(proof, dict) else {}


def _surface_from_view(
    view: dict[str, Any],
    profile: str | None,
    *,
    goal_only: bool,
) -> dict[str, Any]:
    return compose_surface_model_dict(view, profile, goal_only=goal_only)


def _base_proof_surface(
    *,
    base_view: dict[str, Any] | None,
    base_surface: dict[str, Any] | None,
    fallback_view: dict[str, Any],
    profile: str | None,
    goal_only: bool,
) -> dict[str, Any]:
    if isinstance(base_surface, dict) and base_surface.get("schema_version"):
        return dict(base_surface)
    if isinstance(base_view, dict) and base_view:
        prior = proof_surface_from_turn(base_view.get("surface_turn") or {})
        if prior and (not profile or prior.get("profile") == profile):
            return prior
        return _surface_from_view(base_view, profile, goal_only=goal_only)
    sanitized = dict(fallback_view)
    lr = sanitized.get("last_result")
    if isinstance(lr, dict) and intent_is_retrieval(lr.get("intent")):
        sanitized.pop("last_result", None)
    return _surface_from_view(sanitized, profile, goal_only=goal_only)


def _intent_name(handled_intent: dict[str, Any], view: dict[str, Any]) -> str:
    intent = str(handled_intent.get("intent") or "").strip()
    if intent:
        return intent
    lr = view.get("last_result") if isinstance(view.get("last_result"), dict) else {}
    return str(lr.get("intent") or "").strip()


def _proof_state_changed(actions: list[dict[str, Any]], view: dict[str, Any]) -> bool:
    no_change_markers = (
        "unchanged",
        "not changed",
        "rejected",
        "did not execute",
        "did not change",
        "no progress",
        "no_progress",
        "no-op",
        "no effect",
        "auto-revert",
        "auto_revert",
    )
    for action in actions or []:
        if not isinstance(action, dict):
            continue
        if not bool(action.get("mutates_proof_state")) or action.get("exit_code") != 0:
            continue
        obs = action.get("agent_observation")
        if isinstance(obs, dict):
            proof_state = str(obs.get("proof_state") or "").lower()
            result = str(obs.get("result") or "").lower()
            if any(marker in proof_state for marker in no_change_markers):
                continue
            if any(marker in result for marker in no_change_markers):
                continue
        return True
    lr = view.get("last_result") if isinstance(view.get("last_result"), dict) else {}
    text = " ".join(str(lr.get(k) or "").lower() for k in ("result", "proof_state", "kind"))
    if any(marker in text for marker in ("not changed", "unchanged", "rejected", "no progress")):
        return False
    return any(marker in text for marker in ("changed", "checkpoint_rewind", "checkpoint_restore", "confirmed"))


def _has_probe_result(view: dict[str, Any]) -> bool:
    lr = view.get("last_result") if isinstance(view.get("last_result"), dict) else {}
    if "probe_preview" in lr:
        return True
    text = " ".join(str(lr.get(k) or "").lower() for k in ("result", "error_summary", "kind"))
    return bool(text.strip())


def _has_retrieval_result(view: dict[str, Any]) -> bool:
    lr = view.get("last_result") if isinstance(view.get("last_result"), dict) else {}
    content = lr.get("content")
    return isinstance(content, dict) and bool(content)


def _turn_outcome(
    view: dict[str, Any],
    *,
    intent: str,
    payload: dict[str, Any],
    ok: bool,
    repair_prompt: str,
    manager_actions: list[dict[str, Any]],
    health_event: dict[str, Any],
    proof_state_changed: bool,
) -> TurnOutcome:
    lr = view.get("last_result") if isinstance(view.get("last_result"), dict) else {}
    tactic = str(lr.get("tactic") or payload.get("tactic") or "").strip()
    result = str(lr.get("result") or lr.get("message") or lr.get("notice") or "").strip()
    error = str(lr.get("error_summary") or "").strip()
    if not ok and repair_prompt:
        result = repair_prompt
    elif intent_class(intent) == INTENT_CLASS_PROBE_PREVIEW:
        result = _probe_outcome_text(lr, tactic)
    elif tactic:
        result = f"Last action: `{_short(tactic, 80)}` -- {result or '(no result reported)'}"
    if error and "EasyCrypt error:" not in result:
        result += ("\n" if result else "") + f"EasyCrypt error: {error}"
    if repair_prompt and not result:
        result = repair_prompt
    extras: list[str] = []
    if health_event.get("status"):
        extras.append(f"health: `{health_event['status']}`")
    if any(isinstance(a, dict) and a.get("timed_out") for a in manager_actions):
        extras.append("manager backend action TIMED OUT")
    if extras:
        result = (result + "\n" if result else "") + "\n".join(extras)
    return TurnOutcome(
        intent=intent,
        payload=payload,
        ok=ok,
        result_line=result,
        error_summary=error,
        lead_before_goal=last_action_needs_attention(view),
        proof_state_changed=proof_state_changed,
        source_refs=("last_result",),
    )


def _probe_outcome_text(last_result: dict[str, Any], tactic: str) -> str:
    pp = last_result.get("probe_preview") if isinstance(last_result.get("probe_preview"), dict) else {}
    goal_after = pp.get("goal_after_probe") if isinstance(pp, dict) else None
    error = str(last_result.get("error_summary") or "").strip()
    tac = _short(tactic or str(last_result.get("tactic") or ""), 80) or "(probe)"
    remaining = pp.get("goal_after_remaining") if isinstance(pp, dict) else None
    closed = not error and (
        (isinstance(pp, dict) and pp.get("goal_after_closed") is True)
        or remaining == 0
        or (isinstance(remaining, str) and remaining.strip() == "0")
    )
    if closed:
        return (
            f"## Probe preview -- `{tac}` accepted; committing CLOSES the proof "
            "(all goals discharged)"
        )
    if isinstance(goal_after, dict) and goal_after:
        lines = goal_after.get("lines")
        text = "\n".join(str(x) for x in lines) if isinstance(lines, list) else str(goal_after.get("text") or "")
        rem = f" (remaining {remaining})" if remaining not in (None, "", "?") else ""
        return (
            f"## Probe preview -- `{tac}` accepted; committed state unchanged\n"
            f"_committing this would produce{rem}:_\n```\n{text.rstrip()}\n```"
        )
    if error:
        return f"## Probe rejected -- `{tac}`; committed state unchanged\n\nEasyCrypt error: {error}"
    return str(last_result.get("result") or f"Probe returned for `{tac}`.").strip()


def _control_menu_from_view(
    view: dict[str, Any],
    intent: str,
    repair_prompt: str,
) -> ControlMenu | None:
    if intent not in {"undo_to_checkpoint", "fresh_restart", "finish"}:
        return None
    lr = view.get("last_result") if isinstance(view.get("last_result"), dict) else {}
    items: list[ControlMenuItem] = []

    def add(raw: Any, source: str) -> None:
        if not isinstance(raw, dict):
            return
        submit = raw.get("submit")
        if not isinstance(submit, dict):
            raw_intent = raw.get("intent")
            if raw_intent or isinstance(raw.get("payload"), dict):
                submit = {"intent": raw_intent, "payload": raw.get("payload") or {}}
        if not isinstance(submit, dict) or not submit.get("intent"):
            return
        if intent == "undo_to_checkpoint" and submit.get("intent") != "undo_to_checkpoint":
            return
        if intent_class(submit.get("intent")) == INTENT_CLASS_PROBE_PREVIEW:
            return
        items.append(ControlMenuItem(
            label=str(raw.get("label") or raw.get("title") or raw.get("message") or submit.get("intent") or "").strip(),
            description=str(
                raw.get("effect_if_selected")
                or raw.get("repair_use_when")
                or raw.get("why_checkpoint")
                or raw.get("notice")
                or raw.get("description")
                or ""
            ).strip(),
            tactic=str(raw.get("committed_tactic") or raw.get("tactic") or "").strip(),
            submit={"intent": submit.get("intent"), "payload": submit.get("payload") or {}},
            source=source,
        ))

    for option in lr.get("checkpoint_options") or []:
        add(option, "checkpoint_options")
    for option in lr.get("options") or []:
        add(option, "options")
    checkpoint = lr.get("checkpoint")
    if isinstance(checkpoint, dict):
        add(checkpoint, "checkpoint")
    notice = str(
        repair_prompt
        or lr.get("notice")
        or lr.get("message")
        or lr.get("result")
        or ""
    ).strip()
    if not items and not notice:
        return None
    title = {
        "undo_to_checkpoint": "Rewind targets",
        "fresh_restart": "Restart options",
        "finish": "Finish result",
    }.get(intent, intent)
    return ControlMenu(
        intent=intent,
        title=title,
        notice=notice,
        items=tuple(items),
        source_refs=("last_result",),
    )


def _control_intent_executed(
    intent: str,
    payload: dict[str, Any],
    changed: bool,
    view: dict[str, Any],
) -> bool:
    if intent == "undo_to_checkpoint":
        lr = view.get("last_result") if isinstance(view.get("last_result"), dict) else {}
        kind = str(lr.get("kind") or "")
        return changed or kind in {"checkpoint_rewind", "checkpoint_restore"}
    if intent == "fresh_restart":
        lr = view.get("last_result") if isinstance(view.get("last_result"), dict) else {}
        return changed or str(lr.get("kind") or "") == "fresh_restart_confirmed"
    return False


def _presentation_kind(
    intent: str,
    *,
    is_retrieval: bool,
    is_probe: bool,
    is_control_menu: bool,
    handled_intent: dict[str, Any],
) -> str:
    if not handled_intent:
        return "bootstrap"
    if is_probe:
        return "probe_preview"
    if is_retrieval:
        return "read_only_overlay"
    if is_control_menu:
        return "control_menu"
    return "proof_state"


def _base_surface_updates(
    intent: str,
    *,
    payload: dict[str, Any],
    ok: bool,
    is_retrieval: bool,
    is_probe: bool,
    is_control_menu: bool,
    proof_state_changed: bool,
) -> bool:
    if not ok and not proof_state_changed:
        return False
    if is_retrieval or is_probe or is_control_menu:
        return False
    if intent == "finish":
        return False
    if intent == "fresh_restart":
        return bool(payload.get("confirm") and proof_state_changed)
    if intent == "undo_to_checkpoint":
        return bool((payload.get("checkpoint_id") or payload.get("restore_id") or payload.get("confirm")) and proof_state_changed)
    return True


def _render_overlay_surface(surface: dict[str, Any]) -> str:
    panel = surface.get("primary_panel") if isinstance(surface.get("primary_panel"), dict) else {}
    return _join_blocks(_render_panel(panel))


def _render_proof_surface(
    surface: dict[str, Any],
    *,
    compact_goal: bool = False,
    heading: str = "",
) -> str:
    if not isinstance(surface, dict):
        return ""
    goal = _render_surface_goal(surface, compact=compact_goal)
    panel = surface.get("primary_panel") if isinstance(surface.get("primary_panel"), dict) else None
    panel_md = _render_panel(panel) if panel else ""
    actions = _render_actions(surface)
    return _join_sections(heading, goal, panel_md, _render_status(surface), actions)


def _render_goal_only_surface(surface: dict[str, Any]) -> str:
    return _render_surface_goal(surface, compact=False)


def _render_surface_goal(surface: dict[str, Any], *, compact: bool = False) -> str:
    goal = surface.get("goal") if isinstance(surface.get("goal"), dict) else {}
    text = str(goal.get("text") or "").rstrip()
    if not text:
        lines = goal.get("lines")
        text = "\n".join(str(x) for x in lines) if isinstance(lines, list) else ""
    if not text:
        text = "(no goal)"
    title = "## 🎯 Current Goal (unchanged)" if compact else "## 🎯 Current Goal"
    if compact:
        lines = text.splitlines()
        if len(lines) > 10:
            text = "\n".join(lines[:8]) + f"\n... (+{len(lines) - 8} more lines; goal unchanged)"
    rendered = f"{title}\n```\n{text}\n```"
    notice = str(goal.get("notice") or "").strip()
    if notice:
        rendered += f"\n\n_{notice}_"
    return rendered


def _render_panel(panel: dict[str, Any] | None) -> str:
    if not isinstance(panel, dict):
        return ""
    title = str(panel.get("title") or panel.get("panel_id") or "").strip()
    blocks = [f"## {title}"] if title else []
    for fact in panel.get("facts") or []:
        if not isinstance(fact, dict):
            continue
        if str(fact.get("role") or "").strip() == "audit_only":
            continue
        blocks.append(_render_panel_fact(fact))
    return _join_blocks(*blocks)


def _render_panel_fact(fact: dict[str, Any]) -> str:
    label = str(fact.get("label") or fact.get("key") or "Fact")
    summary = str(fact.get("summary") or "").strip()
    details = fact.get("details")
    if summary and details not in (None, "", [], {}, ()):
        detail_text = _render_fact("", details)
        detail_text = detail_text.removeprefix("**:**").strip()
        return _join_blocks(f"**{label}:** { _render_value(summary) }", detail_text)
    if summary:
        return f"**{label}:** {_render_value(summary)}"
    return _render_fact(label, fact.get("value"))


def _render_fact(label: str, value: Any) -> str:
    if isinstance(value, list):
        if not value:
            return f"**{label}:**"
        return f"**{label}:**\n" + "\n".join(_render_list_item(item) for item in value)
    if isinstance(value, dict):
        rows = []
        for key, val in value.items():
            if val in (None, "", [], {}, ()):
                continue
            rows.extend(_render_key_value_rows(str(key), val))
        return f"**{label}:**\n" + "\n".join(rows) if rows else f"**{label}:**"
    if isinstance(value, str) and "\n" in value:
        return f"**{label}:**\n```text\n{value.rstrip()}\n```"
    return f"**{label}:** {_render_value(value)}"


def _render_list_item(item: Any) -> str:
    if not isinstance(item, dict):
        return f"- {_render_value(item)}"
    rows: list[str] = []
    first = True
    for key, value in item.items():
        if value in (None, "", [], {}, ()):
            continue
        prefix = "- " if first else "  "
        rows.append(f"{prefix}`{key}`: {_render_value(value)}")
        first = False
    return "\n".join(rows) if rows else "-"


def _render_value(value: Any) -> str:
    if isinstance(value, str):
        return _render_scalar_value(value)
    return _md_code(json.dumps(value, ensure_ascii=False))


def _render_key_value_rows(key: str, value: Any) -> list[str]:
    if isinstance(value, list):
        rows = [f"- `{key}`:"]
        rows.extend(f"  - {_render_value(item)}" for item in value)
        return rows
    if isinstance(value, dict):
        rows = [f"- `{key}`:"]
        for nested_key, nested_value in value.items():
            if nested_value in (None, "", [], {}, ()):
                continue
            rows.append(f"  - `{nested_key}`: {_render_value(nested_value)}")
        return rows
    return [f"- `{key}`: {_render_value(value)}"]


def _render_scalar_value(value: str) -> str:
    text = str(value)
    if "`" in text:
        return text
    if _looks_like_code_fragment(text):
        return _md_code(text)
    return text


def _looks_like_code_fragment(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    if stripped.startswith(("[", "{", "(", "`")):
        return True
    code_tokens = (
        "\\/",
        "/\\",
        "=>",
        "<@",
        "<-",
        "<$",
        "{1}",
        "{2}",
        "{m}",
        "&m",
        "<inv>",
        "(_:",
    )
    return any(token in stripped for token in code_tokens)


def _render_status(surface: dict[str, Any]) -> str:
    status = surface.get("status") if isinstance(surface.get("status"), dict) else {}
    bits = [
        f"remaining **{status.get('remaining_goals', '?')}**",
        f"phase `{status.get('surface_phase') or status.get('view_focus') or status.get('current_layer') or '?'}`",
    ]
    return "## Status\n" + " · ".join(bits)


def _render_actions(surface: dict[str, Any]) -> str:
    actions = [a for a in surface.get("actions") or [] if isinstance(a, dict)]
    if not actions:
        return ""
    lines = ["### Need more? submit one read-only request"]
    for action in actions[:10]:
        intent = str(action.get("intent") or "")
        payload = dict(action.get("payload") or {}) if isinstance(action.get("payload"), dict) else {}
        choices = action.get("choices") if isinstance(action.get("choices"), dict) else {}
        for field, vals in choices.items():
            if vals and len(vals) > 1:
                payload[field] = f"<{field}>"
        choice_bits = []
        for field, vals in choices.items():
            vals = [str(v) for v in vals if not _is_placeholder(v)]
            if vals:
                choice_bits.append(f"{field} choices: " + ", ".join(f"`{v}`" for v in vals[:8]))
        label = f"`{intent}`"
        if payload:
            label += " (+" + ", ".join(payload) + ")"
        submit = {"intent": intent, "payload": payload}
        lines.append(f"- {label}" + (("; " + "; ".join(choice_bits)) if choice_bits else ""))
        lines.append(f"  submit `{json.dumps(submit, ensure_ascii=False)}`")
    return "\n".join(lines)


def _render_control_menu(menu: dict[str, Any]) -> str:
    lines = [f"## {menu.get('title') or 'Manager menu'}"]
    notice = str(menu.get("notice") or "").strip()
    if notice:
        lines.append(notice)
    items = menu.get("items") if isinstance(menu.get("items"), list) else []
    if items:
        lines.append("Choose one option by submitting its exact payload:")
        for item in items:
            if not isinstance(item, dict):
                continue
            label = str(item.get("label") or "option")
            desc = str(item.get("description") or "").strip()
            tactic = str(item.get("tactic") or "").strip()
            submit = item.get("submit") if isinstance(item.get("submit"), dict) else {}
            line = f"- {label}"
            if desc:
                line += f" -- {desc}"
            if tactic:
                line += f"\n  tactic: `{tactic}`"
            if submit:
                line += f"\n  submit `{json.dumps(submit, ensure_ascii=False)}`"
            lines.append(line)
    elif not notice:
        lines.append("No manager menu is available for this state.")
    return "\n\n".join(lines)


def _render_turn_outcome(outcome: dict[str, Any]) -> str:
    text = str(outcome.get("result_line") or "").strip()
    if not text:
        return ""
    if text.startswith("## "):
        return text
    if text.startswith("Last action: "):
        rest = text[len("Last action: "):]
        return f"**Last action:** {rest}"
    if "\n" in text:
        return "```\n" + text.rstrip() + "\n```"
    return "**" + text.replace("\n", "\n\n") + "**"


def _is_placeholder(value: Any) -> bool:
    stripped = str(value or "").strip()
    return (
        not stripped
        or (stripped.startswith("<") and stripped.endswith(">"))
        or stripped.isupper()
        or "..." in stripped
        or "…" in stripped
    )


def _join_blocks(*blocks: str) -> str:
    return "\n\n".join(str(block).strip() for block in blocks if str(block or "").strip())


def _join_sections(*blocks: str) -> str:
    return "\n\n---\n\n".join(
        str(block).strip() for block in blocks if str(block or "").strip()
    )


def _short(value: str, limit: int) -> str:
    value = " ".join(str(value or "").split())
    return value if len(value) <= limit else value[: limit - 1] + "..."

