"""Auto-fire hook registry for session_cli.

Originally Phase 0 of the cleanup proposed in HOOKS.md / 2026-04-30
audit. The full session_cli.py emits 27+ `[MARKER]` blocks via auto-fire
hooks that are currently inline in `append_block` (~500 lines) and the
`-search` handler. This module is the canonical home; hooks migrate
over time.

# Contract — v2 (Phase 3c)

Phase 0 used a thin `Optional[str]` return type. v2 adds:

* `HookResult` — explicit text + layer + mutation flags. A single hook
  emit may now request `has_new_error = False` (STRICT_WARNING) or
  request a rollback (future TACTIC_NO_EFFECT). Mutations are OR-folded
  by `run_commit_hooks` and applied once by the caller.

* `CommitPhase` — abstract base class for **multi-emit, stateful**
  workflows. The AUTO-PIVOT family is one Phase: it shares `_catalog`,
  `_seen_shapes`, `_target_lemma_name` across 6 inner emit blocks
  (AUTO-PIVOT, AUTO-PIVOT-CALL-READY, AUTO-DIFF annotated, AUTO-BRIDGE-
  SUGGEST, AUTO-CALL-SUGGEST, AUTO-REWRITE-PROBE, AUTO-SELF-HINTS) all
  gated by one shape-key. Forcing this into 6 stateless hooks would
  duplicate the catalog scan and the shape gate every call. Phase
  instances are held by `Session` (constructed once in `__init__`)
  so internal lazy caches survive across `append_block` calls.

* `CommitHookContext.daemon()` — lazy daemon accessor. Setup is
  potentially expensive (sync_to replays the history), so we don't run
  it unless a hook needs it. The first call to `ctx.daemon()` runs the
  setup callable and caches; subsequent calls reuse the cached value.

* `CommitHookContext.scratch` — a dict for cross-hook coordination
  within a single commit. Replaces the latent stale-state bug where
  AUTO-DIFF set `Session._pending_auto_diff` (cross-commit) but
  AUTO-PIVOT-CALL-READY only consumed it inside its own shape gate.
  scratch is per-`CommitHookContext` (per-commit), so stale state
  from a prior commit can't leak.

# Two hook flavors

```
                      simple, pure         multi-emit, stateful
                      ─────────────        ────────────────────
   declared as        @dataclass           class : CommitPhase
   identity           function             instance owned by Session
   gate logic         inside trigger       inside run() (often
                                           outer shape-key gate)
   internal cache     none                 instance attrs
   typical example    POST-CALL-INV-HINT   PivotStrategyPhase
                      GOAL_CLOSED          (AUTO-PIVOT family)
                      GOAL-TOO-LARGE
```

# Adding a new hook

1. Pure single emit? → add a `CommitHook` to `_COMMIT_HOOKS`.
2. Multi-emit / stateful? → subclass `CommitPhase`, instantiate in
   `Session.__init__`, append to `self.commit_phases`.
3. Either way: trigger function returns `Optional[HookResult]` (or
   `list[HookResult]` for Phase). Set `result.suppress_error = True`
   to request `has_new_error = False` post-dispatch.
4. Add unit tests under `tests/test_session_hooks*.py` (no EC daemon
   needed; build `CommitHookContext` directly).

# Hook bookkeeping

The `[POST-CALL-INV-HINT]`, `[GOAL_CLOSED]`, `[ALL_GOALS_CLOSED]`,
`[GOAL-TOO-LARGE]` hooks live as `CommitHook` entries below.
`[SEARCH-QUERY-AUTOFIX]` and `[SEARCH-FALLBACK-HINT]` live as
`SearchHook` entries (separate registry, simpler contract since
`-search` doesn't have layers or mutations).

Stateful phase implementations live in `session_hook_phases.py` and are
re-exported here for compatibility. Remaining inline logic in
`session_runtime.py` is limited to commit orchestration and display assembly.
See HOOKS.md for the historical inventory.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from core.easycrypt.session_goal_context import (  # type: ignore
    is_goal_too_large,
    too_large_warning_block,
)


# ─── Daemon handle ───────────────────────────────────────────────────────

@dataclass
class DaemonHandle:
    """A pair (cli, dbe) sufficient to issue speculative tactics.

    `cli` is the JSON-RPC client; `dbe` is the `DaemonBackend` instance
    holding `_session_id`. Hooks that need to probe a tactic do
    `h = ctx.daemon(); if h: h.cli.try_tactic(h.dbe._session_id, tac)`.
    """
    cli: Any
    dbe: Any


# ─── Contexts ────────────────────────────────────────────────────────────

@dataclass
class CommitHookContext:
    """Inputs available to a commit-pipeline hook (`append_block`).

    Captures the tactic just submitted plus the goal-count delta; everything
    else a hook needs (e.g., access to history/curr files) is reachable via
    `session_dir` paths.

    Optional fields (default-Nullable) carry information that not every hook
    needs and is only computed by `append_block` when relevant. A hook that
    requires one of them should bail out (`return None`) when it's missing
    rather than raise.
    """
    session_dir: Path
    trimmed: str
    has_new_error: bool
    no_progress: bool
    prev_count: int
    curr_count: int
    # ─── Phase 3c additions ───
    no_more: bool = False
    """`last_section` contained "No more goals" — proof structurally closed."""
    async_check_close: bool = False
    """Block ended with `qed.` and EC went into [N|check]> async-check mode
    (no goal text after the qed). Treat as proof-closed."""
    active_goal: str = ""
    """The active goal block text (highest check-number). Used by hooks that
    inspect goal size or content."""
    raw_curr: str = ""
    """Full curr.out text (post-commit). Used by hooks that need to inspect
    new error lines (STRICT_WARNING) or goal output structure."""
    raw_prev: str = ""
    """Full prev.out text (pre-commit). Paired with `raw_curr` for delta
    inspection (e.g., AUTO-NOPROG-HINT compares hypothesis structure)."""
    daemon_rejection_error: str = ""
    """The daemon's EC error text, threaded in from the EC commit result's
    ``rejection_error``. Non-empty when the daemon rejected the tactic
    (parse error, unknown lemma, etc.). Drives [DAEMON_REJECTED]."""
    # ─── Cross-hook coordination ───
    scratch: dict = field(default_factory=dict)
    """Per-commit shared dict for Phase coordination. Replaces the legacy
    `Session._pending_auto_diff` cross-commit attribute (which had a
    latent stale-state bug). scratch is fresh per `CommitHookContext`,
    so a Phase that writes here cannot leak state into the next commit.
    Convention: keys are namespaced by writer (`pivot.call_ready_names`,
    `auto_diff.pending_text`)."""
    # ─── Daemon (lazy) ───
    _daemon_setup: Optional[Callable[[], Optional[DaemonHandle]]] = None
    _daemon_resolved: bool = False
    _daemon_value: Optional[DaemonHandle] = None
    chain_skip_verify: bool = False
    """When True, hooks should NOT call out to the daemon. Folded into
    `_daemon_setup` upstream (it returns None when this flag is set), so
    most hooks just check `if ctx.daemon() is None: return None`. The flag
    is exposed here for hooks that want to surface a different message
    in chain mode vs daemon-unavailable."""

    def daemon(self) -> Optional[DaemonHandle]:
        """Lazy + cached daemon access. The first hook to call this
        triggers `_daemon_setup()` (potentially expensive — runs
        history replay via `_sync_to`); subsequent calls reuse the
        cached value. Returns None when the daemon is unavailable
        (disabled, missing meta, sync failure, or chain-skip mode).
        """
        if not self._daemon_resolved:
            self._daemon_value = (
                self._daemon_setup() if self._daemon_setup else None
            )
            self._daemon_resolved = True
        return self._daemon_value


@dataclass
class SearchHookContext:
    """Inputs available to a search-handler hook (`-search`).

    `raw_query` is what the agent typed (post-shell de-quoting);
    `effective_query` is what was passed to `search_lemmas` after
    transformation (e.g., BRE→ERE autofix). `output` is the search
    result text.
    """
    session_dir: Path
    raw_query: str
    effective_query: str
    output: str
    was_autofixed: bool


# ─── Backend-neutral contract ────────────────────────────────────────────

# The contract types (HookResult, MutationFlags, CommitHook,
# CommitPhase, run_commit_hooks dispatch) live in `core/hooks/`. This
# module re-uses them as-is — the backend-specific surface in
# `core/easycrypt/` is just trigger functions, Phase subclasses,
# CommitHookContext (with EC-specific fields), and the registry
# instances.
#
# Re-exporting here keeps backwards-compatible imports working:
# downstream code that does `from session_hooks import HookResult`
# still functions. New code should import from `hooks` directly:
# `from hooks.contract import HookResult`.
from core.hooks.contract import (  # type: ignore
    CommitHook,
    CommitPhase,
    HookResult,
    MutationFlags,
    run_commit_hooks as _run_commit_hooks_base,
)


# ─── EC-specific search hook descriptor ──────────────────────────────────

@dataclass
class SearchHook:
    """A `-search`-handler auto-fire hook. No layer (emitted in
    registry order, before the search result body) and no mutations
    (the search command never feeds back into commit state). Trigger
    returns the block text directly — Optional[str] is fine here
    because there's no display layer to track."""
    marker: str
    description: str
    trigger: Callable[[SearchHookContext], Optional[str]]


