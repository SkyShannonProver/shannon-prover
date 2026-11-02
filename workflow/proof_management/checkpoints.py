"""Checkpoint domain objects.

CheckpointIndex holds the rewind-menu options, with the pre-rewind restore
option first when one exists. CheckpointOption is the immutable boundary
object used by the manager; dict conversion happens only at the rendered
surface.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CheckpointOption:
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return dict(self.payload)


@dataclass(frozen=True)
class CheckpointIndex:
    menu_options: list[CheckpointOption] = field(default_factory=list)

    def menu_surface(self) -> list[dict[str, Any]]:
        return [item.to_dict() for item in self.menu_options]
