"""CLI handlers for the search-family flags: -search, -search-skeleton,
-sig, -where, -lemma-hints, -tactic-forms, -bridge-lemmas, -members,
-clones, -file-index.

Each handler is `handle_<name>(session, args) -> int` returning a CLI
exit code. Side effects: writes the response block to stdout. Stderr is
used only for hard errors (missing context file, bad arg). The handlers
do NOT mutate Session state — they're read-only library lookups
parameterized by session metadata (include_dirs, context file).

Phase 3b of the cleanup. session_cli.py's main() previously inlined
each `if args.X:` branch with ~20-30 lines of search_dirs construction
and result formatting. Pulling them here keeps main() to dispatch only.
"""
from __future__ import annotations

import json as _json
import re
import sys
from pathlib import Path
from typing import Optional

from core.easycrypt.session_tool_view import (  # type: ignore
    action_requires_instantiation as _action_requires_instantiation,
    emit_tool_or_legacy as _emit_tool_or_legacy,
)


def _build_search_dirs(session, ec_src: str) -> list[Path]:
    """Construct the list of directories to search.

    Order: --ec-src first (typically the EC stdlib theories), then any
    --include-dir entries that are real directories. Used by every
    library-lookup handler that needs to walk .ec/.eca files.
    """
    dirs = [Path(ec_src)]
    for d in session._include_dirs:
        p = Path(d)
        if p.is_dir() and p not in dirs:
            dirs.append(p)
    return dirs


def _find_context_file(session) -> Optional[Path]:
    """Locate the active context file for the session.

    Preference: an `extracted_*.ec` file (from `-start -lemma`) takes
    priority over the generic `context.ec`. Returns None if neither
    exists — callers that REQUIRE a context (-search-skeleton,
    -where) should error out in that case.
    """
    for f in session.dir.glob("extracted_*.ec"):
        return f
    ctx = session.dir / "context.ec"
    return ctx if ctx.exists() else None


def _add_loaded_source_dir(session, dirs: list[Path]) -> None:
    """Mutate `dirs` to include the directory of the original loaded
    source file (from -start -f). Sibling .ec files often live next to
    the target lemma — `-sig`'s search benefits from picking them up.
    """
    try:
        meta_path = session.dir / "session_meta.json"
        if meta_path.exists():
            meta = _json.loads(meta_path.read_text(encoding="utf-8"))
            src = meta.get("source_file")
            if src:
                sib_dir = Path(src).resolve().parent
                if sib_dir.is_dir() and sib_dir not in dirs:
                    dirs.append(sib_dir)
    except Exception:
        pass


# ─── -search ─────────────────────────────────────────────────────────────

def handle_search(session, args) -> int:
    """Run a regex-on-declaration-name search. Routes through the
    search-hook registry for [SEARCH-QUERY-AUTOFIX] (BRE→ERE alternation
    fix) and [SEARCH-FALLBACK-HINT] (3-miss → suggest -search-skeleton).
    See session_hooks.py for the hook contract.
    """
    from core.easycrypt.search.ec_search import search_lemmas
    from core.easycrypt.session_hooks import (
        SearchHookContext, autofix_bre_alternation, run_search_hooks,
    )

    search_dirs = _build_search_dirs(session, args.ec_src)
    ctx = _find_context_file(session)

    raw_query = args.search
    effective_query, was_autofixed = autofix_bre_alternation(raw_query)
    output = search_lemmas(
        effective_query, search_dirs, ctx, args.max_results,
    )
    hook_ctx = SearchHookContext(
        session_dir=session.dir, raw_query=raw_query,
        effective_query=effective_query, output=output,
        was_autofixed=was_autofixed,
    )
    for block in run_search_hooks(hook_ctx):
        sys.stdout.write(block)
    sys.stdout.write(output)
    return 0


# ─── -sig ────────────────────────────────────────────────────────────────

