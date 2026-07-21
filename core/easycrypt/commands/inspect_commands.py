"""CLI handlers for read-only inspection commands: -goal-info, -goal-json,
-program-json, -show-proof, -status, -verify-lemma, -check-lemma, -diagnose,
-subgoal-gap.

These don't mutate session state — they read history.ec / curr.out /
session metadata and print derived information.

Phase 4 (2026-04-30): extracted from session_cli.main() to keep main()
as pure dispatch. Each handler mirrors the inline block it replaced;
no behavior change.
"""
from __future__ import annotations

import json
import json as _json
import re
import sys
from pathlib import Path

from core.easycrypt.session_tool_view import (  # type: ignore
    action_requires_instantiation as _action_requires_instantiation,
    stdout_tool_view as _stdout_tool_view,
    structured_tool_stdout as _structured_only_output,
)


def handle_goal_json(session, args) -> int:
    """Emit the stable goal-state adapter contract.

    This command is intentionally not named ``ec-goal-json``: until EasyCrypt
    itself exposes typed goal JSON, the command may be a fallback projection.
    The payload's authority fields say which source won.
    """
    from core.easycrypt.session_projection import (  # type: ignore
        projection_to_goal_info,
        read_proof_state_projection,
    )
    from core.easycrypt.session_tool_view import tool_view_from_projection  # type: ignore

    if not session.curr.exists():
        sys.stderr.write(
            "No current goal state. Run -start and -next first.\n",
        )
        return 1

    projection = read_proof_state_projection(
        session.dir,
        live_tool_name="goal-json",
    )
    proof_state = projection_to_goal_info(projection)
    state = session.read_state()
    goal_state = projection.goal.to_dict(
        include_raw=True,
        raw_text=state.raw_for_goal_tools,
    )
    view = tool_view_from_projection(
        tool="goal-json",
        proof_state=proof_state,
        evidence={
            "deterministic": [{
                "id": "deterministic.goal_state_adapter",
                "producer": "session_projection",
                "fact_source": goal_state.get("fact_source"),
                "authority": goal_state.get("authority"),
                "authority_rank": goal_state.get("authority_rank"),
                "ec_ground_truth": goal_state.get("ec_ground_truth"),
                "native_artifact": goal_state.get("native_artifact"),
            }],
        },
        guidance={
            "goal_state": {
                key: goal_state.get(key)
                for key in (
                    "state_kind",
                    "goal_type",
                    "num_remaining",
                    "num_remaining_determined",
                    "proof_candidate_closed",
                    "active_goal_hash",
                    "fact_source",
                    "authority",
                    "authority_rank",
                    "ec_ground_truth",
                    "native_artifact",
                )
            }
        },
        debug={"goal_state": goal_state},
    )
    _record_tool_view(session, view)
    sys.stdout.write(_json.dumps({
        "schema_version": 1,
        "kind": "easycrypt_goal_state_adapter",
        "goal_state": goal_state,
        "proof_state": proof_state,
        "tool_view": view,
    }, indent=2, sort_keys=True) + "\n")
    return 0


def handle_program_json(session, args) -> int:
    """Emit the stable program-shape adapter contract."""
    from core.easycrypt.session_projection import (  # type: ignore
        projection_to_goal_info,
        read_proof_state_projection,
    )
    from core.easycrypt.session_tool_view import tool_view_from_projection  # type: ignore
    from core.easycrypt.analysis.ec_proof_ir import build_proof_ir  # type: ignore

    if not session.curr.exists():
        sys.stderr.write(
            "No current goal state. Run -start and -next first.\n",
        )
        return 1

    projection = read_proof_state_projection(
        session.dir,
        live_tool_name="program-json",
    )
    proof_state = projection_to_goal_info(projection)
    current_goal = projection.goal.to_dict()
    proof_ir = build_proof_ir(
        session_dir=session.dir,
        proof_state=proof_state,
        current_goal=current_goal,
    )
    program_ir = dict(
        dict(proof_ir.get("resources") or {}).get("program_ir") or {}
    )
    view = tool_view_from_projection(
        tool="program-json",
        proof_state=proof_state,
        evidence={
            "deterministic": [{
                "id": "deterministic.program_state_adapter",
                "producer": "ec_program_ir",
                "fact_source": program_ir.get("fact_source"),
                "authority": program_ir.get("authority"),
                "authority_rank": program_ir.get("authority_rank"),
                "ec_ground_truth": program_ir.get("ec_ground_truth"),
                "native_artifact": program_ir.get("native_artifact"),
                "statement_count": dict(
                    program_ir.get("summary") or {}
                ).get("statement_count"),
                "call_site_count": dict(
                    program_ir.get("summary") or {}
                ).get("call_site_count"),
            }],
        },
        guidance={
            "program_state": {
                key: program_ir.get(key)
                for key in (
                    "goal_type",
                    "fact_source",
                    "authority",
                    "authority_rank",
                    "ec_ground_truth",
                    "native_artifact",
                    "summary",
                )
            }
        },
        debug={"program_ir": program_ir},
    )
    _record_tool_view(session, view)
    sys.stdout.write(_json.dumps({
        "schema_version": 1,
        "kind": "easycrypt_program_state_adapter",
        "program_ir": program_ir,
        "proof_state": proof_state,
        "tool_view": view,
    }, indent=2, sort_keys=True) + "\n")
    return 0