# ─── [POST-CALL-INV-HINT] ────────────────────────────────────────────────

_POST_CALL_INV_RE = re.compile(r"^\s*call\s*\(\s*_\s*:", re.IGNORECASE)
_POST_CALL_INV_HINT_TEXT = (
    "[POST-CALL-INV-HINT] You're 3 commits past a "
    "`call (_: Inv)` and no fan-out subgoal has closed.\n"
    "  This is the symptom that the invariant is "
    "forcing you to re-prove an operator-vs-procedural "
    "bridge that `smt`/`auto` can't see. Consider "
    "rolling back and:\n"
    "  (1) `call <NAMED_EQUIV>` (Form 1) if a "
    "sibling equiv lemma matches the call-site "
    "procedure pair — inspect `lemma_index` or "
    "`equiv_bridge_lemmas`, then `lookup_symbol` for the "
    "exact declaration before calling it.\n"
    "  (2) `transitivity M_mid.proc (PRE_LM ==> "
    "POST_LM) (PRE_MR ==> POST_MR).` to bridge "
    "through an intermediate game where ONE leg is "
    "a named equiv. (Run `-tactic-forms transitivity` "
    "for the exact two-pair form.)\n"
    "  See CLAUDE.md section \"Before `call (_: Inv)`: "
    "consider the cheaper alternatives\" for the "
    "full checklist.\n"
)


