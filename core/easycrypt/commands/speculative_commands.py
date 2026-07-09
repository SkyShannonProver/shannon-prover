"""CLI handlers for speculative / strategy commands: -align,
-swap-search, -suggest-close, -call-subgoals, -inv-from-lemma,
-bad-trace.

These run analysis or daemon probes on the current state without
committing. Each is a thin wrapper around a backing module
(swap_align, swap_search, ec_suggest, ec_call_subgoals, etc.).

Phase 4: extracted from session_cli.main() to keep main() as pure
dispatch.
"""
from __future__ import annotations

import json as _json
import hashlib
import re
import sys
import time
from pathlib import Path

from core.easycrypt.session_tool_view import (  # type: ignore
    action_requires_instantiation as _action_requires_instantiation,
    emit_tool_or_legacy as _emit_tool_or_legacy,
)


# ─── -align ──────────────────────────────────────────────────────────────

def handle_align(session, args) -> int:
    """pRHL/equiv alignment helper. Refuses on hoare/phoare/ambient/
    probability goals (the swap_align backend produces garbage on
    single-side programs). Surfaces a tip about -bridge-lemmas when
    the goal is an EQUIV statement (before `proc`)."""
    from core.easycrypt.analysis.swap_align import analyze_and_suggest  # type: ignore
    from core.easycrypt.session_projection import read_proof_state_projection  # type: ignore

    if not session.curr.exists():
        sys.stderr.write(
            "No current goal state. Run -start and -next first.\n",
        )
        return 1
    projection = read_proof_state_projection(
        session.dir,
        live_tool_name="align",
    )
    if projection.status in ("candidate_closed", "verified"):
        view = _record_simple_tool_view(
            session, "align", projection,
            notes=["Proof is already complete; no alignment needed."],
        )
        _emit_tool_or_legacy(
            view,
            "[align] Proof is already complete; no alignment needed.\n",
            omit_raw_previews=True,
        )
        return 0
    if projection.consistency.errors:
        output = "[align] Inconsistent proof state; refusing alignment analysis.\n"
        for error in projection.consistency.errors[:5]:
            output += f"  - {error}\n"
        view = _record_simple_tool_view(
            session, "align", projection,
            errors=["Inconsistent proof state; refusing alignment analysis."],
            debug={"consistency_errors": projection.consistency.errors[:5]},
        )
        _emit_tool_or_legacy(view, output, omit_raw_previews=True)
        return 0
    state = session.read_state()
    raw = state.raw_for_goal_tools
    prefix = ""
    try:
        from core.easycrypt.analysis.ec_goal_parser import (  # type: ignore
            _extract_goal_body, classify_goal,
        )
        import re as _re
        goal_type = classify_goal(raw)
        body = _extract_goal_body(raw)
        has_equiv_stmt = (
            goal_type == "equiv"
            or bool(_re.search(r"equiv\s*\[", body))
        )
        if goal_type not in ("pRHL", "equiv") and not has_equiv_stmt:
            output = (
                f"[align] NOT APPLICABLE: goal_type={goal_type}. "
                "-align is a pRHL/equiv tool — it analyzes the two "
                "programs (LHS ~ RHS) of an equiv judgment for swap "
                "alignment + wp simulation. The current goal is "
                f"{goal_type}, which has no two-program structure. "
                "Use `-goal-info` for tactic suggestions on this "
                "goal type, or run a pRHL-opening tactic "
                "(byequiv / byphoare with conseq) first.\n",
            )
            output = "".join(output)
            view = _record_simple_tool_view(
                session, "align", projection,
                notes=[output.strip()],
                debug={"legacy_text": output},
            )
            _emit_tool_or_legacy(view, output, omit_raw_previews=True)
            return 0
        if has_equiv_stmt:
            prefix = (
                "[align] NOTE: Goal contains an EQUIV statement "
                "(before 'proc').\n"
                "  -align works AFTER 'proc; inline *', but inline "
                "* on a while-loop\n"
                "  sampling procedure (e.g. rejection sampling) "
                "would produce an\n"
                "  unmanageable unrolled form.\n"
                "  Run -bridge-lemmas FIRST to check for bridge "
                "equiv lemmas that can\n"
                "  be composed via transitivity without opening "
                "the program at all.\n"
                "  If no bridge lemmas are found, then 'proc.' "
                "(without inline *)\n"
                "  followed by -align is appropriate.\n\n",
            )
            prefix = "".join(prefix)
    except Exception:
        pass

    ctx = None
    for f in session.dir.glob("extracted_*.ec"):
        ctx = f
        break
    if ctx is None and (session.dir / "context.ec").exists():
        ctx = session.dir / "context.ec"
    analysis = analyze_and_suggest(raw, context_file=ctx)
    output = prefix + analysis
    view = _record_simple_tool_view(
        session, "align", projection,
        recommendations=_recommendations_from_tactic_lines(
            "align", "alignment_tactic", output,
            producer="align",
            why=(
                "Static realignment frame. The source position is mechanical; "
                "the offset is route-dependent. Fill the offset that lands the "
                "next sample/rnd coupling target, then probe that concrete swap."
            ),
            action_type="strategy_hint",
            metadata={
                "epistemic_status": "route_dependent_swap_frame",
                "state_changed": False,
                "recommended_probe_tool": "try_after_filling_offset",
            },
        ),
        guidance=_align_guidance_from_output(output),
        evidence={
            "deterministic": [{
                "id": "deterministic.align",
                "producer": "swap_align.analyze_and_suggest",
                "has_context_file": ctx is not None,
                "epistemic_status": "static_analysis",
            }],
            "epistemic": _align_epistemic_evidence(output),
            "raw": [{
                "id": "raw.align_text",
                "format": "legacy_text",
                "preview": output[:1000],
            }],
        },
        notes=(
            [] if "STATICALLY CERTIFIED SWAP FRAMES" in output
            else [output.splitlines()[0] if output.splitlines() else ""]
        ),
        debug={"legacy_text": output[:4000]},
    )
    _emit_tool_or_legacy(view, output, omit_raw_previews=True)
    return 0