# ─── -goal-info ──────────────────────────────────────────────────────────

def handle_goal_info(session, args) -> int:
    """Emit a JSON dump of the active goal — type, num_remaining,
    suggested tactics, structural context (local equivs, call-equiv
    candidates, have-chain candidates, pr-rewrite candidates) — plus
    auto-resolved-name blocks.

    Order: [AUTO-RESOLVED-NAMES] → JSON → [DEFS]. Diagnostic
    blocks come BEFORE the JSON because tool-call output is capped
    (~4KB observed) and trailing blocks get truncated for deep-inline
    goals.
    """
    from core.easycrypt.analysis.ec_goal_parser import goal_to_json, parse_goal  # type: ignore
    from core.easycrypt.session_projection import (  # type: ignore
        projection_to_goal_info,
        read_proof_state_projection,
    )
    from core.easycrypt.session_goal_context import (  # type: ignore
        extract_module_keywords,
        infer_remaining_goals,
        is_goal_too_large,
        match_equivs_to_calls,
        scan_local_equiv_details,
        scan_local_equiv_lemmas,
        scan_pr_bridge_lemmas,
        scan_prob_ineq_lemmas,
        too_large_warning_block,
    )

    if not session.curr.exists():
        sys.stderr.write(
            "No current goal state. Run -start and -next first.\n",
        )
        return 1
    state = session.read_state()
    projection = read_proof_state_projection(
        session.dir,
        live_tool_name="goal-info",
    )
    if projection.status in ("candidate_closed", "verified"):
        proof_state = projection_to_goal_info(projection)
        out = {
            "goal_type": "complete",
            "num_remaining": 0,
            "num_remaining_determined": True,
            "warnings": [],
            "proof_candidate_closed": True,
            "proof_state": proof_state,
        }
        out["tool_view"] = _build_goal_info_tool_view(
            out=out,
            projection=projection,
            auto_block="",
            defs_list=[],
        )
        _record_tool_view(session, out["tool_view"])
        _emit_goal_info_output(out)
        return 0

    n_remaining = state.num_remaining
    raw = state.raw_for_goal_tools
    info = parse_goal(raw)

    # Resolve target lemma name (PivotStrategyPhase used to cache this
    # on Session; post-Phase-3c only session_meta.json carries it).
    active_lemma = getattr(session, "_target_lemma_name", "")
    if not active_lemma:
        meta_path = session.dir / "session_meta.json"
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                active_lemma = meta.get("lemma", "") or ""
            except Exception:
                pass

    # Compute structural-context fields BEFORE building JSON so they
    # appear ahead of legacy tactic reference material. All four follow
    # the same principle: agent sees structural resources before the
    # raw goal text, preventing name-based pattern matching.
    local_equivs = None
    call_equiv_candidates = None
    have_chain_candidates = None
    addend_equiv_candidates = None
    if info.prob_form in ("eq", "diff_eq"):
        # diff_eq (Pr[A]-Pr[B]=Pr[C]-Pr[D]) also wants
        # local_equiv_context: after `congr.` each subgoal becomes a
        # prob_eq using oracle-equiv lemmas.
        local_equivs = (
            scan_local_equiv_lemmas(session.context_file) or None
        )
    elif info.prob_form == "ineq":
        have_chain_candidates = (
            scan_prob_ineq_lemmas(
                session.context_file, exclude_name=active_lemma,
            ) or None
        )
    if info.goal_type in ("pRHL", "equiv"):
        equiv_details = scan_local_equiv_details(session.context_file)
        if equiv_details:
            if info.goal_type == "pRHL":
                call_procs = list({
                    s["procedure"]
                    for s in (info.left_stmts + info.right_stmts)
                    if s.get("type") == "CALL" and s.get("procedure")
                })
                if call_procs:
                    call_equiv_candidates = match_equivs_to_calls(
                        call_procs, equiv_details,
                    ) or None
            else:
                # equiv goal: match all proc names; if none parsed,
                # surface every local equiv as a candidate.
                proc_names = list({
                    s["procedure"]
                    for s in (info.left_stmts + info.right_stmts)
                    if s.get("procedure")
                })
                if proc_names:
                    call_equiv_candidates = match_equivs_to_calls(
                        proc_names, equiv_details,
                    ) or None
                else:
                    call_equiv_candidates = {
                        e["name"]: [e] for e in equiv_details
                    } or None
    if info.prob_form == "compound":
        equiv_details = scan_local_equiv_details(session.context_file)
        if equiv_details:
            games = list({
                a["game"]
                for a in (info.prob_compound_lhs + info.prob_compound_rhs)
                if a.get("game")
            })
            if games:
                addend_equiv_candidates = match_equivs_to_calls(
                    games, equiv_details,
                ) or None

    # Cross-file Pr bridge-lemma scan: when the probability goal names
    # modules that typically need a rewrite lemma to reach a provable shape,
    # surface candidates here so the agent sees them alongside local context.
    # The scan is scoped like a compiler symbol table: local declarations are
    # only usable from the extracted session context, while the original full
    # source file is excluded to avoid future/self-lemma hints.
    pr_rewrite_candidates = None
    if info.goal_type == "probability" and info.prob_form in (
        "eq", "ineq", "diff_eq", "compound",
        "adv_eq", "adv_diff_ineq", "adv_ineq",
    ):
        keywords = extract_module_keywords(info)
        if keywords:
            search_dirs: list[Path] = []
            for d in session._include_dirs:
                p = Path(d)
                if p.is_dir():
                    search_dirs.append(p)
            try:
                meta_path = session.dir / "session_meta.json"
                source_file = None
                if meta_path.exists():
                    m = json.loads(meta_path.read_text(encoding="utf-8"))
                    src = m.get("file") or m.get("source_file")
                    if src:
                        source_file = Path(src).resolve()
                        sib = source_file.parent
                        if sib.is_dir() and sib not in search_dirs:
                            search_dirs.append(sib)
            except Exception:
                source_file = None
            if search_dirs:
                search_files = [
                    session.context_file,
                ] if session.context_file.exists() else []
                hits = scan_pr_bridge_lemmas(
                    search_dirs,
                    keywords,
                    goal_text=raw,
                    search_files=search_files,
                    allow_local_files=search_files,
                    excluded_names={active_lemma} if active_lemma else set(),
                    excluded_files={source_file} if source_file else set(),
                )
                if hits:
                    pr_rewrite_candidates = hits

    parsed_out = goal_to_json(
        info,
        local_equiv_context=local_equivs,
        call_equiv_candidates=call_equiv_candidates,
        have_chain_candidates=have_chain_candidates,
        addend_equiv_candidates=addend_equiv_candidates,
        pr_rewrite_candidates=pr_rewrite_candidates,
    )
    proof_state = projection_to_goal_info(projection)
    out = {
        **parsed_out,
        "proof_state": proof_state,
    }

    # Multi-subgoal note: makes the "current type vs other-subgoal
    # types" distinction explicit so the prover doesn't misread a
    # post-call mixed-type stack as "session is broken".
    if n_remaining > 1 or (info.num_remaining or 0) > 1:
        count = max(n_remaining, info.num_remaining or 0)
        out["remaining_goals_note"] = (
            f"You have {count} subgoals pending. The `goal_type` above "
            f"is for the CURRENT (first pending) goal ONLY — the other "
            f"{count - 1} subgoal(s) may have DIFFERENT types. This is "
            f"normal after tactics like `call (_: Inv)`, `byequiv`, "
            f"`conseq`, or `seq K:` which each generate multiple "
            f"subgoals with mixed pRHL/phoare/hoare/ambient shapes. "
            f"Do NOT interpret a mismatch between the current-goal "
            f"type and your proof plan as 'session is broken'. Close "
            f"the current subgoal, then inspect the next one via "
            f"`-goal-info` again. Use `-status` to see total proof "
            f"progress."
        )
        inferred = infer_remaining_goals(session, count)
        if inferred:
            out["remaining_goals_inference"] = inferred
            out["remaining_goals_inference_caveat"] = (
                "These subgoal shapes are INFERRED from the last "
                "branching tactic's known pattern, NOT read from EC "
                "directly (EC's emacs output only exposes the current "
                "goal). Use as hints, not ground truth. Ground truth "
                "is obtained by closing the current subgoal and "
                "running -goal-info on the next. Known-wrong cases: "
                "3-arg `call (_: bad, Inv)`, nested branchers, "
                "while-variants with different arg counts."
            )

    # Pre-compute auto-resolved-names + KB hints
    auto_block, defs_names_resolved, defs_list = (
        _compute_resolved_names_block(session, raw)
    )
    goal_too_large = is_goal_too_large(raw)

    out["tool_view"] = _build_goal_info_tool_view(
        out=out,
        projection=projection,
        auto_block=auto_block,
        defs_list=defs_list,
    )
    _record_tool_view(session, out["tool_view"])

    if _structured_only_output():
        _emit_goal_info_output(out)
        return 0

    # Emit diagnostics FIRST (small, critical), then JSON, then DEFS
    if goal_too_large:
        sys.stdout.write(too_large_warning_block(raw) + "\n")
    if auto_block:
        sys.stdout.write(auto_block + "\n")

    sys.stdout.write(_json.dumps(out, indent=2) + "\n")

    # DEFS block last (least critical)
    try:
        if defs_list:
            from core.easycrypt.ec_def_resolver import format_defs  # type: ignore
            defs_block = format_defs(defs_list)
            if defs_block:
                sys.stdout.write("\n" + defs_block + "\n")
    except Exception:
        pass
    return 0


