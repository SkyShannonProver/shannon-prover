"""Project one already-authoritative backend snapshot into immutable P1."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from core.easycrypt.proof_state_compiler.contracts.common import TargetRef, TransitionRef
from core.easycrypt.proof_state_compiler.contracts.native_state import (
    NativeProofStateSnapshot,
)
from core.easycrypt.proof_state_compiler.contracts.projected_state import ProjectedProofState
from core.easycrypt.proof_state_compiler.contracts.state_ref import ProvenanceRef, StateRef


@dataclass(frozen=True)
class RuntimeSnapshotInput:
    """Event-bound runtime state before native typed-state enrichment."""

    state_ref: StateRef
    provenance: ProvenanceRef
    target: TargetRef
    transition: TransitionRef
    goal_lines: Sequence[str]
    goal_count: int
    goal_count_known: bool
    closed: bool

    def __post_init__(self) -> None:
        if not self.provenance.authoritative:
            raise ValueError("P1 input provenance must be authoritative")


@dataclass(frozen=True)
class AuthoritativeSnapshotInput(RuntimeSnapshotInput):
    """Compiler-ready P1 input after native state authority is joined."""

    native_state: NativeProofStateSnapshot | None = None

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.closed:
            if self.native_state is not None:
                raise ValueError("closed input cannot carry native open state")
        elif self.native_state is None:
            raise ValueError("open P1 input requires native typed state")
        elif self.native_state.state_ref != self.state_ref:
            raise ValueError("P1 native typed state belongs to another StateRef")


def project_authoritative_state(
    snapshot: AuthoritativeSnapshotInput,
) -> ProjectedProofState:
    """Copy validated runtime facts; never parse, search, or infer liveness."""

    if isinstance(snapshot.goal_lines, (str, bytes)):
        raise TypeError("goal_lines must be a sequence of exact lines")
    lines = tuple(snapshot.goal_lines)
    if not all(isinstance(line, str) for line in lines):
        raise TypeError("goal_lines entries must be strings")
    return ProjectedProofState(
        state_ref=snapshot.state_ref,
        provenance=snapshot.provenance,
        target=snapshot.target,
        transition=snapshot.transition,
        goal_lines=lines,
        goal_count=snapshot.goal_count,
        goal_count_known=snapshot.goal_count_known,
        closed=snapshot.closed,
        native_state=snapshot.native_state,
    )
