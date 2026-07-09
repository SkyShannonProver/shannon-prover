"""Backend-neutral hook dispatch contract.

The types in this package are designed to be reused across prover
backends. Phase 3c built them up inside `core/easycrypt/session_hooks.py`
where they were ALREADY structurally generic — Phase 4 lifted them out
so the genericity is explicit and a second backend can plug in by
defining its own context dataclass + trigger functions, without copying
or re-implementing the dispatch logic.

Public API (re-exported from `core/hooks/contract.py`):

* `HookResult`       — single emit's text + layer + mutation flags
* `MutationFlags`    — aggregate of all mutation requests in a dispatch
* `CommitHook`       — descriptor for stateless single-emit hooks
* `CommitPhase`      — abstract base for stateful multi-emit workflows
* `run_commit_hooks` — dispatch entry point
"""
from .contract import (
    CommitHook,
    CommitPhase,
    HookResult,
    MutationFlags,
    run_commit_hooks,
)

__all__ = [
    "CommitHook",
    "CommitPhase",
    "HookResult",
    "MutationFlags",
    "run_commit_hooks",
]