def _emit_goal_info_output(out: dict) -> None:
    if _structured_only_output() and isinstance(out.get("tool_view"), dict):
        sys.stdout.write(_json.dumps(_stdout_tool_view(out["tool_view"]), indent=2) + "\n")
        return
    sys.stdout.write(_json.dumps(out, indent=2) + "\n")


def _compute_resolved_names_block(session, raw: str) -> tuple[str, set, list]:
    """Run ec_def_resolver + where_multi to surface non-stdlib
    identifiers in the current goal. Returns (block_text,
    defs_names_resolved_set, defs_list)."""
    auto_block = ""
    defs_names_resolved: set[str] = set()
    defs_list: list = []

    try:
        from core.easycrypt.ec_def_resolver import resolve_defs_in_goal  # type: ignore
        meta_path = session.dir / "session_meta.json"
        src_file = None
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                f = meta.get("file")
                if f:
                    src_file = Path(f)
            except Exception:
                pass
        if src_file:
            defs_list = resolve_defs_in_goal(raw, src_file)
            try:
                defs_names_resolved = {d.name for d in defs_list}
            except Exception:
                pass
    except Exception:
        pass

    try:
        from core.easycrypt.ec_where import where_multi  # type: ignore
        ctx_for_where = None
        for wf in session.dir.glob("extracted_*.ec"):
            ctx_for_where = wf
            break
        if ctx_for_where is None and (session.dir / "context.ec").exists():
            ctx_for_where = session.dir / "context.ec"
        if ctx_for_where:
            ident_re = re.compile(
                r"\b([A-Z][A-Za-z0-9_]*(?:\.[A-Za-z_][\w]*)*)\b",
            )
            names = set(ident_re.findall(raw))
            SKIP = {
                "Pr", "Type", "Mod", "Top", "Self",
                "Some", "None", "True", "False",
            }
            to_resolve = [
                n for n in names
                if n not in SKIP
                and n not in defs_names_resolved
                and n.split(".")[0] not in defs_names_resolved
                and len(n) > 1
            ]
            # Add dotted-prefix fallbacks (EC `print` doesn't accept
            # module-procedure access; full dotted forms miss).
            heads: set[str] = set()
            for n in to_resolve:
                if "." in n:
                    h = n.split(".")[0]
                    if (h not in SKIP
                            and h not in defs_names_resolved
                            and len(h) > 1):
                        heads.add(h)
            to_resolve = sorted(set(to_resolve) | heads)[:15]
            if to_resolve:
                include_dirs = [
                    Path(d) for d in session._include_dirs
                    if Path(d).is_dir()
                ]
                resolved = where_multi(
                    to_resolve, ctx_for_where, include_dirs,
                )
                hit_lines = []
                for nm in to_resolve:
                    r = resolved.get(nm, {})
                    st = r.get("status")
                    if st == "direct":
                        hit_lines.append(
                            f"  {nm:30}  ({r.get('kind')})  "
                            f"-> direct hit",
                        )
                    elif st == "clone-resolved":
                        others_n = len(r.get("other_hits") or [])
                        amb = (
                            f"  [AMBIGUOUS in {others_n + 1} clones]"
                            if others_n else ""
                        )
                        hit_lines.append(
                            f"  {nm:30}  ({r.get('kind')})  "
                            f"-> {r.get('resolved')}{amb}",
                        )
                if hit_lines:
                    auto_block = (
                        "[AUTO-RESOLVED-NAMES] (`-where` auto-fired "
                        "on non-stdlib identifiers in current goal):\n"
                        + "\n".join(hit_lines) + "\n"
                        "  → For full body of any name above, run "
                        "`-where NAME`. Clone-resolved names: use "
                        "the qualified form in tactics.\n"
                    )
    except Exception:
        pass

    return auto_block, defs_names_resolved, defs_list


