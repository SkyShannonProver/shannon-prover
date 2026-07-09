"""Shared low-level helpers for proof-management surfaces."""
from __future__ import annotations

import json
from typing import Any


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, tuple):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value]
    return []


def _preview(text: str, *, limit: int) -> str:
    one_line = " ".join(str(text).split())
    if len(one_line) <= limit:
        return one_line
    return one_line[: max(0, limit - 3)].rstrip() + "..."


def _dedupe_dicts(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        compact = _drop_empty(item)
        key = json.dumps(compact, sort_keys=True, default=str)
        if key in seen:
            continue
        seen.add(key)
        out.append(compact)
    return out


def _drop_empty(value: Any) -> Any:
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in value.items():
            compact = _drop_empty(item)
            if compact in (None, "", [], {}):
                continue
            out[key] = compact
        return out
    if isinstance(value, list):
        return [
            item
            for item in (_drop_empty(item) for item in value)
            if item not in (None, "", [], {})
        ]
    return value


def _drop_empty_precheck(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _drop_empty_precheck(item)
            for key, item in value.items()
            if item not in (None, "", [], {})
        }
    if isinstance(value, list):
        return [
            _drop_empty_precheck(item)
            for item in value
            if item not in (None, "", [], {})
        ]
    return value


def node_memory_slug(value: str) -> str:
    """Filesystem-safe node-memory dir slug. The supervisor (progress) and
    the worker (proof_node_runtime) MUST agree on this mapping — the worker
    is spawned with a slug the supervisor computed."""
    out = []
    for ch in str(value or "node"):
        out.append(ch if ch.isalnum() else "_")
    return "".join(out).strip("_") or "node"


def coerce_string_list(value: Any) -> list[str]:
    """List/tuple -> stringified non-blank items (falsy items dropped);
    scalar -> one-item list of its non-blank text. Distinct from the
    module-private `_string_list`, which keeps falsy items like 0/False."""
    if isinstance(value, list):
        return [str(item) for item in value if str(item or "").strip()]
    if isinstance(value, tuple):
        return [str(item) for item in value if str(item or "").strip()]
    text = str(value or "").strip()
    return [text] if text else []


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Dict records of a JSONL file; missing file -> [], bad lines skipped."""
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            out.append(value)
    return out
