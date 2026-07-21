"""Display policy for the prover-facing workspace view.

The durable ProofContextView keeps the full compiler/projection state.  This
manager is the single policy point that decides how that context should be
summarized for ProverWorkspaceView: goal family, display budget, panel focus,
and the order in which a prover should inspect more detail.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any

from core.easycrypt.session_candidate_status import (
    goal_visibly_closed as _goal_visibly_closed,
    transition_can_mark_closed as _transition_can_mark_closed,
)
from core.context_intents import (
    CONTEXT_TOPIC_INTENTS,
    add_intent_contract,
    direct_context_request,
    intent_payload_fields,
    intent_spec,
    normalize_context_topic,
)
from core.easycrypt.analysis.ec_utils import drop_empty_recursive as _drop_empty
from core.easycrypt.value_shapes import (
    as_dict as _dict,
    as_dict_list as _dict_list,
    first_text as _first_text,
)


@dataclass(frozen=True)
class DisplayBudget:
    """Soft render limits for the compact stdout workspace view."""

    goal_window_lines: int
    goal_window_chars: int
    frontier_chars: int
    max_alternatives: int
    max_evidence: int
    soft_total_chars: int = 12000
    hard_total_chars: int = 16000

    def to_dict(self) -> dict[str, int]:
        return {
            "goal_window_lines": self.goal_window_lines,
            "goal_window_chars": self.goal_window_chars,
            "frontier_chars": self.frontier_chars,
            "max_alternatives": self.max_alternatives,
            "max_evidence": self.max_evidence,
            "soft_total_chars": self.soft_total_chars,
            "hard_total_chars": self.hard_total_chars,
        }


@dataclass(frozen=True)
class PanelPlan:
    """One prover-facing panel selected by the manager."""

    name: str
    authority: str
    reason: str
    budget_chars: int = 0

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "name": self.name,
            "authority": self.authority,
            "reason": self.reason,
        }
        if self.budget_chars:
            out["budget_chars"] = self.budget_chars
        return out


@dataclass(frozen=True)
class WorkspaceViewPlan:
    """Render plan from ProofContextView to ProverWorkspaceView."""

    goal_family: str
    goal_display_mode: str
    phase_summary: str
    budget: DisplayBudget
    panels: tuple[PanelPlan, ...]
    authority_order: tuple[str, ...]
    inspect_order: tuple[str, ...]
    focus: tuple[str, ...]
    phase_resource_keys: tuple[str, ...]
    frontier_resource_keys: tuple[str, ...]
    frontier_checks: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal_family": self.goal_family,
            "goal_display_mode": self.goal_display_mode,
            "phase_summary": self.phase_summary,
            "budget": self.budget.to_dict(),
            "panels": [panel.to_dict() for panel in self.panels],
            "authority_order": list(self.authority_order),
            "inspect_order": list(self.inspect_order),
            "focus": list(self.focus),
            "phase_resource_keys": list(self.phase_resource_keys),
            "frontier_resource_keys": list(self.frontier_resource_keys),
            "frontier_checks": list(self.frontier_checks),
        }


DEFAULT_GOAL_WINDOW_LINES = 800
DEFAULT_GOAL_WINDOW_CHARS = 30000

AGENT_VIEW_PANEL_ORDER: tuple[str, ...] = (
    "last_result",
    "proof_status",
    "current_goal",
    "program_frontier",
    "call_site_surface",
    "seq_cut_surface",
    "pure_tail_surface",
    "structural_checkpoints",
    "application_context",
    "facts_and_diagnostics",
    "candidate_moves",
    "inspect_lookup_handles",
)

AGENT_VIEW_METADATA_ORDER: tuple[str, ...] = (
    "ok",
    "kind",
    "schema_version",
    "based_on_state_version",
    "session_epoch",
    "view_hash",
)

AGENT_HIDDEN_METADATA_FIELDS = frozenset(AGENT_VIEW_METADATA_ORDER)

_LOW_LEVEL_INSPECT_TOPICS = frozenset({
    "inspect_context",
    "try",
    "next",
    "prev",
    "chain",
    "tactic_exec",
    "commit_tactic",
    "tactic_candidate",
})

_DIRECT_CONTEXT_TOPIC_INTENTS = CONTEXT_TOPIC_INTENTS

AGENT_ENUM_WORDING_REVIEWS: tuple[dict[str, str], ...] = (
    {
        "raw_value": "ready_to_run",
        "source": "ProofIR/action readiness",
        "meaning": "The tactic has no known placeholders for the current goal.",
        "agent_wording": "This tactic is already concrete for the current goal.",
        "example_context": "candidate_moves.moves[].applicability",
    },
    {
        "raw_value": "needs_instantiation",
        "source": "ProofIR/action readiness",
        "meaning": "The item is a route template with missing proof-specific content.",
        "agent_wording": (
            "This is a proof-route template, not a complete tactic; fill in "
            "the missing invariant or tactic arguments from the current goal "
            "before committing it."
        ),
        "example_context": "candidate_moves.moves[].applicability",
    },
    {
        "raw_value": "context_only",
        "source": "ProofIR/action readiness",
        "meaning": "The item is evidence for route selection, not a tactic.",
        "agent_wording": (
            "This is route-selection context; it is not a tactic to run as-is."
        ),
        "example_context": "candidate_moves.moves[].applicability",
    },
    {
        "raw_value": "state_unchanged",
        "source": "REPL/manager result",
        "meaning": "The committed EasyCrypt proof state was not mutated.",
        "agent_wording": "The committed EasyCrypt proof state was not changed.",
        "example_context": "last_result.proof_state",
    },
)

AGENT_FORBIDDEN_BARE_ENUM_VALUES = frozenset(
    item["raw_value"] for item in AGENT_ENUM_WORDING_REVIEWS
) | frozenset({
    "manager_action_recorded",
    "not_requested",
    "proof_state_effect",
    "does_not_change_proof_state_read_only",
    "does_not_change_proof_state_verification_check",
    "will_change_proof_state",
    "no_proof_state_effect",
})


class WorkspaceViewManager:
    """Internal projection/sanitization manager for agent-facing views.

    The REPL/session layer may produce rich artifacts with historical fields or
    backend-oriented debug affordances.  This manager is the single place that
    turns that material into the neutral ProverWorkspaceView surface the agent
    sees.  It does not execute tactics, inspect EasyCrypt, or mutate proof
    state.
    """

    forbidden_field_names = frozenset({
        "debug_cli_fallback",
        "suggested_next_steps",
        "next_actions",
        "next_try",
        "suggestions",
        "readiness",
        "proof_state_effect",
        "needs_instantiation",
        "requires_instantiation",
    })

    backend_command_markers = (
        "session_cli.py",
        "core/easycrypt/session_cli",
        " -agent-view",
        " -goal-info",
        " -episode-view",
    )
    agent_cost_wording_markers = (
        "high-cost",
        "low-cost",
        "cheap logical",
        "cheaper than",
        "expensive residual",
        "abstraction cost",
    )
    internal_source_markers = (
        "ProofIR",
        "AUTO-DIFF",
        "AUTO-PIVOT",
        "AUTO-ASYM-SEQ",
        "AUTO-CALL-SUGGEST",
        "AUTO-PIVOT-CALL-READY",
    )

    def project(
        self,
        workspace_view: dict[str, Any],
        *,
        state_version: int | None = None,
        session_epoch: int | None = None,
        latest_observation: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Return an agent-facing ProverWorkspaceView.

        ``workspace_view`` is expected to be a completed snapshot output from
        the REPL/session pipeline.  Optional version fields are attached for
        audit/freshness checks; the agent is not asked to echo them back.
        """
        clean = self.sanitize_agent_view(workspace_view)
        if latest_observation:
            self._attach_latest_observation(clean, latest_observation)
        if state_version is not None:
            clean["based_on_state_version"] = int(state_version)
        if session_epoch is not None:
            clean["session_epoch"] = int(session_epoch)
        clean["view_hash"] = self.view_hash(clean)
        return self.order_agent_view(clean)

    def sanitize_agent_view(self, workspace_view: dict[str, Any]) -> dict[str, Any]:
        data = _json_clone(_dict(workspace_view))
        if not data:
            return {}
        self.normalize_decision_context(data)
        self._migrate_legacy_panels(data)
        self._rename_view_focus_fields(data)
        clean = self._scrub_backend_fields(data)
        if isinstance(clean, dict):
            self._compact_inspect_lookup_handles(clean)
            self._enforce_panel_policy(clean)
        return self.order_agent_view(clean) if isinstance(clean, dict) else {}

    def _enforce_panel_policy(self, view: dict[str, Any]) -> None:
        """Single runtime policy point: HARD-strip standing framing + collapse
        over-budget panels and attach honest provenance markers, per
        ``core/easycrypt/panel_policy.py`` (the same rules the CI audit
        ``workflow/validation/view_philosophy_audit.py`` checks, so the two
        never drift). Must never break view projection — degrade gracefully."""
        try:
            from core.easycrypt.panel_policy import enforce as _enforce  # type: ignore
            _enforce(view)
        except Exception:
            pass

    def _rename_view_focus_fields(self, data: dict[str, Any]) -> None:
        """Use display-facing names for the workspace projection mode.

        Internally the render plan still calls this value ``goal_family``.
        Agent-facing JSON should call it ``view_focus`` so it is not confused
        with the EasyCrypt/native ``goal_type``.
        """
        current_goal = _dict(data.get("current_goal"))
        if current_goal:
            if current_goal.get("goal_family") and not current_goal.get("view_focus"):
                current_goal["view_focus"] = current_goal.get("goal_family")
            current_goal.pop("goal_family", None)
            data["current_goal"] = current_goal
        proof_frontier = _dict(data.get("proof_frontier"))
        if proof_frontier:
            if proof_frontier.get("family") and not proof_frontier.get("view_focus"):
                proof_frontier["view_focus"] = proof_frontier.get("family")
            proof_frontier.pop("family", None)
            data["proof_frontier"] = proof_frontier
        program_frontier = _dict(data.get("program_frontier"))
        if program_frontier:
            if program_frontier.get("family") and not program_frontier.get("view_focus"):
                program_frontier["view_focus"] = program_frontier.get("family")
            program_frontier.pop("family", None)
            data["program_frontier"] = program_frontier

    def order_agent_view(self, workspace_view: dict[str, Any]) -> dict[str, Any]:
        """Return the view in GOAL-DYNAMIC human panel order, metadata last.

        A stable situation header + footer keeps the agent oriented; only the
        decision cluster (the synthesized options + the structural surfaces) is
        reordered by the current proof layer so the surfaces that drive the next
        move come first (a call goal leads with call_site_surface, a seq goal
        with seq_cut_surface, …). Machine-only size metadata is stripped and the
        ``surface_profile`` config panel is hidden. Falls back to the static
        order if the policy is unavailable. Single source of truth:
        ``core/easycrypt/panel_policy.py``.
        """
        import copy
        data = copy.deepcopy(_dict(workspace_view))
        if not data:
            return {}
        try:
            from core.easycrypt.panel_policy import (  # type: ignore
                panel_order_for, strip_machine_metadata)
            strip_machine_metadata(data)
            order = panel_order_for(data, pin_last=tuple(AGENT_VIEW_METADATA_ORDER))
            if order:
                return {key: data[key] for key in order}
        except Exception:
            pass
        # Fallback: static panel order.
        out: dict[str, Any] = {}
        used = set(AGENT_VIEW_PANEL_ORDER) | set(AGENT_VIEW_METADATA_ORDER)
        for key in AGENT_VIEW_PANEL_ORDER:
            if key in data:
                out[key] = data[key]
        for key, value in data.items():
            if key not in used:
                out[key] = value
        for key in AGENT_VIEW_METADATA_ORDER:
            if key in data:
                out[key] = data[key]
        return out

    def agent_display_view(self, workspace_view: dict[str, Any]) -> dict[str, Any]:
        """Return the proof-only view shown to the agent.

        The full projected view keeps freshness/hash metadata for audit and
        manager checks.  The agent does not need to inspect or echo those
        values, so the rendered IDE surface hides them.
        """
        ordered = self.order_agent_view(self.sanitize_agent_view(workspace_view))
        return {
            key: value
            for key, value in ordered.items()
            if key not in AGENT_HIDDEN_METADATA_FIELDS
        }

    def _attach_latest_observation(
        self,
        data: dict[str, Any],
        latest_observation: dict[str, Any],
    ) -> None:
        observation = _humanize_latest_observation(
            _drop_empty(self._scrub_backend_fields(latest_observation))
        )
        if not observation:
            return
        data["last_result"] = _drop_empty(observation)
        observation_messages = _note_messages_from_observation(observation)
        diagnostics = _dict(data.get("facts_and_diagnostics"))
        if observation_messages and isinstance(diagnostics.get("notes"), list):
            diagnostics["notes"] = [
                note for note in _dedupe_notes(_dict_list(diagnostics.get("notes")))
                if str(note.get("message") or "").strip() not in observation_messages
            ]
            data["facts_and_diagnostics"] = _drop_empty(diagnostics)

    def _migrate_legacy_panels(self, data: dict[str, Any]) -> None:
        """Project older workspace panels into the v2 IDE surface.

        This keeps manager handoffs and tests that still construct v1-shaped
        fixtures readable without exposing legacy names to the agent.

        Legacy ``decision_context`` fields are projected into their v2 owners
        (``application_context`` and ``candidate_moves``), then removed. Normal
        presentation never receives a second decision-context side channel.
        """
        if "proof_status" not in data and isinstance(data.get("proof_position"), dict):
            old = _dict(data.get("proof_position"))
            current_goal = _dict(data.get("current_goal"))
            data["proof_status"] = _drop_empty({
                "status": old.get("status"),
                "remaining_goals": old.get("remaining_goals"),
                "remaining_goals_known": old.get("remaining_goals_known"),
                "goal_type": current_goal.get("goal_type"),
                "view_focus": current_goal.get("view_focus"),
                "current_layer": old.get("current_layer"),
            })
        if "program_frontier" not in data and isinstance(data.get("proof_frontier"), dict):
            data["program_frontier"] = data.get("proof_frontier")
        if "application_context" not in data and isinstance(data.get("decision_context"), dict):
            data["application_context"] = _legacy_application_context(
                _dict(data.get("decision_context"))
            )
        if "candidate_moves" not in data and isinstance(data.get("decision_context"), dict):
            decision_context = _dict(data.get("decision_context"))
            data["candidate_moves"] = _drop_empty({
                "moves": _dict_list(decision_context.get("proof_options")),
                "limitations": _dict_list(decision_context.get("limitations")),
            })
        if "facts_and_diagnostics" not in data:
            facts = _dict(data.get("facts_and_gaps"))
            diagnostics = _dict(data.get("recent_diagnostics"))
            latest = diagnostics.pop("latest_observation", None)
            if latest and "last_result" not in data:
                data["last_result"] = latest
            facts_and_diagnostics = _drop_empty({
                "facts": facts.get("surface") if isinstance(facts.get("surface"), dict) else facts,
                "fact_note": facts.get("note"),
                "errors": diagnostics.get("errors"),
                "notes": diagnostics.get("notes"),
            })
            if facts_and_diagnostics:
                data["facts_and_diagnostics"] = facts_and_diagnostics
        if "inspect_lookup_handles" not in data and isinstance(data.get("want_more_context"), dict):
            data["inspect_lookup_handles"] = data.get("want_more_context")
        for key in (
            "proof_position",
            "proof_frontier",
            "facts_and_gaps",
            "decision_context",
            "recent_diagnostics",
            "want_more_context",
        ):
            data.pop(key, None)

    def _compact_inspect_lookup_handles(self, data: dict[str, Any]) -> None:
        """Keep the tool menu compact without losing read-only semantics."""

        handles = _dict(data.get("inspect_lookup_handles"))
        if not handles:
            return
        ask_manager_for = _dict_list(handles.get("ask_manager_for"))
        lookup_candidates = _dict_list(handles.get("lookup_candidates"))
        any_runtime_note = bool(
            handles.get("manager_note")
            or any(
                item.get("runtime_note") or item.get("note")
                for item in ask_manager_for
            )
        )
        clean_ask: list[dict[str, Any]] = []
        for item in ask_manager_for:
            compact = dict(item)
            compact.pop("effect", None)
            compact.pop("runtime_note", None)
            compact.pop("note", None)
            lookup_candidates.extend(_lookup_candidates_from_handle_text(compact))
            payload = _dict(compact.get("payload"))
            intent = str(compact.get("intent") or "").strip().replace("-", "_")
            topic = _normalize_inspect_topic(
                payload.get("topic") or compact.get("topic")
            )
            if not topic and intent in _DIRECT_CONTEXT_TOPIC_INTENTS:
                topic = intent
            if not topic:
                continue
            if topic == "suggest_close":
                continue
            compact.pop("topic", None)
            compact["intent"] = topic
            payload.pop("topic", None)
            public_intent = topic
            spec = intent_spec(public_intent)
            if spec is not None and not spec.advertised:
                continue
            compact["payload"] = payload
            clean_ask.append(_drop_empty(direct_context_request(compact)))
        clean_lookup: list[dict[str, Any]] = []
        seen_lookup: set[str] = set()
        for item in lookup_candidates:
            compact = dict(item)
            compact.pop("effect", None)
            compact.pop("runtime_note", None)
            compact.pop("note", None)
            symbol = str(compact.get("symbol") or "").strip()
            if not symbol or symbol in seen_lookup:
                continue
            seen_lookup.add(symbol)
            compact.setdefault("intent", "lookup_symbol")
            clean_lookup.append(_drop_empty(add_intent_contract(compact)))
        for key in ("full_context", "full_context_artifact", "view_fields"):
            handles.pop(key, None)
        if clean_ask or clean_lookup:
            handles["effect"] = (
                "All handles here are read-only manager requests; the "
                "committed EasyCrypt proof state stays unchanged."
            )
        if any_runtime_note:
            handles["manager_note"] = (
                "Some requests may ask EasyCrypt or name resolution; wait for "
                "the manager result before choosing the next proof intent."
            )
        handles["ask_manager_for"] = clean_ask
        handles["lookup_candidates"] = clean_lookup
        data["inspect_lookup_handles"] = _drop_empty(handles)

    def lint_agent_view(self, workspace_view: dict[str, Any]) -> list[str]:
        text = json.dumps(workspace_view, sort_keys=True)
        lower_text = text.lower()
        issues: list[str] = []
        for marker in self.backend_command_markers:
            if marker in text:
                issues.append(f"backend marker leaked into agent view: {marker}")
        for marker in self.agent_cost_wording_markers:
            if marker in lower_text:
                issues.append(
                    f"cost-style wording leaked into agent view: {marker}"
                )
        for marker in self.internal_source_markers:
            if marker in text:
                issues.append(
                    f"internal source marker leaked into agent view: {marker}"
                )
        for field in self.forbidden_field_names:
            if self._field_exists(workspace_view, field):
                issues.append(f"forbidden agent-facing field present: {field}")
        issues.extend(_low_level_inspect_topic_leaks(workspace_view))
        issues.extend(_bare_enum_leaks(workspace_view))
        return issues

    def view_hash(self, workspace_view: dict[str, Any]) -> str:
        text = json.dumps(workspace_view, sort_keys=True)
        return hashlib.sha1(text.encode("utf-8")).hexdigest()

    def normalize_decision_context(self, data: dict[str, Any]) -> None:
        if isinstance(data.get("decision_context"), dict):
            return
        legacy = _dict(data.get("suggested_next_steps") or data.get("next_actions"))
        if not legacy:
            return
        proof_options: list[dict[str, Any]] = []
        primary_and_alternatives = [
            _dict(legacy.get("primary")),
            *_dict_list(legacy.get("alternatives")),
        ]
        for item in primary_and_alternatives:
            option = self._proof_option_from_action(item)
            if option:
                proof_options.append(option)
        context_handles: list[dict[str, Any]] = []
        for item in primary_and_alternatives:
            if str(item.get("category") or "") not in {"inspect", "diagnose", "verify"}:
                continue
            handle = self._context_handle_from_action(item)
            if handle:
                context_handles.append(handle)
        for item in _dict_list(
            legacy.get("context_hints") or legacy.get("background_hints")
        ):
            handle = self._context_handle_from_action(item)
            if handle:
                context_handles.append(handle)
        avoid = [
            self._limitation_from_action(item)
            for item in _dict_list(legacy.get("avoid") or legacy.get("blocked"))
        ]
        data["decision_context"] = _drop_empty({
            "proof_options": proof_options,
            "context_handles": context_handles,
            "limitations": [item for item in avoid if item],
        })

    def _proof_option_from_action(self, action: dict[str, Any]) -> dict[str, Any]:
        if not action:
            return {}
        category = str(action.get("category") or "").strip()
        if category in {"inspect", "diagnose"}:
            return {}
        command_text = str(action.get("command") or "").strip()
        tactic = str(
            action.get("tactic")
            or action.get("tactic_shape")
            or action.get("action")
            or (
                command_text
                if command_text and not any(
                    marker in command_text for marker in self.backend_command_markers
                )
                else ""
            )
            or ""
        ).strip()
        guidance = str(action.get("guidance") or "").strip()
        evidence = [
            str(item)
            for item in (
                action.get("evidence")
                if isinstance(action.get("evidence"), list)
                else []
            )
            if str(item).strip()
        ]
        why = str(action.get("why") or "").strip()
        if why:
            evidence.append(why)
        verification = _verification_evidence(action)
        if verification:
            evidence.append(verification)
        title = _proof_option_title(
            action,
            category=category,
            tactic=tactic,
            guidance=guidance,
            evidence=evidence,
        )
        if (
            (category or "strategy") in {"strategy", "hint", "none"}
            and not tactic
            and not guidance
            and not evidence
            and not title
        ):
            return {}
        if (category or "") == "none":
            return {}
        option = {
            "title": title,
            "category": category or "strategy",
            "applicability": _applicability(action),
            "effect": _effect_text(action),
            "tactic": tactic,
            "guidance": guidance,
            "evidence": evidence[:3],
            "source": _human_source(str(action.get("source") or "").strip()),
            # Preserve the STRUCTURED provenance (not just the humanized source) so
            # the downstream provenance stamper can classify a daemon-probe-accepted
            # candidate as verified instead of defaulting it to "unverified" — which
            # otherwise contradicts a "Daemon probe accepted…" guidance string.
            "confidence": str(action.get("confidence") or "").strip(),
            "epistemic_status": str(
                action.get("epistemic_status")
                or _dict(action.get("metadata")).get("epistemic_status")
                or ""
            ).strip(),
        }
        name_status = str(action.get("name_resolution_status") or "").strip()
        if name_status:
            option["cost_factors"] = {"name_resolution_status": name_status}
        if action.get("needs_instantiation") or action.get("requires_instantiation"):
            option.update(_instantiation_guidance(action))
        _demote_structural_named_call(option, action)
        return _drop_empty(option)

    def _context_handle_from_action(self, action: dict[str, Any]) -> dict[str, Any]:
        if not action:
            return {}
        exact_lookups = _lookup_candidates_from_handle_text(action)
        if exact_lookups:
            lookup = exact_lookups[0]
            return _drop_empty(direct_context_request({
                "category": str(action.get("category") or "").strip(),
                "intent": "lookup_symbol",
                "payload": {"symbol": lookup.get("symbol")},
                "effect": _effect_text(action) or (
                    "This asks the manager for information only; it does not "
                    "change the EasyCrypt proof state."
                ),
                "use_when": lookup.get("use_when"),
                "source": _human_source(str(action.get("source") or "").strip()),
            }))
        topic = str(
            action.get("topic")
            or action.get("request")
            or action.get("tool")
            or "",
        ).strip().lstrip("-").replace("-", "_")
        handle = str(
            action.get("handle")
            or topic
            or action.get("category")
            or ""
        ).strip()
        intent = _semantic_intent(handle)
        if not intent:
            return {}
        target = str(action.get("target") or topic or "").strip()
        payload: dict[str, Any] = {}
        fields = intent_payload_fields(intent)
        for field_name in fields:
            value = action.get(field_name)
            if value is None and len(fields) == 1:
                value = target
            if value is not None and str(value).strip():
                payload[field_name] = value
        if intent == "lookup_symbol" and not payload.get("symbol"):
            return {}
        why = str(action.get("why") or action.get("guidance") or "").strip()
        return _drop_empty(direct_context_request({
            "category": str(action.get("category") or "").strip(),
            "intent": intent,
            "payload": payload,
            "effect": _effect_text(action) or (
                "This asks the manager for information only; it does not "
                "change the EasyCrypt proof state."
            ),
            "use_when": why,
            "source": _human_source(str(action.get("source") or "").strip()),
        }))

    def _limitation_from_action(self, action: dict[str, Any]) -> dict[str, Any]:
        return _drop_empty({
            "category": str(action.get("category") or "avoid"),
            "detail": str(action.get("why") or action.get("guidance") or "").strip(),
            "source": _human_source(str(action.get("source") or "").strip()),
        })

    def _scrub_backend_fields(self, value: Any) -> Any:
        if isinstance(value, dict):
            out: dict[str, Any] = {}
            for key, item in value.items():
                if key in self.forbidden_field_names:
                    continue
                if key == "debug_cli_fallback":
                    continue
                if key == "command":
                    continue
                if key == "code":
                    continue
                if key == "tool" and str(item).startswith("-"):
                    continue
                out[key] = self._scrub_backend_fields(item)
            return out
        if isinstance(value, list):
            return [
                self._scrub_backend_fields(item)
                for item in value
            ]
        if isinstance(value, str):
            return self._scrub_backend_text(value)
        return value

    def _scrub_backend_text(self, text: str) -> str:
        out = text
        for marker in self.backend_command_markers:
            if marker in out:
                out = out.replace(marker, "manager")
        replacements = {
            "ProofIR compiler surface": "proof-state analysis",
            "ProofIR/action readiness": "proof-state readiness",
            "AUTO-PIVOT-CALL-READY": "call-site check",
            "AUTO-CALL-SUGGEST": "call-site analysis",
            "AUTO-ASYM-SEQ": "asymmetric seq-cut check",
            "AUTO-DIFF": "program-difference analysis",
            "AUTO-PIVOT": "probability-route analysis",
            "ProofIR": "proof-state analysis",
        }
        for marker, replacement in replacements.items():
            out = out.replace(marker, replacement)
        out = out.replace("Lookup first:", "Possible context:")
        out = out.replace("after Pr handles are exhausted", "when comparing routes")
        return out

    def _field_exists(self, value: Any, field: str) -> bool:
        if isinstance(value, dict):
            return field in value or any(self._field_exists(v, field) for v in value.values())
        if isinstance(value, list):
            return any(self._field_exists(item, field) for item in value)
        return False


