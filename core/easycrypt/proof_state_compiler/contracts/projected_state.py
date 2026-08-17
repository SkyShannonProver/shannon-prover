"""P1 output: exact authoritative state projection."""

from __future__ import annotations

from dataclasses import dataclass

from core.easycrypt.proof_state_compiler.contracts.common import (
    TargetRef,
    TransitionRef,
)
from core.easycrypt.proof_state_compiler.contracts.native_state import (
    NativeProofStateSnapshot,
)
from core.easycrypt.proof_state_compiler.contracts.state_ref import (
    ProvenanceRef,
    StateRef,
)


@dataclass(frozen=True)
class ProjectedProofState:
    """Exact visible state only; no classification or liveness claims."""

    state_ref: StateRef
    provenance: ProvenanceRef
    target: TargetRef
    transition: TransitionRef
    goal_lines: tuple[str, ...]
    goal_count: int
    goal_count_known: bool
    closed: bool
    native_state: NativeProofStateSnapshot | None

    def __post_init__(self) -> None:
        if self.goal_count < 0:
            raise ValueError("goal_count must be non-negative")
        if self.closed:
            if self.state_ref.goal_identity_required:
                raise ValueError("closed state cannot require a goal identity")
            if self.goal_lines:
                raise ValueError("closed state cannot carry active goal lines")
            if self.goal_count_known and self.goal_count != 0:
                raise ValueError("closed state must have zero known goals")
            if self.native_state is not None:
                raise ValueError("closed state cannot carry an open native state")
        else:
            if not self.state_ref.goal_identity_required:
                raise ValueError("open state requires a goal identity")
            if not self.goal_lines:
                raise ValueError("open state requires exact goal_lines")
            if self.native_state is None:
                raise ValueError("open state requires native typed state")
            if self.native_state.state_ref != self.state_ref:
                raise ValueError("native typed state belongs to another StateRef")
            if self.goal_count_known and (
                self.native_state.open_goal_count != self.goal_count
            ):
                raise ValueError("native and runtime goal counts disagree")
        previous = self.transition.previous_state_ref
        if self.transition.kind in {"rejected", "inspected"}:
            if previous != self.state_ref:
                raise ValueError("non-mutating transition must retain StateRef")
        if self.transition.kind in {"accepted", "undone", "replayed"}:
            if previous == self.state_ref:
                raise ValueError("state-changing transition must change StateRef")
