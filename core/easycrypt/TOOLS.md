# EasyCrypt Tooling for LLM Provers

**Date:** 2026-05-14
**Replaces:** 2026-04-20 edition.

## Compiler-philosophy rating — what it means

Prover-facing tools are rated on whether they cover the three axes of an actionable hint, namely the structure "**When X**, **look at Y**, **try Z**":

- **When (X)** — recognize a *generic pattern*: a goal shape, a tactic failure mode, a structural condition. Applies to ANY EC project, not just one.
- **Look at (Y)** — *context-driven retrieval*: pull info from the actual current goal text, file content, lemma signatures, daemon state, etc. (NOT hardcoded names).
- **Try (Z)** — a *concrete, instantiated tactic suggestion*: feed Y back into a generic template so the agent gets a paste-ready next step, not just generic advice.

Legend: ✅ axis fully covered, 🟡 partially covered, ❌ axis missing.
Grades: **A+** = all three axes covered; **A** = two strong + one partial; **B** = one or two strong, the rest missing; **C** = only one axis (e.g. context-only query, or static-only doc). "Infrastructure" = correctness/glue, not a user-facing hint.

This document describes the EasyCrypt tooling layer under the managed prover
architecture. `session_cli.py` remains the backend/human-debug adapter, while
agent-facing proof interaction goes through `workflow.proof_node_manager`.
Tools exist at nine layers:

1. **ProofNodeManager facade** — the one manager visible to agents and
   orchestrator; accepts proof-level intents and returns `ProverWorkspaceView`.
2. **ReplSessionManager backend** — internal EasyCrypt/session lifecycle owner.
3. **WorkspaceViewManager projection** — internal
   `ProofContextView -> ProverWorkspaceView` display policy.
4. **Interactive backend flags** — `-foo` subcommands on `session_cli.py`, used
   by manager internals and humans.
5. **Automatic diagnostic hooks** — `[AUTO-*]` blocks emitted by the backend on
   tactic commit. They surface context the agent would otherwise have to search
   for.
6. **Structured session events** — append-only `events.jsonl` records tool calls,
   tactic results, goal changes, candidate closure, and verification.
7. **Structured ToolView envelopes** — read-only tools package
   `proof_state`, `guidance.recommendations`, and `evidence` so agents do not
   have to parse display markers for semantics.
8. **Daemon infrastructure** — persistent EC subprocess pool that amortizes REPL
   startup cost and enables speculative tactic probing.
9. **Standalone utilities** — non-interactive tools (lemma extraction, batch
   evaluation, env loading).

Every tool was created in response to a specific stuck-point observed in prover traces — the LLM would waste 5–30 minutes on a task that the tool solves in seconds. See [`prover_style_analysis.md`](../../docs/reports/insights/prover_style_analysis.md) for the failure modes that drove the AUTO-* hooks in particular.

---

## Design Philosophy

**Key insight #1: LLMs don't understand EasyCrypt's goal representation.**

EasyCrypt output is a specialized two-column pRHL format, nested goal structures, and cryptic error messages. LLMs can read this output but consistently misinterpret:

1. **Program structure** — which statement is on which line, what position numbers mean for `swap`, how `inline *` transforms the goal.
2. **Error semantics** — what `swap_not_independent` actually means, whether an error is a syntax problem or a fundamental strategy problem.
3. **Goal type** — whether the current goal is pRHL, eager, hoare, or ambient — each requires completely different tactics.

The tools bridge this gap by **parsing EC output into LLM-friendly structured information** and **automating mechanical tasks** that LLMs do poorly.

**Key insight #2 (added 2026-04-20): abstract-plan-known + concrete-syntax-unknown is a stable local minimum.**

The agent can derive `rewrite -(OpCCinit.pr_CCP_OCCP I_stateless G1 &m).` in thought — but without the concrete signature and argument list, it reverts to `inline *` because `inline *` takes zero arguments (zero uncertainty). The AUTO-* hooks (especially `AUTO-PIVOT-VERIFIED` and `AUTO-BRIDGE-SUGGEST`) resolve this by **daemon-verifying candidate tactics against the current goal and surfacing the accepted ones as pasteable strings**. The agent is handed a ready-to-commit tactic instead of having to synthesize one.

**Design principle: support, don't replace, reasoning.** Hooks and workspace
panels provide facts, options, and evidence. They do not force a tactic order.
Agent-facing wording should remain neutral: "if pursuing this route, possible
handles are ..." rather than "do this first".

**Design principle: event stream over display parsing.** Human-facing stdout is
still useful for agents, but orchestration should not rely on brittle strings
such as `No more goals` or `[ALL_GOALS_CLOSED]` as its primary state signal.
The session runtime records an append-only `events.jsonl` in the session
directory. Use `proof.candidate_closed` as the structured "interactive proof is
closed" signal, and require `verification.completed.status == "pass"` before
accepting the proof. See `workflow/validation/README.md` for the event schema
and replay audit workflow.

Inspection tools should read current EC state through `session_state.py`, not
by each scanning `current.out` independently. This keeps prompt handling,
active-goal extraction, and post-`qed.` closed-proof shapes consistent across
`-status`, `-goal-info`, `-goal-patterns`, `-suggest-close`, and future tools.

**Design principle: context has evidence.** Tool output should distinguish
authoritative state from proof options. `proof_state` is the truth layer;
`guidance.recommendations` and workspace `candidate_moves` are advisory;
`evidence` records whether a proof option came from deterministic parsing,
current-file context, KB pattern matching, retrieval, daemon probing, or raw
fallback text. Migrated read-only tools keep
legacy stdout but also persist full ToolView JSON under `tool_views/` and emit
compact `tool.view.produced` events with a hash and artifact pointer. Current
ToolView producers include `status`, `goal-info`, `goal-json`, `program-json`,
`goal-patterns`, `diagnose`, `align`, `subgoal-gap`, `suggest-close`,
`swap-search`, and `bridge-lemmas`.
AUTO hooks still render `[AUTO-*]` blocks, but migrated hooks also carry
structured recommendations/evidence in `diagnostic.emitted`.

`-agent-view` is the backend aggregate command over those pieces. Internally it
builds a full `ProofContextView` from the canonical projection, recent ToolView
artifacts, structured diagnostics, ProofIR phase analysis, fresh guidance,
stale guidance, evidence, latest errors, and compatibility actions. That full
fact package is persisted under `proof_context_views/` and emitted as
`agent.view.produced`.

The JSON printed to stdout is intentionally smaller: a `ProverWorkspaceView`
with eight IDE-style panels in this order: `last_result`, `proof_status`,
`current_goal`, `program_frontier`, `application_context`,
`facts_and_diagnostics`, `candidate_moves`, and `inspect_lookup_handles`.
`last_result` and `proof_status` stay brief. `current_goal` is always the
committed EasyCrypt proof state; accepted read-only probes show their
speculative post-goal under `last_result.probe_preview.goal_after_probe`.
`application_context` displays selected handles, declaration-derived
requirements, binding/anchor facts, residual obligations, and visible-but-not
required state when ProofContextView/ProofIR/tool output already contains that
material. `candidate_moves` uses neutral fields such as `applicability`,
`effect`, `limitations`, and `use_when`; strategy-only items stay as context
until the agent instantiates a concrete tactic. `program_frontier.call_sites`
expands live/frontier call counts into side/path/procedure/statement entries
when proof-state analysis can identify them. `inspect_lookup_handles` names
semantic manager requests such as `goal_info`, `diagnose`, `episode_view`,
`align`, `subgoal_gap`, `bridge_probe`, or `inv_from_lemma`.

### Panel design philosophy (progressive disclosure, size, provenance)

This is the standing contract for what the `ProverWorkspaceView` panels show.
It is a **design invariant**: a refactor may reorganize *how* panels are built,
but must not change *what* this section requires, and must re-run the panel
philosophy audit afterward (see "Panel philosophy audit" below). It was
augmented 2026-05-28 after a regression where always-on strategy framing
(`proof_story.active_route_objective` + `risk_map`) tripled `application_context`
and pushed the agent into multi-minute whole-proof pre-planning before easy
structural commits.