def build_workspace_view_plan(
    proof_context_view: dict[str, Any],
    *,
    max_alternatives: int = 3,
    max_evidence: int = 6,
) -> WorkspaceViewPlan:
    """Return the centralized render policy for a ProofContextView."""

    view = _dict(proof_context_view)
    proof_state = _dict(view.get("proof_state"))
    proof_goal = _dict(proof_state.get("goal"))
    current_goal = _dict(view.get("current_goal"))
    proof_ir = _dict(view.get("proof_ir"))
    phase = _dict(proof_ir.get("phase"))
    phase_resources = _dict(phase.get("resource_summary"))
    resources = _dict(proof_ir.get("resources"))
    actions = _dict_list(view.get("actions"))
    errors = _dict_list(view.get("errors")) + _dict_list(proof_ir.get("diagnostics"))
    phase_name = _first_text(
        phase.get("name"),
        proof_ir.get("current_layer"),
        default="unknown",
    )
    goal_type = _first_text(
        proof_goal.get("goal_type"),
        current_goal.get("goal_type"),
        proof_ir.get("goal_type"),
        default="unknown",
    )

    raw_goal = _first_text(
        current_goal.get("active_goal_text"),
        current_goal.get("active_goal_preview"),
        default="",
    )
    goal_family = _classify_goal_family(
        proof_state=proof_state,
        proof_goal=proof_goal,
        current_goal=current_goal,
        proof_ir=proof_ir,
        phase=phase,
        resources={**resources, **phase_resources},
        actions=actions,
        errors=errors,
        raw_goal=raw_goal,
    )
    budget = _budget_for(
        goal_family,
        raw_goal=raw_goal,
        max_alternatives=max_alternatives,
        max_evidence=max_evidence,
    )
    focus = _focus_for(goal_family)
    frontier_keys = _frontier_resource_keys_for(goal_family)
    phase_resource_keys = _phase_resource_keys_for(goal_family, frontier_keys)
    frontier_checks = _frontier_checks_for(goal_family)
    panels = _panels_for(goal_family, budget)
    return WorkspaceViewPlan(
        goal_family=goal_family,
        goal_display_mode=_goal_display_mode(goal_family),
        phase_summary=_phase_summary_for(
            layer=phase_name,
            goal_type=goal_type,
        ),
        budget=budget,
        panels=panels,
        authority_order=(
            "EasyCrypt-native proof state",
            "ProofIR compiler surface",
            "current tool views",
            "KB/legacy heuristics",
        ),
        inspect_order=_inspect_order_for(goal_family),
        focus=focus,
        phase_resource_keys=phase_resource_keys,
        frontier_resource_keys=frontier_keys,
        frontier_checks=frontier_checks,
    )


