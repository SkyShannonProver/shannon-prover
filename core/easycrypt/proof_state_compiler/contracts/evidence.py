"""Fine-grained provenance for individual P2-P4 facts."""

from __future__ import annotations

import re
from dataclasses import dataclass


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class EvidenceRef:
    evidence_id: str
    source_kind: str
    source_ref: str
    source_sha256: str

    def __post_init__(self) -> None:
        if not self.evidence_id or not self.source_kind or not self.source_ref:
            raise ValueError(
                "EvidenceRef requires evidence_id, source_kind, and source_ref"
            )
        if not _SHA256_RE.fullmatch(self.source_sha256):
            raise ValueError("EvidenceRef source_sha256 must be lowercase SHA-256")
