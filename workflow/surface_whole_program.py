"""Whole-program region/shape analysis for the proof surface.

Extracted verbatim from workflow/surface_composer.py (the composer both
grew and consumed it). Reads structured regions + plan facts and produces
the whole-program structure fact and observations the panels render.
Layering: below surface_panels (which imports from here), above the core
goal-text scanners.
"""
from __future__ import annotations

import re
from typing import Any
from workflow.surface_model import _drop_empty


def _whole_program_regions_for_side(
    setup: dict[str, Any],
    frontier: dict[str, Any],
    lookahead: Any,
    side: str,
) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    side_setup = setup.get(side) if isinstance(setup.get(side), dict) else {}
    setup_summary = str(side_setup.get("summary") or "").strip()
    setup_count = _setup_statement_count(setup_summary)
    if setup_count:
        out.append({
            "kind": "setup",
            "label": f"setup-block({setup_count})",
            "signature": _setup_statement_signature(setup_summary),
        })
    side_frontier = frontier.get(side) if isinstance(frontier.get(side), dict) else {}
    frontier_region = _whole_program_region_from_entry(side_frontier)
    if frontier_region:
        frontier_region = dict(frontier_region)
        frontier_region["role"] = "current"
        out.append(frontier_region)
    if isinstance(lookahead, list):
        for item in lookahead:
            if not isinstance(item, dict):
                continue
            if str(item.get("side") or "").strip() != side:
                continue
            region = _whole_program_region_from_entry(item)
            if region:
                region = dict(region)
                region["role"] = "after"
                out.append(region)
    return out


def _setup_statement_count(summary: str) -> int:
    if not summary:
        return 0
    stripped = _strip_setup_call_tag(summary).strip()
    count_match = re.match(r"^(\d+)\s+setup statement\(s\):", stripped)
    if count_match:
        return int(count_match.group(1))
    return len(_setup_statements(summary))


def _setup_statement_signature(summary: str) -> str:
    statements = _setup_statements(summary)
    if not statements:
        return ""
    return "; ".join(
        _inline_preview(stmt, limit=_WHOLE_PROGRAM_SETUP_SIGNATURE_PREVIEW_LIMIT)
        for stmt in statements[:_WHOLE_PROGRAM_SETUP_SIGNATURE_LIMIT]
    )


def _whole_program_region_from_entry(entry: dict[str, Any]) -> dict[str, str]:
    if not isinstance(entry, dict) or not entry:
        return {}
    statement = str(entry.get("statement") or "").strip()
    head = _scope_entry_head(entry)
    if not head and _statement_is_proc_call(statement):
        head = "call"
    if not head:
        return {}
    procedure = str(entry.get("procedure") or "").strip()
    label = _frontier_head_label(head)
    if head == "call":
        call_name = (
            _proc_module_method(procedure)
            if procedure else _call_name_from_statement(statement)
        )
        if call_name:
            label = f"call {call_name}"
    elif head == "sample":
        label = "sample"
    elif head == "assignment":
        label = "assign"
    return _drop_empty({
        "kind": head,
        "label": label,
    })


def _call_name_from_statement(statement: str) -> str:
    match = re.search(
        r"<@\s*([A-Za-z_][A-Za-z0-9_'.]*(?:\([^;]*\))?\.[A-Za-z_][A-Za-z0-9_']*)",
        statement,
    )
    if not match:
        return ""
    return _proc_module_method(match.group(1))


def _should_show_whole_program_structure(
    left_regions: list[dict[str, str]],
    right_regions: list[dict[str, str]],
) -> bool:
    if not left_regions or not right_regions:
        return False
    left_kinds = [region.get("kind", "") for region in left_regions]
    right_kinds = [region.get("kind", "") for region in right_regions]
    wrapper_call = _is_wrapper_call_shape(left_regions, right_regions)
    current_only_same_shape = _is_current_only_same_shape(left_regions, right_regions)
    if current_only_same_shape and not wrapper_call:
        return False
    same_shape_with_lookahead = _is_same_shape_with_lookahead(left_regions, right_regions)
    shared_kinds = {
        kind for kind in left_kinds
        if kind and kind in right_kinds and kind != "setup"
    }
    current_left = next((r for r in left_regions if r.get("role") == "current"), {})
    current_right = next((r for r in right_regions if r.get("role") == "current"), {})
    current_mismatch = bool(
        current_left
        and current_right
        and current_left.get("kind") != current_right.get("kind")
    )
    later_left = any(region.get("role") == "after" for region in left_regions)
    later_right = any(region.get("role") == "after" for region in right_regions)
    prefix_vs_call = _is_prefix_block_vs_call_shape(left_regions, right_regions)
    return (
        wrapper_call
        or current_mismatch
        or same_shape_with_lookahead
        or prefix_vs_call
        or bool(shared_kinds and (later_left or later_right))
        or _has_region_count_delta(left_regions, right_regions)
    )


