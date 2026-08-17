"""Feature-neutral contract for one current manager surface profile."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SurfaceProfile:
    name: str
    stage: str
    description: str
    allowed_intents: frozenset[str]
    supported: bool = True
    paper_level: str | None = None
    paper_role: str = "paper"
    base_surface: str = "compiled"
