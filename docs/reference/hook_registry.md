# Session Hook Registry

This document is the canonical reference for how `session_cli.py` emits
`[MARKER]` blocks during the commit pipeline (`-next` / `-chain`) and the
`-search` handler. If you need to add a new diagnostic block, change
where existing blocks land in the layer ordering, or debug "why didn't
hook X fire?", start here.

## Quick architectural picture

```
append_block (in session_cli.py)
    ┌─ pre-checks (META_COMMAND_REFUSED gate, daemon path)
    ├─ goal-state diff (compute prev_count, curr_count, no_more, …)
    ├─ build CommitHookContext
    │
    ├─ run_commit_hooks(ctx, self.commit_phases)  ◀──┐
    │     ├─ CommitHook list (single emit, pure)     │  registered in
    │     └─ CommitPhase list (multi emit, stateful) │  session_hooks.py
    │   returns (list[HookResult], MutationFlags) ───┘
    │
    ├─ apply mutations:
    │     mut.suppress_error    → has_new_error = False  (STRICT_WARNING)
    │     mut.request_rollback  → _apply_no_progress_rollback()
    │
    ├─ inline classifier (CLASS:…) — helper called from 4 paths
    │
    └─ terminal display (State: / Delta: + snippet)

-search handler
    ├─ build SearchHookContext
    └─ run_search_hooks(ctx) → list[str]
```

`session_hooks.py` is the canonical home for all hook implementations.
The contract types (`HookResult`, `MutationFlags`, `CommitHook`,
`CommitPhase`) are intentionally backend-agnostic so they can be
reused if a non-EasyCrypt backend is added later.

## When to add a hook (decision tree)

```
Need to surface a [MARKER] block during -next / -chain?
│
├─ Single emit + no internal cache?
│  └─ CommitHook (function returning Optional[HookResult])
│     Examples: GOAL_CLOSED, STRICT_WARNING, AUTO-KB
│
├─ Multi-emit OR needs cross-call cache OR shape-key dedup?
│  └─ CommitPhase (subclass with run() returning list[HookResult])
│     Examples: AutoSigPhase (per-name dedup),
│               AutoDiffPhase (alignment-shape dedup),
│               PivotStrategyPhase (shape gate + lazy catalog + 6 nested emits)
│
├─ Need to mutate session state (e.g. suppress an error, roll back)?
│  └─ Set HookResult.suppress_error / .request_rollback
│     Caller in append_block applies aggregate after dispatch.
│     If you need a NEW kind of mutation: add a field to HookResult
│     and a matching field on MutationFlags; OR-fold in run_commit_hooks.
│
└─ Pre-commit gate (don't even let the tactic reach the daemon)?
   └─ Inline guard at the top of append_block (like META_COMMAND_REFUSED).
      Not a hook — different lifecycle.
```

For `-search`, use `SearchHook` (much simpler — no layers, no mutations).

## Adding a new hook — checklist

1. **Decide kind**: CommitHook (pure) or CommitPhase (stateful)?
2. **Implement** in `core/easycrypt/session_hooks.py`:
   - Functions return `Optional[HookResult]` (None when gate fails).
   - Phase subclasses construct cheaply (defer expensive work to first
     `run()` call); store lazy state as instance attrs.
3. **Register**:
   - CommitHook: append to `_COMMIT_HOOKS` with marker, layer, description.
   - CommitPhase: instantiate in `Session.__init__` and append to
     `self.commit_phases`. Order matters when phases share scratch
     (PivotStrategyPhase writes `scratch["pivot.call_ready_names"]`
     which AutoDiffPhase reads — pivot MUST run first).
4. **Layer map**: if the marker is new, add a prefix entry to
   `_DISPLAY_LAYER_MAP` in session_cli.py. Earlier prefixes win
   substring matching, so `[AUTO-PIVOT-CALL-READY]` (L2) must
   precede `[AUTO-PIVOT]` (L3).
5. **Test**: add a case to `tests/test_session_hooks_phase3c.py`
   (or `test_hook_contract_v2.py` if exercising the contract itself).
   Build a `CommitHookContext` directly; no EC daemon required for
   unit tests.

## Currently registered hooks

The list below mirrors `_COMMIT_HOOKS`, `Session.commit_phases`,
`_SEARCH_HOOKS_POST` in `session_hooks.py`. The truth source is the code;
update both together.

### Commit-time, single-emit (`CommitHook`)

