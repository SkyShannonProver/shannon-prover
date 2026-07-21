"""Typed compiler facts projected onto the public workspace surface.

This module is the boundary between ProofIR resources and presentation-neutral
workspace facts.  It never reads rendered candidate prose.  Only candidate-menu
items classified as compiler facts may cross this boundary.
"""
from __future__ import annotations

from typing import Any


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _fact_menu_items(proof_ir: dict[str, Any] | None) -> list[dict[str, Any]]:
    return [
        _dict(item)
        for item in _list(_dict(proof_ir).get("candidate_menu"))
        if _dict(item).get("info_kind") == "fact"
        and _dict(item).get("action_type") != "avoid_action"
    ]


def checked_structural_sources(
    proof_ir: dict[str, Any] | None,
) -> dict[str, list[dict[str, Any]]]:
    """Project checked seq positions and verified swap source frames."""
    seq_sources: list[dict[str, Any]] = []
    swap_sources: list[dict[str, Any]] = []
    seen_seq: set[str] = set()
    seen_frames: set[str] = set()
    for item in _fact_menu_items(proof_ir):
        factors = _dict(item.get("cost_factors"))
        seq = _dict(factors.get("structural_seq"))
        seq_form = str(seq.get("form") or "").strip()
        if seq_form and seq_form not in seen_seq:
            seen_seq.add(seq_form)
            seq_sources.append(seq)

        swap = _dict(factors.get("structural_swap"))
        frame = str(swap.get("frame") or "").strip()
        if not frame or frame in seen_frames:
            continue
        seen_frames.add(frame)
        swap_sources.append({
            "form": frame,
            "side": str(swap.get("side") or ""),
            "source_position": str(swap.get("source_position") or ""),
        })
    return {
        "seq_sources": seq_sources,
        "swap_sources": swap_sources,
    }


def loaded_named_routes(
    proof_ir: dict[str, Any] | None,
) -> list[dict[str, str]]:
    """Project exact loaded theorem routes already matched by ProofIR."""
    routes: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in _fact_menu_items(proof_ir):
        route = _dict(_dict(item.get("cost_factors")).get("loaded_named_route"))
        route_kind = str(route.get("route_kind") or "").strip()
        symbol = str(route.get("symbol") or "").strip()
        matched_form = str(route.get("matched_form") or "").strip()
        if not route_kind or not symbol or not matched_form:
            continue
        key = (route_kind, symbol)
        if key in seen:
            continue
        seen.add(key)
        routes.append({
            "route_kind": route_kind,
            "symbol": symbol,
            "matched_form": matched_form,
            "verification_status": str(route.get("verification_status") or ""),
        })
    return routes
