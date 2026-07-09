"""Defensive shape-coercion helpers for JSON-ish view/payload data.

One canonical home for the tiny guards that ~60 modules used to re-define
privately (`_dict` / `_list` / `_drop_empty`). Import with a private alias so
call sites read unchanged:

    from core.easycrypt.value_shapes import as_dict as _dict

This module is a LEAF on purpose: no project imports, so any module (core,
workflow, tests) can use it without cycle risk.

Only the DOMINANT, exactly-identical variants were consolidated here. The
behavioral variants that remain in their own modules are deliberate, not
missed duplicates:
  - copy-on-return `_dict_list` (`[dict(item) for ...]` — different aliasing),
  - recursive `_drop_empty` (compacts nested dicts/lists — canonical home is
    `analysis/ec_utils.drop_empty_recursive`),
  - tuple-dropping `_drop_empty` (also drops `()`),
  - `_first_text(*values, default="")` (optional-default signature),
  - the `_string_list` family (each tuned to its caller's tolerance for
    tuples/None/joining).
Do not "unify" those into this module without checking every caller.
"""
from __future__ import annotations

from typing import Any


def as_dict(value: Any) -> dict[str, Any]:
    """`value` if it is a dict, else `{}`. Returns the SAME object (no copy)."""
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    """`value` if it is a list, else `[]`. Returns the SAME object (no copy)."""
    return value if isinstance(value, list) else []


def drop_empty(value: dict[str, Any]) -> dict[str, Any]:
    """A copy of `value` without None/''/[]/{}-valued keys. SHALLOW: nested
    containers are kept as-is, and empty tuples `()` are kept (some callers
    rely on both — the recursive/tuple variants live with those callers)."""
    return {key: item for key, item in value.items() if item not in (None, "", [], {})}


def as_dict_list(value: Any) -> list[dict[str, Any]]:
    """The dict items of `value` when it is a list, else `[]`. Returns the
    SAME item objects (no copy — the copy-on-return variant stays with its
    workflow callers)."""
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def first_text(*values: Any, default: str) -> str:
    """First value that is a non-blank string (stripped), else the first
    non-empty value stringified, else `default` (keyword-required)."""
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
        if value not in (None, "", [], {}):
            return str(value)
    return default


def as_dict_copy(value: Any) -> dict[str, Any]:
    """A COPY of `value` when it is a dict, else `{}` (callers mutate the
    result without aliasing the source — the copy-on-return variant)."""
    return dict(value) if isinstance(value, dict) else {}
