"""Static name-resolution pass for EasyCrypt proof handles.

This module is the compiler-style symbol-resolution layer for ProofIR.  It
does not run EasyCrypt and does not decide tactics.  Instead, it resolves names
that earlier passes surfaced as useful handles into structured facts:

* where the name appears to come from
* whether an exact local declaration/signature is available
* whether a ``-sig`` lookup should precede direct use
* which low-level tactic template the resolved handle corresponds to
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.easycrypt.analysis.ec_utils import (
    as_dict as _dict,
    as_list as _list,
    candidate_names as _candidate_names,
    dedupe_strings as _dedupe_strings,
    drop_empty as _drop_empty,
    session_source_files as _context_files,
    split_top_level_at as _split_top_level_at,
    unqualified as _unqualified,
)

try:
    from core.easycrypt.ec_static_context import (
        analyze_ec_scope_context,
        is_cloned_theory_lemma,
    )
except Exception:  # Script/session_cli import path.
    try:
        from core.easycrypt.ec_static_context import (  # type: ignore
            analyze_ec_scope_context,
            is_cloned_theory_lemma,
        )
    except Exception:  # pragma: no cover - defensive import fallback.
        analyze_ec_scope_context = None  # type: ignore
        is_cloned_theory_lemma = None  # type: ignore


NAME_RESOLUTION_SCHEMA_VERSION = 1
NAME_RESOLUTION_KIND = "easycrypt_name_resolution"

_DECL_HEAD_RE = re.compile(
    r"\b(?P<local>local\s+)?(?P<kind>equiv|lemma|axiom)\s+"
    r"(?P<name>[A-Za-z_][A-Za-z0-9_']*)(?![A-Za-z0-9_'])",
    re.MULTILINE,
)
_UNFOLDABLE_DECL_HEAD_RE = re.compile(
    r"(?m)^\s*(?P<local>local\s+)?(?P<kind>op|pred|abbrev)\s+"
    r"(?:\[[^\]]+\]\s+)?(?P<name>[A-Za-z_][A-Za-z0-9_']*)(?![A-Za-z0-9_'])",
)
_GOAL_NAME_RE = re.compile(
    # Trailing boundary must allow a closing prime: `…\b` cannot match after a
    # non-word `'`, so it would drop the prime from a goal-side ref like `foo'`.
    r"\b[A-Za-z_][A-Za-z0-9_']*(?:\.[A-Za-z_][A-Za-z0-9_']*)*(?![A-Za-z0-9_'])"
)
_GOAL_NAME_IGNORE = frozenset({
    "Current", "Type", "variables", "none", "forall", "exists", "fun",
    "true", "false", "witness", "pre", "post", "res", "left", "right",
    "int", "bool", "unit", "real", "glob",
})


@dataclass(frozen=True)
class _Declaration:
    name: str
    kind: str
    declaration: str
    source_path: str
    source_kind: str = "local_context"
    parameters: tuple[str, ...] = ()
    lhs_proc: str = ""
    rhs_proc: str = ""
    # An op/pred is delta-unfoldable (`rewrite /X`) ONLY if it has a definitional
    # body (`= ...`). An abstract `op f : T.` cannot be unfolded. Default True so
    # an ambiguous parse never HIDES a genuinely unfoldable definition.
    has_body: bool = True


def _declaration_has_body(region: str) -> bool:
    """True iff this op/pred declaration carries a definitional `= body`.

    `region` starts at the `op`/`pred`/`abbrev` keyword and may run past the
    statement.  We scan to the first statement-terminating `.` (a `.` at
    bracket-depth 0 followed by whitespace/EOF) and report whether a top-level
    `=` (not `=>`, `<=`, `>=`, `:=`, `<>`) appeared before it.  Conservative: if
    no terminator is found, assume a body is present.
    """
    region = re.sub(r"\(\*.*?\*\)", " ", region, flags=re.DOTALL)
    depth = 0
    saw_eq = False
    n = len(region)
    for i, c in enumerate(region):
        if c in "([{":
            depth += 1
        elif c in ")]}":
            depth = max(0, depth - 1)
        elif depth == 0:
            if c == "=":
                nxt = region[i + 1] if i + 1 < n else ""
                prev = region[i - 1] if i > 0 else ""
                if nxt != ">" and prev not in "<>!:=":
                    saw_eq = True
            elif c == "." and (i + 1 >= n or region[i + 1].isspace()):
                return saw_eq
    return True


def resolve_proof_ir_names(
    *,
    session_dir: str | Path | None = None,
    handles: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve ProofIR handles against local context/source declarations."""
    handle_map = _dict(handles)
    context_files = _context_files(session_dir)
    declarations = _scan_declarations(context_files)
    signature_declarations, signature_artifacts = _scan_signature_tool_views(
        session_dir,
    )
    for name, declaration in signature_declarations.items():
        declarations.setdefault(name, declaration)
    where_declarations, where_artifacts = _scan_where_tool_views(session_dir)
    for name, declaration in where_declarations.items():
        # `-where` is clone-resolved and often contains section-exported
        # parameters that the legacy `-sig` formatter omits. Prefer it.
        declarations[name] = declaration
    signature_artifacts.extend(where_artifacts)
    scope_context = _scope_context(context_files)
    inputs = _handle_inputs(handle_map)

    items: list[dict[str, Any]] = []
    lookup_actions: list[str] = []
    for handle in inputs:
        name = str(handle.get("name") or "").strip()
        if not name:
            continue
        item = _resolve_one(handle, declarations, scope_context)
        items.append(item)
        action = str(item.get("signature_lookup_action") or "")
        if action and item.get("resolution_status") not in {
            "resolved_local_declaration",
            "resolved_signature_lookup",
            "resolved_goal_hypothesis",
        }:
            lookup_actions.append(action)

    summary = _summary(items)
    return {
        "schema_version": NAME_RESOLUTION_SCHEMA_VERSION,
        "kind": NAME_RESOLUTION_KIND,
        "context_files": [str(path) for path in context_files],
        "signature_artifacts": signature_artifacts,
        "summary": summary,
        "items": items,
        "lookup_actions": _dedupe_strings(lookup_actions),
    }


