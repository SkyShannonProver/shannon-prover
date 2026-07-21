"""Candidate binding pass for EasyCrypt instantiation slots.

Name resolution turns lemma signatures into typed slots.  This pass searches
the current source/context and parsed goal for conservative values that could
fill those slots.  It is intentionally read-only: candidates carry evidence and
confidence, but the pass never verifies or commits tactics.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

from core.easycrypt.analysis.ec_utils import (
    as_dict as _dict,
    as_list as _list,
    dedupe_ranked_by_value as _dedupe_ranked_by_value,
    dedupe_strings as _dedupe_strings,
    matching_delimiter as _matching_delimiter,
    procedure_tail as _proc_tail,
    session_source_files as _context_files,
    split_top_level_commas as _split_top_level_commas,
    split_top_level_at as _split_top_level_at,
    split_top_level_conjuncts as _split_top_level_conjuncts,
    unqualified as _unqualified,
)
from core.easycrypt.analysis.ec_procedure_ref import (
    parse_call_argument_site as _parse_call_argument_site,
    procedure_application_key as _procedure_application_key,
    procedure_exact_key as _procedure_exact_key,
)
from core.easycrypt.analysis.ec_pr_elaborator import build_pr_elaboration


INSTANTIATION_BINDING_SCHEMA_VERSION = 1
INSTANTIATION_BINDING_KIND = "easycrypt_instantiation_binding"


def build_instantiation_bindings(
    *,
    session_dir: str | Path | None = None,
    parsed_goal: dict[str, Any] | None = None,
    name_resolution: dict[str, Any] | None = None,
    goal_text: str = "",
) -> dict[str, Any]:
    """Bind typed signature slots to conservative context/goal candidates."""
    parsed = _dict(parsed_goal)
    resolution = _dict(name_resolution)
    context_files = _context_files(session_dir)
    source_modules = _source_module_candidates(context_files)
    goal_candidates = _goal_candidates(parsed, extra_texts=[goal_text])
    goal_texts = [
        str(item.get("value") or "")
        for item in goal_candidates.get("strings", [])
    ]

    items: list[dict[str, Any]] = []
    for resolved in _list(resolution.get("items")):
        if not isinstance(resolved, dict):
            continue
        slots = [
            dict(slot) for slot in _list(resolved.get("parameter_slots"))
            if isinstance(slot, dict)
        ]
        if not slots:
            continue
        item_bindings = [
            _bind_slot(
                slot,
                resolved=resolved,
                all_slots=slots,
                source_modules=source_modules,
                goal_candidates=goal_candidates,
            )
            for slot in slots
        ]
        instantiated = _instantiated_templates(
            resolved,
            item_bindings,
        )
        call_elaboration = _call_elaboration(
            resolved,
            item_bindings,
            instantiated_templates=instantiated,
        )
        pr_elaboration = build_pr_elaboration(
            lemma_name=str(resolved.get("name") or ""),
            handle_kind=str(resolved.get("handle_kind") or ""),
            declaration=str(resolved.get("declaration") or ""),
            goal_texts=goal_texts,
            slot_bindings=item_bindings,
            instantiated_templates=instantiated,
        )
        items.append({
            "name": str(resolved.get("name") or ""),
            "handle_kind": str(resolved.get("handle_kind") or ""),
            "tactic_template": str(resolved.get("tactic_template") or ""),
            "instantiated_templates": instantiated,
            "call_elaboration": call_elaboration,
            "slots": item_bindings,
            "pr_elaboration": pr_elaboration,
        })

    return {
        "schema_version": INSTANTIATION_BINDING_SCHEMA_VERSION,
        "kind": INSTANTIATION_BINDING_KIND,
        "context_files": [str(path) for path in context_files],
        "summary": _summary(items),
        "source_summary": {
            "source_module_candidates": len(source_modules),
            "goal_module_candidates": len(goal_candidates["modules"]),
            "goal_memory_candidates": len(goal_candidates["memories"]),
            "goal_call_argument_sites": len(goal_candidates["call_arguments"]),
        },
        "items": items,
    }


def binding_for_name(
    bindings: dict[str, Any],
    name: str,
) -> dict[str, Any]:
    if not name:
        return {}
    target = _unqualified(name)
    for item in _list(_dict(bindings).get("items")):
        if not isinstance(item, dict):
            continue
        if str(item.get("name") or "") == name:
            return item
        if _unqualified(str(item.get("name") or "")) == target:
            return item
    return {}


def _bind_slot(
    slot: dict[str, Any],
    *,
    resolved: dict[str, Any],
    all_slots: list[dict[str, Any]],
    source_modules: list[dict[str, Any]],
    goal_candidates: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    kind = str(slot.get("kind") or "")
    if kind == "module_arg":
        candidates = _module_slot_candidates(
            slot,
            source_modules=source_modules,
            goal_modules=goal_candidates["modules"],
            declaration=str(resolved.get("declaration") or ""),
            goal_texts=[
                str(item.get("value") or "")
                for item in goal_candidates.get("strings", [])
            ],
        )
    elif kind == "memory_arg":
        candidates = _memory_slot_candidates(
            slot,
            memories=goal_candidates["memories"],
        )
    elif kind == "type_arg":
        candidates = _type_slot_candidates(slot)
    elif kind in {"proof_arg", "implicit_arg"}:
        candidates = _placeholder_slot_candidates(slot, kind=kind)
    else:
        candidates = _value_slot_candidates(
            slot,
            values=goal_candidates["values"],
            call_arguments=goal_candidates["call_arguments"],
            declaration=str(resolved.get("declaration") or ""),
            goal_texts=[
                str(item.get("value") or "")
                for item in goal_candidates.get("strings", [])
            ],
            procedure=str(resolved.get("procedure") or ""),
            value_slot_ordinal=_value_slot_ordinal(slot, all_slots),
            value_slot_count=len([
                item for item in all_slots
                if str(item.get("kind") or "") == "value_arg"
            ]),
            value_slot_names=[
                str(item.get("name") or "")
                for item in all_slots
                if str(item.get("kind") or "") == "value_arg"
            ],
        )
    return {
        "slot": {
            "index": int(slot.get("index") or 0),
            "kind": kind,
            "name": str(slot.get("name") or ""),
            "type_or_bound": str(slot.get("type_or_bound") or ""),
            "placeholder": str(slot.get("placeholder") or ""),
        },
        "candidates": candidates,
        "selected_candidate": candidates[0] if candidates else {},
    }


def _module_slot_candidates(
    slot: dict[str, Any],
    *,
    source_modules: list[dict[str, Any]],
    goal_modules: list[dict[str, Any]],
    declaration: str = "",
    goal_texts: list[str] | None = None,
) -> list[dict[str, Any]]:
    bound = _clean_bound(str(slot.get("type_or_bound") or ""))
    slot_name = str(slot.get("name") or "")
    candidates: list[dict[str, Any]] = _module_shape_candidates(
        slot_name=slot_name,
        declaration=declaration,
        goal_texts=goal_texts or [],
    )
    for module in source_modules:
        value = str(module.get("value") or "")
        if not value:
            continue
        confidence, reason = _module_confidence(
            value,
            slot_name=slot_name,
            bound=bound,
            module_bound=str(module.get("bound") or ""),
            source=str(module.get("source") or ""),
        )
        candidates.append({
            "value": value,
            "source": str(module.get("source") or "source_context"),
            "confidence": confidence,
            "reason": reason,
            "bound": str(module.get("bound") or ""),
        })
    for module in goal_modules:
        value = str(module.get("value") or "")
        if not value:
            continue
        source = str(module.get("source") or "parsed_goal")
        if _module_value_matches_slot(value, slot_name):
            confidence = "high"
            reason = (
                f"`{value}` matches module slot `{slot_name}`"
                if value == slot_name else
                f"`{value}` has tail matching module slot `{slot_name}`"
            )
        elif ".functor_arg" in source or str(module.get("confidence") or "") == "medium":
            confidence = "medium"
            reason = str(module.get("reason") or "module appears in current goal")
        else:
            confidence = "low"
            reason = str(module.get("reason") or "module appears in current goal")
        candidates.append({
            "value": value,
            "source": source,
            "confidence": confidence,
            "reason": reason,
            "bound": "",
        })
    return _dedupe_candidates(candidates)


def _memory_slot_candidates(
    slot: dict[str, Any],
    *,
    memories: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    name = str(slot.get("name") or "")
    candidates: list[dict[str, Any]] = []
    for memory in memories:
        value = str(memory.get("value") or "")
        if not value:
            continue
        candidates.append({
            "value": value,
            "source": str(memory.get("source") or "parsed_goal"),
            "confidence": "high" if value == name else "medium",
            "reason": str(memory.get("reason") or "memory token appears in current goal"),
        })
    if name:
        candidates.append({
            "value": name,
            "source": "signature",
            "confidence": "medium",
            "reason": "memory argument is named explicitly in the signature",
        })
    return _dedupe_candidates(candidates)


def _type_slot_candidates(slot: dict[str, Any]) -> list[dict[str, Any]]:
    placeholder = str(slot.get("placeholder") or "")
    return [{
        "value": "_",
        "source": "signature",
        "confidence": "low",
        "reason": (
            f"type slot {placeholder} usually needs EC inference or a "
            "human-supplied type"
        ),
    }]


def _placeholder_slot_candidates(
    slot: dict[str, Any],
    *,
    kind: str,
) -> list[dict[str, Any]]:
    name = str(slot.get("name") or "")
    reason = (
        "proof obligation argument can be left to EC inference or surfaced as a side condition"
        if kind == "proof_arg" else
        "implicit argument should be inferred by EasyCrypt"
    )
    return [{
        "value": "_",
        "source": "signature",
        "confidence": "medium",
        "reason": f"{kind} `{name}`: {reason}" if name else reason,
    }]


def _value_slot_candidates(
    slot: dict[str, Any],
    *,
    values: list[dict[str, Any]],
    call_arguments: list[dict[str, Any]],
    declaration: str,
    goal_texts: list[str],
    procedure: str,
    value_slot_ordinal: int,
    value_slot_count: int,
    value_slot_names: list[str],
) -> list[dict[str, Any]]:
    name = str(slot.get("name") or "")
    aliases = _value_aliases(name)
    candidates: list[dict[str, Any]] = _value_shape_candidates(
        slot,
        declaration=declaration,
        goal_texts=goal_texts,
    )
    candidates.extend(_value_constraint_candidates(
        slot,
        declaration=declaration,
        call_arguments=call_arguments,
        procedure=procedure,
    ))
    for call in _matching_call_arguments(call_arguments, procedure):
        args = [
            str(arg) for arg in _list(call.get("arguments"))
            if str(arg)
        ]
        if not args:
            continue
        for arg in args:
            if _value_matches_slot(arg, name, aliases):
                candidates.append({
                    "value": arg,
                    "source": str(call.get("source") or "parsed_goal.call_argument"),
                    "side": str(call.get("side") or ""),
                    "side_index": str(call.get("side_index") or ""),
                    "call_procedure": str(call.get("procedure") or ""),
                    "confidence": "high" if arg == name else "medium",
                    "reason": (
                        f"call argument `{arg}` matches value slot `{name}` "
                        "by exact or stem match"
                    ),
                })
        if (
            value_slot_count
            and len(args) == value_slot_count
            and 1 <= value_slot_ordinal <= len(args)
            and _positional_value_args_have_binding_evidence(args, value_slot_names)
        ):
            arg = args[value_slot_ordinal - 1]
            confidence = "high" if _value_matches_slot(arg, name, aliases) else "medium"
            candidates.append({
                "value": arg,
                "source": str(call.get("source") or "parsed_goal.call_argument"),
                "side": str(call.get("side") or ""),
                "side_index": str(call.get("side_index") or ""),
                "call_procedure": str(call.get("procedure") or ""),
                "confidence": confidence,
                "reason": (
                    f"call argument position {value_slot_ordinal} matches "
                    f"value slot `{name}` because the call has the same "
                    "number of value arguments as the lemma"
                ),
            })
    for value in values:
        candidate = str(value.get("value") or "")
        if not candidate:
            continue
        confidence = (
            "high" if candidate == name else
            "medium" if _value_matches_slot(candidate, name, aliases) else
            "low"
        )
        candidates.append({
            "value": candidate,
            "source": str(value.get("source") or "parsed_goal"),
            "confidence": confidence,
            "reason": (
                str(value.get("reason") or "value appears in current goal")
                + (
                    f"; matches value slot `{name}` by stem"
                    if confidence == "medium" and candidate != name else
                    ""
                )
            ),
        })
    candidates.append({
        "value": "_",
        "source": "signature",
        "confidence": "low",
        "reason": "leave value argument for EC inference",
    })
    return _dedupe_candidates(candidates)


def _instantiated_templates(
    resolved: dict[str, Any],
    slot_bindings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    name = str(resolved.get("name") or "")
    handle_kind = str(resolved.get("handle_kind") or "")
    if not name or not slot_bindings:
        return []
    args: list[str] = []
    confidence_rank = 0
    evidence: list[dict[str, Any]] = []
    simplify_after_rewrite = False
    for binding in slot_bindings:
        selected = _dict(binding.get("selected_candidate"))
        value = str(selected.get("value") or "")
        slot = _dict(binding.get("slot"))
        if not value:
            value = str(slot.get("placeholder") or "_")
            confidence_rank = max(confidence_rank, 3)
        args.append(value)
        evidence.append({
            "slot": str(slot.get("placeholder") or ""),
            "value": value,
            "source": str(selected.get("source") or ""),
            "confidence": str(selected.get("confidence") or "low"),
        })
        simplify_after_rewrite = simplify_after_rewrite or bool(
            selected.get("post_rewrite_simplification")
        )
        confidence_rank = max(confidence_rank, _confidence_rank(
            str(selected.get("confidence") or "low")
        ))
        if (
            str(selected.get("confidence") or "low") == "low"
            and str(slot.get("kind") or "") != "type_arg"
        ):
            return []
    tactic = _template_for(
        handle_kind,
        name,
        args,
        simplify_after_rewrite=simplify_after_rewrite,
    )
    if not tactic:
        return []
    return [{
        "status": "candidate_from_context",
        "tactic": tactic,
        "confidence": _rank_confidence(confidence_rank),
        "evidence": evidence,
    }]


def _call_elaboration(
    resolved: dict[str, Any],
    slot_bindings: list[dict[str, Any]],
    *,
    instantiated_templates: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Record the exlim/call plumbing for call-level value parameters.

    This is the pRHL counterpart of the Pr elaborator: it keeps program-side
    expressions (``n{1}``) distinct from logical lemma parameters (``n0``).
    The record is a strategy hint, not an EC-certified tactic.
    """
    name = str(resolved.get("name") or "")
    handle_kind = str(resolved.get("handle_kind") or "")
    if handle_kind != "call_equiv" or not name or not slot_bindings:
        return {}
    value_slots = [
        _dict(binding) for binding in slot_bindings
        if str(_dict(_dict(binding).get("slot")).get("kind") or "") == "value_arg"
    ]
    if not value_slots:
        return {}

    lifted: list[dict[str, Any]] = []
    missing: list[dict[str, str]] = []
    call_args_by_slot: dict[int, str] = {}
    direct_call_args_by_slot: dict[int, str] = {}
    for binding in slot_bindings:
        b = _dict(binding)
        slot = _dict(b.get("slot"))
        selected = _dict(b.get("selected_candidate"))
        if str(slot.get("kind") or "") != "value_arg":
            continue
        slot_name = str(slot.get("name") or f"x{len(lifted) + 1}")
        value = str(selected.get("value") or "")
        confidence = str(selected.get("confidence") or "low")
        source = str(selected.get("source") or "")
        program_expression = str(selected.get("program_expression") or "")
        selected_role = str(selected.get("role") or "")
        if (
            not value
            or value == "_"
            or confidence == "low"
            or (
                "call_argument" not in source
                and not program_expression
                and selected_role != "state_snapshot_parameter"
            )
        ):
            missing.append({
                "slot": slot_name,
                "role": "value_arg",
                "reason": (
                    "no medium/high-confidence value candidate was extracted "
                    "from the current call-site arguments or lemma equality constraints"
                ),
            })
            continue
        side_index = str(selected.get("side_index") or "")
        if not program_expression:
            program_expression = f"{value}{{{side_index}}}" if side_index else value
        logical_name = slot_name or f"x{len(lifted) + 1}"
        lifted.append({
            "slot": slot_name,
            "logical_name": logical_name,
            "program_expression": program_expression,
            "raw_value": value,
            "side": str(selected.get("side") or ""),
            "side_index": side_index,
            "source": source,
            "confidence": confidence,
            "role": selected_role or "call_site_value_parameter",
            "belongs_to": "lemma_value_parameter",
            "reason": str(selected.get("reason") or ""),
        })
        call_args_by_slot[int(slot.get("index") or 0)] = logical_name
        direct_call_args_by_slot[int(slot.get("index") or 0)] = program_expression

    if missing or not lifted:
        return {
            "available": False,
            "kind": "call_value_argument_elaboration",
            "lemma": name,
            "missing_slots": missing,
            "strategy_boundary": (
                "ProofIR can suggest exlim/call elaboration only after value "
                "arguments are tied to current call-site expressions."
            ),
        }

    call_args: list[str] = []
    direct_call_args: list[str] = []
    unresolved_non_value: list[str] = []
    for binding in slot_bindings:
        b = _dict(binding)
        slot = _dict(b.get("slot"))
        selected = _dict(b.get("selected_candidate"))
        kind = str(slot.get("kind") or "")
        slot_index = int(slot.get("index") or 0)
        if kind == "value_arg" and slot_index in call_args_by_slot:
            call_args.append(call_args_by_slot[slot_index])
            direct_call_args.append(direct_call_args_by_slot[slot_index])
            continue
        value = str(selected.get("value") or "")
        confidence = str(selected.get("confidence") or "low")
        if not value:
            value = str(slot.get("placeholder") or "_")
        call_args.append(value)
        direct_call_args.append(value)
        if kind != "type_arg" and (not value or value == "_" or confidence == "low"):
            unresolved_non_value.append(_slot_label(slot))

    exlim_left = ", ".join(str(item["program_expression"]) for item in lifted)
    exlim_right = " ".join(str(item["logical_name"]) for item in lifted)
    call_text = f"call ({name} {' '.join(call_args)})."
    tactic = f"exlim {exlim_left} => {exlim_right}; {call_text}"
    direct_ecall = f"ecall ({name} {' '.join(direct_call_args)})."
    naked_templates = [
        str(item.get("tactic") or "")
        for item in (instantiated_templates or [])
        if isinstance(item, dict) and str(item.get("tactic") or "")
    ]
    precondition_coverage = _call_precondition_coverage(
        str(resolved.get("declaration") or ""),
        lifted_value_arguments=lifted,
    )
    preview_preconditions = _call_precondition_preview_lines(
        precondition_coverage
    )
    return {
        "available": True,
        "kind": "call_value_argument_elaboration",
        "lemma": name,
        "status": "strategy_hint_not_verified",
        "requires_exlim": True,
        "tactic_template": tactic,
        "direct_ecall_template": direct_ecall,
        "naked_instantiated_templates": naked_templates[:3],
        "lifted_value_arguments": lifted,
        "unresolved_non_value_slots": unresolved_non_value,
        "lemma_precondition_coverage": precondition_coverage,
        "preconditions": [
            "the current pRHL frontier still contains the displayed call-site expressions",
            "use this when the value arguments are program expressions rather than already-introduced logical variables",
            *preview_preconditions,
            "this pass does not prove frontier compatibility; a manager commit will report EasyCrypt's verdict",
        ],
        "strategy_boundary": (
            "Compiler provides typed argument plumbing. The prover still "
            "chooses whether this lemma is the right frontier strategy."
        ),
    }


