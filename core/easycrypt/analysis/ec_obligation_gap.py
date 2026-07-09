"""Obligation gap signals — proactively flag that the current goal probably
needs a stronger invariant, WITHOUT computing the missing fact.

Lamp (a) of the "IDE, not oracle" design. Like an editor squiggle, this surfaces
WHERE a gap likely is — module program state the conclusion depends on that
nothing in the current context constrains — and never WHAT to add. The agent's
own reasoning fills the conjunct; the shape vocabulary it may reach for is the
companion `invariant_shape_palette` (lamp b), surfaced on the
`call_invariant_skeleton` inspection.

The detector is deliberately conservative so it stays SILENT on healthy goals
and only lights on a real gap:

  * POST side reads only *side-tagged* program state (``Mod.field{1}`` /
    ``...{2}``).  A pRHL goal always side-tags program state, so library
    constants / type names (``SmtMap.empty``, ``Distr.dunifin``) — never
    side-tagged — are excluded.
  * PRE side reads any qualified mention (``={Mod.field}``, ``X{1} = Y{2}``,
    a bare hypothesis), so a field the invariant already couples does NOT flag.
  * A field flags only when it appears in the conclusion yet NOWHERE in the
    context.  As the agent strengthens the invariant the signal dims on its own.
"""
from __future__ import annotations

import re

from core.easycrypt.analysis.ec_utils import dedupe_strings as _dedupe

try:
    from core.easycrypt.analysis.ec_goal_parser import parse_goal  # type: ignore
except Exception:  # pragma: no cover
    parse_goal = None  # type: ignore

# Any module-qualified name: ``Mod.field`` (used for the liberal PRE scan).
_QUAL_FIELD = re.compile(r"\b([A-Z][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_']*)+)")
# Side-tagged program state: ``Mod.field{1}`` / ``Mod.field{2}`` (strict POST).
_STATE_FIELD = re.compile(
    r"\b([A-Z][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_']*)+)\s*\{\s*[12]\s*\}"
)


def _split_pre_post(goal_text: str) -> "tuple[str, str]":
    if parse_goal is not None:
        try:
            info = parse_goal(goal_text)
            pre, post = str(info.pre or ""), str(info.post or "")
            if pre or post:
                return pre, post
        except Exception:
            pass
    # Fallback: split on the last top-level pRHL turnstile.
    if "==>" in goal_text:
        idx = goal_text.rfind("==>")
        return goal_text[:idx], goal_text[idx + 3:]
    return "", ""


def unconstrained_post_fields(goal_text: str) -> "dict[str, Any]":
    """Module program state the conclusion depends on that the context never
    constrains.

    Returns ``{"available": bool, "fields": [...], "note": str}``.  Self-gating:
    ``available`` is False (no signal) whenever every post state field is also
    mentioned somewhere in the pre/hypotheses — healthy, sim-closeable goals stay
    silent.
    """
    pre, post = _split_pre_post(goal_text or "")
    if not post:
        return {"available": False}
    post_fields = _dedupe([m.group(1) for m in _STATE_FIELD.finditer(post)])
    if not post_fields:
        return {"available": False}
    pre_fields = {m.group(1) for m in _QUAL_FIELD.finditer(pre)}
    unconstrained = [f for f in post_fields if f not in pre_fields]
    if not unconstrained:
        return {"available": False}
    return {
        "available": True,
        "fields": unconstrained,
        "note": (
            "Gap likely — the conclusion depends on "
            + ", ".join(unconstrained)
            + ", but no hypothesis or invariant in the current context constrains "
            "this state. If you are building or repairing a call/loop invariant it "
            "probably needs a conjunct over these. Inspect `call_invariant_skeleton` "
            "to see the invariant shapes already used in this development."
        ),
    }
