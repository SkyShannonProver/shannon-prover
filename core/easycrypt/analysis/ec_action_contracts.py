"""ActionCandidate contract helpers for the EasyCrypt analysis compiler.

The action layer is a compiler backend boundary: facts become inspectable,
candidate, or runnable suggestions here.  These helpers keep that boundary
explicit so fallback source scans and unresolved names cannot silently become
committable proof steps.
"""
from __future__ import annotations

import re
from typing import Any

from core.easycrypt.analysis.ec_utils import (
    as_dict as _dict,
    dedupe_strings as _dedupe,
)


ACTION_CONTRACTS_SCHEMA_VERSION = 1
ACTION_CONTRACTS_KIND = "easycrypt_action_contracts"

INSPECTION_ACTION = "inspection_action"
STRATEGY_HINT = "strategy_hint"
TACTIC_CANDIDATE = "tactic_candidate"
RUNNABLE_TACTIC = "runnable_tactic"
AVOID_ACTION = "avoid_action"

ACTION_TYPES = {
    INSPECTION_ACTION,
    STRATEGY_HINT,
    TACTIC_CANDIDATE,
    RUNNABLE_TACTIC,
    AVOID_ACTION,
}

SCHEDULER_ROLES = {
    "proof_context_intro",
    "semantic_risk_map",
    "semantic_frontier_map",
    "typed_resource_lookup",
    "typed_resource_use",
    "program_frontier_exposure",
    "local_control_transform",
    "probabilistic_vc",
    "candidate_validation",
    "residual_close",
    "fallback_lowering",
    "destructive_lowering",
    "unverified_pivot_background",
    "unknown",
}

READINESS_BY_ACTION_TYPE = {
    INSPECTION_ACTION: "inspect_first",
    STRATEGY_HINT: "not_directly_runnable",
    TACTIC_CANDIDATE: "needs_validation",
    RUNNABLE_TACTIC: "ready_to_run",
    AVOID_ACTION: "do_not_run",
}

EFFECT_BY_ACTION_TYPE = {
    INSPECTION_ACTION: "read_only",
    STRATEGY_HINT: "planning_only",
    TACTIC_CANDIDATE: "candidate_only",
    RUNNABLE_TACTIC: "mutates_proof_state",
    AVOID_ACTION: "avoid",
}

UNRESOLVED_NAME_STATUSES = {
    "needs_where_lookup",
    "in_scope_name_without_signature",
    "source_scope_check_required",
    "source_local_scope_check_required",
}

FALLBACK_AUTHORITIES = {
    "source_scan_fallback",
    "source_scan_not_current_scope",
    "legacy_lookup",
}

LAYER_BY_TACTIC_FAMILY = {
    "ambient_close": "ambient_logic",
    "definition_unfold": "ambient_logic",
    "call_invariant_skeleton": "call_site",
    "call_named_equiv": "call_site",
    "inline_all": "procedure_body",
    "instantiated_template": "resolved_action",
    "intro": "proof_context",
    "native_ast_search": "name_resolution",
    "pr_bridge": "pr",
    "pr_normalization": "pr",
    "pr_path_plan": "pr",
    "probabilistic_vc": "pr",
    "probability_to_program": "pr_lowering",
    "proc_open": "prhl_module",
    "procedure_transform": "procedure_body",
    "rewrite": "pr",
    "signature_lookup": "name_resolution",
    "targeted_inline": "procedure_body",
}

UNBOUND_SLOT_STATUSES = {
    "ambiguous",
    "low_confidence",
    "missing_candidates",
    "needs_binding",
}