def _call_precondition_coverage(
    declaration: str,
    *,
    lifted_value_arguments: list[dict[str, Any]],
) -> dict[str, Any]:
    """Summarize what a call-equiv lemma will demand before it can fire.

    This is deliberately name-agnostic.  It reads the equiv declaration as a
    tiny typed IR: value slots already tied to program expressions are marked
    as exlim-covered, while remaining atoms are exposed as expected residual
    obligations for the prover to plan around.
    """
    pre_atoms, post_atoms = _declaration_pre_post_atoms(declaration)
    if not pre_atoms and not post_atoms:
        return {"available": False, "reason": "no declaration pre/post atoms parsed"}

    lifted_by_logical = {
        str(item.get("logical_name") or ""): _dict(item)
        for item in lifted_value_arguments
        if str(item.get("logical_name") or "")
    }
    lifted_names = set(lifted_by_logical)
    entries: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    for atom in pre_atoms:
        entry = _classify_call_precondition_atom(
            atom,
            lifted_by_logical=lifted_by_logical,
            lifted_names=lifted_names,
        )
        entries.append(entry)
        category = str(entry.get("category") or "unknown")
        counts[category] = counts.get(category, 0) + 1

    residual_entries = [
        item for item in entries
        if str(item.get("coverage") or "") != "bound_by_exlim"
    ]
    return {
        "available": True,
        "kind": "call_equiv_precondition_coverage",
        "coverage_label": (
            "all_value_bindings_only"
            if entries and not residual_entries else
            "static_precondition_preview"
        ),
        "pre_atom_count": len(pre_atoms),
        "post_atom_count": len(post_atoms),
        "category_counts": counts,
        "covered_by_exlim_count": len(entries) - len(residual_entries),
        "expected_residual_count": len(residual_entries),
        "precondition_atoms": entries,
        "expected_residual_atoms": residual_entries[:8],
        "postcondition_atoms_preview": [
            _clean_constraint_expr(atom) for atom in post_atoms[:6]
            if _clean_constraint_expr(atom)
        ],
        "strategy_boundary": (
            "Static coverage only: it tells the prover what facts the call "
            "will need, but it does not prove those facts or rank the proof "
            "strategy by lemma name."
        ),
    }