def _classify_goal_family(
    *,
    proof_state: dict[str, Any],
    proof_goal: dict[str, Any],
    current_goal: dict[str, Any],
    proof_ir: dict[str, Any],
    phase: dict[str, Any],
    resources: dict[str, Any],
    actions: list[dict[str, Any]],
    errors: list[dict[str, Any]],
    raw_goal: str,
) -> str:
    if _candidate_closed(proof_state, current_goal):
        return "closed_candidate"

    layer = _first_text(
        phase.get("name"),
        proof_ir.get("current_layer"),
        default="",
    ).lower()
    goal_type = _first_text(
        proof_goal.get("goal_type"),
        current_goal.get("goal_type"),
        proof_ir.get("goal_type"),
        default="",
    ).lower()
    goal_kind = _first_text(proof_ir.get("goal_kind"), default="").lower()
    text = raw_goal.lower()
    resource_words = " ".join(str(key).lower() for key in resources.keys())
    action_words = " ".join(
        str(action.get(field) or "").lower()
        for action in actions
        for field in ("id", "title", "category", "tactic", "source")
    )
    error_words = " ".join(
        str(error.get(field) or "").lower()
        for error in errors
        for field in ("code", "message", "diagnostic")
    )

    if error_words and any(word in error_words for word in ("failure", "error", "blocked")):
        return "failure_diagnostic"
    if (
        "seq" in action_words
        or "seq" in resource_words
        or "seq" in goal_kind
    ) and any(
        word in (resource_words + " " + action_words + " " + error_words)
        for word in ("coverage", "missing_live", "live", "preserved", "prefix")
    ):
        return "seq_cut"
    if (
        layer == "pr"
        or goal_type in {"pr", "probability"}
        or "probability" in goal_kind
        or "pr[" in raw_goal
        or "\\pr" in text
        or "pr[" in action_words
    ):
        return "probability"
    # The first three are STRONG relational signals (a live equiv/pRHL judgement).
    # The `{1}`/`{2}` clause is a WEAK text fallback: a pure-logic residual that EC
    # has reduced to an ambient goal (layer/goal_type == ambient) still carries
    # memory-tagged variables (`F.m{1}`, `oget …{2}`) with NO two-column program
    # frontier, so it must NOT be dragged into the relational-surgery family on that
    # text alone. Panel re-audit cluster RTF_FixC: items 048/068/069/077/078/079 are
    # ambient_logic leaves whose right move is `smt`/`rewrite`/`move`, yet the weak
    # clause routed them to the relational menu (call/sp/wp/swap/conseq surgery). The
    # renderer already framed them as "Pure Logic"; this realigns goal_family so the
    # menu/budget/display agree. Program-bearing relational frontiers
    # (procedure_body/call_site/prhl_module/verification_residue, e.g. item 042) keep
    # `relational_program` — their layer is never `ambient_logic`.
    is_ambient_residual = layer == "ambient_logic" or goal_type == "ambient"
    if (
        goal_type in {"equiv", "prhl", "equivalence"}
        or "prhl" in layer
        or "equiv [" in text
        or (not is_ambient_residual and "{1}" in raw_goal and "{2}" in raw_goal)
    ):
        return "relational_program"
    if is_ambient_residual:
        return "ambient_logic"
    if (
        layer in {"procedure_entry", "procedure_body", "call_site"}
        or "procedure" in layer
        or "call_site" in layer
        or any(token in text for token in ("while", "if ", "<@", "call", ":="))
    ):
        return "procedure_frontier"
    return "unknown"


