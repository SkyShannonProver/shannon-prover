"""PASS 4 — the action surface (§3.4): the read-only candidate menu,
phase guidance/legality and diagnostics built over a frozen handles dict.

Carved out of ec_proof_ir.py (the 56 funcs reachable ONLY from the action-
surface entries). It imports only the sibling analysis modules + ec_proof_ir_util
that the moved funcs actually use, and it does NOT import ec_proof_ir, so there
is no cycle; ec_proof_ir re-exports this module's own defs, so build_proof_ir +
consumers see them at the same path unchanged.
"""
from __future__ import annotations

import re
from typing import Any

# Pure leaf utilities live in ec_proof_ir_util now (carve step: break the
# import cycle for per-pass modules); the leaves this module's passes use are
# imported below.
from core.easycrypt.analysis.ec_proof_ir_util import (
    _legality,
    _call_handle_candidate_kind,
    _program_edit_script_action,
    _instantiation_missing_slot_labels,
    _candidate_names,
    _candidate_lemma_name,
    _lemma_leaf,
    _compact_pr_elaboration,
    _dict,
    _list,
    _dedupe_strings,
    _CALL_NAME_LOOKUP_REQUIRED_STATUSES,
)

from core.easycrypt.analysis.ec_proof_ir_liveness import (
    _apply_candidate_pipeline,
)

from core.easycrypt.analysis.ec_action_contracts import (
    normalize_action_candidates,
)

from core.easycrypt.analysis.ec_instantiation_binding import (
    binding_for_name,
)
from core.easycrypt.analysis.ec_name_resolution import (
    resolution_for_name,
)
from core.easycrypt.analysis.ec_menu_actions import (
    ambient_named_closer_menu_items as build_ambient_named_closer_menu_items,
    menu_item as build_menu_item,
    native_ast_search_menu_items as build_native_ast_search_menu_items,
    safe_id as _safe_id,
    semantic_pr_bound_menu_items as build_semantic_pr_bound_menu_items,
)
from core.easycrypt.analysis.ec_pr_actions import (
    pr_byequiv_fallback_menu_items as build_pr_byequiv_fallback_menu_items,
    pr_clone_bound_apply_menu_items as build_pr_clone_bound_apply_menu_items,
    pr_decomposition_bridge_menu_items as build_pr_decomposition_bridge_menu_items,
    pr_normalization_menu_items as build_pr_normalization_menu_items,
    pr_rewrite_menu_items as build_pr_rewrite_menu_items,
    resolution_preconditions,
    visible_pr_rewrites as build_visible_pr_rewrites,
)
from core.easycrypt.analysis.ec_procedure_actions import (
    call_site_prefix_menu_items as build_call_site_prefix_menu_items,
    procedure_body_menu_items as build_procedure_body_menu_items,
    procedure_entry_fallback_menu_items as build_procedure_entry_fallback_menu_items,
    procedure_frontier_plan_menu_items as build_procedure_frontier_plan_menu_items,
    procedure_surface_map_menu_items as build_procedure_surface_map_menu_items,
    sampling_ordering_diagnostics as build_sampling_ordering_diagnostics,
)


def _while_invariant_tactic_hint(handles: dict[str, Any]) -> str:
    skeleton = _dict(handles.get("invariant_skeleton"))
    invariant = str(skeleton.get("suggested_invariant") or "").strip()
    if invariant and len(invariant) <= 220 and not _invariant_looks_noisy(invariant):
        return invariant
    return "<loop invariant from live variables>"


def _phase_guidance(
    layer: str,
    goal_kind: str,
    liveness: dict[str, Any],
    handles: dict[str, Any],
) -> dict[str, Any]:
    live_calls = int(liveness.get("live_call_site_count") or 0)
    live_lemmas = int(liveness.get("live_callable_lemma_count") or 0)
    callable_now = int(liveness.get("callable_now_lemma_count") or 0)
    non_frontier = int(liveness.get("non_frontier_callable_lemma_count") or 0)
    oracle_obligations = int(liveness.get("oracle_obligation_handle_count") or 0)
    # `prefer`/`avoid` (phase preference/avoid prose) and the
    # `pr_obligation_primary_strategy` recommendation are removed — the phase
    # carries only the FACTUAL resource counts/flags now (view boundary: no
    # "which move to prefer / avoid" guidance).
    return {
        "name": layer,
        "goal_kind": goal_kind,
        "resource_summary": {
            "live_call_sites": live_calls,
            "frontier_call_sites": int(liveness.get("frontier_call_site_count") or 0),
            "live_callable_lemmas": live_lemmas,
            "callable_now_lemmas": callable_now,
            "non_frontier_callable_lemmas": non_frontier,
            "oracle_obligation_handles": oracle_obligations,
            "pr_rewrite_candidates": len(_list(handles.get("pr_rewrite_candidates"))),
            "native_ast_search_queries": len(
                _list(_dict(handles.get("native_ast_search")).get("suggested_queries"))
            ),
            "native_ast_search_hits": len(
                _list(_dict(handles.get("native_ast_search")).get("hits"))
            ),
            "has_probabilistic_vc_frontend": bool(
                _dict(handles.get("probabilistic_vc_frontend")).get("available")
            ),
            "has_pr_normal_form": bool(
                _dict(handles.get("pr_normal_form")).get("available")
            ),
            "pr_path_complete_paths": int(
                _dict(_dict(handles.get("pr_path_plan")).get("summary")).get(
                    "complete_path_count"
                ) or 0
            ),
            "has_pr_arithmetic_plan": bool(
                _dict(_dict(handles.get("pr_path_plan")).get("arithmetic_plan")).get(
                    "available"
                )
                or _dict(_dict(handles.get("pr_path_plan")).get("arithmetic_plan")).get(
                    "shape"
                )
            ),
            "has_pr_obligation_plan": bool(
                _dict(handles.get("pr_obligation_plan")).get("available")
            ),
            "has_invariant_skeleton": bool(
                _dict(handles.get("invariant_skeleton")).get("suggested_invariant")
            ),
            "name_resolution": _dict(
                _dict(handles.get("name_resolution")).get("summary")
            ),
            "unfoldable_goal_heads": _list(
                handles.get("unfoldable_goal_heads")
            )[:6],
            "unfoldable_goal_head_count": len(
                _list(handles.get("unfoldable_goal_heads"))
            ),
        },
    }