# ── fact vs guidance (the compiler pushes state-derived FACTS, not move GUIDANCE) ──
#
# A menu item is a FACT when it is read/derived from the current goal — true
# regardless of strategy: an `Inspect X: <value>` surface-map readout, a
# goal-FILLED tactic (`case: (j=i)`, `rcondt{1} 3`, `while (0 <= j < N)`,
# `call (_: <real-inv>)`), a state-derived opener (`move=> H.`, `proc.`), or a
# resource lookup (`-where L`). It is GUIDANCE when it is a suggestion about HOW
# to prove: a hardcoded bare tactic shape (`wp.`/`sp.`/`sim.`/`byequiv => //.`),
# an un-filled placeholder template (`while (<loop invariant>).`), a route-plan
# (`Probabilistic VC plan…`, `Structured procedure frontier…; primary: use X`),
# or a fill-in template that still needs instantiation. See `tactic="…"`
# (hardcoded) vs `tactic=f"…{state}…"` (state-derived) in
# core/easycrypt/analysis/ec_*_actions.py.
_HARDCODED_BARE_TACTICS = frozenset({
    "wp.", "sp.", "rnd.", "auto.", "auto => />.", "smt().", "skip.", "sim.",
    "if.", "if => //=.", "if => //.", "split.", "sp; if => //=.",
    "rcondf 1; first auto.", "byequiv => //.", "inline *.", "inline{1} 1.",
})

# An UN-FILLED placeholder is `<lowercase prose…>` (`<loop invariant>`,
# `<adversary invariant>`, `<split of 5 <= r>`): a `<` immediately followed by a
# lowercase letter, spanning prose that never contains `{`/`}`. A real less-than is
# `<=`/`< ` (no lowercase right after) so it is not matched; excluding `{`/`}` from
# the span also stops a relational atom (`x{1} <y{2} /\ z{1} >`) from matching across
# to a LATER `>` — relational atoms always carry `{1}`/`{2}`, placeholder prose never
# does. (`<split of 5 <= r>` still matches: its inner `<=` is not a brace.)
_PLACEHOLDER_NOISE_RE = re.compile(r"<[a-z][^>{}]*>")
_SWAP_OFFSET_FRAME_RE = re.compile(
    r"^swap(?:\{[12]\})?\s+(?:\[\d+\.\.\d+\]|\d+)\s+<offset>\.?\s*$"
)
_REALIGNING_SWAP_RE = re.compile(
    r"^(?P<head>swap(?:\{(?P<side>[12])\})?\s+"
    r"(?P<source>\[\d+\.\.\d+\]|\d+))\s+"
    r"(?P<offset>-?\d+)\s*\.?\s*$"
)


def realigning_swap_contract(tactic: str) -> dict[str, Any]:
    """Parse a verified swap once at the compiler action boundary.

    Presentation consumes this typed contract and never recovers source/offset
    structure from tactic prose.
    """
    match = _REALIGNING_SWAP_RE.match(str(tactic or "").strip())
    if not match:
        return {}
    source = match.group("source")
    return {
        "side": match.group("side") or "",
        "source": source,
        "source_position": source if source.isdigit() else "",
        "accepted_offset": int(match.group("offset")),
        "frame": f"{match.group('head')} <offset>.",
    }


def is_hardcoded_noise_move(tactic_text: str) -> bool:
    """True for a hardcoded GENERIC item: an un-filled placeholder template, a
    route-plan / "primary: use X" prose line, or a bare hardcoded tactic shape.
    False for a state-derived fact (a goal-FILLED tactic or an `Inspect …` /
    `-where …` readout)."""
    t = (tactic_text or "").strip()
    if not t:
        return False
    if _PLACEHOLDER_NOISE_RE.search(t) and not _SWAP_OFFSET_FRAME_RE.match(t):
        return True
    if t.startswith(("Probabilistic VC plan", "Structured procedure frontier")) or "; primary:" in t:
        return True
    return t in _HARDCODED_BARE_TACTICS