def _candidate_closed(
    proof_state: dict[str, Any],
    current_goal: dict[str, Any],
) -> bool:
    transition = _dict(proof_state.get("latest_transition"))
    event_contract = _dict(proof_state.get("event_contract"))
    proof_goal = _dict(proof_state.get("goal"))
    goal_closed_visible = _goal_visibly_closed(current_goal, proof_goal)
    return bool(
        (_transition_can_mark_closed(transition) and goal_closed_visible)
        or (
            event_contract.get("candidate_closed")
            and goal_closed_visible
        )
    )


def _budget_for(
    goal_family: str,
    *,
    raw_goal: str,
    max_alternatives: int,
    max_evidence: int,
) -> DisplayBudget:
    if goal_family == "closed_candidate":
        lines, chars, frontier = 200, 12000, 800
    elif goal_family == "ambient_logic":
        lines, chars, frontier = 400, 30000, 1000
    elif goal_family == "probability":
        lines, chars, frontier = 500, 30000, 2200
    elif goal_family in {"relational_program", "procedure_frontier", "seq_cut", "failure_diagnostic"}:
        lines, chars, frontier = 800, 30000, 2600
    else:
        lines, chars, frontier = 500, 30000, 1600

    if len(raw_goal) > chars:
        chars = max(chars, DEFAULT_GOAL_WINDOW_CHARS)
    return DisplayBudget(
        goal_window_lines=lines,
        goal_window_chars=chars,
        frontier_chars=frontier,
        max_alternatives=max_alternatives,
        max_evidence=max_evidence,
    )


