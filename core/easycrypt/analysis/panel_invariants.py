"""Runtime panel-fidelity invariants — a NON-FATAL checker over a built
ProverWorkspaceView.

This is the defense-in-depth half of the "close the finite panel-bug space" plan
(the other half is the generative property test, tests/test_panel_properties.py).
It encodes the strongest invariants the panel must satisfy and reports VIOLATIONS
rather than raising — so it can run inside the live manager's view-sanitization step
and write any violation to the audit log, catching a NEW goal shape that silently
breaks an invariant instead of it slipping through to the agent.

Design contract: pure, total, never raises. `check_panel_invariants(view)` returns a
(possibly empty) list of `{"invariant": str, "detail": str}`. Empty == clean.
"""
from __future__ import annotations

import re
from typing import Any

_SINGLE_SIDED_GOAL_TYPES = frozenset({"hoare", "phoare", "bdhoare"})
# proof_status.status must describe the COMMITTED state, never a last-action outcome.
_VALID_STATUSES = frozenset({
    "open", "closed", "unknown", "candidate_closed_pending_qed",
})


def _d(v: Any) -> dict:
    return v if isinstance(v, dict) else {}


def _lines(goal: Any) -> list[str]:
    g = _d(goal)
    raw = g.get("lines")
    return [str(x) for x in raw] if isinstance(raw, list) else (
        [str(g.get("text"))] if g.get("text") else []
    )


def check_panel_invariants(
    view: dict[str, Any],
    *,
    raw_goal_lines: list[str] | None = None,
) -> list[dict[str, str]]:
    """Check a built ProverWorkspaceView against the panel-fidelity invariants.

    Returns a list of violations; empty means clean. Never raises.
    """
    out: list[dict[str, str]] = []

    def fail(inv: str, detail: str) -> None:
        out.append({"invariant": inv, "detail": detail[:400]})

    try:
        view = _d(view)
        goal = _d(view.get("current_goal"))
        goal_lines = _lines(goal)
        goal_text = "\n".join(goal_lines)
        status_panel = _d(view.get("proof_status"))
        frontier = _d(view.get("program_frontier"))
        nav = _d(frontier.get("procedure_navigation"))

        # INV-1 goal text fidelity: the rendered goal must equal raw EC verbatim
        # (only checked when the caller supplies the raw goal — e.g. the manager
        # has the session's current.out at hand).
        if raw_goal_lines is not None and goal.get("text_fully_shown") is not False:
            if [s.rstrip() for s in goal_lines] != [s.rstrip() for s in raw_goal_lines]:
                fail("goal_text_fidelity",
                     "current_goal.lines differ from raw EC while text_fully_shown")

        # INV-2 proof_status reflects the COMMITTED state, not a last-action error.
        st = str(status_panel.get("status") or "")
        remaining = status_panel.get("remaining_goals")
        if st and st not in _VALID_STATUSES:
            fail("status_committed_state",
                 f"proof_status.status={st!r} is an action outcome, not a committed "
                 f"state (remaining_goals={remaining})")

        # INV-3 sp/wp absorb depth is a VALID leading prefix: per side, the count
        # must be contiguous from order 1 (through_order == absorbable_statements)
        # and not exceed the visible program length.
        n_program_lines = sum(
            1 for ln in goal_lines if re.match(r"^\s*\(\s*\d", ln)
        )
        for side in ("left", "right"):
            entry = _d(_d(nav.get("absorb_depth")).get(side))
            if not entry:
                continue
            n = int(entry.get("absorbable_statements") or 0)
            through = entry.get("through_order")
            if n_program_lines and n > n_program_lines:
                fail("sp_absorb_bound",
                     f"{side} absorb {n} > program length {n_program_lines}")
            if through is not None and int(through) != n:
                fail("sp_absorb_contiguous",
                     f"{side} absorb {n} but through_order {through} is not contiguous "
                     f"from order 1 (would cross a frontier)")

        # INV-4 an unfoldable_goal_head must not be a `<@` procedure call.
        proc_calls = set(re.findall(r"<@\s*([A-Za-z_][A-Za-z0-9_'.]*)", goal_text))
        facts = _d(_d(view.get("facts_and_diagnostics")).get("facts"))
        for head in (facts.get("unfoldable_goal_heads") or []):
            name = str(_d(head).get("name") or "")
            if name and name in proc_calls:
                fail("unfoldable_not_procedure",
                     f"`rewrite /{name}.` offered for a `<@` procedure call")

        # INV-5 the two-sided `eager` surgery handle must be absent on a single-sided
        # goal (and the menu must not offer a tactic that cannot type-check here).
        goal_type = str(goal.get("goal_type") or status_panel.get("goal_type") or "").lower()
        if goal_type in _SINGLE_SIDED_GOAL_TYPES:
            asks = _d(view.get("inspect_lookup_handles")).get("ask_manager_for") or []
            if any((_d(a).get("payload") or {}).get("name") == "eager" for a in asks):
                fail("eager_two_sided_only",
                     f"`eager` (two-sided) offered on a single-sided {goal_type} goal")
    except Exception as exc:  # never raise into the proof loop
        return [{"invariant": "checker_error", "detail": f"{type(exc).__name__}: {exc}"}]
    return out
