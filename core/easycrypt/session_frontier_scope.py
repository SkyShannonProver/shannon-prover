"""Frontier path/scope math for the prover workspace view.

Pure text/path computations over frontier rows and setup statements —
where the committed prefix has advanced to on each side, which scope a
frontier row belongs to, and lookahead over path keys. Extracted verbatim
from session_prover_workspace_view (which imports every name back, so its
internal callers and module attributes are unchanged). Names keep their
underscore form on purpose: this is a private sibling of the view module,
not a public API.
"""
from __future__ import annotations

import re
from typing import Any

from core.easycrypt.value_shapes import (
    as_dict as _dict,
    as_dict_list as _as_dict_list,
    drop_empty as _drop_empty,
    first_text as _first_text,
)
from core.easycrypt.session_display import (
    leading_statement as _leading_statement,
    preview as _preview,
    statement_head as _statement_head,
    string_list as _string_list,
)


def _frontier_setup_counts(alignment_root: dict[str, Any]) -> tuple[int, int]:
    for row in _as_dict_list(alignment_root.get("rows")):
        role = _first_text(row.get("role"), default="").lower()
        if "setup" not in role:
            continue
        location = _dict(row.get("location"))
        left_paths = _string_list(location.get("left_paths"))
        right_paths = _string_list(location.get("right_paths"))
        left = _first_text(row.get("left"), default="").lower()
        right = _first_text(row.get("right"), default="").lower()
        if "easycrypt marks the programs as synchronized" in left:
            left_paths = []
        if "easycrypt marks the programs as synchronized" in right:
            right_paths = []
        # Defensive guard: the setup prefix count must be TOP-LEVEL only (dotless paths
        # like "6", never an in-loop "7.1"). The source fix is upstream —
        # procedure_structured_regions no longer emits nested statements as setup
        # regions — so this filter is normally a no-op; it stays as an invariant
        # so any future setup-region path can never re-inflate the setup prefix past
        # a loop boundary.
        left_top = [p for p in left_paths if "." not in str(p)]
        right_top = [p for p in right_paths if "." not in str(p)]
        return (len(left_top), len(right_top))
    return (0, 0)


def _current_frontier_scope(
    alignment_root: dict[str, Any],
    *,
    call_sites: list[dict[str, Any]],
) -> dict[str, Any]:
    """Typed current-frontier contract for the presentation layer.

    ``frontier_alignment.rows`` is intentionally broad: it can include current
    calls plus deeper calls visible after inlining. This scope isolates the
    actionable frontier immediately after the leading setup prefix so downstream
    renderers do not pair loose one-sided rows themselves.
    """
    rows = _as_dict_list(alignment_root.get("rows"))
    if not rows:
        return {}
    setup = _current_frontier_setup(rows)
    setup = _trim_setup_to_earliest_frontier(rows, setup)
    floors = {
        "left": _max_path_key(_dict(setup.get("left")).get("paths")),
        "right": _max_path_key(_dict(setup.get("right")).get("paths")),
    }
    candidates: dict[str, list[tuple[tuple[int, ...], int, dict[str, Any]]]] = {
        "left": [],
        "right": [],
    }
    for idx, row in enumerate(rows):
        role = _first_text(row.get("role"), default="").lower()
        if "setup" in role or "residual after call" in role:
            continue
        for side in ("left", "right"):
            text = _frontier_row_side_text(row, side)
            if not text:
                continue
            path_key = _frontier_row_path_key(row, side, idx)
            if path_key <= floors[side]:
                continue
            entry = _frontier_scope_entry(
                row,
                side=side,
                text=text,
                path_key=path_key,
                fallback_index=idx,
                call_sites=call_sites,
            )
            if entry:
                candidates[side].append((path_key, idx, entry))
    left = _first_scope_candidate(candidates["left"])
    right = _first_scope_candidate(candidates["right"])
    if not left and not right and not setup:
        return {}
    current = _drop_empty({
        "kind": _current_frontier_kind(left, right),
        "left": left,
        "right": right,
    })
    lookahead = _current_frontier_lookahead(
        rows,
        current=current,
        floors=floors,
        call_sites=call_sites,
    )
    return _drop_empty({
        "setup": setup,
        "frontier": current,
        "tactic_active_tail": _tactic_active_tail(
            rows,
            call_sites=call_sites,
        ),
        "lookahead_after_frontier": lookahead,
    })