| Marker | Layer | Mutation | Trigger function |
|---|---|---|---|
| `[POST-CALL-INV-HINT]` | L0 | — | `post_call_inv_trigger` |
| `[GOAL_CLOSED]` | L0 | — | `goal_closed_trigger` |
| `[ALL_GOALS_CLOSED]` | L0 | — | `all_goals_closed_trigger` |
| `[GOAL-TOO-LARGE]` | L0 | — | `goal_too_large_trigger` |
| `[TACTIC_NO_EFFECT_AUTO_REVERTED]` | L0 | `request_rollback` | `tactic_no_effect_trigger` |
| `[STRICT_WARNING]` | L0 | `suppress_error` | `strict_warning_trigger` |
| `[goal: <type>]` | L1 | — | `goal_header_trigger` |
| `[STATE-DIFF]` | L0 | — (writes commit_meta.log) | `state_diff_trigger` |
| `[DAEMON_REJECTED]` | L0 | — | `daemon_rejected_trigger` |
| `[AUTO-NOPROG-HINT]` | L0 | — | `auto_noprog_hint_trigger` |
| `[AUTO-KB]` | L4 | — | `auto_kb_trigger` |

### Commit-time, multi-emit (`CommitPhase`)

| Phase | Inner emits | Layers | Internal state |
|---|---|---|---|
| `AutoSigPhase` | `[AUTO-SIG]` (deduped by name) | L0 | `_seen_names: set[str]` |
| `AutoDiffPhase` | `[AUTO-DIFF]` (deduped by alignment shape) | L3 | `_seen_alignment_shapes: set[str]`. Reads `ctx.scratch["pivot.call_ready_names"]` for ✓/⚠ tagging. |
| `PivotStrategyPhase` | `[AUTO-PIVOT]` / `[AUTO-PIVOT-VERIFIED]`, `[AUTO-PIVOT-CALL-READY]`, `[AUTO-BRIDGE-SUGGEST/VERIFIED]`, `[AUTO-CALL-SUGGEST]`, `[AUTO-REWRITE-PROBE]`, `[AUTO-SELF-HINTS]` | L2 / L3 / L4 | `_catalog`, `_target_lemma`, `_seen_shapes`, `_self_hints_shown`. Writes `ctx.scratch["pivot.call_ready_names"]` for AutoDiffPhase. |

### Search-time (`SearchHook`)

| Marker | Trigger function |
|---|---|
| `[SEARCH-QUERY-AUTOFIX]` | `search_query_autofix_trigger` |
| `[SEARCH-FALLBACK-HINT]` | `search_fallback_trigger` |

## Layer ordering precedence (`_DISPLAY_LAYER_MAP`)

Defined near the bottom of `session_cli.py`. `_classify_emit_chunk`
returns the layer of the FIRST marker that appears in the chunk
(substring match, in the declaration order of `_DISPLAY_LAYER_MAP`).

```
L0  action result + verdicts:
    [DAEMON_REJECTED], [POST-CALL-INV-HINT], [STATE-DIFF],
    [GOAL_CLOSED], [ALL_GOALS_CLOSED],
    [TACTIC_NO_EFFECT_AUTO_REVERTED], [GOAL-TOO-LARGE],
    [AUTO-NOPROG-HINT], [AUTO-SIG], [CLASS:, [STRICT_WARNING]
L1  current goal state:
    State:, Delta:, [goal:
L2  ready-to-act, daemon-verified:
    [AUTO-PIVOT-CALL-READY], [AUTO-PIVOT-VERIFIED],
    [AUTO-BRIDGE-SUGGEST, [AUTO-REWRITE-PROBE]
L3  strategy hints:
    [AUTO-DIFF], [AUTO-PIVOT], [AUTO-CALL-SUGGEST]
L4  KB / catalog lookups:
    [AUTO-KB], [KB], [KB-IDIOM, [KB-RECIPE,
    [goal-patterns], [AUTO-LEMMA-HINTS], [AUTO-SELF-HINTS]
L5  cross-references:
    [AUTO-RESOLVED-NAMES], [WHERE-HIT]
```

A chunk containing both `[AUTO-PIVOT]` and `[AUTO-PIVOT-CALL-READY]`
is classified by FIRST-marker position, so put longer prefixes
(`[AUTO-PIVOT-CALL-READY]` → L2) BEFORE shorter ones
(`[AUTO-PIVOT]` → L3) in the map. Same trick for
`[AUTO-PIVOT-VERIFIED]` vs `[AUTO-PIVOT]`.

## Persistence files (`<session_dir>/`)

Hook state that needs to survive a process restart goes to a file
under the session directory. Convention: filename is the hook's
state purpose, not its marker.