def _build_goal_info_tool_view(
    *,
    out: dict,
    projection,
    auto_block: str,
    defs_list: list,
) -> dict:
    from core.easycrypt.session_tool_view import (  # type: ignore
        Recommendation,
        SourceRef,
        tool_view_from_projection,
    )

    proof_state = dict(out.get("proof_state") or {})
    recommendations = []

    evidence = {
        "deterministic": [{
            "id": "deterministic.goal_parser",
            "producer": "ec_goal_parser.goal_to_json",
            "goal_type": out.get("goal_type"),
            "num_remaining": out.get("num_remaining"),
            "prob_form": out.get("prob_form"),
            "proof_candidate_closed": out.get("proof_candidate_closed"),
            "active_goal_hash": (
                proof_state.get("goal", {}).get("active_goal_hash")
                if isinstance(proof_state.get("goal"), dict) else ""
            ),
        }],
        "context": [],
        "epistemic": _goal_info_epistemic_evidence(out),
        "kb": [],
        "retrieval": [],
        "preflight": [],
        "event": [{
            "id": "event.proof_state_projection",
            "producer": "session_projection",
            "status": proof_state.get("status"),
            "event_contract": proof_state.get("event_contract"),
            "latest_transition": proof_state.get("latest_transition"),
        }],
        "raw": [],
    }
    if auto_block:
        evidence["context"].append({
            "id": "context.auto_resolved_names",
            "producer": "ec_def_resolver + ec_where.where_multi",
            "format": "legacy_text",
        })
    if defs_list:
        names = []
        for item in defs_list[:20]:
            names.append(str(getattr(item, "name", "") or ""))
        evidence["context"].append({
            "id": "context.defs_referenced_in_goal",
            "producer": "ec_def_resolver",
            "names": [n for n in names if n],
        })
    notes = []
    if out.get("remaining_goals_note"):
        notes.append({
            "code": "goal_info.remaining_goals",
            "message": out["remaining_goals_note"],
        })
    for note in getattr(projection.consistency, "notes", [])[:5]:
        notes.append({
            "code": "projection.consistency.note",
            "message": note,
        })
    errors = []
    if not proof_state.get("event_contract", {}).get("ok", True):
        errors.append({
            "code": "proof_state.event_contract",
            "message": "event contract is not valid",
        })
    if not proof_state.get("consistency", {}).get("ok", True):
        errors.append({
            "code": "proof_state.consistency",
            "message": "proof-state projection is inconsistent",
        })

    return tool_view_from_projection(
        tool="goal-info",
        proof_state=proof_state,
        recommendations=recommendations,
        guidance={
            "goal_info": _goal_info_payload(out),
        },
        evidence=evidence,
        notes=notes,
        errors=errors,
        debug={
            "legacy_top_level_fields": False,
            "legacy_auto_resolved_names_text": auto_block[:1000],
        },
    )


