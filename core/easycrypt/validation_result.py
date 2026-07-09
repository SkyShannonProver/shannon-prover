"""Canonical errors/warnings validation-result shape.

Five view modules used to carry byte-identical copies of this frozen
dataclass (`ToolViewValidation`, `CommandSummaryValidation`,
`CommitResponseValidation`, `ProofContextViewValidation`,
`TacticExecutionResultValidation`). Each keeps its public name as an empty
subclass — dataclass `__repr__` reports the subclass qualname, so behavior
and rendering are unchanged. The near-copies with extra fields/semantics
(`SessionEpisodeTimelineValidation`, `ProverActionValidation`) are
deliberately not forced onto this base.

Leaf module: stdlib only, importable from anywhere without cycle risk.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ValidationResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
        }
