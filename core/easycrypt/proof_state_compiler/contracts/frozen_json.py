"""Deeply immutable JSON facts used at compiler pass boundaries."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class FrozenJsonObject(Mapping[str, object]):
    entries: tuple[tuple[str, object], ...] = ()

    def __post_init__(self) -> None:
        keys = [key for key, _ in self.entries]
        if len(keys) != len(set(keys)):
            raise ValueError("FrozenJsonObject contains duplicate keys")

    def __getitem__(self, key: str) -> object:
        for candidate, value in self.entries:
            if candidate == key:
                return value
        raise KeyError(key)

    def __iter__(self) -> Iterator[str]:
        return (key for key, _ in self.entries)

    def __len__(self) -> int:
        return len(self.entries)

    def to_dict(self) -> dict[str, Any]:
        return {key: thaw_json(value) for key, value in self.entries}


@dataclass(frozen=True)
class FrozenJsonArray(Sequence[object]):
    values: tuple[object, ...] = ()

    def __getitem__(self, index: int | slice) -> object:
        return self.values[index]

    def __len__(self) -> int:
        return len(self.values)

    def to_list(self) -> list[Any]:
        return [thaw_json(value) for value in self.values]


def freeze_json(value: Any) -> object:
    """Copy and freeze one JSON-ready value; reject implicit stringification."""

    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("compiler facts cannot contain non-finite floats")
        return value
    if isinstance(value, Mapping):
        entries: list[tuple[str, object]] = []
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError("compiler fact object keys must be strings")
            entries.append((key, freeze_json(item)))
        return FrozenJsonObject(tuple(entries))
    if isinstance(value, (list, tuple)):
        return FrozenJsonArray(tuple(freeze_json(item) for item in value))
    raise TypeError(
        f"unsupported compiler fact value {type(value).__name__}; expected JSON"
    )


def freeze_json_object(value: Mapping[str, Any] | None) -> FrozenJsonObject:
    frozen = freeze_json(dict(value or {}))
    if not isinstance(frozen, FrozenJsonObject):  # pragma: no cover
        raise TypeError("expected a JSON object")
    return frozen


def freeze_json_array(value: Sequence[Any] | None) -> FrozenJsonArray:
    frozen = freeze_json(list(value or []))
    if not isinstance(frozen, FrozenJsonArray):  # pragma: no cover
        raise TypeError("expected a JSON array")
    return frozen


def thaw_json(value: object) -> Any:
    if isinstance(value, FrozenJsonObject):
        return value.to_dict()
    if isinstance(value, FrozenJsonArray):
        return value.to_list()
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    raise TypeError(f"unsupported frozen compiler fact {type(value).__name__}")


def frozen_json_sha256(value: object) -> str:
    encoded = json.dumps(
        thaw_json(value),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
