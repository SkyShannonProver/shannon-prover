"""Feature-local typed result for an old accepted contract conjunct loss."""

from __future__ import annotations

from dataclasses import dataclass

from core.easycrypt.proof_state_compiler.contracts import EvidenceRef


@dataclass(frozen=True)
class AcceptedContractRetention:
    anchor_id: str
    anchor_source_event_id: str
    anchor_prefix_identity: str
    current_prefix_identity: str
    boundary_identity: str
    original_conjuncts: tuple[str, ...]
    missing_conjuncts: tuple[str, ...]
    evidence_refs: tuple[EvidenceRef, ...]

    def __post_init__(self) -> None:
        if not all((
            self.anchor_id,
            self.anchor_source_event_id,
            self.anchor_prefix_identity,
            self.current_prefix_identity,
            self.boundary_identity,
        )):
            raise ValueError("retention result requires exact anchor and boundary")
        if (
            not self.original_conjuncts
            or len(self.original_conjuncts) != len(set(self.original_conjuncts))
        ):
            raise ValueError("accepted contract conjuncts must be nonempty and unique")
        if not self.missing_conjuncts:
            raise ValueError("missing-conjunct result must abstain when all preserved")
        if self.anchor_prefix_identity != self.current_prefix_identity:
            raise ValueError("accepted contract anchor is stale for current prefix")
        if len(self.missing_conjuncts) != len(set(self.missing_conjuncts)):
            raise ValueError("missing conjuncts must be unique")
        unknown = set(self.missing_conjuncts) - set(self.original_conjuncts)
        if unknown:
            raise ValueError("missing conjunct was not present in accepted contract")
        if not self.evidence_refs:
            raise ValueError("retention result requires current and anchor evidence")