def handle_sig(session, args) -> int:
    """Look up the full declaration of a named lemma/axiom/op/pred. Adds
    the loaded source file's directory to search_dirs so cross-file
    lemmas in sibling .ec files are reachable."""
    from core.easycrypt.search.ec_search import lookup_lemma_signature

    search_dirs = _build_search_dirs(session, args.ec_src)
    _add_loaded_source_dir(session, search_dirs)
    ctx = _find_context_file(session)
    output = lookup_lemma_signature(args.sig_name, search_dirs, ctx)
    _record_lookup_tool_view(
        session,
        "sig",
        output,
        query={"name": args.sig_name},
        producer="ec_search.lookup_lemma_signature",
    )
    sys.stdout.write(output)
    return 0


# ─── -search-skeleton ────────────────────────────────────────────────────

def handle_search_skeleton(session, args) -> int:
    """EC-native AST search via probe file. Requires a context file
    (-start -f) to be loaded — without it the EC daemon has no symbol
    table to search against.
    """
    from core.easycrypt.search.ec_search_skeleton import search_skeleton

    ctx = _find_context_file(session)
    if ctx is None:
        sys.stderr.write(
            "[search-skeleton] No context file in session — load with "
            "`-start -f`.\n",
        )
        return 1
    include_dirs = [Path(d) for d in session._include_dirs
                    if Path(d).is_dir()]
    output = search_skeleton(
        args.search_skeleton, ctx, include_dirs,
        max_results=args.max_results,
    )
    _record_lookup_tool_view(
        session,
        "search-skeleton",
        output,
        query={"query": args.search_skeleton, "max_results": args.max_results},
        producer="ec_search_skeleton.search_skeleton",
    )
    sys.stdout.write(output)
    return 0


# ─── -where ──────────────────────────────────────────────────────────────

def handle_where(session, args) -> int:
    """Resolve a name to its definition site (handles clone aliases)."""
    from core.easycrypt.ec_where import where, format_where

    ctx = _find_context_file(session)
    if ctx is None:
        sys.stderr.write(
            "[where] No context file in session — load with `-start -f`.\n",
        )
        return 1
    include_dirs = [Path(d) for d in session._include_dirs
                    if Path(d).is_dir()]
    result = where(args.where_name, ctx, include_dirs)
    output = format_where(result)
    _record_lookup_tool_view(
        session,
        "where",
        output,
        query={"name": args.where_name},
        producer="ec_where.where",
    )
    sys.stdout.write(output)
    return 0


# ─── -tactic-forms ───────────────────────────────────────────────────────

def handle_tactic_forms(session, args) -> int:
    """Print the structured forms reference for a tactic name. If the
    name isn't covered, list the covered set and exit non-zero."""
    try:
        from core.easycrypt.search.ec_tactic_forms import (
            format_forms,
            get_forms,
            list_all,
            normalize_proof_mode,
        )
    except Exception as exc:
        sys.stderr.write(f"ec_tactic_forms import failed: {exc}\n")
        return 1
    name = args.tactic_forms.strip()
    tf = get_forms(name)
    if tf is None:
        sys.stderr.write(
            f"No tactic-form reference for `{name}`. Covered tactics:\n"
            f"  {', '.join(list_all())}\n"
            "If you think this tactic has multiple argument forms worth\n"
            "documenting, add an entry to core/easycrypt/search/ec_tactic_forms.py.\n",
        )
        return 1
    goal_text = _active_goal_text_for_tactic_forms(session)
    mode = normalize_proof_mode(goal_text=goal_text)
    output = format_forms(tf, mode=mode, goal_text=goal_text)
    _record_lookup_tool_view(
        session,
        "tactic-forms",
        output,
        query={"tactic": name, "mode": mode},
        producer="ec_tactic_forms.get_forms",
    )
    sys.stdout.write(output)
    return 0


def _active_goal_text_for_tactic_forms(session) -> str:
    try:
        if getattr(session, "curr", None) is not None and not session.curr.exists():
            return ""
    except Exception:
        pass
    try:
        goal_block, _ = session.get_active_goal_block()
        if goal_block:
            return str(goal_block)
    except Exception:
        pass
    try:
        return str(session.get_active_goal_output() or "")
    except Exception:
        return ""


# ─── -bridge-lemmas ──────────────────────────────────────────────────────