def post_call_inv_trigger(ctx: CommitHookContext) -> Optional[HookResult]:
    """State-machine for the post-`call (_: Inv)` flailing tracker.

    State persists in `<session_dir>/post_call_inv_count.txt` (a single
    non-negative integer or absent). Transitions:

    - Tactic matching `^\\s*call\\s*\\(\\s*_\\s*:` committed successfully
      (no_progress=False, has_new_error=False) → write file = "0"
      (start tracking; agent just committed a hand-craft-invariant call).
    - File exists and tactic CLOSED a subgoal (curr_count < prev_count) →
      file = "0" (agent is making progress on the fan-out; reset).
    - File exists and tactic errored or made no progress → increment count;
      if it would reach 3, emit hint and DELETE file (one-shot).
    - File exists and tactic was neutral (no error, no progress, no subgoal
      closed) → leave count unchanged.
    - File doesn't exist and tactic isn't a new `call (_: Inv)` → no-op.

    Returns a HookResult with the hint when threshold crossed, else None.
    """
    post_call_path = ctx.session_dir / "post_call_inv_count.txt"

    committed_call_inv = (
        not ctx.has_new_error and not ctx.no_progress
        and bool(_POST_CALL_INV_RE.match(ctx.trimmed or ""))
    )
    if committed_call_inv:
        try:
            post_call_path.write_text("0")
        except OSError:
            pass
        return None

    if not post_call_path.exists():
        return None

    try:
        prev_pc = int(post_call_path.read_text().strip())
    except (OSError, ValueError):
        prev_pc = 0

    closed_subgoal = (
        ctx.prev_count > 0 and ctx.curr_count >= 0
        and ctx.curr_count < ctx.prev_count
    )
    if closed_subgoal:
        try:
            post_call_path.write_text("0")
        except OSError:
            pass
        return None

    if ctx.has_new_error or ctx.no_progress:
        new_pc = prev_pc + 1
        if new_pc >= 3:
            try:
                post_call_path.unlink()
            except OSError:
                pass
            return HookResult(text=_POST_CALL_INV_HINT_TEXT, layer=0)
        try:
            post_call_path.write_text(str(new_pc))
        except OSError:
            pass

    return None


# ─── [GOAL_CLOSED] / [ALL_GOALS_CLOSED] (Phase 3c) ───────────────────────

def goal_closed_trigger(ctx: CommitHookContext) -> Optional[HookResult]:
    """Partial-close: `prev_count > 0 and curr_count > 0 and curr_count <
    prev_count`. Skipped when the proof is fully closed (an
    `[ALL_GOALS_CLOSED]` hook handles that).
    """
    if ctx.no_more or ctx.async_check_close:
        return None
    if ctx.prev_count > 0 and ctx.curr_count > 0 and ctx.curr_count < ctx.prev_count:
        closed = ctx.prev_count - ctx.curr_count
        return HookResult(
            text=(
                f"[GOAL_CLOSED] {closed} goal(s) closed by this tactic. "
                f"{ctx.curr_count} goal(s) remaining.\n"
            ),
            layer=0,
        )
    return None