# ─── -swap-search ────────────────────────────────────────────────────────

def handle_swap_search(session, args) -> int:
    from core.easycrypt.swap_search import search_swaps  # type: ignore
    from core.easycrypt.session_projection import read_proof_state_projection  # type: ignore

    if not session.curr.exists():
        sys.stderr.write(
            "No current goal state. Run -start and -next first.\n",
        )
        return 1
    projection = read_proof_state_projection(
        session.dir,
        live_tool_name="swap-search",
    )
    result = search_swaps(
        str(session.dir), max_attempts=args.max_swap_attempts,
    )
    _record_swap_search_tool_view(session, projection, result)
    if result.success:
        if result.hint and result.attempts == 0 and not result.accepted_swaps:
            sys.stdout.write(f"[swap-search] {result.hint}\n")
            return 0
        sys.stdout.write(
            f"[swap-search] Aligned in {result.attempts} attempts:\n",
        )
        for s in result.accepted_swaps:
            sys.stdout.write(f"  {s}\n")
        if result.hint:
            sys.stdout.write(f"  {result.hint}\n")
        if session.curr.exists():
            raw = session.read_state().raw_for_goal_tools
            if raw:
                snippet = "\n".join(raw.strip().split("\n")[:20])
                sys.stdout.write(f"\n{snippet}\n")
    elif result.hint:
        # Eager goal or other structured hint — display prominently
        sys.stdout.write(f"[swap-search] {result.hint}\n")
        if result.hint_tactics:
            sys.stdout.write("  Suggested next steps:\n")
            for t in result.hint_tactics:
                sys.stdout.write(f"    {t}\n")
            sys.stdout.write(
                "  After applying one of these, re-run -swap-search "
                "to align the resulting pRHL goal.\n",
            )
    else:
        sys.stdout.write(
            f"[swap-search] Could not fully align after "
            f"{result.attempts} attempts.\n",
        )
        if result.accepted_swaps:
            sys.stdout.write(
                f"  Partial progress ({len(result.accepted_swaps)} "
                f"swaps):\n",
            )
            for s in result.accepted_swaps:
                sys.stdout.write(f"    {s}\n")
        sys.stdout.write(
            f"  {result.remaining_misaligned} pairs still "
            f"misaligned.\n",
        )
        if result.error:
            sys.stdout.write(f"  {result.error}\n")
    return 0 if result.success else 1


# ─── -suggest-close ──────────────────────────────────────────────────────