def handle_bridge_lemmas(session, args) -> int:
    """List bridge equiv lemmas relevant to the current session."""
    from core.easycrypt.ec_bridge_lemmas import analyze_bridge_lemmas_from_session

    output = analyze_bridge_lemmas_from_session(session.dir)
    view = _record_bridge_lemmas_tool_view(session, output)
    _emit_tool_or_legacy(view, output, omit_raw_previews=True)
    return 0


def _record_bridge_lemmas_tool_view(session, output: str) -> dict | None:
    from core.easycrypt.session_projection import (  # type: ignore
        projection_to_goal_info,
        read_proof_state_projection,
    )
    from core.easycrypt.session_tool_view import (  # type: ignore
        record_tool_view,
        tool_view_from_projection,
    )
    try:
        projection = read_proof_state_projection(
            session.dir,
            live_tool_name="bridge-lemmas",
        )
        recommendations = _bridge_lemma_recommendations(output)
        view = tool_view_from_projection(
            tool="bridge-lemmas",
            proof_state=projection_to_goal_info(projection),
            recommendations=recommendations,
            evidence={
                "deterministic": [{
                    "id": "deterministic.bridge_lemmas",
                    "producer": "ec_bridge_lemmas.analyze_bridge_lemmas_from_session",
                    "found_recommendations": len(recommendations),
                }],
                "context": [{
                    "id": "context.loaded_easycrypt_file",
                    "producer": "bridge-lemmas",
                    "source": "session context file",
                }],
                "epistemic": _bridge_lemmas_epistemic_evidence(recommendations),
                "raw": [{
                    "id": "raw.bridge_lemmas_text",
                    "format": "legacy_text",
                    "preview": output[:1000],
                }],
            },
            notes=(
                [] if recommendations
                else ["No bridge lemma chain found in the loaded context."]
            ),
            debug={"legacy_text": output[:4000]},
        )
        record_tool_view(session, view)
        return view
    except Exception:
        return None


def _bridge_lemmas_epistemic_evidence(recommendations: list[dict]) -> list[dict]:
    if not recommendations:
        return [{
            "id": "epistemic.bridge_lemmas.no_candidate",
            "status": "no_static_candidate",
            "meaning": "No bridge tactic template was found in the context scan.",
        }]
    statuses = {
        str((rec.get("metadata") or {}).get("epistemic_status") or "")
        for rec in recommendations
    }
    evidence: list[dict] = []
    if "static_candidate_uncertified_by_ec" in statuses:
        evidence.append({
            "id": "epistemic.bridge_lemmas.static_candidate",
            "status": "static_candidate_uncertified_by_ec",
            "meaning": (
                "A bridge tactic shape matched the current goal and context."
            ),
            "not_meaning": "EasyCrypt has not verified this tactic in the session.",
        })
    if "template_requires_instantiation" in statuses:
        evidence.append({
            "id": "epistemic.bridge_lemmas.template",
            "status": "template_requires_instantiation",
            "meaning": "The bridge output contains placeholders such as `...`.",
            "not_meaning": "The template is directly runnable.",
        })
    return evidence


def _bridge_lemma_recommendations(output: str) -> list[dict]:
    recs: list[dict] = []
    for line in output.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        tactic = ""
        if stripped.startswith("transitivity "):
            tactic = stripped
        elif stripped.startswith("apply ") or stripped.startswith("call "):
            tactic = stripped
        elif stripped.startswith("byequiv ") or stripped.startswith("conseq "):
            tactic = stripped
        # A direct (1-hop) bridge surfaces as `exact LEM.` / `symmetry; exact LEM.`;
        # without these openers such chains were dropped to [] (panel audit: the
        # equiv_bridge_lemmas wiring drop — the only genuine "wiring" part).
        elif stripped.startswith("exact ") or stripped.startswith("symmetry"):
            tactic = stripped
        else:
            match = re.match(r"^(?:[-*]|\d+\.)\s+(.+)$", stripped)
            if match and re.match(
                r"^(transitivity|apply|call|byequiv|conseq|exact|symmetry)\b",
                match.group(1),
            ):
                tactic = match.group(1).strip()
        if not tactic:
            continue
        tactic = tactic.split("(*", 1)[0].strip()
        if not tactic:
            continue
        if not tactic.endswith("."):
            tactic += "."
        requires_instantiation = _action_requires_instantiation(tactic)
        recs.append({
            "id": f"bridge_lemmas.{len(recs)}",
            "kind": "bridge_tactic",
            "producer": "bridge-lemmas",
            "action": tactic,
            "why": (
                "Bridge lemma analysis found a tactic template relevant "
                "to the current equivalence/probability bridge."
            ),
            "action_type": (
                "strategy_hint" if requires_instantiation else "tactic_candidate"
            ),
            "confidence": "medium",
            "preconditions": [
                "proof_state.status == open",
                "current goal still matches the analyzed bridge shape",
            ],
            "source_refs": [],
            "evidence_refs": ["raw.bridge_lemmas_text"],
            "metadata": {
                "epistemic_status": (
                    "template_requires_instantiation"
                    if requires_instantiation
                    else "static_candidate_uncertified_by_ec"
                ),
                "state_changed": False,
                "validation_owner": "manager_commit",
                "requires_instantiation": requires_instantiation,
            },
        })
    return recs