def _classify_call_precondition_atom(
    atom: str,
    *,
    lifted_by_logical: dict[str, dict[str, Any]],
    lifted_names: set[str],
) -> dict[str, Any]:
    clean = _clean_constraint_expr(atom)
    sides = _top_level_equality_sides(clean)
    if sides:
        left, right = sides
        for logical_name, lifted in lifted_by_logical.items():
            if _expr_is_slot(left, logical_name) or _expr_is_slot(right, logical_name):
                other = right if _expr_is_slot(left, logical_name) else left
                if (
                    _same_expr_ignoring_space(
                        other,
                        str(lifted.get("program_expression") or ""),
                    )
                    or (
                        str(lifted.get("source") or "")
                        == "lemma_precondition.arg_projection"
                        and _arg_projection(other)
                    )
                ):
                    return {
                        "atom": clean,
                        "category": "value_parameter_binding",
                        "coverage": "bound_by_exlim",
                        "reason": (
                            "value slot is explicitly tied to a program-state "
                            "expression lifted by the generated exlim"
                        ),
                    }
                return {
                    "atom": clean,
                    "category": "value_parameter_binding",
                    "coverage": "expected_residual",
                    "reason": (
                        "value slot appears in an equality, but the other side "
                        "does not match the generated exlim expression"
                    ),
                }
    if re.search(r"\barg\s*(?:\{|\.|$)", clean):
        return {
            "atom": clean,
            "category": "call_argument_alignment",
            "coverage": "requires_frontier_unification",
            "reason": (
                "precondition constrains the current call argument; keep the "
                "call-site frontier visible and expect EC/unfolding residuals"
            ),
        }
    if _mentions_any_name(clean, lifted_names):
        return {
            "atom": clean,
            "category": "lifted_value_side_condition",
            "coverage": "expected_residual",
            "reason": (
                "precondition mentions a lifted logical value outside the "
                "binding equality; current invariant or cut must support it"
            ),
        }
    if _has_side_qualified_state(clean):
        return {
            "atom": clean,
            "category": "state_invariant_requirement",
            "coverage": "requires_current_invariant_or_cut",
            "reason": (
                "precondition mentions side-qualified state; verify the "
                "current invariant/cut preserves this fact"
            ),
        }
    return {
        "atom": clean,
        "category": "ambient_side_condition",
        "coverage": "expected_residual",
        "reason": (
            "precondition is not a value-slot binding; it may need unfolding, "
            "arithmetic/list reasoning, or an existing hypothesis"
        ),
    }


