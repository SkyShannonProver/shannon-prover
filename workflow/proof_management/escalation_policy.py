"""System-decided adaptive surface escalation.

Extracted from ``ProofNodeManager`` (audit §8 #8): the manager used to hold the
adaptive-escalation state (a handful of ``_adaptive_*`` fields + two trace-tuned
magic numbers) and the three methods that drive it directly in its ``__init__``.
This concentrates that one concern in a single owner.

Policy: escalation is SYSTEM-decided, never agent-pulled. An "adaptive" run
profile starts the agent on a cheap L1 base surface and flips ONCE, latched, to
the richer escalate target the moment the agent has OBJECTIVELY stalled —
``_stall_threshold`` turns without committed progress, or a hard cap of
``_hard_cap_turns`` total turns. Easy lemmas advance every turn, never escalate,
and stay on the lean surface (kept off any heavier panels); hard lemmas stall and
earn the full surface. The agent cannot unlock tools on demand: reaching for a
gated intent in the cheap phase is rejected with guidance (``reach_block``) and
counts as a no-progress turn, which is itself what nudges toward auto-escalation.
"""
from __future__ import annotations

from typing import Any, Callable, Optional

from workflow.proof_management.types import ManagedTurn
from workflow.surface_profiles import (
    allowed_intents_for_surface_profile,
    probe_disabled,
    resolve_surface_profile,
)

# Trace-tuned thresholds (were magic numbers in ProofNodeManager.__init__).
_DEFAULT_STALL_THRESHOLD = 3   # N: escalate after N turns w/o committed progress
_DEFAULT_HARD_CAP_TURNS = 12   # M: escalate if the lemma drags past M turns


class EscalationPolicy:
    """Owns the adaptive L1->escalate surface decision for one proof node.

    Dependencies are injected as callbacks so the policy stays decoupled from the
    manager's component graph:

    * ``state_version()``  -> the committed ``state_version`` (advances only on
      accepted, progress-making commits; ``turn.ok`` is unreliable — True even on
      reject — so progress is keyed on this).
    * ``latest_view()`` / ``latest_snapshot()`` -> for the reach-block repair turn.
    * ``propagate_profile(profile)`` -> push the escalated profile to every live
      profile-holder (projection / lifecycle / turns) so projection AND
      intent-gating both switch from the next turn.
    * ``audit(record)`` -> structured event sink.
    """

    def __init__(
        self,
        *,
        surface_profile: Optional[str],
        node_id: str,
        audit: Callable[[dict], None],
        state_version: Callable[[], int],
        latest_view: Callable[[], dict],
        latest_snapshot: Callable[[], Any],
        propagate_profile: Callable[[Optional[str]], None],
        stall_threshold: int = _DEFAULT_STALL_THRESHOLD,
        hard_cap_turns: int = _DEFAULT_HARD_CAP_TURNS,
    ) -> None:
        _prof = resolve_surface_profile(surface_profile)
        self.adaptive = bool(_prof is not None and _prof.escalate_to)
        self._escalate_profile = _prof.escalate_to if self.adaptive else None
        # For an adaptive run the agent starts on the cheap L1 base; for any other
        # profile ``base`` == ``effective`` == the run profile (no escalation).
        self.base_profile = "l1_goal_projection" if self.adaptive else surface_profile
        self.escalated = False
        self.effective_profile = self.base_profile
        self._turns_since_progress = 0
        self._turn_count = 0
        self._stall_threshold = stall_threshold
        self._hard_cap_turns = hard_cap_turns
        self._last_sv: Optional[int] = None  # committed state_version baseline
        self._node_id = node_id
        self._audit = audit
        self._state_version = state_version
        self._latest_view = latest_view
        self._latest_snapshot = latest_snapshot
        self._propagate_profile = propagate_profile

    def escalate(self, reason: str) -> bool:
        """Flip the effective surface profile to the escalate target (latched).

        Propagates to every component that holds a profile so projection AND
        intent-gating both switch to the full surface from the next turn. No-op
        (returns False) when the run is not adaptive or has already escalated."""
        if not self.adaptive or self.escalated:
            return False
        self.escalated = True
        self.effective_profile = self._escalate_profile
        self._propagate_profile(self.effective_profile)
        self._audit({
            "kind": "adaptive.escalated",
            "node": self._node_id,
            "reason": reason,
            "to_profile": self.effective_profile,
            "state_version": self._state_version(),
        })
        return True

    def reach_block(self, intent: "AgentIntent") -> "ManagedTurn | None":
        """In the cheap phase, reaching for a richer (gated) intent is rejected with
        guidance — the manager, not the agent, decides escalation. Returns a repair
        turn for a gated intent, else None (intent allowed in the cheap phase)."""
        if intent.intent in allowed_intents_for_surface_profile(self.base_profile):
            return None
        self._audit({
            "kind": "adaptive.reach_blocked",
            "node": self._node_id,
            "intent": intent.intent,
            "turns_since_progress": self._turns_since_progress,
            "state_version": self._state_version(),
        })
        # Switch-aware: when probe is OFF it is never unlocked, so don't name it
        # among the levels the escalation auto-unlocks.
        unlocks = (
            "`probe_tactic` / context topics / `lookup_symbol`"
            if not probe_disabled() else "context topics / `lookup_symbol`"
        )
        msg = (
            f"`{intent.intent}` is not available yet. The manager has NOT judged you "
            "stuck — you have not accumulated enough no-progress / failed steps to "
            "unlock the richer surface. Stay on the fast path: figure out the next "
            "tactic yourself, from your own EasyCrypt knowledge, and commit your best "
            "GENUINE attempt. Wrong attempts are not wasted — repeated no-progress "
            f"steps are exactly what auto-unlocks {unlocks} and the decision panels. "
            "Don't fish for the tools; reason it out and commit."
        )
        return ManagedTurn(
            ok=False,
            workspace_view=dict(self._latest_view()),
            snapshot=self._latest_snapshot(),
            repair_prompt=msg,
            health_event=None,
            manager_actions=[],
        )

    def monitor(self) -> None:
        """Post-turn objective-stall monitor: escalate to the full surface once the
        committed state has failed to advance for ``_stall_threshold`` turns, or the
        lemma drags past the ``_hard_cap_turns`` cap."""
        if not self.adaptive or self.escalated:
            return
        sv = self._state_version()
        if self._last_sv is None:
            self._last_sv = sv  # establish baseline; first turn is free
            return
        self._turn_count += 1
        if sv != self._last_sv:
            self._turns_since_progress = 0
        else:
            self._turns_since_progress += 1
        self._last_sv = sv
        reason = None
        if self._turns_since_progress >= self._stall_threshold:
            reason = f"{self._turns_since_progress} turns without committed progress"
        elif self._turn_count >= self._hard_cap_turns:
            reason = f"hard cap: {self._turn_count} turns without finishing"
        if reason:
            self.escalate(reason)
