"""Single owner for proof-intent decoding, admission, and repair state."""
from __future__ import annotations

import json
import os
import re
import time
from collections.abc import Callable, Collection, Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

from .checkpoint_surface import checkpoint_id, history_hash
from .protocol_repair import (
    FINISH_REQUIRES_QED_PROMPT,
    QED_CLARIFICATION_PROMPT,
    AgentIntent,
    AgentIntentParse,
    intent_is_standalone_qed,
    parse_agent_intent,
    qed_clarification_action,
    repair_prompt_text_for_streak,
    view_allows_qed,
    view_requires_qed_before_finish,
)
from .turn_view import (
    intent_payload_surface,
    latest_observation_for_view,
    selection_menu_action,
)
from .types import ManagedTurn, NodeHealthEvent, ProofStateSnapshot, TurnDirective


DEFAULT_GIVE_UP_WINDOW_S = float(
    os.environ.get("SHANNON_GIVE_UP_WINDOW_S", str(2 * 60 * 60))
)
DEFAULT_GIVE_UP_ALLOW_AFTER = max(
    1,
    int(os.environ.get("SHANNON_GIVE_UP_ALLOW_AFTER", "2")),
)
_ADMIT_RE = re.compile(
    r"(?<![A-Za-z0-9_])admit(?:\s*\.|\s*;|\s*$)",
    re.IGNORECASE,
)


PreflightKind = Literal["none", "action_repair", "menu"]


@dataclass(frozen=True)
class IntentPreflightDecision:
    kind: PreflightKind = "none"
    ok: bool = True
    actions: list[dict[str, Any]] = field(default_factory=list)
    observation: dict[str, Any] = field(default_factory=dict)
    repair_prompt: str = ""
    label: str = ""
    audit_kind: str = ""
    audit_extra: dict[str, Any] = field(default_factory=dict)

    @property
    def should_handle(self) -> bool:
        return self.kind != "none"


@dataclass(frozen=True)
class IntentAdmission:
    """One decoded intent or an admission-owned terminal decision."""

    intent: AgentIntent | None = None
    turn: ManagedTurn | None = None
    preflight: IntentPreflightDecision = field(
        default_factory=IntentPreflightDecision
    )

    @property
    def admitted(self) -> bool:
        return self.intent is not None and self.turn is None and not self.preflight.should_handle