def _goal_info_payload(out: dict) -> dict:
    """Structured replacement for goal-info's historical top-level JSON."""
    excluded = {"proof_state", "tool_view"}
    return {
        key: value
        for key, value in out.items()
        if key not in excluded
    }


def _goal_info_epistemic_evidence(out: dict) -> list[dict]:
    legacy_templates = out.get("legacy_shape_tactic_templates")
    legacy_items = (
        legacy_templates.get("items")
        if isinstance(legacy_templates, dict) else
        []
    )
    legacy_count = (
        int(legacy_templates.get("count") or 0)
        if isinstance(legacy_templates, dict) else
        0
    )
    tactics = [
        tactic for tactic in (legacy_items or out.get("suggested_tactics") or [])
        if isinstance(tactic, str) and tactic.strip()
    ]
    if not tactics and legacy_count <= 0:
        return [{
            "id": "epistemic.goal_info.no_tactic_candidate",
            "status": "no_static_tactic_candidate",
            "meaning": "The parser did not emit tactic candidates for this goal.",
        }]
    has_template = any(_action_requires_instantiation(tactic) for tactic in tactics)
    evidence = [{
        "id": "epistemic.goal_info.legacy_shape_tactic_templates",
        "status": "legacy_parser_templates_not_action_candidates",
        "meaning": (
            "The goal parser still records legacy shape-to-tactic templates "
            "for compatibility with older diagnostics."
        ),
        "not_meaning": (
            "These templates are not prover-facing action candidates. Use "
            "ProofIR/ProgramIR recommendations for tactic choices."
        ),
    }]
    if has_template:
        evidence.append({
            "id": "epistemic.goal_info.templates",
            "status": "template_requires_instantiation",
            "meaning": "At least one parser suggestion contains placeholders.",
            "not_meaning": "The placeholder suggestion is directly runnable.",
        })
    return evidence


def _record_tool_view(session, view: dict) -> None:
    from core.easycrypt.session_tool_view import record_tool_view  # type: ignore
    try:
        record_tool_view(session, view)
    except Exception:
        pass




# ─── -show-proof ─────────────────────────────────────────────────────────