def _goal_display_mode(goal_family: str) -> str:
    return {
        "ambient_logic": "compact_goal_with_exact_window",
        "closed_candidate": "closed_candidate_status",
        "probability": "probability_goal_with_bridge_focus",
        "relational_program": "relational_program_window",
        "procedure_frontier": "procedure_frontier_window",
        "seq_cut": "seq_cut_coverage_window",
        "failure_diagnostic": "diagnostic_window",
    }.get(goal_family, "general_goal_window")


def _focus_for(goal_family: str) -> tuple[str, ...]:
    return {
        "ambient_logic": (
            "pure goal shape",
            "available local facts/operators",
            "closing tactics only after the shape is clear",
        ),
        "closed_candidate": (
            "proof state says no remaining goals",
            "save with qed before final verification",
        ),
        "probability": (
            "Pr endpoints",
            "typed bridge/path resources",
            "normalization and bound obligations",
            "program lowering only as an explicit fallback",
        ),
        "relational_program": (
            "LHS/RHS program frontier",
            "typed call handles",
            "wrapper/core map",
            "live resources before destructive lowering",
        ),
        "procedure_frontier": (
            "current statement frontier",
            "call-site liveness",
            "program edit actions",
            "loop or invariant skeleton",
        ),
        "seq_cut": (
            "cut coverage",
            "missing live post facts",
            "preserved variables and prefix reads",
            "weak-cut warnings",
        ),
        "failure_diagnostic": (
            "latest EasyCrypt error",
            "failure-specific compiler diagnostic",
            "frontier/resource state",
            "non-destructive next inspection",
        ),
    }.get(goal_family, (
        "current goal text",
        "compiler phase if available",
        "fresh actions before legacy hints",
    ))


def _frontier_resource_keys_for(goal_family: str) -> tuple[str, ...]:
    common = (
        "live_call_sites",
        "frontier_call_sites",
        "live_callable_lemmas",
        "callable_now_lemmas",
    )
    if goal_family == "probability":
        return (
            "pr_rewrite_candidates",
            "has_pr_normal_form",
            "has_pr_arithmetic_plan",
            "has_pr_obligation_plan",
            "pr_obligation_primary_strategy",
            "native_ast_search_hits",
        )
    if goal_family == "seq_cut":
        return (
            "seq_cut_candidates",
            "seq_cut_coverage",
            "coverage",
            "missing_live_facts",
            "preserved_vars",
            "live_post_vars",
            "prefix_read_vars",
            "has_invariant_skeleton",
        )
    if goal_family in {"relational_program", "procedure_frontier", "failure_diagnostic"}:
        return common + (
            "oracle_obligation_handles",
            "has_invariant_skeleton",
            "program_edit_script",
            "frontier_statement",
            "asymmetric_instrumentation_map",
            "asymmetric_instrumentation_regions",
            "one_sided_instrumentation",
            "instrumentation_regions",
        )
    return ()


def _phase_resource_keys_for(
    goal_family: str,
    frontier_keys: tuple[str, ...],
) -> tuple[str, ...]:
    always = (
        "native_ast_search_queries",
        "native_ast_search_hits",
        "unfoldable_goal_heads",
        "unfoldable_goal_head_count",
    )
    if goal_family == "probability":
        family = (
            "has_probabilistic_vc_frontend",
            "has_pr_normal_form",
            "has_pr_arithmetic_plan",
            "has_pr_obligation_plan",
            "pr_obligation_primary_strategy",
            "pr_rewrite_candidates",
        )
    elif goal_family == "seq_cut":
        family = (
            "seq_cut_candidates",
            "seq_cut_coverage",
            "coverage",
            "missing_live_facts",
            "preserved_vars",
            "live_post_vars",
            "prefix_read_vars",
            "has_invariant_skeleton",
        )
    elif goal_family in {"relational_program", "procedure_frontier", "failure_diagnostic"}:
        family = (
            "live_call_sites",
            "frontier_call_sites",
            "live_callable_lemmas",
            "callable_now_lemmas",
            "oracle_obligation_handles",
            "has_invariant_skeleton",
            "program_edit_script",
            "frontier_statement",
            "asymmetric_instrumentation_map",
            "asymmetric_instrumentation_regions",
            "one_sided_instrumentation",
            "instrumentation_regions",
        )
    else:
        family = ()
    return _dedupe(always + family + frontier_keys)


def _phase_summary_for(*, layer: str, goal_type: str) -> str:
    if layer == "pr":
        return "Probability layer: Pr rewrites, bounds, path steps, and direct byequiv are route context; choose by endpoint match."
    if layer == "call_site":
        return "Call-site layer: live named equiv/call handles are route context for the exposed frontier."
    if layer == "procedure_body":
        return "Procedure-body layer: use local program tactics such as wp, sp, seq, if, while, or rnd."
    if layer == "verification_residue":
        return "Residual layer: the main structure is exposed; close pure or synchronized side conditions."
    if layer == "ambient_logic":
        return "Ambient logic layer: close non-program obligations with rewrites, auto, or SMT."
    if layer == "procedure_entry":
        return "Procedure-entry layer: expose the body before choosing statement-level tactics."
    if layer == "prhl_module":
        return "pRHL module layer: expose aligned programs or use module-level equivalence handles."
    if layer and layer != "unknown":
        return f"{layer} layer for a {goal_type} goal."
    return f"No compiler phase identified yet for this {goal_type} goal."


def _frontier_checks_for(goal_family: str) -> tuple[str, ...]:
    # Only epistemic GUARDRAILS remain (view boundary §5 keeps guardrails). The
    # route-preference prose ("Pr resources are context: use them when…",
    # "Direct byequiv is a valid route when…", "Check whether … before applying…")
    # was the same phase prefer/avoid guidance removed from `_phase_guidance`;
    # the underlying facts live in `resource_summary` / `live_fact_coverage`.
    return {
        "procedure_frontier": (
            "Keep one-sided instrumentation as a map, not as a tactic recipe.",
        ),
        "seq_cut": (
            "A runnable seq candidate is not evidence that the invariant is strong enough.",
        ),
        "failure_diagnostic": (
            "Diagnostics locate the frontier; do not infer a proof script from an error.",
        ),
    }.get(goal_family, ())


