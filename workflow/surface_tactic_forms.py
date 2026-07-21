"""State-derived tactic-form actions for the typed surface contract.

This module is the single owner of the question "which tactic-form references
should be visible in this proof state?"  The returned names are the final
state-eligible surface set: composition must not apply a second worthiness
filter, and eligibility must not maintain a parallel tactic-family taxonomy.
"""
from __future__ import annotations

import re
from dataclasses import replace
from typing import Any

from core.easycrypt.search.ec_tactic_forms import list_all as _list_tactic_form_names
from workflow.context_intents import INTENT_CLASS_CONTEXT_TOPIC
from workflow.surface_model import PanelAction, goal_text as _choice_goal_text
from workflow.surface_state_predicates import derive_surface_state, goal_has_program
from workflow.surface_structural_facts import (
    has_checked_seq_source,
    has_checked_swap_source,
)


SUPPORTED_TACTIC_FORM_NAMES = frozenset(_list_tactic_form_names())
OPENER_SURFACE_TACTIC_FORMS = frozenset({
    "byequiv", "byphoare", "phoare", "bdhoare",
})


def eligible_tactic_form_names(
    view: dict[str, Any],
    panel_id: str,
    phase: str,
) -> frozenset[str] | None:
    """Return the canonical tactic-form references visible for this state.

    ``None`` is reserved for recovery or unknown compatibility states where an
    already-diagnosed/requested family should pass through.  Every normal panel
    receives a final set, not a broad applicability set for another policy to
    narrow later.
    """
    if _proof_is_closed(view):
        return frozenset()
    if panel_id == "plain" or phase == "plain":
        names = _pretty_text_current_head_names(view)
        names.discard("ecall")
        if _is_procedure_losslessness_obligation(view):
            names.add("islossless")
        return frozenset(names)
    if panel_id == "single_program" or phase == "single_program":
        state = derive_surface_state(view)
        names: set[str] = set()
        tactic_head = _tactic_active_tail_head(view)
        active_kind = _frontier_kind_for_head(tactic_head) if tactic_head else state.frontier_kind
        if active_kind == "call":
            names.update({"call", "inline"})
        elif active_kind == "sample":
            names.add("rnd")
        elif active_kind == "branch":
            names.update({"rcondt", "rcondf"})
        elif active_kind == "loop":
            names.add("while")
        elif state.authority != "program_ir":
            names.update(_pretty_text_current_head_names(view))
        if _has_live_one_sided_losslessness_certificate(view):
            names.add("call")
        if _is_procedure_losslessness_obligation(view):
            names.add("islossless")
        return frozenset(names)
    if panel_id == "call_site" or phase == "call_site":
        return frozenset({"call", "inline"})
    if panel_id == "pure_logic" or phase == "pure_logic":
        return frozenset()
    if panel_id == "opener" or phase == "opener":
        return frozenset(
            OPENER_SURFACE_TACTIC_FORMS & _advertised_tactic_form_names(view)
        )
    if panel_id == "deep_surgery" or phase == "deep_surgery":
        if not goal_has_program(view) and not derive_surface_state(view).has_program:
            return frozenset()
        names = set(_deep_surgery_tactic_form_names(view))
        if _has_exact_call_form_fact(view):
            names.discard("call")
        return frozenset(names)
    if panel_id == "recovery" or phase == "failure_recovery":
        return None
    if not goal_has_program(view):
        return frozenset()
    return None


def compose_tactic_form_actions(
    view: dict[str, Any],
    panel_id: str,
    phase: str,
    actions: tuple[PanelAction, ...] | list[PanelAction],
    *,
    requested_names: list[str] | tuple[str, ...] | None = None,
) -> list[PanelAction]:
    """Add missing typed tactic-form actions from the canonical state taxonomy.

    Raw manager handles remain useful evidence, but they are not the owner of
    tactic-family visibility.  This function is the only place that turns the
    state taxonomy above into ``PanelAction`` values.  ``requested_names`` is
    used by recovery, where the diagnosed repair families are intentionally
    narrower than the normal phase menu.
    """
    eligible = eligible_tactic_form_names(view, panel_id, phase)
    visible = set(requested_names) if requested_names is not None else set(
        eligible if eligible is not None else SUPPORTED_TACTIC_FORM_NAMES
    )
    visible.intersection_update(SUPPORTED_TACTIC_FORM_NAMES)
    out = _narrow_tactic_form_actions(list(actions), visible)
    target = set(requested_names) if requested_names is not None else set(eligible or ())
    target.intersection_update(visible)
    existing = _existing_tactic_form_names(out)
    for name in _ordered_tactic_names(target):
        if name in existing:
            continue
        out.append(PanelAction(
            intent="tactic_forms",
            payload={"name": name},
            label=f"tactic_forms: {name}",
            intent_class=INTENT_CLASS_CONTEXT_TOPIC,
            read_only=True,
            description="valid EasyCrypt forms for this current proof state",
            source_refs=("surface_tactic_forms", *derive_surface_state(view).source_refs),
            eligibility_reason="tactic reference is state-eligible on the current surface",
            state_scope="current_phase",
        ))
    return out