def handle_suggest_close(session, args) -> int:
    from core.easycrypt.ec_suggest import suggest_from_session  # type: ignore
    from core.easycrypt.session_projection import read_proof_state_projection  # type: ignore

    if not session.curr.exists():
        sys.stderr.write(
            "No current goal state. Run -start and -next first.\n",
        )
        return 1
    projection = read_proof_state_projection(
        session.dir,
        live_tool_name="suggest-close",
    )
    search_dirs = [Path(args.ec_src)]
    for d in session._include_dirs:
        p = Path(d)
        if p.is_dir() and p not in search_dirs:
            search_dirs.append(p)
    output = suggest_from_session(session.dir, search_dirs)
    _record_simple_tool_view(
        session, "suggest-close", projection,
        recommendations=_recommendations_from_tactic_lines(
            "suggest_close", "closing_tactic", output,
            producer="suggest-close",
            why="The closing-tactic analyzer suggested this tactic.",
            action_type="probe_tactic",
            metadata={
                "epistemic_status": "static_candidate_uncertified_by_ec",
                "state_changed": False,
                "recommended_probe_tool": "try",
                "cost": "cheap",
            },
        ),
        guidance=_suggest_close_guidance_from_output(output),
        evidence={
            "deterministic": [{
                "id": "deterministic.suggest_close",
                "producer": "ec_suggest.suggest_from_session",
                "search_dirs": [str(p) for p in search_dirs],
            }],
            "epistemic": _suggest_close_epistemic_evidence(output),
            "raw": [{
                "id": "raw.suggest_close_text",
                "format": "legacy_text",
                "preview": output[:1000],
            }],
        },
        notes=[] if "Suggested tactics" in output else [output.strip()],
        debug={"legacy_text": output[:4000]},
    )
    sys.stdout.write(output)
    return 0


# ─── -pivot-inspect ──────────────────────────────────────────────────────

def handle_pivot_inspect(session, args) -> int:
    """Run explicit pivot/call-site inspections.

    Commit hooks intentionally keep the AUTO-PIVOT family cheap.  This command
    is the read-only opt-in path for the expensive daemon-backed variants.
    """
    if not session.curr.exists():
        sys.stderr.write(
            "No current goal state. Run -start and -next first.\n",
        )
        return 1
    mode = str(getattr(args, "pivot_inspect", "") or "context")
    mode = mode.strip().replace("-", "_")
    from core.easycrypt.session_hook_phases import PivotStrategyPhase  # type: ignore

    ctx = _pivot_hook_context(session)
    phase = PivotStrategyPhase(session)
    results = phase.inspect(ctx, mode)
    text = "\n".join(
        str(getattr(result, "text", "") or "").strip()
        for result in results
        if str(getattr(result, "text", "") or "").strip()
    )
    status = "available" if results else "no_matching_context"
    view = _record_pivot_tool_view(session, mode, results, text, status)
    sys.stdout.write(_json.dumps(
        {
            "schema_version": 1,
            "kind": "pivot_inspect_result",
            "topic": _pivot_topic_for_mode(mode),
            "status": status,
            "ok": True,
            "effect": "read-only; proof state unchanged",
            "cost": _pivot_cost_for_mode(mode),
            "summary": _pivot_summary_for_mode(mode, status, results),
            "observations": _pivot_observations(results),
            "tool_view": view or {},
        },
        indent=2,
        sort_keys=True,
    ) + "\n")
    return 0


def _pivot_hook_context(session):
    from core.easycrypt.session_hooks import CommitHookContext  # type: ignore
    raw_curr = session.curr.read_text(encoding="utf-8", errors="replace")
    try:
        active_goal, curr_count = session.get_active_goal_block()
    except Exception:
        try:
            active_goal = session.get_active_goal_output()
        except Exception:
            active_goal = raw_curr
        curr_count = 0
    try:
        raw_prev = session.prev.read_text(encoding="utf-8", errors="replace")
    except Exception:
        raw_prev = ""
    return CommitHookContext(
        session_dir=session.dir,
        trimmed="",
        has_new_error=False,
        no_progress=False,
        prev_count=0,
        curr_count=int(curr_count or 0),
        active_goal=active_goal or raw_curr,
        raw_curr=raw_curr,
        raw_prev=raw_prev,
        _daemon_setup=session._setup_daemon_for_hooks,
    )