def _call_precondition_preview_lines(coverage: dict[str, Any]) -> list[str]:
    if not coverage.get("available"):
        return []
    residual = int(coverage.get("expected_residual_count") or 0)
    bound = int(coverage.get("covered_by_exlim_count") or 0)
    atoms = int(coverage.get("pre_atom_count") or 0)
    lines = [
        (
            "lemma precondition preview: "
            f"{bound}/{atoms} atoms are value-slot bindings covered by exlim; "
            f"{residual} residual atoms still need invariant/cut support"
        )
    ]
    residual_atoms = [
        str(_dict(item).get("atom") or "")
        for item in _list(coverage.get("expected_residual_atoms"))
        if str(_dict(item).get("atom") or "")
    ]
    if residual_atoms:
        lines.append(
            "expected residual obligations include: "
            + "; ".join(residual_atoms[:3])
        )
    return lines


def _declaration_pre_post_atoms(declaration: str) -> tuple[list[str], list[str]]:
    body = _declaration_logic_body(declaration)
    pre, post = _split_top_level_implication(body)
    return (
        _split_logic_conj_atoms(pre),
        _split_logic_conj_atoms(post),
    )


def _split_top_level_implication(text: str) -> tuple[str, str]:
    clean = re.sub(r"\s+", " ", str(text or "")).strip()
    return _split_top_level_at(clean, "==>") or (clean, "")


def _split_logic_conj_atoms(text: str) -> list[str]:
    atoms = _split_top_level_conjuncts(
        text,
        collapse_whitespace=True,
        nesting_open="([{",
    )
    return [
        _clean_constraint_expr(atom) for atom in atoms
        if _clean_constraint_expr(atom)
    ]


def _same_expr_ignoring_space(left: str, right: str) -> bool:
    return re.sub(r"\s+", "", _clean_constraint_expr(left)) == re.sub(
        r"\s+",
        "",
        _clean_constraint_expr(right),
    )


def _mentions_any_name(text: str, names: set[str]) -> bool:
    for name in names:
        if name and re.search(rf"(?<![A-Za-z0-9_']){re.escape(name)}(?![A-Za-z0-9_'])", text):
            return True
    return False


def _has_side_qualified_state(text: str) -> bool:
    return bool(re.search(r"\{[12]\}", str(text or "")))


def _value_constraint_candidates(
    slot: dict[str, Any],
    *,
    declaration: str,
    call_arguments: list[dict[str, Any]],
    procedure: str,
) -> list[dict[str, Any]]:
    """Infer value slots from lemma-side equality constraints.

    This handles the common EasyCrypt pattern where an equiv lemma freezes
    program state in explicit value parameters, e.g. ``mr0 = RO.m{1}``, or
    relates a value parameter to the current procedure argument via
    ``arg{2}.`1 = n0``.  The pass does not prove the constraints; it only
    classifies the slot role and extracts the program expression to lift.
    """
    name = str(slot.get("name") or "")
    if not name or not declaration:
        return []
    candidates: list[dict[str, Any]] = []
    for expr in _slot_equal_constraint_exprs(declaration, name):
        arg_candidate = _candidate_from_arg_expr(
            expr,
            slot_name=name,
            call_arguments=call_arguments,
            procedure=procedure,
        )
        if arg_candidate:
            candidates.append(arg_candidate)
            continue
        state_candidate = _candidate_from_state_expr(expr, slot_name=name)
        if state_candidate:
            candidates.append(state_candidate)
    return _dedupe_candidates(candidates)