def handle_show_proof(session, args) -> int:
    """Print the accepted-tactic sequence from history.ec, plus a
    note about whether the proof is complete (qed present)."""
    if not session.history.exists() or session.history.stat().st_size == 0:
        sys.stdout.write("No proof in progress. Session history is empty.\n")
        return 0
    lines = session.history.read_text(
        encoding="utf-8", errors="replace",
    ).splitlines()
    non_empty = [l for l in lines if l.strip()]
    if not non_empty:
        sys.stdout.write("No proof in progress. Session history is empty.\n")
        return 0
    has_qed = any(
        l.strip().lower().rstrip(".").strip() == "qed" for l in non_empty
    )
    sys.stdout.write(
        f"=== Accepted proof sequence ({len(non_empty)} lines"
        + (", qed present" if has_qed else ", NO qed yet")
        + ") ===\n",
    )
    for line in non_empty:
        sys.stdout.write(line + "\n")
    if not has_qed:
        sys.stdout.write("\n[proof not yet complete — qed not found]\n")
    else:
        sys.stdout.write("\nTo use: proof.\n  <paste tactics above>\nqed.\n")
    return 0


# ─── -diagnose ───────────────────────────────────────────────────────────

def handle_diagnose(session, args) -> int:
    from core.easycrypt.ec_diagnose import diagnose_from_session  # type: ignore
    text = diagnose_from_session(session.dir)
    from core.easycrypt.session_projection import (  # type: ignore
        projection_to_goal_info,
        read_proof_state_projection,
    )
    from core.easycrypt.session_tool_view import Recommendation, tool_view_from_projection  # type: ignore
    try:
        projection = read_proof_state_projection(
            session.dir,
            live_tool_name="diagnose",
        )
        proof_state = projection_to_goal_info(projection)
        recommendation = _diagnose_recommendation(text, proof_state)
        _record_tool_view(session, tool_view_from_projection(
            tool="diagnose",
            proof_state=proof_state,
            recommendations=[recommendation] if recommendation else [],
            evidence={
                "event": [{
                    "id": "event.latest_error",
                    "producer": "session_projection",
                    "latest_error": proof_state.get("event_contract", {}).get(
                        "latest_error", ""
                    ),
                    "latest_error_tactic": proof_state.get(
                        "event_contract", {}
                    ).get("latest_error_tactic", ""),
                }],
                "epistemic": _diagnose_epistemic_evidence(text),
                "raw": [{
                    "id": "raw.diagnose_text",
                    "format": "legacy_text",
                    "preview": text[:1000],
                }],
            },
            notes=[] if recommendation else [{
                "code": "diagnose.no_actionable_recommendation",
                "message": "No structured diagnosis recommendation was derived.",
            }],
            debug={"legacy_text": text[:4000]},
        ))
    except Exception:
        pass
    sys.stdout.write(text)
    return 0


def _diagnose_recommendation(text: str, proof_state: dict):
    if proof_state.get("status") in ("candidate_closed", "verified"):
        return None
    suggestion = ""
    diagnosis = ""
    level = ""
    source = ""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("Suggestion:"):
            suggestion = stripped.split(":", 1)[1].strip()
        elif stripped.startswith("Diagnosis:"):
            diagnosis = stripped.split(":", 1)[1].strip()
        elif stripped.startswith("Level:"):
            level = stripped.split(":", 1)[1].strip()
        elif stripped.startswith("(Source:"):
            source = stripped.strip("()")
    if not suggestion:
        return None
    from core.easycrypt.session_tool_view import Recommendation, SourceRef  # type: ignore
    epistemic_status = "diagnostic_pattern_match"
    if "No known diagnosis" in text:
        epistemic_status = "diagnostic_fallback"
    level_key = level.lower()
    return Recommendation(
        id="diagnose.suggestion.0",
        kind="diagnostic_suggestion",
        producer="diagnose",
        action=suggestion,
        why=diagnosis or "Diagnosis matched the latest error.",
        action_type="strategy_hint",
        confidence="medium" if "No known diagnosis" not in text else "low",
        preconditions=[
            "proof_state.status == open",
            "the latest error still corresponds to the current tactic",
        ],
        source_refs=[
            SourceRef(kind="diagnosis_source", id=source)
        ] if source else [],
        evidence_refs=["event.latest_error", "raw.diagnose_text"],
        metadata={
            "level": level,
            "diagnosis_level": level_key,
            "epistemic_status": epistemic_status,
            "state_changed": False,
            "recommended_next": (
                "try_alternate_form" if "execution" in level_key
                else "switch_strategy" if "strategy" in level_key
                else "inspect_goal"
            ),
        },
    )


def _diagnose_epistemic_evidence(text: str) -> list[dict]:
    if "No known diagnosis" in text:
        return [{
            "id": "epistemic.diagnose.fallback",
            "status": "diagnostic_fallback",
            "meaning": "No known error pattern matched; suggestions are generic.",
        }]
    if "=== Error Diagnosis ===" in text:
        status = "diagnostic_pattern_match"
        if "Level:" in text and "EXECUTION" in text:
            status = "diagnostic_execution_match"
        elif "Level:" in text and "STRATEGY" in text:
            status = "diagnostic_strategy_match"
        return [{
            "id": "epistemic.diagnose.pattern_match",
            "status": status,
            "meaning": "The latest error matched a deterministic diagnosis pattern.",
            "not_meaning": "The suggested fix has not been executed yet.",
        }]
    return [{
        "id": "epistemic.diagnose.no_action",
        "status": "no_diagnostic_action",
        "meaning": "Diagnose did not find an actionable latest error.",
    }]