# ─── -members ────────────────────────────────────────────────────────────

def handle_members(session, args) -> int:
    """List the members of a clone-scope (theory / module path)."""
    from core.easycrypt.ec_members import members, format_members

    ctx = _find_context_file(session)
    if ctx is None:
        sys.stderr.write(
            "[members] No context file in session — load with `-start -f`.\n",
        )
        return 1
    include_dirs = [Path(d) for d in session._include_dirs
                    if Path(d).is_dir()]
    result = members(args.members_scope, ctx, include_dirs)
    output = format_members(result)
    _record_lookup_tool_view(
        session,
        "members",
        output,
        query={"scope": args.members_scope},
        producer="ec_members.members",
    )
    sys.stdout.write(output)
    return 0


# ─── -clones ─────────────────────────────────────────────────────────────

def handle_clones(session, args) -> int:
    """Analyze clone declarations + lemma renamings in scope. Search is
    scoped to context + include_dirs only (not the full --ec-src) — full-
    stdlib clone analysis is too noisy and irrelevant for most queries.
    """
    from core.easycrypt.search.ec_search import analyze_clones

    ctx = _find_context_file(session)
    search_dirs = [Path(d) for d in session._include_dirs
                   if Path(d).is_dir()]
    output = analyze_clones(ctx, search_dirs)
    _record_lookup_tool_view(
        session,
        "clones",
        output,
        query={"context_file": str(ctx) if ctx else ""},
        producer="ec_search.analyze_clones",
    )
    sys.stdout.write(output)
    return 0


# ─── -lemma-hints ────────────────────────────────────────────────────────

def handle_lemma_hints(session, args) -> int:
    """Op-token-indexed stdlib lookup against the current goal. Reads
    the ACTIVE goal block (highest check-number, same as -goal-info) so
    results scope to the current subgoal, not all of curr.out.
    """
    from core.easycrypt.search.ec_lemma_lookup import lookup_for_goal, format_hints

    if not session.curr.exists():
        sys.stderr.write(
            "No current goal state. Run -start and -next first.\n",
        )
        return 1
    goal_block, _ = session.get_active_goal_block()
    raw = goal_block if goal_block else session.get_active_goal_output()
    hints = lookup_for_goal(raw)
    out = format_hints(hints)
    _record_lemma_hints_tool_view(session, hints, out or "", raw)
    if not out.strip():
        sys.stdout.write(
            "[AUTO-LEMMA-HINTS] No relevant stdlib lemmas matched the "
            "ops visible in the current goal. The goal may be "
            "project-specific (no stdlib op tokens), or the index "
            "doesn't cover the relevant theory. Try `-search "
            "<keyword>` for project-local lemma names.\n",
        )
    else:
        sys.stdout.write(out)
    return 0


