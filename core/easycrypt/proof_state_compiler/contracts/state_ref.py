"""Authoritative proof-state identity and pass provenance."""

from __future__ import annotations

import re
from dataclasses import dataclass


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class StateRef:
    session_id: str
    state_version: int
    goal_identity: str
    goal_identity_required: bool
    committed_prefix_identity: str

    def __post_init__(self) -> None:
        for name in (
            "session_id",
            "goal_identity",
            "committed_prefix_identity",
        ):
            if type(getattr(self, name)) is not str:
                raise TypeError(f"{name} must be a string")
        missing = [
            name
            for name, value in (
                ("session_id", self.session_id),
                ("committed_prefix_identity", self.committed_prefix_identity),
            )
            if not value
        ]
        if missing:
            raise ValueError("StateRef missing " + ", ".join(missing))
        if type(self.state_version) is not int or self.state_version < 0:
            raise ValueError("state_version must be non-negative")
        if type(self.goal_identity_required) is not bool:
            raise TypeError("goal_identity_required must be a bool")
        if self.goal_identity_required and not self.goal_identity:
            raise ValueError("open StateRef requires goal_identity")
        if not self.goal_identity_required and self.goal_identity:
            raise ValueError("closed StateRef cannot carry goal_identity")

    def identity_payload(self) -> dict[str, object]:
        """Canonical complete state identity for hashes and envelopes."""

        return {
            "session_id": self.session_id,
            "state_version": self.state_version,
            "goal_identity": self.goal_identity,
            "goal_identity_required": self.goal_identity_required,
            "committed_prefix_identity": self.committed_prefix_identity,
        }


@dataclass(frozen=True)
class ProvenanceRef:
    producer: str
    authority: str
    source_sha256: str
    artifact_ref: str
    source_event_id: str
    source_event_sequence: int
    authoritative: bool

    def __post_init__(self) -> None:
        if not self.producer:
            raise ValueError("provenance producer is required")
        if not self.authority:
            raise ValueError("provenance authority is required")
        if not self.artifact_ref:
            raise ValueError("provenance artifact_ref is required")
        if not self.source_event_id:
            raise ValueError("provenance source_event_id is required")
        if (
            type(self.source_event_sequence) is not int
            or self.source_event_sequence < 0
        ):
            raise ValueError("source_event_sequence must be non-negative")
        if not _SHA256_RE.fullmatch(self.source_sha256):
            raise ValueError("source_sha256 must be lowercase SHA-256")