def _inspect_order_for(goal_family: str) -> tuple[str, ...]:
    base = (
        "Read current_goal.lines first; it preserves the current goal as ordered EasyCrypt lines.",
        "If text_fully_shown=false, read only the current session's current.out.",
    )
    if goal_family == "probability":
        return base + (
            "Use phase/frontier resources as route context for typed Pr paths, bridges, bound plans, or direct program equivalence.",
            "For tactic syntax, ask the manager for tactic_forms.",
            "For timeline/confusion, ask the manager for episode_view.",
        )
    if goal_family in {"relational_program", "procedure_frontier", "seq_cut"}:
        return base + (
            "Use the frontier panel for LHS/RHS call sites, live handles, instrumentation, and coverage.",
            "For tactic syntax, ask the manager for tactic_forms.",
            "For timeline/confusion, ask the manager for episode_view.",
        )
    if goal_family == "failure_diagnostic":
        return base + (
            "Read errors and diagnostics before submitting another mutating tactic.",
            "Ask the manager for diagnose for structured repair hints.",
            "For timeline/confusion, ask the manager for episode_view.",
        )
    return base + (
        "For tactic syntax, ask the manager for tactic_forms.",
        "For timeline/confusion, ask the manager for episode_view.",
    )


def _panels_for(goal_family: str, budget: DisplayBudget) -> tuple[PanelPlan, ...]:
    panels = [
        PanelPlan(
            "state",
            "EasyCrypt-native proof state",
            "authoritative proof status and exact current-goal window",
            budget.goal_window_chars,
        ),
        PanelPlan(
            "phase",
            "ProofIR compiler surface",
            "current abstraction layer and phase guardrails",
        ),
    ]
    if goal_family in {
        "probability",
        "relational_program",
        "procedure_frontier",
        "seq_cut",
        "failure_diagnostic",
    }:
        panels.append(PanelPlan(
            "frontier",
            "ProofIR compiler surface",
            "goal-family-specific resource/frontier summary",
            budget.frontier_chars,
        ))
    panels.extend([
        PanelPlan(
            "next",
            "fresh actions",
            "runnable and inspection actions after phase policy",
        ),
        PanelPlan(
            "evidence",
            "mixed source summary",
            "short provenance bullets without raw internal menus",
        ),
        PanelPlan(
            "inspect",
            "source policy",
            "where to get more detail if this compact view is insufficient",
        ),
    ])
    return tuple(panels)



def _normalize_inspect_topic(value: Any) -> str:
    topic = _first_text(value, default="").strip().lstrip("-").replace("-", "_")
    if topic in _LOW_LEVEL_INSPECT_TOPICS:
        return ""
    return topic


def _lookup_candidates_from_handle_text(handle: dict[str, Any]) -> list[dict[str, Any]]:
    text = " ".join(
        _first_text(handle.get(key), default="")
        for key in ("use_when", "guidance", "why", "returns", "command", "action")
    )
    out: list[dict[str, Any]] = []
    for match in re.finditer(r"(?:^|[`\s])-(?:where|sig)\s+([A-Za-z_][A-Za-z0-9_.'`]*)", text):
        symbol = match.group(1).strip("`'\"").rstrip("`'\".,;:")
        if not symbol:
            continue
        out.append({
            "symbol": symbol,
            "use_when": (
                f"Resolve exact signature for `{symbol}` only when this "
                "route is being tested."
            ),
        })
    return out