def all_goals_closed_trigger(ctx: CommitHookContext) -> Optional[HookResult]:
    """Two emit paths: `no_more` (EC said "No more goals") OR async-check
    close (block ended with `qed.`, EC went into async mode with no goal
    text after). Both indicate the proof is structurally closed.
    """
    if ctx.no_more:
        return HookResult(
            text="[ALL_GOALS_CLOSED] All proof goals have been closed.\n",
            layer=0,
        )
    if ctx.async_check_close:
        return HookResult(
            text=(
                "[ALL_GOALS_CLOSED] All proof goals have been closed "
                "(qed accepted; EC in async-check mode — full-file "
                "verify is the source of truth for SMT correctness).\n"
            ),
            layer=0,
        )
    return None


# ─── [goal:<type>] (Phase 3c) ────────────────────────────────────────────

def compute_goal_header(active_goal: str) -> str:
    """Classify the active goal text and return a one-line `[goal: …]`
    header (or empty string when the input is empty or unparseable).

    Two pieces of metadata get appended when relevant:
    - `eager` goals: warning to use `eager proc`, NOT `swap/sim/call`.
    - `probability` goals with non-`res` event vars: instruction to
      use explicit `byequiv` postcondition naming the vars.

    The same string is consumed by:
    1. `goal_header_trigger` (hook) — emits as L1 prefix above
       `State:` in the commit-time display.
    2. `Session._auto_goal_header` (chain handler, goal-info, etc.) —
       pre-existing call sites that don't go through commit hooks.
    """
    if not active_goal:
        return ""
    if "No more goals" in active_goal:
        return "[goal: complete]\n"
    if (
        "Current goal" not in active_goal
        and re.fullmatch(r"\s*(?:OK\s*)?\[\d+\|[^\]]+\]>\s*", active_goal)
    ):
        return ""
    try:
        from core.easycrypt.analysis.ec_goal_parser import (  # type: ignore
            _extract_goal_body, classify_goal, extract_event_vars,
        )
    except Exception:
        return ""
    goal_type = classify_goal(active_goal)
    extra = ""
    if goal_type == "eager":
        extra = " ⚠️  Use 'eager proc', NOT swap/sim/call."
    elif goal_type == "probability":
        body = _extract_goal_body(active_goal)
        evars = extract_event_vars(body)
        if evars and "res" not in evars:
            extra = (
                f" Event vars: {evars} — use explicit byequiv "
                f"postcondition."
            )
    return f"[goal: {goal_type}]{extra}\n"


def goal_header_trigger(ctx: CommitHookContext) -> Optional[HookResult]:
    """Emit `[goal: <type>]` for the post-commit active goal. L1 — sits
    above `State:` in the final display.
    """
    text = compute_goal_header(ctx.active_goal)
    return HookResult(text=text, layer=1) if text else None


# ─── [STRICT_WARNING] (Phase 3c) ─────────────────────────────────────────

def strict_warning_trigger(ctx: CommitHookContext) -> Optional[HookResult]:
    """Downgrade strict-mode SMT replay errors when the proof is otherwise
    closed. Fires when:

    1. `no_more` (proof structurally closed — EC said "No more goals"), AND
    2. `has_new_error` (some error text accompanied the close), AND
    3. EVERY new error line matches "cannot prove goal" + "strict" (i.e.,
       only strict-mode SMT replay warnings remain — no real failures).

    Side effect via `HookResult.suppress_error=True`: caller sets
    `has_new_error = False`. Without this, downstream hooks would treat
    the close as a failed commit and surface
    spurious diagnostic blocks.

    Note: a chain-handler variant of this fires from the chain command path
    with leading 2-space indent under `[N/M]` per-step prefix. That path
    doesn't pass through commit hooks; migrating it is out of scope for this
    trigger.
    """
    if not (ctx.no_more and ctx.has_new_error):
        return None
    new_error_lines = set(ctx.raw_curr.splitlines()) - set(ctx.raw_prev.splitlines())
    strict_only = all(
        "cannot prove goal" in e and "strict" in e.lower()
        for e in new_error_lines if "[error" in e
    )
    if not (strict_only and any("[error" in e for e in new_error_lines)):
        return None
    return HookResult(
        text=(
            "[STRICT_WARNING] smt proof accepted but may not replay in "
            "strict mode. Consider adding more lemma hints or using a "
            "deterministic proof if full-file check fails.\n"
        ),
        layer=0,
        suppress_error=True,
    )


