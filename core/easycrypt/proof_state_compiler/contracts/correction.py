"""Generic presentation metadata for one verified recovery correction."""

from __future__ import annotations

from dataclasses import dataclass

from core.easycrypt.proof_state_compiler.contracts.presentation import (
    MAX_INTERNAL_PRESENTATION_BYTES,
)


DO_YOU_MEAN = "do_you_mean"
CORRECTION_PRESENTATION_KINDS = frozenset({DO_YOU_MEAN})


@dataclass(frozen=True)
class CorrectionPresentation:
    """A bounded explanation attached to one action, not a second item."""

    presentation_kind: str
    reason_code: str
    reason: str

    def __post_init__(self) -> None:
        if self.presentation_kind not in CORRECTION_PRESENTATION_KINDS:
            raise ValueError("unsupported correction presentation kind")
        if not self.reason_code or not self.reason.strip():
            raise ValueError("correction presentation requires a reason")
        if (
            self.reason != self.reason.strip()
            or len(self.reason.encode("utf-8"))
            > MAX_INTERNAL_PRESENTATION_BYTES
        ):
            raise ValueError("correction presentation reason is not bounded")
