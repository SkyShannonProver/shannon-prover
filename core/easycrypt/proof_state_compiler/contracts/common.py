"""Small identities shared by compiler contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from core.easycrypt.proof_state_compiler.contracts.state_ref import StateRef


@dataclass(frozen=True)
class TargetRef:
    source_file: str
    lemma: str

    def __post_init__(self) -> None:
        if not self.source_file or not self.lemma:
            raise ValueError("TargetRef requires source_file and lemma")


@dataclass(frozen=True)
class TransitionRef:
    """The one runtime transition whose result produced the current state."""

    kind: str
    previous_state_ref: Optional[StateRef]
    result_artifact_ref: str

    def __post_init__(self) -> None:
        if self.kind not in {
            "initial",
            "accepted",
            "rejected",
            "undone",
            "replayed",
            "inspected",
        }:
            raise ValueError(f"unsupported transition kind {self.kind!r}")
        if self.kind == "initial" and self.previous_state_ref is not None:
            raise ValueError("initial transition cannot carry previous_state_ref")
        if self.kind != "initial" and self.previous_state_ref is None:
            raise ValueError("non-initial transition requires previous_state_ref")
        if not self.result_artifact_ref:
            raise ValueError("transition result_artifact_ref is required")