| File | Owner | Content |
|---|---|---|
| `post_call_inv_count.txt` | `post_call_inv_trigger` | One non-negative integer; deleted on hint fire (one-shot) |
| `search_no_hit_count.txt` | `search_fallback_trigger` | Consecutive 0-hit search counter; reset on hit |
| `commit_meta.log` | `state_diff_trigger` (write); `Session._recent_lemma_names` (read) | One `verdict\|delta\|tactic` line per commit; cross-subgoal-transition detector source |

Phase instance attributes survive within a single process (Session
lifetime) but reset when the CLI exits. Anything that needs to
persist across CLI invocations must use a file.

## Cross-Phase coordination (`ctx.scratch`)

`CommitHookContext.scratch: dict` is per-commit (fresh per
`CommitHookContext` instance, no leakage to next commit). Use it when
one Phase produces data another Phase needs:

```python
class WriterPhase(CommitPhase):
    def run(self, ctx):
        ctx.scratch["my_namespace.value"] = ...  # use namespaced keys
        return [HookResult(...)]

class ReaderPhase(CommitPhase):
    def run(self, ctx):
        v = ctx.scratch.get("my_namespace.value")  # may be None if writer
                                                    # didn't run / its gate
                                                    # was suppressed
        ...
```

**Currently used keys**:
- `pivot.call_ready_names: set[str]` — written by `PivotStrategyPhase`
  (CALL-READY probe results), read by `AutoDiffPhase` (✓/⚠ tagging
  on `→ \`call NAME\`` lines).

When you add a new scratch key, prefix it with the writer's name
(`pivot.X`, `auto_diff.X`) and document it here.

## What stays inline (intentional)

Three things in `append_block` are NOT hooks and shouldn't be:

* **`[CLASS:...]`** — the error classifier helper
  (`_classify_and_format`) is called from 4 paths: commit pipeline,
  `-try` single, `-try` chain, `-chain`. Migrating to a hook would
  scatter the wrapper across those 4 sites with negative net code
  reduction. The helper itself is pure; the 4 callers are tiny
  (3-5 lines each) and call-site-specific.

* **`[META_COMMAND_REFUSED]`** — this is a pre-commit gate that
  returns directly from `append_block`, bypassing the entire commit
  pipeline. It has different lifecycle from post-commit hooks (which
  emit AFTER the commit attempt). Adding a `PreCommitGate` abstraction
  for one 5-line check would be over-engineering.

* **`State:` / `Delta:` + snippet** — the terminal display. Not a
  diagnostic block; not a hook.

## Debugging — "why didn't X fire?"

1. **Layer reorder** may have moved it; search the full output for
   the marker rather than assuming top-of-output ordering.
2. **Phase instance dedup**: AutoSigPhase's `_seen_names`,
   AutoDiffPhase's `_seen_alignment_shapes`, PivotStrategyPhase's
   `_seen_shapes` / `_self_hints_shown`. Restart the session (drop
   `.ec_session*/`) to clear.
3. **Per-session-dir file state**: `post_call_inv_count.txt`,
   `search_no_hit_count.txt`, `commit_meta.log`. Delete to reset.
4. **Daemon gating**: `ctx.daemon()` returns None when the daemon is
   disabled (`EC_DAEMON_DISABLE=1`), missing meta, sync failure, or
   chain mode. Hooks gated on `if h := ctx.daemon():` won't fire
   without a daemon.
5. **Chain mode** (`ctx.chain_skip_verify=True`) skips daemon-verified
   blocks (CALL-READY, VERIFIED, BRIDGE-SUGGEST, REWRITE-PROBE,
   CALL-SUGGEST). Verify on `-next` instead of `-chain`.
6. **Goal-shape gate failed**: AutoDiffPhase wants
   pRHL/equiv/probability/eager classification; AUTO-BRIDGE-SUGGEST
   wants 2-3 Pr terms with `=`/`<=`; AUTO-CALL-SUGGEST wants `&1` AND
   `&2` (or ` ~ ` AND `==>`); AUTO-KB wants structural-tactic match.
7. **Context-side gate failed**: `narrative.json` missing required
   role (`bridge_lemma`, `oracle_equiv`); `_pivot_catalog` empty
   (context.ec yielded no pivot-shape lemmas).

## See also

- `core/easycrypt/session_hooks.py` — the canonical source. The
  module docstring at the top has more detail on the contract design
  decisions; per-hook docstrings cover the gate semantics.
- `tests/test_hook_contract_v2.py` — exercises the contract types
  (HookResult, MutationFlags, CommitPhase, ctx.daemon, ctx.scratch).
- `tests/test_session_hooks_phase3c.py` — exercises the registered
  triggers and Phase classes.
- `CLAUDE.md` — top-level managed prover guidance and the backend/session
  boundary for prover behavior.
