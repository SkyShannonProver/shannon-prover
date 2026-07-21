"""Action/menu rendering helpers for EasyCrypt ProofIR facts.

This module is the first split of the ProofIR action layer.  It renders
read-only inspection/search actions from already-computed handles; it does not
derive new proof facts and does not probe EasyCrypt.
"""
from __future__ import annotations

from typing import Any

from core.easycrypt.analysis.ec_utils import (
    as_dict as _dict,
    as_list as _list,
    safe_id,
)
from core.easycrypt.analysis.ec_action_contracts import (
    normalize_action_candidate,
)


MENU_ACTIONS_SCHEMA_VERSION = 1
MENU_ACTIONS_KIND = "easycrypt_menu_actions"


def ambient_named_closer_menu_items(handles: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for closer in _list(_dict(handles).get("ambient_named_closers")):
        if not isinstance(closer, dict):
            continue
        lemma = str(closer.get("lemma") or "")
        tactic = str(closer.get("tactic") or "")
        if not lemma or not tactic:
            continue
        items.append(menu_item(
            f"ambient_exact_{safe_id(lemma)}",
            tactic=tactic,
            tactic_family="ambient_close",
            action_type="tactic_candidate",
            cost="cheap",
            why=str(
                closer.get("reason")
                or f"Loaded context contains `{lemma}` for this ambient residual."
            ),
            preconditions=[
                "the current ambient goal still matches the lemma conclusion",
            ],
            preserves=["ambient logic layer"],
            cost_factors={
                "lemma": lemma,
                "source_path": str(closer.get("source_path") or ""),
            },
        ))
    return items


def semantic_pr_bound_menu_items(handles: dict[str, Any]) -> list[dict[str, Any]]:
    arithmetic_plan = _dict(
        _dict(_dict(handles).get("pr_path_plan")).get("arithmetic_plan")
    )
    if arithmetic_plan.get("available") or str(arithmetic_plan.get("shape") or ""):
        return []
    items: list[dict[str, Any]] = []
    candidates = _list(_dict(handles).get("semantic_pr_bound_candidates"))[:3]
    for idx, candidate in enumerate(candidates):
        if not isinstance(candidate, dict):
            continue
        lemma = str(candidate.get("lemma") or "")
        if not lemma:
            continue
        tags = [
            str(tag) for tag in _list(candidate.get("semantic_tags"))
            if str(tag)
        ]
        items.append(menu_item(
            f"semantic_pr_bound_{safe_id(lemma)}",
            tactic=f"-where {lemma}",
            tactic_family="signature_lookup",
            action_type="inspection_action",
            cost="free" if idx == 0 else "cheap",
            why=str(
                candidate.get("reason")
                or (
                    "Semantic lemma index found a project-local Pr bound "
                    "candidate for this inequality."
                )
            ),
            preconditions=[
                "inspect the declaration before choosing apply/have/rewrite form",
                "treat this as resource lookup, not as a proof step",
            ],
            preserves=["proof state", "Pr abstraction"],
            cost_factors={
                "lemma": lemma,
                "score": int(candidate.get("score") or 0),
                "semantic_tags": tags,
                "goal_shape": str(candidate.get("goal_shape") or ""),
                "source_path": str(candidate.get("source_path") or ""),
                "pr_game_keys": list(candidate.get("pr_game_keys") or [])[:4],
                "pr_events": list(candidate.get("pr_events") or [])[:4],
            },
        ))
    return items


def native_ast_search_menu_items(handles: dict[str, Any]) -> list[dict[str, Any]]:
    native = _dict(_dict(handles).get("native_ast_search"))
    if not native.get("available"):
        return []
    items: list[dict[str, Any]] = []
    for hit in _list(native.get("hits"))[:4]:
        if not isinstance(hit, dict):
            continue
        name = str(hit.get("name") or "")
        if not name:
            continue
        query = str(hit.get("query") or "")
        items.append(menu_item(
            f"native_ast_hit_{safe_id(name)}",
            tactic=f"-where {name}",
            tactic_family="native_ast_search",
            action_type="inspection_action",
            cost="moderate",
            why=(
                "EasyCrypt native AST search found "
                f"`{name}`"
                + (f" for query `{query}`" if query else "")
                + "; inspect the clone-resolved declaration before applying it."
            ),
            preconditions=[
                "current goal still contains the searched operator skeleton",
                "inspect declaration/arity before applying or rewriting",
            ],
            preserves=["proof state"],
            cost_factors={
                "query": query,
                "source": "search-skeleton",
                "artifact": str(hit.get("artifact") or ""),
                "declaration_kind": str(hit.get("kind") or ""),
            },
        ))
    if items:
        return items
    for idx, query in enumerate(_list(native.get("suggested_queries"))[:2]):
        if not isinstance(query, dict):
            continue
        action = str(query.get("action") or "")
        q = str(query.get("query") or "")
        if not action or not q:
            continue
        items.append(menu_item(
            f"native_ast_search_{idx}",
            tactic=action,
            tactic_family="native_ast_search",
            action_type="inspection_action",
            cost="moderate",
            why=str(
                query.get("reason")
                or "Use EasyCrypt native AST/operator search before regex search."
            ),
            preconditions=[
                "read search-skeleton hits as candidates, not as verified tactics",
                "follow up with `-where <lemma>` for any promising hit",
            ],
            preserves=["proof state"],
            cost_factors={"query": q, "source": "easycrypt_native_search"},
        ))
    return items


def menu_item(
    item_id: str,
    *,
    tactic: str,
    tactic_family: str,
    action_type: str,
    cost: str,
    why: str,
    preconditions: list[str] | None = None,
    preserves: list[str] | None = None,
    destroys: list[str] | None = None,
    cost_factors: dict[str, Any] | None = None,
    program_rank: int | None = None,
    scheduler_role: str | None = None,
) -> dict[str, Any]:
    item = {
        "id": item_id,
        "tactic": tactic,
        "tactic_family": tactic_family,
        "action_type": action_type,
        "cost": cost,
        "why": why,
        "preconditions": list(preconditions or []),
        "preserves": list(preserves or []),
        "destroys": list(destroys or []),
        "cost_factors": dict(cost_factors or {}),
        "confidence": "medium",
    }
    if program_rank is not None:
        item["program_rank"] = program_rank
    if scheduler_role:
        item["scheduler_role"] = scheduler_role
    return normalize_action_candidate(item)


__all__ = [
    "MENU_ACTIONS_KIND",
    "MENU_ACTIONS_SCHEMA_VERSION",
    "ambient_named_closer_menu_items",
    "menu_item",
    "native_ast_search_menu_items",
    "safe_id",
    "semantic_pr_bound_menu_items",
]