def _record_pivot_tool_view(session, mode: str, results: list, text: str, status: str):
    from core.easycrypt.session_projection import read_proof_state_projection  # type: ignore
    projection = read_proof_state_projection(
        session.dir,
        live_tool_name="pivot-inspect",
    )
    recommendations = []
    notes = []
    errors = []
    evidence: dict[str, list[dict]] = {}
    for result in results:
        recommendations.extend(list(getattr(result, "recommendations", None) or []))
        notes.extend(list(getattr(result, "notes", None) or []))
        errors.extend(list(getattr(result, "errors", None) or []))
        for bucket, items in dict(getattr(result, "evidence", None) or {}).items():
            # Evidence buckets are list[dict]. This view aggregates results from
            # several co-running producers (e.g. glob + relational skeletons on
            # call_invariant_skeleton); a single producer emitting a malformed
            # bucket (scalar/dict instead of a list) must not crash a read-only
            # inspect, so skip anything that is not a list/tuple of items.
            if not isinstance(items, (list, tuple)):
                continue
            evidence.setdefault(str(bucket), []).extend(
                item for item in items if isinstance(item, dict)
            )
    evidence.setdefault("raw", []).append({
        "id": f"raw.pivot_{mode}_text",
        "format": "legacy_text",
        "preview": text[:1200],
    })
    view = _record_simple_tool_view(
        session,
        f"pivot-{mode.replace('_', '-')}",
        projection,
        recommendations=recommendations,
        guidance={
            "status": status,
            "topic": _pivot_topic_for_mode(mode),
            "cost": _pivot_cost_for_mode(mode),
            "effect": "read-only; proof state unchanged",
            "summary": _pivot_summary_for_mode(mode, status, results),
        },
        evidence=evidence,
        notes=notes,
        errors=errors,
        debug={"legacy_text": text[:5000], "mode": mode},
    )
    _record_verified_route_options(
        session,
        mode=mode,
        topic=_pivot_topic_for_mode(mode),
        recommendations=recommendations,
        evidence=evidence,
    )
    return view


def _pivot_topic_for_mode(mode: str) -> str:
    return {
        "context": "pivot_context",
        "verified": "verified_pivot_options",
        "call_site": "call_site_options",
        "bridge": "pr_bridge_routes",
        "rewrite": "rewrite_candidates",
        "call_invariant_skeleton": "call_invariant_skeleton",
    }.get(mode, "pivot_context")


def _pivot_cost_for_mode(mode: str) -> str:
    return {
        "context": "cheap",
        "verified": "slow; daemon probes candidate tactics",
        "call_site": "medium-to-slow; daemon probes call-site candidates",
        "bridge": "slow; daemon probes bridge chains",
        "rewrite": "slow; daemon batch-probes rewrite candidates",
    }.get(mode, "cheap")


def _pivot_summary_for_mode(mode: str, status: str, results: list) -> str:
    if status != "available":
        return "No matching context was found for the current goal."
    count = sum(
        len(getattr(result, "recommendations", None) or [])
        for result in results
    )
    return {
        "context": "Static pivot/call-site context for route selection.",
        "verified": "Daemon-verified pivot tactics for the current goal.",
        "call_site": "Call-site/oracle-equivalence context for the current frontier.",
        "bridge": "Daemon-checked Pr bridge context for the current equality.",
        "rewrite": "Daemon-checked rewrite candidates that change the current goal.",
    }.get(mode, "Pivot context for the current goal.") + (
        f" {count} structured item(s)." if count else ""
    )


def _pivot_observations(results: list) -> list[dict]:
    observations: list[dict] = []
    for result in results:
        for rec in list(getattr(result, "recommendations", None) or [])[:5]:
            if not isinstance(rec, dict):
                continue
            metadata = dict(rec.get("metadata") or {})
            observations.append({
                "candidate": str(rec.get("action") or ""),
                "producer": str(rec.get("producer") or ""),
                "kind": str(rec.get("kind") or ""),
                "confidence": str(rec.get("confidence") or ""),
                "why": str(rec.get("why") or ""),
                "effect": (
                    metadata.get("effect")
                    or "read-only context; proof state unchanged"
                ),
                "submit": metadata.get("submit"),
                "bindings": metadata.get("bindings"),
            })
    return [obs for obs in observations if any(obs.values())][:6]


