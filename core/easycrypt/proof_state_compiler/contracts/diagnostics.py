"""Feature-neutral structured diagnostics carried from P3 to presentation."""

from __future__ import annotations

import json
from dataclasses import dataclass

from core.easycrypt.proof_state_compiler.contracts.evidence import EvidenceRef
from core.easycrypt.proof_state_compiler.contracts.presentation import (
    MAX_INTERNAL_PRESENTATION_BYTES,
)


HAS_PLACEHOLDERS = "has_placeholders"
CHOICE_REQUIRED = "choice_required"
EXPLANATION_ONLY = "explanation_only"
DIAGNOSTIC_APPLICABILITIES = frozenset({
    HAS_PLACEHOLDERS,
    CHOICE_REQUIRED,
    EXPLANATION_ONLY,
})
@dataclass(frozen=True)
class StructuredDiagnostic:
    """One compact diagnostic; candidate populations remain audit-only."""

    producer_id: str
    code: str
    primary: str
    notes: tuple[str, ...]
    help: str
    applicability: str
    evidence_refs: tuple[EvidenceRef, ...]
    trigger_id: str = ""
    placeholder_shape: str = ""
    terminal: str = ""

    def __post_init__(self) -> None:
        if not self.producer_id or not self.code or not self.primary:
            raise ValueError("structured diagnostic requires identity and primary")
        if self.applicability not in DIAGNOSTIC_APPLICABILITIES:
            raise ValueError("structured diagnostic applicability is invalid")
        if not self.evidence_refs:
            raise ValueError("structured diagnostic requires evidence")
        if len(self.notes) > 2 or any(not item for item in self.notes):
            raise ValueError("structured diagnostic notes are not bounded")
        if len(self.notes) != len(set(self.notes)):
            raise ValueError("structured diagnostic notes contain duplicates")
        if self.applicability == HAS_PLACEHOLDERS:
            if (
                not self.placeholder_shape
                or "<" not in self.placeholder_shape
                or ">" not in self.placeholder_shape
                or not self.help
            ):
                raise ValueError(
                    "placeholder diagnostic requires a typed shape and help"
                )
        elif self.placeholder_shape and self.applicability != CHOICE_REQUIRED:
            raise ValueError(
                "only placeholder/choice diagnostics may carry an application shape"
            )
        if self.terminal and self.applicability != EXPLANATION_ONLY:
            raise ValueError(
                "only explanation-only diagnostics may carry a strategy terminal"
            )
        if self.applicability == CHOICE_REQUIRED and not self.help:
            raise ValueError("choice-required diagnostic requires help")
        if self.identity_payload_bytes > MAX_INTERNAL_PRESENTATION_BYTES:
            raise ValueError(
                "structured diagnostic exceeds the internal safety bound"
            )

    def identity_payload(self) -> dict[str, object]:
        """Complete internal content used for identity, audit, and tooling."""

        payload: dict[str, object] = {
            "code": self.code,
            "primary": self.primary,
            "applicability": self.applicability,
        }
        if self.notes:
            payload["notes"] = list(self.notes)
        if self.help:
            payload["help"] = self.help
        if self.placeholder_shape:
            payload["placeholder_shape"] = self.placeholder_shape
        if self.terminal:
            payload["terminal"] = self.terminal
        return payload

    @property
    def identity_payload_bytes(self) -> int:
        return len(json.dumps(
            self.identity_payload(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8"))