def _phase_legality(
    layer: str,
    liveness: dict[str, Any],
    handles: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Return the phase legality table for known tactic families."""
    live_calls = int(liveness.get("live_call_site_count") or 0)
    live_lemmas = int(liveness.get("live_callable_lemma_count") or 0)
    callable_now = int(liveness.get("callable_now_lemma_count") or 0)
    non_frontier = int(liveness.get("non_frontier_callable_lemma_count") or 0)
    oracle_obligations = int(liveness.get("oracle_obligation_handle_count") or 0)
    live_handles = live_calls + live_lemmas
    table = {
        "intro": _legality("allowed", "Introductions expose binders/premises without lowering proof resources."),
        "probability_to_program": _legality("allowed", "Probability-to-program openers are legal at Pr layer."),
        "pr_normalization": _legality("allowed", "Pr normalization preserves the probability layer."),
        "rewrite": _legality("allowed", "Rewrites are generally local proof transformations."),
        "pr_bridge": _legality("allowed", "Pr bridges preserve the probability layer."),
        "pr_path_plan": _legality("allowed", "Pr path planning preserves the probability layer."),
        "probabilistic_vc": _legality("allowed", "Probabilistic VC planning classifies loss-accounting obligations without mutating proof state."),
        "signature_lookup": _legality("allowed", "Signature lookup is read-only name resolution."),
        "native_ast_search": _legality("allowed", "EasyCrypt native AST search is read-only lemma retrieval."),
        "instantiated_template": _legality(
            "allowed",
            "Typed instantiation templates are read-only candidates until probed.",
        ),
        "call_named_equiv": _legality("allowed", "Named calls preserve procedure abstraction."),
        "call_invariant_skeleton": _legality("allowed", "Invariant calls preserve call-site structure."),
        "proc_open": _legality("allowed", "`proc` exposes the program body without expanding inner calls."),
        "targeted_inline": _legality("allowed", "Targeted inline lowers one chosen wrapper."),
        "inline_all": _legality("allowed", "Global inline is legal when no higher-level handles are live."),
        "procedure_transform": _legality("allowed", "Procedure transforms are legal after bodies are exposed."),
        "ambient_close": _legality("allowed", "Ambient closers are legal on residual logic."),
        "unknown": _legality("allowed", "Unknown tactic family; defer to producer epistemics."),
    }
    if layer == "pr":
        table["intro"] = _legality("preferred", "Introduce visible binders/premises before choosing a Pr tactic.")
        table["pr_normalization"] = _legality(
            "preferred",
            "Current layer is Pr; normalization is useful when it simplifies the visible Pr shell.",
        )
        table["probability_to_program"] = _legality("preferred", "Current layer is Pr; byequiv/byphoare/bypr are valid routes when the goal is naturally program-facing.")
        table["rewrite"] = _legality("preferred", "Current layer is Pr; rewrite/bridge handles are route context when endpoints match.")
        table["pr_bridge"] = _legality("preferred", "Current layer is Pr; bridge lemmas preserve abstraction.")
        table["pr_path_plan"] = _legality(
            "preferred",
            "Current layer is Pr; a planned Pr path is relevant while its next hop matches the current endpoint.",
        )
        table["probabilistic_vc"] = _legality(
            "preferred",
            "Current layer is Pr; loss-accounting VC planning preserves the probability layer.",
        )
        table["signature_lookup"] = _legality("preferred", "Resolve lemma arity before using cross-file Pr handles.")
        table["native_ast_search"] = _legality(
            "preferred",
            "Use EC native AST search when Pr/real-order lemma shape is the missing context.",
        )
        table["instantiated_template"] = _legality(
            "preferred",
            "A typed template has current-context bindings; probe it when the template matches the visible endpoint.",
        )
        table["call_named_equiv"] = _legality("avoid", "No pRHL call site is exposed at Pr layer.")
        table["proc_open"] = _legality("avoid", "No program judgment is exposed at Pr layer.")
        table["targeted_inline"] = _legality("avoid", "Procedure bodies are not exposed at Pr layer.")
        table["inline_all"] = _legality("avoid", "Global inline may hide Pr-level route context.")
        table["procedure_transform"] = _legality("avoid", "Procedure transforms require exposed bodies.")
        table["ambient_close"] = _legality(
            "avoid",
            "Ambient closers fit residual logic, not unresolved Pr endpoint structure.",
        )
    elif layer == "prhl_module":
        table["pr_normalization"] = _legality("avoid", "Pr normalization applies at the probability layer, not after pRHL is open.")
        table["proc_open"] = _legality("preferred", "`proc` exposes call sites before lower-level proof passes.")
        table["call_named_equiv"] = _legality("allowed", "Run `proc`/alignment first if call sites are not yet exposed.")
        table["inline_all"] = _legality("avoid", "At module layer, global inline may skip call-site analysis.")
        table["procedure_transform"] = _legality("avoid", "Procedure transforms require exposed bodies.")
    elif layer == "procedure_entry":
        table["pr_normalization"] = _legality("avoid", "Pr normalization only applies at probability layer.")
        table["proc_open"] = _legality("preferred", "`proc` is the phase opener for one-sided procedure judgments.")
        table["probabilistic_vc"] = _legality(
            "allowed",
            "The probabilistic VC plan is read-only context; expose the body with `proc` before executing body tactics.",
        )
        table["procedure_transform"] = _legality("avoid", "Expose the procedure body with `proc` before wp/sp/seq/rnd.")
        table["call_named_equiv"] = _legality("avoid", "No pRHL call-site pair is exposed before `proc`.")
        table["inline_all"] = _legality("avoid", "Avoid global inline before the procedure body is explicitly opened.")
    elif layer == "call_site":
        table["proc_open"] = _legality("avoid", "The proof is already below `proc`; another `proc` is usually a no-op.")
        table["call_named_equiv"] = _legality(
            "allowed" if oracle_obligations else ("preferred" if callable_now else "allowed"),
            (
                "A named equiv is at EasyCrypt's last-call frontier."
                if callable_now and not oracle_obligations else
                "Some named equiv handles are oracle obligations produced by the current adversary frontier."
                if oracle_obligations else
                "Named equivs preserve abstraction, but a matching call may need to be exposed first."
            ),
        )
        table["instantiated_template"] = _legality(
            "preferred",
            "A typed template keeps the candidate at the current call-site phase until EC probes it.",
        )
        table["signature_lookup"] = _legality("preferred", "Resolve call lemma signature before guessing arguments.")
        table["call_invariant_skeleton"] = _legality(
            "preferred"
            if (
                _dict(handles.get("adversary_invariant_skeleton")).get("available")
                or _dict(handles.get("invariant_skeleton")).get("available")
            ) else
            "allowed",
            (
                "The current frontier is an adversary call; an invariant call generates oracle obligations."
                if oracle_obligations else
                "Invariant call stays at call-site layer."
            ),
        )
        table["targeted_inline"] = _legality("allowed", "Targeted inline lowers one wrapper while preserving unrelated handles.")
        if live_handles:
            table["inline_all"] = _legality(
                "avoid",
                (
                    f"Global inline would erase {live_calls} live call site(s) "
                    f"and {live_lemmas} callable lemma handle(s); use frontier "
                    "call lemmas, targeted inline, wp, or seq first."
                ),
            )
        else:
            table["inline_all"] = _legality("allowed", "No live call handles are visible.")
        if _dict(handles.get("program_edit_script_action")).get("tactic_hint"):
            table["procedure_transform"] = _legality(
                "preferred",
                (
                    "ProgramIR edit script has a concrete wp/seq alignment "
                    "action; use it to expose the next program slice before "
                    "lowering further."
                ),
            )
        else:
            table["procedure_transform"] = (
                _legality(
                    "preferred",
                    "A live call lemma is not yet at the last-call frontier; use wp/seq to expose it before calling.",
                )
                if non_frontier and not callable_now else
                _legality("avoid", "Work at call-site layer before procedure transforms.")
            )
    elif layer == "procedure_body":
        table["proc_open"] = _legality("avoid", "The procedure body is already exposed.")
        table["probabilistic_vc"] = _legality(
            "preferred",
            "Procedure bodies are exposed; probabilistic VC planning summarizes bound obligations before local tactics.",
        )
        table["procedure_transform"] = _legality("preferred", "Procedure bodies are exposed; wp/sp/seq/rnd are in phase.")
        table["targeted_inline"] = _legality("allowed", "Targeted inline can expose a remaining local wrapper.")
        table["call_named_equiv"] = _legality("avoid", "Call-site handles may already be consumed at procedure layer.")
        table["inline_all"] = _legality("avoid", "Global inline is usually redundant after bodies are exposed.")
        table["ambient_close"] = _legality(
            "allowed",
            "Procedure-body side conditions may be pure residual logic after wp/sp/if.",
        )
    elif layer == "verification_residue":
        table["proc_open"] = _legality(
            "avoid",
            (
                "The pRHL programs are already synchronized; residual closers "
                "preserve that exposed shape better than reopening bodies."
            ),
        )
        table["call_named_equiv"] = _legality("avoid", "No live call frontier remains in this synchronized residual goal.")
        table["procedure_transform"] = _legality("avoid", "No program frontier remains; solve the residual side condition.")
        table["targeted_inline"] = _legality("avoid", "No wrapper/call site remains to expose.")
        table["inline_all"] = _legality("avoid", "No call-site/program layer remains to inline.")
        table["ambient_close"] = _legality(
            "preferred",
            "Synchronized pRHL residue should be discharged by logical closers.",
        )
    elif layer == "ambient_logic":
        table["proc_open"] = _legality("avoid", "No program judgment is active in ambient logic.")
        if _dict(handles.get("intro_candidate")).get("available"):
            table["intro"] = _legality("preferred", "Introduce the leading premise before residual ambient closers.")
        table["native_ast_search"] = _legality(
            "preferred",
            "Use EC native AST search to retrieve lemmas for the residual term skeleton.",
        )
        table["ambient_close"] = _legality("preferred", "Residual goal is ambient logic/algebra.")
        table["procedure_transform"] = _legality("avoid", "No procedure body is active in ambient logic.")
        table["inline_all"] = _legality("avoid", "No call-site/program layer is active in ambient logic.")
    return table


def _has_runnable_pr_frontend_action(
    handles: dict[str, Any],
    *,
    pr_rewrites: list[Any],
    pr_normal: dict[str, Any],
    pr_bridge_obligation: dict[str, Any],
) -> bool:
    """Return whether the Pr layer has a concrete action before lowering.

    Partial handles and signature lookups are valuable context, but they
    should not suppress an explicitly labeled `byequiv` probe.  This keeps the
    compiler view neutral: exact Pr actions stay ahead of lowering, while
    incomplete Pr paths leave the lower-layer probe visible as a choice.
    """
    if pr_bridge_obligation.get("available"):
        return True
    if pr_normal.get("available") and str(pr_normal.get("recommended_tactic") or ""):
        return True
    path_plan = _dict(handles.get("pr_path_plan"))
    if _dict(path_plan.get("recommended_path")):
        return True
    if _has_live_pr_typed_bridge_path(handles):
        return True
    name_resolution = _dict(handles.get("name_resolution"))
    for lemma in pr_rewrites:
        name = str(lemma or "")
        if not name:
            continue
        resolved = resolution_for_name(name_resolution, name)
        if not resolved:
            # No resolution data usually means the local parser has not found a
            # reason to distrust the rewrite form.  Preserve the old conservative
            # ordering and keep lowering as contextual rather than a primary probe.
            return True
        if (
            not bool(resolved.get("exact_signature_known"))
            or bool(resolved.get("requires_instantiation"))
        ):
            continue
        return True
    return False


def _external_call_named_equiv_menu_items(
    handles: dict[str, Any],
    *,
    layer: str,
) -> list[dict[str, Any]]:
    """Surface external named-call candidates through ProofIR name resolution.

    AUTO-DIFF and related passes can notice that a named equiv might match the
    current pRHL frontier before ProofIR has proven the EasyCrypt scope/arity of
    the short name.  Treat that as compiler context: inspect/resolve first,
    then probe the call only if the name is actually typed for this state.
    """
    if layer not in {"prhl_module", "procedure_entry", "call_site", "procedure_body"}:
        return []
    name_resolution = _dict(handles.get("name_resolution"))
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for idx, candidate in enumerate(_list(handles.get("external_candidates"))):
        if not isinstance(candidate, dict):
            continue
        if str(candidate.get("tactic_family") or "") != "call_named_equiv":
            continue
        lemma = _candidate_lemma_name(candidate)
        tactic = str(candidate.get("tactic") or candidate.get("action") or "").strip()
        if not lemma or not tactic:
            continue
        resolved = resolution_for_name(name_resolution, lemma)
        lookup_action = str(resolved.get("signature_lookup_action") or f"-where {lemma}")
        status = str(resolved.get("resolution_status") or "")
        exact = bool(resolved.get("exact_signature_known"))
        binding = binding_for_name(
            _dict(handles.get("instantiation_bindings")),
            lemma,
        )
        requires_instantiation = exact and bool(resolved.get("requires_instantiation"))
        instantiated_templates = _list(binding.get("instantiated_templates"))
        missing_slots = _instantiation_missing_slot_labels(binding, resolved)
        verified = bool(candidate.get("verified"))
        needs_lookup = bool(
            resolved
            and (
                not exact
                or status == "source_local_scope_check_required"
                or (requires_instantiation and not instantiated_templates)
            )
        )
        source = str(candidate.get("producer") or "external analysis")
        if needs_lookup and lookup_action:
            key = ("lookup", lookup_action)
            if key not in seen:
                seen.add(key)
                out.append(_menu_item(
                    f"sig_external_call_{_safe_id(lemma or str(idx))}",
                    tactic=lookup_action,
                    tactic_family="signature_lookup",
                    action_type="inspection_action",
                    cost="free",
                    why=(
                        f"{source} found `{tactic}` as a named equiv candidate, "
                        "but ProofIR has not confirmed the usable EasyCrypt "
                        "scope/signature for this state. Inspect the name before "
                        "probing the call."
                    ),
                    preconditions=[
                        "run this read-only lookup before guessing call arguments",
                        (
                            "if the lemma is local to a closed section/theory, use "
                            "the scoped name or choose a different frontier action"
                        ),
                    ],
                    preserves=["proof state"],
                    cost_factors={
                        "external_candidate": tactic,
                        "name_resolution_status": status or "unknown",
                        "exact_signature_known": exact,
                        "call_candidate_kind": "source_lookup_landmark",
                    },
                ))
        call_candidate_kind = (
            "direct_current_call"
            if (
                verified
                and exact
                and status != "source_local_scope_check_required"
                and not requires_instantiation
            )
            else "source_lookup_landmark"
        )
        if call_candidate_kind != "direct_current_call":
            continue
        key = ("call", tactic)
        if key in seen:
            continue
        if requires_instantiation and instantiated_templates:
            continue
        seen.add(key)
        action_text = tactic
        action_type = (
            "probe_tactic"
            if verified and exact and status != "source_local_scope_check_required"
            else "strategy_hint"
        )
        if requires_instantiation and not instantiated_templates:
            action_text = _call_instantiation_hint(lemma, missing_slots)
            action_type = "strategy_hint"
        out.append(_menu_item(
            f"external_call_{_safe_id(lemma or str(idx))}",
            tactic=action_text,
            tactic_family="call_named_equiv",
            action_type=action_type,
            cost=(
                "moderate"
                if requires_instantiation and not instantiated_templates else
                str(candidate.get("cost") or "cheap")
            ),
            why=(
                (
                    f"{source} found `{lemma}` at the current pRHL frontier, "
                    "but its exact signature has required arguments that are "
                    "not yet bound by the current ProgramIR/goal context."
                )
                if requires_instantiation and not instantiated_templates else
                (
                    f"{source} found a possible named equiv at the current pRHL "
                    "frontier. Treat it as a candidate, not a compiler-certified "
                    "command, until name resolution and frontier matching are clear."
                )
            ),
            preconditions=[
                "the current pRHL frontier must contain the matching procedure call",
                *(
                    _instantiation_preconditions(missing_slots)
                    if requires_instantiation and not instantiated_templates else
                    []
                ),
                *resolution_preconditions(
                    lemma,
                    resolved,
                    lookup_action,
                    action_word="call",
                ),
            ],
            preserves=["pRHL abstraction", "procedure bodies"],
            cost_factors={
                "external_candidate": tactic,
                "name_resolution_status": status or "unknown",
                "exact_signature_known": exact,
                "verified_external_candidate": verified,
                "call_candidate_kind": call_candidate_kind,
                "requires_instantiation": requires_instantiation,
                "missing_slots": missing_slots,
                "instantiation_binding_status": (
                    "has_candidates" if instantiated_templates else
                    "missing_candidates" if requires_instantiation else
                    "not_required"
                ),
            },
        ))
    return out


_SWAP_WITH_ROUTE_OFFSET = re.compile(
    r"^(swap(?:\{[12]\})?\s+(?:\[\d+\.\.\d+\]|\d+))\s+(-?\d+)\s*\.?\s*$"
)


def _swap_route_frame(tactic: str) -> str:
    match = _SWAP_WITH_ROUTE_OFFSET.match(tactic.strip())
    if not match:
        return tactic.strip()
    return f"{match.group(1)} <offset>."


def _external_realignment_swap_menu_items(
    handles: dict[str, Any], *, layer: str
) -> list[dict[str, Any]]:
    """Surface daemon-accepted `swap{N} K M.` examples as route-dependent frames.

    A daemon-accepted swap is a real legality fact, but the signed offset is not a
    unique proof-route fact. At a frontier such as schnorr SHVZK, many offsets are
    EasyCrypt-valid while only the one that lands the next sampling/coupling target is
    strategically useful. The agent-facing action is therefore `swap{N} K <offset>.`;
    the concrete accepted tactic is retained as evidence only.
    """
    if layer not in {"prhl_module", "procedure_entry", "call_site", "procedure_body"}:
        return []
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for idx, candidate in enumerate(_list(handles.get("external_candidates"))):
        if not isinstance(candidate, dict):
            continue
        if str(candidate.get("tactic_family") or "") != "realignment_swap":
            continue
        if not bool(candidate.get("verified")):
            continue  # only daemon-accepted swaps surface; never an unverified guess
        tactic = str(candidate.get("tactic") or candidate.get("action") or "").strip()
        if not tactic or tactic in seen:
            continue
        seen.add(tactic)
        source = str(candidate.get("producer") or "alignment analysis")
        frame = _swap_route_frame(tactic)
        item = _menu_item(
            f"realignment_swap_{_safe_id(str(idx))}",
            tactic=frame,
            tactic_family="realignment_swap",
            action_type="strategy_hint",
            cost="cheap",
            why=(
                f"{source} found concrete swap `{tactic}` and the daemon accepted it "
                "on the live pRHL goal. Treat this as evidence for the source-position "
                "realignment frame, not as a unique next tactic: choose the offset that "
                "lands the route's next sample/rnd coupling target."
            ),
            preserves=["pRHL abstraction", "procedure bodies"],
            cost_factors={
                "external_candidate": frame,
                "ec_accepted_example": tactic,
                "verified_external_candidate": True,
                "offset_policy": "route_dependent",
                "not_unique": True,
            },
        )
        out.append(item)
    return out


def _candidate_menu(
    layer: str,
    goal_kind: str,
    liveness: dict[str, Any],
    handles: dict[str, Any],
    *,
    program_ir: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    menu: list[dict[str, Any]] = []
    instantiated_templates_emitted = False
    intro = _dict(handles.get("intro_candidate"))
    if intro.get("available"):
        tactic = str(intro.get("tactic") or "move=> H.").strip()
        menu.append(_menu_item(
            "intro",
            tactic=tactic if tactic.endswith(".") else tactic + ".",
            tactic_family="intro",
            action_type="probe_tactic",
            cost="cheap",
            why=str(
                intro.get("reason")
                or "Introduce the leading binder/premise before choosing a proof-language pass."
            ),
            preserves=["current abstraction layer"],
        ))
    if layer in {"prhl_module", "procedure_entry"}:
        menu.extend(_equiv_exact_closer_menu_items(handles))
    if layer in {"prhl_module", "procedure_entry"}:
        tactic = "eager proc." if goal_kind == "eager" else "proc."
        menu.append(_menu_item(
            "proc_open",
            tactic=tactic,
            tactic_family="proc_open",
            action_type="probe_tactic",
            cost="cheap",
            why=(
                "Expose the procedure bodies/call sites before lower-level "
                "wp/inline/call decisions."
            ),
            preserves=["higher-level call handles"],
        ))
        if layer == "procedure_entry":
            menu.extend(_probabilistic_vc_menu_items(handles, layer=layer))
            menu.extend(_procedure_entry_fallback_menu_items(handles))
            body_frontend = _dict(handles.get("procedure_body_frontend"))
            if _list(body_frontend.get("statement_types")) or _list(
                body_frontend.get("loop_frontiers")
            ):
                menu.extend(_procedure_frontier_plan_menu_items(handles))
                menu.extend(_procedure_body_menu_items(handles))
    if layer in {"prhl_module", "procedure_entry", "call_site", "procedure_body"}:
        menu.extend(_external_call_named_equiv_menu_items(handles, layer=layer))
        menu.extend(_external_realignment_swap_menu_items(handles, layer=layer))
    if layer in {"call_site", "procedure_body"}:
        menu.extend(_equiv_exact_closer_menu_items(handles))
    pr_rewrites = build_visible_pr_rewrites(handles)
    pr_normal = _dict(handles.get("pr_normal_form"))
    if layer == "pr":
        menu.extend(build_pr_normalization_menu_items(handles))
    pr_bridge_obligation = _dict(handles.get("pr_decomposition_bridge_obligation"))
    if layer == "pr":
        menu.extend(build_pr_decomposition_bridge_menu_items(handles))
    if layer == "pr":
        has_runnable_pr_frontend = _has_runnable_pr_frontend_action(
            handles,
            pr_rewrites=pr_rewrites,
            pr_normal=pr_normal,
            pr_bridge_obligation=pr_bridge_obligation,
        )
        menu.extend(_probabilistic_vc_menu_items(handles, layer=layer))
        menu.extend(_semantic_pr_bound_menu_items(handles))
        menu.extend(build_pr_rewrite_menu_items(
            handles,
            goal_kind=goal_kind,
            pr_rewrites=pr_rewrites,
        ))
    if layer == "pr":
        menu.extend(_pr_typed_bridge_chain_menu_items(handles))
        menu.extend(_external_pr_bridge_frontier_items(handles))
        menu.extend(_pr_wrapper_bridge_menu_items(handles))
        menu.extend(_pr_path_signature_lookup_items(handles))
        menu.extend(build_pr_clone_bound_apply_menu_items(handles))
        menu.extend(build_pr_byequiv_fallback_menu_items(
            handles,
            goal_kind=goal_kind,
            pr_rewrites=pr_rewrites,
            pr_bridge_obligation=pr_bridge_obligation,
            has_live_typed_bridge_path=_has_live_pr_typed_bridge_path(handles),
            has_runnable_pr_frontend=has_runnable_pr_frontend,
        ))
    if layer in {"pr", "ambient_logic", "verification_residue"}:
        menu.extend(_native_ast_search_menu_items(handles))
    if layer == "pr" and goal_kind == "Pr_eq" and not intro.get("available"):
        has_pr_handle = bool(pr_rewrites) or bool(
            _dict(_dict(handles.get("pr_path_plan")).get("recommended_path"))
        ) or bool(
            _dict(handles.get("pr_path_plan")).get("partial_paths")
        ) or _has_live_pr_typed_bridge_path(handles) or bool(
            _list(_dict(handles.get("pr_typed_bridge_frontend")).get("wrapper_bridges"))
        ) or bool(
            _dict(_dict(handles.get("pr_path_plan")).get("arithmetic_plan")).get(
                "available"
            )
            or _dict(_dict(handles.get("pr_path_plan")).get("arithmetic_plan")).get(
                "shape"
            )
        ) or bool(pr_normal.get("available"))
        if not has_pr_handle:
            menu.append(_menu_item(
                "byequiv_bridge",
                tactic="byequiv => //.",
                tactic_family="probability_to_program",
                action_type="probe_tactic",
                cost="cheap",
                why=(
                    "Pure probability equality with no higher-level Pr rewrite/path "
                    "handle visible; bridge into the pRHL layer."
                ),
                preconditions=[
                    "introduce all leading premises/binders first",
                    "compare visible Pr rewrite/path handles with direct byequiv by endpoint match",
                ],
                preserves=["Pr equality intent"],
            ))
    if layer in {"prhl_module", "call_site", "procedure_body"}:
        frontier = _dict(_dict(program_ir or {}).get("frontier"))
        by_side = _dict(frontier.get("by_side"))
        left_frontier = _dict(by_side.get("left"))
        right_frontier = _dict(by_side.get("right"))
        if (
            str(left_frontier.get("kind") or "") == "IF"
            and str(right_frontier.get("kind") or "") == "IF"
        ):
            live_call_behind_if = bool(
                int(liveness.get("non_frontier_callable_lemma_count") or 0) > 0
                or int(liveness.get("live_callable_lemma_count") or 0) > int(
                    liveness.get("callable_now_lemma_count") or 0
                )
            )
            menu.append(_menu_item(
                "if_frontier",
                tactic="if => //.",
                tactic_family="procedure_transform",
                action_type="strategy_hint" if live_call_behind_if else "probe_tactic",
                cost="moderate" if live_call_behind_if else "cheap",
                why=(
                    (
                        "Both sides are blocked by aligned frontier `if` "
                        "statements, but ProofIR also sees live call handles "
                        "behind this branch frontier. Prefer the ProgramIR "
                        "seq/frontier exposure slice first; split the branch "
                        "only after the call frontier is handled or if the "
                        "guard is the actual current obligation."
                    )
                    if live_call_behind_if else
                    (
                        "Both sides are blocked by aligned frontier `if` "
                        "statements; split the branch guard before calling "
                        "nested call-site lemmas."
                    )
                ),
                preconditions=[
                    "frontier statements are aligned conditionals",
                    *(
                        [
                            "a live named call handle is still behind this branch; prefer the ProgramIR seq/frontier exposure candidate before committing if",
                        ]
                        if live_call_behind_if else []
                    ),
                    "after splitting, use wp/call on the branch-local call sites",
                ],
                preserves=["nested call handles"],
                cost_factors={
                    "frontier_kind": "IF",
                    "live_call_behind_frontier": live_call_behind_if,
                    "non_frontier_callable_lemma_count": int(
                        liveness.get("non_frontier_callable_lemma_count") or 0
                    ),
                },
                program_rank=40 if live_call_behind_if else 0,
            ))
        if layer == "call_site":
            menu.extend(_instantiated_template_menu_items(handles))
            instantiated_templates_emitted = True
            menu.extend(_call_site_prefix_menu_items(handles))
            menu.extend(_procedure_surface_map_menu_items(handles))
        menu.extend(_program_edit_script_menu_items(program_ir or {}, handles))
        emitted_call_handles = 0
        for handle in _list(handles.get("callable_lemmas")):
            if not isinstance(handle, dict):
                continue
            lemma = str(handle.get("lemma") or "")
            if not lemma:
                continue
            callable_now = bool(handle.get("callable_now"))
            requires_cut = bool(handle.get("requires_cut_to_frontier"))
            resolved = resolution_for_name(
                _dict(handles.get("name_resolution")),
                lemma,
            )
            lookup_action = str(resolved.get("signature_lookup_action") or "")
            resolution_status = str(resolved.get("resolution_status") or "")
            binding = binding_for_name(
                _dict(handles.get("instantiation_bindings")),
                lemma,
            )
            exact_signature_known = bool(resolved.get("exact_signature_known"))
            requires_instantiation = exact_signature_known and bool(
                resolved.get("requires_instantiation")
            )
            instantiated_templates = _list(binding.get("instantiated_templates"))
            missing_slots = _instantiation_missing_slot_labels(binding, resolved)
            call_candidate_kind = str(handle.get("call_candidate_kind") or "")
            if not call_candidate_kind:
                call_candidate_kind = _call_handle_candidate_kind(
                    handle,
                    resolved=resolved,
                    resolution_status=resolution_status,
                    exact_signature_known=exact_signature_known,
                    requires_instantiation=requires_instantiation,
                    instantiated_templates=instantiated_templates,
                )
            if requires_instantiation and instantiated_templates:
                continue
            if call_candidate_kind != "direct_current_call":
                if (
                    resolved
                    and lookup_action
                    and (
                        not exact_signature_known
                        or resolution_status in _CALL_NAME_LOOKUP_REQUIRED_STATUSES
                        or (requires_instantiation and not instantiated_templates)
                    )
                ):
                    menu.append(_menu_item(
                        f"sig_{lemma}",
                        tactic=lookup_action,
                        tactic_family="signature_lookup",
                        action_type="inspection_action",
                        cost="free",
                        why=(
                            f"Resolve or bind the exact signature for `{lemma}` "
                            "before turning this route landmark into a call tactic."
                        ),
                        preserves=["proof state"],
                        cost_factors={
                            "call_candidate_kind": call_candidate_kind,
                            "name_resolution_status": resolution_status or "unknown",
                            "exact_signature_known": exact_signature_known,
                            "requires_instantiation": requires_instantiation,
                            "missing_slots": missing_slots,
                        },
                    ))
                continue
            if emitted_call_handles >= 2:
                break
            tactic = f"call {lemma}."
            menu.append(_menu_item(
                f"call_{lemma}",
                tactic=tactic,
                tactic_family="call_named_equiv",
                action_type="probe_tactic",
                cost="cheap",
                why=(
                    f"Named call-level equiv `{lemma}` is resolved and matches "
                    "the current last-call frontier."
                ),
                preserves=["call-site layer", "procedure bodies"],
                preconditions=[
                    "the current pRHL program contains this lemma's matching call at the last-call frontier",
                    *resolution_preconditions(
                        lemma,
                        resolved,
                        lookup_action,
                        action_word="call",
                    ),
                ],
                cost_factors={
                    "callable_now": callable_now,
                    "requires_cut_to_frontier": requires_cut,
                    "program_order": int(handle.get("program_order") or 9999),
                    "program_rank": int(handle.get("program_rank") or 9999),
                    "program_diff_steps": list(
                        handle.get("program_diff_steps") or []
                    ),
                    "same_concrete_call_pairs": list(
                        handle.get("same_concrete_call_pairs") or []
                    ),
                    "same_concrete_call_pair": bool(
                        handle.get("same_concrete_call_pairs")
                    ),
                    "call_handle_relevance": str(
                        handle.get("call_handle_relevance") or ""
                    ),
                    "frontier_status_detail": str(
                        handle.get("frontier_status_detail") or ""
                    ),
                    "live_call_site_ids": list(
                        handle.get("live_call_site_ids") or []
                    ),
                    "frontier_call_site_ids": list(
                        handle.get("frontier_call_site_ids") or []
                    ),
                    "name_resolution_status": resolution_status or "unknown",
                    "exact_signature_known": exact_signature_known,
                    "requires_instantiation": requires_instantiation,
                    "missing_slots": missing_slots,
                    "call_candidate_kind": call_candidate_kind,
                    "instantiation_binding_status": (
                        "has_candidates" if instantiated_templates else
                        "missing_candidates" if requires_instantiation else
                        "not_required"
                    ),
                },
                program_rank=int(handle.get("program_rank") or 9999),
            ))
            emitted_call_handles += 1
    if layer == "call_site":
        adversary_skeleton = _dict(handles.get("adversary_invariant_skeleton"))
        if adversary_skeleton.get("available"):
            suggested_inv = str(
                adversary_skeleton.get("suggested_invariant")
                or "<adversary invariant>"
            )
            obligations = [
                _dict(item)
                for item in _list(adversary_skeleton.get("oracle_obligations"))
                if isinstance(item, dict)
            ]
            menu.append(_menu_item(
                "adversary_invariant_skeleton",
                tactic=f"call (_: {suggested_inv}).",
                tactic_family="call_invariant_skeleton",
                action_type="strategy_hint",
                cost="moderate",
                why=str(
                    adversary_skeleton.get("why")
                    or "Abstract adversary calls generate oracle obligations."
                ),
                preconditions=[
                    "check/fill the adversary invariant before committing",
                    "after the adversary call, use the mapped oracle handles in their generated subgoals",
                ],
                preserves=["adversary frontier", "oracle obligation handles"],
                cost_factors={
                    "oracle_obligations": [
                        str(item.get("lemma") or "")
                        for item in obligations
                        if str(item.get("lemma") or "")
                    ],
                    "frontier_sources": _list(
                        adversary_skeleton.get("frontier_sources")
                    ),
                },
            ))
        non_frontier = int(liveness.get("non_frontier_callable_lemma_count") or 0)
        callable_now_count = int(liveness.get("callable_now_lemma_count") or 0)
        if non_frontier and not callable_now_count:
            exposure = _frontier_exposure_candidate(program_ir or {}, handles)
            menu.append(_menu_item(
                "expose_frontier_call",
                tactic=exposure["tactic"],
                tactic_family="procedure_transform",
                action_type="strategy_hint",
                cost="moderate",
                why=exposure["why"],
                preconditions=[
                    exposure["precondition"],
                    "re-run agent-view after exposing the call frontier",
                ],
                preserves=["live call handles"],
                cost_factors={
                    "frontier_blocker_kinds": exposure["blocker_kinds"],
                    "program_action": dict(exposure.get("program_action") or {}),
                },
                scheduler_role="program_frontier_exposure",
            ))
        menu.extend(_call_site_control_menu_items(program_ir or {}, handles))
        skeleton = (
            {}
            if adversary_skeleton.get("available") else
            _dict(handles.get("invariant_skeleton"))
        )
        suggested_inv = str(skeleton.get("suggested_invariant") or "")
        body_frontend = _dict(handles.get("procedure_body_frontend"))
        has_procedure_like_frontier = bool(
            _list(body_frontend.get("init_like_wrappers"))
            or any(
                str(_dict(item).get("kind") or "") == "wrapper_or_init"
                and "." not in str(_dict(item).get("statement_path") or "")
                for item in _list(body_frontend.get("structured_regions"))
                if isinstance(item, dict)
            )
        )
        if suggested_inv and (
            int(liveness.get("frontier_call_site_count") or 0) > 0
            or has_procedure_like_frontier
        ):
            live_fact_coverage = _invariant_live_fact_coverage(
                suggested_inv,
                handles,
                skeleton=skeleton,
            )
            if live_fact_coverage.get("available") and len(suggested_inv) <= 280:
                menu.append(_menu_item(
                    "call_invariant_obligation_preview",
                    tactic=(
                        "-call-subgoals -c "
                        + _double_quoted_tool_arg(suggested_inv)
                    ),
                    tactic_family="call_invariant_skeleton",
                    action_type="inspection_action",
                    cost="moderate",
                    why=(
                        "ProofIR assembled a dataflow invariant candidate and "
                        "sees a procedure-like call frontier. This read-only "
                        "probe shows the actual EasyCrypt subgoals that "
                        "`call (_: <candidate>)` would generate."
                    ),
                    preconditions=[
                        "read-only inspection; do not count this as a proof tactic",
                        "compare `live_fact_coverage` in this item before committing the invariant call",
                    ],
                    preserves=["proof state", "call-site layer"],
                    cost_factors={
                        "live_fact_coverage": live_fact_coverage,
                    },
                ))
            menu.append(_menu_item(
                "call_invariant_skeleton",
                tactic=f"call (_: {suggested_inv}).",
                tactic_family="call_invariant_skeleton",
                action_type="strategy_hint",
                cost="moderate",
                why=(
                    "ProofIR extracted an invariant skeleton from the pRHL "
                    "postcondition and sees a procedure-like call frontier."
                ),
                preconditions=[
                    "fill or check any missing call preconditions before committing",
                    "if the displayed invariant is too weak, strengthen it with live module state from pre/post before probing",
                    "preview generated subgoals with `-call-subgoals -c <invariant>` when the residual order is unclear",
                    *(
                        [
                            "use `live_fact_coverage` to see which visible facts are carried, missing, or intentionally left as residuals",
                        ]
                        if live_fact_coverage.get("available") else []
                    ),
                ],
                preserves=["call-site layer"],
                cost_factors={
                    "live_fact_coverage": live_fact_coverage,
                },
            ))
        lost = int(liveness.get("live_call_site_count") or 0)
        if int(liveness.get("live_callable_lemma_count") or 0) == 0:
            menu.append(_menu_item(
                "targeted_inline",
                tactic="inline{1} 1.",
                tactic_family="targeted_inline",
                action_type="strategy_hint",
                cost="moderate",
                why="Target one wrapper when no named call lemma fits; preserve unrelated call sites.",
                destroys=["one selected wrapper/call site"],
                preserves=["other call sites"],
            ))
        menu.append(_menu_item(
            "inline_all",
            tactic="inline *.",
            tactic_family="inline_all",
            action_type="avoid_action" if lost else "strategy_hint",
            cost="expensive" if lost else "moderate",
            why=(
                (
                    f"Global inline would erase {lost} live call-site handle(s); "
                    "try a frontier call, targeted inline, wp, or seq first."
                )
                if lost else
                (
                    "No live call site is visible; global inline is less "
                    "likely to hide useful call handles here."
                )
            ),
            destroys=["all live call sites"] if lost else [],
            cost_factors={
                "expansion": "high" if lost else "medium",
                "irreversibility": "high" if lost else "medium",
                "lost_handles": lost,
            },
        ))
    if layer == "procedure_body":
        menu.extend(_probabilistic_vc_menu_items(handles, layer=layer))
        menu.extend(_procedure_frontier_plan_menu_items(handles))
        menu.extend(_procedure_body_menu_items(handles))
        menu.append(_menu_item(
            "wp_sp_seq",
            tactic="wp.",
            tactic_family="procedure_transform",
            action_type="strategy_hint",
            cost="moderate",
            why="Procedure bodies are exposed; work backward through statements.",
        ))
    if layer == "verification_residue":
        menu.append(_menu_item(
            "residual_prhl_close",
            tactic="auto.",
            tactic_family="ambient_close",
            action_type="probe_tactic",
            cost="cheap",
            why=(
                "The pRHL programs are synchronized and no call frontier is live; "
                "try the residual logical close before reopening program structure."
            ),
        ))
    if layer == "ambient_logic":
        ambient = _dict(handles.get("ambient_frontend"))
        unfoldables = [
            _dict(item) for item in _list(handles.get("unfoldable_goal_heads"))
            if isinstance(item, dict)
        ]
        menu.extend(_ambient_named_closer_menu_items(handles))
        if (
            ambient.get("top_connective") == "conjunction"
            and not intro.get("available")
        ):
            menu.append(_menu_item(
                "ambient_split",
                tactic="split.",
                tactic_family="ambient_close",
                action_type="strategy_hint",
                cost="cheap",
                why=(
                    "Ambient front-end sees a top-level conjunction; split before "
                    "closing each residue if auto does not solve it."
                ),
                preserves=["ambient logic layer"],
                cost_factors={
                    "ambient_residual_like": bool(ambient.get("residual_like")),
                },
            ))
        if unfoldables:
            first = unfoldables[0]
            name = str(first.get("name") or "").strip()
            tactic = str(first.get("unfold_tactic") or f"rewrite /{name}.")
            if name and tactic:
                menu.append(_menu_item(
                    "ambient_unfold_goal_head",
                    tactic=tactic,
                    tactic_family="definition_unfold",
                    action_type="probe_tactic",
                    cost="free",
                    why=(
                        f"`{name}` occurs in the residual goal and resolves "
                        "as an unfoldable op/pred/abbrev, not as an SMT "
                        "lemma hint."
                    ),
                    preserves=["ambient logic layer"],
                    cost_factors={
                        "unfoldable_goal_heads": [
                            str(item.get("name") or "")
                            for item in unfoldables[:4]
                            if item.get("name")
                        ],
                        "ambient_residual_like": True,
                    },
                ))
        menu.append(_menu_item(
            "ambient_simplify",
            tactic="auto => />.",
            tactic_family="ambient_close",
            action_type="probe_tactic",
            cost="cheap",
            why=(
                "Ambient front-end found a pure residual goal; simplify before "
                "asking SMT to solve the remaining logic."
            ),
            preserves=["ambient logic layer"],
            cost_factors={
                "ambient_residual_like": bool(ambient.get("residual_like")),
            },
        ))
        menu.append(_menu_item(
            "ambient_smt",
            tactic="smt().",
            tactic_family="ambient_close",
            action_type="probe_tactic",
            cost="moderate",
            why=(
                "Ambient front-end leaves a pure logical/algebraic residue "
                "after local simplification."
            ),
            preconditions=["try `auto => />.` first when it is also recommended"],
            preserves=["ambient logic layer"],
            cost_factors={
                "ambient_residual_like": bool(ambient.get("residual_like")),
            },
        ))
    if not instantiated_templates_emitted:
        menu.extend(_instantiated_template_menu_items(handles))
    return menu


def _frontier_exposure_candidate(
    program_ir: dict[str, Any],
    handles: dict[str, Any],
) -> dict[str, Any]:
    frontier = _dict(_dict(program_ir).get("frontier"))
    blockers = [
        _dict(item)
        for item in _dict(frontier.get("frontier_blockers")).values()
        if isinstance(item, dict)
    ]
    kinds = _dedupe_strings([
        str(item.get("kind") or "")
        for item in blockers
        if str(item.get("kind") or "")
    ])
    skeleton = _dict(handles.get("invariant_skeleton"))
    invariant = str(skeleton.get("suggested_invariant") or "").strip()
    if "WHILE" in kinds:
        tactic = (
            f"while ({invariant})."
            if invariant and not _invariant_looks_noisy(invariant) else
            "while (<loop invariant>)."
        )
        return {
            "tactic": tactic,
            "why": (
                "A named call lemma is live under a loop frontier. "
                "Open the loop proof with a real invariant before trying "
                "to expose the inner call-site frontier."
            ),
            "precondition": (
                "supply a loop invariant that preserves the callable lemma precondition"
            ),
            "blocker_kinds": kinds,
        }
    if "IF" in kinds:
        return {
            "tactic": "if.",
            "why": (
                "A named call lemma is live behind an if frontier. Split the "
                "branch before exposing the matching call-site frontier."
            ),
            "precondition": "choose `if.` or `if => //.` according to branch side conditions",
            "blocker_kinds": kinds,
        }
    planned = _planned_frontier_exposure(handles)
    if planned:
        return {
            "tactic": planned["tactic"],
            "why": planned["why"],
            "precondition": planned["precondition"],
            "blocker_kinds": kinds,
            "program_action": planned["program_action"],
        }
    return {
        "tactic": "wp.",
        "why": (
            "A named call lemma is live, but EasyCrypt's call rule uses the "
            "last-call frontier. Use wp/seq to expose the matching call before "
            "`call <lemma>`."
        ),
        "precondition": "choose wp or seq according to the current statement suffix",
        "blocker_kinds": kinds,
    }


def _probabilistic_vc_menu_items(
    handles: dict[str, Any],
    *,
    layer: str,
) -> list[dict[str, Any]]:
    """No menu item: this only emitted the `Probabilistic VC plan: …` route-PLAN
    — its own precondition said "this is not a runnable tactic", i.e. move
    GUIDANCE, not a fact. The probabilistic-VC obligation structure remains
    available to other producers via the frontend handle; the plan PROSE is not a
    state-derived fact, so it is no longer surfaced."""
    return []


def _call_site_control_menu_items(
    program_ir: dict[str, Any],
    handles: dict[str, Any],
) -> list[dict[str, Any]]:
    frontier = _dict(_dict(program_ir).get("frontier"))
    blockers = [
        _dict(item)
        for item in _dict(frontier.get("frontier_blockers")).values()
        if isinstance(item, dict)
    ]
    if not blockers:
        return []
    kinds = _dedupe_strings([
        str(item.get("kind") or "")
        for item in blockers
        if str(item.get("kind") or "")
    ])
    items: list[dict[str, Any]] = []
    live_call_behind_frontier = any(
        isinstance(handle, dict)
        and bool(handle.get("requires_cut_to_frontier"))
        for handle in _list(handles.get("callable_lemmas"))
    )
    if any(kind in {"ASSIGN", "SAMPLE", "ABSTRACT", "ASSERT"} for kind in kinds):
        items.append(_menu_item(
            "program_wp_suffix",
            tactic="wp.",
            tactic_family="procedure_transform",
            action_type="strategy_hint",
            cost="moderate",
            why=(
                "A live call-site resource exists below a non-call suffix. "
                "wp consumes the suffix while preserving the opportunity to "
                "call the named lemma once the frontier is exposed."
            ),
            preconditions=[
                "use when the suffix is ordinary assignment/sample/assert code",
                "after wp, re-check whether a named call or invariant call is now at the frontier",
            ],
            preserves=["live call handles"],
            cost_factors={"frontier_blocker_kinds": kinds},
        ))
    if "IF" in kinds:
        items.append(_menu_item(
            "program_if_frontier",
            tactic="if.",
            tactic_family="procedure_transform",
            action_type="strategy_hint",
            cost="moderate" if live_call_behind_frontier else "cheap",
            why=(
                (
                    "A branch frontier is visible, but a named call handle is "
                    "also live behind it. Treat `if` as the branch-local "
                    "alternative; prefer a ProgramIR seq/frontier exposure "
                    "slice first when that slice exposes the matching call."
                )
                if live_call_behind_frontier else
                (
                    "A live call-site resource is behind a branch frontier. "
                    "Split the branch before choosing the branch-local wp/call route."
                )
            ),
            preconditions=[
                "use side-specific `if{1}.` or `if{2}.` when only one side branches",
                *(
                    [
                        "if a seq/frontier exposure candidate targets the live call handle, try that before splitting the branch",
                    ]
                    if live_call_behind_frontier else []
                ),
            ],
            preserves=["branch-local call handles"],
            cost_factors={
                "frontier_blocker_kinds": kinds,
                "live_call_behind_frontier": live_call_behind_frontier,
            },
            program_rank=41 if live_call_behind_frontier else 0,
        ))
    if "WHILE" in kinds:
        invariant = _while_invariant_tactic_hint(handles)
        items.append(_menu_item(
            "program_while_frontier",
            tactic=f"while ({invariant}).",
            tactic_family="procedure_transform",
            action_type="strategy_hint",
            cost="moderate",
            why=(
                "A live call-site resource is under a loop frontier. Open the "
                "loop with an invariant before trying to expose inner calls."
            ),
            preconditions=[
                "the invariant must preserve the precondition of the call lemma hidden in the loop body",
            ],
            preserves=["loop-contained call handles"],
            cost_factors={"frontier_blocker_kinds": kinds},
        ))
    diff = _dict(_dict(program_ir).get("program_diff"))
    shifted = [
        _dict(step) for step in _list(diff.get("edit_script"))
        if isinstance(step, dict)
        and str(_dict(step).get("kind") or "") == "shifted_call_pair"
    ]
    reorder_like = [
        _dict(step) for step in _list(diff.get("edit_script"))
        if isinstance(step, dict)
        and str(_dict(step).get("kind") or "") == "kind_mismatch"
        and {
            str(_dict(step).get("left_kind") or ""),
            str(_dict(step).get("right_kind") or ""),
        } & {"CALL"}
    ]
    if shifted or reorder_like:
        items.append(_menu_item(
            "program_swap_alignment",
            tactic="swap <range> <offset>.",
            tactic_family="procedure_transform",
            action_type="strategy_hint",
            cost="moderate",
            why=(
                "The same call shape is live on both sides but appears at "
                "different top-level positions. A local swap can align the "
                "call frontier before wp/call."
            ),
            preconditions=[
                "choose the concrete side/range from the shifted call-pair or kind-mismatch evidence",
                "after the swap, re-run agent-view to refresh call-frontier status",
            ],
            preserves=["call-site handles"],
            cost_factors={
                "shifted_call_pairs": shifted[:3],
                "reorder_like_mismatches": reorder_like[:3],
            },
        ))
    return items


def _call_site_prefix_menu_items(handles: dict[str, Any]) -> list[dict[str, Any]]:
    return build_call_site_prefix_menu_items(handles)


def _procedure_entry_fallback_menu_items(handles: dict[str, Any]) -> list[dict[str, Any]]:
    return build_procedure_entry_fallback_menu_items(handles)


def _procedure_frontier_plan_menu_items(handles: dict[str, Any]) -> list[dict[str, Any]]:
    return build_procedure_frontier_plan_menu_items(handles)


def _procedure_body_menu_items(handles: dict[str, Any]) -> list[dict[str, Any]]:
    return build_procedure_body_menu_items(
        handles,
        invariant_hint=_while_invariant_tactic_hint(handles),
    )


def _procedure_surface_map_menu_items(handles: dict[str, Any]) -> list[dict[str, Any]]:
    return build_procedure_surface_map_menu_items(handles)


def _sampling_ordering_diagnostics(
    handles: dict[str, Any],
) -> list[dict[str, Any]]:
    return build_sampling_ordering_diagnostics(handles)


def _ambient_named_closer_menu_items(handles: dict[str, Any]) -> list[dict[str, Any]]:
    return build_ambient_named_closer_menu_items(handles)


def _equiv_exact_closer_menu_items(handles: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for idx, closer in enumerate(_list(handles.get("equiv_exact_closers"))[:4]):
        if not isinstance(closer, dict):
            continue
        lemma = str(closer.get("lemma") or "")
        tactic = str(closer.get("tactic") or "")
        if not lemma or not tactic:
            continue
        items.append(_menu_item(
            f"equiv_exact_{_safe_id(lemma)}_{idx}",
            tactic=tactic,
            tactic_family="call_named_equiv",
            action_type=(
                "probe_tactic"
                if bool(closer.get("fully_bound")) else
                "strategy_hint"
            ),
            cost="cheap" if bool(closer.get("fully_bound")) else "moderate",
            why=str(
                closer.get("reason")
                or f"Source lemma `{lemma}` has an equiv conclusion matching the current pRHL goal."
            ),
            preconditions=[
                "this closes the current pRHL/equiv goal directly; do not open the procedure body first if the signature is fully bound",
                *(
                    []
                    if bool(closer.get("fully_bound")) else
                    ["inspect the lemma signature or fill unresolved premise arguments before probing"]
                ),
            ],
            preserves=["pRHL abstraction", "procedure bodies"],
            cost_factors={
                "lemma": lemma,
                "source_path": str(closer.get("source_path") or ""),
                "matched_lhs_proc": str(closer.get("lhs_proc") or ""),
                "matched_rhs_proc": str(closer.get("rhs_proc") or ""),
                "arguments": list(closer.get("arguments") or []),
                "missing_arguments": list(closer.get("missing_arguments") or []),
            },
        ))
    return items


def _semantic_pr_bound_menu_items(handles: dict[str, Any]) -> list[dict[str, Any]]:
    return build_semantic_pr_bound_menu_items(handles)


def _program_edit_script_menu_items(
    program_ir: dict[str, Any],
    handles: dict[str, Any],
) -> list[dict[str, Any]]:
    action = _dict(handles.get("program_edit_script_action"))
    if not action:
        action = _program_edit_script_action(program_ir)
    tactic = str(action.get("tactic_hint") or action.get("tactic") or "").strip()
    if not tactic:
        return []
    action_kind = str(action.get("kind") or "")
    is_seq_cut = tactic.startswith("seq ") or action_kind in {
        "expose_asymmetric_prefix",
        "expose_call_pair_frontier",
        "expose_last_call_frontier",
    }
    has_placeholder = _has_unfilled_angle_placeholder(tactic)
    family = str(action.get("tactic_family") or "procedure_transform")
    if family not in {"procedure_transform", "targeted_inline"}:
        family = "procedure_transform"
    item_id = (
        "program_full_prefix_split"
        if (
            action_kind == "expose_asymmetric_prefix"
            and str(action.get("proof_intent") or "") == "full_prefix_post_normalization"
        ) else
        "program_seq_cut" if is_seq_cut else
        "program_wrapper_open" if action_kind == "open_one_wrapper" else
        "program_frontier_transform"
    )
    preconditions = [
        "check or fill the displayed invariant before committing the transform",
        "after the slice is exposed, use the matching call lemma or residual closer in the generated subgoal",
        "re-run agent-view after the transform because the frontier changes",
    ]
    if has_placeholder:
        preconditions.insert(
            0,
            "the tactic contains a placeholder, so treat it as a shape hint, not a runnable tactic",
        )
    proof_intent = str(action.get("proof_intent") or "")
    live_fact_coverage = _invariant_live_fact_coverage(
        str(
            action.get("invariant_skeleton")
            or action.get("invariant")
            or tactic
        ),
        handles,
    )
    if proof_intent == "full_prefix_post_normalization":
        preconditions.insert(
            0,
            "this full-prefix split is for suffix/postcondition cleanup, not direct call-site exposure",
        )
    if live_fact_coverage.get("available"):
        preconditions.append(
            "compare `live_fact_coverage` before committing: weak cuts may be accepted by EC while dropping facts needed by the next call/control obligation",
        )
    return [_menu_item(
        item_id,
        tactic=tactic,
        tactic_family=family,
        action_type="strategy_hint",
        cost=(
            "expensive" if proof_intent == "full_prefix_post_normalization" else
            "cheap" if action_kind == "expose_call_pair_frontier" else
            "moderate" if has_placeholder else
            "cheap"
        ),
        why=str(
            action.get("reason")
            or action.get("why")
            or "ProgramIR edit script found the next program slice to expose."
        ),
        preconditions=preconditions,
        preserves=[
            "program alignment intent",
            "live call handles",
        ],
        cost_factors={
            "program_action_kind": action_kind,
            "program_plan_id": str(action.get("plan_id") or ""),
            "program_plan_kind": str(action.get("plan_kind") or ""),
            "proof_intent": proof_intent,
            "left_statement_count": int(action.get("left_statement_count") or 0),
            "right_statement_count": int(action.get("right_statement_count") or 0),
            "target_call_site_ids": list(action.get("target_call_site_ids") or []),
            "has_placeholder": has_placeholder,
            "requires_instantiation": bool(
                action.get("requires_instantiation") or has_placeholder
            ),
            "missing_slots": (
                ["full-prefix invariant"]
                if proof_intent == "full_prefix_post_normalization" else
                []
            ),
            "live_fact_coverage": live_fact_coverage,
        },
        program_rank=int(action.get("rank") or 9999),
        scheduler_role="program_frontier_exposure",
    )]


def _planned_frontier_exposure(handles: dict[str, Any]) -> dict[str, Any]:
    for handle in _list(handles.get("callable_lemmas")):
        if not isinstance(handle, dict):
            continue
        if not bool(handle.get("requires_cut_to_frontier")):
            continue
        for plan in _list(handle.get("program_action_plans")):
            if not isinstance(plan, dict):
                continue
            for action in _list(plan.get("phase_order")):
                if not isinstance(action, dict):
                    continue
                kind = str(action.get("kind") or "")
                if kind not in {
                    "expose_asymmetric_prefix",
                    "expose_call_pair_frontier",
                    "expose_last_call_frontier",
                }:
                    continue
                tactic = str(action.get("tactic_hint") or "").strip()
                if not tactic:
                    continue
                return {
                    "tactic": tactic,
                    "why": (
                        "ProgramIR found a live named call lemma behind the "
                        "current last-call frontier; use the planned sequence "
                        "split to expose that call before applying the lemma."
                    ),
                    "precondition": (
                        "fill the sequence invariant so it preserves the "
                        "named call lemma postcondition"
                    ),
                    "program_action": {
                        "kind": kind,
                        "lemma": str(handle.get("lemma") or ""),
                        "plan_id": str(plan.get("id") or ""),
                        "tactic_hint": tactic,
                    },
                }
    return {}


def _invariant_looks_noisy(invariant: str) -> bool:
    if not invariant:
        return True
    bad_tokens = {"while", "witness", "nth", "block", "post ="}
    lowered = invariant.lower()
    return any(token in lowered for token in bad_tokens)


def _double_quoted_tool_arg(value: str) -> str:
    escaped = str(value or "").replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _call_instantiation_hint(lemma: str, missing_slots: list[str]) -> str:
    slots = ", ".join(missing_slots[:6]) if missing_slots else "required signature slots"
    return (
        f"Resolve call arguments for `{lemma}` before `call`: missing {slots}."
    )


def _instantiation_preconditions(missing_slots: list[str]) -> list[str]:
    if missing_slots:
        return [
            "do not probe the naked `call <lemma>.` form while required slots are unbound",
            "bind these roles from the current call site or lemma signature first: "
            + ", ".join(missing_slots[:6]),
        ]
    return [
        "do not probe the naked `call <lemma>.` form until required signature slots are bound",
        "inspect the signature and current call-site arguments before choosing a call form",
    ]


def _instantiated_template_menu_items(handles: dict[str, Any]) -> list[dict[str, Any]]:
    bindings = _dict(handles.get("instantiation_bindings"))
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in _list(bindings.get("items")):
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "")
        if not name:
            continue
        resolved = resolution_for_name(_dict(handles.get("name_resolution")), name)
        if resolved and not resolved.get("exact_signature_known"):
            continue
        call_elaboration = _dict(item.get("call_elaboration"))
        skip_naked_templates = False
        if call_elaboration.get("available"):
            tactic = str(call_elaboration.get("tactic_template") or "").strip()
            direct_ecall = str(
                call_elaboration.get("direct_ecall_template") or ""
            ).strip()
            skip_naked_templates = bool(call_elaboration.get("requires_exlim"))
            if tactic and tactic not in seen:
                seen.add(tactic)
                lifted = [
                    _dict(arg) for arg in _list(
                        call_elaboration.get("lifted_value_arguments")
                    )
                    if isinstance(arg, dict)
                ]
                precondition_coverage = _dict(
                    call_elaboration.get("lemma_precondition_coverage")
                )
                candidate = _menu_item(
                    f"instantiated_call_elaboration_{_safe_id(name)}",
                    tactic=tactic,
                    tactic_family="call_named_equiv",
                    action_type="strategy_hint",
                    cost="cheap",
                    why=(
                        f"Name resolution found value parameters for `{name}` "
                        "that come from current call-site program expressions. "
                        "Lift those expressions with `exlim` before probing the "
                        "call lemma, instead of guessing naked call arguments."
                    ),
                    preconditions=[
                        *[
                            str(p) for p in _list(
                                call_elaboration.get("preconditions")
                            )
                            if str(p)
                        ],
                        "this is neutral plumbing for the lemma arguments, not a proof that the lemma is the right strategy",
                    ],
                    preserves=["call-site layer", "current procedure frontier"],
                    cost_factors={
                        "lemma": name,
                        "requires_instantiation": True,
                        "call_elaboration_status": str(
                            call_elaboration.get("status") or ""
                        ),
                        "preferred_call_form": "exlim_then_call_fallback",
                        "alternative_direct_ecall_template": direct_ecall,
                        "alternative_direct_ecall_status": (
                            "syntax_sensitive_not_frontline"
                            if direct_ecall else ""
                        ),
                        "suppressed_naked_instantiated_templates": _list(
                            call_elaboration.get("naked_instantiated_templates")
                        ),
                        "lifted_value_arguments": lifted,
                        "unresolved_non_value_slots": _list(
                            call_elaboration.get("unresolved_non_value_slots")
                        ),
                        "lemma_precondition_coverage": precondition_coverage,
                        "authority_rank": 70,
                    },
                    program_rank=0,
                )
                candidate["call_elaboration"] = call_elaboration
                out.append(candidate)
        if skip_naked_templates:
            continue
        for idx, template in enumerate(_list(item.get("instantiated_templates"))):
            if not isinstance(template, dict):
                continue
            tactic = str(template.get("tactic") or "").strip()
            if not tactic or tactic in seen or _has_unfilled_angle_placeholder(tactic):
                continue
            seen.add(tactic)
            confidence = str(template.get("confidence") or "medium")
            bound_family = _bound_template_family(tactic)
            costs = _template_cost_factors(
                bound_family=bound_family,
                confidence=confidence,
                tactic=tactic,
            )
            pr_normal = _dict(handles.get("pr_normal_form"))
            normal_kind = str(pr_normal.get("normalization_kind") or "")
            arithmetic_shell = normal_kind == "union_bound_or_additive_inequality"
            action_type = "probe_tactic"
            cost = "cheap"
            why = (
                f"Name resolution plus context binding produced a concrete "
                f"candidate for `{name}`; probe it with EC before committing."
            )
            preconditions = [
                "signature slots came from the resolved lemma declaration",
                "argument candidates were extracted from current context/goal",
                "probe with `-try` before committing the tactic",
            ]
            if bound_family in {"pr_path_plan", "rewrite"} and arithmetic_shell:
                action_type = "strategy_hint"
                cost = "moderate"
                why = (
                    f"Name resolution can instantiate `{name}`, but the current "
                    "Pr goal is an additive/inequality shell; use this as "
                    "context for a Pr arithmetic/have-chain plan instead of a "
                    "direct rewrite probe."
                )
                preconditions = [
                    "direct rewrite may fail when the lemma only matches a sub-expression under an inequality/additive shell",
                    "first build the appropriate intermediate inequality/equality or use a Pr arithmetic plan",
                    "probe a concrete rewrite only after the matching side and direction are explicit",
                ]
                costs["pr_arithmetic_shell"] = normal_kind
            pr_elaboration = _compact_pr_elaboration(
                _dict(item.get("pr_elaboration"))
            )
            endpoint_mismatch = any(
                str(diag.get("code") or "") == "pr_elaboration.no_matching_pr_endpoint"
                for diag in _list(pr_elaboration.get("diagnostics"))
                if isinstance(diag, dict)
            )
            if bound_family == "rewrite" and endpoint_mismatch:
                action_type = "strategy_hint"
                cost = "moderate"
                why = (
                    f"Name resolution can instantiate `{name}`, but the current "
                    "Pr endpoint does not match the lemma's endpoint template; "
                    "build an intermediate Pr equality or wrapper bridge first."
                )
                preconditions = [
                    "do not probe this direct rewrite on the raw endpoint",
                    "first expose a Pr endpoint matching the lemma signature",
                    "then probe the instantiated rewrite after the endpoint match is explicit",
                ]
                costs["pr_endpoint_match"] = "missing"
            if (
                call_elaboration.get("available")
                and tactic.startswith("call (")
            ):
                action_type = "strategy_hint"
                cost = "moderate"
                why = (
                    f"Name resolution can instantiate `{name}`, but the "
                    "selected value arguments came from program call-site "
                    "expressions. Use the exlim/call elaboration unless those "
                    "values are already introduced as logical variables."
                )
                preconditions = [
                    "naked `call (LEMMA args)` is valid only after the displayed values have been lifted or are already logical variables",
                    "otherwise prefer the corresponding `exlim ...; call (...)` strategy hint",
                    "probe either form before committing",
                ]
                costs["call_elaboration_available"] = True
            if pr_elaboration:
                costs["pr_elaboration_status"] = str(
                    pr_elaboration.get("status") or "elaborated"
                )
                costs.update(
                    _pr_endpoint_relevance_cost_factors(
                        handles,
                        name=name,
                        pr_elaboration=pr_elaboration,
                    )
                )
            candidate = _menu_item(
                f"instantiated_{_safe_id(name)}_{idx}",
                tactic=tactic,
                tactic_family="instantiated_template",
                action_type=action_type,
                cost=cost,
                why=why,
                preconditions=preconditions,
                preserves=["proof state until the probe is accepted"],
                cost_factors=costs,
            )
            if "_" in _template_args(tactic):
                candidate["preconditions"].append(
                    "template still uses `_`; EC must infer that argument"
                )
            if pr_elaboration:
                candidate["pr_elaboration"] = pr_elaboration
                for diagnostic in _list(pr_elaboration.get("diagnostics"))[:2]:
                    if not isinstance(diagnostic, dict):
                        continue
                    message = str(diagnostic.get("message") or "")
                    avoid = str(diagnostic.get("avoid") or "")
                    if message:
                        candidate["preconditions"].append(message)
                    if avoid:
                        candidate["preconditions"].append(
                            f"do not rewrite the concrete endpoint as `{avoid}`"
                        )
            candidate["confidence"] = confidence
            out.append(candidate)
    return out


def _pr_typed_bridge_chain_menu_items(handles: dict[str, Any]) -> list[dict[str, Any]]:
    path_plan = _dict(handles.get("pr_path_plan"))
    candidate_by_action: dict[str, dict[str, Any]] = {}
    for candidate in _list(_dict(handles.get("pr_typed_bridge_frontend")).get("wrapper_bridges")):
        if not isinstance(candidate, dict):
            continue
        action = str(candidate.get("tactic") or "")
        if action:
            candidate_by_action[action] = candidate

    def bridge_menu_item(
        *,
        action: str,
        candidate: dict[str, Any],
        path: dict[str, Any] | None = None,
        hop: dict[str, Any] | None = None,
        fallback_reason: str = "",
    ) -> dict[str, Any]:
        path = _dict(path)
        hop = _dict(hop)
        path_status = str(
            path.get("status") or "frontier_bridge_without_complete_path"
        )
        obligation_status = (
            "complete" if path_status == "complete" and not fallback_reason
            else "partial"
        )
        generated_obligations = (
            [
                "bridge_subproof",
                "possible_oracle_obligations",
                "possible_init_postlude",
            ]
            if obligation_status != "complete" else
            []
        )
        cost_factors: dict[str, Any] = {
            "path_status": path_status,
            "path_side": str(path.get("side") or ""),
            "source": str(
                hop.get("source")
                or candidate.get("lhs_game")
                or candidate.get("source_endpoint_key")
                or ""
            ),
            "target": str(
                hop.get("target")
                or candidate.get("rhs_game")
                or candidate.get("target_endpoint_key")
                or ""
            ),
            "adapter_module": str(candidate.get("adapter_module") or ""),
            "bridge_lemma": str(candidate.get("bridge_lemma") or ""),
            "obligation_completeness": obligation_status,
            "generated_obligations": generated_obligations,
            "obligation_closure_plan_complete": obligation_status == "complete",
        }
        if path:
            cost_factors["hops"] = list(path.get("hops") or [])
        if fallback_reason:
            cost_factors["fallback_reason"] = fallback_reason
        return _menu_item(
            f"pr_typed_bridge_chain_{len(items)}",
            tactic=action,
            tactic_family="pr_path_plan",
            action_type=(
                "probe_tactic"
                if obligation_status == "complete" else
                "strategy_hint"
            ),
            cost="cheap" if obligation_status == "complete" else "moderate",
            why=str(
                candidate.get("reason")
                or "Typed Pr bridge exposes the next endpoint in the Pr graph."
            ) + (
                ""
                if obligation_status == "complete" else
                (
                    " This is only a partial bridge plan: it may open "
                    "oracle/init/postlude obligations, so inspect/probe the "
                    "obligation map before committing it as a clean rewrite."
                )
            ),
            preconditions=[
                (
                    "probe this full `have ... by ...` bridge; do not commit a naked `have` that only opens an obligation"
                    if obligation_status == "complete" else
                    "treat this as a bridge strategy until the generated obligations have a closure plan"
                ),
                "keep lemma value arguments separate from concrete procedure endpoint arguments",
                "if this bridge closes and the endpoint still matches, the typed Pr path remains route context",
            ],
            preserves=["Pr abstraction", "typed Pr bridge path"],
            cost_factors=cost_factors,
            program_rank=len(items),
        )

    paths: list[dict[str, Any]] = []
    recommended = _dict(path_plan.get("recommended_path"))
    if recommended:
        paths.append(recommended)
    for partial in _list(path_plan.get("partial_paths")):
        if isinstance(partial, dict):
            paths.append(partial)

    items: list[dict[str, Any]] = []
    seen_actions: set[str] = set()
    for path in paths:
        for hop in _list(path.get("hops")):
            if not isinstance(hop, dict):
                continue
            if str(hop.get("edge_kind") or "") not in {
                "synthetic_bridge",
                "verified_bridge",
            }:
                continue
            action = str(hop.get("action_hint") or "").strip()
            if not action or action in seen_actions:
                continue
            if action not in candidate_by_action:
                continue
            seen_actions.add(action)
            candidate = candidate_by_action.get(action, {})
            items.append(bridge_menu_item(
                action=action,
                candidate=candidate,
                path=path,
                hop=hop,
            ))
            break
    if not items:
        for action, candidate in candidate_by_action.items():
            if not action or action in seen_actions:
                continue
            seen_actions.add(action)
            items.append(bridge_menu_item(
                action=action,
                candidate=candidate,
                fallback_reason=(
                    "typed wrapper bridge is live, but the Pr path planner has "
                    "not connected the full endpoint chain yet"
                ),
            ))
            if len(items) >= 3:
                break
    return items[:3]


def _has_live_pr_typed_bridge_path(handles: dict[str, Any]) -> bool:
    if any(
        isinstance(candidate, dict) and str(candidate.get("tactic") or "")
        for candidate in _list(
            _dict(handles.get("pr_typed_bridge_frontend")).get("wrapper_bridges")
        )
    ):
        return True
    path_plan = _dict(handles.get("pr_path_plan"))
    paths: list[dict[str, Any]] = []
    recommended = _dict(path_plan.get("recommended_path"))
    if recommended:
        paths.append(recommended)
    for partial in _list(path_plan.get("partial_paths")):
        if isinstance(partial, dict):
            paths.append(partial)
    for path in paths:
        for hop in _list(path.get("hops")):
            action = str(_dict(hop).get("action_hint") or "")
            if (
                isinstance(hop, dict)
                and str(hop.get("edge_kind") or "") in {
                "synthetic_bridge",
                "verified_bridge",
                }
                and action
                and not action.startswith("Pr structural bridge:")
            ):
                return True
    return False


def _pr_wrapper_bridge_menu_items(handles: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for idx, candidate in enumerate(_list(handles.get("pr_wrapper_bridge_candidates"))[:3]):
        if not isinstance(candidate, dict):
            continue
        tactic = str(candidate.get("tactic") or "").strip()
        if not tactic:
            continue
        lemma = str(candidate.get("bridge_lemma") or "")
        items.append(_menu_item(
            f"pr_wrapper_bridge_{idx}",
            tactic=tactic,
            tactic_family="pr_path_plan",
            action_type="probe_tactic",
            cost="cheap",
            why=str(
                candidate.get("reason")
                or "Normalize an experiment-wrapper Pr endpoint when it makes the next Pr rewrite applicable."
            ),
            preconditions=[
                "probe this have-bridge before committing it",
                "the target Pr term is derived from the visible MainD endpoint and the matched Pr rewrite declaration",
                "if the bridge fails, inspect the wrapper module definitions rather than guessing procedure arguments",
            ],
            preserves=["Pr abstraction", "future Pr rewrite handle"],
            cost_factors={
                "bridge_lemma": lemma,
                "source_endpoint": str(candidate.get("source_endpoint_key") or ""),
                "target_endpoint": str(candidate.get("target_endpoint_key") or ""),
                "experiment_wrapper": str(candidate.get("experiment_wrapper_key") or ""),
            },
            program_rank=idx,
        ))
    return items


def _pr_path_signature_lookup_items(handles: dict[str, Any]) -> list[dict[str, Any]]:
    path_plan = _dict(handles.get("pr_path_plan"))
    name_resolution = _dict(handles.get("name_resolution"))
    recent_rewrite = str(handles.get("recently_rewritten_pr_lemma") or "")
    ranked: list[tuple[int, str, str, str]] = []

    recommended = _dict(path_plan.get("recommended_path"))
    for lemma in _path_lemmas(recommended):
        ranked.append((0, lemma, "recommended_path", "complete Pr path"))

    for path_index, partial in enumerate(_list(path_plan.get("partial_paths"))):
        if not isinstance(partial, dict):
            continue
        label = str(partial.get("side") or "partial")
        for lemma_index, lemma in enumerate(_path_lemmas(partial)):
            rank = 10 + path_index * 4 + lemma_index
            ranked.append((rank, lemma, "partial_path", f"{label}-side partial Pr path"))

    out: list[dict[str, Any]] = []
    seen_actions: set[str] = set()
    seen_lemmas: set[str] = set()
    for rank, lemma, path_kind, path_label in sorted(ranked):
        if not lemma or lemma in seen_lemmas:
            continue
        if _lemma_leaf(lemma) == recent_rewrite:
            continue
        seen_lemmas.add(lemma)
        resolved = resolution_for_name(name_resolution, lemma)
        lookup_action = str(resolved.get("signature_lookup_action") or "")
        if not lookup_action or resolved.get("exact_signature_known"):
            continue
        if lookup_action in seen_actions:
            continue
        seen_actions.add(lookup_action)
        out.append(_menu_item(
            f"pr_path_lookup_{_safe_id(lemma)}",
            tactic=lookup_action,
            tactic_family="signature_lookup",
            action_type="inspection_action",
            cost="free",
            why=(
                f"Resolve exact signature for `{lemma}` because it is on the "
                f"{path_label}; do this before guessing rewrite/apply arguments."
            ),
            preserves=["proof state"],
            cost_factors={
                "path_kind": path_kind,
                "path_rank": rank,
                "name_resolution_status": str(
                    resolved.get("resolution_status") or ""
                ),
            },
            program_rank=rank,
        ))
    return out


def _external_pr_bridge_frontier_items(handles: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = _external_pr_bridge_frontier_candidates(handles)
    if not candidates:
        return []
    items = []
    for idx, item in enumerate(candidates[:3]):
        action = str(item.get("action") or "")
        lemma = str(item.get("lemma") or "")
        if not action:
            continue
        items.append(_menu_item(
            f"sig_external_pr_bridge_{_safe_id(lemma or str(idx))}",
            tactic=action,
            tactic_family="signature_lookup",
            action_type="strategy_hint",
            cost="free",
            why=(
                f"Optional Pr checkpoint lookup for `{lemma}`. Use it when "
                "forming an intermediate equality, but do not let a lookup-only "
                "checkpoint block an otherwise natural `byequiv` lowering."
            ),
            preconditions=[
                "current layer is Pr",
                "lookup does not mutate the proof state",
                "prefer a daemon-verified bridge/action over lookup-only checkpoints",
            ],
            preserves=["proof state"],
            cost_factors={
                "lemma": lemma,
                "source": str(item.get("producer") or ""),
            },
        ))
    return items


def _external_pr_bridge_frontier_candidates(handles: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for candidate in _list(handles.get("external_candidates")):
        if not isinstance(candidate, dict):
            continue
        action = str(candidate.get("action") or "").strip()
        lemma = _candidate_lemma_name(candidate)
        if not lemma or not action or lemma in seen:
            continue
        if str(candidate.get("tactic_family") or "") != "signature_lookup":
            continue
        if not _looks_like_pr_bridge_name(lemma):
            continue
        seen.add(lemma)
        out.append({
            "lemma": lemma,
            "action": action,
            "producer": str(candidate.get("producer") or ""),
        })
    return out


def _looks_like_pr_bridge_name(name: str) -> bool:
    leaf = str(name or "").rsplit(".", 1)[-1]
    return bool(re.match(r"^pr_[A-Za-z0-9_']+$", leaf))


def _path_lemmas(path: dict[str, Any]) -> list[str]:
    lemmas = [
        str(item) for item in _list(path.get("lemmas"))
        if str(item)
    ]
    if lemmas:
        return _dedupe_strings(lemmas)
    out: list[str] = []
    for hop in _list(path.get("hops")):
        if not isinstance(hop, dict):
            continue
        lemma = str(hop.get("lemma") or "")
        if lemma:
            out.append(lemma)
    return _dedupe_strings(out)


def _diagnostics(
    layer: str,
    liveness: dict[str, Any],
    handles: dict[str, Any],
    name_resolution: dict[str, Any],
    destructive_moves: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    live_calls = int(liveness.get("live_call_site_count") or 0)
    live_lemmas = int(liveness.get("live_callable_lemma_count") or 0)
    callable_now = int(liveness.get("callable_now_lemma_count") or 0)
    non_frontier = int(liveness.get("non_frontier_callable_lemma_count") or 0)
    oracle_obligations = int(liveness.get("oracle_obligation_handle_count") or 0)
    unfoldables = [
        _dict(item) for item in _list(handles.get("unfoldable_goal_heads"))
        if isinstance(item, dict) and item.get("name")
    ]
    if layer == "ambient_logic" and unfoldables:
        names = [str(item.get("name") or "") for item in unfoldables[:4]]
        out.append({
            "code": "proof_ir.unfoldable_goal_heads",
            "severity": "info",
            "message": (
                "Current residual goal mentions unfoldable definition(s): "
                + ", ".join(names)
                + ". Use `rewrite /NAME` before SMT when those predicates "
                "block simplification; these names are not smt(...) lemma hints."
            ),
        })
    if layer == "call_site" and live_calls:
        if oracle_obligations:
            skeleton = _dict(handles.get("adversary_invariant_skeleton"))
            obligations = [
                str(item.get("lemma") or "")
                for item in _list(skeleton.get("oracle_obligations"))
                if isinstance(item, dict) and item.get("lemma")
            ][:4]
            out.append({
                "code": "proof_ir.oracle_obligation_handles",
                "severity": "info",
                "message": (
                    "ProofIR sees oracle-obligation handle(s) "
                    f"({', '.join(obligations)}), but the current frontier is "
                    "an abstract adversary call. An adversary invariant call "
                    "is the route that generates the oracle subgoals where "
                    "those handles become local context."
                ),
            })
        if live_lemmas and non_frontier and not callable_now:
            lemmas = [
                str(h.get("lemma") or "")
                for h in _list(handles.get("callable_lemmas"))
                if isinstance(h, dict)
                and h.get("lemma")
                and h.get("requires_cut_to_frontier")
            ][:4]
            out.append({
                "code": "proof_ir.call_handles_not_frontier",
                "severity": "info",
                "message": (
                    "ProofIR sees live named call handle(s), but none is "
                    "currently at EasyCrypt's last-call frontier "
                    f"({', '.join(lemmas)}). `call <lemma>` may fail until "
                    "wp/seq/targeted transforms expose the matching call as "
                    "the last statement."
                ),
                "repairs": [
                    (
                        "ProgramIR edit-script candidates such as `wp.`, "
                        "`seq`, or targeted inline can bring the matching "
                        "call to the last-call frontier."
                    ),
                    (
                        "After the frontier changes, re-run agent-view and "
                        "compare the matching `call <lemma>.` candidate."
                    ),
                    (
                        "Global `inline *` may hide live named call handles "
                        "for the current proof slice."
                    ),
                ],
            })
        if live_lemmas:
            lemmas = [
                str(h.get("lemma") or "")
                for h in _list(handles.get("callable_lemmas"))
                if isinstance(h, dict) and h.get("lemma")
            ][:4]
            out.append({
                "code": "proof_ir.live_call_handles",
                "severity": "warning",
                "message": (
                    "ProofIR layer is call_site: "
                    f"{live_calls} call site(s) and {live_lemmas} callable "
                    f"lemma handle(s) are live ({', '.join(lemmas)}). "
                    "`inline *` is a broad global transformation here and "
                    "can hide those handles; named calls and targeted inline "
                    "are route context for comparison."
                ),
                "repairs": [
                    (
                        "A named call lemma is a direct candidate only when "
                        "it is resolved and marked `direct_current_call` for "
                        "the current last-call frontier."
                    ),
                    (
                        "If a handle is live but not at the frontier, `wp`, "
                        "`seq`, or targeted inline may expose it."
                    ),
                    (
                        "Global `inline *` is safest when call handles are no "
                        "longer useful in the current proof slice."
                    ),
                ],
            })
        else:
            out.append({
                "code": "proof_ir.live_call_sites_no_handles",
                "severity": "info",
                "message": (
                    "ProofIR layer is call_site with live procedure calls, "
                    "but no callable lemma handle is currently attached. "
                    "Additional bridge/call lemma context may be relevant "
                    "before changing this frontier by global inlining."
                ),
            })
    if liveness.get("call_site_handles_consumed") and layer != "pr":
        last_inline = next(
            (m for m in reversed(destructive_moves) if m.get("kind") == "inline_all"),
            None,
        )
        out.append({
            "code": "proof_ir.call_sites_already_lowered",
            "severity": "info",
            "message": (
                "ProofIR sees no live call sites after a prior `inline *`"
                + (
                    f" at tactic {last_inline.get('tactic_index')}."
                    if isinstance(last_inline, dict) else "."
                )
                + " Continue at procedure/ambient layer, or undo if a call "
                "lemma is needed."
            ),
        })
    out.extend(_sampling_ordering_diagnostics(handles))
    summary = _dict(name_resolution.get("summary"))
    needs_lookup = int(summary.get("needs_lookup") or 0)
    unresolved = int(summary.get("unresolved") or 0)
    if needs_lookup or unresolved:
        actions = [
            str(action) for action in _list(name_resolution.get("lookup_actions"))
            if action
        ][:4]
        out.append({
            "code": "proof_ir.name_resolution_lookup_required",
            "severity": "info",
            "message": (
                "ProofIR name resolution found "
                f"{needs_lookup} imported/cross-scope handle(s) needing `-sig` "
                f"and {unresolved} unresolved handle(s). "
                + (
                    "If pursuing a handle route, possible read-only lookups: "
                    + ", ".join(actions)
                    + ". Inspect only the handle whose route is being tested."
                    if actions else
                    "Use `-sig <name>` only for the handle route being tested."
                )
            ),
        })
    return out


def _native_ast_search_menu_items(handles: dict[str, Any]) -> list[dict[str, Any]]:
    return build_native_ast_search_menu_items(handles)


def _menu_item(
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
    return build_menu_item(
        item_id,
        tactic=tactic,
        tactic_family=tactic_family,
        action_type=action_type,
        cost=cost,
        why=why,
        preconditions=preconditions,
        preserves=preserves,
        destroys=destroys,
        cost_factors=cost_factors,
        program_rank=program_rank,
        scheduler_role=scheduler_role,
    )


def _bound_template_family(tactic: str) -> str:
    low = tactic.strip().lower()
    if re.match(r"^e?call\b", low):
        return "call_named_equiv"
    if re.match(r"^rewrite\b", low):
        return "rewrite"
    if re.match(r"^byequiv\b", low):
        return "pr_bridge"
    if re.match(r"^(have|apply|exact)\b", low):
        return "pr_path_plan"
    return "unknown"


def _template_cost_factors(
    *,
    bound_family: str,
    confidence: str,
    tactic: str,
) -> dict[str, Any]:
    factors = {
        "bound_tactic_family": bound_family,
        "binding_confidence": confidence,
        "source": "ec_instantiation_binding",
        "expansion": "low",
        "irreversibility": "low",
        "lost_handles": 0,
    }
    if "_" in _template_args(tactic):
        factors["uses_ec_inference_placeholder"] = True
    return factors


def _pr_endpoint_relevance_cost_factors(
    handles: dict[str, Any],
    *,
    name: str,
    pr_elaboration: dict[str, Any],
) -> dict[str, Any]:
    """Tie-break instantiated Pr rewrites by endpoint-aware recall order.

    Name/type binding can instantiate several generic Pr rewrites that all
    mention the visible endpoint.  The earlier pr_rewrite_candidates list is
    produced by the Pr frontend's endpoint scan, so preserving that order as a
    late tie-break keeps the most endpoint-relevant bridge ahead without
    hiding lower-ranked alternatives.
    """
    if not pr_elaboration:
        return {}
    endpoint_rank = 50
    diagnostics = [
        _dict(item) for item in _list(pr_elaboration.get("diagnostics"))
        if isinstance(item, dict)
    ]
    if any(
        str(item.get("code") or "") == "pr_elaboration.no_matching_pr_endpoint"
        for item in diagnostics
    ):
        endpoint_rank = 80
    elif _list(pr_elaboration.get("endpoint_matches")):
        endpoint_rank = 0
    elif _list(pr_elaboration.get("endpoint_argument_separation")):
        endpoint_rank = 1

    out: dict[str, Any] = {
        "pr_endpoint_relevance_rank": endpoint_rank,
    }
    candidate_index = _pr_rewrite_candidate_index(handles, name)
    if candidate_index is not None:
        out["pr_rewrite_candidate_index"] = candidate_index
    return out


def _pr_rewrite_candidate_index(
    handles: dict[str, Any],
    name: str,
) -> int | None:
    leaf = _lemma_leaf(name)
    if not leaf:
        return None
    for idx, candidate_name in enumerate(
        _candidate_names(_dict(handles).get("pr_rewrite_candidates"))
    ):
        if _lemma_leaf(candidate_name) == leaf:
            return idx
    return None


def _has_unfilled_angle_placeholder(tactic: str) -> bool:
    return bool(re.search(r"<(?!:)[^>]+>", tactic))


def _template_args(tactic: str) -> list[str]:
    match = re.search(r"\(([^()]*)\)", tactic)
    if not match:
        return []
    pieces = match.group(1).strip().split()
    return pieces[1:] if len(pieces) > 1 else []


def _invariant_live_fact_coverage(
    invariant_text: str,
    handles: dict[str, Any],
    *,
    skeleton: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a neutral live-fact budget for a seq/call invariant candidate."""
    frontend = _dict(_dict(handles).get("procedure_body_frontend"))
    live_state = _dict(frontend.get("live_state_summary"))
    region = _dict(frontend.get("asymmetric_instrumentation_region"))
    skel = _dict(skeleton) or _dict(handles.get("invariant_skeleton"))
    text = str(invariant_text or "")
    preserved_vars = _coverage_preserved_vars(text, skel)
    required_post = _coverage_strings(live_state.get("post_live_vars"))
    if not required_post:
        post_side = _dict(skel.get("post_side_variables"))
        required_post = _dedupe_strings([
            *_coverage_strings(skel.get("shared_equalities")),
            *_coverage_strings(skel.get("dataflow_equalities")),
            *[
                str(item)
                for values in post_side.values()
                for item in _list(values)
                if str(item)
            ],
        ])
    required_pre = _coverage_strings(live_state.get("pre_live_vars"))
    proof_relevant_extra = _coverage_strings(
        region.get("proof_relevant_extra_vars")
    )
    one_sided_extra = _dedupe_strings([
        *_coverage_strings(region.get("left_extra_written_vars")),
        *_coverage_strings(region.get("right_extra_written_vars")),
    ])
    shared_core = _coverage_strings(region.get("shared_written_vars"))
    required_visible = _dedupe_strings([
        *required_post,
        *proof_relevant_extra,
        *shared_core,
    ])
    if not (
        preserved_vars
        or required_visible
        or required_pre
        or one_sided_extra
    ):
        return {"available": False, "reason": "no_visible_live_budget"}
    missing_post = [
        var for var in required_post
        if not _coverage_var_is_preserved(var, text, preserved_vars)
    ]
    missing_extra = [
        var for var in proof_relevant_extra
        if not _coverage_var_is_preserved(var, text, preserved_vars)
    ]
    missing_shared = [
        var for var in shared_core
        if not _coverage_var_is_preserved(var, text, preserved_vars)
    ]
    missing = _dedupe_strings([*missing_post, *missing_extra, *missing_shared])
    if not required_visible:
        label = "not_applicable"
    elif not missing:
        label = "covers_visible_live_facts"
    elif preserved_vars:
        label = "partial_visible_live_coverage"
    else:
        label = "weak_visible_live_coverage"
    return {
        "available": True,
        "kind": "invariant_live_fact_coverage",
        "coverage_label": label,
        "preserved_vars": preserved_vars[:24],
        "required_post_live_vars": required_post[:16],
        "required_pre_live_vars": required_pre[:16],
        "shared_core_vars": shared_core[:16],
        "one_sided_extra_vars": one_sided_extra[:16],
        "proof_relevant_extra_vars": proof_relevant_extra[:16],
        "missing_post_live_vars": missing_post[:16],
        "missing_one_sided_extra_vars": missing_extra[:16],
        "missing_shared_core_vars": missing_shared[:16],
        "missing_visible_vars": missing[:24],
        "notes": _coverage_notes(label, missing),
        "strategy_boundary": (
            "This is a live-fact accounting pass. It does not prove the "
            "invariant, and it does not force a tactic; it tells the prover "
            "what information the candidate appears to carry or drop."
        ),
        "epistemic_status": "shallow_dataflow_coverage_not_typecheck",
    }


def _coverage_preserved_vars(text: str, skeleton: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for match in re.finditer(r"=\{\s*([^}]*)\s*\}", str(text or "")):
        values.extend(part.strip() for part in match.group(1).split(","))
    for name, _side in re.findall(
        r"([A-Za-z_][A-Za-z0-9_'.]*(?:\.[A-Za-z_][A-Za-z0-9_'.]*)*)\{([12])\}",
        str(text or ""),
    ):
        values.append(name)
    for key in (
        "shared_equalities",
        "dataflow_equalities",
        "carried_precondition_equalities",
    ):
        values.extend(_coverage_strings(skeleton.get(key)))
    for atom in _list(skeleton.get("conjuncts")):
        if isinstance(atom, dict):
            values.extend(_coverage_strings(atom.get("vars")))
    return _dedupe_strings(
        value for value in values
        if _coverage_safe_var(str(value))
    )


def _coverage_strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return _dedupe_strings(
        str(item).strip()
        for item in value
        if str(item).strip()
    )


def _coverage_var_is_preserved(
    var: str,
    text: str,
    preserved_vars: list[str],
) -> bool:
    raw = str(var or "").strip()
    if not raw:
        return False
    leaf = raw.rsplit(".", 1)[-1]
    candidates = _dedupe_strings([raw, leaf])
    preserved_nodes = {
        node
        for item in preserved_vars
        for node in _dedupe_strings([item, item.rsplit(".", 1)[-1]])
    }
    if any(candidate in preserved_nodes for candidate in candidates):
        return True
    haystack = str(text or "")
    return any(
        candidate
        and re.search(
            rf"(?<![A-Za-z0-9_'.]){re.escape(candidate)}(?:\{{[12]\}})?(?![A-Za-z0-9_'])",
            haystack,
        )
        for candidate in candidates
    )


def _coverage_safe_var(value: str) -> bool:
    text = str(value or "").strip()
    if not text or text[0].isdigit():
        return False
    return all(ch.isalnum() or ch in "_.'" for ch in text)


def _coverage_notes(label: str, missing: list[str]) -> list[str]:
    if label == "covers_visible_live_facts":
        return [
            "candidate appears to preserve the visible live facts extracted from the current pre/post and one-sided state",
        ]
    if label == "partial_visible_live_coverage":
        if missing:
            return [
                "candidate carries some visible facts but may leave a frame/precondition residual",
                "missing: " + ", ".join(missing[:8]),
            ]
        return [
            "candidate carries some visible facts; remaining obligations should be checked by EasyCrypt",
        ]
    if label == "weak_visible_live_coverage":
        return [
            (
                "candidate does not visibly carry the proof-relevant state "
                "budget; EC may accept the cut but leave substantial residual "
                "obligations"
            ),
        ]
    return [
        "no concrete visible live facts were required by this shallow pass",
    ]




def _build_action_surface(
    *,
    layer: str,
    goal_kind: str,
    liveness: dict[str, Any],
    handles: dict[str, Any],
    program_ir: dict[str, Any],
    name_resolution: dict[str, Any],
    instantiation_bindings: dict[str, Any],
    legality: dict[str, Any],
    latest_transition: dict[str, Any],
    destructive_moves: list[dict[str, Any]],
) -> dict[str, Any]:
    """PASS 4 — the read-only action surface over the (frozen) handles: phase
    guidance + legality, the candidate menu (post-processed via the shared
    pipeline + PR-bridge ordering), and diagnostics."""
    phase = _phase_guidance(layer, goal_kind, liveness, handles)
    phase["legality"] = legality
    menu = _candidate_menu(layer, goal_kind, liveness, handles, program_ir=program_ir)
    menu = _apply_candidate_pipeline(
        menu,
        name_resolution=name_resolution,
        instantiation_bindings=instantiation_bindings,
        legality=legality,
        liveness=liveness,
        current_layer=layer,
        latest_transition=latest_transition,
    )
    menu = normalize_action_candidates(menu)
    # The compiler surfaces state-derived FACTS, not move GUIDANCE. Drop hardcoded
    # bare tactics, placeholder templates, and route-plan prose at the source so
    # they never enter `candidate_menu` (classified per the FINAL tactic, after the
    # pipeline has filled/rewritten any template). State-derived facts and
    # daemon-verified moves are kept. See `classify_info_kind` in ec_action_contracts.
    menu = [item for item in menu if _dict(item).get("info_kind") != "guidance"]
    menu = _order_instantiated_pr_bridges(menu)
    diagnostics = _diagnostics(
        layer,
        liveness,
        handles,
        name_resolution,
        destructive_moves,
    )
    return {"phase": phase, "menu": menu, "diagnostics": diagnostics}


def _order_instantiated_pr_bridges(menu: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Order the instantiated Pr-rewrite bridges by their FACTUAL chain index.

    With the heuristic candidate_rank ordering gone, the menu keeps its structural
    build order. The one factual sequence that order does not already give is the
    Pr bridge game-hop chain (`pr_rewrite_candidate_index`) — the order the proof
    rewrites the endpoints in (e.g. RO -> FinRO -> FunRO). Reorder ONLY those
    bridge items, in place among their existing menu slots, so nothing else moves.
    """
    slots = [
        i for i, item in enumerate(menu)
        if isinstance(item, dict)
        and item.get("tactic_family") == "instantiated_template"
        and str(item.get("tactic") or "").startswith("rewrite (pr_")
    ]
    if len(slots) < 2:
        return menu

    def _chain_index(item: dict[str, Any]) -> int:
        value = _dict(item.get("cost_factors")).get("pr_rewrite_candidate_index")
        try:
            return int(value)
        except (TypeError, ValueError):
            return 9999

    ordered = sorted((menu[i] for i in slots), key=_chain_index)
    out = list(menu)
    for slot, item in zip(slots, ordered):
        out[slot] = item
    return out