def _is_current_only_same_shape(
    left_regions: list[dict[str, str]],
    right_regions: list[dict[str, str]],
) -> bool:
    if [region.get("kind", "") for region in left_regions] != [
        region.get("kind", "") for region in right_regions
    ]:
        return False
    if _has_after_region(left_regions) or _has_after_region(right_regions):
        return False
    return bool(_current_region(left_regions) and _current_region(right_regions))


def _is_same_shape_with_lookahead(
    left_regions: list[dict[str, str]],
    right_regions: list[dict[str, str]],
) -> bool:
    return (
        _region_kind_sequence(left_regions) == _region_kind_sequence(right_regions)
        and _has_after_region(left_regions)
        and _has_after_region(right_regions)
    )


def _region_kind_sequence(regions: list[dict[str, str]]) -> list[str]:
    return [str(region.get("kind") or "") for region in regions]


def _current_region(regions: list[dict[str, str]]) -> dict[str, str]:
    return next((region for region in regions if region.get("role") == "current"), {})


def _has_after_region(regions: list[dict[str, str]]) -> bool:
    return any(region.get("role") == "after" for region in regions)


def _has_region_count_delta(
    left_regions: list[dict[str, str]],
    right_regions: list[dict[str, str]],
) -> bool:
    return (
        abs(len(left_regions) - len(right_regions))
        >= _WHOLE_PROGRAM_REGION_COUNT_DELTA_THRESHOLD
    )


def _is_wrapper_call_shape(
    left_regions: list[dict[str, str]],
    right_regions: list[dict[str, str]],
) -> bool:
    if not (_is_wrapper_call_side(left_regions) and _is_wrapper_call_side(right_regions)):
        return False
    return _wrapper_call_signature(left_regions) != _wrapper_call_signature(right_regions)


def _is_wrapper_call_side(regions: list[dict[str, str]]) -> bool:
    current = _current_region(regions)
    return (
        bool(current)
        and current.get("kind") == "call"
        and not _has_after_region(regions)
        and bool(regions)
        and regions[0].get("kind") == "setup"
        and all(
            region.get("kind") in _WHOLE_PROGRAM_WRAPPER_REGION_KINDS
            for region in regions
        )
    )


def _wrapper_call_signature(regions: list[dict[str, str]]) -> tuple[str, str]:
    setup = next((region for region in regions if region.get("kind") == "setup"), {})
    call = _current_region(regions)
    return str(setup.get("signature") or ""), str(call.get("label") or "")


def _wrapper_call_observations(
    left_regions: list[dict[str, str]],
    right_regions: list[dict[str, str]],
) -> list[str]:
    if not _is_wrapper_call_shape(left_regions, right_regions):
        return []
    left_setup, left_call = _wrapper_call_signature(left_regions)
    right_setup, right_call = _wrapper_call_signature(right_regions)
    out: list[str] = []
    if left_setup != right_setup:
        out.append("setup prefixes differ before the top-level call region")
    if left_call != right_call:
        out.append("top-level call labels differ after setup prefixes")
    return out or ["both sides expose setup work followed by one top-level call region"]


def _visible_call_labels(regions: list[dict[str, str]]) -> list[str]:
    return [
        str(region.get("label") or "").strip()
        for region in regions
        if region.get("kind") == "call" and str(region.get("label") or "").strip()
    ]


def _visible_call_labels_differ(
    left_regions: list[dict[str, str]],
    right_regions: list[dict[str, str]],
) -> bool:
    left = _visible_call_labels(left_regions)
    right = _visible_call_labels(right_regions)
    return bool(left and right and left != right)


def _call_label_positions(regions: list[dict[str, str]]) -> dict[str, int]:
    positions: dict[str, int] = {}
    for idx, region in enumerate(regions):
        if region.get("kind") != "call":
            continue
        label = str(region.get("label") or "").strip()
        if label and label not in positions:
            positions[label] = idx
    return positions