def _record_verified_route_options(
    session,
    *,
    mode: str,
    topic: str,
    recommendations: list[dict],
    evidence: dict[str, list[dict]],
) -> None:
    records = _verified_route_option_records(
        mode=mode,
        topic=topic,
        recommendations=recommendations,
        evidence=evidence,
    )
    if not records:
        return
    try:
        out_dir = Path(session.dir) / "route_options"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "verified_route_options.jsonl"
        with out_path.open("a", encoding="utf-8") as handle:
            for record in records:
                handle.write(_json.dumps(record, sort_keys=True) + "\n")
    except Exception:
        return


def _verified_route_option_records(
    *,
    mode: str,
    topic: str,
    recommendations: list[dict],
    evidence: dict[str, list[dict]],
) -> list[dict]:
    probe_by_id = {
        str(item.get("id") or ""): item
        for item in (evidence.get("probe") or [])
        if isinstance(item, dict)
    }
    context = [
        item for item in (evidence.get("context") or [])
        if isinstance(item, dict)
    ]
    out: list[dict] = []
    for rec in recommendations:
        if not isinstance(rec, dict):
            continue
        metadata = dict(rec.get("metadata") or {})
        submit = metadata.get("submit")
        if (
            rec.get("confidence") != "verified"
            or rec.get("action_type") != "runnable_tactic"
            or not isinstance(submit, dict)
        ):
            continue
        tactic = str(
            dict(submit.get("payload") or {}).get("tactic")
            or rec.get("action")
            or ""
        ).strip()
        if not tactic:
            continue
        evidence_refs = [
            str(ref) for ref in (rec.get("evidence_refs") or []) if str(ref)
        ]
        verification = [
            probe_by_id[ref] for ref in evidence_refs if ref in probe_by_id
        ]
        digest_source = _json.dumps({
            "topic": topic,
            "producer": rec.get("producer"),
            "tactic": tactic,
            "evidence_refs": evidence_refs,
        }, sort_keys=True)
        option_id = hashlib.sha256(
            digest_source.encode("utf-8")
        ).hexdigest()[:16]
        out.append({
            "kind": "verified_route_option",
            "schema_version": 1,
            "option_id": f"{topic}.{option_id}",
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "topic": topic,
            "mode": mode,
            "producer": rec.get("producer") or "",
            "recommendation_id": rec.get("id") or "",
            "semantic_objective": rec.get("why") or "",
            "confidence": "verified",
            "submit": submit,
            "tactic_chain": metadata.get("chain") or [tactic],
            "bindings": metadata.get("bindings") or {},
            "preconditions": rec.get("preconditions") or [],
            "source_refs": rec.get("source_refs") or [],
            "evidence_refs": evidence_refs,
            "verification_evidence": verification,
            "context_evidence": context[:3],
            "metadata": {
                key: value
                for key, value in metadata.items()
                if key not in {"submit"}
            },
        })
    return out


# ─── -call-subgoals ──────────────────────────────────────────────────────

def handle_call_subgoals(session, args) -> int:
    if args.command is None:
        sys.stderr.write(
            "Usage: -call-subgoals -c '<invariant body>'\n"
            "Example: -call-subgoals -c "
            "'inv X.m{1} Y.m{2} /\\ ={glob A} /\\ !M.bad{2}'\n",
        )
        return 2
    from core.easycrypt.analysis.ec_call_subgoals import preview_from_session  # type: ignore
    sys.stdout.write(preview_from_session(session.dir, args.command))
    return 0


# ─── -inv-from-lemma ─────────────────────────────────────────────────────

