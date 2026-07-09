"""Agent protocol repair observations."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from workflow.surface_profiles import probe_disabled
from workflow.context_intents import PROTOCOL_INTENTS
from workflow.proof_management.transitions import strip_easycrypt_comments
from core.easycrypt.value_shapes import as_dict_copy as _dict
from core.easycrypt.value_shapes import drop_empty as _drop_empty


AgentIntentName = str

ALLOWED_AGENT_INTENTS: set[str] = set(PROTOCOL_INTENTS)

REPAIR_PROMPT = (
    "I could not read a proof intent from the last message. Please reply with "
    "exactly one JSON object like:\n"
    '{"intent": "probe_tactic", "payload": {"tactic": "..."}}\n'
    "or\n"
    '{"intent": "tactic_forms", "payload": {"name": "wp"}}'
)

# Probe is hidden from the default agent-facing surface. When unavailable the
# manager rejects stale/manual probe intents, so repair examples must not advertise
# a `probe_tactic` affordance. Lead with the always-available `commit_tactic`
# example instead. Mirrors the gating in `workflow.surface_profiles` for the
# view/schema/prompt.
_REPAIR_PROMPT_PROBE_OFF = (
    "I could not read a proof intent from the last message. Please reply with "
    "exactly one JSON object like:\n"
    '{"intent": "commit_tactic", "payload": {"tactic": "..."}}\n'
    "or\n"
    '{"intent": "tactic_forms", "payload": {"name": "wp"}}'
)


def repair_prompt_text() -> str:
    """The protocol-repair example shown to the agent on an unreadable intent.

    Switch-aware: when the probe lever is unavailable, the
    example advertises `commit_tactic` instead of `probe_tactic`, so the recovery
    message never offers an affordance the manager will reject. Computed at call
    time because the env switch is a per-run setting."""
    return _REPAIR_PROMPT_PROBE_OFF if probe_disabled() else REPAIR_PROMPT


def repair_prompt_text_for_streak(malformed_count: int) -> str:
    """Repair example, escalated for a *streak* of malformed intents.

    A single unreadable message gets the plain `repair_prompt_text()` example. On
    a streak (two or more consecutive malformed intents) the node is NOT bricked
    — it stays live and re-issues the workspace view — so the corrective nudge is
    made more emphatic to break the loop: the agent's previous reply(ies) carried
    no valid intent and the manager did nothing, so the proof has not advanced.
    The escalated text leads with that explicit no-op framing and then repeats the
    canonical one-JSON-object example (still probe-switch aware)."""
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
    "- If you wanted to peek at later goals, use manager inspection such as "
    "`subgoal_gap` or `call_subgoals`, or probe a non-admit "
    "structural tactic.\n"
    "- If you are stuck, report the blocker in your final PROVER REPORT or "
    "try a different proof route.\n\n"
    "`admit.` is not a proof step for the current target lemma and will not "
    "be committed."
)

QED_CLARIFICATION_PROMPT = (
    "You attempted to commit `qed.`, but the latest authoritative "
    "ProverWorkspaceView does not show a closed proof candidate. The manager "
    "did not execute it, and the committed EasyCrypt proof state is unchanged.\n\n"
    "Read `current_goal.lines`, `proof_status`, and `candidate_moves` in the "
    "latest view. Submit `qed.` only after the view explicitly shows no "
    "remaining goals, `candidate_closed`, `candidate_closed_pending_qed`, or a "
    "`qed.` candidate move. Otherwise continue with a real proof tactic or ask "
    "for `diagnose`."
)

FINISH_REQUIRES_QED_PROMPT = (
    "The current view shows that all EasyCrypt goals are closed, but the lemma "
    "has not been saved with `qed.` yet. The manager did not finish this node "
    "and did not change the committed proof state.\n\n"
    "Submit exactly this proof intent next:\n"
    '{"intent": "commit_tactic", "payload": {"tactic": "qed."}}\n\n'
    "After `qed.` is accepted and the refreshed view shows `candidate_closed` "
    "or `verified`, you may finish."
)



@dataclass(frozen=True)
class AgentIntent:
    intent: str
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"intent": self.intent, "payload": dict(self.payload)}


@dataclass(frozen=True)
class AgentIntentParse:
    ok: bool
    intent: AgentIntent | None = None
    error: str = ""
    # Switch-aware default: computed per-instance so a no-probe run does not
    # advertise a `probe_tactic` example in the recovery message.
    repair_prompt: str = field(default_factory=repair_prompt_text)


def parse_agent_intent(text: str) -> AgentIntentParse:
    obj = _extract_json_object(text)
    if not isinstance(obj, dict):
        return AgentIntentParse(ok=False, error="missing_json_object")
    intent = str(obj.get("intent") or "").strip()
    if intent not in ALLOWED_AGENT_INTENTS:
        return AgentIntentParse(ok=False, error="unknown_or_missing_intent")
    payload = obj.get("payload")
    if payload is None:
        payload = {}
    if not isinstance(payload, dict):
        return AgentIntentParse(ok=False, error="payload_must_be_object")
    return AgentIntentParse(ok=True, intent=AgentIntent(intent=intent, payload=payload))



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
    proof_status = _dict(view.get("proof_status") or view.get("proof_position"))
    status = _first_text(proof_status.get("status"), default="").lower()
    if status in {
        "candidate_closed",
        "candidate_closed_pending_qed",
        "closed_candidate",
        "verified",
    }:
        return True
    current_goal = _dict(view.get("current_goal"))
    if current_goal.get("proof_candidate_closed"):
        return True
    lines = current_goal.get("lines")
    goal_text = "\n".join(str(line) for line in lines) if isinstance(lines, list) else ""
    if not goal_text:
        goal_text = _first_text(
            current_goal.get("active_goal_preview"),
            current_goal.get("active_goal_text"),
            default="",
        )
    if "No more goals" in goal_text:
        return True
    return _view_offers_qed_candidate(view)


def view_requires_qed_before_finish(view: dict[str, Any]) -> bool:
    if not isinstance(view, dict):
        return False
    proof_status = _dict(view.get("proof_status") or view.get("proof_position"))
    status = _first_text(proof_status.get("status"), default="").lower()
    if status in {"candidate_closed", "verified"}:
        return False
    if status == "candidate_closed_pending_qed":
        return True
    current_goal = _dict(view.get("current_goal"))
    lines = current_goal.get("lines")
    goal_text = "\n".join(str(line) for line in lines) if isinstance(lines, list) else ""
    if not goal_text:
        goal_text = _first_text(
            current_goal.get("active_goal_preview"),
            current_goal.get("active_goal_text"),
            default="",
        )
    if "No more goals" in goal_text:
        return True
    return _view_offers_qed_candidate(view)



def qed_clarification_action(payload: dict[str, Any]) -> dict[str, Any]:
    tactic = str(_dict(payload).get("tactic") or "").strip()
    return {
        "label": "qed_clarification",
        "exit_code": 0,
        "duration_ms": 0,
        "mutates_proof_state": False,
        "agent_observation": _drop_empty({
            "manager_action": "qed_clarification",
            "status": "clarification_requested",
            "result": (
                "The manager did not execute `qed.` because the latest view "
                "does not show a closed proof candidate."
            ),
            "effect": (
                "No EasyCrypt command was run. Read the current goal and "
                "continue proving, or ask the manager for semantic inspection."
            ),
            "proof_state": "The committed EasyCrypt proof state was not changed.",
            "tactic": tactic,
            "guidance": [
                (
                    "Submit `qed.` only after the current view shows no "
                    "remaining goals or offers `qed.` as a candidate move."
                ),
                (
                    "If the state looks closed but the view does not say so, "
                    "ask for `diagnose` before trying `qed.` again."
                ),
            ],
        }),
        "stdout_has_workspace_view": False,
    }


def finish_requires_qed_action() -> dict[str, Any]:
    return {
        "label": "finish_requires_qed",
        "exit_code": 0,
        "duration_ms": 0,
        "mutates_proof_state": False,
        "agent_observation": {
            "manager_action": "finish_requires_qed",
            "status": "repair_requested",
            "result": (
                "The manager did not finish because the current view still "
                "requires `qed.` to save the closed proof candidate."
            ),
            "effect": (
                "No EasyCrypt command was run. Submit `qed.` with "
                "`commit_tactic`; then finish only after the refreshed view "
                "shows the saved lemma."
            ),
            "proof_state": "The committed EasyCrypt proof state was not changed.",
            "next_intent": {
                "intent": "commit_tactic",
                "payload": {"tactic": "qed."},
            },
        },
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
        "The manager returned the last completed ProverWorkspaceView. Because "
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
        "latest current view and choose a repair proof intent, a different "
        "context topic, or stop with a concise PROVER REPORT if this blocks "
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


def _view_offers_qed_candidate(view: dict[str, Any]) -> bool:
    moves_container = view.get("candidate_moves")
    moves: list[Any] = []
    if isinstance(moves_container, dict):
        raw_moves = moves_container.get("moves")
        if isinstance(raw_moves, list):
            moves = raw_moves
    elif isinstance(moves_container, list):
        moves = moves_container
    for move in moves:
        if not isinstance(move, dict):
            continue
        tactic = str(move.get("tactic") or move.get("move") or "").strip()
        if tactic.lower().rstrip(".").strip() == "qed":
            return True
    return False


def _extract_json_object(text: str) -> dict[str, Any]:
    raw = (text or "").strip()
    if not raw:
        return {}
    decoder = json.JSONDecoder()
    for idx, ch in enumerate(raw):
        if ch != "{":
            continue
        try:
            obj, _end = decoder.raw_decode(raw[idx:])
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            return obj
    return {}