def _tactic_active_tail(
    rows: list[dict[str, Any]],
    *,
    call_sites: list[dict[str, Any]],
) -> dict[str, Any]:
    """Return each side's last visible top-level structural statement.

    ``frontier`` above is a program-reading coordinate: the first top-level
    statement after the setup prefix.  EasyCrypt suffix tactics such as
    ``while``, ``rnd``, and ``call`` instead require the relevant statement at
    the end of the selected program.  Keeping this second coordinate explicit
    prevents action policy from treating an earlier sample/call as executable
    merely because it is the first unmatched statement.

    Nested paths are deliberately ignored here.  A statement at ``2.1`` is
    inside the top-level statement at ``2`` and is not a suffix boundary until
    that enclosing branch/loop has been opened.
    """
    candidates: dict[str, list[tuple[tuple[int, ...], int, dict[str, Any]]]] = {
        "left": [],
        "right": [],
    }
    for idx, row in enumerate(rows):
        role = _first_text(row.get("role"), default="").lower()
        if "setup" in role or "residual after call" in role:
            continue
        for side in ("left", "right"):
            text = _frontier_row_side_text(row, side)
            if not text:
                continue
            path_key = _frontier_row_path_key(row, side, idx)
            if len(path_key) != 1 or path_key[0] >= 10_000:
                continue
            entry = _frontier_scope_entry(
                row,
                side=side,
                text=text,
                path_key=path_key,
                fallback_index=idx,
                call_sites=call_sites,
            )
            if entry:
                entry["authority"] = "top_level_program_ir"
                candidates[side].append((path_key, idx, entry))

    left = _last_scope_candidate(candidates["left"])
    right = _last_scope_candidate(candidates["right"])
    return _drop_empty({
        "kind": _current_frontier_kind(left, right),
        "left": left,
        "right": right,
    })


def _current_frontier_setup(rows: list[dict[str, Any]]) -> dict[str, Any]:
    for row in rows:
        role = _first_text(row.get("role"), default="").lower()
        if "setup" not in role:
            continue
        location = _dict(row.get("location"))
        return _drop_empty({
            "left": _frontier_setup_side(row, "left", location),
            "right": _frontier_setup_side(row, "right", location),
        })
    return {}


def _trim_setup_to_earliest_frontier(
    rows: list[dict[str, Any]],
    setup: dict[str, Any],
) -> dict[str, Any]:
    if not setup:
        return setup
    earliest = _earliest_frontier_path_by_side(rows)
    out = dict(setup)
    for side in ("left", "right"):
        first = earliest.get(side)
        side_setup = _dict(out.get(side))
        if not first or not side_setup:
            continue
        paths = _string_list(side_setup.get("paths"))
        kept = [
            path for path in paths
            if _path_key_from_text(path) and _path_key_from_text(path) < first
        ]
        if len(kept) == len(paths):
            continue
        if not kept:
            out.pop(side, None)
            continue
        summary = f"{len(kept)} setup statement(s) before current frontier"
        out[side] = _drop_empty({"paths": kept, "summary": summary})
    return _drop_empty(out)


def _earliest_frontier_path_by_side(rows: list[dict[str, Any]]) -> dict[str, tuple[int, ...]]:
    earliest: dict[str, tuple[int, ...]] = {}
    for idx, row in enumerate(rows):
        role = _first_text(row.get("role"), default="").lower()
        if "setup" in role or "residual after call" in role:
            continue
        for side in ("left", "right"):
            if not _frontier_row_side_text(row, side):
                continue
            path_key = _frontier_row_path_key(row, side, idx)
            if not path_key or path_key[0] >= 10_000:
                continue
            current = earliest.get(side)
            if current is None or path_key < current:
                earliest[side] = path_key
    return earliest


def _frontier_setup_side(
    row: dict[str, Any],
    side: str,
    location: dict[str, Any],
) -> dict[str, Any]:
    text = _frontier_row_side_text(row, side)
    paths = _string_list(location.get(f"{side}_paths"))
    return _drop_empty({
        "paths": paths,
        "summary": text,
    })


def _frontier_row_side_text(row: dict[str, Any], side: str) -> str:
    text = _first_text(row.get(side), default="").strip()
    lowered = text.lower()
    if (
        not text
        or lowered.startswith("no ")
        or "no matching" in lowered
        or lowered.startswith("easycrypt marks the programs as synchronized")
    ):
        return ""
    return text


def _max_path_key(paths: Any) -> tuple[int, ...]:
    parsed = [_path_key_from_text(path) for path in _string_list(paths)]
    parsed = [path for path in parsed if path]
    return max(parsed) if parsed else (0,)


def _frontier_row_path_key(
    row: dict[str, Any],
    side: str,
    fallback_index: int,
) -> tuple[int, ...]:
    location = _dict(row.get("location"))
    raw = location.get(f"{side}_path")
    if not raw:
        paths = _string_list(location.get(f"{side}_paths"))
        if paths:
            raw = paths[0]
    key = _path_key_from_text(raw)
    return key if key else (10_000, fallback_index)


def _path_key_from_text(raw: Any) -> tuple[int, ...]:
    parts = [int(part) for part in re.findall(r"\d+", str(raw or ""))]
    return tuple(parts)


