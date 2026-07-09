"""Checkpoint domain objects.

CheckpointIndex is the shared coordinate system for menus, structural
checkpoint panels, restore anchors, route-health repairs, and resume
boundaries.  The first implementation wraps the existing dict surface so the
renderer can stay backward compatible while ownership moves out of the facade.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CheckpointOption:
    payload: dict[str, Any]

    @property
    def checkpoint_id(self) -> str:
        return str(self.payload.get("checkpoint_id") or "")

    @property
    def semantic_ids(self) -> list[str]:
        values = self.payload.get("semantic_ids")
        if isinstance(values, list):
            return [str(item) for item in values if str(item).strip()]
        semantic_id = str(self.payload.get("semantic_id") or "").strip()
        return [semantic_id] if semantic_id else []

    def to_dict(self) -> dict[str, Any]:
        return dict(self.payload)


@dataclass(frozen=True)
class CheckpointIndex:
    menu_options: list[CheckpointOption] = field(default_factory=list)
    structural_items: list[CheckpointOption] = field(default_factory=list)
    restore_option: CheckpointOption | None = None

    def menu_surface(self) -> list[dict[str, Any]]:
        return [item.to_dict() for item in self.menu_options]

    def structural_surface(self) -> list[dict[str, Any]]:
        return [item.to_dict() for item in self.structural_items]

    def to_dict(self) -> dict[str, Any]:
        return {
            "menu_options": self.menu_surface(),
            "structural_items": self.structural_surface(),
            "restore_option": (
                self.restore_option.to_dict()
                if self.restore_option is not None else {}
            ),
        }


def checkpoint_option(value: dict[str, Any] | None) -> CheckpointOption | None:
    if not isinstance(value, dict) or not value:
        return None
    return CheckpointOption(dict(value))
