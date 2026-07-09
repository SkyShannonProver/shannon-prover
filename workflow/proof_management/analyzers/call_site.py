"""Call-site evidence analyzer."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from workflow.proof_management.analyzers.common import (
    _dedupe_dicts,
    _dict,
    _drop_empty,
    _list,
    _preview,
)
from workflow.proof_management.analyzers.pure_tail import (
    looks_like_pure_tail_goal,
)
from workflow.proof_management.frame_facts import view_goal_text
from workflow.proof_management.node_state import ProofNodeState
from workflow.proof_management.transitions import (
    is_broad_inline_tactic as _is_broad_inline_tactic,
)


@dataclass(frozen=True)
class CallSiteAnalysis:
    """Analyzer output for call-site panels plus neutral view cleanup."""

    surface: dict[str, Any] = field(default_factory=dict)
    view_overrides: dict[str, Any] = field(default_factory=dict)
    removed_panels: list[str] = field(default_factory=list)


class CallSiteAnalyzer:
    """Builds `call_site_surface` and removes stale named-call affordances."""

    def analyze(
        self,
        *,
        state: ProofNodeState,
        view: dict[str, Any] | None = None,
    ) -> CallSiteAnalysis:
        del state
        base_view = dict(view or {})
        rendered = call_site_view(base_view)
        surface = dict(_dict(rendered.get("call_site_surface")))
        removed: list[str] = []
        if (
            not surface
            and _dict(base_view.get("call_site_surface"))
            and "call_site_surface" in base_view
        ):
            removed.append("call_site_surface")
        overrides: dict[str, Any] = {}
        if rendered.get("candidate_moves") != base_view.get("candidate_moves"):
            candidate_moves = rendered.get("candidate_moves")
            overrides["candidate_moves"] = (
                dict(candidate_moves)
                if isinstance(candidate_moves, dict)
                else candidate_moves
            )
        return CallSiteAnalysis(
            surface=surface,
            view_overrides=overrides,
            removed_panels=removed,
        )


def call_site_view(view: dict[str, Any]) -> dict[str, Any]:
    raw = dict(_dict(view))
    call_site = call_site_surface(raw)
    if call_site:
        raw["call_site_surface"] = call_site
        raw = _workspace_view_without_noncallable_named_call_affordances(raw)
    if looks_like_pure_tail_goal(
        view_goal_text(raw, legacy_goal_text_fallback=True),
        raw,
    ):
        raw = _workspace_view_without_stale_named_call_affordances(raw)
    return raw


def call_site_surface(view: dict[str, Any]) -> dict[str, Any]:
    existing = dict(_dict(view.get("call_site_surface")))
    existing.pop("named_call_templates", None)
    frontier = _dict(view.get("program_frontier"))
    live_call_sites = [
        _compact_call_site(item)
        for item in _list(frontier.get("call_sites"))
        if isinstance(item, dict)
    ]
    live_call_sites = [item for item in live_call_sites if item]
    named_handles = _call_site_named_handles(view)
    callable_now = [
        item for item in named_handles if bool(item.get("callable_now"))
    ]
    frontier_blockers = _call_site_frontier_blockers(
        frontier=frontier,
        live_call_sites=live_call_sites,
        named_handles=named_handles,
    )
    residual_frontier = _call_site_residual_frontier(frontier)
    preview_effects = _call_site_preview_effects(view)
    one_sided = _one_sided_call_surface(
        view,
        live_call_sites=live_call_sites,
    )
    if not any((
        existing,
        live_call_sites,
        named_handles,
        frontier_blockers,
        residual_frontier,
        preview_effects,
        one_sided,
    )):
        return {}
    result = dict(existing)
    if live_call_sites:
        result["live_call_sites"] = live_call_sites
    if named_handles:
        result["named_handles"] = named_handles
    if callable_now:
        result["callable_now"] = callable_now
    if frontier_blockers:
        result["frontier_blockers"] = frontier_blockers
    if residual_frontier:
        result["residual_frontier"] = residual_frontier
    wrapper_depth = _call_site_wrapper_depth(live_call_sites, named_handles)
    if wrapper_depth:
        result["wrapper_depth"] = wrapper_depth
    if preview_effects:
        result["preview_effects"] = preview_effects
    if one_sided:
        result["one_sided_call_surface"] = one_sided
    return _drop_empty(result)


def _workspace_view_without_stale_named_call_affordances(
    workspace_view: dict[str, Any],
) -> dict[str, Any]:
    raw = dict(_dict(workspace_view))
    goal_text = view_goal_text(raw, legacy_goal_text_fallback=True)
    if _view_has_live_call_site(raw, goal_text):
        return raw
    if not looks_like_pure_tail_goal(goal_text, raw):
        return raw
    candidate_moves = dict(_dict(raw.get("candidate_moves")))
    changed = False
    for panel_name in ("moves", "navigation"):
        items = _list(candidate_moves.get(panel_name))
        if not items:
            continue
        kept: list[Any] = []
        for item in items:
            if isinstance(item, dict) and _is_stale_named_call_affordance(item):
                changed = True
                continue
            kept.append(item)
        if kept:
            candidate_moves[panel_name] = kept
        else:
            candidate_moves.pop(panel_name, None)
            changed = True
    if changed:
        raw["candidate_moves"] = _drop_empty(candidate_moves)

    call_site = dict(_dict(raw.get("call_site_surface")))
    if call_site:
        real_blockers = [
            item for item in _list(call_site.get("frontier_blockers"))
            if isinstance(item, dict)
            and item.get("kind") != "named_handle_not_callable_in_current_view"
        ]
        if real_blockers:
            call_site["frontier_blockers"] = real_blockers
            raw["call_site_surface"] = _drop_empty(call_site)
        elif not any(
            _list(call_site.get(key))
            for key in ("live_call_sites", "callable_now")
        ) and not call_site.get("preview_effects"):
            raw.pop("call_site_surface", None)
    return raw


def _workspace_view_without_noncallable_named_call_affordances(
    workspace_view: dict[str, Any],
) -> dict[str, Any]:
    raw = dict(_dict(workspace_view))
    call_site = _dict(raw.get("call_site_surface"))
    if (
        not _list(call_site.get("live_call_sites"))
        or _list(call_site.get("callable_now"))
    ):
        return raw
    candidate_moves = dict(_dict(raw.get("candidate_moves")))
    changed = False
    for panel_name in ("moves", "navigation"):
        items = _list(candidate_moves.get(panel_name))
        if not items:
            continue
        kept: list[Any] = []
        for item in items:
            if isinstance(item, dict) and _named_call_candidate_from_mapping(item):
                changed = True
                continue
            kept.append(item)
        if kept:
            candidate_moves[panel_name] = kept
        else:
            candidate_moves.pop(panel_name, None)
            changed = True
    if changed:
        raw["candidate_moves"] = _drop_empty(candidate_moves)
    return raw


def _is_stale_named_call_affordance(item: dict[str, Any]) -> bool:
    if _named_call_candidate_from_mapping(item):
        return True
    item_id = str(item.get("id") or "").strip()
    if item_id == "call_site_route":
        return True
    context = " ".join(
        str(item.get(key) or "")
        for key in (
            "title",
            "category",
            "applicability",
            "runnable_status",
            "why_relevant",
            "proof_family",
            "route",
        )
    ).lower()
    return "named-call" in context or (
        "call-site" in context and ("call " in context or "equiv" in context)
    )


def _compact_call_site(item: dict[str, Any]) -> dict[str, Any]:
    procedure = str(
        item.get("procedure")
        or item.get("proc")
        or item.get("callee")
        or ""
    ).strip()
    return _drop_empty({
        "id": item.get("id") or item.get("call_site_id"),
        "side": item.get("side"),
        "position": item.get("pos") or item.get("position") or item.get("pos_path"),
        "procedure": procedure,
        "is_frontier_call": item.get("is_frontier_call"),
        "requires_cut_to_frontier": item.get("requires_cut_to_frontier"),
        "frontier_role": item.get("frontier_role"),
        "text": _preview(str(item.get("text") or ""), limit=180),
    })


def _call_site_named_handles(view: dict[str, Any]) -> list[dict[str, Any]]:
    handles: list[dict[str, Any]] = []
    app_context = _dict(view.get("application_context"))
    for item in _list(app_context.get("selected_handles")):
        if not isinstance(item, dict):
            continue
        name = str(
            item.get("name")
            or item.get("lemma")
            or item.get("symbol")
            or ""
        ).strip()
        context = " ".join(
            str(item.get(key) or "")
            for key in ("kind", "title", "why_relevant", "tactic_family")
        ).lower()
        if not name or not any(token in context for token in ("call", "equiv", "oracle")):
            continue
        handles.append(_drop_empty({
            "symbol": name,
            "source": "application_context.selected_handles",
            "callable_now": _handle_callable_now(item),
            "runnable_status": item.get("runnable_status"),
            "why_visible": item.get("why_relevant"),
        }))
    candidate_moves = _dict(view.get("candidate_moves"))
    for panel_name in ("moves", "navigation"):
        for item in _list(candidate_moves.get(panel_name)):
            if not isinstance(item, dict):
                continue
            candidate = _named_call_candidate_from_mapping(item)
            if not candidate:
                continue
            callable_now = _handle_callable_now(item)
            handle = {
                "symbol": candidate.get("symbol"),
                "source": candidate.get("source") or f"candidate_moves.{panel_name}",
                "callable_now": callable_now,
                "why_visible": candidate.get("why_visible"),
            }
            if callable_now and candidate.get("tactic_shape"):
                handle["tactic_shape"] = candidate.get("tactic_shape")
            elif candidate.get("tactic_shape"):
                handle["limitations"] = [
                    (
                        "The tactic shape is hidden until the handle is "
                        "callable at the current frontier."
                    )
                ]
            handles.append(_drop_empty(handle))
    lookup_handles = _dict(view.get("inspect_lookup_handles"))
    for item in _list(lookup_handles.get("lookup_candidates")):
        if not isinstance(item, dict):
            continue
        symbol = str(item.get("symbol") or "").strip()
        context = " ".join(
            str(item.get(key) or "")
            for key in ("role", "why", "use_when", "returns")
        ).lower()
        if symbol and any(token in context for token in ("call", "equiv", "oracle")):
            handles.append(_drop_empty({
                "symbol": symbol,
                "source": "inspect_lookup_handles.lookup_candidates",
                "callable_now": False,
                "why_visible": item.get("use_when") or item.get("why"),
            }))
    return _dedupe_named_handles(handles)[:6]


def _handle_callable_now(item: dict[str, Any]) -> bool:
    if isinstance(item.get("callable_now"), bool):
        return bool(item.get("callable_now"))
    text = " ".join(
        str(item.get(key) or "")
        for key in ("runnable_status", "call_candidate_kind", "applicability")
    ).lower()
    return any(
        token in text
        for token in (
            "callable_now",
            "direct_current_call",
            "matches the current last-call frontier",
        )
    )


def _dedupe_named_handles(handles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in handles:
        symbol = str(item.get("symbol") or "")
        source = str(item.get("source") or "")
        key = (symbol, source)
        if not symbol or key in seen:
            continue
        seen.add(key)
        out.append(_drop_empty(item))
    return out


def _call_site_residual_rows(frontier: dict[str, Any]) -> list[dict[str, Any]]:
    alignment = _dict(frontier.get("frontier_alignment"))
    rows = _list(alignment.get("rows"))
    residuals: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        role = str(row.get("role") or "").lower()
        if "residual after call" not in role:
            continue
        residuals.append(_drop_empty({
            "role": row.get("role"),
            "left": row.get("left"),
            "right": row.get("right"),
            "location": row.get("location"),
            "proof_read": row.get("proof_read"),
        }))
    return residuals[:4]


def _call_site_residual_frontier(frontier: dict[str, Any]) -> dict[str, Any]:
    residuals = _call_site_residual_rows(frontier)
    if not residuals:
        return {}
    return _drop_empty({
        "state": "residual_after_call",
        "rows": residuals,
        "effect": (
            "These statements remain after the live call frontier and are "
            "checked after the call returns."
        ),
        "limitations": [
            (
                "The surface reports suffix structure only; it does not choose "
                "whether to use a call, inline, wp, or another local tactic."
            )
        ],
    })


def _call_site_frontier_blockers(
    *,
    frontier: dict[str, Any],
    live_call_sites: list[dict[str, Any]],
    named_handles: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    raw_blockers = frontier.get("frontier_blockers")
    if isinstance(raw_blockers, dict):
        for side, item in raw_blockers.items():
            if isinstance(item, dict):
                blockers.append(_drop_empty({
                    "side": side,
                    "kind": item.get("kind"),
                    "text": _preview(str(item.get("text") or ""), limit=180),
                }))
    for item in live_call_sites:
        if item.get("requires_cut_to_frontier"):
            blockers.append(_drop_empty({
                "kind": "requires_cut_to_frontier",
                "procedure": item.get("procedure"),
                "side": item.get("side"),
                "position": item.get("position"),
            }))
    for row in _call_site_residual_rows(frontier):
        blockers.append(_drop_empty({
            "kind": "residual_after_call_site",
            "left": row.get("left"),
            "right": row.get("right"),
            "effect": (
                "Residual statements remain after the live call frontier; "
                "their effects are not part of the callee obligation."
            ),
        }))
    if named_handles and not any(item.get("callable_now") for item in named_handles):
        blockers.append({
            "kind": "named_handle_not_callable_in_current_view",
            "named_handle_count": len(named_handles),
            "live_call_site_count": len(live_call_sites),
        })
    return _dedupe_dicts(blockers)[:6]


def _call_site_wrapper_depth(
    live_call_sites: list[dict[str, Any]],
    named_handles: list[dict[str, Any]],
) -> int:
    if not live_call_sites:
        return 0
    if any(item.get("callable_now") for item in named_handles):
        return 0
    dotted = [
        str(item.get("procedure") or "").count(".")
        for item in live_call_sites
        if item.get("procedure")
    ]
    return max(dotted or [1])


def _call_site_preview_effects(view: dict[str, Any]) -> dict[str, Any]:
    last = _dict(view.get("last_result"))
    tactic = str(
        last.get("accepted_tactic")
        or _dict(last.get("probe_preview")).get("tactic")
        or ""
    ).strip()
    if not tactic or not _is_broad_inline_tactic(tactic.lower()):
        return {}
    preview_summary = _dict(last.get("preview_summary"))
    probe_preview = _dict(last.get("probe_preview"))
    goal_after = _dict(probe_preview.get("goal_after_probe"))
    if not preview_summary and goal_after:
        preview_summary = {
            "line_count": goal_after.get("line_count"),
            "char_count": goal_after.get("char_count"),
            "truncated": goal_after.get("truncated"),
            "remaining_goals": probe_preview.get("goal_after_remaining"),
        }
    current_goal = _dict(view.get("current_goal"))
    after_lines = "\n".join(
        str(line)
        for line in _list(goal_after.get("lines"))
        if isinstance(line, str)
    )
    return _drop_empty({
        "tactic": tactic,
        "kind": "broad_inline_preview",
        "before": {
            "line_count": current_goal.get("line_count"),
            "char_count": current_goal.get("char_count"),
            "goal_contains_call_site": _goal_text_contains_call_site(
                view_goal_text(view, legacy_goal_text_fallback=True)
            ),
        },
        "after": {
            **preview_summary,
            "goal_contains_call_site": (
                _goal_text_contains_call_site(after_lines)
                if after_lines else None
            ),
        },
        "observed_risk": "broad_inline_can_reduce_call_site_handles",
    })


def _one_sided_call_surface(
    view: dict[str, Any],
    *,
    live_call_sites: list[dict[str, Any]],
) -> dict[str, Any]:
    one_sided_sites = _one_sided_live_call_sites(view, live_call_sites)
    if not one_sided_sites:
        return {}
    live_procedures = {
        str(item.get("procedure") or "").strip()
        for item in one_sided_sites
        if item.get("procedure")
    }
    visible_handles = [
        item for item in _visible_call_certificate_handles(view)
        if (
            not live_procedures
            or not item.get("procedure")
            or str(item.get("procedure") or "").strip() in live_procedures
        )
    ]
    hoare_handles = [
        item for item in visible_handles
        if item.get("certificate_kind") == "hoare"
    ]
    phoare_handles = [
        item for item in visible_handles
        if item.get("certificate_kind") == "phoare"
    ]
    lossless_handles = [
        item for item in visible_handles
        if item.get("certificate_kind") == "losslessness"
    ]
    recent_failures = _one_sided_direct_call_shape_failures(view)
    if not any((hoare_handles, phoare_handles, lossless_handles, recent_failures)):
        return {}
    packaging = _one_sided_call_packaging_evidence(
        hoare_handles=hoare_handles,
        phoare_handles=phoare_handles,
        lossless_handles=lossless_handles,
        recent_failures=recent_failures,
    )
    return _drop_empty({
        "state": "one_sided_call_frontier",
        "one_sided_sites": one_sided_sites,
        "visible_hoare_handles": hoare_handles[:5],
        "visible_phoare_handles": phoare_handles[:5],
        "visible_lossless_handles": lossless_handles[:5],
        "recent_direct_call_shape_failures": recent_failures[:4],
        "packaging_evidence": packaging,
        "available_inspection_topics": [
            "tactic_forms(call)",
            "tactic_forms(ecall)",
            "call_subgoals",
        ],
    })


def _one_sided_live_call_sites(
    view: dict[str, Any],
    live_call_sites: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not live_call_sites:
        return []
    sides = {
        _normalize_call_side(item.get("side") or item.get("side_index"))
        for item in live_call_sites
    }
    sides.discard("")
    frontier = _dict(view.get("program_frontier"))
    alignment = _dict(frontier.get("frontier_alignment"))
    first = _dict(alignment.get("first_instruction_alignment"))
    branch_alignment = str(first.get("branch_alignment") or "").lower()
    one_sided_alignment = "one-sided" in branch_alignment
    if not one_sided_alignment and len(sides) != 1:
        return []
    return [
        _drop_empty({
            "side": item.get("side") or item.get("side_index"),
            "procedure": item.get("procedure"),
            "statement": item.get("statement") or item.get("text"),
            "position": item.get("position"),
        })
        for item in live_call_sites
        if item.get("procedure") or item.get("statement") or item.get("text")
    ][:4]


def _normalize_call_side(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in {"1", "{1}", "left", "lhs", "l"}:
        return "left"
    if text in {"2", "{2}", "right", "rhs", "r"}:
        return "right"
    if "left" in text:
        return "left"
    if "right" in text:
        return "right"
    return text


def _visible_call_certificate_handles(view: dict[str, Any]) -> list[dict[str, Any]]:
    handles: list[dict[str, Any]] = []
    handles.extend(_goal_call_certificate_handles(view))
    handles.extend(_context_call_certificate_handles(view))
    return _dedupe_call_certificate_handles(handles)


def _goal_call_certificate_handles(view: dict[str, Any]) -> list[dict[str, Any]]:
    lines = [
        str(line)
        for line in _list(_dict(view.get("current_goal")).get("lines"))
        if isinstance(line, str)
    ]
    handles: list[dict[str, Any]] = []
    for symbol, block in _goal_declaration_blocks(lines):
        kind = _call_certificate_kind(symbol, block)
        if not kind:
            continue
        handles.append(_drop_empty({
            "symbol": symbol,
            "certificate_kind": kind,
            "procedure": _certificate_procedure(block),
            "source": "current_goal",
            "text": _preview(block, limit=220),
        }))
    return handles


def _goal_declaration_blocks(lines: list[str]) -> list[tuple[str, str]]:
    blocks: list[tuple[str, str]] = []
    for idx, line in enumerate(lines):
        match = re.match(r"\s*([A-Za-z_][A-Za-z0-9_']*)\s*:", line)
        if not match:
            continue
        symbol = match.group(1)
        block_lines = [line.strip()]
        for next_line in lines[idx + 1:idx + 12]:
            stripped = next_line.strip()
            if not stripped or stripped.startswith("---"):
                break
            if re.match(r"[A-Za-z_][A-Za-z0-9_']*\s*:", stripped):
                break
            block_lines.append(stripped)
        blocks.append((symbol, " ".join(block_lines)))
    return blocks


def _context_call_certificate_handles(view: dict[str, Any]) -> list[dict[str, Any]]:
    handles: list[dict[str, Any]] = []
    app_context = _dict(view.get("application_context"))
    for item in _list(app_context.get("selected_handles")):
        if isinstance(item, dict):
            handle = _call_certificate_handle_from_mapping(
                item,
                source="application_context.selected_handles",
            )
            if handle:
                handles.append(handle)
    candidate_moves = _dict(view.get("candidate_moves"))
    for panel_name in ("moves", "navigation", "probe_alternatives"):
        for item in _list(candidate_moves.get(panel_name)):
            if isinstance(item, dict):
                handle = _call_certificate_handle_from_mapping(
                    item,
                    source=f"candidate_moves.{panel_name}",
                )
                if handle:
                    handles.append(handle)
    lookup_handles = _dict(view.get("inspect_lookup_handles"))
    for item in _list(lookup_handles.get("lookup_candidates")):
        if isinstance(item, dict):
            handle = _call_certificate_handle_from_mapping(
                item,
                source="inspect_lookup_handles.lookup_candidates",
            )
            if handle:
                handles.append(handle)
    return handles


def _call_certificate_handle_from_mapping(
    item: dict[str, Any],
    *,
    source: str,
) -> dict[str, Any]:
    symbol = str(
        item.get("name")
        or item.get("lemma")
        or item.get("symbol")
        or item.get("id")
        or ""
    ).strip()
    text = " ".join(
        str(item.get(key) or "")
        for key in (
            "name",
            "lemma",
            "symbol",
            "id",
            "kind",
            "title",
            "role",
            "why",
            "why_relevant",
            "use_when",
            "returns",
            "statement",
            "declaration",
            "type",
            "tactic",
            "tactic_shape",
            "applicability",
        )
    )
    kind = _call_certificate_kind(symbol, text)
    if not kind:
        return {}
    return _drop_empty({
        "symbol": symbol or _certificate_procedure(text),
        "certificate_kind": kind,
        "procedure": _certificate_procedure(text),
        "source": source,
        "text": _preview(text, limit=220),
    })


def _call_certificate_kind(symbol: str, text: str) -> str:
    lower = str(text or "").lower()
    name = str(symbol or "").strip()
    if "phoare[" in lower or re.search(r"\bphoare\b", lower):
        return "phoare"
    if "hoare[" in lower or re.search(r"\bhoare\b", lower):
        return "hoare"
    if (
        "islossless" in lower
        or "lossless" in lower
        or re.search(r"(^|[A-Za-z0-9])_ll$", name)
        or re.search(r"(^|[A-Za-z0-9])_lossless$", name)
    ):
        return "losslessness"
    return ""


def _certificate_procedure(text: str) -> str:
    match = re.search(r"\b(?:p?hoare)\[\s*([A-Za-z_][A-Za-z0-9_.'`]*)", text)
    if match:
        return match.group(1)
    match = re.search(r"\bislossless\s+([A-Za-z_][A-Za-z0-9_.'`]*)", text)
    if match:
        return match.group(1)
    return ""


def _dedupe_call_certificate_handles(
    handles: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for item in handles:
        symbol = str(item.get("symbol") or "")
        kind = str(item.get("certificate_kind") or "")
        proc = str(item.get("procedure") or "")
        source = str(item.get("source") or "")
        key = (symbol, kind, proc, source)
        if not kind or key in seen:
            continue
        seen.add(key)
        out.append(_drop_empty(item))
    return out[:12]


def _one_sided_direct_call_shape_failures(view: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    last = _dict(view.get("last_result"))
    if last:
        candidates.append(last)
    candidate_moves = _dict(view.get("candidate_moves"))
    candidates.extend(
        item for item in _list(candidate_moves.get("probe_alternatives"))
        if isinstance(item, dict)
    )
    failures: list[dict[str, Any]] = []
    for item in candidates:
        tactic = str(
            item.get("tactic")
            or _dict(item.get("payload")).get("tactic")
            or ""
        ).strip()
        error = str(item.get("error_summary") or item.get("result") or "").strip()
        if not tactic or not error:
            continue
        if not _is_direct_one_sided_call_tactic(tactic):
            continue
        lower_error = error.lower()
        if not any(token in lower_error for token in (
            "invalid goal shape",
            "not a valid formula",
            "proof-term argument",
            "call cannot be used",
        )):
            continue
        failures.append(_drop_empty({
            "tactic": _preview(tactic, limit=180),
            "side": _one_sided_call_tactic_side(tactic),
            "error_summary": _preview(error, limit=180),
            "classification": "direct_one_sided_call_shape_rejected",
        }))
    return _dedupe_dicts(failures)[:5]


def _is_direct_one_sided_call_tactic(tactic: str) -> bool:
    match = re.search(r"\b(?:ecall|call)\s*\{([12])\}", tactic)
    if not match:
        return False
    after = tactic[match.end():].strip()
    if after.startswith("(:") or re.match(r"\(_?\s*:", after):
        return False
    return True


def _one_sided_call_tactic_side(tactic: str) -> str:
    match = re.search(r"\b(?:ecall|call)\s*\{([12])\}", tactic)
    if not match:
        return ""
    return "left" if match.group(1) == "1" else "right"


def _one_sided_call_packaging_evidence(
    *,
    hoare_handles: list[dict[str, Any]],
    phoare_handles: list[dict[str, Any]],
    lossless_handles: list[dict[str, Any]],
    recent_failures: list[dict[str, Any]],
) -> dict[str, Any]:
    if phoare_handles:
        confidence = "high"
    elif hoare_handles and lossless_handles:
        confidence = "high"
    elif hoare_handles and recent_failures:
        confidence = "medium"
    elif hoare_handles:
        confidence = "low"
    else:
        confidence = "low"
    limitations: list[str] = []
    if hoare_handles and not lossless_handles and not phoare_handles:
        limitations.append(
            "No losslessness or phoare certificate for the live procedure is "
            "visible in this view."
        )
    if recent_failures:
        limitations.append(
            "Recent direct one-sided call attempts were rejected on proof-term "
            "shape, not as committed proof-state changes."
        )
    return _drop_empty({
        "kind": "one_sided_call_certificate_shape",
        "confidence": confidence,
        "effect": (
            "One-sided calls in a relational goal use single-procedure "
            "certificates; a Hoare certificate plus losslessness evidence can "
            "package the same local specification as a phoare certificate."
        ),
        "available_shapes": [
            {
                "kind": "phoare_certificate",
                "shape": "phoare[PROC : PRE ==> POST] = 1%r",
                "evidence_inputs": ["hoare_certificate", "losslessness_certificate"],
            },
            {
                "kind": "anonymous_one_sided_call_spec",
                "shape": "call{SIDE} (: PRE ==> POST)",
                "evidence_inputs": ["local_pre_post_certificate"],
            },
        ],
        "limitations": limitations,
    })


def _named_call_candidate_from_mapping(item: dict[str, Any]) -> dict[str, Any]:
    for key in ("tactic", "tactic_shape", "command"):
        text = str(item.get(key) or "")
        symbol = _call_symbol_from_tactic_text(text)
        if symbol:
            return _drop_empty({
                "symbol": symbol,
                "tactic_shape": text.strip(),
                "source": str(item.get("source") or ""),
                "why_visible": str(
                    item.get("applicability")
                    or item.get("why_relevant")
                    or item.get("effect")
                    or ""
                ),
            })
    symbol = str(item.get("symbol_hint") or item.get("symbol") or "").strip()
    if not symbol:
        return {}
    context = " ".join(
        str(item.get(key) or "")
        for key in (
            "title",
            "category",
            "applicability",
            "runnable_status",
            "why_relevant",
            "limitations",
        )
    ).lower()
    if any(token in context for token in ("call", "equiv", "oracle")):
        return _drop_empty({
            "symbol": symbol,
            "source": str(item.get("source") or ""),
            "why_visible": str(item.get("applicability") or item.get("why_relevant") or ""),
        })
    return {}


def _call_symbol_from_tactic_text(text: str) -> str:
    match = re.search(
        r"\b(?:e?call)\s+\(?\s*([A-Za-z_][A-Za-z0-9_.'`]*)",
        str(text or ""),
    )
    if not match:
        return ""
    symbol = match.group(1).strip().rstrip(".")
    if symbol in {"_", "Inv"} or symbol.startswith("<"):
        return ""
    return symbol


def _view_has_live_call_site(view: dict[str, Any], goal_text: str) -> bool:
    frontier = _dict(view.get("program_frontier"))
    call_sites = frontier.get("call_sites")
    if isinstance(call_sites, list) and any(isinstance(item, dict) for item in call_sites):
        return True
    if "<@" in str(goal_text or ""):
        return True
    alignment = _dict(frontier.get("frontier_alignment"))
    rows = alignment.get("rows")
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict):
                continue
            text = " ".join(str(row.get(key) or "") for key in ("role", "left", "right"))
            if "call" in text.lower() or "<@" in text:
                return True
    return False


def _goal_text_contains_call_site(text: str) -> bool:
    return "<@" in str(text or "") or bool(
        re.search(r"\bcall\s+[A-Za-z_][A-Za-z0-9_.'`]*", str(text or ""))
    )

