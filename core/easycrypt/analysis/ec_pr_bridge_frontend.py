"""Typed Pr bridge and adapter planner pass for EasyCrypt ProofIR.

This module owns Pr endpoint-normalization facts: wrapper-to-MainD bridges,
typed adapter rewrites, synthetic bridge edges, and contextual structural bridge
hints.  It is a planner/frontend pass: it emits typed bridge candidates, while
ProofIR and the action/ranking layers decide how to present and order them.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from core.easycrypt.analysis.ec_utils import (
    as_dict as _dict,
    as_list as _list,
    dedupe_strings as _dedupe_strings,
)
from core.easycrypt.analysis.ec_instantiation_binding import binding_for_name
from core.easycrypt.analysis.ec_lemma_index import (
    build_semantic_lemma_index,
    semantic_pr_rewrite_declarations,
    session_context_files as _session_context_files,
)
from core.easycrypt.analysis.ec_menu_actions import safe_id as _safe_id
from core.easycrypt.analysis.ec_pr_canonical import (
    game_key as _game_key,
    matching_bracket as _matching_bracket,
    module_application_parts as _canonical_module_application_parts,
    parse_pr_terms as _canonical_parse_pr_terms,
    pr_term_for_game as _pr_term_for_game,
    split_top_level_args as _split_top_level_args,
)


PR_BRIDGE_FRONTEND_SCHEMA_VERSION = 1
PR_BRIDGE_FRONTEND_KIND = "easycrypt_pr_bridge_frontend"


def build_pr_typed_bridge_frontend(
    *,
    session_dir: str | Path | None,
    goal_text: str,
    handles: dict[str, Any],
    instantiation_bindings: dict[str, Any],
) -> dict[str, Any]:
    return _pr_typed_bridge_frontend(
        session_dir=session_dir,
        goal_text=goal_text,
        handles=handles,
        instantiation_bindings=instantiation_bindings,
    )


def pr_wrapper_bridge_candidates(
    parsed: dict[str, Any],
    goal_text: str,
    handles: dict[str, Any],
    pr_path_plan: dict[str, Any],
) -> list[dict[str, Any]]:
    return _pr_wrapper_bridge_candidates(parsed, goal_text, handles, pr_path_plan)


def _pr_typed_bridge_frontend(
    *,
    session_dir: str | Path | None,
    goal_text: str,
    handles: dict[str, Any],
    instantiation_bindings: dict[str, Any],
) -> dict[str, Any]:
    """Infer typed Pr bridge graph edges from current endpoints and context.

    The important separation is compiler-like: wrapper-to-MainD bridge tactics
    must close their own `have` proof before they become probeable actions, and
    generic MainD rewrite lemmas are instantiated as graph edges with the local
    adapter module.  This keeps `byequiv` from racing ahead while a typed Pr
    route is still live.
    """
    if "Pr[" not in str(goal_text or ""):
        return _empty_typed_pr_bridge("not_pr_goal")

    terms = _pr_term_records(goal_text)
    wrappers = [
        {
            **term,
            "wrapper": _experiment_wrapper_parts(str(term.get("game_key") or "")),
        }
        for term in terms
    ]
    wrappers = [item for item in wrappers if item.get("wrapper")]
    if not wrappers:
        return _empty_typed_pr_bridge("no_experiment_wrapper_endpoint")

    bridge_details = [
        _dict(item)
        for item in _list(handles.get("pr_rewrite_candidate_details"))
        if isinstance(item, dict)
    ]
    bridge_details = _merge_pr_bridge_details(
        bridge_details,
        _enriched_source_pr_rewrite_declarations(session_dir),
    )
    adapters = _source_ro_adapter_modules(session_dir)
    oracle_aliases = _source_oracle_aliases(session_dir)
    oracle_candidates = _typed_bridge_oracle_candidates(
        terms,
        bridge_details,
        adapters,
        oracle_aliases,
    )
    wrapper_bridges: list[dict[str, Any]] = []
    instantiated_rewrites: list[dict[str, Any]] = []
    seen_bridges: set[tuple[str, str, str]] = set()
    seen_rewrites: set[tuple[str, str, str]] = set()

    for wrapper_item in wrappers:
        wrapper = _dict(wrapper_item.get("wrapper"))
        wrapper_oracle = str(wrapper.get("oracle") or "")
        wrapper_oracle_base = oracle_aliases.get(wrapper_oracle, wrapper_oracle)
        wrapper_distinguisher = str(wrapper.get("distinguisher") or "")
        source_key = str(wrapper_item.get("game_key") or "")
        source_pr = str(wrapper_item.get("pr_text") or "")
        if not wrapper_oracle_base or not wrapper_distinguisher or not source_key:
            continue
        for adapter in adapters:
            direct_bridge = _direct_wrapper_adapter_bridge(
                adapter=adapter,
                wrapper_item=wrapper_item,
                source_key=source_key,
                source_pr=source_pr,
                oracle_candidates=oracle_candidates,
                bridge_details=bridge_details,
            )
            if direct_bridge:
                bridge_key = (
                    str(direct_bridge.get("lhs_game") or ""),
                    str(direct_bridge.get("rhs_game") or ""),
                    str(direct_bridge.get("adapter_module") or ""),
                )
                if bridge_key not in seen_bridges:
                    seen_bridges.add(bridge_key)
                    wrapper_bridges.append(direct_bridge)
            if not _adapter_matches_wrapper(adapter, wrapper_distinguisher):
                continue
            adapter_name = str(adapter.get("name") or "")
            if not adapter_name:
                continue
            for detail in bridge_details:
                lhs = _main_d_parts(str(detail.get("lhs_game") or ""))
                rhs = _main_d_parts(str(detail.get("rhs_game") or ""))
                if not lhs or not rhs:
                    continue
                root = str(lhs.get("root") or rhs.get("root") or "MainD")
                lhs_oracle = str(lhs.get("oracle") or "")
                rhs_oracle = str(rhs.get("oracle") or "")
                matched_oracle = _matching_main_d_oracle(
                    wrapper_oracle_base,
                    lhs_oracle,
                    rhs_oracle,
                )
                if not matched_oracle:
                    continue
                target_expr = f"{root}({adapter_name}, {matched_oracle}).distinguish()"
                target_key = _game_key(target_expr)
                target_pr = _pr_term_for_game(
                    target_expr,
                    memory=str(wrapper_item.get("memory") or "&m"),
                    event=str(wrapper_item.get("event") or "res"),
                )
                bridge_key = (source_key, target_key, adapter_name)
                if source_pr and target_pr and bridge_key not in seen_bridges:
                    seen_bridges.add(bridge_key)
                    lemma = str(detail.get("lemma") or detail.get("name") or "")
                    tactic = (
                        f"have -> : {source_pr} = {target_pr} "
                        "by byequiv => //; proc; inline *; sim."
                    )
                    wrapper_bridges.append({
                        "name": (
                            "bridge_"
                            + _safe_id(source_key)
                            + "_to_"
                            + _safe_id(target_key)
                        ),
                        "edge_kind": "synthetic_bridge",
                        "relation": "equality",
                        "lhs_game": source_key,
                        "rhs_game": target_key,
                        "source_pr": source_pr,
                        "target_pr": target_pr,
                        "tactic": tactic,
                        "action_hint": tactic,
                        "adapter_module": adapter_name,
                        "adapter_reason": str(adapter.get("reason") or ""),
                        "wrapper_oracle": wrapper_oracle,
                        "base_oracle": wrapper_oracle_base,
                        "bridge_lemma": lemma,
                        "reason": (
                            f"Local adapter `{adapter_name}` normalizes wrapper "
                            f"`{source_key}` to `{target_key}`, exposing generic "
                            f"Pr rewrite `{lemma}`."
                        ),
                    })
                rewrite_key = (adapter_name, lhs_oracle, rhs_oracle)
                if lhs_oracle and rhs_oracle and rewrite_key not in seen_rewrites:
                    seen_rewrites.add(rewrite_key)
                    lemma = str(detail.get("lemma") or detail.get("name") or "")
                    lhs_expr = f"{root}({adapter_name}, {lhs_oracle}).distinguish()"
                    rhs_expr = f"{root}({adapter_name}, {rhs_oracle}).distinguish()"
                    instantiated_rewrites.append({
                        "name": lemma,
                        "lemma": lemma,
                        "edge_kind": "pr_rewrite",
                        "relation": "equality",
                        "lhs_game": lhs_expr,
                        "rhs_game": rhs_expr,
                        "adapter_module": adapter_name,
                        "source_template_lhs": str(detail.get("lhs_game") or ""),
                        "source_template_rhs": str(detail.get("rhs_game") or ""),
                        "action_hint": _typed_pr_rewrite_action_hint(
                            lemma,
                            adapter_name,
                            instantiation_bindings,
                            direction="forward",
                        ),
                        "backward_action_hint": _typed_pr_rewrite_action_hint(
                            lemma,
                            adapter_name,
                            instantiation_bindings,
                            direction="backward",
                        ),
                        "reason": (
                            f"Instantiate generic Pr rewrite `{lemma}` with "
                            f"adapter `{adapter_name}`."
                        ),
                    })

    for bridge in _structural_adapter_bridges(
        adapters=adapters,
        oracle_candidates=oracle_candidates,
        current_terms=terms,
    ):
        bridge_key = (
            str(bridge.get("lhs_game") or ""),
            str(bridge.get("rhs_game") or ""),
            str(bridge.get("adapter_module") or ""),
        )
        if bridge_key in seen_bridges:
            continue
        seen_bridges.add(bridge_key)
        wrapper_bridges.append(bridge)

    for rewrite in _instantiated_main_d_rewrites_for_adapters(
        adapters=adapters,
        bridge_details=bridge_details,
        instantiation_bindings=instantiation_bindings,
    ):
        rewrite_key = (
            str(rewrite.get("adapter_module") or ""),
            str(rewrite.get("lhs_game") or ""),
            str(rewrite.get("rhs_game") or ""),
        )
        if rewrite_key in seen_rewrites:
            continue
        seen_rewrites.add(rewrite_key)
        instantiated_rewrites.append(rewrite)

    for bridge in _contextual_structural_adapter_bridges(
        adapters=adapters,
        current_terms=terms,
        instantiated_rewrites=instantiated_rewrites,
    ):
        bridge_key = (
            str(bridge.get("lhs_game") or ""),
            str(bridge.get("rhs_game") or ""),
            str(bridge.get("adapter_module") or ""),
        )
        if bridge_key in seen_bridges:
            continue
        seen_bridges.add(bridge_key)
        wrapper_bridges.append(bridge)

    # Endpoint-anchored scheme normalizations are the highest-priority runnable
    # bridges for the current goal, so they lead the wrapper-bridge list (and
    # are therefore probed before generic library rewrites).
    scheme_bridges: list[dict[str, Any]] = []
    for bridge in _oracle_scheme_normalization_bridges(
        session_dir=session_dir,
        terms=terms,
    ):
        bridge_key = (
            str(bridge.get("lhs_game") or ""),
            str(bridge.get("rhs_game") or ""),
            str(bridge.get("adapter_module") or ""),
        )
        if bridge_key in seen_bridges:
            continue
        seen_bridges.add(bridge_key)
        scheme_bridges.append(bridge)
    wrapper_bridges = scheme_bridges + wrapper_bridges

    return {
        "available": bool(wrapper_bridges or instantiated_rewrites),
        "reason": (
            "typed_wrapper_to_main_bridge_found"
            if wrapper_bridges else
            "typed_main_rewrite_instantiations_found"
            if instantiated_rewrites else
            "no_typed_bridge_chain"
        ),
        "wrapper_bridges": wrapper_bridges[:128],
        "instantiated_rewrites": instantiated_rewrites[:48],
        "adapter_count": len(adapters),
        "oracle_alias_count": len(oracle_aliases),
    }


def _empty_typed_pr_bridge(reason: str) -> dict[str, Any]:
    return {
        "available": False,
        "reason": reason,
        "wrapper_bridges": [],
        "instantiated_rewrites": [],
        "adapter_count": 0,
        "oracle_alias_count": 0,
    }


def _merge_pr_bridge_details(
    primary: list[dict[str, Any]],
    fallback: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in [*primary, *fallback]:
        if not isinstance(item, dict):
            continue
        name = str(item.get("lemma") or item.get("name") or "")
        lhs = _game_key(str(item.get("lhs_game") or ""))
        rhs = _game_key(str(item.get("rhs_game") or ""))
        key = (name, lhs, rhs)
        if not name or not lhs or not rhs or key in seen:
            continue
        seen.add(key)
        enriched = _dict(item)
        enriched["lemma"] = name
        enriched["name"] = str(enriched.get("name") or name)
        enriched["lhs_game"] = lhs
        enriched["rhs_game"] = rhs
        out.append(enriched)
    return out


def _enriched_source_pr_rewrite_declarations(
    session_dir: str | Path | None,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in semantic_pr_rewrite_declarations(
        build_semantic_lemma_index(session_dir)
    ):
        if not isinstance(item, dict):
            continue
        games = [
            str(item.get("lhs_game") or ""),
            str(item.get("rhs_game") or ""),
        ]
        if len(games) != 2 or not games[0] or not games[1]:
            continue
        enriched = _dict(item)
        enriched["name"] = str(enriched.get("name") or enriched.get("lemma") or "")
        enriched["lhs_game"] = games[0]
        enriched["rhs_game"] = games[1]
        out.append(enriched)
    return out


def _typed_pr_rewrite_action_hint(
    lemma: str,
    adapter_name: str,
    instantiation_bindings: dict[str, Any],
    *,
    direction: str,
) -> str:
    binding = binding_for_name(instantiation_bindings, lemma)
    for template in _list(binding.get("instantiated_templates")):
        if not isinstance(template, dict):
            continue
        tactic = str(template.get("tactic") or "")
        if tactic and adapter_name in tactic:
            return tactic
    if str(direction or "") == "backward":
        return (
            f"rewrite -{lemma}.  (* instantiate distinguisher slot with "
            f"`{adapter_name}` after `-where {lemma}` *)"
        )
    return (
        f"rewrite {lemma}.  (* instantiate distinguisher slot with "
        f"`{adapter_name}` after `-where {lemma}` *)"
    )


def _matching_main_d_oracle(
    wrapper_oracle_base: str,
    lhs_oracle: str,
    rhs_oracle: str,
) -> str:
    base = _oracle_root(wrapper_oracle_base)
    for oracle in (lhs_oracle, rhs_oracle):
        if _oracle_root(oracle) == base:
            return str(oracle or "")
    return ""


def _oracle_root(oracle: str) -> str:
    text = str(oracle or "").strip()
    match = re.match(r"([A-Za-z_][A-Za-z0-9_'.]*)", text)
    return match.group(1).rsplit(".", 1)[-1] if match else ""


def _adapter_matches_wrapper(adapter: dict[str, Any], wrapper_distinguisher: str) -> bool:
    adapter_d = _compact_expr(str(adapter.get("distinguisher") or ""))
    wrapper_d = _compact_expr(wrapper_distinguisher)
    if not adapter_d or not wrapper_d:
        return False
    if adapter_d == wrapper_d:
        return True
    if adapter_d.startswith(wrapper_d[:-1] + ",") and wrapper_d.endswith(")"):
        return True
    return False


def _source_ro_adapter_modules(session_dir: str | Path | None) -> list[dict[str, Any]]:
    adapters: list[dict[str, Any]] = []
    for text, path, _kind in _session_source_texts(session_dir):
        for module in _module_bodies(text, path=path):
            adapter = _ro_adapter_from_module(module)
            if adapter:
                adapters.append(adapter)
            adapter = _wrapper_adapter_from_module(module)
            if adapter:
                adapters.append(adapter)
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for adapter in adapters:
        key = (
            str(adapter.get("name") or ""),
            str(adapter.get("adapter_kind") or ""),
            str(adapter.get("source_template") or ""),
            str(adapter.get("source_main_d_template") or ""),
        )
        name = "|".join(key)
        if not key[0] or name in seen:
            continue
        seen.add(name)
        deduped.append(adapter)
    return deduped


def _ro_adapter_from_module(module: dict[str, Any]) -> dict[str, Any]:
    name = str(module.get("name") or "")
    formals = _module_formals(str(module.get("formals") or ""))
    body = str(module.get("body") or "")
    if not name or not formals:
        return {}
    formal = formals[0]
    formal_name = str(formal.get("name") or "")
    formal_bound = str(formal.get("bound") or "")
    if not formal_name or _oracle_root(formal_bound) != "RO":
        return {}
    inner_oracle = _inner_get_adapter_module(body, formal_name)
    distinguish = _adapter_distinguish_alias(body, inner_oracle)
    if not inner_oracle or not distinguish:
        return {}
    return {
        "name": name,
        "formal_name": formal_name,
        "formal_bound": formal_bound,
        "inner_oracle": inner_oracle,
        "distinguisher": str(distinguish.get("distinguisher") or ""),
        "called_procedure": str(distinguish.get("procedure") or ""),
        "source_path": str(module.get("source_path") or ""),
        "reason": (
            f"`{name}` takes an RO module, exposes `{inner_oracle}.f` as "
            f"`{formal_name}.get`, and delegates distinguish to "
            f"`{distinguish.get('callee')}`."
        ),
    }


def _wrapper_adapter_from_module(module: dict[str, Any]) -> dict[str, Any]:
    """Detect adapters whose distinguish procedure delegates to a wrapper.

    This is a generic typed-IR normalization pattern:

    ``module G(A, O:RO).distinguish`` calls either an experiment ``...main``
    using ``O`` or another distinguisher ``D(..., O').distinguish``.  Such a
    module gives the Pr path planner a structural edge from the wrapper
    endpoint to ``MainD(G(A), O)`` without naming any project-specific lemma.
    """
    name = str(module.get("name") or "")
    formals = _module_formals(str(module.get("formals") or ""))
    body = str(module.get("body") or "")
    if not name or not formals or "proc distinguish" not in body:
        return {}
    oracle_formal = _first_oracle_formal(formals)
    if not oracle_formal:
        return {}
    formal_name = str(oracle_formal.get("name") or "")
    formal_bound = str(oracle_formal.get("bound") or "")
    if not formal_name:
        return {}
    non_oracle_args = [
        str(formal.get("name") or "")
        for formal in formals
        if str(formal.get("name") or "") != formal_name
    ]
    distinguish_body = _procedure_body_by_name(body, "distinguish")
    if not distinguish_body:
        return {}
    call = _first_distinguish_delegate_call(distinguish_body)
    if not call:
        return {}
    callee = str(call.get("callee") or "")
    proc = str(call.get("procedure") or "")
    if not callee or formal_name not in callee:
        return {}
    module_expr = _module_application(name, non_oracle_args)
    common = {
        "name": name,
        "module_expr": module_expr,
        "formal_name": formal_name,
        "formal_bound": formal_bound,
        "main_d_root": _main_d_root_for_oracle_bound(formal_bound),
        "non_oracle_args": non_oracle_args,
        "source_path": str(module.get("source_path") or ""),
    }
    if proc in {"main", "game"}:
        return {
            **common,
            "adapter_kind": "direct_wrapper_main",
            "source_template": callee,
            "source_procedure": proc,
            "reason": (
                f"`{name}` takes oracle `{formal_name}` and delegates "
                f"`distinguish` to wrapper `{callee}.{proc}`."
            ),
        }
    if proc == "distinguish":
        parts = _module_application_parts(callee)
        args = _list(parts.get("args"))
        if len(args) < 2:
            return {}
        oracle_template = str(args[-1] or "")
        if formal_name not in oracle_template:
            return {}
        distinguisher_template = (
            str(parts.get("root") or "")
            + "("
            + ", ".join(str(arg) for arg in args[:-1])
            + ")"
        )
        return {
            **common,
            "adapter_kind": "main_d_wrapper",
            "source_distinguisher_template": distinguisher_template,
            "source_oracle_template": oracle_template,
            "source_procedure": proc,
            "reason": (
                f"`{name}` takes oracle `{formal_name}` and delegates "
                f"`distinguish` to `{callee}.distinguish`."
            ),
        }
    return {}


def _first_oracle_formal(formals: list[dict[str, str]]) -> dict[str, str]:
    for formal in formals:
        bound = str(formal.get("bound") or "")
        if _oracle_root(bound) == "RO":
            return formal
    return {}


def _procedure_body_by_name(body: str, proc_name: str) -> str:
    pattern = re.compile(
        rf"\bproc\s+{re.escape(proc_name)}\s*(?:\([^)]*\))?\s*=\s*\{{",
        flags=re.DOTALL,
    )
    match = pattern.search(body)
    if not match:
        return ""
    open_idx = match.end() - 1
    close_idx = _matching_bracket(body, open_idx, "{", "}")
    if close_idx <= open_idx:
        return ""
    return body[open_idx + 1:close_idx]


def _first_distinguish_delegate_call(body: str) -> dict[str, str]:
    pattern = re.compile(
        r"(?:<@|=)\s*"
        r"(?P<callee>[A-Za-z_][A-Za-z0-9_'.]*\s*\(.*\))\."
        r"(?P<proc>[A-Za-z_][A-Za-z0-9_']*)\s*\(",
        flags=re.DOTALL,
    )
    for statement in _top_level_statement_chunks(body):
        match = pattern.search(statement)
        if not match:
            continue
        callee = re.sub(r"\s+", "", match.group("callee"))
        proc = str(match.group("proc") or "")
        if proc not in {"main", "game", "distinguish"}:
            continue
        return {"callee": callee, "procedure": proc}
    return {}


def _top_level_statement_chunks(body: str) -> list[str]:
    chunks: list[str] = []
    start = 0
    depth = 0
    for idx, ch in enumerate(str(body or "")):
        if ch in "([{":
            depth += 1
        elif ch in ")]}" and depth:
            depth -= 1
        elif ch == ";" and depth == 0:
            chunk = body[start:idx].strip()
            if chunk:
                chunks.append(chunk)
            start = idx + 1
    tail = str(body or "")[start:].strip()
    if tail:
        chunks.append(tail)
    return chunks


def _module_application(name: str, args: list[str]) -> str:
    clean_args = [str(arg).strip() for arg in args if str(arg).strip()]
    if not clean_args:
        return str(name or "")
    return f"{name}({', '.join(clean_args)})"


def _module_application_parts(expr: str) -> dict[str, Any]:
    return _canonical_module_application_parts(expr)


def _main_d_root_for_oracle_bound(bound: str) -> str:
    text = str(bound or "").strip()
    if not text or text == "RO":
        return "MainD"
    parts = text.split(".")
    if len(parts) >= 3 and parts[-2] in {"I1", "I2"} and parts[-1] == "RO":
        return ".".join(parts[:-2] + ["IdealAll", "MainD"])
    if parts[-1] == "RO":
        return ".".join(parts[:-1] + ["MainD"])
    return "MainD"


def _substitute_formal_expr(template: str, formal: str, actual: str) -> str:
    if not template or not formal or not actual:
        return str(template or "")
    return re.sub(
        rf"(?<![A-Za-z0-9_'.]){re.escape(formal)}(?![A-Za-z0-9_'])",
        str(actual).strip(),
        str(template),
    )


def _typed_bridge_oracle_candidates(
    terms: list[dict[str, str]],
    bridge_details: list[dict[str, Any]],
    adapters: list[dict[str, Any]],
    oracle_aliases: dict[str, str],
) -> list[str]:
    out: list[str] = []
    for term in terms:
        key = str(term.get("game_key") or "")
        main = _main_d_parts(key)
        if main:
            out.append(str(main.get("oracle") or ""))
        wrapper = _experiment_wrapper_parts(key)
        if wrapper:
            oracle = str(wrapper.get("oracle") or "")
            out.append(oracle_aliases.get(oracle, oracle))
            out.extend(_oracle_like_terms(oracle))
    for detail in bridge_details:
        for side in ("lhs_game", "rhs_game"):
            main = _main_d_parts(str(detail.get(side) or ""))
            if main:
                out.append(str(main.get("oracle") or ""))
                out.extend(_oracle_like_terms(str(main.get("oracle") or "")))
    for adapter in adapters:
        for key in ("source_template", "source_oracle_template"):
            out.extend(_oracle_like_terms(str(adapter.get(key) or "")))
        formal = str(adapter.get("formal_name") or "")
        if formal:
            out = [item for item in out if item != formal]
    return _dedupe_strings([item for item in out if item])


def _oracle_like_terms(expr: str) -> list[str]:
    text = str(expr or "")
    out: list[str] = []
    compact = _compact_expr(text)
    parts = _module_application_parts(compact)
    if parts:
        root_leaf = str(parts.get("root") or "").rsplit(".", 1)[-1]
        if root_leaf in {"RO", "FinRO", "IndRO"} or "RO" in root_leaf:
            out.append(compact)
        for arg in _list(parts.get("args")):
            arg_text = str(arg or "").strip()
            if _expr_mentions_oracle(arg_text):
                out.append(_compact_expr(arg_text))
                out.extend(_oracle_like_terms(arg_text))
    for match in re.finditer(
        r"[A-Za-z_][A-Za-z0-9_'.]*(?:\s*\([^()]*\))?",
        text,
    ):
        raw = re.sub(r"\s+", "", match.group(0))
        if not raw:
            continue
        leaf = raw.split("(", 1)[0].rsplit(".", 1)[-1]
        if leaf in {"RO", "FinRO", "IndRO"} or "RO" in leaf:
            out.append(raw)
    return _dedupe_strings(out)


def _direct_wrapper_adapter_bridge(
    *,
    adapter: dict[str, Any],
    wrapper_item: dict[str, Any],
    source_key: str,
    source_pr: str,
    oracle_candidates: list[str],
    bridge_details: list[dict[str, Any]],
) -> dict[str, Any]:
    if str(adapter.get("adapter_kind") or "") != "direct_wrapper_main":
        return {}
    template = str(adapter.get("source_template") or "")
    proc = str(adapter.get("source_procedure") or "main")
    formal = str(adapter.get("formal_name") or "")
    if not template or not formal:
        return {}
    memory = str(wrapper_item.get("memory") or "&m")
    event = str(wrapper_item.get("event") or "res")
    source_expr_with_proc = _game_expr_with_proc(source_key, proc)
    for actual in oracle_candidates:
        instantiated = _substitute_formal_expr(template, formal, actual)
        instantiated_key = _game_key(instantiated)
        if (
            instantiated_key != source_key
            and not _game_wrapper_expands_to_call(source_key, instantiated_key)
        ):
            continue
        target_expr = (
            f"{adapter.get('main_d_root')}"
            f"({adapter.get('module_expr')}, {actual}).distinguish()"
        )
        target_key = _game_key(target_expr)
        target_pr = _pr_term_for_game(target_expr, memory=memory, event=event)
        if not source_pr or not target_pr:
            continue
        lemma = _nearest_bridge_lemma_for_oracle(actual, bridge_details)
        tactic = (
            f"have -> : {source_pr or _pr_term_for_game(source_expr_with_proc, memory=memory, event=event)} = "
            f"{target_pr} by byequiv => //; proc; inline *; sim."
        )
        return {
            "name": (
                "bridge_"
                + _safe_id(source_key)
                + "_to_"
                + _safe_id(target_key)
            ),
            "edge_kind": "synthetic_bridge",
            "relation": "equality",
            "lhs_game": source_key,
            "rhs_game": target_key,
            "source_pr": source_pr,
            "target_pr": target_pr,
            "tactic": tactic,
            "action_hint": tactic,
            "adapter_module": str(adapter.get("module_expr") or adapter.get("name") or ""),
            "adapter_reason": str(adapter.get("reason") or ""),
            "wrapper_oracle": actual,
            "base_oracle": actual,
            "bridge_lemma": lemma,
            "reason": (
                f"Local adapter `{adapter.get('module_expr')}` normalizes "
                f"wrapper endpoint `{source_key}` to typed endpoint "
                f"`{target_key}` before Pr rewrite/split handles."
            ),
        }
    return {}


def _game_wrapper_expands_to_call(wrapper_key: str, callee_key: str) -> bool:
    """Return true when a game endpoint wraps a module-call endpoint.

    This captures the common EasyCrypt shape:

    ``Game(F(args), O).main`` executes/normalizes to ``F(args, O).main``.

    The relation is structural and intentionally name-agnostic: the game root,
    adversary root, and oracle expression can be project-specific.
    """
    wrapper = _module_application_parts(wrapper_key)
    callee = _module_application_parts(callee_key)
    if not wrapper or not callee:
        return False
    wrapper_args = [str(arg).strip() for arg in _list(wrapper.get("args"))]
    callee_args = [str(arg).strip() for arg in _list(callee.get("args"))]
    if len(wrapper_args) < 2 or len(callee_args) < 1:
        return False
    oracle_arg = wrapper_args[1]
    if _compact_expr(callee_args[-1]) != _compact_expr(oracle_arg):
        return False
    wrapped_adv = _module_application_parts(wrapper_args[0])
    if wrapped_adv:
        if _compact_expr(str(wrapped_adv.get("root") or "")) != _compact_expr(
            str(callee.get("root") or "")
        ):
            return False
        wrapped_args = [
            str(arg).strip()
            for arg in _list(wrapped_adv.get("args"))
        ]
        return _compact_expr(",".join(wrapped_args)) == _compact_expr(
            ",".join(callee_args[:-1])
        )
    return _compact_expr(wrapper_args[0]) == _compact_expr(
        str(callee.get("root") or "")
    ) and len(callee_args) == 1


def _structural_adapter_bridges(
    *,
    adapters: list[dict[str, Any]],
    oracle_candidates: list[str],
    current_terms: list[dict[str, str]],
) -> list[dict[str, Any]]:
    current_keys = {str(term.get("game_key") or "") for term in current_terms}
    current_pr_by_key = {
        str(term.get("game_key") or ""): term
        for term in current_terms
        if str(term.get("game_key") or "")
    }
    root_by_module = {
        str(adapter.get("name") or ""): str(adapter.get("main_d_root") or "MainD")
        for adapter in adapters
        if str(adapter.get("name") or "")
    }
    out: list[dict[str, Any]] = []
    for adapter in adapters:
        if str(adapter.get("adapter_kind") or "") != "main_d_wrapper":
            continue
        formal = str(adapter.get("formal_name") or "")
        formal_bound = str(adapter.get("formal_bound") or "")
        source_d = str(adapter.get("source_distinguisher_template") or "")
        source_o = str(adapter.get("source_oracle_template") or "")
        if not formal or not source_d or not source_o:
            continue
        source_root = root_by_module.get(
            source_d.split("(", 1)[0].rsplit(".", 1)[-1],
            "MainD",
        )
        for actual in oracle_candidates:
            instantiated_oracle = _substitute_formal_expr(source_o, formal, actual)
            if instantiated_oracle == source_o and formal in source_o:
                continue
            source_expr = (
                f"{source_root}({source_d}, {instantiated_oracle}).distinguish()"
            )
            target_expr = (
                f"{adapter.get('main_d_root')}"
                f"({adapter.get('module_expr')}, {actual}).distinguish()"
            )
            source_key = _game_key(source_expr)
            target_key = _game_key(target_expr)
            if not source_key or not target_key or source_key == target_key:
                continue
            current = _dict(current_pr_by_key.get(source_key))
            source_pr = str(current.get("pr_text") or "")
            memory = str(current.get("memory") or "&m")
            event = str(current.get("event") or "res")
            target_pr = (
                _pr_term_for_game(target_expr, memory=memory, event=event)
                if source_key in current_keys else
                ""
            )
            tactic = (
                f"have -> : {source_pr} = {target_pr} "
                "by byequiv => //; proc; inline *; sim."
                if source_pr and target_pr else
                f"Pr structural bridge: {source_key} -> {target_key}"
            )
            out.append({
                "name": (
                    "bridge_"
                    + _safe_id(source_key)
                    + "_to_"
                    + _safe_id(target_key)
                ),
                "edge_kind": "synthetic_bridge",
                "relation": "equality",
                "lhs_game": source_key,
                "rhs_game": target_key,
                "source_pr": source_pr,
                "target_pr": target_pr,
                "tactic": tactic if source_pr and target_pr else "",
                "action_hint": tactic,
                "adapter_module": str(adapter.get("module_expr") or adapter.get("name") or ""),
                "adapter_reason": str(adapter.get("reason") or ""),
                "wrapper_oracle": actual,
                "base_oracle": actual,
                "bridge_lemma": "",
                "reason": (
                    f"Adapter `{adapter.get('module_expr')}` relates "
                    f"the typed endpoint `{source_key}` to `{target_key}`."
                ),
            })
        for actual in _formal_child_oracle_actuals(
            formal=formal,
            formal_bound=formal_bound,
            oracle_candidates=oracle_candidates,
        ):
            instantiated_oracle = _substitute_formal_expr(source_o, formal, actual)
            if not instantiated_oracle or instantiated_oracle == source_o:
                continue
            source_roots = [source_root]
            adapter_root = str(adapter.get("main_d_root") or "")
            if formal_bound.endswith("IdealAll.RO") and adapter_root:
                source_roots.append(adapter_root)
            for bridge_source_root in _dedupe_strings(source_roots):
                source_expr = (
                    f"{bridge_source_root}({source_d}, "
                    f"{instantiated_oracle}).distinguish()"
                )
                target_expr = (
                    f"{adapter.get('main_d_root')}"
                    f"({adapter.get('module_expr')}, {formal_bound}).distinguish()"
                )
                source_key = _game_key(source_expr)
                target_key = _game_key(target_expr)
                if not source_key or not target_key or source_key == target_key:
                    continue
                out.append(_structural_bridge_record(
                    source_key=source_key,
                    target_key=target_key,
                    source_pr="",
                    target_pr="",
                    adapter=adapter,
                    actual=actual,
                    action_hint=(
                        f"Pr structural bridge: {source_key} -> {target_key}"
                    ),
                    reason=(
                        f"Adapter `{adapter.get('module_expr')}` receives "
                        f"child oracle `{actual}` inside `{source_o}`, while "
                        f"the typed MainD frontier exposes its bound oracle "
                        f"`{formal_bound}`."
                    ),
                ))
        if formal_bound.endswith("IdealAll.RO") and source_root == "MainD":
            source_key = _game_key(f"{source_root}({source_d}, RO).distinguish()")
            target_key = _game_key(
                f"{adapter.get('main_d_root')}"
                f"({source_d}, {formal_bound}).distinguish()"
            )
            if source_key and target_key and source_key != target_key:
                out.append(_structural_bridge_record(
                    source_key=source_key,
                    target_key=target_key,
                    source_pr="",
                    target_pr="",
                    adapter=adapter,
                    actual=formal_bound,
                    action_hint=(
                        f"Pr structural bridge: {source_key} -> {target_key}"
                    ),
                    reason=(
                        f"Adapter `{adapter.get('module_expr')}` uses a "
                        f"clone-scoped oracle bound `{formal_bound}`; align "
                        f"the generic MainD frontier for `{source_d}` with "
                        "that clone root before applying clone-local Pr rewrites."
                    ),
                ))
    return out[:64]


def _formal_child_oracle_actuals(
    *,
    formal: str,
    formal_bound: str,
    oracle_candidates: list[str],
) -> list[str]:
    if not formal or not formal_bound or "(" in formal_bound:
        return []
    out: list[str] = []
    for candidate in oracle_candidates:
        text = str(candidate or "").strip()
        if not text or text == formal or text == formal_bound:
            continue
        compact = _compact_expr(text)
        if compact == _compact_expr(f"{formal}.RO"):
            out.append(text)
            continue
        if compact.endswith("." + _compact_expr(f"{formal}.RO")):
            out.append(text)
    return _dedupe_strings(out)


def _contextual_structural_adapter_bridges(
    *,
    adapters: list[dict[str, Any]],
    current_terms: list[dict[str, str]],
    instantiated_rewrites: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    current_keys = {str(term.get("game_key") or "") for term in current_terms}
    root_by_module = {
        str(adapter.get("name") or ""): str(adapter.get("main_d_root") or "MainD")
        for adapter in adapters
        if str(adapter.get("name") or "")
    }
    out: list[dict[str, Any]] = []
    for adapter in adapters:
        if str(adapter.get("adapter_kind") or "") != "main_d_wrapper":
            continue
        adapter_module = str(adapter.get("module_expr") or adapter.get("name") or "")
        formal = str(adapter.get("formal_name") or "")
        formal_bound = str(adapter.get("formal_bound") or "")
        source_d = str(adapter.get("source_distinguisher_template") or "")
        source_o = str(adapter.get("source_oracle_template") or "")
        if not adapter_module or not formal or not formal_bound or not source_d or not source_o:
            continue
        source_root = root_by_module.get(
            source_d.split("(", 1)[0].rsplit(".", 1)[-1],
            "MainD",
        )
        source_oracle = _substitute_formal_expr(source_o, formal, formal_bound)
        if not source_oracle or source_oracle == source_o:
            continue
        source_expr = f"{source_root}({source_d}, {source_oracle}).distinguish()"
        source_key = _game_key(source_expr)
        if not source_key:
            continue
        for rewrite in instantiated_rewrites:
            if str(rewrite.get("adapter_module") or "") != adapter_module:
                continue
            lhs = _main_d_parts(str(rewrite.get("lhs_game") or ""))
            rhs = _main_d_parts(str(rewrite.get("rhs_game") or ""))
            if not lhs or not rhs:
                continue
            lhs_key = _game_key(str(rewrite.get("lhs_game") or ""))
            rhs_key = _game_key(str(rewrite.get("rhs_game") or ""))
            target = lhs if rhs_key in current_keys and lhs_key not in current_keys else {}
            if not target and lhs_key in current_keys and rhs_key not in current_keys:
                target = rhs
            if not target:
                continue
            target_expr = (
                f"{target.get('root')}({adapter_module}, "
                f"{target.get('oracle')}).distinguish()"
            )
            target_key = _game_key(target_expr)
            if not target_key or target_key == source_key:
                continue
            out.append(_structural_bridge_record(
                source_key=source_key,
                target_key=target_key,
                source_pr="",
                target_pr="",
                adapter=adapter,
                actual=formal_bound,
                action_hint=f"Pr structural bridge: {source_key} -> {target_key}",
                reason=(
                    f"Adapter `{adapter_module}` aligns the source wrapper "
                    f"`{source_key}` with the typed MainD frontier "
                    f"`{target_key}` exposed by the Pr rewrite context."
                ),
            ))
    return out[:32]


def _structural_bridge_record(
    *,
    source_key: str,
    target_key: str,
    source_pr: str,
    target_pr: str,
    adapter: dict[str, Any],
    actual: str,
    action_hint: str,
    reason: str,
) -> dict[str, Any]:
    return {
        "name": (
            "bridge_"
            + _safe_id(source_key)
            + "_to_"
            + _safe_id(target_key)
        ),
        "edge_kind": "synthetic_bridge",
        "relation": "equality",
        "lhs_game": source_key,
        "rhs_game": target_key,
        "source_pr": source_pr,
        "target_pr": target_pr,
        "tactic": "",
        "action_hint": action_hint,
        "adapter_module": str(adapter.get("module_expr") or adapter.get("name") or ""),
        "adapter_reason": str(adapter.get("reason") or ""),
        "wrapper_oracle": actual,
        "base_oracle": actual,
        "bridge_lemma": "",
        "reason": reason,
    }


def _instantiated_main_d_rewrites_for_adapters(
    *,
    adapters: list[dict[str, Any]],
    bridge_details: list[dict[str, Any]],
    instantiation_bindings: dict[str, Any],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for adapter in adapters:
        adapter_module = str(
            adapter.get("module_expr") or adapter.get("name") or ""
        )
        if not adapter_module:
            continue
        for detail in bridge_details:
            lhs = _main_d_parts(str(detail.get("lhs_game") or ""))
            rhs = _main_d_parts(str(detail.get("rhs_game") or ""))
            if not lhs or not rhs:
                continue
            root = str(lhs.get("root") or rhs.get("root") or "MainD")
            lhs_oracle = str(lhs.get("oracle") or "")
            rhs_oracle = str(rhs.get("oracle") or "")
            if not lhs_oracle or not rhs_oracle:
                continue
            lemma = str(detail.get("lemma") or detail.get("name") or "")
            lhs_expr = f"{root}({adapter_module}, {lhs_oracle}).distinguish()"
            rhs_expr = f"{root}({adapter_module}, {rhs_oracle}).distinguish()"
            key = (adapter_module, _game_key(lhs_expr), _game_key(rhs_expr))
            if key in seen or key[1] == key[2]:
                continue
            seen.add(key)
            out.append({
                "name": lemma,
                "lemma": lemma,
                "edge_kind": "pr_rewrite",
                "relation": "equality",
                "lhs_game": lhs_expr,
                "rhs_game": rhs_expr,
                "adapter_module": adapter_module,
                "source_template_lhs": str(detail.get("lhs_game") or ""),
                "source_template_rhs": str(detail.get("rhs_game") or ""),
                "action_hint": _typed_pr_rewrite_action_hint(
                    lemma,
                    adapter_module,
                    instantiation_bindings,
                    direction="forward",
                ),
                "backward_action_hint": _typed_pr_rewrite_action_hint(
                    lemma,
                    adapter_module,
                    instantiation_bindings,
                    direction="backward",
                ),
                "reason": (
                    f"Instantiate generic Pr rewrite `{lemma}` with "
                    f"typed adapter `{adapter_module}`."
                ),
            })
    return out[:32]


def _nearest_bridge_lemma_for_oracle(
    actual: str,
    bridge_details: list[dict[str, Any]],
) -> str:
    actual_root = _oracle_root(actual)
    for detail in bridge_details:
        lhs = _main_d_parts(str(detail.get("lhs_game") or ""))
        rhs = _main_d_parts(str(detail.get("rhs_game") or ""))
        if not lhs or not rhs:
            continue
        if actual_root in {
            _oracle_root(str(lhs.get("oracle") or "")),
            _oracle_root(str(rhs.get("oracle") or "")),
        }:
            return str(detail.get("lemma") or detail.get("name") or "")
    return ""


def _game_expr_with_proc(source_key: str, proc: str) -> str:
    proc_name = str(proc or "main").strip()
    if not proc_name:
        proc_name = "main"
    return f"{source_key}.{proc_name}()"


def _inner_get_adapter_module(body: str, formal_name: str) -> str:
    pattern = re.compile(r"\bmodule\s+([A-Za-z_][A-Za-z0-9_']*)\s*=\s*\{")
    for match in pattern.finditer(body):
        open_idx = match.end() - 1
        close_idx = _matching_bracket(body, open_idx, "{", "}")
        if close_idx <= open_idx:
            continue
        inner_body = body[open_idx + 1:close_idx]
        if re.search(
            rf"\bproc\s+f\s*=\s*{re.escape(formal_name)}\.get\b",
            inner_body,
        ):
            return match.group(1)
    return ""


def _adapter_distinguish_alias(body: str, inner_oracle: str) -> dict[str, str]:
    if not inner_oracle:
        return {}
    pattern = re.compile(
        r"\bproc\s+distinguish\s*(?:\([^)]*\))?\s*=\s*"
        r"(?P<callee>[A-Za-z_][A-Za-z0-9_'.]*\s*\(.*?\))\."
        r"(?P<proc>[A-Za-z_][A-Za-z0-9_']*)\b",
        flags=re.DOTALL,
    )
    for match in pattern.finditer(body):
        callee = re.sub(r"\s+", "", match.group("callee"))
        args_start = callee.find("(")
        if args_start < 0:
            continue
        args_end = _matching_bracket(callee, args_start, "(", ")")
        if args_end <= args_start:
            continue
        args = _split_top_level_args(callee[args_start + 1:args_end])
        if not args or _compact_expr(args[-1]) != _compact_expr(inner_oracle):
            continue
        root = callee[:args_start]
        distinguisher = f"{root}({', '.join(arg.strip() for arg in args[:-1])})"
        return {
            "callee": f"{callee}.{match.group('proc')}",
            "distinguisher": distinguisher,
            "procedure": match.group("proc"),
        }
    return {}


def _source_oracle_aliases(session_dir: str | Path | None) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for text, path, _kind in _session_source_texts(session_dir):
        for module in _module_bodies(text, path=path):
            name = str(module.get("name") or "")
            body = str(module.get("body") or "")
            base = _oracle_alias_base(body)
            if name and base:
                aliases[name] = base
    return aliases


def _oracle_alias_base(body: str) -> str:
    init = re.search(r"\bproc\s+init\s*=\s*([A-Za-z_][A-Za-z0-9_'.]*)\.init\b", body)
    get = re.search(r"\bproc\s+f\s*=\s*([A-Za-z_][A-Za-z0-9_'.]*)\.get\b", body)
    if init and get and init.group(1) == get.group(1):
        return init.group(1)
    return ""


def _module_bodies(text: str, *, path: Path) -> list[dict[str, Any]]:
    modules: list[dict[str, Any]] = []
    pattern = re.compile(
        r"\b(?:local\s+)?module\s+"
        r"(?P<name>[A-Z][A-Za-z0-9_']*)"
        r"\s*(?P<formals>\([^=]*?\))?\s*=\s*\{",
        flags=re.DOTALL,
    )
    for match in pattern.finditer(text):
        open_idx = match.end() - 1
        close_idx = _matching_bracket(text, open_idx, "{", "}")
        if close_idx <= open_idx:
            continue
        modules.append({
            "name": match.group("name"),
            "formals": match.group("formals") or "",
            "body": text[open_idx + 1:close_idx],
            "source_path": str(path),
        })
    return modules


def _module_formals(formals: str) -> list[dict[str, str]]:
    text = str(formals or "").strip()
    if text.startswith("(") and text.endswith(")"):
        text = text[1:-1]
    out: list[dict[str, str]] = []
    for arg in _split_top_level_args(text):
        match = re.match(
            r"\s*([A-Za-z_][A-Za-z0-9_']*)\s*:\s*"
            r"([A-Za-z_][A-Za-z0-9_'.]*)",
            arg,
        )
        if match:
            out.append({"name": match.group(1), "bound": match.group(2)})
    return out


def _session_source_texts(
    session_dir: str | Path | None,
) -> list[tuple[str, Path, str]]:
    texts: list[tuple[str, Path, str]] = []
    for path, kind in _session_context_files(session_dir):
        try:
            texts.append((
                path.read_text(encoding="utf-8", errors="replace"),
                path,
                kind,
            ))
        except Exception:
            continue
    return texts


# ─── Oracle-scheme normalization bridges ───
#
# Pattern handled here: the current Pr equality is between two experiment
# wrappers, and one side wraps a *concrete* scheme module ``M`` (e.g.
# ``Wrap(M)``).  A family-independent EasyCrypt idiom is that ``M`` has an
# open/parameterized functor form ``F(I0)`` (named after ``M``, such as
# ``OFoo``/``GenFoo`` for ``Foo``) that is extensionally equal to ``M`` once a
# state/init module ``I0`` is plugged in.  This pass proposes the
# endpoint-local normalization
#
#     have -> : Pr[W(.. M ..)] = Pr[W(.. F_qual(I0) ..)]
#                 by byequiv=>//; proc; inline *; sim.
#
# for each clone-qualified ``F`` and each in-scope module ``I0`` whose signature
# matches ``F``'s formal module-type bound.  The pass does NOT decide which
# functor / init / clone is correct: it enumerates type-plausible instantiations
# from name resolution + signature matching and leaves the daemon gate in
# ``_try_bridge_suggest`` to keep only the chain it actually proves.  The closer
# is the same generic relational closer used for synthetic bridges -- no scheme,
# game, oracle, invariant, or formal-name token is hard-coded.

_MIN_SCHEME_TOKEN_LEN = 4
_SCHEME_NORMALIZATION_CLOSER = "byequiv=>//; proc; inline *; sim."


def _clone_alias_map(session_dir: str | Path | None) -> dict[str, list[str]]:
    """Map a (simple) theory name to its clone aliases.

    Parses ``clone [import] THEORY as ALIAS`` so theory-local functors can be
    rendered with the clone qualifier the goal actually needs (an un-qualified
    member of a doubly-cloned theory is ambiguous and will not resolve).
    """
    out: dict[str, list[str]] = {}
    pattern = re.compile(
        r"\bclone\s+(?:import\s+)?(?P<theory>[A-Za-z_][A-Za-z0-9_'.]*)\s+as\s+"
        r"(?P<alias>[A-Za-z_][A-Za-z0-9_']*)"
    )
    for text, _path, _kind in _session_source_texts(session_dir):
        for match in pattern.finditer(text):
            theory = match.group("theory").rsplit(".", 1)[-1]
            alias = match.group("alias")
            out.setdefault(theory, [])
            if alias not in out[theory]:
                out[theory].append(alias)
    return out


def _clone_qualified_names(
    functor: dict[str, Any],
    alias_map: dict[str, list[str]],
) -> list[str]:
    name = str(functor.get("name") or "")
    theory = str(functor.get("theory") or "")
    if not name:
        return []
    if theory:
        return [f"{alias}.{name}" for alias in (alias_map.get(theory) or [])]
    return [name]


def _theory_ranges(text: str) -> list[tuple[str, int, int]]:
    out: list[tuple[str, int, int]] = []
    for match in re.finditer(
        r"\b(?:abstract\s+)?theory\s+([A-Za-z_][A-Za-z0-9_']*)\s*\.",
        str(text or ""),
    ):
        name = match.group(1)
        endm = re.search(rf"\bend\s+{re.escape(name)}\s*\.", text[match.end():])
        if endm:
            out.append((name, match.end(), match.end() + endm.start()))
    return out


def _enclosing_theory(ranges: list[tuple[str, int, int]], pos: int) -> str:
    theory = ""
    best_start = -1
    for name, start, end in ranges:
        if start <= pos < end and start > best_start:
            best_start = start
            theory = name
    return theory


def _scheme_normalization_functors(
    session_dir: str | Path | None,
) -> list[dict[str, Any]]:
    """Single-module-argument functors and the theory each is defined in.

    These are the candidate "open"/parameterized forms a concrete scheme can be
    normalized to.  Two-or-more argument functors (distinguishers, games) are
    excluded; the daemon, not this list, decides which functor is correct.
    """
    funcs: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    pattern = re.compile(
        r"\b(?:local\s+)?module\s+(?P<name>[A-Z][A-Za-z0-9_']*)\s*"
        r"\((?P<formals>[^=]*?)\)\s*(?::[^={]*)?=\s*\{"
    )
    for text, _path, _kind in _session_source_texts(session_dir):
        ranges = _theory_ranges(text)
        for match in pattern.finditer(text):
            formals = _module_formals("(" + match.group("formals") + ")")
            if len(formals) != 1:
                continue
            name = match.group("name")
            theory = _enclosing_theory(ranges, match.start())
            key = (name, theory)
            if key in seen:
                continue
            seen.add(key)
            funcs.append({
                "name": name,
                "formal_name": str(formals[0].get("name") or ""),
                "formal_bound": str(formals[0].get("bound") or ""),
                "theory": theory,
            })
    return funcs


def _concrete_module_names(session_dir: str | Path | None) -> set[str]:
    """Concrete (no-formal) module names declared in session context."""
    names: set[str] = set()
    pattern = re.compile(
        r"\b(?:local\s+)?module\s+([A-Z][A-Za-z0-9_']*)\s*(?::[^={(]*)?=\s*\{"
    )
    for text, _path, _kind in _session_source_texts(session_dir):
        for match in pattern.finditer(text):
            names.add(match.group(1))
    return names


def _module_body_procs(text: str, header_pattern: re.Pattern[str]) -> set[str]:
    match = header_pattern.search(text)
    if not match:
        return set()
    open_idx = match.end() - 1
    close_idx = _matching_bracket(text, open_idx, "{", "}")
    if close_idx <= open_idx:
        return set()
    body = text[open_idx + 1:close_idx]
    return set(re.findall(r"\bproc\s+([A-Za-z_][A-Za-z0-9_']*)", body))


def _module_type_procs(
    session_dir: str | Path | None,
    type_name: str,
) -> set[str]:
    if not type_name:
        return set()
    pattern = re.compile(rf"\bmodule\s+type\s+{re.escape(type_name)}\b[^=]*=\s*\{{")
    for text, _path, _kind in _session_source_texts(session_dir):
        procs = _module_body_procs(text, pattern)
        if procs:
            return procs
    return set()


def _concrete_module_procs(
    session_dir: str | Path | None,
    module_name: str,
) -> set[str]:
    if not module_name:
        return set()
    pattern = re.compile(
        rf"\b(?:local\s+)?module\s+{re.escape(module_name)}\s*(?::[^={{(]*)?=\s*\{{"
    )
    for text, _path, _kind in _session_source_texts(session_dir):
        procs = _module_body_procs(text, pattern)
        if procs:
            return procs
    return set()


def _modules_matching_module_type(
    session_dir: str | Path | None,
    bound: str,
    concrete: set[str],
) -> list[str]:
    """In-scope concrete modules whose procedure set covers module-type ``bound``.

    Exact-signature modules are ranked first so the type-faithful instantiation
    is probed within the daemon budget; broader supersets follow.
    """
    bound_simple = str(bound or "").rsplit(".", 1)[-1]
    required = _module_type_procs(session_dir, bound_simple)
    if not required:
        return []
    matches: list[tuple[int, str]] = []
    for name in sorted(concrete):
        procs = _concrete_module_procs(session_dir, name)
        if procs and required <= procs:
            matches.append((0 if procs == required else 1, name))
    matches.sort()
    return [name for _rank, name in matches][:4]


def _scheme_tokens_in_term(game_key: str, concrete: set[str]) -> list[str]:
    out: list[str] = []
    for token in re.findall(r"[A-Za-z_][A-Za-z0-9_']*", str(game_key or "")):
        if (
            len(token) >= _MIN_SCHEME_TOKEN_LEN
            and token in concrete
            and token not in out
        ):
            out.append(token)
    return out


def _substitute_module_token(text: str, token: str, replacement: str) -> str:
    if not token or not replacement:
        return str(text or "")
    return re.sub(
        rf"(?<![A-Za-z0-9_'.]){re.escape(token)}(?![A-Za-z0-9_'])",
        replacement,
        str(text),
    )


def _oracle_scheme_normalization_bridges(
    *,
    session_dir: str | Path | None,
    terms: list[dict[str, str]],
) -> list[dict[str, Any]]:
    if not terms:
        return []
    functors = _scheme_normalization_functors(session_dir)
    if not functors:
        return []
    concrete = _concrete_module_names(session_dir)
    if not concrete:
        return []
    alias_map = _clone_alias_map(session_dir)
    bound_members: dict[str, list[str]] = {}
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for term in terms:
        key = str(term.get("game_key") or "")
        if not _experiment_wrapper_parts(key):
            continue
        source_pr = str(term.get("pr_text") or "")
        if not source_pr:
            continue
        for scheme in _scheme_tokens_in_term(key, concrete):
            for functor in functors:
                fname = str(functor.get("name") or "")
                if fname == scheme or scheme not in fname:
                    continue
                bound = str(functor.get("formal_bound") or "")
                if bound not in bound_members:
                    bound_members[bound] = _modules_matching_module_type(
                        session_dir, bound, concrete,
                    )
                init_modules = bound_members.get(bound) or []
                qualified_names = _clone_qualified_names(functor, alias_map)
                for qualified in qualified_names:
                    for init_mod in init_modules:
                        if init_mod == scheme:
                            continue
                        replacement = f"{qualified}({init_mod})"
                        target_pr = _substitute_module_token(
                            source_pr, scheme, replacement,
                        )
                        if target_pr == source_pr or "Pr[" not in target_pr:
                            continue
                        tactic = (
                            f"have -> : {source_pr} = {target_pr} "
                            f"by {_SCHEME_NORMALIZATION_CLOSER}"
                        )
                        if tactic in seen:
                            continue
                        seen.add(tactic)
                        out.append({
                            "name": (
                                "scheme_norm_"
                                + _safe_id(scheme)
                                + "_to_"
                                + _safe_id(replacement)
                            ),
                            "edge_kind": "scheme_normalization_bridge",
                            "relation": "equality",
                            "lhs_game": key,
                            "rhs_game": _game_key(replacement),
                            "source_pr": source_pr,
                            "target_pr": target_pr,
                            "tactic": tactic,
                            "action_hint": tactic,
                            "adapter_module": qualified,
                            "scheme_module": scheme,
                            "init_module": init_mod,
                            "bridge_lemma": "",
                            "reason": (
                                f"Normalize concrete scheme `{scheme}` to its "
                                f"parameterized form `{replacement}` inside the "
                                "current wrapper endpoint before Pr "
                                "rewrite/game-hop handles."
                            ),
                        })
    return out[:24]


def _pr_wrapper_bridge_candidates(
    parsed: dict[str, Any],
    goal_text: str,
    handles: dict[str, Any],
    pr_path_plan: dict[str, Any],
) -> list[dict[str, Any]]:
    """Surface Pr endpoint-normalization bridges for experiment wrappers.

    This is a compiler-style gap filler for a common library pattern:
    a current endpoint is a concrete ``MainD(...).distinguish()`` game, a
    live Pr rewrite declaration connects that endpoint to another ``MainD``
    oracle variant, and the other side of the goal is still printed as a
    higher-level experiment wrapper such as ``...Distinguish(...).game()``.

    The pass does not know the target lemma proof.  It derives the missing
    ``MainD`` endpoint from the rewrite declaration and emits a probeable
    local ``have`` bridge for the wrapper endpoint.  If the probe fails, the
    right repair is to inspect wrapper definitions, not to guess arity such as
    ``distinguish(())``.
    """
    if str(parsed.get("goal_type") or "") != "probability":
        return []
    terms = _pr_term_records(goal_text)
    if len(terms) < 2:
        return []
    main_terms = [
        term for term in terms
        if _main_d_parts(str(term.get("game_key") or ""))
    ]
    wrapper_terms = [
        term for term in terms
        if _experiment_wrapper_parts(str(term.get("game_key") or ""))
    ]
    if not main_terms or not wrapper_terms:
        return []
    bridge_details = [
        _dict(item)
        for item in _list(handles.get("pr_rewrite_candidate_details"))
        if isinstance(item, dict)
    ]
    if not bridge_details:
        return []

    partial_frontiers = _pr_path_partial_frontiers(pr_path_plan)
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for main_term in main_terms:
        main_key = str(main_term.get("game_key") or "")
        main_parts = _dict(_main_d_parts(main_key))
        if not main_parts:
            continue
        for detail in bridge_details:
            counterpart = _main_d_counterpart_from_bridge(main_parts, detail)
            if not counterpart:
                continue
            target_key = str(counterpart.get("key") or "")
            if partial_frontiers and not any(
                _main_d_keys_compatible(target_key, frontier)
                for frontier in partial_frontiers
            ):
                # When the path planner already exposed a frontier, use it to
                # avoid inventing unrelated wrapper gaps.
                continue
            for wrapper_term in wrapper_terms:
                wrapper_key = str(wrapper_term.get("game_key") or "")
                target_pr = _pr_term_for_game(
                    str(counterpart.get("expr") or ""),
                    memory=str(wrapper_term.get("memory") or "&m"),
                    event=str(wrapper_term.get("event") or "res"),
                )
                source_pr = str(wrapper_term.get("pr_text") or "")
                if not source_pr or not target_pr:
                    continue
                tactic = (
                    f"have -> : {source_pr} = {target_pr} "
                    "by byequiv => //; proc; inline *; sim."
                )
                if tactic in seen:
                    continue
                seen.add(tactic)
                lemma = str(detail.get("lemma") or detail.get("name") or "")
                out.append({
                    "tactic": tactic,
                    "bridge_lemma": lemma,
                    "source_endpoint_key": main_key,
                    "target_endpoint_key": target_key,
                    "experiment_wrapper_key": wrapper_key,
                    "target_pr": target_pr,
                    "source_pr": source_pr,
                    "reason": (
                        f"Pr rewrite `{lemma}` can move the visible MainD "
                        f"endpoint through `{target_key}`; first normalize "
                        f"the experiment-wrapper endpoint `{wrapper_key}` to "
                        "that MainD entrypoint."
                    ),
                })
    return out[:4]


def _pr_path_partial_frontiers(pr_path_plan: dict[str, Any]) -> set[str]:
    frontiers: set[str] = set()
    for partial in _list(_dict(pr_path_plan).get("partial_paths")):
        if not isinstance(partial, dict):
            continue
        frontier = str(partial.get("frontier_key") or "")
        if frontier:
            frontiers.add(frontier)
    return frontiers


def _main_d_counterpart_from_bridge(
    main_parts: dict[str, Any],
    detail: dict[str, Any],
) -> dict[str, str]:
    lhs = _main_d_parts(str(detail.get("lhs_game") or ""))
    rhs = _main_d_parts(str(detail.get("rhs_game") or ""))
    if not lhs or not rhs:
        return {}
    current_oracle = _compact_expr(str(main_parts.get("oracle") or ""))
    lhs_oracle = _compact_expr(str(lhs.get("oracle") or ""))
    rhs_oracle = _compact_expr(str(rhs.get("oracle") or ""))
    target_oracle = ""
    if current_oracle == lhs_oracle:
        target_oracle = str(rhs.get("oracle") or "")
    elif current_oracle == rhs_oracle:
        target_oracle = str(lhs.get("oracle") or "")
    if not target_oracle:
        return {}
    root = str(main_parts.get("root") or "MainD")
    distinguisher = str(main_parts.get("distinguisher") or "")
    if not root or not distinguisher:
        return {}
    expr = f"{root}({distinguisher}, {target_oracle}).distinguish()"
    return {
        "expr": expr,
        "key": _game_key(expr),
    }


def _main_d_keys_compatible(left: str, right: str) -> bool:
    if left == right:
        return True
    lparts = _main_d_parts(left)
    rparts = _main_d_parts(right)
    if not lparts or not rparts:
        return False
    return (
        str(lparts.get("root") or "").rsplit(".", 1)[-1]
        == str(rparts.get("root") or "").rsplit(".", 1)[-1]
        and _compact_expr(str(lparts.get("oracle") or ""))
        == _compact_expr(str(rparts.get("oracle") or ""))
    )


def _main_d_parts(key: str) -> dict[str, str]:
    text = str(key or "").strip()
    match = re.match(
        r"(?P<root>(?:[A-Za-z_][A-Za-z0-9_']*\.)*MainD)\s*\(",
        text,
    )
    if not match:
        return {}
    open_idx = match.end() - 1
    close_idx = _matching_bracket(text, open_idx, "(", ")")
    if close_idx <= open_idx:
        return {}
    args = _split_top_level_args(text[open_idx + 1 : close_idx])
    if len(args) < 2:
        return {}
    return {
        "root": match.group("root"),
        "distinguisher": args[0].strip(),
        "oracle": args[1].strip(),
    }


def _experiment_wrapper_parts(key: str) -> dict[str, Any]:
    text = str(key or "").strip()
    match = re.match(
        r"(?P<root>[A-Za-z_][A-Za-z0-9_']*(?:\.[A-Za-z_][A-Za-z0-9_']*)*)\s*\(",
        text,
    )
    if not match:
        return {}
    root = match.group("root")
    if root.endswith("MainD") or root == "MainD":
        return {}
    open_idx = match.end() - 1
    close_idx = _matching_bracket(text, open_idx, "(", ")")
    if close_idx <= open_idx:
        return {}
    args = _split_top_level_args(text[open_idx + 1 : close_idx])
    if len(args) < 2:
        return {}
    is_known_distinguish = root.endswith("Distinguish") or "Distinguish" in root
    is_experiment_like = (
        root.endswith("_game")
        or root.endswith("game")
        or "Game" in root
        or "game" in root
        or _expr_mentions_oracle(args[-1])
    )
    if not is_known_distinguish and not is_experiment_like:
        return {}
    return {
        "root": root,
        "args": args,
        "distinguisher": args[0].strip(),
        "oracle": args[1].strip(),
    }


def _expr_mentions_oracle(expr: str) -> bool:
    return bool(re.search(r"\b(?:RO|FinRO|IndRO|[A-Za-z_][A-Za-z0-9_']*RO)\b", str(expr or "")))


def _pr_term_records(goal_text: str) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for term in _canonical_parse_pr_terms(
        goal_text,
        default_memory="&m",
        default_event="res",
        require_endpoint=False,
    ):
        key = str(term.get("game_key") or "")
        if not key:
            continue
        out.append({
            "pr_text": str(term.get("pr_text") or ""),
            "game_expr": str(term.get("game_expr") or ""),
            "game_key": key,
            "memory": str(term.get("memory") or "&m"),
            "event": str(term.get("event") or "res"),
        })
    return out


def _compact_expr(text: str) -> str:
    return re.sub(r"\s+", "", str(text or ""))



__all__ = [
    "PR_BRIDGE_FRONTEND_KIND",
    "PR_BRIDGE_FRONTEND_SCHEMA_VERSION",
    "build_pr_typed_bridge_frontend",
    "pr_wrapper_bridge_candidates",
]
