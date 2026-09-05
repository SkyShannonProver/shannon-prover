"""Bounded, non-semantic guidance that survives prover continuation.

The brief deliberately contains no proof-state reconstruction and no hidden
model reasoning.  It preserves only explicit outer handoff material and the
inner prover's final concrete blockers/discoveries.  Current proof state and
accepted history remain manager-owned.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from workflow.node.resource_anchor_render import (
    normalize_resource_anchors,
    render_resource_anchors_markdown,
)


CONTINUATION_BRIEF_KIND = "proof_continuation_brief"
CONTINUATION_BRIEF_VERSION = 1
_SUFFIX_LIMIT = 12_000
_ITEM_LIMIT = 12
_ITEM_CHARS = 3_000
_BREADCRUMB_LIMIT = 12


def _bounded_text(value: object, *, limit: int) -> str:
    return str(value or "").strip()[:limit]


def _bounded_items(value: object) -> list[str]:
    if value in (None, ()):  # absent is the common successful-proof case
        return []
    if not isinstance(value, (list, tuple)):
        raise ValueError("continuation brief report fields must be lists")
    return [
        str(item).strip()[:_ITEM_CHARS]
        for item in value[:_ITEM_LIMIT]
        if isinstance(item, str) and str(item).strip()
    ]


def continuation_brief_from_outer_handoff(context: object) -> dict[str, Any]:
    """Project one validated outer handoff into durable untrusted guidance."""

    if not isinstance(context, dict) or context.get("kind") != "outer_proof_handoff":
        return {}
    full_suffix = str(context.get("candidate_suffix") or "").strip()
    suffix = full_suffix[:_SUFFIX_LIMIT]
    return normalize_continuation_brief({
        "kind": CONTINUATION_BRIEF_KIND,
        "version": CONTINUATION_BRIEF_VERSION,
        "origin": "outer_proof_handoff",
        "strategy_note": _bounded_text(context.get("strategy_note"), limit=8_000),
        "failed_tactic": _bounded_text(context.get("failed_tactic"), limit=4_000),
        "failure_summary": _bounded_text(
            context.get("failure_summary"), limit=4_000
        ),
        "candidate_suffix": suffix,
        "candidate_suffix_sha256": hashlib.sha256(
            full_suffix.encode("utf-8")
        ).hexdigest() if full_suffix else "",
        "candidate_suffix_full_chars": len(full_suffix),
        "candidate_suffix_truncated": len(full_suffix) > len(suffix),
        "resource_anchors": list(context.get("resource_anchors") or []),
        "source_breadcrumbs": [],
        "blockers": [],
        "discoveries": [],
    })


def merge_agent_report(
    brief: object,
    report: object,
) -> dict[str, Any]:
    """Add final public report facts without inventing strategy advice."""

    base = normalize_continuation_brief(brief) if brief else {
        "kind": CONTINUATION_BRIEF_KIND,
        "version": CONTINUATION_BRIEF_VERSION,
        "origin": "prover_report",
        "strategy_note": "",
        "failed_tactic": "",
        "failure_summary": "",
        "candidate_suffix": "",
        "candidate_suffix_sha256": "",
        "candidate_suffix_full_chars": 0,
        "candidate_suffix_truncated": False,
        "resource_anchors": [],
        "source_breadcrumbs": [],
        "blockers": [],
        "discoveries": [],
    }
    if isinstance(report, dict):
        # Missing fields mean that no newer report was produced (for example,
        # on timeout). Only an explicitly present list replaces prior guidance.
        for key in ("blockers", "discoveries"):
            if key in report:
                base[key] = _bounded_items(report[key])
    if not any(
        base.get(key)
        for key in (
            "strategy_note",
            "failed_tactic",
            "failure_summary",
            "candidate_suffix",
            "resource_anchors",
            "source_breadcrumbs",
            "blockers",
            "discoveries",
        )
    ):
        return {}
    return normalize_continuation_brief(base)


def normalize_continuation_brief(value: object) -> dict[str, Any]:
    """Validate and normalize the current bounded brief contract."""

    if not isinstance(value, dict):
        raise ValueError("continuation brief must be an object")
    if (
        value.get("kind") != CONTINUATION_BRIEF_KIND
        or value.get("version") != CONTINUATION_BRIEF_VERSION
    ):
        raise ValueError("unsupported continuation brief contract")
    suffix = _bounded_text(value.get("candidate_suffix"), limit=_SUFFIX_LIMIT)
    full_chars = value.get("candidate_suffix_full_chars", len(suffix))
    if isinstance(full_chars, bool) or not isinstance(full_chars, int) or full_chars < len(suffix):
        raise ValueError("invalid continuation brief suffix length")
    truncated = value.get("candidate_suffix_truncated", full_chars > len(suffix))
    if type(truncated) is not bool or truncated != (full_chars > len(suffix)):
        raise ValueError("invalid continuation brief suffix truncation marker")
    suffix_sha = str(value.get("candidate_suffix_sha256") or "").strip()
    if suffix_sha and (
        len(suffix_sha) != 64
        or any(char not in "0123456789abcdef" for char in suffix_sha)
    ):
        raise ValueError("invalid continuation brief suffix digest")
    anchors = normalize_resource_anchors(value.get("resource_anchors") or [])
    breadcrumbs = _normalize_source_breadcrumbs(value.get("source_breadcrumbs"))
    return {
        "kind": CONTINUATION_BRIEF_KIND,
        "version": CONTINUATION_BRIEF_VERSION,
        "origin": _bounded_text(value.get("origin"), limit=64),
        "strategy_note": _bounded_text(value.get("strategy_note"), limit=8_000),
        "failed_tactic": _bounded_text(value.get("failed_tactic"), limit=4_000),
        "failure_summary": _bounded_text(value.get("failure_summary"), limit=4_000),
        "candidate_suffix": suffix,
        "candidate_suffix_sha256": suffix_sha,
        "candidate_suffix_full_chars": full_chars,
        "candidate_suffix_truncated": truncated,
        "resource_anchors": list(anchors),
        "source_breadcrumbs": breadcrumbs,
        "blockers": _bounded_items(value.get("blockers")),
        "discoveries": _bounded_items(value.get("discoveries")),
    }


def append_source_breadcrumb(
    brief: object,
    event: object,
) -> dict[str, Any]:
    """Persist one bounded manager-observed source-navigation location."""

    base = normalize_continuation_brief(brief) if brief else normalize_continuation_brief({
        "kind": CONTINUATION_BRIEF_KIND,
        "version": CONTINUATION_BRIEF_VERSION,
        "origin": "source_navigation",
    })
    breadcrumb = _source_breadcrumb_from_event(event)
    if not breadcrumb:
        return base
    rows = [*base["source_breadcrumbs"], breadcrumb]
    unique: list[dict[str, Any]] = []
    for row in reversed(rows):
        if row not in unique:
            unique.append(row)
    base["source_breadcrumbs"] = list(reversed(unique[:_BREADCRUMB_LIMIT]))
    return normalize_continuation_brief(base)


def _normalize_source_breadcrumbs(value: object) -> list[dict[str, Any]]:
    if value in (None, ()):
        return []
    if not isinstance(value, (list, tuple)):
        raise ValueError("continuation brief source breadcrumbs must be a list")
    rows: list[dict[str, Any]] = []
    for item in value[-_BREADCRUMB_LIMIT:]:
        row = _source_breadcrumb_from_event(item)
        if row:
            rows.append(row)
    return rows


def _source_breadcrumb_from_event(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    tool = _bounded_text(value.get("tool"), limit=16)
    if not tool:
        event = str(value.get("event") or "")
        tool = event.rsplit(".", 1)[-1] if event.startswith(
            "easycrypt.source_resource."
        ) else ""
    if tool not in {"read", "search", "resolve"}:
        return {}
    row: dict[str, Any] = {"tool": tool}
    for key, limit in (
        ("path", 1_000),
        ("query", 256),
        ("scope", 16),
        ("requested", 256),
        ("resolved", 512),
        ("status", 32),
    ):
        text = _bounded_text(value.get(key), limit=limit)
        if text:
            row[key] = text
    for key in ("start_line", "end_line", "match_count"):
        number = value.get(key)
        if isinstance(number, int) and not isinstance(number, bool) and number >= 0:
            row[key] = number
    raw_locations = value.get("locations")
    if isinstance(raw_locations, (list, tuple)):
        locations = [
            _bounded_text(item, limit=1_200)
            for item in raw_locations[:8]
            if isinstance(item, str) and str(item).strip()
        ]
        if locations:
            row["locations"] = locations
    return row if len(row) > 1 else {}


def render_continuation_brief_markdown(value: object) -> str:
    brief = normalize_continuation_brief(value)
    sections = [
        "## Durable proof continuation brief",
        "",
        "This is bounded, untrusted construction guidance carried across context "
        "refreshes and resume jobs. The current manager goal and accepted tactic "
        "history remain authoritative. Decide the next proof strategy yourself.",
    ]
    fields = (
        ("Outer strategy", "strategy_note"),
        ("First rejected tactic", "failed_tactic"),
        ("Failure summary", "failure_summary"),
        ("Candidate suffix", "candidate_suffix"),
    )
    for title, key in fields:
        text = str(brief.get(key) or "").strip()
        if text:
            sections.extend(["", f"### {title}", "", text])
    if brief["candidate_suffix_truncated"]:
        sections.extend([
            "",
            "The candidate suffix is intentionally truncated; its full length was "
            f"{brief['candidate_suffix_full_chars']} characters and its digest is "
            f"`{brief['candidate_suffix_sha256']}`.",
        ])
    for title, key in (("Concrete blockers", "blockers"), ("Reported discoveries", "discoveries")):
        items = list(brief.get(key) or [])
        if items:
            sections.extend(["", f"### {title}", ""])
            sections.extend(f"- {item}" for item in items)
    breadcrumbs = list(brief.get("source_breadcrumbs") or [])
    if breadcrumbs:
        sections.extend(["", "### Source locations already inspected", ""])
        sections.extend(
            f"- `{json.dumps(item, ensure_ascii=False, sort_keys=True)}`"
            for item in breadcrumbs
        )
    anchors = render_resource_anchors_markdown(brief.get("resource_anchors"))
    if anchors:
        sections.extend(["", anchors])
    return "\n".join(sections).rstrip()