def _frontier_scope_entry(
    row: dict[str, Any],
    *,
    side: str,
    text: str,
    path_key: tuple[int, ...],
    fallback_index: int,
    call_sites: list[dict[str, Any]],
) -> dict[str, Any]:
    path = _frontier_row_path_text(row, side)
    statement = _preview(text, limit=220)
    head = _statement_head(_leading_statement(statement))
    return _drop_empty({
        "side": side,
        "path": path,
        "path_key": list(path_key),
        "statement": statement,
        "head": head,
        "procedure": _frontier_scope_procedure(
            side=side,
            path=path,
            statement=statement,
            call_sites=call_sites,
        ) if head == "call" else "",
        "source_row": fallback_index,
    })


def _frontier_row_path_text(row: dict[str, Any], side: str) -> str:
    location = _dict(row.get("location"))
    raw = _first_text(location.get(f"{side}_path"), default="")
    if raw:
        return raw
    paths = _string_list(location.get(f"{side}_paths"))
    return paths[0] if paths else ""


def _frontier_scope_procedure(
    *,
    side: str,
    path: str,
    statement: str,
    call_sites: list[dict[str, Any]],
) -> str:
    stmt_norm = " ".join(statement.split())
    for site in call_sites:
        if _first_text(site.get("side"), default="") != side:
            continue
        site_path = _first_text(site.get("statement_path"), site.get("path"), default="")
        site_statement = " ".join(_first_text(site.get("statement"), default="").split())
        if path and site_path == path:
            return _first_text(site.get("procedure"), default="")
        if site_statement and (site_statement in stmt_norm or stmt_norm in site_statement):
            return _first_text(site.get("procedure"), default="")
    return ""


def _first_scope_candidate(
    candidates: list[tuple[tuple[int, ...], int, dict[str, Any]]],
) -> dict[str, Any]:
    if not candidates:
        return {}
    return min(candidates, key=lambda item: (item[0], item[1]))[2]


def _last_scope_candidate(
    candidates: list[tuple[tuple[int, ...], int, dict[str, Any]]],
) -> dict[str, Any]:
    if not candidates:
        return {}
    return max(candidates, key=lambda item: (item[0], item[1]))[2]


def _current_frontier_kind(left: dict[str, Any], right: dict[str, Any]) -> str:
    left_head = _first_text(left.get("head"), default="")
    right_head = _first_text(right.get("head"), default="")
    if left_head and right_head:
        return f"{left_head}_pair" if left_head == right_head else f"{left_head}_vs_{right_head}"
    if left_head:
        return f"left_{left_head}"
    if right_head:
        return f"right_{right_head}"
    return ""


def _current_frontier_lookahead(
    rows: list[dict[str, Any]],
    *,
    current: dict[str, Any],
    floors: dict[str, tuple[int, ...]],
    call_sites: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    current_paths = {
        (side, _first_text(_dict(current.get(side)).get("path"), default=""))
        for side in ("left", "right")
        if _dict(current.get(side))
    }
    current_keys = {
        side: tuple(int(part) for part in _dict(current.get(side)).get("path_key") or [])
        for side in ("left", "right")
    }
    candidates: list[tuple[tuple[int, ...], int, str, dict[str, Any]]] = []
    for idx, row in enumerate(rows):
        role = _first_text(row.get("role"), default="").lower()
        if "frontier" not in role or "residual" in role:
            continue
        for side in ("left", "right"):
            text = _frontier_row_side_text(row, side)
            if not text:
                continue
            path = _frontier_row_path_text(row, side)
            if (side, path) in current_paths:
                continue
            path_key = _frontier_row_path_key(row, side, idx)
            floor = current_keys.get(side) or floors.get(side) or (0,)
            if path_key <= floor:
                continue
            if _path_key_is_descendant(path_key, floor):
                continue
            entry = _frontier_scope_entry(
                row,
                side=side,
                text=text,
                path_key=path_key,
                fallback_index=idx,
                call_sites=call_sites,
            )
            if entry:
                entry["not_current"] = "after current frontier"
                candidates.append((path_key, idx, side, entry))
    selected_keys: dict[str, list[tuple[int, ...]]] = {"left": [], "right": []}
    out: list[dict[str, Any]] = []
    for path_key, _idx, side, entry in sorted(candidates, key=lambda item: (item[0], item[1], item[2])):
        if any(_path_key_is_descendant(path_key, parent) for parent in selected_keys[side]):
            continue
        out.append(entry)
        selected_keys[side].append(path_key)
    return out


def _path_key_is_descendant(path_key: tuple[int, ...], parent: tuple[int, ...]) -> bool:
    return (
        bool(path_key)
        and bool(parent)
        and len(path_key) > len(parent)
        and path_key[:len(parent)] == parent
    )
