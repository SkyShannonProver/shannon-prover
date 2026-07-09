"""Hook dispatch contract — backend-neutral.

This module carries the mechanics of the commit-time hook registry:
result type, mutation flags, descriptor types, ABC for stateful
phases, and the dispatcher itself. Nothing here references EasyCrypt
or any specific prover backend.

Each prover backend defines its own commit-context dataclass with
backend-specific fields (active goal text, daemon handle, raw output,
etc.) and registers triggers/phases that consume that context. The
dispatch logic in `run_commit_hooks` is generic over the context type
— it only ever inspects the `HookResult`s the triggers return, never
the context itself.

# Why this lives in `core/hooks/` and not in a backend module

Two reasons:

1. Reuse without copy. The contract types are pure mechanics; pinning
   them in `core/easycrypt/` would force any future backend to either
   copy or import across an unnatural boundary.
2. Forcing function. Locating these here, separate from any backend
   surface, surfaces accidental backend coupling early — anything
   that needs to be in this file must NOT import from
   `core/easycrypt/`. (At time of writing, that property holds.)

The EC-specific pieces (CommitHookContext with its goal-text fields,
SearchHook for `-search`, DaemonHandle for the EC daemon, all
trigger functions and Phase subclasses, the registry instances)
live in `core/easycrypt/session_hooks.py`.

# Type loosening note

`CommitHook.trigger` and `CommitPhase.run` accept `ctx: Any` rather
than `ctx: CommitHookContext`. This is intentional: the dispatch
mechanics are genuinely generic over context, but Python's type
system would require parameterizing every call site to enforce that
without losing information. We leave the typing loose here and rely
on per-backend modules to type their own triggers tightly against
their concrete context dataclass.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Optional


# ─── Hook results ─────────────────────────────────────────────────────────

@dataclass
class HookResult:
    """A single emit from a commit-time hook or phase.

    `text` is the block to append to the display. `layer` controls
    placement under the backend's display reorder scheme (0 = action
    result/top, 5 = lookups/bottom is the EasyCrypt convention; other
    backends can adopt the same or define their own).

    Mutation flags request post-dispatch state changes the caller
    applies AFTER all hooks/phases have run. This lets a hook keep
    its trigger pure (no closure over outer state) while still
    requesting a side effect.
    """
    text: str = ""
    layer: int = 0
    suppress_error: bool = False
    """Request that the caller treat the just-committed tactic as if
    no error occurred (e.g., set `has_new_error = False`). Used by
    hooks that detect "the apparent error is benign" — the EC
    STRICT_WARNING hook is the canonical example."""
    request_rollback: bool = False
    """Request that the caller restore the session to its pre-tactic
    state. The caller is responsible for the actual file/cache
    mutations; the hook only declares the request."""

    schema_version: int = 1
    """Structured diagnostic payload schema version.

    ``text`` remains the compatibility display surface. The fields below are
    optional machine-readable guidance carried into ``diagnostic.emitted`` so
    future agents can inspect hook output without parsing marker text.
    """
    kind: str = ""
    recommendations: list[dict[str, Any]] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)
    notes: list[dict[str, Any]] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)
    debug: dict[str, Any] = field(default_factory=dict)


@dataclass
class MutationFlags:
    """Aggregate of all mutation requests from one dispatch round.

    `run_commit_hooks` OR-folds individual `HookResult.<flag>` values
    into the aggregate; the caller checks the aggregate once rather
    than scanning every result.

    To add a new mutation kind: add a field on both `HookResult` and
    `MutationFlags`, then OR-fold it in `_absorb` inside
    `run_commit_hooks`. Existing hooks are unaffected.
    """
    suppress_error: bool = False
    request_rollback: bool = False


# ─── Hook descriptors ─────────────────────────────────────────────────────

@dataclass
class CommitHook:
    """A commit-time auto-fire hook — single emit, pure function.

    `trigger` is a callable taking the backend's commit-context dataclass
    and returning `Optional[HookResult]`. Untyped here (`Any`) — see the
    module docstring's "Type loosening note" — but each backend's
    triggers should be typed against its own context for IDE support.

    For multi-emit / stateful workflows, use `CommitPhase` instead.
    """
    marker: str
    """Display marker prefix (e.g., '[STRICT_WARNING]'). Used in the
    backend's layer-map to route emits to display layers, and as a
    debugging label."""

    layer: int
    """Default layer assigned to results emitted by this hook. The
    trigger function may override per-call by setting `result.layer`;
    if the trigger leaves `result.layer == 0` (the dataclass default)
    AND this descriptor `layer` is non-zero, dispatch fills it in."""

    description: str
    """Free-form developer-facing description of when this hook
    fires and what it surfaces. Read by `HOOKS.md` and on-screen
    debugging tools."""

    trigger: Callable[[Any], Optional[HookResult]]
    """Pure function: takes the commit-context dataclass, returns
    `Optional[HookResult]`. Returning None means the hook chose not
    to emit (gate failed)."""


class CommitPhase(ABC):
    """A multi-emit, stateful commit-time workflow.

    Phase instances are held by the backend's session object
    (constructed once in `__init__`, passed to `run_commit_hooks` via
    `phases=`). The instance stores its own lazy caches (catalog,
    seen-shape sets, once-per-session flags) as instance attrs —
    these survive across dispatch calls without polluting the session
    class with legacy bookkeeping attrs.

    `run(ctx)` is the only required method; it returns 0+ `HookResult`s.
    A Phase that fans out N inner emits returns up to N entries. Phase
    authors are expected to wrap each inner emit in their own
    `try/except` so a single sub-emit failure doesn't lose the rest.

    Phase instances should be constructed cheaply — defer all
    expensive work (file reads, catalog scans) to first `run()` call.
    """

    @abstractmethod
    def run(self, ctx: Any) -> list[HookResult]:
        """Emit 0+ HookResults. Always called once per commit (the
        gate decision lives inside the Phase, not at registry level).
        """
        ...


# ─── Dispatch ─────────────────────────────────────────────────────────────

def run_commit_hooks(
    ctx: Any,
    hooks: "list[CommitHook] | tuple[CommitHook, ...]" = (),
    phases: "list[CommitPhase] | tuple[CommitPhase, ...]" = (),
) -> tuple[list[HookResult], MutationFlags]:
    """Run all commit-time hooks and phases; return
    `(results, mutations)`.

    Order: hooks first (in `hooks` list order), then phases (in
    `phases` list order). Each phase's emits appear contiguous;
    cross-phase reordering happens later via the backend's display
    layer-map.

    Hooks/phases that raise exceptions are silently skipped
    (best-effort: a buggy hook should not break the commit pipeline).
    For phases this means a single internal failure can lose all
    subsequent results from the SAME phase — phase authors are
    expected to wrap their inner emits in try/except for fine-grained
    recovery.

    Mutation aggregation: `result.suppress_error=True` and
    `result.request_rollback=True` propagate into
    `mutations.suppress_error` / `mutations.request_rollback`
    (OR-fold). The caller applies the aggregate once after dispatch.

    `result.layer == 0` is overwritten with the descriptor's `layer`
    when a non-zero descriptor layer is configured. This lets simple
    hooks declare layer once at the registry entry rather than
    populating it on every HookResult.

    Backends invoke this with their own `hooks` and `phases` lists;
    typically a backend-private list of `CommitHook` plus
    `Session.commit_phases`.
    """
    out: list[HookResult] = []
    mut = MutationFlags()

    def _absorb(result: Optional[HookResult],
                descriptor_layer: int) -> None:
        if not result:
            return
        if result.layer == 0 and descriptor_layer:
            result.layer = descriptor_layer
        out.append(result)
        if result.suppress_error:
            mut.suppress_error = True
        if result.request_rollback:
            mut.request_rollback = True

    for hook in hooks:
        try:
            result = hook.trigger(ctx)
        except Exception:
            continue
        _absorb(result, hook.layer)

    for phase in phases:
        try:
            results = phase.run(ctx)
        except Exception:
            continue
        for result in results or ():
            _absorb(result, 0)  # phases own their layer assignments

    return out, mut