def _slot_equal_constraint_exprs(declaration: str, slot_name: str) -> list[str]:
    out: list[str] = []
    for atom in _declaration_logic_atoms(declaration):
        sides = _top_level_equality_sides(atom)
        if not sides:
            continue
        left, right = sides
        if _expr_is_slot(left, slot_name):
            out.append(right)
        elif _expr_is_slot(right, slot_name):
            out.append(left)
    return _dedupe_strings([
        _clean_constraint_expr(expr) for expr in out
        if _clean_constraint_expr(expr)
    ])


def _declaration_logic_atoms(declaration: str) -> list[str]:
    text = _declaration_logic_body(declaration)
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    if not text:
        return []
    atoms: list[str] = []
    start = 0
    depth = 0
    idx = 0
    while idx < len(text):
        ch = text[idx]
        if ch in "([{":
            depth += 1
            idx += 1
            continue
        if ch in ")]}":
            depth = max(0, depth - 1)
            idx += 1
            continue
        if depth == 0 and (text.startswith("/\\", idx) or text.startswith("==>", idx)):
            atom = text[start:idx].strip()
            if atom:
                atoms.append(atom)
            idx += 2 if text.startswith("/\\", idx) else 3
            start = idx
            continue
        idx += 1
    tail = text[start:].strip()
    if tail:
        atoms.append(tail)
    return atoms


def _declaration_logic_body(declaration: str) -> str:
    text = re.sub(r"\s+", " ", str(declaration or "")).strip()
    if not text:
        return ""
    # For equiv declarations, only the pre/post part after the procedure pair
    # contains value-slot constraints.  Keeping the declaration header attached
    # to the first atom hides constraints such as `arg{2}.`1 = n0`.
    match = re.search(r":\s*[^:~]+?\s*~\s*[^:]+?\s*:\s*(.*)$", text)
    if match:
        return match.group(1).strip()
    first_colon = text.find(":")
    return text[first_colon + 1:].strip() if first_colon >= 0 else text


def _top_level_equality_sides(atom: str) -> tuple[str, str] | None:
    text = str(atom or "").strip()
    if not text:
        return None
    depth = 0
    for idx, ch in enumerate(text):
        if ch in "([{":
            depth += 1
            continue
        if ch in ")]}":
            depth = max(0, depth - 1)
            continue
        if ch != "=" or depth != 0:
            continue
        prev_ch = text[idx - 1] if idx > 0 else ""
        next_ch = text[idx + 1] if idx + 1 < len(text) else ""
        if prev_ch in {"<", ">", "!"} or next_ch in {">", "{", "="}:
            continue
        left = _clean_constraint_expr(text[:idx])
        right = _clean_constraint_expr(text[idx + 1:])
        if left and right:
            return (left, right)
    return None


def _expr_is_slot(expr: str, slot_name: str) -> bool:
    return bool(re.fullmatch(rf"{re.escape(slot_name)}", _clean_constraint_expr(expr)))


def _clean_constraint_expr(expr: str) -> str:
    text = str(expr or "").strip()
    text = re.sub(r"^(?:pre|post)\s*=\s*", "", text)
    text = re.sub(r"^\(?\s*", "", text)
    text = re.sub(r"\s*\)?$", "", text)
    return text.strip().rstrip(",;")


def _candidate_from_state_expr(expr: str, *, slot_name: str) -> dict[str, Any]:
    text = _clean_constraint_expr(expr)
    match = re.fullmatch(
        r"(?P<base>[A-Za-z_][A-Za-z0-9_']*(?:\.[A-Za-z_][A-Za-z0-9_']*)*)"
        r"\s*\{\s*(?P<side>[12])\s*\}",
        text,
    )
    if not match:
        return {}
    base = match.group("base")
    side_index = match.group("side")
    return {
        "value": base,
        "program_expression": f"{base}{{{side_index}}}",
        "source": "lemma_precondition.value_slot_equality",
        "side": "left" if side_index == "1" else "right",
        "side_index": side_index,
        "confidence": "high",
        "role": "state_snapshot_parameter",
        "belongs_to": "lemma_value_parameter",
        "reason": (
            f"lemma equality binds value slot `{slot_name}` to state "
            f"expression `{base}{{{side_index}}}`"
        ),
    }


def _candidate_from_arg_expr(
    expr: str,
    *,
    slot_name: str,
    call_arguments: list[dict[str, Any]],
    procedure: str,
) -> dict[str, Any]:
    projection = _arg_projection(expr)
    if not projection:
        return {}
    side_index, arg_index = projection
    call = _call_for_arg_projection(
        call_arguments,
        side_index=side_index,
        procedure=procedure,
    )
    if not call:
        return {}
    args = [str(arg) for arg in _list(call.get("arguments")) if str(arg)]
    if arg_index < 1 or arg_index > len(args):
        return {}
    value = args[arg_index - 1]
    source_side = str(call.get("side_index") or side_index)
    return {
        "value": value,
        "program_expression": f"{value}{{{source_side}}}" if source_side else value,
        "source": "lemma_precondition.arg_projection",
        "side": str(call.get("side") or ("left" if source_side == "1" else "right")),
        "side_index": source_side,
        "call_procedure": str(call.get("procedure") or ""),
        "confidence": "high",
        "role": "call_argument_parameter",
        "belongs_to": "lemma_value_parameter",
        "reason": (
            f"lemma equality binds value slot `{slot_name}` to projection "
            f"`{_clean_constraint_expr(expr)}` of the current call argument"
        ),
    }


def _arg_projection(expr: str) -> tuple[str, int] | None:
    text = _clean_constraint_expr(expr)
    match = re.fullmatch(
        r"arg\s*\{\s*(?P<side>[12])\s*\}\s*\.\s*`(?P<idx>\d+)",
        text,
    )
    if match:
        return (match.group("side"), int(match.group("idx")))
    match = re.fullmatch(
        r"arg\s*\.\s*`(?P<idx>\d+)\s*\{\s*(?P<side>[12])\s*\}",
        text,
    )
    if match:
        return (match.group("side"), int(match.group("idx")))
    match = re.fullmatch(r"arg\s*\{\s*(?P<side>[12])\s*\}", text)
    if match:
        return (match.group("side"), 1)
    return None


