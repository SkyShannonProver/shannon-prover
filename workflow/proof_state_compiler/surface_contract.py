"""Feature-neutral contract for one current manager surface profile."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SurfaceProfile:
    name: str
    stage: str
    allowed_intents: frozenset[str]
    paper_level: str | None = None