def _shared_call_label_position_observation(
    left_regions: list[dict[str, str]],
    right_regions: list[dict[str, str]],
) -> str:
    left = _call_label_positions(left_regions)
    right = _call_label_positions(right_regions)
    shifted = [
        label for label in left
        if label in right and left[label] != right[label]
    ]
    if not shifted:
        return ""
    label_text = ", ".join(shifted[:2])
    if len(shifted) > 2:
        label_text += f", ... ({len(shifted) - 2} more)"
    return f"shared visible top-level call label(s) appear at different positions: {label_text}"


def _has_intervening_guard_before_later_while(
    left_regions: list[dict[str, str]],
    right_regions: list[dict[str, str]],
) -> bool:
    return (
        _side_has_guard_before_while(left_regions)
        and any(region.get("kind") == "while" for region in right_regions)
    ) or (
        _side_has_guard_before_while(right_regions)
        and any(region.get("kind") == "while" for region in left_regions)
    )


def _side_has_guard_before_while(regions: list[dict[str, str]]) -> bool:
    seen_guard = False
    for region in regions:
        kind = region.get("kind")
        if kind == "if":
            seen_guard = True
        elif kind == "while" and seen_guard:
            return True
    return False


def _is_prefix_block_vs_call_shape(
    left_regions: list[dict[str, str]],
    right_regions: list[dict[str, str]],
) -> bool:
    return (
        _has_noncall_prefix_before_later_call(left_regions)
        and _has_current_or_earlier_call(right_regions)
    ) or (
        _has_noncall_prefix_before_later_call(right_regions)
        and _has_current_or_earlier_call(left_regions)
    )


def _has_noncall_prefix_before_later_call(regions: list[dict[str, str]]) -> bool:
    for idx, region in enumerate(regions):
        if region.get("kind") != "call" or region.get("role") != "after":
            continue
        prefix_kinds = [item.get("kind", "") for item in regions[:idx]]
        return bool(prefix_kinds) and all(
            kind in _WHOLE_PROGRAM_PREFIX_REGION_KINDS
            for kind in prefix_kinds
        )
    return False


def _has_current_or_earlier_call(regions: list[dict[str, str]]) -> bool:
    return any(
        region.get("kind") == "call" and region.get("role") != "after"
        for region in regions
    )


def _whole_program_observations(
    left_regions: list[dict[str, str]],
    right_regions: list[dict[str, str]],
) -> list[str]:
    observations: list[str] = []
    left_kinds = [region.get("kind", "") for region in left_regions]
    right_kinds = [region.get("kind", "") for region in right_regions]
    current_left = next((r for r in left_regions if r.get("role") == "current"), {})
    current_right = next((r for r in right_regions if r.get("role") == "current"), {})
    wrapper_observations = _wrapper_call_observations(left_regions, right_regions)
    observations.extend(wrapper_observations)
    shared_call_position = _shared_call_label_position_observation(left_regions, right_regions)
    if shared_call_position:
        observations.append(shared_call_position)
    if _is_same_shape_with_lookahead(left_regions, right_regions):
        observations.append("visible top-level region sequence matches across sides")
    if not wrapper_observations and _visible_call_labels_differ(left_regions, right_regions):
        observations.append("visible top-level call labels differ across sides")
    if current_left and current_right and current_left.get("kind") != current_right.get("kind"):
        observations.append(
            "current frontier heads differ, so the local frontier is one boundary inside a larger program shape"
        )
    if _has_intervening_guard_before_later_while(left_regions, right_regions):
        observations.append(
            "one side has an intervening guarded region before a later top-level while; both sides expose top-level while regions"
        )
    if _is_prefix_block_vs_call_shape(left_regions, right_regions):
        observations.append(
            "one side exposes non-call prefix regions before a later top-level call"
        )
    for kind in _WHOLE_PROGRAM_REORDER_REGION_KIND_PRIORITY:
        if kind == "call" and shared_call_position:
            continue
        if kind not in left_kinds or kind not in right_kinds:
            continue
        left_first = left_kinds.index(kind)
        right_first = right_kinds.index(kind)
        if left_first != right_first:
            observations.append(
                f"shared `{_frontier_head_label(kind)}` regions appear at different top-level positions"
            )
            break
    if _has_region_count_delta(left_regions, right_regions):
        observations.append("the visible top-level region counts differ across sides")
    return observations[:_WHOLE_PROGRAM_OBSERVATION_LIMIT]


