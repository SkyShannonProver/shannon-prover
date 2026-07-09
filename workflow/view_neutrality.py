"""Feature flag for the compiler view-boundary cleanup.

Lives at the workflow root (not inside proof_management) so the surface
layer can import it without creating a surface <-> manager package cycle.

See ``docs/design/compiler_view_boundary.md``. When strict, the agent-facing
view is held to the neutrality boundary: heuristic content is advisory only and
**never gates a commit** — a daemon-accepted transition is never converted to a
repair menu nor stripped of its commit affordance.

Default OFF so the flag is behavior-neutral until it is flipped on for the L4
eval A/B (decision 1 in the design doc: reversible-first).
"""
from __future__ import annotations

import os

_ENV = "SHANNON_VIEW_NEUTRALITY_STRICT"
_TRUTHY = frozenset({"1", "true", "yes", "on"})


def view_neutrality_strict() -> bool:
    """True when the view-neutrality boundary is enforced.

    Read per call (not cached) so tests and runs can toggle it via the
    ``SHANNON_VIEW_NEUTRALITY_STRICT`` environment variable.
    """
    return os.environ.get(_ENV, "").strip().lower() in _TRUTHY
