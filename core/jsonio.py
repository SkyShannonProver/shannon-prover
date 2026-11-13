"""JSON and JSONL file helpers shared by the runtime.

There are two read contracts on purpose. ``read_json_object`` is strict: a
missing, unreadable, malformed or non-object file raises. ``read_json_object_or_empty``
is best effort and returns ``{}`` for all of those. Choose by what the caller
must do with a bad file; a fail-closed reader must never use the second one.
"""
from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any


def read_json_object(path: Path) -> dict[str, Any]:
    """The JSON object stored at ``path``; anything else raises."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected JSON object: {path}")
    return data


def read_json_object_or_empty(path: Path) -> dict[str, Any]:
    """The JSON object at ``path``, or ``{}`` if it is missing, unreadable or not an object."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Object records of a JSONL file; no file gives [], bad or non-object lines are skipped."""
    if not path.is_file():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            records.append(value)
    return records


def append_jsonl(path: Path, record: Mapping[str, Any]) -> None:
    """Append one sorted-key JSON line to ``path``, creating its directory."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, sort_keys=True) + "\n")


def _reject_constant(value: str) -> Any:
    raise ValueError(f"non-finite JSON number is forbidden: {value}")


def strict_json_loads(text: str) -> Any:
    """``json.loads`` that rejects ``NaN``, ``Infinity`` and ``-Infinity``."""
    return json.loads(text, parse_constant=_reject_constant)
