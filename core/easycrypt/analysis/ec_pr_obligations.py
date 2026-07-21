"""Typed obligation planning for EasyCrypt probability goals.

This module owns Pr-goal middle-end classification: normalization shells,
additive/union-bound structure, native-search needs, and semantic bound-lemma
lookup opportunities.  It intentionally does not commit proof tactics.
"""
from __future__ import annotations

import re
from typing import Any

from core.easycrypt.analysis.ec_utils import as_dict as _dict, as_list as _list


PR_OBLIGATION_SCHEMA_VERSION = 1
PR_OBLIGATION_KIND = "easycrypt_pr_obligation_plan"


def build_pr_normal_form(
    parsed: dict[str, Any],
    goal_type: str,
    goal_text: str,
) -> dict[str, Any]:
    """Classify outer Pr arithmetic shells that should be handled at Pr layer."""
    if goal_type != "probability":
        return {"available": False, "reason": "not_probability"}
    form = str(_dict(parsed).get("prob_form") or "")
    body = goal_body(goal_text)
    flat = re.sub(r"\s+", " ", body).strip()
    reasons: list[str] = []
    shell = ""
    is_equality = is_probability_equality_form(form, flat)
    if is_equality and has_common_unary_minus_pr_shell(flat):
        shell = "common_unary_minus"
        reasons.append("both sides are under the same unary minus Pr shell")
    elif is_equality and (
        has_additive_pr_shell(flat) or form in {"diff_eq", "adv_eq"}
    ):
        shell = "additive_or_advantage_shell"
        reasons.append("the probability equality is wrapped in additive/subtractive structure")
    elif is_probability_union_bound_shape(form, flat):
        shell = "union_bound_or_additive_inequality"
        reasons.append(
            "the probability inequality has additive Pr structure; Pr-level inequality planning is route context, while congr usually does not match inequality goals"
        )
    congr_subgoals = _list(_dict(parsed).get("congr_subgoals"))
    if is_equality and congr_subgoals and not shell:
        shell = "parser_congr_subgoals"
        reasons.append("goal parser produced congr subgoal previews")
    if not shell:
        return {
            "available": False,
            "goal_form": form,
            "reason": "already_atomic_or_unknown",
        }
    return {
        "available": True,
        "goal_form": form,
        "normalization_kind": shell,
        "recommended_tactic": (
            "congr."
            if shell in {
                "common_unary_minus",
                "additive_or_advantage_shell",
                "parser_congr_subgoals",
            } else
            ""
        ),
        "reason": "; ".join(reasons),
        "congr_subgoals": congr_subgoals,
    }


