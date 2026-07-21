"""Program-level IR for EasyCrypt pRHL/procedure proof states.

This pass is the program-structure half of ProofIR.  It normalizes the shallow
goal-parser statement dictionaries into stable statement/call-site records and
annotates which calls are at EasyCrypt's current "last-call" frontier.

The frontier distinction mirrors EasyCrypt's call rule: `call <lemma>` consumes
the last statement call(s), not an arbitrary call that merely appears somewhere
in the program body.
"""
from __future__ import annotations

import re
from typing import Any, Iterable

from core.easycrypt.analysis.ec_utils import (
    as_dict as _dict,
    as_list as _list,
    dedupe_strings as _dedupe_strings,
    deduped_string_list as _strings,
    infer_statement_kind as _infer_kind,
    int_or_default as _int_or_default,
    is_emit_safe_var as _is_emit_safe_var,
    procedure_tail as _proc_tail,
    safe_id as _safe_id,
    split_flat_conjuncts as _split_flat_conjuncts,
)
from core.easycrypt.analysis.ec_procedure_ref import (
    parse_call_statement as _parse_call_statement,
    procedure_spine_key as _procedure_spine_key,
)
from core.easycrypt.analysis.ec_native_state import (
    annotate_program_fallback,
    program_authority,
)
from core.easycrypt.analysis.ec_dataflow_invariant import (
    build_invariant_skeleton,
)


PROGRAM_IR_SCHEMA_VERSION = 1
PROGRAM_IR_KIND = "easycrypt_program_ir"


def build_program_ir(
    parsed_goal: dict[str, Any],
    goal_type: str,
    *,
    goal_text: str = "",
) -> dict[str, Any]:
    """Build a JSON-ready program IR from parsed goal dictionaries."""
    parsed = annotate_program_fallback(_dict(parsed_goal))
    authority = program_authority(parsed)
    abstract_modules = _abstract_module_names(goal_text)
    statements: list[dict[str, Any]] = []
    for side, key in (("left", "left_statements"), ("right", "right_statements")):
        for order, stmt in enumerate(_list(parsed.get(key)), start=1):
            if not isinstance(stmt, dict):
                continue
            statements.append(_normalize_statement(
                stmt,
                side=side,
                order=order,
                abstract_modules=abstract_modules,
            ))

    _annotate_statement_context(statements)
    _mark_frontier(statements)
    call_sites = [stmt for stmt in statements if stmt.get("is_call_site")]
    frontier = _frontier_summary(statements, goal_type)
    program_diff = _program_diff(statements, frontier, parsed)
    program_ast = _program_ast(statements)
    return {
        "schema_version": PROGRAM_IR_SCHEMA_VERSION,
        "kind": PROGRAM_IR_KIND,
        "goal_type": goal_type,
        "fact_source": authority["fact_source"],
        "authority": authority["authority"],
        "authority_rank": authority["authority_rank"],
        "ec_ground_truth": authority["ec_ground_truth"],
        "native_artifact": authority["native_artifact"],
        "program_ast": program_ast,
        "statements": statements,
        "call_sites": call_sites,
        "frontier": frontier,
        "program_diff": program_diff,
        "summary": {
            "statement_count": len(statements),
            "call_site_count": len(call_sites),
            "frontier_call_site_count": len(frontier["frontier_call_site_ids"]),
            "non_frontier_call_site_count": len([
                site for site in call_sites
                if not site.get("is_frontier_call")
            ]),
            "has_statement_paths": any(
                stmt.get("statement_path") for stmt in statements
            ),
            "program_ast_block_count": len(program_ast["blocks"]),
            "aligned_call_pair_count": program_diff["summary"][
                "aligned_call_pair_count"
            ],
            "shifted_call_pair_count": program_diff["summary"][
                "shifted_call_pair_count"
            ],
            "edit_script_v2_slice_count": program_diff["summary"][
                "edit_script_v2_slice_count"
            ],
        },
    }