def resolution_for_name(
    name_resolution: dict[str, Any],
    name: str,
) -> dict[str, Any]:
    """Return the first name-resolution item for ``name``."""
    if not name:
        return {}
    target = _unqualified(name)
    for item in _list(_dict(name_resolution).get("items")):
        if not isinstance(item, dict):
            continue
        if str(item.get("name") or "") == name:
            return item
        if _unqualified(str(item.get("name") or "")) == target:
            return item
    return {}


def resolve_goal_unfoldable_names(
    *,
    session_dir: str | Path | None = None,
    goal_text: str = "",
    limit: int = 6,
) -> list[dict[str, Any]]:
    """Return unfoldable op/pred/abbrev heads that occur in the current goal.

    This is source-resolution information, not a tactic recipe.  It helps the
    prover distinguish definitions that should be unfolded with ``rewrite /X``
    from lemmas that may be passed to ``smt(X)``.
    """
    names = _goal_identifier_order(goal_text)
    if not names:
        return []
    # Names invoked as a PROCEDURE (`x <@ Mod.proc(...)`) are call sites, not
    # unfoldable ops — never offer `rewrite /Mod.proc.` for them. Without this, a
    # qualified module procedure like `FinRO.get` (a random-oracle call) falls
    # through the unqualified fallback below and matches an unrelated `op get`,
    # producing a bogus `rewrite /FinRO.get.` next to the call-site panel.
    proc_call_names = set(
        re.findall(r"<@\s*([A-Za-z_][A-Za-z0-9_'.]*)", str(goal_text or ""))
    )
    declarations = _scan_unfoldable_declarations(_context_files(session_dir))
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for name in names:
        if name in proc_call_names:
            continue
        decl = declarations.get(name)
        if decl is None and "." in name:
            decl = declarations.get(_unqualified(name))
        if decl is None:
            continue
        # An abstract (body-less) op/pred cannot be delta-unfolded; offering
        # `rewrite /X` for it is misleading. `abbrev` always carries a body.
        if not decl.has_body and "abbrev" not in decl.kind:
            continue
        display_name = name if "." in name else _unqualified(decl.name)
        key = display_name
        if key in seen:
            continue
        seen.add(key)
        out.append(_drop_empty({
            "name": display_name,
            "unqualified_name": _unqualified(display_name),
            "declaration_kind": decl.kind,
            "source_kind": decl.source_kind,
            "source_path": decl.source_path,
            "fact_source": _decl_fact_source(decl),
            "authority": _decl_authority(decl),
            "authority_rank": _decl_authority_rank(decl),
            "ec_ground_truth": _decl_is_ec_ground_truth(decl),
            "unfold_tactic": f"rewrite /{display_name}.",
            "smt_argument_role": "not_a_lemma_hint",
            "note": (
                "This name resolves as an unfoldable definition in the goal; "
                "do not pass it as an smt(...) lemma argument."
            ),
        }))
        if len(out) >= limit:
            break
    return out


def _decl_is_ec_ground_truth(decl: _Declaration) -> bool:
    return decl.source_kind in {"where_lookup_tool"}


def _decl_fact_source(decl: _Declaration) -> str:
    if decl.source_kind == "where_lookup_tool":
        return "ec_native_print"
    if decl.source_kind == "signature_lookup_tool":
        return "legacy_signature_lookup"
    if decl.source_kind == "source_file_out_of_context":
        return "source_scan_out_of_context"
    return "source_scan"


def _decl_authority(decl: _Declaration) -> str:
    if decl.source_kind == "where_lookup_tool":
        return "ec_native_ground_truth"
    if decl.source_kind == "signature_lookup_tool":
        return "legacy_lookup"
    if decl.source_kind == "source_file_out_of_context":
        return "source_scan_not_current_scope"
    return "source_scan_fallback"


def _decl_authority_rank(decl: _Declaration) -> int:
    if decl.source_kind == "where_lookup_tool":
        return 100
    if decl.source_kind == "signature_lookup_tool":
        return 60
    if decl.source_kind == "source_file_out_of_context":
        return 5
    return 10