def build_pr_obligation_plan(
    *,
    parsed: dict[str, Any],
    goal_type: str,
    goal_text: str,
    pr_normal_form: dict[str, Any] | None = None,
    pr_path_plan: dict[str, Any] | None = None,
    semantic_pr_bound_candidates: list[dict[str, Any]] | None = None,
    native_ast_search: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return typed Pr obligations and a stable high-level proof strategy."""
    if str(goal_type or "") != "probability":
        return {
            "schema_version": PR_OBLIGATION_SCHEMA_VERSION,
            "kind": PR_OBLIGATION_KIND,
            "available": False,
            "reason": "not_probability",
            "obligations": [],
            "primary_strategy": "not_probability",
        }
    parsed = _dict(parsed)
    normal = (
        dict(pr_normal_form)
        if isinstance(pr_normal_form, dict) else
        build_pr_normal_form(parsed, goal_type, goal_text)
    )
    path_plan = _dict(pr_path_plan)
    arithmetic_plan = _dict(path_plan.get("arithmetic_plan"))
    semantic_bounds = [
        _dict(item) for item in (semantic_pr_bound_candidates or [])
        if isinstance(item, dict)
    ]
    native = _dict(native_ast_search)
    native_queries = [
        _dict(item) for item in _list(native.get("suggested_queries"))
        if isinstance(item, dict)
    ]
    pr_shape = native_ast_pr_arithmetic_shape(parsed, goal_type, goal_text)
    obligations: list[dict[str, Any]] = []

    if normal.get("available"):
        normal_kind = str(normal.get("normalization_kind") or "")
        if normal_kind == "union_bound_or_additive_inequality":
            obligations.append({
                "kind": "pr_union_bound_plan",
                "why": str(
                    normal.get("reason")
                    or "Pr inequality has additive/union-bound structure."
                ),
                "evidence": {
                    "normalization_kind": normal_kind,
                    "goal_form": str(normal.get("goal_form") or ""),
                },
                "action_boundary": "strategy_only",
            })
        else:
            obligations.append({
                "kind": "pr_normalization",
                "why": str(
                    normal.get("reason")
                    or "Normalize the outer Pr arithmetic shell."
                ),
                "evidence": {
                    "normalization_kind": normal_kind,
                    "recommended_tactic": str(normal.get("recommended_tactic") or ""),
                    "goal_form": str(normal.get("goal_form") or ""),
                },
                "action_boundary": "unverified_tactic_candidate",
            })

    arithmetic_chain = [
        str(item) for item in _list(arithmetic_plan.get("recommended_chain"))
        if str(item)
    ]
    arithmetic_candidates = [
        str(item) for item in _list(arithmetic_plan.get("candidate_lemmas"))
        if str(item)
    ]
    if arithmetic_plan.get("available") or arithmetic_chain or arithmetic_candidates:
        obligations.append({
            "kind": "pr_arithmetic_chain",
            "why": str(
                arithmetic_plan.get("strategy")
                or "Pr path planner found an arithmetic/bound composition."
            ),
            "evidence": {
                "shape": str(arithmetic_plan.get("shape") or pr_shape),
                "recommended_chain": arithmetic_chain,
                "candidate_lemmas": arithmetic_candidates,
            },
            "action_boundary": "strategy_only",
        })

    if semantic_bounds:
        obligations.append({
            "kind": "pr_semantic_bound_lookup",
            "why": (
                "Project-local Pr bound lemmas overlap the current goal by "
                "canonical game/event shape."
            ),
            "evidence": {
                "candidate_count": len(semantic_bounds),
                "top_candidates": [
                    {
                        "lemma": str(item.get("lemma") or ""),
                        "score": int(item.get("score") or 0),
                        "semantic_tags": [
                            str(tag) for tag in _list(item.get("semantic_tags"))
                            if str(tag)
                        ],
                    }
                    for item in semantic_bounds[:4]
                ],
            },
            "action_boundary": "inspection_before_apply",
        })

    if pr_shape and native_queries:
        obligations.append({
            "kind": "pr_native_bound_search",
            "why": (
                "EC native AST search can surface library Pr/mu/real-order "
                "lemmas for the current probability shape."
            ),
            "evidence": {
                "shape": pr_shape,
                "queries": [
                    str(item.get("query") or "") for item in native_queries
                    if str(item.get("query") or "")
                ][:4],
            },
            "action_boundary": "inspection_before_apply",
        })

    obligations = _dedupe_obligations(obligations)
    return {
        "schema_version": PR_OBLIGATION_SCHEMA_VERSION,
        "kind": PR_OBLIGATION_KIND,
        "available": bool(obligations),
        "reason": "pr_obligations_found" if obligations else "no_pr_obligation_shape",
        "primary_strategy": _primary_strategy(obligations),
        "arithmetic_shape": pr_shape,
        "obligations": obligations,
        "summary": {
            "obligation_count": len(obligations),
            "has_semantic_bound_lookup": any(
                item.get("kind") == "pr_semantic_bound_lookup"
                for item in obligations
            ),
            "has_arithmetic_chain": any(
                item.get("kind") == "pr_arithmetic_chain"
                for item in obligations
            ),
            "has_union_bound_plan": any(
                item.get("kind") == "pr_union_bound_plan"
                for item in obligations
            ),
        },
    }


def native_ast_pr_arithmetic_shape(
    parsed: dict[str, Any],
    goal_type: str,
    goal_text: str,
) -> str:
    """Classify Pr inequality shapes relevant to EC native AST search."""
    if str(goal_type or "") != "probability" and "Pr[" not in str(goal_text or ""):
        return ""
    return classify_pr_arithmetic_shape(
        parsed,
        goal_text,
        min_probability_inequality_pr_terms=1,
    )


def classify_pr_arithmetic_shape(
    parsed: dict[str, Any],
    goal_text: str,
    *,
    min_probability_inequality_pr_terms: int = 1,
) -> str:
    """Classify Pr arithmetic shells while preserving caller-specific gates."""
    form = str(_dict(parsed).get("prob_form") or "")
    flat = re.sub(r"\s+", " ", str(goal_text or "")).strip()
    pr_count = len(re.findall(r"Pr\s*\[", flat))
    if (
        "ineq" in form
        and ("`|" in flat or "|" in flat)
        and "-" in flat
        and "<=" in flat
        and pr_count >= 2
    ):
        return "absolute_pr_difference_bound"
    if form in {"adv_ineq", "adv_diff_ineq"}:
        return "absolute_pr_difference_bound"
    if "<=" in flat and "+" in flat and pr_count >= 2:
        return "additive_pr_inequality"
    if (
        "ineq" in form
        and pr_count >= max(1, int(min_probability_inequality_pr_terms))
    ):
        return "probability_inequality"
    return ""


def goal_body(goal_text: str) -> str:
    """Return the body after an EasyCrypt goal separator, if present."""
    if not goal_text:
        return ""
    parts = re.split(r"^-{5,}\s*$", goal_text, maxsplit=1, flags=re.MULTILINE)
    return parts[-1] if parts else goal_text


def is_probability_equality_form(form: str, flat_goal: str) -> bool:
    if "ineq" in form:
        return False
    if form in {"eq", "diff_eq", "adv_eq"} or form.endswith("_eq"):
        return True
    return bool(re.search(r"(?<![<=>])=(?!=|>)", flat_goal))


def is_probability_union_bound_shape(form: str, flat_goal: str) -> bool:
    if form not in {"compound", "adv_diff_ineq"} and "ineq" not in form:
        return False
    if "<=" not in flat_goal:
        return False
    return len(re.findall(r"Pr\s*\[", flat_goal)) >= 2 and "+" in flat_goal


def has_common_unary_minus_pr_shell(flat_goal: str) -> bool:
    if not flat_goal:
        return False
    return bool(re.search(r"^\s*-\s*Pr\s*\[.+\]\s*=\s*-\s*Pr\s*\[", flat_goal))


def has_additive_pr_shell(flat_goal: str) -> bool:
    if not flat_goal:
        return False
    pr_count = len(re.findall(r"Pr\s*\[", flat_goal))
    if pr_count < 2:
        return False
    return bool(re.search(r"Pr\s*\[[^\]]+\]\s*(?:\+|-)", flat_goal))


def _primary_strategy(obligations: list[dict[str, Any]]) -> str:
    kinds = [str(item.get("kind") or "") for item in obligations]
    for kind, strategy in (
        ("pr_arithmetic_chain", "use_pr_arithmetic_chain"),
        ("pr_union_bound_plan", "decompose_pr_union_bound"),
        ("pr_semantic_bound_lookup", "inspect_semantic_bound_candidates"),
        ("pr_normalization", "normalize_pr_shell"),
        ("pr_native_bound_search", "run_native_pr_search"),
    ):
        if kind in kinds:
            return strategy
    return "no_pr_obligation"


def _dedupe_obligations(obligations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in obligations:
        kind = str(item.get("kind") or "")
        if not kind or kind in seen:
            continue
        seen.add(kind)
        out.append(item)
    return out


__all__ = [
    "PR_OBLIGATION_KIND",
    "PR_OBLIGATION_SCHEMA_VERSION",
    "build_pr_normal_form",
    "build_pr_obligation_plan",
    "classify_pr_arithmetic_shape",
    "goal_body",
    "has_additive_pr_shell",
    "has_common_unary_minus_pr_shell",
    "is_probability_equality_form",
    "is_probability_union_bound_shape",
    "native_ast_pr_arithmetic_shape",
]