def handle_inv_from_lemma(session, args) -> int:
    from core.easycrypt.session_projection import read_proof_state_projection  # type: ignore
    from core.easycrypt.ec_inv_from_lemma import (  # type: ignore
        extract_from_context_file,
    )
    output = extract_from_context_file(session.dir, args.inv_from_lemma)
    try:
        projection = read_proof_state_projection(
            session.dir,
            live_tool_name="inv-from-lemma",
        )
        _record_simple_tool_view(
            session,
            "inv-from-lemma",
            projection,
            recommendations=_inv_from_lemma_recommendations(
                args.inv_from_lemma,
                output,
            ),
            evidence={
                "context": [{
                    "id": "context.inv_from_lemma",
                    "producer": "ec_inv_from_lemma.extract_from_context_file",
                    "lemma": args.inv_from_lemma,
                }],
                "epistemic": _inv_from_lemma_epistemic_evidence(output),
                "raw": [{
                    "id": "raw.inv_from_lemma_text",
                    "format": "legacy_text",
                    "preview": output[:1000],
                }],
            },
            notes=[] if "Ready-to-use call template" in output else [output.strip()],
            debug={"legacy_text": output[:4000]},
        )
    except Exception:
        pass
    sys.stdout.write(output)
    return 0


def _inv_from_lemma_recommendations(lemma_name: str, output: str) -> list[dict]:
    if "Ready-to-use call template" not in output:
        return []
    lines = output.splitlines()
    try:
        start = next(
            idx for idx, line in enumerate(lines)
            if "Ready-to-use call template" in line
        )
    except StopIteration:
        return []
    template_lines = []
    for line in lines[start + 1:]:
        if line.strip():
            template_lines.append(line.rstrip())
    action = "\n".join(template_lines).strip()
    if not action:
        return []
    requires_instantiation = _action_requires_instantiation(action)
    return [{
        "id": "inv_from_lemma.call_template",
        "kind": "call_invariant_template",
        "producer": "inv-from-lemma",
        "action": action,
        "why": (
            f"The invariant was extracted from the precondition of equiv "
            f"lemma `{lemma_name}`."
        ),
        "action_type": "strategy_hint" if requires_instantiation else "probe_tactic",
        "confidence": "medium",
        "preconditions": [
            "proof_state.status == open",
            "current call site still matches the source equiv lemma",
        ],
        "source_refs": [{"kind": "lemma", "id": lemma_name}],
        "evidence_refs": ["context.inv_from_lemma", "raw.inv_from_lemma_text"],
        "metadata": {
            "lemma": lemma_name,
            "epistemic_status": (
                "template_requires_instantiation"
                if requires_instantiation
                else "context_extracted_candidate_uncertified_by_ec"
            ),
            "requires_instantiation": requires_instantiation,
            "state_changed": False,
            "recommended_probe_tool": "try",
        },
    }]


def _inv_from_lemma_epistemic_evidence(output: str) -> list[dict]:
    if "Ready-to-use call template" in output:
        return [{
            "id": "epistemic.inv_from_lemma.context_extraction",
            "status": "context_extracted_candidate_uncertified_by_ec",
            "meaning": (
                "The call invariant was extracted deterministically from a "
                "named equiv lemma in the loaded context."
            ),
            "not_meaning": "EasyCrypt has not verified the call tactic here.",
        }]
    return [{
        "id": "epistemic.inv_from_lemma.no_template",
        "status": "no_context_template",
        "meaning": "No call invariant template was extracted from the lemma.",
    }]


# ─── -bad-trace ──────────────────────────────────────────────────────────

def handle_bad_trace(session, args) -> int:
    from core.easycrypt.ec_bad_trace import trace_from_session  # type: ignore
    sys.stdout.write(
        trace_from_session(session.dir, args.bad_trace_module),
    )
    return 0


def _record_simple_tool_view(
    session,
    tool: str,
    projection,
    *,
    recommendations=None,
    guidance=None,
    evidence=None,
    notes=None,
    errors=None,
    debug=None,
) -> dict | None:
    from core.easycrypt.session_projection import projection_to_goal_info  # type: ignore
    from core.easycrypt.session_tool_view import record_tool_view, tool_view_from_projection  # type: ignore
    try:
        view = tool_view_from_projection(
            tool=tool,
            proof_state=projection_to_goal_info(projection),
            recommendations=recommendations or [],
            guidance=guidance or {},
            evidence=evidence or {},
            notes=[n for n in (notes or []) if n],
            errors=[e for e in (errors or []) if e],
            debug=debug or {},
        )
        record_tool_view(session, view)
        return view
    except Exception:
        return None


_SWAP_WITH_OFFSET = re.compile(
    r"^(swap(?:\{[12]\})?\s+(?:\[\d+\.\.\d+\]|\d+))\s+(-?\d+)\s*\.?\s*$"
)


