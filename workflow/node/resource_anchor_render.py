"""Bounded rendering for EasyCrypt-resolved outer-handoff resources."""

from __future__ import annotations

import hashlib
from typing import Any


_MAX_ANCHORS = 8
_USES = frozenset({"apply", "call", "exact", "rewrite", "smt", "reference"})


def normalize_resource_anchors(value: object) -> tuple[dict[str, str], ...]:
    if value in (None, ()):
        return ()
    if not isinstance(value, (list, tuple)) or len(value) > _MAX_ANCHORS:
        raise ValueError("resource anchors must be a bounded list")
    anchors: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, raw in enumerate(value):
        if not isinstance(raw, dict):
            raise ValueError(f"resource anchor {index} must be an object")
        anchor = {
            key: str(raw.get(key) or "").strip()
            for key in (
                "symbol",
                "intended_use",
                "role",
                "source_ref",
                "declaration_sha256",
                "declaration",
            )
        }
        symbol = anchor["symbol"]
        if not symbol or symbol in seen:
            raise ValueError("resource anchors require unique symbols")
        if anchor["intended_use"] not in _USES:
            raise ValueError(f"resource anchor {symbol!r} has invalid intended use")
        if not anchor["role"] or len(anchor["role"]) > 500:
            raise ValueError(f"resource anchor {symbol!r} has invalid role")
        if not anchor["source_ref"]:
            raise ValueError(f"resource anchor {symbol!r} has no native source")
        if (
            len(anchor["declaration_sha256"]) != 64
            or hashlib.sha256(anchor["declaration"].encode("utf-8")).hexdigest()
            != anchor["declaration_sha256"]
        ):
            raise ValueError(f"resource anchor {symbol!r} declaration hash mismatch")
        seen.add(symbol)
        anchors.append(anchor)
    return tuple(anchors)


def render_resource_anchors_markdown(value: object) -> str:
    anchors = normalize_resource_anchors(value)
    if not anchors:
        return ""
    lines = [
        "## Persistent handoff resource anchors",
        "",
        "These declarations were explicitly selected by the outer constructor and "
        "resolved by EasyCrypt at handoff. They are durable construction guidance, "
        "not proof-state facts. Try the stated resource before guessing synonymous "
        "lemma names; if it does not fit the current goal, use native manager feedback "
        "and choose another route.",
        "",
    ]
    for anchor in anchors:
        lines.extend([
            f"- `{anchor['symbol']}` — intended use `{anchor['intended_use']}`; "
            f"role: {anchor['role']}; declaration hash "
            f"`{anchor['declaration_sha256'][:16]}…`",
            "",
            "  ```easycrypt",
            *[f"  {line}" for line in anchor["declaration"].splitlines()],
            "  ```",
            "",
        ])
    return "\n".join(lines).rstrip()
