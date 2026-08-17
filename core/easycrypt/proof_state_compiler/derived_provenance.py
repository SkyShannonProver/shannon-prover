"""Create pass provenance while preserving the authoritative source event."""

from __future__ import annotations

from core.easycrypt.proof_state_compiler.contracts.frozen_json import (
    freeze_json_object,
    frozen_json_sha256,
)
from core.easycrypt.proof_state_compiler.contracts.state_ref import (
    ProvenanceRef,
    StateRef,
)


def derived_provenance(
    producer: str,
    state_ref: StateRef,
    upstream: ProvenanceRef,
) -> ProvenanceRef:
    state_identity = (
        state_ref.goal_identity
        if state_ref.goal_identity_required
        else f"closed-{state_ref.state_version}"
    )
    source = freeze_json_object(
        {
            "goal_identity": state_ref.goal_identity,
            "producer": producer,
            "upstream_sha256": upstream.source_sha256,
        }
    )
    return ProvenanceRef(
        producer=producer,
        authority="compiler_derivation",
        source_sha256=frozen_json_sha256(source),
        artifact_ref=f"compiler://{producer}/{state_identity}",
        source_event_id=upstream.source_event_id,
        source_event_sequence=upstream.source_event_sequence,
        authoritative=False,
    )