def _resolve_one(
    handle: dict[str, Any],
    declarations: dict[str, _Declaration],
    scope_context: Any,
) -> dict[str, Any]:
    name = str(handle.get("name") or "")
    unqualified = _unqualified(name)
    decl = declarations.get(name) or declarations.get(unqualified)
    procedure = str(handle.get("procedure") or "")
    handle_kind = str(handle.get("handle_kind") or "lemma")
    tactic_template = _tactic_template(handle_kind, name)
    signature_lookup_action = f"-where {unqualified or name}"

    base: dict[str, Any] = {
        "name": name,
        "unqualified_name": unqualified,
        "handle_kind": handle_kind,
        "procedure": procedure,
        "source": str(handle.get("source") or ""),
        "handle_fact_source": str(handle.get("fact_source") or ""),
        "handle_authority": str(handle.get("authority") or ""),
        "handle_authority_rank": int(handle.get("authority_rank") or 0),
        "handle_ec_ground_truth": bool(handle.get("ec_ground_truth")),
        "signature_lookup_action": signature_lookup_action,
        "tactic_template": tactic_template,
        "instantiation_candidates": [],
    }
    if str(handle.get("source") or "") == "current_goal_hypothesis":
        lhs_proc = str(handle.get("lhs_proc") or "")
        rhs_proc = str(handle.get("rhs_proc") or "")
        item = {
            **base,
            "resolution_status": "resolved_goal_hypothesis",
            "source_kind": "current_goal_hypothesis",
            "declaration_kind": "hypothesis_equiv",
            "source_path": "current_goal",
            "exact_signature_known": True,
            "declaration": str(handle.get("declaration") or ""),
            "parameters": [],
            "parameter_slots": [],
            "requires_instantiation": False,
            "lhs_proc": lhs_proc,
            "rhs_proc": rhs_proc,
            "procedure_match": _procedure_match(
                procedure,
                _Declaration(
                    name=name,
                    kind="equiv",
                    declaration=str(handle.get("declaration") or ""),
                    source_path="current_goal",
                    source_kind="current_goal_hypothesis",
                    lhs_proc=lhs_proc,
                    rhs_proc=rhs_proc,
                ),
            ),
        }
        return item
    handle_declaration = str(handle.get("declaration") or "")
    if decl is None and handle_declaration:
        return {
            **base,
            "resolution_status": "needs_where_lookup",
            "source_kind": str(handle.get("source") or "source_candidate"),
            "source_path": str(handle.get("source_path") or ""),
            "declaration_kind": str(handle.get("declaration_kind") or "lemma"),
            "fact_source": str(handle.get("fact_source") or "source_scan"),
            "authority": str(handle.get("authority") or "source_scan_fallback"),
            "authority_rank": int(handle.get("authority_rank") or 0),
            "ec_ground_truth": bool(handle.get("ec_ground_truth")),
            "exact_signature_known": False,
            "declaration": handle_declaration,
            "parameters": [],
            "parameter_slots": [],
            "requires_instantiation": True,
            "lhs_proc": str(handle.get("lhs_proc") or ""),
            "rhs_proc": str(handle.get("rhs_proc") or ""),
            "procedure_match": "unknown",
            "instantiation_candidates": [{
                "status": "lookup_first",
                "action": signature_lookup_action,
                "reason": (
                    "A Pr lemma declaration matched the current goal shape, "
                    "but clone/section parameters require `-where` before "
                    "committing a tactic."
                ),
            }],
        }
    if decl is not None:
        if decl.source_kind == "source_file_out_of_context":
            status = (
                "source_local_scope_check_required"
                if str(decl.kind or "").startswith("local_") else
                "source_scope_check_required"
            )
            return {
                **base,
                "resolution_status": status,
                "source_kind": decl.source_kind,
                "source_path": decl.source_path,
                "declaration_kind": decl.kind,
                "fact_source": _decl_fact_source(decl),
                "authority": _decl_authority(decl),
                "authority_rank": _decl_authority_rank(decl),
                "ec_ground_truth": False,
                "exact_signature_known": False,
                "declaration": decl.declaration,
                "parameters": list(decl.parameters),
                "parameter_slots": _parameter_slots(list(decl.parameters)),
                "requires_instantiation": True,
                "lhs_proc": decl.lhs_proc,
                "rhs_proc": decl.rhs_proc,
                "procedure_match": "unknown",
                "instantiation_candidates": [{
                    "status": "scope_check_first",
                    "action": signature_lookup_action,
                    "reason": (
                        "The declaration appears in the source file but not "
                        "in the frozen EasyCrypt context for this session. It "
                        "may be after the target lemma or otherwise out of "
                        "scope; confirm with `-where` before using it."
                    ),
                }],
            }
        if (
            str(handle.get("source") or "") == "external_candidates"
            and str(decl.kind or "").startswith("local_")
        ):
            return {
                **base,
                "resolution_status": "source_local_scope_check_required",
                "source_kind": "source_file_local_declaration",
                "source_path": decl.source_path,
                "declaration_kind": decl.kind,
                "fact_source": _decl_fact_source(decl),
                "authority": _decl_authority(decl),
                "authority_rank": _decl_authority_rank(decl),
                "ec_ground_truth": _decl_is_ec_ground_truth(decl),
                "exact_signature_known": False,
                "declaration": decl.declaration,
                "parameters": list(decl.parameters),
                "parameter_slots": _parameter_slots(list(decl.parameters)),
                "requires_instantiation": True,
                "lhs_proc": decl.lhs_proc,
                "rhs_proc": decl.rhs_proc,
                "procedure_match": "unknown",
                "instantiation_candidates": [{
                    "status": "scope_check_first",
                    "action": signature_lookup_action,
                    "reason": (
                        "The name only appears as a local declaration in the "
                        "source file; verify it is in the current EasyCrypt "
                        "scope before direct use."
                    ),
                }],
            }
        if decl.source_kind == "local_theory_template":
            return {
                **base,
                "resolution_status": "needs_where_lookup",
                "source_kind": decl.source_kind,
                "source_path": decl.source_path,
                "declaration_kind": decl.kind,
                "fact_source": _decl_fact_source(decl),
                "authority": _decl_authority(decl),
                "authority_rank": _decl_authority_rank(decl),
                "ec_ground_truth": _decl_is_ec_ground_truth(decl),
                "exact_signature_known": False,
                "declaration": decl.declaration,
                "parameters": list(decl.parameters),
                "parameter_slots": _parameter_slots(list(decl.parameters)),
                "requires_instantiation": True,
                "lhs_proc": decl.lhs_proc,
                "rhs_proc": decl.rhs_proc,
                "procedure_match": "unknown",
                "instantiation_candidates": [{
                    "status": "lookup_first",
                    "action": signature_lookup_action,
                    "reason": (
                        "The source declaration is inside an EasyCrypt theory "
                        "template; resolve the clone-exported arity with "
                        "`-where` before using it."
                    ),
                }],
            }
        match = _procedure_match(procedure, decl)
        params = list(decl.parameters)
        slots = _parameter_slots(params)
        source_kind = decl.source_kind or "local_context"
        resolution_status = (
            "resolved_signature_lookup"
            if source_kind in {"signature_lookup_tool", "where_lookup_tool"} else
            "resolved_local_declaration"
        )
        item = {
            **base,
            "resolution_status": resolution_status,
            "source_kind": source_kind,
            "declaration_kind": decl.kind,
            "source_path": decl.source_path,
            "fact_source": _decl_fact_source(decl),
            "authority": _decl_authority(decl),
            "authority_rank": _decl_authority_rank(decl),
            "ec_ground_truth": _decl_is_ec_ground_truth(decl),
            "exact_signature_known": True,
            "declaration": decl.declaration,
            "parameters": params,
            "parameter_slots": slots,
            "requires_instantiation": bool(params),
            "lhs_proc": decl.lhs_proc,
            "rhs_proc": decl.rhs_proc,
            "procedure_match": match,
        }
        item["instantiation_candidates"] = _instantiation_candidates(
            item,
            tactic_template=tactic_template,
        )
        return item

    cross, source_hint = _is_cross_scope_name(name, scope_context)
    if cross:
        return {
            **base,
            "resolution_status": "needs_where_lookup",
            "source_kind": "cloned_or_imported_theory",
            "source_hint": source_hint,
            "exact_signature_known": False,
            "requires_instantiation": True,
            "procedure_match": "unknown",
            "instantiation_candidates": [{
                "status": "lookup_first",
                "action": signature_lookup_action,
                "reason": "Name crosses a clone/import boundary; inspect exact arity before applying it.",
            }],
        }

    named_equivs = set(getattr(scope_context, "named_equivs", ()) or ())
    if unqualified in named_equivs:
        return {
            **base,
            "resolution_status": "in_scope_name_without_signature",
            "source_kind": "local_context",
            "exact_signature_known": False,
            "requires_instantiation": True,
            "procedure_match": "unknown",
            "instantiation_candidates": [{
                "status": "lookup_first",
                "action": signature_lookup_action,
                "reason": "Name is in local equiv scope but exact declaration was not recovered.",
            }],
        }

    return {
        **base,
        "resolution_status": "unresolved",
        "source_kind": "unknown",
        "exact_signature_known": False,
        "requires_instantiation": True,
        "procedure_match": "unknown",
        "instantiation_candidates": [{
            "status": "lookup_first",
            "action": signature_lookup_action,
            "reason": "No local declaration was found for this handle.",
        }],
    }

