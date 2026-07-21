"""Read typed structural facts from the canonical workspace contract.

The compiler projection owns fact construction.  This presentation helper only
reads typed fields; it must never recover structure from candidate tactic text.
"""
from __future__ import annotations

from typing import Any


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _dict_items(value: Any) -> tuple[dict[str, Any], ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, dict))


def checked_seq_sources(view: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    frontier = _dict(view.get("program_frontier"))
    sources = _dict(frontier.get("checked_structural_sources"))
    return _dict_items(sources.get("seq_sources"))


def checked_swap_sources(view: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    frontier = _dict(view.get("program_frontier"))
    sources = _dict(frontier.get("checked_structural_sources"))
    return _dict_items(sources.get("swap_sources"))


def loaded_named_routes(view: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    context = _dict(view.get("application_context"))
    return _dict_items(context.get("loaded_named_routes"))


def has_checked_seq_source(view: dict[str, Any]) -> bool:
    return bool(checked_seq_sources(view))


def has_checked_swap_source(view: dict[str, Any]) -> bool:
    return bool(checked_swap_sources(view))
