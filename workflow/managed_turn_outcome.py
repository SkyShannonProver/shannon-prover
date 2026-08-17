"""Neutral manager-action outcome contract.

Backend execution owns the verdict. Manager services, the proof-state compiler,
and presentation layers consume these typed fields without depending on one
another or reclassifying prose.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


PROOF_STATE_CHANGED = "changed"
PROOF_STATE_UNCHANGED = "unchanged"
PROOF_STATE_READ_ONLY = "read_only"
PROOF_STATE_UNKNOWN = "unknown"
PROOF_STATE_EFFECTS = frozenset({
    PROOF_STATE_CHANGED,
    PROOF_STATE_UNCHANGED,
    PROOF_STATE_READ_ONLY,
    PROOF_STATE_UNKNOWN,
})


def normalize_proof_state_effect(value: Any) -> str:
    """Return the canonical executed-state effect, never a forecast/operation."""
    normalized = str(value or "").strip()
    if normalized in PROOF_STATE_EFFECTS:
        return normalized
    return PROOF_STATE_UNKNOWN


@dataclass(frozen=True)
class ManagerActionOutcome:
    outcome_kind: str
    proof_state_effect: str
    proof_state_changed: bool
    needs_attention: bool = False

    def __post_init__(self) -> None:
        if self.proof_state_effect not in PROOF_STATE_EFFECTS:
            raise ValueError(
                "proof_state_effect must be one of "
                f"{sorted(PROOF_STATE_EFFECTS)!r}, got {self.proof_state_effect!r}"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "outcome_kind": self.outcome_kind,
            "proof_state_effect": self.proof_state_effect,
            "proof_state_changed": self.proof_state_changed,
            "needs_attention": self.needs_attention,
        }


def classify_manager_action_outcome(
    *,
    status: str,
    ok: bool,
    read_only: bool,
    mutates_proof_state: bool,
    state_changed: bool,
    timed_out: bool = False,
    control_menu: bool = False,
    repair_requested: bool = False,
) -> ManagerActionOutcome:
    """Classify one action from structured backend facts only."""
    normalized = str(status or "").strip().lower()
    if control_menu:
        return ManagerActionOutcome(
            "control_menu",
            PROOF_STATE_UNCHANGED,
            False,
            needs_attention=not ok,
        )
    if repair_requested:
        return ManagerActionOutcome("repair", PROOF_STATE_UNCHANGED, False, True)
    if timed_out:
        effect = PROOF_STATE_READ_ONLY if read_only else PROOF_STATE_UNKNOWN
        return ManagerActionOutcome("timeout", effect, False, True)
    if normalized == "backend_contract_error":
        effect = PROOF_STATE_READ_ONLY if read_only else PROOF_STATE_UNKNOWN
        return ManagerActionOutcome("backend_error", effect, False, True)
    if read_only:
        kind = "read_only" if ok else "backend_error"
        return ManagerActionOutcome(
            kind,
            PROOF_STATE_READ_ONLY,
            False,
            needs_attention=not ok,
        )
    if normalized == "partial_success":
        if state_changed:
            return ManagerActionOutcome(
                "partial_success",
                PROOF_STATE_CHANGED,
                True,
                True,
            )
        return ManagerActionOutcome(
            "backend_error",
            PROOF_STATE_UNKNOWN,
            False,
            True,
        )
    if normalized in {"no_progress", "no_progress_reverted"}:
        return ManagerActionOutcome(
            "no_progress",
            PROOF_STATE_UNCHANGED,
            False,
            True,
        )
    if not ok or normalized in {"failed", "error", "rejected", "refused"}:
        return ManagerActionOutcome(
            "rejected",
            PROOF_STATE_UNCHANGED,
            False,
            True,
        )
    if state_changed:
        return ManagerActionOutcome("accepted", PROOF_STATE_CHANGED, True)
    if mutates_proof_state:
        return ManagerActionOutcome(
            "accepted_unconfirmed",
            PROOF_STATE_UNKNOWN,
            False,
        )
    return ManagerActionOutcome("accepted", PROOF_STATE_UNCHANGED, False)


def action_outcome_from_action(action: dict[str, Any]) -> ManagerActionOutcome:
    """Read an already-normalized manager action without prose fallbacks."""
    kind = str(action.get("outcome_kind") or "unknown")
    effect = normalize_proof_state_effect(action.get("proof_state_effect"))
    return ManagerActionOutcome(
        outcome_kind=kind,
        proof_state_effect=effect,
        proof_state_changed=bool(action.get("proof_state_changed")),
        needs_attention=bool(action.get("needs_attention")),
    )


def observation_with_action_outcome(
    observation: dict[str, Any],
    actions: list[dict[str, Any]],
) -> dict[str, Any]:
    """Attach the first visible manager action's typed outcome to last_result."""
    out = dict(observation) if isinstance(observation, dict) else {}
    for action in actions:
        if (
            not isinstance(action, dict)
            or action.get("label") == "managed_goal_view"
        ):
            continue
        out.update(action_outcome_from_action(action).to_dict())
        break
    return out


def proof_state_changed_for_turn(
    actions: list[dict[str, Any]],
    view: dict[str, Any],
) -> bool:
    if any(
        isinstance(action, dict) and bool(action.get("proof_state_changed"))
        for action in actions
    ):
        return True
    last_result = (
        view.get("last_result")
        if isinstance(view.get("last_result"), dict)
        else {}
    )
    return bool(last_result.get("proof_state_changed"))


def turn_needs_attention(
    actions: list[dict[str, Any]],
    view: dict[str, Any],
) -> bool:
    if any(
        isinstance(action, dict) and bool(action.get("needs_attention"))
        for action in actions
    ):
        return True
    last_result = (
        view.get("last_result")
        if isinstance(view.get("last_result"), dict)
        else {}
    )
    return bool(last_result.get("needs_attention"))