def _call_for_arg_projection(
    call_arguments: list[dict[str, Any]],
    *,
    side_index: str,
    procedure: str,
) -> dict[str, Any]:
    side_matches = [
        call for call in call_arguments
        if str(call.get("side_index") or "") == side_index
    ]
    if side_matches:
        return side_matches[0]
    proc_matches = _matching_call_arguments(call_arguments, procedure)
    if proc_matches:
        return proc_matches[0]
    return call_arguments[0] if call_arguments else {}


def _template_for(
    handle_kind: str,
    name: str,
    args: list[str],
    *,
    simplify_after_rewrite: bool = False,
) -> str:
    arg_text = " ".join(args).strip()
    if not arg_text:
        return ""
    if handle_kind == "call_equiv":
        return f"call ({name} {arg_text})."
    if handle_kind in {"local_equiv_context", "addend_equiv"}:
        return f"byequiv ({name} {arg_text})."
    if handle_kind == "pr_rewrite":
        suffix = " /=." if simplify_after_rewrite else "."
        return f"rewrite ({name} {arg_text}){suffix}"
    if handle_kind == "have_chain":
        return f"have := {name} {arg_text}."
    return ""


def _slot_label(slot: dict[str, Any]) -> str:
    item = _dict(slot)
    kind = str(item.get("kind") or "arg")
    name = str(item.get("name") or item.get("placeholder") or "")
    return f"{kind} `{name}`" if name else kind