def _record_lemma_hints_tool_view(
    session,
    hints: list[dict],
    output: str,
    raw_goal: str,
) -> None:
    from core.easycrypt.session_projection import (  # type: ignore
        projection_to_goal_info,
        read_proof_state_projection,
    )
    from core.easycrypt.session_tool_view import Recommendation, SourceRef, record_tool_view, tool_view_from_projection  # type: ignore
    try:
        projection = read_proof_state_projection(
            session.dir,
            live_tool_name="lemma-hints",
        )
        recommendations = _lemma_hint_recommendations(hints)
        evidence = {
            "retrieval": [{
                "id": "retrieval.lemma_hints",
                "producer": "ec_lemma_lookup.lookup_for_goal",
                "hint_count": len(hints),
                "goal_preview": raw_goal[:500],
            }],
            "epistemic": _lemma_hints_epistemic_evidence(hints),
            "raw": [{
                "id": "raw.lemma_hints_text",
                "format": "legacy_text",
                "preview": output[:1000],
            }],
        }
        view = tool_view_from_projection(
            tool="lemma-hints",
            proof_state=projection_to_goal_info(projection),
            recommendations=recommendations,
            evidence=evidence,
            notes=[] if hints else [{
                "code": "lemma_hints.no_match",
                "message": (
                    "No stdlib lemmas matched op tokens in the current goal."
                ),
            }],
            debug={"legacy_text": output[:4000]},
        )
        record_tool_view(session, view)
    except Exception:
        pass


def _lemma_hint_recommendations(hints: list[dict]) -> list:
    from core.easycrypt.session_tool_view import Recommendation, SourceRef  # type: ignore
    recs = []
    for idx, hint in enumerate(hints[:5]):
        name = str(hint.get("name") or hint.get("qualified") or "").strip()
        if not name:
            continue
        recs.append(Recommendation(
            id=f"lemma_hints.lookup_symbol.{idx}",
            kind="lemma_signature_lookup",
            producer="lemma-hints",
            action=(
                '{"intent":"lookup_symbol","payload":{"symbol":"'
                + name.replace("\\", "\\\\").replace('"', '\\"')
                + '"}}'
            ),
            why=(
                "A stdlib lemma matched operators in the current goal; "
                "inspect its signature before applying/rewrite/smt use."
            ),
            action_type="inspection_action",
            confidence="medium",
            preconditions=["proof_state.status == open"],
            source_refs=[
                SourceRef(
                    kind="lemma",
                    id=name,
                    path=str(hint.get("file") or ""),
                    details={
                        "matched_op": str(hint.get("matched_op") or ""),
                        "qualified": str(hint.get("qualified") or ""),
                        "kind": str(hint.get("kind") or ""),
                    },
                ),
            ],
            evidence_refs=["retrieval.lemma_hints", "raw.lemma_hints_text"],
            metadata={
                "epistemic_status": "context_retrieval_unverified",
                "state_changed": False,
                "recommended_next": "inspect_signature",
                "lemma": name,
                "matched_op": str(hint.get("matched_op") or ""),
            },
        ))
    return recs


def _lemma_hints_epistemic_evidence(hints: list[dict]) -> list[dict]:
    if not hints:
        return [{
            "id": "epistemic.lemma_hints.no_match",
            "status": "no_retrieval_match",
            "meaning": "No indexed stdlib lemma matched current goal tokens.",
        }]
    return [{
        "id": "epistemic.lemma_hints.retrieval",
        "status": "context_retrieval_unverified",
        "meaning": (
            "Lemma hints were retrieved by matching goal tokens against an "
            "offline stdlib lemma index."
        ),
        "not_meaning": "The lemmas are in scope or applicable without checking.",
    }]


# ─── -file-index ─────────────────────────────────────────────────────────

def _resolve_target_file(session, args) -> Optional[Path]:
    """File-resolution shared by -file-index and -check-lemma.

    Order: explicit `-f <file>` wins. Otherwise prefer `session_meta.file`
    (the original source) over the in-session extract — `context.ec` /
    `extracted_*.ec` is a trimmed view and may miss declarations that the
    file-level indexer wants. Fall back to the extract only if the meta
    hint isn't usable.
    """
    if args.file:
        return Path(args.file)
    ctx = session.dir / "context.ec"
    for f in session.dir.glob("extracted_*.ec"):
        ctx = f
        break
    if not (ctx.exists() and ctx.stat().st_size > 0):
        return None
    meta_path = session.dir / "session_meta.json"
    if meta_path.exists():
        try:
            meta = _json.loads(meta_path.read_text())
            if meta.get("file"):
                src = Path(meta["file"])
                if src.exists():
                    return src
        except Exception:
            pass
    return ctx