**Principle: progressive, goal-state gated — not a constant dashboard.** A panel
appears only when the *current* goal-state needs it, following the L1→L4 ladder
(see the "Paper eval interface ladder" doc, `docs/concepts/eval_interface_ladder.md`): L1 is just current
goal / status / last result; route hypotheses, phase doors, and liveness/cost
warnings are **L3** and must not appear unconditionally at an L1 state (e.g. a
fresh `Pr[A]-Pr[B]=Pr[C]-Pr[D]` goal needs "this is a probability goal; `congr`
splits it", not the whole game-hop route). The view tracks the current goal, so
it should stay flat or **shrink** as the goal narrows — a view whose size grows
monotonically with proof depth is a bug.

**Principle: push what removes cheap uncertainty; ignore the rest.** Surface a
fact exactly when it spares the agent from leaving the view to re-derive or
guess it — module signatures, type-matched endpoints, instantiation bindings,
"what is missing and where it could come from". Do **not** push (a) context the
agent cannot act on yet (a post-`congr` rewrite shown before `congr`), (b) the
whole-proof route/arc as a per-step directive, or (c) risk warnings as default
framing — risk is surfaced as *evidence after a relevant failure* ("byequiv just
left N residual subgoals"), never pre-emptively on every goal of a shape.

**Principle: strategically reticent, structurally generous.** Be sparing with
strategy/route framing; be rich with structural facts. The pre-refactor lean
view was right to drop strategy framing but wrong to also withhold structure
(the agent then ran `grep` and still guessed, e.g. "I don't have the source of
`Indist.Distinguish`"). Make leaving the view unnecessary.

**Principle: importance ranking.** `current_goal.lines` is always #1 and must be
complete and untruncated; everything else is subordinate. The unit of relevance
is *this turn's decision*, not the plan — surface what helps choose the next
move, not how the whole proof goes.

**Principle: workbench rhythm over pre-simulation.** Because probe/commit are
cheap and `undo_last_step`/`undo_to_checkpoint` exist, the view must encourage
"commit and read the resulting state, undo if worse" and must never require the
agent to plan beyond the next move to act safely. Falsifiable test: **if the
view makes the agent feel it must see the whole route before committing one
verified move, the view is wrong.**

**Verified tactics may be surfaced — with mandatory provenance (resolves Key
insight #2).** A daemon-verified tactic *may* be handed to the agent as a
ready-to-commit option (this is the point of `AUTO-BRIDGE-SUGGEST` /
`call_site_options` / `rewrite_candidates`). It must carry, and a verified-tactic
entry without these is treated by the audit as a **misleading panel**:

- `derivation` — how the string was produced, in plain terms, e.g. "typed bridge
  frontend: endpoint typing + clone-qualified name resolution (`OpCCinit`) +
  signature match (`I_stateless:Init`) → enumerate `(functor, init)` →
  daemon-probe on the current goal".
- `verified` — the verification scope, e.g. `daemon_accepted_on_current_goal`
  (the daemon ran *this* tactic on *this* goal and it was accepted).
- `guarantee` — the anti-mislead clause, stating what it does **not** promise:
  "locally valid (passes on the current goal); not a claim it is the optimal
  route or that it reaches `qed`; reversible — commit, read the new state, undo
  if worse".
- `source_refs` — the lemma / endpoint / bindings it used, so the agent can
  inspect.

The tactic is framed as an **option labelled "verified-available"**, never as
"the move" or "do this first". Daemon acceptance is *local validity*, not
*strategic value* — the marking must make that distinction legible so the agent
is not misled into treating a verified move as a guaranteed-correct route.

**Size budget (quantitative).** Target total view ≤ ~5 KB (the pre-refactor
norm; framing panels only — the goal/frontier truth layers are exempt). Size is
a *secondary* signal (a rich-but-clean equiv goal legitimately needs more
framing than a bloated Pr goal), so the real bloat detector is framing
*presence*, not raw size. `candidate_moves` ≤ ~3 options; `inspect_lookup_handles`
≤ ~6 state-relevant topics (the canonical menu). At an L1 state,
`application_context` is near-empty.

**Anti-patterns (audit-flagged).** (1) Any panel value that is a constant string
across goal-states (it is not context-derived — `active_route_objective`'s fixed
sentence is the canonical example). (2) Imperative / ordering wording in
agent-facing text ("do this first", "resolve ... before opening ...", risk
ordering). (3) L3 route-hypothesis content at an L1 state. (4) View total over
the size budget, or growing monotonically with proof depth. (5) A runnable
verified tactic missing `derivation` / `verified` / `guarantee` markers.

### Panel philosophy audit

`workflow/validation/view_philosophy_audit.py` checks one or a sequence of
`workspace_views/turn_*.json` against the anti-patterns above and is part of the
proof-manager refactor gate. A view-snapshot regression test (the anchor
manifest) confirms panels did not *disappear*; the philosophy audit confirms
they did not *violate the contract*. Refactors that touch view rendering must
pass both.

### Map, navigator, and surgery workbench

For the managed prover, the useful metaphor is an IDE with a map and a surgery
table:

- `ProofIR`, ToolViews, and source facts draw the **map**: goal family,
  program frontier, call sites, name-resolution evidence, residual facts, and
  recent failures.
- `candidate_moves.navigation` is the **navigator**: at most three
  current-view route hypotheses, each with confidence, anti-routes, bounded
  fast-track probe, expected next shape, and repair guidance.
- `ProverWorkspaceView` is the **workbench**: the only compact panel the agent
  needs each turn.
- pRHL branch/suffix work is the **surgery table**: `case`,
  `rcondt`/`rcondf`, `swap`, indexed `wp`, `conseq`, one-sided `rnd`, and
  local closing tactics should be checked against the visible frontier rather
  than guessed globally.
- `probe_tactic` and `call_subgoals` are **previews**. A tactic probe is
  read-only and places speculative after-goal text under
  `last_result.probe_preview.goal_after_probe`; `call_subgoals` previews the
  obligations created by a concrete `call (_: Inv)` invariant before the proof
  commits to it.
- `ProofNodeManager` may add **vital signs** under
  `candidate_moves.route_health`, **phase doors** under
  `candidate_moves.structural_transitions`, and accepted/rejected preview
  history under `candidate_moves.probe_alternatives`.

All of these surfaces are advisory except the committed goal itself. They help
the prover choose a proof intent; they do not replace EasyCrypt execution,
offline replay, or the manager-owned proof-state boundary.

Agent-facing panel design follows one rule: the workspace view should read like
an IDE surface, not a backend transcript. `current_goal` is the authoritative
committed proof state; `program_frontier` and `application_context` expose the
proof situation; `candidate_moves` contains proof-level moves or tactic shapes;
and `inspect_lookup_handles` contains read-only questions the agent can ask the
manager. The context compiler, ProofIR, and tools produce candidates and
evidence; ProverWorkspaceView only selects, orders, words, and lints that
material.

The panel framing, size, and imperative-wording rules live in
`core/easycrypt/panel_policy.py`. The read-only compliance checker for those
rules is `workflow/validation/view_philosophy_audit.py`, which audits a single
version's persisted views for policy violations. (Runtime enforcement wiring
that calls `panel_policy.enforce()` from the view producers is a tracked
follow-up and is not yet active.)

Handle topics must be normalized before they reach the agent. Topic names are
semantic requests such as `goal_info`, `call_site_options`, `call_subgoals`,
`pivot_context`, `pr_bridge_routes` (verified Pr bridge routes — game-hops and
scheme/endpoint normalizations; old name `bridge_options` still resolves),
`equiv_bridge_lemmas` (context-only equiv bridge lemma names; old name
`bridge_lemmas`), `goal_patterns`, `suggest_close`, `align`,
and `tactic_forms`. Low-level protocol or backend labels are not topics:
`inspect_context` is the generic intent wrapper, `try` is a probe execution
mode, and `session_cli`/raw flags are backend implementation details. Map them
to the right panel instead: probe-shaped choices go under `candidate_moves`,
specific declaration reads such as `-where NAME` become `lookup_candidates`,
and generic wrappers such as `inspect_context` are replaced by their concrete
semantic topic or dropped.

Agent-facing views do not expose backend commands, `debug_cli_fallback`,
`session_cli.py`, `next_actions`, `suggested_next_steps`, `next_try`, or
imperative strings such as "Lookup first". Stale recommendation bodies and
compiler internals stay in the ProofContextView artifact referenced by
`inspect_lookup_handles`. When `current_goal.text_fully_shown=true`, the workspace
view intentionally does not expose `current.out`; agents should use
`current_goal.lines`. Raw current-goal file fallback is only surfaced when the
inline goal is truncated.

Mutating commands also record a `CommitResponse` artifact under
`commit_responses/` and emit `commit.response.produced`. This is the structured
answer to "what did this `-next` / `-chain` invocation do?": attempted tactics,
accepted count, failed tactic, rollback count, and post-state projection. The
manager records the matching ProofContextView and ProverWorkspaceView and
links them from TacticExecutionResult/backend artifacts. New workflow code
should read that contract rather than parsing display text.

Tactic commands now print and persist `TacticExecutionResult` under
`tactic_execution_results/`, emitted as `tactic.execution.produced`. The printed
`[TACTIC-EXECUTION-RESULT]` block is a backend artifact after `-try`, `-next`,
`-prev`, or `-chain`: it combines execution outcome, current
ProverWorkspaceView, manager context requests, and audit artifact refs. In
managed runs, the agent sees the manager response and refreshed
`ProverWorkspaceView` rather than direct backend commands. CommandSummary
artifacts are retained only for historical audit compatibility.
Recommendation producers should attach `action_type` when they know their
intent (`runnable_tactic`, `inspection_action`, `strategy_hint`, or `warning`);
ProofContextView consumes that field when building canonical actions. Use
CommitResponse and ProofContextView when you need the full durable artifacts.

Legacy display is still available. For quieter prover-facing sessions set
`SHANNON_LEGACY_DISPLAY=compact` or `SHANNON_LEGACY_DISPLAY=off`; live tactic
commands print TacticExecutionResult as the structured result, while legacy text
stays optional display/debug output.

Use `-episode-view` when you need the cross-step prover view for a live
session. It projects structured tactic/view artifacts in event order, persists
`episode_timelines/*.json`, and emits `episode.timeline.produced`.

Use `workflow.validation.prover_behavior_audit` after replay or live Claude
runs to measure the interaction shape: tool calls by name, repeated read-only
calls on the same goal hash, decision-context follow-through, failed-step
diagnosis, and candidate-close verification follow-through.

**Module boundary:** `session_cli.py` is the backend/human-debug CLI/argparse
entry point. Agent-facing runs go through `ProofNodeManager`.
`session_runtime.py` owns the concrete `Session` and mutation operations.
`session_api.py` is the stable facade for non-CLI imports.
Read-only handlers should use `session_state.py` and pure helpers such as
`session_goal_context.py`, `session_diagnostics.py`, and
`session_display.py` instead of importing the CLI as a utility module.
Handlers that produce prover-facing guidance should use
`session_tool_view.py` for the envelope and validator.
Aggregate prover state should go through `session_agent_view.py` rather than
having agents or workflow code merge ToolViews and diagnostics by hand.
Stateful AUTO-* phase bodies live in `session_hook_phases.py`; `session_hooks.py`
keeps the hook contexts, simple triggers, registries, and compatibility
re-exports.

---

## Tool Relationships

`session_cli.py` is the central backend interface. Every minitool below is
dispatched as a flag/subcommand on it for manager internals or human debugging,
while the concrete session behavior lives in `session_runtime.py` and read-only
tool handlers live under `core/easycrypt/commands/`. The map below groups tools
by phase and shows which tools call which (solid arrows = direct call, dashed
arrows = automatic trigger after another tool's output).

```
                         ┌─────────────────────────────────────────────────┐
                         │        session_cli.py (CLI dispatch)            │
                         │  -start -next -prev -try -chain -checkpoint     │
                         │  -replay -status -show-proof -write-back -verify│
                         └──────────────┬──────────────────────────────────┘
                                        │ (every -next/-chain commit)
                                        ▼
                         ┌─────────────────────────────────────────────────┐
                         │   AUTO-* hook pipeline (fires unbidden)         │
                         │   [AUTO-KB] [AUTO-DIFF] [AUTO-PIVOT]            │
                         │   [AUTO-PIVOT-VERIFIED] [AUTO-PIVOT-CALL-READY] │
                         │   [AUTO-BRIDGE-SUGGEST] [AUTO-SIG]              │
                         └────┬─────────┬──────────┬──────────┬────────────┘
                              │         │          │          │
        ┌─────────────────────┘         │          │          └────────────────┐
        │ (state lifecycle)             │          │                           │
        ▼                               ▼          ▼                           ▼
  ┌─────────────┐    ┌────────────────────────┐  ┌─────────────────┐  ┌────────────────┐
  │ daemon_     │    │  goal/error analysis   │  │ context/library │  │ proof          │
  │ backend     │    │  -goal-info            │  │  search         │  │ construction   │
  │  ↓          │    │   ├─▶ -goal-patterns   │  │  -search        │  │  -inv-from-    │
  │ ec_daemon_  │    │   └─▶ ec_def_resolver  │  │  -clones        │  │   lemma        │
  │ client      │    │  -diagnose             │  │  -sig           │  │  -lemma        │
  │  ↓          │    │  -align (swap_align)   │  │  -file-index    │  │   (lemma_      │
  │ ec_daemon   │    │  -swap-search          │  │  -bridge-lemmas │  │    extract)    │
  │  ↓          │    │  -suggest-close        │  │  -bridge-probe ─┼──┐             
  │ easycrypt   │    │  -tactic-forms         │  │   (uses daemon) │  │             
  │ -emacs      │    │  -subgoal-gap          │  └─────────────────┘  │             
  └─────┬───────┘    │   ├─default: parse own │                       │             
        │            │   │  pre/post          │                       │             
        │ (used by   │   └─--against-lemma:   │                       │             
        │ AUTO-*-    │     reads source via   │                       │             
        │ VERIFIED,  │     parse_named_equivs │                       │             
        │ -try,      │                        │                       │             
        │ -chain,    │  Support libs:         │                       │             
        │ -bridge-   │   ec_goal_parser       │                       │             
        │ probe,     │   ec_goal_patterns     │                       │             
        │ -swap-     │   ec_diagnose          │                       │             
        │ search)    │   swap_align           │                       │             
        │            │   ec_tactic_forms      │                       │             
        │            │   subgoal_gap          │                       │             
        │            │   ec_def_resolver  ◀───┼───[AUTO-DEF lookup]───┘             
        │            │   ec_pr_path_diff   ───┼──▶ used by AUTO-DIFF, AUTO-PIVOT,
        │            │                        │      AUTO-BRIDGE-SUGGEST
        │            └────────────────────────┘
        │
        └──▶ daemon-verifies candidate tactics for AUTO-PIVOT-VERIFIED,
             AUTO-PIVOT-CALL-READY, AUTO-BRIDGE-SUGGEST, -bridge-probe.

Phase legend:
  • state lifecycle      — -start / -next / -prev / -try / -chain / -checkpoint /
                           -replay / -status / -show-proof / -write-back / -verify
  • goal/error analysis  — inspect current goal, classify errors, surface gaps
  • context/library      — find lemmas, signatures, file indexes, bridges
  • proof construction   — invariant templates, lemma extraction
  • automatic AUTO-*     — hook pipeline that fires on every commit

Cross-tool wiring (key non-obvious calls):
  • -goal-info  ─auto─▶  -goal-patterns           (pattern catalog match)
  • -goal-info  ─auto─▶  ec_def_resolver.resolve_defs_in_goal
                                                   (yields [DEFS REFERENCED IN GOAL])
  • -bridge-probe         uses daemon.bridge_probe RPC
  • -subgoal-gap --against-lemma  reads .ec source via parse_named_equivs
                                  in subgoal_gap.py
  • AUTO-PIVOT-VERIFIED   uses daemon.try_tactic / try_chain to filter candidates
  • AUTO-BRIDGE-SUGGEST   uses daemon.bridge_probe + session_meta.json narrative
  • AUTO-SIG              uses ec_search.sig_lookup on the failing lemma name
```

---

## Architecture

```
    LLM prover
        │  (issues -foo command, reads stdout)
        ▼
  ┌─────────────────────┐
  │   session_cli.py    │  ← backend/human-debug CLI
  └──────────┬──────────┘
             │
     ┌───────┴───────┐
     │               │
     ▼               ▼
  ┌──────────┐   ┌─────────────────┐
  │ subprocess│   │ daemon_backend  │  ← fast-path via persistent EC
  │  (legacy) │   │   (preferred)   │
  └──────────┘   └────────┬────────┘
                          │ Unix socket
                          ▼
                 ┌─────────────────┐
                 │   ec_daemon.py  │  ← persistent EC subprocess pool
                 │ (one per proof) │
                 └────────┬────────┘
                          │ pexpect
                          ▼
                     easycrypt -emacs

On every `-next` commit, the session runtime runs a fixed hook pipeline:
  1. [AUTO-KB]               — on structural tactic failure, surface KB patterns
  2. [AUTO-DIFF]             — on success, render program/Pr-expression alignment
  3. [AUTO-PIVOT]            — on success, list applicable pre-declared lemmas
  4. [AUTO-PIVOT-VERIFIED]   — if daemon available, verify each pivot plan against the current goal
  5. [AUTO-PIVOT-CALL-READY] — identify lemmas where `call <name>.` works directly
  6. [AUTO-BRIDGE-SUGGEST]   — for Pr[A]=Pr[B] goals, emit daemon-verified pasteable rewrites
  7. [AUTO-SIG]              — on `apply`/`rewrite` failure referencing an unknown lemma, dump its signature
```

---

## 1. Backend Session Tools (via `session_cli.py`)

### 1.1 Session lifecycle

| Flag | Purpose |
|------|---------|
| `-start [-f FILE] [-I DIR] [-lemma NAME]` | Start a new session; optionally load .ec context and target a specific lemma. |
| `-next -c 'TACTIC.'` | Commit a tactic permanently. |
| `-prev` | Undo the last committed tactic. |
| `-try -c 'TACTIC.'` | Test a tactic speculatively; auto-undo after reporting whether EC accepted it. State unchanged. |
| `-chain [--keep-on-fail] -c 'T1. T2. T3.'` | Apply tactics sequentially; stop on first error. By default rolls back the entire prefix on any failure; `--keep-on-fail` keeps the accepted prefix. |
| `-checkpoint NAME` | Save a named snapshot of session state (prefix + proof state). |
| `-replay NAME` | Restore session from a named checkpoint. |
| `-status` | Print session metadata: lemma, tactics applied, daemon availability. |
| `-show-proof LEMMA` | Print the proof body of an already-proved lemma in the .ec file. |

**Why session management is needed.** Without persistence, each tactic attempt would need to re-run `easycrypt <file.ec>` from scratch (~5–30 s). With the session layer each tactic takes ~1 s (subprocess fallback) or ~50–100 ms (daemon fast-path).

**Critical flags built from prover observations:**
- `[NO_PROGRESS]` detection — LLMs often commit tactics that EC accepts but don't change the goal. Without this flag, the agent thinks it's progressing while walking a dead path.
- `[GOAL_CLOSED]` / `[ALL_GOALS_CLOSED]` — LLMs cannot reliably count remaining goals from raw EC output.
- `--deltas-only` — shows only the change since the last tactic. Without it, the agent sees 500+ lines of accumulated output and confuses which part is the current goal.

#### Per-flag examples

**`-start -f chacha_poly.ec -lemma step1`**
```
[OK] session started at .ec_session_step1
  loaded:  eval/examples/ChaChaPoly/chacha_poly.ec  (744 lines)
  lemma:   step1
  context: 12 modules, 3 clones, 47 lemmas (proved 31, admit 0, open 16)
  daemon:  available (socket=/tmp/ec_daemon.sock, pid=84321)
Current goal:
  &m: ...
  Pr[CCA(RealOrcls(ChaChaPoly), G1).main() @ &m : res] =
  Pr[CCA(IndBlock, G2).main() @ &m : res]
```

**`-next -c 'proc.'`**
```
[OK] proc.
[GOAL_OPEN] 1 goal remaining
  pre  = ={glob A, glob G1}
  post = ={res, glob A}
  body lhs (24 stmts) | body rhs (24 stmts)
[AUTO-DIFF] pRHL program alignment: 22 identical, 2 differing, 0 side-only
[AUTO-PIVOT-VERIFIED] 1 actionable lemma: pr_CCP_OCCP (DIRECT)
```

**`-prev`**
```
[OK] reverted: proc.
  prefix: 0 tactics applied
  goal:   restored to pre-proc Pr[A]=Pr[B] form
```

**`-try -c 'sim.'`**

**Compiler-philosophy rating**: B (tool, not hint) (When ❌ generic pattern: pure execution; Look at ✅ context retrieval: runs on current state; Try ✅ instantiated tactic: reports accepted/error with `[TRY] WARNING: no progress` etc.).

```
[TRY] sim.
[REJECTED] no progress on goal — programs differ at call sites
  speculatively undone; session state unchanged.
```

**`-chain -c 'proc. inline *. wp. call (_: Inv).'`**

**Compiler-philosophy rating**: B (tool, not hint) (When ❌ generic pattern: pure execution; Look at ✅ context retrieval: runs on current state; Try ✅ instantiated tactic: reports accepted/error with `[TRY] WARNING: no progress` etc.).

```
[CHAIN] 4 tactics, stop-on-error mode
  ✓ proc.            (1 goal open)
  ✓ inline *.        (1 goal open, body expanded to 87 stmts)
  ✓ wp.              (1 goal open)
  ✗ call (_: Inv).   SYNTAX: Inv not in scope
[ROLLED-BACK] all 3 accepted tactics undone (default rollback policy).
  use --keep-on-fail to retain the accepted prefix.
```

**`-checkpoint pre-pivot`**
```
[OK] checkpoint saved: pre-pivot
  prefix:  3 tactics
  hash:    a1b2c3d4
```

**`-replay pre-pivot`**
```
[OK] restored from checkpoint: pre-pivot
  prefix:  3 tactics replayed
  daemon:  resynced (215 ms)
```

**`-status`**
```
session:  .ec_session_step1
lemma:    step1  (file=chacha_poly.ec)
prefix:   12 tactics applied (0 admits)
goal:     OPEN  (1 of 1 ambient subgoal)
daemon:   available, 4 active sessions on socket
checkpoints: pre-pivot (3 tac), post-rewrite (8 tac)
```

**`-show-proof step2_1`**
```
lemma step2_1 &m : Pr[...] = Pr[...].
proof.
  byequiv => //; proc; inline *.
  swap{1} 3 -1; wp.
  call (CCA_CPA_UFCMA St A G1 G2 &m).
  by auto.
qed.
```

---

### 1.2 Goal / error analysis

| Flag | Tool module | Purpose |
|------|-------------|---------|
| `-goal-info` | `ec_goal_parser.py` | Classify the goal (pRHL, eager, hoare, phoare, ambient, probability) and emit parser-level structural facts. Includes `-goal-patterns` output automatically. It does not expose a `suggested_tactics` field; tactic choices should come from ProofIR/ProgramIR, diagnostics, or EC-backed probes. |
| `-goal-json` | `session_projection.py` / `ec_native_state.py` | Emit the stable goal-state adapter contract with provenance. It prefers EC-native goal artifacts when present; otherwise the payload is explicitly labeled `pretty_goal_text` / `pretty_text_fallback`. |
| `-program-json` | `ec_program_ir.py` / `ec_native_state.py` | Emit the stable program-shape adapter contract with provenance. It prefers EC-native program AST artifacts when present; otherwise statement extraction is explicitly labeled `pretty_program_text` / `pretty_text_fallback`. |
| `-goal-patterns` | `ec_goal_patterns.py` **(new)** | Match the current goal against a KB pattern catalog (~8–12 detectors covering P20 pRHL-with-renamed-globals, byphoare_split, islossless, while-without-invariant, etc.). Emits `[KB]` blocks with advice + doc refs. |
| `-diagnose` | `ec_diagnose.py` | Classify the latest error against a database of ~150 known EC error patterns (built from 29 proof attempts). Tags each error as **execution-level** (retry with different args) or **strategy-level** (wrong tactic entirely, switch approach). ToolView guidance is a `strategy_hint` with diagnostic epistemic status; the fix has not been executed yet. |
| `-align` | `swap_align.py` | Parse the two-column pRHL goal, identify corresponding statements (by procedure for CALLs, by distribution for SAMPLEs), and emit explicit epistemic status: `static_candidate_uncertified_by_ec` for static swap candidates, `static_blocked_uncertified` for conservative CALL/dependency barriers. A blocked candidate is not an EC rejection and not a proof of impossibility; probe with `-try` or use `-swap-search` for EC-backed search. |
| `-swap-search [--max-swap-attempts N]` | `swap_search.py` | Brute-force valid swap sequences using the daemon for per-candidate probing. Returns the longest valid sequence found and applies it. |
| `-suggest-close` | `ec_suggest.py` | When the current goal is a pure logic/algebra formula, suggest closing tactics (`rewrite`, `ring`, `algebra`, SMT hints). Concrete tactics are `probe_tactic` / `static_candidate_uncertified_by_ec`; templates with `...` are `strategy_hint`. |
| `-tactic-forms NAME` | `ec_tactic_forms.py` **(new)** | Print the valid argument forms for a tactic and the use-cases / common mistakes for each form. Covered tactics include `call`, `ecall`, `apply`, `rewrite`, `byequiv`, `conseq`, `while`, `sim`, `sp`, `seq`, `wp`, `swap`, `rcondt`, `rcondf`, `rnd`, `eager`, `transitivity`, and `congr`. Use BEFORE writing a non-trivial tactic, or after a SYNTAX error from arity/form mismatch. |
| `-subgoal-gap [--against-lemma 'NAME args...']` | `subgoal_gap.py` **(new)** | Decompose a pRHL goal's pre/post into conjuncts and surface the structural gap. Default mode: classify each post conjunct as PROVED-BY-PRE / LOOSE-MATCH / PROVIDED-BY-NEXT-CALL / MISSING (the last one is the actionable gap). With `--against-lemma 'equ_X arg1 arg2 ...'`: project the lemma's PRE against your current state — answers "if I `call`/`ecall LEMMA` here, which of its pre-conditions are already covered?" Use when stuck after a structural tactic produced multiple ambient subgoals — distinguishes "pre-state alignment is wrong" from "lemma is wrong" so you don't undo a route that is actually correct. See § 1.2.1 for an example. |

**Why goal classification was needed.** The #1 failure mode observed was *wrong tactic for goal type*. The prover would try `swap` on an eager goal (needs `eager proc`), or `proc` on an ambient goal (needs `rewrite`/`smt`). LLMs cannot reliably distinguish goal types from raw EC output because the visual formats are similar.

#### Per-flag examples

**`-goal-info`**

**Compiler-philosophy rating**: B+ (When ✅ generic pattern: any goal; Look at ✅ context retrieval: classify goal type + extract fields (addend_equiv_candidates etc.); Try 🟡 instantiated tactic: emits `recommended_tactics` but doesn't account for EC quirks (abstract module etc.)).

```
[GOAL-INFO] kind=pRHL  |  1 subgoal open  |  ambient depth 0
  pre  = ={glob A, glob G1} /\ ={Mem.k}
  post = ={res, glob A}
  body lhs (24 stmts):  RealOrcls(ChaChaPoly).init() ; b <@ A(...).main()
  body rhs (24 stmts):  IndBlock.init()             ; b <@ D(A, IndBlock).guess()

  Recommended families:  byequiv | proc + sim | proc + call (_: Inv)
  Anti-recommendations:  rewrite (this is not an ambient goal)

[KB] P20: pRHL with renamed module-qualified globals
  → `sim.` will fail silently. Use `call (_: OCC.gs{1} = StLSke.gs{2})`.
  refs: decision_tree.md P20

[DEFS REFERENCED IN GOAL]

SplitD.test (op, chacha_poly.ec:412):
  = fun (p : nonce * C.counter) => C.toint p.`2 = 0

C.counter (subtype, chacha_poly.ec:118):
  = { i : int | 0 <= i < max_counter + 1 }
    rename "ofint", "toint"
  Derived lemmas (subtype convention):
    C.ofintdK         : forall x, 0 <= x < max_counter + 1 => C.toint (C.ofintd x) = x
    C.toint_ofintd    : forall x, C.toint (C.ofintd x) = if 0 <= x < max_counter + 1 then x else C.toint witness

max_counter (op, chacha_poly.ec:115):
  : int
gt0_max_counter (axiom, chacha_poly.ec:117):
  : 0 < max_counter
```

The `[KB]` block is the auto-triggered output of `-goal-patterns` (see below); the `[DEFS REFERENCED IN GOAL]` block is the auto-triggered output of `ec_def_resolver` (see § 1.2.2).

**`-goal-patterns`**
```
[KB] 2 matching pattern(s)
  P20: pRHL where programs use different module-qualified globals
    → `sim.` will silently fail. Use `call (_: OCC.gs{1} = StLSke.gs{2} /\ ={Mem.k})`.
    refs: decision_tree.md P20
  P07: while loop without explicit invariant
    → `auto` won't close. Need `while (Inv) (Variant)` with measure decreasing.
    refs: decision_tree.md P07
```

**`-diagnose`**
```
[DIAGNOSE] last error: "swap_not_independent: variable c is read at position 5"
  category:        EXECUTION-LEVEL
  classifier:      swap.dependency_violation
  cause:           swap{1} 3 5 attempts to move statement 3 past statement 5,
                   but statement 5 reads `c` which is written at statement 3.
  fix:             insert a `wp` before the swap, OR pick a different swap range.
  related KB:      P12 (swap with side-effect dependency)
```

**`-align`**

**Compiler-philosophy rating**: A+ (When ✅ generic pattern: pRHL goal after `inline *`; Look at ✅ context retrieval: parse both sides + dependency analysis; Try ✅ instantiated tactic: outputs "swap{1} 4 -2." with concrete numbers).

```
[ALIGN] pRHL two-column alignment (24 stmts each side)
   1. IDENTICAL  Mem.k <$ dkey
   2. IDENTICAL  c <$ dnonce
   3. DIFFER     RealOrcls(ChaChaPoly).enc(...) ~ IndBlock.enc(...)
   4. SIDE-ONLY  (RHS) extra wp-stmt: log <- (n, c) :: log
   ...
  Recommended:
    swap{2} 4 -1     ; pull RHS log update before the differing call
    call (_: Inv)    ; on row 3 with Inv linking ChaChaPoly.gs vs IndBlock.gs
```

**`-swap-search --max-swap-attempts 12`**
```
[SWAP-SEARCH] daemon-probing valid swap sequences (depth ≤ 12)
  candidate 1:  swap{1} 3 -1.                       ✓ accepted, 1 stmt aligned
  candidate 2:  swap{1} 3 -1; swap{2} 5 -2.         ✓ accepted, 3 stmts aligned
  candidate 3:  swap{1} 3 -1; swap{2} 5 -2; wp.     ✓ accepted, 4 stmts aligned
  ...
  best sequence (4 tactics, 6 stmts aligned):
    swap{1} 3 -1; swap{2} 5 -2; wp; sp 1 1.
  applied to session.
```

**`-suggest-close`**
```
[SUGGEST-CLOSE] goal is ambient (`forall n, 0 <= n => P n`)
  Static candidates (not EC-verified yet; probe with -try):
    1. by smt(@Int gt0_max_counter).
    2. apply gt0_max_counter; smt().
    3. rewrite /max_counter; smt().
  ToolView: action_type=probe_tactic, epistemic_status=static_candidate_uncertified_by_ec
```

**`-tactic-forms call`**

**Compiler-philosophy rating**: C+ static ref (When ✅ generic pattern: when agent wants to use a tactic; Look at ❌ context retrieval: static doc, doesn't read current goal; Try 🟡 instantiated tactic: examples are hardcoded, not instantiated to current goal).

```
[TACTIC-FORMS] call — 4 valid forms
  1. call LEMMA.
       use-when:   a named equiv lemma proves this exact procedure correspondence
       example:    call CCA_CPA_UFCMA.
       mistake:    falling back to (_: Inv) when a named lemma exists, fanning
                   out subgoals per oracle
  2. call (_: Inv).
       use-when:   no named lemma; specify a relational invariant by hand
       example:    call (_: ={glob A, Mem.k} /\ OCC.gs{1} = StL.gs{2}).
       mistake:    using when a named equiv lemma is available (form 1 is cheaper)
  3. call (_: bad, Inv).
       use-when:   need a "bad" event escape clause for upto-bad reasoning
       example:    call (_: BadE, ={glob A}).
  4. call (LEMMA arg1 arg2 &m).
       use-when:   the lemma is section-exported and needs explicit module args
       example:    call (CCA_CPA_UFCMA St A G1 G2 &m).
       mistake:    omitting the module args outside the section
```

#### 1.2.1 `-subgoal-gap` example: rescuing the "complex side conditions" pivot

**Compiler-philosophy rating**: A- (When ✅ generic pattern: ambient residue / pivot candidate; Look at ✅ context retrieval: project lemma vs current state; Try 🟡 instantiated tactic: reports mismatch + SHAPE MISMATCH warning; concrete fix-it generic).

**Failure pattern this addresses.** ChaChaPoly `step3` Run 8 (2026-04-27): Tree-0.1 reached the right `equ_cc` call frontier and partially discharged the ambient residue, then judged the remaining precondition goals as "complex side conditions" and **voluntarily undid the entire route** at minute 35. The route was correct; the agent's pivot was premature. Current ProofIR prefers the less syntax-sensitive `exlim ...; call (equ_cc ...)` elaboration when the lemma parameters come from side-qualified program expressions.

The **structural reason** for the 4 unclosed subgoals was: equ_cc's PRE has 7 conjuncts; some are substitution-driven (auto-resolved at apply time), some need a definition unfold (`check_plaintext`), and some are about local-functor-parameter map names that look different from the externally-qualified names in the agent's invariant. None are "the lemma is wrong"; all are "pre-state alignment".

**What the tool surfaces.** Run at the same stuck point, `-subgoal-gap --against-lemma 'equ_cc n{1} ROin.m{1} ROout.m{1}'` produces:

```
[LEMMA-PRE RESIDUAL]  Target: equ_cc (declared at chacha_poly.ec:1306)
  Params:  n0 mr0 ms0
  Witnesses: n0=n{1} mr0=ROin.m{1} ms0=ROout.m{1}

  Lemma LHS: ChaCha(CCRO(SplitD.RO_DOM(SplitC1.RO_Pair(SplitC2.RO_Pair(ROin, ROout), ...
  Lemma RHS: EncRnd.cc

  Coverage of equ_cc's PRE (7 conjuncts):

    ✓ COVERED   ROin.m{1} = ROin.m{1}
    ✓ COVERED   ROout.m{1} = ROout.m{1}
    ~ LOOSE     arg{2} = (arg.`2, arg.`3){1}
                References `arg{1}`/`arg{2}` — resolved by the typed call's argument
                substitution (auto-handled if your call args match the procedure
                signature).
    ~ LOOSE     arg{2}.`1 = n{1}
                References `arg{1}`/`arg{2}` — resolved by ecall's argument substitution.
    ~ LOOSE     size arg{1}.`3 <= max_cipher_size
                References `arg{1}`/`arg{2}` — resolved by ecall's argument substitution.
    ~ LOOSE     !n{1} \in BNR.lenc{1}
                Pre has `check_plaintext` over same container — its definition
                unfold yields `!(_ \in _)`. After ecall, try `rewrite /check_plaintext`.
    ~ LOOSE     (forall n c, (n,c) \in ROF.m => n \in BNR.lenc){1}
                Possible module-qualification alias: lemma uses `ROF.m`, your
                context has `SplitD.ROF.RO.m` (same container, dot-parts overlap).
                If they ARE aliases (check clone scope), this matches; otherwise
                extend invariant.

  Verdict: 2 covered, 5 loose, 0 missing
```

**The `0 missing` verdict is the load-bearing signal.** It tells the agent: lemma is correct, every pre-condition can be discharged by some combination of substitution / unfold / module-alias resolution. Do not undo. Try `move=> /> *; rewrite /check_plaintext; smt(...)`.

**Design principle exercised.** The output names *what is missing* and *where it could come from* (substitution, definition unfold, module-alias). It does not say "do X then Y". The agent reads the structural inventory and chooses the action. Information supports reasoning, doesn't replace it.

#### 1.2.2 `[DEFS REFERENCED IN GOAL]` — context-driven definition lookup

**Compiler-philosophy rating**: B+ (When ✅ generic pattern: any goal; Look at ✅ context retrieval: parse op/lemma names from goal text + lookup body; Try ❌ instantiated tactic: surfaces definitions but doesn't say "try `rewrite /op` or `smt(LEMMA)`").

**Trigger.** Appended automatically to every `-goal-info` invocation **only when the loaded source file declares ≥1 op/pred/abbrev/axiom/subtype whose name appears in the current goal**. If the goal is a pure ambient formula or its identifiers are all from the EC standard library, the section is silently omitted (no false-positive noise).

**Implementation.** `core/easycrypt/ec_def_resolver.py`. The resolver walks the loaded `.ec` source, extracts every named declaration with its position and form (op / pred / abbrev / axiom / subtype), and intersects that set against the identifiers parsed out of the current goal.

**Shape.** One block per referenced definition, in source order. Each entry shows the kind, the file location, and the declaration body. For `subtype` declarations the resolver additionally synthesizes the standard derived-lemma pair (`<name>dK` and `toint_<name>d`) — these are emitted by EC's subtype mechanism but never appear in source, so the agent would otherwise have to guess they exist.

**Why it matters.** Repeated stuck-point in ChaChaPoly `step3`: the goal contained `SplitD.test` and `C.toint p.`2`, but the agent had no easy way to learn that `SplitD.test` was a one-line definition unfoldable by `rewrite /SplitD.test`, or that `C.counter`'s subtype framework auto-generates `C.ofintdK`. Without this hook the agent would either (a) `-search SplitD` and read 30 unrelated matches, or (b) pattern-match guess and fail. The hook surfaces exactly the definitions that are *demonstrably referenced in the current goal*.

**Example output (ChaChaPoly step3, ambient subgoal after `byequiv => //; proc; inline *.`):**

```
[DEFS REFERENCED IN GOAL]

SplitD.test (op, chacha_poly.ec:412):
  = fun (p : nonce * C.counter) => C.toint p.`2 = 0

C.counter (subtype, chacha_poly.ec:118):
  = { i : int | 0 <= i < max_counter + 1 }
    rename "ofint", "toint"
  Derived lemmas (subtype convention):
    C.ofintdK         : forall x, 0 <= x < max_counter + 1 => C.toint (C.ofintd x) = x
    C.toint_ofintd    : forall x, C.toint (C.ofintd x) = if 0 <= x < max_counter + 1 then x else C.toint witness

max_counter (op, chacha_poly.ec:115):
  : int
gt0_max_counter (axiom, chacha_poly.ec:117):
  : 0 < max_counter
```

Read this as: *the current goal mentions `SplitD.test`, `C.counter` (via `C.toint`), `max_counter`, and `gt0_max_counter`; here is each one's declaration verbatim, plus the derived lemmas the subtype mechanism auto-creates*. From there, the agent can compose `rewrite /SplitD.test` and `apply C.ofintdK` directly without any further lookup.

---

### 1.3 Context / library search

| Flag | Tool module | Purpose |
|------|-------------|---------|
| `-search QUERY [--max N]` | `ec_search.py` | Regex-search EC standard library + loaded context for lemma/axiom/op names. |
| `-lemma-hints` | `ec_lemma_lookup.py` | Retrieve stdlib lemmas by operators visible in the current goal. ToolView emits `inspection_action` recommendations (`-sig NAME`) rather than direct apply/rewrite tactics, because retrieval alone does not prove scope or applicability. |
| `-clones` | `ec_search.py` | List all `clone` declarations and their lemma renamings. Critical because EC's clone mechanism renames lemmas (e.g., `dunifin_ll` becomes `dbool_ll` after a clone). |
| `-sig LEMMA` | `ec_search.py` | Print the full declaration of a lemma: arity, implicit args, module parameters, section-scope args. **The first-line defense against flailing on `apply`/`rewrite`.** |
| `-file-index FILE` | `ec_file_index.py` | Parse an .ec file and produce a structured outline: types, operators, modules, clones, lemmas with proof status. |
| `-bridge-lemmas` | `ec_bridge_lemmas.py` | For an `equiv L.proc ~ R.proc` goal, scan the loaded context for equiv lemmas forming a transitivity chain between them. Concrete output is `probe_tactic`; templates with placeholders are `strategy_hint`. |
| `-bridge-probe BRIDGE_STMT` **(new)** | session_cli + daemon | Given `BRIDGE_STMT` = `Pr[A] = Pr[B]`, test via daemon whether a short sim-family chain closes it. Accepted probes emit `runnable_tactic` with `confidence=verified`; rejected probes emit decompose/avoid guidance. |

#### Per-flag examples

**`-search 'pr_CCP'`**

**Compiler-philosophy rating**: C context-only (When ❌ generic pattern: pure query; Look at ✅ context retrieval: context-driven (search theories); Try ❌ instantiated tactic: doesn't suggest tactic).

```
[SEARCH] regex /pr_CCP/  (3 hits in loaded context, 0 in stdlib)
  chacha_poly.ec:1187   lemma OpCCinit.pr_CCP_OCCP (I <: Init) (A <: Adv) &m :
                          Pr[CCP(I, A).main() @ &m : res] =
                          Pr[OCCP(I, A).main() @ &m : res].
  chacha_poly.ec:1224   lemma pr_CCP_FinRO &m : ...
  chacha_poly.ec:1271   lemma pr_CCP_eager &m : ...
```

**`-clones`**

**Compiler-philosophy rating**: C context-only (When ❌ generic pattern: pure query; Look at ✅ context retrieval: context-driven (list clones); Try ❌ instantiated tactic: doesn't suggest tactic).

```
[CLONES] 5 clone declarations in loaded context
  1. clone include OpCCinit as OCC with type Init <- I_stateless.
       renames: pr_CCP_OCCP → OCC.pr_CCP_OCCP
  2. clone include FinRO as IFinRO with op n <- max_counter + 1.
       renames: dunifin_ll → dbool_ll, FinT.card → max_counter
  3. clone SplitC1 as SC1 with type t1 <- nonce, type t2 <- counter.
       (no renames)
  ...
```

**`-sig CCA_CPA_UFCMA`**

**Compiler-philosophy rating**: C context-only (When ❌ generic pattern: pure query; Look at ✅ context retrieval: context-driven (pull signature); Try ❌ instantiated tactic: doesn't suggest tactic).

```
[SIG] CCA_CPA_UFCMA (chacha_poly.ec:1306)
  declare module St : StatefulOrcl.
  declare module A  : Adv {-St}.
  module G1 = ChaChaPoly(St).
  module G2 = IndBlock(St).
  lemma CCA_CPA_UFCMA (St <: StatefulOrcl) (A <: Adv {-St})
                      (G1 <: Game) (G2 <: Game) &m :
        Pr[CCA(G1).main() @ &m : res] = Pr[CCA(G2).main() @ &m : res].
  apply form (outside section): apply (CCA_CPA_UFCMA St A G1 G2 &m).
  call form  (outside section): call  (CCA_CPA_UFCMA St A G1 G2 &m).
```

**`-file-index chacha_poly.ec`**
```
[FILE-INDEX] chacha_poly.ec  (744 lines, 12 modules, 5 clones, 47 lemmas)
  types:        nonce, counter, key, plaintext, ciphertext
  operators:    max_counter, max_cipher_size, check_plaintext
  axioms:       gt0_max_counter
  modules:      ChaChaPoly, OChaChaPoly, IndBlock, RealOrcls, CCRO, ...
  clones:       OpCCinit→OCC, FinRO→IFinRO, SplitC1→SC1, SplitC2→SC2, SplitD
  lemmas:       47 total
                  proved:  31  (step1, step2_1, step2_2, ...)
                  open:    16  (step3, step4_1, step4_2, ...)
                  admit:    0
```

**`-bridge-lemmas`**
```
[BRIDGE-LEMMAS] equiv RealOrcls(ChaChaPoly).enc ~ IndBlock.enc
  Available transitivity hops (3 found):
    1. equ_chacha    : RealOrcls(ChaChaPoly).enc ~ OChaChaPoly(I_stateless).enc
    2. equ_occ_split : OChaChaPoly(I_stateless).enc ~ SplitC1.RO_Pair(...).enc
    3. equ_split_ind : SplitC1.RO_Pair(...).enc ~ IndBlock.enc
  Pasteable transitivity template (chains all 3):
    transitivity OChaChaPoly(I_stateless).enc.
      + by call equ_chacha.
    transitivity SplitC1.RO_Pair(...).enc.
      + by call equ_occ_split.
    by call equ_split_ind.
```

**`-bridge-probe 'Pr[CCA(G1).main() @ &m : res] = Pr[CCA(G2).main() @ &m : res]'`**

**Compiler-philosophy rating**: A+ (When ✅ generic pattern: preparing `have ->: Pr=Pr`; Look at ✅ context retrieval: try sim/byequiv closer to verify; Try ✅ instantiated tactic: "use `have -> : <stmt>. <closer>`" with closer name).

```
[BRIDGE-PROBE] daemon-testing 1-step and 2-step sim-family closures
  1-step:
    byequiv => //; proc; sim.                          ✗ rejected (programs differ)
    byequiv => //; proc; inline *; sim.                ✗ rejected
    apply (CCA_CPA_UFCMA St A G1 G2 &m).               ✓ accepted
  2-step (rewrite + closer):
    rewrite -(OpCCinit.pr_CCP_OCCP I_stateless G1 &m).
      + closes residual: byequiv => //; proc; sim.     ✓ accepted
  Best: apply (CCA_CPA_UFCMA St A G1 G2 &m).  (1 tactic)
```

---

### 1.4 Proof construction helpers

| Flag | Tool module | Purpose |
|------|-------------|---------|
| `-inv-from-lemma LEMMA` | `ec_inv_from_lemma.py` | Extract the precondition of a local `equiv` lemma and format it as a `call (_: bad, Inv)` template, eliminating hand-copy errors. Concrete templates are `probe_tactic` (`context_extracted_candidate_uncertified_by_ec`); placeholder templates remain `strategy_hint`. |
| `-lemma LEMMA` | `lemma_extract.py` | Extract a section-local lemma into a standalone .ec file with `declare module`/`declare axiom` context and sibling lemmas replaced by `admit.`. Required because section-internal lemmas can't otherwise be proved interactively. |
| `-write-back` | session_cli | Write the current committed proof back into the source .ec file at the lemma site. |
| `-verify LEMMA` | session_cli | Type-check a lemma's proof; rejects any `admit.` at depth 0 (enforces the no-admit rule in `CLAUDE.md`). |

#### Per-flag examples

**`-inv-from-lemma equ_cc`**

**Compiler-philosophy rating**: A+ (When ✅ generic pattern: preparing `call (_: bad, Inv)`; Look at ✅ context retrieval: extract invariant template from lemma's pre; Try ✅ instantiated tactic: outputs `call (_: bad, ={...})` template).

```
[INV-FROM-LEMMA] equ_cc (declared at chacha_poly.ec:1306)
  Pre-conditions extracted (7 conjuncts):
    arg{2} = (arg.`2, arg.`3){1}
    arg{2}.`1 = n{1}
    size arg{1}.`3 <= max_cipher_size
    !n{1} \in BNR.lenc{1}
    forall n c, (n,c) \in ROF.m{1} => n \in BNR.lenc{1}
    ROin.m{1} = ROin.m{1}
    ROout.m{1} = ROout.m{1}
  Pasteable call template:
    call (_:    !n{1} \in BNR.lenc{1}
             /\ (forall n c, (n,c) \in ROF.m{1} => n \in BNR.lenc{1})
             /\ ={ROin.m, ROout.m}).
```

**`-lemma step3`**
```
[LEMMA-EXTRACT] step3
  Source:  chacha_poly.ec:1487 (inside section CCABody)
  Output:  /tmp/ec_extract_step3.ec  (218 lines)
    declare module St : StatefulOrcl.
    declare module A  : Adv {-St}.
    declare axiom A_ll : islossless A(...).main.
    (* ... 31 sibling lemmas replaced by `admit.` ... *)
    lemma step3 &m : Pr[...] = Pr[...].
    proof.
      (* extracted, ready to be proved interactively *)
    qed.
  Build OK: easycrypt /tmp/ec_extract_step3.ec  ✓
```

**`-write-back`**
```
[WRITE-BACK] step1
  current proof: 12 tactics, 0 admits
  target file:   chacha_poly.ec
  target lemma:  step1 (line 887)
  written 12 lines into chacha_poly.ec:887-899  ✓
  re-typecheck:  easycrypt chacha_poly.ec       ✓ (3.1 s)
```

**`-verify step1`**
```
[VERIFY] step1
  pre-check (admit scan):  0 admits at depth 0  ✓
  type-check:              easycrypt chacha_poly.ec  ✓ (3.1 s)
  post-check (admit scan): 0 admits in body     ✓
  Verdict: PROVED
```

---

## 2. Automatic Diagnostic Hooks (the `AUTO-*` block family)

**These are the most important recent additions.** Unlike the flags above, auto-hooks fire unbidden on every `-next` / `-chain` commit. They transform passive-observation tools into active-guidance signals. Each hook is dedup'd by goal-shape to avoid repetition across a session.

### 2.1 `[AUTO-KB]` — KB pattern matching on failure

**Compiler-philosophy rating**: A+ (When ✅ generic pattern: structural tactic + error / no-effect; Look at ✅ context retrieval: run KB pattern matcher on current goal; Try ✅ instantiated tactic: outputs KB pattern ID + explanation + recommended tactic).

**Trigger:** a structural tactic (`proc`, `inline`, `swap`, `rnd`, `wp`, `sp`, `auto`) fails.

**Action:** run `-goal-patterns` on the current goal and emit any matches with advice and doc references.

**Emits:**
```
[AUTO-KB] 1 matching pattern(s):
  [KB] P20: pRHL where programs use different module-qualified globals
    → `sim.` will silently fail. Use `call (_: OCC.gs{1} = StLSke.gs{2} /\ ={Mem.k})`
    refs: decision_tree.md P20
```

**Source:** `session_hooks.auto_kb_trigger` + `ec_goal_patterns.py`.

---

### 2.2 `[AUTO-DIFF]` — structural alignment of the current goal

**Compiler-philosophy rating**: A (When ✅ generic pattern: programs misaligned; Look at ✅ context retrieval: parse actual LHS/RHS, report row correspondence; Try 🟡 instantiated tactic: reports "row 12 / row 5 misaligned, consider `seq 12 5`" — only one form, no alternatives like `wp` to consume tail).

**Trigger:** any tactic succeeds.

**Action:** parse the goal and render a structural alignment — different renderers per goal type:

- **pRHL goals** → `program_alignment_diff()`: two-column table marking each row as **IDENTICAL**, **DIFFER**, or **SIDE-ONLY**, with functor-path diffs for differing call sites.
- **Probability goals** (`Pr[A] op Pr[B]`) → `probability_diff()`: walk the module trees, report every differing node and its path.
- **Eager goals** → `eager_diff()`: left/right procedure expression diff.

**Example output:**
```
[AUTO-DIFF] pRHL program alignment
  0 identical, 2 differing, 0 side-only (of 2 statements total)
    1. DIFFER: RealOrcls(ChaChaPoly).init() ~ IndBlock.init()
    2. DIFFER: b <@ A(RealOrcls(ChaChaPoly)).main() ~ b <@ D(A, IndBlock).guess()

  Statements DIFFER → sim alone won't suffice. Use `call (_: Inv)` at each
  differing call-site with an invariant linking the two modules' states.
```

**Source:** `session_hook_phases.AutoDiffPhase` + `ec_pr_path_diff.py`.

---

### 2.3 `[AUTO-PIVOT]` / `[AUTO-PIVOT-VERIFIED]` — applicable-lemma surfacing

**Compiler-philosophy rating**: A+ (When ✅ generic pattern: goal is Pr=Pr / Pr-bound; Look at ✅ context retrieval: scan file for equiv-shape lemmas + run `try_tactic('call NAME.')` to verify which apply; Try ✅ instantiated tactic: outputs "Run `-chain -c 'call <name>.'`" with concrete name).

**Trigger:** any tactic succeeds.

**Action:** cache a lemma inventory from the loaded .ec context once per session (via `extract_lemma_inventory()`); for every goal, score each lemma against the goal with `pivot_applicability()`, ranked:

| Tag | Meaning | Plan |
|-----|---------|------|
| **DIRECT** | module trees identical (modulo args) | `apply <lemma>.` |
| **ARG_DIFF** | trees identical; only args differ | `apply (<lemma> <args>).` |
| **UNFOLD** | pivot is more specific than goal; unfold definitions to expose match | `inline chain; apply <lemma>.` |
| **TOO_ABSTRACT** | pivot is strictly more general; needs `have :=` instantiation | hint only |
| **PR_CHECKPOINT** | Pr-level checkpoint whose raw endpoint does not match by one-step apply/rewrite | route context: inspect/build an intermediate Pr equality only if it matches and simplifies the visible endpoint |
| **NEEDS_INTERMEDIATE** | not one-step applicable on the raw wrapper | use after an explicit bridge or structural transform |

**Verification:** if the daemon is available, each `DIRECT`/`ARG_DIFF`/`UNFOLD` candidate is probed against the current goal via `try_tactic()` / `try_chain()`. Accepted candidates get the `/VERIFIED` suffix. Rejected candidates are suppressed (honest "nothing applies" beats a misleading offer).

**Example output:**
```
[AUTO-PIVOT-VERIFIED] actionable lemmas (checked against current goal):
  [DIRECT/VERIFIED] pr_CCP_OCCP — rewrite -(OpCCinit.pr_CCP_OCCP I_stateless G1 &m).
  [UNFOLD/VERIFIED] poly_mac1    — inline GenChaChaPoly(OCC(I_stateless)).enc; call poly_mac1.
```

**Additional pass — `[AUTO-PIVOT-CALL-READY]`:** for `equiv` goals, enumerates already-proven oracle-equivalence lemmas where `call <name>.` directly matches, and explains that `inline *` at this point would erase the call site.

**Example output (AUTO-PIVOT-CALL-READY):**
```
[AUTO-PIVOT-CALL-READY] 1 named equiv lemma matches the next call site:
  call UFCMA_genCC.   ← daemon-verified, closes the call goal directly
  NOTE: `inline *` here would expand the call site UFCMA_genCC targets,
        breaking the one-step closure. Apply `call UFCMA_genCC.` first.
```

**Source:** `session_hook_phases.PivotStrategyPhase` + `ec_pr_path_diff.pivot_applicability()`.

---

### 2.4 `[AUTO-BRIDGE-SUGGEST]` — daemon-verified Pr-layer rewrites

**Compiler-philosophy rating**: A+ (When ✅ generic pattern: goal hints `have ->: Pr=Pr` need; Look at ✅ context retrieval: scan narrative bridge_lemma + try_chain to verify; Try ✅ instantiated tactic: "Command: `-chain -c '<have>. <byequiv-closer>.'`" with concrete).

**Trigger:** tactic succeeds AND the goal is exactly `Pr[A] = Pr[B]`.

**Action:** consult `session_meta.json` (the narrative) for bridge lemmas and synthetic module bridges; enumerate typed-slot instantiations; daemon-verify each; surface only the accepted forms.

The narrative schema (produced by the annotator in `workflow/`) encodes each pivot with typed slots and `known_instances_in_file`, so the hook does **Cartesian product of in-file instances × daemon verification**:

```yaml
lemma: OpCCinit.pr_CCP_OCCP
rewrite_form: "rewrite -(OpCCinit.pr_CCP_OCCP <I> <A> &m)."
arg_types:
  <I>: { type: OpCCinit.Init, known_instances_in_file: [I_stateless, IFinRO] }
  <A>: { type: OpCCinit.Adv,  known_instances_in_file: [G1] }
```

For synthetic bridges (wrapper→wrapper hops that aren't named as lemmas, e.g. `RealOrcls(ChaChaPoly) ↔ RealOrcls(OChaChaPoly(I_stateless))`), the hook tries `have -> : ... by <closer_hint>.` followed by a bridge-lemma rewrite and probes the full chain.

**Example output:**
```
[AUTO-BRIDGE-SUGGEST] pasteable tactics (daemon-verified against current goal):
  rewrite -(OpCCinit.pr_CCP_OCCP I_stateless G1 &m).      ← accepted
  rewrite  (Indist.pr_RO_FinRO_D  G2).                    ← accepted
[AUTO-BRIDGE-SUGGEST] 2-step chain candidates:
  have -> : Pr[...ChaChaPoly...] = Pr[...OChaChaPoly(I_stateless)...].
  + by byequiv => //; proc; inline *; wp; call (_: ={Mem.k}); sim />.
  rewrite -(OpCCinit.pr_CCP_OCCP I_stateless G1 &m).
```

**Validated result (v6 step1 run):** 2 bridge-suggest emissions, 3 `rewrite pr_*` commits, first 5 committed tactics match the human proof ~95%. See [`prover_style_analysis.md § 6.1`](../../docs/reports/insights/prover_style_analysis.md#61-shipped) for the full validation write-up and design rationale.

**Source:** `session_hook_phases.PivotStrategyPhase._try_bridge_suggest` + `ec_pr_path_diff.py` + narrative in `session_meta.json`.

---

### 2.5 `[AUTO-SIG]` — unknown-lemma signature rescue

**Compiler-philosophy rating**: B+ (When ✅ generic pattern: tactic reports unification/arity error; Look at ✅ context retrieval: extract lemma name + lookup signature; Try 🟡 instantiated tactic: surfaces signature, doesn't write the instantiated `apply (LEMMA arg1 _ &m).`).

**Trigger:** an `apply` / `rewrite` / `exact` tactic fails with "unknown lemma" or a unification error referencing a lemma name.

**Action:** look up the lemma's full signature (arity, implicit args, module params, section-scope args) from context.ec + cross-file imports; render it as a pasteable template. Dedup'd per lemma per session via `_auto_sig_seen`.

**Why it matters.** The `AGENTS.md` / `CLAUDE.md` rule "before `apply LEMMA` on a non-trivial lemma, read its declaration first" is supposed to force the agent to run `-where` proactively, with `-sig` as a fast fallback. In practice the agent can still flail before remembering. `AUTO-SIG` makes the rescue automatic.

**Example output:**
```
[AUTO-SIG] last tactic referenced unknown/mis-typed lemma: CCA_CPA_UFCMA
  declared at chacha_poly.ec:1306 (inside section CCABody)
    declare module St : StatefulOrcl.
    declare module A  : Adv {-St}.
    lemma CCA_CPA_UFCMA (St <: StatefulOrcl) (A <: Adv {-St})
                        (G1 <: Game) (G2 <: Game) &m :
          Pr[CCA(G1).main() @ &m : res] = Pr[CCA(G2).main() @ &m : res].
  Section is exported — outside CCABody you must pass the module args explicitly.
  Pasteable forms:
    apply (CCA_CPA_UFCMA St A G1 G2 &m).
    call  (CCA_CPA_UFCMA St A G1 G2 &m).
```

**Source:** `session_hook_phases.AutoSigPhase` + `ec_search.py`.

---

## 3. Daemon Infrastructure

The daemon layer is where the speed + speculative-probing capabilities come from. It's invisible to end users (automatically spawned by `session_cli.py` when needed) but essential to `AUTO-PIVOT-VERIFIED` and `AUTO-BRIDGE-SUGGEST`.

### 3.1 `ec_daemon.py` — persistent EC subprocess pool

- Runs one `easycrypt -emacs` subprocess per session.
- Listens on `/tmp/ec_daemon.sock` (overridable via `EC_DAEMON_SOCKET`).
- Newline-delimited JSON protocol.
- Supports multiple concurrent sessions (for tree-mode provers running in parallel).

**RPC methods:**
- `open_session` / `close_session` / `list_sessions`
- `commit` — commit a tactic permanently
- `try_tactic` — speculatively test, auto-undo
- `try_chain` — sequentially test a list, stop at first failure
- `batch_try` — independent per-tactic probes (each returns its own result)
- `bridge_probe` — specialized Pr-bridge probe for `AUTO-BRIDGE-SUGGEST`
- `get_goal` — inspect current goal state

**Disable switch:** `EC_DAEMON_DISABLE=1` falls back to per-tactic subprocess (slower but simpler; useful for CI or debugging).

### 3.2 `ec_daemon_client.py` — thin RPC client

`ECDaemonClient` class wraps socket communication. Used only by `daemon_backend.py`.

### 3.3 `daemon_backend.py` — client-side shim in `session_cli`

- **Design principle: disk is truth.** The session's `history.ec` file is the single source of committed state. The daemon is a volatile cache — droppable and rebuildable at any time.
- `try_commit_latest()` — fast-path commit attempt; on any inconsistency or daemon failure, caller falls back to subprocess.
- `_sync_to(target_tactics)` — replay tactics until daemon session matches disk state.
- `invalidate()` — called on `-start` / `-prev` to drop daemon state.
- `_spawn_daemon()` — lazy-start the daemon, POSIX-lock serialized so multiple sessions don't race.

---

## 4. Standalone Utilities

### 4.1 `lemma_extract.py` (`-lemma` flag)

Extracts a section-local lemma into a standalone .ec file with all necessary context (imports, `declare module/axiom`, local modules, sibling lemmas replaced with `admit.`). Required because section-internal lemmas can't be proved by appending tactics to the original file. Handles edge cases: abstract theories, nested sections, clone-renamed types.

### 4.2 / 4.3 (removed)

`evaluator.py` and `repl.py` — the legacy pexpect evaluator stack — were
deleted along with their only caller (`eval/trial_run.py`); the managed
session pipeline (`ec_lifecycle` / `ec_proc` / `ProofNodeManager`) is the
single way EasyCrypt runs.

### 4.4 `core/env_loader.py`

Dependency-free `.env` loader. `load_env(env_path=None)` reads `.env` (default: project root) and populates `os.environ` with every `KEY=VALUE` line not already set. Skips blanks and `#`-comments.

### 4.5 `core/easycrypt/ec_env.py`

Holds the opam switch name used to launch EC (default: `easycrypt`). Referenced by every tool that shells out to `easycrypt`.

---

## 5. Support Libraries (not directly user-facing)

These are imported by the tools above. Worth knowing about if you're extending the system.

### 5.1 `ec_pr_path_diff.py` (formerly `ec_structural_diff.py`)

The workhorse behind `AUTO-DIFF`, `AUTO-PIVOT`, and `AUTO-BRIDGE-SUGGEST`. Provides two layers:

- **Layer 2 (Functor-path diff):** walk two module expressions (`RealOrcls(OChaChaPoly(IFinRO))` vs `Indist.Distinguish(D(A), IndBlock)`) as parse trees; report every differing node and its depth. Critical insight: a diff at the *root* node tells the agent "these are entirely different game architectures — don't byequiv directly."
- **Layer 1 (Program alignment):** align two pRHL statement lists row-by-row; mark each row IDENTICAL / DIFFER / SIDE-ONLY.

Key functions: `parse_module_expr`, `diff_module_trees`, `pivot_applicability` (the lemma-to-goal scoring function), `extract_lemma_inventory`, `program_alignment_diff`, `probability_diff`, `eager_diff`.

### 5.2 `ec_goal_patterns.py`

Catalog of ~8–12 pattern detectors. Each returns a `PatternHit {id, when, advice, refs}`. Matched on every `-goal-info` call and on `AUTO-KB` triggers. Patterns are curated from repeated stuck-points (e.g., P20 = "pRHL where `sim` silently fails due to renamed globals").

### 5.3 `ec_goal_parser.py`

Classifies a goal as one of: pRHL, eager, hoare, phoare, ambient, probability. Used by `-goal-info`, `AUTO-DIFF`, and internally whenever other tools need to know the goal type.

---

## 6. Flag Summary Table

| Flag | Tool / Module | Purpose | Stateful? | Daemon-accelerated? |
|------|---------------|---------|-----------|---------------------|
| `-start` | session_cli | begin session (optionally load .ec + lemma) | yes | — |
| `-next` / `-prev` | session_cli | commit / undo tactic | yes | yes |
| `-try` | session_cli | speculative tactic test | yes | yes |
| `-chain [--keep-on-fail]` | session_cli | sequential apply with rollback | yes | yes |
| `-checkpoint NAME` / `-replay NAME` | session_cli | save / restore named snapshots | yes | — |
| `-status` | session_cli | session metadata | yes | — |
| `-show-proof LEMMA` | session_cli | print proof body of proved lemma | yes | — |
| `-goal-info` | ec_goal_parser | goal type + parser probe/strategy actions | yes | — |
| `-goal-json` | session_projection | goal-state adapter with authority fields | yes | — |
| `-program-json` | ec_program_ir | program-shape adapter with authority fields | yes | — |
| `-goal-patterns` **new** | ec_goal_patterns | KB pattern matches | yes | — |
| `-diagnose` | ec_diagnose | classify error + strategy/execution fix hint | yes | — |
| `-align` | swap_align | suggest swaps for pRHL alignment | yes | — |
| `-swap-search` | swap_search | brute-force swap sequences | yes | yes |
| `-suggest-close` | ec_suggest | static closing candidates; probe before commit | yes | — |
| `-search QUERY [--max N]` | ec_search | lemma/axiom search | no | — |
| `-lemma-hints` | ec_lemma_lookup | op-based lemma retrieval; recommends `-sig` | yes | — |
| `-clones` | ec_search | list clone renamings | yes | — |
| `-sig LEMMA` | ec_search | lemma signature lookup | yes | — |
| `-file-index FILE` | ec_file_index | structured .ec file outline | no | — |
| `-bridge-lemmas` | ec_bridge_lemmas | bridge templates / probe candidates | yes | — |
| `-bridge-probe STMT` **new** | session_cli + daemon | daemon-verify Pr-equality bridge closer | yes | yes |
| `-inv-from-lemma LEMMA` | ec_inv_from_lemma | extract call invariant probe/template | yes | — |
| `-lemma LEMMA` | lemma_extract | section-local extraction | no | — |
| `-write-back` | session_cli | commit proof to source file | yes | — |
| `-verify LEMMA` | session_cli | type-check proof + admit check | yes | — |

**Hook summary:**

| Hook | Trigger | Source | Daemon-backed? |
|------|---------|--------|----------------|
| `[AUTO-KB]` | structural tactic fails | `session_hooks.auto_kb_trigger` + `ec_goal_patterns` | no |
| `[AUTO-DIFF]` | tactic succeeds | `session_hook_phases.AutoDiffPhase` + `ec_pr_path_diff` | no |
| `[AUTO-PIVOT]` | tactic succeeds | `session_hook_phases.PivotStrategyPhase` + `ec_pr_path_diff` | no |
| `[AUTO-PIVOT-VERIFIED]` | tactic succeeds | `session_hook_phases.PivotStrategyPhase` | **yes** |
| `[AUTO-PIVOT-CALL-READY]` | tactic succeeds on equiv goal | `session_hook_phases.PivotStrategyPhase` | **yes** |
| `[AUTO-BRIDGE-SUGGEST]` | Pr[A]=Pr[B] goal | `session_hook_phases.PivotStrategyPhase` | **yes** |
| `[AUTO-SIG]` | apply/rewrite fails | `session_hook_phases.AutoSigPhase` | no |

---

## 7. Time-Saved Summary

| Without tools (LLM alone) | With tools | Time saved |
|---|---|---|
| Guess goal type from raw EC output | `-goal-info` / `AUTO-KB`: explicit classification + patterns | 3–5 min per wrong guess |
| Try 5–10 swap variations by trial and error | `-swap-search`: automated search with daemon | 5–10 min |
| Read 200 lines of theory files for a lemma name | `-search`: instant regex match | 2–5 min |
| Misinterpret error, try random fixes | `-diagnose`: cause + fix + execution/strategy tag | 3–5 min |
| Manually count program positions for alignment | `-align` / `AUTO-DIFF`: parsed structure + suggestions | 3–5 min |
| Hand-copy invariant from oracle lemma | `-inv-from-lemma`: extracted template | 2–3 min |
| Can't prove section-local lemmas at all | `-lemma`: auto-extraction | Entire proof blocked |
| `smt()` fails, no idea what lemma hints to use | `-suggest-close` / `AUTO-PIVOT`: targeted suggestions | 2–5 min |
| Flail on `apply PIVOT` with wrong arity (Signature-Availability Crisis) | `-sig` / `AUTO-SIG` / `AUTO-PIVOT-VERIFIED` | 5–25 min (`step2_1` regression) |
| Bridge-too-big spiral into manual `while` invariant | `AUTO-BRIDGE-SUGGEST` with daemon-verified rewrites | entire proof path (see step1) |

**Total estimated time savings per hard proof: 30–60 minutes** (from ~60 min to ~15–30 min; validated on ChaChaPoly `step1` where v6 with `AUTO-BRIDGE-SUGGEST` matched the human proof's first 5 tactics ~95%).

---

## 8. For MCP Implementation

Each user-facing tool has a clear input → output contract suitable for MCP. Stateful tools require an active EC session (managed by `session_cli` or, in MCP, by a stateful server that maintains `ec_daemon` sessions across tool calls).

The AUTO-* hooks are **inherent to `-next` / `-chain`** — in MCP they should be returned as structured fields on the tactic-commit response, not as separate tools. Recommended response schema:

```json
{
  "accepted": true,
  "goal_after": "…",
  "auto_diff":        { "shape": "pRHL", "aligned_rows": [...] },
  "auto_pivot":       [ { "name": "...", "tag": "DIRECT", "verified": true, "plan": "..." } ],
  "auto_bridge":      [ { "kind": "1-step", "tactic": "..." } ],
  "auto_kb":          [ { "id": "P20", "advice": "..." } ],
  "auto_sig":         null
}
```

This way an MCP-backed agent sees the hook payloads as structured data on every tool call without needing to parse stdout.

---

## 9. Related Reading

- [`docs/reports/insights/prover_style_analysis.md`](../../docs/reports/insights/prover_style_analysis.md) — failure-mode analysis that motivated the AUTO-* hooks, with v6 validation data.
- `/CLAUDE.md` and `/AGENTS.md` (repo root) — operational rules (no-`admit.`, declaration lookup before `apply`, eval-mode redaction, no cross-session dir reads).
- `/TESTING.md` (repo root) — test patterns (A/B, regression, single-branch).