def _narrow_tactic_form_actions(
    actions: list[PanelAction],
    visible: set[str],
) -> list[PanelAction]:
    out: list[PanelAction] = []
    for action in actions:
        if action.intent != "tactic_forms":
            out.append(action)
            continue
        concrete = str(action.payload.get("name") or "").strip()
        choices = dict(action.choices)
        names = [
            value for value in choices.get("name", [])
            if str(value).strip() in visible
        ]
        if concrete and not concrete.startswith("<"):
            if concrete not in visible:
                continue
            names = names or [concrete]
        elif not names:
            continue
        choices["name"] = names
        out.append(replace(action, choices=choices))
    return out


def _deep_surgery_tactic_form_names(view: dict[str, Any]) -> frozenset[str]:
    """Return state-eligible forms justified by the *current* frontier.

    Lookahead rows may explain what follows, but they do not make a tactic
    applicable now.  This helper therefore reads only the current frontier,
    setup prefixes, and checked tactic-shaped compiler facts such as swap/seq
    sources.  It deliberately does not choose an invariant, cut, branch
    direction, coupling map, or global route.
    """
    frontier = view.get("program_frontier") if isinstance(view.get("program_frontier"), dict) else {}
    scope = frontier.get("current_frontier_scope") if isinstance(frontier.get("current_frontier_scope"), dict) else {}
    active_tail = (
        scope.get("tactic_active_tail")
        if isinstance(scope.get("tactic_active_tail"), dict)
        else {}
    )
    current = active_tail or (
        scope.get("frontier") if isinstance(scope.get("frontier"), dict) else {}
    )
    entries = [
        current.get(side)
        for side in ("left", "right")
        if isinstance(current.get(side), dict)
    ]
    heads = {
        str(entry.get("head") or "").strip().lower()
        for entry in entries
        if str(entry.get("head") or "").strip()
    }
    statements = " ".join(
        str(entry.get("statement") or "") for entry in entries
    )
    kind = str(current.get("kind") or "").strip().lower()
    names: set[str] = set()

    has_call = "call" in heads or "call" in kind or "<@" in statements
    has_sample = "sample" in heads or "sample" in kind or "<$" in statements
    has_branch = bool({"if", "branch"} & heads) or "if" in kind or "branch" in kind
    has_loop = bool({"while", "loop"} & heads) or "while" in kind or "loop" in kind

    if has_call:
        names.update({"call", "inline"})
    if has_sample:
        names.add("rnd")
    if has_branch:
        names.update({"rcondt", "rcondf"})
    if has_loop:
        names.add("while")
    if has_call and has_sample:
        names.add("eager")

    setup = scope.get("setup") if isinstance(scope.get("setup"), dict) else {}
    setup_text = " ".join(
        str((setup.get(side) or {}).get("summary") or "")
        for side in ("left", "right")
        if isinstance(setup.get(side), dict)
    )
    if not active_tail and (
        "<@" in setup_text or "procedure-call prefix:" in setup_text.lower()
    ):
        names.update({"call", "inline"})

    if has_checked_swap_source(view):
        names.add("swap")
    if has_checked_seq_source(view):
        names.add("seq")
    return frozenset(names)


def _has_exact_call_form_fact(view: dict[str, Any]) -> bool:
    """Whether the primary facts already carry a current exact call form.

    In that state a generic call-syntax reference is redundant; this remains a
    state-eligibility decision here, rather than a downstream presentation gate.
    """
    context = view.get("application_context")
    up_to_bad = context.get("up_to_bad_call") if isinstance(context, dict) else None
    return bool(
        isinstance(up_to_bad, dict)
        and str(up_to_bad.get("candidate") or "").strip()
    )


