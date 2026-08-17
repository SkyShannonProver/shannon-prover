"""Feature-local typed result for current program-operation readiness."""

from __future__ import annotations

from dataclasses import dataclass

from core.easycrypt.proof_state_compiler.contracts import EvidenceRef


@dataclass(frozen=True)
class ProgramOperationReadiness:
    operation: str
    status: str
    tactic_active_boundary: str
    blocker: str = ""
    evidence_refs: tuple[EvidenceRef, ...] = ()

    def __post_init__(self) -> None:
        if self.operation not in {"call", "rnd", "while"}:
            raise ValueError("readiness supports only call/rnd/while")
        if self.status not in {"legal", "blocked"}:
            raise ValueError("readiness status must be legal or blocked")
        if not self.tactic_active_boundary or not self.evidence_refs:
            raise ValueError("readiness requires an exact boundary and evidence")
        if self.status == "blocked" and not self.blocker:
            raise ValueError("blocked readiness requires an exact blocker")
        if self.status == "legal" and self.blocker:
            raise ValueError("legal readiness cannot carry a blocker")