def _scan_declarations(paths: list[Path]) -> dict[str, _Declaration]:
    declarations: dict[str, _Declaration] = {}
    has_frozen_context = any(path.name == "context.ec" for path in paths)
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        in_current_scope = path.name == "context.ec" or not has_frozen_context
        heads = list(_DECL_HEAD_RE.finditer(text))
        for idx, match in enumerate(heads):
            name = match.group("name")
            start = match.start()
            next_start = heads[idx + 1].start() if idx + 1 < len(heads) else len(text)
            proof = re.search(r"\bproof\.", text[match.end():next_start])
            cut = match.end() + proof.start() if proof else next_start
            snippet = _normalize_declaration(text[start:cut])
            existing = declarations.get(name)
            if existing is not None and existing.declaration:
                continue
            source_kind = (
                "local_theory_template"
                if _inside_theory_template(text, start) else
                "local_context"
            )
            if not in_current_scope:
                source_kind = "source_file_out_of_context"
            declarations[name] = _Declaration(
                name=name,
                kind=(
                    ("local_" if match.group("local") else "")
                    + str(match.group("kind") or "")
                ),
                declaration=snippet,
                source_path=str(path),
                source_kind=source_kind,
                parameters=tuple(_parameters(name, snippet)),
                lhs_proc=_equiv_proc(snippet, side="lhs"),
                rhs_proc=_equiv_proc(snippet, side="rhs"),
            )
    return declarations


def _scan_unfoldable_declarations(paths: list[Path]) -> dict[str, _Declaration]:
    declarations: dict[str, _Declaration] = {}
    has_frozen_context = any(path.name == "context.ec" for path in paths)
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        in_current_scope = path.name == "context.ec" or not has_frozen_context
        heads = list(_UNFOLDABLE_DECL_HEAD_RE.finditer(text))
        for idx, match in enumerate(heads):
            name = match.group("name")
            start = match.start()
            next_start = heads[idx + 1].start() if idx + 1 < len(heads) else len(text)
            region = text[start:next_start]
            snippet = _normalize_declaration(region)
            has_body = _declaration_has_body(region)
            existing = declarations.get(name)
            if existing is not None and existing.declaration:
                continue
            source_kind = (
                "local_theory_template"
                if _inside_theory_template(text, start) else
                "local_context"
            )
            if not in_current_scope:
                source_kind = "source_file_out_of_context"
            declarations[name] = _Declaration(
                name=name,
                kind=(
                    ("local_" if match.group("local") else "")
                    + str(match.group("kind") or "")
                ),
                declaration=snippet,
                source_path=str(path),
                source_kind=source_kind,
                parameters=tuple(_parameters(name, snippet)),
                has_body=has_body,
            )
    return declarations


def _inside_theory_template(text: str, index: int) -> bool:
    prefix = text[:max(index, 0)]
    theory_starts = list(re.finditer(
        r"\b(?:abstract\s+)?theory\s+[A-Za-z_][A-Za-z0-9_']*",
        prefix,
    ))
    if not theory_starts:
        return False
    last_start = theory_starts[-1].start()
    tail = prefix[last_start:]
    # EasyCrypt closes theories with `end <name>.`; a later end means this
    # declaration is no longer in the template whose raw section parameters
    # may be clone-exported under a different arity.
    return not bool(re.search(r"\bend\s+[A-Za-z_][A-Za-z0-9_']*\s*\.", tail))


def _scan_signature_tool_views(
    session_dir: str | Path | None,
) -> tuple[dict[str, _Declaration], list[str]]:
    if session_dir is None:
        return ({}, [])
    root = Path(session_dir) / "tool_views"
    if not root.exists():
        return ({}, [])
    declarations: dict[str, _Declaration] = {}
    artifacts: list[str] = []
    for path in sorted(root.glob("sig_*.json"), key=lambda p: p.stat().st_mtime):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(data, dict) or data.get("tool") != "sig":
            continue
        query_name = _tool_query_name(data)
        text = str(_dict(data.get("debug")).get("legacy_text") or "")
        if not text:
            for item in _list(_dict(data.get("evidence")).get("raw")):
                if isinstance(item, dict) and item.get("preview"):
                    text = str(item.get("preview") or "")
                    break
        parsed = _parse_sig_output(text, query_name=query_name)
        if not parsed:
            continue
        artifacts.append(str(path))
        for declaration in parsed:
            declarations.setdefault(declaration.name, declaration)
    return (declarations, artifacts)


