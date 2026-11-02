"""One typed manager request to the EasyCrypt session backend.

``ReplSessionManager`` and ``CompilerSurface`` know which backend call they
issue.  They state it once as a ``BackendRequest``; the command line, the
event-bound authority contract and the read-only classification all come from
that record, so no consumer has to rediscover the call kind from argv.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Literal


BackendKind = Literal[
    "start",
    "commit",
    "commit_chain",
    "undo",
    "try",
    "managed_goal_view",
    "compiler_input",
    "compiler_resource_load",
    "native_semantic_batch",
    "native_state_projection",
]

_MUTATING_KINDS = frozenset({"start", "commit", "commit_chain", "undo"})
_TACTIC_EXECUTION_KINDS = frozenset({"commit", "commit_chain", "undo"})

# Read-only calls whose result is trusted only through one produced event in
# the call's own event window: (backend action name, produced event type).
_AUTHORITATIVE_VIEWS: dict[str, tuple[str, str]] = {
    "managed_goal_view": (
        "managed-goal-view",
        "prover.workspace_view.produced",
    ),
    "compiler_input": ("compiler-input-v2", "compiler.input.produced"),
    "compiler_resource_load": (
        "compiler-resource-load-v2",
        "compiler.resources.loaded",
    ),
    "native_semantic_batch": (
        "native-semantic-batch",
        "native.semantic.batch.produced",
    ),
    "native_state_projection": (
        "native-state-projection",
        "native.state.produced",
    ),
}


@dataclass(frozen=True)
class BackendRequest:
    """One session-CLI call: what it is, its label, and its arguments."""

    kind: BackendKind
    label: str
    args: tuple[str, ...]
    tactic: str = ""

    @classmethod
    def start(
        cls,
        label: str,
        *,
        file_path: str,
        include_dirs: list[str],
        lemma_name: str,
        force_restart: bool,
    ) -> "BackendRequest":
        args = ["-start"]
        if force_restart:
            args.append("--force-restart")
        args.extend(["-f", file_path])
        for include_dir in include_dirs:
            args.extend(["-I", include_dir])
        args.extend(["-lemma", lemma_name])
        return cls("start", label, tuple(args))

    @classmethod
    def commit(cls, label: str, tactic: str) -> "BackendRequest":
        return cls(
            "commit", label, ("-tactic-exec", "commit", "-c", tactic), tactic
        )

    @classmethod
    def commit_chain(cls, label: str, text: str) -> "BackendRequest":
        """A keep-on-fail chain.  The manager issues single commits only;
        the chain contract stays until the text layer owns chain parsing."""

        return cls(
            "commit_chain",
            label,
            ("-tactic-exec", "commit_chain", "--keep-on-fail", "-c", text),
            text,
        )

    @classmethod
    def undo(
        cls,
        label: str,
        *,
        keep_commands: int | None = None,
    ) -> "BackendRequest":
        """Undo the last transaction, or rewind to ``keep_commands`` commands
        with EasyCrypt's ``undo`` (refused without change when impossible)."""
        args: tuple[str, ...] = ("-tactic-exec", "undo")
        if keep_commands is not None:
            if type(keep_commands) is not int or keep_commands < 0:
                raise ValueError("keep_commands must be a non-negative int")
            args = (*args, "--keep-commands", str(keep_commands))
        return cls("undo", label, args)

    @classmethod
    def try_tactic(cls, tactic: str) -> "BackendRequest":
        return cls("try", "exact_tactic_preflight", ("-try", "-c", tactic), tactic)

    @classmethod
    def managed_goal_view(cls) -> "BackendRequest":
        return cls("managed_goal_view", "managed_goal_view", ("-managed-goal-view",))

    @classmethod
    def compiler_input(cls, state_version: int) -> "BackendRequest":
        return cls(
            "compiler_input",
            "compiler_input_v2",
            ("-compiler-input-v2", "--manager-state-version", str(state_version)),
        )

    @classmethod
    def compiler_resource_load(
        cls,
        state_version: int,
        request: dict[str, Any],
    ) -> "BackendRequest":
        return cls(
            "compiler_resource_load",
            "compiler_resource_load_v2",
            (
                "-compiler-resource-load-v2",
                "--manager-state-version",
                str(state_version),
                "--compiler-resource-load-request-json",
                _request_json(request),
            ),
        )

    @classmethod
    def native_semantic_batch(
        cls,
        state_version: int,
        request: dict[str, Any],
    ) -> "BackendRequest":
        return cls(
            "native_semantic_batch",
            "native_semantic_batch",
            (
                "-native-semantic-batch-json",
                "--manager-state-version",
                str(state_version),
                "--native-semantic-batch-request-json",
                _request_json(request),
            ),
        )

    @classmethod
    def native_state_projection(
        cls,
        state_version: int,
        request: dict[str, Any],
    ) -> "BackendRequest":
        return cls(
            "native_state_projection",
            "native_state_projection",
            (
                "-native-state-projection-json",
                "--manager-state-version",
                str(state_version),
                "--native-state-projection-request-json",
                _request_json(request),
            ),
        )

    @property
    def mutates_proof_state(self) -> bool:
        return self.kind in _MUTATING_KINDS

    @property
    def read_only(self) -> bool:
        return not self.mutates_proof_state

    @property
    def requires_tactic_execution_result(self) -> bool:
        """Tactic submissions use the per-tactic execution contract.

        Session start mutates lifecycle state but is not a tactic submission;
        it has its own response contract.
        """

        return self.kind in _TACTIC_EXECUTION_KINDS

    @property
    def requires_tactic_preflight(self) -> bool:
        return self.kind == "try"

    @property
    def authoritative_view(self) -> tuple[str, str] | None:
        """``(backend action name, produced event type)`` for bound views."""

        return _AUTHORITATIVE_VIEWS.get(self.kind)


def _request_json(request: dict[str, Any]) -> str:
    return json.dumps(request, sort_keys=True, separators=(",", ":"))