def _swap_frame_from_tactic(tactic: str) -> tuple[str, str]:
    """Return (frame, concrete) for route-dependent swap offsets."""
    match = _SWAP_WITH_OFFSET.match(tactic.strip())
    if not match:
        return "", ""
    return f"{match.group(1)} <offset>.", tactic.strip()


def _recommendations_from_tactic_lines(
    prefix: str,
    kind: str,
    text: str,
    *,
    producer: str,
    why: str,
    action_type: str = "runnable_tactic",
    confidence: str = "medium",
    metadata: dict | None = None,
) -> list[dict]:
    recs: list[dict] = []
    for line in text.splitlines():
        stripped = line.strip()
        tactic = ""
        numbered = re.match(r"^\d+\.\s+(.+)$", stripped)
        if numbered:
            tactic = numbered.group(1).strip()
        elif re.search(r"\bswap\{[12]\}\s+", stripped):
            if stripped.startswith("candidate:") or "blocked_by:" in stripped:
                continue
            tactic = stripped.split("(*", 1)[0].strip()
        if not tactic:
            continue
        tactic = tactic.split("(*", 1)[0].strip()
        if not tactic:
            continue
        if not tactic.endswith("."):
            tactic += "."
        rec_metadata = dict(metadata or {})
        is_route_dependent_swap_frame = False
        if kind == "alignment_tactic":
            frame, concrete = _swap_frame_from_tactic(tactic)
            if frame:
                tactic = frame
                is_route_dependent_swap_frame = True
                rec_metadata["concrete_static_candidate"] = concrete
                rec_metadata["offset_policy"] = "route_dependent"
                rec_metadata["not_unique"] = True
                rec_metadata.setdefault(
                    "route_selection_note",
                    (
                        "Many offsets may be EasyCrypt-valid; the proof route "
                        "must choose the offset that exposes the next coupling target."
                    ),
                )
        requires_instantiation = (
            False
            if is_route_dependent_swap_frame
            else _action_requires_instantiation(tactic)
        )
        rec_action_type = (
            "strategy_hint"
            if requires_instantiation or is_route_dependent_swap_frame
            else action_type
        )
        if requires_instantiation:
            rec_metadata["requires_instantiation"] = True
            rec_metadata["original_action_type"] = action_type
            rec_metadata.setdefault(
                "epistemic_status",
                "template_requires_instantiation",
            )
        recs.append({
            "id": f"{prefix}.{len(recs)}",
            "kind": kind,
            "producer": producer,
            "action": tactic,
            "why": why,
            "action_type": rec_action_type,
            "confidence": confidence,
            "preconditions": [
                "proof_state.status == open",
                "current goal still matches the analyzed shape",
            ],
            "source_refs": [],
            "evidence_refs": [f"raw.{prefix}_text"],
            "metadata": rec_metadata,
        })
    return recs


def _suggest_close_epistemic_evidence(output: str) -> list[dict]:
    if "Suggested tactics" in output:
        return [{
            "id": "epistemic.suggest_close.static_candidates",
            "status": "static_candidate_uncertified_by_ec",
            "meaning": (
                "The analyzer matched current goal text to closing tactic forms."
            ),
            "not_meaning": "EasyCrypt has not verified these tactics.",
        }]
    if "Goal still contains samples" in output:
        return [{
            "id": "epistemic.suggest_close.not_program_free",
            "status": "not_applicable_current_goal",
            "meaning": "The current goal still has program statements.",
            "not_meaning": "No proof exists; use structural tactics first.",
        }]
    return [{
        "id": "epistemic.suggest_close.no_candidate",
        "status": "no_static_candidate",
        "meaning": "The analyzer did not emit closing tactics.",
    }]


def _suggest_close_guidance_from_output(output: str) -> dict:
    if "Suggested tactics" in output:
        return {
            "primary_action": "probe",
            "epistemic_status": "static_analysis",
            "state_changed": False,
            "action_semantics": (
                "Probe suggested closing tactics with -try before committing."
            ),
        }
    return {
        "primary_action": "inspect_or_continue",
        "epistemic_status": "static_analysis",
        "state_changed": False,
    }