def handle_file_index(session, args) -> int:
    """Walk an .ec file and print its index of declarations."""
    from core.easycrypt.ec_file_index import index_ec_file, format_index

    target_file = _resolve_target_file(session, args)
    if target_file is None or not target_file.exists():
        sys.stderr.write(
            "[file-index] No file found. Use -f <file.ec> or start the "
            "session with -f first.\n",
        )
        return 1

    idx = index_ec_file(target_file)
    if args.as_json:
        output = _json.dumps(idx, indent=2) + "\n"
    else:
        output = format_index(idx)
    _record_lookup_tool_view(
        session,
        "file-index",
        output,
        query={"file": str(target_file), "as_json": bool(args.as_json)},
        producer="ec_file_index.index_ec_file",
        metadata=_file_index_metadata(idx),
    )
    sys.stdout.write(output)
    return 0


def handle_lemma_index(session, args) -> int:
    """Whole-file lemma index: every lemma's name + statement (no proofs).

    Eval-safe: prints only signatures (proofs are excluded by the extractor),
    so it is admissible even in eval mode where sibling-lemma statements are
    allowed but proofs are not.
    """
    from core.easycrypt.ec_file_index import index_ec_file, format_lemma_index, format_index

    target_file = _resolve_target_file(session, args)
    if target_file is None or not target_file.exists():
        sys.stderr.write(
            "[lemma-index] No file found. Use -f <file.ec> or start the "
            "session with -f first.\n",
        )
        return 1

    idx = index_ec_file(target_file)
    if args.as_json:
        # JSON: lemmas-only slice (name/kind/location/line/statement)
        output = _json.dumps(
            {"file": idx.get("file"), "all_lemmas": idx.get("all_lemmas", [])},
            indent=2,
        ) + "\n"
    else:
        output = format_lemma_index(idx)
    _record_lookup_tool_view(
        session,
        "lemma-index",
        output,
        query={"file": str(target_file), "as_json": bool(args.as_json)},
        producer="ec_file_index.index_ec_file",
        metadata=_file_index_metadata(idx),
    )
    sys.stdout.write(output)
    return 0


def _record_lookup_tool_view(
    session,
    tool: str,
    output: str,
    *,
    query: dict | None = None,
    producer: str,
    metadata: dict | None = None,
) -> None:
    from core.easycrypt.session_projection import (  # type: ignore
        projection_to_goal_info,
        read_proof_state_projection,
    )
    from core.easycrypt.session_tool_view import record_tool_view, tool_view_from_projection  # type: ignore
    try:
        projection = read_proof_state_projection(
            session.dir,
            live_tool_name=tool,
        )
        view = tool_view_from_projection(
            tool=tool,
            proof_state=projection_to_goal_info(projection),
            recommendations=[],
            evidence={
                "context": [{
                    "id": f"context.{tool}.query",
                    "producer": producer,
                    "query": dict(query or {}),
                    "metadata": dict(metadata or {}),
                }],
                "raw": [{
                    "id": f"raw.{tool}_text",
                    "format": "legacy_text",
                    "preview": output[:1000],
                }],
            },
            notes=[{
                "code": f"{tool}.lookup",
                "message": "Lookup result is recorded as raw/context evidence.",
            }],
            debug={"legacy_text": output[:4000]},
        )
        record_tool_view(session, view)
    except Exception:
        pass


def _file_index_metadata(idx: dict) -> dict:
    if not isinstance(idx, dict):
        return {}
    return {
        "total_lines": idx.get("total_lines"),
        "types": len(idx.get("types") or []),
        "ops": len(idx.get("ops") or []),
        "axioms": len(idx.get("axioms") or []),
        "modules": len(idx.get("modules") or []),
        "clones": len(idx.get("clones") or []),
        "lemmas": len(idx.get("all_lemmas") or []),
        "error": idx.get("error", ""),
    }
