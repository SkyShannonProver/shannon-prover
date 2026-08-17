"""Deterministic wire serialization for compiler audit artifacts."""

from __future__ import annotations

import json
from dataclasses import fields, is_dataclass
from typing import Any

from core.easycrypt.proof_state_compiler.contracts import (
    CompilationBundle,
    FrozenJsonArray,
    FrozenJsonObject,
    StrategyContract,
)


def to_wire(value: object) -> Any:
    """Serialize contracts without leaking dataclass implementation details."""

    if isinstance(value, FrozenJsonObject):
        return {key: to_wire(item) for key, item in value.entries}
    if isinstance(value, FrozenJsonArray):
        return [to_wire(item) for item in value.values]
    if isinstance(value, StrategyContract):
        # FeatureSpec owns the full rationale/anchor/choice declaration.  A
        # candidate bundle needs the enforced class without duplicating that
        # static declaration on every emitted item.
        return value.strategy_class
    if is_dataclass(value):
        return {
            field.name: to_wire(getattr(value, field.name))
            for field in fields(value)
            if field.metadata.get("wire", True)
        }
    if isinstance(value, tuple):
        return [to_wire(item) for item in value]
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    raise TypeError(f"cannot serialize compiler value {type(value).__name__}")


def serialize_bundle(bundle: CompilationBundle) -> dict[str, Any]:
    return to_wire(bundle)


def bundle_json(bundle: CompilationBundle) -> str:
    return json.dumps(
        serialize_bundle(bundle),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