def classify_info_kind(candidate: dict[str, Any]) -> str:
    """Classify a menu item ``"fact"`` vs ``"guidance"``.

    GUIDANCE is hardcoded move advice the compiler must not push: a bare tactic
    shape / placeholder / route-plan (`is_hardcoded_noise_move`), or a strategy
    fill-in TEMPLATE still carrying `requires_instantiation`. A daemon-VERIFIED
    item is always a FACT (a real provenance fact, even when bare like `wp.`).
    The `requires_instantiation` drop is gated on the strategy bucket — a typed
    resource lookup that merely needs a `-where` first is a fact, not a
    template."""
    if candidate.get("verified"):
        return "fact"
    if is_hardcoded_noise_move(str(candidate.get("tactic") or "")):
        return "guidance"
    if str(candidate.get("action_type") or "") == STRATEGY_HINT:
        factors = candidate.get("cost_factors")
        factors = factors if isinstance(factors, dict) else {}
        if candidate.get("requires_instantiation") or factors.get("requires_instantiation"):
            return "guidance"
    return "fact"


def normalize_action_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    """Return a copy with stable readiness/effect/provenance fields."""
    item = dict(candidate) if isinstance(candidate, dict) else {}
    explicit_layer = item.get("layer")
    for derived_key in (
        "abstraction_preservation",
        "generated_obligations",
        "live_resource_loss",
        "missing_slots",
        "obligation_completeness",
        "phase_legality",
        "scheduler",
        "typed_readiness",
    ):
        item.pop(derived_key, None)
    if explicit_layer:
        item["layer"] = explicit_layer
    action_type = str(item.get("action_type") or "")
    if action_type not in ACTION_TYPES:
        action_type = STRATEGY_HINT
        item["action_type"] = action_type
    item.setdefault("readiness", READINESS_BY_ACTION_TYPE[action_type])
    item.setdefault("effect", EFFECT_BY_ACTION_TYPE[action_type])
    item.setdefault("preconditions", [])
    item.setdefault("preserves", [])
    item.setdefault("destroys", [])
    item.setdefault("cost_factors", {})
    item.setdefault("confidence", "medium")
    # FACT vs GUIDANCE — recomputed (not setdefault) so it always reflects the
    # FINAL tactic, even after the candidate pipeline fills/rewrites a template.
    item["info_kind"] = classify_info_kind(item)
    item.setdefault("provenance", _candidate_provenance(item))
    item.setdefault("authority", str(_dict(item.get("provenance")).get("authority") or "analysis"))
    item.setdefault(
        "authority_rank",
        int(_dict(item.get("provenance")).get("authority_rank") or 0),
    )
    item.setdefault("layer", _candidate_layer(item))
    item.setdefault("phase_legality", _phase_legality(item))
    item.setdefault("typed_readiness", _typed_readiness(item))
    item.setdefault("missing_slots", _missing_slots(item))
    item.setdefault("generated_obligations", _generated_obligations(item))
    item.setdefault("obligation_completeness", _obligation_completeness(item))
    item.setdefault("live_resource_loss", _live_resource_loss(item))
    item.setdefault("abstraction_preservation", _abstraction_preservation(item))
    item.setdefault("scheduler_role", _scheduler_role(item))
    item.setdefault("scheduler", _scheduler_contract(item))
    errors = validate_action_candidate(item)
    if errors:
        item["contract_errors"] = errors
    return item


def normalize_action_candidates(candidates: list[Any]) -> list[dict[str, Any]]:
    return [
        normalize_action_candidate(candidate)
        for candidate in candidates
        if isinstance(candidate, dict)
    ]


def validate_action_candidate(candidate: dict[str, Any]) -> list[str]:
    if not isinstance(candidate, dict):
        return ["candidate must be a dictionary"]
    errors: list[str] = []
    action_type = str(candidate.get("action_type") or "")
    if action_type not in ACTION_TYPES:
        errors.append(f"invalid action_type: {action_type or '<missing>'}")
    if not str(candidate.get("id") or ""):
        errors.append("missing id")
    if not str(candidate.get("tactic") or ""):
        errors.append("missing tactic")
    if not str(candidate.get("tactic_family") or ""):
        errors.append("missing tactic_family")
    if not isinstance(candidate.get("preconditions"), list):
        errors.append("preconditions must be a list")
    if not str(candidate.get("layer") or ""):
        errors.append("missing layer")
    if not str(candidate.get("typed_readiness") or ""):
        errors.append("missing typed_readiness")
    if not str(candidate.get("obligation_completeness") or ""):
        errors.append("missing obligation_completeness")
    if str(candidate.get("scheduler_role") or "") not in SCHEDULER_ROLES:
        errors.append(
            f"invalid scheduler_role: {candidate.get('scheduler_role') or '<missing>'}"
        )
    if _fallback_or_unresolved(candidate) and action_type in {
        TACTIC_CANDIDATE,
        RUNNABLE_TACTIC,
    }:
        errors.append(
            "fallback or unresolved resource cannot be a tactic candidate/runnable before inspection"
        )
    return errors


