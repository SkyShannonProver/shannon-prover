"""Authoritative EasyCrypt typed-state source contract for compiler P1.

The native companion owns the versioned projection schema. The compiler does
not reconstruct that schema from pretty-printed goals: it receives one frozen,
event-bound projection and lowers it exactly once in the frontend.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.easycrypt.proof_state_compiler.contracts.frozen_json import (
    FrozenJsonObject,
)
from core.easycrypt.proof_state_compiler.contracts.state_ref import (
    ProvenanceRef,
    StateRef,
)


@dataclass(frozen=True)
class NativeProofStateSnapshot:
    """One validated ``native.state.produced`` occurrence.

    ``projection`` stays frozen instead of being re-declared as a second
    Python copy of every EasyCrypt AST constructor. Its transport schema is
    validated at the runtime gateway; P2 alone translates it into stable
    proof-domain IR.
    """

    state_ref: StateRef
    request_id: str
    projection: FrozenJsonObject
    runtime_identity_sha256: str
    companion_identity_sha256: str
    provenance: ProvenanceRef
    elapsed_ms: int

    def __post_init__(self) -> None:
        if not self.request_id:
            raise ValueError("native proof-state snapshot requires request identity")
        for value in (
            self.runtime_identity_sha256,
            self.companion_identity_sha256,
        ):
            if (
                len(value) != 64
                or any(char not in "0123456789abcdef" for char in value)
            ):
                raise ValueError("native proof-state identity is invalid")
        if self.elapsed_ms < 0:
            raise ValueError("native proof-state elapsed time is invalid")
        if not self.provenance.authoritative or (
            self.provenance.authority != "native.state.produced"
        ):
            raise ValueError("native proof state requires event authority")
        if type(self.projection.get("complete")) is not bool:
            raise ValueError("native proof-state projection requires completeness")
        if type(self.projection.get("open_goal_count")) is not int or (
            self.projection.get("open_goal_count", 0) < 1
        ):
            raise ValueError("native proof-state projection requires open goals")
        focused = self.projection.get("focused_goal")
        if not isinstance(focused, FrozenJsonObject):
            raise ValueError("native proof-state projection requires focused goal")

    @property
    def complete(self) -> bool:
        return self.projection["complete"] is True

    @property
    def open_goal_count(self) -> int:
        return int(self.projection["open_goal_count"])

    @property
    def truncation_reasons(self) -> tuple[str, ...]:
        value = self.projection.get("truncation_reasons", ())
        return tuple(str(item) for item in value)