# ─── -subgoal-gap ────────────────────────────────────────────────────────

def handle_subgoal_gap(session, args) -> int:
    try:
        from core.easycrypt.subgoal_gap import (  # type: ignore
            analyze_against_lemma, analyze_session,
        )
        from core.easycrypt.session_projection import (  # type: ignore
            projection_to_goal_info,
            read_proof_state_projection,
        )
    except Exception as exc:
        sys.stderr.write(f"subgoal_gap import failed: {exc}\n")
        return 1
    projection = read_proof_state_projection(
        session.dir,
        live_tool_name="subgoal-gap",
    )
    if getattr(args, "against_lemma", ""):
        output = analyze_against_lemma(session.dir, args.against_lemma) + "\n"
    else:
        output = analyze_session(session.dir) + "\n"
    _record_tool_view(session, _subgoal_gap_tool_view(
        proof_state=projection_to_goal_info(projection),
        output=output,
        against_lemma=getattr(args, "against_lemma", "") or "",
    ))
    sys.stdout.write(output)
    return 0


def _subgoal_gap_tool_view(
    *,
    proof_state: dict,
    output: str,
    against_lemma: str,
) -> dict:
    from core.easycrypt.session_tool_view import Recommendation, tool_view_from_projection  # type: ignore
    missing_count = len(re.findall(r"\bMISSING\b", output))
    recommendations = []
    if missing_count and proof_state.get("status") not in (
        "candidate_closed", "verified",
    ):
        recommendations.append(Recommendation(
            id="subgoal_gap.missing.0",
            kind="invariant_or_precondition_gap",
            producer="subgoal-gap",
            action=(
                "Strengthen the invariant/precondition or use the "
                "reported structural source before retrying the call."
            ),
            why=f"subgoal-gap found {missing_count} missing conjunct marker(s).",
            action_type="strategy_hint",
            confidence="medium",
            preconditions=[
                "proof_state.status == open",
                "current pRHL/post-call goal still matches the analyzed state",
            ],
            evidence_refs=["raw.subgoal_gap_text"],
            metadata={"missing_count": missing_count},
        ))
    return tool_view_from_projection(
        tool="subgoal-gap",
        proof_state=proof_state,
        recommendations=recommendations,
        evidence={
            "deterministic": [{
                "id": "deterministic.subgoal_gap",
                "producer": "subgoal_gap.analyze_session",
                "against_lemma": against_lemma,
                "missing_count": missing_count,
            }],
            "raw": [{
                "id": "raw.subgoal_gap_text",
                "format": "legacy_text",
                "preview": output[:1000],
            }],
        },
        notes=[] if missing_count else [{
            "code": "subgoal_gap.no_missing_marker",
            "message": "No MISSING marker was reported.",
        }],
        debug={"legacy_text": output[:4000]},
    )


# ─── -check-lemma ────────────────────────────────────────────────────────

def handle_check_lemma(session, args) -> int:
    """Lookup whether a lemma exists in the source/context file +
    return its signature info. Same file-resolution logic as
    -file-index (prefers -f, falls back to session_meta.json's source,
    falls back to context.ec)."""
    from core.easycrypt.ec_file_index import (  # type: ignore
        check_lemma, format_check_lemma,
    )

    target_file = None
    if args.file:
        target_file = Path(args.file)
    else:
        ctx = session.dir / "context.ec"
        for f in session.dir.glob("extracted_*.ec"):
            ctx = f
            break
        if ctx.exists() and ctx.stat().st_size > 0:
            meta_path = session.dir / "session_meta.json"
            if meta_path.exists():
                try:
                    meta = json.loads(meta_path.read_text())
                    if meta.get("file"):
                        src = Path(meta["file"])
                        if src.exists():
                            target_file = src
                except Exception:
                    pass
            if target_file is None:
                target_file = ctx

    if target_file is None or not target_file.exists():
        sys.stderr.write(
            "[check-lemma] No file found. Use -f <file.ec> or start "
            "the session with -f first.\n",
        )
        return 1

    result = check_lemma(target_file, args.check_lemma)
    if args.as_json:
        sys.stdout.write(json.dumps(result, indent=2) + "\n")
    else:
        sys.stdout.write(
            format_check_lemma(
                result, args.check_lemma, target_file.name,
            ),
        )
    return 0 if result.get("exists") else 1


# ─── -verify-lemma ───────────────────────────────────────────────────────