class IntentAdmissionController:
    """Own all mutable protocol/admission state for one proof node."""

    def __init__(
        self,
        *,
        node_id: str,
        surface_profile: str | None,
        effective_profile_intents: Collection[str],
        events: Any,
        state_version: Callable[[], int],
        committed_history: Callable[[], list[str]],
        audit: Callable[[dict[str, Any]], None],
        give_up_window_s: float = DEFAULT_GIVE_UP_WINDOW_S,
        give_up_allow_after: int = DEFAULT_GIVE_UP_ALLOW_AFTER,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.node_id = node_id
        self.surface_profile = surface_profile
        self.effective_profile_intents = frozenset(effective_profile_intents)
        self.events = events
        self._state_version = state_version
        self._committed_history = committed_history
        self._audit = audit
        self.give_up_window_s = float(give_up_window_s)
        self.give_up_allow_after = max(1, int(give_up_allow_after))
        self._clock = clock
        self.malformed_count = 0
        self._rejection_goal_hash = ""
        self._current_goal_rejections: list[dict[str, Any]] = []
        self._give_up_times: list[float] = []

    def admit_text(
        self,
        text: str,
        *,
        latest_view: dict[str, Any],
        latest_snapshot: ProofStateSnapshot | None,
        deadline: float | None = None,
    ) -> IntentAdmission:
        return self._admit_parse(
            parse_agent_intent(text),
            latest_view=latest_view,
            latest_snapshot=latest_snapshot,
            deadline=deadline,
            raw_text=str(text or ""),
        )

    def admit_tool_arguments(
        self,
        raw_arguments: Any,
        *,
        latest_view: dict[str, Any],
        latest_snapshot: ProofStateSnapshot | None,
        deadline: float | None = None,
    ) -> IntentAdmission:
        """Decode raw MCP arguments through the same canonical parser.

        The transport schema is intentionally permissive.  This method, not
        the MCP adapter, owns all semantic shape and payload validation.
        """

        encoded = ""
        if not isinstance(raw_arguments, Mapping):
            encoded = repr(raw_arguments)
            parsed = AgentIntentParse(
                ok=False,
                error="expected_exactly_one_json_object",
            )
        else:
            try:
                encoded = json.dumps(
                    dict(raw_arguments),
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
            except (TypeError, ValueError):
                encoded = repr(raw_arguments)
                parsed = AgentIntentParse(
                    ok=False,
                    error="expected_exactly_one_json_object",
                )
            else:
                parsed = parse_agent_intent(encoded)
        return self._admit_parse(
            parsed,
            latest_view=latest_view,
            latest_snapshot=latest_snapshot,
            deadline=deadline,
            raw_text=encoded,
        )

    def admit_intent(
        self,
        intent: AgentIntent,
        *,
        latest_view: dict[str, Any],
        latest_snapshot: ProofStateSnapshot | None,
        deadline: float | None = None,
        record_received: bool = False,
    ) -> IntentAdmission:
        """Admit an already-canonical intent; useful for deterministic tests."""

        if self._deadline_expired(deadline):
            return IntentAdmission(
                turn=self.deadline_exceeded_turn(
                    latest_view=latest_view,
                    latest_snapshot=latest_snapshot,
                )
            )
        self.malformed_count = 0
        if record_received:
            self.events.record_intent_received(
                intent=intent.intent,
                payload=intent.payload,
                state_version=self._state_version(),
            )
        blocked = self._committed_admit_gate(
            intent,
            latest_view=latest_view,
            latest_snapshot=latest_snapshot,
        )
        if blocked is not None:
            return IntentAdmission(intent=intent, turn=blocked)
        blocked = self._exact_rejection_gate(
            intent,
            latest_view=latest_view,
            latest_snapshot=latest_snapshot,
        )
        if blocked is not None:
            return IntentAdmission(intent=intent, turn=blocked)
        give_up = self._give_up_preflight(intent, latest_view=latest_view)
        if give_up.should_handle:
            return IntentAdmission(intent=intent, preflight=give_up)
        preflight = self._protocol_preflight(intent, latest_view=latest_view)
        return IntentAdmission(intent=intent, preflight=preflight)

    def observe_projection(
        self,
        snapshot: ProofStateSnapshot,
        observation: dict[str, Any] | None,
    ) -> None:
        """Bind exact backend rejection memory to the canonical current goal."""

        goal_hash = str(snapshot.goal_hash or "")
        result = observation if isinstance(observation, dict) else {}
        effect = str(result.get("proof_state_effect") or "")
        if effect == "changed":
            self._rejection_goal_hash = goal_hash
            self._current_goal_rejections = []
            return
        if goal_hash != self._rejection_goal_hash:
            self._rejection_goal_hash = goal_hash
            self._current_goal_rejections = []
        if (
            effect != "unchanged"
            or str(result.get("outcome_kind") or "")
            not in {"rejected", "no_progress"}
        ):
            return
        intent = str(result.get("intent") or "").strip()
        payload = result.get("payload")
        if not intent or not isinstance(payload, dict) or not payload:
            return
        item = {
            "intent": intent,
            "payload": dict(payload),
            "outcome_kind": str(result.get("outcome_kind") or ""),
        }
        if not any(
            current.get("intent") == item["intent"]
            and current.get("payload") == item["payload"]
            for current in self._current_goal_rejections
        ):
            self._current_goal_rejections.append(item)

    def clear_goal_rejections(self) -> None:
        self._rejection_goal_hash = ""
        self._current_goal_rejections = []

    def committed_admit_records(
        self,
        tactics: list[str] | tuple[str, ...] | None = None,
    ) -> list[dict[str, Any]]:
        """Project admit debt from session-owned history without reading files."""

        if tactics is None:
            tactics = self._committed_history()
        clean = [str(item or "") for item in tactics]
        digest = history_hash(clean) if clean else ""
        records: list[dict[str, Any]] = []
        for index, tactic in enumerate(clean):
            if not _tactic_has_admit(tactic):
                continue
            step = index + 1
            label = _short_tactic(tactic)
            record: dict[str, Any] = {
                "kind": "committed_admit",
                "step": step,
                "tactic": label,
                "gate_label": f"committed admit (step {step}): {label}",
            }
            if index > 0:
                record["parked_after"] = (
                    f"step {index}: `{_short_tactic(clean[index - 1])}`"
                )
            if digest:
                cid = checkpoint_id(digest, step)
                record["rewind_checkpoint"] = {
                    "checkpoint_id": cid,
                    "committed_step_index": step,
                    "label": f"Just before this admit (committed tactic #{step})",
                    "effect_if_selected": (
                        f"Undo committed tactic #{step} (the admit) and every "
                        "committed tactic after it in this node."
                    ),
                    "submit": {
                        "intent": "undo_to_checkpoint",
                        "payload": {"checkpoint_id": cid},
                    },
                }
            records.append(record)
        return records

    def deadline_exceeded_turn(
        self,
        *,
        latest_view: dict[str, Any],
        latest_snapshot: ProofStateSnapshot | None,
    ) -> ManagedTurn:
        health = NodeHealthEvent(
            node_id=self.node_id,
            status="manager_turn_deadline_exceeded",
            message=(
                "the shared proof-tool turn deadline expired; the node is "
                "fail-closed and will not accept another proof intent"
            ),
            state_version=self._state_version(),
        )
        self._audit({
            "kind": "manager_turn.deadline_exceeded",
            "node": self.node_id,
            "health": health.to_dict(),
        })
        return ManagedTurn(
            ok=False,
            workspace_view=dict(latest_view),
            snapshot=latest_snapshot,
            health_event=health,
            directive=TurnDirective.NODE_UNHEALTHY,
        )

    def deadline_expired(self, deadline: float | None) -> bool:
        """Return whether the shared absolute turn deadline has elapsed."""

        return self._deadline_expired(deadline)

    def _admit_parse(
        self,
        parsed: AgentIntentParse,
        *,
        latest_view: dict[str, Any],
        latest_snapshot: ProofStateSnapshot | None,
        deadline: float | None,
        raw_text: str = "",
    ) -> IntentAdmission:
        if self._deadline_expired(deadline):
            return IntentAdmission(
                turn=self.deadline_exceeded_turn(
                    latest_view=latest_view,
                    latest_snapshot=latest_snapshot,
                )
            )
        if not parsed.ok or parsed.intent is None:
            self.malformed_count += 1
            self.events.record_malformed_intent(
                error=parsed.error,
                malformed_count=self.malformed_count,
                state_version=self._state_version(),
            )
            self._audit({
                "kind": "agent_intent.malformed",
                "node": self.node_id,
                "error": parsed.error,
                "malformed_count": self.malformed_count,
                "recoverable": True,
                # What actually arrived (bounded). A live run once burned a
                # full 30-minute window on payload_must_be_object x5 with no
                # way to see the argument shape post-mortem.
                "raw": raw_text[:500],
            })
            return IntentAdmission(turn=ManagedTurn(
                ok=False,
                workspace_view=dict(latest_view),
                snapshot=latest_snapshot,
                repair_prompt=repair_prompt_text_for_streak(
                    self.malformed_count
                ),
            ))
        return self.admit_intent(
            parsed.intent,
            latest_view=latest_view,
            latest_snapshot=latest_snapshot,
            deadline=deadline,
            record_received=True,
        )

    def _committed_admit_gate(
        self,
        intent: AgentIntent,
        *,
        latest_view: dict[str, Any],
        latest_snapshot: ProofStateSnapshot | None,
    ) -> ManagedTurn | None:
        if not (
            intent.intent == "finish"
            or intent_is_standalone_qed(intent.intent, intent.payload)
        ):
            return None
        debt = [
            item["gate_label"]
            for item in self.committed_admit_records()
        ]
        if not debt:
            return None
        shown = ", ".join(debt[:6]) + ("…" if len(debt) > 6 else "")
        prompt = (
            f"The proof still has {len(debt)} un-discharged `admit.` "
            f"tactic(s): {shown}. An `admit`-ed subgoal is set aside, not "
            "proved — the lemma is not complete until each admit is replaced "
            "with a real proof. Undo the admit and prove that subgoal before "
            "qed/finish."
        )
        return ManagedTurn(
            ok=False,
            workspace_view=dict(latest_view),
            snapshot=latest_snapshot,
            intent=intent,
            repair_prompt=prompt,
            manager_actions=[{
                "label": "committed_admit_gate",
                "admits": debt,
            }],
        )

    def _exact_rejection_gate(
        self,
        intent: AgentIntent,
        *,
        latest_view: dict[str, Any],
        latest_snapshot: ProofStateSnapshot | None,
    ) -> ManagedTurn | None:
        goal_hash = str(getattr(latest_snapshot, "goal_hash", "") or "")
        if not goal_hash or goal_hash != self._rejection_goal_hash:
            return None
        match = next((
            item
            for item in self._current_goal_rejections
            if item.get("intent") == intent.intent
            and item.get("payload") == intent.payload
        ), None)
        if match is None:
            return None
        self._audit({
            "kind": "proof_intent.exact_rejection_suppressed",
            "node": self.node_id,
            "intent": intent.intent,
            "payload": dict(intent.payload),
            "goal_hash": goal_hash,
        })
        return ManagedTurn(
            ok=False,
            workspace_view=dict(latest_view),
            snapshot=latest_snapshot,
            intent=intent,
            repair_prompt=(
                "EasyCrypt already rejected this exact intent and payload "
                "without changing the current goal. Change the tactic or "
                "inspect current evidence before retrying."
            ),
            manager_actions=[{
                "label": "exact_rejection_memory",
                "mutates_proof_state": False,
                "outcome_kind": str(match.get("outcome_kind") or "rejected"),
            }],
        )

    def _give_up_preflight(
        self,
        intent: AgentIntent,
        *,
        latest_view: dict[str, Any],
    ) -> IntentPreflightDecision:
        if intent.intent != "finish":
            return IntentPreflightDecision()
        proof_status = (
            latest_view.get("proof_status")
            if isinstance(latest_view.get("proof_status"), dict)
            else {}
        )
        status = str(proof_status.get("status") or "")
        remaining = proof_status.get("remaining_goals")
        if not (status == "open" and remaining != 0):
            return IntentPreflightDecision()
        now = self._clock()
        self._give_up_times = [
            when
            for when in self._give_up_times
            if now - when < self.give_up_window_s
        ]
        self._give_up_times.append(now)
        attempts = len(self._give_up_times)
        if attempts >= self.give_up_allow_after:
            self._audit({
                "kind": "give_up.allowed",
                "node": self.node_id,
                "attempts_in_window": attempts,
                "remaining_goals": remaining,
            })
            return IntentPreflightDecision()
        goals = (
            f"{remaining} goal(s) still open"
            if isinstance(remaining, int)
            else "the proof still open"
        )
        prompt = (
            f"You submitted `finish` with {goals}. That is your call — if you "
            "have already considered the alternatives and are genuinely "
            "blocked, finishing is fine; just record the concrete obstacle in "
            "PROVER REPORT.blockers so it is captured. If you have not tried "
            "a different angle yet, one more turn is often worth it: a "
            "different tactic, undo a wrong step, or reconsider the current "
            "goal. To stop now, just submit `finish` again."
        )
        return IntentPreflightDecision(
            kind="menu",
            ok=False,
            label="give_up_gate",
            observation={
                "intent": "finish",
                "kind": "give_up_gate",
                "control_menu": {
                    "title": "Finish while proof is open",
                    "notice": prompt,
                    "items": [{
                        "label": "Finish anyway",
                        "description": (
                            "Stop this proof node with goals still open."
                        ),
                        "submit": {"intent": "finish", "payload": {}},
                    }],
                },
            },
            audit_kind="give_up.deflected",
            audit_extra={
                "attempts_in_window": attempts,
                "allow_after": self.give_up_allow_after,
                "remaining_goals": remaining,
            },
        )

    def _protocol_preflight(
        self,
        intent: AgentIntent,
        *,
        latest_view: dict[str, Any],
    ) -> IntentPreflightDecision:
        if (
            intent_is_standalone_qed(intent.intent, intent.payload)
            and not view_allows_qed(latest_view)
        ):
            actions = [qed_clarification_action(intent.payload)]
            return IntentPreflightDecision(
                kind="action_repair",
                ok=False,
                actions=actions,
                observation=latest_observation_for_view(intent, actions),
                repair_prompt=QED_CLARIFICATION_PROMPT,
                audit_kind="agent_intent.qed_clarification",
            )
        if intent.intent not in self.effective_profile_intents:
            reason = (
                f"Surface profile `{self.surface_profile}` exposes only the "
                "matched proof-control protocol; intent "
                f"`{intent.intent}` is unavailable."
            )
            actions = [selection_menu_action(
                "surface_profile_hidden_intent",
                {
                    "intent": intent.intent,
                    "payload": intent_payload_surface(intent),
                    "message": reason,
                },
            )]
            return IntentPreflightDecision(
                kind="action_repair",
                ok=False,
                actions=actions,
                observation=latest_observation_for_view(intent, actions),
                repair_prompt=reason,
                audit_kind="agent_intent.blocked_by_surface_profile",
                audit_extra={"reason": reason},
            )
        if (
            intent.intent == "finish"
            and view_requires_qed_before_finish(latest_view)
        ):
            return IntentPreflightDecision(
                kind="menu",
                ok=False,
                label="finish_requires_qed",
                observation={
                    "intent": "finish",
                    "kind": "finish_requires_qed",
                    "control_menu": {
                        "title": "Finish unavailable",
                        "notice": FINISH_REQUIRES_QED_PROMPT,
                        "items": [{
                            "label": "Commit qed.",
                            "description": "Save the closed proof candidate.",
                            "submit": {
                                "intent": "commit_tactic",
                                "payload": {"tactic": "qed."},
                            },
                        }],
                    },
                },
                audit_kind="agent_intent.finish_requires_qed",
            )
        return IntentPreflightDecision()

    def _deadline_expired(self, deadline: float | None) -> bool:
        return deadline is not None and self._clock() >= float(deadline)


def _tactic_has_admit(tactic: str) -> bool:
    return bool(_ADMIT_RE.search(str(tactic or "")))


def _short_tactic(tactic: str) -> str:
    flattened = " ".join(str(tactic or "").split())
    return flattened if len(flattened) <= 60 else flattened[:59] + "…"