def _scan_where_tool_views(
    session_dir: str | Path | None,
) -> tuple[dict[str, _Declaration], list[str]]:
    if session_dir is None:
        return ({}, [])
    root = Path(session_dir) / "tool_views"
    if not root.exists():
        return ({}, [])
    declarations: dict[str, _Declaration] = {}
    artifacts: list[str] = []
    for path in sorted(root.glob("where_*.json"), key=lambda p: p.stat().st_mtime):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(data, dict) or data.get("tool") != "where":
            continue
        query_name = _tool_query_name(data)
        text = str(_dict(data.get("debug")).get("legacy_text") or "")
        if not text:
            for item in _list(_dict(data.get("evidence")).get("raw")):
                if isinstance(item, dict) and item.get("preview"):
                    text = str(item.get("preview") or "")
                    break
        parsed = _parse_where_output(text, query_name=query_name)
        if not parsed:
            continue
        artifacts.append(str(path))
        for declaration in parsed:
            declarations[declaration.name] = declaration
    return (declarations, artifacts)


def _tool_query_name(data: dict[str, Any]) -> str:
    evidence = _dict(data.get("evidence"))
    for item in _list(evidence.get("context")):
        if not isinstance(item, dict):
            continue
        query = _dict(item.get("query"))
        name = str(query.get("name") or "").strip()
        if name:
            return name
    return ""


def _parse_sig_output(text: str, *, query_name: str = "") -> list[_Declaration]:
    if not text or "No declaration named" in text:
        return []
    header_name = query_name
    header = re.search(r"===\s+Signature of '([^']+)'", text)
    if header:
        header_name = header.group(1)
    blocks: list[_Declaration] = []
    loc_re = re.compile(r"^--\s+(.+?):(\d+)\s+\(([^)]+)\)\s*$")
    lines = text.splitlines()
    idx = 0
    while idx < len(lines):
        loc = loc_re.match(lines[idx].strip())
        if not loc:
            idx += 1
            continue
        source = f"{loc.group(1)}:{loc.group(2)}"
        kind = loc.group(3)
        idx += 1
        decl_lines: list[str] = []
        while idx < len(lines):
            line = lines[idx]
            stripped = line.strip()
            if loc_re.match(stripped) or stripped.startswith("Usage:"):
                break
            if stripped:
                decl_lines.append(line)
            idx += 1
        declaration = _normalize_declaration("\n".join(decl_lines))
        if not declaration:
            continue
        name = _declared_name(declaration) or header_name
        if not name:
            continue
        blocks.append(_Declaration(
            name=name,
            kind=kind,
            declaration=declaration,
            source_path=source,
            source_kind="signature_lookup_tool",
            parameters=tuple(_parameters(name, declaration)),
            lhs_proc=_equiv_proc(declaration, side="lhs"),
            rhs_proc=_equiv_proc(declaration, side="rhs"),
        ))
    return blocks


def _parse_where_output(text: str, *, query_name: str = "") -> list[_Declaration]:
    if not text or "[WHERE-HIT" not in text:
        return []
    hit = re.search(
        r"\[WHERE-HIT(?:-VIA-CLONE|-SOURCE)?\]\s+"
        r"([A-Za-z_][A-Za-z0-9_'.]*)"
        r"(?:\s+->\s+([A-Za-z_][A-Za-z0-9_'.]*))?",
        text,
    )
    requested = query_name or (hit.group(1) if hit else "")
    resolved = hit.group(2) if hit and hit.group(2) else requested
    lookup_name = _unqualified(requested or resolved)
    declared_name = _unqualified(resolved or requested)
    if not lookup_name:
        return []
    kind_match = re.search(
        r"\[WHERE-HIT(?:-VIA-CLONE|-SOURCE)?\]\s+[^\n]+\(kind:\s*([^;)]+)",
        text,
    )
    kind = kind_match.group(1).strip() if kind_match else "lemma"
    decl_re = re.compile(
        rf"\b(?:lemma|equiv|axiom)\s+{re.escape(declared_name)}\s*:\s*"
        r"(?P<body>.*?)(?=\n\n\[|$)",
        re.DOTALL,
    )
    match = decl_re.search(text)
    if not match:
        return []
    body = " ".join(str(match.group("body") or "").split()).strip()
    if not body:
        return []
    decl_keyword = "equiv" if kind == "equiv" else "lemma"
    declaration = _normalize_declaration(
        f"{decl_keyword} {declared_name}: {body}"
    )
    return [_Declaration(
        name=lookup_name,
        kind=kind,
        declaration=declaration,
        source_path="where_lookup",
        source_kind="where_lookup_tool",
        parameters=tuple(_parameters(declared_name, declaration)),
        lhs_proc=_equiv_proc(declaration, side="lhs"),
        rhs_proc=_equiv_proc(declaration, side="rhs"),
    )]


def _scope_context(paths: list[Path]) -> Any:
    if analyze_ec_scope_context is None:
        return None
    text_parts: list[str] = []
    source_path: str | Path | None = None
    for path in paths:
        try:
            text_parts.append(path.read_text(encoding="utf-8", errors="replace"))
            source_path = source_path or path
        except Exception:
            continue
    try:
        return analyze_ec_scope_context("\n".join(text_parts), source_path=source_path)
    except Exception:
        return None