def _candidate_provenance(candidate: dict[str, Any]) -> dict[str, Any]:
    factors = _dict(candidate.get("cost_factors"))
    source = str(
        candidate.get("source")
        or factors.get("source")
        or factors.get("fact_source")
        or "analysis"
    )
    authority = str(
        candidate.get("authority")
        or factors.get("authority")
        or "analysis"
    )
    return {
        "source": source,
        "authority": authority,
        "authority_rank": _authority_rank(candidate, factors, authority, source),
        "ec_ground_truth": bool(
            candidate.get("ec_ground_truth")
            or factors.get("ec_ground_truth")
        ),
    }


def _authority_rank(
    candidate: dict[str, Any],
    factors: dict[str, Any],
    authority: str,
    source: str,
) -> int:
    raw = candidate.get("authority_rank") or factors.get("authority_rank")
    if raw is not None:
        try:
            return int(raw)
        except (TypeError, ValueError):
            pass
    if bool(candidate.get("ec_ground_truth") or factors.get("ec_ground_truth")):
        return 100
    if authority == "ec_native_ground_truth":
        return 100
    if authority in {"where_lookup_tool", "signature_lookup_tool"}:
        return 80
    if source in {"current_goal_hypothesis", "local_context"}:
        return 60
    if authority == "pretty_text_fallback":
        return 10
    if authority in FALLBACK_AUTHORITIES:
        return 0
    return 20


def _candidate_layer(candidate: dict[str, Any]) -> str:
    explicit = str(candidate.get("layer") or "")
    if explicit:
        return explicit
    factor_layer = str(_dict(candidate.get("cost_factors")).get("layer") or "")
    if factor_layer:
        return factor_layer
    return LAYER_BY_TACTIC_FAMILY.get(
        str(candidate.get("tactic_family") or ""),
        "unknown",
    )


def _phase_legality(candidate: dict[str, Any]) -> str:
    legality = _dict(candidate.get("legality"))
    status = str(legality.get("status") or "")
    if status:
        return status
    if str(candidate.get("action_type") or "") == AVOID_ACTION:
        return "avoid"
    return "allowed"


def _typed_readiness(candidate: dict[str, Any]) -> str:
    action_type = str(candidate.get("action_type") or "")
    factors = _dict(candidate.get("cost_factors"))
    status = str(
        factors.get("instantiation_binding_status")
        or factors.get("name_resolution_status")
        or factors.get("resolution_status")
        or ""
    )
    if action_type == AVOID_ACTION:
        return "blocked"
    if action_type == INSPECTION_ACTION:
        return "needs_inspection"
    if _missing_slots(candidate):
        return "missing_slots"
    if (
        str(candidate.get("tactic_family") or "") == "call_named_equiv"
        and (
            factors.get("requires_cut_to_frontier")
            or factors.get("callable_now") is False
        )
    ):
        return "frontier_not_ready"
    if status in UNRESOLVED_NAME_STATUSES:
        return "needs_inspection"
    if status in UNBOUND_SLOT_STATUSES:
        return "missing_slots"
    if action_type == STRATEGY_HINT:
        return "semantic_only"
    if factors.get("instantiated_template_count") or status == "has_candidates":
        return "typed_candidate"
    if bool(factors.get("exact_signature_known")):
        return "typed_candidate"
    if action_type == RUNNABLE_TACTIC:
        return "ready"
    if action_type == TACTIC_CANDIDATE:
        return "needs_validation"
    return "unknown"


