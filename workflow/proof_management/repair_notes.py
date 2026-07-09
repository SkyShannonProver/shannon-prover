"""Typed repair-note schema for checkpoint rewinds.

The agent can attach a free-form ``rewind_note`` when it asks to go back to a
checkpoint.  This module turns that loose payload into a stable manager-owned
shape that route memory, lineage, and later resume briefing can share.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from core.easycrypt.value_shapes import drop_empty as _drop_empty


@dataclass(frozen=True)
class RewindNote:
    hypothesis: str = ""
    broken_boundary_kind: str = ""
    missing_facts: list[str] = field(default_factory=list)
    intended_repair: str = ""
    reuse_expectation: str = ""
    negative_memories: list[dict[str, Any]] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = _drop_empty({
            "schema_version": 1,
            "hypothesis": self.hypothesis,
            "broken_boundary_kind": self.broken_boundary_kind,
            "missing_facts": list(self.missing_facts),
            "intended_repair": self.intended_repair,
            "reuse_expectation": self.reuse_expectation,
            "negative_memories": [
                dict(item) for item in self.negative_memories
            ],
            "extra": dict(self.extra),
        })
        if list(payload.keys()) == ["schema_version"]:
            return {}
        return payload

    def summary(self) -> dict[str, Any]:
        return _drop_empty({
            "hypothesis": self.hypothesis,
            "broken_boundary_kind": self.broken_boundary_kind,
            "missing_facts": list(self.missing_facts[:8]),
            "intended_repair": self.intended_repair,
            "reuse_expectation": self.reuse_expectation,
            "negative_memory_count": len(self.negative_memories),
        })


def normalize_rewind_note(value: Any) -> RewindNote:
    raw = dict(value) if isinstance(value, dict) else {}
    negative_entries: list[Any] = []
    for key in _NEGATIVE_MEMORY_KEYS:
        item = raw.get(key)
        if isinstance(item, list):
            negative_entries.extend(item)
        elif item not in (None, "", {}, []):
            negative_entries.append(item)

    known = {
        "schema_version",
        "hypothesis",
        "broken_boundary_kind",
        "boundary_kind",
        "missing_facts",
        "missing_fact",
        "intended_repair",
        "repair",
        "reuse_expectation",
        *_NEGATIVE_MEMORY_KEYS,
    }
    return RewindNote(
        hypothesis=_text(raw.get("hypothesis")),
        broken_boundary_kind=(
            _text(raw.get("broken_boundary_kind"))
            or _text(raw.get("boundary_kind"))
        ),
        missing_facts=_text_list(
            raw.get("missing_facts", raw.get("missing_fact"))
        ),
        intended_repair=(
            _text(raw.get("intended_repair")) or _text(raw.get("repair"))
        ),
        reuse_expectation=_text(raw.get("reuse_expectation")),
        negative_memories=[
            item for item in (
                _negative_memory_entry(entry)
                for entry in negative_entries
            ) if item
        ],
        extra={
            str(key): item
            for key, item in raw.items()
            if key not in known
        },
    )


def rewind_note_summary(value: Any) -> dict[str, Any]:
    return normalize_rewind_note(value).summary()


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (list, tuple)):
        return "; ".join(str(item).strip() for item in value if str(item).strip())
    return str(value).strip()


def _text_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, tuple):
        return [str(item).strip() for item in value if str(item).strip()]
    text = _text(value)
    return [text] if text else []


def _negative_memory_entry(entry: Any) -> dict[str, Any]:
    if isinstance(entry, dict):
        out = dict(entry)
        if "avoid_pattern" not in out:
            for key in ("pattern", "avoid", "do_not"):
                if key in out:
                    out["avoid_pattern"] = out.get(key)
                    break
        return _drop_empty({
            "kind": _text(out.get("kind")),
            "scope": _text(out.get("scope")),
            "avoid_pattern": _text(out.get("avoid_pattern")),
            "reason": _text(out.get("reason")),
            "applies_when": _text(out.get("applies_when")),
            "evidence": dict(out.get("evidence"))
            if isinstance(out.get("evidence"), dict) else {},
        })
    text = _text(entry)
    if not text:
        return {}
    return {
        "avoid_pattern": text,
        "reason": "recorded by rewind_note",
    }



_NEGATIVE_MEMORY_KEYS = (
    "negative_memory",
    "negative_memories",
    "avoid_patterns",
    "avoid",
    "do_not",
)