def _whole_program_region_text(regions: list[dict[str, str]]) -> str:
    labels: list[str] = []
    for region in regions[:_WHOLE_PROGRAM_RENDER_REGION_LIMIT]:
        label = str(region.get("label") or region.get("kind") or "").strip()
        if label:
            labels.append(label)
    if len(regions) > _WHOLE_PROGRAM_RENDER_REGION_LIMIT:
        omitted = len(regions) - _WHOLE_PROGRAM_RENDER_REGION_LIMIT
        labels.append(f"... ({omitted} more)")
    return " | ".join(labels)


_PROC_CALL_RE = re.compile(
    r"[A-Za-z_]\w*(?:\((?:[^()]|\([^()]*\))*\))?\.[A-Za-z_]\w*\s*\("
)


_SETUP_SUMMARY_RE = re.compile(r"^\d+\s+setup statement\(s\):\s*(.*)$")


_SETUP_ANNOTATION_RE = re.compile(r"\s\[(?:call|procedure-call prefix):")


_WHOLE_PROGRAM_SETUP_SIGNATURE_LIMIT = 4


_WHOLE_PROGRAM_SETUP_SIGNATURE_PREVIEW_LIMIT = 56


_WHOLE_PROGRAM_RENDER_REGION_LIMIT = 7


_WHOLE_PROGRAM_OBSERVATION_LIMIT = 3


_WHOLE_PROGRAM_REGION_COUNT_DELTA_THRESHOLD = 2


_WHOLE_PROGRAM_PREFIX_REGION_KINDS = frozenset({"setup", "sample", "assignment"})


_WHOLE_PROGRAM_WRAPPER_REGION_KINDS = frozenset({"setup", "call"})


_WHOLE_PROGRAM_REORDER_REGION_KIND_PRIORITY = ("call", "while", "sample", "if")


def _setup_statements(text: Any) -> list[str]:
    if not isinstance(text, str):
        return []
    s = text.strip()
    if not s:
        return []
    tag_idx = _setup_annotation_index(s)
    if tag_idx != -1:
        s = s[:tag_idx].strip()
    match = _SETUP_SUMMARY_RE.match(s)
    if match:
        s = match.group(1)
    parts = [p.strip() for p in s.split(";")]
    return [p for p in parts if p and not p.startswith("...")]


def _statement_is_proc_call(text: Any) -> bool:
    if not isinstance(text, str) or not text.strip():
        return False
    if "<@" in text:
        return True
    if "<-" in text:
        return False
    return bool(_PROC_CALL_RE.search(text))


def _proc_module_method(proc: str) -> str:
    match = re.search(
        r"([A-Za-z_][A-Za-z0-9_']*)\s*(?:\([^()]*(?:\([^()]*\)[^()]*)*\))?\.([A-Za-z_][A-Za-z0-9_']*)\s*$",
        proc.strip(),
    )
    return f"{match.group(1)}.{match.group(2)}" if match else proc.strip()


def _strip_setup_call_tag(summary: str) -> str:
    tag_idx = _setup_annotation_index(summary)
    if tag_idx == -1:
        return summary
    return summary[:tag_idx].rstrip()


def _setup_annotation_index(summary: str) -> int:
    match = _SETUP_ANNOTATION_RE.search(summary)
    return match.start() if match else -1


def _scope_entry_head(entry: dict[str, Any]) -> str:
    head = str(entry.get("head") or "").strip()
    if head:
        return head
    statement = str(entry.get("statement") or "").strip()
    lowered = statement.lower()
    if lowered.startswith("if ") or lowered.startswith("if("):
        return "if"
    if lowered.startswith("while ") or lowered.startswith("while("):
        return "while"
    if "<@" in statement:
        return "call"
    if "<$" in statement:
        return "sample"
    if "<-" in statement:
        return "assignment"
    return ""


def _frontier_head_label(head: str) -> str:
    return {
        "if": "guarded if",
        "while": "while",
        "call": "call",
        "sample": "sample",
        "assignment": "assignment",
        "return": "return",
    }.get(head, head or "frontier")


def _inline_preview(text: str, *, limit: int = 72) -> str:
    compact = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(compact) <= limit:
        return compact
    cut = compact.rfind(" ", 0, max(0, limit - 3))
    if cut < int(limit * 0.55):
        cut = max(0, limit - 3)
    return compact[:cut].rstrip(" ,;(") + "..."