def _missing_slots(candidate: dict[str, Any]) -> list[str]:
    factors = _dict(candidate.get("cost_factors"))
    out: list[str] = []
    for key in (
        "missing_slots",
        "missing_arguments",
        "unresolved_slots",
        "unbound_slots",
    ):
        value = candidate.get(key, factors.get(key))
        if isinstance(value, list):
            out.extend(str(item) for item in value if str(item))
        elif isinstance(value, str) and value:
            out.append(value)
    return _dedupe(out)


def _generated_obligations(candidate: dict[str, Any]) -> list[str]:
    factors = _dict(candidate.get("cost_factors"))
    out: list[str] = []
    for key in (
        "generated_obligations",
        "oracle_obligations",
        "remaining_obligations",
    ):
        value = candidate.get(key, factors.get(key))
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    label = str(
                        item.get("kind")
                        or item.get("lemma")
                        or item.get("id")
                        or ""
                    )
                    if label:
                        out.append(label)
                elif str(item):
                    out.append(str(item))
        elif isinstance(value, str) and value:
            out.append(value)
    return _dedupe(out)


def _obligation_completeness(candidate: dict[str, Any]) -> str:
    explicit = str(candidate.get("obligation_completeness") or "")
    if explicit:
        return explicit
    factors = _dict(candidate.get("cost_factors"))
    explicit = str(factors.get("obligation_completeness") or "")
    if explicit:
        return explicit
    path_status = str(factors.get("path_status") or "")
    if path_status == "complete":
        return "complete"
    if path_status and path_status != "complete":
        return "partial"
    if _generated_obligations(candidate):
        if bool(factors.get("obligation_closure_plan_complete")):
            return "complete"
        return "partial"
    if str(candidate.get("action_type") or "") == STRATEGY_HINT:
        return "not_applicable"
    return "complete"


def _live_resource_loss(candidate: dict[str, Any]) -> int:
    factors = _dict(candidate.get("cost_factors"))
    for key in ("live_resource_loss", "lost_handles", "lost_callable_lemmas"):
        value = candidate.get(key, factors.get(key))
        try:
            return max(0, int(value))
        except (TypeError, ValueError):
            continue
    destroys = candidate.get("destroys")
    return len(destroys) if isinstance(destroys, list) else 0


def _abstraction_preservation(candidate: dict[str, Any]) -> str:
    if _live_resource_loss(candidate):
        return "destroys_live_resources"
    family = str(candidate.get("tactic_family") or "")
    if family in {"inline_all", "probability_to_program", "proc_open"}:
        return "lowers_abstraction"
    if family in {
        "call_invariant_skeleton",
        "call_named_equiv",
        "intro",
        "native_ast_search",
        "definition_unfold",
        "pr_normalization",
        "pr_path_plan",
        "rewrite",
        "signature_lookup",
    }:
        return "preserves_abstraction"
    if family in {"procedure_transform", "targeted_inline"}:
        return "local_lowering"
    return "unknown"