def handle_verify_lemma(session, args) -> int:
    """Run a full-file EasyCrypt check on the trimmed file (target
    lemma's proof body, plus any session-history tactics if the
    session has a closed proof). Returns 0 on PASSED, 1 on FAILED."""
    import subprocess
    from core.easycrypt.lemma_extract import extract_lemma  # type: ignore
    from core.easycrypt.session_common import get_ec_env  # type: ignore

    def emit_verification(status: str, **payload) -> None:
        data = {
            "lemma": args.verify_lemma,
            "status": status,
            "verifier": "easycrypt",
        }
        data.update(payload)
        session.emit_event("verification.completed", data)

    file_path = None
    if args.file:
        file_path = Path(args.file)
    else:
        meta_path = session.dir / "session_meta.json"
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text())
                if meta.get("file"):
                    file_path = Path(meta["file"])
            except Exception:
                pass
    if file_path is None or not file_path.exists():
        sys.stderr.write(
            "No source file found. Use -f <file.ec> or start the "
            "session with -f.\n",
        )
        emit_verification("error", reason="source_file_not_found")
        return 1

    use_session_proof = False
    session_proof_tactics = ""
    if session.history.exists() and session.history.stat().st_size > 0:
        hist_text = session.history.read_text(
            encoding="utf-8", errors="replace",
        )
        if any(
            l.strip().lower().rstrip(".").strip() == "qed"
            for l in hist_text.splitlines()
        ):
            use_session_proof = True
            session_proof_tactics = hist_text

    sys.stdout.write(
        f"[verify] Extracting lemma '{args.verify_lemma}' from "
        f"{file_path.name}...\n",
    )
    try:
        if use_session_proof:
            extracted = extract_lemma(
                file_path, args.verify_lemma, open_proof=True,
            )
            sys.stdout.write(
                f"[verify] Using proof from session history "
                f"({len(session_proof_tactics.splitlines())} lines)\n",
            )
        else:
            extracted = extract_lemma(
                file_path, args.verify_lemma, verify_proof=True,
            )
            sys.stdout.write("[verify] Using proof from source file\n")
    except ValueError as e:
        sys.stderr.write(f"[verify] Error: {e}\n")
        emit_verification(
            "error", reason="extract_lemma_failed",
            file=str(file_path.resolve()), error=str(e),
        )
        return 1

    extracted_lines = len(extracted.splitlines())
    total_lines = sum(1 for _ in file_path.read_text().splitlines())
    sys.stdout.write(
        f"[verify] Trimmed to {extracted_lines} lines "
        f"(source has {total_lines} lines — "
        f"{total_lines - extracted_lines} lines after target omitted)\n",
    )

    verify_content = extracted
    if use_session_proof:
        if not verify_content.endswith("\n"):
            verify_content += "\n"
        verify_content += session_proof_tactics
    verify_tmp = session.dir / "verify_tmp.ec"
    verify_out = session.dir / "verify.out"
    verify_tmp.write_text(verify_content, encoding="utf-8")

    sys.stdout.write("[verify] Running EasyCrypt on trimmed file...\n")
    cmd = ["easycrypt", "-emacs"]
    for d in session._include_dirs:
        cmd.extend(["-I", d])
    ec_env = get_ec_env()
    with verify_tmp.open("rb") as inp, verify_out.open("wb") as out:
        try:
            subprocess.run(
                cmd, stdin=inp, stdout=out,
                stderr=subprocess.STDOUT, check=False, env=ec_env,
            )
        except FileNotFoundError:
            sys.stderr.write(
                "[verify] Error: easycrypt not found on PATH.\n",
            )
            emit_verification(
                "error", reason="easycrypt_not_found",
                file=str(file_path.resolve()),
                verify_tmp=str(verify_tmp.resolve()),
            )
            return 1

    output = verify_out.read_text(encoding="utf-8", errors="replace")
    error_lines = [
        l for l in output.split("\n") if "[error" in l.lower()
    ]
    if error_lines:
        sys.stdout.write(
            f"[verify] FAILED: {len(error_lines)} error(s) found\n",
        )
        for err in error_lines[:5]:
            sys.stdout.write(f"  {err.strip()}\n")
        last_lines = output.strip().split("\n")[-30:]
        sys.stdout.write("\nEC output (last 30 lines):\n")
        sys.stdout.write("\n".join(last_lines) + "\n")
        emit_verification(
            "fail",
            file=str(file_path.resolve()),
            verify_tmp=str(verify_tmp.resolve()),
            verify_out=str(verify_out.resolve()),
            use_session_proof=use_session_proof,
            error_count=len(error_lines),
            errors=error_lines[:5],
        )
        return 1
    sys.stdout.write(
        f"[verify] PASSED: lemma '{args.verify_lemma}' proof "
        f"verified successfully\n",
    )
    last_lines = output.strip().split("\n")[-10:]
    sys.stdout.write("\n".join(last_lines) + "\n")
    emit_verification(
        "pass",
        file=str(file_path.resolve()),
        verify_tmp=str(verify_tmp.resolve()),
        verify_out=str(verify_out.resolve()),
        use_session_proof=use_session_proof,
        error_count=0,
    )
    return 0