# ─── [GOAL-TOO-LARGE] (Phase 3c) ─────────────────────────────────────────


def goal_too_large_trigger(ctx: CommitHookContext) -> Optional[HookResult]:
    """Fires when the post-commit active goal exceeds 8000 bytes. The same
    threshold/body fires from `-goal-info` directly — that path calls
    `too_large_warning_block` without going through this trigger.
    """
    if ctx.active_goal and is_goal_too_large(ctx.active_goal):
        return HookResult(
            text=too_large_warning_block(ctx.active_goal), layer=0,
        )
    return None


# ─── [TACTIC_NO_EFFECT_AUTO_REVERTED] (Phase 3c step 8) ──────────────────

_TACTIC_NO_EFFECT_TEXT = (
    "[TACTIC_NO_EFFECT_AUTO_REVERTED] The tactic was accepted by EC "
    "but did not change the goal state. Session history has been "
    "automatically rolled back — this tactic is NOT committed. Try "
    "a different approach; do NOT run -prev (there is nothing to "
    "undo).\n"
)


def tactic_no_effect_trigger(
        ctx: CommitHookContext) -> Optional[HookResult]:
    """Auto-revert for accepted-but-no-progress tactics. Pre-rollback
    detection happens upstream (`Session.detect_no_progress`); the
    hook fires when `ctx.no_progress` is True and requests the
    rollback via `request_rollback=True`. Caller
    (`Session.append_block`) applies it via
    `Session._apply_no_progress_rollback()` after dispatch.

    The rollback restores history.ec, pops a step from steps.log,
    restores curr.out from prev.out, and invalidates the daemon
    cache (EC has no undo, so the daemon session must be dropped
    and replayed on the next `-next`).

    Why a mutation flag instead of inline rollback in the trigger:
    keeps hooks pure (single emit + flags). The caller owns the
    file-mutation responsibility; the hook only declares "this kind
    of side effect should follow my emit."
    """
    if not ctx.no_progress:
        return None
    return HookResult(
        text=_TACTIC_NO_EFFECT_TEXT,
        layer=0,
        request_rollback=True,
    )


# ─── [STATE-DIFF] (Phase 3c step 7) ──────────────────────────────────────

def state_diff_trigger(ctx: CommitHookContext) -> Optional[HookResult]:
    """Emit `[STATE-DIFF]` block (compute_state_diff verdict + body) AND
    append a one-line summary to `<session_dir>/commit_meta.log` for
    later reads by `Session._recent_lemma_names` (cross-subgoal-
    transition detection in AUTO-DIFF repeat warnings).

    Gate: tactic actually committed (`not no_progress and not
    has_new_error`). The `has_new_error` companion path
    — log-only, no STATE-DIFF emit — stays inline because it depends
    on `Session._count_lines` for daemon-rollback detection.

    Side effect (commit_meta.log write) runs even when
    `format_state_diff_block` returns empty text — the meta entry is
    needed for log/history.ec alignment regardless of whether the
    block is shown.
    """
    if ctx.no_progress or ctx.has_new_error:
        return None
    try:
        from core.easycrypt.analysis.ec_state_diff import (  # type: ignore
            compute_state_diff, format_state_diff_block,
        )
    except Exception:
        return None
    try:
        diff = compute_state_diff(ctx.raw_prev, ctx.raw_curr, ctx.trimmed)
    except Exception:
        return None
    try:
        block = format_state_diff_block(diff)
    except Exception:
        block = ""
    # Persist a single `verdict|delta|tactic_text` line per commit.
    # Writes happen even if `block` is empty so the cross-subgoal
    # transition analysis sees consistent history.
    try:
        pre_n = diff.get("pre_metrics", {}).get("subgoals_count", 0) or 0
        post_n = diff.get("post_metrics", {}).get("subgoals_count", 0) or 0
        delta = post_n - pre_n
        tactic_one = (ctx.trimmed or "").strip().replace("\n", " ")
        meta_line = (
            f"{diff.get('verdict', '—')}|{delta}|{tactic_one}\n"
        )
    except Exception:
        tactic_one = (ctx.trimmed or "").strip().replace("\n", " ")
        meta_line = f"—|—|{tactic_one}\n"
    try:
        meta_path = ctx.session_dir / "commit_meta.log"
        with meta_path.open("a", encoding="utf-8") as mf:
            mf.write(meta_line)
    except Exception:
        pass
    return HookResult(text=block, layer=0) if block else None


