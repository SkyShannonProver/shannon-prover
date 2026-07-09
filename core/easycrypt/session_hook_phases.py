"""Stateful commit phases for EasyCrypt session hooks.

These phases are imported and re-exported by ``session_hooks.py`` so existing
callers can keep importing ``AutoSigPhase``, ``PivotStrategyPhase``, and
``AutoDiffPhase`` from the hook registry module. Keeping the phase bodies here
keeps ``session_hooks.py`` focused on hook contexts, simple triggers, and
registry dispatch.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Optional

from core.hooks.contract import CommitPhase, HookResult  # type: ignore

from core.easycrypt import session_pivot_bridge as _pivot_bridge
from core.easycrypt import session_pivot_invariants as _pivot_invariants
from core.easycrypt import session_pivot_routes as _pivot_routes
from core.easycrypt.session_goal_context import is_goal_too_large  # type: ignore
from core.easycrypt.session_placeholders import requires_placeholder_instantiation


def _normalize_plan_step(step: object, lemma_name: str = "") -> str:
    tactic = str(step or "").split("#", 1)[0].strip()
    if lemma_name:
        tactic = tactic.replace("<pivot_name>", lemma_name)
    if tactic and not tactic.endswith("."):
        tactic += "."
    return tactic


def _pivot_display_tag(lem: dict, tag: str) -> str:
    if tag != "DISJOINT":
        return tag
    if _is_pr_checkpoint_lemma(lem):
        return "PR_CHECKPOINT"
    return "NEEDS_INTERMEDIATE"


def _pivot_display_detail(lem: dict, detail: str) -> str:
    text = str(detail or "")
    name = str(lem.get("name") or "this lemma")
    if _is_pr_checkpoint_lemma(lem):
        return (
            "Direct `apply`/`rewrite` does not match the raw endpoint yet, "
            "but this is a live Pr bridge checkpoint. If pursuing this "
            f"Pr-bridge route, inspect it with `-where {name}` and probe a "
            "small intermediate Pr equality to one instantiated side; "
            "otherwise treat it as context for route selection."
        )
    return (
        "This is not a one-step `apply`/`rewrite` on the raw wrapper. "
        "Use it after an explicit intermediate bridge or structural "
        "transform; do not read this as 'irrelevant'."
    ) if "not reachable" in text or "wrapper root differs" in text else text


def _is_pr_checkpoint_lemma(lem: dict) -> bool:
    name = str(lem.get("name") or "").rsplit(".", 1)[-1]
    stmt = str(lem.get("statement") or "")
    return bool(name.startswith("pr_") and "Pr[" in stmt)


def _requires_action_instantiation(action: str) -> bool:
    return requires_placeholder_instantiation(action)


def _session_context_file_path(session) -> Path | None:
    try:
        ctx_file = session.context_file
    except Exception:
        return None
    if ctx_file and ctx_file.exists():
        return ctx_file
    return None






# ─── AutoSigPhase (Phase 3c step 6) ──────────────────────────────────────

class AutoSigPhase(CommitPhase):
    """[AUTO-SIG] — surface a lemma signature when a failed
    apply/rewrite/have/call/ecall references a lemma whose definition
    we can look up. Single emit, but Phase rather than CommitHook
    because the per-name dedup state (`_seen_names`) is genuinely
    session-scoped (don't re-surface the same signature on every
    retry of the same `apply LEMMA`).

    The Session previously held this state as `_auto_sig_seen`; it
    moves to a Phase instance attr.
    """

    _APPLY_NAME_RE = re.compile(
        r"(?:^|\s)(?:apply|exact|rewrite(?:\s*-)?|have(?:\s+\w+)?\s*:=|"
        r"byequiv|ecall|call)\s*\(?\s*(?P<name>[A-Za-z_][A-Za-z0-9_]{2,})"
    )
    _ERROR_NAME_PATTERNS = (
        r"cannot find a pattern for ['`]?([A-Za-z_]\w{2,})['`]?",
        r"unknown lemma ['`]?([A-Za-z_]\w{2,})['`]?",
    )
    _IGNORE_NAMES = frozenset({
        "auto", "wp", "sp", "rnd", "skip", "call", "proc", "inline",
        "smt", "done", "trivial", "simplify", "move", "elim", "case",
        "split", "by", "true", "false", "witness", "fun",
    })

    def __init__(self, session):
        self.session = session
        self._seen_names: set[str] = set()

    def run(self, ctx: CommitHookContext) -> list[HookResult]:
        if not ctx.has_new_error:
            return []
        block = self._build_sig_block(
            ctx.trimmed, ctx.raw_curr, ctx.raw_prev,
        )
        if not block:
            return []
        return [HookResult(text=block, layer=0)]

    def _build_sig_block(self, tactic_text: str, curr_raw: str,
                         prev_raw: str) -> str:
        """Identify the failing lemma name (priority 1: explicit name in
        EC error text; priority 2: extract from tactic text), look up
        its signature, and format the [AUTO-SIG] block. Empty string
        on miss (no name, ignored name, already seen, lookup empty).
        """
        verb = "apply"
        vm = re.match(
            r"^\s*(apply|exact|rewrite|have|byequiv|ecall|call)\b",
            tactic_text,
        )
        if vm:
            verb = vm.group(1).lower()

        new_err_lines = (
            set(curr_raw.splitlines()) - set(prev_raw.splitlines())
        )
        new_err_text = "\n".join(
            ln for ln in new_err_lines
            if re.match(r"^\s*\[(error|critical|fatal)", ln)
        )
        if not new_err_text:
            return ""

        # Priority 1: error text names the failing identifier.
        name = None
        for pat in self._ERROR_NAME_PATTERNS:
            m = re.search(pat, new_err_text)
            if m:
                cand = m.group(1)
                if (cand not in self._IGNORE_NAMES
                        and cand.lower() not in self._IGNORE_NAMES):
                    name = cand
                    break
        # Priority 2: extract from tactic text.
        if not name:
            for m in self._APPLY_NAME_RE.finditer(tactic_text):
                cand = m.group("name")
                if (cand in self._IGNORE_NAMES
                        or cand.lower() in self._IGNORE_NAMES):
                    continue
                name = cand
                break

        if not name or name in self._seen_names:
            return ""

        # Look up the signature
        sig_out = self._lookup_sig(name)
        if not sig_out or "No declaration named" in sig_out:
            return ""
        self._seen_names.add(name)
        # Strip header/footer noise; keep declaration lines only.
        lines = [
            ln for ln in sig_out.splitlines()
            if ln and not ln.startswith("===")
            and not ln.startswith("Usage:")
            and not ln.startswith("Supply ")
        ]
        body = "\n".join(lines).strip()
        return (
            f"[AUTO-SIG] `{verb} {name}` failed. The lemma's signature was "
            f"fetched for you — do NOT guess argument patterns, use the "
            f"exact arity shown below. This is surfaced ONCE per session "
            f"per lemma.\n"
            f"{body}\n"
            f"(Run `-sig {name}` anytime for this information. If {verb} "
            f"still fails with the correct arity, the goal shape doesn't "
            f"match — try `have h := {name} <args>.` and bridge with "
            f"rewrite/smt.)\n\n"
        )

    def _lookup_sig(self, name: str) -> str:
        """Build the search dirs list and call `lookup_lemma_signature`.
        Search includes: --include-dir args, the loaded source file's
        sibling dir, and `easycrypt-src/theories` (always, so stdlib
        lemmas surface even when the include list is populated)."""
        try:
            from core.easycrypt.search.ec_search import lookup_lemma_signature  # type: ignore
        except Exception:
            return ""
        search_dirs: list[Path] = []
        for d in self.session._include_dirs:
            p = Path(d)
            if p.is_dir():
                search_dirs.append(p)
        try:
            meta_path = self.session.dir / "session_meta.json"
            if meta_path.exists():
                import json as _json
                meta = _json.loads(meta_path.read_text())
                src = meta.get("source_file")
                if src:
                    sib = Path(src).resolve().parent
                    if sib.is_dir() and sib not in search_dirs:
                        search_dirs.append(sib)
        except Exception:
            pass
        theories = Path("easycrypt-src/theories")
        if theories.is_dir() and theories not in search_dirs:
            search_dirs.append(theories)
        ctx_file = (self.session.dir / "context.ec"
                    if (self.session.dir / "context.ec").exists()
                    else None)
        for f in self.session.dir.glob("extracted_*.ec"):
            ctx_file = f
            break
        try:
            return lookup_lemma_signature(name, search_dirs, ctx_file)
        except Exception:
            return ""


# ─── PivotStrategyPhase (Phase 3c step 5c) ───────────────────────────────

class PivotStrategyPhase(CommitPhase):
    """The AUTO-PIVOT family — cheap commit context plus opt-in probes.

    The commit-time ``run`` path now emits only static/cheap context so proof
    state refresh stays responsive.  The daemon-backed members of the family
    are still implemented here, but they are reached through explicit
    read-only inspection via ``inspect``.

    Historically this phase owned six emit blocks under a single shape-key
    gate, sharing a lazy pivot catalog and target-lemma metadata.
    Migrated as one Phase because the inner emits aren't independent:
    they all sit under `pivot_shape_key not in _seen_shapes`, share
    the catalog scan, and AUTO-BRIDGE-SUGGEST + AUTO-REWRITE-PROBE
    cross-reference each other via `is_bridge_shape`.

    Inner emits (in registry order; layer assignments per
    `_DISPLAY_LAYER_MAP`):

    * `[AUTO-PIVOT]` / `[AUTO-PIVOT-VERIFIED]`   L3 / L2
    * `[AUTO-PIVOT-CALL-READY]`                   L2
    * `[AUTO-BRIDGE-SUGGEST/VERIFIED]`            L2
    * `[AUTO-CALL-SUGGEST]`                       L3
    * `[AUTO-REWRITE-PROBE]`                      L2
    * `[AUTO-SELF-HINTS]`                         L4

    Cross-Phase coordination: the old commit path wrote
    `ctx.scratch["pivot.call_ready_names"]` for `AutoDiffPhase` annotations.
    That daemon-backed call-ready probe now lives behind explicit inspect
    topics, so commit-time AUTO-DIFF remains unannotated rather than blocking
    on hidden probes.

    Internal lazy state (instance attrs, not Session attrs):
    * `_catalog: list[dict]`     — pivot lemma inventory built once
    * `_target_lemma: str`        — name of the lemma being proved
    * `_seen_shapes: set[str]`    — per-shape dedup
    * `_self_hints_shown: bool`   — once-per-session AUTO-SELF-HINTS
    """

    def __init__(self, session):
        self.session = session
        self._catalog: Optional[list[dict]] = None
        self._target_lemma: Optional[str] = None
        self._seen_shapes: set[str] = set()
        self._self_hints_shown = False

    # ─── Lazy initializers ───

    def _ensure_catalog(self) -> None:
        """Build the pivot catalog from `session.context_file` once.
        Only pivot-like shapes (pr_eq, pr_ineq, equiv, phoare_ll)
        participate.
        """
        if self._catalog is not None:
            return
        self._catalog = []
        if not self.session.context_file.exists():
            return
        try:
            from core.easycrypt.analysis.ec_pr_path_diff import (  # type: ignore
                extract_lemma_inventory, group_lemmas_by_shape,
            )
        except Exception:
            return
        try:
            content = self.session.context_file.read_text(
                encoding="utf-8", errors="replace",
            )
            inv = extract_lemma_inventory(content)
            groups = group_lemmas_by_shape(inv)
            for shape in ("pr_eq", "pr_ineq", "equiv", "phoare_ll"):
                for lem in groups.get(shape, []):
                    self._catalog.append(lem)
        except Exception:
            pass

    def _ensure_target_lemma(self) -> None:
        """Read `_target_lemma` once from `session_meta.json`. Used to
        skip the self-match (target IS one of the lemmas in the
        catalog; matching it against itself yields DIRECT noise).
        """
        if self._target_lemma is not None:
            return
        self._target_lemma = ""
        meta_path = self.session.dir / "session_meta.json"
        if not meta_path.exists():
            return
        try:
            import json as _json
            meta = _json.loads(meta_path.read_text(encoding="utf-8"))
            self._target_lemma = meta.get("lemma", "") or ""
        except Exception:
            pass

    # ─── Main dispatch ───

    def run(self, ctx: CommitHookContext) -> list[HookResult]:
        """Emit only cheap, synchronous context on the commit path.

        The verified AUTO-PIVOT family used to call ``ctx.daemon()``
        unconditionally here.  In managed prover runs that made ordinary
        commits such as ``proc.`` block for tens of seconds even when the final
        emitted block was only static context.  The commit path should behave
        like an IDE proof-state refresh: show the fresh goal immediately, then
        let explicit inspect tools perform daemon-heavy probes when needed.
        """
        if not ctx.active_goal:
            return []
        self._ensure_catalog()
        if not self._catalog:
            return []
        self._ensure_target_lemma()

        raw_goal = ctx.active_goal
        shape_key = "pivot::" + raw_goal[:300]
        if shape_key in self._seen_shapes:
            return []
        self._seen_shapes.add(shape_key)

        results: list[HookResult] = []

        try:
            scored = self._score_pivots(raw_goal)
        except Exception:
            scored = []
        actionable = [m for m in scored if m[0] <= 2]
        disjoint = [m for m in scored if m[0] == 4][:2]
        too_abstract = [m for m in scored if m[0] == 3][:2]

        kept = actionable + too_abstract + disjoint
        # AUTO-PIVOT / AUTO-PIVOT-VERIFIED block
        block = self._render_pivot_block(
            kept, set(), set(), False,
        )
        if block:
            results.append(block)
        # AUTO-CALL-SUGGEST
        try:
            call_sugg = self._try_call_suggest(raw_goal, None)
        except Exception:
            call_sugg = None
        if call_sugg:
            results.append(call_sugg)
        # AUTO-SELF-HINTS (once per session)
        try:
            self_hints = self._try_self_hints()
        except Exception:
            self_hints = None
        if self_hints:
            results.append(self_hints)

        return results

    def inspect(self, ctx: CommitHookContext, mode: str) -> list[HookResult]:
        """Run explicit, read-only pivot inspections.

        ``mode`` is intentionally manager/tool facing, not agent CLI-facing.
        It separates cheap static context from daemon-heavy probes so the
        caller can decide when latency is worth paying.
        """
        if not ctx.active_goal:
            return []
        self._ensure_catalog()
        self._ensure_target_lemma()
        raw_goal = ctx.active_goal
        mode = str(mode or "context").strip().replace("-", "_")
        if mode == "context":
            return self._inspect_context(raw_goal)
        if not self._catalog and mode not in {
            "call_site", "bridge", "rewrite", "call_invariant_skeleton",
        }:
            return []
        h = ctx.daemon()
        # One shared probe budget for this whole inspect: producers that co-run
        # (glob + relational on call_invariant_skeleton) read this via
        # _resolve_probe_deadline() so their probe times sum under ~10 s.
        import time as _time
        self._inspect_deadline = _time.monotonic() + self._INSPECT_PROBE_BUDGET_S
        if mode == "verified":
            return self._inspect_verified(raw_goal, h)
        if mode == "call_site":
            return self._inspect_call_site(raw_goal, h)
        if mode == "call_invariant_skeleton":
            results: list[HookResult] = []
            try:
                glob_skel = self._try_call_glob_invariant(raw_goal, h)
                if glob_skel:
                    results.append(glob_skel)
            except Exception as exc:
                results.append(HookResult(
                    text=(
                        "\n[CALL-INVARIANT-SKELETON/ERROR] could not synthesize "
                        f"the glob skeleton: {type(exc).__name__}: {exc}\n"
                    ),
                    layer=3, kind="recommendation",
                    errors=[{"code": "call_invariant_skeleton.error",
                             "message": f"{type(exc).__name__}: {exc}"}],
                ))
            # Field-correct named-coupling carrier (the verified successor to the
            # glob frame); best-effort, never blocks the glob skeleton.
            try:
                rel_skel = self._try_relational_invariant(raw_goal, h)
                if rel_skel:
                    results.append(rel_skel)
            except Exception:
                pass
            return results
        if mode == "bridge":
            try:
                bridge = self._try_bridge_suggest(raw_goal, h)
            except Exception as exc:
                bridge = HookResult(
                    text=(
                        "\n[BRIDGE-OPTIONS/ERROR] The manager could not "
                        f"compile bridge options: {type(exc).__name__}: {exc}\n"
                    ),
                    layer=2,
                    kind="recommendation",
                    errors=[{
                        "code": "bridge_options.compiler_error",
                        "message": f"{type(exc).__name__}: {exc}",
                    }],
                    debug={"exception_type": type(exc).__name__},
                )
            return [bridge] if bridge else []
        if mode == "rewrite":
            try:
                rewrite = self._try_rewrite_probe(raw_goal, h)
            except Exception:
                rewrite = None
            return [rewrite] if rewrite else []
        return self._inspect_context(raw_goal)

    def _inspect_context(self, raw_goal: str) -> list[HookResult]:
        results: list[HookResult] = []
        try:
            scored = self._score_pivots(raw_goal)
        except Exception:
            scored = []
        actionable = [m for m in scored if m[0] <= 2]
        disjoint = [m for m in scored if m[0] == 4][:2]
        too_abstract = [m for m in scored if m[0] == 3][:2]
        block = self._render_pivot_block(
            actionable + too_abstract + disjoint,
            set(),
            set(),
            False,
        )
        if block:
            results.append(block)
        try:
            call_sugg = self._try_call_suggest(raw_goal, None)
        except Exception:
            call_sugg = None
        if call_sugg:
            results.append(call_sugg)
        return results

    def _inspect_verified(
        self,
        raw_goal: str,
        h: Optional[DaemonHandle],
    ) -> list[HookResult]:
        try:
            scored = self._score_pivots(raw_goal)
        except Exception:
            scored = []
        actionable = [m for m in scored if m[0] <= 2]
        disjoint = [m for m in scored if m[0] == 4][:2]
        too_abstract = [m for m in scored if m[0] == 3][:2]
        verified_names, tried_names, verify_errors, verification_ran = (
            self._verify_actionable(h, actionable)
        )
        if verification_ran:
            actionable = [
                (rank, lem, r) for rank, lem, r in actionable
                if lem.get("name", "") not in verify_errors
            ]
        block = self._render_pivot_block(
            actionable + too_abstract + disjoint,
            verified_names,
            tried_names,
            verification_ran,
        )
        return [block] if block else []

    def _inspect_call_site(
        self,
        raw_goal: str,
        h: Optional[DaemonHandle],
    ) -> list[HookResult]:
        results: list[HookResult] = []
        call_ready_names = self._probe_call_ready(h, set(), {})
        if call_ready_names:
            results.append(self._render_call_ready(call_ready_names))
        try:
            call_sugg = self._try_call_suggest(raw_goal, h)
        except Exception:
            call_sugg = None
        if call_sugg:
            results.append(call_sugg)
        try:
            body_res = self._try_called_proc_body(raw_goal)
        except Exception:
            body_res = None
        if body_res:
            results.append(body_res)
        return results

    def _try_called_proc_body(self, raw_goal: str) -> Optional[HookResult]:
        return _pivot_routes.try_called_proc_body(self, raw_goal)

    @staticmethod
    def _raw_goal_frontier_has_call(raw_goal: str) -> bool:
        """Best-effort guard: called-proc body is only for the current call head.

        EasyCrypt goal text may contain future calls inside a visible while/if
        body.  Those are not current call-site options yet, so static body
        extraction must not surface them as a call-site result.
        """
        text = str(raw_goal or "")
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith(("Type variables:", "Context", "Bound")):
                continue
            if set(line) <= {"-"}:
                continue
            marker = PivotStrategyPhase._program_frontier_marker(line)
            if marker:
                return marker == "call"
        return PivotStrategyPhase._program_frontier_marker(text) == "call"

    @staticmethod
    def _program_frontier_marker(text: str) -> str:
        line = re.sub(
            r"^\(?\s*\d+(?:\.\d+)*(?:--)?\)?\s*",
            "",
            str(text or "").strip(),
        )
        candidates: list[tuple[int, str]] = []
        for kind, pattern in (
            ("call", r"<@"),
            ("sample", r"<\$"),
            ("assign", r"<-"),
            ("while", r"\bwhile\s*\("),
            ("if", r"\bif\s*\("),
        ):
            match = re.search(pattern, line)
            if match:
                candidates.append((match.start(), kind))
        if not candidates:
            return ""
        return min(candidates, key=lambda item: item[0])[1]

    # ─── AUTO-PIVOT scoring + verification ───

    _RANK = {
        "DIRECT": 0, "ARG_DIFF": 1, "UNFOLD": 2,
        "TOO_ABSTRACT": 3, "DISJOINT": 4,
    }

    def _score_pivots(self, raw_goal: str) -> list:
        """Run `pivot_applicability` against each catalog entry; return
        list of (rank, lem, result) sorted by tag-rank. Skips the
        self-match against the target lemma."""
        from core.easycrypt.analysis.ec_pr_path_diff import pivot_applicability  # type: ignore
        scored: list = []
        latest_rewrite = _pivot_bridge._rewrite_direction_and_name(
            self._latest_committed_tactic(),
        )
        for lem in self._catalog or []:
            pstmt = lem.get("statement", "") or ""
            if not pstmt:
                continue
            if (self._target_lemma
                    and lem.get("name") == self._target_lemma):
                continue
            if latest_rewrite:
                leaf = str(lem.get("name") or "").rsplit(".", 1)[-1]
                if leaf == latest_rewrite[1]:
                    continue
            try:
                r = pivot_applicability(pstmt, raw_goal)
            except Exception:
                continue
            tag = r.get("tag", "NO_MATCH")
            if tag in self._RANK:
                scored.append((self._RANK[tag], lem, r))
        return scored

    def _verify_actionable(self, h: Optional[DaemonHandle],
                           actionable: list) -> tuple[set, set, dict, bool]:
        """Daemon-side verification for actionable plans. Single-step
        (DIRECT/ARG_DIFF) via try_tactic; multi-step (UNFOLD) via
        try_chain. Cap = 5 across both. Returns
        (verified, tried, errors, verification_ran).
        """
        verified: set[str] = set()
        tried: set[str] = set()
        errors: dict[str, str] = {}
        if not actionable or h is None:
            return verified, tried, errors, False

        single_step = []
        multi_step = []
        budget = 5
        for rank, lem, r in actionable:
            plan = r.get("plan") or []
            if not plan:
                continue
            if len(plan) == 1 and rank <= 1:
                single_step.append((rank, lem, r))
            elif len(plan) > 1:
                multi_step.append((rank, lem, r))
            if (len(single_step) + len(multi_step)) >= budget:
                break
        verification_ran = bool(single_step or multi_step)

        for _, lem, r in single_step:
            plan = r.get("plan") or []
            if len(plan) != 1:
                continue
            tac = plan[0].split("#", 1)[0]
            tac = tac.replace("<pivot_name>", lem["name"]).strip()
            if not tac.endswith("."):
                tac = tac + "."
            tried.add(lem["name"])
            try:
                vres = h.cli.try_tactic(h.dbe._session_id, tac)
            except Exception:
                continue
            if vres.get("accepted"):
                verified.add(lem["name"])
            else:
                err = vres.get("error") or {}
                kind = (err.get("kind", "unknown")
                        if isinstance(err, dict) else "unknown")
                errors[lem["name"]] = kind
        for _, lem, r in multi_step:
            plan = r.get("plan") or []
            if len(plan) <= 1:
                continue
            tactics_list = []
            for step in plan:
                t = step.split("#", 1)[0]
                t = t.replace("<pivot_name>", lem["name"]).strip()
                if not t.endswith("."):
                    t = t + "."
                tactics_list.append(t)
            tried.add(lem["name"])
            try:
                chain = h.cli.try_chain(h.dbe._session_id, tactics_list)
            except Exception:
                continue
            if chain.get("accepted"):
                verified.add(lem["name"])
            else:
                err = chain.get("error") or {}
                kind = (err.get("kind", "unknown")
                        if isinstance(err, dict) else "unknown")
                fa = chain.get("failed_at")
                if fa is not None:
                    kind = f"{kind}@step{fa + 1}"
                errors[lem["name"]] = kind
        return verified, tried, errors, verification_ran

    _CALL_PROBE_BUDGET = 6

    def _probe_call_ready(self, h: Optional[DaemonHandle],
                          verified: set, errors: dict) -> set[str]:
        """For each `equiv` pivot not already covered by verification,
        run `call <name>.` through the daemon. Surface the accepted
        ones — these are the lemmas that close a call site cleanly
        even when the wrapper-tree comparison says DISJOINT.
        """
        ready: set[str] = set()
        if h is None:
            return ready
        equiv_pivots: list[dict] = []
        for lem in self._catalog or []:
            stmt_head = (lem.get("statement") or "")[:120].lower()
            if re.search(r"\bequiv\b", stmt_head):
                if (self._target_lemma
                        and lem.get("name") == self._target_lemma):
                    continue
                equiv_pivots.append(lem)
        equiv_pivots.sort(key=lambda l: l.get("name", ""))
        probed = 0
        for lem in equiv_pivots:
            if probed >= self._CALL_PROBE_BUDGET:
                break
            name = lem.get("name", "")
            if not name or name in verified or name in errors:
                continue
            probed += 1
            try:
                vres = h.cli.try_tactic(
                    h.dbe._session_id, f"call {name}.",
                )
            except Exception:
                continue
            if vres.get("accepted"):
                ready.add(name)
        return ready

    # ─── Renderers ───

    def _render_pivot_block(self, kept: list, verified: set,
                            tried: set,
                            verification_ran: bool) -> Optional[HookResult]:
        if not kept:
            return None
        kept = sorted(kept, key=lambda x: (x[0], x[1].get("name", "")))
        header = (
            "[AUTO-PIVOT-VERIFIED]"
            if verification_ran
            else "[AUTO-PIVOT]"
        )
        out = [
            f"{header} pre-declared lemmas near the current proof frontier:",
            "  (Tags decide how to use each proof fact. DIRECT/ARG_DIFF are",
            "   one-step actions; PR_CHECKPOINT is a live Pr bridge that needs",
            "   an intermediate equality if that route matches the endpoint; proof status is",
            "   separate from applicability.)",
        ]
        if verification_ran:
            n_ver = len(verified)
            n_try = len(tried)
            out.append(
                f"  Empirical verification: {n_ver}/{n_try} "
                "actionable plan(s) accepted by EC "
                "(rejected ones suppressed)."
            )
        out.append("")
        for _, lem, r in kept:
            internal_tag = str(r["tag"])
            tag = _pivot_display_tag(lem, internal_tag)
            if lem.get("name") in verified:
                tag = f"{tag}/VERIFIED"
            out.append(f"  [{tag}] `{lem['name']}`")
            out.append(
                f"      → {_pivot_display_detail(lem, str(r.get('detail') or ''))}"
            )
            plan = r.get("plan") or []
            if plan:
                out.append("      Tactic plan (substitute the pivot name):")
                for step in plan:
                    out.append(f"        {step.replace('<pivot_name>', lem['name'])}")
            elif _pivot_display_tag(lem, internal_tag) == "PR_CHECKPOINT":
                out.append("      Bridge plan:")
                out.append(
                    f"        - if testing this route, inspect with `-where {lem['name']}`"
                )
                out.append(
                    "        - build/probe the small intermediate Pr equality "
                    "to one instantiated checkpoint side"
                )
                out.append(
                    f"        - use `{lem['name']}` only if that bridge simplifies the endpoint"
                )
        out.append("")
        out.append(
            "  Tag guide: DIRECT/ARG_DIFF → run the `apply` "
            "shown immediately. UNFOLD → run the "
            "`inline{N}` chain first, THEN `apply`; lower-level "
            "`inline *`/`wp`/`sp`/`auto` before the shown `call` can "
                "erase the call structure, so probe the displayed plan first. "
                "TOO_ABSTRACT → pivot is too general; "
                "instantiate with `have :=`. PR_CHECKPOINT → "
                "Pr bridge context; inspect it only when testing that route. "
                "NEEDS_INTERMEDIATE → use after an "
                "explicit bridge or structural transform."
            )
        if verification_ran:
            out.append(
                "  /VERIFIED suffix = daemon just ran the "
                "plan (apply for single-step, try_chain "
                "for UNFOLD multi-step) and EC accepted "
                "it — apply with high confidence. "
                "Absence of /VERIFIED means the plan was "
                "beyond the verification cap — probe it "
                "yourself with `-try -c '<plan>'`."
            )
        layer = 2 if verification_ran else 3
        recommendations, evidence = self._pivot_structured_payload(
            kept, verified, tried, verification_ran,
        )
        return HookResult(
            text="\n" + "\n".join(out) + "\n",
            layer=layer,
            kind="recommendation",
            recommendations=recommendations,
            evidence=evidence,
            notes=[{
                "code": "auto_pivot.verified_suffix",
                "message": (
                    "/VERIFIED entries were daemon-accepted on the live "
                    "goal; other entries are deterministic shape matches."
                ),
            }] if verification_ran else [],
        )

    def _pivot_structured_payload(
        self, kept: list, verified: set, tried: set, verification_ran: bool,
    ) -> tuple[list[dict], dict]:
        recommendations: list[dict] = []
        deterministic: list[dict] = []
        probe: list[dict] = []
        for idx, (rank, lem, r) in enumerate(kept):
            name = str(lem.get("name") or "")
            tag = str(r.get("tag") or "")
            display_tag = _pivot_display_tag(lem, tag)
            display_detail = _pivot_display_detail(
                lem, str(r.get("detail") or ""),
            )
            plan = [
                _normalize_plan_step(step, name)
                for step in (r.get("plan") or [])
            ]
            plan = [step for step in plan if step]
            ev_id = f"deterministic.auto_pivot.{idx}"
            evidence_refs = [ev_id]
            deterministic.append({
                "id": ev_id,
                "producer": "ec_pr_path_diff.pivot_applicability",
                "lemma": name,
                "rank": int(rank),
                "tag": display_tag,
                "detail": display_detail,
            })
            if name in tried:
                probe_id = f"probe.auto_pivot.{idx}"
                evidence_refs.append(probe_id)
                probe.append({
                    "id": probe_id,
                    "producer": "EasyCrypt daemon",
                    "lemma": name,
                    "accepted": name in verified,
                })
            daemon_verified = name in verified
            unverified_hint = not daemon_verified
            if plan:
                action = " ".join(plan)
                kind = "pivot_tactic" if len(plan) == 1 else "tactic_chain"
                action_type = (
                    "runnable_tactic" if daemon_verified else "strategy_hint"
                )
            else:
                action = f"-where {name}" if name else "inspect pivot lemma"
                kind = "lemma_lookup"
                action_type = "strategy_hint"
            metadata = {
                "tag": display_tag,
                "rank": rank,
                "plan": plan,
                "daemon_tried": name in tried,
                "daemon_verified": daemon_verified,
                "source_kind": (
                    "verified_pivot" if daemon_verified else "unverified_pivot_hint"
                ),
                "scheduler_role": (
                    "typed_resource_use"
                    if daemon_verified else "unverified_pivot_background"
                ),
                "authority_rank": 80 if daemon_verified else 0,
                "epistemic_status": (
                    "daemon_probe_accepted"
                    if daemon_verified else
                    "unverified_pivot_not_frontier_verified"
                ),
                "unverified_pivot_hint": unverified_hint,
            }
            if plan and daemon_verified:
                metadata["submit"] = {
                    "intent": "commit_tactic",
                    "payload": {"tactic": action},
                }
            recommendations.append({
                "id": f"auto_pivot.{idx}",
                "kind": kind,
                "producer": (
                    "AUTO-PIVOT-VERIFIED"
                    if verification_ran else "AUTO-PIVOT"
                ),
                "action": action,
                "why": display_detail or "Pivot lemma matched the current goal.",
                "action_type": action_type,
                "confidence": "verified" if name in verified else "medium",
                "preconditions": [
                    "proof_state.status == open",
                    "current goal still matches the pivot scoring shape",
                ],
                "source_refs": [{
                    "kind": "lemma",
                    "id": name,
                    "details": {
                        "tag": display_tag,
                        "rank": rank,
                        "statement": lem.get("statement") or "",
                    },
                }],
                "evidence_refs": evidence_refs,
                "metadata": metadata,
            })
        evidence = {
            "deterministic": deterministic,
            "probe": probe,
        }
        return recommendations, evidence

    def _render_call_ready(self, names: set[str]) -> HookResult:
        ready_out = [
            "",
            "[AUTO-PIVOT-CALL-READY] oracle-equivalence "
            "lemmas that `call <name>.` ACCEPTS on your "
            "CURRENT goal (daemon-verified):",
        ]
        for name in sorted(names):
            ready_out.append(f"  - `call {name}.`")
        ready_out.append(
            "  → Use one of these directly. `inline *.` "
            "at this equiv would erase the call sites that "
            "`call <name>.` matches against, and EC can only "
            "recover them by undoing. Prefer `call <name>.` → then `auto.` / "
            "`smt()` to close residuals."
        )
        recommendations = []
        probe = []
        for idx, name in enumerate(sorted(names)):
            ev_id = f"probe.auto_pivot_call_ready.{idx}"
            recommendations.append({
                "id": f"auto_pivot_call_ready.{idx}",
                "kind": "call_tactic",
                "producer": "AUTO-PIVOT-CALL-READY",
                "action": f"call {name}.",
                "why": (
                    "The daemon accepted this named oracle-equivalence "
                    "lemma on the live call-site goal."
                ),
                "action_type": "runnable_tactic",
                "confidence": "verified",
                "preconditions": [
                    "proof_state.status == open",
                    "the current goal still contains the same call site",
                ],
                "source_refs": [{"kind": "lemma", "id": name}],
                "evidence_refs": [ev_id],
                "metadata": {},
            })
            probe.append({
                "id": ev_id,
                "producer": "EasyCrypt daemon try_tactic",
                "accepted": True,
                "tactic": f"call {name}.",
            })
        return HookResult(
            text="\n".join(ready_out) + "\n",
            layer=2,
            kind="recommendation",
            recommendations=recommendations,
            evidence={"probe": probe},
        )

    # ─── AUTO-BRIDGE-SUGGEST ───

    _BRIDGE_BUDGET = 8
    _CHAIN_BUDGET = 6
    # A daemon probe is ~1.5 s of EC type-check compute (measured) and does NOT
    # amortize across a batch — so the only way to keep an inspect under the
    # manager's ~10 s information-latency budget is to bound the probe COUNT and
    # wall-clock. Cap the verification scan and bail before the deadline; any
    # candidates left unprobed are reported, never silently dropped.
    _INSPECT_PROBE_CAP = 6
    _INSPECT_PROBE_BUDGET_S = 8.0
    # Reserve one probe's worth of time when deciding whether to start another:
    # a probe cannot be interrupted, so a guard that only checks `now > deadline`
    # lets a probe begin just under the deadline and overrun it by ~1.5-1.8 s
    # (plus render), which pushed pr_bridge_routes to 10.8 s. Don't start a probe
    # that can't finish before the deadline.
    _PROBE_EST_S = 2.0
    # Set by `inspect` for the duration of one inspect dispatch so producers that
    # co-run on a single inspect (glob + relational on call_invariant_skeleton)
    # SHARE one budget instead of each getting a fresh 8 s; left in the past
    # between inspects, where _resolve_probe_deadline() ignores it.
    _inspect_deadline: "Optional[float]" = None

    def _resolve_probe_deadline(self) -> float:
        """Wall-clock deadline for inspect probing. A live shared deadline (set by
        `inspect`, still in the future) is honored so co-running producers sum
        under one budget; otherwise — standalone (a commit hook) or a stale value
        — a producer gets its own fresh budget."""
        import time as _t
        now = _t.monotonic()
        shared = self._inspect_deadline
        return (shared if (shared is not None and shared > now)
                else now + self._INSPECT_PROBE_BUDGET_S)

    @staticmethod
    def _bridge_candidates_in_goal(candidates, raw_goal):
        return _pivot_bridge.bridge_candidates_in_goal(candidates, raw_goal)

    _CALL_CALLEE = _pivot_bridge._CALL_CALLEE
    _GLOB_MENTION = _pivot_bridge._GLOB_MENTION

    @staticmethod
    def _called_adversary_roots(goal_text):
        return _pivot_bridge.called_adversary_roots(goal_text)

    def _scan_named_bridge_fallback(self, raw_goal: str) -> list[dict[str, Any]]:
        return _pivot_bridge.scan_named_bridge_fallback(self, raw_goal)

    def _named_bridge_fallback_block(
        self, raw_goal: str,
    ) -> tuple[str, list[dict[str, Any]]]:
        return _pivot_bridge.named_bridge_fallback_block(self, raw_goal)

    def _try_bridge_suggest(self, raw_goal: str,
                            h: Optional[DaemonHandle]) -> Optional[HookResult]:
        return _pivot_bridge.try_bridge_suggest(self, raw_goal, h)

    def _proof_ir_pr_bridge_candidates(self, raw_goal: str) -> list[dict[str, Any]]:
        return _pivot_bridge.proof_ir_pr_bridge_candidates(self, raw_goal)

    @staticmethod
    def _typed_bridge_candidates_from_handles(handles):
        return _pivot_bridge.typed_bridge_candidates_from_handles(handles)

    @staticmethod
    def _typed_bridge_chain(entry):
        return _pivot_bridge.typed_bridge_chain(entry)

    @staticmethod
    def _dedupe_bridge_candidates(candidates):
        return _pivot_bridge.dedupe_bridge_candidates(candidates)

    def _latest_committed_tactic(self) -> str:
        hist = getattr(self.session, "history", None)
        if not hist:
            return ""
        try:
            lines = [
                line.strip()
                for line in Path(hist).read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
        except Exception:
            return ""
        return lines[-1] if lines else ""

    def _committed_tactics(self) -> list[str]:
        """All committed tactic lines (oldest->newest), for sticky-fact scans."""
        hist = getattr(self.session, "history", None)
        if not hist:
            return []
        try:
            return [
                line.strip()
                for line in Path(hist).read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
        except Exception:
            return []

    def _up_to_bad_call_coherence(self, raw_goal: str):
        return _pivot_bridge.up_to_bad_call_coherence(self, raw_goal)

    # ─── CALL-INVARIANT GLOB SKELETON (mechanical) ───

    def _try_relational_invariant(self, raw_goal: str,
                                  h: Optional[DaemonHandle]) -> Optional[HookResult]:
        return _pivot_invariants.try_relational_invariant(self, raw_goal, h)

    def _shape_palette_block(
        self, raw_goal: str
    ) -> "Optional[tuple[list[str], dict[str, Any]]]":
        return _pivot_invariants.shape_palette_block(self, raw_goal)

    def _try_call_glob_invariant(self, raw_goal: str,
                                 h: Optional[DaemonHandle]) -> Optional[HookResult]:
        return _pivot_invariants.try_call_glob_invariant(self, raw_goal, h)

    # ─── AUTO-CALL-SUGGEST ───

    def _try_call_suggest(self, raw_goal: str,
                          h: Optional[DaemonHandle]) -> Optional[HookResult]:
        return _pivot_routes.try_call_suggest(self, raw_goal, h)

    def _proof_ir_call_site_route(self) -> dict[str, Any]:
        return _pivot_routes.proof_ir_call_site_route(self)

    def _render_call_site_route_options(
        self,
        route: dict[str, Any],
        h: Optional[DaemonHandle],
    ) -> HookResult:
        return _pivot_routes.render_call_site_route_options(self, route, h)

    @staticmethod
    def _call_site_candidate_tactics(templates):
        return _pivot_routes.call_site_candidate_tactics(templates)

    # ─── AUTO-REWRITE-PROBE ───

    def _try_rewrite_probe(self, raw_goal: str,
                           h: Optional[DaemonHandle]) -> Optional[HookResult]:
        return _pivot_routes.try_rewrite_probe(self, raw_goal, h)

    def _collect_rewrite_candidates(
            self, raw_goal: str) -> list[tuple[str, str]]:
        return _pivot_routes.collect_rewrite_candidates(self, raw_goal)

    # ─── AUTO-SELF-HINTS ───

    def _try_self_hints(self) -> Optional[HookResult]:
        if not self._target_lemma or self._self_hints_shown:
            return None
        narrative = self.session._load_narrative()
        match = None
        for l in (narrative.get("lemma_catalog") or []):
            nm = l.get("name", "")
            short = nm.split(".")[-1]
            if nm == self._target_lemma or short == self._target_lemma:
                match = l
                break
        if not match:
            return None

        legacy_fields = [
            key for key in (
                "closer_hints",
                "call_template",
                "invariant_sketch",
                "typical_tail",
                "rewrite_form",
            )
            if match.get(key) not in (None, "", [], {})
        ]
        if not legacy_fields:
            return None

        self._self_hints_shown = True
        return HookResult(
            text=(
                "\n[AUTO-SELF-HINTS/LEGACY_NARRATIVE_REJECTED] The target "
                f"lemma `{self._target_lemma}` has legacy narrative proof-hint "
                "fields, but target-specific closer/call/invariant/tactic "
                "hints are not manager-owned proof options. They were not "
                "shown to the agent. Use verified "
                "pr_bridge_routes/call_site_options/rewrite_candidates instead.\n"
            ),
            layer=4,
            kind="recommendation",
            recommendations=[],
            evidence={"context": [{
                "id": "context.self_hints.legacy_narrative",
                "producer": "session._load_narrative",
                "target_lemma": self._target_lemma,
                "legacy_fields": legacy_fields,
                "used_for_agent_guidance": False,
            }]},
            notes=[{
                "code": "self_hints.legacy_narrative_rejected",
                "message": (
                    "Target lemma proof-hint fields are tainted legacy "
                    "context and are not injected as proof guidance."
                ),
            }],
        )

# ─── [AUTO-DIFF] phase (Phase 3c step 5b) ────────────────────────────────

class AutoDiffPhase(CommitPhase):
    """Compute and emit `[AUTO-DIFF]` for the active goal — pRHL/equiv
    program alignment, probability-goal Pr/module diff, or eager-judgment
    procedure diff. Single emit per alignment shape (dedup via
    `_seen_alignment_shapes` instance attr).

    Annotation: when `PivotStrategyPhase` (registered earlier in
    `Session.commit_phases`) has run and written
    `ctx.scratch["pivot.call_ready_names"]`, this Phase reads that set
    and tags each `→ \\`call NAME\\`` line in the diff with
    `✓ daemon-ready at this state` or
    `⚠ this SUGGESTION not daemon-ready ...` based on membership.

    If PivotStrategyPhase did not emit for a given commit, the scratch
    entry is absent and the diff is left unannotated. The legacy stale-
    pending bug (alignment-shape-OLD + pivot-shape-NEW emitting an
    annotated diff from a *prior* commit) is fixed by the per-commit
    scratch lifetime.
    """

    def __init__(self, session):
        # Session reference is needed for two cross-cutting reads:
        # `session.context_file` (for local-equiv lookup) and
        # `session._annotate_repeat_recommendations` (which reads
        # commit_meta.log + Session._last_tactics — session-scoped state
        # that doesn't belong on a Phase).
        self.session = session
        self._seen_alignment_shapes: set[str] = set()

    def run(self, ctx: CommitHookContext) -> list[HookResult]:
        if not ctx.active_goal:
            return []
        try:
            diff_text, shape_key = self._classify_and_diff(ctx.active_goal)
        except Exception:
            return []
        if not (diff_text and shape_key):
            return []
        if shape_key in self._seen_alignment_shapes:
            return []
        self._seen_alignment_shapes.add(shape_key)
        # Annotate "you already tried this" warnings inline — uses
        # commit_meta.log + Session._last_tactics, which the Phase
        # accesses via `self.session._annotate_repeat_recommendations`.
        try:
            diff_text = self.session._annotate_repeat_recommendations(diff_text)
        except Exception:
            pass
        # Large-goal abbreviation
        if is_goal_too_large(ctx.active_goal):
            diff_text = self._abbreviate(diff_text)
        # Optional ✓/⚠ annotation if PivotStrategyPhase ran first AND
        # the daemon was reachable (without daemon, we can't validate
        # pivot recommendations — leave the diff unannotated).
        call_ready = ctx.scratch.get("pivot.call_ready_names")
        if call_ready and ctx.daemon() is not None:
            diff_text = self._annotate_call_ready(diff_text, call_ready)
        recommendations = self._diff_recommendations(
            diff_text,
            call_ready if isinstance(call_ready, set) else set(),
        )
        return [HookResult(
            text="\n" + diff_text + "\n",
            layer=3,
            kind="recommendation" if recommendations else "analysis",
            recommendations=recommendations,
            evidence={
                "deterministic": [{
                    "id": "deterministic.auto_diff",
                    "producer": "ec_pr_path_diff",
                    "shape_key": shape_key[:200],
                    "has_call_ready_annotation": bool(call_ready),
                }],
                "raw": [{
                    "id": "raw.auto_diff_text",
                    "format": "legacy_text",
                    "preview": diff_text[:1000],
                }],
            },
            notes=[] if recommendations else [{
                "code": "auto_diff.no_structured_tactic",
                "message": (
                    "AUTO-DIFF produced structural analysis but no "
                    "machine-extracted tactic recommendation."
                ),
            }],
        )]

    def _diff_recommendations(
        self, diff_text: str, call_ready: set[str],
    ) -> list[dict]:
        tactic_prefixes = (
            "call", "swap", "seq", "wp", "sp", "inline", "proc",
            "byequiv", "byphoare", "conseq", "while", "rnd", "auto",
            "smt", "rewrite", "apply",
        )
        recs: list[dict] = []
        seen: set[str] = set()
        for idx, match in enumerate(re.finditer(r"`([^`]+)`", diff_text)):
            candidate = match.group(1).strip()
            if not candidate.startswith(tactic_prefixes):
                continue
            tactic = _normalize_plan_step(candidate)
            if not tactic or tactic in seen:
                continue
            seen.add(tactic)
            call_match = re.match(r"call\s+([A-Za-z_]\w*)\.", tactic)
            call_like = bool(re.match(r"e?call\b", tactic))
            verified = bool(call_match and call_match.group(1) in call_ready)
            needs_instantiation = _requires_action_instantiation(tactic)
            if verified:
                action_type = "runnable_tactic"
                confidence = "verified"
                epistemic_status = "daemon_probe_accepted"
            elif needs_instantiation:
                action_type = "strategy_hint"
                confidence = "medium"
                epistemic_status = "template_requires_instantiation"
            elif call_like:
                action_type = "strategy_hint"
                confidence = "medium"
                epistemic_status = "static_call_alignment_not_frontier_verified"
            else:
                action_type = "probe_tactic"
                confidence = "medium"
                epistemic_status = "static_alignment_candidate_uncertified_by_ec"
            recs.append({
                "id": f"auto_diff.{len(recs)}",
                "kind": "alignment_tactic",
                "producer": "AUTO-DIFF",
                "action": tactic,
                "why": (
                    "AUTO-DIFF found this tactic while comparing the "
                    "current programs/probability expressions. Unverified "
                    "call/ecall items are structural hints only; ProofIR or "
                    "a daemon probe must establish frontier readiness before "
                    "they become runnable."
                ),
                "action_type": action_type,
                "confidence": confidence,
                "preconditions": [
                    "proof_state.status == open",
                    "current goal still matches the AUTO-DIFF shape",
                ],
                "source_refs": [],
                "evidence_refs": ["raw.auto_diff_text"],
                "metadata": {
                    "daemon_ready": verified,
                    "epistemic_status": epistemic_status,
                    "requires_instantiation": needs_instantiation,
                    "text_offset": match.start(),
                },
            })
        return recs

    def _classify_and_diff(self, raw_goal: str) -> tuple[str, str]:
        """Dispatch by goal type, return (diff_text, shape_key) or
        ('', '') when nothing applicable."""
        from core.easycrypt.analysis.ec_goal_parser import parse_goal  # type: ignore
        from core.easycrypt.analysis.ec_pr_path_diff import (  # type: ignore
            eager_diff, probability_diff, program_alignment_diff,
        )
        info = parse_goal(raw_goal)
        if info.goal_type in ("pRHL", "equiv") and (info.left_stmts or info.right_stmts):
            shape_key = (
                "prhl:"
                + "|".join(s.get("text", "")
                           for s in (info.left_stmts or []))
                + "###"
                + "|".join(s.get("text", "")
                           for s in (info.right_stmts or []))
            )
            # Match local equivs to call sites so the alignment footer
            # can prefer `call LEMMA` (named equiv) over `call (_: Inv)`
            # (hand-craft invariant) when a proved correspondence
            # already exists.
            diff_equivs = self._match_call_equivs(info)
            diff_text = program_alignment_diff(
                info, call_equiv_candidates=diff_equivs,
            )
            return diff_text, shape_key
        if info.goal_type == "probability":
            return (
                probability_diff(info),
                "prob:" + (info.raw_text or "")[:400],
            )
        if info.goal_type == "eager":
            shape = (
                "eager:"
                + getattr(info, "eager_left_proc", "")
                + "~"
                + getattr(info, "eager_right_proc", "")
            )
            return eager_diff(info), shape
        return "", ""

    def _match_call_equivs(self, info) -> Optional[dict]:
        """Map call-site procedure names to local-equiv lemmas declared
        in the session's context file. None when no match found or the
        scan fails."""
        try:
            from core.easycrypt.session_goal_context import (  # type: ignore
                match_equivs_to_calls, scan_local_equiv_details,
            )
            ed = scan_local_equiv_details(self.session.context_file)
        except Exception:
            try:
                from core.easycrypt.session_goal_context import (  # type: ignore
                    match_equivs_to_calls, scan_local_equiv_details,
                )
                ed = scan_local_equiv_details(self.session.context_file)
            except Exception:
                return None
        try:
            if not ed:
                return None
            call_procs = list({
                s["procedure"]
                for s in (info.left_stmts + info.right_stmts)
                if s.get("type") == "CALL" and s.get("procedure")
            })
            if not call_procs:
                return None
            return match_equivs_to_calls(call_procs, ed) or None
        except Exception:
            return None

    def _abbreviate(self, diff_text: str) -> str:
        """Compress a large diff to header + first 5 + last 2 rows + a
        marker. Used when the active goal is over the size threshold —
        the agent reads the goal text directly to see the rest."""
        diff_lines = diff_text.splitlines()
        if len(diff_lines) <= 12:
            return diff_text
        head = diff_lines[:7]
        tail = diff_lines[-3:]
        return "\n".join(
            head + [
                f"  ... [abbreviated: {len(diff_lines) - 10} "
                f"intermediate rows hidden because goal is "
                f"large; see goal text directly] ..."
            ] + tail
        )

    def _annotate_call_ready(self, diff_text: str,
                             call_ready: set[str]) -> str:
        """Tag each `→ \\`call NAME\\`` line with ✓ when NAME is in
        the daemon-ready set, ⚠ otherwise. Other lines pass through
        unchanged."""
        call_re = re.compile(r"→\s*`call\s+([A-Za-z_]\w*)`")
        annotated = []
        for ln in diff_text.splitlines():
            m = call_re.search(ln)
            if not m:
                annotated.append(ln)
                continue
            nm = m.group(1)
            if nm in call_ready:
                annotated.append(
                    ln.rstrip() + "  ✓ daemon-ready at this state",
                )
            else:
                annotated.append(
                    ln.rstrip()
                    + "  ⚠ this SUGGESTION not daemon-ready "
                    "at current state (annotation refers to "
                    "the suggested lemma's applicability, NOT "
                    "to whatever tactic you just ran; see "
                    "alignment hint same line, or revert to "
                    "PRE-inline state)"
                )
        return "\n".join(annotated)


# ─── Layer-1 hint generators (consumed by HintDispatchPhase) ────────────

from core.easycrypt.hint_dispatch import (  # type: ignore
    Candidate,
    candidates_to_recommendations,
    dispatch_hints,
)


class _AbstractAdvCallGenerator:
    """Layer-1 generator for canonical-Inv `call` against abstract
    adversaries (modules declared via `declare module A <: T`).

    Covers the CPA-style shape that NAMED-equiv producers
    (`AUTO-PIVOT-CALL-READY`) cannot reach, since abstract module
    parameters have no `equiv` lemmas attached.
    """

    producer_name = "AUTO-ABSTRACT-ADV-CALL"
    marker = "[AUTO-ABSTRACT-ADV-CALL]"
    layer = 2

    def __init__(self, session):
        self.session = session
        self._cached_source: Optional[str] = None
        self._cached_source_path: Optional[Path] = None

    def applies_to_shape(self, goal_type: str) -> bool:
        return goal_type == "pRHL"

    def generate(self, ctx) -> list[Candidate]:
        if not ctx.active_goal:
            return []
        try:
            from core.easycrypt.analysis.ec_abstract_adv_hint import (  # type: ignore
                detect_and_propose,
            )
        except Exception:
            try:
                from core.easycrypt.analysis.ec_abstract_adv_hint import (  # type: ignore  # noqa: E501
                    detect_and_propose,
                )
            except Exception:
                return []
        source = self._read_source_text()
        if not source:
            return []
        calls, tactics = detect_and_propose(ctx.active_goal, source)
        if not calls or not tactics:
            return []
        modules_sorted = sorted({c.module for c in calls})
        why = (
            "Daemon accepted this canonical-invariant `call` tactic "
            "for the abstract adversary call site at the current "
            "pRHL goal."
        )
        return [
            Candidate(
                tactic=t,
                why=why,
                source_modules=tuple(modules_sorted),
                metadata={"abstract_modules": modules_sorted},
            )
            for t in tactics
        ]

    def _read_source_text(self) -> str:
        try:
            ctx_path = self.session.context_file
        except Exception:
            return ""
        if not ctx_path or not ctx_path.exists():
            return ""
        if (
            self._cached_source is not None
            and self._cached_source_path == ctx_path
        ):
            return self._cached_source
        try:
            self._cached_source = ctx_path.read_text(
                encoding="utf-8", errors="replace",
            )
            self._cached_source_path = ctx_path
        except Exception:
            self._cached_source = ""
        return self._cached_source or ""


class _SwapAlignGenerator:
    """Layer-1 generator for daemon-verified `swap{N} K M.` candidates
    on misaligned pRHL columns.

    Equivalent to `-align` fired automatically post-commit; the agent
    no longer has to invoke `-align` manually between steps.

    Emits two tiers, both daemon-verified by the dispatcher (only accepted
    candidates surface): (1) the statically-certified `result.swaps`; (2) Slice
    1B -- the CALL-crossing swaps the static scan conservatively dumped into
    `result.blocked_swaps`. The CALL barrier is a blanket conservatism, not an
    EC rejection, so probing those is how a hard reduction's CALL-crossing swap
    (the move it stalls on) surfaces as a verified fact.
    """

    producer_name = "AUTO-SWAP-ALIGN"
    marker = "[AUTO-SWAP-ALIGN]"
    layer = 2

    def __init__(self, session):
        self.session = session

    def applies_to_shape(self, goal_type: str) -> bool:
        return goal_type == "pRHL"

    def generate(self, ctx) -> list[Candidate]:
        if not ctx.active_goal:
            return []
        try:
            from core.easycrypt.analysis.swap_align import parse_prhl_goal  # type: ignore
        except Exception:
            try:
                from core.easycrypt.analysis.swap_align import (  # type: ignore  # noqa: E501
                    parse_prhl_goal,
                )
            except Exception:
                return []
        ctx_path = _session_context_file_path(self.session)
        try:
            result = parse_prhl_goal(ctx.active_goal, context_file=ctx_path)
        except Exception:
            return []
        if result is None:
            return []
        out: list[Candidate] = []
        seen: set[str] = set()

        def _emit(tactic: str, why: str) -> None:
            tac = (tactic or "").strip()
            if not tac:
                return
            # `compute_swap_plan` annotates clean swaps with a `(* move ... *)` rationale
            # comment. The emitted tactic must be a CLEAN runnable (the comment otherwise
            # appends a stray `.` and breaks the downstream `_SWAP_OFFSET` panel regex), so
            # strip it and fold the note into `why`.
            note = ""
            m = re.search(r"\(\*(.*?)\*\)", tac)
            if m:
                note = m.group(1).strip()
                tac = re.sub(r"\s*\(\*.*?\*\)\s*", "", tac).strip()
            if not tac:
                return
            if not tac.endswith("."):
                tac = tac + "."
            if tac in seen:
                return
            seen.add(tac)
            out.append(Candidate(tactic=tac, why=why + (f" ({note})" if note else "")))

        # Clean, statically-certified swaps first: they consume the dispatch probe
        # budget ahead of the conservative blocked candidates below.
        clean_why = (
            "Static alignment found this swap candidate and the "
            "daemon accepted it on the live pRHL goal."
        )
        for tactic in (getattr(result, "swaps", None) or []):
            _emit(tactic, clean_why)

        # Slice 1B: probe the CALL-crossing swaps the static scan conservatively BLOCKED.
        # `_has_dependency` dumps any swap crossing a CALL into `blocked_swaps` via a
        # BLANKET barrier ("adversary calls touch glob A implicitly") -- conservative
        # evidence, NOT an EC rejection, and exactly the move hard reductions stall on
        # (e.g. step3's `swap{1} 11 -9` crossing the adversary call). dispatch_hints
        # daemon-verifies every emitted candidate and keeps only ACCEPTED ones, so a
        # blocked candidate surfaces iff EC actually accepts it here; an EC-rejected one
        # is silently dropped. We restrict to the CALL barrier (data/output dependencies
        # are far more likely to be real rejections) and emit AFTER the clean swaps, so a
        # goal with no clean swaps at all (the common hard-reduction shape) spends the
        # whole probe budget unblocking the hard case.
        blocked_why = (
            "Static read/write scan conservatively BLOCKED this swap (it crosses a CALL "
            "-- a blanket barrier, not an EC rejection); the daemon accepted it on the "
            "live goal, so it is valid here."
        )
        for item in (getattr(result, "blocked_swaps", None) or []):
            if not isinstance(item, dict):
                continue
            for cand_key, blk_key in (
                ("left_candidate", "left_blocker"),
                ("right_candidate", "right_blocker"),
            ):
                if "crosses CALL" not in str(item.get(blk_key) or ""):
                    continue
                _emit(str(item.get(cand_key) or ""), blocked_why)
        return out

class _AsymSeqGenerator:
    """Layer-1 generator for asymmetric pRHL ``seq N M : <inv>.``.

    When LHS and RHS have unequal statement counts, one useful family of
    moves is ``seq N M`` under an explicit invariant tying the matched
    columns' state.  The exact split point is proof-state dependent, so this
    generator emits several candidate split points rather than presenting a
    single proof-shaped recipe.

    AUTO-DIFF already detects the asymmetry but emits the tactic with
    a literal ``<inv>`` placeholder, which the bucket router downgrades
    to ``strategy_hint``. The agent then has no concrete invariant to
    work from. This generator synthesizes a CONCRETE invariant from
    swap_align's column matches:

      - same-name vars on both sides → ``={var, ...}``
      - renamed-only vars matched by column → ``var_l{1} = var_r{2}``

    The synthesized tactics are daemon-probed. Daemon-accepted candidates
    surface as ``runnable_tactic``. Daemon-rejected candidates surface
    as ``strategy_hint`` via ``fallback_recommendation_for_rejected``
    — even an incomplete invariant is far more actionable than the
    ``<inv>`` placeholder, because the agent now has concrete shape +
    starting clauses to extend.
    """

    producer_name = "AUTO-ASYM-SEQ"
    marker = "[AUTO-ASYM-SEQ]"
    layer = 2

    def __init__(self, session):
        self.session = session

    def applies_to_shape(self, goal_type: str) -> bool:
        return goal_type == "pRHL"

    def generate(self, ctx) -> list[Candidate]:
        if not ctx.active_goal:
            return []
        proposals = self._build_proposals(ctx)
        if not proposals:
            return []
        out: list[Candidate] = []
        for proposal in proposals[:6]:
            why = (
                "Asymmetric pRHL split candidate "
                f"`{proposal.origin}` (LHS {proposal.left_n} stmts, "
                f"RHS {proposal.right_m}). Synthesized invariant from "
                f"{proposal.matched_pair_count} column-matches. "
                f"Coverage: {proposal.coverage}. "
                "Probe this split point; if the invariant is incomplete, "
                "extend it with call-invariant carry-over and renamed-state "
                "clauses not visible to swap_align."
            )
            coverage_note = proposal.coverage_note()
            if coverage_note:
                why += f" Live-fact note: {coverage_note}."
            out.append(Candidate(
                tactic=proposal.to_tactic(),
                why=why,
                metadata={
                    "left_n": proposal.left_n,
                    "right_m": proposal.right_m,
                    "matched_pair_count": proposal.matched_pair_count,
                    "synthesized_invariant": proposal.invariant,
                    "split_origin": proposal.origin,
                    "coverage": proposal.coverage,
                    "preserved_vars": list(proposal.preserved_vars),
                    "live_post_vars": list(proposal.live_post_vars),
                    "prefix_read_vars": list(proposal.prefix_read_vars),
                    "missing_live_post_vars": list(proposal.missing_live_post_vars),
                    "missing_prefix_read_vars": list(proposal.missing_prefix_read_vars),
                },
            ))
        return out

    def _build_proposals(self, ctx):
        try:
            from core.easycrypt.analysis.ec_asym_seq_hint import (  # type: ignore
                detect_and_propose_all,
            )
        except Exception:
            try:
                from core.easycrypt.analysis.ec_asym_seq_hint import (  # type: ignore  # noqa: E501
                    detect_and_propose_all,
                )
            except Exception:
                return []
        ctx_path = _session_context_file_path(self.session)
        try:
            return detect_and_propose_all(ctx.active_goal, context_file=ctx_path)
        except Exception:
            return []


# ─── HintDispatchPhase — runs Layer-1 generators via the dispatcher ─────

class HintDispatchPhase(CommitPhase):
    """Single CommitPhase that drives the Layer-1 hint dispatcher.

    Holds a list of ``HintGenerator`` instances and delegates
    goal-shape gating + Layer-2 daemon verification + Layer-3 rec
    shaping to ``hint_dispatch.dispatch_hints``. Adding a new shape
    generator is a one-line append here — no new Phase class, no
    duplicated daemon loop, no per-shape rec construction.

    Per-shape dedup is centralized: ``_seen_shapes`` stores
    ``(producer_name, goal-prefix)`` so the same goal isn't re-probed
    by the same generator across consecutive commits. Goal mutations
    naturally yield new prefixes and re-probe.
    """

    _PROBE_BUDGET_PER_GENERATOR = 6

    def __init__(self, session, generators: Optional[list] = None):
        self.session = session
        self._generators = list(generators or [])
        self._seen_shapes: set[tuple[str, str]] = set()

    def run(self, ctx) -> list[HookResult]:
        if not ctx.active_goal or not self._generators:
            return []
        # Centralized dedup: skip generators whose (producer, prefix)
        # we already probed at this exact goal shape.
        shape_prefix = ctx.active_goal[:300]
        active = [
            g for g in self._generators
            if (g.producer_name, shape_prefix) not in self._seen_shapes
        ]
        if not active:
            return []
        results = dispatch_hints(
            ctx,
            active,
            probe_budget_per_generator=self._PROBE_BUDGET_PER_GENERATOR,
        )
        out: list[HookResult] = []
        for r in results:
            self._seen_shapes.add((r.producer.producer_name, shape_prefix))
            recs = candidates_to_recommendations(r)
            if not recs:
                continue
            text_lines = [
                f"{r.producer.marker} daemon-verified candidates "
                "(all probed against the live goal):",
            ]
            for c in r.accepted:
                text_lines.append(f"  ✓ {c.tactic}")
            for c in r.rejected:
                text_lines.append(f"  ✗ {c.tactic}  [daemon rejected]")
            probe_evidence = []
            for rec in recs:
                ev_ref = rec["evidence_refs"][0] if rec["evidence_refs"] else ""
                probe_evidence.append({
                    "id": ev_ref,
                    "producer": "EasyCrypt daemon try_tactic",
                    "accepted": rec.get("action_type") == "runnable_tactic",
                    "tactic": rec["action"],
                })
            out.append(HookResult(
                text="\n".join(text_lines) + "\n",
                layer=r.producer.layer,
                kind="recommendation",
                recommendations=recs,
                evidence={"probe": probe_evidence},
            ))
        return out


def make_default_hint_dispatch_phase(session) -> HintDispatchPhase:
    """Construct the default ``HintDispatchPhase`` with all known
    Layer-1 generators registered. Call from ``Session.__init__``.

    To add a new generator: append it to the list below. No other
    change in the hook pipeline is required.
    """
    return HintDispatchPhase(session, generators=[
        _AbstractAdvCallGenerator(session),
        _SwapAlignGenerator(session),
        _AsymSeqGenerator(session),
    ])

