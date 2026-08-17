"""Typed boundary between P4 candidates and manager-owned verifier checks."""

from __future__ import annotations

from dataclasses import dataclass

from core.easycrypt.proof_state_compiler.contracts.frozen_json import FrozenJsonObject
from core.easycrypt.proof_state_compiler.contracts.state_ref import (
    ProvenanceRef,
    StateRef,
)


@dataclass(frozen=True)
class CertificationRequest:
    """One exact candidate submitted to a declared read-only verifier policy."""

    candidate_id: str
    state_ref: StateRef
    policy: str
    intent: str
    payload: FrozenJsonObject

    def __post_init__(self) -> None:
        if not self.candidate_id or not self.policy or not self.intent:
            raise ValueError("certification request is incomplete")


@dataclass(frozen=True)
class CertificationReuse:
    """Why an older verifier witness is valid for this observation.

    The verifier occurrence itself remains the authority for the checked
    tactic.  A fresh compiler-input occurrence establishes that the current
    observation has the same complete material proof-state fingerprint.  This
    record keeps both sides explicit instead of relabelling an old result as a
    new EasyCrypt check.
    """

    material_state_sha256: str
    origin_state_ref: StateRef
    origin_input_provenance: ProvenanceRef
    current_input_provenance: ProvenanceRef

    def __post_init__(self) -> None:
        if (
            len(self.material_state_sha256) != 64
            or any(
                char not in "0123456789abcdef"
                for char in self.material_state_sha256
            )
        ):
            raise ValueError("certification reuse requires a SHA-256 state key")
        if not self.origin_input_provenance.authoritative:
            raise ValueError("certification origin input must be authoritative")
        if not self.current_input_provenance.authoritative:
            raise ValueError("certification current input must be authoritative")


@dataclass(frozen=True)
class CertificationResult:
    candidate_id: str
    state_ref: StateRef
    policy: str
    intent: str
    payload_sha256: str
    accepted: bool
    verification_ref: str
    checked_effect: FrozenJsonObject
    reuse: CertificationReuse | None = None

    def __post_init__(self) -> None:
        if (
            not self.candidate_id
            or not self.policy
            or not self.intent
            or len(self.payload_sha256) != 64
            or any(
                char not in "0123456789abcdef" for char in self.payload_sha256
            )
            or not self.verification_ref
        ):
            raise ValueError("certification result is incomplete")
        if self.reuse is not None:
            origin = self.reuse.origin_state_ref
            current = self.state_ref
            if (
                origin.session_id != current.session_id
                or origin.goal_identity != current.goal_identity
                or origin.goal_identity_required
                != current.goal_identity_required
                or origin.committed_prefix_identity
                != current.committed_prefix_identity
            ):
                raise ValueError(
                    "reused certification crosses material state identity"
                )