def _scheduler_role(candidate: dict[str, Any]) -> str:
    explicit = str(candidate.get("scheduler_role") or "")
    if explicit in SCHEDULER_ROLES:
        return explicit
    factors = _dict(candidate.get("cost_factors"))
    explicit = str(factors.get("scheduler_role") or "")
    if explicit in SCHEDULER_ROLES:
        return explicit
    family = str(candidate.get("tactic_family") or "")
    action_type = str(candidate.get("action_type") or "")
    tactic = str(candidate.get("tactic") or "").strip()
    if action_type == AVOID_ACTION or family == "inline_all":
        return "destructive_lowering"
    if family == "intro":
        return "proof_context_intro"
    if family in {"signature_lookup", "native_ast_search"}:
        return "typed_resource_lookup"
    if family in {
        "call_named_equiv",
        "instantiated_template",
        "pr_bridge",
        "pr_normalization",
        "pr_path_plan",
        "rewrite",
    }:
        return "typed_resource_use"
    if family == "probabilistic_vc":
        return "probabilistic_vc"
    if family in {"probability_to_program", "proc_open"}:
        return "fallback_lowering"
    if family in {"ambient_close", "definition_unfold"}:
        return "residual_close"
    if family == "call_invariant_skeleton":
        return "typed_resource_use"
    if family == "targeted_inline":
        return (
            "program_frontier_exposure"
            if factors.get("program_action_kind") else
            "fallback_lowering"
        )
    if family == "procedure_transform":
        head = tactic.split(None, 1)[0].rstrip(".") if tactic else ""
        if head in {"sim"}:
            return "low_precision_candidate"
        if head in {"skip", "auto", "smt"}:
            return "residual_close"
        if (
            factors.get("program_action_kind")
            or factors.get("program_plan_kind")
            or factors.get("frontier_blocker_kinds")
            or factors.get("loop_invariant_conjuncts")
        ):
            return "program_frontier_exposure"
        if (
            factors.get("result_expression_map")
            or factors.get("asymmetric_instrumentation_region")
            or _dict(factors.get("region")).get("kind")
            == "asymmetric_instrumentation_region"
        ):
            return "semantic_risk_map"
        if head in {
            "case:",
            "case",
            "conseq",
            "if",
            "rcondf",
            "rcondt",
            "rnd",
            "splitwhile",
            "swap",
            "while",
        }:
            return "local_control_transform"
        if (
            factors.get("frontier_kind")
            or factors.get("one_sided_call_site_summary")
            or factors.get("region_summary")
        ):
            return "semantic_frontier_map"
        if head in {"wp", "sp", "seq"}:
            return "program_frontier_exposure"
        return "local_control_transform"
    return "unknown"


def _scheduler_contract(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "layer": str(candidate.get("layer") or _candidate_layer(candidate)),
        "phase_legality": str(
            candidate.get("phase_legality") or _phase_legality(candidate)
        ),
        "authority_rank": int(candidate.get("authority_rank") or 0),
        "typed_readiness": str(
            candidate.get("typed_readiness") or _typed_readiness(candidate)
        ),
        "missing_slots": list(candidate.get("missing_slots") or []),
        "obligation_completeness": str(
            candidate.get("obligation_completeness")
            or _obligation_completeness(candidate)
        ),
        "generated_obligations": list(
            candidate.get("generated_obligations") or []
        ),
        "abstraction_preservation": str(
            candidate.get("abstraction_preservation")
            or _abstraction_preservation(candidate)
        ),
        "live_resource_loss": int(candidate.get("live_resource_loss") or 0),
        "scheduler_role": str(
            candidate.get("scheduler_role") or _scheduler_role(candidate)
        ),
    }


def _fallback_or_unresolved(candidate: dict[str, Any]) -> bool:
    provenance = _dict(candidate.get("provenance"))
    factors = _dict(candidate.get("cost_factors"))
    authority = str(
        provenance.get("authority")
        or candidate.get("authority")
        or factors.get("authority")
        or ""
    )
    source = str(
        provenance.get("source")
        or candidate.get("source")
        or factors.get("source")
        or factors.get("fact_source")
        or ""
    )
    status = str(
        factors.get("name_resolution_status")
        or factors.get("resolution_status")
        or ""
    )
    return (
        authority in FALLBACK_AUTHORITIES
        or source in {"source_scan_out_of_context", "source_file_out_of_context"}
        or status in UNRESOLVED_NAME_STATUSES
    )


__all__ = [
    "ACTION_CONTRACTS_KIND",
    "ACTION_CONTRACTS_SCHEMA_VERSION",
    "ACTION_TYPES",
    "AVOID_ACTION",
    "INSPECTION_ACTION",
    "TACTIC_CANDIDATE",
    "RUNNABLE_TACTIC",
    "SCHEDULER_ROLES",
    "STRATEGY_HINT",
    "classify_info_kind",
    "is_hardcoded_noise_move",
    "normalize_action_candidate",
    "normalize_action_candidates",
    "validate_action_candidate",
]
