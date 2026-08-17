"""Agent protocol repair observations."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from core.easycrypt.proof_lifecycle import (
    allows_qed,
    requires_qed_before_finish,
)

from core.context_intents import (
    PROTOCOL_INTENTS,
    canonicalize_intent_payload,
    intent_payload_contract_error,
)
from workflow.managed_turn_outcome import classify_manager_action_outcome
from workflow.proof_management.tactic_utils import strip_easycrypt_comments
from core.easycrypt.value_shapes import as_dict_copy as _dict
from core.easycrypt.value_shapes import drop_empty as _drop_empty


AgentIntentName = str

ALLOWED_AGENT_INTENTS: set[str] = set(PROTOCOL_INTENTS)

REPAIR_PROMPT = (
    "I could not read a proof intent from the last message. Please reply with "
    "exactly one JSON object like:\n"
    '{"intent": "commit_tactic", "payload": {"tactic": "..."}}'
)

def repair_prompt_text() -> str:
    """The protocol-repair example shown to the agent on an unreadable intent."""
    return REPAIR_PROMPT


def repair_prompt_text_for_streak(malformed_count: int) -> str:
    """Repair example, escalated for a *streak* of malformed intents.

    A single unreadable message gets the plain `repair_prompt_text()` example. On
    a streak (two or more consecutive malformed intents) the node is NOT bricked
    — it stays live and re-issues the workspace view — so the corrective nudge is
    made more emphatic to break the loop: the agent's previous reply(ies) carried
    no valid intent and the manager did nothing, so the proof has not advanced.
    The escalated text leads with that explicit no-op framing and then repeats the
    canonical one-JSON-object example."""
    base = repair_prompt_text()
    if malformed_count <= 1:
        return base
    return (
        f"Your last {malformed_count} replies contained no valid proof intent, "
        "so the manager did nothing and the proof state is unchanged. This is a "
        "recoverable no-op, not a failure — read the current goal again and reply "
        "with exactly ONE JSON intent object (no prose, no extra fields):\n\n"
        f"{base}"
    )

ADMIT_CLARIFICATION_PROMPT = (
    "You attempted to use `admit.`. The manager did not execute it, and the "
    "committed EasyCrypt proof state is unchanged.\n\n"
    "Clarify the purpose by choosing the next proof intent:\n"
    "- If this was accidental, continue with a real non-admit proof tactic.\n"
    "- If you wanted to explore later goals, commit a real structural tactic "
    "and undo it if it does not fit.\n"
    "- If you are stuck, report the blocker in your final PROVER REPORT or "
    "try a different proof route.\n\n"
    "`admit.` is not a proof step for the current target lemma and will not "
    "be committed."
)

QED_CLARIFICATION_PROMPT = (
    "You attempted to commit `qed.`, but the latest authoritative session "
    "state is not `goals_discharged_pending_qed`. The manager "
    "did not execute it, and the committed EasyCrypt proof state is unchanged.\n\n"
    "Read `current_goal.lines` and `proof_status`. Submit `qed.` only when "
    "`proof_status.status` is exactly `goals_discharged_pending_qed`. "
    "Otherwise continue with a real proof tactic."
)

FINISH_REQUIRES_QED_PROMPT = (
    "The current view shows that all EasyCrypt goals are closed, but the lemma "
    "has not been saved with `qed.` yet. The manager did not finish this node "
    "and did not change the committed proof state.\n\n"
    "Submit exactly this proof intent next:\n"
    '{"intent": "commit_tactic", "payload": {"tactic": "qed."}}\n\n'
    "After `qed.` is accepted and the refreshed view shows "
    "`session_closed_pending_verification` or `verified`, you may finish."
)

@dataclass(frozen=True)
class AgentIntent:
    """One canonical semantic intent decoded from the agent transport."""

    intent: str
    payload: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        canonical_payload = canonicalize_intent_payload(self.payload)
        object.__setattr__(self, "intent", str(self.intent).strip())
        object.__setattr__(self, "payload", canonical_payload)

    def to_dict(self) -> dict[str, Any]:
        return {"intent": self.intent, "payload": dict(self.payload)}


@dataclass(frozen=True)
class AgentIntentParse:
    ok: bool
    intent: AgentIntent | None = None
    error: str = ""
    repair_prompt: str = field(default_factory=repair_prompt_text)


def parse_agent_intent(text: str) -> AgentIntentParse:
    raw = text.strip() if type(text) is str else ""
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        return AgentIntentParse(
            ok=False,
            error="expected_exactly_one_json_object",
        )
    if type(obj) is not dict:
        return AgentIntentParse(
            ok=False,
            error="expected_exactly_one_json_object",
        )
    unexpected_top_level = sorted(set(obj) - {"intent", "payload"})
    if unexpected_top_level:
        return AgentIntentParse(ok=False, error="unexpected_top_level_fields")
    raw_intent = obj.get("intent")
    intent = raw_intent.strip() if type(raw_intent) is str else ""
    if intent not in ALLOWED_AGENT_INTENTS:
        return AgentIntentParse(ok=False, error="unknown_or_missing_intent")
    payload = obj.get("payload")
    if not isinstance(payload, dict):
        return AgentIntentParse(ok=False, error="payload_must_be_object")
    payload_error = _intent_payload_error(intent, payload)
    if payload_error:
        return AgentIntentParse(ok=False, error=payload_error)
    return AgentIntentParse(ok=True, intent=AgentIntent(intent=intent, payload=payload))


def _intent_payload_error(intent: str, payload: dict[str, Any]) -> str:
    """Return the strict live-protocol payload error, or ``""`` when valid."""

    field_error = intent_payload_contract_error(
        intent,
        payload,
        require_required_fields=False,
    )
    if field_error:
        return field_error

    if intent == "undo_to_checkpoint":
        return _undo_to_checkpoint_payload_error(payload)
    if intent == "fresh_restart":
        if not payload:
            return ""
        if set(payload) != {"confirm", "confirmation_id"}:
            return "invalid_fresh_restart_payload"
        if payload["confirm"] is not True:
            return "invalid_fresh_restart_payload"
        return ""
    if intent == "amend_and_replay" and not payload:
        return ""

    return intent_payload_contract_error(intent, payload)


def _undo_to_checkpoint_payload_error(payload: dict[str, Any]) -> str:
    if not payload:
        return ""
    keys = set(payload)
    if "restore_id" in keys:
        return "" if keys == {"restore_id"} else "invalid_undo_to_checkpoint_payload"
    if "checkpoint_id" not in keys:
        return "invalid_undo_to_checkpoint_payload"
    confirmation = {"confirm", "confirmation_id"}
    extras = keys - {"checkpoint_id"} - confirmation
    if extras:
        return "invalid_undo_to_checkpoint_payload"
    if keys & confirmation and not confirmation <= keys:
        return "invalid_undo_to_checkpoint_payload"
    if confirmation <= keys and payload["confirm"] is not True:
        return "invalid_undo_to_checkpoint_payload"
    return ""



def intent_is_standalone_qed(intent: str, payload: dict[str, Any]) -> bool:
    if intent != "commit_tactic":
        return False
    tactic = strip_easycrypt_comments(
        str(_dict(payload).get("tactic") or "")
    ).strip()
    return tactic.lower().rstrip(".").strip() == "qed"


def view_allows_qed(view: dict[str, Any]) -> bool:
    if not isinstance(view, dict):
        return False
    proof_status = _dict(view.get("proof_status"))
    status = _first_text(proof_status.get("status"), default="").lower()
    return allows_qed(status)


def view_requires_qed_before_finish(view: dict[str, Any]) -> bool:
    if not isinstance(view, dict):
        return False
    proof_status = _dict(view.get("proof_status"))
    status = _first_text(proof_status.get("status"), default="").lower()
    return requires_qed_before_finish(status)



def qed_clarification_action(payload: dict[str, Any]) -> dict[str, Any]:
    tactic = str(_dict(payload).get("tactic") or "").strip()
    outcome = classify_manager_action_outcome(
        status="clarification_requested",
        ok=False,
        read_only=False,
        mutates_proof_state=False,
        state_changed=False,
        repair_requested=True,
    ).to_dict()
    return {
        "label": "qed_clarification",
        "exit_code": 0,
        "duration_ms": 0,
        "mutates_proof_state": False,
        **outcome,
        "agent_observation": _drop_empty({
            "manager_action": "qed_clarification",
            "status": "clarification_requested",
            "result": (
                "The manager did not execute `qed.` because the latest view "
                "does not show a closed proof candidate."
            ),
            "effect": (
                "No EasyCrypt command was run. Read the current goal and "
                "continue proving."
            ),
            "proof_state": "The committed EasyCrypt proof state was not changed.",
            "tactic": tactic,
            "guidance": [
                (
                    "Submit `qed.` only after the current view shows no "
                    "remaining goals."
                ),
                (
                    "If the state looks closed but the view does not say so, "
                    "do not retry `qed.` blindly; the manager must refresh its "
                    "event-bound goal state."
                ),
            ],
        }),
        "stdout_has_workspace_view": False,
    }


def backend_failure_repair_prompt(action: dict[str, Any]) -> str:
    label = str(action.get("label") or "manager request")
    mutating = bool(action.get("mutates_proof_state"))
    observation = action.get("agent_observation")
    error_summary = ""
    if isinstance(observation, dict):
        error_summary = str(observation.get("error_summary") or "").strip()
    proof_state = (
        "The manager returned the last completed managed goal. Because "
        "the failed backend action could have been mutating, treat the node as "
        "unhealthy if the manager health event says so."
        if mutating
        else (
            "This was a read-only manager request, so the committed EasyCrypt "
            "proof state was not changed."
        )
    )
    detail = f"\n\nBackend error summary: {error_summary}" if error_summary else ""
    return (
        f"The manager could not complete `{label}`. {proof_state} Use the "
        "latest current view and choose a repair proof intent or stop with a "
        "concise PROVER REPORT if this blocks "
        f"the proof.{detail}"
    )



def _first_text(*values: Any, default: str = "") -> str:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return default