# ─── [DAEMON_REJECTED] (Phase 3c step 6) ─────────────────────────────────

def daemon_rejected_trigger(ctx: CommitHookContext) -> Optional[HookResult]:
    """Surface the daemon's rejection text as a top-level L0 block.

    Fires when `ctx.daemon_rejection_error` is non-empty (the caller
    threads it in from the EC commit result's rejection_error).
    Strips leading `[error]` / `[critical]` /
    `[fatal]` prefix from the error text and adds the standard
    "session state unchanged; read classifier below" footer.

    The `[CLASS:...]` classifier follow-up stays inline in
    append_block — it's a separate concern (4 call sites total),
    not paired one-to-one with this hook.
    """
    if not ctx.daemon_rejection_error:
        return None
    err_text = ctx.daemon_rejection_error.strip()
    for prefix in ("[error]", "[critical]", "[fatal]"):
        if err_text.startswith(prefix):
            err_text = err_text[len(prefix):].lstrip()
            break
    return HookResult(
        text=(
            f"[DAEMON_REJECTED] {err_text}\n"
            f"  EC daemon rejected this tactic. The session state "
            f"is unchanged (history rolled back); the tactic is "
            f"NOT committed. Read the classifier block below "
            f"before retrying.\n"
        ),
        layer=0,
    )


# ─── [AUTO-NOPROG-HINT] (Phase 3c step 6) ────────────────────────────────

def auto_noprog_hint_trigger(ctx: CommitHookContext) -> Optional[HookResult]:
    """Compiler-style diagnostic for no-progress tactics. Fires after
    `[TACTIC_NO_EFFECT_AUTO_REVERTED]` (still inline because of the
    rollback side effects) when the shared no-progress diagnostic returns
    non-empty advice for the tactic against the prior goal state.

    The pre-tactic state — `ctx.raw_prev` — is what the tactic was
    supposed to act on; passing `raw_curr` would mean diagnosing the
    post-state which is identical to pre by definition (no_progress
    means text-equal or fingerprint-equal).
    """
    if not ctx.no_progress:
        return None
    try:
        from core.easycrypt.session_api import explain_no_progress  # type: ignore
    except Exception:
        try:
            from core.easycrypt.session_api import explain_no_progress  # type: ignore
        except Exception:
            return None
    try:
        hint = explain_no_progress(ctx.trimmed, ctx.raw_prev)
    except Exception:
        return None
    if not hint:
        return None
    return HookResult(text=f"[AUTO-NOPROG-HINT] {hint}\n", layer=0)


# ─── Stateful commit phases ──────────────────────────────────────────────

from core.easycrypt.session_hook_phases import (  # type: ignore
    AutoDiffPhase,
    AutoSigPhase,
    HintDispatchPhase,
    PivotStrategyPhase,
    make_default_hint_dispatch_phase,
)


# ─── [SEARCH-QUERY-AUTOFIX] ──────────────────────────────────────────────

def autofix_bre_alternation(raw_query: str) -> tuple[str, bool]:
    """Convert BRE-style `\\|` alternation to ERE `|` for Python `re`.

    Agents commonly write `pat1\\|pat2\\|pat3` (GNU grep BRE alternation
    syntax) when they want OR. Python `re` (used by `-search`) is ERE-style:
    `\\|` matches a literal `|` character — never present in any lemma
    name. This helper transforms the query before search; the
    `[SEARCH-QUERY-AUTOFIX]` hook below surfaces a notice when the fix
    fired.

    Returns (effective_query, was_autofixed).
    """
    if '\\|' in raw_query:
        return raw_query.replace('\\|', '|'), True
    return raw_query, False


def search_query_autofix_trigger(ctx: SearchHookContext) -> Optional[str]:
    """[SEARCH-QUERY-AUTOFIX] notice when raw_query had BRE alternation.

    Emit only when `was_autofixed=True`. Parse the search output for the
    hit count to include in the notice.
    """
    if not ctx.was_autofixed:
        return None
    m_hits = re.search(r'\((\d+) match', ctx.output)
    n_hits = int(m_hits.group(1)) if m_hits else 0
    return (
        f"[SEARCH-QUERY-AUTOFIX] Your query used `\\|` for alternation "
        f"(BRE / GNU grep syntax), but `-search` uses Python `re` "
        f"(ERE) where `\\|` matches a literal `|` character — not "
        f"alternation. I auto-corrected `\\|` → `|` and re-ran.\n"
        f"  Original:   '{ctx.raw_query}'\n"
        f"  Auto-fixed: '{ctx.effective_query}'\n"
        f"  Below: {n_hits} match{'es' if n_hits != 1 else ''} from "
        f"the fixed query.\n\n"
    )