def annotate_callable_lemma_handles(
    program_ir: dict[str, Any],
    handles: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Attach ProgramIR call-site/frontier facts to callable lemma handles."""
    call_sites = [
        site for site in _list(_dict(program_ir).get("call_sites"))
        if isinstance(site, dict)
    ]
    oracle_sources = [
        site for site in call_sites
        if str(site.get("frontier_role") or "") == "oracle_obligation_source"
    ]
    same_concrete_index = _same_concrete_call_pair_index(call_sites)
    diff_index = _diff_index(program_ir)
    plan_index = _action_plan_index(program_ir)
    slice_index = _edit_script_v2_index(program_ir)
    out: list[dict[str, Any]] = []
    for handle in handles:
        if not isinstance(handle, dict):
            continue
        item = dict(handle)
        proc = str(item.get("procedure") or "")
        procedures = _strings(item.get("procedures")) or ([proc] if proc else [])
        linked = [
            site for site in call_sites
            if any(
                _procedure_matches(candidate, str(site.get("procedure") or ""))
                for candidate in procedures
            )
        ]
        frontier = [site for site in linked if site.get("is_frontier_call")]
        oracle_source_matches = [
            site for site in oracle_sources
            if _handle_matches_oracle_source(procedures, site)
        ]
        item["live_call_site_ids"] = [
            str(site.get("call_site_id") or site.get("id") or "")
            for site in linked
            if site.get("call_site_id") or site.get("id")
        ]
        item["frontier_call_site_ids"] = [
            str(site.get("call_site_id") or site.get("id") or "")
            for site in frontier
            if site.get("call_site_id") or site.get("id")
        ]
        orders = [
            int(site.get("order") or 9999)
            for site in linked
            if str(site.get("side") or "") == "left"
        ] or [
            int(site.get("order") or 9999)
            for site in linked
        ]
        item["program_order"] = min(orders) if orders else 9999
        item["program_rank"] = item["program_order"] * 10 + (
            0 if frontier else 5 if linked else 9
        )
        diff_steps = _handle_diff_steps(linked, diff_index)
        if diff_steps:
            item["program_diff_steps"] = diff_steps
        same_concrete_pairs = _handle_same_concrete_pairs(
            linked,
            same_concrete_index,
        )
        if same_concrete_pairs:
            item["same_concrete_call_pairs"] = same_concrete_pairs
            item["call_handle_relevance"] = (
                "off_frontier_named_equiv_for_same_concrete_call_pair"
                if not frontier else
                "frontier_named_equiv_for_same_concrete_call_pair"
            )
        action_plans = _handle_action_plans(linked, plan_index, item)
        if action_plans:
            item["program_action_plans"] = action_plans
            item["next_program_action"] = action_plans[0]["phase_order"][0]
        slices = _handle_edit_script_v2_slices(linked, slice_index, item)
        if slices:
            item["program_edit_script_v2"] = slices
        item["callable_now"] = bool(frontier)
        item["requires_cut_to_frontier"] = bool(linked and not frontier)
        item["oracle_obligation_source_call_site_ids"] = [
            str(site.get("call_site_id") or site.get("id") or "")
            for site in oracle_source_matches
            if site.get("call_site_id") or site.get("id")
        ]
        item["handle_role"] = (
            "frontier_handle" if frontier else
            "non_frontier_handle" if linked else
            "oracle_obligation_handle" if oracle_source_matches else
            "unmatched_handle"
        )
        item["frontier_status"] = (
            "callable_now" if frontier else
            "requires_cut" if linked else
            "oracle_obligation" if oracle_source_matches else
            "no_matching_live_call_site"
        )
        if (
            same_concrete_pairs
            and linked
            and not frontier
            and item["frontier_status"] == "requires_cut"
        ):
            item["frontier_status_detail"] = (
                "matching call is part of a same-concrete-procedure pair; "
                "treat named cross-procedure lemmas as lower-priority until "
                "the local synchronized region has been accounted for"
            )
        if linked:
            item["matched_call_sites"] = [
                _compact_call_site(site) for site in linked[:4]
            ]
        if oracle_source_matches:
            item["oracle_obligation_sources"] = [
                _compact_call_site(site) for site in oracle_source_matches[:4]
            ]
        if item["requires_cut_to_frontier"]:
            item["repair_hint"] = _repair_hint_from_action_plans(
                action_plans,
                fallback=(
                    "Use `wp`, `seq`, or a targeted transform to make the "
                    "matching call the last-call frontier before `call <lemma>`."
                ),
            )
        out.append(item)
    return sorted(
        out,
        key=lambda item: (
            int(item.get("program_rank") or 9999),
            str(item.get("lemma") or ""),
        ),
    )


def _program_diff(
    statements: list[dict[str, Any]],
    frontier: dict[str, Any],
    parsed_goal: dict[str, Any],
) -> dict[str, Any]:
    """Build a conservative top-level edit script for the current programs."""
    left = _top_level(statements, "left")
    right = _top_level(statements, "right")
    max_len = max(len(left), len(right))
    script: list[dict[str, Any]] = []
    used_left: set[str] = set()
    used_right: set[str] = set()

    for index in range(max_len):
        lstmt = left[index] if index < len(left) else None
        rstmt = right[index] if index < len(right) else None
        step = _positional_diff_step(index + 1, lstmt, rstmt)
        if step:
            script.append(step)
            if step.get("left_statement_id"):
                used_left.add(str(step["left_statement_id"]))
            if step.get("right_statement_id"):
                used_right.add(str(step["right_statement_id"]))

    shifted = _shifted_call_pairs(left, right, used_left, used_right)
    script.extend(shifted)

    blockers = _frontier_blocker_steps(frontier)
    script.extend(blockers)

    script = _dedupe_steps(script)
    action_plans = _program_action_plans(statements, script, parsed_goal)
    edit_script_v2 = _program_edit_script_v2(
        statements,
        script,
        action_plans,
        parsed_goal,
    )
    return {
        "edit_script": script,
        "action_plans": action_plans,
        "next_action_plan": action_plans[0] if action_plans else {},
        "edit_script_v2": edit_script_v2,
        "summary": {
            "aligned_call_pair_count": len([
                step for step in script
                if step.get("kind") == "aligned_call_pair"
            ]),
            "shifted_call_pair_count": len([
                step for step in script
                if step.get("kind") == "shifted_call_pair"
            ]),
            "frontier_blocker_count": len([
                step for step in script
                if step.get("kind") == "frontier_blocker"
            ]),
            "action_plan_count": len(action_plans),
            "edit_script_v2_slice_count": len(edit_script_v2["slices"]),
        },
    }


def _program_action_plans(
    statements: list[dict[str, Any]],
    script: list[dict[str, Any]],
    parsed_goal: dict[str, Any],
) -> list[dict[str, Any]]:
    """Lift raw edit-script facts into a tactic-family proof plan.

    The plan is still conservative and mostly non-runnable.  Its job is to
    make phase ordering explicit: expose the frontier if needed, align or open
    one wrapper if needed, then use a named call lemma.  The lemma name is
    filled in later by ``annotate_callable_lemma_handles``.
    """
    by_id = {
        str(stmt.get("statement_id") or ""): stmt
        for stmt in statements
        if isinstance(stmt, dict)
    }
    plans: list[dict[str, Any]] = []
    for step in script:
        if not isinstance(step, dict):
            continue
        kind = str(step.get("kind") or "")
        if kind not in {
            "aligned_call_pair",
            "different_call_pair",
            "shifted_call_pair",
            "frontier_blocker",
        }:
            continue
        plan = _action_plan_for_step(step, by_id)
        if plan:
            plans.append(plan)
    asym = _asymmetric_seq_plan(statements, script, parsed_goal)
    if asym:
        plans.append(asym)
    return sorted(
        plans,
        key=lambda item: (
            int(item.get("rank") or 9999),
            str(item.get("id") or ""),
        ),
    )


def _asymmetric_seq_plan(
    statements: list[dict[str, Any]],
    script: list[dict[str, Any]],
    parsed_goal: dict[str, Any],
) -> dict[str, Any] | None:
    left = _top_level(statements, "left")
    right = _top_level(statements, "right")
    if not left or not right or len(left) == len(right):
        return None
    matched_steps = [
        step for step in script
        if step.get("kind") in {
            "aligned_call_pair",
            "different_call_pair",
            "shifted_call_pair",
            "same_kind",
        }
        and step.get("left_statement_id")
        and step.get("right_statement_id")
    ]
    if not matched_steps:
        return None
    invariant, invariant_sources = _asymmetric_seq_invariant(
        left,
        right,
        matched_steps,
        parsed_goal,
    )
    if not invariant:
        return None
    left_n = len(left)
    right_m = len(right)
    target_ids = _dedupe_strings([
        str(step.get(key) or "")
        for step in matched_steps
        for key in ("left_call_site_id", "right_call_site_id")
        if str(step.get(key) or "")
    ])
    first_call = next(
        (
            step for step in matched_steps
            if step.get("left_call_site_id") or step.get("right_call_site_id")
        ),
        {},
    )
    return {
        "id": "plan.asymmetric_seq_prefix",
        "source_edit_id": "asymmetric_seq_prefix",
        "kind": "asymmetric_seq_exposure_plan",
        "rank": 90000 + max(left_n, right_m),
        "confidence": "low",
        "proof_intent": "full_prefix_post_normalization",
        "procedure_tail": str(first_call.get("procedure_tail") or ""),
        "target_call_site_ids": target_ids,
        "left_procedure": str(first_call.get("left_procedure") or ""),
        "right_procedure": str(first_call.get("right_procedure") or ""),
        "left_statement_count": left_n,
        "right_statement_count": right_m,
        "synthesized_invariant": invariant,
        "invariant_sources": invariant_sources,
        "phase_order": [
            {
                "kind": "weaken_or_normalize_post",
                "tactic_family": "procedure_transform",
                "action_type": "strategy_hint",
                "tactic_hint": "conseq />.",
                "reason": (
                    "normalize the pRHL postcondition before the asymmetric "
                    "sequence split when the current post is too strong"
                ),
            },
            {
                "kind": "expose_asymmetric_prefix",
                "side": "both",
                "tactic_family": "procedure_transform",
                "action_type": "strategy_hint",
                "tactic_hint": (
                    f"seq {left_n} {right_m} : "
                    "<full-prefix invariant preserving postcondition/resources>."
                ),
                "proof_intent": "full_prefix_post_normalization",
                "requires_instantiation": True,
                "left_statement_count": left_n,
                "right_statement_count": right_m,
                "synthesized_invariant": invariant,
                "invariant_skeleton": invariant,
                "invariant_sources": invariant_sources,
                "reason": (
                    "the programs have unequal top-level statement counts; "
                    "this is a coarse full-prefix/postcondition split, not a "
                    "call-site exposure. Prefer a call-pair frontier split "
                    "when a live call lemma is available"
                ),
            },
        ],
        "why": (
            f"ProgramIR sees an asymmetric pRHL prefix "
            f"({left_n} left statements vs {right_m} right statements). "
            "This plan preserves the suffix/post-normalization option but is "
            "secondary to exact call-site frontier exposure."
        ),
    }


def _action_plan_for_step(
    step: dict[str, Any],
    by_id: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    kind = str(step.get("kind") or "")
    phase_order: list[dict[str, Any]] = []
    target_call_site_ids = [
        str(step.get(key) or "")
        for key in ("left_call_site_id", "right_call_site_id")
        if str(step.get(key) or "")
    ]

    if kind == "frontier_blocker":
        side = str(step.get("side") or "")
        phase_order.append(_expose_frontier_action(
            side=side,
            reason=(
                "the current frontier statement is not a call, so call lemmas "
                "behind it are not consumable yet"
            ),
        ))
        return {
            "id": f"plan.{step.get('id')}",
            "source_edit_id": str(step.get("id") or ""),
            "kind": "frontier_exposure_plan",
            "rank": int(step.get("order") or 9999) * 10 + 5,
            "confidence": str(step.get("confidence") or "medium"),
            "target_call_site_ids": target_call_site_ids,
            "phase_order": phase_order,
            "why": "Expose the last-call frontier before attempting call-level lemmas.",
        }

    left_stmt = by_id.get(str(step.get("left_statement_id") or ""))
    right_stmt = by_id.get(str(step.get("right_statement_id") or ""))
    if not left_stmt and str(step.get("side") or "") == "left":
        left_stmt = by_id.get(str(step.get("statement_id") or ""))
    if not right_stmt and str(step.get("side") or "") == "right":
        right_stmt = by_id.get(str(step.get("statement_id") or ""))
    if (
        left_stmt and right_stmt
        and left_stmt.get("is_call_site")
        and right_stmt.get("is_call_site")
        and (
            not left_stmt.get("is_frontier_call")
            or not right_stmt.get("is_frontier_call")
        )
    ):
        phase_order.append(_expose_pair_frontier_action(
            left_stmt=left_stmt,
            right_stmt=right_stmt,
            reason=(
                "the matching call pair exists before the last-call frontier; "
                "split the sequence at that pair before using a call lemma"
            ),
        ))
    else:
        for side, stmt in (("left", left_stmt), ("right", right_stmt)):
            if (
                stmt
                and stmt.get("is_call_site")
                and not stmt.get("is_frontier_call")
            ):
                phase_order.append(_expose_frontier_action(
                    side=side,
                    statement=stmt,
                    reason=(
                        "the matching call exists but is not EasyCrypt's "
                        "last-call frontier on this side"
                    ),
                ))

    if kind == "shifted_call_pair":
        phase_order.append({
            "kind": "align_programs",
            "tactic_family": "procedure_transform",
            "action_type": "strategy_hint",
            "tactic_hint": "swap/seq to align the shifted call pair",
            "reason": (
                "the same call shape appears on both sides, but at different "
                "top-level positions"
            ),
        })
    elif kind == "different_call_pair":
        phase_order.append({
            "kind": "open_one_wrapper",
            "tactic_family": "targeted_inline",
            "action_type": "strategy_hint",
            "tactic_hint": _targeted_inline_hint(step),
            "reason": (
                "both sides have calls at this position, but their procedure "
                "tails differ; open one wrapper before matching a local lemma"
            ),
        })

    if kind in {"aligned_call_pair", "shifted_call_pair", "different_call_pair"}:
        phase_order.append({
            "kind": "call_named_equiv",
            "tactic_family": "call_named_equiv",
            "action_type": "tactic_candidate_if_frontier_ready",
            "tactic_template": "call <matching lemma>.",
            "reason": (
                "after exposure/alignment, consume the matching call-site "
                "handle with a named equiv lemma"
            ),
        })

    if not phase_order:
        return None
    ready = bool(step.get("is_frontier_ready"))
    rank_base = _call_pair_frontier_distance_rank(left_stmt, right_stmt)
    if rank_base is None:
        rank_base = int(step.get("order") or 9999) * 10
    return {
        "id": f"plan.{step.get('id')}",
        "source_edit_id": str(step.get("id") or ""),
        "kind": (
            "frontier_ready_call_plan"
            if ready else
            "call_site_exposure_plan"
        ),
        "rank": rank_base + (0 if ready else 4),
        "confidence": str(step.get("confidence") or "medium"),
        "procedure_tail": str(step.get("procedure_tail") or ""),
        "target_call_site_ids": target_call_site_ids,
        "left_procedure": str(step.get("left_procedure") or ""),
        "right_procedure": str(step.get("right_procedure") or ""),
        "phase_order": phase_order,
        "why": str(step.get("why") or ""),
    }


def _call_pair_frontier_distance_rank(
    left_stmt: dict[str, Any] | None,
    right_stmt: dict[str, Any] | None,
) -> int | None:
    """Rank paired calls by how close they are to the current call frontier.

    EasyCrypt call tactics consume the last-call frontier of the current
    slice.  When several call pairs are live, the later/nearer-to-frontier pair
    is usually the actionable split; earlier pairs remain inside the prefix.
    """
    if not left_stmt or not right_stmt:
        return None
    if not left_stmt.get("is_call_site") or not right_stmt.get("is_call_site"):
        return None
    left_suffix = _int_or_default(left_stmt.get("suffix_statement_count"), 9999)
    right_suffix = _int_or_default(right_stmt.get("suffix_statement_count"), 9999)
    distance = max(left_suffix, right_suffix)
    order = max(
        _int_or_default(left_stmt.get("order"), 0),
        _int_or_default(right_stmt.get("order"), 0),
    )
    # Distance dominates.  For equal distances, prefer the syntactically later
    # pair so the exposed slice is closer to EC's last-call frontier.
    return distance * 100 + max(0, 99 - min(order, 99))


def _asymmetric_seq_invariant(
    left: list[dict[str, Any]],
    right: list[dict[str, Any]],
    matched_steps: list[dict[str, Any]],
    parsed_goal: dict[str, Any],
) -> tuple[str, list[str]]:
    by_id = {
        str(stmt.get("statement_id") or ""): stmt
        for stmt in [*left, *right]
    }
    eq_vars: set[str] = set()
    sources: list[str] = []
    for step in matched_steps:
        left_stmt = by_id.get(str(step.get("left_statement_id") or ""))
        right_stmt = by_id.get(str(step.get("right_statement_id") or ""))
        if not left_stmt or not right_stmt:
            continue
        l_writes = {
            name for name in _strings(left_stmt.get("vars_written"))
            if _is_emit_safe_var(name)
        }
        r_writes = {
            name for name in _strings(right_stmt.get("vars_written"))
            if _is_emit_safe_var(name)
        }
        if not l_writes or not r_writes:
            continue
        eq_vars.update(l_writes & r_writes)
        sources.append(str(step.get("id") or "matched_statement"))

    pieces = _condition_conjuncts(str(parsed_goal.get("post") or ""))
    if eq_vars:
        pieces.append("={" + ", ".join(sorted(eq_vars)) + "}")
    dataflow = build_invariant_skeleton(
        {
            **_dict(parsed_goal),
            "left_statements": left,
            "right_statements": right,
        },
        "pRHL",
    )
    for conjunct in _list(_dict(dataflow).get("conjuncts")):
        if not isinstance(conjunct, dict):
            continue
        text = str(conjunct.get("text") or "").strip()
        if text:
            pieces.append(text)
            source = str(conjunct.get("source") or "dataflow_invariant")
            if source:
                sources.append(source)
    pieces.extend(_condition_conjuncts(str(parsed_goal.get("pre") or "")))
    clean = _dedupe_condition_pieces([
        piece for piece in (_normalize_condition_piece(item) for item in pieces)
        if piece and not _condition_piece_is_too_broad(piece)
    ])
    return (" /\\ ".join(clean), _dedupe_strings(sources))


def _expose_frontier_action(
    *,
    side: str,
    reason: str,
    statement: dict[str, Any] | None = None,
) -> dict[str, Any]:
    stmt = _dict(statement)
    tactic_hint = _single_side_exposure_hint(side, stmt)
    return {
        "kind": "expose_last_call_frontier",
        "side": side,
        "tactic_family": "procedure_transform",
        "action_type": "strategy_hint",
        "tactic_hint": tactic_hint,
        "statement_path": str(stmt.get("statement_path") or ""),
        "statement_order": _int_or_default(stmt.get("order"), 0),
        "suffix_statement_count": _int_or_default(
            stmt.get("suffix_statement_count"), 0
        ),
        "call_site_id": str(stmt.get("call_site_id") or ""),
        "procedure": str(stmt.get("procedure") or ""),
        "reason": reason,
    }


def _expose_pair_frontier_action(
    *,
    left_stmt: dict[str, Any],
    right_stmt: dict[str, Any],
    reason: str,
) -> dict[str, Any]:
    left_order = _int_or_default(left_stmt.get("order"), 0)
    right_order = _int_or_default(right_stmt.get("order"), 0)
    return {
        "kind": "expose_call_pair_frontier",
        "side": "both",
        "tactic_family": "procedure_transform",
        "action_type": "strategy_hint",
        "tactic_hint": (
            f"seq {left_order} {right_order} : "
            "<invariant preserving the call lemma postcondition>."
        ),
        "left_statement_path": str(left_stmt.get("statement_path") or ""),
        "right_statement_path": str(right_stmt.get("statement_path") or ""),
        "left_statement_order": left_order,
        "right_statement_order": right_order,
        "left_suffix_statement_count": _int_or_default(
            left_stmt.get("suffix_statement_count"), 0
        ),
        "right_suffix_statement_count": _int_or_default(
            right_stmt.get("suffix_statement_count"), 0
        ),
        "left_call_site_id": str(left_stmt.get("call_site_id") or ""),
        "right_call_site_id": str(right_stmt.get("call_site_id") or ""),
        "left_procedure": str(left_stmt.get("procedure") or ""),
        "right_procedure": str(right_stmt.get("procedure") or ""),
        "reason": reason,
    }


def _single_side_exposure_hint(side: str, stmt: dict[str, Any]) -> str:
    order = _int_or_default(stmt.get("order"), 0)
    suffix = _int_or_default(stmt.get("suffix_statement_count"), 0)
    if order > 0:
        other = 0
        return (
            f"seq {order} {other} : "
            "<invariant preserving the call lemma postcondition>."
            if side == "left" else
            f"seq {other} {order} : "
            "<invariant preserving the call lemma postcondition>."
        )
    if suffix > 0:
        return "wp. / seq <prefix> : <invariant preserving the call lemma postcondition>."
    return "wp. / seq <suffix> according to the suffix shape"


def _targeted_inline_hint(step: dict[str, Any]) -> str:
    left = str(step.get("left_procedure") or "")
    right = str(step.get("right_procedure") or "")
    proc = _outer_wrapper_candidate(left, right)
    return (
        f"inline {proc}."
        if proc else
        "inline <mismatching wrapper only>."
    )


def _outer_wrapper_candidate(left: str, right: str) -> str:
    left_tail = _proc_tail(_normalize_proc(left))
    right_tail = _proc_tail(_normalize_proc(right))
    if left_tail and right_tail and left_tail != right_tail:
        return min(
            [item for item in (left, right) if item],
            key=lambda item: (
                _procedure_depth(item),
                len(_normalize_proc(item)),
            ),
        )
    if left_tail and right_tail:
        if left.endswith(left_tail) and not right.endswith(left_tail):
            return right
        if right.endswith(right_tail) and not left.endswith(right_tail):
            return left
    return left or right


def _procedure_depth(procedure: str) -> int:
    normalized = _normalize_proc(procedure)
    return len([part for part in normalized.split(".") if part])


def _positional_diff_step(
    index: int,
    left: dict[str, Any] | None,
    right: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if left is None and right is None:
        return None
    if left is None or right is None:
        stmt = right if left is None else left
        side = "right" if left is None else "left"
        return {
            "id": f"insert_delete.{index}.{side}",
            "kind": "insert_delete_prefix",
            "order": index,
            "side": side,
            "statement_id": str(_dict(stmt).get("statement_id") or ""),
            "statement_kind": str(_dict(stmt).get("kind") or ""),
            "suggested_action_family": "seq_or_wp",
            "confidence": "medium",
            "why": "Only one side has a top-level statement at this position.",
        }

    left_kind = str(left.get("kind") or "")
    right_kind = str(right.get("kind") or "")
    base = {
        "order": index,
        "left_statement_id": str(left.get("statement_id") or ""),
        "right_statement_id": str(right.get("statement_id") or ""),
        "left_kind": left_kind,
        "right_kind": right_kind,
        "left_statement_path": str(left.get("statement_path") or ""),
        "right_statement_path": str(right.get("statement_path") or ""),
    }
    if left.get("is_call_site") and right.get("is_call_site"):
        left_tail = _proc_tail(_normalize_proc(str(left.get("procedure") or "")))
        right_tail = _proc_tail(_normalize_proc(str(right.get("procedure") or "")))
        same_tail = bool(left_tail and right_tail and left_tail == right_tail)
        return {
            **base,
            "id": f"call_pair.{index}",
            "kind": "aligned_call_pair" if same_tail else "different_call_pair",
            "left_call_site_id": str(left.get("call_site_id") or ""),
            "right_call_site_id": str(right.get("call_site_id") or ""),
            "left_procedure": str(left.get("procedure") or ""),
            "right_procedure": str(right.get("procedure") or ""),
            "procedure_tail": left_tail if same_tail else "",
            "suggested_action_family": (
                "call_named_equiv" if same_tail else "targeted_inline_or_seq"
            ),
            "is_frontier_ready": bool(
                left.get("is_frontier_call") and right.get("is_frontier_call")
            ),
            "confidence": "high" if same_tail else "medium",
            "why": (
                "Both sides have a call with the same procedure tail at this position."
                if same_tail else
                "Both sides have calls here, but their procedure tails differ."
            ),
        }
    if left_kind == right_kind:
        return {
            **base,
            "id": f"same_kind.{index}",
            "kind": "same_kind",
            "suggested_action_family": "procedure_transform",
            "confidence": "medium",
            "why": "Both sides have the same top-level statement kind.",
        }
    return {
        **base,
        "id": f"kind_mismatch.{index}",
        "kind": "kind_mismatch",
        "suggested_action_family": "seq_or_targeted_inline",
        "confidence": "medium",
        "why": "Top-level statement kinds differ at this position.",
    }


def _shifted_call_pairs(
    left: list[dict[str, Any]],
    right: list[dict[str, Any]],
    used_left: set[str],
    used_right: set[str],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for lstmt in left:
        if not lstmt.get("is_call_site"):
            continue
        left_id = str(lstmt.get("statement_id") or "")
        left_tail = _proc_tail(_normalize_proc(str(lstmt.get("procedure") or "")))
        if not left_tail:
            continue
        for rstmt in right:
            if not rstmt.get("is_call_site"):
                continue
            right_id = str(rstmt.get("statement_id") or "")
            if left_id in used_left and right_id in used_right:
                continue
            right_tail = _proc_tail(_normalize_proc(str(rstmt.get("procedure") or "")))
            if left_tail != right_tail:
                continue
            if int(lstmt.get("order") or 0) == int(rstmt.get("order") or 0):
                continue
            out.append({
                "id": f"shifted_call_pair.{left_id}.{right_id}",
                "kind": "shifted_call_pair",
                "order": min(
                    int(lstmt.get("order") or 9999),
                    int(rstmt.get("order") or 9999),
                ),
                "left_statement_id": left_id,
                "right_statement_id": right_id,
                "left_call_site_id": str(lstmt.get("call_site_id") or ""),
                "right_call_site_id": str(rstmt.get("call_site_id") or ""),
                "left_procedure": str(lstmt.get("procedure") or ""),
                "right_procedure": str(rstmt.get("procedure") or ""),
                "procedure_tail": left_tail,
                "suggested_action_family": "swap_or_seq",
                "confidence": "medium",
                "why": (
                    "Both sides contain the same call shape at different "
                    "top-level positions."
                ),
            })
            break
    return out


def _frontier_blocker_steps(frontier: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    blockers = _dict(frontier.get("frontier_blockers"))
    for side, blocker in blockers.items():
        item = _dict(blocker)
        out.append({
            "id": f"frontier_blocker.{side}",
            "kind": "frontier_blocker",
            "side": str(side),
            "statement_id": str(item.get("statement_id") or ""),
            "statement_kind": str(item.get("kind") or ""),
            "suggested_action_family": "wp_or_seq",
            "confidence": "medium",
            "why": (
                "The last top-level statement on this side is not a call; "
                "a live call lemma may need wp/seq before it becomes callable."
            ),
        })
    return out


def _dedupe_steps(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for step in sorted(
        steps,
        key=lambda item: (
            int(item.get("order") or 9999),
            str(item.get("id") or ""),
        ),
    ):
        step_id = str(step.get("id") or "")
        if not step_id or step_id in seen:
            continue
        seen.add(step_id)
        out.append(step)
    return out


def _diff_index(program_ir: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    diff = _dict(_dict(program_ir).get("program_diff"))
    for step in _list(diff.get("edit_script")):
        if not isinstance(step, dict):
            continue
        for key in ("left_call_site_id", "right_call_site_id"):
            call_id = str(step.get(key) or "")
            if call_id:
                out.setdefault(call_id, []).append(step)
    return out


def _same_concrete_call_pair_index(
    call_sites: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    by_side = {
        side: sorted(
            [
                site for site in call_sites
                if str(_dict(site).get("side") or "") == side
            ],
            key=lambda item: int(_dict(item).get("order") or 0),
        )
        for side in ("left", "right")
    }
    out: dict[str, list[dict[str, Any]]] = {}
    for left in by_side["left"]:
        for right in by_side["right"]:
            if int(left.get("order") or 0) != int(right.get("order") or 0):
                continue
            lproc = _normalize_proc(str(left.get("procedure") or ""))
            rproc = _normalize_proc(str(right.get("procedure") or ""))
            if not lproc or lproc != rproc:
                continue
            pair = {
                "kind": "same_concrete_call_pair",
                "left_call_site_id": str(left.get("call_site_id") or ""),
                "right_call_site_id": str(right.get("call_site_id") or ""),
                "procedure": str(left.get("procedure") or ""),
                "statement_order": int(left.get("order") or 0),
                "is_frontier_ready": bool(
                    left.get("is_frontier_call") and right.get("is_frontier_call")
                ),
                "orientation": (
                    "same concrete procedure call appears on both sides. "
                    "This is a local synchronized region; a cross-procedure "
                    "named equiv handle is not automatically the next action."
                ),
            }
            for call_id in (pair["left_call_site_id"], pair["right_call_site_id"]):
                if call_id:
                    out.setdefault(call_id, []).append(pair)
    return out


def _handle_same_concrete_pairs(
    linked: list[dict[str, Any]],
    same_concrete_index: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for site in linked:
        call_id = str(site.get("call_site_id") or "")
        for pair in same_concrete_index.get(call_id, []):
            key = (
                str(pair.get("left_call_site_id") or ""),
                str(pair.get("right_call_site_id") or ""),
            )
            if key in seen:
                continue
            seen.add(key)
            out.append(dict(pair))
    return sorted(
        out,
        key=lambda item: (
            int(item.get("statement_order") or 9999),
            str(item.get("procedure") or ""),
        ),
    )


def _action_plan_index(program_ir: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    diff = _dict(_dict(program_ir).get("program_diff"))
    for plan in _list(diff.get("action_plans")):
        if not isinstance(plan, dict):
            continue
        for call_id in _list(plan.get("target_call_site_ids")):
            key = str(call_id or "")
            if key:
                out.setdefault(key, []).append(plan)
    return out


def _edit_script_v2_index(program_ir: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    diff = _dict(_dict(program_ir).get("program_diff"))
    edit_v2 = _dict(diff.get("edit_script_v2"))
    for item in _list(edit_v2.get("slices")):
        if not isinstance(item, dict):
            continue
        for call_id in _list(item.get("target_call_site_ids")):
            key = str(call_id or "")
            if key:
                out.setdefault(key, []).append(item)
    return out


def _handle_diff_steps(
    linked: list[dict[str, Any]],
    diff_index: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for site in linked:
        call_id = str(site.get("call_site_id") or "")
        for step in diff_index.get(call_id, []):
            step_id = str(step.get("id") or "")
            if not step_id or step_id in seen:
                continue
            seen.add(step_id)
            out.append({
                "id": step_id,
                "kind": str(step.get("kind") or ""),
                "order": int(step.get("order") or 9999),
                "suggested_action_family": str(
                    step.get("suggested_action_family") or ""
                ),
            })
    return sorted(out, key=lambda item: (item["order"], item["id"]))


def _handle_edit_script_v2_slices(
    linked: list[dict[str, Any]],
    slice_index: dict[str, list[dict[str, Any]]],
    handle: dict[str, Any],
) -> list[dict[str, Any]]:
    lemma = str(handle.get("lemma") or "")
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for site in linked:
        call_id = str(site.get("call_site_id") or "")
        for item in slice_index.get(call_id, []):
            slice_id = str(item.get("id") or "")
            if not slice_id or slice_id in seen:
                continue
            seen.add(slice_id)
            out.append(_specialize_edit_slice_v2(item, lemma=lemma))
    return sorted(
        out,
        key=lambda item: (
            int(item.get("rank") or 9999),
            str(item.get("id") or ""),
        ),
    )


def _specialize_edit_slice_v2(item: dict[str, Any], *, lemma: str) -> dict[str, Any]:
    copied = {
        key: value
        for key, value in dict(item).items()
        if key != "phase_order"
    }
    phase_order: list[dict[str, Any]] = []
    for action in _list(item.get("phase_order")):
        if not isinstance(action, dict):
            continue
        action_copy = dict(action)
        if lemma and action_copy.get("tactic_template") == "call <matching lemma>.":
            action_copy["tactic_template"] = f"call {lemma}."
            action_copy["lemma"] = lemma
        phase_order.append(action_copy)
    copied["phase_order"] = phase_order
    copied["expected_next"] = _expected_next_from_phase_order(phase_order)
    return copied


def _handle_action_plans(
    linked: list[dict[str, Any]],
    plan_index: dict[str, list[dict[str, Any]]],
    handle: dict[str, Any],
) -> list[dict[str, Any]]:
    lemma = str(handle.get("lemma") or "")
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for site in linked:
        call_id = str(site.get("call_site_id") or "")
        for plan in plan_index.get(call_id, []):
            plan_id = str(plan.get("id") or "")
            if not plan_id or plan_id in seen:
                continue
            seen.add(plan_id)
            out.append(_specialize_action_plan(plan, lemma=lemma))
    if not out:
        for site in linked:
            if not site.get("is_call_site") or site.get("is_frontier_call"):
                continue
            plan = _fallback_handle_exposure_plan(site, lemma=lemma)
            if plan:
                out.append(plan)
                break
    return sorted(
        out,
        key=lambda item: (
            int(item.get("rank") or 9999),
            str(item.get("id") or ""),
        ),
    )


def _specialize_action_plan(plan: dict[str, Any], *, lemma: str) -> dict[str, Any]:
    item = {
        key: value
        for key, value in dict(plan).items()
        if key != "phase_order"
    }
    phase_order: list[dict[str, Any]] = []
    for action in _list(plan.get("phase_order")):
        if not isinstance(action, dict):
            continue
        copied = dict(action)
        if lemma and copied.get("tactic_template") == "call <matching lemma>.":
            copied["tactic_template"] = f"call {lemma}."
            copied["lemma"] = lemma
        phase_order.append(copied)
    item["phase_order"] = phase_order
    return item


def _fallback_handle_exposure_plan(
    site: dict[str, Any],
    *,
    lemma: str,
) -> dict[str, Any]:
    call_id = str(site.get("call_site_id") or "")
    action = _expose_frontier_action(
        side=str(site.get("side") or ""),
        statement=site,
        reason=(
            "the matching call is live but no paired edit-script step was "
            "available; expose this side's call frontier before calling the "
            "lemma"
        ),
    )
    return {
        "id": f"plan.fallback_expose.{call_id or _safe_id(lemma)}",
        "source_edit_id": "",
        "kind": "call_site_exposure_plan",
        "rank": int(site.get("order") or 9999) * 10 + 6,
        "confidence": "medium",
        "procedure_tail": _proc_tail(_normalize_proc(str(site.get("procedure") or ""))),
        "target_call_site_ids": [call_id] if call_id else [],
        "left_procedure": (
            str(site.get("procedure") or "")
            if str(site.get("side") or "") == "left" else ""
        ),
        "right_procedure": (
            str(site.get("procedure") or "")
            if str(site.get("side") or "") == "right" else ""
        ),
        "phase_order": [
            action,
            {
                "kind": "call_named_equiv",
                "tactic_family": "call_named_equiv",
                "action_type": "tactic_candidate_if_frontier_ready",
                "tactic_template": f"call {lemma}." if lemma else "call <matching lemma>.",
                "lemma": lemma,
                "reason": (
                    "after exposure, consume the matching call-site handle "
                    "with the named equiv lemma"
                ),
            },
        ],
        "why": "Expose the live call before applying its named equiv lemma.",
    }


def _repair_hint_from_action_plans(
    plans: list[dict[str, Any]],
    *,
    fallback: str,
) -> str:
    if not plans:
        return fallback
    for action in _list(plans[0].get("phase_order")):
        if not isinstance(action, dict):
            continue
        kind = str(action.get("kind") or "")
        if kind == "expose_call_pair_frontier":
            hint = str(action.get("tactic_hint") or "seq <l> <r> : <invariant>.")
            return (
                f"Use `{hint}` to expose the paired call frontier, then call "
                "the named equiv lemma."
            )
        if kind == "expose_asymmetric_prefix":
            hint = str(action.get("tactic_hint") or "seq <n> <m> : <invariant>.")
            return (
                f"`{hint}` is a full-prefix/post-normalization split, not "
                "the direct call-site exposure. Prefer an exact call-pair "
                "frontier plan when one is available; use this only after "
                "validating the invariant skeleton."
            )
        if kind == "expose_last_call_frontier":
            proc = str(action.get("procedure") or "the matching call")
            side = str(action.get("side") or "one side")
            return (
                f"Expose `{proc}` on {side} with wp/seq before calling the "
                "named equiv lemma."
            )
        if kind == "align_programs":
            return "Align the shifted call pair with swap/seq before calling the named equiv lemma."
        if kind == "open_one_wrapper":
            hint = str(action.get("tactic_hint") or "targeted inline")
            return f"Use {hint}, then re-run ProofContextView before calling the lemma."
    return fallback


def _program_ast(statements: list[dict[str, Any]]) -> dict[str, Any]:
    """Return a shallow AST/block view keyed by EasyCrypt statement paths.

    EasyCrypt's goal printer exposes statement positions rather than a full
    typed AST.  This view keeps those paths stable and explicit so downstream
    passes can talk about blocks, parents, and children without reparsing raw
    two-column text.
    """
    blocks: list[dict[str, Any]] = []
    by_side_path = {
        (str(stmt.get("side") or ""), str(stmt.get("statement_path") or "")): stmt
        for stmt in statements
        if isinstance(stmt, dict)
    }
    for stmt in statements:
        if not isinstance(stmt, dict):
            continue
        side = str(stmt.get("side") or "")
        path = str(stmt.get("statement_path") or "")
        parent = _parent_path(path)
        child_paths = [
            str(other.get("statement_path") or "")
            for other in statements
            if (
                isinstance(other, dict)
                and str(other.get("side") or "") == side
                and _parent_path(str(other.get("statement_path") or "")) == path
            )
        ]
        blocks.append({
            "id": f"{side}:{path or stmt.get('order')}",
            "side": side,
            "statement_path": path,
            "parent_path": parent,
            "parent_statement_id": str(
                _dict(by_side_path.get((side, parent))).get("statement_id") or ""
            ),
            "child_paths": child_paths,
            "depth": int(stmt.get("depth") or 1),
            "kind": str(stmt.get("kind") or ""),
            "procedure": str(stmt.get("procedure") or ""),
            "call_site_id": str(stmt.get("call_site_id") or ""),
            "vars_written": _strings(stmt.get("vars_written")),
            "vars_read": _strings(stmt.get("vars_read")),
            "frontier_role": str(stmt.get("frontier_role") or ""),
        })
    return {
        "schema_version": 1,
        "kind": "easycrypt_program_ast_shallow",
        "blocks": sorted(
            blocks,
            key=lambda item: (
                str(item.get("side") or ""),
                _path_sort_key(str(item.get("statement_path") or "")),
            ),
        ),
        "by_side": {
            side: [
                block for block in blocks
                if str(block.get("side") or "") == side
                and int(block.get("depth") or 1) == 1
            ]
            for side in ("left", "right")
        },
    }


def _program_edit_script_v2(
    statements: list[dict[str, Any]],
    script: list[dict[str, Any]],
    action_plans: list[dict[str, Any]],
    parsed_goal: dict[str, Any],
) -> dict[str, Any]:
    """Normalize edit/action plans into proof-oriented program slices."""
    by_id = {
        str(stmt.get("statement_id") or ""): stmt
        for stmt in statements
        if isinstance(stmt, dict)
    }
    by_plan_source = {
        str(plan.get("source_edit_id") or ""): plan
        for plan in action_plans
        if isinstance(plan, dict)
    }
    slices: list[dict[str, Any]] = []
    seen_sources: set[str] = set()
    for step in script:
        if not isinstance(step, dict):
            continue
        kind = str(step.get("kind") or "")
        if kind not in {
            "aligned_call_pair",
            "different_call_pair",
            "shifted_call_pair",
            "insert_delete_prefix",
            "frontier_blocker",
        }:
            continue
        plan = _dict(by_plan_source.get(str(step.get("id") or "")))
        slice_item = _edit_slice_from_step(step, plan, by_id, parsed_goal)
        if slice_item:
            seen_sources.add(str(slice_item.get("source_edit_id") or ""))
            slices.append(slice_item)
    for plan in action_plans:
        if not isinstance(plan, dict):
            continue
        source = str(plan.get("source_edit_id") or "")
        if not source or source in seen_sources:
            continue
        slice_item = _edit_slice_from_plan(plan, parsed_goal)
        if slice_item:
            slices.append(slice_item)
    slices.sort(key=lambda item: (
        int(item.get("rank") or 9999),
        str(item.get("id") or ""),
    ))
    return {
        "schema_version": 2,
        "kind": "easycrypt_program_edit_script",
        "slices": slices,
        "next_slice": slices[0] if slices else {},
        "summary": {
            "slice_count": len(slices),
            "wrapper_open_slice_count": len([
                item for item in slices
                if item.get("requires_targeted_inline")
            ]),
            "seq_cut_slice_count": len([
                item for item in slices
                if any(
                    str(action.get("kind") or "").startswith("expose_")
                    for action in _list(item.get("phase_order"))
                    if isinstance(action, dict)
                )
            ]),
        },
    }


def _edit_slice_from_step(
    step: dict[str, Any],
    plan: dict[str, Any],
    by_id: dict[str, dict[str, Any]],
    parsed_goal: dict[str, Any],
) -> dict[str, Any] | None:
    left_stmt = by_id.get(str(step.get("left_statement_id") or ""))
    right_stmt = by_id.get(str(step.get("right_statement_id") or ""))
    target_call_site_ids = _dedupe_strings([
        str(step.get(key) or "")
        for key in ("left_call_site_id", "right_call_site_id")
        if str(step.get(key) or "")
    ] + [
        str(item) for item in _list(plan.get("target_call_site_ids"))
        if str(item)
    ])
    phase_order = _edit_slice_phase_order(step, plan, left_stmt, right_stmt)
    invariant = _edit_slice_invariant(plan, parsed_goal)
    return {
        "id": f"slice.{step.get('id')}",
        "source_edit_id": str(step.get("id") or ""),
        "kind": _edit_slice_kind(step),
        "rank": int(step.get("order") or plan.get("rank") or 9999),
        "confidence": str(step.get("confidence") or plan.get("confidence") or "medium"),
        "target_call_site_ids": target_call_site_ids,
        "statement_pair": {
            "left": _statement_ref(left_stmt),
            "right": _statement_ref(right_stmt),
        },
        "left_statement_count": int(plan.get("left_statement_count") or 0),
        "right_statement_count": int(plan.get("right_statement_count") or 0),
        "call_alignment": {
            "procedure_tail": str(step.get("procedure_tail") or plan.get("procedure_tail") or ""),
            "left_procedure": str(step.get("left_procedure") or plan.get("left_procedure") or ""),
            "right_procedure": str(step.get("right_procedure") or plan.get("right_procedure") or ""),
            "is_frontier_ready": bool(step.get("is_frontier_ready")),
        },
        "phase_order": phase_order,
        "invariant_skeleton": invariant,
        "requires_targeted_inline": any(
            str(action.get("kind") or "") == "open_one_wrapper"
            for action in phase_order
            if isinstance(action, dict)
        ),
        "expected_next": _expected_next_from_phase_order(phase_order),
        "why": str(plan.get("why") or step.get("why") or ""),
    }


def _edit_slice_from_plan(
    plan: dict[str, Any],
    parsed_goal: dict[str, Any],
) -> dict[str, Any] | None:
    phase_order = [
        _compact_phase_action(action)
        for action in _list(plan.get("phase_order"))
        if isinstance(action, dict)
    ]
    if not phase_order:
        return None
    invariant = _edit_slice_invariant(plan, parsed_goal)
    return {
        "id": f"slice.{plan.get('source_edit_id') or plan.get('id')}",
        "source_edit_id": str(plan.get("source_edit_id") or ""),
        "kind": _edit_slice_kind_from_plan(plan),
        "rank": int(plan.get("rank") or 9999),
        "confidence": str(plan.get("confidence") or "medium"),
        "target_call_site_ids": [
            str(item) for item in _list(plan.get("target_call_site_ids"))
            if str(item)
        ],
        "statement_pair": {"left": {}, "right": {}},
        "left_statement_count": int(plan.get("left_statement_count") or 0),
        "right_statement_count": int(plan.get("right_statement_count") or 0),
        "call_alignment": {
            "procedure_tail": str(plan.get("procedure_tail") or ""),
            "left_procedure": str(plan.get("left_procedure") or ""),
            "right_procedure": str(plan.get("right_procedure") or ""),
            "is_frontier_ready": False,
        },
        "phase_order": phase_order,
        "invariant_skeleton": invariant,
        "requires_targeted_inline": any(
            str(action.get("kind") or "") == "open_one_wrapper"
            for action in phase_order
            if isinstance(action, dict)
        ),
        "expected_next": _expected_next_from_phase_order(phase_order),
        "why": str(plan.get("why") or ""),
    }


def _edit_slice_kind_from_plan(plan: dict[str, Any]) -> str:
    kind = str(plan.get("kind") or "")
    return {
        "asymmetric_seq_exposure_plan": "asymmetric_prefix_slice",
        "frontier_exposure_plan": "frontier_exposure_slice",
        "call_site_exposure_plan": "call_pair_slice",
        "frontier_ready_call_plan": "call_pair_slice",
    }.get(kind, "program_slice")


def _edit_slice_kind(step: dict[str, Any]) -> str:
    kind = str(step.get("kind") or "")
    return {
        "aligned_call_pair": "call_pair_slice",
        "different_call_pair": "wrapper_open_slice",
        "shifted_call_pair": "alignment_slice",
        "insert_delete_prefix": "asymmetric_prefix_slice",
        "frontier_blocker": "frontier_exposure_slice",
    }.get(kind, "program_slice")


def _edit_slice_phase_order(
    step: dict[str, Any],
    plan: dict[str, Any],
    left_stmt: dict[str, Any] | None,
    right_stmt: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if plan.get("phase_order"):
        return [
            _compact_phase_action(action)
            for action in _list(plan.get("phase_order"))
            if isinstance(action, dict)
        ]
    kind = str(step.get("kind") or "")
    if kind == "different_call_pair":
        return [
            _compact_phase_action({
                "kind": "open_one_wrapper",
                "tactic_family": "targeted_inline",
                "action_type": "strategy_hint",
                "tactic_hint": _targeted_inline_hint(step),
                "reason": "open the mismatching wrapper and re-run ProgramIR",
            }),
            _compact_phase_action({
                "kind": "recompute_program_ir",
                "tactic_family": "inspection",
                "action_type": "inspection_action",
                "tactic_hint": "-agent-view",
                "reason": "wrapper inline should expose lower-level call sites",
            }),
        ]
    if kind == "aligned_call_pair":
        return [_compact_phase_action({
            "kind": "call_named_equiv",
            "tactic_family": "call_named_equiv",
            "action_type": "tactic_candidate_if_frontier_ready",
            "tactic_template": "call <matching lemma>.",
            "reason": "consume the aligned call pair with a named equiv lemma",
        })]
    if kind == "frontier_blocker":
        side = str(step.get("side") or "")
        stmt = left_stmt if side == "left" else right_stmt
        return [_compact_phase_action(_expose_frontier_action(
            side=side,
            statement=stmt,
            reason="expose the last-call frontier before applying call lemmas",
        ))]
    return []


def _compact_phase_action(action: dict[str, Any]) -> dict[str, Any]:
    keys = {
        "kind",
        "side",
        "tactic_family",
        "action_type",
        "tactic_hint",
        "tactic_template",
        "lemma",
        "reason",
        "left_statement_order",
        "right_statement_order",
        "left_statement_count",
        "right_statement_count",
        "synthesized_invariant",
        "invariant_skeleton",
        "invariant_sources",
        "proof_intent",
        "requires_instantiation",
    }
    return {
        key: value
        for key, value in dict(action).items()
        if key in keys and value not in (None, "", [])
    }


def _edit_slice_invariant(
    plan: dict[str, Any],
    parsed_goal: dict[str, Any],
) -> dict[str, Any]:
    synthesized = str(plan.get("synthesized_invariant") or "")
    pieces = _condition_conjuncts(synthesized)
    if not pieces:
        pieces = (
            _condition_conjuncts(str(parsed_goal.get("post") or ""))
            + _condition_conjuncts(str(parsed_goal.get("pre") or ""))
        )
    pieces = [
        piece for piece in _dedupe_condition_pieces(pieces)
        if not _condition_piece_is_too_broad(piece)
    ]
    return {
        "available": bool(pieces),
        "conjuncts": pieces[:12],
        "tactic_fragment": " /\\ ".join(pieces[:12]),
        "sources": _strings(plan.get("invariant_sources")),
    }


def _statement_ref(stmt: dict[str, Any] | None) -> dict[str, Any]:
    item = _dict(stmt)
    if not item:
        return {}
    return {
        "statement_id": str(item.get("statement_id") or ""),
        "statement_path": str(item.get("statement_path") or ""),
        "kind": str(item.get("kind") or ""),
        "procedure": str(item.get("procedure") or ""),
        "call_site_id": str(item.get("call_site_id") or ""),
        "is_frontier_call": bool(item.get("is_frontier_call")),
    }


def _expected_next_from_phase_order(phase_order: list[dict[str, Any]]) -> dict[str, Any]:
    for action in phase_order:
        if not isinstance(action, dict):
            continue
        kind = str(action.get("kind") or "")
        if kind and kind != "weaken_or_normalize_post":
            return {
                "kind": kind,
                "tactic": str(action.get("tactic_hint") or action.get("tactic_template") or ""),
                "action_type": str(action.get("action_type") or ""),
            }
    return {}


def _parent_path(path: str) -> str:
    parts = re.findall(r"\d+", str(path or ""))
    if len(parts) <= 1:
        return ""
    return ".".join(parts[:-1])


def _path_sort_key(path: str) -> tuple[int, ...]:
    values = []
    for part in re.findall(r"\d+", str(path or "")):
        try:
            values.append(int(part))
        except Exception:
            values.append(9999)
    return tuple(values or [9999])


def _top_level(statements: list[dict[str, Any]], side: str) -> list[dict[str, Any]]:
    return sorted(
        [
            stmt for stmt in statements
            if stmt.get("side") == side and stmt.get("top_level")
        ],
        key=lambda stmt: int(stmt.get("order") or 0),
    )


def _annotate_statement_context(statements: list[dict[str, Any]]) -> None:
    for side in ("left", "right"):
        top = _top_level(statements, side)
        total = len(top)
        for idx, stmt in enumerate(top, start=1):
            stmt["top_level_index"] = idx
            stmt["side_statement_count"] = total
            stmt["suffix_statement_count"] = max(total - idx, 0)


def _normalize_statement(
    stmt: dict[str, Any],
    *,
    side: str,
    order: int,
    abstract_modules: set[str] | None = None,
) -> dict[str, Any]:
    text = str(stmt.get("text") or "").strip()
    kind = str(stmt.get("type") or "").strip().upper() or _infer_kind(text)
    procedure = str(stmt.get("procedure") or "").strip()
    if not procedure and ("<@" in text or kind == "CALL"):
        procedure = _fallback_proc_from_call_text(text)
    position = stmt.get("pos", order)
    statement_path = str(stmt.get("pos_path") or position or order)
    depth = _path_depth(statement_path)
    is_call = kind == "CALL" or "<@" in text
    statement_id = f"{side}:{statement_path or order}"
    call_site_id = (
        f"{statement_id}:{_safe_id(procedure or 'call')}"
        if is_call else ""
    )
    boundary = _oracle_boundary(procedure)
    call_boundary_kind = _call_boundary_kind(
        procedure,
        is_call=is_call,
        abstract_modules=abstract_modules or set(),
        oracle_boundary=boundary,
    )
    return {
        "id": statement_id,
        "statement_id": statement_id,
        "side": side,
        "order": order,
        "position": position,
        "statement_path": statement_path,
        "ec_codepos_hint": statement_path,
        "ec_codegap_before_hint": f"^<{statement_path}" if statement_path else "",
        "kind": kind,
        "type": kind,
        "text": text,
        "statement": text,
        "procedure": procedure,
        "distribution": str(stmt.get("distribution") or ""),
        "vars_written": _strings(stmt.get("vars_written")),
        "vars_read": _strings(stmt.get("vars_read")),
        "depth": depth,
        "top_level": depth == 1,
        "is_call_site": is_call,
        "call_site_id": call_site_id,
        "oracle_boundary": boundary,
        "call_boundary_kind": call_boundary_kind,
        "frontier_role": "nested_non_frontier" if is_call else "",
        "alive": True,
        "is_frontier_statement": False,
        "is_frontier_call": False,
        "requires_cut_to_frontier": False,
    }


def _mark_frontier(statements: list[dict[str, Any]]) -> None:
    for side in ("left", "right"):
        top = [
            stmt for stmt in statements
            if stmt.get("side") == side and stmt.get("top_level")
        ]
        if not top:
            continue
        last = max(top, key=lambda stmt: int(stmt.get("order") or 0))
        last["is_frontier_statement"] = True
        if last.get("is_call_site"):
            last["is_frontier_call"] = True
            last["frontier_role"] = (
                "oracle_obligation_source"
                if str(last.get("call_boundary_kind") or "") == "abstract_adversary_call" else
                "current_frontier"
            )
        for stmt in top:
            if stmt.get("is_call_site") and not stmt.get("is_frontier_call"):
                stmt["requires_cut_to_frontier"] = True
                stmt["frontier_role"] = "nested_non_frontier"


def _frontier_summary(
    statements: list[dict[str, Any]],
    goal_type: str,
) -> dict[str, Any]:
    by_side: dict[str, Any] = {}
    blockers: dict[str, Any] = {}
    frontier_call_ids: list[str] = []
    for side in ("left", "right"):
        frontier = next(
            (
                stmt for stmt in statements
                if stmt.get("side") == side and stmt.get("is_frontier_statement")
            ),
            None,
        )
        if not frontier:
            by_side[side] = None
            continue
        item = {
            "statement_id": str(frontier.get("statement_id") or ""),
            "kind": str(frontier.get("kind") or ""),
            "procedure": str(frontier.get("procedure") or ""),
            "call_site_id": str(frontier.get("call_site_id") or ""),
            "is_call": bool(frontier.get("is_call_site")),
            "call_boundary_kind": str(frontier.get("call_boundary_kind") or ""),
            "frontier_role": str(frontier.get("frontier_role") or ""),
        }
        by_side[side] = item
        if frontier.get("is_call_site"):
            frontier_call_ids.append(str(frontier.get("call_site_id") or ""))
        else:
            blockers[side] = item
    return {
        "goal_type": goal_type,
        "by_side": by_side,
        "frontier_call_site_ids": [
            call_id for call_id in frontier_call_ids if call_id
        ],
        "frontier_blockers": blockers,
        "has_frontier_pair": bool(by_side.get("left") and by_side.get("right")
                                  and by_side["left"].get("is_call")
                                  and by_side["right"].get("is_call")),
    }


def _compact_call_site(site: dict[str, Any]) -> dict[str, Any]:
    return {
        "call_site_id": str(site.get("call_site_id") or ""),
        "side": str(site.get("side") or ""),
        "statement_path": str(site.get("statement_path") or ""),
        "procedure": str(site.get("procedure") or ""),
        "is_frontier_call": bool(site.get("is_frontier_call")),
        "requires_cut_to_frontier": bool(site.get("requires_cut_to_frontier")),
        "call_boundary_kind": str(site.get("call_boundary_kind") or ""),
        "frontier_role": str(site.get("frontier_role") or ""),
    }


def _procedure_matches(handle_proc: str, site_proc: str) -> bool:
    if not handle_proc:
        return False
    left = _normalize_proc(handle_proc)
    right = _normalize_proc(site_proc)
    if not left or not right:
        return False
    if left == right:
        return True
    left_tail = _proc_tail(left)
    right_tail = _proc_tail(right)
    return bool(left_tail and right_tail and left_tail == right_tail)


def _normalize_proc(proc: str) -> str:
    return _procedure_spine_key(proc, strip_outer=False)


def _fallback_proc_from_call_text(text: str) -> str:
    call = _parse_call_statement(text, strip_outer=False)
    if call is None:
        return ""
    return _procedure_spine_key(call.procedure, strip_outer=False)


def _path_depth(path: str) -> int:
    digits = re.findall(r"\d+", path)
    return max(1, len(digits))


def _oracle_boundary(procedure: str) -> dict[str, Any]:
    tokens = [tok for tok in re.split(r"[.()]+", procedure) if tok]
    marker = next(
        (
            tok for tok in tokens
            if tok in {"O", "Oracle", "Oracles"}
            or tok.endswith("RO")
            or tok.endswith("Orcls")
        ),
        "",
    )
    return {
        "is_oracle_like": bool(marker),
        "marker": marker,
    }


def _abstract_module_names(goal_text: str) -> set[str]:
    if not goal_text:
        return set()
    header = re.split(r"^-{5,}\s*$", goal_text, maxsplit=1, flags=re.MULTILINE)[0]
    names: set[str] = set()
    for line in header.splitlines():
        match = re.match(r"\s*([A-Z][A-Za-z0-9_']*)\b(?P<rest>.*)$", line)
        if not match:
            continue
        rest = str(match.group("rest") or "")
        if ":" not in rest:
            continue
        if re.search(r"(?:Adv|Adversary|Distinguisher)\w*", rest):
            name = match.group(1)
            names.add(name)
    return names


def _call_boundary_kind(
    procedure: str,
    *,
    is_call: bool,
    abstract_modules: set[str],
    oracle_boundary: dict[str, Any],
) -> str:
    if not is_call:
        return ""
    if not procedure:
        return "unknown_call"
    head = _module_head(procedure)
    tail = _proc_tail(_normalize_proc(procedure)).rsplit(".", 1)[-1]
    if head in abstract_modules:
        return "abstract_adversary_call"
    if (
        len(head) == 1
        and head.isupper()
        and "(" in procedure
        and tail in {"main", "distinguish", "guess", "choose", "challenge"}
    ):
        return "abstract_adversary_call"
    if _dict(oracle_boundary).get("is_oracle_like"):
        return "oracle_call"
    return "direct_call"


def _module_head(procedure: str) -> str:
    clean = procedure.strip()
    match = re.match(r"\s*([A-Z][A-Za-z0-9_']*)", clean)
    return match.group(1) if match else ""


def _handle_matches_oracle_source(
    procedures: list[str],
    source_site: dict[str, Any],
) -> bool:
    haystack = (
        str(source_site.get("procedure") or "")
        + " "
        + str(source_site.get("statement") or "")
        + " "
        + str(source_site.get("text") or "")
    )
    if not haystack:
        return False
    for proc in procedures:
        head = _module_head(proc)
        tail = _proc_tail(_normalize_proc(proc)).rsplit(".", 1)[-1]
        if head and re.search(rf"(?<![A-Za-z0-9_']){re.escape(head)}(?![A-Za-z0-9_'])", haystack):
            return True
        if tail and re.search(rf"\b{re.escape(tail)}\b", haystack):
            return True
    return False


def _condition_conjuncts(text: str) -> list[str]:
    clean = re.sub(
        r"^\s*(?:pre|post)\s*=\s*",
        "",
        str(text or "").strip(),
        flags=re.IGNORECASE,
    )
    if not clean:
        return []
    return [
        _normalize_condition_piece(piece)
        for piece in _split_flat_conjuncts(clean)
        if _normalize_condition_piece(piece)
    ]


def _normalize_condition_piece(piece: str) -> str:
    text = re.sub(r"\s+", " ", str(piece or "").strip())
    while _has_wrapping_parens(text):
        text = text[1:-1].strip()
    return text


def _has_wrapping_parens(text: str) -> bool:
    if not (text.startswith("(") and text.endswith(")")):
        return False
    depth = 0
    for index, char in enumerate(text):
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth < 0:
                return False
            if depth == 0 and index != len(text) - 1:
                return False
    return depth == 0


def _condition_piece_is_too_broad(piece: str) -> bool:
    return str(piece or "").strip() in {"true", "pre", "post"}


def _dedupe_condition_pieces(values: Iterable[str]) -> list[str]:
    pieces = _dedupe_strings([
        _normalize_condition_piece(item)
        for item in values
        if _normalize_condition_piece(item)
    ])
    eq_sets = [
        (_eq_set_vars(piece), piece)
        for piece in pieces
    ]
    out: list[str] = []
    for piece in pieces:
        vars_here = _eq_set_vars(piece)
        if vars_here and any(
            vars_here < other_vars
            for other_vars, other_piece in eq_sets
            if other_piece != piece
        ):
            continue
        out.append(piece)
    return out


def _eq_set_vars(piece: str) -> set[str]:
    match = re.fullmatch(r"=\{([^}]*)\}", str(piece or "").strip())
    if not match:
        return set()
    return {
        item.strip()
        for item in match.group(1).split(",")
        if item.strip()
    }


__all__ = [
    "PROGRAM_IR_KIND",
    "PROGRAM_IR_SCHEMA_VERSION",
    "annotate_callable_lemma_handles",
    "build_program_ir",
]
