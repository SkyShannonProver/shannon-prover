"""Fresh-context continuation (auto context-respawn) — shared logic.

This module holds the small, pure, testable pieces of the fresh-context
continuation feature designed in ``docs/design/fresh_context_continuation.md``:

- env-knob resolution (one place, so defaults stay centralized),
- the per-turn token-watermark detector (Layer 1 detection),
- the frontier brief + accepted-spine builder (the handoff), and
- the proof-open / premature-give-up classifier (Layer 2 backstop).

The wiring that *acts* on these decisions lives in
``workflow.proof_node_runtime`` (the in-worker swap, Layers 1-2) and
``workflow.progress`` (the supervisor marker-reset + Layer-3 crash net). Keeping
the decision logic here makes it unit-testable without spinning up EasyCrypt or a
real ``claude`` child.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any


# --- env knobs (defaults centralized here) -----------------------------------

# Fire the swap BEFORE the agent's context degrades or its claude process dies.
# Empirically the `finish` run's claude process died (exit 143) at ~145k tokens —
# BELOW the old 150k watermark, so the watermark never tripped. 140k fires while
# the agent is still alive and coherent, before the ~145k death and below the
# ~159-169k SDK compaction band. (NOTE: the ~145k death point itself should be
# investigated separately — out of scope here.) Env-overridable via
# SHANNON_CTX_WATERMARK_TOKENS.
DEFAULT_WATERMARK_TOKENS = 140_000
DEFAULT_WATERMARK_TURNS = 2
DEFAULT_RESPAWN_MAX = 2

# Minimum wall-clock runway (seconds) that must remain for a respawn to be worth
# starting — below this a fresh session cannot make meaningful progress.
DEFAULT_MIN_RUNWAY_S = 180.0


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not str(raw).strip():
        return default
    try:
        return int(str(raw).strip())
    except (TypeError, ValueError):
        return default


def watermark_tokens() -> int:
    return _env_int("SHANNON_CTX_WATERMARK_TOKENS", DEFAULT_WATERMARK_TOKENS)


def watermark_turns() -> int:
    return max(1, _env_int("SHANNON_CTX_WATERMARK_TURNS", DEFAULT_WATERMARK_TURNS))


def respawn_max() -> int:
    return max(0, _env_int("SHANNON_CTX_RESPAWN_MAX", DEFAULT_RESPAWN_MAX))


def respawn_disabled() -> bool:
    """Kill switch. On-by-default otherwise.

    Any truthy value (1/true/yes/on) disables the whole mechanism. strict=True:
    a typo'd value raises rather than silently leaving respawn ON — this knob
    defines a tree-search ablation arm, so a mislabel corrupts the comparison.
    """
    from core.env_loader import env_bool

    return env_bool("SHANNON_DISABLE_CTX_RESPAWN", strict=True)


def min_runway_seconds() -> float:
    raw = os.environ.get("SHANNON_CTX_RESPAWN_MIN_RUNWAY_S")
    if raw is None or not str(raw).strip():
        return DEFAULT_MIN_RUNWAY_S
    try:
        return float(str(raw).strip())
    except (TypeError, ValueError):
        return DEFAULT_MIN_RUNWAY_S


# --- Layer 1 detection: per-turn token watermark -----------------------------

def context_tokens_from_assistant_event(event: dict[str, Any]) -> int | None:
    """Total context size for one `assistant` stream-json event, or None.

    The live `stream-json` `assistant` event nests usage under
    ``event["message"]["usage"]`` (verified against the equiv_step4 transcript and
    matching the retired trace-preprocess heuristics). Total context the model saw
    on this turn = ``input_tokens + cache_read_input_tokens +
    cache_creation_input_tokens`` (cache reads/creations are the bulk under
    prompt-caching). Returns None when usage is absent/unparseable so the caller
    leaves the hot-turn counter untouched.
    """
    if not isinstance(event, dict) or event.get("type") != "assistant":
        return None
    message = event.get("message")
    if not isinstance(message, dict):
        return None
    usage = message.get("usage")
    if not isinstance(usage, dict):
        return None

    def _n(key: str) -> int:
        try:
            return int(usage.get(key) or 0)
        except (TypeError, ValueError):
            return 0

    total = (
        _n("input_tokens")
        + _n("cache_read_input_tokens")
        + _n("cache_creation_input_tokens")
    )
    return total if total > 0 else None


class CtxWatermarkDetector:
    """Debounced token-watermark trip for one Claude session generation.

    Feed every `assistant` event. ``ctx_pressure`` latches True once context has
    been at/above the watermark for ``turns`` consecutive assistant turns. Reset
    between generations with :meth:`reset`.
    """

    def __init__(
        self,
        *,
        tokens: int | None = None,
        turns: int | None = None,
        enabled: bool | None = None,
    ) -> None:
        self.tokens = watermark_tokens() if tokens is None else int(tokens)
        self.turns = watermark_turns() if turns is None else max(1, int(turns))
        self.enabled = (not respawn_disabled()) if enabled is None else bool(enabled)
        self.hot_turns = 0
        self.ctx_pressure = False
        self.last_ctx_tokens = 0

    def reset(self) -> None:
        self.hot_turns = 0
        self.ctx_pressure = False

    def observe(self, event: dict[str, Any]) -> bool:
        """Update state for one event; return True iff pressure just tripped.

        Only `assistant` events with usage move the counter. The trip is a rising
        edge — returns True only on the transition into pressure, so the caller
        can terminate the child exactly once, between turns.
        """
        if not self.enabled or self.ctx_pressure:
            return False
        ctx = context_tokens_from_assistant_event(event)
        if ctx is None:
            return False
        self.last_ctx_tokens = ctx
        if ctx >= self.tokens:
            self.hot_turns += 1
        else:
            self.hot_turns = 0
        if self.hot_turns >= self.turns:
            self.ctx_pressure = True
            return True
        return False


# --- Layer 2 classifier: proof-open / premature give-up ----------------------

def proof_is_open(latest_view: dict[str, Any] | None) -> bool:
    """True iff the manager view says the proof is genuinely open.

    Mirrors the manager's own give-up gate
    (``ProofNodeManager._give_up_gate``): a proof is OPEN only when
    ``proof_status.status == "open"`` AND ``remaining_goals != 0``. Closed /
    candidate_* / complete / unknown / missing all read as NOT open, so we never
    misclassify a real or closing finish as premature.
    """
    if not isinstance(latest_view, dict):
        return False
    ps = latest_view.get("proof_status")
    if not isinstance(ps, dict):
        return False
    status = str(ps.get("status") or "")
    remaining = ps.get("remaining_goals")
    return status == "open" and remaining != 0


# --- Handoff: frontier brief + accepted spine -------------------------------


def _canonical_tactic_shape(tactic: str) -> str:
    """Whitespace-normalize a tactic string for dedup, trailing-dot-insensitive."""
    text = " ".join(str(tactic or "").split())
    return text.rstrip(".").strip()


def build_frontier_brief(latest_view: dict[str, Any] | None) -> str:
    """One-paragraph statement of where the proof is, from the manager view.

    Remaining count + phase + the specific current subgoal preview. Best-effort:
    falls back to a terse note if the view is thin.
    """
    if not isinstance(latest_view, dict):
        return "Frontier: proof state unavailable from the current view."
    ps = latest_view.get("proof_status")
    ps = ps if isinstance(ps, dict) else {}
    remaining = ps.get("remaining_goals")
    status = str(ps.get("status") or "unknown")
    phase = ""
    for key in ("phase", "proof_phase", "route_phase"):
        val = latest_view.get(key)
        if isinstance(val, str) and val.strip():
            phase = val.strip()
            break
    goal_preview = ""
    cg = latest_view.get("current_goal")
    if isinstance(cg, dict):
        lines = cg.get("lines")
        if isinstance(lines, list) and lines:
            goal_preview = " / ".join(str(x) for x in lines[:4])
        elif isinstance(cg.get("text"), str):
            goal_preview = cg["text"]
    goal_preview = " ".join(goal_preview.split())
    if len(goal_preview) > 400:
        goal_preview = goal_preview[:399] + "…"
    rem_txt = (
        f"{remaining} goal(s) remaining"
        if isinstance(remaining, int) else f"status={status}"
    )
    parts = [f"Frontier: {rem_txt}"]
    if phase:
        parts.append(f"phase={phase}")
    if goal_preview:
        parts.append(f"current subgoal: {goal_preview}")
    return "; ".join(parts) + "."


def build_accepted_spine(committed_tactics: list[str], *, cap: int = 60) -> list[str]:
    """The confirmed-working tactic spine already accepted (tail-capped)."""
    spine = [t for t in (committed_tactics or []) if str(t or "").strip()]
    if cap and len(spine) > cap:
        return spine[-cap:]
    return spine


# --- Anti-anchoring: strip closed dispositions from forwarded reasoning -------

# Closed-verdict phrases that must never be forwarded as established conclusions.
# A watermark respawn happens MID-reasoning (the agent has not given up), but the
# captured ring buffer can still hold a half-formed wrong conclusion; forwarding
# it verbatim would anchor the fresh context onto a give-up it never reached.
# Match only CLOSED provability verdicts. Deliberately NOT bare "impossible" or
# bare "stuck" — those over-strip legitimate technical observations
# ("impossible to apply byequiv here", "the rewrite got stuck on the conditional").
# We anchor those words to closing/provability senses, and we DO catch the most
# common give-up form ("giving up", which `give[\s-]?up` alone missed).
_CLOSED_VERDICT_RE = re.compile(
    r"\b("
    r"unprovable(?:\s+as\s+posed)?"
    r"|impossible\s+as\s+posed"
    r"|impossible\s+to\s+(?:prove|close|discharge)"
    r"|cannot\s+(?:be\s+proved|prove(?:\s+this)?)"
    r"|no\s+(?:route|way\s+to\s+prove(?:\s+this)?)"
    r"|giv(?:e|ing|en)[\s-]?up"
    r"|gave[\s-]?up"
    r"|unsatisfiable"
    r")\b",
    re.IGNORECASE,
)


def strip_closed_verdicts(text: str) -> str:
    """Neutralize closed dispositions in forwarded recent reasoning.

    Removes/neutralizes closed-verdict phrasings (``unprovable``,
    ``impossible (as posed)``, ``no route``, ``cannot be proved``, ``give up``,
    ``stuck``, case-insensitive) so the working plan/insight survives but the
    conclusion does not. Best-effort: any failure returns the input unchanged so
    the caller can still forward something rather than blocking the swap.
    """
    try:
        if not text:
            return text
        return _CLOSED_VERDICT_RE.sub("[disposition removed]", str(text))
    except Exception:
        return text


def render_handoff_section(
    *,
    frontier_brief: str,
    accepted_spine: list[str],
) -> str:
    """Render the fresh-session opening handoff as NEUTRAL EVIDENCE.

    The handoff is intentionally state/acceptance oriented: where the proof is
    now, and which accepted tactic forms are confirmed-working. Rejected-attempt
    history is left to the agent's own memory rather than injected here.
    """
    lines: list[str] = []
    lines.append("## Fresh-context continuation handoff (neutral evidence)")
    lines.append("")
    lines.append(
        "Your prior context degraded and was swapped for this fresh one. The "
        "EasyCrypt session, accepted proof, and manager are UNCHANGED — nothing "
        "was replayed or lost. The notes below are evidence from your own prior "
        "turns, not instructions."
    )
    lines.append("")
    lines.append(frontier_brief)
    lines.append("")
    if accepted_spine:
        lines.append(
            "### Already accepted (confirmed-working spine — reuse these forms)"
        )
        for tac in accepted_spine:
            lines.append(f"- `{_canonical_tactic_shape(tac)}.`")
        lines.append("")
    lines.append(
        "Read `LEGAL_LATEST_FOLLOWUP` first to recover the current proof "
        "surface, and `LEGAL_PROOF_SO_FAR` only if you need the accepted tactic "
        "spine. Then continue the proof with one `submit_proof_intent` per turn."
    )
    return "\n".join(lines).strip() + "\n"