def _dedupe_notes(notes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for note in notes:
        message = str(note.get("message") or "").strip()
        severity = str(note.get("severity") or "").strip()
        key = f"{severity}\n{message}"
        if not message or key in seen:
            continue
        seen.add(key)
        out.append(_drop_empty({
            "message": message,
            "severity": severity,
        }))
    return out


def _note_messages_from_observation(observation: dict[str, Any]) -> set[str]:
    content = _dict(observation.get("content"))
    messages: set[str] = set()
    for note in _dict_list(content.get("notes")):
        message = str(note.get("message") or "").strip()
        if message:
            messages.add(message)
    return messages


def _legacy_application_context(decision_context: dict[str, Any]) -> dict[str, Any]:
    invariant_inputs = _dict(decision_context.get("call_invariant_inputs"))
    if invariant_inputs:
        return _drop_empty({
            "selected_handles": _dict_list(invariant_inputs.get("call_equiv_context")),
            "visible_call_frontier": invariant_inputs.get("visible_call_frontier"),
            "declaration_requirements": (
                _dict_list(invariant_inputs.get("required_external_facts"))
                + _dict_list(invariant_inputs.get("base_relation_inputs"))
            ),
            "visible_but_not_required": invariant_inputs.get(
                "visible_but_not_currently_required"
            ),
            "inspect_if_unsure": invariant_inputs.get("inspect_if_unsure"),
        })
    selected = []
    for option in _dict_list(decision_context.get("proof_options"))[:2]:
        selected.append(_drop_empty({
            "title": option.get("title"),
            "tactic": option.get("tactic"),
            "runnable_status": option.get("runnable_status"),
            "missing_input": option.get("missing_input"),
        }))
    return _drop_empty({"selected_handles": selected})


def _json_clone(value: Any) -> Any:
    try:
        return json.loads(json.dumps(value))
    except Exception:
        return value



def _applicability(action: dict[str, Any]) -> str:
    readiness = str(action.get("readiness") or "").strip()
    category = str(action.get("category") or "").strip()
    if readiness == "ready_to_run":
        return "This tactic is already concrete for the current goal."
    if readiness == "needs_instantiation":
        return _instantiation_applicability(action)
    if readiness == "reasoning_required" or category in {"strategy", "hint"}:
        return (
            "Use this as route-selection context; it is not a tactic to run "
            "as-is."
        )
    if readiness == "blocked" or category == "avoid":
        return (
            "The current context argues against this route; treat it as a "
            "guardrail, not as a candidate tactic."
        )
    if readiness == "inspect_first":
        return (
            "Ask the manager for this context before deciding whether it is "
            "relevant to the current proof state."
        )
    if readiness == "no_action":
        return "No proof action is available from this panel."
    return "Use this as proof context for the current goal."


def _effect_text(action: dict[str, Any]) -> str:
    effect = str(
        action.get("effect")
        or action.get("proof_state_effect")
        or "",
    ).strip()
    category = str(action.get("category") or "").strip()
    if effect == "will_change_proof_state" or category == "commit":
        return (
            "Committing this tactic would change the EasyCrypt proof state if "
            "EasyCrypt accepts it."
        )
    if effect in {
        "does_not_change_proof_state_read_only",
        "does_not_change_proof_state_verification_check",
    } or category in {"inspect", "diagnose", "verify", "hint"}:
        return (
            "This asks the manager for information only; it does not change "
            "the EasyCrypt proof state."
        )
    if effect in {"no_proof_state_effect", "no_proof_state_effect_guardrail"}:
        return "This does not change the EasyCrypt proof state."
    if category in {"strategy", "hint"} or not effect:
        return (
            "This is route-selection context only; it does not run a tactic "
            "or change the EasyCrypt proof state."
        )
    return effect


def _verification_evidence(action: dict[str, Any]) -> str:
    confidence = str(action.get("confidence") or "").strip()
    if confidence == "verified_by_easycrypt":
        return "EasyCrypt verified this against the current goal."
    return ""


def _demote_structural_named_call(
    option: dict[str, Any],
    action: dict[str, Any],
) -> None:
    """Keep unverified structural call hints visible without making them look runnable."""

    tactic = str(option.get("tactic") or action.get("tactic") or "").strip()
    if not tactic.startswith("call ") or "call (_:" in tactic:
        return
    if str(option.get("category") or "") not in {"strategy", "hint"}:
        return
    if str(option.get("source") or "") != "program-difference analysis":
        return
    evidence_text = " ".join(str(item) for item in option.get("evidence") or [])
    if "Unverified call/ecall items are structural hints only" not in evidence_text:
        return

    option["title"] = "Named-call context"
    option["applicability"] = (
        "This named-call shape came from program comparison. Treat it as "
        "context until manager-owned EasyCrypt validation confirms the "
        "lemma matches the visible call frontier."
    )
    option["runnable_status"] = (
        "Not established as runnable from this panel; use the current "
        "frontier and call-site context before deciding whether to commit it."
    )
    limitations = list(option.get("limitations") or [])
    limitations.append(
        "Do not treat this as the next call tactic solely because the name is "
        "visible; the current frontier still determines whether it applies."
    )
    option["limitations"] = limitations


def _proof_option_title(
    action: dict[str, Any],
    *,
    category: str,
    tactic: str,
    guidance: str,
    evidence: list[str],
) -> str:
    explicit = str(action.get("title") or "").strip()
    if explicit:
        return explicit
    family = _action_family(action)
    lowered = " ".join([tactic, guidance, " ".join(evidence)]).lower()
    head = tactic.split(None, 1)[0].strip(".;") if tactic else ""
    if family == "call_invariant_skeleton" or "call (_:" in lowered:
        return "Invariant-call route"
    if family == "call_named_equiv" or head == "call":
        return "Named-call route"
    if family == "sampling_coupling" or head == "rnd":
        return "Sampling-coupling route"
    if family == "splitwhile" or "splitwhile" in lowered:
        return "Loop-splitting route"
    if head == "while":
        return "Loop-invariant route"
    if head == "seq":
        return "Seq-cut route"
    if head in {"auto", "smt", "done", "trivial"}:
        return "Residual closing tactic"
    if "pr inequality" in lowered or "probability inequality" in lowered:
        return "Probability-inequality route"
    if "procedure region" in lowered or "program shape" in lowered:
        return "Program-shape context"
    if category == "commit":
        return "Concrete tactic candidate"
    if category in {"strategy", "hint"} and (guidance or evidence):
        return "Proof-route context"
    return ""


def _human_source(source: str) -> str:
    normalized = str(source or "").strip()
    if not normalized:
        return ""
    mapping = {
        "ProofIR": "proof-state analysis",
        "EasyCrypt": "EasyCrypt",
        "AUTO-DIFF": "program-difference analysis",
        "AUTO-PIVOT": "probability-route analysis",
        "AUTO-ASYM-SEQ": "asymmetric seq-cut check",
        "AUTO-CALL-SUGGEST": "call-site analysis",
        "AUTO-PIVOT-CALL-READY": "call-site check",
        "goal-info": "goal parser",
        "current_goal_hypothesis": "current goal hypothesis",
    }
    if normalized in mapping:
        return mapping[normalized]
    if normalized.isupper() and "-" in normalized:
        return normalized.lower().replace("-", " ").replace("_", " ")
    return normalized.replace("_", " ")


def _humanize_latest_observation(observation: dict[str, Any]) -> dict[str, Any]:
    data = dict(_dict(observation))
    status = str(data.pop("status", "") or "").strip()
    data.pop("ok", None)
    if status and not data.get("result"):
        data["result"] = _observation_status_wording(status)
    proof_state = str(data.get("proof_state") or "").strip()
    if proof_state in {"unchanged", "state_unchanged"}:
        data["proof_state"] = "The committed EasyCrypt proof state was not changed."
    elif proof_state == "changed":
        data["proof_state"] = "The committed EasyCrypt proof state changed."
    if str(data.get("effect") or "").strip():
        data["effect"] = _observation_effect_wording(str(data.get("effect") or ""))
    return _drop_empty(data)


def _observation_status_wording(status: str) -> str:
    if status == "preflight_accepted":
        return (
            "Private EasyCrypt preflight accepted this candidate. The committed proof "
            "state was not changed."
        )
    if status == "preflight_rejected":
        return (
            "Private EasyCrypt preflight rejected this candidate. The proof state was not "
            "changed; use the error summary to revise the tactic."
        )
    if status in {"failed", "error", "rejected"}:
        return "EasyCrypt rejected this proof step; use the error summary to revise it."
    if status == "timeout":
        return "The manager action timed out before producing a new completed view."
    return "The manager returned a result for the last proof-level request."


def _observation_effect_wording(effect: str) -> str:
    normalized = effect.strip()
    if normalized in {
        "read-only; proof state unchanged",
        "speculative only; proof state unchanged; not committed",
    }:
        return (
            "This was read-only; it did not change the committed EasyCrypt "
            "proof state."
        )
    if normalized == "context only; proof state unchanged":
        return (
            "This is route-selection context only; it does not run a tactic "
            "or change the EasyCrypt proof state."
        )
    return normalized


def _instantiation_applicability(action: dict[str, Any]) -> str:
    family = _action_family(action)
    tactic = str(action.get("tactic") or action.get("tactic_shape") or "").strip()
    if family == "call_invariant_skeleton" or "call (_:" in tactic:
        return (
            "This is a `call (_: Inv)` route template, not a complete tactic; "
            "fill in the invariant expression from the current goal before "
            "submitting it."
        )
    if family == "call_named_equiv" or tactic.startswith("call "):
        return (
            "This lemma-call shape is not a complete tactic yet; determine "
            "the missing module, procedure, or term arguments from the current "
            "goal before submitting it."
        )
    return (
        "This tactic shape still has placeholders; replace them with concrete "
        "EasyCrypt arguments from the current goal before submitting "
        "it."
    )


def _instantiation_limitation(action: dict[str, Any]) -> str:
    family = _action_family(action)
    tactic = str(action.get("tactic") or action.get("tactic_shape") or "").strip()
    if family == "call_invariant_skeleton" or "call (_:" in tactic:
        return (
            "The invariant is not filled in yet; use the current goal and, if "
            "helpful, call-subgoal preview to choose the concrete invariant."
        )
    if family == "call_named_equiv" or tactic.startswith("call "):
        return (
            "The call still needs concrete EasyCrypt arguments before it is a "
            "tactic to submit."
        )
    return (
        "The displayed tactic is a template; fill every placeholder with "
        "current-goal arguments before submitting it."
    )


def _instantiation_guidance(action: dict[str, Any]) -> dict[str, Any]:
    kind = _instantiation_kind(action)
    if kind == "call_invariant":
        return {
            "runnable_status": (
                "Not yet; replace `Inv` with a concrete EasyCrypt invariant "
                "before submitting this tactic."
            ),
            "missing_input": [
                "Concrete invariant expression inside `call (_: ...)`.",
            ],
            "how_to_complete": [
                (
                    "Read the current precondition, postcondition, and the "
                    "two visible call sites; include the state that must be "
                    "preserved across the adversary or oracle call."
                ),
                (
                    "If the call generates oracle obligations, include the "
                    "global/oracle state needed by the named oracle-equivalence "
                    "handles visible in the current context."
                ),
            ],
            "inspect_if_unsure": [
                direct_context_request({
                    "intent": "call_site_options",
                    "payload": {},
                    "why": (
                        "Shows the live call frontier and any named call or "
                        "oracle-equivalence handles."
                    ),
                }),
                direct_context_request({
                    "intent": "call_subgoals",
                    "payload": {},
                    "why": (
                        "After you have a candidate invariant, previews the "
                        "obligations and missing facts before changing the "
                        "proof state."
                    ),
                }),
                direct_context_request({
                    "intent": "tactic_forms",
                    "payload": {"name": "call"},
                    "why": "Shows the valid EasyCrypt forms for `call`.",
                }),
            ],
            "limitations": [_instantiation_limitation(action)],
        }
    if kind == "rnd_coupling":
        return {
            "runnable_status": (
                "Not yet; replace the placeholder coupling or offset with "
                "concrete EasyCrypt expressions before submitting "
                "this tactic."
            ),
            "missing_input": [
                "Concrete coupling function, offset, or inverse mapping for the sampled values.",
                "Any side conditions needed to show the mapping preserves the sampled distributions.",
            ],
            "how_to_complete": [
                (
                    "Compare the visible sampling statements with the "
                    "postcondition relation; choose the mapping that turns the "
                    "left sample into the right sample."
                ),
                (
                    "Use current variables, loop invariants, and support bounds "
                    "from the goal to justify the sampled values stay in range."
                ),
            ],
            "inspect_if_unsure": [
                direct_context_request({
                    "intent": "align",
                    "payload": {},
                    "why": "Shows whether the LHS/RHS sampling statements are aligned.",
                }),
                direct_context_request({
                    "intent": "tactic_forms",
                    "payload": {"name": "rnd"},
                    "why": "Shows the valid EasyCrypt forms for coupling samples.",
                }),
            ],
            "limitations": [_instantiation_limitation(action)],
        }
    if kind == "splitwhile":
        return {
            "runnable_status": (
                "Not yet; fill the split condition, side, and loop position "
                "before submitting this tactic."
            ),
            "missing_input": [
                "Concrete split condition for the loop phase boundary.",
                "The side and loop occurrence to split, if they are not already concrete.",
            ],
            "how_to_complete": [
                (
                    "Use the visible loop condition, current pre/post relation, "
                    "and the phase boundary you want before choosing the split "
                    "condition."
                ),
                (
                    "The split should make the next invariant, `while`, `wp`, "
                    "or `rnd` step match the current program shape more directly."
                ),
            ],
            "inspect_if_unsure": [
                direct_context_request({
                    "intent": "align",
                    "payload": {},
                    "why": "Shows whether the two loops or loop phases are aligned.",
                }),
                direct_context_request({
                    "intent": "tactic_forms",
                    "payload": {"name": "while"},
                    "why": "Shows related EasyCrypt loop tactic forms and common traps.",
                }),
            ],
            "limitations": [_instantiation_limitation(action)],
        }
    if kind == "targeted_inline":
        return {
            "runnable_status": (
                "Not yet; replace the wrapper placeholder with a concrete "
                "procedure or occurrence from the current goal before submitting "
                "this tactic."
            ),
            "missing_input": [
                "Concrete wrapper/procedure name, and occurrence selector if needed.",
            ],
            "how_to_complete": [
                (
                    "Choose a wrapper that is visible in the current goal and "
                    "is blocking the next local `wp`, `seq`, or `call` step."
                ),
                (
                    "Prefer the smallest targeted inline that exposes the "
                    "needed frontier without hiding unrelated call handles."
                ),
            ],
            "inspect_if_unsure": [
                direct_context_request({
                    "intent": "call_site_options",
                    "payload": {},
                    "why": (
                        "Shows whether a live call handle should be used before "
                        "lowering wrappers."
                    ),
                }),
            ],
            "limitations": [_instantiation_limitation(action)],
        }
    if kind == "lemma_or_call_args":
        return {
            "runnable_status": (
                "Not yet; fill the missing EasyCrypt lemma, module, procedure, "
                "or term arguments before submitting this tactic."
            ),
            "missing_input": [
                "Concrete arguments required by the lemma or call form.",
            ],
            "how_to_complete": [
                (
                    "Match the lemma or call statement against the visible "
                    "call sites, module parameters, globals, and hypotheses in "
                    "the current goal."
                ),
                (
                    "If the arity or argument order is unclear, inspect the "
                    "tactic form or lookup the symbol before guessing."
                ),
            ],
            "inspect_if_unsure": [
                direct_context_request({
                    "intent": "call_site_options",
                    "payload": {},
                    "why": "Shows call-site context and named call handles for this frontier.",
                }),
                direct_context_request({
                    "intent": "tactic_forms",
                    "payload": {"name": "call"},
                    "why": "Shows the valid EasyCrypt forms for `call`.",
                }),
                direct_context_request({
                    "intent": "lookup_symbol",
                    "payload": {"symbol": "<lemma or symbol name>"},
                    "why": "Shows the declaration/signature when a concrete symbol is known.",
                }),
            ],
            "limitations": [_instantiation_limitation(action)],
        }
    return {
        "runnable_status": (
            "Not yet; replace every placeholder with concrete EasyCrypt terms "
            "from the current goal before submitting this tactic."
        ),
        "missing_input": [
            "Concrete EasyCrypt arguments for every placeholder in the displayed tactic.",
        ],
        "how_to_complete": [
            (
                "Use the current goal variables, hypotheses, precondition, "
                "postcondition, and visible program statements to fill the "
                "placeholders."
            ),
        ],
        "inspect_if_unsure": [
            direct_context_request({
                "intent": "tactic_forms",
                "payload": {"name": _tactic_head(action) or "<tactic>"},
                "why": "Shows valid argument forms when this tactic has several shapes.",
            }),
        ],
        "limitations": [_instantiation_limitation(action)],
    }


def _instantiation_kind(action: dict[str, Any]) -> str:
    family = _action_family(action)
    text = " ".join(
        str(value or "")
        for value in (
            action.get("tactic"),
            action.get("tactic_shape"),
            action.get("guidance"),
            action.get("why"),
        )
    ).strip()
    lowered = text.lower()
    if family == "call_invariant_skeleton" or "call (_:" in lowered:
        return "call_invariant"
    if family == "sampling_coupling" or lowered.startswith("rnd ") or " rnd " in lowered:
        return "rnd_coupling"
    if family == "splitwhile" or "splitwhile" in lowered:
        return "splitwhile"
    if (
        family == "targeted_inline"
        or "<local wrapper>" in lowered
        or (lowered.startswith("inline ") and "<" in lowered)
    ):
        return "targeted_inline"
    if family == "call_named_equiv" or lowered.startswith("call "):
        return "lemma_or_call_args"
    return "generic"


def _tactic_head(action: dict[str, Any]) -> str:
    text = str(
        action.get("tactic")
        or action.get("tactic_shape")
        or action.get("guidance")
        or ""
    ).strip()
    if not text:
        return ""
    head = text.split(None, 1)[0].strip().strip(".;")
    return head


def _action_family(action: dict[str, Any]) -> str:
    metadata = _dict(action.get("metadata"))
    return str(
        metadata.get("proof_ir_tactic_family")
        or action.get("proof_ir_tactic_family")
        or ""
    ).strip()


def _bare_enum_leaks(value: Any, path: str = "") -> list[str]:
    issues: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            issues.extend(_bare_enum_leaks(item, child_path))
        return issues
    if isinstance(value, list):
        for idx, item in enumerate(value):
            issues.extend(_bare_enum_leaks(item, f"{path}[{idx}]"))
        return issues
    if not isinstance(value, str):
        return issues
    if _skip_enum_lint_path(path):
        return issues
    stripped = value.strip()
    if stripped in AGENT_FORBIDDEN_BARE_ENUM_VALUES:
        issues.append(f"unreviewed enum-like value in agent view: {path} = {stripped!r}")
    return issues


def _low_level_inspect_topic_leaks(value: Any, path: str = "") -> list[str]:
    issues: list[str] = []
    if isinstance(value, dict):
        payload = value.get("payload")
        if isinstance(payload, dict) and "topic" in payload:
            raw = str(payload.get("topic") or "").strip()
            normalized = raw.lstrip("-").replace("-", "_")
            if normalized in _LOW_LEVEL_INSPECT_TOPICS:
                topic_path = f"{path}.payload.topic" if path else "payload.topic"
                issues.append(
                    f"low-level inspect topic leaked into agent view: "
                    f"{topic_path} = {raw!r}"
                )
        for key, item in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            issues.extend(_low_level_inspect_topic_leaks(item, child_path))
        return issues
    if isinstance(value, list):
        for idx, item in enumerate(value):
            issues.extend(_low_level_inspect_topic_leaks(item, f"{path}[{idx}]"))
    return issues


def _skip_enum_lint_path(path: str) -> bool:
    # These fields intentionally carry EasyCrypt/user protocol syntax.  The
    # display layer should not treat tactic text or manager payload selectors
    # as prose to be rewritten.
    syntax_fields = (
        ".tactic",
        ".tactic_shape",
        ".candidate",
        ".lines[",
        ".payload.",
        ".source.",
        ".path",
        ".artifact",
    )
    return any(token in path for token in syntax_fields)


def _semantic_intent(handle: str) -> str:
    normalized = str(handle or "").strip().lstrip("-").replace("-", "_")
    mapped = {
        "where": "lookup_symbol",
        "signature": "lookup_symbol",
        "sig": "lookup_symbol",
        "members": "lookup_symbol",
        "check_lemma": "lookup_symbol",
        "search": "rewrite_candidates",
        "search_skeleton": "rewrite_candidates",
        "native_ast_search": "rewrite_candidates",
    }.get(normalized, normalize_context_topic(normalized, default=""))
    if mapped == "lookup_symbol" or mapped in CONTEXT_TOPIC_INTENTS:
        return mapped
    return ""


def _dedupe(values: tuple[str, ...]) -> tuple[str, ...]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return tuple(out)