def _advertised_tactic_form_names(view: dict[str, Any]) -> set[str]:
    """Return concrete tactic references supplied by the fact producer.

    Opener references are static documentation, not facts derivable from a
    program head.  They therefore surface only when the producer supplied that
    concrete reference for this state.  This is source availability inside the
    canonical selector, not a second visibility policy.
    """
    handles = view.get("inspect_lookup_handles")
    requests = handles.get("ask_manager_for") if isinstance(handles, dict) else []
    names: set[str] = set()
    for request in requests if isinstance(requests, list) else []:
        if not isinstance(request, dict) or request.get("intent") != "tactic_forms":
            continue
        payload = request.get("payload") if isinstance(request.get("payload"), dict) else {}
        name = str(payload.get("name") or "").strip()
        if name and not name.startswith("<"):
            names.add(name)
        choices = request.get("choices") if isinstance(request.get("choices"), dict) else {}
        names.update(
            str(item).strip()
            for item in choices.get("name", [])
            if str(item).strip() and not str(item).strip().startswith("<")
        )
    return names


def _proof_is_closed(view: dict[str, Any]) -> bool:
    status = view.get("proof_status")
    value = str(status.get("status") or "") if isinstance(status, dict) else ""
    return value in {"candidate_closed_pending_qed", "candidate_closed", "verified", "closed"}


def _tactic_active_tail_head(view: dict[str, Any]) -> str:
    frontier = view.get("program_frontier")
    scope = (
        frontier.get("current_frontier_scope")
        if isinstance(frontier, dict)
        and isinstance(frontier.get("current_frontier_scope"), dict)
        else {}
    )
    tail = scope.get("tactic_active_tail") if isinstance(scope.get("tactic_active_tail"), dict) else {}
    heads = {
        str((tail.get(side) or {}).get("head") or "").strip().lower()
        for side in ("left", "right")
        if isinstance(tail.get(side), dict)
    }
    heads.discard("")
    if len(heads) == 1:
        return next(iter(heads))
    if "if" in heads:
        return "if"
    return ""


def _frontier_kind_for_head(head: str) -> str:
    if head == "call":
        return "call"
    if head == "sample":
        return "sample"
    if head in {"if", "branch"}:
        return "branch"
    if head in {"while", "loop"}:
        return "loop"
    return "statement" if head else "none"


def _pretty_text_current_head_names(view: dict[str, Any]) -> set[str]:
    """Narrow fallback for Hoare shells that have no structured frontier.

    Only the first program head is considered. Later statements in the pretty
    goal must not advertise tactics before they become current.
    """
    program = plain_program_body(goal_text(view)).lstrip()
    if re.match(r"^while\b", program):
        return {"while"}
    if re.match(r"^if\b", program):
        return {"rcondt", "rcondf"}
    first = program.splitlines()[0] if program else ""
    if "<@" in first:
        return {"call", "ecall", "inline"}
    if "<$" in first:
        return {"rnd"}
    return set()


def _has_live_one_sided_losslessness_certificate(view: dict[str, Any]) -> bool:
    call_site = view.get("call_site_surface")
    if not isinstance(call_site, dict):
        return False
    one_sided = call_site.get("one_sided_call_surface")
    return bool(
        isinstance(one_sided, dict)
        and one_sided.get("visible_lossless_handles")
    )


def _is_procedure_losslessness_obligation(view: dict[str, Any]) -> bool:
    frontier = view.get("program_frontier")
    obligation = (
        frontier.get("program_obligation")
        if isinstance(frontier, dict)
        and isinstance(frontier.get("program_obligation"), dict)
        else {}
    )
    return obligation.get("kind") == "procedure_losslessness"


def _existing_tactic_form_names(actions: list[PanelAction]) -> set[str]:
    names: set[str] = set()
    for action in actions:
        if action.intent != "tactic_forms":
            continue
        value = str(action.payload.get("name") or "").strip()
        if value and not value.startswith("<"):
            names.add(value)
        names.update(
            str(item).strip()
            for item in action.choices.get("name", [])
            if str(item).strip()
        )
    return names


def _ordered_tactic_names(names: set[str]) -> list[str]:
    order = (
        "proc", "sp", "wp", "inline", "call", "ecall", "seq", "if",
        "rcondt", "rcondf", "while", "rnd", "islossless", "swap", "eager", "conseq",
        "rewrite", "apply", "case", "have", "smt", "byequiv", "byphoare",
        "phoare", "bdhoare",
    )
    rank = {name: idx for idx, name in enumerate(order)}
    return sorted(names, key=lambda name: (rank.get(name, len(rank)), name))


def plain_program_body(text: str) -> str:
    match = re.search(r"\b(?:hoare|phoare|bdhoare)\s*\[(.*?):", text, re.S)
    if match:
        return match.group(1)
    return text if goal_has_program({"current_goal": {"text": text}}) else ""


def goal_text(view: dict[str, Any]) -> str:
    return _choice_goal_text(view)