def _handle_inputs(handles: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()

    def add(
        name: str,
        *,
        handle_kind: str,
        procedure: str = "",
        source: str = "",
        declaration: str = "",
        source_path: str = "",
        declaration_kind: str = "",
        lhs_proc: str = "",
        rhs_proc: str = "",
    ) -> None:
        key = (name, handle_kind, procedure)
        if not name or key in seen:
            return
        seen.add(key)
        item = {
            "name": name,
            "handle_kind": handle_kind,
            "procedure": procedure,
            "source": source,
        }
        if declaration:
            item["declaration"] = declaration
        if source_path:
            item["source_path"] = source_path
        if declaration_kind:
            item["declaration_kind"] = declaration_kind
        if lhs_proc:
            item["lhs_proc"] = lhs_proc
        if rhs_proc:
            item["rhs_proc"] = rhs_proc
        out.append(item)

    for handle in _list(handles.get("callable_lemmas")):
        if not isinstance(handle, dict):
            continue
        add(
            str(handle.get("lemma") or ""),
            handle_kind="call_equiv",
            procedure=str(handle.get("procedure") or ""),
            source=str(handle.get("source") or "callable_lemmas"),
            declaration=str(handle.get("declaration") or ""),
            lhs_proc=str(handle.get("lhs_proc") or ""),
            rhs_proc=str(handle.get("rhs_proc") or ""),
        )
    for candidate in _list(handles.get("pr_rewrite_candidate_details")):
        if not isinstance(candidate, dict):
            continue
        add(
            str(candidate.get("lemma") or candidate.get("name") or ""),
            handle_kind="pr_rewrite",
            source=str(candidate.get("source") or "pr_rewrite_candidate_details"),
            declaration=str(candidate.get("declaration") or ""),
            source_path=str(candidate.get("source_path") or ""),
            declaration_kind=str(candidate.get("declaration_kind") or ""),
        )
    for name in _candidate_names(handles.get("pr_rewrite_candidates")):
        add(name, handle_kind="pr_rewrite", source="pr_rewrite_candidates")
    for item in _list(handles.get("addend_equiv_candidates")):
        if isinstance(item, dict):
            add(
                str(item.get("lemma") or ""),
                handle_kind="addend_equiv",
                procedure=str(item.get("subject") or ""),
                source="addend_equiv_candidates",
            )
    for item in _list(handles.get("have_chain_candidates")):
        if isinstance(item, dict):
            add(
                str(item.get("lemma") or item.get("name") or ""),
                handle_kind="have_chain",
                source="have_chain_candidates",
            )
        elif isinstance(item, str) and item:
            add(
                item,
                handle_kind="have_chain",
                source="have_chain_candidates",
            )
    for name in _candidate_names(handles.get("local_equiv_context")):
        add(name, handle_kind="local_equiv_context", source="local_equiv_context")
    for candidate in _list(handles.get("external_candidates")):
        if not isinstance(candidate, dict):
            continue
        name = _external_candidate_name(candidate)
        if not name:
            continue
        add(
            name,
            handle_kind=_external_handle_kind(candidate),
            source="external_candidates",
        )
    return out


def _external_candidate_name(candidate: dict[str, Any]) -> str:
    action = str(candidate.get("tactic") or candidate.get("action") or "")
    lemma_pat = r"([A-Za-z_][\w']*(?:\.[A-Za-z_][\w']*)*)"
    for pattern in (
        rf"^e?call\s+\(\s*{lemma_pat}\b",
        rf"^e?call\s+{lemma_pat}\s*\.?$",
        rf"^byequiv\s+\(\s*{lemma_pat}\b",
        rf"^rewrite\s+-?\(\s*{lemma_pat}\b",
        rf"^rewrite\s+-?{lemma_pat}\s*\.?$",
        rf"^(?:apply|exact)\s+\(\s*{lemma_pat}\b",
        rf"^(?:apply|exact)\s+-?{lemma_pat}\s*\.?$",
        rf"^have\s*:=\s*{lemma_pat}\b",
    ):
        match = re.match(pattern, action.strip())
        if match:
            name = match.group(1)
            return "" if name in {"_", "lemma_name", "Inv"} else name
    return ""


def _external_handle_kind(candidate: dict[str, Any]) -> str:
    family = str(candidate.get("tactic_family") or "")
    tactic = str(candidate.get("tactic") or candidate.get("action") or "").strip()
    low = tactic.lower()
    if family == "call_named_equiv" or re.match(r"^e?call\b", low):
        return "call_equiv"
    if family == "rewrite" or re.match(r"^rewrite\b", low):
        return "pr_rewrite"
    if family in {"pr_path_plan", "pr_bridge"} or re.match(
        r"^(apply|exact|have)\b", low
    ):
        return "have_chain"
    return "lemma"


def _instantiation_candidates(
    item: dict[str, Any],
    *,
    tactic_template: str,
) -> list[dict[str, Any]]:
    if not tactic_template:
        return []
    slots = [
        dict(slot) for slot in _list(item.get("parameter_slots"))
        if isinstance(slot, dict)
    ]
    instantiation_template = _instantiation_template(
        str(item.get("handle_kind") or ""),
        str(item.get("name") or ""),
        slots,
        fallback=tactic_template,
    )
    if item.get("requires_instantiation"):
        status = (
            "signature_known_needs_instantiation"
            if item.get("exact_signature_known") else
            "needs_signature_check"
        )
        reason = (
            "Exact signature is known; instantiate the listed parameters before direct use."
            if item.get("exact_signature_known") else
            "Local declaration has parameters; verify instantiation before direct use."
        )
        return [{
            "status": status,
            "action": str(item.get("signature_lookup_action") or ""),
            "candidate_tactic": instantiation_template,
            "parameters": list(item.get("parameters") or []),
            "parameter_slots": slots,
            "slot_count": len(slots),
            "reason": reason,
        }]
    if (
        item.get("handle_kind") == "call_equiv"
        and item.get("procedure")
        and item.get("procedure_match") == "mismatch"
    ):
        return [{
            "status": "procedure_mismatch",
            "candidate_tactic": tactic_template,
            "parameter_slots": slots,
            "reason": "Resolved equiv does not mention the currently live call procedure.",
        }]
    return [{
        "status": "ready_template",
        "candidate_tactic": tactic_template,
        "parameter_slots": slots,
        "slot_count": len(slots),
        "reason": "Exact local declaration is available and no explicit parameters were detected.",
    }]


def _parameter_slots(parameters: list[str]) -> list[dict[str, Any]]:
    slots: list[dict[str, Any]] = []
    next_index = 1
    for raw in parameters:
        if not str(raw).strip():
            continue
        base = _parameter_slot(raw, next_index)
        names = _split_multi_binder_names(base)
        if len(names) <= 1:
            base["index"] = next_index
            slots.append(base)
            next_index += 1
            continue
        for name in names:
            slot = dict(base)
            slot["index"] = next_index
            slot["name"] = name
            slot["placeholder"] = _slot_placeholder(
                str(slot.get("kind") or ""),
                name,
                next_index,
            )
            slot["argument"] = name if slot["kind"] == "memory_arg" else slot["placeholder"]
            slots.append(slot)
            next_index += 1
    return slots


def _parameter_slot(raw: str, index: int) -> dict[str, Any]:
    text = str(raw).strip()
    inner = text[1:-1].strip() if _wrapped(text) else text
    kind = "value_arg"
    name = inner
    type_or_bound = ""
    if text.startswith("["):
        kind = "type_arg"
        name = inner.strip("' ") or f"type{index}"
    elif text.startswith("{"):
        kind = "type_arg" if re.search(r"\bType\b", inner) else "implicit_arg"
        name = inner.split(":", 1)[0].strip() or f"arg{index}"
        type_or_bound = inner.split(":", 1)[1].strip() if ":" in inner else ""
    elif text.startswith("&"):
        kind = "memory_arg"
        name = text
    elif "<:" in inner:
        kind = "module_arg"
        name, type_or_bound = [piece.strip() for piece in inner.split("<:", 1)]
        name = _module_parameter_name(name)
    elif ":" in inner:
        kind = "value_arg"
        name, type_or_bound = [piece.strip() for piece in inner.split(":", 1)]
        if _looks_like_proof_parameter(type_or_bound):
            kind = "proof_arg"
    elif re.match(r"^&[A-Za-z_]\w*$", inner):
        kind = "memory_arg"
        name = inner
    placeholder = _slot_placeholder(kind, name, index)
    return {
        "index": index,
        "raw": text,
        "kind": kind,
        "name": name,
        "type_or_bound": type_or_bound,
        "placeholder": placeholder,
        "argument": name if kind == "memory_arg" else placeholder,
    }


def _module_parameter_name(name: str) -> str:
    clean = str(name or "").strip()
    if "(" in clean:
        clean = clean.split("(", 1)[0].strip()
    return clean


def _split_multi_binder_names(slot: dict[str, Any]) -> list[str]:
    kind = str(slot.get("kind") or "")
    if kind not in {"value_arg", "proof_arg", "implicit_arg"}:
        return []
    name = str(slot.get("name") or "").strip()
    if not name or "," in name or "(" in name or ")" in name:
        return []
    names = re.findall(r"[A-Za-z_][A-Za-z0-9_']*", name)
    return names if len(names) > 1 and " ".join(names) == name else []


def _instantiation_template(
    handle_kind: str,
    name: str,
    slots: list[dict[str, Any]],
    *,
    fallback: str,
) -> str:
    if not slots or not name:
        return fallback
    args = " ".join(str(slot.get("argument") or slot.get("placeholder") or "")
                    for slot in slots).strip()
    if not args:
        return fallback
    if handle_kind == "call_equiv":
        return f"call ({name} {args})."
    if handle_kind in {"local_equiv_context", "addend_equiv"}:
        return f"byequiv ({name} {args})."
    if handle_kind == "pr_rewrite":
        return f"rewrite ({name} {args})."
    if handle_kind == "have_chain":
        return f"have := {name} {args}."
    return fallback


def _slot_placeholder(kind: str, name: str, index: int) -> str:
    clean = re.sub(r"[^A-Za-z0-9_]+", "_", name).strip("_")
    if not clean:
        clean = f"arg{index}"
    if kind == "module_arg":
        return f"<{clean}_module>"
    if kind == "type_arg":
        return f"<{clean}_type>"
    if kind == "memory_arg":
        return f"<{clean.lstrip('&') or 'memory'}>"
    if kind == "proof_arg":
        return f"<{clean or 'proof'}>"
    return f"<{clean}>"


def _looks_like_proof_parameter(type_or_bound: str) -> bool:
    """Best-effort Prop/proof-argument classifier for exported lemmas.

    EasyCrypt section exports often add obligations such as
    ``dout_ll : forall x, is_lossless (dout x)`` before the module/memory
    arguments that a probability rewrite really needs.  The proof checker can
    usually infer these with ``_`` or expose them as side conditions.  Treating
    them as ordinary value parameters makes the compiler withhold otherwise
    useful typed templates.
    """
    text = re.sub(r"\s+", " ", str(type_or_bound or "")).strip()
    if not text:
        return False
    prop_markers = (
        "forall ",
        "exists ",
        "is_lossless",
        "lossless",
        "/\\",
        "\\/",
        "==>",
        "<=>",
    )
    if any(marker in text for marker in prop_markers):
        return True
    return bool(re.search(r"(?<![-<>])(?:=|<=|<|>=|>)(?!>)", text))


def _wrapped(text: str) -> bool:
    return (
        (text.startswith("(") and text.endswith(")"))
        or (text.startswith("{") and text.endswith("}"))
        or (text.startswith("[") and text.endswith("]"))
    )


def _tactic_template(handle_kind: str, name: str) -> str:
    if not name:
        return ""
    if handle_kind == "call_equiv":
        return f"call {name}."
    if handle_kind in {"local_equiv_context", "addend_equiv"}:
        return f"byequiv {name}."
    if handle_kind == "pr_rewrite":
        return f"rewrite {name}."
    if handle_kind == "have_chain":
        return f"have := {name}."
    return ""


def _procedure_match(procedure: str, declaration: _Declaration) -> str:
    if not procedure:
        return "not_applicable"
    targets = [declaration.lhs_proc, declaration.rhs_proc]
    if not any(targets):
        return "unknown"
    proc_norm = _proc_key(procedure)
    for side, target in (("lhs", declaration.lhs_proc), ("rhs", declaration.rhs_proc)):
        target_norm = _proc_key(target)
        if not target_norm:
            continue
        if proc_norm == target_norm or proc_norm in target_norm or target_norm in proc_norm:
            return side
    return "mismatch"


def _is_cross_scope_name(name: str, scope_context: Any) -> tuple[bool, str]:
    if not name:
        return (False, "")
    if is_cloned_theory_lemma is not None and scope_context is not None:
        try:
            ok, hint = is_cloned_theory_lemma(name, scope_context)
            if ok:
                return (ok, hint)
        except Exception:
            pass
    if "." in name:
        return (True, name.split(".", 1)[0])
    return (False, "")


def _parameters(name: str, declaration: str) -> list[str]:
    pattern = re.compile(
        rf"\b(?:local\s+)?(?:equiv|lemma|axiom|op|pred|abbrev|hoare)\s+"
        rf"(?:\[[^\]]+\]\s+)?{re.escape(name)}\b",
        re.DOTALL,
    )
    match = pattern.search(declaration)
    if not match:
        return []
    after_name = declaration[match.end():].lstrip()
    if re.match(r":\s*(?:\(|forall\b)", after_name):
        return _where_style_parameters(after_name[1:])
    params = " ".join(_scan_params_until_colon(declaration[match.end():]).split())
    if not params:
        return []
    return _split_parameter_chunks(params)


def _where_style_parameters(text: str) -> list[str]:
    body = " ".join(str(text or "").split())
    if not body:
        return []
    params: list[str] = []
    implication = _split_top_level_implication(body)
    if implication:
        antecedent, body = implication
        params.append(f"(proof1 : {antecedent})")
    body = body.strip()
    if body.startswith("forall "):
        body = body[len("forall "):].strip()
    param_text = _scan_where_params_until_body(body)
    return [*params, *_split_parameter_chunks(param_text)]


def _split_top_level_implication(text: str) -> tuple[str, str] | None:
    split = _split_top_level_at(text, "=>")
    if not split:
        return None
    left, right = split
    return (left, right) if left and right else None


def _scan_where_params_until_body(text: str) -> str:
    depth = 0
    out: list[str] = []
    for idx, ch in enumerate(text):
        if depth == 0 and text.startswith("Pr[", idx):
            break
        if depth == 0 and ch == ",":
            rest = text[idx + 1:].lstrip()
            if rest.startswith("Pr["):
                break
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth = max(0, depth - 1)
        out.append(ch)
    return "".join(out).strip().rstrip(",").strip()


def _split_parameter_chunks(params: str) -> list[str]:
    chunks: list[str] = []
    idx = 0
    pairs = {"(": ")", "{": "}", "[": "]"}
    while idx < len(params):
        while idx < len(params) and params[idx].isspace():
            idx += 1
        if idx >= len(params):
            break
        ch = params[idx]
        if ch in pairs:
            close = pairs[ch]
            depth = 0
            start = idx
            while idx < len(params):
                if params[idx] == ch:
                    depth += 1
                elif params[idx] == close:
                    depth -= 1
                    if depth == 0:
                        idx += 1
                        break
                idx += 1
            chunks.append(params[start:idx].strip())
            continue
        start = idx
        while idx < len(params) and not params[idx].isspace():
            idx += 1
        token = params[start:idx].strip()
        if token and token not in {",", "."}:
            chunks.append(token)
    return chunks


def _scan_params_until_colon(text: str) -> str:
    depth = 0
    out: list[str] = []
    pairs = {"(": ")", "{": "}", "[": "]"}
    closers = set(pairs.values())
    stack: list[str] = []
    for ch in text:
        if ch in pairs:
            stack.append(pairs[ch])
            depth += 1
            out.append(ch)
            continue
        if ch in closers:
            if stack and stack[-1] == ch:
                stack.pop()
                depth = max(0, depth - 1)
            out.append(ch)
            continue
        if ch == ":" and depth == 0:
            break
        out.append(ch)
    return "".join(out).strip()


def _declared_name(declaration: str) -> str:
    match = re.search(
        r"\b(?:local\s+)?(?:equiv|lemma|axiom|op|pred|abbrev|hoare)\s+"
        r"(?:\[[^\]]+\]\s+)?([A-Za-z_][A-Za-z0-9_']*)(?![A-Za-z0-9_'])",
        declaration,
    )
    return match.group(1) if match else ""


def _equiv_proc(declaration: str, *, side: str) -> str:
    match = re.search(r":\s*([^~:]+?)\s*~\s*([^:]+?)\s*:", declaration, re.DOTALL)
    if not match:
        return ""
    value = match.group(1 if side == "lhs" else 2)
    return " ".join(value.split()).strip()


def _normalize_declaration(text: str) -> str:
    text = re.sub(r"\(\*.*?\*\)", " ", text, flags=re.DOTALL)
    text = " ".join(text.strip().split())
    return text[:1200]


def _summary(items: list[dict[str, Any]]) -> dict[str, int]:
    resolved = sum(
        1 for item in items
        if item.get("resolution_status") in {
            "resolved_local_declaration",
            "resolved_signature_lookup",
            "resolved_goal_hypothesis",
        }
    )
    needs_lookup = sum(
        1 for item in items
        if item.get("resolution_status") in {
            "needs_where_lookup",
            "needs_sig_lookup",
            "in_scope_name_without_signature",
        }
    )
    unresolved = sum(
        1 for item in items
        if item.get("resolution_status") == "unresolved"
    )
    return {
        "total": len(items),
        "resolved": resolved,
        "needs_lookup": needs_lookup,
        "unresolved": unresolved,
    }


def _proc_key(value: str) -> str:
    return re.sub(r"\s+", "", value).strip().lower()


def _goal_identifier_order(text: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for match in _GOAL_NAME_RE.finditer(str(text or "")):
        name = match.group(0)
        if name in seen or name in _GOAL_NAME_IGNORE:
            continue
        if name and name[0].isupper() and "." not in name:
            # Module/theory names are not unfoldable goal heads by themselves.
            continue
        seen.add(name)
        out.append(name)
    return out


__all__ = [
    "NAME_RESOLUTION_KIND",
    "NAME_RESOLUTION_SCHEMA_VERSION",
    "resolution_for_name",
    "resolve_proof_ir_names",
]
