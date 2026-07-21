"""PASS 2 — ProofIR handle construction (§3.2): build the typed proof-handle
set (ambient/frontend/adversary-invariant/PR-bridge handles) that PASS 3/4 read.

Carved out of ec_proof_ir.py (the funcs reachable ONLY from _proof_handles).
Imports only what these funcs use and NOTHING from ec_proof_ir, so there is no
cycle; ec_proof_ir re-exports this module's own defs so build_proof_ir +
consumers see them at the same path unchanged.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

# Pure leaf utilities live in ec_proof_ir_util now (carve step: break the
# import cycle for per-pass modules); the leaves this module's passes use are
# imported below.
from core.easycrypt.analysis.ec_proof_ir_util import (
    _legacy_shape_tactic_templates,
    _candidate_names,
    _lemma_leaf,
    _dict,
    _list,
    _dedupe_strings,
    _call_handle_candidate_kind,
    _extract_tactic_from_action,
    _program_edit_script_action,
)
from core.easycrypt.analysis.ec_utils import (
    contains_top_level_implication as _contains_top_level_implication,
    first_top_level_implication as _first_top_level_implication,
    matching_delimiter as _matching_delimiter,
    procedure_template_matches as _procedure_template_matches_with_key,
    split_flat_conjuncts as _split_flat_conjuncts,
    strip_outer_parens as _strip_outer_parens,
    top_level_token_index as _top_level_token_index,
)
from core.easycrypt.analysis.ec_action_contracts import (
    normalize_action_candidate,
    realigning_swap_contract,
)

from core.easycrypt.analysis.ec_equiv_closers import (
    _clean_proc,
    _equiv_proc_pair,
    _local_equiv_hypothesis_handles as _base_local_equiv_hypothesis_handles,
    _parse_equiv_hypothesis_body,
    _source_equiv_declarations,
    build_equiv_exact_closers,
)
from core.easycrypt.analysis.ec_lemma_index import (
    build_semantic_lemma_index,
    high_precision_pr_bound_routes,
    mechanical_goal_candidates,
    semantic_distribution_certificates,
    semantic_one_sided_losslessness_candidates,
    semantic_pr_bound_candidates,
    semantic_pr_rewrite_candidates,
    session_context_files as _session_context_files,
    session_target_lemma as _session_target_lemma,
    source_declarations_by_name as _lemma_index_source_declarations_by_name,
)
from core.easycrypt.analysis.ec_pr_obligations import (
    goal_body as _pr_goal_body,
)
from core.easycrypt.analysis.ec_probabilistic_vc import (
    build_probabilistic_vc_frontend,
)
from core.easycrypt.analysis.ec_pr_canonical import (
    matching_bracket as _matching_bracket,
)
from core.easycrypt.analysis.ec_procedure_frontend import (
    build_procedure_body_frontend,
)
from core.easycrypt.analysis.ec_program_ir import (
    annotate_callable_lemma_handles,
)
from core.easycrypt.analysis.ec_procedure_ref import (
    extract_visible_call_procedures,
    parse_call_statement,
)

from core.easycrypt.analysis.ec_dataflow_invariant import (
    build_invariant_skeleton,
)
from core.easycrypt.analysis.ec_instantiation_binding import (
    binding_for_name,
    build_instantiation_bindings,
)
from core.easycrypt.analysis.ec_name_resolution import (
    resolution_for_name,
    resolve_goal_unfoldable_names,
    resolve_proof_ir_names,
)
from core.easycrypt.analysis.ec_native_ast_search import (
    build_native_ast_search_frontend,
)
from core.easycrypt.analysis.ec_pr_obligations import (
    build_pr_obligation_plan,
)
from core.easycrypt.analysis.ec_pr_path_planner import build_pr_path_plan
from core.easycrypt.analysis.ec_pr_bridge_frontend import (
    build_pr_typed_bridge_frontend,
    pr_wrapper_bridge_candidates as build_pr_wrapper_bridge_candidates,
)


def _proof_handles(
    parsed: dict[str, Any],
    goal_type: str,
    *,
    program_ir: dict[str, Any],
    goal_text: str = "",
    session_dir: str | Path | None = None,
    pr_normal_form: dict[str, Any] | None = None,
) -> dict[str, Any]:
    lemma_index = build_semantic_lemma_index(session_dir)
    raw_call_handles = (
        _callable_lemma_handles(parsed)
        + _local_equiv_hypothesis_handles(goal_text)
        + _source_call_equiv_handles(session_dir, program_ir)
    )
    call_handles = annotate_callable_lemma_handles(
        program_ir,
        raw_call_handles,
    )
    adversary_skeleton = _adversary_invariant_skeleton(
        parsed,
        goal_type,
        program_ir,
        call_handles,
    )
    source_pr_rewrites = _source_pr_rewrite_handles(
        session_dir,
        parsed,
        goal_text,
        pr_normal_form=pr_normal_form,
        semantic_lemma_index=lemma_index,
    )
    source_pr_bounds = semantic_pr_bound_candidates(
        lemma_index,
        parsed=parsed,
        goal_type=goal_type,
        goal_text=goal_text,
        target_lemma=_session_target_lemma(session_dir),
    )
    pr_bound_routes = high_precision_pr_bound_routes(
        source_pr_bounds,
        goal_text=goal_text,
    )
    mechanical_matches = mechanical_goal_candidates(
        lemma_index,
        goal_text=goal_text,
        target_lemma=_session_target_lemma(session_dir),
    )
    one_sided_losslessness = semantic_one_sided_losslessness_candidates(
        lemma_index,
        procedures=_program_call_procedures(program_ir, goal_text=goal_text),
        target_lemma=_session_target_lemma(session_dir),
    )
    distribution_certificates = semantic_distribution_certificates(
        lemma_index,
        goal_text=goal_text,
        target_lemma=_session_target_lemma(session_dir),
    )
    pr_rewrites = _dedupe_strings(
        _candidate_names(parsed.get("pr_rewrite_candidates"))
        + [
            str(item.get("lemma") or item.get("name") or "")
            for item in source_pr_rewrites
            if isinstance(item, dict)
        ]
    )
    addend_equivs = _mapping_names(parsed.get("addend_equiv_candidates"))
    have_chains = _candidate_names(parsed.get("have_chain_candidates"))
    local_equivs = _candidate_names(parsed.get("local_equiv_context"))
    body_frontend = _procedure_body_frontend(
        parsed,
        goal_type,
        program_ir,
        goal_text,
    )
    return {
        "callable_lemmas": call_handles,
        "semantic_lemma_index": _compact_semantic_lemma_index(lemma_index),
        "mechanical_goal_candidates": mechanical_matches,
        "one_sided_losslessness_candidates": one_sided_losslessness,
        "distribution_certificates": distribution_certificates,
        "pr_rewrite_candidates": pr_rewrites,
        "pr_rewrite_candidate_details": source_pr_rewrites,
        "semantic_pr_bound_candidates": source_pr_bounds,
        "high_precision_pr_bound_routes": pr_bound_routes,
        "pr_byequiv_frontend": _pr_byequiv_frontend(parsed, goal_type),
        "pr_clone_bound_apply_candidates": _pr_clone_bound_apply_candidates(
            parsed,
            goal_type,
            goal_text,
        ),
        "addend_equiv_candidates": addend_equivs,
        "have_chain_candidates": have_chains,
        "local_equiv_context": local_equivs,
        "intro_candidate": _intro_candidate(parsed, goal_type, goal_text),
        "ambient_frontend": _ambient_frontend(parsed, goal_type, goal_text),
        "ambient_named_closers": _ambient_named_closers(
            session_dir,
            parsed,
            goal_type,
            goal_text,
        ),
        "equiv_exact_closers": _equiv_exact_closers(
            session_dir,
            parsed,
            goal_type,
            goal_text,
        ),
        "procedure_body_frontend": body_frontend,
        "probabilistic_vc_frontend": _probabilistic_vc_frontend(
            parsed,
            goal_type,
            program_ir,
            goal_text,
            body_frontend,
        ),
        "adversary_invariant_skeleton": adversary_skeleton,
    }


def _program_call_procedures(
    program_ir: dict[str, Any],
    *,
    goal_text: str = "",
) -> list[str]:
    """Return full call targets, preferring the statement parser over shims.

    Some shallow parser artifacts retain only a functor head in ``procedure``
    (for example ``Adv_MAC_to_F``).  The statement still contains the exact
    target ``Adv_MAC_to_F(A, D2(O).O).guess()``; use that authoritative shape
    for semantic declaration matching without changing ProgramIR's structural
    statement ownership.
    """
    procedures: list[str] = []
    for site in _list(_dict(program_ir).get("call_sites")):
        if not isinstance(site, dict):
            continue
        statement = str(site.get("statement") or site.get("text") or "")
        parsed_call = parse_call_statement(statement) if statement else None
        procedure = str(
            parsed_call.procedure
            if parsed_call and parsed_call.procedure
            else site.get("procedure") or ""
        ).strip()
        if procedure:
            procedures.append(procedure)
    procedures.extend(extract_visible_call_procedures(goal_text))
    return _dedupe_strings(procedures)


def _callable_lemma_handles(parsed: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    mappings = []
    for key in ("call_equiv_candidates", "matching_local_equivs"):
        value = parsed.get(key)
        if isinstance(value, dict):
            mappings.append(value)
        elif isinstance(value, list):
            mappings.append({"": value})
    seen: set[tuple[str, str]] = set()
    for mapping in mappings:
        for proc, names in mapping.items():
            for name in _candidate_names(names):
                key = (str(proc), name)
                if key in seen:
                    continue
                seen.add(key)
                out.append({
                    "lemma": name,
                    "procedure": str(proc),
                    "handle_kind": "call_equiv",
                    "alive": True,
                })
    return out


def _local_equiv_hypothesis_handles(goal_text: str) -> list[dict[str, Any]]:
    """Extract current-goal hypotheses like `H: equiv[ L.f ~ R.f : ...]`.

    These are proof-context values, not global declarations.  They should be
    callable immediately when their procedure pair is at the frontier, and
    they should not require `-sig H`.
    """
    out: list[dict[str, Any]] = []
    for item in _base_local_equiv_hypothesis_handles(goal_text):
        if not isinstance(item, dict):
            continue
        name = str(item.get("lemma") or "")
        lhs = str(item.get("lhs_proc") or "")
        rhs = str(item.get("rhs_proc") or "")
        pre = str(item.get("pre") or "")
        post = str(item.get("post") or "")
        if not name or not lhs or not rhs:
            continue
        out.append({
            "lemma": name,
            "procedure": lhs,
            "procedures": [lhs, rhs],
            "handle_kind": "call_equiv",
            "source": "current_goal_hypothesis",
            "alive": True,
            "declaration": f"{name}: equiv[{lhs} ~ {rhs} : {pre} ==> {post}]",
            "lhs_proc": lhs,
            "rhs_proc": rhs,
            "pre": pre,
            "post": post,
            "invariant_atoms": _oracle_handle_invariant_atoms(pre, post),
        })
    return out


def _intro_candidate(
    parsed: dict[str, Any],
    goal_type: str,
    goal_text: str,
) -> dict[str, Any]:
    if parsed.get("intro_required"):
        prefix = str(parsed.get("intro_prefix") or "").strip()
        tactic = prefix if prefix.endswith(".") else _fresh_intro_tactic(goal_text)
        return {
            "available": True,
            "tactic": tactic,
            "reason": "goal parser reports a leading implication/quantifier",
        }
    if goal_type == "ambient" and _has_top_level_implication(goal_text):
        return {
            "available": True,
            "tactic": _fresh_intro_tactic(goal_text),
            "reason": "ambient goal has a leading implication before the proof judgment",
        }
    return {"available": False}


def _fresh_intro_tactic(goal_text: str) -> str:
    used = _context_names(goal_text)
    quantifier_intro = _quantifier_intro_tactic(goal_text, used)
    if quantifier_intro:
        return quantifier_intro
    return f"move=> {_fresh_name('H', used)}."


def _context_names(goal_text: str) -> set[str]:
    if not goal_text:
        return set()
    header = re.split(r"^-{5,}\s*$", goal_text, maxsplit=1, flags=re.MULTILINE)[0]
    return {
        match.group(1)
        for match in re.finditer(r"(?m)^\s*([A-Za-z_][\w']*)\s*:", header)
    }


def _fresh_name(base: str, used: set[str]) -> str:
    if base not in used:
        return base
    idx = 0
    while f"{base}{idx}" in used:
        idx += 1
    return f"{base}{idx}"


def _quantifier_intro_tactic(goal_text: str, used: set[str]) -> str:
    body = _goal_body(goal_text).lstrip()
    body = re.sub(r"\s+", " ", body)
    if not body.startswith("forall "):
        return ""
    binder_text, rest = _forall_binder_region(body)
    binders = _forall_intro_binders(binder_text, used)
    if not binders:
        return f"move=> {_fresh_name('H', used)}."
    pieces = binders[:]
    if _contains_top_level_implication(rest):
        occupied = used | {_strip_memory_marker(x) for x in pieces}
        pieces.append(_fresh_name("H", occupied))
    return f"move=> {' '.join(pieces)}."


def _forall_binder_region(body: str) -> tuple[str, str]:
    text = body.strip()
    if not text.startswith("forall "):
        return "", ""
    after = text[len("forall "):]
    comma = _first_top_level(after, ",")
    if comma < 0:
        return after.strip(), ""
    return after[:comma].strip(), after[comma + 1 :].strip()


def _forall_intro_binders(binder_text: str, used: set[str]) -> list[str]:
    binders: list[str] = []
    occupied = set(used)
    i = 0
    while i < len(binder_text):
        ch = binder_text[i]
        if ch.isspace():
            i += 1
            continue
        if ch == "&":
            match = re.match(r"&[A-Za-z0-9_][\w']*", binder_text[i:])
            if match:
                token = match.group(0)
                binders.append(token)
                occupied.add(_strip_memory_marker(token))
                i += len(token)
                continue
        if ch == "(":
            end = _matching_delimiter(binder_text, i, "(", ")")
            if end > i:
                chunk = binder_text[i + 1 : end]
                match = re.match(r"\s*([A-Za-z_][\w']*)\b", chunk)
                if match:
                    name = _fresh_name(match.group(1), occupied)
                    binders.append(name)
                    occupied.add(name)
                i = end + 1
                continue
        match = re.match(r"[A-Za-z_][\w']*", binder_text[i:])
        if match:
            name = _fresh_name(match.group(0), occupied)
            binders.append(name)
            occupied.add(name)
            i += len(match.group(0))
            continue
        i += 1
    return binders


def _strip_memory_marker(name: str) -> str:
    return name[1:] if name.startswith("&") else name


def _has_top_level_implication(goal_text: str) -> bool:
    body = _goal_body(goal_text)
    if not body:
        return False
    flat = re.sub(r"\s+", " ", body)
    idx = _first_top_level_implication(flat)
    if idx < 0:
        return False
    prefix = flat[:idx]
    if re.search(r"\bfun\b", prefix):
        return False
    pr_pos = flat.find("Pr[")
    return pr_pos == -1 or idx < pr_pos


def _first_top_level(text: str, token: str) -> int:
    return _top_level_token_index(text, token)


def _ambient_frontend(
    parsed: dict[str, Any],
    goal_type: str,
    goal_text: str,
) -> dict[str, Any]:
    if goal_type != "ambient":
        return {"available": False, "reason": "not_ambient"}
    body = _goal_body(goal_text).strip()
    intro = _intro_candidate(parsed, goal_type, goal_text)
    top_connective = _ambient_top_connective(body)
    residual_like = bool(
        _dict(intro).get("available")
        or ("{1}" in body and "{2}" in body)
        or re.search(r"\b(pre|post)\s*=", body)
    )
    close_tactics = ["auto => />.", "smt()."]
    return {
        "available": True,
        "shape": str(parsed.get("ambient_shape") or "logical"),
        "intro_required": bool(_dict(intro).get("available")),
        "intro_tactic": str(_dict(intro).get("tactic") or ""),
        "top_connective": top_connective,
        "residual_like": residual_like,
        "close_tactics": close_tactics,
        "recommended_order": [
            *(
                ["intro"]
                if _dict(intro).get("available") else
                []
            ),
            *(
                ["split"]
                if top_connective == "conjunction" and not _dict(intro).get("available") else
                []
            ),
            "auto => />",
            "smt",
        ],
    }


def _ambient_named_closers(
    session_dir: str | Path | None,
    parsed: dict[str, Any],
    goal_type: str,
    goal_text: str,
) -> list[dict[str, Any]]:
    if goal_type != "ambient":
        return []
    body = _goal_body(goal_text).strip()
    if not body:
        return []
    names = _ambient_conventional_closer_names(body)
    if not names:
        return []
    found = _source_declarations_by_name(session_dir, names)
    out: list[dict[str, Any]] = []
    for name in names:
        decl = _dict(found.get(name))
        if not decl:
            continue
        out.append({
            "lemma": name,
            "tactic": f"exact: {name}.",
            "source": str(decl.get("source") or ""),
            "source_path": str(decl.get("source_path") or ""),
            "declaration_kind": str(decl.get("declaration_kind") or ""),
            "reason": (
                f"The ambient goal matches the conventional closer `{name}` "
                "already declared in the loaded context."
            ),
        })
    return out[:4]


def _ambient_conventional_closer_names(body: str) -> list[str]:
    text = re.sub(r"\s+", " ", str(body or ""))
    candidates: list[str] = []
    for pattern in (
        r"\bis_lossless\s+([A-Za-z_][A-Za-z0-9_'.]*)\b",
        r"\bislossless\s+([A-Za-z_][A-Za-z0-9_'.]*(?:\([^)]*\))?(?:\.[A-Za-z_][A-Za-z0-9_']*)*)",
    ):
        for match in re.finditer(pattern, text):
            raw = match.group(1)
            leaf = _lemma_leaf(raw).strip("'")
            if not leaf:
                continue
            candidates.extend([
                f"{leaf}_ll",
                f"{leaf}_lossless",
                f"{leaf}_islossless",
            ])
            app_proc = re.match(
                r"([A-Za-z_][A-Za-z0-9_']*)\([^)]*\)\.([A-Za-z_][A-Za-z0-9_']*)",
                raw,
            )
            dotted_proc = re.match(
                r"([A-Za-z_][A-Za-z0-9_']*)\.([A-Za-z_][A-Za-z0-9_']*)$",
                raw,
            )
            proc_match = app_proc or dotted_proc
            if proc_match:
                candidates.extend([
                    f"{proc_match.group(1)}_{proc_match.group(2)}_ll",
                    f"{proc_match.group(1)}_{proc_match.group(2)}_lossless",
                ])
    return _dedupe_strings(candidates)


def _equiv_exact_closers(
    session_dir: str | Path | None,
    parsed: dict[str, Any],
    goal_type: str,
    goal_text: str,
) -> list[dict[str, Any]]:
    return build_equiv_exact_closers(
        session_dir=session_dir,
        parsed=parsed,
        goal_type=goal_type,
        goal_text=goal_text,
    )


def _procedure_body_frontend(
    parsed: dict[str, Any],
    goal_type: str,
    program_ir: dict[str, Any],
    goal_text: str,
) -> dict[str, Any]:
    return build_procedure_body_frontend(
        parsed,
        goal_type,
        program_ir,
        goal_text,
    )


def _probabilistic_vc_frontend(
    parsed: dict[str, Any],
    goal_type: str,
    program_ir: dict[str, Any],
    goal_text: str,
    procedure_frontend: dict[str, Any],
) -> dict[str, Any]:
    return build_probabilistic_vc_frontend(
        parsed,
        goal_type,
        program_ir,
        goal_text,
        procedure_frontend,
    )


def _ambient_top_connective(body: str) -> str:
    text = re.sub(r"\s+", " ", str(body or "")).strip()
    if not text:
        return ""
    implication = _first_top_level_implication(text)
    if implication >= 0:
        text = text[implication + 2 :].strip()
    if _first_top_level(text, "/\\") >= 0 or _first_top_level(text, "&&") >= 0:
        return "conjunction"
    return ""


def _goal_body(goal_text: str) -> str:
    return _pr_goal_body(goal_text)


def _adversary_invariant_skeleton(
    parsed: dict[str, Any],
    goal_type: str,
    program_ir: dict[str, Any],
    call_handles: list[dict[str, Any]],
) -> dict[str, Any]:
    if goal_type not in {"pRHL", "equiv"}:
        return {"available": False}
    oracle_handles = [
        handle for handle in call_handles
        if isinstance(handle, dict)
        and str(handle.get("handle_role") or "") == "oracle_obligation_handle"
    ]
    if not oracle_handles:
        return {"available": False}
    sources = _oracle_obligation_sources(program_ir)
    if not sources:
        return {"available": False}
    invariant_atoms = (
        _adversary_invariant_atoms_from_handles(oracle_handles)
        or _adversary_invariant_atoms(parsed)
    )
    invariant = " /\\ ".join(invariant_atoms) if invariant_atoms else "<adversary invariant>"
    return {
        "available": True,
        "kind": "adversary_call_invariant_skeleton",
        "suggested_invariant": invariant,
        "has_placeholder": "<" in invariant or ">" in invariant,
        "frontier_sources": sources,
        "oracle_obligations": [
            {
                "lemma": str(handle.get("lemma") or ""),
                "procedures": _list(handle.get("procedures")) or [
                    str(handle.get("procedure") or "")
                ],
                "precondition": str(handle.get("pre") or ""),
                "postcondition": str(handle.get("post") or ""),
                "invariant_atoms": _list(handle.get("invariant_atoms")),
                "expected_tactic": f"call {handle.get('lemma')}.",
                "source": str(handle.get("source") or ""),
            }
            for handle in oracle_handles
            if str(handle.get("lemma") or "")
        ],
        "why": (
            "The current frontier is an abstract adversary call; local oracle "
            "equiv handles become obligations generated by that call."
        ),
    }


def _oracle_obligation_sources(program_ir: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for site in _list(_dict(program_ir).get("call_sites")):
        if not isinstance(site, dict):
            continue
        if str(site.get("frontier_role") or "") != "oracle_obligation_source":
            continue
        out.append({
            "call_site_id": str(site.get("call_site_id") or ""),
            "side": str(site.get("side") or ""),
            "procedure": str(site.get("procedure") or ""),
            "call_boundary_kind": str(site.get("call_boundary_kind") or ""),
            "frontier_role": str(site.get("frontier_role") or ""),
        })
    return out


def _adversary_invariant_atoms(parsed: dict[str, Any]) -> list[str]:
    atoms: list[str] = []
    for key in ("pre", "post"):
        text = str(parsed.get(key) or "")
        for atom in _split_relational_atoms(text):
            if _adversary_invariant_atom_worth_keeping(atom):
                atoms.append(atom)
    return _dedupe_strings(atoms[:6])


def _adversary_invariant_atoms_from_handles(
    oracle_handles: list[dict[str, Any]],
) -> list[str]:
    atoms: list[str] = []
    for handle in oracle_handles:
        if not isinstance(handle, dict):
            continue
        atoms.extend([
            str(atom) for atom in _list(handle.get("invariant_atoms"))
            if str(atom)
        ])
        if not handle.get("invariant_atoms"):
            atoms.extend(_oracle_handle_invariant_atoms(
                str(handle.get("pre") or ""),
                str(handle.get("post") or ""),
            ))
    return _dedupe_strings(atoms[:6])


def _oracle_handle_invariant_atoms(pre: str, post: str) -> list[str]:
    atoms: list[str] = []
    for text in (pre, post):
        for atom in _split_relational_atoms(text):
            if _oracle_handle_atom_worth_keeping(atom):
                atoms.append(atom)
    return _dedupe_strings(atoms)


def _oracle_handle_atom_worth_keeping(atom: str) -> bool:
    clean = atom.strip()
    if not clean or clean in {"true", "false"}:
        return False
    if re.search(r"\b(arg|res)\{[12]\}", clean):
        return False
    if clean in {"={arg}", "={res}", "={arg, res}", "={res, arg}"}:
        return False
    return bool(
        "glob" in clean
        or clean.startswith("I ")
        or re.match(r"^[A-Za-z_][A-Za-z0-9_']*\s*\(", clean)
        or clean.startswith("={")
    )


def _split_relational_atoms(text: str) -> list[str]:
    clean = re.sub(r"^\s*(pre|post)\s*=\s*", "", text.strip())
    if not clean:
        return []
    return [
        _strip_outer_parens(piece.strip())
        for piece in _split_flat_conjuncts(clean, include_double_escaped=False)
        if _strip_outer_parens(piece.strip())
    ]


def _adversary_invariant_atom_worth_keeping(atom: str) -> bool:
    if not atom:
        return False
    return bool(
        "glob" in atom
        or "{m}" in atom
        or re.search(r"\b[A-Z][A-Za-z0-9_'.]*\.[A-Za-z0-9_']+\{[12]\}", atom)
        or atom.startswith("I ")
        or atom.startswith("={")
    )


def _pr_byequiv_frontend(parsed: dict[str, Any], goal_type: str) -> dict[str, Any]:
    if str(goal_type or parsed.get("goal_type") or "") not in {
        "probability",
        "Pr_eq",
        "Pr_ineq",
    }:
        return {}
    form = str(parsed.get("prob_form") or "")
    if form not in {"eq", ""} and "ineq" not in form:
        return {}
    suggested = " ".join(str(item) for item in _legacy_shape_tactic_templates(parsed))
    strategy = str(parsed.get("strategy_hint") or "")
    if "byequiv" not in suggested and strategy != "byequiv":
        return {}
    shape = "inequality" if "ineq" in form else "equality"
    return {
        "available": True,
        "reason": (
            f"The Pr parser recognizes this as a probability {shape} that can "
            "be approached either through matching Pr handles or through pRHL."
        ),
    }


def _pr_clone_bound_apply_candidates(
    parsed: dict[str, Any],
    goal_type: str,
    goal_text: str,
) -> list[dict[str, Any]]:
    if str(goal_type or parsed.get("goal_type") or "") != "probability":
        return []
    if "Pr[" not in str(goal_text or ""):
        return []
    memory = _first_memory_name(goal_text) or "&m"
    out: list[dict[str, Any]] = []
    for wrapper in _clone_wrapper_terms(goal_text):
        root = str(wrapper.get("root") or "")
        wrapper_name = str(wrapper.get("wrapper") or "")
        arg = str(wrapper.get("arg") or "")
        if not root or not wrapper_name or not arg:
            continue
        # EasyCrypt clone reductions commonly expose theorem names as
        # Root.Conclusion_<wrapper>.  Treat the candidate as a typed strategy
        # hint; the prover should still inspect the declaration if arity is
        # surprising.
        lemma = f"{root}.Conclusion_{wrapper_name}"
        out.append({
            "lemma": lemma,
            "wrapper": wrapper_name,
            "root": root,
            "arg": arg,
            "memory": memory,
            "tactic": f"apply/({lemma} {arg} _ {memory}).",
            "reason": (
                f"The Pr bound goal contains cloned wrapper `{root}.{wrapper_name}({arg})`; "
                f"`{lemma}` is the conventional bound theorem shape for that wrapper."
            ),
        })
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in out:
        key = str(item.get("tactic") or "")
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped[:4]


def _clone_wrapper_terms(goal_text: str) -> list[dict[str, str]]:
    text = str(goal_text or "")
    out: list[dict[str, str]] = []
    pattern = re.compile(
        r"\b(?P<root>[A-Z][A-Za-z0-9_']*)\."
        r"(?P<wrapper>[A-Z][A-Za-z0-9_']*Bounder)\s*\("
    )
    for match in pattern.finditer(text):
        open_idx = match.end() - 1
        close_idx = _matching_bracket(text, open_idx, "(", ")")
        if close_idx <= open_idx:
            continue
        arg = re.sub(r"\s+", "", text[open_idx + 1:close_idx]).strip()
        if not arg:
            continue
        out.append({
            "root": match.group("root"),
            "wrapper": match.group("wrapper"),
            "arg": arg,
        })
    return out


def _first_memory_name(goal_text: str) -> str:
    match = re.search(r"@\s*(&[A-Za-z_][A-Za-z0-9_']*)\b", str(goal_text or ""))
    return match.group(1) if match else ""


def _source_call_equiv_handles(
    session_dir: str | Path | None,
    program_ir: dict[str, Any],
) -> list[dict[str, Any]]:
    """Discover generic call-level equiv lemmas from current context/source.

    This is intentionally shallow: it only turns a declaration into a handle
    when its equiv conclusion names procedure templates that match a live call
    site shape.  Local declarations in the raw source file are ignored unless
    they are in context.ec, because EasyCrypt local section names may no
    longer be in scope at the current lemma.
    """
    call_sites = [
        site for site in _list(_dict(program_ir).get("call_sites"))
        if isinstance(site, dict) and str(site.get("procedure") or "")
    ]
    if not call_sites:
        return []
    handles: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in _source_equiv_declarations(session_dir):
        lemma = str(item.get("lemma") or "")
        lhs = str(item.get("lhs_proc") or "")
        rhs = str(item.get("rhs_proc") or "")
        if not lemma or not lhs:
            continue
        matched = [
            site for site in call_sites
            if (
                _procedure_template_matches(lhs, str(site.get("procedure") or ""))
                or _procedure_template_matches(rhs, str(site.get("procedure") or ""))
            )
        ]
        if not matched:
            continue
        procedure = str(matched[0].get("procedure") or lhs)
        key = (lemma, procedure)
        if key in seen:
            continue
        seen.add(key)
        handles.append({
            "lemma": lemma,
            "procedure": procedure,
            "procedures": [lhs, rhs] if rhs else [lhs],
            "handle_kind": "call_equiv",
            "source": "source_equiv_declaration",
            "alive": True,
            "declaration": str(item.get("declaration") or ""),
            "lhs_proc": lhs,
            "rhs_proc": rhs,
        })
        if len(handles) >= 8:
            break
    return handles


def _source_pr_rewrite_handles(
    session_dir: str | Path | None,
    parsed: dict[str, Any],
    goal_text: str,
    *,
    pr_normal_form: dict[str, Any] | None = None,
    semantic_lemma_index: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    if str(parsed.get("goal_type") or "") != "probability":
        return []
    if _dict(pr_normal_form).get("available"):
        return []
    lemma_index = (
        semantic_lemma_index
        if isinstance(semantic_lemma_index, dict) else
        build_semantic_lemma_index(session_dir)
    )
    return semantic_pr_rewrite_candidates(
        lemma_index,
        parsed=parsed,
        goal_text=goal_text,
        target_lemma=_session_target_lemma(session_dir),
    )


def _source_declarations_by_name(
    session_dir: str | Path | None,
    names: list[str],
) -> dict[str, dict[str, str]]:
    return _lemma_index_source_declarations_by_name(
        build_semantic_lemma_index(session_dir),
        names,
    )


def _procedure_template_matches(template: str, concrete: str) -> bool:
    return _procedure_template_matches_with_key(
        template,
        concrete,
        key=_proc_signature_key,
    )


def _proc_signature_key(proc: str) -> str:
    text = re.sub(r"\s+", "", str(proc or ""))
    if not text:
        return ""
    # Strip balanced (possibly nested) module-application args so that a local
    # oracle-equiv lemma's qualified procedure and the live call-site procedure
    # compare equal:
    #   Impl(Wrap.OCC(I0)).f   ->  Impl.f        (== call site)
    #   Adv(A, Blk).O.Impl.f   ->  Adv.O.Impl.f  (== call site)
    # The previous split-on-first-dot landed *inside* dotted module args
    # (e.g. `Wrap.OCC`) and dropped middle path segments, so qualified
    # call-equiv lemmas never matched their call sites and `call_site_options`
    # reported `wrapper_layer_no_named_handle`.
    out: list[str] = []
    depth = 0
    for ch in text:
        if ch == "(":
            depth += 1
        elif ch == ")":
            if depth:
                depth -= 1
        elif depth == 0:
            out.append(ch)
    return "".join(out)


def _mapping_names(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, dict):
        return []
    out: list[dict[str, str]] = []
    for key, names in value.items():
        for name in _candidate_names(names):
            out.append({"subject": str(key), "lemma": name})
    return out


def _compact_semantic_lemma_index(index: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(index, dict):
        return {}
    items: list[dict[str, Any]] = []
    for item in _list(index.get("items")):
        if not isinstance(item, dict):
            continue
        tags = [
            str(tag) for tag in _list(item.get("semantic_tags"))
            if str(tag)
        ]
        if not tags:
            continue
        items.append({
            "lemma": str(item.get("lemma") or ""),
            "declaration_kind": str(item.get("declaration_kind") or ""),
            "source": str(item.get("source") or ""),
            "source_path": str(item.get("source_path") or ""),
            "fact_source": str(item.get("fact_source") or ""),
            "authority": str(item.get("authority") or ""),
            "authority_rank": int(item.get("authority_rank") or 0),
            "ec_ground_truth": bool(item.get("ec_ground_truth")),
            "semantic_tags": tags,
            "pr_game_keys": [
                str(key) for key in _list(item.get("pr_game_keys"))[:4]
                if str(key)
            ],
            "pr_events": [
                str(event) for event in _list(item.get("pr_events"))[:4]
                if str(event)
            ],
        })
        if len(items) >= 12:
            break
    return {
        "schema_version": int(index.get("schema_version") or 0),
        "kind": str(index.get("kind") or ""),
        "summary": dict(index.get("summary") or {}),
        "items": items,
    }


class _Handles(dict):
    """The proof-handles accumulator for ``build_proof_ir``.

    A plain ``dict`` during the PASS 2/3 mutation phase (the ~18 writes between
    lines 284-417, all routed through ``__setitem__`` so the write surface lives
    in one place). ``freeze()`` marks the end of writes; once frozen a write
    raises — making "PASS 4 (menu / phase / diagnostics) is read-only" an
    *enforceable* invariant rather than an implicit one (the property the future
    per-pass carving depends on). It serializes identically to a ``dict``, so the
    panel-published ``resources.handles`` stays byte-identical. The freeze is
    scoped to ``build_proof_ir`` (``thaw``-ed before return) so downstream
    consumers that still mutate the handles dict (e.g.
    ``session_workspace_view_manager``) are unaffected.
    """

    _frozen = False

    def freeze(self) -> "_Handles":
        self._frozen = True
        return self

    def thaw(self) -> "_Handles":
        self._frozen = False
        return self

    def __setitem__(self, key, value):
        if self._frozen:
            raise RuntimeError(
                f"proof handles are frozen (PASS 4 is read-only); attempted "
                f"write to {key!r}"
            )
        super().__setitem__(key, value)


def _build_proof_handles(
    *,
    parsed: dict[str, Any],
    goal_type: str,
    goal_text: str,
    program_ir: dict[str, Any],
    pr_normal_form: dict[str, Any],
    session_dir: str | Path | None,
    latest_transition: dict[str, Any],
    external_recommendations: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """PASS 2 — build the proof-handle accumulator and enrich it with the
    derived resources (PR decomposition-bridge obligation, external candidates,
    invariant skeleton, program-edit/native-AST search, name resolution +
    instantiation bindings, typed PR bridge frontend, PR path plan, obligation
    plan). Returns the still-mutable handles plus the resource locals the later
    passes and the result dict consume."""
    handles = _Handles(_proof_handles(
        parsed,
        goal_type,
        program_ir=program_ir,
        goal_text=goal_text,
        session_dir=session_dir,
        pr_normal_form=pr_normal_form,
    ))
    pr_bridge_obligation = _pr_decomposition_bridge_obligation(
        latest_transition,
        parsed,
        goal_type,
    )
    handles["pr_decomposition_bridge_obligation"] = pr_bridge_obligation
    if pr_bridge_obligation.get("available"):
        explicit_pr_rewrites = set(_candidate_names(parsed.get("pr_rewrite_candidates")))
        scored_pr_rewrites = {
            str(item.get("lemma") or item.get("name") or ""): int(item.get("score") or 0)
            for item in _list(handles.get("pr_rewrite_candidate_details"))
            if isinstance(item, dict)
        }
        handles["pr_rewrite_candidates"] = [
            lemma for lemma in _list(handles.get("pr_rewrite_candidates"))
            if str(lemma) in explicit_pr_rewrites
            or int(scored_pr_rewrites.get(str(lemma), 0)) >= 12
        ]
    external_candidates = _external_candidates(external_recommendations or [])
    invariant_skeleton = _invariant_skeleton(parsed, goal_type)
    handles["invariant_skeleton"] = invariant_skeleton
    handles["external_candidates"] = external_candidates
    handles["pr_normal_form"] = pr_normal_form
    handles["program_edit_script_action"] = _program_edit_script_action(program_ir)
    handles["native_ast_search"] = _native_ast_search_frontend(
        session_dir=session_dir,
        parsed=parsed,
        goal_type=goal_type,
        goal_text=goal_text,
    )
    handles["unfoldable_goal_heads"] = resolve_goal_unfoldable_names(
        session_dir=session_dir,
        goal_text=goal_text,
    )
    name_resolution = resolve_proof_ir_names(
        session_dir=session_dir,
        handles=handles,
    )
    instantiation_bindings = build_instantiation_bindings(
        session_dir=session_dir,
        parsed_goal=parsed,
        name_resolution=name_resolution,
        goal_text=goal_text,
    )
    handles["name_resolution"] = name_resolution
    handles["instantiation_bindings"] = instantiation_bindings
    _annotate_call_handle_candidate_kinds(handles)
    pr_typed_bridge_frontend = build_pr_typed_bridge_frontend(
        session_dir=session_dir,
        goal_text=goal_text,
        handles=handles,
        instantiation_bindings=instantiation_bindings,
    )
    handles["pr_typed_bridge_frontend"] = pr_typed_bridge_frontend
    pr_path_input = dict(parsed)
    pr_path_input["goal_text"] = goal_text
    pr_path_input["resolved_name_items"] = _list(name_resolution.get("items"))
    pr_path_input["external_candidates"] = external_candidates
    pr_path_input["synthetic_pr_bridge_candidates"] = _list(
        pr_typed_bridge_frontend.get("wrapper_bridges")
    )
    pr_path_input["instantiated_pr_rewrite_candidates"] = _list(
        pr_typed_bridge_frontend.get("instantiated_rewrites")
    )
    pr_path_plan = build_pr_path_plan(pr_path_input)
    handles["pr_path_plan"] = pr_path_plan
    handles["pr_wrapper_bridge_candidates"] = build_pr_wrapper_bridge_candidates(
        parsed,
        goal_text,
        handles,
        pr_path_plan,
    )
    handles["pr_obligation_plan"] = build_pr_obligation_plan(
        parsed=parsed,
        goal_type=goal_type,
        goal_text=goal_text,
        pr_normal_form=pr_normal_form,
        pr_path_plan=pr_path_plan,
        semantic_pr_bound_candidates=_list(
            handles.get("semantic_pr_bound_candidates")
        ),
        native_ast_search=_dict(handles.get("native_ast_search")),
    )
    return {
        "handles": handles,
        "external_candidates": external_candidates,
        "invariant_skeleton": invariant_skeleton,
        "name_resolution": name_resolution,
        "instantiation_bindings": instantiation_bindings,
        "pr_path_plan": pr_path_plan,
    }


def _external_candidates(recommendations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for rec in recommendations:
        if not isinstance(rec, dict):
            continue
        action = str(rec.get("action") or "").strip()
        if not action or action in seen:
            continue
        seen.add(action)
        family = _external_tactic_family(rec)
        cost = _family_cost(family, rec)
        candidate = {
            "id": str(rec.get("id") or f"external.{len(out)}"),
            "producer": str(rec.get("producer") or rec.get("source") or ""),
            "action": action,
            "tactic": _extract_tactic_from_action(action),
            "tactic_family": family,
            "action_type": str(rec.get("action_type") or ""),
            "confidence": str(rec.get("confidence") or ""),
            "verified": _is_verified_recommendation(rec),
            "cost": cost,
            "layer": _family_layer(family),
            "cost_factors": _family_cost_factors(family, rec),
        }
        if family == "realignment_swap":
            candidate["structural_swap"] = realigning_swap_contract(
                str(candidate.get("tactic") or "")
            )
        out.append(normalize_action_candidate(candidate))
    return out


def _external_tactic_family(rec: dict[str, Any]) -> str:
    action = str(rec.get("action") or "")
    metadata = _dict(rec.get("metadata"))
    producer = str(rec.get("producer") or "").lower()
    kind = str(rec.get("kind") or "").lower()
    tactic = _extract_tactic_from_action(action).strip()
    low = tactic.lower()
    if re.match(r"^move\s*=>\b|^move=>\b|^move\b", tactic):
        return "intro"
    if re.match(r"^(?:eager\s+)?proc\b", low):
        return "proc_open"
    if re.match(r"^byphoare\b", low):
        return "probability_to_program"
    if re.match(r"^bypr\b|^byequiv\b", low):
        return "probability_to_program"
    if re.match(r"^-search-skeleton\b", low) or producer == "search-skeleton":
        return "native_ast_search"
    if re.match(r"^-where\s+[A-Za-z_][\w'.]*\s*$", low):
        return "signature_lookup"
    if re.match(r"^(?:apply|exact)\s+\(?\s*[A-Za-z_][\w'.]*", low):
        return "pr_path_plan"
    if re.match(r"^have\s+(?:[A-Za-z_][\w']*\s*:\s*|:=)", low):
        return "pr_path_plan"
    if re.match(r"^e?call\s*\(_:", tactic):
        return "call_invariant_skeleton"
    if "call-ready" in producer or re.match(r"^e?call\s+[A-Za-z_][\w'.]*\s*\.$", tactic):
        return "call_named_equiv"
    if "auto-bridge" in producer or metadata.get("bridge_kind") or "bridge" in kind:
        return "pr_bridge"
    if re.match(r"^rewrite\b", low):
        return "rewrite"
    if re.match(r"^-sig\b", low):
        return "signature_lookup"
    if re.match(r"^inline\s+\*\s*\.$", low):
        return "inline_all"
    if re.match(r"^inline\b", low):
        return "targeted_inline"
    if re.match(r"^swap\b", low):
        return "realignment_swap"
    if re.match(
        r"^(wp|sp|seq|splitwhile|while|if|rnd|rcondt|rcondf|skip|conseq)\b|^case:",
        low,
    ):
        return "procedure_transform"
    if re.match(r"^(auto|smt)\b", low):
        return "ambient_close"
    return "unknown"


def _family_layer(family: str) -> str:
    if family == "intro":
        return "proof_context"
    if family == "proc_open":
        return "prhl_module"
    if family in {"pr_bridge", "pr_path_plan", "probabilistic_vc", "rewrite"}:
        return "pr"
    if family == "probability_to_program":
        return "pr"
    if family == "instantiated_template":
        return "resolved_action"
    if family == "signature_lookup":
        return "name_resolution"
    if family == "native_ast_search":
        return "name_resolution"
    if family == "call_named_equiv":
        return "call_site"
    if family == "call_invariant_skeleton":
        return "call_site"
    if family in {"targeted_inline", "inline_all", "procedure_transform", "realignment_swap"}:
        return "procedure_body"
    if family == "ambient_close":
        return "ambient_logic"
    return "unknown"


def _family_cost(family: str, rec: dict[str, Any]) -> str:
    metadata = _dict(rec.get("metadata"))
    if metadata.get("cost"):
        return str(metadata.get("cost"))
    if family in {
        "call_named_equiv",
        "call_invariant_skeleton",
        "instantiated_template",
        "intro",
        "proc_open",
        "probability_to_program",
        "pr_path_plan",
        "rewrite",
    }:
        return "cheap"
    if family == "signature_lookup":
        return "free"
    if family == "native_ast_search":
        return "cheap"
    if family == "pr_bridge":
        return "cheap" if metadata.get("bridge_kind") == "single" else "moderate"
    if family == "pr_path_plan":
        return "moderate"
    if family == "probabilistic_vc":
        return "moderate"
    if family == "targeted_inline":
        return "moderate"
    if family == "inline_all":
        return "expensive"
    if family in {"procedure_transform", "ambient_close"}:
        return "cheap"
    return "unknown"


def _family_cost_factors(family: str, rec: dict[str, Any]) -> dict[str, Any]:
    if family == "inline_all":
        return {
            "expansion": "high",
            "irreversibility": "high",
            "lost_handles": "unknown_until_liveness",
        }
    if family == "call_named_equiv":
        return {
            "expansion": "low",
            "irreversibility": "low",
            "lost_handles": 0,
        }
    if family == "call_invariant_skeleton":
        return {
            "expansion": "medium",
            "irreversibility": "low",
            "lost_handles": 0,
        }
    if family == "instantiated_template":
        return {
            "expansion": "low",
            "irreversibility": "low",
            "lost_handles": 0,
        }
    if family == "signature_lookup":
        return {
            "expansion": "none",
            "irreversibility": "none",
            "lost_handles": 0,
        }
    if family == "native_ast_search":
        return {
            "expansion": "none",
            "irreversibility": "none",
            "lost_handles": 0,
        }
    if family == "intro":
        return {
            "expansion": "none",
            "irreversibility": "low",
            "lost_handles": 0,
        }
    if family == "proc_open":
        return {
            "expansion": "low",
            "irreversibility": "low",
            "lost_handles": 0,
        }
    if family == "probability_to_program":
        return {
            "expansion": "medium",
            "irreversibility": "medium",
            "lost_handles": 0,
        }
    if family == "pr_bridge":
        metadata = _dict(rec.get("metadata"))
        return {
            "expansion": "low" if metadata.get("bridge_kind") == "single" else "medium",
            "irreversibility": "low",
            "lost_handles": 0,
        }
    if family == "pr_path_plan":
        return {
            "expansion": "low",
            "irreversibility": "low",
            "lost_handles": 0,
        }
    return {}


def _is_verified_recommendation(rec: dict[str, Any]) -> bool:
    metadata = _dict(rec.get("metadata"))
    return (
        str(rec.get("confidence") or "") == "verified"
        or str(metadata.get("epistemic_status") or "") == "easycrypt_preflight_accepted"
        or metadata.get("daemon_verified") is True
    )


def _invariant_skeleton(parsed: dict[str, Any], goal_type: str) -> dict[str, Any]:
    return build_invariant_skeleton(parsed, goal_type)


def _annotate_call_handle_candidate_kinds(handles: dict[str, Any]) -> None:
    name_resolution = _dict(handles.get("name_resolution"))
    instantiation_bindings = _dict(handles.get("instantiation_bindings"))
    out: list[dict[str, Any]] = []
    for handle in _list(handles.get("callable_lemmas")):
        if not isinstance(handle, dict):
            continue
        item = dict(handle)
        lemma = str(item.get("lemma") or "")
        resolved = resolution_for_name(name_resolution, lemma)
        binding = binding_for_name(instantiation_bindings, lemma)
        exact_signature_known = bool(resolved.get("exact_signature_known"))
        requires_instantiation = exact_signature_known and bool(
            resolved.get("requires_instantiation")
        )
        instantiated_templates = _list(binding.get("instantiated_templates"))
        resolution_status = str(resolved.get("resolution_status") or "")
        item["call_candidate_kind"] = _call_handle_candidate_kind(
            item,
            resolved=resolved,
            resolution_status=resolution_status,
            exact_signature_known=exact_signature_known,
            requires_instantiation=requires_instantiation,
            instantiated_templates=instantiated_templates,
        )
        out.append(item)
    handles["callable_lemmas"] = out


def _pr_decomposition_bridge_obligation(
    latest_transition: dict[str, Any],
    parsed: dict[str, Any],
    goal_type: str,
) -> dict[str, Any]:
    tactic = str(latest_transition.get("tactic") or "").strip()
    if not re.match(r"^\+?\s*have\b", tactic):
        return {}
    if str(goal_type or parsed.get("goal_type") or "") not in {
        "probability",
        "Pr_eq",
    }:
        return {}
    if str(parsed.get("prob_form") or "") not in {"eq", ""}:
        return {}
    suggested = " ".join(str(item) for item in _legacy_shape_tactic_templates(parsed))
    strategy = str(parsed.get("strategy_hint") or "")
    if "byequiv" not in suggested and strategy != "byequiv":
        return {}
    goals_after = int(latest_transition.get("goals_after") or 0)
    goals_before = int(latest_transition.get("goals_before") or 0)
    if goals_after and goals_before and goals_after <= goals_before:
        return {}
    return {
        "available": True,
        "reason": (
            "The previous `have` opened a Pr equality bridge obligation; "
            "prove this local bridge directly before following future Pr "
            "rewrite/path candidates."
        ),
    }


def _native_ast_search_frontend(
    *,
    session_dir: str | Path | None,
    parsed: dict[str, Any],
    goal_type: str,
    goal_text: str,
) -> dict[str, Any]:
    return build_native_ast_search_frontend(
        session_dir=session_dir,
        parsed=parsed,
        goal_type=goal_type,
        goal_text=goal_text,
    )
