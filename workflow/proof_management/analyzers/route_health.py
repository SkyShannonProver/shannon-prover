"""Route-health evidence analyzer.

This pass owns route-health and structural-transition evidence for the current
workspace view. It is deliberately pure: it reads the aggregated node state and
returns evidence dictionaries, but does not mutate proof state or render the
final ProverWorkspaceView directly.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core.easycrypt.analysis.probability_budget import (
    analyze_probability_budget,
)
from workflow.proof_management.analyzers.common import (
    _dict,
    _drop_empty_precheck as _drop_empty,
    _list,
    _string_list,
)
from workflow.proof_management.analyzers.call_site import (
    _named_call_candidate_from_mapping,
    _view_has_live_call_site,
)
from workflow.proof_management.analyzers.pure_tail import (
    _looks_like_procedure_equivalence_obligation,
    _pure_tail_gap_analysis,
    looks_like_pure_tail_goal,
)
from workflow.proof_management.analyzers.seq_cut import (
    _latest_seq_tactic,
    _rewound_seq_cut_observation,
)
from workflow.proof_management.checkpoint_surface import (
    checkpoint_surface_item,
    history_hash,
    latest_inline_boundary as _latest_inline_boundary,
    ordered_checkpoint_indices,
    route_health_checkpoint,
    semantic_checkpoint_overrides,
)
from workflow.proof_management.frame_facts import (
    frame_boundary_facts,
    frame_fact_carried,
    frame_ledger_scope_start,
    pre_post_global_frame_gap,
    pre_post_sections,
    transitively_equal_terms,
    view_goal_text,
)
from workflow.proof_management.node_state import ProofNodeState
from workflow.proof_management.recovery import annotate_route_health_items
from workflow.proof_management.transitions import structural_transition_surface


@dataclass(frozen=True)
class RouteHealthAnalysis:
    route_health: list[dict[str, Any]] = field(default_factory=list)
    structural_transitions: list[dict[str, Any]] = field(default_factory=list)


class RouteHealthAnalyzer:
    """Build route-health evidence and route-level structural transitions."""

    def analyze(
        self,
        *,
        state: ProofNodeState,
        view: dict[str, Any] | None = None,
    ) -> RouteHealthAnalysis:
        workspace_view = dict(view or state.base_workspace_view)
        route_health = route_health_items(
            view=workspace_view,
            route_event_facts=state.route_event_facts,
            tactics=state.committed_tactics,
            file_path=state.file_path,
            project_root=Path(state.project_root or "."),
            replay_prefix_count=state.replay_prefix_count,
        )
        structural_transitions = structural_transition_items(
            view=workspace_view,
            route_event_facts=state.route_event_facts,
            route_health=route_health,
        )
        return RouteHealthAnalysis(
            route_health=route_health,
            structural_transitions=structural_transitions,
        )


def current_route_health(view: dict[str, Any]) -> list[dict[str, Any]]:
    candidate_moves = _dict(_dict(view).get("candidate_moves"))
    return [
        item
        for item in _list(candidate_moves.get("route_health"))
        if isinstance(item, dict)
    ]


_CONCEPT_CLUSTERS: tuple[dict[str, Any], ...] = (
    {
        "id": "bad_event_index_structure",
        "label": "bad-event index/list structure",
        "tokens": (
            "lbad",
            "cbad",
            "badi",
            "nth",
            "size",
            "make_lbad",
            "log",
        ),
        "ingredient_tokens": ("inv", "lbad", "log", "cbad"),
    },
    {
        "id": "oracle_log_cpa_structure",
        "label": "oracle/log CPA invariant structure",
        "tokens": (
            "inv_cpa",
            "rof.m",
            "roin.m",
            "roout.m",
            "bnr.lenc",
            "bnr.ndec",
            "mem.log",
            "mem.lc",
        ),
        "ingredient_tokens": ("inv", "cpa", "log", "lenc"),
    },
    {
        "id": "list_index_arithmetic",
        "label": "list/index arithmetic structure",
        "tokens": (
            "nth",
            "size",
            "cat",
            "map",
            "take",
            "drop",
            "mkseq",
        ),
        "ingredient_tokens": ("nth", "size"),
    },
)


def route_health_items(
    *,
    view: dict[str, Any],
    route_event_facts: list[dict[str, Any]],
    tactics: list[str],
    file_path: str,
    project_root: Path,
    replay_prefix_count: int = 0,
) -> list[dict[str, Any]]:
    goal_text = view_goal_text(view)
    goal_lower = goal_text.lower()
    proof_status = _dict(view.get("proof_status") or view.get("proof_position"))
    goal_type = str(proof_status.get("goal_type") or "").lower()
    view_focus = str(proof_status.get("view_focus") or "").lower()
    current_layer = str(proof_status.get("current_layer") or "").lower()
    is_prhl = (
        goal_type in {"prhl", "equiv", "equivalence"}
        or "prhl" in current_layer
        or "procedure" in current_layer
        or "{1}" in goal_text
        or "{2}" in goal_text
    )
    items: list[dict[str, Any]] = []

    for item in (
        _frame_boundary_gap_signal(
            view=view,
            goal_text=goal_text,
            tactics=tactics,
        ),
        _call_abstraction_loss_signal(
            view=view,
            goal_text=goal_text,
            tactics=tactics,
        ),
        _boundary_gap_signal(
            goal_lower=goal_lower,
            route_event_facts=route_event_facts,
            tactics=tactics,
            file_path=file_path,
            project_root=project_root,
        ),
    ):
        if item:
            items.append(item)

    for item in (
        _seq_boundary_restored_signal(view),
        _seq_cut_mismatch_signal(route_event_facts=route_event_facts, tactics=tactics),
        _pure_tail_route_health_signal(
            view=view,
            goal_text=goal_text,
            tactics=tactics,
        ),
        _frontier_placement_signal(route_event_facts),
        _local_tool_not_ready_signal(goal_lower, route_event_facts),
    ):
        if item:
            items.append(item)

    if is_prhl and "seq" in view_focus and not any(
        str(item.get("signal") or "") == "possible_boundary_gap"
        for item in items
    ):
        surgery = _prhl_surgery_sequence_signal(goal_text)
        if surgery:
            items.append(surgery)

    return annotate_route_health_items(_dedupe_route_health(items))[:2]


def structural_transition_items(
    *,
    view: dict[str, Any],
    route_event_facts: list[dict[str, Any]],
    route_health: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if any(
        str(item.get("signal") or "") in {
            "lost_call_abstraction_boundary",
            "possible_boundary_gap",
            "frontier_placement",
        }
        for item in route_health
        if isinstance(item, dict)
    ):
        return []
    goal_text = view_goal_text(view)
    goal_lower = goal_text.lower()
    proof_status = _dict(view.get("proof_status") or view.get("proof_position"))
    goal_type = str(proof_status.get("goal_type") or "").lower()
    view_focus = str(proof_status.get("view_focus") or "").lower()
    current_layer = str(proof_status.get("current_layer") or "").lower()
    is_prhl = (
        goal_type in {"prhl", "equiv", "equivalence"}
        or "prhl" in current_layer
        or "procedure" in current_layer
        or "{1}" in goal_text
        or "{2}" in goal_text
    )
    items: list[dict[str, Any]] = []
    probability_transition = _probability_budget_random_tuple_transition(goal_text)
    if probability_transition:
        items.append(probability_transition)
    if any(
        str(item.get("signal") or "") == "probability_budget_route_risk"
        for item in route_health
        if isinstance(item, dict)
    ):
        return items[:3]

    if not is_prhl or "seq" not in view_focus or "post =" not in goal_lower:
        return items[:3]
    looks_like_large_surgery = (
        len(goal_text) > 1200
        or any(token in goal_lower for token in ("forall", "if ", "let ", "&&"))
    )
    if not (
        _latest_event_is_large_workbench_commit(route_event_facts)
        or looks_like_large_surgery
    ):
        return items[:3]
    if _inside_post_wp_surgery(route_event_facts):
        return items[:3]
    items.append(
        structural_transition_surface(
            "wp.",
            status="candidate_reversible_probe",
            why_here=(
                "The current pRHL seq-cut exposes a large postcondition. "
                "Probe `wp.` if you want to test entry into the real "
                "post-wp suffix/surgery workbench."
            ),
            submit_intent="probe_tactic",
        )
    )
    return items[:3]


def _frame_boundary_gap_signal(
    *,
    view: dict[str, Any],
    goal_text: str,
    tactics: list[str],
) -> dict[str, Any]:
    missing_terms = pre_post_global_frame_gap(view, goal_text=goal_text)
    if missing_terms:
        # A glob in the post that is DERIVABLE from the pre by transitivity through a middle
        # memory (`X{1}=X{m} ∧ X{2}=X{m}` ⊢ `={X}`) is NOT a real gap (cpa_ddh0 `={glob A}`).
        transitive = transitively_equal_terms(pre_post_sections(goal_text)[0])
        missing_terms = [t for t in missing_terms if t not in transitive]
    if not missing_terms:
        return {}
    checkpoint = _frame_gap_checkpoint(tactics, missing_terms)
    displayed = [f"={{{term}}}" for term in missing_terms[:3]]
    evidence = [
        "current pRHL post requires frame equality absent from the displayed precondition",
        "missing frame fact(s): " + ", ".join(displayed),
    ]
    if checkpoint:
        evidence.append(
            "related structural boundary does not carry the same frame fact(s): "
            + str(checkpoint.get("label") or "")
        )
    recommended_next = dict(checkpoint.get("submit") or {})
    return _drop_empty({
        "signal": "frame_boundary_gap",
        "confidence": "high",
        "message": (
            "A current pRHL postcondition exposes a frame equality that is not "
            "available in the displayed precondition."
        ),
        "evidence": evidence,
        "missing_frame_facts": displayed,
        "related_surface": "current_goal.pre_post_frame_facts",
        "recommended_next": recommended_next,
        "primary_next_action": recommended_next,
        "repair_checkpoint": checkpoint,
    })


def _frame_gap_checkpoint(
    tactics: list[str],
    missing_terms: list[str],
) -> dict[str, Any]:
    if not tactics or not missing_terms:
        return {}
    boundaries = frame_boundary_facts(tactics, start_index=1)
    if not boundaries:
        return {}
    missing = set(missing_terms)

    def missing_from(boundary: dict[str, Any]) -> bool:
        # Lenient carried check (glob-subsumption + clone-alias) so a `={glob M}` or a
        # clone-qualified `ROIN.RO.m` is not falsely reported as a dropped `M.x` / `RO.m`
        # -> no wrong-rewind recommendation. Mirrors the frame-obligation ledger fix.
        carried = set(_string_list(boundary.get("canonical_facts")))
        return any(not frame_fact_carried(term, carried) for term in missing)

    ordered: list[dict[str, Any]] = []
    for preferred_kind in ("call", "seq", "while", "conseq"):
        ordered.extend(
            item for item in reversed(boundaries)
            if str(item.get("kind") or "") == preferred_kind and missing_from(item)
        )
        if ordered:
            break
    if not ordered:
        ordered = [item for item in reversed(boundaries) if missing_from(item)]
    if not ordered:
        return {}
    boundary = ordered[0]
    tactic_index = int(boundary.get("tactic_index") or 0)
    checkpoint = route_health_checkpoint(
        tactics,
        tactic_index,
        why_here=(
            "Current pRHL postcondition requires a global frame fact that is "
            "absent from this structural boundary assertion."
        ),
    )
    if not checkpoint:
        return {}
    kind = str(boundary.get("kind") or "")
    if kind == "call":
        checkpoint["semantic_id"] = "before_call_route"
        checkpoint["undo_scope"] = "call_local"
        checkpoint["restored_affordances"] = {
            "call_route": "not_committed",
            "frame_facts": "before_call_invariant",
        }
    else:
        checkpoint["semantic_id"] = "boundary_repair"
        checkpoint["undo_scope"] = "structural_boundary"
        checkpoint["restored_affordances"] = {
            "frame_facts": "before_structural_boundary",
        }
    return checkpoint


def _seq_boundary_restored_signal(view: dict[str, Any]) -> dict[str, Any]:
    rewound_seq = _rewound_seq_cut_observation(_dict(view.get("last_result")))
    if not rewound_seq:
        return {}
    tactic_index = int(rewound_seq.get("tactic_index") or 0)
    evidence = [
        "last manager action restored the state before a seq cut",
        f"rewound tactic index: {tactic_index}" if tactic_index else "",
        "the restored seq boundary is not committed in the current proof state",
    ]
    return _drop_empty({
        "signal": "seq_boundary_restored",
        "confidence": "high",
        "message": (
            "The current proof point was restored to the state before a checked "
            "seq cut."
        ),
        "evidence": evidence,
        "related_surface": "seq_cut_surface",
        "observed_risk": "older_committed_seq_scope_or_frontier_nav_can_obscure_restored_boundary",
        "limitations": [
            "This signal identifies the restored boundary only.",
            "It does not select a replacement cut formula or proof tactic.",
        ],
    })


def _call_abstraction_loss_signal(
    *,
    view: dict[str, Any],
    goal_text: str,
    tactics: list[str],
) -> dict[str, Any]:
    candidate = _visible_named_call_candidate(view)
    if not candidate:
        return {}
    if _view_has_live_call_site(view, goal_text):
        return {}
    if _looks_like_procedure_equivalence_obligation(goal_text):
        return {}
    if _pure_tail_alignment_gap_visible(
        view=view,
        goal_text=goal_text,
        tactics=tactics,
    ):
        return {}
    inline_boundary = _latest_inline_boundary(
        tactics,
        start_index=frame_ledger_scope_start(tactics),
    )
    if not inline_boundary:
        return {}

    checkpoint_reason = (
        "inline boundary associated with the current named call/oracle-"
        "equivalence context; the current view has no live call site after "
        "this expansion"
    )
    checkpoint = route_health_checkpoint(
        tactics,
        inline_boundary["tactic_index"],
        why_here=checkpoint_reason,
    )
    symbol = str(candidate.get("symbol") or "")
    evidence = [
        "named call/oracle-equivalence route context remains visible"
        + (f": {symbol}" if symbol else ""),
        "current proof state exposes no live procedure call site",
        (
            f"likely erased by committed tactic #{inline_boundary['tactic_index']}: "
            f"{inline_boundary['tactic']}"
        ),
    ]
    recommended_next = dict(checkpoint.get("submit") or {})
    return _drop_empty({
        "signal": "lost_call_abstraction_boundary",
        "confidence": "high" if inline_boundary.get("broad") else "medium",
        "message": (
            "A named call/oracle-equivalence route is still visible as proof "
            "context, while the current frontier has no live call site."
        ),
        "evidence": evidence,
        "route_candidate": candidate,
        "recommended_next": recommended_next,
        "primary_next_action": recommended_next,
        "repair_checkpoint": checkpoint,
        "useful_inspections": [
            {
                "intent": "inspect_context",
                "payload": {"topic": "call_site_options"},
                "why": (
                    "Call-site context for the corresponding live frontier."
                ),
            },
            {
                "intent": "lookup_symbol",
                "payload": {"symbol": symbol},
                "why": (
                    "Declaration context for this named call/oracle-"
                    "equivalence handle."
                ),
            } if symbol else {},
        ],
    })


def _pure_tail_alignment_gap_visible(
    *,
    view: dict[str, Any],
    goal_text: str,
    tactics: list[str],
) -> bool:
    if _view_has_live_call_site(view, goal_text):
        return False
    if not looks_like_pure_tail_goal(goal_text, view):
        return False
    return bool(_pure_tail_gap_analysis_with_tactics(goal_text, view, tactics=tactics))


def _visible_named_call_candidate(view: dict[str, Any]) -> dict[str, Any]:
    candidate_moves = _dict(view.get("candidate_moves"))
    for item in _list(candidate_moves.get("moves")):
        if not isinstance(item, dict):
            continue
        candidate = _named_call_candidate_from_mapping(item)
        if candidate:
            return candidate
    for item in _list(candidate_moves.get("navigation")):
        if not isinstance(item, dict):
            continue
        candidate = _named_call_candidate_from_mapping(item)
        if candidate:
            return candidate
    handles = _dict(view.get("inspect_lookup_handles"))
    for item in _list(handles.get("lookup_candidates")):
        if not isinstance(item, dict):
            continue
        symbol = str(item.get("symbol") or "").strip()
        if not symbol:
            continue
        context = " ".join(
            str(item.get(key) or "")
            for key in ("use_when", "why", "returns", "role")
        ).lower()
        if any(token in context for token in ("call", "equiv", "oracle")):
            return _drop_empty({
                "symbol": symbol,
                "source": "inspect_lookup_handles.lookup_candidates",
                "why_visible": str(item.get("use_when") or item.get("why") or ""),
            })
    return {}


def _probability_budget_random_tuple_transition(goal_text: str) -> dict[str, Any]:
    if not analyze_probability_budget(goal_text):
        return {}
    if "<@" not in goal_text or "<$" not in goal_text:
        return {}
    post_text = _extract_goal_post_text(goal_text)
    statements = _indexed_goal_statements(goal_text)
    for idx, statement in enumerate(statements[:-1]):
        if "<@" not in statement["body"]:
            continue
        samples: list[dict[str, Any]] = []
        for later in statements[idx + 1:]:
            if later["number"] != statement["number"] + len(samples) + 1:
                break
            if "<$" not in later["body"]:
                break
            samples.append(later)
        if len(samples) < 2:
            continue
        assigned = [
            name for name in (
                _sample_assignment_name(sample["body"])
                for sample in samples
            )
            if name
        ]
        mentioned = [
            name for name in assigned
            if _goal_text_mentions_name(post_text, name)
        ]
        if len(mentioned) < 2:
            continue
        first = int(samples[0]["number"])
        last = int(samples[-1]["number"])
        tactic = (
            f"swap [{first}..{last}] -1."
            if first != last else f"swap {first} -1."
        )
        transition = structural_transition_surface(
            tactic,
            status="candidate_reversible_probe",
            why_here=(
                "The product-budget event is built from random samples that "
                "currently sit immediately after a procedure call. Probe this "
                "swap if you want to test moving that random tuple before the "
                "call, so the probability-budget route can reason about the "
                "sampled event instead of charging local samples one by one."
            ),
            submit_intent="probe_tactic",
        )
        transition["profile_gate"] = "l4_checked_action_surface"
        transition["detected_shape"] = {
            "kind": "random_tuple_after_call_under_product_budget",
            "call_statement": statement["number"],
            "sample_statements": [sample["number"] for sample in samples],
            "event_mentions": mentioned[:6],
        }
        return transition
    return {}


def _indexed_goal_statements(goal_text: str) -> list[dict[str, Any]]:
    statements: list[dict[str, Any]] = []
    for match in re.finditer(r"^\s*\(\s*(\d+)\)\s*(.*?)\s*$", goal_text, re.M):
        try:
            number = int(match.group(1))
        except ValueError:
            continue
        body = match.group(2).strip()
        if body:
            statements.append({"number": number, "body": body})
    return statements


def _sample_assignment_name(statement_body: str) -> str:
    lhs = str(statement_body or "").split("<$", 1)[0].strip()
    lhs = lhs.rstrip(";").strip()
    if not lhs:
        return ""
    return lhs.split()[-1].strip()


def _extract_goal_post_text(goal_text: str) -> str:
    match = re.search(
        r"\bpost\s*=\s*(.+)$",
        goal_text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    return match.group(1) if match else goal_text


def _goal_text_mentions_name(text: str, name: str) -> bool:
    raw = str(text or "")
    if name and name in raw:
        return True
    base = name.rsplit(".", 1)[-1] if "." in name else name
    if not base:
        return False
    return bool(re.search(rf"(?<![A-Za-z0-9_']){re.escape(base)}(?![A-Za-z0-9_'])", raw))


def _inside_post_wp_surgery(route_event_facts: list[dict[str, Any]]) -> bool:
    """Return true after entering a wp workbench but before leaving it."""

    post_wp_local_heads = {
        "inline",
        "rcondt",
        "rcondf",
        "swap",
        "conseq",
        "rnd",
        "case",
        "if",
    }
    for event in reversed(route_event_facts):
        if not event.get("changed"):
            continue
        head = str(event.get("tactic_head") or "")
        if head == "wp":
            return True
        if head in post_wp_local_heads:
            continue
        return False
    return False


def _boundary_gap_signal(
    *,
    goal_lower: str,
    route_event_facts: list[dict[str, Any]],
    tactics: list[str],
    file_path: str,
    project_root: Path,
) -> dict[str, Any]:
    boundary = _latest_boundary_tactic(tactics)
    if not boundary:
        return {}
    rejected_local_count = sum(
        1
        for event in route_event_facts[-10:]
        if event.get("rejected")
        and str(event.get("tactic_head") or "") in {"smt", "sim", "auto", "conseq", "eager", "wp"}
    )
    if rejected_local_count < 2:
        return {}
    cluster = _dominant_uncovered_cluster(goal_lower, boundary["tactic"])
    if not cluster:
        return {}
    concept_diff = _boundary_residual_concept_diff(
        residual_lower=goal_lower,
        boundary_tactic=boundary["tactic"],
        cluster=cluster,
    )
    context_symbols = _discover_local_context_symbols(
        file_path=file_path,
        project_root=project_root,
        cluster=cluster,
    )
    evidence = [
        f"residual concept cluster: {cluster['label']}",
        f"recent local repair failures: {rejected_local_count}",
        f"likely place to re-check: {boundary['label']}",
    ]
    residual_only = concept_diff.get("residual_terms_not_obvious_in_boundary")
    if isinstance(residual_only, list) and residual_only:
        evidence.append(
            "residual terms not obvious in boundary: "
            + ", ".join(str(item) for item in residual_only[:6])
        )
    useful_inspections = [
        {
            "intent": "inspect_context",
            "payload": {"topic": "lemma_hints"},
            "why": (
                "Use this as context before deciding whether the earlier "
                "boundary should be strengthened."
            ),
        }
    ]
    for symbol in context_symbols[:2]:
        useful_inspections.append({
            "intent": "lookup_symbol",
            "payload": {"symbol": symbol["symbol"]},
            "why": (
                "Read the declaration as context only; the manager is not "
                "suggesting this as the invariant."
            ),
        })
    checkpoint_reason = (
        f"Revisit this {boundary['kind']} boundary; residual goals now "
        f"repeatedly mention {cluster['label']}, "
        + (
            "including terms not obvious in the boundary formula."
            if isinstance(residual_only, list) and residual_only
            else "and recent local repairs have not discharged those obligations."
        )
    )
    checkpoint = route_health_checkpoint(
        tactics,
        boundary["tactic_index"],
        why_here=checkpoint_reason,
    )
    recommended_next = dict(checkpoint.get("submit") or {})
    return _drop_empty({
        "signal": "possible_boundary_gap",
        "confidence": "high" if rejected_local_count >= 2 else "medium",
        "message": (
            "Recent residual goals and local repair failures suggest a previous "
            f"{boundary['kind']} boundary may need to be revisited."
        ),
        "evidence": evidence,
        "concept_diff": concept_diff,
        "recommended_next": recommended_next,
        "primary_next_action": recommended_next,
        "useful_inspections": useful_inspections,
        "repair_checkpoint": checkpoint,
    })


def _frontier_placement_signal(route_event_facts: list[dict[str, Any]]) -> dict[str, Any]:
    latest = route_event_facts[-1] if route_event_facts else {}
    if not latest.get("rejected"):
        return {}
    error = str(latest.get("error_summary") or "").lower()
    head = str(latest.get("tactic_head") or "")
    if head == "while" and "invalid last instruction" in error:
        message = (
            "The while form is plausible, but the current frontier is not "
            "positioned at a loop tail."
        )
    elif head == "eager" and "tail" in error and "right statement" in error:
        message = (
            "`eager` is plausible only when the selected side has the right "
            "tail form; the current frontier is not positioned for it."
        )
    else:
        return {}
    return {
        "signal": "frontier_placement",
        "confidence": "high",
        "message": message,
        "evidence": [str(latest.get("error_summary") or "")],
        "recommended_next": {
            "intent": "inspect_context",
            "payload": {"topic": "align"},
        },
    }


def _seq_cut_mismatch_signal(
    *,
    route_event_facts: list[dict[str, Any]],
    tactics: list[str],
) -> dict[str, Any]:
    latest_seq = _latest_seq_tactic(tactics)
    seq_idx = int(latest_seq.get("tactic_index") or 0)
    if not seq_idx:
        return {}
    rejected = [
        item
        for item in route_event_facts[-6:]
        if item.get("rejected")
        and str(item.get("intent") or "") in {"probe_tactic", "commit_tactic"}
    ]
    if not rejected:
        return {}
    latest = rejected[-1]
    head = str(latest.get("tactic_head") or "")
    error = str(latest.get("error_summary") or "").lower()
    mismatch_kind = ""
    if head == "seq" or "invalid formula" in error or "ill-formed" in error:
        mismatch_kind = "cut_formula"
    elif head in {"call", "ecall", "sim", "wp", "sp", "conseq", "smt", "auto"}:
        mismatch_kind = "branch_obligation"
    if not mismatch_kind:
        return {}
    digest = history_hash(tactics)
    related = []
    overrides = semantic_checkpoint_overrides(tactics)
    for idx, override in overrides.items():
        if 1 <= idx <= len(tactics) and str(
            override.get("undo_scope") or ""
        ) in {"seq_local", "branch_local"}:
            related.append(checkpoint_surface_item(
                tactics,
                digest,
                idx,
                override=override,
            ))
    checkpoint_idx = seq_idx + 1 if seq_idx < len(tactics) else seq_idx
    checkpoint = route_health_checkpoint(
        tactics,
        checkpoint_idx,
        why_here=(
            "seq-local boundary associated with recent rejected work inside "
            "the current seq scope"
        ),
    )
    if checkpoint:
        checkpoint["undo_scope"] = "branch_local" if checkpoint_idx > seq_idx else "seq_local"
        checkpoint["semantic_id"] = (
            "after_seq_opened" if checkpoint_idx > seq_idx else "before_seq_cut"
        )
    return _drop_empty({
        "signal": "seq_cut_mismatch",
        "confidence": "medium",
        "message": (
            "Recent rejected work is inside the current seq-cut scope."
        ),
        "evidence": [
            f"latest seq cut tactic #{seq_idx}: {latest_seq.get('tactic')}",
            f"recent rejected tactic head: {head or 'unknown'}",
            f"mismatch kind: {mismatch_kind}",
        ],
        "repair_checkpoint": checkpoint,
        "recommended_next": dict(checkpoint.get("submit") or {}),
        "primary_next_action": dict(checkpoint.get("submit") or {}),
        "related_checkpoints": related[:4],
    })


def _local_tool_not_ready_signal(
    goal_lower: str,
    route_event_facts: list[dict[str, Any]],
) -> dict[str, Any]:
    sim_failures = [
        event for event in route_event_facts[-8:]
        if event.get("rejected")
        and str(event.get("tactic_head") or "") == "sim"
    ]
    if not sim_failures:
        return {}
    frontier_mismatch = any(
        token in goal_lower
        for token in ("right-only", "left-only", "no matching", "<$", "if ")
    )
    if not frontier_mismatch:
        return {}
    return {
        "signal": "local_tool_not_ready",
        "confidence": "high" if len(sim_failures) >= 2 else "medium",
        "message": (
            "`sim` is usually useful after branch, sampling, and postcondition "
            "alignment. The current frontier still shows unmatched structure."
        ),
        "evidence": [
            "recent `sim` rejection",
            "visible branch/sampling/frontier mismatch",
        ],
        "recommended_next": {
            "intent": "inspect_context",
            "payload": {"topic": "align"},
        },
    }


def _prhl_surgery_sequence_signal(goal_text: str) -> dict[str, Any]:
    goal_lower = goal_text.lower()
    if "post =" not in goal_lower:
        return {}
    if not any(token in goal_lower for token in ("forall", "if ", "let ", "&&")):
        return {}
    equal_vars = _extract_equal_vars_from_goal(goal_text)
    if len(equal_vars) >= 2:
        tactic = f"conseq (_: _ ==> ={{{', '.join(equal_vars[:8])}}})."
        recommended_next = {"intent": "probe_tactic", "payload": {"tactic": tactic}}
    else:
        recommended_next = {
            "intent": "inspect_context",
            "payload": {"topic": "tactic_forms", "name": "conseq"},
        }
    return {
        "signal": "prhl_surgery_sequence_needed",
        "confidence": "medium",
        "message": (
            "This looks like pRHL mid-surgery with a large postcondition. "
            "A common expert move is to use `conseq` to weaken to a smaller "
            "relational post, then use `sim` or automation."
        ),
        "evidence": [
            "pRHL seq-cut postcondition is large",
            "`conseq` is useful after the frontier is already aligned enough to name a smaller relation",
        ],
        "recommended_next": recommended_next,
        "anti_route": (
            "Do not use `conseq` as a blind replacement for a missing call or "
            "loop invariant; if residuals need facts not carried by the last "
            "boundary, repair that boundary first."
        ),
    }


def _pure_tail_route_health_signal(
    *,
    view: dict[str, Any],
    goal_text: str,
    tactics: list[str],
) -> dict[str, Any]:
    if not looks_like_pure_tail_goal(goal_text, view):
        return {}
    gaps = _pure_tail_gap_analysis_with_tactics(goal_text, view, tactics=tactics)
    if not gaps:
        return {}
    primary = gaps[0]
    if primary.get("signal") == "local_membership_decomposition_available":
        return _drop_empty({
            "signal": "local_membership_decomposition_available",
            "confidence": primary.get("confidence") or "medium",
            "message": (
                "Current pure-tail obligations expose list/map/filter membership "
                "source structure whose local facts are not separated in the "
                "current context."
            ),
            "evidence": primary.get("evidence"),
            "observed_gap": primary.get("gap"),
            "observed_risk": primary.get("observed_risk"),
            "related_surface": "pure_tail_surface.membership_decomposition_surface",
            "companion_surfaces": [
                "pure_tail_surface.existential_witness_surface",
                "pure_tail_surface.map_update_lookup_surface",
            ],
        })
    checkpoint = _pure_tail_route_checkpoint(tactics)
    return _drop_empty({
        "signal": "pure_tail_alignment_gap",
        "confidence": "medium",
        "message": (
            "Current pure-tail obligations expose map/projection alignment "
            "facts that are not visible in the goal text."
        ),
        "evidence": primary.get("evidence"),
        "observed_gap": primary.get("gap"),
        "observed_risk": primary.get("observed_risk"),
        "related_surface": "pure_tail_surface.gap_analysis",
        "repair_checkpoint": checkpoint,
    })


def _pure_tail_gap_analysis_with_tactics(
    goal_text: str,
    view: dict[str, Any],
    *,
    tactics: list[str],
) -> list[dict[str, Any]]:
    gaps = [
        dict(item)
        for item in _pure_tail_gap_analysis(goal_text, view)
        if isinstance(item, dict)
    ]
    if not gaps:
        return []
    checkpoint: dict[str, Any] | None = None
    out: list[dict[str, Any]] = []
    for item in gaps:
        if not item.get("reversible_to"):
            if checkpoint is None:
                checkpoint = _pure_tail_route_checkpoint(tactics)
            if checkpoint:
                item["reversible_to"] = [checkpoint]
        out.append(_drop_empty(item))
    return out


def _pure_tail_route_checkpoint(tactics: list[str]) -> dict[str, Any]:
    overrides = semantic_checkpoint_overrides(tactics)
    for idx in ordered_checkpoint_indices(tactics, overrides):
        override = overrides.get(idx) or {}
        semantic_ids = set(_string_list(override.get("semantic_ids")))
        if not semantic_ids and override.get("semantic_id"):
            semantic_ids = {str(override.get("semantic_id") or "")}
        scope = str(override.get("undo_scope") or "")
        if scope not in {"branch_local", "seq_local"} and not (
            semantic_ids & {"before_branch_work", "after_seq_opened", "before_seq_cut"}
        ):
            continue
        checkpoint = route_health_checkpoint(
            tactics,
            idx,
            why_here=(
                "seq-local boundary associated with the currently visible "
                "pure-tail alignment gap"
            ),
        )
        if checkpoint:
            checkpoint["undo_scope"] = scope or "branch_local"
            checkpoint["semantic_id"] = (
                "before_branch_work"
                if "before_branch_work" in semantic_ids
                else "after_seq_opened"
                if "after_seq_opened" in semantic_ids
                else "before_seq_cut"
            )
            checkpoint["restored_affordances"] = dict(
                override.get("restored_affordances") or {
                    "pure_tail_alignment": "before_cut_formula",
                }
            )
            return checkpoint
    checkpoint = route_health_checkpoint(
        tactics,
        int(_latest_seq_tactic(tactics).get("tactic_index") or 0),
        why_here=(
            "seq boundary associated with the currently visible pure-tail "
            "alignment gap"
        ),
    )
    if checkpoint:
        checkpoint["undo_scope"] = "seq_local"
        checkpoint["semantic_id"] = "before_seq_cut"
        checkpoint["restored_affordances"] = {
            "seq_cut": "not_committed",
            "pure_tail_alignment": "before_cut_formula",
        }
    return checkpoint


def _dedupe_route_health(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items:
        signal = str(item.get("signal") or "")
        if not signal or signal in seen:
            continue
        seen.add(signal)
        out.append(_drop_empty(item))
    order = {
        "frame_boundary_gap": 0,
        "lost_call_abstraction_boundary": 1,
        "possible_boundary_gap": 2,
        "probability_budget_route_risk": 3,
        "seq_cut_mismatch": 4,
        "local_membership_decomposition_available": 5,
        "pure_tail_alignment_gap": 6,
        "frontier_placement": 7,
        "local_tool_not_ready": 8,
        "prhl_surgery_sequence_needed": 9,
    }
    out.sort(key=lambda item: order.get(str(item.get("signal") or ""), 99))
    return out


def _latest_boundary_tactic(tactics: list[str]) -> dict[str, Any]:
    for idx in range(len(tactics), 0, -1):
        tactic = tactics[idx - 1]
        text = tactic.lower()
        kind = ""
        if "call (_:" in text:
            kind = "call invariant"
        elif re.match(r"\s*while\b", text):
            kind = "while invariant"
        elif re.match(r"\s*seq\b", text):
            kind = "seq cut"
        elif re.match(r"\s*conseq\b", text):
            kind = "conseq"
        if kind:
            return {
                "tactic_index": idx,
                "tactic": tactic,
                "kind": kind,
                "label": f"before committed tactic #{idx}",
            }
    return {}


def _dominant_uncovered_cluster(
    goal_lower: str,
    boundary_tactic: str,
) -> dict[str, Any]:
    boundary_lower = boundary_tactic.lower()
    best: dict[str, Any] = {}
    best_score = 0
    for cluster in _CONCEPT_CLUSTERS:
        tokens = [str(token).lower() for token in cluster["tokens"]]
        present = [token for token in tokens if token in goal_lower]
        if len(present) < 3:
            continue
        missing = [token for token in present if token not in boundary_lower]
        ingredient_covered = any(
            token in boundary_lower
            for token in ("inv_", "invariant", str(cluster.get("id") or ""))
        )
        if len(missing) < 2 and ingredient_covered:
            continue
        score = len(present) + len(missing)
        if score > best_score:
            best_score = score
            best = {**cluster, "present_tokens": present, "missing_tokens": missing}
    return best


def _boundary_residual_concept_diff(
    *,
    residual_lower: str,
    boundary_tactic: str,
    cluster: dict[str, Any],
) -> dict[str, Any]:
    boundary_lower = str(boundary_tactic or "").lower()
    residual_terms = _concept_terms_for_cluster(residual_lower, cluster)
    boundary_terms = _concept_terms_for_cluster(boundary_lower, cluster)
    shared = [term for term in residual_terms if term in set(boundary_terms)]
    residual_only = [term for term in residual_terms if term not in set(boundary_terms)]
    return _drop_empty({
        "residual_cluster": cluster.get("label"),
        "residual_mentions": residual_terms[:12],
        "boundary_mentions": boundary_terms[:12],
        "shared_mentions": shared[:8],
        "residual_terms_not_obvious_in_boundary": residual_only[:12],
        "how_to_read": (
            "Heuristic boundary-vs-residual concept comparison. Use it to "
            "decide whether to revisit the boundary; it is not an invariant "
            "recipe."
        ),
    })


def _concept_terms_for_cluster(text: str, cluster: dict[str, Any]) -> list[str]:
    stems = [str(token).lower() for token in cluster.get("tokens") or ()]
    terms: set[str] = set()
    for stem in stems:
        if stem and stem in text:
            terms.add(stem)
    identifiers = re.findall(
        r"[A-Za-z_][A-Za-z0-9_']*(?:\.[A-Za-z_][A-Za-z0-9_']*)*",
        text,
    )
    for identifier in identifiers:
        ident = identifier.lower()
        if any(stem and stem in ident for stem in stems):
            terms.add(ident)
    return sorted(terms)


def _discover_local_context_symbols(
    *,
    file_path: str,
    project_root: Path,
    cluster: dict[str, Any],
) -> list[dict[str, Any]]:
    path = Path(file_path)
    if not path.is_absolute():
        path = Path(project_root) / path
    try:
        source = path.read_text(encoding="utf-8")
    except OSError:
        return []
    decls: list[tuple[int, str, str]] = []
    pattern = re.compile(
        r"(?m)^\s*(?:local\s+)?(?:lemma|op|pred)\s+([A-Za-z_][A-Za-z0-9_'.]*)"
    )
    matches = list(pattern.finditer(source))
    for idx, match in enumerate(matches):
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(source)
        decls.append((match.start(), match.group(1), source[match.start():end]))
    required = [str(token).lower() for token in cluster.get("ingredient_tokens") or ()]
    present = [str(token).lower() for token in cluster.get("present_tokens") or ()]
    candidates: list[dict[str, Any]] = []
    for _start, name, body in decls:
        body_lower = body.lower()
        name_lower = name.lower()
        score = sum(2 for token in required if token in body_lower or token in name_lower)
        score += sum(1 for token in present if token in body_lower or token in name_lower)
        if "inv" in name_lower:
            score += 3
        if (
            cluster.get("id") == "bad_event_index_structure"
            and name_lower.endswith("_i")
            and any(token in present for token in ("badi", "cbad", "nth"))
        ):
            score += 4
        if score < 4:
            continue
        candidates.append({
            "symbol": name,
            "role": (
                "local declaration connected to the residual "
                f"{cluster.get('label')}"
            ),
            "_score": score,
        })
    candidates.sort(key=lambda item: (-int(item.get("_score") or 0), str(item.get("symbol") or "")))
    return [
        {key: value for key, value in item.items() if key != "_score"}
        for item in candidates[:4]
    ]


def _latest_event_is_large_workbench_commit(route_event_facts: list[dict[str, Any]]) -> bool:
    if not route_event_facts:
        return False
    latest = route_event_facts[-1]
    return bool(
        latest.get("intent") == "commit_tactic"
        and latest.get("accepted")
        and latest.get("changed")
    )


def _extract_equal_vars_from_goal(goal_text: str) -> list[str]:
    pre_match = re.search(r"\bpre\s*=\s*(.*?)(?:\n\s*\w.*\(\d|post\s*=)", goal_text, re.S)
    text = pre_match.group(1) if pre_match else goal_text[:2500]
    pairs = re.findall(
        r"\b([A-Za-z_][A-Za-z0-9_'.]*)\{1\}\s*=\s*\1\{2\}",
        text,
    )
    out: list[str] = []
    for item in pairs:
        if item not in out and len(item) <= 32:
            out.append(item)
    return out[:10]

