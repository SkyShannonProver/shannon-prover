"""Manager-state-derived call-frontier surface helpers.

These facts derive from manager-owned state (notably the live EC session source)
that the stateless projection pipeline does not hold, so they are applied to the
turn views after ``project()``.  The producer is idempotent and never raises into
the proof loop.
"""
from __future__ import annotations

import json
from typing import Any, Callable, Optional

class ManagerSurfaceProducer:
    """Owns manager-derived call-frontier structure facts."""

    def __init__(
        self,
        *,
        session_dir: Callable[[], Any],
    ) -> None:
        self._session_dir = session_dir
        # Call-frontier source caches (cheap + source-level constant, computed once).
        self._frontier_source_texts: Optional[list] = None
        self._call_frontier_structure_cache: dict = {}
        self._oracle_diff_cache: Optional[dict] = None

    def inject_call_frontier_structure(self, view: dict) -> None:
        """At a call frontier, surface module aliases + the abstract-adversary glob
        boundary — the mechanical name resolution the agent otherwise traces by
        hand (`ROout -> SplitC2.I2.RO`; `glob A` separate from the state modules).

        Cheap + source-level constant, so computed once and cached. Passive (no
        inspect needed) + never raises into the proof loop.
        """
        try:
            if not isinstance(view, dict):
                return
            ac = view.get("application_context")
            ac = ac if isinstance(ac, dict) else None
            if not ac or not ac.get("visible_call_frontier"):
                return
            sess = self._session_dir()
            if not sess:
                return
            texts = self._frontier_source_texts
            if texts is None:
                from core.easycrypt.analysis.ec_relational_invariant import (
                    state_field_pool, _relational_source_texts)
                from core.easycrypt.analysis.ec_call_frontier_structure import (
                    call_frontier_structure)
                texts = [(t, p) for t, p, *_ in _relational_source_texts(sess)]
                aliases = state_field_pool(sess).get("aliases", {})
                goal = json.dumps(ac.get("visible_call_frontier"))
                self._frontier_source_texts = texts
                self._call_frontier_structure_cache = (
                    call_frontier_structure(texts, aliases=aliases, goal_text=goal) or {})
            struct = self._call_frontier_structure_cache
            if struct:
                ac["call_frontier_structure"] = struct

            # Structural diff of the two oracle modules (per frontier): which
            # procedures diverge between the left/right oracle — the agent's #1
            # hand-reconstruction (set_bad1 vs set_bad1i).
            from core.easycrypt.analysis.ec_oracle_diff import (
                differing_call_modules, oracle_module_diff)

            def _d(x: Any) -> dict[str, Any]:
                return x if isinstance(x, dict) else {}

            vcf = _d(ac.get("visible_call_frontier"))
            lc = _d(vcf.get("left")).get("statement") or ""
            rc = _d(vcf.get("right")).get("statement") or ""

            # inline preview: which modules `inline*` expands vs stops at (abstract)
            if lc and struct.get("abstract_adversaries"):
                from core.easycrypt.analysis.ec_call_frontier_structure import (
                    inline_preview)
                abst = [a.get("name") for a in struct["abstract_adversaries"]]
                prev = inline_preview(texts, lc, abst)
                if prev:
                    ac["inline_preview"] = prev

            lm, rm = differing_call_modules(lc, rc)
            if lm and rm:
                dcache = self._oracle_diff_cache
                if dcache is None:
                    dcache = {}
                    self._oracle_diff_cache = dcache
                if (lm, rm) not in dcache:
                    dcache[(lm, rm)] = oracle_module_diff(texts, lm, rm) or {}
                if dcache[(lm, rm)]:
                    ac["oracle_module_diff"] = dcache[(lm, rm)]

            # Static write-map: who mutates each frame-candidate field. It reduces the agent's
            # single biggest head-simulation ("does UFCMA_li write lbad1 / where is
            # Mem.lc updated"). Keyed off the goal's qualified fields for relevance.
            from core.easycrypt.analysis.ec_concrete_global_frame import (
                write_map_for_goal, _QUAL_FIELD, _strip_side)
            cg = view.get("current_goal")
            goal_lines = cg.get("lines") if isinstance(cg, dict) else None
            goal_text = "\n".join(goal_lines) if isinstance(goal_lines, list) else str(goal_lines or "")
            fields = {
                _strip_side(m.group(1))
                for m in _QUAL_FIELD.finditer(goal_text)
                if "." in m.group(1)
            }
            if fields:
                focus = [m for m in (lm, rm) if m]
                wm = write_map_for_goal(
                    texts, field_universe=sorted(fields), focus_modules=focus)
                if wm:
                    ac["write_map"] = wm

        except Exception:
            pass