# ─── [SEARCH-FALLBACK-HINT] ──────────────────────────────────────────────

def search_fallback_trigger(ctx: SearchHookContext) -> Optional[str]:
    """[SEARCH-FALLBACK-HINT] after 3 consecutive 0-hit searches.

    State persists in `<session_dir>/search_no_hit_count.txt` as a single
    non-negative integer (created on first no-hit, incremented on each
    subsequent no-hit, reset to 0 on any hit). When count reaches 3, emit
    the fallback hint pointing at `-search-skeleton` and `-lemma-hints`.

    Side effect: this trigger ALWAYS updates the counter (regardless of
    whether it emits) — it's the canonical no-hit tracker. Other hooks
    should not write to `search_no_hit_count.txt`.
    """
    nohit_path = ctx.session_dir / "search_no_hit_count.txt"
    try:
        prev_count = (int(nohit_path.read_text().strip())
                      if nohit_path.exists() else 0)
    except (OSError, ValueError):
        prev_count = 0
    is_no_hit = ctx.output.lstrip().startswith("No matches for")
    new_count = prev_count + 1 if is_no_hit else 0
    try:
        nohit_path.write_text(str(new_count))
    except OSError:
        pass
    if is_no_hit and new_count >= 3:
        return (
            f"\n[SEARCH-FALLBACK-HINT] {new_count} consecutive `-search` "
            f"queries returned no matches.\n"
            f"  `-search` is regex on declaration NAMES — it misses "
            f"lemmas whose name doesn't match your pattern but whose "
            f"STATEMENT contains the operators you need.\n"
            f"  Try `-search-skeleton 'OP1 OP2'` (EC's native AST "
            f"search) to find lemmas where two operators co-occur — "
            f"e.g. `-search-skeleton 'take mem'` returns `mem_take` "
            f"even though the lemma's name doesn't contain both words.\n"
            f"  Or `-lemma-hints` (no args; reads the current goal) "
            f"for an op-indexed stdlib shortlist.\n\n"
        )
    return None


# ─── Registries ──────────────────────────────────────────────────────────

# Order within a registry is the order in which hooks are evaluated.
# For commit hooks, layer (not registry order) controls display position
# after `_reorder_display`. For search hooks, registry order IS display
# order.