def _align_epistemic_evidence(output: str) -> list[dict]:
    evidence: list[dict] = []
    if "STATICALLY CERTIFIED SWAP FRAMES" in output:
        evidence.append({
            "id": "epistemic.align.static_candidate",
            "status": "static_candidate_uncertified_by_ec",
            "meaning": (
                "Static read/write scan found a source statement that can be "
                "used for realignment."
            ),
            "not_meaning": (
                "The shown offset is not unique and is not a proof-route "
                "decision; EasyCrypt may accept many offsets."
            ),
        })
    if "STATICALLY BLOCKED / UNCERTIFIED CANDIDATES" in output:
        evidence.append({
            "id": "epistemic.align.static_blocked",
            "status": "static_blocked_uncertified",
            "meaning": (
                "The analyzer found a conservative static barrier such as "
                "a CALL or variable dependency."
            ),
            "not_meaning": (
                "This is not an EasyCrypt rejection and does not prove the "
                "candidate is semantically impossible."
            ),
        })
    if "NO STATICALLY CERTIFIED SWAPS" in output:
        evidence.append({
            "id": "epistemic.align.no_static_certification",
            "status": "no_static_certification",
            "meaning": "No swap was certified by the static analyzer.",
            "not_meaning": "No valid swap exists.",
        })
    if not evidence:
        evidence.append({
            "id": "epistemic.align.no_action_needed",
            "status": "no_alignment_action",
            "meaning": "The alignment tool did not identify a swap action.",
        })
    return evidence


def _align_guidance_from_output(output: str) -> dict:
    guidance: dict = {
        "epistemic_status": "static_analysis",
        "state_changed": False,
    }
    if "STATICALLY CERTIFIED SWAP FRAMES" in output:
        guidance["primary_action"] = "choose_offset_then_probe"
        guidance["action_semantics"] = (
            "Treat the swap as a source-position frame. Choose the concrete "
            "offset from the next coupling/realignment target, then use -try "
            "on that filled swap if needed."
        )
    if "STATICALLY BLOCKED / UNCERTIFIED CANDIDATES" in output:
        guidance["blocked_semantics"] = {
            "status": "static_blocked_uncertified",
            "meaning": "Static analyzer cannot certify candidate movement.",
            "not_meaning": "Swap is impossible or EC-rejected.",
            "recommended_action": (
                "Run -try on a candidate if strategically needed, or run "
                "-swap-search for bounded EC-backed search."
            ),
        }
    return guidance


def _record_swap_search_tool_view(session, projection, result) -> None:
    recommendations: list[dict] = []
    for idx, tactic in enumerate(result.accepted_swaps or []):
        recommendations.append({
            "id": f"swap_search.accepted.{idx}",
            "kind": "swap_tactic",
            "producer": "swap-search",
            "action": tactic.strip(),
            "why": "swap-search accepted this swap while probing the live session.",
            "action_type": "runnable_tactic",
            "confidence": "verified",
            "preconditions": [
                "proof_state.status == open",
                "current goal still matches the probed alignment state",
            ],
            "source_refs": [],
            "evidence_refs": ["probe.swap_search"],
            "metadata": {"attempts": result.attempts},
        })
    for idx, tactic in enumerate(result.hint_tactics or []):
        recommendations.append({
            "id": f"swap_search.hint.{idx}",
            "kind": "followup_tactic",
            "producer": "swap-search",
            "action": tactic.strip(),
            "why": result.hint or "swap-search produced a structured hint.",
            "action_type": "runnable_tactic",
            "confidence": "medium",
            "preconditions": ["proof_state.status == open"],
            "source_refs": [],
            "evidence_refs": ["deterministic.swap_search"],
            "metadata": {},
        })
    _record_simple_tool_view(
        session, "swap-search", projection,
        recommendations=recommendations,
        evidence={
            "deterministic": [{
                "id": "deterministic.swap_search",
                "producer": "swap_search.search_swaps",
                "success": bool(result.success),
                "attempts": int(result.attempts),
                "remaining_misaligned": int(result.remaining_misaligned),
                "hint": result.hint or "",
            }],
            "probe": [{
                "id": "probe.swap_search",
                "producer": "swap_search.search_swaps",
                "accepted_swaps": list(result.accepted_swaps or []),
                "error": result.error or "",
            }],
        },
        notes=[] if recommendations else [result.hint or "No swap-search recommendations."],
        errors=[result.error] if result.error and not result.success else [],
    )