def _source_module_candidates(paths: list[Path]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    patterns = [
        (
            re.compile(
                r"\bdeclare\s+module\s+([A-Z][A-Za-z0-9_']*)\s*<:\s*"
                r"([A-Z][A-Za-z0-9_'.]*)"
            ),
            "declared_module",
        ),
        (
            re.compile(
                r"\blocal\s+module\s+([A-Z][A-Za-z0-9_']*)\s*:\s*"
                r"([A-Z][A-Za-z0-9_'.]*)"
            ),
            "local_module_signature",
        ),
        (
            re.compile(r"\blocal\s+module\s+([A-Z][A-Za-z0-9_']*)\b"),
            "local_module",
        ),
    ]
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        for pattern, source in patterns:
            for match in pattern.finditer(text):
                candidates.append({
                    "value": match.group(1),
                    "bound": match.group(2) if match.lastindex and match.lastindex >= 2 else "",
                    "source": f"source_context.{source}",
                    "reason": f"{source.replace('_', ' ')} in {path.name}",
                })
    return _dedupe_candidates(candidates)


def _goal_candidates(
    parsed_goal: dict[str, Any],
    *,
    extra_texts: list[str] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    modules: list[dict[str, Any]] = []
    memories: list[dict[str, Any]] = []
    values: list[dict[str, Any]] = []
    call_arguments: list[dict[str, Any]] = []
    strings: list[dict[str, Any]] = []
    raw_strings = list(_walk_strings(parsed_goal))
    for idx, text in enumerate(extra_texts or []):
        if str(text or "").strip():
            raw_strings.append((f"extra_goal_text.{idx}", str(text)))
    for key, value in raw_strings:
        strings.append({
            "value": value,
            "source": f"parsed_goal.{key}",
            "reason": "raw parsed-goal string",
        })
        for memory in re.findall(r"&[A-Za-z_]\w*", value):
            memories.append({
                "value": memory,
                "source": f"parsed_goal.{key}",
                "reason": "memory token appears in current goal",
            })
        for module in _functor_arg_mentions(value):
            modules.append({
                "value": module,
                "source": f"parsed_goal.{key}.functor_arg",
                "confidence": "medium",
                "reason": "module appears as a functor argument in current goal",
            })
        for module in _module_mentions(value):
            modules.append({
                "value": module,
                "source": f"parsed_goal.{key}",
                "confidence": "low",
                "reason": "module-like identifier appears in current goal",
            })
        if "<@" in value:
            call = _call_argument_candidates(value)
            if call:
                side, side_index = _side_from_goal_key(key)
                call_arguments.append({
                    **call,
                    "side": side,
                    "side_index": side_index,
                    "source": f"parsed_goal.{key}.call_argument",
                })
        if _is_value_candidate_source(key):
            for var in re.findall(r"\b[a-z][A-Za-z0-9_']*\b", value):
                if var in {"true", "false", "res", "glob", "forall", "Pr"}:
                    continue
                values.append({
                    "value": var,
                    "source": f"parsed_goal.{key}",
                    "reason": "value-like identifier appears in current goal",
                })
    return {
        "modules": _dedupe_candidates(modules),
        "memories": _dedupe_candidates(memories),
        "values": _dedupe_candidates(values),
        "call_arguments": _dedupe_call_arguments(call_arguments),
        "strings": _dedupe_candidates(strings),
    }


def _call_argument_candidates(text: str) -> dict[str, Any]:
    call = _parse_call_argument_site(text)
    if call is None:
        return {}
    args = [
        arg for arg in (_clean_call_arg(piece) for piece in call.arguments)
        if arg and _is_liftable_call_arg(arg)
    ]
    return {"procedure": call.procedure, "arguments": args}


def _side_from_goal_key(key: str) -> tuple[str, str]:
    text = str(key or "")
    if "left_statements" in text or ".lhs" in text or ".left" in text:
        return ("left", "1")
    if "right_statements" in text or ".rhs" in text or ".right" in text:
        return ("right", "2")
    return ("", "")


def _clean_call_arg(text: str) -> str:
    value = text.strip()
    if "{" in value:
        value = value.split("{", 1)[0].strip()
    return value


def _is_liftable_call_arg(value: str) -> bool:
    """Return whether a call argument can be shown in an exlim expression."""
    return bool(re.match(
        r"^[A-Za-z_][A-Za-z0-9_']*(?:\.[A-Za-z_][A-Za-z0-9_']*)*$",
        str(value or "").strip(),
    ))


def _matching_call_arguments(
    call_arguments: list[dict[str, Any]],
    procedure: str,
) -> list[dict[str, Any]]:
    if not procedure:
        return call_arguments
    proc = _proc_tail(_normalize_proc(procedure))
    exact = _normalize_proc(procedure)
    out = []
    for call in call_arguments:
        call_proc = _normalize_proc(str(call.get("procedure") or ""))
        if not call_proc:
            continue
        call_tail = _proc_tail(call_proc)
        if call_proc == exact or (proc and call_tail == proc):
            out.append(call)
    return out


def _value_slot_ordinal(slot: dict[str, Any], all_slots: list[dict[str, Any]]) -> int:
    ordinal = 0
    target_index = int(slot.get("index") or 0)
    for item in all_slots:
        if str(item.get("kind") or "") != "value_arg":
            continue
        ordinal += 1
        if int(item.get("index") or 0) == target_index:
            return ordinal
    return 0


def _value_aliases(name: str) -> set[str]:
    clean = str(name or "").strip()
    aliases = {clean} if clean else set()
    stem = re.sub(r"\d+$", "", clean)
    if stem and stem != clean:
        aliases.add(stem)
    for suffix in ("0", "1", "2"):
        if clean.endswith(suffix) and len(clean) > len(suffix):
            aliases.add(clean[:-len(suffix)])
    return {alias for alias in aliases if alias}


def _value_matches_slot(candidate: str, name: str, aliases: set[str]) -> bool:
    cand = str(candidate or "").strip()
    if not cand:
        return False
    return cand == name or cand in aliases


def _all_positional_value_args_match(
    args: list[str],
    slot_names: list[str],
) -> bool:
    if not args or len(args) != len(slot_names):
        return False
    for arg, slot_name in zip(args, slot_names):
        if not _value_matches_slot(arg, slot_name, _value_aliases(slot_name)):
            return False
    return True


def _positional_value_args_have_binding_evidence(
    args: list[str],
    slot_names: list[str],
) -> bool:
    if _all_positional_value_args_match(args, slot_names):
        return True
    # Dotted state expressions such as RO.m rarely share names with logical
    # lemma binders, but they are exactly the expressions EC can lift with
    # `exlim RO.m{1} => mr0`.  Keep this positional match medium-confidence and
    # prover-facing, not a verified call.
    return bool(args and len(args) == len(slot_names) and any("." in arg for arg in args))


def _module_shape_candidates(
    *,
    slot_name: str,
    declaration: str,
    goal_texts: list[str],
) -> list[dict[str, Any]]:
    """Infer module arguments by matching lemma Pr skeletons to the goal.

    Example: a signature body containing ``MainD(D,RO)`` and a current goal
    containing ``MainD(G2,RO)`` gives the binding ``D := G2``.  This is a
    generic applicative-module shape match, not a PROM/ChaChaPoly rule.
    """
    if not slot_name or not declaration or not goal_texts:
        return []
    decl_apps = _application_mentions(declaration)
    goal_apps = [
        app for text in goal_texts for app in _application_mentions(text)
    ]
    candidates: list[dict[str, Any]] = []
    for decl in decl_apps:
        args = _list(decl.get("arguments"))
        if slot_name not in args:
            continue
        slot_index = args.index(slot_name)
        key = _application_key(str(decl.get("callee") or ""))
        if not key:
            continue
        for goal in goal_apps:
            if _application_key(str(goal.get("callee") or "")) != key:
                continue
            goal_args = [
                str(arg) for arg in _list(goal.get("arguments")) if str(arg)
            ]
            if slot_index >= len(goal_args):
                continue
            if not _sibling_args_compatible(args, goal_args, slot_index):
                continue
            value = _clean_module_expr(goal_args[slot_index])
            if not value:
                continue
            candidates.append({
                "value": value,
                "source": "parsed_goal.module_shape",
                "confidence": "high",
                "reason": (
                    f"lemma declaration application `{decl.get('callee')}` "
                    f"uses module slot `{slot_name}` where the current goal "
                    f"uses `{value}`"
                ),
            })
    return _dedupe_candidates(candidates)


def _value_shape_candidates(
    slot: dict[str, Any],
    *,
    declaration: str,
    goal_texts: list[str],
) -> list[dict[str, Any]]:
    """Infer value/predicate arguments by comparing Pr application shapes."""
    name = str(slot.get("name") or "")
    if not name or not declaration or not goal_texts:
        return []
    candidates: list[dict[str, Any]] = []
    decl_apps = _application_mentions(declaration)
    goal_apps = [
        app for text in goal_texts for app in _application_mentions(text)
    ]
    for decl in decl_apps:
        args = [str(arg) for arg in _list(decl.get("arguments")) if str(arg)]
        if name not in args:
            continue
        slot_index = args.index(name)
        key = _application_key(str(decl.get("callee") or ""))
        if not key:
            continue
        for goal in goal_apps:
            if _application_key(str(goal.get("callee") or "")) != key:
                continue
            goal_args = [
                str(arg) for arg in _list(goal.get("arguments")) if str(arg)
            ]
            if slot_index < len(goal_args):
                value = _clean_value_expr(goal_args[slot_index])
                if value:
                    candidates.append({
                        "value": value,
                        "source": "parsed_goal.pr_application_shape",
                        "confidence": "high",
                        "reason": (
                            f"lemma declaration application `{decl.get('callee')}` "
                            f"uses value slot `{name}` where the current goal "
                            f"uses `{value}`"
                        ),
                    })
            elif (
                len(args) == 1
                and not goal_args
                and _slot_has_unit_type(slot, declaration, name)
            ):
                candidates.append({
                    "value": "()",
                    "source": "parsed_goal.pr_application_shape.type_checked",
                    "confidence": "high",
                    "reason": (
                        f"lemma declaration calls `{decl.get('callee')}` with "
                        f"unit-typed value slot `{name}`, while the current "
                        "goal uses EasyCrypt no-argument procedure syntax"
                    ),
                })

    type_or_bound = str(slot.get("type_or_bound") or "")
    if "-> bool" in type_or_bound and _declaration_uses_predicate_on_res(
        declaration,
        name,
    ) and any(_goal_event_is_res(text) for text in goal_texts):
        candidates.append({
            "value": "(fun x => x)",
            "source": "parsed_goal.pr_event_predicate",
            "confidence": "medium",
            "reason": (
                f"predicate slot `{name}` is applied to `res` in the lemma, "
                "and the current Pr event is `res`; bind it to the identity predicate"
            ),
            "post_rewrite_simplification": True,
        })
    return _dedupe_candidates(candidates)


def _slot_has_unit_type(
    slot: dict[str, Any],
    declaration: str,
    name: str,
) -> bool:
    """Return True only with explicit evidence that a value slot is unit.

    Shape alone is not enough.  A lemma template may contain ``proc(x)`` while
    a concrete endpoint prints ``proc()`` for reasons unrelated to the value
    argument.  We only synthesize ``x := ()`` when name resolution or the raw
    declaration gives explicit type evidence such as ``(x : unit)``.
    """
    typ = _clean_type(str(slot.get("type_or_bound") or ""))
    if typ == "unit":
        return True
    if not name:
        return False
    pattern = re.compile(
        rf"[\(\s]\s*{re.escape(name)}\s*:\s*unit\b"
    )
    return bool(pattern.search(str(declaration or "")))


def _clean_type(value: str) -> str:
    return re.sub(r"\s+", "", str(value or "").strip())


def _normalize_proc(proc: str) -> str:
    return _procedure_exact_key(proc, strip_outer=False)


def _application_mentions(text: str) -> list[dict[str, Any]]:
    mentions: list[dict[str, Any]] = []
    value = str(text or "")
    for idx, ch in enumerate(value):
        if ch != "(" or idx == 0:
            continue
        prev = value[idx - 1]
        if not re.match(r"[A-Za-z0-9_'.)]", prev):
            continue
        close_idx = _matching_delimiter(value, idx, "(", ")")
        if close_idx < 0:
            continue
        callee = _scan_callee_before_open(value, idx)
        if not callee:
            continue
        raw_args = value[idx + 1:close_idx]
        args = [
            _clean_value_expr(part)
            for part in _split_top_level_commas(raw_args)
            if _clean_value_expr(part)
        ]
        mentions.append({
            "callee": callee,
            "arguments": args,
        })
    return mentions


def _scan_callee_before_open(text: str, open_idx: int) -> str:
    start = open_idx - 1
    while start >= 0:
        ch = text[start]
        if ch.isspace() or ch in "[]{};:=,+*/<>":
            break
        if ch == "-" and start > 0 and text[start - 1] != ">":
            break
        start -= 1
    return text[start + 1:open_idx].strip()


def _application_key(callee: str) -> str:
    return _procedure_application_key(callee, strip_outer=False)


def _sibling_args_compatible(
    declaration_args: list[Any],
    goal_args: list[str],
    slot_index: int,
) -> bool:
    if len(goal_args) < len(declaration_args):
        return False
    for idx, raw in enumerate(declaration_args):
        if idx == slot_index:
            continue
        decl = _clean_value_expr(str(raw))
        goal = _clean_value_expr(goal_args[idx])
        if not decl or not goal:
            continue
        if _module_value_matches_slot(goal, decl):
            continue
        if decl == "_" or goal == "_":
            continue
        return False
    return True


def _clean_module_expr(value: str) -> str:
    text = _clean_value_expr(value)
    if not text:
        return ""
    if re.match(r"^[A-Z][A-Za-z0-9_'.]*(?:\(.*\))?$", text):
        return text
    return ""


def _clean_value_expr(value: str) -> str:
    text = str(value or "").strip()
    text = re.sub(r"\s+", " ", text)
    return text.rstrip(";")


def _declaration_uses_predicate_on_res(declaration: str, name: str) -> bool:
    return bool(re.search(rf"\b{re.escape(name)}\s+res\b", declaration))


def _goal_event_is_res(text: str) -> bool:
    return bool(re.search(r":\s*res\s*\]", str(text or "")))


def _module_mentions(text: str) -> list[str]:
    out: list[str] = []
    for token in re.findall(
        r"\b[A-Z][A-Za-z0-9_']*(?:\.[A-Z][A-Za-z0-9_']*)+\b",
        text,
    ):
        if token in {"Pr", "Type"}:
            continue
        out.append(token)
    for token in re.findall(r"\b[A-Z][A-Za-z0-9_']*\b", text):
        if token in {"Pr", "Type"}:
            continue
        out.append(token)
    return _dedupe_strings(out)


def _is_value_candidate_source(key: str) -> bool:
    return not (
        ".call_equiv_candidates" in key
        or key.endswith(".goal_type")
        or key.endswith(".procedure")
    )


def _functor_arg_mentions(text: str) -> list[str]:
    out: list[str] = []
    # Keep compound functor arguments as candidates too, e.g. OCC(IFinRO).
    for args in _balanced_functor_args(text):
        if args and re.match(r"^[A-Z][A-Za-z0-9_'.]*(?:\(.*\))?$", args):
            out.append(args)
    return _dedupe_strings(out)


def _balanced_functor_args(text: str) -> list[str]:
    args: list[str] = []
    for idx, ch in enumerate(text):
        if ch != "(" or idx == 0 or not re.match(r"[A-Za-z0-9_'.]", text[idx - 1]):
            continue
        depth = 1
        start = idx + 1
        end = start
        for end in range(start, len(text)):
            if text[end] == "(":
                depth += 1
            elif text[end] == ")":
                depth -= 1
                if depth == 0:
                    piece = text[start:end].strip()
                    if piece and "," not in piece:
                        args.append(piece)
                    break
    return args


def _module_confidence(
    value: str,
    *,
    slot_name: str,
    bound: str,
    module_bound: str,
    source: str,
) -> tuple[str, str]:
    clean_bound = _clean_bound(module_bound)
    if value == slot_name and bound and clean_bound == bound:
        return ("high", f"`{value}` matches the slot name and bound `{bound}`")
    if _module_value_matches_slot(value, slot_name):
        return ("high" if source.startswith("source_context") else "medium",
                f"`{value}` matches the slot name or tail")
    if bound and clean_bound == bound:
        return ("high", f"`{value}` has matching module bound `{bound}`")
    if clean_bound:
        return ("medium", f"`{value}` has declared module bound `{clean_bound}`")
    return ("medium" if source.startswith("source_context") else "low",
            f"`{value}` is visible in current context")


def _module_value_matches_slot(value: str, slot_name: str) -> bool:
    if not value or not slot_name:
        return False
    return value == slot_name or value.rsplit(".", 1)[-1] == slot_name


def _walk_strings(value: Any, prefix: str = "root") -> Iterable[tuple[str, str]]:
    if isinstance(value, str):
        yield (prefix, value)
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from _walk_strings(item, f"{prefix}.{key}")
    elif isinstance(value, list):
        for idx, item in enumerate(value):
            yield from _walk_strings(item, f"{prefix}.{idx}")


def _summary(items: list[dict[str, Any]]) -> dict[str, int]:
    slot_count = sum(len(_list(item.get("slots"))) for item in items)
    bound_count = 0
    for item in items:
        for slot in _list(item.get("slots")):
            if isinstance(slot, dict) and _list(slot.get("candidates")):
                bound_count += 1
    return {
        "items": len(items),
        "slots": slot_count,
        "slots_with_candidates": bound_count,
    }


def _clean_bound(value: str) -> str:
    return re.sub(r"\s+", "", value or "")


def _confidence_rank(confidence: str) -> int:
    return {"high": 0, "medium": 1, "low": 2}.get(confidence, 2)


def _rank_confidence(rank: int) -> str:
    if rank <= 0:
        return "high"
    if rank == 1:
        return "medium"
    return "low"


def _dedupe_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return _dedupe_ranked_by_value(candidates, _candidate_rank)


def _candidate_rank(candidate: dict[str, Any]) -> tuple[int, int, str, str]:
    value = str(candidate.get("value") or "")
    return (
        _confidence_rank(str(candidate.get("confidence") or "low")),
        0 if "." in value else 1,
        str(candidate.get("source") or ""),
        value,
    )


def _dedupe_call_arguments(calls: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, tuple[str, ...]]] = set()
    for call in calls:
        if not isinstance(call, dict):
            continue
        proc = str(call.get("procedure") or "")
        args = tuple(str(arg) for arg in _list(call.get("arguments")) if str(arg))
        key = (proc, args)
        if not proc or key in seen:
            continue
        seen.add(key)
        out.append({
            "procedure": proc,
            "arguments": list(args),
            "side": str(call.get("side") or ""),
            "side_index": str(call.get("side_index") or ""),
            "source": str(call.get("source") or ""),
        })
    return out


__all__ = [
    "INSTANTIATION_BINDING_KIND",
    "INSTANTIATION_BINDING_SCHEMA_VERSION",
    "binding_for_name",
    "build_instantiation_bindings",
]