_COMMIT_HOOKS: list[CommitHook] = [
    CommitHook(
        marker="[POST-CALL-INV-HINT]",
        layer=0,
        description=(
            "Failure-driven hint after 3 consecutive failures (errors or "
            "no-progress) on subgoals spawned by a prior committed `call "
            "(_: Inv)`, with no fan-out subgoal closed in between."
        ),
        trigger=post_call_inv_trigger,
    ),
    CommitHook(
        marker="[GOAL_CLOSED]",
        layer=0,
        description=(
            "Partial-close: subgoal count strictly decreased but the proof "
            "isn't fully closed. Reports closed-count + remaining-count."
        ),
        trigger=goal_closed_trigger,
    ),
    CommitHook(
        marker="[ALL_GOALS_CLOSED]",
        layer=0,
        description=(
            "Proof structurally closed. Two paths: EC printed 'No more goals' "
            "(synchronous), or block ended with qed. and EC went to "
            "async-check mode without a goal-text response."
        ),
        trigger=all_goals_closed_trigger,
    ),
    CommitHook(
        marker="[GOAL-TOO-LARGE]",
        layer=0,
        description=(
            "Active goal exceeds 8KB after the commit — usually `inline *` "
            "blew up the program tree. Surfaces the size and recovery moves."
        ),
        trigger=goal_too_large_trigger,
    ),
    CommitHook(
        marker="[TACTIC_NO_EFFECT_AUTO_REVERTED]",
        layer=0,
        description=(
            "Auto-revert for accepted-but-no-progress tactics. Detects "
            "via Session.detect_no_progress (text-equal or "
            "structural-fingerprint-equal between pre and post raw). "
            "Returns request_rollback=True so the caller restores "
            "history.ec / steps.log / curr.out from their pre-tactic "
            "snapshots and invalidates the daemon."
        ),
        trigger=tactic_no_effect_trigger,
    ),
    CommitHook(
        marker="[STRICT_WARNING]",
        layer=0,
        description=(
            "Proof closed but only strict-mode SMT replay errors remain. "
            "Downgrades has_new_error to False via "
            "HookResult.suppress_error so downstream hooks don't treat "
            "the close as a failure."
        ),
        trigger=strict_warning_trigger,
    ),
    CommitHook(
        marker="[goal:",
        layer=1,
        description=(
            "Classifies the active goal (pRHL, equiv, probability, "
            "eager, ambient, …) and emits a one-line header with optional "
            "warnings for eager goals and probability goals with "
            "non-`res` event vars."
        ),
        trigger=goal_header_trigger,
    ),
    CommitHook(
        marker="[DAEMON_REJECTED]",
        layer=0,
        description=(
            "Surfaces daemon-side rejection text (parse error, "
            "unknown lemma, `cannot infer all placeholders`, etc.) "
            "captured by the daemon path before commit. Without this "
            "block, daemon rejections on tactics that AUTO-SIG does not "
            "match (e.g. `ecall <LEMMA>`) are fully "
            "silent. The classifier `[CLASS:...]` block follows "
            "inline in append_block."
        ),
        trigger=daemon_rejected_trigger,
    ),
    CommitHook(
        marker="[AUTO-NOPROG-HINT]",
        layer=0,
        description=(
            "Compiler-style diagnostic for no-progress tactics. "
            "Calls the shared no-progress diagnostic against the pre-tactic "
            "goal state — extracts trailing-non-call statements, "
            "suggests wp/sp/seq peeling, warns about `={glob X}` "
            "invariant mismatches. Fires after TACTIC_NO_EFFECT_AUTO_REVERTED "
            "(which still lives inline in append_block due to its "
            "rollback side effects)."
        ),
        trigger=auto_noprog_hint_trigger,
    ),
    CommitHook(
        marker="[STATE-DIFF]",
        layer=0,
        description=(
            "Structural verdict on the tactic's effect (subgoal count, "
            "Pr[] terms, quantifiers, module nesting depth, top "
            "connectives) plus cosmetic-noise detection (beta-redex, "
            "eta, iota, unreduced glob chains). Side effect: appends "
            "one line to <dir>/commit_meta.log for "
            "cross-subgoal-transition detection in AUTO-DIFF repeat "
            "warnings."
        ),
        trigger=state_diff_trigger,
    ),
]


_SEARCH_HOOKS_POST: list[SearchHook] = [
    SearchHook(
        marker="[SEARCH-QUERY-AUTOFIX]",
        description=(
            "BRE→ERE alternation autofix notice. Fires when `raw_query` "
            "contained `\\|` and `effective_query` substituted `|`; emits "
            "the original/fixed query pair plus the hit count."
        ),
        trigger=search_query_autofix_trigger,
    ),
    SearchHook(
        marker="[SEARCH-FALLBACK-HINT]",
        description=(
            "After 3 consecutive 0-hit `-search` invocations, point at "
            "`-search-skeleton` (op-AND) and `-lemma-hints` (op-indexed) "
            "as alternative tools the agent likely doesn't know about."
        ),
        trigger=search_fallback_trigger,
    ),
]


# ─── Dispatch ─────────────────────────────────────────────────────────────

def run_commit_hooks(
    ctx: CommitHookContext,
    phases: "list[CommitPhase] | tuple[CommitPhase, ...]" = (),
) -> tuple[list[HookResult], MutationFlags]:
    """EC-specific entry point. Delegates to the backend-neutral
    dispatcher in `hooks.contract`, passing the EC commit-hook
    registry (`_COMMIT_HOOKS`) and the caller-provided phases list.

    Kept here so existing call sites in session_cli.py continue to
    work with the simple `run_commit_hooks(ctx, phases)` signature
    rather than having to thread the registry through.

    See `hooks.contract.run_commit_hooks` for the dispatch semantics
    (order, exception isolation, mutation aggregation,
    descriptor-layer fill-in).
    """
    return _run_commit_hooks_base(ctx, hooks=_COMMIT_HOOKS, phases=phases)


def run_search_hooks(ctx: SearchHookContext) -> list[str]:
    """Run all post-search hooks; return block texts in registry order.

    Caller is responsible for printing these BEFORE the search-result body
    (current convention: hooks appear above results).
    """
    out: list[str] = []
    for hook in _SEARCH_HOOKS_POST:
        try:
            result = hook.trigger(ctx)
        except Exception:
            continue
        if result:
            out.append(result)
    return out
