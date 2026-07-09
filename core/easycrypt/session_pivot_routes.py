"""Call-site route options and rewrite-probe inspection engines.

Extracted verbatim from PivotStrategyPhase (session_hook_phases.py) — the
2,900-line inspect-engine god-class. Each function's first parameter is
named ``self`` ON PURPOSE: it receives the PivotStrategyPhase instance
(for ``self.session`` and the small shared helpers that stay on the
class), so the bodies are byte-identical to the original methods and the
panel-invariance guarantee holds. De-self-ifying the signatures into
explicit params is a follow-up, not part of this carve.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Optional
from core.hooks.contract import CommitPhase, HookResult  # type: ignore


def try_call_suggest(self, raw_goal: str,
                      h: Optional[DaemonHandle]) -> Optional[HookResult]:
    if not raw_goal:
        return None
    is_prhl = (
        ("&1" in raw_goal and "&2" in raw_goal)
        or (" ~ " in raw_goal and "==>" in raw_goal)
    )
    pr_count = raw_goal.count("Pr[")
    has_pr_eq_only = pr_count >= 2 and "&1" not in raw_goal
    if not (is_prhl and not has_pr_eq_only):
        return None
    route = self._proof_ir_call_site_route()
    if route:
        return self._render_call_site_route_options(route, h)
    narrative = self.session._load_narrative()
    legacy_count = len([
        l for l in (narrative.get("lemma_catalog") or [])
        if l.get("role") == "oracle_equiv" and l.get("call_template")
    ])
    if legacy_count:
        return HookResult(
            text=(
                "\n[CALL-SITE-OPTIONS/LEGACY_NARRATIVE_REJECTED] "
                "The current call-site inspect found legacy narrative "
                f"call template(s) ({legacy_count}), but executable "
                "call options must come from ProofIR/current-frontier "
                "binding plus daemon verification. No runnable call "
                "option is surfaced from narrative text.\n"
            ),
            layer=3,
            kind="recommendation",
            recommendations=[],
            evidence={"context": [{
                "id": "context.call_site_options.legacy_narrative",
                "producer": "session._load_narrative",
                "legacy_template_count": legacy_count,
                "used_for_executable_options": False,
            }]},
            notes=[{
                "code": "call_site_options.legacy_narrative_rejected",
                "message": (
                    "Narrative call_template/invariant_sketch fields are "
                    "not executable authority for eval-clean call-site "
                    "options."
                ),
            }],
        )
    return HookResult(
        text=(
            "\n[CALL-SITE-OPTIONS/NO_ROUTE] The current pRHL goal looks "
            "call-site shaped, but ProofIR did not expose a current "
            "call_site_route. Use proof_frontier/align to inspect the "
            "program frontier before trying direct call tactics.\n"
        ),
        layer=3,
        kind="recommendation",
        recommendations=[],
        evidence={"context": [{
            "id": "context.call_site_options.no_route",
            "producer": "ProofIR.call_site_route",
            "route_available": False,
        }]},
        notes=[{
            "code": "call_site_options.no_route",
            "message": "No manager-owned call-site route is available.",
        }],
    )


def proof_ir_call_site_route(self) -> dict[str, Any]:
    try:
        from core.easycrypt.session_projection import (  # type: ignore
            projection_to_goal_info,
            read_proof_state_projection,
        )
        from core.easycrypt.analysis.ec_proof_ir import build_proof_ir  # type: ignore
    except Exception:
        try:
            from core.easycrypt.session_projection import (
                projection_to_goal_info,
                read_proof_state_projection,
            )
            from core.easycrypt.analysis.ec_proof_ir import build_proof_ir
        except Exception:
            return {}
    try:
        projection = read_proof_state_projection(
            self.session.dir,
            live_tool_name="pivot-call-site",
        )
        proof_state = projection_to_goal_info(projection)
        proof_ir = build_proof_ir(
            session_dir=self.session.dir,
            proof_state=proof_state,
            current_goal=projection.goal.to_dict(),
        )
        handles = (
            dict(dict(proof_ir.get("resources") or {}).get("handles") or {})
        )
        route = handles.get("call_site_route") or {}
        return dict(route) if isinstance(route, dict) else {}
    except Exception:
        return {}


def render_call_site_route_options(
    self,
    route: dict[str, Any],
    h: Optional[DaemonHandle],
) -> HookResult:
    state = str(route.get("state") or "call_site_route")
    templates = [
        item for item in (route.get("named_call_templates") or [])
        if isinstance(item, dict)
    ]
    named_handles = [
        item for item in (route.get("named_handles") or [])
        if isinstance(item, dict)
    ]
    candidates = self._call_site_candidate_tactics(templates)
    context_evidence = {
        "id": "context.call_site_route",
        "producer": "ProofIR.call_site_route",
        "state": state,
        "live_call_site_count": len(route.get("live_call_sites") or []),
        "named_handle_count": len(named_handles),
        "template_count": len(templates),
        "candidate_count": len(candidates),
        "frontier_blocker_count": len(route.get("frontier_blockers") or []),
    }
    if not candidates:
        return HookResult(
            text=(
                "\n[CALL-SITE-OPTIONS/CONTEXT_ONLY] ProofIR exposed a "
                f"call-site route (`{state}`), but no fully concrete call "
                "tactic template is currently available. Inspect the "
                "route's missing slots/frontier blockers before probing "
                "call tactics.\n"
            ),
            layer=3,
            kind="recommendation",
            recommendations=[],
            evidence={"context": [context_evidence]},
            notes=[{
                "code": "call_site_options.context_only",
                "message": (
                    "Current call-site facts are available, but no concrete "
                    "tactic template is ready for daemon verification."
                ),
            }],
        )
    if h is None:
        return HookResult(
            text=(
                "\n[CALL-SITE-OPTIONS/UNAVAILABLE] ProofIR exposed "
                f"{len(candidates)} concrete call-site candidate(s), but "
                "the EasyCrypt daemon is unavailable. No executable call "
                "option is shown until daemon verification accepts a "
                "candidate on the current goal.\n"
            ),
            layer=3,
            kind="recommendation",
            recommendations=[],
            evidence={"context": [context_evidence]},
            notes=[{
                "code": "call_site_options.daemon_unavailable",
                "message": (
                    "Call-site candidates are hidden until daemon "
                    "verification accepts them on the current goal."
                ),
            }],
            errors=[{
                "code": "call_site_options.daemon_unavailable",
                "message": "EasyCrypt daemon handle is unavailable.",
            }],
        )
    verified: list[dict[str, Any]] = []
    probe_evidence: list[dict[str, Any]] = []
    # Bound the verification scan to keep this inspect under the manager's
    # ~10 s latency budget: a probe is ~1.5 s of EC compute and does not
    # amortize, so cap the count and stop before the wall-clock deadline.
    import time as _time
    _probe_deadline = self._resolve_probe_deadline()
    # Static drop (no probe): a template with unresolved non-value (module /
    # proof / type) slots can't be filled by a bare `call`, so it would only
    # produce a guaranteed "cannot infer" failure — drop it rather than probe.
    candidates = [c for c in candidates
                  if not (c.get("unresolved_slots") or [])] or candidates
    _scan = candidates[:self._INSPECT_PROBE_CAP]
    _unprobed = max(0, len(candidates) - len(_scan))
    for idx, candidate in enumerate(_scan):
        if _time.monotonic() + self._PROBE_EST_S > _probe_deadline:
            _unprobed += len(_scan) - idx
            break
        tactic = str(candidate.get("tactic") or "").strip()
        ev_id = f"probe.call_site.{idx}"
        try:
            result = h.cli.try_tactic(h.dbe._session_id, tactic)
        except Exception as exc:
            probe_evidence.append({
                "id": ev_id,
                "producer": "ec_daemon.exception",
                "accepted": False,
                "tactic": tactic,
                "error_kind": type(exc).__name__,
                "error_message": str(exc),
            })
            continue
        accepted = bool(result.get("accepted")) and not bool(
            result.get("no_progress", False)
        )
        err = result.get("error") or {}
        error_kind = (
            str(err.get("kind") or "unknown")
            if isinstance(err, dict) else "unknown"
        )
        error_message = (
            str(err.get("message") or err.get("raw") or "")
            if isinstance(err, dict) else str(err or "")
        )
        probe_evidence.append({
            "id": ev_id,
            "producer": "ec_daemon.try_tactic",
            "accepted": accepted,
            "tactic": tactic,
            "error_kind": "" if accepted else error_kind,
            "error_message": "" if accepted else error_message,
        })
        if accepted:
            item = dict(candidate)
            item["evidence_id"] = ev_id
            verified.append(item)
    if not verified:
        first_error = next(
            (
                str(ev.get("error_message") or ev.get("error_kind") or "")
                for ev in probe_evidence
                if ev.get("accepted") is False
            ),
            "",
        )
        return HookResult(
            text=(
                "\n[CALL-SITE-OPTIONS/NO_VERIFIED_CALL] ProofIR exposed "
                f"{len(candidates)} concrete call-site candidate(s), but "
                "daemon verification accepted none on the current goal. "
                "No executable call option is surfaced.\n"
                + (f"  First verifier failure: {first_error}\n"
                   if first_error else "")
            ),
            layer=3,
            kind="recommendation",
            recommendations=[],
            evidence={"context": [context_evidence], "probe": probe_evidence},
            notes=[{
                "code": "call_site_options.no_verified_call",
                "message": (
                    "Concrete call-site candidates exist, but none passed "
                    "daemon verification."
                ),
            }],
            errors=[{
                "code": "call_site_options.no_verified_call",
                "message": first_error or "Daemon rejected every call candidate.",
            }],
        )
    out_lines = [
        "",
        "[CALL-SITE-OPTIONS/VERIFIED] ProofIR produced concrete call-site "
        "candidate(s), and the daemon accepted the option(s) below on the "
        "current goal.",
    ]
    recommendations: list[dict[str, Any]] = []
    for idx, candidate in enumerate(verified[:5], start=1):
        tactic = str(candidate.get("tactic") or "").strip()
        symbol = str(candidate.get("symbol") or "")
        out_lines.append("")
        out_lines.append(f"  Option {idx}: {symbol or 'call-site tactic'}")
        out_lines.append(
            "     manager intent: "
            + json.dumps({
                "intent": "commit_tactic",
                "payload": {"tactic": tactic},
            }, ensure_ascii=True)
        )
        ev_id = str(candidate.get("evidence_id") or f"probe.call_site.{idx - 1}")
        recommendations.append({
            "id": f"call_site_options.verified.{idx - 1}",
            "kind": "call_site_tactic",
            "producer": "ProofIR.call_site_route",
            "action": tactic,
            "why": (
                "ProofIR attached this tactic to the current call-site "
                "route and the daemon accepted it on the live goal."
            ),
            "action_type": "runnable_tactic",
            "confidence": "verified",
            "preconditions": [
                "proof_state.status == open",
                "current goal still exposes the same call frontier",
            ],
            "source_refs": [{
                "kind": "call_site_handle",
                "id": symbol,
                "details": {"status": candidate.get("status") or ""},
            }],
            "evidence_refs": [ev_id],
            "metadata": {
                "submit": {
                    "intent": "commit_tactic",
                    "payload": {"tactic": tactic},
                },
                "effect": (
                    "commits a daemon-verified call-site tactic; proof "
                    "state changes only if the agent submits the manager intent"
                ),
                "route_state": state,
                "symbol": symbol,
            },
        })
    out_lines.append("")
    out_lines.append(
        "  Read: these are executable call-site options, not narrative "
        "templates. Prefer them over hand-instantiating stale call hints."
    )
    return HookResult(
        text="\n".join(out_lines) + "\n",
        layer=3,
        kind="recommendation",
        recommendations=recommendations,
        evidence={"context": [context_evidence], "probe": probe_evidence},
        notes=[{
            "code": "call_site_options.daemon_verified",
            "message": (
                "Every surfaced call-site option was accepted by the "
                "daemon against the current goal."
            ),
        }],
    )


def call_site_candidate_tactics(
    templates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in templates:
        for key in ("direct_ecall_template", "tactic_shape"):
            tactic = str(item.get(key) or "").strip()
            if not tactic:
                continue
            if "<" in tactic or ">" in tactic or "..." in tactic:
                continue
            if not tactic.endswith("."):
                tactic += "."
            if tactic in seen:
                continue
            seen.add(tactic)
            out.append({
                "symbol": item.get("symbol"),
                "status": item.get("status"),
                "template_field": key,
                "tactic": tactic,
                "unresolved_slots": item.get("unresolved_non_value_slots") or [],
            })
    return out


def try_called_proc_body(self, raw_goal: str) -> Optional[HookResult]:
    """Surface the BODY of the procedure(s) called at this frontier.

    At a `call (_: <inv>)` over a compound game procedure (e.g.
    `CPA_game(...).main()` defined in an imported file), the agent must know
    what that procedure DOES — which oracles it calls, what state they touch —
    to choose the invariant. The structured view shows the goal but not the
    called body, so without this the agent reads the source file (and trips
    the IO policy). Extract the body statically, resolving functor aliases
    (`module CPA_game(A,O) = CCA_game(A,O).` -> `CCA_game.main`).
    """
    if not raw_goal or "<@" not in raw_goal:
        return None
    if not self._raw_goal_frontier_has_call(raw_goal):
        return None
    try:
        from core.easycrypt.analysis.ec_called_proc_body import (  # type: ignore
            called_module_proc, extract_called_proc_body)
    except Exception:
        try:
            from core.easycrypt.analysis.ec_called_proc_body import (  # type: ignore
                called_module_proc, extract_called_proc_body)
        except Exception:
            return None
    pairs: list[tuple[str, str]] = []
    for m in re.finditer(r"<@[^\n;]*", raw_goal):
        mp = called_module_proc(m.group(0))
        if mp and mp not in pairs:
            pairs.append(mp)
    if not pairs:
        return None
    try:
        from core.easycrypt.analysis.ec_relational_invariant import (  # type: ignore
            _relational_source_texts)
    except Exception:
        try:
            from core.easycrypt.analysis.ec_relational_invariant import (  # type: ignore
                _relational_source_texts)
        except Exception:
            return None
    try:
        texts = [(t, getattr(p, "name", str(p)))
                 for t, p, _k in _relational_source_texts(self.session.dir)]
    except Exception:
        return None
    if not texts:
        return None
    bodies: list[dict[str, Any]] = []
    for mod, proc in pairs[:3]:
        try:
            res = extract_called_proc_body(texts, mod, proc)
        except Exception:
            res = None
        if res:
            bodies.append(res)
    if not bodies:
        return None
    lines = [
        "\n[CALLED-PROCEDURE-BODY] Bodies of the procedure(s) called at this "
        "frontier, resolved statically from source (functor aliases followed). "
        "Use these to see which oracles/state each call touches, so your "
        "`call (_: <inv>)` invariant covers them — you do NOT need to read "
        "source files."]
    recs: list[dict[str, Any]] = []
    for b in bodies:
        chain = (" = ".join(b["alias_chain"])
                 if len(b.get("alias_chain") or []) > 1 else b["module"])
        lines.append(f"\n  {chain}.{b['proc']}  (from {b['source']}):")
        lines.extend("    " + ln for ln in b["body"].splitlines())
        if b.get("truncated"):
            lines.append("    (* … body truncated *)")
        recs.append({
            "id": f"called_proc_body.{b['module']}.{b['proc']}",
            "kind": "call_site",
            "producer": "ec_called_proc_body",
            "module": b["module"],
            "proc": b["proc"],
            "alias_chain": b.get("alias_chain"),
            "source": b["source"],
            "body": b["body"],
            "guarantee": (
                "statically extracted procedure body (functor aliases "
                "resolved); read-only context for choosing the call "
                "invariant — not a tactic"),
            "why": (
                "the call invariant must be preserved through every oracle/"
                "state this procedure touches; its body shows them"),
        })
    return HookResult(
        text="\n".join(lines) + "\n", layer=2, kind="recommendation",
        recommendations=recs,
        evidence={"context": [{
            "id": "called_proc_body.static",
            "producer": "ec_called_proc_body",
            "procedures": [f"{b['module']}.{b['proc']}" for b in bodies],
        }]})


def try_rewrite_probe(self, raw_goal: str,
                       h: Optional[DaemonHandle]) -> Optional[HookResult]:
    if not raw_goal or len(raw_goal) <= 20:
        return None
    # Skip when AUTO-BRIDGE-SUGGEST owns the shape
    pr_count = raw_goal.count("Pr[")
    is_bridge_shape = (
        2 <= pr_count <= 3
        and "&1" not in raw_goal
        and "&2" not in raw_goal
    )
    if is_bridge_shape:
        return None
    candidates = self._collect_rewrite_candidates(raw_goal)
    if not candidates:
        return HookResult(
            text=(
                "\n[REWRITE-CANDIDATES/NO_CANDIDATES] The rewrite "
                "compiler found no hypothesis/file-local rewrite or "
                "unfold candidates for the current goal.\n"
            ),
            layer=2,
            kind="recommendation",
            recommendations=[],
            evidence={"context": [{
                "id": "context.rewrite_candidates",
                "producer": "rewrite_candidate_collector",
                "candidate_count": 0,
            }]},
            notes=[{
                "code": "rewrite_candidates.no_candidates",
                "message": "No source-derived rewrite candidates were found.",
            }],
        )
    # Dedupe + cap
    seen: set[str] = set()
    deduped: list[tuple[str, str]] = []
    for kind, tac in candidates:
        if tac in seen:
            continue
        seen.add(tac)
        deduped.append((kind, tac))
    # A daemon probe is ~1.5 s of EC compute and does NOT amortize in a
    # batch, so cap the candidate set to keep this inspect under the
    # manager's ~10 s latency budget (batch_try cannot be interrupted
    # mid-call, so the bound has to be a count, not a wall-clock deadline).
    deduped = deduped[:self._INSPECT_PROBE_CAP]
    context_evidence = {
        "id": "context.rewrite_candidates",
        "producer": "rewrite_candidate_collector",
        "candidate_count": len(deduped),
        "sources": sorted({kind for kind, _ in deduped}),
    }
    if h is None or not hasattr(h.cli, "batch_try"):
        return HookResult(
            text=(
                "\n[REWRITE-CANDIDATES/UNAVAILABLE] The rewrite compiler "
                f"found {len(deduped)} candidate(s), but daemon batch "
                "verification is unavailable. No executable rewrite option "
                "is shown until EasyCrypt accepts a candidate on the "
                "current goal.\n"
            ),
            layer=2,
            kind="recommendation",
            recommendations=[],
            evidence={"context": [context_evidence]},
            notes=[{
                "code": "rewrite_candidates.daemon_unavailable",
                "message": (
                    "Rewrite candidates are hidden until daemon "
                    "verification accepts them on the current goal."
                ),
            }],
            errors=[{
                "code": "rewrite_candidates.daemon_unavailable",
                "message": "EasyCrypt daemon batch_try is unavailable.",
            }],
        )
    try:
        results_r = h.cli.batch_try(
            h.dbe._session_id, [c[1] for c in deduped],
        )
    except Exception as exc:
        return HookResult(
            text=(
                "\n[REWRITE-CANDIDATES/ERROR] Daemon rewrite verification "
                f"failed before returning results: {type(exc).__name__}: {exc}\n"
            ),
            layer=2,
            kind="recommendation",
            recommendations=[],
            evidence={"context": [context_evidence]},
            errors=[{
                "code": "rewrite_candidates.compiler_error",
                "message": f"{type(exc).__name__}: {exc}",
            }],
            debug={"exception_type": type(exc).__name__},
        )
    accepted: list[tuple[str, str, str]] = []
    probe_evidence: list[dict[str, Any]] = []
    for (kind, tac), res_r in zip(deduped, results_r or []):
        ev_id = f"probe.rewrite.{len(probe_evidence)}"
        ok = bool(res_r.get("accepted")) and not bool(
            res_r.get("no_progress", False)
        )
        err = res_r.get("error") or {}
        probe_evidence.append({
            "id": ev_id,
            "producer": "ec_daemon.batch_try",
            "accepted": ok,
            "tactic": tac,
            "candidate_kind": kind,
            "error_kind": (
                str(err.get("kind") or "unknown")
                if isinstance(err, dict) and not ok else ""
            ),
            "error_message": (
                str(err.get("message") or err.get("raw") or "")
                if isinstance(err, dict) and not ok else ""
            ),
        })
        if ok:
            accepted.append((kind, tac, ev_id))
    if not accepted:
        first_error = next(
            (
                str(ev.get("error_message") or ev.get("error_kind") or "")
                for ev in probe_evidence
                if ev.get("accepted") is False
            ),
            "",
        )
        return HookResult(
            text=(
                "\n[REWRITE-CANDIDATES/NO_VERIFIED_REWRITE] The rewrite "
                f"compiler checked {len(deduped)} candidate(s), but the "
                "daemon accepted none that changed the current goal. No "
                "executable rewrite option is surfaced.\n"
                + (f"  First verifier failure: {first_error}\n"
                   if first_error else "")
            ),
            layer=2,
            kind="recommendation",
            recommendations=[],
            evidence={"context": [context_evidence], "probe": probe_evidence},
            notes=[{
                "code": "rewrite_candidates.no_verified_rewrite",
                "message": (
                    "Candidates exist, but none passed daemon verification "
                    "with progress on the current goal."
                ),
            }],
            errors=[{
                "code": "rewrite_candidates.no_verified_rewrite",
                "message": first_error or "Daemon rejected every rewrite candidate.",
            }],
        )
    SOURCE_LABEL = {
        "hypothesis": "FROM-HYPOTHESIS",
        "file-lemma": "FROM-FILE-SCAN",
        "file-op-unfold": "FROM-FILE-SCAN",
    }
    out_lines = [
        "",
        "[REWRITE-CANDIDATES/VERIFIED] "
        "The manager compiled rewrite/unfold candidates and the daemon "
        "accepted the option(s) below with progress on the current goal. "
        "This verifies executability, not global proof usefulness.",
    ]
    by_kind: dict[str, list[str]] = {}
    for kind, tac, _ev_id in accepted[:10]:
        label = SOURCE_LABEL.get(kind, kind.upper())
        by_kind.setdefault(label, []).append(tac)
    priority = ["FROM-HYPOTHESIS", "FROM-FILE-SCAN"]
    for label in priority:
        tacs = by_kind.get(label, [])
        if not tacs:
            continue
        out_lines.append("")
        out_lines.append(f"  [{label}]")
        for tac in tacs:
            out_lines.append(
                "    • "
                + json.dumps({
                    "intent": "commit_tactic",
                    "payload": {"tactic": tac},
                }, ensure_ascii=True)
            )
    out_lines.append("")
    out_lines.append(
        "  Read: these are manager-owned proof intents. The daemon has "
        "only checked that the tactic runs and changes the goal; the agent "
        "still decides whether the rewrite direction fits the route."
    )
    recommendations: list[dict[str, Any]] = []
    for idx, (kind, tac, ev_id) in enumerate(accepted[:10]):
        recommendations.append({
            "id": f"rewrite_candidates.verified.{idx}",
            "kind": "rewrite_tactic",
            "producer": "rewrite_candidate_collector",
            "action": tac,
            "why": (
                "The candidate was derived from current proof context and "
                "accepted by the daemon with progress on the live goal."
            ),
            "action_type": "runnable_tactic",
            "confidence": "verified",
            "preconditions": [
                "proof_state.status == open",
                "current goal still contains the same rewrite target",
            ],
            "source_refs": [{
                "kind": kind,
                "id": tac,
            }],
            "evidence_refs": [ev_id],
            "metadata": {
                "submit": {
                    "intent": "commit_tactic",
                    "payload": {"tactic": tac},
                },
                "effect": (
                    "commits a daemon-verified rewrite/unfold tactic; "
                    "proof state changes only if the agent submits the "
                    "manager intent"
                ),
                "candidate_kind": kind,
            },
        })
    return HookResult(
        text="\n".join(out_lines) + "\n",
        layer=2,
        kind="recommendation",
        recommendations=recommendations,
        evidence={"context": [context_evidence], "probe": probe_evidence},
        notes=[{
            "code": "rewrite_candidates.daemon_verified",
            "message": (
                "Every surfaced rewrite candidate was accepted by the "
                "daemon and changed the current goal."
            ),
        }],
    )


def collect_rewrite_candidates(
        self, raw_goal: str) -> list[tuple[str, str]]:
    """Collect rewrite candidates from three non-adhoc channels:
    (A) hypothesis names with `=` in their type and (B) file-local
    lemma + op names from the frozen session context. No hardcoded
    catalog and no narrative closer hints: every candidate comes from
    current proof/session structure.
    """
    cands: list[tuple[str, str]] = []
    # Identifiers present in the goal — used to drop op-unfold candidates
    # whose operator does not occur here (a `rewrite /OP.` is a no-op, and a
    # wasted ~1.5 s probe, when OP is nowhere in the goal). Read the goal,
    # don't probe to learn it.
    goal_syms = set(re.findall(r"\b([a-zA-Z_][A-Za-z0-9_']*)\b", raw_goal))
    # Source A: hypothesis names from goal text
    for m in re.finditer(
        r"(?m)^\s*([a-zA-Z_][\w]*)\s*:\s+[^=\n]*=", raw_goal,
    ):
        hn = m.group(1)
        if hn in {"Pr", "res", "true", "false", "proof",
                  "qed", "axiom", "op", "lemma", "module",
                  "type"}:
            continue
        cands.append(("hypothesis", f"rewrite {hn}."))
    # Source B: file-level lemmas + ops from the frozen session context.
    source_path = ""
    try:
        ctx_file = getattr(self.session, "context_file", None)
        if ctx_file and Path(ctx_file).exists():
            source_path = str(ctx_file)
    except Exception:
        source_path = ""
    if not source_path:
        try:
            source_path, _ = self.session._get_daemon_meta()
        except Exception:
            source_path = ""
    if source_path:
        try:
            content = Path(source_path).read_text(encoding="utf-8")
            for m in re.finditer(
                r"(?m)^\s*(?:local\s+)?lemma\s+([a-zA-Z_][\w]*)",
                content,
            ):
                cands.append(("file-lemma", f"rewrite {m.group(1)}."))
            for m in re.finditer(
                r"(?m)^\s*(?:abbrev\s+|op\s+)([a-zA-Z_][\w]*)",
                content,
            ):
                if m.group(1) not in goal_syms:
                    continue   # op-unfold is a no-op unless OP is in the goal
                cands.append((
                    "file-op-unfold", f"rewrite /{m.group(1)}.",
                ))
        except Exception:
            pass
    return cands
